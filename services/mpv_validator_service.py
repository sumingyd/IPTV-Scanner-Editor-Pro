import ctypes
import os
import threading
import time
from typing import Dict
from core.log_manager import global_logger
from services.mpv_common import (
    MPV_EVENT_FILE_LOADED,
    MPV_EVENT_END_FILE,
    MPV_EVENT_VIDEO_RECONFIG,
    MPV_EVENT_SHUTDOWN,
    MPV_FORMAT_INT64,
    MPV_END_FILE_REASON_ERROR,
    mpv_event_end_file,
    create_mpv_handle,
    initialize_mpv,
    destroy_mpv,
    set_property_string as _mpv_set_property_string,
    set_option_string as _mpv_set_option_string,
    send_command as _mpv_send_command,
    wait_for_specific_event,
    get_property_string as _mpv_get_property_string,
    get_property_int as _mpv_get_property_int,
    _is_mpv_available,
)


def get_optimal_thread_count():
    cpu = os.cpu_count() or 4
    return min(max(cpu, 4), 32)


def _create_lightweight_mpv():
    if not _is_mpv_available():
        return None
    try:
        handle = create_mpv_handle()
        if not handle:
            return None
        _mpv_set_option_string(handle, 'vo', 'null')
        _mpv_set_option_string(handle, 'ao', 'null')
        _mpv_set_option_string(handle, 'hwdec', 'no')
        _mpv_set_option_string(handle, 'osc', 'no')
        _mpv_set_option_string(handle, 'osd-bar', 'no')
        _mpv_set_option_string(handle, 'idle', 'yes')
        _mpv_set_option_string(handle, 'ytdl', 'no')
        _mpv_set_option_string(handle, 'keep-open', 'yes')
        _mpv_set_option_string(handle, 'log-level', 'fatal')
        _mpv_set_option_string(handle, 'config', 'no')
        _mpv_set_option_string(handle, 'demuxer-lavf-probesize', '32768')
        _mpv_set_option_string(handle, 'demuxer-lavf-analyzeduration', '1000000')
        _mpv_set_option_string(handle, 'cache', 'yes')
        _mpv_set_option_string(handle, 'cache-secs', '10')
        _mpv_set_option_string(handle, 'demuxer-max-bytes', '16MiB')
        _mpv_set_option_string(handle, 'demuxer-max-back-bytes', '8MiB')
        _mpv_set_option_string(handle, 'tls-verify', 'no')

        try:
            from core.config_manager import ConfigManager
            playback = ConfigManager().load_playback_settings()
        except Exception:
            playback = {}

        net_timeout = playback.get('network_timeout_sec', 0)
        if net_timeout > 0:
            _mpv_set_option_string(handle, 'network-timeout', str(net_timeout))
        else:
            _mpv_set_option_string(handle, 'network-timeout', '10')

        user_agent = MpvStreamValidator.get_user_agent()
        if not user_agent:
            user_agent = playback.get('user_agent', '')
        if user_agent:
            _mpv_set_option_string(handle, 'user-agent', user_agent)

        http_headers = playback.get('http_headers', '')
        referer = MpvStreamValidator.get_referer()
        if http_headers:
            header_val = http_headers.replace('\r\n', '\n').replace('\n', '\\n')
            if referer and 'eferer' not in header_val:
                header_val += f'\\nReferer: {referer}'
            _mpv_set_option_string(handle, 'http-header-fields', header_val)
        elif referer:
            _mpv_set_option_string(handle, 'http-header-fields', f'Referer: {referer}')

        if not initialize_mpv(handle):
            destroy_mpv(handle)
            return None
        return handle
    except Exception:
        return None


