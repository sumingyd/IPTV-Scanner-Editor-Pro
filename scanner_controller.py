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

    def __init__(self, model: ChannelListModel):
        super().__init__()
        self.logger = LogManager()
        self.model = model
        self.url_parser = URLRangeParser()
        self.is_validating = False
        self.stats_lock = threading.Lock()
        self.worker_queue = queue.Queue()
        self.stop_event = threading.Event()
        self.workers = []
        self.timeout = 10  # 默认超时时间
        self.stats = {
            'total': 0,
            'valid': 0,
            'invalid': 0,
            'start_time': 0,
            'elapsed': 0
        }
        
    def start_scan(self, base_url: str, thread_count: int = 10, timeout: int = 10):
        """开始扫描"""
        if self.stop_event.is_set():
            self.stop_event.clear()
            
        # 解析URL范围
        urls = self.url_parser.parse_url(base_url)
        if not urls:
            self.logger.warning("没有可扫描的URL")
            return
            
        self.stats = {
            'total': len(urls),
            'valid': 0,
            'invalid': 0,
            'start_time': time.time(),
            'elapsed': 0
        }
        
        # 填充任务队列
        for url in urls:
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
        
        self.logger.info(f"开始扫描 {len(urls)} 个URL，使用 {thread_count} 个线程")
        
    def stop_scan(self):
        """停止扫描"""
        self.stop_event.set()
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
                
                # 更新统计
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
                # 检测URL有效性
                valid, latency, resolution = self._check_channel(url)
                
                # 生成频道信息
                channel_info = {
                    'url': url,
                    'name': f"频道-{threading.current_thread().name.split('-')[-1]}",
                    'valid': valid,
                    'latency': latency,
                    'resolution': resolution,
                    'status': '有效' if valid else '无效'
                }
                
                # 更新统计信息
                with threading.Lock():
                    if valid:
                        self.stats['valid'] += 1
                    else:
                        self.stats['invalid'] += 1
                        
                # 只发送有效频道并更新UI
                if valid:
                    self.channel_found.emit(channel_info)
                    
                # 更新进度
                self.progress_updated.emit(
                    self.stats['valid'] + self.stats['invalid'],
                    self.stats['total']
                )
            except Exception as e:
                self.logger.error(f"工作线程错误: {e}")
            
        self.logger.debug(f"工作线程 {threading.current_thread().name} 退出")
        
    def _check_channel(self, url: str) -> tuple:
        """检查频道有效性
        返回: (valid: bool, latency: int, resolution: str)
        """
        from validator import StreamValidator
        validator = StreamValidator()
        result = validator.validate_stream(url, timeout=self.timeout)
        return result['valid'], result['latency'], result.get('resolution', '')
        
    def is_scanning(self):
        """检查是否正在扫描"""
        return len(self.workers) > 0 and not self.stop_event.is_set()

    def _update_stats(self):
        """更新统计信息线程"""
        while not self.stop_event.is_set() and any(w.is_alive() for w in self.workers):
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
                self.stats_updated.emit({'text': stats_text, 'is_validation': True})
            else:
                # 扫描统计信息
                self.stats_updated.emit({'text': '', 'is_validation': False, 'stats': self.stats})
            
            time.sleep(0.5)
            
        # 扫描完成
        if not self.stop_event.is_set():
            self.scan_completed.emit()
            
        self.logger.info("扫描统计线程退出")


if __name__ == "__main__":
    # 测试代码
    from PyQt6.QtWidgets import QApplication
    import sys
    
    app = QApplication(sys.argv)
    
    class TestModel:
        def __init__(self):
            self.channels = []
            
        def add_channel(self, channel):
            self.channels.append(channel)
            print(f"添加频道: {channel['name']} - {channel['url']}")
    
    model = TestModel()
    controller = ScannerController(model)
    
    def on_progress(current, total):
        print(f"进度: {current}/{total}")
        
    def on_channel(channel):
        model.add_channel(channel)
        
    def on_complete():
        print("扫描完成")
        
    controller.progress_updated.connect(on_progress)
    controller.channel_found.connect(on_channel)
    controller.scan_completed.connect(on_complete)
    
    # 测试扫描
    controller.start_scan("http://192.168.1.1/rtp/239.1.1.[1-10]:5002", 3)
    
    # 运行5秒后停止
    threading.Timer(5, controller.stop_scan).start()
    
    sys.exit(app.exec())
