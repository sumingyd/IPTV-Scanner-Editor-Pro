import ctypes
import os
import sys
import locale

from core.log_manager import global_logger as logger
from utils.platform_utils import find_libmpv_path, find_libmpv_paths, get_libmpv_filename, is_macos, is_linux, is_android

_mpv_loaded = False

libmpv_path = find_libmpv_path()

# mpv_dir 从实际找到的 libmpv_path 推导（dll/so 所在目录），
# 而不是固定用 base_path/mpv。这样当 _MEIPASS/mpv/libmpv-2.dll 丢失时，
# 能从 exe 同级目录的 mpv/ 找到 dll，并正确设置 MPV_HOME 和 PATH。
if libmpv_path and os.path.exists(libmpv_path):
    os.environ['MPV_LIBRARY'] = libmpv_path
    mpv_dir = os.path.dirname(libmpv_path)
else:
    # 备用：使用默认 mpv_dir（base_path/mpv）
    if getattr(sys, 'frozen', False):
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    else:
        from models.channel_mappings import get_app_data_dir
        base_path = get_app_data_dir()
    mpv_dir = os.path.join(base_path, 'mpv')
    logger.warning(f"未找到libmpv库: {libmpv_path}")

os.environ['MPV_HOME'] = mpv_dir
os.environ['PATH'] = mpv_dir + os.pathsep + os.environ.get('PATH', '')

if is_macos() and os.path.isdir(mpv_dir):
    existing = os.environ.get('DYLD_LIBRARY_PATH', '')
    if mpv_dir not in existing:
        os.environ['DYLD_LIBRARY_PATH'] = mpv_dir + (os.pathsep + existing if existing else '')

MPV_AVAILABLE = False
libmpv = None
_mpv_loaded = False
_last_load_error = ""  # 最后一次加载失败的诊断信息（供 UI 层读取并展示给用户）


def _is_mpv_available():
    _ensure_libmpv_loaded()
    return MPV_AVAILABLE


