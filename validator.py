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
        self._current_url = None  # 当前正在验证的URL

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
                    valid, latency = await self._validate_channel(url)
                    if valid:
                        valid_channels.append({**channel, 'valid': True, 'latency': latency})
                    else:
                        invalid_channels.append({**channel, 'valid': False, 'latency': 0.0})
                except Exception as e:
                    logger.warning(f"验证失败: {url} - {str(e)}")
                    invalid_channels.append({**channel, 'valid': False})
                
                # 更新进度
                progress = int((i + 1) / total * 100)
                status_msg = f"验证进度: {len(valid_channels)}有效/{len(invalid_channels)}无效"
                if valid_channels:
                    avg_latency = sum(c['latency'] for c in valid_channels) / len(valid_channels)
                    status_msg += f" | 平均延迟: {avg_latency:.2f}s"
                self.progress_updated.emit(progress, status_msg)

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

    async def _validate_channel(self, url: str) -> tuple[bool, float]:
        """使用ffprobe验证单个频道并返回(是否有效, 延迟秒数)"""
        self._current_url = url
        # 验证命令
        validate_cmd = [
            self._ffprobe_path,
            '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=codec_name',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            url
        ]
        
        # 延迟测量命令
        latency_cmd = [
            self._ffprobe_path,
            '-v', 'error',
            '-show_entries', 'format=start_time',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            url
        ]
        
        # 执行验证
        validate_proc = await asyncio.create_subprocess_exec(
            *validate_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        self._active_processes.append(validate_proc)
        
        try:
            _, stderr = await asyncio.wait_for(validate_proc.communicate(), timeout=self._timeout)
            valid = validate_proc.returncode == 0
            
            # 如果有效则测量延迟
            latency = 0.0
            if valid:
                latency_proc = await asyncio.create_subprocess_exec(
                    *latency_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                self._active_processes.append(latency_proc)
                try:
                    stdout, _ = await asyncio.wait_for(latency_proc.communicate(), timeout=self._timeout)
                    if latency_proc.returncode == 0:
                        latency = float(stdout.decode().strip())
                finally:
                    if latency_proc.returncode is None:
                        latency_proc.terminate()
                    try:
                        self._active_processes.remove(latency_proc)
                    except ValueError:
                        pass
            
            return (valid, latency)
        except asyncio.TimeoutError:
            return (False, 0.0)
        finally:
            self._current_url = None
            if validate_proc.returncode is None:
                validate_proc.terminate()
            try:
                self._active_processes.remove(validate_proc)
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
