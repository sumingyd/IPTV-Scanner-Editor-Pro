from PyQt6.QtWidgets import QSlider
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter, QColor


class CacheProgressSlider(QSlider):

    def __init__(self, orientation=Qt.Orientation.Horizontal, parent=None):
        super().__init__(orientation, parent)
        self._cache_start_ratio = -1.0
        self._cache_end_ratio = -1.0
        self._cache_color = QColor(76, 175, 80, 100)
        self._update_cache_color_from_theme()
        from ui.theme_manager import get_theme_manager
        get_theme_manager().theme_changed.connect(self._on_theme_changed)

    def _on_theme_changed(self, _theme_name):
        self._update_cache_color_from_theme()
        self.update()

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
