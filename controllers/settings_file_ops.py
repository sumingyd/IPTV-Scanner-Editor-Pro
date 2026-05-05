"""
设置和文件操作处理器 - 负责配置管理、文件打开/保存等
从 pyqt_player.py 提取的独立模块
"""

import os
from typing import Optional
import threading
from PyQt6.QtWidgets import (QFileDialog, QMessageBox, QComboBox, QApplication,
                             QCheckBox, QSpinBox)


class SettingsFileOperations:
    """设置和文件操作 - 管理配置和文件I/O"""

    def __init__(self, main_window):
        self.window = main_window

    def open_playlist(self):
        """打开播放列表文件"""
        tr = self.window.language_manager.tr if hasattr(self.window, 'language_manager') else lambda k, d=None: d or k
        file_path, _ = QFileDialog.getOpenFileName(
            self.window,
            tr("open_playlist", "Open Playlist"),
            "",
            "M3U Files (*.m3u *.m3u8);;All Files (*)"
        )

        if file_path:
            self._load_playlist_file(file_path)

    def open_specific_file(self, file_path: str):
        """打开指定路径的播放列表文件（用于命令行参数或右键打开方式）"""
        if file_path and os.path.isfile(file_path):
            self._load_playlist_file(file_path)

    def save_as(self):
        """另存为"""
        tr = self.window.language_manager.tr if hasattr(self.window, 'language_manager') else lambda k, d=None: d or k
        if not hasattr(self.window, 'channels') or not self.window.channels:
            QMessageBox.warning(
                self.window,
                tr("warning", "Warning"),
                tr("no_channels_to_save", "No channels to save")
            )
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self.window,
            tr("save_as", "Save As"),
            "",
            "M3U Files (*.m3u);;Text Files (*.txt);;All Files (*)"
        )

        if file_path:
            self._save_playlist_file(file_path)

    def player_settings(self):
        """显示播放器设置对话框"""
        from core.log_manager import global_logger as logger
        from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                                     QPushButton, QLineEdit, QGroupBox,
                                     QListWidget, QListWidgetItem, QWidget, QFormLayout)

        try:
            FloatingDialog = __import__('ui.floating_dialog', fromlist=['FloatingDialog']).FloatingDialog
            AppStyles = __import__('ui.styles', fromlist=['AppStyles']).AppStyles

            try:
                dialog = FloatingDialog(self.window, stay_on_top=False)
            except TypeError:
                dialog = FloatingDialog(self.window)
        except ImportError:
            from PyQt6.QtWidgets import QDialog as FloatingDialog
            AppStyles = None
            dialog = FloatingDialog(self.window)
        tr = self.window.language_manager.tr if hasattr(self.window, 'language_manager') else lambda x, y: x
        dialog.setWindowTitle(tr("subscription_settings_title", "Subscription Settings"))
        dialog.setMinimumSize(620, 620)
        if AppStyles:
            dialog.setStyleSheet(AppStyles.dialog_style())

        main_layout = QVBoxLayout(dialog)

        playback_settings = {}
        if hasattr(self.window, 'config'):
            try:
                playback_settings = self.window.config.load_playback_settings()
            except Exception:
                pass

        protocol_group = QGroupBox(tr("protocol_settings", "Protocol Settings"))
        protocol_layout = QFormLayout()

        protocol_combo = QComboBox()
        protocol_combo.addItems(["HTTP", "HTTPS", "RTSP", "RTMP", "HLS"])
        if hasattr(self.window, 'config'):
            protocol = self.window.config.get_value('Player', 'protocol', 'HTTP')
            index = protocol_combo.findText(protocol)
            if index >= 0:
                protocol_combo.setCurrentIndex(index)
        protocol_layout.addRow(tr("protocol_type_colon", "Protocol Type:"), protocol_combo)

        rtsp_transport_combo = QComboBox()
        rtsp_transport_combo.setObjectName("rtsp_transport_combo")
        rtsp_transport_combo.addItems(["tcp", "udp", "lavf"])
        rtsp_transport_value = playback_settings.get('rtsp_transport', 'tcp')
        rtsp_idx = rtsp_transport_combo.findText(rtsp_transport_value)
        if rtsp_idx >= 0:
            rtsp_transport_combo.setCurrentIndex(rtsp_idx)
        protocol_layout.addRow(tr("rtsp_transport_colon", "RTSP Transport:"), rtsp_transport_combo)

        hwdec_check = QCheckBox(tr("hwdec_label", "Hardware Decoding"))
        hwdec_check.setObjectName("hwdec_check")
        hwdec_check.setChecked(playback_settings.get('hwdec', True))
        protocol_layout.addRow(hwdec_check)

        tls_check = QCheckBox(tr("tls_verify_label", "TLS Verify"))
        tls_check.setObjectName("tls_check")
        tls_check.setChecked(playback_settings.get('tls_verify', False))
        protocol_layout.addRow(tls_check)

        network_timeout_spin = QSpinBox()
        network_timeout_spin.setObjectName("network_timeout_spin")
        network_timeout_spin.setRange(0, 120)
        network_timeout_spin.setSuffix("s")
        network_timeout_spin.setValue(playback_settings.get('network_timeout_sec', 0))
        network_timeout_spin.setSpecialValueText(tr("auto_timeout", "Auto"))
        protocol_layout.addRow(tr("network_timeout_colon", "Network Timeout:"), network_timeout_spin)

        protocol_group.setLayout(protocol_layout)
        main_layout.addWidget(protocol_group)

        playlist_group = QGroupBox(tr("playlist_subscription", "Playlist Subscription"))
        playlist_layout = QVBoxLayout()

        playlist_sources_label = QLabel(tr("playlist_sources", "Playlist Sources (click to activate):"))
        playlist_list_widget = QListWidget()
        playlist_list_widget.setObjectName("__settings_playlist_list__")
        playlist_list_widget.setMaximumHeight(120)

        playlist_add_btn = QPushButton(tr("add_source", "+ Add Source"))
        playlist_remove_btn = QPushButton(tr("remove_source", "- Remove Selected"))

        playlist_input_widget = QWidget()
        playlist_input_layout = QHBoxLayout(playlist_input_widget)
        playlist_input_layout.setContentsMargins(0, 0, 0, 0)

        playlist_new_url_edit = QLineEdit()
        playlist_new_url_edit.setPlaceholderText(tr("enter_playlist_url", "Enter playlist URL"))
        playlist_new_name_edit = QLineEdit()
        playlist_new_name_edit.setPlaceholderText(tr("enter_source_name", "Source name (optional)"))
        playlist_new_name_edit.setMaximumWidth(150)

        playlist_input_layout.addWidget(QLabel("URL:"))
        playlist_input_layout.addWidget(playlist_new_url_edit)
        playlist_input_layout.addWidget(QLabel("Name:"))
        playlist_input_layout.addWidget(playlist_new_name_edit)

        playlist_btn_layout = QHBoxLayout()
        playlist_btn_layout.addWidget(playlist_add_btn)
        playlist_btn_layout.addWidget(playlist_remove_btn)
        playlist_btn_layout.addStretch()

        playlist_interval_label = QLabel(tr("update_interval_colon", "Update interval (minutes):"))
        playlist_interval_combo = QComboBox()
        playlist_interval_combo.setObjectName("playlist_interval_combo")
        playlist_interval_combo.addItems(["15", "30", "60", "120", "240", "480", "720"])

        if hasattr(self.window, 'config'):
            playlist_interval_value = self.window.config.get_value('PlaylistSources', 'update_interval', '60')
            index = playlist_interval_combo.findText(playlist_interval_value)
            if index >= 0:
                playlist_interval_combo.setCurrentIndex(index)

        playlist_layout.addWidget(playlist_sources_label)
        playlist_layout.addWidget(playlist_list_widget)
        playlist_layout.addWidget(playlist_input_widget)
        playlist_layout.addLayout(playlist_btn_layout)
        playlist_layout.addWidget(playlist_interval_label)
        playlist_layout.addWidget(playlist_interval_combo)
        playlist_group.setLayout(playlist_layout)
        main_layout.addWidget(playlist_group)

        epg_group = QGroupBox(tr("epg_subscription", "EPG Subscription (all sources will be merged)"))
        epg_layout = QVBoxLayout()

        epg_sources_label = QLabel(tr("epg_sources", "EPG Sources:"))
        epg_list_widget = QListWidget()
        epg_list_widget.setObjectName("__settings_epg_list__")
        epg_list_widget.setMaximumHeight(120)

        epg_add_btn = QPushButton(tr("add_source", "+ Add Source"))
        epg_remove_btn = QPushButton(tr("remove_source", "- Remove Selected"))

        epg_input_widget = QWidget()
        epg_input_layout = QHBoxLayout(epg_input_widget)
        epg_input_layout.setContentsMargins(0, 0, 0, 0)

        epg_new_url_edit = QLineEdit()
        epg_new_url_edit.setPlaceholderText(tr("enter_epg_url", "Enter EPG URL"))
        epg_new_name_edit = QLineEdit()
        epg_new_name_edit.setPlaceholderText(tr("enter_source_name", "Source name (optional)"))
        epg_new_name_edit.setMaximumWidth(150)

        epg_input_layout.addWidget(QLabel("URL:"))
        epg_input_layout.addWidget(epg_new_url_edit)
        epg_input_layout.addWidget(QLabel("Name:"))
        epg_input_layout.addWidget(epg_new_name_edit)

        epg_btn_layout = QHBoxLayout()
        epg_btn_layout.addWidget(epg_add_btn)
        epg_btn_layout.addWidget(epg_remove_btn)
        epg_btn_layout.addStretch()

        epg_interval_label = QLabel(tr("update_interval_colon", "Update interval (minutes):"))
        epg_interval_combo = QComboBox()
        epg_interval_combo.setObjectName("epg_interval_combo")
        epg_interval_combo.addItems(["15", "30", "60", "120", "240", "480", "720"])

        if hasattr(self.window, 'config'):
            epg_interval_value = self.window.config.get_value('EPGSources', 'update_interval', '60')
            index = epg_interval_combo.findText(epg_interval_value)
            if index >= 0:
                epg_interval_combo.setCurrentIndex(index)

        epg_layout.addWidget(epg_sources_label)
        epg_layout.addWidget(epg_list_widget)
        epg_layout.addWidget(epg_input_widget)
        epg_layout.addLayout(epg_btn_layout)
        epg_layout.addWidget(epg_interval_label)
        epg_layout.addWidget(epg_interval_combo)
        epg_group.setLayout(epg_layout)
        main_layout.addWidget(epg_group)

        button_layout = QHBoxLayout()
        save_button = QPushButton(tr("save_button", "Save"))
        cancel_button = QPushButton(tr("cancel_button", "Cancel"))

        save_button.clicked.connect(lambda: self._save_and_close_settings(dialog))
        cancel_button.clicked.connect(dialog.close)

        button_layout.addStretch()
        button_layout.addWidget(save_button)
        button_layout.addWidget(cancel_button)
        main_layout.addLayout(button_layout)

        # 将关键控件保存到 window 实例（供 subscription_ui_controller 使用）
        self.window.playlist_list_widget = playlist_list_widget
        self.window.epg_list_widget = epg_list_widget
        self.window.playlist_new_url_edit = playlist_new_url_edit
        self.window.playlist_new_name_edit = playlist_new_name_edit
        self.window.epg_new_url_edit = epg_new_url_edit
        self.window.epg_new_name_edit = epg_new_name_edit
        self.window._editing_playlist_index = -1
        self.window._editing_epg_index = -1
        self.window._playlist_add_btn = playlist_add_btn
        self.window._epg_add_btn = epg_add_btn

        # 信号连接
        playlist_add_btn.clicked.connect(lambda: self.window.subscription_ui_ctrl.add_or_update_playlist_source())
        playlist_remove_btn.clicked.connect(lambda: self.window.subscription_ui_ctrl.remove_selected_playlist_source())
        playlist_list_widget.itemClicked.connect(lambda item: self.window.subscription_ui_ctrl.activate_playlist_source(item))
        playlist_list_widget.itemDoubleClicked.connect(lambda item: self.window.subscription_ui_ctrl.edit_playlist_source(item))

        epg_add_btn.clicked.connect(lambda: self.window.subscription_ui_ctrl.add_or_update_epg_source())
        epg_remove_btn.clicked.connect(lambda: self.window.subscription_ui_ctrl.remove_selected_epg_source())
        epg_list_widget.itemDoubleClicked.connect(lambda item: self.window.subscription_ui_ctrl.edit_epg_source(item))

        # 加载现有数据到UI（直接传入控件，不依赖 window 属性）
        if hasattr(self.window, 'subscription_ui_ctrl'):
            self.window.subscription_ui_ctrl.load_subscription_sources_to_ui(
                pl_widget=playlist_list_widget, epg_widget=epg_list_widget
            )

        # 居中显示对话框
        if hasattr(self.window, '_center_dialog_on_screen'):
            self.window._center_dialog_on_screen(dialog)

        dialog.exec()

    def _save_and_close_settings(self, dialog):
        """保存订阅设置并关闭对话框"""
        try:
            from core.subscription_manager import global_subscription_manager
            from PyQt6 import QtCore

            old_playlist_sources = global_subscription_manager.get_playlist_sources()
            old_epg_sources = global_subscription_manager.get_epg_sources()
            old_active_index = global_subscription_manager.get_active_playlist_source_index()

            new_playlist_sources = []
            pl_widget = getattr(self.window, 'playlist_list_widget', None)
            if pl_widget:
                for i in range(pl_widget.count()):
                    item = pl_widget.item(i)
                    source_data = item.data(QtCore.Qt.ItemDataRole.UserRole)
                    if source_data:
                        source_data['enabled'] = item.checkState() == QtCore.Qt.CheckState.Checked
                        new_playlist_sources.append(source_data)

            if new_playlist_sources:
                global_subscription_manager._config.save_playlist_sources(new_playlist_sources)

            new_epg_sources = []
            epg_widget = getattr(self.window, 'epg_list_widget', None)
            if epg_widget:
                for i in range(epg_widget.count()):
                    item = epg_widget.item(i)
                    source_data = item.data(QtCore.Qt.ItemDataRole.UserRole)
                    if source_data:
                        new_epg_sources.append(source_data)

            if new_epg_sources:
                global_subscription_manager._config.save_epg_sources(new_epg_sources)

            pl_interval_combo = dialog.findChild(QComboBox, "playlist_interval_combo")
            if pl_interval_combo:
                self.window.config.set_value('PlaylistSources', 'update_interval', pl_interval_combo.currentText())

            epg_interval_combo = dialog.findChild(QComboBox, "epg_interval_combo")
            if epg_interval_combo:
                self.window.config.set_value('EPGSources', 'update_interval', epg_interval_combo.currentText())

            playback_changed = False
            new_playback = {}

            rtsp_transport_combo = dialog.findChild(QComboBox, "rtsp_transport_combo")
            if rtsp_transport_combo:
                new_playback['rtsp_transport'] = rtsp_transport_combo.currentText()

            hwdec_check = dialog.findChild(QCheckBox, "hwdec_check")
            if hwdec_check:
                new_playback['hwdec'] = hwdec_check.isChecked()

            tls_check = dialog.findChild(QCheckBox, "tls_check")
            if tls_check:
                new_playback['tls_verify'] = tls_check.isChecked()

            network_timeout_spin = dialog.findChild(QSpinBox, "network_timeout_spin")
            if network_timeout_spin:
                new_playback['network_timeout_sec'] = network_timeout_spin.value()

            if new_playback:
                old_playback = self.window.config.load_playback_settings()
                for k, v in new_playback.items():
                    if old_playback.get(k) != v:
                        playback_changed = True
                        break
                self.window.config.save_playback_settings(new_playback)

                if playback_changed and hasattr(self.window, 'player_controller'):
                    try:
                        pc = self.window.player_controller
                        if pc and hasattr(pc, '_playback_settings'):
                            pc._playback_settings.update(new_playback)
                    except Exception:
                        pass

            new_active_index = -1
            for i, s in enumerate(new_playlist_sources):
                if s.get('enabled'):
                    new_active_index = i
                    break
            if new_active_index < 0 and new_playlist_sources:
                new_active_index = 0

            playlist_changed = False
            if len(old_playlist_sources) != len(new_playlist_sources):
                playlist_changed = True
            elif old_active_index != new_active_index:
                playlist_changed = True
            else:
                for old_s, new_s in zip(old_playlist_sources, new_playlist_sources):
                    if old_s.get('url') != new_s.get('url') or old_s.get('enabled') != new_s.get('enabled'):
                        playlist_changed = True
                        break

            if playlist_changed:
                active = global_subscription_manager.get_active_playlist_source()
                if active:
                    source_index = global_subscription_manager.get_active_playlist_source_index()

                    def _reload_playlist_and_refresh():
                        self.window._handle_playlist_subscription(True, active.get('url', ''), source_index)
                        from PyQt6.QtCore import QMetaObject, Qt, QThread
                        if QThread.currentThread() != self.window.thread():
                            QMetaObject.invokeMethod(self.window, "_do_on_playlist_updated_in_main_thread", Qt.ConnectionType.QueuedConnection)
                        else:
                            self.window._do_on_playlist_updated_in_main_thread()

                    threading.Thread(
                        target=_reload_playlist_and_refresh,
                        daemon=True
                    ).start()

            epg_changed = False
            if len(old_epg_sources) != len(new_epg_sources):
                epg_changed = True
            else:
                for old_s, new_s in zip(old_epg_sources, new_epg_sources):
                    if old_s.get('url') != new_s.get('url'):
                        epg_changed = True
                        break

            if epg_changed:
                threading.Thread(
                    target=global_subscription_manager.load_all_epg_data,
                    daemon=True
                ).start()

            dialog.close()
        except Exception as e:
            from core.log_manager import global_logger as logger
            logger.error(f"保存订阅设置失败: {e}")
            dialog.close()

    def reload_subscription(self):
        """重新加载订阅源"""
        if hasattr(self.window, 'subscription_ctrl'):
            self.window.subscription_ctrl.reload_subscription()

    def set_language(self, language: str):
        """切换语言"""
        try:
            self.window.language_manager.set_language(language)

            from core.config_manager import ConfigManager
            config = ConfigManager()
            config.save_language_settings(language)

            from ui.dialogs.about_dialog import AboutDialog
            current_version = AboutDialog.CURRENT_VERSION
            tr = self.window.language_manager.tr
            new_title = f"{tr('app_title', 'IPTV Scanner Editor Pro')} v{current_version}"
            self.window.setWindowTitle(new_title)
            # 同步更新自定义标题栏标签（无边框窗口 setWindowTitle 不可见）
            if hasattr(self.window, '_title_label') and self.window._title_label:
                self.window._title_label.setText(new_title)

            if hasattr(self.window, 'setup_menu_bar'):
                self.window.setup_menu_bar()

            self.window.language_manager.update_ui_texts(self.window)

            if hasattr(self.window, 'status_bar_show_message'):
                self.window.status_bar_show_message(tr("language_changed", "Language changed"))
        except Exception as e:
            from core.log_manager import global_logger as logger
            logger.error(f"切换语言失败: {e}")
            if hasattr(self.window, 'status_bar_show_message'):
                tr = getattr(self.window.language_manager, 'tr', lambda x, y: x) if hasattr(self.window, 'language_manager') else lambda x, y: x
                self.window.status_bar_show_message(tr("language_change_failed", "Failed"))

    def set_theme(self, theme: str):
        """切换主题"""
        from ui.theme_manager import get_theme_manager
        from ui.styles import AppStyles

        theme_manager = get_theme_manager()
        theme_manager.set_theme(theme)

        self.window.setStyleSheet(AppStyles.main_window_style())

        if hasattr(self.window, '_title_bar') and self.window._title_bar:
            self.window._title_bar.setStyleSheet(AppStyles.title_bar_style())
        if hasattr(self.window, '_title_label') and self.window._title_label:
            self.window._title_label.setStyleSheet(AppStyles.title_label_style())

        if hasattr(self.window, '_custom_menu_bar') and self.window._custom_menu_bar:
            self.window._custom_menu_bar.setStyleSheet(AppStyles.player_menu_bar_style())

        if hasattr(self.window, 'central_widget') and self.window.central_widget:
            self.window.central_widget.setStyleSheet(AppStyles.player_background_style())
        if hasattr(self.window, 'video_frame') and self.window.video_frame:
            self.window.video_frame.setStyleSheet(AppStyles.player_background_style())
        if hasattr(self.window, 'video_placeholder') and self.window.video_placeholder:
            self.window.video_placeholder.setStyleSheet(AppStyles.player_video_placeholder_style())
        if hasattr(self.window, 'status_bar') and self.window.status_bar:
            self.window.status_bar.setStyleSheet(AppStyles.statusbar_style())
        if hasattr(self.window, 'toolbar') and self.window.toolbar:
            self.window.toolbar.setStyleSheet(AppStyles.player_toolbar_style())

        for panel_attr in ['epg_dock', 'playlist_dock', 'floating_dock']:
            panel = getattr(self.window, panel_attr, None)
            if panel:
                container = panel.widget()
                if container and hasattr(container, 'setStyleSheet'):
                    container.setStyleSheet(AppStyles.player_panel_style())
                panel.update()

        if hasattr(self.window, '_reapply_floating_panel_styles'):
            self.window._reapply_floating_panel_styles()
        if hasattr(self.window, '_reapply_side_panel_styles'):
            self.window._reapply_side_panel_styles()

        self.window.update()
        QApplication.processEvents()

    def show_about(self):
        """显示关于对话框"""
        from ui.dialogs.about_dialog import AboutDialog
        dialog = AboutDialog(self.window)
        dialog.exec()

    def show_usage_instructions(self):
        """显示使用说明"""
        from PyQt6 import QtCore, QtGui
        from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QTextEdit, QHBoxLayout,
                                     QPushButton, QFrame, QLabel)
        from ui.styles import AppStyles
        from ui.floating_dialog import FloatingDialog

        dialog = FloatingDialog(self.window, stay_on_top=False)
        tr = self.window.language_manager.tr if hasattr(self.window, 'language_manager') else lambda x, y: x
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
        header_icon.setAlignment(QtCore.Qt.AlignmentFlag.AlignVCenter)
        header_layout.addWidget(header_icon)
        header_title = QLabel(tr("usage_instructions_title", "Usage Instructions"))
        header_title.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {colors['accent']}; background-color: transparent;")
        header_title.setAlignment(QtCore.Qt.AlignmentFlag.AlignVCenter)
        header_layout.addWidget(header_title)
        header_layout.addStretch()
        main_layout.addLayout(header_layout)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background-color: {colors['mid']}; max-height: 1px;")
        main_layout.addWidget(sep)

        text_edit = QTextEdit()
        usage_content = tr("usage_content", "")
        if not usage_content:
            usage_content = '## 基本操作\n\n### 1. 打开播放列表\n- 点击"文件"菜单 → "打开播放列表"（Ctrl+O）\n- 支持 M3U、M3U8、TXT 格式\n- 也可将文件直接拖放到主窗口打开\n\n### 2. 播放频道\n- 在频道列表中**双击**频道开始播放\n- 底部控制面板：▶ 播放 / ▮▮ 暂停 / ■ 停止\n- 音量滑块调节音量，点击图标静音/取消静音\n- 倍速按钮切换播放速度，比例按钮切换画面比例\n- 全屏按钮或 F11 进入全屏\n- **↑ ↓** 键切换频道，**← →** 键调整音量\n\n### 3. EPG 电子节目单\n- 左侧面板显示当前频道节目安排\n- 点击 ◀ / ▶ 切换日期查看节目\n- 进度条实时显示当前节目播放进度\n- 支持配置 EPG 数据源自动订阅更新\n- M3U 文件头中的 EPG 地址会自动加载\n\n### 4. 扫描频道\n- 工具菜单 → 扫描频道\n- 输入 IP 范围或流地址（如 `239.3.1.[1-100]:8000`）\n- 设置超时时间和线程数，支持追加扫描和重试\n- 扫描完成后可使用**批量操作**：\n  - **自动分类**：根据频道名称规则自动归类分组\n  - **清理名称**：去除多余括号、HD后缀等，规范化频道名\n  - **匹配台标**：批量匹配频道台标图片\n  - **分配字段**：批量设置分组、台标等属性\n  - **按组排序**：按频道分组自动排序\n\n### 5. 验证频道\n- 批量检测频道有效性，显示延迟、分辨率等参数\n- 支持智能重试失败的项\n\n### 6. 频道管理\n- **拖拽排序**：拖动调整频道顺序\n- **分组筛选**：下拉框按分组过滤频道\n- **右键菜单**：删除、复制、清理名称、匹配台标等操作\n- **频道分类**：基于正则规则自动归类到对应分组\n- **名称清理**：智能去除冗余信息，规范化显示\n- **导出保存**：另存为 M3U / TXT / Excel 格式\n\n## 高级功能\n\n### 订阅设置\n- 工具菜单 → 订阅设置\n- 配置多个播放列表源和 EPG 数据源，独立管理\n- 支持过期自动刷新和增量更新\n- RTSP 传输方式可选 TCP/UDP/LAVF\n\n### 频道映射\n- 工具菜单 → 频道映射管理器\n- 可视化编辑频道名称、LOGO、分组的映射规则\n\n### 文件关联\n- 工具菜单 → 文件关联\n- 勾选需要关联的格式（M3U/M3U8/TXT/视频格式）\n- 关联后可从资源管理器右键打开\n\n### 界面定制\n- **主题切换**：5 种主题即时切换\n- **语言切换**：中文 / English\n- **面板控制**：视图菜单或快捷键\n  - **E** — EPG 节目单面板\n  - **L** — 频道列表面板\n  - **M** — 播放控制面板\n  - **Y** — 隐藏/恢复所有悬浮面板\n  - **Tab** — 切换 OSD 信息遮罩\n- **F5** 刷新界面，**F11** 全屏，**Ctrl+Q** 退出\n\n### 时移/回看\n- 支持多种回看类型：default / append / shift / flussonic / xc\n- 时间变量替换支持自定义格式和时区偏移\n- M3U 文件头可定义全局回看参数'

        html_content = self._convert_markdown_to_html(usage_content)
        text_edit.setHtml(html_content)
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

        if hasattr(self.window, '_center_dialog_on_screen'):
            self.window._center_dialog_on_screen(dialog)

        dialog.exec()

    @staticmethod
    def _convert_markdown_to_html(markdown):
        """将Markdown格式转换为HTML格式"""
        import re
        from ui.styles import AppStyles
        colors = AppStyles._get_colors()
        html = markdown
        # 先处理三级标题（### ），再处理二级标题（## ），避免顺序混淆
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

    def save_window_layout(self):
        """保存窗口布局"""
        config = getattr(self.window, 'config', None) or getattr(self.window, 'config_manager', None)
        if not config:
            from core.log_manager import global_logger as logger
            logger.warning("无法保存窗口布局：未找到配置管理器")
            return

        geometry = self.window.geometry()

        floating_settings = {
            'epg_visible': getattr(self.window, 'epg_visible', True),
            'playlist_visible': getattr(self.window, 'playlist_visible', True),
            'floating_visible': getattr(self.window, 'floating_panel_visible', True),
        }

        if hasattr(self.window, 'epg_dock') and self.window.epg_dock:
            floating_settings['epg_width'] = self.window.epg_dock.width()
        if hasattr(self.window, 'playlist_dock') and self.window.playlist_dock:
            floating_settings['playlist_width'] = self.window.playlist_dock.width()
        if hasattr(self.window, 'floating_dock') and self.window.floating_dock:
            floating_settings['floating_width'] = self.window.floating_dock.width()

        config.save_window_layout(
            x=geometry.x(),
            y=geometry.y(),
            width=geometry.width(),
            height=geometry.height(),
            dividers=self._get_divider_positions()
        )

        config.save_ui_settings(floating_settings)

    def _get_divider_positions(self) -> list:
        """获取分隔条位置列表（主界面已不再使用分隔条，始终返回空列表）"""
        return []

    def _load_playlist_file(self, file_path: str):
        """加载播放列表文件"""
        tr = self.window.language_manager.tr if hasattr(self.window, 'language_manager') else lambda k, d=None: d or k
        try:
            from services.m3u_parser import load_m3u_file
            content = load_m3u_file(file_path)

            if hasattr(self.window, 'channel_model') and self.window.channel_model:
                if self.window.channel_model.load_from_file(content):
                    channels = self.window.channel_model.channels
                else:
                    channels = []
            else:
                channels = []

            if hasattr(self.window, 'channels'):
                self.window.channels = channels

            import sys
            main_module = sys.modules.get('__main__')
            if main_module and hasattr(main_module, 'CHANNELS'):
                main_module.CHANNELS.clear()
                main_module.CHANNELS.extend(channels)

            from core.application_state import app_state
            app_state._channels.clear()
            app_state._channels.extend(channels)

            # 如果M3U文件头包含EPG地址且未配置EPG源，自动加载
            if hasattr(self.window, 'channel_model') and self.window.channel_model:
                header_attrs = getattr(self.window.channel_model, '_last_header_attrs', {})
                epg_url = header_attrs.get('epg_url', '')
                if epg_url:
                    from core.subscription_manager import global_subscription_manager
                    epg_sources = global_subscription_manager.get_epg_sources()
                    if not epg_sources:
                        from core.log_manager import global_logger as logger
                        logger.info(f"本地文件头发现EPG地址，自动加载: {epg_url[:80]}")
                        try:
                            global_subscription_manager.load_single_epg(epg_url)
                            if hasattr(self.window, '_populate_epg_list'):
                                from PyQt6.QtCore import QTimer
                                QTimer.singleShot(500, self.window._populate_epg_list)
                        except Exception as epg_err:
                            from core.log_manager import global_logger as logger
                            logger.warning(f"从本地文件头加载EPG失败: {epg_err}")

            if hasattr(self.window, 'playlist_tab'):
                self.window.playlist_tab.setCurrentIndex(1)

            if hasattr(self.window, 'populate_channel_list'):
                self.window.populate_channel_list(source='local')

            from core.log_manager import global_logger as logger
            logger.info(f"成功加载播放列表: {file_path}, 共 {len(channels)} 个频道")

        except Exception as e:
            from core.log_manager import global_logger as logger
            logger.error(f"加载播放列表失败: {e}")
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(
                self.window,
                tr("error", "Error"),
                tr("open_file_error", "Failed to load playlist:\n{error}").format(error=str(e))
            )

    def _save_playlist_file(self, file_path: str):
        """保存播放列表文件"""
        tr = self.window.language_manager.tr if hasattr(self.window, 'language_manager') else lambda k, d=None: d or k
        try:
            if not hasattr(self.window, 'channels'):
                return

            channels = self.window.channels

            # 根据扩展名选择格式
            if file_path.endswith('.m3u') or file_path.endswith('.m3u8'):
                self._save_as_m3u(channels, file_path)
            elif file_path.endswith('.txt'):
                self._save_as_txt(channels, file_path)
            else:
                # 默认M3U格式
                self._save_as_m3u(channels, file_path)

            from core.log_manager import global_logger as logger
            logger.info(f"成功保存播放列表: {file_path}")

        except Exception as e:
            QMessageBox.critical(
                self.window,
                tr("error", "Error"),
                tr("save_error", "Failed to save playlist:\n{error}").format(error=str(e))
            )

    def _save_as_m3u(self, channels: list, file_path: str):
        """保存为M3U格式（保留完整元数据）"""
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write('#EXTM3U\n')
            for ch in channels:
                name = ch.get('name', '')
                url = ch.get('url', '')
                group = ch.get('group', '')
                logo = ch.get('logo_url', '')
                tvg_id = ch.get('tvg_id', '')
                tvg_name = ch.get('_all_tags', {}).get('tvg-name', '') if ch.get('_all_tags') else ''
                tvg_chno = ch.get('_all_tags', {}).get('tvg-chno', '') if ch.get('_all_tags') else ''
                tvg_shift = ch.get('_all_tags', {}).get('tvg-shift', '') if ch.get('_all_tags') else ''
                catchup = ch.get('_all_tags', {}).get('catchup', '') if ch.get('_all_tags') else ''
                catchup_days = ch.get('_all_tags', {}).get('catchup-days', '') if ch.get('_all_tags') else ''
                catchup_source = ch.get('catchup_source', '')
                catchup_correction = ch.get('_all_tags', {}).get('catchup-correction', '') if ch.get('_all_tags') else ''
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

    def _save_as_txt(self, channels: list, file_path: str):
        """保存为TXT格式"""
        with open(file_path, 'w', encoding='utf-8') as f:
            for ch in channels:
                name = ch.get('name', '')
                url = ch.get('url', '')
                f.write(f"{name},{url}\n")
