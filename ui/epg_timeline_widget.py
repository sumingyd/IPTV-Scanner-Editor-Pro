from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from PyQt6.QtWidgets import QWidget, QScrollArea, QVBoxLayout, QHBoxLayout, QLabel, QFrame
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QBrush, QLinearGradient
from ui.styles import AppStyles
from core.log_manager import global_logger as logger


class EpgTimelineWidget(QWidget):
    HOUR_WIDTH = 120
    ROW_HEIGHT = 36
    HEADER_HEIGHT = 28
    LEFT_MARGIN = 100

    def __init__(self, parent=None):
        super().__init__(parent)
        self._channels: List[Dict[str, Any]] = []
        self._start_hour = 0
        self._hours = 24
        self.setMinimumHeight(200)
        self._hover_channel = -1
        self._hover_program = -1
        self.setMouseTracking(True)
        self.setAutoFillBackground(False)

    def set_data(self, channels: List[Dict[str, Any]], date=None):
        self._channels = channels
        if date:
            self._start_hour = 0
        else:
            now = datetime.now()
            self._start_hour = max(0, now.hour - 2)
        n = len(self._channels)
        h = self.HEADER_HEIGHT + n * self.ROW_HEIGHT + 10
        self.setMinimumHeight(max(200, h))
        self.setFixedWidth(self.LEFT_MARGIN + self._hours * self.HOUR_WIDTH)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = AppStyles._get_colors()
        bg = QColor(c.get('player_panel', c.get('window', '#1e1e1e')))
        text = QColor(c.get('player_panel_text', c.get('window_text', '#ffffff')))
        accent = QColor(c.get('accent', '#4a9eff'))
        border = QColor(c.get('player_line', c.get('mid', '#333333')))
        header_bg = QColor(c.get('alternate_base', c.get('window', '#2d2d2d')))
        program_bg = QColor(c.get('alternate_base', '#2a2a2a'))
        current_bg = QColor(c.get('highlight', '#264f78'))

        painter.fillRect(self.rect(), bg)

        w = self.LEFT_MARGIN + self._hours * self.HOUR_WIDTH
        painter.fillRect(0, 0, w, self.HEADER_HEIGHT, header_bg)
        pen = QPen(border, 1)
        painter.setPen(pen)
        painter.drawLine(0, self.HEADER_HEIGHT, w, self.HEADER_HEIGHT)

        font = QFont()
        font.setPixelSize(11)
        painter.setFont(font)
        painter.setPen(text)
        for h in range(self._hours + 1):
            hour = self._start_hour + h
            if hour > 23:
                hour -= 24
            x = self.LEFT_MARGIN + h * self.HOUR_WIDTH
            painter.drawText(x + 4, 0, self.HOUR_WIDTH - 8, self.HEADER_HEIGHT,
                           Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                           f"{hour:02d}:00")
            painter.setPen(pen)
            painter.drawLine(x, 0, x, self.HEADER_HEIGHT + len(self._channels) * self.ROW_HEIGHT)

        for i, ch_data in enumerate(self._channels):
            y = self.HEADER_HEIGHT + i * self.ROW_HEIGHT
            painter.setPen(pen)
            painter.drawLine(0, y + self.ROW_HEIGHT, w, y + self.ROW_HEIGHT)
            painter.fillRect(0, y, self.LEFT_MARGIN, self.ROW_HEIGHT, header_bg)
            painter.setPen(text)
            ch_name = ch_data.get('name', '')
            painter.drawText(4, y, self.LEFT_MARGIN - 8, self.ROW_HEIGHT,
                           Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                           ch_name)

            programs = ch_data.get('programs', [])
            for prog in programs:
                try:
                    start = datetime.fromisoformat(prog.get('start', ''))
                    end = datetime.fromisoformat(prog.get('end', ''))
                    base = datetime.now().replace(hour=self._start_hour, minute=0, second=0, microsecond=0)
                    start_sec = (start - base).total_seconds()
                    end_sec = (end - base).total_seconds()
                    x1 = self.LEFT_MARGIN + (start_sec / 3600) * self.HOUR_WIDTH
                    x2 = self.LEFT_MARGIN + (end_sec / 3600) * self.HOUR_WIDTH
                    if x2 < self.LEFT_MARGIN or x1 > w:
                        continue
                    x1 = max(self.LEFT_MARGIN, x1)
                    x2 = min(w, x2)
                    if x2 - x1 < 2:
                        continue
                    is_current = start <= datetime.now() <= end
                    fill = current_bg if is_current else program_bg
                    painter.fillRect(int(x1) + 1, y + 3, int(x2 - x1) - 2, self.ROW_HEIGHT - 6, fill)
                    painter.setPen(text)
                    title = prog.get('title', '')
                    small_font = QFont()
                    small_font.setPixelSize(10)
                    painter.setFont(small_font)
                    painter.drawText(int(x1) + 4, y + 3, int(x2 - x1) - 8, self.ROW_HEIGHT - 6,
                                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                                   title)
                    painter.setFont(font)
                except Exception:
                    pass

        now = datetime.now()
        base = datetime.now().replace(hour=self._start_hour, minute=0, second=0, microsecond=0)
        now_sec = (now - base).total_seconds()
        now_x = self.LEFT_MARGIN + (now_sec / 3600) * self.HOUR_WIDTH
        if self.LEFT_MARGIN <= now_x <= w:
            pen_now = QPen(accent, 2)
            painter.setPen(pen_now)
            painter.drawLine(int(now_x), 0, int(now_x), self.HEADER_HEIGHT + len(self._channels) * self.ROW_HEIGHT)

        painter.end()

    def _get_program_at(self, pos):
        x, y = pos.x(), pos.y()
        if y < self.HEADER_HEIGHT or x < self.LEFT_MARGIN:
            return None, None
        row = (y - self.HEADER_HEIGHT) // self.ROW_HEIGHT
        if row < 0 or row >= len(self._channels):
            return None, None
        ch = self._channels[row]
        base = datetime.now().replace(hour=self._start_hour, minute=0, second=0, microsecond=0)
        click_sec = ((x - self.LEFT_MARGIN) / self.HOUR_WIDTH) * 3600
        click_time = base + timedelta(seconds=click_sec)
        for prog in ch.get('programs', []):
            try:
                start = datetime.fromisoformat(prog.get('start', ''))
                end = datetime.fromisoformat(prog.get('end', ''))
                if start <= click_time <= end:
                    return ch, prog
            except Exception:
                pass
        return ch, None