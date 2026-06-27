import sys
import os

if sys.platform == 'darwin' and getattr(sys, 'frozen', False):
    try:
        import certifi
        os.environ['SSL_CERT_FILE'] = certifi.where()
        os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()
    except ImportError:
        _cert_path = os.path.join(os.path.dirname(sys.executable), 'resources', 'cert.pem')
        if os.path.exists(_cert_path):
            os.environ['SSL_CERT_FILE'] = _cert_path
            os.environ['REQUESTS_CA_BUNDLE'] = _cert_path

if sys.platform.startswith('linux') and not getattr(sys, 'platform', '') == 'android':
    # 完整的Wayland检测：与platform_utils.is_wayland()保持一致
    # 必须在QApplication创建前设置QT_QPA_PLATFORM=xcb，使Qt使用XWayland，
    # 这样video_widget.winId()返回X11窗口ID，mpv的wid嵌入才能正常工作
    session_type = os.environ.get('XDG_SESSION_TYPE', '').lower()
    wayland_display = os.environ.get('WAYLAND_DISPLAY', '')
    is_wayland_env = (session_type == 'wayland') or (bool(wayland_display) and session_type != 'x11')
    if is_wayland_env and not os.environ.get('QT_QPA_PLATFORM'):
        os.environ['QT_QPA_PLATFORM'] = 'xcb'

from datetime import date, datetime
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.play_state import PlayStateManager
from core.panel_visibility import PanelVisibilityManager
from controllers.main_window_protocol import CatchupProgram
from controllers.progress_controller import ProgressController
from models.channel_model import ChannelListModel
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel,
    QStatusBar, QSizePolicy, QDialog,
    QFrame,
)
from PySide6 import QtWidgets
from PySide6.QtCore import Qt, QSize, QTimer, Signal, QRectF
from PySide6 import QtCore
from PySide6.QtGui import QIcon, QFont, QFontMetrics, QColor, QPainter, QBrush, QPen, QLinearGradient, QPainterPath, QPixmap

from PySide6.QtGui import QShortcut

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
    CatchupController,
    PipController,
    MediaController,
    UpdateController,
    FavoritesController,
    EpgReminderController
)

