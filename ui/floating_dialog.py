from PyQt6.QtWidgets import QFrame, QDialog, QDockWidget, QWidget, QApplication
from PyQt6 import QtWidgets
from PyQt6.QtGui import QPainter, QColor, QPainterPath
from PyQt6.QtCore import Qt, QRectF
import sys


def _hide_from_taskbar(window):
    """隐藏窗口的任务栏图标（仅 Windows 平台）"""
    if sys.platform == 'win32':
        try:
            import ctypes
            from ctypes import wintypes
            GWL_EXSTYLE = -20
            WS_EX_TOOLWINDOW = 0x00000080
            WS_EX_APPWINDOW = 0x00040000
            hwnd = int(window.winId())
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            style = (style | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
        except Exception:
            pass


def _parse_hex_color(hex_str, default=(0, 0, 0)):
    if hex_str and hex_str.startswith('#') and len(hex_str) == 7:
        return int(hex_str[1:3], 16), int(hex_str[3:5], 16), int(hex_str[5:7], 16)
    return default


class FloatingDockWidget(QDockWidget):
    """浮动停靠窗口 - QDockWidget 子控件模式（用于诊断对比）"""

    def __init__(self, title, parent=None, opacity=180):
        super().__init__(title, parent)
        self._opacity = opacity
        self._base_title = title
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.topLevelChanged.connect(self._on_floating_changed)
        empty_bar = QWidget()
        empty_bar.setFixedHeight(0)
        self.setTitleBarWidget(empty_bar)

    def _on_floating_changed(self, floating):
        if floating:
            flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
            if self.parent() and (self.parent().windowFlags() & Qt.WindowType.WindowStaysOnTopHint):
                flags |= Qt.WindowType.WindowStaysOnTopHint
            self.setWindowFlags(flags)
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            self.show()

    def show(self):
        super().show()
        _hide_from_taskbar(self)

    def paintEvent(self, event):
        from ui.styles import AppStyles

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        path = QPainterPath()
        rect = QRectF(self.rect().adjusted(1, 1, -1, -1))
        path.addRoundedRect(rect, 8, 8)

        colors = AppStyles._get_colors()
        neo = AppStyles.is_neumorphic()

        r, g, b = _parse_hex_color(colors.get('player_panel', '#1e1e1e'))
        painter.fillPath(path, QColor(r, g, b, self._opacity))

        if not neo:
            br, bg, bb = _parse_hex_color(colors.get('mid', '#646464'))
            painter.setPen(QColor(br, bg, bb, 150))
            painter.drawPath(path)

        super().paintEvent(event)


class FloatingDialog(QDialog):
    _bg_color_key = 'window'
    _border_color_key = 'mid'
    _corner_radius = 12

    def __init__(self, parent=None, frameless=True, tool_window=False, stay_on_top=True):
        super().__init__(parent)
        self.dragging = False
        self.offset = None
        from ui.styles import AppStyles
        colors = AppStyles._get_colors()
        self.opacity = colors.get('window_opacity', 220)

        flags = Qt.WindowType.Dialog
        if stay_on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        if tool_window:
            flags |= Qt.WindowType.Tool
        if frameless:
            flags |= Qt.WindowType.FramelessWindowHint
        self.setWindowFlags(flags)
        if frameless:
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            widget = QtWidgets.QApplication.widgetAt(event.globalPosition().toPoint())
            if widget:
                interactive_types = (
                    QtWidgets.QAbstractButton,
                    QtWidgets.QLineEdit,
                    QtWidgets.QComboBox,
                    QtWidgets.QCheckBox,
                    QtWidgets.QScrollBar,
                    QtWidgets.QTableView,
                    QtWidgets.QTreeView,
                    QtWidgets.QListView,
                    QtWidgets.QAbstractSlider,
                    QtWidgets.QAbstractSpinBox,
                    QtWidgets.QTextEdit,
                )
                w = widget
                while w:
                    if isinstance(w, interactive_types):
                        super().mousePressEvent(event)
                        return
                    w = w.parent()
            self.dragging = True
            self.offset = event.position().toPoint()

    def mouseMoveEvent(self, event):
        if self.dragging and self.offset is not None:
            new_position = event.globalPosition().toPoint() - self.offset
            self.move(new_position)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = False

    def paintEvent(self, event):
        from PyQt6.QtGui import QPainterPath
        from PyQt6.QtCore import QRectF
        from ui.styles import AppStyles

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        colors = AppStyles._get_colors()
        neo = AppStyles.is_neumorphic()

        path = QPainterPath()
        rect = QRectF(self.rect().adjusted(1, 1, -1, -1))
        path.addRoundedRect(rect, self._corner_radius, self._corner_radius)

        r, g, b = _parse_hex_color(colors.get(self._bg_color_key, '#333333'))
        painter.fillPath(path, QColor(r, g, b, self.opacity))

        if not neo:
            br, bg, bb = _parse_hex_color(colors.get(self._border_color_key, '#999999'))
            painter.setPen(QColor(br, bg, bb, 200))
            painter.drawPath(path)

        super().paintEvent(event)
