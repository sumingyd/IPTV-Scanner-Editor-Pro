import sys
import os

if sys.platform == 'darwin' and getattr(sys, 'frozen', False):
    try:
        import certifi
        os.environ['SSL_CERT_FILE'] = certifi.where()
        os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()
    except ImportError:
        _cert_path = os.path.join(os.path.dirname(sys.executable), 'resources', 'cert.pem')
        if os.path.exists(_cert_path):
            os.environ['SSL_CERT_FILE'] = _cert_path
            os.environ['REQUESTS_CA_BUNDLE'] = _cert_path

if sys.platform.startswith('linux') and not getattr(sys, 'platform', '') == 'android':
    session_type = os.environ.get('XDG_SESSION_TYPE', '').lower()
    wayland_display = os.environ.get('WAYLAND_DISPLAY', '')
    is_wayland_env = (session_type == 'wayland') or (bool(wayland_display) and session_type != 'x11')
    if is_wayland_env and not os.environ.get('QT_QPA_PLATFORM'):
        os.environ['QT_QPA_PLATFORM'] = 'xcb'

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _suppress_qfont_pointsize_warning(msg_type, context, msg):
    from PySide6.QtCore import QtMsgType
    if msg_type == QtMsgType.QtWarningMsg and 'setPointSize' in msg and 'Point size <= 0' in msg:
        return
    if msg_type == QtMsgType.QtWarningMsg:
        sys.stderr.write(f"Qt Warning: {msg}\n")
    elif msg_type == QtMsgType.QtCritical:
        sys.stderr.write(f"Qt Critical: {msg}\n")


def main():
    from PySide6.QtWidgets import QApplication, QSplashScreen
    from PySide6.QtGui import QIcon, QPixmap, QColor
    from PySide6.QtCore import Qt, qInstallMessageHandler

    qInstallMessageHandler(_suppress_qfont_pointsize_warning)

    app = QApplication(sys.argv)

    splash = None
    try:
        from utils.general_utils import get_icon_path
        ico_path = get_icon_path()
        if os.path.exists(ico_path):
            splash_pixmap = QIcon(ico_path).pixmap(128, 128)
        else:
            splash_pixmap = QPixmap(128, 128)
            splash_pixmap.fill(Qt.GlobalColor.transparent)
        splash = QSplashScreen(splash_pixmap, Qt.WindowType.WindowStaysOnTopHint)
        splash.showMessage(
            "Loading...",
            Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter,
            QColor(200, 200, 200))
        try:
            from core.config_manager import ConfigManager
            cfg = ConfigManager()
            wx = int(cfg.get_value('UI', 'window_x') or 100)
            wy = int(cfg.get_value('UI', 'window_y') or 100)
            ww = int(cfg.get_value('UI', 'window_width') or 1280)
            wh = int(cfg.get_value('UI', 'window_height') or 780)
            sp = splash.size()
            from utils.platform_utils import wayland_move
            wayland_move(splash, wx + (ww - sp.width()) // 2, wy + (wh - sp.height()) // 2)
        except Exception:
            pass
        splash.show()
        app.processEvents()
    except Exception:
        pass

    from pyqt_player import IPTVPlayer

    player = IPTVPlayer()

    if splash:
        splash.finish(player)

    if len(sys.argv) > 1:
        from PySide6.QtCore import QTimer
        file_path = sys.argv[1]
        if os.path.isfile(file_path):
            if file_path.lower().endswith(('.m3u', '.m3u8', '.txt')):
                QTimer.singleShot(800, lambda fp=file_path: player.settings_ops.open_specific_file(fp))
            elif file_path.lower().endswith(('.mp4', '.mkv', '.avi', '.mov',
                                             '.flv', '.wmv', '.ts', '.webm',
                                             '.mp3', '.flac', '.wav', '.aac', '.ogg', '.opus',
                                             '.wma', '.m4a', '.ape', '.alac', '.wv', '.tta',
                                             '.dts', '.ac3', '.mid', '.midi')):
                def _open_video_from_cmdline(fp=file_path):
                    player._add_local_video_and_track(fp)
                QTimer.singleShot(800, _open_video_from_cmdline)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()