"""
设置和文件操作处理器 - 负责配置管理、文件打开/保存等
从 pyqt_player.py 提取的独立模块
"""

import os
import re
import threading
from typing import Optional

from PyQt6 import QtCore, QtGui
from PyQt6.QtCore import Qt, QTimer, QThread, QMetaObject
from PyQt6.QtWidgets import (
    QFileDialog, QMessageBox, QComboBox, QApplication,
    QCheckBox, QSpinBox, QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QGroupBox, QListWidget, QListWidgetItem,
    QWidget, QFormLayout, QTextEdit, QFrame
)

from core.log_manager import global_logger as logger
from core.config_manager import ConfigManager
from core.subscription_manager import global_subscription_manager
from core.application_state import app_state
from ui.styles import AppStyles
from ui.floating_dialog import FloatingDialog
from ui.theme_manager import get_theme_manager
from ui.dialogs.about_dialog import AboutDialog
from services.m3u_parser import load_m3u_file


# 使用说明默认内容 —— 定义在模块级别便于维护
DEFAULT_USAGE_CONTENT = (
    '## 基本操作\n\n'
    '### 1. 打开播放列表\n'
    '- 点击"文件"菜单 → "打开播放列表"（Ctrl+O）\n'
    '- 支持 M3U、M3U8、TXT 格式\n'
    '- 也可将文件直接拖放到主窗口打开\n\n'
    '### 2. 播放频道\n'
    '- 在频道列表中**双击**频道开始播放\n'
    '- 底部控制面板：▶ 播放 / ▮▮ 暂停 / ■ 停止\n'
    '- 音量滑块调节音量，点击图标静音/取消静音\n'
    '- 倍速按钮切换播放速度，比例按钮切换画面比例\n'
    '- 全屏按钮或 F11 进入全屏\n'
    '- **↑ ↓** 键切换频道，**← →** 键调整音量\n\n'
    '### 3. EPG 电子节目单\n'
    '- 左侧面板显示当前频道节目安排\n'
    '- 点击 ◀ / ▶ 切换日期查看节目\n'
    '- 进度条实时显示当前节目播放进度\n'
    '- 支持配置 EPG 数据源自动订阅更新\n'
    '- M3U 文件头中的 EPG 地址会自动加载\n\n'
    '### 4. 扫描整理\n'
    '- 工具菜单 → 扫描整理\n'
    '- 输入 IP 范围或流地址\n'
    '- 设置超时时间和线程数，支持追加扫描和重试\n'
    '- 扫描完成后可使用**批量操作**：自动分类、清理名称、匹配台标\n\n'
    '### 5. 验证频道\n'
    '- 批量检测频道有效性，显示延迟、分辨率等参数\n'
    '- 支持智能重试失败的项\n\n'
    '## 高级功能\n\n'
    '### 订阅设置\n'
    '- 工具菜单 → 订阅设置\n'
    '- 配置多个播放列表源和 EPG 数据源\n\n'
    '### 频道映射\n'
    '- 工具菜单 → 频道映射管理器\n\n'
    '### 界面定制\n'
    '- **主题切换**：5 种主题即时切换\n'
    '- **语言切换**：中文 / English\n'
    '- E / L / M / Y 快捷键控制面板\n'
    '- Tab 切换 OSD 信息遮罩\n'
    '- F5 刷新界面，F11 全屏，Ctrl+Q 退出\n\n'
    '### 时移/回看\n'
    '- 支持多种回看类型：default / append / shift / flussonic / xc\n'
    '- 时间变量替换支持自定义格式和时区偏移\n'
)


