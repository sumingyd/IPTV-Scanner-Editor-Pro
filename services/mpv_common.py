import ctypes
import os
import sys

from core.log_manager import global_logger as logger

_mpvt_loaded = False

if getattr(sys, 'frozen', False):
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
else:
    from models.channel_mappings import get_app_data_dir
    base_path = get_app_data_dir()

mpv_dir = os.path.join(base_path, 'mpv')
os.environ['MPV_HOME'] = mpv_dir
os.environ['PATH'] = mpv_dir + os.pathsep + os.environ.get('PATH', '')

libmpv_path = os.path.join(mpv_dir, 'libmpv-2.dll')
if os.path.exists(libmpv_path):
    os.environ['MPV_LIBRARY'] = libmpv_path
else:
    logger.warning(f"未找到libmpv-2.dll: {libmpv_path}")

MPV_AVAILABLE = False
libmpv = None
_mpv_loaded = False


def _ensure_libmpv_loaded():
    global libmpv, MPV_AVAILABLE, _mpv_loaded
    if _mpv_loaded:
        return MPV_AVAILABLE
    _mpv_loaded = True

    if not os.path.exists(libmpv_path):
        logger.warning(f"未找到libmpv-2.dll: {libmpv_path}")
        return False

    try:
        libmpv = ctypes.CDLL(libmpv_path)

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

        MPV_AVAILABLE = True
        return True
    except Exception as e:
        logger.error(f"加载libmpv-2.dll失败: {e}")
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
    except Exception:
        return None


def initialize_mpv(handle):
    if not handle or not libmpv:
        return False
    try:
        return libmpv.mpv_initialize(handle) >= 0
    except Exception:
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
                    return event.event_id, event.error
                if event.event_id == MPV_EVENT_SHUTDOWN:
                    return MPV_EVENT_SHUTDOWN, 0
                if event.event_id == MPV_EVENT_NONE:
                    continue
        except Exception:
            break
    return 0, 0


def observe_property(handle, reply_userdata, name, fmt):
    if not handle or not libmpv:
        return -1
    try:
        return libmpv.mpv_observe_property(handle, reply_userdata, name.encode('utf-8'), fmt)
    except Exception:
        return -1


_callback_refs = []


def set_wakeup_callback(handle, callback, data):
    if not handle or not libmpv:
        return
    try:
        _callback_refs.append(callback)
        libmpv.mpv_set_wakeup_callback(handle, callback, data)
    except Exception:
        pass
