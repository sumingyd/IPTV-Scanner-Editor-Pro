import asyncio
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt
from channel_model import ChannelListModel
from styles import AppStyles
from pathlib import Path
from log_manager import LogManager

class UIBuilder:
    def __init__(self, main_window):
        self.main_window = main_window
        self.logger = LogManager()
        self._ui_initialized = False
        self._model_initialized = False

    def build_ui(self):
        if not self._ui_initialized:
            self.logger.info("开始构建UI界面")
            self._init_ui()
            self._setup_toolbar()
            self.logger.info("UI界面构建完成")
            self._ui_initialized = True

    def _setup_channel_list(self, parent: QtWidgets.QSplitter) -> None:  
        """配置频道列表"""
        if not self._model_initialized:
            self.logger.info("初始化频道列表")
            self._model_initialized = True

    def _init_ui(self):
        """初始化用户界面"""
        self.logger.info("初始化主窗口UI")
        self.main_window.setWindowTitle("IPTV Scanner Editor Pro / IPTV 专业扫描编辑工具")
        
        # 加载保存的窗口布局
        width, height, dividers = self.main_window.config.load_window_layout()
        self.main_window.resize(width, height)
        
        # 连接窗口大小变化信号
        self.main_window.resizeEvent = lambda e: self._on_window_resize(e)
        
        self.main_window.setStyleSheet(AppStyles.main_window_style())
        
        # 主布局
        main_widget = QtWidgets.QWidget()
        self.main_window.setCentralWidget(main_widget)
        main_layout = QtWidgets.QHBoxLayout(main_widget)
        self._init_splitters()
        main_layout.addWidget(self.main_window.main_splitter)

        # 强制应用布局设置
        if dividers and len(dividers) >= 8:
            self.logger.info(f"恢复分割器布局: {dividers}")
            self.main_window.main_splitter.setSizes(dividers[:2])
            self.main_window.left_splitter.setSizes(dividers[2:4])
            self.main_window.right_splitter.setSizes(dividers[4:6])
            self.main_window.h_splitter.setSizes(dividers[6:8])

        # 状态栏
        status_bar = self.main_window.statusBar()
        status_bar.show()
        status_bar.setStyleSheet(AppStyles.statusbar_style())
        # 状态栏统计信息
        self.main_window.scan_status_label = QtWidgets.QLabel("扫描: 0/0")
        self.main_window.validate_status_label = QtWidgets.QLabel("检测: 0/0")
        status_bar.addPermanentWidget(self.main_window.scan_status_label)
        status_bar.addPermanentWidget(self.main_window.validate_status_label)
        
        self.main_window.progress_indicator = QtWidgets.QProgressBar()
        self.main_window.progress_indicator.setRange(0, 0)
        self.main_window.progress_indicator.setTextVisible(False)
        self.main_window.progress_indicator.setFixedWidth(120)
        self.main_window.progress_indicator.setStyleSheet(AppStyles.progress_style())
        self.main_window.progress_indicator.hide()
        status_bar.addPermanentWidget(self.main_window.progress_indicator)

    def _on_window_resize(self, event):
        """处理窗口大小变化事件"""
        try:
            size = self.main_window.size()
            # 保存当前分割器状态
            dividers = [
                *self.main_window.main_splitter.sizes(),
                *self.main_window.left_splitter.sizes(),
                *self.main_window.right_splitter.sizes(),
                *self.main_window.h_splitter.sizes()
            ]
            
            # 如果EPG面板是收起状态，强制保持右侧收起
            if not self.main_window.epg_toggle_btn.isChecked():
                self.main_window.main_splitter.setSizes([size.width(), 0])
            
            # 保存窗口布局
            self.main_window.config.save_window_layout(size.width(), size.height(), dividers)
            event.accept()
            
            # 强制更新布局
            QtCore.QTimer.singleShot(50, lambda: [
                self.main_window.main_splitter.update(),
                self.main_window.main_splitter.updateGeometry()
            ])
        except Exception as e:
            self.logger.error(f"窗口大小变化处理错误: {str(e)}")

    def _init_splitters(self):
        """初始化所有分隔条控件"""
        # 加载保存的分隔条位置
        _, _, dividers = self.main_window.config.load_window_layout()
        
        # 主水平分割器（左右布局）
        self.main_window.main_splitter = QtWidgets.QSplitter(Qt.Orientation.Horizontal)
        self.main_window.main_splitter.setChildrenCollapsible(True)  # 允许子部件收起
        self.main_window.main_splitter.setHandleWidth(10)  # 设置足够大的手柄宽度
        self.main_window.main_splitter.setOpaqueResize(True)  # 实时更新分割器位置
        self._setup_custom_splitter(self.main_window.main_splitter)
        
        # 仅在未加载保存布局时设置默认值
        if not (dividers and len(dividers) >= 8):
            # 设置更合理的默认尺寸(基于窗口当前大小)
            width = self.main_window.width()
            height = self.main_window.height()
            self.main_window.main_splitter.setSizes([int(width*0.7), int(width*0.3)])
        
        # 左侧垂直分割器（扫描面板 + 频道列表）
        self.main_window.left_splitter = QtWidgets.QSplitter(Qt.Orientation.Vertical) 
        self._setup_custom_splitter(self.main_window.left_splitter)
        self._setup_scan_panel(self.main_window.left_splitter)
        self._setup_channel_list(self.main_window.left_splitter)

        # 右侧垂直分割器（播放器 + 底部编辑区）
        self.main_window.right_splitter = QtWidgets.QSplitter(Qt.Orientation.Vertical)
        self._setup_custom_splitter(self.main_window.right_splitter)
        self._setup_player_panel(self.main_window.right_splitter)
        
        # 底部水平分割器（编辑面板 + 匹配面板）
        bottom_container = QtWidgets.QWidget()
        bottom_container.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding
        )
        bottom_layout = QtWidgets.QHBoxLayout(bottom_container)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        
        self.main_window.h_splitter = QtWidgets.QSplitter(Qt.Orientation.Horizontal)
        self._setup_custom_splitter(self.main_window.h_splitter)
        self._setup_edit_panel(self.main_window.h_splitter)
        self._setup_match_panel(self.main_window.h_splitter)
        bottom_layout.addWidget(self.main_window.h_splitter)
        self.main_window.right_splitter.addWidget(bottom_container)

        # 组装主界面
        self.main_window.main_splitter.addWidget(self.main_window.left_splitter)
        self.main_window.main_splitter.addWidget(self.main_window.right_splitter)

        # 加载保存的分隔条位置
        _, _, dividers = self.main_window.config.load_window_layout()
        if dividers and len(dividers) >= 8:
            self.main_window.main_splitter.setSizes(dividers[:2])
            self.main_window.left_splitter.setSizes(dividers[2:4])
            self.main_window.right_splitter.setSizes(dividers[4:6])
            self.main_window.h_splitter.setSizes(dividers[6:8])
        else:
            # 设置更合理的默认尺寸(基于窗口当前大小)
            width = self.main_window.width()
            height = self.main_window.height()
            self.main_window.main_splitter.setSizes([int(width*0.4), int(width*0.6)])
            self.main_window.left_splitter.setSizes([int(height*0.4), int(height*0.6)])
            self.main_window.right_splitter.setSizes([int(height*0.7), int(height*0.3)])
            self.main_window.h_splitter.setSizes([int(width*0.5), int(width*0.5)])

    def _setup_custom_splitter(self, splitter):
        splitter.setChildrenCollapsible(False)
        
        # 必须设置足够大的handle宽度
        handle_size = 10
        splitter.setHandleWidth(handle_size)
        
        # 延迟设置确保splitter已初始化
        QtCore.QTimer.singleShot(100, lambda: self._install_handle(splitter))

    def _install_handle(self, splitter):
        if splitter.count() < 2:
            return
            
        handle = splitter.handle(1)
        handle.setStyleSheet("background: transparent;")
        
        # 创建并添加自定义手柄
        custom_handle = AndroidSplitterHandle(splitter.orientation())
        
        # 使用布局确保填充
        layout = QtWidgets.QHBoxLayout(handle) if splitter.orientation() == Qt.Orientation.Horizontal \
                else QtWidgets.QVBoxLayout(handle)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(custom_handle)
        
        # 连接事件
        custom_handle.mousePressEvent = lambda e: self._start_drag(splitter, e)
        custom_handle.mouseMoveEvent = lambda e: self._do_drag(splitter, e)

    def _start_drag(self, splitter, event):
        """开始拖动分隔条"""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = event.globalPosition().toPoint()
            self._drag_splitter = splitter
            self._drag_start_sizes = splitter.sizes()
        else:
            event.ignore()

    def _do_drag(self, splitter, event):
        """处理拖动分隔条"""
        if not hasattr(self, '_drag_start_pos') or not self._drag_start_pos:
            return
            
        if event.buttons() & Qt.MouseButton.LeftButton:
            new_pos = event.globalPosition().toPoint()
            delta = new_pos - self._drag_start_pos
            
            # 计算新尺寸
            sizes = self._drag_start_sizes.copy()
            total = sum(sizes)
            
            if splitter.orientation() == Qt.Orientation.Horizontal:
                sizes[0] = max(50, min(total-50, sizes[0] + delta.x()))
                sizes[1] = total - sizes[0]
            else:
                sizes[0] = max(50, min(total-50, sizes[0] + delta.y()))
                sizes[1] = total - sizes[0]
            
            splitter.setSizes(sizes)
            
            # 保存分隔条位置
            size = self.main_window.size()
            dividers = [
                *self.main_window.main_splitter.sizes(),
                *self.main_window.left_splitter.sizes(),
                *self.main_window.right_splitter.sizes(),
                *self.main_window.h_splitter.sizes()
            ]
            self.main_window.config.save_window_layout(size.width(), size.height(), dividers)
        else:
            self._drag_start_pos = None

    def _setup_player_panel(self, parent: QtWidgets.QSplitter) -> None:
        """配置播放器面板"""
        self.logger.info("初始化播放器面板")
        player_group = QtWidgets.QGroupBox("视频播放")
        player_layout = QtWidgets.QHBoxLayout()
        player_layout.setContentsMargins(2, 2, 2, 2)
        player_layout.setSpacing(5)
        
        # 左侧播放器区域 (占3/4宽度)
        player_left = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout()
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        # 播放器主体
        self.main_window.player = QtWidgets.QWidget()
        left_layout.addWidget(self.main_window.player, stretch=10)  # 大部分空间给播放器

        # 控制按钮区域
        control_container = QtWidgets.QWidget()
        control_layout = QtWidgets.QVBoxLayout()
        control_layout.setContentsMargins(0, 5, 0, 5)
        
        # 播放/停止按钮行
        btn_row = QtWidgets.QHBoxLayout()
        self.main_window.pause_btn = QtWidgets.QPushButton("播放")
        self.main_window.pause_btn.setStyleSheet(AppStyles.button_style(active=True))
        self.main_window.stop_btn = QtWidgets.QPushButton("停止")
        self.main_window.stop_btn.setStyleSheet(AppStyles.button_style(active=False))
        self.main_window.stop_btn.setEnabled(False)
        btn_row.addWidget(self.main_window.pause_btn)
        btn_row.addWidget(self.main_window.stop_btn)
        
        # 音量控制行
        volume_row = QtWidgets.QHBoxLayout()
        self.main_window.volume_slider = QtWidgets.QSlider(Qt.Orientation.Horizontal)
        self.main_window.volume_slider.setRange(0, 100)
        self.main_window.volume_slider.setValue(50)
        volume_row.addWidget(QtWidgets.QLabel("音量："))
        volume_row.addWidget(self.main_window.volume_slider)
        
        # 添加到控制区域
        control_layout.addLayout(btn_row)
        control_layout.addLayout(volume_row)
        control_container.setLayout(control_layout)
        
        # 将控制区域添加到左侧布局
        left_layout.addWidget(control_container, stretch=1)
        player_left.setLayout(left_layout)
        player_layout.addWidget(player_left, stretch=3)  # 左侧占3/4
        
        # 右侧EPG节目单区域 (独立布局)
        self.main_window.epg_panel = QtWidgets.QWidget()
        epg_layout = QtWidgets.QVBoxLayout()
        epg_layout.setContentsMargins(0, 0, 0, 0)
        epg_layout.setSpacing(0)
        
        # EPG容器(包含标题和内容)
        self.main_window.epg_container = QtWidgets.QWidget()
        self.main_window.epg_container.setLayout(QtWidgets.QVBoxLayout())
        self.main_window.epg_container.layout().setContentsMargins(0, 0, 0, 0)
        
        # 标题栏(仅包含标题)
        self.main_window.epg_header = QtWidgets.QWidget()
        header_layout = QtWidgets.QHBoxLayout(self.main_window.epg_header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        self.main_window.epg_title = QtWidgets.QLabel("当前节目单")
        self.main_window.epg_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(self.main_window.epg_title)
        
        # EPG内容区域
        self.main_window.epg_content = QtWidgets.QScrollArea()
        self.main_window.epg_content.setWidgetResizable(True)
        self.main_window.epg_content.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding
        )
        
        # 创建EPG时间线控件
        self.main_window.epg_timeline = QtWidgets.QScrollArea()
        self.main_window.epg_timeline.setWidgetResizable(True)
        
        # 添加标题和内容到容器
        self.main_window.epg_container.layout().addWidget(self.main_window.epg_header)
        self.main_window.epg_container.layout().addWidget(self.main_window.epg_content)
        
        # 将收起按钮移到播放器控制区域
        self.main_window.epg_toggle_btn = QtWidgets.QPushButton("◀")
        self.main_window.epg_toggle_btn.setFixedWidth(20)
        self.main_window.epg_toggle_btn.setCheckable(True)
        self.main_window.epg_toggle_btn.setChecked(True)
        
        # 添加到控制按钮行
        btn_row.addWidget(self.main_window.epg_toggle_btn)
        
        # 初始化EPG面板状态(默认展开)
        self._toggle_epg_panel(True)
        
        # 连接收起按钮信号
        self.main_window.epg_toggle_btn.toggled.connect(self._toggle_epg_panel)
        
        epg_layout.addWidget(self.main_window.epg_container, stretch=1)
        self.main_window.epg_panel.setLayout(epg_layout)
        
        # 使用独立的布局管理EPG面板
        player_layout.addWidget(self.main_window.epg_panel)
        
        player_group.setLayout(player_layout)
        parent.addWidget(player_group)

    def _setup_edit_panel(self, parent: QtWidgets.QSplitter) -> None:  
        """配置编辑面板"""
        edit_group = QtWidgets.QGroupBox("频道编辑")
        edit_layout = QtWidgets.QFormLayout()
        edit_layout.setRowWrapPolicy(QtWidgets.QFormLayout.RowWrapPolicy.WrapAllRows)
        edit_layout.setVerticalSpacing(5)
        edit_layout.setHorizontalSpacing(5)
        edit_layout.setContentsMargins(10, 15, 10, 15)

        # 频道名称输入(带自动补全)
        self.main_window.name_edit = QtWidgets.QLineEdit()
        self.main_window.name_edit.setMinimumHeight(32)
        self.main_window.name_edit.setPlaceholderText("输入频道名称...")
        
        # 名称自动补全(使用EPG频道名)
        name_completer = QtWidgets.QCompleter(self.main_window.epg_manager.get_channel_names())
        name_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        name_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.main_window.name_edit.setCompleter(name_completer)
        
        # 编辑框载入时自动全选文本
        self.main_window.name_edit.focusInEvent = self._handle_name_edit_focus
        
        # 回车键处理
        self.main_window.name_edit.returnPressed.connect(self._handle_enter_press)

        # 分组选择(带自动补全)
        self.main_window.group_combo = QtWidgets.QComboBox()
        self.main_window.group_combo.setMinimumHeight(32)
        self.main_window.group_combo.setEditable(True)
        group_completer = QtWidgets.QCompleter()
        group_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        group_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.main_window.group_combo.setCompleter(group_completer)

        # EPG匹配状态显示
        self.main_window.epg_match_label = QtWidgets.QLabel("EPG状态: 未匹配")
        self.main_window.epg_match_label.setStyleSheet("font-weight: bold;")
        
        # 保存按钮 - 作为窗口属性
        self.main_window.save_channel_btn = QtWidgets.QPushButton("保存修改")
        self.main_window.save_channel_btn.setObjectName("save_channel_btn")
        self.main_window.save_channel_btn.setMinimumHeight(36)
        self.main_window.save_channel_btn.setStyleSheet(AppStyles.button_style(active=True))
        self.main_window.save_channel_btn.setEnabled(True)
        
        # 文本变化时更新按钮状态
        self.main_window.name_edit.textChanged.connect(self._update_save_button_state)

        # 布局
        edit_layout.addRow("频道名称：", self.main_window.name_edit)
        edit_layout.addRow("分组分类：", self.main_window.group_combo)
        edit_layout.addRow(self.main_window.epg_match_label)
        edit_layout.addRow(QtWidgets.QLabel())
        edit_layout.addRow(self.main_window.save_channel_btn)

        edit_group.setLayout(edit_layout)
        parent.addWidget(edit_group)

    def _setup_match_panel(self, parent):
        """配置智能匹配面板"""
        match_group = QtWidgets.QGroupBox("智能匹配")
        layout = QtWidgets.QVBoxLayout()
        
        self._setup_match_buttons(layout)
        self._setup_match_progress(layout)
        self._setup_match_options(layout)
        
        match_group.setLayout(layout)
        parent.addWidget(match_group)

    def _setup_match_buttons(self, layout):
        """设置匹配操作按钮"""
        button_layout = QtWidgets.QHBoxLayout()
        
        # 加载旧列表按钮
        self.main_window.btn_load_old = QtWidgets.QPushButton("加载旧列表")
        self.main_window.btn_load_old.setStyleSheet(AppStyles.button_style(active=True))
        
        # 执行匹配按钮
        self.main_window.btn_match = QtWidgets.QPushButton("执行自动匹配")
        self.main_window.btn_match.setStyleSheet(AppStyles.button_style(active=False))
        self.main_window.btn_match.setEnabled(False)
        
        button_layout.addWidget(self.main_window.btn_load_old)
        button_layout.addWidget(self.main_window.btn_match)
        layout.addLayout(button_layout)

    def _setup_match_progress(self, layout):
        """设置匹配进度显示"""
        # 匹配进度标签
        layout.addWidget(QtWidgets.QLabel("匹配进度:"))
        
        # 进度条
        self.main_window.match_progress = QtWidgets.QProgressBar()
        self.main_window.match_progress.setTextVisible(True)
        self.main_window.match_progress.setStyleSheet(AppStyles.progress_style())
        layout.addWidget(self.main_window.match_progress)
        
        # 状态标签
        self.main_window.match_status = QtWidgets.QLabel("匹配功能未就绪 - 请先加载旧列表")
        self.main_window.match_status.setStyleSheet("color: #666; font-weight: bold;")
        layout.addWidget(self.main_window.match_status)
        
        layout.addStretch()

    def _setup_match_options(self, layout):
        """设置匹配高级选项"""
        # EPG覆盖选项
        self.main_window.cb_override_epg = QtWidgets.QCheckBox("EPG不匹配时强制覆盖")
        layout.addWidget(self.main_window.cb_override_epg)
        
        # 自动保存选项
        self.main_window.cb_auto_save = QtWidgets.QCheckBox("匹配后自动保存")
        layout.addWidget(self.main_window.cb_auto_save)

    def _setup_scan_panel(self, parent: QtWidgets.QSplitter) -> None:
        """配置扫描面板"""
        self.logger.info("初始化扫描面板")
        scan_group = QtWidgets.QGroupBox("扫描设置")
        scan_layout = QtWidgets.QFormLayout()

        self.main_window.ip_range_input = QtWidgets.QLineEdit()
        self.main_window.scan_progress = QtWidgets.QProgressBar()
        self.main_window.scan_progress.setStyleSheet(AppStyles.progress_style())

        # 超时时间设置
        timeout_layout = QtWidgets.QHBoxLayout()
        timeout_label = QtWidgets.QLabel("设置扫描超时时间（秒）")
        timeout_layout.addWidget(timeout_label)
        self.main_window.timeout_input = QtWidgets.QSpinBox()
        self.main_window.timeout_input.setRange(1, 60)
        self.main_window.timeout_input.setValue(10)
        self.main_window.timeout_input.setSuffix(" 秒")
        timeout_layout.addWidget(self.main_window.timeout_input)
        self.main_window.timeout_input.valueChanged.connect(
            lambda: self.main_window.config.save_network_settings(
                self.main_window.ip_range_input.text(),
                self.main_window.timeout_input.value(),
                self.main_window.thread_count_input.value(),
                self.main_window.user_agent_input.text(),
                self.main_window.referer_input.text()
            )
        )
        
        # 线程数设置
        thread_layout = QtWidgets.QHBoxLayout()
        thread_label = QtWidgets.QLabel("设置扫描使用的线程数量")
        thread_layout.addWidget(thread_label)
        self.main_window.thread_count_input = QtWidgets.QSpinBox()
        self.main_window.thread_count_input.setRange(1, 100)
        self.main_window.thread_count_input.setValue(10)
        thread_layout.addWidget(self.main_window.thread_count_input)
        self.main_window.thread_count_input.valueChanged.connect(
            lambda: self.main_window.config.save_network_settings(
                self.main_window.ip_range_input.text(),
                self.main_window.timeout_input.value(),
                self.main_window.thread_count_input.value(),
                self.main_window.user_agent_input.text(),
                self.main_window.referer_input.text()
            )
        )

        # User-Agent设置
        user_agent_layout = QtWidgets.QHBoxLayout()
        user_agent_label = QtWidgets.QLabel("User-Agent:")
        user_agent_layout.addWidget(user_agent_label)
        self.main_window.user_agent_input = QtWidgets.QLineEdit()
        self.main_window.user_agent_input.setPlaceholderText("可选，留空使用默认")
        user_agent_layout.addWidget(self.main_window.user_agent_input)
        self.main_window.user_agent_input.textChanged.connect(
            lambda: self.main_window.config.save_network_settings(
                self.main_window.ip_range_input.text(),
                self.main_window.timeout_input.value(),
                self.main_window.thread_count_input.value(),
                self.main_window.user_agent_input.text(),
                self.main_window.referer_input.text()
            )
        )

        # Referer设置
        referer_layout = QtWidgets.QHBoxLayout()
        referer_label = QtWidgets.QLabel("Referer:")
        referer_layout.addWidget(referer_label)
        self.main_window.referer_input = QtWidgets.QLineEdit()
        self.main_window.referer_input.setPlaceholderText("可选，留空不使用")
        referer_layout.addWidget(self.main_window.referer_input)
        self.main_window.referer_input.textChanged.connect(
            lambda: self.main_window.config.save_network_settings(
                self.main_window.ip_range_input.text(),
                self.main_window.timeout_input.value(),
                self.main_window.thread_count_input.value(),
                self.main_window.user_agent_input.text(),
                self.main_window.referer_input.text()
            )
        )

        # 扫描控制按钮
        self.main_window.scan_btn = QtWidgets.QPushButton("完整扫描")
        self.main_window.scan_btn.setStyleSheet(AppStyles.button_style(active=True))
        
        # 扫描统计信息
        self.main_window.detailed_stats_label = QtWidgets.QLabel("总频道: 0 | 有效: 0 | 无效: 0 | 耗时: 0s")
        self.main_window.detailed_stats_label.setStyleSheet(AppStyles.status_label_style())

        # 使用网格布局让按钮和统计信息并排显示
        button_stats_layout = QtWidgets.QGridLayout()
        button_stats_layout.addWidget(self.main_window.scan_btn, 0, 0, 1, 2)
        button_stats_layout.addWidget(self.main_window.detailed_stats_label, 1, 0, 1, 2)
        
        button_stats_layout.setColumnStretch(0, 1)
        button_stats_layout.setColumnStretch(1, 1)

        scan_layout.addRow("地址格式：", QtWidgets.QLabel("示例：http://192.168.1.1:1234/rtp/10.10.[1-20].[1-20]:5002   [1-20]表示范围"))
        scan_layout.addRow("输入地址：", self.main_window.ip_range_input)
        scan_layout.addRow("超时时间：", timeout_layout)
        scan_layout.addRow("线程数：", thread_layout)
        scan_layout.addRow("User-Agent：", user_agent_layout)
        scan_layout.addRow("Referer：", referer_layout)
        scan_layout.addRow("进度：", self.main_window.scan_progress)
        scan_layout.addRow(button_stats_layout)

        scan_group.setLayout(scan_layout)
        parent.addWidget(scan_group)

    def _setup_channel_list(self, parent: QtWidgets.QSplitter) -> None:  
        """配置频道列表"""
        self.logger.info("初始化频道列表")
        list_group = QtWidgets.QGroupBox("频道列表")
        list_layout = QtWidgets.QVBoxLayout()

        # 工具栏
        toolbar = QtWidgets.QHBoxLayout()
        
        # 有效性检测按钮
        self.main_window.btn_validate = QtWidgets.QPushButton("检测有效性")
        self.main_window.btn_validate.setStyleSheet(AppStyles.button_style(active=True))
        
        # 隐藏无效项按钮
        self.main_window.btn_hide_invalid = QtWidgets.QPushButton("隐藏无效项")
        self.main_window.btn_hide_invalid.setStyleSheet(AppStyles.button_style(active=False))
        self.main_window.btn_hide_invalid.setEnabled(False)
        
        # 检测统计标签
        self.main_window.validate_stats_label = QtWidgets.QLabel("请先加载列表")
        self.main_window.validate_stats_label.setStyleSheet(AppStyles.status_label_style())
        
        toolbar.addWidget(self.main_window.btn_validate)
        toolbar.addWidget(self.main_window.btn_hide_invalid)
        toolbar.addWidget(self.main_window.validate_stats_label)
        toolbar.addStretch()
        list_layout.addLayout(toolbar)

        # 频道列表视图
        self.main_window.channel_list = QtWidgets.QTableView()
        self.main_window.channel_list.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.main_window.channel_list.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.main_window.channel_list.horizontalHeader().setStretchLastSection(True)
        self.main_window.channel_list.verticalHeader().setVisible(False)
        self.main_window.model = ChannelListModel()
        self.main_window.channel_list.setModel(self.main_window.model)
        self.main_window.channel_list.setStyleSheet(AppStyles.list_style())
        
        # 启用拖放排序功能
        self.main_window.channel_list.setDragEnabled(True)
        self.main_window.channel_list.setAcceptDrops(True)
        self.main_window.channel_list.setDragDropOverwriteMode(False)
        self.main_window.channel_list.setDragDropMode(QtWidgets.QAbstractItemView.DragDropMode.InternalMove)
        self.main_window.channel_list.setDefaultDropAction(QtCore.Qt.DropAction.MoveAction)
        
        # 添加右键菜单
        self.main_window.channel_list.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.main_window.channel_list.customContextMenuRequested.connect(self._show_channel_context_menu)
        
        list_layout.addWidget(self.main_window.channel_list)
        list_group.setLayout(list_layout)
        parent.addWidget(list_group)

    def _update_save_button_state(self):
        """更新保存按钮状态"""
        has_text = bool(self.main_window.name_edit.text())
        self.main_window.save_channel_btn.setEnabled(has_text)
        self.main_window.save_channel_btn.setStyleSheet(
            AppStyles.button_style(active=has_text)
        )

    def _handle_enter_press(self):
        """处理回车键按下事件"""
        if self.main_window.save_channel_btn.isEnabled():
            # 模拟点击保存按钮
            self.main_window.save_channel_btn.click()
            
            # 重新初始化自动补全
            name_completer = QtWidgets.QCompleter(self.main_window.epg_manager.get_channel_names())
            name_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            name_completer.setFilterMode(Qt.MatchFlag.MatchContains)
            self.main_window.name_edit.setCompleter(name_completer)
            
            # 延迟执行导航
            QtCore.QTimer.singleShot(100, self._navigate_to_next_channel)

    def _handle_name_edit_focus(self, event):
        """处理编辑框焦点事件"""
        QtWidgets.QLineEdit.focusInEvent(self.main_window.name_edit, event)
        self.main_window.name_edit.selectAll()

    def _navigate_to_next_channel(self):
        """导航到下一个频道并自动播放"""
        selection = self.main_window.channel_list.selectionModel()
        if not selection.hasSelection():
            return
            
        current_row = selection.currentIndex().row()
        row_count = self.main_window.model.rowCount()
        
        # 导航到下一行
        if current_row < row_count - 1:
            next_index = self.main_window.model.index(current_row + 1, 0)
            self.main_window.channel_list.setCurrentIndex(next_index)
            self.main_window.channel_list.selectRow(current_row + 1)
            # 载入频道名并自动全选
            self.main_window.name_edit.setText(self.main_window.model.data(next_index))
            self.main_window.name_edit.selectAll()
            # 重新设置自动补全数据源
            name_completer = QtWidgets.QCompleter(self.main_window.epg_manager.get_channel_names())
            name_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            name_completer.setFilterMode(Qt.MatchFlag.MatchContains)
            self.main_window.name_edit.setCompleter(name_completer)
            # 播放当前选中的频道
            current_index = self.main_window.channel_list.currentIndex()
            channel_data = {
                'url': self.main_window.model.data(self.main_window.model.index(current_index.row(), 2)),  # URL在第2列
                'name': self.main_window.model.data(current_index)
            }
            self.main_window.player_controller.play_channel(channel_data)
            
            # 延迟执行高亮，确保EPG节目单已加载
            QtCore.QTimer.singleShot(500, lambda: self._highlight_current_program(channel_data))
            
            # 高亮并滚动到当前节目
            self.logger.info(f"正在处理频道: {channel_data['name']}")
            
            if not hasattr(self.main_window, 'epg_widget'):
                self.logger.warning("epg_widget属性不存在")
                return
                
            if not self.main_window.epg_widget:
                self.logger.warning("epg_widget未初始化")
                return
                
            # 清除之前的高亮
            for child in self.main_window.epg_widget.findChildren(QtWidgets.QLabel):
                if 'current-program' in child.property('class'):
                    child.setProperty('class', '')
                    child.style().unpolish(child)
                    child.style().polish(child)
            
            # 查找并高亮当前节目(模糊匹配)
            current_channel = channel_data['name'].lower()
            best_match = None
            best_score = 0
            
            labels = self.main_window.epg_widget.findChildren(QtWidgets.QLabel)
            self.logger.info(f"找到{len(labels)}个EPG节目标签")
            
            for child in labels:
                epg_channel = child.text().lower()
                self.logger.debug(f"比较频道: {current_channel} vs {epg_channel}")
                
                # 简单相似度计算
                score = sum(1 for a, b in zip(current_channel, epg_channel) if a == b)
                if score > best_score or (score == best_score and len(epg_channel) < len(child.text())):
                    best_match = child
                    best_score = score
            
            if best_match:
                self.logger.info(f"最佳匹配: {best_match.text()} (匹配度: {best_score}/{len(current_channel)})")
                if best_score >= len(current_channel)//2:  # 至少匹配一半字符
                    best_match.setProperty('class', 'current-program')
                    best_match.style().unpolish(best_match)
                    best_match.style().polish(best_match)
                    
                    # 滚动到可见区域中心
                    scroll_bar = self.main_window.epg_timeline.verticalScrollBar()
                    widget_pos = best_match.mapTo(self.main_window.epg_timeline, QtCore.QPoint(0, 0))
                    scroll_pos = widget_pos.y() - self.main_window.epg_timeline.height()//2 + best_match.height()//2
                    scroll_bar.setValue(scroll_pos)
                    self.logger.info(f"已滚动到位置: {scroll_pos}")
                else:
                    self.logger.warning("匹配度不足，未高亮显示")
            else:
                self.logger.warning("未找到匹配的EPG节目")
        else:
            # 已经是最后一行，回到第一行
            first_index = self.main_window.model.index(0, 0)
            self.main_window.channel_list.setCurrentIndex(first_index)
            self.main_window.channel_list.selectRow(0)
            # 载入频道名并自动全选
            self.main_window.name_edit.setText(self.main_window.model.data(first_index))
            self.main_window.name_edit.selectAll()
            # 播放当前选中的频道
            current_index = self.main_window.channel_list.currentIndex()
            channel_data = {
                'url': self.main_window.model.data(self.main_window.model.index(current_index.row(), 2)),  # URL在第2列
                'name': self.main_window.model.data(current_index)
            }
            self.main_window.player_controller.play_channel(channel_data)

    def _setup_menubar(self):
        """初始化菜单栏"""
        menubar = self.main_window.menuBar()

        # 文件菜单
        file_menu = menubar.addMenu("文件(&F)")
        open_action = QtGui.QAction("打开列表(&O)", self.main_window)
        open_action.setShortcut(QtGui.QKeySequence("Ctrl+O"))
        file_menu.addAction(open_action)

        save_action = QtGui.QAction("保存列表(&S)", self.main_window)
        save_action.setShortcut(QtGui.QKeySequence("Ctrl+S"))
        file_menu.addAction(save_action)

        file_menu.addSeparator()
        exit_action = QtGui.QAction("退出(&X)", self.main_window)
        exit_action.setShortcut(QtGui.QKeySequence("Ctrl+Q"))
        file_menu.addAction(exit_action)

    def _toggle_epg_panel(self, checked):
        """切换EPG节目单区域显示状态"""
        # 更新按钮图标方向(▶表示面板收起，◀表示面板展开)
        self.main_window.epg_toggle_btn.setText("◀" if checked else "▶")
        
        # 确保分割器已初始化
        if not hasattr(self.main_window, 'right_splitter'):
            self.logger.error("right_splitter未初始化")
            return
            
        # 获取当前总高度
        total_height = self.main_window.right_splitter.height()
        
        if checked:
            # 显示EPG面板 - 动态分配高度(播放器占70%，EPG占30%)
            player_height = int(total_height * 0.7)
            epg_height = total_height - player_height
            self.main_window.right_splitter.setSizes([player_height, epg_height])
            self.main_window.epg_content.setVisible(True)
            self.main_window.epg_header.layout().setAlignment(Qt.AlignmentFlag.AlignTop)
        else:
            # 收起EPG面板 - 全部空间给播放器
            self.main_window.right_splitter.setSizes([total_height, 0])
            self.main_window.epg_content.setVisible(False)
            self.main_window.epg_header.layout().setAlignment(Qt.AlignmentFlag.AlignCenter)
            
        # 确保按钮始终可见
        self.main_window.epg_toggle_btn.show()
        
        # 最小化布局更新
        def update_layout():
            self.main_window.epg_panel.setVisible(checked)
            self.main_window.epg_panel.updateGeometry()
            
        QtCore.QTimer.singleShot(50, update_layout)

    def _show_channel_context_menu(self, pos):
        """显示频道列表的右键菜单"""
        index = self.main_window.channel_list.indexAt(pos)
        if not index.isValid():
            return
            
        menu = QtWidgets.QMenu()
        
        # 添加删除频道菜单项
        delete_action = QtGui.QAction("删除频道", self.main_window)
        delete_action.triggered.connect(lambda: self._delete_selected_channel(index))
        menu.addAction(delete_action)
        
        # 显示菜单
        menu.exec(self.main_window.channel_list.viewport().mapToGlobal(pos))
        
    def _delete_selected_channel(self, index):
        """删除选中的频道"""
        if not index.isValid():
            return
            
        # 确认删除
        reply = QtWidgets.QMessageBox.question(
            self.main_window,
            "确认删除",
            "确定要删除这个频道吗?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
        )
        
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            # 从模型中删除行
            self.main_window.model.removeRow(index.row())
            self.logger.info(f"已删除频道: 行 {index.row()}")
            
            # 更新状态标签
            if hasattr(self.main_window, 'validate_status_label'):
                self.main_window.validate_status_label.setText(
                    f"检测: {self.main_window.model.rowCount()}/0"
                )

    def _setup_toolbar(self):
        """初始化工具栏"""
        toolbar = self.main_window.addToolBar("主工具栏")
        toolbar.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        toolbar.setMovable(False)
        toolbar.setIconSize(QtCore.QSize(24, 24))  # 设置合适的图标大小

        # 使用emoji作为文本的工具栏按钮
        def create_action(emoji, text, tooltip=None):
            """创建带有emoji文本的动作"""
            action = QtGui.QAction(f"{emoji} {text}", self.main_window)
            if tooltip:
                action.setToolTip(tooltip)
            return action

        # 主要功能按钮
        open_action = create_action("📂", "打开列表", "打开IPTV列表文件")
        save_action = create_action("💾", "保存列表", "保存当前列表到文件")
        refresh_epg_action = create_action("🔄", "刷新EPG", "重新获取EPG节目信息")
        epg_manager_action = create_action("📺", "EPG管理", "管理EPG源和设置")
        about_action = create_action("ℹ️", "关于", "关于本程序")

        # 添加分隔符
        toolbar.addSeparator()

        # 添加按钮到工具栏
        toolbar.addAction(open_action)
        toolbar.addAction(save_action)
        toolbar.addAction(refresh_epg_action)
        toolbar.addAction(epg_manager_action)
        toolbar.addAction(about_action)
        

    def _show_about_dialog(self):
        """显示关于对话框"""
        from about_dialog import AboutDialog
        dialog = AboutDialog(
            self.main_window)
        dialog.exec()

    def _show_epg_manager(self):
        """显示EPG管理对话框"""
        from epg_ui import EPGManagementDialog
        dialog = EPGManagementDialog(
            self.main_window,
            self.main_window.config_manager,
            lambda config: self.main_window.config_manager.save_epg_config(config)
        )
        dialog.exec()

        
class AndroidSplitterHandle(QtWidgets.QWidget):
    def __init__(self, orientation, parent=None):
        super().__init__(parent)
        self._orientation = orientation
        self.setStyleSheet("background: transparent;")
        
    def sizeHint(self):
        """强制要求布局系统保留足够空间"""
        return QtCore.QSize(20, 20) if self._orientation == Qt.Orientation.Horizontal else QtCore.QSize(20, 20)
        
    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        rect = self.rect()
        
        # 计算中心点和线条长度
        center = rect.center()
        line_length = min(rect.width(), rect.height()) - 0
        
        if self._orientation == Qt.Orientation.Horizontal:
            # 水平分隔条：短垂直线
            painter.drawLine(center.x(), center.y() - line_length//1, 
                            center.x(), center.y() + line_length//1)
        else:
            # 垂直分隔条：短水平线
            painter.drawLine(center.x() - line_length//1, center.y(),
                            center.x() + line_length//1, center.y())
