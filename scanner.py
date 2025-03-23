import asyncio
import subprocess
from typing import List, Dict, Optional
from PyQt6.QtCore import QObject, pyqtSignal
from utils import setup_logger
from qasync import asyncSlot
from utils import parse_ip_range

logger = setup_logger('Scanner')

class StreamScanner(QObject):
    progress_updated = pyqtSignal(int, str)    # 进度百分比, 状态信息
    scan_finished = pyqtSignal(list)           # 有效频道列表
    error_occurred = pyqtSignal(str)           # 错误信息

    def __init__(self):
        super().__init__()
        self._is_scanning = False
        self._timeout = 5  # 默认超时时间为 5 秒
        self._thread_count = 10  # 默认线程数为 10
        self._scan_lock = asyncio.Lock()  # 扫描任务锁

    def set_timeout(self, timeout: int) -> None:
        """设置超时时间（单位：秒）"""
        self._timeout = timeout

    def set_thread_count(self, thread_count: int) -> None:
        """设置线程数"""
        self._thread_count = thread_count

    @asyncSlot()
    async def start_scan(self, ip_pattern: str) -> None:
        """正确的异步任务启动方式"""
        async with self._scan_lock:
            if self._is_scanning:
                self.error_occurred.emit("已有扫描任务正在进行")
                return

            self._is_scanning = True
            try:
                # 直接返回协程对象而不是任务
                await self._scan_task(ip_pattern)
            finally:
                self._is_scanning = False

    async def _scan_task(self, ip_pattern: str) -> None:
        """执行扫描的核心任务"""
        try:
            # 生成待扫描URL列表
            urls = parse_ip_range(ip_pattern)  # 直接使用 parse_ip_range 生成的完整 URL
            total = len(urls)
            valid_channels = []
            
            # 使用信号量控制并发数
            semaphore = asyncio.Semaphore(self._thread_count)
            
            async def probe_with_semaphore(url: str) -> Optional[Dict]:
                async with semaphore:
                    return await self._probe_stream(url)
            
            # 并发探测
            tasks = [probe_with_semaphore(url) for url in urls]
            results = [None] * len(tasks)  # 初始化结果列表
            
            # 添加进度更新
            completed = 0
            for i, task in enumerate(asyncio.as_completed(tasks)):
                result = await task
                completed += 1
                progress = int((completed / total) * 100)
                self.progress_updated.emit(progress, f"正在扫描 {completed}/{total}")
                results[i] = result
            
            # 过滤有效结果
            for i, result in enumerate(results):
                if result is not None:
                    # 生成频道名称（使用序号代替）
                    channel_name = f"频道 {i + 1}"
                    valid_channels.append({
                        'name': channel_name,
                        'url': urls[i],
                        'width': result['width'],
                        'height': result['height'],
                        'codec': result['codec'],
                        'resolution': f"{result['width']}x{result['height']}"
                    })
            
            # 发送最终结果
            if self._is_scanning:
                self.scan_finished.emit(valid_channels)
                
        except Exception as e:
            logger.exception("扫描任务异常终止")
            self.error_occurred.emit(f"扫描错误: {str(e)}")
            raise
        finally:
            self._is_scanning = False

    async def _probe_stream(self, url: str) -> Optional[Dict]:
        """探测单个流媒体信息"""
        try:
            # 构建ffprobe命令
            cmd = [
                'ffprobe',
                '-v', 'error',
                '-select_streams', 'v:0',
                '-show_entries', 'stream=codec_name,width,height',
                '-of', 'csv=p=0',
                '-timeout', str(self._timeout * 1_000_000),  # 微秒单位
                url
            ]
            
            # 启动子进程
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # 等待结果（带超时）
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=self._timeout
            )
            
            # 检查返回码
            if proc.returncode != 0:
                err_msg = stderr.decode().strip()
                logger.error(f"流探测失败: {url} - {err_msg}")  # 增加错误日志
                return None
                
            # 解析输出
            output = stdout.decode().strip()
            
            # 处理多余的空行和重复信息
            lines = [line for line in output.splitlines() if line.strip()]
            if not lines:
                logger.warning(f"ffprobe 输出为空: {url}")
                return None
            
            # 取第一行有效数据
            video_info = lines[0].split(',')
            if len(video_info) < 3:
                logger.warning(f"ffprobe 输出格式错误: {video_info}")
                return None
            
            return {
                'codec': video_info[0],
                'width': int(video_info[1]),
                'height': int(video_info[2])
            }
            
        except asyncio.TimeoutError:
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
        self._is_scanning = False
        logger.info("扫描已强制停止")
