"""
设置和文件操作处理器 - 负责配置管理、文件打开/保存等
从 pyqt_player.py 提取的独立模块
"""

from typing import Optional
from PyQt6.QtWidgets import QFileDialog, QMessageBox, QComboBox


class SettingsFileOperations:
    """设置和文件操作 - 管理配置和文件I/O"""

    def __init__(self, main_window):
        self.window = main_window

    def open_playlist(self):
        """打开播放列表文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self.window,
            "Open Playlist",
            "",
            "M3U Files (*.m3u *.m3u8);;All Files (*)"
        )
        
        if file_path:
            self._load_playlist_file(file_path)

    def save_as(self):
        """另存为"""
        if not hasattr(self.window, 'channels') or not self.window.channels:
            QMessageBox.warning(
                self.window,
                "Warning",
                "No channels to save"
            )
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self.window,
            "Save Playlist",
            "",
            "M3U Files (*.m3u);;Text Files (*.txt);;All Files (*)"
        )
        
        if file_path:
            self._save_playlist_file(file_path)

    def player_settings(self):
        """显示播放器设置对话框"""
        from core.log_manager import global_logger as logger
        from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                                     QPushButton, QComboBox, QLineEdit, QGroupBox,
                                     QListWidget, QListWidgetItem, QWidget, QFormLayout)

        try:
            FloatingDialog = __import__('ui.floating_dialog', fromlist=['FloatingDialog']).FloatingDialog
            AppStyles = __import__('ui.styles', fromlist=['AppStyles']).AppStyles

            # 创建对话框（FloatingDialog支持stay_on_top参数）
            try:
                dialog = FloatingDialog(self.window, stay_on_top=False)
            except TypeError:
                # 如果参数不支持，尝试不带参数创建
                dialog = FloatingDialog(self.window)
        except ImportError:
            # 导入失败时使用标准 QDialog（不支持 stay_on_top 参数）
            from PyQt6.QtWidgets import QDialog as FloatingDialog
            AppStyles = None
            dialog = FloatingDialog(self.window)
        tr = self.window.language_manager.tr if hasattr(self.window, 'language_manager') else lambda x, y: x
        dialog.setWindowTitle(tr("subscription_settings_title", "Subscription Settings"))
        dialog.setMinimumSize(600, 550)
        if AppStyles:
            dialog.setStyleSheet(AppStyles.dialog_style())

        main_layout = QVBoxLayout(dialog)

        protocol_group = QGroupBox(tr("protocol_settings", "Protocol Settings"))
        protocol_layout = QVBoxLayout()

        protocol_label = QLabel(tr("protocol_type_colon", "Protocol Type:"))
        protocol_combo = QComboBox()
        protocol_combo.addItems(["HTTP", "HTTPS", "RTSP", "RTMP", "HLS"])

        if hasattr(self.window, 'config'):
            protocol = self.window.config.get_value('Player', 'protocol', 'HTTP')
            index = protocol_combo.findText(protocol)
            if index >= 0:
                protocol_combo.setCurrentIndex(index)

        protocol_layout.addWidget(protocol_label)
        protocol_layout.addWidget(protocol_combo)
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
                import threading
                active = global_subscription_manager.get_active_playlist_source()
                if active:
                    threading.Thread(
                        target=self.window._handle_playlist_subscription,
                        args=(True,),
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
                import threading
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
        if hasattr(self.window, '_handle_playlist_subscription'):
            self.window._handle_playlist_subscription(need_update=True)

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
            self.window.setWindowTitle(f"{tr('app_title', 'IPTV Scanner Editor Pro')} v{current_version}")

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

        # 刷新主窗口和悬浮窗样式
        if hasattr(self.window, 'refresh_ui'):
            self.window.refresh_ui()

        # 重新应用3个停靠面板的面板样式（只应用到内部容器widget）
        for panel_attr in ['epg_dock', 'playlist_dock', 'floating_dock']:
            panel = getattr(self.window, panel_attr, None)
            if panel:
                container = panel.widget()
                if container and hasattr(container, 'setStyleSheet'):
                    container.setStyleSheet(AppStyles.player_panel_style())
                panel.update()

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
            usage_content = '## 基本操作\n\n### 1. 打开播放列表\n- 点击"文件"菜单 → "打开播放列表"（快捷键 Ctrl+O）\n- 支持 M3U、M3U8、TXT 格式的播放列表文件\n- 支持最近打开的文件快速访问\n\n### 2. 播放频道\n- 在右侧频道列表中**双击**任意频道开始播放\n- 底部控制面板操作：\n  - **▶ 播放 / ▮▮ 暂停 / ■ 停止**：控制播放状态\n  - **🔊 音量滑块**：调节音量，点击图标静音/取消静音\n  - **倍速按钮**：循环切换播放速度（1.0x / 1.25x / 1.5x / 2.0x）\n  - **📐 比例按钮**：切换画面比例（原始/16:9/4:3/填充）\n  - **⛶ 全屏按钮**：进入/退出全屏模式（F11）\n- 键盘快捷键：空格键播放/暂停，Escape 退出全屏\n\n### 3. EPG 电子节目单\n- 左侧面板显示当前选中频道的节目安排\n- 点击 **◀ / ▶** 切换查看不同日期的节目\n- 进度条实时显示当前节目播放进度和时间轴\n- 支持配置远程 EPG 数据源自动订阅更新\n\n### 4. 扫描频道\n- 点击"工具"菜单 → "扫描频道"\n- 输入 IP 范围或流地址（如 `239.3.1.[1-100]:8000`）\n- 设置超时时间和线程数，支持追加扫描和重试\n\n### 5. 验证频道\n- 打开播放列表后可批量检测频道有效性\n- 显示检测进度、有效/无效数量及延迟等参数\n\n### 6. 频道管理\n- **拖拽排序**：在频道列表中拖动调整顺序\n- **分组筛选**：使用顶部下拉框按分组过滤频道\n- **右键菜单**：删除、复制频道名及 URL 等操作\n- **导出保存**：另存为 M3U / TXT / Excel 格式\n\n## 高级功能\n\n### 订阅设置\n- 工具菜单 → 订阅设置\n- 配置播放列表订阅 URL 和 EPG 数据源地址\n- 支持过期自动刷新和 URL 变更强制重新下载\n\n### 频道映射\n- 工具菜单 → 频道映射管理器\n- 可视化编辑频道名称、LOGO、分组的映射规则\n\n### 界面定制\n- **主题切换**：主题菜单提供多种主题\n- **语言切换**：语言菜单支持中文/English\n- **面板控制**：视图菜单或快捷键控制各面板显隐\n  - **E** — EPG 节目单面板\n  - **L** — 频道列表面板\n  - **M** — 播放控制面板\n- **F5** 刷新界面，**F11** 全屏，**Ctrl+Q** 退出'

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

        config.save_window_layout(
            x=geometry.x(),
            y=geometry.y(),
            width=geometry.width(),
            height=geometry.height(),
            dividers=self._get_divider_positions()
        )

    def _get_divider_positions(self) -> list:
        """获取分隔条位置列表"""
        positions = []
        # TODO: 从UI获取各分隔条的位置
        return positions

    def _load_playlist_file(self, file_path: str):
        """加载播放列表文件"""
        try:
            from services.m3u_parser import parse_m3u
            channels = parse_m3u(file_path)
            
            if hasattr(self.window, 'channels'):
                self.window.channels = channels
                
            if hasattr(self.window, 'channel_model'):
                self.window.channel_model.set_channels(channels)
                
            # 刷新UI
            if hasattr(self.window, 'channel_ctrl'):
                self.window.channel_ctrl.populate_channel_list()
                
            from core.log_manager import global_logger as logger
            logger.info(f"成功加载播放列表: {file_path}, 共 {len(channels)} 个频道")
            
        except Exception as e:
            QMessageBox.critical(
                self.window,
                "Error",
                f"Failed to load playlist:\n{str(e)}"
            )

    def _save_playlist_file(self, file_path: str):
        """保存播放列表文件"""
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
                "Error",
                f"Failed to save playlist:\n{str(e)}"
            )

    def _save_as_m3u(self, channels: list, file_path: str):
        """保存为M3U格式"""
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write('#EXTM3U\n')
            for ch in channels:
                name = ch.get('name', '')
                url = ch.get('url', '')
                group = ch.get('group', '')
                logo = ch.get('logo_url', '')
                
                f.write(f'#EXTINF:-1 {name}')
                if group:
                    f.write(f' group-title="{group}"')
                if logo:
                    f.write(f' tvg-logo="{logo}"')
                f.write('\n')
                f.write(f'{url}\n')

    def _save_as_txt(self, channels: list, file_path: str):
        """保存为TXT格式"""
        with open(file_path, 'w', encoding='utf-8') as f:
            for ch in channels:
                name = ch.get('name', '')
                url = ch.get('url', '')
                f.write(f"{name},{url}\n")
