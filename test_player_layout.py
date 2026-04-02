"""
测试新的播放器布局
运行此脚本查看新布局效果
"""
import sys
from PyQt6 import QtWidgets, QtCore, QtGui
from ui.player_layout import PlayerLayout


class TestMainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        
        # 去掉系统标题栏
        self.setWindowFlags(QtCore.Qt.WindowType.FramelessWindowHint)
        
        # 设置语言管理器（简化版）
        self.language_manager = None
        
        # 构建新布局
        self.layout_manager = PlayerLayout(self)
        self.layout_manager.build_layout()
        
        # 添加自定义标题栏
        self._setup_custom_titlebar()
        
        # 添加一些测试数据到播放列表
        self._load_test_data()
        
        # 设置窗口大小和位置
        self.resize(1600, 900)
        self.move(100, 100)
        
        # 设置鼠标跟踪以显示悬浮面板
        self.setMouseTracking(True)
        self.centralWidget().setMouseTracking(True)
        
        # 不再使用悬浮面板中的展开按钮，使用面板本身的收起/展开按钮
        
        # 为播放列表添加右键菜单
        if hasattr(self.layout_manager.main_window, 'playlist_table'):
            self.layout_manager.main_window.playlist_table.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
            self.layout_manager.main_window.playlist_table.customContextMenuRequested.connect(self._show_playlist_context_menu)
        
        # 连接信号
        self._connect_signals()
        
    def _setup_custom_titlebar(self):
        """设置自定义标题栏"""
        # 获取原有的central widget
        old_central = self.centralWidget()
        
        # 创建新的主容器
        main_container = QtWidgets.QWidget()
        main_layout = QtWidgets.QVBoxLayout(main_container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 创建自定义标题栏
        titlebar = QtWidgets.QWidget()
        titlebar.setStyleSheet("background-color: #1a1a1a;")
        titlebar.setFixedHeight(32)
        
        titlebar_layout = QtWidgets.QHBoxLayout(titlebar)
        titlebar_layout.setContentsMargins(8, 0, 8, 0)
        titlebar_layout.setSpacing(8)
        
        # LOGO和标题
        title_label = QtWidgets.QLabel("📺  IPTV Pro")
        title_label.setStyleSheet("color: #fff; font-size: 13px; font-weight: bold;")
        titlebar_layout.addWidget(title_label)
        
        # 自定义菜单
        file_menu = QtWidgets.QPushButton("文件")
        file_menu.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #ccc;
                border: none;
                padding: 5px 10px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #3d3d3d;
                color: #fff;
            }
        """)
        file_menu.clicked.connect(self._show_file_menu)
        titlebar_layout.addWidget(file_menu)
        
        view_menu = QtWidgets.QPushButton("视图")
        view_menu.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #ccc;
                border: none;
                padding: 5px 10px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #3d3d3d;
                color: #fff;
            }
        """)
        view_menu.clicked.connect(self._show_view_menu)
        titlebar_layout.addWidget(view_menu)
        
        tools_menu = QtWidgets.QPushButton("工具")
        tools_menu.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #ccc;
                border: none;
                padding: 5px 10px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #3d3d3d;
                color: #fff;
            }
        """)
        tools_menu.clicked.connect(self._show_tools_menu)
        titlebar_layout.addWidget(tools_menu)
        
        help_menu = QtWidgets.QPushButton("帮助")
        help_menu.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #ccc;
                border: none;
                padding: 5px 10px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #3d3d3d;
                color: #fff;
            }
        """)
        help_menu.clicked.connect(self._show_help_menu)
        titlebar_layout.addWidget(help_menu)
        
        titlebar_layout.addStretch()
        
        # 窗口控制按钮
        self.btn_minimize = QtWidgets.QPushButton("─")
        self.btn_minimize.setFixedSize(32, 32)
        self.btn_minimize.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #888;
                border: none;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #3d3d3d;
                color: #fff;
            }
        """)
        titlebar_layout.addWidget(self.btn_minimize)
        
        self.btn_maximize = QtWidgets.QPushButton("□")
        self.btn_maximize.setFixedSize(32, 32)
        self.btn_maximize.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #888;
                border: none;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #3d3d3d;
                color: #fff;
            }
        """)
        titlebar_layout.addWidget(self.btn_maximize)
        
        self.btn_close = QtWidgets.QPushButton("✕")
        self.btn_close.setFixedSize(32, 32)
        self.btn_close.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #888;
                border: none;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #e81123;
                color: #fff;
            }
        """)
        titlebar_layout.addWidget(self.btn_close)
        
        main_layout.addWidget(titlebar)
        main_layout.addWidget(old_central)
        
        self.setCentralWidget(main_container)
        
        # 保存标题栏引用
        self.titlebar = titlebar
        self.title_label = title_label
        
        # 连接窗口控制按钮信号
        self.btn_minimize.clicked.connect(self.showMinimized)
        self.btn_maximize.clicked.connect(self._toggle_maximize)
        self.btn_close.clicked.connect(self.close)
        
        # 允许拖动标题栏
        self.drag_position = None
        titlebar.mousePressEvent = self.titlebar_mouse_press
        titlebar.mouseMoveEvent = self.titlebar_mouse_move
        
    def _toggle_maximize(self):
        """切换最大化/还原"""
        if self.isMaximized():
            self.showNormal()
            self.btn_maximize.setText("□")
        else:
            self.showMaximized()
            self.btn_maximize.setText("◱")
            
    def titlebar_mouse_press(self, event):
        """标题栏鼠标按下"""
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            
    def titlebar_mouse_move(self, event):
        """标题栏鼠标移动"""
        if event.buttons() == QtCore.Qt.MouseButton.LeftButton and self.drag_position is not None:
            if self.isMaximized():
                # 如果是最大化状态，先还原
                self.showNormal()
                self.btn_maximize.setText("□")
                # 调整鼠标位置
                self.drag_position = event.globalPosition().toPoint() - QtCore.QPoint(self.width() // 2, 10)
            self.move(event.globalPosition().toPoint() - self.drag_position)
        
    def _load_test_data(self):
        """加载测试数据"""
        # 添加测试频道到播放列表
        test_channels = [
            ("1", "CCTV-1 综合", "新闻联播", "http://192.168.1.1:8080/live/cctv1", "✅"),
            ("2", "CCTV-2 财经", "经济半小时", "http://192.168.1.2:8080/live/cctv2", "✅"),
            ("3", "湖南卫视", "快乐大本营", "http://192.168.1.3:8080/live/hunan", "✅"),
            ("4", "浙江卫视", "中国好声音", "http://192.168.1.4:8080/live/zhejiang", "✅"),
            ("5", "江苏卫视", "非诚勿扰", "http://192.168.1.5:8080/live/jiangsu", "✅"),
            ("6", "东方卫视", "极限挑战", "http://192.168.1.6:8080/live/dongfang", "✅"),
            ("7", "北京卫视", "养生堂", "http://192.168.1.7:8080/live/beijing", "✅"),
            ("8", "深圳卫视", "暂无节目", "http://192.168.1.8:8080/live/shenzhen", "⚠️"),
            ("9", "山东卫视", "山东新闻联播", "http://192.168.1.9:8080/live/shandong", "✅"),
            ("10", "广东卫视", "珠江新闻", "http://192.168.1.10:8080/live/guangdong", "✅"),
        ]
        
        self.playlist_table.setRowCount(len(test_channels))
        self.playlist_table.verticalHeader().setDefaultSectionSize(60)
        
        for row, (num, name, epg, url, status) in enumerate(test_channels):
            # 序号
            self.playlist_table.setItem(row, 0, QtWidgets.QTableWidgetItem(num))
            # LOGO（用状态代替）
            logo_item = QtWidgets.QTableWidgetItem(status)
            logo_item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            self.playlist_table.setItem(row, 1, logo_item)
            
            # 频道信息（自定义widget）
            channel_info_widget = QtWidgets.QWidget()
            channel_info_layout = QtWidgets.QVBoxLayout(channel_info_widget)
            channel_info_layout.setContentsMargins(2, 2, 2, 2)
            channel_info_layout.setSpacing(2)
            
            # 第一行：频道名称 + 正在播放
            name_epg_label = QtWidgets.QLabel(f"<b>{name}</b>  -  <span style='color:#4CAF50;'>{epg}</span>")
            name_epg_label.setStyleSheet("color: #fff;")
            channel_info_layout.addWidget(name_epg_label)
            
            # 第二行：频道地址
            url_label = QtWidgets.QLabel(f"<small style='color:#888;'>{url}</small>")
            channel_info_layout.addWidget(url_label)
            
            channel_info_layout.addStretch()
            
            self.playlist_table.setCellWidget(row, 2, channel_info_widget)
            
    def _connect_signals(self):
        """连接信号"""
        # 播放列表点击
        self.playlist_table.itemClicked.connect(self._on_channel_selected)
        
        # EPG收起/展开按钮
        self.epg_collapse_btn.clicked.connect(self._toggle_epg_panel)
        
        # 播放列表收起/展开按钮
        self.playlist_collapse_btn.clicked.connect(self._toggle_playlist_panel)
        
        # 按钮点击
        self.btn_play_pause.clicked.connect(self._toggle_play_pause)
        self.btn_prev.clicked.connect(self._prev_channel)
        self.btn_next.clicked.connect(self._next_channel)
        self.btn_fullscreen.clicked.connect(self._toggle_fullscreen)
        
    def _on_channel_selected(self, item):
        """频道被选中"""
        row = item.row()
        channel_name = self.playlist_table.item(row, 2).text()
        self.current_channel_label.setText(f"{channel_name} - 准备播放...")
        
    def _toggle_play_pause(self):
        """播放/暂停切换"""
        current_text = self.btn_play_pause.text()
        if current_text == "⏸️":
            self.btn_play_pause.setText("▶️")
        else:
            self.btn_play_pause.setText("⏸️")
            
    def _prev_channel(self):
        """上一个频道"""
        current_row = self.playlist_table.currentRow()
        if current_row > 0:
            self.playlist_table.setCurrentCell(current_row - 1, 0)
            
    def _next_channel(self):
        """下一个频道"""
        current_row = self.playlist_table.currentRow()
        if current_row < self.playlist_table.rowCount() - 1:
            self.playlist_table.setCurrentCell(current_row + 1, 0)
            
    def _toggle_fullscreen(self):
        """切换全屏"""
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()
            
    def _edit_channel(self):
        """编辑频道"""
        QtWidgets.QMessageBox.information(self, "编辑频道", "打开频道编辑器对话框")
        
    def _delete_channel(self):
        """删除频道"""
        current_row = self.playlist_table.currentRow()
        if current_row >= 0:
            reply = QtWidgets.QMessageBox.question(
                self, "确认删除", "确定要删除选中的频道吗？",
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
            )
            if reply == QtWidgets.QMessageBox.StandardButton.Yes:
                self.playlist_table.removeRow(current_row)
                
    def _scan_channels(self):
        """扫描频道"""
        QtWidgets.QMessageBox.information(self, "扫描频道", "打开扫描管理器对话框")
        
    def _open_file(self):
        """打开文件"""
        file_name, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "打开播放列表", "", "M3U Files (*.m3u *.m3u8);;All Files (*)"
        )
        if file_name:
            QtWidgets.QMessageBox.information(self, "打开文件", f"已选择: {file_name}")
            
    def _save_file(self):
        """保存文件"""
        file_name, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "保存播放列表", "", "M3U Files (*.m3u *.m3u8);;All Files (*)"
        )
        if file_name:
            QtWidgets.QMessageBox.information(self, "保存文件", f"已保存到: {file_name}")
            
    def _show_about(self):
        """显示关于对话框"""
        QtWidgets.QMessageBox.about(
            self, "关于 IPTV Pro",
            "IPTV Pro - 现代化IPTV播放器\n\n"
            "版本: 2.0.0\n"
            "作者: sumingyd\n"
            "GitHub: github.com/sumingyd/IPTV-Scanner-Editor-Pro"
        )
        
    def _toggle_epg_panel(self):
        """切换EPG面板收起/展开 - 新方案"""
        if not hasattr(self, 'layout_manager'):
            return
        
        if self.layout_manager.epg_collapsed:
            # 展开
            self.layout_manager.epg_collapsed = False
            # 更新所有窗口位置
            self.layout_manager._update_all_windows_position()
            # 隐藏独立的展开按钮
            if hasattr(self, 'epg_expand_button') and self.epg_expand_button:
                self.epg_expand_button.hide()
        else:
            # 收起
            self.layout_manager.epg_collapsed = True
            # 更新所有窗口位置
            self.layout_manager._update_all_windows_position()
            # 创建独立的展开按钮
            if not hasattr(self, 'epg_expand_button') or not self.epg_expand_button:
                self.epg_expand_button = QtWidgets.QPushButton("▶")
                self.epg_expand_button.setFixedSize(32, 32)
                self.epg_expand_button.setStyleSheet("""
                    QPushButton {
                        background-color: rgba(45, 45, 45, 150);
                        color: #aaa;
                        border: none;
                        border-radius: 4px;
                        font-size: 12px;
                        padding: 6px;
                    }
                    QPushButton:hover {
                        background-color: rgba(60, 60, 60, 200);
                        color: #fff;
                    }
                """)
                self.epg_expand_button.clicked.connect(self._toggle_epg_panel)
                self.epg_expand_button.setParent(self)
                # 设置窗口标志，使其独立
                self.epg_expand_button.setWindowFlags(
                    QtCore.Qt.WindowType.FramelessWindowHint |
                    QtCore.Qt.WindowType.WindowStaysOnTopHint |
                    QtCore.Qt.WindowType.Tool
                )
            # 定位按钮到左侧边缘
            self._update_expand_button_positions()
            # 初始隐藏，当悬浮窗显示时再显示
            self.epg_expand_button.hide()
            
    def _toggle_playlist_panel(self):
        """切换播放列表面板收起/展开 - 新方案"""
        if not hasattr(self, 'layout_manager'):
            return
        
        if self.layout_manager.playlist_collapsed:
            # 展开
            self.layout_manager.playlist_collapsed = False
            # 更新所有窗口位置
            self.layout_manager._update_all_windows_position()
            # 隐藏独立的展开按钮
            if hasattr(self, 'playlist_expand_button') and self.playlist_expand_button:
                self.playlist_expand_button.hide()
        else:
            # 收起
            self.layout_manager.playlist_collapsed = True
            # 更新所有窗口位置
            self.layout_manager._update_all_windows_position()
            # 创建独立的展开按钮
            if not hasattr(self, 'playlist_expand_button') or not self.playlist_expand_button:
                self.playlist_expand_button = QtWidgets.QPushButton("◀")
                self.playlist_expand_button.setFixedSize(32, 32)
                self.playlist_expand_button.setStyleSheet("""
                    QPushButton {
                        background-color: rgba(45, 45, 45, 150);
                        color: #aaa;
                        border: none;
                        border-radius: 4px;
                        font-size: 12px;
                        padding: 6px;
                    }
                    QPushButton:hover {
                        background-color: rgba(60, 60, 60, 200);
                        color: #fff;
                    }
                """)
                self.playlist_expand_button.clicked.connect(self._toggle_playlist_panel)
                self.playlist_expand_button.setParent(self)
                # 设置窗口标志，使其独立
                self.playlist_expand_button.setWindowFlags(
                    QtCore.Qt.WindowType.FramelessWindowHint |
                    QtCore.Qt.WindowType.WindowStaysOnTopHint |
                    QtCore.Qt.WindowType.Tool
                )
            # 定位按钮到右侧边缘
            self._update_expand_button_positions()
            # 初始隐藏，当悬浮窗显示时再显示
            self.playlist_expand_button.hide()
    
    def enterEvent(self, event):
        """鼠标进入窗口事件"""
        super().enterEvent(event)
        self._check_show_floating_panel()
        
    def mouseMoveEvent(self, event):
        """鼠标移动事件 - 控制悬浮面板显示"""
        super().mouseMoveEvent(event)
        self._check_show_floating_panel()
        
    def _check_show_floating_panel(self):
        """检查是否显示悬浮面板 - 新方案"""
        # 获取鼠标在窗口中的位置
        cursor_global = QtGui.QCursor.pos()
        
        # 检查鼠标是否在悬浮面板区域内
        is_over_floating = False
        if self.floating_panel.isVisible():
            # 转换鼠标位置到悬浮面板的坐标系
            cursor_in_floating = self.floating_panel.mapFromGlobal(cursor_global)
            is_over_floating = self.floating_panel.rect().contains(cursor_in_floating)
        
        # 检查鼠标是否在视频播放区域的底部触发区域
        is_over_video_trigger = False
        if hasattr(self.layout_manager.main_window, 'video_frame'):
            video_frame = self.layout_manager.main_window.video_frame
            # 转换视频区域的几何位置到全局坐标系
            video_top_left = video_frame.mapToGlobal(QtCore.QPoint(0, 0))
            video_size = video_frame.size()
            # 创建视频区域的全局矩形
            video_global_rect = QtCore.QRect(video_top_left, video_size)
            # 检查鼠标是否在视频区域内，并且在底部150px范围内
            if video_global_rect.contains(cursor_global):
                # 计算鼠标在视频区域内的Y坐标
                mouse_in_video_y = cursor_global.y() - video_global_rect.top()
                if mouse_in_video_y > video_global_rect.height() - 150:
                    is_over_video_trigger = True
        
        # 检查鼠标是否在收起的面板按钮上
        is_over_epg_btn = False
        is_over_playlist_btn = False
        
        # 检查EPG独立展开按钮
        if hasattr(self.layout_manager, 'epg_collapsed') and self.layout_manager.epg_collapsed:
            if hasattr(self, 'epg_expand_button') and self.epg_expand_button:
                btn_rect = self.epg_expand_button.geometry()
                btn_global = self.epg_expand_button.mapToGlobal(QtCore.QPoint(0, 0))
                btn_rect.moveTo(btn_global)
                is_over_epg_btn = btn_rect.contains(cursor_global)
        
        # 检查播放列表独立展开按钮
        if hasattr(self.layout_manager, 'playlist_collapsed') and self.layout_manager.playlist_collapsed:
            if hasattr(self, 'playlist_expand_button') and self.playlist_expand_button:
                btn_rect = self.playlist_expand_button.geometry()
                btn_global = self.playlist_expand_button.mapToGlobal(QtCore.QPoint(0, 0))
                btn_rect.moveTo(btn_global)
                is_over_playlist_btn = btn_rect.contains(cursor_global)
        
        # 调试信息
        # print(f"Mouse: {cursor_global}, Over floating: {is_over_floating}, Over video trigger: {is_over_video_trigger}")
        
        if self.floating_panel.isVisible():
            if is_over_floating or is_over_video_trigger or is_over_epg_btn or is_over_playlist_btn:
                # 鼠标在悬浮面板区域、视频底部触发区域或收起按钮上，保持显示，取消隐藏定时器
                if hasattr(self, '_hide_timer') and self._hide_timer is not None:
                    self._hide_timer.stop()
                # 显示收起的面板按钮
                self._show_collapsed_buttons()
            else:
                # 鼠标离开悬浮区域，启动2秒延迟隐藏
                if not hasattr(self, '_hide_timer') or self._hide_timer is None:
                    self._hide_timer = QtCore.QTimer()
                    self._hide_timer.setSingleShot(True)
                    self._hide_timer.timeout.connect(self._hide_floating_panel)
                if not self._hide_timer.isActive():
                    self._hide_timer.start(2000)  # 2秒延迟
        else:
            # 悬浮面板隐藏时，检查鼠标是否在视频底部区域或收起按钮上来显示
            if is_over_video_trigger or is_over_epg_btn or is_over_playlist_btn:
                if not self.floating_panel.isVisible():
                    self.floating_panel.show()
                    self.floating_panel.raise_()
                    # 显示收起的面板按钮
                    self._show_collapsed_buttons()
                    # 确保隐藏定时器停止
                    if hasattr(self, '_hide_timer') and self._hide_timer is not None:
                        self._hide_timer.stop()

    def _update_expand_button_positions(self):
        """更新独立展开按钮的位置"""
        # 计算按钮位置，与悬浮窗在同一水平线上
        window_rect = self.geometry()
        # 悬浮窗距离底部30px，按钮在悬浮窗上方10px
        btn_y = window_rect.bottom() - 220 - 10 - 32 // 2
        
        # 定位EPG展开按钮（左侧边缘）
        if hasattr(self, 'epg_expand_button') and self.epg_expand_button:
            btn_x = window_rect.left() + 10
            self.epg_expand_button.move(btn_x, btn_y)
        
        # 定位播放列表展开按钮（右侧边缘）
        if hasattr(self, 'playlist_expand_button') and self.playlist_expand_button:
            btn_x = window_rect.right() - self.playlist_expand_button.width() - 10
            self.playlist_expand_button.move(btn_x, btn_y)

    def _show_collapsed_buttons(self):
        """显示收起的面板按钮"""
        # 显示EPG独立展开按钮
        if hasattr(self.layout_manager, 'epg_collapsed') and self.layout_manager.epg_collapsed:
            if hasattr(self, 'epg_expand_button') and self.epg_expand_button:
                self.epg_expand_button.show()
        # 显示播放列表独立展开按钮
        if hasattr(self.layout_manager, 'playlist_collapsed') and self.layout_manager.playlist_collapsed:
            if hasattr(self, 'playlist_expand_button') and self.playlist_expand_button:
                self.playlist_expand_button.show()

    def _hide_floating_panel(self):
        """隐藏悬浮面板"""
        if hasattr(self, 'floating_panel') and self.floating_panel.isVisible():
            self.floating_panel.hide()
            # 同时隐藏独立的展开按钮
            if hasattr(self, 'epg_expand_button') and self.epg_expand_button:
                self.epg_expand_button.hide()
            if hasattr(self, 'playlist_expand_button') and self.playlist_expand_button:
                self.playlist_expand_button.hide()
            
    def _show_file_menu(self):
        """显示文件菜单"""
        menu = QtWidgets.QMenu(self)
        open_action = menu.addAction("打开文件...")
        open_url_action = menu.addAction("打开网络地址...")
        open_playlist_action = menu.addAction("打开播放列表...")
        menu.addSeparator()
        save_action = menu.addAction("保存文件")
        save_as_action = menu.addAction("另存为...")
        save_playlist_action = menu.addAction("保存播放列表")
        menu.addSeparator()
        exit_action = menu.addAction("退出")
        
        # 连接信号
        open_action.triggered.connect(self._open_file)
        save_action.triggered.connect(self._save_file)
        exit_action.triggered.connect(self.close)
        
        # 显示菜单
        menu.exec(QtGui.QCursor.pos())
        
    def _show_view_menu(self):
        """显示视图菜单"""
        menu = QtWidgets.QMenu(self)
        epg_action = menu.addAction("显示节目单")
        playlist_action = menu.addAction("显示播放列表")
        menu.addSeparator()
        fullscreen_action = menu.addAction("全屏")
        compact_mode_action = menu.addAction("紧凑模式")
        menu.addSeparator()
        language_action = menu.addAction("语言")
        
        # 连接信号
        epg_action.triggered.connect(lambda: self._toggle_epg_panel() if hasattr(self, '_toggle_epg_panel') else None)
        playlist_action.triggered.connect(lambda: self._toggle_playlist_panel() if hasattr(self, '_toggle_playlist_panel') else None)
        fullscreen_action.triggered.connect(lambda: self._toggle_fullscreen() if hasattr(self, '_toggle_fullscreen') else None)
        
        # 显示菜单
        menu.exec(QtGui.QCursor.pos())
        
    def _show_tools_menu(self):
        """显示工具菜单"""
        menu = QtWidgets.QMenu(self)
        scan_action = menu.addAction("扫描频道")
        edit_action = menu.addAction("编辑频道")
        delete_action = menu.addAction("删除频道")
        menu.addSeparator()
        favorite_action = menu.addAction("收藏频道")
        export_action = menu.addAction("导出频道")
        import_action = menu.addAction("导入频道")
        menu.addSeparator()
        settings_action = menu.addAction("设置")
        
        # 连接信号
        scan_action.triggered.connect(lambda: self._scan_channels() if hasattr(self, '_scan_channels') else None)
        edit_action.triggered.connect(lambda: self._edit_channel() if hasattr(self, '_edit_channel') else None)
        delete_action.triggered.connect(lambda: self._delete_channel() if hasattr(self, '_delete_channel') else None)
        
        # 显示菜单
        menu.exec(QtGui.QCursor.pos())
        
    def _show_help_menu(self):
        """显示帮助菜单"""
        menu = QtWidgets.QMenu(self)
        about_action = menu.addAction("关于")
        help_action = menu.addAction("使用帮助")
        check_update_action = menu.addAction("检查更新")
        feedback_action = menu.addAction("反馈问题")
        
        # 连接信号
        about_action.triggered.connect(self._show_about)
        
        # 显示菜单
        menu.exec(QtGui.QCursor.pos())
        
    def _show_playlist_context_menu(self, pos):
        """显示播放列表右键菜单"""
        if not hasattr(self.layout_manager.main_window, 'playlist_table'):
            return
        
        playlist_table = self.layout_manager.main_window.playlist_table
        # 检查是否有选中的行
        selected_rows = playlist_table.selectionModel().selectedRows()
        if not selected_rows:
            return
        
        menu = QtWidgets.QMenu(self)
        play_action = menu.addAction("播放")
        edit_action = menu.addAction("编辑频道")
        delete_action = menu.addAction("删除频道")
        menu.addSeparator()
        favorite_action = menu.addAction("添加到收藏")
        export_action = menu.addAction("导出频道")
        menu.addSeparator()
        copy_url_action = menu.addAction("复制播放地址")
        
        # 连接信号
        edit_action.triggered.connect(lambda: self._edit_channel() if hasattr(self, '_edit_channel') else None)
        delete_action.triggered.connect(lambda: self._delete_channel() if hasattr(self, '_delete_channel') else None)
        
        # 显示菜单
        menu.exec(playlist_table.mapToGlobal(pos))
            
    def keyPressEvent(self, event):
        """键盘事件 - ESC退出全屏"""
        if event.key() == QtCore.Qt.Key.Key_Escape:
            if self.isFullScreen():
                self.showNormal()
                self.btn_maximize.setText("□")
        super().keyPressEvent(event)
        
    def moveEvent(self, event):
        """窗口移动事件 - 更新所有独立窗口位置"""
        super().moveEvent(event)
        # 主窗口移动时，更新所有独立窗口位置
        if hasattr(self, 'layout_manager'):
            self.layout_manager._update_all_windows_position()
        # 更新展开按钮位置
        self._update_expand_button_positions()
        
    def resizeEvent(self, event):
        """窗口大小改变事件 - 更新所有独立窗口位置"""
        super().resizeEvent(event)
        # 主窗口大小改变时，更新所有独立窗口位置
        if hasattr(self, 'layout_manager'):
            self.layout_manager._update_all_windows_position()
        # 更新展开按钮位置
        self._update_expand_button_positions()
        # 更新悬浮面板位置
        if hasattr(self, 'layout_manager'):
            self.layout_manager._update_floating_panel_position()


def main():
    app = QtWidgets.QApplication(sys.argv)
    
    # 设置应用样式
    app.setStyle("Fusion")
    
    # 设置深色主题
    palette = QtGui.QPalette()
    palette.setColor(QtGui.QPalette.ColorRole.Window, QtGui.QColor(26, 26, 26))
    palette.setColor(QtGui.QPalette.ColorRole.WindowText, QtGui.QColor(255, 255, 255))
    palette.setColor(QtGui.QPalette.ColorRole.Base, QtGui.QColor(26, 26, 26))
    palette.setColor(QtGui.QPalette.ColorRole.AlternateBase, QtGui.QColor(45, 45, 45))
    palette.setColor(QtGui.QPalette.ColorRole.ToolTipBase, QtGui.QColor(255, 255, 255))
    palette.setColor(QtGui.QPalette.ColorRole.ToolTipText, QtGui.QColor(255, 255, 255))
    palette.setColor(QtGui.QPalette.ColorRole.Text, QtGui.QColor(255, 255, 255))
    palette.setColor(QtGui.QPalette.ColorRole.Button, QtGui.QColor(45, 45, 45))
    palette.setColor(QtGui.QPalette.ColorRole.ButtonText, QtGui.QColor(255, 255, 255))
    palette.setColor(QtGui.QPalette.ColorRole.Highlight, QtGui.QColor(0, 168, 232))
    app.setPalette(palette)
    
    # 创建并显示主窗口
    window = TestMainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
