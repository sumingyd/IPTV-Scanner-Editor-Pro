import sys
import os
import json
import subprocess
import threading
from PyQt6.QtCore import QRunnable, QThreadPool
from core.log_manager import global_logger

VIDEO_CODEC_MAP = {
    'h264': 'H.264', 'avc1': 'H.264', 'h265': 'H.265', 'hevc': 'H.265',
    'vp9': 'VP9', 'vp8': 'VP8', 'av01': 'AV1', 'av1': 'AV1',
    'mpeg': 'MPEG-2', 'mp2v': 'MPEG-2', 'mp4v': 'MPEG-4',
    'divx': 'DivX', 'xvid': 'XviD', 'wmv3': 'WMV3',
    'wmv2': 'WMV2', 'wmv1': 'WMV1', 'theo': 'Theora',
    'flv1': 'FLV', 'rv40': 'RealVideo 4', 'rv30': 'RealVideo 3',
    '462h': 'H.264', '462H': 'H.264', 'avc3': 'H.264',
    'hvc1': 'H.265', 'hev1': 'H.265', 'vp09': 'VP9', 'av00': 'AV1',
}

AUDIO_CODEC_MAP = {
    'aac': 'AAC', 'mp3': 'MP3', 'mp2': 'MP2', 'mp1': 'MP1',
    'ac3': 'AC-3', 'eac3': 'E-AC-3', 'dts': 'DTS', 'dtsh': 'DTS-HD',
    'opus': 'Opus', 'vorb': 'Vorbis', 'flac': 'FLAC', 'alac': 'ALAC',
    'wma': 'WMA', 'pcm': 'PCM', 'twos': 'PCM', 'sowt': 'PCM',
    'lpcm': 'PCM', 'agpm': 'AAC', 'aacp': 'AAC+', 'aach': 'AAC-HE',
    'mp4a': 'AAC', 'ac-3': 'AC-3', 'dtsc': 'DTS', 'dtse': 'DTS-HD Master Audio',
}

_ffprobe_path_cache = None
_cache_lock = threading.Lock()


def get_ffprobe_path():
    global _ffprobe_path_cache
    if _ffprobe_path_cache is not None:
        return _ffprobe_path_cache

    with _cache_lock:
        if _ffprobe_path_cache is not None:
            return _ffprobe_path_cache

        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
        else:
            base_path = os.getcwd()

        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE

        exe_path = 'ffprobe.exe'
        try:
            subprocess.run([exe_path, '-version'], capture_output=True, check=True, startupinfo=startupinfo)
            _ffprobe_path_cache = exe_path
            return exe_path
        except Exception:
            pass

        search_paths = [
            os.path.join(base_path, 'ffprobe.exe'),
            os.path.join(base_path, 'ffmpeg', 'bin', 'ffprobe.exe'),
        ]
        for p in search_paths:
            if os.path.exists(p):
                _ffprobe_path_cache = p
                return p

        if getattr(sys, 'frozen', False):
            pkg_path = os.path.dirname(sys.executable)
            pkg_search = [
                os.path.join(pkg_path, 'ffmpeg', 'bin', 'ffprobe.exe'),
                os.path.join(pkg_path, 'ffprobe.exe'),
            ]
            for p in pkg_search:
                if os.path.exists(p):
                    _ffprobe_path_cache = p
                    return p

        try:
            from shutil import which
            path = which('ffprobe')
            if path:
                _ffprobe_path_cache = path
                return path
        except ImportError:
            pass

        for root, dirs, files in os.walk(base_path):
            for file in files:
                if file.lower() == 'ffprobe.exe':
                    found = os.path.join(root, file)
                    _ffprobe_path_cache = found
                    return found

        _ffprobe_path_cache = 'ffprobe'
        return 'ffprobe'


def _make_startupinfo():
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE
    return startupinfo