def _ensure_libmpv_loaded():
    global libmpv, MPV_AVAILABLE, _mpv_loaded, libmpv_path, _last_load_error
    if _mpv_loaded:
        return MPV_AVAILABLE

    if is_linux() or is_android():
        try:
            locale.setlocale(locale.LC_NUMERIC, "C")
        except Exception:
            pass

    # 逐一尝试所有候选路径：文件可能存在但损坏（UPX 解压损坏、杀毒软件拦截、依赖缺失），
    # ctypes.CDLL 失败时继续尝试下一个路径（exe 同级 mpv/ 目录等 fallback）
    candidate_paths = find_libmpv_paths()
    last_error = None
    for path in candidate_paths:
        if not path or not os.path.exists(path):
            continue
        try:
            # Windows 上先添加 DLL 所在目录到搜索路径，
            # 确保 libmpv-2.dll 的依赖 DLL（如 MinGW 运行时、VC++ Runtime）能被找到。
            # Python 3.8+ 不再使用 PATH 搜索 DLL，必须显式调用 os.add_dll_directory。
            if is_windows():
                dll_dir = os.path.dirname(os.path.abspath(path))
                try:
                    os.add_dll_directory(dll_dir)
                except Exception:
                    pass
            libmpv = ctypes.CDLL(path)

            libmpv.mpv_create.restype = ctypes.c_void_p
            libmpv.mpv_create.argtypes = []

            libmpv.mpv_initialize.restype = ctypes.c_int
            libmpv.mpv_initialize.argtypes = [ctypes.c_void_p]

            libmpv.mpv_set_option_string.restype = ctypes.c_int
            libmpv.mpv_set_option_string.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p]

            libmpv.mpv_set_property_string.restype = ctypes.c_int
            libmpv.mpv_set_property_string.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p]

            libmpv.mpv_set_property.restype = ctypes.c_int
            libmpv.mpv_set_property.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int, ctypes.c_void_p]

            libmpv.mpv_command.restype = ctypes.c_int
            libmpv.mpv_command.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_char_p)]

            libmpv.mpv_destroy.restype = None
            libmpv.mpv_destroy.argtypes = [ctypes.c_void_p]

            libmpv.mpv_terminate_destroy.restype = None
            libmpv.mpv_terminate_destroy.argtypes = [ctypes.c_void_p]

            libmpv.mpv_observe_property.restype = ctypes.c_int
            libmpv.mpv_observe_property.argtypes = [ctypes.c_void_p, ctypes.c_uint64, ctypes.c_char_p, ctypes.c_int]

            libmpv.mpv_set_wakeup_callback.restype = None
            libmpv.mpv_set_wakeup_callback.argtypes = [ctypes.c_void_p, ctypes.CFUNCTYPE(None, ctypes.c_void_p), ctypes.c_void_p]

            libmpv.mpv_wait_event.restype = ctypes.c_void_p
            libmpv.mpv_wait_event.argtypes = [ctypes.c_void_p, ctypes.c_double]

            libmpv.mpv_get_property_string.restype = ctypes.c_void_p
            libmpv.mpv_get_property_string.argtypes = [ctypes.c_void_p, ctypes.c_char_p]

            libmpv.mpv_free.restype = None
            libmpv.mpv_free.argtypes = [ctypes.c_void_p]

            libmpv.mpv_get_property.restype = ctypes.c_int
            libmpv.mpv_get_property.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int, ctypes.c_void_p]

            libmpv.mpv_request_log_messages.restype = ctypes.c_int
            libmpv.mpv_request_log_messages.argtypes = [ctypes.c_void_p, ctypes.c_char_p]

            # 加载成功：更新 libmpv_path 和环境变量，确保后续使用正确的路径
            libmpv_path = path
            os.environ['MPV_LIBRARY'] = path
            mpv_dir = os.path.dirname(path)
            os.environ['MPV_HOME'] = mpv_dir
            os.environ['PATH'] = mpv_dir + os.pathsep + os.environ.get('PATH', '')
            MPV_AVAILABLE = True
            _mpv_loaded = True
            return True
        except OSError as e:
            last_error = e
            # Windows 上从 winerror 提取详细错误码，区分"依赖缺失"和"文件损坏"
            winerror = getattr(e, 'winerror', None)
            if winerror == 126:
                # ERROR_MOD_NOT_FOUND: 文件存在但依赖的 DLL 缺失（通常是 VC++ Runtime）
                logger.warning(f"libmpv加载失败（依赖DLL缺失，可能是VC++ Runtime未安装）: {path} -> winerror={winerror}")
            elif winerror == 193:
                # ERROR_BAD_EXE_FORMAT: 架构不匹配（32/64位）
                logger.warning(f"libmpv加载失败（架构不匹配）: {path} -> winerror={winerror}")
            elif winerror == 5:
                # ERROR_ACCESS_DENIED: 杀毒软件拦截或权限不足
                logger.warning(f"libmpv加载失败（访问被拒绝，可能是杀毒软件拦截）: {path} -> winerror={winerror}")
            else:
                logger.warning(f"libmpv路径加载失败，尝试下一个: {path} -> winerror={winerror}, {e}")
            continue
        except Exception as e:
            last_error = e
            logger.warning(f"libmpv路径加载失败，尝试下一个: {path} -> {e}")
            continue

    # 所有路径均失败：输出诊断信息
    logger.error(f"加载libmpv失败（所有候选路径均失败）: {last_error}")
    diag_msg = "libmpv加载失败"
    if is_windows():
        winerror = getattr(last_error, 'winerror', None) if last_error else None
        if winerror == 126:
            # ERROR_MOD_NOT_FOUND: 检查 VC++ Runtime 是否存在并提供解决建议
            system_dir = os.path.join(os.environ.get('SystemRoot', r'C:\Windows'), 'System32')
            vcruntime_files = ['MSVCP140.dll', 'VCRUNTIME140.dll', 'VCRUNTIME140_1.dll']
            missing = [f for f in vcruntime_files if not os.path.exists(os.path.join(system_dir, f))]
            if missing:
                diag_msg = (f"libmpv加载失败：Visual C++ Runtime 缺失（缺少 {', '.join(missing)}）。"
                            f"请安装 VC++ Redistributable: https://aka.ms/vs/17/release/vc_redist.x64.exe")
                logger.error(f"诊断: {diag_msg}")
            else:
                diag_msg = ("libmpv加载失败：依赖 DLL 缺失（VC++ Runtime 已安装，"
                            "可能是其他依赖项问题）。建议重新下载程序或安装 mpv 播放器。")
                logger.error(f"诊断: {diag_msg}")
        elif winerror == 193:
            diag_msg = "libmpv加载失败：架构不匹配，请确认使用 64 位 Windows 系统。"
            logger.error(f"诊断: {diag_msg}")
        elif winerror == 5:
            diag_msg = "libmpv加载失败：访问被拒绝，可能是杀毒软件拦截。请将程序加入白名单。"
            logger.error(f"诊断: {diag_msg}")
        else:
            diag_msg = f"libmpv加载失败（winerror={winerror}）: {last_error}"
            logger.error(f"诊断: {diag_msg}")
    _last_load_error = diag_msg
    _mpv_loaded = False
    return False