from utils.general_utils import calculate_adaptive_delay
from mixins.server_mixin import ServerMixin
from mixins.tray_mixin import TrayMixin
from mixins.update_mixin import UpdateMixin
from mixins.thumbnail_mixin import ThumbnailMixin
from mixins.file_ops_mixin import FileOpsMixin
from mixins.panel_mixin import PanelMixin
from mixins.progress_mixin import ProgressMixin
from mixins.playback_mixin import PlaybackMixin
from mixins.epg_mixin import EpgMixin
from mixins.channel_mixin import ChannelMixin
from mixins.settings_mixin import SettingsMixin
from mixins.window_mixin import WindowMixin
from mixins.control_panel_mixin import ControlPanelMixin
from mixins.playlist_panel_mixin import PlaylistPanelMixin
from mixins.event_mixin import EventMixin


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
            'catchup': (c['accent'], c['accent_pressed'], 'catchup', c['window']),
            'timeshift': (c['warning'], c['accent_pressed'], 'timeshift', c['window']),
        }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mode = self.MODE_CATCHUP
        self._label_text = ''
        self._icon_pixmap = None
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NativeWindow)
        self.setAttribute(Qt.WidgetAttribute.WA_DontCreateNativeAncestors)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._font = QFont()
        self._font.setPixelSize(13)
        self._font.setBold(True)
        self._update_icon()
        self._update_size()

    def set_mode(self, mode: str, label_text: str):
        self._mode = mode
        self._label_text = label_text
        self._update_icon()
        self._update_size()
        self.update()

    def _update_icon(self):
        from ui.styles import AppStyles
        c = AppStyles._get_colors()
        icon_name = 'play' if self._mode == self.MODE_CATCHUP else 'backward'
        icon_color = c['window']
        icon_path = AppStyles.get_icon(icon_name, icon_color, 14)
        if icon_path:
            from PySide6.QtGui import QPixmap
            px = QPixmap(icon_path)
            if not px.isNull():
                self._icon_pixmap = px.scaled(14, 14, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                return
        self._icon_pixmap = None

    def _update_size(self):
        self._font.setPixelSize(13)
        fm2 = QFontMetrics(self._font)
        text_w = fm2.horizontalAdvance(self._label_text)
        icon_w = 18 if self._icon_pixmap else 0
        spacing = 4 if self._icon_pixmap else 0
        w = icon_w + spacing + text_w + 20
        h = max(fm2.height(), 14) + 12
        self.setFixedSize(w, h)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        cfg = self._get_mode_configs().get(self._mode, self._get_mode_configs()[self.MODE_CATCHUP])
        color1, color2, _icon_key, text_color = cfg

        r = self.rect()
        radius = r.height() / 2

        path = QPainterPath()
        path.addRoundedRect(0, 0, r.width(), r.height(), radius, radius)

        grad = QLinearGradient(0, 0, r.width(), 0)
        from ui.styles import color_to_qcolor
        grad.setColorAt(0, color_to_qcolor(color1))
        grad.setColorAt(1, color_to_qcolor(color2))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(grad))
        painter.drawPath(path)

        painter.setPen(QPen(QColor(255, 255, 255, 40), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

        painter.setFont(self._font)
        painter.setPen(color_to_qcolor(text_color))

        icon_w = 14 if self._icon_pixmap else 0
        spacing = 4 if self._icon_pixmap else 0
        total_text_w = QFontMetrics(self._font).horizontalAdvance(self._label_text)
        total_content_w = icon_w + spacing + total_text_w
        start_x = (r.width() - total_content_w) / 2

        if self._icon_pixmap:
            icon_y = (r.height() - 14) / 2
            painter.drawPixmap(int(start_x), int(icon_y), self._icon_pixmap)

        text_x = start_x + icon_w + spacing
        text_rect = QRectF(text_x, 0, r.width() - text_x, r.height())
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self._label_text)

        painter.end()


# 导入播放器服务
from services.mpv_player_service import MpvPlayerController


class IPTVPlayer(ServerMixin, TrayMixin, UpdateMixin, ThumbnailMixin, FileOpsMixin, PanelMixin, ProgressMixin, PlaybackMixin, EpgMixin, ChannelMixin, SettingsMixin, WindowMixin, ControlPanelMixin, PlaylistPanelMixin, EventMixin, QMainWindow):
    epg_status_signal = Signal(str)
    channel_list_updated = Signal()
    epg_list_updated = Signal()
    status_message = Signal(str)

    AUTO_HIDE_INTERVAL_MS = 5000
    RECONNECT_DELAY_MS = 2000
    SLIDER_DEBOUNCE_MS = 100
    CHANNEL_CLICK_DELAY_MS = 300
    PROGRAM_DESC_HEIGHT = 54
    CHANNEL_LOGO_WIDTH = 100
    CHANNEL_LOGO_HEIGHT = 36
    CTRL_BUTTON_WIDTH = 36
    CTRL_BUTTON_HEIGHT = 32

    player_controller = None
    config = None
    config_manager = None
    language_manager = None
    channel_model = None
    channels: Optional[List[Dict[str, Any]]] = None
    current_channel: Optional[Dict[str, Any]] = None
    original_channel: Optional[Dict[str, Any]] = None
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
    update_ctrl = None
    multi_screen_ctrl = None
    favorites_ctrl = None
    epg_reminder_ctrl = None
    progress_ctrl = None
    play_state = None
    panel_vis = None

    video_frame = None
    video_widget = None
    video_placeholder = None
    central_widget = None

    status_bar = None
    epg_panel = None
    playlist_panel = None
    floating_panel = None
    top_layout = None
    main_layout = None
    content_layout = None

    # UI 控件 - 信息区
    channel_name = None
    channel_logo = None
    channel_list = None
    group_combo = None
    video_info = None
    audio_info = None
    network_info = None
    buffer_info = None
    current_program = None
    program_desc = None
    time_label = None
    remain_label = None
    catchup_indicator = None

    # UI 控件 - 进度条区
    program_progress = None
    progress_start = None
    progress_end = None

    # UI 控件 - 控制按钮
    play_button = None
    volume_slider = None
    volume_button = None
    speed_button = None
    exit_catchup_button = None
    audio_track_button = None
    sub_track_button = None
    aspect_button = None
    pip_button = None
    fullscreen_button = None
    stop_button = None
    prev_ch_button = None
    next_ch_button = None

    # UI 控件 - EPG 面板
    epg_content = None
    epg_empty_label = None
    epg_date_label = None
    epg_title = None
    epg_prev_day = None
    epg_next_day = None

    # UI 控件 - 播放列表面板
    playlist_title = None
    sub_group_combo = None
    local_group_combo = None
    sub_channel_list = None
    local_channel_list = None
    fav_channel_list = None
    fav_empty_label = None
    history_channel_list = None
    history_empty_label = None

    # UI 控件 - 视频覆盖层
    _video_overlay_label = None

    # UI 控件 - 菜单/快捷键/动作
    recent_menu = None
    _global_search_shortcut = None
    _hide_floating_action = None
    _server_action = None
    _osd_menu_action = None
    _pip_menu_action = None
    _epg_menu_action = None
    _playlist_menu_action = None
    _floating_menu_action = None
    _fullscreen_menu_action = None

    # 标题栏
    _title_bar = None
    _title_label = None
    _title_icon_label = None
    _stay_on_top_btn = None
    _minimize_btn = None
    _maximize_btn = None
    _close_btn = None
    _custom_menu_bar = None
    _main_container = None

    # 定时器与 Dock
    update_timer = None

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

    # 频道数据
    _local_channels: Optional[List[Dict[str, Any]]] = None
    _sub_channels: Optional[List[Dict[str, Any]]] = None
    _local_channels_dirty = False

    # 进度/时移状态
    _progress_total_seconds: float = 3600
    _progress_time_mode: str = 'hour'
    _progress_program_start: Optional[datetime] = None
    _progress_program_end: Optional[datetime] = None
    _initial_position_fixed: bool = False
    _floating_hidden: bool = False
    _osd_visible: bool = False
    _network_base_info: str = ''
    last_catchup_state: bool = False
    _last_epg_refresh: float = 0
    _pending_catchup_progress: float = 0
    _target_catchup_progress: float = 0
    _catchup_start_time: float = 0
    _catchup_start_progress: float = 0
    _timeshift_start_time = None
    _epg_hidden_by_local_file: bool = False

    # 图标加载队列
    _icon_load_set = None
    _icon_load_queue = None
    _icon_load_timer = None

    # 媒体信息缓存
    _last_media_info: Optional[Dict[str, Any]] = None
    _last_info_key: Optional[str] = None

    # 服务/对话框引用
    _thumbnail_service = None
    _scan_dialog = None
    scan_window = None

    PLAYLIST_EXTENSIONS = ('.m3u', '.m3u8', '.txt')
    VIDEO_EXTENSIONS = ('.mp4', '.mkv', '.avi', '.mov', '.flv', '.wmv', '.ts', '.webm')
    AUDIO_EXTENSIONS = ('.mp3', '.flac', '.wav', '.aac', '.ogg', '.opus', '.wma', '.m4a', '.ape', '.alac', '.wv', '.tta', '.dts', '.ac3', '.mid', '.midi')
    ALL_DROP_EXTENSIONS = PLAYLIST_EXTENSIONS + VIDEO_EXTENSIONS + AUDIO_EXTENSIONS

    is_fullscreen = False
    _live_timeshift_seconds = 0
    catchup_program: Optional[CatchupProgram] = None
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
            from PySide6.QtGui import QIcon
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

        self.status_bar = None

        from datetime import datetime
        self.current_epg_date = datetime.now().date()
        self._last_media_info = {}
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
        self.favorites_ctrl = FavoritesController(self)
        self.epg_reminder_ctrl = EpgReminderController(self)

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


    def _update_splash(self, message):
        try:
            from PySide6.QtWidgets import QSplashScreen
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
        from services.mpv_validator_service import MpvStreamValidator
        register_cleanup(FfprobeStreamValidator.terminate_all, "ffprobe_validator_terminate_all")
        register_cleanup(MpvStreamValidator.terminate_all, "mpv_validator_terminate_all")

        self._theme_manager.register_window(self)

        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        self._space_shortcut = QShortcut(' ', app)  # type: ignore[arg-type]
        self._space_shortcut.activated.connect(self.toggle_play)
        self._space_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)

        # 标记UI初始化完成
        self._ui_initialized = True

        # 12. 窗口首次绘制后：定位悬浮窗并显示面板（一次延迟即可）
        QTimer.singleShot(150, self._deferred_initial_position)

        # 13. 延迟加载数据，确保不阻塞首帧渲染
        def load_data_with_delay():
            self.start_subscription_timers()
            self._populate_channel_list(source='subscription')

            self._check_for_updates_async()
            self._auto_start_server()

        adaptive_delay = calculate_adaptive_delay(300, 150, 600)
        logger.debug(f"使用自适应延迟: {adaptive_delay}ms")
        QTimer.singleShot(adaptive_delay, load_data_with_delay)

        logger.debug("_initialize_in_order: 完成")


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
        
        logger.debug("_create_menu_bar: 完成")
    
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
            from PySide6.QtWidgets import QApplication
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
        if sys.platform == 'darwin':
            # macOS上mpv v0.41+不支持wid嵌入，使用vo=libmpv + render API渲染
            from services.mpv_gl_widget import MpvGLWidget
            self.video_widget = MpvGLWidget(self.video_frame)
            self.video_widget.setStyleSheet(AppStyles.player_background_style())
        else:
            self.video_widget = QWidget(self.video_frame)
            self.video_widget.setStyleSheet(AppStyles.player_background_style())
            needs_native_window = (
                (sys.platform.startswith('linux') and not getattr(sys, 'platform', '') == 'android')
            )
            if needs_native_window:
                self.video_widget.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)
                self.video_widget.setAttribute(Qt.WidgetAttribute.WA_DontCreateNativeAncestors, True)
        self.video_widget.hide()

        self._video_overlay_label = VideoOverlayBadge(self.video_frame)
        self._video_overlay_label.hide()

        from services.audio_visual_service import AudioVisualWidget
        self._audio_visual_widget = AudioVisualWidget(self.video_frame, player_controller=None)
        self._audio_visual_widget.hide()

        
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
        if hasattr(self, '_audio_visual_widget') and self._audio_visual_widget:
            self.player_controller.audio_visual._widget = self._audio_visual_widget
        if hasattr(self, '_audio_visual_widget') and self._audio_visual_widget:
            self._audio_visual_widget._pc = self.player_controller
        self.player_controller.play_state_changed.connect(self.playback_ctrl.handle_play_state_change)
        self.player_controller.live_media_info_updated.connect(self.on_live_media_info_updated)
        self.player_controller.play_error.connect(self.on_play_error)
        self.player_controller.reconnect_requested.connect(self._on_reconnect_requested)
        self.player_controller.timeshift_continue_requested.connect(self._on_timeshift_continue)
        self.player_controller.thumbnail_captured.connect(self._on_player_thumbnail_captured)
        self.player_controller.file_loaded.connect(self.media_ctrl.apply_video_eq_on_load)
        self.player_controller.file_loaded.connect(self.media_ctrl.apply_audio_eq_on_load)

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

        self.favorites_ctrl.init_service(self.config)
        self.epg_reminder_ctrl.init_service(self.config)
        self._setup_system_tray()

        logger.debug("_init_player: 完成")
    

    def _create_timer(self):
        """创建定时器"""
        logger.debug("_create_timer: 开始")
        
        # 创建定时器，定期更新悬浮窗信息
        from PySide6.QtCore import QTimer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_floating_panel_info)
        self.player_controller.playback_position_updated.connect(self._on_playback_position_updated)
        
        logger.debug("_create_timer: 完成")


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
        from PySide6.QtWidgets import QApplication
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
                if hasattr(self, '_audio_visual_widget') and self._audio_visual_widget and self._audio_visual_widget.isVisible():
                    self._audio_visual_widget.setGeometry(0, 0, w, h)
                if hasattr(self, '_lyrics_widget') and self._lyrics_widget and self._lyrics_widget.isVisible():
                    self._lyrics_widget.setGeometry(0, 0, w, h)


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

