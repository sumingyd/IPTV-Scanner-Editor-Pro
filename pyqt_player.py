import sys
import os
from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.play_state import PlayStateManager
from core.panel_visibility import PanelVisibilityManager
from controllers.progress_controller import ProgressController
from models.channel_model import ChannelListModel
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QListWidget, QListWidgetItem,
    QStatusBar, QSizePolicy,
    QFrame, QToolButton, QSlider, QComboBox,
    QTabWidget
)
from PyQt6 import QtWidgets
from PyQt6.QtCore import Qt, QSize, QTimer, QThread, pyqtSlot, pyqtSignal, QRectF
from PyQt6 import QtCore
from PyQt6.QtGui import QIcon, QFont, QFontMetrics, QColor, QAction, QPainter, QBrush, QShortcut, QPen, QLinearGradient, QPainterPath, QPixmap

from core.log_manager import global_logger as logger
from core.application_state import app_state
from core.language_manager import LanguageManager
from ui.styles import AppStyles
from ui.cache_progress_slider import CacheProgressSlider

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
    CatchupController,
    PipController,
    MediaController,
    UpdateController
)

from utils.general_utils import calculate_adaptive_delay


class _RoundedContainer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

    def paintEvent(self, event):
        from ui.styles import AppStyles
        r = AppStyles._get_style_border_radius()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        rect = QRectF(self.rect())
        path.addRoundedRect(rect, r, r)
        painter.setClipPath(path)
        painter.end()
        super().paintEvent(event)