class mpv_event(ctypes.Structure):
    _fields_ = [
        ('event_id', ctypes.c_int),
        ('error', ctypes.c_int),
        ('reply_userdata', ctypes.c_uint64),
        ('data', ctypes.c_void_p)
    ]


class mpv_event_end_file(ctypes.Structure):
    _fields_ = [
        ('reason', ctypes.c_int),
        ('error', ctypes.c_int),
        ('playlist_entry_id', ctypes.c_int64),
        ('playlist_insert_id', ctypes.c_int64),
        ('playlist_insert_num_entries', ctypes.c_int),
    ]


class mpv_event_property(ctypes.Structure):
    _fields_ = [
        ('name', ctypes.c_char_p),
        ('format', ctypes.c_int),
        ('data', ctypes.c_void_p),
    ]


class mpv_event_log_message(ctypes.Structure):
    """mpv 日志消息事件结构体（MPV_EVENT_LOG_MESSAGE）"""
    _fields_ = [
        ('prefix', ctypes.c_char_p),   # 模块前缀，如 "demuxer"、"vd"
        ('level', ctypes.c_char_p),    # 级别，如 "debug"、"warn"、"error"
        ('text', ctypes.c_char_p),     # 日志文本（含换行符）
    ]


MPV_EVENT_NONE = 0
MPV_EVENT_SHUTDOWN = 1
MPV_EVENT_LOG_MESSAGE = 2
MPV_EVENT_GET_PROPERTY_REPLY = 3
MPV_EVENT_SET_PROPERTY_REPLY = 4
MPV_EVENT_COMMAND_REPLY = 5
MPV_EVENT_START_FILE = 6
MPV_EVENT_END_FILE = 7
MPV_EVENT_FILE_LOADED = 8
MPV_EVENT_IDLE = 11
MPV_EVENT_TICK = 14
MPV_EVENT_CLIENT_MESSAGE = 16
MPV_EVENT_VIDEO_RECONFIG = 17
MPV_EVENT_AUDIO_RECONFIG = 18
MPV_EVENT_SEEK = 20
MPV_EVENT_PLAYBACK_RESTART = 21
MPV_EVENT_PROPERTY_CHANGE = 22
MPV_EVENT_QUEUE_OVERFLOW = 24
MPV_EVENT_HOOK = 25

MPV_FORMAT_NONE = 0
MPV_FORMAT_STRING = 1
MPV_FORMAT_OSD_STRING = 2
MPV_FORMAT_FLAG = 3
MPV_FORMAT_INT64 = 4
MPV_FORMAT_DOUBLE = 5
MPV_FORMAT_NODE = 6

MPV_END_FILE_REASON_EOF = 0
MPV_END_FILE_REASON_STOP = 2
MPV_END_FILE_REASON_QUIT = 3
MPV_END_FILE_REASON_ERROR = 4
MPV_END_FILE_REASON_REDIRECT = 5


def get_property_string(handle, name):
    if not handle or not libmpv:
        return None
    try:
        raw_ptr = libmpv.mpv_get_property_string(handle, name.encode('utf-8'))
        if not raw_ptr:
            return None
        value = ctypes.cast(raw_ptr, ctypes.c_char_p).value.decode('utf-8')
        libmpv.mpv_free(raw_ptr)
        return value
    except Exception:
        return None


def get_property_int(handle, name):
    if not handle or not libmpv:
        return None
    try:
        value = ctypes.c_int64()
        result = libmpv.mpv_get_property(handle, name.encode('utf-8'), MPV_FORMAT_INT64, ctypes.byref(value))
        if result < 0:
            return None
        return value.value
    except Exception:
        return None


def get_property_double(handle, name):
    if not handle or not libmpv:
        return None
    try:
        value = ctypes.c_double()
        result = libmpv.mpv_get_property(handle, name.encode('utf-8'), MPV_FORMAT_DOUBLE, ctypes.byref(value))
        if result < 0:
            return None
        return value.value
    except Exception:
        return None


def create_mpv_handle():
    if not MPV_AVAILABLE or not libmpv:
        return None
    try:
        handle = libmpv.mpv_create()
        return handle if handle else None
    except Exception as e:
        logger.error(f"create_mpv_handle failed: {e}")
        return None


