from typing import Dict, Any, List
from PyQt6.QtWidgets import (QVBoxLayout, QHBoxLayout, QListWidget,
                              QListWidgetItem, QLabel, QPushButton)
from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6 import QtWidgets
from ui.styles import AppStyles
from ui.floating_dialog import FloatingDialog
from core.log_manager import global_logger as logger


class ReminderManagerDialog(FloatingDialog):
    reminder_removed = pyqtSignal(str)

    def __init__(self, main_window, parent=None):
        super().__init__(parent, frameless=False, stay_on_top=False)
        self.window = main_window
        tr = main_window.language_manager.tr
        self.setWindowTitle(tr('reminder_manager', '提醒管理'))
        self.setMinimumSize(500, 400)
        self._setup_ui()
        self._apply_theme()
        self._load_reminders()
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
                background-color: {c.get('panel', c.get('window', '#1e1e1e'))};
                color: {c.get('window_text', '#ffffff')};
            }}
            QLabel {{
                color: {c.get('window_text', '#ffffff')};
                background-color: transparent;
            }}
            QListWidget {{
                background-color: transparent;
                color: {c.get('window_text', '#ffffff')};
                border: none; outline: none;
            }}
            QListWidget::item {{
                padding: 4px 6px; min-height: 30px;
                border: 1px solid transparent; border-radius: {r}px;
            }}
            QListWidget::item:selected {{
                border: 1px solid {c.get('accent', '#4a9eff')};
                background-color: {c.get('highlight', '#264f78')};
            }}
            QPushButton {{
                background-color: {c.get('player_button', '#3a3a3a')};
                color: {c.get('window_text', '#ffffff')};
                border: 1px solid {c.get('player_line', '#555')};
                border-radius: {r}px;
                padding: 4px 12px; min-height: 24px;
            }}
            QPushButton:hover {{
                background-color: {c.get('accent', '#4a9eff')};
            }}
        """)

    def _setup_ui(self):
        tr = self.window.language_manager.tr
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self.info_label = QLabel(tr('reminder_info', '提醒基于具体频道+节目+开始时间，节目开始前60秒触发通知'))
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)

        self.reminder_list = QListWidget()
        self.reminder_list.setSpacing(2)
        layout.addWidget(self.reminder_list, 1)

        btn_row = QHBoxLayout()
        self.remove_btn = QPushButton(tr('remove_selected', '删除选中'))
        self.remove_btn.clicked.connect(self._on_remove_selected)
        btn_row.addWidget(self.remove_btn)

        self.clear_btn = QPushButton(tr('clear_all', '清空全部'))
        self.clear_btn.clicked.connect(self._on_clear_all)
        btn_row.addWidget(self.clear_btn)

        btn_row.addStretch(1)
        layout.addLayout(btn_row)

    def _load_reminders(self):
        self.reminder_list.clear()
        ctrl = getattr(self.window, 'epg_reminder_ctrl', None)
        if not ctrl or not ctrl.service:
            return

        c = AppStyles._get_colors()
        name_style = f"color: {c.get('window_text', '#ffffff')}; background-color: transparent;"
        time_style = f"color: {c.get('player_panel_secondary', c.get('window_text', '#aaaaaa'))}; background-color: transparent;"

        reminders = ctrl.get_reminders()
        for idx, reminder in enumerate(reminders):
            try:
                ch_name = reminder.get('channel_name', '')
                title = reminder.get('program_title', '')
                start = reminder.get('start_time', '')
                time_str = ''
                if start:
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(start)
                        time_str = dt.strftime('%Y-%m-%d %H:%M')
                    except Exception:
                        time_str = start

                item_widget = QtWidgets.QWidget()
                item_layout = QtWidgets.QHBoxLayout(item_widget)
                item_layout.setContentsMargins(5, 2, 5, 2)
                item_layout.setSpacing(8)

                name_label = QtWidgets.QLabel(f"{ch_name} - {title}")
                name_label.setStyleSheet(name_style)
                name_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)

                time_label = QtWidgets.QLabel(time_str)
                time_label.setStyleSheet(time_style)
                time_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)

                item_layout.addWidget(name_label, 1)
                item_layout.addWidget(time_label)

                item = QListWidgetItem()
                item.setSizeHint(QSize(0, 40))
                item.setData(Qt.ItemDataRole.UserRole, idx)
                self.reminder_list.addItem(item)
                self.reminder_list.setItemWidget(item, item_widget)
            except Exception:
                pass

        tr = self.window.language_manager.tr
        self.info_label.setText(
            tr('reminder_count_info', '共 {count} 个提醒 | 提醒基于具体频道+节目+开始时间，节目开始前60秒触发通知')
            .format(count=len(reminders))
        )

    def _on_remove_selected(self):
        item = self.reminder_list.currentItem()
        if not item:
            return
        idx = item.data(Qt.ItemDataRole.UserRole)
        ctrl = getattr(self.window, 'epg_reminder_ctrl', None)
        if not ctrl or not ctrl.service:
            return
        reminders = ctrl.get_reminders()
        if isinstance(idx, int) and 0 <= idx < len(reminders):
            reminder_id = reminders[idx].get('id', '')
            ctrl.remove_reminder(reminder_id)
            self.reminder_removed.emit(reminder_id)
            self._load_reminders()

    def _on_clear_all(self):
        ctrl = getattr(self.window, 'epg_reminder_ctrl', None)
        if not ctrl or not ctrl.service:
            return
        reminders = ctrl.get_reminders()
        for r in reminders:
            ctrl.remove_reminder(r.get('id', ''))
        self._load_reminders()