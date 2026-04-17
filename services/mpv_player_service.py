import sys
import os
import time
import ctypes
import threading
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot, QThread, QCoreApplication, QTimer
from core.log_manager import global_logger

if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS
else:
    base_path = os.getcwd()

mpv_dir = os.path.join(base_path, 'mpv')
os.environ['MPV_HOME'] = mpv_dir
os.environ['PATH'] = mpv_dir + os.pathsep + os.environ['PATH']

libmpv_path = os.path.join(mpv_dir, 'libmpv-2.dll')
if os.path.exists(libmpv_path):
    os.environ['MPV_LIBRARY'] = libmpv_path
else:
    print(f"未找到libmpv-2.dll: {libmpv_path}")

try:
    from services.mpv_bindings import (
        libmpv, MPV_AVAILABLE, mpv_event,
        MPV_EVENT_NONE, MPV_EVENT_SHUTDOWN, MPV_EVENT_START_FILE, MPV_EVENT_END_FILE,
        MPV_EVENT_FILE_LOADED, MPV_EVENT_PROPERTY_CHANGE,
        MPV_FORMAT_STRING, MPV_FORMAT_INT64, MPV_FORMAT_DOUBLE,
    )
except Exception as e:
    print(f"使用ctypes加载libmpv-2.dll失败: {str(e)}")
    libmpv = None
    mpv_event = None
    MPV_AVAILABLE = False

try:
    import mpv
except Exception as e:
    print(f"导入mpv模块失败: {str(e)}")
    mpv = None

VIDEO_CODEC_MAP = {
    'h264': 'H.264', 'avc1': 'H.264', 'h265': 'H.265', 'hevc': 'H.265',
    'vp9': 'VP9', 'vp8': 'VP8', 'av01': 'AV1', 'mpeg': 'MPEG-2',
    'mp2v': 'MPEG-2', 'mp4v': 'MPEG-4', 'divx': 'DivX', 'xvid': 'XviD',
    'wmv3': 'WMV3', 'wmv2': 'WMV2', 'wmv1': 'WMV1', 'theo': 'Theora',
    'flv1': 'FLV', 'rv40': 'RealVideo 4', 'rv30': 'RealVideo 3',
    '462h': 'H.264', '462H': 'H.264', 'avc3': 'H.264',
    'hvc1': 'H.265', 'hev1': 'H.265', 'vp09': 'VP9', 'av00': 'AV1',
}

AUDIO_CODEC_MAP = {
    'aac': 'AAC', 'mp3': 'MP3', 'mp2': 'MP2', 'mp1': 'MP1',
    'ac3': 'AC-3', 'eac3': 'E-AC-3', 'dts': 'DTS', 'dtsh': 'DTS-HD',
    'opus': 'Opus', 'vorb': 'Vorbis', 'flac': 'FLAC', 'alac': 'ALAC',
    'wma': 'WMA', 'pcm': 'PCM', 'twos': 'PCM', 'sowt': 'PCM', 'lpcm': 'PCM',
    'agpm': 'AAC', 'aacp': 'AAC+', 'aach': 'AAC-HE', 'mp4a': 'AAC',
    'ac-3': 'AC-3', 'dtsc': 'DTS', 'dtse': 'DTS-HD Master Audio',
    'truehd': 'TrueHD',
}

DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


def _load_playback_settings():
    settings = {
        'hwdec': True,
        'cache_secs': 1.0,
        'demuxer_max_bytes_mib': 16,
        'demuxer_max_back_bytes_mib': 512,
        'fcc_prefetch_count': 2,
        'source_timeout_sec': 3,
        'enable_protocol_adaptive': True,
        'hls_start_at_live_edge': False,
        'hls_readahead_secs': 0,
        'user_agent': DEFAULT_USER_AGENT,
        'tls_verify': False,
        'http_headers': '',
        'rtsp_transport': 'tcp',
        'rtsp_user_agent': 'VLC/3.0.18Libmpv',
        'network_timeout_sec': 0,
    }
    try:
        from core.config_manager import ConfigManager
        config = ConfigManager()
        s = config.load_playback_settings()
        settings.update(s)
    except Exception:
        pass
    return settings


