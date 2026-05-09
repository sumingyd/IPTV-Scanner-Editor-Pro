import ctypes
import hashlib
import os
import sys
import threading
import time
from typing import Optional
from PyQt6.QtCore import QObject, pyqtSignal
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
    _libmpv.mpv_set_option_string.restype = ctypes.c_int
    _libmpv.mpv_set_option_string.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p]
    _libmpv.mpv_set_property_string.restype = ctypes.c_int
    _libmpv.mpv_set_property_string.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p]
    _libmpv.mpv_command.restype = ctypes.c_int
    _libmpv.mpv_command.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_char_p)]
    _libmpv.mpv_destroy.restype = None
    _libmpv.mpv_destroy.argtypes = [ctypes.c_void_p]
    _libmpv.mpv_wait_event.restype = ctypes.c_void_p
    _libmpv.mpv_wait_event.argtypes = [ctypes.c_void_p, ctypes.c_double]
    _MPV_AVAILABLE = True
except Exception:
    _MPV_AVAILABLE = False

_MPV_EVENT_FILE_LOADED = 8
_MPV_EVENT_END_FILE = 7
_MPV_EVENT_SHUTDOWN = 1

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'cache', 'thumbnails')


def _url_to_thumb_path(url: str) -> str:
    url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()
    return os.path.join(CACHE_DIR, f"{url_hash}.png")


def has_thumbnail(url: str) -> bool:
    if not url:
        return False
    return os.path.exists(_url_to_thumb_path(url))


def is_thumbnail_stale(url: str, max_age_minutes: int = 5) -> bool:
    if not url:
        return False
    path = _url_to_thumb_path(url)
    if not os.path.exists(path):
        return True
    try:
        mtime = os.path.getmtime(path)
        age_minutes = (time.time() - mtime) / 60
        return age_minutes > max_age_minutes
    except Exception:
        return False


def get_thumbnail_path(url: str) -> Optional[str]:
    if not url:
        return None
    path = _url_to_thumb_path(url)
    if os.path.exists(path):
        return path
    return None


def _wait_for_event(handle, timeout_sec, target_events):
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        try:
            event_ptr = _libmpv.mpv_wait_event(handle, 0.05)
            if event_ptr:
                event = ctypes.cast(event_ptr, ctypes.POINTER(ctypes.c_void_p * 4)).contents
                event_id = event[0]
                if event_id in target_events:
                    return event_id
                if event_id == _MPV_EVENT_SHUTDOWN:
                    return _MPV_EVENT_SHUTDOWN
        except Exception:
            break
    return 0


