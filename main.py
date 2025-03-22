import sys
import asyncio
import platform
from pathlib import Path
from typing import Optional, List, Dict, Any
from PyQt6 import QtCore, QtWidgets
from PyQt6.QtCore import Qt, pyqtSlot, QModelIndex
from PyQt6.QtGui import QCloseEvent, QAction, QKeySequence, QIcon
from PyQt6.QtWidgets import QFileDialog, QMessageBox
from scanner import StreamScanner
from epg_manager import EPGManager
from playlist_io import PlaylistParser, PlaylistConverter, PlaylistHandler
from player import VLCPlayer
from utils import ConfigHandler, setup_logger
import qasync
from async_utils import AsyncWorker

logger = setup_logger('Main')


class ChannelListModel(QtCore.QAbstractListModel):
    def __init__(self, data: Optional[List[Dict]] = None):
        super().__init__()
        self.channels = data if data is not None else []

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if role == Qt.ItemDataRole.DisplayRole:
            chan = self.channels[index.row()]
            return f"{chan.get('name', '未命名频道')} [{chan.get('width', 0)}x{chan.get('height', 0)}]"
        elif role == Qt.ItemDataRole.UserRole:
            return self.channels[index.row()]
        return None

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self.channels)


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

    def _init_ui(self) -> None:
        """初始化用户界面"""
        self.setWindowTitle("IPTV管理工具")
        self.resize(1200, 800)

        # 主布局
        main_widget = QtWidgets.QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QtWidgets.QHBoxLayout(main_widget)

        # 左侧面板
        left_panel = QtWidgets.QSplitter(Qt.Orientation.Vertical)
        self._setup_scan_panel(left_panel)
        self._setup_channel_list(left_panel)

        # 右侧面板
        right_panel = QtWidgets.QSplitter(Qt.Orientation.Vertical)
        self._setup_player_panel(right_panel)
        self._setup_edit_panel(right_panel)

        main_layout.addWidget(left_panel)
        main_layout.addWidget(right_panel)

        # 初始化菜单和工具栏
        self._setup_menubar()
        self._setup_toolbar()

        # 确保状态栏显示
        self.statusBar().show()
        self.statusBar().showMessage("程序已启动")

    def _setup_scan_panel(self, parent: QtWidgets.QSplitter) -> None:
        """配置扫描面板"""
        scan_group = QtWidgets.QGroupBox("扫描设置")
        scan_layout = QtWidgets.QFormLayout()

        self.ip_range_input = QtWidgets.QLineEdit()
        self.timeout_input = QtWidgets.QSpinBox()  # 超时时间输入框
        self.timeout_input.setRange(1, 60)  # 超时时间范围：1 到 60 秒
        self.timeout_input.setValue(10)  # 默认超时时间：10 秒
        self.thread_count_input = QtWidgets.QSpinBox()  # 线程数输入框
        self.thread_count_input.setRange(1, 100)  # 线程数范围：1 到 100
        self.thread_count_input.setValue(10)  # 默认线程数：10
        self.scan_progress = QtWidgets.QProgressBar()
        scan_btn = QtWidgets.QPushButton("开始扫描")
        scan_btn.clicked.connect(self.start_scan)
        stop_btn = QtWidgets.QPushButton("停止扫描")  # 停止扫描按钮
        stop_btn.clicked.connect(self.stop_scan)

        scan_layout.addRow("URL格式：", QtWidgets.QLabel("示例：http://192.168.50.1:20231/rtp/239.21.[1-20].[1-20]:5002"))
        scan_layout.addRow("输入URL：", self.ip_range_input)
        scan_layout.addRow("超时时间（秒）：", self.timeout_input)  # 添加超时时间输入框
        scan_layout.addRow("线程数：", self.thread_count_input)  # 添加线程数输入框
        scan_layout.addRow("进度：", self.scan_progress)
        scan_layout.addRow(scan_btn, stop_btn)  # 添加开始和停止按钮

        scan_group.setLayout(scan_layout)
        parent.addWidget(scan_group)

    def _setup_channel_list(self, parent: QtWidgets.QSplitter) -> None:
        """配置频道列表"""
        list_group = QtWidgets.QGroupBox("频道列表")
        list_layout = QtWidgets.QVBoxLayout()

        self.channel_list = QtWidgets.QListView()
        self.channel_list.setSelectionMode(
            QtWidgets.QListView.SelectionMode.ExtendedSelection
        )
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

        self.pause_btn = QtWidgets.QPushButton("暂停/继续")
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

        # 工具菜单
        tool_menu = menubar.addMenu("工具(&T)")
        tool_menu.addAction("扫描设置(&S)", self.show_scan_settings)
        tool_menu.addAction("EPG管理(&E)", self.manage_epg)

    def _setup_toolbar(self) -> None:
        """初始化工具栏，区分加载 EPG 和更新 EPG 按钮"""
        toolbar = self.addToolBar("主工具栏")
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)  # 图标下方显示文字
        toolbar.setMovable(False)

        # 修复图标加载问题
        def load_icon(path: str) -> QIcon:
            icon_path = Path(__file__).parent / path
            if not icon_path.exists():
                return QIcon()  # 返回空图标
            icon = QIcon(str(icon_path))
            if icon.isNull():
                return QIcon()  # 返回空图标
            return icon

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

        # 停止
        stop_action = QAction(load_icon("icons/stop.png"), "停止播放", self)
        stop_action.triggered.connect(self.stop_play)
        toolbar.addAction(stop_action)

        # 设置
        settings_action = QAction(load_icon("icons/settings.png"), "设置", self)
        settings_action.triggered.connect(self.show_settings)
        toolbar.addAction(settings_action)

    def _connect_signals(self) -> None:
        """连接信号与槽"""
        self.scanner.progress_updated.connect(self.update_progress)
        self.scanner.scan_finished.connect(self.handle_scan_results)
        self.scanner.error_occurred.connect(self.show_error)
        self.channel_list.selectionModel().currentChanged.connect(self.on_channel_selected)
        self.player.state_changed.connect(self.update_status)

    @pyqtSlot()
    def start_scan(self) -> None:
        """启动扫描任务"""
        ip_range = self.ip_range_input.text().strip()
        if not ip_range:
            self.show_error("请输入有效的频道地址")
            return

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
        self.scanner.stop_scan()
        self.statusBar().showMessage("扫描已停止")

    async def _async_scan(self, ip_range: str) -> None:
        """执行异步扫描"""
        await self.scanner.scan_task(ip_range)

    @pyqtSlot(int, str)
    def update_progress(self, percent: int, msg: str) -> None:
        """更新扫描进度"""
        self.scan_progress.setValue(percent)
        self.statusBar().showMessage(f"{msg} ({percent}%)")

    @pyqtSlot(list)
    def handle_scan_results(self, channels: List[Dict]) -> None:
        """处理扫描结果"""
        self.model.channels.extend(channels)
        self.model.layoutChanged.emit()
        self.statusBar().showMessage(f"发现 {len(channels)} 个有效频道")

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
            if self.play_worker and not self.play_worker.is_finished():
                self.play_worker.cancel()

            self.play_worker = AsyncWorker(self.player.async_play(url))  # 调用 player 的 async_play 方法
            self.play_worker.finished.connect(self.handle_play_success)
            self.play_worker.error.connect(self.handle_play_error)
            await self.play_worker.run()
        except Exception as e:
            self.show_error(f"播放失败: {str(e)}")

    @pyqtSlot()
    def stop_play(self) -> None:
        """停止播放"""
        if self.play_worker:
            self.play_worker.cancel()
        self.player.stop()
        self.statusBar().showMessage("播放已停止")

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

    async def _load_epg_data(self, is_refresh: bool) -> None:
        """加载或刷新 EPG 数据"""
        try:
            if is_refresh:
                success = await self.epg_manager.refresh_epg()
                message = "EPG 数据更新成功" if success else "EPG 更新失败，请检查网络连接"
            else:
                success = self.epg_manager.load_cached_epg()
                message = "EPG 缓存已加载" if success else "EPG 缓存加载失败"

            if success:
                self.update_completer_model()
            self.statusBar().showMessage(message)
        except Exception as e:
            logger.error(f"EPG 操作失败: {str(e)}")
            self.show_error(f"EPG 操作失败: {str(e)}")

    @pyqtSlot()
    def load_epg_cache(self) -> None:
        """异步加载 EPG 缓存"""
        self.epg_progress_updated.emit("正在加载 EPG 缓存...")
        self.scan_worker = AsyncWorker(self._async_load_epg(is_refresh=False))
        self.scan_worker.finished.connect(self.handle_epg_load_success)
        self.scan_worker.error.connect(self.handle_epg_load_error)
        asyncio.create_task(self.scan_worker.run())

    @pyqtSlot()
    def refresh_epg(self) -> None:
        """异步更新 EPG 数据"""
        self.epg_progress_updated.emit("正在更新 EPG 数据...")
        self.scan_worker = AsyncWorker(self._async_load_epg(is_refresh=True))
        self.scan_worker.finished.connect(self.handle_epg_load_success)
        self.scan_worker.error.connect(self.handle_epg_load_error)
        asyncio.create_task(self.scan_worker.run())

    async def _async_load_epg(self, is_refresh: bool) -> None:
        """异步加载或刷新 EPG 数据"""
        try:
            if is_refresh:
                success = await self.epg_manager.refresh_epg()
                message = "EPG 数据更新成功" if success else "EPG 更新失败，请检查网络连接"
            else:
                success = self.epg_manager.load_cached_epg()
                message = "EPG 缓存已加载" if success else "EPG 缓存加载失败"

            if success:
                self.epg_progress_updated.emit("EPG 数据加载完成，正在更新界面...")
                self.update_completer_model()
                self.epg_progress_updated.emit(message)
            else:
                self.epg_progress_updated.emit(message)
        except Exception as e:
            logger.error(f"EPG 操作失败: {str(e)}")
            self.epg_progress_updated.emit(f"EPG 操作失败: {str(e)}")

    @pyqtSlot()
    def handle_epg_load_success(self) -> None:
        """EPG 加载成功后的处理"""
        self.statusBar().showMessage("EPG 数据加载完成")

    @pyqtSlot(Exception)
    def handle_epg_load_error(self, error: Exception) -> None:
        """EPG 加载失败后的处理"""
        self.show_error(f"EPG 加载失败: {str(error)}")

    def on_text_changed(self, text: str) -> None:
        """输入框文本变化时的处理"""
        self.debounce_timer.start(300)
        self.name_edit.setFocus()  # 强制设置输入框焦点

    def update_completer_model(self) -> None:
        """更新自动补全模型"""
        try:
            # 获取输入框的当前文本
            partial = self.name_edit.text().strip()
            names = self.epg_manager.match_channel_name(partial)

            # 更新自动补全模型
            model = QtCore.QStringListModel(names)
            self.epg_completer.setModel(model)

            # 强制刷新待选框
            if partial:  # 仅在输入框不为空时刷新
                self.epg_completer.complete()
        except Exception as e:
            logger.warning(f"更新自动补全模型失败: {str(e)}")

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

    def load_config(self) -> None:
        """加载用户配置"""
        try:
            # 窗口布局
            if geometry := self.config.config.get('UserPrefs', 'window_geometry', fallback=''):
                self.restoreGeometry(QtCore.QByteArray.fromHex(geometry.encode()))

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

    def closeEvent(self, event: QCloseEvent) -> None:
        """处理关闭事件"""
        try:
            # 停止播放并释放资源
            if self.player:
                self.player.stop()

            # 保存窗口状态
            self.config.config['UserPrefs']['window_geometry'] = self.saveGeometry().toHex().data().decode()

            # 保存扫描记录
            self.config.config['Scanner']['last_range'] = self.ip_range_input.text()

            # 保存播放器设置
            self.config.config['Player']['hardware_accel'] = self.player.hw_accel

            self.config.save_prefs()
            super().closeEvent(event)
        except Exception as e:
            logger.error(f"关闭时保存配置失败: {str(e)}")
            event.ignore()

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
        self.statusBar().showMessage("扫描任务完成")

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
        """管理EPG数据源"""
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("EPG管理")
        layout = QtWidgets.QVBoxLayout()

        # 添加EPG源设置
        epg_label = QtWidgets.QLabel("EPG源URL：")
        self.epg_url_input = QtWidgets.QLineEdit()
        self.epg_url_input.setText(self.epg_manager.epg_sources['main'])

        layout.addWidget(epg_label)
        layout.addWidget(self.epg_url_input)

        # 保存按钮
        save_btn = QtWidgets.QPushButton("保存")
        save_btn.clicked.connect(lambda: self.save_epg_settings(dialog))
        layout.addWidget(save_btn)

        dialog.setLayout(layout)
        dialog.exec()

    def save_epg_settings(self, dialog: QtWidgets.QDialog) -> None:
        """保存EPG设置"""
        self.epg_manager.epg_sources['main'] = self.epg_url_input.text()
        dialog.close()
        self.statusBar().showMessage("EPG设置已保存")

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