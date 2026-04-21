"""
IPTV Player Pro - 主窗口（精简版）
重构后：6375行 → <800行
职责：仅负责UI组装和控制器协调
"""

import sys
import os

from datetime import datetime, timedelta
from models.channel_mappings import extract_channel_name_from_url
from models.channel_model import ChannelListModel
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QListWidget, QListWidgetItem, QStackedWidget,
    QMenuBar, QMenu, QFileDialog, QDialog, QTextEdit, QStatusBar,
    QFrame, QToolButton, QSlider, QGridLayout, QComboBox, QLabel as QtWidgets_QLabel,
    QAbstractItemView, QDateEdit
)
from PyQt6 import QtWidgets
from PyQt6.QtCore import Qt, QSize, QTimer, QUrl, QThread, pyqtSlot, QMetaObject, QPoint, pyqtSignal
from PyQt6 import QtCore
from PyQt6.QtGui import QIcon, QPixmap, QFont, QColor, QAction, QPainter, QBrush, QKeySequence, QShortcut

# 导入核心模块
from core.log_manager import global_logger as logger
from core.application_state import app_state
from core.language_manager import LanguageManager
from ui.styles import AppStyles
from ui.floating_dialog import TranslucentPanel, FloatingDialog

# 导入控制器包
from controllers import (
    WindowController,
    PlaybackController,
    EPGController,
    ChannelController,
    SettingsFileOperations,
    EventHandler
)

# 导入播放器服务
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from services.mpv_player_service import MpvPlayerController


def calculate_adaptive_delay(base_delay_ms: int = 200, min_delay_ms: int = 50, max_delay_ms: int = 500) -> int:
    """根据设备性能自适应计算延迟时间"""
    try:
        import psutil
        memory_gb = psutil.virtual_memory().total / (1024**3)
        cpu_count = psutil.cpu_count() or 2
        
        if memory_gb > 8 and cpu_count > 4:
            factor = 0.5
        elif memory_gb >= 4 and cpu_count >= 2:
            factor = 1.0
        else:
            factor = 1.5
        
        adaptive_delay = int(base_delay_ms * factor)
        return max(min_delay_ms, min(max_delay_ms, adaptive_delay))
        
    except ImportError:
        return base_delay_ms
    except Exception as e:
        logger.debug(f"计算自适应延迟失败: {e}，使用默认值")
        return base_delay_ms


# 向后兼容的全局变量引用
CHANNELS = app_state._channels
CHANNEL_GROUPS = app_state._channel_groups
EPG_DATA = app_state._epg_data


