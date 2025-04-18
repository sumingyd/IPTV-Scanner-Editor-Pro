import sys
import vlc
from PyQt6.QtCore import QObject, pyqtSignal
from log_manager import LogManager

class PlayerController(QObject):
    play_error = pyqtSignal(str)
    
    def __init__(self, video_widget):
        super().__init__()
        self.logger = LogManager()
        self.video_widget = video_widget
        self.instance = None
        self.player = None
        self._init_player()

    def _init_player(self):
        """初始化VLC播放器"""
        try:
            self.instance = vlc.Instance()
            self.player = self.instance.media_player_new()
            if sys.platform.startswith('win'):
                self.player.set_hwnd(self.video_widget.winId())
            else:
                self.player.set_xwindow(self.video_widget.winId())
        except Exception as e:
            self.logger.error(f"播放器初始化失败: {e}")
            self.play_error.emit(str(e))

    def play(self, url, channel_name=""):
        """播放指定URL的视频"""
        if not self.player:
            self._init_player()
            
        try:
            self.player.stop()
            media = self.instance.media_new(url)
            self.player.set_media(media)
            self.player.play()
            self.logger.info(f"正在播放: {channel_name}")
            return True
        except Exception as e:
            self.logger.error(f"播放失败: {e}")
            self.play_error.emit(str(e))
            return False

    def stop(self):
        """停止播放"""
        if self.player:
            self.player.stop()

    def release(self):
        """释放播放器资源"""
        if self.player:
            self.player.release()
        if self.instance:
            self.instance.release()