class SettingsFileOperations:
    """设置和文件操作 - 管理配置和文件I/O"""

    def __init__(self, main_window):
        self.window = main_window

    def _tr(self, key, default=None):
        w = self.window
        if w and w.language_manager:
            return w.language_manager.tr(key, default or key)
        return default or key

    # ==================== 文件操作 ====================

    def open_playlist(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self.window,
            self._tr("open_playlist", "Open Playlist"),
            "",
            "M3U Files (*.m3u *.m3u8);;All Files (*)"
        )
        if file_path:
            self._load_playlist_file(file_path)

    def open_specific_file(self, file_path: str):
        if file_path and os.path.isfile(file_path):
            self._load_playlist_file(file_path)

    def save_as(self):
        if not self.window.channels:
            QMessageBox.warning(
                self.window,
                self._tr("warning", "Warning"),
                self._tr("no_channels_to_save", "No channels to save")
            )
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self.window,
            self._tr("save_as", "Save As"),
            "",
            "M3U Files (*.m3u);;Text Files (*.txt);;All Files (*)"
        )
        if file_path:
            self._save_playlist_file(file_path)

    def reload_subscription(self):
        if self.window.subscription_ctrl:
            self.window.subscription_ctrl.reload_subscription()

    # ==================== 设置对话框 ====================

    def player_settings(self):
        dialog = self._create_settings_dialog()
        tr = self._tr

        main_layout = QVBoxLayout(dialog)

        playback_settings = self.window.config.load_playback_settings() if self.window.config else {}

        main_layout.addWidget(self._build_protocol_section(tr, playback_settings))
        playlist_section = self._build_subscription_section(tr, 'playlist', playback=False)
        main_layout.addWidget(playlist_section['group'])
        epg_section = self._build_subscription_section(tr, 'epg', playback=False)
        main_layout.addWidget(epg_section['group'])

        self._connect_subscription_signals(playlist_section, epg_section)

        button_layout = QHBoxLayout()
        save_button = QPushButton(tr("save_button", "Save"))
        cancel_button = QPushButton(tr("cancel_button", "Cancel"))
        save_button.clicked.connect(lambda: self._save_and_close_settings(dialog))
        cancel_button.clicked.connect(dialog.close)
        button_layout.addStretch()
        button_layout.addWidget(save_button)
        button_layout.addWidget(cancel_button)
        main_layout.addLayout(button_layout)

        if self.window.subscription_ui_ctrl:
            self.window.subscription_ui_ctrl.load_subscription_sources_to_ui(
                pl_widget=playlist_section['list_widget'],
                epg_widget=epg_section['list_widget']
            )

        if self.window._center_dialog_on_screen:
            self.window._center_dialog_on_screen(dialog)

        dialog.exec()

    def _create_settings_dialog(self):
        try:
            dialog = FloatingDialog(self.window, stay_on_top=False)
        except TypeError:
            dialog = FloatingDialog(self.window)
        dialog.setWindowTitle(self._tr("subscription_settings_title", "Subscription Settings"))
        dialog.setMinimumSize(620, 620)
        dialog.setStyleSheet(AppStyles.dialog_style())
        return dialog

    def _build_protocol_section(self, tr, playback_settings):
        group = QGroupBox(tr("protocol_settings", "Protocol Settings"))
        layout = QFormLayout()

        protocol_combo = QComboBox()
        protocol_combo.addItems(["HTTP", "HTTPS", "RTSP", "RTMP", "HLS"])
        if self.window.config:
            protocol = self.window.config.get_value('Player', 'protocol', 'HTTP')
            idx = protocol_combo.findText(protocol)
            if idx >= 0:
                protocol_combo.setCurrentIndex(idx)
        layout.addRow(tr("protocol_type_colon", "Protocol Type:"), protocol_combo)

        rtsp_transport_combo = QComboBox()
        rtsp_transport_combo.setObjectName("rtsp_transport_combo")
        rtsp_transport_combo.addItems(["tcp", "udp", "lavf"])
        rtsp_value = playback_settings.get('rtsp_transport', 'tcp')
        rtsp_idx = rtsp_transport_combo.findText(rtsp_value)
        if rtsp_idx >= 0:
            rtsp_transport_combo.setCurrentIndex(rtsp_idx)
        layout.addRow(tr("rtsp_transport_colon", "RTSP Transport:"), rtsp_transport_combo)

        hwdec_check = QCheckBox(tr("hwdec_label", "Hardware Decoding"))
        hwdec_check.setObjectName("hwdec_check")
        hwdec_check.setChecked(playback_settings.get('hwdec', True))
        layout.addRow(hwdec_check)

        tls_check = QCheckBox(tr("tls_verify_label", "TLS Verify"))
        tls_check.setObjectName("tls_check")
        tls_check.setChecked(playback_settings.get('tls_verify', False))
        layout.addRow(tls_check)

        timeout_spin = QSpinBox()
        timeout_spin.setObjectName("network_timeout_spin")
        timeout_spin.setRange(0, 120)
        timeout_spin.setSuffix("s")
        timeout_spin.setValue(playback_settings.get('network_timeout_sec', 0))
        timeout_spin.setSpecialValueText(tr("auto_timeout", "Auto"))
        layout.addRow(tr("network_timeout_colon", "Network Timeout:"), timeout_spin)

        group.setLayout(layout)
        return group

    def _build_subscription_section(self, tr, source_type, playback=True):
        if source_type == 'playlist':
            title_key = "playlist_subscription"
            title_default = "Playlist Subscription"
            sources_label_key = "playlist_sources"
            sources_label_default = "Playlist Sources (click to activate):"
            list_obj_name = "__settings_playlist_list__"
            interval_obj_name = "playlist_interval_combo"
            config_section = 'PlaylistSources'
            url_placeholder_key = "enter_playlist_url"
            url_placeholder_default = "Enter playlist URL"
            widget_prefix = 'playlist_'
        else:
            title_key = "epg_subscription"
            title_default = "EPG Subscription (all sources will be merged)"
            sources_label_key = "epg_sources"
            sources_label_default = "EPG Sources:"
            list_obj_name = "__settings_epg_list__"
            interval_obj_name = "epg_interval_combo"
            config_section = 'EPGSources'
            url_placeholder_key = "enter_epg_url"
            url_placeholder_default = "Enter EPG URL"
            widget_prefix = 'epg_'

        group = QGroupBox(tr(title_key, title_default))
        layout = QVBoxLayout()

        sources_label = QLabel(tr(sources_label_key, sources_label_default))
        list_widget = QListWidget()
        list_widget.setObjectName(list_obj_name)
        list_widget.setMaximumHeight(120)

        add_btn = QPushButton(tr("add_source", "+ Add Source"))
        remove_btn = QPushButton(tr("remove_source", "- Remove Selected"))

        input_widget = QWidget()
        input_layout = QHBoxLayout(input_widget)
        input_layout.setContentsMargins(0, 0, 0, 0)

        new_url_edit = QLineEdit()
        new_url_edit.setPlaceholderText(tr(url_placeholder_key, url_placeholder_default))
        new_name_edit = QLineEdit()
        new_name_edit.setPlaceholderText(tr("enter_source_name", "Source name (optional)"))
        new_name_edit.setMaximumWidth(150)

        input_layout.addWidget(QLabel("URL:"))
        input_layout.addWidget(new_url_edit)
        input_layout.addWidget(QLabel("Name:"))
        input_layout.addWidget(new_name_edit)

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(remove_btn)
        btn_layout.addStretch()

        interval_label = QLabel(tr("update_interval_colon", "Update interval (minutes):"))
        interval_combo = QComboBox()
        interval_combo.setObjectName(interval_obj_name)
        interval_combo.addItems(["15", "30", "60", "120", "240", "480", "720"])

        if self.window.config and not playback:
            interval_value = self.window.config.get_value(config_section, 'update_interval', '60')
            idx = interval_combo.findText(interval_value)
            if idx >= 0:
                interval_combo.setCurrentIndex(idx)

        layout.addWidget(sources_label)
        layout.addWidget(list_widget)
        layout.addWidget(input_widget)
        layout.addLayout(btn_layout)
        if not playback:
            layout.addWidget(interval_label)
            layout.addWidget(interval_combo)

        group.setLayout(layout)

        self.window.__dict__[f'{widget_prefix}list_widget'] = list_widget
        self.window.__dict__[f'{widget_prefix}new_url_edit'] = new_url_edit
        self.window.__dict__[f'{widget_prefix}new_name_edit'] = new_name_edit
        self.window.__dict__[f'_{widget_prefix}add_btn'] = add_btn
        self.window.__dict__[f'_editing_{widget_prefix}index'] = -1

        return {
            'group': group,
            'list_widget': list_widget,
            'add_btn': add_btn,
            'remove_btn': remove_btn,
            'new_url_edit': new_url_edit,
            'new_name_edit': new_name_edit,
        }

    def _connect_subscription_signals(self, playlist_section, epg_section):
        ui = self.window.subscription_ui_ctrl
        if not ui:
            return

        playlist_section['add_btn'].clicked.connect(lambda: ui.add_or_update_playlist_source())
        playlist_section['remove_btn'].clicked.connect(lambda: ui.remove_selected_playlist_source())
        playlist_section['list_widget'].itemClicked.connect(lambda item: ui.activate_playlist_source(item))
        playlist_section['list_widget'].itemDoubleClicked.connect(lambda item: ui.edit_playlist_source(item))

        epg_section['add_btn'].clicked.connect(lambda: ui.add_or_update_epg_source())
        epg_section['remove_btn'].clicked.connect(lambda: ui.remove_selected_epg_source())
        epg_section['list_widget'].itemDoubleClicked.connect(lambda item: ui.edit_epg_source(item))

    # ==================== 保存与关闭 ====================

    def _save_and_close_settings(self, dialog):
        try:
            old_playlist = global_subscription_manager.get_playlist_sources()
            old_epg = global_subscription_manager.get_epg_sources()
            old_active_index = global_subscription_manager.get_active_playlist_source_index()

            new_playlist = self._extract_sources_from_ui('playlist')
            new_epg = self._extract_sources_from_ui('epg')
            new_playback = self._extract_playback_settings(dialog)

            if new_playlist:
                global_subscription_manager._config.save_playlist_sources(new_playlist)
            if new_epg:
                global_subscription_manager._config.save_epg_sources(new_epg)

            self._save_intervals(dialog)
            self._apply_playback_settings(new_playback)

            playlist_changed, new_active_index = self._check_playlist_changed(old_playlist, new_playlist, old_active_index)
            if playlist_changed:
                self._reload_playlist_async(new_playlist, new_active_index)

            if self._check_epg_changed(old_epg, new_epg):
                threading.Thread(target=global_subscription_manager.load_all_epg_data, daemon=True).start()

            dialog.close()
        except Exception as e:
            logger.error(f"保存订阅设置失败: {e}")
            dialog.close()

    def _extract_sources_from_ui(self, source_type):
        widget = getattr(self.window, f'{source_type}_list_widget', None)
        if not widget:
            return []
        sources = []
        for i in range(widget.count()):
            item = widget.item(i)
            source_data = item.data(QtCore.Qt.ItemDataRole.UserRole)
            if source_data:
                if source_type == 'playlist':
                    source_data['enabled'] = item.checkState() == QtCore.Qt.CheckState.Checked
                sources.append(source_data)
        return sources

    def _extract_playback_settings(self, dialog):
        settings = {}
        combo = dialog.findChild(QComboBox, "rtsp_transport_combo")
        if combo:
            settings['rtsp_transport'] = combo.currentText()
        check = dialog.findChild(QCheckBox, "hwdec_check")
        if check:
            settings['hwdec'] = check.isChecked()
        check = dialog.findChild(QCheckBox, "tls_check")
        if check:
            settings['tls_verify'] = check.isChecked()
        spin = dialog.findChild(QSpinBox, "network_timeout_spin")
        if spin:
            settings['network_timeout_sec'] = spin.value()
        return settings

    def _save_intervals(self, dialog):
        for prefix, section in [('playlist', 'PlaylistSources'), ('epg', 'EPGSources')]:
            combo = dialog.findChild(QComboBox, f"{prefix}_interval_combo")
            if combo and self.window.config:
                self.window.config.set_value(section, 'update_interval', combo.currentText())

    def _apply_playback_settings(self, new_playback):
        if not new_playback or not self.window.config:
            return
        old_playback = self.window.config.load_playback_settings()
        self.window.config.save_playback_settings(new_playback)

        changed = any(old_playback.get(k) != v for k, v in new_playback.items())
        if changed and self.window.player_controller:
            try:
                pc = self.window.player_controller
                if pc and hasattr(pc, '_playback_settings'):
                    pc._playback_settings.update(new_playback)
            except Exception:
                pass

    @staticmethod
    def _check_playlist_changed(old, new, old_active_index):
        if len(old) != len(new):
            return True, SettingsFileOperations._find_active_index(new)
        new_active_index = SettingsFileOperations._find_active_index(new)
        if old_active_index != new_active_index:
            return True, new_active_index
        for old_s, new_s in zip(old, new):
            if old_s.get('url') != new_s.get('url') or old_s.get('enabled') != new_s.get('enabled'):
                return True, new_active_index
        return False, old_active_index

    @staticmethod
    def _find_active_index(sources):
        for i, s in enumerate(sources):
            if s.get('enabled'):
                return i
        return 0 if sources else -1

    @staticmethod
    def _check_epg_changed(old, new):
        if len(old) != len(new):
            return True
        return any(old_s.get('url') != new_s.get('url') for old_s, new_s in zip(old, new))

    def _reload_playlist_async(self, new_sources, new_active_index):
        if new_active_index < 0 or new_active_index >= len(new_sources):
            return
        active = new_sources[new_active_index]

        def _reload_and_refresh():
            try:
                self.window._handle_playlist_subscription(True, active.get('url', ''), new_active_index)
                if QThread.currentThread() != self.window.thread():
                    QMetaObject.invokeMethod(
                        self.window, "_do_on_playlist_updated_in_main_thread",
                        Qt.ConnectionType.QueuedConnection
                    )
                else:
                    self.window._do_on_playlist_updated_in_main_thread()
            except Exception as e:
                logger.error(f"重新加载播放列表失败: {e}")

        threading.Thread(target=_reload_and_refresh, daemon=True).start()

    # ==================== 语言 / 主题 ====================

    def set_language(self, language: str):
        try:
            self.window.language_manager.set_language(language)
            ConfigManager().save_language_settings(language)

            current_version = AboutDialog.CURRENT_VERSION
            tr = self.window.language_manager.tr
            new_title = f"{tr('app_title', 'IPTV Scanner Editor Pro')} v{current_version}"
            self.window.setWindowTitle(new_title)
            if self.window._title_label:
                self.window._title_label.setText(new_title)

            if hasattr(self.window, 'setup_menu_bar'):
                self.window.setup_menu_bar()

            self.window.language_manager.update_ui_texts(self.window)

            if hasattr(self.window, 'status_bar_show_message'):
                self.window.status_bar_show_message(tr("language_changed", "Language changed"))
        except Exception as e:
            logger.error(f"切换语言失败: {e}")
            if hasattr(self.window, 'status_bar_show_message'):
                fallback = getattr(self.window.language_manager, 'tr', lambda x, y: x) if self.window.language_manager else lambda x, y: x
                self.window.status_bar_show_message(fallback("language_change_failed", "Failed"))

    def set_theme(self, theme: str):
        get_theme_manager().set_theme(theme)
        w = self.window

        w.setStyleSheet(AppStyles.main_window_style())

        for attr, style_func in [
            ('_title_bar', AppStyles.title_bar_style),
            ('_title_label', AppStyles.title_label_style),
            ('_custom_menu_bar', AppStyles.player_menu_bar_style),
            ('central_widget', AppStyles.player_background_style),
            ('video_frame', AppStyles.player_background_style),
            ('video_placeholder', AppStyles.player_video_placeholder_style),
            ('status_bar', AppStyles.statusbar_style),
            ('toolbar', AppStyles.player_toolbar_style),
        ]:
            widget = getattr(w, attr, None)
            if widget:
                widget.setStyleSheet(style_func())

        for dock_attr in ['epg_dock', 'playlist_dock', 'floating_dock']:
            panel = getattr(w, dock_attr, None)
            if panel:
                container = panel.widget()
                if container and hasattr(container, 'setStyleSheet'):
                    container.setStyleSheet(AppStyles.player_panel_style())
                panel.update()

        if hasattr(w, '_reapply_floating_panel_styles'):
            w._reapply_floating_panel_styles()
        if hasattr(w, '_reapply_side_panel_styles'):
            w._reapply_side_panel_styles()

        w.update()
        QApplication.processEvents()

    # ==================== 关于 / 使用说明 ====================

    def show_about(self):
        AboutDialog(self.window).exec()

    def show_usage_instructions(self):
        dialog = FloatingDialog(self.window, stay_on_top=False)
        tr = self._tr
        colors = AppStyles._get_colors()

        dialog.setWindowTitle(tr("usage_instructions_title", "Usage Instructions"))
        dialog.setMinimumSize(560, 520)
        dialog.setStyleSheet(AppStyles.dialog_style())

        main_layout = QVBoxLayout(dialog)
        main_layout.setContentsMargins(24, 20, 24, 16)
        main_layout.setSpacing(12)

        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)
        header_icon = QLabel("📖")
        header_icon.setStyleSheet("font-size: 28px; background-color: transparent;")
        header_icon.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        header_layout.addWidget(header_icon)
        header_title = QLabel(tr("usage_instructions_title", "Usage Instructions"))
        header_title.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {colors['accent']}; background-color: transparent;")
        header_title.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        header_layout.addWidget(header_title)
        header_layout.addStretch()
        main_layout.addLayout(header_layout)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background-color: {colors['mid']}; max-height: 1px;")
        main_layout.addWidget(sep)

        text_edit = QTextEdit()
        usage_content = tr("usage_content", "") or DEFAULT_USAGE_CONTENT
        text_edit.setHtml(self._convert_markdown_to_html(usage_content))
        text_edit.setReadOnly(True)
        text_edit.setFont(QtGui.QFont('Microsoft YaHei', 10))
        text_edit.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        text_edit.setWordWrapMode(QtGui.QTextOption.WrapMode.WordWrap)
        text_edit.setStyleSheet(f"""
            QTextEdit {{
                background-color: {colors['alternate_base']};
                color: {colors['window_text']};
                border: 1px solid {colors['mid']};
                border-radius: 8px;
                padding: 12px;
                font-size: 13px;
            }}
        """)
        main_layout.addWidget(text_edit)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        close_btn = QPushButton(tr("close_button", "Close"))
        close_btn.setFixedSize(72, 28)
        close_btn.setStyleSheet(AppStyles.button_style())
        close_btn.clicked.connect(dialog.accept)
        button_layout.addWidget(close_btn)
        main_layout.addLayout(button_layout)

        if self.window._center_dialog_on_screen:
            self.window._center_dialog_on_screen(dialog)

        dialog.exec()

    @staticmethod
    def _convert_markdown_to_html(markdown):
        colors = AppStyles._get_colors()
        html = markdown
        html = re.sub(r'### (.*)', rf'<h3 style="color: {colors["window_text"]}; margin-top: 8px; margin-bottom: 4px; font-size: 13px;">\1</h3>', html)
        html = re.sub(r'## (.*)', rf'<h2 style="color: {colors["accent"]}; margin-top: 12px; margin-bottom: 6px; font-size: 15px;">\1</h2>', html)
        html = re.sub(r'\*\*(.*?)\*\*', rf'<strong style="color: {colors["window_text"]};">\1</strong>', html)
        html = re.sub(r'^1\. (.*)', r'<p style="margin: 3px 0; line-height: 1.4;">1. \1</p>', html, flags=re.MULTILINE)
        html = re.sub(r'^- (.*)', r'<p style="margin: 2px 0 2px 16px; line-height: 1.4;">• \1</p>', html, flags=re.MULTILINE)
        html = html.replace('\n\n', '<br>')
        html = html.replace('\n', ' ')
        return f'''<html>
        <head>
            <style>
                body {{
                    font-family: 'Microsoft YaHei', 'Segoe UI', sans-serif;
                    font-size: 13px;
                    line-height: 1.5;
                    color: {colors['window_text']};
                    background-color: transparent;
                    margin: 0;
                    padding: 0;
                }}
                p {{ margin: 3px 0; }}
            </style>
        </head>
        <body>
            {html}
        </body>
        </html>'''

    # ==================== 窗口布局 ====================

    def save_window_layout(self):
        config = self.window.config or self.window.config_manager
        if not config:
            logger.warning("无法保存窗口布局：未找到配置管理器")
            return

        geometry = self.window.geometry()

        floating_settings = {
            'epg_visible': self.window.epg_visible,
            'playlist_visible': self.window.playlist_visible,
            'floating_visible': self.window.floating_panel_visible,
        }

        if self.window.epg_dock:
            floating_settings['epg_width'] = self.window.epg_dock.width()
        if self.window.playlist_dock:
            floating_settings['playlist_width'] = self.window.playlist_dock.width()
        if self.window.floating_dock:
            floating_settings['floating_width'] = self.window.floating_dock.width()

        config.save_window_layout(
            x=geometry.x(), y=geometry.y(),
            width=geometry.width(), height=geometry.height(),
            dividers=[]
        )
        config.save_ui_settings(floating_settings)

    # ==================== 内部文件 I/O ====================

    def _load_playlist_file(self, file_path: str):
        tr = self._tr
        try:
            content = load_m3u_file(file_path)

            if self.window.channel_model and self.window.channel_model.load_from_file(content):
                channels = self.window.channel_model.channels
            else:
                channels = []

            self.window.channels = channels
            self.window._local_channels = list(channels)
            app_state.replace_channels(channels)

            if self.window.channel_model:
                epg_url = getattr(self.window.channel_model, '_last_header_attrs', {}).get('epg_url', '')
                if epg_url and not global_subscription_manager.get_epg_sources():
                    logger.info(f"本地文件头发现EPG地址，自动加载: {epg_url[:80]}")
                    try:
                        global_subscription_manager.load_single_epg(epg_url)
                        if self.window._populate_epg_list:
                            QTimer.singleShot(500, self.window._populate_epg_list)
                    except Exception as epg_err:
                        logger.warning(f"从本地文件头加载EPG失败: {epg_err}")

            if self.window.playlist_tab:
                self.window.playlist_tab.setCurrentIndex(1)

            if hasattr(self.window, 'populate_channel_list'):
                self.window.populate_channel_list(source='local')

            logger.info(f"成功加载播放列表: {file_path}, 共 {len(channels)} 个频道")
        except Exception as e:
            logger.error(f"加载播放列表失败: {e}")
            QMessageBox.critical(
                self.window,
                tr("error", "Error"),
                tr("open_file_error", "Failed to load playlist:\n{error}").format(error=str(e))
            )

    def _save_playlist_file(self, file_path: str):
        tr = self._tr
        try:
            channels = self.window.channels
            if file_path.endswith('.m3u') or file_path.endswith('.m3u8'):
                self._save_as_m3u(channels, file_path)
            elif file_path.endswith('.txt'):
                self._save_as_txt(channels, file_path)
            else:
                self._save_as_m3u(channels, file_path)
            logger.info(f"成功保存播放列表: {file_path}")
        except Exception as e:
            QMessageBox.critical(
                self.window,
                tr("error", "Error"),
                tr("save_error", "Failed to save playlist:\n{error}").format(error=str(e))
            )

    @staticmethod
    def _save_as_m3u(channels: list, file_path: str):
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write('#EXTM3U\n')
            for ch in channels:
                name = ch.get('name', '')
                url = ch.get('url', '')
                group = ch.get('group', '')
                logo = ch.get('logo_url', '')
                tags = ch.get('_all_tags', {}) or {}
                tvg_id = ch.get('tvg_id', '')
                tvg_name = tags.get('tvg-name', '')
                tvg_chno = tags.get('tvg-chno', '')
                tvg_shift = tags.get('tvg-shift', '')
                catchup = tags.get('catchup', '')
                catchup_days = tags.get('catchup-days', '')
                catchup_source = ch.get('catchup_source', '')
                catchup_correction = tags.get('catchup-correction', '')
                groups = ch.get('_groups', [])

                attrs = ['#EXTINF:-1']
                if tvg_id:
                    attrs.append(f'tvg-id="{tvg_id}"')
                if tvg_name:
                    attrs.append(f'tvg-name="{tvg_name}"')
                elif name:
                    attrs.append(f'tvg-name="{name}"')
                if logo:
                    attrs.append(f'tvg-logo="{logo}"')
                if tvg_chno:
                    attrs.append(f'tvg-chno="{tvg_chno}"')
                if tvg_shift:
                    attrs.append(f'tvg-shift="{tvg_shift}"')
                if group:
                    group_value = ';'.join(groups) if groups and len(groups) > 1 else group
                    attrs.append(f'group-title="{group_value}"')
                if catchup:
                    attrs.append(f'catchup="{catchup}"')
                if catchup_days:
                    attrs.append(f'catchup-days="{catchup_days}"')
                if catchup_source:
                    attrs.append(f'catchup-source="{catchup_source}"')
                if catchup_correction:
                    attrs.append(f'catchup-correction="{catchup_correction}"')

                f.write(' '.join(attrs) + f',{name}\n')
                f.write(f'{url}\n')

    @staticmethod
    def _save_as_txt(channels: list, file_path: str):
        with open(file_path, 'w', encoding='utf-8') as f:
            for ch in channels:
                f.write(f"{ch.get('name', '')},{ch.get('url', '')}\n")