def parse_media_info(data, url=None):
    info = {
        'format': '未知',
        'duration': 0,
        'protocol': '未知',
        'video': {
            'codec': '未知',
            'width': 0,
            'height': 0,
            'frame_rate': 0,
            'bit_rate': 0,
        },
        'audio': {
            'codec': '未知',
            'channels': 0,
            'sample_rate': 0,
            'bit_rate': 0,
        },
    }

    if url and '://' in url:
        info['protocol'] = url.split('://')[0].upper()

    if 'format' in data:
        fmt = data['format']
        if 'format_name' in fmt:
            info['format'] = fmt['format_name']
        if 'duration' in fmt:
            try:
                info['duration'] = float(fmt['duration'])
            except (ValueError, TypeError):
                pass
        if 'size' in fmt:
            info['size'] = fmt['size']
        if 'bit_rate' in fmt:
            info['bit_rate'] = fmt['bit_rate']

    if 'streams' in data:
        for stream in data['streams']:
            if stream.get('codec_type') == 'video':
                codec_name = stream.get('codec_name', '')
                info['video']['codec'] = VIDEO_CODEC_MAP.get(codec_name.lower(), codec_name)
                info['video']['width'] = stream.get('width', 0)
                info['video']['height'] = stream.get('height', 0)
                if 'r_frame_rate' in stream:
                    try:
                        num, den = map(int, stream['r_frame_rate'].split('/'))
                        if den > 0:
                            info['video']['frame_rate'] = num / den
                    except (ValueError, ZeroDivisionError):
                        pass
                if 'bit_rate' in stream:
                    try:
                        info['video']['bit_rate'] = int(stream['bit_rate'])
                    except (ValueError, TypeError):
                        pass
                break

        for stream in data['streams']:
            if stream.get('codec_type') == 'audio':
                codec_name = stream.get('codec_name', '')
                info['audio']['codec'] = AUDIO_CODEC_MAP.get(codec_name.lower(), codec_name)
                info['audio']['channels'] = stream.get('channels', 0)
                if 'sample_rate' in stream:
                    try:
                        info['audio']['sample_rate'] = int(stream['sample_rate'])
                    except (ValueError, TypeError):
                        pass
                if 'bit_rate' in stream:
                    try:
                        info['audio']['bit_rate'] = int(stream['bit_rate'])
                    except (ValueError, TypeError):
                        pass
                break

    return info


def get_media_info_sync(url, timeout=10):
    ffprobe_path = get_ffprobe_path()
    if not ffprobe_path or ffprobe_path == 'ffprobe':
        try:
            startupinfo = _make_startupinfo()
            subprocess.run([ffprobe_path, '-version'], capture_output=True, text=True, timeout=5, startupinfo=startupinfo)
        except Exception:
            return None

    cmd = [
        ffprobe_path,
        '-v', 'quiet',
        '-print_format', 'json',
        '-show_format',
        '-show_streams',
        url,
    ]

    try:
        startupinfo = _make_startupinfo()
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, startupinfo=startupinfo)
        if result.returncode != 0:
            return None
        data = json.loads(result.stdout)
        return parse_media_info(data, url)
    except Exception:
        return None


class FFProbeWorker(QRunnable):
    def __init__(self, url, callback, timeout=10):
        super().__init__()
        self.url = url
        self.callback = callback
        self.timeout = timeout
        self.is_running = True
        self.process = None

    def run(self):
        try:
            ffprobe_path = get_ffprobe_path()
            if not ffprobe_path:
                self._safe_callback(None)
                return

            try:
                startupinfo = _make_startupinfo()
                subprocess.run([ffprobe_path, '-version'], capture_output=True, text=True, timeout=5, startupinfo=startupinfo)
            except Exception:
                self._safe_callback(None)
                return

            if not self.is_running:
                return

            cmd = [
                ffprobe_path,
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                self.url,
            ]

            startupinfo = _make_startupinfo()
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                startupinfo=startupinfo,
            )

            if not self.is_running:
                if self.process:
                    self.process.kill()
                return

            try:
                stdout, stderr = self.process.communicate(timeout=self.timeout)
            except subprocess.TimeoutExpired:
                if self.process:
                    self.process.kill()
                self._safe_callback(None)
                return

            if not self.is_running:
                return

            if self.process.returncode == 0:
                data = json.loads(stdout)
                media_info = parse_media_info(data, self.url)
                self._safe_callback(media_info)
            else:
                self._safe_callback(None)
        except Exception:
            self._safe_callback(None)

    def _safe_callback(self, media_info):
        try:
            if self.is_running and self.callback:
                self.callback(media_info)
        except RuntimeError:
            pass

    def cancel(self):
        self.is_running = False
        if self.process:
            try:
                self.process.kill()
            except Exception:
                pass