if __name__ == "__main__":

    def _suppress_qfont_pointsize_warning(msg_type, context, msg):
        if msg_type == msg_type.Warning and 'setPointSize' in msg and 'Point size <= 0' in msg:
            return
        if msg_type == msg_type.Warning:
            sys.stderr.write(f"Qt Warning: {msg}\n")
        elif msg_type == msg_type.Critical:
            sys.stderr.write(f"Qt Critical: {msg}\n")

    from PySide6.QtCore import qInstallMessageHandler
    qInstallMessageHandler(_suppress_qfont_pointsize_warning)

    app = QApplication(sys.argv)

    splash = None
    try:
        from utils.general_utils import get_icon_path
        from PySide6.QtGui import QPixmap
        from PySide6.QtWidgets import QSplashScreen
        ico_path = get_icon_path()
        if os.path.exists(ico_path):
            from PySide6.QtGui import QIcon
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
            from utils.platform_utils import wayland_move
            wayland_move(splash, wx + (ww - sp.width()) // 2, wy + (wh - sp.height()) // 2)
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
                from PySide6.QtCore import QTimer
                QTimer.singleShot(800, lambda fp=file_path: player.settings_ops.open_specific_file(fp))
            elif file_path.lower().endswith(('.mp4', '.mkv', '.avi', '.mov',
                                             '.flv', '.wmv', '.ts', '.webm',
                                             '.mp3', '.flac', '.wav', '.aac', '.ogg', '.opus',
                                             '.wma', '.m4a', '.ape', '.alac', '.wv', '.tta',
                                             '.dts', '.ac3', '.mid', '.midi')):
                from PySide6.QtCore import QTimer
                def _open_video_from_cmdline(fp=file_path):
                    player._add_local_video_and_track(fp)
                QTimer.singleShot(800, _open_video_from_cmdline)

    sys.exit(app.exec())
