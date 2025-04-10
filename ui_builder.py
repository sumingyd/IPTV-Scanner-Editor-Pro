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

    def _setup_scan_panel(self, parent):
        """配置扫描面板"""
        scan_group = QtWidgets.QGroupBox("扫描设置")
        scan_layout = QtWidgets.QFormLayout()

        self.main_window.ip_range_input = QtWidgets.QLineEdit()
        self.main_window.scan_progress = QtWidgets.QProgressBar()
        self.main_window.scan_progress.setStyleSheet(AppStyles.progress_style())

        # ... (其余扫描面板代码)

        scan_group.setLayout(scan_layout)
        parent.addWidget(scan_group)

    def _setup_channel_list(self, parent):
        """配置频道列表"""
        # ... (频道列表代码)

    def _setup_player_panel(self, parent):
        """配置播放器面板"""
        player_group = QtWidgets.QGroupBox("播放器")
        player_layout = QtWidgets.QVBoxLayout()

        # 播放器控件
        self.main_window.video_widget = QtWidgets.QWidget()
        self.main_window.video_widget.setStyleSheet("background: black;")
        
        # 播放控制按钮
        btn_container = QtWidgets.QWidget()
        btn_layout = QtWidgets.QHBoxLayout(btn_container)
        
        self.main_window.play_btn = QtWidgets.QPushButton("播放")
        self.main_window.pause_btn = QtWidgets.QPushButton("暂停")
        self.main_window.stop_btn = QtWidgets.QPushButton("停止")
        
        for btn in [self.main_window.play_btn, self.main_window.pause_btn, self.main_window.stop_btn]:
            btn.setStyleSheet(AppStyles.button_style())
            btn.setFixedWidth(80)
            
        btn_layout.addWidget(self.main_window.play_btn)
        btn_layout.addWidget(self.main_window.pause_btn)
        btn_layout.addWidget(self.main_window.stop_btn)
        
        # 音量控制
        volume_container = QtWidgets.QWidget()
        volume_layout = QtWidgets.QHBoxLayout(volume_container)
        
        self.main_window.volume_label = QtWidgets.QLabel("音量:")
        self.main_window.volume_slider = QtWidgets.QSlider(Qt.Orientation.Horizontal)
        self.main_window.volume_slider.setRange(0, 100)
        self.main_window.volume_slider.setValue(50)
        self.main_window.volume_slider.setStyleSheet(AppStyles.slider_style())
        
        volume_layout.addWidget(self.main_window.volume_label)
        volume_layout.addWidget(self.main_window.volume_slider)
        
        # 添加到主布局
        player_layout.addWidget(self.main_window.video_widget)
        player_layout.addWidget(btn_container)
        player_layout.addWidget(volume_container)
        
        player_group.setLayout(player_layout)
        parent.addWidget(player_group)

    def _setup_edit_panel(self, parent):
        """配置编辑面板"""
        edit_group = QtWidgets.QGroupBox("频道编辑")
        edit_layout = QtWidgets.QFormLayout()

        # 频道名称
        self.main_window.name_edit = QtWidgets.QLineEdit()
        self.main_window.name_edit.setPlaceholderText("输入频道名称")
        self.main_window.name_edit.setStyleSheet(AppStyles.line_edit_style())
        edit_layout.addRow("名称:", self.main_window.name_edit)

        # 频道分组
        self.main_window.group_combo = QtWidgets.QComboBox()
        self.main_window.group_combo.setEditable(True)
        self.main_window.group_combo.addItems(["新闻", "体育", "电影", "娱乐", "少儿"])
        self.main_window.group_combo.setStyleSheet(AppStyles.combo_box_style())
        edit_layout.addRow("分组:", self.main_window.group_combo)

        # EPG匹配状态
        self.main_window.epg_match_label = QtWidgets.QLabel("未匹配EPG")
        self.main_window.epg_match_label.setStyleSheet(AppStyles.status_label_style())
        edit_layout.addRow("EPG状态:", self.main_window.epg_match_label)

        # 保存按钮
        self.main_window.save_btn = QtWidgets.QPushButton("保存修改")
        self.main_window.save_btn.setStyleSheet(AppStyles.button_style())
        self.main_window.save_btn.clicked.connect(self.main_window.save_channel_edit)
        edit_layout.addRow(self.main_window.save_btn)

        edit_group.setLayout(edit_layout)
        parent.addWidget(edit_group)

    def _setup_match_panel(self, parent):
        """配置智能匹配面板"""
        match_group = QtWidgets.QGroupBox("智能匹配")
        match_layout = QtWidgets.QVBoxLayout()

        # 旧列表操作按钮
        self.main_window.load_old_btn = QtWidgets.QPushButton("加载旧列表")
        self.main_window.load_old_btn.setStyleSheet(AppStyles.button_style())
        self.main_window.load_old_btn.clicked.connect(self.main_window.load_old_playlist)

        # 匹配操作按钮
        self.main_window.match_btn = QtWidgets.QPushButton("开始匹配")
        self.main_window.match_btn.setStyleSheet(AppStyles.button_style())
        self.main_window.match_btn.clicked.connect(
            lambda: asyncio.create_task(self.main_window.run_auto_match())
        )

        # 匹配结果统计
        self.main_window.match_stats = QtWidgets.QLabel("匹配结果: 0/0")
        self.main_window.match_stats.setStyleSheet(AppStyles.status_label_style())

        # 添加到布局
        match_layout.addWidget(self.main_window.load_old_btn)
        match_layout.addWidget(self.main_window.match_btn)
        match_layout.addWidget(self.main_window.match_stats)
        match_layout.addStretch()

        match_group.setLayout(match_layout)
        parent.addWidget(match_group)

    def _setup_scan_panel(self, parent):
        """配置扫描面板"""
        scan_group = QtWidgets.QGroupBox("扫描设置")
        scan_layout = QtWidgets.QFormLayout()

        self.main_window.ip_range_input = QtWidgets.QLineEdit()
        self.main_window.scan_progress = QtWidgets.QProgressBar()
        self.main_window.scan_progress.setStyleSheet(AppStyles.progress_style())

        # IP范围输入
        scan_layout.addRow("IP范围:", self.main_window.ip_range_input)
        
        # 扫描按钮
        self.main_window.scan_btn = QtWidgets.QPushButton("完整扫描")
        self.main_window.scan_btn.setStyleSheet(AppStyles.button_style())
        self.main_window.scan_btn.clicked.connect(
            lambda: asyncio.create_task(self.main_window.toggle_scan())
        )
        scan_layout.addRow(self.main_window.scan_btn)
        
        # 停止按钮
        self.main_window.stop_btn = QtWidgets.QPushButton("停止")
        self.main_window.stop_btn.setStyleSheet(AppStyles.button_style(active=True))
        self.main_window.stop_btn.clicked.connect(self.main_window.stop_scan)
        scan_layout.addRow(self.main_window.stop_btn)
        
        # 进度条
        scan_layout.addRow("进度:", self.main_window.scan_progress)
        
        # 详细统计
        self.main_window.detailed_stats_label = QtWidgets.QLabel("准备扫描")
        self.main_window.detailed_stats_label.setStyleSheet(AppStyles.status_label_style())
        scan_layout.addRow(self.main_window.detailed_stats_label)

        scan_group.setLayout(scan_layout)
        parent.addWidget(scan_group)

    def _setup_channel_list(self, parent):
        """配置频道列表"""
        # 频道列表视图
        self.main_window.channel_list = QtWidgets.QListView()
        self.main_window.channel_list.setStyleSheet(AppStyles.list_view_style())
        self.main_window.channel_list.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.main_window.channel_list.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        
        # 频道模型
        self.main_window.model = ChannelListModel()
        self.main_window.channel_list.setModel(self.main_window.model)
        
        # 右键菜单
        self.main_window.channel_list.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.main_window.channel_list.customContextMenuRequested.connect(self.main_window.show_context_menu)
        
        # 选中事件
        self.main_window.channel_list.selectionModel().currentChanged.connect(
            lambda: self.main_window.on_channel_selected()
        )
        
        # 添加到布局
        parent.addWidget(self.main_window.channel_list)

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
