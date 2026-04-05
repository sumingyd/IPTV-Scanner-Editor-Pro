import sys
import vlc
import json
import subprocess
import os
import time
from PyQt6.QtCore import QObject, pyqtSignal
from core.log_manager import global_logger


# 编码映射表 - 将 FourCC 编码转换为人类可读的名称
VIDEO_CODEC_MAP = {
    'h264': 'H.264',
    'avc1': 'H.264',
    'h265': 'H.265',
    'hevc': 'H.265',
    'vp9': 'VP9',
    'vp8': 'VP8',
    'av01': 'AV1',
    'mpeg': 'MPEG-2',
    'mp2v': 'MPEG-2',
    'mp4v': 'MPEG-4',
    'divx': 'DivX',
    'xvid': 'XviD',
    'wmv3': 'WMV3',
    'wmv2': 'WMV2',
    'wmv1': 'WMV1',
    'theo': 'Theora',
    'flv1': 'FLV',
    'rv40': 'RealVideo 4',
    'rv30': 'RealVideo 3',
    '462h': 'H.264',  # 常见的 H.264 变体
    '462H': 'H.264',
    'avc3': 'H.264',
    'hvc1': 'H.265',
    'hev1': 'H.265',
    'vp09': 'VP9',
    'av00': 'AV1',
}

AUDIO_CODEC_MAP = {
    'aac': 'AAC',
    'mp3': 'MP3',
    'mp2': 'MP2',
    'mp1': 'MP1',
    'ac3': 'AC-3',
    'eac3': 'E-AC-3',
    'dts': 'DTS',
    'dtsh': 'DTS-HD',
    'opus': 'Opus',
    'vorb': 'Vorbis',
    'flac': 'FLAC',
    'alac': 'ALAC',
    'wma': 'WMA',
    'pcm': 'PCM',
    'twos': 'PCM',
    'sowt': 'PCM',
    'lpcm': 'PCM',
    'agpm': 'AAC',  # 常见的 AAC 变体
    'aacp': 'AAC+',
    'aach': 'AAC-HE',
    'mp4a': 'AAC',
    'ac-3': 'AC-3',
    'dtsc': 'DTS',
    'dtsh': 'DTS-HD',
    'dtse': 'DTS-HD Master Audio',
}


