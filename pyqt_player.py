import sys
import os

import re
from datetime import datetime, timedelta
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QListWidget, QListWidgetItem, QStackedWidget,
    QMenuBar, QMenu, QFileDialog, QDialog, QTextEdit, QStatusBar,
    QFrame, QToolButton, QSlider, QGridLayout, QComboBox
)
from PyQt6.QtCore import Qt, QSize, QTimer, QUrl
from PyQt6.QtGui import QIcon, QPixmap, QFont, QColor, QAction, QPainter, QBrush

# 导入日志管理器
from core.log_manager import global_logger as logger

# 导入语言管理器
from core.language_manager import LanguageManager
from ui.styles import AppStyles

# 导入播放器服务
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from services.mpv_player_service import MpvPlayerController

# 频道列表（默认为空，需要用户打开播放列表文件）
CHANNELS = []

# 频道分组（从实际数据中提取，初始为空）
CHANNEL_GROUPS = ["全部频道"]

# EPG 节目单数据（初始为空字典）
EPG_DATA = {}

# 自定义半透明面板类（独立窗口）
class TranslucentPanel(QFrame):
    """支持真正半透明背景的悬浮面板（独立窗口）"""
    def __init__(self, parent=None, opacity=180):
        super().__init__(parent)
        self.opacity = opacity
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        # 设置为工具窗口，无边框
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
        # 确保面板可以接收鼠标事件
        self.setMouseTracking(True)
        # 确保面板保持活动状态
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        
    def paintEvent(self, event):
        """自定义绘制半透明背景和边框"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 创建圆角矩形路径
        from PyQt6.QtGui import QPainterPath
        from PyQt6.QtCore import QRectF
        path = QPainterPath()
        rect = QRectF(self.rect().adjusted(1, 1, -1, -1))
        path.addRoundedRect(rect, 8, 8)
        
        # 绘制半透明背景（只在圆角内）
        painter.fillPath(path, QColor(30, 30, 30, self.opacity))
        
        # 绘制边框
        painter.setPen(QColor(100, 100, 100, 150))
        painter.drawPath(path)
        
        # 调用父类的 paintEvent 来绘制子控件
        super().paintEvent(event)

# 频道列表模型
class ChannelListModel:
    def __init__(self):
        self.channels = []
        self.original_data = ""
    
    def clear(self):
        self.channels = []
        self.original_data = ""
    
    def load_from_file(self, content: str) -> bool:
        """从文件内容加载频道"""
        try:
            self.clear()
            self.original_data = content
            lines = content.splitlines()
            current_channel = None
            
            # 解析x-tvg-url属性
            if lines:
                first_line = lines[0]
                if first_line.startswith('#EXTM3U'):
                    import re
                    tvg_url_match = re.search(r'x-tvg-url=["\']([^"\']*)["\']', first_line)
                    if tvg_url_match:
                        tvg_url = tvg_url_match.group(1)
                        # 检查是否已手动设置EPG地址
                        from core.config_manager import ConfigManager
                        config = ConfigManager()
                        epg_settings = config.load_epg_settings()
                        if not epg_settings.get('epg_url'):
                            # 如果没有手动设置EPG地址，使用M3U文件中的地址
                            config.save_epg_settings(tvg_url, "M3U文件")
                            # 加载EPG数据
                            from core.epg_parser import global_epg_parser
                            import threading
                            threading.Thread(target=global_epg_parser.load_epg_from_url, args=(tvg_url,), daemon=True).start()
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                if line == "#EXTM3U":
                    continue
                
                if line.startswith("#EXTINF:"):
                    extinf_content = line[8:].strip()
                    # 查找最后一个逗号，忽略引号内的逗号
                    last_comma = -1
                    in_quotes = False
                    for i, char in enumerate(extinf_content):
                        if char == '"':
                            in_quotes = not in_quotes
                        elif char == ',' and not in_quotes:
                            last_comma = i
                    
                    if last_comma > 0:
                        attrs_part = extinf_content[:last_comma].strip()
                        name = extinf_content[last_comma+1:].strip()
                    else:
                        attrs_part = extinf_content
                        name = ""
                    
                    if name.startswith('"') and name.endswith('"'):
                        name = name[1:-1]
                    
                    current_channel = {
                        'name': name if name else '未命名',
                        'url': '',
                        'group': '未分类',
                        'logo': '',
                        'tvg_id': '',
                        'tvg_chno': '',
                        'tvg_shift': '',
                        'catchup': '',
                        'catchup_days': '',
                        'catchup_source': '',
                        'resolution': '',
                        'status': '待检测',
                        'valid': False
                    }
                    
                    # 解析属性
                    tvg_name_match = re.search(r"tvg-name=[\"']([^\"']*)[\"']", attrs_part)
                    if tvg_name_match and tvg_name_match.group(1):
                        current_channel['name'] = tvg_name_match.group(1)
                    
                    tvg_id_match = re.search(r"tvg-id=[\"']([^\"']*)[\"']", attrs_part)
                    if tvg_id_match:
                        current_channel['tvg_id'] = tvg_id_match.group(1)
                    
                    tvg_logo_match = re.search(r"tvg-logo=[\"']([^\"']*)[\"']", attrs_part)
                    if tvg_logo_match:
                        current_channel['logo'] = tvg_logo_match.group(1)
                    
                    group_match = re.search(r"group-title=[\"']([^\"']*)[\"']", attrs_part)
                    if group_match and group_match.group(1):
                        current_channel['group'] = group_match.group(1)
                    
                    tvg_chno_match = re.search(r"tvg-chno=[\"']([^\"']*)[\"']", attrs_part)
                    if tvg_chno_match:
                        current_channel['tvg_chno'] = tvg_chno_match.group(1)
                    
                    resolution_match = re.search(r"resolution=[\"']([^\"']*)[\"']", attrs_part)
                    if resolution_match:
                        current_channel['resolution'] = resolution_match.group(1)
                    
                    tvg_shift_match = re.search(r"tvg-shift=[\"']([^\"']*)[\"']", attrs_part)
                    if tvg_shift_match:
                        current_channel['tvg_shift'] = tvg_shift_match.group(1)
                    
                    catchup_match = re.search(r"catchup=[\"']([^\"']*)[\"']", attrs_part)
                    if catchup_match:
                        current_channel['catchup'] = catchup_match.group(1)
                    
                    catchup_days_match = re.search(r"catchup-days=[\"']([^\"']*)[\"']", attrs_part)
                    if catchup_days_match:
                        current_channel['catchup_days'] = catchup_days_match.group(1)
                    
                    catchup_source_match = re.search(r"catchup-source=[\"']([^\"']*)[\"']", attrs_part)
                    if catchup_source_match:
                        current_channel['catchup_source'] = catchup_source_match.group(1)
                    
                elif current_channel and line and not line.startswith("#"):
                    current_channel['url'] = line
                    self.channels.append(current_channel)
                    current_channel = None
            
            return len(self.channels) > 0
        except Exception as e:
            print(f"解析文件失败: {e}")
            return False
    
    def to_m3u(self) -> str:
        """转换为M3U格式"""
        if self.original_data:
            return self.original_data
        
        m3u_content = "#EXTM3U\n"
        for channel in self.channels:
            attrs = []
            if channel.get('tvg_id'):
                attrs.append(f"tvg-id=\"{channel['tvg_id']}\"")
            if channel.get('tvg_name'):
                attrs.append(f"tvg-name=\"{channel['tvg_name']}\"")
            if channel.get('tvg_logo'):
                attrs.append(f"tvg-logo=\"{channel['tvg_logo']}\"")
            if channel.get('group'):
                attrs.append(f"group-title=\"{channel['group']}\"")
            if channel.get('tvg_chno'):
                attrs.append(f"tvg-chno=\"{channel['tvg_chno']}\"")
            if channel.get('resolution'):
                attrs.append(f"resolution=\"{channel['resolution']}\"")
            if channel.get('tvg_shift'):
                attrs.append(f"tvg-shift=\"{channel['tvg_shift']}\"")
            if channel.get('catchup'):
                attrs.append(f"catchup=\"{channel['catchup']}\"")
            if channel.get('catchup_days'):
                attrs.append(f"catchup-days=\"{channel['catchup_days']}\"")
            if channel.get('catchup_source'):
                attrs.append(f"catchup-source=\"{channel['catchup_source']}\"")
            
            attrs_str = " " if attrs else ""
            attrs_str += " ".join(attrs)
            
            m3u_content += f"#EXTINF:-1{attrs_str},{channel.get('name', '未命名')}\n"
            m3u_content += f"{channel.get('url', '')}\n"
        
        m3u_content += f"\n# Generated by IPTV Scanner Editor Pro\n"
        m3u_content += f"# Saved at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        return m3u_content

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
        
        # 获取当前版本号并设置窗口标题
        from ui.dialogs.about_dialog import AboutDialog
        current_version = AboutDialog.CURRENT_VERSION
        self.setWindowTitle(f"IPTV Scanner Editor Pro v{current_version}")
        
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
        
        # 语言管理
        self.language_manager = LanguageManager()
        self.language_manager.load_available_languages()
        self.language_manager.set_language('zh')
        
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
        
        # LOGO 缓存
        self.logo_cache = {}
        
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
        QTimer.singleShot(1000, load_data_with_delay)
        
        # 标记UI初始化完成
        self._ui_initialized = True
        
        # 注册窗口到主题管理器
        from ui.theme_manager import get_theme_manager
        theme_manager = get_theme_manager()
        theme_manager.register_window(self)
        
        logger.debug("_initialize_in_order: 完成")
    
    def _handle_playlist_subscription(self, need_update, playlist_url):
        """在后台线程中处理列表订阅"""
        try:
            global CHANNELS
            
            if need_update:
                logger.info("列表订阅需要更新，开始下载最新数据")
                self.update_playlist_subscription()
            else:
                # 检查是否有本地缓存的列表文件
                import os
                cache_dir = self.config.get_value('General', 'cache_dir', 'cache')
                if not os.path.exists(cache_dir):
                    os.makedirs(cache_dir)
                
                playlist_cache_file = os.path.join(cache_dir, 'playlist_cache.m3u')
                
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
                            
                            logger.info(f"列表订阅无需更新，从缓存加载数据，共 {len(CHANNELS)} 个频道")
                            self.status_message.emit("从缓存加载列表数据")
                        else:
                            logger.error("缓存列表文件解析失败")
                            # 尝试直接解析内容
                            logger.info("尝试直接解析缓存内容...")
                            try:
                                # 手动解析M3U内容
                                lines = content.strip().split('\n')
                                channels = []
                                current_channel = {}
                                for line in lines:
                                    line = line.strip()
                                    if line.startswith('#EXTINF:'):
                                        # 解析频道信息
                                        parts = line.split(',', 1)
                                        if len(parts) > 1:
                                            current_channel['name'] = parts[1]
                                    elif not line.startswith('#') and line:
                                        # 解析频道URL
                                        if current_channel:
                                            current_channel['url'] = line
                                            channels.append(current_channel.copy())
                                            current_channel = {}
                                
                                if channels:
                                    logger.info(f"手动解析成功，共 {len(channels)} 个频道")
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
                                    
                                    logger.info(f"手动解析后更新列表UI，共 {len(CHANNELS)} 个频道")
                                    self.status_message.emit("手动解析后更新列表")
                                else:
                                    logger.error("手动解析也失败")
                            except Exception as ex:
                                logger.error(f"手动解析失败: {ex}")
                    except Exception as ex:
                        logger.error(f"加载缓存列表失败: {ex}")
                else:
                    logger.info("缓存文件不存在")
                    # 如果缓存文件不存在，强制更新列表
                    logger.info("缓存文件不存在，强制更新列表")
                    self.update_playlist_subscription()
        except Exception as ex:
            logger.error(f"处理列表订阅失败: {ex}")
    
    def update_channel_list_ui(self):
        """更新频道列表UI（公共方法，用于 QMetaObject.invokeMethod 调用）"""
        self._update_channel_list_ui()
    
    def _update_channel_list_ui(self):
        """更新频道列表UI"""
        try:
            self.channel_list.clear()
            for ch in CHANNELS:
                item = QListWidgetItem(ch['name'])
                item.setData(Qt.ItemDataRole.UserRole, ch)
                self.channel_list.addItem(item)
        except Exception as ex:
            logger.error(f"更新频道列表UI失败: {ex}")
    
    def status_bar_show_message(self, message):
        """在状态栏显示消息"""
        try:
            self.status_bar.showMessage(message)
        except Exception as ex:
            logger.error(f"在状态栏显示消息失败: {ex}")
    
    def _handle_epg_subscription(self, epg_url, epg_interval):
        """在后台线程中处理节目单订阅"""
        try:
            global EPG_DATA
            
            from datetime import datetime, timedelta
            
            # 检查是否需要立即更新
            last_update_str = self.config.get_value('EPG', 'last_update', None)
            need_update = True
            if last_update_str:
                try:
                    last_update = datetime.fromisoformat(last_update_str)
                    time_since_update = datetime.now() - last_update
                    if time_since_update.total_seconds() < epg_interval * 60:
                        need_update = False
                        logger.info(f"节目单订阅无需立即更新，上次更新时间: {last_update}")
                except Exception as e:
                    logger.error(f"解析EPG上次更新时间失败: {e}")
                    pass
            else:
                logger.info("未找到EPG上次更新时间，需要更新")
            
            if need_update:
                logger.info("节目单订阅需要更新，开始下载最新数据")
                self.update_epg_subscription()
            else:
                # 从缓存加载EPG数据
                from core.epg_parser import global_epg_parser
                # 加载缓存的EPG数据
                global_epg_parser.load_cached_epg_data()
                if global_epg_parser.epg_data:
                    EPG_DATA = global_epg_parser.epg_data
                    logger.info(f"节目单订阅无需更新，从缓存加载数据，共 {len(EPG_DATA)} 个频道")
                    # 更新EPG列表UI
                    self.epg_list_updated.emit()
                else:
                    # 如果缓存数据为空，强制更新
                    logger.info("EPG缓存数据为空，强制更新")
                    self.update_epg_subscription()
        except Exception as ex:
            logger.error(f"处理节目单订阅失败: {ex}")
    
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
        
        # 创建默认背景
        self.video_placeholder = QLabel("📺", self.video_frame)
        self.video_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_placeholder.setStyleSheet(AppStyles.player_video_placeholder_style())
        self.video_placeholder.show()
        
        # 创建视频播放窗口
        self.video_widget = QWidget(self.video_frame)
        self.video_widget.setStyleSheet(AppStyles.player_background_style())
        self.video_widget.show()
        
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
        self.status_bar.showMessage("就绪")
        
        # 回看相关属性
        self.is_catchup_mode = False
        self.original_channel = None
        
        logger.debug("_create_status_bar: 完成")
    
    def _init_player(self):
        """初始化播放器"""
        logger.debug("_init_player: 开始")
        
        # 初始化播放器控制器
        self.player_controller = MpvPlayerController(self.video_widget)
        self.player_controller.play_state_changed.connect(self.on_play_state_changed)
        self.player_controller.media_info_ready.connect(self.on_media_info_ready)
        
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
        
        # 左侧EPG面板
        self.epg_panel = TranslucentPanel(opacity=180)
        self.epg_panel.setStyleSheet(AppStyles.player_panel_style())
        self.epg_panel.setFixedWidth(250)
        self.epg_layout = QVBoxLayout(self.epg_panel)
        
        # EPG标题
        self.epg_title = QLabel("📅 节目单")
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
        self.epg_date_label = QLabel("今天")
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
        self.epg_content.addItem("加载中...")
        # 添加点击事件处理
        self.epg_content.itemClicked.connect(self.on_epg_item_clicked)
        self.epg_layout.addWidget(self.epg_content, 1)
        
        # EPG空提示
        self.epg_empty_label = QLabel("暂无节目信息")
        self.epg_empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.epg_empty_label.setStyleSheet(AppStyles.player_empty_label_style())
        self.epg_layout.addWidget(self.epg_empty_label)
        
        # 显示面板
        self.epg_panel.show()
        
        logger.debug("_create_epg_panel: 完成")
    
    def _create_playlist_panel(self):
        """创建播放列表面板"""
        logger.debug("_create_playlist_panel: 开始")
        
        # 右侧播放列表面板
        self.playlist_panel = TranslucentPanel(opacity=180)
        self.playlist_panel.setStyleSheet(AppStyles.player_panel_style())
        self.playlist_panel.setFixedWidth(250)
        self.playlist_layout = QVBoxLayout(self.playlist_panel)
        
        # 播放列表标题和分组选择
        self.playlist_header = QHBoxLayout()
        self.playlist_title = QLabel("📺 频道列表")
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
        self.channel_empty_label = QLabel("暂无频道")
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
        
        # 第一行：媒体信息（详细版）
        self.media_row = QHBoxLayout()
        self.media_row.setSpacing(12)
        
        self.video_info = QLabel("📺 未播放")
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
        
        self.channel_name = QLabel("未选择频道")
        self.channel_name.setStyleSheet(AppStyles.player_channel_name_style())
        name_section.addWidget(self.channel_name)
        
        self.current_program = QLabel("▶ 请选择频道开始播放")
        self.current_program.setStyleSheet(AppStyles.player_program_style())
        name_section.addWidget(self.current_program)
        
        left_section.addLayout(name_section)
        left_section.addStretch()
        self.info_row.addLayout(left_section, 2)
        
        # 中间：节目描述（直接显示内容，无标题）
        desc_section = QVBoxLayout()
        desc_section.setContentsMargins(0, 5, 0, 0)
        
        self.program_desc = QLabel("打开播放列表文件或导入频道以开始观看")
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
        
        self.remain_label = QLabel("等待播放...")
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
        self.floating_panel.show()
        
        logger.debug("_show_floating_panel: 完成")
    
    def _show_side_panels(self):
        """显示左右面板"""
        logger.debug("_show_side_panels: 开始")
        
        # 设置左右侧边栏为独立窗口（悬浮效果）
        # 左侧EPG面板悬浮
        self.epg_panel.setFixedHeight(self.video_frame.height() - 180)
        self.epg_panel.show()
        
        # 右侧播放列表面板悬浮
        self.playlist_panel.setFixedHeight(self.video_frame.height() - 180)
        self.playlist_panel.show()
        
        logger.debug("_show_side_panels: 完成")
    
    def _install_event_filters(self):
        """安装事件过滤器"""
        logger.debug("_install_event_filters: 开始")
        
        # 安装事件过滤器
        self.video_frame.installEventFilter(self)
        self.video_widget.installEventFilter(self)
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
        """填充频道列表"""
        logger.debug("_populate_channel_list: 开始")
        
        # 填充频道列表
        self.populate_channel_list()
        
        # 填充 EPG 列表
        self._populate_epg_list()
        
        logger.debug("_populate_channel_list: 完成")
    
    def populate_epg_list_ui(self):
        """填充EPG列表（公共方法，用于 QMetaObject.invokeMethod 调用）"""
        self._populate_epg_list()
    
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
        self.status_bar.showMessage(message)
        
        # 填充频道列表
        self.populate_channel_list()
        
        # 更新悬浮窗位置
        self.update_floating_position()
    
    def setup_menu_bar(self, skip_recent_files=False):
        """设置菜单栏"""
        menu_bar = self.menuBar()
        # 设置菜单栏样式
        menu_bar.setStyleSheet(AppStyles.player_menu_bar_style())
        
        try:
            # 文件菜单
            file_menu = menu_bar.addMenu("文件")
            
            open_playlist = QAction("打开列表", self)
            open_playlist.triggered.connect(self.open_playlist)
            open_playlist.setShortcut("Ctrl+O")
            file_menu.addAction(open_playlist)
            
            # 添加最近打开子菜单
            recent_menu = file_menu.addMenu("最近打开")
            
            save_as = QAction("另存...", self)
            save_as.triggered.connect(self.save_as)
            save_as.setShortcut("Ctrl+S")
            file_menu.addAction(save_as)
            
            file_menu.addSeparator()
            
            exit_action = QAction("退出", self)
            exit_action.triggered.connect(self.close)
            exit_action.setShortcut("Ctrl+Q")
            file_menu.addAction(exit_action)
            
            # 保存最近打开菜单引用
            self.recent_menu = recent_menu
            
            # 初始化最近打开文件列表（如果需要）
            if not skip_recent_files:
                self.update_recent_files_menu()
            
            # 视图菜单
            view_menu = menu_bar.addMenu("视图")
            
            show_epg = QAction("节目列表", self, checkable=True)
            show_epg.setChecked(self.epg_visible)
            show_epg.triggered.connect(self.toggle_epg)
            show_epg.setShortcut("E")
            view_menu.addAction(show_epg)
            
            show_playlist = QAction("播放列表", self, checkable=True)
            show_playlist.setChecked(self.playlist_visible)
            show_playlist.triggered.connect(self.toggle_playlist)
            show_playlist.setShortcut("L")
            view_menu.addAction(show_playlist)
            
            show_floating = QAction("控制面板", self, checkable=True)
            show_floating.setChecked(self.floating_panel_visible)
            show_floating.triggered.connect(self.toggle_floating_panel)
            show_floating.setShortcut("M")
            view_menu.addAction(show_floating)
            
            view_menu.addSeparator()
            
            fullscreen = QAction("全屏模式", self, checkable=True)
            fullscreen.triggered.connect(self.toggle_fullscreen)
            fullscreen.setShortcut("F11")
            view_menu.addAction(fullscreen)
            
            refresh = QAction("刷新界面", self)
            refresh.triggered.connect(self.refresh_ui)
            refresh.setShortcut("F5")
            view_menu.addAction(refresh)
            
            reset_layout = QAction("重置布局", self)
            reset_layout.triggered.connect(self.reset_layout)
            view_menu.addAction(reset_layout)
            
            # 工具菜单
            tools_menu = menu_bar.addMenu("工具")
            
            scan_channels = QAction("扫描频道", self)
            scan_channels.triggered.connect(self.open_scan_ui)
            tools_menu.addAction(scan_channels)
            
            channel_mapping = QAction("映射管理", self)
            channel_mapping.triggered.connect(self.open_channel_mapping)
            tools_menu.addAction(channel_mapping)
            
            tools_menu.addSeparator()
            
            player_settings = QAction("订阅设置", self)
            player_settings.triggered.connect(self.player_settings)
            tools_menu.addAction(player_settings)
            
            # 语言菜单
            language_menu = menu_bar.addMenu("语言")
            
            chinese = QAction("中文", self, checkable=True)
            chinese.setChecked(True)  # 默认中文
            chinese.triggered.connect(lambda: self.set_language("zh"))
            language_menu.addAction(chinese)
            
            english = QAction("English", self, checkable=True)
            
            # 主题菜单
            theme_menu = menu_bar.addMenu("主题")
            
            # 导入主题管理器
            from ui.theme_manager import get_theme_manager
            theme_manager = get_theme_manager()
            
            # 获取可用的主题列表
            themes = theme_manager.get_available_themes()
            
            # 为每个主题创建一个动作
            for theme in themes:
                theme_action = QAction(theme, self, checkable=True)
                theme_action.setChecked(theme == theme_manager.get_current_theme())
                theme_action.triggered.connect(lambda checked, t=theme: self.set_theme(t))
                theme_menu.addAction(theme_action)
            english.setChecked(False)
            english.triggered.connect(lambda: self.set_language("en"))
            language_menu.addAction(english)
            
            # 帮助菜单
            help_menu = menu_bar.addMenu("帮助")
            
            usage_instructions = QAction("说明", self)
            usage_instructions.triggered.connect(self.show_usage_instructions)
            help_menu.addAction(usage_instructions)
            
            about = QAction("关于", self)
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
        new_groups = ["全部频道"] + groups
        
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
            self.channel_empty_label.show()
            return
        self.channel_empty_label.hide()
        
        # 获取当前选中的分组
        selected_group = self.group_combo.currentText()
        
        for channel in CHANNELS:
            # 如果选择了特定分组，只显示该分组的频道
            if selected_group != "全部频道":
                channel_group = channel.get('group', '未分类')
                if channel_group != selected_group:
                    continue
            
            item = QListWidgetItem(channel.get("name", "未命名"))
            item.setSizeHint(QSize(0, 40))  # 增加行高
            self.channel_list.addItem(item)
    
    def populate_epg_list(self):
        """填充EPG列表"""
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
                                    'title': program_data.get('title', '未知节目'),
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
        from PyQt6.QtCore import QSize
        
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
                    # 记录节目信息，用于调试
                    logger.debug(f"添加节目: {program.get('title', '未知节目')}, 开始: {start_time}, 结束: {end_time}")
                # 检查节目是否是昨天的节目
                elif start_time.date() == self.current_epg_date - timedelta(days=1):
                    yesterday_programs.append(program)
                    # 记录节目信息，用于调试
                    logger.debug(f"添加昨天的节目: {program.get('title', '未知节目')}, 开始: {start_time}, 结束: {end_time}")
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
            item = QListWidgetItem(f"当前时间 {now_str} 没有正在播放的节目")
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
                item_text = f"{start_str}  {program.get('title', '未知节目')}"
                item = QListWidgetItem(item_text)
                
                # 给已播放的节目添加回看图标
                if has_catchup and end_time < now:
                    # 创建一个带有回看图标的QPixmap
                    pixmap = QPixmap(20, 20)
                    pixmap.fill(QColor(0, 0, 0, 0))  # 透明背景
                    painter = QPainter(pixmap)
                    painter.setPen(QColor(255, 255, 255))
                    painter.setFont(painter.font())
                    painter.drawText(0, 0, 20, 20, 0x0004 | 0x0008, "🔄")  # 居中显示
                    painter.end()
                    
                    # 设置图标
                    item.setIcon(QIcon(pixmap))
                    item.setToolTip("支持回看")
                
                # 设置样式
                if start_time <= now <= end_time:
                    # 当前正在播放的节目
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                    item.setForeground(QColor(76, 168, 232))  # #00a8e8
                    current_program_index = item_index
                elif start_time > now:
                    # 未来节目
                    item.setForeground(QColor(255, 255, 255))  # white
                else:
                    # 已播放的节目
                    item.setForeground(QColor(102, 102, 102))  # #666666
                
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
            self.status_bar.showMessage("该频道不支持回看")
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
                program_text = f"{start_str}  {program.get('title', '未知节目')}"
                
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
    
    def start_catchup(self, program):
        """启动回看功能"""
        if not self.current_channel:
            return
        
        # 获取频道信息
        channel_name = self.current_channel.get("name", "未知频道")
        catchup_source = self.current_channel.get('catchup_source', '')
        
        # 构建回看URL
        from datetime import datetime
        start_time = datetime.fromisoformat(program.get('start', ''))
        end_time = datetime.fromisoformat(program.get('end', ''))
        title = program.get('title', '未知节目')
        
        # 构建回看URL
        catchup_url = catchup_source
        if catchup_source:
            # 替换时间占位符
            catchup_url = catchup_source.replace('${(b)yyyyMMddHHmmss}', start_time.strftime('%Y%m%d%H%M%S'))
            catchup_url = catchup_url.replace('${(e)yyyyMMddHHmmss}', end_time.strftime('%Y%m%d%H%M%S'))
            # 记录构建的回看URL
            logger.debug(f"构建回看URL: {catchup_url}")
        
        # 显示回看状态
        self.status_bar.showMessage(f"正在回看: {channel_name} - {title}")
        
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
            
            # 播放前隐藏背景占位符
            if hasattr(self, 'video_placeholder'):
                self.video_placeholder.hide()
            # 确保视频窗口位置正确
            if hasattr(self, 'video_widget'):
                self.video_widget.setGeometry(0, 0, self.video_frame.width(), self.video_frame.height())
            # 确保悬浮窗在视频窗口之上
            if hasattr(self, 'floating_panel'):
                self.floating_panel.raise_()
            
            # 重置进度条
            if hasattr(self, 'program_progress'):
                self.program_progress.setValue(0)
            
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
        
        # 恢复播放原频道
        if hasattr(self, 'original_channel') and self.original_channel:
            channel_name = self.original_channel.get("name", "未知频道")
            self.status_bar.showMessage(f"返回直播: {channel_name}")
            # 实际播放原频道
            self.play_channel(self.original_channel)
    
    def on_progress_slider_released(self):
        """进度条拖动释放时的处理"""
        # 检查是否处于回看模式
        is_catchup = hasattr(self, 'is_catchup_mode') and self.is_catchup_mode
        if not is_catchup:
            # 直播模式下，立即更新进度条到当前时间
            from datetime import datetime
            current_time = datetime.now()
            minutes = current_time.minute
            seconds = current_time.second
            progress = int(((minutes * 60) + seconds) / 3600 * 100)
            self.program_progress.setValue(progress)
            return
        
        # 获取进度条的当前值
        value = self.program_progress.value()
        
        # 重新构建回看URL并重新播放
        if hasattr(self, 'catchup_program') and hasattr(self, 'original_channel'):
            try:
                # 获取频道信息
                channel_name = self.original_channel.get("name", "未知频道")
                catchup_source = self.original_channel.get('catchup_source', '')
                
                if not catchup_source:
                    return
                
                # 获取回看节目的信息
                start_time = self.catchup_program.get('start')
                end_time = self.catchup_program.get('end')
                title = self.catchup_program.get('title', '未知节目')
                
                if not (start_time and end_time):
                    return
                
                # 计算总时长
                total_duration = (end_time - start_time).total_seconds()
                
                # 根据进度条位置计算新的开始时间
                from datetime import timedelta
                new_start_seconds = total_duration * (value / 100.0)
                new_start_time = start_time + timedelta(seconds=new_start_seconds)
                
                # 构建新的回看URL
                catchup_url = catchup_source
                catchup_url = catchup_url.replace('${(b)yyyyMMddHHmmss}', new_start_time.strftime('%Y%m%d%H%M%S'))
                catchup_url = catchup_url.replace('${(e)yyyyMMddHHmmss}', end_time.strftime('%Y%m%d%H%M%S'))
                
                # 记录构建的回看URL
                logger.debug(f"构建新的回看URL: {catchup_url}")
                
                # 显示回看状态
                self.status_bar.showMessage(f"正在回看: {channel_name} - {title}")
                
                # 保存当前进度条位置
                saved_progress = value
                
                # 播放新的回看URL
                if hasattr(self, 'player_controller') and self.player_controller:
                    # 播放新的回看
                    self.player_controller.play(catchup_url, f"{channel_name} - {title} (回看)")
                    
                    # 强制设置进度条位置
                    if hasattr(self, 'program_progress'):
                        self.program_progress.setValue(saved_progress)
                        # 强制更新显示
                        self.program_progress.repaint()
            except Exception as e:
                logger.error(f"重新构建回看URL失败: {e}")
                # 如果失败，尝试使用播放器的seek方法
                if hasattr(self, 'player_controller') and self.player_controller:
                    # 计算对应的播放位置（0-1之间的浮点数）
                    position = value / 100.0
                    # 调用seek方法
                    self.player_controller.seek(position)
    
    def on_group_changed(self, group_name):
        """分组切换时重新填充频道列表"""
        self.populate_channel_list()
    
    def select_channel(self, item):
        """选择频道并播放"""
        index = self.channel_list.row(item)
        if 0 <= index < len(CHANNELS):
            self.current_channel = CHANNELS[index]
            
            # 立即更新悬浮窗信息
            self.update_channel_info_on_selection()
            
            # 更新EPG列表
            self.populate_epg_list()
            
            # 播放选中的频道
            self.play_channel(self.current_channel)
    
    def update_channel_info_on_selection(self):
        """选择频道时立即更新悬浮窗信息"""
        if not self.current_channel:
            return
        
        # 更新频道名称和LOGO
        self.channel_name.setText(self.current_channel.get("name", "未知频道"))
        self.current_program.setText("▶ 准备播放...")
        logo = self.current_channel.get("logo", "")
        
        if logo:
            # 去除 URL 中的各种引号
            logo = logo.strip('`"\'')
            
            # 检查缓存中是否已有该 LOGO
            if logo in self.logo_cache:
                pixmap = self.logo_cache[logo]
                # 缩放图片以适应 QLabel 大小
                scaled_pixmap = pixmap.scaled(self.channel_logo.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                self.channel_logo.setPixmap(scaled_pixmap)
                self.channel_logo.setText("")  # 清除文本
                return
            
            # 使用 QNetworkAccessManager 加载网络图片
            from PyQt6.QtGui import QPixmap
            from PyQt6.QtCore import QUrl, QByteArray
            from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
            
            # 创建网络管理器（作为实例属性，避免被垃圾回收）
            if not hasattr(self, 'logo_manager'):
                self.logo_manager = QNetworkAccessManager()
            
            def on_logo_loaded(reply):
                if reply.error() == QNetworkReply.NetworkError.NoError:
                    data = reply.readAll()
                    pixmap = QPixmap()
                    if pixmap.loadFromData(data):
                        # 缓存 LOGO
                        self.logo_cache[logo] = pixmap
                        # 缩放图片以适应 QLabel 大小
                        scaled_pixmap = pixmap.scaled(self.channel_logo.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                        self.channel_logo.setPixmap(scaled_pixmap)
                        self.channel_logo.setText("")  # 清除文本
                    else:
                        # 加载失败，显示默认图标
                        self.channel_logo.setPixmap(QPixmap())
                        self.channel_logo.setText("📺")
                else:
                    # 加载失败，显示默认图标
                    self.channel_logo.setPixmap(QPixmap())
                    self.channel_logo.setText("📺")
                reply.deleteLater()
            
            # 断开之前的信号连接，避免重复回调
            try:
                self.logo_manager.finished.disconnect()
            except:
                pass
            
            # 连接信号
            self.logo_manager.finished.connect(on_logo_loaded)
            
            # 发送请求
            request = QNetworkRequest(QUrl(logo))
            self.logo_manager.get(request)
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
                    program_name = current_program_data.get("title", "正在播放")
                    self.current_program.setText(f"▶ {program_name}")
                    # 更新节目描述
                    self.program_desc.setText(current_program_data.get("description", "暂无节目描述"))
                    # 更新时间信息
                    self.progress_start.setText(current_program_data.get("time", "--:--"))
                    self.time_label.setText(f"⏱ {current_program_data.get('time', '--:--')} - --:--")
                    self.remain_label.setText("等待播放...")
                else:
                    # 没有节目单，显示默认信息
                    self.current_program.setText("▶ 正在播放")
                    self.program_desc.setText("打开播放列表文件成功，点击频道开始播放")
                    # 显示当前系统时间
                    from datetime import datetime
                    current_time = datetime.now().strftime("%H:%M")
                    self.time_label.setText(f"⏱ {current_time}")
                    self.remain_label.setText("等待播放...")
            else:
                # 没有节目单，显示默认信息
                self.current_program.setText("▶ 正在播放")
                self.program_desc.setText("打开播放列表文件成功，点击频道开始播放")
                # 显示当前系统时间
                from datetime import datetime
                current_time = datetime.now().strftime("%H:%M")
                self.time_label.setText(f"⏱ {current_time}")
                self.remain_label.setText("等待播放...")
        except Exception:
            # 发生异常，显示默认信息
            self.current_program.setText("▶ 正在播放")
            self.program_desc.setText("打开播放列表文件成功，点击频道开始播放")
            # 显示当前系统时间
            from datetime import datetime
            current_time = datetime.now().strftime("%H:%M")
            self.time_label.setText(f"⏱ {current_time}")
            self.remain_label.setText("等待播放...")
        
        # 重置进度条和时间
        self.program_progress.setValue(0)
        self.progress_end.setText("--:--")
        
        # 重置第一行媒体信息为默认值
        self.video_info.setText("📺 等待播放...")
        self.audio_info.setText("🔊 --")
        self.network_info.setText("📡 等待连接...")
    
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
        print("toggle_play 被调用")
        if self.player_controller:
            print(f"player_controller 存在: {self.player_controller}")
            self.player_controller.toggle_pause()
        else:
            print("player_controller 不存在")
    
    def set_volume(self, value):
        """设置音量"""
        if self.player_controller:
            self.player_controller.set_volume(value)
            # 如果不是静音状态，更新音量图标
            if hasattr(self, '_is_muted') and not self._is_muted:
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
        """播放指定频道"""
        if self.player_controller and channel:
            # 退出回看模式
            if hasattr(self, 'is_catchup_mode') and self.is_catchup_mode:
                self.is_catchup_mode = False
                # 隐藏退出回看按钮
                if hasattr(self, 'exit_catchup_button'):
                    self.exit_catchup_button.hide()
                # 清除回看节目信息
                if hasattr(self, 'catchup_program'):
                    delattr(self, 'catchup_program')
            
            # 切换频道时清空之前的频道信息
            if hasattr(self, 'channel_name'):
                self.channel_name.setText("切换频道中...")
            if hasattr(self, 'current_program'):
                self.current_program.setText("▶ 正在播放")
            if hasattr(self, 'program_desc'):
                self.program_desc.setText("正在加载节目信息...")
            if hasattr(self, 'media_info'):
                self.media_info.setText("📺 加载中...")
            if hasattr(self, 'video_info'):
                self.video_info.setText("📺 加载中...")
            if hasattr(self, 'audio_info'):
                self.audio_info.setText("🔊 加载中...")
            if hasattr(self, 'network_info'):
                self.network_info.setText("📡 加载中...")
            if hasattr(self, 'progress_start'):
                self.progress_start.setText("00:00")
            if hasattr(self, 'progress_end'):
                self.progress_end.setText("00:00")
            if hasattr(self, 'time_label'):
                self.time_label.setText("⏱ 00:00")
            if hasattr(self, 'program_progress'):
                self.program_progress.setValue(0)
            
            url = channel.get('url')
            name = channel.get('name', '未知频道')
            if url:
                # 更新状态栏消息
                self.status_bar.showMessage(f"正在播放: {name}")
                # 播放前隐藏背景占位符
                if hasattr(self, 'video_placeholder'):
                    self.video_placeholder.hide()
                # 确保视频窗口位置正确
                if hasattr(self, 'video_widget'):
                    self.video_widget.setGeometry(0, 0, self.video_frame.width(), self.video_frame.height())
                # 确保悬浮窗在视频窗口之上
                if hasattr(self, 'floating_panel'):
                    self.floating_panel.raise_()
                # 更新当前频道
                self.current_channel = channel
                # 播放频道
                self.player_controller.play(url, name)
    
    def on_play_state_changed(self, is_playing):
        """播放状态改变时的处理"""
        # 确保在主线程中执行
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0, lambda: self._handle_play_state_change(is_playing))
    
    def _handle_play_state_change(self, is_playing):
        """处理播放状态改变（在主线程中执行）"""
        if is_playing:
            self.play_button.setText("⏸")
            # 播放时隐藏背景，显示视频窗口
            if hasattr(self, 'video_placeholder'):
                self.video_placeholder.hide()
            if hasattr(self, 'video_widget'):
                self.video_widget.setGeometry(0, 0, self.video_frame.width(), self.video_frame.height())
                self.video_widget.show()
            # 确保悬浮控件在视频窗口之上
            if hasattr(self, 'epg_panel'):
                self.epg_panel.raise_()
            if hasattr(self, 'playlist_panel'):
                self.playlist_panel.raise_()
            if hasattr(self, 'floating_panel'):
                self.floating_panel.raise_()
            # 更新媒体信息
            self.update_media_info()
            # 启动定时器，每500ms更新一次（减少频率，避免卡顿）
            self.update_timer.start(500)
            # 暂时禁用自动调整窗口大小，避免程序卡死
            # self.adjust_window_size_to_video()
            # 更新状态栏消息
            if self.current_channel:
                channel_name = self.current_channel.get('name', '未知频道')
                if hasattr(self, 'is_catchup_mode') and self.is_catchup_mode:
                    self.status_bar.showMessage(f"正在回看: {channel_name}")
                else:
                    self.status_bar.showMessage(f"正在播放: {channel_name}")
        else:
            self.play_button.setText("▶")
            # 暂停时不要显示背景占位符，保持视频窗口可见
            # 停止定时器
            if hasattr(self, 'update_timer'):
                self.update_timer.stop()
            # 更新状态栏消息
            if self.current_channel:
                channel_name = self.current_channel.get('name', '未知频道')
                if hasattr(self, 'is_catchup_mode') and self.is_catchup_mode:
                    self.status_bar.showMessage(f"已暂停回看: {channel_name}")
                else:
                    self.status_bar.showMessage(f"已暂停: {channel_name}")
    
    def on_media_info_ready(self, media_info):
        """媒体信息获取完成时的处理"""
        # 更新媒体信息显示
        if media_info:
            # 更新视频信息
            video_info = media_info.get('video', {})
            video_codec = video_info.get('codec', '未知')
            video_width = video_info.get('width', 0)
            video_height = video_info.get('height', 0)
            video_resolution = f"{video_width}x{video_height}" if video_width and video_height else "未知"
            video_bitrate = video_info.get('bit_rate', 0)
            video_bitrate_str = f"{video_bitrate // 1000}kbps" if video_bitrate else "未知"
            
            # 更新音频信息
            audio_info = media_info.get('audio', {})
            audio_codec = audio_info.get('codec', '未知')
            channels = audio_info.get('channels', 0)
            sample_rate = audio_info.get('sample_rate', 0)
            audio_bitrate = audio_info.get('bit_rate', 0)
            audio_bitrate_str = f"{audio_bitrate // 1000}kbps" if audio_bitrate else "未知"
            
            # 更新网络信息
            format_name = media_info.get('format', '未知')
            protocol = media_info.get('protocol', '未知')
            
            # 更新显示
            if hasattr(self, 'media_info'):
                self.media_info.setText(f"📺 媒体信息")
            # 修复码率显示，确保即使码率为0也能正确显示
            video_bitrate_str = f"{video_bitrate // 1000}kbps" if video_bitrate is not None and video_bitrate >= 0 else "未知"
            audio_bitrate_str = f"{audio_bitrate // 1000}kbps" if audio_bitrate is not None and audio_bitrate >= 0 else "未知"
            self.video_info.setText(f"📺 编码: {video_codec} | 分辨率: {video_resolution} | 码率: {video_bitrate_str}")
            self.audio_info.setText(f"🔊 编码: {audio_codec} | 声道: {channels}ch | 采样率: {sample_rate}Hz | 码率: {audio_bitrate_str}")
            self.network_info.setText(f"📡 格式: {format_name} | 协议: {protocol}")
            
            # 更新状态栏消息
            if self.current_channel:
                channel_name = self.current_channel.get('name', '未知频道')
                self.status_bar.showMessage(f"正在播放: {channel_name} - {video_codec} {video_resolution} {protocol}")
    
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
            
            print(f"DEBUG: setting geometry to {new_window_width}x{current_height}")
            self.setGeometry(new_x, new_y, new_window_width, current_height)
            
        except Exception as e:
            print(f"DEBUG: exception = {e}")
    
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
            self.channel_name.setText(self.current_channel.get("name", "未知频道"))
            
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
                        title = self.catchup_program.get('title', '未知节目')
                        desc = self.catchup_program.get('desc', '暂无节目描述')
                        # 显示节目描述
                        self.program_desc.setText(desc)
                        # 显示节目名称
                        self.current_program.setText(f"▶ {title}")
                        if start_time and end_time:
                            start_str = start_time.strftime("%H:%M")
                            end_str = end_time.strftime("%H:%M")
                            self.time_label.setText(f"⏱ {start_str} - {end_str}")
                            self.remain_label.setText("回看中...")
                        else:
                            self.time_label.setText("⏱ --:-- - --:--")
                            self.remain_label.setText("回看中...")
                    except Exception as e:
                        # 发生异常，显示默认信息
                        logger.error(f"处理回看节目信息失败: {e}")
                        if hasattr(self, 'catchup_program'):
                            title = self.catchup_program.get('title', '未知节目')
                            self.current_program.setText(f"▶ {title}")
                        self.program_desc.setText("正在回看当前节目")
                        self.time_label.setText("⏱ --:-- - --:--")
                        self.remain_label.setText("回看中...")
                else:
                    # 非回看模式，从EPG数据获取节目描述
                    channel_name = self.current_channel.get("name", "")
                    tvg_id = self.current_channel.get("tvg_id", "")
                    if channel_name:
                        # 首先尝试从EPG解析器获取节目描述（使用tvg-id和频道名称）
                        current_program = self.epg_parser.get_current_program(channel_name, tvg_id)
                        if current_program:
                            self.program_desc.setText(current_program.get("desc", "暂无节目描述"))
                            # 更新时间信息
                            try:
                                from datetime import datetime
                                start_time = datetime.fromisoformat(current_program.get('start', ''))
                                end_time = datetime.fromisoformat(current_program.get('end', ''))
                                start_str = start_time.strftime("%H:%M")
                                end_str = end_time.strftime("%H:%M")
                                self.progress_start.setText(start_str)
                                self.time_label.setText(f"⏱ {start_str} - {end_str}")
                                self.remain_label.setText("播放中...")
                            except:
                                # 时间解析失败，使用默认时间
                                from datetime import datetime
                                current_time = datetime.now()
                                start_hour = current_time.strftime("%H:00")
                                end_hour = (current_time.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)).strftime("%H:00")
                                self.progress_start.setText(start_hour)
                                self.time_label.setText(f"⏱ {current_time.strftime('%H:%M')}")
                                self.remain_label.setText("播放中...")
                        # 然后尝试从EPG_DATA获取节目描述
                        elif EPG_DATA and channel_name in EPG_DATA:
                            current_channel_epg = EPG_DATA[channel_name]
                            if current_channel_epg and len(current_channel_epg) > 0:
                                current_program_data = current_channel_epg[0]
                                self.program_desc.setText(current_program_data.get("description", "暂无节目描述"))
                                # 更新时间信息
                                self.progress_start.setText(current_program_data.get("time", "--:--"))
                                self.time_label.setText(f"⏱ {current_program_data.get('time', '--:--')} - --:--")
                                self.remain_label.setText("播放中...")
                            else:
                                # 没有节目单，显示默认信息
                                self.program_desc.setText("正在播放当前频道")
                                # 显示当前系统时间
                                from datetime import datetime
                                current_time = datetime.now()
                                start_hour = current_time.strftime("%H:00")
                                end_hour = (current_time.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)).strftime("%H:00")
                                self.progress_start.setText(start_hour)
                                self.progress_end.setText(end_hour)
                                self.time_label.setText(f"⏱ {current_time.strftime('%H:%M')}")
                                self.remain_label.setText("播放中...")
                                # 设置进度条
                            minutes = current_time.minute
                            seconds = current_time.second
                            progress = int(((minutes * 60) + seconds) / 3600 * 100)
                            self.program_progress.setValue(progress)
                    else:
                        # 没有节目单，显示默认信息
                        self.program_desc.setText("正在播放当前频道")
                        # 显示当前系统时间
                        from datetime import datetime
                        current_time = datetime.now()
                        start_hour = current_time.strftime("%H:00")
                        end_hour = (current_time.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)).strftime("%H:00")
                        self.progress_start.setText(start_hour)
                        self.progress_end.setText(end_hour)
                        self.time_label.setText(f"⏱ {current_time.strftime('%H:%M')}")
                        self.remain_label.setText("播放中...")
                        # 设置进度条
                        minutes = current_time.minute
                        seconds = current_time.second
                        progress = int(((minutes * 60) + seconds) / 3600 * 100)
                        self.program_progress.setValue(progress)
        except Exception:
            # 发生异常，显示默认信息
            if is_catchup:
                self.program_desc.setText("正在回看当前节目")
                self.time_label.setText("⏱ --:-- - --:--")
                self.remain_label.setText("回看中...")
            else:
                self.program_desc.setText("正在播放当前频道")
                # 显示当前系统时间
                from datetime import datetime
                current_time = datetime.now()
                start_hour = current_time.strftime("%H:00")
                end_hour = (current_time.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)).strftime("%H:00")
                self.progress_start.setText(start_hour)
                self.progress_end.setText(end_hour)
                self.time_label.setText(f"⏱ {current_time.strftime('%H:%M')}")
                self.remain_label.setText("播放中...")
                # 设置进度条
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
                        current_position = current_time_ms / 1000
                        
                        if total_duration > 0:
                            # 计算进度百分比
                            if current_position > 0:
                                progress_value = min(int((current_position / total_duration) * 100), 100)
                            else:
                                # 如果获取不到播放位置，使用0作为初始值
                                progress_value = 0
                            self.program_progress.setValue(progress_value)
                        else:
                            self.program_progress.setValue(0)
                except Exception as e:
                    logger.error(f"处理回看时间显示失败: {e}")
                    # 如果出错，使用视频播放时间
                    if total_time_ms > 0:
                        progress_value = int(position * 100)
                        self.program_progress.setValue(progress_value)
                        self.progress_start.setText(current_time_str)
                        self.progress_end.setText(total_time_str)
                    else:
                        self.program_progress.setValue(0)
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
                        
                        # 格式化时间显示
                        start_str = start_time.strftime("%H:%M")
                        end_str = end_time.strftime("%H:%M")
                        self.progress_start.setText(start_str)
                        self.progress_end.setText(end_str)
                    else:
                        self.program_progress.setValue(0)
                except:
                    # 如果EPG时间解析失败，使用视频播放时间
                    if total_time_ms > 0:
                        progress_value = int(position * 100)
                        self.program_progress.setValue(progress_value)
                        self.progress_start.setText(current_time_str)
                        self.progress_end.setText(total_time_str)
                    else:
                        self.program_progress.setValue(0)
            else:
                # 使用视频播放时间
                if total_time_ms > 0:
                    progress_value = int(position * 100)
                    self.program_progress.setValue(progress_value)
                    self.progress_start.setText(current_time_str)
                    self.progress_end.setText(total_time_str)
                else:
                    self.program_progress.setValue(0)
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
        
        # 不再更新音量，避免音量拖动后自动恢复的问题
        
        # 媒体信息已经通过on_media_info_ready方法更新，这里不再重复获取
        # 如果需要更新媒体信息，会通过on_media_info_ready方法触发
    
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
    
    def keyPressEvent(self, event):
        """处理键盘事件"""
        if event.key() == Qt.Key.Key_Space:
            # 当按下空格键时，如果正在播放，则切换暂停/播放状态
            if hasattr(self, 'player_controller') and self.player_controller and self.player_controller.is_playing:
                self.toggle_play()
        super().keyPressEvent(event)
    
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
            
            # 创建扫描窗口，传递parent参数
            dialog = ScanChannelDialog(self)
            # 使用exec()显示窗口
            dialog.exec()
            
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
        class FloatingDialog(QDialog):
            def __init__(self, parent=None):
                super().__init__(parent)
                self.dragging = False
                self.offset = None
                self.opacity = 220
                self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
                # 设置为工具窗口，无边框
                self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
                # 确保窗口可以接收鼠标事件
                self.setMouseTracking(True)
                # 确保窗口保持活动状态
                self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            
            def mousePressEvent(self, event):
                if event.button() == Qt.MouseButton.LeftButton:
                    self.dragging = True
                    self.offset = event.position().toPoint()
            
            def mouseMoveEvent(self, event):
                if self.dragging:
                    new_position = event.globalPosition().toPoint() - self.offset
                    self.move(new_position)
            
            def mouseReleaseEvent(self, event):
                if event.button() == Qt.MouseButton.LeftButton:
                    self.dragging = False
            
            def paintEvent(self, event):
                """自定义绘制半透明背景和边框"""
                painter = QPainter(self)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                
                # 导入样式
                from ui.styles import AppStyles
                colors = AppStyles._get_colors()
                
                # 创建圆角矩形路径
                from PyQt6.QtGui import QPainterPath
                from PyQt6.QtCore import QRectF
                path = QPainterPath()
                rect = QRectF(self.rect().adjusted(1, 1, -1, -1))
                path.addRoundedRect(rect, 12, 12)
                
                # 绘制半透明背景（只在圆角内）
                # 从主题中获取背景颜色
                bg_color = colors.get('window', '#333333')
                # 解析颜色值
                if bg_color.startswith('#'):
                    # 十六进制颜色
                    r = int(bg_color[1:3], 16)
                    g = int(bg_color[3:5], 16)
                    b = int(bg_color[5:7], 16)
                else:
                    # 默认颜色
                    r, g, b = 30, 30, 30
                painter.fillPath(path, QColor(r, g, b, self.opacity))
                
                # 绘制边框
                border_color = colors.get('mid', '#999999')
                if border_color.startswith('#'):
                    r = int(border_color[1:3], 16)
                    g = int(border_color[3:5], 16)
                    b = int(border_color[5:7], 16)
                else:
                    r, g, b = 120, 120, 120
                painter.setPen(QColor(r, g, b, 200))
                painter.drawPath(path)
                
                # 调用父类的 paintEvent 来绘制子控件
                super().paintEvent(event)
        
        dialog = FloatingDialog(self)
        dialog.setWindowTitle("播放器设置")
        dialog.setMinimumSize(400, 350)
        # 设置样式表
        dialog.setStyleSheet(AppStyles.player_settings_dialog_style())
        
        # 创建布局
        main_layout = QVBoxLayout(dialog)
        
        # 回放协议类型选择
        protocol_group = QGroupBox("回放协议设置")
        protocol_layout = QVBoxLayout()
        
        protocol_label = QLabel("协议类型:")
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
        playlist_group = QGroupBox("列表订阅设置")
        playlist_layout = QVBoxLayout()
        
        playlist_url_label = QLabel("订阅地址:")
        self.playlist_url_edit = QLineEdit()
        self.playlist_url_edit.setPlaceholderText("请输入列表订阅地址")
        
        playlist_name_label = QLabel("订阅名称:")
        self.playlist_name_edit = QLineEdit()
        self.playlist_name_edit.setPlaceholderText("请输入订阅名称")
        
        playlist_interval_label = QLabel("更新间隔时间 (分钟):")
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
        epg_group = QGroupBox("节目单订阅设置")
        epg_layout = QVBoxLayout()
        
        epg_url_label = QLabel("订阅地址:")
        self.epg_url_edit = QLineEdit()
        self.epg_url_edit.setPlaceholderText("请输入节目单订阅地址")
        
        epg_name_label = QLabel("订阅名称:")
        self.epg_name_edit = QLineEdit()
        self.epg_name_edit.setPlaceholderText("请输入订阅名称")
        
        epg_interval_label = QLabel("更新间隔时间 (分钟):")
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
        save_button = QPushButton("保存")
        cancel_button = QPushButton("取消")
        
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
            playlist_interval = int(self.config.get_value('Playlist', 'update_interval', '60'))
            epg_url = self.config.get_value('EPG', 'epg_url', '')
            epg_interval = int(self.config.get_value('EPG', 'update_interval', '60'))
            
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
        """更新列表订阅"""
        try:
            # 声明全局变量
            global CHANNELS
            
            import requests
            
            # 获取订阅设置
            playlist_url = self.config.get_value('Playlist', 'url', '')
            if not playlist_url:
                return
            
            logger.info(f"开始更新列表订阅: {playlist_url}")
            
            # 下载订阅内容
            response = requests.get(playlist_url, timeout=30)
            response.raise_for_status()
            content = response.text
            
            # 解析M3U内容
            if self.channel_model.load_from_file(content):
                # 更新CHANNELS列表
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
                self._update_channel_list_ui()
                
                # 保存最后更新时间
                from datetime import datetime
                self.config.set_value('Playlist', 'last_update', datetime.now().isoformat())
                self.config.save_config()
                
                # 保存列表到缓存文件
                import os
                cache_dir = self.config.get_value('General', 'cache_dir', 'cache')
                if not os.path.exists(cache_dir):
                    os.makedirs(cache_dir)
                
                playlist_cache_file = os.path.join(cache_dir, 'playlist_cache.m3u')
                try:
                    with open(playlist_cache_file, 'w', encoding='utf-8') as f:
                        f.write(content)
                    logger.info(f"列表已保存到缓存文件: {playlist_cache_file}")
                except Exception as ex:
                    logger.error(f"保存列表缓存失败: {ex}")
                
                logger.info(f"列表订阅更新成功，共 {len(CHANNELS)} 个频道")
                self.status_bar.showMessage("列表订阅更新成功")
            else:
                logger.error("列表订阅内容解析失败")
                self.status_bar.showMessage("列表订阅内容解析失败")
        except Exception as ex:
            logger.error(f"更新列表订阅失败: {str(ex)}")
            self.status_bar.showMessage(f"更新列表订阅失败: {str(ex)}")
    
    def update_epg_subscription(self):
        """更新节目单订阅"""
        try:
            # 声明全局变量
            global EPG_DATA
            
            # 获取订阅设置
            epg_url = self.config.get_value('EPG', 'epg_url', '')
            if not epg_url:
                return
            
            logger.info(f"开始更新节目单订阅: {epg_url}")
            
            # 使用EPGParser的load_epg_from_url方法
            from core.epg_parser import global_epg_parser
            if global_epg_parser.load_epg_from_url(epg_url):
                # 更新全局EPG_DATA
                EPG_DATA = global_epg_parser.epg_data
                # 保存最后更新时间
                from datetime import datetime
                self.config.set_value('EPG', 'last_update', datetime.now().isoformat())
                self.config.save_config()
                logger.info(f"节目单订阅更新成功，共 {len(EPG_DATA)} 个频道的节目单，已使用最新数据")
                self.status_bar_show_message("节目单订阅更新成功")
            else:
                # 如果加载失败，从缓存加载
                if global_epg_parser.epg_data:
                    EPG_DATA = global_epg_parser.epg_data
                    logger.info(f"使用缓存的EPG数据，包含 {len(EPG_DATA)} 个频道")
                    self.status_bar_show_message("使用缓存的EPG数据")
                else:
                    logger.error("节目单订阅内容解析失败")
                    self.status_bar_show_message("节目单订阅内容解析失败")
        except Exception as ex:
            logger.error(f"更新节目单订阅失败: {str(ex)}")
            self.status_bar_show_message(f"更新节目单订阅失败: {str(ex)}")
    
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
            self.status_bar.showMessage("播放器设置保存成功")
            dialog.accept()
        except Exception as ex:
            logger.error(f"保存播放器设置失败: {str(ex)}")
            self.status_bar.showMessage(f"保存播放器设置失败: {str(ex)}")
    
    def epg_settings(self):
        """EPG节目单设置"""
        from PyQt6 import QtCore, QtGui
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QDialogButtonBox
        
        # 创建自定义对话框
        class FloatingDialog(QDialog):
            def __init__(self, parent=None):
                super().__init__(parent)
                self.dragging = False
                self.offset = None
                self.opacity = 220
                self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
                # 设置为工具窗口，无边框
                self.setWindowFlags(QtCore.Qt.WindowType.Tool | QtCore.Qt.WindowType.FramelessWindowHint | QtCore.Qt.WindowType.WindowStaysOnTopHint)
                # 确保窗口可以接收鼠标事件
                self.setMouseTracking(True)
                # 确保窗口保持活动状态
                self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
            
            def mousePressEvent(self, event):
                if event.button() == QtCore.Qt.MouseButton.LeftButton:
                    self.dragging = True
                    self.offset = event.position().toPoint()
            
            def mouseMoveEvent(self, event):
                if self.dragging:
                    new_position = event.globalPosition().toPoint() - self.offset
                    self.move(new_position)
            
            def mouseReleaseEvent(self, event):
                if event.button() == QtCore.Qt.MouseButton.LeftButton:
                    self.dragging = False
            
            def paintEvent(self, event):
                """自定义绘制半透明背景和边框"""
                painter = QtGui.QPainter(self)
                painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
                
                # 导入样式
                from ui.styles import AppStyles
                colors = AppStyles._get_colors()
                
                # 创建圆角矩形路径
                from PyQt6.QtGui import QPainterPath
                from PyQt6.QtCore import QRectF
                path = QPainterPath()
                rect = QRectF(self.rect().adjusted(1, 1, -1, -1))
                path.addRoundedRect(rect, 12, 12)
                
                # 绘制半透明背景（只在圆角内）
                # 从主题中获取背景颜色
                bg_color = colors.get('window', '#333333')
                # 解析颜色值
                if bg_color.startswith('#'):
                    # 十六进制颜色
                    r = int(bg_color[1:3], 16)
                    g = int(bg_color[3:5], 16)
                    b = int(bg_color[5:7], 16)
                else:
                    # 默认颜色
                    r, g, b = 30, 30, 30
                painter.fillPath(path, QtGui.QColor(r, g, b, self.opacity))
                
                # 绘制边框
                border_color = colors.get('mid', '#999999')
                if border_color.startswith('#'):
                    r = int(border_color[1:3], 16)
                    g = int(border_color[3:5], 16)
                    b = int(border_color[5:7], 16)
                else:
                    r, g, b = 120, 120, 120
                painter.setPen(QtGui.QColor(r, g, b, 200))
                painter.drawPath(path)
                
                # 调用父类的 paintEvent 来绘制子控件
                super().paintEvent(event)
        
        dialog = FloatingDialog(self)
        dialog.setWindowTitle("EPG节目单设置")
        dialog.setMinimumSize(400, 200)
        # 应用样式
        from ui.styles import AppStyles
        dialog.setStyleSheet(AppStyles.dialog_style())
        
        # 创建布局
        layout = QVBoxLayout(dialog)
        
        # 加载现有设置
        epg_settings = self.config.load_epg_settings()
        
        # EPG URL输入
        url_label = QLabel("EPG节目单URL:")
        layout.addWidget(url_label)
        url_input = QLineEdit()
        url_input.setText(epg_settings['epg_url'])
        layout.addWidget(url_input)
        
        # EPG 来源输入
        source_label = QLabel("EPG节目单来源:")
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
            self.status_bar.showMessage("EPG节目单设置已保存")
    
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
            no_recent_action = QAction("无最近打开的文件", self)
            no_recent_action.setEnabled(False)
            self.recent_menu.addAction(no_recent_action)
        else:
            # 添加最近打开的文件到菜单
            for file_path in recent_files:
                action = QAction(file_path, self)
                action.triggered.connect(lambda checked, path=file_path: self.open_recent_file(path))
                self.recent_menu.addAction(action)
    
    def open_recent_file(self, file_path):
        """打开最近打开的文件"""
        from core.log_manager import global_logger as logger
        
        try:
            # 加载文件内容
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 解析M3U内容
            self.channel_model.load_from_file(content)
            
            # 更新最近打开文件列表
            from core.config_manager import ConfigManager
            config_manager = ConfigManager()
            config_manager.add_recent_file(file_path)
            self.update_recent_files_menu()
            
            logger.info(f"成功打开最近文件: {file_path}")
            self.status_bar.showMessage(f"成功打开文件: {file_path}")
        except Exception as ex:
            logger.error(f"打开最近文件失败: {str(ex)}")
            self.status_bar.showMessage(f"打开文件失败: {str(ex)}")
    
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
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
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
                        self.channel_name.setText(self.current_channel.get("name", "未知频道"))
                        self.current_program.setText("▶ 请选择频道播放")
                        self.program_desc.setText("打开播放列表文件成功，点击频道开始播放")
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
        # 转换标题
        import re
        html = markdown
        # 转换标题
        html = re.sub(r'## (.*)', r'<h2 style="color: #6a9eff; margin-top: 20px; margin-bottom: 10px;">\1</h2>', html)
        # 转换粗体
        html = re.sub(r'\*\*(.*?)\*\*', r'<strong style="color: #ffffff;">\1</strong>', html)
        # 转换列表项
        html = re.sub(r'^1\. (.*)', r'<p style="margin: 5px 0;"><span style="color: #6a9eff;">1. </span>\1</p>', html, flags=re.MULTILINE)
        html = re.sub(r'^- (.*)', r'<p style="margin: 5px 0; margin-left: 20px;"><span style="color: #6a9eff;">- </span>\1</p>', html, flags=re.MULTILINE)
        # 转换换行
        html = html.replace('\n', '<br>')
        # 添加整体样式
        html = f'''<html>
        <head>
            <style>
                body {{ 
                    font-family: 'Microsoft YaHei', sans-serif; 
                    font-size: 14px; 
                    line-height: 1.6; 
                    color: #e0e0e0; 
                    background-color: transparent;
                }}
            </style>
        </head>
        <body>
            {html}
        </body>
        </html>'''
        return html

    def show_usage_instructions(self):
        """显示使用说明"""
        from PyQt6 import QtCore, QtGui
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QHBoxLayout, QPushButton
        from ui.styles import AppStyles
        
        # 创建自定义对话框
        class FloatingDialog(QDialog):
            def __init__(self, parent=None):
                super().__init__(parent)
                self.dragging = False
                self.offset = None
                self.opacity = 220
                self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
                # 设置为工具窗口，无边框
                self.setWindowFlags(QtCore.Qt.WindowType.Tool | QtCore.Qt.WindowType.FramelessWindowHint | QtCore.Qt.WindowType.WindowStaysOnTopHint)
                # 确保窗口可以接收鼠标事件
                self.setMouseTracking(True)
                # 确保窗口保持活动状态
                self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
            
            def mousePressEvent(self, event):
                if event.button() == QtCore.Qt.MouseButton.LeftButton:
                    self.dragging = True
                    self.offset = event.position().toPoint()
            
            def mouseMoveEvent(self, event):
                if self.dragging:
                    new_position = event.globalPosition().toPoint() - self.offset
                    self.move(new_position)
            
            def mouseReleaseEvent(self, event):
                if event.button() == QtCore.Qt.MouseButton.LeftButton:
                    self.dragging = False
            
            def paintEvent(self, event):
                """自定义绘制半透明背景和边框"""
                painter = QtGui.QPainter(self)
                painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
                
                # 导入样式
                from ui.styles import AppStyles
                colors = AppStyles._get_colors()
                
                # 创建圆角矩形路径
                from PyQt6.QtGui import QPainterPath
                from PyQt6.QtCore import QRectF
                path = QPainterPath()
                rect = QRectF(self.rect().adjusted(1, 1, -1, -1))
                path.addRoundedRect(rect, 12, 12)
                
                # 绘制半透明背景（只在圆角内）
                # 从主题中获取背景颜色
                bg_color = colors.get('window', '#333333')
                # 解析颜色值
                if bg_color.startswith('#'):
                    # 十六进制颜色
                    r = int(bg_color[1:3], 16)
                    g = int(bg_color[3:5], 16)
                    b = int(bg_color[5:7], 16)
                else:
                    # 默认颜色
                    r, g, b = 30, 30, 30
                painter.fillPath(path, QtGui.QColor(r, g, b, self.opacity))
                
                # 绘制边框
                border_color = colors.get('mid', '#999999')
                if border_color.startswith('#'):
                    r = int(border_color[1:3], 16)
                    g = int(border_color[3:5], 16)
                    b = int(border_color[5:7], 16)
                else:
                    r, g, b = 120, 120, 120
                painter.setPen(QtGui.QColor(r, g, b, 200))
                painter.drawPath(path)
                
                # 调用父类的 paintEvent 来绘制子控件
                super().paintEvent(event)
    
        dialog = FloatingDialog(self)
        dialog.setWindowTitle(self.language_manager.tr("usage_title"))
        dialog.setMinimumSize(600, 600)
        # 应用样式
        dialog.setStyleSheet(AppStyles.dialog_style())
        
        layout = QVBoxLayout(dialog)
        text_edit = QTextEdit()
        # 设置为富文本模式，支持基本格式
        usage_content = self.language_manager.tr("usage_content")
        if not usage_content:
            # 添加默认说明内容
            usage_content = '## 基本操作\n\n1. **打开播放列表**\n   - 点击"文件"菜单，选择"打开播放列表"\n   - 支持 M3U、TXT 等格式的播放列表文件\n\n2. **播放频道**\n   - 在频道列表中双击频道开始播放\n   - 使用工具栏的播放/暂停/停止按钮控制播放\n   - 调整音量和全屏显示\n\n3. **扫描频道**\n   - 点击"工具"菜单，选择"扫描频道"\n   - 在扫描窗口中输入 IP 范围或 URL\n   - 设置超时时间和线程数\n   - 点击"开始扫描"按钮\n\n4. **验证频道**\n   - 点击"工具"菜单，选择"验证频道"\n   - 系统会自动检测频道的有效性\n   - 无效频道会被标记\n\n5. **频道管理**\n   - 支持拖拽排序频道\n   - 右键菜单可进行批量操作\n   - 支持频道分组和收藏\n\n6. **频道映射**\n   - 点击"工具"菜单，选择"频道映射管理器"\n   - 管理用户映射规则\n   - 查看频道指纹和映射建议\n\n7. **排序配置**\n   - 点击"工具"菜单，选择"排序配置"\n   - 自定义频道分组和排序规则\n   - 支持拖拽调整分组顺序\n\n## 高级功能\n\n- **URL 解析器**：解析复杂的 URL 范围\n- **多语言支持**：切换界面语言\n- **主题切换**：支持深色/浅色主题\n- **配置管理**：自动保存和加载配置\n- **日志系统**：详细的操作日志'
        
        # 转换为HTML格式以支持更好的显示效果
        html_content = self._convert_markdown_to_html(usage_content)
        text_edit.setHtml(html_content)
        text_edit.setReadOnly(True)
        # 设置字体和间距
        text_edit.setFont(QtGui.QFont('Microsoft YaHei', 10))
        text_edit.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        text_edit.setWordWrapMode(QtGui.QTextOption.WrapMode.WordWrap)
        text_edit.setContentsMargins(20, 20, 20, 20)
        layout.addWidget(text_edit)
        
        button_box = QHBoxLayout()
        ok_button = QPushButton("确定")
        ok_button.setStyleSheet(AppStyles.common_button_style())
        ok_button.clicked.connect(dialog.accept)
        button_box.addStretch()
        button_box.addWidget(ok_button)
        layout.addLayout(button_box)
        
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
            # 重新创建菜单栏以更新语言
            self.menuBar().clear()
            self.setup_menu_bar()
            # 更新所有UI文本
            self.language_manager.update_ui_texts(self)
            # 更新状态栏消息
            self.status_bar.showMessage(self.language_manager.tr("language_changed"))
        except Exception as e:
            logger.error(f"切换语言失败: {str(e)}")
            self.status_bar.showMessage("切换语言失败")
    
    def set_theme(self, theme):
        """设置主题"""
        try:
            from ui.theme_manager import get_theme_manager
            theme_manager = get_theme_manager()
            theme_manager.set_theme(theme)
            # 重新创建菜单栏以更新主题
            self.menuBar().clear()
            self.setup_menu_bar()
            # 更新状态栏消息
            self.status_bar.showMessage(f"主题已切换为: {theme}")
        except Exception as e:
            logger.error(f"切换主题失败: {str(e)}")
            self.status_bar.showMessage("切换主题失败")
    
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
        """窗口关闭时，保存窗口布局并关闭扫描频道窗口"""
        # 保存窗口布局
        self.save_window_layout()
        
        # 关闭扫描频道窗口
        if hasattr(self, 'scan_window') and self.scan_window:
            self.scan_window.close()
            
        super().closeEvent(event)
    
    def keyPressEvent(self, event):
        """键盘事件处理"""
        if event.key() == Qt.Key.Key_Escape and self.is_fullscreen:
            self.toggle_fullscreen(False)

    def _check_for_updates_async(self):
        """异步检查新版本"""
        # 检查是否已在检查或已检查过
        if hasattr(self, '_update_checking') and self._update_checking:
            return
        if hasattr(self, '_update_checked') and self._update_checked:
            return
        
        self._update_checking = True
        try:
            # 在后台线程中执行版本检查
            from PyQt6.QtCore import QThread, pyqtSignal
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
            original_title = self.windowTitle()
            if " - 有新版本" not in original_title:
                new_title = f"{original_title} - 有新版本 {latest_version}"
                self.setWindowTitle(new_title)

            # 在状态栏用红字显示提示
            status_message = f"发现新版本 {latest_version} (当前版本 {current_version})"
            self.status_bar.showMessage(status_message, 10000)  # 显示10秒

            # 设置状态栏消息为红色
            from ui.styles import AppStyles
            self.status_bar.setStyleSheet(AppStyles.statusbar_error_style())

            # 10秒后恢复状态栏样式
            from PyQt6.QtCore import QMetaObject, Qt
            QMetaObject.invokeMethod(self, "_reset_statusbar_style", Qt.ConnectionType.QueuedConnection)

            logger.info(f"发现新版本: {latest_version} (当前版本: {current_version})")

        except Exception as e:
            logger.error(f"更新界面提示失败: {str(e)}")

    def _reset_statusbar_style(self):
        """恢复状态栏样式"""
        self.status_bar.setStyleSheet("")
    
    def _on_update_check_completed(self, success, message):
        """版本检查完成时的处理"""
        if success:
            logger.info(f"版本检查完成: {message}")
        else:
            logger.warning(f"版本检查失败: {message}")

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
