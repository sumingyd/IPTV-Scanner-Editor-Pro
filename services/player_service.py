import sys
import vlc
from PyQt6.QtCore import QObject, pyqtSignal
from core.log_manager import global_logger


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
                    # 使用默认参数捕获e的值，避免lambda执行时e已超出作用域
                    QTimer.singleShot(0, lambda e=e: self.play_error.emit(str(e)))

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
                        # 使用QTimer在主线程中安全地发射状态变化信号
                        from PyQt6.QtCore import QTimer
                        QTimer.singleShot(0, lambda: self.play_state_changed.emit(self.is_playing))
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

    def get_video_resolution(self):
        """从VLC播放器获取当前视频的分辨率"""
        if not self.player:
            return None

        try:
            # 获取当前视频尺寸 - 使用正确的VLC API
            width = self.player.video_get_width()
            height = self.player.video_get_height()

            if width > 0 and height > 0:
                resolution = f"{width}x{height}"
                self.logger.info(f"VLC获取到分辨率: {resolution}")
                return resolution
            else:
                self.logger.warning("VLC获取到的分辨率为0")
                return None
        except Exception as e:
            self.logger.debug(f"获取视频分辨率失败: {e}")
            return None

    def get_video_resolution_from_media_info(self):
        """从媒体信息获取原始分辨率（可能更准确）"""
        if not self.player:
            return None

        try:
            # 获取当前媒体
            media = self.player.get_media()
            if not media:
                return None

            # 解析媒体信息
            media.parse_with_options(vlc.MediaParseFlag.network, 5000)

            # 获取轨道信息
            tracks = media.tracks_get()
            for track in tracks:
                if track.type == vlc.TrackType.video:
                    width = track.video.width
                    height = track.video.height
                    if width > 0 and height > 0:
                        resolution = f"{width}x{height}"
                        self.logger.info(f"从媒体信息获取到分辨率: {resolution}")
                        return resolution

            return None
        except Exception as e:
            self.logger.debug(f"从媒体信息获取分辨率失败: {e}")
            return None

    def play_channel(self, channel, channel_index=None):
        """播放指定频道(允许任何状态)"""
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
                # 播放命令成功发出，但不自动标记频道为有效
                # 让用户通过"检测有效性"功能来验证频道
                self.logger.info(f"播放命令已发出: {name}")

                # 可选：延迟检查播放状态，但不更新频道有效性
                # 这可以帮助用户了解播放是否真正成功
                if hasattr(self, 'channel_model') and self.channel_model:
                    import threading

                    def check_playback_status():
                        """检查播放状态，但不更新频道有效性"""
                        try:
                            # 等待几秒让播放器稳定
                            import time
                            time.sleep(3)

                            # 检查播放器状态
                            if self.player:
                                state = self.player.get_state()
                                self.logger.info(f"播放状态检查: {name} -> {state}")

                                # 如果播放状态良好，可以记录日志但不更新频道有效性
                                if state in [vlc.State.Playing, vlc.State.Opening]:
                                    self.logger.info(f"频道 {name} 播放状态良好")
                                else:
                                    self.logger.warning(f"频道 {name} 播放状态不佳: {state}")
                        except Exception as e:
                            self.logger.warning(f"检查播放状态失败: {e}")

                    # 在后台线程中检查播放状态
                    status_thread = threading.Thread(target=check_playback_status, daemon=True)
                    status_thread.start()
            else:
                self.logger.warning(f"播放失败: {url} (状态码: {self.player.get_state().value if self.player else 'N/A'})")
            return result
        except Exception as e:
            self.logger.error(f"播放异常: {str(e)}")
            return False
