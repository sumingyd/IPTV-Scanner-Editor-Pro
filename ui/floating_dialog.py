from PySide6.QtWidgets import (QDialog, QDockWidget, QWidget, QApplication,
                              QHBoxLayout, QLabel, QPushButton)
from PySide6 import QtWidgets
from PySide6.QtGui import QPainter, QColor, QPainterPath, QCursor, QIcon, QBitmap
from PySide6.QtCore import Qt, QRectF, QSize
import PySide6.QtCore as QtCore
import sys
from utils.platform_utils import is_windows, is_macos, is_android, is_linux, is_wayland, wayland_move


def _hide_from_taskbar(window):
    if is_windows():
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
        self.setAutoFillBackground(False)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.topLevelChanged.connect(self._on_floating_changed)
        empty_bar = QWidget()
        empty_bar.setFixedHeight(0)
        self.setTitleBarWidget(empty_bar)
        self._dwm_blur_enabled = False
        self._cached_frosted_colors = None
        self._cached_frosted_theme = None
        self._resizing = False
        self._resize_edge = None
        self._resize_start_geo = None
        self._resize_start_pos = None

    def _set_transient_parent(self):
        try:
            parent_window = self.parent()
            if parent_window is None:
                return
            from PySide6.QtGui import QWindow
            parent_handle = parent_window.windowHandle()
            if parent_handle is None:
                parent_window.createWinId()
                parent_handle = parent_window.windowHandle()
            if parent_handle:
                self_handle = self.windowHandle()
                if self_handle is None:
                    self.createWinId()
                    self_handle = self.windowHandle()
                if self_handle:
                    self_handle.setTransientParent(parent_handle)
        except Exception:
            pass

    def _on_floating_changed(self, floating):
        if floating:
            flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
            if self.parent() and (self.parent().windowFlags() & Qt.WindowType.WindowStaysOnTopHint):
                flags |= Qt.WindowType.WindowStaysOnTopHint
            from ui.styles import AppStyles
            is_frosted = AppStyles._visual_style == 'frosted'
            if is_frosted:
                self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            self.setWindowFlags(flags)
            if is_frosted:
                self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            if is_linux():
                self._set_transient_parent()
            self.show()

    def show(self):
        super().show()
        _hide_from_taskbar(self)

    def _try_enable_macos_blur(self):
        try:
            from ui.styles import AppStyles
            if AppStyles._visual_style != 'frosted':
                if self._dwm_blur_enabled:
                    self._dwm_blur_enabled = False
                return
            if self._dwm_blur_enabled:
                return
            self._dwm_blur_enabled = True
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        except Exception:
            pass

    def _try_enable_dwm_blur(self):
        if is_android():
            return
        if is_macos():
            self._try_enable_macos_blur()
            return
        if not is_windows():
            return
        try:
            import ctypes
            from ui.styles import AppStyles
            if AppStyles._visual_style != 'frosted':
                if self._dwm_blur_enabled:
                    self._disable_dwm_blur()
                self._dwm_blur_enabled = False
                self.clearMask()
                return
            if self._dwm_blur_enabled:
                return
            self._dwm_blur_enabled = True
            try:
                hwnd = int(self.winId())
                DWMWA_SYSTEMBACKDROP_TYPE = 38
                DWMSBT_MAINVIEW = 2
                value = ctypes.c_int(DWMSBT_MAINVIEW)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, DWMWA_SYSTEMBACKDROP_TYPE,
                    ctypes.byref(value), ctypes.sizeof(value)
                )
            except Exception:
                pass
            try:

                corner_r = AppStyles._get_style_border_radius()
                size = self.size()
                bitmap = QBitmap(size)
                bitmap.fill(QtCore.Qt.GlobalColor.color0)
                p = QPainter(bitmap)
                p.setRenderHint(QPainter.RenderHint.Antialiasing)
                p.setBrush(QtCore.Qt.GlobalColor.color1)
                p.setPen(QtCore.Qt.PenStyle.NoPen)
                path = QPainterPath()
                path.addRoundedRect(QRectF(0, 0, size.width(), size.height()), corner_r, corner_r)
                p.drawPath(path)
                p.end()
                self.setMask(bitmap)
            except Exception:
                pass
        except Exception:
            pass

    def _disable_dwm_blur(self):
        if is_android():
            return
        if is_macos():
            self._dwm_blur_enabled = False
            return
        if not is_windows():
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
                if is_wayland():
                    wh = self.windowHandle()
                    if wh:
                        edges_map = {
                            'top': Qt.Edge.TopEdge,
                            'bottom': Qt.Edge.BottomEdge,
                            'left': Qt.Edge.LeftEdge,
                            'right': Qt.Edge.RightEdge,
                            'top_left': Qt.Edge.TopEdge | Qt.Edge.LeftEdge,
                            'top_right': Qt.Edge.TopEdge | Qt.Edge.RightEdge,
                            'bottom_left': Qt.Edge.BottomEdge | Qt.Edge.LeftEdge,
                            'bottom_right': Qt.Edge.BottomEdge | Qt.Edge.RightEdge,
                        }
                        qt_edge = edges_map.get(edge)
                        if qt_edge:
                            wh.startSystemResize(qt_edge)
                            return
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
        from ui.styles import AppStyles, color_to_hex, rgba_to_blended_hex

        if not self._dwm_blur_enabled:
            self._try_enable_dwm_blur()

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        colors = AppStyles._get_colors()
        neo = AppStyles.is_neumorphic()
        is_frosted = AppStyles._visual_style == 'frosted'

        if is_frosted:
            current_theme = AppStyles._current_theme
            if self._cached_frosted_theme != current_theme:
                effective_mode = AppStyles._get_effective_color_mode()
                bg = (0, 0, 0) if effective_mode == 'dark' else (255, 255, 255)
                self._cached_frosted_colors = {}
                for k, v in colors.items():
                    self._cached_frosted_colors[k] = rgba_to_blended_hex(v, bg) if isinstance(v, str) and v.startswith('rgba') else v
                self._cached_frosted_theme = current_theme
            dock_colors = self._cached_frosted_colors
        else:
            dock_colors = colors

        path = QPainterPath()
        corner_r = AppStyles._get_style_border_radius()
        path.addRoundedRect(QRectF(self.rect()), corner_r, corner_r)

        panel_hex = dock_colors.get('player_panel', '#1e1e1e')
        r, g, b = _parse_hex_color(panel_hex)
        painter.fillPath(path, QColor(r, g, b, self._opacity))
        if neo:
            br, bg, bb = _parse_hex_color(dock_colors.get('mid', '#646464'))
            painter.setPen(QColor(br, bg, bb, 60))
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
        close_hover = AppStyles.COLOR_CLOSE_HOVER if hasattr(AppStyles, 'COLOR_CLOSE_HOVER') else '#e81123'

        bar = QWidget()
        bar.setFixedHeight(height)
        bar.setObjectName("dialogTitleBar")
        bar.setStyleSheet(AppStyles.dialog_title_bar_style())

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(12, 0, 4, 0)
        layout.setSpacing(0)

        label = QLabel(title_text)
        label.setStyleSheet(AppStyles.title_label_style())
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
        if AppStyles._visual_style == 'frosted':
            self.opacity = int(colors.get('frosted_opacity', 0.8) * 255)
        else:
            self.opacity = colors.get('window_opacity', 220)

        flags = Qt.WindowType.Window
        if stay_on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        if tool_window:
            flags |= Qt.WindowType.Tool
        flags |= Qt.WindowType.FramelessWindowHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._dwm_blur_enabled = False
        self._cached_frosted_colors = None
        self._cached_frosted_theme = None

    def showEvent(self, event):
        super().showEvent(event)
        if is_linux() and self.parent():
            try:
                from PySide6.QtGui import QWindow
                parent_handle = self.parent().windowHandle()
                if parent_handle is None:
                    self.parent().createWinId()
                    parent_handle = self.parent().windowHandle()
                if parent_handle:
                    self_handle = self.windowHandle()
                    if self_handle is None:
                        self.createWinId()
                        self_handle = self.windowHandle()
                    if self_handle and self_handle.transientParent() is None:
                        self_handle.setTransientParent(parent_handle)
            except Exception:
                pass
        if is_android():
            return
        if is_macos():
            from ui.styles import AppStyles
            if AppStyles._visual_style == 'frosted' and not self._dwm_blur_enabled:
                self._try_enable_macos_blur()
            return
        if not is_windows():
            return

    def _try_enable_macos_blur(self):
        try:
            from ui.styles import AppStyles
            if AppStyles._visual_style != 'frosted':
                if self._dwm_blur_enabled:
                    self._dwm_blur_enabled = False
                return
            if self._dwm_blur_enabled:
                return
            self._dwm_blur_enabled = True
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        except Exception:
            pass

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
            if is_wayland():
                wh = self.windowHandle()
                if wh:
                    wh.startSystemMove()
                    event.accept()
                    return
            self.dragging = True
            self.offset = event.position().toPoint()

    def mouseMoveEvent(self, event):
        if self.dragging and self.offset is not None:
            new_position = event.globalPosition().toPoint() - self.offset
            self.move(new_position.x(), new_position.y())

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = False

    def paintEvent(self, event):
        from PySide6.QtGui import QPainterPath
        from PySide6.QtCore import QRectF
        from ui.styles import AppStyles, color_to_hex, rgba_to_blended_hex

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        colors = AppStyles._get_colors()
        neo = AppStyles.is_neumorphic()
        is_frosted = AppStyles._visual_style == 'frosted'

        if is_frosted:
            current_theme = AppStyles._current_theme
            if self._cached_frosted_theme != current_theme:
                effective_mode = AppStyles._get_effective_color_mode()
                bg = (0, 0, 0) if effective_mode == 'dark' else (255, 255, 255)
                self._cached_frosted_colors = {}
                for k, v in colors.items():
                    self._cached_frosted_colors[k] = rgba_to_blended_hex(v, bg) if isinstance(v, str) and v.startswith('rgba') else v
                self._cached_frosted_theme = current_theme
            dlg_colors = self._cached_frosted_colors
        else:
            dlg_colors = colors

        path = QPainterPath()
        corner_r = AppStyles._get_style_border_radius()
        path.addRoundedRect(QRectF(self.rect()), corner_r, corner_r)

        bg_hex = dlg_colors.get(self._bg_color_key, '#333333')
        r, g, b = _parse_hex_color(bg_hex)
        painter.fillPath(path, QColor(r, g, b, self.opacity))
        if neo:
            br, bg, bb = _parse_hex_color(dlg_colors.get(self._border_color_key, '#999999'))
            painter.setPen(QColor(br, bg, bb, 60))
            painter.drawPath(path)

        super().paintEvent(event)

