import sys
import os

import re
from datetime import datetime, timedelta
from models.channel_mappings import extract_channel_name_from_url
from models.channel_model import ChannelListModel
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QListWidget, QListWidgetItem, QStackedWidget,
    QMenuBar, QMenu, QFileDialog, QDialog, QTextEdit, QStatusBar,
    QFrame, QToolButton, QSlider, QGridLayout, QComboBox, QLabel as QtWidgets_QLabel
)
from PyQt6 import QtWidgets
from PyQt6.QtCore import Qt, QSize, QTimer, QUrl, QThread, pyqtSlot, QMetaObject
from PyQt6.QtGui import QIcon, QPixmap, QFont, QColor, QAction, QPainter, QBrush, QKeySequence, QShortcut

# 导入日志管理器
from core.log_manager import global_logger as logger

# 导入语言管理器
from core.language_manager import LanguageManager
from ui.styles import AppStyles
from ui.floating_dialog import TranslucentPanel, FloatingDialog

# 导入播放器服务
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from services.mpv_player_service import MpvPlayerController

# 频道列表（默认为空，需要用户打开播放列表文件）
CHANNELS = []

# 频道分组（从实际数据中提取，初始为空）
CHANNEL_GROUPS = ["All Channels"]

# EPG 节目单数据（初始为空字典）
EPG_DATA = {}


