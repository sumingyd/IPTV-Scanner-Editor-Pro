from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from PySide6.QtWidgets import QWidget, QScrollArea, QVBoxLayout, QHBoxLayout, QLabel, QFrame
from PySide6.QtCore import Qt, QRectF, QPoint, Signal
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QBrush, QLinearGradient
from ui.styles import AppStyles
from core.log_manager import global_logger as logger


class EpgTimelineWidget(QWidget):
    HOUR_WIDTH = 120
    ROW_HEIGHT = 36
    HEADER_HEIGHT = 28
    LEFT_MARGIN = 120
    channel_double_clicked = Signal(str)

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
        self._cached_rects: List[List[Dict[str, Any]]] = []
        self._cache_valid = False

    def set_data(self, channels: List[Dict[str, Any]], date=None):
        self._channels = channels
        if date:
            self._start_hour = 0
        else:
            now = datetime.now()
            self._start_hour = max(0, now.hour - 2)
        n = len(self._channels)
        h = n * self.ROW_HEIGHT + 10
        self.setMinimumHeight(max(200, h))
        self.setFixedWidth(self._hours * self.HOUR_WIDTH)
        self._cache_valid = False
        self._build_cache()
        self.update()

    def _build_cache(self):
        self._cached_rects = []
        base = datetime.now().replace(hour=self._start_hour, minute=0, second=0, microsecond=0)
        w = self._hours * self.HOUR_WIDTH
        for ch_data in self._channels:
            row_rects = []
            programs = ch_data.get('programs', [])
            for prog in programs:
                try:
                    start = datetime.fromisoformat(prog.get('start', ''))
                    end = datetime.fromisoformat(prog.get('end', ''))
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
                    row_rects.append({
                        'x1': int(x1), 'x2': int(x2),
                        'title': prog.get('title', ''),
                        'is_current': start <= datetime.now() <= end,
                    })
                except Exception:
                    pass
            self._cached_rects.append(row_rects)
        self._cache_valid = True

    def get_current_time_x(self):
        now = datetime.now()
        base = datetime.now().replace(hour=self._start_hour, minute=0, second=0, microsecond=0)
        now_sec = (now - base).total_seconds()
        now_x = (now_sec / 3600) * self.HOUR_WIDTH
        return now_x

    def paintEvent(self, event):
        if not self._cache_valid:
            self._build_cache()
        painter = QPainter(self)
        c = AppStyles._get_colors()
        bg = QColor(c.get('player_panel', c.get('window', '#1e1e1e')))
        text = QColor(c.get('player_panel_text', c.get('window_text', '#ffffff')))
        accent = QColor(c.get('accent', '#4a9eff'))
        border = QColor(c.get('player_line', c.get('mid', '#333333')))
        program_bg = QColor(c.get('alternate_base', '#2a2a2a'))
        current_bg = QColor(c.get('highlight', '#264f78'))

        clip = event.rect()
        painter.fillRect(clip, bg)

        w = self._hours * self.HOUR_WIDTH
        font = QFont()
        font.setPixelSize(11)
        painter.setFont(font)
        painter.setPen(text)

        first_hour = max(0, clip.left() // self.HOUR_WIDTH)
        last_hour = min(self._hours, clip.right() // self.HOUR_WIDTH + 1)
        for h in range(first_hour, last_hour + 1):
            hour = self._start_hour + h
            if hour > 23:
                hour -= 24
            x = h * self.HOUR_WIDTH
            painter.drawText(x + 4, 0, self.HOUR_WIDTH - 8, self.HEADER_HEIGHT,
                           Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                           f"{hour:02d}:00")
            painter.setPen(QPen(border, 1))
            painter.drawLine(x, 0, x, len(self._channels) * self.ROW_HEIGHT)
            painter.setPen(text)

        first_row = max(0, clip.top() // self.ROW_HEIGHT)
        last_row = min(len(self._channels), clip.bottom() // self.ROW_HEIGHT + 1)

        pen_border = QPen(border, 1)
        small_font = QFont()
        small_font.setPixelSize(10)

        for i in range(first_row, last_row):
            ch_data = self._channels[i]
            y = i * self.ROW_HEIGHT
            painter.setPen(pen_border)
            painter.drawLine(0, y + self.ROW_HEIGHT, w, y + self.ROW_HEIGHT)

            if i < len(self._cached_rects):
                for rect_info in self._cached_rects[i]:
                    rx1, rx2 = rect_info['x1'], rect_info['x2']
                    if rx2 < clip.left() or rx1 > clip.right():
                        continue
                    fill = current_bg if rect_info['is_current'] else program_bg
                    painter.fillRect(rx1 + 1, y + 3, rx2 - rx1 - 2, self.ROW_HEIGHT - 6, fill)
                    painter.setPen(text)
                    painter.setFont(small_font)
                    painter.drawText(rx1 + 4, y + 3, rx2 - rx1 - 8, self.ROW_HEIGHT - 6,
                                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                                   rect_info['title'])
                    painter.setFont(font)

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

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            ch, prog = self._get_program_at(event.position().toPoint() if hasattr(event, 'position') else event.pos())
            if ch:
                ch_name = ch.get('name', '')
                self.channel_double_clicked.emit(ch_name)


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
        c = AppStyles._get_colors()
        text = QColor(c.get('player_panel_text', c.get('window_text', '#ffffff')))
        border = QColor(c.get('player_line', c.get('mid', '#333333')))
        header_bg = QColor(c.get('alternate_base', c.get('window', '#2d2d2d')))

        w = self.width()
        clip = event.rect()
        painter.fillRect(clip, header_bg)

        pen = QPen(border, 1)
        font = QFont()
        font.setPixelSize(11)
        painter.setFont(font)
        painter.setPen(text)

        first_row = max(0, clip.top() // self.ROW_HEIGHT)
        last_row = min(len(self._channels), clip.bottom() // self.ROW_HEIGHT + 1)

        for i in range(first_row, last_row):
            y = i * self.ROW_HEIGHT
            painter.setPen(pen)
            painter.drawLine(0, y + self.ROW_HEIGHT, w, y + self.ROW_HEIGHT)
            painter.setPen(text)
            ch_name = self._channels[i].get('name', '')
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
        c = AppStyles._get_colors()
        text = QColor(c.get('player_panel_text', c.get('window_text', '#ffffff')))
        border = QColor(c.get('player_line', c.get('mid', '#333333')))
        header_bg = QColor(c.get('alternate_base', c.get('window', '#2d2d2d')))

        w = self._hours * self.HOUR_WIDTH
        clip = event.rect()
        painter.fillRect(clip, header_bg)
        pen = QPen(border, 1)
        painter.setPen(pen)
        painter.drawLine(0, self.HEADER_HEIGHT, w, self.HEADER_HEIGHT)

        font = QFont()
        font.setPixelSize(11)
        painter.setFont(font)
        painter.setPen(text)

        first_hour = max(0, clip.left() // self.HOUR_WIDTH)
        last_hour = min(self._hours, clip.right() // self.HOUR_WIDTH + 1)

        for h in range(first_hour, last_hour + 1):
            hour = self._start_hour + h
            if hour > 23:
                hour -= 24
            x = h * self.HOUR_WIDTH
            painter.drawText(x + 4, 0, self.HOUR_WIDTH - 8, self.HEADER_HEIGHT,
                           Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                           f"{hour:02d}:00")
            painter.setPen(pen)
            painter.drawLine(x, 0, x, self.HEADER_HEIGHT)
            painter.setPen(text)

        painter.end()
