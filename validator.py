import asyncio
from typing import List, Dict, Union
from PyQt6.QtCore import QObject, pyqtSignal
from qasync import asyncSlot
from utils import setup_logger
import subprocess
import os

logger = setup_logger('Validator')

class StreamValidator(QObject):
    """流媒体有效性验证器"""
    progress_updated = pyqtSignal(int, str)  # 进度百分比, 状态信息
    validation_finished = pyqtSignal(dict)   # 验证结果字典
    error_occurred = pyqtSignal(str)         # 错误信息
    
    def __init__(self):
        super().__init__()
        self._timeout = 10  # 默认超时时间(秒)
        self._ffprobe_path = os.path.join('ffmpeg', 'bin', 'ffprobe.exe')
        self._is_running = False
        self._active_processes = []  # 跟踪所有活动的ffprobe进程

    def set_timeout(self, timeout: int) -> None:
        """设置验证超时时间(秒)"""
        self._timeout = timeout

    def is_running(self) -> bool:
        """检查验证是否在进行中"""
        return self._is_running

    @asyncSlot()
    async def validate_playlist(self, playlist_data: Union[List[Dict], List[str]]) -> Dict:
        """验证播放列表有效性"""
        if not playlist_data:
            self.error_occurred.emit("播放列表为空")
            return {'valid': [], 'invalid': []}

        # 处理纯URL字符串列表的情况
        if isinstance(playlist_data[0], str):
            playlist_data = [{'url': url} for url in playlist_data]

        self._is_running = True
        total = len(playlist_data)
        valid_channels = []
        invalid_channels = []
        
        try:
            for i, channel in enumerate(playlist_data):
                if not self._is_running:  # 检查是否被停止
                    break
                    
                url = channel.get('url', '')
                if not url:
                    invalid_channels.append({**channel, 'valid': False})
                    continue
                
                try:
                    valid = await self._validate_channel(url)
                    if valid:
                        valid_channels.append({**channel, 'valid': True})
                    else:
                        invalid_channels.append({**channel, 'valid': False})
                except Exception as e:
                    logger.warning(f"验证失败: {url} - {str(e)}")
                    invalid_channels.append({**channel, 'valid': False})
                
                # 更新进度
                progress = int((i + 1) / total * 100)
                self.progress_updated.emit(
                    progress,
                    f"验证进度: {len(valid_channels)}有效/{len(invalid_channels)}无效"
                )

            # 验证完成
            result = {
                'valid': valid_channels,
                'invalid': invalid_channels,
                'total': total
            }
            self.validation_finished.emit(result)
            return result
            
        except Exception as e:
            logger.error(f"验证出错: {str(e)}")
            self.error_occurred.emit(f"验证出错: {str(e)}")
            return {'valid': [], 'invalid': []}
        finally:
            self._is_running = False

    async def _validate_channel(self, url: str) -> bool:
        """使用ffprobe验证单个频道"""
        cmd = [
            self._ffprobe_path,
            '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=codec_name',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            url
        ]
        
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        self._active_processes.append(proc)  # 跟踪新创建的进程
        
        try:
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=self._timeout)
            return proc.returncode == 0
        except asyncio.TimeoutError:
            return False
        finally:
            if proc.returncode is None:
                proc.terminate()
            try:
                self._active_processes.remove(proc)  # 清理已完成进程
            except ValueError:
                pass

    async def stop_validation(self):
        """停止验证"""
        self._is_running = False
        # 终止所有活动的ffprobe进程
        for proc in self._active_processes:
            if proc.returncode is None:
                try:
                    proc.terminate()
                    await proc.wait()
                except ProcessLookupError:
                    pass
        self._active_processes.clear()
        self.progress_updated.emit(0, "验证已停止")