# 主应用类
class IPTVPlayer(QMainWindow):
    # 导入信号模块
    from PyQt6.QtCore import pyqtSignal
    from ui.styles import AppStyles
    # 定义EPG状态更新信号
    epg_status_signal = pyqtSignal(str)
    # 定义其他信号
    channel_list_updated = pyqtSignal()
    epg_list_updated = pyqtSignal()
    status_message = pyqtSignal(str)
    
    def __init__(self):
        import time
        logger.debug("开始初始化 IPTVPlayer（最小化）")
        super().__init__()
        logger.debug("设置窗口属性")
        # 配置管理器
        from core.config_manager import ConfigManager
        self.config = ConfigManager()

        from ui.theme_manager import get_theme_manager
        self._theme_manager = get_theme_manager()

        self.language_manager = LanguageManager()
        self.language_manager.load_available_languages()
        saved_language = self.config.load_language_settings()
        self.language_manager.set_language(saved_language)
        
        # 获取当前版本号并设置窗口标题
        from ui.dialogs.about_dialog import AboutDialog
        current_version = AboutDialog.CURRENT_VERSION
        self.setWindowTitle(f"{self.language_manager.tr('app_title', 'IPTV Scanner Editor Pro')} v{current_version}")
        
        # 设置窗口图标
        from PyQt6.QtGui import QIcon
        from utils.general_utils import get_icon_path
        ico_path = get_icon_path()
        if os.path.exists(ico_path):
            self.setWindowIcon(QIcon(ico_path))
        
        # 加载窗口布局（包括位置和大小）
        x, y, width, height, _ = self.config.load_window_layout(
            default_x=100,
            default_y=100,
            default_width=1280,
            default_height=780
        )
        self.setGeometry(x, y, width, height)
        self.setMinimumSize(800, 600)

        # 连接EPG状态信号到槽函数
        self.epg_status_signal.connect(self.update_status_bar)
        # 连接其他信号到槽函数
        self.channel_list_updated.connect(self._update_channel_list_ui)
        self.epg_list_updated.connect(self._populate_epg_list)
        self.status_message.connect(self.status_bar_show_message)
        
        # 频道列表模型
        self.channel_model = ChannelListModel()
        
        # 当前选中的频道（默认为None）
        self.current_channel = None
        
        # 面板状态
        self.epg_visible = True
        self.playlist_visible = True
        
        # 悬浮面板显示状态
        self.floating_panel_visible = True
        
        # 全屏状态
        self.is_fullscreen = False
        
        # EPG解析器
        from core.epg_parser import global_epg_parser
        self.epg_parser = global_epg_parser
        
        # 导入 QTimer
        from PyQt6.QtCore import QTimer
        
        # 初始化定时器占位符
        self.update_timer = None
        self.resize_timer = None
        self._initialization_complete = False
        self._panels_initialized = False
        self._ui_initialized = False
        
        # 注意：所有悬浮窗先不创建
        self.epg_panel = None
        self.playlist_panel = None
        self.floating_panel = None
        
        # 初始化视频相关属性，避免 update_floating_position 出错
        self.video_frame = None
        self.video_widget = None
        self.video_placeholder = None
        self.top_layout = None
        self.toolbar = None
        self.status_bar = None
        
        # 初始化EPG日期选择
        from datetime import datetime
        self.current_epg_date = datetime.now().date()
        
        # 创建最最基本的UI，只为了显示黑色背景的窗口
        logger.debug("创建最最基本的UI")
        self.central_widget = QWidget()
        self.central_widget.setStyleSheet(AppStyles.player_background_style())
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        logger.debug("IPTVPlayer（最小化）初始化完成")
        
        # 加载窗口布局
        x, y, width, height, _ = self.config.load_window_layout(
            default_x=100,
            default_y=100,
            default_width=1280,
            default_height=780
        )
        # 增加 Y 坐标 30 像素，以补偿标题栏高度
        y += 30
        self.setGeometry(x, y, width, height)
        
        # 设置主窗口样式
        self.setStyleSheet(AppStyles.main_window_style())
        
        # 立即显示窗口
        self.show()
        
        # 处理事件，确保窗口渲染完成
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        if app:
            app.processEvents()
        
        # 执行初始化流程
        self._initialize_in_order()
    
    def init_ui(self):
        """初始化UI（极简版本，只为了立即显示黑色窗口）"""
        # 注意：central_widget 和 main_layout 已经在 __init__ 中创建了
        # 这里什么都不用做，因为我们只需要显示黑色背景的窗口
        # 所有复杂的UI都在 _create_full_ui 中创建
        logger.debug("init_ui: 完成（极简）")
    
    def _initialize_in_order(self):
        """按照顺序执行初始化流程"""
        logger.debug("_initialize_in_order: 开始")
        
        # 处理事件，确保UI渲染完成
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        
        # 批量创建UI组件
        # 1. 初始化基本UI
        self.init_ui()
        
        # 2. 初始化视频相关组件（菜单栏、工具栏、视频区域、状态栏）
        self._init_video_components()
        
        # 3. 创建视频区域
        self._create_video_area()
        
        # 4. 创建状态栏
        self._create_status_bar()
        
        # 5. 初始化播放器
        self._init_player()
        
        # 6. 创建定时器
        self._create_timer()
        
        # 7. 创建并显示EPG面板
        self._create_epg_panel()
        
        # 8. 创建并显示播放列表面板
        self._create_playlist_panel()
        
        # 9. 创建并显示底部悬浮控制面板
        self._create_bottom_panel()
        
        # 10. 初始化最近打开文件菜单
        self._update_recent_files_menu()
        
        # 11. 安装事件过滤器
        self._install_event_filters()
        
        # 12. 面板已经在创建时显示，无需再次显示
        
        # 13. 更新悬浮窗位置
        self._update_floating_position()
        
        # 批量处理事件，确保所有UI渲染完成
        if app:
            app.processEvents()
        
        # 14. 延迟执行数据加载，确保UI先显示
        from PyQt6.QtCore import QTimer
        
        def load_data_with_delay():
            # 启动订阅更新
            self._start_subscription_timers()
            
            # 填充频道列表
            self._populate_channel_list()
            
            # 填充 EPG 列表
            self._populate_epg_list()
            
            # 检查版本更新
            self._check_for_updates_async()
        
        # 使用 QTimer 延迟执行，确保在主线程中执行
        QTimer.singleShot(200, load_data_with_delay)
        
        # 标记UI初始化完成
        self._ui_initialized = True

        from utils.resource_cleaner import register_cleanup
        from services.mpv_validator_service import MpvStreamValidator
        from utils.memory_manager import optimize_memory
        register_cleanup(MpvStreamValidator.terminate_all, "mpv_validator_terminate_all")
        register_cleanup(optimize_memory, "optimize_memory")

        self._theme_manager.register_window(self)
        
        # 添加空格键快捷键，用于播放/暂停
        # 绑定到应用程序，这样无论哪个窗口获得焦点，快捷键都会响应
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        # 使用正确的方式创建空格键快捷键
        space_shortcut = QShortcut(' ', app)
        space_shortcut.activated.connect(self.toggle_play)
        # 确保快捷键在所有窗口中都能工作
        space_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        
        logger.debug("_initialize_in_order: 完成")
    
    def _handle_playlist_subscription(self, need_update, playlist_url):
        """在后台线程中处理列表订阅"""
        try:
            global CHANNELS

            # 检查 URL 是否变化
            last_url = self.config.get_value('Playlist', 'last_url', '')
            url_changed = (last_url != playlist_url)

            if url_changed:
                logger.info(f"列表订阅地址已变化: '{last_url}' -> '{playlist_url}'，强制更新")
                need_update = True

            if need_update:
                logger.info("列表订阅需要更新，开始下载最新数据")
                self.update_playlist_subscription()
                # 保存当前 URL
                self.config.set_value('Playlist', 'last_url', playlist_url)
                self.config.save_config()
            else:
                # 检查是否有本地缓存的列表文件
                import os
                cache_dir = self.config.get_value('General', 'cache_dir', 'cache')
                if cache_dir and not os.path.exists(cache_dir):
                    os.makedirs(cache_dir)
                
                playlist_cache_file = os.path.join(cache_dir, 'playlist_cache.m3u') if cache_dir else 'playlist_cache.m3u'
                
                if os.path.exists(playlist_cache_file):
                    try:
                        with open(playlist_cache_file, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        # 解析M3U内容
                        if self.channel_model.load_from_file(content):
                            # 更新CHANNELS列表
                            global CHANNELS
                            CHANNELS = []
                            for i, ch in enumerate(self.channel_model.channels):
                                CHANNELS.append({
                                    "id": i + 1,
                                    "name": ch.get('name', '未命名'),
                                    "url": ch.get('url', ''),
                                    "logo": ch.get('logo', ''),
                                    "group": ch.get('group', '未分类'),
                                    "tvg_id": ch.get('tvg_id', ''),
                                    "tvg_chno": ch.get('tvg_chno', ''),
                                    "tvg_shift": ch.get('tvg_shift', ''),
                                    "catchup": ch.get('catchup', ''),
                                    "catchup_days": ch.get('catchup_days', ''),
                                    "catchup_source": ch.get('catchup_source', ''),
                                    "resolution": ch.get('resolution', ''),
                                    "current_program": ''
                                })
                            
                            # 更新频道列表UI
                            self.channel_list_updated.emit()
                            
                            logger.debug(f"列表订阅无需更新，从缓存加载数据，共 {len(CHANNELS)} 个频道")
                            self.status_message.emit(self.language_manager.tr("loading_from_cache", "Loading from cache"))
                        else:
                            logger.error("缓存列表文件解析失败")
                            # 尝试直接解析内容
                            logger.debug("尝试直接解析缓存内容...")
                            try:
                                from services.m3u_parser import is_valid_channel_url as _is_valid_url
                                lines = content.strip().split('\n')
                                channels = []
                                current_channel = {}
                                current_group = '未分类'
                                for line in lines:
                                    line = line.strip()
                                    if line.startswith('#EXTINF:'):
                                        extinf_content = line[8:].strip()
                                        genre_match = re.search(r',\s*#genre#\s*', extinf_content)
                                        if genre_match:
                                            before_genre = extinf_content[:genre_match.start()].strip()
                                            group_name = before_genre
                                            comma_pos = before_genre.rfind(',')
                                            if comma_pos >= 0:
                                                group_name = before_genre[comma_pos+1:].strip()
                                            group_name = group_name.strip('=').strip()
                                            if group_name:
                                                current_group = group_name
                                            current_channel = {}
                                            continue
                                        parts = line.split(',', 1)
                                        if len(parts) > 1:
                                            name = parts[1].strip()
                                            current_channel['name'] = name
                                            current_channel['group'] = current_group
                                    elif line.startswith('#EXTGRP:'):
                                        current_group = line[8:].strip()
                                    elif not line.startswith('#') and line:
                                        if current_channel:
                                            url = line.strip()
                                            if _is_valid_url(url):
                                                current_channel['url'] = url
                                                channels.append(current_channel.copy())
                                            current_channel = {}
                                
                                if channels:
                                    logger.debug(f"手动解析成功，共 {len(channels)} 个频道")
                                    # 更新CHANNELS列表
                                    CHANNELS = []
                                    for i, ch in enumerate(channels):
                                        CHANNELS.append({
                                            "id": i + 1,
                                            "name": ch.get('name', '未命名'),
                                            "url": ch.get('url', ''),
                                            "logo": ch.get('logo', ''),
                                            "group": ch.get('group', '未分类'),
                                            "tvg_id": ch.get('tvg_id', ''),
                                            "tvg_chno": ch.get('tvg_chno', ''),
                                            "tvg_shift": ch.get('tvg_shift', ''),
                                            "catchup": ch.get('catchup', ''),
                                            "catchup_days": ch.get('catchup_days', ''),
                                            "catchup_source": ch.get('catchup_source', ''),
                                            "resolution": ch.get('resolution', ''),
                                            "current_program": ''
                                        })
                                    
                                    # 更新频道列表UI
                                    self.channel_list_updated.emit()
                                    
                                    logger.debug(f"手动解析后更新列表UI，共 {len(CHANNELS)} 个频道")
                                    self.status_message.emit("手动解析后更新列表")
                                else:
                                    logger.error("手动解析也失败")
                            except Exception as ex:
                                logger.error(f"手动解析失败: {ex}")
                    except Exception as ex:
                        logger.error(f"加载缓存列表失败: {ex}")
                else:
                    logger.debug("缓存文件不存在")
                    # 如果缓存文件不存在，强制更新列表
                    logger.debug("缓存文件不存在，强制更新列表")
                    self.update_playlist_subscription()
        except Exception as ex:
            logger.error(f"处理列表订阅失败: {ex}")
    
    def update_channel_list_ui(self):
        """更新频道列表UI（公共方法，用于 QMetaObject.invokeMethod 调用）"""
        self._update_channel_list_ui()
    
    def _update_channel_list_ui(self):
        try:
            self.populate_channel_list()
        except Exception as ex:
            logger.error(f"更新频道列表UI失败: {ex}")
    
    def status_bar_show_message(self, message):
        """在状态栏显示消息"""
        try:
            if self.status_bar:
                self.status_bar.showMessage(message)
        except Exception as ex:
            logger.error(f"在状态栏显示消息失败: {ex}")
    
    def _handle_epg_subscription(self, epg_url, epg_interval):
        """在后台线程中处理节目单订阅"""
        logger.info(f"开始处理节目单订阅: {epg_url}")
        try:
            global EPG_DATA

            from datetime import datetime, timedelta

            # 检查 URL 是否变化
            last_url = self.config.get_value('EPG', 'last_url', '')
            url_changed = (last_url != epg_url)

            if url_changed:
                logger.info(f"EPG 订阅地址已变化: '{last_url}' -> '{epg_url}'，强制更新")

            last_update_str = self.config.get_value('EPG', 'last_update', None)
            need_update = True
            if last_update_str and not url_changed:
                try:
                    last_update = datetime.fromisoformat(last_update_str)
                    time_since_update = datetime.now() - last_update
                    if time_since_update.total_seconds() < epg_interval * 60:
                        need_update = False
                        logger.debug(f"节目单订阅无需立即更新，上次更新时间: {last_update}，距下次更新还有 {(epg_interval * 60 - time_since_update.total_seconds()) / 60:.1f} 分钟")
                except Exception as e:
                    logger.error(f"解析EPG上次更新时间失败: {e}")
                    pass
            else:
                logger.debug("未找到EPG上次更新时间，需要更新")

            if need_update or url_changed:
                logger.info(f"节目单订阅需要更新（间隔: {epg_interval} 分钟），开始下载最新数据")
                self.update_epg_subscription()
                # 保存当前 URL
                self.config.set_value('EPG', 'last_url', epg_url)
                self.config.save_config()
            else:
                from core.epg_parser import global_epg_parser
                global_epg_parser.load_cached_epg_data()
                if global_epg_parser.epg_data:
                    EPG_DATA = global_epg_parser.epg_data
                    logger.info(f"节目单订阅无需更新，从缓存加载数据，共 {len(EPG_DATA)} 个频道")
                    self.epg_list_updated.emit()
                else:
                    logger.debug("EPG缓存数据为空，强制更新")
                    self.update_epg_subscription()
        except Exception as ex:
            logger.error(f"处理节目单订阅失败: {ex}", exc_info=True)
    
    def _load_data_in_background(self):
        """在后台线程中加载数据"""
        logger.debug("_load_data_in_background: 开始")
        
        # 1. 等待UI元素显示
        import time
        max_wait = 5  # 最大等待时间（秒）
        wait_time = 0
        
        while wait_time < max_wait:
            # 检查关键UI元素是否已经创建
            if hasattr(self, 'video_frame') and self.video_frame and \
               hasattr(self, 'floating_panel') and self.floating_panel and \
               hasattr(self, 'epg_panel') and self.epg_panel and \
               hasattr(self, 'playlist_panel') and self.playlist_panel:
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
        
        # 第一步：初始化基本UI
        self.init_ui()
        
        # 第二步：创建视频相关组件
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
        
        # 添加视频区域到布局
        self.top_layout.addWidget(self.video_frame, 1)
        self.main_layout.addLayout(self.top_layout, 1)
        
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
        self.original_channel = None
        
        logger.debug("_create_status_bar: 完成")
    
    def _init_player(self):
        logger.debug("_init_player: 开始")
        
        self.player_controller = MpvPlayerController(self.video_widget)
        self.player_controller.play_state_changed.connect(self.on_play_state_changed)
        self.player_controller.media_info_ready.connect(self.on_media_info_ready)
        self.player_controller.live_media_info_updated.connect(self.on_live_media_info_updated)
        self.player_controller.play_error.connect(self.on_play_error)

        from services.logo_cache_service import LogoCacheService
        self._logo_cache_service = LogoCacheService(self)
        self._logo_cache_service.logo_loaded.connect(self._on_logo_cache_loaded)

        from services.network_preheat_service import DnsPrefetcher, ConnectionPreheater
        self._dns_prefetcher = DnsPrefetcher(self)
        self._connection_preheater = ConnectionPreheater(self)

        self._source_timeout_timer = None
        self._current_source_index = {}
        self._timeshift_active = False
        self._timeshift_start_time = None

        self._load_last_channel()

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
        
        logger.debug("_create_timer: 完成")
    
    def _create_epg_panel(self):
        """创建EPG面板"""
        logger.debug("_create_epg_panel: 开始")
        tr = self.language_manager.tr
        
        # 左侧EPG面板
        self.epg_panel = TranslucentPanel(opacity=180)
        self.epg_panel.setStyleSheet(AppStyles.player_panel_style())
        self.epg_panel.setFixedWidth(250)
        self.epg_layout = QVBoxLayout(self.epg_panel)
        
        # EPG标题
        tr = self.language_manager.tr
        self.epg_title = QLabel(f"📅 {tr('epg_title', 'Program Guide')}")
        self.epg_title.setStyleSheet(AppStyles.player_epg_title_style())
        self.epg_layout.addWidget(self.epg_title)
        
        # 日期选择器
        date_layout = QHBoxLayout()
        date_layout.setContentsMargins(8, 0, 8, 8)
        
        # 上一天按钮
        self.epg_prev_day = QPushButton("◀")
        self.epg_prev_day.setFixedSize(24, 24)
        self.epg_prev_day.setStyleSheet(AppStyles.player_date_button_style())
        self.epg_prev_day.clicked.connect(self.on_prev_day)
        date_layout.addWidget(self.epg_prev_day)
        
        # 日期显示
        self.epg_date_label = QLabel(tr("today", "Today"))
        self.epg_date_label.setStyleSheet(AppStyles.player_date_label_style())
        self.epg_date_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        date_layout.addWidget(self.epg_date_label, 1)
        
        # 下一天按钮
        self.epg_next_day = QPushButton("▶")
        self.epg_next_day.setFixedSize(24, 24)
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
        self.epg_content.addItem(self.language_manager.tr("loading", "Loading..."))
        # 添加点击事件处理
        self.epg_content.itemClicked.connect(self.on_epg_item_clicked)
        self.epg_layout.addWidget(self.epg_content, 1)
        
        # EPG空提示
        self.epg_empty_label = QLabel(tr("no_epg_data", "No program information"))
        self.epg_empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.epg_empty_label.setStyleSheet(AppStyles.player_empty_label_style())
        self.epg_layout.addWidget(self.epg_empty_label)
        
        # 显示面板
        self.epg_panel.show()
        
        logger.debug("_create_epg_panel: 完成")
    
    def _create_playlist_panel(self):
        """创建播放列表面板"""
        logger.debug("_create_playlist_panel: 开始")
        tr = self.language_manager.tr
        
        # 右侧播放列表面板
        self.playlist_panel = TranslucentPanel(opacity=180)
        self.playlist_panel.setStyleSheet(AppStyles.player_panel_style())
        self.playlist_panel.setFixedWidth(250)
        self.playlist_layout = QVBoxLayout(self.playlist_panel)
        
        # 播放列表标题和分组选择
        self.playlist_header = QHBoxLayout()
        self.playlist_title = QLabel(f"📺 {tr('channel_list', 'Channel List')}")
        self.playlist_title.setStyleSheet(AppStyles.player_playlist_title_style())
        self.group_combo = QComboBox()
        self.group_combo.addItems(CHANNEL_GROUPS)
        self.group_combo.setStyleSheet(AppStyles.player_group_combo_style())
        self.group_combo.currentTextChanged.connect(self.on_group_changed)
        self.playlist_header.addWidget(self.playlist_title)
        self.playlist_header.addWidget(self.group_combo)
        self.playlist_layout.addLayout(self.playlist_header)
        
        # 频道列表
        self.channel_list = QListWidget()
        self.channel_list.setStyleSheet(AppStyles.player_list_style())
        self.channel_list.setSpacing(6)
        self.channel_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.channel_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.channel_list.itemClicked.connect(self.select_channel)
        self.playlist_layout.addWidget(self.channel_list, 1)
        
        # 频道列表空提示
        self.channel_empty_label = QLabel(tr("no_channels", "No channels"))
        self.channel_empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.channel_empty_label.setStyleSheet(AppStyles.player_empty_label_style())
        self.playlist_layout.addWidget(self.channel_empty_label)
        
        # 显示面板
        self.playlist_panel.show()
        
        logger.debug("_create_playlist_panel: 完成")
    
    def _create_bottom_panel(self):
        """创建底部悬浮控制面板"""
        logger.debug("_create_bottom_panel: 开始")
        
        # 第一步：创建底部面板
        self._create_panel()
        
        logger.debug("_create_bottom_panel: 完成")
    
    def _create_panel(self):
        """创建面板"""
        logger.debug("_create_panel: 开始")
        tr = self.language_manager.tr
        
        # 悬浮控制面板
        self.floating_panel = TranslucentPanel(opacity=180)
        self.floating_panel.setStyleSheet(AppStyles.player_panel_style())
        self.floating_panel.setFixedHeight(150)
        self.floating_panel.setFixedWidth(1000)
        self.floating_layout = QVBoxLayout(self.floating_panel)
        self.floating_layout.setContentsMargins(15, 6, 15, 8)
        self.floating_layout.setSpacing(3)
        
        # 第二步：创建媒体信息行
        self._create_media_row()
        
        # 显示面板
        self.floating_panel.show()
        
        logger.debug("_create_panel: 完成")
    
    def _create_media_row(self):
        """创建媒体信息行"""
        logger.debug("_create_media_row: 开始")
        tr = self.language_manager.tr
        
        # 第一行：媒体信息（详细版）
        self.media_row = QHBoxLayout()
        self.media_row.setSpacing(12)
        
        self.video_info = QLabel(f"📺 {tr('not_playing', 'Not playing')}")
        self.video_info.setStyleSheet(AppStyles.player_label_style())
        self.video_info.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.video_info.setFixedHeight(22)
        self.media_row.addWidget(self.video_info)
        
        self.audio_info = QLabel("🔊 --")
        self.audio_info.setStyleSheet(AppStyles.player_label_style())
        self.audio_info.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.audio_info.setFixedHeight(18)
        self.media_row.addWidget(self.audio_info)
        
        self.network_info = QLabel("📡 --")
        self.network_info.setStyleSheet(AppStyles.player_label_style())
        self.network_info.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.network_info.setFixedHeight(18)
        self.media_row.addWidget(self.network_info)
        
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
        
        # 第二行：节目信息（加高布局）
        self.info_row = QHBoxLayout()
        self.info_row.setSpacing(15)
        
        # 左侧：频道LOGO（更宽的长方形）和名称
        left_section = QHBoxLayout()
        left_section.setSpacing(10)
        
        self.channel_logo = QLabel("📺")
        self.channel_logo.setStyleSheet(AppStyles.player_channel_logo_style())
        self.channel_logo.setFixedSize(120, 40)
        left_section.addWidget(self.channel_logo)
        
        name_section = QVBoxLayout()
        name_section.setSpacing(2)
        
        self.channel_name = QLabel(tr("no_channel_selected", "No channel selected"))
        self.channel_name.setStyleSheet(AppStyles.player_channel_name_style())
        name_section.addWidget(self.channel_name)
        
        self.current_program = QLabel(tr("select_channel_to_play", "▶ Select a channel to play"))
        self.current_program.setStyleSheet(AppStyles.player_program_style())
        name_section.addWidget(self.current_program)
        
        left_section.addLayout(name_section)
        left_section.addStretch()
        self.info_row.addLayout(left_section, 2)
        
        # 中间：节目描述（直接显示内容，无标题）
        desc_section = QVBoxLayout()
        desc_section.setContentsMargins(0, 5, 0, 0)
        
        self.program_desc = QLabel(tr("open_playlist_or_import", "Open a playlist file or import channels to start watching"))
        self.program_desc.setStyleSheet(AppStyles.player_program_desc_style())
        self.program_desc.setWordWrap(True)
        self.program_desc.setFixedHeight(40)
        self.program_desc.setAlignment(Qt.AlignmentFlag.AlignTop)
        desc_section.addWidget(self.program_desc)
        self.info_row.addLayout(desc_section, 3)
        
        # 右侧：节目时间信息
        time_section = QVBoxLayout()
        time_section.setSpacing(2)
        
        self.time_label = QLabel("⏱ --:-- - --:--")
        self.time_label.setStyleSheet(AppStyles.player_label_style())
        time_section.addWidget(self.time_label)
        
        self.remain_label = QLabel(tr("waiting_to_play", "Waiting to play..."))
        self.remain_label.setStyleSheet(AppStyles.player_program_style())
        time_section.addWidget(self.remain_label)
        self.info_row.addLayout(time_section, 1)
        
        self.floating_layout.addLayout(self.info_row)
        
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
        self.program_progress.setRange(0, 100)
        self.program_progress.setValue(0)
        self.program_progress.setFixedWidth(450)
        self.program_progress.setStyleSheet(AppStyles.player_slider_style())
        self.program_progress.sliderReleased.connect(self.on_progress_slider_released)
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
        self.aspect_button.setFixedSize(28, 26)
        self.aspect_button.setStyleSheet(AppStyles.player_button_style())
        self.aspect_button.clicked.connect(self._cycle_aspect_ratio)
        self.control_row.addWidget(self.aspect_button)
        
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
        logger.debug("_final_initialization: 开始")
        
        logger.debug("_final_initialization: 完成")
    
    def _show_floating_panel(self):
        """显示底部悬浮控制面板"""
        logger.debug("_show_floating_panel: 开始")
        
        # 显示底部悬浮控制面板
        if self.floating_panel:
            self.floating_panel.show()
        
        logger.debug("_show_floating_panel: 完成")
    
    def _show_side_panels(self):
        """显示左右面板"""
        logger.debug("_show_side_panels: 开始")
        
        # 设置左右侧边栏为独立窗口（悬浮效果）
        # 左侧 EPG 面板悬浮
        if self.epg_panel and self.video_frame:
            self.epg_panel.setFixedHeight(self.video_frame.height() - 180)
            self.epg_panel.show()
        
        # 右侧播放列表面板悬浮
        if self.playlist_panel and self.video_frame:
            self.playlist_panel.setFixedHeight(self.video_frame.height() - 180)
            self.playlist_panel.show()
        
        logger.debug("_show_side_panels: 完成")
    
    def _install_event_filters(self):
        """安装事件过滤器"""
        logger.debug("_install_event_filters: 开始")
        
        # 安装事件过滤器
        if self.video_frame:
            self.video_frame.installEventFilter(self)
        if self.video_widget:
            self.video_widget.installEventFilter(self)
        if self.video_placeholder:
            self.video_placeholder.installEventFilter(self)
        
        # 填充频道列表
        self._populate_channel_list()
        
        logger.debug("_install_event_filters: 完成")
    
    def populate_channel_list_ui(self):
        """填充频道列表（公共方法，用于 QMetaObject.invokeMethod 调用）"""
        self._populate_channel_list()
    
    def populate_epg_list_ui(self):
        """填充EPG列表（公共方法，用于 QMetaObject.invokeMethod 调用）"""
        self._populate_epg_list()
    
    def check_for_updates_ui(self):
        """检查版本更新（公共方法，用于 QMetaObject.invokeMethod 调用）"""
        self._check_for_updates_async()
    
    def _populate_channel_list(self):
        """填充频道列表（带防重复机制）"""
        # 防止短时间内重复调用（500ms内只执行一次）
        current_time = time.time()
        if hasattr(self, '_last_populate_time') and current_time - self._last_populate_time < 0.5:
            logger.debug(f"_populate_channel_list: 跳过重复调用（距上次{current_time - self._last_populate_time:.2f}秒）")
            return
        self._last_populate_time = current_time

        logger.debug("_populate_channel_list: 开始")

        # 填充频道列表
        self.populate_channel_list()

        # 填充 EPG 列表
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
    
    def _start_subscription_timers(self):
        """启动订阅更新定时器"""
        logger.debug("_start_subscription_timers: 开始")
        
        # 启动订阅更新定时器
        self.start_subscription_timers()
        
        # 安装事件过滤器
        self._install_event_filters()
        
        logger.debug("_start_subscription_timers: 完成")
    
    def _update_recent_files_menu(self):
        """初始化最近打开文件菜单"""
        logger.debug("_update_recent_files_menu: 开始")
        
        # 初始化最近打开文件菜单
        self.update_recent_files_menu()
        
        self._panels_initialized = True
        self._initialization_complete = True
        

        
        logger.debug("_update_recent_files_menu: 完成")
    
    def update_status_bar(self, message):
        """更新状态栏消息"""
        if self.status_bar:
            self.status_bar.showMessage(message)
        
        # 填充频道列表
        self.populate_channel_list()
        
        # 更新悬浮窗位置
        self.update_floating_position()
    
    def setup_menu_bar(self, skip_recent_files=False):
        """设置菜单栏"""
        menu_bar = self.menuBar()
        if not menu_bar:
            return
        
        # 设置菜单栏样式
        menu_bar.setStyleSheet(AppStyles.player_menu_bar_style())
        
        try:
            tr = self.language_manager.tr
            
            # 文件菜单
            file_menu = menu_bar.addMenu(tr("menu_file", "File"))
            recent_menu = None
            if file_menu:
                open_playlist = QAction(tr("menu_open_playlist", "Open Playlist"), self)
                open_playlist.triggered.connect(self.open_playlist)
                open_playlist.setShortcut("Ctrl+O")
                file_menu.addAction(open_playlist)
                
                # 添加最近打开子菜单
                recent_menu = file_menu.addMenu(tr("menu_recent_open", "Recent"))
                
                save_as = QAction(tr("menu_save_as", "Save As..."), self)
                save_as.triggered.connect(self.save_as)
                save_as.setShortcut("Ctrl+S")
                file_menu.addAction(save_as)
                
                file_menu.addSeparator()
                
                exit_action = QAction(tr("menu_exit", "Exit"), self)
                exit_action.triggered.connect(self.close)
                exit_action.setShortcut("Ctrl+Q")
                file_menu.addAction(exit_action)
            
            # 保存最近打开菜单引用
            self.recent_menu = recent_menu
            
            # 初始化最近打开文件列表（如果需要）
            if not skip_recent_files:
                self.update_recent_files_menu()
            
            # 视图菜单
            view_menu = menu_bar.addMenu(tr("menu_view", "View"))
            
            show_epg = QAction(tr("menu_epg_list", "EPG List"), self)
            show_epg.setCheckable(True)
            show_epg.setChecked(self.epg_visible)
            show_epg.triggered.connect(self.toggle_epg)
            show_epg.setShortcut("E")
            view_menu.addAction(show_epg)
            
            show_playlist = QAction(tr("menu_playlist", "Playlist"), self)
            show_playlist.setCheckable(True)
            show_playlist.setChecked(self.playlist_visible)
            show_playlist.triggered.connect(self.toggle_playlist)
            show_playlist.setShortcut("L")
            view_menu.addAction(show_playlist)
            
            show_floating = QAction(tr("menu_control_panel", "Control Panel"), self)
            show_floating.setCheckable(True)
            show_floating.setChecked(self.floating_panel_visible)
            show_floating.triggered.connect(self.toggle_floating_panel)
            show_floating.setShortcut("M")
            view_menu.addAction(show_floating)
            
            view_menu.addSeparator()
            
            fullscreen = QAction(tr("menu_fullscreen", "Fullscreen"), self)
            fullscreen.setCheckable(True)
            fullscreen.triggered.connect(self.toggle_fullscreen)
            fullscreen.setShortcut("F11")
            view_menu.addAction(fullscreen)
            
            refresh = QAction(tr("menu_refresh", "Refresh"), self)
            refresh.triggered.connect(self.refresh_ui)
            refresh.setShortcut("F5")
            view_menu.addAction(refresh)
            
            reset_layout = QAction(tr("menu_reset_layout", "Reset Layout"), self)
            reset_layout.triggered.connect(self.reset_layout)
            view_menu.addAction(reset_layout)
            
            # 工具菜单
            tools_menu = menu_bar.addMenu(tr("menu_tools", "Tools"))
            
            scan_channels = QAction(tr("menu_scan_channels", "Scan Channels"), self)
            scan_channels.triggered.connect(self.open_scan_ui)
            tools_menu.addAction(scan_channels)
            
            channel_mapping = QAction(tr("menu_mapping", "Mapping"), self)
            channel_mapping.triggered.connect(self.open_channel_mapping)
            tools_menu.addAction(channel_mapping)
            
            tools_menu.addSeparator()
            
            player_settings = QAction(tr("menu_subscription_settings", "Subscription Settings"), self)
            player_settings.triggered.connect(self.player_settings)
            tools_menu.addAction(player_settings)
            
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

            for theme in themes:
                theme_display = tr(theme, theme)
                theme_action = QAction(theme_display, self)
                theme_action.setCheckable(True)
                theme_action.setChecked(theme == theme_manager.get_current_theme())
                theme_action.triggered.connect(lambda checked, t=theme: self.set_theme(t))
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
    
    def update_channel_groups(self):
        """从CHANNELS中提取分组并更新下拉框"""
        global CHANNEL_GROUPS
        
        # 提取所有唯一的分组，保持出现顺序
        groups = []
        seen = set()
        for channel in CHANNELS:
            group = channel.get('group', '') or '未分类'
            if group not in seen:
                groups.append(group)
                seen.add(group)
        
        # 更新CHANNEL_GROUPS
        new_groups = [self.language_manager.tr("all_channels", "All Channels")] + groups
        
        # 如果分组没有变化，不需要更新
        if new_groups == CHANNEL_GROUPS:
            return
        
        CHANNEL_GROUPS = new_groups
        
        # 暂时断开信号连接，避免递归
        self.group_combo.blockSignals(True)
        
        # 更新下拉框
        current_text = self.group_combo.currentText()
        self.group_combo.clear()
        self.group_combo.addItems(CHANNEL_GROUPS)
        
        # 尝试恢复之前的选择
        index = self.group_combo.findText(current_text)
        if index >= 0:
            self.group_combo.setCurrentIndex(index)
        
        # 恢复信号连接
        self.group_combo.blockSignals(False)
    
    def populate_channel_list(self):
        """填充频道列表"""
        self.channel_list.clear()
        
        # 更新分组下拉框
        self.update_channel_groups()
        
        if not CHANNELS:
            logger.debug(f"populate_channel_list: CHANNELS为空，显示空提示")
            self.channel_empty_label.show()
            return
        self.channel_empty_label.hide()
        
        # 获取当前选中的分组
        selected_group = self.group_combo.currentText()

        for idx, channel in enumerate(CHANNELS):
            if selected_group != self.language_manager.tr("all_channels", "All Channels"):
                channel_group = channel.get('group', self.language_manager.tr("uncategorized", "Uncategorized"))
                if channel_group != selected_group:
                    continue

            # 创建自定义的频道项 widget
            channel_name = channel.get("name", self.language_manager.tr("unnamed", "Unnamed"))
            logo_url = channel.get('logo', '')
            
            # 创建一个容器 widget
            item_widget = QtWidgets.QWidget()
            item_layout = QHBoxLayout(item_widget)
            item_layout.setContentsMargins(5, 5, 5, 5)
            item_layout.setSpacing(10)
            
            # 台标标签
            logo_label = QtWidgets.QLabel()
            logo_label.setFixedSize(60, 60)
            logo_label.setStyleSheet("background-color: transparent; border: none;")
            logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            logo_label.setMinimumSize(60, 60)
            logo_label.setMaximumSize(60, 60)
            
            # 如果有台标，加载它
            if logo_url:
                logo_url = logo_url.strip('`"\'')
                cached = self._logo_cache_service.get(logo_url)
                if cached:
                    scaled = self._logo_cache_service.scale_logo_pixmap(cached, 60)
                    logo_label.setPixmap(scaled)
                else:
                    # 异步加载台标
                    self._logo_cache_service.fetch_async(logo_url)
            
            # 频道名称标签
            name_label = QtWidgets.QLabel(channel_name)
            name_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #FFFFFF;")
            name_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            name_label.setWordWrap(False)
            
            # 添加到布局
            item_layout.addWidget(logo_label, 0, Qt.AlignmentFlag.AlignVCenter)
            item_layout.addWidget(name_label, 1, Qt.AlignmentFlag.AlignVCenter)
            
            # 创建 QListWidgetItem 并设置大小
            item = QListWidgetItem()
            item.setSizeHint(QSize(0, 70))
            item.setData(Qt.ItemDataRole.UserRole, idx)
            
            # 将自定义 widget 设置为 item 的 widget
            self.channel_list.addItem(item)
            self.channel_list.setItemWidget(item, item_widget)
        
        logger.info(f"populate_channel_list: 填充完成，共 {self.channel_list.count()} 个频道项")
        # 连接滚动信号，实现懒加载
        self.channel_list.verticalScrollBar().valueChanged.connect(self._on_channel_list_scrolled)
    
    def _on_channel_list_scrolled(self, value):
        """频道列表滚动时，加载可见区域的台标"""
        # 获取可见区域的项
        viewport_rect = self.channel_list.viewport().rect()
        top_index = self.channel_list.indexAt(viewport_rect.topLeft())
        bottom_index = self.channel_list.indexAt(viewport_rect.bottomLeft())
        
        first_visible = top_index.row() if top_index.isValid() else 0
        last_visible = bottom_index.row() if bottom_index.isValid() else self.channel_list.count() - 1
        
        # 扩大加载范围，提前加载上下各 5 个项
        first_visible = max(0, first_visible - 5)
        last_visible = min(self.channel_list.count() - 1, last_visible + 5)
        
        # 加载可见区域的台标
        for i in range(first_visible, last_visible + 1):
            item = self.channel_list.item(i)
            if not item:
                continue
            
            # 获取自定义 widget
            item_widget = self.channel_list.itemWidget(item)
            if not item_widget:
                continue
            
            # 获取台标标签
            logo_label = item_widget.findChild(QtWidgets.QLabel)
            if not logo_label:
                continue
            # 检查是否已经有台标
            if logo_label.pixmap() and not logo_label.pixmap().isNull():
                continue  # 已经有台标了
            
            channel_idx = item.data(Qt.ItemDataRole.UserRole)
            if channel_idx is None or channel_idx >= len(CHANNELS):
                continue
            
            channel = CHANNELS[channel_idx]
            logo_url = channel.get('logo', '')
            if logo_url:
                logo_url = logo_url.strip('`"\'')
                # 尝试从缓存获取
                cached = self._logo_cache_service.get(logo_url)
                if cached:
                    scaled = self._logo_cache_service.scale_logo_pixmap(cached, 60)
                    logo_label.setPixmap(scaled)
                else:
                    # 异步加载台标
                    self._logo_cache_service.fetch_async(logo_url)
    
    def populate_epg_list(self):
        """填充EPG列表"""
        colors = AppStyles._get_colors()
        self.epg_content.clear()
        # 设置列表的整体样式
        self.epg_content.setStyleSheet(AppStyles.player_list_style())
        
        # 检查是否有当前频道
        if not self.current_channel:
            self.epg_empty_label.show()
            return
        
        # 从EPG解析器获取真实数据
        channel_name = self.current_channel.get("name", "")
        tvg_id = self.current_channel.get("tvg_id", "")
        
        # 获取当前频道的节目单
        epg_list = self.epg_parser.get_channel_epg(channel_name, tvg_id)
        
        # 处理从EPG解析器获取的节目数据
        if epg_list:
            # 确保节目数据按开始时间排序
            from datetime import datetime
            epg_list.sort(key=lambda x: datetime.fromisoformat(x.get('start', '')))
        
        # 如果EPG解析器没有数据，尝试从EPG_DATA获取
        if not epg_list and EPG_DATA and channel_name in EPG_DATA:
            current_channel_epg = EPG_DATA[channel_name]
            if current_channel_epg and len(current_channel_epg) > 0:
                # 转换EPG_DATA格式为与epg_parser返回的格式一致
                epg_list = []
                from datetime import datetime
                for program_data in current_channel_epg:
                    try:
                        # 解析时间格式
                        time_str = program_data.get('time', '')
                        if time_str:
                            # 假设时间格式为 "HH:MM-HH:MM"
                            time_parts = time_str.split('-')
                            if len(time_parts) == 2:
                                # 创建一个简单的节目对象
                                # 处理跨天节目
                                from datetime import timedelta
                                start_hour, start_minute = map(int, time_parts[0].split(':'))
                                end_hour, end_minute = map(int, time_parts[1].split(':'))
                                
                                # 确定开始和结束日期
                                now = datetime.now()
                                today = now.date()
                                current_hour = now.hour
                                
                                start_date = today
                                end_date = today
                                
                                # 如果结束时间小于开始时间，说明是跨天节目
                                if end_hour < start_hour:
                                    # 如果当前时间在00:00-开始时间之间，说明节目是昨天开始的
                                    if current_hour < start_hour:
                                        start_date = today - timedelta(days=1)
                                    end_date = today + timedelta(days=1)
                                
                                # 创建开始和结束时间
                                start_datetime = datetime.combine(start_date, datetime.min.time())
                                start_datetime = start_datetime.replace(hour=start_hour, minute=start_minute)
                                
                                end_datetime = datetime.combine(end_date, datetime.min.time())
                                end_datetime = end_datetime.replace(hour=end_hour, minute=end_minute)
                                
                                program = {
                                    'title': program_data.get('title', self.language_manager.tr('unknown_program', 'Unknown Program')),
                                    'desc': program_data.get('description', ''),
                                    'start': start_datetime.isoformat(),
                                    'end': end_datetime.isoformat()
                                }
                                epg_list.append(program)
                    except Exception as e:
                        logger.error(f"处理EPG_DATA节目失败: {e}")
                        continue
            
            # 确保节目数据按开始时间排序
            if epg_list:
                from datetime import datetime
                epg_list.sort(key=lambda x: datetime.fromisoformat(x.get('start', '')))
        
        # 如果没有节目数据，显示空提示
        if not epg_list:
            self.epg_empty_label.show()
            return
        
        # 隐藏空提示
        self.epg_empty_label.hide()
        
        # 显示节目单数据
        from datetime import datetime, timedelta
        now = datetime.now()
        current_program_index = -1
        item_index = 0
        has_date_program = False

        # 导入需要的模块
        from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor
        from PyQt6.QtCore import QSize, Qt

        # 过滤并排序节目列表
        filtered_programs = []
        yesterday_programs = []

        for program in epg_list:
            try:
                start_time = datetime.fromisoformat(program.get('start', ''))
                end_time = datetime.fromisoformat(program.get('end', ''))

                # 检查节目是否在当前选择的日期或与当前日期相关
                if start_time.date() == self.current_epg_date or end_time.date() == self.current_epg_date:
                    filtered_programs.append(program)
                # 检查节目是否是昨天的节目
                elif start_time.date() == self.current_epg_date - timedelta(days=1):
                    yesterday_programs.append(program)
            except Exception as e:
                logger.error(f"过滤节目失败: {e}")
                continue

        # 按开始时间排序节目列表
        filtered_programs.sort(key=lambda x: datetime.fromisoformat(x.get('start', '')))
        
        # 检查是否有当前时间正在播放的节目
        has_current_program = False
        current_program_index = -1
        item_index = 0
        
        # 首先检查是否有当前时间正在播放的节目
        for i, program in enumerate(filtered_programs):
            try:
                start_time = datetime.fromisoformat(program.get('start', ''))
                end_time = datetime.fromisoformat(program.get('end', ''))
                if start_time <= now <= end_time:
                    has_current_program = True
                    current_program_index = i
                    break
            except Exception as e:
                logger.error(f"检查当前节目失败: {e}")
                continue
        
        # 如果没有当前时间正在播放的节目，尝试从昨天的节目中查找
        if not has_current_program and yesterday_programs:
            # 按结束时间排序昨天的节目，找到结束时间最晚的节目
            yesterday_programs.sort(key=lambda x: datetime.fromisoformat(x.get('end', '')))
            
            # 查找昨天的节目中，结束时间大于当前时间的节目
            for program in reversed(yesterday_programs):
                try:
                    start_time = datetime.fromisoformat(program.get('start', ''))
                    end_time = datetime.fromisoformat(program.get('end', ''))
                    
                    # 检查节目是否在当前时间仍在播放
                    if start_time <= now <= end_time:
                        # 将这个节目添加到过滤列表的最前面
                        filtered_programs.insert(0, program)
                        logger.debug(f"添加昨天的跨天节目: {program.get('title', '未知节目')}, 开始: {start_time}, 结束: {end_time}")
                        has_current_program = True
                        current_program_index = 0
                        break
                except Exception as e:
                    logger.error(f"检查昨天节目失败: {e}")
                    continue
        
        # 如果仍然没有找到，尝试从所有节目中查找
        if not has_current_program:
            for program in epg_list:
                try:
                    start_time = datetime.fromisoformat(program.get('start', ''))
                    end_time = datetime.fromisoformat(program.get('end', ''))
                    
                    # 检查节目是否在当前时间正在播放
                    if start_time <= now <= end_time:
                        # 将这个节目添加到过滤列表的最前面
                        filtered_programs.insert(0, program)
                        logger.debug(f"添加当前播放的节目: {program.get('title', '未知节目')}, 开始: {start_time}, 结束: {end_time}")
                        has_current_program = True
                        current_program_index = 0
                        break
                except Exception as e:
                    logger.error(f"检查节目失败: {e}")
                    continue
        
        # 如果仍然没有当前时间正在播放的节目，显示一个提示
        if not has_current_program and filtered_programs:
            # 创建一个提示项
            now_str = now.strftime("%H:%M")
            item = QListWidgetItem(f"{now_str} {self.language_manager.tr('no_current_program', 'No current program')}")
            item.setForeground(QColor(255, 165, 0))  # 橙色
            # 将提示项添加到列表的最前面
            filtered_programs.insert(0, item)
            logger.info(f"添加提示项: 当前时间 {now_str} 没有正在播放的节目")
        
        # 记录排序后的节目信息，用于调试
        logger.debug(f"排序后的节目列表:")
        for i, program in enumerate(filtered_programs):
            try:
                # 检查是否是QListWidgetItem对象（提示项）
                if isinstance(program, QListWidgetItem):
                    logger.info(f"{i+1}. {program.text()}")
                else:
                    start_time = datetime.fromisoformat(program.get('start', ''))
                    end_time = datetime.fromisoformat(program.get('end', ''))
                    logger.debug(f"{i+1}. {program.get('title', '未知节目')}, 开始: {start_time}, 结束: {end_time}")
            except Exception as e:
                logger.error(f"记录节目信息失败: {e}")
        
        # 遍历排序后的节目列表
        for program in filtered_programs:
            try:
                # 检查是否是QListWidgetItem对象（提示项）
                if isinstance(program, QListWidgetItem):
                    self.epg_content.addItem(program)
                    item_index += 1
                    continue
                
                start_time = datetime.fromisoformat(program.get('start', ''))
                end_time = datetime.fromisoformat(program.get('end', ''))
                
                has_date_program = True
                
                # 格式化时间显示
                start_str = start_time.strftime("%H:%M")
                
                # 检查频道是否支持回看
                catchup = self.current_channel.get('catchup', '')
                catchup_source = self.current_channel.get('catchup_source', '')
                has_catchup = bool(catchup) and bool(catchup_source)
                
                # 创建节目项
                item_text = f"{start_str}  {program.get('title', self.language_manager.tr('unknown_program', 'Unknown Program'))}"
                item = QListWidgetItem(item_text)
                
                # 给已播放的节目添加回看图标
                if has_catchup and end_time < now:
                    # 创建一个带有回看图标的QPixmap
                    pixmap = QPixmap(20, 20)
                    pixmap.fill(QColor(0, 0, 0, 0))
                    painter = QPainter(pixmap)
                    painter.setPen(QColor(colors['player_panel_text']))
                    painter.setFont(painter.font())
                    painter.drawText(0, 0, 20, 20, 0x0004 | 0x0008, "🔄")  # 居中显示
                    painter.end()
                    
                    # 设置图标
                    item.setIcon(QIcon(pixmap))
                    item.setToolTip(self.language_manager.tr("catchup_supported", "Catchup supported"))
                
                # 设置样式
                if start_time <= now <= end_time:
                    # 当前正在播放的节目
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                    item.setForeground(QColor(colors['player_accent']))
                    current_program_index = item_index
                elif start_time > now:
                    item.setForeground(QColor(colors['player_panel_text']))
                else:
                    item.setForeground(QColor(colors['player_panel_disabled']))
                
                self.epg_content.addItem(item)
                item_index += 1
            except Exception as e:
                logger.error(f"处理节目失败: {e}")
                continue
        
        # 如果没有当前日期的节目，显示空提示
        if not has_date_program:
            self.epg_empty_label.show()
            return
        
        # 隐藏空提示
        self.epg_empty_label.hide()
        
        # 滚动到当前正在播放的节目
        if current_program_index >= 0:
            self.epg_content.setCurrentRow(current_program_index)
            self.epg_content.scrollToItem(self.epg_content.item(current_program_index))
    
    def on_epg_item_clicked(self, item):
        """EPG节目项点击事件"""
        if not self.current_channel:
            return
        
        # 检查频道是否支持回看
        catchup = self.current_channel.get('catchup', '')
        catchup_source = self.current_channel.get('catchup_source', '')
        if not (catchup and catchup_source):
            # 不支持回看，显示提示
            self.status_bar_show_message(self.language_manager.tr("catchup_not_supported", "This channel does not support catchup"))
            return
        
        # 获取当前选择的日期
        from datetime import datetime
        now = datetime.now()
        
        # 获取当前频道的节目单
        channel_name = self.current_channel.get("name", "")
        tvg_id = self.current_channel.get("tvg_id", "")
        epg_list = self.epg_parser.get_channel_epg(channel_name, tvg_id)
        
        if not epg_list:
            return
        
        # 查找被点击的节目
        item_text = item.text()
        for program in epg_list:
            try:
                start_time = datetime.fromisoformat(program.get('start', ''))
                end_time = datetime.fromisoformat(program.get('end', ''))
                
                # 检查节目是否在当前选择的日期或与当前日期相关
                # 情况1：节目完全在当前日期内
                # 情况2：跨天节目，开始时间在上一天，结束时间在今天
                # 情况3：跨天节目，开始时间在今天，结束时间在明天
                if not (start_time.date() == self.current_epg_date or end_time.date() == self.current_epg_date):
                    continue
                
                # 格式化时间显示
                start_str = start_time.strftime("%H:%M")
                program_text = f"{start_str}  {program.get('title', self.language_manager.tr('unknown_program', 'Unknown Program'))}"
                
                # 直接比较文本，因为图标不会影响文本内容
                if program_text == item_text:
                    # 检查节目是否已播放
                    if end_time < now:
                        # 已播放的节目，启动回看
                        self.start_catchup(program)
                    break
            except Exception as e:
                logger.error(f"处理节目失败: {e}")
                continue
    
    def _replace_catchup_variables(self, catchup_source, start_time, end_time):
        if not catchup_source:
            return catchup_source

        url = catchup_source

        def format_time(dt, fmt):
            # 支持时区标识符：|utc |local :utc :local
            timezone = None
            base_fmt = fmt

            if '|utc' in fmt.lower() or ':utc' in fmt.lower():
                timezone = 'utc'
                base_fmt = re.split(r'[|:]', fmt)[0]
            elif '|local' in fmt.lower() or ':local' in fmt.lower():
                timezone = 'local'
                base_fmt = re.split(r'[|:]', fmt)[0]
            
            # 根据时区选择时间对象
            target_dt = dt
            if timezone == 'utc':
                # 转换为UTC时间（减去本地时区偏移）
                import datetime as dt_module
                if dt.tzinfo is None:
                    # 本地时间转UTC
                    utc_offset = dt_module.datetime.now() - dt_module.datetime.utcnow()
                    target_dt = dt - utc_offset
                else:
                    target_dt = dt.astimezone(dt_module.timezone.utc)
            elif timezone == 'local':
                target_dt = dt
            
            fmt_map = {
                'yyyy': target_dt.strftime('%Y'),
                'yy': target_dt.strftime('%y'),
                'MM': target_dt.strftime('%m'),
                'dd': target_dt.strftime('%d'),
                'HH': target_dt.strftime('%H'),
                'mm': target_dt.strftime('%M'),
                'ss': target_dt.strftime('%S'),
                'yyyyMMddHHmmss': target_dt.strftime('%Y%m%d%H%M%S'),
                'yyyyMMddHHmm': target_dt.strftime('%Y%m%d%H%M'),
                'yyyyMMdd': target_dt.strftime('%Y%m%d'),
                'HHmmss': target_dt.strftime('%H%M%S'),
                'HHmm': target_dt.strftime('%H%M'),
                'yyyy-MM-dd': target_dt.strftime('%Y-%m-%d'),
                'yyyy-MM-ddTHH:mm:ss': target_dt.strftime('%Y-%m-%dT%H:%M:%S'),
                'yyyy-MM-dd HH:mm:ss': target_dt.strftime('%Y-%m-%d %H:%M:%S'),
                'unix': str(int(target_dt.timestamp())),
                'unix_ms': str(int(target_dt.timestamp() * 1000)),
                '10': str(int(target_dt.timestamp())),
                '13': str(int(target_dt.timestamp() * 1000)),
            }
            return fmt_map.get(base_fmt, target_dt.strftime(base_fmt))

        def replace_braced_vars(url, dt, prefix):
            for m in re.finditer(r'\$\{\(' + re.escape(prefix) + r'\)([^}]+)\}', url):
                fmt = m.group(1)
                replacement = format_time(dt, fmt)
                url = url.replace(m.group(0), replacement)
            return url

        url = replace_braced_vars(url, start_time, 'b')
        url = replace_braced_vars(url, end_time, 'e')
        url = replace_braced_vars(url, start_time, 'start')
        url = replace_braced_vars(url, end_time, 'end')

        start_ts = str(int(start_time.timestamp()))
        end_ts = str(int(end_time.timestamp()))
        start_ts_ms = str(int(start_time.timestamp() * 1000))
        end_ts_ms = str(int(end_time.timestamp() * 1000))

        url = url.replace('${start}', start_ts)
        url = url.replace('${end}', end_ts)
        url = url.replace('${timestamp}', start_ts)
        url = url.replace('${start_utc}', start_ts)
        url = url.replace('${end_utc}', end_ts)
        url = url.replace('${start_ms}', start_ts_ms)
        url = url.replace('${end_ms}', end_ts_ms)
        url = url.replace('${offset}', start_ts)
        url = url.replace('${duration}', str(int((end_time - start_time).total_seconds())))
        url = url.replace('${duration_ms}', str(int((end_time - start_time).total_seconds() * 1000)))

        url = url.replace('${start_year}', start_time.strftime('%Y'))
        url = url.replace('${start_month}', start_time.strftime('%m'))
        url = url.replace('${start_day}', start_time.strftime('%d'))
        url = url.replace('${start_hour}', start_time.strftime('%H'))
        url = url.replace('${start_minute}', start_time.strftime('%M'))
        url = url.replace('${start_second}', start_time.strftime('%S'))
        url = url.replace('${end_year}', end_time.strftime('%Y'))
        url = url.replace('${end_month}', end_time.strftime('%m'))
        url = url.replace('${end_day}', end_time.strftime('%d'))
        url = url.replace('${end_hour}', end_time.strftime('%H'))
        url = url.replace('${end_minute}', end_time.strftime('%M'))
        url = url.replace('${end_second}', end_time.strftime('%S'))

        url = url.replace('{start}', start_ts)
        url = url.replace('{end}', end_ts)
        url = url.replace('{timestamp}', start_ts)
        url = url.replace('{offset}', start_ts)

        return url

    def start_catchup(self, program):
        """启动回看功能"""
        if not self.current_channel:
            return
        
        # 获取频道信息
        channel_name = self.current_channel.get("name", self.language_manager.tr("unknown_channel", "Unknown Channel"))
        catchup_source = self.current_channel.get('catchup_source', '')
        
        # 构建回看URL
        from datetime import datetime
        start_time = datetime.fromisoformat(program.get('start', ''))
        end_time = datetime.fromisoformat(program.get('end', ''))
        title = program.get('title', self.language_manager.tr('unknown_program', 'Unknown Program'))
        
        catchup_url = catchup_source
        if catchup_source:
            catchup_url = self._replace_catchup_variables(catchup_source, start_time, end_time)
            logger.debug(f"构建回看URL: {catchup_url}")
        
        # 显示回看状态（使用format替换占位符）
        catchup_template = self.language_manager.tr('catchup_playing', '正在回看: {name}')
        self.status_bar_show_message(f"{catchup_template.format(name=channel_name)} - {title}")
        
        # 使用mpv播放回看
        if self.player_controller:
            # 保存当前频道信息，用于退出回看
            self.original_channel = self.current_channel.copy()
            # 保存当前回看的节目信息
            self.catchup_program = {
                'start': start_time,
                'end': end_time,
                'title': title,
                'desc': program.get('desc', '')
            }
            # 标记当前处于回看模式
            self.is_catchup_mode = True
            
            self._cancel_source_timeout()
            
            # 播放前隐藏背景占位符
            if hasattr(self, 'video_placeholder') and self.video_placeholder:
                self.video_placeholder.hide()
            # 确保视频窗口位置正确
            if hasattr(self, 'video_widget') and self.video_widget and self.video_frame:
                self.video_widget.setGeometry(0, 0, self.video_frame.width(), self.video_frame.height())
            # 确保悬浮窗在视频窗口之上
            if hasattr(self, 'floating_panel') and self.floating_panel:
                self.floating_panel.raise_()
            
            # 清除回看模拟相关的属性
            # 当用户从EPG选择新的回看节目时，应该清除之前的模拟状态
            if hasattr(self, '_catchup_start_time'):
                delattr(self, '_catchup_start_time')
            if hasattr(self, '_catchup_start_progress'):
                delattr(self, '_catchup_start_progress')
            if hasattr(self, '_target_catchup_progress'):
                delattr(self, '_target_catchup_progress')
            if hasattr(self, '_disable_progress_auto_update'):
                delattr(self, '_disable_progress_auto_update')
            
            # 重置进度条为0（新节目从0开始）
            if hasattr(self, 'program_progress'):
                self.program_progress.setValue(0)
                logger.debug("play_catchup: 新回看节目，重置进度条为0")
            
            # 播放回看
            self.player_controller.play(catchup_url, f"{channel_name} - {title} (回看)")
            # 添加退出回看按钮
            self.add_exit_catchup_button()
    
    def add_exit_catchup_button(self):
        """显示退出回看按钮"""
        # 显示退出回看按钮
        if hasattr(self, 'exit_catchup_button') and self.exit_catchup_button:
            try:
                self.exit_catchup_button.show()
                # 确保按钮在最上层
                self.exit_catchup_button.raise_()
                logger.debug("退出回看按钮已显示")
            except Exception as e:
                logger.error(f"显示退出回看按钮失败: {e}")
    
    def exit_catchup(self):
        """退出回看，返回直播"""
        # 隐藏退出回看按钮
        if hasattr(self, 'exit_catchup_button'):
            self.exit_catchup_button.hide()
        
        # 退出回看模式
        self.is_catchup_mode = False
        # 清除回看节目信息
        if hasattr(self, 'catchup_program'):
            delattr(self, 'catchup_program')
        
        # 重置节目单日期为今天
        from datetime import datetime, timedelta
        self.current_epg_date = datetime.now().date()
        # 更新日期显示
        if hasattr(self, 'epg_date_label'):
            today = datetime.now().date()
            if self.current_epg_date == today:
                self.epg_date_label.setText(self.language_manager.tr("today", "Today"))
            elif self.current_epg_date == today - timedelta(days=1):
                self.epg_date_label.setText(self.language_manager.tr("yesterday", "Yesterday"))
            elif self.current_epg_date == today + timedelta(days=1):
                self.epg_date_label.setText(self.language_manager.tr("tomorrow", "Tomorrow"))
            else:
                self.epg_date_label.setText(self.current_epg_date.strftime("%Y-%m-%d"))
        # 更新节目单列表
        if hasattr(self, '_populate_epg_list'):
            self._populate_epg_list()
        
        # 恢复播放原频道
        if hasattr(self, 'original_channel') and self.original_channel:
            channel_name = self.original_channel.get("name", self.language_manager.tr("unknown_channel", "Unknown Channel"))
            self.status_bar_show_message(f"{self.language_manager.tr('back_to_live', 'Back to live')}: {channel_name}")
            # 实际播放原频道（play_channel 会处理清理工作）
            self.play_channel(self.original_channel)
    
    def on_progress_slider_released(self):
        """进度条拖动释放时的处理"""
        logger.debug(f"进度条拖动释放事件触发，当前值：{self.program_progress.value()}%")
        
        # 检查是否处于回看模式
        is_catchup = hasattr(self, 'is_catchup_mode') and self.is_catchup_mode
        logger.debug(f"是否处于回看模式：{is_catchup}")
        
        if not is_catchup:
            # 直播模式下，立即更新进度条到当前时间
            from datetime import datetime
            current_time = datetime.now()
            minutes = current_time.minute
            seconds = current_time.second
            progress = int(((minutes * 60) + seconds) / 3600 * 100)
            self.program_progress.setValue(progress)
            logger.debug(f"直播模式，设置进度条到当前时间：{progress}%")
            return
        
        # 获取进度条的当前值
        value = self.program_progress.value()
        
        # 重新构建回看URL并重新播放
        has_catchup_program = hasattr(self, 'catchup_program')
        has_original_channel = hasattr(self, 'original_channel')
        logger.debug(f"检查必要属性：catchup_program={has_catchup_program}, original_channel={has_original_channel}")
        
        if has_catchup_program and has_original_channel:
            try:
                # 获取频道信息
                channel_name = self.original_channel.get("name", self.language_manager.tr("unknown_channel", "Unknown Channel"))
                catchup_source = self.original_channel.get('catchup_source', '')
                
                if not catchup_source:
                    # 不支持回看，显示提示
                    self.status_bar_show_message(self.language_manager.tr("catchup_not_supported", "This channel does not support catchup"))
                    return
                
                # 获取回看节目的信息
                start_time = self.catchup_program.get('start')
                end_time = self.catchup_program.get('end')
                title = self.catchup_program.get('title', self.language_manager.tr('unknown_program', 'Unknown Program'))
                
                if not (start_time and end_time):
                    logger.error("回看节目信息不完整")
                    self.status_bar.showMessage(self.language_manager.tr("catchup_error", "Catchup error: Missing program information"))
                    return
                
                # 计算总时长
                total_duration = (end_time - start_time).total_seconds()
                
                # 根据进度条位置计算新的开始时间
                from datetime import timedelta
                new_start_seconds = total_duration * (value / 100.0)
                new_start_time = start_time + timedelta(seconds=new_start_seconds)
                
                catchup_url = catchup_source
                catchup_url = self._replace_catchup_variables(catchup_source, new_start_time, end_time)
                
                # 记录构建的回看URL
                logger.debug(f"构建新的回看URL: {catchup_url}")
                
                # 显示回看状态
                catchup_msg = self.language_manager.tr('catchup_playing', '正在回看: {name}')
                self.status_bar.showMessage(f"{catchup_msg.format(name=channel_name)} - {title}")
                
                # 保存目标进度值，用于在播放开始后设置进度条
                self._pending_catchup_progress = value
                logger.debug(f"保存回看进度目标值：{value}%")
                
                # 记录拖动时间点（用于模拟进度条移动）
                import time
                self._catchup_start_time = time.time()
                self._catchup_start_progress = value
                logger.debug(f"记录回看开始时间：{self._catchup_start_time}，开始进度：{value}%")
                
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
        """分组切换时重新填充频道列表"""
        self.populate_channel_list()
    
    def select_channel(self, item):
        idx = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(idx, int) and 0 <= idx < len(CHANNELS):
            self.current_channel = CHANNELS[idx]
        else:
            index = self.channel_list.row(item)
            if 0 <= index < len(CHANNELS):
                self.current_channel = CHANNELS[index]
            else:
                return

        self.update_channel_info_on_selection()
        self.populate_epg_list()
        self.play_channel(self.current_channel)
    
    def update_channel_info_on_selection(self):
        """选择频道时立即更新悬浮窗信息"""
        if not self.current_channel:
            return
        
        # 更新频道名称和LOGO
        self.channel_name.setText(self.current_channel.get("name", self.language_manager.tr("unknown_channel", "Unknown Channel")))
        self.current_program.setText(f"▶ {self.language_manager.tr('preparing_play', 'Preparing to play...')}")
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
            self.channel_logo.setPixmap(QPixmap())
            self.channel_logo.setText("📺")
        else:
            # 没有 logo，显示默认图标
            self.channel_logo.setPixmap(QPixmap())
            self.channel_logo.setText("📺")
        
        # 从EPG数据获取当前节目描述（安全处理）
        try:
            channel_name = self.current_channel.get("name", "")
            if channel_name and EPG_DATA and channel_name in EPG_DATA:
                current_channel_epg = EPG_DATA[channel_name]
                if current_channel_epg and len(current_channel_epg) > 0:
                    current_program_data = current_channel_epg[0]
                    # 更新节目名称
                    program_name = current_program_data.get("title", self.language_manager.tr("now_playing", "Now Playing"))
                    self.current_program.setText(f"▶ {program_name}")
                    self.program_desc.setText(current_program_data.get("description", self.language_manager.tr("no_program_desc", "No program description")))
                    self.progress_start.setText(current_program_data.get("time", "--:--"))
                    self.time_label.setText(f"⏱ {current_program_data.get('time', '--:--')} - --:--")
                    self.remain_label.setText(self.language_manager.tr("waiting_to_play", "Waiting to play..."))
                else:
                    self.current_program.setText(f"▶ {self.language_manager.tr('now_playing', 'Now Playing')}")
                    self.program_desc.setText(self.language_manager.tr("open_playlist_success", "Playlist opened, click a channel to play"))
                    from datetime import datetime
                    current_time = datetime.now().strftime("%H:%M")
                    self.time_label.setText(f"⏱ {current_time}")
                    self.remain_label.setText(self.language_manager.tr("waiting_to_play", "Waiting to play..."))
            else:
                self.current_program.setText(f"▶ {self.language_manager.tr('now_playing', 'Now Playing')}")
                self.program_desc.setText(self.language_manager.tr("open_playlist_success", "Playlist opened, click a channel to play"))
                from datetime import datetime
                current_time = datetime.now().strftime("%H:%M")
                self.time_label.setText(f"⏱ {current_time}")
                self.remain_label.setText(self.language_manager.tr("waiting_to_play", "Waiting to play..."))
        except Exception:
            self.current_program.setText(f"▶ {self.language_manager.tr('now_playing', 'Now Playing')}")
            self.program_desc.setText(self.language_manager.tr("open_playlist_success", "Playlist opened, click a channel to play"))
            from datetime import datetime
            current_time = datetime.now().strftime("%H:%M")
            self.time_label.setText(f"⏱ {current_time}")
            self.remain_label.setText(self.language_manager.tr("waiting_to_play", "Waiting to play..."))
        
        # 重置进度条和时间（只在非回看模式下重置）
        # 检查是否处于回看模式
        is_catchup = hasattr(self, 'is_catchup_mode') and self.is_catchup_mode
        if not is_catchup:
            self.program_progress.setValue(0)
            logger.debug("update_channel_info_on_selection: 重置进度条为0（非回看模式）")
        self.progress_end.setText("--:--")
        
        # 重置第一行媒体信息为默认值
        self.video_info.setText(f"📺 {self.language_manager.tr('waiting_to_play', 'Waiting to play...')}")
        self.audio_info.setText("🔊 --")
        self.network_info.setText(f"📡 {self.language_manager.tr('waiting_connect', 'Waiting to connect...')}")
    
    def toggle_epg(self, checked):
        """显示/隐藏EPG面板"""
        self.epg_visible = checked
        self.epg_panel.setVisible(checked)
    
    def update_epg_date_display(self):
        """更新EPG日期显示"""
        from datetime import datetime, timedelta
        today = datetime.now().date()
        
        if self.current_epg_date == today:
            date_str = "今天"
        elif self.current_epg_date == today - timedelta(days=1):
            date_str = "昨天"
        elif self.current_epg_date == today + timedelta(days=1):
            date_str = "明天"
        else:
            date_str = self.current_epg_date.strftime("%m-%d")
        
        self.epg_date_label.setText(date_str)
    
    def on_prev_day(self):
        """上一天按钮点击事件"""
        from datetime import timedelta
        self.current_epg_date -= timedelta(days=1)
        self.update_epg_date_display()
        self.populate_epg_list()
    
    def on_next_day(self):
        """下一天按钮点击事件"""
        from datetime import timedelta
        self.current_epg_date += timedelta(days=1)
        self.update_epg_date_display()
        self.populate_epg_list()
    
    def toggle_playlist(self, checked):
        """显示/隐藏播放列表面板"""
        self.playlist_visible = checked
        self.playlist_panel.setVisible(checked)
    
    def toggle_floating_panel(self, checked):
        """显示/隐藏底部控制面板"""
        self.floating_panel_visible = checked
        self.floating_panel.setVisible(checked)
    
    def toggle_play(self):
        """切换播放/暂停"""
        if self.player_controller:
            self.player_controller.toggle_pause()

    def stop_playback(self):
        """停止播放，恢复到初始状态"""
        if self.player_controller:
            self.player_controller.stop()
        if hasattr(self, 'video_widget') and self.video_widget:
            self.video_widget.hide()
        if hasattr(self, 'video_placeholder') and self.video_placeholder:
            self.video_placeholder.show()
            from utils.general_utils import get_icon_path
            ico_path = get_icon_path()
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
        if hasattr(self, 'play_button'):
            self.play_button.setText("▶")
        if hasattr(self, 'channel_name'):
            tr = self.language_manager.tr
            self.channel_name.setText(tr("no_channel_selected", "No channel selected"))
        if hasattr(self, 'current_program'):
            tr = self.language_manager.tr
            self.current_program.setText(tr("select_channel_to_play", "▶ Select a channel to play"))
        if hasattr(self, 'channel_logo'):
            self.channel_logo.setPixmap(QPixmap())
            self.channel_logo.setText("📺")
        if hasattr(self, 'video_info'):
            tr = self.language_manager.tr
            self.video_info.setText(f"📺 {tr('not_playing', 'Not playing')}")
        if hasattr(self, 'audio_info'):
            self.audio_info.setText("🔊 --")
        if hasattr(self, 'network_info'):
            self.network_info.setText("📡 --")
        if hasattr(self, 'program_desc'):
            tr = self.language_manager.tr
            self.program_desc.setText(tr("open_playlist_or_import", "Open a playlist file or import channels to start watching"))
        if hasattr(self, 'time_label'):
            self.time_label.setText("⏱ --:-- - --:--")
        if hasattr(self, 'remain_label'):
            tr = self.language_manager.tr
            self.remain_label.setText(tr("waiting_to_play", "Waiting to play..."))
        if hasattr(self, 'progress_start'):
            self.progress_start.setText("--:--")
        if hasattr(self, 'progress_end'):
            self.progress_end.setText("--:--")
        if hasattr(self, 'program_progress'):
            self.program_progress.setValue(0)
        self.current_channel = None
    
    def set_volume(self, value):
        """设置音量"""
        if self.player_controller:
            self.player_controller.set_volume(value)
            # 如果不是静音状态，更新音量图标
            if not hasattr(self, '_is_muted'):
                self._is_muted = False
            if not self._is_muted:
                self._update_volume_icon(value)
    
    def toggle_mute(self):
        """切换静音/取消静音"""
        if not hasattr(self, '_is_muted'):
            self._is_muted = False
        
        if self.player_controller:
            if self._is_muted:
                # 取消静音
                self._is_muted = False
                # 恢复之前的音量
                if hasattr(self, '_pre_mute_volume'):
                    self.player_controller.set_volume(self._pre_mute_volume)
                    self.volume_slider.setValue(self._pre_mute_volume)
                    self._update_volume_icon(self._pre_mute_volume)
            else:
                # 静音
                self._is_muted = True
                # 保存当前音量
                self._pre_mute_volume = self.player_controller.get_volume()
                # 设置音量为0
                self.player_controller.set_volume(0)
                self.volume_slider.setValue(0)
                # 更新音量图标
                self.volume_button.setText("🔇")
    
    def _update_volume_icon(self, volume):
        """根据音量更新音量图标"""
        if volume == 0:
            self.volume_button.setText("🔇")
        elif volume < 50:
            self.volume_button.setText("🔉")
        else:
            self.volume_button.setText("🔊")
    
    def play_channel(self, channel):
        if self.player_controller and channel:
            # 如果当前处于回看模式，先退出回看
            if hasattr(self, 'is_catchup_mode') and self.is_catchup_mode:
                self.is_catchup_mode = False
                if hasattr(self, 'exit_catchup_button'):
                    self.exit_catchup_button.hide()
                if hasattr(self, 'catchup_program'):
                    delattr(self, 'catchup_program')
                
                # 清除回看模拟相关的属性
                if hasattr(self, '_catchup_start_time'):
                    delattr(self, '_catchup_start_time')
                if hasattr(self, '_catchup_start_progress'):
                    delattr(self, '_catchup_start_progress')
                if hasattr(self, '_target_catchup_progress'):
                    delattr(self, '_target_catchup_progress')
                if hasattr(self, '_disable_progress_auto_update'):
                    delattr(self, '_disable_progress_auto_update')
                if hasattr(self, '_pending_catchup_progress'):
                    delattr(self, '_pending_catchup_progress')
            
            # 重置节目单日期为今天（只在非回看模式下执行）
            from datetime import datetime, timedelta
            if not hasattr(self, 'is_catchup_mode') or not self.is_catchup_mode:
                self.current_epg_date = datetime.now().date()
                if hasattr(self, 'epg_date_label'):
                    today = datetime.now().date()
                    if self.current_epg_date == today:
                        self.epg_date_label.setText(self.language_manager.tr("today", "Today"))
                    elif self.current_epg_date == today - timedelta(days=1):
                        self.epg_date_label.setText(self.language_manager.tr("yesterday", "Yesterday"))
                    elif self.current_epg_date == today + timedelta(days=1):
                        self.epg_date_label.setText(self.language_manager.tr("tomorrow", "Tomorrow"))
                    else:
                        self.epg_date_label.setText(self.current_epg_date.strftime("%Y-%m-%d"))
            
            if hasattr(self, 'channel_name'):
                self.channel_name.setText(self.language_manager.tr("switching_channel", "Switching channel..."))
            if hasattr(self, 'current_program'):
                self.current_program.setText(f"▶ {self.language_manager.tr('now_playing', 'Now Playing')}")
            if hasattr(self, 'program_desc'):
                self.program_desc.setText(self.language_manager.tr("loading_program_info", "Loading program info..."))
            if hasattr(self, 'video_info'):
                self.video_info.setText(f"📺 {self.language_manager.tr('loading', 'Loading...')}")
            if hasattr(self, 'audio_info'):
                self.audio_info.setText(f"🔊 {self.language_manager.tr('loading', 'Loading...')}")
            if hasattr(self, 'network_info'):
                self.network_info.setText(f"📡 {self.language_manager.tr('loading', 'Loading...')}")
            if hasattr(self, 'progress_start'):
                self.progress_start.setText("00:00")
            if hasattr(self, 'progress_end'):
                self.progress_end.setText("00:00")
            if hasattr(self, 'time_label'):
                self.time_label.setText("⏱ 00:00")
            if hasattr(self, 'program_progress'):
                # 检查是否处于回看模式
                is_catchup = hasattr(self, 'is_catchup_mode') and self.is_catchup_mode
                if not is_catchup:
                    self.program_progress.setValue(0)
                    logger.debug("play_channel: 重置进度条为0（非回看模式）")
            
            url = channel.get('url')
            name = channel.get('name', '未知频道')
            if url:
                self.status_bar_show_message(f"{self.language_manager.tr('playing', 'Playing')}: {name}")
                if hasattr(self, 'video_placeholder') and self.video_placeholder:
                    self.video_placeholder.hide()
                if hasattr(self, 'video_widget') and self.video_widget and self.video_frame:
                    self.video_widget.setGeometry(0, 0, self.video_frame.width(), self.video_frame.height())
                if hasattr(self, 'floating_panel') and self.floating_panel:
                    self.floating_panel.raise_()
                self.current_channel = channel

                self._dns_prefetcher.prefetch(url)
                self._connection_preheater.preheat(url)

                next_urls = self._get_next_channel_urls(channel)
                if next_urls:
                    self.player_controller.play_with_prefetch(url, next_urls)
                else:
                    self.player_controller.play(url, name)

                self._start_source_timeout(channel)

                self._save_last_channel(channel)

                self._warmup_logos_around(channel)
    
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
            self._cancel_source_timeout()
            if hasattr(self, 'video_placeholder') and self.video_placeholder:
                self.video_placeholder.hide()
            if hasattr(self, 'video_widget') and self.video_widget and self.video_frame:
                self.video_widget.setGeometry(0, 0, self.video_frame.width(), self.video_frame.height())
                self.video_widget.show()
            if hasattr(self, 'epg_panel') and self.epg_panel:
                self.epg_panel.raise_()
            if hasattr(self, 'playlist_panel') and self.playlist_panel:
                self.playlist_panel.raise_()
            if hasattr(self, 'floating_panel') and self.floating_panel:
                self.floating_panel.raise_()
            self.update_media_info()
            self.update_timer.start(500)
            if self.current_channel:
                channel_name = self.current_channel.get('name', tr('unknown_channel', 'Unknown Channel'))
                if hasattr(self, 'is_catchup_mode') and self.is_catchup_mode:
                    catchup_playing_text = tr('catchup_playing', '正在回看: {name}')
                    self.status_bar.showMessage(catchup_playing_text.format(name=channel_name))
                    # 检查是否有待处理的回看进度值
                    if hasattr(self, '_pending_catchup_progress'):
                        try:
                            progress_value = self._pending_catchup_progress
                            logger.debug(f"设置回看进度条到目标值：{progress_value}%")
                            self.program_progress.setValue(progress_value)
                            
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

    def on_media_info_ready(self, media_info):
        """媒体信息获取完成时的处理 - 只显示能获取到的信息，参考 SRCBOX"""
        tr = self.language_manager.tr
        if media_info:
            video_info = media_info.get('video', {})
            audio_info = media_info.get('audio', {})
            
            # 构建视频信息标签（只显示有值的字段）
            video_parts = []
            
            # 视频编码
            video_codec = video_info.get('codec')
            if video_codec and video_codec != '未知':
                video_parts.append(f"{tr('codec_label', 'Codec')}: {video_codec}")
            
            # 分辨率
            video_width = video_info.get('width', 0)
            video_height = video_info.get('height', 0)
            if video_width > 0 and video_height > 0:
                video_parts.append(f"{tr('resolution_label', 'Resolution')}: {video_width}x{video_height}")
            
            # 帧率
            frame_rate = video_info.get('frame_rate', 0)
            if frame_rate and frame_rate > 0:
                video_parts.append(f"{tr('frame_rate_label', 'Frame Rate')}: {frame_rate:.2f}fps")
            
            # 视频码率
            video_bitrate = video_info.get('bit_rate', 0)
            if video_bitrate and video_bitrate > 0:
                if video_bitrate >= 1_000_000:
                    video_bitrate_str = f"{video_bitrate / 1_000_000:.1f}MB/s"
                elif video_bitrate >= 1000:
                    video_bitrate_str = f"{video_bitrate / 1000:.1f}KB/s"
                else:
                    video_bitrate_str = f"{video_bitrate}B/s"
                video_parts.append(f"{tr('bitrate_label', 'Bitrate')}: {video_bitrate_str}")
            
            # 像素格式
            pixel_format = video_info.get('pixel_format', '')
            if pixel_format and pixel_format != '未知':
                video_parts.append(f"{tr('pixel_format_label', 'Pixel Format')}: {pixel_format}")
            
            # 更新视频信息标签
            if video_parts:
                self.video_info.setText(f"📺 {' | '.join(video_parts)}")
            else:
                self.video_info.setText(f"📺 {tr('no_video_info', 'No video info available')}")
            
            # 构建音频信息标签（只显示有值的字段）
            audio_parts = []
            
            # 音频编码
            audio_codec = audio_info.get('codec')
            if audio_codec and audio_codec != '未知':
                audio_parts.append(f"{tr('codec_label', 'Codec')}: {audio_codec}")
            
            # 声道数
            channels = audio_info.get('channels', 0)
            if channels and channels > 0:
                audio_parts.append(f"{tr('channel_count_label', 'Channels')}: {channels}ch")
            
            # 采样率
            sample_rate = audio_info.get('sample_rate', 0)
            if sample_rate and sample_rate > 0:
                audio_parts.append(f"{tr('sample_rate_label', 'Sample Rate')}: {sample_rate}Hz")
            
            # 音频码率
            audio_bitrate = audio_info.get('bit_rate', 0)
            if audio_bitrate and audio_bitrate > 0:
                if audio_bitrate >= 1000:
                    audio_bitrate_str = f"{audio_bitrate / 1000:.1f}KB/s"
                else:
                    audio_bitrate_str = f"{audio_bitrate}B/s"
                audio_parts.append(f"{tr('bitrate_label', 'Bitrate')}: {audio_bitrate_str}")
            
            # 更新音频信息标签
            if audio_parts:
                self.audio_info.setText(f"🔊 {' | '.join(audio_parts)}")
            else:
                self.audio_info.setText(f"🔊 {tr('no_audio_info', 'No audio info available')}")
            
            # 构建网络/格式信息标签（只显示有值的字段）
            network_parts = []
            
            # 格式
            format_name = media_info.get('format')
            if format_name and format_name != '未知':
                network_parts.append(f"{tr('format_label', 'Format')}: {format_name}")
            
            # 协议
            protocol = media_info.get('protocol')
            if protocol and protocol != '未知':
                network_parts.append(f"{tr('protocol_label', 'Protocol')}: {protocol}")
            
            # 更新网络信息标签
            if network_parts:
                self.network_info.setText(f"📡 {' | '.join(network_parts)}")
            else:
                self.network_info.setText(f"📡 {tr('no_network_info', 'No network info available')}")

            # 状态栏消息
            if self.current_channel:
                channel_name = self.current_channel.get('name', tr('unknown_channel', 'Unknown Channel'))
                status_msg = f"{tr('playing', 'Playing')}: {channel_name}"
                
                # 添加可用的视频信息
                if video_codec and video_codec != '未知':
                    status_msg += f" - {video_codec}"
                if video_width > 0 and video_height > 0:
                    status_msg += f" {video_width}x{video_height}"
                if protocol and protocol != '未知':
                    status_msg += f" {protocol}"
                
                self.status_bar.showMessage(status_msg)
    
    def on_live_media_info_updated(self, info):
        """持续更新媒体信息 - 参考 SRCBOX，每 500ms 更新一次"""
        if not info:
            return
        try:
            tr = self.language_manager.tr
            
            # 保存上次的媒体信息，用于在当前信息为空时显示
            if not hasattr(self, '_last_media_info'):
                self._last_media_info = {}
            
            # 如果当前信息为空，使用上次的信息
            if info.get('width', 0) == 0 and info.get('height', 0) == 0 and not info.get('video_codec'):
                # 当前信息为空，使用上次缓存的信息
                info = self._last_media_info.copy()
                if not info:
                    return  # 没有缓存信息，不更新
            else:
                # 当前信息有效，更新缓存
                self._last_media_info = info.copy()
            
            # 构建视频信息标签（只显示有值的字段）
            video_parts = []
            
            # 硬件解码状态（优先显示）
            hw = info.get('hwdec', '')
            if hw and hw != 'no':
                video_parts.append('HW')
            
            # 视频编码（简化显示）
            video_codec = info.get('video_codec', '')
            if video_codec and video_codec != '未知':
                # 简化 codec 名称
                codec_short = self._shorten_codec_name(video_codec)
                video_parts.append(codec_short)
            
            # 音频编码（简化显示）
            audio_codec = info.get('audio_codec', '')
            if audio_codec and audio_codec != '未知':
                codec_short = self._shorten_codec_name(audio_codec)
                video_parts.append(codec_short)
            
            # 分辨率（简化显示为 FHD/QHD 等）
            video_width = info.get('width', 0)
            video_height = info.get('height', 0)
            if video_width > 0 and video_height > 0:
                res_label = self._get_resolution_label(video_width, video_height)
                video_parts.append(res_label)
            
            # 帧率
            fps = info.get('fps', 0)
            if fps and fps > 0:
                video_parts.append(f"{fps:.0f}fps")
            
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
                self.video_info.setText(f"  {'  •  '.join(video_parts)}")
            else:
                # 如果没有视频信息，显示"直播流"（对于直播流这是正常的）
                self.video_info.setText(f"  {tr('live_stream', 'Live Stream')}")
            
            # 构建音频信息标签（详细信息）
            audio_parts = []
            
            # 音频编码
            if audio_codec and audio_codec != '未知':
                audio_parts.append(f"{tr('codec_label', 'Codec')}: {audio_codec}")
            
            # 声道数
            channels = info.get('audio_channels', 0)
            if channels and channels > 0:
                audio_parts.append(f"{tr('channel_count_label', 'Channels')}: {channels}ch")
            
            # 采样率
            sample_rate = info.get('sample_rate', 0)
            if sample_rate and sample_rate > 0:
                audio_parts.append(f"{tr('sample_rate_label', 'Sample Rate')}: {sample_rate}Hz")
            
            # 音频码率
            if a_br and a_br > 0:
                if a_br >= 1000:
                    audio_bitrate_str = f"{a_br / 1000:.1f}KB/s"
                else:
                    audio_bitrate_str = f"{a_br}B/s"
                audio_parts.append(f"{tr('bitrate_label', 'Bitrate')}: {audio_bitrate_str}")
            
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
                self.network_info.setText(f"📡 {' | '.join(network_parts)}")
            else:
                self.network_info.setText(f"📡 {tr('no_network_info', 'No network info available')}")
        
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
        
        # 更新第二行：频道信息
        if self.current_channel:
            self.channel_name.setText(self.current_channel.get("name", self.language_manager.tr("unknown_channel", "Unknown Channel")))
            
            # 回看模式下，使用回看节目的信息
            if is_catchup and hasattr(self, 'catchup_program'):
                try:
                    program_name = self.catchup_program.get('title', '正在回看')
                    self.current_program.setText(f"▶ {program_name}")
                except Exception:
                    self.current_program.setText("▶ 正在回看")
            else:
                # 非回看模式，从EPG数据获取当前节目名称（安全处理）
                try:
                    channel_name = self.current_channel.get("name", "")
                    tvg_id = self.current_channel.get("tvg_id", "")
                    if channel_name:
                        # 首先尝试从EPG解析器获取节目名称（使用tvg-id和频道名称）
                        current_program = self.epg_parser.get_current_program(channel_name, tvg_id)
                        if current_program:
                            program_name = current_program.get("title", "正在播放")
                            self.current_program.setText(f"▶ {program_name}")
                        # 然后尝试从EPG_DATA获取节目名称
                        elif EPG_DATA and channel_name in EPG_DATA:
                            current_channel_epg = EPG_DATA[channel_name]
                            if current_channel_epg and len(current_channel_epg) > 0:
                                current_program_data = current_channel_epg[0]
                                program_name = current_program_data.get("title", "正在播放")
                                self.current_program.setText(f"▶ {program_name}")
                            else:
                                self.current_program.setText("▶ 正在播放")
                        else:
                            self.current_program.setText("▶ 正在播放")
                except Exception:
                    self.current_program.setText("▶ 正在播放")
        
        # 从EPG数据获取当前节目描述（安全处理）
        try:
            if self.current_channel:
                # 回看模式下，使用回看节目的信息
                if is_catchup and hasattr(self, 'catchup_program'):
                    try:
                        # 使用回看节目的信息
                        start_time = self.catchup_program.get('start')
                        end_time = self.catchup_program.get('end')
                        title = self.catchup_program.get('title', self.language_manager.tr('unknown_program', 'Unknown Program'))
                        desc = self.catchup_program.get('desc', self.language_manager.tr('no_program_desc', 'No program description'))
                        # 显示节目描述
                        self.program_desc.setText(desc)
                        # 显示节目名称
                        self.current_program.setText(f"▶ {title}")
                        if start_time and end_time:
                            start_str = start_time.strftime("%H:%M")
                            end_str = end_time.strftime("%H:%M")
                            self.time_label.setText(f"⏱ {start_str} - {end_str}")
                            self.remain_label.setText(self.language_manager.tr("catchup_playing_label", "Catching up"))
                        else:
                            self.time_label.setText("⏱ --:-- - --:--")
                            self.remain_label.setText(self.language_manager.tr("catchup_playing_label", "Catching up"))
                    except Exception as e:
                        logger.error(f"处理回看节目信息失败: {e}")
                        if hasattr(self, 'catchup_program'):
                            title = self.catchup_program.get('title', self.language_manager.tr('unknown_program', 'Unknown Program'))
                            self.current_program.setText(f"▶ {title}")
                        self.program_desc.setText(self.language_manager.tr("catchup_current_program", "Catching up current program"))
                        self.time_label.setText("⏱ --:-- - --:--")
                        self.remain_label.setText(self.language_manager.tr("catchup_playing_label", "Catching up"))
                else:
                    # 非回看模式，从EPG数据获取节目描述
                    channel_name = self.current_channel.get("name", "")
                    tvg_id = self.current_channel.get("tvg_id", "")
                    if channel_name:
                        # 首先尝试从EPG解析器获取节目描述（使用tvg-id和频道名称）
                        current_program = self.epg_parser.get_current_program(channel_name, tvg_id)
                        if current_program:
                            self.program_desc.setText(current_program.get("desc", self.language_manager.tr("no_program_desc", "No program description")))
                            # 更新时间信息
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
                        # 然后尝试从EPG_DATA获取节目描述
                        elif EPG_DATA and channel_name in EPG_DATA:
                            current_channel_epg = EPG_DATA[channel_name]
                            if current_channel_epg and len(current_channel_epg) > 0:
                                current_program_data = current_channel_epg[0]
                                self.program_desc.setText(current_program_data.get("description", self.language_manager.tr("no_program_desc", "No program description")))
                                # 更新时间信息
                                self.progress_start.setText(current_program_data.get("time", "--:--"))
                                self.time_label.setText(f"⏱ {current_program_data.get('time', '--:--')} - --:--")
                                self.remain_label.setText(self.language_manager.tr("playing_label", "Playing..."))
                            else:
                                self.program_desc.setText(self.language_manager.tr("playing_current_channel", "Playing current channel"))
                                # 显示当前系统时间
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
                                progress = int(((minutes * 60) + seconds) / 3600 * 100)
                                self.program_progress.setValue(progress)
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
                        progress = int(((minutes * 60) + seconds) / 3600 * 100)
                        self.program_progress.setValue(progress)
        except Exception:
            if is_catchup:
                self.program_desc.setText(self.language_manager.tr("catchup_current_program", "Catching up current program"))
                self.time_label.setText("⏱ --:-- - --:--")
                self.remain_label.setText(self.language_manager.tr("catchup_playing_label", "Catching up"))
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
                progress = int(((minutes * 60) + seconds) / 3600 * 100)
                self.program_progress.setValue(progress)
    
    def update_floating_panel_info(self):
        """定期更新悬浮窗信息（进度条、时间、媒体信息等）"""
        if not self.player_controller or not self.current_channel:
            return
        
        # 减少对VLC的调用频率，避免录屏时卡死
        if not hasattr(self, 'update_count'):
            self.update_count = 0
        
        # 每2次更新才获取一次播放进度，减少VLC交互
        if self.update_count % 2 == 0:
            # 更新播放进度
            current_time_ms = self.player_controller.get_current_time()
            total_time_ms = self.player_controller.get_total_time()
            position = self.player_controller.get_position()
        else:
            # 使用上次的值
            if hasattr(self, 'last_current_time_ms'):
                current_time_ms = self.last_current_time_ms
                total_time_ms = self.last_total_time_ms
                position = self.last_position
            else:
                # 第一次获取
                current_time_ms = self.player_controller.get_current_time()
                total_time_ms = self.player_controller.get_total_time()
                position = self.player_controller.get_position()
        
        # 保存当前值
        self.last_current_time_ms = current_time_ms
        self.last_total_time_ms = total_time_ms
        self.last_position = position
        
        # 增加更新计数
        self.update_count += 1
        
        # 格式化时间
        def format_time(ms):
            if ms <= 0:
                return "00:00:00"
            seconds = ms // 1000
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
        
        # 只有在非回看模式下才检查EPG
        has_epg = False
        current_program = None
        if not is_catchup:
            try:
                channel_name = self.current_channel.get("name", "")
                tvg_id = self.current_channel.get("tvg_id", "")
                if channel_name:
                    # 首先尝试从EPG解析器获取节目单（使用tvg-id和频道名称）
                    current_program = self.epg_parser.get_current_program(channel_name, tvg_id)
                    if current_program:
                        has_epg = True
                    # 然后尝试从EPG_DATA获取节目单
                    elif EPG_DATA and channel_name in EPG_DATA:
                        current_channel_epg = EPG_DATA[channel_name]
                        if current_channel_epg and len(current_channel_epg) > 0:
                            has_epg = True
            except Exception:
                pass
        
        # 更新进度条和时间显示
        if is_catchup:
            # 回看模式，使用EPG节目单的时间信息
            if hasattr(self, 'catchup_program'):
                try:
                    # 使用回看节目的时间信息
                    start_time = self.catchup_program.get('start')
                    end_time = self.catchup_program.get('end')
                    if start_time and end_time:
                        # 计算节目总时长
                        total_duration = (end_time - start_time).total_seconds()
                        
                        # 格式化时间显示
                        start_str = start_time.strftime("%H:%M")
                        end_str = end_time.strftime("%H:%M")
                        # 确保时间显示正确
                        self.progress_start.setText(start_str)
                        self.progress_end.setText(end_str)
                        # 强制更新显示
                        self.progress_start.repaint()
                        self.progress_end.repaint()
                        # 记录日志
                        logger.debug(f"回看模式 - 设置时间显示: {start_str} - {end_str}")
                        
                        # 获取当前播放位置（秒）
                        if current_time_ms is not None:
                            current_position = current_time_ms / 1000
                            logger.debug(f"回看模式 - 获取播放位置: {current_time_ms}ms = {current_position:.1f}s")
                        else:
                            current_position = 0
                            logger.warning(f"回看模式 - 播放位置为None，使用0")
                        
                        if total_duration > 0:
                            # 在回看模式下，总是使用系统时间模拟进度条移动
                            if hasattr(self, '_catchup_start_time') and hasattr(self, '_catchup_start_progress'):
                                import time
                                current_time = time.time()
                                elapsed_seconds = current_time - self._catchup_start_time
                                
                                # 计算进度：开始进度 + (经过时间 / 总时长) * 100
                                progress_increment = (elapsed_seconds / total_duration) * 100
                                progress_value = min(int(self._catchup_start_progress + progress_increment), 100)
                                
                                self.program_progress.setValue(progress_value)
                                logger.debug(f"回看进度条模拟更新: {progress_value}% (开始: {self._catchup_start_progress}%，经过: {elapsed_seconds:.1f}s，增量: {progress_increment:.2f}%)")
                            else:
                                # 如果没有开始时间记录，检查是否禁用进度条自动更新
                                if hasattr(self, '_disable_progress_auto_update') and self._disable_progress_auto_update:
                                    logger.debug(f"进度条自动更新被禁用，跳过更新")
                                    # 检查播放位置是否已经达到目标位置
                                    target_progress = getattr(self, '_target_catchup_progress', 0)
                                    target_position = total_duration * (target_progress / 100.0)
                                    logger.debug(f"检查播放位置: current={current_position:.1f}s, target={target_position:.1f}s (进度={target_progress}%)")
                                    
                                    # 如果当前播放位置已经接近目标位置，清除禁用标志
                                    if current_position >= target_position * 0.9:  # 达到目标位置的90%
                                        logger.debug(f"播放位置已达到目标位置附近，清除禁用标志")
                                        delattr(self, '_disable_progress_auto_update')
                                else:
                                    # 计算进度百分比
                                    if current_position > 0:
                                        progress_value = min(int((current_position / total_duration) * 100), 100)
                                    else:
                                        # 如果获取不到播放位置，使用0作为初始值
                                        progress_value = 0
                                    self.program_progress.setValue(progress_value)
                                    logger.debug(f"回看进度条实时更新: {progress_value}% (位置: {current_position:.1f}s / 总时长: {total_duration:.1f}s)")
                        else:
                            # 只有在非回看拖动模式下才重置为0
                            if not (hasattr(self, '_disable_progress_auto_update') and self._disable_progress_auto_update):
                                self.program_progress.setValue(0)
                                logger.debug("update_floating_panel_info: 总时长为0，重置进度条为0")
                except Exception as e:
                    logger.error(f"处理回看时间显示失败: {e}")
                    # 如果出错，使用视频播放时间
                    if total_time_ms > 0:
                        progress_value = int(position * 100)
                        self.program_progress.setValue(progress_value)
                        # 记录进度条实时变化（回看时间显示失败时）
                        logger.debug(f"回看进度条实时更新（时间显示失败）: {progress_value}% (位置: {position*100:.1f}%)")
                        self.progress_start.setText(current_time_str)
                        self.progress_end.setText(total_time_str)
                    else:
                        # 只有在非回看拖动模式下才重置为0
                        if not (hasattr(self, '_disable_progress_auto_update') and self._disable_progress_auto_update):
                            self.program_progress.setValue(0)
                            logger.debug("update_floating_panel_info: 处理回看时间显示失败，重置进度条为0")
            # 回看模式下，继续执行后面的代码，确保更新节目描述
            # 不再直接返回
        elif has_epg:
            if current_program:
                # 使用EPG节目单的时间信息
                try:
                    from datetime import datetime
                    start_time = datetime.fromisoformat(current_program.get('start', ''))
                    end_time = datetime.fromisoformat(current_program.get('end', ''))
                    now = datetime.now()
                    
                    # 计算节目总时长和当前播放位置
                    total_duration = (end_time - start_time).total_seconds()
                    current_position = (now - start_time).total_seconds()
                    
                    if total_duration > 0:
                        # 计算进度百分比
                        progress_value = int((current_position / total_duration) * 100)
                        self.program_progress.setValue(progress_value)
                        # 记录进度条实时变化（EPG模式）
                        logger.debug(f"EPG进度条实时更新: {progress_value}% (位置: {current_position:.1f}s / 总时长: {total_duration:.1f}s)")
                        
                        # 格式化时间显示
                        start_str = start_time.strftime("%H:%M")
                        end_str = end_time.strftime("%H:%M")
                        self.progress_start.setText(start_str)
                        self.progress_end.setText(end_str)
                    else:
                        # 只有在非回看模式下才重置为0
                        is_catchup = hasattr(self, 'is_catchup_mode') and self.is_catchup_mode
                        if not is_catchup:
                            self.program_progress.setValue(0)
                            logger.debug("update_floating_panel_info: EPG总时长为0，重置进度条为0")
                except:
                    # 如果EPG时间解析失败，使用视频播放时间
                    if total_time_ms > 0:
                        progress_value = int(position * 100)
                        self.program_progress.setValue(progress_value)
                        # 记录进度条实时变化（EPG时间解析失败）
                        logger.debug(f"进度条实时更新（EPG解析失败）: {progress_value}% (位置: {position*100:.1f}%)")
                        self.progress_start.setText(current_time_str)
                        self.progress_end.setText(total_time_str)
                    else:
                        # 只有在非回看模式下才重置为0
                        is_catchup = hasattr(self, 'is_catchup_mode') and self.is_catchup_mode
                        if not is_catchup:
                            self.program_progress.setValue(0)
                            logger.debug("update_floating_panel_info: EPG时间解析失败且无视频时间，重置进度条为0")
            else:
                # 使用视频播放时间
                if total_time_ms > 0:
                    progress_value = int(position * 100)
                    self.program_progress.setValue(progress_value)
                    # 记录进度条实时变化（无EPG模式）
                    logger.debug(f"进度条实时更新（无EPG）: {progress_value}% (位置: {position*100:.1f}%)")
                    self.progress_start.setText(current_time_str)
                    self.progress_end.setText(total_time_str)
                else:
                    # 只有在非回看模式下才重置为0
                    is_catchup = hasattr(self, 'is_catchup_mode') and self.is_catchup_mode
                    if not is_catchup:
                        self.program_progress.setValue(0)
                        logger.debug("update_floating_panel_info: 无EPG且无视频时间，重置进度条为0")
        else:
            # 没有节目单，使用当前系统时间和小时段
            from datetime import datetime
            current_time = datetime.now()
            start_hour = current_time.strftime("%H:00")
            end_hour = (current_time.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)).strftime("%H:00")
            self.progress_start.setText(start_hour)
            self.progress_end.setText(end_hour)
            # 更新time_label显示当前系统时间
            self.time_label.setText(f"⏱ {current_time.strftime('%H:%M')}")
            # 设置进度条
            minutes = current_time.minute
            seconds = current_time.second
            progress = int(((minutes * 60) + seconds) / 3600 * 100)
            self.program_progress.setValue(progress)
            # 记录进度条实时变化（无节目单模式）
            logger.debug(f"进度条实时更新（无节目单）: {progress}% (时间: {current_time.strftime('%H:%M:%S')})")
        
    
    def eventFilter(self, obj, event):
        """事件过滤器，处理鼠标事件"""
        if obj in (self.video_frame, self.video_widget, self.video_placeholder):
            if event.type() == event.Type.Resize:
                # 视频区域大小改变时，重新定位悬浮窗
                # 添加节流，避免频繁调用
                import time
                current_time = time.time()
                if not hasattr(self, '_last_resize_log_time'):
                    self._last_resize_log_time = 0
                if current_time - self._last_resize_log_time >= 0.1:  # 至少 100ms
                    self._last_resize_log_time = current_time
                    self.update_floating_position()
        return super().eventFilter(obj, event)
    
    def mousePressEvent(self, event):
        """处理鼠标点击事件"""
        # 当点击窗口时，显示悬浮窗
        if self.floating_panel_visible:
            self.update_floating_position()
        super().mousePressEvent(event)
    
    def update_floating_position(self):
        """更新悬浮窗位置（带日志节流）"""
        # 检查必要的属性是否存在
        if not hasattr(self, 'video_frame') or self.video_frame is None:
            return
        
        # 日志节流：最多每 1 秒记录一次
        import time
        current_time = time.time()
        
        # 检查是否需要记录日志
        should_log = False
        if not hasattr(self, '_last_update_position_log_time'):
            self._last_update_position_log_time = 0
            should_log = True
        elif current_time - self._last_update_position_log_time >= 1.0:
            self._last_update_position_log_time = current_time
            should_log = True
        
        if should_log:
            logger.debug("update_floating_position: 开始")
        
        try:
            # 更新视频窗口大小
            if hasattr(self, 'video_widget') and self.video_widget:
                self.video_widget.setGeometry(0, 0, self.video_frame.width(), self.video_frame.height())
            
            # 更新默认背景大小
            if hasattr(self, 'video_placeholder') and self.video_placeholder:
                self.video_placeholder.setGeometry(0, 0, self.video_frame.width(), self.video_frame.height())
            
            # 获取 video_frame 在屏幕上的位置
            video_frame_global_pos = self.video_frame.mapToGlobal(self.video_frame.rect().topLeft())
            
            # 更新左侧EPG面板位置和高度
            if hasattr(self, 'epg_panel') and self.epg_panel:
                self.epg_panel.setFixedHeight(self.video_frame.height() - 180)
                x = video_frame_global_pos.x() + 10
                y = video_frame_global_pos.y() + 10
                self.epg_panel.move(x, y)
                self.epg_panel.raise_()
            
            # 更新右侧播放列表面板位置和高度
            if hasattr(self, 'playlist_panel') and self.playlist_panel:
                self.playlist_panel.setFixedHeight(self.video_frame.height() - 180)
                x = video_frame_global_pos.x() + self.video_frame.width() - self.playlist_panel.width() - 10
                y = video_frame_global_pos.y() + 10
                self.playlist_panel.move(x, y)
                self.playlist_panel.raise_()
            
            # 更新底部悬浮控制面板位置
            if hasattr(self, 'floating_panel') and self.floating_panel:
                x = video_frame_global_pos.x() + (self.video_frame.width() - self.floating_panel.width()) // 2
                y = video_frame_global_pos.y() + self.video_frame.height() - self.floating_panel.height() - 20
                self.floating_panel.move(x, y)
                self.floating_panel.raise_()
        except Exception as e:
            logger.error(f"update_floating_position: 出错 - {e}")
        
        if should_log:
            logger.debug("update_floating_position: 完成")
    
    def toggle_fullscreen(self, checked=False):
        """切换全屏"""
        # 无论从哪里调用，都切换状态
        # 忽略checked参数，因为我们只是需要切换全屏状态
        self.is_fullscreen = not self.is_fullscreen
        
        if self.is_fullscreen:
            self.showFullScreen()
        else:
            self.showNormal()
    
    def refresh_ui(self):
        """刷新界面"""
        self.populate_channel_list()
        self.populate_epg_list()
    
    def reset_layout(self):
        """重置布局"""
        self.epg_visible = True
        self.playlist_visible = True
        self.floating_panel_visible = True
        self.epg_panel.setVisible(True)
        self.playlist_panel.setVisible(True)
        self.floating_panel.setVisible(True)
        self.resize(1280, 780)
    
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
    
    def player_settings(self):
        """播放器设置"""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox, QLineEdit, QGroupBox
        
        # 创建对话框
        dialog = FloatingDialog(self)
        tr = self.language_manager.tr
        dialog.setWindowTitle(tr("player_settings_title", "Player Settings"))
        dialog.setMinimumSize(400, 350)
        # 设置样式表
        dialog.setStyleSheet(AppStyles.dialog_style())
        
        # 创建布局
        main_layout = QVBoxLayout(dialog)
        
        # 回放协议类型选择
        protocol_group = QGroupBox(tr("protocol_settings", "Protocol Settings"))
        protocol_layout = QVBoxLayout()
        
        protocol_label = QLabel(tr("protocol_type_colon", "Protocol Type:"))
        self.protocol_combo = QComboBox()
        self.protocol_combo.addItems(["HTTP", "HTTPS", "RTSP", "RTMP", "HLS"])
        
        # 加载现有设置
        protocol = self.config.get_value('Player', 'protocol', 'HTTP')
        index = self.protocol_combo.findText(protocol)
        if index >= 0:
            self.protocol_combo.setCurrentIndex(index)
        
        protocol_layout.addWidget(protocol_label)
        protocol_layout.addWidget(self.protocol_combo)
        protocol_group.setLayout(protocol_layout)
        main_layout.addWidget(protocol_group)
        
        # 列表订阅设置
        playlist_group = QGroupBox(tr("playlist_subscription", "Playlist Subscription"))
        playlist_layout = QVBoxLayout()
        
        playlist_url_label = QLabel(tr("subscription_url_colon", "Subscription URL:"))
        self.playlist_url_edit = QLineEdit()
        self.playlist_url_edit.setPlaceholderText(tr("enter_playlist_url", "Enter playlist subscription URL"))
        
        playlist_name_label = QLabel(tr("subscription_name_colon", "Subscription Name:"))
        self.playlist_name_edit = QLineEdit()
        self.playlist_name_edit.setPlaceholderText(tr("enter_subscription_name", "Enter subscription name"))
        
        playlist_interval_label = QLabel(tr("update_interval_colon", "Update interval (minutes):"))
        self.playlist_interval_combo = QComboBox()
        self.playlist_interval_combo.addItems(["15", "30", "60", "120", "240", "480", "720"])
        
        # 加载现有设置
        playlist_url = self.config.get_value('Playlist', 'url', '')
        playlist_name = self.config.get_value('Playlist', 'name', '')
        playlist_interval = self.config.get_value('Playlist', 'update_interval', '60')
        self.playlist_url_edit.setText(playlist_url)
        self.playlist_name_edit.setText(playlist_name)
        index = self.playlist_interval_combo.findText(playlist_interval)
        if index >= 0:
            self.playlist_interval_combo.setCurrentIndex(index)
        
        playlist_layout.addWidget(playlist_url_label)
        playlist_layout.addWidget(self.playlist_url_edit)
        playlist_layout.addWidget(playlist_name_label)
        playlist_layout.addWidget(self.playlist_name_edit)
        playlist_layout.addWidget(playlist_interval_label)
        playlist_layout.addWidget(self.playlist_interval_combo)
        playlist_group.setLayout(playlist_layout)
        main_layout.addWidget(playlist_group)
        
        # 节目单订阅设置
        epg_group = QGroupBox(tr("epg_subscription", "EPG Subscription"))
        epg_layout = QVBoxLayout()
        
        epg_url_label = QLabel(tr("subscription_url_colon", "Subscription URL:"))
        self.epg_url_edit = QLineEdit()
        self.epg_url_edit.setPlaceholderText(tr("enter_epg_url", "Enter EPG subscription URL"))
        
        epg_name_label = QLabel(tr("subscription_name_colon", "Subscription Name:"))
        self.epg_name_edit = QLineEdit()
        self.epg_name_edit.setPlaceholderText(tr("enter_subscription_name", "Enter subscription name"))
        
        epg_interval_label = QLabel(tr("update_interval_colon", "Update interval (minutes):"))
        self.epg_interval_combo = QComboBox()
        self.epg_interval_combo.addItems(["15", "30", "60", "120", "240", "480", "720"])
        
        # 加载现有设置
        epg_url = self.config.get_value('EPG', 'epg_url', '')
        epg_name = self.config.get_value('EPG', 'epg_source', '')
        epg_interval = self.config.get_value('EPG', 'update_interval', '60')
        self.epg_url_edit.setText(epg_url)
        self.epg_name_edit.setText(epg_name)
        index = self.epg_interval_combo.findText(epg_interval)
        if index >= 0:
            self.epg_interval_combo.setCurrentIndex(index)
        
        epg_layout.addWidget(epg_url_label)
        epg_layout.addWidget(self.epg_url_edit)
        epg_layout.addWidget(epg_name_label)
        epg_layout.addWidget(self.epg_name_edit)
        epg_layout.addWidget(epg_interval_label)
        epg_layout.addWidget(self.epg_interval_combo)
        epg_group.setLayout(epg_layout)
        main_layout.addWidget(epg_group)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        save_button = QPushButton(tr("save_button", "Save"))
        cancel_button = QPushButton(tr("cancel_button", "Cancel"))
        
        save_button.clicked.connect(lambda: self.save_player_settings(dialog))
        cancel_button.clicked.connect(dialog.close)
        
        button_layout.addStretch()
        button_layout.addWidget(save_button)
        button_layout.addWidget(cancel_button)
        main_layout.addLayout(button_layout)
        
        dialog.exec()
    
    def start_subscription_timers(self):
        """检查并更新订阅内容（只在启动时检查一次）"""
        try:
            # 声明全局变量
            global EPG_DATA, CHANNELS
            
            from datetime import datetime, timedelta
            
            # 标记已经检查过订阅更新
            if hasattr(self, '_subscription_checked') and self._subscription_checked:
                return
            self._subscription_checked = True
            
            # 获取订阅设置
            playlist_url = self.config.get_value('Playlist', 'url', '')
            playlist_interval_str = self.config.get_value('Playlist', 'update_interval', '60')
            playlist_interval = int(playlist_interval_str) if playlist_interval_str else 60
            epg_url = self.config.get_value('EPG', 'epg_url', '')
            epg_interval_str = self.config.get_value('EPG', 'update_interval', '60')
            epg_interval = int(epg_interval_str) if epg_interval_str else 60
            
            # 处理列表订阅
            if playlist_url:
                # 检查是否需要立即更新
                last_update_str = self.config.get_value('Playlist', 'last_update', None)
                need_update = True
                if last_update_str:
                    try:
                        last_update = datetime.fromisoformat(last_update_str)
                        time_since_update = datetime.now() - last_update
                        if time_since_update.total_seconds() < playlist_interval * 60:
                            need_update = False
                            logger.info(f"列表订阅无需立即更新，上次更新时间: {last_update}")
                    except Exception:
                        pass
                
                # 无论是否需要更新，都在后台线程中处理
                import threading
                threading.Thread(target=self._handle_playlist_subscription, args=(need_update, playlist_url), daemon=True).start()
            
            # 处理节目单订阅
            if epg_url:
                # 无论是否需要更新，都在后台线程中处理
                import threading
                threading.Thread(target=self._handle_epg_subscription, args=(epg_url, epg_interval), daemon=True).start()
        except Exception as ex:
            logger.error(f"检查订阅内容失败: {str(ex)}")
    
    def update_playlist_subscription(self):
        """更新列表订阅 - 线程安全版本"""
        try:
            global CHANNELS

            import requests

            playlist_url = self.config.get_value('Playlist', 'url', '')
            if not playlist_url:
                return

            logger.info(f"开始更新列表订阅: {playlist_url}")

            import requests

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }

            response = requests.get(playlist_url, timeout=30, headers=headers, allow_redirects=True)
            response.raise_for_status()

            content = response.text

            if self.channel_model.load_from_file(content):
                CHANNELS = []
                for i, ch in enumerate(self.channel_model.channels):
                    CHANNELS.append({
                        "id": i + 1,
                        "name": ch.get('name', '未命名'),
                        "url": ch.get('url', ''),
                        "logo": ch.get('logo', ''),
                        "group": ch.get('group', '未分类'),
                        "tvg_id": ch.get('tvg_id', ''),
                        "tvg_chno": ch.get('tvg_chno', ''),
                        "tvg_shift": ch.get('tvg_shift', ''),
                        "catchup": ch.get('catchup', ''),
                        "catchup_days": ch.get('catchup_days', ''),
                        "catchup_source": ch.get('catchup_source', ''),
                        "resolution": ch.get('resolution', ''),
                        "current_program": ''
                    })

                from datetime import datetime
                self.config.set_value('Playlist', 'last_update', datetime.now().isoformat())
                self.config.save_config()

                import os
                cache_dir = self.config.get_value('General', 'cache_dir', 'cache')
                if cache_dir and not os.path.exists(cache_dir):
                    os.makedirs(cache_dir)

                playlist_cache_file = os.path.join(cache_dir, 'playlist_cache.m3u') if cache_dir else 'playlist_cache.m3u'
                try:
                    with open(playlist_cache_file, 'w', encoding='utf-8') as f:
                        f.write(content)
                    logger.debug(f"列表已保存到缓存文件: {playlist_cache_file}")
                except Exception as ex:
                    logger.error(f"保存列表缓存失败: {ex}")

                logger.info(f"列表订阅更新成功，共 {len(CHANNELS)} 个频道")

                if QThread.currentThread() != self.thread():
                    self._pending_update_message = self.language_manager.tr("playlist_sub_updated", "Playlist subscription updated")
                    QMetaObject.invokeMethod(self, "_do_on_playlist_updated_in_main_thread", Qt.ConnectionType.QueuedConnection)
                else:
                    self._update_channel_list_ui()
                    self.status_bar.showMessage(self.language_manager.tr("playlist_sub_updated", "Playlist subscription updated"))
            else:
                logger.error("列表订阅内容解析失败")
                if QThread.currentThread() != self.thread():
                    self._pending_status_msg = self.language_manager.tr("playlist_sub_parse_failed", "Playlist subscription parse failed")
                    QMetaObject.invokeMethod(self, "_do_show_status_message", Qt.ConnectionType.QueuedConnection)
                else:
                    self.status_bar.showMessage(self.language_manager.tr("playlist_sub_parse_failed", "Playlist subscription parse failed"))
        except Exception as ex:
            logger.error(f"更新列表订阅失败: {str(ex)}")
            if QThread.currentThread() != self.thread():
                self._pending_status_msg = f"{self.language_manager.tr('playlist_sub_update_failed', 'Failed to update playlist subscription')}: {str(ex)}"
                QMetaObject.invokeMethod(self, "_do_show_status_message", Qt.ConnectionType.QueuedConnection)
            else:
                self.status_bar.showMessage(f"{self.language_manager.tr('playlist_sub_update_failed', 'Failed to update playlist subscription')}: {str(ex)}")

    @pyqtSlot()
    def _do_on_playlist_updated_in_main_thread(self):
        """在主线程中处理订阅更新完成后的UI操作"""
        try:
            message = getattr(self, '_pending_update_message', '')
            if hasattr(self, '_pending_update_message'):
                delattr(self, '_pending_update_message')
            logger.info(f"_do_on_playlist_updated_in_main_thread: 开始更新UI, CHANNELS数量={len(CHANNELS)}")
            self._update_channel_list_ui()
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
            global EPG_DATA

            epg_url = self.config.get_value('EPG', 'epg_url', '')
            if not epg_url:
                return

            logger.info(f"开始更新节目单订阅: {epg_url}")

            from core.epg_parser import global_epg_parser

            if global_epg_parser.load_epg_from_url(epg_url):
                EPG_DATA = global_epg_parser.epg_data

                if EPG_DATA:
                    sample_channel = list(EPG_DATA.keys())[0] if EPG_DATA else None
                    if sample_channel and EPG_DATA[sample_channel]:
                        sample_date = EPG_DATA[sample_channel][0].get('start', 'N/A')
                        logger.info(f"EPG 数据样本日期: {sample_date}")

                from datetime import datetime
                self.config.set_value('EPG', 'last_update', datetime.now().isoformat())
                self.config.save_config()
                logger.info(f"节目单订阅更新成功，共 {len(EPG_DATA)} 个频道的节目单，已使用最新数据")

                if QThread.currentThread() != self.thread():
                    QMetaObject.invokeMethod(self, "_do_on_epg_success", Qt.ConnectionType.QueuedConnection)
                else:
                    self._do_on_epg_success()
            else:
                if global_epg_parser.epg_data:
                    EPG_DATA = global_epg_parser.epg_data
                    logger.debug(f"使用缓存的EPG数据，包含 {len(EPG_DATA)} 个频道")

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
            # 获取设置值
            protocol = self.protocol_combo.currentText()
            playlist_url = self.playlist_url_edit.text()
            playlist_name = self.playlist_name_edit.text()
            playlist_interval = self.playlist_interval_combo.currentText()
            epg_url = self.epg_url_edit.text()
            epg_name = self.epg_name_edit.text()
            epg_interval = self.epg_interval_combo.currentText()
            
            # 保存到配置文件
            self.config.set_value('Player', 'protocol', protocol)
            self.config.set_value('Playlist', 'url', playlist_url)
            self.config.set_value('Playlist', 'name', playlist_name)
            self.config.set_value('Playlist', 'update_interval', playlist_interval)
            self.config.set_value('EPG', 'epg_url', epg_url)
            self.config.set_value('EPG', 'epg_source', epg_name)
            self.config.set_value('EPG', 'update_interval', epg_interval)
            self.config.save_config()
            
            # 启动订阅更新定时器
            self.start_subscription_timers()
            
            logger.info("播放器设置保存成功")
            self.status_bar.showMessage(self.language_manager.tr("player_settings_saved", "Player settings saved"))
            dialog.accept()
        except Exception as ex:
            logger.error(f"保存播放器设置失败: {str(ex)}")
            self.status_bar.showMessage(f"{self.language_manager.tr('player_settings_save_failed', 'Failed to save player settings')}: {str(ex)}")
    
    def epg_settings(self):
        """EPG节目单设置"""
        from PyQt6 import QtCore, QtGui
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QDialogButtonBox
        
        # 创建自定义对话框
        dialog = FloatingDialog(self)
        tr = self.language_manager.tr
        dialog.setWindowTitle(tr("epg_settings_title", "EPG Settings"))
        dialog.setMinimumSize(400, 200)
        # 应用样式
        from ui.styles import AppStyles
        dialog.setStyleSheet(AppStyles.dialog_style())
        
        # 创建布局
        layout = QVBoxLayout(dialog)
        
        # 加载现有设置
        epg_settings = self.config.load_epg_settings()
        
        # EPG URL输入
        url_label = QLabel(tr("epg_url_colon", "EPG URL:"))
        layout.addWidget(url_label)
        url_input = QLineEdit()
        url_input.setText(epg_settings['epg_url'])
        layout.addWidget(url_input)
        
        # EPG 来源输入
        source_label = QLabel(tr("epg_source_colon", "EPG Source:"))
        layout.addWidget(source_label)
        source_input = QLineEdit()
        source_input.setText(epg_settings['epg_source'])
        layout.addWidget(source_input)
        
        # 按钮
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        layout.addWidget(button_box)
        
        # 连接信号
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        
        # 显示对话框
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # 保存设置
            epg_url = url_input.text()
            epg_source = source_input.text()
            self.config.save_epg_settings(epg_url, epg_source)
            self.status_bar.showMessage(self.language_manager.tr("epg_settings_saved", "EPG settings saved"))
    
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
                global CHANNELS
                CHANNELS = []
                for i, ch in enumerate(self.channel_model.channels):
                    CHANNELS.append({
                        "id": i + 1,
                        "name": ch.get('name', '未命名'),
                        "url": ch.get('url', ''),
                        "logo": ch.get('logo', ''),
                        "group": ch.get('group', '未分类'),
                        "tvg_id": ch.get('tvg_id', ''),
                        "tvg_chno": ch.get('tvg_chno', ''),
                        "tvg_shift": ch.get('tvg_shift', ''),
                        "catchup": ch.get('catchup', ''),
                        "catchup_days": ch.get('catchup_days', ''),
                        "catchup_source": ch.get('catchup_source', ''),
                        "resolution": ch.get('resolution', ''),
                        "current_program": ''
                    })

                from core.config_manager import ConfigManager
                config_manager = ConfigManager()
                config_manager.add_recent_file(file_path)
                self.update_recent_files_menu()

                if CHANNELS:
                    self.current_channel = CHANNELS[0]
                    self.channel_name.setText(self.current_channel.get("name", self.language_manager.tr("unknown_channel", "Unknown Channel")))

                self.populate_channel_list()
                self.status_bar.showMessage(f"{self.language_manager.tr('file_opened', 'File opened')}: {file_path}")
                logger.info(f"成功打开最近文件: {file_path}, 共 {len(CHANNELS)} 个频道")
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
        """打开播放列表"""
        from core.log_manager import global_logger as logger
        from core.config_manager import ConfigManager
        
        # 临时隐藏悬浮窗，避免遮挡文件选择对话框
        epg_visible = False
        playlist_visible = False
        floating_visible = False
        
        if hasattr(self, 'epg_panel') and self.epg_panel:
            epg_visible = self.epg_panel.isVisible()
            self.epg_panel.hide()
        
        if hasattr(self, 'playlist_panel') and self.playlist_panel:
            playlist_visible = self.playlist_panel.isVisible()
            self.playlist_panel.hide()
        
        if hasattr(self, 'floating_panel') and self.floating_panel:
            floating_visible = self.floating_panel.isVisible()
            self.floating_panel.hide()
        
        # 打开文件选择对话框
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            self.language_manager.tr("open_playlist"),
            "",
            "M3U文件 (*.m3u *.m3u8);;文本文件 (*.txt);;所有文件 (*.*)"
        )
        
        # 重新显示悬浮窗
        if hasattr(self, 'epg_panel') and self.epg_panel and epg_visible:
            self.epg_panel.show()
        
        if hasattr(self, 'playlist_panel') and self.playlist_panel and playlist_visible:
            self.playlist_panel.show()
        
        if hasattr(self, 'floating_panel') and self.floating_panel and floating_visible:
            self.floating_panel.show()
        
        if file_path:
            try:
                logger.info(f"开始打开播放列表文件: {file_path}")
                from services.m3u_parser import load_m3u_file
                content = load_m3u_file(file_path)
                logger.info(f"成功读取文件，文件大小: {len(content)} 字节")
                
                # 解析x-tvg-url属性，但优先使用手动设置的EPG地址
                import re
                first_line = content.splitlines()[0]
                if first_line.startswith('#EXTM3U'):
                    tvg_url_match = re.search(r'x-tvg-url=["\']([^"\']*)["\']', first_line)
                    if tvg_url_match:
                        tvg_url = tvg_url_match.group(1)
                        logger.info(f"从M3U文件中解析到EPG URL: {tvg_url}")
                        # 检查是否已手动设置EPG地址
                        epg_settings = self.config.load_epg_settings()
                        if not epg_settings.get('epg_url'):
                            # 如果没有手动设置EPG地址，使用M3U文件中的地址
                            self.config.save_epg_settings(tvg_url, "M3U文件")
                            # 加载EPG数据
                            import threading
                            # 定义状态回调函数
                            def epg_status_callback(message):
                                # 使用信号更新状态栏
                                self.epg_status_signal.emit(message)
                            threading.Thread(target=self.epg_parser.load_epg_from_url, args=(tvg_url, epg_status_callback), daemon=True).start()
                
                logger.info("开始解析M3U文件内容")
                if self.channel_model.load_from_file(content):
                    # 添加到最近打开文件列表
                    config_manager = ConfigManager()
                    config_manager.add_recent_file(file_path)
                    self.update_recent_files_menu()
                    
                    logger.info(f"解析成功，共解析到 {len(self.channel_model.channels)} 个频道")
                    global CHANNELS
                    CHANNELS = []
                    for i, ch in enumerate(self.channel_model.channels):
                        CHANNELS.append({
                            "id": i + 1,
                            "name": ch.get('name', '未命名'),
                            "url": ch.get('url', ''),
                            "logo": ch.get('logo', ''),
                            "group": ch.get('group', '未分类'),
                            "tvg_id": ch.get('tvg_id', ''),
                            "tvg_chno": ch.get('tvg_chno', ''),
                            "tvg_shift": ch.get('tvg_shift', ''),
                            "catchup": ch.get('catchup', ''),
                            "catchup_days": ch.get('catchup_days', ''),
                            "catchup_source": ch.get('catchup_source', ''),
                            "resolution": ch.get('resolution', ''),
                            "current_program": ''
                        })
                    logger.info(f"成功创建CHANNELS列表，包含 {len(CHANNELS)} 个频道")
                    if CHANNELS:
                        self.current_channel = CHANNELS[0]
                        self.channel_name.setText(self.current_channel.get("name", self.language_manager.tr("unknown_channel", "Unknown Channel")))
                        self.current_program.setText(f"▶ {self.language_manager.tr('select_channel_play', 'Select a channel to play')}")
                        self.program_desc.setText(self.language_manager.tr("open_playlist_success", "Playlist opened, click a channel to play"))
                        # 重置 LOGO 显示为默认图标，等待用户选择频道时加载
                        self.channel_logo.setPixmap(QPixmap())
                        self.channel_logo.setText("📺")
                    
                    logger.info("开始填充频道列表")
                    self.populate_channel_list()
                    self.status_bar.showMessage(self.language_manager.tr("channels_loaded").format(count=len(CHANNELS)))
                    logger.info(f"频道列表填充完成，显示 {len(CHANNELS)} 个频道")
                    
                    # 重新显示并提升三个悬浮窗
                    self.raise_floating_panels()
                else:
                    logger.error("M3U文件解析失败")
                    self.status_bar.showMessage(self.language_manager.tr("file_format_error"))
            except Exception as ex:
                logger.error(f"打开播放列表文件失败: {ex}")
                self.status_bar.showMessage(self.language_manager.tr("open_file_error").format(error=str(ex)))
                # 发生异常也要重新显示悬浮窗
                self.raise_floating_panels()
    
    def raise_floating_panels(self):
        """重新显示并提升三个悬浮窗到最前面"""
        # 更新位置
        self.update_floating_position()
        
        # 显示并提升三个面板
        if hasattr(self, 'epg_panel') and self.epg_panel:
            self.epg_panel.show()
            self.epg_panel.raise_()
            self.epg_panel.activateWindow()
        
        if hasattr(self, 'playlist_panel') and self.playlist_panel:
            self.playlist_panel.show()
            self.playlist_panel.raise_()
            self.playlist_panel.activateWindow()
        
        if hasattr(self, 'floating_panel') and self.floating_panel:
            self.floating_panel.show()
            self.floating_panel.raise_()
            self.floating_panel.activateWindow()
    
    def save_as(self):
        """另存为"""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            self.language_manager.tr("save_as"),
            "playlist.m3u",
            "M3U文件 (*.m3u);;M3U8文件 (*.m3u8);;文本文件 (*.txt);;所有文件 (*.*)"
        )
        
        if file_path:
            try:
                content = self.channel_model.to_m3u()
                if not content or content == "#EXTM3U":
                    if CHANNELS:
                        content = "#EXTM3U\n"
                        for ch in CHANNELS:
                            content += f'#EXTINF:-1 tvg-name="{ch["name"]}",{ch["name"]}\n{ch["url"]}\n'
                        content += f"\n# Generated by IPTV Scanner Editor Pro\n"
                        content += f"# Saved at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                
                if content:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    self.status_bar.showMessage(self.language_manager.tr("save_success"))
                else:
                    self.status_bar.showMessage(self.language_manager.tr("no_content"))
            except Exception as ex:
                self.status_bar.showMessage(self.language_manager.tr("save_error").format(error=str(ex)))
        
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
        from PyQt6 import QtCore, QtGui
        from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QTextEdit, QHBoxLayout,
                                     QPushButton, QFrame, QLabel)
        from ui.styles import AppStyles

        dialog = FloatingDialog(self)
        tr = self.language_manager.tr
        colors = AppStyles._get_colors()
        dialog.setWindowTitle(tr("usage_instructions_title", "Usage Instructions"))
        dialog.setMinimumSize(560, 520)
        dialog.setStyleSheet(AppStyles.dialog_style())

        main_layout = QVBoxLayout(dialog)
        main_layout.setContentsMargins(24, 20, 24, 16)
        main_layout.setSpacing(12)

        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)
        header_icon = QLabel("📖")
        header_icon.setStyleSheet("font-size: 28px; background-color: transparent;")
        header_icon.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        header_layout.addWidget(header_icon)
        header_title = QLabel(tr("usage_instructions_title", "Usage Instructions"))
        header_title.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {colors['accent']}; background-color: transparent;")
        header_title.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        header_layout.addWidget(header_title)
        header_layout.addStretch()
        main_layout.addLayout(header_layout)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background-color: {colors['mid']}; max-height: 1px;")
        main_layout.addWidget(sep)

        text_edit = QTextEdit()
        usage_content = tr("usage_content")
        if not usage_content:
            usage_content = '## 基本操作\n\n### 1. 打开播放列表\n- 点击"文件"菜单 → "打开播放列表"（快捷键 Ctrl+O）\n- 支持 M3U、M3U8、TXT 格式的播放列表文件\n- 支持最近打开的文件快速访问\n\n### 2. 播放频道\n- 在右侧频道列表中**双击**任意频道开始播放\n- 底部控制面板操作：\n  - **▶ 播放 / ▮▮ 暂停 / ■ 停止**：控制播放状态\n  - **🔊 音量滑块**：调节音量，点击图标静音/取消静音\n  - **倍速按钮**：循环切换播放速度（1.0x / 1.25x / 1.5x / 2.0x）\n  - **📐 比例按钮**：切换画面比例（原始/16:9/4:3/填充）\n  - **⛶ 全屏按钮**：进入/退出全屏模式（F11）\n- 键盘快捷键：空格键播放/暂停，Escape 退出全屏\n\n### 3. EPG 电子节目单\n- 左侧面板显示当前选中频道的节目安排\n- 点击 **◀ / ▶** 切换查看不同日期的节目\n- 进度条实时显示当前节目播放进度和时间轴\n- 支持配置远程 EPG 数据源自动订阅更新\n\n### 4. 扫描频道\n- 点击"工具"菜单 → "扫描频道"\n- 输入 IP 范围或流地址（如 `239.3.1.[1-100]:8000`）\n- 设置超时时间和线程数，支持追加扫描和重试\n\n### 5. 验证频道\n- 打开播放列表后可批量检测频道有效性\n- 显示检测进度、有效/无效数量及延迟等参数\n\n### 6. 频道管理\n- **拖拽排序**：在频道列表中拖动调整顺序\n- **分组筛选**：使用顶部下拉框按分组过滤频道\n- **右键菜单**：删除、复制频道名及 URL 等操作\n- **导出保存**：另存为 M3U / TXT / Excel 格式\n\n## 高级功能\n\n### 订阅设置\n- 工具菜单 → 订阅设置\n- 配置播放列表订阅 URL 和 EPG 数据源地址\n- 支持过期自动刷新和 URL 变更强制重新下载\n\n### 频道映射\n- 工具菜单 → 频道映射管理器\n- 可视化编辑频道名称、LOGO、分组的映射规则\n\n### 界面定制\n- **主题切换**：主题菜单提供 5 种主题（深色/浅色/暗蓝/新拟态/GitHub暗色）\n- **语言切换**：语言菜单支持中文/English\n- **面板控制**：视图菜单或快捷键控制各面板显隐\n  - **E** — EPG 节目单面板\n  - **L** — 频道列表面板\n  - **M** — 播放控制面板\n- **F5** 刷新界面，**F11** 全屏，**Ctrl+Q** 退出'

        html_content = self._convert_markdown_to_html(usage_content)
        text_edit.setHtml(html_content)
        text_edit.setReadOnly(True)
        text_edit.setFont(QtGui.QFont('Microsoft YaHei', 10))
        text_edit.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        text_edit.setWordWrapMode(QtGui.QTextOption.WrapMode.WordWrap)
        text_edit.setStyleSheet(f"""
            QTextEdit {{
                background-color: {colors['alternate_base']};
                color: {colors['window_text']};
                border: 1px solid {colors['mid']};
                border-radius: 8px;
                padding: 12px;
                font-size: 13px;
            }}
        """)
        main_layout.addWidget(text_edit)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        close_btn = QPushButton(tr("close_button", "Close"))
        close_btn.setFixedSize(72, 28)
        close_btn.setStyleSheet(AppStyles.button_style())
        close_btn.clicked.connect(dialog.accept)
        button_layout.addWidget(close_btn)
        main_layout.addLayout(button_layout)

        dialog.exec()
    
    def show_about(self):
        """显示关于"""
        from ui.dialogs.about_dialog import AboutDialog
        dialog = AboutDialog(self)
        dialog.exec()
    
    def set_language(self, language):
        """设置语言"""
        try:
            # 更新语言设置
            self.language_manager.set_language(language)
            # 保存语言设置到配置文件
            from core.config_manager import ConfigManager
            config_manager = ConfigManager()
            config_manager.save_language_settings(language)
            # 更新窗口标题
            from ui.dialogs.about_dialog import AboutDialog
            current_version = AboutDialog.CURRENT_VERSION
            self.setWindowTitle(f"{self.language_manager.tr('app_title', 'IPTV Scanner Editor Pro')} v{current_version}")
            # 重新创建菜单栏以更新语言
            self.menuBar().clear()
            self.setup_menu_bar()
            # 更新所有UI文本
            self.language_manager.update_ui_texts(self)
            # 更新状态栏消息
            self.status_bar.showMessage(self.language_manager.tr("language_changed"))
        except Exception as e:
            logger.error(f"切换语言失败: {str(e)}")
            self.status_bar.showMessage(self.language_manager.tr("language_change_failed", "Language change failed"))
    
    def set_theme(self, theme):
        """设置主题"""
        try:
            self._theme_manager.set_theme(theme)
            self.setStyleSheet(AppStyles.main_window_style())
            self.menuBar().clear()
            self.setup_menu_bar()
            self._reapply_all_styles()
            self.status_bar.showMessage(f"{self.language_manager.tr('theme_changed', 'Theme changed to')}: {theme}")
        except Exception as e:
            logger.error(f"切换主题失败: {str(e)}")
            self.status_bar.showMessage(self.language_manager.tr("theme_change_failed", "Theme change failed"))

    def _reapply_all_styles(self):
        try:
            colors = AppStyles._get_colors()
            self.setStyleSheet(AppStyles.main_window_style())
            self.menuBar().setStyleSheet(AppStyles.player_menu_bar_style())
            self.status_bar.setStyleSheet(AppStyles.statusbar_style())
            if hasattr(self, 'channel_table'):
                self.channel_table.setStyleSheet(AppStyles.list_style())
            if hasattr(self, 'central_widget'):
                self.central_widget.setStyleSheet(AppStyles.player_background_style())
            if hasattr(self, 'video_frame'):
                self.video_frame.setStyleSheet(AppStyles.player_background_style())
            if hasattr(self, 'video_widget'):
                self.video_widget.setStyleSheet(AppStyles.player_background_style())
            if hasattr(self, 'video_placeholder'):
                self.video_placeholder.setStyleSheet(AppStyles.player_video_placeholder_style())
            if hasattr(self, 'epg_panel'):
                self.epg_panel.setStyleSheet(AppStyles.player_panel_style())
            if hasattr(self, 'playlist_panel'):
                self.playlist_panel.setStyleSheet(AppStyles.player_panel_style())
            self._reapply_side_panel_styles()
            if hasattr(self, 'floating_panel'):
                self.floating_panel.setStyleSheet(AppStyles.player_panel_style())
                self.floating_panel.opacity = colors.get('window_opacity', 220)
                self.floating_panel.update()
                self._reapply_floating_panel_styles()
            for btn in self.findChildren(QPushButton):
                btn.setStyleSheet(AppStyles.button_style())
            for tool_btn in self.findChildren(QToolButton):
                tool_btn.setStyleSheet(AppStyles.player_button_style())
            for slider in self.findChildren(QSlider):
                slider.setStyleSheet(AppStyles.player_slider_style())
            if hasattr(self, 'volume_slider'):
                self.volume_slider.setStyleSheet(AppStyles.player_volume_slider_style())
            if hasattr(self, 'exit_catchup_button'):
                self.exit_catchup_button.setStyleSheet(AppStyles.exit_catchup_button_style())
            for combo in self.findChildren(QComboBox):
                combo.setStyleSheet(AppStyles.player_group_combo_style())
            for list_widget in self.findChildren(QListWidget):
                list_widget.setStyleSheet(AppStyles.player_list_style())
            if hasattr(self, '_scan_dialog') and self._scan_dialog:
                if hasattr(self._scan_dialog, 'reapply_styles'):
                    self._scan_dialog.reapply_styles()
        except Exception as e:
            logger.error(f"重新应用样式失败: {e}")

    def _reapply_side_panel_styles(self):
        try:
            if hasattr(self, 'epg_prev_day'):
                self.epg_prev_day.setStyleSheet(AppStyles.player_date_button_style())
            if hasattr(self, 'epg_next_day'):
                self.epg_next_day.setStyleSheet(AppStyles.player_date_button_style())
            if hasattr(self, 'epg_date_label'):
                self.epg_date_label.setStyleSheet(AppStyles.player_date_label_style())
            if hasattr(self, 'playlist_title'):
                self.playlist_title.setStyleSheet(AppStyles.player_playlist_title_style())
            if hasattr(self, 'group_combo'):
                self.group_combo.setStyleSheet(AppStyles.player_group_combo_style())
        except Exception as e:
            logger.error(f"重新应用侧边栏样式失败: {e}")

    def _reapply_floating_panel_styles(self):
        try:
            if not hasattr(self, 'floating_panel'):
                return
            fp = self.floating_panel
            if hasattr(self, 'video_info'):
                self.video_info.setStyleSheet(AppStyles.player_label_style())
            if hasattr(self, 'audio_info'):
                self.audio_info.setStyleSheet(AppStyles.player_label_style())
            if hasattr(self, 'network_info'):
                self.network_info.setStyleSheet(AppStyles.player_label_style())
            if hasattr(self, 'channel_logo'):
                self.channel_logo.setStyleSheet(AppStyles.player_channel_logo_style())
            if hasattr(self, 'channel_name'):
                self.channel_name.setStyleSheet(AppStyles.player_channel_name_style())
            if hasattr(self, 'current_program'):
                self.current_program.setStyleSheet(AppStyles.player_program_style())
            if hasattr(self, 'program_desc'):
                self.program_desc.setStyleSheet(AppStyles.player_program_desc_style())
            if hasattr(self, 'time_label'):
                self.time_label.setStyleSheet(AppStyles.player_label_style())
            if hasattr(self, 'remain_label'):
                self.remain_label.setStyleSheet(AppStyles.player_program_style())
            if hasattr(self, 'progress_start'):
                self.progress_start.setStyleSheet(AppStyles.player_progress_label_style())
            if hasattr(self, 'progress_end'):
                self.progress_end.setStyleSheet(AppStyles.player_progress_label_style())
            for btn in fp.findChildren(QPushButton):
                btn.setStyleSheet(AppStyles.player_date_button_style())
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
        """保存窗口布局（包括位置和大小）"""
        # 只有当UI初始化完成后才保存窗口布局
        if not hasattr(self, '_ui_initialized') or not self._ui_initialized:
            return
            
        try:
            # 使用 geometry() 来获取窗口的几何形状（不包括标题栏和边框）
            geometry = self.geometry()
            # 保存窗口布局（包括位置和大小）
            self.config.save_window_layout(geometry.x(), geometry.y(), geometry.width(), geometry.height(), [])
            logger.debug(f"保存窗口布局: x={geometry.x()}, y={geometry.y()}, width={geometry.width()}, height={geometry.height()}")
        except Exception as e:
            logger.error(f"保存窗口布局失败: {e}")
    
    def moveEvent(self, event):
        """主窗口移动时，更新悬浮窗口位置"""
        super().moveEvent(event)
        self.update_floating_position()
    
    def resizeEvent(self, event):
        """主窗口调整大小时，更新悬浮窗口位置"""
        super().resizeEvent(event)
        self.update_floating_position()
        
        # 使用防抖机制，避免频繁保存配置
        if self.resize_timer:
            self.resize_timer.stop()
        
        # 创建新的定时器，300毫秒后保存配置
        self.resize_timer = QTimer(self)
        self.resize_timer.setSingleShot(True)
        self.resize_timer.timeout.connect(self.save_window_layout)
        self.resize_timer.start(300)
    
    def closeEvent(self, event):
        self.save_window_layout()

        if hasattr(self, 'player_controller') and self.player_controller:
            self.player_controller.stop()

        # 关闭扫描窗口（检查两种可能的属性名以兼容）
        scan_dialog = getattr(self, '_scan_dialog', None) or getattr(self, 'scan_window', None)
        if scan_dialog:
            try:
                scan_dialog.close()
                scan_dialog.deleteLater()
            except Exception:
                pass
            self._scan_dialog = None
            self.scan_window = None

        for panel_name in ['floating_panel', 'epg_panel', 'playlist_panel']:
            panel = getattr(self, panel_name, None)
            if panel:
                panel.close()

        if hasattr(self, 'update_timer') and self.update_timer:
            self.update_timer.stop()

        if hasattr(self, '_source_timeout_timer') and self._source_timeout_timer:
            self._source_timeout_timer.stop()

        super().closeEvent(event)
    
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape and self.is_fullscreen:
            self.toggle_fullscreen(False)
        elif event.key() == Qt.Key.Key_Space:
            if hasattr(self, 'player_controller') and self.player_controller:
                self.toggle_play()
        else:
            super().keyPressEvent(event)

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
        if not self.current_channel:
            return
        logo = self.current_channel.get('logo', '')
        if logo:
            logo = logo.strip('`"\'')
            if logo == url and hasattr(self, 'channel_logo'):
                scaled = self._logo_cache_service.scale_logo_pixmap_to_fit(pixmap, self.channel_logo.width(), self.channel_logo.height())
                self.channel_logo.setPixmap(scaled)
                self.channel_logo.setText("")
        
        # 更新频道列表中的图标
        for i in range(self.channel_list.count()):
            item = self.channel_list.item(i)
            if not item:
                continue
            
            channel_idx = item.data(Qt.ItemDataRole.UserRole)
            if channel_idx is None or channel_idx >= len(CHANNELS):
                continue
            
            channel = CHANNELS[channel_idx]
            channel_logo = channel.get('logo', '')
            if channel_logo:
                channel_logo = channel_logo.strip('`"\'')
                if channel_logo == url:
                    # 获取自定义 widget 并更新台标
                    item_widget = self.channel_list.itemWidget(item)
                    if item_widget:
                        logo_label = item_widget.findChild(QtWidgets.QLabel)
                        if logo_label:
                            scaled = self._logo_cache_service.scale_logo_pixmap(pixmap, 60)
                            logo_label.setPixmap(scaled)
                    break

    def _get_next_channel_urls(self, current_channel):
        if not CHANNELS or not current_channel:
            return []
        current_idx = -1
        for i, ch in enumerate(CHANNELS):
            if ch is current_channel:
                current_idx = i
                break
        if current_idx < 0:
            return []
        next_urls = []
        for j in range(current_idx + 1, min(current_idx + 3, len(CHANNELS))):
            url = CHANNELS[j].get('url', '')
            if url:
                next_urls.append(url)
        return next_urls

    def _start_source_timeout(self, channel):
        if hasattr(self, '_source_timeout_timer') and self._source_timeout_timer:
            self._source_timeout_timer.stop()
        try:
            from core.config_manager import ConfigManager
            timeout = ConfigManager().load_playback_settings().get('source_timeout_sec', 10)
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
            for i, ch in enumerate(CHANNELS):
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
        if not CHANNELS:
            return
        idx = last.get('index', -1)
        if 0 <= idx < len(CHANNELS):
            ch = CHANNELS[idx]
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

    def _warmup_logos_around(self, channel):
        if not CHANNELS:
            return
        current_idx = -1
        for i, ch in enumerate(CHANNELS):
            if ch is channel:
                current_idx = i
                break
        if current_idx < 0:
            return
        urls = []
        for j in range(max(0, current_idx - 5), min(current_idx + 10, len(CHANNELS))):
            logo = CHANNELS[j].get('logo', '')
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
        from datetime import datetime, timedelta
        now = datetime.now()
        start_time = now - timedelta(minutes=offset_minutes)
        end_time = now

        if catchup_source:
            timeshift_url = self._replace_catchup_variables(catchup_source, start_time, end_time)
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
        self.is_catchup_mode = True
        self.catchup_program = {
            'start': start_time,
            'end': end_time,
            'title': f'时移 -{offset_minutes}分钟',
            'desc': '',
        }
        self.original_channel = self.current_channel.copy()

        if self.player_controller:
            self.player_controller.play(timeshift_url, f"{self.current_channel.get('name', '')} (时移)")
        self.add_exit_catchup_button()

    def merge_channels_from_content(self, content, mode='append'):
        from services.m3u_parser import detect_and_decode_text
        if isinstance(content, bytes):
            content = detect_and_decode_text(content)

        merge_model = ChannelListModel()
        if not merge_model.load_from_file(content):
            return False

        global CHANNELS
        new_channels = []
        for i, ch in enumerate(merge_model.channels):
            new_channels.append({
                "id": len(CHANNELS) + i + 1,
                "name": ch.get('name', '未命名'),
                "url": ch.get('url', ''),
                "logo": ch.get('logo', ''),
                "group": ch.get('group', '未分类'),
                "tvg_id": ch.get('tvg_id', ''),
                "tvg_chno": ch.get('tvg_chno', ''),
                "tvg_shift": ch.get('tvg_shift', ''),
                "catchup": ch.get('catchup', ''),
                "catchup_days": ch.get('catchup_days', ''),
                "catchup_source": ch.get('catchup_source', ''),
                "resolution": ch.get('resolution', ''),
                "current_program": ''
            })

        if mode == 'replace':
            CHANNELS = new_channels
        else:
            existing_names = {ch.get('name', '') for ch in CHANNELS}
            for ch in new_channels:
                if mode == 'append' or ch.get('name', '') not in existing_names:
                    CHANNELS.append(ch)

        self.populate_channel_list()
        return True

    _SPEED_STEPS = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0, 5.0]

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

# 主函数
if __name__ == "__main__":
    import time
    app_start_time = time.time()
    app = QApplication(sys.argv)
    player = IPTVPlayer()
    # 在显示窗口前强制处理所有待处理事件
    app.processEvents()
    player.show()
    sys.exit(app.exec())
