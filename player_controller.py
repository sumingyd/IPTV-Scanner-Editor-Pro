import sys
import vlc
from PyQt6.QtCore import QObject, pyqtSignal
from log_manager import LogManager, global_logger

class PlayerController(QObject):
    play_error = pyqtSignal(str)
    play_state_changed = pyqtSignal(bool)  # True=播放中, False=停止
    
    def __init__(self, video_widget, channel_model=None):
        super().__init__()
        self.logger = global_logger
        self.video_widget = video_widget
        self.channel_model = channel_model
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
        """播放指定URL的视频 - 使用异步方式避免阻塞UI线程"""
        if not self.player:
            self._init_player()
            
        try:
            # 先异步停止当前播放
            self.stop()
            
            # 使用异步方式播放新URL
            import threading
            
            def async_play():
                try:
                    media = self.instance.media_new(url)
                    self.player.set_media(media)
                    self.player.play()
                    self.is_playing = True
                    # 使用QTimer在主线程中安全地发射信号
                    from PyQt6.QtCore import QTimer
                    QTimer.singleShot(0, lambda: self.play_state_changed.emit(True))
                    self.logger.info(f"正在播放: {channel_name}")
                except Exception as e:
                    self.logger.error(f"异步播放失败: {e}")
                    # 使用QTimer在主线程中安全地发射错误信号
                    QTimer.singleShot(0, lambda: self.play_error.emit(str(e)))
            
            # 在后台线程中执行播放操作
            play_thread = threading.Thread(target=async_play, daemon=True)
            play_thread.start()
            
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
        """切换暂停/播放状态 - 使用异步方式避免阻塞UI线程"""
        if self.player:
            try:
                # 使用异步方式切换暂停状态
                import threading
                
                def async_pause():
                    try:
                        self.player.pause()
                        self.is_playing = not self.is_playing
                    except Exception as e:
                        self.logger.error(f"异步暂停失败: {e}")
                
                # 在后台线程中执行暂停操作
                pause_thread = threading.Thread(target=async_pause, daemon=True)
                pause_thread.start()
                
                return self.is_playing
            except Exception as e:
                self.logger.error(f"暂停失败: {e}")
                return False
        return False

    def stop(self):
        """停止播放 - 使用异步方式避免阻塞UI线程"""
        if self.player:
            try:
                # 使用异步方式停止播放，避免阻塞UI线程
                import threading
                
                def async_stop():
                    try:
                        self.player.stop()
                        self.is_playing = False
                        # 使用QTimer在主线程中安全地发射信号
                        from PyQt6.QtCore import QTimer
                        QTimer.singleShot(0, lambda: self.play_state_changed.emit(False))
                    except Exception as e:
                        self.logger.error(f"异步停止播放失败: {e}")
                
                # 在后台线程中执行停止操作
                stop_thread = threading.Thread(target=async_stop, daemon=True)
                stop_thread.start()
                
            except Exception as e:
                self.logger.error(f"停止播放失败: {e}")
                self.is_playing = False
                self.play_state_changed.emit(False)

    def release(self):
        """释放播放器资源"""
        try:
            if self.player:
                self.player.stop()
                self.player.release()
                self.player = None
            if self.instance:
                self.instance.release()
                self.instance = None
            self.is_playing = False
            self.logger.info("播放器资源已释放")
        except Exception as e:
            self.logger.error(f"释放播放器资源失败: {e}")

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
            if result:
                # 播放成功，标记频道为有效
                if hasattr(self, 'channel_model') and self.channel_model:
                    self.channel_model.set_channel_valid(url, True)
            else:
                self.logger.warning(f"播放失败: {url} (状态码: {self.player.get_state().value if self.player else 'N/A'})")
            return result
        except Exception as e:
            self.logger.error(f"播放异常: {str(e)}")
            return False
