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
from PyQt6.QtGui import QIcon, QPixmap, QFont, QColor, QAction

# 频道列表（默认数据）
CHANNELS = [
    {"id": 1, "name": "CCTV-1 综合", "url": "http://example.com/cctv1.m3u8", "logo": "📺", "current_program": "新闻联播"},
    {"id": 2, "name": "CCTV-2 财经", "url": "http://example.com/cctv2.m3u8", "logo": "📺", "current_program": "经济半小时"},
    {"id": 3, "name": "CCTV-3 综艺", "url": "http://example.com/cctv3.m3u8", "logo": "📺", "current_program": "星光大道"},
    {"id": 4, "name": "CCTV-4 国际", "url": "http://example.com/cctv4.m3u8", "logo": "📺", "current_program": "中国新闻"},
    {"id": 5, "name": "CCTV-5 体育", "url": "http://example.com/cctv5.m3u8", "logo": "📺", "current_program": "体育新闻"},
    {"id": 6, "name": "CCTV-6 电影", "url": "http://example.com/cctv6.m3u8", "logo": "📺", "current_program": "佳片有约"},
    {"id": 7, "name": "CCTV-7 军事", "url": "http://example.com/cctv7.m3u8", "logo": "📺", "current_program": "军事报道"},
    {"id": 8, "name": "CCTV-8 电视剧", "url": "http://example.com/cctv8.m3u8", "logo": "📺", "current_program": "黄金剧场"},
    {"id": 9, "name": "CCTV-9 纪录", "url": "http://example.com/cctv9.m3u8", "logo": "📺", "current_program": "纪录天下"},
    {"id": 10, "name": "CCTV-10 科教", "url": "http://example.com/cctv10.m3u8", "logo": "📺", "current_program": "走近科学"},
    {"id": 11, "name": "湖南卫视", "url": "http://example.com/hunan.m3u8", "logo": "📺", "current_program": "快乐大本营"},
    {"id": 12, "name": "浙江卫视", "url": "http://example.com/zhejiang.m3u8", "logo": "📺", "current_program": "中国好声音"},
    {"id": 13, "name": "东方卫视", "url": "http://example.com/dongfang.m3u8", "logo": "📺", "current_program": "极限挑战"},
    {"id": 14, "name": "江苏卫视", "url": "http://example.com/jiangsu.m3u8", "logo": "📺", "current_program": "非诚勿扰"},
    {"id": 15, "name": "北京卫视", "url": "http://example.com/beijing.m3u8", "logo": "📺", "current_program": "养生堂"},
]

