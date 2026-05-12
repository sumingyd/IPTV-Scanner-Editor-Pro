import sys
import os
import re
import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional
from models.channel_model import ChannelListModel
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QListWidget, QListWidgetItem,
    QStatusBar,
    QFrame, QToolButton, QSlider, QComboBox,
    QTabWidget
)
from PyQt6 import QtWidgets
from PyQt6.QtCore import Qt, QSize, QTimer, QThread, pyqtSlot, pyqtSignal, QMetaObject
from PyQt6 import QtCore
from PyQt6.QtGui import QIcon, QFont, QFontMetrics, QColor, QAction, QPainter, QBrush, QShortcut, QPen, QLinearGradient, QPainterPath, QPixmap

from core.log_manager import global_logger as logger
from core.application_state import app_state
from core.language_manager import LanguageManager
from ui.styles import AppStyles

from controllers import (
    WindowController,
    PlaybackController,
    EPGController,
    ChannelController,
    SettingsFileOperations,
    EventHandler,
    UIController,
    SubscriptionController,
    SubscriptionUIController,
    CatchupController
)

from utils.general_utils import calculate_adaptive_delay


class VideoOverlayBadge(QWidget):
    """视频区域叠加标识 Widget，用 QPainter 绘制精美的回看/时移标签"""

    MODE_CATCHUP   = 'catchup'
    MODE_TIMESHIFT = 'timeshift'

    # 各模式的颜色配置 (渐变起, 渐变止, 图标文字, 文字颜色)
    _CONFIGS = {
        MODE_CATCHUP:   ('#1a6fcf', '#0d4e9a', '▶ ', '#e8f4fd'),
        MODE_TIMESHIFT: ('#c97a00', '#8a5200', '⏪ ', '#fff4e0'),
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mode = self.MODE_CATCHUP
        self._label_text = ''
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._font = QFont()
        self._font.setPixelSize(13)
        self._font.setBold(True)
        self._update_size()

    def set_mode(self, mode: str, label_text: str):
        self._mode = mode
        self._label_text = label_text
        self._update_size()
        self.update()

    def _update_size(self):
        icon, text = self._get_parts()
        full_text = icon + text
        self._font.setPixelSize(13)
        fm2 = QFontMetrics(self._font)
        w = fm2.horizontalAdvance(full_text) + 20
        h = fm2.height() + 12
        self.setFixedSize(w, h)

    def _get_parts(self):
        cfg = self._CONFIGS.get(self._mode, self._CONFIGS[self.MODE_CATCHUP])
        icon = cfg[2]
        return icon, self._label_text

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        cfg = self._CONFIGS.get(self._mode, self._CONFIGS[self.MODE_CATCHUP])
        color1, color2, icon, text_color = cfg

        r = self.rect()
        radius = r.height() / 2

        # 绘制圆角矩形背景 (渐变)
        path = QPainterPath()
        path.addRoundedRect(0, 0, r.width(), r.height(), radius, radius)

        grad = QLinearGradient(0, 0, r.width(), 0)
        grad.setColorAt(0, QColor(color1))
        grad.setColorAt(1, QColor(color2))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(grad))
        painter.drawPath(path)

        # 微光描边
        painter.setPen(QPen(QColor(255, 255, 255, 40), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

        # 绘制文字 (图标 + 标签)
        painter.setFont(self._font)
        painter.setPen(QColor(text_color))
        full_text = icon + self._label_text
        painter.drawText(r, Qt.AlignmentFlag.AlignCenter, full_text)

        painter.end()


# 导入播放器服务
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from services.mpv_player_service import MpvPlayerController


class IPTVPlayer(QMainWindow):
    epg_status_signal = pyqtSignal(str)
    channel_list_updated = pyqtSignal()
    epg_list_updated = pyqtSignal()
    status_message = pyqtSignal(str)

    player_controller = None
    config = None
    config_manager = None
    language_manager = None
    channel_model = None
    channels = None
    current_channel: Optional[Dict[str, Any]] = None
    epg_parser = None

    window_ctrl = None
    playback_ctrl = None
    epg_ctrl = None
    channel_ctrl = None
    settings_ops = None
    event_handler = None
    ui_ctrl = None
    subscription_ctrl = None
    subscription_ui_ctrl = None
    catchup_ctrl = None

    video_frame = None
    video_widget = None
    video_placeholder = None
    central_widget = None
    toolbar = None
    status_bar = None
    epg_panel = None
    playlist_panel = None
    floating_panel = None
    top_layout = None
    main_layout = None
    content_layout = None

    _title_bar = None
    _title_label = None
    _title_icon_label = None
    _stay_on_top_btn = None
    _minimize_btn = None
    _maximize_btn = None
    _close_btn = None
    _custom_menu_bar = None
    _main_container = None

    update_timer = None
    resize_timer = None
    epg_dock = None
    playlist_dock = None
    floating_dock = None
    playlist_tab = None
    playlist_list_widget = None
    epg_list_widget = None
    playlist_new_url_edit = None
    playlist_new_name_edit = None
    epg_new_url_edit = None
    epg_new_name_edit = None
    _playlist_add_btn = None
    _epg_add_btn = None

    is_fullscreen = False
    is_catchup_mode = False
    is_timeshift_mode = False
    _is_timeshift_mode = False
    _live_timeshift_seconds = 0
    catchup_program: Optional[Dict[str, Any]] = None
    epg_visible = True
    playlist_visible = True
    floating_panel_visible = True
    _floating_hidden = False
    _auto_hide_state = 'visible'
    _osd_visible = False
    _suppress_volume_osd = False
    _initialization_complete = False
    _panels_initialized = False
    _ui_initialized = False
    _dragging = False
    _drag_offset = None
    _last_mouse_pos = None
    _editing_playlist_index = -1
    _editing_epg_index = -1
    current_epg_date: Optional[date] = None
    _saved_floating_states: Optional[Dict[str, bool]] = None
    _auto_hide_saved_states: Optional[Dict[str, bool]] = None
    _osd_saved_panel_states: Optional[Dict[str, bool]] = None
    _window_title = ''
    _theme_manager = None
    
    def __init__(self, parent: Optional[QWidget] = None, flags: Qt.WindowType = Qt.WindowType.Window):
        from utils.general_utils import suppress_urllib3_warnings
        suppress_urllib3_warnings()
        logger.debug("开始初始化 IPTVPlayer")
        super().__init__(parent=parent, flags=flags)

        self._init_config()
        self._init_state()
        self._init_signals()
        self._init_controllers()
        self._init_basic_ui()

        self.setStyleSheet(AppStyles.main_window_style())
        self._initialize_in_order()

    def _init_config(self):
        """初始化配置、主题、语言、窗口布局"""
        from core.config_manager import ConfigManager
        self.config = ConfigManager()

        from ui.theme_manager import get_theme_manager
        self._theme_manager = get_theme_manager()

        self.language_manager = LanguageManager()
        self.language_manager.load_available_languages()
        saved_language = self.config.load_language_settings()
        self.language_manager.set_language(saved_language)

        from ui.dialogs.about_dialog import AboutDialog
        current_version = AboutDialog.CURRENT_VERSION
        self._window_title = f"{self.language_manager.tr('app_title', 'IPTV Scanner Editor Pro')} v{current_version}"
        self.setWindowTitle(self._window_title)

        from utils.general_utils import get_icon_path
        ico_path = get_icon_path()
        if os.path.exists(ico_path):
            from PyQt6.QtGui import QIcon
            self.setWindowIcon(QIcon(ico_path))

        x, y, width, height, _ = self.config.load_window_layout(
            default_x=100, default_y=100, default_width=1280, default_height=780
        )
        self.setGeometry(x, y, width, height)
        self.setMinimumSize(800, 600)

    def _init_state(self):
        """初始化所有状态变量"""
        self._dragging = False
        self._drag_offset = None
        self._last_mouse_pos = None

        self.channel_model = ChannelListModel()
        self.current_channel = None

        self.epg_visible = True
        self.playlist_visible = True
        self.floating_panel_visible = True
        self._floating_hidden = False
        self._saved_floating_states = {}
        self._auto_hide_state = 'visible'
        self._auto_hide_saved_states = {}
        self._osd_visible = False
        self._osd_saved_panel_states = {}
        self._suppress_volume_osd = False
        self.is_fullscreen = False

        from core.subscription_manager import global_subscription_manager
        self.epg_parser = global_subscription_manager

        self.update_timer = None
        self.resize_timer = None
        self._initialization_complete = False
        self._panels_initialized = False
        self._ui_initialized = False
        self.epg_panel = None
        self.playlist_panel = None
        self.floating_panel = None
        self.video_frame = None
        self.video_widget = None
        self.video_placeholder = None
        self.top_layout = None
        self.toolbar = None
        self.status_bar = None

        from datetime import datetime
        self.current_epg_date = datetime.now().date()
        self._last_media_info: Dict[str, Any] = {}

    def _init_signals(self):
        """连接所有信号到槽函数"""
        self.epg_status_signal.connect(self.update_status_bar)
        self.channel_list_updated.connect(self._update_channel_list_ui)
        self.epg_list_updated.connect(self._populate_epg_list)
        self.status_message.connect(self.status_bar_show_message)

    def _init_controllers(self):
        """初始化所有业务控制器"""
        logger.debug("初始化业务控制器...")
        self.window_ctrl = WindowController(self)
        self.playback_ctrl = PlaybackController(self)
        self.epg_ctrl = EPGController(self)
        self.channel_ctrl = ChannelController(self)
        self.settings_ops = SettingsFileOperations(self)
        self.event_handler = EventHandler(self)
        self.ui_ctrl = UIController(self)
        self.subscription_ctrl = SubscriptionController(self)
        self.subscription_ui_ctrl = SubscriptionUIController(self)
        self.catchup_ctrl = CatchupController(self)
        logger.debug("业务控制器初始化完成")

    def _init_basic_ui(self):
        """创建最基础的UI框架：无边框窗口、容器、标题栏、内容区域"""
        logger.debug("创建最最基本的UI")
        self.setWindowFlags(QtCore.Qt.WindowType.FramelessWindowHint | QtCore.Qt.WindowType.Window)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self.setAcceptDrops(True)

        self._main_container = QWidget()
        self._main_container.setObjectName("mainContainer")
        self.setCentralWidget(self._main_container)

        self.main_layout = QVBoxLayout(self._main_container)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        self._create_custom_title_bar()

        self.central_widget = QWidget()
        self.central_widget.setStyleSheet(AppStyles.player_background_style())
        self.central_widget.setObjectName("contentArea")
        self.main_layout.addWidget(self.central_widget)

        self.content_layout = QVBoxLayout(self.central_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(0)
        logger.debug("IPTVPlayer 最小化初始化完成")

    def _create_custom_title_bar(self):
        """创建自定义标题栏（委托给WindowController）"""
        title_bar = self.window_ctrl.create_custom_title_bar(self._window_title)
        
        # 保存引用（兼容原有代码）
        self._title_bar = title_bar
        self._title_icon_label = self.window_ctrl._title_icon_label
        self._title_label = self.window_ctrl._title_label
        self._stay_on_top_btn = self.window_ctrl._stay_on_top_btn
        self._minimize_btn = self.window_ctrl._minimize_btn
        self._maximize_btn = self.window_ctrl._maximize_btn
        self._close_btn = self.window_ctrl._close_btn
        
        # 将标题栏添加到主布局顶部
        self.main_layout.addWidget(self._title_bar)

    def _toggle_maximize(self):
        """切换最大化/还原状态（委托给WindowController）"""
        self.window_ctrl.toggle_maximize()

    def _toggle_stay_on_top(self):
        """切换置顶状态（委托给WindowController）"""
        self.window_ctrl.toggle_stay_on_top()

    def mousePressEvent(self, event):
        """鼠标按下事件"""
        if getattr(self, 'is_fullscreen', False):
            self._on_mouse_activity()
        if getattr(self, '_pip_mode', False):
            if self._pip_mouse_press(event):
                return
        if not self.window_ctrl.handle_mouse_press_event(event):
            self.update_floating_position()
            super().mousePressEvent(event)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                path = url.toLocalFile()
                if path.lower().endswith(('.m3u', '.m3u8', '.txt',
                                          '.mp4', '.mkv', '.avi', '.mov',
                                          '.flv', '.wmv', '.ts', '.webm')):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if not path:
                continue
            if path.lower().endswith(('.m3u', '.m3u8', '.txt')):
                if hasattr(self, 'settings_ops'):
                    self.settings_ops.open_specific_file(path)
                event.acceptProposedAction()
                return
            elif path.lower().endswith(('.mp4', '.mkv', '.avi', '.mov',
                                        '.flv', '.wmv', '.ts', '.webm')):
                if hasattr(self, 'player_controller') and self.player_controller:
                    self.player_controller.play(path)
                    from core.log_manager import global_logger as logger
                    logger.info(f"拖放打开视频文件: {path}")
                event.acceptProposedAction()
                return
        event.ignore()

    def mouseMoveEvent(self, event):
        """鼠标移动事件"""
        if getattr(self, 'is_fullscreen', False):
            self._on_mouse_activity()
        if getattr(self, '_pip_mode', False):
            if self._pip_mouse_move(event):
                return
        if not self.window_ctrl.handle_mouse_move_event(event):
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """鼠标释放事件"""
        if getattr(self, '_pip_mode', False):
            if self._pip_mouse_release(event):
                return
        self.window_ctrl.handle_mouse_release_event(event)
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        """鼠标双击事件 - 视频区域双击切换全屏，标题栏双击最大化"""
        if getattr(self, '_pip_mode', False):
            return
        if not self.window_ctrl.handle_mouse_double_click_event(event):
            if hasattr(self, 'video_widget') and self.video_widget:
                gpos = event.globalPosition().toPoint()
                vw_geo = self.video_widget.geometry()
                vw_global = self.video_widget.mapToGlobal(vw_geo.topLeft())
                if (vw_global.x() <= gpos.x() <= vw_global.x() + vw_geo.width() and
                        vw_global.y() <= gpos.y() <= vw_global.y() + vw_geo.height()):
                    self.toggle_fullscreen()
                    event.accept()
                    return
            super().mouseDoubleClickEvent(event)

    def wheelEvent(self, event):
        """滚轮事件 - 调节音量"""
        if getattr(self, '_pip_mode', False):
            return
        if getattr(self, 'is_fullscreen', False):
            self._on_mouse_activity()
        delta = event.angleDelta().y()
        if delta != 0 and hasattr(self, 'event_handler'):
            step = 5
            self.event_handler._adjust_volume(step if delta > 0 else -step)

    def enterEvent(self, event):
        """鼠标进入窗口"""
        if getattr(self, '_pip_mode', False):
            self._show_pip_overlay()
        elif not getattr(self, '_floating_hidden', False) and not getattr(self, 'is_fullscreen', False):
            self._show_floating_panels_on_enter()
        super().enterEvent(event)

    def leaveEvent(self, event):
        """鼠标离开窗口"""
        if getattr(self, '_pip_mode', False):
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(50, self._pip_delayed_hide_overlay)
        elif not getattr(self, '_floating_hidden', False) and not getattr(self, 'is_fullscreen', False):
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(50, self._delayed_hide_floating_panels)
        super().leaveEvent(event)
    
    def _initialize_in_order(self):
        """按照顺序执行初始化流程"""
        logger.debug("_initialize_in_order: 开始")

        # 1. 菜单栏、工具栏
        self._init_video_components()
        # 2. 视频区域
        self._create_video_area()
        # 3. 状态栏
        self._create_status_bar()
        # 4. 播放器
        self._init_player()
        # 5. 定时器
        self._create_timer()
        # 6. EPG 面板（创建后先隐藏，待窗口显示后由延迟定位再显示）
        self._create_epg_panel(show=False)
        # 7. 频道列表面板（同上）
        self._create_playlist_panel(show=False)
        # 8. 底部控制面板（同上）
        self._create_bottom_panel(show=False)
        # 9. 最近文件菜单
        self._update_recent_files_menu()
        # 10. 事件过滤器（幂等，只注册一次）
        self._install_event_filters()

        # ---- 所有同步 UI 构建完成，现在显示窗口 ----
        self.show()

        # 11. 注册清理 / 主题 / 快捷键（轻量，不阻塞）
        from utils.resource_cleaner import register_cleanup
        from services.mpv_validator_service import MpvStreamValidator
        from utils.memory_manager import optimize_memory
        register_cleanup(MpvStreamValidator.terminate_all, "mpv_validator_terminate_all")
        register_cleanup(optimize_memory, "optimize_memory")

        self._theme_manager.register_window(self)

        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        space_shortcut = QShortcut(' ', app)
        space_shortcut.activated.connect(self.toggle_play)
        space_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)

        # 标记UI初始化完成
        self._ui_initialized = True

        # 12. 窗口首次绘制后：定位悬浮窗并显示面板（一次延迟即可）
        QTimer.singleShot(150, self._deferred_initial_position)

        # 13. 延迟加载数据，确保不阻塞首帧渲染
        def load_data_with_delay():
            self._start_subscription_timers()
            self._populate_channel_list(source='subscription')
            self._populate_epg_list()
            self._check_for_updates_async()

        adaptive_delay = calculate_adaptive_delay(300, 150, 600)
        logger.debug(f"使用自适应延迟: {adaptive_delay}ms")
        QTimer.singleShot(adaptive_delay, load_data_with_delay)

        logger.debug("_initialize_in_order: 完成")

    def _handle_playlist_subscription(self, need_update, playlist_url, source_index=None):
        """在后台线程中处理列表订阅（委托给SubscriptionController）"""
        self.subscription_ctrl.handle_playlist_subscription(need_update, playlist_url, source_index)

    def update_channel_list_ui(self):
        """更新频道列表UI（公共方法，用于 QMetaObject.invokeMethod 调用）"""
        self._update_channel_list_ui()
    
    def _update_channel_list_ui(self):
        try:
            self.populate_channel_list(source='auto')
        except Exception as ex:
            logger.error(f"更新频道列表UI失败: {ex}")
    
    def status_bar_show_message(self, message):
        """在状态栏显示消息"""
        try:
            if self.status_bar:
                self.status_bar.showMessage(message)
        except Exception as ex:
            logger.error(f"在状态栏显示消息失败: {ex}")
    
    def _load_data_in_background(self):
        """在后台线程中加载数据"""
        logger.debug("_load_data_in_background: 开始")
        
        # 1. 等待UI元素显示
        import time
        max_wait = 5  # 最大等待时间（秒）
        wait_time = 0
        
        while wait_time < max_wait:
            if hasattr(self, 'video_frame') and self.video_frame:
                break
            time.sleep(0.1)
            wait_time += 0.1
        
        logger.debug(f"_load_data_in_background: UI准备就绪，等待时间: {wait_time:.1f}秒")
        
        # 2. 填充频道列表
        self.channel_list_updated.emit()
        
        # 3. 填充 EPG 列表
        self.epg_list_updated.emit()
        
        # 4. 检查版本更新
        self._check_for_updates_async()
        
        logger.debug("_load_data_in_background: 完成")
    
    def _full_initialization(self):
        """完整的初始化（在窗口显示后异步执行）"""
        logger.debug("_full_initialization: 开始")
        
        # 创建视频相关组件
        self._init_video_components()
        
        logger.debug("_full_initialization: 完成")
    
    def _init_video_components(self):
        """初始化视频相关组件"""
        logger.debug("_init_video_components: 开始")
        
        # 第一步：创建菜单栏
        self._create_menu_bar()
        
        logger.debug("_init_video_components: 完成")
    
    def _create_menu_bar(self):
        """创建菜单栏"""
        logger.debug("_create_menu_bar: 开始")
        
        # 菜单栏
        self.setup_menu_bar(skip_recent_files=True)
        
        # 第二步：创建工具栏
        self._create_tool_bar()
        
        logger.debug("_create_menu_bar: 完成")
    
    def _create_tool_bar(self):
        """创建工具栏"""
        logger.debug("_create_tool_bar: 开始")
        
        # 工具栏（暂时隐藏，等需要时再显示）
        self.toolbar = self.addToolBar("播放控制")
        if self.toolbar:
            self.toolbar.setStyleSheet(AppStyles.player_toolbar_style())
            self.toolbar.hide()
        
        logger.debug("_create_tool_bar: 完成")
    
    def _create_video_area(self):
        """创建视频区域"""
        logger.debug("_create_video_area: 开始")
        
        # 上半部分布局
        self.top_layout = QHBoxLayout()
        
        # 只创建视频播放区域（不创建悬浮窗）
        self.video_frame = QFrame()
        self.video_frame.setStyleSheet(AppStyles.player_background_style())
        
        # 创建默认背景（使用软件图标）
        from utils.general_utils import get_icon_path
        ico_path = get_icon_path()
        self.video_placeholder = QLabel(self.video_frame)
        self.video_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_placeholder.setStyleSheet(AppStyles.player_video_placeholder_style())
        if os.path.exists(ico_path):
            icon = QIcon(ico_path)
            from PyQt6.QtWidgets import QApplication
            screen = QApplication.primaryScreen()
            dpr = screen.devicePixelRatio() if screen else 1.0
            size = int(256 * dpr)
            pixmap = icon.pixmap(size, size, QIcon.Mode.Normal, QIcon.State.On)
            if not pixmap.isNull():
                pixmap.setDevicePixelRatio(dpr)
                self.video_placeholder.setPixmap(pixmap)
            else:
                self.video_placeholder.setText("📺")
        else:
            self.video_placeholder.setText("📺")

        # 创建视频播放窗口（初始隐藏，播放时才显示）
        self.video_widget = QWidget(self.video_frame)
        self.video_widget.setStyleSheet(AppStyles.player_background_style())
        self.video_widget.hide()

        self._video_overlay_label = VideoOverlayBadge(self.video_frame)
        self._video_overlay_label.hide()
        
        # 添加视频区域到布局
        self.top_layout.addWidget(self.video_frame, 1)
        self.content_layout.addLayout(self.top_layout, 1)
        
        logger.debug("_create_video_area: 完成")
    
    def _create_status_bar(self):
        """创建状态栏"""
        logger.debug("_create_status_bar: 开始")
        
        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.setStyleSheet(AppStyles.statusbar_style())
        self.status_bar_show_message(self.language_manager.tr("ready", "Ready"))
        
        # 回看相关属性
        self.is_catchup_mode = False
        self.original_channel: Optional[Dict[str, Any]] = None
        
        logger.debug("_create_status_bar: 完成")
    
    def _init_player(self):
        logger.debug("_init_player: 开始")
        
        self.player_controller = MpvPlayerController(self.video_widget)
        self.player_controller.play_state_changed.connect(self.on_play_state_changed)
        self.player_controller.live_media_info_updated.connect(self.on_live_media_info_updated)
        self.player_controller.play_error.connect(self.on_play_error)
        self.player_controller.reconnect_requested.connect(self._on_reconnect_requested)
        self.player_controller.thumbnail_captured.connect(self._on_player_thumbnail_captured)

        from services.logo_cache_service import LogoCacheService
        self._logo_cache_service = LogoCacheService(self)
        self._logo_cache_service.logo_loaded.connect(self._on_logo_cache_loaded)

        from services.thumbnail_service import ThumbnailService
        self._thumbnail_service = ThumbnailService(self)
        self._thumbnail_service.thumbnail_ready.connect(self._on_thumbnail_ready)

        from services.network_preheat_service import DnsPrefetcher, ConnectionPreheater
        self._dns_prefetcher = DnsPrefetcher(self)
        self._connection_preheater = ConnectionPreheater(self)

        self._source_timeout_timer = None
        self._current_source_index = {}
        self._timeshift_active = False
        self._timeshift_start_time = None

        self._load_last_channel()
        self._restore_aspect_ratio()

        logger.debug("_init_player: 完成")
    
    def _create_floating_panels(self):
        """创建悬浮窗"""
        logger.debug("_create_floating_panels: 开始")
        
        logger.debug("_create_floating_panels: 完成")
    
    def _create_timer(self):
        """创建定时器"""
        logger.debug("_create_timer: 开始")
        
        # 创建定时器，定期更新悬浮窗信息
        from PyQt6.QtCore import QTimer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_floating_panel_info)
        self.player_controller.playback_position_updated.connect(self._on_playback_position_updated)
        
        logger.debug("_create_timer: 完成")
    
    def _create_epg_panel(self, show=True):
        """创建EPG面板（QDockWidget 停靠左侧）"""
        logger.debug("_create_epg_panel: 开始")
        tr = self.language_manager.tr

        # EPG 面板内容容器（保持原有UI不变）
        epg_container = QWidget()
        epg_container.setStyleSheet(AppStyles.player_panel_style())
        epg_container.setFixedWidth(250)
        self.epg_layout = QVBoxLayout(epg_container)
        self.epg_layout.setContentsMargins(0, 0, 0, 0)

        # EPG标题
        self.epg_title = QLabel(f"📅 {tr('epg_title', 'Program Guide')}")
        self.epg_title.setStyleSheet(AppStyles.player_epg_title_style())
        self.epg_layout.addWidget(self.epg_title)

        # 日期选择器
        date_layout = QHBoxLayout()
        date_layout.setContentsMargins(8, 4, 8, 4)
        date_layout.setSpacing(8)

        self.epg_prev_day = QPushButton("◀")
        self.epg_prev_day.setFixedSize(24, 24)
        self.epg_prev_day.setCursor(Qt.CursorShape.PointingHandCursor)
        self.epg_prev_day.setStyleSheet(AppStyles.player_date_button_style())
        self.epg_prev_day.clicked.connect(self.on_prev_day)
        date_layout.addWidget(self.epg_prev_day)

        self.epg_date_label = QLabel(tr("today", "Today"))
        self.epg_date_label.setStyleSheet(AppStyles.player_date_label_style())
        self.epg_date_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        date_layout.addWidget(self.epg_date_label, 1)

        self.epg_next_day = QPushButton("▶")
        self.epg_next_day.setFixedSize(24, 24)
        self.epg_next_day.setCursor(Qt.CursorShape.PointingHandCursor)
        self.epg_next_day.setStyleSheet(AppStyles.player_date_button_style())
        self.epg_next_day.clicked.connect(self.on_next_day)
        date_layout.addWidget(self.epg_next_day)

        self.epg_layout.addLayout(date_layout)

        # EPG内容
        self.epg_content = QListWidget()
        self.epg_content.setStyleSheet(AppStyles.player_list_style())
        self.epg_content.setSpacing(8)
        self.epg_content.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.epg_content.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        from controllers.epg_controller import EPGItemDelegate
        self.epg_content.setItemDelegate(EPGItemDelegate(self.epg_content))
        self.epg_content.addItem(self.language_manager.tr("loading", "Loading..."))
        self.epg_content.itemClicked.connect(self.on_epg_item_clicked)
        self.epg_layout.addWidget(self.epg_content, 1)

        # EPG空提示
        self.epg_empty_label = QLabel(tr("no_epg_data", "No program information"))
        self.epg_empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.epg_empty_label.setStyleSheet(AppStyles.player_empty_label_style())
        self.epg_layout.addWidget(self.epg_empty_label)

        # 用 FloatingDockWidget 包装（圆角半透明 + Qt管理）
        from PyQt6.QtWidgets import QDockWidget
        from ui.floating_dialog import FloatingDockWidget
        self.epg_dock = FloatingDockWidget(tr("epg_title", "Program Guide"), self)
        self.epg_dock.setWidget(epg_container)
        self.epg_dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetClosable)
        self.epg_dock.setObjectName("epg_dock")
        if hasattr(self, 'epg_panel'):
            delattr(self, 'epg_panel')
        self.epg_panel = self.epg_dock

        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.epg_dock)
        self.epg_dock.setFloating(True)
        if not show:
            self.epg_dock.hide()

        logger.debug("_create_epg_panel: 完成")
    
    def _create_playlist_panel(self, show=True):
        """创建播放列表面板（双标签：订阅 + 本地）"""
        logger.debug("_create_playlist_panel: 开始")
        tr = self.language_manager.tr

        playlist_container = QWidget()
        playlist_container.setStyleSheet(AppStyles.player_panel_style())
        playlist_container.setFixedWidth(250)
        self.playlist_layout = QVBoxLayout(playlist_container)
        self.playlist_layout.setContentsMargins(0, 0, 0, 0)

        self.playlist_tab = QTabWidget()
        self.playlist_tab.setStyleSheet(AppStyles.player_tab_style())

        sub_tab = QWidget()
        sub_layout = QVBoxLayout(sub_tab)
        sub_layout.setContentsMargins(0, 0, 0, 0)
        sub_layout.setSpacing(0)

        self.sub_group_combo = QComboBox()
        self.sub_group_combo.addItems(app_state._channel_groups)
        self.sub_group_combo.setStyleSheet(AppStyles.player_group_combo_style())
        self.sub_group_combo.currentTextChanged.connect(self.on_sub_group_changed)
        sub_layout.addWidget(self.sub_group_combo)

        sub_toolbar = QWidget()
        sub_toolbar_layout = QHBoxLayout(sub_toolbar)
        sub_toolbar_layout.setContentsMargins(4, 2, 4, 2)
        sub_toolbar_layout.setSpacing(2)
        self.sub_view_list_btn = QToolButton()
        self.sub_view_list_btn.setText("≡")
        self.sub_view_list_btn.setFixedSize(24, 20)
        self.sub_view_list_btn.setStyleSheet(AppStyles.player_button_style())
        self.sub_view_list_btn.setCheckable(True)
        self.sub_view_list_btn.setChecked(True)
        self.sub_view_list_btn.clicked.connect(lambda: self._set_channel_view_mode('list', 'sub'))
        sub_toolbar_layout.addWidget(self.sub_view_list_btn)
        self.sub_view_grid_btn = QToolButton()
        self.sub_view_grid_btn.setText("⊞")
        self.sub_view_grid_btn.setFixedSize(24, 20)
        self.sub_view_grid_btn.setStyleSheet(AppStyles.player_button_style())
        self.sub_view_grid_btn.setCheckable(True)
        self.sub_view_grid_btn.clicked.connect(lambda: self._set_channel_view_mode('grid', 'sub'))
        sub_toolbar_layout.addWidget(self.sub_view_grid_btn)
        sub_toolbar_layout.addStretch()
        sub_layout.addWidget(sub_toolbar)

        self.sub_channel_list = QListWidget()
        self.sub_channel_list.setStyleSheet(AppStyles.player_list_style())
        self.sub_channel_list.setSpacing(2)
        self.sub_channel_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.sub_channel_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.sub_channel_list.itemClicked.connect(self.select_channel)
        sub_layout.addWidget(self.sub_channel_list, 1)

        self.sub_empty_label = QLabel(tr("no_channels", "No channels"))
        self.sub_empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sub_empty_label.setStyleSheet(AppStyles.player_empty_label_style())
        sub_layout.addWidget(self.sub_empty_label)

        local_tab = QWidget()
        local_layout = QVBoxLayout(local_tab)
        local_layout.setContentsMargins(0, 0, 0, 0)
        local_layout.setSpacing(0)

        self.local_group_combo = QComboBox()
        self.local_group_combo.addItems([tr("all_channels", "All Channels")])
        self.local_group_combo.setStyleSheet(AppStyles.player_group_combo_style())
        self.local_group_combo.currentTextChanged.connect(self.on_local_group_changed)
        local_layout.addWidget(self.local_group_combo)

        local_toolbar = QWidget()
        local_toolbar_layout = QHBoxLayout(local_toolbar)
        local_toolbar_layout.setContentsMargins(4, 2, 4, 2)
        local_toolbar_layout.setSpacing(2)
        self.local_view_list_btn = QToolButton()
        self.local_view_list_btn.setText("≡")
        self.local_view_list_btn.setFixedSize(24, 20)
        self.local_view_list_btn.setStyleSheet(AppStyles.player_button_style())
        self.local_view_list_btn.setCheckable(True)
        self.local_view_list_btn.setChecked(True)
        self.local_view_list_btn.clicked.connect(lambda: self._set_channel_view_mode('list', 'local'))
        local_toolbar_layout.addWidget(self.local_view_list_btn)
        self.local_view_grid_btn = QToolButton()
        self.local_view_grid_btn.setText("⊞")
        self.local_view_grid_btn.setFixedSize(24, 20)
        self.local_view_grid_btn.setStyleSheet(AppStyles.player_button_style())
        self.local_view_grid_btn.setCheckable(True)
        self.local_view_grid_btn.clicked.connect(lambda: self._set_channel_view_mode('grid', 'local'))
        local_toolbar_layout.addWidget(self.local_view_grid_btn)
        local_toolbar_layout.addStretch()
        local_layout.addWidget(local_toolbar)

        self.local_channel_list = QListWidget()
        self.local_channel_list.setStyleSheet(AppStyles.player_list_style())
        self.local_channel_list.setSpacing(2)
        self.local_channel_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.local_channel_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.local_channel_list.itemClicked.connect(self.select_channel)
        local_layout.addWidget(self.local_channel_list, 1)

        self.local_empty_label = QLabel(tr("no_channels", "No channels"))
        self.local_empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.local_empty_label.setStyleSheet(AppStyles.player_empty_label_style())
        local_layout.addWidget(self.local_empty_label)

        self.playlist_tab.addTab(sub_tab, tr("subscription_tab", "📡 Subscription"))
        self.playlist_tab.addTab(local_tab, tr("local_tab", "📂 Local"))
        self.playlist_tab.currentChanged.connect(self._on_playlist_tab_changed)
        self.playlist_layout.addWidget(self.playlist_tab)

        self.channel_list = self.sub_channel_list
        self.group_combo = self.sub_group_combo
        self.channel_empty_label = self.sub_empty_label

        self._sub_channels = []
        self._local_channels = []
        self._sub_groups = [tr("all_channels", "All Channels")]
        self._local_groups = [tr("all_channels", "All Channels")]

        from PyQt6.QtWidgets import QDockWidget
        from ui.floating_dialog import FloatingDockWidget
        self.playlist_dock = FloatingDockWidget(tr("channel_list", "Channel List"), self)
        self.playlist_dock.setWidget(playlist_container)
        self.playlist_dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetClosable)
        self.playlist_dock.setObjectName("playlist_dock")
        if hasattr(self, 'playlist_panel'):
            delattr(self, 'playlist_panel')
        self.playlist_panel = self.playlist_dock

        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.playlist_dock)
        self.playlist_dock.setFloating(True)
        if not show:
            self.playlist_dock.hide()

        logger.debug("_create_playlist_panel: 完成")

    def _on_playlist_tab_changed(self, index):
        """播放列表标签页切换"""
        if index == 0:
            self.channel_list = self.sub_channel_list
            self.group_combo = self.sub_group_combo
            self.channel_empty_label = self.sub_empty_label
        else:
            self.channel_list = self.local_channel_list
            self.group_combo = self.local_group_combo
            self.channel_empty_label = self.local_empty_label

        if self.channel_list.viewMode() == QListWidget.ViewMode.IconMode:
            tab = 'sub' if index == 0 else 'local'
            QTimer.singleShot(200, lambda: self._capture_visible_thumbnails(tab))

    def on_sub_group_changed(self, group_name):
        """订阅标签分组切换"""
        self._populate_channel_list_for(self.sub_channel_list, self._sub_channels, group_name)
        if self.sub_channel_list.viewMode() == QListWidget.ViewMode.IconMode:
            QTimer.singleShot(200, lambda: self._capture_visible_thumbnails('sub'))

    def on_local_group_changed(self, group_name):
        """本地标签分组切换"""
        self._populate_channel_list_for(self.local_channel_list, self._local_channels, group_name)
        if self.local_channel_list.viewMode() == QListWidget.ViewMode.IconMode:
            QTimer.singleShot(200, lambda: self._capture_visible_thumbnails('local'))
    
    def _create_bottom_panel(self, show=True):
        """创建底部悬浮控制面板"""
        logger.debug("_create_bottom_panel: 开始")
        
        # 第一步：创建底部面板
        self._create_panel(show=show)
        
        logger.debug("_create_bottom_panel: 完成")
    
    def _create_panel(self, show=True):
        """创建底部控制面板（QDockWidget 停靠底部）"""
        logger.debug("_create_panel: 开始")
        tr = self.language_manager.tr

        # 控制面板内容容器
        floating_container = QWidget()
        floating_container.setStyleSheet(AppStyles.player_panel_style())
        floating_container.setFixedHeight(170)
        floating_container.setMinimumWidth(600)
        self.floating_layout = QVBoxLayout(floating_container)
        self.floating_layout.setContentsMargins(15, 6, 15, 8)
        self.floating_layout.setSpacing(3)

        # 创建媒体信息行
        self._create_media_row()

        # 用 FloatingDockWidget 包装（圆角半透明 + Qt管理）
        from PyQt6.QtWidgets import QDockWidget
        from ui.floating_dialog import FloatingDockWidget
        self.floating_dock = FloatingDockWidget(tr("control_panel", "Control Panel"), self)
        self.floating_dock.setWidget(floating_container)
        self.floating_dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetClosable)
        self.floating_dock.setObjectName("floating_dock")
        if hasattr(self, 'floating_panel'):
            delattr(self, 'floating_panel')
        self.floating_panel = self.floating_dock

        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.floating_dock)
        self.floating_dock.setFloating(True)
        if not show:
            self.floating_dock.hide()

        logger.debug("_create_panel: 完成")
    
    def _create_media_row(self):
        """创建媒体信息行"""
        logger.debug("_create_media_row: 开始")
        tr = self.language_manager.tr
        
        # 第一行：媒体信息（详细版）
        self.media_row = QHBoxLayout()
        self.media_row.setSpacing(12)
        
        self.video_info = QLabel(f"📺 {tr('not_playing', 'Not playing')}")
        self.video_info.setStyleSheet(AppStyles.player_media_badge_style())
        self.video_info.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.video_info.setFixedHeight(22)
        self.media_row.addWidget(self.video_info)
        
        self.audio_info = QLabel("🔊 --")
        self.audio_info.setStyleSheet(AppStyles.player_media_badge_style())
        self.audio_info.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.audio_info.setFixedHeight(18)
        self.media_row.addWidget(self.audio_info)
        
        self.network_info = QLabel("📡 --")
        self.network_info.setStyleSheet(AppStyles.player_media_badge_style())
        self.network_info.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.network_info.setFixedHeight(18)
        self.media_row.addWidget(self.network_info)

        self.buffer_info = QLabel("")
        self.buffer_info.setStyleSheet(AppStyles.player_media_badge_style())
        self.buffer_info.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.buffer_info.setFixedHeight(18)
        self.buffer_info.hide()
        self.media_row.addWidget(self.buffer_info)
        
        self.media_row.addStretch()
        self.floating_layout.addLayout(self.media_row)
        
        # 分隔线
        line1 = QFrame()
        line1.setFrameShape(QFrame.Shape.HLine)
        line1.setStyleSheet(AppStyles.player_line_style())
        self.floating_layout.addWidget(line1)
        
        # 第三步：创建节目信息行
        self._create_info_row()
        
        logger.debug("_create_media_row: 完成")
    
    def _create_info_row(self):
        """创建节目信息行"""
        logger.debug("_create_info_row: 开始")
        tr = self.language_manager.tr

        # 信息区：LOGO在左(跨全高居中)，右侧两行文字自适应
        info_layout = QHBoxLayout()
        info_layout.setSpacing(12)

        # 左侧：频道LOGO
        self.channel_logo = QLabel()
        self.channel_logo.setStyleSheet(AppStyles.player_channel_logo_style())
        self.channel_logo.setFixedSize(100, 36)
        self.channel_logo.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter)
        from utils.general_utils import set_default_channel_logo
        set_default_channel_logo(self.channel_logo, 100, 36)
        info_layout.addWidget(self.channel_logo, 0, Qt.AlignmentFlag.AlignVCenter)

        # 右侧：两行文字区
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        text_layout.setContentsMargins(0, 0, 0, 0)

        # 第一行：频道名称 + 节目名称 + 时间 + 播放状态
        row1 = QHBoxLayout()
        row1.setSpacing(8)
        self.channel_name = QLabel(tr("no_channel_selected", "No channel selected"))
        self.channel_name.setStyleSheet(AppStyles.player_channel_name_style())
        row1.addWidget(self.channel_name, 0)
        self.current_program = QLabel("")
        self.current_program.setStyleSheet(AppStyles.player_program_style())
        self.current_program.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        row1.addWidget(self.current_program, 1)
        self.time_label = QLabel("⏱ --:-- - --:--")
        self.time_label.setStyleSheet(AppStyles.player_time_badge_style())
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row1.addWidget(self.time_label, 0)
        self.catchup_indicator = QLabel("")
        self.catchup_indicator.setStyleSheet(AppStyles.player_catchup_indicator_style())
        self.catchup_indicator.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.catchup_indicator.hide()
        row1.addWidget(self.catchup_indicator, 0)
        self.remain_label = QLabel(tr("waiting_to_play", "Waiting to play..."))
        self.remain_label.setStyleSheet(AppStyles.player_status_badge_style())
        self.remain_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.remain_label.setMinimumWidth(70)
        row1.addWidget(self.remain_label, 0)
        text_layout.addLayout(row1)

        # 第二行：节目描述（自动换行，占据剩余空间）
        self.program_desc = QLabel(tr("open_playlist_or_import", "Open a playlist file or import channels to start watching"))
        self.program_desc.setStyleSheet(AppStyles.player_program_desc_style())
        self.program_desc.setWordWrap(True)
        self.program_desc.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        text_layout.addWidget(self.program_desc, 1)

        info_layout.addLayout(text_layout, 1)

        self.floating_layout.addLayout(info_layout)
        
        # 分隔线
        line2 = QFrame()
        line2.setFrameShape(QFrame.Shape.HLine)
        line2.setStyleSheet(AppStyles.player_line_style())
        self.floating_layout.addWidget(line2)
        
        # 第四步：创建控制行
        self._create_control_row()
        
        logger.debug("_create_info_row: 完成")
    
    def _create_control_row(self):
        """创建控制行"""
        logger.debug("_create_control_row: 开始")
        
        # 第三行：播放控制 + 节目进度条
        self.control_row = QHBoxLayout()
        self.control_row.setSpacing(8)
        
        # 左侧：播放按钮
        self.play_button = QToolButton()
        self.play_button.setText("▶")
        self.play_button.setFixedSize(28, 26)
        self.play_button.setStyleSheet(AppStyles.player_button_style())
        self.play_button.clicked.connect(self.toggle_play)
        self.control_row.addWidget(self.play_button)

        # 停止按钮
        self.stop_button = QToolButton()
        self.stop_button.setText("■")
        self.stop_button.setFixedSize(28, 26)
        self.stop_button.setStyleSheet(AppStyles.player_button_style())
        self.stop_button.clicked.connect(self.stop_playback)
        self.control_row.addWidget(self.stop_button)
        
        self.control_row.addStretch()
        
        # 中间：时间进度条组（居中）
        self.progress_group = QHBoxLayout()
        self.progress_group.setSpacing(4)
        
        # 当前节目开始时间
        self.progress_start = QLabel("--:--")
        self.progress_start.setStyleSheet(AppStyles.player_progress_label_style())
        self.progress_group.addWidget(self.progress_start)
        
        # 时间进度条
        self.program_progress = QSlider(Qt.Orientation.Horizontal)
        self.program_progress.setRange(0, 3600)
        self.program_progress.setValue(0)
        self.program_progress.setSingleStep(1)
        self.program_progress.setPageStep(30)
        self.program_progress.setFixedWidth(450)
        self.program_progress.setStyleSheet(AppStyles.player_slider_style())
        self.program_progress.sliderReleased.connect(self.on_progress_slider_released)
        self._progress_total_seconds = 3600
        self.progress_group.addWidget(self.program_progress)
        
        # 当前节目结束时间
        self.progress_end = QLabel("--:--")
        self.progress_end.setStyleSheet(AppStyles.player_progress_label_style())
        self.progress_group.addWidget(self.progress_end)
        
        self.control_row.addLayout(self.progress_group)
        
        self.control_row.addStretch()
        
        # 5. 音量图标
        self.volume_button = QToolButton()
        self.volume_button.setText("🔊")
        self.volume_button.setFixedSize(28, 26)
        self.volume_button.setStyleSheet(AppStyles.player_button_style())
        self.volume_button.clicked.connect(self.toggle_mute)
        self.control_row.addWidget(self.volume_button)
        
        # 6. 音量调节拖动条
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(80)
        self.volume_slider.setFixedWidth(80)
        self.volume_slider.setStyleSheet(AppStyles.player_volume_slider_style())
        self.volume_slider.valueChanged.connect(self.set_volume)
        self.control_row.addWidget(self.volume_slider)
        
        # 7. 退出回看按钮（初始隐藏）
        self.exit_catchup_button = QToolButton()
        self.exit_catchup_button.setText("⏪ 退出回看")
        self.exit_catchup_button.setFixedSize(100, 26)
        self.exit_catchup_button.setStyleSheet(AppStyles.exit_catchup_button_style())
        self.exit_catchup_button.clicked.connect(self.exit_catchup)
        self.exit_catchup_button.hide()
        self.control_row.addWidget(self.exit_catchup_button)

        # 7.5 速度控制按钮
        self.speed_button = QToolButton()
        self.speed_button.setText("1.0x")
        self.speed_button.setFixedSize(42, 26)
        self.speed_button.setStyleSheet(AppStyles.player_button_style())
        self.speed_button.clicked.connect(self._cycle_speed)
        self.control_row.addWidget(self.speed_button)

        # 7.6 画面比例按钮
        self.aspect_button = QToolButton()
        self.aspect_button.setText("📐")
        self.aspect_button.setFixedSize(48, 26)
        self.aspect_button.setStyleSheet(AppStyles.player_button_style())
        self.aspect_button.clicked.connect(self._cycle_aspect_ratio)
        self.control_row.addWidget(self.aspect_button)

        # 7.7 音轨切换按钮
        self.audio_track_button = QToolButton()
        self.audio_track_button.setText("🔊T")
        self.audio_track_button.setFixedSize(36, 26)
        self.audio_track_button.setStyleSheet(AppStyles.player_button_style())
        self.audio_track_button.clicked.connect(self._show_audio_track_menu)
        self.control_row.addWidget(self.audio_track_button)

        # 7.8 字幕切换按钮
        self.sub_track_button = QToolButton()
        self.sub_track_button.setText("💬S")
        self.sub_track_button.setFixedSize(36, 26)
        self.sub_track_button.setStyleSheet(AppStyles.player_button_style())
        self.sub_track_button.clicked.connect(self._show_sub_track_menu)
        self.control_row.addWidget(self.sub_track_button)
        
        # 8. 全屏图标
        self.fullscreen_button = QToolButton()
        self.fullscreen_button.setText("⛶")
        self.fullscreen_button.setFixedSize(28, 26)
        self.fullscreen_button.setStyleSheet(AppStyles.player_button_style())
        self.fullscreen_button.clicked.connect(self.toggle_fullscreen)
        self.control_row.addWidget(self.fullscreen_button)
        
        self.floating_layout.addLayout(self.control_row)
        
        logger.debug("_create_control_row: 完成")
    
    def _final_initialization(self):
        """最终初始化"""
        logger.debug("_final_initialization: 完成")

    def _install_event_filters(self):
        """安装事件过滤器（幂等：多次调用只生效一次）"""
        if getattr(self, '_event_filters_installed', False):
            logger.debug("_install_event_filters: 已安装，跳过")
            return
        self._event_filters_installed = True
        logger.debug("_install_event_filters: 开始")
        
        # 安装事件过滤器
        if self.video_frame:
            self.video_frame.installEventFilter(self)
        if self.video_widget:
            self.video_widget.setMouseTracking(True)
            self.video_widget.installEventFilter(self)
        if self.video_placeholder:
            self.video_placeholder.installEventFilter(self)
        
        # 安装 QApplication 级别事件过滤器（用于全局快捷键）
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        if app:
            app.installEventFilter(self)
        
        self._populate_channel_list(source='subscription')
        
        logger.debug("_install_event_filters: 完成")
    
    def populate_channel_list_ui(self):
        """填充频道列表UI（委托给ChannelController）"""
        self.channel_ctrl.populate_channel_list()

    def populate_epg_list_ui(self):
        """填充EPG列表（公共方法，用于 QMetaObject.invokeMethod 调用）"""
        self._populate_epg_list()
    
    def check_for_updates_ui(self):
        """检查版本更新（公共方法，用于 QMetaObject.invokeMethod 调用）"""
        self._check_for_updates_async()
    
    def _populate_channel_list(self, source='subscription'):
        """填充频道列表（带防重复机制）"""
        import time
        current_time = time.time()
        if hasattr(self, '_last_populate_time') and current_time - self._last_populate_time < 0.5:
            logger.debug(f"_populate_channel_list: 跳过重复调用（距上次{current_time - self._last_populate_time:.2f}秒）")
            return
        self._last_populate_time = current_time

        logger.debug("_populate_channel_list: 开始")

        self.populate_channel_list(source=source)

        self._populate_epg_list()

        logger.debug("_populate_channel_list: 完成")
    
    def _populate_epg_list(self):
        """填充EPG列表"""
        logger.debug("_populate_epg_list: 开始")
        
        # 延迟填充EPG列表，等待EPG数据下载完成
        self.populate_epg_list()
        
        logger.debug("_populate_epg_list: 完成")
    
    def _update_floating_position(self):
        """更新悬浮窗位置"""
        logger.debug("_update_floating_position: 开始")
        
        # 使用定时器延迟更新悬浮窗位置，确保窗口已显示
        self.update_floating_position()
        
        logger.debug("_update_floating_position: 完成")

    def _deferred_initial_position(self):
        """窗口首次渲染后的延迟定位：
        1. 先定位三个悬浮 dock（无论可见性）
        2. 再按初始可见性标志 show() 各面板
        3. 同步 video_placeholder / video_widget 到 video_frame 的实际尺寸
        """
        if getattr(self, '_initial_position_fixed', False):
            return
        self._initial_position_fixed = True

        # 1. 定位（_position_floating_docks 已改为不依赖 isVisible）
        self.update_floating_position()

        # 2. 按初始状态决定是否 show
        if getattr(self, 'epg_visible', True) and getattr(self, 'epg_panel', None):
            self.epg_panel.show()
        if getattr(self, 'playlist_visible', True) and getattr(self, 'playlist_panel', None):
            self.playlist_panel.show()
        if getattr(self, 'floating_panel_visible', True) and getattr(self, 'floating_panel', None):
            self.floating_panel.show()

        # 3. 同步视频区域子控件尺寸
        if hasattr(self, 'video_frame') and self.video_frame:
            w, h = self.video_frame.width(), self.video_frame.height()
            if w > 0 and h > 0:
                if hasattr(self, 'video_widget') and self.video_widget:
                    self.video_widget.setGeometry(0, 0, w, h)
                if hasattr(self, 'video_placeholder') and self.video_placeholder:
                    self.video_placeholder.setGeometry(0, 0, w, h)


    def _start_subscription_timers(self):
        """启动订阅更新定时器"""
        logger.debug("_start_subscription_timers: 开始")
        self.start_subscription_timers()
        logger.debug("_start_subscription_timers: 完成")
    
    def _update_recent_files_menu(self):
        """初始化最近打开文件菜单"""
        logger.debug("_update_recent_files_menu: 开始")
        
        # 初始化最近打开文件菜单
        self.update_recent_files_menu()
        
        self._panels_initialized = True
        self._initialization_complete = True
        self._restart_auto_hide_timer()
        

        
        logger.debug("_update_recent_files_menu: 完成")
    
    def update_status_bar(self, message):
        """更新状态栏消息"""
        if self.status_bar:
            self.status_bar.showMessage(message)
    
    def setup_menu_bar(self, skip_recent_files=False):
        """设置菜单栏"""
        from PyQt6.QtWidgets import QMenuBar
        if hasattr(self, '_custom_menu_bar') and self._custom_menu_bar:
            menu_bar = self._custom_menu_bar
            menu_bar.clear()
        else:
            menu_bar = QMenuBar()
            menu_bar.setObjectName("customMenuBar")
            self._custom_menu_bar = menu_bar

        # 设置菜单栏样式
        menu_bar.setStyleSheet(AppStyles.player_menu_bar_style())
        
        try:
            tr = self.language_manager.tr
            
            # 文件菜单
            file_menu = menu_bar.addMenu(tr("menu_file", "File"))
            recent_menu = None
            if file_menu:
                open_playlist = QAction(tr("menu_open_playlist", "Open Playlist\tCtrl+O"), self)
                open_playlist.triggered.connect(self.open_playlist)
                file_menu.addAction(open_playlist)

                open_stream = QAction(tr("menu_open_stream", "Open Stream\tCtrl+U"), self)
                open_stream.triggered.connect(self._open_stream)
                file_menu.addAction(open_stream)

                open_video = QAction(tr("menu_open_video", "Open Video\tCtrl+Shift+O"), self)
                open_video.triggered.connect(self._open_video_file)
                file_menu.addAction(open_video)

                # 添加最近打开子菜单
                recent_menu = file_menu.addMenu(tr("menu_recent_open", "Recent"))

                save_as = QAction(tr("menu_save_as", "Save As...\tCtrl+S"), self)
                save_as.triggered.connect(self.save_as)
                file_menu.addAction(save_as)

                file_menu.addSeparator()

                exit_action = QAction(tr("menu_exit", "Exit\tCtrl+Q"), self)
                exit_action.triggered.connect(self.close)
                file_menu.addAction(exit_action)
            
            # 保存最近打开菜单引用
            self.recent_menu = recent_menu
            
            # 初始化最近打开文件列表（如果需要）
            if not skip_recent_files:
                self.update_recent_files_menu()

            # 播放菜单
            playback_menu = menu_bar.addMenu(tr("menu_playback", "Playback"))

            prev_channel = QAction(tr("menu_prev_channel", "Previous Channel\t↑"), self)
            prev_channel.triggered.connect(lambda: self.event_handler._switch_channel(-1) if hasattr(self, 'event_handler') else None)
            playback_menu.addAction(prev_channel)

            next_channel = QAction(tr("menu_next_channel", "Next Channel\t↓"), self)
            next_channel.triggered.connect(lambda: self.event_handler._switch_channel(1) if hasattr(self, 'event_handler') else None)
            playback_menu.addAction(next_channel)

            prev_channel2 = QAction(tr("menu_prev_channel2", "Previous Channel (Alt)\tCtrl+Shift+←"), self)
            prev_channel2.triggered.connect(lambda: self.event_handler._switch_channel(-1) if hasattr(self, 'event_handler') else None)
            playback_menu.addAction(prev_channel2)

            next_channel2 = QAction(tr("menu_next_channel2", "Next Channel (Alt)\tCtrl+Shift+→"), self)
            next_channel2.triggered.connect(lambda: self.event_handler._switch_channel(1) if hasattr(self, 'event_handler') else None)
            playback_menu.addAction(next_channel2)

            back_channel = QAction(tr("menu_back_channel", "Switch Back\tBackspace"), self)
            back_channel.triggered.connect(lambda: self.switch_to_previous_channel() if hasattr(self, 'switch_to_previous_channel') else None)
            playback_menu.addAction(back_channel)

            playback_menu.addSeparator()

            play_pause = QAction(tr("menu_play_pause", "Play/Pause\tSpace"), self)
            play_pause.triggered.connect(lambda: self.playback_ctrl.toggle_play() if hasattr(self, 'playback_ctrl') else None)
            playback_menu.addAction(play_pause)

            stop_play = QAction(tr("menu_stop", "Stop\tEsc"), self)
            stop_play.triggered.connect(lambda: self.playback_ctrl.stop_playback() if hasattr(self, 'playback_ctrl') else None)
            playback_menu.addAction(stop_play)

            playback_menu.addSeparator()

            vol_up = QAction(tr("menu_vol_up", "Volume Up\t→"), self)
            vol_up.triggered.connect(lambda: self.event_handler._adjust_volume(5) if hasattr(self, 'event_handler') else None)
            playback_menu.addAction(vol_up)

            vol_down = QAction(tr("menu_vol_down", "Volume Down\t←"), self)
            vol_down.triggered.connect(lambda: self.event_handler._adjust_volume(-5) if hasattr(self, 'event_handler') else None)
            playback_menu.addAction(vol_down)

            mute_action = QAction(tr("menu_mute", "Mute\tCtrl+M"), self)
            mute_action.triggered.connect(lambda: self.toggle_mute() if hasattr(self, 'toggle_mute') else None)
            playback_menu.addAction(mute_action)

            playback_menu.addSeparator()

            speed_up = QAction(tr("menu_speed_up", "Speed Up\t."), self)
            speed_up.triggered.connect(lambda: self._adjust_speed(0.1) if hasattr(self, '_adjust_speed') else None)
            playback_menu.addAction(speed_up)

            speed_down = QAction(tr("menu_speed_down", "Speed Down\t,"), self)
            speed_down.triggered.connect(lambda: self._adjust_speed(-0.1) if hasattr(self, '_adjust_speed') else None)
            playback_menu.addAction(speed_down)

            playback_menu.addSeparator()

            screenshot = QAction(tr("menu_screenshot", "Screenshot\tS"), self)
            screenshot.triggered.connect(lambda: self._take_screenshot() if hasattr(self, '_take_screenshot') else None)
            playback_menu.addAction(screenshot)

            # 视图菜单
            view_menu = menu_bar.addMenu(tr("menu_view", "View"))
            
            show_epg = QAction(tr("menu_epg_list", "EPG List\tE"), self)
            show_epg.setCheckable(True)
            show_epg.setChecked(self.epg_visible)
            show_epg.triggered.connect(self.toggle_epg)
            view_menu.addAction(show_epg)

            show_playlist = QAction(tr("menu_playlist", "Playlist\tL"), self)
            show_playlist.setCheckable(True)
            show_playlist.setChecked(self.playlist_visible)
            show_playlist.triggered.connect(self.toggle_playlist)
            view_menu.addAction(show_playlist)

            show_floating = QAction(tr("menu_control_panel", "Control Panel\tM"), self)
            show_floating.setCheckable(True)
            show_floating.setChecked(self.floating_panel_visible)
            show_floating.triggered.connect(self.toggle_floating_panel)
            view_menu.addAction(show_floating)

            hide_all_floating = QAction(tr("menu_hide_floating", "Hide Floating Panels\tY"), self)
            hide_all_floating.triggered.connect(lambda: self.toggle_hide_floating())
            view_menu.addAction(hide_all_floating)
            self._hide_floating_action = hide_all_floating

            show_osd = QAction(tr("menu_osd_toggle", "OSD Mask\tTab"), self)
            show_osd.setCheckable(True)
            show_osd.setChecked(self._osd_visible)
            show_osd.triggered.connect(lambda c: self.toggle_osd(c))
            view_menu.addAction(show_osd)
            self._osd_menu_action = show_osd

            view_menu.addSeparator()
            
            fullscreen = QAction(tr("menu_fullscreen", "Fullscreen\tF11"), self)
            fullscreen.setCheckable(True)
            fullscreen.triggered.connect(self.toggle_fullscreen)
            view_menu.addAction(fullscreen)

            pip_action = QAction(tr("menu_pip", "Picture-in-Picture\tP"), self)
            pip_action.setCheckable(True)
            pip_action.triggered.connect(self.toggle_pip_mode)
            view_menu.addAction(pip_action)
            self._pip_menu_action = pip_action

            refresh = QAction(tr("menu_refresh", "Refresh\tF5"), self)
            refresh.triggered.connect(self.refresh_ui)
            view_menu.addAction(refresh)
            
            reset_layout = QAction(tr("menu_reset_layout", "Reset Layout"), self)
            reset_layout.triggered.connect(self.reset_layout)
            view_menu.addAction(reset_layout)
            
            # 工具菜单
            tools_menu = menu_bar.addMenu(tr("menu_tools", "Tools"))
            
            scan_channels = QAction(tr("menu_scan_channels", "Scan & Organize"), self)
            scan_channels.triggered.connect(self.open_scan_ui)
            tools_menu.addAction(scan_channels)
            
            channel_mapping = QAction(tr("menu_mapping", "Mapping"), self)
            channel_mapping.triggered.connect(self.open_channel_mapping)
            tools_menu.addAction(channel_mapping)
            
            tools_menu.addSeparator()
            
            player_settings = QAction(tr("menu_subscription_settings", "Subscription Settings"), self)
            player_settings.triggered.connect(self.player_settings)
            tools_menu.addAction(player_settings)

            tools_menu.addSeparator()

            file_assoc = QAction(tr("menu_file_association", "File Association"), self)
            file_assoc.triggered.connect(self._toggle_file_association)
            tools_menu.addAction(file_assoc)
            
            # 语言菜单
            language_menu = menu_bar.addMenu(tr("language", "Language"))
            
            # 获取当前语言
            current_language = self.language_manager.current_language
            
            chinese = QAction(tr("chinese", "中文"), self)
            chinese.setCheckable(True)
            chinese.setChecked(current_language == "zh")
            chinese.triggered.connect(lambda: self.set_language("zh"))
            language_menu.addAction(chinese)
            
            english = QAction(tr("english", "English"), self)
            english.setCheckable(True)
            english.setChecked(current_language == "en")
            english.triggered.connect(lambda: self.set_language("en"))
            language_menu.addAction(english)
            
            # 主题菜单
            theme_menu = menu_bar.addMenu(tr("menu_theme", "Theme"))

            theme_manager = self._theme_manager

            themes = theme_manager.get_available_themes()

            from PyQt6.QtGui import QActionGroup
            theme_group = QActionGroup(self)
            theme_group.setExclusive(True)

            for theme in themes:
                theme_display = tr(theme, theme)
                theme_action = QAction(theme_display, self)
                theme_action.setCheckable(True)
                theme_action.setChecked(theme == theme_manager.get_current_theme())
                theme_action.triggered.connect(lambda checked, t=theme: self.set_theme(t))
                theme_group.addAction(theme_action)
                theme_menu.addAction(theme_action)
            
            # 帮助菜单
            help_menu = menu_bar.addMenu(tr("menu_help", "Help"))
            
            usage_instructions = QAction(tr("menu_instructions", "Instructions"), self)
            usage_instructions.triggered.connect(self.show_usage_instructions)
            help_menu.addAction(usage_instructions)
            
            about = QAction(tr("menu_about", "About"), self)
            about.triggered.connect(self.show_about)
            help_menu.addAction(about)
            
        except Exception as e:
            logger.error(f"创建菜单栏失败: {str(e)}")

        # 将自定义菜单栏插入到标题栏和内容区域之间（仅首次插入）
        if hasattr(self, '_custom_menu_bar') and self._custom_menu_bar and hasattr(self, 'main_layout'):
            if self._custom_menu_bar.parent() != self._main_container:
                self.main_layout.insertWidget(1, self._custom_menu_bar)

    def update_channel_groups(self):
        """从CHANNELS中提取分组并更新下拉框（委托给SubscriptionController）"""
        self.subscription_ctrl.update_channel_groups()

    def populate_channel_list(self, source='subscription'):
        """填充频道列表

        Args:
            source: 'subscription' 填充订阅标签, 'local' 填充本地标签,
                    'auto' 自动判断（默认填充当前活跃标签）
        """
        if source == 'auto':
            if not hasattr(self, 'playlist_tab'):
                source = 'subscription'
            else:
                source = 'subscription' if self.playlist_tab.currentIndex() == 0 else 'local'

        if source == 'subscription':
            self._sub_channels = list(app_state._channels)
            self._update_groups_for('subscription')
            self._populate_channel_list_for(self.sub_channel_list, self._sub_channels,
                                            self.sub_group_combo.currentText())
        else:
            self._update_groups_for('local')
            self._populate_channel_list_for(self.local_channel_list, self._local_channels,
                                            self.local_group_combo.currentText())

    def _update_groups_for(self, source):
        """更新指定源的分组下拉框"""
        channels = self._sub_channels if source == 'subscription' else self._local_channels
        combo = self.sub_group_combo if source == 'subscription' else self.local_group_combo
        groups_attr = '_sub_groups' if source == 'subscription' else '_local_groups'

        tr = self.language_manager.tr
        all_channels_text = tr("all_channels", "All Channels")

        groups = []
        seen = set()
        for channel in channels:
            for g in channel.get('_groups', [channel.get('group', '') or '未分类']):
                if g and g not in seen:
                    groups.append(g)
                    seen.add(g)

        new_groups = [all_channels_text] + groups
        old_groups = getattr(self, groups_attr, [])

        if new_groups == old_groups:
            return

        setattr(self, groups_attr, new_groups)

        current_text = combo.currentText() if combo.currentText() else all_channels_text
        combo.blockSignals(True)
        combo.clear()
        combo.addItems(new_groups)
        if current_text in new_groups:
            combo.setCurrentText(current_text)
        elif new_groups:
            combo.setCurrentIndex(0)
        combo.blockSignals(False)

    def _populate_channel_list_for(self, list_widget, channels, selected_group=''):
        """通用频道列表填充方法"""
        from core.log_manager import global_logger as logger

        list_widget.clear()

        all_channels_text = self.language_manager.tr("all_channels", "All Channels")
        is_all_channels = (
            not selected_group or
            selected_group.lower() == 'all channels' or
            selected_group == all_channels_text or
            selected_group == 'All Channels'
        )

        added_count = 0
        error_count = 0
        skipped_count = 0

        for idx, channel in enumerate(channels):
            try:
                if not is_all_channels:
                    channel_groups = channel.get('_groups', [channel.get('group', '')])
                    if selected_group not in channel_groups:
                        skipped_count += 1
                        continue

                channel_name = channel.get("name", self.language_manager.tr("unnamed", "Unnamed"))
                logo_url = channel.get('logo', '')

                try:
                    is_grid = list_widget.viewMode() == QListWidget.ViewMode.IconMode

                    if is_grid:
                        item = QListWidgetItem()
                        item.setText(channel_name)
                        item.setData(Qt.ItemDataRole.UserRole, idx)
                        item.setSizeHint(QSize(220, 140))
                        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

                        list_widget.addItem(item)
                    else:
                        item_widget = QtWidgets.QWidget()
                        item_layout = QHBoxLayout(item_widget)
                        item_layout.setContentsMargins(5, 5, 5, 5)
                        item_layout.setSpacing(10)

                        logo_label = QtWidgets.QLabel()
                        logo_label.setFixedSize(48, 34)
                        logo_label.setStyleSheet("background-color: transparent; border: none;")
                        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                        logo_label.setObjectName("channel_logo_label")

                        name_label = QtWidgets.QLabel(channel_name)
                        from ui.styles import AppStyles
                        colors = AppStyles._get_colors()
                        name_label.setStyleSheet(f"font-size: 12px; font-weight: bold; color: {colors['player_panel_text']};")
                        name_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
                        name_label.setWordWrap(False)

                        item_layout.addWidget(logo_label, 0, Qt.AlignmentFlag.AlignVCenter)
                        item_layout.addWidget(name_label, 1, Qt.AlignmentFlag.AlignVCenter)

                        item = QListWidgetItem()
                        item.setSizeHint(QSize(0, 42))
                        item.setData(Qt.ItemDataRole.UserRole, idx)

                        list_widget.addItem(item)
                        list_widget.setItemWidget(item, item_widget)

                    added_count += 1

                except Exception as widget_ex:
                    simple_item = QListWidgetItem(channel_name)
                    simple_item.setData(Qt.ItemDataRole.UserRole, idx)
                    list_widget.addItem(simple_item)
                    added_count += 1
                    error_count += 1
                    if error_count <= 3:
                        logger.warning(f"第{idx}个频道的自定义widget创建失败，使用简单文本: {widget_ex}")

            except Exception as e:
                error_count += 1
                if error_count <= 3:
                    logger.error(f"populate_channel_list: 添加第{idx}个频道失败: {e}")

        empty_label = None
        if list_widget is self.sub_channel_list:
            empty_label = self.sub_empty_label
        elif list_widget is self.local_channel_list:
            empty_label = self.local_empty_label

        if empty_label:
            if added_count == 0:
                empty_label.show()
            else:
                empty_label.hide()

        if error_count > 0:
            logger.warning(f"populate_channel_list: 共 {error_count} 个频道添加失败")
        if skipped_count > 0:
            logger.warning(f"populate_channel_list: 共 {skipped_count} 个频道被分组过滤跳过")

        logger.info(f"populate_channel_list: 填充完成，共 {list_widget.count()} 个频道项（实际添加: {added_count}, 跳过: {skipped_count}, 总数据: {len(channels)}）")
        list_widget.verticalScrollBar().valueChanged.connect(self._on_channel_list_scrolled)
        QTimer.singleShot(50, lambda: self._load_visible_icons(list_widget, channels))
    
    def _load_visible_icons(self, list_widget, channels):
        """异步分批加载可见区域的台标/缩略图"""
        if not hasattr(self, '_icon_load_queue'):
            self._icon_load_queue = []
            self._icon_load_timer = QTimer(self)
            self._icon_load_timer.setInterval(16)
            self._icon_load_timer.timeout.connect(self._process_icon_load_batch)

        viewport_rect = list_widget.viewport().rect()
        top_index = list_widget.indexAt(viewport_rect.topLeft())
        bottom_index = list_widget.indexAt(viewport_rect.bottomLeft())

        first_visible = top_index.row() if top_index.isValid() else 0
        last_visible = bottom_index.row() if bottom_index.isValid() else list_widget.count() - 1
        first_visible = max(0, first_visible - 3)
        last_visible = min(list_widget.count() - 1, last_visible + 3)

        is_grid = list_widget.viewMode() == QListWidget.ViewMode.IconMode
        need_capture = []
        queue_items = []

        for i in range(first_visible, last_visible + 1):
            item = list_widget.item(i)
            if not item:
                continue
            channel_idx = item.data(Qt.ItemDataRole.UserRole)
            if channel_idx is None or channel_idx >= len(channels):
                continue
            channel = channels[channel_idx]
            logo_url = channel.get('logo', '').strip('`"\'')

            if is_grid:
                if not item.icon().isNull():
                    continue
                ch_url = channel.get('url', '')
                if self.player_controller and ch_url:
                    thumb_path = self.player_controller.get_thumbnail_path(ch_url)
                    if thumb_path:
                        queue_items.append(('grid_thumb', item, thumb_path, None))
                        continue
                if logo_url:
                    cached = self._logo_cache_service.get(logo_url)
                    if cached:
                        queue_items.append(('grid_logo', item, None, cached))
                    else:
                        self._logo_cache_service.fetch_async(logo_url)
                if ch_url:
                    need_capture.append(channel)
            else:
                item_widget = list_widget.itemWidget(item)
                if not item_widget:
                    continue
                logo_label = item_widget.findChild(QtWidgets.QLabel, "channel_logo_label")
                if not logo_label:
                    continue
                if logo_label.pixmap() and not logo_label.pixmap().isNull():
                    continue
                if logo_url:
                    cached = self._logo_cache_service.get(logo_url)
                    if cached:
                        queue_items.append(('list_logo', item, logo_label, cached))
                    else:
                        self._logo_cache_service.fetch_async(logo_url)

        self._icon_load_queue.extend(queue_items)
        if self._icon_load_queue and not self._icon_load_timer.isActive():
            self._icon_load_timer.start()

        if need_capture and hasattr(self, '_thumbnail_service'):
            self._thumbnail_service.capture_channels(need_capture, force=True)

    def _process_icon_load_batch(self):
        """每帧处理少量图标加载，避免UI卡顿"""
        if not hasattr(self, '_icon_load_queue') or not self._icon_load_queue:
            if hasattr(self, '_icon_load_timer'):
                self._icon_load_timer.stop()
            return

        batch_size = 3
        for _ in range(batch_size):
            if not self._icon_load_queue:
                break
            task = self._icon_load_queue.pop(0)
            try:
                kind = task[0]
                if kind == 'grid_thumb':
                    _, item, thumb_path, _ = task
                    px = QPixmap(thumb_path)
                    if not px.isNull():
                        scaled = px.scaled(210, 118, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                        item.setIcon(QIcon(scaled))
                elif kind == 'grid_logo':
                    _, item, _, cached = task
                    if cached and not cached.isNull():
                        scaled = cached.scaled(160, 90, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                        item.setIcon(QIcon(scaled))
                elif kind == 'list_logo':
                    _, item, logo_label, cached = task
                    if cached and not cached.isNull() and logo_label:
                        scaled = self._logo_cache_service.scale_logo_pixmap_to_fit(
                            cached,
                            logo_label.width() if logo_label.width() > 0 else 48,
                            logo_label.height() if logo_label.height() > 0 else 34
                        )
                        logo_label.setPixmap(scaled)
            except RuntimeError:
                pass

        if not self._icon_load_queue:
            self._icon_load_timer.stop()

    def _on_channel_list_scrolled(self, value):
        """频道列表滚动时，加载可见区域的台标/缩略图"""
        sender = self.sender()
        if sender is self.local_channel_list:
            list_widget = self.local_channel_list
            channels = self._local_channels
        else:
            list_widget = self.sub_channel_list
            channels = self._sub_channels
        self._load_visible_icons(list_widget, channels)

    def _capture_visible_thumbnails(self, tab='sub'):
        """截取当前可见频道的缩略图（按需加载，含过期刷新）"""
        list_widget = self.sub_channel_list if tab == 'sub' else self.local_channel_list
        channels = self._sub_channels if tab == 'sub' else self._local_channels
        if list_widget.viewMode() != QListWidget.ViewMode.IconMode:
            return
        if not hasattr(self, '_thumbnail_service'):
            return

        viewport_rect = list_widget.viewport().rect()
        top_index = list_widget.indexAt(viewport_rect.topLeft())
        bottom_index = list_widget.indexAt(viewport_rect.bottomLeft())

        first_visible = top_index.row() if top_index.isValid() else 0
        last_visible = bottom_index.row() if bottom_index.isValid() else list_widget.count() - 1

        need_capture = []
        for i in range(first_visible, last_visible + 1):
            item = list_widget.item(i)
            if not item:
                continue
            channel_idx = item.data(Qt.ItemDataRole.UserRole)
            if channel_idx is None or channel_idx >= len(channels):
                continue
            channel = channels[channel_idx]
            ch_url = channel.get('url', '')
            if ch_url:
                need_capture.append(channel)

        if need_capture:
            self._thumbnail_service.capture_channels(need_capture, force=True)
    
    def populate_epg_list(self):
        """填充EPG列表（委托给EPGController）"""
        self.epg_ctrl.populate_epg_list()

    def on_epg_item_clicked(self, item):
        """处理EPG列表项点击事件（委托给EPGController）"""
        self.epg_ctrl.on_epg_item_clicked(item)

    def _replace_catchup_variables(self, catchup_source, start_time, end_time):
        """替换回看URL中的时间变量占位符（委托给CatchupController）"""
        return self.catchup_ctrl.replace_catchup_variables(catchup_source, start_time, end_time)

    def start_catchup(self, program):
        """启动回看功能（委托给CatchupController）"""
        self.catchup_ctrl.start_catchup(program)
    
    def add_exit_catchup_button(self):
        """显示退出回看按钮（委托给CatchupController）"""
        self.catchup_ctrl.add_exit_catchup_button()

    def exit_catchup(self):
        """退出回看，返回直播（委托给CatchupController）"""
        self.catchup_ctrl.exit_catchup()

    def _show_exit_timeshift_button(self):
        """显示退出时移按钮（委托给CatchupController）"""
        self.catchup_ctrl.show_exit_timeshift_button()

    def _on_timeshift_slider_seek(self):
        """时移模式下拖动进度条（委托给CatchupController）"""
        self.catchup_ctrl.on_timeshift_slider_seek()

    def _exit_timeshift(self):
        """退出时移模式（委托给CatchupController）"""
        self.catchup_ctrl.exit_timeshift()
    
    def _get_epg_match_params(self):
        """获取EPG匹配所需的参数"""
        if not self.current_channel:
            return '', '', '', ''
        channel_name = self.current_channel.get("name", "")
        tvg_id = self.current_channel.get("tvg_id", "")
        all_tags = self.current_channel.get("_all_tags", {})
        tvg_name = all_tags.get("tvg-name", "")
        comma_name = ''
        raw_extinf = self.current_channel.get('_raw_extinf', '')
        if raw_extinf and ',' in raw_extinf:
            comma_name = raw_extinf.split(',', 1)[-1].strip()
            if comma_name.startswith('"') and comma_name.endswith('"'):
                comma_name = comma_name[1:-1]
        return channel_name, tvg_id, tvg_name, comma_name

    def _is_local_file(self, channel=None):
        """判断频道是否为本地视频文件
        
        Args:
            channel: 频道字典，为None时使用 self.current_channel
        """
        ch = channel if channel is not None else self.current_channel
        if not isinstance(ch, dict):
            return False
        url = ch.get('url', '')
        if not url:
            return False
        if url.lower().startswith('file://'):
            return True
        if url.split('?')[0].lower().endswith(
            ('.mp4', '.mkv', '.avi', '.mov', '.flv', '.wmv', '.ts', '.webm', '.mp3', '.wav', '.flac')
        ):
            return True
        if not url.startswith(('http://', 'https://', 'rtmp://', 'rtsp://', 'rtp://')):
            return True
        return False

    def _update_progress_range_for_live(self):
        """根据当前节目时长动态设置进度条范围"""
        from datetime import datetime, timedelta
        
        try:
            channel_name, tvg_id, tvg_name, comma_name = self._get_epg_match_params()
            current_program = self.epg_parser.get_current_program(channel_name, tvg_id, tvg_name=tvg_name, comma_name=comma_name)
            
            if current_program:
                start_time = datetime.fromisoformat(current_program.get('start', ''))
                end_time = datetime.fromisoformat(current_program.get('end', ''))
                total_seconds = int((end_time - start_time).total_seconds())
                if total_seconds > 0:
                    self._set_progress_range(total_seconds)
                    self._progress_time_mode = 'epg'
                    self._progress_program_start = start_time
                    self._progress_program_end = end_time
                    return
        except:
            pass
        
        self._set_progress_range(3600)
        self._progress_time_mode = 'hour'
        self._progress_program_start = None
        self._progress_program_end = None
    
    def _map_slider_to_stream_position(self, slider_seconds, seek_range):
        """将进度条值(秒，从节目起始算)映射到MPV流内的绝对位置(秒)
        
        核心思路：buffer_end 是直播点（对应当前墙钟时间 now），
        目标位置 = buffer_end - (now - target_wallclock).total_seconds()
        不依赖 time_pos（直播流中 time_pos 经常为0或不可靠）
        """
        from datetime import datetime, timedelta
        
        buffer_start = seek_range.get('buffer_start', 0)
        buffer_end = seek_range.get('buffer_end', 0)
        
        if getattr(self, '_progress_time_mode', None) == 'epg' and self._progress_program_start:
            try:
                target_wallclock = self._progress_program_start + timedelta(seconds=slider_seconds)
                now = datetime.now()
                offset_from_live = (now - target_wallclock).total_seconds()
                target_pos = buffer_end - offset_from_live
                return target_pos
            except:
                pass
        
        try:
            now = datetime.now()
            hour_start = now.replace(minute=0, second=0, microsecond=0)
            target_wallclock = hour_start + timedelta(seconds=slider_seconds)
            offset_from_live = (now - target_wallclock).total_seconds()
            target_pos = buffer_end - offset_from_live
            return target_pos
        except:
            pass
        
        total_seconds = self._progress_total_seconds
        if total_seconds <= 0:
            total_seconds = 3600
        ratio = slider_seconds / total_seconds
        return buffer_start + (buffer_end - buffer_start) * ratio
    
    def _set_progress_range(self, total_seconds):
        """设置进度条范围（秒级精度，1单位=1秒）"""
        self._progress_total_seconds = total_seconds
        self.program_progress.setRange(0, int(total_seconds))
    
    def _set_progress_value(self, seconds):
        """设置进度条位置（输入为秒数），用户拖动时跳过"""
        if self.program_progress.isSliderDown():
            return
        v = max(0, min(int(seconds), self.program_progress.maximum()))
        self.program_progress.setValue(v)
    
    def _get_progress_seconds(self):
        """获取进度条当前值（秒数）"""
        return self.program_progress.value()
    
    def _get_current_program_duration(self):
        """获取当前节目的时长（秒），用于设置缓存大小"""
        try:
            if self.current_channel:
                channel_name, tvg_id, tvg_name, comma_name = self._get_epg_match_params()
                current_program = self.epg_parser.get_current_program(channel_name, tvg_id, tvg_name=tvg_name, comma_name=comma_name)
                if current_program:
                    from datetime import datetime
                    start_time = datetime.fromisoformat(current_program.get('start', ''))
                    end_time = datetime.fromisoformat(current_program.get('end', ''))
                    duration = int((end_time - start_time).total_seconds())
                    if duration > 0:
                        return duration
        except:
            pass
        return 0
    
    def _check_program_change(self):
        """检测节目是否切换，更新UI信息"""
        is_catchup = hasattr(self, 'is_catchup_mode') and self.is_catchup_mode
        if is_catchup:
            return

        if self._is_local_file():
            return

        try:
            if not self.current_channel or not self.player_controller:
                return

            channel_name, tvg_id, tvg_name, comma_name = self._get_epg_match_params()
            current_program = self.epg_parser.get_current_program(channel_name, tvg_id, tvg_name=tvg_name, comma_name=comma_name)

            if current_program:
                program_id = current_program.get('start', '') + current_program.get('end', '')
                last_id = getattr(self, '_last_program_id', None)

                if last_id != program_id:
                    logger.info(f"检测到节目切换，更新UI信息 (last={last_id}, new={program_id})")
                    self._live_timeshift_seconds = 0
                    desc = current_program.get('description', '') or self.language_manager.tr('no_program_desc', 'No program description')
                    if hasattr(self, 'program_desc') and self.program_desc:
                        self.program_desc.setText(desc)
                    if hasattr(self, 'program_progress'):
                        new_duration = self._get_current_program_duration()
                        if new_duration > 0:
                            self._set_progress_range(new_duration)
                            self._set_progress_value(0)

                self._last_program_id = program_id
            else:
                self._last_program_id = None
        except Exception as e:
            logger.debug("节目切换检测异常: {}".format(e))
    
    def on_progress_slider_released(self):
        """进度条拖动释放时的处理"""
        
        is_catchup = hasattr(self, 'is_catchup_mode') and self.is_catchup_mode

        if getattr(self, '_progress_time_mode', None) == 'vod' and not is_catchup:
            slider_seconds = self._get_progress_seconds()
            if self.player_controller:
                self.player_controller.seek_absolute(float(slider_seconds))
            return
        
        if not is_catchup:
            if not self.current_channel or not self.player_controller:
                return
            
            slider_seconds = self._get_progress_seconds()
            
            seek_range = self.player_controller.get_available_seek_range()
            max_back = seek_range.get('max_back', 0)
            cache_duration = seek_range.get('cache_duration', 0)
            buffer_start = seek_range.get('buffer_start', 0)
            buffer_end = seek_range.get('buffer_end', 0)
            time_pos = seek_range.get('time_pos', 0)
            
            logger.info(f"直播拖动进度条 -> slider={slider_seconds}s, "
                        f"time_pos={time_pos:.1f}s, buffer={buffer_start:.1f}s~{buffer_end:.1f}s, "
                        f"max_back={max_back}s, mode={getattr(self, '_progress_time_mode', '?')}")
            
            if max_back == 0 and cache_duration < 5:
                logger.warning(f"直播拖动进度条 -> 无法回退（缓冲区为空，cache={cache_duration:.1f}s）")
                self.status_bar_show_message(self.language_manager.tr("cannot_seek_live", "无法回退：直播流缓冲区不足"))
                return
            
            target_pos = self._map_slider_to_stream_position(slider_seconds, seek_range)
            
            logger.info(f"直播拖动进度条 -> 映射后 target_pos={target_pos:.1f}s, "
                        f"clamp后={max(buffer_start, min(target_pos, buffer_end)):.1f}s")
            
            # 检测是否请求的位置超出了缓冲区边界（即想跳到更早的时间点）
            if target_pos < buffer_start:
                catchup_source = self.current_channel.get('catchup_source', '') if self.current_channel else ''
                if catchup_source and getattr(self, '_progress_time_mode', None) == 'epg' and self._progress_program_start:
                    # 频道支持回看且处于EPG模式：自动以时移方式从目标时间点播放当前节目
                    self._start_live_timeshift_from_progress(slider_seconds, catchup_source)
                    return
                elif catchup_source:
                    # 有回看但没有EPG信息，只能提示
                    self.status_bar_show_message(
                        self.language_manager.tr(
                            "timeshift_beyond_cache_no_epg",
                            "超出缓冲范围，无节目信息，无法自动时移"
                        )
                    )
                else:
                    self.status_bar_show_message(
                        self.language_manager.tr(
                            "timeshift_beyond_cache",
                            "超出缓冲范围，无法跳转到更早时间"
                        )
                    )
                return
            
            target_pos = max(buffer_start, min(target_pos, buffer_end))
            
            timeshift = getattr(self, '_live_timeshift_seconds', 0)
            if timeshift > 0 and time_pos < 1:
                effective_pos = buffer_end - timeshift
            elif time_pos > 1:
                effective_pos = time_pos
            else:
                effective_pos = buffer_end
            
            if abs(target_pos - effective_pos) < 1:
                logger.info(f"直播拖动进度条 -> 跳过（目标{target_pos:.1f}s与当前位置{effective_pos:.1f}s差<1s, timeshift={timeshift}s）")
                return
            
            logger.info(f"直播拖动进度条 -> seek到 {target_pos:.1f}s")
            
            self.player_controller.seek_absolute(target_pos)
            
            if target_pos < buffer_end - 1:
                self._live_timeshift_seconds = buffer_end - target_pos
            else:
                self._live_timeshift_seconds = 0
            
            return
        
        value = self._get_progress_seconds()
        
        if self.catchup_program is not None and self.original_channel is not None:
            try:
                channel_name = self.original_channel.get("name", self.language_manager.tr("unknown_channel", "Unknown Channel"))
                catchup_source = self.original_channel.get('catchup_source', '')
                catchup_type = (self.original_channel.get('catchup', '') or '').lower().strip()
                
                if not catchup_source and not catchup_type:
                    self.status_bar_show_message(self.language_manager.tr("catchup_not_supported", "This channel does not support catchup"))
                    return
                
                start_time = self.catchup_program.get('start')
                end_time = self.catchup_program.get('end')
                title = self.catchup_program.get('title', self.language_manager.tr('unknown_program', 'Unknown Program'))
                
                if not (start_time and end_time):
                    logger.error("回看节目信息不完整")
                    self.status_bar.showMessage(self.language_manager.tr("catchup_error", "Catchup error: Missing program information"))
                    return
                
                total_duration = (end_time - start_time).total_seconds()
                
                from datetime import timedelta
                new_start_seconds = value
                new_start_time = start_time + timedelta(seconds=new_start_seconds)
                
                catchup_url = self.catchup_ctrl.build_catchup_url(self.original_channel, new_start_time, end_time)
                
                logger.debug(f"构建新的回看URL: {catchup_url}")
                
                catchup_msg = self.language_manager.tr('catchup_playing', '正在回看: {name}')
                self.status_bar.showMessage(f"{catchup_msg.format(name=channel_name)} - {title}")
                
                self._pending_catchup_progress = value
                
                import time
                self._catchup_start_time = time.time()
                self._catchup_start_progress = value
                
                # 设置标志，禁用进度条自动更新
                self._disable_progress_auto_update = True
                logger.debug(f"禁用进度条自动更新，等待播放位置达到目标值")
                
                # 播放新的回看 URL
                if hasattr(self, 'player_controller') and self.player_controller:
                    # 播放新的回看
                    self.player_controller.play(catchup_url, f"{channel_name} - {title} (回看)")
            except Exception as e:
                logger.error(f"重新构建回看 URL 失败：{e}")
                self.status_bar.showMessage(self.language_manager.tr("catchup_seek_error", "Catchup seek failed"))
        else:
            logger.error("回看模式但缺少必要信息")
            self.status_bar.showMessage(self.language_manager.tr("catchup_error", "Catchup error: Missing information"))
    
    def on_group_changed(self, group_name):
        """处理分组切换事件（委托给ChannelController）"""
        self.channel_ctrl.on_group_changed(group_name)

    def select_channel(self, item):
        from core.log_manager import global_logger as logger
        try:
            idx = item.data(Qt.ItemDataRole.UserRole)

            sender = self.sender()
            if sender is self.local_channel_list:
                channels = self._local_channels
            else:
                channels = self._sub_channels

            if isinstance(idx, int) and 0 <= idx < len(channels):
                self.current_channel = channels[idx]
            else:
                index = self.channel_list.row(item)
                if 0 <= index < len(channels):
                    self.current_channel = channels[index]
                else:
                    logger.warning(f"select_channel: 无效的索引 idx={idx}, row={index}, channels长度={len(channels)}")
                    return

            logger.info(f"select_channel: 选中频道 {self.current_channel.get('name', '?')}")

            if hasattr(self, 'current_channel') and self.current_channel:
                old = getattr(self, 'current_channel', None)
                if old and old is not self.current_channel:
                    self._previous_channel = dict(old)

            if hasattr(self, 'is_catchup_mode') and self.is_catchup_mode:
                self.playback_ctrl._exit_catchup_mode()

            self.update_channel_info_on_selection()
            if not self._is_local_file():
                self.populate_epg_list()
            self.play_channel(self.current_channel)
        except Exception as e:
            logger.error(f"select_channel: 选择频道失败: {e}", exc_info=True)
    
    def _get_display_channel_name(self, channel):
        """获取用于显示的频道名称，优先级：逗号后的名字 > tvg-name > name"""
        if not channel:
            return self.language_manager.tr("unknown_channel", "Unknown Channel")

        all_tags = channel.get('_all_tags', {})

        comma_name = ''
        raw_extinf = channel.get('_raw_extinf', '')
        if raw_extinf and ',' in raw_extinf:
            comma_name = raw_extinf.split(',', 1)[-1].strip()
            if comma_name.startswith('"') and comma_name.endswith('"'):
                comma_name = comma_name[1:-1]

        tvg_name = all_tags.get('tvg-name', '')

        if comma_name:
            return comma_name
        elif tvg_name:
            return tvg_name
        else:
            return channel.get("name", self.language_manager.tr("unknown_channel", "Unknown Channel"))

    def update_channel_info_on_selection(self):
        """选择频道时立即更新悬浮窗信息"""
        if not self.current_channel:
            return

        self._update_catchup_indicator()

        # 更新频道名称和LOGO
        display_name = self._get_display_channel_name(self.current_channel)
        self.channel_name.setText(display_name)
        self.current_program.setText("")
        logo = self.current_channel.get("logo", "")
        
        if logo:
            logo = logo.strip('`"\'')

            cached = self._logo_cache_service.get(logo)
            if cached:
                scaled_pixmap = self._logo_cache_service.scale_logo_pixmap_to_fit(cached, self.channel_logo.width(), self.channel_logo.height())
                self.channel_logo.setPixmap(scaled_pixmap)
                self.channel_logo.setText("")
                return

            self._logo_cache_service.fetch_async(logo)
            from utils.general_utils import set_default_channel_logo
            set_default_channel_logo(self.channel_logo, self.channel_logo.width(), self.channel_logo.height())
        else:
            # 没有 logo，显示默认图标
            from utils.general_utils import set_default_channel_logo
            set_default_channel_logo(self.channel_logo, self.channel_logo.width(), self.channel_logo.height())
        
        # 从EPG数据获取当前节目描述（安全处理）
        try:
            if self._is_local_file():
                self.current_program.setText("")
                self.program_desc.setText(self.language_manager.tr("local_video_file", "本地视频文件"))
                self.time_label.setText("⏱ --:-- / --:--")
                self.remain_label.setText(self.language_manager.tr("loading", "加载中..."))
            else:
                channel_name = self.current_channel.get("name", "")
                current_program_data = None
                if channel_name and hasattr(self, 'epg_parser') and self.epg_parser:
                    ch_name, tvg_id, tvg_name, comma_name = self._get_epg_match_params()
                    current_program_data = self.epg_parser.get_current_program(
                        ch_name, tvg_id, tvg_name=tvg_name, comma_name=comma_name
                    )
                if current_program_data:
                    program_name = current_program_data.get("title", "")
                    self.current_program.setText(f"· {program_name}" if program_name else "")
                    self.program_desc.setText(current_program_data.get("desc", self.language_manager.tr("no_program_desc", "No program description")))
                    start_str = current_program_data.get("start", "")
                    start_display = datetime.fromisoformat(start_str).strftime("%H:%M") if start_str else "--:--"
                    self.progress_start.setText(start_display)
                    self.time_label.setText(f"⏱ {datetime.now().strftime('%H:%M')}")
                    self.remain_label.setText(self.language_manager.tr("waiting_to_play", "Waiting to play..."))
                else:
                    self.current_program.setText("")
                    self.program_desc.setText(self.language_manager.tr("open_playlist_success", "Playlist opened, click a channel to play"))
                    self.time_label.setText(f"⏱ {datetime.now().strftime('%H:%M')}")
                    self.remain_label.setText(self.language_manager.tr("waiting_to_play", "Waiting to play..."))
        except Exception:
            self.current_program.setText("")
            self.program_desc.setText(self.language_manager.tr("open_playlist_success", "Playlist opened, click a channel to play"))
            current_time = datetime.now().strftime("%H:%M")
            self.time_label.setText(f"⏱ {current_time}")
            self.remain_label.setText(self.language_manager.tr("waiting_to_play", "Waiting to play..."))
        
        self._set_progress_value(0)
        self.progress_end.setText("--:--")
        
        # 重置第一行媒体信息为默认值
        self.video_info.setText(f"📺 {self.language_manager.tr('waiting_to_play', 'Waiting to play...')}")
        self.audio_info.setText("🔊 --")
        self.network_info.setText(f"📡 {self.language_manager.tr('waiting_connect', 'Waiting to connect...')}")
        if hasattr(self, 'buffer_info'):
            self.buffer_info.hide()
    
    def toggle_epg(self, checked=None):
        """切换EPG面板显示/隐藏（委托给EPGController）"""
        if self._auto_hide_state == 'auto_hidden':
            self._auto_restore_panels()
            return
        if checked is None:
            checked = not self.epg_panel.isVisible()
        self.epg_ctrl.toggle_epg(checked)

    def set_language(self, language: str):
        """设置界面语言（委托给SettingsFileOperations）"""
        self.settings_ops.set_language(language)

    def set_theme(self, theme: str):
        """设置界面主题（委托给SettingsFileOperations）"""
        self.settings_ops.set_theme(theme)

        if hasattr(self, '_custom_menu_bar'):
            for action in self._custom_menu_bar.actions():
                menu = action.menu()
                if menu:
                    for sub_action in menu.actions():
                        if sub_action.isCheckable() and sub_action.text().replace('&', '') == theme:
                            sub_action.setChecked(True)
                            return

    def show_about(self):
        """显示关于对话框（委托给SettingsFileOperations）"""
        self.settings_ops.show_about()

    def player_settings(self):
        """打开播放器设置（委托给SettingsFileOperations）"""
        self.settings_ops.player_settings()

    def _toggle_file_association(self):
        """打开文件关联设置对话框"""
        from ui.dialogs.file_association_dialog import FileAssociationDialog
        dialog = FileAssociationDialog(self)
        dialog.exec()

    def update_epg_date_display(self):
        """更新EPG日期显示（委托给EPGController）"""
        self.epg_ctrl.update_epg_date_display()

    def on_prev_day(self):
        """上一天按钮点击事件"""
        from datetime import timedelta
        if self.current_epg_date is not None:
            self.current_epg_date -= timedelta(days=1)
        self.update_epg_date_display()
        self.populate_epg_list()
    
    def on_next_day(self):
        """下一天按钮点击事件"""
        from datetime import timedelta
        if self.current_epg_date is not None:
            self.current_epg_date += timedelta(days=1)
        self.update_epg_date_display()
        self.populate_epg_list()
    
    def toggle_playlist(self, checked=None):
        """显示/隐藏播放列表面板"""
        if self._auto_hide_state == 'auto_hidden':
            self._auto_restore_panels()
            return
        if checked is None:
            self.playlist_visible = not self.playlist_panel.isVisible()
        else:
            self.playlist_visible = checked
        self.playlist_panel.setVisible(self.playlist_visible)
        for action in self.findChildren(QAction):
            if action.text() and 'Playlist' in action.text() and action.isCheckable():
                action.blockSignals(True)
                action.setChecked(self.playlist_visible)
                action.blockSignals(False)
                break

    def toggle_floating_panel(self, checked=None):
        """显示/隐藏底部控制面板"""
        if self._auto_hide_state == 'auto_hidden':
            self._auto_restore_panels()
            return
        if checked is None:
            self.floating_panel_visible = not self.floating_panel.isVisible()
        else:
            self.floating_panel_visible = checked
        self.floating_panel.setVisible(self.floating_panel_visible)
        for action in self.findChildren(QAction):
            if action.text() and ('Control Panel' in action.text() or '控制' in action.text()) and action.isCheckable():
                action.blockSignals(True)
                action.setChecked(self.floating_panel_visible)
                action.blockSignals(False)
                break

    def toggle_hide_floating(self, checked=None):
        """一键隐藏/恢复所有悬浮窗"""
        from core.log_manager import global_logger as logger

        currently_hidden = getattr(self, '_floating_hidden', False)
        logger.debug(f"toggle_hide_floating: checked={checked}, _floating_hidden={currently_hidden}, "
                     f"epg_visible={self.epg_visible}, playlist_visible={self.playlist_visible}, "
                     f"floating_visible={self.floating_panel_visible}")

        if currently_hidden:
            saved = getattr(self, '_saved_floating_states', {})
            logger.debug(f"toggle_hide_floating: RESTORE, saved={saved}")
            if saved.get('epg', False) and hasattr(self, 'epg_panel') and self.epg_panel:
                self.epg_panel.show()
            self.epg_visible = saved.get('epg', False)
            if saved.get('playlist', False) and hasattr(self, 'playlist_panel') and self.playlist_panel:
                self.playlist_panel.show()
            self.playlist_visible = saved.get('playlist', False)
            if saved.get('floating', False) and hasattr(self, 'floating_panel') and self.floating_panel:
                self.floating_panel.show()
            self.floating_panel_visible = saved.get('floating', False)
            self._floating_hidden = False
            self._auto_hide_state = 'visible'
        else:
            if self._auto_hide_state == 'auto_hidden':
                self._saved_floating_states = dict(self._auto_hide_saved_states or {})
                self._auto_hide_state = 'visible'
                self._auto_hide_saved_states = {}
            else:
                self._saved_floating_states = {
                    'epg': self.epg_visible,
                    'playlist': self.playlist_visible,
                    'floating': self.floating_panel_visible
                }
            logger.debug(f"toggle_hide_floating: HIDE, saved={self._saved_floating_states}")
            if hasattr(self, 'epg_panel') and self.epg_panel:
                self.epg_panel.hide()
            if hasattr(self, 'playlist_panel') and self.playlist_panel:
                self.playlist_panel.hide()
            if hasattr(self, 'floating_panel') and self.floating_panel:
                self.floating_panel.hide()
            self._floating_hidden = True
            self.epg_visible = False
            self.playlist_visible = False
            self.floating_panel_visible = False

        self._sync_panel_actions()
        logger.debug(f"toggle_hide_floating: DONE, _floating_hidden={self._floating_hidden}")

    def _show_floating_panels_on_enter(self):
        """鼠标进入窗口时显示悬浮窗"""
        if getattr(self, '_floating_hidden', False):
            return
        if getattr(self, 'is_fullscreen', False):
            return
        if getattr(self, '_pip_mode', False):
            return
        if self._auto_hide_state != 'auto_hidden':
            return

        saved = self._auto_hide_saved_states
        if saved.get('epg', False) and hasattr(self, 'epg_panel') and self.epg_panel:
            self.epg_panel.show()
            self.epg_visible = True
        if saved.get('playlist', False) and hasattr(self, 'playlist_panel') and self.playlist_panel:
            self.playlist_panel.show()
            self.playlist_visible = True
        if saved.get('floating', False) and hasattr(self, 'floating_panel') and self.floating_panel:
            self.floating_panel.show()
            self.floating_panel_visible = True

        self._auto_hide_state = 'visible'
        self._auto_hide_saved_states = {}
        self._sync_panel_actions()
        self._raise_child_dialogs()

    def _delayed_hide_floating_panels(self):
        """延迟隐藏悬浮窗（避免鼠标移到悬浮窗上时误隐藏）"""
        if getattr(self, '_floating_hidden', False):
            return
        if getattr(self, 'is_fullscreen', False):
            return
        if getattr(self, '_pip_mode', False):
            return
        if self._auto_hide_state != 'visible':
            return
        cursor_pos = self.cursor().pos()
        if self.rect().contains(self.mapFromGlobal(cursor_pos)):
            return
        if hasattr(self, 'epg_panel') and self.epg_panel.isVisible() and self.epg_panel.geometry().contains(cursor_pos):
            return
        if hasattr(self, 'playlist_panel') and self.playlist_panel.isVisible() and self.playlist_panel.geometry().contains(cursor_pos):
            return
        if hasattr(self, 'floating_panel') and self.floating_panel.isVisible() and self.floating_panel.geometry().contains(cursor_pos):
            return

        self._auto_hide_saved_states = {
            'epg': self.epg_visible,
            'playlist': self.playlist_visible,
            'floating': self.floating_panel_visible
        }

        if self.epg_visible and hasattr(self, 'epg_panel') and self.epg_panel:
            self.epg_panel.hide()
            self.epg_visible = False
        if self.playlist_visible and hasattr(self, 'playlist_panel') and self.playlist_panel:
            self.playlist_panel.hide()
            self.playlist_visible = False
        if self.floating_panel_visible and hasattr(self, 'floating_panel') and self.floating_panel:
            self.floating_panel.hide()
            self.floating_panel_visible = False

        self._auto_hide_state = 'auto_hidden'
        self._sync_panel_actions()

    def _auto_hide_panels(self):
        """全屏模式下自动隐藏悬浮窗和鼠标光标"""
        if not getattr(self, 'is_fullscreen', False):
            return
        if getattr(self, '_floating_hidden', False):
            return
        if self._auto_hide_state != 'visible':
            return

        self._auto_hide_saved_states = {
            'epg': self.epg_visible,
            'playlist': self.playlist_visible,
            'floating': self.floating_panel_visible
        }

        if self.epg_visible and hasattr(self, 'epg_panel') and self.epg_panel:
            self.epg_panel.hide()
            self.epg_visible = False
        if self.playlist_visible and hasattr(self, 'playlist_panel') and self.playlist_panel:
            self.playlist_panel.hide()
            self.playlist_visible = False
        if self.floating_panel_visible and hasattr(self, 'floating_panel') and self.floating_panel:
            self.floating_panel.hide()
            self.floating_panel_visible = False

        self._auto_hide_state = 'auto_hidden'
        self.setCursor(Qt.CursorShape.BlankCursor)
        self._sync_panel_actions()

    def _auto_restore_panels(self):
        """全屏模式下恢复悬浮窗和鼠标光标"""
        if not getattr(self, 'is_fullscreen', False):
            if not getattr(self, '_floating_hidden', False):
                self._show_floating_panels_on_enter()
            return
        if self._auto_hide_state != 'auto_hidden':
            return
        if getattr(self, '_floating_hidden', False):
            return

        saved = self._auto_hide_saved_states
        if saved.get('epg', False) and hasattr(self, 'epg_panel') and self.epg_panel:
            self.epg_panel.show()
            self.epg_visible = True
        if saved.get('playlist', False) and hasattr(self, 'playlist_panel') and self.playlist_panel:
            self.playlist_panel.show()
            self.playlist_visible = True
        if saved.get('floating', False) and hasattr(self, 'floating_panel') and self.floating_panel:
            self.floating_panel.show()
            self.floating_panel_visible = True

        self._auto_hide_state = 'visible'
        self._auto_hide_saved_states = {}
        self.unsetCursor()
        self._sync_panel_actions()
        self._restart_auto_hide_timer()
        self._raise_child_dialogs()

    def _restart_auto_hide_timer(self):
        """重启全屏自动隐藏定时器"""
        if getattr(self, 'is_fullscreen', False) and not getattr(self, '_floating_hidden', False):
            if not hasattr(self, '_auto_hide_timer'):
                from PyQt6.QtCore import QTimer
                self._auto_hide_timer = QTimer(self)
                self._auto_hide_timer.setSingleShot(True)
                self._auto_hide_timer.setInterval(5000)
                self._auto_hide_timer.timeout.connect(self._auto_hide_panels)
            if self._auto_hide_state == 'visible':
                self._auto_hide_timer.start()

    def _stop_auto_hide_timer(self):
        """停止全屏自动隐藏定时器"""
        if hasattr(self, '_auto_hide_timer') and self._auto_hide_timer:
            self._auto_hide_timer.stop()

    def _poll_mouse_position(self):
        """轮询鼠标位置（保留接口兼容）"""
        pass

    def _on_mouse_activity(self):
        """鼠标活动回调"""
        if getattr(self, 'is_fullscreen', False) and not getattr(self, '_floating_hidden', False):
            if self._auto_hide_state == 'auto_hidden':
                self._auto_restore_panels()
            elif self._auto_hide_state == 'visible':
                self._restart_auto_hide_timer()

    def _on_main_window_activated(self):
        """主窗口获得焦点时回调"""
        pass

    def _on_main_window_deactivated(self):
        """主窗口失去焦点时回调"""
        pass

    def _sync_panel_actions(self):
        """同步所有面板相关 QAction 的 checked 状态"""
        for action in self.findChildren(QAction):
            if not action.isCheckable():
                continue
            text = action.text()
            if 'EPG' in text or '节目' in text:
                action.blockSignals(True)
                action.setChecked(self.epg_visible)
                action.blockSignals(False)
            elif 'Playlist' in text or '播放' in text:
                action.blockSignals(True)
                action.setChecked(self.playlist_visible)
                action.blockSignals(False)
            elif 'Control Panel' in text or '控制' in text:
                action.blockSignals(True)
                action.setChecked(self.floating_panel_visible)
                action.blockSignals(False)

    def toggle_osd(self, checked=None):
        """切换OSD显示/隐藏（委托给UIController）"""
        self.ui_ctrl.toggle_osd(checked)

    def toggle_play(self):
        """切换播放/暂停（委托给PlaybackController）"""
        self.playback_ctrl.toggle_play()

    def stop_playback(self):
        """停止播放（委托给PlaybackController）"""
        self.playback_ctrl.stop_playback()

    def set_volume(self, value):
        """设置音量（委托给PlaybackController）"""
        self.playback_ctrl.set_volume(value)
        if not self._suppress_volume_osd and not self._osd_visible:
            self._show_osd_feedback(f"{self.language_manager.tr('osd_volume', 'Volume')}: {value}%")

    def toggle_mute(self):
        """切换静音/取消静音（委托给PlaybackController）"""
        self._suppress_volume_osd = True
        self.playback_ctrl.toggle_mute()
        if not self._osd_visible:
            if self.playback_ctrl.is_muted_state:
                self._show_osd_feedback(self.language_manager.tr('osd_muted', 'Muted'))
            else:
                vol = self.volume_slider.value() if hasattr(self, 'volume_slider') else 0
                self._show_osd_feedback(f"{self.language_manager.tr('osd_volume', 'Volume')}: {vol}%")
        self._suppress_volume_osd = False

    def _update_volume_icon(self, volume):
        """根据音量更新音量图标（保留兼容性）"""
        if hasattr(self, 'playback_ctrl'):
            self.playback_ctrl._update_volume_icon(volume)
        elif hasattr(self, 'volume_button'):
            if volume == 0:
                self.volume_button.setText("🔇")
            elif volume < 50:
                self.volume_button.setText("🔉")
            else:
                self.volume_button.setText("🔊")

    def _show_osd_feedback(self, text: str):
        """在视频上显示短暂的OSD反馈提示"""
        if hasattr(self, 'player_controller') and self.player_controller:
            self.player_controller.show_osd(text, 2000)

    def play_channel(self, channel):
        """播放指定频道（委托给PlaybackController）"""
        self.playback_ctrl.play_channel(channel)

    def _do_play_channel(self, channel):
        """实际执行频道切换（委托给PlaybackController）"""
        self.playback_ctrl._do_play_channel(channel)
    
    def on_play_state_changed(self, is_playing):
        """播放状态改变时的处理"""
        if QThread.currentThread() != self.thread():
            self._pending_play_state = is_playing
            QMetaObject.invokeMethod(self, "_do_handle_play_state_change", Qt.ConnectionType.QueuedConnection)
        else:
            self._handle_play_state_change(is_playing)

    @pyqtSlot()
    def _do_handle_play_state_change(self):
        is_playing = getattr(self, '_pending_play_state', False)
        if hasattr(self, '_pending_play_state'):
            delattr(self, '_pending_play_state')
        self._handle_play_state_change(is_playing)
    
    def _handle_play_state_change(self, is_playing):
        tr = self.language_manager.tr
        if is_playing:
            self.play_button.setText("▮▮")
            self._pip_update_play_btn()
            self._cancel_source_timeout()
            if hasattr(self, 'video_placeholder') and self.video_placeholder:
                self.video_placeholder.hide()
            if hasattr(self, 'video_widget') and self.video_widget and self.video_frame:
                self.video_widget.setGeometry(0, 0, self.video_frame.width(), self.video_frame.height())
                self.video_widget.show()
            self.update_media_info()
            self._last_info_key = None
            self.update_timer.start(500)
            if self._is_local_file():
                if hasattr(self, 'epg_panel') and self.epg_panel and self.epg_panel.isVisible():
                    self.epg_panel.hide()
            elif hasattr(self, 'epg_panel') and self.epg_panel and getattr(self, 'epg_visible', True) and not self.epg_panel.isVisible():
                self.epg_panel.show()
            if self.current_channel:
                channel_name = self.current_channel.get('name', tr('unknown_channel', 'Unknown Channel'))
                if hasattr(self, 'is_catchup_mode') and self.is_catchup_mode:
                    catchup_playing_text = tr('catchup_playing', '正在回看: {name}')
                    self.status_bar.showMessage(catchup_playing_text.format(name=channel_name))
                    # 检查是否有待处理的回看进度值
                    if hasattr(self, '_pending_catchup_progress'):
                        try:
                            progress_value = self._pending_catchup_progress
                            self._set_progress_value(progress_value)
                            
                            # 保存目标进度值，用于在update_floating_panel_info中检查
                            self._target_catchup_progress = progress_value
                            
                            # 记录开始时间（用于模拟进度条移动）
                            import time
                            self._catchup_start_time = time.time()
                            self._catchup_start_progress = progress_value
                            logger.debug(f"记录回看开始时间：{self._catchup_start_time}，开始进度：{progress_value}%")
                            
                            # 清除待处理值，但保留禁用标志
                            # 禁用标志会在update_floating_panel_info中根据播放位置自动清除
                            delattr(self, '_pending_catchup_progress')
                            logger.debug(f"已设置回看进度条，保存目标值：{progress_value}%，保留禁用标志")
                        except Exception as e:
                            logger.error(f"设置回看进度条失败：{e}")
                else:
                    self.status_bar_show_message(f"{tr('playing', 'Playing')}: {channel_name}")
        else:
            self.play_button.setText("▶")
            self._pip_update_play_btn()
            if getattr(self, '_is_stopped', False):
                self._is_stopped = False
                return
            # 暂停时不要显示背景占位符，保持视频窗口可见
            # 停止定时器
            if hasattr(self, 'update_timer'):
                self.update_timer.stop()
            # 更新状态栏消息
            if self.current_channel:
                channel_name = self.current_channel.get('name', tr('unknown_channel', 'Unknown Channel'))
                if hasattr(self, 'is_catchup_mode') and self.is_catchup_mode:
                    catchup_paused_text = tr('catchup_paused', '回看暂停: {name}')
                    self.status_bar_show_message(catchup_paused_text.format(name=channel_name))
                else:
                    self.status_bar_show_message(f"{tr('paused', 'Paused')}: {channel_name}")
    
    def on_play_error(self, error_msg):
        tr = self.language_manager.tr
        logger.error(f"播放错误：{error_msg}")
        if self.current_channel:
            channel_name = self.current_channel.get('name', tr('unknown_channel', 'Unknown Channel'))
            self.status_bar_show_message(f"{tr('play_error', 'Play Error')}: {channel_name} - {error_msg}")
        else:
            self.status_bar_show_message(f"{tr('play_error', 'Play Error')}: {error_msg}")

    def _on_reconnect_requested(self, url):
        """断线自动重连"""
        from PyQt6.QtCore import QTimer
        tr = self.language_manager.tr
        if self.current_channel:
            channel_name = self.current_channel.get('name', '')
            self.status_bar_show_message(
                f"{tr('reconnecting', 'Reconnecting')}: {channel_name} "
                f"({self.player_controller._reconnect_count}/{self.player_controller._max_reconnect})")
        QTimer.singleShot(2000, lambda: self._do_reconnect(url))

    def _do_reconnect(self, url):
        """执行重连"""
        if self.player_controller._user_stopped:
            return
        if self.current_channel:
            self.playback_ctrl.play_channel(self.current_channel)

    def on_live_media_info_updated(self, info: Dict[str, Any]):
        """持续更新媒体信息 - 信息稳定后才更新UI，避免闪烁"""
        if not info:
            return
        try:
            tr = self.language_manager.tr

            key = (
                info.get('width', 0),
                info.get('height', 0),
                info.get('video_codec', ''),
                info.get('audio_codec', ''),
                info.get('fps', 0),
                info.get('hwdec', ''),
                info.get('video_bitrate', 0),
                info.get('audio_bitrate', 0),
                info.get('audio_channels', 0),
                info.get('sample_rate', 0),
                info.get('colormatrix', ''),
                info.get('gamma', ''),
                info.get('sig_peak', 0),
            )
            if hasattr(self, '_last_info_key') and self._last_info_key == key:
                return
            self._last_info_key = key

            has_video = info.get('width', 0) > 0 and info.get('height', 0) > 0
            has_codec = bool(info.get('video_codec', ''))

            if not has_video and not has_codec:
                info = self._last_media_info.copy()
                if not info:
                    return
            elif not has_video and has_codec:
                cached = self._last_media_info
                if cached.get('width', 0) > 0 and cached.get('height', 0) > 0:
                    merged = dict(info)
                    for k in ('width', 'height', 'fps', 'video_bitrate', 'colormatrix', 'gamma', 'sig_peak'):
                        if k in cached and cached[k]:
                            merged[k] = cached[k]
                    info = merged
                else:
                    self._last_media_info.update(info)
                    return
            else:
                self._last_media_info = info.copy()
            
            # 构建视频信息标签（带参数标题，与音频/网络对齐）
            video_parts = []

            hw = info.get('hwdec', '')
            if hw and hw != 'no':
                video_parts.append("{}: {}".format(tr('hwdec_label', 'HW') or 'HW', hw))

            video_codec = info.get('video_codec', '')
            if video_codec and video_codec != '未知':
                codec_short = self._shorten_codec_name(video_codec)
                video_parts.append("{}: {}".format(tr('vcodec_label', 'Video') or 'Video', codec_short))

            video_width = info.get('width', 0)
            video_height = info.get('height', 0)
            if video_width > 0 and video_height > 0:
                video_parts.append("{}: {}x{}".format(tr('resolution_label', 'Resolution') or 'Resolution', video_width, video_height))

            hdr_type = MpvPlayerController.detect_hdr_type(
                info.get('colormatrix', ''),
                info.get('gamma', ''),
                info.get('sig_peak', 0)
            )
            if hdr_type:
                video_parts.append("{}: {}".format(tr('hdr_label', 'HDR') or 'HDR', hdr_type))

            fps = info.get('fps', 0)
            if fps and fps > 0:
                video_parts.append("{}: {:.0f}fps".format(tr('frame_rate_label', 'FPS') or 'FPS', fps))
            
            # 总码率（视频 + 音频）
            v_br = info.get('video_bitrate', 0)
            a_br = info.get('audio_bitrate', 0)
            total_br = v_br + a_br
            if total_br and total_br > 0:
                if total_br >= 1_000_000:
                    br_str = f"{total_br / 1_000_000:.1f}MB/s"
                elif total_br >= 1000:
                    br_str = f"{total_br / 1000:.1f}KB/s"
                else:
                    br_str = f"{total_br}B/s"
                video_parts.append(br_str)
            
            # 更新视频信息标签
            if video_parts:
                self.video_info.setText("\U0001f4fa  {}".format(" | ".join(video_parts)))
            else:
                self.video_info.setText("\U0001f4fa  {}".format(tr('live_stream', 'Live Stream') or 'Live Stream'))

            # 构建音频信息标签（详细信息）
            audio_parts = []

            audio_codec = info.get('audio_codec', '')
            if audio_codec and audio_codec != '未知':
                audio_codec = re.sub(r'\s*\(.*?\)\s*', '', audio_codec).strip()
                audio_parts.append("{}: {}".format(tr('acodec_label', 'Audio') or 'Audio', audio_codec))

            channels = info.get('audio_channels', 0)
            if channels and channels > 0:
                audio_parts.append("{}: {}ch".format(tr('channel_count_label', 'Channels') or 'Channels', channels))

            sample_rate = info.get('sample_rate', 0)
            if sample_rate and sample_rate > 0:
                audio_parts.append("{}: {}Hz".format(tr('sample_rate_label', 'Sample Rate') or 'Sample Rate', sample_rate))

            if a_br and a_br > 0:
                if a_br >= 1000:
                    audio_bitrate_str = "{:.1f}KB/s".format(a_br / 1000)
                else:
                    audio_bitrate_str = "{}B/s".format(a_br)
                audio_parts.append("{}: {}".format(tr('bitrate_label', 'Bitrate') or 'Bitrate', audio_bitrate_str))
            
            # 更新音频信息标签
            if audio_parts:
                self.audio_info.setText(f"🔊 {' | '.join(audio_parts)}")
            else:
                # 如果没有音频信息，显示提示信息
                self.audio_info.setText(f"🔊 {tr('no_audio_info', 'No audio info available')}")
            
            # 网络/格式信息
            network_parts = []
            container = info.get('container', '')
            proto = info.get('protocol', self.player_controller._guess_protocol(self.current_channel.get('url', '') if self.current_channel else ''))
            
            if container and container != '未知':
                network_parts.append(f"{tr('format_label', 'Format')}: {container}")
            if proto and proto != '未知':
                network_parts.append(f"{tr('protocol_label', 'Protocol')}: {proto}")
            
            # 更新网络信息标签
            if network_parts:
                base_text = f"📡 {' | '.join(network_parts)}"
                self.network_info.setText(base_text)
                self._network_base_info = base_text
            else:
                fallback = f"📡 {tr('no_network_info', 'No network info available')}"
                self.network_info.setText(fallback)
                self._network_base_info = fallback
        
        except RuntimeError:
            pass  # UI 对象可能已被销毁
    
    def _shorten_codec_name(self, codec_name):
        """简化编解码器名称"""
        if not codec_name:
            return ''
        
        # H.264
        if 'H.264' in codec_name or 'AVC' in codec_name or 'h264' in codec_name.lower():
            return 'H.264'
        
        # H.265/HEVC
        if 'H.265' in codec_name or 'HEVC' in codec_name or 'hevc' in codec_name.lower():
            return 'H.265'
        
        # MPEG
        if 'MPEG-2' in codec_name or 'mpeg2' in codec_name.lower():
            return 'MPEG-2'
        if 'MPEG-4' in codec_name or 'mpeg4' in codec_name.lower():
            return 'MPEG-4'
        
        # MP3
        if 'MP3' in codec_name or 'MPEG audio layer 3' in codec_name:
            return 'MP3'
        
        # AAC
        if 'AAC' in codec_name or 'aac' in codec_name.lower():
            return 'AAC'
        
        # AC3
        if 'AC-3' in codec_name or 'AC3' in codec_name or 'ac3' in codec_name.lower():
            return 'AC3'
        
        # 默认返回原名称（截取前 10 个字符）
        return codec_name[:10] if len(codec_name) > 10 else codec_name
    
    def _get_resolution_label(self, width, height):
        """获取分辨率标签（FHD、QHD 等）"""
        if width <= 0 or height <= 0:
            return ''
        
        # SD
        if width <= 720:
            return 'SD'
        # HD
        elif width <= 1280:
            return 'HD'
        # FHD
        elif width <= 1920:
            return 'FHD'
        # QHD
        elif width <= 2560:
            return 'QHD'
        # 4K
        elif width <= 3840:
            return '4K'
        # 8K
        else:
            return '8K'
    
    def adjust_window_size_to_video(self):
        """根据视频分辨率调整窗口大小，保持窗口高度不变，调整宽度以适应视频比例"""
        if not self.player_controller:
            return
        
        try:
            # 获取视频分辨率
            resolution = self.player_controller.get_video_resolution()
            # 获取视频分辨率成功
            if not resolution or resolution == "未知":
                return
            
            # 解析分辨率
            parts = resolution.split('x')
            if len(parts) != 2:
                return
            
            video_width = int(parts[0])
            video_height = int(parts[1])
            
            if video_width <= 0 or video_height <= 0:
                return
            
            # 获取当前窗口高度（保持高度不变）
            current_height = self.height()
            current_width = self.width()
            
            # 对于4K及以上分辨率，限制缩放比例，避免窗口过大
            max_video_width = 1920  # 限制最大视频宽度为1080p
            if video_width > max_video_width:
                # 保存原始的视频宽度
                original_video_width = video_width
                video_width = max_video_width
                # 按比例调整视频高度
                video_height = int(video_height * (max_video_width / original_video_width))
            
            # 计算缩放比例：窗口高度 / 视频高度
            scale = current_height / video_height
            
            # 计算新的窗口宽度 = 视频宽度 * 缩放比例
            new_window_width = int(video_width * scale)
            
            # 设置最小和最大宽度限制
            new_window_width = max(800, min(new_window_width, 1920))
            
            # 只有当新宽度与当前宽度差异超过50px时才调整
            if abs(new_window_width - current_width) < 50:
                return
            
            # 调整窗口大小（保持窗口中心位置不变）
            current_geometry = self.geometry()
            center_x = current_geometry.x() + current_geometry.width() // 2
            center_y = current_geometry.y() + current_geometry.height() // 2
            
            new_x = center_x - new_window_width // 2
            new_y = center_y - current_height // 2

            self.setGeometry(new_x, new_y, new_window_width, current_height)

        except Exception as e:
            logger.debug(f"调整窗口大小异常: {e}")
    
    def _try_adjust_window_size(self):
        """尝试调整窗口大小，最多尝试10次"""
        self._resize_attempts += 1
        
        # 尝试调整窗口大小
        self.adjust_window_size_to_video()
        
        # 检查是否获取到了分辨率
        if self.player_controller:
            resolution = self.player_controller.get_video_resolution()
            if resolution and resolution != "未知":
                # 成功获取到分辨率，停止定时器
                if hasattr(self, '_resize_timer') and self._resize_timer:
                    self._resize_timer.stop()
                    self._resize_timer = None
                return
        
        # 如果尝试次数超过10次，停止定时器
        if self._resize_attempts >= 10:
            if hasattr(self, '_resize_timer') and self._resize_timer:
                self._resize_timer.stop()
                self._resize_timer = None
    
    def update_media_info(self):
        """更新媒体信息显示"""
        # 直接调用 update_floating_panel_info 方法，保持统一
        self.update_floating_panel_info()
        
        # 检查是否处于回看模式
        is_catchup = hasattr(self, 'is_catchup_mode') and self.is_catchup_mode
        is_timeshift = hasattr(self, '_is_timeshift_mode') and self._is_timeshift_mode
        
        # 更新第二行：频道信息
        if self.current_channel:
            display_name = self._get_display_channel_name(self.current_channel)
            self.channel_name.setText(display_name)
            
            # 回看模式下，使用回看节目的信息
            if is_catchup and self.catchup_program is not None:
                try:
                    program_name = self.catchup_program.get('title', '')
                    self.current_program.setText(f"· {program_name}" if program_name else "")
                except Exception:
                    self.current_program.setText("")
            else:
                # 非回看模式，从EPG数据获取当前节目名称（安全处理）
                try:
                    channel_name, tvg_id, tvg_name, comma_name = self._get_epg_match_params()
                    if channel_name:
                        current_program = self.epg_parser.get_current_program(channel_name, tvg_id, tvg_name=tvg_name, comma_name=comma_name)
                        if current_program:
                            program_name = current_program.get("title", "")
                            self.current_program.setText(f"· {program_name}" if program_name else "")
                        else:
                            self.current_program.setText("")
                except Exception:
                    self.current_program.setText("")
        
        # 从EPG数据获取当前节目描述（安全处理）
        try:
            if self.current_channel:
                # 回看模式下，使用回看节目的信息
                if is_catchup and self.catchup_program is not None:
                    try:
                        # 使用回看节目的信息
                        start_time = self.catchup_program.get('start')
                        end_time = self.catchup_program.get('end')
                        title = self.catchup_program.get('title', '')
                        desc = self.catchup_program.get('desc', '')
                        # 时移模式下desc为空时，尝试从EPG获取当前节目描述
                        if is_timeshift and (not desc or desc.strip() == ''):
                            channel_name, tvg_id, tvg_name, comma_name = self._get_epg_match_params()
                            if channel_name:
                                current_epg = self.epg_parser.get_current_program(channel_name, tvg_id, tvg_name=tvg_name, comma_name=comma_name)
                                if current_epg:
                                    desc = current_epg.get("desc", '')
                            if not desc or desc.strip() == '':
                                desc = self.language_manager.tr('no_program_desc', 'No program description')
                        elif not desc or desc.strip() == '':
                            desc = self.language_manager.tr('no_program_desc', 'No program description')
                        # 显示节目描述
                        self.program_desc.setText(desc)
                        # 显示节目名称
                        self.current_program.setText(f"· {title}" if title else "")
                        if start_time and end_time:
                            start_str = start_time.strftime("%H:%M")
                            end_str = end_time.strftime("%H:%M")
                            self.time_label.setText(f"⏱ {start_str} - {end_str}")
                            self.remain_label.hide()
                        else:
                            self.time_label.setText("⏱ --:-- - --:--")
                            self.remain_label.hide()
                    except Exception as e:
                        logger.error(f"处理回看节目信息失败: {e}")
                        if self.catchup_program is not None:
                            title = self.catchup_program.get('title', '')
                            self.current_program.setText(f"· {title}" if title else "")
                        self.program_desc.setText(self.language_manager.tr("catchup_current_program", "Catching up current program"))
                        self.time_label.setText("⏱ --:-- - --:--")
                        self.remain_label.hide()
                else:
                    # 非回看模式，从EPG数据获取节目描述
                    self.remain_label.show()
                    channel_name, tvg_id, tvg_name, comma_name = self._get_epg_match_params()
                    # 检测是否为本地视频文件
                    is_local = self._is_local_file()
                    if is_local:
                        self.program_desc.setText(self.language_manager.tr("local_video_file", "本地视频文件"))
                        self.current_program.setText("")
                        self.remain_label.setText(self.language_manager.tr("playing_label", "Playing..."))
                        # time_label、progress_start、progress_end 由 update_floating_panel_info 更新
                    elif channel_name:
                        current_program = self.epg_parser.get_current_program(channel_name, tvg_id, tvg_name=tvg_name, comma_name=comma_name)
                        if current_program:
                            self.program_desc.setText(current_program.get("desc", self.language_manager.tr("no_program_desc", "No program description")))
                            try:
                                from datetime import datetime
                                start_time = datetime.fromisoformat(current_program.get('start', ''))
                                end_time = datetime.fromisoformat(current_program.get('end', ''))
                                start_str = start_time.strftime("%H:%M")
                                end_str = end_time.strftime("%H:%M")
                                self.progress_start.setText(start_str)
                                self.time_label.setText(f"⏱ {start_str} - {end_str}")
                                self.remain_label.setText(self.language_manager.tr("playing_label", "Playing..."))
                            except:
                                from datetime import datetime
                                current_time = datetime.now()
                                start_hour = current_time.strftime("%H:00")
                                end_hour = (current_time.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)).strftime("%H:00")
                                self.progress_start.setText(start_hour)
                                self.time_label.setText(f"⏱ {current_time.strftime('%H:%M')}")
                                self.remain_label.setText(self.language_manager.tr("playing_label", "Playing..."))
                        else:
                            self.program_desc.setText(self.language_manager.tr("playing_current_channel", "Playing current channel"))
                            from datetime import datetime as _dt
                            current_time = _dt.now()
                            start_hour = current_time.strftime("%H:00")
                            end_hour = (current_time.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)).strftime("%H:00")
                            self.progress_start.setText(start_hour)
                            self.progress_end.setText(end_hour)
                            self.time_label.setText(f"⏱ {current_time.strftime('%H:%M')}")
                            self.remain_label.setText(self.language_manager.tr("playing_label", "Playing..."))
                            minutes = current_time.minute
                            seconds = current_time.second
                            self._set_progress_value(minutes * 60 + seconds)
                    else:
                        self.program_desc.setText(self.language_manager.tr("playing_current_channel", "Playing current channel"))
                        from datetime import datetime
                        current_time = datetime.now()
                        start_hour = current_time.strftime("%H:00")
                        end_hour = (current_time.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)).strftime("%H:00")
                        self.progress_start.setText(start_hour)
                        self.progress_end.setText(end_hour)
                        self.time_label.setText(f"⏱ {current_time.strftime('%H:%M')}")
                        self.remain_label.setText(self.language_manager.tr("playing_label", "Playing..."))
                        minutes = current_time.minute
                        seconds = current_time.second
                        self._set_progress_value(minutes * 60 + seconds)
        except Exception:
            if is_catchup:
                self.program_desc.setText(self.language_manager.tr("catchup_current_program", "Catching up current program"))
                self.time_label.setText("⏱ --:-- - --:--")
                self.remain_label.hide()
            else:
                self.remain_label.show()
                self.program_desc.setText(self.language_manager.tr("playing_current_channel", "Playing current channel"))
                from datetime import datetime
                current_time = datetime.now()
                start_hour = current_time.strftime("%H:00")
                end_hour = (current_time.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)).strftime("%H:00")
                self.progress_start.setText(start_hour)
                self.progress_end.setText(end_hour)
                self.time_label.setText(f"⏱ {current_time.strftime('%H:%M')}")
                self.remain_label.setText(self.language_manager.tr("playing_label", "Playing..."))
                minutes = current_time.minute
                seconds = current_time.second
                self._set_progress_value(minutes * 60 + seconds)
    
    def _on_playback_position_updated(self, current_time_ms, total_time_ms, position):
        """接收后台线程获取的播放位置（避免主线程调用MPV API）"""
        prev_total = getattr(self, '_cached_total_time_ms', 0) or 0
        self._cached_current_time_ms = current_time_ms
        self._cached_total_time_ms = total_time_ms
        self._cached_position = position
        if ((not prev_total or prev_total <= 0) and total_time_ms and total_time_ms > 0
                and self._is_local_file()):
            logger.warning(f"[GOT_DURATION] total={total_time_ms:.0f}ms cur={current_time_ms:.0f}ms pos={position:.4f}")
    
    def update_floating_panel_info(self):
        """定期更新悬浮窗信息（进度条、时间、媒体信息等）"""
        if not self.player_controller or not self.current_channel:
            return
        
        if hasattr(self.player_controller, '_heartbeat'):
            self.player_controller._heartbeat()
        
        import time as _time
        now = _time.monotonic()
        if now - getattr(self, '_last_epg_refresh', 0) >= 30:
            self._last_epg_refresh = now
            if hasattr(self, 'epg_content') and self.epg_content.isVisible() and not self._is_local_file():
                self.populate_epg_list()
        
        self._check_program_change()

        if hasattr(self, 'buffer_info') and self.player_controller:
            buffer_state = self.player_controller.get_buffer_state()
            if buffer_state:
                if buffer_state.get('buffering'):
                    self.buffer_info.setText("⏳")
                    self.buffer_info.show()
                else:
                    cache_dur = buffer_state.get('cache_duration', 0)
                    if cache_dur > 0:
                        self.buffer_info.setText(f"💾{cache_dur:.0f}s")
                        self.buffer_info.show()
                    else:
                        self.buffer_info.hide()

        _slider_dragging = hasattr(self, 'program_progress') and self.program_progress.isSliderDown()
        
        current_time_ms = getattr(self, '_cached_current_time_ms', 0)
        total_time_ms = getattr(self, '_cached_total_time_ms', 0)
        position = getattr(self, '_cached_position', 0)

        # 格式化时间
        def format_time(ms):
            if not ms or ms <= 0:
                return "00:00:00"
            seconds = int(ms) // 1000
            minutes = seconds // 60
            hours = minutes // 60
            return f"{hours:02d}:{minutes % 60:02d}:{seconds % 60:02d}"
        
        current_time_str = format_time(current_time_ms)
        total_time_str = format_time(total_time_ms)
        
        # 检查是否处于回看模式
        is_catchup = hasattr(self, 'is_catchup_mode') and self.is_catchup_mode
        
        # 只在状态发生变化时记录回看模式状态
        if not hasattr(self, 'last_catchup_state') or self.last_catchup_state != is_catchup:
            logger.debug(f"回看模式状态: {is_catchup}")
            self.last_catchup_state = is_catchup

        if hasattr(self, '_video_overlay_label'):
            if is_catchup:
                is_timeshift = hasattr(self, '_is_timeshift_mode') and self._is_timeshift_mode
                if is_timeshift:
                    self._video_overlay_label.set_mode(
                        VideoOverlayBadge.MODE_TIMESHIFT,
                        self.language_manager.tr('timeshift_label', '时移')
                    )
                else:
                    self._video_overlay_label.set_mode(
                        VideoOverlayBadge.MODE_CATCHUP,
                        self.language_manager.tr('catchup_label', '回看')
                    )
                if not self._video_overlay_label.isVisible():
                    self._video_overlay_label.show()
                    self._update_video_overlay_position()
            else:
                if self._video_overlay_label.isVisible():
                    self._video_overlay_label.hide()
        
        # 只有在非回看模式下才检查EPG（时移模式也需要EPG），本地文件跳过EPG
        has_epg = False
        current_program = None
        if not self._is_local_file() and (not is_catchup or is_timeshift):
            try:
                channel_name, tvg_id, tvg_name, comma_name = self._get_epg_match_params()
                if channel_name:
                    current_program = self.epg_parser.get_current_program(channel_name, tvg_id, tvg_name=tvg_name, comma_name=comma_name)
                    if current_program:
                        has_epg = True
            except Exception:
                pass
        
        # 更新进度条和时间显示
        if is_catchup and not is_timeshift:
            if self.catchup_program is not None:
                try:
                    start_time = self.catchup_program.get('start')
                    end_time = self.catchup_program.get('end')
                    if start_time and end_time:
                        total_duration = (end_time - start_time).total_seconds()
                        
                        start_str = start_time.strftime("%H:%M")
                        end_str = end_time.strftime("%H:%M")
                        self.progress_start.setText(start_str)
                        self.progress_end.setText(end_str)
                        self.progress_start.repaint()
                        self.progress_end.repaint()
                        
                        if current_time_ms is not None:
                            current_position = current_time_ms / 1000
                        else:
                            current_position = 0
                        
                        if total_duration > 0:
                            if abs(self._progress_total_seconds - int(total_duration)) > 1:
                                self._set_progress_range(int(total_duration))
                            
                            if hasattr(self, '_catchup_start_time') and hasattr(self, '_catchup_start_progress'):
                                import time
                                current_time = time.time()
                                elapsed_seconds = current_time - self._catchup_start_time
                                progress_seconds = min(int(self._catchup_start_progress + elapsed_seconds), int(total_duration))
                                
                                if progress_seconds >= int(total_duration) * 0.98 and hasattr(self, 'speed_button') and self.player_controller:
                                    current_speed = self.player_controller.get_speed()
                                    if abs(current_speed - 1.0) > 0.01:
                                        self.player_controller.set_speed(1.0)
                                        self.speed_button.setText("1.0x")
                                        logger.info("回看已追上直播，自动恢复倍速到1.0x")
                                
                                self._set_progress_value(progress_seconds)
                            else:
                                if hasattr(self, '_disable_progress_auto_update') and self._disable_progress_auto_update:
                                    target_progress = getattr(self, '_target_catchup_progress', 0)
                                    if current_position >= target_progress * 0.9:
                                        delattr(self, '_disable_progress_auto_update')
                                else:
                                    if current_position > 0:
                                        progress_seconds = min(int(current_position), int(total_duration))
                                    else:
                                        progress_seconds = 0
                                    self._set_progress_value(progress_seconds)
                        else:
                            if not (hasattr(self, '_disable_progress_auto_update') and self._disable_progress_auto_update):
                                self._set_progress_value(0)
                except Exception as e:
                    logger.error(f"处理回看时间显示失败: {e}")
                    if total_time_ms > 0:
                        self._set_progress_value(position * total_time_ms / 1000)
                        self.progress_start.setText(current_time_str)
                        self.progress_end.setText(total_time_str)
                    else:
                        if not (hasattr(self, '_disable_progress_auto_update') and self._disable_progress_auto_update):
                            self._set_progress_value(0)
            # 回看模式下，继续执行后面的代码，确保更新节目描述
            # 不再直接返回
        elif has_epg:
            if current_program:
                try:
                    from datetime import datetime, timedelta
                    start_time = datetime.fromisoformat(current_program.get('start', ''))
                    end_time = datetime.fromisoformat(current_program.get('end', ''))
                    now = datetime.now()
                    
                    total_duration = (end_time - start_time).total_seconds()
                    
                    if total_duration > 0:
                        if abs(self._progress_total_seconds - int(total_duration)) > 1:
                            self._set_progress_range(int(total_duration))
                        self._progress_time_mode = 'epg'
                        self._progress_program_start = start_time
                        self._progress_program_end = end_time
                        
                        timeshift = getattr(self, '_live_timeshift_seconds', 0)
                        if timeshift > 0:
                            current_position = (now - timedelta(seconds=timeshift) - start_time).total_seconds()
                            live_position = (now - start_time).total_seconds()
                            if current_position >= live_position - 1:
                                self._live_timeshift_seconds = 0
                                current_position = live_position
                            else:
                                current_position = max(0, current_position)
                        else:
                            current_position = (now - start_time).total_seconds()
                        
                        self._set_progress_value(current_position)
                        
                        start_str = start_time.strftime("%H:%M")
                        end_str = end_time.strftime("%H:%M")
                        self.progress_start.setText(start_str)
                        self.progress_end.setText(end_str)
                    else:
                        is_catchup = hasattr(self, 'is_catchup_mode') and self.is_catchup_mode
                        if not is_catchup:
                            self._set_progress_value(0)
                except:
                    if total_time_ms > 0:
                        self._set_progress_value(position * total_time_ms / 1000)
                        self.progress_start.setText(current_time_str)
                        self.progress_end.setText(total_time_str)
                    else:
                        is_catchup = hasattr(self, 'is_catchup_mode') and self.is_catchup_mode
                        if not is_catchup:
                            self._set_progress_value(0)
            else:
                if total_time_ms > 0:
                    self._set_progress_value(position * total_time_ms / 1000)
                    self.progress_start.setText(current_time_str)
                    self.progress_end.setText(total_time_str)
                else:
                    is_catchup = hasattr(self, 'is_catchup_mode') and self.is_catchup_mode
                    if not is_catchup:
                        self._set_progress_value(0)
        else:
            from datetime import datetime, timedelta

            is_local_file = self._is_local_file()

            if is_local_file and total_time_ms > 0:
                total_seconds = int(total_time_ms) // 1000
                current_seconds = int(current_time_ms) // 1000 if current_time_ms else 0

                if total_seconds > 0:
                    if abs(self._progress_total_seconds - total_seconds) > 1:
                        self._set_progress_range(total_seconds)
                    self._progress_time_mode = 'vod'
                    self._progress_program_start = None
                    self._progress_program_end = None

                    self._set_progress_value(current_seconds)

                    m_s, s_s = divmod(current_seconds, 60)
                    m_e, s_e = divmod(total_seconds, 60)
                    if m_s >= 60 or m_e >= 60:
                        h_s, m_s = divmod(m_s, 60)
                        h_e, m_e = divmod(m_e, 60)
                        self.progress_start.setText(f"{h_s}:{m_s:02d}:{s_s:02d}")
                        self.progress_end.setText(f"{h_e}:{m_e:02d}:{s_e:02d}")
                        self.time_label.setText(f"⏱ {h_s}:{m_s:02d}:{s_s:02d} / {h_e}:{m_e:02d}:{s_e:02d}")
                    else:
                        self.progress_start.setText(f"{m_s}:{s_s:02d}")
                        self.progress_end.setText(f"{m_e}:{s_e:02d}")
                        self.time_label.setText(f"⏱ {m_s}:{s_s:02d} / {m_e}:{s_e:02d}")

                    remain = total_seconds - current_seconds
                    m_r, s_r = divmod(remain, 60)
                    if m_r >= 60:
                        h_r, m_r = divmod(m_r, 60)
                        self.remain_label.setText(f"-{h_r}:{m_r:02d}:{s_r:02d}")
                    else:
                        self.remain_label.setText(f"-{m_r}:{s_r:02d}")
            elif is_local_file:
                self._progress_time_mode = 'vod'
                self._progress_program_start = None
                self._progress_program_end = None
                if total_time_ms <= 0 and self.player_controller and self.player_controller.is_playing:
                    try:
                        fallback_total = self.player_controller.get_total_time()
                        fallback_current = self.player_controller.get_current_time()
                        if fallback_total > 0:
                            total_time_ms = fallback_total
                            current_time_ms = fallback_current
                            self._cached_total_time_ms = fallback_total
                            self._cached_current_time_ms = fallback_current
                            total_seconds = int(fallback_total) // 1000
                            current_seconds = int(fallback_current) // 1000 if fallback_current else 0
                            if abs(self._progress_total_seconds - total_seconds) > 1:
                                self._set_progress_range(total_seconds)
                            self._set_progress_value(current_seconds)
                            m_s, s_s = divmod(current_seconds, 60)
                            m_e, s_e = divmod(total_seconds, 60)
                            if m_s >= 60 or m_e >= 60:
                                h_s, m_s = divmod(m_s, 60)
                                h_e, m_e = divmod(m_e, 60)
                                self.progress_start.setText(f"{h_s}:{m_s:02d}:{s_s:02d}")
                                self.progress_end.setText(f"{h_e}:{m_e:02d}:{s_e:02d}")
                                self.time_label.setText(f"⏱ {h_s}:{m_s:02d}:{s_s:02d} / {h_e}:{m_e:02d}:{s_e:02d}")
                            else:
                                self.progress_start.setText(f"{m_s}:{s_s:02d}")
                                self.progress_end.setText(f"{m_e}:{s_e:02d}")
                                self.time_label.setText(f"⏱ {m_s}:{s_s:02d} / {m_e}:{s_e:02d}")
                            remain = total_seconds - current_seconds
                            m_r, s_r = divmod(remain, 60)
                            if m_r >= 60:
                                h_r, m_r = divmod(m_r, 60)
                                self.remain_label.setText(f"-{h_r}:{m_r:02d}:{s_r:02d}")
                            else:
                                self.remain_label.setText(f"-{m_r}:{s_r:02d}")
                    except Exception:
                        pass

                if total_time_ms <= 0:
                    self.progress_start.setText("--:--")
                    self.progress_end.setText("--:--")
                    self.time_label.setText("⏱ --:-- / --:--")
                    self._set_progress_value(0)
                    if hasattr(self, 'remain_label'):
                        self.remain_label.setText(self.language_manager.tr("loading", "加载中..."))
            else:
                if self._progress_total_seconds != 3600:
                    self._set_progress_range(3600)
                    self._progress_time_mode = 'hour'
                    self._progress_program_start = None
                    self._progress_program_end = None

                timeshift = getattr(self, '_live_timeshift_seconds', 0)
                if timeshift > 0:
                    effective_time = datetime.now() - timedelta(seconds=timeshift)
                else:
                    effective_time = datetime.now()

                start_hour = effective_time.strftime("%H:00")
                end_hour = (effective_time.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)).strftime("%H:00")
                self.progress_start.setText(start_hour)
                self.progress_end.setText(end_hour)
                self.time_label.setText(f"⏱ {datetime.now().strftime('%H:%M')}")
                seconds_from_hour = effective_time.minute * 60 + effective_time.second
                self._set_progress_value(seconds_from_hour)
        
    
    def eventFilter(self, obj, event):
        """事件过滤器（委托给EventHandler）"""
        return self.event_handler.eventFilter(obj, event)

    def update_floating_position(self):
        """更新视频区域大小 + 重新定位浮动Dock面板"""
        if not hasattr(self, 'video_frame') or self.video_frame is None:
            return

        if hasattr(self, 'video_widget') and self.video_widget:
            self.video_widget.setGeometry(0, 0, self.video_frame.width(), self.video_frame.height())

        if hasattr(self, 'video_placeholder') and self.video_placeholder:
            self.video_placeholder.setGeometry(0, 0, self.video_frame.width(), self.video_frame.height())

        self._update_video_overlay_position()

    def _update_video_overlay_position(self):
        if not hasattr(self, '_video_overlay_label') or not self._video_overlay_label:
            return
        if not hasattr(self, 'video_frame') or not self.video_frame:
            return
        self._video_overlay_label.adjustSize()
        w = self._video_overlay_label.width()
        h = self._video_overlay_label.height()
        fw = self.video_frame.width()
        fh = self.video_frame.height()
        self._video_overlay_label.setGeometry(12, fh - h - 12, w, h)

        self._position_floating_docks()

    def _position_floating_docks(self):
        """将3个浮动Dock定位到相对于主窗口的正确位置"""
        if hasattr(self, '_main_container') and self._main_container.layout():
            self._main_container.layout().activate()

        mw = self.geometry()
        if mw.isEmpty():
            return

        mw_x, mw_y, mw_w, mw_h = mw.x(), mw.y(), mw.width(), mw.height()

        gap = 8
        title_bar_h = 32
        menu_bar_h = 28 if (hasattr(self, '_custom_menu_bar') and self._custom_menu_bar and self._custom_menu_bar.isVisible()) else 0
        control_panel_h = 170
        status_bar_h = 25

        side_top = mw_y + title_bar_h + menu_bar_h + gap
        side_h = mw_h - title_bar_h - menu_bar_h - control_panel_h - status_bar_h - gap * 2

        if hasattr(self, 'epg_dock') and self.epg_dock:
            self.epg_dock.move(mw_x + gap, side_top)
            self.epg_dock.setFixedHeight(max(150, side_h))

        if hasattr(self, 'playlist_dock') and self.playlist_dock:
            pl_w = self.playlist_dock.width() or 250
            self.playlist_dock.move(mw_x + mw_w - pl_w - gap, side_top)
            self.playlist_dock.setFixedHeight(max(150, side_h))

        if hasattr(self, 'floating_dock') and self.floating_dock:
            fl_w = min(mw_w - gap * 2, 1050)
            self.floating_dock.setFixedWidth(max(fl_w, 600))
            fl_x = mw_x + (mw_w - self.floating_dock.width()) // 2
            fl_y = mw_y + mw_h - control_panel_h - status_bar_h - gap
            self.floating_dock.move(fl_x, fl_y)

    def toggle_fullscreen(self, checked=False):
        """切换全屏"""
        self.is_fullscreen = not self.is_fullscreen

        if self.is_fullscreen:
            self._auto_hide_state = 'visible'
            self._auto_hide_saved_states = {}
            self._fullscreen_saved_states = {
                'title_bar': hasattr(self, '_title_bar') and self._title_bar and self._title_bar.isVisible(),
                'menu_bar': hasattr(self, '_custom_menu_bar') and self._custom_menu_bar and self._custom_menu_bar.isVisible(),
                'status_bar': bool(self.status_bar and self.status_bar.isVisible()),
                'epg': self.epg_visible,
                'playlist': self.playlist_visible,
                'floating': self.floating_panel_visible,
                'floating_hidden': getattr(self, '_floating_hidden', False)
            }
            if hasattr(self, '_title_bar') and self._title_bar:
                self._title_bar.hide()
            if hasattr(self, '_custom_menu_bar') and self._custom_menu_bar:
                self._custom_menu_bar.hide()
            if self.status_bar:
                self.status_bar.hide()
            self.showFullScreen()
            self.unsetCursor()
            if hasattr(self, 'epg_panel') and self.epg_panel and self.epg_visible:
                self.epg_panel.show()
            if hasattr(self, 'playlist_panel') and self.playlist_panel and self.playlist_visible:
                self.playlist_panel.show()
            if hasattr(self, 'floating_panel') and self.floating_panel and self.floating_panel_visible:
                self.floating_panel.show()
            self._restart_auto_hide_timer()
        else:
            self._stop_auto_hide_timer()
            self.unsetCursor()
            saved = getattr(self, '_fullscreen_saved_states', {})
            self.showNormal()
            if saved.get('title_bar', True) and hasattr(self, '_title_bar') and self._title_bar:
                self._title_bar.show()
            if saved.get('menu_bar', True) and hasattr(self, '_custom_menu_bar') and self._custom_menu_bar:
                self._custom_menu_bar.show()
            if saved.get('status_bar', True) and self.status_bar:
                self.status_bar.show()
            if saved.get('epg', True) and hasattr(self, 'epg_panel') and self.epg_panel:
                self.epg_panel.show()
                self.epg_visible = True
            else:
                self.epg_visible = False
            if saved.get('playlist', True) and hasattr(self, 'playlist_panel') and self.playlist_panel:
                self.playlist_panel.show()
                self.playlist_visible = True
            else:
                self.playlist_visible = False
            if saved.get('floating', True) and hasattr(self, 'floating_panel') and self.floating_panel:
                self.floating_panel.show()
                self.floating_panel_visible = True
            else:
                self.floating_panel_visible = False
            self._floating_hidden = saved.get('floating_hidden', False)
            self._auto_hide_state = 'visible'
            self._auto_hide_saved_states = {}
            self._sync_panel_actions()
            self.update_floating_position()
    
    def refresh_ui(self):
        """刷新界面"""
        self.populate_channel_list(source='auto')
        self.populate_epg_list()
    
    def reset_layout(self):
        """重置布局"""
        self.epg_visible = True
        self.playlist_visible = True
        self.floating_panel_visible = True
        self._floating_hidden = False
        self.epg_panel.setVisible(True)
        self.playlist_panel.setVisible(True)
        self.floating_panel.setVisible(True)
        self._sync_panel_actions()
        self.resize(1280, 806)
    
    def open_scan_ui(self):
        """打开扫描频道窗口"""
        try:
            # 导入扫描窗口模块
            from ui.dialogs.scan_channel_dialog import ScanChannelDialog
            from PyQt6.QtCore import Qt

            # 创建扫描窗口，必须传递parent参数（主窗口self）
            # 这样scan_dialog.parent()才能返回主窗口，双击播放功能才能正常工作
            dialog = ScanChannelDialog(self)
            dialog.config = self.config
            dialog.language_manager = self.language_manager
            self._scan_dialog = dialog
            dialog.show()

            logger.info("成功打开扫描界面")
        except Exception as ex:
            logger.error(f"打开扫描界面失败: {str(ex)}")
    
    def _raise_floating_panels(self):
        """主窗口激活时，将悬浮窗与主窗口一起提升到上层"""
        self.raise_()
        self.update_floating_position()
        for panel_attr in ['epg_panel', 'playlist_panel', 'floating_panel']:
            panel = getattr(self, panel_attr, None)
            if panel and panel.isVisible():
                panel.show()
        self._raise_child_dialogs()

    def _raise_child_dialogs(self):
        """将所有可见的子对话框提升到悬浮窗之上，避免悬浮窗覆盖子对话框"""
        from PyQt6.QtWidgets import QDialog
        for dialog in self.findChildren(QDialog):
            if dialog.isVisible() and not dialog.isModal():
                dialog.raise_()

    def open_channel_mapping(self):
        """打开频道映射管理器"""
        try:
            from ui.dialogs.mapping_manager_dialog import MappingManagerDialog
            from PyQt6.QtCore import Qt
            
            dialog = MappingManagerDialog(self)
            dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
            dialog.exec()
            
            logger.info("成功打开频道映射管理器")
        except Exception as ex:
            logger.error(f"打开频道映射管理器失败: {str(ex)}")

    def _center_dialog_on_screen(self, dialog):
        """将对话框居中显示到屏幕中心（修复多显示器环境下窗口不显示的问题）"""
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        if app:
            screen = app.primaryScreen()
            if screen:
                screen_geometry = screen.availableGeometry()
                dialog.adjustSize()
                dialog_size = dialog.size()
                x = (screen_geometry.width() - dialog_size.width()) // 2 + screen_geometry.x()
                y = (screen_geometry.height() - dialog_size.height()) // 2 + screen_geometry.y()
                dialog.move(x, y)

    def reload_subscription(self):
        """重新加载订阅源（委托给SettingsFileOperations）"""
        self.settings_ops.reload_subscription()

    def start_subscription_timers(self):
        """检查并更新订阅内容（委托给SubscriptionController）"""
        self.subscription_ctrl.start_subscription_timers()

    def update_playlist_subscription(self, source_index=None):
        """更新列表订阅 - 线程安全版本（委托给SubscriptionController）"""
        self.subscription_ctrl.update_playlist_subscription(source_index)

    @pyqtSlot()
    def _do_on_playlist_updated_in_main_thread(self):
        """在主线程中处理订阅更新完成后的UI操作"""
        try:
            message = getattr(self, '_pending_update_message', '')
            if hasattr(self, '_pending_update_message'):
                delattr(self, '_pending_update_message')
            logger.info(f"_do_on_playlist_updated_in_main_thread: 开始更新UI, CHANNELS数量={len(app_state._channels)}")
            if hasattr(self, 'playlist_tab'):
                self.playlist_tab.setCurrentIndex(0)
            self.populate_channel_list(source='subscription')
            self._populate_epg_list()
            if hasattr(self, '_update_floating_position'):
                self._update_floating_position()
            self.status_bar.showMessage(message)
            logger.info("_do_on_playlist_updated_in_main_thread: UI更新完成")
        except Exception as ex:
            logger.error(f"在主线程更新UI失败: {ex}")

    @pyqtSlot()
    def _do_show_status_message(self):
        msg = getattr(self, '_pending_status_msg', '')
        if hasattr(self, '_pending_status_msg'):
            delattr(self, '_pending_status_msg')
        if self.status_bar:
            self.status_bar.showMessage(msg)

    @pyqtSlot()
    def _do_show_status_bar_message(self):
        msg = getattr(self, '_pending_status_bar_msg', '')
        if hasattr(self, '_pending_status_bar_msg'):
            delattr(self, '_pending_status_bar_msg')
        self.status_bar_show_message(msg)

    @pyqtSlot()
    def _do_on_epg_cache(self):
        self.epg_list_updated.emit()
        self.status_bar_show_message(self.language_manager.tr("epg_using_cache", "Using cached EPG data"))

    @pyqtSlot()
    def _do_on_epg_success(self):
        self.epg_list_updated.emit()
        self.status_bar_show_message(self.language_manager.tr("epg_sub_updated", "EPG subscription updated"))

    def update_epg_subscription(self):
        """更新节目单订阅 - 线程安全版本"""
        from PyQt6.QtCore import QTimer
        try:
            from core.subscription_manager import global_subscription_manager
            
            epg_sources = global_subscription_manager.get_epg_sources()
            if not epg_sources:
                logger.info("没有配置EPG源，跳过更新")
                return

            logger.info(f"开始更新节目单订阅，共 {len(epg_sources)} 个EPG源")

            def status_callback(msg):
                logger.info(f"EPG加载状态: {msg}")

            if global_subscription_manager.load_all_epg_data(status_callback):
                app_state._epg_data.clear()
                app_state._epg_data.update(global_subscription_manager._epg_data)

                if app_state._epg_data:
                    sample_channel = list(app_state._epg_data.keys())[0] if app_state._epg_data else None
                    if sample_channel and app_state._epg_data[sample_channel]:
                        sample_date = app_state._epg_data[sample_channel][0].get('start', 'N/A')
                        logger.info(f"EPG 数据样本日期: {sample_date}")

                logger.info(f"节目单订阅更新成功，共 {len(app_state._epg_data)} 个频道的节目单，已使用最新数据")

                if QThread.currentThread() != self.thread():
                    QMetaObject.invokeMethod(self, "_do_on_epg_success", Qt.ConnectionType.QueuedConnection)
                else:
                    self._do_on_epg_success()
            else:
                cached_loaded = global_subscription_manager.load_cached_epg_data()
                if cached_loaded:
                    app_state._epg_data.clear()
                    app_state._epg_data.update(global_subscription_manager._epg_data)
                    logger.debug(f"使用缓存的EPG数据，包含 {len(app_state._epg_data)} 个频道")

                    def _on_epg_cache():
                        self.epg_list_updated.emit()
                        self.status_bar_show_message(self.language_manager.tr("epg_using_cache", "Using cached EPG data"))

                    if QThread.currentThread() != self.thread():
                        QMetaObject.invokeMethod(self, "_do_on_epg_cache", Qt.ConnectionType.QueuedConnection)
                    else:
                        self._do_on_epg_cache()
                else:
                    logger.error("节目单订阅内容解析失败")
                    if QThread.currentThread() != self.thread():
                        self._pending_status_bar_msg = self.language_manager.tr("epg_sub_parse_failed", "EPG subscription parse failed")
                        QMetaObject.invokeMethod(self, "_do_show_status_bar_message", Qt.ConnectionType.QueuedConnection)
                    else:
                        self.status_bar.show_message(self.language_manager.tr("epg_sub_parse_failed", "EPG subscription parse failed"))
        except Exception as ex:
            logger.error(f"更新节目单订阅失败: {str(ex)}")
            if QThread.currentThread() != self.thread():
                self._pending_status_bar_msg = f"{self.language_manager.tr('epg_sub_update_failed', 'Failed to update EPG subscription')}: {str(ex)}"
                QMetaObject.invokeMethod(self, "_do_show_status_bar_message", Qt.ConnectionType.QueuedConnection)
            else:
                self.status_bar_show_message(f"{self.language_manager.tr('epg_sub_update_failed', 'Failed to update EPG subscription')}: {str(ex)}")
    
    def save_player_settings(self, dialog):
        """保存播放器设置"""
        try:
            from core.subscription_manager import global_subscription_manager
            
            protocol = self.protocol_combo.currentText()
            playlist_interval = self.playlist_interval_combo.currentText()
            epg_interval = self.epg_interval_combo.currentText()
            
            self.config.set_value('Player', 'protocol', protocol)
            self.config.set_value('PlaylistSources', 'update_interval', playlist_interval)
            self.config.set_value('EPGSources', 'update_interval', epg_interval)
            
            old_playlist_sources = global_subscription_manager.get_playlist_sources()
            old_epg_sources = global_subscription_manager.get_epg_sources()
            old_active_index = global_subscription_manager.get_active_playlist_source_index()
            
            new_playlist_sources = []
            for i in range(self.playlist_list_widget.count()):
                item = self.playlist_list_widget.item(i)
                source_data = item.data(QtCore.Qt.ItemDataRole.UserRole)
                if source_data:
                    source_data['enabled'] = item.checkState() == QtCore.Qt.CheckState.Checked
                    new_playlist_sources.append(source_data)
            
            if new_playlist_sources:
                global_subscription_manager._config.save_playlist_sources(new_playlist_sources)
            
            new_epg_sources = []
            for i in range(self.epg_list_widget.count()):
                item = self.epg_list_widget.item(i)
                source_data = item.data(QtCore.Qt.ItemDataRole.UserRole)
                if source_data:
                    new_epg_sources.append(source_data)
            
            if new_epg_sources:
                global_subscription_manager._config.save_epg_sources(new_epg_sources)
            
            self.config.save_config()
            
            import threading
            
            new_active_index = -1
            for i, s in enumerate(new_playlist_sources):
                if s.get('enabled'):
                    new_active_index = i
                    break
            if new_active_index < 0 and new_playlist_sources:
                new_active_index = 0
            
            playlist_changed = False
            if len(old_playlist_sources) != len(new_playlist_sources):
                playlist_changed = True
            elif old_active_index != new_active_index:
                playlist_changed = True
            else:
                for i, (old_s, new_s) in enumerate(zip(old_playlist_sources, new_playlist_sources)):
                    if old_s.get('url') != new_s.get('url'):
                        playlist_changed = True
                        break
                    if old_s.get('enabled') != new_s.get('enabled'):
                        playlist_changed = True
                        break
            
            if playlist_changed:
                active = global_subscription_manager.get_active_playlist_source()
                if active:
                    source_index = global_subscription_manager.get_active_playlist_source_index()

                    def _reload_playlist_and_refresh():
                        self._handle_playlist_subscription(True, active.get('url', ''), source_index)
                        from PyQt6.QtCore import QMetaObject, Qt
                        if QThread.currentThread() != self.thread():
                            QMetaObject.invokeMethod(self, "_do_on_playlist_updated_in_main_thread", Qt.ConnectionType.QueuedConnection)
                        else:
                            self._do_on_playlist_updated_in_main_thread()

                    threading.Thread(
                        target=_reload_playlist_and_refresh,
                        daemon=True
                    ).start()
            
            epg_changed_indices = []
            if len(old_epg_sources) != len(new_epg_sources):
                epg_changed_indices = list(range(len(new_epg_sources)))
            else:
                for i, (old_s, new_s) in enumerate(zip(old_epg_sources, new_epg_sources)):
                    if old_s.get('url') != new_s.get('url'):
                        epg_changed_indices.append(i)
            
            if epg_changed_indices:
                def _reload_epg_incremental():
                    def status_callback(msg):
                        logger.info(f"EPG加载状态: {msg}")
                    
                    if len(epg_changed_indices) == len(new_epg_sources):
                        success = global_subscription_manager.load_all_epg_data(status_callback)
                    else:
                        all_ok = True
                        for idx in epg_changed_indices:
                            ok = global_subscription_manager.reload_single_epg_source(idx, status_callback)
                            if not ok:
                                all_ok = False
                        success = all_ok
                    
                    if success:
                        app_state._epg_data.clear()
                        app_state._epg_data.update(global_subscription_manager._epg_data)
                        
                        from PyQt6.QtCore import QMetaObject, Qt
                        if QThread.currentThread() != self.thread():
                            QMetaObject.invokeMethod(self, "_do_on_epg_success", Qt.ConnectionType.QueuedConnection)
                        else:
                            self.epg_list_updated.emit()
                            self.status_bar_show_message(self.language_manager.tr("epg_loaded", "EPG data loaded successfully"))
                
                threading.Thread(target=_reload_epg_incremental, daemon=True).start()
            
            logger.info("播放器设置保存成功")
            self.status_bar.showMessage(self.language_manager.tr("player_settings_saved", "Player settings saved"))
            dialog.accept()
        except Exception as ex:
            logger.error(f"保存播放器设置失败: {str(ex)}")
            self.status_bar.showMessage(f"{self.language_manager.tr('player_settings_save_failed', 'Failed to save player settings')}: {str(ex)}")
    
    def _load_subscription_sources_to_ui(self):
        """加载订阅源到UI控件（委托给SubscriptionUIController）"""
        self.subscription_ui_ctrl.load_subscription_sources_to_ui()

    def _add_or_update_playlist_source(self):
        """从UI添加或更新直播源（委托给SubscriptionUIController）"""
        self.subscription_ui_ctrl.add_or_update_playlist_source()

    def _edit_playlist_source(self, item):
        """编辑选中的直播源（委托给SubscriptionUIController）"""
        self.subscription_ui_ctrl.edit_playlist_source(item)

    def _remove_selected_playlist_source(self):
        """删除选中的直播源（委托给SubscriptionUIController）"""
        self.subscription_ui_ctrl.remove_selected_playlist_source()

    def _activate_playlist_source(self, item):
        """激活指定的直播源（委托给SubscriptionUIController）"""
        self.subscription_ui_ctrl.activate_playlist_source(item)
    
    def _add_or_update_epg_source(self):
        """从UI添加或更新EPG源（委托给SubscriptionUIController）"""
        self.subscription_ui_ctrl.add_or_update_epg_source()

    def _edit_epg_source(self, item):
        """编辑选中的EPG源（委托给SubscriptionUIController）"""
        self.subscription_ui_ctrl.edit_epg_source(item)

    def _on_playlist_url_changed(self):
        """Playlist URL输入框文本变化时，清空则退出编辑模式"""
        if self._editing_playlist_index >= 0 and not self.playlist_new_url_edit.text().strip():
            self._editing_playlist_index = -1
            tr = self.language_manager.tr
            self._playlist_add_btn.setText(tr("add_source", "+ Add Source"))
    
    def _on_epg_url_changed(self):
        """EPG URL输入框文本变化时，清空则退出编辑模式"""
        if self._editing_epg_index >= 0 and not self.epg_new_url_edit.text().strip():
            self._editing_epg_index = -1
            tr = self.language_manager.tr
            self._epg_add_btn.setText(tr("add_source", "+ Add Source"))
    
    def _remove_selected_epg_source(self):
        """删除选中的EPG源（委托给SubscriptionUIController）"""
        self.subscription_ui_ctrl.remove_selected_epg_source()
    
    def update_recent_files_menu(self):
        """更新最近打开文件菜单"""
        from core.config_manager import ConfigManager
        
        # 清空当前菜单
        self.recent_menu.clear()
        
        # 加载最近打开的文件列表
        config_manager = ConfigManager()
        recent_files = config_manager.load_recent_files()
        
        if not recent_files:
            # 如果没有最近打开的文件，添加一个禁用的菜单项
            no_recent_action = QAction(self.language_manager.tr("no_recent_files", "No recent files"), self)
            no_recent_action.setEnabled(False)
            self.recent_menu.addAction(no_recent_action)
        else:
            # 添加最近打开的文件到菜单
            for file_path in recent_files:
                action = QAction(file_path, self)
                action.triggered.connect(lambda checked, path=file_path: self.open_recent_file(path))
                self.recent_menu.addAction(action)
    
    def open_recent_file(self, file_path):
        from core.log_manager import global_logger as logger

        try:
            from services.m3u_parser import load_m3u_file
            content = load_m3u_file(file_path)

            if self.channel_model.load_from_file(content):
                new_channels = []
                for i, ch in enumerate(self.channel_model.channels):
                    new_channels.append({
                        "id": i + 1,
                        "name": ch.get('name', '未命名'),
                        "url": ch.get('url', ''),
                        "logo": ch.get('logo', ''),
                        "group": ch.get('group', '未分类'),
                        "_groups": ch.get('_groups', [ch.get('group', '未分类')]),
                        "tvg_id": ch.get('tvg_id', ''),
                        "tvg_chno": ch.get('tvg_chno', ''),
                        "tvg_shift": ch.get('tvg_shift', ''),
                        "catchup": ch.get('catchup', ''),
                        "catchup_days": ch.get('catchup_days', ''),
                        "catchup_source": ch.get('catchup_source', ''),
                        "resolution": ch.get('resolution', ''),
                        "current_program": '',
                        "_raw_extinf": ch.get('_raw_extinf', ''),
                        "_all_tags": ch.get('_all_tags', {})
                    })

                app_state._channels.clear()
                app_state._channels.extend(new_channels)

                from core.config_manager import ConfigManager
                config_manager = ConfigManager()
                config_manager.add_recent_file(file_path)
                self.update_recent_files_menu()

                if app_state._channels:
                    self.current_channel = app_state._channels[0]
                    display_name = self._get_display_channel_name(self.current_channel)
                    self.channel_name.setText(display_name)

                if hasattr(self, 'playlist_tab'):
                    self.playlist_tab.setCurrentIndex(1)
                self.populate_channel_list(source='local')
                self.status_bar.showMessage(f"{self.language_manager.tr('file_opened', 'File opened')}: {file_path}")
                logger.info(f"成功打开最近文件: {file_path}, 共 {len(app_state._channels)} 个频道")
            else:
                self.status_bar.showMessage(self.language_manager.tr("file_format_error"))
        except FileNotFoundError:
            from core.config_manager import ConfigManager
            ConfigManager().remove_recent_file(file_path)
            self.update_recent_files_menu()
            self.status_bar.showMessage(self.language_manager.tr('file_not_found', 'File not found, removed from recent list'))
            logger.warning(f"最近文件不存在，已从列表移除: {file_path}")
        except Exception as ex:
            logger.error(f"打开最近文件失败: {str(ex)}")
            self.status_bar.showMessage(f"{self.language_manager.tr('file_open_failed', 'Failed to open file')}: {str(ex)}")
    
    def open_playlist(self):
        """打开播放列表（委托给SettingsFileOperations）"""
        self.settings_ops.open_playlist()

    def _open_stream(self):
        """打开串流地址"""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QHBoxLayout, QPushButton
        tr = self.language_manager.tr

        dialog = QDialog(self)
        dialog.setWindowTitle(tr("open_stream", "打开串流"))
        dialog.setMinimumWidth(600)
        dialog.setMinimumHeight(160)

        layout = QVBoxLayout(dialog)
        layout.setSpacing(10)

        label = QLabel(tr("open_stream_url", "请输入直播地址或串流URL:"))
        layout.addWidget(label)

        url_input = QLineEdit()
        url_input.setPlaceholderText("http://example.com/stream.m3u8")
        url_input.setMinimumHeight(32)
        layout.addWidget(url_input)

        name_label = QLabel(tr("stream_name_optional", "频道名称（可选）:"))
        layout.addWidget(name_label)

        name_input = QLineEdit()
        name_input.setPlaceholderText(tr("stream_name_hint", "留空则自动命名"))
        name_input.setMinimumHeight(32)
        layout.addWidget(name_input)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton(tr("cancel", "取消"))
        cancel_btn.setFixedWidth(80)
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(cancel_btn)
        ok_btn = QPushButton(tr("ok", "确定"))
        ok_btn.setFixedWidth(80)
        ok_btn.clicked.connect(dialog.accept)
        ok_btn.setDefault(True)
        btn_layout.addWidget(ok_btn)
        layout.addLayout(btn_layout)

        url_input.setFocus()

        if dialog.exec() == QDialog.DialogCode.Accepted:
            url = url_input.text().strip()
            if url:
                name = name_input.text().strip()
                if not name:
                    name = url.split('/')[-1][:30] if '/' in url else url[:30]
                channel = {
                    'name': name,
                    'url': url,
                    'group': tr("temp_stream", "临时串流"),
                    '_groups': [tr("temp_stream", "临时串流")],
                }
                self._add_to_local_list(channel)

    def _open_video_file(self):
        """打开本地视频文件"""
        from PyQt6.QtWidgets import QFileDialog
        tr = self.language_manager.tr
        file_path, _ = QFileDialog.getOpenFileName(
            self, tr("open_video", "打开视频"),
            "",
            tr("video_files", "视频文件 (*.mp4 *.mkv *.avi *.mov *.flv *.wmv *.ts *.webm);;所有文件 (*)"),
        )
        if file_path:
            import os
            name = os.path.splitext(os.path.basename(file_path))[0]
            channel = {
                'name': name,
                'url': file_path,
                'group': tr("local_video", "本地视频"),
                '_groups': [tr("local_video", "本地视频")],
            }
            self._add_to_local_list(channel)

    def _add_to_local_list(self, channel):
        """将频道添加到本地列表并播放"""
        self._local_channels.append(channel)
        self.playlist_tab.setCurrentIndex(1)
        self._update_groups_for('local')
        self._populate_channel_list_for(
            self.local_channel_list, self._local_channels,
            self.local_group_combo.currentText()
        )
        for i in range(self.local_channel_list.count()):
            item = self.local_channel_list.item(i)
            if item and item.data(Qt.ItemDataRole.UserRole) == channel:
                self.local_channel_list.setCurrentItem(item)
                break
        self.current_channel = channel
        self.update_channel_info_on_selection()
        self.play_channel(channel)

    def raise_floating_panels(self):
        """重新显示可见的悬浮窗（与主窗口保持在一起，依赖Tool窗口标志维持层级）"""
        self.update_floating_position()

        if hasattr(self, 'epg_panel') and self.epg_panel and self.epg_visible:
            if not self.epg_panel.isVisible():
                self.epg_panel.show()

        if hasattr(self, 'playlist_panel') and self.playlist_panel and self.playlist_visible:
            if not self.playlist_panel.isVisible():
                self.playlist_panel.show()

        if hasattr(self, 'floating_panel') and self.floating_panel and self.floating_panel_visible:
            if not self.floating_panel.isVisible():
                self.floating_panel.show()

        self._raise_child_dialogs()
    
    def save_as(self):
        """另存为（委托给SettingsFileOperations）"""
        self.settings_ops.save_as()

    def _convert_markdown_to_html(self, markdown):
        """将Markdown格式转换为HTML格式"""
        import re
        colors = AppStyles._get_colors()
        html = markdown
        html = re.sub(r'## (.*)', rf'<h2 style="color: {colors["accent"]}; margin-top: 12px; margin-bottom: 6px; font-size: 15px;">\1</h2>', html)
        html = re.sub(r'\*\*(.*?)\*\*', rf'<strong style="color: {colors["window_text"]};">\1</strong>', html)
        html = re.sub(r'^1\. (.*)', r'<p style="margin: 3px 0; line-height: 1.4;">1. \1</p>', html, flags=re.MULTILINE)
        html = re.sub(r'^- (.*)', r'<p style="margin: 2px 0 2px 16px; line-height: 1.4;">• \1</p>', html, flags=re.MULTILINE)
        html = html.replace('\n\n', '<br>')
        html = html.replace('\n', ' ')
        html = f'''<html>
        <head>
            <style>
                body {{ 
                    font-family: 'Microsoft YaHei', 'Segoe UI', sans-serif; 
                    font-size: 13px; 
                    line-height: 1.5; 
                    color: {colors['window_text']}; 
                    background-color: transparent;
                    margin: 0;
                    padding: 0;
                }}
                p {{ margin: 3px 0; }}
            </style>
        </head>
        <body>
            {html}
        </body>
        </html>'''
        return html

    def show_usage_instructions(self):
        """显示使用说明（委托给SettingsFileOperations）"""
        self.settings_ops.show_usage_instructions()

    def _reapply_all_styles(self):
        """重新应用所有样式（委托给UIController）"""
        self.ui_ctrl.reapply_all_styles()

    def _reapply_side_panel_styles(self):
        try:
            if hasattr(self, 'epg_title'):
                self.epg_title.setStyleSheet(AppStyles.player_epg_title_style())
            if hasattr(self, 'epg_prev_day'):
                self.epg_prev_day.setStyleSheet(AppStyles.player_date_button_style())
            if hasattr(self, 'epg_next_day'):
                self.epg_next_day.setStyleSheet(AppStyles.player_date_button_style())
            if hasattr(self, 'epg_date_label'):
                self.epg_date_label.setStyleSheet(AppStyles.player_date_label_style())
            if hasattr(self, 'epg_content'):
                self.epg_content.setStyleSheet(AppStyles.player_list_style())
            if hasattr(self, 'epg_empty_label'):
                self.epg_empty_label.setStyleSheet(AppStyles.player_empty_label_style())
            if hasattr(self, 'sub_group_combo'):
                self.sub_group_combo.setStyleSheet(AppStyles.player_group_combo_style())
            if hasattr(self, 'local_group_combo'):
                self.local_group_combo.setStyleSheet(AppStyles.player_group_combo_style())
            if hasattr(self, 'playlist_tab'):
                self.playlist_tab.setStyleSheet(AppStyles.player_tab_style())
            for list_attr in ['sub_channel_list', 'local_channel_list']:
                cl = getattr(self, list_attr, None)
                if cl:
                    cl.setStyleSheet(AppStyles.player_list_style())
                    colors = AppStyles._get_colors()
                    name_style = f"font-size: 12px; font-weight: bold; color: {colors['player_panel_text']};"
                    for i in range(cl.count()):
                        item = cl.item(i)
                        item_widget = cl.itemWidget(item)
                        if item_widget:
                            for label in item_widget.findChildren(QtWidgets.QLabel):
                                if label.objectName() != "channel_logo_label":
                                    label.setStyleSheet(name_style)
            for empty_attr in ['sub_empty_label', 'local_empty_label']:
                el = getattr(self, empty_attr, None)
                if el:
                    el.setStyleSheet(AppStyles.player_empty_label_style())
        except Exception as e:
            logger.error(f"重新应用侧边栏样式失败: {e}")

    def _reapply_floating_panel_styles(self):
        try:
            if not hasattr(self, 'floating_panel'):
                return
            fp = self.floating_panel
            if hasattr(self, 'video_info'):
                self.video_info.setStyleSheet(AppStyles.player_media_badge_style())
            if hasattr(self, 'audio_info'):
                self.audio_info.setStyleSheet(AppStyles.player_media_badge_style())
            if hasattr(self, 'network_info'):
                self.network_info.setStyleSheet(AppStyles.player_media_badge_style())
            if hasattr(self, 'buffer_info'):
                self.buffer_info.setStyleSheet(AppStyles.player_media_badge_style())
            if hasattr(self, 'channel_logo'):
                self.channel_logo.setStyleSheet(AppStyles.player_channel_logo_style())
            if hasattr(self, 'channel_name'):
                self.channel_name.setStyleSheet(AppStyles.player_channel_name_style())
            if hasattr(self, 'current_program'):
                self.current_program.setStyleSheet(AppStyles.player_program_style())
            if hasattr(self, 'program_desc'):
                self.program_desc.setStyleSheet(AppStyles.player_program_desc_style())
            if hasattr(self, 'time_label'):
                self.time_label.setStyleSheet(AppStyles.player_time_badge_style())
            if hasattr(self, 'remain_label'):
                self.remain_label.setStyleSheet(AppStyles.player_status_badge_style())
            if hasattr(self, 'progress_start'):
                self.progress_start.setStyleSheet(AppStyles.player_progress_label_style())
            if hasattr(self, 'progress_end'):
                self.progress_end.setStyleSheet(AppStyles.player_progress_label_style())
            for tool_btn in fp.findChildren(QToolButton):
                tool_btn.setStyleSheet(AppStyles.player_button_style())
            if hasattr(self, 'exit_catchup_button'):
                self.exit_catchup_button.setStyleSheet(AppStyles.exit_catchup_button_style())
            if hasattr(self, 'catchup_indicator'):
                self.catchup_indicator.setStyleSheet(AppStyles.player_catchup_indicator_style())
            for slider in fp.findChildren(QSlider):
                slider.setStyleSheet(AppStyles.player_slider_style())
            if hasattr(self, 'volume_slider'):
                self.volume_slider.setStyleSheet(AppStyles.player_volume_slider_style())
            for combo in fp.findChildren(QComboBox):
                combo.setStyleSheet(AppStyles.player_group_combo_style())
            for frame in fp.findChildren(QFrame):
                if frame.styleSheet() and 'max-height' in frame.styleSheet():
                    frame.setStyleSheet(AppStyles.player_line_style())
        except Exception as e:
            logger.error(f"重新应用悬浮面板样式失败: {e}")

    def save_window_layout(self):
        """保存窗口布局（委托给SettingsFileOperations）"""
        self.settings_ops.save_window_layout()

    def showEvent(self, event):
        """窗口显示事件（委托给EventHandler）"""
        if hasattr(self, 'event_handler') and self.event_handler:
            self.event_handler.showEvent(event)
        else:
            super().showEvent(event)

    def changeEvent(self, event):
        """窗口状态变化事件（委托给EventHandler）"""
        if hasattr(self, 'event_handler') and self.event_handler:
            self.event_handler.changeEvent(event)
        else:
            super().changeEvent(event)

    def moveEvent(self, event):
        """窗口移动事件（委托给EventHandler）"""
        if hasattr(self, 'event_handler') and self.event_handler:
            self.event_handler.moveEvent(event)
        else:
            super().moveEvent(event)

    def resizeEvent(self, event):
        """窗口大小变化事件（委托给EventHandler）"""
        if hasattr(self, 'event_handler') and self.event_handler:
            self.event_handler.resizeEvent(event)
        else:
            super().resizeEvent(event)

    def closeEvent(self, event):
        """窗口关闭事件（委托给EventHandler）"""
        if hasattr(self, 'event_handler') and self.event_handler:
            self.event_handler.closeEvent(event)
        else:
            super().closeEvent(event)

    def _check_for_updates_async(self):
        """异步检查新版本"""
        if QThread.currentThread() != self.thread():
            QMetaObject.invokeMethod(self, "_do_check_for_updates_async", Qt.ConnectionType.QueuedConnection)
            return
        self._do_check_for_updates_async()

    @pyqtSlot()
    def _do_check_for_updates_async(self):
        # 检查是否已在检查或已检查过
        if hasattr(self, '_update_checking') and self._update_checking:
            return
        if hasattr(self, '_update_checked') and self._update_checked:
            return

        self._update_checking = True
        try:
            # 在后台线程中执行版本检查
            from PyQt6.QtCore import pyqtSignal
            import asyncio
            import aiohttp

            class UpdateCheckThread(QThread):
                """版本检查线程"""
                update_found = pyqtSignal(str, str)  # 最新版本号, 当前版本号
                check_completed = pyqtSignal(bool, str)  # 是否成功, 消息

                def run(self):
                    try:
                        # 创建新的事件循环
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)

                        # 获取当前版本
                        from ui.dialogs.about_dialog import AboutDialog
                        current_version = AboutDialog.CURRENT_VERSION

                        # 获取最新版本（设置超时避免长时间等待）
                        latest_version, _, _ = loop.run_until_complete(
                            asyncio.wait_for(self._get_latest_version(), timeout=15)
                        )

                        if latest_version and not latest_version.startswith("("):
                            # 检查是否有新版本
                            if self._is_newer_version(current_version, latest_version):
                                self.update_found.emit(latest_version, current_version)
                                self.check_completed.emit(True, f"发现新版本: {latest_version}")
                            else:
                                self.check_completed.emit(True, "当前已是最新版本")
                        else:
                            # 网络错误或其他问题，静默处理，不显示给用户
                            self.check_completed.emit(False, f"版本检查失败: {latest_version}")

                    except asyncio.TimeoutError:
                        # 超时错误，静默处理
                        self.check_completed.emit(False, "版本检查超时")
                    except Exception as e:
                        # 其他异常，静默处理
                        self.check_completed.emit(False, f"版本检查异常: {str(e)}")
                    finally:
                        try:
                            loop.close()
                        except Exception:
                            pass

                async def _get_latest_version(self):
                    """从GitHub获取最新版本信息"""
                    try:
                        async with aiohttp.ClientSession() as session:
                            async with session.get(
                                "https://api.github.com/repos/sumingyd/IPTV-Scanner-Editor-Pro/releases/latest",
                                headers={'User-Agent': 'IPTV-Scanner-Editor-Pro'},
                                timeout=aiohttp.ClientTimeout(total=10)
                            ) as response:
                                if response.status == 200:
                                    data = await response.json()
                                    version = data.get('tag_name', '').lstrip('v')
                                    return version, None, None
                                elif response.status == 403:
                                    return "(API限制)", None, None
                                else:
                                    return "(获取失败)", None, None
                    except asyncio.TimeoutError:
                        return "(请求超时)", None, None
                    except Exception:
                        return "(获取失败)", None, None

                def _is_newer_version(self, current_version, latest_version):
                    """比较版本号，判断最新版本是否比当前版本新"""
                    try:
                        # 将版本号转换为数字列表进行比较
                        current_parts = list(map(int, current_version.split('.')))
                        latest_parts = list(map(int, latest_version.split('.')))

                        # 确保两个版本号有相同的长度
                        max_length = max(len(current_parts), len(latest_parts))
                        current_parts.extend([0] * (max_length - len(current_parts)))
                        latest_parts.extend([0] * (max_length - len(latest_parts)))

                        # 逐位比较
                        for i in range(max_length):
                            if latest_parts[i] > current_parts[i]:
                                return True
                            elif latest_parts[i] < current_parts[i]:
                                return False
                        return False  # 版本相同
                    except (ValueError, AttributeError):
                        # 如果版本号格式不正确，使用字符串比较
                        return latest_version > current_version

            # 创建并启动版本检查线程
            self.update_check_thread = UpdateCheckThread()
            self.update_check_thread.setParent(self)
            self.update_check_thread.update_found.connect(self._on_update_found)
            self.update_check_thread.check_completed.connect(self._on_update_check_completed)
            self.update_check_thread.start()

        except Exception as e:
            logger.error(f"启动版本检查失败: {str(e)}")
        finally:
            # 重置检查状态
            self._update_checking = False
            self._update_checked = True

    def _on_update_found(self, latest_version, current_version):
        """发现新版本时的处理"""
        try:
            # 在窗口标题添加提示
            original_title = self.windowTitle() or ""
            new_version_text = self.language_manager.tr("new_version_available", "New Version Available") or "New Version Available"
            if new_version_text not in original_title:
                new_title = f"{original_title} - {new_version_text} {latest_version}"
                self.setWindowTitle(new_title)

            status_message = f"{self.language_manager.tr('new_version_found', 'New version found')} {latest_version} ({self.language_manager.tr('current_version', 'Current Version')} {current_version})"
            self.status_bar.showMessage(status_message, 10000)  # 显示10秒

            # 设置状态栏消息为红色
            from ui.styles import AppStyles
            self.status_bar.setStyleSheet(AppStyles.statusbar_error_style())

            # 10秒后恢复状态栏样式
            QMetaObject.invokeMethod(self, "_reset_statusbar_style", Qt.ConnectionType.QueuedConnection)

            logger.info(f"发现新版本: {latest_version} (当前版本: {current_version})")

        except Exception as e:
            logger.error(f"更新界面提示失败: {str(e)}")

    def _reset_statusbar_style(self):
        """恢复状态栏样式"""
        self.status_bar.setStyleSheet("")
    
    def _on_update_check_completed(self, success, message):
        if success:
            logger.info(f"版本检查完成: {message}")
        else:
            logger.warning(f"版本检查失败: {message}")

    def _on_logo_cache_loaded(self, url, pixmap):
        """台标加载完成的回调"""
        logger.debug(f"台标加载完成: {url[:50]}..., pixmap有效: {not pixmap.isNull()}, 更新列表项...")

        if self.current_channel:
            logo = self.current_channel.get('logo', '')
            if logo:
                logo = logo.strip('`"\'')
                if logo == url and hasattr(self, 'channel_logo'):
                    scaled = self._logo_cache_service.scale_logo_pixmap_to_fit(pixmap, self.channel_logo.width(), self.channel_logo.height())
                    self.channel_logo.setPixmap(scaled)
                    self.channel_logo.setText("")
        
        for list_widget in (self.sub_channel_list, self.local_channel_list):
            channels = self._sub_channels if list_widget is self.sub_channel_list else self._local_channels
            is_grid = list_widget.viewMode() == QListWidget.ViewMode.IconMode
            for i in range(list_widget.count()):
                item = list_widget.item(i)
                if not item:
                    continue
                channel_idx = item.data(Qt.ItemDataRole.UserRole)
                if channel_idx is None or channel_idx >= len(channels):
                    continue
                channel = channels[channel_idx]
                channel_logo = channel.get('logo', '')
                if channel_logo:
                    channel_logo = channel_logo.strip('`"\'')
                    if channel_logo == url:
                        if is_grid:
                            ch_url = channel.get('url', '')
                            if self.player_controller and ch_url:
                                thumb_path = self.player_controller.get_thumbnail_path(ch_url)
                                if thumb_path:
                                    break
                            scaled = pixmap.scaled(160, 90, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                            item.setIcon(QIcon(scaled))
                        else:
                            item_widget = list_widget.itemWidget(item)
                            if item_widget:
                                logo_label = item_widget.findChild(QtWidgets.QLabel, "channel_logo_label")
                                if logo_label:
                                    scaled = self._logo_cache_service.scale_logo_pixmap_to_fit(
                                        pixmap,
                                        logo_label.width() if logo_label.width() > 0 else 34,
                                        logo_label.height() if logo_label.height() > 0 else 34
                                    )
                                    logo_label.setPixmap(scaled)
                        break

    def _on_thumbnail_ready(self, channel_name, url):
        """后台缩略图截取完成的回调"""
        self._update_grid_thumbnail(url)

    def _on_player_thumbnail_captured(self, url):
        """播放器截图完成后的回调"""
        self._update_grid_thumbnail(url)

    def _update_grid_thumbnail(self, url):
        """更新grid视图中指定URL频道的缩略图"""
        from services.thumbnail_service import get_thumbnail_path
        thumb_path = get_thumbnail_path(url)
        if not thumb_path:
            return
        for list_widget in (self.sub_channel_list, self.local_channel_list):
            if list_widget.viewMode() != QListWidget.ViewMode.IconMode:
                continue
            channels = self._sub_channels if list_widget is self.sub_channel_list else self._local_channels
            for i in range(list_widget.count()):
                item = list_widget.item(i)
                if not item:
                    continue
                channel_idx = item.data(Qt.ItemDataRole.UserRole)
                if channel_idx is None or channel_idx >= len(channels):
                    continue
                channel = channels[channel_idx]
                if channel.get('url', '') == url:
                    px = QPixmap(thumb_path)
                    if not px.isNull():
                        scaled = px.scaled(210, 118, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                        item.setIcon(QIcon(scaled))
                    break

    def _get_next_channel_urls(self, current_channel):
        channels = app_state._channels
        if not channels or not current_channel:
            return []
        current_idx = -1
        for i, ch in enumerate(channels):
            if ch is current_channel:
                current_idx = i
                break
        if current_idx < 0:
            return []
        next_urls = []
        for j in range(current_idx + 1, min(current_idx + 3, len(channels))):
            url = channels[j].get('url', '')
            if url:
                next_urls.append(url)
        return next_urls

    def _start_source_timeout(self, channel):
        if hasattr(self, '_source_timeout_timer') and self._source_timeout_timer:
            self._source_timeout_timer.stop()
        try:
            from core.config_manager import ConfigManager
            timeout = self.config.load_playback_settings().get('source_timeout_sec', 10)
        except Exception:
            timeout = 10
        if timeout <= 0:
            return
        self._source_timeout_timer = QTimer(self)
        self._source_timeout_timer.setSingleShot(True)
        self._source_timeout_timer.timeout.connect(lambda: self._on_source_timeout(channel))
        self._source_timeout_timer.start(timeout * 1000)

    def _cancel_source_timeout(self):
        if hasattr(self, '_source_timeout_timer') and self._source_timeout_timer:
            self._source_timeout_timer.stop()

    def _on_source_timeout(self, channel):
        if not self.player_controller or not self.player_controller.is_playing:
            return
        if hasattr(self, 'is_catchup_mode') and self.is_catchup_mode:
            return
        logger.debug(f"源超时（无备用源可切换）: {channel.get('name', '')}")

    def _save_last_channel(self, channel):
        if not channel:
            return
        try:
            name = channel.get('name', '')
            idx = -1
            for i, ch in enumerate(app_state._channels):
                if ch is channel:
                    idx = i
                    break
            file_path = ''
            if hasattr(self, 'channel_model') and hasattr(self.channel_model, 'original_data'):
                pass
            self.config.save_last_channel(file_path, name, idx)
        except Exception:
            pass

    def _load_last_channel(self):
        try:
            last = self.config.load_last_channel()
            if last.get('name') and last.get('index', -1) >= 0:
                self._pending_last_channel = last
        except Exception:
            pass

    def _try_restore_last_channel(self):
        if not hasattr(self, '_pending_last_channel'):
            return
        last = self._pending_last_channel
        delattr(self, '_pending_last_channel')
        if not app_state._channels:
            return
        idx = last.get('index', -1)
        if 0 <= idx < len(app_state._channels):
            ch = app_state._channels[idx]
            if ch.get('name') == last.get('name'):
                self.current_channel = ch
                self.select_channel_by_index(idx)

    def select_channel_by_index(self, idx):
        if not hasattr(self, 'channel_list') or idx < 0:
            return
        for i in range(self.channel_list.count()):
            item = self.channel_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == idx:
                self.channel_list.setCurrentItem(item)
                self.select_channel(item)
                return

    def switch_to_previous_channel(self):
        """Backspace 快速回切到上一个频道"""
        if not hasattr(self, '_previous_channel') or not self._previous_channel:
            return
        prev = self._previous_channel
        self._previous_channel = None
        if hasattr(self, 'channel_list'):
            for i in range(self.channel_list.count()):
                item = self.channel_list.item(i)
                ch = item.data(Qt.ItemDataRole.UserRole)
                if isinstance(ch, dict) and ch.get('url') == prev.get('url'):
                    self.channel_list.setCurrentItem(item)
                    self.select_channel(item)
                    return

    def _warmup_logos_around(self, channel):
        channels = app_state._channels
        if not channels:
            return
        current_idx = -1
        for i, ch in enumerate(channels):
            if ch is channel:
                current_idx = i
                break
        if current_idx < 0:
            return
        urls = []
        for j in range(max(0, current_idx - 5), min(current_idx + 10, len(channels))):
            logo = channels[j].get('logo', '')
            if logo:
                urls.append(logo.strip('`"\''))
        if urls:
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(3000, lambda: self._logo_cache_service.warmup(urls))

    def start_timeshift(self, offset_minutes=None):
        if not self.current_channel:
            return
        if hasattr(self, 'is_catchup_mode') and self.is_catchup_mode:
            return
        try:
            from core.config_manager import ConfigManager
            ts_settings = ConfigManager().load_timeshift_settings()
        except Exception:
            ts_settings = {}

        if offset_minutes is None:
            offset_minutes = ts_settings.get('default_offset_minutes', 30)

        catchup_source = self.current_channel.get('catchup_source', '')
        catchup_type = (self.current_channel.get('catchup', '') or '').lower().strip()
        from datetime import datetime, timedelta
        now = datetime.now()
        start_time = now - timedelta(minutes=offset_minutes)
        end_time = now

        if catchup_source or catchup_type:
            timeshift_url = self.catchup_ctrl.build_catchup_url(self.current_channel, start_time, end_time)
        else:
            url_format = ts_settings.get('url_format', '')
            if url_format:
                base_url = self.current_channel.get('url', '')
                if url_format.startswith('?') or url_format.startswith('&'):
                    timeshift_url = base_url + url_format
                else:
                    timeshift_url = url_format
                time_encoding = ts_settings.get('time_encoding', 'unix')
                start_key = ts_settings.get('start_key', 'startTime')
                end_key = ts_settings.get('end_key', 'endTime')
                layout = ts_settings.get('layout', 'start_end')

                if time_encoding == 'unix':
                    sv = str(int(start_time.timestamp()))
                    ev = str(int(end_time.timestamp()))
                elif time_encoding == 'unix_ms':
                    sv = str(int(start_time.timestamp() * 1000))
                    ev = str(int(end_time.timestamp() * 1000))
                else:
                    sv = start_time.strftime('%Y%m%d%H%M%S')
                    ev = end_time.strftime('%Y%m%d%H%M%S')

                sep = '&' if '?' in timeshift_url else '?'
                if layout == 'start_end':
                    timeshift_url += f"{sep}{start_key}={sv}&{end_key}={ev}"
                elif layout == 'start_duration':
                    duration = str(int((end_time - start_time).total_seconds()))
                    timeshift_url += f"{sep}{start_key}={sv}&duration={duration}"
                elif layout == 'playseek':
                    timeshift_url += f"{sep}playseek={sv}"
            else:
                logger.warning("时移无可用URL格式")
                return

        self._timeshift_active = True
        self._timeshift_start_time = start_time
        self._is_timeshift_mode = True
        self.is_catchup_mode = True
        self._live_timeshift_seconds = max(0, (datetime.now() - start_time).total_seconds())
        self.catchup_program = {
            'start': start_time,
            'end': end_time,
            'title': f'时移 -{offset_minutes}分钟',
            'desc': '',
        }
        self.original_channel = self.current_channel.copy()
        if hasattr(self, 'catchup_ctrl'):
            self.catchup_ctrl.original_channel = self.current_channel.copy()

        if self.player_controller:
            self.player_controller.play(timeshift_url, f"{self.current_channel.get('name', '')} (时移)")
        self._show_exit_timeshift_button()
        self._update_catchup_indicator()
        self._populate_epg_list()

    def _start_live_timeshift_from_progress(self, slider_seconds, catchup_source):
        """直播时进度条拖到缓冲区之前，自动用回看URL进行时移播放。
        
        slider_seconds: 进度条对应的秒数（从节目开始算）
        catchup_source: 频道的 catchup_source URL 模板
        """
        program_start = self._progress_program_start
        program_end = self._progress_program_end

        if program_start is None:
            logger.warning("直播时移(进度条) -> program_start 为 None，无法执行时移")
            return

        target_wallclock = program_start + timedelta(seconds=slider_seconds)
        now = datetime.now()

        if target_wallclock >= now:
            target_wallclock = now - timedelta(seconds=5)

        if target_wallclock < program_start:
            target_wallclock = program_start

        end_time = min(program_end, now) if program_end else now

        timeshift_url = self.catchup_ctrl.build_catchup_url(self.current_channel, target_wallclock, end_time)

        channel_name = self.current_channel.get('name', '')
        program_title = ''
        try:
            # 尝试从EPG获取当前节目标题
            ch_name, tvg_id, tvg_name, comma_name = self._get_epg_match_params()
            prog = self.epg_parser.get_current_program(ch_name, tvg_id, tvg_name=tvg_name, comma_name=comma_name)
            if prog:
                program_title = prog.get('title', '')
        except Exception:
            pass

        offset_from_start = int((target_wallclock - program_start).total_seconds())
        m, s = divmod(offset_from_start, 60)
        h, m = divmod(m, 60)
        offset_str = f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"

        logger.info(f"直播时移(进度条) -> 从 {target_wallclock} 开始播放，offset={offset_str}, url={timeshift_url[:80]}...")

        tr = self.language_manager.tr
        self.status_bar_show_message(
            f"{tr('timeshift_playing', '正在时移')}: {channel_name}"
            + (f" - {program_title}" if program_title else "")
            + f"  [{offset_str}]"
        )

        if hasattr(self, '_cancel_source_timeout'):
            self._cancel_source_timeout()

        if hasattr(self, 'video_placeholder') and self.video_placeholder:
            self.video_placeholder.hide()
        if hasattr(self, 'video_widget') and self.video_widget and self.video_frame:
            self.video_widget.setGeometry(0, 0, self.video_frame.width(), self.video_frame.height())
        if hasattr(self, 'floating_panel') and self.floating_panel:
            if not self.floating_panel.isVisible():
                self.floating_panel.show()

        for attr in ['_catchup_start_time', '_catchup_start_progress',
                     '_target_catchup_progress', '_disable_progress_auto_update']:
            if hasattr(self, attr):
                delattr(self, attr)

        self._timeshift_active = True
        self._timeshift_start_time = target_wallclock
        self._is_timeshift_mode = True
        self.is_catchup_mode = True
        self._live_timeshift_seconds = max(0, (datetime.now() - target_wallclock).total_seconds())
        self.original_channel = self.current_channel.copy()
        if hasattr(self, 'catchup_ctrl'):
            self.catchup_ctrl.original_channel = self.current_channel.copy()
        self.catchup_program = {
            'start': target_wallclock,
            'end': end_time,
            'title': program_title or tr('timeshift_label', '时移'),
            'desc': '',
        }

        if self.player_controller:
            self.player_controller.play(timeshift_url, f"{channel_name} (时移 {offset_str})")
        self._show_exit_timeshift_button()
        self._update_catchup_indicator()
        self._populate_epg_list()

    def _show_audio_track_menu(self):
        """显示音轨切换菜单"""
        if not self.player_controller or not self.player_controller.is_playing:
            return
        from PyQt6.QtWidgets import QMenu
        menu = QMenu(self)
        tracks = self.player_controller.get_track_list('audio')
        current_id = self.player_controller.get_current_track('audio')
        if not tracks:
            act = menu.addAction(self.language_manager.tr('no_audio_tracks', 'No audio tracks'))
            act.setEnabled(False)
        else:
            for t in tracks:
                label = t.get('title') or t.get('lang') or f"Track {t['id']}"
                if t.get('lang') and t.get('title') and t['lang'] != t['title']:
                    label = f"{t['title']} ({t['lang']})"
                act = menu.addAction(label)
                act.setCheckable(True)
                act.setChecked(t['id'] == current_id)
                act.triggered.connect(lambda checked, tid=t['id']: self.player_controller.set_track('audio', tid))
        menu.exec(self.audio_track_button.mapToGlobal(self.audio_track_button.rect().bottomLeft()))

    def _show_sub_track_menu(self):
        """显示字幕切换菜单"""
        if not self.player_controller or not self.player_controller.is_playing:
            return
        from PyQt6.QtWidgets import QMenu
        menu = QMenu(self)
        tracks = self.player_controller.get_track_list('sub')
        current_id = self.player_controller.get_current_track('sub')
        no_sub = menu.addAction(self.language_manager.tr('no_subtitle', 'No Subtitle'))
        no_sub.setCheckable(True)
        no_sub.setChecked(current_id is None or current_id == 0)
        no_sub.triggered.connect(lambda: self.player_controller.set_track('sub', 0))
        if tracks:
            menu.addSeparator()
            for t in tracks:
                label = t.get('title') or t.get('lang') or f"Sub {t['id']}"
                if t.get('lang') and t.get('title') and t['lang'] != t['title']:
                    label = f"{t['title']} ({t['lang']})"
                act = menu.addAction(label)
                act.setCheckable(True)
                act.setChecked(t['id'] == current_id)
                act.triggered.connect(lambda checked, tid=t['id']: self.player_controller.set_track('sub', tid))
        menu.exec(self.sub_track_button.mapToGlobal(self.sub_track_button.rect().bottomLeft()))

    def _set_channel_view_mode(self, mode, tab='sub'):
        """切换频道列表视图模式（list/grid）"""
        list_widget = self.sub_channel_list if tab == 'sub' else self.local_channel_list
        list_btn = getattr(self, f'{tab}_view_list_btn', None)
        grid_btn = getattr(self, f'{tab}_view_grid_btn', None)

        if mode == 'list':
            if list_btn:
                list_btn.setChecked(True)
            if grid_btn:
                grid_btn.setChecked(False)
            list_widget.setViewMode(QListWidget.ViewMode.ListMode)
            list_widget.setGridSize(QSize())
            list_widget.setIconSize(QSize())
            list_widget.setSpacing(2)
            list_widget.setWrapping(False)
            if hasattr(self, '_thumbnail_service'):
                self._thumbnail_service.stop()
        elif mode == 'grid':
            if list_btn:
                list_btn.setChecked(False)
            if grid_btn:
                grid_btn.setChecked(True)
            list_widget.setViewMode(QListWidget.ViewMode.IconMode)
            list_widget.setGridSize(QSize(230, 150))
            list_widget.setIconSize(QSize(210, 118))
            list_widget.setSpacing(2)
            list_widget.setWrapping(True)
            list_widget.setResizeMode(QListWidget.ResizeMode.Adjust)
            list_widget.verticalScrollBar().setSingleStep(30)

        source = 'subscription' if tab == 'sub' else 'local'
        self.populate_channel_list(source)

        if mode == 'grid':
            QTimer.singleShot(200, lambda: self._capture_visible_thumbnails(tab))

    def _take_screenshot(self):
        """S键截图 - 保存到 screenshots 目录并复制到剪贴板"""
        if not self.player_controller or not self.player_controller.is_playing:
            return
        try:
            import os
            from datetime import datetime
            from PyQt6.QtWidgets import QApplication
            from PyQt6.QtGui import QClipboard

            screenshot_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'screenshots')
            os.makedirs(screenshot_dir, exist_ok=True)

            channel_name = ''
            if self.current_channel:
                channel_name = self.current_channel.get('name', '')
                channel_name = re.sub(r'[\\/:*?"<>|]', '_', channel_name)

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{channel_name}_{timestamp}.png" if channel_name else f"screenshot_{timestamp}.png"
            filepath = os.path.join(screenshot_dir, filename)

            self.player_controller.send_command(['screenshot-to-file', filepath, 'video'])

            clipboard = QApplication.clipboard()
            from PyQt6.QtGui import QPixmap
            pixmap = QPixmap(filepath)
            if not pixmap.isNull():
                clipboard.setPixmap(pixmap)

            self.status_bar_show_message(
                f"{self.language_manager.tr('screenshot_saved', 'Screenshot saved')}: {filename}")
        except Exception as e:
            from core.log_manager import global_logger as logger
            logger.error(f"截图失败: {e}")

    def _adjust_speed(self, delta):
        """倍速微调 (> / < 键)"""
        if not self.player_controller:
            return
        current = self.player_controller.get_speed()
        new_speed = round(max(0.1, min(10.0, current + delta)), 1)
        self.player_controller.set_speed(new_speed)
        if hasattr(self, 'speed_button'):
            self.speed_button.setText(f"{new_speed}x")
        if not self._osd_visible:
            self._show_osd_feedback(f"{self.language_manager.tr('osd_speed', 'Speed')}: {new_speed}x")

    def toggle_pip_mode(self, checked=None):
        """P键画中画模式 - 小窗口置顶播放"""
        if getattr(self, '_pip_mode', False):
            self._exit_pip_mode()
            return
        pc = self.player_controller
        has_content = (pc and (pc.is_playing or getattr(pc, 'is_paused', False))) or getattr(self, 'current_channel', None)
        if not has_content:
            if hasattr(self, '_pip_menu_action') and self._pip_menu_action:
                self._pip_menu_action.setChecked(False)
            return
        self._enter_pip_mode()

    def _enter_pip_mode(self):
        """进入画中画模式"""
        if getattr(self, '_pip_mode', False):
            return

        try:
            self._pip_saved_geometry = self.geometry()
            self._pip_saved_maximized = self.isMaximized()
            self._pip_saved_fullscreen = getattr(self, 'is_fullscreen', False)

            self._pip_saved_visibilities = {
                'title_bar': hasattr(self, '_title_bar') and self._title_bar and self._title_bar.isVisible(),
                'menu_bar': hasattr(self, '_custom_menu_bar') and self._custom_menu_bar and self._custom_menu_bar.isVisible(),
                'status_bar': bool(self.status_bar and self.status_bar.isVisible()),
                'epg': self.epg_visible,
                'playlist': self.playlist_visible,
                'floating': self.floating_panel_visible,
                'floating_hidden': getattr(self, '_floating_hidden', False),
            }

            if self._pip_saved_fullscreen:
                self.toggle_fullscreen()

            if self.isMaximized():
                self.showNormal()

            self._stop_auto_hide_timer()

            self._pip_mode = True
            self.epg_visible = False
            self.playlist_visible = False
            self.floating_panel_visible = False

            if hasattr(self, '_title_bar') and self._title_bar:
                self._title_bar.hide()
            if hasattr(self, '_custom_menu_bar') and self._custom_menu_bar:
                self._custom_menu_bar.hide()
            if self.status_bar:
                self.status_bar.hide()
            if hasattr(self, 'epg_panel') and self.epg_panel:
                self.epg_panel.hide()
            if hasattr(self, 'playlist_panel') and self.playlist_panel:
                self.playlist_panel.hide()
            if hasattr(self, 'floating_panel') and self.floating_panel:
                self.floating_panel.hide()

            pip_w, pip_h = 480, 270
            from PyQt6.QtWidgets import QApplication
            scr = self.screen()
            primary = QApplication.primaryScreen()
            if scr:
                screen = scr.availableGeometry()
            elif primary:
                screen = primary.availableGeometry()
            else:
                logger.error("_enter_pip_mode: 无法获取屏幕信息")
                self._pip_mode = False
                self._restore_pip_hidden_elements()
                return

            x = screen.right() - pip_w - 20
            y = screen.bottom() - pip_h - 20

            self.setMinimumSize(240, 135)
            self.setMaximumSize(16777215, 16777215)
            self.resize(pip_w, pip_h)
            self.move(x, y)

            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
            self.show()
            self.raise_()

            self._pip_dragging = False
            self._pip_drag_pos = None
            self._pip_resizing = False
            self._pip_resize_edge = None
            self._pip_resize_start_geo = None
            self._pip_resize_start_pos = None
            self.setMouseTracking(True)

            if not hasattr(self, '_pip_buttons') or not self._pip_buttons:
                self._create_pip_overlay()

            from PyQt6.QtCore import QTimer
            QTimer.singleShot(50, self._show_pip_overlay)
            QTimer.singleShot(50, self._update_pip_video_geometry)

            if hasattr(self, '_pip_menu_action') and self._pip_menu_action:
                self._pip_menu_action.setChecked(True)
            self.status_bar_show_message(
                self.language_manager.tr('pip_mode', 'PiP Mode') + " - P " +
                self.language_manager.tr('to_exit', 'to exit'))
            logger.info("已进入画中画模式")
        except Exception as e:
            logger.error(f"进入画中画模式失败: {e}")
            self._pip_mode = False
            self._restore_pip_hidden_elements()

    def _exit_pip_mode(self):
        """退出画中画模式"""
        if not getattr(self, '_pip_mode', False):
            return

        try:
            self._pip_mode = False
            self._hide_pip_overlay()

            self.setMinimumSize(0, 0)
            self.setMaximumSize(16777215, 16777215)

            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, False)
            self.show()
            self.raise_()

            if getattr(self, '_pip_saved_maximized', False):
                self.showMaximized()
            elif hasattr(self, '_pip_saved_geometry'):
                self.setGeometry(self._pip_saved_geometry)

            self._pip_dragging = False
            self._pip_resizing = False
            self.unsetCursor()
            if hasattr(self, '_pip_menu_action') and self._pip_menu_action:
                self._pip_menu_action.setChecked(False)

            self._pip_exit_status_msg = (
                self.language_manager.tr('pip_mode', 'PiP Mode') + " " +
                self.language_manager.tr('pip_exited', 'exited'))

            from PyQt6.QtCore import QTimer
            QTimer.singleShot(100, self._restore_pip_hidden_elements)
            QTimer.singleShot(200, self.update_floating_position)
            QTimer.singleShot(300, self._restart_auto_hide_timer)
            logger.info("已退出画中画模式")
        except Exception as e:
            logger.error(f"退出画中画模式失败: {e}")
            self._pip_mode = False

    def _restore_pip_hidden_elements(self):
        """恢复画中画模式隐藏的UI元素"""
        saved = getattr(self, '_pip_saved_visibilities', {})
        if not saved:
            return

        if saved.get('title_bar', True) and hasattr(self, '_title_bar') and self._title_bar:
            self._title_bar.show()
        if saved.get('menu_bar', True) and hasattr(self, '_custom_menu_bar') and self._custom_menu_bar:
            self._custom_menu_bar.show()
        if saved.get('status_bar', True) and self.status_bar:
            self.status_bar.show()
        if saved.get('epg', True) and hasattr(self, 'epg_panel') and self.epg_panel:
            self.epg_panel.show()
            self.epg_visible = True
        else:
            self.epg_visible = False
        if saved.get('playlist', True) and hasattr(self, 'playlist_panel') and self.playlist_panel:
            self.playlist_panel.show()
            self.playlist_visible = True
        else:
            self.playlist_visible = False
        if saved.get('floating', True) and hasattr(self, 'floating_panel') and self.floating_panel:
            self.floating_panel.show()
            self.floating_panel_visible = True
        else:
            self.floating_panel_visible = False
        self._floating_hidden = saved.get('floating_hidden', False)
        self._sync_panel_actions()

        exit_msg = getattr(self, '_pip_exit_status_msg', '')
        if exit_msg:
            self.status_bar_show_message(exit_msg)
            self._pip_exit_status_msg = ''

    def _create_pip_overlay(self):
        """创建画中画控制按钮（使用独立Qt::Tool窗口，确保在D3D11视频之上显示）"""
        from PyQt6.QtWidgets import QWidget
        from PyQt6.QtCore import Qt

        self._pip_overlay_widget = QWidget(
            self,
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self._pip_overlay_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._pip_overlay_widget.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self._pip_overlay_widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        btn_size = 44
        self._pip_prev_btn = self._create_pip_button("⏮", btn_size)
        self._pip_play_btn = self._create_pip_button("⏸", btn_size)
        self._pip_next_btn = self._create_pip_button("⏭", btn_size)
        self._pip_close_btn = self._create_pip_button("✕", btn_size)

        self._pip_buttons = [self._pip_prev_btn, self._pip_play_btn, self._pip_next_btn, self._pip_close_btn]
        for btn in self._pip_buttons:
            btn.setParent(self._pip_overlay_widget)
            btn.hide()

        self._pip_overlay_widget.hide()

    def _create_pip_button(self, text, btn_size):
        """创建画中画圆形按钮（自定义绘制，无背景填充）"""
        from PyQt6.QtWidgets import QWidget
        from PyQt6.QtGui import QPainter, QPen, QColor, QFont, QRegion
        from PyQt6.QtCore import QRect, Qt

        class PipButton(QWidget):
            def __init__(self, label, size, parent):
                super().__init__(parent)
                self._label = label
                self._size = size
                self._hovered = False
                self.setFixedSize(size, size)
                self.setCursor(Qt.CursorShape.PointingHandCursor)
                self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
                self.setAutoFillBackground(False)
                self.setMouseTracking(True)
                circle = QRegion(QRect(0, 0, size, size), QRegion.RegionType.Ellipse)
                self.setMask(circle)

            def set_label(self, label):
                self._label = label
                self.update()

            def paintEvent(self, event):
                painter = QPainter(self)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                if self._hovered:
                    painter.setBrush(QColor(50, 50, 50, 200))
                    pen = QPen(QColor(255, 255, 255, 220), 2)
                else:
                    painter.setBrush(QColor(20, 20, 20, 160))
                    pen = QPen(QColor(255, 255, 255, 150), 2)
                painter.setPen(pen)
                painter.drawEllipse(1, 1, self._size - 2, self._size - 2)
                painter.setPen(QColor(255, 255, 255, 230))
                font = QFont()
                font.setPixelSize(int(self._size * 0.4))
                painter.setFont(font)
                painter.drawText(QRect(0, 0, self._size, self._size), Qt.AlignmentFlag.AlignCenter, self._label)
                painter.end()

            def enterEvent(self, event):
                self._hovered = True
                self.update()
                super().enterEvent(event)

            def leaveEvent(self, event):
                self._hovered = False
                self.update()
                super().leaveEvent(event)

            def mousePressEvent(self, event):
                if event.button() == Qt.MouseButton.LeftButton:
                    main_win = self.window().parent()
                    if main_win and hasattr(main_win, '_pip_btn_clicked'):
                        main_win._pip_btn_clicked(self)

        btn = PipButton(text, btn_size, None)
        return btn

    def _pip_btn_clicked(self, btn):
        """画中画按钮点击回调"""
        if btn is getattr(self, '_pip_prev_btn', None):
            logger.debug("画中画: 点击上一个频道按钮")
            self._pip_prev_channel()
        elif btn is getattr(self, '_pip_play_btn', None):
            logger.debug("画中画: 点击播放/暂停按钮")
            self._pip_toggle_play()
        elif btn is getattr(self, '_pip_next_btn', None):
            logger.debug("画中画: 点击下一个频道按钮")
            self._pip_next_channel()
        elif btn is getattr(self, '_pip_close_btn', None):
            logger.debug("画中画: 点击关闭按钮")
            self._exit_pip_mode()

    def _pip_prev_channel(self):
        """画中画：上一个频道"""
        if hasattr(self, 'event_handler'):
            self.event_handler._switch_channel(-1)

    def _pip_toggle_play(self):
        """画中画：暂停/播放"""
        if hasattr(self, 'playback_ctrl'):
            self.playback_ctrl.toggle_play()
            self._pip_update_play_btn()

    def _pip_update_play_btn(self):
        """更新画中画播放/暂停按钮状态"""
        if not hasattr(self, '_pip_play_btn') or not self._pip_play_btn:
            return
        pc = self.player_controller
        if pc and pc.is_playing:
            self._pip_play_btn.set_label("⏸")
        else:
            self._pip_play_btn.set_label("▶")

    def _pip_next_channel(self):
        """画中画：下一个频道"""
        if hasattr(self, 'event_handler'):
            self.event_handler._switch_channel(1)

    def _pip_get_resize_edge(self, pos):
        """判断鼠标是否在画中画窗口调整大小边缘区域"""
        if not getattr(self, '_pip_mode', False):
            return None
        margin = 8
        w = self.width()
        h = self.height()
        x, y = pos.x(), pos.y()

        edges = []
        if x < margin:
            edges.append('left')
        if x > w - margin:
            edges.append('right')
        if y < margin:
            edges.append('top')
        if y > h - margin:
            edges.append('bottom')

        if not edges:
            return None
        return '-'.join(edges)

    def _pip_update_cursor(self, edge):
        """根据调整大小边缘更新鼠标光标"""
        if edge is None:
            self.unsetCursor()
        elif edge in ('left', 'right'):
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        elif edge in ('top', 'bottom'):
            self.setCursor(Qt.CursorShape.SizeVerCursor)
        elif edge in ('top-left', 'bottom-right'):
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif edge in ('top-right', 'bottom-left'):
            self.setCursor(Qt.CursorShape.SizeBDiagCursor)
        else:
            self.unsetCursor()

    def _pip_mouse_press(self, event):
        """画中画模式鼠标按下"""
        if not getattr(self, '_pip_mode', False):
            return False
        if event.button() == Qt.MouseButton.LeftButton:
            if hasattr(self, '_pip_overlay_widget') and self._pip_overlay_widget.isVisible():
                gpos = event.globalPosition().toPoint()
                overlay_geo = self._pip_overlay_widget.geometry()
                if overlay_geo.contains(gpos):
                    return False
            edge = self._pip_get_resize_edge(event.position().toPoint())
            if edge:
                self._pip_resizing = True
                self._pip_resize_edge = edge
                self._pip_resize_start_geo = self.geometry()
                self._pip_resize_start_pos = event.globalPosition().toPoint()
                return True
            else:
                self._pip_dragging = True
                self._pip_drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                return True
        return False

    def _pip_mouse_move(self, event):
        """画中画模式鼠标移动"""
        if not getattr(self, '_pip_mode', False):
            return False

        if self._pip_dragging and self._pip_drag_pos is not None:
            new_pos = event.globalPosition().toPoint() - self._pip_drag_pos
            self.move(new_pos)
            return True

        if self._pip_resizing and self._pip_resize_edge:
            delta = event.globalPosition().toPoint() - self._pip_resize_start_pos
            geo = self._pip_resize_start_geo
            min_w, min_h = 240, 135

            dx_left = 0
            dx_right = 0
            dy_top = 0
            dy_bottom = 0

            if 'left' in self._pip_resize_edge:
                dx_left = min(delta.x(), geo.width() - min_w)
            if 'right' in self._pip_resize_edge:
                dx_right = max(delta.x(), min_w - geo.width())
            if 'top' in self._pip_resize_edge:
                dy_top = min(delta.y(), geo.height() - min_h)
            if 'bottom' in self._pip_resize_edge:
                dy_bottom = max(delta.y(), min_h - geo.height())

            new_x = geo.x() + dx_left
            new_y = geo.y() + dy_top
            new_w = geo.width() - dx_left + dx_right
            new_h = geo.height() - dy_top + dy_bottom

            self.setGeometry(new_x, new_y, max(min_w, new_w), max(min_h, new_h))
            self._update_pip_overlay_geometry()
            self._update_pip_video_geometry()
            return True

        edge = self._pip_get_resize_edge(event.position().toPoint())
        self._pip_update_cursor(edge)
        return False

    def _pip_mouse_release(self, event):
        """画中画模式鼠标释放"""
        if not getattr(self, '_pip_mode', False):
            return False
        if event.button() == Qt.MouseButton.LeftButton:
            self._pip_dragging = False
            self._pip_drag_pos = None
            self._pip_resizing = False
            self._pip_resize_edge = None
            self._pip_resize_start_geo = None
            self._pip_resize_start_pos = None
            return True
        return False

    def _update_pip_video_geometry(self):
        """画中画模式下同步video_widget尺寸到video_frame"""
        if not getattr(self, '_pip_mode', False):
            return
        if hasattr(self, 'video_widget') and self.video_widget and hasattr(self, 'video_frame') and self.video_frame:
            self.video_widget.setGeometry(0, 0, self.video_frame.width(), self.video_frame.height())

    def _update_pip_overlay_geometry(self):
        """更新画中画覆盖窗口和按钮位置"""
        if not getattr(self, '_pip_mode', False):
            return
        if not hasattr(self, '_pip_buttons'):
            return
        if not hasattr(self, 'video_widget') or not self.video_widget:
            return
        if not hasattr(self, '_pip_overlay_widget'):
            return

        vw = self.video_widget
        top_left = vw.mapToGlobal(vw.rect().topLeft())
        self._pip_overlay_widget.setGeometry(top_left.x(), top_left.y(), vw.width(), vw.height())

        btn_size = 44
        spacing = 16
        total_w = btn_size * 3 + spacing * 2
        cx = vw.width() // 2
        cy = vw.height() // 2
        start_x = cx - total_w // 2
        control_btns = [self._pip_prev_btn, self._pip_play_btn, self._pip_next_btn]
        positions = [
            (start_x, cy - btn_size // 2),
            (start_x + btn_size + spacing, cy - btn_size // 2),
            (start_x + (btn_size + spacing) * 2, cy - btn_size // 2),
        ]
        for btn, (x, y) in zip(control_btns, positions):
            btn.move(x, y)

        close_margin = 6
        if hasattr(self, '_pip_close_btn') and self._pip_close_btn:
            self._pip_close_btn.move(vw.width() - btn_size - close_margin, close_margin)

        from PyQt6.QtGui import QRegion
        from PyQt6.QtCore import QRect
        mask = QRegion()
        for btn in self._pip_buttons:
            if not btn.isHidden():
                mask = mask.united(QRegion(btn.geometry()))
        if mask.isEmpty():
            mask = QRegion(QRect(0, 0, 1, 1))
        self._pip_overlay_widget.setMask(mask)

    def _show_pip_overlay(self):
        """显示画中画控制按钮"""
        if not getattr(self, '_pip_mode', False):
            return
        if not hasattr(self, '_pip_buttons'):
            return
        self._pip_update_play_btn()
        for btn in self._pip_buttons:
            btn.show()
        self._update_pip_overlay_geometry()
        if hasattr(self, '_pip_overlay_widget'):
            self._pip_overlay_widget.show()

    def _hide_pip_overlay(self):
        """隐藏画中画控制按钮"""
        if hasattr(self, '_pip_overlay_widget'):
            self._pip_overlay_widget.hide()
        if not hasattr(self, '_pip_buttons'):
            return
        for btn in self._pip_buttons:
            btn.hide()

    def _pip_delayed_hide_overlay(self):
        """延迟隐藏画中画按钮（避免鼠标移到按钮上时误隐藏）"""
        if not getattr(self, '_pip_mode', False):
            return
        cursor_pos = self.cursor().pos()
        if self.rect().contains(self.mapFromGlobal(cursor_pos)):
            return
        if hasattr(self, '_pip_overlay_widget') and self._pip_overlay_widget.isVisible():
            overlay_rect = self._pip_overlay_widget.geometry()
            if overlay_rect.contains(cursor_pos):
                return
        self._hide_pip_overlay()

    _SPEED_STEPS = [0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 3.0, 5.0]

    def _cycle_speed(self):
        if not self.player_controller:
            return
        current = self.player_controller.get_speed()
        idx = 0
        for i, s in enumerate(self._SPEED_STEPS):
            if abs(current - s) < 0.01:
                idx = i
                break
        next_idx = (idx + 1) % len(self._SPEED_STEPS)
        new_speed = self._SPEED_STEPS[next_idx]
        self.player_controller.set_speed(new_speed)
        if hasattr(self, 'speed_button'):
            self.speed_button.setText(f"{new_speed}x")
        if not self._osd_visible:
            self._show_osd_feedback(f"{self.language_manager.tr('osd_speed', 'Speed')}: {new_speed}x")

    _ASPECT_CYCLE = ['default', '16:9', '4:3', 'stretch', 'fill']

    def _cycle_aspect_ratio(self):
        if not self.player_controller:
            return
        if not hasattr(self, '_current_aspect_idx'):
            self._current_aspect_idx = 0
        self._current_aspect_idx = (self._current_aspect_idx + 1) % len(self._ASPECT_CYCLE)
        ratio = self._ASPECT_CYCLE[self._current_aspect_idx]
        self.player_controller.set_aspect_ratio(ratio)
        labels = {'default': '📐', '16:9': '16:9', '4:3': '4:3', 'stretch': '↔', 'fill': '⬛'}
        if hasattr(self, 'aspect_button'):
            self.aspect_button.setText(labels.get(ratio, '📐'))
        self._save_aspect_ratio(ratio)

    def _save_aspect_ratio(self, ratio):
        try:
            self.config.set_value('Player', 'aspect_ratio', ratio)
            self.config.save_config()
        except Exception:
            pass

    def _restore_aspect_ratio(self):
        try:
            ratio = self.config.get_value('Player', 'aspect_ratio', 'default') or 'default'
            if ratio in self._ASPECT_CYCLE:
                self._current_aspect_idx = self._ASPECT_CYCLE.index(ratio)
            else:
                self._current_aspect_idx = 0
                ratio = 'default'
            if self.player_controller:
                self.player_controller.set_aspect_ratio(ratio)
            labels = {'default': '📐', '16:9': '16:9', '4:3': '4:3', 'stretch': '↔', 'fill': '⬛'}
            if hasattr(self, 'aspect_button'):
                self.aspect_button.setText(labels.get(ratio, '📐'))
        except Exception:
            pass

    def _update_catchup_indicator(self):
        try:
            if not hasattr(self, 'catchup_indicator'):
                return

            is_timeshift = getattr(self, '_is_timeshift_mode', False)
            is_catchup = getattr(self, 'is_catchup_mode', False)

            if is_timeshift:
                self.catchup_indicator.setText(self.language_manager.tr('timeshift_watching', '正在时移观看'))
                self.catchup_indicator.show()
            elif is_catchup and not is_timeshift:
                self.catchup_indicator.setText(self.language_manager.tr('catchup_playing_label', '正在回看'))
                self.catchup_indicator.show()
            elif self.current_channel and (
                self.current_channel.get('catchup_source', '')
                or self.current_channel.get('catchup', '')
            ):
                self.catchup_indicator.setText(self.language_manager.tr('catchup_available', '可回放'))
                self.catchup_indicator.show()
            else:
                self.catchup_indicator.hide()
        except Exception:
            pass

# 主函数
if __name__ == "__main__":
    import time
    app_start_time = time.time()
    app = QApplication(sys.argv)
    player = IPTVPlayer()

    # 处理命令行参数（右键"打开方式"传入的文件路径）
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        if os.path.isfile(file_path):
            if file_path.lower().endswith(('.m3u', '.m3u8', '.txt')):
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(800, lambda: player.settings_ops.open_specific_file(file_path))
            elif file_path.lower().endswith(('.mp4', '.mkv', '.avi', '.mov',
                                             '.flv', '.wmv', '.ts', '.webm')):
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(800, lambda: player.player_controller.play(file_path) if player.player_controller else None)

    # show() 已在 _initialize_in_order 中调用，此处直接进入事件循环
    sys.exit(app.exec())
