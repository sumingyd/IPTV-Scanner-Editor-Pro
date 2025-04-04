# ================= 标准库导入 =================
import os
import asyncio
import datetime
import platform
import sys
import json
import re
from pathlib import Path
from typing import Optional, List, Dict, Any
import aiohttp
from copy import deepcopy

# ================= 第三方库导入 =================
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt, QModelIndex, pyqtSlot
from PyQt6.QtGui import QAction, QIcon, QKeySequence, QCloseEvent
from PyQt6.QtWidgets import QFileDialog, QMessageBox
import qasync

# ================= 本地模块导入 =================
from async_utils import AsyncWorker
from epg_manager import EPGManager
from player import VLCPlayer
from playlist_io import PlaylistConverter, PlaylistHandler, PlaylistParser
from scanner import StreamScanner
from utils import ConfigHandler, setup_logger
from styles import AppStyles
from validator import StreamValidator

logger = setup_logger('Main') # 主程序日志器

# 频道列表模型
class ChannelListModel(QtCore.QAbstractTableModel):

    # 初始化频道列表
    def __init__(self, data: Optional[List[Dict]] = None):
        super().__init__()
        self.channels = data if data is not None else []
        self.headers = ["频道名称", "分辨率", "URL", "分组", "状态", "延迟(ms)"]

    # 数据处理
    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None
            
        if role == Qt.ItemDataRole.DisplayRole:
            chan = self.channels[index.row()]
            if index.column() == 0:
                return chan.get('name', '未命名频道')
            elif index.column() == 1:
                return f"{chan.get('width', 0)}x{chan.get('height', 0)}"
            elif index.column() == 2:
                return chan.get('url', '无地址')
            elif index.column() == 3:
                return chan.get('group', '未分类')
            elif index.column() == 4:  # 状态列
                if 'valid' in chan:
                    if chan.get('validating', False):
                        return "⏳"  # 正在检测
                    return "✓" if chan['valid'] else "✗"
                return ""
            elif index.column() == 5:  # 延迟列
                if 'latency' in chan:
                    return f"{chan['latency']*1000:.0f}ms" if chan.get('valid') else ""
                return ""
        elif role == Qt.ItemDataRole.UserRole:
            return self.channels[index.row()]
        elif role == Qt.ItemDataRole.ForegroundRole:  # 设置文本颜色
            if index.column() == 4:  # 状态列
                if 'valid' in self.channels[index.row()]:
                    return QtGui.QColor('#4CAF50') if self.channels[index.row()]['valid'] else QtGui.QColor('#F44336')
        elif role == Qt.ItemDataRole.TextAlignmentRole:  # 设置对齐方式
            if index.column() in (4, 5):  # 状态和延迟列居中
                return Qt.AlignmentFlag.AlignCenter
        return None

    # 行数
    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self.channels)

    # 列数
    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self.headers)

    # 表头数据
    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.headers[section]
        return None

