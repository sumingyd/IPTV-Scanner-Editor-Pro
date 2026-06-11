from PySide6.QtWidgets import QSlider, QLabel
from PySide6.QtCore import Qt, QRectF, Signal, QPoint
from PySide6.QtGui import QPainter, QColor


class CacheProgressSlider(QSlider):

    preview_position_changed = Signal(int)

    def __init__(self, orientation=Qt.Orientation.Horizontal, parent=None):
        super().__init__(orientation, parent)
        self._cache_start_ratio = -1.0
        self._cache_end_ratio = -1.0
        self._cache_color = QColor(76, 175, 80, 100)
        self._update_cache_color_from_theme()
        from ui.theme_manager import get_theme_manager
        get_theme_manager().theme_changed.connect(self._on_theme_changed)

        self._preview_label = QLabel()
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_label.setVisible(False)
        self._preview_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._preview_label.setWindowFlags(
            Qt.WindowType.ToolTip |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self._update_preview_style()
        self._is_dragging = False

    def _on_theme_changed(self, _theme_name):
        self._update_cache_color_from_theme()
        self._update_preview_style()
        self.update()

    def _update_preview_style(self):
        try:
            from ui.styles import AppStyles
            colors = AppStyles._get_colors()
            bg = colors.get('player_background', AppStyles._safe_fallback('window'))
            text_color = colors.get('player_slider_handle', AppStyles._safe_fallback('window_text'))
            border_color = colors.get('player_slider_fill', AppStyles._safe_fallback('accent'))
            r = AppStyles._get_style_border_radius()
        except Exception:
            bg, text_color, border_color = '#1a1a1a', '#ffffff', '#4CAF50'
            r = 4
        self._preview_label.setStyleSheet(
            f"QLabel {{"
            f"  color: {text_color};"
            f"  background-color: {bg};"
            f"  border: 1px solid {border_color};"
            f"  border-radius: {r}px;"
            f"  padding: 2px 6px;"
            f"  font-size: 11px;"
            f"}}"
        )

    def _update_cache_color_from_theme(self):
        try:
            from ui.styles import AppStyles
            colors = AppStyles._get_colors()
            color_str = colors.get('cache_progress', 'rgba(76,175,80,0.39)')
            self.set_cache_color(color_str)
        except Exception:
            self._cache_color = QColor(76, 175, 80, 100)

    def set_cache_range(self, start_ratio: float, end_ratio: float):
        self._cache_start_ratio = max(0.0, min(1.0, start_ratio))
        self._cache_end_ratio = max(0.0, min(1.0, end_ratio))
        self.update()

    def clear_cache_range(self):
        self._cache_start_ratio = -1.0
        self._cache_end_ratio = -1.0
        self.update()

    def set_cache_color(self, color_str: str):
        try:
            if color_str.startswith('rgba('):
                parts = color_str[5:-1].split(',')
                r = int(parts[0].strip())
                g = int(parts[1].strip())
                b = int(parts[2].strip())
                a = int(float(parts[3].strip()) * 255)
                self._cache_color = QColor(r, g, b, a)
            elif color_str.startswith('#') and len(color_str) == 7:
                self._cache_color = QColor(color_str)
                self._cache_color.setAlpha(100)
            else:
                self._cache_color = QColor(color_str)
        except Exception:
            self._cache_color = QColor(76, 175, 80, 100)

    def set_preview_text(self, text: str):
        self._preview_label.setText(text)
        self._preview_label.adjustSize()
        if self._is_dragging:
            self._update_preview_position()

    def _get_handle_x(self) -> int:
        value = self.value()
        min_val = self.minimum()
        max_val = self.maximum()
        if max_val == min_val:
            return 0
        ratio = (value - min_val) / (max_val - min_val)
        groove_rect = self._get_groove_rect()
        return int(groove_rect.x() + groove_rect.width() * ratio)

    def _update_preview_position(self):
        handle_x = self._get_handle_x()
        label_w = self._preview_label.width()
        label_h = self._preview_label.height()
        global_pos = self.mapToGlobal(QPoint(handle_x, 0))
        x = global_pos.x() - label_w // 2
        y = global_pos.y() - label_h - 6
        self._preview_label.move(x, y)

    def _pos_to_value(self, pos_x):
        groove_rect = self._get_groove_rect()
        if groove_rect.width() <= 0:
            return self.value()
        ratio = max(0.0, min(1.0, (pos_x - groove_rect.x()) / groove_rect.width()))
        return int(self.minimum() + ratio * (self.maximum() - self.minimum()))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_dragging = True
            self.setSliderDown(True)
            new_value = self._pos_to_value(event.position().toPoint().x())
            self.setValue(new_value)
            self.sliderPressed.emit()
            self.preview_position_changed.emit(self.value())
            self._preview_label.setVisible(True)
            self._update_preview_position()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._is_dragging:
            new_value = self._pos_to_value(event.position().toPoint().x())
            self.setValue(new_value)
            self.preview_position_changed.emit(self.value())
            self._update_preview_position()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._is_dragging:
            self._is_dragging = False
            self._preview_label.setVisible(False)
            self.setSliderDown(False)
            self.sliderReleased.emit()
        else:
            super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)

        if self._cache_start_ratio < 0 or self._cache_end_ratio <= self._cache_start_ratio:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        groove_rect = self._get_groove_rect()
        if groove_rect.isEmpty():
            painter.end()
            return

        cache_x_start = groove_rect.x() + groove_rect.width() * self._cache_start_ratio
        cache_x_end = groove_rect.x() + groove_rect.width() * self._cache_end_ratio

        cache_rect = QRectF(
            cache_x_start,
            groove_rect.y(),
            cache_x_end - cache_x_start,
            groove_rect.height()
        )

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._cache_color)
        painter.drawRoundedRect(cache_rect, groove_rect.height() / 2, groove_rect.height() / 2)

        painter.end()

    def _get_groove_rect(self) -> QRectF:
        w = self.width()
        h = self.height()
        groove_height = 4
        y = (h - groove_height) / 2.0
        margin = 5
        return QRectF(margin, y, w - 2 * margin, groove_height)