# 频道分组
CHANNEL_GROUPS = ["全部频道", "央视频道", "卫视频道", "地方频道", "体育频道", "电影频道", "综艺频道", "新闻频道"]

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
                    if group_match:
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
        
        # 当前选中的频道
        self.current_channel = CHANNELS[0]
        
        # 面板状态
        self.epg_visible = True
        self.playlist_visible = True
        
        # 悬浮面板显示状态
        self.floating_panel_visible = True
        
        # 全屏状态
        self.is_fullscreen = False
        
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
        self.epg_panel = QFrame()
        self.epg_panel.setStyleSheet("background-color: rgba(30, 30, 30, 0.8); border-radius: 8px;")
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
        
        # 视频播放区域
        self.video_frame = QFrame()
        self.video_frame.setStyleSheet("background-color: #000000;")
        self.video_layout = QVBoxLayout(self.video_frame)
        
        # 视频占位符
        self.video_placeholder = QLabel("📺")
        self.video_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_placeholder.setStyleSheet("font-size: 200px; color: #1a1a1a; background-color: transparent;")
        self.video_layout.addWidget(self.video_placeholder)
        
        # 右侧播放列表面板
        self.playlist_panel = QFrame()
        self.playlist_panel.setStyleSheet("background-color: rgba(30, 30, 30, 0.8); border-radius: 8px;")
        self.playlist_panel.setFixedWidth(250)
        self.playlist_layout = QVBoxLayout(self.playlist_panel)
        
        # 播放列表标题和分组选择
        self.playlist_header = QHBoxLayout()
        self.playlist_title = QLabel("📺 频道列表")
        self.playlist_title.setStyleSheet("color: white; font-size: 14px; font-weight: bold; padding: 8px; background-color: transparent;")
        self.group_combo = QComboBox()
        self.group_combo.addItems(CHANNEL_GROUPS)
        self.group_combo.setStyleSheet("background-color: rgba(45, 45, 45, 0.8); color: white; padding: 4px; border: none; font-size: 12px;")
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
        
        # 添加到上半部分布局（只添加视频区域）
        self.top_layout.addWidget(self.video_frame, 1)
        
        # 设置左右侧边栏为视频区域的子控件（悬浮效果）
        # 左侧EPG面板悬浮
        self.epg_panel.setParent(self.video_frame)
        self.epg_panel.setFixedHeight(self.video_frame.height() - 180)  # 留出底部空间
        self.epg_panel.move(10, 10)
        self.epg_panel.show()
        
        # 右侧播放列表面板悬浮
        self.playlist_panel.setParent(self.video_frame)
        self.playlist_panel.setFixedHeight(self.video_frame.height() - 180)  # 留出底部空间
        self.playlist_panel.move(self.video_frame.width() - self.playlist_panel.width() - 10, 10)
        self.playlist_panel.show()
        
        # 悬浮控制面板
        self.floating_panel = QFrame()
        self.floating_panel.setStyleSheet("background-color: rgba(30, 30, 30, 0.8); border-radius: 8px;")
        self.floating_panel.setFixedHeight(150)
        self.floating_panel.setFixedWidth(1000)
        self.floating_layout = QVBoxLayout(self.floating_panel)
        self.floating_layout.setContentsMargins(15, 8, 15, 8)
        self.floating_layout.setSpacing(5)
        
        # 第一行：媒体信息（详细版）
        media_row = QHBoxLayout()
        media_row.setSpacing(20)
        
        video_info = QLabel("📺 1920×1080  H.264  High@L4.1  4.5Mbps  25fps  YUV420P  BT.709")
        video_info.setStyleSheet("color: #aaaaaa; font-size: 10px; background-color: transparent;")
        media_row.addWidget(video_info)
        
        audio_info = QLabel("🔊 AAC-LC  128kbps  2.0ch  48kHz  16bit  Dolby Digital+")
        audio_info.setStyleSheet("color: #aaaaaa; font-size: 10px; background-color: transparent;")
        media_row.addWidget(audio_info)
        
        network_info = QLabel("📡 RTMP  延迟:45ms  丢包:0%  缓冲:100%  码率:4.8Mbps  连接:稳定")
        network_info.setStyleSheet("color: #aaaaaa; font-size: 10px; background-color: transparent;")
        media_row.addWidget(network_info)
        
        media_row.addStretch()
        self.floating_layout.addLayout(media_row)
        
        # 分隔线
        line1 = QFrame()
        line1.setFrameShape(QFrame.Shape.HLine)
        line1.setStyleSheet("background-color: #555555; max-height: 1px;")
        self.floating_layout.addWidget(line1)
        
        # 第二行：节目信息（加高布局）
        info_row = QHBoxLayout()
        info_row.setSpacing(15)
        
        # 左侧：频道LOGO（更宽的长方形）和名称
        left_section = QHBoxLayout()
        left_section.setSpacing(10)
        
        self.channel_logo = QLabel("📺")
        self.channel_logo.setStyleSheet("font-size: 24px; background-color: transparent;")
        self.channel_logo.setFixedSize(120, 40)
        left_section.addWidget(self.channel_logo)
        
        name_section = QVBoxLayout()
        name_section.setSpacing(2)
        
        self.channel_name = QLabel(self.current_channel["name"])
        self.channel_name.setStyleSheet("color: white; font-size: 14px; font-weight: bold; background-color: transparent;")
        name_section.addWidget(self.channel_name)
        
        self.current_program = QLabel("▶ " + self.current_channel["current_program"])
        self.current_program.setStyleSheet("color: #4CAF50; font-size: 11px; background-color: transparent;")
        name_section.addWidget(self.current_program)
        
        left_section.addLayout(name_section)
        left_section.addStretch()
        info_row.addLayout(left_section, 2)
        
        # 中间：节目描述（直接显示内容，无标题）
        desc_section = QVBoxLayout()
        desc_section.setContentsMargins(0, 5, 0, 0)
        
        self.program_desc = QLabel("本期节目精彩看点，不容错过！这里是节目的详细描述内容，介绍节目的主要内容和看点。")
        self.program_desc.setStyleSheet("color: #cccccc; font-size: 10px; background-color: transparent;")
        self.program_desc.setWordWrap(True)
        desc_section.addWidget(self.program_desc)
        info_row.addLayout(desc_section, 3)
        
        # 右侧：节目时间信息
        time_section = QVBoxLayout()
        time_section.setSpacing(2)
        
        time_label = QLabel("⏱ 20:00 - 20:45")
        time_label.setStyleSheet("color: #aaaaaa; font-size: 10px; background-color: transparent;")
        time_section.addWidget(time_label)
        
        remain_label = QLabel("剩余: 32分钟")
        remain_label.setStyleSheet("color: #4CAF50; font-size: 10px; background-color: transparent;")
        time_section.addWidget(remain_label)
        info_row.addLayout(time_section, 1)
        
        self.floating_layout.addLayout(info_row)
        
        # 分隔线
        line2 = QFrame()
        line2.setFrameShape(QFrame.Shape.HLine)
        line2.setStyleSheet("background-color: #555555; max-height: 1px;")
        self.floating_layout.addWidget(line2)
        
        # 第三行：播放控制 + 节目进度条
        control_row = QHBoxLayout()
        control_row.setSpacing(8)
        
        # 左侧：播放按钮
        self.play_button = QToolButton()
        self.play_button.setText("▶")
        self.play_button.setFixedSize(28, 26)
        self.play_button.setStyleSheet("color: white; font-size: 14px; background-color: rgba(60, 60, 60, 0.9); border-radius: 4px; border: none;")
        control_row.addWidget(self.play_button)
        
        control_row.addStretch()
        
        # 中间：时间进度条组（居中）
        progress_group = QHBoxLayout()
        progress_group.setSpacing(4)
        
        # 当前节目开始时间
        progress_start = QLabel("20:00")
        progress_start.setStyleSheet("color: #888888; font-size: 11px; background-color: transparent;")
        progress_group.addWidget(progress_start)
        
        # 时间进度条
        self.program_progress = QSlider(Qt.Orientation.Horizontal)
        self.program_progress.setRange(0, 100)
        self.program_progress.setValue(35)
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
        progress_group.addWidget(self.program_progress)
        
        # 当前节目结束时间
        progress_end = QLabel("20:45")
        progress_end.setStyleSheet("color: #888888; font-size: 11px; background-color: transparent;")
        progress_group.addWidget(progress_end)
        
        control_row.addLayout(progress_group)
        
        control_row.addStretch()
        
        # 5. 音量图标
        self.volume_button = QToolButton()
        self.volume_button.setText("🔊")
        self.volume_button.setFixedSize(28, 26)
        self.volume_button.setStyleSheet("color: white; font-size: 12px; background-color: rgba(60, 60, 60, 0.9); border-radius: 4px; border: none;")
        control_row.addWidget(self.volume_button)
        
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
        control_row.addWidget(self.volume_slider)
        
        # 7. 全屏图标
        self.fullscreen_button = QToolButton()
        self.fullscreen_button.setText("⛶")
        self.fullscreen_button.setFixedSize(28, 26)
        self.fullscreen_button.setStyleSheet("color: white; font-size: 12px; background-color: rgba(60, 60, 60, 0.9); border-radius: 4px; border: none;")
        self.fullscreen_button.clicked.connect(self.toggle_fullscreen)
        control_row.addWidget(self.fullscreen_button)
        
        self.floating_layout.addLayout(control_row)
        
        # 添加到主布局
        self.main_layout.addLayout(self.top_layout, 1)
        
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(10)
        
        # 设置悬浮窗为视频区域的子控件，实现真正的悬浮效果
        self.floating_panel.setParent(self.video_frame)
        self.floating_panel.setFixedWidth(900)
        self.floating_panel.move(
            (self.video_frame.width() - self.floating_panel.width()) // 2,
            self.video_frame.height() - self.floating_panel.height() - 20
        )
        
        # 设置悬浮窗鼠标悬停显示/离开隐藏
        self.floating_panel.setMouseTracking(True)
        self.video_frame.setMouseTracking(True)
        
        # 初始显示悬浮窗（用于测试）
        self.floating_panel.show()
        
        # 安装事件过滤器
        self.video_frame.installEventFilter(self)
        self.floating_panel.installEventFilter(self)
        
        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪")
        
        # 填充频道列表
        self.populate_channel_list()
        
        # 填充EPG列表
        self.populate_epg_list()
    
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
    
    def populate_channel_list(self):
        """填充频道列表"""
        self.channel_list.clear()
        for channel in CHANNELS:
            item = QListWidgetItem(channel["name"])
            item.setSizeHint(QSize(0, 40))  # 增加行高
            self.channel_list.addItem(item)
    
    def populate_epg_list(self):
        """填充EPG列表"""
        self.epg_content.clear()
        # 设置列表的整体样式
        self.epg_content.setStyleSheet("background-color: transparent; color: white; border: none; padding: 5px;")
        epg_items = [
            {"time": "19:00", "name": "新闻联播", "replay": True, "current": False},
            {"time": "19:30", "name": "天气预报", "replay": False, "current": False},
            {"time": "20:00", "name": "焦点访谈", "replay": True, "current": True},  # 当前播放节目
            {"time": "20:30", "name": "电视剧", "replay": True, "current": False},
            {"time": "22:00", "name": "晚间新闻", "replay": False, "current": False},
            {"time": "22:30", "name": "国际新闻", "replay": True, "current": False}
        ]
        for item_data in epg_items:
            replay_icon = "⏮" if item_data["replay"] else ""
            current_icon = "▶" if item_data["current"] else ""
            if item_data["current"]:
                item_text = f"{item_data['time']} - {item_data['name']} {replay_icon} {current_icon}"
                list_item = QListWidgetItem(item_text)
                # 使用不同的方式标记当前节目
                font = list_item.font()
                font.setBold(True)
                list_item.setFont(font)
                list_item.setForeground(QColor(76, 175, 80))  # #4CAF50
            else:
                item_text = f"{item_data['time']} - {item_data['name']} {replay_icon}"
                list_item = QListWidgetItem(item_text)
            list_item.setSizeHint(QSize(0, 30))  # 增加行高
            self.epg_content.addItem(list_item)
    
    def select_channel(self, item):
        """选择频道"""
        index = self.channel_list.row(item)
        if 0 <= index < len(CHANNELS):
            self.current_channel = CHANNELS[index]
            self.channel_name.setText(self.current_channel["name"])
            self.current_program.setText(self.current_channel["current_program"])
            self.program_desc.setText("当前节目：" + self.current_channel["current_program"])
            self.channel_logo.setText(self.current_channel["logo"])
    
    def toggle_epg(self, checked):
        """显示/隐藏EPG面板"""
        self.epg_visible = checked
        self.epg_panel.setVisible(checked)
    
    def toggle_playlist(self, checked):
        """显示/隐藏播放列表面板"""
        self.playlist_visible = checked
        self.playlist_panel.setVisible(checked)
    
    def eventFilter(self, obj, event):
        """事件过滤器，处理鼠标事件"""
        if obj == self.video_frame:
            if event.type() == event.Type.Resize:
                # 视频区域大小改变时，重新定位悬浮窗
                self.update_floating_position()
            elif event.type() == event.Type.MouseMove:
                # 检查鼠标是否在底部区域
                if self.is_mouse_in_bottom_area(event.pos()):
                    self.floating_panel.show()
                elif not self.floating_panel.underMouse():
                    # 鼠标不在底部区域且不在悬浮窗内，隐藏悬浮窗
                    self.floating_panel.hide()
            elif event.type() == event.Type.Leave:
                # 鼠标离开视频区域时隐藏悬浮窗
                if not self.floating_panel.underMouse():
                    self.floating_panel.hide()
        elif obj == self.floating_panel:
            if event.type() == event.Type.Leave:
                # 鼠标离开悬浮窗时，检查是否还在视频区域底部
                if self.video_frame.underMouse():
                    # 鼠标还在视频区域内，检查是否在底部区域
                    mouse_pos = self.video_frame.mapFromGlobal(self.cursor().pos())
                    if not self.is_mouse_in_bottom_area(mouse_pos):
                        self.floating_panel.hide()
                else:
                    # 鼠标不在视频区域内，隐藏悬浮窗
                    self.floating_panel.hide()
        return super().eventFilter(obj, event)

    def is_mouse_in_bottom_area(self, pos):
        """检查鼠标是否在视频区域底部"""
        bottom_threshold = 80  # 底部80像素区域
        return pos.y() > self.video_frame.height() - bottom_threshold
    
    def update_floating_position(self):
        """更新悬浮窗位置"""
        if hasattr(self, 'floating_panel') and self.floating_panel:
            # 更新底部悬浮控制面板位置
            x = (self.video_frame.width() - self.floating_panel.width()) // 2
            y = self.video_frame.height() - self.floating_panel.height() - 20
            self.floating_panel.move(x, y)
            
            # 更新左侧EPG面板位置和高度
            if hasattr(self, 'epg_panel') and self.epg_panel:
                self.epg_panel.setFixedHeight(self.video_frame.height() - 180)
                self.epg_panel.move(10, 10)
            
            # 更新右侧播放列表面板位置和高度
            if hasattr(self, 'playlist_panel') and self.playlist_panel:
                self.playlist_panel.setFixedHeight(self.video_frame.height() - 180)
                self.playlist_panel.move(self.video_frame.width() - self.playlist_panel.width() - 10, 10)
    
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
        self.epg_panel.setVisible(True)
        self.playlist_panel.setVisible(True)
        self.resize(1280, 720)
    
    def new_playlist(self):
        """新建播放列表"""
        global CHANNELS
        CHANNELS = []
        self.populate_channel_list()
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
                            "logo": ch.get('logo', '📺'),
                            "current_program": ''
                        })
                    if CHANNELS:
                        self.current_channel = CHANNELS[0]
                        self.channel_name.setText(self.current_channel["name"])
                        self.current_program.setText(self.current_channel["current_program"])
                        self.program_desc.setText("当前节目：" + self.current_channel["current_program"])
                        self.channel_logo.setText(self.current_channel["logo"])
                    
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
