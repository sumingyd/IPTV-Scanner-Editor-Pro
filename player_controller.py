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
        self.is_playing = False
        self._init_player()

    def _init_player(self):
        """初始化VLC播放器"""
        try:
            # 禁用VLC控制台输出
            vlc_args = [
                '--no-xlib', 
                '--quiet',
                '--no-stats',
                '--no-video-title-show'
            ]
            self.instance = vlc.Instance(vlc_args)
            self.player = self.instance.media_player_new()
            
            # 设置硬件加速
            if sys.platform.startswith('win'):
                self.player.set_hwnd(self.video_widget.winId())
                self.player.video_set_format("RV32", 0, 0, 0)
            else:
                self.player.set_xwindow(self.video_widget.winId())
                
            # 设置初始音量
            self.player.audio_set_volume(50)
            
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
            self.is_playing = True
            self.logger.info(f"正在播放: {channel_name}")
            return True
        except Exception as e:
            self.logger.error(f"播放失败: {e}")
            self.play_error.emit(str(e))
            return False
            
    def set_volume(self, volume):
        """设置音量(0-100)"""
        if self.player:
            self.player.audio_set_volume(volume)
            
    def toggle_pause(self):
        """切换暂停/播放状态"""
        if self.player:
            self.player.pause()
            self.is_playing = not self.is_playing
            return self.is_playing
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

    def play_channel(self, channel):
        """播放指定频道(允许任何状态)
        Args:
            channel: 可以是Channel对象或包含'url'和'name'键的字典
        """
        if not channel:
            self.logger.warning("无法播放空频道")
            return False
            
        # 处理字典或对象类型的channel
        url = channel.get('url') if isinstance(channel, dict) else getattr(channel, 'url', None)
        name = channel.get('name') if isinstance(channel, dict) else getattr(channel, 'name', '未知频道')
        
        if not url:
            self.logger.warning(f"频道[{name}]没有有效的URL")
            return False
            
        self.logger.info(f"尝试播放频道: {name} (URL: {url})")
        try:
            result = self.play(url, name)
            if not result:
                self.logger.warning(f"播放失败: {url} (状态码: {self.player.get_state().value if self.player else 'N/A'})")
            return result
        except Exception as e:
            self.logger.error(f"播放异常: {str(e)}")
            return False