class VideoOverlayBadge(QWidget):
    """视频区域叠加标识 Widget，用 QPainter 绘制精美的回看/时移标签"""

    MODE_CATCHUP   = 'catchup'
    MODE_TIMESHIFT = 'timeshift'

    @staticmethod
    def _get_mode_configs():
        from ui.styles import AppStyles
        c = AppStyles._get_colors()
        return {
            'catchup': (c['accent'], c['accent_pressed'], '▶ ', c['window']),
            'timeshift': (c['warning'], c['accent_pressed'], '⏪ ', c['window']),
        }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mode = self.MODE_CATCHUP
        self._label_text = ''
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NativeWindow)
        self.setAttribute(Qt.WidgetAttribute.WA_DontCreateNativeAncestors)
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
        cfg = self._get_mode_configs().get(self._mode, self._get_mode_configs()[self.MODE_CATCHUP])
        icon = cfg[2]
        return icon, self._label_text

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        cfg = self._get_mode_configs().get(self._mode, self._get_mode_configs()[self.MODE_CATCHUP])
        color1, color2, icon, text_color = cfg

        r = self.rect()
        radius = r.height() / 2

        # 绘制圆角矩形背景 (渐变)
        path = QPainterPath()
        path.addRoundedRect(0, 0, r.width(), r.height(), radius, radius)

        grad = QLinearGradient(0, 0, r.width(), 0)
        from ui.styles import color_to_qcolor
        grad.setColorAt(0, color_to_qcolor(color1))
        grad.setColorAt(1, color_to_qcolor(color2))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(grad))
        painter.drawPath(path)

        # 微光描边
        painter.setPen(QPen(QColor(255, 255, 255, 40), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

        # 绘制文字 (图标 + 标签)
        painter.setFont(self._font)
        painter.setPen(color_to_qcolor(text_color))
        full_text = icon + self._label_text
        painter.drawText(r, Qt.AlignmentFlag.AlignCenter, full_text)

        painter.end()


# 导入播放器服务
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

    @property
    def epg_visible(self):
        return self.panel_vis.get_visible('epg')

    @epg_visible.setter
    def epg_visible(self, value):
        self.panel_vis.set_visible('epg', value)

    @property
    def playlist_visible(self):
        return self.panel_vis.get_visible('playlist')

    @playlist_visible.setter
    def playlist_visible(self, value):
        self.panel_vis.set_visible('playlist', value)

    @property
    def floating_panel_visible(self):
        return self.panel_vis.get_visible('floating')

    @floating_panel_visible.setter
    def floating_panel_visible(self, value):
        self.panel_vis.set_visible('floating', value)

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
    pip_ctrl = None
    media_ctrl = None

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

    PLAYLIST_EXTENSIONS = ('.m3u', '.m3u8', '.txt')
    VIDEO_EXTENSIONS = ('.mp4', '.mkv', '.avi', '.mov', '.flv', '.wmv', '.ts', '.webm')
    ALL_DROP_EXTENSIONS = PLAYLIST_EXTENSIONS + VIDEO_EXTENSIONS

    is_fullscreen = False
    _live_timeshift_seconds = 0
    catchup_program: Optional[Dict[str, Any]] = None
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

        from ui.menu_proxy_style import MenuRoundedProxyStyle
        self._menu_proxy_style = MenuRoundedProxyStyle(self.style())
        self.setStyle(self._menu_proxy_style)

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

        from core.version import CURRENT_VERSION
        current_version = CURRENT_VERSION
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
        self._dragging = False
        self._drag_offset = None
        self._last_mouse_pos = None

        self.play_state = PlayStateManager()
        self.panel_vis = PanelVisibilityManager(self)
        self.progress_ctrl = ProgressController(self)
        self.channel_model = ChannelListModel()
        self.current_channel = None
        self.original_channel: Optional[Dict[str, Any]] = None

        self._floating_hidden = False
        self._suppress_volume_osd = False
        self._osd_visible = False
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
        self._last_info_key = None

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
        self.pip_ctrl = PipController(self)
        self.media_ctrl = MediaController(self)
        self.update_ctrl = UpdateController(self)
        from controllers.multi_screen_controller import MultiScreenController
        self.multi_screen_ctrl = MultiScreenController(self)
        logger.debug("业务控制器初始化完成")

    def _init_basic_ui(self):
        """创建最基础的UI框架：无边框窗口、容器、标题栏、内容区域"""
        logger.debug("创建最最基本的UI")
        self.setWindowFlags(QtCore.Qt.WindowType.FramelessWindowHint | QtCore.Qt.WindowType.Window)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMouseTracking(True)
        self.setAcceptDrops(True)

        self._main_container = _RoundedContainer()
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

    @property
    def pip_mode(self):
        return self.pip_ctrl.is_active

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

    def mousePressEvent(self, event):
        """鼠标按下事件"""
        if getattr(self, 'is_fullscreen', False):
            self._on_mouse_activity()
        if self.pip_mode:
            if self.pip_ctrl.handle_mouse_press(event):
                return
        if not self.window_ctrl.handle_mouse_press_event(event):
            self.update_floating_position()
            super().mousePressEvent(event)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                path = url.toLocalFile()
                if path.lower().endswith(self.ALL_DROP_EXTENSIONS):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if not path:
                continue
            if path.lower().endswith(self.PLAYLIST_EXTENSIONS):
                if hasattr(self, 'settings_ops'):
                    self.settings_ops.open_specific_file(path)
                event.acceptProposedAction()
                return
            elif path.lower().endswith(self.VIDEO_EXTENSIONS):
                name = os.path.splitext(os.path.basename(path))[0]
                tr = self.language_manager.tr
                channel = {
                    'name': name,
                    'url': path,
                    'group': tr("local_video", "本地视频"),
                    '_groups': [tr("local_video", "本地视频")],
                }
                self._add_to_local_list(channel)
                self.config.add_recent_file(path)
                self.update_recent_files_menu()
                logger.info(f"拖放打开视频文件: {path}")
                event.acceptProposedAction()
                return
        event.ignore()

    def _fix_win32_drag_drop(self):
        """修复 Win32 无边框窗口拖放失效问题

        Qt6 的 FramelessWindowHint + WA_TranslucentBackground 会导致
        Windows OLE 拖放目标未注册，需要在窗口显示后手动初始化 OLE 并重新注册。
        """
        if sys.platform != 'win32':
            return
        try:
            import ctypes
            from ctypes import wintypes
            ole32 = ctypes.windll.ole32
            ole32.OleInitialize(None)
            hwnd = int(self.winId())
            user32 = ctypes.windll.user32
            user32.DragAcceptFiles(hwnd, True)
        except Exception:
            pass

    def mouseMoveEvent(self, event):
        """鼠标移动事件"""
        if getattr(self, 'is_fullscreen', False):
            self._on_mouse_activity()
        if self.pip_mode:
            if self.pip_ctrl.handle_mouse_move(event):
                return
        if not self.window_ctrl.handle_mouse_move_event(event):
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """鼠标释放事件"""
        if self.pip_mode:
            if self.pip_ctrl.handle_mouse_release(event):
                return
        self.window_ctrl.handle_mouse_release_event(event)
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        """鼠标双击事件 - 视频区域双击切换全屏，标题栏双击最大化"""
        if self.pip_mode:
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
        if self.pip_mode:
            return
        if getattr(self, 'is_fullscreen', False):
            self._on_mouse_activity()
        delta = event.angleDelta().y()
        if delta != 0 and hasattr(self, 'event_handler'):
            step = 5
            self.event_handler._adjust_volume(step if delta > 0 else -step)

    def enterEvent(self, event):
        """鼠标进入窗口"""
        if self.pip_mode:
            self.pip_ctrl.show_overlay()
        elif not getattr(self, '_floating_hidden', False) and not getattr(self, 'is_fullscreen', False):
            self._show_floating_panels_on_enter()
        super().enterEvent(event)

    def leaveEvent(self, event):
        """鼠标离开窗口"""
        if self.pip_mode:
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(50, self.pip_ctrl.delayed_hide_overlay)
        elif not getattr(self, '_floating_hidden', False) and not getattr(self, 'is_fullscreen', False):
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(50, self._delayed_hide_floating_panels)
        super().leaveEvent(event)
    
    def _update_splash(self, message):
        try:
            from PyQt6.QtWidgets import QSplashScreen
            app = QApplication.instance()
            for widget in app.topLevelWidgets():
                if isinstance(widget, QSplashScreen):
                    widget.showMessage(message, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter, QColor(200, 200, 200))
                    app.processEvents()
                    break
        except Exception:
            pass

    def _initialize_in_order(self):
        """按照顺序执行初始化流程"""
        logger.debug("_initialize_in_order: 开始")

        # 1. 菜单栏、工具栏
        self._update_splash("Loading UI...")
        self._init_video_components()
        # 2. 视频区域
        self._create_video_area()
        # 3. 状态栏
        self._create_status_bar()
        # 4. 播放器
        self._update_splash("Initializing player...")
        self._init_player()
        # 5. 定时器
        self._create_timer()
        # 6-8. 面板延迟创建（窗口show后由 _deferred_create_panels 创建）
        # 9. 最近文件菜单
        self._update_recent_files_menu()
        # 10. 事件过滤器（幂等，只注册一次）
        self._install_event_filters()

        # ---- 所有同步 UI 构建完成，现在显示窗口 ----
        self.show()

        # 6-8. 延迟创建面板（窗口已显示，避免阻塞首帧）
        self._update_splash("Loading panels...")
        self._create_epg_panel(show=False)
        self._create_playlist_panel(show=False)
        self._create_bottom_panel(show=False)

        # 11. 注册清理 / 主题 / 快捷键（轻量，不阻塞）
        from utils.resource_cleaner import register_cleanup
        from services.ffprobe_validator_service import FfprobeStreamValidator
        register_cleanup(FfprobeStreamValidator.terminate_all, "ffprobe_validator_terminate_all")

        self._theme_manager.register_window(self)

        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        self._space_shortcut = QShortcut(' ', app)
        self._space_shortcut.activated.connect(self.toggle_play)
        self._space_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)

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
        self.video_frame.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.video_frame.customContextMenuRequested.connect(self.media_ctrl.show_video_context_menu)
        
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
                self.video_placeholder.setText("")
        else:
            self.video_placeholder.setText("")

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
        self._timeshift_start_time = None

        self._load_last_channel()
        self.media_ctrl.restore_aspect_ratio()

        logger.debug("_init_player: 完成")
    


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
        epg_container.setMinimumWidth(200)
        self.epg_layout = QVBoxLayout(epg_container)
        self.epg_layout.setContentsMargins(0, 0, 0, 0)
        self.epg_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # EPG标题
        self.epg_title = QLabel(tr('epg_title', 'Program Guide'))
        self.epg_title.setStyleSheet(AppStyles.player_epg_title_style())
        epg_icon_path = AppStyles.get_icon('calendar', AppStyles._get_colors().get('player_panel_text', AppStyles._safe_fallback('player_panel_text')))
        if epg_icon_path:
            self.epg_title.setProperty('icon_path', epg_icon_path)
        self.epg_layout.addWidget(self.epg_title)

        # 日期选择器
        date_layout = QHBoxLayout()
        date_layout.setContentsMargins(8, 4, 8, 4)
        date_layout.setSpacing(8)

        date_icon_color = AppStyles._get_colors().get('player_panel_text', AppStyles._safe_fallback('player_panel_text'))
        self.epg_prev_day = QPushButton()
        self.epg_prev_day.setIcon(QIcon(AppStyles.get_icon('chevron_left', date_icon_color, 12)))
        self.epg_prev_day.setIconSize(QSize(12, 12))
        self.epg_prev_day.setFixedSize(24, 24)
        self.epg_prev_day.setCursor(Qt.CursorShape.PointingHandCursor)
        self.epg_prev_day.setStyleSheet(AppStyles.player_date_button_style())
        self.epg_prev_day.clicked.connect(self.epg_ctrl.on_prev_day)
        self.epg_prev_day.setToolTip(tr("tooltip_prev_day", "前一天"))
        date_layout.addWidget(self.epg_prev_day)

        self.epg_date_label = QLabel(tr("today", "Today"))
        self.epg_date_label.setStyleSheet(AppStyles.player_date_label_style())
        self.epg_date_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        date_layout.addWidget(self.epg_date_label, 1)

        self.epg_next_day = QPushButton()
        self.epg_next_day.setIcon(QIcon(AppStyles.get_icon('chevron_right', date_icon_color, 12)))
        self.epg_next_day.setIconSize(QSize(12, 12))
        self.epg_next_day.setFixedSize(24, 24)
        self.epg_next_day.setCursor(Qt.CursorShape.PointingHandCursor)
        self.epg_next_day.setStyleSheet(AppStyles.player_date_button_style())
        self.epg_next_day.clicked.connect(self.epg_ctrl.on_next_day)
        self.epg_next_day.setToolTip(tr("tooltip_next_day", "后一天"))
        date_layout.addWidget(self.epg_next_day)

        self.epg_layout.addLayout(date_layout)

        # EPG内容
        self.epg_content = QListWidget()
        self.epg_content.setStyleSheet(AppStyles.player_list_style())
        self.epg_content.setSpacing(8)
        self.epg_content.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.epg_content.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        from controllers.epg_controller import EPGItemDelegate
        self.epg_content.setItemDelegate(EPGItemDelegate(self.epg_content))
        self.epg_content.addItem(self.language_manager.tr("loading", "Loading..."))
        self.epg_content.itemClicked.connect(self.on_epg_item_clicked)
        self.epg_layout.addWidget(self.epg_content, 1)

        self.epg_empty_label = QLabel(tr("no_epg_data", "No program information"), self.epg_content)
        self.epg_empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.epg_empty_label.setStyleSheet(AppStyles.player_empty_label_style())
        self.epg_empty_label.hide()

        # 用 FloatingDockWidget 包装（圆角半透明 + Qt管理）
        from PyQt6.QtWidgets import QDockWidget
        from ui.floating_dialog import FloatingDockWidget
        self.epg_dock = FloatingDockWidget(tr("epg_title", "Program Guide"), self)
        self.epg_dock.setWidget(epg_container)
        self.epg_dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetClosable)
        self.epg_dock.setObjectName("epg_dock")
        if hasattr(self, 'epg_panel'):
            self.epg_panel = None
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
        playlist_container.setMinimumWidth(200)
        self.playlist_layout = QVBoxLayout(playlist_container)
        self.playlist_layout.setContentsMargins(0, 0, 0, 0)

        self.playlist_title = QLabel(tr('playlist_title', 'Playlist'))
        self.playlist_title.setStyleSheet(AppStyles.player_playlist_title_style())
        self.playlist_layout.addWidget(self.playlist_title)

        self.playlist_tab = QTabWidget()
        self.playlist_tab.setStyleSheet(AppStyles.player_tab_style())

        sub_tab = QWidget()
        sub_layout = QVBoxLayout(sub_tab)
        sub_layout.setContentsMargins(0, 0, 0, 0)
        sub_layout.setSpacing(0)

        self.sub_group_combo = QComboBox()
        self.sub_group_combo.addItems(app_state._channel_groups)
        self.sub_group_combo.setStyleSheet(AppStyles.player_group_combo_style())
        self.sub_group_combo.setToolTip(tr("channel_group", "频道分组"))
        self.sub_group_combo.currentTextChanged.connect(self.on_sub_group_changed)
        sub_layout.addWidget(self.sub_group_combo)

        sub_search_row = QHBoxLayout()
        sub_search_row.setContentsMargins(0, 0, 0, 0)
        sub_search_row.setSpacing(4)

        self.sub_search_input = QtWidgets.QLineEdit()
        self.sub_search_input.setPlaceholderText(tr("search_channel", "搜索频道..."))
        self.sub_search_input.setClearButtonEnabled(True)
        self.sub_search_input.setStyleSheet(AppStyles.player_search_input_style())
        self.sub_search_input.setToolTip(tr("search_channel", "搜索频道"))
        self.sub_search_input.textChanged.connect(self._on_sub_search_changed)
        sub_search_row.addWidget(self.sub_search_input, 1)

        view_icon_color = AppStyles._get_colors().get('player_panel_text', AppStyles._safe_fallback('player_panel_text'))
        self.sub_view_list_btn = QToolButton()
        self.sub_view_list_btn.setIcon(QIcon(AppStyles.get_icon('list_view', view_icon_color)))
        self.sub_view_list_btn.setIconSize(QSize(14, 14))
        self.sub_view_list_btn.setFixedSize(24, 20)
        self.sub_view_list_btn.setStyleSheet(AppStyles.player_button_style())
        self.sub_view_list_btn.setCheckable(True)
        self.sub_view_list_btn.setChecked(True)
        self.sub_view_list_btn.setToolTip(tr("list_view", "列表视图"))
        self.sub_view_list_btn.clicked.connect(lambda: self._set_channel_view_mode('list', 'sub'))
        sub_search_row.addWidget(self.sub_view_list_btn)
        self.sub_view_grid_btn = QToolButton()
        self.sub_view_grid_btn.setIcon(QIcon(AppStyles.get_icon('grid_view', view_icon_color)))
        self.sub_view_grid_btn.setIconSize(QSize(14, 14))
        self.sub_view_grid_btn.setFixedSize(24, 20)
        self.sub_view_grid_btn.setStyleSheet(AppStyles.player_button_style())
        self.sub_view_grid_btn.setCheckable(True)
        self.sub_view_grid_btn.setToolTip(tr("grid_view", "网格视图"))
        self.sub_view_grid_btn.clicked.connect(lambda: self._set_channel_view_mode('grid', 'sub'))
        sub_search_row.addWidget(self.sub_view_grid_btn)

        sub_layout.addLayout(sub_search_row)

        from ui.multi_screen_widget import DraggableChannelListWidget
        self.sub_channel_list = DraggableChannelListWidget()
        self.sub_channel_list.setStyleSheet(AppStyles.player_list_style())
        self.sub_channel_list.setSpacing(2)
        self.sub_channel_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.sub_channel_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.sub_channel_list.itemClicked.connect(self._on_channel_single_click)
        self.sub_channel_list.itemDoubleClicked.connect(self._on_channel_double_clicked)
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
        self.local_group_combo.setToolTip(tr("channel_group", "频道分组"))
        self.local_group_combo.currentTextChanged.connect(self.on_local_group_changed)
        local_layout.addWidget(self.local_group_combo)

        local_search_row = QHBoxLayout()
        local_search_row.setContentsMargins(0, 0, 0, 0)
        local_search_row.setSpacing(4)

        self.local_search_input = QtWidgets.QLineEdit()
        self.local_search_input.setPlaceholderText(tr("search_channel", "搜索频道..."))
        self.local_search_input.setClearButtonEnabled(True)
        self.local_search_input.setStyleSheet(AppStyles.player_search_input_style())
        self.local_search_input.setToolTip(tr("search_channel", "搜索频道"))
        self.local_search_input.textChanged.connect(self._on_local_search_changed)
        local_search_row.addWidget(self.local_search_input, 1)

        self.local_view_list_btn = QToolButton()
        self.local_view_list_btn.setIcon(QIcon(AppStyles.get_icon('list_view', view_icon_color)))
        self.local_view_list_btn.setIconSize(QSize(14, 14))
        self.local_view_list_btn.setFixedSize(24, 20)
        self.local_view_list_btn.setStyleSheet(AppStyles.player_button_style())
        self.local_view_list_btn.setCheckable(True)
        self.local_view_list_btn.setChecked(True)
        self.local_view_list_btn.setToolTip(tr("list_view", "列表视图"))
        self.local_view_list_btn.clicked.connect(lambda: self._set_channel_view_mode('list', 'local'))
        local_search_row.addWidget(self.local_view_list_btn)
        self.local_view_grid_btn = QToolButton()
        self.local_view_grid_btn.setIcon(QIcon(AppStyles.get_icon('grid_view', view_icon_color)))
        self.local_view_grid_btn.setIconSize(QSize(14, 14))
        self.local_view_grid_btn.setFixedSize(24, 20)
        self.local_view_grid_btn.setStyleSheet(AppStyles.player_button_style())
        self.local_view_grid_btn.setCheckable(True)
        self.local_view_grid_btn.setToolTip(tr("grid_view", "网格视图"))
        self.local_view_grid_btn.clicked.connect(lambda: self._set_channel_view_mode('grid', 'local'))
        local_search_row.addWidget(self.local_view_grid_btn)

        local_layout.addLayout(local_search_row)

        self.local_channel_list = DraggableChannelListWidget()
        self.local_channel_list.setStyleSheet(AppStyles.player_list_style())
        self.local_channel_list.setSpacing(2)
        self.local_channel_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.local_channel_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.local_channel_list.itemClicked.connect(self._on_channel_single_click)
        self.local_channel_list.itemDoubleClicked.connect(self._on_channel_double_clicked)
        local_layout.addWidget(self.local_channel_list, 1)

        self.local_empty_label = QLabel(tr("no_channels", "No channels"))
        self.local_empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.local_empty_label.setStyleSheet(AppStyles.player_empty_label_style())
        local_layout.addWidget(self.local_empty_label)

        self.playlist_tab.addTab(sub_tab, tr("subscription_tab", "Subscription"))
        self.playlist_tab.addTab(local_tab, tr("local_tab", "Local"))
        tab_icon_color = AppStyles._get_colors().get('player_panel_text', AppStyles._safe_fallback('player_panel_text'))
        signal_icon_path = AppStyles.get_icon('signal', tab_icon_color, 14)
        folder_icon_path = AppStyles.get_icon('folder', tab_icon_color, 14)
        if signal_icon_path:
            self.playlist_tab.setTabIcon(0, QIcon(signal_icon_path))
        if folder_icon_path:
            self.playlist_tab.setTabIcon(1, QIcon(folder_icon_path))
        self.playlist_tab.currentChanged.connect(self._on_playlist_tab_changed)
        self.playlist_layout.addWidget(self.playlist_tab)

        self.channel_list = self.sub_channel_list
        self.group_combo = self.sub_group_combo
        self.channel_empty_label = self.sub_empty_label

        self._click_timer = QTimer()
        self._click_timer.setSingleShot(True)
        self._click_timer.timeout.connect(self._deferred_single_click)
        self._pending_click_item = None
        self._pending_click_source = None

        self._sub_channels = []
        self._local_channels = []
        self._local_channels_dirty = False
        self._sub_groups = [tr("all_channels", "All Channels")]
        self._local_groups = [tr("all_channels", "All Channels")]

        from PyQt6.QtWidgets import QDockWidget
        from ui.floating_dialog import FloatingDockWidget
        self.playlist_dock = FloatingDockWidget(tr("channel_list", "Channel List"), self)
        self.playlist_dock.setWidget(playlist_container)
        self.playlist_dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetClosable)
        self.playlist_dock.setObjectName("playlist_dock")
        if hasattr(self, 'playlist_panel'):
            self.playlist_panel = None
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
        floating_container.setMinimumHeight(120)
        floating_container.setMinimumWidth(480)
        floating_container.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.floating_layout = QVBoxLayout(floating_container)
        self.floating_layout.setContentsMargins(12, 8, 12, 8)
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
            self.floating_panel = None
        self.floating_panel = self.floating_dock

        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.floating_dock)
        self.floating_dock.setFloating(True)
        if not show:
            self.floating_dock.hide()

        logger.debug("_create_panel: 完成")
    
    def _set_info_label_icon(self, icon_label: QLabel, icon_name: str):
        """设置信息行前的小图标"""
        color = AppStyles._get_colors().get('player_panel_text', AppStyles._safe_fallback('player_panel_text'))
        icon_path = AppStyles.get_icon(icon_name, color, 14)
        if icon_path:
            from PyQt6.QtGui import QPixmap
            pixmap = QPixmap(icon_path)
            if not pixmap.isNull():
                icon_label.setPixmap(pixmap.scaled(14, 14, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                icon_label.setFixedSize(16, 16)
                icon_label.setAlignment(Qt.AlignmentFlag.AlignVCenter)

    def _create_media_row(self):
        """创建媒体信息行"""
        logger.debug("_create_media_row: 开始")
        tr = self.language_manager.tr
        
        # 第一行：媒体信息（详细版）
        self.media_row = QHBoxLayout()
        self.media_row.setSpacing(6)
        
        self.video_info_icon = QLabel()
        self.video_info_icon.setStyleSheet("background: transparent; border: none;")
        self._set_info_label_icon(self.video_info_icon, 'tv')
        self.media_row.addWidget(self.video_info_icon)
        
        self.video_info = QLabel()
        self.video_info.setStyleSheet(AppStyles.player_media_badge_style())
        self.video_info.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.video_info.setFixedHeight(22)
        self.video_info.setText(tr('not_playing', 'Not playing'))
        self.media_row.addWidget(self.video_info)
        
        self.media_row.addSpacing(6)
        
        self.audio_info_icon = QLabel()
        self.audio_info_icon.setStyleSheet("background: transparent; border: none;")
        self._set_info_label_icon(self.audio_info_icon, 'speaker')
        self.media_row.addWidget(self.audio_info_icon)
        
        self.audio_info = QLabel()
        self.audio_info.setStyleSheet(AppStyles.player_media_badge_style())
        self.audio_info.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.audio_info.setFixedHeight(18)
        self.audio_info.setText("--")
        self.media_row.addWidget(self.audio_info)
        
        self.media_row.addSpacing(6)
        
        self.network_info_icon = QLabel()
        self.network_info_icon.setStyleSheet("background: transparent; border: none;")
        self._set_info_label_icon(self.network_info_icon, 'signal')
        self.media_row.addWidget(self.network_info_icon)
        
        self.network_info = QLabel()
        self.network_info.setStyleSheet(AppStyles.player_media_badge_style())
        self.network_info.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.network_info.setFixedHeight(18)
        self.network_info.setText("--")
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
        self.current_program.setObjectName("current_program")
        self.current_program.setStyleSheet(AppStyles.player_program_style())
        self.current_program.setAutoFillBackground(False)
        self.current_program.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.current_program.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        row1.addWidget(self.current_program, 1)
        self.time_label = QLabel("--:-- - --:--")
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

        # 第二行：节目描述（自动换行，最多3行，紧贴标题行）
        self.program_desc = QLabel(tr("open_playlist_or_import", "Open a playlist file or import channels to start watching"))
        self.program_desc.setObjectName("program_desc")
        self.program_desc.setStyleSheet(AppStyles.player_program_desc_style())
        self.program_desc.setAutoFillBackground(False)
        self.program_desc.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.program_desc.setWordWrap(True)
        self.program_desc.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.program_desc.setFixedHeight(48)
        self.program_desc.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        text_layout.addWidget(self.program_desc, 0, Qt.AlignmentFlag.AlignTop)

        info_layout.addLayout(text_layout)

        # 用一个容器widget包装info_layout，Fixed策略防止被拉伸
        info_widget = QWidget()
        info_widget.setLayout(info_layout)
        info_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        self.floating_layout.addWidget(info_widget)
        
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
        tr = self.language_manager.tr
        
        # 第三行：播放控制 + 节目进度条
        self.control_row = QHBoxLayout()
        self.control_row.setSpacing(8)
        
        # 左侧：播放按钮
        btn_color = AppStyles._get_colors().get('player_panel_text', AppStyles._safe_fallback('player_panel_text'))
        btn_icon_size = QSize(20, 20)
        self.play_button = QToolButton()
        self.play_button.setIcon(QIcon(AppStyles.get_icon('play', btn_color)))
        self.play_button.setIconSize(btn_icon_size)
        self.play_button.setFixedSize(36, 32)
        self.play_button.setStyleSheet(AppStyles.player_button_style())
        self.play_button.clicked.connect(self.toggle_play)
        self.play_button.setToolTip(tr("panel_play", "播放/暂停"))
        self.control_row.addWidget(self.play_button)

        # 停止按钮
        self.stop_button = QToolButton()
        self.stop_button.setIcon(QIcon(AppStyles.get_icon('stop', btn_color)))
        self.stop_button.setIconSize(btn_icon_size)
        self.stop_button.setFixedSize(36, 32)
        self.stop_button.setStyleSheet(AppStyles.player_button_style())
        self.stop_button.clicked.connect(self.stop_playback)
        self.stop_button.setToolTip(tr("panel_stop", "停止"))
        self.control_row.addWidget(self.stop_button)

        # 上一频道按钮
        self.prev_ch_button = QToolButton()
        self.prev_ch_button.setIcon(QIcon(AppStyles.get_icon('prev', btn_color)))
        self.prev_ch_button.setIconSize(btn_icon_size)
        self.prev_ch_button.setFixedSize(36, 32)
        self.prev_ch_button.setStyleSheet(AppStyles.player_button_style())
        self.prev_ch_button.clicked.connect(lambda: self.event_handler._switch_channel(-1))
        self.prev_ch_button.setToolTip(tr("panel_prev_ch", "上一频道"))
        self.control_row.addWidget(self.prev_ch_button)

        # 下一频道按钮
        self.next_ch_button = QToolButton()
        self.next_ch_button.setIcon(QIcon(AppStyles.get_icon('next', btn_color)))
        self.next_ch_button.setIconSize(btn_icon_size)
        self.next_ch_button.setFixedSize(36, 32)
        self.next_ch_button.setStyleSheet(AppStyles.player_button_style())
        self.next_ch_button.clicked.connect(lambda: self.event_handler._switch_channel(1))
        self.next_ch_button.setToolTip(tr("panel_next_ch", "下一频道"))
        self.control_row.addWidget(self.next_ch_button)
        
        # 中间：时间进度条组
        self.progress_group = QHBoxLayout()
        self.progress_group.setSpacing(4)
        
        # 当前节目开始时间
        self.progress_start = QLabel("--:--")
        self.progress_start.setStyleSheet(AppStyles.player_progress_label_style())
        self.progress_group.addWidget(self.progress_start)
        
        # 时间进度条
        self.program_progress = CacheProgressSlider(Qt.Orientation.Horizontal)
        self.program_progress.setRange(0, 3600)
        self.program_progress.setValue(0)
        self.program_progress.setSingleStep(1)
        self.program_progress.setPageStep(30)
        self.program_progress.setStyleSheet(AppStyles.player_slider_style())
        self.program_progress.set_cache_color(AppStyles._get_colors().get('player_cache_bar', 'rgba(76,175,80,0.4)'))
        self.program_progress.setToolTip(tr("panel_progress", "节目进度"))
        self.program_progress.sliderReleased.connect(self.on_progress_slider_released)
        self.program_progress.sliderPressed.connect(self._on_progress_slider_pressed)
        self.program_progress.preview_position_changed.connect(self._on_progress_preview)
        self._progress_total_seconds = 3600
        self.progress_group.addWidget(self.program_progress, 1)
        
        # 当前节目结束时间
        self.progress_end = QLabel("--:--")
        self.progress_end.setStyleSheet(AppStyles.player_progress_label_style())
        self.progress_group.addWidget(self.progress_end)
        
        self.control_row.addLayout(self.progress_group, 1)
        
        # 5. 音量图标
        self.volume_button = QToolButton()
        self.volume_button.setIcon(QIcon(AppStyles.get_icon('volume', btn_color)))
        self.volume_button.setIconSize(QSize(22, 20))
        self.volume_button.setFixedSize(40, 32)
        self.volume_button.setStyleSheet(AppStyles.player_button_style())
        self.volume_button.clicked.connect(self.toggle_mute)
        self.volume_button.setToolTip(tr("panel_volume", "音量"))
        self.control_row.addWidget(self.volume_button)
        
        # 6. 音量调节拖动条
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(80)
        self.volume_slider.setFixedWidth(90)
        self.volume_slider.setStyleSheet(AppStyles.player_volume_slider_style())
        self.volume_slider.setToolTip(tr("panel_volume_slider", "音量调节"))
        self.volume_slider.valueChanged.connect(self.set_volume)
        self.control_row.addWidget(self.volume_slider)
        
        # 7. 退出回看按钮（初始隐藏）
        self.exit_catchup_button = QToolButton()
        self.exit_catchup_button.setIcon(QIcon(AppStyles.get_icon('prev', btn_color)))
        self.exit_catchup_button.setIconSize(btn_icon_size)
        self.exit_catchup_button.setText(tr("exit_catchup", "退出回看"))
        self.exit_catchup_button.setFixedSize(100, 32)
        self.exit_catchup_button.setStyleSheet(AppStyles.player_button_style())
        self.exit_catchup_button.clicked.connect(self.exit_catchup)
        self.exit_catchup_button.setToolTip(tr("panel_exit_catchup", "退出回看"))
        self.exit_catchup_button.hide()
        self.control_row.addWidget(self.exit_catchup_button)

        # 7.5 速度控制按钮
        self.speed_button = QToolButton()
        self.speed_button.setIcon(QIcon(AppStyles.get_icon('speed', btn_color)))
        self.speed_button.setIconSize(btn_icon_size)
        self.speed_button.setText("1.0x")
        self.speed_button.setFixedSize(50, 32)
        self.speed_button.setStyleSheet(AppStyles.player_button_style())
        self.speed_button.clicked.connect(self.media_ctrl.show_speed_menu)
        self.speed_button.setToolTip(tr("panel_speed", "播放速度"))
        self.control_row.addWidget(self.speed_button)

        # 7.6 画面比例按钮
        self.aspect_button = QToolButton()
        self.aspect_button.setIcon(QIcon(AppStyles.get_icon('aspect', btn_color)))
        self.aspect_button.setIconSize(btn_icon_size)
        self.aspect_button.setFixedSize(52, 32)
        self.aspect_button.setStyleSheet(AppStyles.player_button_style())
        self.aspect_button.clicked.connect(self.media_ctrl.show_aspect_menu)
        self.aspect_button.setToolTip(tr("panel_aspect", "画面比例"))
        self.control_row.addWidget(self.aspect_button)

        # 7.7 音轨切换按钮
        self.audio_track_button = QToolButton()
        self.audio_track_button.setIcon(QIcon(AppStyles.get_icon('audio_track', btn_color)))
        self.audio_track_button.setIconSize(btn_icon_size)
        self.audio_track_button.setToolTip(self.language_manager.tr("panel_audio_track", "Audio Track"))
        self.audio_track_button.setFixedSize(40, 32)
        self.audio_track_button.setStyleSheet(AppStyles.player_button_style())
        self.audio_track_button.clicked.connect(self.media_ctrl.show_audio_track_menu)
        self.control_row.addWidget(self.audio_track_button)

        self.sub_track_button = QToolButton()
        self.sub_track_button.setIcon(QIcon(AppStyles.get_icon('subtitle', btn_color)))
        self.sub_track_button.setIconSize(btn_icon_size)
        self.sub_track_button.setToolTip(self.language_manager.tr("panel_subtitle", "Subtitle"))
        self.sub_track_button.setFixedSize(40, 32)
        self.sub_track_button.setStyleSheet(AppStyles.player_button_style())
        self.sub_track_button.clicked.connect(self.media_ctrl.show_sub_track_menu)
        self.control_row.addWidget(self.sub_track_button)
        
        # PiP按钮
        self.pip_button = QToolButton()
        self.pip_button.setIcon(QIcon(AppStyles.get_icon('pip', btn_color)))
        self.pip_button.setIconSize(btn_icon_size)
        self.pip_button.setFixedSize(36, 32)
        self.pip_button.setStyleSheet(AppStyles.player_button_style())
        self.pip_button.clicked.connect(self.pip_ctrl.toggle)
        self.pip_button.setToolTip(tr("panel_pip", "画中画"))
        self.control_row.addWidget(self.pip_button)

        # 8. 全屏图标
        self.fullscreen_button = QToolButton()
        self.fullscreen_button.setIcon(QIcon(AppStyles.get_icon('fullscreen', btn_color)))
        self.fullscreen_button.setIconSize(btn_icon_size)
        self.fullscreen_button.setFixedSize(36, 32)
        self.fullscreen_button.setStyleSheet(AppStyles.player_button_style())
        self.fullscreen_button.clicked.connect(self.toggle_fullscreen)
        self.fullscreen_button.setToolTip(tr("panel_fullscreen", "全屏"))
        self.control_row.addWidget(self.fullscreen_button)
        
        self.floating_layout.addLayout(self.control_row)
        
        logger.debug("_create_control_row: 完成")
    


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
        
        logger.debug("_install_event_filters: 完成")
    
    def _populate_channel_list(self, source='subscription'):
        """填充频道列表（带EPG刷新）"""
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
        self.ui_ctrl.setup_menu_bar(skip_recent_files)

    def update_channel_groups(self):
        """从CHANNELS中提取分组并更新下拉框（委托给SubscriptionController）"""
        self.subscription_ctrl.update_channel_groups()

    def populate_channel_list(self, source='subscription'):
        """填充频道列表（内置防抖）

        Args:
            source: 'subscription' 填充订阅标签, 'local' 填充本地标签,
                    'auto' 自动判断（默认填充当前活跃标签）
        """
        import time
        if source == 'auto':
            if not hasattr(self, 'playlist_tab'):
                source = 'subscription'
            else:
                source = 'subscription' if self.playlist_tab.currentIndex() == 0 else 'local'

        current_time = time.time()
        if not hasattr(self, '_last_populate_times'):
            self._last_populate_times = {}
        last_time = self._last_populate_times.get(source, 0)

        if source == 'subscription':
            new_channels = app_state.channels
            skip_debounce = len(new_channels) != len(getattr(self, '_sub_channels', []))
        else:
            new_channels = None
            skip_debounce = False

        if not skip_debounce and current_time - last_time < 0.5:
            logger.debug(f"populate_channel_list: 跳过重复调用（source={source}，距上次{current_time - last_time:.2f}秒）")
            return
        self._last_populate_times[source] = current_time

        if source == 'subscription':
            self._sub_channels = new_channels
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

    def _on_sub_search_changed(self, text):
        self._apply_channel_search(self.sub_channel_list, self._sub_channels, text)

    def _on_local_search_changed(self, text):
        self._apply_channel_search(self.local_channel_list, self._local_channels, text)

    def _apply_channel_search(self, list_widget, channels, search_text):
        search_text = search_text.strip().lower()
        if not search_text:
            for i in range(list_widget.count()):
                item = list_widget.item(i)
                if item:
                    item.setHidden(False)
            return
        for i in range(list_widget.count()):
            item = list_widget.item(i)
            if not item:
                continue
            idx = item.data(Qt.ItemDataRole.UserRole)
            if idx is None or idx >= len(channels):
                item.setHidden(True)
                continue
            channel = channels[idx]
            name = channel.get('name', '').lower()
            url = channel.get('url', '').lower()
            group = channel.get('group', '').lower()
            match = search_text in name or search_text in url or search_text in group
            item.setHidden(not match)

    def _populate_channel_list_for(self, list_widget, channels, selected_group=''):
        self.channel_ctrl.populate_channel_list_for(list_widget, channels, selected_group)

    
    def _load_visible_icons(self, list_widget, channels):
        self.channel_ctrl.load_visible_icons(list_widget, channels)


    def _process_icon_load_batch(self):
        """每帧处理少量图标加载，避免UI卡顿"""
        if not hasattr(self, '_icon_load_queue') or not self._icon_load_queue:
            if hasattr(self, '_icon_load_timer'):
                self._icon_load_timer.stop()
            return

        batch_size = 3
        for _ in range(batch_size):
            if not self._icon_load_queue:
                if hasattr(self, '_icon_load_set'):
                    self._icon_load_set.clear()
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
            except (ValueError, TypeError, AttributeError):
                pass
        
        try:
            now = datetime.now()
            hour_start = now.replace(minute=0, second=0, microsecond=0)
            target_wallclock = hour_start + timedelta(seconds=slider_seconds)
            offset_from_live = (now - target_wallclock).total_seconds()
            target_pos = buffer_end - offset_from_live
            return target_pos
        except (ValueError, TypeError, AttributeError):
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
        except (ValueError, KeyError, TypeError):
            pass
        return 0
    
    def _check_program_change(self):
        """检测节目是否切换，更新UI信息"""
        is_catchup = self.play_state.is_catchup_or_timeshift
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
                    desc = current_program.get('desc', '') or self.language_manager.tr('no_program_desc', 'No program description')
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
    
    def _on_progress_slider_pressed(self):
        self._stop_auto_hide_timer()

    def _on_progress_preview(self, seconds):
        mode = getattr(self, '_progress_time_mode', None)
        if mode == 'vod':
            self.program_progress.set_preview_text(self._format_seconds_to_time(seconds))
        elif mode == 'epg':
            program_start = getattr(self, '_progress_program_start', None)
            if program_start:
                from datetime import timedelta
                preview_time = program_start + timedelta(seconds=seconds)
                self.program_progress.set_preview_text(preview_time.strftime("%H:%M:%S"))
            else:
                self.program_progress.set_preview_text(self._format_seconds_to_time(seconds))
        elif mode == 'hour':
            from datetime import datetime, timedelta
            now = datetime.now()
            hour_start = now.replace(minute=0, second=0, microsecond=0)
            preview_time = hour_start + timedelta(seconds=seconds)
            self.program_progress.set_preview_text(preview_time.strftime("%H:%M:%S"))
        else:
            is_catchup = self.play_state.is_catchup_or_timeshift
            if is_catchup:
                catchup_program = getattr(self, 'catchup_program', None)
                if catchup_program:
                    start_time = catchup_program.get('start')
                    if start_time:
                        from datetime import timedelta
                        preview_time = start_time + timedelta(seconds=seconds)
                        self.program_progress.set_preview_text(preview_time.strftime("%H:%M:%S"))
                        return
            self.program_progress.set_preview_text(self._format_seconds_to_time(seconds))

    def _format_seconds_to_time(self, seconds):
        seconds = max(0, int(seconds))
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        if h > 0:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"

    def on_progress_slider_released(self):
        if hasattr(self, '_slider_debounce_timer') and self._slider_debounce_timer is not None:
            self._slider_debounce_timer.stop()
        else:
            from PyQt6.QtCore import QTimer
            self._slider_debounce_timer = QTimer()
            self._slider_debounce_timer.setSingleShot(True)
            self._slider_debounce_timer.timeout.connect(self._do_progress_slider_released)
        self._slider_debounce_timer.start(100)

    def _do_progress_slider_released(self):
        is_catchup = self.play_state.is_catchup_or_timeshift
        if getattr(self, '_progress_time_mode', None) == 'vod' and not is_catchup:
            self._seek_vod(self._get_progress_seconds())
        elif is_catchup:
            self._seek_catchup(self._get_progress_seconds())
        else:
            self._seek_live(self._get_progress_seconds())

        if getattr(self, 'is_fullscreen', False):
            self._restart_auto_hide_timer()

    def _seek_vod(self, position):
        if self.player_controller:
            self.player_controller.seek_absolute(float(position))

    def _seek_live(self, position):
        if not self.current_channel or not self.player_controller:
            return

        seek_range = self.player_controller.get_available_seek_range()
        max_back = seek_range.get('max_back', 0)
        cache_duration = seek_range.get('cache_duration', 0)
        buffer_start = seek_range.get('buffer_start', 0)
        buffer_end = seek_range.get('buffer_end', 0)
        time_pos = seek_range.get('time_pos', 0)

        logger.info(f"直播拖动进度条 -> slider={position}s, "
                    f"time_pos={time_pos:.1f}s, buffer={buffer_start:.1f}s~{buffer_end:.1f}s, "
                    f"max_back={max_back}s, mode={getattr(self, '_progress_time_mode', '?')}")

        if max_back == 0 and cache_duration < 5:
            logger.warning(f"直播拖动进度条 -> 无法回退（缓冲区为空，cache={cache_duration:.1f}s）")
            self.status_bar_show_message(self.language_manager.tr("cannot_seek_live", "无法回退：直播流缓冲区不足"))
            return

        target_pos = self._map_slider_to_stream_position(position, seek_range)

        logger.info(f"直播拖动进度条 -> 映射后 target_pos={target_pos:.1f}s, "
                    f"clamp后={max(buffer_start, min(target_pos, buffer_end)):.1f}s")

        if target_pos < buffer_start:
            catchup_source = self.current_channel.get('catchup_source', '') if self.current_channel else ''
            if catchup_source and getattr(self, '_progress_time_mode', None) == 'epg' and self._progress_program_start:
                self._start_live_timeshift_from_progress(position, catchup_source)
                return
            elif catchup_source:
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

    def _seek_catchup(self, position):
        self.catchup_ctrl.seek_catchup(position)


    def on_group_changed(self, group_name):
        """处理分组切换事件（委托给ChannelController）"""
        self.channel_ctrl.on_group_changed(group_name)

    def select_channel(self, item, source_list=None):
        try:
            idx = item.data(Qt.ItemDataRole.UserRole)

            if source_list is not None:
                channel_list = source_list
            else:
                sender = self.sender()
                channel_list = sender if sender else self.sub_channel_list

            if channel_list is self.local_channel_list:
                channels = self._local_channels
            else:
                channels = self._sub_channels

            old_channel = getattr(self, 'current_channel', None)

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

            if old_channel and old_channel is not self.current_channel:
                self._previous_channel = dict(old_channel)

            if self.play_state.is_catchup_or_timeshift:
                self.playback_ctrl._exit_catchup_mode()

            self.update_channel_info_on_selection()
            if not self._is_local_file():
                self.populate_epg_list()
            self.play_channel(self.current_channel)
        except Exception as e:
            logger.error(f"select_channel: 选择频道失败: {e}", exc_info=True)
    
    def _on_channel_single_click(self, item):
        self._pending_click_item = item
        self._pending_click_source = self.sender()
        self._click_timer.start(300)

    def _deferred_single_click(self):
        if self._pending_click_item:
            self.select_channel(self._pending_click_item, source_list=self._pending_click_source)

    def _on_channel_double_clicked(self, item):
        """双击频道：多画面模式填入空画面，普通模式播放"""
        self._click_timer.stop()
        if not item:
            return
        idx = item.data(Qt.ItemDataRole.UserRole)
        sender = self.sender()
        if sender is self.local_channel_list:
            channels = self._local_channels
        else:
            channels = self._sub_channels
        if isinstance(idx, int) and 0 <= idx < len(channels):
            channel = channels[idx]
        else:
            return
        if hasattr(self, 'multi_screen_ctrl') and self.multi_screen_ctrl.is_active:
            self.multi_screen_ctrl.play_in_empty_cell(channel)
        else:
            self.select_channel(item, source_list=sender)

    def _get_display_channel_name(self, channel):
        """获取用于显示的频道名称（委托给通用工具函数）"""
        from utils.general_utils import get_display_channel_name
        return get_display_channel_name(channel, self.language_manager)

    def update_channel_info_on_selection(self):
        self.channel_ctrl.update_channel_info_on_selection()

    
    def toggle_epg(self, checked=None):
        """切换EPG面板显示/隐藏（委托给EPGController）"""
        if self.panel_vis.is_auto_hidden:
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

    def set_color_mode(self, mode: str):
        """设置颜色模式（委托给SettingsFileOperations）"""
        self.settings_ops.set_color_mode(mode)

    def set_visual_style(self, style: str):
        """设置视觉风格（委托给SettingsFileOperations）"""
        self.settings_ops.set_visual_style(style)

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


    def toggle_playlist(self, checked=None):
        """显示/隐藏播放列表面板"""
        if self.panel_vis.is_auto_hidden:
            self._auto_restore_panels()
            return
        if checked is None:
            self.playlist_visible = not self.playlist_panel.isVisible()
        else:
            self.playlist_visible = checked
        self._sync_panel_actions()

    def toggle_floating_panel(self, checked=None):
        """显示/隐藏底部控制面板"""
        if self.panel_vis.is_auto_hidden:
            self._auto_restore_panels()
            return
        if checked is None:
            self.floating_panel_visible = not self.floating_panel.isVisible()
        else:
            self.floating_panel_visible = checked
        self._sync_panel_actions()

    def toggle_hide_floating(self, checked=None):
        if self.panel_vis.manually_hidden:
            is_local = self._is_local_file() if hasattr(self, '_is_local_file') else False
            self.panel_vis.restore_from_manual_hide(is_local_file=is_local)
        else:
            if self.panel_vis.is_auto_hidden:
                self.panel_vis._auto_hide_saved = dict(self.panel_vis._auto_hide_saved or {})
                self.panel_vis.set_auto_hide_visible()
            self.panel_vis.hide_all()
        self._sync_panel_actions()

    def _show_floating_panels_on_enter(self):
        if self.panel_vis.manually_hidden:
            return
        if getattr(self, 'is_fullscreen', False):
            return
        if getattr(self, '_pip_mode', False):
            return
        if not self.panel_vis.is_auto_hidden:
            return

        is_local = self._is_local_file() if hasattr(self, '_is_local_file') else False
        self.panel_vis.restore_auto_hide_state(is_local_file=is_local)
        self._sync_panel_actions()
        self._raise_child_dialogs()

    def _delayed_hide_floating_panels(self):
        if self.panel_vis.manually_hidden:
            return
        if getattr(self, 'is_fullscreen', False):
            return
        if getattr(self, '_pip_mode', False):
            return
        if not self.panel_vis.is_auto_hide_visible:
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

        self.panel_vis.auto_hide_all()
        self._sync_panel_actions()

    def _auto_hide_panels(self):
        if not getattr(self, 'is_fullscreen', False):
            return
        if self.panel_vis.manually_hidden:
            return
        if not self.panel_vis.is_auto_hide_visible:
            return

        self.panel_vis.auto_hide_all()
        self.setCursor(Qt.CursorShape.BlankCursor)
        self._sync_panel_actions()

    def _auto_restore_panels(self):
        if not getattr(self, 'is_fullscreen', False):
            if not self.panel_vis.manually_hidden:
                self._show_floating_panels_on_enter()
            return
        if not self.panel_vis.is_auto_hidden:
            return
        if self.panel_vis.manually_hidden:
            return

        is_local = self._is_local_file() if hasattr(self, '_is_local_file') else False
        self.panel_vis.restore_auto_hide_state(is_local_file=is_local)
        self.unsetCursor()
        self._sync_panel_actions()
        self._restart_auto_hide_timer()
        self._raise_child_dialogs()

    def _restart_auto_hide_timer(self):
        if getattr(self, 'is_fullscreen', False) and not self.panel_vis.manually_hidden:
            if not hasattr(self, '_auto_hide_timer'):
                from PyQt6.QtCore import QTimer
                self._auto_hide_timer = QTimer(self)
                self._auto_hide_timer.setSingleShot(True)
                self._auto_hide_timer.setInterval(5000)
                self._auto_hide_timer.timeout.connect(self._auto_hide_panels)
            if self.panel_vis.is_auto_hide_visible:
                self._auto_hide_timer.start()

    def _stop_auto_hide_timer(self):
        """停止全屏自动隐藏定时器"""
        if hasattr(self, '_auto_hide_timer') and self._auto_hide_timer:
            self._auto_hide_timer.stop()


    def _on_mouse_activity(self):
        if getattr(self, 'is_fullscreen', False) and not self.panel_vis.manually_hidden:
            if self.panel_vis.is_auto_hidden:
                self._auto_restore_panels()
            elif self.panel_vis.is_auto_hide_visible:
                self._restart_auto_hide_timer()


    def _sync_panel_actions(self):
        """同步所有面板相关 QAction 的 checked 状态"""
        for attr, visible in [
            ('_epg_menu_action', self.epg_visible),
            ('_playlist_menu_action', self.playlist_visible),
            ('_floating_menu_action', self.floating_panel_visible),
            ('_osd_menu_action', self._osd_visible),
            ('_fullscreen_menu_action', getattr(self, 'is_fullscreen', False)),
            ('_pip_menu_action', self.pip_ctrl.is_active if hasattr(self, 'pip_ctrl') else False),
        ]:
            action = getattr(self, attr, None)
            if action:
                action.blockSignals(True)
                action.setChecked(visible)
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
        if QThread.currentThread() != self.thread():
            self._pending_play_state = is_playing
            QTimer.singleShot(0, self._do_handle_play_state_change)
        else:
            self._handle_play_state_change(is_playing)

    @pyqtSlot()
    def _do_handle_play_state_change(self):
        is_playing = getattr(self, '_pending_play_state', False)
        self._pending_play_state = None
        self._handle_play_state_change(is_playing)

    def _handle_play_state_change(self, is_playing):
        self.playback_ctrl.handle_play_state_change(is_playing)

    def _seek_live(self, position):
        self.playback_ctrl.seek_live(position)


    def _seek_catchup(self, position):
        self.catchup_ctrl.seek_catchup(position)


    def on_group_changed(self, group_name):
        """处理分组切换事件（委托给ChannelController）"""
        self.channel_ctrl.on_group_changed(group_name)

    def select_channel(self, item, source_list=None):
        try:
            idx = item.data(Qt.ItemDataRole.UserRole)

            if source_list is not None:
                channel_list = source_list
            else:
                sender = self.sender()
                channel_list = sender if sender else self.sub_channel_list

            if channel_list is self.local_channel_list:
                channels = self._local_channels
            else:
                channels = self._sub_channels

            old_channel = getattr(self, 'current_channel', None)

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

            if old_channel and old_channel is not self.current_channel:
                self._previous_channel = dict(old_channel)

            if self.play_state.is_catchup_or_timeshift:
                self.playback_ctrl._exit_catchup_mode()

            self.update_channel_info_on_selection()
            if not self._is_local_file():
                self.populate_epg_list()
            self.play_channel(self.current_channel)
        except Exception as e:
            logger.error(f"select_channel: 选择频道失败: {e}", exc_info=True)
    
    def _on_channel_single_click(self, item):
        self._pending_click_item = item
        self._pending_click_source = self.sender()
        self._click_timer.start(300)

    def _deferred_single_click(self):
        if self._pending_click_item:
            self.select_channel(self._pending_click_item, source_list=self._pending_click_source)

    def _on_channel_double_clicked(self, item):
        """双击频道：多画面模式填入空画面，普通模式播放"""
        self._click_timer.stop()
        if not item:
            return
        idx = item.data(Qt.ItemDataRole.UserRole)
        sender = self.sender()
        if sender is self.local_channel_list:
            channels = self._local_channels
        else:
            channels = self._sub_channels
        if isinstance(idx, int) and 0 <= idx < len(channels):
            channel = channels[idx]
        else:
            return
        if hasattr(self, 'multi_screen_ctrl') and self.multi_screen_ctrl.is_active:
            self.multi_screen_ctrl.play_in_empty_cell(channel)
        else:
            self.select_channel(item, source_list=sender)

    def _get_display_channel_name(self, channel):
        """获取用于显示的频道名称（委托给通用工具函数）"""
        from utils.general_utils import get_display_channel_name
        return get_display_channel_name(channel, self.language_manager)

    
    def toggle_epg(self, checked=None):
        """切换EPG面板显示/隐藏（委托给EPGController）"""
        if self.panel_vis.is_auto_hidden:
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

    def set_color_mode(self, mode: str):
        """设置颜色模式（委托给SettingsFileOperations）"""
        self.settings_ops.set_color_mode(mode)

    def set_visual_style(self, style: str):
        """设置视觉风格（委托给SettingsFileOperations）"""
        self.settings_ops.set_visual_style(style)

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


    def toggle_playlist(self, checked=None):
        """显示/隐藏播放列表面板"""
        if self.panel_vis.is_auto_hidden:
            self._auto_restore_panels()
            return
        if checked is None:
            self.playlist_visible = not self.playlist_panel.isVisible()
        else:
            self.playlist_visible = checked
        self._sync_panel_actions()

    def toggle_floating_panel(self, checked=None):
        """显示/隐藏底部控制面板"""
        if self.panel_vis.is_auto_hidden:
            self._auto_restore_panels()
            return
        if checked is None:
            self.floating_panel_visible = not self.floating_panel.isVisible()
        else:
            self.floating_panel_visible = checked
        self._sync_panel_actions()

    def toggle_hide_floating(self, checked=None):
        if self.panel_vis.manually_hidden:
            is_local = self._is_local_file() if hasattr(self, '_is_local_file') else False
            self.panel_vis.restore_from_manual_hide(is_local_file=is_local)
        else:
            if self.panel_vis.is_auto_hidden:
                self.panel_vis._auto_hide_saved = dict(self.panel_vis._auto_hide_saved or {})
                self.panel_vis.set_auto_hide_visible()
            self.panel_vis.hide_all()
        self._sync_panel_actions()

    def _show_floating_panels_on_enter(self):
        if self.panel_vis.manually_hidden:
            return
        if getattr(self, 'is_fullscreen', False):
            return
        if getattr(self, '_pip_mode', False):
            return
        if not self.panel_vis.is_auto_hidden:
            return

        is_local = self._is_local_file() if hasattr(self, '_is_local_file') else False
        self.panel_vis.restore_auto_hide_state(is_local_file=is_local)
        self._sync_panel_actions()
        self._raise_child_dialogs()

    def _delayed_hide_floating_panels(self):
        if self.panel_vis.manually_hidden:
            return
        if getattr(self, 'is_fullscreen', False):
            return
        if getattr(self, '_pip_mode', False):
            return
        if not self.panel_vis.is_auto_hide_visible:
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

        self.panel_vis.auto_hide_all()
        self._sync_panel_actions()

    def _auto_hide_panels(self):
        if not getattr(self, 'is_fullscreen', False):
            return
        if self.panel_vis.manually_hidden:
            return
        if not self.panel_vis.is_auto_hide_visible:
            return

        self.panel_vis.auto_hide_all()
        self.setCursor(Qt.CursorShape.BlankCursor)
        self._sync_panel_actions()

    def _auto_restore_panels(self):
        if not getattr(self, 'is_fullscreen', False):
            if not self.panel_vis.manually_hidden:
                self._show_floating_panels_on_enter()
            return
        if not self.panel_vis.is_auto_hidden:
            return
        if self.panel_vis.manually_hidden:
            return

        is_local = self._is_local_file() if hasattr(self, '_is_local_file') else False
        self.panel_vis.restore_auto_hide_state(is_local_file=is_local)
        self.unsetCursor()
        self._sync_panel_actions()
        self._restart_auto_hide_timer()
        self._raise_child_dialogs()

    def _restart_auto_hide_timer(self):
        if getattr(self, 'is_fullscreen', False) and not self.panel_vis.manually_hidden:
            if not hasattr(self, '_auto_hide_timer'):
                from PyQt6.QtCore import QTimer
                self._auto_hide_timer = QTimer(self)
                self._auto_hide_timer.setSingleShot(True)
                self._auto_hide_timer.setInterval(5000)
                self._auto_hide_timer.timeout.connect(self._auto_hide_panels)
            if self.panel_vis.is_auto_hide_visible:
                self._auto_hide_timer.start()

    def _stop_auto_hide_timer(self):
        """停止全屏自动隐藏定时器"""
        if hasattr(self, '_auto_hide_timer') and self._auto_hide_timer:
            self._auto_hide_timer.stop()


    def _on_mouse_activity(self):
        if getattr(self, 'is_fullscreen', False) and not self.panel_vis.manually_hidden:
            if self.panel_vis.is_auto_hidden:
                self._auto_restore_panels()
            elif self.panel_vis.is_auto_hide_visible:
                self._restart_auto_hide_timer()


    def _sync_panel_actions(self):
        """同步所有面板相关 QAction 的 checked 状态"""
        for attr, visible in [
            ('_epg_menu_action', self.epg_visible),
            ('_playlist_menu_action', self.playlist_visible),
            ('_floating_menu_action', self.floating_panel_visible),
            ('_osd_menu_action', self._osd_visible),
            ('_fullscreen_menu_action', getattr(self, 'is_fullscreen', False)),
            ('_pip_menu_action', self.pip_ctrl.is_active if hasattr(self, 'pip_ctrl') else False),
        ]:
            action = getattr(self, attr, None)
            if action:
                action.blockSignals(True)
                action.setChecked(visible)
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
            if self.play_state.is_catchup_or_timeshift:
                from core.log_manager import global_logger as logger
                tr = self.language_manager.tr
                channel_name = self.current_channel.get('name', '')
                logger.info(f"时移/回看播放失败，自动退回直播: {channel_name}")
                self.status_bar_show_message(
                    f"{tr('timeshift_failed_back_to_live', '时移播放失败，退回直播')}: {channel_name}"
                )
            self.playback_ctrl.play_channel(self.current_channel)

    def on_live_media_info_updated(self, info: Dict[str, Any]):
        self.ui_ctrl.on_live_media_info_updated(info)
    

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
    
    def update_media_info(self):
        self.ui_ctrl.update_media_info()
    
    def _on_playback_position_updated(self, current_time_ms, total_time_ms, position):
        """接收后台线程获取的播放位置（避免主线程调用MPV API）"""
        prev_total = getattr(self, '_cached_total_time_ms', 0) or 0
        self._cached_current_time_ms = current_time_ms
        self._cached_total_time_ms = total_time_ms
        self._cached_position = position
        if ((not prev_total or prev_total <= 0) and total_time_ms and total_time_ms > 0
                and self._is_local_file()):
            logger.warning(f"[GOT_DURATION] total={total_time_ms:.0f}ms cur={current_time_ms:.0f}ms pos={position:.4f}")
        self.update_floating_panel_info()
    
    def update_floating_panel_info(self):
        self.ui_ctrl.update_floating_panel_info()
        
    
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

    def _raise_overlay_above_video(self):
        if not hasattr(self, '_video_overlay_label') or not self._video_overlay_label:
            return
        self._video_overlay_label.raise_()
        try:
            hwnd = int(self._video_overlay_label.winId())
            import ctypes
            SWP_NOMOVE = 0x0002
            SWP_NOSIZE = 0x0001
            SWP_NOACTIVATE = 0x0010
            SWP_SHOWWINDOW = 0x0040
            ctypes.windll.user32.SetWindowPos(
                hwnd, -1, 0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW
            )
            ctypes.windll.user32.SetWindowPos(
                hwnd, -2, 0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW
            )
        except Exception:
            pass

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
        if self._video_overlay_label.isVisible():
            self._raise_overlay_above_video()

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
        floating_dock = getattr(self, 'floating_dock', None)
        if floating_dock:
            if floating_dock.isVisible():
                control_panel_h = floating_dock.height()
                self._last_control_panel_h = control_panel_h
            else:
                control_panel_h = getattr(self, '_last_control_panel_h', floating_dock.height() or 170)
        else:
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
            self.floating_dock.setMinimumWidth(max(fl_w, 480))
            fl_x = mw_x + (mw_w - self.floating_dock.width()) // 2
            fl_y = mw_y + mw_h - control_panel_h - status_bar_h - gap
            self.floating_dock.move(fl_x, fl_y)

    def toggle_fullscreen(self, checked=None):
        if checked is not None and self.fullscreen_button.isCheckable():
            want_fullscreen = bool(checked)
        else:
            want_fullscreen = not self.is_fullscreen

        if want_fullscreen == self.is_fullscreen:
            logger.debug(f"toggle_fullscreen跳过: checked={checked}, is_fullscreen={self.is_fullscreen}, btn_checkable={self.fullscreen_button.isCheckable()}")
            return

        self.is_fullscreen = want_fullscreen

        if self.is_fullscreen:
            self._before_fullscreen_geo = self.geometry()
            logger.debug(f"进入全屏: 保存geometry={self._before_fullscreen_geo.getRect()}, screen={self.screen().geometry().getRect() if self.screen() else None}")
            self.panel_vis.set_auto_hide_visible()
            self.panel_vis.save_context('fullscreen')
            if hasattr(self, '_title_bar') and self._title_bar:
                self._title_bar.hide()
            if hasattr(self, '_custom_menu_bar') and self._custom_menu_bar:
                self._custom_menu_bar.hide()
            if self.status_bar:
                self.status_bar.hide()
            self.showFullScreen()
            screen = self.screen()
            if screen:
                geo = screen.geometry()
                self.setGeometry(geo)
            logger.debug(f"进入全屏后: geometry={self.geometry().getRect()}, isFullScreen={self.isFullScreen()}")
            self.unsetCursor()
            is_local = self._is_local_file() if hasattr(self, '_is_local_file') else False
            self.panel_vis.set_all_visible(is_local_file=is_local)
            self._sync_panel_actions()
            self._restart_auto_hide_timer()
        else:
            self._stop_auto_hide_timer()
            self.unsetCursor()
            saved = self.panel_vis.restore_context('fullscreen')
            logger.debug(f"退出全屏: showNormal前geometry={self.geometry().getRect()}, isFullScreen={self.isFullScreen()}, saved_geo={getattr(self, '_before_fullscreen_geo', None)}")
            self.showNormal()
            saved_geo = getattr(self, '_before_fullscreen_geo', None)
            if saved_geo:
                self.setGeometry(saved_geo)
            logger.debug(f"退出全屏后: geometry={self.geometry().getRect()}, isFullScreen={self.isFullScreen()}")
            if saved:
                if saved.get('title_bar', True) and hasattr(self, '_title_bar') and self._title_bar:
                    self._title_bar.show()
                if saved.get('menu_bar', True) and hasattr(self, '_custom_menu_bar') and self._custom_menu_bar:
                    self._custom_menu_bar.show()
                if saved.get('status_bar', True) and self.status_bar:
                    self.status_bar.show()
            self.panel_vis.set_auto_hide_visible()
            self._sync_panel_actions()
            self.update_floating_position()
    
    def refresh_ui(self):
        """刷新界面"""
        self.populate_channel_list(source='auto')
        self.populate_epg_list()
    
    def reset_layout(self):
        self.panel_vis.reset()
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

            from ui.theme_manager import get_theme_manager
            try:
                get_theme_manager().register_window(dialog)
            except Exception:
                pass

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
        """重新加载订阅源"""
        if self.subscription_ctrl:
            self.subscription_ctrl.reload_subscription()

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
            self._pending_update_message = None
            logger.info(f"_do_on_playlist_updated_in_main_thread: 开始更新UI, CHANNELS数量={app_state.channel_count}")
            if hasattr(self, 'playlist_tab'):
                self.playlist_tab.setCurrentIndex(0)
            try:
                self.populate_channel_list(source='subscription')
            except Exception as ex:
                logger.error(f"populate_channel_list失败: {ex}")
            try:
                self._populate_epg_list()
            except Exception as ex:
                logger.error(f"_populate_epg_list失败: {ex}")
            if hasattr(self, 'update_floating_position'):
                self.update_floating_position()
            self.status_bar.showMessage(message)
            logger.info("_do_on_playlist_updated_in_main_thread: UI更新完成")
        except Exception as ex:
            logger.error(f"在主线程更新UI失败: {ex}")

    @pyqtSlot()
    @pyqtSlot()
    def _do_show_status_bar_message(self):
        msg = getattr(self, '_pending_status_bar_msg', '')
        self._pending_status_bar_msg = None
        self.status_bar_show_message(msg)

    @pyqtSlot()
    def _do_on_epg_cache(self):
        self.epg_list_updated.emit()
        self.status_bar_show_message(self.language_manager.tr("epg_using_cache", "Using cached EPG data"))

    @pyqtSlot()
    def _do_on_epg_success(self):
        self.epg_list_updated.emit()
        self.status_bar_show_message(self.language_manager.tr("epg_sub_updated", "EPG subscription updated"))

    def update_recent_files_menu(self):
        """更新最近打开文件菜单"""
        
        # 清空当前菜单
        self.recent_menu.clear()
        
        # 加载最近打开的文件列表
        recent_files = self.config.load_recent_files()
        
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
        self.settings_ops.open_recent_file(file_path)

    def _apply_m3u_content(self, content, file_path):
        """将M3U内容应用到频道列表（供open_recent_file复用）"""
        tr = self.language_manager.tr
        try:
            if self.channel_model.load_from_file(content):
                self.channel_model._source_file_path = file_path
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

                app_state.replace_channels(new_channels)
                self._local_channels = list(new_channels)
                self._local_channels_dirty = True

                if app_state.channel_count > 0:
                    self.current_channel = app_state.get_channel_by_index(0)
                    display_name = self._get_display_channel_name(self.current_channel)
                    self.channel_name.setText(display_name)

                if hasattr(self, 'playlist_tab'):
                    self.playlist_tab.setCurrentIndex(1)
                self.populate_channel_list(source='local')
                self.status_bar.showMessage(f"{tr('file_opened', 'File opened')}: {file_path}")
                logger.info(f"成功打开最近文件: {file_path}, 共 {app_state.channel_count} 个频道")
            else:
                self.status_bar.showMessage(tr("file_format_error"))
        except Exception as ex:
            logger.error(f"应用M3U内容失败: {str(ex)}")
            self.status_bar.showMessage(f"{tr('file_open_failed', 'Failed to open file')}: {str(ex)}")
    
    def open_playlist(self):
        """打开播放列表（委托给SettingsFileOperations）"""
        self.settings_ops.open_playlist()

    def _open_stream(self):
        self.settings_ops._open_stream()

    def _open_video_file(self):
        """打开本地视频文件或蓝光原盘目录"""
        from PyQt6.QtWidgets import QFileDialog
        tr = self.language_manager.tr
        file_path, _ = QFileDialog.getOpenFileName(
            self, tr("open_video", "打开视频"),
            "",
            tr("video_files", "视频文件 (*.mp4 *.mkv *.avi *.mov *.flv *.wmv *.ts *.m2ts *.webm);;所有文件 (*)"),
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
            self.config.add_recent_file(file_path)
            self.update_recent_files_menu()
            return
        from PyQt6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self, tr("open_bluray", "打开蓝光原盘"),
            tr("open_bluray_ask", "是否选择蓝光原盘目录？"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            dir_path = QFileDialog.getExistingDirectory(
                self, tr("select_bluray_dir", "选择蓝光原盘目录"), ""
            )
            if dir_path:
                from services.mpv_player_service import MpvPlayerController
                bdmv = MpvPlayerController._detect_bdmv_path(dir_path)
                if bdmv:
                    import os
                    name = os.path.basename(os.path.dirname(bdmv)) or os.path.basename(bdmv)
                    channel = {
                        'name': name,
                        'url': dir_path,
                        'group': tr("bluray", "蓝光原盘"),
                        '_groups': [tr("bluray", "蓝光原盘")],
                    }
                    self._add_to_local_list(channel)
                    self.config.add_recent_file(dir_path)
                    self.update_recent_files_menu()
                else:
                    QMessageBox.warning(
                        self, tr("not_bluray", "非蓝光原盘"),
                        tr("not_bluray_msg", "所选目录不是有效的蓝光原盘结构（未找到BDMV/STREAM目录）"),
                    )

    def _add_to_local_list(self, channel):
        """将频道添加到本地列表并播放"""
        import copy
        self._local_channels.append(copy.deepcopy(channel))
        self._local_channels_dirty = True
        new_idx = len(self._local_channels) - 1
        self.playlist_tab.setCurrentIndex(1)
        self._update_groups_for('local')
        self._populate_channel_list_for(
            self.local_channel_list, self._local_channels,
            self.local_group_combo.currentText()
        )
        for i in range(self.local_channel_list.count()):
            item = self.local_channel_list.item(i)
            if item and item.data(Qt.ItemDataRole.UserRole) == new_idx:
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

    def show_usage_instructions(self):
        """显示使用说明（委托给SettingsFileOperations）"""
        self.settings_ops.show_usage_instructions()

    def _reapply_side_panel_styles(self):
        self.ui_ctrl._reapply_side_panel_styles()

    def _reapply_floating_panel_styles(self):
        self.ui_ctrl._reapply_floating_panel_styles()

    def save_window_layout(self):
        """保存窗口布局（委托给SettingsFileOperations）"""
        self.settings_ops.save_window_layout()

    def showEvent(self, event):
        """窗口显示事件（委托给EventHandler）"""
        if hasattr(self, 'event_handler') and self.event_handler:
            self.event_handler.showEvent(event)
        else:
            super().showEvent(event)
        self._fix_win32_drag_drop()

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
            QTimer.singleShot(0, self._do_check_for_updates_async)
            return
        self._do_check_for_updates_async()

    @pyqtSlot()
    def _do_check_for_updates_async(self):
        self.update_ctrl.check_for_updates()

    def _on_update_found(self, latest_version, current_version):
        self.update_ctrl._on_update_found(latest_version, current_version)

    def _reset_statusbar_style(self):
        """恢复状态栏样式"""
        self.status_bar.setStyleSheet(AppStyles.statusbar_style())
    
    def _on_update_check_completed(self, success, message):
        self.update_ctrl._on_update_check_completed(success, message)

    def _on_logo_cache_loaded(self, url, pixmap):
        self.ui_ctrl._on_logo_cache_loaded(url, pixmap)

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
            match_idx = None
            for ci, ch in enumerate(channels):
                if ch.get('url', '') == url:
                    match_idx = ci
                    break
            if match_idx is None:
                continue
            for i in range(list_widget.count()):
                item = list_widget.item(i)
                if not item:
                    continue
                if item.data(Qt.ItemDataRole.UserRole) == match_idx:
                    px = QPixmap(thumb_path)
                    if not px.isNull():
                        scaled = px.scaled(210, 118, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                        item.setIcon(QIcon(scaled))
                    break

    def _cancel_source_timeout(self):
        if hasattr(self, '_source_timeout_timer') and self._source_timeout_timer:
            self._source_timeout_timer.stop()

    def _on_source_timeout(self, channel):
        if not self.player_controller or not self.player_controller.is_playing:
            return
        if self.play_state.is_catchup_or_timeshift:
            return
        logger.debug(f"源超时（无备用源可切换）: {channel.get('name', '')}")

    def _load_last_channel(self):
        try:
            last = self.config.load_last_channel()
            if last.get('name') and last.get('index', -1) >= 0:
                self._pending_last_channel = last
        except Exception as e:
            logger.debug(f"加载最后频道失败: {e}")

    def select_channel_by_index(self, idx):
        if not hasattr(self, 'channel_list') or idx < 0:
            return
        for i in range(self.channel_list.count()):
            item = self.channel_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == idx:
                self.channel_list.setCurrentItem(item)
                self.select_channel(item, source_list=self.channel_list)
                return

    def switch_to_previous_channel(self):
        """Backspace 快速回切到上一个频道"""
        if not hasattr(self, '_previous_channel') or not self._previous_channel:
            return
        prev = self._previous_channel
        self._previous_channel = None
        if hasattr(self, 'channel_list'):
            sender = self.sender()
            if sender is getattr(self, 'local_channel_list', None):
                channels = self._local_channels
            else:
                channels = self._sub_channels
            for i in range(self.channel_list.count()):
                item = self.channel_list.item(i)
                idx = item.data(Qt.ItemDataRole.UserRole)
                if isinstance(idx, int) and 0 <= idx < len(channels):
                    ch = channels[idx]
                    if ch.get('url') == prev.get('url'):
                        self.channel_list.setCurrentItem(item)
                        self.select_channel(item, source_list=self.channel_list)
                        return

    def _start_live_timeshift_from_progress(self, slider_seconds, catchup_source):
        self.catchup_ctrl.start_live_timeshift_from_progress(slider_seconds, catchup_source)


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
            list_widget.setGridSize(QSize(230, 160))
            list_widget.setIconSize(QSize(210, 110))
            list_widget.setSpacing(4)
            list_widget.setWrapping(True)
            list_widget.setResizeMode(QListWidget.ResizeMode.Adjust)
            list_widget.setWordWrap(True)
            list_widget.verticalScrollBar().setSingleStep(30)

        source = 'subscription' if tab == 'sub' else 'local'
        self.populate_channel_list(source)

        if mode == 'grid':
            QTimer.singleShot(200, lambda: self._capture_visible_thumbnails(tab))

if __name__ == "__main__":
    app = QApplication(sys.argv)

    splash = None
    try:
        from utils.general_utils import get_icon_path
        from PyQt6.QtGui import QPixmap
        from PyQt6.QtWidgets import QSplashScreen
        ico_path = get_icon_path()
        if os.path.exists(ico_path):
            from PyQt6.QtGui import QIcon
            splash_pixmap = QIcon(ico_path).pixmap(128, 128)
        else:
            splash_pixmap = QPixmap(128, 128)
            splash_pixmap.fill(Qt.GlobalColor.transparent)
        splash = QSplashScreen(splash_pixmap, Qt.WindowType.WindowStaysOnTopHint)
        splash.showMessage("Loading...", Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter, QColor(200, 200, 200))
        try:
            from core.config_manager import ConfigManager
            cfg = ConfigManager()
            wx = int(cfg.get_value('UI', 'window_x') or 100)
            wy = int(cfg.get_value('UI', 'window_y') or 100)
            ww = int(cfg.get_value('UI', 'window_width') or 1280)
            wh = int(cfg.get_value('UI', 'window_height') or 780)
            sp = splash.size()
            splash.move(wx + (ww - sp.width()) // 2, wy + (wh - sp.height()) // 2)
        except Exception:
            pass
        splash.show()
        app.processEvents()
    except Exception:
        pass

    player = IPTVPlayer()

    if splash:
        splash.finish(player)

    # 处理命令行参数（右键"打开方式"传入的文件路径）
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        if os.path.isfile(file_path):
            if file_path.lower().endswith(('.m3u', '.m3u8', '.txt')):
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(800, lambda fp=file_path: player.settings_ops.open_specific_file(fp))
            elif file_path.lower().endswith(('.mp4', '.mkv', '.avi', '.mov',
                                             '.flv', '.wmv', '.ts', '.webm')):
                from PyQt6.QtCore import QTimer
                def _open_video_from_cmdline(fp=file_path):
                    name = os.path.splitext(os.path.basename(fp))[0]
                    channel = {
                        'name': name,
                        'url': fp,
                        'group': player.language_manager.tr("local_video", "本地视频"),
                        '_groups': [player.language_manager.tr("local_video", "本地视频")],
                    }
                    player._add_to_local_list(channel)
                    player.config.add_recent_file(fp)
                    player.update_recent_files_menu()
                QTimer.singleShot(800, _open_video_from_cmdline)

    sys.exit(app.exec())
