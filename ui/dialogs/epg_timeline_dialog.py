from typing import Dict, Any, List
from datetime import datetime
from PyQt6.QtWidgets import (QVBoxLayout, QHBoxLayout, QScrollArea,
                              QPushButton, QDateEdit, QLabel)
from PyQt6.QtCore import Qt, QDate, pyqtSignal
from ui.styles import AppStyles
from ui.floating_dialog import FloatingDialog
from ui.epg_timeline_widget import EpgTimelineWidget
from core.log_manager import global_logger as logger


class EpgTimelineDialog(FloatingDialog):
    channel_selected = pyqtSignal(dict)

    def __init__(self, main_window, parent=None):
        super().__init__(parent, frameless=False, stay_on_top=False)
        self.window = main_window
        tr = main_window.language_manager.tr
        self.setWindowTitle(tr('epg_timeline', 'EPG时间轴'))
        self.setMinimumSize(900, 500)
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
                padding: 2px 6px;
                min-height: 24px;
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
        """)

    def _setup_ui(self):
        tr = self.window.language_manager.tr

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        date_label = QLabel(tr('epg_date', '日期'))
        toolbar.addWidget(date_label)

        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.dateChanged.connect(self._on_date_changed)
        toolbar.addWidget(self.date_edit)

        toolbar.addStretch(1)

        self.refresh_btn = QPushButton(tr('refresh', '刷新'))
        self.refresh_btn.clicked.connect(self._load_data)
        toolbar.addWidget(self.refresh_btn)

        layout.addLayout(toolbar)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.timeline_widget = EpgTimelineWidget()
        self.scroll.setWidget(self.timeline_widget)
        layout.addWidget(self.scroll, 1)

    def _on_date_changed(self, date):
        self._load_data()

    def _load_data(self):
        w = self.window
        epg_parser = getattr(w, 'epg_parser', None)
        if not epg_parser:
            logger.debug("EPG时间轴: epg_parser不可用")
            return

        date = self.date_edit.date().toPyDate()
        channels_data = []
        channels = list(getattr(w, '_sub_channels', []))

        for ch in channels[:30]:
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
                programs = epg_parser.get_channel_epg(
                    ch_name, tvg_id, tvg_name=tvg_name, comma_name=comma_name
                ) or []
            except Exception as e:
                logger.debug(f"EPG时间轴获取节目失败: {ch_name} - {e}")

            if programs:
                channels_data.append({
                    'name': ch_name,
                    'programs': programs,
                })

        logger.debug(f"EPG时间轴: 加载{len(channels_data)}个频道数据")
        self.timeline_widget.set_data(channels_data, date)