# 主窗口
class MainWindow(QtWidgets.QMainWindow):
    # 定义信号（必须在类的作用域内定义）
    epg_progress_updated = QtCore.pyqtSignal(str)  # 用于更新进度提示

    # 初始化
    def __init__(self):
        super().__init__()
        self.validation_results = {}  # 保存验证结果 {url: True/False}
        self.first_time_hide = True  # 首次点击隐藏按钮提示
        self.is_hiding_invalid = False  # 跟踪当前是否处于隐藏无效项状态
        self.config = ConfigHandler()
        self.scanner = StreamScanner()
        self.validator = StreamValidator()  # 新增验证器实例
        self.epg_manager = EPGManager()
        self.player = VLCPlayer()
        self.playlist_handler = PlaylistHandler()
        self.converter = PlaylistConverter(self.epg_manager)
        self.playlist_source = None  # 播放列表来源：None/file/scan
        # +++ 新增智能匹配相关变量 +++
        self.old_playlist = None  # 存储旧列表数据 {url: channel_info}
        self.match_worker = None  # 异步任务对象
        self._is_closing = False  # 关闭标志

        # 连接信号
        self.scanner.ffprobe_missing.connect(self.show_ffprobe_warning)
        self.validator.progress_updated.connect(self.update_validation_progress)
        self.validator.validation_finished.connect(self.on_validation_finished)
        self.validator.error_occurred.connect(self.show_error)
        self.validator.channel_validated.connect(self.on_channel_validated)
            
        # 异步任务跟踪
        self.scan_worker: Optional[AsyncWorker] = None
        self.play_worker: Optional[AsyncWorker] = None

        self._init_ui()
        self._connect_signals()
        self.load_config()

        # 添加防抖定时器
        self.debounce_timer = QtCore.QTimer()
        self.debounce_timer.setSingleShot(True)  # 单次触发
        self.debounce_timer.timeout.connect(self.update_completer_model)

        # 连接信号与槽
        self.epg_progress_updated.connect(self.update_status)
        self.player.state_changed.connect(self._handle_player_state)
        self.name_edit.installEventFilter(self)

    def show_ffprobe_warning(self):
        """显示ffprobe缺失警告"""
        QMessageBox.warning(
            self,
            "功能受限",
            "未检测到ffprobe，部分功能将受限：\n"
            "1. 无法检测视频分辨率/编码格式\n"
            "2. 仅能验证基本连接性\n\n"
            "请安装FFmpeg以获得完整功能\n"
            "下载地址: https://ffmpeg.org"
        )

    async def _async_show_warning(self, title: str, message: str) -> None:
        """异步显示警告对话框"""
        # 使用QMessageBox显示警告
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Icon.Warning)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        
        # 直接执行对话框
        msg_box.exec()

    # 事件过滤器处理焦点事件（最终版）
    def eventFilter(self, source, event: QtCore.QEvent) -> bool:
        """事件过滤器处理焦点事件（最终版）"""
        if (source is self.name_edit and 
            event.type() == QtCore.QEvent.Type.FocusIn):
            self.update_completer_model()
        return super().eventFilter(source, event)

    # 初始化用户界面
    def _init_ui(self) -> None:
        """初始化用户界面"""
        self.setWindowTitle("IPTV Scanner Editor Pro / IPTV 专业扫描编辑工具")
        self.resize(1200, 800)
        
        # 使用系统调色板适应深色/浅色模式
        self.setStyleSheet(AppStyles.main_window_style())
        
        # 主布局
        main_widget = QtWidgets.QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QtWidgets.QHBoxLayout(main_widget)

        # 左侧面板
        self.left_splitter = QtWidgets.QSplitter(Qt.Orientation.Vertical)
        self._setup_scan_panel(self.left_splitter)
        self._setup_channel_list(self.left_splitter)

        # 右侧面板布局（关键修正）
        self.right_splitter = QtWidgets.QSplitter(Qt.Orientation.Vertical)
        self.right_splitter.setHandleWidth(10)  # 显式设置分割线宽度
        
        # 播放器区域（必须作为第一个直接子部件）
        self._setup_player_panel(self.right_splitter)
        
        # 底部容器（包含编辑区和功能区）
        bottom_container = QtWidgets.QWidget()
        bottom_container.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding
        )
        
        bottom_layout = QtWidgets.QHBoxLayout(bottom_container)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        
        # 水平分割器
        h_splitter = QtWidgets.QSplitter(Qt.Orientation.Horizontal)
        self._setup_edit_panel(h_splitter)
        self._setup_match_panel(h_splitter)
        bottom_layout.addWidget(h_splitter)
        
        # 添加到垂直分割器
        self.right_splitter.addWidget(bottom_container)
        
        # 设置初始比例（7:3）
        self.right_splitter.setSizes([700, 300])


        # 添加分隔线样式
        self._setup_splitter_handle(self.left_splitter)
        self._setup_splitter_handle(self.right_splitter)

        main_layout.addWidget(self.left_splitter)
        main_layout.addWidget(self.right_splitter)

        # 初始化菜单和工具栏
        self._setup_menubar()
        self._setup_toolbar()

        # 确保状态栏显示并设置样式
        status_bar = self.statusBar()
        
        # 连接分隔条位置变化信号
        self.left_splitter.splitterMoved.connect(self._save_splitter_sizes)
        self.right_splitter.splitterMoved.connect(self._save_splitter_sizes)
        status_bar.show()
        status_bar.setStyleSheet(AppStyles.statusbar_style())
        status_bar.showMessage("程序已启动")
        
        # 添加进度指示器
        self.progress_indicator = QtWidgets.QProgressBar()
        self.progress_indicator.setRange(0, 0)  # 无限循环模式
        self.progress_indicator.setTextVisible(False)
        self.progress_indicator.setFixedWidth(120)
        self.progress_indicator.setStyleSheet(AppStyles.progress_style())
        self.progress_indicator.hide()
        status_bar.addPermanentWidget(self.progress_indicator)

    # 为 QSplitter 设置分隔线样式
    def _setup_splitter_handle(self, splitter: QtWidgets.QSplitter) -> None:
        """为 QSplitter 设置分隔线样式"""
        # 设置分隔线的样式表
        if splitter.orientation() == QtCore.Qt.Orientation.Vertical:
            splitter.setStyleSheet(AppStyles.splitter_handle_style("horizontal"))
        else:
            splitter.setStyleSheet(AppStyles.splitter_handle_style("vertical"))

    # 配置扫描面板
    def _setup_scan_panel(self, parent: QtWidgets.QSplitter) -> None:
        """配置扫描面板"""
        scan_group = QtWidgets.QGroupBox("扫描设置")
        scan_layout = QtWidgets.QFormLayout()

        self.ip_range_input = QtWidgets.QLineEdit()
        self.scan_progress = QtWidgets.QProgressBar()
        self.scan_progress.setStyleSheet(AppStyles.progress_style())

        # 超时时间设置
        timeout_layout = QtWidgets.QHBoxLayout()
        timeout_label = QtWidgets.QLabel("设置扫描超时时间（秒）")
        timeout_layout.addWidget(timeout_label)
        self.timeout_input = QtWidgets.QSpinBox()
        self.timeout_input.setRange(1, 60)
        self.timeout_input.setValue(10)
        self.timeout_input.setSuffix(" 秒")
        timeout_layout.addWidget(self.timeout_input)
        
        # 线程数设置
        thread_layout = QtWidgets.QHBoxLayout()
        thread_label = QtWidgets.QLabel("设置扫描使用的线程数量")
        thread_layout.addWidget(thread_label)
        self.thread_count_input = QtWidgets.QSpinBox()
        self.thread_count_input.setRange(1, 100)
        self.thread_count_input.setValue(10)
        self.thread_count_input.setToolTip("同时处理的频道数量，也决定批处理大小(最大50)")
        thread_layout.addWidget(self.thread_count_input)

        # User-Agent设置
        user_agent_layout = QtWidgets.QHBoxLayout()
        user_agent_label = QtWidgets.QLabel("User-Agent:")
        user_agent_layout.addWidget(user_agent_label)
        self.user_agent_input = QtWidgets.QLineEdit()
        self.user_agent_input.setPlaceholderText("可选，留空使用默认")
        user_agent_layout.addWidget(self.user_agent_input)

        # Referer设置
        referer_layout = QtWidgets.QHBoxLayout()
        referer_label = QtWidgets.QLabel("Referer:")
        referer_layout.addWidget(referer_label)
        self.referer_input = QtWidgets.QLineEdit()
        self.referer_input.setPlaceholderText("可选，留空不使用")
        referer_layout.addWidget(self.referer_input)

        # 扫描控制按钮
        self.scan_btn = QtWidgets.QPushButton("完整扫描")
        self.scan_btn.setStyleSheet(AppStyles.button_style(active=True))
        self.scan_btn.clicked.connect(self.toggle_scan)
        
        # 设置按钮尺寸策略为Expanding
        self.scan_btn.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Fixed
        )

        # 扫描统计信息
        self.detailed_stats_label = QtWidgets.QLabel("总频道: 0 | 有效: 0 | 无效: 0 | 耗时: 0s")
        self.detailed_stats_label.setStyleSheet(AppStyles.stats_label_style())

        # 使用网格布局让按钮和统计信息并排显示
        button_stats_layout = QtWidgets.QGridLayout()
        button_stats_layout.addWidget(self.scan_btn, 0, 0, 1, 2)  # 按钮占满前两列
        button_stats_layout.addWidget(self.detailed_stats_label, 1, 0, 1, 2)  # 统计信息占满第二行
        
        # 设置列拉伸比例
        button_stats_layout.setColumnStretch(0, 1)
        button_stats_layout.setColumnStretch(1, 1)

        scan_layout.addRow("地址格式：", QtWidgets.QLabel("示例：http://192.168.1.1:1234/rtp/10.10.[1-20].[1-20]:5002   [1-20]表示范围"))
        scan_layout.addRow("输入地址：", self.ip_range_input)
        scan_layout.addRow("超时时间：", timeout_layout)
        scan_layout.addRow("线程数：", thread_layout)
        scan_layout.addRow("User-Agent：", user_agent_layout)
        scan_layout.addRow("Referer：", referer_layout)
        scan_layout.addRow("进度：", self.scan_progress)
        scan_layout.addRow(button_stats_layout)  # 添加按钮和统计信息布局

        scan_group.setLayout(scan_layout)
        parent.addWidget(scan_group)

    # 配置频道列表
    def _setup_channel_list(self, parent: QtWidgets.QSplitter) -> None:  
        """配置频道列表"""
        list_group = QtWidgets.QGroupBox("频道列表")
        list_layout = QtWidgets.QVBoxLayout()

        # === 新增工具栏 ===
        toolbar = QtWidgets.QHBoxLayout()
        
        # 有效性检测按钮
        self.btn_validate = QtWidgets.QPushButton("检测有效性")
        self.btn_validate.setStyleSheet(AppStyles.button_style(active=True))
        
        # 隐藏无效项按钮
        self.btn_hide_invalid = QtWidgets.QPushButton("隐藏无效项")
        self.btn_hide_invalid.setStyleSheet(AppStyles.button_style())
        self.btn_validate.clicked.connect(lambda: asyncio.create_task(self.toggle_validation()))
        self.btn_hide_invalid.clicked.connect(lambda: asyncio.create_task(self.hide_invalid_channels()))
        
        # 状态标签
        self.filter_status_label = QtWidgets.QLabel("请先加载列表并点击检测有效性")
        self.filter_status_label.setStyleSheet(AppStyles.status_label_style())
        
        toolbar.addWidget(self.btn_validate)
        toolbar.addWidget(self.btn_hide_invalid)
        toolbar.addWidget(self.filter_status_label)
        toolbar.addStretch()
        list_layout.addLayout(toolbar)

        self.channel_list = QtWidgets.QTableView()
       
        self.channel_list.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.channel_list.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.channel_list.horizontalHeader().setStretchLastSection(True)
        self.channel_list.verticalHeader().setVisible(False)
        self.model = ChannelListModel()
        self.channel_list.setModel(self.model)
        self.channel_list.setStyleSheet(AppStyles.list_style())
        # === 新增右键菜单 ===
        self.channel_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.channel_list.customContextMenuRequested.connect(self.show_context_menu)
        list_layout.addWidget(self.channel_list)
        list_group.setLayout(list_layout)
        parent.addWidget(list_group)

    # 配置播放器面板
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
        player_layout.addWidget(self.player, stretch=10)  # 播放器占主要空间

        # 控制按钮
        control_layout = QtWidgets.QHBoxLayout()
        self.pause_btn = QtWidgets.QPushButton("播放")
        self.pause_btn.setStyleSheet(AppStyles.player_button_style())
        self.pause_btn.clicked.connect(self.player.toggle_pause)
        self.stop_btn = QtWidgets.QPushButton("停止")
        self.stop_btn.setStyleSheet(AppStyles.button_style())
        self.stop_btn.clicked.connect(self.stop_play)

        control_layout.addWidget(self.pause_btn)
        control_layout.addWidget(self.stop_btn)

        player_layout.addLayout(control_layout, stretch=1)  # 控制区占较小空间

        # 音量控制
        volume_layout = QtWidgets.QHBoxLayout()

        self.volume_slider = QtWidgets.QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(50)  # 默认音量
        self.volume_slider.valueChanged.connect(self.set_volume)

        volume_layout.addWidget(QtWidgets.QLabel("音量："))
        volume_layout.addWidget(self.volume_slider)

        player_layout.addLayout(volume_layout, stretch=1)  # 音量控制占较小空间

        player_group.setLayout(player_layout)
        
        # 关键修改3：确保直接添加到QSplitter
        if isinstance(parent, QtWidgets.QSplitter):
            parent.addWidget(player_group)
        else:
            layout = parent.layout() or QtWidgets.QVBoxLayout(parent)
            layout.addWidget(player_group)

    # 配置编辑面板
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
        self.name_edit = QtWidgets.QLineEdit()
        self.name_edit.setMinimumHeight(32)  # 增加输入框高度
        self.name_edit.setPlaceholderText("输入频道名称...")
        self.name_edit.returnPressed.connect(self.save_channel_edit)  # 绑定回车键事件

        # 分组选择（增加下拉框高度，设置为可编辑）
        self.group_combo = QtWidgets.QComboBox()
        self.group_combo.setMinimumHeight(32)
        self.group_combo.setEditable(True)  # 允许自定义输入
        self.group_combo.addItems(["未分类", "央视", "卫视", "本地", "高清频道", "测试频道"])

        # EPG匹配状态显示（新增）
        self.epg_match_label = QtWidgets.QLabel("EPG状态: 未匹配")
        self.epg_match_label.setStyleSheet("font-weight: bold;")
        
        # 保存按钮（加大尺寸）
        save_btn = QtWidgets.QPushButton("保存修改")
        save_btn.setMinimumHeight(36)  # 增加按钮高度
        save_btn.setStyleSheet(AppStyles.button_style())
        save_btn.clicked.connect(self.save_channel_edit)

        # 布局调整
        edit_layout.addRow("频道名称：", self.name_edit)
        edit_layout.addRow("分组分类：", self.group_combo)
        edit_layout.addRow(self.epg_match_label)  # 新增状态显示
        edit_layout.addRow(QtWidgets.QLabel())  # 空行占位
        edit_layout.addRow(save_btn)

        # 修复自动补全功能
        self.epg_completer = QtWidgets.QCompleter()
        self.epg_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)  # 不区分大小写
        self.epg_completer.setFilterMode(Qt.MatchFlag.MatchContains)  # 支持模糊匹配
        self.epg_completer.setCompletionMode(QtWidgets.QCompleter.CompletionMode.PopupCompletion)  # 显示下拉列表
        self.epg_completer.setMaxVisibleItems(10)  # 最多显示10个匹配项
        self.name_edit.setCompleter(self.epg_completer)

        # 绑定文本变化事件
        self.name_edit.textChanged.connect(self.on_text_changed)

        edit_group.setLayout(edit_layout)
        parent.addWidget(edit_group)

    # 初始化菜单栏
    def _setup_menubar(self) -> None:  
        """初始化菜单栏"""
        menubar = self.menuBar()

        # 文件菜单
        file_menu = menubar.addMenu("文件(&F)")
        open_action = QAction("打开列表(&O)", self)
        open_action.setShortcut(QKeySequence("Ctrl+O"))
        open_action.triggered.connect(self.open_playlist)
        file_menu.addAction(open_action)

        save_action = QAction("保存列表(&S)", self)
        save_action.setShortcut(QKeySequence("Ctrl+S"))
        save_action.triggered.connect(self.save_playlist)
        file_menu.addAction(save_action)

        file_menu.addSeparator()
        exit_action = QAction("退出(&X)", self)
        exit_action.setShortcut(QKeySequence("Ctrl+Q"))
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

    # 初始化工具栏
    def _setup_toolbar(self) -> None:  
        """初始化工具栏"""
        toolbar = self.addToolBar("主工具栏")
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        toolbar.setMovable(False)

        def load_icon(path: str) -> QIcon:
            """加载图标，如果失败则返回空图标"""
            icon_path = Path(__file__).parent / path
            if icon_path.exists():
                return QIcon(str(icon_path))
            return QIcon()

        # 打开列表
        open_action = QAction(load_icon("icons/open.png"), "打开列表", self)
        open_action.triggered.connect(self.open_playlist)
        toolbar.addAction(open_action)

        # 保存列表
        save_action = QAction(load_icon("icons/save.png"), "保存列表", self)
        save_action.triggered.connect(self.save_playlist)
        toolbar.addAction(save_action)

        # 加载 EPG 数据
        load_epg_action = QAction(load_icon("icons/load.png"), "加载 EPG", self)
        load_epg_action.triggered.connect(self.load_epg_cache)
        toolbar.addAction(load_epg_action)

        # EPG 管理
        epg_manage_action = QAction(load_icon("icons/settings.png"), "EPG 管理", self)
        epg_manage_action.triggered.connect(self.manage_epg)
        toolbar.addAction(epg_manage_action)

        # 关于
        about_action = QAction(load_icon("icons/info.png"), "关于", self)
        about_action.triggered.connect(lambda: asyncio.create_task(self._show_about_dialog()))
        toolbar.addAction(about_action)

        # 添加分隔线保持布局美观
        toolbar.addSeparator()

    # 从GitHub获取最新版本号
    async def _get_latest_version(self) -> str:
        """从GitHub获取最新版本号"""
        try:
            # GitHub API获取最新发布版本
            url = "https://api.github.com/repos/sumingyd/IPTV-Scanner-Editor-Pro/releases/latest"
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        version = data.get('tag_name', '').lstrip('v')
                        if version:  # 确保获取到的版本号不为空
                            return version
                    # 如果请求失败或版本号为空，则抛出异常
                    raise Exception(f"从GitHub获取最新版本失败，HTTP状态码: {response.status}")
        except Exception as e:
            logger.error(f"获取最新版本失败: {str(e)}")
            # 返回默认版本号
            return "2.0.0.0"

    # 显示关于对话框
    async def _show_about_dialog(self):
        """显示自动适应系统深浅色主题的关于对话框"""
        # 异步获取最新版本号
        try:
            latest_version = await asyncio.wait_for(self._get_latest_version(), timeout=5)
        except asyncio.TimeoutError:
            latest_version = "2.0.0.0"
            logger.warning("获取最新版本超时，使用默认版本号")
        
        # 检测系统主题
        is_dark = self.palette().window().color().lightness() < 128
        
        # 动态颜色设置
        bg_color = "#2d2d2d" if is_dark else "#ffffff"
        text_color = "#eeeeee" if is_dark else "#333333"
        accent_color = "#3498db"  # 主色调保持不变
        card_bg = "#3a3a3a" if is_dark else "#f8f9fa"
        border_color = "#444444" if is_dark else "#e0e0e0"
        code_bg = "#454545" if is_dark else "#f0f0f0"
        code_text = "#ffffff" if is_dark else "#333333"

        about_text = f'''
        <div style="font-family: 'Microsoft YaHei', sans-serif; color: {text_color};">
            <h1 style="color: {accent_color}; text-align: center; margin-bottom: 15px; font-size: 18px;">
                IPTV Scanner Editor Pro / IPTV 专业扫描编辑工具
            </h1>
            
            <div style="background-color: {card_bg}; padding: 15px; border-radius: 8px; 
                 margin-bottom: 15px; border: 1px solid {border_color};">
                <p style="line-height: 1.6; margin: 5px 0;">
                    <b>当前版本：</b> 4.0.0.1
                </p>
                <p style="line-height: 1.6; margin: 5px 0;">
                    <b>最新版本：</b> {latest_version} 
                </p>
                <p style="line-height: 1.6; margin: 5px 0;">
                    <b>编译日期：</b> {datetime.date.today().strftime("%Y-%m-%d")}
                </p>
                <p style="line-height: 1.6; margin: 5px 0;">
                    <b>QT版本：</b> {QtCore.qVersion()}
                </p>
            </div>
            
            <h3 style="color: {accent_color}; border-bottom: 1px solid {border_color}; 
                padding-bottom: 5px; font-size: 15px; margin-top: 0;">
                功能特性
            </h3>
            <ul style="margin-left: 20px; line-height: 1.6; padding-left: 5px;">
                <li>支持 HTTP/UDP/RTP/RTSP 协议检测</li>
                <li>EPG 信息保存与加载</li>
                <li>多线程高效扫描引擎</li>
                <li>支持 M3U/M3U8/TXT 播放列表格式</li>
                <li>实时流媒体可用性检测</li>
            </ul>
            
            <h3 style="color: {accent_color}; border-bottom: 1px solid {border_color}; 
                padding-bottom: 5px; font-size: 15px; margin-top: 15px;">
                快捷键
            </h3>
            <ul style="margin-left: 20px; line-height: 1.6; padding-left: 5px;">
                <li><code style="background-color: {code_bg}; color: {code_text}; 
                    padding: 2px 5px; border-radius: 3px;">Ctrl+O</code> - 打开播放列表</li>
                <li><code style="background-color: {code_bg}; color: {code_text};
                    padding: 2px 5px; border-radius: 3px;">Ctrl+S</code> - 保存播放列表</li>
                <li><code style="background-color: {code_bg}; color: {code_text};
                    padding: 2px 5px; border-radius: 3px;">空格键</code> - 暂停/继续播放</li>
            </ul>
            
            <div style="margin-top: 20px; text-align: center; font-size: 0.9em; color: {text_color}; opacity: 0.8;">
                <p>   DeepSeek 贡献代码  </p>
                <p>
                    <a href="https://github.com/sumingyd/IPTV-Scanner-Editor-Pro" 
                       style="color: {accent_color}; text-decoration: none;">GitHub 仓库</a> 
                    | <span>作者QQ: 331874545</span>
                </p>
            </div>
        </div>
        '''

        # 创建对话框
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowFlags(dialog.windowFlags() | QtCore.Qt.WindowType.WindowStaysOnTopHint)
        dialog.setWindowTitle("关于")
        dialog.setMinimumWidth(480)
        dialog.setMinimumHeight(550)
        
        # 设置自适应样式
        dialog.setStyleSheet(f"""
            QDialog {{
                background-color: {bg_color};
                color: {text_color};
            }}
            QPushButton {{
                background-color: {accent_color};
                color: white;
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
                min-width: 80px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #2980b9;
            }}
        """)
        
        # 主布局
        layout = QtWidgets.QVBoxLayout(dialog)
        layout.setContentsMargins(20, 20, 20, 15)
        layout.setSpacing(15)
        
        # 添加图标
        icon_path = str(Path(__file__).parent / "icons" / "logo.png")
        pixmap = QtGui.QPixmap(icon_path)
        if not pixmap.isNull():
            pixmap = pixmap.scaled(90, 90, 
                                 QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                                 QtCore.Qt.TransformationMode.SmoothTransformation)
            icon_label = QtWidgets.QLabel()
            icon_label.setPixmap(pixmap)
            icon_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(icon_label)
        
        # 使用QTextBrowser显示富文本内容
        text_browser = QtWidgets.QTextBrowser()
        text_browser.setHtml(about_text)
        text_browser.setOpenExternalLinks(True)
        layout.addWidget(text_browser)
        
        # 确定按钮
        button_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok)
        button_box.accepted.connect(dialog.accept)
        layout.addWidget(button_box)
        
        dialog.exec()

    # 配置智能匹配功能区
    def _setup_match_panel(self, parent_layout):
        """添加智能匹配功能区（右侧新增区域）"""
        match_group = QtWidgets.QGroupBox("智能匹配")
        layout = QtWidgets.QVBoxLayout()
        
        # 1. 操作按钮
        self.btn_load_old = QtWidgets.QPushButton("加载旧列表")  # 改为成员变量
        self.btn_load_old.setStyleSheet(AppStyles.button_style())

        self.btn_match = QtWidgets.QPushButton("执行自动匹配")  # 改为成员变量
        self.btn_match.setStyleSheet(AppStyles.button_style())
        self.btn_match.setEnabled(False)  # 现在可以正确访问

        # 2. 状态显示
        self.match_status = QtWidgets.QLabel("匹配功能未就绪 - 请先加载旧列表", self)
        self.match_status.setStyleSheet("color: #666; font-weight: bold;")
        self.match_progress = QtWidgets.QProgressBar(self)  # 初始化进度条
        self.match_progress.setTextVisible(True)
        self.match_progress.setStyleSheet(AppStyles.progress_style())  # 正确调用样式
        
        # 3. 高级选项
        self.cb_override_epg = QtWidgets.QCheckBox("EPG不匹配时强制覆盖", self)
        self.cb_auto_save = QtWidgets.QCheckBox("匹配后自动保存", self)
        
        # 布局
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addWidget(self.btn_load_old)
        button_layout.addWidget(self.btn_match)
        
        layout.addLayout(button_layout)
        layout.addWidget(QtWidgets.QLabel("匹配进度:"))
        layout.addWidget(self.match_progress)
        layout.addWidget(self.match_status)
        layout.addStretch()
        layout.addWidget(self.cb_override_epg)
        layout.addWidget(self.cb_auto_save)
        
        match_group.setLayout(layout)
        parent_layout.addWidget(match_group)
        
        # 信号连接
        self.btn_load_old.clicked.connect(self.load_old_playlist)
        self.btn_match.clicked.connect(lambda: asyncio.create_task(self.run_auto_match()))

    # 更新EPG匹配状态显示
    def update_epg_match_status(self, is_matched: bool, source: str = "EPG"):
        """更新EPG匹配状态显示"""
        if is_matched:
            self.epg_match_label.setText(f"✓ {source}匹配成功")
            self.epg_match_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
        else:
            self.epg_match_label.setText(f"⚠ 未匹配到{source}数据")
            self.epg_match_label.setStyleSheet("color: #FF9800; font-weight: bold;")

    # 连接信号与槽
    def _connect_signals(self) -> None:  
        """连接信号与槽"""
        self.scanner.progress_updated.connect(self.update_progress)
        self.scanner.scan_finished.connect(self.handle_scan_results)
        self.scanner.channel_found.connect(self.handle_channel_found)
        self.scanner.error_occurred.connect(self.show_error)
        self.channel_list.selectionModel().currentChanged.connect(self.on_channel_selected)
        self.player.state_changed.connect(self._handle_player_state)

    # 统一处理播放状态更新
    def _handle_player_state(self, msg: str):  
        """统一处理播放状态更新"""
        self.statusBar().showMessage(msg)
        # 根据播放状态更新按钮文字
        if "播放中" in msg:
            self.pause_btn.setText("暂停")
        elif "暂停" in msg:
            self.pause_btn.setText("继续")
        else:  # 不在播放状态
            self.pause_btn.setText("播放")

    # 扫描控制切换
    @pyqtSlot()
    def toggle_scan(self) -> None:
        """切换扫描状态"""
        try:
            ip_range = self.ip_range_input.text().strip()
            
            if hasattr(self.scanner, '_is_scanning') and self.scanner._is_scanning:
                self.scanner.stop_scan()
                self.scan_btn.setText("完整扫描")
                self.scan_btn.setStyleSheet(AppStyles.button_style())
                self.statusBar().showMessage("扫描已停止")
            else:
                if not ip_range:
                    self.show_error("请输入有效的频道地址")
                    return
                    

                # 清空现有频道列表
                self.model.channels.clear()
                self.model.layoutChanged.emit()
                self.playlist_source = 'scan'  # 设置播放列表来源为扫描

                # 显示扫描开始信息
                timeout = self.timeout_input.value()
                thread_count = self.thread_count_input.value()
                self.statusBar().showMessage(
                    f"开始扫描: {ip_range} (超时: {timeout}秒, 线程数: {thread_count})"
                )

                # 设置超时时间（从用户输入中获取）
                timeout = self.timeout_input.value()
                self.scanner.set_timeout(timeout)

                # 设置线程数（从用户输入中获取）
                thread_count = self.thread_count_input.value()
                self.scanner.set_thread_count(thread_count)

                # 设置User-Agent和Referer
                user_agent = self.user_agent_input.text().strip()
                if user_agent:
                    self.scanner.set_user_agent(user_agent)
                
                referer = self.referer_input.text().strip()
                if referer:
                    self.scanner.set_referer(referer)

                # 确保传入的是一个协程
                self.scan_worker = AsyncWorker(self.scanner.toggle_scan(ip_range))
                self.scan_worker.finished.connect(self.handle_scan_success)
                self.scan_worker.error.connect(self.handle_scan_error)
                self.scan_worker.cancelled.connect(self.handle_scan_cancel)
                asyncio.create_task(self.scan_worker.run())
                
                # 更新按钮状态
                self.scan_btn.setText("停止扫描")
                self.scan_btn.setStyleSheet(AppStyles.button_style(active=True))
        except Exception as e:
            self.show_error(f"扫描控制错误: {str(e)}")
            self.scan_btn.setText("完整扫描")
            self.scan_btn.setStyleSheet(AppStyles.button_style())

    # 停止扫描任务
    @pyqtSlot()
    def stop_scan(self) -> None: 
        """停止扫描任务"""
        if not hasattr(self.scanner, '_is_scanning') or not self.scanner._is_scanning:
            self.statusBar().showMessage("当前没有进行中的扫描任务")
            return
            
        self.scanner.stop_scan()
        if self.model.channels:
            self.statusBar().showMessage(f"扫描已停止，共发现 {len(self.model.channels)} 个频道")
        else:
            self.statusBar().showMessage("扫描已停止，未发现有效频道")

    # 执行异步扫描
    async def _async_scan(self, ip_range: str) -> None:  
        """执行异步扫描"""
        await self.scanner.scan_task(ip_range)

    # 更新扫描进度
    @pyqtSlot(int, str)
    def update_progress(self, percent: int, msg: str) -> None: 
        """更新扫描进度"""
        self.scan_progress.setValue(percent)
        # 直接显示scanner.py传递的详细状态信息
        self.statusBar().showMessage(msg)
        # 标记当前处于扫描状态
        self._last_scan_status = msg

    #处理单个频道发现
    @pyqtSlot(dict)
    def handle_channel_found(self, channel: Dict) -> None: 
        """处理单个频道发现"""
        # 检查是否已存在相同URL的频道
        if not any(c['url'] == channel['url'] for c in self.model.channels):
            # 在主线程中执行UI更新
            QtCore.QMetaObject.invokeMethod(self, "_add_channel", 
                QtCore.Qt.ConnectionType.QueuedConnection,
                QtCore.Q_ARG(dict, channel))

    #实际添加频道的槽函数
    @pyqtSlot(dict)
    def _add_channel(self, channel: Dict) -> None: 
        """实际添加频道的槽函数"""
        self.model.beginInsertRows(QtCore.QModelIndex(),
                                 len(self.model.channels),
                                 len(self.model.channels))
        self.model.channels.append(channel)
        self.model.endInsertRows()
        # 强制刷新UI
        QtWidgets.QApplication.processEvents()

    #处理最终扫描结果
    @pyqtSlot(dict)
    def handle_scan_results(self, result: Dict) -> None: 
        """处理最终扫描结果"""
        channels = result['channels']
        total = result['total']
        invalid = result['invalid']
        elapsed = result['elapsed']
        # 更新统计信息显示
        self.detailed_stats_label.setText(f"总数: {total} | 有效: {len(channels)} | 无效: {invalid} | 耗时: {elapsed:.1f}s")
        self.statusBar().showMessage("扫描完成")
        
        # 恢复扫描按钮状态
        self.scan_btn.setText("完整扫描")
        self.scan_btn.setStyleSheet(AppStyles.button_style())
        
        # 自动选择第一个频道但不自动播放
        if channels:
            first_index = self.model.index(0, 0)
            self.channel_list.setCurrentIndex(first_index)
            # 手动触发状态更新
            self._handle_player_state("准备播放")

    # 处理频道选择事件
    @pyqtSlot()
    def on_channel_selected(self) -> None: 
        """处理频道选择事件"""
        index = self.channel_list.currentIndex()
        if not index.isValid():
            return

        chan = self.model.channels[index.row()]
        self.name_edit.setText(chan.get('name', '未命名频道'))
        self.group_combo.setCurrentText(chan.get('group', '未分类'))

        # 更新EPG匹配状态
        is_matched = self.epg_manager.is_channel_matched(chan.get('name', ''))
        self.update_epg_match_status(is_matched, "EPG")

        # 如果EPG未匹配但频道名称不为空，尝试重新匹配
        if not is_matched and chan.get('name'):
            is_matched = self.epg_manager.is_channel_matched(chan.get('name', ''))
            self.update_epg_match_status(is_matched, "EPG")

        if url := chan.get('url'):
            asyncio.create_task(self.safe_play(url))

    # 安全播放包装器
    async def safe_play(self, url: str) -> None: 
        """安全播放包装器"""
        try:
            # 取消旧任务
            if hasattr(self, 'play_worker') and self.play_worker and not self.play_worker.is_finished():
                self.play_worker.cancel()
                
            # 确保播放器已初始化
            if not hasattr(self, 'player') or not self.player:
                self.player = VLCPlayer()
                
            # 创建新任务
            self.play_worker = AsyncWorker(self.player.async_play(url))
            self.play_worker.finished.connect(self.handle_play_success)
            self.play_worker.error.connect(self.handle_play_error)
            await self.play_worker.run()
            
            # 手动触发状态更新
            self._handle_player_state("播放中")
        except Exception as e:
            self.show_error(f"播放失败: {str(e)}")

    # 安全停止包装器
    async def safe_stop(self) -> None:
        """安全停止包装器"""
        try:
            if hasattr(self, 'player') and self.player:
                await self.player.stop()
        except Exception as e:
            self.show_error(f"停止失败: {str(e)}")

    # 统一调用播放器的停止方法
    @qasync.asyncSlot()
    async def stop_play(self): 
        """统一调用播放器的停止方法"""
        await self.safe_stop()


    # 隐藏无效频道
    async def hide_invalid_channels(self):
        """切换隐藏/显示无效频道状态"""
        # 检查是否有正在进行的验证任务
        if hasattr(self, 'validator') and self.validator.is_running():
            msg_box = QMessageBox(self)
            msg_box.setIcon(QMessageBox.Icon.Warning)
            msg_box.setWindowTitle("提示")
            msg_box.setText("有效性检测正在进行中，请等待完成")
            msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg_box.exec()
            return
            
        if not hasattr(self, 'validation_results') or not self.validation_results:
            msg_box = QMessageBox(self)
            msg_box.setIcon(QMessageBox.Icon.Warning)
            msg_box.setWindowTitle("提示")
            msg_box.setText("请先点击[检测有效性]")
            msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg_box.exec()
            return

        if not hasattr(self, 'original_channels'):
            self.original_channels = deepcopy(self.model.channels)

        if self.is_hiding_invalid:
            # 恢复显示所有频道
            self.model.channels = self.original_channels
            self.model.layoutChanged.emit()
            self.channel_list.setCornerWidget(None)
            self.filter_status_label.setText("已恢复全部频道")
            self.btn_hide_invalid.setText("隐藏无效项")
            self.is_hiding_invalid = False
        else:
            # 隐藏无效频道
            # 首次点击提示
            if self.first_time_hide:
                await self._async_show_warning(
                    "提示",
                    "将隐藏所有检测为无效的频道\n"
                    "再次点击按钮可恢复显示"
                )
                self.first_time_hide = False

            # 过滤无效频道
            valid_channels = [
                chan for chan in self.model.channels 
                if self.validation_results.get(chan['url'], False)
            ]
            
            # 更新模型
            self.model.channels = valid_channels
            self.model.layoutChanged.emit()
            
            # 显示隐藏数量提示
            hidden_count = len(self.validation_results) - len(valid_channels)
            if hidden_count > 0:
                corner_label = QtWidgets.QLabel(f"已隐藏{hidden_count}项")
                corner_label.setStyleSheet("color: gray; font-size: 10px;")
                self.channel_list.setCornerWidget(corner_label)
            else:
                self.channel_list.setCornerWidget(None)
            self.filter_status_label.setText(f"显示中: {len(valid_channels)}项")
            self.btn_hide_invalid.setText("取消隐藏")
            self.is_hiding_invalid = True

    # 显示右键菜单
    def show_context_menu(self, pos):
        """显示右键菜单"""
        menu = QtWidgets.QMenu()
        
        # 根据当前状态显示不同的菜单项
        if self.is_hiding_invalid:
            menu.addAction(
                QIcon(":/icons/restore.svg"),  # 可替换为你的图标
                "恢复显示全部",
                lambda: asyncio.create_task(self.hide_invalid_channels())
            )
        menu.addAction("复制选中URL", self.copy_selected_url)
        menu.exec(self.channel_list.mapToGlobal(pos))

    # 恢复显示所有频道
    def restore_all_channels(self):
        """恢复显示所有频道（从原始数据重建模型）"""
        if hasattr(self, 'original_channels'):  # 需要先在hide时备份原始数据
            self.model.channels = self.original_channels
        self.model.layoutChanged.emit()
        self.channel_list.setCornerText("")
        self.filter_status_label.setText("已恢复全部频道")

    # 复制选中URL到剪贴板
    def copy_selected_url(self):
        """复制选中URL到剪贴板"""
        index = self.channel_list.currentIndex()
        if index.isValid():
            url = self.model.channels[index.row()].get('url', '')
            QtWidgets.QApplication.clipboard().setText(url)
            self.statusBar().showMessage("已复制URL", 2000)

    # 保存频道编辑
    @pyqtSlot()
    def save_channel_edit(self) -> None:
        """保存频道编辑"""
        index = self.channel_list.currentIndex()
        if not index.isValid():
            self.show_error("请先选择要编辑的频道")
            return

        new_name = self.name_edit.text().strip()
        new_group = self.group_combo.currentText()

        if not new_name:
            self.show_error("频道名称不能为空")
            return

        # 立即更新模型数据
        self.model.channels[index.row()].update({
            'name': new_name,
            'group': new_group
        })
        self.model.dataChanged.emit(index, index)
        
        # 自动保存配置
        self._save_config_sync()
        
        # 处理焦点和选择逻辑
        row_count = self.model.rowCount()
        if row_count > 1:
            # 多个频道时跳转到下一个
            next_row = index.row() + 1
            if next_row < row_count:
                next_index = self.model.index(next_row, 0)
                self.channel_list.setCurrentIndex(next_index)
            else:
                # 如果是最后一个频道，回到第一个
                next_index = self.model.index(0, 0)
                self.channel_list.setCurrentIndex(next_index)
            
            # 触发选中事件并确保编辑框获得焦点
            self.on_channel_selected()
        else:
            # 单个频道时保持当前选中状态
            self.channel_list.setCurrentIndex(index)
        
        # 自动选中编辑框中的文本
        self.name_edit.selectAll()
        # 确保焦点在编辑框
        self.name_edit.setFocus()
        # 强制立即处理事件队列
        QtWidgets.QApplication.processEvents()

    # 异步加载 EPG 数据
    @pyqtSlot()
    def load_epg_cache(self) -> None: 
        """异步加载 EPG 数据"""
        self.epg_progress_updated.emit("正在加载 EPG 数据...")
        self.scan_worker = AsyncWorker(self._async_load_epg())
        self.scan_worker.finished.connect(self.handle_epg_load_success)
        self.scan_worker.error.connect(self.handle_epg_load_error)
        self.scan_worker.start()

    # 异步加载 EPG 数据
    async def _async_load_epg(self) -> None: 
        """异步加载 EPG 数据"""
        try:
            success = await self.epg_manager.load_epg(self.epg_progress_updated.emit)
            message = "EPG 数据加载成功" if success else "EPG 数据加载失败"
            if success:
                self.epg_progress_updated.emit("EPG 数据加载完成，正在更新界面...")
                self.update_completer_model()
            self.epg_progress_updated.emit(message)
        except Exception as e:
            logger.error(f"EPG 操作失败: {str(e)}")
            self.epg_progress_updated.emit(f"EPG 操作失败: {str(e)}")

    # EPG 加载成功后的处理
    @pyqtSlot()
    def handle_epg_load_success(self) -> None: 
        """EPG 加载成功后的处理"""
        self.statusBar().showMessage("EPG 数据加载完成")
        self.update_completer_model()  # 确保界面更新
        # 更新当前选中频道的EPG匹配状态
        index = self.channel_list.currentIndex()
        if index.isValid():
            chan = self.model.channels[index.row()]
            is_matched = self.epg_manager.is_channel_matched(chan.get('name', ''))
            self.update_epg_match_status(is_matched, "EPG")
        # 刷新EPG匹配状态显示
        self.on_channel_selected()

    # EPG 加载失败后的处理
    @pyqtSlot(Exception)
    def handle_epg_load_error(self, error: Exception) -> None: 
        """EPG 加载失败后的处理"""
        self.show_error(f"EPG 加载失败: {str(error)}")
        self.statusBar().showMessage("EPG 加载失败")

    # 输入框文本变化处理
    def on_text_changed(self, text: str) -> None: 
        """输入框文本变化处理"""
        # 立即触发补全更新
        self.update_completer_model()
        # 启动防抖定时器（后续输入防抖）
        self.debounce_timer.start(300)

    # 自动补全模型更新
    def update_completer_model(self) -> None: 
        """自动补全模型更新"""
        try:
            current_text = self.name_edit.text().strip()
            if not current_text:
                self.epg_completer.setModel(QtCore.QStringListModel([]))
                return

            # 获取匹配的频道名称
            names = self._get_matching_channel_names(current_text)
            if names:
                QtCore.QTimer.singleShot(0, lambda: 
                    self.epg_completer.setModel(QtCore.QStringListModel(names)))
                if self.name_edit.hasFocus():
                    self.epg_completer.complete()
        except Exception as e:
            logger.error(f"自动补全异常: {str(e)}", exc_info=True)
            self.epg_completer.setModel(QtCore.QStringListModel([]))

    # 获取匹配的频道名称
    def _get_matching_channel_names(self, text: str) -> List[str]: 
        """获取匹配的频道名称"""
        try:
            raw_names = self.epg_manager.match_channel_name(text)
            return sorted(list(set(raw_names)), key=lambda x: (len(x), x))
        except Exception as e:
            logger.error(f"EPG查询失败: {str(e)}")
            return []
    
    # 打开播放列表文件
    @pyqtSlot()
    def open_playlist(self) -> None: 
        """打开播放列表文件"""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "打开播放列表",
            "",
            "播放列表文件 (*.m3u *.m3u8 *.txt)"
        )
        if not path:
            return

        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()

            if path.endswith('.txt'):
                channels = PlaylistParser.parse_txt(content)
            else:
                channels = PlaylistParser.parse_m3u(content)

            # 清空现有列表，而不是追加
            self.model.channels = channels
            self.model.layoutChanged.emit()
            self.statusBar().showMessage(f"已加载列表：{Path(path).name}")
            self.playlist_source = 'file'  # 设置播放列表来源为文件
        except Exception as e:
            self.show_error(f"打开文件失败: {str(e)}")
    
    # 保存播放列表文件
    @pyqtSlot()
    def save_playlist(self) -> None: 
        """保存播放列表文件"""
        path, _ = QFileDialog.getSaveFileName(
            self,
            "保存播放列表",
            "",
            "M3U播放列表 (*.m3u *.m3u8);;文本文件 (*.txt)"
        )
        if not path:
            return

        try:
            success = self.playlist_handler.save_playlist(self.model.channels, path)
            if success:
                self.statusBar().showMessage(f"列表已保存至：{path}")
            else:
                self.show_error("保存失败，请检查文件路径")
        except Exception as e:
            self.show_error(f"保存文件失败: {str(e)}")

    # 保存分隔条位置
    def _save_splitter_sizes(self):
        """保存当前分隔条位置到配置"""
        if hasattr(self, 'left_splitter') and hasattr(self, 'right_splitter'):
            left_sizes = self.left_splitter.sizes()
            right_sizes = self.right_splitter.sizes()
            self.config.config['UserPrefs']['splitter_sizes'] = json.dumps([left_sizes, right_sizes])
            self.config.save_prefs()

    # 窗口显示事件 - 恢复分隔条位置
    def showEvent(self, event):
        """窗口显示后恢复分隔条位置"""
        def restore_splitter_sizes():
            try:
                # 确保分隔条控件已初始化
                if not hasattr(self, 'left_splitter') or not hasattr(self, 'right_splitter'):
                    logger.warning("分隔条控件未初始化")
                    return
                
                # 确保有保存的分隔条位置
                if not hasattr(self, 'config') or not self.config.config.get('UserPrefs', 'splitter_sizes', fallback=''):
                    logger.warning("没有保存的分隔条位置")
                    return
                    
                left_sizes = self.config_file['splitter_sizes'][0]
                right_sizes = self.config_file['splitter_sizes'][1]
            
                # 验证尺寸数据
                if len(left_sizes) == 2 and len(right_sizes) == 2:
                    self.left_splitter.setSizes(left_sizes)
                    self.right_splitter.setSizes(right_sizes)
                    logger.info(f"成功恢复分隔条位置: left={left_sizes}, right={right_sizes}")
                else:
                    logger.warning(f"无效的分隔条尺寸: left={left_sizes}, right={right_sizes}")
            except Exception as e:
                logger.error(f"恢复分隔条位置失败: {str(e)}")
        
        # 延迟500ms确保所有控件完全初始化
        QtCore.QTimer.singleShot(500, restore_splitter_sizes)
        super().showEvent(event)

    async def _async_close(self, event: QCloseEvent):
        """异步关闭处理"""
        try:
            # 1. 设置关闭标志
            self._is_closing = True
            
            # 2. 保存当前UI配置到INI
            self._save_config_sync()
            
            # 3. 停止所有异步任务
            tasks = []
            if hasattr(self, 'scan_worker') and self.scan_worker:
                tasks.append(self.scan_worker.cancel())
            if hasattr(self, 'play_worker') and self.play_worker:
                tasks.append(self.play_worker.cancel())
            if hasattr(self, 'match_worker') and self.match_worker:
                tasks.append(self.match_worker.cancel())
                
            # 4. 停止所有子组件
            stop_tasks = []
            if hasattr(self, 'player') and self.player:
                stop_tasks.append(self.player.force_stop())
            if hasattr(self, 'scanner') and self.scanner:
                stop_tasks.append(self.scanner.stop_scan())
            if hasattr(self, 'validator') and self.validator:
                try:
                    await asyncio.wait_for(self.validator.stop_validation(), timeout=3)
                    for proc in self.validator._active_processes[:]:
                        if proc.returncode is None:
                            try:
                                proc.kill()
                            except ProcessLookupError:
                                pass
                    self.validator._active_processes.clear()
                except Exception:
                    for proc in self.validator._active_processes[:]:
                        if proc.returncode is None:
                            try:
                                proc.kill()
                            except ProcessLookupError:
                                pass
                    self.validator._active_processes.clear()
            
            # 5. 等待所有任务完成(带超时)
            if tasks or stop_tasks:
                await asyncio.wait_for(asyncio.gather(*tasks, *stop_tasks), timeout=2.0)
            
            # 6. 检查是否需要保存播放列表
            if self.playlist_source == 'file' and self.model.channels:
                reply = await qasync.QtAsyncio.asyncExec(QMessageBox.question)(
                    self,
                    '保存修改',
                    '是否保存对播放列表的修改？',
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel
                )
                
                if reply == QMessageBox.StandardButton.Yes:
                    self.save_playlist()
                elif reply == QMessageBox.StandardButton.Cancel:
                    event.ignore()
                    return
            
            # 7. 保存窗口布局
            self._save_splitter_sizes()
            
            # 8. 强制释放资源
            if hasattr(self, 'player') and self.player:
                self.player._release_sync()
            if hasattr(self, 'scanner') and self.scanner:
                await self.scanner.cleanup()
            
            # 9. 执行父类关闭事件
            super().closeEvent(event)
            
            # 10. 确保事件循环停止
            if hasattr(self, '_event_loop'):
                self._event_loop.stop()
        except Exception as e:
            logger.error(f"关闭异常: {str(e)}")
            event.ignore()

    # 处理关闭事件
    def closeEvent(self, event: QCloseEvent):
        """处理窗口关闭事件"""
        try:
            # 同步保存当前配置
            self._save_config_sync()
            
            # 获取当前事件循环
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 在已有事件循环中运行
                future = asyncio.ensure_future(self._async_close(event))
                future.add_done_callback(lambda _: event.accept())  # 完成后接受关闭事件
            else:
                # 没有运行中的事件循环，创建新循环
                loop.run_until_complete(self._async_close(event))
                event.accept()
        except Exception as e:
            logger.error(f"关闭事件处理失败: {str(e)}", exc_info=True)
            event.ignore()  # 出现异常时忽略关闭事件

    @pyqtSlot(int, str)
    def update_validation_progress(self, percent: int, msg: str):
        """更新验证进度"""
        self.filter_status_label.setText(msg)
        
        # 高亮显示当前正在检测的频道
        if hasattr(self.validator, '_current_url'):
            for i, chan in enumerate(self.model.channels):
                if chan.get('url') == self.validator._current_url:
                    chan['validating'] = True
                    index = self.model.index(i, 0)
                    self.model.dataChanged.emit(index, index)
                    break
        
        if percent == 100:
            self.btn_validate.setText("检测有效性")
            self.btn_validate.setStyleSheet(AppStyles.button_style())

    async def toggle_validation(self):
        """切换有效性检测状态"""
        if self.validator.is_running():
            await self.validator.stop_validation()
            self.btn_validate.setText("检测有效性")
            self.btn_validate.setChecked(False)
            return

        urls = [chan['url'] for chan in self.model.channels if 'url' in chan]
        if not urls:
            self.show_error("没有可检测的频道")
            return
            
        self.btn_validate.setText("停止检测")
        self.btn_validate.setStyleSheet(AppStyles.button_style(active=True))
        self.btn_validate.setChecked(True)
        self.filter_status_label.setText("有效性检测中...")
        
        try:
            # 从UI获取并发数设置并传递给验证器
            max_workers = self.thread_count_input.value()
            await self.validator.validate_playlist(urls, max_workers)
        except Exception as e:
            self.show_error(f"有效性检测失败: {str(e)}")
            self.btn_validate.setText("检测有效性")
            self.btn_validate.setStyleSheet(AppStyles.button_style())
            self.btn_validate.setChecked(False)

    @pyqtSlot(dict)
    def on_channel_validated(self, result: dict):
        """处理单个频道的验证结果"""
        url = result['url']
        valid = result['valid']
        latency = result.get('latency', 0.0)
        width = result.get('width', 0)
        height = result.get('height', 0)
        
        # 更新验证结果字典
        self.validation_results[url] = valid
        
        # 查找并更新对应的频道
        for i, chan in enumerate(self.model.channels):
            if chan['url'] == url:
                chan['valid'] = valid
                chan['validating'] = False  # 清除正在检测状态
                if valid:
                    chan['width'] = width
                    chan['height'] = height
                if valid:
                    chan['latency'] = latency
                
                # 触发UI更新
                index = self.model.index(i, 0)
                self.model.dataChanged.emit(index, index)
                break

    @pyqtSlot(dict)
    def on_validation_finished(self, result: dict):
        """处理验证完成事件"""
        # 保存验证结果和延迟信息到频道数据
        for chan in result['valid']:
            self.validation_results[chan['url']] = chan['valid']
            # 更新频道模型中的验证状态和延迟
            for i, model_chan in enumerate(self.model.channels):
                if model_chan['url'] == chan['url']:
                    model_chan['valid'] = chan['valid']
                    model_chan['validating'] = False  # 清除正在检测状态
                    if chan['valid'] and 'latency' in chan:
                        model_chan['latency'] = chan['latency']
                    # 触发UI更新
                    index = self.model.index(i, 0)
                    self.model.dataChanged.emit(index, index)
        
        # 更新无效频道状态
        for chan in result['invalid']:
            for i, model_chan in enumerate(self.model.channels):
                if model_chan['url'] == chan['url']:
                    model_chan['valid'] = False
                    model_chan['validating'] = False
                    model_chan['latency'] = 0.0
                    index = self.model.index(i, 0)
                    self.model.dataChanged.emit(index, index)
        
        valid_count = len(result['valid'])
        total = result['total']
        self.btn_validate.setText("检测有效性")
        self.btn_validate.setStyleSheet(AppStyles.button_style())
        self.filter_status_label.setText(f"检测完成 - 有效: {valid_count}/{total}")

    #加载用户配置
    def load_config(self) -> None:
        """加载用户配置"""
        try:
            # 窗口布局
            if geometry := self.config.config.get('UserPrefs', 'window_geometry', fallback=''):
                self.restoreGeometry(QtCore.QByteArray.fromHex(geometry.encode()))

            # 加载区域大小
            if splitter_sizes := self.config.config.get('UserPrefs', 'splitter_sizes', fallback=''):
                sizes = json.loads(splitter_sizes)
                if len(sizes) == 2:
                    self.left_splitter.setSizes(sizes[0])
                    self.right_splitter.setSizes(sizes[1])

            # 扫描历史
            scan_address = self.config.config.get('Scanner', 'scan_address', fallback='')
            timeout = self.config.config.getint('Scanner', 'timeout', fallback=10)
            thread_count = self.config.config.getint('Scanner', 'thread_count', fallback=10)
            user_agent = self.config.config.get('Scanner', 'user_agent', fallback='')
            referer = self.config.config.get('Scanner', 'referer', fallback='')
            
            logger.info(f"加载Scanner配置: address={scan_address}, timeout={timeout}, threads={thread_count}, user_agent={user_agent}, referer={referer}")
            
            self.ip_range_input.setText(scan_address)
            self.timeout_input.setValue(timeout)
            self.thread_count_input.setValue(thread_count)
            self.user_agent_input.setText(user_agent)
            self.referer_input.setText(referer)

            # 播放器设置
            hardware_accel = self.config.config.get('Player', 'hardware_accel', fallback='d3d11va')
            self.player.hw_accel = hardware_accel

        except Exception as e:
            logger.error(f"配置加载失败: {str(e)}")

    # 清理资源
    def _cleanup_resources(self) -> None:
        """清理资源"""
        asyncio.run(AsyncWorker.cancel_all())
        if hasattr(self, 'player'):
            self.player.force_stop()

    # 同步保存配置
    def _save_config_sync(self) -> None:
        """同步保存配置"""
        try:
            # 保存窗口几何信息
            self.config.config['UserPrefs']['window_geometry'] = self.saveGeometry().toHex().data().decode()
            
            # 保存扫描配置
            self.config.config['Scanner']['scan_address'] = self.ip_range_input.text()
            self.config.config['Scanner']['timeout'] = str(self.timeout_input.value())
            self.config.config['Scanner']['thread_count'] = str(self.thread_count_input.value())
            self.config.config['Scanner']['user_agent'] = self.user_agent_input.text()
            self.config.config['Scanner']['referer'] = self.referer_input.text()
            
            # 保存播放器配置
            self.config.config['Player']['hardware_accel'] = self.player.hw_accel
            self.config.config['Player']['volume'] = str(self.volume_slider.value())
            
            # 保存EPG配置（带详细日志）
            if hasattr(self, 'epg_manager'):
                logger.debug(f"开始保存EPG配置，epg_manager类型: {type(self.epg_manager)}")
                if hasattr(self.epg_manager, 'main_url'):
                    logger.debug(f"保存main_url: {self.epg_manager.main_url}")
                    self.config.config['EPG']['main_url'] = self.epg_manager.main_url
                    logger.info(f"EPG主URL已保存: {self.epg_manager.main_url}")
                else:
                    logger.warning("epg_manager没有main_url属性")
                
                if hasattr(self.epg_manager, 'backup_urls'):
                    logger.debug(f"保存backup_urls: {self.epg_manager.backup_urls}")
                    self.config.config['EPG']['backup_urls'] = ','.join(self.epg_manager.backup_urls)
                    logger.info(f"EPG备用URL已保存: {self.epg_manager.backup_urls}")
                else:
                    logger.warning("epg_manager没有backup_urls属性")
            
            # 保存频道列表状态
            if hasattr(self, 'model') and self.model.channels:
                self.config.config['ChannelList']['last_count'] = str(len(self.model.channels))
                self.config.config['ChannelList']['last_valid'] = str(sum(1 for c in self.model.channels if c.get('valid', False)))
            
            # 保存分隔条位置（仅在分隔条已初始化且有内容时保存）
            if (hasattr(self, 'left_splitter') and hasattr(self, 'right_splitter') and
                self.left_splitter.count() > 0 and self.right_splitter.count() > 0):
                left_sizes = self.left_splitter.sizes()
                right_sizes = self.right_splitter.sizes()
                if left_sizes and right_sizes:  # 确保尺寸列表不为空
                    self.config.config['UserPrefs']['splitter_sizes'] = json.dumps([left_sizes, right_sizes])
            
            self.config.save_prefs()
            logger.info("配置已保存 - 窗口几何: %s, 扫描配置: %s, 播放器配置: %s",
                       self.saveGeometry().toHex().data().decode()[:20] + "...",
                       f"address={self.ip_range_input.text()}, timeout={self.timeout_input.value()}",
                       f"hw_accel={self.player.hw_accel}, volume={self.volume_slider.value()}")
        except Exception as e:
            logger.error(f"保存配置失败: {str(e)}", exc_info=True)

    # 显示错误对话框
    @pyqtSlot(str)
    def show_error(self, msg: str) -> None:
        """显示错误对话框"""
        QMessageBox.critical(self, "操作错误", msg)

    # 更新状态栏
    @pyqtSlot(str)
    def update_status(self, msg: str) -> None:
        """更新状态栏"""
        self.statusBar().showMessage(msg)

    # 处理扫描成功结果（信号槽）
    @pyqtSlot(object)
    def handle_scan_success(self, result: Any) -> None:
        elapsed = self.scanner.get_elapsed_time()
        self.statusBar().showMessage(f"扫描完成，耗时 {elapsed:.1f} 秒")

    # # 处理扫描错误（异常信号槽）
    @pyqtSlot(Exception)
    def handle_scan_error(self, error: Exception) -> None:
        self.show_error(f"扫描错误: {str(error)}")

    # 处理扫描取消信号（信号槽）
    @pyqtSlot()
    def handle_scan_cancel(self) -> None:
        self.statusBar().showMessage("扫描已取消")

    # 处理播放成功信号（信号槽） 
    @pyqtSlot(object)
    def handle_play_success(self, result: Any) -> None:
        self.statusBar().showMessage("播放成功")

    # 处理播放错误（异常信号槽）
    @pyqtSlot(Exception)
    def handle_play_error(self, error: Exception) -> None:
        self.show_error(f"播放错误: {str(error)}")

    # 显示扫描设置对话框
    def show_scan_settings(self) -> None:
        """显示扫描设置对话框"""
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("扫描设置")
        layout = QtWidgets.QVBoxLayout()

        # 添加设置项
        timeout_label = QtWidgets.QLabel("超时时间（秒）：")
        self.timeout_input = QtWidgets.QSpinBox()
        self.timeout_input.setRange(1, 60)
        self.timeout_input.setValue(self.scanner._timeout)

        layout.addWidget(timeout_label)
        layout.addWidget(self.timeout_input)

        # 保存按钮
        save_btn = QtWidgets.QPushButton("保存")
        save_btn.clicked.connect(lambda: self.save_scan_settings(dialog))
        layout.addWidget(save_btn)

        dialog.setLayout(layout)
        dialog.exec()

    # 保存扫描设置
    def save_scan_settings(self, dialog: QtWidgets.QDialog) -> None:
        """保存扫描设置"""
        self.scanner._timeout = self.timeout_input.value()
        dialog.close()
        self.statusBar().showMessage("扫描设置已保存")

    # 管理 EPG 数据源
    def manage_epg(self) -> None:
        """管理 EPG 数据源"""
        try:
            dialog = QtWidgets.QDialog(self)
            dialog.setWindowTitle("EPG 管理")
            layout = QtWidgets.QVBoxLayout()

            # 主源设置
            main_source_label = QtWidgets.QLabel("主源 URL：")
            main_source_input = QtWidgets.QLineEdit()
            main_source_input.setText(self.config.config.get('EPG', 'main_url', fallback=''))

            # 备用源设置
            backup_sources_label = QtWidgets.QLabel("备用源 URL（多个用逗号分隔）：")
            backup_sources_input = QtWidgets.QLineEdit()
            backup_sources_input.setText(self.config.config.get('EPG', 'backup_urls', fallback=''))

            # 缓存TTL设置
            ttl_label = QtWidgets.QLabel("缓存有效期（秒）：")
            ttl_input = QtWidgets.QSpinBox()
            ttl_input.setRange(60, 86400)
            ttl_input.setValue(self.config.config.getint('EPG', 'cache_ttl', fallback=3600))

            # 保存按钮
            save_btn = QtWidgets.QPushButton("保存")
            def save_epg_settings():
                self.config.config['EPG']['main_url'] = main_source_input.text()
                self.config.config['EPG']['backup_urls'] = backup_sources_input.text()
                self.config.config['EPG']['cache_ttl'] = str(ttl_input.value())
                self.config.save_prefs()
                dialog.close()
                self.statusBar().showMessage("EPG 设置已保存")
            save_btn.clicked.connect(save_epg_settings)

            # 添加到布局
            layout.addWidget(main_source_label)
            layout.addWidget(main_source_input)
            layout.addWidget(backup_sources_label)
            layout.addWidget(backup_sources_input)
            layout.addWidget(ttl_label)
            layout.addWidget(ttl_input)
            layout.addWidget(save_btn)

            dialog.setLayout(layout)
            dialog.exec()
        except Exception as e:
            logger.error(f"EPG管理错误: {str(e)}")
            self.show_error(f"EPG管理错误: {str(e)}")



    # 显示全局设置对话框
    def show_settings(self) -> None:
        """显示全局设置对话框"""
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("全局设置")
        layout = QtWidgets.QVBoxLayout()

        # 添加硬件加速设置
        hw_accel_label = QtWidgets.QLabel("硬件加速：")
        self.hw_accel_combo = QtWidgets.QComboBox()
        self.hw_accel_combo.addItems(['auto', 'd3d11va', 'vaapi', 'vdpau', 'none'])
        self.hw_accel_combo.setCurrentText(self.player.hw_accel)

        layout.addWidget(hw_accel_label)
        layout.addWidget(self.hw_accel_combo)

        # 保存按钮
        save_btn = QtWidgets.QPushButton("保存")
        save_btn.clicked.connect(lambda: self.save_global_settings(dialog))
        layout.addWidget(save_btn)

        dialog.setLayout(layout)
        dialog.exec()

    # 保存全局设置
    def save_global_settings(self, dialog: QtWidgets.QDialog) -> None:
        """保存全局设置"""
        self.player.hw_accel = self.hw_accel_combo.currentText()
        dialog.close()
        self.statusBar().showMessage("全局设置已保存")

    # 设置音量
    def set_volume(self, volume: int) -> None:
        """设置音量"""
        self.player.set_volume(volume)

    # +++ 新增方法：加载旧列表 +++
    @pyqtSlot()
    def load_old_playlist(self):
        """加载旧播放列表文件"""
        path, _ = QFileDialog.getOpenFileName(
            self, "选择旧列表", "", "播放列表 (*.m3u *.m3u8 *.txt)"
        )
        if not path:
            return
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if path.endswith('.txt'):
                channels = PlaylistParser.parse_txt(content)
            else:
                channels = PlaylistParser.parse_m3u(content)
            
            # 转换为 {url: channel} 字典
            self.old_playlist = {chan['url']: chan for chan in channels}
            self.btn_match.setEnabled(True)
            self.match_status.setText(f"✔ 已加载旧列表({len(self.old_playlist)}个频道) - 点击'执行自动匹配'开始匹配")
            self.match_status.setStyleSheet("color: #4CAF50; font-weight: bold;")
        except Exception as e:
            self.show_error(f"加载旧列表失败: {str(e)}")

    # +++ 新增方法：执行自动匹配 +++
    async def run_auto_match(self):
        """执行自动匹配任务"""
        try:
            if not hasattr(self, 'old_playlist') or not self.old_playlist:
                self.match_status.setText("请先加载旧列表")
                return
            
            total = len(self.model.channels)
            self.match_progress.setMaximum(total)
            self.match_progress.setValue(0)
            
            for row in range(total):
                try:
                    chan = self.model.channels[row]
                    
                    # 1. 匹配旧列表
                    if chan['url'] in self.old_playlist:
                        old_chan = self.old_playlist[chan['url']]
                        self._apply_match(row, old_chan, 'old')
                    
                    # 2. 匹配EPG
                    if hasattr(self, 'epg_manager'):
                        epg_names = self.epg_manager.match_channel_name(chan.get('name', ''))
                        if epg_names:
                            # 更新频道名称
                            self.model.channels[row]['name'] = epg_names[0]
                            self._apply_match(row, {'name': epg_names[0]}, 'epg')
                    
                    # 更新进度
                    self.match_progress.setValue(row + 1)
                    self.match_status.setText(f"匹配中: {row+1}/{total} ({(row+1)/total*100:.1f}%)")
                    await asyncio.sleep(0.01)  # 释放事件循环
                except asyncio.CancelledError:
                    self.match_status.setText("匹配已取消")
                    return
                except Exception as e:
                    logger.error(f"匹配第{row+1}行时出错: {str(e)}")
            
            
            matched_count = sum(1 for chan in self.model.channels if 'old_name' in chan or 'epg_name' in chan)
            # 统计匹配结果
            old_matched = sum(1 for chan in self.model.channels if 'old_name' in chan)
            epg_matched = sum(1 for chan in self.model.channels if 'epg_name' in chan)
            conflict_count = sum(1 for chan in self.model.channels 
                                if 'old_name' in chan and 'epg_name' in chan 
                                and chan['old_name'] != chan['epg_name'])
            
            stats = (f"✔ 匹配完成\n"
                    f"• 共匹配 {matched_count}/{total} 个频道\n"
                    f"• 旧列表匹配: {old_matched}\n"
                    f"• EPG匹配: {epg_matched}\n"
                    f"• 冲突: {conflict_count}")
            
            self.match_status.setText(stats)
            self.match_status.setStyleSheet("color: #2196F3; font-weight: bold;")
            if self.cb_auto_save.isChecked():
                self.save_playlist()
        except asyncio.CancelledError:
            self.match_status.setText("匹配已取消")
        except Exception as e:
            self.show_error(f"自动匹配失败: {str(e)}")
            self.match_status.setText("匹配失败")

    # +++ 新增方法：应用匹配结果 +++
    def _apply_match(self, row, data, source):
        """更新指定行的数据和颜色"""
        index = self.model.index(row, 0)
        chan = self.model.channels[row]
        
        # 确定颜色
        if source == 'old':
            color = QtGui.QColor(255, 255, 200)  # 浅黄：旧列表匹配
            # 保留原始名称
            self.model.channels[row]['old_name'] = chan['name']
            # 更新名称
            self.model.channels[row]['name'] = data['name']
        else:
            is_conflict = ('old_name' in chan and data['name'] != chan['old_name'])
            color = QtGui.QColor(255, 200, 200) if is_conflict else QtGui.QColor(200, 255, 200)
            # 更新名称
            self.model.channels[row]['name'] = data['name']
        
        # 更新UI
        self.model.setData(index, data['name'], Qt.ItemDataRole.DisplayRole)
        self.model.setData(index, color, Qt.ItemDataRole.BackgroundRole)
        self.model.dataChanged.emit(index, index)

# 程序入口
if __name__ == "__main__":
    # 禁用QT屏幕相关的警告
    os.environ["QT_LOGGING_RULES"] = "qt.qpa.*=false"
    app = QtWidgets.QApplication(sys.argv)
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    main_window = MainWindow()
    main_window.show()

    with loop:
        sys.exit(loop.run_forever())
