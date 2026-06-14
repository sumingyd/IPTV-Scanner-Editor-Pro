from typing import Dict, Any, List
from PySide6.QtWidgets import (QVBoxLayout, QHBoxLayout, QLineEdit,
                              QListWidget, QListWidgetItem, QLabel)
from PySide6.QtCore import Qt, QSize, Signal, QThread, QTimer
from PySide6 import QtWidgets
from ui.styles import AppStyles
from ui.floating_dialog import FloatingDialog
from core.log_manager import global_logger as logger


class _EpgSearchWorker(QThread):
    results_ready = Signal(list, list)
    MAX_RESULTS = 200

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

        ch_map = {}
        for ch in self._channels:
            name = ch.get('name', '')
            if name and name not in ch_map:
                ch_map[name] = ch
            tvg_id = ch.get('tvg_id', '')
            if tvg_id and tvg_id not in ch_map:
                ch_map[tvg_id] = ch

        epg_data = self._epg_parser.get_epg_data_copy() if hasattr(self._epg_parser, 'get_epg_data_copy') else getattr(self._epg_parser, '_epg_data', None)
        if not epg_data or not isinstance(epg_data, dict):
            self.results_ready.emit(results, result_channels)
            return

        for epg_id, programs in epg_data.items():
            if not isinstance(programs, list):
                continue
            ch = ch_map.get(epg_id)
            for prog in programs:
                title = (prog.get('title', '') or '').lower()
                if keyword in title:
                    key = f"{epg_id}_{prog.get('title', '')}_{prog.get('start', '')}"
                    if key not in seen:
                        seen.add(key)
                        results.append(prog)
                        result_channels.append(ch if ch else {'name': epg_id})
                        if len(results) >= self.MAX_RESULTS:
                            break
            if len(results) >= self.MAX_RESULTS:
                break

        results.sort(key=lambda r: r.get('start', ''))
        self.results_ready.emit(results, result_channels)


class EpgSearchDialog(FloatingDialog):
    channel_selected = Signal(dict, dict)

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
        list_r = AppStyles._get_scaled_radius('list_item')
        self.setStyleSheet(AppStyles.popup_dialog_style() + f"""
            QListWidget {{
                background-color: transparent;
                color: {c.get('window_text', '#ffffff')};
                border: none; outline: none;
            }}
            QListWidget::item {{
                padding: 2px 4px; min-height: 26px;
                border: 1px solid transparent; border-radius: {list_r}px;
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
            self._worker.requestInterruption()
            self._worker.wait(500)

        channels = list(getattr(w, '_sub_channels', [])) + list(getattr(w, '_local_channels', []))
        self._worker = _EpgSearchWorker(epg_parser, channels, text)
        self._worker.results_ready.connect(self._on_search_results)
        self._worker.start()

    def _on_search_results(self, results, result_channels):
        self._results = results
        self._result_channels = result_channels
        self.result_list.clear()

        tr = self.window.language_manager.tr

        for idx, prog in enumerate(results):
            try:
                ch = result_channels[idx]
                ch_name = ch.get('name', '')
                title = prog.get('title', '')
                desc = prog.get('desc', '')
                start = prog.get('start', '')
                time_str = ''
                if start:
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(start)
                        time_str = dt.strftime('%H:%M')
                    except Exception:
                        pass
                parts = []
                if time_str:
                    parts.append(time_str)
                parts.append(title)
                if ch_name:
                    parts.append(f'({ch_name})')
                display = ' '.join(parts)


                item = QListWidgetItem(display)
                item.setData(Qt.ItemDataRole.UserRole, idx)
                self.result_list.addItem(item)
            except Exception:
                pass

        is_truncated = len(results) >= _EpgSearchWorker.MAX_RESULTS
        count = len(results)
        if is_truncated:
            self.count_label.setText(tr('search_results_truncated', '找到 {count}+ 个结果（已截断）').format(count=count))
        else:
            self.count_label.setText(tr('search_results_count', '找到 {count} 个结果').format(count=count))

    def _on_item_double_clicked(self, item):
        idx = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(idx, int) and 0 <= idx < len(self._results):
            ch = self._result_channels[idx]
            prog = self._results[idx]
            self.channel_selected.emit(ch, prog)
            self.accept()
