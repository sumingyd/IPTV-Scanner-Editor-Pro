from typing import Dict, Any, List, Optional
from PyQt6.QtCore import QTimer
from core.log_manager import global_logger as logger
from controllers.main_window_protocol import MainWindowProtocol


class EpgReminderController:
    def __init__(self, main_window: MainWindowProtocol):
        self.window: MainWindowProtocol = main_window
        self._service = None

    def init_service(self, config_manager):
        from services.epg_reminder_service import EpgReminderService
        self._service = EpgReminderService(config_manager)
        self._service.set_callback(self._on_reminder_triggered)
        self._service.start_check_timer()

    @property
    def service(self):
        return self._service

    def add_reminder(self, channel_name: str, program_title: str,
                     start_time: str, end_time: str,
                     tvg_id: str = '', auto_switch: bool = False) -> bool:
        if not self._service:
            return False
        return self._service.add_reminder(channel_name, program_title, start_time, end_time, tvg_id, auto_switch)

    def remove_reminder(self, reminder_id: str):
        if self._service:
            self._service.remove_reminder(reminder_id)

    def has_reminder(self, channel_name: str, program_title: str, start_time: str) -> bool:
        if not self._service:
            return False
        return self._service.has_reminder(channel_name, program_title, start_time)

    def get_reminders(self) -> List[Dict[str, Any]]:
        if self._service:
            return self._service.get_reminders()
        return []

    def _on_reminder_triggered(self, reminder: Dict[str, Any]):
        w = self.window
        tr = w.language_manager.tr
        channel_name = reminder.get('channel_name', '')
        program_title = reminder.get('program_title', '')
        auto_switch = reminder.get('auto_switch', False)

        if auto_switch:
            self._switch_to_channel(channel_name, reminder.get('tvg_id', ''))
            msg = tr('reminder_auto_switch', '提醒: 即将开播 {title}，已自动切换到 {channel}')
            w.status_bar_show_message(msg.format(title=program_title, channel=channel_name))
        else:
            msg = tr('reminder_notify', '提醒: {channel} 即将开播 {title}')
            w.status_bar_show_message(msg.format(channel=channel_name, title=program_title))
            self._show_reminder_notification(channel_name, program_title)

    def _switch_to_channel(self, channel_name: str, tvg_id: str = ''):
        w = self.window
        channels = getattr(w, '_sub_channels', []) + getattr(w, '_local_channels', [])
        for ch in channels:
            if ch.get('name', '') == channel_name or (tvg_id and ch.get('tvg_id', '') == tvg_id):
                w.current_channel = ch
                w.update_channel_info_on_selection()
                w.play_channel(ch)
                return

    def _show_reminder_notification(self, channel_name: str, program_title: str):
        from PyQt6.QtWidgets import QSystemTrayIcon
        w = self.window
        try:
            tray = getattr(w, '_system_tray', None)
            if tray and tray.isSystemTrayAvailable():
                tr = w.language_manager.tr
                msg = tr('reminder_tray_msg', '{channel}: {title} 即将开播')
                tray.showMessage(
                    tr('reminder_tray_title', 'EPG节目提醒'),
                    msg.format(channel=channel_name, title=program_title),
                    QSystemTrayIcon.MessageIcon.Information,
                    5000
                )
        except Exception as e:
            logger.debug(f"系统托盘通知失败: {e}")

    def toggle_reminder_for_program(self, channel_name: str, program_title: str,
                                     start_time: str, end_time: str,
                                     tvg_id: str = ''):
        if not self._service:
            return
        if self.has_reminder(channel_name, program_title, start_time):
            reminder_id = f"{channel_name}_{program_title}_{start_time}"
            self._service.remove_reminder(reminder_id)
            tr = self.window.language_manager.tr
            self.window.status_bar_show_message(tr('reminder_removed', '已取消提醒'))
        else:
            self.add_reminder(channel_name, program_title, start_time, end_time, tvg_id)
            tr = self.window.language_manager.tr
            self.window.status_bar_show_message(tr('reminder_added', '已设置提醒'))