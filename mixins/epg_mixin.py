from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu
from datetime import datetime

from ui.styles import AppStyles
from core.log_manager import global_logger as logger


class EpgMixin:
    """从 IPTVPlayer 提取的 EPG/节目信息职责"""

    def populate_epg_list(self):
        self.epg_ctrl.populate_epg_list()

    def on_epg_item_clicked(self, item):
        self.epg_ctrl.on_epg_item_clicked(item)

    def _on_epg_context_menu(self, pos):
        item = self.epg_content.itemAt(pos)
        if not item:
            return
        item_data = item.data(Qt.ItemDataRole.UserRole)
        if not item_data or not isinstance(item_data, dict):
            return
        program = item_data.get('program', item_data)
        tr = self.language_manager.tr
        menu = QMenu(self.epg_content)
        menu.setStyleSheet(AppStyles.common_menu_style())

        ch_name = self.current_channel.get('name', '') if self.current_channel else ''
        prog_title = program.get('title', '')
        start = program.get('start', '')
        end = program.get('end', '')

        has_reminder = self.epg_reminder_ctrl.has_reminder(ch_name, prog_title, start)
        if has_reminder:
            reminder_action = QAction(tr('epg_cancel_reminder', '取消提醒'), menu)
            reminder_action.triggered.connect(lambda: self.epg_reminder_ctrl.toggle_reminder_for_program(
                ch_name, prog_title, start, end, self.current_channel.get('tvg_id', '') if self.current_channel else ''))
        else:
            reminder_action = QAction(tr('epg_set_reminder', '设置提醒'), menu)
            reminder_action.triggered.connect(lambda: self.epg_reminder_ctrl.toggle_reminder_for_program(
                ch_name, prog_title, start, end, self.current_channel.get('tvg_id', '') if self.current_channel else ''))
        menu.addAction(reminder_action)

        try:
            start_dt = datetime.fromisoformat(start)
            end_dt = datetime.fromisoformat(end)
            now = datetime.now()
            if start_dt < now and self.current_channel and self.current_channel.get('catchup_source', ''):
                catchup_action = QAction(tr('menu_catchup', '回看'), menu)
                catchup_action.triggered.connect(lambda: self.catchup_ctrl.start_catchup(program))
                menu.addAction(catchup_action)
        except Exception:
            pass

        menu.exec(self.epg_content.mapToGlobal(pos))

    def start_catchup(self, program):
        self.catchup_ctrl.start_catchup(program)

    def add_exit_catchup_button(self):
        self.catchup_ctrl.add_exit_catchup_button()

    def exit_catchup(self):
        self.catchup_ctrl.exit_catchup()

    def _show_exit_timeshift_button(self):
        self.catchup_ctrl.show_exit_timeshift_button()

    def _get_epg_match_params(self):
        if not self.current_channel:
            return '', '', '', ''
        channel_name = self.current_channel.get("name", "")
        tvg_id = self.current_channel.get("tvg_id", "")
        all_tags = self.current_channel.get("_all_tags", {})
        tvg_name = all_tags.get("tvg-name", "")
        comma_name = ''
        raw_extinf = self.current_channel.get('_raw_extinf', '')
        if raw_extinf and ',' in raw_extinf:
            comma_name = raw_extinf.split(',', 1)[-1].strip()
            if comma_name.startswith('"') and comma_name.endswith('"'):
                comma_name = comma_name[1:-1]
        return channel_name, tvg_id, tvg_name, comma_name

    def _is_local_file(self, channel=None):
        ch = channel if channel is not None else self.current_channel
        if not isinstance(ch, dict):
            return False
        url = ch.get('url', '')
        if not url:
            return False
        if url.lower().startswith('file://'):
            return True
        if url.split('?')[0].lower().endswith(
            ('.mp4', '.mkv', '.avi', '.mov', '.flv', '.wmv', '.ts', '.webm', '.mp3', '.wav', '.flac')
        ):
            return True
        if not url.startswith(('http://', 'https://', 'rtmp://', 'rtsp://', 'rtp://', 'udp://', 'srt://', 'rist://', 'hls://', 'dash://')):
            return True
        return False

    def toggle_epg(self, checked=None):
        if self.panel_vis.is_auto_hidden:
            self._auto_restore_panels()
            return
        if checked is None:
            checked = not self.epg_panel.isVisible()
        self.epg_ctrl.toggle_epg(checked)

    def update_epg_date_display(self):
        self.epg_ctrl.update_epg_date_display()