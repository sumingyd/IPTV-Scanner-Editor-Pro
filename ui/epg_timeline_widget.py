from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from PyQt6.QtWidgets import QWidget, QScrollArea, QVBoxLayout, QHBoxLayout, QLabel, QFrame
from PyQt6.QtCore import Qt, QRectF, QPoint
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QBrush, QLinearGradient
from ui.styles import AppStyles
from core.log_manager import global_logger as logger


class EpgTimelineWidget(QWidget):
    HOUR_WIDTH = 120
    ROW_HEIGHT = 36
    HEADER_HEIGHT = 28
    LEFT_MARGIN = 120

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
            now = datetime.now()
            self._start_hour = 0
        else:
            now = datetime.now()
            self._start_hour = max(0, now.hour - 2)
        n = len(self._channels)
        h = n * self.ROW_HEIGHT + 10
        self.setMinimumHeight(max(200, h))
        self.setFixedWidth(self._hours * self.HOUR_WIDTH)
        self.update()

    def get_current_time_x(self):
        now = datetime.now()
        base = datetime.now().replace(hour=self._start_hour, minute=0, second=0, microsecond=0)
        now_sec = (now - base).total_seconds()
        now_x = (now_sec / 3600) * self.HOUR_WIDTH
        return now_x

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

        w = self._hours * self.HOUR_WIDTH
        font = QFont()
        font.setPixelSize(11)
        painter.setFont(font)
        painter.setPen(text)

        for h in range(self._hours + 1):
            hour = self._start_hour + h
            if hour > 23:
                hour -= 24
            x = h * self.HOUR_WIDTH
            painter.drawText(x + 4, 0, self.HOUR_WIDTH - 8, self.HEADER_HEIGHT,
                           Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                           f"{hour:02d}:00")
            painter.setPen(QPen(border, 1))
            painter.drawLine(x, 0, x, len(self._channels) * self.ROW_HEIGHT)

        for i, ch_data in enumerate(self._channels):
            y = i * self.ROW_HEIGHT
            painter.setPen(QPen(border, 1))
            painter.drawLine(0, y + self.ROW_HEIGHT, w, y + self.ROW_HEIGHT)

            programs = ch_data.get('programs', [])
            for prog in programs:
                try:
                    start = datetime.fromisoformat(prog.get('start', ''))
                    end = datetime.fromisoformat(prog.get('end', ''))
                    base = datetime.now().replace(hour=self._start_hour, minute=0, second=0, microsecond=0)
                    start_sec = (start - base).total_seconds()
                    end_sec = (end - base).total_seconds()
                    x1 = (start_sec / 3600) * self.HOUR_WIDTH
                    x2 = (end_sec / 3600) * self.HOUR_WIDTH
                    if x2 < 0 or x1 > w:
                        continue
                    x1 = max(0, x1)
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
        now_x = (now_sec / 3600) * self.HOUR_WIDTH
        if 0 <= now_x <= w:
            pen_now = QPen(accent, 2)
            painter.setPen(pen_now)
            painter.drawLine(int(now_x), 0, int(now_x), len(self._channels) * self.ROW_HEIGHT)

        painter.end()

    def _get_program_at(self, pos):
        x, y = pos.x(), pos.y()
        row = y // self.ROW_HEIGHT
        if row < 0 or row >= len(self._channels):
            return None, None
        ch = self._channels[row]
        base = datetime.now().replace(hour=self._start_hour, minute=0, second=0, microsecond=0)
        click_sec = (x / self.HOUR_WIDTH) * 3600
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


class EpgChannelHeaderWidget(QWidget):
    ROW_HEIGHT = 36

    def __init__(self, parent=None):
        super().__init__(parent)
        self._channels: List[Dict[str, Any]] = []
        self.setAutoFillBackground(False)

    def set_data(self, channels: List[Dict[str, Any]]):
        self._channels = channels
        n = len(self._channels)
        h = n * self.ROW_HEIGHT + 10
        self.setFixedHeight(max(200, h))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = AppStyles._get_colors()
        bg = QColor(c.get('player_panel', c.get('window', '#1e1e1e')))
        text = QColor(c.get('player_panel_text', c.get('window_text', '#ffffff')))
        border = QColor(c.get('player_line', c.get('mid', '#333333')))
        header_bg = QColor(c.get('alternate_base', c.get('window', '#2d2d2d')))

        w = self.width()
        painter.fillRect(self.rect(), header_bg)

        pen = QPen(border, 1)
        font = QFont()
        font.setPixelSize(11)
        painter.setFont(font)
        painter.setPen(text)

        for i, ch_data in enumerate(self._channels):
            y = i * self.ROW_HEIGHT
            painter.setPen(pen)
            painter.drawLine(0, y + self.ROW_HEIGHT, w, y + self.ROW_HEIGHT)
            painter.setPen(text)
            ch_name = ch_data.get('name', '')
            painter.drawText(4, y, w - 8, self.ROW_HEIGHT,
                           Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                           ch_name)

        painter.end()


class EpgTimeHeaderWidget(QWidget):
    HOUR_WIDTH = 120
    HEADER_HEIGHT = 28

    def __init__(self, parent=None):
        super().__init__(parent)
        self._start_hour = 0
        self._hours = 24
        self.setAutoFillBackground(False)

    def set_start_hour(self, start_hour):
        self._start_hour = start_hour
        self.setFixedWidth(self._hours * self.HOUR_WIDTH)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = AppStyles._get_colors()
        text = QColor(c.get('player_panel_text', c.get('window_text', '#ffffff')))
        border = QColor(c.get('player_line', c.get('mid', '#333333')))
        header_bg = QColor(c.get('alternate_base', c.get('window', '#2d2d2d')))

        w = self._hours * self.HOUR_WIDTH
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
            x = h * self.HOUR_WIDTH
            painter.drawText(x + 4, 0, self.HOUR_WIDTH - 8, self.HEADER_HEIGHT,
                           Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                           f"{hour:02d}:00")
            painter.setPen(pen)
            painter.drawLine(x, 0, x, self.HEADER_HEIGHT)

        painter.end()
