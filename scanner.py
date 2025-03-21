import asyncio
import subprocess
from typing import List, Dict, Optional
from PyQt6.QtCore import QObject, pyqtSignal
from utils import parse_ip_range, setup_logger
from qasync import asyncSlot

logger = setup_logger('Scanner')

class StreamScanner(QObject):
    progress_updated = pyqtSignal(int, str)    # 进度百分比, 状态信息
    scan_finished = pyqtSignal(list)           # 有效频道列表
    error_occurred = pyqtSignal(str)           # 错误信息

    def __init__(self):
        super().__init__()
        self._is_scanning = False
        self._timeout = 5          # 单个流探测超时时间
        self._scan_lock = asyncio.Lock()  # 扫描任务锁

    @asyncSlot()
    async def start_scan(self, ip_pattern: str) -> None:
        """启动扫描任务"""
        async with self._scan_lock:
            if self._is_scanning:
                self.error_occurred.emit("已有扫描任务正在进行")
                return

            self._is_scanning = True
            try:
                await self._scan_task(ip_pattern)
            finally:
                self._is_scanning = False

    async def _scan_task(self, ip_pattern: str) -> None:
        """执行扫描的核心任务"""
        logger.debug("进入 _scan_task 方法")
        try:
            # 生成待扫描URL列表
            urls = [f"{ip}" for ip in parse_ip_range(ip_pattern)]
            total = len(urls)
            valid_channels = []
            
            logger.debug(f"生成的 URL 列表: {urls}")
            
            for i, url in enumerate(urls):
                if not self._is_scanning:
                    break
                
                # 更新进度
                progress = int((i+1)/total*100)
                self.progress_updated.emit(progress, f"扫描中 {url}")
                
                # 探测流信息
                logger.debug(f"开始探测: {url}")
                if info := await self._probe_stream(url):
                    logger.debug(f"探测成功: {url} - {info}")
                    valid_channels.append({
                        'url': url,
                        'width': info['width'],
                        'height': info['height'],
                        'codec': info['codec'],
                        'resolution': f"{info['width']}x{info['height']}"
                    })
                else:
                    logger.debug(f"探测失败: {url}")
            
            # 发送最终结果
            if self._is_scanning:
                self.scan_finished.emit(valid_channels)
                
        except Exception as e:
            logger.exception("扫描任务异常终止")
            self.error_occurred.emit(f"扫描错误: {str(e)}")
            raise
        finally:
            self._is_scanning = False

    def parse_ip_range(ip_pattern: str) -> List[str]:
        """解析 IP 范围"""
        logger.debug(f"解析 IP 范围: {ip_pattern}")
        # 在这里实现 IP 范围解析逻辑
        # 返回 IP 地址列表

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
            
            logger.debug(f"执行 ffprobe 命令: {' '.join(cmd)}")
            
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
                logger.debug(f"流探测失败: {url} - {err_msg}")
                return None
                
            # 解析输出
            video_info = stdout.decode().strip().split(',')
            logger.debug(f"ffprobe 输出: {video_info}")
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
        """停止当前扫描任务"""
        if self._is_scanning:
            logger.info("用户请求停止扫描")
            self._is_scanning = False
            self.progress_updated.emit(0, "扫描已中止")