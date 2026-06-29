import os
import time
import ctypes
import sys
import threading
from PySide6.QtCore import QObject, Signal, QTimer
from core.log_manager import global_logger
from utils.platform_utils import is_windows, is_macos, is_linux, is_android
from services.mpv_common import (
    mpv_event,
    mpv_event_end_file,
    mpv_event_property,
    MPV_EVENT_NONE,
    MPV_EVENT_SHUTDOWN,
    MPV_EVENT_START_FILE,
    MPV_EVENT_END_FILE,
    MPV_EVENT_FILE_LOADED,
    MPV_EVENT_PROPERTY_CHANGE,
    MPV_FORMAT_STRING,
    MPV_FORMAT_INT64,
    MPV_FORMAT_DOUBLE,
    MPV_FORMAT_FLAG,
    MPV_END_FILE_REASON_EOF,
    MPV_END_FILE_REASON_ERROR,
    MPV_END_FILE_REASON_STOP,
    MPV_END_FILE_REASON_QUIT,
    get_property_string as _mpv_get_property_string,
    get_property_int as _mpv_get_property_int,
    get_property_double as _mpv_get_property_double,
    create_mpv_handle,
    initialize_mpv,
    destroy_mpv,
    terminate_destroy_mpv,
    set_property_string as _mpv_set_property_string,
    set_property_int64 as _mpv_set_property_int64,
    set_option_string as _mpv_set_option_string,
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
        'network_timeout_sec': 30,
        'audio_passthrough': 'never',
        'http_referer': '',
        'http_proxy': '',
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

    play_state_changed = Signal(bool)
    play_error = Signal(str)
    reconnect_requested = Signal(str)
    timeshift_continue_requested = Signal()
    live_media_info_updated = Signal(dict)
    playback_position_updated = Signal(int, int, float)
    logo_cache_loaded = Signal(str, object)
    thumbnail_captured = Signal(str)
    file_loaded = Signal()
    local_file_ended = Signal(str)
    # 本地文件结束时需保存播放位置：参数 (url, position_sec, duration_sec)
    local_file_position_to_save = Signal(str, float, float)

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
        self._use_render_api = False
        self._terminated = False
        from services.audio_visual_service import AudioVisualService
        self.audio_visual = AudioVisualService(self)

    def _ensure_mpv_initialized(self):
        if self._mpv_initialized:
            return True


        try:
            import services.mpv_common as _mpv_mod
            if not _mpv_mod._ensure_libmpv_loaded():
                error_msg = "libmpv加载失败"
                self.logger.error(error_msg)
                self._safe_emit(self.play_error, error_msg)
                return False

            if not _mpv_mod.MPV_AVAILABLE or _mpv_mod.libmpv is None:
                error_msg = "libmpv加载失败"
                self.logger.error(error_msg)
                self._safe_emit(self.play_error, error_msg)
                return False

            self.mpv_handle = create_mpv_handle()
            if not self.mpv_handle:
                error_msg = "创建mpv实例失败"
                self.logger.error(error_msg)
                self._safe_emit(self.play_error, error_msg)
                return False

            self.video_widget.show()
            self.video_widget.repaint()

            # macOS使用vo=libmpv + render API时不需要设置wid
            _skip_wid = False
            if is_macos():
                try:
                    from services.mpv_gl_widget import MpvGLWidget
                    _skip_wid = isinstance(self.video_widget, MpvGLWidget)
                except Exception:
                    pass

            if not _skip_wid:
                try:
                    from PySide6.QtWidgets import QApplication
                    QApplication.processEvents()
                except Exception:
                    pass

                if is_linux():
                    self.logger.info(
                        f"Linux窗口环境: QT_QPA_PLATFORM={os.environ.get('QT_QPA_PLATFORM', '<未设置>')}, "
                        f"XDG_SESSION_TYPE={os.environ.get('XDG_SESSION_TYPE', '<未设置>')}, "
                        f"WAYLAND_DISPLAY={os.environ.get('WAYLAND_DISPLAY', '<未设置>')}"
                    )

                window_id = self.video_widget.winId()
                if hasattr(window_id, 'value'):
                    window_id = window_id.value

                try:
                    window_id_int = int(window_id)
                    if window_id_int > 0:
                        ret = _mpv_set_option_string(self.mpv_handle, 'wid', f"{window_id_int}")
                        if ret < 0:
                            self.logger.error(f"设置wid失败，错误码: {ret}, 窗口ID: {window_id_int}")
                        else:
                            self.logger.info(f"设置窗口ID成功: {window_id_int}")
                    else:
                        self.logger.warning(f"窗口ID无效: {window_id_int}")
                except Exception as e:
                    self.logger.error(f"设置窗口ID失败: {str(e)}")


            hdr_mode = self._playback_settings.get('hdr_output_mode', 'disable')

            system_hdr_enabled = False
            try:
                if is_windows():
                    from utils.hdr_detect import is_windows_hdr_enabled
                    system_hdr_enabled = is_windows_hdr_enabled()
                elif is_macos():
                    from utils.hdr_detect import is_macos_hdr_enabled
                    system_hdr_enabled = is_macos_hdr_enabled()
                elif is_android():
                    from utils.hdr_detect import is_android_hdr_enabled
                    system_hdr_enabled = is_android_hdr_enabled()
            except Exception as e:
                self.logger.warning(f"HDR检测失败，保守使用SDR模式: {e}")

            self._hdr_fallback_tonemap = False
            if hdr_mode == 'disable':
                vo = 'gpu'
            elif hdr_mode == 'tonemap':
                vo = 'gpu'
            elif hdr_mode == 'passthrough':
                if system_hdr_enabled:
                    vo = 'gpu-next'
                else:
                    self.logger.warning("系统未启用HDR，passthrough模式回退到tonemap")
                    vo = 'gpu'
                    self._hdr_fallback_tonemap = True
            elif hdr_mode == 'scrgb':
                if system_hdr_enabled:
                    vo = 'gpu-next'
                else:
                    self.logger.warning("系统未启用HDR，scrgb模式回退到tonemap")
                    vo = 'gpu'
                    self._hdr_fallback_tonemap = True
            else:
                if system_hdr_enabled:
                    vo = 'gpu-next'
                else:
                    vo = 'gpu'

            # gpu-api和gpu-context必须在vo之前设置
            # 否则mpv内部锁定渲染后端后，gpu-context设置会被拒绝(错误码-7)
            if is_windows():
                _mpv_set_option_string(self.mpv_handle, 'gpu-api', 'd3d11')
                _mpv_set_option_string(self.mpv_handle, 'd3d11-sync-interval', '1')
            elif is_macos():
                # macOS上mpv v0.41+的gpu-context选项不再支持wid嵌入
                # 使用vo=libmpv + render API渲染到QOpenGLWidget（IINA等播放器的标准方案）
                ret_vo = _mpv_set_option_string(self.mpv_handle, 'vo', 'libmpv')
                if ret_vo >= 0:
                    self.logger.info("macOS: 设置vo=libmpv成功，将使用render API渲染")
                    self._use_render_api = True
                else:
                    self.logger.warning(f"macOS: 设置vo=libmpv失败(错误码:{ret_vo})，回退wid嵌入")
                    self._use_render_api = False
                    for ctx_val in ['cocoa', 'coregraphics', 'macos']:
                        ret_ctx = _mpv_set_option_string(self.mpv_handle, 'gpu-context', ctx_val)
                        if ret_ctx >= 0:
                            self.logger.info(f"设置gpu-context={ctx_val}成功")
                            break
                        self.logger.warning(f"设置gpu-context={ctx_val}失败(错误码:{ret_ctx})")
                _mpv_set_option_string(self.mpv_handle, 'force-window', 'no')
            elif is_linux():
                _mpv_set_option_string(self.mpv_handle, 'gpu-api', 'opengl')
                ret_ctx = _mpv_set_option_string(self.mpv_handle, 'gpu-context', 'x11')
                if ret_ctx < 0:
                    self.logger.warning(f"设置gpu-context=x11失败(错误码:{ret_ctx})，尝试x11egl")
                    ret_ctx = _mpv_set_option_string(self.mpv_handle, 'gpu-context', 'x11egl')
                    if ret_ctx < 0:
                        self.logger.error(f"设置gpu-context=x11egl也失败(错误码:{ret_ctx})，wid嵌入可能无法工作")
                    else:
                        self.logger.info("设置gpu-context=x11egl成功")
                else:
                    self.logger.info("设置gpu-context=x11成功")
                _mpv_set_option_string(self.mpv_handle, 'force-window', 'no')

            if not (is_macos() and getattr(self, '_use_render_api', False)):
                _mpv_set_option_string(self.mpv_handle, 'vo', vo)
            hwdec = 'auto' if self._playback_settings.get('hwdec', True) else 'no'
            _mpv_set_option_string(self.mpv_handle, 'hwdec', hwdec)
            _mpv_set_option_string(self.mpv_handle, 'osc', 'no')
            _mpv_set_option_string(self.mpv_handle, 'osd-bar', 'no')

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

            # source-timeout：source 暂时不可用时快速失败，避免长时间阻塞导致卡顿
            source_to = self._playback_settings.get('source_timeout_sec', 0)
            if source_to > 0:
                _mpv_set_property_string(self.mpv_handle, 'source-timeout', str(source_to))

            # 性能与卡顿优化：
            # - framedrop=vo：视频输出慢时丢帧，避免渲染积压阻塞 GUI（默认值，但显式指定避免 mpv 版本差异）
            # - cache-pause-initial=no：初始缓存阶段不暂停，避免直播流启动卡顿
            # - video-sync=audio：以音频时钟为同步基准，视频帧迟到时丢帧而非阻塞
            _mpv_set_property_string(self.mpv_handle, 'framedrop', 'vo')
            _mpv_set_property_string(self.mpv_handle, 'cache-pause-initial', 'no')
            _mpv_set_property_string(self.mpv_handle, 'video-sync', 'audio')

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
                self._safe_emit(self.play_error, error_msg)
                destroy_mpv(self.mpv_handle)
                self.mpv_handle = None
                return False

            try:
                _mpv_observe_property(self.mpv_handle, 1, 'pause', MPV_FORMAT_FLAG)
            except Exception as e:
                self.logger.warning(f"订阅pause属性失败: {str(e)}")

            self.logger.info("mpv播放器初始化成功")

            if is_macos() and getattr(self, '_use_render_api', False):
                try:
                    if hasattr(self.video_widget, 'setup_render_context'):
                        if not self.video_widget.setup_render_context(self.mpv_handle):
                            self.logger.error("macOS render context创建失败，视频可能无法显示")
                except Exception as e:
                    self.logger.error(f"macOS render context初始化异常: {e}")

            if is_macos():
                try:
                    _ver = self._get_mpv_property_string('mpv-version') or '?'
                    _vo = self._get_mpv_property_string('vo') or '?'
                    _ga = self._get_mpv_property_string('gpu-api') or '?'
                    _gc = self._get_mpv_property_string('gpu-context') or '?'
                    self.logger.info(f"macOS mpv诊断: version={_ver}, vo={_vo}, gpu-api={_ga}, gpu-context={_gc}")
                except Exception as e:
                    self.logger.debug(f"macOS mpv诊断读取失败: {e}")

            try:
                _vo = self._get_mpv_property_string('vo') or '?'
                _tp = self._get_mpv_property_string('target-prim') or '?'
                _tt = self._get_mpv_property_string('target-trc') or '?'
                _tm = self._get_mpv_property_string('tone-mapping') or '?'
                _tch = self._get_mpv_property_string('target-colorspace-hint') or '?'
                _ga = self._get_mpv_property_string('gpu-api') or '?'
                _gc = self._get_mpv_property_string('gpu-context') or '?'
                _csp = self._get_mpv_property_string('d3d11-output-csp') or '?'
                self.logger.info(f"HDR诊断: vo={_vo}, gpu-api={_ga}, gpu-context={_gc}, target-prim={_tp}, target-trc={_tt}, tone-mapping={_tm}, target-colorspace-hint={_tch}, d3d11-output-csp={_csp}, hdr_mode={hdr_mode}")
            except Exception as e:
                self.logger.debug(f"HDR诊断读取失败: {e}")

            self.event_timer = QTimer(self)
            self.event_timer.timeout.connect(self._process_events)
            self.event_timer.start(100)

            self._mpv_initialized = True
            return True

        except Exception as e:
            error_msg = f"初始化mpv播放器失败: {str(e)}"
            self.logger.error(error_msg)
            self._safe_emit(self.play_error, error_msg)
            if self.mpv_handle:
                destroy_mpv(self.mpv_handle)
                self.mpv_handle = None
            return False

    def _safe_emit(self, signal, *args):
        if self._terminated:
            return
        try:
            signal.emit(*args)
        except RuntimeError:
            pass

    def _apply_tonemap_config(self):
        # HDR→SDR 色调映射：显式指定目标色域和 gamma，避免 mpv 自动推断失败
        # （PQ 是绝对 OETF，依赖明确的 target-trc 才能正确逆转换；HLG 有 OOTF 兼容路径不受影响）
        self._set_mpv_string('tone-mapping', 'bt.2390')      # EETF，比 hable 更适合 HDR→SDR
        self._set_mpv_string('tone-mapping-mode', 'auto')
        self._set_mpv_string('tone-mapping-desat', '0.5')    # 高光去饱和，避免画面发灰
        self._set_mpv_string('hdr-compute-peak', 'yes')
        self._set_mpv_string('d3d11-output-csp', 'srgb')
        self._set_mpv_string('target-prim', 'bt.709')        # SDR 显示器色域
        self._set_mpv_string('target-trc', 'bt.1886')        # SDR 显示器 gamma
        self._set_mpv_string('target-colorspace-hint', 'no')  # 避免从 passthrough 切过来残留
        self.logger.info("HDR配置: tonemap → SDR (bt.2390, bt.709/bt.1886)")

    def _apply_passthrough_config(self):
        self._set_mpv_string('tone-mapping', 'clip')
        self._set_mpv_string('hdr-compute-peak', 'no')
        self._set_mpv_string('d3d11-output-csp', 'pq')
        self._set_mpv_string('target-colorspace-hint', 'yes')
        # 显式指定 HDR 目标色域和传递特性（PQ OETF 依赖明确 target-trc 才能正确转换）
        # 留空时 mpv 自动推断对 HDR10 不稳定，会导致画面偏暗；HLG 因有 OOTF 兼容路径影响较小
        self._set_mpv_string('target-prim', 'bt.2020')   # HDR 标准色域
        self._set_mpv_string('target-trc', 'pq')           # HDR10 PQ 传递特性
        self.logger.info("HDR配置: passthrough → PQ直通 (bt.2020/pq)")

    def _apply_scrgb_config(self):
        self._set_mpv_string('tone-mapping', 'clip')
        self._set_mpv_string('hdr-compute-peak', 'no')
        self._set_mpv_string('d3d11-output-csp', 'pq')
        self._set_mpv_string('target-colorspace-hint', 'yes')
        # 显式指定 HDR 目标色域和传递特性（与 passthrough 一致）
        # auto 模式下系统 HDR 开启时走此分支，输出 PQ HDR 信号给显示器
        self._set_mpv_string('target-prim', 'bt.2020')
        self._set_mpv_string('target-trc', 'pq')
        self.logger.info("HDR配置: scrgb → PQ直通 (bt.2020/pq)")

    def _reset_hdr_params(self):
        # 非 HDR 视频：显式指定 SDR 目标，确保 bt.2020 色域（WCG）视频能正确映射到 bt.709
        self._set_mpv_string('tone-mapping', '')
        self._set_mpv_string('tone-mapping-mode', '')
        self._set_mpv_string('tone-mapping-desat', '')
        self._set_mpv_string('hdr-compute-peak', '')
        self._set_mpv_string('d3d11-output-csp', 'srgb')
        self._set_mpv_string('target-prim', 'bt.709')        # SDR 显示器色域
        self._set_mpv_string('target-trc', 'bt.1886')        # SDR 显示器 gamma
        self._set_mpv_string('target-colorspace-hint', 'no')
        self.logger.info("HDR配置: 已重置为SDR默认值 (bt.709/bt.1886)")


    def _set_mpv_string(self, name, value):
        if self._terminated or not self.mpv_handle:
            return -1
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


    def _is_network_url(self, url):
        if not url:
            return False
        return url.lower().startswith(('http://', 'https://', 'rtsp://', 'rtp://', 'udp://', 'rtmp://'))

    @staticmethod
    def _is_network_drive(path):
        if not is_windows():
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
        result: list = [None]
        event = threading.Event()

        def _worker():
            result[0] = self._check_path_reachability_sync(url)
            event.set()

        t = threading.Thread(target=_worker, daemon=True)
        t.start()
        if not event.wait(timeout=3.5):
            self.logger.debug("网络可达性检查超时，继续尝试播放")
            return None
        return result[0]

    @staticmethod
    def _fix_unc_path(path):
        if not path:
            return path
        if not is_windows():
            return path
        if path.startswith('//'):
            path = '\\\\' + path[2:]
            return path.replace('/', '\\')
        if path.startswith('\\\\'):
            return path.replace('/', '\\')
        if len(path) >= 2 and path[1] == ':':
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
                    return path
        for item in os.listdir(path):
            sub = os.path.join(path, item)
            if os.path.isdir(sub):
                sub_bdmv = os.path.join(sub, 'BDMV')
                if os.path.isdir(sub_bdmv):
                    stream_dir = os.path.join(sub_bdmv, 'STREAM')
                    if os.path.isdir(stream_dir):
                        m2ts_files = [f for f in os.listdir(stream_dir) if f.lower().endswith('.m2ts')]
                        if m2ts_files:
                            return sub
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

    def _apply_hdr_on_file_loaded(self):
        try:
            if not self.mpv_handle or self._terminated:
                return
            hdr_mode = self._playback_settings.get('hdr_output_mode', 'disable')

            if hdr_mode == 'disable':
                self._reset_hdr_params()
                return

            vp_prim = (self._get_mpv_property_string('video-params/primaries') or '').lower()
            vp_gamma = (self._get_mpv_property_string('video-params/gamma') or '').lower()
            vp_peak = self._get_mpv_property_double('video-params/sig-peak') or 0

            self.logger.info(f"视频HDR参数: primaries={vp_prim}, gamma={vp_gamma}, sig_peak={vp_peak}")

            is_hdr_video = ('pq' in vp_gamma or 'smpte2084' in vp_gamma or
                           'hlg' in vp_gamma or 'arib-std-b67' in vp_gamma or
                           vp_peak > 100)

            if not is_hdr_video:
                self.logger.info("非HDR视频，重置HDR参数为默认值")
                self._reset_hdr_params()
                return

            if hdr_mode == 'tonemap':
                self._apply_tonemap_config()
                return

            if hdr_mode == 'passthrough':
                if getattr(self, '_hdr_fallback_tonemap', False):
                    self._apply_tonemap_config()
                else:
                    self._apply_passthrough_config()
                return

            if hdr_mode == 'scrgb':
                if getattr(self, '_hdr_fallback_tonemap', False):
                    self._apply_tonemap_config()
                else:
                    self._apply_scrgb_config()
                return

            if hdr_mode == 'auto':
                system_hdr_enabled = False
                try:
                    if is_windows():
                        from utils.hdr_detect import is_windows_hdr_enabled
                        system_hdr_enabled = is_windows_hdr_enabled()
                    elif is_macos():
                        from utils.hdr_detect import is_macos_hdr_enabled
                        system_hdr_enabled = is_macos_hdr_enabled()
                    elif is_android():
                        from utils.hdr_detect import is_android_hdr_enabled
                        system_hdr_enabled = is_android_hdr_enabled()
                except Exception:
                    pass

                if system_hdr_enabled:
                    self._apply_scrgb_config()
                else:
                    self._apply_tonemap_config()
                return

        except Exception as e:
            self.logger.error(f"应用HDR设置失败: {e}")

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

            # HTTP Referer
            referer = settings.get('http_referer', '') or ''
            if referer:
                self._set_mpv_string('referrer', referer)
                self.logger.debug(f"[mpv] referrer set: {referer[:50]}")
            else:
                self._set_mpv_string('referrer', '')

            # HTTP/HTTPS 代理
            proxy = settings.get('http_proxy', '') or ''
            if proxy:
                # mpv 的 http-proxy 选项对 HTTP/HTTPS 流生效
                self._set_mpv_string('http-proxy', proxy)
                self.logger.debug(f"[mpv] http-proxy set: {proxy[:50]}")
            else:
                self._set_mpv_string('http-proxy', '')

    def _process_events(self):
        if self._terminated:
            return
        with self._lock:
            handle = self.mpv_handle
            if not handle:
                return
        try:
            while not self._terminated:
                with self._lock:
                    if self._terminated or self.mpv_handle is not handle:
                        return
                    from services.mpv_common import libmpv as _libmpv
                    event_ptr = _libmpv.mpv_wait_event(handle, 0.0)
                    if not event_ptr:
                        return
                    event = ctypes.cast(event_ptr, ctypes.POINTER(mpv_event)).contents

                if event.event_id == MPV_EVENT_NONE:
                    return

                if event.event_id == MPV_EVENT_PROPERTY_CHANGE:
                    if event.data:
                        try:
                            import ctypes as _ctypes
                            prop = _ctypes.cast(event.data, _ctypes.POINTER(mpv_event_property)).contents
                            if prop.name:
                                name = _ctypes.cast(prop.name, _ctypes.c_char_p).value
                                if name and name.decode('utf-8', errors='ignore') == 'pause':
                                    if prop.format == MPV_FORMAT_FLAG and prop.data:
                                        val_ptr = _ctypes.cast(prop.data, _ctypes.POINTER(_ctypes.c_int)).contents
                                        new_paused = bool(val_ptr.value)
                                        if new_paused != self.is_paused:
                                            self.is_paused = new_paused
                                            self._safe_emit(self.play_state_changed, not new_paused)
                                    elif prop.format == MPV_FORMAT_STRING and prop.data:
                                        val_ptr = _ctypes.cast(prop.data, _ctypes.POINTER(_ctypes.c_char_p)).contents
                                        if val_ptr:
                                            val = val_ptr.decode('utf-8', errors='ignore')
                                            new_paused = (val == 'yes')
                                            if new_paused != self.is_paused:
                                                self.is_paused = new_paused
                                                self._safe_emit(self.play_state_changed, not new_paused)
                        except Exception:
                            pass

                elif event.event_id == MPV_EVENT_FILE_LOADED:
                    self._reconnect_count = 0
                    self._switching_channel = False
                    self.is_playing = True
                    self._schedule_media_info_start()
                    self._adjust_buffer_for_content()
                    self._apply_hdr_on_file_loaded()
                    if hasattr(self, 'audio_visual') and self.audio_visual:
                        self.audio_visual.auto_enable_if_audio()
                    self._safe_emit(self.file_loaded)

                elif event.event_id == MPV_EVENT_END_FILE:
                    if event.data:
                        end_file = ctypes.cast(event.data, ctypes.POINTER(mpv_event_end_file)).contents
                        reason = end_file.reason
                        if reason == MPV_END_FILE_REASON_EOF:
                            if self._user_stopped:
                                self.logger.debug("END_FILE_EOF: 用户已停止，忽略")
                            elif self.current_url and self._is_network_url(self.current_url):
                                self.logger.info("END_FILE_EOF: 流播放到终点，请求续播")
                                self.is_playing = False
                                self.is_paused = False
                                self._safe_emit(self.play_state_changed, False)
                                self._safe_emit(self.timeshift_continue_requested)
                            else:
                                self.logger.debug("END_FILE_EOF: 非网络流，正常结束")
                                ended_url = self.current_url or ''
                                # 保存播放位置（用于断点续播）
                                try:
                                    pos_sec = self._get_mpv_property_double('time-pos') or 0.0
                                    dur_sec = self._get_mpv_property_double('duration') or 0.0
                                    if ended_url and pos_sec > 0:
                                        self._safe_emit(self.local_file_position_to_save, ended_url, float(pos_sec), float(dur_sec))
                                except Exception as e:
                                    self.logger.debug(f"保存播放位置失败: {e}")
                                self.is_playing = False
                                self.is_paused = False
                                self._safe_emit(self.play_state_changed, False)
                                self._safe_emit(self.local_file_ended, ended_url)
                        elif reason == MPV_END_FILE_REASON_ERROR:
                            if self._switching_channel:
                                self.logger.debug("频道切换导致的END_FILE，忽略重连")
                                self._switching_channel = False
                            elif not self._user_stopped and self.current_url:
                                is_net_file = self._is_network_drive(self.current_url)
                                is_network_url = self.current_url.lower().startswith(
                                    ('http://', 'https://', 'rtsp://', 'rtp://', 'udp://', 'rtmp://'))
                                if not is_net_file and not is_network_url:
                                    self.logger.debug(f"END_FILE错误(本地文件)，不重连: reason={reason}")
                                    self.is_playing = False
                                    self.is_paused = False
                                    self._safe_emit(self.play_state_changed, False)
                                else:
                                    err_str = self._get_mpv_error_string(end_file.error) if hasattr(end_file, 'error') else f"error_code={reason}"
                                    self.logger.warning(f"END_FILE错误，尝试重连: {err_str}, is_net_file={is_net_file}")
                                    self.is_playing = False
                                    self.is_paused = False
                                    self._safe_emit(self.play_state_changed, False)
                                    if self._reconnect_count < self._max_reconnect:
                                        self._reconnect_count += 1
                                        self.logger.info(f"断线自动重连 ({self._reconnect_count}/{self._max_reconnect})")
                                        self._safe_emit(self.reconnect_requested, self.current_url)
                                    else:
                                        self.logger.info("已达最大重连次数，停止重连")
                                        self._reconnect_count = 0
                        elif reason in (MPV_END_FILE_REASON_STOP, MPV_END_FILE_REASON_QUIT):
                            self.logger.debug(f"END_FILE: 正常停止/退出 reason={reason}")
                        else:
                            self.logger.warning(f"END_FILE: 未知reason={reason}")

        except Exception as e:
            self.logger.error(f"处理 mpv 事件失败：{str(e)}")

    def play(self, url, channel_name=None, program_duration=0, **kwargs):
        try:
            if not self._ensure_mpv_initialized():
                self.logger.error("mpv播放器初始化失败，无法播放")
                self._safe_emit(self.play_error, "mpv播放器初始化失败")
                return False

            self.current_url = url
            self._user_stopped = False
            self._switching_channel = True

            reachability = self._check_path_reachability(url)
            if reachability is not None:
                self.logger.warning(f"路径不可达，取消播放: {reachability}")
                self._safe_emit(self.play_error, reachability)
                return False

            if not self.mpv_handle:
                self.logger.error("mpv播放器未初始化")
                self._safe_emit(self.play_error, "mpv播放器未初始化")
                return False

            if self._terminated:
                return False

            # 切换频道前显式停止当前播放，让 mpv 释放 hwdec/D3D11 解码器资源
            # 避免 keep-open=yes + idle=yes 导致旧解码器未释放，新文件 hwdec 初始化失败（黑屏）
            if (self.is_playing or self.is_paused) and not self._user_stopped:
                try:
                    with self._lock:
                        if self.mpv_handle and not self._terminated:
                            _mpv_send_command(self.mpv_handle, ['stop'])
                except Exception as e:
                    self.logger.debug(f"切换前停止旧播放失败: {e}")
                # 重置内部状态，但不发 play_state_changed 信号避免 UI 闪烁
                self.is_playing = False
                self.is_paused = False
                self.media_info = {}
                # 清理可能残留的视频滤镜（flip/crop/360），避免新文件加载时冲突
                try:
                    self.clear_all_video_filters()
                except Exception:
                    pass

            if hasattr(self, 'event_timer') and self.event_timer and not self.event_timer.isActive():
                self.event_timer.start(100)

            if hasattr(self, '_media_info_timer') and self._media_info_timer:
                self._media_info_timer.stop()

            self._media_info_scheduled = False
            self._track_list_logged = False

            self._setup_protocol_options(url, program_duration)

            if hasattr(self, 'audio_visual') and self.audio_visual:
                self.audio_visual.prepare_before_loadfile(url)

            is_vod = 'starttime=' in url.lower() or 'endtime=' in url.lower() or 'playseek' in url.lower()
            if is_vod:
                self._set_mpv_string('prefetch-playlist', 'no')
            else:
                self._set_mpv_string('prefetch-playlist', 'yes')

            mpv_url = self._normalize_url(url)
            with self._lock:
                if not self.mpv_handle or self._terminated:
                    return False
                result = _mpv_send_command(self.mpv_handle, ['loadfile', mpv_url])

            if result < 0:
                error_msg = f"播放失败: {result}"
                self.logger.error(error_msg)
                self._safe_emit(self.play_error, error_msg)
                return False

            self._set_mpv_string('pause', 'no')

            if self._current_speed != 1.0:
                self._set_mpv_string('speed', str(self._current_speed))

            self.is_paused = False

            self._safe_emit(self.play_state_changed, True)

            self._schedule_media_info_start()

            self.logger.debug(f"开始播放: {url}")
            return True
        except Exception as e:
            error_msg = f"播放失败: {str(e)}"
            self.logger.error(error_msg)
            self._safe_emit(self.play_error, error_msg)
            return False

    def play_with_prefetch(self, url, next_urls=None, program_duration=0):
        try:
            self.current_url = url
            self._user_stopped = False
            self._switching_channel = True

            if not self.mpv_handle or self._terminated:
                self._safe_emit(self.play_error, "mpv播放器未初始化")
                return False

            self._setup_protocol_options(url, program_duration)

            is_vod = 'starttime=' in url.lower() or 'endtime=' in url.lower() or 'playseek' in url.lower()
            if is_vod:
                self._set_mpv_string('prefetch-playlist', 'no')
            else:
                self._set_mpv_string('prefetch-playlist', 'yes')

            mpv_url = self._normalize_url(url)
            with self._lock:
                if not self.mpv_handle or self._terminated:
                    return False
                result = _mpv_send_command(self.mpv_handle, ['loadfile', mpv_url])

            if result < 0:
                self.logger.error(f"预取播放失败: {result}")
                return False

            self._set_mpv_string('pause', 'no')
            if self._current_speed != 1.0:
                self._set_mpv_string('speed', str(self._current_speed))

            self.is_paused = False
            self.is_playing = True
            self._safe_emit(self.play_state_changed, True)
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

            with self._lock:
                if self.mpv_handle and not self._terminated:
                    _mpv_send_command(self.mpv_handle, ['stop'])

            if hasattr(self, '_media_info_timer') and self._media_info_timer:
                self._media_info_timer.stop()
            if hasattr(self, '_live_info_timer') and self._live_info_timer:
                self._live_info_timer.stop()

            self.is_playing = False
            self.is_paused = False
            self._safe_emit(self.play_state_changed, False)
            self.current_url = None
            self.media_info = {}

            if hasattr(self, 'event_timer') and self.event_timer:
                self.event_timer.stop()

            if was_playing:
                self.logger.info("停止播放")
            if hasattr(self, 'audio_visual'):
                self.audio_visual.clear_visual()
        except Exception as e:
            self.logger.error(f"停止播放失败: {str(e)}")

    def terminate(self):
        try:
            self._terminated = True
            self.logger.info("正在终止MPV播放器...")

            if is_macos() and hasattr(self.video_widget, 'cleanup'):
                try:
                    self.video_widget.cleanup()
                except Exception:
                    pass

            for timer_attr in ['_media_info_timer', '_live_info_timer', 'event_timer']:
                timer = getattr(self, timer_attr, None)
                if timer:
                    try:
                        timer.stop()
                    except Exception:
                        pass

            with self._lock:
                handle = self.mpv_handle
                self.mpv_handle = None

            if handle:
                try:
                    _mpv_send_command(handle, ['quit'])
                except Exception as e:
                    self.logger.debug(f"发送quit命令失败（可能已关闭）: {e}")

                from PySide6.QtCore import QElapsedTimer
                elapsed = QElapsedTimer()
                elapsed.start()
                while elapsed.elapsed() < 150:
                    from PySide6.QtWidgets import QApplication
                    QApplication.processEvents()
                    with self._lock:
                        if self.mpv_handle is None:
                            break

                try:
                    terminate_destroy_mpv(handle)
                except Exception as e:
                    self.logger.debug(f"销毁mpv handle失败: {e}")

            self.is_playing = False
            self.is_paused = False
            self.current_url = None
            self.media_info = {}

            self.logger.info("MPV播放器已完全终止")
        except Exception as e:
            self.logger.error(f"终止MPV播放器失败: {str(e)}")


    def reinit_for_hdr_change(self, new_hdr_mode):
        try:
            from utils.hdr_detect import clear_hdr_cache
            clear_hdr_cache()
        except Exception:
            pass
        saved_url = self.current_url
        saved_position = 0.0
        was_playing = self.is_playing and not self.is_paused
        if self.mpv_handle:
            try:
                saved_position = self._get_mpv_property_double('time-pos') or 0.0
            except Exception:
                pass
        self.stop()
        for timer_attr in ['_media_info_timer', '_live_info_timer', 'event_timer']:
            timer = getattr(self, timer_attr, None)
            if timer:
                try:
                    timer.stop()
                except Exception:
                    pass
        # 在销毁旧 mpv_handle 前释放 macOS render context，避免 GL 资源泄漏
        if is_macos() and hasattr(self.video_widget, 'cleanup'):
            try:
                self.video_widget.cleanup()
            except Exception as e:
                self.logger.debug(f"HDR切换时清理render context失败: {e}")
        with self._lock:
            handle = self.mpv_handle
            self.mpv_handle = None
        if handle:
            try:
                _mpv_send_command(handle, ['quit'])
            except Exception:
                pass
            with self._lock:
                terminate_destroy_mpv(handle)
        self._mpv_initialized = False
        self._terminated = False
        self._playback_settings['hdr_output_mode'] = new_hdr_mode
        if not self._ensure_mpv_initialized():
            self.logger.error("HDR模式切换后重新初始化mpv失败")
            return
        if saved_url and was_playing:
            self.play(saved_url)
            if saved_position > 0:
                from PySide6.QtCore import QTimer
                pos = saved_position
                def _do_seek():
                    if not self._terminated and self.mpv_handle and self.is_playing:
                        self.send_command(['seek', str(pos), 'absolute'])
                QTimer.singleShot(1500, _do_seek)
        self.logger.info(f"HDR模式已切换为: {new_hdr_mode}")

    def pause(self):
        try:
            if self.mpv_handle and not self._terminated:
                with self._lock:
                    if not self.mpv_handle or self._terminated:
                        return
                    result = _mpv_send_command(self.mpv_handle, ['cycle', 'pause'])
                if result < 0:
                    self.logger.error(f"切换暂停状态失败: {result}")
                    self.is_paused = not self.is_paused
                    self.is_playing = not self.is_paused
                    self._safe_emit(self.play_state_changed, self.is_playing)
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

                    self._safe_emit(self.play_state_changed, self.is_playing)
        except Exception as e:
            self.logger.error(f"暂停播放失败: {str(e)}")

    def set_volume(self, volume):
        try:
            self._last_volume = volume
            if self.mpv_handle and not self._terminated:
                self._set_mpv_string('volume', f"{volume}")
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
            if self.mpv_handle and not self._terminated:
                self._set_mpv_string('mute', 'yes' if muted else 'no')
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
            if self.mpv_handle and not self._terminated and target_seconds >= 0:
                result = self.send_command(['seek', f'{target_seconds:.3f}', 'absolute'])
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
            if self.mpv_handle and not self._terminated:
                duration_seconds = self._get_mpv_property_double('duration')
                if duration_seconds:
                    target_position = duration_seconds * position
                    result = self.send_command(['seek', f'{target_position}', 'absolute'])
                    if result < 0:
                        seek_percent = position * 100.0
                        self.send_command(['seek', f'{seek_percent}', 'absolute-percent'])
                else:
                    seek_percent = position * 100.0
                    self.send_command(['seek', f'{seek_percent}', 'absolute-percent'])
        except Exception as e:
            self.logger.error(f"设置播放位置失败: {str(e)}")

    def seek_relative_seconds(self, seconds):
        try:
            if self.mpv_handle and not self._terminated and seconds != 0:
                result = self.send_command(['seek', f'{seconds:.1f}', 'relative'])
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
            demux_br = get_double('demuxer-bitrate')
            if v_br == 0 and demux_br > 0:
                v_br = demux_br
            a_br = get_double('audio-params/bitrate')
            if v_br == 0 and a_br == 0 and demux_br == 0:
                est_br = get_double('demuxer-cache-state/bytes-per-second') or 0
                if est_br > 0:
                    v_br = est_br

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
                'demuxer_bitrate': demux_br,
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
                'video_depth': get_int('video-params/bits-per-component') or 0,
                'interlaced': get_str('video-params/interlaced') or '',
                'audio_depth': get_int('audio-params/bits-per-sample') or 0,
                'frame_drop_count': get_int('frame-drop-count') or 0,
                'decoder_frame_drop_count': get_int('decoder-frame-drop-count') or 0,
                'mistimed_frame_count': get_int('mistimed-frame-count') or 0,
                'vo_delay': get_double('vo-delayed-frame-count') or 0,
                'cache_size': get_double('demuxer-cache-state/total-bytes') or 0,
                'cache_range_end': get_double('demuxer-cache-state/seeking-ranges/0/end') or 0,
                'video_rotate': get_int('video-params/rotate') or 0,
                'audio_layout': get_str('audio-params/channel-layout') or '',
                'egl_type': get_str('current-vo') or '',
                'current_gpu_api': get_str('current-gpu-api') or '',
                'gpu_context': get_str('gpu-context') or '',
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
        if self._terminated or not self.mpv_handle:
            return

        self._static_info_counter = getattr(self, '_static_info_counter', 0) + 1
        if self._static_info_counter >= self._STATIC_INFO_REFRESH_TICKS:
            self._static_info_counter = 0
            info = self.get_live_media_info()
            if info:
                self._safe_emit(self.live_media_info_updated, info)

        if self.is_playing:
            try:
                current_time = self.get_current_time()
                total_time = self.get_total_time()
                position = self.get_position()

                self._pos_log_count = getattr(self, '_pos_log_count', 0) + 1
                if self._pos_log_count in (1, 2, 3, 5, 10):
                    self.logger.debug(f"[SRC{self._pos_log_count}] total={total_time} cur={current_time} pos={position} url={self.current_url[:60] if self.current_url else 'None'}...")

                self._safe_emit(self.playback_position_updated,
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

        if hasattr(self, '_media_info_timer') and self._media_info_timer:
            self._media_info_timer.stop()
            self._media_info_timer.deleteLater()
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
            # 异步执行截图，避免在 GUI 线程阻塞 mpv 渲染管线导致播放卡顿
            import threading
            handle = self.mpv_handle
            if not handle or self._terminated:
                return
            def _do_screenshot():
                try:
                    from services.mpv_common import send_command as _async_send
                    _async_send(handle, ['screenshot-to-file', filepath, 'video'])
                except Exception:
                    pass
            threading.Thread(target=_do_screenshot, daemon=True).start()
            QTimer.singleShot(1500, lambda: self._check_thumbnail_saved(filepath) if not self._terminated else None)
        except Exception as e:
            self.logger.debug(f"缩略图截取失败: {e}")

    def _check_thumbnail_saved(self, filepath):
        try:
            if self._terminated:
                return
            if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
                self._safe_emit(self.thumbnail_captured, self.current_url)
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
        if self._terminated:
            return None
        with self._lock:
            if not self.mpv_handle:
                return None
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
        if self._terminated:
            return None
        with self._lock:
            if not self.mpv_handle:
                return None
            return _mpv_get_property_int(self.mpv_handle, property_name)

    def _get_mpv_property_double(self, property_name):
        if self._terminated:
            return None
        with self._lock:
            if not self.mpv_handle:
                return None
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
            if not self.mpv_handle or self._terminated:
                return
            self._set_mpv_string('pause', 'no')
            eof = self._get_mpv_property_string('eof-reached')
            if eof and eof.lower() == 'yes':
                self.send_command(['stop'])
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
            if self._terminated or not self.mpv_handle:
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
            if self._terminated or not self.mpv_handle:
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
            if not self.mpv_handle or self._terminated:
                return False
            prop = f'{track_type}-track' if track_type in ('audio', 'sub') else track_type
            current = self.get_current_track(track_type)
            if current is not None and current == track_id:
                return True
            with self._lock:
                if not self.mpv_handle or self._terminated:
                    return False
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

    # ---------- 章节（chapter）API ----------
    def get_chapter_list(self):
        """获取视频内置章节列表
        返回 [{title, time}, ...]，time 为秒（float）
        失败或无章节返回 []
        """
        try:
            if self._terminated or not self.mpv_handle:
                return []
            raw = self._get_mpv_property_string('chapter-list')
            if not raw:
                return []
            import json
            data = json.loads(raw)
            if not isinstance(data, list):
                return []
            result = []
            for i, ch in enumerate(data):
                if not isinstance(ch, dict):
                    continue
                result.append({
                    'id': ch.get('id', i),
                    'title': ch.get('title', '') or '',
                    'time': float(ch.get('time', 0.0) or 0.0),
                })
            return result
        except Exception as e:
            self.logger.debug(f"获取章节列表失败: {e}")
            return []

    def get_chapter_count(self) -> int:
        """获取章节总数"""
        try:
            v = self._get_mpv_property_int('chapter-count')
            if v is None:
                v = self._get_mpv_property_int('chapters')
            return int(v) if v is not None else 0
        except Exception:
            return 0

    def get_current_chapter(self):
        """获取当前章节索引（int），无章节返回 -1"""
        try:
            v = self._get_mpv_property_int('chapter')
            if v is not None:
                return v
            s = self._get_mpv_property_string('chapter')
            if s and s not in ('no', ''):
                try:
                    return int(s)
                except ValueError:
                    return -1
            return -1
        except Exception:
            return -1

    def set_chapter(self, idx: int) -> bool:
        """切换到指定章节（索引从 0 开始）"""
        try:
            if not self.mpv_handle or self._terminated:
                return False
            current = self.get_current_chapter()
            if current is not None and current == idx:
                return True
            with self._lock:
                if not self.mpv_handle or self._terminated:
                    return False
                result = _mpv_set_property_int64(self.mpv_handle, 'chapter', int(idx))
            if result < 0:
                result2 = self._set_mpv_string('chapter', str(idx))
                if result2 < 0:
                    result3 = self.send_command(['set', 'chapter', str(idx)])
                    if result3 == 0:
                        return True
                    self.logger.debug(f"切换章节失败: chapter={idx}, int64={result}, str={result2}, cmd={result3}")
                    return False
            return True
        except Exception as e:
            self.logger.error(f"切换章节失败: {e}")
            return False

    def chapter_next(self) -> bool:
        """跳转到下一章"""
        try:
            if not self.mpv_handle or self._terminated:
                return False
            return self.send_command(['add', 'chapter', '1']) == 0
        except Exception as e:
            self.logger.debug(f"下一章失败: {e}")
            return False

    def chapter_prev(self) -> bool:
        """跳转到上一章"""
        try:
            if not self.mpv_handle or self._terminated:
                return False
            return self.send_command(['add', 'chapter', '-1']) == 0
        except Exception as e:
            self.logger.debug(f"上一章失败: {e}")
            return False

    # ---------- 音视频同步（A/V sync）API ----------
    def get_avdiff(self) -> float:
        """获取音视频时间差（秒，float）
        - 正值表示音频落后于视频
        - 负值表示音频领先于视频
        - 接近 0 表示同步良好
        """
        try:
            v = self._get_mpv_property_double('avdiff')
            return float(v) if v is not None else 0.0
        except Exception:
            return 0.0

    def get_audio_pts(self) -> float:
        """获取音频当前时间戳（秒）"""
        try:
            v = self._get_mpv_property_double('audio-pts')
            return float(v) if v is not None else 0.0
        except Exception:
            return 0.0

    def get_video_pts(self) -> float:
        """获取视频当前时间戳（秒）"""
        try:
            v = self._get_mpv_property_double('video-pts')
            return float(v) if v is not None else 0.0
        except Exception:
            return 0.0

    # ---------- 字幕样式与控制（sub-* 属性） ----------
    def set_sub_delay(self, delay: float) -> bool:
        """设置字幕延迟（秒，可负）"""
        try:
            self._set_mpv_string('sub-delay', f"{delay:.3f}")
            return True
        except Exception as e:
            self.logger.error(f"设置字幕延迟失败: {e}")
            return False

    def get_sub_delay(self) -> float:
        try:
            v = self._get_mpv_property_double('sub-delay')
            return float(v) if v is not None else 0.0
        except Exception:
            return 0.0

    def adjust_sub_delay(self, delta: float) -> float:
        """相对调整字幕延迟，返回新值"""
        new_delay = round(self.get_sub_delay() + delta, 3)
        self.set_sub_delay(new_delay)
        return new_delay

    def set_sub_scale(self, scale: float) -> bool:
        """设置字幕缩放（0.1-10.0）"""
        scale = max(0.1, min(10.0, float(scale)))
        try:
            self._set_mpv_string('sub-scale', f"{scale:.2f}")
            return True
        except Exception as e:
            self.logger.error(f"设置字幕缩放失败: {e}")
            return False

    def get_sub_scale(self) -> float:
        try:
            v = self._get_mpv_property_double('sub-scale')
            return float(v) if v is not None else 1.0
        except Exception:
            return 1.0

    def adjust_sub_scale(self, delta: float) -> float:
        new_scale = round(max(0.1, min(10.0, self.get_sub_scale() + delta)), 2)
        self.set_sub_scale(new_scale)
        return new_scale

    def set_sub_pos(self, pos: int) -> bool:
        """设置字幕垂直位置（0-100，0=顶部，100=底部）"""
        pos = max(0, min(100, int(pos)))
        try:
            self._set_mpv_string('sub-pos', f"{pos}")
            return True
        except Exception as e:
            self.logger.error(f"设置字幕位置失败: {e}")
            return False

    def get_sub_pos(self) -> int:
        try:
            v = self._get_mpv_property_int('sub-pos')
            return int(v) if v is not None else 100
        except Exception:
            return 100

    def set_sub_visibility(self, visible: bool) -> bool:
        try:
            self._set_mpv_string('sub-visibility', 'yes' if visible else 'no')
            return True
        except Exception as e:
            self.logger.error(f"设置字幕可见性失败: {e}")
            return False

    def get_sub_visibility(self) -> bool:
        try:
            v = self._get_mpv_property_string('sub-visibility')
            return v != 'no'
        except Exception:
            return True

    def toggle_sub_visibility(self) -> bool:
        new_state = not self.get_sub_visibility()
        self.set_sub_visibility(new_state)
        return new_state

    def apply_sub_style(self, style: dict) -> bool:
        """应用字幕样式到 mpv 属性
        style 字典支持键:
          color: 字幕颜色（#RRGGBB 或 #AARRGGBB）
          border_color: 边框颜色
          shadow_color: 阴影颜色
          font: 字体名称
          font_size: 字体大小
          border_size: 边框粗细
          shadow_offset: 阴影偏移
          bold/italic: 布尔
          margin_x/margin_y: 边距
          align_x/align_y: 对齐方式
        """
        if not self.mpv_handle or self._terminated:
            return False
        try:
            mapping = {
                'color': 'sub-color',
                'border_color': 'sub-border-color',
                'shadow_color': 'sub-shadow-color',
                'font': 'sub-font',
                'font_size': 'sub-font-size',
                'border_size': 'sub-border-size',
                'shadow_offset': 'sub-shadow-offset',
                'margin_x': 'sub-margin-x',
                'margin_y': 'sub-margin-y',
                'align_x': 'sub-align-x',
                'align_y': 'sub-align-y',
            }
            for key, prop in mapping.items():
                if key in style and style[key] is not None and style[key] != '':
                    self._set_mpv_string(prop, str(style[key]))
            if 'bold' in style:
                self._set_mpv_string('sub-bold', 'yes' if style['bold'] else 'no')
            if 'italic' in style:
                self._set_mpv_string('sub-italic', 'yes' if style['italic'] else 'no')
            return True
        except Exception as e:
            self.logger.error(f"应用字幕样式失败: {e}")
            return False

    def get_sub_style(self) -> dict:
        """读取当前字幕样式"""
        result = {}
        try:
            for key, prop in {
                'color': 'sub-color',
                'border_color': 'sub-border-color',
                'shadow_color': 'sub-shadow-color',
                'font': 'sub-font',
                'font_size': 'sub-font-size',
                'border_size': 'sub-border-size',
                'shadow_offset': 'sub-shadow-offset',
                'margin_x': 'sub-margin-x',
                'margin_y': 'sub-margin-y',
                'align_x': 'sub-align-x',
                'align_y': 'sub-align-y',
            }.items():
                v = self._get_mpv_property_string(prop)
                if v:
                    result[key] = v
            bv = self._get_mpv_property_string('sub-bold')
            result['bold'] = (bv == 'yes')
            iv = self._get_mpv_property_string('sub-italic')
            result['italic'] = (iv == 'yes')
        except Exception:
            pass
        return result

    # ---------- 视频图像调整（brightness/contrast/saturation/hue/gamma/sharpness） ----------
    # mpv 属性取值范围：brightness/contrast/saturation/hue/gamma 为 -100~100
    # sharpness 为 -1.0~1.0；rotate 仅 0/90/180/270；flip 用 vf 滤镜实现
    def set_brightness(self, v: int) -> bool:
        v = max(-100, min(100, int(v)))
        return self._set_mpv_string('brightness', str(v)) >= 0

    def get_brightness(self) -> int:
        v = self._get_mpv_property_int('brightness')
        return int(v) if v is not None else 0

    def set_contrast(self, v: int) -> bool:
        v = max(-100, min(100, int(v)))
        return self._set_mpv_string('contrast', str(v)) >= 0

    def get_contrast(self) -> int:
        v = self._get_mpv_property_int('contrast')
        return int(v) if v is not None else 0

    def set_saturation(self, v: int) -> bool:
        v = max(-100, min(100, int(v)))
        return self._set_mpv_string('saturation', str(v)) >= 0

    def get_saturation(self) -> int:
        v = self._get_mpv_property_int('saturation')
        return int(v) if v is not None else 0

    def set_hue(self, v: int) -> bool:
        v = max(-100, min(100, int(v)))
        return self._set_mpv_string('hue', str(v)) >= 0

    def get_hue(self) -> int:
        v = self._get_mpv_property_int('hue')
        return int(v) if v is not None else 0

    def set_gamma(self, v: int) -> bool:
        v = max(-100, min(100, int(v)))
        return self._set_mpv_string('gamma', str(v)) >= 0

    def get_gamma(self) -> int:
        v = self._get_mpv_property_int('gamma')
        return int(v) if v is not None else 0

    def set_sharpness(self, v: float) -> bool:
        v = max(-1.0, min(1.0, float(v)))
        return self._set_mpv_string('sharpen', f"{v:.3f}") >= 0

    def get_sharpness(self) -> float:
        v = self._get_mpv_property_double('sharpen')
        return float(v) if v is not None else 0.0

    def adjust_video_eq(self, key: str, delta) -> float:
        """相对调整图像参数，返回新值
        key: brightness/contrast/saturation/hue/gamma (int，步进 delta 整数)
              sharpness (float，步进 0.05)
        """
        if key in ('brightness', 'contrast', 'saturation', 'hue', 'gamma'):
            cur = getattr(self, f'get_{key}')()
            new_v = max(-100, min(100, int(cur + delta)))
            getattr(self, f'set_{key}')(new_v)
            return float(new_v)
        elif key == 'sharpness':
            cur = self.get_sharpness()
            new_v = round(max(-1.0, min(1.0, cur + delta)), 3)
            self.set_sharpness(new_v)
            return new_v
        return 0.0

    def apply_video_eq(self, eq: dict) -> bool:
        """批量应用图像参数（dict 可含上述 key 与 video_rotate/video_flip/crop_*）"""
        if not self.mpv_handle or self._terminated:
            return False
        try:
            int_keys = ('brightness', 'contrast', 'saturation', 'hue', 'gamma')
            for k in int_keys:
                if k in eq and eq[k] is not None:
                    getattr(self, f'set_{k}')(eq[k])
            if 'sharpness' in eq and eq['sharpness'] is not None:
                self.set_sharpness(eq['sharpness'])
            if 'video_rotate' in eq and eq['video_rotate'] is not None:
                self.set_video_rotate(int(eq['video_rotate']))
            if 'video_flip' in eq and eq['video_flip']:
                self.set_video_flip(eq['video_flip'])
            if 'crop_w' in eq and 'crop_h' in eq:
                self.set_video_crop(int(eq.get('crop_x', 0)), int(eq.get('crop_y', 0)),
                                    int(eq['crop_w']), int(eq['crop_h']))
            return True
        except Exception as e:
            self.logger.error(f"应用视频参数失败: {e}")
            return False

    def get_video_eq(self) -> dict:
        """读取当前所有视频图像参数"""
        return {
            'brightness': self.get_brightness(),
            'contrast': self.get_contrast(),
            'saturation': self.get_saturation(),
            'hue': self.get_hue(),
            'gamma': self.get_gamma(),
            'sharpness': self.get_sharpness(),
            'video_rotate': self.get_video_rotate(),
        }

    def reset_video_eq(self):
        """重置图像参数为默认（0）"""
        self.set_brightness(0)
        self.set_contrast(0)
        self.set_saturation(0)
        self.set_hue(0)
        self.set_gamma(0)
        self.set_sharpness(0.0)

    # ---------- 画面旋转 / 镜像 / 裁剪（vf 滤镜） ----------
    def set_video_rotate(self, degree: int) -> bool:
        """设置画面旋转（0/90/180/270）"""
        degree = int(degree)
        if degree not in (0, 90, 180, 270):
            degree = 0
        # 通过 video-rotate 属性设置（mpv 0.27+）
        return self._set_mpv_string('video-rotate', str(degree)) >= 0

    def get_video_rotate(self) -> int:
        v = self._get_mpv_property_int('video-rotate')
        return int(v) if v is not None else 0

    def set_video_flip(self, mode: str) -> bool:
        """设置画面翻转
        mode: '' / 'horizontal' / 'vertical' / 'both'
        """
        if not self.mpv_handle or self._terminated:
            return False
        # 通过 vf 滤镜实现；先清除已有 flip 滤镜，再添加新的
        try:
            self.send_command(['vf', 'remove', '@iptv_flip'])
        except Exception:
            pass
        if not mode:
            return True
        if mode == 'horizontal':
            args = ['hflip']
        elif mode == 'vertical':
            args = ['vflip']
        elif mode == 'both':
            args = ['flip', 'y', 'y']  # 二次翻转
        else:
            return False
        # 使用命名标签便于后续替换
        return self.send_command(['vf', 'add', f'@iptv_flip:{",".join(args)}']) == 0

    def get_video_flip(self) -> str:
        """读取当前 flip 状态"""
        try:
            vf = self._get_mpv_property_string('vf')
            if not vf:
                return ''
            import json
            data = json.loads(vf) if isinstance(vf, str) else vf
            for item in data.get('vf', []):
                params = item.get('params', {})
                name = params.get('name', '')
                if name == 'hflip':
                    return 'horizontal'
                if name == 'vflip':
                    return 'vertical'
            return ''
        except Exception:
            return ''

    def set_video_crop(self, x: int, y: int, w: int, h: int) -> bool:
        """设置画面裁剪（x,y 起点；w,h 大小，0 表示使用视频原尺寸）"""
        if not self.mpv_handle or self._terminated:
            return False
        # 清除旧裁剪
        try:
            self.send_command(['vf', 'remove', '@iptv_crop'])
        except Exception:
            pass
        if w <= 0 or h <= 0:
            return True
        # crop=w:h:x:y
        cmd = f"@iptv_crop:crop={w}:{h}:{x}:{y}"
        return self.send_command(['vf', 'add', cmd]) == 0

    def clear_video_crop(self) -> bool:
        """清除画面裁剪"""
        if not self.mpv_handle or self._terminated:
            return False
        try:
            self.send_command(['vf', 'remove', '@iptv_crop'])
            return True
        except Exception:
            return False

    def clear_all_video_filters(self) -> bool:
        """清除所有由本程序添加的视频滤镜"""
        if not self.mpv_handle or self._terminated:
            return False
        for label in ('@iptv_flip', '@iptv_crop', '@iptv_360'):
            try:
                self.send_command(['vf', 'remove', label])
            except Exception:
                pass
        return True

    # ---------- 3D 立体模式 / 360° 视角 ----------
    # mpv video-stereo-mode 取值（简化形式，mpv 会自动识别）：
    #   mono / sbs / sbs2 / ab / ab2
    # 对应：普通2D / 左右并排-左前 / 左右并排-右前 / 上下-上前 / 上下-下前
    _STEREO_MODES = ('mono', 'sbs', 'sbs2', 'ab', 'ab2')

    def set_video_stereo_mode(self, mode: str) -> bool:
        """设置 3D 立体显示模式
        mode: 'mono' / 'sbs' / 'sbs2' / 'ab' / 'ab2'
        """
        if not self.mpv_handle or self._terminated:
            return False
        if mode not in self._STEREO_MODES:
            mode = 'mono'
        return self._set_mpv_string('video-stereo-mode', mode) >= 0

    def get_video_stereo_mode(self) -> str:
        """读取当前 3D 立体模式"""
        v = self._get_mpv_property_string('video-stereo-mode')
        if v and v in self._STEREO_MODES:
            return v
        return 'mono'

    # 360° 视频视角控制：通过 lavfi panorama 滤镜
    # 滤镜参数：e=投影方式（flat/equirect/cubemap/sg）, yaw=偏航, pitch=俯仰, roll=滚转
    # 注意：panorama 滤镜要求 ffmpeg 编译时启用，可能不可用
    _360_PROJECTIONS = ('flat', 'equirect', 'cubemap')

    def set_360_view(self, yaw: float, pitch: float, roll: float,
                     projection: str = 'equirect') -> bool:
        """设置 360° 视频视角
        yaw:   -180~180 度（偏航）
        pitch:  -90~ 90 度（俯仰）
        roll:  -180~180 度（滚转）
        projection: 'flat' / 'equirect' / 'cubemap'
        返回成功与否；滤镜不可用时返回 False
        """
        if not self.mpv_handle or self._terminated:
            return False
        if projection not in self._360_PROJECTIONS:
            projection = 'equirect'
        yaw = max(-180.0, min(180.0, float(yaw)))
        pitch = max(-90.0, min(90.0, float(pitch)))
        roll = max(-180.0, min(180.0, float(roll)))
        # 移除旧滤镜
        try:
            self.send_command(['vf', 'remove', '@iptv_360'])
        except Exception:
            pass
        # 全 0 视角等同于无滤镜
        if yaw == 0.0 and pitch == 0.0 and roll == 0.0:
            return True
        # 构建 lavfi panorama 滤镜
        cmd = (f"@iptv_360:lavfi=[panorama=e={projection}:"
               f"yaw={yaw:.3f}:pitch={pitch:.3f}:roll={roll:.3f}]")
        return self.send_command(['vf', 'add', cmd]) == 0

    def clear_360_filter(self) -> bool:
        """清除 360° 视角滤镜"""
        if not self.mpv_handle or self._terminated:
            return False
        try:
            self.send_command(['vf', 'remove', '@iptv_360'])
            return True
        except Exception:
            return False

    def get_360_view(self) -> dict:
        """读取当前 360° 视角设置
        返回 {'yaw','pitch','roll','projection','active'}；滤镜不可用时 active=False
        """
        result = {'yaw': 0.0, 'pitch': 0.0, 'roll': 0.0,
                  'projection': 'equirect', 'active': False}
        if not self.mpv_handle or self._terminated:
            return result
        try:
            import re
            vf = self._get_mpv_property_string('vf')
            if not vf:
                return result
            import json
            data = json.loads(vf) if isinstance(vf, str) else vf
            for item in data.get('vf', []):
                params = item.get('params', {})
                label = params.get('@label', '') or item.get('label', '')
                if label != '@iptv_360':
                    continue
                # lavfi 滤镜的 params 通常含 'graph' 字段
                graph = params.get('graph', '') or params.get('lavfi', '')
                if not graph:
                    continue
                m = re.search(r'e=(\w+)', graph)
                if m:
                    result['projection'] = m.group(1)
                m = re.search(r'yaw=(-?[\d.]+)', graph)
                if m:
                    result['yaw'] = float(m.group(1))
                m = re.search(r'pitch=(-?[\d.]+)', graph)
                if m:
                    result['pitch'] = float(m.group(1))
                m = re.search(r'roll=(-?[\d.]+)', graph)
                if m:
                    result['roll'] = float(m.group(1))
                result['active'] = True
                break
        except Exception:
            pass
        return result

    # ---------- 音频系统增强（audio-delay/device/channels/pitch/equalizer） ----------
    # mpv 属性取值范围：audio-delay 秒（-10~10，默认 0）；audio-pitch-correction 0.0~2.0（1.0=正常）
    # audio-channels 字符串（auto/mono/1.0/2.0/2.1/5.1/7.1 等）；audio-device 字符串
    # 均衡器通过 af 滤镜 equalizer=g1:g2:...:g10 实现（10 频段，-12~+12 dB）
    EQ_BANDS = (60, 170, 310, 600, 1000, 3000, 6000, 12000, 14000, 16000)
    EQ_LABELS = ('60Hz', '170Hz', '310Hz', '600Hz', '1kHz', '3kHz', '6kHz', '12kHz', '14kHz', '16kHz')

    def set_audio_delay(self, v: float) -> bool:
        v = max(-10.0, min(10.0, float(v)))
        return self._set_mpv_string('audio-delay', f"{v:.3f}") >= 0

    def get_audio_delay(self) -> float:
        v = self._get_mpv_property_double('audio-delay')
        return float(v) if v is not None else 0.0

    def adjust_audio_delay(self, delta: float) -> float:
        cur = self.get_audio_delay()
        new_v = round(max(-10.0, min(10.0, cur + delta)), 3)
        self.set_audio_delay(new_v)
        return new_v

    def set_audio_device(self, name: str) -> bool:
        if not name:
            return False
        return self._set_mpv_string('audio-device', name) >= 0

    def get_audio_device(self) -> str:
        return self._get_mpv_property_string('audio-device') or ''

    def get_audio_device_list(self) -> list:
        """返回音频设备列表，每项为 dict(name, description)"""
        try:
            raw = self._get_mpv_property_string('audio-device-list')
            if not raw:
                return []
            import json
            data = json.loads(raw) if isinstance(raw, str) else raw
            result = []
            for item in data:
                name = item.get('name', '')
                desc = item.get('description', '')
                if name:
                    result.append({'name': name, 'description': desc or name})
            return result
        except Exception:
            return []

    def set_audio_channels(self, ch: str) -> bool:
        """设置音频声道布局（auto/mono/1.0/2.0/2.1/3.0/4.0/5.0/5.1/6.0/6.1/7.0/7.1）"""
        if not ch:
            return False
        return self._set_mpv_string('audio-channels', ch) >= 0

    def get_audio_channels(self) -> str:
        return self._get_mpv_property_string('audio-channels') or 'auto'

    def set_audio_pitch(self, v: float) -> bool:
        """设置音调补偿（0.0~2.0，1.0=正常）"""
        v = max(0.0, min(2.0, float(v)))
        return self._set_mpv_string('audio-pitch-correction', f"{v:.3f}") >= 0

    def get_audio_pitch(self) -> float:
        v = self._get_mpv_property_double('audio-pitch-correction')
        return float(v) if v is not None else 1.0

    def adjust_audio_pitch(self, delta: float) -> float:
        cur = self.get_audio_pitch()
        new_v = round(max(0.0, min(2.0, cur + delta)), 3)
        self.set_audio_pitch(new_v)
        return new_v

    def set_audio_eq_band(self, band_index: int, gain_db: float) -> bool:
        """设置均衡器指定频段的增益（band_index 0-9，gain -12~+12 dB）"""
        if not (0 <= band_index < 10):
            return False
        eq = self.get_audio_eq()
        eq[band_index] = max(-12.0, min(12.0, float(gain_db)))
        return self._apply_audio_eq_filter(eq)

    def set_audio_eq(self, gains: list) -> bool:
        """设置完整均衡器（gains 长度 10，每项 -12~+12 dB）"""
        if not gains or len(gains) != 10:
            return False
        eq = [max(-12.0, min(12.0, float(g))) for g in gains]
        return self._apply_audio_eq_filter(eq)

    def get_audio_eq(self) -> list:
        """读取当前均衡器增益列表（长度 10）。无法读取时返回全 0"""
        try:
            af = self._get_mpv_property_string('af')
            if not af:
                return [0.0] * 10
            import json
            data = json.loads(af) if isinstance(af, str) else af
            for item in data.get('af', []):
                params = item.get('params', {})
                if params.get('name') == 'equalizer':
                    raw = params.get('params', '') or ''
                    # 格式可能是 "g1:g2:...:g10" 或 dict
                    if isinstance(raw, str) and raw:
                        parts = raw.split(':')
                        if len(parts) == 10:
                            return [max(-12.0, min(12.0, float(p))) for p in parts]
                    break
        except Exception:
            pass
        return [0.0] * 10

    def _apply_audio_eq_filter(self, gains: list) -> bool:
        """内部：应用均衡器 af 滤镜"""
        if not self.mpv_handle or self._terminated:
            return False
        # 先移除已有的 eq 滤镜
        try:
            self.send_command(['af', 'remove', '@iptv_eq'])
        except Exception:
            pass
        # 全为 0 时不再添加
        if all(abs(g) < 0.01 for g in gains):
            return True
        cmd = "@iptv_eq:equalizer=" + ":".join(f"{g:.1f}" for g in gains)
        return self.send_command(['af', 'add', cmd]) == 0

    def apply_audio_eq(self, settings: dict) -> bool:
        """批量应用音频参数
        dict 可含：audio_delay, audio_channels, audio_pitch, audio_device, eq(列表)
        """
        if not self.mpv_handle or self._terminated:
            return False
        try:
            if 'audio_delay' in settings and settings['audio_delay'] is not None:
                self.set_audio_delay(float(settings['audio_delay']))
            if 'audio_pitch' in settings and settings['audio_pitch'] is not None:
                self.set_audio_pitch(float(settings['audio_pitch']))
            if 'audio_channels' in settings and settings['audio_channels']:
                self.set_audio_channels(str(settings['audio_channels']))
            if 'audio_device' in settings and settings['audio_device']:
                self.set_audio_device(str(settings['audio_device']))
            if 'eq' in settings and settings['eq'] is not None:
                self.set_audio_eq(list(settings['eq']))
            return True
        except Exception as e:
            self.logger.error(f"应用音频参数失败: {e}")
            return False

    def get_audio_eq_all(self) -> dict:
        """读取所有音频参数"""
        return {
            'audio_delay': self.get_audio_delay(),
            'audio_channels': self.get_audio_channels(),
            'audio_pitch': self.get_audio_pitch(),
            'audio_device': self.get_audio_device(),
            'eq': self.get_audio_eq(),
        }

    def reset_audio_eq(self):
        """重置音频参数为默认"""
        self.set_audio_delay(0.0)
        self.set_audio_pitch(1.0)
        self.set_audio_channels('auto')
        # 清除均衡器滤镜
        try:
            self.send_command(['af', 'remove', '@iptv_eq'])
        except Exception:
            pass

    # ---------- 播放列表控制（loop-file / ab-loop / frame-step） ----------
    def set_loop_file(self, mode: str) -> bool:
        """设置单文件循环模式
        mode: 'no' / 'inf' / 'yes' 或 'once'
        """
        if mode not in ('no', 'inf', 'yes', 'once'):
            mode = 'no'
        if mode == 'once':
            mode = '1'
        return self._set_mpv_string('loop-file', mode) >= 0

    def get_loop_file(self) -> str:
        return self._get_mpv_property_string('loop-file') or 'no'

    def set_loop_playlist(self, mode: str) -> bool:
        """设置播放列表循环模式（'no' / 'inf' / 'force'）"""
        if mode not in ('no', 'inf', 'force'):
            mode = 'no'
        return self._set_mpv_string('loop-playlist', mode) >= 0

    def get_loop_playlist(self) -> str:
        return self._get_mpv_property_string('loop-playlist') or 'no'

    # AB 循环：利用 mpv 原生 ab-loop-a / ab-loop-b 属性
    def ab_loop_set_a(self) -> float:
        """将当前位置设为 A 点，返回 A 点时间（秒）"""
        pos = self._get_mpv_property_double('time-pos')
        if pos is None:
            pos = 0.0
        self._set_mpv_string('ab-loop-a', f"{pos:.3f}")
        return float(pos)

    def ab_loop_set_b(self) -> float:
        """将当前位置设为 B 点，返回 B 点时间（秒）"""
        pos = self._get_mpv_property_double('time-pos')
        if pos is None:
            pos = 0.0
        self._set_mpv_string('ab-loop-b', f"{pos:.3f}")
        return float(pos)

    def ab_loop_clear(self) -> bool:
        """清除 AB 循环"""
        ok1 = self._set_mpv_string('ab-loop-a', 'no') >= 0
        ok2 = self._set_mpv_string('ab-loop-b', 'no') >= 0
        return ok1 and ok2

    def ab_loop_get_status(self) -> dict:
        """读取 AB 循环状态"""
        a = self._get_mpv_property_double('ab-loop-a')
        b = self._get_mpv_property_double('ab-loop-b')
        # mpv 中 'no' 通常返回 None 或字符串 'no'
        a_val = None if (a is None or a == 'no') else float(a)
        b_val = None if (b is None or b == 'no') else float(b)
        return {
            'a': a_val,
            'b': b_val,
            'active': a_val is not None and b_val is not None,
        }

    # 逐帧播放
    def frame_step(self) -> bool:
        """前进一帧（mpv 会自动暂停）"""
        return self.send_command(['frame-step']) == 0

    def frame_back_step(self) -> bool:
        """后退一帧"""
        return self.send_command(['frame-back-step']) == 0

    # ---------- 网络流媒体增强（Referer / 代理） ----------
    def set_http_referer(self, referer: str) -> bool:
        """设置 HTTP Referer（运行时生效，对下次 loadfile 起作用）"""
        try:
            self._playback_settings['http_referer'] = referer or ''
            return self._set_mpv_string('referrer', referer or '') >= 0
        except Exception as e:
            self.logger.debug(f"设置 Referer 失败: {e}")
            return False

    def get_http_referer(self) -> str:
        try:
            return self._playback_settings.get('http_referer', '') or ''
        except Exception:
            return ''

    def set_http_proxy(self, proxy: str) -> bool:
        """设置 HTTP/HTTPS 代理（运行时生效，对下次 loadfile 起作用）
        支持格式：
          http://host:port
          https://host:port
          socks5://host:port
          socks5h://host:port
        """
        try:
            self._playback_settings['http_proxy'] = proxy or ''
            return self._set_mpv_string('http-proxy', proxy or '') >= 0
        except Exception as e:
            self.logger.debug(f"设置 HTTP 代理失败: {e}")
            return False

    def get_http_proxy(self) -> str:
        try:
            return self._playback_settings.get('http_proxy', '') or ''
        except Exception:
            return ''

    def set_property_string(self, name, value):
        self._set_mpv_string(name, value)

    def send_command(self, cmd_args):
        if self._terminated:
            return -1
        with self._lock:
            if not self.mpv_handle:
                return -1
            return _mpv_send_command(self.mpv_handle, cmd_args)

    def show_osd(self, text: str, duration: int = 3000):
        self.send_command(['show-text', text, str(duration)])

    def _apply_osd_colors(self):
        if not self.mpv_handle or self._terminated:
            return
        try:
            from ui.styles import AppStyles
            colors = AppStyles._get_colors()
            osd_fg = colors.get('osd_text', '#ffffff')
            osd_border = colors.get('osd_border', '#000000')
            osd_shadow = colors.get('osd_shadow', '#000000')
            self._set_mpv_string('osd-color', osd_fg)
            self._set_mpv_string('osd-border-color', osd_border)
            self._set_mpv_string('osd-shadow-color', osd_shadow)
            font_family = colors.get('font_family', "'Segoe UI', 'Microsoft YaHei', sans-serif")
            mpv_font = font_family.split(",")[0].strip("' \"")
            self._set_mpv_string('osd-font', mpv_font)
        except Exception:
            pass

    def update_osd_theme(self):
        self._apply_osd_colors()

    @staticmethod
    def detect_hdr_type(colormatrix: str, gamma: str, sig_peak: float, video_format: str = '') -> str:
        vf_lower = (video_format or '').lower()
        if 'dovi' in vf_lower or 'dolbyvision' in vf_lower or 'dolby_vision' in vf_lower:
            return 'DV'
        if gamma and ('pq' in gamma.lower() or 'smpte2084' in gamma.lower()):
            if sig_peak > 1000:
                return 'HDR10+'
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
        return 'SDR'

    def get_available_seek_range(self) -> dict:
        empty = {'max_back': 0, 'max_forward': 0, 'cache_duration': 0,
                 'buffer_start': 0, 'buffer_end': 0, 'time_pos': 0}
        if self._terminated or not self.mpv_handle:
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