def _capture_single(url: str, timeout: int = 8, wid: int = 0, force: bool = False) -> Optional[str]:
    if not _MPV_AVAILABLE:
        return None
    os.makedirs(CACHE_DIR, exist_ok=True)
    thumb_path = _url_to_thumb_path(url)
    if os.path.exists(thumb_path) and not force:
        return thumb_path

    handle = None
    try:
        handle = _libmpv.mpv_create()
        if not handle:
            return None

        if wid:
            _libmpv.mpv_set_option_string(handle, b'wid', str(wid).encode('utf-8'))
        _libmpv.mpv_set_option_string(handle, b'vo', b'gpu')
        _libmpv.mpv_set_option_string(handle, b'ao', b'null')
        _libmpv.mpv_set_option_string(handle, b'gpu-api', b'd3d11')
        _libmpv.mpv_set_option_string(handle, b'hwdec', b'd3d11va')
        _libmpv.mpv_set_option_string(handle, b'osc', b'no')
        _libmpv.mpv_set_option_string(handle, b'osd-bar', b'no')
        _libmpv.mpv_set_option_string(handle, b'idle', b'yes')
        _libmpv.mpv_set_option_string(handle, b'ytdl', b'no')
        _libmpv.mpv_set_option_string(handle, b'keep-open', b'yes')
        _libmpv.mpv_set_option_string(handle, b'log-level', b'error')
        _libmpv.mpv_set_option_string(handle, b'config', b'no')
        _libmpv.mpv_set_option_string(handle, b'force-window', b'no')

        u = url.lower()
        if u.startswith('rtsp://'):
            try:
                from core.config_manager import ConfigManager
                cfg = ConfigManager()
                playback = cfg.load_playback_settings()
                rtsp_transport = playback.get('rtsp_transport', 'tcp')
            except Exception:
                rtsp_transport = 'tcp'
            _libmpv.mpv_set_option_string(handle, b'rtsp-transport', rtsp_transport.encode('utf-8'))
        elif '/rtp/' in u or u.endswith('.ts') or u.startswith('udp://'):
            _libmpv.mpv_set_option_string(handle, b'demuxer-lavf-format', b'mpegts')

        try:
            from services.mpv_validator_service import MpvStreamValidator
            headers = MpvStreamValidator.get_headers()
            if headers:
                import json
                headers_json = json.dumps(headers).encode('utf-8')
                _libmpv.mpv_set_option_string(handle, b'http-header-fields', headers_json)
        except Exception:
            pass

        result = _libmpv.mpv_initialize(handle)
        if result < 0:
            _libmpv.mpv_destroy(handle)
            return None

        cmd = [b'loadfile', url.encode('utf-8'), None]
        cmd_ptr = (ctypes.c_char_p * len(cmd))(*cmd)
        _libmpv.mpv_command(handle, cmd_ptr)

        event_id = _wait_for_event(handle, timeout, {_MPV_EVENT_FILE_LOADED, _MPV_EVENT_END_FILE})

        if event_id == _MPV_EVENT_FILE_LOADED:
            _wait_for_event(handle, 2, {_MPV_EVENT_END_FILE})

            cmd = [b'screenshot-to-file', thumb_path.encode('utf-8'), b'video', None]
            cmd_ptr = (ctypes.c_char_p * len(cmd))(*cmd)
            _libmpv.mpv_command(handle, cmd_ptr)

            time.sleep(0.5)

            if os.path.exists(thumb_path) and os.path.getsize(thumb_path) > 0:
                return thumb_path

        return None
    except Exception:
        return None
    finally:
        if handle:
            try:
                _libmpv.mpv_destroy(handle)
            except Exception:
                pass


class ThumbnailService(QObject):
    thumbnail_ready = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        from PyQt6.QtWidgets import QWidget
        self._hidden_widget = QWidget()
        self._hidden_widget.resize(320, 180)
        self._hidden_winid = int(self._hidden_widget.winId())
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._queue: list = []
        self._lock = threading.Lock()
        self._running = False

    def capture_channels(self, channels: list, force: bool = False):
        """将需要截取缩略图的频道加入队列

        Args:
            channels: 频道列表
            force: 是否强制刷新（包括已有但过旧的缩略图）
        """
        added = False
        with self._lock:
            existing_urls = {url for _, url, _ in self._queue}
            for ch in channels:
                url = ch.get('url', '')
                name = ch.get('name', '')
                if not url or url in existing_urls:
                    continue
                if force:
                    if is_thumbnail_stale(url) or not has_thumbnail(url):
                        self._queue.append((name, url, True))
                        existing_urls.add(url)
                        added = True
                else:
                    if not has_thumbnail(url):
                        self._queue.append((name, url, False))
                        existing_urls.add(url)
                        added = True
        if added and not self._running:
            self._stop_event.clear()
            self._running = True
            self._thread = threading.Thread(target=self._worker, daemon=True)
            self._thread.start()

    def stop(self):
        """停止后台截取"""
        self._stop_event.set()
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)
        self._thread = None
        with self._lock:
            self._queue.clear()

    def _worker(self):
        while not self._stop_event.is_set():
            with self._lock:
                if not self._queue:
                    break
                name, url, force = self._queue.pop(0)
            try:
                result = _capture_single(url, timeout=8, wid=self._hidden_winid, force=force)
                if result and not self._stop_event.is_set():
                    try:
                        self.thumbnail_ready.emit(name, url)
                    except RuntimeError:
                        pass
            except Exception:
                pass
        self._running = False
