from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu
from PySide6.QtWidgets import QApplication
from datetime import datetime

from ui.styles import AppStyles


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

        # 回看（已结束的节目且频道支持回看）
        try:
            start_dt = datetime.fromisoformat(start)
            end_dt = datetime.fromisoformat(end)
            now = datetime.now()
            supports_catchup = bool(self.current_channel and (
                self.current_channel.get('catchup_source', '')
                or self.current_channel.get('catchup', '')
            ))
            if not supports_catchup and self.current_channel:
                from services.m3u_parser import safe_detect_catchup_source
                if safe_detect_catchup_source(self.current_channel.get('url', '')):
                    supports_catchup = True
            if end_dt < now and self.current_channel and supports_catchup:
                catchup_action = QAction(tr('menu_catchup', '回看'), menu)
                catchup_action.triggered.connect(lambda: self.catchup_ctrl.start_catchup(program))
                menu.addAction(catchup_action)
                menu.addSeparator()
        except Exception:
            pass

        # 提醒
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

        menu.addSeparator()

        # 复制节目信息
        copy_title_action = QAction(tr('epg_copy_title', '复制节目标题'), menu)
        copy_title_action.triggered.connect(lambda: self._epg_copy_text(prog_title))
        menu.addAction(copy_title_action)

        # 复制完整节目信息（频道 + 时间 + 标题）
        try:
            start_dt2 = datetime.fromisoformat(start) if start else None
            end_dt2 = datetime.fromisoformat(end) if end else None
            time_str = ''
            if start_dt2 and end_dt2:
                time_str = f"{start_dt2.strftime('%Y-%m-%d %H:%M')} - {end_dt2.strftime('%H:%M')}"
            elif start_dt2:
                time_str = start_dt2.strftime('%Y-%m-%d %H:%M')
            full_info = f"{ch_name}  {time_str}\n{prog_title}"
            if program.get('desc'):
                full_info += f"\n{program.get('desc', '')}"
            copy_info_action = QAction(tr('epg_copy_info', '复制节目信息'), menu)
            copy_info_action.triggered.connect(lambda: self._epg_copy_text(full_info))
            menu.addAction(copy_info_action)
        except Exception:
            pass

        menu.addSeparator()

        # 跳转到此节目所在频道
        if ch_name and self.current_channel:
            goto_ch_action = QAction(tr('epg_goto_channel', '定位到正在播放的频道'), menu)
            goto_ch_action.triggered.connect(lambda: self._epg_goto_current_channel())
            menu.addAction(goto_ch_action)

        menu.exec(self.epg_content.mapToGlobal(pos))

    def _epg_copy_text(self, text):
        if not text:
            return
        QApplication.clipboard().setText(text)
        tr = self.language_manager.tr
        self.status_bar_show_message(tr('copied_to_clipboard', '已复制到剪贴板'))

    def _epg_goto_current_channel(self):
        """在播放列表中定位并选中当前频道"""
        if not self.current_channel:
            return
        ch_name = self.current_channel.get('name', '')
        if not ch_name:
            return
        # 在订阅和本地列表中搜索
        for list_widget, channels in [
            (self.sub_channel_list, getattr(self, '_sub_channels', [])),
            (self.local_channel_list, getattr(self, '_local_channels', [])),
        ]:
            if not list_widget or not channels:
                continue
            for i in range(list_widget.count()):
                lw_item = list_widget.item(i)
                if not lw_item:
                    continue
                idx = lw_item.data(Qt.ItemDataRole.UserRole)
                if isinstance(idx, int) and 0 <= idx < len(channels):
                    if channels[idx].get('name', '') == ch_name:
                        list_widget.setCurrentRow(i)
                        list_widget.scrollToItem(lw_item)
                        return

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