import asyncio
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt
from channel_model import ChannelListModel
from styles import AppStyles
from pathlib import Path

class UIBuilder:
    def __init__(self, main_window):
        self.main_window = main_window

    def build_ui(self):
        self._init_ui()
        self._setup_menubar()
        self._setup_toolbar()

    def _init_ui(self):
        """初始化用户界面"""
        self.main_window.setWindowTitle("IPTV Scanner Editor Pro / IPTV 专业扫描编辑工具")
        self.main_window.resize(1200, 800)
        self.main_window.setStyleSheet(AppStyles.main_window_style())
        
        # 主布局
        main_widget = QtWidgets.QWidget()
        self.main_window.setCentralWidget(main_widget)
        main_layout = QtWidgets.QHBoxLayout(main_widget)
        self._init_splitters()
        main_layout.addWidget(self.main_window.main_splitter)

        # 状态栏
        status_bar = self.main_window.statusBar()
        status_bar.show()
        status_bar.setStyleSheet(AppStyles.statusbar_style())
        status_bar.showMessage("程序已启动")
        
        self.main_window.progress_indicator = QtWidgets.QProgressBar()
        self.main_window.progress_indicator.setRange(0, 0)
        self.main_window.progress_indicator.setTextVisible(False)
        self.main_window.progress_indicator.setFixedWidth(120)
        self.main_window.progress_indicator.setStyleSheet(AppStyles.progress_style())
        self.main_window.progress_indicator.hide()
        status_bar.addPermanentWidget(self.main_window.progress_indicator)

    def _init_splitters(self):
        """初始化所有分隔条控件"""
        # 主水平分割器（左右布局）
        self.main_window.main_splitter = QtWidgets.QSplitter(Qt.Orientation.Horizontal)
        self.main_window.main_splitter.setChildrenCollapsible(False)

        # 左侧垂直分割器（扫描面板 + 频道列表）
        self.main_window.left_splitter = QtWidgets.QSplitter(Qt.Orientation.Vertical)
        self.main_window.left_splitter.setChildrenCollapsible(False)
        self._setup_scan_panel(self.main_window.left_splitter)
        self._setup_channel_list(self.main_window.left_splitter)

        # 右侧垂直分割器（播放器 + 底部编辑区）
        self.main_window.right_splitter = QtWidgets.QSplitter(Qt.Orientation.Vertical)
        self.main_window.right_splitter.setChildrenCollapsible(False)
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
        self.main_window.h_splitter.setChildrenCollapsible(False)
        self._setup_edit_panel(self.main_window.h_splitter)
        self._setup_match_panel(self.main_window.h_splitter)
        bottom_layout.addWidget(self.main_window.h_splitter)
        self.main_window.right_splitter.addWidget(bottom_container)

        # 统一设置分隔条样式
        style_map = {
            QtCore.Qt.Orientation.Vertical: AppStyles.splitter_handle_style("horizontal"),
            QtCore.Qt.Orientation.Horizontal: AppStyles.splitter_handle_style("vertical")
        }

        for splitter in [self.main_window.left_splitter, self.main_window.right_splitter, 
                        self.main_window.main_splitter, self.main_window.h_splitter]:
            splitter.setMinimumSize(100, 100)
            splitter.setStyleSheet(style_map[splitter.orientation()])
            splitter.setHandleWidth(8)

        # 组装主界面
        self.main_window.main_splitter.addWidget(self.main_window.left_splitter)
        self.main_window.main_splitter.addWidget(self.main_window.right_splitter)

        # 设置默认尺寸
        self.main_window.main_splitter.setSizes([300, 700])
        self.main_window.left_splitter.setSizes([200, 400])
        self.main_window.right_splitter.setSizes([400, 200])
        self.main_window.h_splitter.setSizes([300, 300])

    def _setup_channel_list(self, parent):
        """配置频道列表"""
        # ... (频道列表代码)

    def _setup_player_panel(self, parent: QtWidgets.QSplitter) -> None:  
        """配置播放器面板"""
        player_group = QtWidgets.QGroupBox("视频播放")
        # 关键修改1：设置正确的尺寸策略
        player_group.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding  # 必须为Expanding
        )
        
        player_layout = QtWidgets.QVBoxLayout()
        player_layout.setContentsMargins(2, 2, 2, 2)
        
        # 关键修改2：添加伸缩空间
        player_layout.addWidget(self.main_window.player, stretch=10)  # 播放器占主要空间

        # 控制按钮
        control_layout = QtWidgets.QHBoxLayout()
        self.main_window.pause_btn = QtWidgets.QPushButton("播放")
        self.main_window.pause_btn.setStyleSheet(AppStyles.player_button_style())
        self.main_window.pause_btn.clicked.connect(self.main_window.player.toggle_pause)
        self.main_window.stop_btn = QtWidgets.QPushButton("停止")
        self.main_window.stop_btn.setStyleSheet(AppStyles.button_style())
        self.main_window.stop_btn.clicked.connect(self.main_window.stop_play)

        control_layout.addWidget(self.main_window.pause_btn)
        control_layout.addWidget(self.main_window.stop_btn)

        player_layout.addLayout(control_layout, stretch=1)  # 控制区占较小空间

        # 音量控制
        volume_layout = QtWidgets.QHBoxLayout()

        self.main_window.volume_slider = QtWidgets.QSlider(Qt.Orientation.Horizontal)
        self.main_window.volume_slider.setRange(0, 100)
        self.main_window.volume_slider.setValue(50)  # 默认音量
        self.main_window.volume_slider.valueChanged.connect(self.main_window.set_volume)

        volume_layout.addWidget(QtWidgets.QLabel("音量："))
        volume_layout.addWidget(self.main_window.volume_slider)

        player_layout.addLayout(volume_layout, stretch=1)  # 音量控制占较小空间

        player_group.setLayout(player_layout)
        
        # 关键修改3：确保直接添加到QSplitter
        if isinstance(parent, QtWidgets.QSplitter):
            parent.addWidget(player_group)
        else:
            layout = parent.layout() or QtWidgets.QVBoxLayout(parent)
            layout.addWidget(player_group)

    def _setup_edit_panel(self, parent: QtWidgets.QSplitter) -> None:  
        """配置编辑面板"""
        edit_group = QtWidgets.QGroupBox("频道编辑")
        edit_layout = QtWidgets.QFormLayout()
        edit_layout.setRowWrapPolicy(QtWidgets.QFormLayout.RowWrapPolicy.WrapAllRows)  # 允许换行

        # 增加控件间距
        edit_layout.setVerticalSpacing(1)
        edit_layout.setHorizontalSpacing(1)
        edit_layout.setContentsMargins(10, 15, 10, 15)  # 增加内边距

        # 频道名称输入（加大高度）
        self.main_window.name_edit = QtWidgets.QLineEdit()
        self.main_window.name_edit.setMinimumHeight(32)  # 增加输入框高度
        self.main_window.name_edit.setPlaceholderText("输入频道名称...")
        self.main_window.name_edit.returnPressed.connect(self.main_window.save_channel_edit)  # 绑定回车键事件

        # 分组选择（增加下拉框高度，设置为可编辑）
        self.main_window.group_combo = QtWidgets.QComboBox()
        self.main_window.group_combo.setMinimumHeight(32)
        self.main_window.group_combo.setEditable(True)  # 允许自定义输入
        self.main_window.group_combo.addItems(["未分类", "央视", "卫视", "本地", "高清频道", "测试频道"])

        # EPG匹配状态显示（新增）
        self.main_window.epg_match_label = QtWidgets.QLabel("EPG状态: 未匹配")
        self.main_window.epg_match_label.setStyleSheet("font-weight: bold;")
        
        # 保存按钮（加大尺寸）
        save_btn = QtWidgets.QPushButton("保存修改")
        save_btn.setMinimumHeight(36)  # 增加按钮高度
        save_btn.setStyleSheet(AppStyles.button_style())
        save_btn.clicked.connect(self.main_window.save_channel_edit)

        # 布局调整
        edit_layout.addRow("频道名称：", self.main_window.name_edit)
        edit_layout.addRow("分组分类：", self.main_window.group_combo)
        edit_layout.addRow(self.main_window.epg_match_label)  # 新增状态显示
        edit_layout.addRow(QtWidgets.QLabel())  # 空行占位
        edit_layout.addRow(save_btn)

        # 修复自动补全功能
        self.main_window.epg_completer = QtWidgets.QCompleter()
        self.main_window.epg_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)  # 不区分大小写
        self.main_window.epg_completer.setFilterMode(Qt.MatchFlag.MatchContains)  # 支持模糊匹配
        self.main_window.epg_completer.setCompletionMode(QtWidgets.QCompleter.CompletionMode.PopupCompletion)  # 显示下拉列表
        self.main_window.epg_completer.setMaxVisibleItems(10)  # 最多显示10个匹配项
        # 禁用补全项的图标显示，避免libpng警告
        self.main_window.epg_completer.popup().setItemDelegate(QtWidgets.QStyledItemDelegate())
        # 彻底禁用所有输入法功能
        self.main_window.name_edit.setAttribute(Qt.WidgetAttribute.WA_InputMethodEnabled, False)
        # 设置最严格的输入法提示
        self.main_window.name_edit.setInputMethodHints(Qt.InputMethodHint.ImhNone)
        # 设置属性确保无输入法
        self.main_window.name_edit.setProperty("inputMethodHints", Qt.InputMethodHint.ImhNone)
        # 完全禁用补全器的输入法
        self.main_window.epg_completer.popup().setAttribute(Qt.WidgetAttribute.WA_InputMethodEnabled, False)
        self.main_window.epg_completer.popup().setInputMethodHints(Qt.InputMethodHint.ImhNone)
        self.main_window.epg_completer.popup().setStyleSheet("")
        # 设置补全器但不启用输入法
        self.main_window.name_edit.setCompleter(self.main_window.epg_completer)
        # 强制禁用输入法上下文
        self.main_window.name_edit.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        # 确保输入法完全禁用
        self.main_window.name_edit.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # 绑定文本变化事件
        self.main_window.name_edit.textChanged.connect(self.main_window.on_text_changed)

        edit_group.setLayout(edit_layout)
        parent.addWidget(edit_group)

    def _setup_match_panel(self, parent):
        """配置智能匹配面板"""
        match_group = QtWidgets.QGroupBox("智能匹配")
        layout = QtWidgets.QVBoxLayout()
        
        # 1. 操作按钮
        self.main_window.btn_load_old = QtWidgets.QPushButton("加载旧列表")
        self.main_window.btn_load_old.setStyleSheet(AppStyles.button_style())

        self.main_window.btn_match = QtWidgets.QPushButton("执行自动匹配")
        self.main_window.btn_match.setStyleSheet(AppStyles.button_style())
        self.main_window.btn_match.setEnabled(False)

        # 2. 状态显示
        self.main_window.match_status = QtWidgets.QLabel("匹配功能未就绪 - 请先加载旧列表")
        self.main_window.match_status.setStyleSheet("color: #666; font-weight: bold;")
        self.main_window.match_progress = QtWidgets.QProgressBar()
        self.main_window.match_progress.setTextVisible(True)
        self.main_window.match_progress.setStyleSheet(AppStyles.progress_style())
        
        # 3. 高级选项
        self.main_window.cb_override_epg = QtWidgets.QCheckBox("EPG不匹配时强制覆盖")
        self.main_window.cb_auto_save = QtWidgets.QCheckBox("匹配后自动保存")
        
        # 布局
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addWidget(self.main_window.btn_load_old)
        button_layout.addWidget(self.main_window.btn_match)
        
        layout.addLayout(button_layout)
        layout.addWidget(QtWidgets.QLabel("匹配进度:"))
        layout.addWidget(self.main_window.match_progress)
        layout.addWidget(self.main_window.match_status)
        layout.addStretch()
        layout.addWidget(self.main_window.cb_override_epg)
        layout.addWidget(self.main_window.cb_auto_save)
        
        match_group.setLayout(layout)
        parent.addWidget(match_group)
        
        # 信号连接
        self.main_window.btn_load_old.clicked.connect(self.main_window.load_old_playlist)
        self.main_window.btn_match.clicked.connect(
            lambda: asyncio.create_task(self.main_window.run_auto_match()))

    def _setup_scan_panel(self, parent: QtWidgets.QSplitter) -> None:
        """配置扫描面板"""
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
        
        # 线程数设置
        thread_layout = QtWidgets.QHBoxLayout()
        thread_label = QtWidgets.QLabel("设置扫描使用的线程数量")
        thread_layout.addWidget(thread_label)
        self.main_window.thread_count_input = QtWidgets.QSpinBox()
        self.main_window.thread_count_input.setRange(1, 100)
        self.main_window.thread_count_input.setValue(10)
        self.main_window.thread_count_input.setToolTip("同时处理的频道数量，也决定批处理大小(最大50)")
        thread_layout.addWidget(self.main_window.thread_count_input)

        # User-Agent设置
        user_agent_layout = QtWidgets.QHBoxLayout()
        user_agent_label = QtWidgets.QLabel("User-Agent:")
        user_agent_layout.addWidget(user_agent_label)
        self.main_window.user_agent_input = QtWidgets.QLineEdit()
        self.main_window.user_agent_input.setPlaceholderText("可选，留空使用默认")
        user_agent_layout.addWidget(self.main_window.user_agent_input)

        # Referer设置
        referer_layout = QtWidgets.QHBoxLayout()
        referer_label = QtWidgets.QLabel("Referer:")
        referer_layout.addWidget(referer_label)
        self.main_window.referer_input = QtWidgets.QLineEdit()
        self.main_window.referer_input.setPlaceholderText("可选，留空不使用")
        referer_layout.addWidget(self.main_window.referer_input)

        # 扫描控制按钮
        self.main_window.scan_btn = QtWidgets.QPushButton("完整扫描")
        self.main_window.scan_btn.setStyleSheet(AppStyles.button_style(active=True))
        self.main_window.scan_btn.clicked.connect(lambda: asyncio.create_task(self.main_window.toggle_scan()))
        
        # 设置按钮尺寸策略为Expanding
        self.main_window.scan_btn.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Fixed
        )

        # 扫描统计信息
        self.main_window.detailed_stats_label = QtWidgets.QLabel("总频道: 0 | 有效: 0 | 无效: 0 | 耗时: 0s")
        self.main_window.detailed_stats_label.setStyleSheet(AppStyles.status_label_style())

        # 使用网格布局让按钮和统计信息并排显示
        button_stats_layout = QtWidgets.QGridLayout()
        button_stats_layout.addWidget(self.main_window.scan_btn, 0, 0, 1, 2)  # 按钮占满前两列
        button_stats_layout.addWidget(self.main_window.detailed_stats_label, 1, 0, 1, 2)  # 统计信息占满第二行
        
        # 设置列拉伸比例
        button_stats_layout.setColumnStretch(0, 1)
        button_stats_layout.setColumnStretch(1, 1)

        scan_layout.addRow("地址格式：", QtWidgets.QLabel("示例：http://192.168.1.1:1234/rtp/10.10.[1-20].[1-20]:5002   [1-20]表示范围"))
        scan_layout.addRow("输入地址：", self.main_window.ip_range_input)
        scan_layout.addRow("超时时间：", timeout_layout)
        scan_layout.addRow("线程数：", thread_layout)
        scan_layout.addRow("User-Agent：", user_agent_layout)
        scan_layout.addRow("Referer：", referer_layout)
        scan_layout.addRow("进度：", self.main_window.scan_progress)
        scan_layout.addRow(button_stats_layout)  # 添加按钮和统计信息布局

        scan_group.setLayout(scan_layout)
        parent.addWidget(scan_group)

    def _setup_channel_list(self, parent: QtWidgets.QSplitter) -> None:  
        """配置频道列表"""
        list_group = QtWidgets.QGroupBox("频道列表")
        list_layout = QtWidgets.QVBoxLayout()

        # 工具栏
        toolbar = QtWidgets.QHBoxLayout()
        
        # 有效性检测按钮
        self.main_window.btn_validate = QtWidgets.QPushButton("检测有效性")
        self.main_window.btn_validate.setStyleSheet(AppStyles.button_style(active=True))
        
        # 隐藏无效项按钮
        self.main_window.btn_hide_invalid = QtWidgets.QPushButton("隐藏无效项")
        self.main_window.btn_hide_invalid.setStyleSheet(AppStyles.button_style())
        self.main_window.btn_validate.clicked.connect(lambda: asyncio.create_task(self.main_window.toggle_validation()))
        self.main_window.btn_hide_invalid.clicked.connect(lambda: asyncio.create_task(self.main_window.hide_invalid_channels()))
        
        # 状态标签
        self.main_window.filter_status_label = QtWidgets.QLabel("请先加载列表并点击检测有效性")
        self.main_window.filter_status_label.setStyleSheet(AppStyles.status_label_style())
        
        toolbar.addWidget(self.main_window.btn_validate)
        toolbar.addWidget(self.main_window.btn_hide_invalid)
        toolbar.addWidget(self.main_window.filter_status_label)
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
        
        # 右键菜单
        self.main_window.channel_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.main_window.channel_list.customContextMenuRequested.connect(self.main_window.show_context_menu)
        
        list_layout.addWidget(self.main_window.channel_list)
        list_group.setLayout(list_layout)
        parent.addWidget(list_group)

    def _setup_menubar(self):
        """初始化菜单栏"""
        menubar = self.main_window.menuBar()

        # 文件菜单
        file_menu = menubar.addMenu("文件(&F)")
        open_action = QtGui.QAction("打开列表(&O)", self.main_window)
        open_action.setShortcut(QtGui.QKeySequence("Ctrl+O"))
        open_action.triggered.connect(self.main_window.open_playlist)
        file_menu.addAction(open_action)

        save_action = QtGui.QAction("保存列表(&S)", self.main_window)
        save_action.setShortcut(QtGui.QKeySequence("Ctrl+S"))
        save_action.triggered.connect(self.main_window.save_playlist)
        file_menu.addAction(save_action)

        file_menu.addSeparator()
        exit_action = QtGui.QAction("退出(&X)", self.main_window)
        exit_action.setShortcut(QtGui.QKeySequence("Ctrl+Q"))
        exit_action.triggered.connect(self.main_window.close)
        file_menu.addAction(exit_action)

    def _setup_toolbar(self):
        """初始化工具栏"""
        toolbar = self.main_window.addToolBar("主工具栏")
        toolbar.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        toolbar.setMovable(False)

        def load_icon(path: str) -> QtGui.QIcon:
            """加载图标，如果失败则返回空图标"""
            icon_path = Path(__file__).parent / path
            if icon_path.exists():
                return QtGui.QIcon(str(icon_path))
            return QtGui.QIcon()

        # 打开列表
        open_action = QtGui.QAction(load_icon("icons/open.png"), "打开列表", self.main_window)
        open_action.triggered.connect(self.main_window.open_playlist)
        toolbar.addAction(open_action)

        # 保存列表
        save_action = QtGui.QAction(load_icon("icons/save.png"), "保存列表", self.main_window)
        save_action.triggered.connect(self.main_window.save_playlist)
        toolbar.addAction(save_action)

        # 加载 EPG 数据
        load_epg_action = QtGui.QAction(load_icon("icons/load.png"), "加载 EPG", self.main_window)
        load_epg_action.triggered.connect(lambda: asyncio.create_task(self.main_window._load_epg_with_progress()))
        toolbar.addAction(load_epg_action)

        # EPG 管理
        epg_manage_action = QtGui.QAction(load_icon("icons/settings.png"), "EPG 管理", self.main_window)
        epg_manage_action.triggered.connect(lambda: self.main_window.epg_manager.show_epg_manager_dialog(self.main_window))
        toolbar.addAction(epg_manage_action)

        # 关于
        about_action = QtGui.QAction(load_icon("icons/info.png"), "关于", self.main_window)
        about_action.triggered.connect(lambda: asyncio.create_task(self.main_window._show_about_dialog()))
        toolbar.addAction(about_action)

        # 添加分隔线保持布局美观
        toolbar.addSeparator()
