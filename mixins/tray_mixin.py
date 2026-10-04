from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon
from utils.platform_utils import is_macos, is_android


class TrayMixin:

    def _setup_system_tray(self):
        if is_android():
            self._system_tray = None
            self._is_hidden_to_tray = False
            return
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

        play_pause_action = tray_menu.addAction(tr('tray_play_pause', '播放/暂停'))
        play_pause_action.triggered.connect(self._tray_play_pause)
        prev_ch_action = tray_menu.addAction(tr('tray_prev', '上一频道'))
        prev_ch_action.triggered.connect(self._tray_prev_channel)
        next_ch_action = tray_menu.addAction(tr('tray_next', '下一频道'))
        next_ch_action.triggered.connect(self._tray_next_channel)
        mute_action = tray_menu.addAction(tr('tray_mute', '静音'))
        mute_action.triggered.connect(self._tray_toggle_mute)

        tray_menu.addSeparator()
        quit_action = tray_menu.addAction(tr('tray_quit', '退出程序'))
        quit_action.triggered.connect(self._tray_quit)
        self._system_tray.setContextMenu(tray_menu)
        self._system_tray.activated.connect(self._on_tray_activated)
        self._is_hidden_to_tray = False

    def _on_tray_activated(self, reason):
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
        # 隐藏到托盘时若正在播放而暂停，恢复窗口后继续播放
        if getattr(self, '_was_playing_before_tray', False):
            pc = getattr(self, 'player_controller', None)
            if pc:
                pc.play()
            self._was_playing_before_tray = False

    def _tray_quit(self):
        self._force_quit = True
        self._is_hidden_to_tray = False
        self.close()

    def _tray_play_pause(self):
        pc = getattr(self, 'player_controller', None)
        if pc:
            if pc.is_playing and not pc.is_paused:
                pc.pause()
            else:
                pc.play()

    def _tray_prev_channel(self):
        if hasattr(self, '_switch_channel_safe'):
            self._switch_channel_safe(-1)

    def _tray_next_channel(self):
        if hasattr(self, '_switch_channel_safe'):
            self._switch_channel_safe(1)

    def _tray_toggle_mute(self):
        if hasattr(self, 'toggle_mute'):
            self.toggle_mute()

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
            tray.setToolTip(tr('app_title', 'ISEP'))