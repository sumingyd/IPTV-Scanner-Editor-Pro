"""
扫描频道窗口模块 - 负责扫描频道功能的UI和事件处理
"""

import os
import time
from PyQt6 import QtWidgets, QtCore, QtGui

# 导入自定义模块
from models.channel_model import ChannelListModel
from services.scanner_service import ScannerController
from ui.styles import AppStyles
from services.url_parser_service import URLRangeParser
from ui.optimizer import get_ui_optimizer
from utils.error_handler import init_global_error_handler
from utils.resource_cleaner import register_cleanup
from utils.general_utils import safe_connect_button
from utils.progress_manager import init_progress_manager
from utils.config_notifier import register_config_observer
from utils.scan_state_manager import get_scan_state_manager, register_retry_task, RetryScanStateContext
from utils.logging_helper import (
    log_ui_info, log_ui_warning, log_ui_error, log_scan_info,
    log_scan_warning, log_config_error, log_config_info
)
from core.config_manager import ConfigManager
from core.log_manager import global_logger
from core.language_manager import LanguageManager


class ScanChannelDialog(QtWidgets.QDialog):
    """扫描频道窗口类，继承自QDialog"""

    def __init__(self, parent=None):
        super().__init__(parent)
        # 窗口拖动相关变量
        self.dragging = False
        self.offset = None
        self.opacity = 220
        # 保存应用程序引用
        self.application = parent
        if parent:
            self.config = getattr(parent, 'config', None) or ConfigManager()
            self.logger = getattr(parent, 'logger', None) or global_logger
            self.language_manager = getattr(parent, 'language_manager', None)
            if not self.language_manager:
                self.language_manager = LanguageManager()
                self.language_manager.load_available_languages()
                language_code = self.config.load_language_settings()
                self.language_manager.set_language(language_code)
        else:
            self.config = ConfigManager()
            self.logger = global_logger
            self.language_manager = LanguageManager()
            self.language_manager.load_available_languages()
            language_code = self.config.load_language_settings()
            self.language_manager.set_language(language_code)

        # 扫描状态管理器
        self.scan_state_manager = get_scan_state_manager()
        self.retry_id = 'main_retry'

        # 注册重试扫描任务
        register_retry_task(self.retry_id, self)

        self._init_ui()

        # 立即更新UI文本到当前语言
        if hasattr(self, 'language_manager'):
            self.language_manager.update_ui_texts(self)

        # 初始化主窗口的后续设置
        self._init_main_window()
        self._timers = []
        QtCore.QTimer.singleShot(0, self._init_timers)
    
    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            # 检查鼠标位置下的控件是否是滚动条
            widget = QtWidgets.QApplication.widgetAt(event.globalPosition().toPoint())
            if widget and (isinstance(widget, QtWidgets.QScrollBar) or isinstance(widget, QtWidgets.QTableView)):
                # 如果是滚动条或表格视图，不处理事件
                return
            self.dragging = True
            self.offset = event.position().toPoint()
    
    def mouseMoveEvent(self, event):
        if self.dragging:
            new_position = event.globalPosition().toPoint() - self.offset
            self.move(new_position)
    
    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.dragging = False

    def _init_timers(self):
        """在主线程初始化所有定时器"""
        pass

    def _stop_all_timers(self):
        """安全停止所有定时器"""
        if hasattr(self, '_timers'):
            for timer in self._timers:
                if timer.isActive():
                    if QtCore.QThread.currentThread() == timer.thread():
                        timer.stop()
                    else:
                        QtCore.QMetaObject.invokeMethod(
                            timer, "stop", QtCore.Qt.ConnectionType.QueuedConnection
                        )
            self._timers.clear()
        
        # 停止扫描器中的批量更新定时器
        if hasattr(self, 'scanner') and hasattr(self.scanner, '_batch_timer'):
            try:
                if self.scanner._batch_timer and self.scanner._batch_timer.isActive():
                    if QtCore.QThread.currentThread() == self.scanner._batch_timer.thread():
                        self.scanner._batch_timer.stop()
                    else:
                        QtCore.QMetaObject.invokeMethod(
                            self.scanner._batch_timer, "stop", QtCore.Qt.ConnectionType.QueuedConnection
                        )
            except Exception as e:
                self.logger.error(f"停止批量更新定时器失败: {e}")

    def _init_ui(self):
        """初始化用户界面"""
        # 设置窗口属性，与 AboutDialog 的实现一致
        self.setWindowTitle("")
        # 设置为工具窗口，无边框
        self.setWindowFlags(QtCore.Qt.WindowType.Tool | QtCore.Qt.WindowType.FramelessWindowHint | QtCore.Qt.WindowType.WindowStaysOnTopHint)
        # 确保窗口可以接收鼠标事件
        self.setMouseTracking(True)
        # 确保窗口保持活动状态
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)

        # 使用默认窗口大小
        self.resize(1400, 800)

        # 先设置窗口样式，避免闪烁
        self.setStyleSheet(AppStyles.popup_dialog_style())

        # 扫描频道窗口不需要状态栏
        # 创建进度条用于显示扫描进度
        self.progress_indicator = QtWidgets.QProgressBar()
        self.progress_indicator.setRange(0, 100)
        self.progress_indicator.setValue(0)
        self.progress_indicator.setTextVisible(True)
        self.progress_indicator.setFixedWidth(120)
        # 初始隐藏进度条，开始扫描后再显示
        self.progress_indicator.hide()
        
        # 创建统计信息标签用于显示扫描状态
        self.stats_label = QtWidgets.QLabel("就绪")
        self.stats_label.setStyleSheet(AppStyles.common_label_style())

        # 主布局
        main_widget = QtWidgets.QWidget()
        # 不设置透明背景，让ScanChannelDialog的paintEvent绘制的背景可见
        main_layout = QtWidgets.QVBoxLayout(main_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # 顶部标题栏
        title_bar = QtWidgets.QHBoxLayout()
        title_bar.setContentsMargins(0, 0, 0, 10)
        title_bar.setSpacing(10)
        
        # 标题
        title_label = QtWidgets.QLabel("扫描频道")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #ffffff;")
        title_bar.addWidget(title_label)
        title_bar.addStretch()
        
        # 关闭按钮
        close_button = QtWidgets.QPushButton("关闭")
        close_button.setStyleSheet(AppStyles.common_button_style())
        close_button.setFixedSize(60, 30)
        close_button.clicked.connect(self.close)
        title_bar.addWidget(close_button)
        
        main_layout.addLayout(title_bar)
        
        # 主要内容区域 - 分为上下两部分
        content_layout = QtWidgets.QVBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(10)
        
        # 上部分：频道列表（更大）
        list_widget = QtWidgets.QWidget()
        list_layout = QtWidgets.QVBoxLayout(list_widget)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.setSpacing(10)
        self._setup_channel_list(list_layout)
        content_layout.addWidget(list_widget, 5)
        
        # 下部分：分为左右两部分
        bottom_content_layout = QtWidgets.QHBoxLayout()
        bottom_content_layout.setContentsMargins(0, 0, 0, 0)
        bottom_content_layout.setSpacing(10)
        
        # 左侧：扫描设置（带滚动条）
        scan_scroll = QtWidgets.QScrollArea()
        scan_scroll.setWidgetResizable(True)
        scan_scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        
        scan_widget = QtWidgets.QWidget()
        scan_layout = QtWidgets.QVBoxLayout(scan_widget)
        scan_layout.setContentsMargins(0, 0, 0, 0)
        scan_layout.setSpacing(8)
        self._setup_scan_panel(scan_layout)
        
        scan_scroll.setWidget(scan_widget)
        bottom_content_layout.addWidget(scan_scroll, 1)
        
        # 右侧：频道编辑（带滚动条）
        edit_scroll = QtWidgets.QScrollArea()
        edit_scroll.setWidgetResizable(True)
        edit_scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        
        edit_widget = QtWidgets.QWidget()
        edit_layout = QtWidgets.QVBoxLayout(edit_widget)
        edit_layout.setContentsMargins(0, 0, 0, 0)
        edit_layout.setSpacing(10)
        self._setup_channel_edit(edit_layout)
        
        edit_scroll.setWidget(edit_widget)
        bottom_content_layout.addWidget(edit_scroll, 1)
        
        content_layout.addLayout(bottom_content_layout, 1)
        main_layout.addLayout(content_layout, 1)
        
        # 底部信息栏
        bottom_info_widget = QtWidgets.QWidget()
        bottom_info_layout = QtWidgets.QHBoxLayout(bottom_info_widget)
        bottom_info_layout.setContentsMargins(10, 5, 10, 5)
        bottom_info_layout.setSpacing(10)
        # 增加进度条的高度
        self.progress_indicator.setFixedHeight(30)
        bottom_info_layout.addWidget(self.progress_indicator)
        bottom_info_layout.addWidget(self.stats_label)
        main_layout.addWidget(bottom_info_widget)
        
        # QDialog使用setLayout直接设置布局
        self.setLayout(main_layout)

    def _save_network_settings(self):
        """保存网络设置到配置文件（提取的重复代码）"""
        # 使用配置变更上下文保存网络设置
        from utils.config_notifier import config_change_context
        with config_change_context("Network", "url"):
            enable_retry = self.enable_retry_checkbox.isChecked()
            self.config.save_network_settings(
                self.ip_range_input.text(),
                self.timeout_input.value(),
                self.thread_count_input.value(),
                self.user_agent_input.text(),
                self.referer_input.text(),
                enable_retry,
                enable_retry  # 简化后，启用重试即默认启用循环行为
            )

    def _setup_scan_panel(self, parent: QtWidgets.QLayout) -> None:
        """配置扫描面板"""
        scan_group = QtWidgets.QGroupBox("扫描设置")
        self.scan_group = scan_group  # 设置为属性以便语言管理器访问
        scan_layout = QtWidgets.QVBoxLayout()
        scan_layout.setContentsMargins(10, 10, 10, 10)
        scan_layout.setSpacing(8)

        # 设置扫描按钮
        self._setup_scan_buttons()

        # 添加所有控件到布局
        self._add_scan_controls_to_layout(scan_layout)

        # 设置扫描面板样式，使用专门的样式函数
        scan_group.setStyleSheet(AppStyles.scan_window_style())

        scan_group.setLayout(scan_layout)
        parent.addWidget(scan_group)

    def _setup_scan_inputs(self):
        """设置扫描输入控件"""
        # IP地址输入
        self.ip_range_input = QtWidgets.QLineEdit()
        self.ip_range_input.editingFinished.connect(
            lambda: self._save_network_settings()
        )

        # 超时时间设置
        self._setup_timeout_input()

        # 线程数设置
        self._setup_thread_input()

        # User-Agent设置
        self._setup_user_agent_input()

        # Referer设置
        self._setup_referer_input()

    def _setup_timeout_input(self):
        """设置超时时间输入控件"""
        timeout_layout = QtWidgets.QHBoxLayout()
        timeout_label = QtWidgets.QLabel("设置扫描超时时间（秒）")
        self.timeout_description_label = timeout_label
        timeout_layout.addWidget(timeout_label)
        self.timeout_input = QtWidgets.QSpinBox()
        self.timeout_input.setRange(1, 60)
        # 从配置文件加载默认值，如果没有则使用配置管理器的默认值
        try:
            settings = self.config.load_network_settings()
            default_timeout = settings['timeout']
        except Exception:
            default_timeout = 30  # 配置管理器的默认值
        self.timeout_input.setValue(default_timeout)
        self.timeout_input.setSuffix(" 秒")
        timeout_layout.addWidget(self.timeout_input)
        self.timeout_input.valueChanged.connect(
            lambda: self._save_network_settings()
        )
        self.timeout_layout = timeout_layout

    def _setup_thread_input(self):
        """设置线程数输入控件"""
        thread_layout = QtWidgets.QHBoxLayout()
        thread_label = QtWidgets.QLabel("设置扫描使用的线程数量")
        self.thread_count_label = thread_label
        thread_layout.addWidget(thread_label)
        self.thread_count_input = QtWidgets.QSpinBox()
        self.thread_count_input.setRange(1, 100)
        # 从配置文件加载默认值，如果没有则使用配置管理器的默认值
        try:
            settings = self.config.load_network_settings()
            default_threads = settings['threads']
        except Exception:
            default_threads = 5  # 配置管理器的默认值
        self.thread_count_input.setValue(default_threads)
        thread_layout.addWidget(self.thread_count_input)
        self.thread_count_input.valueChanged.connect(
            lambda: self._save_network_settings()
        )
        self.thread_layout = thread_layout

    def _setup_user_agent_input(self):
        """设置User-Agent输入控件"""
        user_agent_layout = QtWidgets.QHBoxLayout()
        user_agent_label = QtWidgets.QLabel("User-Agent:")
        self.user_agent_label = user_agent_label
        user_agent_layout.addWidget(user_agent_label)
        self.user_agent_input = QtWidgets.QLineEdit()
        self.user_agent_input.setPlaceholderText("可选，留空使用默认")
        user_agent_layout.addWidget(self.user_agent_input)
        self.user_agent_input.textChanged.connect(
            lambda: self._save_network_settings()
        )
        self.user_agent_layout = user_agent_layout

    def _setup_referer_input(self):
        """设置Referer输入控件"""
        referer_layout = QtWidgets.QHBoxLayout()
        referer_label = QtWidgets.QLabel("Referer:")
        self.referer_label = referer_label
        referer_layout.addWidget(referer_label)
        self.referer_input = QtWidgets.QLineEdit()
        self.referer_input.setPlaceholderText("可选，留空不使用")
        referer_layout.addWidget(self.referer_input)
        self.referer_input.textChanged.connect(
            lambda: self._save_network_settings()
        )
        self.referer_layout = referer_layout

    def _setup_scan_retry_options(self):
        """设置扫描重试选项"""
        retry_layout = QtWidgets.QHBoxLayout()
        retry_label = QtWidgets.QLabel("扫描重试选项：")
        self.retry_label = retry_label
        retry_layout.addWidget(retry_label)

        # 是否启用智能重试扫描（基于失败原因，自动循环直到无新频道）
        self.enable_retry_checkbox = QtWidgets.QCheckBox("启用智能重试扫描")
        self.enable_retry_checkbox.setToolTip(
            "基于失败原因智能重试：只重试超时、连接失败等临时错误，"
            "不重试TCP失败、404等永久错误。启用后会自动循环重试直到没有新的有效频道"
        )
        self.enable_retry_checkbox.setChecked(False)
        retry_layout.addWidget(self.enable_retry_checkbox)
        retry_layout.addStretch()

        # 连接复选框状态变化信号，保存设置
        self.enable_retry_checkbox.stateChanged.connect(
            lambda: self._save_scan_retry_settings()
        )

        # 加载保存的重试扫描设置
        self._load_scan_retry_settings()

        self.retry_layout = retry_layout

    def _save_scan_retry_settings(self):
        """保存重试扫描设置到配置文件"""
        enable_retry = self.enable_retry_checkbox.isChecked()
        # 简化后，启用重试即默认启用循环行为
        self.config.save_scan_retry_settings(enable_retry, enable_retry)

    def _load_scan_retry_settings(self):
        """加载重试扫描设置"""
        try:
            settings = self.config.load_scan_retry_settings()
            enable_retry = settings['enable_retry']
            self.enable_retry_checkbox.setChecked(enable_retry)
        except Exception as e:
            self.logger.error(f"加载重试扫描设置失败: {e}")

    def _setup_mapping_options(self):
        """设置映射功能选项"""
        mapping_layout = QtWidgets.QHBoxLayout()
        mapping_label = QtWidgets.QLabel("映射功能选项：")
        self.mapping_label = mapping_label
        mapping_layout.addWidget(mapping_label)

        # 是否启用频道映射
        self.enable_mapping_checkbox = QtWidgets.QCheckBox("启用频道映射")
        self.enable_mapping_checkbox.setToolTip(
            "启用后，扫描到的频道会根据映射文件自动匹配频道名称、Logo、分组等信息"
        )
        self.enable_mapping_checkbox.setChecked(True)
        mapping_layout.addWidget(self.enable_mapping_checkbox)
        mapping_layout.addStretch()

        # 连接复选框状态变化信号，保存设置
        self.enable_mapping_checkbox.stateChanged.connect(
            lambda: self._save_mapping_settings()
        )

        # 加载保存的映射设置
        self._load_mapping_settings()

        self.mapping_layout = mapping_layout

    def _save_mapping_settings(self):
        """保存映射设置到配置文件"""
        from models.channel_mappings import mapping_manager
        enable_mapping = self.enable_mapping_checkbox.isChecked()
        self.config.save_mapping_settings(enable_mapping)
        # 同时更新 mapping_manager 的状态
        mapping_manager.enable_mapping = enable_mapping

    def _load_mapping_settings(self):
        """加载映射设置"""
        from models.channel_mappings import mapping_manager
        try:
            settings = self.config.load_mapping_settings()
            enable_mapping = settings['enable_mapping']
            self.enable_mapping_checkbox.setChecked(enable_mapping)
            # 同时更新 mapping_manager 的状态
            mapping_manager.enable_mapping = enable_mapping
        except Exception as e:
            self.logger.error(f"加载映射设置失败: {e}")

    def _setup_scan_buttons(self):
        """设置扫描按钮"""
        # 扫描控制按钮
        self.btn_scan = QtWidgets.QPushButton("完整扫描")
        self.btn_scan.setStyleSheet(AppStyles.common_button_style())
        self.btn_scan.setMinimumHeight(32)  # 减少按钮高度

        # 新增追加扫描按钮
        self.btn_append_scan = QtWidgets.QPushButton("追加扫描")
        self.btn_append_scan.setStyleSheet(AppStyles.common_button_style())
        self.btn_append_scan.setMinimumHeight(32)  # 减少按钮高度
        self.btn_append_scan.setToolTip("不清空现有列表，扫描到的有效频道直接追加到列表末尾")

        # 新增直接生成列表按钮
        self.btn_generate = QtWidgets.QPushButton("直接生成列表")
        self.btn_generate.setStyleSheet(AppStyles.common_button_style())
        self.btn_generate.setMinimumHeight(32)  # 减少按钮高度

        # 使用水平布局让按钮并排显示，自适应宽度
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addWidget(self.btn_scan, 1)
        button_layout.addSpacing(4)
        button_layout.addWidget(self.btn_append_scan, 1)
        button_layout.addSpacing(4)
        button_layout.addWidget(self.btn_generate, 1)
        button_layout.addStretch()

        self.scan_button_layout = button_layout

    def _add_scan_controls_to_layout(self, scan_layout):
        """添加扫描控件到布局"""
        # 先设置所有输入控件
        self._setup_scan_inputs()
        
        # 设置扫描重试选项
        self._setup_scan_retry_options()
        
        # 设置映射功能选项
        self._setup_mapping_options()

        # 地址设置组
        address_group = QtWidgets.QGroupBox("地址设置")
        address_group_layout = QtWidgets.QVBoxLayout()
        address_group_layout.setContentsMargins(10, 15, 10, 10)
        address_group_layout.setSpacing(8)

        address_format_label = QtWidgets.QLabel("地址格式：")
        self.address_format_label = address_format_label
        address_example_label = QtWidgets.QLabel(
            "示例：http://192.168.1.1:1234/rtp/10.10.[1-20].[1-20]:5002   [1-20]表示范围"
        )
        self.address_example_label = address_example_label
        address_example_label.setWordWrap(True)
        address_example_label.setStyleSheet("font-size: 11px; color: #999;")
        input_address_label = QtWidgets.QLabel("输入地址：")
        self.input_address_label = input_address_label
        
        address_group_layout.addWidget(address_format_label)
        address_group_layout.addWidget(address_example_label)
        address_group_layout.addWidget(input_address_label)
        address_group_layout.addWidget(self.ip_range_input)
        address_group.setLayout(address_group_layout)
        
        # 扫描设置组
        scan_settings_group = QtWidgets.QGroupBox("扫描设置")
        scan_settings_layout = QtWidgets.QVBoxLayout()
        scan_settings_layout.setContentsMargins(10, 15, 10, 10)
        scan_settings_layout.setSpacing(8)
        
        # 添加超时时间设置
        scan_settings_layout.addLayout(self.timeout_layout)
        
        # 添加线程数设置
        scan_settings_layout.addLayout(self.thread_layout)
        
        # 添加User-Agent设置
        scan_settings_layout.addLayout(self.user_agent_layout)
        
        # 添加Referer设置
        scan_settings_layout.addLayout(self.referer_layout)
        
        scan_settings_group.setLayout(scan_settings_layout)
        
        # 选项组
        options_group = QtWidgets.QGroupBox("选项")
        options_layout = QtWidgets.QVBoxLayout()
        options_layout.setContentsMargins(10, 15, 10, 10)
        options_layout.setSpacing(8)
        
        # 添加重试选项
        options_layout.addLayout(self.retry_layout)
        
        # 添加映射选项
        options_layout.addLayout(self.mapping_layout)
        
        options_group.setLayout(options_layout)
        
        # 添加所有组到主布局
        scan_layout.addWidget(address_group)
        scan_layout.addWidget(scan_settings_group)
        scan_layout.addWidget(options_group)
        scan_layout.addStretch()
        scan_layout.addLayout(self.scan_button_layout)

    def _setup_channel_list(self, parent: QtWidgets.QLayout) -> None:
        """配置频道列表"""
        # 导入样式
        # 频道列表区域
        list_group = QtWidgets.QGroupBox("频道列表")
        self.list_group = list_group  # 设置为属性以便语言管理器访问
        list_layout = QtWidgets.QVBoxLayout()
        list_layout.setContentsMargins(15, 15, 15, 15)  # 增加边距，提升美观度
        list_layout.setSpacing(10)  # 增加间距，提升美观度

        # 工具栏
        toolbar = QtWidgets.QHBoxLayout()
        toolbar.setContentsMargins(0, 0, 0, 8)  # 减少底部空间

        # 有效性检测按钮
        self.btn_validate = QtWidgets.QPushButton("检测有效性")
        self.btn_validate.setStyleSheet(AppStyles.common_button_style())
        self.btn_validate.setFixedHeight(32)  # 减少按钮高度

        # 隐藏无效项按钮
        self.btn_hide_invalid = QtWidgets.QPushButton("隐藏无效项")
        self.btn_hide_invalid.setStyleSheet(AppStyles.common_button_style())
        self.btn_hide_invalid.setFixedHeight(32)  # 减少按钮高度
        self.btn_hide_invalid.setEnabled(False)

        # 智能排序按钮
        self.btn_smart_sort = QtWidgets.QPushButton("智能排序")
        self.btn_smart_sort.setStyleSheet(AppStyles.common_button_style())
        self.btn_smart_sort.setFixedHeight(32)  # 减少按钮高度
        self.btn_smart_sort.setEnabled(True)
        self.btn_smart_sort.clicked.connect(
            lambda: self.model.sort_channels()
        )

        # 排序配置按钮
        self.btn_sort_config = QtWidgets.QPushButton(
            self.language_manager.tr('sort_config_button', 'Sort Config')
        )
        self.btn_sort_config.setStyleSheet(AppStyles.common_button_style())
        self.btn_sort_config.setFixedHeight(32)  # 减少按钮高度
        self.btn_sort_config.setEnabled(True)
        self.btn_sort_config.clicked.connect(self._show_sort_config)

        toolbar.addWidget(self.btn_validate)
        toolbar.addSpacing(4)
        toolbar.addWidget(self.btn_hide_invalid)
        toolbar.addSpacing(4)
        toolbar.addWidget(self.btn_smart_sort)
        toolbar.addSpacing(4)
        toolbar.addWidget(self.btn_sort_config)
        toolbar.addStretch()
        list_layout.addLayout(toolbar)

        # 频道列表视图
        self.channel_list = QtWidgets.QTableView()
        self.channel_list.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.channel_list.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.channel_list.verticalHeader().setVisible(False)
        # 启用水平滚动条
        self.channel_list.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.channel_list.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        # 增加频道列表的最小宽度
        self.channel_list.setMinimumWidth(600)

        # 确保模型存在并正确设置到视图中
        if not hasattr(self, 'model') or not self.model:
            self.model = ChannelListModel()
            # 设置语言管理器
            if hasattr(self, 'language_manager') and self.language_manager:
                self.model.set_language_manager(self.language_manager)

        # 关键：始终将模型设置到视图中，确保连接正确
        self.channel_list.setModel(self.model)

        # 使用与主窗口一致的列表样式
        self.channel_list.setStyleSheet(AppStyles.list_style())

        # 设置表头
        self.header = self.channel_list.horizontalHeader()
        self.header.setStretchLastSection(False)  # 禁用最后列自动拉伸
        self.header.setMinimumSectionSize(30)  # 最小列宽
        self.header.setMaximumSectionSize(1000)  # 最大列宽

        # 设置表头属性
        self.header.setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.header.setDefaultSectionSize(100)  # 默认列宽

        # 启用表头点击排序
        self.header.setSectionsClickable(True)
        self.header.setSortIndicatorShown(True)
        self.header.setSortIndicator(-1, QtCore.Qt.SortOrder.AscendingOrder)  # 初始无排序
        self.header.sectionClicked.connect(self._on_header_clicked)

        # 强制立即调整列宽，确保初始状态正确
        self.header.resizeSections(QtWidgets.QHeaderView.ResizeMode.ResizeToContents)

        # 启用拖放排序功能 - 改进拖拽体验
        self.channel_list.setDragEnabled(True)
        self.channel_list.setAcceptDrops(True)
        self.channel_list.setDragDropOverwriteMode(False)
        self.channel_list.setDragDropMode(QtWidgets.QAbstractItemView.DragDropMode.InternalMove)
        self.channel_list.setDefaultDropAction(QtCore.Qt.DropAction.MoveAction)
        self.channel_list.setDropIndicatorShown(True)  # 显示拖拽指示器

        # 添加频道列表拖拽提示
        self.channel_drag_hint_label = QtWidgets.QLabel("")
        colors = AppStyles._get_colors()
        self.channel_drag_hint_label.setStyleSheet(f"""
            QLabel {{
                color: {colors['accent']};
                font-size: 12px;
                padding: 8px 12px;
                background-color: {colors['light']};
                border-radius: 6px;
                font-weight: 500;
                border: 1px solid {colors['mid']};
                margin-bottom: 10px;
            }}
        """)
        self.channel_drag_hint_label.setWordWrap(True)
        list_layout.addWidget(self.channel_drag_hint_label)

        # 设置频道列表拖拽提示文本
        self.update_channel_drag_hint()

        # 添加右键菜单
        self.channel_list.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.channel_list.customContextMenuRequested.connect(self._show_channel_context_menu)

        # 连接选择事件
        self.channel_list.selectionModel().selectionChanged.connect(self._on_channel_selected)

        # 设置频道列表为主要内容，占据大部分空间
        list_layout.addWidget(self.channel_list)
        
        # 设置频道列表面板样式
        colors = AppStyles._get_colors()
        list_group.setStyleSheet(f"""
            QGroupBox {{
                background-color: {colors['alternate_base']};
                color: {colors['window_text']};
                border: 1px solid {colors['mid']};
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 16px;
                font-weight: 600;
                font-size: 13px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
                color: {colors['window_text']};
                font-weight: 600;
            }}
        """)

        list_group.setLayout(list_layout)
        parent.addWidget(list_group)

    def _setup_channel_edit(self, parent: QtWidgets.QLayout) -> None:
        """配置频道编辑区域"""
        # 导入样式
        edit_group = QtWidgets.QGroupBox("频道编辑")
        edit_layout = QtWidgets.QGridLayout()
        edit_layout.setContentsMargins(15, 15, 15, 15)
        edit_layout.setSpacing(10)

        # 频道名称
        self.edit_name_label = QtWidgets.QLabel("频道名称:")
        self.edit_name_label.setStyleSheet(AppStyles.common_label_style())
        self.edit_name = QtWidgets.QLineEdit()
        self.edit_name.setStyleSheet(AppStyles.common_line_edit_style())
        self.edit_name.setMaximumWidth(300)

        # 频道分组
        self.edit_group_label = QtWidgets.QLabel("频道分组:")
        self.edit_group_label.setStyleSheet(AppStyles.common_label_style())
        self.edit_group = QtWidgets.QLineEdit()
        self.edit_group.setStyleSheet(AppStyles.common_line_edit_style())
        self.edit_group.setMaximumWidth(200)

        # 频道URL
        self.edit_url_label = QtWidgets.QLabel("频道URL:")
        self.edit_url_label.setStyleSheet(AppStyles.common_label_style())
        self.edit_url = QtWidgets.QLineEdit()
        self.edit_url.setStyleSheet(AppStyles.common_line_edit_style())
        self.edit_url.setMaximumWidth(400)

        # TVG-ID
        self.edit_tvg_id_label = QtWidgets.QLabel("TVG-ID:")
        self.edit_tvg_id_label.setStyleSheet(AppStyles.common_label_style())
        self.edit_tvg_id = QtWidgets.QLineEdit()
        self.edit_tvg_id.setStyleSheet(AppStyles.common_line_edit_style())
        self.edit_tvg_id.setMaximumWidth(200)

        # Logo URL
        self.edit_logo_label = QtWidgets.QLabel("Logo URL:")
        self.edit_logo_label.setStyleSheet(AppStyles.common_label_style())
        self.edit_logo = QtWidgets.QLineEdit()
        self.edit_logo.setStyleSheet(AppStyles.common_line_edit_style())
        self.edit_logo.setMaximumWidth(400)

        # 添加控件到网格布局
        edit_layout.addWidget(self.edit_name_label, 0, 0)
        edit_layout.addWidget(self.edit_name, 0, 1)
        edit_layout.addWidget(self.edit_group_label, 1, 0)
        edit_layout.addWidget(self.edit_group, 1, 1)
        edit_layout.addWidget(self.edit_url_label, 2, 0)
        edit_layout.addWidget(self.edit_url, 2, 1)
        edit_layout.addWidget(self.edit_tvg_id_label, 3, 0)
        edit_layout.addWidget(self.edit_tvg_id, 3, 1)
        edit_layout.addWidget(self.edit_logo_label, 4, 0)
        edit_layout.addWidget(self.edit_logo, 4, 1)

        # 保存按钮
        button_layout = QtWidgets.QHBoxLayout()
        self.btn_save_channel = QtWidgets.QPushButton("保存修改")
        self.btn_save_channel.setStyleSheet(AppStyles.common_button_style())
        self.btn_save_channel.setFixedHeight(32)
        self.btn_save_channel.clicked.connect(self._on_save_channel)
        button_layout.addWidget(self.btn_save_channel)
        button_layout.addStretch()
        edit_layout.addLayout(button_layout, 5, 0, 1, 2)

        # 设置编辑面板样式
        colors = AppStyles._get_colors()
        edit_group.setStyleSheet(f"""
            QGroupBox {{
                background-color: {colors['alternate_base']};
                color: {colors['window_text']};
                border: 1px solid {colors['mid']};
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 16px;
                font-weight: 600;
                font-size: 13px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
                color: {colors['window_text']};
                font-weight: 600;
            }}
        """)

        edit_group.setLayout(edit_layout)
        parent.addWidget(edit_group)

    def _on_channel_selected(self, selected, deselected):
        """处理频道选择事件"""
        indexes = selected.indexes()
        if not indexes:
            return

        row = indexes[0].row()
        channel = self.model.get_channel(row)
        if channel:
            # 填充编辑区域
            self.edit_name.setText(channel.get('name', ''))
            self.edit_group.setText(channel.get('group', ''))
            self.edit_url.setText(channel.get('url', ''))
            self.edit_tvg_id.setText(channel.get('tvg_id', ''))
            self.edit_logo.setText(channel.get('logo', ''))

    def _on_save_channel(self):
        """处理保存频道修改"""
        indexes = self.channel_list.selectionModel().selectedIndexes()
        if not indexes:
            return

        row = indexes[0].row()
        channel_info = {
            'name': self.edit_name.text(),
            'group': self.edit_group.text(),
            'url': self.edit_url.text(),
            'tvg_id': self.edit_tvg_id.text(),
            'logo': self.edit_logo.text()
        }

        self.model.update_channel(row, channel_info)
        # 刷新列表
        self.channel_list.viewport().update()

    def _show_channel_context_menu(self, pos):
        """显示频道列表的右键菜单"""
        index = self.channel_list.indexAt(pos)
        if not index.isValid():
            return

        menu = QtWidgets.QMenu()

        # 获取选中频道的URL和名称
        url = self.model.data(self.model.index(index.row(), 3))  # URL在第3列
        name = self.model.data(self.model.index(index.row(), 1))  # 名称在第1列

        # 添加复制频道名菜单项
        copy_name_action = QtGui.QAction("复制频道名", self)
        copy_name_action.triggered.connect(lambda: self._copy_channel_name(name))
        menu.addAction(copy_name_action)

        # 添加复制URL菜单项
        copy_url_action = QtGui.QAction("复制URL", self)
        copy_url_action.triggered.connect(lambda: self._copy_channel_url(url))
        menu.addAction(copy_url_action)

        # 添加复制TVG-ID菜单项
        tvg_id = self.model.data(self.model.index(index.row(), 8))  # TVG-ID在第8列
        copy_tvg_id_action = QtGui.QAction("复制TVG-ID", self)
        copy_tvg_id_action.triggered.connect(lambda: self._copy_channel_tvg_id(tvg_id))
        menu.addAction(copy_tvg_id_action)

        # 添加复制分组菜单项
        group = self.model.data(self.model.index(index.row(), 4))  # 分组在第4列
        copy_group_action = QtGui.QAction("复制分组", self)
        copy_group_action.triggered.connect(lambda: self._copy_channel_group(group))
        menu.addAction(copy_group_action)

        menu.addSeparator()

        # 添加删除频道菜单项
        delete_action = QtGui.QAction("删除频道", self)
        delete_action.triggered.connect(lambda: self._delete_selected_channel(index))
        menu.addAction(delete_action)

        # 显示菜单
        menu.exec(self.channel_list.viewport().mapToGlobal(pos))

    def _copy_channel_url(self, url):
        """复制频道URL到剪贴板"""
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText(url)

    def _copy_channel_name(self, name):
        """复制频道名到剪贴板"""
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText(name)

    def _copy_channel_tvg_id(self, tvg_id):
        """复制TVG-ID到剪贴板"""
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText(tvg_id)

    def _copy_channel_group(self, group):
        """复制分组到剪贴板"""
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText(group)

    def _delete_selected_channel(self, index):
        """删除选中的频道"""
        from utils.error_handler import show_confirm
        if show_confirm("确认删除", "确定要删除选中的频道吗？", parent=self):
            self.model.remove_channel(index.row())

    def _show_sort_config(self):
        """显示排序配置对话框"""
        pass

    def _on_header_clicked(self, logical_index):
        """处理表头点击事件"""
        pass

    def update_channel_drag_hint(self):
        """更新频道列表拖拽提示文本"""
        self.channel_drag_hint_label.setText("提示：拖动频道可以调整顺序")

    def _init_main_window(self):
        """初始化主窗口的后续设置"""
        # 确保模型存在
        if not hasattr(self, 'model') or not self.model:
            self.model = ChannelListModel()
            # 设置语言管理器
            if hasattr(self, 'language_manager') and self.language_manager:
                self.model.set_language_manager(self.language_manager)
        
        self.model.setParent(self)

        # 初始化进度条管理器（必须在 init_controllers 之前）
        self.progress_manager = init_progress_manager(
            self.progress_indicator,
            None
        )

        self.init_controllers()

        self.ui_optimizer = get_ui_optimizer()
        self.error_handler = init_global_error_handler(self)

        self.ui_optimizer.optimize_table_view(
            self.channel_list
        )

        self._load_config()

        # 样式已在_init_ui中设置，这里只需连接信号和注册处理器
        self._connect_signals()
        self._register_cleanup_handlers()
        self._register_config_observers()

    def init_controllers(self):
        """初始化所有控制器"""
        log_ui_info("=== 初始化控制器 ===")

        if not hasattr(self, 'scanner') or self.scanner is None:
            log_scan_info("创建ScannerController实例")
            self.scanner = ScannerController(self.model, self)
            log_scan_info(f"ScannerController创建完成: {self.scanner}")
        else:
            log_scan_info(f"ScannerController已存在: {self.scanner}")

        self._connect_progress_signals()

        log_ui_info("=== 控制器初始化完成 ===")

    def _connect_progress_signals(self):
        """连接进度条更新信号"""
        # 使用进度条管理器注册扫描进度回调
        self.progress_manager.register_progress_callback(
            'scan',
            self._update_scan_progress
        )

        # 启动自动更新
        self.progress_manager.start_auto_update(
            self._update_scan_progress,
            interval=500
        )

        log_ui_info("进度条信号已连接")

    def _update_scan_progress(self):
        """更新扫描进度（使用进度条管理器）"""
        try:
            if hasattr(self.scanner, 'stats'):
                stats = self.scanner.stats
                total = stats.get('total', 0)
                valid = stats.get('valid', 0)
                invalid = stats.get('invalid', 0)

                current = valid + invalid

                if total > 0:
                    # 使用进度条管理器更新进度
                    self.progress_manager.update_progress_from_stats(
                        current,
                        total,
                        f"扫描进度: {current}/{total}"
                    )

                    # 检查是否完成
                    if current >= total and total > 0:
                        self.progress_manager.complete_progress("扫描完成")
                        self._set_scan_button_text('full_scan', '完整扫描')
                        self._set_append_scan_button_text('append_scan', '追加扫描')

        except AttributeError as e:
            log_scan_warning(f"扫描进度更新失败: {e}")
        except Exception as e:
            log_scan_warning(f"扫描进度更新时发生意外错误: {e}")

    def _load_config(self):
        """加载保存的配置到UI"""
        try:
            settings = self.config.load_network_settings()

            if settings['url']:
                self.ip_range_input.setText(settings['url'])

            self.timeout_input.setValue(int(settings['timeout']))
            self.thread_count_input.setValue(int(settings['threads']))

            if settings['user_agent']:
                self.user_agent_input.setText(settings['user_agent'])

            if settings['referer']:
                self.referer_input.setText(settings['referer'])

            # 加载重试设置（简化后只加载 enable_retry）
            if 'enable_retry' in settings:
                self.enable_retry_checkbox.setChecked(settings['enable_retry'])

            language_code = self.config.load_language_settings()

            if hasattr(self, 'language_manager'):
                self.language_manager.set_language(language_code)

        except Exception as e:
            log_config_error(f"加载配置失败: {e}")
            self.timeout_input.setValue(10)
            self.thread_count_input.setValue(5)

    def _register_config_observers(self):
        """注册配置变更观察者"""
        # 注册网络配置变更观察者
        register_config_observer("Network.*", self._on_network_config_changed)
        register_config_observer("ScanRetry.*", self._on_scan_retry_config_changed)
        register_config_observer("Language.current_language", self._on_language_config_changed)

        log_config_info("配置变更观察者已注册")

    def _on_network_config_changed(self, section, key, old_value, new_value):
        """处理网络配置变更"""
        log_config_info(f"网络配置变更: {section}.{key} = {old_value} -> {new_value}")

        # 更新对应的UI控件
        if key == 'url':
            self.ip_range_input.setText(new_value)
        elif key == 'timeout':
            self.timeout_input.setValue(int(new_value))
        elif key == 'threads':
            self.thread_count_input.setValue(int(new_value))
        elif key == 'user_agent':
            self.user_agent_input.setText(new_value)
        elif key == 'referer':
            self.referer_input.setText(new_value)
        elif key == 'enable_retry':
            self.enable_retry_checkbox.setChecked(str(new_value).lower() == 'true')

    def _on_scan_retry_config_changed(self, section, key, old_value, new_value):
        """处理扫描重试配置变更"""
        log_config_info(f"扫描重试配置变更: {section}.{key} = {old_value} -> {new_value}")

        if key == 'enable_retry':
            self.enable_retry_checkbox.setChecked(str(new_value).lower() == 'true')

    def _on_language_config_changed(self, section, key, old_value, new_value):
        """处理语言配置变更"""
        log_config_info(f"语言配置变更: {section}.{key} = {old_value} -> {new_value}")

        if hasattr(self, 'language_manager'):
            self.language_manager.set_language(new_value)
            self.language_manager.update_ui_texts(self)

    def _connect_signals(self):
        """连接所有信号和槽"""
        log_ui_info("=== 开始连接信号 ===")

        # 注意：channel_list的selectionChanged信号已经在_setup_channel_list中连接
        # 这里不需要重复连接

        safe_connect_button(self.btn_scan, self._on_scan_clicked)
        safe_connect_button(self.btn_append_scan, self._on_append_scan_clicked)

        safe_connect_button(self.btn_validate, self._on_validate_clicked)
        safe_connect_button(self.btn_hide_invalid, self._on_hide_invalid_clicked)
        safe_connect_button(self.btn_generate, self._on_generate_clicked)

        # 连接扫描器信号
        log_ui_info("连接扫描器信号...")

        # 检查scanner对象是否存在
        if not hasattr(self, 'scanner') or self.scanner is None:
            log_ui_error("scanner对象不存在，无法连接信号")
            return

        log_ui_info(f"scanner对象: {self.scanner}")

        try:
            self.scanner.channel_found.connect(self._on_channel_found)
            log_ui_info("channel_found信号已连接")
        except Exception as e:
            log_ui_error(f"连接channel_found信号失败: {e}")

        try:
            self.scanner.scan_completed.connect(self._on_scan_completed)
            log_ui_info("scan_completed信号已连接到 _on_scan_completed")
        except Exception as e:
            log_ui_error(f"连接scan_completed信号失败: {e}")

        try:
            self.scanner.stats_updated.connect(
                self._update_stats_display,
                QtCore.Qt.ConnectionType.QueuedConnection
            )
            log_ui_info("stats_updated信号已连接")
        except Exception as e:
            log_ui_error(f"连接stats_updated信号失败: {e}")

        try:
            self.scanner.channel_validated.connect(self._on_channel_validated)
            log_ui_info("channel_validated信号已连接")
        except Exception as e:
            log_ui_error(f"连接channel_validated信号失败: {e}")

        log_ui_info("=== 信号连接完成 ===")

    def _on_scan_clicked(self):
        """处理扫描按钮点击事件"""
        if not hasattr(self, 'scanner') or self.scanner is None:
            log_ui_error("扫描器未初始化，无法执行扫描")
            return
        if self.scanner.is_scanning():
            self.scanner.stop_scan()
            self._set_scan_button_text('full_scan', '完整扫描')
            self._set_append_scan_button_text('append_scan', '追加扫描')
        else:
            url = self.ip_range_input.text()
            if not url.strip():
                log_ui_warning("请输入扫描地址")
                # 扫描频道窗口没有状态栏，直接在日志中记录
                return

            QtCore.QTimer.singleShot(0, lambda: self._start_scan_delayed(url, clear_list=True))

    def _on_append_scan_clicked(self):
        """处理追加扫描按钮点击事件"""
        if not hasattr(self, 'scanner') or self.scanner is None:
            log_ui_error("扫描器未初始化，无法执行扫描")
            return
        if self.scanner.is_scanning():
            self.scanner.stop_scan()
            self._set_scan_button_text('full_scan', '完整扫描')
            self._set_append_scan_button_text('append_scan', '追加扫描')
        else:
            url = self.ip_range_input.text()
            if not url.strip():
                log_ui_warning("请输入扫描地址")
                # 扫描频道窗口没有状态栏，直接在日志中记录
                return

            QtCore.QTimer.singleShot(0, lambda: self._start_scan_delayed(url, clear_list=False))

    def _start_scan_delayed(self, url, clear_list=True):
        """延迟启动扫描，避免UI阻塞"""
        if not hasattr(self, 'scanner') or self.scanner is None:
            log_ui_error("扫描器未初始化，无法启动扫描")
            return
        if clear_list:
            self.model.clear()
            log_scan_info("开始完整扫描，清空现有列表")
        else:
            log_scan_info("开始追加扫描，保留现有列表")

        timeout = self.timeout_input.value()
        threads = self.thread_count_input.value()

        self.scanner.start_scan(url, threads, timeout)

        if clear_list:
            self._set_scan_button_text('stop_scan', '停止扫描')
        else:
            self._set_append_scan_button_text('stop_scan', '停止扫描')

    def _set_button_text(self, button, translation_key, default_text):
        """通用按钮文本设置函数"""
        if hasattr(self, 'language_manager') and self.language_manager:
            button.setText(self.language_manager.tr(translation_key, default_text))
        else:
            button.setText(default_text)

    def _set_scan_button_text(self, translation_key, default_text):
        """设置扫描按钮文本"""
        self._set_button_text(self.btn_scan, translation_key, default_text)

    def _set_append_scan_button_text(self, translation_key, default_text):
        """设置追加扫描按钮文本"""
        self._set_button_text(self.btn_append_scan, translation_key, default_text)

    def _on_validate_clicked(self):
        """处理有效性检测按钮点击事件"""
        if not hasattr(self, 'scanner') or self.scanner is None:
            log_ui_error("扫描器未初始化，无法执行验证")
            return
        if not self.model.rowCount():
            self.logger.warning("请先加载列表")
            return

        if not hasattr(self.scanner, 'is_validating') or not self.scanner.is_validating:
            timeout = self.timeout_input.value()
            threads = self.thread_count_input.value()
            user_agent = self.user_agent_input.text()
            referer = self.referer_input.text()
            self.scanner.start_validation(
                self.model,
                threads,
                timeout,
                user_agent,
                referer
            )
            self.btn_validate.setText("停止检测")
            self.btn_hide_invalid.setEnabled(True)
            self.btn_hide_invalid.setStyleSheet(
                AppStyles.button_style(active=True)
            )
        else:
            self.scanner.stop_validation()
            self.btn_validate.setText("检测有效性")

    def _on_channel_validated(self, index, valid, latency, resolution):
        """处理频道验证结果"""
        channel_info = {
            'valid': valid,
            'latency': latency,
            'resolution': resolution,
            'status': '有效' if valid else '无效'
        }

        self.model.update_channel(index, channel_info)

    def _on_generate_clicked(self):
        """处理直接生成列表按钮点击事件"""
        url = self.ip_range_input.text()
        if not url.strip():
            self.logger.warning("请输入生成地址")
            # 扫描频道窗口没有状态栏，直接在日志中记录
            return

        self.model.clear()

        url_parser = URLRangeParser()
        url_generator = url_parser.parse_url(url)

        count = 0
        for batch in url_generator:
            for url in batch:
                channel = {
                    'name': f"生成频道-{count+1}",
                    'group': "生成频道",
                    'url': url,
                    'valid': False,
                    'latency': 0,
                    'status': '未检测'
                }
                self.model.add_channel(channel)
                count += 1

        # 扫描频道窗口没有状态栏，直接在日志中记录
        self.logger.info(f"已生成 {count} 个频道")

    def _on_hide_invalid_clicked(self):
        """处理隐藏无效项按钮点击事件"""
        if self.btn_hide_invalid.text() == "隐藏无效项":
            self.model.hide_invalid()
            self.btn_hide_invalid.setText("恢复隐藏项")
        else:
            self.model.show_all()
            self.btn_hide_invalid.setText("隐藏无效项")

    def save_before_exit(self):
        """退出前保存配置"""
        try:
            if hasattr(self, 'config'):
                self.config.save_network_settings(
                    url=self.ip_range_input.text(),
                    timeout=self.timeout_input.value(),
                    threads=self.thread_count_input.value(),
                    user_agent=self.user_agent_input.text(),
                    referer=self.referer_input.text(),
                    enable_retry=self.enable_retry_checkbox.isChecked(),
                    loop_scan=self.enable_retry_checkbox.isChecked()
                )
                self.logger.info("配置已保存")
        except Exception as e:
            self.logger.error(f"保存配置失败: {e}")

    @QtCore.pyqtSlot(dict)
    def _on_channel_found(self, channel_info):
        """处理发现有效频道事件"""
        self.model.add_channel(channel_info)

        if hasattr(self, 'channel_list'):
            header = self.channel_list.horizontalHeader()
            QtCore.QTimer.singleShot(
                0, lambda: header.resizeSections(QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
                )

    @QtCore.pyqtSlot()
    def _on_scan_completed(self):
        """处理扫描完成事件 - 修复重试扫描状态管理问题"""
        # 导入样式
        # 检查是否是重试扫描
        is_retry = self.scan_state_manager.is_retry_scan(self.retry_id)

        # 隐藏进度条
        self.progress_manager.hide_progress()

        # 更新按钮文本
        self._set_scan_button_text('full_scan', '完整扫描')
        self._set_append_scan_button_text('append_scan', '追加扫描')

        self.btn_validate.setText("检测有效性")

        # 更新UI状态
        self.btn_smart_sort.setEnabled(True)
        self.btn_smart_sort.setStyleSheet(
            AppStyles.button_style(active=True)
        )

        if hasattr(self, 'channel_list'):
            header = self.channel_list.horizontalHeader()
            header.resizeSections(QtWidgets.QHeaderView.ResizeMode.ResizeToContents)

        # 检查是否需要重试扫描
        if not is_retry:
            # 这是第一次扫描完成，检查是否需要重试
            if self.enable_retry_checkbox.isChecked():
                # 延迟启动重试扫描，避免状态冲突
                QtCore.QTimer.singleShot(100, self._handle_retry_scan)
        else:
            # 这是重试扫描完成，处理循环扫描逻辑
            self._handle_retry_scan_completed()

    @QtCore.pyqtSlot(dict)
    def _update_stats_display(self, stats_data):
        """更新统计信息显示，包括扫描次数"""
        try:
            if not hasattr(self, 'stats_label') or not self.stats_label:
                self.logger.error("状态栏统计标签不存在")
                return

            stats = stats_data.get('stats', stats_data)
            elapsed = time.strftime("%H:%M:%S", time.gmtime(stats.get('elapsed', 0)))

            # 获取重试次数
            retry_count = self.scan_state_manager.get_retry_count(self.retry_id)
            is_retry_scan = self.scan_state_manager.is_retry_scan(self.retry_id)

            # 如果是重试扫描，显示重试次数
            scan_type = ""
            if is_retry_scan:
                scan_type = f"第{retry_count}次重试"
            elif retry_count > 0:
                scan_type = f"第{retry_count + 1}次扫描"
            else:
                scan_type = "第1次扫描"

            if hasattr(self, 'language_manager') and self.language_manager:
                # 使用更清晰的文本
                scan_text = self.language_manager.tr('scan', '扫描')
                total_text = self.language_manager.tr('scan_total', '本次总数')
                valid_text = self.language_manager.tr('valid', '有效')
                invalid_text = self.language_manager.tr('invalid', '无效')
                time_text = self.language_manager.tr('time_elapsed', '耗时')

                stats_text = (
                    f"{scan_text}: {scan_type} | "
                    f"{total_text}: {stats.get('total', 0)} | "
                    f"{valid_text}: {stats.get('valid', 0)} | "
                    f"{invalid_text}: {stats.get('invalid', 0)} | "
                    f"{time_text}: {elapsed}"
                )
                self.stats_label.setText(stats_text)
            else:
                # 使用更清晰的文本："本次总数"而不是"总数"
                stats_text = (
                    f"扫描: {scan_type} | "
                    f"本次总数: {stats.get('total', 0)} | "
                    f"有效: {stats.get('valid', 0)} | "
                    f"无效: {stats.get('invalid', 0)} | "
                    f"耗时: {elapsed}"
                )
                self.stats_label.setText(stats_text)
        except Exception as e:
            self.logger.error(f"更新统计信息显示失败: {e}", exc_info=True)

    def _register_cleanup_handlers(self):
        """注册资源清理处理器"""
        self.logger.info("注册资源清理处理器...")

        # 收集所有处理器名称用于整合日志
        handler_names = []

        # 注册配置保存处理器（应该在清理前执行）
        register_cleanup(self.save_before_exit, "save_config_before_exit")
        handler_names.append("save_config_before_exit")

        register_cleanup(self._stop_all_timers, "stop_all_timers")
        handler_names.append("stop_all_timers")

        # 进度条管理器清理
        register_cleanup(self.progress_manager.stop_auto_update, "progress_manager_stop_auto_update")
        handler_names.append("progress_manager_stop_auto_update")

        register_cleanup(self.progress_manager.hide_progress, "progress_manager_hide_progress")
        handler_names.append("progress_manager_hide_progress")

        if hasattr(self, 'scanner'):
            register_cleanup(self.scanner.stop_scan, "scanner_stop_scan")
            handler_names.append("scanner_stop_scan")

        from services.validator_service import StreamValidator
        register_cleanup(StreamValidator.terminate_all, "validator_terminate_all")
        handler_names.append("validator_terminate_all")

        from utils.memory_manager import optimize_memory
        register_cleanup(optimize_memory, "optimize_memory")
        handler_names.append("optimize_memory")

        # 整合日志：显示所有注册的处理器
        self.logger.info(f"已注册 {len(handler_names)} 个资源清理处理器: {', '.join(handler_names)}")

    def _handle_retry_scan(self):
        """处理重试扫描"""
        self.logger.info("=== _handle_retry_scan 方法开始 ===")

        # 使用重试扫描状态上下文管理器
        with RetryScanStateContext(self.retry_id, self):
            self._handle_retry_scan_internal()

    def _handle_retry_scan_internal(self):
        """内部重试扫描处理方法"""
        # 收集失败的频道
        self._collect_failed_channels()

        failed_channels = self.scan_state_manager.get_failed_channels(self.retry_id)
        self.logger.info(f"收集到的失败频道数量: {len(failed_channels)}")

        if not failed_channels:
            self.logger.info("没有失败的频道需要重试")
            # 扫描频道窗口没有状态栏，直接在日志中记录
            self.logger.info("=== _handle_retry_scan 方法结束（无失败频道）===")
            return

        # 记录当前的有效频道数，用于判断是否找到了新的有效频道
        current_valid_count = self._count_valid_channels()
        self.scan_state_manager.update_last_retry_valid_count(self.retry_id, current_valid_count)
        self.logger.info(f"当前有效频道数: {current_valid_count}")

        # 启动重试扫描
        self._start_retry_scan()

        self.logger.info("=== _handle_retry_scan 方法结束 ===")

    def _collect_failed_channels(self):
        """收集失败的频道URL，基于失败原因进行智能重试"""
        # 从扫描状态管理器获取需要重试的URL列表（基于失败原因）
        if hasattr(self, 'scanner') and self.scanner:
            # 获取需要重试的URL（基于失败原因过滤）
            retry_urls = self.scan_state_manager.get_retry_urls(self.scanner.scan_id)

            # 清空之前的失败频道列表，避免累积
            self.scan_state_manager.clear_failed_channels(self.retry_id)

            # 批量添加到重试扫描状态管理器，优化内存使用
            batch_size = 1000
            total_count = len(retry_urls)

            for i in range(0, total_count, batch_size):
                batch = retry_urls[i:i+batch_size]
                for url in batch:
                    self.scan_state_manager.add_failed_channel(self.retry_id, url)

                # 每处理一批后稍微休息，避免UI阻塞
                if i + batch_size < total_count:
                    time.sleep(0.001)  # 1ms休息，几乎不影响性能

            # 减少日志输出，避免日志过多
            if total_count > 1000:
                self.logger.info(f"智能重试: 基于失败原因筛选出 {total_count} 个需要重试的URL (大量URL，简化日志)")
                # 只记录前2个需要重试的URL
                for i in range(min(2, total_count)):
                    url = retry_urls[i]
                    self.logger.info(f"重试URL示例 {i}: {url[:50]}")
                if total_count > 2:
                    self.logger.info(f"... 还有 {total_count - 2} 个URL")
            else:
                self.logger.info(f"智能重试: 基于失败原因筛选出 {total_count} 个需要重试的URL")
                # 只记录前3个需要重试的URL
                for i in range(min(3, total_count)):
                    url = retry_urls[i]
                    self.logger.info(f"重试URL {i}: {url[:50]}")
        else:
            self.logger.warning("ScannerController不存在，无法获取需要重试的URL列表")

        failed_channels = self.scan_state_manager.get_failed_channels(self.retry_id)
        self.logger.info(f"智能重试收集完成: 需要重试的URL数={len(failed_channels)}")

        # 如果重试URL数量很大，记录警告信息
        if len(failed_channels) > 10000:
            self.logger.warning(f"警告: 有 {len(failed_channels)} 个URL需要重试，可能需要较长时间")
        elif len(failed_channels) > 0:
            # 记录智能重试信息
            self.logger.info("智能重试开始，准备扫描失败的频道")

    def _count_valid_channels(self):
        """统计当前有效频道数量"""
        count = 0
        for i in range(self.model.rowCount()):
            channel = self.model.get_channel(i)
            if channel and channel.get('valid', False):
                count += 1
        return count

    def _start_retry_scan(self):
        """启动重试扫描"""
        if not hasattr(self, 'scanner') or self.scanner is None:
            log_ui_error("扫描器未初始化，无法启动重试扫描")
            return
        self.logger.info("启动重试扫描...")
        
        # 从扫描状态管理器获取失败的频道
        failed_channels = self.scan_state_manager.get_failed_channels(self.retry_id)
        
        if not failed_channels:
            self.logger.info("没有失败的频道需要重试")
            return
        
        # 直接使用failed_channels作为retry_urls，因为它们都是URL字符串的列表
        retry_urls = failed_channels
        
        # 启动扫描
        self.scanner.start_scan(
            retry_urls,
            self.thread_count_input.value(),
            self.timeout_input.value(),
            is_retry=True
        )
        
        # 更新按钮文本
        self._set_scan_button_text('stop_scan', '停止扫描')
        self._set_append_scan_button_text('stop_scan', '停止扫描')

    def _handle_retry_scan_completed(self):
        """处理重试扫描完成 - 简化后默认启用循环扫描"""
        self.logger.info("=== 处理重试扫描完成 ===")
        
        # 统计当前有效频道数
        current_valid_count = self._count_valid_channels()
        # 获取上一次重试时的有效频道数
        last_valid_count = self.scan_state_manager.get_last_retry_valid_count(self.retry_id)
        
        self.logger.info(f"循环扫描检查: 上次有效频道数={last_valid_count}, 当前有效频道数={current_valid_count}")
        
        # 如果这次重试找到了新的有效频道，继续循环扫描
        if current_valid_count > last_valid_count:
            self.logger.info("找到新的有效频道，继续循环扫描")
            # 延迟启动下一次重试扫描
            QtCore.QTimer.singleShot(100, self._handle_retry_scan)
        else:
            self.logger.info("没有找到新的有效频道，结束循环扫描")
            # 重置重试扫描状态
            self.scan_state_manager.reset_retry_scan(self.retry_id)


class HeaderDelegate(QtWidgets.QHeaderView):
    """自定义表头委托"""
    def __init__(self, parent=None, model=None):
        super().__init__(QtCore.Qt.Orientation.Horizontal, parent)
        self.model = model