class IPTVPlayer(QMainWindow):
    """主窗口类 - 精简版（仅负责组装和协调）"""
    
    # 定义信号
    epg_status_signal = pyqtSignal(str)

    def __init__(self):
        """初始化主窗口 - 集成所有控制器"""
        logger.debug("开始初始化 IPTVPlayer（精简版）")
        super().__init__()
        
        # 窗口基本属性
        self._window_title = "IPTV Player Pro"
        self._is_stopped = True
        self.current_channel = None
        self.floating_panel_visible = False
        self._ui_initialized = False
        
        # 初始化所有控制器（核心改动：委托给专职控制器）
        self.window_ctrl = WindowController(self)
        self.playback_ctrl = PlaybackController(self)
        self.epg_ctrl = EPGController(self)
        self.channel_ctrl = ChannelController(self)
        self.settings_ops = SettingsFileOperations(self)
        self.event_handler = EventHandler(self)
        
        # 语言管理器
        self.language_manager = LanguageManager()
        
        # 配置管理器
        from core.config_manager import ConfigManager
        self.config_manager = ConfigManager()
        
        # 拖动相关变量（保留给WindowController使用）
        self._dragging = False
        self._drag_offset = None
        
        logger.debug("控制器初始化完成")
        
        # UI组件占位符（后续由_init_ui_components初始化）
        self.central_widget = None
        self.main_layout = None
        self.video_placeholder = None
        self.video_widget = None
        self.channel_list = None
        self.epg_list = None
        self.channel_name = None
        self.current_program = None
        self.channel_logo = None
        self.video_info = None
        self.audio_info = None
        self.network_info = None
        self.program_desc = None
        self.time_label = None
        self.remain_label = None
        self.progress_start = None
        self.progress_end = None
        self.program_progress = None
        self.volume_slider = None
        self.volume_button = None
        self.play_button = None
        self.group_combo = None
        self.epg_date_edit = None
        self.epg_panel = None
        self.playlist_panel = None
        self.status_bar = None
        self.player_controller = None
        self.channel_model = None
        
        # 数据属性
        self.channels = CHANNELS
        self.channel_groups = CHANNEL_GROUPS
        self.epg_data = EPG_DATA
        self._current_epg_date = None
        
        # 回看/时移状态（由PlaybackController管理）
        self.is_catchup_mode = False
        self.catchup_program = None
        self._live_timeshift_seconds = 0
        self._last_program_id = None
        self.exit_catchup_button = None
        
        # 调用初始化方法
        self._setup_basic_window()
        self.init_ui()

    def _setup_basic_window(self):
        """设置基本窗口属性"""
        self.setWindowTitle(self._window_title)
        self.setMinimumSize(800, 600)
        
        # 创建中央部件和布局
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        # 设置主窗口样式
        self.setStyleSheet(AppStyles.main_window_style())
        self.central_widget.setStyleSheet(AppStyles.player_background_style())

    def init_ui(self):
        """初始化UI（极简版本）"""
        # 使用WindowController创建自定义标题栏
        title_bar = self.window_ctrl.create_custom_title_bar(self._window_title)
        self.main_layout.addWidget(title_bar)
        
        # 创建视频区域
        self._create_video_area()
        
        # 创建底部控制面板
        self._create_bottom_panel()
        
        # 创建侧边面板（EPG和播放列表）
        self._create_side_panels()
        
        # 创建状态栏
        self._create_status_bar()
        
        # 标记UI初始化完成
        self._ui_initialized = True
        
        # 延迟加载数据
        adaptive_delay = calculate_adaptive_delay(200, 50, 500)
        QTimer.singleShot(adaptive_delay, self._load_initial_data)

    def _create_video_area(self):
        """创建视频显示区域"""
        # 视频占位符
        self.video_placeholder = QLabel()
        self.video_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_placeholder.setText("📺")
        self.video_placeholder.setStyleSheet(AppStyles.player_video_placeholder_style())
        self.main_layout.addWidget(self.video_placeholder, stretch=1)

    def _create_bottom_panel(self):
        """创建底部控制面板"""
        bottom_panel = QWidget()
        bottom_panel.setFixedHeight(120)
        bottom_panel.setStyleSheet(AppStyles.player_panel_style())
        bottom_layout = QHBoxLayout(bottom_panel)
        
        # 播放控制按钮
        self.play_button = QPushButton("▶")
        self.play_button.setFixedSize(50, 50)
        self.play_button.setStyleSheet(AppStyles.player_button_style())
        self.play_button.clicked.connect(self.toggle_play)
        bottom_layout.addWidget(self.play_button)
        
        # 音量控制
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setStyleSheet(AppStyles.player_volume_slider_style())
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(80)
        self.volume_slider.valueChanged.connect(self.set_volume)
        bottom_layout.addWidget(self.volume_slider)
        
        # 音量按钮
        self.volume_button = QPushButton("🔊")
        self.volume_button.setStyleSheet(AppStyles.player_button_style())
        self.volume_button.clicked.connect(self.toggle_mute)
        bottom_layout.addWidget(self.volume_button)
        
        # 进度条
        self.program_progress = QSlider(Qt.Orientation.Horizontal)
        self.program_progress.setStyleSheet(AppStyles.player_slider_style())
        bottom_layout.addWidget(self.program_progress, stretch=1)
        
        # 时间标签
        self.time_label = QLabel("⏱ --:-- - --:--")
        self.time_label.setStyleSheet(AppStyles.player_label_style())
        bottom_layout.addWidget(self.time_label)
        
        self.main_layout.addWidget(bottom_panel)

    def _create_side_panels(self):
        """创建侧边面板"""
        # EPG面板
        self.epg_panel = QWidget()
        self.epg_panel.setStyleSheet(AppStyles.player_panel_style())
        epg_layout = QVBoxLayout(self.epg_panel)
        
        # EPG标题
        self.epg_title = QLabel("EPG Program Guide")
        self.epg_title.setStyleSheet(AppStyles.player_epg_title_style())
        epg_layout.addWidget(self.epg_title)
        
        # EPG日期选择
        date_row = QHBoxLayout()
        self.epg_prev_day = QPushButton("◀")
        self.epg_prev_day.setStyleSheet(AppStyles.player_date_button_style())
        self.epg_prev_day.clicked.connect(self.epg_ctrl.on_prev_day)
        self.epg_date_edit = QDateEdit()
        self.epg_date_label = QLabel()
        self.epg_date_label.setStyleSheet(AppStyles.player_date_label_style())
        self.epg_next_day = QPushButton("▶")
        self.epg_next_day.setStyleSheet(AppStyles.player_date_button_style())
        self.epg_next_day.clicked.connect(self.epg_ctrl.on_next_day)
        date_row.addWidget(self.epg_prev_day)
        date_row.addWidget(self.epg_date_edit)
        date_row.addWidget(self.epg_next_day)
        epg_layout.addLayout(date_row)
        
        # EPG列表
        self.epg_list = QListWidget()
        self.epg_list.setStyleSheet(AppStyles.player_list_style())
        self.epg_list.itemClicked.connect(self.epg_ctrl.on_epg_item_clicked)
        epg_layout.addWidget(self.epg_list)
        
        # 播放列表面板
        self.playlist_panel = QWidget()
        self.playlist_panel.setStyleSheet(AppStyles.player_panel_style())
        playlist_layout = QVBoxLayout(self.playlist_panel)
        
        # 播放列表标题
        self.playlist_title = QLabel("Playlist")
        self.playlist_title.setStyleSheet(AppStyles.player_playlist_title_style())
        playlist_layout.addWidget(self.playlist_title)
        
        # 分组选择
        self.group_combo = QComboBox()
        self.group_combo.setStyleSheet(AppStyles.player_group_combo_style())
        self.group_combo.currentTextChanged.connect(self.channel_ctrl.on_group_changed)
        playlist_layout.addWidget(self.group_combo)
        
        # 频道列表
        self.channel_list = QListWidget()
        self.channel_list.setStyleSheet(AppStyles.player_list_style())
        self.channel_list.itemClicked.connect(self.channel_ctrl.select_channel)
        playlist_layout.addWidget(self.channel_list)
        
        # 信息显示区域
        info_frame = QFrame()
        info_layout = QGridLayout(info_frame)
        
        self.channel_logo = QLabel("📺")
        self.channel_logo.setStyleSheet(AppStyles.player_channel_logo_style())
        self.channel_name = QLabel("No channel selected")
        self.channel_name.setStyleSheet(AppStyles.player_channel_name_style())
        self.current_program = QLabel("▶ Select a channel to play")
        self.current_program.setStyleSheet(AppStyles.player_program_style())
        self.video_info = QLabel("📺 Not playing")
        self.video_info.setStyleSheet(AppStyles.player_label_style())
        self.audio_info = QLabel("🔊 --")
        self.audio_info.setStyleSheet(AppStyles.player_label_style())
        self.network_info = QLabel("📡 --")
        self.network_info.setStyleSheet(AppStyles.player_label_style())
        self.program_desc = QLabel("Open a playlist file or import channels")
        self.program_desc.setStyleSheet(AppStyles.player_program_desc_style())
        self.remain_label = QLabel("Waiting to play...")
        self.remain_label.setStyleSheet(AppStyles.player_program_style())
        self.progress_start = QLabel("--:--")
        self.progress_start.setStyleSheet(AppStyles.player_progress_label_style())
        self.progress_end = QLabel("--:--")
        self.progress_end.setStyleSheet(AppStyles.player_progress_label_style())
        
        info_layout.addWidget(self.channel_logo, 0, 0)
        info_layout.addWidget(self.channel_name, 0, 1)
        info_layout.addWidget(self.current_program, 1, 0, 1, 2)
        info_layout.addWidget(self.video_info, 2, 0)
        info_layout.addWidget(self.audio_info, 2, 1)
        info_layout.addWidget(self.network_info, 3, 0)
        info_layout.addWidget(self.program_desc, 4, 0, 1, 2)
        info_layout.addWidget(self.progress_start, 5, 0)
        info_layout.addWidget(self.program_progress, 5, 1)
        info_layout.addWidget(self.progress_end, 5, 2)
        info_layout.addWidget(self.time_label, 6, 0, 1, 3)
        info_layout.addWidget(self.remain_label, 7, 0, 1, 3)
        
        playlist_layout.addWidget(info_frame)

    def _create_status_bar(self):
        """创建状态栏"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

    def _load_initial_data(self):
        """加载初始数据"""
        logger.debug("加载初始数据...")
        
        # 初始化播放器
        self._init_player()
        
        # 加载配置
        self._load_config()
        
        # 填充频道列表
        if self.channels:
            self.channel_ctrl.populate_channel_list()
            self.channel_ctrl.update_channel_groups()
        
        # 填充EPG列表
        if self.epg_data:
            self.epg_ctrl.populate_epg_list()
        
        logger.debug("初始数据加载完成")

    def _init_player(self):
        """初始化播放器"""
        try:
            # 创建视频widget
            from services.mpv_bindings import MpvWidget
            self.video_widget = MpvWidget()
            self.video_widget.hide()
            
            # 创建播放器控制器
            self.player_controller = MpvPlayerController(self.video_widget)
            
            # 连接信号
            self.player_controller.play_error.connect(self.on_play_error)
            self.player_controller.media_info_ready.connect(self.on_media_info_ready)
            
            logger.info("播放器初始化成功")
        except Exception as e:
            logger.error(f"播放器初始化失败: {e}")

    def _load_config(self):
        """加载配置"""
        try:
            # 从配置文件恢复窗口布局
            layout = self.config_manager.load_window_layout()
            if layout:
                x, y, width, height = layout['x'], layout['y'], layout['width'], layout['height']
                self.setGeometry(x, y, width, height)
                
            # 加载音量设置
            volume = self.config_manager.get_value('Playback', 'volume', '80')
            if volume:
                self.volume_slider.setValue(int(volume))
                
        except Exception as e:
            logger.warning(f"加载配置失败: {e}")

    # ========== 委托给控制器的公共方法 ==========
    
    @property
    def is_playing(self):
        return self.playback_ctrl.is_playing
    
    # 窗口操作（委托给WindowController）
    def _toggle_maximize(self):
        self.window_ctrl.toggle_maximize()
    
    def _toggle_stay_on_top(self):
        self.window_ctrl.toggle_stay_on_top()
    
    def mousePressEvent(self, event):
        if not self.window_ctrl.handle_mouse_press_event(event):
            super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        if not self.window_ctrl.handle_mouse_move_event(event):
            super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        self.window_ctrl.handle_mouse_release_event(event)
        super().mouseReleaseEvent(event)
    
    def mouseDoubleClickEvent(self, event):
        if not self.window_ctrl.handle_mouse_double_click_event(event):
            super().mouseDoubleClickEvent(event)
    
    # 播放控制（委托给PlaybackController）
    def toggle_play(self):
        self.playback_ctrl.toggle_play()
    
    def stop_playback(self):
        self.playback_ctrl.stop_playback()
    
    def set_volume(self, value):
        self.playback_ctrl.set_volume(value)
    
    def toggle_mute(self):
        self.playback_ctrl.toggle_mute()
    
    def play_channel(self, channel):
        self.playback_ctrl.play_channel(channel)
    
    def _do_play_channel(self, channel):
        self.playback_ctrl._do_play_channel(channel)
    
    # EPG操作（委托给EPGController）
    def populate_epg_list(self):
        self.epg_ctrl.populate_epg_list()
    
    def on_epg_item_clicked(self, item):
        self.epg_ctrl.on_epg_item_clicked(item)
    
    def toggle_epg(self, checked):
        self.epg_ctrl.toggle_epg(checked)
    
    def on_prev_day(self):
        self.epg_ctrl.on_prev_day()
    
    def on_next_day(self):
        self.epg_ctrl.on_next_day()
    
    # 频道列表操作（委托给ChannelController）
    def populate_channel_list(self):
        self.channel_ctrl.populate_channel_list()
    
    def on_group_changed(self, group_name):
        self.channel_ctrl.on_group_changed(group_name)
    
    def select_channel(self, item):
        self.channel_ctrl.select_channel(item)
    
    def update_channel_groups(self):
        if hasattr(self, 'group_combo') and self.channel_model:
            groups = ["All Channels"] + list(set(ch.get('group', '') for ch in self.channels if ch.get('group')))
            current = self.group_combo.currentText()
            self.group_combo.clear()
            self.group_combo.addItems(groups)
            if current in [self.group_combo.itemText(i) for i in range(self.group_combo.count())]:
                self.group_combo.setCurrentText(current)
    
    # 文件操作（委托给SettingsFileOperations）
    def open_playlist(self):
        self.settings_ops.open_playlist()
    
    def save_as(self):
        self.settings_ops.save_as()
    
    def player_settings(self):
        self.settings_ops.player_settings()
    
    def reload_subscription(self):
        self.settings_ops.reload_subscription()
    
    def set_language(self, language):
        self.settings_ops.set_language(language)
    
    def set_theme(self, theme):
        self.settings_ops.set_theme(theme)
    
    def show_about(self):
        self.settings_ops.show_about()
    
    def show_usage_instructions(self):
        self.settings_ops.show_usage_instructions()
    
    def save_window_layout(self):
        self.settings_ops.save_window_layout()
    
    # 事件处理（委托给EventHandler）
    def keyPressEvent(self, event):
        if not self.event_handler.keyPressEvent(event):
            super().keyPressEvent(event)
    
    def eventFilter(self, obj, event):
        return self.event_handler.eventFilter(obj, event)
    
    def showEvent(self, event):
        self.event_handler.showEvent(event)
    
    def changeEvent(self, event):
        self.event_handler.changeEvent(event)
    
    def moveEvent(self, event):
        self.event_handler.moveEvent(event)
    
    def resizeEvent(self, event):
        self.event_handler.resizeEvent(event)
    
    def closeEvent(self, event):
        self.event_handler.closeEvent(event)
    
    # ========== 信号处理方法 ==========
    
    def on_play_error(self, error_msg):
        """处理播放错误"""
        logger.error(f"播放错误: {error_msg}")
        self.status_bar_show_message(f"Error: {error_msg}")
    
    def on_media_info_ready(self, media_info):
        """媒体信息就绪"""
        if media_info:
            self.update_media_info(media_info)
    
    def update_media_info(self, media_info=None):
        """更新媒体信息显示"""
        if media_info and self.video_info:
            codec = media_info.get('codec', 'Unknown')
            resolution = media_info.get('resolution', 'N/A')
            fps = media_info.get('fps', 'N/A')
            bitrate = media_info.get('bitrate', 'N/A')
            self.video_info.setText(f"📺 {resolution} | {codec} | {fps} fps | {bitrate}")
    
    def status_bar_show_message(self, message):
        """在状态栏显示消息"""
        if self.status_bar:
            self.status_bar.showMessage(message, 3000)
    
    # ========== 其他辅助方法 ==========
    
    def update_floating_position(self):
        """更新悬浮窗位置"""
        pass  # 由WindowController处理
    
    def toggle_fullscreen(self, checked=False):
        """切换全屏"""
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()
    
    def refresh_ui(self):
        """刷新UI"""
        self.setStyleSheet(AppStyles.main_window_style())
        if self.central_widget:
            self.central_widget.setStyleSheet(AppStyles.player_background_style())
    
    def reset_layout(self):
        """重置布局"""
        self.setGeometry(100, 100, 1280, 780)
    
    def open_scan_ui(self):
        """打开扫描界面"""
        from ui.dialogs.scan_channel_dialog import ScanChannelDialog
        dialog = ScanChannelDialog(self, self.channel_model)
        dialog.exec()
    
    def open_channel_mapping(self):
        """打开频道映射编辑器"""
        from ui.dialogs.mapping_manager_dialog import MappingManagerDialog
        dialog = MappingManagerDialog(self)
        dialog.exec()
    
    def start_subscription_timers(self):
        """启动订阅定时器"""
        self.settings_ops.reload_subscription()
    
    def update_playlist_subscription(self, source_index=None):
        """更新播放列表订阅"""
        self.settings_ops.reload_subscription()
    
    def update_epg_subscription(self):
        """更新EPG订阅"""
        self.epg_ctrl.populate_epg_list()
    
    def save_player_settings(self, dialog):
        """保存播放器设置"""
        self.settings_ops.save_window_layout()
    
    def update_recent_files_menu(self):
        """更新最近文件菜单"""
        pass  # TODO: 实现
    
    def open_recent_file(self, file_path):
        """打开最近的文件"""
        self.settings_ops._load_playlist_file(file_path)
    
    def raise_floating_panels(self):
        """提升悬浮窗"""
        pass  # 由WindowController处理
    
    def merge_channels_from_content(self, content, mode='append'):
        """合并频道内容"""
        try:
            from services.m3u_parser import parse_m3u_content
            new_channels = parse_m3u_content(content)
            if mode == 'append':
                self.channels.extend(new_channels)
            else:
                self.channels = new_channels
            self.channel_ctrl.populate_channel_list()
        except Exception as e:
            logger.error(f"合并频道失败: {e}")
    
    def select_channel_by_index(self, idx):
        """按索引选择频道"""
        if self.channel_list and idx < self.channel_list.count():
            self.channel_list.setCurrentRow(idx)
            item = self.channel_list.currentItem()
            if item:
                self.channel_ctrl.select_channel(item)
    
    def start_timeshift(self, offset_minutes=None):
        """启动时移"""
        logger.info(f"启动时移: {offset_minutes} 分钟")
        # TODO: 实现时移功能
    
    def update_floating_panel_info(self):
        """更新悬浮窗信息"""
        pass  # 由WindowController处理


# 程序入口
if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setApplicationName("IPTV Player Pro")
    
    player = IPTVPlayer()
    app.processEvents()
    player.show()
    sys.exit(app.exec())