class PlayerController(QObject):
    play_error = pyqtSignal(str)
    play_state_changed = pyqtSignal(bool)  # True=播放中, False=停止
    media_info_ready = pyqtSignal(dict)  # 当ffprobe获取到信息时发射此信号

    def __init__(self, video_widget, channel_model=None):
        super().__init__()
        self.logger = global_logger
        self.video_widget = video_widget
        self.channel_model = channel_model
        self.instance = None
        self.player = None
        self.is_playing = False
        self.current_url = None
        self.media_info = {}
        
        self._init_player()
        
        # 连接信号
        self.media_info_ready.connect(self._on_media_info_ready)

    def _on_media_info_ready(self, info):
        """当ffprobe获取到信息时调用"""
        self.media_info = info

    def _get_ffprobe_path(self):
        """获取ffprobe路径"""
        # 1. 尝试从打包后的路径查找
        if getattr(sys, 'frozen', False):
            base_path = os.path.dirname(sys.executable)
            exe_path = os.path.join(base_path, 'ffmpeg', 'bin', 'ffprobe.exe')
            if os.path.exists(exe_path):
                return exe_path

        # 2. 尝试从开发环境路径查找 - 项目根目录
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)  # 从services目录到项目根目录
        dev_path = os.path.join(project_root, 'ffmpeg', 'bin', 'ffprobe.exe')
        if os.path.exists(dev_path):
            return dev_path

        # 3. 尝试从系统PATH查找
        try:
            from shutil import which
            path = which('ffprobe')
            if path:
                return path
        except ImportError:
            pass

        # 最后尝试直接调用
        return 'ffprobe'

    def _run_ffprobe(self, url, timeout=5):
        """运行ffprobe获取媒体信息"""
        try:
            ffprobe_path = self._get_ffprobe_path()
            cmd = [
                ffprobe_path,
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                '-show_programs',
                url
            ]

            # 在Windows上需要处理特殊字符
            if sys.platform == 'win32':
                cmd = [arg.replace('^', '^^').replace('&', '^&') for arg in cmd]

            # 设置环境变量
            env = os.environ.copy()
            env['PATH'] = os.path.dirname(ffprobe_path) + os.pathsep + env['PATH']

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=False,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0,
                shell=True if sys.platform == 'win32' else False,
                env=env,
                cwd=os.path.dirname(ffprobe_path) if os.path.dirname(ffprobe_path) else os.getcwd()
            )

            stdout_bytes, stderr_bytes = process.communicate(timeout=timeout)
            stdout = stdout_bytes.decode('utf-8', errors='replace')
            stderr = stderr_bytes.decode('utf-8', errors='replace')

            if process.returncode == 0:
                if stdout.strip():
                    data = json.loads(stdout)
                    return self._parse_ffprobe_output(data)
            return {}
        except Exception as e:
            self.logger.debug(f"ffprobe执行失败: {e}")
            return {}

    def _parse_ffprobe_output(self, data):
        """解析ffprobe输出"""
        result = {}

        # 解析视频流信息
        if 'streams' in data:
            for stream in data['streams']:
                if stream.get('codec_type') == 'video':
                    # 分辨率
                    if 'width' in stream and 'height' in stream:
                        result['resolution'] = f"{stream['width']}x{stream['height']}"
                    # 视频编码
                    if 'codec_name' in stream:
                        codec = stream['codec_name'].lower()
                        result['video_codec'] = VIDEO_CODEC_MAP.get(codec, codec.upper())
                    # 视频级别
                    if 'profile' in stream:
                        result['video_profile'] = stream['profile']
                    # 码率
                    if 'bit_rate' in stream:
                        bitrate = int(stream['bit_rate'])
                        if bitrate > 1000000:
                            result['bitrate'] = f"{bitrate/1000000:.1f}Mbps"
                        else:
                            result['bitrate'] = f"{bitrate/1000:.1f}kbps"
                    # 帧率
                    if 'r_frame_rate' in stream:
                        try:
                            num, den = map(int, stream['r_frame_rate'].split('/'))
                            if den > 0:
                                fps = num / den
                                result['fps'] = f"{fps:.1f}fps"
                        except Exception:
                            pass
                    # 色彩空间
                    if 'color_space' in stream:
                        result['color_space'] = stream['color_space']
                    # 色彩标准
                    if 'color_primaries' in stream:
                        result['color_primaries'] = stream['color_primaries']
                elif stream.get('codec_type') == 'audio':
                    # 音频编码
                    if 'codec_name' in stream:
                        codec = stream['codec_name'].lower()
                        result['audio_codec'] = AUDIO_CODEC_MAP.get(codec, codec.upper())
                    # 音频码率
                    if 'bit_rate' in stream:
                        bitrate = int(stream['bit_rate'])
                        result['audio_bitrate'] = f"{bitrate/1000:.1f}kbps"
                    # 声道数
                    if 'channels' in stream:
                        result['audio_channels'] = f"{stream['channels']}.0ch"
                    # 采样率
                    if 'sample_rate' in stream:
                        result['audio_samplerate'] = f"{int(stream['sample_rate'])}kHz"
                    # 位深
                    if 'bits_per_sample' in stream:
                        result['audio_bits'] = f"{stream['bits_per_sample']}bit"

        return result

    def _init_player(self):
        """初始化VLC播放器"""
        try:
            # 禁用VLC控制台输出
            vlc_args = [
                '--no-xlib',
                '--quiet',
                '--no-stats',
                '--no-video-title-show',
                '--rtsp-timeout=30',  # 设置RTSP超时时间为30秒
                '--network-caching=3000',  # 设置网络缓存为3000毫秒，提高稳定性
                '--live-caching=3000',  # 设置直播缓存为3000毫秒
                '--file-caching=3000',  # 设置文件缓存为3000毫秒
                '--sout-mux-caching=3000',  # 设置输出缓存为3000毫秒
                '--ignore-config'  # 忽略配置文件，使用当前参数
            ]
            
            # 从配置文件读取RTSP协议类型
            from core.config_manager import ConfigManager
            config = ConfigManager()
            rtsp_protocol = config.get_value('Player', 'rtsp_protocol', 'tcp')
            if rtsp_protocol.lower() == 'tcp':
                vlc_args.append('--rtsp-tcp')  # 使用TCP协议而非UDP，提高稳定性
            self.instance = vlc.Instance(vlc_args)
            self.player = self.instance.media_player_new()

            # 设置硬件加速
            if sys.platform.startswith('win'):
                self.player.set_hwnd(self.video_widget.winId())
                self.player.video_set_format("RV32", 0, 0, 0)
            else:
                self.player.set_xwindow(self.video_widget.winId())

            # 设置视频缩放模式为填充（让视频填满窗口）
            self.player.video_set_scale(0)  # 0 表示自动缩放
            self.player.video_set_aspect_ratio(None)  # 使用视频原始比例

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
            # 先停止当前播放
            self.stop()

            # 保存当前URL
            self.current_url = url
            
            # 在主线程中获取窗口ID（winId()必须在主线程调用）
            win_id = None
            if self.video_widget and sys.platform.startswith('win'):
                win_id = int(self.video_widget.winId())

            # 使用异步方式播放新URL
            import threading

            def async_play():
                try:
                    # 设置视频输出窗口
                    if win_id is not None:
                        self.player.set_hwnd(win_id)
                    
                    media = self.instance.media_new(url)
                    # 为RTSP流添加特殊处理
                    if url.lower().startswith('rtsp://'):
                        # 设置RTSP相关选项
                        media.add_option('rtsp-tcp')  # 使用TCP协议
                        media.add_option('network-caching=3000')  # 设置网络缓存
                        media.add_option('live-caching=3000')  # 设置直播缓存
                        media.add_option('file-caching=3000')  # 设置文件缓存
                        media.add_option('sout-mux-caching=3000')  # 设置输出缓存
                    self.player.set_media(media)
                    self.player.play()
                    self.is_playing = True
                    
                    # 直接发射信号
                    self.play_state_changed.emit(True)
                    self.logger.info(f"正在播放: {channel_name}")
                    
                    # 保存当前URL，用于检查是否已经切换了频道
                    current_url_for_fetch = url
                    
                    # 在另一个后台线程中使用ffprobe获取媒体信息（不阻碍播放）
                    def fetch_media_info():
                        try:
                            # 对RTSP协议的URL跳过ffprobe获取媒体信息
                            if not current_url_for_fetch.lower().startswith('rtsp://'):
                                info = self._run_ffprobe(current_url_for_fetch, timeout=10)  # 增加超时时间到10秒
                                # 检查是否已经切换了频道，如果切换了就不发射信号
                                if self.current_url == current_url_for_fetch:
                                    # 通过信号将信息传递到主线程
                                    self.media_info_ready.emit(info)
                        except Exception as e:
                            self.logger.debug(f"ffprobe获取信息失败: {e}")
                    
                    info_thread = threading.Thread(target=fetch_media_info, daemon=True)
                    info_thread.start()
                    
                except Exception as e:
                    self.logger.error(f"异步播放失败: {e}")
                    # 发射错误信号
                    self.play_error.emit(str(e))

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
        # 优先使用ffprobe获取的信息
        if self.media_info.get('resolution'):
            return self.media_info['resolution']
        return None

    def get_video_resolution_from_media_info(self):
        """从媒体信息获取原始分辨率（可能更准确）"""
        # 优先使用ffprobe获取的信息
        if self.media_info.get('resolution'):
            return self.media_info['resolution']
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
    
    def get_current_time(self):
        """获取当前播放时间（毫秒）"""
        if self.player and self.is_playing:
            try:
                return self.player.get_time()
            except Exception:
                pass
        return 0
    
    def get_total_time(self):
        """获取总时长（毫秒）"""
        if self.player and self.is_playing:
            try:
                return self.player.get_length()
            except Exception:
                pass
        return 0
    
    def get_position(self):
        """获取播放位置（0.0-1.0）"""
        if self.player and self.is_playing:
            try:
                return self.player.get_position()
            except Exception:
                pass
        return 0.0
    
    def get_volume(self):
        """获取当前音量（0-100）"""
        if self.player:
            try:
                return self.player.audio_get_volume()
            except Exception:
                pass
        return 50
    
    def _fourcc_to_string(self, fourcc):
        """将 FourCC 整数值转换为字符串"""
        try:
            if isinstance(fourcc, int):
                # 将整数转换为四个字符
                return ''.join([chr((fourcc >> 24) & 0xFF),
                              chr((fourcc >> 16) & 0xFF),
                              chr((fourcc >> 8) & 0xFF),
                              chr(fourcc & 0xFF)]).strip()
            return fourcc
        except:
            return str(fourcc)
    
    def get_audio_codec(self):
        """获取音频编码"""
        # 优先使用ffprobe获取的信息
        if self.media_info.get('audio_codec'):
            return self.media_info['audio_codec']
        return "--"
    
    def get_video_codec(self):
        """获取视频编码"""
        # 优先使用ffprobe获取的信息
        if self.media_info.get('video_codec'):
            return self.media_info['video_codec']
        return "--"
    
    def get_bitrate(self):
        """获取码率"""
        # 优先使用ffprobe获取的信息
        if self.media_info.get('bitrate'):
            return self.media_info['bitrate']
        return "--"
    
    def get_fps(self):
        """获取帧率"""
        # 优先使用ffprobe获取的信息
        if self.media_info.get('fps'):
            return self.media_info['fps']
        return "--"
    
    def get_network_stats(self):
        """获取网络统计"""
        return ""
    
    def get_video_profile(self):
        """获取视频编码级别"""
        # 优先使用ffprobe获取的信息
        if self.media_info.get('video_profile'):
            return self.media_info['video_profile']
        return "--"
    
    def get_video_color_space(self):
        """获取视频色彩空间"""
        # 优先使用ffprobe获取的信息
        if self.media_info.get('color_space'):
            return self.media_info['color_space']
        return "--"
    
    def get_video_color_primaries(self):
        """获取视频色彩标准"""
        # 优先使用ffprobe获取的信息
        if self.media_info.get('color_primaries'):
            return self.media_info['color_primaries']
        return "--"
    
    def get_audio_bitrate(self):
        """获取音频码率"""
        # 优先使用ffprobe获取的信息
        if self.media_info.get('audio_bitrate'):
            return self.media_info['audio_bitrate']
        return "--"
    
    def get_audio_channels(self):
        """获取音频声道数"""
        # 优先使用ffprobe获取的信息
        if self.media_info.get('audio_channels'):
            return self.media_info['audio_channels']
        return "--"
    
    def get_audio_samplerate(self):
        """获取音频采样率"""
        # 优先使用ffprobe获取的信息
        if self.media_info.get('audio_samplerate'):
            return self.media_info['audio_samplerate']
        return "--"
    
    def get_audio_bits(self):
        """获取音频位深"""
        # 优先使用ffprobe获取的信息
        if self.media_info.get('audio_bits'):
            return self.media_info['audio_bits']
        return "--"
    
    def get_audio_format(self):
        """获取音频格式"""
        # 优先使用ffprobe获取的信息
        if self.media_info.get('audio_codec'):
            return self.media_info['audio_codec']
        return "--"
    
    def get_network_protocol(self):
        """获取网络协议"""
        if self.player and self.is_playing:
            try:
                media = self.player.get_media()
                if media:
                    url = media.get_mrl()
                    if url:
                        url_lower = url.lower()
                        if url_lower.startswith("rtmp://"):
                            return "RTMP"
                        elif url_lower.startswith("http://") or url_lower.startswith("https://"):
                            return "HTTP"
                        elif url_lower.startswith("rtsp://"):
                            return "RTSP"
                        elif url_lower.startswith("udp://"):
                            return "UDP"
                        elif url_lower.startswith("rtp://"):
                            return "RTP"
            except Exception as e:
                self.logger.debug(f"获取网络协议失败: {e}")
        return "--"
