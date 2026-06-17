import re
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QPainter, QColor, QFont


def parse_lrc(lrc_text):
    lines = []
    time_pattern = re.compile(r'\[(\d{1,2}):(\d{2})(?:[.:](\d{1,3}))?\]')
    tag_pattern = re.compile(r'\[.*?\]')
    for line in lrc_text.split('\n'):
        line = line.strip()
        if not line:
            continue
        matches = time_pattern.findall(line)
        text = tag_pattern.sub('', line).strip()
        if not text:
            continue
        for m in matches:
            try:
                minutes = int(m[0])
                seconds = int(m[1])
                ms = 0
                if m[2]:
                    raw = m[2]
                    if len(raw) == 1:
                        ms = int(raw) * 100
                    elif len(raw) == 2:
                        ms = int(raw) * 10
                    else:
                        ms = int(raw[:3].ljust(3, '0'))
                time_sec = minutes * 60 + seconds + ms / 1000.0
                lines.append((time_sec, text))
            except (ValueError, IndexError):
                continue
    lines.sort(key=lambda x: x[0])
    return lines if lines else None


def parse_plain_lyrics(text):
    lines = []
    for i, line in enumerate(text.split('\n')):
        line = line.strip()
        if line:
            lines.append((i * 5, line))
    return lines if lines else None


class LyricsWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._lines = []
        self._current_idx = -1
        self._scroll_y = 0.0
        self._target_y = 0.0
        self._line_height = 52
        self._font = QFont("Microsoft YaHei", 16)
        self._font_current = QFont("Microsoft YaHei", 22, QFont.Weight.Bold)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.setInterval(40)

    def set_lyrics(self, lrc_text, is_lrc=True):
        if is_lrc:
            parsed = parse_lrc(lrc_text)
            if not parsed:
                parsed = parse_plain_lyrics(lrc_text)
        else:
            parsed = parse_plain_lyrics(lrc_text)
        self._lines = parsed or []
        self._current_idx = -1
        self._scroll_y = 0.0
        self._target_y = 0.0
        self.update()

    def update_time(self, time_sec):
        if not self._lines:
            return
        new_idx = -1
        for i, (t, _) in enumerate(self._lines):
            if t <= time_sec:
                new_idx = i
            else:
                break
        if new_idx != self._current_idx:
            self._current_idx = new_idx
            self._target_y = new_idx * self._line_height
        self.update()

    def start(self):
        self._timer.start()

    def stop(self):
        self._timer.stop()

    def _tick(self):
        diff = self._target_y - self._scroll_y
        if abs(diff) > 0.5:
            self._scroll_y += diff * 0.15
        else:
            self._scroll_y = self._target_y
        self.update()

    def paintEvent(self, event):
        if not self._lines:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        h = self.height()
        if w <= 0 or h <= 0:
            painter.end()
            return

        cy = h / 2.0
        n = len(self._lines)
        visible_count = int(h / self._line_height) + 4
        half = visible_count // 2

        for offset in range(-half, half + 1):
            idx = self._current_idx + offset
            if idx < 0 or idx >= n:
                continue
            _, text = self._lines[idx]

            scroll_frac = (self._scroll_y - self._target_y) / self._line_height if self._line_height > 0 else 0
            y = cy + (offset - scroll_frac) * self._line_height

            if y < -self._line_height * 2 or y > h + self._line_height * 2:
                continue

            distance = abs(offset)
            if distance == 0:
                alpha = 255
                painter.setFont(self._font_current)
                painter.setPen(QColor(255, 255, 255, alpha))
            elif distance == 1:
                alpha = 180
                painter.setFont(self._font)
                painter.setPen(QColor(200, 210, 230, alpha))
            elif distance == 2:
                alpha = 120
                painter.setFont(self._font)
                painter.setPen(QColor(160, 170, 190, alpha))
            else:
                alpha = max(20, 80 - distance * 12)
                painter.setFont(self._font)
                painter.setPen(QColor(120, 130, 150, alpha))

            fm = painter.fontMetrics()
            text_width = fm.horizontalAdvance(text)
            text_height = fm.height()
            x = (w - text_width) / 2.0
            baseline_y = y + text_height / 2.0

            if distance == 0:
                from PySide6.QtGui import QLinearGradient
                grad = QLinearGradient(x, baseline_y, x + text_width, baseline_y)
                grad.setColorAt(0, QColor(80, 180, 255, alpha))
                grad.setColorAt(0.5, QColor(255, 255, 255, alpha))
                grad.setColorAt(1, QColor(80, 180, 255, alpha))
                painter.setPen(QColor(255, 255, 255, alpha))

            painter.drawText(int(x), int(baseline_y), text)

        painter.end()
