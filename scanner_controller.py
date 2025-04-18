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
    
    def __init__(self, model: ChannelListModel):
        super().__init__()
        self.logger = LogManager()
        self.model = model
        self.url_parser = URLRangeParser()
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
        
    def _worker(self):
        """工作线程函数"""
        while not self.stop_event.is_set():
            try:
                url = self.worker_queue.get_nowait()
            except queue.Empty:
                break
                
            # 检测URL有效性
            channel_info = self._validate_url(url)
            
            # 更新统计信息
            with threading.Lock():
                if channel_info.get('valid', False):
                    self.stats['valid'] += 1
                else:
                    self.stats['invalid'] += 1
                    
            # 只发送有效频道并更新UI
            if channel_info['valid']:
                self.channel_found.emit(channel_info)
                
            # 更新进度
            self.progress_updated.emit(
                self.stats['valid'] + self.stats['invalid'],
                self.stats['total']
            )
            
        self.logger.debug(f"工作线程 {threading.current_thread().name} 退出")
        
    def _validate_url(self, url: str) -> Dict:
        """验证URL有效性"""
        from validator import StreamValidator
        validator = StreamValidator()
        result = validator.validate_stream(url, timeout=self.timeout)
        
        # 生成频道名称 (线程名-序号)
        thread_num = int(threading.current_thread().name.split('-')[-1]) + 1
        channel_num = self.stats['valid'] + 1
        channel_name = f"频道-{thread_num}-{channel_num}"
        
        # 添加分辨率信息
        if result.get('resolution'):
            channel_name = f"{channel_name} ({result['resolution']})"
            
        return {
            'url': url,
            'name': channel_name,
            'valid': result['valid'],
            'latency': result['latency'],
            'resolution': result['resolution'],
            'codec': result['codec'],
            'bitrate': result['bitrate'],
            'error': result['error']
        }
        
    def _update_stats(self):
        """更新统计信息线程"""
        while not self.stop_event.is_set() and any(w.is_alive() for w in self.workers):
            self.stats['elapsed'] = time.time() - self.stats['start_time']
            self.stats_updated.emit(self.stats)
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
