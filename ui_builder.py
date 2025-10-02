import asyncio
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from channel_model import ChannelListModel
from styles import AppStyles
from pathlib import Path
from log_manager import LogManager
from language_manager import LanguageManager
import functools

class UIBuilder(QtCore.QObject):
    # 定义信号
    refresh_channel_finished = QtCore.pyqtSignal(object, object, str, str)
    
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.logger = LogManager()
        self._ui_initialized = False
        self._model_initialized = False
        # 网络图片管理器
        self.network_manager = QNetworkAccessManager()
        self.logo_cache = {}  # 缓存已下载的Logo图片
        self.pending_requests = {}  # 正在进行的请求
        # 防止Logo加载无限循环的标志
        self._loading_logos = False
        
        # 连接信号
        self.refresh_channel_finished.connect(self._finish_refresh_channel)

    def build_ui(self):
        if not self._ui_initialized:
            self._init_ui()
            self._setup_toolbar()
            self._ui_initialized = True

    def _setup_channel_list(self, parent: QtWidgets.QSplitter) -> None:  
        """配置频道列表"""
        if not self._model_initialized:
            self._model_initialized = True

    def _init_ui(self):
        """初始化用户界面"""
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
        if dividers and len(dividers) >= 2:
            self.main_window.main_splitter.setSizes(dividers[:2])
            self.main_window.left_splitter.setSizes(dividers[2:4])

        # 状态栏
        status_bar = self.main_window.statusBar()
        status_bar.show()
        status_bar.setStyleSheet(AppStyles.statusbar_style())
        
        # 添加远程映射状态标签
        self.main_window.mapping_status_label = QtWidgets.QLabel()
        status_bar.addWidget(self.main_window.mapping_status_label)
        
        # 添加进度条到状态栏右下角（显示实际进度）
        self.main_window.progress_indicator = QtWidgets.QProgressBar()
        self.main_window.progress_indicator.setRange(0, 100)
        self.main_window.progress_indicator.setValue(0)
        self.main_window.progress_indicator.setTextVisible(True)
        self.main_window.progress_indicator.setFixedWidth(120)
        self.main_window.progress_indicator.setStyleSheet(AppStyles.progress_style())
        self.main_window.progress_indicator.hide()
        status_bar.addPermanentWidget(self.main_window.progress_indicator)
        
        # 添加统计信息标签到状态栏右下角（统一用于扫描和有效性检测）
        self.main_window.stats_label = QtWidgets.QLabel("")
        self.main_window.stats_label.setStyleSheet("color: #666; padding: 0 5px;")
        status_bar.addPermanentWidget(self.main_window.stats_label)
        
        # 初始化时显示映射状态
        from channel_mappings import mapping_manager
        if mapping_manager.remote_mappings:
            self.main_window.mapping_status_label.setText(
                self.main_window.language_manager.tr('mapping_loaded', 'Remote mapping loaded')
            )
        else:
            self.main_window.mapping_status_label.setText(
                self.main_window.language_manager.tr('mapping_failed', 'Remote mapping load failed')
            )

    def _on_window_resize(self, event):
        """处理窗口大小变化事件"""
        try:
            size = self.main_window.size()
            # 保存当前分割器状态
            dividers = [
                *self.main_window.main_splitter.sizes(),
                *self.main_window.left_splitter.sizes(),
                *self.main_window.channel_splitter.sizes(),
            ]
            
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
        # 先初始化所有分割器
        self.main_window.main_splitter = QtWidgets.QSplitter(Qt.Orientation.Horizontal)
        self.main_window.left_splitter = QtWidgets.QSplitter(Qt.Orientation.Vertical)
        self.main_window.channel_splitter = QtWidgets.QSplitter(Qt.Orientation.Vertical)
        
        # 设置分割器属性
        self._setup_custom_splitter(self.main_window.main_splitter)
        self._setup_custom_splitter(self.main_window.left_splitter)
        self._setup_custom_splitter(self.main_window.channel_splitter)
        
        # 加载保存的分隔条位置
        _, _, dividers = self.main_window.config.load_window_layout()
        
        # 仅在未加载保存布局时设置默认值
        if not (dividers and len(dividers) >= 8):
            # 设置更合理的默认尺寸(基于窗口当前大小)
            width = self.main_window.width()
            height = self.main_window.height()
            self.main_window.main_splitter.setSizes([int(width*0.4), int(width*0.6)])
        
        # 设置分割器属性
        self._setup_custom_splitter(self.main_window.main_splitter)
        self._setup_custom_splitter(self.main_window.left_splitter)
        self._setup_custom_splitter(self.main_window.channel_splitter)
        
        # 视频播放面板放在左侧上方
        video_container = QtWidgets.QWidget()
        self._setup_player_panel(video_container)
        self.main_window.left_splitter.addWidget(video_container)
        
        # 扫描设置面板放在左侧下方
        self._setup_scan_panel(self.main_window.left_splitter)

        # 右侧频道列表面板
        right_container = QtWidgets.QWidget()
        self._setup_channel_list(right_container)

        # 组装主界面
        self.main_window.main_splitter.addWidget(self.main_window.left_splitter)
        self.main_window.main_splitter.addWidget(right_container)
        
        # 加载保存的分隔条位置
        _, _, dividers = self.main_window.config.load_window_layout()
        if dividers and len(dividers) >= 6:
            # 确保所有分割器都已初始化后再设置位置
            self.main_window.main_splitter.setSizes(dividers[:2])
            self.main_window.left_splitter.setSizes(dividers[2:4])
            # 延迟设置channel_splitter确保UI完全初始化
            QtCore.QTimer.singleShot(100, lambda: 
                self.main_window.channel_splitter.setSizes(dividers[4:6]))

        else:
            # 设置更合理的默认尺寸(基于窗口当前大小)
            width = self.main_window.width()
            height = self.main_window.height()
            self.main_window.main_splitter.setSizes([int(width*0.4), int(width*0.6)])
            self.main_window.left_splitter.setSizes([int(height*0.4), int(height*0.6)])


    def _setup_custom_splitter(self, splitter):
        if hasattr(splitter, '_custom_handle_installed'):
            return
            
        splitter.setChildrenCollapsible(False)
        splitter._custom_handle_installed = True
        
        # 必须设置足够大的handle宽度
        handle_size = 10
        splitter.setHandleWidth(handle_size)
        
        # 延迟设置确保splitter已初始化
        QtCore.QTimer.singleShot(100, lambda: self._install_handle(splitter))

    def _install_handle(self, splitter):
        if splitter.count() < 2:
            return
            
        handle = splitter.handle(1)
        if handle.findChild(QtWidgets.QWidget) is not None:
            return
            
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
                *self.main_window.channel_splitter.sizes(),
            ]
            self.main_window.config.save_window_layout(size.width(), size.height(), dividers)
        else:
            self._drag_start_pos = None

    def _setup_player_panel(self, parent: QtWidgets.QWidget) -> None:
        """配置播放器面板"""
        player_group = QtWidgets.QGroupBox("视频播放")
        self.main_window.player_group = player_group  # 设置为属性以便语言管理器访问
        player_layout = QtWidgets.QVBoxLayout()
        player_layout.setContentsMargins(2, 2, 2, 2)
        player_layout.setSpacing(5)
        
        # 播放器主体
        self.main_window.player = QtWidgets.QWidget()
        player_layout.addWidget(self.main_window.player, stretch=10)  # 大部分空间给播放器

        # 控制按钮区域
        control_layout = QtWidgets.QHBoxLayout()
        control_layout.setContentsMargins(0, 5, 0, 5)
        
        # 播放/停止按钮
        self.main_window.pause_btn = QtWidgets.QPushButton("播放")
        self.main_window.pause_btn.setStyleSheet(AppStyles.button_style(active=False))
        self.main_window.pause_btn.setEnabled(False)
        self.main_window.stop_btn = QtWidgets.QPushButton("停止")
        self.main_window.stop_btn.setStyleSheet(AppStyles.button_style(active=False))
        self.main_window.stop_btn.setEnabled(False)
        
        # 音量控制
        self.main_window.volume_slider = QtWidgets.QSlider(Qt.Orientation.Horizontal)
        self.main_window.volume_slider.setRange(0, 100)
        self.main_window.volume_slider.setValue(50)
        
        control_layout.addWidget(self.main_window.pause_btn)
        control_layout.addWidget(self.main_window.stop_btn)
        volume_label = QtWidgets.QLabel("音量：")
        self.main_window.volume_label = volume_label  # 设置为属性以便语言管理器访问
        control_layout.addWidget(volume_label)
        control_layout.addWidget(self.main_window.volume_slider)
        
        player_layout.addLayout(control_layout)
        player_group.setLayout(player_layout)
        parent.setLayout(QtWidgets.QVBoxLayout())
        parent.layout().addWidget(player_group)


    def _setup_scan_panel(self, parent: QtWidgets.QSplitter) -> None:
        """配置扫描面板"""
        scan_group = QtWidgets.QGroupBox("扫描设置")
        self.main_window.scan_group = scan_group  # 设置为属性以便语言管理器访问
        scan_layout = QtWidgets.QFormLayout()
        scan_layout.setContentsMargins(5, 5, 5, 5)  # 统一设置边距
        scan_layout.setSpacing(5)  # 统一设置间距

        self.main_window.ip_range_input = QtWidgets.QLineEdit()

        # 超时时间设置
        timeout_layout = QtWidgets.QHBoxLayout()
        timeout_label = QtWidgets.QLabel("设置扫描超时时间（秒）")
        self.main_window.timeout_description_label = timeout_label  # 设置为属性以便语言管理器访问
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
        self.main_window.thread_count_label = thread_label  # 设置为属性以便语言管理器访问
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
        self.main_window.user_agent_label = user_agent_label  # 设置为属性以便语言管理器访问
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
        self.main_window.referer_label = referer_label  # 设置为属性以便语言管理器访问
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

        # 扫描重试选项
        retry_layout = QtWidgets.QHBoxLayout()
        retry_label = QtWidgets.QLabel("扫描重试选项：")
        self.main_window.retry_label = retry_label  # 设置为属性以便语言管理器访问
        retry_layout.addWidget(retry_label)
        
        # 是否启用重试扫描
        self.main_window.enable_retry_checkbox = QtWidgets.QCheckBox("启用重试扫描")
        self.main_window.enable_retry_checkbox.setChecked(False)
        self.main_window.enable_retry_checkbox.setToolTip("第一次扫描完成后，对失效频道进行再次扫描")
        retry_layout.addWidget(self.main_window.enable_retry_checkbox)
        
        # 是否循环扫描
        self.main_window.loop_scan_checkbox = QtWidgets.QCheckBox("循环扫描")
        self.main_window.loop_scan_checkbox.setChecked(False)
        self.main_window.loop_scan_checkbox.setToolTip("如果重试扫描找到有效频道，继续扫描失效频道直到没有新的有效频道")
        self.main_window.loop_scan_checkbox.setEnabled(False)  # 默认禁用，需要启用重试扫描才能使用
        retry_layout.addWidget(self.main_window.loop_scan_checkbox)
        retry_layout.addStretch()
        
        # 连接复选框状态变化
        self.main_window.enable_retry_checkbox.stateChanged.connect(
            lambda state: self.main_window.loop_scan_checkbox.setEnabled(state == 2)
        )

        # 扫描控制按钮
        self.main_window.scan_btn = QtWidgets.QPushButton("完整扫描")
        self.main_window.scan_btn.setStyleSheet(AppStyles.button_style(active=True))
        self.main_window.scan_btn.setMinimumHeight(36)
        
        # 新增直接生成列表按钮
        self.main_window.generate_btn = QtWidgets.QPushButton("直接生成列表")
        self.main_window.generate_btn.setStyleSheet(AppStyles.button_style(active=True))
        self.main_window.generate_btn.setMinimumHeight(36)
        
        # 使用水平布局让按钮并排显示，自适应宽度
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addWidget(self.main_window.scan_btn, 1)  # 1表示拉伸因子
        button_layout.addSpacing(10)  # 添加间距
        button_layout.addWidget(self.main_window.generate_btn, 1)  # 1表示拉伸因子
        button_layout.addStretch()

        address_format_label = QtWidgets.QLabel("地址格式：")
        self.main_window.address_format_label = address_format_label  # 设置为属性以便语言管理器访问
        address_example_label = QtWidgets.QLabel("示例：http://192.168.1.1:1234/rtp/10.10.[1-20].[1-20]:5002   [1-20]表示范围")
        self.main_window.address_example_label = address_example_label  # 设置为属性以便语言管理器访问
        scan_layout.addRow(address_format_label, address_example_label)
        input_address_label = QtWidgets.QLabel("输入地址：")
        self.main_window.input_address_label = input_address_label  # 设置为属性以便语言管理器访问
        scan_layout.addRow(input_address_label, self.main_window.ip_range_input)
        timeout_row_label = QtWidgets.QLabel("超时时间：")
        self.main_window.timeout_row_label = timeout_row_label  # 设置为属性以便语言管理器访问
        scan_layout.addRow(timeout_row_label, timeout_layout)
        
        thread_row_label = QtWidgets.QLabel("线程数：")
        self.main_window.thread_row_label = thread_row_label  # 设置为属性以便语言管理器访问
        scan_layout.addRow(thread_row_label, thread_layout)
        user_agent_row_label = QtWidgets.QLabel("User-Agent：")
        self.main_window.user_agent_row_label = user_agent_row_label  # 设置为属性以便语言管理器访问
        scan_layout.addRow(user_agent_row_label, user_agent_layout)
        
        referer_row_label = QtWidgets.QLabel("Referer：")
        self.main_window.referer_row_label = referer_row_label  # 设置为属性以便语言管理器访问
        scan_layout.addRow(referer_row_label, referer_layout)
        
        # 添加重试选项行
        retry_row_label = QtWidgets.QLabel("重试选项：")
        self.main_window.retry_row_label = retry_row_label  # 设置为属性以便语言管理器访问
        scan_layout.addRow(retry_row_label, retry_layout)
        
        scan_layout.addRow(button_layout)

        scan_group.setLayout(scan_layout)
        parent.addWidget(scan_group)

    def _setup_channel_list(self, parent) -> None:  
        """配置频道列表"""
        # 使用类成员变量保存分割器引用
        self.main_window.channel_splitter = QtWidgets.QSplitter(Qt.Orientation.Vertical)
        self._setup_custom_splitter(self.main_window.channel_splitter)
        
        # 频道列表区域
        list_group = QtWidgets.QGroupBox("频道列表")
        self.main_window.list_group = list_group  # 设置为属性以便语言管理器访问
        list_layout = QtWidgets.QVBoxLayout()
        list_layout.setContentsMargins(5, 5, 5, 5)
        list_layout.setSpacing(5)

        # 工具栏
        toolbar = QtWidgets.QHBoxLayout()
        
        # 有效性检测按钮
        self.main_window.btn_validate = QtWidgets.QPushButton("检测有效性")
        self.main_window.btn_validate.setStyleSheet(AppStyles.button_style(active=True))
        self.main_window.btn_validate.setFixedHeight(36)
        
        # 隐藏无效项按钮
        self.main_window.btn_hide_invalid = QtWidgets.QPushButton("隐藏无效项")
        self.main_window.btn_hide_invalid.setStyleSheet(AppStyles.button_style(active=False))
        self.main_window.btn_hide_invalid.setFixedHeight(36)
        self.main_window.btn_hide_invalid.setEnabled(False)
        
        # 智能排序按钮
        self.main_window.btn_smart_sort = QtWidgets.QPushButton("智能排序")
        self.main_window.btn_smart_sort.setStyleSheet(AppStyles.button_style(active=True))
        self.main_window.btn_smart_sort.setFixedHeight(36)
        self.main_window.btn_smart_sort.setEnabled(True)
        self.main_window.btn_smart_sort.clicked.connect(
            lambda: self.main_window.model.sort_channels()
        )
        
        toolbar.addWidget(self.main_window.btn_validate)
        toolbar.addWidget(self.main_window.btn_hide_invalid)
        toolbar.addWidget(self.main_window.btn_smart_sort)
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
        
        # 确保模型存在并正确设置到视图中
        if not hasattr(self.main_window, 'model') or not self.main_window.model:
            self.main_window.model = ChannelListModel()
            self.main_window.model.update_status_label = self.main_window._update_validate_status
            # 设置语言管理器
            if hasattr(self.main_window, 'language_manager') and self.main_window.language_manager:
                self.main_window.model.set_language_manager(self.main_window.language_manager)
        
        # 关键：始终将模型设置到视图中，确保连接正确
        self.main_window.channel_list.setModel(self.main_window.model)
        self.logger.info("频道列表模型已设置到视图中")
        
        # 调试：检查模型和视图是否连接正确
        if self.main_window.channel_list.model() == self.main_window.model:
            self.logger.info("✅ 模型和视图连接验证成功")
        else:
            self.logger.error("❌ 模型和视图连接验证失败")
            self.logger.error(f"视图模型: {self.main_window.channel_list.model()}")
            self.logger.error(f"主窗口模型: {self.main_window.model}")
        
        self.main_window.channel_list.setStyleSheet(AppStyles.list_style())
        
        # 设置列宽自适应
        header = self.main_window.channel_list.horizontalHeader()
        header.setStretchLastSection(False)  # 禁用最后列自动拉伸
        header.setMinimumSectionSize(30)  # 最小列宽
        header.setMaximumSectionSize(1000)  # 最大列宽
        
        # 所有列始终自适应内容
        for i in range(header.count()):
            header.setSectionResizeMode(i, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        
        # 使用定时器控制列宽调整频率
        self._resize_timer = QtCore.QTimer()
        self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(500)  # 500ms延迟
        self._resize_timer.timeout.connect(header.resizeSections)

        # 监听数据变化重新计算布局和更新按钮状态
        def update_buttons():
            has_channels = self.main_window.model.rowCount() > 0
            self.main_window.pause_btn.setEnabled(has_channels)
            self.main_window.pause_btn.setStyleSheet(AppStyles.button_style(active=has_channels))

        # 使用批量更新机制
        self.main_window.model.dataChanged.connect(lambda: self._resize_timer.start())
        self.main_window.model.dataChanged.connect(update_buttons)
        self.main_window.model.rowsInserted.connect(update_buttons)
        self.main_window.model.rowsRemoved.connect(update_buttons)
        self.main_window.model.modelReset.connect(update_buttons)
        
        # 监听数据变化，异步加载网络Logo（只针对新增的行）
        self.main_window.model.rowsInserted.connect(self._load_single_channel_logo)
        self.main_window.model.modelReset.connect(self._load_network_logos)
        
        # 立即触发一次Logo加载
        QtCore.QTimer.singleShot(100, self._load_network_logos)
        
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

        # 添加频道列表到分割器
        list_group.setLayout(list_layout)
        self.main_window.channel_splitter.addWidget(list_group)
        
        # 添加频道编辑区域
        edit_group = self._setup_channel_edit(self.main_window.channel_splitter)
        
        if isinstance(parent, QtWidgets.QSplitter):
            parent.addWidget(self.main_window.channel_splitter)
        else:
            parent.setLayout(QtWidgets.QVBoxLayout())
            parent.layout().setContentsMargins(0, 0, 0, 0)
            parent.layout().addWidget(self.main_window.channel_splitter)
        
        # 设置默认分割比例
        self.main_window.channel_splitter.setSizes([int(self.main_window.height()*0.7), int(self.main_window.height()*0.3)])


    def _show_channel_context_menu(self, pos):
        """显示频道列表的右键菜单"""
        index = self.main_window.channel_list.indexAt(pos)
        if not index.isValid():
            return
            
        menu = QtWidgets.QMenu()
        
        # 获取选中频道的URL和名称
        url = self.main_window.model.data(self.main_window.model.index(index.row(), 3))  # URL在第3列
        name = self.main_window.model.data(self.main_window.model.index(index.row(), 1))  # 名称在第1列
        
        # 添加重新获取信息菜单项
        refresh_info_action = QtGui.QAction("重新获取信息", self.main_window)
        refresh_info_action.triggered.connect(lambda: self._refresh_channel_info(index))
        menu.addAction(refresh_info_action)
        
        menu.addSeparator()
        
        # 添加复制频道名菜单项
        copy_name_action = QtGui.QAction("复制频道名", self.main_window)
        copy_name_action.triggered.connect(lambda: self._copy_channel_name(name))
        menu.addAction(copy_name_action)
        
        # 添加复制URL菜单项
        copy_url_action = QtGui.QAction("复制URL", self.main_window)
        copy_url_action.triggered.connect(lambda: self._copy_channel_url(url))
        menu.addAction(copy_url_action)
        
        menu.addSeparator()
        
        # 添加删除频道菜单项
        delete_action = QtGui.QAction("删除频道", self.main_window)
        delete_action.triggered.connect(lambda: self._delete_selected_channel(index))
        menu.addAction(delete_action)
        
        # 显示菜单
        menu.exec(self.main_window.channel_list.viewport().mapToGlobal(pos))
        
    def _copy_channel_url(self, url):
        """复制频道URL到剪贴板"""
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText(url)
        self.logger.info(f"已复制URL: {url}")
        
    def _copy_channel_name(self, name):
        """复制频道名到剪贴板"""
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText(name)
        self.logger.info(f"已复制频道名: {name}")
        
    def _refresh_channel_info(self, index):
        """重新获取选中频道的详细信息（异步执行）"""
        if not index.isValid():
            return
            
        # 获取当前频道的URL和名称
        url = self.main_window.model.data(self.main_window.model.index(index.row(), 3))  # URL在第3列
        current_name = self.main_window.model.data(self.main_window.model.index(index.row(), 1))  # 名称在第1列
        
        if not url:
            QtWidgets.QMessageBox.warning(
                self.main_window,
                "错误",
                "无法获取频道URL",
                QtWidgets.QMessageBox.StandardButton.Ok
            )
            return
        
        self.logger.info(f"开始重新获取频道信息: 行 {index.row()}, 名称: {current_name}, URL: {url}")
        
        # 显示进度条和状态信息
        self.main_window.progress_indicator.show()
        self.main_window.progress_indicator.setValue(0)
        self.main_window.statusBar().showMessage(f"正在重新获取频道信息: {current_name}")
        
        # 使用QThreadPool异步执行验证任务
        from PyQt6.QtCore import QRunnable, QThreadPool, pyqtSlot
        from validator import StreamValidator
        from channel_mappings import mapping_manager, extract_channel_name_from_url
        
        class RefreshChannelTask(QRunnable):
            def __init__(self, ui_builder, index, url, current_name, timeout):
                super().__init__()
                self.ui_builder = ui_builder
                self.index = index
                self.url = url
                self.current_name = current_name
                self.timeout = timeout
                
            @pyqtSlot()
            def run(self):
                try:
                    self.ui_builder.logger.info(f"异步任务开始: 验证流媒体 {self.url}")
                    
                    # 更新进度：开始验证
                    self.ui_builder._update_refresh_progress(25, "正在验证流媒体...")
                    
                    # 执行流媒体验证
                    validator = StreamValidator(self.ui_builder.main_window)
                    result = validator.validate_stream(self.url, timeout=self.timeout)
                    
                    self.ui_builder.logger.info(f"流媒体验证结果: 有效={result['valid']}, 延迟={result['latency']}, 分辨率={result.get('resolution', '')}")
                    
                    # 更新进度：正在处理映射
                    self.ui_builder._update_refresh_progress(50, "正在处理频道映射...")
                    
                    # 获取原始频道名
                    raw_name = result.get('service_name', '') or extract_channel_name_from_url(self.url)
                    if not raw_name or raw_name == "未知频道":
                        raw_name = extract_channel_name_from_url(self.url)
                    
                    self.ui_builder.logger.info(f"原始频道名: {raw_name}")
                    
                    # 获取映射信息
                    channel_info_for_fingerprint = {
                        'service_name': result.get('service_name', ''),
                        'resolution': result.get('resolution', ''),
                        'codec': result.get('codec', ''),
                        'bitrate': result.get('bitrate', '')
                    }
                    
                    mapped_info = mapping_manager.get_channel_info(raw_name, self.url, channel_info_for_fingerprint) if result['valid'] else None
                    mapped_name = mapped_info.get('standard_name', raw_name) if mapped_info else raw_name
                    
                    self.ui_builder.logger.info(f"映射后频道名: {mapped_name}")
                    
                    # 更新进度：构建频道信息
                    self.ui_builder._update_refresh_progress(75, "正在更新频道信息...")
                    
                    # 获取当前频道信息以保留自定义设置
                    current_channel = self.ui_builder.main_window.model.get_channel(self.index.row())
                    
                    # 构建新的频道信息
                    new_channel_info = {
                        'url': self.url,
                        'name': mapped_name,
                        'raw_name': raw_name,
                        'valid': result['valid'],
                        'latency': result['latency'],
                        'resolution': result.get('resolution', ''),
                        'status': '有效' if result['valid'] else '无效',
                        'group': mapped_info.get('group_name', '未分类') if mapped_info else '未分类',
                        'logo_url': mapped_info.get('logo_url') if mapped_info else None,
                        'fingerprint': mapping_manager.create_channel_fingerprint(self.url, channel_info_for_fingerprint) if result['valid'] else None
                    }
                    
                    # 保留原有的自定义字段
                    if 'logo' in current_channel and current_channel['logo']:
                        new_channel_info['logo'] = current_channel['logo']
                    
                    self.ui_builder.logger.info(f"构建的新频道信息: {new_channel_info}")
                    
                    # 更新进度：完成更新
                    self.ui_builder._update_refresh_progress(100, "频道信息更新完成")
                    
                    # 在主线程中更新UI - 使用信号槽机制确保在主线程中执行
                    self.ui_builder.logger.info("准备调用 _finish_refresh_channel 方法")
                    
                    # 使用信号发射来触发主线程中的回调
                    try:
                        self.ui_builder.logger.info("尝试使用信号发射")
                        self.ui_builder.refresh_channel_finished.emit(
                            self.index, new_channel_info, mapped_name, raw_name
                        )
                        self.ui_builder.logger.info("信号发射成功")
                    except Exception as e:
                        self.ui_builder.logger.error(f"信号发射失败: {e}", exc_info=True)
                        # 备用方案：使用QTimer.singleShot
                        self.ui_builder.logger.info("尝试备用方案：QTimer.singleShot")
                        QtCore.QTimer.singleShot(0, lambda: self.ui_builder._finish_refresh_channel(
                            self.index, new_channel_info, mapped_name, raw_name
                        ))
                        self.ui_builder.logger.info("备用方案已安排")
                    
                    self.ui_builder.logger.info("已安排调用 _finish_refresh_channel 方法")
                    
                except Exception as e:
                    self.ui_builder.logger.error(f"重新获取频道信息失败: {e}", exc_info=True)
                    # 在主线程中显示错误
                    QtCore.QTimer.singleShot(0, lambda: self.ui_builder._handle_refresh_error(str(e)))
        
        # 创建并启动异步任务
        task = RefreshChannelTask(self, index, url, current_name, self.main_window.timeout_input.value())
        QThreadPool.globalInstance().start(task)
        self.logger.info(f"异步任务已启动: {url}")
        
    def _update_refresh_progress(self, value, message):
        """更新刷新进度（线程安全）"""
        QtCore.QTimer.singleShot(0, lambda: self._update_progress_ui(value, message))
        
    def _update_progress_ui(self, value, message):
        """在主线程中更新进度UI"""
        if hasattr(self.main_window, 'progress_indicator'):
            self.main_window.progress_indicator.setValue(value)
            self.main_window.statusBar().showMessage(f"{message}")
            
    def _finish_refresh_channel(self, index, new_channel_info, mapped_name, raw_name):
        """完成频道信息刷新"""
        try:
            self.logger.info(f"开始完成频道刷新: 索引 {index.row()}, 原始名: {raw_name}, 新名: {mapped_name}")
            
            # 更新模型中的频道信息
            success = self.main_window.model.update_channel(index.row(), new_channel_info)
            
            if not success:
                self.logger.error(f"更新频道信息失败: 索引 {index.row()}")
                self._handle_refresh_error("更新频道信息失败")
                return
            
            # 隐藏进度条
            if hasattr(self.main_window, 'progress_indicator'):
                self.main_window.progress_indicator.hide()
            
            # 显示成功消息
            self.main_window.statusBar().showMessage(f"频道信息已更新: {raw_name} -> {mapped_name}", 3000)
            self.logger.info(f"重新获取频道信息成功: {raw_name} -> {mapped_name}")
            
            # 强制刷新整个视图，确保所有列都更新
            top_left = self.main_window.model.index(index.row(), 0)
            bottom_right = self.main_window.model.index(index.row(), self.main_window.model.columnCount() - 1)
            self.logger.info(f"发送数据变化信号: 行 {index.row()}, 列 0-{self.main_window.model.columnCount()-1}")
            self.main_window.model.dataChanged.emit(top_left, bottom_right, [QtCore.Qt.ItemDataRole.DisplayRole, QtCore.Qt.ItemDataRole.DecorationRole])
            
            # 重新加载Logo（如果是网络Logo）
            if new_channel_info.get('logo_url') and new_channel_info['logo_url'].startswith(('http://', 'https://')):
                self.logger.info(f"重新加载Logo: {new_channel_info['logo_url']}")
                self._load_single_channel_logo_async(index.row())
                
            # 强制刷新UI，确保立即显示更新
            self.logger.info("强制刷新UI视图")
            self.main_window.channel_list.viewport().update()
            
            # 强制调整列宽以适应新内容
            self.logger.info("强制调整列宽")
            header = self.main_window.channel_list.horizontalHeader()
            header.resizeSections(QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
            
            # 强制刷新整个模型，确保UI完全更新
            self.logger.info("发送布局变化信号")
            self.main_window.model.layoutChanged.emit()
            
            # 额外强制刷新：确保UI立即响应
            self.logger.info("安排延迟UI更新")
            QtCore.QTimer.singleShot(0, lambda: self._force_ui_update(index.row()))
            
            # 延迟再次刷新，确保UI完全更新
            QtCore.QTimer.singleShot(100, lambda: self._final_ui_refresh(index.row()))
            
            self.logger.info("频道刷新完成")
                
        except Exception as e:
            self.logger.error(f"完成频道刷新失败: {e}", exc_info=True)
            self._handle_refresh_error(str(e))
            
    def _final_ui_refresh(self, row):
        """最终UI刷新，确保所有更新都显示"""
        try:
            # 再次强制刷新特定行
            top_left = self.main_window.model.index(row, 0)
            bottom_right = self.main_window.model.index(row, self.main_window.model.columnCount() - 1)
            self.main_window.model.dataChanged.emit(top_left, bottom_right)
            
            # 强制刷新整个视图
            self.main_window.channel_list.viewport().update()
            
            # 强制重绘
            self.main_window.channel_list.repaint()
            
            # 强制调整列宽
            header = self.main_window.channel_list.horizontalHeader()
            header.resizeSections(QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
            
            self.logger.debug(f"最终UI刷新完成: 行 {row}")
        except Exception as e:
            self.logger.debug(f"最终UI刷新失败: {e}")
            
    def _force_ui_update(self, row):
        """强制UI更新，确保频道信息立即显示"""
        try:
            # 强制刷新特定行
            top_left = self.main_window.model.index(row, 0)
            bottom_right = self.main_window.model.index(row, self.main_window.model.columnCount() - 1)
            self.main_window.model.dataChanged.emit(top_left, bottom_right)
            
            # 强制刷新整个视图
            self.main_window.channel_list.viewport().update()
            
            # 强制调整列宽
            header = self.main_window.channel_list.horizontalHeader()
            header.resizeSections(QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
            
            # 强制重绘
            self.main_window.channel_list.repaint()
            
            self.logger.debug(f"强制UI更新完成: 行 {row}")
        except Exception as e:
            self.logger.debug(f"强制UI更新失败: {e}")
            
    def _handle_refresh_error(self, error_message):
        """处理刷新错误"""
        if hasattr(self.main_window, 'progress_indicator'):
            self.main_window.progress_indicator.hide()
            
        QtWidgets.QMessageBox.critical(
            self.main_window,
            "错误",
            f"重新获取频道信息失败: {error_message}",
            QtWidgets.QMessageBox.StandardButton.Ok
        )
        self.main_window.statusBar().showMessage("重新获取频道信息失败", 3000)
        
    def _load_single_channel_logo_async(self, row):
        """异步重新加载单个频道的Logo"""
        try:
            channel = self.main_window.model.get_channel(row)
            logo_url = channel.get('logo_url', channel.get('logo', ''))
            
            # 只处理网络Logo地址
            if logo_url and logo_url.startswith(('http://', 'https://')):
                # 清除缓存中的旧Logo
                if logo_url in self.logo_cache:
                    del self.logo_cache[logo_url]
                
                # 显示占位符图标
                self._show_placeholder_icon(row, logo_url)
                
                # 重新下载Logo
                self._download_logo(logo_url, row)
                
        except Exception as e:
            self.logger.debug(f"重新加载Logo失败: {e}")
            
    def _delete_selected_channel(self, index):
        """删除选中的频道"""
        if not index.isValid():
            return
            
        # 确认删除
        reply = QtWidgets.QMessageBox.question(
            self.main_window,
            self.main_window.language_manager.tr('confirm_delete', 'Confirm Delete'),
            self.main_window.language_manager.tr('delete_channel_confirm', 'Are you sure you want to delete this channel?'),
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

    def _setup_channel_edit(self, parent) -> QtWidgets.QWidget:
        """配置频道编辑区域"""
        edit_group = QtWidgets.QGroupBox("频道编辑")
        self.main_window.edit_group = edit_group  # 设置为属性以便语言管理器访问
        edit_layout = QtWidgets.QFormLayout()
        edit_layout.setContentsMargins(5, 5, 5, 5)
        edit_layout.setSpacing(5)
        
        # 频道名称输入
        self.main_window.channel_name_edit = QtWidgets.QLineEdit()
        self.main_window.channel_name_edit.setPlaceholderText("输入频道名称 (必填)")
        self.main_window.channel_name_edit.setToolTip("输入频道的名称，如'CCTV-1 综合'")
        
        # 频道分组输入
        self.main_window.channel_group_edit = QtWidgets.QLineEdit()
        self.main_window.channel_group_edit.setPlaceholderText("输入频道分组 (可选)")
        self.main_window.channel_group_edit.setToolTip("输入频道所属分组，如'央视频道'")
        
        # LOGO地址输入
        self.main_window.channel_logo_edit = QtWidgets.QLineEdit()
        self.main_window.channel_logo_edit.setPlaceholderText("输入LOGO地址 (可选)")
        self.main_window.channel_logo_edit.setToolTip("输入频道LOGO图片的URL地址")
        
        # 频道URL输入
        self.main_window.channel_url_edit = QtWidgets.QLineEdit()
        self.main_window.channel_url_edit.setPlaceholderText("输入频道URL (必填)")
        self.main_window.channel_url_edit.setToolTip("输入频道的播放地址，如'http://example.com/stream.m3u8'")
        
        # 修改频道按钮
        self.main_window.edit_channel_btn = QtWidgets.QPushButton("修改频道")
        self.main_window.edit_channel_btn.setStyleSheet(AppStyles.button_style(active=True))
        self.main_window.edit_channel_btn.setFixedHeight(36)
        self.main_window.edit_channel_btn.setEnabled(False)
        self.main_window.edit_channel_btn.setToolTip("修改当前选中的频道信息")
        self.main_window.edit_channel_btn.clicked.connect(self._edit_channel)
        
        # 监听列表选择变化
        self.main_window.channel_list.selectionModel().selectionChanged.connect(
            self._on_selection_changed
        )
        
        # 添加频道按钮
        self.main_window.add_channel_btn = QtWidgets.QPushButton("添加频道")
        self.main_window.add_channel_btn.setStyleSheet(AppStyles.button_style(active=True))
        self.main_window.add_channel_btn.setFixedHeight(36)
        self.main_window.add_channel_btn.setToolTip("添加新频道到列表")
        self.main_window.add_channel_btn.clicked.connect(self._add_channel)
        
        # 按钮布局
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addWidget(self.main_window.edit_channel_btn)
        button_layout.addSpacing(10)
        button_layout.addWidget(self.main_window.add_channel_btn)
        
        # 添加到布局
        channel_name_label = QtWidgets.QLabel("频道名称:")
        self.main_window.channel_name_label = channel_name_label  # 设置为属性以便语言管理器访问
        edit_layout.addRow(channel_name_label, self.main_window.channel_name_edit)
        
        channel_group_label = QtWidgets.QLabel("频道分组:")
        self.main_window.channel_group_label = channel_group_label  # 设置为属性以便语言管理器访问
        edit_layout.addRow(channel_group_label, self.main_window.channel_group_edit)
        
        logo_address_label = QtWidgets.QLabel("LOGO地址:")
        self.main_window.logo_address_label = logo_address_label  # 设置为属性以便语言管理器访问
        edit_layout.addRow(logo_address_label, self.main_window.channel_logo_edit)
        
        channel_url_label = QtWidgets.QLabel("频道URL:")
        self.main_window.channel_url_label = channel_url_label  # 设置为属性以便语言管理器访问
        edit_layout.addRow(channel_url_label, self.main_window.channel_url_edit)
        
        operation_label = QtWidgets.QLabel("操作:")
        self.main_window.operation_label = operation_label  # 设置为属性以便语言管理器访问
        edit_layout.addRow(operation_label)
        edit_layout.addRow(button_layout)
        
        edit_group.setLayout(edit_layout)
        parent.addWidget(edit_group)
        return edit_group

    def _setup_toolbar(self):
        """初始化工具栏"""
        toolbar = self.main_window.addToolBar("主工具栏")
        toolbar.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        toolbar.setMovable(False)
        toolbar.setIconSize(QtCore.QSize(24, 24))  # 设置合适的图标大小
        toolbar.setStyleSheet(AppStyles.toolbar_button_style())

        # 使用emoji作为文本的工具栏按钮
        def create_action(emoji, text, tooltip=None):
            """创建带有emoji文本的动作"""
            action = QtGui.QAction(f"{emoji} {text}", self.main_window)
            if tooltip:
                action.setToolTip(tooltip)
            return action

        # 主要功能按钮 - 在创建时直接连接信号
        self.main_window.open_action = create_action("📂", "打开列表", "打开IPTV列表文件")
        self.main_window.open_action.triggered.connect(self.main_window._open_list)
        
        self.main_window.save_action = create_action("💾", "保存列表", "保存当前列表到文件")
        self.main_window.save_action.triggered.connect(self.main_window._save_list)
        
        # 使用QToolButton并手动连接菜单项点击事件
        self.main_window.language_button = QtWidgets.QToolButton(self.main_window)
        self.main_window.language_button.setText("🌐 语言")
        self.main_window.language_button.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        self.main_window.language_button.setStyleSheet(AppStyles.toolbar_button_style())
        
        # 创建语言菜单
        self.main_window.language_menu = QtWidgets.QMenu("语言", self.main_window)
        self.main_window.language_button.setMenu(self.main_window.language_menu)
        
        # 使用主窗口的语言管理器，避免重复加载
        if not hasattr(self.main_window, 'language_manager') or not self.main_window.language_manager:
            self.logger.warning("语言管理器未初始化，跳过工具栏语言设置")
            return
        
        # 添加语言选项并直接连接信号
        available_languages = self.main_window.language_manager.available_languages
        for lang_code, lang_info in available_languages.items():
            lang_action = QtGui.QAction(lang_info['display_name'], self.main_window)
            lang_action.setData(lang_code)
            # 直接连接信号，不使用functools.partial
            lang_action.triggered.connect(lambda checked, code=lang_code: self._change_language(code))
            self.main_window.language_menu.addAction(lang_action)
            self.logger.debug(f"添加语言选项: {lang_code} - {lang_info['display_name']}")
        
        self.logger.debug(f"语言菜单包含 {len(self.main_window.language_menu.actions())} 个动作")
        
        # 创建QWidgetAction来包装QToolButton
        language_action = QtWidgets.QWidgetAction(self.main_window)
        language_action.setDefaultWidget(self.main_window.language_button)
        
        self.main_window.about_action = create_action("ℹ️", "关于", "关于本程序")
        self.main_window.about_action.triggered.connect(self.main_window._on_about_clicked)
        
        # 添加映射管理器按钮
        self.main_window.mapping_action = create_action("🗺️", "映射管理", "管理频道映射规则")
        self.main_window.mapping_action.triggered.connect(self.main_window._on_mapping_clicked)

        # 添加分隔符
        toolbar.addSeparator()

        # 添加按钮到工具栏
        toolbar.addAction(self.main_window.open_action)
        toolbar.addAction(self.main_window.save_action)
        toolbar.addAction(language_action)
        toolbar.addAction(self.main_window.mapping_action)
        toolbar.addAction(self.main_window.about_action)
        
        # 立即刷新语言菜单显示
        self.main_window.language_menu.aboutToShow.connect(self._refresh_language_menu)
        
    def _refresh_language_menu(self):
        """刷新语言菜单，确保在打包环境中也能正确显示"""
        # 清空现有菜单项
        self.main_window.language_menu.clear()
        
        # 使用已加载的语言列表，避免重复加载
        available_languages = self.main_window.language_manager.available_languages
        
        # 如果语言列表为空，则加载一次
        if not available_languages:
            self.main_window.language_manager.load_available_languages()
            available_languages = self.main_window.language_manager.available_languages
        
        # 重新添加语言选项
        for lang_code, lang_info in available_languages.items():
            lang_action = QtGui.QAction(lang_info['display_name'], self.main_window)
            lang_action.setData(lang_code)
            lang_action.triggered.connect(lambda checked, code=lang_code: self._change_language(code))
            self.main_window.language_menu.addAction(lang_action)
            self.logger.debug(f"添加语言选项: {lang_code} - {lang_info['display_name']}")
        
        self.logger.debug(f"语言菜单已刷新，包含 {len(self.main_window.language_menu.actions())} 个动作")

    def _change_language(self, lang_code):
        """切换语言"""
        self.logger.info(f"尝试切换语言到: {lang_code}")
        if self.main_window.language_manager.set_language(lang_code):
            # 保存语言设置
            self.main_window.config.save_language_settings(lang_code)
            # 更新UI文本
            self.main_window.language_manager.update_ui_texts(self.main_window)
            self.logger.info(f"语言已切换到: {lang_code}")
        else:
            self.logger.warning(f"语言切换失败: {lang_code}")

    def _show_about_dialog(self):
        """显示关于对话框"""
        from about_dialog import AboutDialog
        dialog = AboutDialog(
            self.main_window)
        dialog.exec()

    def _on_selection_changed(self):
        """处理列表选择变化"""
        selection = self.main_window.channel_list.selectionModel().selectedRows()
        if selection:
            # 获取选中频道数据
            channel = self.main_window.model.get_channel(selection[0].row())
            
            # 填充到编辑区
            self.main_window.channel_name_edit.setText(channel.get('name', ''))
            self.main_window.channel_group_edit.setText(channel.get('group', ''))
            self.main_window.channel_logo_edit.setText(channel.get('logo', ''))
            self.main_window.channel_url_edit.setText(channel.get('url', ''))
            
            # 启用修改按钮
            self.main_window.edit_channel_btn.setEnabled(True)
        else:
            # 清空编辑区
            self.main_window.channel_name_edit.clear()
            self.main_window.channel_group_edit.clear()
            self.main_window.channel_logo_edit.clear()
            self.main_window.channel_url_edit.clear()
            
            # 禁用修改按钮
            self.main_window.edit_channel_btn.setEnabled(False)

    def _edit_channel(self):
        """修改选中频道"""
        selection = self.main_window.channel_list.selectionModel().selectedRows()
        if not selection:
            return
            
        # 获取编辑后的数据
        channel_info = {
            'name': self.main_window.channel_name_edit.text().strip(),
            'group': self.main_window.channel_group_edit.text().strip(),
            'logo': self.main_window.channel_logo_edit.text().strip(),
            'url': self.main_window.channel_url_edit.text().strip()
        }
        
        # 验证必填字段
        if not channel_info['name'] or not channel_info['url']:
            QtWidgets.QMessageBox.warning(
                self.main_window,
                self.main_window.language_manager.tr('input_error', 'Input Error'),
                self.main_window.language_manager.tr('name_url_required', 'Channel name and URL cannot be empty'),
                QtWidgets.QMessageBox.StandardButton.Ok
            )
            return
            
        # 更新模型数据
        self.main_window.model.update_channel(selection[0].row(), channel_info)
        
        # 清空编辑区
        self.main_window.channel_name_edit.clear()
        self.main_window.channel_group_edit.clear()
        self.main_window.channel_logo_edit.clear()
        self.main_window.channel_url_edit.clear()
        
        # 禁用修改按钮
        self.main_window.edit_channel_btn.setEnabled(False)

    def _add_channel(self):
        """添加新频道到列表"""
        name = self.main_window.channel_name_edit.text().strip()
        url = self.main_window.channel_url_edit.text().strip()
        
        if not name or not url:
            QtWidgets.QMessageBox.warning(
                self.main_window,
                self.main_window.language_manager.tr('input_error', 'Input Error'),
                self.main_window.language_manager.tr('name_url_required', 'Channel name and URL cannot be empty'),
                QtWidgets.QMessageBox.StandardButton.Ok
            )
            return
            
        group = self.main_window.channel_group_edit.text().strip()
        logo = self.main_window.channel_logo_edit.text().strip()
        
        # 添加到模型
        channel_info = {
            'name': name,
            'group': group if group else "未分组",
            'url': url,
            'logo': logo if logo else "",
            'valid': True,
            'latency': 0,
            'status': '待检测'
        }
        self.main_window.model.add_channel(channel_info)
        
        # 清空输入框
        self.main_window.channel_name_edit.clear()
        self.main_window.channel_group_edit.clear()
        self.main_window.channel_logo_edit.clear()
        self.main_window.channel_url_edit.clear()

    def _load_network_logos(self):
        """异步加载网络Logo图片"""
        # 防止无限循环
        if self._loading_logos:
            return
            
        if not hasattr(self.main_window, 'model') or not self.main_window.model:
            return
            
        self._loading_logos = True
        try:
            # 只记录开始加载的简要信息
            if self.main_window.model.rowCount() > 0:
                self.logger.debug(f"开始加载网络Logo，共 {self.main_window.model.rowCount()} 个频道")
            
            # 遍历所有频道，检查是否有网络Logo需要加载
            for row in range(self.main_window.model.rowCount()):
                channel = self.main_window.model.get_channel(row)
                logo_url = channel.get('logo_url', channel.get('logo', ''))
                
                # 只处理网络Logo地址
                if logo_url and logo_url.startswith(('http://', 'https://')):
                    # 检查是否已经在缓存中
                    if logo_url in self.logo_cache:
                        continue
                        
                    # 检查是否已经在请求中
                    if logo_url in self.pending_requests:
                        continue
                        
                    # 立即显示占位符图标，然后异步加载实际图片
                    self._show_placeholder_icon(row, logo_url)
                    
                    # 发起网络请求
                    self._download_logo(logo_url, row)
                    
            # 强制刷新视图以确保Logo显示
            if self.main_window.model.rowCount() > 0:
                top_left = self.main_window.model.index(0, 0)
                bottom_right = self.main_window.model.index(self.main_window.model.rowCount() - 1, 0)
                self.main_window.model.dataChanged.emit(top_left, bottom_right)
        finally:
            self._loading_logos = False

    def _show_placeholder_icon(self, row, logo_url):
        """显示占位符图标，并立即更新UI"""
        try:
            # 创建一个简单的占位符图标
            pixmap = QtGui.QPixmap(24, 24)
            pixmap.fill(QtGui.QColor('#cccccc'))
            placeholder_icon = QtGui.QIcon(pixmap)
            
            # 临时缓存占位符图标
            self.logo_cache[logo_url] = placeholder_icon
            
            # 立即更新UI
            index = self.main_window.model.index(row, 0)
            self.main_window.model.dataChanged.emit(index, index)
            
            self.logger.debug(f"显示占位符图标: {logo_url}")
        except Exception as e:
            self.logger.debug(f"显示占位符图标失败: {logo_url}, {e}")

    def _download_logo(self, logo_url, row):
        """下载Logo图片"""
        try:
            request = QNetworkRequest(QtCore.QUrl(logo_url))
            
            # 发起请求
            reply = self.network_manager.get(request)
            self.pending_requests[logo_url] = reply
            
            # 连接完成信号
            reply.finished.connect(lambda: self._on_logo_downloaded(reply, logo_url, row))
            
        except Exception as e:
            self.logger.debug(f"Logo下载请求失败: {logo_url}, {e}")

    def _load_single_channel_logo(self, parent, first, last):
        """只加载新增频道的Logo"""
        if self._loading_logos:
            return
            
        self._loading_logos = True
        try:
            for row in range(first, last + 1):
                if row < self.main_window.model.rowCount():
                    channel = self.main_window.model.get_channel(row)
                    logo_url = channel.get('logo_url', channel.get('logo', ''))
                    
                    # 只处理网络Logo地址
                    if logo_url and logo_url.startswith(('http://', 'https://')):
                        # 检查是否已经在缓存中
                        if logo_url in self.logo_cache:
                            continue
                            
                        # 检查是否已经在请求中
                        if logo_url in self.pending_requests:
                            continue
                            
                        # 立即显示占位符图标，然后异步加载实际图片
                        self._show_placeholder_icon(row, logo_url)
                        
                        # 发起网络请求
                        self._download_logo(logo_url, row)
        finally:
            self._loading_logos = False

    def _on_logo_downloaded(self, reply, logo_url, row):
        """Logo下载完成处理"""
        try:
            if reply.error() == QNetworkReply.NetworkError.NoError:
                # 读取图片数据
                data = reply.readAll()
                pixmap = QtGui.QPixmap()
                if pixmap.loadFromData(data):
                    # 等比缩放图片，保持宽高比，增大Logo尺寸到36像素
                    original_size = pixmap.size()
                    if original_size.height() > 0:
                        # 计算缩放比例，保持宽高比
                        scale_factor = 36.0 / original_size.height()  # 从24增大到36
                        new_width = int(original_size.width() * scale_factor)
                        new_height = 36  # 从24增大到36
                        
                        # 如果宽度超过120像素，限制最大宽度
                        if new_width > 120:  # 从100增大到120
                            scale_factor = 120.0 / original_size.width()
                            new_width = 120
                            new_height = int(original_size.height() * scale_factor)
                        
                        scaled_pixmap = pixmap.scaled(new_width, new_height, 
                                                    QtCore.Qt.AspectRatioMode.KeepAspectRatio, 
                                                    QtCore.Qt.TransformationMode.SmoothTransformation)
                        icon = QtGui.QIcon(scaled_pixmap)
                        
                        # 缓存图片
                        self.logo_cache[logo_url] = icon
                        
                        # 更新UI
                        index = self.main_window.model.index(row, 0)
                        self.main_window.model.dataChanged.emit(index, index)
                        
                        # 只记录成功信息，不记录详细尺寸
                        self.logger.debug(f"Logo下载成功: {logo_url}")
                    else:
                        self.logger.debug(f"Logo图片高度为0: {logo_url}")
                else:
                    self.logger.debug(f"Logo图片格式不支持: {logo_url}")
            else:
                self.logger.debug(f"Logo下载失败: {logo_url}, 错误: {reply.errorString()}")
                
        except Exception as e:
            self.logger.debug(f"Logo处理异常: {logo_url}, {e}")
        finally:
            # 清理请求
            if logo_url in self.pending_requests:
                del self.pending_requests[logo_url]
            reply.deleteLater()


        
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
