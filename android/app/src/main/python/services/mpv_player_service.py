import os
import time
import ctypes
import threading
from PySide6.QtCore import QObject, Signal, QTimer
from core.log_manager import global_logger
from utils.platform_utils import is_windows, is_macos, is_linux, is_android, get_android_data_dir
from services.mpv_common import (
    mpv_event,
    mpv_event_end_file,
    mpv_event_property,
    mpv_event_log_message,
    MPV_EVENT_NONE,
    MPV_EVENT_END_FILE,
    MPV_EVENT_FILE_LOADED,
    MPV_EVENT_PROPERTY_CHANGE,
    MPV_EVENT_LOG_MESSAGE,
    MPV_FORMAT_STRING,
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
    get_property_node as _mpv_get_property_node,
)

from services.mpv_common import _ensure_env_initialized

try:
    _ensure_env_initialized()
    import mpv
except ImportError as _e:
    import logging as _logging
    _logging.getLogger('services.mpv_player_service').warning(
        f"python-mpv 模块导入失败（非致命，libmpv 直接调用仍可用）: {_e}"
    )
    mpv = None
except Exception as _e:
    import logging as _logging
    _logging.getLogger('services.mpv_player_service').warning(
        f"python-mpv 模块导入异常: {_e}"
    )
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

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


