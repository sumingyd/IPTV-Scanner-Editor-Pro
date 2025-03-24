import asyncio
import subprocess
from typing import List, Dict, Optional
from PyQt6 import QtWidgets
from PyQt6.QtCore import QObject, pyqtSignal
from utils import setup_logger
from qasync import asyncSlot
from utils import parse_ip_range

logger = setup_logger('Scanner')

class StreamScanner(QObject):
    progress_updated = pyqtSignal(int, str)    # 进度百分比, 状态信息
    scan_finished = pyqtSignal(list)           # 有效频道列表
    channel_found = pyqtSignal(dict)           # 单个有效频道信息
    error_occurred = pyqtSignal(str)           # 错误信息

    def __init__(self):
        super().__init__()
        self._is_scanning = False
        self._timeout = 5  # 默认超时时间为 5 秒
        self._thread_count = 10  # 默认线程数为 10
        self._scan_lock = asyncio.Lock()  # 扫描任务锁
        self._start_time = 0  # 扫描开始时间
        self._scanned_count = 0  # 已扫描IP计数器

    def set_timeout(self, timeout: int) -> None:
        """设置超时时间（单位：秒）"""
        self._timeout = timeout

    def set_thread_count(self, thread_count: int) -> None:
        """设置线程数"""
        self._thread_count = thread_count

    def get_elapsed_time(self) -> float:
        """获取扫描耗时(秒)"""
        if not hasattr(self, '_start_time'):
            return 0.0
        return asyncio.get_event_loop().time() - self._start_time

    def get_scanned_count(self) -> int:
        """获取已扫描IP数量"""
        return self._scanned_count

    @asyncSlot()
    async def start_scan(self, ip_pattern: str) -> None:
        """正确的异步任务启动方式"""
        async with self._scan_lock:
            if self._is_scanning:
                self.error_occurred.emit("已有扫描任务正在进行")
                return

            self._is_scanning = True
            self._start_time = asyncio.get_event_loop().time()
            self._scanned_count = 0  # 重置计数器
            try:
                await self._scan_task(ip_pattern)
            finally:
                self._is_scanning = False

    async def _scan_task(self, ip_pattern: str) -> None:
        """执行扫描的核心任务"""
        try:
            urls = parse_ip_range(ip_pattern)
            total = len(urls)
            valid_channels = []
            
            semaphore = asyncio.Semaphore(self._thread_count)
            
            async def probe_with_semaphore(url: str) -> Optional[Dict]:
                async with semaphore:
                    await asyncio.sleep(0)
                    result = await self._probe_stream(url)
                    await asyncio.get_event_loop().run_in_executor(None, QtWidgets.QApplication.processEvents)
                    return result
            
            completed = 0
            async def process_result(url: str, result: Optional[Dict]):
                nonlocal completed, valid_channels
                self._scanned_count += 1  # 更新已扫描计数
                
                if result is not None:
                    channel_name = f"频道 {completed + 1}"
                    channel_info = {
                        'name': channel_name,
                        'url': url,
                        'width': result['width'],
                        'height': result['height'],
                        'codec': result['codec'],
                        'resolution': f"{result['width']}x{result['height']}"
                    }
                    valid_channels.append(channel_info)
                    
                    await asyncio.sleep(0)
                    self.channel_found.emit(channel_info)
                    await asyncio.sleep(0)
                    QtWidgets.QApplication.processEvents()
                
                completed += 1
                progress = int((completed / total) * 100)
                self.progress_updated.emit(progress, f"正在扫描 {completed}/{total}")
                await asyncio.sleep(0)
                QtWidgets.QApplication.processEvents()

            url_queue = asyncio.Queue()
            for url in urls:
                url_queue.put_nowait(url)

            worker_lock = asyncio.Lock()

            async def worker():
                while self._is_scanning:
                    async with worker_lock:
                        try:
                            try:
                                url = await asyncio.wait_for(url_queue.get(), timeout=0.1)
                            except asyncio.TimeoutError:
                                continue
                                
                            try:
                                result = await probe_with_semaphore(url)
                                await process_result(url, result)
                            finally:
                                url_queue.task_done()
                        except asyncio.CancelledError:
                            break
                        except Exception as e:
                            logger.error(f"Worker error: {str(e)}")
                            break

            self._workers = []
            for _ in range(self._thread_count):
                worker_task = asyncio.create_task(worker())
                self._workers.append(worker_task)
                if not self._is_scanning:
                    break
            
            try:
                await url_queue.join()
            finally:
                for w in self._workers:
                    if not w.done():
                        w.cancel()
                await asyncio.gather(*self._workers, return_exceptions=True)
            
            if self._is_scanning:
                elapsed = asyncio.get_event_loop().time() - self._start_time
                self.scan_finished.emit(valid_channels)
                self.progress_updated.emit(100, f"扫描完成，耗时 {elapsed:.1f} 秒")
                
        except Exception as e:
            logger.exception("扫描任务异常终止")
            self.error_occurred.emit(f"扫描错误: {str(e)}")
            raise
        finally:
            self._is_scanning = False

    async def _probe_stream(self, url: str) -> Optional[Dict]:
        """探测单个流媒体信息"""
        try:
            loop = asyncio.get_running_loop()
        except Exception as e:
            logger.error(f"获取事件循环失败: {str(e)}")
            return None
            
        try:
            return await loop.run_in_executor(None, self._run_ffprobe, url)
        finally:
            await asyncio.sleep(0)
            
    def _run_ffprobe(self, url: str) -> Optional[Dict]:
        """执行ffprobe命令的同步方法"""
        try:
            cmd = [
                'ffprobe',
                '-v', 'error',
                '-select_streams', 'v:0',
                '-show_entries', 'stream=codec_name,width,height',
                '-of', 'csv=p=0',
                '-timeout', str(self._timeout * 1_000_000),
                url
            ]
            
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=self._timeout
            )
            
            if result.returncode != 0:
                err_msg = result.stderr.decode().strip()
                logger.error(f"流探测失败: {url} - {err_msg}")
                return None
                
            output = result.stdout.decode().strip()
            lines = [line for line in output.splitlines() if line.strip()]
            if not lines:
                logger.warning(f"ffprobe 输出为空: {url}")
                return None
                
            video_info = lines[0].split(',')
            if len(video_info) < 3:
                logger.warning(f"ffprobe 输出格式错误: {video_info}")
                return None
                
            return {
                'codec': video_info[0],
                'width': int(video_info[1]),
                'height': int(video_info[2])
            }
            
        except subprocess.TimeoutExpired:
            logger.warning(f"流探测超时: {url}")
            return None
        except subprocess.CalledProcessError as e:
            logger.error(f"ffprobe执行错误: {str(e)}")
            return None
        except Exception as e:
            logger.exception(f"流探测异常: {url}")
            return None

    def stop_scan(self) -> None:
        """增强停止方法"""
        if not self._is_scanning:
            return
            
        self._is_scanning = False
        logger.info("扫描已强制停止")
        
        if hasattr(self, '_url_queue'):
            while not self._url_queue.empty():
                try:
                    self._url_queue.get_nowait()
                    self._url_queue.task_done()
                except:
                    break
                    
        if hasattr(self, '_workers'):
            for worker in self._workers:
                if not worker.done():
                    worker.cancel()
            self._workers.clear()
            
        if hasattr(self, 'valid_channels'):
            self.valid_channels.clear()
            
        self._url_queue = asyncio.Queue()
        self._workers = []
        self._semaphore = asyncio.Semaphore(self._thread_count)
        self._is_scanning = False
        
        if self._scan_lock.locked():
            self._scan_lock.release()
            
        self.progress_updated.emit(0, "已停止")