def initialize_mpv(handle):
    if not handle or not libmpv:
        return False
    try:
        return libmpv.mpv_initialize(handle) >= 0
    except Exception as e:
        logger.error(f"initialize_mpv failed: {e}")
        return False


def destroy_mpv(handle):
    if handle and libmpv:
        try:
            libmpv.mpv_destroy(handle)
        except Exception:
            pass


def terminate_destroy_mpv(handle):
    if handle and libmpv:
        try:
            libmpv.mpv_terminate_destroy(handle)
        except Exception:
            try:
                libmpv.mpv_destroy(handle)
            except Exception:
                pass


def set_property_string(handle, name, value):
    if not handle or not libmpv:
        return -1
    try:
        return libmpv.mpv_set_property_string(handle, name.encode('utf-8'), str(value).encode('utf-8'))
    except Exception:
        return -1


def set_property_int64(handle, name, value):
    if not handle or not libmpv:
        return -1
    try:
        v = ctypes.c_int64(int(value))
        return libmpv.mpv_set_property(handle, name.encode('utf-8'), MPV_FORMAT_INT64, ctypes.byref(v))
    except Exception:
        return -1


def set_option_string(handle, name, value):
    if not handle or not libmpv:
        return -1
    try:
        return libmpv.mpv_set_option_string(handle, name.encode('utf-8'), str(value).encode('utf-8'))
    except Exception:
        return -1


def send_command(handle, cmd_parts):
    if not handle or not libmpv:
        return -1
    try:
        cmd = [part.encode('utf-8') if isinstance(part, str) else part for part in cmd_parts] + [None]
        cmd_ptr = (ctypes.c_char_p * len(cmd))(*cmd)
        return libmpv.mpv_command(handle, cmd_ptr)
    except Exception:
        return -1


def wait_for_event(handle, timeout_sec):
    if not handle or not libmpv:
        return None
    try:
        event_ptr = libmpv.mpv_wait_event(handle, timeout_sec)
        if event_ptr:
            return ctypes.cast(event_ptr, ctypes.POINTER(mpv_event)).contents
    except Exception:
        pass
    return None


def wait_for_specific_event(handle, timeout_sec, target_events):
    import time
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        try:
            event_ptr = libmpv.mpv_wait_event(handle, 0.02)
            if event_ptr:
                event = ctypes.cast(event_ptr, ctypes.POINTER(mpv_event)).contents
                if event.event_id in target_events:
                    return event.event_id, event.error, event.data
                if event.event_id == MPV_EVENT_SHUTDOWN:
                    return MPV_EVENT_SHUTDOWN, 0, None
                if event.event_id == MPV_EVENT_NONE:
                    continue
        except Exception:
            break
    return 0, 0, None


def observe_property(handle, reply_userdata, name, fmt):
    if not handle or not libmpv:
        return -1
    try:
        return libmpv.mpv_observe_property(handle, reply_userdata, name.encode('utf-8'), fmt)
    except Exception:
        return -1


_callback_refs = []
_MAX_CALLBACK_REFS = 16


def set_wakeup_callback(handle, callback, data):
    if not handle or not libmpv:
        return
    try:
        _callback_refs.append(callback)
        if len(_callback_refs) > _MAX_CALLBACK_REFS:
            _callback_refs[:] = _callback_refs[-_MAX_CALLBACK_REFS:]
        libmpv.mpv_set_wakeup_callback(handle, callback, data)
    except Exception:
        pass


MPV_RENDER_API_TYPE_OPENGL = b'opengl'
MPV_RENDER_PARAM_INVALID = 0
MPV_RENDER_PARAM_API_TYPE = 1
MPV_RENDER_PARAM_OPENGL_FBO = 2
MPV_RENDER_PARAM_FLIP_Y = 3
MPV_RENDER_PARAM_DEPTH = 4
MPV_RENDER_PARAM_BLOCK_FOR_TARGET_TIME = 11
MPV_RENDER_PARAM_SKIP_RENDERING = 12


class mpv_opengl_fbo(ctypes.Structure):
    _fields_ = [
        ('fbo', ctypes.c_int),
        ('w', ctypes.c_int),
        ('h', ctypes.c_int),
        ('internal_format', ctypes.c_int),
    ]


class mpv_render_param(ctypes.Structure):
    _fields_ = [
        ('type', ctypes.c_int),
        ('data', ctypes.c_void_p),
    ]


