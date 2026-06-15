from core.log_manager import global_logger as logger
from utils.platform_utils import is_macos


class TrayMixin:

    def _setup_system_tray(self):
        from PySide6.QtWidgets import QSystemTrayIcon, QMenu
        from PySide6.QtGui import QIcon
        import os
        project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        icon_candidates = []
        if is_macos():
            icon_candidates.append(os.path.join(project_dir, 'resources', 'logo.icns'))
            icon_candidates.append(os.path.join(project_dir, 'resources', 'logo.png'))
        icon_candidates.append(os.path.join(project_dir, 'resources', 'logo.ico'))
        icon_path = None
        for p in icon_candidates:
            if os.path.exists(p):
                icon_path = p
                break
        icon = QIcon(icon_path) if icon_path else QIcon()
        self._system_tray = QSystemTrayIcon(icon, self)
        tray_menu = QMenu()
        tr = self.language_manager.tr
        show_action = tray_menu.addAction(tr('tray_show', '显示主窗口'))
        show_action.triggered.connect(self._tray_show_window)
        tray_menu.addSeparator()
        quit_action = tray_menu.addAction(tr('tray_quit', '退出程序'))
        quit_action.triggered.connect(self._tray_quit)
        self._system_tray.setContextMenu(tray_menu)
        self._system_tray.activated.connect(self._on_tray_activated)
        self._is_hidden_to_tray = False

    def _on_tray_activated(self, reason):
        from PySide6.QtWidgets import QSystemTrayIcon
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._tray_show_window()

    def _tray_show_window(self):
        self._is_hidden_to_tray = False
        self.show()
        self.activateWindow()
        self.raise_()
        for dock_name in getattr(self, '_tray_hidden_docks', []):
            dock = getattr(self, dock_name, None)
            if dock:
                dock.show()
                dock.setFloating(True)

    def _tray_quit(self):
        self._force_quit = True
        self._is_hidden_to_tray = False
        self.close()

    def _do_close_minimize_tray(self):
        tr = self.language_manager.tr
        self._is_hidden_to_tray = True
        pc = self.player_controller
        if pc and pc.is_playing and not pc.is_paused:
            pc.pause()
            self._was_playing_before_tray = True
        else:
            self._was_playing_before_tray = False
        self._tray_hidden_docks = []
        for dock_name in ('epg_dock', 'playlist_dock', 'floating_dock'):
            dock = getattr(self, dock_name, None)
            if dock and dock.isVisible():
                self._tray_hidden_docks.append(dock_name)
                dock.blockSignals(True)
                dock.setFloating(False)
                dock.blockSignals(False)
        self.hide()
        tray = self._system_tray
        if tray:
            tray.show()
            tray.setToolTip(tr('app_title', 'IPTV Scanner Editor Pro'))