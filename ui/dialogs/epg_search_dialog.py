from typing import Dict, Any, List
from PyQt6.QtWidgets import (QVBoxLayout, QHBoxLayout, QLineEdit,
                              QListWidget, QListWidgetItem, QLabel)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QThread, QTimer
from PyQt6 import QtWidgets
from ui.styles import AppStyles
from ui.floating_dialog import FloatingDialog
from core.log_manager import global_logger as logger


class _EpgSearchWorker(QThread):
    results_ready = pyqtSignal(list, list)

    def __init__(self, epg_parser, channels, keyword):
        super().__init__()
        self._epg_parser = epg_parser
        self._channels = channels
        self._keyword = keyword

    def run(self):
        keyword = self._keyword
        results = []
        result_channels = []
        seen = set()

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

            try:
                programs = self._epg_parser.get_channel_epg(
                    ch_name, tvg_id, tvg_name=tvg_name, comma_name=comma_name
                ) or []
            except Exception:
                continue

            for prog in programs:
                title = (prog.get('title', '') or '').lower()
                desc = (prog.get('desc', '') or '').lower()
                if keyword in title or keyword in desc:
                    key = f"{ch_name}_{prog.get('title', '')}_{prog.get('start', '')}"
                    if key not in seen:
                        seen.add(key)
                        results.append(prog)
                        result_channels.append(ch)

        results.sort(key=lambda r: r.get('start', ''))
        self.results_ready.emit(results, result_channels)


class EpgSearchDialog(FloatingDialog):
    channel_selected = pyqtSignal(dict, dict)

    def __init__(self, main_window, parent=None):
        super().__init__(parent, frameless=False, stay_on_top=False)
        self.window = main_window
        tr = main_window.language_manager.tr
        self.setWindowTitle(tr('epg_search', 'EPG搜索'))
        self.setMinimumSize(500, 400)
        self._results: List[Dict[str, Any]] = []
        self._result_channels: List[Dict[str, Any]] = []
        self._worker = None
        self._search_timer = QTimer()
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(300)
        self._search_timer.timeout.connect(self._do_search)
        self._pending_text = ''
        self._setup_ui()
        self._apply_theme()
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
            QLineEdit {{
                background-color: {c.get('player_combo', '#2a2a2a')};
                color: {c.get('window_text', '#ffffff')};
                border: 1px solid {c.get('player_line', '#555')};
                border-radius: {r}px;
                padding: 4px 8px;
                min-height: 28px;
            }}
            QListWidget {{
                background-color: transparent;
                color: {c.get('window_text', '#ffffff')};
                border: none; outline: none;
            }}
            QListWidget::item {{
                padding: 2px 4px; min-height: 26px;
                border: 1px solid transparent; border-radius: {r}px;
            }}
            QListWidget::item:selected {{
                border: 1px solid {c.get('accent', '#4a9eff')};
                background-color: {c.get('highlight', '#264f78')};
                color: {c.get('highlighted_text', '#ffffff')};
            }}
            QListWidget::item:hover {{
                border: 1px solid {c.get('player_line', '#555')};
                background-color: {c.get('highlight', '#264f78')};
            }}
        """)

    def _setup_ui(self):
        tr = self.window.language_manager.tr

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        search_row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(tr('epg_search_placeholder', '搜索节目名称/描述...'))
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._on_search_text_changed)
        search_row.addWidget(self.search_input)
        layout.addLayout(search_row)

        self.result_list = QListWidget()
        self.result_list.setSpacing(2)
        self.result_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self.result_list, 1)

        self.count_label = QLabel('')
        layout.addWidget(self.count_label)

    def _on_search_text_changed(self, text: str):
        self._search_timer.stop()
        text = text.strip().lower()
        if not text:
            self.result_list.clear()
            self._results.clear()
            self._result_channels.clear()
            self.count_label.setText('')
            return
        self._pending_text = text
        tr = self.window.language_manager.tr
        self.count_label.setText(tr('searching', '搜索中...'))
        self._search_timer.start()

    def _do_search(self):
        text = self._pending_text
        if not text:
            return

        w = self.window
        epg_parser = getattr(w, 'epg_parser', None)
        if not epg_parser:
            tr = w.language_manager.tr
            self.count_label.setText(tr('search_no_results', '无结果'))
            return

        if self._worker and self._worker.isRunning():
            self._worker.results_ready.disconnect(self._on_search_results)
            self._worker.quit()
            self._worker.wait(1000)

        channels = list(getattr(w, '_sub_channels', []))
        self._worker = _EpgSearchWorker(epg_parser, channels, text)
        self._worker.results_ready.connect(self._on_search_results)
        self._worker.start()

    def _on_search_results(self, results, result_channels):
        self._results = results
        self._result_channels = result_channels
        self.result_list.clear()

        c = AppStyles._get_colors()
        name_style = f"color: {c.get('window_text', '#ffffff')}; background-color: transparent;"
        tr = self.window.language_manager.tr

        for idx, prog in enumerate(results):
            try:
                ch = result_channels[idx]
                ch_name = ch.get('name', '')
                title = prog.get('title', '')
                start = prog.get('start', '')
                time_str = ''
                if start:
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(start)
                        time_str = dt.strftime('%H:%M')
                    except Exception:
                        pass
                display = f"{time_str} {title} ({ch_name})" if time_str else f"{title} ({ch_name})"

                item_widget = QtWidgets.QWidget()
                item_layout = QtWidgets.QHBoxLayout(item_widget)
                item_layout.setContentsMargins(5, 2, 5, 2)
                item_layout.setSpacing(8)

                name_label = QtWidgets.QLabel(display)
                name_label.setStyleSheet(name_style)
                name_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
                name_label.setWordWrap(False)
                item_layout.addWidget(name_label, 1)

                item = QListWidgetItem()
                item.setSizeHint(QSize(0, 36))
                item.setData(Qt.ItemDataRole.UserRole, idx)
                self.result_list.addItem(item)
                self.result_list.setItemWidget(item, item_widget)
            except Exception:
                pass

        count = len(results)
        self.count_label.setText(tr('search_results_count', '找到 {count} 个结果').format(count=count))

    def _on_item_double_clicked(self, item):
        idx = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(idx, int) and 0 <= idx < len(self._results):
            ch = self._result_channels[idx]
            prog = self._results[idx]
            self.channel_selected.emit(ch, prog)
            self.accept()
