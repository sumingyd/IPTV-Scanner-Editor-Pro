import threading
import queue
import time
from typing import List, Dict
from url_parser import URLRangeParser
from log_manager import LogManager
from channel_model import ChannelListModel
from PyQt6.QtCore import pyqtSignal, QObject

class ScannerController(QObject):
    """扫描控制器，管理多线程扫描过程"""
    
    # 定义信号
    progress_updated = pyqtSignal(int, int)  # 当前进度, 总数
    channel_found = pyqtSignal(dict)  # 有效的频道信息
    scan_completed = pyqtSignal()
    stats_updated = pyqtSignal(dict)  # 统计信息
    
    # 在类定义中声明信号
    channel_validated = pyqtSignal(int, bool, int, str)  # index, valid, latency, resolution

    def __init__(self, model: ChannelListModel, epg_manager=None):
        super().__init__()
        self.logger = LogManager()
        self.model = model
        self.epg_manager = epg_manager
        self.url_parser = URLRangeParser()
        self.is_validating = False
        self.stats_lock = threading.Lock()
        self.worker_queue = queue.Queue()
        self.stop_event = threading.Event()
        self.workers = []
        self.timeout = 10  # 默认超时时间
        self.channel_counter = 0
        self.counter_lock = threading.Lock()
        
        # 确保信号连接
        self.channel_found.connect(self.model.add_channel)
        self.stats = {
            'total': 0,
            'valid': 0,
            'invalid': 0,
            'start_time': 0,
            'elapsed': 0
        }
        
    def start_scan(self, base_url: str, thread_count: int = 10, timeout: int = 10, user_agent: str = None, referer: str = None):
        """开始扫描
        Args:
            base_url: 基础URL
            thread_count: 线程数
            timeout: 每个线程的超时时间(秒)
            user_agent: 请求头中的User-Agent
            referer: 请求头中的Referer
        """
        if self.stop_event.is_set():
            self.stop_event.clear()
            
        # 设置验证器参数
        from validator import StreamValidator
        StreamValidator.timeout = timeout
        if user_agent:
            StreamValidator.headers['User-Agent'] = user_agent
        if referer:
            StreamValidator.headers['Referer'] = referer
            
        # 解析URL范围并保存到实例变量
        self.urls = self.url_parser.parse_url(base_url)
        if not self.urls:
            self.logger.warning("没有可扫描的URL")
            return
            
        self.stats = {
            'total': len(self.urls),
            'valid': 0,
            'invalid': 0,
            'start_time': time.time(),
            'elapsed': 0
        }
        
        # 填充任务队列
        for url in self.urls:
            self.worker_queue.put(url)
            
        # 创建工作线程
        self.workers = []
        for i in range(thread_count):
            worker = threading.Thread(
                target=self._worker,
                name=f"ScannerWorker-{i}",
                daemon=True
            )
            worker.start()
            self.workers.append(worker)
            
        # 启动统计更新线程
        stats_thread = threading.Thread(
            target=self._update_stats,
            name="StatsUpdater",
            daemon=True
        )
        stats_thread.start()
        
        self.logger.info(f"开始扫描 {len(self.urls)} 个URL，使用 {thread_count} 个线程")
        
    def stop_scan(self):
        """停止扫描"""
        self.stop_event.set()
        for worker in self.workers:
            if worker.is_alive():
                worker.join(timeout=1)
        self.workers = []
        self.logger.info("扫描已停止")

    def start_validation(self, model, threads, timeout):
        """开始有效性验证"""
        self.is_validating = True
        self.stop_event.clear()
        self.timeout = timeout
        
        # 初始化统计信息
        self.stats = {
            'total': model.rowCount(),
            'valid': 0,
            'invalid': 0,
            'start_time': time.time(),
            'elapsed': 0
        }
        
        # 填充任务队列
        for i in range(model.rowCount()):
            channel = model.get_channel(i)
            self.worker_queue.put((channel['url'], i))  # 同时传递索引
            
        # 创建工作线程
        self.workers = []
        for i in range(threads):
            worker = threading.Thread(
                target=self._validation_worker,
                name=f"ValidationWorker-{i}",
                daemon=True
            )
            worker.start()
            self.workers.append(worker)
            
        # 启动统计更新线程
        stats_thread = threading.Thread(
            target=self._update_stats,
            name="ValidationStatsUpdater",
            daemon=True
        )
        stats_thread.start()

    def stop_validation(self):
        """停止有效性验证"""
        self.stop_event.set()
        self.is_validating = False
        self.logger.info("有效性验证已停止")

    def _validation_worker(self):
        """有效性验证工作线程"""
        while not self.stop_event.is_set():
            try:
                url, index = self.worker_queue.get_nowait()
                valid, latency, resolution = self._check_channel(url)
                
                # 更新模型
                self.channel_validated.emit(index, valid, latency, resolution)
                
                # 更新统计 (仅在_worker中更新，避免重复统计)
                if not self.is_validating:
                    with self.stats_lock:
                        if valid:
                            self.stats['valid'] += 1
                        else:
                            self.stats['invalid'] += 1
            except queue.Empty:
                break
            except Exception as e:
                self.logger.error(f"验证线程错误: {e}")
        
    def _worker(self):
        """工作线程函数"""
        while not self.stop_event.is_set():
            try:
                url = self.worker_queue.get_nowait()
            except queue.Empty:
                break
                
            try:
                # 调用验证器获取完整结果
                valid, latency, resolution, result = self._check_channel(url)
                
                # 构建频道信息
                channel_info = self._build_channel_info(url, valid, latency, resolution, result)
                
                # 处理所有频道信息 (无论有效与否)
                self.channel_found.emit(channel_info)
                
                # 更新进度和统计信息 (使用stats_lock确保线程安全)
                with self.stats_lock:
                    # 更新进度
                    self.progress_updated.emit(
                        self.stats['valid'] + self.stats['invalid'],
                        self.stats['total']
                    )
                        
                # 处理所有验证结果
                # 确保使用解析后的具体URL
                channel_info['url'] = url
                
                # 从URL中提取频道编号 (格式: CHANNEL00000001)
                # 示例URL: http://150.138.8.143/00/SNM/CHANNEL00000001/index.m3u8
                try:
                    # 处理组播转单播URL格式 (如http://.../rtp/239.21.1.1:5002)
                    if any(x in url.lower() for x in ['/rtp/', '/udp/', '/rtsp/']):
                        # 组播频道名处理逻辑已在上面的统一流程中完成
                        # 这里只需要确保使用正确的名称
                        if 'name' not in channel_info:
                            channel_info['name'] = channel_info.get('raw_name', url.split('/')[-1])
                    # 处理CHANNEL格式URL
                    elif 'CHANNEL' in url and '/index.m3u8' in url:
                        channel_num = url.split('CHANNEL')[1].split('/')[0]
                        if channel_num.isdigit():
                            channel_info['name'] = f"CHANNEL{channel_num}"
                        else:
                            raise ValueError("无效的频道编号格式")
                    # 其他URL格式
                    else:
                        # 使用URL最后部分作为频道名
                        channel_info['name'] = url.split('/')[-1].split('?')[0].split('#')[0]
                except Exception as e:
                    # 如果提取失败，使用URL最后部分作为频道名
                    channel_info['name'] = url.split('/')[-1].split('?')[0].split('#')[0]
                    self.logger.warning(f"从URL提取频道编号失败({e})，使用默认名称: {channel_info['name']}")
                
                # 添加分组信息
                channel_info['group'] = '未分类'
                
                # 记录所有频道信息
                self.channel_found.emit(channel_info)
                status = "有效" if valid else "无效"
                self.logger.info(f"添加频道({status}): {channel_info['name']} - {url}")
                self.logger.debug(f"频道详情: {channel_info}")
                
                # 更新进度
                with self.stats_lock:
                    self.progress_updated.emit(
                        self.stats['valid'] + self.stats['invalid'],
                        self.stats['total']
                    )
            except Exception as e:
                self.logger.error(f"工作线程错误: {e}")
        
    def _extract_channel_name_from_url(self, url: str) -> str:
        """从URL提取频道名，支持多种协议格式"""
        try:
            # 标准化URL为小写
            url_lower = url.lower()
            
            # 组播地址提取 - 保留完整组播地址作为频道名
            for proto in ['rtp', 'stp', 'udp', 'rtsp']:
                proto_prefix = f'/{proto}/'
                if proto_prefix in url_lower:
                    full_addr = url.split(proto_prefix)[1].split('?')[0].split('#')[0].strip()
                    # 对于组播地址，返回完整地址如"239.21.1.1:5002"
                    return full_addr
            
            # HTTP/HTTPS地址提取
            if url_lower.startswith(('http://', 'https://')):
                # 提取具体频道地址部分，忽略范围地址
                if '[' in url and ']' in url:  # 如果是范围地址
                    # 提取具体频道编号部分
                    base_url = url.split('[')[0]
                    channel_part = url.split('[')[1].split(']')[0]
                    if '-' in channel_part:  # 如果是范围
                        return base_url.split('/')[-1]  # 返回基础频道名
                    else:  # 如果是具体频道
                        return channel_part
                else:  # 普通URL
                    return url.split('/')[-1].split('?')[0].split('#')[0].strip()
            
            # 默认提取URL最后部分
            return url.split('/')[-1].split('?')[0].split('#')[0].strip()
        except Exception as e:
            self.logger.error(f"提取频道名失败: {e}")
            return url  # 如果提取失败，返回完整URL

    def _update_progress(self, valid: bool):
        """更新扫描进度"""
        with self.stats_lock:
            if valid:
                self.stats['valid'] += 1
            else:
                self.stats['invalid'] += 1
            
            # 发射进度更新信号
            self.progress_updated.emit(
                self.stats['valid'] + self.stats['invalid'],
                self.stats['total']
            )

    def _process_valid_channel(self, channel_info: dict):
        """处理有效频道"""
        # 直接更新模型中的频道信息
        self.model.add_channel(channel_info)
        self.logger.info(f"添加有效频道: {channel_info['name']}")

    def _build_channel_info(self, url: str, valid: bool, latency: int, resolution: str, result: dict) -> dict:
        """构建完整的频道信息字典"""
        # 获取原始频道名
        raw_name = result.get('service_name', '')
        if not raw_name or raw_name == "未知频道":
            raw_name = self._extract_channel_name_from_url(url)
        
        # 只要有分辨率就视为有效
        is_valid = bool(resolution)
        
        # 处理频道名称映射
        from channel_mappings import get_channel_info
        mapped_info = get_channel_info(raw_name) if is_valid else None
        final_name = mapped_info['standard_name'] if mapped_info and mapped_info.get('standard_name') else raw_name
        
        # 构建频道信息字典
        return {
            'url': url,
            'name': final_name,
            'raw_name': raw_name,
            'valid': is_valid,
            'latency': latency,
            'resolution': resolution,
            'status': '有效' if is_valid else '无效',
            'group': '未分类',
            'logo_url': mapped_info.get('logo_url') if mapped_info else None
        }

    def _check_channel(self, url: str) -> tuple:
        """检查频道有效性
        返回: (valid: bool, latency: int, resolution: str, result: dict)
        """
        from validator import StreamValidator
        validator = StreamValidator()
        result = validator.validate_stream(url, timeout=self.timeout)
        return result['valid'], result['latency'], result.get('resolution', ''), result
        
    def is_scanning(self):
        """检查是否正在扫描"""
        return len(self.workers) > 0 and not self.stop_event.is_set()

    def _update_stats(self):
        """更新统计信息线程"""
        try:
            while not self.stop_event.is_set() and any(w.is_alive() for w in self.workers):
                try:
                    self.stats['elapsed'] = time.time() - self.stats['start_time']
                    
                    # 区分扫描和验证的统计更新
                    if self.is_validating:
                        # 验证统计信息
                        stats_text = (
                            f"总数: {self.stats['total']} | "
                            f"有效: {self.stats['valid']} | "
                            f"无效: {self.stats['invalid']} | "
                            f"耗时: {time.strftime('%H:%M:%S', time.gmtime(self.stats['elapsed']))}"
                        )
                        self.stats_updated.emit({
                            'text': stats_text,
                            'is_validation': True,
                            'stats': self.stats
                        })
                    else:
                        # 扫描统计信息
                        stats_text = (
                            f"总数: {self.stats['total']} | "
                            f"有效: {self.stats['valid']} | "
                            f"无效: {self.stats['invalid']} | "
                            f"耗时: {time.strftime('%H:%M:%S', time.gmtime(self.stats['elapsed']))}"
                        )
                        self.stats_updated.emit({
                            'text': stats_text,
                            'is_validation': False,
                            'stats': self.stats
                        })
                    
                    time.sleep(0.5)
                except RuntimeError:
                    break
                
            # 扫描完成
            if not self.stop_event.is_set():
                try:
                    self.scan_completed.emit()
                except RuntimeError:
                    pass
        finally:
            # 重置扫描状态
            self.stop_event.set()
            self.workers = []
