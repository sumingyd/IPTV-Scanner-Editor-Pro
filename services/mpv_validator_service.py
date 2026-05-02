import ctypes
import os
import sys
import threading
import time
from typing import Dict
from core.log_manager import global_logger

if getattr(sys, 'frozen', False):
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
else:
    from models.channel_mappings import get_app_data_dir
    base_path = get_app_data_dir()

mpv_dir = os.path.join(base_path, 'mpv')
libmpv_path = os.path.join(mpv_dir, 'libmpv-2.dll')

try:
    _libmpv = ctypes.CDLL(libmpv_path)
    _libmpv.mpv_create.restype = ctypes.c_void_p
    _libmpv.mpv_create.argtypes = []
    _libmpv.mpv_initialize.restype = ctypes.c_int
    _libmpv.mpv_initialize.argtypes = [ctypes.c_void_p]
    _libmpv.mpv_set_property_string.restype = ctypes.c_int
    _libmpv.mpv_set_property_string.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p]
    _libmpv.mpv_command.restype = ctypes.c_int
    _libmpv.mpv_command.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_char_p)]
    _libmpv.mpv_destroy.restype = None
    _libmpv.mpv_destroy.argtypes = [ctypes.c_void_p]
    _libmpv.mpv_wait_event.restype = ctypes.c_void_p
    _libmpv.mpv_wait_event.argtypes = [ctypes.c_void_p, ctypes.c_double]
    _libmpv.mpv_get_property_string.restype = ctypes.c_char_p
    _libmpv.mpv_get_property_string.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    _libmpv.mpv_free.restype = None
    _libmpv.mpv_free.argtypes = [ctypes.c_void_p]
    _libmpv.mpv_get_property.restype = ctypes.c_int
    _libmpv.mpv_get_property.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int, ctypes.c_void_p]

    class _mpv_event(ctypes.Structure):
        _fields_ = [
            ('event_id', ctypes.c_int),
            ('error', ctypes.c_int),
            ('reply_userdata', ctypes.c_uint64),
            ('data', ctypes.c_void_p)
        ]

    _MPV_EVENT_FILE_LOADED = 8
    _MPV_EVENT_END_FILE = 7
    _MPV_EVENT_SHUTDOWN = 1
    _MPV_EVENT_START_FILE = 6
    _MPV_FORMAT_INT64 = 3
    _MPV_AVAILABLE = True
except Exception:
    _MPV_AVAILABLE = False


def _create_lightweight_mpv():
    if not _MPV_AVAILABLE:
        return None
    try:
        handle = _libmpv.mpv_create()
        if not handle:
            return None
        _libmpv.mpv_set_property_string(handle, b'vo', b'null')
        _libmpv.mpv_set_property_string(handle, b'ao', b'null')
        _libmpv.mpv_set_property_string(handle, b'hwdec', b'no')
        _libmpv.mpv_set_property_string(handle, b'osc', b'no')
        _libmpv.mpv_set_property_string(handle, b'osd-bar', b'no')
        _libmpv.mpv_set_property_string(handle, b'idle', b'yes')
        _libmpv.mpv_set_property_string(handle, b'ytdl', b'no')
        _libmpv.mpv_set_property_string(handle, b'keep-open', b'yes')
        _libmpv.mpv_set_property_string(handle, b'log-level', b'error')
        _libmpv.mpv_set_property_string(handle, b'config', b'no')
        _libmpv.mpv_set_property_string(handle, b'demuxer-lavf-probesize', b'10000000')
        _libmpv.mpv_set_property_string(handle, b'demuxer-lavf-analyzeduration', b'5000000')

        headers = MpvStreamValidator.get_headers()
        if headers:
            import json
            headers_json = json.dumps(headers).encode('utf-8')
            _libmpv.mpv_set_property_string(handle, b'http-header-fields', headers_json)

        result = _libmpv.mpv_initialize(handle)
        if result < 0:
            _libmpv.mpv_destroy(handle)
            return None
        return handle
    except Exception:
        return None


def _destroy_mpv(handle):
    if handle:
        try:
            _libmpv.mpv_destroy(handle)
        except Exception:
            pass


def _get_property_string(handle, name):
    try:
        result = _libmpv.mpv_get_property_string(handle, name.encode('utf-8'))
        if not result:
            return None
        return result.decode('utf-8')
    except Exception:
        return None


def _get_property_int(handle, name):
    try:
        value = ctypes.c_int64()
        result = _libmpv.mpv_get_property(handle, name.encode('utf-8'), _MPV_FORMAT_INT64, ctypes.byref(value))
        if result < 0:
            return None
        return value.value
    except Exception:
        return None


