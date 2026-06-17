import math
import random
import struct
import time
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import QTimer, Qt, QRectF
from PySide6.QtGui import QPainter, QColor, QLinearGradient, QRadialGradient, QPen, QBrush, QFont

AUDIO_EXTENSIONS = ('.mp3', '.flac', '.wav', '.aac', '.ogg', '.opus', '.wma', '.m4a',
                    '.ape', '.alac', '.wv', '.tta', '.dts', '.ac3', '.mid', '.midi')

AUDIO_VISUAL_STYLES = {
    'spectrum': {
        'name_key': 'audio_vis_spectrum',
        'name_default': '频谱',
    },
    'cqt': {
        'name_key': 'audio_vis_cqt',
        'name_default': 'CQT频谱',
    },
    'waves': {
        'name_key': 'audio_vis_waves',
        'name_default': '波形',
    },
    'vector_scope': {
        'name_key': 'audio_vis_vectorscope',
        'name_default': '矢量示波器',
    },
    'none': {
        'name_key': 'audio_vis_none',
        'name_default': '关闭可视化',
    },
}

STYLE_KEYS = [k for k in AUDIO_VISUAL_STYLES if k != 'none']


class AudioVisualWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._style = 'spectrum'
        self._active = False
        self._time_offset = 0.0
        self._start_time = 0.0
        self._bars = [0.0] * 64
        self._bars_target = [0.0] * 64
        self._wave_data = [0.0] * 256
        self._scope_x = 0.0
        self._scope_y = 0.0
        self._scope_trail = []

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.setInterval(33)

    def set_style(self, style_key):
        self._style = style_key
        self.update()

    def get_style(self):
        return self._style

    def start(self):
        self._active = True
        self._start_time = time.time()
        self._timer.start()
        self.show()
        self.raise_()

    def stop(self):
        self._active = False
        self._timer.stop()
        self.hide()

    def is_active(self):
        return self._active

    def _tick(self):
        if not self._active:
            return
        t = time.time() - self._start_time
        self._update_data(t)
        self.update()

    def _update_data(self, t):
        if self._style == 'spectrum':
            self._update_spectrum(t)
        elif self._style == 'cqt':
            self._update_cqt(t)
        elif self._style == 'waves':
            self._update_waves(t)
        elif self._style == 'vector_scope':
            self._update_scope(t)

    def _update_spectrum(self, t):
        n = len(self._bars)
        for i in range(n):
            freq = (i + 1) / n
            base = 0.3 + 0.5 * math.exp(-freq * 2)
            beat = 0.3 * max(0, math.sin(t * 4.0 + i * 0.1))
            variation = 0.15 * math.sin(t * 1.7 + i * 0.3) * math.sin(t * 2.3 + i * 0.7)
            noise = random.uniform(-0.05, 0.05)
            target = max(0.02, min(1.0, base + beat + variation + noise))
            self._bars[i] += (target - self._bars[i]) * 0.3

    def _update_cqt(self, t):
        n = len(self._bars)
        for i in range(n):
            freq = (i + 1) / n
            base = 0.4 + 0.4 * math.exp(-freq * 1.5)
            beat = 0.25 * max(0, math.sin(t * 3.5 + i * 0.05))
            variation = 0.2 * math.sin(t * 1.3 + i * 0.5) * math.cos(t * 2.7 + i * 0.2)
            noise = random.uniform(-0.04, 0.04)
            target = max(0.02, min(1.0, base + beat + variation + noise))
            self._bars[i] += (target - self._bars[i]) * 0.25

    def _update_waves(self, t):
        n = len(self._wave_data)
        for i in range(n):
            x = i / n
            val = (0.4 * math.sin(t * 3.0 + x * 12.0)
                   + 0.25 * math.sin(t * 5.0 + x * 20.0)
                   + 0.15 * math.sin(t * 7.0 + x * 30.0)
                   + 0.1 * random.uniform(-1, 1))
            self._wave_data[i] = max(-1.0, min(1.0, val))

    def _update_scope(self, t):
        self._scope_x = (0.6 * math.sin(t * 2.5) + 0.3 * math.sin(t * 4.1) + 0.1 * random.uniform(-1, 1))
        self._scope_y = (0.6 * math.cos(t * 3.3) + 0.3 * math.cos(t * 5.7) + 0.1 * random.uniform(-1, 1))
        self._scope_trail.append((self._scope_x, self._scope_y))
        if len(self._scope_trail) > 80:
            self._scope_trail.pop(0)

    def paintEvent(self, event):
        if not self._active:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        h = self.height()
        if w <= 0 or h <= 0:
            painter.end()
            return

        painter.fillRect(0, 0, w, h, QColor(0, 0, 0))

        if self._style == 'spectrum':
            self._paint_spectrum(painter, w, h)
        elif self._style == 'cqt':
            self._paint_cqt(painter, w, h)
        elif self._style == 'waves':
            self._paint_waves(painter, w, h)
        elif self._style == 'vector_scope':
            self._paint_scope(painter, w, h)

        painter.end()

    def _paint_spectrum(self, painter, w, h):
        n = len(self._bars)
        bar_w = max(2, w / n - 1)
        gap = 1
        for i in range(n):
            val = self._bars[i]
            bar_h = val * h * 0.85
            x = i * (bar_w + gap)
            y = h - bar_h

            grad = QLinearGradient(x, y, x, h)
            hue = int(200 + i * 160 / n) % 360
            grad.setColorAt(0, QColor.fromHsv(hue, 255, 255, 220))
            grad.setColorAt(0.5, QColor.fromHsv(hue, 200, 200, 180))
            grad.setColorAt(1, QColor.fromHsv(hue, 150, 120, 100))
            painter.setBrush(QBrush(grad))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(QRectF(x, y, bar_w, bar_h), 2, 2)

    def _paint_cqt(self, painter, w, h):
        n = len(self._bars)
        bar_w = max(2, w / n - 1)
        gap = 1
        for i in range(n):
            val = self._bars[i]
            bar_h = val * h * 0.85
            x = i * (bar_w + gap)
            y = h - bar_h

            grad = QLinearGradient(x, y, x, h)
            r = int(30 + val * 200)
            g = int(80 + val * 150)
            b = int(180 + val * 75)
            grad.setColorAt(0, QColor(r, g, b, 230))
            grad.setColorAt(1, QColor(r // 2, g // 2, b // 2, 80))
            painter.setBrush(QBrush(grad))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(QRectF(x, y, bar_w, bar_h), 1, 1)

        painter.setPen(QPen(QColor(255, 255, 255, 40), 1))
        for i in range(n):
            val = self._bars[i]
            x = i * (bar_w + gap) + bar_w / 2
            y = h - val * h * 0.85
            if i > 0:
                prev_val = self._bars[i - 1]
                px = (i - 1) * (bar_w + gap) + bar_w / 2
                py = h - prev_val * h * 0.85
                painter.drawLine(int(px), int(py), int(x), int(y))

    def _paint_waves(self, painter, w, h):
        n = len(self._wave_data)
        cy = h / 2

        grad = QLinearGradient(0, 0, w, 0)
        grad.setColorAt(0, QColor(0, 180, 255, 200))
        grad.setColorAt(0.5, QColor(100, 255, 180, 200))
        grad.setColorAt(1, QColor(255, 100, 200, 200))

        painter.setPen(QPen(QBrush(grad), 2.5))
        painter.setBrush(Qt.BrushStyle.NoBrush)

        from PySide6.QtGui import QPolygonF
        from PySide6.QtCore import QPointF
        points = QPolygonF()
        for i in range(n):
            x = i * w / (n - 1)
            y = cy + self._wave_data[i] * h * 0.4
            points.append(QPointF(x, y))
        painter.drawPolyline(points)

        painter.setPen(QPen(QColor(0, 180, 255, 60), 1))
        points2 = QPolygonF()
        for i in range(n):
            x = i * w / (n - 1)
            y = cy + self._wave_data[i] * h * 0.4 + 3
            points2.append(QPointF(x, y))
        painter.drawPolyline(points2)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 180, 255, 15))
        painter.drawRect(0, int(cy - h * 0.4), w, int(h * 0.8))

    def _paint_scope(self, painter, w, h):
        cx = w / 2
        cy = h / 2
        radius = min(w, h) * 0.4

        painter.setPen(QPen(QColor(40, 40, 40), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QRectF(cx - radius, cy - radius, radius * 2, radius * 2))
        painter.drawLine(int(cx - radius), int(cy), int(cx + radius), int(cy))
        painter.drawLine(int(cx), int(cy - radius), int(cx), int(cy + radius))

        trail = self._scope_trail
        n = len(trail)
        if n < 2:
            return

        for i in range(1, n):
            alpha = int(60 + 195 * i / n)
            x1 = cx + trail[i - 1][0] * radius
            y1 = cy + trail[i - 1][1] * radius
            x2 = cx + trail[i][0] * radius
            y2 = cy + trail[i][1] * radius
            hue = (int(time.time() * 50) + i * 3) % 360
            painter.setPen(QPen(QColor.fromHsv(hue, 220, 255, alpha), 2))
            painter.drawLine(int(x1), int(y1), int(x2), int(y2))

        last = trail[-1]
        px = cx + last[0] * radius
        py = cy + last[1] * radius
        painter.setPen(Qt.PenStyle.NoPen)
        grad = QRadialGradient(px, py, 8)
        grad.setColorAt(0, QColor(255, 255, 255, 200))
        grad.setColorAt(1, QColor(0, 180, 255, 0))
        painter.setBrush(QBrush(grad))
        painter.drawEllipse(QRectF(px - 8, py - 8, 16, 16))


class AudioVisualService:
    def __init__(self, player_controller):
        self._pc = player_controller
        self._current_style = 'none'
        self._is_audio_only = False
        self._widget = None

    @property
    def current_style(self):
        return self._current_style

    @property
    def is_audio_only(self):
        return self._is_audio_only

    def is_audio_file(self, url):
        if not url:
            return False
        path = url.split('?')[0].split('#')[0]
        return path.lower().endswith(AUDIO_EXTENSIONS)

    def setup_widget(self, video_frame):
        if self._widget:
            return
        self._widget = AudioVisualWidget(video_frame)
        self._widget.hide()

    def prepare_before_loadfile(self, url):
        if not self.is_audio_file(url):
            self._is_audio_only = False
            self._hide_widget()
            self._current_style = 'none'
            return
        self._is_audio_only = True

    def auto_enable_if_audio(self):
        if self.detect_audio_only():
            if self._current_style == 'none':
                saved = self._load_saved_style()
                if saved and saved != 'none':
                    self._current_style = saved
                else:
                    self._current_style = random.choice(STYLE_KEYS)
            self._show_widget()
            return True
        else:
            if self._current_style != 'none':
                self._hide_widget()
            return False

    def detect_audio_only(self):
        if not self._pc or not self._pc.is_playing:
            self._is_audio_only = False
            return False
        try:
            track_list_str = self._pc._get_mpv_property_string('track-list') or ''
            has_real_video = False
            has_audio = False
            if track_list_str:
                import json
                try:
                    tracks = json.loads(track_list_str)
                    for t in tracks:
                        if t.get('type') == 'video':
                            if not t.get('albumart', False):
                                has_real_video = True
                        elif t.get('type') == 'audio':
                            has_audio = True
                except Exception:
                    pass
            is_audio = has_audio and not has_real_video
            self._is_audio_only = is_audio
            return is_audio
        except Exception:
            self._is_audio_only = False
            return False

    def apply_visual_style(self, style_key):
        if style_key not in AUDIO_VISUAL_STYLES:
            return False
        self._current_style = style_key
        if style_key == 'none':
            self._hide_widget()
        else:
            self._show_widget()
        self.save_current_style()
        return True

    def clear_visual(self):
        self._hide_widget()
        self._current_style = 'none'

    def apply_random_style(self):
        available = [k for k in STYLE_KEYS if k != self._current_style]
        if not available:
            available = STYLE_KEYS
        return self.apply_visual_style(random.choice(available))

    def _show_widget(self):
        if not self._widget:
            return
        self._widget.set_style(self._current_style)
        parent = self._widget.parent()
        if parent:
            self._widget.setGeometry(0, 0, parent.width(), parent.height())
        self._widget.start()

    def _hide_widget(self):
        if self._widget:
            self._widget.stop()

    def resize_widget(self):
        if self._widget and self._widget.isVisible():
            parent = self._widget.parent()
            if parent:
                self._widget.setGeometry(0, 0, parent.width(), parent.height())

    def _load_saved_style(self):
        try:
            from core.config_manager import ConfigManager
            config = ConfigManager()
            return config.get_value('Player', 'audio_visual_style', 'none') or 'none'
        except Exception:
            return 'none'

    def save_current_style(self):
        try:
            from core.config_manager import ConfigManager
            config = ConfigManager()
            config.set_value('Player', 'audio_visual_style', self._current_style)
            config.save_config()
        except Exception:
            pass

    def get_style_display_name(self, style_key, language_manager=None):
        style = AUDIO_VISUAL_STYLES.get(style_key)
        if not style:
            return style_key
        if language_manager:
            return language_manager.tr(style['name_key'], style['name_default'])
        return style['name_default']

    def get_all_styles(self):
        return AUDIO_VISUAL_STYLES