_RENDER_CB_REFS = []


def init_render_api():
    if not libmpv:
        return False
    try:
        libmpv.mpv_render_context_create.restype = ctypes.c_int
        libmpv.mpv_render_context_create.argtypes = [
            ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p, ctypes.POINTER(mpv_render_param)
        ]
        libmpv.mpv_render_context_set_parameter.restype = ctypes.c_int
        libmpv.mpv_render_context_set_parameter.argtypes = [
            ctypes.c_void_p, ctypes.POINTER(mpv_render_param)
        ]
        libmpv.mpv_render_context_render.restype = ctypes.c_int
        libmpv.mpv_render_context_render.argtypes = [
            ctypes.c_void_p, ctypes.POINTER(mpv_render_param)
        ]
        libmpv.mpv_render_context_report_swap.restype = None
        libmpv.mpv_render_context_report_swap.argtypes = [ctypes.c_void_p]
        libmpv.mpv_render_context_free.restype = None
        libmpv.mpv_render_context_free.argtypes = [ctypes.c_void_p]
        libmpv.mpv_render_context_set_update_callback.restype = None
        libmpv.mpv_render_context_set_update_callback.argtypes = [
            ctypes.c_void_p,
            ctypes.CFUNCTYPE(None, ctypes.c_void_p),
            ctypes.c_void_p,
        ]
        return True
    except Exception as e:
        logger.error(f"初始化mpv render API失败: {e}")
        return False


def render_context_create(mpv_handle):
    if not libmpv or not mpv_handle:
        return None
    try:
        params = [
            mpv_render_param(MPV_RENDER_PARAM_API_TYPE,
                             ctypes.cast(ctypes.c_char_p(MPV_RENDER_API_TYPE_OPENGL), ctypes.c_void_p)),
            mpv_render_param(MPV_RENDER_PARAM_INVALID, ctypes.c_void_p(0)),
        ]
        ctx = ctypes.c_void_p()
        ret = libmpv.mpv_render_context_create(ctypes.byref(ctx), mpv_handle, params)
        if ret < 0:
            logger.error(f"mpv_render_context_create失败: {ret}")
            return None
        return ctx.value
    except Exception as e:
        logger.error(f"mpv_render_context_create异常: {e}")
        return None


def render_context_render(render_ctx, fbo, width, height, flip_y=False):
    if not libmpv or not render_ctx:
        return -1
    try:
        gl_fbo = mpv_opengl_fbo(fbo=fbo, w=width, h=height, internal_format=0)
        flip = ctypes.c_int(1 if flip_y else 0)
        block = ctypes.c_int(1)
        params = [
            mpv_render_param(MPV_RENDER_PARAM_OPENGL_FBO,
                             ctypes.cast(ctypes.byref(gl_fbo), ctypes.c_void_p)),
            mpv_render_param(MPV_RENDER_PARAM_FLIP_Y,
                             ctypes.cast(ctypes.byref(flip), ctypes.c_void_p)),
            mpv_render_param(MPV_RENDER_PARAM_BLOCK_FOR_TARGET_TIME,
                             ctypes.cast(ctypes.byref(block), ctypes.c_void_p)),
            mpv_render_param(MPV_RENDER_PARAM_INVALID, ctypes.c_void_p(0)),
        ]
        return libmpv.mpv_render_context_render(render_ctx, params)
    except Exception as e:
        logger.error(f"mpv_render_context_render异常: {e}")
        return -1


def render_context_report_swap(render_ctx):
    if libmpv and render_ctx:
        try:
            libmpv.mpv_render_context_report_swap(render_ctx)
        except Exception:
            pass


def render_context_set_update_callback(render_ctx, callback, user_data=None):
    if not libmpv or not render_ctx:
        return
    try:
        _RENDER_CB_REFS.append(callback)
        if len(_RENDER_CB_REFS) > _MAX_CALLBACK_REFS:
            _RENDER_CB_REFS[:] = _RENDER_CB_REFS[-_MAX_CALLBACK_REFS:]
        libmpv.mpv_render_context_set_update_callback(render_ctx, callback, user_data or ctypes.c_void_p(0))
    except Exception as e:
        logger.error(f"mpv_render_context_set_update_callback异常: {e}")


def render_context_free(render_ctx):
    if libmpv and render_ctx:
        try:
            libmpv.mpv_render_context_free(render_ctx)
        except Exception:
            pass