def _wait_for_event(handle, timeout_sec, target_events):
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        try:
            event_ptr = _libmpv.mpv_wait_event(handle, 0.02)
            if event_ptr:
                event = ctypes.cast(event_ptr, ctypes.POINTER(_mpv_event)).contents
                if event.event_id in target_events:
                    return event.event_id, event.error
                if event.event_id == _MPV_EVENT_SHUTDOWN:
                    return _MPV_EVENT_SHUTDOWN, 0
        except Exception:
            break
    return 0, 0


def get_optimal_thread_count():
    cpu = os.cpu_count() or 4
    return min(max(cpu, 4), 32)


class MpvStreamValidator:
    _semaphore: threading.Semaphore | None = None
    _user_agent: str | None = None
    _referer: str | None = None
    _headers_lock = threading.Lock()

    @classmethod
    def _get_semaphore(cls) -> threading.Semaphore:
        if cls._semaphore is None:
            cls._semaphore = threading.Semaphore(get_optimal_thread_count())
        return cls._semaphore

    def __init__(self, main_window=None):
        self.logger = global_logger
        self.main_window = main_window

    def validate_stream(self, url: str, raw_channel_name: str | None = None, timeout: int = 3) -> Dict:
        result = {
            'url': url,
            'valid': False,
            'latency': None,
            'error': None,
            'error_type': None,
            'service_name': None,
            'resolution': None,
            'codec': None,
            'bitrate': None
        }

        if not _MPV_AVAILABLE:
            result['error'] = 'mpv不可用'
            result['error_type'] = 'mpv_unavailable'
            return result

        sem = self._get_semaphore()
        acquired = sem.acquire(timeout=30)
        if not acquired:
            result['error'] = '并发数超限'
            result['error_type'] = 'concurrency_limit'
            return result

        handle = None
        try:
            handle = _create_lightweight_mpv()
            if not handle:
                result['error'] = '创建mpv实例失败'
                result['error_type'] = 'mpv_create_failed'
                return result

            u = url.lower()
            if u.startswith('rtsp://'):
                _libmpv.mpv_set_property_string(handle, b'rtsp-transport', b'tcp')
            elif '/rtp/' in u or u.endswith('.ts') or u.startswith('udp://'):
                _libmpv.mpv_set_property_string(handle, b'demuxer-lavf-format', b'mpegts')

            start_time = time.time()

            cmd = [b'loadfile', url.encode('utf-8'), None]
            cmd_ptr = (ctypes.c_char_p * len(cmd))(*cmd)
            _libmpv.mpv_command(handle, cmd_ptr)

            event_id, error_code = _wait_for_event(
                handle, timeout,
                {_MPV_EVENT_FILE_LOADED, _MPV_EVENT_END_FILE}
            )

            latency = int((time.time() - start_time) * 1000)

            if event_id == _MPV_EVENT_FILE_LOADED:
                result['valid'] = True
                result['latency'] = latency

                w = _get_property_int(handle, 'width')
                h = _get_property_int(handle, 'height')
                if w and h and w > 0 and h > 0:
                    result['resolution'] = f"{w}x{h}"

                codec = _get_property_string(handle, 'video-codec')
                if codec:
                    result['codec'] = codec

                try:
                    from models.channel_mappings import extract_channel_name_from_url
                    result['service_name'] = extract_channel_name_from_url(url)
                except Exception:
                    result['service_name'] = ''

            elif event_id == _MPV_EVENT_END_FILE:
                result['valid'] = False
                result['latency'] = latency
                if error_code != 0:
                    result['error'] = f'播放失败(错误码:{error_code})'
                    result['error_type'] = 'playback_failed'
                else:
                    result['error'] = '流结束(无内容)'
                    result['error_type'] = 'stream_ended'

            else:
                result['valid'] = False
                result['latency'] = latency
                result['error'] = f'超时({timeout}秒)'
                result['error_type'] = 'timeout'

        except Exception as e:
            result['error'] = str(e)
            result['error_type'] = 'unknown_error'
        finally:
            if handle:
                _destroy_mpv(handle)
            sem.release()

        return result

    @classmethod
    def set_max_concurrent(cls, max_count):
        cls._semaphore = threading.Semaphore(max(1, max_count))

    @classmethod
    def set_user_agent(cls, user_agent: str):
        with cls._headers_lock:
            cls._user_agent = user_agent if user_agent else None

    @classmethod
    def set_referer(cls, referer: str):
        with cls._headers_lock:
            cls._referer = referer if referer else None

    @classmethod
    def get_headers(cls) -> dict:
        with cls._headers_lock:
            headers = {}
            if cls._user_agent:
                headers['user-agent'] = cls._user_agent
            if cls._referer:
                headers['referer'] = cls._referer
            return headers

    @classmethod
    def terminate_all(cls):
        pass
