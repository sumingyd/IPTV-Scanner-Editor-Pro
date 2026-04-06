"""
PotPlayer风格现代化播放器布局
主窗口采用左右布局，左侧视频播放，右侧播放列表
悬浮面板包含节目单、媒体信息和播放控制
"""

from PyQt6 import QtCore, QtWidgets, QtGui
from PyQt6.QtCore import Qt
from core.log_manager import global_logger


class PlayerLayout:
    """播放器布局管理器"""

    def __init__(self, main_window):
        self.main_window = main_window
        self.logger = global_logger
        self.ui_builder = None  # 将在后续设置

    def build_layout(self):
        """构建主窗口布局"""
        # 设置窗口标题和大小
        self.main_window.setWindowTitle("IPTV Pro")
        self.main_window.resize(1600, 900)

        # 创建中央部件
        central_widget = QtWidgets.QWidget()
        self.main_window.setCentralWidget(central_widget)

        # 主布局 - 只包含视频播放区域
        main_layout = QtWidgets.QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 视频播放区域（占据整个主窗口）
        self._setup_video_panel()
        main_layout.addWidget(self.main_window.video_frame)

        # 创建EPG节目单（独立窗口）
        self._setup_epg_panel()

        # 创建播放列表（独立窗口）
        self._setup_playlist_panel()

        # 创建悬浮控制面板（独立窗口）
        self._setup_floating_control_panel()

        # 保存原始宽度
        self.epg_original_width = 240
        self.epg_collapsed = False
        self.playlist_original_width = 400
        self.playlist_collapsed = False

        # 更新所有独立窗口的位置
        self._update_all_windows_position()

        # 菜单栏移到标题栏中，这里不创建系统菜单栏

    def _setup_epg_panel(self):
        """设置EPG节目表面板（独立窗口）"""
        # 创建EPG容器作为独立窗口
        self.epg_container = QtWidgets.QWidget()
        self.epg_container.setStyleSheet("""
            QWidget {
                background-color: #1a1a1a;
            }
        """)
        # 设置窗口标志，使其独立、无框（不置顶，避免覆盖标题栏）
        self.epg_container.setWindowFlags(
            QtCore.Qt.WindowType.FramelessWindowHint |
            QtCore.Qt.WindowType.Tool
        )
        epg_layout = QtWidgets.QVBoxLayout(self.epg_container)
        epg_layout.setContentsMargins(0, 0, 0, 0)
        epg_layout.setSpacing(0)

        # 标题栏（带收起按钮）
        self.main_window.epg_header = QtWidgets.QWidget()
        epg_header_layout = QtWidgets.QHBoxLayout(self.main_window.epg_header)
        epg_header_layout.setContentsMargins(5, 5, 5, 5)
        
        self.main_window.epg_collapse_btn = QtWidgets.QPushButton("◀")
        self.main_window.epg_collapse_btn.setFixedSize(24, 24)
        self.main_window.epg_collapse_btn.setStyleSheet("""
            QPushButton {
                background-color: #2d2d2d;
                color: #888;
                border: none;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover {
                color: #fff;
            }
        """)
        epg_header_layout.addWidget(self.main_window.epg_collapse_btn)
        
        epg_title_label = QtWidgets.QLabel("📅 节目单")
        epg_title_label.setStyleSheet("color: #fff; font-weight: bold; font-size: 12px;")
        epg_header_layout.addWidget(epg_title_label)
        epg_header_layout.addStretch()
        
        epg_layout.addWidget(self.main_window.epg_header)
        
        # EPG内容区域
        self.main_window.epg_content = QtWidgets.QWidget()
        epg_content_layout = QtWidgets.QVBoxLayout(self.main_window.epg_content)
        epg_content_layout.setContentsMargins(5, 0, 5, 5)
        epg_content_layout.setSpacing(5)
        
        # 当前频道信息
        self.main_window.current_epg_channel = QtWidgets.QLabel("CCTV-1 综合")
        self.main_window.current_epg_channel.setStyleSheet("""
            color: #fff; font-size: 13px; font-weight: bold;
            padding: 8px; background-color: #2d5a8a; border-radius: 4px;
        """)
        epg_content_layout.addWidget(self.main_window.current_epg_channel)
        
        # 日期选择器
        date_layout = QtWidgets.QHBoxLayout()
        self.main_window.epg_date_prev = QtWidgets.QPushButton("◀")
        self.main_window.epg_date_prev.setFixedSize(24, 24)
        self.main_window.epg_date_prev.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #888;
                border: none;
                font-size: 12px;
            }
            QPushButton:hover {
                color: #fff;
            }
        """)
        date_layout.addWidget(self.main_window.epg_date_prev)
        
        self.main_window.epg_date_label = QtWidgets.QLabel("今天 04/02")
        self.main_window.epg_date_label.setStyleSheet("color: #fff; font-size: 12px;")
        self.main_window.epg_date_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        date_layout.addWidget(self.main_window.epg_date_label)
        
        self.main_window.epg_date_next = QtWidgets.QPushButton("▶")
        self.main_window.epg_date_next.setFixedSize(24, 24)
        self.main_window.epg_date_next.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #888;
                border: none;
                font-size: 12px;
            }
            QPushButton:hover {
                color: #fff;
            }
        """)
        date_layout.addWidget(self.main_window.epg_date_next)
        
        epg_content_layout.addLayout(date_layout)
        
        # 节目列表（使用表格支持回看图标）
        self.main_window.epg_table = QtWidgets.QTableWidget()
        self.main_window.epg_table.setColumnCount(3)
        self.main_window.epg_table.setHorizontalHeaderLabels(["时间", "节目", ""])
        self.main_window.epg_table.verticalHeader().setVisible(False)
        self.main_window.epg_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.main_window.epg_table.setStyleSheet("""
            QTableWidget {
                background-color: #1a1a1a;
                border: none;
                color: #ccc;
            }
            QTableWidget::item {
                padding: 6px;
                border-bottom: 1px solid #333;
            }
            QTableWidget::item:selected {
                background-color: #2d5a8a;
            }
            QHeaderView::section {
                background-color: #252525;
                color: #888;
                padding: 6px;
                border: none;
                font-size: 11px;
            }
        """)
        self.main_window.epg_table.setColumnWidth(2, 30)
        self.main_window.epg_table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.main_window.epg_table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        
        # 示例节目（带回看支持）
        epg_programs = [
            ("18:00", "新闻联播", "已播", True),
            ("18:30", "天气预报", "已播", True),
            ("19:00", "焦点访谈", "已播", True),
            ("19:38", "电视剧:觉醒年代", "播放", False),
            ("20:30", "电视剧:觉醒年代", "待播", False),
            ("21:30", "晚间新闻", "待播", False),
            ("22:00", "星光大道", "待播", False),
        ]
        
        self.main_window.epg_table.setRowCount(len(epg_programs))
        for row, (time, program, status, can_rewind) in enumerate(epg_programs):
            # 时间
            time_item = QtWidgets.QTableWidgetItem(time)
            if status == "播放":
                time_item.setForeground(QtGui.QColor(76, 175, 80))
                font = time_item.font()
                font.setBold(True)
                time_item.setFont(font)
            elif status == "已播":
                time_item.setForeground(QtGui.QColor(136, 136, 136))
            self.main_window.epg_table.setItem(row, 0, time_item)
            
            # 节目名称
            program_item = QtWidgets.QTableWidgetItem(program)
            if status == "播放":
                program_item.setForeground(QtGui.QColor(76, 175, 80))
                font = program_item.font()
                font.setBold(True)
                program_item.setFont(font)
            elif status == "已播":
                program_item.setForeground(QtGui.QColor(136, 136, 136))
            self.main_window.epg_table.setItem(row, 1, program_item)
            
            # 回看图标
            if can_rewind:
                rewind_item = QtWidgets.QTableWidgetItem("⏪")
                rewind_item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                rewind_item.setToolTip("点击回看")
                self.main_window.epg_table.setItem(row, 2, rewind_item)
        
        epg_content_layout.addWidget(self.main_window.epg_table)
        
        epg_layout.addWidget(self.main_window.epg_content)
        
        # 显示EPG窗口
        self.epg_container.show()
        
        # 保存原始宽度
        self.epg_original_width = 240
        self.epg_collapsed = False

    def _setup_video_panel(self):
        """设置视频播放区域"""
        # 直接创建视频播放区域，不再使用容器
        self.main_window.video_frame = QtWidgets.QFrame()
        self.main_window.video_frame.setStyleSheet("background-color: #000000;")
        self.main_window.video_frame.setMinimumSize(640, 480)

    def _setup_playlist_panel(self):
        """设置播放列表面板（独立窗口）"""
        # 创建播放列表容器作为独立窗口
        self.playlist_container = QtWidgets.QWidget()
        self.playlist_container.setStyleSheet("""
            QWidget {
                background-color: #1a1a1a;
            }
        """)
        # 设置窗口标志，使其独立、无框（不置顶，避免覆盖标题栏）
        self.playlist_container.setWindowFlags(
            QtCore.Qt.WindowType.FramelessWindowHint |
            QtCore.Qt.WindowType.Tool
        )
        playlist_layout = QtWidgets.QVBoxLayout(self.playlist_container)
        playlist_layout.setContentsMargins(0, 0, 0, 0)
        playlist_layout.setSpacing(0)

        # 播放列表标题栏（带收起按钮）
        self.main_window.playlist_header = QtWidgets.QWidget()
        playlist_header_layout = QtWidgets.QHBoxLayout(self.main_window.playlist_header)
        playlist_header_layout.setContentsMargins(5, 5, 5, 5)

        self.main_window.playlist_collapse_btn = QtWidgets.QPushButton("▶")
        self.main_window.playlist_collapse_btn.setFixedSize(24, 24)
        self.main_window.playlist_collapse_btn.setStyleSheet("""
            QPushButton {
                background-color: #2d2d2d;
                color: #888;
                border: none;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover {
                color: #fff;
            }
        """)
        playlist_header_layout.addWidget(self.main_window.playlist_collapse_btn)

        header_label = QtWidgets.QLabel("📋 播放列表")
        header_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #fff;")
        playlist_header_layout.addWidget(header_label)
        playlist_header_layout.addStretch()

        # 搜索框
        self.main_window.playlist_search = QtWidgets.QLineEdit()
        self.main_window.playlist_search.setPlaceholderText("🔍 搜索...")
        self.main_window.playlist_search.setMaximumWidth(150)
        self.main_window.playlist_search.setStyleSheet("""
            QLineEdit {
                background-color: #2d2d2d;
                color: #fff;
                border: none;
                padding: 4px 8px;
                border-radius: 4px;
            }
        """)
        playlist_header_layout.addWidget(self.main_window.playlist_search)

        playlist_layout.addWidget(self.main_window.playlist_header)

        # 播放列表内容区域
        self.main_window.playlist_content = QtWidgets.QWidget()
        playlist_content_layout = QtWidgets.QVBoxLayout(self.main_window.playlist_content)
        playlist_content_layout.setContentsMargins(5, 0, 5, 5)
        playlist_content_layout.setSpacing(5)

        # 播放列表表格
        self.main_window.playlist_table = QtWidgets.QTableWidget()
        self.main_window.playlist_table.setColumnCount(3)
        self.main_window.playlist_table.setHorizontalHeaderLabels(["#", "", "频道信息"])
        self.main_window.playlist_table.verticalHeader().setVisible(False)
        self.main_window.playlist_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.main_window.playlist_table.setStyleSheet("""
            QTableWidget {
                background-color: #1a1a1a;
                border: none;
                color: #ffffff;
            }
            QTableWidget::item {
                padding: 4px;
                border-bottom: 1px solid #333;
            }
            QTableWidget::item:selected {
                background-color: #2d5a8a;
            }
            QHeaderView::section {
                background-color: #252525;
                color: #888;
                padding: 4px;
                border: none;
            }
        """)

        # 设置列宽
        self.main_window.playlist_table.setColumnWidth(0, 40)   # 序号
        self.main_window.playlist_table.setColumnWidth(1, 50)   # LOGO
        self.main_window.playlist_table.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.Stretch)  # 频道信息

        playlist_content_layout.addWidget(self.main_window.playlist_table)

        playlist_layout.addWidget(self.main_window.playlist_content)

        # 显示播放列表窗口
        self.playlist_container.show()

        # 保存原始宽度
        self.playlist_original_width = 480
        self.playlist_collapsed = False

    def _setup_floating_control_panel(self):
        """设置悬浮控制面板（独立窗口）"""
        # 创建悬浮面板作为独立窗口
        self.main_window.floating_panel = QtWidgets.QWidget()
        self.main_window.floating_panel.setStyleSheet("""
            QWidget {
                background-color: rgba(30, 30, 30, 0.95);
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
            }
        """)
        self.main_window.floating_panel.setFixedHeight(220)
        # 设置窗口标志，使其独立、无框、置顶
        self.main_window.floating_panel.setWindowFlags(
            QtCore.Qt.WindowType.FramelessWindowHint |
            QtCore.Qt.WindowType.WindowStaysOnTopHint |
            QtCore.Qt.WindowType.Tool |
            QtCore.Qt.WindowType.NoDropShadowWindowHint
        )
        self.main_window.floating_panel.hide()  # 默认隐藏

        # 悬浮面板布局
        panel_layout = QtWidgets.QVBoxLayout(self.main_window.floating_panel)
        panel_layout.setContentsMargins(15, 12, 15, 12)
        panel_layout.setSpacing(8)

        # 第一行：媒体信息（一排显示）
        top_layout = QtWidgets.QHBoxLayout()
        top_layout.setSpacing(12)
        
        # 媒体信息（一排显示）
        self.main_window.media_full_info = QtWidgets.QLabel(
            "📺 1920×1080  H.264  4.5Mbps  25fps  "
            "🔊 AAC  128kbps  2.0ch  48kHz  "
            "📡 延迟:45ms  丢包:0%  缓冲:100%  "
            "📦 TS  1.2Mbps  5.2GB/h  "
            "📐 4:3  🔄 逐行扫描  "
            "🎨 10bit  📊 码率波动:±0.2Mbps"
        )
        self.main_window.media_full_info.setStyleSheet("color: #ccc; font-size: 12px;")
        self.main_window.media_full_info.setWordWrap(True)
        top_layout.addWidget(self.main_window.media_full_info, stretch=1)

        panel_layout.addLayout(top_layout)

        # 分隔线
        separator1 = QtWidgets.QFrame()
        separator1.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        separator1.setStyleSheet("background-color: #444;")
        separator1.setFixedHeight(1)
        panel_layout.addWidget(separator1)

        # 第二行：LOGO + 当前节目信息（横向布局）
        program_info_layout = QtWidgets.QHBoxLayout()
        program_info_layout.setSpacing(20)

        # LOGO
        self.main_window.media_logo = QtWidgets.QLabel("📺")
        self.main_window.media_logo.setStyleSheet("color: #fff; font-size: 48px;")
        program_info_layout.addWidget(self.main_window.media_logo)

        # 节目信息 - 左边
        program_left = QtWidgets.QWidget()
        program_left_layout = QtWidgets.QVBoxLayout(program_left)
        program_left_layout.setContentsMargins(0, 0, 0, 0)
        program_left_layout.setSpacing(4)

        # 频道名称 + 当前节目
        self.main_window.media_channel_program = QtWidgets.QLabel("CCTV-1 综合  -  电视剧:觉醒年代")
        self.main_window.media_channel_program.setStyleSheet("color: #fff; font-size: 18px; font-weight: bold;")
        program_left_layout.addWidget(self.main_window.media_channel_program)

        program_info_layout.addWidget(program_left)
        
        # 节目描述 - 右边（增加示例文字，让它占满空间）
        self.main_window.media_program_desc = QtWidgets.QLabel("第一集：1915年，陈独秀创办《青年杂志》，倡导民主与科学，开启了新文化运动的先河。李大钊、鲁迅、胡适等知识分子积极参与，推动了中国思想文化的现代化进程。这部剧通过真实的历史事件和人物，展现了那个时代的精神风貌和思想碰撞。")
        self.main_window.media_program_desc.setStyleSheet("color: #888; font-size: 13px;")
        self.main_window.media_program_desc.setWordWrap(True)
        self.main_window.media_program_desc.setMinimumWidth(400)
        program_info_layout.addWidget(self.main_window.media_program_desc, stretch=1)

        program_info_layout.addStretch()

        panel_layout.addLayout(program_info_layout)

        # 分隔线
        separator2 = QtWidgets.QFrame()
        separator2.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        separator2.setStyleSheet("background-color: #444;")
        separator2.setFixedHeight(1)
        panel_layout.addWidget(separator2)

        # 第三行：播放控制
        control_layout = QtWidgets.QHBoxLayout()

        # 播放控制按钮
        self.main_window.btn_prev = QtWidgets.QPushButton("⏮️")
        self.main_window.btn_play_pause = QtWidgets.QPushButton("⏸️")
        self.main_window.btn_next = QtWidgets.QPushButton("⏭️")

        for btn in [self.main_window.btn_prev, self.main_window.btn_play_pause, self.main_window.btn_next]:
            btn.setFixedSize(40, 40)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    color: #fff;
                    border: none;
                    font-size: 20px;
                }
                QPushButton:hover {
                    color: #00a8e8;
                }
            """)

        control_layout.addWidget(self.main_window.btn_prev)
        control_layout.addWidget(self.main_window.btn_play_pause)
        control_layout.addWidget(self.main_window.btn_next)

        control_layout.addSpacing(20)

        # 进度条（可选）
        self.main_window.progress_widget = QtWidgets.QWidget()
        progress_layout = QtWidgets.QHBoxLayout(self.main_window.progress_widget)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        
        self.main_window.time_current = QtWidgets.QLabel("00:23:15")
        self.main_window.time_current.setStyleSheet("color: #888; font-size: 11px;")
        progress_layout.addWidget(self.main_window.time_current)
        
        self.main_window.progress_slider = QtWidgets.QSlider(Qt.Orientation.Horizontal)
        self.main_window.progress_slider.setValue(35)
        progress_layout.addWidget(self.main_window.progress_slider)
        
        self.main_window.time_total = QtWidgets.QLabel("--:--:--")
        self.main_window.time_total.setStyleSheet("color: #888; font-size: 11px;")
        progress_layout.addWidget(self.main_window.time_total)
        
        control_layout.addWidget(self.main_window.progress_widget, stretch=1)

        control_layout.addSpacing(20)

        # 音量控制
        self.main_window.btn_volume = QtWidgets.QPushButton("🔊")
        self.main_window.btn_volume.setFixedSize(30, 30)
        self.main_window.btn_volume.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #fff;
                border: none;
                font-size: 16px;
            }
        """)
        control_layout.addWidget(self.main_window.btn_volume)

        self.main_window.volume_slider = QtWidgets.QSlider(Qt.Orientation.Horizontal)
        self.main_window.volume_slider.setFixedWidth(80)
        self.main_window.volume_slider.setValue(100)
        control_layout.addWidget(self.main_window.volume_slider)

        control_layout.addSpacing(10)

        # 清晰度选择
        self.main_window.btn_quality = QtWidgets.QPushButton("📺 超清 ▼")
        self.main_window.btn_quality.setStyleSheet("""
            QPushButton {
                background-color: #2d2d2d;
                color: #fff;
                border: none;
                padding: 5px 10px;
                border-radius: 4px;
            }
        """)
        control_layout.addWidget(self.main_window.btn_quality)

        control_layout.addSpacing(10)

        # 全屏按钮
        self.main_window.btn_fullscreen = QtWidgets.QPushButton("⛶")
        self.main_window.btn_fullscreen.setFixedSize(40, 40)
        self.main_window.btn_fullscreen.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #fff;
                border: none;
                font-size: 18px;
            }
            QPushButton:hover {
                color: #00a8e8;
            }
        """)
        control_layout.addWidget(self.main_window.btn_fullscreen)

        panel_layout.addLayout(control_layout)

        # 设置悬浮面板位置
        self._update_floating_panel_position()

    def _update_all_windows_position(self):
        """更新所有独立窗口的位置"""
        # 获取主窗口尺寸
        window_rect = self.main_window.geometry()
        # 标题栏高度（假设为30px）
        titlebar_height = 30
        
        # 更新EPG窗口位置（从标题栏下方开始）
        if hasattr(self, 'epg_container') and not self.epg_collapsed:
            epg_width = self.epg_original_width
            epg_height = window_rect.height() - titlebar_height
            epg_x = window_rect.left()
            epg_y = window_rect.top() + titlebar_height
            self.epg_container.setGeometry(epg_x, epg_y, epg_width, epg_height)
            self.epg_container.show()
        elif hasattr(self, 'epg_container') and self.epg_collapsed:
            self.epg_container.hide()
        
        # 更新播放列表窗口位置（从标题栏下方开始）
        if hasattr(self, 'playlist_container') and not self.playlist_collapsed:
            playlist_width = self.playlist_original_width
            playlist_height = window_rect.height() - titlebar_height
            playlist_x = window_rect.right() - playlist_width
            playlist_y = window_rect.top() + titlebar_height
            self.playlist_container.setGeometry(playlist_x, playlist_y, playlist_width, playlist_height)
            self.playlist_container.show()
        elif hasattr(self, 'playlist_container') and self.playlist_collapsed:
            self.playlist_container.hide()
        
        # 更新悬浮面板位置
        self._update_floating_panel_position()

    def _update_floating_panel_position(self):
        """更新悬浮面板位置（独立窗口，距离底部有距离）"""
        if hasattr(self.main_window, 'floating_panel') and self.main_window.floating_panel.isVisible():
            # 获取主窗口尺寸
            window_rect = self.main_window.geometry()
            # 标题栏高度（假设为30px）
            titlebar_height = 30

            # 计算面板位置（距离底部30px，从标题栏下方开始）
            panel_width = window_rect.width() - 40
            panel_x = window_rect.left() + 20
            panel_y = window_rect.bottom() - self.main_window.floating_panel.height() - 30

            self.main_window.floating_panel.setGeometry(panel_x, panel_y, panel_width, self.main_window.floating_panel.height())
    
    def _update_recent_files_menu(self):
        """更新最近打开文件菜单"""
        from core.config_manager import ConfigManager
        
        # 清空当前菜单
        self.main_window.recent_menu.clear()
        
        # 加载最近打开的文件列表
        config_manager = ConfigManager()
        recent_files = config_manager.load_recent_files()
        
        if not recent_files:
            # 如果没有最近打开的文件，添加一个禁用的菜单项
            no_recent_action = QtGui.QAction("无最近打开的文件", self.main_window)
            no_recent_action.setEnabled(False)
            self.main_window.recent_menu.addAction(no_recent_action)
        else:
            # 添加最近打开的文件到菜单
            for file_path in recent_files:
                action = QtGui.QAction(file_path, self.main_window)
                action.triggered.connect(lambda checked, path=file_path: self._open_recent_file(path))
                self.main_window.recent_menu.addAction(action)
    
    def _open_recent_file(self, file_path):
        """打开最近打开的文件"""
        from core.log_manager import global_logger as logger
        
        try:
            # 加载文件内容
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 解析M3U内容
            if hasattr(self.main_window, 'model'):
                self.main_window.model.load_from_file(content)
            
            # 更新最近打开文件列表
            from core.config_manager import ConfigManager
            config_manager = ConfigManager()
            config_manager.add_recent_file(file_path)
            self._update_recent_files_menu()
            
            logger.info(f"成功打开最近文件: {file_path}")
            if hasattr(self.main_window, 'statusBar'):
                self.main_window.statusBar().showMessage(f"成功打开文件: {file_path}")
        except Exception as ex:
            logger.error(f"打开最近文件失败: {str(ex)}")
            if hasattr(self.main_window, 'statusBar'):
                self.main_window.statusBar().showMessage(f"打开文件失败: {str(ex)}")
    
    def _on_open_list(self):
        """打开列表文件"""
        from core.log_manager import global_logger as logger
        from core.config_manager import ConfigManager
        
        # 打开文件选择对话框
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self.main_window,
            "打开列表文件",
            "",
            "M3U文件 (*.m3u *.m3u8);;文本文件 (*.txt);;所有文件 (*.*)"
        )
        
        if file_path:
            try:
                # 加载文件内容
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # 解析M3U内容
                if hasattr(self.main_window, 'model'):
                    self.main_window.model.load_from_file(content)
                
                # 添加到最近打开文件列表
                config_manager = ConfigManager()
                config_manager.add_recent_file(file_path)
                self._update_recent_files_menu()
                
                logger.info(f"成功加载列表文件: {file_path}")
                if hasattr(self.main_window, 'statusBar'):
                    self.main_window.statusBar().showMessage(f"成功加载列表文件: {file_path}")
            except Exception as ex:
                logger.error(f"打开列表文件失败: {str(ex)}")
                if hasattr(self.main_window, 'statusBar'):
                    self.main_window.statusBar().showMessage(f"打开列表文件失败: {str(ex)}")
    
    def _on_save_as(self):
        """另存为"""
        from core.log_manager import global_logger as logger
        
        # 打开保存文件对话框
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self.main_window,
            "保存列表文件",
            "playlist.m3u",
            "M3U文件 (*.m3u);;M3U8文件 (*.m3u8);;文本文件 (*.txt);;所有文件 (*.*)"
        )
        
        if file_path:
            try:
                # 获取M3U内容
                if hasattr(self.main_window, 'model'):
                    content = self.main_window.model.to_m3u()
                else:
                    content = "#EXTM3U"
                
                if content:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    logger.info(f"成功保存列表文件: {file_path}")
                    if hasattr(self.main_window, 'statusBar'):
                        self.main_window.statusBar().showMessage(f"成功保存列表文件: {file_path}")
                else:
                    logger.warning("没有可保存的内容")
                    if hasattr(self.main_window, 'statusBar'):
                        self.main_window.statusBar().showMessage("没有可保存的内容")
            except Exception as ex:
                logger.error(f"保存列表文件失败: {str(ex)}")
                if hasattr(self.main_window, 'statusBar'):
                    self.main_window.statusBar().showMessage(f"保存列表文件失败: {str(ex)}")
    
    def _on_exit(self):
        """退出应用程序"""
        self.main_window.close()

    def _setup_menu_bar(self):
        """设置菜单栏"""
        menubar = self.main_window.menuBar()

        # 文件菜单
        file_menu = menubar.addMenu("📁 文件")

        open_action = QtGui.QAction("📂 打开列表", self.main_window)
        # 添加最近打开子菜单
        recent_menu = file_menu.addMenu("📋 最近打开")
        save_as_action = QtGui.QAction("💾 另存为", self.main_window)
        exit_action = QtGui.QAction("🚪 退出", self.main_window)

        file_menu.addAction(open_action)
        file_menu.addMenu(recent_menu)
        file_menu.addAction(save_as_action)
        file_menu.addSeparator()
        file_menu.addAction(exit_action)
        
        # 保存菜单动作引用
        self.main_window.recent_menu = recent_menu
        
        # 初始化最近打开文件菜单
        self._update_recent_files_menu()
        
        # 连接菜单动作
        open_action.triggered.connect(self._on_open_list)
        save_as_action.triggered.connect(self._on_save_as)
        exit_action.triggered.connect(self._on_exit)

        # 编辑菜单
        edit_menu = menubar.addMenu("✏️ 编辑")

        add_channel_action = QtGui.QAction("➕ 添加频道", self.main_window)
        edit_channel_action = QtGui.QAction("✏️ 编辑频道", self.main_window)
        delete_channel_action = QtGui.QAction("🗑️ 删除频道", self.main_window)
        find_replace_action = QtGui.QAction("🔍 查找替换", self.main_window)

        edit_menu.addAction(add_channel_action)
        edit_menu.addAction(edit_channel_action)
        edit_menu.addAction(delete_channel_action)
        edit_menu.addSeparator()
        edit_menu.addAction(find_replace_action)

        # 扫描菜单
        scan_menu = menubar.addMenu("📡 扫描")

        start_scan_action = QtGui.QAction("▶️ 开始扫描", self.main_window)
        pause_scan_action = QtGui.QAction("⏸️ 暂停扫描", self.main_window)
        stop_scan_action = QtGui.QAction("⏹️ 停止扫描", self.main_window)
        scan_settings_action = QtGui.QAction("⚙️ 扫描设置", self.main_window)

        scan_menu.addAction(start_scan_action)
        scan_menu.addAction(pause_scan_action)
        scan_menu.addAction(stop_scan_action)
        scan_menu.addSeparator()
        scan_menu.addAction(scan_settings_action)

        # 工具菜单
        tools_menu = menubar.addMenu("🛠️ 工具")

        validate_action = QtGui.QAction("✅ 检测有效性", self.main_window)
        sort_action = QtGui.QAction("📊 智能排序", self.main_window)
        mapping_action = QtGui.QAction("🗺️ 映射管理", self.main_window)
        epg_action = QtGui.QAction("📅 EPG设置", self.main_window)

        tools_menu.addAction(validate_action)
        tools_menu.addAction(sort_action)
        tools_menu.addSeparator()
        tools_menu.addAction(mapping_action)
        tools_menu.addAction(epg_action)

        # 视图菜单
        view_menu = menubar.addMenu("👁️ 视图")

        show_controls_action = QtGui.QAction("🎮 显示控制面板", self.main_window)
        show_controls_action.setCheckable(True)
        show_controls_action.setChecked(True)

        always_on_top_action = QtGui.QAction("📌 置顶窗口", self.main_window)
        always_on_top_action.setCheckable(True)

        fullscreen_action = QtGui.QAction("⛶ 全屏模式", self.main_window)

        view_menu.addAction(show_controls_action)
        view_menu.addAction(always_on_top_action)
        view_menu.addSeparator()
        view_menu.addAction(fullscreen_action)

        # 设置菜单
        settings_menu = menubar.addMenu("⚙️ 设置")

        network_action = QtGui.QAction("🌐 网络设置", self.main_window)
        player_action = QtGui.QAction("🎬 播放器设置", self.main_window)
        language_action = QtGui.QAction("🌐 语言", self.main_window)
        theme_action = QtGui.QAction("🎨 主题", self.main_window)

        settings_menu.addAction(network_action)
        settings_menu.addAction(player_action)
        settings_menu.addSeparator()
        settings_menu.addAction(language_action)
        settings_menu.addAction(theme_action)

        # 帮助菜单
        help_menu = menubar.addMenu("❓ 帮助")

        docs_action = QtGui.QAction("📖 使用文档", self.main_window)
        update_action = QtGui.QAction("🔄 检查更新", self.main_window)
        about_action = QtGui.QAction("ℹ️ 关于", self.main_window)

        help_menu.addAction(docs_action)
        help_menu.addAction(update_action)
        help_menu.addSeparator()
        help_menu.addAction(about_action)

        # 保存菜单动作引用
        self.main_window.open_action = open_action
        self.main_window.save_as_action = save_as_action
        self.main_window.exit_action = exit_action
        self.main_window.add_channel_action = add_channel_action
        self.main_window.edit_channel_action = edit_channel_action
        self.main_window.delete_channel_action = delete_channel_action
        self.main_window.find_replace_action = find_replace_action
        self.main_window.start_scan_action = start_scan_action
        self.main_window.pause_scan_action = pause_scan_action
        self.main_window.stop_scan_action = stop_scan_action
        self.main_window.scan_settings_action = scan_settings_action
        self.main_window.validate_action = validate_action
        self.main_window.sort_action = sort_action
        self.main_window.mapping_action = mapping_action
        self.main_window.epg_action = epg_action
        self.main_window.show_controls_action = show_controls_action
        self.main_window.always_on_top_action = always_on_top_action
        self.main_window.fullscreen_action = fullscreen_action
        self.main_window.network_action = network_action
        self.main_window.player_action = player_action
        self.main_window.language_action = language_action
        self.main_window.theme_action = theme_action
        self.main_window.docs_action = docs_action
        self.main_window.update_action = update_action
        self.main_window.about_action = about_action
