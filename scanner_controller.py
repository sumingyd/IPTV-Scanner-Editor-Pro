import threading
import queue
import time
from typing import List, Dict
from url_parser import URLRangeParser
from log_manager import LogManager
from channel_model import ChannelListModel
from PyQt6.QtCore import pyqtSignal, QObject
from channel_mappings import extract_channel_name_from_url

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
        """开始扫描"""
        if self.stop_event.is_set():
            self.stop_event.clear()
            
        from validator import StreamValidator
        StreamValidator.timeout = timeout
        if user_agent:
            StreamValidator.headers['User-Agent'] = user_agent
        if referer:
            StreamValidator.headers['Referer'] = referer
            
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
        
        for url in self.urls:
            self.worker_queue.put(url)
            
        self.workers = []
        for i in range(thread_count):
            worker = threading.Thread(
                target=self._worker,
                name=f"ScannerWorker-{i}",
                daemon=True
            )
            worker.start()
            self.workers.append(worker)
            
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
        
        while not self.worker_queue.empty():
            try:
                self.worker_queue.get_nowait()
            except queue.Empty:
                break
                
        for worker in self.workers:
            if worker.is_alive():
                worker.join(timeout=0.5)
                
        self.workers = []
        self.worker_queue = queue.Queue()
        self.logger.info("扫描已完全停止，任务队列已清空")

    def start_validation(self, model, threads, timeout):
        """开始有效性验证"""
        self.is_validating = True
        self.stop_event.clear()
        self.timeout = timeout
        
        self.stats = {
            'total': model.rowCount(),
            'valid': 0,
            'invalid': 0,
            'start_time': time.time(),
            'elapsed': 0
        }
        
        for i in range(model.rowCount()):
            channel = model.get_channel(i)
            self.worker_queue.put((channel['url'], i))
            
        self.workers = []
        for i in range(threads):
            worker = threading.Thread(
                target=self._validation_worker,
                name=f"ValidationWorker-{i}",
                daemon=True
            )
            worker.start()
            self.workers.append(worker)
            
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
                time.sleep(0.01)
                
                result = self._check_channel(url)
                valid = result['valid']
                latency = result['latency']
                resolution = result.get('resolution', '')
                
                self.channel_validated.emit(index, valid, latency, resolution)
                
                if not self.is_validating:
                    with self.stats_lock:
                        if valid:
                            self.stats['valid'] += 1
                        else:
                            self.stats['invalid'] += 1
            except queue.Empty:
                time.sleep(0.1)
                break
            except Exception as e:
                self.logger.error(f"验证线程错误: {e}")
                time.sleep(0.1)
        
    def _worker(self):
        """工作线程函数"""
        while not self.stop_event.is_set():
            try:
                url = self.worker_queue.get_nowait()
            except queue.Empty:
                break
                
            try:
                result = self._check_channel(url)
                valid = result['valid']
                latency = result['latency']
                resolution = result.get('resolution', '')
                
                channel_info = self._build_channel_info(url, valid, latency, resolution, result)
                if not channel_info:
                    continue
                    
                # 确保频道信息包含必要字段
                channel_info.setdefault('name', channel_info.get('raw_name', extract_channel_name_from_url(url)))
                channel_info.setdefault('group', '未分类')
                
                # 记录完整的频道信息，无论有效与否
                log_msg = f"频道信息 - 原始名: {channel_info['raw_name']}, 映射名: {channel_info['name']}, URL: {url}, 状态: {'有效' if valid else '无效'}"
                if valid:
                    self.channel_found.emit(channel_info)
                    self.logger.info(log_msg)
                else:
                    self.logger.info(log_msg)
                
                with self.stats_lock:
                    if valid:
                        self.stats['valid'] += 1
                    else:
                        self.stats['invalid'] += 1
                    
                    self.progress_updated.emit(
                        self.stats['valid'] + self.stats['invalid'],
                        self.stats['total']
                    )
                
            except Exception as e:
                self.logger.error(f"工作线程错误: {e}")
        
    def _update_progress(self, valid: bool):
        """更新扫描进度"""
        with self.stats_lock:
            if valid:
                self.stats['valid'] += 1
            else:
                self.stats['invalid'] += 1
            
            self.progress_updated.emit(
                self.stats['valid'] + self.stats['invalid'],
                self.stats['total']
            )

    def _process_valid_channel(self, channel_info: dict):
        """处理有效频道"""
        self.model.add_channel(channel_info)
        self.logger.info(f"添加有效频道: {channel_info['name']}")

    def _build_channel_info(self, url: str, valid: bool, latency: int, resolution: str, result: dict) -> dict:
        """构建完整的频道信息字典"""
        from channel_mappings import get_channel_info
        
        try:
            # 获取原始频道名
            raw_name = result.get('service_name', '') or extract_channel_name_from_url(url)
            if raw_name == "未知频道":
                raw_name = extract_channel_name_from_url(url)
            
            # 获取映射信息
            mapped_info = get_channel_info(raw_name) if valid else None
            mapped_name = mapped_info.get('standard_name', raw_name) if mapped_info else raw_name
            
            # 构建频道信息
            channel_info = {
                'url': url,
                'name': mapped_name,
                'raw_name': raw_name,
                'valid': bool(resolution),
                'latency': latency,
                'resolution': resolution,
                'status': '有效' if resolution else '无效',
                'group': '未分类',
                'logo_url': mapped_info.get('logo_url') if mapped_info else None
            }
            return channel_info
            
        except Exception as e:
            self.logger.error(f"构建频道信息失败: {e}")
            return None

    def _check_channel(self, url: str, raw_channel_name: str = None) -> dict:
        """检查频道有效性"""
        from validator import StreamValidator
        validator = StreamValidator()
        return validator.validate_stream(url, raw_channel_name=raw_channel_name, timeout=self.timeout)
        
    def is_scanning(self):
        """检查是否正在扫描"""
        return len(self.workers) > 0 and not self.stop_event.is_set()

    def _update_stats(self):
        """更新统计信息线程"""
        try:
            while not self.stop_event.is_set() and any(w.is_alive() for w in self.workers):
                try:
                    self.stats['elapsed'] = time.time() - self.stats['start_time']
                    
                    if self.is_validating:
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
                
            if not self.stop_event.is_set():
                try:
                    self.scan_completed.emit()
                except RuntimeError:
                    pass
        finally:
            self.stop_event.set()
            self.workers = []