class MpvPlayerController(QObject):
    play_error = pyqtSignal(str)
    play_state_changed = pyqtSignal(bool)
    media_info_ready = pyqtSignal(dict)
    live_media_info_updated = pyqtSignal(dict)

    def __init__(self, video_widget, channel_model=None):
        super().__init__()
        self.logger = global_logger
        self.video_widget = video_widget
        self.channel_model = channel_model
        self.mpv_handle = None
        self.is_playing = False
        self.is_paused = False
        self.current_url = None
        self.media_info = {}
        self.event_timer = None
        self._playback_settings = _load_playback_settings()
        self._current_speed = 1.0
        self._live_info_timer = None

        try:
            if libmpv is None:
                error_msg = "libmpv-2.dll加载失败"
                self.logger.error(error_msg)
                self.play_error.emit(error_msg)
                return

            self.mpv_handle = libmpv.mpv_create()
            if not self.mpv_handle:
                error_msg = "创建mpv实例失败"
                self.logger.error(error_msg)
                self.play_error.emit(error_msg)
                return

            window_id = self.video_widget.winId()
            if hasattr(window_id, 'value'):
                window_id = window_id.value

            try:
                window_id_int = int(window_id)
                window_id_str = f"{window_id_int}".encode('utf-8')
                result = libmpv.mpv_set_property_string(self.mpv_handle, b'wid', window_id_str)
                if result < 0:
                    self.logger.error(f"设置窗口ID失败: {result}")
            except Exception as e:
                self.logger.error(f"设置窗口ID失败: {str(e)}")

            libmpv.mpv_set_property_string(self.mpv_handle, b'vo', b'gpu')
            hwdec = b'd3d11va' if self._playback_settings.get('hwdec', True) else b'no'
            libmpv.mpv_set_property_string(self.mpv_handle, b'hwdec', hwdec)
            libmpv.mpv_set_property_string(self.mpv_handle, b'gpu-api', b'd3d11')
            libmpv.mpv_set_property_string(self.mpv_handle, b'osc', b'no')
            libmpv.mpv_set_property_string(self.mpv_handle, b'osd-bar', b'no')
            libmpv.mpv_set_property_string(self.mpv_handle, b'log-level', b'error')
            libmpv.mpv_set_property_string(self.mpv_handle, b'no-window-dragging', b'yes')
            libmpv.mpv_set_property_string(self.mpv_handle, b'window-scale', b'1.0')
            libmpv.mpv_set_property_string(self.mpv_handle, b'border', b'no')

            libmpv.mpv_set_property_string(self.mpv_handle, b'keep-open', b'yes')
            libmpv.mpv_set_property_string(self.mpv_handle, b'idle', b'yes')
            libmpv.mpv_set_property_string(self.mpv_handle, b'ytdl', b'no')

            ua = self._playback_settings.get('user_agent', DEFAULT_USER_AGENT)
            if ua:
                libmpv.mpv_set_property_string(self.mpv_handle, b'user-agent', ua.encode('utf-8'))

            if not self._playback_settings.get('tls_verify', True):
                libmpv.mpv_set_property_string(self.mpv_handle, b'tls-verify', b'no')

            libmpv.mpv_set_property_string(self.mpv_handle, b'mute', b'no')
            libmpv.mpv_set_property_string(self.mpv_handle, b'audio', b'yes')
            libmpv.mpv_set_property_string(self.mpv_handle, b'audio-device', b'auto')

            net_to = self._playback_settings.get('network_timeout_sec', 0)
            if net_to > 0:
                libmpv.mpv_set_property_string(self.mpv_handle, b'network-timeout', str(net_to).encode('utf-8'))

            cpu_count = os.cpu_count() or 1
            threads = max(2, cpu_count // 2)
            libmpv.mpv_set_property_string(self.mpv_handle, b'vd-lavc-threads', str(threads).encode('utf-8'))

            result = libmpv.mpv_initialize(self.mpv_handle)
            if result < 0:
                error_msg = f"初始化mpv失败: {result}"
                self.logger.error(error_msg)
                self.play_error.emit(error_msg)
                libmpv.mpv_destroy(self.mpv_handle)
                self.mpv_handle = None
                return

            try:
                libmpv.mpv_observe_property(self.mpv_handle, 1, b'pause', MPV_FORMAT_STRING)
            except Exception as e:
                self.logger.warning(f"订阅pause属性失败: {str(e)}")

            self.logger.info("mpv播放器初始化成功")

            self.event_timer = QTimer(self)
            self.event_timer.timeout.connect(self._process_events)
            self.event_timer.start(100)

        except Exception as e:
            error_msg = f"初始化mpv播放器失败: {str(e)}"
            self.logger.error(error_msg)
            self.play_error.emit(error_msg)
            if self.mpv_handle:
                libmpv.mpv_destroy(self.mpv_handle)
                self.mpv_handle = None

    def _set_mpv_string(self, name, value):
        try:
            if self.mpv_handle:
                libmpv.mpv_set_property_string(self.mpv_handle, name.encode('utf-8'), str(value).encode('utf-8'))
        except Exception:
            pass

    def _extract_original_url(self, url):
        """从 FCC URL 中提取原始 URL"""
        # 检测是否是 FCC 代理 URL: http://proxy/rtp/...?fcc=server
        if '/rtp/' in url and 'fcc=' in url:
            try:
                # 解析 URL
                from urllib.parse import urlparse, parse_qs
                parsed = urlparse(url)
                query = parse_qs(parsed.query)
                
                # 提取 fcc 参数
                if 'fcc' in query:
                    fcc_server = query['fcc'][0]  # 例如：150.138.8.132:8027
                    # 提取路径中的 RTP 部分
                    path_parts = parsed.path.split('/rtp/')
                    if len(path_parts) > 1:
                        rtp_part = path_parts[1]  # 例如：239.21.1.120:5002
                        # 构建原始 RTP URL
                        original_url = f'rtp://{rtp_part}'
                        self.logger.info(f"从 FCC URL 提取原始地址：{original_url}")
                        return original_url
            except Exception as e:
                self.logger.debug(f"提取原始 URL 失败：{str(e)}")
        return url
    
    def _setup_protocol_options(self, url):
        if not self.mpv_handle or not url:
            return
        u = url.lower()
        settings = self._playback_settings

        is_vod = ('playseek' in u or 'starttime=' in u or 'endtime=' in u or
                  'catchup' in u or 'timeshift' in u or 'playback' in u)

        if u.startswith('rtsp://'):
            rtsp_transport = settings.get('rtsp_transport', 'tcp')
            self._set_mpv_string('rtsp-transport', rtsp_transport)
            rtsp_ua = settings.get('rtsp_user_agent', 'VLC/3.0.18Libmpv')
            self._set_mpv_string('user-agent', rtsp_ua)
            cache_secs = settings.get('cache_secs', 1.0)
            self._set_mpv_string('cache', 'yes' if cache_secs > 0 else 'no')
            if cache_secs > 0:
                self._set_mpv_string('cache-secs', str(cache_secs))
            self._set_mpv_string('demuxer-lavf-format', '')
            if is_vod:
                self._set_mpv_string('demuxer-lavf-probesize', '5000000')
                self._set_mpv_string('demuxer-lavf-analyzeduration', '5000000')
                self._set_mpv_string('force-seekable', 'yes')
                self.logger.debug(f"[mpv] rtsp-vod cache={cache_secs} transport={rtsp_transport}")
            else:
                self._set_mpv_string('demuxer-lavf-probesize', '32')
                self._set_mpv_string('demuxer-lavf-analyzeduration', '0')
                self.logger.debug(f"[mpv] rtsp-live cache={cache_secs} transport={rtsp_transport}")
            return

        looks_ts = ('/rtp/' in u or u.endswith('.ts') or 'proto=http' in u or u.startswith('udp://'))
        if looks_ts:
            self._set_mpv_string('demuxer', 'lavf')
            self._set_mpv_string('demuxer-lavf-format', 'mpegts')
            if is_vod:
                self._set_mpv_string('demuxer-lavf-probesize', '5000000')
                self._set_mpv_string('demuxer-lavf-analyzeduration', '5000000')
                self._set_mpv_string('force-seekable', 'yes')
            else:
                self._set_mpv_string('demuxer-lavf-probesize', '32')
                self._set_mpv_string('demuxer-lavf-analyzeduration', '0')
            self._set_mpv_string('demuxer-lavf-buffersize', '128000')

            if u.startswith('udp://'):
                self._set_mpv_string('cache', 'yes')
                cache_secs = settings.get('cache_secs', 10)
                self._set_mpv_string('cache-secs', str(max(1, cache_secs)))
                self._set_mpv_string('demuxer-max-back-bytes', '128MiB')
                self.logger.debug(f"[mpv] udp-ts demux=mpegts cache=yes max-back=128MiB")
            else:
                cache_secs = settings.get('cache_secs', 1.0)
                self._set_mpv_string('cache', 'yes' if cache_secs > 0 else 'no')
                if cache_secs > 0:
                    self._set_mpv_string('cache-secs', str(cache_secs))
                max_mib = settings.get('demuxer_max_bytes_mib', 16)
                back_mib = settings.get('demuxer_max_back_bytes_mib', 512)
                self._set_mpv_string('demuxer-max-bytes', f'{max_mib}MiB')
                self._set_mpv_string('demuxer-max-back-bytes', f'{back_mib}MiB')
                self.logger.debug(f"[mpv] http-ts demux=mpegts cache={cache_secs} back={back_mib}MiB")
            return

        if u.endswith('.m3u8') or 'format=hls' in u:
            self._set_mpv_string('demuxer-lavf-format', '')
            self._set_mpv_string('cache', 'yes')
            self._set_mpv_string('demuxer-max-bytes', '512MiB')
            self._set_mpv_string('demuxer-max-back-bytes', '256MiB')
            self._set_mpv_string('force-seekable', 'yes')
            self._set_mpv_string('demuxer-readahead-secs', '60')

            if settings.get('hls_start_at_live_edge', False):
                self._set_mpv_string('hls-playlist-start', 'no')
            readahead = settings.get('hls_readahead_secs', 0)
            if readahead > 0:
                self._set_mpv_string('demuxer-readahead-secs', str(readahead))
            self.logger.debug(f"[mpv] hls cache=yes seekable=yes")
            return

        self._set_mpv_string('demuxer-lavf-format', '')
        self._set_mpv_string('cache', 'yes')
        self._set_mpv_string('demuxer-max-bytes', '512MiB')
        self._set_mpv_string('demuxer-max-back-bytes', '256MiB')
        self._set_mpv_string('force-seekable', 'yes')
        self._set_mpv_string('demuxer-readahead-secs', '60')
        self._set_mpv_string('demuxer-cache-wait', 'no')
        self.logger.debug(f"[mpv] generic http cache=yes seekable=yes")

        if (u.startswith('http://') or u.startswith('https://')):
            headers = settings.get('http_headers', '')
            if headers:
                header_val = headers.replace('\r\n', '\n').replace('\n', '\\n')
                self._set_mpv_string('http-header-fields', header_val)
                self.logger.debug(f"[mpv] http-headers set")

            ua = settings.get('user_agent', DEFAULT_USER_AGENT)
            if ua:
                self._set_mpv_string('user-agent', ua)

    def _process_events(self):
        """处理 MPV 事件"""
        if not self.mpv_handle:
            return
        try:
            # 等待事件（非阻塞）
            event_ptr = libmpv.mpv_wait_event(self.mpv_handle, 0.0)
            if not event_ptr:
                return
            
            # 将指针转换为事件结构
            event = ctypes.cast(event_ptr, ctypes.POINTER(mpv_event)).contents
            
            # 检查事件类型
            if event.event_id == MPV_EVENT_NONE:
                return
            
            # 处理属性变化事件
            if event.event_id == MPV_EVENT_PROPERTY_CHANGE:
                self.logger.debug(f"收到属性变化事件，userdata={event.reply_userdata}")
                # 可以从 event.data 读取属性值，但需要使用 mpv_get_property 获取
                # 这里我们只是触发一次媒体信息获取
                if hasattr(self, '_live_info_timer') and self._live_info_timer:
                    # 属性变化时立即获取一次信息
                    info = self.get_live_media_info()
                    if info:
                        try:
                            self.live_media_info_updated.emit(info)
                        except RuntimeError:
                            pass
            
            # 处理文件加载完成事件
            elif event.event_id == MPV_EVENT_FILE_LOADED:
                self.logger.info("文件加载完成事件")
                # 文件加载完成后，延迟开始获取媒体信息
                if hasattr(self, '_media_info_timer'):
                    self._media_info_timer.stop()
                self._media_info_timer = QTimer(self)
                self._media_info_timer.singleShot(1000, self._start_live_info_timer)
                
        except Exception as e:
            self.logger.error(f"处理 mpv 事件失败：{str(e)}")

    def play(self, url, channel_name=None, **kwargs):
        try:
            self.current_url = url

            if not self.mpv_handle:
                self.logger.error("mpv播放器未初始化")
                self.play_error.emit("mpv播放器未初始化")
                return False

            try:
                if self.mpv_handle:
                    cmd_stop = [b'stop', None]
                    cmd_ptr_stop = (ctypes.c_char_p * len(cmd_stop))(*cmd_stop)
                    libmpv.mpv_command(self.mpv_handle, cmd_ptr_stop)
                    time.sleep(0.05)
                    cmd_clear = [b'playlist-clear', None]
                    cmd_ptr_clear = (ctypes.c_char_p * len(cmd_clear))(*cmd_clear)
                    libmpv.mpv_command(self.mpv_handle, cmd_ptr_clear)
            except:
                pass

            if hasattr(self, '_media_info_timer') and self._media_info_timer:
                self._media_info_timer.stop()

            self._setup_protocol_options(url)

            cmd = [b'loadfile', url.encode('utf-8'), None]
            cmd_ptr = (ctypes.c_char_p * len(cmd))(*cmd)
            result = libmpv.mpv_command(self.mpv_handle, cmd_ptr)

            if result < 0:
                error_msg = f"播放失败: {result}"
                self.logger.error(error_msg)
                self.play_error.emit(error_msg)
                return False

            libmpv.mpv_set_property_string(self.mpv_handle, b'pause', b'no')

            if self._current_speed != 1.0:
                self._set_mpv_string('speed', str(self._current_speed))

            self.is_paused = False
            self.is_playing = True
            self.play_state_changed.emit(True)

            self._get_media_info(url)

            self.logger.info(f"开始播放: {url}")
            return True
        except Exception as e:
            error_msg = f"播放失败: {str(e)}"
            self.logger.error(error_msg)
            self.play_error.emit(error_msg)
            return False

    def play_with_prefetch(self, url, next_urls=None):
        try:
            self.current_url = url

            if not self.mpv_handle:
                self.play_error.emit("mpv播放器未初始化")
                return False

            try:
                if self.mpv_handle:
                    cmd_stop = [b'stop', None]
                    cmd_ptr_stop = (ctypes.c_char_p * len(cmd_stop))(*cmd_stop)
                    libmpv.mpv_command(self.mpv_handle, cmd_ptr_stop)
            except:
                pass

            self._setup_protocol_options(url)
            self._set_mpv_string('prefetch-playlist', 'yes')

            cmd_clear = [b'playlist-clear', None]
            cmd_ptr_clear = (ctypes.c_char_p * len(cmd_clear))(*cmd_clear)
            libmpv.mpv_command(self.mpv_handle, cmd_ptr_clear)

            cmd = [b'loadfile', url.encode('utf-8'), None]
            cmd_ptr = (ctypes.c_char_p * len(cmd))(*cmd)
            libmpv.mpv_command(self.mpv_handle, cmd_ptr)

            if next_urls:
                prefetch_count = self._playback_settings.get('fcc_prefetch_count', 2)
                for i, next_url in enumerate(next_urls[:prefetch_count]):
                    if not next_url or not next_url.strip():
                        continue
                    cmd_next = [b'loadfile', next_url.encode('utf-8'), b'append-play', None]
                    cmd_ptr_next = (ctypes.c_char_p * len(cmd_next))(*cmd_next)
                    libmpv.mpv_command(self.mpv_handle, cmd_ptr_next)

            libmpv.mpv_set_property_string(self.mpv_handle, b'pause', b'no')
            if self._current_speed != 1.0:
                self._set_mpv_string('speed', str(self._current_speed))

            self.is_paused = False
            self.is_playing = True
            self.play_state_changed.emit(True)
            self._get_media_info(url)

            self.logger.info(f"开始播放(预取模式): {url}")
            return True
        except Exception as e:
            self.logger.error(f"预取播放失败: {str(e)}")
            return self.play(url)

    def stop(self):
        try:
            # 记录是否真正在播放，用于决定是否记录日志
            was_playing = self.is_playing or self.current_url

            if self.mpv_handle:
                cmd = [b'stop', None]
                cmd_ptr = (ctypes.c_char_p * len(cmd))(*cmd)
                libmpv.mpv_command(self.mpv_handle, cmd_ptr)

            if hasattr(self, '_media_info_timer') and self._media_info_timer:
                self._media_info_timer.stop()
            if hasattr(self, '_live_info_timer') and self._live_info_timer:
                self._live_info_timer.stop()

            self.is_playing = False
            self.is_paused = False
            self.play_state_changed.emit(False)
            self.current_url = None
            self.media_info = {}

            if hasattr(self, 'event_timer') and self.event_timer:
                self.event_timer.stop()

            # 只在之前有播放活动时才记录日志，避免关闭程序时的无效日志
            if was_playing:
                self.logger.info("停止播放")
        except Exception as e:
            self.logger.error(f"停止播放失败: {str(e)}")

    def pause(self):
        try:
            if self.mpv_handle:
                cmd = [b'cycle', b'pause', None]
                cmd_ptr = (ctypes.c_char_p * len(cmd))(*cmd)
                result = libmpv.mpv_command(self.mpv_handle, cmd_ptr)
                if result < 0:
                    self.logger.error(f"切换暂停状态失败: {result}")
                else:
                    was_paused = self.is_paused
                    self.is_paused = not self.is_paused
                    self.is_playing = not self.is_paused
                    
                    if self.is_paused:
                        # 暂停：mpv会保持连接并继续缓冲数据
                        self.logger.info("播放已暂停（继续缓冲中）")
                    else:
                        # 恢复播放
                        self.logger.info("恢复播放")
                    
                    self.play_state_changed.emit(self.is_playing)
        except Exception as e:
            self.logger.error(f"暂停播放失败: {str(e)}")

    def toggle_pause(self):
        self.pause()

    def set_volume(self, volume):
        try:
            self._last_volume = volume
            if self.mpv_handle:
                volume_str = f"{volume}".encode('utf-8')
                result = libmpv.mpv_set_property_string(self.mpv_handle, b'volume', volume_str)
                if result < 0:
                    self.logger.error(f"设置音量失败，错误码: {result}")
        except Exception as e:
            self.logger.error(f"设置音量失败: {str(e)}")

    def get_volume(self):
        try:
            if not hasattr(self, '_last_volume'):
                self._last_volume = 80
            volume_value = self._get_mpv_property_double('volume')
            if volume_value is not None:
                self._last_volume = int(volume_value)
            return self._last_volume
        except Exception:
            return getattr(self, '_last_volume', 80)

    def set_speed(self, speed):
        try:
            self._current_speed = speed
            if self.mpv_handle:
                self._set_mpv_string('speed', str(speed))
                self.logger.debug(f"设置播放速度: {speed}x")
        except Exception as e:
            self.logger.error(f"设置播放速度失败: {str(e)}")

    def get_speed(self):
        return self._current_speed

    def set_aspect_ratio(self, ratio):
        try:
            if not self.mpv_handle:
                return
            ratio_lower = ratio.lower() if ratio else 'default'
            if ratio_lower == '16:9':
                self._set_mpv_string('video-aspect-override', '16:9')
                self._set_mpv_string('keepaspect', 'yes')
                self._set_mpv_string('panscan', '0.0')
            elif ratio_lower == '4:3':
                self._set_mpv_string('video-aspect-override', '4:3')
                self._set_mpv_string('keepaspect', 'yes')
                self._set_mpv_string('panscan', '0.0')
            elif ratio_lower == 'stretch':
                self._set_mpv_string('video-aspect-override', '-1')
                self._set_mpv_string('keepaspect', 'no')
                self._set_mpv_string('panscan', '0.0')
            elif ratio_lower == 'fill':
                self._set_mpv_string('video-aspect-override', '-1')
                self._set_mpv_string('keepaspect', 'yes')
                self._set_mpv_string('panscan', '1.0')
            elif ratio_lower == 'crop':
                self._set_mpv_string('video-aspect-override', '-1')
                self._set_mpv_string('keepaspect', 'yes')
                self._set_mpv_string('panscan', '1.0')
            else:
                self._set_mpv_string('video-aspect-override', '-1')
                self._set_mpv_string('keepaspect', 'yes')
                self._set_mpv_string('panscan', '0.0')
            self.logger.debug(f"设置画面比例: {ratio}")
        except Exception as e:
            self.logger.error(f"设置画面比例失败: {str(e)}")

    def set_mute(self, muted):
        try:
            if self.mpv_handle:
                val = b'yes' if muted else b'no'
                libmpv.mpv_set_property_string(self.mpv_handle, b'mute', val)
        except Exception as e:
            self.logger.error(f"设置静音失败: {str(e)}")

    def get_mute(self):
        try:
            val = self._get_mpv_property_string('mute')
            return val == 'yes'
        except Exception:
            return False

    def get_current_time(self):
        try:
            # 首先尝试 time-pos
            time_seconds = self._get_mpv_property_double('time-pos')
            if time_seconds:
                result = int(time_seconds * 1000)
                self.logger.debug(f"get_current_time: time-pos={time_seconds}s = {result}ms")
                return result
            
            # 如果 time-pos 失败，尝试 playback-time
            time_seconds = self._get_mpv_property_double('playback-time')
            if time_seconds:
                result = int(time_seconds * 1000)
                self.logger.debug(f"get_current_time: playback-time={time_seconds}s = {result}ms")
                return result
            
            # 如果 playback-time 失败，尝试 percent-pos 并计算时间
            percent = self._get_mpv_property_double('percent-pos')
            if percent:
                # 获取总时长
                duration_seconds = self._get_mpv_property_double('duration')
                if duration_seconds:
                    time_seconds = duration_seconds * (percent / 100.0)
                    result = int(time_seconds * 1000)
                    self.logger.debug(f"get_current_time: percent-pos={percent}%, duration={duration_seconds}s = {result}ms")
                    return result
            
            self.logger.debug(f"get_current_time: 所有属性都返回None或0")
            return 0
        except Exception as e:
            self.logger.debug(f"get_current_time exception: {e}")
            return 0

    def get_total_time(self):
        try:
            # 首先尝试 duration
            duration_seconds = self._get_mpv_property_double('duration')
            if duration_seconds:
                result = int(duration_seconds * 1000)
                self.logger.debug(f"get_total_time: duration={duration_seconds}s = {result}ms")
                return result
            
            # 如果 duration 失败，尝试 length
            duration_seconds = self._get_mpv_property_double('length')
            if duration_seconds:
                result = int(duration_seconds * 1000)
                self.logger.debug(f"get_total_time: length={duration_seconds}s = {result}ms")
                return result
            
            # 如果 length 失败，尝试 file-size 并估计时长
            file_size = self._get_mpv_property_double('file-size')
            if file_size:
                # 粗略估计：1MB ≈ 1分钟（对于标准视频）
                # 这只是一个估计，不准确
                duration_seconds = file_size / (1024 * 1024) * 60  # MB * 60秒
                result = int(duration_seconds * 1000)
                self.logger.debug(f"get_total_time: file-size={file_size} bytes, estimated={duration_seconds}s = {result}ms")
                return result
            
            self.logger.debug(f"get_total_time: 所有属性都返回None或0")
            return 0
        except Exception as e:
            self.logger.debug(f"get_total_time exception: {e}")
            return 0

    def get_position(self):
        try:
            percent_pos = self._get_mpv_property_double('percent-pos')
            if percent_pos:
                return percent_pos / 100.0
            return 0
        except Exception:
            return 0

    def get_timeshift_range(self):
        """获取时移可用的时间范围（秒），返回 (earliest, latest)"""
        try:
            if not self.mpv_handle:
                return (0, 0)
            current = self._get_mpv_property_double('time-pos') or 0
            return (max(0, current - 900), current)
        except Exception:
            return (0, 0)

    def seek_absolute(self, target_seconds):
        """绝对位置 seek（秒），用于时移精确定位"""
        try:
            if self.mpv_handle and target_seconds >= 0:
                cmd = [b'seek', f'{target_seconds:.3f}'.encode('utf-8'), b'absolute', None]
                cmd_ptr = (ctypes.c_char_p * len(cmd))(*cmd)
                result = libmpv.mpv_command(self.mpv_handle, cmd_ptr)
                if result < 0:
                    self.logger.warning(f"绝对seek到{target_seconds:.1f}秒失败，错误码: {result}")
                else:
                    self.logger.info(f"绝对seek成功: {target_seconds:.1f}秒")
                return result
        except Exception as e:
            self.logger.error(f"绝对seek失败: {str(e)}")
        return -1

    def seek(self, position):
        try:
            if self.mpv_handle:
                duration_seconds = self._get_mpv_property_double('duration')
                if duration_seconds:
                    target_position = duration_seconds * position
                    cmd = [b'seek', f'{target_position}'.encode('utf-8'), b'absolute', None]
                    cmd_ptr = (ctypes.c_char_p * len(cmd))(*cmd)
                    result = libmpv.mpv_command(self.mpv_handle, cmd_ptr)
                    if result < 0:
                        seek_percent = position * 100.0
                        cmd = [b'seek', f'{seek_percent}'.encode('utf-8'), b'absolute-percent', None]
                        cmd_ptr = (ctypes.c_char_p * len(cmd))(*cmd)
                        libmpv.mpv_command(self.mpv_handle, cmd_ptr)
                else:
                    seek_percent = position * 100.0
                    cmd = [b'seek', f'{seek_percent}'.encode('utf-8'), b'absolute-percent', None]
                    cmd_ptr = (ctypes.c_char_p * len(cmd))(*cmd)
                    libmpv.mpv_command(self.mpv_handle, cmd_ptr)
        except Exception as e:
            self.logger.error(f"设置播放位置失败: {str(e)}")

    def seek_relative_seconds(self, seconds):
        """按秒数相对 seek（正数前进，负数后退），用于时移功能"""
        try:
            if self.mpv_handle and seconds != 0:
                cmd = [b'seek', f'{seconds:.1f}'.encode('utf-8'), b'relative', None]
                cmd_ptr = (ctypes.c_char_p * len(cmd))(*cmd)
                result = libmpv.mpv_command(self.mpv_handle, cmd_ptr)
                if result < 0:
                    self.logger.warning(f"相对seek {seconds}秒失败，错误码: {result}")
                else:
                    self.logger.debug(f"相对seek: {seconds}秒")
        except Exception as e:
            self.logger.error(f"相对seek失败: {str(e)}")

    def get_live_media_info(self):
        """获取实时媒体信息 - 参考 SRCBOX，统一使用字符串获取方式"""
        if not self.mpv_handle:
            return None
        try:
            # 统一使用字符串获取，然后解析（参考 SRCBOX 的实现方式）
            def get_str(prop):
                return self._get_mpv_property_string(prop)
            
            def get_int(prop):
                # 直接获取整数值，不通过字符串转换
                val = self._get_mpv_property_int(prop)
                if val is not None:
                    return val
                # 回退到字符串方式
                s = get_str(prop)
                if s:
                    try:
                        return int(s)
                    except ValueError:
                        return 0
                return 0
            
            def get_double(prop):
                # 直接获取浮点数值，不通过字符串转换
                val = self._get_mpv_property_double(prop)
                if val is not None:
                    return val
                # 回退到字符串方式
                s = get_str(prop)
                if s:
                    try:
                        return float(s)
                    except ValueError:
                        return 0.0
                return 0.0
            
            # 视频信息
            w = get_int('width')
            h = get_int('height')
            fps = get_double('estimated-vf-fps')
            if fps == 0:
                fps = get_double('fps')
            
            hw = get_str('hwdec-current') or ''
            vcodec = get_str('video-codec') or ''
            acodec = get_str('audio-codec') or ''
            
            # 码率信息 - 使用 demuxer-bitrate 作为备选
            v_br = get_double('video-params/bitrate')
            if v_br == 0:
                v_br = get_double('demuxer-bitrate')
            a_br = get_double('audio-params/bitrate')
            
            # 容器格式
            container = get_str('file-format') or ''
            
            # 音频信息
            audio_channels = get_int('audio-params/channel-count')
            sample_rate = get_int('audio-params/samplerate')
            
            # 像素格式
            pix_fmt = get_str('video-params/pixelformat') or ''
            
            # 详细调试日志：只在值变化时输出
            if not hasattr(self, '_last_info_debug') or self._last_info_debug != (w, h, vcodec, acodec):
                self._last_info_debug = (w, h, vcodec, acodec)
                self.logger.debug(f"媒体信息：width={w}, height={h}, vcodec='{vcodec}', acodec='{acodec}', fps={fps}, container='{container}'")
            
            # 如果获取不到关键信息，尝试获取所有可能的属性
            if not vcodec and not acodec and w == 0:
                self.logger.debug("尝试获取备选属性...")
                # 尝试其他可能的属性名
                alt_vcodec = get_str('video-format') or get_str('hwdec') or ''
                alt_acodec = get_str('audio-format') or ''
                self.logger.debug(f"备选：video-format='{alt_vcodec}', audio-format='{alt_acodec}', hwdec='{get_str('hwdec')}'")
                
                # 对于直播流，尝试从 track-list 获取信息
                try:
                    track_list_ptr = libmpv.mpv_get_property_string(
                        self.mpv_handle,
                        b'track-list',
                        ctypes.byref(ctypes.c_char_p())
                    )
                    if track_list_ptr >= 0:
                        self.logger.debug(f"track-list 属性可用")
                except:
                    pass
                
                # 尝试获取 demuxer 信息
                demuxer = get_str('demuxer') or ''
                self.logger.info(f"demuxer: {demuxer}")
                
                # 尝试获取 stream-format 信息
                v_format = get_str('video-format') or ''
                a_format = get_str('audio-format') or ''
                self.logger.info(f"video-format: {v_format}, audio-format: {a_format}")
            
            info = {
                'width': w,
                'height': h,
                'fps': fps,
                'hwdec': hw,
                'video_codec': vcodec,
                'audio_codec': acodec,
                'container': container,
                'audio_channels': audio_channels,
                'sample_rate': sample_rate,
                'pixel_format': pix_fmt,
                'video_bitrate': v_br,
                'audio_bitrate': a_br,
            }
            return info
        except Exception as e:
            self.logger.error(f"获取媒体信息失败：{str(e)}")
            return None

    def _start_live_info_timer(self):
        if hasattr(self, '_live_info_timer') and self._live_info_timer:
            self._live_info_timer.stop()
        self._live_info_timer = QTimer(self)
        self._live_info_timer.timeout.connect(self._update_live_info)
        self._live_info_timer.start(500)

    def _stop_live_info_timer(self):
        if hasattr(self, '_live_info_timer') and self._live_info_timer:
            self._live_info_timer.stop()

    def _update_live_info(self):
        """持续更新媒体信息 - 参考 SRCBOX"""
        if not self.mpv_handle:
            return
        info = self.get_live_media_info()
        if info:
            try:
                self.live_media_info_updated.emit(info)
            except RuntimeError as e:
                self.logger.error(f"_update_live_info: 信号发送失败 {str(e)}")
                self._stop_live_info_timer()

    def _get_media_info(self, url):
        """获取媒体信息 - 参考 SRCBOX，简单轮询方式"""
        # 停止之前的定时器
        if hasattr(self, '_live_info_timer') and self._live_info_timer:
            self._live_info_timer.stop()
        
        # 参考 SRCBOX：延迟 1 秒后就开始持续更新
        # SRCBOX 不会等待很长时间，而是立即开始轮询
        self._media_info_timer = QTimer(self)
        self._media_info_timer.singleShot(1000, self._start_live_info_timer)

    def _get_media_info_once(self):
        """一次性获取媒体信息，不重试"""
        if not self.mpv_handle:
            return
        try:
            info = self.get_live_media_info()
            if info and (info.get('width', 0) > 0 or info.get('video_codec') or info.get('audio_codec')):
                # 成功获取到有效信息
                v_br = info.get('video_bitrate', 0)
                a_br = info.get('audio_bitrate', 0)
                media_info = {
                    'format': info.get('container', '') or self._get_mpv_property_string('file-format') or '未知',
                    'duration': self.get_total_time(),
                    'protocol': self._guess_protocol(self.current_url or ''),
                    'video': {
                        'codec': info.get('video_codec', '未知'),
                        'width': info.get('width', 0),
                        'height': info.get('height', 0),
                        'frame_rate': info.get('fps', 0),
                        'bit_rate': int(v_br) if v_br else 0,
                        'pixel_format': info.get('pixel_format', ''),
                    },
                    'audio': {
                        'codec': info.get('audio_codec', '未知'),
                        'channels': info.get('audio_channels', 0),
                        'sample_rate': info.get('sample_rate', 0),
                        'bit_rate': int(a_br) if a_br else 0,
                    },
                    'tags': info.get('tags', []),
                    'info_text': info.get('info_text', ''),
                    'hwdec': info.get('hwdec', ''),
                }
                self.media_info = media_info
                self.media_info_ready.emit(media_info)
            else:
                # 未获取到有效信息，发送默认值
                default_media_info = {
                    'format': self._get_mpv_property_string('file-format') or '未知',
                    'duration': 0,
                    'protocol': self._guess_protocol(self.current_url or ''),
                    'video': {'codec': '未知', 'width': 0, 'height': 0, 'frame_rate': 0, 'bit_rate': 0, 'pixel_format': ''},
                    'audio': {'codec': '未知', 'channels': 0, 'sample_rate': 0, 'bit_rate': 0},
                }
                self.media_info = default_media_info
                self.media_info_ready.emit(default_media_info)
        except Exception as e:
            try:
                self.logger.error(f"获取媒体信息失败：{str(e)}")
                default_media_info = {
                    'format': '未知', 'duration': 0, 'protocol': '未知',
                    'video': {'codec': '未知', 'width': 0, 'height': 0, 'frame_rate': 0, 'bit_rate': 0, 'pixel_format': ''},
                    'audio': {'codec': '未知', 'channels': 0, 'sample_rate': 0, 'bit_rate': 0},
                }
                if hasattr(self, 'media_info_ready'):
                    self.media_info_ready.emit(default_media_info)
            except (RuntimeError, Exception):
                pass

    def _try_get_media_info(self):
        if not self.mpv_handle:
            return
        try:
            info = self.get_live_media_info()
            if info and (info.get('width', 0) > 0 or info.get('video_codec') or info.get('audio_codec')):
                v_br = info.get('video_bitrate', 0)
                a_br = info.get('audio_bitrate', 0)
                media_info = {
                    'format': info.get('container', '') or self._get_mpv_property_string('file-format') or '未知',
                    'duration': self.get_total_time(),
                    'protocol': self._guess_protocol(self.current_url or ''),
                    'video': {
                        'codec': info.get('video_codec', '未知'),
                        'width': info.get('width', 0),
                        'height': info.get('height', 0),
                        'frame_rate': info.get('fps', 0),
                        'bit_rate': int(v_br) if v_br else 0,
                        'pixel_format': info.get('pixel_format', ''),
                    },
                    'audio': {
                        'codec': info.get('audio_codec', '未知'),
                        'channels': info.get('audio_channels', 0),
                        'sample_rate': info.get('sample_rate', 0),
                        'bit_rate': int(a_br) if a_br else 0,
                    },
                    'tags': info.get('tags', []),
                    'info_text': info.get('info_text', ''),
                    'hwdec': info.get('hwdec', ''),
                }
                self.media_info = media_info
                self.media_info_ready.emit(media_info)
                return

            if not hasattr(self, '_media_info_retry_count'):
                self._media_info_retry_count = 0
            self._media_info_retry_count += 1
            if self._media_info_retry_count <= 3:
                QTimer.singleShot(1500, self._try_get_media_info)
            else:
                self._media_info_retry_count = 0
                default_media_info = {
                    'format': self._get_mpv_property_string('file-format') or '未知',
                    'duration': 0,
                    'protocol': self._guess_protocol(self.current_url or ''),
                    'video': {'codec': '未知', 'width': 0, 'height': 0, 'frame_rate': 0, 'bit_rate': 0, 'pixel_format': ''},
                    'audio': {'codec': '未知', 'channels': 0, 'sample_rate': 0, 'bit_rate': 0},
                }
                self.media_info = default_media_info
                self.media_info_ready.emit(default_media_info)

        except Exception as e:
            try:
                self.logger.error(f"获取媒体信息失败: {str(e)}")
                default_media_info = {
                    'format': '未知', 'duration': 0, 'protocol': '未知',
                    'video': {'codec': '未知', 'width': 0, 'height': 0, 'frame_rate': 0, 'bit_rate': 0, 'pixel_format': ''},
                    'audio': {'codec': '未知', 'channels': 0, 'sample_rate': 0, 'bit_rate': 0},
                }
                if hasattr(self, 'media_info_ready'):
                    self.media_info_ready.emit(default_media_info)
            except (RuntimeError, Exception):
                pass

    @staticmethod
    def _guess_protocol(url):
        if not url:
            return '未知'
        u = url.lower()
        if '.m3u8' in u or u.startswith('hls+'):
            return 'HLS'
        if '.mpd' in u or u.startswith('dash+'):
            return 'DASH'
        if u.startswith('rtsp://'):
            return 'RTSP'
        if u.startswith('rtp://') or u.startswith('udp://'):
            return 'RTP/UDP'
        if u.startswith('srt://'):
            return 'SRT'
        if u.startswith('http://') or u.startswith('https://'):
            return 'HTTP'
        if u.startswith('file://') or ('://' not in url):
            return 'FILE'
        return '未知'

    def _get_mpv_property_string(self, property_name):
        """获取 MPV 属性字符串 - 参考 SRCBOX，使用正确的 API 签名"""
        try:
            if not self.mpv_handle:
                return None
            # 正确的调用方式：mpv_get_property_string(handle, name) 返回 char*
            result = libmpv.mpv_get_property_string(
                self.mpv_handle,
                property_name.encode('utf-8')
            )
            
            # 参考 SRCBOX：只检查指针是否为空，不检查返回值
            if not result:
                return None
            property_value = result.decode('utf-8')
            # mpv_get_property_string 返回的字符串由 MPV 内部管理，不需要手动释放
            return property_value
        except Exception as e:
            self.logger.debug(f"_get_mpv_property_string('{property_name}'): 异常 {str(e)}")
            return None

    def _get_mpv_error_string(self, error_code):
        try:
            if hasattr(libmpv, 'mpv_error_string'):
                error_str = libmpv.mpv_error_string(error_code)
                if error_str:
                    return error_str.decode('utf-8')
        except:
            pass
        return f"错误码: {error_code}"

    def _get_mpv_property_int(self, property_name):
        try:
            if not self.mpv_handle:
                return None
            value = ctypes.c_int64()
            result = libmpv.mpv_get_property(
                self.mpv_handle,
                property_name.encode('utf-8'),
                MPV_FORMAT_INT64,
                ctypes.byref(value)
            )
            if result < 0:
                return None
            return value.value
        except:
            return None

    def _get_mpv_property_double(self, property_name):
        try:
            if not self.mpv_handle:
                return None
            value = ctypes.c_double()
            result = libmpv.mpv_get_property(
                self.mpv_handle,
                property_name.encode('utf-8'),
                MPV_FORMAT_DOUBLE,
                ctypes.byref(value)
            )
            if result < 0:
                return None
            return value.value
        except:
            return None

    def get_video_resolution(self):
        try:
            width = self._get_mpv_property_int('width')
            height = self._get_mpv_property_int('height')
            if width and height and width > 0 and height > 0:
                return f"{width}x{height}"
            return None
        except Exception:
            return None

    def ensure_ready_for_load(self):
        try:
            if not self.mpv_handle:
                return
            libmpv.mpv_set_property_string(self.mpv_handle, b'pause', b'no')
            eof = self._get_mpv_property_string('eof-reached')
            if eof and eof.lower() == 'yes':
                cmd = [b'stop', None]
                cmd_ptr = (ctypes.c_char_p * len(cmd))(*cmd)
                libmpv.mpv_command(self.mpv_handle, cmd_ptr)
                time.sleep(0.08)
        except Exception:
            pass

    def is_eof_reached(self):
        try:
            eof = self._get_mpv_property_string('eof-reached')
            return eof and eof.lower() == 'yes'
        except Exception:
            return False

    def get_property_string(self, name):
        return self._get_mpv_property_string(name)

    def get_property_double(self, name):
        return self._get_mpv_property_double(name)

    def get_property_int(self, name):
        return self._get_mpv_property_int(name)

    def set_property_string(self, name, value):
        self._set_mpv_string(name, value)

    @pyqtSlot(dict)
    def _on_media_info_thread_finished(self, info):
        if info:
            self.media_info_ready.emit(info)

    @pyqtSlot(str)
    def _on_media_info_thread_error(self, error):
        self.logger.error(f"获取媒体信息失败: {error}")
