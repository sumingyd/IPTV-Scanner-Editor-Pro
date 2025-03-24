# ================= 标准库导入 =================
import asyncio
import datetime
import platform
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any

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

logger = setup_logger('Main')


class ChannelListModel(QtCore.QAbstractTableModel):
    def __init__(self, data: Optional[List[Dict]] = None):
        super().__init__()
        self.channels = data if data is not None else []
        self.headers = ["频道名称", "分辨率", "URL", "分组"]

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
        elif role == Qt.ItemDataRole.UserRole:
            return self.channels[index.row()]
        return None

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self.channels)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self.headers)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.headers[section]
        return None

class MainWindow(QtWidgets.QMainWindow):
    # 定义信号（必须在类的作用域内定义）
    epg_progress_updated = QtCore.pyqtSignal(str)  # 用于更新进度提示
    def __init__(self):
        super().__init__()
        self.config = ConfigHandler()
        self.scanner = StreamScanner()
        self.epg_manager = EPGManager()
        self.player = VLCPlayer()
        self.playlist_handler = PlaylistHandler()
        self.converter = PlaylistConverter(self.epg_manager)
        self.playlist_source = None  # 播放列表来源：None/file/scan

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

    def eventFilter(self, source, event: QtCore.QEvent) -> bool:
        """事件过滤器处理焦点事件（最终版）"""
        if (source is self.name_edit and 
            event.type() == QtCore.QEvent.Type.FocusIn):
            self.update_completer_model()
        return super().eventFilter(source, event)

    def _init_ui(self) -> None:
        """初始化用户界面"""
        self.setWindowTitle("IPTV管理工具")
        self.resize(1200, 800)

        # 主布局
        main_widget = QtWidgets.QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QtWidgets.QHBoxLayout(main_widget)

        # 左侧面板
        self.left_splitter = QtWidgets.QSplitter(Qt.Orientation.Vertical)
        self._setup_scan_panel(self.left_splitter)
        self._setup_channel_list(self.left_splitter)

        # 右侧面板
        self.right_splitter = QtWidgets.QSplitter(Qt.Orientation.Vertical)
        self._setup_player_panel(self.right_splitter)
        self._setup_edit_panel(self.right_splitter)

        # 添加分隔线样式
        self._setup_splitter_handle(self.left_splitter)
        self._setup_splitter_handle(self.right_splitter)

        main_layout.addWidget(self.left_splitter)
        main_layout.addWidget(self.right_splitter)

        # 初始化菜单和工具栏
        self._setup_menubar()
        self._setup_toolbar()

        # 确保状态栏显示
        self.statusBar().show()
        self.statusBar().showMessage("程序已启动")

    def _setup_splitter_handle(self, splitter: QtWidgets.QSplitter) -> None:
        """为 QSplitter 设置分隔线样式"""
        # 设置分隔线的样式表
        if splitter.orientation() == QtCore.Qt.Orientation.Vertical:
            # 垂直分隔线：设置高度和背景颜色
            splitter.setStyleSheet("""
                QSplitter::handle {
                    background-color: rgba(245, 166, 35, 128);  /* 最后一位是透明度(0-255) */
                    height: 2px;           /* 分隔线高度 */
                }
            """)
        else:
            # 水平分隔线：设置宽度和背景颜色
            splitter.setStyleSheet("""
                QSplitter::handle {
                    background-color: rgba(245, 166, 35, 128);  /* 最后一位是透明度(0-255) */
                    width: 2px;            /* 分隔线宽度 */
                }
            """)

    def _setup_scan_panel(self, parent: QtWidgets.QSplitter) -> None:
        """配置扫描面板"""
        scan_group = QtWidgets.QGroupBox("扫描设置")
        scan_layout = QtWidgets.QFormLayout()

        self.ip_range_input = QtWidgets.QLineEdit()
        self.scan_progress = QtWidgets.QProgressBar()

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
        thread_layout.addWidget(self.thread_count_input)

        # 开始扫描和停止扫描按钮
        scan_btn = QtWidgets.QPushButton("开始扫描")
        scan_btn.clicked.connect(self.start_scan)
        stop_btn = QtWidgets.QPushButton("停止扫描")
        stop_btn.clicked.connect(self.stop_scan)

        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addWidget(scan_btn)
        button_layout.addWidget(stop_btn)

        scan_layout.addRow("地址格式：", QtWidgets.QLabel("示例：http://192.168.1.1:1234/rtp/10.10.[1-20].[1-20]:5002   [1-20]表示范围"))
        scan_layout.addRow("输入地址：", self.ip_range_input)
        scan_layout.addRow("超时时间：", timeout_layout)
        scan_layout.addRow("线程数：", thread_layout)
        scan_layout.addRow("进度：", self.scan_progress)
        scan_layout.addRow(button_layout)  # 添加按钮布局

        scan_group.setLayout(scan_layout)
        parent.addWidget(scan_group)

    def _setup_channel_list(self, parent: QtWidgets.QSplitter) -> None:
        """配置频道列表"""
        list_group = QtWidgets.QGroupBox("频道列表")
        list_layout = QtWidgets.QVBoxLayout()

        self.channel_list = QtWidgets.QTableView()
        self.channel_list.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.channel_list.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.channel_list.horizontalHeader().setStretchLastSection(True)
        self.channel_list.verticalHeader().setVisible(False)
        self.model = ChannelListModel()
        self.channel_list.setModel(self.model)

        list_layout.addWidget(self.channel_list)
        list_group.setLayout(list_layout)
        parent.addWidget(list_group)

    def _setup_player_panel(self, parent: QtWidgets.QSplitter) -> None:
        """配置播放器面板"""
        player_group = QtWidgets.QGroupBox("视频播放")
        player_layout = QtWidgets.QVBoxLayout()

        # 播放器控件
        player_layout.addWidget(self.player)

        # 控制按钮
        control_layout = QtWidgets.QHBoxLayout()

        self.pause_btn = QtWidgets.QPushButton("播放")
        self.pause_btn.clicked.connect(self.player.toggle_pause)

        self.stop_btn = QtWidgets.QPushButton("停止")
        self.stop_btn.clicked.connect(self.player.stop)

        control_layout.addWidget(self.pause_btn)
        control_layout.addWidget(self.stop_btn)

        player_layout.addLayout(control_layout)

        # 音量控制
        volume_layout = QtWidgets.QHBoxLayout()

        self.volume_slider = QtWidgets.QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(50)  # 默认音量
        self.volume_slider.valueChanged.connect(self.set_volume)

        volume_layout.addWidget(QtWidgets.QLabel("音量："))
        volume_layout.addWidget(self.volume_slider)

        player_layout.addLayout(volume_layout)

        player_group.setLayout(player_layout)
        parent.addWidget(player_group)

    def _setup_edit_panel(self, parent: QtWidgets.QSplitter) -> None:
        """配置编辑面板，修复频道名称输入框的自动补全功能"""
        edit_group = QtWidgets.QGroupBox("频道编辑")
        edit_layout = QtWidgets.QFormLayout()

        self.name_edit = QtWidgets.QLineEdit()
        self.name_edit.setPlaceholderText("输入频道名称...")

        # 修复自动补全功能
        self.epg_completer = QtWidgets.QCompleter()
        self.epg_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)  # 不区分大小写
        self.epg_completer.setFilterMode(Qt.MatchFlag.MatchContains)  # 支持模糊匹配
        self.epg_completer.setCompletionMode(QtWidgets.QCompleter.CompletionMode.PopupCompletion)  # 显示下拉列表
        self.epg_completer.setMaxVisibleItems(10)  # 最多显示10个匹配项
        self.name_edit.setCompleter(self.epg_completer)

        # 绑定文本变化事件
        self.name_edit.textChanged.connect(self.on_text_changed)

        self.group_combo = QtWidgets.QComboBox()
        self.group_combo.addItems(["未分类", "央视", "卫视", "本地", "高清频道", "测试频道"])

        edit_layout.addRow("频道名称：", self.name_edit)
        edit_layout.addRow("分组分类：", self.group_combo)

        save_btn = QtWidgets.QPushButton("保存修改")
        save_btn.clicked.connect(self.save_channel_edit)
        edit_layout.addRow(save_btn)

        edit_group.setLayout(edit_layout)
        parent.addWidget(edit_group)

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

        # 扫描
        scan_action = QAction(load_icon("icons/scan.png"), "扫描频道", self)
        scan_action.triggered.connect(self.start_scan)
        toolbar.addAction(scan_action)

        # 加载 EPG 缓存
        load_epg_action = QAction(load_icon("icons/load.png"), "加载 EPG", self)
        load_epg_action.triggered.connect(self.load_epg_cache)
        toolbar.addAction(load_epg_action)

        # 更新 EPG 数据
        refresh_epg_action = QAction(load_icon("icons/refresh.png"), "更新 EPG", self)
        refresh_epg_action.triggered.connect(self.refresh_epg)
        toolbar.addAction(refresh_epg_action)

        # EPG 管理
        epg_manage_action = QAction(load_icon("icons/settings.png"), "EPG 管理", self)
        epg_manage_action.triggered.connect(self.manage_epg)
        toolbar.addAction(epg_manage_action)

        # 关于
        about_action = QAction(load_icon("icons/info.png"), "关于", self) 
        about_action.triggered.connect(self._show_about_dialog)
        toolbar.addAction(about_action)

        # 添加分隔线保持布局美观
        toolbar.addSeparator()

    def _show_about_dialog(self):
        """显示关于对话框"""
        about_text = f'''
        <b>IPTV 专业扫描器</b>
        <p style="line-height: 1.5;">
            版本：2.1.0<br>
            编译日期：{datetime.date.today().strftime("%Y-%m-%d")}<br>
            QT版本：{QtCore.qVersion()}
        </p>
        <p>功能特性：</p>
        <ul style="margin-left: 20px;">
            <li>支持 HTTP/UDP/RTP/RTSP 协议检测</li>
            <li> EPG 信息保存与加载</li>
            <li>多线程高效扫描引擎</li>
            <li>支持 M3U/M3U8/TXT 播放列表格式</li>
            <li>编辑频道名匹配EGP频道名功能</li>
            <li>实时流媒体可用性检测</li>
            <li>硬件加速视频播放</li>
            <li>快捷键设置</li>
            <li>频道分组与批量编辑</li>
        </ul>
        <p>快捷键：</p>
        <ul style="margin-left: 20px;">
            <li>Ctrl+O - 打开播放列表</li>
            <li>Ctrl+S - 保存播放列表</li>
            <li>Ctrl+Q - 退出程序</li>
            <li>空格键 - 暂停/继续播放</li>
        </ul>
        <p>程序由 deepseek 提供代码</p>
        <p>作者QQ:331874545</p>
        '''
        
        dialog = QtWidgets.QMessageBox(self)
        dialog.setWindowTitle("关于")
        # 确保存在 icons/logo.png
        dialog.setIconPixmap(QtGui.QPixmap(str(Path(__file__).parent / "icons/logo.png")).scaled(64, 64))
        dialog.setTextFormat(QtCore.Qt.TextFormat.RichText)
        dialog.setText(about_text)
        dialog.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Ok)
        dialog.exec()

    def _connect_signals(self) -> None:
        """连接信号与槽"""
        self.scanner.progress_updated.connect(self.update_progress)
        self.scanner.scan_finished.connect(self.handle_scan_results)
        self.scanner.channel_found.connect(self.handle_channel_found)
        self.scanner.error_occurred.connect(self.show_error)
        self.channel_list.selectionModel().currentChanged.connect(self.on_channel_selected)
        self.player.state_changed.connect(self._handle_player_state)

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

    @pyqtSlot()
    def start_scan(self) -> None:
        """启动扫描任务"""
        ip_range = self.ip_range_input.text().strip()
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

        # 确保传入的是一个协程
        self.scan_worker = AsyncWorker(self.scanner.start_scan(ip_range))
        self.scan_worker.finished.connect(self.handle_scan_success)
        self.scan_worker.error.connect(self.handle_scan_error)
        self.scan_worker.cancelled.connect(self.handle_scan_cancel)
        asyncio.create_task(self.scan_worker.run())

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

    async def _async_scan(self, ip_range: str) -> None:
        """执行异步扫描"""
        await self.scanner.scan_task(ip_range)

    @pyqtSlot(int, str)
    def update_progress(self, percent: int, msg: str) -> None:
        """更新扫描进度"""
        self.scan_progress.setValue(percent)
        # 强制更新扫描状态信息，确保不会被其他消息覆盖
        self.statusBar().showMessage(msg)
        # 标记当前处于扫描状态
        self._last_scan_status = msg

    @pyqtSlot(dict)
    def handle_channel_found(self, channel: Dict) -> None:
        """处理单个频道发现"""
        # 检查是否已存在相同URL的频道
        if not any(c['url'] == channel['url'] for c in self.model.channels):
            # 在主线程中执行UI更新
            QtCore.QMetaObject.invokeMethod(self, "_add_channel", 
                QtCore.Qt.ConnectionType.QueuedConnection,
                QtCore.Q_ARG(dict, channel))

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

    @pyqtSlot(list)
    def handle_scan_results(self, channels: List[Dict]) -> None:
        """处理最终扫描结果"""
        elapsed = self.scanner.get_elapsed_time()
        self.statusBar().showMessage(f"扫描完成，共发现 {len(channels)} 个有效频道 - 总耗时: {elapsed:.1f}秒")
        
        # 自动选择第一个频道但不自动播放
        if channels:
            first_index = self.model.index(0, 0)
            self.channel_list.setCurrentIndex(first_index)
            # 手动触发状态更新
            self._handle_player_state("准备播放")

    @pyqtSlot()
    def on_channel_selected(self) -> None:
        """处理频道选择事件"""
        index = self.channel_list.currentIndex()
        if not index.isValid():
            return

        chan = self.model.channels[index.row()]
        self.name_edit.setText(chan.get('name', '未命名频道'))
        self.group_combo.setCurrentText(chan.get('group', '未分类'))

        if url := chan.get('url'):
            asyncio.create_task(self.safe_play(url))

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

    def stop_play(self):
        """统一调用播放器的停止方法"""
        try:
            if hasattr(self, 'player') and self.player:
                self.player.stop()
        except Exception as e:
            self.show_error(f"停止失败: {str(e)}")

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

        self.model.channels[index.row()].update({
            'name': new_name,
            'group': new_group
        })
        self.model.dataChanged.emit(index, index)

        # 自动跳转到下一个频道
        next_index = index.siblingAtRow(index.row() + 1)
        if next_index.isValid():
            self.channel_list.setCurrentIndex(next_index)

    @pyqtSlot()
    def load_epg_cache(self) -> None:
        """异步加载 EPG 缓存"""
        self._start_epg_task(is_refresh=False)

    @pyqtSlot()
    def refresh_epg(self) -> None:
        """异步更新 EPG 数据"""
        self._start_epg_task(is_refresh=True)

    def _start_epg_task(self, is_refresh: bool) -> None:
        """启动 EPG 任务"""
        message = "正在加载 EPG 缓存..." if not is_refresh else "正在更新 EPG 数据..."
        self.epg_progress_updated.emit(message)
        self.scan_worker = AsyncWorker(self._async_load_epg(is_refresh))
        self.scan_worker.finished.connect(self.handle_epg_load_success)
        self.scan_worker.error.connect(self.handle_epg_load_error)
        self.scan_worker.start()  # 使用 start 方法启动任务

    async def _async_load_epg(self, is_refresh: bool) -> None:
        """异步加载或刷新 EPG 数据"""
        try:
            success = await self.epg_manager.load_epg(is_refresh, self.epg_progress_updated.emit)
            message = "EPG 数据加载成功" if success else "EPG 数据加载失败"
            if success:
                self.epg_progress_updated.emit("EPG 数据加载完成，正在更新界面...")
                self.update_completer_model()
            self.epg_progress_updated.emit(message)
        except Exception as e:
            logger.error(f"EPG 操作失败: {str(e)}")
            self.epg_progress_updated.emit(f"EPG 操作失败: {str(e)}")

    @pyqtSlot()
    def handle_epg_load_success(self) -> None:
        """EPG 加载成功后的处理"""
        self.statusBar().showMessage("EPG 数据加载完成")
        self.update_completer_model()  # 确保界面更新

    @pyqtSlot(Exception)
    def handle_epg_load_error(self, error: Exception) -> None:
        """EPG 加载失败后的处理"""
        self.show_error(f"EPG 加载失败: {str(error)}")
        self.statusBar().showMessage("EPG 加载失败")

    def on_text_changed(self, text: str) -> None:
        """输入框文本变化处理（优化版）"""
        # 立即触发补全更新
        self.update_completer_model()
        # 启动防抖定时器（后续输入防抖）
        self.debounce_timer.start(300)

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

    def _get_matching_channel_names(self, text: str) -> List[str]:
        """获取匹配的频道名称"""
        try:
            raw_names = self.epg_manager.match_channel_name(text)
            return sorted(list(set(raw_names)), key=lambda x: (len(x), x))
        except Exception as e:
            logger.error(f"EPG查询失败: {str(e)}")
            return []

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

    def closeEvent(self, event: QCloseEvent):
        try:
            # 先停止所有异步任务
            if hasattr(self, 'scan_worker') and self.scan_worker:
                self.scan_worker.cancel()
            if hasattr(self, 'play_worker') and self.play_worker:
                self.play_worker.cancel()
                
            # 停止播放器
            if hasattr(self, 'player') and self.player:
                self.player.force_stop()
                
            # 如果播放列表来自文件且有修改，提示保存
            if self.playlist_source == 'file' and self.model.channels:
                reply = QMessageBox.question(
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
                
            # 保存配置
            self._save_config_sync()
            
            # 保存区域大小
            self.config.config['UserPrefs']['left_splitter_sizes'] = ','.join(map(str, self.left_splitter.sizes()))
            self.config.config['UserPrefs']['right_splitter_sizes'] = ','.join(map(str, self.right_splitter.sizes()))
            self.config.save_prefs()
            
            # 确保所有异步任务完成
            async def _final_cleanup():
                await asyncio.sleep(0.1)  # 给任务一些时间完成
                super().closeEvent(event)
                
            asyncio.create_task(_final_cleanup())
        except Exception as e:
            logger.error(f"关闭异常: {str(e)}")
            event.ignore()

    def load_config(self) -> None:
        """加载用户配置"""
        try:
            # 窗口布局
            if geometry := self.config.config.get('UserPrefs', 'window_geometry', fallback=''):
                self.restoreGeometry(QtCore.QByteArray.fromHex(geometry.encode()))

            # 加载区域大小
            if left_splitter_sizes := self.config.config.get('UserPrefs', 'left_splitter_sizes', fallback=''):
                sizes = list(map(int, left_splitter_sizes.split(',')))
                self.left_splitter.setSizes(sizes)

            if right_splitter_sizes := self.config.config.get('UserPrefs', 'right_splitter_sizes', fallback=''):
                sizes = list(map(int, right_splitter_sizes.split(',')))
                self.right_splitter.setSizes(sizes)

            # 扫描历史
            self.ip_range_input.setText(
                self.config.config.get('Scanner', 'last_range', fallback='')
            )

            # 播放器设置
            hardware_accel = self.config.config.get(
                'Player', 'hardware_accel', fallback='d3d11va'
            )
            self.player.hw_accel = 'none'  # 硬件加速设置

        except Exception as e:
            logger.error(f"配置加载失败: {str(e)}")

    def _cleanup_resources(self) -> None:
        """清理资源"""
        AsyncWorker.cancel_all()
        if hasattr(self, 'player'):
            self.player.force_stop()

    def _save_config_sync(self) -> None:
        """同步保存配置"""
        self.config.config['UserPrefs']['window_geometry'] = self.saveGeometry().toHex().data().decode()
        self.config.config['Scanner']['last_range'] = self.ip_range_input.text()
        self.config.save_prefs()

    @pyqtSlot(str)
    def show_error(self, msg: str) -> None:
        """显示错误对话框"""
        QMessageBox.critical(self, "操作错误", msg)

    @pyqtSlot(str)
    def update_status(self, msg: str) -> None:
        """更新状态栏"""
        self.statusBar().showMessage(msg)

    # 信号处理方法
    @pyqtSlot(object)
    def handle_scan_success(self, result: Any) -> None:
        elapsed = self.scanner.get_elapsed_time()
        self.statusBar().showMessage(f"扫描完成，耗时 {elapsed:.1f} 秒")

    @pyqtSlot(Exception)
    def handle_scan_error(self, error: Exception) -> None:
        self.show_error(f"扫描错误: {str(error)}")

    @pyqtSlot()
    def handle_scan_cancel(self) -> None:
        self.statusBar().showMessage("扫描已取消")

    @pyqtSlot(object)
    def handle_play_success(self, result: Any) -> None:
        self.statusBar().showMessage("播放成功")

    @pyqtSlot(Exception)
    def handle_play_error(self, error: Exception) -> None:
        self.show_error(f"播放错误: {str(error)}")

    # 辅助功能
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

    def save_scan_settings(self, dialog: QtWidgets.QDialog) -> None:
        """保存扫描设置"""
        self.scanner._timeout = self.timeout_input.value()
        dialog.close()
        self.statusBar().showMessage("扫描设置已保存")

    def manage_epg(self) -> None:
        """管理 EPG 数据源"""
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("EPG 管理")
        layout = QtWidgets.QVBoxLayout()

        # 主源设置
        main_source_label = QtWidgets.QLabel("主源 URL：")
        self.main_source_input = QtWidgets.QLineEdit()
        self.main_source_input.setText(self.epg_manager.epg_sources['main'])

        # 备用源设置
        backup_sources_label = QtWidgets.QLabel("备用源 URL（多个用逗号分隔）：")
        self.backup_sources_input = QtWidgets.QLineEdit()
        self.backup_sources_input.setText(','.join(self.epg_manager.epg_sources['backups']))

        # 保存按钮
        save_btn = QtWidgets.QPushButton("保存")
        save_btn.clicked.connect(lambda: self.save_epg_settings(dialog))

        # 添加到布局
        layout.addWidget(main_source_label)
        layout.addWidget(self.main_source_input)
        layout.addWidget(backup_sources_label)
        layout.addWidget(self.backup_sources_input)
        layout.addWidget(save_btn)

        dialog.setLayout(layout)
        dialog.exec()

    def save_epg_settings(self, dialog: QtWidgets.QDialog) -> None:
        """保存 EPG 设置"""
        self.epg_manager.epg_sources['main'] = self.main_source_input.text()
        self.epg_manager.epg_sources['backups'] = [
            url.strip() for url in self.backup_sources_input.text().split(',') if url.strip()
        ]
        dialog.close()
        self.statusBar().showMessage("EPG 设置已保存")

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

    def save_global_settings(self, dialog: QtWidgets.QDialog) -> None:
        """保存全局设置"""
        self.player.hw_accel = self.hw_accel_combo.currentText()
        dialog.close()
        self.statusBar().showMessage("全局设置已保存")

    def set_volume(self, volume: int) -> None:
        """设置音量"""
        self.player.set_volume(volume)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    main_window = MainWindow()
    main_window.show()

    with loop:
        sys.exit(loop.run_forever())
