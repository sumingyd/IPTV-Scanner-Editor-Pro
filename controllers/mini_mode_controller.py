from typing import Optional
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon
from core.log_manager import global_logger as logger


class MiniModeController:
    MINI_WIDTH = 480
    MINI_HEIGHT = 270

    def __init__(self, main_window):
        self.window = main_window
        self._is_mini = False
        self._saved_geometry = None
        self._saved_flags = None

    @property
    def is_mini(self) -> bool:
        return self._is_mini

    def toggle(self):
        if self._is_mini:
            self.exit_mini_mode()
        else:
            self.enter_mini_mode()

    def enter_mini_mode(self):
        w = self.window
        if self._is_mini:
            return
        self._is_mini = True
        self._saved_geometry = w.geometry()

        for panel_attr in ('epg_panel', 'playlist_panel', 'floating_panel'):
            panel = getattr(w, panel_attr, None)
            if panel and panel.isVisible():
                panel.hide()

        if hasattr(w, '_title_bar') and w._title_bar:
            w._title_bar.hide()
        if hasattr(w, '_custom_menu_bar') and w._custom_menu_bar:
            w._custom_menu_bar.hide()
        if w.status_bar:
            w.status_bar.hide()

        w.setMinimumSize(self.MINI_WIDTH, self.MINI_HEIGHT)
        w.setMaximumSize(800, 500)
        w.resize(self.MINI_WIDTH, self.MINI_HEIGHT)

        w.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        w.show()

        tr = w.language_manager.tr
        w.status_bar_show_message(tr('mini_mode_entered', '已进入迷你模式'))

    def exit_mini_mode(self):
        w = self.window
        if not self._is_mini:
            return
        self._is_mini = False

        w.setMinimumSize(800, 600)
        w.setMaximumSize(16777215, 16777215)

        w.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Window
        )
        w.show()

        if hasattr(w, '_title_bar') and w._title_bar:
            w._title_bar.show()
        if hasattr(w, '_custom_menu_bar') and w._custom_menu_bar:
            w._custom_menu_bar.show()
        if w.status_bar:
            w.status_bar.show()

        if self._saved_geometry:
            w.setGeometry(self._saved_geometry)
            self._saved_geometry = None

        w.update_floating_position()

        tr = w.language_manager.tr
        w.status_bar_show_message(tr('mini_mode_exited', '已退出迷你模式'))