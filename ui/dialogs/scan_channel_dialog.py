"""
扫描频道窗口模块 - 负责扫描频道功能的UI和事件处理
"""

import os
import time
from PyQt6 import QtWidgets, QtCore, QtGui

# 导入自定义模块
from models.channel_model import ChannelListModel
from services.scanner_service import ScannerController
from services.mpv_validator_service import get_optimal_thread_count
from ui.styles import AppStyles
from services.url_parser_service import URLRangeParser

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
        # 从主题获取透明度设置
        from ..styles import AppStyles
        colors = AppStyles._get_colors()
        self.opacity = colors.get('window_opacity', 220)
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

        self._init_main_window()

    def done(self, result):
        self._unregister_cleanup_handlers()
        self._unregister_config_observers()
        super().done(result)

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

    def paintEvent(self, event):
        """自定义绘制圆角背景和边框"""
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        
        colors = AppStyles._get_colors()
        neo = AppStyles.is_neumorphic()
        
        path = QtGui.QPainterPath()
        rect = QtCore.QRectF(self.rect().adjusted(1, 1, -1, -1))
        path.addRoundedRect(rect, 12, 12)
        
        bg_color = colors.get('window', '#2d2d2d')
        if bg_color.startswith('#'):
            r = int(bg_color[1:3], 16)
            g = int(bg_color[3:5], 16)
            b = int(bg_color[5:7], 16)
        else:
            r, g, b = 45, 45, 45
        painter.fillPath(path, QtGui.QColor(r, g, b, self.opacity))
        
        if not neo:
            border_color = colors.get('mid', '#555555')
            if border_color.startswith('#'):
                r = int(border_color[1:3], 16)
                g = int(border_color[3:5], 16)
                b = int(border_color[5:7], 16)
            else:
                r, g, b = 85, 85, 85
            painter.setPen(QtGui.QColor(r, g, b, 200))
            painter.drawPath(path)
        
        super().paintEvent(event)

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
        tr = self.language_manager.tr
        self.setWindowTitle(tr("scan_window_title", "IPTV Scanner"))
        from utils.general_utils import get_icon_path
        ico_path = get_icon_path()
        if os.path.exists(ico_path):
            from PyQt6.QtGui import QIcon
            self.setWindowIcon(QIcon(ico_path))
        self.setWindowFlags(QtCore.Qt.WindowType.FramelessWindowHint | QtCore.Qt.WindowType.Window)
        # 设置透明背景，实现圆角窗口效果
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
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
        self.stats_label = QtWidgets.QLabel(tr("ready", "Ready"))
        self.stats_label.setStyleSheet(AppStyles.common_label_style())

        # 主布局
        main_widget = QtWidgets.QWidget()
        # 主布局 - 使用水平布局替代分割器
        main_layout = QtWidgets.QHBoxLayout(main_widget)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(0)

        # ========== 左侧边栏：扫描设置 (固定宽度 280px) ==========
        left_panel = QtWidgets.QWidget()
        left_panel.setFixedWidth(280)
        left_panel.setStyleSheet(AppStyles.side_panel_style())
        left_layout = QtWidgets.QVBoxLayout(left_panel)
        left_layout.setContentsMargins(8, 8, 8, 8)
        left_layout.setSpacing(8)

        # 左侧标题栏
        self.left_title = QtWidgets.QLabel(f"⚙️ {tr('scan_settings_title', 'Scan Settings')}")
        self.left_title.setStyleSheet(AppStyles.section_title_style())
        left_layout.addWidget(self.left_title)

        # 扫描设置内容
        scan_scroll = QtWidgets.QScrollArea()
        scan_scroll.setWidgetResizable(True)
        scan_scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        scan_scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        scan_widget = QtWidgets.QWidget()
        scan_layout = QtWidgets.QVBoxLayout(scan_widget)
        scan_layout.setContentsMargins(0, 0, 0, 0)
        scan_layout.setSpacing(8)
        self._setup_scan_panel(scan_layout)

        scan_scroll.setWidget(scan_widget)
        left_layout.addWidget(scan_scroll, 1)

        # 关闭按钮放在左下角
        self.close_btn = QtWidgets.QPushButton(f"✕ {tr('close_button', 'Close')}")
        self.close_btn.setStyleSheet(AppStyles.common_button_style())
        self.close_btn.setFixedHeight(32)
        self.close_btn.clicked.connect(self.close)
        left_layout.addWidget(self.close_btn)

        main_layout.addWidget(left_panel)

        # 中间间隔
        main_layout.addSpacing(12)

        # ========== 中间区域：频道列表 (自适应宽度) ==========
        center_panel = QtWidgets.QWidget()
        center_panel.setStyleSheet(AppStyles.side_panel_style())
        center_layout = QtWidgets.QVBoxLayout(center_panel)
        center_layout.setContentsMargins(12, 12, 12, 12)
        center_layout.setSpacing(10)

        # 频道列表标题栏（包含操作按钮）
        list_header = QtWidgets.QHBoxLayout()
        self.list_title = QtWidgets.QLabel(f"📺 {tr('channel_list_title', 'Channel List')}")
        self.list_title.setStyleSheet(AppStyles.section_title_style())
        list_header.addWidget(self.list_title)
        list_header.addStretch()

        # 将工具栏按钮移到标题栏
        self._setup_list_toolbar(list_header)
        center_layout.addLayout(list_header)

        # 频道列表
        self._setup_channel_list(center_layout)

        # 底部状态栏
        status_layout = QtWidgets.QHBoxLayout()
        status_layout.setContentsMargins(0, 5, 0, 0)
        self.progress_indicator.setFixedHeight(24)
        self.progress_indicator.setFixedWidth(120)
        status_layout.addWidget(self.progress_indicator)
        status_layout.addWidget(self.stats_label)
        status_layout.addStretch()
        center_layout.addLayout(status_layout)

        main_layout.addWidget(center_panel, 1)

        # 中间间隔
        main_layout.addSpacing(12)

        # ========== 右侧边栏：频道编辑 (固定宽度 240px) ==========
        right_panel = QtWidgets.QWidget()
        right_panel.setFixedWidth(240)
        right_panel.setStyleSheet(AppStyles.side_panel_style())
        right_layout = QtWidgets.QVBoxLayout(right_panel)
        right_layout.setContentsMargins(8, 8, 8, 8)
        right_layout.setSpacing(8)

        # 右侧标题
        self.right_title = QtWidgets.QLabel(f"✏️ {tr('channel_edit_title', 'Channel Edit')}")
        self.right_title.setStyleSheet(AppStyles.section_title_style())
        right_layout.addWidget(self.right_title)

        # 频道编辑内容
        self._setup_channel_edit(right_layout)

        main_layout.addWidget(right_panel)

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
                3,
                get_optimal_thread_count(),
                self.user_agent_input.text(),
                self.referer_input.text(),
                enable_retry,
                enable_retry  # 简化后，启用重试即默认启用循环行为
            )

    def _setup_scan_panel(self, parent: QtWidgets.QLayout) -> None:
        """配置扫描面板（简化版，不含GroupBox）"""
        scan_layout = QtWidgets.QVBoxLayout()
        scan_layout.setContentsMargins(0, 0, 0, 0)
        scan_layout.setSpacing(8)

        # 设置扫描按钮
        self._setup_scan_buttons()

        # 添加所有控件到布局
        self._add_scan_controls_to_layout(scan_layout)

        parent.addLayout(scan_layout)

    def _setup_scan_inputs(self):
        """设置扫描输入控件"""
        # IP地址输入
        self.ip_range_input = QtWidgets.QLineEdit()
        self.ip_range_input.editingFinished.connect(
            lambda: self._save_network_settings()
        )

        # User-Agent设置
        self._setup_user_agent_input()

        # Referer设置
        self._setup_referer_input()

    def _setup_user_agent_input(self):
        """设置User-Agent输入控件"""
        tr = self.language_manager.tr
        user_agent_layout = QtWidgets.QHBoxLayout()
        user_agent_label = QtWidgets.QLabel("User-Agent:")
        self.user_agent_label = user_agent_label
        user_agent_layout.addWidget(user_agent_label)
        self.user_agent_input = QtWidgets.QLineEdit()
        self.user_agent_input.setPlaceholderText(tr("optional_default_input", "Optional, use default if empty"))
        user_agent_layout.addWidget(self.user_agent_input)
        self.user_agent_input.textChanged.connect(
            lambda: self._save_network_settings()
        )
        self.user_agent_layout = user_agent_layout

    def _setup_referer_input(self):
        """设置Referer输入控件"""
        tr = self.language_manager.tr
        referer_layout = QtWidgets.QHBoxLayout()
        referer_label = QtWidgets.QLabel("Referer:")
        self.referer_label = referer_label
        referer_layout.addWidget(referer_label)
        self.referer_input = QtWidgets.QLineEdit()
        self.referer_input.setPlaceholderText(tr("optional_not_used_input", "Optional, not used if empty"))
        referer_layout.addWidget(self.referer_input)
        self.referer_input.textChanged.connect(
            lambda: self._save_network_settings()
        )
        self.referer_layout = referer_layout

    def _setup_scan_retry_options(self):
        """设置扫描重试选项"""
        tr = self.language_manager.tr
        retry_layout = QtWidgets.QHBoxLayout()
        retry_label = QtWidgets.QLabel(f"{tr('scan_retry_options', 'Scan Retry Options')}：")
        self.retry_label = retry_label
        retry_layout.addWidget(retry_label)

        # 是否启用智能重试扫描（基于失败原因，自动循环直到无新频道）
        self.enable_retry_checkbox = QtWidgets.QCheckBox(tr("enable_smart_retry", "Enable Smart Retry"))
        self.enable_retry_checkbox.setToolTip(
            tr("smart_retry_tooltip", "Smart retry based on failure reasons")
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
        tr = self.language_manager.tr
        mapping_layout = QtWidgets.QHBoxLayout()
        mapping_label = QtWidgets.QLabel(f"{tr('mapping_options', 'Mapping Options')}：")
        self.mapping_label = mapping_label
        mapping_layout.addWidget(mapping_label)

        # 是否启用频道映射
        self.enable_mapping_checkbox = QtWidgets.QCheckBox(tr("enable_channel_mapping", "Enable Channel Mapping"))
        self.enable_mapping_checkbox.setToolTip(
            tr("mapping_tooltip", "When enabled, scanned channels will auto-match from mapping file")
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
        tr = self.language_manager.tr
        # 扫描控制按钮
        self.btn_scan = QtWidgets.QPushButton(tr("full_scan", "Full Scan"))
        self.btn_scan.setStyleSheet(AppStyles.common_button_style())
        self.btn_scan.setMinimumHeight(32)  # 减少按钮高度
        self.btn_scan.setAutoDefault(False)

        # 新增追加扫描按钮
        self.btn_append_scan = QtWidgets.QPushButton(tr("append_scan", "Append Scan"))
        self.btn_append_scan.setStyleSheet(AppStyles.common_button_style())
        self.btn_append_scan.setMinimumHeight(32)  # 减少按钮高度
        self.btn_append_scan.setToolTip(tr("append_scan_tooltip", "Append valid channels to existing list without clearing"))
        self.btn_append_scan.setAutoDefault(False)

        # 新增直接生成列表按钮
        self.btn_generate = QtWidgets.QPushButton(tr("generate_list", "Generate List"))
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
        """添加扫描控件到布局（优化版，适合窄边栏）"""
        tr = self.language_manager.tr
        # 先设置所有输入控件
        self._setup_scan_inputs()

        # 设置扫描重试选项
        self._setup_scan_retry_options()

        # 设置映射功能选项
        self._setup_mapping_options()

        # 地址设置（简化标题）
        address_section = QtWidgets.QVBoxLayout()
        address_section.setSpacing(8)

        address_example_label = QtWidgets.QLabel(
            tr("address_format_hint", "Format: http://ip:port/rtp/...")
        )
        self.address_example_label = address_example_label
        address_example_label.setWordWrap(True)
        address_example_label.setStyleSheet(AppStyles.hint_label_style())
        address_example_label.setMinimumHeight(40)

        address_section.addWidget(address_example_label)
        self.ip_range_input.setFixedHeight(32)
        address_section.addWidget(self.ip_range_input)

        scan_layout.addLayout(address_section)
        scan_layout.addSpacing(12)

        # 扫描设置（简化标题）
        scan_settings_section = QtWidgets.QVBoxLayout()
        scan_settings_section.setSpacing(8)

        # User-Agent（简化标签）
        ua_label = QtWidgets.QLabel("User-Agent:")
        ua_label.setStyleSheet(AppStyles.small_label_style())
        scan_settings_section.addWidget(ua_label)
        self.user_agent_input.setFixedHeight(28)
        scan_settings_section.addWidget(self.user_agent_input)

        # Referer（简化标签）
        ref_label = QtWidgets.QLabel("Referer:")
        ref_label.setStyleSheet(AppStyles.small_label_style())
        scan_settings_section.addWidget(ref_label)
        self.referer_input.setFixedHeight(28)
        scan_settings_section.addWidget(self.referer_input)

        scan_layout.addLayout(scan_settings_section)
        scan_layout.addSpacing(12)

        # 选项（简化）
        options_section = QtWidgets.QVBoxLayout()
        options_section.setSpacing(8)
        self.enable_retry_checkbox.setFixedHeight(24)
        options_section.addWidget(self.enable_retry_checkbox)
        self.enable_mapping_checkbox.setFixedHeight(24)
        options_section.addWidget(self.enable_mapping_checkbox)

        scan_layout.addLayout(options_section)
        scan_layout.addStretch()

        # 扫描按钮（垂直排列，适合窄边栏）
        button_section = QtWidgets.QVBoxLayout()
        button_section.setSpacing(8)
        self.btn_scan.setFixedHeight(36)
        button_section.addWidget(self.btn_scan)
        self.btn_append_scan.setFixedHeight(36)
        button_section.addWidget(self.btn_append_scan)
        self.btn_generate.setFixedHeight(36)
        button_section.addWidget(self.btn_generate)

        scan_layout.addLayout(button_section)

    def _setup_channel_list(self, parent: QtWidgets.QLayout) -> None:
        """配置频道列表（简化版，不含工具栏和GroupBox）"""
        # 频道列表视图
        self.channel_list = QtWidgets.QTableView()
        self.channel_list.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.channel_list.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.channel_list.verticalHeader().setVisible(False)
        # 启用水平滚动条
        self.channel_list.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.channel_list.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)

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

        self.channel_list.doubleClicked.connect(self._on_channel_double_clicked)

        # 启用拖放排序功能 - 改进拖拽体验
        self.channel_list.setDragEnabled(True)
        self.channel_list.setAcceptDrops(True)
        self.channel_list.setDragDropOverwriteMode(False)
        self.channel_list.setDragDropMode(QtWidgets.QAbstractItemView.DragDropMode.InternalMove)
        self.channel_list.setDefaultDropAction(QtCore.Qt.DropAction.MoveAction)
        self.channel_list.setDropIndicatorShown(True)  # 显示拖拽指示器

        # 添加右键菜单
        self.channel_list.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.channel_list.customContextMenuRequested.connect(self._show_channel_context_menu)

        # 连接选择事件
        self.channel_list.selectionModel().selectionChanged.connect(self._on_channel_selected)

        # 设置频道列表为主要内容，占据大部分空间
        parent.addWidget(self.channel_list)

    def _setup_list_toolbar(self, toolbar_layout):
        """设置频道列表的工具栏按钮（用于标题栏）"""
        tr = self.language_manager.tr
        # 打开列表按钮
        self.btn_open_list = QtWidgets.QPushButton(tr("open_list", "Open List"))
        self.btn_open_list.setStyleSheet(AppStyles.common_button_style())
        self.btn_open_list.setFixedHeight(32)
        self.btn_open_list.setFixedWidth(70)
        self.btn_open_list.setToolTip(tr("open_list_tooltip", "Import M3U file to channel list for validation"))

        # 有效性检测按钮
        self.btn_validate = QtWidgets.QPushButton(tr("validate_button", "Validate"))
        self.btn_validate.setStyleSheet(AppStyles.common_button_style())
        self.btn_validate.setFixedHeight(32)
        self.btn_validate.setFixedWidth(60)
        self.btn_validate.setToolTip(tr("validate_tooltip", "Validate channel effectiveness"))

        # 隐藏无效项按钮
        self.btn_hide_invalid = QtWidgets.QPushButton(tr("hide_invalid_button", "Hide Invalid"))
        self.btn_hide_invalid.setStyleSheet(AppStyles.common_button_style())
        self.btn_hide_invalid.setFixedHeight(32)
        self.btn_hide_invalid.setFixedWidth(80)
        self.btn_hide_invalid.setEnabled(False)

        # 保存M3U按钮
        self.btn_save_m3u = QtWidgets.QPushButton(tr("save_m3u", "Save M3U"))
        self.btn_save_m3u.setStyleSheet(AppStyles.common_button_style())
        self.btn_save_m3u.setFixedHeight(32)
        self.btn_save_m3u.setFixedWidth(70)
        self.btn_save_m3u.setToolTip(tr("save_m3u_tooltip", "Save channel list as M3U format"))

        # 保存TXT按钮
        self.btn_save_txt = QtWidgets.QPushButton(tr("save_txt", "Save TXT"))
        self.btn_save_txt.setStyleSheet(AppStyles.common_button_style())
        self.btn_save_txt.setFixedHeight(32)
        self.btn_save_txt.setFixedWidth(70)
        self.btn_save_txt.setToolTip(tr("save_txt_tooltip", "Save channel list as TXT format"))

        toolbar_layout.addWidget(self.btn_open_list)
        toolbar_layout.addSpacing(6)
        toolbar_layout.addWidget(self.btn_validate)
        toolbar_layout.addSpacing(6)
        toolbar_layout.addWidget(self.btn_hide_invalid)
        toolbar_layout.addSpacing(6)
        toolbar_layout.addWidget(self.btn_save_m3u)
        toolbar_layout.addSpacing(6)
        toolbar_layout.addWidget(self.btn_save_txt)

    def _setup_channel_edit(self, parent: QtWidgets.QLayout) -> None:
        """配置频道编辑区域（简化版，不含GroupBox）"""
        tr = self.language_manager.tr
        # 使用垂直布局替代网格布局，更适合窄边栏
        edit_layout = QtWidgets.QVBoxLayout()
        edit_layout.setContentsMargins(0, 0, 0, 0)
        edit_layout.setSpacing(10)

        # 频道名称
        name_layout = QtWidgets.QVBoxLayout()
        name_layout.setSpacing(4)
        self.edit_name_label = QtWidgets.QLabel(f"{tr('channel_name', 'Channel Name')}:")
        self.edit_name_label.setStyleSheet(AppStyles.common_label_style())
        self.edit_name = QtWidgets.QLineEdit()
        self.edit_name.setStyleSheet(AppStyles.common_line_edit_style())
        self.edit_name.setFixedHeight(30)
        name_layout.addWidget(self.edit_name_label)
        name_layout.addWidget(self.edit_name)
        edit_layout.addLayout(name_layout)

        # 频道分组
        group_layout = QtWidgets.QVBoxLayout()
        group_layout.setSpacing(4)
        self.edit_group_label = QtWidgets.QLabel(f"{tr('channel_group', 'Channel Group')}:")
        self.edit_group_label.setStyleSheet(AppStyles.common_label_style())
        self.edit_group = QtWidgets.QLineEdit()
        self.edit_group.setStyleSheet(AppStyles.common_line_edit_style())
        self.edit_group.setFixedHeight(30)
        group_layout.addWidget(self.edit_group_label)
        group_layout.addWidget(self.edit_group)
        edit_layout.addLayout(group_layout)

        # 频道URL
        url_layout = QtWidgets.QVBoxLayout()
        url_layout.setSpacing(4)
        self.edit_url_label = QtWidgets.QLabel(f"{tr('channel_url', 'Channel URL')}:")
        self.edit_url_label.setStyleSheet(AppStyles.common_label_style())
        self.edit_url = QtWidgets.QLineEdit()
        self.edit_url.setStyleSheet(AppStyles.common_line_edit_style())
        self.edit_url.setFixedHeight(30)
        url_layout.addWidget(self.edit_url_label)
        url_layout.addWidget(self.edit_url)
        edit_layout.addLayout(url_layout)

        # TVG-ID
        tvg_layout = QtWidgets.QVBoxLayout()
        tvg_layout.setSpacing(4)
        self.edit_tvg_id_label = QtWidgets.QLabel("TVG-ID:")
        self.edit_tvg_id_label.setStyleSheet(AppStyles.common_label_style())
        self.edit_tvg_id = QtWidgets.QLineEdit()
        self.edit_tvg_id.setStyleSheet(AppStyles.common_line_edit_style())
        self.edit_tvg_id.setFixedHeight(30)
        tvg_layout.addWidget(self.edit_tvg_id_label)
        tvg_layout.addWidget(self.edit_tvg_id)
        edit_layout.addLayout(tvg_layout)

        # Logo URL
        logo_layout = QtWidgets.QVBoxLayout()
        logo_layout.setSpacing(4)
        self.edit_logo_label = QtWidgets.QLabel(f"{tr('logo_address', 'Logo Address')}:")
        self.edit_logo_label.setStyleSheet(AppStyles.common_label_style())
        self.edit_logo = QtWidgets.QLineEdit()
        self.edit_logo.setStyleSheet(AppStyles.common_line_edit_style())
        self.edit_logo.setFixedHeight(30)
        logo_layout.addWidget(self.edit_logo_label)
        logo_layout.addWidget(self.edit_logo)
        edit_layout.addLayout(logo_layout)

        # 增加一些垂直空间，让内容分布更均匀
        edit_layout.addStretch(1)

        # 保存按钮
        self.btn_save_channel = QtWidgets.QPushButton(tr("save_changes", "💾 Save Changes"))
        self.btn_save_channel.setStyleSheet(AppStyles.common_button_style())
        self.btn_save_channel.setFixedHeight(40)
        self.btn_save_channel.setDefault(True)
        self.btn_save_channel.clicked.connect(self._on_save_channel)
        edit_layout.addWidget(self.btn_save_channel)

        parent.addLayout(edit_layout)

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
            self.edit_logo.setText(channel.get('logo_url', channel.get('logo', '')))

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
            'logo_url': self.edit_logo.text(),
            'logo': self.edit_logo.text()
        }

        self.model.update_channel(row, channel_info)
        # 刷新列表
        self.channel_list.viewport().update()

    def _show_channel_context_menu(self, pos):
        """显示频道列表的右键菜单"""
        tr = self.language_manager.tr
        index = self.channel_list.indexAt(pos)
        if not index.isValid():
            return

        menu = QtWidgets.QMenu()

        # 获取选中频道的URL和名称
        url = self.model.data(self.model.index(index.row(), 3))  # URL在第3列
        name = self.model.data(self.model.index(index.row(), 1))  # 名称在第1列

        # 添加复制频道名菜单项
        copy_name_action = QtGui.QAction(tr("copy_channel_name", "Copy Channel Name"), self)
        copy_name_action.triggered.connect(lambda: self._copy_channel_name(name))
        menu.addAction(copy_name_action)

        # 添加复制URL菜单项
        copy_url_action = QtGui.QAction(tr("copy_url", "Copy URL"), self)
        copy_url_action.triggered.connect(lambda: self._copy_channel_url(url))
        menu.addAction(copy_url_action)

        # 添加复制TVG-ID菜单项
        tvg_id = self.model.data(self.model.index(index.row(), 8))  # TVG-ID在第8列
        copy_tvg_id_action = QtGui.QAction(tr("copy_tvg_id", "Copy TVG-ID"), self)
        copy_tvg_id_action.triggered.connect(lambda: self._copy_channel_tvg_id(tvg_id))
        menu.addAction(copy_tvg_id_action)

        # 添加复制分组菜单项
        group = self.model.data(self.model.index(index.row(), 4))  # 分组在第4列
        copy_group_action = QtGui.QAction(tr("copy_group", "Copy Group"), self)
        copy_group_action.triggered.connect(lambda: self._copy_channel_group(group))
        menu.addAction(copy_group_action)

        menu.addSeparator()

        # 添加删除频道菜单项
        delete_action = QtGui.QAction(tr("delete_channel", "Delete Channel"), self)
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
        tr = self.language_manager.tr
        from utils.error_handler import show_confirm
        title = tr("confirm_delete", "Confirm Delete") or "Confirm Delete"
        message = tr("confirm_delete_message", "Are you sure you want to delete the selected channel?") or "Are you sure you want to delete the selected channel?"
        if show_confirm(title, message, parent=self):
            self.model.remove_channel(index.row())

    def _on_header_clicked(self, logical_index):
        """处理表头点击排序"""
        if not hasattr(self, 'model') or not self.model:
            return
        
        # 使用实例变量跟踪排序状态，避免被model.reset()重置
        if not hasattr(self, '_last_sort_column'):
            self._last_sort_column = -1
            self._last_sort_order = QtCore.Qt.SortOrder.AscendingOrder
        
        # 判断是否点击了同一列
        if self._last_sort_column == logical_index:
            # 同一列：切换排序顺序
            if self._last_sort_order == QtCore.Qt.SortOrder.AscendingOrder:
                new_order = QtCore.Qt.SortOrder.DescendingOrder
            else:
                new_order = QtCore.Qt.SortOrder.AscendingOrder
        else:
            # 不同列：默认升序
            new_order = QtCore.Qt.SortOrder.AscendingOrder
        
        # 保存当前排序状态
        self._last_sort_column = logical_index
        self._last_sort_order = new_order
        
        # 先执行排序
        self.model.sort(logical_index, new_order)
        
        # 排序完成后重新设置指示器（重要：必须在sort之后！）
        self.header.setSortIndicator(logical_index, new_order)

    def _on_channel_double_clicked(self, index):
        """双击频道列表项预览播放"""
        if not index.isValid():
            return
        channel = self.model.get_channel(index.row())
        if not channel or not channel.get('url'):
            return
        parent = self.parent()
        if parent and hasattr(parent, 'play_channel'):
            parent.play_channel(channel)
            parent.activateWindow()
            parent.raise_()

    def _init_main_window(self):
        if not hasattr(self, 'model') or not self.model:
            self.model = ChannelListModel()
            if hasattr(self, 'language_manager') and self.language_manager:
                self.model.set_language_manager(self.language_manager)

        self.model.setParent(self)

        self.progress_manager = init_progress_manager(
            self.progress_indicator,
            None
        )

        self.init_controllers()

        self._load_config()

        # 样式已在_init_ui中设置，这里只需连接信号和注册处理器
        self._connect_signals()
        self._register_cleanup_handlers()
        self._register_config_observers()

    def init_controllers(self):
        if not hasattr(self, 'scanner') or self.scanner is None:
            self.scanner = ScannerController(self.model, self)

        self._connect_progress_signals()

    def _connect_progress_signals(self):
        self.progress_manager.register_progress_callback(
            'scan',
            self._update_scan_progress
        )
        self.progress_manager.start_auto_update(
            self._update_scan_progress,
            interval=500
        )

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

            if settings['user_agent']:
                self.user_agent_input.setText(settings['user_agent'])

            if settings['referer']:
                self.referer_input.setText(settings['referer'])

            if 'enable_retry' in settings:
                self.enable_retry_checkbox.setChecked(settings['enable_retry'])

        except Exception as e:
            log_config_error(f"加载配置失败: {e}")

    def _register_config_observers(self):
        register_config_observer("Network.*", self._on_network_config_changed)
        register_config_observer("ScanRetry.*", self._on_scan_retry_config_changed)
        register_config_observer("Language.current_language", self._on_language_config_changed)

    def _on_network_config_changed(self, section, key, old_value, new_value):
        """处理网络配置变更"""
        log_config_info(f"网络配置变更: {section}.{key} = {old_value} -> {new_value}")

        # 更新对应的UI控件
        if key == 'url':
            self.ip_range_input.setText(new_value)
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
        safe_connect_button(self.btn_scan, self._on_scan_clicked)
        safe_connect_button(self.btn_append_scan, self._on_append_scan_clicked)
        safe_connect_button(self.btn_validate, self._on_validate_clicked)
        safe_connect_button(self.btn_hide_invalid, self._on_hide_invalid_clicked)
        safe_connect_button(self.btn_generate, self._on_generate_clicked)
        safe_connect_button(self.btn_open_list, self._on_open_list_clicked)
        safe_connect_button(self.btn_save_m3u, self._on_save_m3u_clicked)
        safe_connect_button(self.btn_save_txt, self._on_save_txt_clicked)

        if not hasattr(self, 'scanner') or self.scanner is None:
            return

        try:
            self.scanner.channel_found.connect(self._on_channel_found)
            self.scanner.scan_completed.connect(self._on_scan_completed)
            self.scanner.channel_validated.connect(self._on_channel_validated)
            # 对于 stats_updated，使用默认的 DirectConnection
            self.scanner.stats_updated.connect(self._update_stats_display)
        except Exception as e:
            log_ui_error(f"连接扫描器信号失败: {e}")

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

        # 智能两阶段扫描策略
        # 第一阶段：快速扫描（5秒超时），快速筛选有效频道
        # 第二阶段：对失败的URL自动重试（15秒超时），提高检出率
        scan_timeout_phase1 = 5  # 第一阶段快速超时

        # 智能动态线程数：5-8线程范围
        # 根据CPU核心数和内存情况自适应，但限制在安全范围内避免mpv句柄污染
        cpu_count = os.cpu_count() or 4
        if cpu_count <= 2:
            scan_threads = 5  # 低配机器用5线程
        elif cpu_count <= 4:
            scan_threads = 6  # 中等配置用6线程
        elif cpu_count <= 8:
            scan_threads = 7  # 高配机器用7线程
        else:
            scan_threads = 8  # 顶级配置最多8线程

        self.logger.debug(f"智能线程数: CPU={cpu_count}核, 使用{scan_threads}线程")

        try:
            if hasattr(self, 'config') and self.config:
                network_settings = self.config.load_network_settings()
                configured_timeout = network_settings.get('timeout', 30)
                if configured_timeout and configured_timeout > 0:
                    # 配置值作为参考，实际使用优化后的两阶段策略
                    scan_timeout_phase1 = max(3, min(10, int(configured_timeout) // 2))
        except Exception as e:
            self.logger.debug(f"读取超时配置失败，使用默认值: {e}")

        self.scanner.start_scan(url, scan_threads, scan_timeout_phase1)

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
            user_agent = self.user_agent_input.text()
            referer = self.referer_input.text()
            self.scanner.start_validation(
                self.model,
                get_optimal_thread_count(),
                3,
                user_agent,
                referer
            )
            self.btn_validate.setText(self.language_manager.tr("stop_validate", "Stop Validate"))
            self.btn_hide_invalid.setEnabled(True)
            self.btn_hide_invalid.setStyleSheet(
                AppStyles.button_style(active=True)
            )
        else:
            self.scanner.stop_validation()
            self.btn_validate.setText(self.language_manager.tr("validate_effectiveness", "Validate Effectiveness"))

    def _on_channel_validated(self, index, valid, latency, resolution):
        """处理频道验证结果"""
        channel_info = {
            'valid': valid,
            'latency': latency,
            'resolution': resolution,
            'status': '有效' if valid else '无效'
        }

        self.model.update_channel(index, channel_info)

    def _on_open_list_clicked(self):
        """打开M3U文件，将频道导入到扫描列表用于有效性检测"""
        tr = self.language_manager.tr
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            tr("open_list_for_validation", "Open List for Validation"),
            "",
            "M3U文件 (*.m3u *.m3u8);;文本文件 (*.txt);;所有文件 (*.*)"
        )
        if not file_path:
            return

        try:
            from services.m3u_parser import load_m3u_file
            content = load_m3u_file(file_path)

            if not self.model.load_from_file(content):
                self.logger.warning("解析M3U文件失败")
                return

            count = self.model.rowCount()
            self.logger.info(f"已导入 {count} 个频道到扫描列表")

            if hasattr(self, 'channel_list'):
                header = self.channel_list.horizontalHeader()
                header.resizeSections(QtWidgets.QHeaderView.ResizeMode.ResizeToContents)

            self.btn_hide_invalid.setEnabled(True)
            self.btn_hide_invalid.setStyleSheet(AppStyles.button_style(active=True))

        except FileNotFoundError:
            self.logger.warning(f"文件不存在: {file_path}")
        except Exception as e:
            self.logger.error(f"打开列表文件失败: {str(e)}")

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
        tr = self.language_manager.tr
        gen_name = tr("generated_channel", "Generated Channel")
        gen_group = tr("generated_group", "Generated")
        for batch in url_generator:
            for url in batch:
                channel = {
                    'name': f"{gen_name}-{count+1}",
                    'group': gen_group,
                    'url': url,
                    'valid': False,
                    'latency': 0,
                    'status': tr("not_tested", "Not Tested")
                }
                self.model.add_channel(channel)
                count += 1

        # 扫描频道窗口没有状态栏，直接在日志中记录
        self.logger.info(f"已生成 {count} 个频道")

    def _save_list_as(self, fmt: str):
        tr = self.language_manager.tr
        if not self.model or self.model.rowCount() == 0:
            self.logger.warning(str(tr("no_channels_to_save", "No channels to save")))
            return

        if fmt == 'm3u':
            filter_str = "M3U文件 (*.m3u);;M3U8文件 (*.m3u8);;所有文件 (*.*)"
            default_name = "scan_result.m3u"
        else:
            filter_str = "TXT文件 (*.txt);;所有文件 (*.*)"
            default_name = "scan_result.txt"

        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            tr("save_scan_result", "Save Scan Result"),
            default_name,
            filter_str
        )
        if not file_path:
            return

        try:
            if fmt == 'm3u':
                content = self.model.to_m3u()
            else:
                content = self.model.to_txt()

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)

            self.logger.info(f"已保存 {self.model.rowCount()} 个频道到 {file_path}")
        except Exception as e:
            self.logger.error(f"保存失败: {e}")

    def _on_save_m3u_clicked(self):
        self._save_list_as('m3u')

    def _on_save_txt_clicked(self):
        self._save_list_as('txt')

    def _on_hide_invalid_clicked(self):
        """处理隐藏无效项按钮点击事件"""
        tr = self.language_manager.tr
        hide_text = tr("hide_invalid", "Hide Invalid")
        if self.btn_hide_invalid.text() == hide_text:
            self.model.hide_invalid()
            self.btn_hide_invalid.setText(tr("show_hidden", "Show Hidden"))
        else:
            self.model.show_all()
            self.btn_hide_invalid.setText(hide_text)

    def save_before_exit(self):
        """退出前保存配置"""
        try:
            if hasattr(self, 'config'):
                self.config.save_network_settings(
                    url=self.ip_range_input.text(),
                    timeout=3,
                    threads=get_optimal_thread_count(),
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

        self.btn_validate.setText(self.language_manager.tr("validate_effectiveness", "Validate Effectiveness"))

        # 更新UI状态

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
            tr = self.language_manager.tr
            if is_retry_scan:
                scan_type = tr('retry_nth', 'Retry #{n}').format(n=retry_count)
            elif retry_count > 0:
                scan_type = tr('scan_nth', 'Scan #{n}').format(n=retry_count + 1)
            else:
                scan_type = tr('scan_nth', 'Scan #{n}').format(n=1)

            scan_text = tr('scan', 'Scan')
            total_text = tr('scan_total', 'Total')
            valid_text = tr('valid', 'Valid')
            invalid_text = tr('invalid', 'Invalid')
            time_text = tr('time_elapsed', 'Time')

            stats_text = (
                f"{scan_text}: {scan_type} | "
                f"{total_text}: {stats.get('total', 0)} | "
                f"{valid_text}: {stats.get('valid', 0)} | "
                f"{invalid_text}: {stats.get('invalid', 0)} | "
                f"{time_text}: {elapsed}"
            )
            self.stats_label.setText(stats_text)
        except Exception as e:
            self.logger.error(f"更新统计信息显示失败: {e}", exc_info=True)

    def closeEvent(self, event):
        if hasattr(self, 'application') and self.application:
            if hasattr(self.application, '_scan_dialog'):
                self.application._scan_dialog = None
        event.accept()

    def reapply_styles(self):
        try:
            self.setStyleSheet(AppStyles.popup_dialog_style())
            if hasattr(self, 'stats_label'):
                self.stats_label.setStyleSheet(AppStyles.common_label_style())
            if hasattr(self, 'left_panel'):
                self.left_panel.setStyleSheet(AppStyles.side_panel_style())
            if hasattr(self, 'left_title'):
                self.left_title.setStyleSheet(AppStyles.section_title_style())
            if hasattr(self, 'close_btn'):
                self.close_btn.setStyleSheet(AppStyles.common_button_style())
            if hasattr(self, 'center_panel'):
                self.center_panel.setStyleSheet(AppStyles.side_panel_style())
            if hasattr(self, 'list_title'):
                self.list_title.setStyleSheet(AppStyles.section_title_style())
            if hasattr(self, 'right_panel'):
                self.right_panel.setStyleSheet(AppStyles.side_panel_style())
            if hasattr(self, 'right_title'):
                self.right_title.setStyleSheet(AppStyles.section_title_style())
            for btn in [self.btn_scan, self.btn_append_scan, self.btn_generate,
                        self.btn_open_list, self.btn_validate, self.btn_hide_invalid,
                        self.btn_save_m3u, self.btn_save_txt, self.btn_save_channel]:
                if hasattr(btn, 'setStyleSheet'):
                    btn.setStyleSheet(AppStyles.common_button_style())
            if hasattr(self, 'channel_list'):
                self.channel_list.setStyleSheet(AppStyles.list_style())
            for label in [self.edit_name_label, self.edit_group_label,
                          self.edit_url_label, self.edit_tvg_id_label, self.edit_logo_label]:
                if hasattr(label, 'setStyleSheet'):
                    label.setStyleSheet(AppStyles.common_label_style())
            for edit in [self.edit_name, self.edit_group, self.edit_url,
                         self.edit_tvg_id, self.edit_logo]:
                if hasattr(edit, 'setStyleSheet'):
                    edit.setStyleSheet(AppStyles.common_line_edit_style())
            if hasattr(self, 'address_example_label'):
                self.address_example_label.setStyleSheet(AppStyles.hint_label_style())
            if hasattr(self, 'ua_label'):
                self.ua_label.setStyleSheet(AppStyles.small_label_style())
            if hasattr(self, 'ref_label'):
                self.ref_label.setStyleSheet(AppStyles.small_label_style())
        except Exception as e:
            if hasattr(self, 'logger'):
                self.logger.error(f"重新应用扫描窗口样式失败: {e}")

    def update_ui_texts(self):
        """语言切换时更新UI文本"""
        try:
            tr = self.language_manager.tr
            if hasattr(self, 'left_title'):
                self.left_title.setText(f"⚙️ {tr('scan_settings_title', 'Scan Settings')}")
            if hasattr(self, 'list_title'):
                self.list_title.setText(f"📺 {tr('channel_list_title', 'Channel List')}")
            if hasattr(self, 'right_title'):
                self.right_title.setText(f"✏️ {tr('channel_edit_title', 'Channel Edit')}")
            if hasattr(self, 'close_btn'):
                self.close_btn.setText(f"✕ {tr('close_button', 'Close')}")
            if hasattr(self, 'btn_validate'):
                self.btn_validate.setText(tr("validate_button", "Validate"))
            if hasattr(self, 'btn_open_list'):
                self.btn_open_list.setText(tr("open_list", "Open List"))
            if hasattr(self, 'btn_hide_invalid'):
                self.btn_hide_invalid.setText(tr("hide_invalid_button", "Hide Invalid"))
            if hasattr(self, 'btn_save_m3u'):
                self.btn_save_m3u.setText(tr("save_m3u", "Save M3U"))
                self.btn_save_m3u.setToolTip(tr("save_m3u_tooltip", "Save channel list as M3U format"))
            if hasattr(self, 'btn_save_txt'):
                self.btn_save_txt.setText(tr("save_txt", "Save TXT"))
                self.btn_save_txt.setToolTip(tr("save_txt_tooltip", "Save channel list as TXT format"))
            if hasattr(self, 'btn_scan'):
                self.btn_scan.setText(tr("full_scan", "Full Scan"))
            if hasattr(self, 'btn_append_scan'):
                self.btn_append_scan.setText(tr("append_scan", "Append Scan"))
            if hasattr(self, 'btn_generate'):
                self.btn_generate.setText(tr("generate_list", "Generate List"))
            if hasattr(self, 'stats_label'):
                self.stats_label.setText(tr("ready", "Ready"))
            if hasattr(self, 'edit_name_label'):
                self.edit_name_label.setText(f"{tr('channel_name', 'Channel Name')}:")
            if hasattr(self, 'edit_group_label'):
                self.edit_group_label.setText(f"{tr('channel_group', 'Channel Group')}:")
            if hasattr(self, 'edit_url_label'):
                self.edit_url_label.setText(f"{tr('channel_url', 'Channel URL')}:")
            if hasattr(self, 'edit_logo_label'):
                self.edit_logo_label.setText(f"{tr('logo_address', 'Logo Address')}:")
            if hasattr(self, 'btn_save_channel'):
                self.btn_save_channel.setText(tr("save_changes", "💾 Save Changes"))
            if hasattr(self, 'address_example_label'):
                self.address_example_label.setText(tr("address_format_hint", "Format: http://ip:port/rtp/..."))
            if hasattr(self, 'user_agent_label'):
                self.user_agent_label.setText("User-Agent:")
            if hasattr(self, 'referer_label'):
                self.referer_label.setText("Referer:")
            if hasattr(self, 'retry_label'):
                self.retry_label.setText(f"{tr('scan_retry_options', 'Scan Retry Options')}：")
            if hasattr(self, 'enable_retry_checkbox'):
                self.enable_retry_checkbox.setText(tr("enable_smart_retry", "Enable Smart Retry"))
            if hasattr(self, 'mapping_label'):
                self.mapping_label.setText(f"{tr('mapping_options', 'Mapping Options')}：")
            if hasattr(self, 'enable_mapping_checkbox'):
                self.enable_mapping_checkbox.setText(tr("enable_channel_mapping", "Enable Channel Mapping"))
            if hasattr(self, 'user_agent_input'):
                self.user_agent_input.setPlaceholderText(tr("optional_default_input", "Optional, use default if empty"))
            if hasattr(self, 'referer_input'):
                self.referer_input.setPlaceholderText(tr("optional_not_used_input", "Optional, not used if empty"))
        except Exception as e:
            self.logger.error(f"更新扫描窗口UI文本失败: {e}")

    def _register_cleanup_handlers(self):
        """注册资源清理处理器"""
        self._cleanup_handlers = []

        self._cleanup_handlers.append((self.save_before_exit, "save_config_before_exit"))
        self._cleanup_handlers.append((self._stop_all_timers, "stop_all_timers"))
        self._cleanup_handlers.append((self.progress_manager.stop_auto_update, "progress_manager_stop_auto_update"))
        self._cleanup_handlers.append((self.progress_manager.hide_progress, "progress_manager_hide_progress"))

        if hasattr(self, 'scanner'):
            self._cleanup_handlers.append((self.scanner.stop_scan, "scanner_stop_scan"))

        for handler, name in self._cleanup_handlers:
            register_cleanup(handler, name)

    def _unregister_cleanup_handlers(self):
        """注销资源清理处理器"""
        if not hasattr(self, '_cleanup_handlers'):
            return
        from utils.resource_cleaner import unregister_cleanup
        for handler, name in self._cleanup_handlers:
            try:
                unregister_cleanup(handler)
            except Exception:
                pass
        self._cleanup_handlers.clear()

    def _unregister_config_observers(self):
        """注销配置变更观察者"""
        from utils.config_notifier import unregister_config_observer
        try:
            unregister_config_observer("Network.*", self._on_network_config_changed)
            unregister_config_observer("ScanRetry.*", self._on_scan_retry_config_changed)
            unregister_config_observer("Language.current_language", self._on_language_config_changed)
        except Exception:
            pass

    def _handle_retry_scan(self):
        """处理重试扫描"""
        self.logger.debug("=== _handle_retry_scan 方法开始 ===")

        # 使用重试扫描状态上下文管理器
        with RetryScanStateContext(self.retry_id, self):
            self._handle_retry_scan_internal()

    def _handle_retry_scan_internal(self):
        """内部重试扫描处理方法"""
        # 增加重试计数（每次进入重试扫描时）
        self.scan_state_manager.increment_retry_count(self.retry_id)
        retry_count = self.scan_state_manager.get_retry_count(self.retry_id)
        self.logger.debug(f"当前重试次数：{retry_count}")
        
        # 检查是否超过最大重试次数
        max_retries = 3
        if retry_count > max_retries:
            self.logger.info(f"已达到最大重试次数 ({max_retries})，停止重试")
            # 使用 clear_failed_channels 代替不存在的 reset_retry_scan
            self.scan_state_manager.clear_failed_channels(self.retry_id)
            return
        
        # 收集失败的频道
        self._collect_failed_channels()

        failed_channels = self.scan_state_manager.get_failed_channels(self.retry_id)
        self.logger.debug(f"收集到的失败频道数量: {len(failed_channels)}")

        if not failed_channels:
            self.logger.debug("没有失败的频道需要重试")
            self.logger.debug("=== _handle_retry_scan 方法结束（无失败频道）===")
            return

        # 记录当前的有效频道数，用于判断是否找到了新的有效频道
        current_valid_count = self._count_valid_channels()
        self.scan_state_manager.update_last_retry_valid_count(self.retry_id, current_valid_count)
        self.logger.debug(f"当前有效频道数: {current_valid_count}")

        self._start_retry_scan()

        self.logger.debug("=== _handle_retry_scan 方法结束 ===")

    def _collect_failed_channels(self):
        """收集失败的频道URL，基于失败原因进行智能重试"""
        # 从扫描状态管理器获取需要重试的 URL 列表（基于失败原因）
        if hasattr(self, 'scanner') and self.scanner:
            # 获取需要重试的 URL（基于失败原因过滤）
            retry_urls = self.scan_state_manager.get_retry_urls(self.scanner.scan_id)

            # 获取已经重试过的 URL，避免重复重试
            retried_urls = self.scan_state_manager.get_retried_urls(self.retry_id)
            
            # 过滤掉已经重试过的 URL
            new_retry_urls = [url for url in retry_urls if url not in retried_urls]
            
            self.logger.debug(f"智能重试：原始={len(retry_urls)}, 已重试={len(retried_urls)}, 新重试={len(new_retry_urls)}")

            # 清空之前的失败频道列表，避免累积
            self.scan_state_manager.clear_failed_channels(self.retry_id)

            # 批量添加到重试扫描状态管理器，优化内存使用
            batch_size = 1000
            total_count = len(new_retry_urls)

            for i in range(0, total_count, batch_size):
                batch = new_retry_urls[i:i+batch_size]
                for url in batch:
                    self.scan_state_manager.add_failed_channel(self.retry_id, url)
                    # 立即标记为已重试，避免重复
                    self.scan_state_manager.add_retried_url(self.retry_id, url)

                # 每处理一批后稍微休息，避免 UI 阻塞
                if i + batch_size < total_count:
                    time.sleep(0.001)  # 1ms 休息，几乎不影响性能

            # 减少日志输出，避免日志过多
            if total_count > 1000:
                self.logger.debug(f"智能重试: 基于失败原因筛选出 {total_count} 个需要重试的URL (大量URL，简化日志)")
                # 只记录前2个需要重试的URL
                for i in range(min(2, total_count)):
                    url = retry_urls[i]
                    self.logger.debug(f"重试URL示例 {i}: {url[:50]}")
                if total_count > 2:
                    self.logger.debug(f"... 还有 {total_count - 2} 个URL")
            else:
                self.logger.debug(f"智能重试: 基于失败原因筛选出 {total_count} 个需要重试的URL")
                # 只记录前3个需要重试的URL
                for i in range(min(3, total_count)):
                    url = retry_urls[i]
                    self.logger.debug(f"重试URL {i}: {url[:50]}")
        else:
            self.logger.warning("ScannerController不存在，无法获取需要重试的URL列表")

        failed_channels = self.scan_state_manager.get_failed_channels(self.retry_id)
        self.logger.debug(f"智能重试收集完成: 需要重试的URL数={len(failed_channels)}")

        # 如果重试URL数量很大，记录警告信息
        if len(failed_channels) > 10000:
            self.logger.warning(f"警告: 有 {len(failed_channels)} 个URL需要重试，可能需要较长时间")
        elif len(failed_channels) > 0:
            # 记录智能重试信息
            self.logger.debug("智能重试开始，准备扫描失败的频道")

    def _count_valid_channels(self):
        """统计当前有效频道数量"""
        count = 0
        for i in range(self.model.rowCount()):
            channel = self.model.get_channel(i)
            if channel and channel.get('valid', False):
                count += 1
        return count

    def _start_retry_scan(self):
        """启动重试扫描 - 第二阶段深度扫描"""
        if not hasattr(self, 'scanner') or self.scanner is None:
            log_ui_error("扫描器未初始化，无法启动重试扫描")
            return
        self.logger.debug("启动重试扫描（第二阶段深度扫描）...")

        # 从扫描状态管理器获取失败的频道
        failed_channels = self.scan_state_manager.get_failed_channels(self.retry_id)

        if not failed_channels:
            self.logger.debug("没有失败的频道需要重试")
            return

        # 直接使用failed_channels作为retry_urls，因为它们都是URL字符串的列表
        retry_urls = failed_channels

        # 第二阶段使用更长的超时时间（15秒），提高慢速频道的检出率
        retry_timeout = 15
        try:
            if hasattr(self, 'config') and self.config:
                network_settings = self.config.load_network_settings()
                configured_timeout = network_settings.get('timeout', 30)
                if configured_timeout and configured_timeout > 0:
                    retry_timeout = max(10, min(30, int(configured_timeout)))
        except Exception:
            pass

        self.logger.info(f"第二阶段深度扫描: {len(retry_urls)} 个URL, 超时={retry_timeout}秒")

        # 使用与第一阶段相同的智能线程数
        cpu_count = os.cpu_count() or 4
        if cpu_count <= 2:
            retry_threads = 5
        elif cpu_count <= 4:
            retry_threads = 6
        elif cpu_count <= 8:
            retry_threads = 7
        else:
            retry_threads = 8

        # 启动深度重试扫描
        self.scanner.start_scan_from_urls(
            retry_urls,
            retry_threads,
            retry_timeout
        )
        
        # 更新按钮文本
        self._set_scan_button_text('stop_scan', '停止扫描')
        self._set_append_scan_button_text('stop_scan', '停止扫描')

    def _handle_retry_scan_completed(self):
        retry_count = self.scan_state_manager.get_retry_count(self.retry_id)
        max_retries = 3

        if retry_count >= max_retries:
            self.logger.info(f"已达到最大重试次数 ({max_retries})，结束重试扫描")
            self.scan_state_manager.clear_failed_channels(self.retry_id)
            return

        current_valid_count = self._count_valid_channels()
        last_valid_count = self.scan_state_manager.get_last_retry_valid_count(self.retry_id)

        new_valid = current_valid_count - last_valid_count
        self.logger.info(f"重试扫描完成: 新增有效={new_valid}, 总有效={current_valid_count}, 重试次数={retry_count}")

        # 改进的重试策略：只要还有失败的频道且未达上限，就继续重试
        # 不再要求必须发现新有效频道才继续（因为超时短可能导致误判）
        failed_channels = self.scan_state_manager.get_failed_channels(self.retry_id)
        
        if retry_count < max_retries and failed_channels and len(failed_channels) > 0:
            # 还有失败频道且重试次数未达上限，继续重试
            self.logger.info(f"还有{len(failed_channels)}个失败频道，继续重试 (第{retry_count + 1}次)")
            self.scan_state_manager.update_last_retry_valid_count(self.retry_id, current_valid_count)
            # 延迟启动下一次重试，让状态有时间更新
            QtCore.QTimer.singleShot(500, self._handle_retry_scan)
        else:
            if not failed_channels or len(failed_channels) == 0:
                self.logger.info("没有更多失败频道需要重试，结束重试扫描")
            elif retry_count >= max_retries:
                self.logger.info(f"重试次数已达上限 ({max_retries})，结束重试扫描")
            else:
                self.logger.info("结束重试扫描")
            # 使用 clear_failed_channels 代替不存在的 reset_retry_scan
            self.scan_state_manager.clear_failed_channels(self.retry_id)


class HeaderDelegate(QtWidgets.QHeaderView):
    """自定义表头委托"""
    def __init__(self, parent=None, model=None):
        super().__init__(QtCore.Qt.Orientation.Horizontal, parent)
        self.model = model