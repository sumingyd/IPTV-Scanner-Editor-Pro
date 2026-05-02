import ctypes
import os
import sys

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

MPV_AVAILABLE = False
libmpv = None

try:
    libmpv = ctypes.CDLL(libmpv_path)

    libmpv.mpv_create.restype = ctypes.c_void_p
    libmpv.mpv_create.argtypes = []

    libmpv.mpv_initialize.restype = ctypes.c_int
    libmpv.mpv_initialize.argtypes = [ctypes.c_void_p]

    libmpv.mpv_set_property_string.restype = ctypes.c_int
    libmpv.mpv_set_property_string.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p]

    libmpv.mpv_set_property.restype = ctypes.c_int
    libmpv.mpv_set_property.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int, ctypes.c_void_p]

    libmpv.mpv_command.restype = ctypes.c_int
    libmpv.mpv_command.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_char_p)]

    libmpv.mpv_destroy.restype = None
    libmpv.mpv_destroy.argtypes = [ctypes.c_void_p]

    libmpv.mpv_observe_property.restype = ctypes.c_int
    libmpv.mpv_observe_property.argtypes = [ctypes.c_void_p, ctypes.c_uint64, ctypes.c_char_p, ctypes.c_int]

    libmpv.mpv_set_wakeup_callback.restype = None
    libmpv.mpv_set_wakeup_callback.argtypes = [ctypes.c_void_p, ctypes.CFUNCTYPE(None, ctypes.c_void_p), ctypes.c_void_p]

    libmpv.mpv_wait_event.restype = ctypes.c_void_p
    libmpv.mpv_wait_event.argtypes = [ctypes.c_void_p, ctypes.c_double]

    libmpv.mpv_get_property_string.restype = ctypes.c_char_p
    libmpv.mpv_get_property_string.argtypes = [ctypes.c_void_p, ctypes.c_char_p]

    libmpv.mpv_free.restype = None
    libmpv.mpv_free.argtypes = [ctypes.c_void_p]

    libmpv.mpv_get_property.restype = ctypes.c_int
    libmpv.mpv_get_property.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int, ctypes.c_void_p]

    MPV_AVAILABLE = True
except Exception as e:
    print(f"加载libmpv-2.dll失败: {e}")


class mpv_event(ctypes.Structure):
    _fields_ = [
        ('event_id', ctypes.c_int),
        ('error', ctypes.c_int),
        ('reply_userdata', ctypes.c_uint64),
        ('data', ctypes.c_void_p)
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
MPV_EVENT_CLIENT_MESSAGE = 9
MPV_EVENT_VIDEO_RECONFIG = 10
MPV_EVENT_AUDIO_RECONFIG = 11
MPV_EVENT_SEEK = 12
MPV_EVENT_PLAYBACK_RESTART = 13
MPV_EVENT_PROPERTY_CHANGE = 14
MPV_EVENT_QUEUE_OVERFLOW = 15
MPV_EVENT_ERROR = 16

MPV_FORMAT_STRING = 0
MPV_FORMAT_OSD_STRING = 1
MPV_FORMAT_FLAG = 2
MPV_FORMAT_INT64 = 3
MPV_FORMAT_DOUBLE = 4
MPV_FORMAT_NODE = 5


def get_property_string(handle, name):
    try:
        result = libmpv.mpv_get_property_string(handle, name.encode('utf-8'))
        if not result:
            return None
        return result.decode('utf-8')
    except Exception:
        return None


def get_property_int(handle, name):
    try:
        value = ctypes.c_int64()
        result = libmpv.mpv_get_property(handle, name.encode('utf-8'), MPV_FORMAT_INT64, ctypes.byref(value))
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


def set_property_string(handle, name, value):
    if not handle or not libmpv:
        return -1
    try:
        return libmpv.mpv_set_property_string(handle, name.encode('utf-8'), value.encode('utf-8'))
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
