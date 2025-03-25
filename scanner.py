import asyncio
import subprocess
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor
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
        # 创建固定大小的线程池
        self._executor = None

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
            
            # 创建线程池，大小与并发数一致
            self._executor = ThreadPoolExecutor(max_workers=self._thread_count)
            logger.info(f"创建线程池，线程数: {self._thread_count}")
            
            async def probe_url(url: str) -> tuple[str, Optional[Dict]]:
                try:
                    result = await self._probe_stream(url)
                    return (url, result)
                finally:
                    await asyncio.get_event_loop().run_in_executor(None, QtWidgets.QApplication.processEvents)
            
            # 创建所有探测任务
            tasks = [asyncio.create_task(probe_url(url)) for url in urls]
            
            # 使用asyncio.as_completed处理结果
            for future in asyncio.as_completed(tasks):
                try:
                    result = await future
                    # 由于as_completed返回的future可能不是原始对象，无法使用index查找
                    # 改为在任务内部返回URL和结果
                    url, result = result if isinstance(result, tuple) else (None, result)
                    
                    if url is None:
                        logger.warning("无法获取URL关联")
                        continue
                        
                    self._scanned_count += 1
                    
                    if result is not None:
                        channel_name = f"频道 {len(valid_channels) + 1}"
                        channel_info = {
                            'name': channel_name,
                            'url': url,
                            'width': result['width'],
                            'height': result['height'],
                            'codec': result['codec'],
                            'resolution': f"{result['width']}x{result['height']}"
                        }
                        valid_channels.append(channel_info)
                        self.channel_found.emit(channel_info)
                    
                    # 更新进度
                    progress = int((self._scanned_count / total) * 100)
                    elapsed = self.get_elapsed_time()
                    scan_speed = self._scanned_count / elapsed if elapsed > 0 else 0
                    remaining = (total - self._scanned_count) / scan_speed if scan_speed > 0 else 0
                    
                    current_ip = url.split('/')[-1].split(':')[0] if url else ""
                    status_parts = [
                        f"进度: {self._scanned_count}/{total} ({progress}%)", 
                        f"速度: {scan_speed:.1f} IP/s",
                        f"剩余: {int(remaining)}s",
                        f"当前: {current_ip}",
                        f"有效: {len(valid_channels)}"
                    ]
                    status_msg = " | ".join(filter(None, status_parts))
                    self.progress_updated.emit(progress, status_msg)
                    
                except Exception as e:
                    pass
            
            # 等待所有任务完成
            await asyncio.gather(*tasks, return_exceptions=True)
            
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
            # 添加详细日志记录
            logger.debug(f"开始探测流: {url}")
            result = await loop.run_in_executor(
                self._executor,  # 使用配置的线程池
                self._run_ffprobe, 
                url
            )
            if result:
                logger.debug(f"成功探测到流: {url} - {result}")
            else:
                logger.debug(f"未探测到有效流: {url}")
            return result
        except Exception as e:
            logger.error(f"探测流异常: {url} - {str(e)}")
            return None
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
        
        # 关闭线程池
        if self._executor:
            self._executor.shutdown(wait=False)
            self._executor = None
            
        if hasattr(self, 'valid_channels'):
            self.valid_channels.clear()
            
        self._is_scanning = False
        
        try:
            if self._scan_lock.locked():
                self._scan_lock.release()
        except RuntimeError:
            pass  # 忽略锁未被获取的错误
            
        self.progress_updated.emit(0, "已停止")