class MpvStreamValidator:
    _semaphore: threading.Semaphore | None = None
    _user_agent: str | None = None
    _referer: str | None = None
    _headers_lock = threading.Lock()
    _active_handles: list = []
    _handles_lock = threading.Lock()
    _terminating = False

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

        if not _is_mpv_available():
            result['error'] = 'mpv不可用'
            result['error_type'] = 'mpv_unavailable'
            return result

        if self._terminating:
            result['error'] = '验证器正在关闭'
            result['error_type'] = 'terminating'
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

            with self._handles_lock:
                self._active_handles.append(handle)

            u = url.lower()
            looks_ts = '/rtp/' in u or u.endswith('.ts') or 'proto=http' in u or u.startswith('udp://')
            if u.startswith('rtsp://'):
                rtsp_transport = 'tcp'
                try:
                    from core.config_manager import ConfigManager
                    cfg = ConfigManager()
                    playback = cfg.load_playback_settings()
                    rtsp_transport = playback.get('rtsp_transport', 'tcp')
                except Exception:
                    pass
                _mpv_set_property_string(handle, 'rtsp-transport', rtsp_transport)
                _mpv_set_property_string(handle, 'demuxer', 'lavf')
                _mpv_set_property_string(handle, 'demuxer-lavf-probesize', '32')
                _mpv_set_property_string(handle, 'demuxer-lavf-analyzeduration', '0')
                _mpv_set_property_string(handle, 'demuxer-lavf-buffersize', '128000')
                _mpv_set_property_string(handle, 'force-seekable', 'yes')
            elif looks_ts:
                _mpv_set_property_string(handle, 'demuxer', 'lavf')
                _mpv_set_property_string(handle, 'demuxer-lavf-format', 'mpegts')
                _mpv_set_property_string(handle, 'demuxer-lavf-probesize', '32')
                _mpv_set_property_string(handle, 'demuxer-lavf-analyzeduration', '0')
                _mpv_set_property_string(handle, 'demuxer-lavf-buffersize', '128000')
                _mpv_set_property_string(handle, 'force-seekable', 'yes')
            elif u.startswith('http://') or u.startswith('https://'):
                _mpv_set_property_string(handle, 'force-seekable', 'yes')

            start_time = time.time()

            _mpv_send_command(handle, ['loadfile', url])

            event_id, error_code, event_data = wait_for_specific_event(
                handle, timeout,
                {MPV_EVENT_FILE_LOADED, MPV_EVENT_END_FILE}
            )

            latency = int((time.time() - start_time) * 1000)

            if event_id == MPV_EVENT_FILE_LOADED:
                result['valid'] = True
                result['latency'] = latency

                vid_event, _, _ = wait_for_specific_event(
                    handle, min(timeout, 3),
                    {MPV_EVENT_VIDEO_RECONFIG, MPV_EVENT_END_FILE}
                )

                w = _mpv_get_property_int(handle, 'width')
                h = _mpv_get_property_int(handle, 'height')
                if w and h and w > 0 and h > 0:
                    result['resolution'] = f"{w}x{h}"

                codec = _mpv_get_property_string(handle, 'video-codec')
                if codec:
                    result['codec'] = codec

                try:
                    from models.channel_mappings import extract_channel_name_from_url
                    result['service_name'] = extract_channel_name_from_url(url)
                except Exception:
                    result['service_name'] = ''

            elif event_id == MPV_EVENT_END_FILE:
                result['valid'] = False
                result['latency'] = latency
                end_reason = None
                end_error = 0
                if event_data:
                    try:
                        end_file = ctypes.cast(event_data, ctypes.POINTER(mpv_event_end_file)).contents
                        end_reason = end_file.reason
                        end_error = end_file.error
                    except Exception:
                        pass
                if end_reason == MPV_END_FILE_REASON_ERROR:
                    result['error'] = f'播放失败(错误码:{end_error})'
                    result['error_type'] = 'playback_failed'
                elif end_reason is not None:
                    result['error'] = f'流结束(reason:{end_reason})'
                    result['error_type'] = 'stream_ended'
                else:
                    result['error'] = '流结束'
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
                with self._handles_lock:
                    was_active = handle in self._active_handles
                    if was_active:
                        self._active_handles.remove(handle)
                if was_active:
                    destroy_mpv(handle)
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
    def get_user_agent(cls) -> str | None:
        with cls._headers_lock:
            return cls._user_agent

    @classmethod
    def get_referer(cls) -> str | None:
        with cls._headers_lock:
            return cls._referer

    @classmethod
    def terminate_all(cls):
        cls._terminating = True
        with cls._handles_lock:
            handles_to_destroy = list(cls._active_handles)
            cls._active_handles.clear()
        for handle in handles_to_destroy:
            try:
                destroy_mpv(handle)
            except Exception:
                pass

    @classmethod
    def set_terminating(cls):
        """仅设置终止标志，不销毁句柄（用于安全停止）"""
        cls._terminating = True

    @classmethod
    def destroy_all_handles(cls):
        """销毁所有活跃mpv句柄（应在工作线程退出后调用）"""
        with cls._handles_lock:
            handles_to_destroy = list(cls._active_handles)
            cls._active_handles.clear()
        for handle in handles_to_destroy:
            try:
                destroy_mpv(handle)
            except Exception:
                pass

    @classmethod
    def reset_terminating(cls):
        cls._terminating = False
