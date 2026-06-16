import os
import sys


def is_windows():
    return sys.platform == 'win32'


def is_macos():
    return sys.platform == 'darwin'


def is_linux():
    return sys.platform.startswith('linux') and not is_android()


def is_wayland():
    if not is_linux():
        return False
    session_type = os.environ.get('XDG_SESSION_TYPE', '').lower()
    if session_type == 'wayland':
        return True
    qt_qpa = os.environ.get('QT_QPA_PLATFORM', '').lower()
    if qt_qpa == 'wayland':
        return True
    if session_type == 'x11':
        return False
    wayland_display = os.environ.get('WAYLAND_DISPLAY', '')
    if wayland_display:
        return True
    return False


def wayland_move(widget, x, y):
    if not is_wayland():
        widget.move(x, y)
        return
    try:
        window_handle = widget.windowHandle()
        if window_handle is None:
            widget.createWinId()
            window_handle = widget.windowHandle()
        if window_handle:
            from PySide6.QtCore import QPoint
            window_handle.setPosition(QPoint(x, y))
    except Exception:
        widget.move(x, y)


def wayland_set_geometry(widget, x, y, w, h):
    if not is_wayland():
        widget.setGeometry(x, y, w, h)
        return
    try:
        window_handle = widget.windowHandle()
        if window_handle is None:
            widget.createWinId()
            window_handle = widget.windowHandle()
        if window_handle:
            from PySide6.QtCore import QPoint
            window_handle.setPosition(QPoint(x, y))
        widget.resize(w, h)
    except Exception:
        widget.setGeometry(x, y, w, h)


def is_android():
    return getattr(sys, 'platform', '') == 'android' or 'ANDROID_ARGUMENT' in os.environ


def is_mobile():
    return is_android()


def is_touch_device():
    if is_android():
        return True
    return False


def get_platform_name():
    if is_android():
        return 'android'
    if is_windows():
        return 'windows'
    if is_macos():
        return 'macos'
    if is_linux():
        return 'linux'
    return 'unknown'


def get_app_base_path():
    if is_android():
        try:
            from PySide6.QtCore import QStandardPaths
            app_data = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
            if app_data:
                return app_data
        except Exception:
            pass
        return os.path.join(os.path.expanduser('~'), 'IPTV_Scanner_Editor_Pro')
    if getattr(sys, 'frozen', False):
        return getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    from models.channel_mappings import get_app_data_dir
    return get_app_data_dir()


def get_libmpv_filename():
    if is_windows():
        return 'libmpv-2.dll'
    if is_macos():
        return 'libmpv.2.dylib'
    if is_android():
        return 'libmpv.so'
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

    if is_android():
        possible_names = ['libmpv.so', 'libmpv.so.2', 'libmpv.so.1']
        for name in possible_names:
            p = os.path.join(mpv_dir, name)
            if os.path.exists(p):
                return p
        lib_dir = os.path.join(base_path, 'lib')
        for name in possible_names:
            p = os.path.join(lib_dir, name)
            if os.path.exists(p):
                return p
        return os.path.join(mpv_dir, 'libmpv.so')

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


def get_screen_dpi_scale():
    try:
        from PySide6.QtGui import QGuiApplication
        if QGuiApplication.instance():
            screen = QGuiApplication.primaryScreen()
            if screen:
                return screen.devicePixelRatio()
    except Exception:
        pass
    return 1.0


def get_touch_target_size():
    if is_android():
        return 48
    return 32
