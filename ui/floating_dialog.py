from PyQt6.QtWidgets import QFrame, QDialog
from PyQt6.QtGui import QPainter, QColor
from PyQt6.QtCore import Qt


class TranslucentPanel(QFrame):
    def __init__(self, parent=None, opacity=180):
        super().__init__(parent)
        self.opacity = opacity
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def paintEvent(self, event):
        from PyQt6.QtGui import QPainterPath
        from PyQt6.QtCore import QRectF
        from ui.styles import AppStyles

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        path = QPainterPath()
        rect = QRectF(self.rect().adjusted(1, 1, -1, -1))
        path.addRoundedRect(rect, 8, 8)

        colors = AppStyles._get_colors()
        neo = AppStyles.is_neumorphic()

        bg_hex = colors.get('player_panel', '#1e1e1e')
        r = int(bg_hex[1:3], 16)
        g = int(bg_hex[3:5], 16)
        b = int(bg_hex[5:7], 16)
        painter.fillPath(path, QColor(r, g, b, self.opacity))

        if not neo:
            border_hex = colors.get('mid', '#646464')
            br = int(border_hex[1:3], 16)
            bg = int(border_hex[3:5], 16)
            bb = int(border_hex[5:7], 16)
            painter.setPen(QColor(br, bg, bb, 150))
            painter.drawPath(path)

        super().paintEvent(event)


class FloatingDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.dragging = False
        self.offset = None
        from ui.styles import AppStyles
        colors = AppStyles._get_colors()
        self.opacity = colors.get('window_opacity', 220)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = True
            self.offset = event.position().toPoint()

    def mouseMoveEvent(self, event):
        if self.dragging and self.offset is not None:
            from PyQt6.QtCore import QPoint
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
        path.addRoundedRect(rect, 12, 12)

        bg_color = colors.get('window', '#333333')
        if bg_color.startswith('#'):
            r = int(bg_color[1:3], 16)
            g = int(bg_color[3:5], 16)
            b = int(bg_color[5:7], 16)
        else:
            r, g, b = 30, 30, 30
        painter.fillPath(path, QColor(r, g, b, self.opacity))

        if not neo:
            border_color = colors.get('mid', '#999999')
            if border_color.startswith('#'):
                r = int(border_color[1:3], 16)
                g = int(border_color[3:5], 16)
                b = int(border_color[5:7], 16)
            else:
                r, g, b = 120, 120, 120
            painter.setPen(QColor(r, g, b, 200))
            painter.drawPath(path)

        super().paintEvent(event)
