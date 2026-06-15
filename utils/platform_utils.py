import os
import sys


def is_windows():
    return sys.platform == 'win32'


def is_macos():
    return sys.platform == 'darwin'


def is_linux():
    return sys.platform.startswith('linux')


def get_platform_name():
    if is_windows():
        return 'windows'
    if is_macos():
        return 'macos'
    if is_linux():
        return 'linux'
    return 'unknown'


def get_app_base_path():
    if getattr(sys, 'frozen', False):
        return getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    from models.channel_mappings import get_app_data_dir
    return get_app_data_dir()


def get_libmpv_filename():
    if is_windows():
        return 'libmpv-2.dll'
    if is_macos():
        return 'libmpv.2.dylib'
    return 'libmpv.so.2'


def find_libmpv_path():
    base_path = get_app_base_path()
    mpv_dir = os.path.join(base_path, 'mpv')

    if is_windows():
        return os.path.join(mpv_dir, get_libmpv_filename())

    if is_macos():
        search_paths = [
            os.path.join(mpv_dir, 'libmpv.2.dylib'),
            '/usr/local/lib/libmpv.2.dylib',
            '/opt/homebrew/lib/libmpv.2.dylib',
            '/usr/lib/libmpv.2.dylib',
        ]
        for p in search_paths:
            if os.path.exists(p):
                return p
        return search_paths[0]

    possible_names = ['libmpv.so.2', 'libmpv.so.1', 'libmpv.so']
    for name in possible_names:
        p = os.path.join(mpv_dir, name)
        if os.path.exists(p):
            return p

    try:
        import ctypes.util
        found = ctypes.util.find_library('mpv')
        if found and os.path.exists(found):
            return found
    except Exception:
        pass

    system_dirs = [
        '/usr/lib/aarch64-linux-gnu/',
        '/usr/lib/x86_64-linux-gnu/',
        '/usr/lib64/',
        '/usr/local/lib/',
        '/usr/lib/',
    ]
    for d in system_dirs:
        for name in possible_names:
            p = os.path.join(d, name)
            if os.path.exists(p):
                return p

    try:
        import subprocess
        result = subprocess.run(['ldconfig', '-p'], capture_output=True, text=True, timeout=5)
        for line in result.stdout.splitlines():
            for name in possible_names:
                if name in line:
                    parts = line.strip().split('=>')
                    if len(parts) == 2:
                        p = parts[1].strip()
                        if os.path.exists(p):
                            return p
    except Exception:
        pass

    return os.path.join(mpv_dir, 'libmpv.so.2')


def get_ffprobe_filename():
    if is_windows():
        return 'ffprobe.exe'
    return 'ffprobe'


def get_ffprobe_path():
    base_path = get_app_base_path()
    ffprobe_dir = os.path.join(base_path, 'ffmpeg')
    filename = get_ffprobe_filename()
    ffprobe_exe = os.path.join(ffprobe_dir, filename)
    if os.path.exists(ffprobe_exe):
        return ffprobe_exe
    ffprobe_dir_alt = os.path.join(base_path, 'ffmpge')
    ffprobe_exe_alt = os.path.join(ffprobe_dir_alt, filename)
    if os.path.exists(ffprobe_exe_alt):
        return ffprobe_exe_alt
    return None


def get_subprocess_creation_flags():
    if is_windows():
        import subprocess
        return subprocess.CREATE_NO_WINDOW
    return 0
