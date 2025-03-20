import sys
import asyncio
import platform
from pathlib import Path
from typing import Optional, List, Dict, Any
from PyQt6 import QtCore, QtWidgets
from PyQt6.QtCore import Qt, pyqtSlot, QModelIndex
from PyQt6.QtGui import QCloseEvent, QAction, QKeySequence
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
            return f"{chan['name']} [{chan.get('width', 0)}x{chan.get('height', 0)}]"
        elif role == Qt.ItemDataRole.UserRole:
            return self.channels[index.row()]
        return None

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self.channels)

class MainWindow(QtWidgets.QMainWindow):
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

    def _setup_scan_panel(self, parent: QtWidgets.QSplitter) -> None:
        """配置扫描面板"""
        scan_group = QtWidgets.QGroupBox("扫描设置")
        scan_layout = QtWidgets.QFormLayout()
        
        self.ip_range_input = QtWidgets.QLineEdit()
        self.scan_progress = QtWidgets.QProgressBar()
        scan_btn = QtWidgets.QPushButton("开始扫描")
        scan_btn.clicked.connect(self.start_scan)
        
        scan_layout.addRow("IP范围格式：", QtWidgets.QLabel("示例：192.168.[1-5].[1-255]:5002"))
        scan_layout.addRow("输入范围：", self.ip_range_input)
        scan_layout.addRow("进度：", self.scan_progress)
        scan_layout.addRow(scan_btn)
        
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
        player_layout.addWidget(self.player)
        player_group.setLayout(player_layout)
        parent.addWidget(player_group)

    def _setup_edit_panel(self, parent: QtWidgets.QSplitter) -> None:
        """配置编辑面板"""
        edit_group = QtWidgets.QGroupBox("频道编辑")
        edit_layout = QtWidgets.QFormLayout()
        
        self.name_edit = QtWidgets.QLineEdit()
        self.name_edit.setPlaceholderText("输入频道名称...")
        self.epg_completer = QtWidgets.QCompleter()
        self.name_edit.setCompleter(self.epg_completer)
        
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
        """初始化工具栏"""
        toolbar = self.addToolBar("主工具栏")
        toolbar.setMovable(False)
        
        self.tool_actions = {
            'open': toolbar.addAction("📂 打开", self.open_playlist),
            'save': toolbar.addAction("💾 保存", self.save_playlist),
            'scan': toolbar.addAction("🔍 扫描", self.start_scan),
            'epg_refresh': toolbar.addAction("🔄 EPG", self.refresh_epg),
            'stop': toolbar.addAction("⏹ 停止", self.stop_play)
        }
        toolbar.addSeparator()
        toolbar.addWidget(QtWidgets.QLabel("|"))
        toolbar.addAction("⚙ 设置", self.show_settings)

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
            self.show_error("请输入有效的IP范围")
            return
        
        self.scan_worker = AsyncWorker(self._async_scan(ip_range))
        self.scan_worker.finished.connect(self.handle_scan_success)
        self.scan_worker.error.connect(self.handle_scan_error)
        self.scan_worker.cancelled.connect(self.handle_scan_cancel)
        asyncio.create_task(self.scan_worker.run())

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
            
            self.play_worker = AsyncWorker(self.player.async_play(url))
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

    @pyqtSlot()
    def refresh_epg(self) -> None:
        """刷新EPG数据"""
        try:
            if self.epg_manager.refresh_epg():
                self.update_completer_model()
                self.statusBar().showMessage("EPG数据更新成功")
            else:
                self.show_error("EPG更新失败，请检查网络连接")
        except Exception as e:
            self.show_error(f"EPG刷新错误: {str(e)}")

    def update_completer_model(self) -> None:
        """更新自动补全模型"""
        names = self.epg_manager.match_channel_name('')
        model = QtCore.QStringListModel(names)
        self.epg_completer.setModel(model)

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
            self.player.set_hardware_accel(hardware_accel)
            
        except Exception as e:
            logger.error(f"配置加载失败: {str(e)}")

    def closeEvent(self, event: QCloseEvent) -> None:
        """处理关闭事件"""
        try:
            # 保存窗口状态
            self.config.config['UserPrefs']['window_geometry'] = self.saveGeometry().toHex().decode()
            
            # 保存扫描记录
            self.config.config['Scanner']['last_range'] = self.ip_range_input.text()
            
            # 保存播放器设置
            self.config.config['Player']['hardware_accel'] = self.player.get_hardware_accel()
            
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

    # 辅助功能占位
    def show_scan_settings(self) -> None:
        QMessageBox.information(self, "提示", "扫描设置功能待实现")

    def manage_epg(self) -> None:
        QMessageBox.information(self, "提示", "EPG管理功能待实现")

    def show_settings(self) -> None:
        QMessageBox.information(self, "提示", "全局设置功能待实现")

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)
    
    main_window = MainWindow()
    main_window.show()
    
    with loop:
        sys.exit(loop.run_forever())