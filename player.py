import vlc
import asyncio
import platform
from PyQt6 import QtWidgets, QtCore
from PyQt6.QtCore import pyqtSignal
from utils import setup_logger

logger = setup_logger('Player')

class VLCPlayer(QtWidgets.QWidget):
    state_changed = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.instance = None
        self.media_player = None
        self.hw_accel = 'd3d11va'
        self._init_vlc()
        self._init_ui()
        self._setup_connections()
        self.history = []
        self.max_history = 50

    def _init_vlc(self):
        """初始化 VLC 实例"""
        args = [
            '--avcodec-hw=none',  # 强制禁用硬件解码
            '--network-caching=3000',
            '--no-video-title-show',
            '--drop-late-frames',
            '--skip-frames'
        ]
        try:
            self.instance = vlc.Instance(args)
            if self.instance is None:
                raise RuntimeError("无法创建 VLC 实例，请检查参数是否正确。")
            self.media_player = self.instance.media_player_new()
        except Exception as e:
            logger.error(f"VLC 初始化失败: {str(e)}")
            raise

    def _init_ui(self):
        """初始化界面组件"""
        self.video_frame = QtWidgets.QFrame()
        self.video_frame.setStyleSheet("background-color: black;")
        self.video_frame.setMinimumSize(640, 360)
        
        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.video_frame)
        self.setLayout(layout)
        
        QtCore.QTimer.singleShot(100, self._bind_video_window)

    def _setup_connections(self):
        """初始化信号连接"""
        try:
            event_manager = self.media_player.event_manager()
            event_manager.event_attach(vlc.EventType.MediaPlayerPlaying, self._on_play)
            event_manager.event_attach(vlc.EventType.MediaPlayerStopped, self._on_stop)
            event_manager.event_attach(vlc.EventType.MediaPlayerPaused, self._on_pause)
        except Exception as e:
            logger.error(f"事件绑定失败: {str(e)}")

    def _bind_video_window(self):
        """窗口绑定逻辑"""
        if not self.video_frame or not self.media_player:
            return

        try:
            if platform.system() == 'Windows':
                hwnd = int(self.video_frame.winId())
                self.media_player.set_hwnd(hwnd)
            else:
                xid = int(self.video_frame.winId())
                self.media_player.set_xwindow(xid)
        except Exception as e:
            logger.error(f"窗口绑定失败: {str(e)}")
            QtCore.QTimer.singleShot(100, self._bind_video_window)

    def set_hardware_accel(self, hw_accel: str) -> None:
        """设置硬件加速"""
        self.hw_accel = hw_accel
        logger.info(f"硬件加速设置为: {hw_accel}")

    async def async_play(self, url: str, retry=3) -> bool:
        """播放核心方法"""
        for attempt in range(retry):
            try:
                media = self.instance.media_new(url)
                opts = [
                    f':network-caching={2000 + attempt * 1000}',
                    ':rtsp-tcp'
                ]
                # 将 opts 列表拼接为字符串
                media.add_options(' '.join(opts))
                self.media_player.set_media(media)
                
                if self.media_player.play() == -1:
                    raise RuntimeError("播放失败")
                
                if not await self._wait_for_playback():
                    raise TimeoutError("播放超时")
                
                return True
            except Exception as e:
                logger.error(f"播放失败 ({attempt+1}/{retry}): {str(e)}")
                if attempt == retry - 1:  # 最后一次尝试失败后，停止播放
                    self.stop()
        return False

    async def _wait_for_playback(self, timeout=10) -> bool:
        """等待播放状态"""
        start_time = asyncio.get_event_loop().time()
        while (asyncio.get_event_loop().time() - start_time) < timeout:
            await asyncio.sleep(0.5)
            if self.media_player.is_playing():
                return True
        return False

    def toggle_pause(self) -> None:
        """暂停/继续播放"""
        if self.media_player.is_playing():
            self.media_player.pause()
            logger.info("播放已暂停")
        else:
            self.media_player.play()
            logger.info("播放已继续")

    def stop(self) -> None:
        """停止播放"""
        try:
            if self.media_player:
                if self.media_player.is_playing():
                    self.media_player.stop()
                # 确保释放媒体资源
                media = self.media_player.get_media()
                if media:
                    media.release()
                # 释放播放器资源
                self.media_player.release()
                self.media_player = None
            self.state_changed.emit("播放已停止")
            logger.info("播放器资源已释放")
        except Exception as e:
            logger.error(f"停止播放失败: {str(e)}")

    def set_volume(self, volume: int) -> None:
        """设置音量 (0-100)"""
        if 0 <= volume <= 100:
            self.media_player.audio_set_volume(volume)
            logger.info(f"音量设置为: {volume}")
        else:
            logger.warning(f"无效的音量值: {volume}")

    def _on_play(self, event):
        """播放事件处理"""
        self.state_changed.emit("正在播放...")

    def _on_pause(self, event):
        """暂停事件处理"""
        self.state_changed.emit("播放已暂停")

    def _on_stop(self, event):
        """停止事件处理"""
        logger.info("播放停止，当前解码器状态: %s", self.media_player.get_state())
        self.state_changed.emit("播放停止")

    def __del__(self):
        """资源清理"""
        try:
            if self.media_player:
                self.media_player.release()
            if self.instance:
                self.instance.release()
            logger.info("资源已释放")
        except Exception as e:
            logger.error(f"资源释放失败: {str(e)}")