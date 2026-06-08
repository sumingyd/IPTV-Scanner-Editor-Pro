from PyQt6.QtWidgets import (QDialog, QDockWidget, QWidget, QApplication,
                              QHBoxLayout, QLabel, QPushButton)
from PyQt6 import QtWidgets
from PyQt6.QtGui import QPainter, QColor, QPainterPath, QCursor, QIcon
from PyQt6.QtCore import Qt, QRectF, QSize
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
    if hex_str and hex_str.startswith('rgba('):
        try:
            inner = hex_str[5:].rstrip(')')
            parts = [p.strip() for p in inner.split(',')]
            return int(parts[0]), int(parts[1]), int(parts[2])
        except Exception:
            pass
    if hex_str and hex_str.startswith('rgb('):
        try:
            inner = hex_str[4:].rstrip(')')
            parts = [p.strip() for p in inner.split(',')]
            return int(parts[0]), int(parts[1]), int(parts[2])
        except Exception:
            pass
    return default


class FloatingDockWidget(QDockWidget):
    """浮动停靠窗口 - QDockWidget 子控件模式（用于诊断对比）"""

    _RESIZE_MARGIN = 6

    def __init__(self, title, parent=None, opacity=130):
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
        self._dwm_blur_enabled = False
        self._resizing = False
        self._resize_edge = None
        self._resize_start_geo = None
        self._resize_start_pos = None

    def _on_floating_changed(self, floating):
        if floating:
            flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
            if self.parent() and (self.parent().windowFlags() & Qt.WindowType.WindowStaysOnTopHint):
                flags |= Qt.WindowType.WindowStaysOnTopHint
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            self.setWindowFlags(flags)
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            self.show()

    def show(self):
        super().show()
        _hide_from_taskbar(self)

    def _try_enable_dwm_blur(self):
        if sys.platform != 'win32':
            return
        try:
            from ui.styles import AppStyles
            if AppStyles._visual_style != 'frosted':
                if self._dwm_blur_enabled:
                    self._disable_dwm_blur()
                    self._dwm_blur_enabled = False
                return
            import ctypes
            hwnd = int(self.winId())
            try:
                DWMWA_SYSTEMBACKDROP_TYPE = 38
                DWMSBT_MAINVIEW = 2
                value = ctypes.c_int(DWMSBT_MAINVIEW)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, DWMWA_SYSTEMBACKDROP_TYPE,
                    ctypes.byref(value), ctypes.sizeof(value)
                )
                self._dwm_blur_enabled = True
            except Exception:
                pass
        except Exception:
            pass

    def _disable_dwm_blur(self):
        if sys.platform != 'win32':
            return
        try:
            import ctypes
            hwnd = int(self.winId())
            DWMWA_SYSTEMBACKDROP_TYPE = 38
            DWMSBT_NONE = 1
            value = ctypes.c_int(DWMSBT_NONE)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, DWMWA_SYSTEMBACKDROP_TYPE,
                ctypes.byref(value), ctypes.sizeof(value)
            )
        except Exception:
            pass

    def _hit_resize_edge(self, pos):
        m = self._RESIZE_MARGIN
        w, h = self.width(), self.height()
        x, y = pos.x(), pos.y()
        on_left = x < m
        on_right = x > w - m
        on_top = y < m
        on_bottom = y > h - m
        if on_top and on_left:
            return 'top_left'
        if on_top and on_right:
            return 'top_right'
        if on_bottom and on_left:
            return 'bottom_left'
        if on_bottom and on_right:
            return 'bottom_right'
        if on_left:
            return 'left'
        if on_right:
            return 'right'
        if on_top:
            return 'top'
        if on_bottom:
            return 'bottom'
        return None

    def _edge_cursor(self, edge):
        cursors = {
            'left': Qt.CursorShape.SizeHorCursor,
            'right': Qt.CursorShape.SizeHorCursor,
            'top': Qt.CursorShape.SizeVerCursor,
            'bottom': Qt.CursorShape.SizeVerCursor,
            'top_left': Qt.CursorShape.SizeFDiagCursor,
            'bottom_right': Qt.CursorShape.SizeFDiagCursor,
            'top_right': Qt.CursorShape.SizeBDiagCursor,
            'bottom_left': Qt.CursorShape.SizeBDiagCursor,
        }
        return cursors.get(edge, Qt.CursorShape.ArrowCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            edge = self._hit_resize_edge(event.position().toPoint())
            if edge:
                self._resizing = True
                self._resize_edge = edge
                self._resize_start_geo = self.geometry()
                self._resize_start_pos = event.globalPosition().toPoint()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._resizing and self._resize_edge and self._resize_start_geo and self._resize_start_pos:
            delta = event.globalPosition().toPoint() - self._resize_start_pos
            geo = self._resize_start_geo.__class__(self._resize_start_geo)
            edge = self._resize_edge
            min_w = self.minimumWidth() if self.minimumWidth() > 0 else 200
            min_h = self.minimumHeight() if self.minimumHeight() > 0 else 150
            if 'right' in edge:
                new_w = max(min_w, self._resize_start_geo.width() + delta.x())
                geo.setWidth(new_w)
            if 'left' in edge:
                new_w = max(min_w, self._resize_start_geo.width() - delta.x())
                geo.setX(self._resize_start_geo.x() + self._resize_start_geo.width() - new_w)
                geo.setWidth(new_w)
            if 'bottom' in edge:
                new_h = max(min_h, self._resize_start_geo.height() + delta.y())
                geo.setHeight(new_h)
            if 'top' in edge:
                new_h = max(min_h, self._resize_start_geo.height() - delta.y())
                geo.setY(self._resize_start_geo.y() + self._resize_start_geo.height() - new_h)
                geo.setHeight(new_h)
            self.setGeometry(geo)
            return
        edge = self._hit_resize_edge(event.position().toPoint())
        if edge:
            self.setCursor(QCursor(self._edge_cursor(edge)))
        else:
            self.unsetCursor()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._resizing:
            self._resizing = False
            self._resize_edge = None
            self._resize_start_geo = None
            self._resize_start_pos = None
            return
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        from ui.styles import AppStyles

        self._try_enable_dwm_blur()

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if AppStyles._visual_style == 'frosted':
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
            painter.fillRect(self.rect(), QColor(0, 0, 0, 0))
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

        path = QPainterPath()
        rect = QRectF(self.rect().adjusted(1, 1, -1, -1))
        corner_r = AppStyles._get_style_border_radius()
        path.addRoundedRect(rect, corner_r, corner_r)

        colors = AppStyles._get_colors()
        neo = AppStyles.is_neumorphic()
        is_frosted = AppStyles._visual_style == 'frosted'

        if is_frosted:
            opacity = int(colors.get('frosted_opacity', 0.65) * 255)
            r, g, b = _parse_hex_color(colors.get('player_panel', '#1e1e1e'))
            painter.fillPath(path, QColor(r, g, b, opacity))
        else:
            r, g, b = _parse_hex_color(colors.get('player_panel', '#1e1e1e'))
            painter.fillPath(path, QColor(r, g, b, self._opacity))

        if not neo and not is_frosted:
            br, bg, bb = _parse_hex_color(colors.get('mid', '#646464'))
            painter.setPen(QColor(br, bg, bb, 150))
            painter.drawPath(path)
        elif is_frosted:
            br, bg, bb = _parse_hex_color(colors.get('mid', '#646464'))
            painter.setPen(QColor(br, bg, bb, 80))
            painter.drawPath(path)

        super().paintEvent(event)


class FloatingDialog(QDialog):
    _bg_color_key = 'window'
    _border_color_key = 'mid'

    @staticmethod
    def create_dialog_title_bar(title_text, close_target, min_width=46, height=32):
        from ui.styles import AppStyles
        colors = AppStyles._get_colors()
        r = AppStyles._get_style_border_radius()
        title_bg = colors.get('window', '#1e1e1e')
        title_text_color = colors.get('window_text', '#ffffff')
        accent = colors.get('accent', '#4a9eff')
        close_hover = AppStyles.COLOR_CLOSE_HOVER if hasattr(AppStyles, 'COLOR_CLOSE_HOVER') else '#e81123'

        bar = QWidget()
        bar.setFixedHeight(height)
        bar.setObjectName("dialogTitleBar")
        bar.setStyleSheet(f"""
            QWidget#dialogTitleBar {{
                background-color: {title_bg};
                border-top-left-radius: {r}px;
                border-top-right-radius: {r}px;
            }}
        """)

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(12, 0, 4, 0)
        layout.setSpacing(0)

        label = QLabel(title_text)
        label.setStyleSheet(f"color: {title_text_color}; font-size: 13px; font-weight: bold; background: transparent; padding-left: 4px;")
        layout.addWidget(label, 1)

        icon_color = title_text_color
        icon_size = QSize(14, 14)

        close_btn = QPushButton()
        close_icon_path = AppStyles.get_icon('close', icon_color, 14)
        if close_icon_path:
            close_btn.setIcon(QIcon(close_icon_path))
        close_btn.setIconSize(icon_size)
        close_btn.setFixedSize(min_width, height - 4)
        close_btn.setObjectName("closeButton")
        close_btn.setToolTip('关闭')
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent; border: none; border-radius: {r}px;
            }}
            QPushButton:hover {{
                background-color: {close_hover}; color: white;
            }}
        """)
        close_btn.clicked.connect(close_target.close)
        layout.addWidget(close_btn)

        return bar

    def __init__(self, parent=None, frameless=True, tool_window=False, stay_on_top=True):
        super().__init__(parent)
        self.dragging = False
        self.offset = None
        from ui.styles import AppStyles
        colors = AppStyles._get_colors()
        self.opacity = colors.get('window_opacity', 220)

        flags = Qt.WindowType.Window
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
        self._dwm_blur_enabled = False

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
        is_frosted = AppStyles._visual_style == 'frosted'

        if is_frosted:
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
            painter.fillRect(self.rect(), QColor(0, 0, 0, 0))
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

        path = QPainterPath()
        rect = QRectF(self.rect().adjusted(1, 1, -1, -1))
        corner_r = AppStyles._get_style_border_radius()
        path.addRoundedRect(rect, corner_r, corner_r)

        r, g, b = _parse_hex_color(colors.get(self._bg_color_key, '#333333'))
        if is_frosted:
            opacity = int(colors.get('frosted_opacity', 0.65) * 255)
            painter.fillPath(path, QColor(r, g, b, opacity))
        else:
            painter.fillPath(path, QColor(r, g, b, self.opacity))

        if not neo and not is_frosted:
            br, bg, bb = _parse_hex_color(colors.get(self._border_color_key, '#999999'))
            painter.setPen(QColor(br, bg, bb, 200))
            painter.drawPath(path)
        elif is_frosted:
            br, bg, bb = _parse_hex_color(colors.get(self._border_color_key, '#999999'))
            painter.setPen(QColor(br, bg, bb, 80))
            painter.drawPath(path)

        if is_frosted and sys.platform == 'win32':
            try:
                import ctypes
                hwnd = int(self.winId())
                DWMWA_SYSTEMBACKDROP_TYPE = 38
                DWMSBT_MAINVIEW = 2
                value = ctypes.c_int(DWMSBT_MAINVIEW)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, DWMWA_SYSTEMBACKDROP_TYPE,
                    ctypes.byref(value), ctypes.sizeof(value)
                )
                self._dwm_blur_enabled = True
            except Exception:
                pass
        elif self._dwm_blur_enabled and sys.platform == 'win32':
            try:
                import ctypes
                hwnd = int(self.winId())
                DWMWA_SYSTEMBACKDROP_TYPE = 38
                DWMSBT_NONE = 1
                value = ctypes.c_int(DWMSBT_NONE)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, DWMWA_SYSTEMBACKDROP_TYPE,
                    ctypes.byref(value), ctypes.sizeof(value)
                )
                self._dwm_blur_enabled = False
            except Exception:
                pass

        super().paintEvent(event)
