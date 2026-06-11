from typing import Dict, Any, List
from datetime import datetime, date
from PySide6.QtWidgets import (QVBoxLayout, QHBoxLayout, QScrollArea,
                               QPushButton, QDateEdit, QLabel, QWidget,
                               QCalendarWidget, QSizePolicy, QScrollBar)
from PySide6.QtCore import Qt, QDate, Signal, QThread, QTimer
from ui.styles import AppStyles
from ui.floating_dialog import FloatingDialog
from ui.epg_timeline_widget import EpgTimelineWidget, EpgChannelHeaderWidget, EpgTimeHeaderWidget
from core.log_manager import global_logger as logger


class _TimelineLoadWorker(QThread):
    data_ready = Signal(list, object)

    def __init__(self, epg_parser, channels, selected_date):
        super().__init__()
        self._epg_parser = epg_parser
        self._channels = channels
        self._selected_date = selected_date

    def run(self):
        channels_data = []
        for ch in self._channels:
            ch_name = ch.get('name', '')
            tvg_id = ch.get('tvg_id', '')
            all_tags = ch.get('_all_tags', {})
            tvg_name = all_tags.get('tvg-name', '')
            comma_name = ''
            raw_extinf = ch.get('_raw_extinf', '')
            if raw_extinf and ',' in raw_extinf:
                comma_name = raw_extinf.split(',', 1)[-1].strip()
                if comma_name.startswith('"') and comma_name.endswith('"'):
                    comma_name = comma_name[1:-1]

            programs = []
            try:
                all_programs = self._epg_parser.get_channel_epg(
                    ch_name, tvg_id, tvg_name=tvg_name, comma_name=comma_name
                ) or []
                if all_programs and self._selected_date:
                    for p in all_programs:
                        try:
                            p_start = datetime.fromisoformat(p.get('start', ''))
                            if p_start.date() == self._selected_date:
                                programs.append(p)
                        except Exception:
                            pass
                else:
                    programs = all_programs
            except Exception as e:
                logger.debug(f"EPG时间轴获取节目失败: {ch_name} - {e}")

            channels_data.append({
                'name': ch_name,
                'programs': programs,
            })
        self.data_ready.emit(channels_data, self._selected_date)


