import os
import time
import ctypes
import threading
from PyQt6.QtCore import QObject, pyqtSignal, QTimer
from core.log_manager import global_logger
from services.mpv_common import (
    mpv_event,
    mpv_event_end_file,
    MPV_EVENT_NONE,
    MPV_EVENT_SHUTDOWN,
    MPV_EVENT_START_FILE,
    MPV_EVENT_END_FILE,
    MPV_EVENT_FILE_LOADED,
    MPV_EVENT_PROPERTY_CHANGE,
    MPV_FORMAT_STRING,
    MPV_FORMAT_INT64,
    MPV_FORMAT_DOUBLE,
    MPV_END_FILE_REASON_EOF,
    get_property_string as _mpv_get_property_string,
    get_property_int as _mpv_get_property_int,
    get_property_double as _mpv_get_property_double,
    create_mpv_handle,
    initialize_mpv,
    destroy_mpv,
    terminate_destroy_mpv,
    set_property_string as _mpv_set_property_string,
    set_property_int64 as _mpv_set_property_int64,
    send_command as _mpv_send_command,
    observe_property as _mpv_observe_property,
    wait_for_event as _mpv_wait_event,
)

try:
    import mpv
except Exception:
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
        'demuxer_max_back_bytes_mib': 4,
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
        'audio_passthrough': 'never',
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

    play_state_changed = pyqtSignal(bool)
    play_error = pyqtSignal(str)
    reconnect_requested = pyqtSignal(str)
    live_media_info_updated = pyqtSignal(dict)
    playback_position_updated = pyqtSignal(float, float, float)
    logo_cache_loaded = pyqtSignal(str, object)
    thumbnail_captured = pyqtSignal(str)

    def __init__(self, video_widget, channel_model=None):
        super().__init__()
        self.logger = global_logger
        self._lock = threading.RLock()
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
        self._last_volume = 80
        self._reconnect_count = 0
        self._max_reconnect = 3
        self._user_stopped = False
        self._switching_channel = False
        self._mpv_initialized = False

    def _ensure_mpv_initialized(self):
        if self._mpv_initialized:
            return True
        self._mpv_initialized = True

        try:
            import services.mpv_common as _mpv_mod
            if not _mpv_mod._ensure_libmpv_loaded():
                error_msg = "libmpv-2.dll加载失败"
                self.logger.error(error_msg)
                self.play_error.emit(error_msg)
                return False

            if not _mpv_mod.MPV_AVAILABLE or _mpv_mod.libmpv is None:
                error_msg = "libmpv-2.dll加载失败"
                self.logger.error(error_msg)
                self.play_error.emit(error_msg)
                return False

            self.mpv_handle = create_mpv_handle()
            if not self.mpv_handle:
                error_msg = "创建mpv实例失败"
                self.logger.error(error_msg)
                self.play_error.emit(error_msg)
                return False

            window_id = self.video_widget.winId()
            if hasattr(window_id, 'value'):
                window_id = window_id.value

            try:
                window_id_int = int(window_id)
                _mpv_set_property_string(self.mpv_handle, 'wid', f"{window_id_int}")
            except Exception as e:
                self.logger.error(f"设置窗口ID失败: {str(e)}")

            _mpv_set_property_string(self.mpv_handle, 'vo', 'gpu')
            hwdec = 'auto' if self._playback_settings.get('hwdec', True) else 'no'
            _mpv_set_property_string(self.mpv_handle, 'hwdec', hwdec)
            _mpv_set_property_string(self.mpv_handle, 'gpu-api', 'd3d11')
            _mpv_set_property_string(self.mpv_handle, 'd3d11-sync-interval', '1')
            _mpv_set_property_string(self.mpv_handle, 'osc', 'no')
            _mpv_set_property_string(self.mpv_handle, 'osd-bar', 'no')

            _mpv_set_property_string(self.mpv_handle, 'osd-font-size', '18')
            _mpv_set_property_string(self.mpv_handle, 'osd-border-size', '2')
            _mpv_set_property_string(self.mpv_handle, 'osd-shadow-offset', '1.5')
            _mpv_set_property_string(self.mpv_handle, 'osd-spacing', '0.5')
            _mpv_set_property_string(self.mpv_handle, 'osd-margin-x', '24')
            _mpv_set_property_string(self.mpv_handle, 'osd-margin-y', '24')
            _mpv_set_property_string(self.mpv_handle, 'osd-align-x', 'left')
            _mpv_set_property_string(self.mpv_handle, 'osd-align-y', 'top')
            self._apply_osd_colors()
            _mpv_set_property_string(self.mpv_handle, 'log-level', 'fatal')
            _mpv_set_property_string(self.mpv_handle, 'no-window-dragging', 'yes')
            _mpv_set_property_string(self.mpv_handle, 'window-scale', '1.0')
            _mpv_set_property_string(self.mpv_handle, 'border', 'no')

            _mpv_set_property_string(self.mpv_handle, 'keep-open', 'yes')
            _mpv_set_property_string(self.mpv_handle, 'idle', 'yes')
            _mpv_set_property_string(self.mpv_handle, 'ytdl', 'no')

            _mpv_set_property_string(self.mpv_handle, 'video-aspect-override', '-1')
            _mpv_set_property_string(self.mpv_handle, 'keepaspect', 'yes')
            _mpv_set_property_string(self.mpv_handle, 'panscan', '0.0')

            _mpv_set_property_string(self.mpv_handle, 'tone-mapping', 'hable')
            _mpv_set_property_string(self.mpv_handle, 'tone-mapping-mode', 'auto')
            _mpv_set_property_string(self.mpv_handle, 'hdr-compute-peak', 'yes')

            ua = self._playback_settings.get('user_agent', DEFAULT_USER_AGENT)
            if ua:
                _mpv_set_property_string(self.mpv_handle, 'user-agent', ua)

            if not self._playback_settings.get('tls_verify', True):
                _mpv_set_property_string(self.mpv_handle, 'tls-verify', 'no')

            _mpv_set_property_string(self.mpv_handle, 'mute', 'no')
            _mpv_set_property_string(self.mpv_handle, 'audio', 'yes')
            _mpv_set_property_string(self.mpv_handle, 'audio-device', 'auto')

            net_to = self._playback_settings.get('network_timeout_sec', 0)
            if net_to > 0:
                _mpv_set_property_string(self.mpv_handle, 'network-timeout', str(net_to))

            passthrough = self._playback_settings.get('audio_passthrough', 'never')
            if passthrough and passthrough != 'never':
                passthrough_map = {
                    'all': 'yes',
                    'hd_codecs': 'ac3,eac3,dts,dts-hd,truehd',
                    'lossless': 'flac,alac,truehd,dts-hd',
                    'spdif_only': 'ac3,eac3,dts',
                }
                pt_val = passthrough_map.get(passthrough, '')
                if pt_val:
                    _mpv_set_property_string(self.mpv_handle, 'audio-spdif', pt_val)
                    _mpv_set_property_string(self.mpv_handle, 'audio-passthrough', pt_val)
                    self.logger.info(f"音频直通已启用: {passthrough} -> {pt_val}")

            cpu_count = os.cpu_count() or 1
            threads = max(2, cpu_count // 2)
            _mpv_set_property_string(self.mpv_handle, 'vd-lavc-threads', str(threads))

            if not initialize_mpv(self.mpv_handle):
                error_msg = "初始化mpv失败"
                self.logger.error(error_msg)
                self.play_error.emit(error_msg)
                destroy_mpv(self.mpv_handle)
                self.mpv_handle = None
                return False

            try:
                _mpv_observe_property(self.mpv_handle, 1, 'pause', MPV_FORMAT_STRING)
            except Exception as e:
                self.logger.warning(f"订阅pause属性失败: {str(e)}")

            self.logger.info("mpv播放器初始化成功")

            self.event_timer = QTimer(self)
            self.event_timer.timeout.connect(self._process_events)
            self.event_timer.start(100)

            return True

        except Exception as e:
            error_msg = f"初始化mpv播放器失败: {str(e)}"
            self.logger.error(error_msg)
            self.play_error.emit(error_msg)
            if self.mpv_handle:
                destroy_mpv(self.mpv_handle)
                self.mpv_handle = None
            return False

    def _set_mpv_string(self, name, value):
        return _mpv_set_property_string(self.mpv_handle, name, str(value))

    def _extract_original_url(self, url):
        if '/rtp/' in url and 'fcc=' in url:
            try:
                from urllib.parse import urlparse, parse_qs
                parsed = urlparse(url)
                query = parse_qs(parsed.query)
                if 'fcc' in query:
                    fcc_server = query['fcc'][0]
                    path_parts = parsed.path.split('/rtp/')
                    if len(path_parts) > 1:
                        rtp_part = path_parts[1]
                        original_url = f'rtp://{rtp_part}'
                        self.logger.info(f"从 FCC URL 提取原始地址：{original_url}")
                        return original_url
            except Exception as e:
                self.logger.debug(f"提取原始 URL 失败：{str(e)}")
        return url

    @staticmethod
    def _is_network_drive(path):
        if os.name != 'nt':
            path_lower = path.lower()
            return path_lower.startswith('//') or path_lower.startswith('\\\\')
        try:
            path_lower = path.lower()
            if path_lower.startswith('//') or path_lower.startswith('\\\\'):
                return True
            drive = os.path.splitdrive(path)[0]
            if not drive or len(drive) != 2 or drive[1] != ':':
                return False
            kernel32 = ctypes.windll.kernel32
            DRIVE_REMOTE = 4
            return kernel32.GetDriveTypeW(drive + '\\') == DRIVE_REMOTE
        except Exception:
            return False

    _reachability_result = pyqtSignal(str, object)

    @staticmethod
    def _check_path_reachability_sync(url):
        if not url:
            return None
        u = url.lower()
        if u.startswith('bd://'):
            return None
        is_http = u.startswith(('http://', 'https://'))
        if is_http:
            try:
                from urllib.parse import urlparse
                parsed = urlparse(url)
                host = parsed.hostname
                port = parsed.port
                if not host:
                    return None
                import socket
                if not port:
                    port = 443 if parsed.scheme == 'https' else 80
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(3)
                sock.connect((host, port))
                sock.close()
            except (socket.timeout, socket.error, OSError) as e:
                return f"网络不可达: {host}:{port} ({e})"
            except Exception:
                pass
            return None
        return None

    def _check_path_reachability(self, url):
        if not url or not url.lower().startswith(('http://', 'https://')):
            return None
        result = [None]
        event = threading.Event()

        def _worker():
            result[0] = self._check_path_reachability_sync(url)
            event.set()

        t = threading.Thread(target=_worker, daemon=True)
        t.start()
        if not event.wait(timeout=3.5):
            return None
        return result[0]

    @staticmethod
    def _fix_unc_path(path):
        if not path:
            return path
        if path.startswith('//'):
            path = '\\\\' + path[2:]
            return path.replace('/', '\\')
        if path.startswith('\\\\'):
            return path.replace('/', '\\')
        if os.name == 'nt' and len(path) >= 2 and path[1] == ':':
            return path.replace('/', '\\')
        return path

    @staticmethod
    def _detect_bdmv_path(path):
        if not path or not os.path.isdir(path):
            return None
        bdmv_dir = os.path.join(path, 'BDMV')
        if os.path.isdir(bdmv_dir):
            stream_dir = os.path.join(bdmv_dir, 'STREAM')
            if os.path.isdir(stream_dir):
                m2ts_files = [f for f in os.listdir(stream_dir) if f.lower().endswith('.m2ts')]
                if m2ts_files:
                    return bdmv_dir
        for item in os.listdir(path):
            sub = os.path.join(path, item)
            if os.path.isdir(sub):
                sub_bdmv = os.path.join(sub, 'BDMV')
                if os.path.isdir(sub_bdmv):
                    stream_dir = os.path.join(sub_bdmv, 'STREAM')
                    if os.path.isdir(stream_dir):
                        m2ts_files = [f for f in os.listdir(stream_dir) if f.lower().endswith('.m2ts')]
                        if m2ts_files:
                            return sub_bdmv
        return None

    def _normalize_url(self, url):
        if not url:
            return url
        u = url.lower()
        is_network = (u.startswith(('http://', 'https://', 'rtmp://', 'rtsp://', 'rtp://', 'udp://', 'file://')) or
                      u.endswith('.m3u8'))
        if is_network:
            return url
        if self._is_network_drive(url):
            fixed = self._fix_unc_path(url)
            bdmv = self._detect_bdmv_path(fixed)
            if bdmv:
                self.logger.info(f"检测到蓝光原盘结构: {bdmv}")
                return f'bd://{bdmv}'
            if fixed != url:
                self.logger.debug(f"网络路径格式修正: {url[:80]}... -> {fixed[:80]}...")
            return fixed
        bdmv = self._detect_bdmv_path(url)
        if bdmv:
            self.logger.info(f"检测到蓝光原盘结构: {bdmv}")
            return f'bd://{bdmv}'
        try:
            from pathlib import Path
            path = Path(url)
            if path.is_absolute():
                normalized = path.resolve().as_uri()
                if normalized != url:
                    self.logger.debug(f"本地文件路径已规范化: {url[:80]}... -> {normalized[:80]}...")
                return normalized
        except Exception as e:
            self.logger.debug(f"路径规范化失败，使用原始URL: {e}")
        return url

    def _reset_demuxer_options(self):
        try:
            self._set_mpv_string('demuxer', '')
            self._set_mpv_string('demuxer-lavf-format', '')
            self._set_mpv_string('demuxer-lavf-probesize', '5000000')
            self._set_mpv_string('demuxer-lavf-analyzeduration', '5000000')
            self._set_mpv_string('demuxer-lavf-buffersize', '')
            self._set_mpv_string('cache', 'no')
            self._set_mpv_string('cache-secs', '')
            self._set_mpv_string('demuxer-max-bytes', '')
            self._set_mpv_string('demuxer-max-back-bytes', '')
            self._set_mpv_string('demuxer-readahead-secs', '')
            self._set_mpv_string('force-seekable', '')
            self._set_mpv_string('demuxer-seekable-cache', 'no')
            self._set_mpv_string('demuxer-cache-wait', 'no')
            self._set_mpv_string('rtsp-transport', '')
            self.logger.debug("[mpv] 已重置demuxer/cache选项")
        except Exception as e:
            self.logger.debug(f"重置demuxer选项失败: {e}")

    def _adjust_buffer_for_content(self):
        try:
            if not self.mpv_handle:
                return
            url = self.current_url
            if not url:
                return
            u = url.lower()
            is_network = (u.startswith(('http://', 'https://', 'rtmp://', 'rtsp://', 'rtp://', 'udp://')) or
                          u.endswith('.m3u8'))
            is_net_drive = not is_network and self._is_network_drive(url)
            if not is_network and not is_net_drive:
                return
            w = self._get_mpv_property_int('width') or 0
            h = self._get_mpv_property_int('height') or 0
            duration = self._get_mpv_property_double('duration') or 0
            file_size = 0
            try:
                fs_str = self._get_mpv_property_string('file-size')
                if fs_str:
                    file_size = int(fs_str)
            except Exception:
                pass
            is_4k = (w >= 3840 or h >= 2160)
            is_hdr = False
            try:
                gamma = (self._get_mpv_property_string('video-params/gamma') or '').lower()
                sig_peak = self._get_mpv_property_double('video-params/sig-peak') or 0
                is_hdr = 'pq' in gamma or 'hlg' in gamma or sig_peak > 100
            except Exception:
                pass
            is_large_file = file_size > 10 * 1024 * 1024 * 1024 or (duration > 3600 and is_4k)
            if not is_4k and not is_hdr and not is_large_file:
                return
            cache_secs = 120
            max_bytes_mib = 1024
            probesize = 50000000
            analyzeduration = 10000000
            if is_4k and is_hdr:
                cache_secs = 180
                max_bytes_mib = 2048
                probesize = 100000000
                analyzeduration = 15000000
            elif is_4k:
                cache_secs = 150
                max_bytes_mib = 1536
                probesize = 80000000
                analyzeduration = 12000000
            if is_large_file:
                cache_secs = max(cache_secs, 240)
                max_bytes_mib = max(max_bytes_mib, 3072)
            self._set_mpv_string('cache-secs', str(cache_secs))
            self._set_mpv_string('demuxer-max-bytes', f'{max_bytes_mib}MiB')
            self._set_mpv_string('demuxer-max-back-bytes', f'{max_bytes_mib // 2}MiB')
            self._set_mpv_string('demuxer-lavf-probesize', str(probesize))
            self._set_mpv_string('demuxer-lavf-analyzeduration', str(analyzeduration))
            self.logger.info(f"动态缓冲调整: {w}x{h} HDR={is_hdr} large={is_large_file} -> cache={cache_secs}s max={max_bytes_mib}MiB probesize={probesize}")
        except Exception as e:
            self.logger.debug(f"动态缓冲调整失败: {e}")

    def _setup_bluray_options(self):
        try:
            self._set_mpv_string('demuxer', '')
            self._set_mpv_string('demuxer-lavf-format', '')
            self._set_mpv_string('demuxer-lavf-probesize', '100000000')
            self._set_mpv_string('demuxer-lavf-analyzeduration', '20000000')
            self._set_mpv_string('cache', 'yes')
            self._set_mpv_string('cache-secs', '180')
            self._set_mpv_string('demuxer-max-bytes', '2048MiB')
            self._set_mpv_string('demuxer-max-back-bytes', '1024MiB')
            self._set_mpv_string('demuxer-readahead-secs', '60')
            self._set_mpv_string('force-seekable', 'yes')
            self._set_mpv_string('demuxer-seekable-cache', 'yes')
            self.logger.debug("[mpv] 蓝光原盘选项已设置: cache=180s, probesize=100M, max=2048MiB")
        except Exception as e:
            self.logger.debug(f"设置蓝光原盘选项失败: {e}")

    def _setup_network_drive_options(self):
        try:
            self._set_mpv_string('demuxer', '')
            self._set_mpv_string('demuxer-lavf-format', '')
            self._set_mpv_string('demuxer-lavf-probesize', '50000000')
            self._set_mpv_string('demuxer-lavf-analyzeduration', '10000000')
            self._set_mpv_string('demuxer-lavf-buffersize', '50000000')
            self._set_mpv_string('cache', 'yes')
            self._set_mpv_string('cache-secs', '60')
            self._set_mpv_string('demuxer-max-bytes', '512MiB')
            self._set_mpv_string('demuxer-max-back-bytes', '256MiB')
            self._set_mpv_string('demuxer-readahead-secs', '30')
            self._set_mpv_string('force-seekable', 'yes')
            self._set_mpv_string('demuxer-seekable-cache', 'yes')
            self.logger.debug("[mpv] 网络挂载盘选项已设置: cache=yes, probesize=50M, readahead=30s")
        except Exception as e:
            self.logger.debug(f"设置网络挂载盘选项失败: {e}")

    def _setup_protocol_options(self, url, program_duration=0):
        if not self.mpv_handle or not url:
            return
        u = url.lower()

        is_network = (u.startswith(('http://', 'https://', 'rtmp://', 'rtsp://', 'rtp://', 'udp://')) or
                      u.endswith('.m3u8'))
        if u.startswith('bd://'):
            self._setup_bluray_options()
            return
        if not is_network:
            if self._is_network_drive(url):
                self._setup_network_drive_options()
                return
            self._reset_demuxer_options()
            return

        settings = self._playback_settings

        is_vod = ('playseek' in u or 'starttime=' in u or 'endtime=' in u or
                  'catchup' in u or 'timeshift' in u or 'playback' in u)

        cache_secs = max(program_duration, 3600) if program_duration > 0 else 3600
        cache_secs = min(cache_secs, 14400)
        max_bytes_mib = min(max(cache_secs * 2 // 60, 256), 4096)

        if u.startswith('rtsp://'):
            rtsp_transport = settings.get('rtsp_transport', 'tcp')
            self._set_mpv_string('rtsp-transport', rtsp_transport)
            rtsp_ua = settings.get('rtsp_user_agent', 'VLC/3.0.18Libmpv')
            self._set_mpv_string('user-agent', rtsp_ua)
            self._set_mpv_string('cache', 'yes')
            self._set_mpv_string('cache-secs', str(cache_secs))
            self._set_mpv_string('demuxer-lavf-format', '')
            if rtsp_transport == 'udp':
                self._set_mpv_string('demuxer-lavf-probesize', '500000')
                self._set_mpv_string('demuxer-lavf-analyzeduration', '500000')
                self._set_mpv_string('demuxer-max-bytes', f'{max_bytes_mib}MiB')
                self._set_mpv_string('demuxer-max-back-bytes', f'{max_bytes_mib}MiB')
                self._set_mpv_string('demuxer-readahead-secs', '5')
                self._set_mpv_string('force-seekable', 'no')
                self.logger.debug(f"[mpv] rtsp-udp-live cache={cache_secs} transport={rtsp_transport}")
            elif is_vod:
                self._set_mpv_string('demuxer-lavf-probesize', '5000000')
                self._set_mpv_string('demuxer-lavf-analyzeduration', '5000000')
                self._set_mpv_string('force-seekable', 'yes')
                self.logger.debug(f"[mpv] rtsp-vod cache={cache_secs} transport={rtsp_transport}")
            else:
                self._set_mpv_string('demuxer-lavf-probesize', '32')
                self._set_mpv_string('demuxer-lavf-analyzeduration', '0')
                self.logger.debug(f"[mpv] rtsp-tcp-live cache={cache_secs} transport={rtsp_transport}")
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
            self._set_mpv_string('cache', 'yes')
            self._set_mpv_string('force-seekable', 'yes')
            self._set_mpv_string('demuxer-seekable-cache', 'yes')
            self._set_mpv_string('cache-secs', str(cache_secs))
            self._set_mpv_string('demuxer-max-bytes', f'{max_bytes_mib}MiB')
            self._set_mpv_string('demuxer-max-back-bytes', f'{max_bytes_mib}MiB')
            self._set_mpv_string('demuxer-readahead-secs', '300')
            self.logger.debug(f"[mpv] ts demux=mpegts cache={cache_secs}s back={max_bytes_mib}MiB dur={program_duration}s")
            return

        if u.endswith('.m3u8') or 'format=hls' in u:
            self._set_mpv_string('demuxer-lavf-format', '')
            self._set_mpv_string('cache', 'yes')
            self._set_mpv_string('cache-secs', str(cache_secs))
            self._set_mpv_string('demuxer-max-bytes', f'{max_bytes_mib}MiB')
            self._set_mpv_string('demuxer-max-back-bytes', f'{max_bytes_mib}MiB')
            self._set_mpv_string('force-seekable', 'yes')
            self._set_mpv_string('demuxer-readahead-secs', '120')

            if settings.get('hls_start_at_live_edge', False):
                self._set_mpv_string('hls-playlist-start', 'no')
            readahead = settings.get('hls_readahead_secs', 0)
            if readahead > 0:
                self._set_mpv_string('demuxer-readahead-secs', str(readahead))
            self.logger.debug(f"[mpv] hls cache=yes seekable=yes vod={is_vod}")
            return

        self._set_mpv_string('demuxer-lavf-format', '')
        self._set_mpv_string('cache', 'yes')
        self._set_mpv_string('cache-secs', str(cache_secs))
        self._set_mpv_string('demuxer-max-bytes', f'{max_bytes_mib}MiB')
        self._set_mpv_string('demuxer-max-back-bytes', f'{max_bytes_mib}MiB')
        self._set_mpv_string('force-seekable', 'yes')
        self._set_mpv_string('demuxer-readahead-secs', '120')
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
        with self._lock:
            handle = self.mpv_handle
            if not handle:
                return
        try:
            while True:
                with self._lock:
                    current_handle = self.mpv_handle
                if current_handle is not handle:
                    return
                from services.mpv_common import libmpv as _libmpv
                with self._lock:
                    if self.mpv_handle is not handle:
                        return
                    event_ptr = _libmpv.mpv_wait_event(handle, 0.0)
                if not event_ptr:
                    return

                event = ctypes.cast(event_ptr, ctypes.POINTER(mpv_event)).contents

                if event.event_id == MPV_EVENT_NONE:
                    return

                if event.event_id == MPV_EVENT_PROPERTY_CHANGE:
                    pass

                elif event.event_id == MPV_EVENT_FILE_LOADED:
                    self._reconnect_count = 0
                    self._switching_channel = False
                    self._schedule_media_info_start()
                    self._adjust_buffer_for_content()

                elif event.event_id == MPV_EVENT_END_FILE:
                    if event.data:
                        end_file = ctypes.cast(event.data, ctypes.POINTER(mpv_event_end_file)).contents
                        reason = end_file.reason
                        if reason == 0:
                            pass
                        elif reason in (1, 2, 3, 4):
                            if self._switching_channel:
                                self.logger.debug("频道切换导致的END_FILE，忽略重连")
                                self._switching_channel = False
                            elif not self._user_stopped and self.current_url:
                                is_net_file = self._is_network_drive(self.current_url)
                                is_network_url = self.current_url.lower().startswith(
                                    ('http://', 'https://', 'rtsp://', 'rtp://', 'udp://', 'rtmp://'))
                                if reason == 4 and not is_net_file and not is_network_url:
                                    self.logger.debug(f"END_FILE错误(本地文件)，不重连: reason={reason}")
                                    self.is_playing = False
                                    self.is_paused = False
                                    self.play_state_changed.emit(False)
                                else:
                                    if reason == 4:
                                        err_str = self._get_mpv_error_string(end_file.error) if hasattr(end_file, 'error') else f"error_code={reason}"
                                        self.logger.warning(f"END_FILE错误，尝试重连: {err_str}, is_net_file={is_net_file}")
                                    self.is_playing = False
                                    self.is_paused = False
                                    self.play_state_changed.emit(False)
                                    if self._reconnect_count < self._max_reconnect:
                                        self._reconnect_count += 1
                                        self.logger.info(f"断线自动重连 ({self._reconnect_count}/{self._max_reconnect})")
                                        self.reconnect_requested.emit(self.current_url)
                                    else:
                                        self.logger.info("已达最大重连次数，停止重连")
                                        self._reconnect_count = 0

        except Exception as e:
            self.logger.error(f"处理 mpv 事件失败：{str(e)}")

    def play(self, url, channel_name=None, program_duration=0, **kwargs):
        try:
            if not self._ensure_mpv_initialized():
                self.logger.error("mpv播放器初始化失败，无法播放")
                self.play_error.emit("mpv播放器初始化失败")
                return False

            self.current_url = url
            self._user_stopped = False
            self._switching_channel = True

            reachability = self._check_path_reachability(url)
            if reachability is not None:
                self.logger.warning(f"路径不可达，取消播放: {reachability}")
                self.play_error.emit(reachability)
                return False

            if not self.mpv_handle:
                self.logger.error("mpv播放器未初始化")
                self.play_error.emit("mpv播放器未初始化")
                return False

            if hasattr(self, 'event_timer') and self.event_timer and not self.event_timer.isActive():
                self.event_timer.start(100)

            if hasattr(self, '_media_info_timer') and self._media_info_timer:
                self._media_info_timer.stop()

            self._media_info_scheduled = False
            self._track_list_logged = False

            self._setup_protocol_options(url, program_duration)
            is_vod = 'starttime=' in url.lower() or 'endtime=' in url.lower() or 'playseek' in url.lower()
            if is_vod:
                self._set_mpv_string('prefetch-playlist', 'no')
            else:
                self._set_mpv_string('prefetch-playlist', 'yes')

            mpv_url = self._normalize_url(url)
            result = _mpv_send_command(self.mpv_handle, ['loadfile', mpv_url])

            if result < 0:
                error_msg = f"播放失败: {result}"
                self.logger.error(error_msg)
                self.play_error.emit(error_msg)
                return False

            _mpv_set_property_string(self.mpv_handle, 'pause', 'no')

            if self._current_speed != 1.0:
                self._set_mpv_string('speed', str(self._current_speed))

            self.is_paused = False
            self.is_playing = True
            self.play_state_changed.emit(True)

            self._schedule_media_info_start()

            self.logger.debug(f"开始播放: {url}")
            return True
        except Exception as e:
            error_msg = f"播放失败: {str(e)}"
            self.logger.error(error_msg)
            self.play_error.emit(error_msg)
            return False

    def play_with_prefetch(self, url, next_urls=None, program_duration=0):
        try:
            self.current_url = url
            self._user_stopped = False
            self._switching_channel = True

            if not self.mpv_handle:
                self.play_error.emit("mpv播放器未初始化")
                return False

            self._setup_protocol_options(url, program_duration)

            is_vod = 'starttime=' in url.lower() or 'endtime=' in url.lower() or 'playseek' in url.lower()
            if is_vod:
                self._set_mpv_string('prefetch-playlist', 'no')
            else:
                self._set_mpv_string('prefetch-playlist', 'yes')

            mpv_url = self._normalize_url(url)
            result = _mpv_send_command(self.mpv_handle, ['loadfile', mpv_url])

            if result < 0:
                self.logger.error(f"预取播放失败: {result}")
                return False

            _mpv_set_property_string(self.mpv_handle, 'pause', 'no')
            if self._current_speed != 1.0:
                self._set_mpv_string('speed', str(self._current_speed))

            self.is_paused = False
            self.is_playing = True
            self.play_state_changed.emit(True)
            self._schedule_media_info_start()

            if next_urls:
                self._prefetch_next_channels(next_urls)

            self.logger.debug(f"开始播放(预取模式): {url}")
            return True
        except Exception as e:
            self.logger.error(f"预取播放失败: {str(e)}")
            return self.play(url)

    def _prefetch_next_channels(self, next_urls):
        prefetch_count = self._playback_settings.get('fcc_prefetch_count', 2)
        urls_to_prefetch = []
        for i, next_url in enumerate(next_urls[:prefetch_count]):
            if not next_url or not next_url.strip():
                continue
            urls_to_prefetch.append(next_url)

        if not urls_to_prefetch:
            return

        try:
            from services.network_preheat_service import DnsPrefetcher, ConnectionPreheater
            for next_url in urls_to_prefetch:
                dns_prefetcher = getattr(self, '_dns_prefetcher', None)
                if dns_prefetcher:
                    dns_prefetcher.prefetch(next_url)
                conn_preheater = getattr(self, '_connection_preheater', None)
                if conn_preheater:
                    conn_preheater.preheat(next_url)
            self.logger.debug(f"预取{len(urls_to_prefetch)}个相邻频道的DNS/TCP连接")
        except Exception as e:
            self.logger.debug(f"预取相邻频道失败(非致命): {e}")

    def stop(self):
        try:
            self._user_stopped = True
            was_playing = self.is_playing or self.current_url

            if self.mpv_handle:
                _mpv_send_command(self.mpv_handle, ['stop'])

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

            if was_playing:
                self.logger.info("停止播放")
        except Exception as e:
            self.logger.error(f"停止播放失败: {str(e)}")

    def terminate(self):
        try:
            self.logger.info("正在终止MPV播放器...")

            for timer_attr in ['_media_info_timer', '_live_info_timer', 'event_timer']:
                timer = getattr(self, timer_attr, None)
                if timer:
                    try:
                        timer.stop()
                    except Exception:
                        pass

            if self.mpv_handle:
                try:
                    _mpv_send_command(self.mpv_handle, ['quit'])
                except Exception as e:
                    self.logger.debug(f"发送quit命令失败（可能已关闭）: {e}")

                with self._lock:
                    terminate_destroy_mpv(self.mpv_handle)
                    self.mpv_handle = None

            self.is_playing = False
            self.is_paused = False
            self.current_url = None
            self.media_info = {}

            self.logger.info("MPV播放器已完全终止")
        except Exception as e:
            self.logger.error(f"终止MPV播放器失败: {str(e)}")

    def pause(self):
        try:
            if self.mpv_handle:
                result = _mpv_send_command(self.mpv_handle, ['cycle', 'pause'])
                if result < 0:
                    self.logger.error(f"切换暂停状态失败: {result}")
                else:
                    try:
                        actual_paused = self._get_mpv_property_int('pause')
                        self.is_paused = bool(actual_paused)
                    except Exception:
                        self.is_paused = not self.is_paused
                    self.is_playing = not self.is_paused

                    if self.is_paused:
                        self.logger.info("播放已暂停（继续缓冲中）")
                    else:
                        self.logger.info("恢复播放")

                    self.play_state_changed.emit(self.is_playing)
        except Exception as e:
            self.logger.error(f"暂停播放失败: {str(e)}")

    def set_volume(self, volume):
        try:
            self._last_volume = volume
            if self.mpv_handle:
                _mpv_set_property_string(self.mpv_handle, 'volume', f"{volume}")
        except Exception as e:
            self.logger.error(f"设置音量失败: {str(e)}")

    def get_volume(self):
        try:
            volume_value = self._get_mpv_property_double('volume')
            if volume_value is not None:
                self._last_volume = int(volume_value)
            return self._last_volume
        except Exception:
            return self._last_volume

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
                _mpv_set_property_string(self.mpv_handle, 'mute', 'yes' if muted else 'no')
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
            time_seconds = self._get_mpv_property_double('time-pos')
            if time_seconds is not None:
                return int(time_seconds * 1000)

            time_seconds = self._get_mpv_property_double('playback-time')
            if time_seconds is not None:
                return int(time_seconds * 1000)

            percent = self._get_mpv_property_double('percent-pos')
            if percent is not None:
                duration_seconds = self._get_mpv_property_double('duration')
                if duration_seconds is not None:
                    time_seconds = duration_seconds * (percent / 100.0)
                    return int(time_seconds * 1000)

            return 0
        except Exception:
            return 0

    def get_total_time(self):
        try:
            duration_seconds = self._get_mpv_property_double('duration')
            if duration_seconds is not None:
                return int(duration_seconds * 1000)

            duration_seconds = self._get_mpv_property_double('length')
            if duration_seconds is not None:
                return int(duration_seconds * 1000)

            return 0
        except Exception:
            return 0

    def get_position(self):
        try:
            percent_pos = self._get_mpv_property_double('percent-pos')
            if percent_pos is not None:
                return percent_pos / 100.0
            return 0
        except Exception:
            return 0

    def get_timeshift_range(self):
        try:
            if not self.mpv_handle:
                return (0, 0)
            current = self._get_mpv_property_double('time-pos') or 0
            return (max(0, current - 900), current)
        except Exception:
            return (0, 0)

    def seek_absolute(self, target_seconds):
        try:
            if self.mpv_handle and target_seconds >= 0:
                result = _mpv_send_command(self.mpv_handle, ['seek', f'{target_seconds:.3f}', 'absolute'])
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
                    result = _mpv_send_command(self.mpv_handle, ['seek', f'{target_position}', 'absolute'])
                    if result < 0:
                        seek_percent = position * 100.0
                        _mpv_send_command(self.mpv_handle, ['seek', f'{seek_percent}', 'absolute-percent'])
                else:
                    seek_percent = position * 100.0
                    _mpv_send_command(self.mpv_handle, ['seek', f'{seek_percent}', 'absolute-percent'])
        except Exception as e:
            self.logger.error(f"设置播放位置失败: {str(e)}")

    def seek_relative_seconds(self, seconds):
        try:
            if self.mpv_handle and seconds != 0:
                result = _mpv_send_command(self.mpv_handle, ['seek', f'{seconds:.1f}', 'relative'])
                if result < 0:
                    self.logger.warning(f"相对seek {seconds}秒失败，错误码: {result}")
                else:
                    self.logger.debug(f"相对seek: {seconds}秒")
        except Exception as e:
            self.logger.error(f"相对seek失败: {str(e)}")

    def get_live_media_info(self):
        if not self.mpv_handle:
            return None
        try:
            def get_str(prop):
                return self._get_mpv_property_string(prop)

            def get_int(prop):
                val = self._get_mpv_property_int(prop)
                if val is not None:
                    return val
                s = get_str(prop)
                if s:
                    try:
                        return int(s)
                    except ValueError:
                        return 0
                return 0

            def get_double(prop):
                val = self._get_mpv_property_double(prop)
                if val is not None:
                    return val
                s = get_str(prop)
                if s:
                    try:
                        return float(s)
                    except ValueError:
                        return 0.0
                return 0.0

            w = get_int('width')
            h = get_int('height')
            fps = get_double('container-fps')
            if fps == 0:
                fps = get_double('estimated-vf-fps')
            if fps == 0:
                fps = get_double('fps')

            hw = get_str('hwdec-current') or ''
            vcodec = get_str('video-codec') or ''
            acodec = get_str('audio-codec') or ''

            v_br = get_double('video-params/bitrate')
            if v_br == 0:
                v_br = get_double('demuxer-bitrate')
            a_br = get_double('audio-params/bitrate')

            container = get_str('file-format') or ''

            audio_channels = get_int('audio-params/channel-count')
            sample_rate = get_int('audio-params/samplerate')

            pix_fmt = get_str('video-params/pixelformat') or ''

            colormatrix = get_str('video-params/colormatrix') or ''
            color_primaries = get_str('video-params/primaries') or ''
            gamma = get_str('video-params/gamma') or ''
            colorlevels = get_str('video-params/colorlevels') or ''
            sig_peak = get_double('video-params/sig-peak')
            sig_avg = get_double('video-params/sig-avg')

            if not hasattr(self, '_last_info_debug') or self._last_info_debug != (w, h, vcodec, acodec):
                self._last_info_debug = (w, h, vcodec, acodec)
                self.logger.debug(f"媒体信息：width={w}, height={h}, vcodec='{vcodec}', acodec='{acodec}', fps={fps}, container='{container}'")

            if not vcodec and not acodec and w == 0:
                demuxer = get_str('demuxer') or ''
                v_format = get_str('video-format') or ''
                a_format = get_str('audio-format') or ''
                self.logger.info(f"demuxer: {demuxer}, video-format: {v_format}, audio-format: {a_format}")

                track_list_str = get_str('track-list') or ''
                if track_list_str and not getattr(self, '_track_list_logged', False):
                    self._track_list_logged = True
                    self.logger.info(f"track-list: {track_list_str[:500]}")
                paused = get_str('pause') or ''
                core_idle = get_str('core-idle') or ''
                demuxer_cache = get_str('demuxer-cache-state') or ''
                self.logger.debug(f"pause={paused}, core-idle={core_idle}, cache-state={demuxer_cache[:200]}")

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
                'colormatrix': colormatrix,
                'color_primaries': color_primaries,
                'gamma': gamma,
                'colorlevels': colorlevels,
                'sig_peak': sig_peak,
                'sig_avg': sig_avg,
                'demuxer': get_str('demuxer') or '',
                'protocol': get_str('protocol') or '',
                'video_format': get_str('video-format') or '',
                'audio_format': get_str('audio-format') or '',
                'aspect_ratio': get_str('video-params/aspect') or '',
                'dwidth': get_int('dwidth'),
                'dheight': get_int('dheight'),
                'video_fps': get_double('estimated-vf-fps') or 0,
                'audio_bitrate_demux': get_double('audio-params/bitrate') or 0,
                'cache_speed': get_double('cache-speed') or 0,
                'cache_used': get_double('demuxer-cache-state/demo-range/avg') or 0,
                'buffering': get_int('cache-buffering-state') or 0,
            }
            return info
        except Exception as e:
            self.logger.error(f"获取媒体信息失败：{str(e)}")
            return None

    def _start_live_info_timer(self):
        if hasattr(self, '_live_info_timer') and self._live_info_timer:
            self._live_info_timer.stop()
            self._live_info_timer.deleteLater()
        self._static_info_counter = self._STATIC_INFO_REFRESH_TICKS
        self._live_info_timer = QTimer(self)
        self._live_info_timer.timeout.connect(self._update_live_info)
        self._live_info_timer.start(500)

    def _stop_live_info_timer(self):
        if hasattr(self, '_live_info_timer') and self._live_info_timer:
            self._live_info_timer.stop()

    _STATIC_INFO_REFRESH_TICKS = 10

    def _update_live_info(self):
        if not self.mpv_handle:
            return

        self._static_info_counter = getattr(self, '_static_info_counter', 0) + 1
        if self._static_info_counter >= self._STATIC_INFO_REFRESH_TICKS:
            self._static_info_counter = 0
            info = self.get_live_media_info()
            if info:
                try:
                    self.live_media_info_updated.emit(info)
                except RuntimeError as e:
                    self.logger.error(f"_update_live_info: 信号发送失败 {str(e)}")
                    self._stop_live_info_timer()
                    return

        if self.is_playing:
            try:
                current_time = self.get_current_time()
                total_time = self.get_total_time()
                position = self.get_position()

                self._pos_log_count = getattr(self, '_pos_log_count', 0) + 1
                if self._pos_log_count in (1, 2, 3, 5, 10):
                    self.logger.debug(f"[SRC{self._pos_log_count}] total={total_time} cur={current_time} pos={position} url={self.current_url[:60] if self.current_url else 'None'}...")

                self.playback_position_updated.emit(
                    int(current_time or 0),
                    int(total_time or 0),
                    float(position or 0)
                )
            except RuntimeError:
                pass

    def _schedule_media_info_start(self):
        if getattr(self, '_media_info_scheduled', False):
            return
        self._media_info_scheduled = True

        if hasattr(self, '_live_info_timer') and self._live_info_timer:
            self._live_info_timer.stop()

        self._media_info_timer = QTimer(self)
        self._media_info_timer.singleShot(1000, self._start_live_info_timer)

        QTimer.singleShot(3000, self._capture_thumbnail)

    def _capture_thumbnail(self):
        if not self.is_playing or not self.current_url:
            return
        try:
            import hashlib
            cache_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'cache', 'thumbnails')
            os.makedirs(cache_dir, exist_ok=True)
            url_hash = hashlib.md5(self.current_url.encode('utf-8')).hexdigest()
            filepath = os.path.join(cache_dir, f"{url_hash}.png")
            if os.path.exists(filepath):
                return
            self.send_command(['screenshot-to-file', filepath, 'video'])
            QTimer.singleShot(1500, lambda: self._check_thumbnail_saved(filepath))
        except Exception as e:
            self.logger.debug(f"缩略图截取失败: {e}")

    def _check_thumbnail_saved(self, filepath):
        try:
            if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
                self.thumbnail_captured.emit(self.current_url)
        except Exception:
            pass

    @staticmethod
    def get_thumbnail_path(url):
        if not url:
            return None
        import hashlib
        cache_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'cache', 'thumbnails')
        filepath = os.path.join(cache_dir, f"{hashlib.md5(url.encode('utf-8')).hexdigest()}.png")
        if os.path.exists(filepath):
            return filepath
        return None

    @staticmethod
    def _guess_protocol(url):
        if not url:
            return '未知'
        u = url.lower()
        if u.startswith('bd://'):
            return 'BLURAY'
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
            if MpvPlayerController._is_network_drive(url):
                return 'NET-FILE'
            return 'FILE'
        return '未知'

    def _get_mpv_property_string(self, property_name):
        return _mpv_get_property_string(self.mpv_handle, property_name)

    def _get_mpv_error_string(self, error_code):
        try:
            from services.mpv_common import libmpv as _libmpv
            if hasattr(_libmpv, 'mpv_error_string'):
                error_str = _libmpv.mpv_error_string(error_code)
                if error_str:
                    return error_str.decode('utf-8')
        except Exception:
            pass
        return f"错误码: {error_code}"

    def _get_mpv_property_int(self, property_name):
        return _mpv_get_property_int(self.mpv_handle, property_name)

    def _get_mpv_property_double(self, property_name):
        return _mpv_get_property_double(self.mpv_handle, property_name)

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
            _mpv_set_property_string(self.mpv_handle, 'pause', 'no')
            eof = self._get_mpv_property_string('eof-reached')
            if eof and eof.lower() == 'yes':
                _mpv_send_command(self.mpv_handle, ['stop'])
                time.sleep(0.08)
        except Exception:
            pass

    def is_eof_reached(self):
        try:
            eof = self._get_mpv_property_string('eof-reached')
            return eof and eof.lower() == 'yes'
        except Exception:
            return False

    def get_buffer_state(self):
        try:
            if not self.mpv_handle:
                return None
            cache_state_str = self._get_mpv_property_string('demuxer-cache-state')
            cache_duration = 0
            buffering = False
            if cache_state_str:
                try:
                    import json
                    cache_state = json.loads(cache_state_str)
                    seekable_ranges = cache_state.get('seekable-ranges', [])
                    if seekable_ranges:
                        first = seekable_ranges[0]
                        cache_duration = first.get('end', 0) - first.get('start', 0)
                    buffering = cache_state.get('eof', False) is False and cache_state.get('underrun', False)
                except Exception:
                    pass
            if cache_duration <= 0:
                dur = self._get_mpv_property_double('demuxer-cache-duration') or 0
                if dur > 0:
                    cache_duration = dur
            paused_for_cache = self._get_mpv_property_string('paused-for-cache')
            if paused_for_cache == 'yes':
                buffering = True
            return {
                'cache_duration': cache_duration,
                'buffering': buffering
            }
        except Exception:
            return None

    def get_track_list(self, track_type='audio'):
        try:
            if not self.mpv_handle:
                return []
            track_list_str = self._get_mpv_property_string('track-list')
            if not track_list_str:
                return []
            import json
            tracks = json.loads(track_list_str)
            result = []
            for t in tracks:
                if t.get('type') == track_type:
                    result.append({
                        'id': t.get('id', 0),
                        'lang': t.get('lang', ''),
                        'title': t.get('title', ''),
                        'default': t.get('default', False),
                        'codec': t.get('codec', ''),
                    })
            return result
        except Exception:
            return []

    def set_track(self, track_type, track_id):
        try:
            if not self.mpv_handle:
                return False
            prop = f'{track_type}-track' if track_type in ('audio', 'sub') else track_type
            current = self.get_current_track(track_type)
            if current is not None and current == track_id:
                return True
            result = _mpv_set_property_int64(self.mpv_handle, prop, int(track_id))
            if result < 0:
                result2 = self._set_mpv_string(prop, str(track_id))
                if result2 < 0:
                    cmd_prop = 'aid' if track_type == 'audio' else ('sid' if track_type == 'sub' else prop)
                    result3 = self.send_command(['set', cmd_prop, str(track_id)])
                    if result3 == 0:
                        return True
                    self.logger.error(f"切换轨道失败: {prop}={track_id}, int64错误码={result}, string错误码={result2}, command错误码={result3}")
                    return False
            return True
        except Exception as e:
            self.logger.error(f"切换轨道失败: {e}")
            return False

    def get_current_track(self, track_type='audio'):
        try:
            if not self.mpv_handle:
                return None
            prop = f'{track_type}-track' if track_type in ('audio', 'sub') else track_type
            result = self._get_mpv_property_int(prop)
            if result is not None:
                return result
            str_val = self._get_mpv_property_string(prop)
            if str_val and str_val not in ('no', ''):
                try:
                    return int(str_val)
                except ValueError:
                    return None
            return None
        except Exception:
            return None

    def add_subtitle_file(self, file_path):
        try:
            if not self.mpv_handle:
                return False
            return self.send_command(['sub-add', file_path, 'select']) == 0
        except Exception as e:
            self.logger.error(f"加载外部字幕失败: {e}")
            return False

    def set_property_string(self, name, value):
        self._set_mpv_string(name, value)

    def send_command(self, cmd_args):
        return _mpv_send_command(self.mpv_handle, cmd_args)

    def show_osd(self, text: str, duration: int = 3000):
        self.send_command(['show-text', text, str(duration)])

    def _apply_osd_colors(self):
        if not self.mpv_handle:
            return
        try:
            from ui.styles import AppStyles
            colors = AppStyles._get_colors()
            osd_fg = colors.get('osd_text', '#ffffff')
            osd_border = colors.get('osd_border', '#000000')
            osd_shadow = colors.get('osd_shadow', '#000000')
            _mpv_set_property_string(self.mpv_handle, 'osd-color', osd_fg)
            _mpv_set_property_string(self.mpv_handle, 'osd-border-color', osd_border)
            _mpv_set_property_string(self.mpv_handle, 'osd-shadow-color', osd_shadow)
            font_family = colors.get('font_family', "'Segoe UI', 'Microsoft YaHei', sans-serif")
            _mpv_set_property_string(self.mpv_handle, 'osd-font', font_family)
        except Exception:
            pass

    def update_osd_theme(self):
        self._apply_osd_colors()

    @staticmethod
    def detect_hdr_type(colormatrix: str, gamma: str, sig_peak: float) -> str:
        if not colormatrix and not gamma:
            return 'SDR'
        if gamma and 'pq' in gamma.lower() and sig_peak > 4000:
            if 'bt.2020' in colormatrix.lower():
                return 'DV'
        if gamma and 'pq' in gamma.lower() and sig_peak > 1000:
            return 'HDR10+'
        if gamma and ('pq' in gamma.lower() or 'smpte2084' in gamma.lower()):
            return 'HDR10'
        if gamma and ('hlg' in gamma.lower() or 'arib-std-b67' in gamma.lower()):
            return 'HLG'
        if colormatrix:
            cm_lower = colormatrix.lower()
            if 'bt.2020' in cm_lower or 'bt.2100' in cm_lower:
                if sig_peak > 100:
                    return 'HLG'
                else:
                    return 'WCG'
            if 'bt.709' in cm_lower or 'bt.601' in cm_lower:
                return 'SDR'
        return 'SDR'

    def get_available_seek_range(self) -> dict:
        empty = {'max_back': 0, 'max_forward': 0, 'cache_duration': 0,
                 'buffer_start': 0, 'buffer_end': 0, 'time_pos': 0}
        if not self.mpv_handle:
            return empty
        try:
            time_pos = self._get_mpv_property_double('time-pos') or 0
            buffer_start = 0.0
            buffer_end = 0.0
            cache_duration = 0.0
            cache_state_str = self._get_mpv_property_string('demuxer-cache-state')
            if cache_state_str:
                try:
                    import json
                    cache_state = json.loads(cache_state_str)
                    seekable_ranges = cache_state.get('seekable-ranges', [])
                    if seekable_ranges:
                        first = seekable_ranges[0]
                        buffer_start = first.get('start', 0)
                        buffer_end = first.get('end', 0)
                        cache_duration = buffer_end - buffer_start
                except Exception:
                    pass
            if cache_duration <= 0:
                cache_dur = self._get_mpv_property_double('demuxer-cache-duration') or 0
                if cache_dur > 0:
                    cache_duration = cache_dur
                    buffer_start = max(0, time_pos - cache_dur)
                    buffer_end = time_pos
            max_back = int(cache_duration) if cache_duration > 0 else 0
            max_forward = min(60, max(0, int(cache_duration * 0.1)))
            return {
                'max_back': max_back,
                'max_forward': max_forward,
                'cache_duration': cache_duration,
                'buffer_start': buffer_start,
                'buffer_end': buffer_end,
                'time_pos': time_pos
            }
        except Exception as e:
            self.logger.debug(f"获取可回退范围失败: {e}")
            return empty
