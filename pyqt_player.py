import sys
import os
import re
from datetime import datetime
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QListWidget, QListWidgetItem, QStackedWidget,
    QMenuBar, QMenu, QFileDialog, QDialog, QTextEdit, QStatusBar,
    QFrame, QToolButton, QSlider, QGridLayout, QComboBox
)
from PyQt6.QtCore import Qt, QSize, QTimer, QUrl
from PyQt6.QtGui import QIcon, QPixmap, QFont, QColor, QAction, QPainter, QBrush

# 导入播放器服务
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from services.player_service import PlayerController

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
        
    def paintEvent(self, event):
        """自定义绘制半透明背景和边框"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 绘制半透明背景
        painter.fillRect(self.rect(), QColor(30, 30, 30, self.opacity))
        
        # 绘制边框
        painter.setPen(QColor(100, 100, 100, 150))
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 8, 8)
        
        # 调用父类的 paintEvent 来绘制子控件
        super().paintEvent(event)

# 语言管理
class LanguageManager:
    def __init__(self):
        self.current_language = "zh"
        self.translations = {
            "zh": {
                "file": "文件",
                "edit": "编辑",
                "view": "视图",
                "tools": "工具",
                "help": "帮助",
                "new_playlist": "新建播放列表",
                "open_playlist": "打开播放列表",
                "save_playlist": "保存播放列表",
                "save_as": "另存为...",
                "import_channels": "导入频道",
                "export_channels": "导出频道",
                "exit": "退出",
                "undo": "撤销",
                "redo": "重做",
                "select_all": "全选",
                "delete_selected": "删除选中",
                "add_channel": "添加频道",
                "show_epg": "显示节目单",
                "show_playlist": "显示播放列表",
                "fullscreen": "全屏模式",
                "refresh": "刷新",
                "reset_layout": "重置布局",
                "scan_channels": "扫描频道",
                "verify_channels": "验证频道",
                "smart_sort": "智能排序",
                "hide_invalid": "隐藏无效项",
                "restore_hidden": "恢复隐藏项",
                "channel_management": "频道管理",
                "channel_mapping": "频道映射",
                "favorite_management": "收藏管理",
                "network_settings": "网络设置",
                "player_settings": "播放器设置",
                "usage_instructions": "使用说明",
                "about": "关于",
                "language": "语言",
                "chinese": "中文",
                "english": "English",
                "loading_channels": "正在加载频道...",
                "channels_loaded": "成功加载 {count} 个频道",
                "file_format_error": "文件格式不正确或为空",
                "open_file_error": "打开文件失败: {error}",
                "save_success": "保存成功",
                "save_error": "保存文件失败: {error}",
                "no_content": "没有可保存的内容",
                "file_selection_error": "文件选择失败: {error}",
                "app_name": "IPTV Scanner Editor Pro",
                "version": "版本 1.0.0",
                "description": "IPTV 频道扫描和编辑工具",
                "usage_title": "使用说明",
                "usage_content": "1. 点击'文件'菜单打开播放列表\n2. 选择频道开始播放\n3. 使用工具栏控制播放\n4. 点击'工具'菜单扫描和验证频道",
                "about_title": "关于",
                "about_content": "IPTV Scanner Editor Pro\n版本 1.0.0\n\nIPTV 频道扫描和编辑工具\n\n© 2026 IPTV Scanner Editor Pro"
            },
            "en": {
                "file": "File",
                "edit": "Edit",
                "view": "View",
                "tools": "Tools",
                "help": "Help",
                "new_playlist": "New Playlist",
                "open_playlist": "Open Playlist",
                "save_playlist": "Save Playlist",
                "save_as": "Save As...",
                "import_channels": "Import Channels",
                "export_channels": "Export Channels",
                "exit": "Exit",
                "undo": "Undo",
                "redo": "Redo",
                "select_all": "Select All",
                "delete_selected": "Delete Selected",
                "add_channel": "Add Channel",
                "show_epg": "Show EPG",
                "show_playlist": "Show Playlist",
                "fullscreen": "Fullscreen",
                "refresh": "Refresh",
                "reset_layout": "Reset Layout",
                "scan_channels": "Scan Channels",
                "verify_channels": "Verify Channels",
                "smart_sort": "Smart Sort",
                "hide_invalid": "Hide Invalid",
                "restore_hidden": "Restore Hidden",
                "channel_management": "Channel Management",
                "channel_mapping": "Channel Mapping",
                "favorite_management": "Favorite Management",
                "network_settings": "Network Settings",
                "player_settings": "Player Settings",
                "usage_instructions": "Usage Instructions",
                "about": "About",
                "language": "Language",
                "chinese": "中文",
                "english": "English",
                "loading_channels": "Loading channels...",
                "channels_loaded": "Successfully loaded {count} channels",
                "file_format_error": "File format is incorrect or empty",
                "open_file_error": "Failed to open file: {error}",
                "save_success": "Save successful",
                "save_error": "Failed to save file: {error}",
                "no_content": "No content to save",
                "file_selection_error": "File selection failed: {error}",
                "app_name": "IPTV Scanner Editor Pro",
                "version": "Version 1.0.0",
                "description": "IPTV channel scanning and editing tool",
                "usage_title": "Usage Instructions",
                "usage_content": "1. Click 'File' menu to open playlist\n2. Select channel to start playing\n3. Use toolbar to control playback\n4. Click 'Tools' menu to scan and verify channels",
                "about_title": "About",
                "about_content": "IPTV Scanner Editor Pro\nVersion 1.0.0\n\nIPTV channel scanning and editing tool\n\n© 2026 IPTV Scanner Editor Pro"
            }
        }
    
    def set_language(self, language):
        if language in self.translations:
            self.current_language = language
    
    def get(self, key):
        return self.translations.get(self.current_language, {}).get(key, key)

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
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                if line == "#EXTM3U":
                    continue
                
                if line.startswith("#EXTINF:"):
                    extinf_content = line[8:].strip()
                    last_comma = extinf_content.rfind(",")
                    
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
    def __init__(self):
        super().__init__()
        self.setWindowTitle("IPTV Scanner Editor Pro")
        self.setGeometry(100, 100, 1280, 720)
        self.setMinimumSize(800, 600)
        
        # 语言管理
        self.language_manager = LanguageManager()
        
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
        
        # 导入 QTimer
        from PyQt6.QtCore import QTimer
        
        # 创建定时器，定期更新悬浮窗信息
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_floating_panel_info)
        
        # 初始化UI
        self.init_ui()
    
    def init_ui(self):
        """初始化UI"""
        # 主布局
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        
        # 背景设置
        self.central_widget.setStyleSheet("background-color: #000000;")
        
        # 菜单栏
        self.setup_menu_bar()
        
        # 上半部分布局（包含侧边栏和视频区域）
        self.top_layout = QHBoxLayout()
        
        # 左侧EPG面板
        self.epg_panel = TranslucentPanel(opacity=180)
        self.epg_panel.setStyleSheet("""
            QLabel {
                border: none;
                background-color: transparent;
            }
            QListWidget {
                border: none;
                background-color: transparent;
            }
        """)
        self.epg_panel.setFixedWidth(200)
        self.epg_layout = QVBoxLayout(self.epg_panel)
        
        # EPG标题
        self.epg_title = QLabel("📅 节目单")
        self.epg_title.setStyleSheet("color: white; font-size: 14px; font-weight: bold; padding: 8px; background-color: transparent;")
        self.epg_layout.addWidget(self.epg_title)
        
        # EPG内容
        self.epg_content = QListWidget()
        self.epg_content.setStyleSheet("background-color: transparent; color: white; border: none; padding: 5px;")
        self.epg_content.setSpacing(8)
        self.epg_content.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.epg_content.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.epg_layout.addWidget(self.epg_content, 1)
        
        # EPG空提示
        self.epg_empty_label = QLabel("暂无节目信息")
        self.epg_empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.epg_empty_label.setStyleSheet("color: #666666; font-size: 12px; background-color: transparent;")
        self.epg_layout.addWidget(self.epg_empty_label)
        
        # 视频播放区域
        self.video_frame = QFrame()
        self.video_frame.setStyleSheet("background-color: #000000;")
        
        # 创建默认背景（不播放时显示）
        self.video_placeholder = QLabel("📺", self.video_frame)
        self.video_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_placeholder.setStyleSheet("font-size: 200px; color: #1a1a1a; background-color: transparent;")
        self.video_placeholder.show()  # 初始显示
        
        # 创建视频播放窗口（用于VLC）
        self.video_widget = QWidget(self.video_frame)
        self.video_widget.setStyleSheet("background-color: #000000;")
        self.video_widget.hide()  # 初始隐藏
        
        # 初始化播放器控制器
        self.player_controller = PlayerController(self.video_widget)
        self.player_controller.play_state_changed.connect(self.on_play_state_changed)
        
        # 右侧播放列表面板
        self.playlist_panel = TranslucentPanel(opacity=180)
        self.playlist_panel.setStyleSheet("""
            QLabel {
                border: none;
                background-color: transparent;
            }
            QListWidget {
                border: none;
                background-color: transparent;
            }
            QComboBox {
                border: none;
            }
        """)
        self.playlist_panel.setFixedWidth(250)
        self.playlist_layout = QVBoxLayout(self.playlist_panel)
        
        # 播放列表标题和分组选择
        self.playlist_header = QHBoxLayout()
        self.playlist_title = QLabel("📺 频道列表")
        self.playlist_title.setStyleSheet("color: white; font-size: 14px; font-weight: bold; padding: 8px; background-color: transparent;")
        self.group_combo = QComboBox()
        self.group_combo.addItems(CHANNEL_GROUPS)
        self.group_combo.setStyleSheet("background-color: rgba(45, 45, 45, 0.8); color: white; padding: 4px; border: none; font-size: 12px;")
        self.group_combo.currentTextChanged.connect(self.on_group_changed)
        self.playlist_header.addWidget(self.playlist_title)
        self.playlist_header.addWidget(self.group_combo)
        self.playlist_layout.addLayout(self.playlist_header)
        
        # 频道列表
        self.channel_list = QListWidget()
        self.channel_list.setStyleSheet("background-color: transparent; color: white; border: none; padding: 5px;")
        self.channel_list.setSpacing(6)
        self.channel_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.channel_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.channel_list.itemClicked.connect(self.select_channel)
        self.playlist_layout.addWidget(self.channel_list, 1)
        
        # 频道列表空提示
        self.channel_empty_label = QLabel("暂无频道")
        self.channel_empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.channel_empty_label.setStyleSheet("color: #666666; font-size: 12px; background-color: transparent;")
        self.playlist_layout.addWidget(self.channel_empty_label)
        
        # 添加到上半部分布局（只添加视频区域）
        self.top_layout.addWidget(self.video_frame, 1)
        
        # 设置左右侧边栏为独立窗口（悬浮效果）
        # 左侧EPG面板悬浮
        self.epg_panel.setFixedHeight(self.video_frame.height() - 180)  # 留出底部空间
        self.epg_panel.show()
        
        # 右侧播放列表面板悬浮
        self.playlist_panel.setFixedHeight(self.video_frame.height() - 180)  # 留出底部空间
        self.playlist_panel.show()
        
        # 悬浮控制面板
        self.floating_panel = TranslucentPanel(opacity=180)
        self.floating_panel.setStyleSheet("""
            QLabel {
                border: none;
                background-color: transparent;
            }
            QPushButton {
                border: none;
            }
            QSlider {
                border: none;
            }
            QProgressBar {
                border: none;
            }
        """)
        self.floating_panel.setFixedHeight(150)
        self.floating_panel.setFixedWidth(1100)
        self.floating_layout = QVBoxLayout(self.floating_panel)
        self.floating_layout.setContentsMargins(15, 8, 15, 8)
        self.floating_layout.setSpacing(5)
        
        # 第一行：媒体信息（详细版）
        self.media_row = QHBoxLayout()
        self.media_row.setSpacing(12)
        
        self.video_info = QLabel("📺 未播放")
        self.video_info.setStyleSheet("color: #aaaaaa; font-size: 9px; background-color: transparent;")
        self.media_row.addWidget(self.video_info)
        
        self.audio_info = QLabel("🔊 --")
        self.audio_info.setStyleSheet("color: #aaaaaa; font-size: 9px; background-color: transparent;")
        self.media_row.addWidget(self.audio_info)
        
        self.network_info = QLabel("📡 --")
        self.network_info.setStyleSheet("color: #aaaaaa; font-size: 9px; background-color: transparent;")
        self.media_row.addWidget(self.network_info)
        
        self.media_row.addStretch()
        self.floating_layout.addLayout(self.media_row)
        
        # 分隔线
        line1 = QFrame()
        line1.setFrameShape(QFrame.Shape.HLine)
        line1.setStyleSheet("background-color: #555555; max-height: 1px;")
        self.floating_layout.addWidget(line1)
        
        # 第二行：节目信息（加高布局）
        self.info_row = QHBoxLayout()
        self.info_row.setSpacing(15)
        
        # 左侧：频道LOGO（更宽的长方形）和名称
        left_section = QHBoxLayout()
        left_section.setSpacing(10)
        
        self.channel_logo = QLabel("📺")
        self.channel_logo.setStyleSheet("font-size: 24px; background-color: transparent;")
        self.channel_logo.setFixedSize(120, 40)
        left_section.addWidget(self.channel_logo)
        
        name_section = QVBoxLayout()
        name_section.setSpacing(2)
        
        self.channel_name = QLabel("未选择频道")
        self.channel_name.setStyleSheet("color: white; font-size: 14px; font-weight: bold; background-color: transparent;")
        name_section.addWidget(self.channel_name)
        
        self.current_program = QLabel("▶ 请选择频道开始播放")
        self.current_program.setStyleSheet("color: #4CAF50; font-size: 11px; background-color: transparent;")
        name_section.addWidget(self.current_program)
        
        left_section.addLayout(name_section)
        left_section.addStretch()
        self.info_row.addLayout(left_section, 2)
        
        # 中间：节目描述（直接显示内容，无标题）
        desc_section = QVBoxLayout()
        desc_section.setContentsMargins(0, 5, 0, 0)
        
        self.program_desc = QLabel("打开播放列表文件或导入频道以开始观看")
        self.program_desc.setStyleSheet("color: #cccccc; font-size: 10px; background-color: transparent;")
        self.program_desc.setWordWrap(True)
        desc_section.addWidget(self.program_desc)
        self.info_row.addLayout(desc_section, 3)
        
        # 右侧：节目时间信息
        time_section = QVBoxLayout()
        time_section.setSpacing(2)
        
        self.time_label = QLabel("⏱ --:-- - --:--")
        self.time_label.setStyleSheet("color: #aaaaaa; font-size: 10px; background-color: transparent;")
        time_section.addWidget(self.time_label)
        
        self.remain_label = QLabel("等待播放...")
        self.remain_label.setStyleSheet("color: #4CAF50; font-size: 10px; background-color: transparent;")
        time_section.addWidget(self.remain_label)
        self.info_row.addLayout(time_section, 1)
        
        self.floating_layout.addLayout(self.info_row)
        
        # 分隔线
        line2 = QFrame()
        line2.setFrameShape(QFrame.Shape.HLine)
        line2.setStyleSheet("background-color: #555555; max-height: 1px;")
        self.floating_layout.addWidget(line2)
        
        # 第三行：播放控制 + 节目进度条
        self.control_row = QHBoxLayout()
        self.control_row.setSpacing(8)
        
        # 左侧：播放按钮
        self.play_button = QToolButton()
        self.play_button.setText("▶")
        self.play_button.setFixedSize(28, 26)
        self.play_button.setStyleSheet("color: white; font-size: 14px; background-color: rgba(60, 60, 60, 0.9); border-radius: 4px; border: none;")
        self.play_button.clicked.connect(self.toggle_play)
        self.control_row.addWidget(self.play_button)
        
        self.control_row.addStretch()
        
        # 中间：时间进度条组（居中）
        self.progress_group = QHBoxLayout()
        self.progress_group.setSpacing(4)
        
        # 当前节目开始时间
        self.progress_start = QLabel("--:--")
        self.progress_start.setStyleSheet("color: #888888; font-size: 11px; background-color: transparent;")
        self.progress_group.addWidget(self.progress_start)
        
        # 时间进度条
        self.program_progress = QSlider(Qt.Orientation.Horizontal)
        self.program_progress.setRange(0, 100)
        self.program_progress.setValue(0)
        self.program_progress.setFixedWidth(450)
        self.program_progress.setStyleSheet("""
            QSlider {
                background-color: transparent;
            }
            QSlider::groove:horizontal { 
                background: #555555; 
                height: 4px; 
                border-radius: 2px;
            } 
            QSlider::sub-page:horizontal { 
                background: #4CAF50;
                height: 4px; 
                border-radius: 2px;
            }
            QSlider::handle:horizontal { 
                background: #ffffff; 
                width: 10px; 
                height: 10px; 
                border-radius: 5px;
                margin: -3px 0;
            }
        """)
        self.progress_group.addWidget(self.program_progress)
        
        # 当前节目结束时间
        self.progress_end = QLabel("--:--")
        self.progress_end.setStyleSheet("color: #888888; font-size: 11px; background-color: transparent;")
        self.progress_group.addWidget(self.progress_end)
        
        self.control_row.addLayout(self.progress_group)
        
        self.control_row.addStretch()
        
        # 5. 音量图标
        self.volume_button = QToolButton()
        self.volume_button.setText("🔊")
        self.volume_button.setFixedSize(28, 26)
        self.volume_button.setStyleSheet("color: white; font-size: 12px; background-color: rgba(60, 60, 60, 0.9); border-radius: 4px; border: none;")
        self.control_row.addWidget(self.volume_button)
        
        # 6. 音量调节拖动条
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(80)
        self.volume_slider.setFixedWidth(80)
        self.volume_slider.setStyleSheet("""
            QSlider::groove:horizontal { 
                background: #444444; 
                height: 4px; 
                border-radius: 2px;
            } 
            QSlider::sub-page:horizontal {
                background: #4CAF50;
                height: 4px;
                border-radius: 2px;
            }
            QSlider::handle:horizontal { 
                background: #ffffff; 
                width: 12px; 
                height: 12px; 
                border-radius: 6px;
                margin: -4px 0;
            }
        """)
        self.volume_slider.valueChanged.connect(self.set_volume)
        self.control_row.addWidget(self.volume_slider)
        
        # 7. 全屏图标
        self.fullscreen_button = QToolButton()
        self.fullscreen_button.setText("⛶")
        self.fullscreen_button.setFixedSize(28, 26)
        self.fullscreen_button.setStyleSheet("color: white; font-size: 12px; background-color: rgba(60, 60, 60, 0.9); border-radius: 4px; border: none;")
        self.fullscreen_button.clicked.connect(self.toggle_fullscreen)
        self.control_row.addWidget(self.fullscreen_button)
        
        self.floating_layout.addLayout(self.control_row)
        
        # 添加到主布局
        self.main_layout.addLayout(self.top_layout, 1)
        
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        # 显示底部悬浮控制面板
        self.floating_panel.show()
        
        # 安装事件过滤器
        self.video_frame.installEventFilter(self)
        self.video_widget.installEventFilter(self)
        self.video_placeholder.installEventFilter(self)
        
        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪")
        
        # 填充频道列表
        self.populate_channel_list()
        
        # 填充EPG列表
        self.populate_epg_list()
        
        # 使用定时器延迟更新悬浮窗位置，确保窗口已显示
        QTimer.singleShot(100, self.update_floating_position)
    
    def setup_menu_bar(self):
        """设置菜单栏"""
        menu_bar = self.menuBar()
        
        # 文件菜单
        file_menu = menu_bar.addMenu(self.language_manager.get("file"))
        
        new_playlist = QAction(self.language_manager.get("new_playlist"), self)
        new_playlist.triggered.connect(self.new_playlist)
        file_menu.addAction(new_playlist)
        
        open_playlist = QAction(self.language_manager.get("open_playlist"), self)
        open_playlist.triggered.connect(self.open_playlist)
        file_menu.addAction(open_playlist)
        
        save_playlist = QAction(self.language_manager.get("save_playlist"), self)
        save_playlist.triggered.connect(self.save_playlist)
        file_menu.addAction(save_playlist)
        
        save_as = QAction(self.language_manager.get("save_as"), self)
        save_as.triggered.connect(self.save_as)
        file_menu.addAction(save_as)
        
        file_menu.addSeparator()
        
        import_channels = QAction(self.language_manager.get("import_channels"), self)
        import_channels.triggered.connect(self.import_channels)
        file_menu.addAction(import_channels)
        
        export_channels = QAction(self.language_manager.get("export_channels"), self)
        export_channels.triggered.connect(self.export_channels)
        file_menu.addAction(export_channels)
        
        file_menu.addSeparator()
        
        exit_action = QAction(self.language_manager.get("exit"), self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # 编辑菜单
        edit_menu = menu_bar.addMenu(self.language_manager.get("edit"))
        
        undo = QAction(self.language_manager.get("undo"), self)
        edit_menu.addAction(undo)
        
        redo = QAction(self.language_manager.get("redo"), self)
        edit_menu.addAction(redo)
        
        edit_menu.addSeparator()
        
        select_all = QAction(self.language_manager.get("select_all"), self)
        edit_menu.addAction(select_all)
        
        delete_selected = QAction(self.language_manager.get("delete_selected"), self)
        edit_menu.addAction(delete_selected)
        
        add_channel = QAction(self.language_manager.get("add_channel"), self)
        edit_menu.addAction(add_channel)
        
        # 视图菜单
        view_menu = menu_bar.addMenu(self.language_manager.get("view"))
        
        show_epg = QAction(self.language_manager.get("show_epg"), self, checkable=True)
        show_epg.setChecked(self.epg_visible)
        show_epg.triggered.connect(self.toggle_epg)
        view_menu.addAction(show_epg)
        
        show_playlist = QAction(self.language_manager.get("show_playlist"), self, checkable=True)
        show_playlist.setChecked(self.playlist_visible)
        show_playlist.triggered.connect(self.toggle_playlist)
        view_menu.addAction(show_playlist)
        
        show_floating = QAction("显示控制面板", self, checkable=True)
        show_floating.setChecked(self.floating_panel_visible)
        show_floating.triggered.connect(self.toggle_floating_panel)
        view_menu.addAction(show_floating)
        
        view_menu.addSeparator()
        
        fullscreen = QAction(self.language_manager.get("fullscreen"), self, checkable=True)
        fullscreen.triggered.connect(self.toggle_fullscreen)
        view_menu.addAction(fullscreen)
        
        refresh = QAction(self.language_manager.get("refresh"), self)
        refresh.triggered.connect(self.refresh_ui)
        view_menu.addAction(refresh)
        
        reset_layout = QAction(self.language_manager.get("reset_layout"), self)
        reset_layout.triggered.connect(self.reset_layout)
        view_menu.addAction(reset_layout)
        
        # 工具菜单
        tools_menu = menu_bar.addMenu(self.language_manager.get("tools"))
        
        scan_channels = QAction(self.language_manager.get("scan_channels"), self)
        tools_menu.addAction(scan_channels)
        
        verify_channels = QAction(self.language_manager.get("verify_channels"), self)
        tools_menu.addAction(verify_channels)
        
        tools_menu.addSeparator()
        
        smart_sort = QAction(self.language_manager.get("smart_sort"), self)
        tools_menu.addAction(smart_sort)
        
        hide_invalid = QAction(self.language_manager.get("hide_invalid"), self)
        tools_menu.addAction(hide_invalid)
        
        restore_hidden = QAction(self.language_manager.get("restore_hidden"), self)
        tools_menu.addAction(restore_hidden)
        
        tools_menu.addSeparator()
        
        channel_management = QAction(self.language_manager.get("channel_management"), self)
        tools_menu.addAction(channel_management)
        
        channel_mapping = QAction(self.language_manager.get("channel_mapping"), self)
        tools_menu.addAction(channel_mapping)
        
        favorite_management = QAction(self.language_manager.get("favorite_management"), self)
        tools_menu.addAction(favorite_management)
        
        tools_menu.addSeparator()
        
        network_settings = QAction(self.language_manager.get("network_settings"), self)
        tools_menu.addAction(network_settings)
        
        player_settings = QAction(self.language_manager.get("player_settings"), self)
        tools_menu.addAction(player_settings)
        
        # 帮助菜单
        help_menu = menu_bar.addMenu(self.language_manager.get("help"))
        
        usage_instructions = QAction(self.language_manager.get("usage_instructions"), self)
        usage_instructions.triggered.connect(self.show_usage_instructions)
        help_menu.addAction(usage_instructions)
        
        about = QAction(self.language_manager.get("about"), self)
        about.triggered.connect(self.show_about)
        help_menu.addAction(about)
        
        help_menu.addSeparator()
        
        # 语言选择
        language_menu = help_menu.addMenu(self.language_manager.get("language"))
        
        chinese = QAction(self.language_manager.get("chinese"), self, checkable=True)
        chinese.setChecked(self.language_manager.current_language == "zh")
        chinese.triggered.connect(lambda: self.set_language("zh"))
        language_menu.addAction(chinese)
        
        english = QAction(self.language_manager.get("english"), self, checkable=True)
        english.setChecked(self.language_manager.current_language == "en")
        english.triggered.connect(lambda: self.set_language("en"))
        language_menu.addAction(english)
    
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
        self.epg_content.setStyleSheet("background-color: transparent; color: white; border: none; padding: 5px;")
        
        # 检查是否有当前频道
        if not self.current_channel:
            self.epg_empty_label.show()
            return
        
        # TODO: 从EPG源获取真实数据
        # 目前显示空提示，等待真实EPG数据
        self.epg_empty_label.show()
    
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
        self.channel_logo.setText(logo if logo else "📺")
        
        # 从EPG数据获取当前节目描述（安全处理）
        try:
            channel_name = self.current_channel.get("name", "")
            if channel_name and EPG_DATA and channel_name in EPG_DATA:
                current_channel_epg = EPG_DATA[channel_name]
                if current_channel_epg and len(current_channel_epg) > 0:
                    current_program_data = current_channel_epg[0]
                    self.program_desc.setText(current_program_data.get("description", "暂无节目描述"))
                    # 更新时间信息
                    self.progress_start.setText(current_program_data.get("time", "--:--"))
                    self.time_label.setText(f"⏱ {current_program_data.get('time', '--:--')} - --:--")
                    self.remain_label.setText("等待播放...")
                else:
                    self.program_desc.setText(f"URL: {self.current_channel.get('url', 'N/A')[:50]}...")
            else:
                self.program_desc.setText(f"URL: {self.current_channel.get('url', 'N/A')[:50]}...")
        except Exception:
            self.program_desc.setText(f"URL: {self.current_channel.get('url', 'N/A')[:50]}...")
        
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
    
    def set_volume(self, value):
        """设置音量"""
        if self.player_controller:
            self.player_controller.set_volume(value)
    
    def play_channel(self, channel):
        """播放指定频道"""
        if self.player_controller and channel:
            url = channel.get('url')
            name = channel.get('name', '未知频道')
            if url:
                # 播放前先显示视频窗口（VLC需要可见窗口才能正确设置视频输出）
                if hasattr(self, 'video_placeholder'):
                    self.video_placeholder.hide()
                if hasattr(self, 'video_widget'):
                    self.video_widget.setGeometry(0, 0, self.video_frame.width(), self.video_frame.height())
                    self.video_widget.show()
                # 确保悬浮窗在视频窗口之上
                if hasattr(self, 'floating_panel'):
                    self.floating_panel.raise_()
                self.player_controller.play(url, name)
    
    def on_play_state_changed(self, is_playing):
        """播放状态改变时的处理"""
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
            # 启动定时器，每200ms更新一次
            self.update_timer.start(200)
            # 立即尝试调整窗口大小，并在之后持续检查
            self.adjust_window_size_to_video()
            self._resize_attempts = 0
            self._resize_timer = QTimer()
            self._resize_timer.timeout.connect(self._try_adjust_window_size)
            self._resize_timer.start(500)  # 每500ms检查一次
        else:
            self.play_button.setText("▶")
            # 停止时隐藏视频窗口，显示背景
            if hasattr(self, 'video_widget'):
                self.video_widget.hide()
            if hasattr(self, 'video_placeholder'):
                self.video_placeholder.setGeometry(0, 0, self.video_frame.width(), self.video_frame.height())
                self.video_placeholder.show()
            # 停止定时器
            if hasattr(self, 'update_timer'):
                self.update_timer.stop()
    
    def adjust_window_size_to_video(self):
        """根据视频分辨率调整窗口大小，保持窗口高度不变，调整宽度以适应视频比例"""
        if not self.player_controller:
            return
        
        try:
            # 获取视频分辨率
            resolution = self.player_controller.get_video_resolution()
            print(f"DEBUG: resolution = {resolution}")
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
            
            # 计算缩放比例：窗口高度 / 视频高度
            scale = current_height / video_height
            
            # 计算新的窗口宽度 = 视频宽度 * 缩放比例
            new_window_width = int(video_width * scale)
            
            print(f"DEBUG: video={video_width}x{video_height}, scale={scale:.3f}, current={current_width}x{current_height}, new_width={new_window_width}")
            
            # 设置最小和最大宽度限制
            new_window_width = max(800, min(new_window_width, 1920))
            
            # 只有当新宽度与当前宽度差异超过50px时才调整
            if abs(new_window_width - current_width) < 50:
                print(f"DEBUG: width difference too small, skipping")
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
        if not self.player_controller or not self.current_channel:
            return
        
        # 获取视频分辨率和其他媒体信息（安全处理）
        try:
            resolution = self.player_controller.get_video_resolution() or "未知"
            video_codec = self.player_controller.get_video_codec() or "未知"
            bitrate = self.player_controller.get_bitrate() or "未知"
            fps = self.player_controller.get_fps() or "未知"
            audio_codec = self.player_controller.get_audio_codec() or "未知"
            network_stats = self.player_controller.get_network_stats() or "延迟:--ms 丢包:--% 缓冲:--%"
            
            # 更新第一行：媒体信息
            video_info_text = f"📺 {resolution}  {video_codec}  {bitrate}  {fps}"
            audio_info_text = f"🔊 {audio_codec}"
            network_info_text = f"📡 {network_stats}"
            
            self.video_info.setText(video_info_text)
            self.audio_info.setText(audio_info_text)
            self.network_info.setText(network_info_text)
        except Exception:
            self.video_info.setText("📺 获取中...")
            self.audio_info.setText("🔊 --")
            self.network_info.setText("📡 --")
        
        # 更新第二行：频道信息
        self.channel_name.setText(self.current_channel.get("name", "未知频道"))
        self.current_program.setText("▶ 正在播放")
        
        # 从EPG数据获取当前节目描述（安全处理）
        try:
            channel_name = self.current_channel.get("name", "")
            if channel_name and EPG_DATA and channel_name in EPG_DATA:
                current_channel_epg = EPG_DATA[channel_name]
                if current_channel_epg and len(current_channel_epg) > 0:
                    current_program_data = current_channel_epg[0]
                    self.program_desc.setText(current_program_data.get("description", "暂无节目描述"))
                    # 更新时间信息
                    self.progress_start.setText(current_program_data.get("time", "--:--"))
                    self.time_label.setText(f"⏱ {current_program_data.get('time', '--:--')} - --:--")
                    self.remain_label.setText("播放中...")
        except Exception:
            pass
    
    def update_floating_panel_info(self):
        """定期更新悬浮窗信息（进度条、时间等）"""
        if not self.player_controller or not self.current_channel:
            return
        
        # 更新播放进度
        current_time_ms = self.player_controller.get_current_time()
        total_time_ms = self.player_controller.get_total_time()
        position = self.player_controller.get_position()
        
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
        
        # 更新进度条
        if total_time_ms > 0:
            progress_value = int(position * 100)
            self.program_progress.setValue(progress_value)
        else:
            self.program_progress.setValue(0)
        
        # 更新时间显示（如果有视频时间信息）
        if current_time_ms > 0 and total_time_ms > 0:
            self.progress_start.setText(current_time_str)
            self.progress_end.setText(total_time_str)
        
        # 更新音量
        volume = self.player_controller.get_volume()
        self.volume_slider.setValue(volume)
    
    def eventFilter(self, obj, event):
        """事件过滤器，处理鼠标事件"""
        if obj in (self.video_frame, self.video_widget, self.video_placeholder):
            if event.type() == event.Type.Resize:
                # 视频区域大小改变时，重新定位悬浮窗
                self.update_floating_position()
        return super().eventFilter(obj, event)
    
    def update_floating_position(self):
        """更新悬浮窗位置"""
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
    
    def toggle_fullscreen(self, checked=None):
        """切换全屏"""
        if checked is None:
            self.is_fullscreen = not self.is_fullscreen
        else:
            self.is_fullscreen = checked
        
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
        self.resize(1280, 720)
    
    def new_playlist(self):
        """新建播放列表"""
        global CHANNELS
        CHANNELS = []
        self.populate_channel_list()
        # 清空EPG显示
        self.epg_content.clear()
        self.epg_empty_label.show()
        self.status_bar.showMessage("已新建播放列表")
    
    def open_playlist(self):
        """打开播放列表"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            self.language_manager.get("open_playlist"),
            "",
            "M3U文件 (*.m3u *.m3u8);;文本文件 (*.txt);;所有文件 (*.*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
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
                            "current_program": ''
                        })
                    if CHANNELS:
                        self.current_channel = CHANNELS[0]
                        self.channel_name.setText(self.current_channel.get("name", "未知频道"))
                        self.current_program.setText("▶ 请选择频道播放")
                        self.program_desc.setText("打开播放列表文件成功，点击频道开始播放")
                        logo = self.current_channel.get("logo", "")
                        self.channel_logo.setText(logo if logo else "📺")
                    
                    self.populate_channel_list()
                    self.status_bar.showMessage(self.language_manager.get("channels_loaded").format(count=len(CHANNELS)))
                else:
                    self.status_bar.showMessage(self.language_manager.get("file_format_error"))
            except Exception as ex:
                self.status_bar.showMessage(self.language_manager.get("open_file_error").format(error=str(ex)))
    
    def save_playlist(self):
        """保存播放列表"""
        self.save_as()
    
    def save_as(self):
        """另存为"""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            self.language_manager.get("save_as"),
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
                    self.status_bar.showMessage(self.language_manager.get("save_success"))
                else:
                    self.status_bar.showMessage(self.language_manager.get("no_content"))
            except Exception as ex:
                self.status_bar.showMessage(self.language_manager.get("save_error").format(error=str(ex)))
    
    def import_channels(self):
        """导入频道"""
        self.open_playlist()
    
    def export_channels(self):
        """导出频道"""
        self.save_as()
    
    def show_usage_instructions(self):
        """显示使用说明"""
        dialog = QDialog(self)
        dialog.setWindowTitle(self.language_manager.get("usage_title"))
        dialog.setGeometry(200, 200, 400, 300)
        
        layout = QVBoxLayout(dialog)
        text_edit = QTextEdit()
        text_edit.setPlainText(self.language_manager.get("usage_content"))
        text_edit.setReadOnly(True)
        layout.addWidget(text_edit)
        
        button_box = QHBoxLayout()
        ok_button = QPushButton("确定")
        ok_button.clicked.connect(dialog.accept)
        button_box.addStretch()
        button_box.addWidget(ok_button)
        layout.addLayout(button_box)
        
        dialog.exec()
    
    def show_about(self):
        """显示关于"""
        dialog = QDialog(self)
        dialog.setWindowTitle(self.language_manager.get("about_title"))
        dialog.setGeometry(200, 200, 400, 300)
        
        layout = QVBoxLayout(dialog)
        text_edit = QTextEdit()
        text_edit.setPlainText(self.language_manager.get("about_content"))
        text_edit.setReadOnly(True)
        layout.addWidget(text_edit)
        
        button_box = QHBoxLayout()
        ok_button = QPushButton("确定")
        ok_button.clicked.connect(dialog.accept)
        button_box.addStretch()
        button_box.addWidget(ok_button)
        layout.addLayout(button_box)
        
        dialog.exec()
    
    def set_language(self, language):
        """设置语言"""
        self.language_manager.set_language(language)
        # 重新初始化UI
        self.close()
        self.__init__()
        self.show()
    
    def moveEvent(self, event):
        """主窗口移动时，更新悬浮窗口位置"""
        super().moveEvent(event)
        self.update_floating_position()
    
    def resizeEvent(self, event):
        """主窗口调整大小时，更新悬浮窗口位置"""
        super().resizeEvent(event)
        self.update_floating_position()
    
    def keyPressEvent(self, event):
        """键盘事件处理"""
        if event.key() == Qt.Key.Key_Escape and self.is_fullscreen:
            self.toggle_fullscreen(False)

# 主函数
if __name__ == "__main__":
    app = QApplication(sys.argv)
    player = IPTVPlayer()
    player.show()
    sys.exit(app.exec())
