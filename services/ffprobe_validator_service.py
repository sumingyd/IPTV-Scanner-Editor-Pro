import json
import os
import subprocess
import sys
import threading
import time
from typing import Dict
from core.log_manager import global_logger


def _get_ffprobe_path():
    if getattr(sys, 'frozen', False):
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    else:
        from models.channel_mappings import get_app_data_dir
        base_path = get_app_data_dir()

    ffprobe_dir = os.path.join(base_path, 'ffmpge')
    ffprobe_exe = os.path.join(ffprobe_dir, 'ffprobe.exe')
    if os.path.exists(ffprobe_exe):
        return ffprobe_exe

    ffprobe_dir_alt = os.path.join(base_path, 'ffmpeg')
    ffprobe_exe_alt = os.path.join(ffprobe_dir_alt, 'ffprobe.exe')
    if os.path.exists(ffprobe_exe_alt):
        return ffprobe_exe_alt

    global_logger.warning(f"未找到ffprobe.exe: {ffprobe_exe}")
    return None


def get_optimal_thread_count():
    cpu = os.cpu_count() or 4
    return min(max(cpu, 4), 32)


class FfprobeStreamValidator:
    _semaphore: threading.Semaphore | None = None
    _user_agent: str | None = None
    _referer: str | None = None
    _headers_lock = threading.Lock()
    _terminating = False
    _ffprobe_path: str | None = None
    _ffprobe_checked = False

    @classmethod
    def _get_ffprobe_path(cls):
        if not cls._ffprobe_checked:
            cls._ffprobe_path = _get_ffprobe_path()
            cls._ffprobe_checked = True
        return cls._ffprobe_path

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

        ffprobe_path = self._get_ffprobe_path()
        if not ffprobe_path:
            result['error'] = 'ffprobe不可用'
            result['error_type'] = 'ffprobe_unavailable'
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

        try:
            cmd = self._build_ffprobe_command(ffprobe_path, url, timeout)
            start_time = time.time()

            try:
                proc = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=timeout + 10,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
                )
            except subprocess.TimeoutExpired:
                latency = int((time.time() - start_time) * 1000)
                result['latency'] = latency
                result['error'] = f'超时({timeout}秒)'
                result['error_type'] = 'timeout'
                return result

            latency = int((time.time() - start_time) * 1000)
            result['latency'] = latency

            stderr_output = proc.stderr.decode('utf-8', errors='ignore').strip()

            probe_data = self._parse_probe_output(proc.stdout)
            if probe_data is not None:
                streams = probe_data.get('streams', [])
                if streams:
                    result['valid'] = True

                    video_stream = None
                    audio_stream = None
                    for s in streams:
                        if s.get('codec_type') == 'video' and video_stream is None:
                            video_stream = s
                        elif s.get('codec_type') == 'audio' and audio_stream is None:
                            audio_stream = s

                    if video_stream:
                        width = video_stream.get('width')
                        height = video_stream.get('height')
                        if width and height:
                            result['resolution'] = f"{width}x{height}"
                        codec_name = video_stream.get('codec_name')
                        if codec_name:
                            result['codec'] = codec_name

                    format_info = probe_data.get('format', {})
                    bitrate = format_info.get('bit_rate')
                    if bitrate:
                        try:
                            bitrate_kbps = int(int(bitrate) / 1000)
                            result['bitrate'] = f"{bitrate_kbps}kbps"
                        except (ValueError, TypeError):
                            pass

                    try:
                        from models.channel_mappings import extract_channel_name_from_url
                        result['service_name'] = extract_channel_name_from_url(url)
                    except Exception:
                        result['service_name'] = ''

                    return result

            if proc.returncode != 0:
                if 'Server returned 404' in stderr_output or '404 Not Found' in stderr_output:
                    result['error'] = '服务器返回404'
                    result['error_type'] = 'http_404'
                elif 'Connection refused' in stderr_output:
                    result['error'] = '连接被拒绝'
                    result['error_type'] = 'connection_refused'
                elif 'Connection timed out' in stderr_output or 'timed out' in stderr_output.lower():
                    result['error'] = '连接超时'
                    result['error_type'] = 'timeout'
                elif 'No such file' in stderr_output or 'not found' in stderr_output.lower():
                    result['error'] = '资源未找到'
                    result['error_type'] = 'not_found'
                else:
                    result['error'] = f'探测失败(返回码:{proc.returncode})'
                    result['error_type'] = 'probe_failed'
                return result

            result['error'] = '无媒体流'
            result['error_type'] = 'no_streams'

        except Exception as e:
            result['error'] = str(e)
            result['error_type'] = 'unknown_error'
        finally:
            sem.release()

        if not result.get('valid', False):
            global_logger.debug(
                f"验证无效: {url} | "
                f"latency={result.get('latency', 0)}ms | "
                f"error_type={result.get('error_type', 'unknown')} | "
                f"error={result.get('error', '')}"
            )

        return result

    def _build_ffprobe_command(self, ffprobe_path: str, url: str, timeout: int) -> list:
        cmd = [
            ffprobe_path,
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            '-analyzeduration', str(timeout * 1000000),
            '-probesize', '1048576',
            '-timeout', str(timeout * 1000000),
        ]

        u = url.lower()
        if u.startswith('rtsp://'):
            rtsp_transport = 'tcp'
            try:
                from core.config_manager import ConfigManager
                cfg = ConfigManager()
                playback = cfg.load_playback_settings()
                rtsp_transport = playback.get('rtsp_transport', 'tcp')
            except Exception:
                pass
            cmd.extend(['-rtsp_transport', rtsp_transport])

        if u.startswith('udp://') or u.startswith('rtp://'):
            cmd.extend(['-f', 'mpegts'])

        if u.endswith('.ts') and not (u.startswith('http://') or u.startswith('https://')):
            cmd.extend(['-f', 'mpegts'])

        user_agent = self.get_user_agent()
        if not user_agent:
            try:
                from core.config_manager import ConfigManager
                playback = ConfigManager().load_playback_settings()
                user_agent = playback.get('user_agent', '')
            except Exception:
                pass

        headers_parts = []
        if user_agent:
            headers_parts.append(f'User-Agent: {user_agent}')

        referer = self.get_referer()
        if not referer:
            try:
                from core.config_manager import ConfigManager
                playback = ConfigManager().load_playback_settings()
                http_headers = playback.get('http_headers', '')
                if http_headers:
                    for line in http_headers.replace('\r\n', '\n').split('\n'):
                        line = line.strip()
                        if line and 'eferer' in line:
                            referer = line.split(':', 1)[1].strip() if ':' in line else ''
                            break
            except Exception:
                pass

        if referer:
            headers_parts.append(f'Referer: {referer}')

        if headers_parts:
            cmd.extend(['-headers', '\r\n'.join(headers_parts)])

        cmd.append(url)
        return cmd

    @staticmethod
    def _parse_probe_output(stdout_bytes: bytes) -> dict | None:
        try:
            text = stdout_bytes.decode('utf-8', errors='ignore').strip()
            if not text:
                return None
            return json.loads(text)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None

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

    @classmethod
    def set_terminating(cls):
        cls._terminating = True

    @classmethod
    def destroy_all_handles(cls):
        pass

    @classmethod
    def reset_terminating(cls):
        cls._terminating = False