class EpgTimelineDialog(FloatingDialog):
    channel_selected = Signal(dict)

    def __init__(self, main_window, parent=None):
        super().__init__(parent, frameless=True, stay_on_top=False, tool_window=False)
        self.window = main_window
        tr = main_window.language_manager.tr
        self._title_text = tr('epg_timeline', 'EPG时间轴')
        self.setWindowTitle(self._title_text)
        self.setMinimumSize(1000, 600)
        self._channels_data: List[Dict[str, Any]] = []
        self._load_worker = None
        self._setup_ui()
        self._apply_theme()
        self._load_data()
        try:
            from ui.theme_manager import get_theme_manager
            get_theme_manager().register_window(self)
        except Exception:
            pass

    def _apply_theme(self):
        c = AppStyles._get_colors()
        r = AppStyles._get_style_border_radius()
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {c.get('panel', '#1e1e1e')};
                color: {c.get('window_text', '#ffffff')};
            }}
            QLabel {{
                color: {c.get('window_text', '#ffffff')};
                background-color: transparent;
            }}
            QDateEdit {{
                background-color: {c.get('player_combo', '#2a2a2a')};
                color: {c.get('window_text', '#ffffff')};
                border: 1px solid {c.get('player_line', '#555')};
                border-radius: {r}px;
                padding: 2px 8px;
                min-height: 24px;
            }}
            QDateEdit::up-button {{
                width: 0px;
                border: none;
            }}
            QDateEdit::down-button {{
                width: 0px;
                border: none;
            }}
            QDateEdit::drop-down {{
                border: none;
                width: 24px;
                subcontrol-origin: padding;
                subcontrol-position: center right;
            }}
            QPushButton {{
                background-color: {c.get('player_button', '#3a3a3a')};
                color: {c.get('window_text', '#ffffff')};
                border: 1px solid {c.get('player_line', '#555')};
                border-radius: {r}px;
                padding: 4px 12px;
                min-height: 24px;
            }}
            QPushButton:hover {{
                background-color: {c.get('accent', '#4a9eff')};
            }}
            QPushButton:pressed {{
                background-color: {c.get('accent_pressed', '#3a7acc')};
            }}
            QScrollArea {{
                background-color: transparent;
                border: none;
            }}
            QScrollBar:vertical {{
                background-color: {c.get('dark', '#1a1a1a')};
                width: 10px;
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {c.get('mid', '#555555')};
                min-height: 30px;
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: {c.get('accent', '#4a9eff')};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: none;
            }}
            QScrollBar:horizontal {{
                background-color: {c.get('dark', '#1a1a1a')};
                height: 10px;
                border-radius: 5px;
            }}
            QScrollBar::handle:horizontal {{
                background-color: {c.get('mid', '#555555')};
                min-width: 30px;
                border-radius: 5px;
            }}
            QScrollBar::handle:horizontal:hover {{
                background-color: {c.get('accent', '#4a9eff')};
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                width: 0px;
            }}
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
                background: none;
            }}
            QCalendarWidget {{
                background-color: {c.get('base', '#1e1e1e')};
                color: {c.get('window_text', '#ffffff')};
            }}
            QCalendarWidget QWidget {{
                alternate-background-color: {c.get('alternate_base', '#2d2d2d')};
            }}
            QCalendarWidget QToolButton {{
                color: {c.get('window_text', '#ffffff')};
                background-color: {c.get('player_button', '#3a3a3a')};
                border-radius: {r}px;
                padding: 4px;
                min-width: 80px;
            }}
            QCalendarWidget QToolButton:hover {{
                background-color: {c.get('accent', '#4a9eff')};
            }}
            QCalendarWidget QMenu {{
                background-color: {c.get('base', '#1e1e1e')};
                color: {c.get('window_text', '#ffffff')};
            }}
            QCalendarWidget QAbstractItemView {{
                background-color: {c.get('base', '#1e1e1e')};
                color: {c.get('window_text', '#ffffff')};
                selection-background-color: {c.get('accent', '#4a9eff')};
                selection-color: {c.get('highlighted_text', '#ffffff')};
                alternate-background-color: {c.get('alternate_base', '#2d2d2d')};
            }}
            QCalendarWidget QSpinBox {{
                color: {c.get('window_text', '#ffffff')};
                background-color: {c.get('player_combo', '#2a2a2a')};
            }}
        """)

    def _setup_ui(self):
        tr = self.window.language_manager.tr

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(8, 0, 8, 8)
        outer_layout.setSpacing(0)

        title_bar = FloatingDialog.create_dialog_title_bar(self._title_text, self)
        outer_layout.addWidget(title_bar)

        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(8, 8, 8, 0)
        content_layout.setSpacing(6)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        date_label = QLabel(tr('epg_date', '日期'))
        toolbar.addWidget(date_label)

        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat('yyyy-MM-dd')
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.dateChanged.connect(self._on_date_changed)
        self.date_edit.setFixedSize(130, 30)
        toolbar.addWidget(self.date_edit)

        toolbar.addStretch(1)

        self.refresh_btn = QPushButton(tr('refresh', '刷新'))
        self.refresh_btn.clicked.connect(self._load_data)
        toolbar.addWidget(self.refresh_btn)

        content_layout.addLayout(toolbar)

        self._grid_widget = QWidget()
        self._grid_layout = QVBoxLayout(self._grid_widget)
        self._grid_layout.setContentsMargins(0, 0, 0, 0)
        self._grid_layout.setSpacing(0)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(0)

        self._corner_widget = QWidget()
        self._corner_widget.setFixedSize(EpgTimelineWidget.LEFT_MARGIN, EpgTimelineWidget.HEADER_HEIGHT)
        self._corner_widget.setAutoFillBackground(True)
        top_row.addWidget(self._corner_widget)

        self.time_header_container = QWidget()
        self.time_header_container.setFixedHeight(EpgTimelineWidget.HEADER_HEIGHT)
        self._time_header_layout = QHBoxLayout(self.time_header_container)
        self._time_header_layout.setContentsMargins(0, 0, 0, 0)
        self._time_header_layout.setSpacing(0)
        self.time_header = EpgTimeHeaderWidget()
        self.time_header.setFixedHeight(EpgTimelineWidget.HEADER_HEIGHT)
        self._time_header_layout.addWidget(self.time_header)
        self._time_header_layout.addStretch()
        top_row.addWidget(self.time_header_container, 1)

        self._grid_layout.addLayout(top_row)

        bottom_row = QHBoxLayout()
        bottom_row.setContentsMargins(0, 0, 0, 0)
        bottom_row.setSpacing(0)

        self.channel_scroll = QScrollArea()
        self.channel_scroll.setWidgetResizable(True)
        self.channel_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.channel_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.channel_scroll.setFixedWidth(EpgTimelineWidget.LEFT_MARGIN)
        self.channel_header = EpgChannelHeaderWidget()
        self.channel_scroll.setWidget(self.channel_header)
        bottom_row.addWidget(self.channel_scroll)

        self.main_scroll = QScrollArea()
        self.main_scroll.setWidgetResizable(True)
        self.timeline_widget = EpgTimelineWidget()
        self.timeline_widget.channel_double_clicked.connect(self._on_channel_double_clicked)
        self.main_scroll.setWidget(self.timeline_widget)
        bottom_row.addWidget(self.main_scroll, 1)

        self._grid_layout.addLayout(bottom_row, 1)

        content_layout.addWidget(self._grid_widget, 1)
        outer_layout.addLayout(content_layout)

        self.main_scroll.verticalScrollBar().valueChanged.connect(self._sync_v_scroll)
        self.main_scroll.horizontalScrollBar().valueChanged.connect(self._sync_h_scroll)
        self._v_scroll_timer = QTimer()
        self._v_scroll_timer.setSingleShot(True)
        self._v_scroll_timer.setInterval(16)
        self._v_scroll_timer.timeout.connect(self._apply_v_scroll)
        self._pending_v_value = 0
        self._h_scroll_timer = QTimer()
        self._h_scroll_timer.setSingleShot(True)
        self._h_scroll_timer.setInterval(16)
        self._h_scroll_timer.timeout.connect(self._apply_h_scroll)
        self._pending_h_value = 0

    def _sync_v_scroll(self, value):
        self._pending_v_value = value
        if not self._v_scroll_timer.isActive():
            self._v_scroll_timer.start()

    def _apply_v_scroll(self):
        self.channel_scroll.verticalScrollBar().setValue(self._pending_v_value)

    def _sync_h_scroll(self, value):
        self._pending_h_value = value
        if not self._h_scroll_timer.isActive():
            self._h_scroll_timer.start()

    def _apply_h_scroll(self):
        self.time_header.move(-self._pending_h_value, 0)

    def _on_date_changed(self, date):
        self._load_data()

    def _get_epg_dates(self):
        epg_parser = getattr(self.window, 'epg_parser', None)
        if not epg_parser:
            return set()
        dates = set()
        try:
            epg_data = getattr(epg_parser, '_epg_data', {})
            for channel_id, programs in epg_data.items():
                for prog in programs:
                    try:
                        start_str = prog.get('start', '')
                        if start_str:
                            d = datetime.fromisoformat(start_str).date()
                            dates.add(d)
                    except Exception:
                        pass
        except Exception:
            pass
        return dates

    def _load_data(self):
        w = self.window
        epg_parser = getattr(w, 'epg_parser', None)
        if not epg_parser:
            logger.debug("EPG时间轴: epg_parser不可用")
            return

        selected_date = self.date_edit.date().toPyDate()
        channels = list(getattr(w, '_sub_channels', []))

        if self._load_worker and self._load_worker.isRunning():
            self._load_worker.data_ready.disconnect(self._on_data_loaded)
            self._load_worker.quit()
            self._load_worker.wait(1000)

        self._load_worker = _TimelineLoadWorker(epg_parser, channels, selected_date)
        self._load_worker.data_ready.connect(self._on_data_loaded)
        self._load_worker.start()

    def _on_data_loaded(self, channels_data, selected_date):
        self._channels_data = channels_data
        logger.debug(f"EPG时间轴: 加载{len(channels_data)}个频道数据")

        self.timeline_widget.set_data(channels_data, selected_date)
        self.channel_header.set_data(channels_data)
        self.time_header.set_start_hour(self.timeline_widget._start_hour)

        self._update_corner_widget()

        self._mark_calendar_dates()

        QTimer.singleShot(100, self._scroll_to_current_time)

    def _update_corner_widget(self):
        c = AppStyles._get_colors()
        header_bg = c.get('alternate_base', c.get('window', '#2d2d2d'))
        self._corner_widget.setStyleSheet(f"background-color: {header_bg};")

    def _mark_calendar_dates(self):
        epg_dates = self._get_epg_dates()
        calendar = self.date_edit.calendarWidget()
        if not calendar:
            return
        try:
            calendar.setMinimumSize(320, 240)
            fmt = calendar.dateTextFormat()
            fmt.clear()
            accent = AppStyles._get_colors().get('accent', '#4a9eff')
            for d in epg_dates:
                qd = QDate(d.year, d.month, d.day)
                fmt[qd] = Qt.TextFormat.RichText
            calendar.setDateTextFormat(fmt)
        except Exception:
            pass

    def _scroll_to_current_time(self):
        now_x = self.timeline_widget.get_current_time_x()
        viewport_width = self.main_scroll.viewport().width()
        target_x = int(now_x - viewport_width / 2)
        if target_x < 0:
            target_x = 0
        self.main_scroll.horizontalScrollBar().setValue(target_x)

    def _on_channel_double_clicked(self, channel_name: str):
        w = self.window
        channels = getattr(w, '_sub_channels', []) + getattr(w, '_local_channels', [])
        for ch in channels:
            if ch.get('name', '') == channel_name:
                w.current_channel = ch
                if hasattr(w, 'update_channel_info_on_selection'):
                    w.update_channel_info_on_selection()
                if hasattr(w, 'play_channel'):
                    w.play_channel(ch)

                return