def _load_playback_settings():
    settings = {
        'hwdec': 'auto-copy',
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
        # 高级播放器参数（与安卓端 PlayerSettingsPanel 对齐）
        'vo': 'auto',
        'gpu_api': 'auto',
        'video_sync': 'audio',
        'framedrop': 'vo',
        'cache_secs_override': 0,
        'demuxer_readahead_secs_override': 0,
        'demuxer_max_bytes_mib_override': 0,
        'deinterlace': 'no',
        'probesize_override': 0,
        'analyzeduration_override': 0,
    }
    try:
        from core.config_manager import ConfigManager
        config = ConfigManager()
        s = config.load_playback_settings()
        settings.update(s)
    except Exception as e:
        import logging as _logging
        _logging.getLogger('services.mpv_player_service').warning(
            f"加载播放设置失败，使用默认值: {e}"
        )
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
        # 当前画面比例（'default'/'16:9'/'4:3'/'stretch'/'fill'/'crop'）
        # set_aspect_ratio 写入，get_aspect_ratio 读出
        self._current_aspect_ratio = 'default'
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
                error_msg = getattr(_mpv_mod, '_last_load_error', '') or "libmpv加载失败"
                self.logger.error(error_msg)
                self._safe_emit(self.play_error, error_msg)
                return False

            if not _mpv_mod.MPV_AVAILABLE or _mpv_mod.libmpv is None:
                error_msg = getattr(_mpv_mod, '_last_load_error', '') or "libmpv加载失败"
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
                except Exception as _e:
                    global_logger.debug(f"unexpected error: {_e}")

            if not _skip_wid:
                try:
                    from PySide6.QtWidgets import QApplication
                    QApplication.processEvents()
                except Exception as _e:
                    global_logger.debug(f"unexpected error: {_e}")

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

            try:
                if is_windows():
                    from utils.hdr_detect import is_windows_hdr_enabled
                    _system_hdr_enabled = is_windows_hdr_enabled()
                elif is_macos():
                    from utils.hdr_detect import is_macos_hdr_enabled
                    _system_hdr_enabled = is_macos_hdr_enabled()
                elif is_android():
                    from utils.hdr_detect import is_android_hdr_enabled
                    _system_hdr_enabled = is_android_hdr_enabled()
                elif is_linux():
                    from utils.hdr_detect import is_linux_hdr_enabled
                    _system_hdr_enabled = is_linux_hdr_enabled()
                else:
                    _system_hdr_enabled = False
            except Exception as e:
                self.logger.warning(f"HDR检测失败，保守使用SDR模式: {e}")
                _system_hdr_enabled = False  # noqa: F841

            self._hdr_fallback_tonemap = False
            # vo 推导：auto 时始终使用 gpu-next（支持 HDR 和 SDR，gpu 不支持 HDR 信号输出）。
            # 这样无论用户启动时选什么 HDR 模式，运行时切换到 passthrough/scrgb 时，
            # vo 已经是 gpu-next，配合 target-colorspace-hint=yes 可以动态切换 swapchain。
            user_vo = str(self._playback_settings.get('vo', 'auto')).lower()
            if user_vo not in ('auto', 'gpu', 'gpu-next', 'libmpv', 'direct3d'):
                user_vo = 'auto'
            if user_vo == 'auto':
                vo = 'gpu-next'
            else:
                vo = user_vo
                if hdr_mode in ('passthrough', 'scrgb', 'auto') and vo != 'gpu-next':
                    self.logger.warning(
                        f"HDR模式({hdr_mode})建议使用gpu-next，但用户选了vo={vo}，HDR信号可能异常"
                    )

            # gpu-api和gpu-context必须在vo之前设置
            # 否则mpv内部锁定渲染后端后，gpu-context设置会被拒绝(错误码-7)
            # 第三阶段：支持 Vulkan GPU API，可在某些 GPU 上获得更好的性能
            gpu_api = str(self._playback_settings.get('gpu_api', 'auto')).lower()
            if is_windows():
                if gpu_api == 'vulkan':
                    _mpv_set_option_string(self.mpv_handle, 'gpu-api', 'vulkan')
                    _mpv_set_option_string(self.mpv_handle, 'gpu-context', 'win')
                    self.logger.info("使用 Vulkan GPU API（用户配置）")
                else:
                    _mpv_set_option_string(self.mpv_handle, 'gpu-api', 'd3d11')
                    _mpv_set_option_string(self.mpv_handle, 'd3d11-sync-interval', '1')
                # d3d11-output-csp 控制 swapchain 的初始色彩空间和底层 DXGI 格式：
                # - srgb → R8G8B8A8_UNORM（仅支持 sRGB，运行时无法切换到 PQ）
                # - pq   → R10G10B10A2_UNORM（支持 PQ 和 sRGB 之间动态切换）
                # - auto → 根据初始 target-trc 选择（默认 auto 时通常选 sRGB）
                #
                # 根因：d3d11-output-csp=auto 在初始化时创建了 R8G8B8A8_UNORM 格式的 swapchain，
                # 此格式不支持 PQ 色彩空间。运行时设置 target-trc=pq 后，target-colorspace-hint=yes
                # 会让 mpv 调用 SetColorSpace1 尝试切换到 PQ，但 R8G8B8A8_UNORM 格式不支持 PQ，
                # 切换失败，PQ 信号在 sRGB swapchain 上显示为极暗画面（用户反馈的"HDR直通画面暗"）。
                #
                # 修复：对于 HDR 模式（passthrough/scrgb/auto），设置 d3d11-output-csp=pq，
                # 让 mpv 创建 R10G10B10A2_UNORM 格式的 swapchain，运行时可通过 SetColorSpace1
                # 在 PQ 和 sRGB 之间动态切换。reinit_for_hdr_change() 切换 HDR 模式时会重新
                # 初始化 mpv，所以根据新的 hdr_mode 设置正确的 d3d11-output-csp。
                # 对于 tonemap/disable 模式，使用 srgb 即可。
                #
                # 注意：Windows 显示合成器总是支持 HDR 交换链（即使显示器是 SDR），
                # 所以 d3d11-output-csp=pq 能成功创建 swapchain。当系统 HDR 未启用时，
                # _apply_hdr_on_file_loaded() 会回退到 tonemap（target-trc=srgb），
                # target-colorspace-hint=yes 会让 mpv 将 swapchain 切换回 sRGB。
                if hdr_mode in ('passthrough', 'scrgb', 'auto'):
                    _mpv_set_option_string(self.mpv_handle, 'd3d11-output-csp', 'pq')
                else:
                    _mpv_set_option_string(self.mpv_handle, 'd3d11-output-csp', 'srgb')
                _mpv_set_option_string(self.mpv_handle, 'target-colorspace-hint', 'yes')
            elif is_macos():
                # macOS上mpv v0.41+的gpu-context选项不再支持wid嵌入
                # 使用vo=libmpv + render API渲染到QOpenGLWidget（IINA等播放器的标准方案）
                # 注意：即使用户在订阅设置中选了 gpu/gpu-next，macOS 也强制走 libmpv，
                # 因为 wid 嵌入在 mpv v0.41+ 已失效。这里日志提示用户其选择被覆盖。
                if vo != 'libmpv':
                    self.logger.info(
                        f"macOS: 用户选择的vo={vo}被覆盖为libmpv（mpv v0.41+不再支持wid嵌入）"
                    )
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
            # 硬解模式：auto-copy（默认，copy-back 保证 vf 滤镜可用）/ auto（原生，最快但滤镜受限）/ no（软解）
            # 兼容旧配置：bool True→auto-copy，False→no；字符串 'True'/'False' 同样处理
            hwdec_raw = self._playback_settings.get('hwdec', 'auto-copy')
            if isinstance(hwdec_raw, bool):
                hwdec = 'auto-copy' if hwdec_raw else 'no'
            else:
                hwdec_str = str(hwdec_raw).lower()
                if hwdec_str in ('auto', 'auto-copy', 'no'):
                    hwdec = hwdec_str
                elif hwdec_str in ('true', '1', 'yes'):
                    hwdec = 'auto-copy'  # 旧 bool True 升级到 auto-copy，保证滤镜可用
                else:
                    hwdec = 'no'
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
            # 按模块设置日志级别。默认只投递 warn 及以上，避免 debug 日志在 UI 线程
            # 被 100ms 的 _process_events 定时器批量解码转发导致播放卡顿
            # （demuxer/vd/ad/hwdec 的 debug 日志在播放期间会持续大量生成）。
            # 需要诊断编解码/探测问题时，设置环境变量 MPV_DEBUG_LOG=1 开启 debug 日志。
            # 注意：还需调用 mpv_request_log_messages 才能让 MPV_EVENT_LOG_MESSAGE
            # 事件被投递到事件队列，否则日志永远不会输出。
            if os.environ.get('MPV_DEBUG_LOG', '0') == '1':
                _mpv_set_property_string(
                    self.mpv_handle, 'msg-level',
                    'all=fatal,demuxer=debug,vd=debug,ad=debug,hwdec=debug'
                )
                _log_request_level = b'debug'
            else:
                _mpv_set_property_string(self.mpv_handle, 'msg-level', 'all=fatal')
                _log_request_level = b'warn'
            try:
                # 必须通过 _mpv_mod.libmpv 访问，不能用模块级导入的 libmpv
                # （模块级导入时 libmpv 是 None，_ensure_libmpv_loaded() 后才被赋值）
                _mpv_mod.libmpv.mpv_request_log_messages(self.mpv_handle, _log_request_level)
            except Exception as _e:
                self.logger.debug(f"mpv_request_log_messages 调用失败: {_e}")
            _mpv_set_property_string(self.mpv_handle, 'no-window-dragging', 'yes')
            _mpv_set_property_string(self.mpv_handle, 'window-scale', '1.0')
            _mpv_set_property_string(self.mpv_handle, 'border', 'no')

            _mpv_set_property_string(self.mpv_handle, 'keep-open', 'yes')
            _mpv_set_property_string(self.mpv_handle, 'idle', 'yes')
            _mpv_set_property_string(self.mpv_handle, 'ytdl', 'no')

            # mpv 新版废弃 video-aspect-override=-1，需用 'no' + video-aspect-mode=container
            _mpv_set_property_string(self.mpv_handle, 'video-aspect-override', 'no')
            _mpv_set_property_string(self.mpv_handle, 'video-aspect-mode', 'container')
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
            # - framedrop：视频输出慢时丢帧策略，默认 vo（VO 慢时丢帧），用户可配置
            # - cache-pause-initial=no：初始缓存阶段不暂停，避免直播流启动卡顿
            # - video-sync：音画同步基准，默认 audio（以音频时钟为基准），用户可配置
            framedrop_raw = str(self._playback_settings.get('framedrop', 'vo')).lower()
            if framedrop_raw not in ('vo', 'decoder', 'insert', 'none', 'never'):
                framedrop_raw = 'vo'
            _mpv_set_property_string(self.mpv_handle, 'framedrop', framedrop_raw)
            _mpv_set_property_string(self.mpv_handle, 'cache-pause-initial', 'no')
            video_sync_raw = str(self._playback_settings.get('video_sync', 'audio')).lower()
            if video_sync_raw not in ('audio', 'display-resample', 'display-tempo', 'resample',
                                      'display-desync', 'desync'):
                video_sync_raw = 'audio'
            _mpv_set_property_string(self.mpv_handle, 'video-sync', video_sync_raw)

            # 反交错：使用 yadif=mode=1 (bob) vf 滤镜代替 mpv 的 deinterlace 属性
            # 原因：deinterlace=yes 内部用 yadif mode=0（frame mode），50i→25p 帧率减半，运动卡顿
            # yadif=mode=1 (field/bob mode) 输出 50i→50p，保持运动流畅同时消除梳齿条纹
            deinterlace_raw = str(self._playback_settings.get('deinterlace', 'no')).lower()
            if deinterlace_raw not in ('yes', 'no', 'auto'):
                deinterlace_raw = 'no'
            if deinterlace_raw in ('yes', 'auto'):
                self._enable_deinterlace_filter()

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
                _tpk = self._get_mpv_property_string('target-peak') or '?'
                _gmm = self._get_mpv_property_string('gamut-mapping-mode') or '?'
                self.logger.info(
                    f"HDR诊断: vo={_vo}, gpu-api={_ga}, gpu-context={_gc}, "
                    f"target-prim={_tp}, target-trc={_tt}, tone-mapping={_tm}, "
                    f"target-colorspace-hint={_tch}, d3d11-output-csp={_csp}, "
                    f"target-peak={_tpk}, gamut-mapping-mode={_gmm}, "
                    f"hdr_mode={hdr_mode}"
                )
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

    def _get_sdr_target_trc(self):
        """获取当前系统下 SDR 输出的正确 target-trc。

        Windows HDR 模式下桌面运行在 sRGB 线性空间，
        SDR 内容（包括 tonemap 后的 HDR 内容）需用 srgb gamma
        才能正确显示，否则会偏灰偏暗。
        """
        try:
            if is_windows():
                from utils.hdr_detect import is_windows_hdr_enabled
                if is_windows_hdr_enabled():
                    return 'srgb'
        except Exception as _e:
            global_logger.debug(f"unexpected error: {_e}")
        return 'bt.1886'

    def _apply_tonemap_config(self, is_hlg=False):
        # HDR→SDR 色调映射（与 Android 端 applyTonemapConfig 统一策略）：
        # 显式指定目标色域和 gamma，避免 mpv 自动推断失败
        # 统一策略：target-prim=bt.2020 保留广色域（WCG），在支持广色域的显示器上显示更丰富色彩
        # gamut-mapping-mode=perceptual 感知映射，减少色域裁剪损失
        # 注意：d3d11-output-csp 和 target-colorspace-hint 已在初始化时设置（option），
        # 运行时修改不会重建 swapchain，所以这里不再设置。
        # 重置 target-peak：passthrough/scrgb 模式设置了 10000，切换到 tonemap 时必须重置，
        # 否则 mpv 认为显示器能显示 10000 nits，不会做 HDR→SDR tone mapping，画面会过曝。
        # 注意：hdr10-opt 由 _apply_hdr_on_file_loaded 根据视频类型统一设置，这里不再设置。
        sdr_trc = self._get_sdr_target_trc()
        # HLG 视频去饱和度降为 0，避免整体发灰
        # PQ 视频保留 0.5 的去饱和度，防止高光过饱和
        desat = '0' if is_hlg else '0.5'
        if is_hlg:
            # HLG 是相对编码，不像 PQ/HDR10 携带绝对亮度元数据（maxCLL/maxFALL）。
            # hdr-compute-peak=no 时 mpv 用 HLG 信号峰值（1.0≈参考白 1000 nits），
            # 对 target-peak=100 做 10:1 压缩，导致画面偏暗。
            # hdr-compute-peak=yes 让 mpv 从实际帧内容动态计算场景峰值，
            # 典型 HLG 广播实际峰值远低于 1000 nits（通常 200-500 nits），
            # 压缩比更小、画面更亮更自然。
            # tone-mapping=bt.2390：ITU-R BT.2390 专为 HLG/HDR10 设计的色调映射标准，
            # 软膝滚降保留更多中间调亮度，比 auto/spline 更适合 HLG。
            self._set_mpv_string('tone-mapping', 'bt.2390')
            self._set_mpv_string('hdr-compute-peak', 'yes')
        else:
            self._set_mpv_string('tone-mapping', 'auto')
            self._set_mpv_string('hdr-compute-peak', 'no')
        self._set_mpv_string('tone-mapping-mode', 'auto')
        self._set_mpv_string('tone-mapping-desat', desat)
        self._set_mpv_string('target-prim', 'bt.2020')
        self._set_mpv_string('target-trc', sdr_trc)
        # target-peak=100：显式 SDR 电平，确保 swapchain 切换到 sRGB 色彩空间
        self._set_mpv_string('target-peak', '100')
        self._set_mpv_string('gamut-mapping-mode', 'perceptual')
        self.logger.info(
            f"HDR配置: tonemap → SDR (bt.2020/{sdr_trc}, target-peak=100, "
            f"gamut=perceptual, desat={desat}{' [HLG]' if is_hlg else ''})"
        )

    def _apply_passthrough_config(self, is_pq=True):
        # d3d11-output-csp=pq + target-colorspace-hint=yes 已在初始化时设置
        #
        # PQ 视频（HDR10/HDR10+）：
        #   target-peak=10000 是 HDR 直通的关键：告诉 mpv 显示器能处理 10000 nits，
        #   mpv 不会做 tone mapping（target-peak=10000 同 hdr-compute-peak 矛盾，自动关闭），
        #   而是直接输出 PQ 信号让显示器/Windows 合成器处理。
        #   参考：mpv 官方 issue #7357、chiphell 论坛 mpv HDR 教程。
        #   tone-mapping=clip：不做 tone mapping，直接输出 PQ 信号。
        #
        # HLG 视频：
        #   HLG 是相对编码，亮度根据显示器自动缩放（参考：forasoft HLG 文档）。
        #   若设置 target-peak=10000，mpv 会将 HLG 的 1.0（参考白 1000 nits）映射到
        #   10000 nits，导致高光过度拉伸过曝，tone-mapping=clip 截断高光，形成阴阳脸
        #   （用户反馈的"HLG人脸阴阳脸"）。
        #
        #   target-peak=1000（HLG 参考白电平）：
        #   必须设置非零 target-peak 才能触发 target-colorspace-hint 将 swapchain
        #   切换到 PQ 色彩空间。target-peak='' （auto/0）时 mpv 无法确定输出为 HDR，
        #   不切换 swapchain，HLG→PQ 输出在 sRGB swapchain 上显示为极暗画面
        #   （用户反馈的"HLG黑乎乎"）。1000 是 HLG 标准参考白电平（1000 nits），
        #   不会导致 target-peak=10000 的过曝/阴阳脸问题。
        #   hdr-compute-peak=yes 仍保留用于动态计算场景峰值。
        #   tone-mapping=auto（gpu-next 中选 spline）让 mpv 平滑处理 HLG→PQ 转换。
        #
        # gamut-mapping-mode=relative：相对色域映射，保持色彩准确性，
        # 让显示器/Windows 合成器处理最终的色域压缩。
        # 注意：hdr10-opt 由 _apply_hdr_on_file_loaded 根据视频类型统一设置，这里不再设置。
        self._set_mpv_string('target-prim', 'bt.2020')
        self._set_mpv_string('target-trc', 'pq')
        self._set_mpv_string('gamut-mapping-mode', 'relative')
        if is_pq:
            self._set_mpv_string('tone-mapping', 'clip')
            self._set_mpv_string('hdr-compute-peak', 'no')
            self._set_mpv_string('target-peak', '10000')
            self.logger.info("HDR配置: passthrough → PQ直通 (bt.2020/pq, target-peak=10000, gamut=relative)")
        else:
            # HLG 视频：让 mpv 自动处理 HLG→PQ 转换
            # target-peak=1000：HLG 参考白电平，触发 PQ swapchain 切换（修复首次播放黑屏）
            self._set_mpv_string('tone-mapping', 'auto')
            self._set_mpv_string('hdr-compute-peak', 'yes')
            self._set_mpv_string('target-peak', '1000')
            self.logger.info(
                "HDR配置: passthrough → HLG自动转换 "
                "(bt.2020/pq, target-peak=1000, compute-peak=yes, gamut=relative)"
            )

    def _apply_scrgb_config(self, is_pq=True):
        # d3d11-output-csp=pq + target-colorspace-hint=yes 已在初始化时设置
        # scrgb 模式与 passthrough 模式的 HDR 处理逻辑相同，
        # 都是将 HDR 内容以 PQ 信号输出到 swapchain，由 Windows DWM 合成。
        # 区别在于 scrgb 模式主要用于 auto 模式回退，passthrough 用于显式直通。
        # 参数选择同 passthrough，根据视频类型（PQ/HLG）区分处理。
        # 注意：hdr10-opt 由 _apply_hdr_on_file_loaded 根据视频类型统一设置，这里不再设置。
        self._apply_passthrough_config(is_pq)
        self.logger.info(f"HDR配置: scrgb → {'PQ直通' if is_pq else 'HLG自动转换'} (复用 passthrough 配置)")

    def _apply_wcg_config(self):
        """WCG 视频（宽色域 SDR）配置：保持 bt.2020 色域，SDR 亮度。

        WCG 视频是 BT.2020 色域但 SDR 亮度（gamma=srgb/bt.1886），
        需要保持 bt.2020 色域，避免被压缩到 bt.709 导致偏色。
        使用 gamut-mapping-mode=relative 让显示器/Windows 合成器处理色域映射。

        关键：必须显式重置所有 tone-mapping 参数，避免从 HDR10 passthrough
        切换时残留 target-peak=10000 / tone-mapping=clip 等参数导致画面发灰。
        """
        sdr_trc = self._get_sdr_target_trc()
        # 显式设置所有参数（不用空字符串重置，避免 mpv 默认值不确定性）
        self._set_mpv_string('tone-mapping', 'clip')
        self._set_mpv_string('tone-mapping-mode', 'auto')
        self._set_mpv_string('tone-mapping-desat', '0')
        self._set_mpv_string('hdr-compute-peak', 'no')
        self._set_mpv_string('hdr10-opt', 'no')
        self._set_mpv_string('target-prim', 'bt.2020')
        self._set_mpv_string('target-trc', sdr_trc)
        # target-peak=100：显式 SDR 电平，确保 target-colorspace-hint 将 swapchain
        # 切换到 sRGB 色彩空间。target-peak='' 时可能残留上次 HDR 视频的 PQ swapchain，
        # 导致 SDR 内容在 PQ swapchain 上显示为极暗画面。
        self._set_mpv_string('target-peak', '100')
        self._set_mpv_string('gamut-mapping-mode', 'relative')
        self.logger.info(f"HDR配置: WCG → 保持bt.2020色域 (bt.2020/{sdr_trc}, target-peak=100, gamut=relative)")

    def _reset_hdr_params(self):
        # 非 HDR 视频：显式指定 SDR 目标，确保 bt.2020 色域（WCG）视频能正确映射到 bt.709
        # d3d11-output-csp 和 target-colorspace-hint 已在初始化时设置
        # 重置 target-peak：passthrough/scrgb 模式设置了 10000，切换到非 HDR 视频时必须重置。
        # 重置 gamut-mapping-mode：passthrough/scrgb 设置了 relative，非 HDR 视频不需要。
        sdr_trc = self._get_sdr_target_trc()
        self._set_mpv_string('tone-mapping', '')
        self._set_mpv_string('tone-mapping-mode', '')
        self._set_mpv_string('tone-mapping-desat', '')
        self._set_mpv_string('hdr-compute-peak', '')
        self._set_mpv_string('hdr10-opt', 'no')
        self._set_mpv_string('target-prim', 'bt.709')
        self._set_mpv_string('target-trc', sdr_trc)
        # target-peak=100：显式 SDR 电平，确保 swapchain 切换到 sRGB 色彩空间
        self._set_mpv_string('target-peak', '100')
        self._set_mpv_string('gamut-mapping-mode', '')
        self.logger.info(f"HDR配置: 已重置为SDR默认值 (bt.709/{sdr_trc}, target-peak=100)")

    def _set_mpv_string(self, name, value):
        if self._terminated or not self.mpv_handle:
            return -1
        return _mpv_set_property_string(self.mpv_handle, name, str(value))

    def _set_cache_param(self, name, value):
        """设置缓存相关参数（cache-secs / demuxer-max-bytes / demuxer-readahead-secs）。

        与 _set_mpv_string 的区别：用户在订阅设置中配置了 override(>0) 时，
        用 override 替换动态计算值。_reset_demuxer_options 中的清空操作
        不经过此方法，因此 override 不会破坏重置逻辑。
        """
        if self._terminated or not self.mpv_handle:
            return -1
        s = self._playback_settings
        try:
            if name == 'cache-secs':
                ov = float(s.get('cache_secs_override', 0) or 0)
                if ov > 0:
                    value = str(int(ov))
            elif name == 'demuxer-max-bytes':
                ov = float(s.get('demuxer_max_bytes_mib_override', 0) or 0)
                if ov > 0:
                    value = f'{int(ov)}MiB'
            elif name == 'demuxer-readahead-secs':
                ov = float(s.get('demuxer_readahead_secs_override', 0) or 0)
                if ov > 0:
                    value = str(int(ov))
        except (TypeError, ValueError):
            pass
        return _mpv_set_property_string(self.mpv_handle, name, str(value))

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
        """快速检查 HTTP/HTTPS 主机是否可达。

        返回 None 表示可达或无法判断，返回错误字符串表示不可达。
        注意：此检查仅用于快速过滤完全不可达的地址（如 DNS 解析失败），
        不应阻止慢响应服务器播放——mpv 内部 network-timeout 会处理。
        """
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
                # 使用 AF_UNSPEC 支持 IPv4 和 IPv6（getaddrinfo 自动选择）
                sock = socket.socket(socket.AF_UNSPEC, socket.SOCK_STREAM)
                sock.settimeout(3)
                sock.connect((host, port))
                sock.close()
            except (socket.timeout, socket.error, OSError) as e:
                return f"网络不可达: {host}:{port} ({e})"
            except Exception as e:
                global_logger.debug(f"_check_path_reachability_sync 未知异常: {e}")
            return None
        return None

    def _check_path_reachability(self, url):
        """异步检查网络可达性。

        返回 None 表示可达或检查超时（继续尝试播放），
        返回错误字符串表示确定不可达（如 DNS 解析失败）。
        """
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
                      '.m3u8' in u)
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

            vp_prim = (self._get_mpv_property_string('video-params/primaries') or '').lower()
            vp_gamma = (self._get_mpv_property_string('video-params/gamma') or '').lower()
            vp_peak = self._get_mpv_property_double('video-params/sig-peak') or 0
            vp_format = (self._get_mpv_property_string('video-format') or '').lower()
            vp_cm = (self._get_mpv_property_string('video-params/colormatrix') or '').lower()

            # DV 检测（libmpv 只能播放 HDR10 基础层）
            has_dovi = ('dovi' in vp_format or 'dolbyvision' in vp_format or
                        'dvhe' in vp_format or 'dvh1' in vp_format or 'dav1' in vp_format)
            # 统一 HDR 检测（与 detect_hdr_type 对齐）
            is_pq = 'pq' in vp_gamma or 'smpte2084' in vp_gamma
            is_hlg = 'hlg' in vp_gamma or 'arib-std-b67' in vp_gamma
            is_bt2020 = ('bt.2020' in vp_prim or 'bt2020' in vp_prim or
                         'bt.2020' in vp_cm or 'bt2020' in vp_cm)

            self.logger.info(
                f"视频HDR参数: primaries={vp_prim}, gamma={vp_gamma}, "
                f"sig_peak={vp_peak}, format={vp_format}, dovi={has_dovi}"
            )

            is_hdr_video = is_pq or is_hlg or has_dovi

            # WCG 视频（宽色域 SDR）：BT.2020 色域但 SDR 亮度（gamma=srgb/bt.1886）
            # 这类视频需要保持 bt.2020 色域，避免被压缩到 bt.709 导致偏色
            # 无论 hdr_mode 是什么，WCG 都必须保持 bt.2020 色域
            is_wcg_video = (not is_hdr_video and is_bt2020)

            if is_wcg_video:
                self.logger.info("WCG视频（宽色域SDR），保持bt.2020色域")
                self._apply_wcg_config()
                return

            if not is_hdr_video:
                self.logger.info("非HDR视频，重置HDR参数为默认值")
                self._reset_hdr_params()
                return

            # 根据 HDR 视频类型动态设置 hdr10-opt（HDR10+ 动态元数据传递）：
            # - PQ 视频（HDR10/HDR10+）/ DV 基础层（PQ）：启用 hdr10-opt=yes
            # - HLG 视频：禁用 hdr10-opt=no
            if has_dovi:
                self.logger.info("DV视频（基础层），按HDR10基础层处理")
            if is_pq:
                self._set_mpv_string('hdr10-opt', 'yes')
                self.logger.info("PQ视频，启用hdr10-opt传递HDR10+动态元数据")
            else:
                self._set_mpv_string('hdr10-opt', 'no')
                self.logger.info("非PQ视频（HLG），禁用hdr10-opt")

            def _check_system_hdr():
                """运行时检测系统 HDR 状态（比初始化时更准确，Qt 应用已完全就绪）。"""
                try:
                    if is_windows():
                        from utils.hdr_detect import is_windows_hdr_enabled
                        return is_windows_hdr_enabled()
                    elif is_macos():
                        from utils.hdr_detect import is_macos_hdr_enabled
                        return is_macos_hdr_enabled()
                    elif is_android():
                        from utils.hdr_detect import is_android_hdr_enabled
                        return is_android_hdr_enabled()
                    elif is_linux():
                        from utils.hdr_detect import is_linux_hdr_enabled
                        return is_linux_hdr_enabled()
                except Exception as _e:
                    global_logger.debug(f"unexpected error: {_e}")
                return False

            # hdr_mode == 'disable' 时，HDR 视频仍需 tonemap 到 SDR
            # 但要保持 bt.2020 色域（而非压到 bt.709）
            if hdr_mode == 'disable':
                self._apply_tonemap_config(is_hlg=is_hlg)
                return

            if hdr_mode == 'tonemap':
                self._apply_tonemap_config(is_hlg=is_hlg)
                return

            if hdr_mode == 'passthrough':
                system_hdr = _check_system_hdr()
                fallback = getattr(self, '_hdr_fallback_tonemap', False) or not system_hdr
                if fallback:
                    if not system_hdr:
                        self.logger.warning("运行时检测系统未启用HDR，passthrough模式回退到tonemap")
                    self._apply_tonemap_config(is_hlg=is_hlg)
                else:
                    self._apply_passthrough_config(is_pq)
                return

            if hdr_mode == 'scrgb':
                system_hdr = _check_system_hdr()
                fallback = getattr(self, '_hdr_fallback_tonemap', False) or not system_hdr
                if fallback:
                    if not system_hdr:
                        self.logger.warning("运行时检测系统未启用HDR，scrgb模式回退到tonemap")
                    self._apply_tonemap_config(is_hlg=is_hlg)
                else:
                    self._apply_scrgb_config(is_pq)
                return

            if hdr_mode == 'auto':
                system_hdr_enabled = _check_system_hdr()
                if system_hdr_enabled:
                    self._apply_scrgb_config(is_pq)
                else:
                    self._apply_tonemap_config(is_hlg=is_hlg)
                return

        except Exception as e:
            self.logger.error(f"应用HDR设置失败: {e}")

    def _reset_demuxer_options(self):
        try:
            self._set_mpv_string('demuxer', '')
            self._set_mpv_string('demuxer-lavf-format', '')
            self._set_mpv_string('demuxer-lavf-probesize', '5000000')
            self._set_mpv_string('demuxer-lavf-analyzeduration', '5')
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
                          '.m3u8' in u)
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
            except Exception as _e:
                global_logger.debug(f"unexpected error: {_e}")
            is_4k = (w >= 3840 or h >= 2160)
            is_hdr = False
            try:
                gamma = (self._get_mpv_property_string('video-params/gamma') or '').lower()
                vf = (self._get_mpv_property_string('video-format') or '').lower()
                # 统一 HDR 检测（与 detect_hdr_type 对齐）
                is_hdr = ('pq' in gamma or 'smpte2084' in gamma or
                          'hlg' in gamma or 'arib-std-b67' in gamma or
                          'dovi' in vf or 'dvhe' in vf or 'dvh1' in vf or 'dav1' in vf)
            except Exception as _e:
                global_logger.debug(f"unexpected error: {_e}")
            is_large_file = file_size > 10 * 1024 * 1024 * 1024 or (duration > 3600 and is_4k)
            if not is_4k and not is_hdr and not is_large_file:
                return
            cache_secs = 120
            max_bytes_mib = 1024
            probesize = 50000000
            analyzeduration = 10
            if is_4k and is_hdr:
                cache_secs = 180
                max_bytes_mib = 2048
                probesize = 100000000
                analyzeduration = 15
            elif is_4k:
                cache_secs = 150
                max_bytes_mib = 1536
                probesize = 80000000
                analyzeduration = 12
            if is_large_file:
                cache_secs = max(cache_secs, 240)
                max_bytes_mib = max(max_bytes_mib, 3072)
            self._set_cache_param('cache-secs', str(cache_secs))
            self._set_cache_param('demuxer-max-bytes', f'{max_bytes_mib}MiB')
            self._set_mpv_string('demuxer-max-back-bytes', f'{max_bytes_mib // 2}MiB')
            self._set_mpv_string('demuxer-lavf-probesize', str(probesize))
            self._set_mpv_string('demuxer-lavf-analyzeduration', str(analyzeduration))
            self.logger.info(
                f"动态缓冲调整: {w}x{h} HDR={is_hdr} large={is_large_file} "
                f"-> cache={cache_secs}s max={max_bytes_mib}MiB "
                f"probesize={probesize}"
            )
        except Exception as e:
            self.logger.debug(f"动态缓冲调整失败: {e}")

    def _setup_bluray_options(self):
        try:
            self._set_mpv_string('demuxer', '')
            self._set_mpv_string('demuxer-lavf-format', '')
            self._set_mpv_string('demuxer-lavf-probesize', '100000000')
            self._set_mpv_string('demuxer-lavf-analyzeduration', '20')
            self._set_mpv_string('cache', 'yes')
            self._set_cache_param('cache-secs', '180')
            self._set_cache_param('demuxer-max-bytes', '2048MiB')
            self._set_mpv_string('demuxer-max-back-bytes', '1024MiB')
            self._set_cache_param('demuxer-readahead-secs', '60')
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
            self._set_mpv_string('demuxer-lavf-analyzeduration', '10')
            # mpv 规定 demuxer-lavf-buffersize 最大值为 10485760（10MiB），
            # 超出会被拒绝并导致整个网络挂载盘配置失败（参考 app.log 错误：
            # "The demuxer-lavf-buffersize option must be <= 10485760"）
            self._set_mpv_string('demuxer-lavf-buffersize', '10485760')
            self._set_mpv_string('cache', 'yes')
            self._set_cache_param('cache-secs', '60')
            self._set_cache_param('demuxer-max-bytes', '512MiB')
            self._set_mpv_string('demuxer-max-back-bytes', '256MiB')
            self._set_cache_param('demuxer-readahead-secs', '30')
            self._set_mpv_string('force-seekable', 'yes')
            self._set_mpv_string('demuxer-seekable-cache', 'yes')
            self.logger.debug("[mpv] 网络挂载盘选项已设置: cache=yes, probesize=50M, readahead=30s")
        except Exception as e:
            self.logger.debug(f"设置网络挂载盘选项失败: {e}")

    def _setup_protocol_options(self, url, program_duration=0):
        if not self.mpv_handle or not url:
            return
        u = url.lower()

        # FCC 频道检测：rtp2httpd 等 FCC 代理已预先加入组播并转发流，
        # 数据到达速度快且编码通常为 H.264/H.265，可使用更小的探测参数加速首帧。
        # 非 FCC 频道保留大 probesize 以兼容 CAVS 等编码。
        is_fcc = '?fcc=' in u

        is_network = (u.startswith(('http://', 'https://', 'rtmp://', 'rtsp://', 'rtp://', 'udp://')) or
                      '.m3u8' in u)
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

        # 用户自定义 probesize/analyzeduration 覆盖（0 表示使用各流类型的自动值）
        _probe_override = int(settings.get('probesize_override', 0) or 0)
        _analyze_override = float(settings.get('analyzeduration_override', 0) or 0)

        def _probe(probesize, analyzeduration):
            """应用用户覆盖值（如果已配置）"""
            p = str(_probe_override) if _probe_override > 0 else str(probesize)
            a = str(_analyze_override) if _analyze_override > 0 else str(analyzeduration)
            self._set_mpv_string('demuxer-lavf-probesize', p)
            self._set_mpv_string('demuxer-lavf-analyzeduration', a)

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
            self._set_cache_param('cache-secs', str(cache_secs))
            self._set_mpv_string('demuxer-lavf-format', '')
            if rtsp_transport == 'udp':
                _probe(500000, 1)
                self._set_cache_param('demuxer-max-bytes', f'{max_bytes_mib}MiB')
                self._set_mpv_string('demuxer-max-back-bytes', f'{max_bytes_mib}MiB')
                self._set_cache_param('demuxer-readahead-secs', '5')
                self._set_mpv_string('force-seekable', 'no')
                self.logger.debug(f"[mpv] rtsp-udp-live cache={cache_secs} transport={rtsp_transport}")
            elif is_vod:
                _probe(5000000, 5)
                self._set_mpv_string('force-seekable', 'yes')
                self.logger.debug(f"[mpv] rtsp-vod cache={cache_secs} transport={rtsp_transport}")
            else:
                # 直播流需要足够的探测数据让 demuxer 识别编码格式（如 CAVS）
                # probesize=32 太少会导致 CAVS 流无法被识别（track-list 为空）
                _probe(5000000, 5)
                self.logger.debug(f"[mpv] rtsp-tcp-live cache={cache_secs} transport={rtsp_transport}")
            return

        looks_ts = ('/rtp/' in u or u.endswith('.ts') or 'proto=http' in u or u.startswith('udp://'))
        if looks_ts:
            self._set_mpv_string('demuxer', 'lavf')
            self._set_mpv_string('demuxer-lavf-format', 'mpegts')
            if is_vod:
                _probe(5000000, 5)
                self._set_mpv_string('force-seekable', 'yes')
            elif is_fcc:
                # FCC 快速换台：rtp2httpd 代理已预加入组播，流数据即时可用。
                # probesize 2MB 足够识别各种编码，analyzeduration 2s 进一步减少首帧等待。
                # （probesize 500KB 太小会导致部分频道无法识别编码 → 不出画面）
                _probe(2000000, 2)
            else:
                # 非 FCC 直播流需要足够的探测数据让 demuxer 识别编码格式（如 CAVS）
                # probesize=32 太少会导致 CAVS 流无法被识别（track-list 为空）
                _probe(5000000, 5)
            self._set_mpv_string('demuxer-lavf-buffersize', '128000')
            self._set_mpv_string('cache', 'yes')
            self._set_mpv_string('force-seekable', 'yes')
            self._set_mpv_string('demuxer-seekable-cache', 'yes')
            self._set_cache_param('cache-secs', str(cache_secs))
            self._set_cache_param('demuxer-max-bytes', f'{max_bytes_mib}MiB')
            self._set_mpv_string('demuxer-max-back-bytes', f'{max_bytes_mib}MiB')
            self._set_cache_param('demuxer-readahead-secs', '300')
            self.logger.debug(
                f"[mpv] ts demux=mpegts cache={cache_secs}s "
                f"back={max_bytes_mib}MiB dur={program_duration}s fcc={is_fcc}"
            )
            return

        if '.m3u8' in u or 'format=hls' in u:
            self._set_mpv_string('demuxer-lavf-format', '')
            self._set_mpv_string('cache', 'yes')
            self._set_cache_param('cache-secs', str(cache_secs))
            self._set_cache_param('demuxer-max-bytes', f'{max_bytes_mib}MiB')
            self._set_mpv_string('demuxer-max-back-bytes', f'{max_bytes_mib}MiB')
            self._set_mpv_string('force-seekable', 'yes')
            self._set_cache_param('demuxer-readahead-secs', '120')
            # HLS 流也需要设置 probesize/analyzeduration，否则使用 mpv 默认值
            # 可能导致部分 HLS 流（含损坏分片）无法正确识别编码
            _probe(5000000, 5)

            if settings.get('hls_start_at_live_edge', False):
                self._set_mpv_string('hls-playlist-start', 'no')
            readahead = settings.get('hls_readahead_secs', 0)
            if readahead > 0:
                self._set_cache_param('demuxer-readahead-secs', str(readahead))
            self.logger.debug(f"[mpv] hls cache=yes seekable=yes vod={is_vod}")
            return

        self._set_mpv_string('demuxer-lavf-format', '')
        if is_fcc and not is_vod:
            # FCC 频道：适度降低探测参数加速首帧（保留足够数据兼容各种编码）
            _probe(2000000, 2)
        else:
            # 显式设置 probesize/analyzeduration，确保 CAVS 等编码能被 demuxer 正确识别
            # （mpv 默认值可能因版本/平台不同而不一致）
            _probe(5000000, 5)
        self._set_mpv_string('cache', 'yes')
        self._set_cache_param('cache-secs', str(cache_secs))
        self._set_cache_param('demuxer-max-bytes', f'{max_bytes_mib}MiB')
        self._set_mpv_string('demuxer-max-back-bytes', f'{max_bytes_mib}MiB')
        self._set_mpv_string('force-seekable', 'yes')
        self._set_cache_param('demuxer-readahead-secs', '120')
        self._set_mpv_string('demuxer-cache-wait', 'no')
        self.logger.debug(f"[mpv] generic http cache=yes seekable=yes fcc={is_fcc}")

        if (u.startswith('http://') or u.startswith('https://')):
            headers = settings.get('http_headers', '')
            if headers:
                header_val = headers.replace('\r\n', '\n').replace('\n', '\\n')
                self._set_mpv_string('http-header-fields', header_val)
                self.logger.debug("[mpv] http-headers set")

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
                        except Exception as _e:
                            self.logger.debug(f"处理 pause 属性变更事件失败: {_e}")

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
                                        self._safe_emit(
                                            self.local_file_position_to_save,
                                            ended_url, float(pos_sec), float(dur_sec)
                                        )
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
                                    err_str = (
                                        self._get_mpv_error_string(end_file.error)
                                        if hasattr(end_file, 'error')
                                        else f"error_code={reason}"
                                    )
                                    self.logger.warning(
                                        f"END_FILE错误，尝试重连: {err_str}, "
                                        f"is_net_file={is_net_file}"
                                    )
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

                elif event.event_id == MPV_EVENT_LOG_MESSAGE:
                    # 将 mpv 内部日志转发到 app logger（仅 demuxer/vd/ad/hwdec 模块的 debug 日志，
                    # 由 msg-level 和 mpv_request_log_messages 共同控制）
                    if event.data:
                        try:
                            log_msg = ctypes.cast(event.data, ctypes.POINTER(mpv_event_log_message)).contents
                            prefix = log_msg.prefix.decode('utf-8', errors='ignore') if log_msg.prefix else ''
                            level = log_msg.level.decode('utf-8', errors='ignore') if log_msg.level else ''
                            text = log_msg.text.decode('utf-8', errors='ignore').rstrip() if log_msg.text else ''
                            if not text:
                                continue
                            if level in ('error', 'fatal'):
                                global_logger.error(f"[mpv:{prefix}] {text}")
                            elif level == 'warn':
                                global_logger.warning(f"[mpv:{prefix}] {text}")
                            else:
                                global_logger.debug(f"[mpv:{prefix}] {text}")
                        except Exception as _e:
                            global_logger.debug(f"处理 mpv 日志消息失败: {_e}")

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
                # 预检查失败不阻止播放：某些服务器响应慢或有地域限制，
                # Python socket 检查可能超时，但 mpv 内部网络栈（network-timeout=30s）
                # 可以成功连接。仅记录警告，让 mpv 自行尝试。
                self.logger.warning(
                    f"预检查提示可能不可达（不阻止播放）: {reachability}，"
                    f"交给 mpv 尝试连接"
                )

            if not self.mpv_handle:
                self.logger.error("mpv播放器未初始化")
                self._safe_emit(self.play_error, "mpv播放器未初始化")
                return False

            if self._terminated:
                return False

            # 切换频道前显式停止当前播放，让 mpv 释放 hwdec/D3D11 解码器资源
            # 避免 keep-open=yes + idle=yes 导致旧解码器未释放，新文件 hwdec 初始化失败（黑屏）
            if (self.is_playing or self.is_paused) and not self._user_stopped:
                # 保存本地视频播放位置（stop 触发的 END_FILE reason=STOP 不会保存位置）
                old_url = self.current_url or ''
                if old_url and not self._is_network_url(old_url):
                    try:
                        pos_sec = self._get_mpv_property_double('time-pos') or 0.0
                        dur_sec = self._get_mpv_property_double('duration') or 0.0
                        if old_url and pos_sec > 0:
                            self._safe_emit(
                                self.local_file_position_to_save,
                                old_url, float(pos_sec), float(dur_sec)
                            )
                            self.logger.debug(
                                f"切换前保存本地视频断点: {old_url[:60]} "
                                f"pos={pos_sec:.1f}s"
                            )
                    except Exception as e:
                        self.logger.debug(f"切换前保存播放位置失败: {e}")
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
                except Exception as _e:
                    self.logger.debug(f"清理视频滤镜失败: {_e}")

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
            import services.network_preheat_service  # noqa: F401
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
        # 防止重入：如果已在终止过程中，直接返回
        if getattr(self, '_terminated', False):
            self.logger.debug("terminate() 已在执行中，跳过重复调用")
            return
        try:
            self._terminated = True
            self.logger.info("正在终止MPV播放器...")

            if is_macos() and hasattr(self.video_widget, 'cleanup'):
                try:
                    self.video_widget.cleanup()
                except Exception as _e:
                    global_logger.debug(f"unexpected error: {_e}")

            for timer_attr in ['_media_info_timer', '_live_info_timer', 'event_timer']:
                timer = getattr(self, timer_attr, None)
                if timer:
                    try:
                        timer.stop()
                    except Exception as _e:
                        global_logger.debug(f"unexpected error: {_e}")

            with self._lock:
                handle = self.mpv_handle
                self.mpv_handle = None

            if handle:
                try:
                    _mpv_send_command(handle, ['quit'])
                except Exception as e:
                    self.logger.debug(f"发送quit命令失败（可能已关闭）: {e}")

                from PySide6.QtCore import QElapsedTimer, QEventLoop
                elapsed = QElapsedTimer()
                elapsed.start()
                while elapsed.elapsed() < 150:
                    from PySide6.QtWidgets import QApplication
                    QApplication.processEvents(
                        QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents
                    )
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

            # 关闭 FCC 持久化 UDP socket
            try:
                from services.fcc_service import _close_udp_socket
                _close_udp_socket()
            except Exception as _e:
                global_logger.debug(f"unexpected error: {_e}")

            self.logger.info("MPV播放器已完全终止")
        except Exception as e:
            self.logger.error(f"终止MPV播放器失败: {str(e)}")

    def reinit_for_hdr_change(self, new_hdr_mode):
        try:
            from utils.hdr_detect import clear_hdr_cache
            clear_hdr_cache()
        except Exception as _e:
            global_logger.debug(f"unexpected error: {_e}")
        saved_url = self.current_url
        saved_position = 0.0
        was_playing = self.is_playing and not self.is_paused
        if self.mpv_handle:
            try:
                saved_position = self._get_mpv_property_double('time-pos') or 0.0
            except Exception as _e:
                global_logger.debug(f"unexpected error: {_e}")
        self.stop()
        for timer_attr in ['_media_info_timer', '_live_info_timer', 'event_timer']:
            timer = getattr(self, timer_attr, None)
            if timer:
                try:
                    timer.stop()
                except Exception as _e:
                    global_logger.debug(f"unexpected error: {_e}")
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
            except Exception as _e:
                global_logger.debug(f"unexpected error: {_e}")
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
                seek_retries = [0]

                def _do_seek():
                    if self._terminated or not self.mpv_handle or not self.is_playing:
                        return
                    # 等待 file-loaded 事件后再 seek，确保播放器就绪
                    file_loaded = False
                    try:
                        file_loaded = self._get_mpv_property_double('time-pos') is not None
                    except Exception as _e:
                        global_logger.debug(f"unexpected error: {_e}")
                    if file_loaded:
                        self.send_command(['seek', str(pos), 'absolute'])
                    elif seek_retries[0] < 5:
                        seek_retries[0] += 1
                        QTimer.singleShot(500, _do_seek)
                    else:
                        self.logger.warning(f"HDR切换后恢复播放位置失败（重试 {seek_retries[0]} 次后放弃）")
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
            # mpv 新版废弃 video-aspect-override=-1，需用 'no' + video-aspect-mode=container 替代
            ratio_lower = ratio.lower() if ratio else 'default'
            if ratio_lower == '16:9':
                self._set_mpv_string('video-aspect-override', '16:9')
                self._set_mpv_string('video-aspect-mode', 'container')
                self._set_mpv_string('keepaspect', 'yes')
                self._set_mpv_string('panscan', '0.0')
            elif ratio_lower == '4:3':
                self._set_mpv_string('video-aspect-override', '4:3')
                self._set_mpv_string('video-aspect-mode', 'container')
                self._set_mpv_string('keepaspect', 'yes')
                self._set_mpv_string('panscan', '0.0')
            elif ratio_lower == 'stretch':
                self._set_mpv_string('video-aspect-override', 'no')
                self._set_mpv_string('video-aspect-mode', 'container')
                self._set_mpv_string('keepaspect', 'no')
                self._set_mpv_string('panscan', '0.0')
            elif ratio_lower == 'fill':
                self._set_mpv_string('video-aspect-override', 'no')
                self._set_mpv_string('video-aspect-mode', 'container')
                self._set_mpv_string('keepaspect', 'yes')
                self._set_mpv_string('panscan', '1.0')
            elif ratio_lower == 'crop':
                self._set_mpv_string('video-aspect-override', 'no')
                self._set_mpv_string('video-aspect-mode', 'container')
                self._set_mpv_string('keepaspect', 'yes')
                self._set_mpv_string('panscan', '1.0')
            else:
                self._set_mpv_string('video-aspect-override', 'no')
                self._set_mpv_string('video-aspect-mode', 'container')
                self._set_mpv_string('keepaspect', 'yes')
                self._set_mpv_string('panscan', '0.0')
            # 缓存当前比例，供 get_aspect_ratio 读出
            # 用于 PlaybackSettingsController 在切换频道前持久化播放设置
            self._current_aspect_ratio = ratio_lower
            self.logger.debug(f"设置画面比例: {ratio}")
        except Exception as e:
            self.logger.error(f"设置画面比例失败: {str(e)}")

    def get_aspect_ratio(self) -> str:
        """读取当前画面比例（与 set_aspect_ratio 配对，用于播放设置持久化）"""
        return self._current_aspect_ratio

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
                self.logger.debug(
                    f"媒体信息：width={w}, height={h}, vcodec='{vcodec}', "
                    f"acodec='{acodec}', fps={fps}, container='{container}'"
                )

            if not vcodec and not acodec and w == 0:
                demuxer = get_str('demuxer') or ''
                v_format = get_str('video-format') or ''
                a_format = get_str('audio-format') or ''
                self.logger.info(
                    f"demuxer: {demuxer}, video-format: {v_format}, "
                    f"audio-format: {a_format} "
                    f"(demuxer probing in progress, info may update later)"
                )

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
                    self.logger.debug(
                        f"[SRC{self._pos_log_count}] total={total_time} "
                        f"cur={current_time} pos={position} "
                        f"url={self.current_url[:60] if self.current_url else 'None'}..."
                    )

                self._safe_emit(
                    self.playback_position_updated,
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

    def _has_video_track(self):
        """检查当前播放的流是否包含真实视频轨（非 albumart）。

        用于截图前判断：纯音频频道（如电视伴音）没有视频帧，
        screenshot-to-file 会失败并产生 ERROR 日志。
        """
        try:
            track_list_str = self._get_mpv_property_string('track-list') or ''
            if not track_list_str:
                return False
            import json
            tracks = json.loads(track_list_str)
            for t in tracks:
                if t.get('type') == 'video' and not t.get('albumart', False):
                    return True
            return False
        except Exception:
            return False

    def _capture_thumbnail(self):
        if not self.is_playing or not self.current_url:
            return
        # 纯音频频道（如电视伴音）没有视频帧，截图必然失败
        if not self._has_video_track():
            self.logger.debug("纯音频频道，跳过缩略图截图")
            return
        try:
            import hashlib
            # Android Chaquopy 环境：优先使用 IPTV_DATA_DIR（已指向 ISEP 目录）
            _android_data = get_android_data_dir()
            if _android_data:
                cache_dir = os.path.join(_android_data, 'cache', 'thumbnails')
            else:
                cache_dir = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    'cache', 'thumbnails'
                )
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
                except Exception as _e:
                    global_logger.debug(f"unexpected error: {_e}")
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
        except Exception as _e:
            global_logger.debug(f"unexpected error: {_e}")

    @staticmethod
    def get_thumbnail_path(url):
        if not url:
            return None
        import hashlib
        # Android Chaquopy 环境：优先使用 IPTV_DATA_DIR（已指向 ISEP 目录）
        _android_data = get_android_data_dir()
        if _android_data:
            cache_dir = os.path.join(_android_data, 'cache', 'thumbnails')
        else:
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
        except Exception as _e:
            global_logger.debug(f"unexpected error: {_e}")
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
        except Exception as _e:
            global_logger.debug(f"unexpected error: {_e}")

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
                except Exception as _e:
                    global_logger.debug(f"unexpected error: {_e}")
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
                    self.logger.error(
                        f"切换轨道失败: {prop}={track_id}, "
                        f"int64错误码={result}, string错误码={result2}, "
                        f"command错误码={result3}"
                    )
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
        except Exception as _e:
            global_logger.debug(f"unexpected error: {_e}")
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
            if 'video_flip' in eq and eq['video_flip'] is not None:
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

    # ---------- 反交错（vf 滤镜） ----------
    def _enable_deinterlace_filter(self):
        """启用 yadif bob 反交错滤镜（mode=1，50i→50p，保持运动流畅）

        使用 vf 滤镜链的命名标签 @iptv_deint 管理，便于运行时添加/移除。
        与 mpv 的 deinterlace 属性区别：
        - deinterlace=yes：内部用 yadif mode=0（frame mode），50i→25p，帧率减半，运动卡顿
        - yadif=mode=1（field/bob mode）：50i→50p，保持原始帧率，运动流畅
        注意：lavfi/vf 滤镜需要 copy-back 硬解（hwdec=auto-copy）或软解（hwdec=no）。
        """
        if not self.mpv_handle or self._terminated:
            return
        try:
            self.send_command(['vf', 'remove', '@iptv_deint'])
        except Exception as _e:
            global_logger.debug(f"unexpected error: {_e}")
        ret = self.send_command(['vf', 'add', '@iptv_deint:yadif=mode=1'])
        if ret != 0:
            cur_hwdec = ''
            try:
                cur_hwdec = self._get_mpv_property_string('hwdec') or ''
            except Exception as _e:
                global_logger.debug(f"unexpected error: {_e}")
            self.logger.warning(
                f"yadif bob 反交错滤镜添加失败(ret={ret})，当前 hwdec='{cur_hwdec}'。"
                f"若为原生硬解(auto)，请在播放设置中改为 copy-back(auto-copy) 或软解(no)"
            )
        else:
            self.logger.info("yadif bob 反交错滤镜已添加 (mode=1, 50i→50p)")

    def _disable_deinterlace_filter(self):
        """禁用反交错滤镜"""
        if not self.mpv_handle or self._terminated:
            return
        try:
            self.send_command(['vf', 'remove', '@iptv_deint'])
            self.logger.info("反交错滤镜已移除")
        except Exception as _e:
            global_logger.debug(f"unexpected error: {_e}")

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
        使用 mpv 的 lavfi 滤镜包装 FFmpeg 的 hflip/vflip：
          - horizontal: lavfi=[hflip]
          - vertical:   lavfi=[vflip]
          - both:       lavfi=[hflip,vflip]  （方括号内的逗号属于 FFmpeg filter_graph，不会被 mpv 当滤镜分隔符）
        注意：lavfi 滤镜需要 copy-back 硬解（hwdec=auto-copy）或软解（hwdec=no）。
              原生硬解（hwdec=auto）下解码帧留在 GPU，lavfi 无法访问帧数据，滤镜不生效。
        """
        if not self.mpv_handle or self._terminated:
            return False
        # 通过 vf 滤镜实现；先清除已有 flip 滤镜，再添加新的
        try:
            self.send_command(['vf', 'remove', '@iptv_flip'])
        except Exception as _e:
            global_logger.debug(f"unexpected error: {_e}")
        if not mode:
            return True
        if mode == 'horizontal':
            filter_str = 'lavfi=[hflip]'
        elif mode == 'vertical':
            filter_str = 'lavfi=[vflip]'
        elif mode == 'both':
            filter_str = 'lavfi=[hflip,vflip]'
        else:
            return False
        # 使用命名标签便于后续替换
        ret = self.send_command(['vf', 'add', f'@iptv_flip:{filter_str}'])
        if ret != 0:
            # 滤镜添加失败：常见原因是原生硬解（hwdec=auto）下 lavfi 不可用
            cur_hwdec = self._get_mpv_property_string('hwdec') or ''
            self.logger.warning(
                f"翻转滤镜添加失败(ret={ret})，filter='{filter_str}'，当前 hwdec='{cur_hwdec}'。"
                f"若为原生硬解(auto)，请在播放设置中改为 copy-back(auto-copy) 或软解(no)"
            )
            return False
        self.logger.info(f"翻转滤镜已添加: {filter_str}")
        return True

    def get_video_flip(self) -> str:
        """读取当前 flip 状态"""
        try:
            vf = self._get_mpv_property_string('vf')
            if not vf:
                return ''
            import json
            data = json.loads(vf) if isinstance(vf, str) else vf
            # mpv 返回的 vf JSON 结构：
            # {"vf": [{"name": "lavfi", "params": {"graph": "hflip"}, "label": "iptv_flip"}, ...]}
            # 通过 label 识别本程序添加的翻转滤镜，再解析 graph 判断方向
            for item in data.get('vf', []):
                label = item.get('label', '') or ''
                if label != 'iptv_flip':
                    continue
                name = item.get('name', '')
                if name != 'lavfi':
                    continue
                graph = (item.get('params', {}) or {}).get('graph', '') or ''
                has_hflip = 'hflip' in graph
                has_vflip = 'vflip' in graph
                if has_hflip and has_vflip:
                    return 'both'
                if has_hflip:
                    return 'horizontal'
                if has_vflip:
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
        except Exception as _e:
            global_logger.debug(f"unexpected error: {_e}")
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
        for label in ('@iptv_flip', '@iptv_crop', '@iptv_360', '@iptv_mc', '@iptv_sr'):
            try:
                self.send_command(['vf', 'remove', label])
            except Exception as _e:
                global_logger.debug(f"unexpected error: {_e}")
        return True

    # ---------- 运动补偿（vf 滤镜） ----------
    # 使用 FFmpeg minterpolate 滤镜实现运动补偿插帧
    # 滤镜标签：@iptv_mc
    #
    # 强度级别：
    #   off    — 关闭（移除滤镜）
    #   low    — 帧混合模式（mi_mode=blend），最轻量，仅做简单帧间混合
    #   medium — 运动补偿插帧（mi_mode=mci, mc_mode=obmc, me=dsr），中等 CPU 开销
    #   high   — 运动补偿插帧（mi_mode=mci, mc_mode=aobmc, me=hexbs），较重 CPU 开销
    #
    # me 搜索算法：dsr(菱形搜索,最快) > hexbs(六边形,中等) > epzs(穷举,最慢)
    # me_mode: uni(单向) 远快于 bidir(双向)
    #
    # 目标帧率：50 / 60 / 120 等（自动匹配显示器时传 0，使用 video-sync=display-resample）
    #
    # 注意：minterpolate 需要 copy-back 硬解（hwdec=auto-copy）或软解（hwdec=no）。
    #       原生硬解（hwdec=auto）下 lavfi 不可用。

    # 运动补偿预设参数
    _MC_PRESETS = {
        'off': None,
        'low': 'mi_mode=blend',
        'medium': 'mi_mode=mci:mc_mode=obmc:me=dsr',
        'high': 'mi_mode=mci:mc_mode=aobmc:me=hexbs',
    }

    def _get_video_resolution(self):
        """获取当前视频分辨率，返回 (width, height)"""
        try:
            w = self._get_mpv_property_int('width') or 0
            h = self._get_mpv_property_int('height') or 0
            return w, h
        except Exception:
            return 0, 0

    def _is_4k_or_above(self) -> bool:
        """检测当前视频是否为 4K 及以上分辨率"""
        w, h = self._get_video_resolution()
        return w >= 3840 or h >= 2160

    def set_motion_compensation(self, strength: str, target_fps: int = 60) -> bool:
        """设置运动补偿插帧

        :param strength: 'off' / 'low' / 'medium' / 'high'
        :param target_fps: 目标帧率（50/60/120），0 表示自动匹配显示器
        :return: 成功与否
        """
        if not self.mpv_handle or self._terminated:
            return False
        # 先移除旧滤镜
        try:
            self.send_command(['vf', 'remove', '@iptv_mc'])
        except Exception as _e:
            global_logger.debug(f"unexpected error: {_e}")

        if strength not in self._MC_PRESETS:
            strength = 'off'
        preset = self._MC_PRESETS[strength]
        if preset is None:
            self.logger.info("运动补偿已关闭")
            return True

        # 限制目标帧率到合理范围
        fps = int(target_fps)
        if fps not in (50, 60, 90, 120, 144, 240):
            fps = 60

        # 4K 及以上：先降采样到 1080p 再做运动补偿，避免 CPU 瓶颈
        # minterpolate 是 CPU 端滤镜，4K 像素量是 1080p 的 4 倍，直接处理会严重卡顿
        if self._is_4k_or_above():
            filter_str = (
                f'@iptv_mc:lavfi=['
                f'scale=1920:1080:flags=fast_bilinear,'
                f'minterpolate=fps={fps}:{preset}'
                f']'
            )
            self.logger.info(
                "检测到 4K+ 视频，运动补偿已自动降采样到 1080p 处理"
            )
        else:
            filter_str = f'@iptv_mc:lavfi=[minterpolate=fps={fps}:{preset}]'
        ret = self.send_command(['vf', 'add', filter_str])
        if ret != 0:
            cur_hwdec = ''
            try:
                cur_hwdec = self._get_mpv_property_string('hwdec') or ''
            except Exception as _e:
                global_logger.debug(f"unexpected error: {_e}")
            self.logger.warning(
                f"运动补偿滤镜添加失败(ret={ret})，strength='{strength}'，fps={fps}，"
                f"当前 hwdec='{cur_hwdec}'。"
                f"若为原生硬解(auto)，请在播放设置中改为 copy-back(auto-copy) 或软解(no)"
            )
            return False
        self.logger.info(f"运动补偿滤镜已添加: strength={strength}, fps={fps}")
        return True

    def get_motion_compensation(self) -> dict:
        """读取当前运动补偿设置

        :return: {'strength': str, 'target_fps': int, 'active': bool}
        """
        result = {'strength': 'off', 'target_fps': 60, 'active': False}
        if not self.mpv_handle or self._terminated:
            return result
        try:
            vf = self._get_mpv_property_string('vf')
            if not vf:
                return result
            import json
            data = json.loads(vf) if isinstance(vf, str) else vf
            for item in data.get('vf', []):
                label = item.get('label', '') or ''
                if label != 'iptv_mc':
                    continue
                graph = (item.get('params', {}) or {}).get('graph', '') or ''
                if 'minterpolate' not in graph:
                    continue
                result['active'] = True
                # 解析 fps
                import re
                m = re.search(r'fps=(\d+)', graph)
                if m:
                    result['target_fps'] = int(m.group(1))
                # 解析强度
                if 'mi_mode=blend' in graph:
                    result['strength'] = 'low'
                elif 'me=hexbs' in graph:
                    result['strength'] = 'high'
                elif 'mi_mode=mci' in graph:
                    result['strength'] = 'medium'
                break
        except Exception as _e:
            global_logger.debug(f"unexpected error: {_e}")
        return result

    def clear_motion_compensation(self) -> bool:
        """清除运动补偿滤镜"""
        if not self.mpv_handle or self._terminated:
            return False
        try:
            self.send_command(['vf', 'remove', '@iptv_mc'])
            self.logger.info("运动补偿滤镜已移除")
            return True
        except Exception:
            return False

    # ---------- 分辨率提升（mpv scale 属性 + lavfi unsharp 滤镜） ----------
    # 使用 MPV 内置 scale/cscale/dscale 属性控制缩放算法
    # 使用 lavfi unsharp 滤镜进行细节增强
    # 滤镜标签：@iptv_sr
    #
    # 缩放算法选项（mpv scale 属性）：
    #   bilinear        — 双线性（最快，质量一般）
    #   bicubic         — 双三次（常用，质量较好）
    #   lanczos         — Lanczos（高质量，锐利）
    #   spline          — 样条（高质量，平滑）
    #   ewa_lanczos     — EWA Lanczos（高质量，适合放大）
    #   ewa_lanczossharp— EWA Lanczos Sharp（最佳质量，最锐利）
    #
    # 细节增强：unsharp 滤镜 amount 参数（0-100 映射到 0.0-1.5）
    #
    # 注意：scale/cscale 属性不需要 copy-back 硬解，GPU 渲染管线直接处理。
    #       unsharp lavfi 滤镜需要 copy-back 硬解或软解。

    # 缩放算法选项
    _SCALE_OPTIONS = ('bilinear', 'bicubic', 'lanczos', 'spline', 'ewa_lanczos', 'ewa_lanczossharp')

    def set_super_resolution(self, scale_algo: str = 'off', detail_enhance: int = 0) -> bool:
        """设置分辨率提升

        :param scale_algo: 缩放算法
            'off' / 'bilinear' / 'bicubic' / 'lanczos' / 'spline' / 'ewa_lanczos' / 'ewa_lanczossharp'
        :param detail_enhance: 细节增强强度（0-100，0=关闭）
        :return: 成功与否
        """
        if not self.mpv_handle or self._terminated:
            return False

        success = True

        # 1. 设置缩放算法（mpv 属性，不需要 copy-back）
        if scale_algo in self._SCALE_OPTIONS:
            # 4K+ 视频下 EWA Lanczos 系列对 GPU 压力极大，自动降级为 lanczos
            if self._is_4k_or_above() and scale_algo in ('ewa_lanczos', 'ewa_lanczossharp'):
                self.logger.info(
                    f"4K+ 视频检测到 {scale_algo}，自动降级为 lanczos 以保证流畅度"
                )
                scale_algo = 'lanczos'
            ret1 = self._set_mpv_string('scale', scale_algo)
            ret2 = self._set_mpv_string('cscale', scale_algo)
            self._set_mpv_string('dscale', scale_algo if scale_algo != 'ewa_lanczossharp' else 'ewa_lanczos')
            if ret1 < 0 or ret2 < 0:
                self.logger.warning(f"缩放算法设置失败: scale={scale_algo}")
                success = False
            else:
                self.logger.info(f"缩放算法已设置: {scale_algo}")
        elif scale_algo == 'off':
            # 恢复默认
            self._set_mpv_string('scale', 'bilinear')
            self._set_mpv_string('cscale', 'bilinear')
            self._set_mpv_string('dscale', 'bilinear')
            self.logger.info("缩放算法已恢复默认")
        else:
            self.logger.warning(f"未知缩放算法: {scale_algo}")
            success = False

        # 2. 设置细节增强（unsharp lavfi 滤镜）
        try:
            self.send_command(['vf', 'remove', '@iptv_sr'])
        except Exception as _e:
            global_logger.debug(f"unexpected error: {_e}")

        detail = max(0, min(100, int(detail_enhance)))
        if detail > 0:
            # unsharp=luma_msize=5:luma_amount=X:chroma_msize=5:chroma_amount=0
            # amount 范围 0.0~1.5，映射 detail 0-100
            amount = round(detail / 100.0 * 1.5, 3)
            # 4K+ 视频下 unsharp 是 CPU 端滤镜，先降采样再处理
            if self._is_4k_or_above():
                filter_str = (
                    f'@iptv_sr:lavfi=['
                    f'scale=1920:1080:flags=fast_bilinear,'
                    f'unsharp=5:5:{amount}:5:5:0.0'
                    f']'
                )
                self.logger.info(
                    f"4K+ 视频检测到，细节增强已降采样到 1080p 处理: detail={detail}"
                )
            else:
                filter_str = f'@iptv_sr:lavfi=[unsharp=5:5:{amount}:5:5:0.0]'
            ret = self.send_command(['vf', 'add', filter_str])
            if ret != 0:
                cur_hwdec = ''
                try:
                    cur_hwdec = self._get_mpv_property_string('hwdec') or ''
                except Exception as _e:
                    global_logger.debug(f"unexpected error: {_e}")
                self.logger.warning(
                    f"细节增强滤镜添加失败(ret={ret})，detail={detail}，"
                    f"当前 hwdec='{cur_hwdec}'。"
                    f"若为原生硬解(auto)，请在播放设置中改为 copy-back(auto-copy) 或软解(no)"
                )
                success = False
            else:
                self.logger.info(f"细节增强滤镜已添加: detail={detail} (amount={amount})")

        return success

    def get_super_resolution(self) -> dict:
        """读取当前分辨率提升设置

        :return: {'scale_algo': str, 'detail_enhance': int, 'active': bool}
        """
        result = {'scale_algo': 'off', 'detail_enhance': 0, 'active': False}
        if not self.mpv_handle or self._terminated:
            return result

        # 读取 scale 属性
        scale_val = self._get_mpv_property_string('scale') or 'bilinear'
        if scale_val in self._SCALE_OPTIONS:
            result['scale_algo'] = scale_val
            if scale_val != 'bilinear':
                result['active'] = True

        # 读取 unsharp 滤镜
        try:
            vf = self._get_mpv_property_string('vf')
            if vf:
                import json
                data = json.loads(vf) if isinstance(vf, str) else vf
                for item in data.get('vf', []):
                    label = item.get('label', '') or ''
                    if label != 'iptv_sr':
                        continue
                    graph = (item.get('params', {}) or {}).get('graph', '') or ''
                    if 'unsharp' in graph:
                        import re
                        m = re.search(r'5:5:([\d.]+)', graph)
                        if m:
                            amount = float(m.group(1))
                            result['detail_enhance'] = int(round(amount / 1.5 * 100))
                            result['active'] = True
                    break
        except Exception as _e:
            global_logger.debug(f"unexpected error: {_e}")
        return result

    def clear_super_resolution(self) -> bool:
        """清除分辨率提升（恢复默认缩放算法 + 移除细节增强滤镜）"""
        if not self.mpv_handle or self._terminated:
            return False
        # 恢复默认缩放
        self._set_mpv_string('scale', 'bilinear')
        self._set_mpv_string('cscale', 'bilinear')
        self._set_mpv_string('dscale', 'bilinear')
        # 移除滤镜
        try:
            self.send_command(['vf', 'remove', '@iptv_sr'])
            self.logger.info("分辨率提升已清除（缩放恢复默认，细节增强已移除）")
            return True
        except Exception:
            return False

    # ---------- 用户着色器（GLSL Shader，GPU 加速 AI 超分辨率） ----------
    # 使用 MPV 的 glsl-shaders 属性加载自定义 GLSL 着色器
    # 常用着色器：
    #   - RAVU (Rule-based Artificial Vector Upscaling) — 锐利放大
    #   - FSRCNNX — 快速超分辨率卷积神经网络
    #   - Anime4K — 动画专用增强
    #   - KrigBilateral — 色度升频
    #   - SSimDownscaler — 高质量降频
    #
    # 着色器文件放在 shaders/ 目录下，用户可自行下载放置
    # MPV 通过 glsl-shaders 属性（逗号分隔路径）加载，运行时可动态切换
    # 注意：着色器在 GPU 渲染管线运行，不需要 copy-back 硬解

    # 内置着色器预设（预设名 → 描述）
    _SHADER_PRESETS = {
        'off': '关闭着色器',
        'ravu': 'RAVU 锐利放大',
        'fsrcnnx': 'FSRCNNX 超分辨率',
        'anime4k': 'Anime4K 动画增强',
        'krig': 'KrigBilateral 色度升频',
        'ssim': 'SSim 降频',
    }

    # 预设对应的着色器文件列表（多文件用逗号分隔加载）
    _SHADER_PRESET_FILES = {
        'ravu': ['ravu_r3.hook'],
        'fsrcnnx': ['FSRCNNX_x2_8-0-4-1.glsl'],
        'anime4k': [
            'Anime4K_Clamp_Highlights.glsl',
            'Anime4K_Restore_CNN_S.glsl',
            'Anime4K_Upscale_CNN_x2_S.glsl',
        ],
        'krig': ['KrigBilateral.hook'],
        'ssim': ['SSimDownscaler.glsl'],
        # 第三阶段：ESRGAN 高质量模式（组合多个着色器实现高质量超分）
        # ESRGAN 本身需要神经网络推理，此处使用高质量 GLSL 着色器组合模拟
        'esrgan': [
            'ravu_r4.hook',
            'FSRCNNX_x2_8-0-4-1.glsl',
            'adaptive_sharpen.glsl',
        ],
        'adaptive_sharpen': ['adaptive_sharpen.glsl'],
    }

    def _get_shaders_dir(self) -> str:
        """获取着色器目录路径"""
        # 优先使用程序目录下的 shaders/
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        shaders_dir = os.path.join(base, 'shaders')
        if not os.path.isdir(shaders_dir):
            try:
                os.makedirs(shaders_dir, exist_ok=True)
            except Exception:
                pass
        return shaders_dir

    def _find_shader_files(self, preset: str) -> list:
        """查找预设对应的所有着色器文件路径

        :return: 文件路径列表（可能多个，如 Anime4K 需要 3 个文件）
        """
        if preset == 'off':
            return []
        shaders_dir = self._get_shaders_dir()
        if not os.path.isdir(shaders_dir):
            return []

        # 1. 如果预设名在 _SHADER_PRESET_FILES 中，按精确文件名查找
        if preset in self._SHADER_PRESET_FILES:
            paths = []
            for fname in self._SHADER_PRESET_FILES[preset]:
                path = os.path.join(shaders_dir, fname)
                if os.path.isfile(path):
                    paths.append(path)
            if paths:
                return paths

        # 2. 回退：前缀匹配查找单个文件
        extensions = ('.glsl', '.hook', '.glsl.hook')
        for ext in extensions:
            # 精确匹配：preset.ext
            path = os.path.join(shaders_dir, f'{preset}{ext}')
            if os.path.isfile(path):
                return [path]
            # 前缀匹配：preset_*.ext
            for fname in os.listdir(shaders_dir):
                if fname.lower().startswith(preset.lower()) and fname.lower().endswith(ext):
                    return [os.path.join(shaders_dir, fname)]
        return []

    def list_available_shaders(self) -> list:
        """列出可用的着色器文件

        :return: [{'preset': str, 'path': str, 'filename': str}]
        """
        result = []
        shaders_dir = self._get_shaders_dir()
        if not os.path.isdir(shaders_dir):
            return result
        for fname in sorted(os.listdir(shaders_dir)):
            if not fname.lower().endswith(('.glsl', '.hook')):
                continue
            path = os.path.join(shaders_dir, fname)
            if not os.path.isfile(path):
                continue
            # 从文件名提取预设名
            name_base = fname
            for ext in ('.glsl.hook', '.glsl', '.hook'):
                if name_base.lower().endswith(ext):
                    name_base = name_base[:-len(ext)]
                    break
            result.append({
                'preset': name_base,
                'path': path,
                'filename': fname,
            })
        return result

    def set_user_shader(self, preset: str) -> bool:
        """设置用户着色器

        :param preset: 预设名（'off'/'ravu'/'fsrcnnx'/'anime4k'/'krig'/'ssim'）
                       或自定义文件路径
        :return: 成功与否
        """
        if not self.mpv_handle or self._terminated:
            return False

        if preset == 'off' or not preset:
            ret = self._set_mpv_string('glsl-shaders', '')
            if ret >= 0:
                self.logger.info("用户着色器已清除")
                return True
            return False

        # 判断是预设名还是文件路径
        if os.path.isfile(preset):
            shader_paths = [preset]
        else:
            shader_paths = self._find_shader_files(preset)

        if not shader_paths:
            self.logger.warning(
                f"着色器文件未找到: preset='{preset}'，"
                f"请在 shaders/ 目录放置对应文件"
            )
            return False

        # MPV glsl-shaders 属性接受逗号分隔的多个路径
        shader_str = ','.join(shader_paths)
        ret = self._set_mpv_string('glsl-shaders', shader_str)
        if ret < 0:
            self.logger.warning(f"着色器设置失败: paths='{shader_str}'")
            return False
        self.logger.info(f"用户着色器已加载: {preset} -> {shader_str}")
        return True

    def get_user_shader(self) -> str:
        """读取当前着色器路径"""
        if not self.mpv_handle or self._terminated:
            return ''
        return self._get_mpv_property_string('glsl-shaders') or ''

    def clear_user_shader(self) -> bool:
        """清除用户着色器"""
        if not self.mpv_handle or self._terminated:
            return False
        ret = self._set_mpv_string('glsl-shaders', '')
        if ret >= 0:
            self.logger.info("用户着色器已清除")
            return True
        return False

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
        except Exception as _e:
            global_logger.debug(f"unexpected error: {_e}")
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
        except Exception as _e:
            global_logger.debug(f"unexpected error: {_e}")
        return result

    # ---------- 音频系统增强（audio-delay/device/channels/pitch/equalizer） ----------
    # mpv 属性：
    # - audio-delay：秒（-10~10，默认 0）
    # - audio-pitch-correction：Flag（yes/no，默认 yes），控制变速时是否自动修正音调。
    #   注意：mpv 没有直接的"变调不变速"浮点属性，此处保留 0.0~2.0 接口仅用于 UI 兼容，
    #   实际设置时 >=0.5 映射为 yes、<0.5 映射为 no。
    # - audio-channels：字符串（auto/mono/1.0/2.0/2.1/5.1/7.1 等）
    # - audio-device：字符串
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

    # ---------- 声道信息检测 + 声道活动状态监控（astats 滤镜） ----------
    # FFmpeg 标准声道布局 → 声道名称列表
    CHANNEL_LAYOUT_MAP = {
        'mono':   ['FC'],
        '1.0':    ['FC'],
        'stereo': ['FL', 'FR'],
        '2.0':    ['FL', 'FR'],
        '2.1':    ['FL', 'FR', 'LFE'],
        '3.0':    ['FL', 'FR', 'FC'],
        '4.0':    ['FL', 'FR', 'FC', 'BC'],
        'quad':   ['FL', 'FR', 'BL', 'BR'],
        '5.0':    ['FL', 'FR', 'FC', 'BL', 'BR'],
        '5.1':    ['FL', 'FR', 'FC', 'LFE', 'BL', 'BR'],
        '6.0':    ['FL', 'FR', 'FC', 'BC', 'SL', 'SR'],
        '6.1':    ['FL', 'FR', 'FC', 'LFE', 'BC', 'SL', 'SR'],
        '7.0':    ['FL', 'FR', 'FC', 'BL', 'BR', 'SL', 'SR'],
        '7.1':    ['FL', 'FR', 'FC', 'LFE', 'BL', 'BR', 'SL', 'SR'],
    }

    CHANNEL_DISPLAY = {
        'FL':  '左前',
        'FR':  '右前',
        'FC':  '中置',
        'LFE': '低音炮',
        'BL':  '左环绕',
        'BR':  '右环绕',
        'BC':  '后中置',
        'SL':  '左侧',
        'SR':  '右侧',
    }

    def get_audio_channel_info(self) -> dict:
        """获取当前音频声道信息
        返回: {'layout': '5.1', 'channels': ['FL','FR','FC','LFE','BL','BR'], 'count': 6}
        """
        layout = self._get_mpv_property_string('audio-params/channel-layout') or ''
        count = self._get_mpv_property_double('audio-params/channel-count') or 0
        # 规范化布局字符串
        layout_lower = layout.lower().strip()
        channels = self.CHANNEL_LAYOUT_MAP.get(layout_lower, [])
        if not channels and count > 0:
            # 未知布局但有声道数，尝试按数量推断
            if count == 1:
                channels = ['FC']
                layout_lower = 'mono'
            elif count == 2:
                channels = ['FL', 'FR']
                layout_lower = 'stereo'
            elif count >= 6:
                channels = ['FL', 'FR', 'FC', 'LFE', 'BL', 'BR']
                layout_lower = '5.1'
            elif count >= 3:
                channels = ['FL', 'FR', 'FC']
                layout_lower = '3.0'
        return {
            'layout': layout_lower or 'stereo',
            'channels': channels,
            'count': len(channels) if channels else int(count),
        }

    def start_channel_monitor(self) -> bool:
        """启动声道活动监控（添加 astats 滤镜）
        astats 滤镜将各声道 RMS 电平写入 metadata，通过 af-metadata 读取。
        reset=1 使每帧重置统计，输出瞬时 RMS 电平（VU 表所需）。
        """
        if not self.mpv_handle or self._terminated:
            return False
        # 先移除旧的 astats 滤镜
        try:
            self.send_command(['af', 'remove', '@iptv_stats'])
        except Exception as _e:
            global_logger.debug(f"unexpected error: {_e}")
        return self.send_command(
            ['af', 'add', '@iptv_stats:lavfi=[astats=metadata=1:reset=1]']
        ) == 0

    def stop_channel_monitor(self):
        """停止声道活动监控（移除 astats 滤镜）"""
        if not self.mpv_handle or self._terminated:
            return
        try:
            self.send_command(['af', 'remove', '@iptv_stats'])
        except Exception as _e:
            global_logger.debug(f"unexpected error: {_e}")

    def get_channel_levels(self) -> dict:
        """获取各声道 RMS 电平
        返回: {声道序号(1-based): 电平dB}
        电平为 -inf 或极低值表示该声道无声。
        """
        if not self.mpv_handle or self._terminated:
            return {}
        try:
            # 尝试直接读取带标签的 metadata
            data = _mpv_get_property_node(
                self.mpv_handle, 'af-metadata/@iptv_stats'
            )
            # 如果带 @ 的路径失败，尝试不带 @
            if not data or not isinstance(data, dict):
                data = _mpv_get_property_node(
                    self.mpv_handle, 'af-metadata/iptv_stats'
                )
            # 如果仍然失败，读取全部 af-metadata 再查找
            if not data or not isinstance(data, dict):
                all_meta = _mpv_get_property_node(
                    self.mpv_handle, 'af-metadata'
                )
                if all_meta and isinstance(all_meta, dict):
                    data = all_meta.get('iptv_stats') or all_meta.get('@iptv_stats') or {}
                if not data and all_meta is not None:
                    global_logger.debug(
                        f"af-metadata full: {all_meta}"
                    )
            if not data or not isinstance(data, dict):
                return {}
            result = {}
            for key, val in data.items():
                # 格式: lavfi.astats.1.RMS_level
                if key.startswith('lavfi.astats.') and key.endswith('.RMS_level'):
                    parts = key.split('.')
                    if len(parts) == 4 and parts[2].isdigit():
                        ch_idx = int(parts[2])
                        try:
                            level = float(val)
                            result[ch_idx] = level
                        except (ValueError, TypeError):
                            pass
            if not result:
                global_logger.debug(
                    f"af-metadata keys: {list(data.keys()) if data else 'empty'}"
                )
            return result
        except Exception as _e:
            global_logger.debug(f"unexpected error: {_e}")
            return {}

    def set_audio_pitch(self, v: float) -> bool:
        """设置音调补偿。
        注意：audio-pitch-correction 是 mpv Flag（yes/no），不是浮点。
        保留 0.0~2.0 接口仅用于 UI 兼容：>=0.5 映射 yes，<0.5 映射 no。
        """
        v = max(0.0, min(2.0, float(v)))
        flag_val = 'yes' if v >= 0.5 else 'no'
        return self._set_mpv_string('audio-pitch-correction', flag_val) >= 0

    def get_audio_pitch(self) -> float:
        """读取音调补偿（UI 兼容：yes→1.0，no→0.0）"""
        v = self._get_mpv_property_string('audio-pitch-correction')
        if v and v.lower() in ('yes', 'true', '1'):
            return 1.0
        return 0.0

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
        except Exception as _e:
            global_logger.debug(f"unexpected error: {_e}")
        return [0.0] * 10

    def _apply_audio_eq_filter(self, gains: list) -> bool:
        """内部：应用均衡器 af 滤镜"""
        if not self.mpv_handle or self._terminated:
            return False
        # 先移除已有的 eq 滤镜
        try:
            self.send_command(['af', 'remove', '@iptv_eq'])
        except Exception as _e:
            global_logger.debug(f"unexpected error: {_e}")
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
        except Exception as _e:
            global_logger.debug(f"unexpected error: {_e}")

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
        except Exception as _e:
            global_logger.debug(f"unexpected error: {_e}")

    def update_osd_theme(self):
        self._apply_osd_colors()

    @staticmethod
    def detect_hdr_type(colormatrix: str, gamma: str, sig_peak: float,
                        video_format: str = '', primaries: str = '') -> str:
        """统一 HDR 类型检测逻辑（PC/Android/Web 三端共用此算法）。

        检测优先级：DV → PQ(HDR10) → HLG → WCG → SDR

        注意：
        - mpv 运行时无法区分 HDR10 与 HDR10+（ST.2094-40 动态元数据不暴露为属性），
          统一返回 'HDR10'。HDR10+ 的检测仅在 ffprobe 扫描阶段通过 side_data 完成。
        - libmpv 无法解码 DV RPU 增强层，只能播放 HDR10 基础层。
          检测到 DV 时返回 'DV'，由 UI 层标注 "(基础层)"。
        - WCG（宽色域 SDR）：BT.2020 色域 + SDR 亮度，需要保持广色域避免压缩偏色。
        - sig_peak 用于辅助判断（mpv 中 1.0≈SDR 白电平，HDR 内容通常 >1.0），
          但不作为 HDR10/HDR10+ 的区分依据。

        Args:
            colormatrix: 色彩矩阵（如 bt.709/bt.2020），来自 video-params/colormatrix
            gamma: 传输特性（如 pq/smpte2084/hlg/arib-std-b67/srgb/bt.1886）
            sig_peak: 信号峰值（mpv video-params/sig-peak，1.0≈SDR白）
            video_format: 视频格式/编解码器（如 hevc/dvhe/dav1）
            primaries: 色彩原色（如 bt.709/bt.2020），来自 video-params/primaries
        """
        g = (gamma or '').lower()
        vf = (video_format or '').lower()
        cm = (colormatrix or '').lower()
        prim = (primaries or '').lower()

        # 杜比视界检测：编解码器标记 dvhe/dvh1/dav1/dovi/dolby_vision
        has_dovi = ('dovi' in vf or 'dolbyvision' in vf or 'dolby_vision' in vf
                    or 'dvhe' in vf or 'dvh1' in vf or 'dav1' in vf or 'dvc' in vf)

        # PQ 视频（HDR10 / HDR10+）：SMPTE ST 2084 (PQ) EOTF
        is_pq = 'pq' in g or 'smpte2084' in g
        # HLG 视频：ARIB STD-B67 (HLG)
        is_hlg = 'hlg' in g or 'arib-std-b67' in g
        # BT.2020 色域检测（从 colormatrix 或 primaries 判断）
        is_bt2020 = ('bt.2020' in cm or 'bt2020' in cm or 'bt.2100' in cm or
                     'bt.2020' in prim or 'bt2020' in prim or 'bt.2100' in prim)

        # DV 优先（DV 流通常也带 PQ 基础层，但标记为 DV 更准确）
        if has_dovi:
            return 'DV'
        # PQ → HDR10（运行时无法区分 HDR10+，hdr10-opt=yes 会自动传递动态元数据）
        if is_pq:
            return 'HDR10'
        # HLG
        if is_hlg:
            return 'HLG'
        # WCG：BT.2020 色域 + SDR 亮度（非 HDR），sig_peak 辅助排除极少数高亮度 SDR
        if is_bt2020 and sig_peak <= 1.0:
            return 'WCG'
        # BT.2020 + 高 sig_peak 但 gamma 未标记 → 可能是未正确标记的 HLG
        if is_bt2020 and sig_peak > 1.0:
            return 'HLG'
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
                except Exception as _e:
                    global_logger.debug(f"unexpected error: {_e}")
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
