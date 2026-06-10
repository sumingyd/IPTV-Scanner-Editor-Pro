"""
扫描频道窗口模块 - 负责扫描频道功能的UI和事件处理
"""

import os
import time
from PySide6 import QtWidgets, QtCore, QtGui

# 导入自定义模块
from models.channel_model import ChannelListModel
from services.scanner_service import ScannerController
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
from ..floating_dialog import FloatingDialog


class _HomeOnFocusOut(QtCore.QObject):
    """事件过滤器：输入框失去焦点时将光标移到开头，使长文本从起始位置显示"""

    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.Type.FocusOut:
            if isinstance(obj, QtWidgets.QLineEdit):
                obj.setCursorPosition(0)
        return False


class ScanChannelDialog(FloatingDialog):
    """扫描频道窗口类"""
    _bg_color_key = 'window'
    _border_color_key = 'mid'

    def __init__(self, parent=None):
        super().__init__(parent, frameless=False, stay_on_top=False)
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

        self._home_on_focus_out = _HomeOnFocusOut(self)

        # 注册重试扫描任务
        register_retry_task(self.retry_id, self)

        self._init_ui()

        self._init_main_window()

        from ..theme_manager import get_theme_manager
        get_theme_manager().register_window(self)

        self._setup_shortcuts()

    def _get_validator_class(self):
        """根据配置获取验证器类"""
        engine = 'mpv'
        try:
            settings = self.config.load_scan_engine_settings()
            engine = settings.get('engine', 'mpv')
        except Exception:
            pass
        if engine == 'ffprobe':
            from services.ffprobe_validator_service import FfprobeStreamValidator
            return FfprobeStreamValidator
        else:
            from services.mpv_validator_service import MpvStreamValidator
            return MpvStreamValidator

    def done(self, result):
        if hasattr(self, 'scanner') and self.scanner is not None:
            if self.scanner.is_scanning():
                self.scanner.stop_event.set()
                ValidatorClass = self._get_validator_class()
                ValidatorClass.set_terminating()
            if getattr(self.scanner, 'is_validating', False):
                self.scanner.stop_validation()
        self._stop_all_timers()
        self._unregister_cleanup_handlers()
        self._unregister_config_observers()
        from ..theme_manager import get_theme_manager
        get_theme_manager().unregister_window(self)
        super().done(result)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            widget = QtWidgets.QApplication.widgetAt(event.globalPosition().toPoint())
            if widget:
                interactive_types = (
                    QtWidgets.QAbstractButton,
                    QtWidgets.QLineEdit,
                    QtWidgets.QComboBox,
                    QtWidgets.QCheckBox,
                    QtWidgets.QScrollBar,
                    QtWidgets.QTableView,
                    QtWidgets.QTreeView,
                    QtWidgets.QListView,
                    QtWidgets.QAbstractSlider,
                    QtWidgets.QAbstractSpinBox,
                )
                w = widget
                while w:
                    if isinstance(w, interactive_types):
                        return
                    w = w.parent()
                if hasattr(self, 'channel_list') and self.channel_list.selectionModel():
                    self.channel_list.clearSelection()
        super().mousePressEvent(event)

    def reapply_styles(self):
        colors = AppStyles._get_colors()
        for child in self.findChildren(QtWidgets.QPushButton):
            child.setStyleSheet(AppStyles.common_button_style())
        for child in self.findChildren(QtWidgets.QLineEdit):
            child.setStyleSheet(AppStyles.common_line_edit_style())
        for child in self.findChildren(QtWidgets.QComboBox):
            child.setStyleSheet(AppStyles.common_combo_box_style())
        for child in self.findChildren(QtWidgets.QCheckBox):
            child.setStyleSheet(AppStyles.common_check_box_style())
        for child in self.findChildren(QtWidgets.QGroupBox):
            child.setStyleSheet(AppStyles.common_group_box_style())
        for child in self.findChildren(QtWidgets.QTableView):
            child.setStyleSheet(AppStyles.list_style())
        for child in self.findChildren(QtWidgets.QTabWidget):
            child.setStyleSheet(AppStyles.tab_widget_style())
        if hasattr(self, 'channel_table'):
            self.channel_table.setStyleSheet(AppStyles.list_style())
        if hasattr(self, '_empty_hint_label') and self._empty_hint_label:
            self._empty_hint_label.setStyleSheet(
                f"color: {colors['player_panel_hint']}; font-size: 14px; padding: 40px;"
            )

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
        if hasattr(self, 'scanner') and self.scanner:
            for attr in ('_batch_timer',):
                try:
                    timer = getattr(self.scanner, attr, None)
                    if timer and hasattr(timer, 'isActive') and timer.isActive():
                        if QtCore.QThread.currentThread() == timer.thread():
                            timer.stop()
                        else:
                            QtCore.QMetaObject.invokeMethod(
                                timer, "stop", QtCore.Qt.ConnectionType.QueuedConnection
                            )
                except Exception as e:
                    self.logger.error(f"停止扫描器定时器失败: {e}")

    def _init_ui(self):
        """初始化用户界面"""
        tr = self.language_manager.tr
        self.setWindowTitle(tr("scan_window_title", "IPTV Scanner"))
        from utils.general_utils import get_icon_path
        ico_path = get_icon_path()
        if os.path.exists(ico_path):
            from PySide6.QtGui import QIcon
            self.setWindowIcon(QIcon(ico_path))
        self.setWindowFlags(QtCore.Qt.WindowType.FramelessWindowHint | QtCore.Qt.WindowType.Window)
        # 设置透明背景，实现圆角窗口效果
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
        # 确保窗口可以接收鼠标事件
        self.setMouseTracking(True)
        # 确保窗口保持活动状态
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)

        # 根据屏幕尺寸动态计算窗口大小，不超过90%屏幕
        screen = QtWidgets.QApplication.primaryScreen()
        if screen:
            avail = screen.availableGeometry()
            max_w = int(avail.width() * 0.9)
            max_h = int(avail.height() * 0.9)
            self.resize(min(1400, max_w), min(800, max_h))
        else:
            self.resize(1400, 800)

        # 先设置窗口样式，避免闪烁
        self.setStyleSheet(AppStyles.popup_dialog_style())

        # 扫描频道窗口不需要状态栏
        # 创建进度条用于显示扫描进度
        self.progress_indicator = QtWidgets.QProgressBar()
        self.progress_indicator.setRange(0, 100)
        self.progress_indicator.setValue(0)
        self.progress_indicator.setTextVisible(True)
        self.progress_indicator.setMinimumWidth(150)
        self.progress_indicator.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
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

        # ========== 左侧边栏：扫描设置 (弹性宽度 240~320px) ==========
        left_panel = QtWidgets.QWidget()
        left_panel.setMinimumWidth(240)
        left_panel.setMaximumWidth(320)
        left_panel.setStyleSheet(AppStyles.side_panel_style())
        left_layout = QtWidgets.QVBoxLayout(left_panel)
        left_layout.setContentsMargins(12, 12, 12, 12)
        left_layout.setSpacing(8)

        # 左侧标题栏
        self.left_title = QtWidgets.QLabel(tr('scan_settings_title', 'Scan Settings'))
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
        self.close_btn = QtWidgets.QPushButton(tr('close_button', 'Close'))
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
        self.list_title = QtWidgets.QLabel(tr('channel_list_title', 'Channel List'))
        self.list_title.setStyleSheet(AppStyles.section_title_style())
        list_header.addWidget(self.list_title)
        list_header.addStretch()

        # 搜索过滤框
        self.search_input = QtWidgets.QLineEdit()
        self.search_input.setPlaceholderText(tr("search_filter_hint", "搜索频道名/URL/分组..."))
        self.search_input.setFixedHeight(28)
        self.search_input.setFixedWidth(180)
        self.search_input.setStyleSheet(AppStyles.common_line_edit_style())
        self.search_input.setClearButtonEnabled(True)
        list_header.addWidget(self.search_input)

        # 将工具栏按钮移到标题栏
        self._setup_list_toolbar(list_header)
        center_layout.addLayout(list_header)

        # 频道列表
        self._setup_channel_list(center_layout)

        # 底部状态栏
        status_layout = QtWidgets.QHBoxLayout()
        status_layout.setContentsMargins(0, 5, 0, 0)
        self.progress_indicator.setFixedHeight(24)
        status_layout.addWidget(self.progress_indicator)
        status_layout.addWidget(self.stats_label)
        status_layout.addStretch()
        center_layout.addLayout(status_layout)

        main_layout.addWidget(center_panel, 1)

        # 中间间隔
        main_layout.addSpacing(12)

        # ========== 右侧边栏：频道编辑 (弹性宽度 200~280px) ==========
        right_panel = QtWidgets.QWidget()
        right_panel.setMinimumWidth(200)
        right_panel.setMaximumWidth(280)
        right_panel.setStyleSheet(AppStyles.side_panel_style())
        right_layout = QtWidgets.QVBoxLayout(right_panel)
        right_layout.setContentsMargins(12, 12, 12, 12)
        right_layout.setSpacing(8)

        # 右侧标题
        self.right_title = QtWidgets.QLabel(tr('channel_edit_title', 'Channel Edit'))
        self.right_title.setStyleSheet(AppStyles.section_title_style())
        right_layout.addWidget(self.right_title)

        # 频道编辑内容
        self._setup_channel_edit(right_layout)

        main_layout.addWidget(right_panel)

        # QDialog使用setLayout直接设置布局
        self.setLayout(main_layout)

    def _connect_input_signals(self):
        """在_load_config加载完所有值后，再连接输入控件的保存信号"""
        self.ip_range_input.lineEdit().editingFinished.connect(self._save_network_settings)
        self.user_agent_input.textChanged.connect(self._save_network_settings)
        self.referer_input.textChanged.connect(self._save_network_settings)
        self.timeout_input.textChanged.connect(self._save_network_settings)
        self.threads_input.textChanged.connect(self._save_network_settings)

    def _save_network_settings(self):
        """保存网络设置到配置文件（提取的重复代码）"""
        from utils.config_notifier import config_change_context
        with config_change_context("Network", "url"):
            timeout_val = 5
            threads_val = 4
            if hasattr(self, 'timeout_input'):
                timeout_val = self.timeout_input.text()
            if hasattr(self, 'threads_input'):
                threads_val = self.threads_input.text()
            self.config.save_network_settings(
                self.ip_range_input.currentText(),
                timeout_val,
                threads_val,
                self.user_agent_input.text(),
                self.referer_input.text()
            )

    def _add_url_to_history(self, url):
        """将URL添加到历史记录（去重，最近使用的排最前，最多10条）"""
        if not url or not url.strip():
            return
        url = url.strip()
        current_items = [self.ip_range_input.itemText(i) for i in range(self.ip_range_input.count())]
        if url in current_items:
            current_items.remove(url)
        current_items.insert(0, url)
        current_items = current_items[:10]
        self.ip_range_input.clear()
        self.ip_range_input.addItems(current_items)
        self.ip_range_input.setCurrentText(url)
        self.config.save_url_history(current_items)

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
        self.ip_range_input = QtWidgets.QComboBox()
        self.ip_range_input.setEditable(True)
        self.ip_range_input.setInsertPolicy(QtWidgets.QComboBox.InsertPolicy.NoInsert)
        self.ip_range_input.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
        self.ip_range_input.setSizeAdjustPolicy(QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.ip_range_input.setMinimumContentsLength(20)
        self.ip_range_input.completer().setCompletionMode(QtWidgets.QCompleter.CompletionMode.PopupCompletion)
        self.ip_range_input.setFixedHeight(34)
        self.ip_range_input.lineEdit().installEventFilter(self._home_on_focus_out)

        self._setup_user_agent_input()

        self._setup_referer_input()

        self._setup_timeout_threads_input()

    def _setup_user_agent_input(self):
        """设置User-Agent输入控件"""
        tr = self.language_manager.tr
        user_agent_layout = QtWidgets.QHBoxLayout()
        user_agent_label = QtWidgets.QLabel("User-Agent:")
        user_agent_label.setStyleSheet(AppStyles.small_label_style())
        self.user_agent_label = user_agent_label
        user_agent_layout.addWidget(user_agent_label)
        self.user_agent_input = QtWidgets.QLineEdit()
        self.user_agent_input.setPlaceholderText(tr("optional_default_input", "Optional, use default if empty"))
        self.user_agent_input.setFixedHeight(34)
        self.user_agent_input.installEventFilter(self._home_on_focus_out)
        user_agent_layout.addWidget(self.user_agent_input)
        self.user_agent_layout = user_agent_layout

    def _setup_referer_input(self):
        """设置Referer输入控件"""
        tr = self.language_manager.tr
        referer_layout = QtWidgets.QHBoxLayout()
        referer_label = QtWidgets.QLabel("Referer:")
        referer_label.setStyleSheet(AppStyles.small_label_style())
        self.referer_label = referer_label
        referer_layout.addWidget(referer_label)
        self.referer_input = QtWidgets.QLineEdit()
        self.referer_input.setPlaceholderText(tr("optional_not_used_input", "Optional, not used if empty"))
        self.referer_input.setFixedHeight(34)
        self.referer_input.installEventFilter(self._home_on_focus_out)
        referer_layout.addWidget(self.referer_input)
        self.referer_layout = referer_layout

    def _setup_timeout_threads_input(self):
        """设置超时和线程数输入控件（两行独立布局）"""
        tr = self.language_manager.tr

        timeout_threads_layout = QtWidgets.QVBoxLayout()
        timeout_threads_layout.setSpacing(4)

        timeout_row = QtWidgets.QHBoxLayout()
        timeout_row.setSpacing(6)
        timeout_label = QtWidgets.QLabel(tr("scan_timeout", "Timeout(s):"))
        self.timeout_label = timeout_label
        timeout_row.addWidget(timeout_label)
        self.timeout_input = QtWidgets.QLineEdit("10")
        self.timeout_input.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
        self.timeout_input.setPlaceholderText("1-60")
        self.timeout_input.setFixedHeight(34)
        timeout_row.addWidget(self.timeout_input)
        timeout_threads_layout.addLayout(timeout_row)

        threads_row = QtWidgets.QHBoxLayout()
        threads_row.setSpacing(6)
        threads_label = QtWidgets.QLabel(tr("scan_threads", "Threads:"))
        self.threads_label = threads_label
        threads_row.addWidget(threads_label)
        self.threads_input = QtWidgets.QLineEdit("4")
        self.threads_input.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
        self.threads_input.setPlaceholderText("1-64")
        self.threads_input.setFixedHeight(34)
        threads_row.addWidget(self.threads_input)
        timeout_threads_layout.addLayout(threads_row)

        self.timeout_threads_layout = timeout_threads_layout

        self._load_timeout_threads_settings()

    def _setup_scan_engine_options(self):
        """设置扫描引擎选项"""
        tr = self.language_manager.tr
        engine_layout = QtWidgets.QHBoxLayout()
        engine_label = QtWidgets.QLabel(f"{tr('scan_engine', 'Scan Engine')}：")
        self.scan_engine_label = engine_label
        engine_layout.addWidget(engine_label)

        self.scan_engine_combo = QtWidgets.QComboBox()
        self.scan_engine_combo.addItem("mpv", "mpv")
        self.scan_engine_combo.addItem("ffprobe", "ffprobe")
        self.scan_engine_combo.setFixedHeight(28)
        self.scan_engine_combo.setToolTip(
            tr("scan_engine_tooltip", "Select the core engine for scanning and validation")
        )
        engine_layout.addWidget(self.scan_engine_combo, 1)

        self.scan_engine_combo.currentIndexChanged.connect(
            lambda: self._save_scan_engine_settings()
        )

        self._load_scan_engine_settings()

        self.scan_engine_layout = engine_layout

    def _save_scan_engine_settings(self):
        """保存扫描引擎设置到配置文件"""
        engine = self.scan_engine_combo.currentData() or 'mpv'
        self.config.save_scan_engine_settings(engine)

    def _load_scan_engine_settings(self):
        """加载扫描引擎设置"""
        try:
            settings = self.config.load_scan_engine_settings()
            engine = settings.get('engine', 'mpv')
            index = self.scan_engine_combo.findData(engine)
            if index >= 0:
                self.scan_engine_combo.setCurrentIndex(index)
        except Exception as e:
            self.logger.error(f"加载扫描引擎设置失败: {e}")

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
        self.config.save_scan_retry_settings(enable_retry)

    def _load_scan_retry_settings(self):
        """加载重试扫描设置"""
        try:
            settings = self.config.load_scan_retry_settings()
            enable_retry = settings['enable_retry']
            self.enable_retry_checkbox.setChecked(enable_retry)
        except Exception as e:
            self.logger.error(f"加载重试扫描设置失败: {e}")

    def _get_scan_params(self, default_timeout=10, default_threads=4, timeout_multiplier=1):
        """从UI输入框读取扫描参数，若无效则使用配置文件或默认值

        Args:
            default_timeout: 默认超时秒数
            default_threads: 默认线程数
            timeout_multiplier: 超时倍率（重试时可用2倍超时）

        Returns:
            (timeout, threads) 元组
        """
        timeout = default_timeout
        threads = default_threads

        if hasattr(self, 'timeout_input') and self.timeout_input:
            try:
                ui_timeout = int(self.timeout_input.text().strip())
                if ui_timeout > 0:
                    timeout = max(3, min(60, ui_timeout * timeout_multiplier))
            except (ValueError, AttributeError):
                pass

        if hasattr(self, 'threads_input') and self.threads_input:
            try:
                ui_threads = int(self.threads_input.text().strip())
                if ui_threads > 0:
                    threads = max(1, min(32, ui_threads))
            except (ValueError, AttributeError):
                pass

        if timeout == default_timeout and threads == default_threads:
            try:
                if hasattr(self, 'config') and self.config:
                    network_settings = self.config.load_network_settings()
                    configured_timeout = network_settings.get('timeout', default_timeout)
                    if configured_timeout and configured_timeout > 0:
                        timeout = max(3, min(60, int(configured_timeout) * timeout_multiplier))
                    configured_threads = network_settings.get('threads', default_threads)
                    if configured_threads and configured_threads > 0:
                        threads = max(1, min(32, int(configured_threads)))
            except Exception as e:
                self.logger.debug(f"读取扫描配置失败，使用默认值: {e}")
        return timeout, threads

    def _load_timeout_threads_settings(self):
        """加载超时和线程数设置"""
        try:
            if hasattr(self, 'config') and self.config:
                network_settings = self.config.load_network_settings()
                timeout = network_settings.get('timeout', 10)
                threads = network_settings.get('threads', 4)
                if hasattr(self, 'timeout_input'):
                    self.timeout_input.setText(str(timeout))
                if hasattr(self, 'threads_input'):
                    self.threads_input.setText(str(threads))
        except Exception as e:
            self.logger.debug(f"加载超时线程设置失败: {e}")

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
        self.btn_scan.setMinimumHeight(32)
        self.btn_scan.setAutoDefault(False)
        self.btn_scan.setToolTip(tr("full_scan_tooltip", "扫描所有URL并验证有效性"))

        # 新增追加扫描按钮
        self.btn_append_scan = QtWidgets.QPushButton(tr("append_scan", "Append Scan"))
        self.btn_append_scan.setStyleSheet(AppStyles.common_button_style())
        self.btn_append_scan.setMinimumHeight(32)  # 减少按钮高度
        self.btn_append_scan.setToolTip(tr("append_scan_tooltip", "Append valid channels to existing list without clearing"))
        self.btn_append_scan.setAutoDefault(False)

        # 新增直接生成列表按钮
        self.btn_generate = QtWidgets.QPushButton(tr("generate_list", "Generate List"))
        self.btn_generate.setStyleSheet(AppStyles.common_button_style())
        self.btn_generate.setMinimumHeight(32)
        self.btn_generate.setToolTip(tr("generate_list_tooltip", "仅生成URL列表不验证"))

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

        # 设置扫描引擎选项
        self._setup_scan_engine_options()

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
        self.ip_range_input.setMinimumHeight(32)
        self.ip_range_input.setStyleSheet(AppStyles.url_combo_style())
        address_section.addWidget(self.ip_range_input)

        scan_layout.addLayout(address_section)
        scan_layout.addSpacing(12)

        # 扫描设置（简化标题）
        scan_settings_section = QtWidgets.QVBoxLayout()
        scan_settings_section.setSpacing(8)

        # User-Agent（简化标签）
        scan_settings_section.addWidget(self.user_agent_label)
        self.user_agent_input.setFixedHeight(28)
        scan_settings_section.addWidget(self.user_agent_input)

        # Referer（简化标签）
        scan_settings_section.addWidget(self.referer_label)
        self.referer_input.setFixedHeight(28)
        scan_settings_section.addWidget(self.referer_input)

        # 超时和线程数
        if hasattr(self, 'timeout_threads_layout'):
            scan_settings_section.addLayout(self.timeout_threads_layout)

        scan_layout.addLayout(scan_settings_section)
        scan_layout.addSpacing(12)

        # 选项（简化）
        options_section = QtWidgets.QVBoxLayout()
        options_section.setSpacing(8)
        if hasattr(self, 'scan_engine_layout'):
            options_section.addLayout(self.scan_engine_layout)
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

        # 设置搜索过滤代理模型
        self._filter_proxy = QtCore.QSortFilterProxyModel(self)
        self._filter_proxy.setSourceModel(self.model)
        self._filter_proxy.setFilterCaseSensitivity(QtCore.Qt.CaseSensitivity.CaseInsensitive)
        self._filter_proxy.setFilterKeyColumn(-1)
        self.channel_list.setModel(self._filter_proxy)

        # 使用与主窗口一致的列表样式
        self.channel_list.setStyleSheet(AppStyles.list_style())

        # 设置表头
        self.header = self.channel_list.horizontalHeader()
        self.header.setStretchLastSection(False)  # 禁用最后列自动拉伸
        self.header.setMinimumSectionSize(30)  # 最小列宽
        self.header.setMaximumSectionSize(1000)  # 最大列宽

        # 设置表头属性
        self.header.setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Interactive)
        self.header.setDefaultSectionSize(100)

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

        # 空状态提示标签（使用QStackedWidget切换列表/提示）
        tr_local = self.language_manager.tr
        _hint_colors = AppStyles._get_colors()
        self._empty_hint = QtWidgets.QLabel(tr_local("empty_list_hint", "输入地址后点击扫描，或打开已有列表"))
        self._empty_hint.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._empty_hint.setStyleSheet(f"color: {_hint_colors['player_panel_hint']}; font-size: 14px; padding: 40px;")
        self._empty_hint.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._empty_stack = QtWidgets.QStackedWidget()
        self._empty_stack.addWidget(self.channel_list)
        self._empty_stack.addWidget(self._empty_hint)
        parent.addWidget(self._empty_stack, 1)
        self.model.rowsInserted.connect(lambda *_: self._update_empty_hint())
        self.model.rowsRemoved.connect(lambda *_: self._update_empty_hint())
        self.model.modelReset.connect(self._update_empty_hint)
        self._update_empty_hint()

    def _setup_list_toolbar(self, toolbar_layout):
        """设置频道列表的工具栏按钮（用于标题栏）"""
        tr = self.language_manager.tr
        # 打开列表按钮
        self.btn_open_list = QtWidgets.QPushButton(tr("open_list", "Open List"))
        self.btn_open_list.setStyleSheet(AppStyles.common_button_style())
        self.btn_open_list.setFixedHeight(32)
        self.btn_open_list.setMinimumWidth(60)
        self.btn_open_list.setToolTip(tr("open_list_tooltip", "Import M3U file to channel list for validation"))

        self.btn_validate = QtWidgets.QPushButton(tr("validate_button", "Validate"))
        self.btn_validate.setStyleSheet(AppStyles.common_button_style())
        self.btn_validate.setFixedHeight(32)
        self.btn_validate.setMinimumWidth(55)
        self.btn_validate.setToolTip(tr("validate_tooltip", "Validate channel effectiveness"))

        self.btn_hide_invalid = QtWidgets.QPushButton(tr("hide_invalid_button", "Hide Invalid"))
        self.btn_hide_invalid.setStyleSheet(AppStyles.common_button_style())
        self.btn_hide_invalid.setFixedHeight(32)
        self.btn_hide_invalid.setMinimumWidth(70)
        self.btn_hide_invalid.setEnabled(False)

        self.btn_save_m3u = QtWidgets.QPushButton(tr("save_m3u", "Save M3U"))
        self.btn_save_m3u.setStyleSheet(AppStyles.common_button_style())
        self.btn_save_m3u.setFixedHeight(32)
        self.btn_save_m3u.setMinimumWidth(65)
        self.btn_save_m3u.setToolTip(tr("save_m3u_tooltip", "Save channel list as M3U format"))

        self.btn_save_txt = QtWidgets.QPushButton(tr("save_txt", "Save TXT"))
        self.btn_save_txt.setStyleSheet(AppStyles.common_button_style())
        self.btn_save_txt.setFixedHeight(32)
        self.btn_save_txt.setMinimumWidth(65)
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
        toolbar_layout.addSpacing(6)

        self.btn_batch_ops = QtWidgets.QPushButton(tr("batch_ops", "Batch Ops"))
        self.btn_batch_ops.setStyleSheet(AppStyles.common_button_style())
        self.btn_batch_ops.setFixedHeight(32)
        self.btn_batch_ops.setMinimumWidth(70)
        self.btn_batch_ops.setToolTip(tr("batch_ops_tooltip", "Batch operations for channels"))
        self.btn_batch_ops.setMenu(self._create_batch_menu())
        toolbar_layout.addWidget(self.btn_batch_ops)

    def _create_batch_menu(self) -> QtWidgets.QMenu:
        tr = self.language_manager.tr
        menu = QtWidgets.QMenu(self)
        menu.setStyleSheet(AppStyles.common_menu_style())

        auto_classify_action = QtGui.QAction(tr("auto_classify", "Auto Classify"), self)
        auto_classify_action.triggered.connect(self._show_auto_classify_dialog)
        menu.addAction(auto_classify_action)

        clean_names_action = QtGui.QAction(tr("clean_names", "Clean Names"), self)
        clean_names_action.triggered.connect(self._show_clean_names_dialog)
        menu.addAction(clean_names_action)

        assign_fields_action = QtGui.QAction(tr("assign_fields", "Assign Fields"), self)
        assign_fields_action.triggered.connect(self._show_assign_fields_dialog)
        menu.addAction(assign_fields_action)

        match_logo_action = QtGui.QAction(tr("match_logo", "Match Logo"), self)
        match_logo_action.triggered.connect(self._auto_match_logo)
        menu.addAction(match_logo_action)

        menu.addSeparator()

        clear_params_action = QtGui.QAction(tr("clear_params", "Clear Params"), self)
        clear_params_action.triggered.connect(self._show_clear_params_dialog)
        menu.addAction(clear_params_action)

        sort_by_group_action = QtGui.QAction(tr("sort_by_group", "Sort by Group"), self)
        sort_by_group_action.triggered.connect(self._sort_by_group)
        menu.addAction(sort_by_group_action)

        return menu

    def _get_all_channels(self) -> list:
        from models.channel_model import ChannelListModel as CLM
        if hasattr(self, '_channels_cache') and self._channels_cache is not None:
            return self._channels_cache
        channels = []
        for row in range(self.model.rowCount()):
            ch = {}
            ch['_index'] = row
            ch['name'] = str(self.model.data(self.model.index(row, CLM.COL_NAME)) or '')
            ch['url'] = str(self.model.data(self.model.index(row, CLM.COL_URL)) or '')
            ch['group'] = str(self.model.data(self.model.index(row, CLM.COL_GROUP)) or '')
            ch['logo'] = str(self.model.data(self.model.index(row, CLM.COL_LOGO)) or '')
            ch['tvg_id'] = str(self.model.data(self.model.index(row, CLM.COL_TVG_ID)) or '')
            ch['tvg_chno'] = str(self.model.data(self.model.index(row, CLM.COL_TVG_CHNO)) or '')
            ch['catchup'] = str(self.model.data(self.model.index(row, CLM.COL_CATCHUP)) or '')
            ch['catchup_days'] = str(self.model.data(self.model.index(row, CLM.COL_CATCHUP_DAYS)) or '')
            ch['catchup_source'] = str(self.model.data(self.model.index(row, CLM.COL_CATCHUP_SOURCE)) or '')
            raw_ch = self.model.channels[row] if row < len(self.model.channels) else {}
            ch['_all_tags'] = raw_ch.get('_all_tags', {})
            channels.append(ch)
        self._channels_cache = channels
        return channels

    def _invalidate_channels_cache(self):
        """数据变更时清除频道缓存"""
        self._channels_cache = None

    def _get_selected_indices(self) -> list:
        indices = []
        for index in self.channel_list.selectionModel().selectedRows():
            if hasattr(self, '_filter_proxy'):
                source_row = self._filter_proxy.mapToSource(index).row()
            else:
                source_row = index.row()
            indices.append(source_row)
        return sorted(indices)

    def _show_auto_classify_dialog(self):
        from services.channel_classifier import ChannelClassifier
        from models.channel_model import ChannelListModel as CLM
        tr = self.language_manager.tr

        channels = self._get_all_channels()
        if not channels:
            return

        dialog = FloatingDialog(self, stay_on_top=True)
        dialog.setWindowTitle(tr("auto_classify", "Auto Classify"))
        dialog.setMinimumSize(420, 380)
        dialog.setStyleSheet(AppStyles.dialog_style())

        layout = QtWidgets.QVBoxLayout(dialog)

        form_layout = QtWidgets.QFormLayout()
        province_combo = QtWidgets.QComboBox()
        province_combo.addItems(ChannelClassifier.PROVINCES)
        province_combo.setCurrentText('通用')
        form_layout.addRow(tr("local_province", "Local Province:"), province_combo)

        overwrite_check = QtWidgets.QCheckBox(tr("overwrite_existing", "Overwrite existing groups"))
        overwrite_check.setChecked(True)
        form_layout.addRow(overwrite_check)

        merge_nonlocal_check = QtWidgets.QCheckBox(tr("merge_nonlocal", "Merge non-local to Other"))
        merge_nonlocal_check.setChecked(True)
        form_layout.addRow(merge_nonlocal_check)

        layout.addLayout(form_layout)

        preview_label = QtWidgets.QLabel(tr("preview_count", "Preview:"))
        layout.addWidget(preview_label)

        preview_table = QtWidgets.QTableWidget(0, 3)
        preview_table.setHorizontalHeaderLabels([
            tr("channel_name", "Channel Name"),
            tr("old_group", "Old Group"),
            tr("new_group", "New Group"),
        ])
        preview_table.horizontalHeader().setStretchLastSection(True)
        preview_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        preview_table.setMaximumHeight(200)
        layout.addWidget(preview_table)

        btn_layout = QtWidgets.QHBoxLayout()
        preview_btn = QtWidgets.QPushButton(tr("preview", "Preview"))
        apply_btn = QtWidgets.QPushButton(tr("apply", "Apply"))
        cancel_btn = QtWidgets.QPushButton(tr("cancel", "Cancel"))
        btn_layout.addWidget(preview_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(apply_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        classifier_ref = [None]  # type: list
        results_ref = [None]  # type: list

        def do_preview():
            province = province_combo.currentText()
            overwrite = overwrite_check.isChecked()
            merge_nonlocal = merge_nonlocal_check.isChecked()
            classifier = ChannelClassifier(local_province=province)
            results = classifier.classify_all(channels, overwrite=overwrite)
            if merge_nonlocal:
                local_cats = {province, '央视频道', 'CGTN', 'CETV'}
                for r in results:
                    if r.get('new_group') not in local_cats and r.get('new_group') != '其他频道':
                        r['new_group'] = '其他频道'
                        r['changed'] = True
            classifier_ref[0] = classifier
            results_ref[0] = results
            changed = [r for r in results if r.get('changed')]
            preview_label.setText(tr("preview_count", "Preview:") + f" {len(changed)} changed")
            preview_table.setRowCount(min(len(changed), 50))
            for i, r in enumerate(changed[:50]):
                preview_table.setItem(i, 0, QtWidgets.QTableWidgetItem(str(r.get('name', ''))))
                preview_table.setItem(i, 1, QtWidgets.QTableWidgetItem(str(r.get('old_group', ''))))
                preview_table.setItem(i, 2, QtWidgets.QTableWidgetItem(str(r.get('new_group', ''))))

        def do_apply():
            if results_ref[0] is None:
                do_preview()
            results = results_ref[0]
            if not results:
                dialog.accept()
                return
            changed = [r for r in results if r.get('changed')]
            for r in changed:
                row = r.get('index', 0)
                self.model.setData(self.model.index(row, CLM.COL_GROUP), r.get('new_group', ''))
            dialog.accept()

        preview_btn.clicked.connect(do_preview)
        apply_btn.clicked.connect(do_apply)
        cancel_btn.clicked.connect(dialog.reject)

        self._exec_themed_dialog(dialog)

    def _show_clean_names_dialog(self):
        from services.channel_cleaner import ChannelCleaner
        from models.channel_model import ChannelListModel as CLM
        tr = self.language_manager.tr

        channels = self._get_all_channels()
        if not channels:
            return

        dialog = FloatingDialog(self, stay_on_top=True)
        dialog.setWindowTitle(tr("clean_names", "Clean Names"))
        dialog.setMinimumSize(420, 400)
        dialog.setStyleSheet(AppStyles.dialog_style())

        layout = QtWidgets.QVBoxLayout(dialog)

        cleaner = ChannelCleaner()
        rule_checks = {}
        for key, desc in cleaner.get_rule_descriptions():
            cb = QtWidgets.QCheckBox(desc)
            cb.setChecked(True)
            rule_checks[key] = cb
            layout.addWidget(cb)

        selected_indices = self._get_selected_indices()
        target_label = QtWidgets.QLabel(
            tr("target_channels", "Target:") + " " +
            (f"{len(selected_indices)} selected" if selected_indices else f"{len(channels)} all")
        )
        layout.addWidget(target_label)

        preview_table = QtWidgets.QTableWidget(0, 2)
        preview_table.setHorizontalHeaderLabels([
            tr("before", "Before"),
            tr("after", "After"),
        ])
        preview_table.horizontalHeader().setStretchLastSection(True)
        preview_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        preview_table.setMaximumHeight(200)
        layout.addWidget(preview_table)

        btn_layout = QtWidgets.QHBoxLayout()
        preview_btn = QtWidgets.QPushButton(tr("preview", "Preview"))
        apply_btn = QtWidgets.QPushButton(tr("apply", "Apply"))
        cancel_btn = QtWidgets.QPushButton(tr("cancel", "Cancel"))
        btn_layout.addWidget(preview_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(apply_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        preview_ref = [None]  # type: list

        def get_active_rules():
            return {k: cb.isChecked() for k, cb in rule_checks.items()}

        def do_preview():
            rules = get_active_rules()
            indices = selected_indices if selected_indices else list(range(len(channels)))
            preview = cleaner.preview(channels, rules=rules, indices=indices)
            preview_ref[0] = preview
            preview_table.setRowCount(min(len(preview), 50))
            for i, r in enumerate(preview[:50]):
                preview_table.setItem(i, 0, QtWidgets.QTableWidgetItem(str(r.get('name', ''))))
                preview_table.setItem(i, 1, QtWidgets.QTableWidgetItem(str(r.get('cleaned', ''))))

        def do_apply():
            if preview_ref[0] is None:
                do_preview()
            preview = preview_ref[0]
            if not preview:
                dialog.accept()
                return
            for r in preview:
                row = r.get('index', 0)
                self.model.setData(self.model.index(row, CLM.COL_NAME), r.get('cleaned', ''))
            dialog.accept()

        preview_btn.clicked.connect(do_preview)
        apply_btn.clicked.connect(do_apply)
        cancel_btn.clicked.connect(dialog.reject)

        self._exec_themed_dialog(dialog)

    def _show_assign_fields_dialog(self):
        from models.channel_model import ChannelListModel as CLM
        tr = self.language_manager.tr

        channels = self._get_all_channels()
        if not channels:
            return

        dialog = FloatingDialog(self, stay_on_top=True)
        dialog.setWindowTitle(tr("assign_fields", "Assign Fields"))
        dialog.setMinimumSize(380, 300)
        dialog.setStyleSheet(AppStyles.dialog_style())

        layout = QtWidgets.QVBoxLayout(dialog)

        assign_options = [
            ('name2tvg_id', 'Channel Name -> TVG-ID'),
            ('tvg_id2name', 'TVG-ID -> Channel Name'),
            ('tvg_name2name', 'TVG-Name(from tags) -> Channel Name'),
            ('tvg_id2tvg_chno', 'TVG-ID -> TVG-CHNO'),
        ]

        radio_group = QtWidgets.QButtonGroup(self)
        for i, (key, label) in enumerate(assign_options):
            rb = QtWidgets.QRadioButton(label)
            if i == 0:
                rb.setChecked(True)
            radio_group.addButton(rb, i)
            layout.addWidget(rb)

        only_empty_check = QtWidgets.QCheckBox(tr("only_empty_fields", "Only assign to empty fields"))
        only_empty_check.setChecked(True)
        layout.addWidget(only_empty_check)

        selected_indices = self._get_selected_indices()
        target_label = QtWidgets.QLabel(
            tr("target_channels", "Target:") + " " +
            (f"{len(selected_indices)} selected" if selected_indices else f"{len(channels)} all")
        )
        layout.addWidget(target_label)

        preview_table = QtWidgets.QTableWidget(0, 2)
        preview_table.setHorizontalHeaderLabels([tr("before", "Before"), tr("after", "After")])
        preview_table.horizontalHeader().setStretchLastSection(True)
        preview_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        preview_table.setMaximumHeight(200)
        layout.addWidget(preview_table)

        btn_layout = QtWidgets.QHBoxLayout()
        preview_btn = QtWidgets.QPushButton(tr("preview", "Preview"))
        apply_btn = QtWidgets.QPushButton(tr("apply", "Apply"))
        cancel_btn = QtWidgets.QPushButton(tr("cancel", "Cancel"))
        btn_layout.addWidget(preview_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(apply_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        preview_ref = [None]

        def _compute_assign(action_key, only_empty, indices):
            results = []
            for i in indices:
                if i >= len(channels):
                    continue
                ch = channels[i]
                src_val = None
                dst_col = None
                dst_val = None
                if action_key == 'name2tvg_id':
                    if not (only_empty and ch.get('tvg_id')):
                        src_val = ch.get('name', '')
                        dst_col = CLM.COL_TVG_ID
                        dst_val = ch.get('name', '')
                elif action_key == 'tvg_id2name':
                    if ch.get('tvg_id') and not (only_empty and ch.get('name')):
                        src_val = ch.get('tvg_id', '')
                        dst_col = CLM.COL_NAME
                        dst_val = ch.get('tvg_id', '')
                elif action_key == 'tvg_name2name':
                    tvg_name = ch.get('_all_tags', {}).get('tvg-name', '')
                    if tvg_name and not (only_empty and ch.get('name')):
                        src_val = tvg_name
                        dst_col = CLM.COL_NAME
                        dst_val = tvg_name
                elif action_key == 'tvg_id2tvg_chno':
                    if ch.get('tvg_id') and not (only_empty and ch.get('tvg_chno')):
                        src_val = ch.get('tvg_id', '')
                        dst_col = CLM.COL_TVG_CHNO
                        dst_val = ch.get('tvg_id', '')
                if dst_col is not None and dst_val:
                    results.append({'index': i, 'src': src_val, 'dst': dst_val, 'col': dst_col})
            return results

        def do_preview():
            action_idx = radio_group.checkedId()
            action_key = assign_options[action_idx][0] if 0 <= action_idx < len(assign_options) else assign_options[0][0]
            only_empty = only_empty_check.isChecked()
            indices = selected_indices if selected_indices else list(range(len(channels)))
            results = _compute_assign(action_key, only_empty, indices)
            preview_ref[0] = results
            preview_table.setRowCount(min(len(results), 50))
            for i, r in enumerate(results[:50]):
                preview_table.setItem(i, 0, QtWidgets.QTableWidgetItem(str(r.get('src', ''))))
                preview_table.setItem(i, 1, QtWidgets.QTableWidgetItem(str(r.get('dst', ''))))

        def do_apply():
            if preview_ref[0] is None:
                do_preview()
            results = preview_ref[0]
            if not results:
                dialog.accept()
                return
            for r in results:
                self.model.setData(self.model.index(r['index'], r['col']), r['dst'])
            self._invalidate_channels_cache()
            dialog.accept()

        preview_btn.clicked.connect(do_preview)
        apply_btn.clicked.connect(do_apply)
        cancel_btn.clicked.connect(dialog.reject)

        self._exec_themed_dialog(dialog)

    def _auto_match_logo(self):
        tr = self.language_manager.tr
        channels = self._get_all_channels()
        if not channels:
            return

        reply = QtWidgets.QMessageBox.question(
            self,
            tr("match_logo", "Match Logo"),
            tr("overwrite_logo_confirm", "Overwrite existing logos?"),
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No | QtWidgets.QMessageBox.StandardButton.Cancel,
        )

        if reply == QtWidgets.QMessageBox.StandardButton.Cancel:
            return

        overwrite = (reply == QtWidgets.QMessageBox.StandardButton.Yes)

        try:
            from services.logo_matcher import LogoMatcher
            from models.channel_model import ChannelListModel as CLM
            matcher = LogoMatcher()
            updates = []
            for i, ch in enumerate(channels):
                if not overwrite and ch.get('logo'):
                    continue
                logo = matcher.match(ch.get('name', ''))
                if logo:
                    updates.append((i, logo))

            self.model.layoutAboutToBeChanged.emit()
            for i, logo in updates:
                self.model.setData(self.model.index(i, CLM.COL_LOGO), logo)
            self.model.layoutChanged.emit()
            self._invalidate_channels_cache()

            QtWidgets.QMessageBox.information(
                self, tr("match_logo", "Match Logo"),
                f"{len(updates)} channels matched"
            )
        except ImportError:
            self.logger.warning("Logo匹配模块不可用")
            QtWidgets.QMessageBox.warning(self, tr("match_logo", "Match Logo"), tr("logo_matcher_unavailable", "Logo匹配模块不可用"))

    def _show_clear_params_dialog(self):
        tr = self.language_manager.tr
        from models.channel_model import ChannelListModel as CLM

        channels = self._get_all_channels()
        if not channels:
            return

        selected_indices = self._get_selected_indices()
        target_indices = selected_indices if selected_indices else list(range(len(channels)))

        param_defs = [
            ('tvg_id', CLM.COL_TVG_ID, 'TVG-ID'),
            ('logo', CLM.COL_LOGO, 'Logo'),
            ('group', CLM.COL_GROUP, 'Group'),
            ('catchup', CLM.COL_CATCHUP, 'Catchup'),
            ('catchup_days', CLM.COL_CATCHUP_DAYS, 'Catchup Days'),
            ('catchup_source', CLM.COL_CATCHUP_SOURCE, 'Catchup Source'),
        ]

        available = []
        for key, col, label in param_defs:
            has_value = any(
                channels[i].get(key) for i in target_indices if i < len(channels)
            )
            if has_value:
                available.append((key, col, label))

        if not available:
            return

        dialog = FloatingDialog(self, stay_on_top=True)
        dialog.setWindowTitle(tr("clear_params", "Clear Params"))
        dialog.setMinimumSize(320, 280)
        dialog.setStyleSheet(AppStyles.dialog_style())

        layout = QtWidgets.QVBoxLayout(dialog)

        target_label = QtWidgets.QLabel(
            tr("target_channels", "Target:") + " " +
            (f"{len(selected_indices)} selected" if selected_indices else f"{len(channels)} all")
        )
        layout.addWidget(target_label)

        checks = {}
        for key, col, label in available:
            cb = QtWidgets.QCheckBox(label)
            cb.setChecked(True)
            checks[key] = (cb, col)
            layout.addWidget(cb)

        btn_layout = QtWidgets.QHBoxLayout()
        apply_btn = QtWidgets.QPushButton(tr("apply", "Apply"))
        cancel_btn = QtWidgets.QPushButton(tr("cancel", "Cancel"))
        btn_layout.addStretch()
        btn_layout.addWidget(apply_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        def do_apply():
            count = 0
            for key, (cb, col) in checks.items():
                if not cb.isChecked():
                    continue
                for i in target_indices:
                    if i < len(channels) and channels[i].get(key):
                        self.model.setData(self.model.index(i, col), '')
                        count += 1
            dialog.accept()

        apply_btn.clicked.connect(do_apply)
        cancel_btn.clicked.connect(dialog.reject)

        self._exec_themed_dialog(dialog)

    def _sort_by_group(self):
        from services.channel_classifier import ChannelClassifier
        tr = self.language_manager.tr

        channels = self._get_all_channels()
        if not channels:
            return

        classifier = ChannelClassifier(local_province='通用')
        results = classifier.classify_all(channels, overwrite=False)

        category_order = classifier.get_category_order()

        def sort_key(r):
            cat = r['new_group']
            cat_idx = category_order.index(cat) if cat in category_order else 99
            return (cat_idx, r['sort_key'])

        sorted_results = sorted(results, key=sort_key)
        row_order = [r['index'] for r in sorted_results]

        self.model.sort_by_indices(row_order)

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
        self.edit_name.setFixedHeight(34)
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
        self.edit_group.setFixedHeight(34)
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
        self.edit_url.setFixedHeight(34)
        self.edit_url.installEventFilter(self._home_on_focus_out)
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
        self.edit_tvg_id.setFixedHeight(34)
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
        self.edit_logo.setFixedHeight(34)
        self.edit_logo.installEventFilter(self._home_on_focus_out)
        logo_layout.addWidget(self.edit_logo_label)
        logo_layout.addWidget(self.edit_logo)
        edit_layout.addLayout(logo_layout)

        # 增加一些垂直空间，让内容分布更均匀
        edit_layout.addStretch(1)

        # 保存按钮
        self.btn_save_channel = QtWidgets.QPushButton(tr("save_changes", "Save Changes"))
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

        # 通过代理模型映射到源模型行号
        if hasattr(self, '_filter_proxy'):
            source_row = self._filter_proxy.mapToSource(indexes[0]).row()
        else:
            source_row = indexes[0].row()

        selected_rows = self.channel_list.selectionModel().selectedRows()
        if len(selected_rows) > 1:
            tr = self.language_manager.tr
            self.edit_name.setText(tr("multi_selected", f"已选中 {len(selected_rows)} 个频道"))
            self.edit_name.setReadOnly(True)
            self.edit_group.setReadOnly(True)
            self.edit_url.setReadOnly(True)
            self.edit_tvg_id.setReadOnly(True)
            self.edit_logo.setReadOnly(True)
            return

        self.edit_name.setReadOnly(False)
        self.edit_group.setReadOnly(False)
        self.edit_url.setReadOnly(False)
        self.edit_tvg_id.setReadOnly(False)
        self.edit_logo.setReadOnly(False)

        channel = self.model.get_channel(source_row)
        if channel:
            self.edit_name.setText(channel.get('name', ''))
            self.edit_group.setText(channel.get('group', ''))
            self.edit_url.setText(channel.get('url', ''))
            self.edit_tvg_id.setText(channel.get('tvg_id', ''))
            self.edit_logo.setText(channel.get('logo_url', channel.get('logo', '')))
            self.edit_url.setCursorPosition(0)
            self.edit_logo.setCursorPosition(0)

    def _on_save_channel(self):
        """处理保存频道修改"""
        indexes = self.channel_list.selectionModel().selectedIndexes()
        if not indexes:
            return

        if hasattr(self, '_filter_proxy'):
            source_index = self._filter_proxy.mapToSource(indexes[0])
            row = source_index.row()
        else:
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
        menu.setStyleSheet(AppStyles.common_menu_style())

        from models.channel_model import ChannelListModel as CLM
        if hasattr(self, '_filter_proxy'):
            source_index = self._filter_proxy.mapToSource(index)
            source_row = source_index.row()
        else:
            source_row = index.row()

        url = self.model.data(self.model.index(source_row, CLM.COL_URL))
        name = self.model.data(self.model.index(source_row, CLM.COL_NAME))

        # 添加复制频道名菜单项
        copy_name_action = QtGui.QAction(tr("copy_channel_name", "Copy Channel Name"), self)
        copy_name_action.triggered.connect(lambda: self._copy_channel_name(name))
        menu.addAction(copy_name_action)

        # 添加复制URL菜单项
        copy_url_action = QtGui.QAction(tr("copy_url", "Copy URL"), self)
        copy_url_action.triggered.connect(lambda: self._copy_channel_url(url))
        menu.addAction(copy_url_action)

        # 添加复制TVG-ID菜单项
        tvg_id = self.model.data(self.model.index(source_row, CLM.COL_TVG_ID))
        copy_tvg_id_action = QtGui.QAction(tr("copy_tvg_id", "Copy TVG-ID"), self)
        copy_tvg_id_action.triggered.connect(lambda: self._copy_channel_tvg_id(tvg_id))
        menu.addAction(copy_tvg_id_action)

        # 添加复制分组菜单项
        group = self.model.data(self.model.index(source_row, CLM.COL_GROUP))
        copy_group_action = QtGui.QAction(tr("copy_group", "Copy Group"), self)
        copy_group_action.triggered.connect(lambda: self._copy_channel_group(group))
        menu.addAction(copy_group_action)

        menu.addSeparator()

        select_all_action = QtGui.QAction(tr("select_all", "Select All"), self)
        select_all_action.triggered.connect(self._select_all_channels)
        menu.addAction(select_all_action)

        invert_selection_action = QtGui.QAction(tr("invert_selection", "Invert Selection"), self)
        invert_selection_action.triggered.connect(self._invert_selection)
        menu.addAction(invert_selection_action)

        select_valid_action = QtGui.QAction(tr("select_valid", "Select Valid"), self)
        select_valid_action.triggered.connect(lambda: self._select_by_validity(True))
        menu.addAction(select_valid_action)

        select_invalid_action = QtGui.QAction(tr("select_invalid", "Select Invalid"), self)
        select_invalid_action.triggered.connect(lambda: self._select_by_validity(False))
        menu.addAction(select_invalid_action)

        menu.addSeparator()

        move_to_group_action = QtGui.QAction(tr("move_to_group", "Move to Group..."), self)
        move_to_group_action.triggered.connect(self._move_selected_to_group)
        menu.addAction(move_to_group_action)

        clean_selected_action = QtGui.QAction(tr("clean_selected_names", "Clean Selected Names"), self)
        clean_selected_action.triggered.connect(lambda: self._show_clean_names_dialog())
        menu.addAction(clean_selected_action)

        match_logo_selected_action = QtGui.QAction(tr("match_selected_logo", "Match Selected Logo"), self)
        match_logo_selected_action.triggered.connect(self._match_selected_logo)
        menu.addAction(match_logo_selected_action)

        menu.addSeparator()

        selected_count = len(self.channel_list.selectionModel().selectedRows())
        delete_label = tr("delete_selected_channels", "Delete Selected") + (f" ({selected_count})" if selected_count > 1 else "")
        delete_action = QtGui.QAction(delete_label, self)
        delete_action.triggered.connect(self._delete_selected_channels)
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

    def _move_selected_to_group(self):
        tr = self.language_manager.tr
        indices = self._get_selected_indices()
        if not indices:
            return

        existing_groups = set()
        from models.channel_model import ChannelListModel as CLM
        for row in range(self.model.rowCount()):
            g = self.model.data(self.model.index(row, CLM.COL_GROUP))
            if g:
                existing_groups.add(g)

        group_name, ok = QtWidgets.QInputDialog.getItem(
            self,
            tr("move_to_group", "Move to Group..."),
            tr("target_group", "Target Group:"),
            sorted(existing_groups),
            0,
            True
        )
        if ok and group_name:
            for row in indices:
                self.model.setData(self.model.index(row, CLM.COL_GROUP), group_name)

    def _match_selected_logo(self):
        from services.logo_matcher import LogoMatcher
        tr = self.language_manager.tr
        indices = self._get_selected_indices()
        if not indices:
            return

        matcher = LogoMatcher()
        from models.channel_model import ChannelListModel as CLM
        matched = 0
        for row in indices:
            name = str(self.model.data(self.model.index(row, CLM.COL_NAME)) or '')
            current_logo = str(self.model.data(self.model.index(row, CLM.COL_LOGO)) or '')
            if current_logo:
                continue
            logo = matcher.match(name)
            if logo:
                self.model.setData(self.model.index(row, CLM.COL_LOGO), str(logo))
                matched += 1

        if matched > 0:
            QtWidgets.QMessageBox.information(
                self, tr("match_logo", "Match Logo"),
                f"{matched} channels matched"
            )

    def _delete_selected_channel(self, index):
        """删除选中的频道"""
        tr = self.language_manager.tr
        from utils.error_handler import show_confirm
        title = tr("confirm_delete", "Confirm Delete") or "Confirm Delete"
        message = tr("confirm_delete_message", "Are you sure you want to delete the selected channel?") or "Are you sure you want to delete the selected channel?"
        if show_confirm(title, message, parent=self):
            if hasattr(self, '_filter_proxy'):
                source_row = self._filter_proxy.mapToSource(index).row()
            else:
                source_row = index.row()
            self.model.remove_channel(source_row)

    def _delete_selected_channels(self):
        """删除选中的频道（支持多选批量删除）"""
        tr = self.language_manager.tr
        indices = self._get_selected_indices()
        if not indices:
            return
        from utils.error_handler import show_confirm
        title = tr("confirm_delete", "Confirm Delete")
        message = tr("confirm_delete_selected_message", "确定删除选中的{n}个频道？").format(n=len(indices))
        if show_confirm(title, message, parent=self):
            for row in sorted(indices, reverse=True):
                self.model.remove_channel(row)

    def _select_all_channels(self):
        """全选频道"""
        self.channel_list.selectAll()

    def _invert_selection(self):
        """反选频道"""
        model = self._filter_proxy if hasattr(self, '_filter_proxy') else self.model
        selection_model = self.channel_list.selectionModel()
        for row in range(model.rowCount()):
            index = model.index(row, 0)
            if selection_model.isSelected(index):
                selection_model.select(index, QtCore.QItemSelectionModel.SelectionFlag.Deselect | QtCore.QItemSelectionModel.SelectionFlag.Rows)
            else:
                selection_model.select(index, QtCore.QItemSelectionModel.SelectionFlag.Select | QtCore.QItemSelectionModel.SelectionFlag.Rows)

    def _select_by_validity(self, select_valid: bool):
        """按有效性选择频道"""
        from models.channel_model import ChannelListModel as CLM
        model = self._filter_proxy if hasattr(self, '_filter_proxy') else self.model
        selection_model = self.channel_list.selectionModel()
        selection_model.clearSelection()
        source_model = self.model
        for row in range(model.rowCount()):
            if hasattr(self, '_filter_proxy'):
                source_row = self._filter_proxy.mapToSource(model.index(row, 0)).row()
            else:
                source_row = row
            channel = source_model.get_channel(source_row)
            if channel:
                is_valid = channel.get('valid', False)
                if is_valid == select_valid:
                    selection_model.select(model.index(row, 0), QtCore.QItemSelectionModel.SelectionFlag.Select | QtCore.QItemSelectionModel.SelectionFlag.Rows)

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
        if hasattr(self, '_filter_proxy'):
            source_row = self._filter_proxy.mapToSource(index).row()
        else:
            source_row = index.row()
        channel = self.model.get_channel(source_row)
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

        self._connect_input_signals()
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
        """更新扫描/检测进度（使用进度条管理器）"""
        try:
            if hasattr(self.scanner, 'stats'):
                stats = self.scanner.stats
                total = stats.get('total', 0)
                valid = stats.get('valid', 0)
                invalid = stats.get('invalid', 0)

                current = valid + invalid
                is_validating = getattr(self.scanner, 'is_validating', False)
                tr = self.language_manager.tr

                if total > 0:
                    if is_validating:
                        progress_text = f"{tr('validate_progress', '检测进度')}: {current}/{total}"
                    else:
                        progress_text = f"{tr('scan_progress', '扫描进度')}: {current}/{total}"

                    self.progress_manager.update_progress_from_stats(
                        current,
                        total,
                        progress_text
                    )

                    if current >= total and total > 0:
                        if not getattr(self, '_scan_progress_completed', False):
                            self._scan_progress_completed = True
                            if is_validating:
                                self.progress_manager.complete_progress(tr('validate_completed', '检测完成'))
                            else:
                                self.progress_manager.complete_progress(tr('scan_completed', '扫描完成'))
                                self._reset_scan_buttons()

        except AttributeError as e:
            log_scan_warning(f"进度更新失败: {e}")
        except Exception as e:
            log_scan_warning(f"进度更新时发生意外错误: {e}")

    def _load_config(self):
        """加载保存的配置到UI"""
        try:
            settings = self.config.load_network_settings()

            # 加载URL历史记录到下拉列表
            url_history = self.config.load_url_history()
            self.ip_range_input.addItems(url_history)

            if settings['url']:
                self.ip_range_input.setCurrentText(settings['url'])

            if settings['user_agent']:
                self.user_agent_input.setText(settings['user_agent'])

            if settings['referer']:
                self.referer_input.setText(settings['referer'])

            if hasattr(self, 'timeout_input'):
                self.timeout_input.setText(str(settings.get('timeout', 10)))
            if hasattr(self, 'threads_input'):
                self.threads_input.setText(str(settings.get('threads', 4)))

        except Exception as e:
            log_config_error(f"加载配置失败: {e}")

        self._reset_cursor_to_home()

    def _reset_cursor_to_home(self):
        """将所有URL输入框的光标移到开头，使长文本从起始位置显示"""
        for widget in (self.user_agent_input, self.referer_input,
                       getattr(self, 'edit_url', None), getattr(self, 'edit_logo', None)):
            if widget and isinstance(widget, QtWidgets.QLineEdit):
                widget.setCursorPosition(0)
        ip_line_edit = self.ip_range_input.lineEdit()
        if ip_line_edit:
            ip_line_edit.setCursorPosition(0)

    def _register_config_observers(self):
        register_config_observer("Network.*", self._on_network_config_changed)
        register_config_observer("ScanRetry.*", self._on_scan_retry_config_changed)
        register_config_observer("Language.current_language", self._on_language_config_changed)

    def _on_network_config_changed(self, section, key, old_value, new_value):
        """处理网络配置变更"""
        log_config_info(f"网络配置变更: {section}.{key} = {old_value} -> {new_value}")

        if key == 'url':
            self.ip_range_input.setCurrentText(new_value)
            self.ip_range_input.lineEdit().setCursorPosition(0)
        elif key == 'user_agent':
            self.user_agent_input.setText(new_value)
            self.user_agent_input.setCursorPosition(0)
        elif key == 'referer':
            self.referer_input.setText(new_value)
            self.referer_input.setCursorPosition(0)
        elif key == 'timeout' and hasattr(self, 'timeout_input'):
            try:
                self.timeout_input.setText(str(new_value))
            except (ValueError, TypeError):
                pass
        elif key == 'threads' and hasattr(self, 'threads_input'):
            try:
                self.threads_input.setText(str(new_value))
            except (ValueError, TypeError):
                pass

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

        # 搜索过滤
        if hasattr(self, 'search_input'):
            self.search_input.textChanged.connect(self._on_search_filter_changed)

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

    def _exec_themed_dialog(self, dialog):
        """执行对话框并注册/注销ThemeManager"""
        from ..theme_manager import get_theme_manager
        tm = None
        try:
            tm = get_theme_manager()
            tm.register_window(dialog)
        except Exception:
            tm = None
        dialog.exec()
        if tm:
            try:
                tm.unregister_window(dialog)
            except Exception:
                pass

    def _update_empty_hint(self):
        """更新空列表提示可见性"""
        if hasattr(self, '_empty_stack'):
            if self.model.rowCount() == 0:
                self._empty_stack.setCurrentIndex(1)
            else:
                self._empty_stack.setCurrentIndex(0)

    def _setup_shortcuts(self):
        """设置快捷键"""
        from PySide6.QtGui import QKeySequence
        from PySide6.QtGui import QShortcut
        QShortcut(QKeySequence("Ctrl+S"), self, self._on_save_m3u_clicked)
        QShortcut(QKeySequence("Ctrl+F"), self, self._focus_search)
        QShortcut(QKeySequence("Ctrl+A"), self, self._select_all_channels)
        QShortcut(QKeySequence("Delete"), self, self._delete_selected_channels)

    def _focus_search(self):
        """聚焦搜索框"""
        if hasattr(self, 'search_input'):
            self.search_input.setFocus()
            self.search_input.selectAll()

    def _on_search_filter_changed(self, text):
        """搜索过滤：按频道名/URL/分组实时过滤"""
        if hasattr(self, '_filter_proxy'):
            self._filter_proxy.setFilterFixedString(text.strip())

    def _stop_scan_async(self):
        """安全停止扫描：先设标志让线程退出，再延迟做重量级清理"""
        self._is_stopping = True
        self._reset_scan_buttons()
        self._scan_progress_completed = True

        self.scanner.stop_event.set()
        ValidatorClass = self._get_validator_class()
        ValidatorClass.set_terminating()

        self.scanner.scan_state_manager.update_scan_state(self.scanner.scan_id, {
            'is_scanning': False
        })

        QtCore.QTimer.singleShot(500, self._finalize_stop_scan)

    def _finalize_stop_scan(self):
        """延迟执行重量级停止清理（在主线程中安全执行）"""
        if not hasattr(self, 'scanner') or self.scanner is None:
            return
        try:
            ValidatorClass = self._get_validator_class()
            ValidatorClass.terminate_all()

            if hasattr(self.scanner, '_flush_pending_channels'):
                self.scanner._flush_pending_channels()

            self.scanner.stop_event.set()

            import queue
            for q_attr in ('scan_queue', 'validation_queue'):
                q = getattr(self.scanner, q_attr, None)
                if q:
                    while not q.empty():
                        try:
                            q.get_nowait()
                        except queue.Empty:
                            break

            still_running = any(w.is_alive() for w in self.scanner.workers)
            if still_running:
                QtCore.QTimer.singleShot(300, self._finalize_stop_scan)
                return

            self.scanner.workers = []

            FfprobeStreamValidator.destroy_all_handles()

            if hasattr(self.scanner, '_mapping_executor') and self.scanner._mapping_executor:
                try:
                    self.scanner._mapping_executor.shutdown(wait=False)
                except Exception:
                    pass
                self.scanner._mapping_executor = None

            self.progress_manager.complete_progress(
                self.language_manager.tr('scan_stopped', '扫描已停止')
            )
            self.stats_label.setText(self.language_manager.tr('scan_stopped', '扫描已停止'))
            self._set_browse_model()
        except Exception as e:
            log_ui_error(f"停止扫描清理失败: {e}")
        finally:
            try:
                ValidatorClass = self._get_validator_class()
                ValidatorClass.reset_terminating()
            except Exception:
                pass

    def _on_scan_clicked(self):
        """处理扫描按钮点击事件"""
        if not hasattr(self, 'scanner') or self.scanner is None:
            log_ui_error("扫描器未初始化，无法执行扫描")
            return
        if self.scanner.is_scanning():
            self._is_stopping = True
            self._stop_scan_async()
        else:
            url = self.ip_range_input.currentText()
            if not url.strip():
                log_ui_warning("请输入扫描地址")
                self._show_input_warning(self.ip_range_input, self.language_manager.tr("please_input_url", "请输入扫描地址"))
                return

            from utils.thread_safety import invoke_on_thread
            invoke_on_thread(self, lambda: self._start_scan_delayed(url, clear_list=True))

    def _on_append_scan_clicked(self):
        """处理追加扫描按钮点击事件"""
        if not hasattr(self, 'scanner') or self.scanner is None:
            log_ui_error("扫描器未初始化，无法执行扫描")
            return
        if self.scanner.is_scanning():
            self._is_stopping = True
            self._stop_scan_async()
        else:
            url = self.ip_range_input.currentText()
            if not url.strip():
                log_ui_warning("请输入扫描地址")
                self._show_input_warning(self.ip_range_input, self.language_manager.tr("please_input_url", "请输入扫描地址"))
                return

            from utils.thread_safety import invoke_on_thread
            invoke_on_thread(self, lambda: self._start_scan_delayed(url, clear_list=False))

    def _start_scan_delayed(self, url, clear_list=True):
        """延迟启动扫描，避免UI阻塞"""
        if not hasattr(self, 'scanner') or self.scanner is None:
            log_ui_error("扫描器未初始化，无法启动扫描")
            return

        self._is_stopping = False
        self._scan_progress_completed = False
        self._add_url_to_history(url)

        if clear_list:
            self.model.clear()
            log_scan_info("开始完整扫描，清空现有列表")
        else:
            log_scan_info("开始追加扫描，保留现有列表")

        # 从配置统一读取扫描参数
        scan_timeout, scan_threads = self._get_scan_params()

        self.logger.debug(f"使用{scan_threads}线程，{scan_timeout}秒超时")

        skip_urls = None
        if not clear_list:
            skip_urls = {ch.get('url', '') for ch in self.model.channels if ch.get('url')}

        user_agent = self.user_agent_input.text() or None
        referer = self.referer_input.text() or None

        self.scanner.start_scan(url, scan_threads, scan_timeout, user_agent=user_agent, referer=referer, skip_urls=skip_urls)

        self._set_scan_model()

        self.progress_manager.start_progress(
            str(self.language_manager.tr('scan', '扫描')),
            max_value=100
        )

        self._set_buttons_during_scan(True)

        if clear_list:
            self._set_scan_button_text('stop_scan', '停止扫描')
        else:
            self._set_append_scan_button_text('stop_scan', '停止扫描')

    def _set_scan_model(self):
        """扫描期间切换到源模型，断开代理模型避免竞态崩溃"""
        if hasattr(self, '_filter_proxy') and self._filter_proxy:
            self.channel_list.setModel(self.model)

    def _set_browse_model(self):
        """扫描结束后恢复代理模型，支持搜索过滤和排序"""
        if hasattr(self, '_filter_proxy') and self._filter_proxy:
            self._filter_proxy.setSourceModel(self.model)
            self.channel_list.setModel(self._filter_proxy)

    def _set_buttons_during_scan(self, is_scanning: bool):
        """扫描/验证期间禁用或恢复冲突按钮"""
        disabled = is_scanning
        self.btn_validate.setEnabled(not disabled)
        self.btn_generate.setEnabled(not disabled)
        self.btn_open_list.setEnabled(not disabled)
        self.btn_save_m3u.setEnabled(not disabled)
        self.btn_save_txt.setEnabled(not disabled)
        self.btn_batch_ops.setEnabled(not disabled)
        self.enable_retry_checkbox.setEnabled(not disabled)
        self.enable_mapping_checkbox.setEnabled(not disabled)

    def _reset_scan_buttons(self):
        """统一重置扫描按钮文本和状态"""
        self._set_scan_button_text('full_scan', '完整扫描')
        self._set_append_scan_button_text('append_scan', '追加扫描')
        self._set_buttons_during_scan(False)

    def _set_button_text(self, button, translation_key, default_text):
        """通用按钮文本设置函数"""
        if hasattr(self, 'language_manager') and self.language_manager:
            button.setText(self.language_manager.tr(translation_key, default_text))
        else:
            button.setText(default_text)

    def _show_input_warning(self, input_widget, message):
        """在输入框旁显示临时警告提示"""
        err_color = AppStyles._get_colors().get('error', '#e74c3c')
        original_style = input_widget.styleSheet()
        input_widget.setStyleSheet(original_style + f"; border: 2px solid {err_color};")
        self.stats_label.setText(message)
        self.stats_label.setStyleSheet(f"color: {err_color}; font-weight: bold;")
        QtCore.QTimer.singleShot(2000, lambda: (
            input_widget.setStyleSheet(original_style),
            self.stats_label.setStyleSheet(AppStyles.common_label_style())
        ))

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
            user_agent = self.user_agent_input.text() or None
            referer = self.referer_input.text() or None
            validate_timeout, validate_threads = self._get_scan_params()
            self.scanner.start_validation(
                self.model,
                validate_threads,
                validate_timeout,
                user_agent,
                referer
            )
            self._set_scan_model()
            self.btn_validate.setText(self.language_manager.tr("stop_validate", "Stop Validate"))
            self.btn_hide_invalid.setEnabled(True)
            self.btn_hide_invalid.setStyleSheet(
                AppStyles.button_style(active=True)
            )
            self.progress_manager.start_progress(
                str(self.language_manager.tr('validate', '检测')),
                max_value=self.model.rowCount()
            )
            self.stats_label.setText(
                f"{self.language_manager.tr('validate', '检测')}: "
                f"{self.language_manager.tr('validate_nth', '第{n}次检测').format(n=1)} | "
                f"0/{self.model.rowCount()}"
            )
        else:
            self._is_stopping = True
            self._is_validation_retrying = False
            self._validation_retry_urls = None
            self.btn_validate.setText(self.language_manager.tr("validate_button", "Validate"))
            self.progress_manager.hide_progress()
            self.stats_label.setText(self.language_manager.tr('validate_stopped', '检测已停止'))
            self.scanner.stop_event.set()
            ValidatorClass = self._get_validator_class()
            ValidatorClass.set_terminating()
            self.scanner.is_validating = False
            self.scanner.scan_state_manager.update_scan_state(self.scanner.scan_id, {
                'is_validating': False
            })
            QtCore.QTimer.singleShot(500, self._finalize_stop_validation)

    def _finalize_stop_validation(self):
        """延迟执行停止验证清理"""
        if not hasattr(self, 'scanner') or self.scanner is None:
            return
        try:
            ValidatorClass = self._get_validator_class()
            ValidatorClass.terminate_all()
            self.scanner.stop_event.set()

            import queue
            q = getattr(self.scanner, 'validation_queue', None)
            if q:
                while not q.empty():
                    try:
                        q.get_nowait()
                    except queue.Empty:
                        break
            sq = getattr(self.scanner, 'scan_queue', None)
            if sq:
                while not sq.empty():
                    try:
                        sq.get_nowait()
                    except queue.Empty:
                        break

            still_running = any(w.is_alive() for w in self.scanner.workers)
            if still_running:
                QtCore.QTimer.singleShot(300, self._finalize_stop_validation)
                return

            self.scanner.workers = []
            ValidatorClass.destroy_all_handles()
            self._set_browse_model()
        except Exception as e:
            log_ui_error(f"停止验证清理失败: {e}")
        finally:
            try:
                ValidatorClass = self._get_validator_class()
                ValidatorClass.reset_terminating()
            except Exception:
                pass

    def _on_channel_validated(self, index, valid, latency, resolution):
        """处理频道验证结果"""
        if not (0 <= index < self.model.rowCount()):
            return
        channel_info = {
            'valid': valid,
            'latency': latency,
            'resolution': resolution,
            'status': self.language_manager.tr('valid', '有效') if valid else self.language_manager.tr('invalid', '无效')
        }

        self.model.update_channel(index, channel_info)

    def _on_validation_completed(self):
        """处理验证完成事件"""
        self._set_browse_model()
        try:
            self.progress_manager.complete_progress(self.language_manager.tr('validate_completed', '检测完成'))
        except Exception:
            pass
        # 智能重试：对检测为无效的频道进行重试验证
        if self.enable_retry_checkbox.isChecked():
            invalid_urls = []
            for ch in self.model.channels:
                if ch.get('valid') is False and ch.get('url'):
                    invalid_urls.append(ch.get('url'))
            if invalid_urls:
                self.logger.info(f"检测有效性完成，{len(invalid_urls)}个无效频道，启动智能重试...")
                self._validation_retry_urls = invalid_urls
                self._validation_retry_count = 0
                self._is_validation_retrying = True
                QtCore.QTimer.singleShot(100, self._start_validation_retry)
            else:
                self.logger.info("检测有效性完成，所有频道均有效")
                self.stats_label.setText(self.language_manager.tr("all_channels_valid", "All channels are valid"))
                try:
                    self.btn_validate.setText(self.language_manager.tr("validate_button", "Validate"))
                except Exception:
                    pass
        else:
            valid_count = sum(1 for ch in self.model.channels if ch.get('valid') is True)
            total = len(self.model.channels)
            tr = self.language_manager.tr
            self.stats_label.setText(
                f"{tr('validate_completed', '检测完成')} | "
                f"{tr('valid', '有效')}: {valid_count}/{total}"
            )
            try:
                self.btn_validate.setText(self.language_manager.tr("validate_button", "Validate"))
            except Exception:
                pass

    def _start_validation_retry(self):
        """对无效频道进行智能重试验证"""
        if not hasattr(self, '_validation_retry_urls') or not self._validation_retry_urls:
            return

        if getattr(self, '_is_stopping', False):
            self.logger.info("检测重试被用户停止，不再继续重试")
            self._is_validation_retrying = False
            self._validation_retry_urls = None
            return

        max_retries = 3
        if hasattr(self, '_validation_retry_count') and self._validation_retry_count >= max_retries:
            self.logger.info(f"智能重试已达最大次数({max_retries}次)，停止重试")
            self._is_validation_retrying = False
            self.stats_label.setText(
                self.language_manager.tr("retry_completed", "Smart retry completed")
            )
            return

        retry_timeout, _ = self._get_scan_params(default_timeout=10, timeout_multiplier=2)

        retry_threads = 4
        self._validation_retry_count = (getattr(self, '_validation_retry_count', 0) or 0) + 1
        self._is_validation_retrying = True

        self.logger.info(
            f"智能重试验证(第{self._validation_retry_count}次): "
            f"{len(self._validation_retry_urls)}个URL, 超时={retry_timeout}秒"
        )

        tr = self.language_manager.tr
        task_text = tr('validate', '检测')
        task_type = tr('validate_nth', '第{n}次检测').format(n=self._validation_retry_count + 1)
        self.stats_label.setText(
            f"{task_text}: {task_type} | 0/{len(self._validation_retry_urls)}"
        )

        self.progress_manager.start_progress(
            f"{tr('smart_retry', '智能重试')} #{self._validation_retry_count}",
            max_value=len(self._validation_retry_urls)
        )

        self.btn_validate.setText(tr("stop_validate", "Stop Validate"))

        self.scanner.start_scan_from_urls(
            self._validation_retry_urls,
            retry_threads,
            retry_timeout,
            user_agent=self.user_agent_input.text() or None,
            referer=self.referer_input.text() or None,
            is_validation_retry=True
        )
        self._set_scan_model()

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
        url = self.ip_range_input.currentText()
        if not url.strip():
            self.logger.warning("请输入生成地址")
            self._show_input_warning(self.ip_range_input, self.language_manager.tr("please_input_url", "请输入生成地址"))
            return

        self._add_url_to_history(url)

        self.model.clear()
        self._invalidate_channels_cache()

        url_parser = URLRangeParser()
        url_generator = url_parser.parse_url(url)

        batch_channels = []
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
                batch_channels.append(channel)
                count += 1

        if hasattr(self.model, 'add_channels'):
            self.model.add_channels(batch_channels)
        else:
            for ch in batch_channels:
                self.model.add_channel(ch)

        self.logger.info(f"已生成 {count} 个频道")

    def _save_list_as(self, fmt: str):
        tr = self.language_manager.tr
        if not self.model or self.model.rowCount() == 0:
            self.logger.warning(str(tr("no_channels_to_save", "No channels to save")))
            return

        selected_indices = self._get_selected_indices()
        save_selected = False
        if selected_indices:
            reply = QtWidgets.QMessageBox.question(
                self,
                tr("save_scope", "保存范围"),
                tr("save_selected_or_all", "是否仅保存选中的{n}个频道？").format(n=len(selected_indices)),
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No | QtWidgets.QMessageBox.StandardButton.Cancel,
            )
            if reply == QtWidgets.QMessageBox.StandardButton.Cancel:
                return
            save_selected = (reply == QtWidgets.QMessageBox.StandardButton.Yes)

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
            if save_selected:
                channels_to_save = [self.model.channels[i] for i in selected_indices if i < len(self.model.channels)]
                if fmt == 'm3u':
                    content = self.model._channels_to_m3u(channels_to_save) if hasattr(self.model, '_channels_to_m3u') else self.model.to_m3u()
                else:
                    content = self.model._channels_to_txt(channels_to_save) if hasattr(self.model, '_channels_to_txt') else self.model.to_txt()
            else:
                if fmt == 'm3u':
                    content = self.model.to_m3u()
                else:
                    content = self.model.to_txt()

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)

            count = len(selected_indices) if save_selected else self.model.rowCount()
            self.logger.info(f"已保存 {count} 个频道到 {file_path}")
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
                timeout_val = 5
                threads_val = 4
                if hasattr(self, 'timeout_input'):
                    timeout_val = self.timeout_input.text()
                if hasattr(self, 'threads_input'):
                    threads_val = self.threads_input.text()
                self.config.save_network_settings(
                    url=self.ip_range_input.currentText(),
                    timeout=timeout_val,
                    threads=threads_val,
                    user_agent=self.user_agent_input.text(),
                    referer=self.referer_input.text()
                )
                self.logger.info("配置已保存")
        except Exception as e:
            self.logger.error(f"保存配置失败: {e}")

    @QtCore.Slot(dict)
    def _on_channel_found(self, channel_info):
        """处理发现有效频道事件"""
        self._invalidate_channels_cache()
        is_valid = channel_info.get('valid') is True
        channel_info['status'] = self.language_manager.tr('valid', '有效') if is_valid else self.language_manager.tr('invalid', '无效')
        self.model.add_channel(channel_info)

    @QtCore.Slot()
    def _on_scan_completed(self):
        """处理扫描完成事件"""
        if not hasattr(self, 'scanner') or self.scanner is None:
            return
        was_stopping = getattr(self, '_is_stopping', False)

        self._set_browse_model()

        if hasattr(self, '_validation_retry_urls') and self._validation_retry_urls:
            self._on_validation_retry_completed()
            return

        self._is_stopping = False

        is_retry = self.scan_state_manager.is_retry_scan(self.retry_id)

        try:
            self.progress_manager.complete_progress(self.language_manager.tr('scan_completed', '扫描完成'))
        except Exception:
            pass

        try:
            self._reset_scan_buttons()
        except Exception:
            pass

        try:
            self.btn_validate.setText(self.language_manager.tr("validate_button", "Validate"))
        except Exception:
            pass

        if was_stopping:
            return

        if not is_retry:
            if self.enable_retry_checkbox.isChecked():
                QtCore.QTimer.singleShot(100, self._handle_retry_scan)
        else:
            self._handle_retry_scan_completed()

    def _on_validation_retry_completed(self):
        """处理验证重试扫描完成事件"""
        try:
            self.progress_manager.complete_progress(self.language_manager.tr('validate_completed', '检测完成'))
        except Exception:
            pass
        try:
            self._reset_scan_buttons()
        except Exception:
            pass

        if getattr(self, '_is_stopping', False):
            self.logger.info("检测重试被用户停止")
            self._is_validation_retrying = False
            self._validation_retry_urls = None
            self._is_stopping = False
            return

        found_urls = {ch.get('url', '') for ch in self.scanner.found_channels} if hasattr(self, 'scanner') and self.scanner and hasattr(self.scanner, 'found_channels') else set()

        url_to_index = {}
        for i, ch in enumerate(self.model.channels):
            url = ch.get('url', '')
            if url and ch.get('valid') is False:
                url_to_index.setdefault(url, i)

        newly_valid = 0
        remaining_invalid = []
        for url in getattr(self, '_validation_retry_urls', []):
            if url in found_urls and url in url_to_index:
                idx = url_to_index[url]
                self.model.update_channel(idx, {'valid': True, 'status': self.language_manager.tr('valid', '有效')})
                newly_valid += 1
            else:
                remaining_invalid.append(url)
        
        self._validation_retry_urls = remaining_invalid
        
        if newly_valid > 0:
            self.logger.info(f"验证重试发现 {newly_valid} 个新有效频道")
        
        max_retries = 3
        current_count = getattr(self, '_validation_retry_count', 0) or 0
        
        if remaining_invalid and current_count < max_retries:
            if getattr(self, '_is_stopping', False):
                self.logger.info("检测重试被用户停止，不启动下一轮")
                self._is_validation_retrying = False
                return
            self.logger.info(f"仍有 {len(remaining_invalid)} 个无效频道，继续智能重试(第{current_count + 1}/{max_retries}次)...")
            QtCore.QTimer.singleShot(500, self._start_validation_retry)
        else:
            self._is_validation_retrying = False
            if remaining_invalid:
                self.logger.info(f"智能重试完成({max_retries}次)，仍剩{len(remaining_invalid)}个无效频道")
            else:
                self.logger.info("智能重试完成，所有无效频道已全部恢复有效")
            self.stats_label.setText(
                self.language_manager.tr("retry_completed", "Smart retry completed")
            )
            self._validation_retry_urls = None

    @QtCore.Slot(dict)
    def _update_stats_display(self, stats_data):
        """更新统计信息显示，包括扫描次数"""
        try:
            if not hasattr(self, 'stats_label') or not self.stats_label:
                self.logger.error("状态栏统计标签不存在")
                return

            stats = stats_data.get('stats', stats_data)
            is_validation = stats_data.get('is_validation', False)
            elapsed = time.strftime("%H:%M:%S", time.gmtime(stats.get('elapsed', 0)))

            is_validation_retrying = getattr(self, '_is_validation_retrying', False)

            retry_count = self.scan_state_manager.get_retry_count(self.retry_id)
            is_retry_scan = self.scan_state_manager.is_retry_scan(self.retry_id)

            tr = self.language_manager.tr

            if is_validation:
                task_text = tr('validate', '检测')
                if is_validation_retrying:
                    validation_retry_count = getattr(self, '_validation_retry_count', 0) or 0
                    task_type = tr('validate_nth', '第{n}次检测').format(n=validation_retry_count + 1)
                elif is_retry_scan:
                    task_type = tr('retry_nth', '第{n}次重试').format(n=retry_count)
                else:
                    task_type = tr('validate_nth', '第{n}次检测').format(n=1)
            else:
                task_text = tr('scan', '扫描')
                if is_retry_scan:
                    task_type = tr('retry_nth', '第{n}次重试').format(n=retry_count)
                elif retry_count > 0:
                    task_type = tr('scan_nth', '第{n}次扫描').format(n=retry_count + 1)
                else:
                    task_type = tr('scan_nth', '第{n}次扫描').format(n=1)

            total_text = tr('scan_total', '本次总数')
            valid_text = tr('valid', '有效')
            invalid_text = tr('invalid', '无效')
            time_text = tr('time_elapsed', '耗时')

            stats_text = (
                f"{task_text}: {task_type} | "
                f"{total_text}: {stats.get('total', 0)} | "
                f"{valid_text}: {stats.get('valid', 0)} | "
                f"{invalid_text}: {stats.get('invalid', 0)} | "
                f"{time_text}: {elapsed}"
            )
            self.stats_label.setText(stats_text)
        except Exception as e:
            self.logger.error(f"更新统计信息显示失败: {e}", exc_info=True)

    def closeEvent(self, event):
        if hasattr(self, 'scanner') and self.scanner:
            if self.scanner.is_scanning() or getattr(self.scanner, 'is_validating', False):
                tr = self.language_manager.tr
                reply = QtWidgets.QMessageBox.question(
                    self,
                    tr("confirm_close", "确认关闭"),
                    tr("confirm_close_scanning", "扫描/验证正在进行中，关闭将丢失结果，是否继续？"),
                    QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
                    QtWidgets.QMessageBox.StandardButton.No
                )
                if reply == QtWidgets.QMessageBox.StandardButton.No:
                    event.ignore()
                    return
                self.scanner.stop_event.set()
                ValidatorClass = self._get_validator_class()
                ValidatorClass.set_terminating()
                if getattr(self.scanner, 'is_validating', False):
                    self.scanner.stop_validation()
        if hasattr(self, 'application') and self.application:
            if hasattr(self.application, '_scan_dialog'):
                self.application._scan_dialog = None
        try:
            from ui.theme_manager import get_theme_manager
            get_theme_manager().unregister_window(self)
        except Exception:
            pass
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
                        self.btn_save_m3u, self.btn_save_txt, self.btn_save_channel,
                        self.btn_batch_ops]:
                if hasattr(btn, 'setStyleSheet'):
                    btn.setStyleSheet(AppStyles.common_button_style())
            if hasattr(self, 'btn_batch_ops') and self.btn_batch_ops.menu():
                self.btn_batch_ops.menu().setStyleSheet(AppStyles.common_menu_style())
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
            if hasattr(self, 'ip_range_input'):
                self.ip_range_input.setStyleSheet(AppStyles.url_combo_style())
            if hasattr(self, 'address_example_label'):
                self.address_example_label.setStyleSheet(AppStyles.hint_label_style())
            if hasattr(self, 'user_agent_label'):
                self.user_agent_label.setStyleSheet(AppStyles.small_label_style())
            if hasattr(self, 'referer_label'):
                self.referer_label.setStyleSheet(AppStyles.small_label_style())
        except Exception as e:
            if hasattr(self, 'logger'):
                self.logger.error(f"重新应用扫描窗口样式失败: {e}")

    def update_ui_texts(self):
        """语言切换时更新UI文本"""
        try:
            tr = self.language_manager.tr
            if hasattr(self, 'left_title'):
                self.left_title.setText(tr('scan_settings_title', 'Scan Settings'))
            if hasattr(self, 'list_title'):
                self.list_title.setText(tr('channel_list_title', 'Channel List'))
            if hasattr(self, 'right_title'):
                self.right_title.setText(tr('channel_edit_title', 'Channel Edit'))
            if hasattr(self, 'close_btn'):
                self.close_btn.setText(tr('close_button', 'Close'))
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
                self.btn_save_channel.setText(tr("save_changes", "Save Changes"))
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
        if getattr(self, '_is_stopping', False):
            self.logger.info("重试扫描被用户停止，不再继续")
            return
        self.logger.debug("=== _handle_retry_scan 方法开始 ===")

        # 使用重试扫描状态上下文管理器
        with RetryScanStateContext(self.retry_id, self):
            self._handle_retry_scan_internal()

    def _handle_retry_scan_internal(self):
        """内部重试扫描处理方法"""
        if getattr(self, '_is_stopping', False):
            self.logger.info("重试扫描被用户停止，不再继续")
            return
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

                # 每处理一批后让出CPU，避免UI卡顿
                if i + batch_size < total_count:
                    time.sleep(0.001)

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
        return sum(1 for ch in self.model.channels if ch.get('valid', False))

    def _start_retry_scan(self):
        """启动重试扫描 - 第二阶段深度扫描"""
        if getattr(self, '_is_stopping', False):
            self.logger.info("重试扫描被用户停止，不启动新轮次")
            return
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

        # 智能重试使用更长的超时时间，提高慢速频道的检出率
        retry_timeout, _ = self._get_scan_params(default_timeout=10, timeout_multiplier=2)

        self.logger.info(f"智能重试扫描: {len(retry_urls)} 个URL, 超时={retry_timeout}秒")

        # 使用4个扫描线程（与主扫描一致）
        retry_threads = 4

        # 启动深度重试扫描
        self.progress_manager.start_progress(
            str(self.language_manager.tr('retry_scan', '重试扫描')),
            max_value=len(retry_urls)
        )
        self.scanner.start_scan_from_urls(
            retry_urls,
            retry_threads,
            retry_timeout,
            user_agent=self.user_agent_input.text() or None,
            referer=self.referer_input.text() or None
        )
        self._set_scan_model()
        self._set_scan_button_text('stop_scan', '停止扫描')
        self._set_append_scan_button_text('stop_scan', '停止扫描')

    def _handle_retry_scan_completed(self):
        if getattr(self, '_is_stopping', False):
            self.logger.info("重试扫描被用户停止，不再继续")
            self.scan_state_manager.clear_failed_channels(self.retry_id)
            return
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