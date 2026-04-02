import flet as ft
import asyncio
import os
import json

class LanguageManager:
    """语言管理器"""
    def __init__(self, locales_dir="locales"):
        self.locales_dir = locales_dir
        self.current_language = "zh"  # 默认中文
        self.translations = {}
        self._load_translations()
    
    def _load_translations(self):
        """加载所有语言翻译"""
        for lang_code in ["zh", "en"]:
            file_path = os.path.join(self.locales_dir, f"{lang_code}.json")
            if os.path.exists(file_path):
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        self.translations[lang_code] = json.load(f)
                except Exception as e:
                    print(f"加载语言文件失败 {lang_code}: {e}")
    
    def set_language(self, lang_code):
        """设置当前语言"""
        if lang_code in self.translations:
            self.current_language = lang_code
    
    def get(self, key, default=None):
        """获取翻译文本"""
        if self.current_language in self.translations:
            return self.translations[self.current_language].get(key, default or key)
        return default or key

# 初始化语言管理器
lang_manager = LanguageManager()

# 模拟频道数据
CHANNELS = [
    {"id": 1, "name": "CCTV-1 综合", "url": "http://example.com/cctv1", "logo": "📺", "current_program": "新闻联播"},
    {"id": 2, "name": "CCTV-2 财经", "url": "http://example.com/cctv2", "logo": "📈", "current_program": "经济半小时"},
    {"id": 3, "name": "CCTV-3 综艺", "url": "http://example.com/cctv3", "logo": "🎭", "current_program": "星光大道"},
    {"id": 4, "name": "CCTV-4 国际", "url": "http://example.com/cctv4", "logo": "🌏", "current_program": "中国新闻"},
    {"id": 5, "name": "CCTV-5 体育", "url": "http://example.com/cctv5", "logo": "⚽", "current_program": "体育新闻"},
    {"id": 6, "name": "CCTV-6 电影", "url": "http://example.com/cctv6", "logo": "🎬", "current_program": "国产电影"},
    {"id": 7, "name": "CCTV-7 军事", "url": "http://example.com/cctv7", "logo": "🔱", "current_program": "军事报道"},
    {"id": 8, "name": "CCTV-8 电视剧", "url": "http://example.com/cctv8", "logo": "📺", "current_program": "觉醒年代"},
]

# 模拟EPG数据
EPG_DATA = {
    "CCTV-1 综合": [
        {"time": "18:30", "title": "新闻联播", "description": "全国新闻联播"},
        {"time": "19:00", "title": "天气预报", "description": "全国天气预报"},
        {"time": "19:30", "title": "焦点访谈", "description": "焦点访谈节目"},
        {"time": "20:00", "title": "黄金剧场", "description": "电视剧：觉醒年代"},
        {"time": "21:00", "title": "晚间新闻", "description": "晚间新闻报道"},
    ],
    "CCTV-2 财经": [
        {"time": "18:30", "title": "经济半小时", "description": "经济新闻"},
        {"time": "19:00", "title": "经济信息联播", "description": "经济信息"},
        {"time": "20:00", "title": "生财有道", "description": "创业故事"},
        {"time": "21:00", "title": "消费主张", "description": "消费指南"},
    ],
}

class IPTVPlayer:
    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = "IPTV Scanner Editor Pro"
        self.page.bgcolor = "#000000"
        # 16:9 比例窗口，更适合视频播放 (1280x720)
        self.page.window.width = 1280
        self.page.window.height = 720
        self.page.window.resizable = False
        
        # 当前选中的频道
        self.current_channel = CHANNELS[0]
        
        # 面板状态
        self.epg_collapsed = True  # 默认收起
        self.playlist_collapsed = True  # 默认收起
        
        # 悬浮面板显示状态
        self.floating_panel_visible = False  # 初始隐藏
        
        # 全屏状态
        self.is_fullscreen = False
        
        # 设置键盘事件监听
        self.page.on_keyboard_event = self._on_keyboard_event
        
        # 构建界面
        self.build_ui()
    
    def build_ui(self):
        """构建主界面"""
        # 创建悬浮控制面板容器（用于显示/隐藏）- 使用opacity
        self.floating_panel_inner = self.build_floating_panel()
        self.floating_panel_wrapper = ft.Container(
            content=self.floating_panel_inner,
            opacity=1.0 if self.floating_panel_visible else 0.0,
            animate_opacity=ft.Animation(300, ft.AnimationCurve.EASE_IN_OUT),
            on_hover=self._on_hover_floating_panel,
        )
        self.floating_panel_container = ft.Container(
            content=self.floating_panel_wrapper,
            bottom=10,
            left=200,
            right=200,
        )
        
        # 添加菜单栏
        self._setup_menu_bar()
        
        # 视频面板 - 使用expand让它自动填充
        self.video_panel = self.build_video_panel()
        
        # 悬浮的EPG面板
        self.epg_floating = self.build_epg_floating_panel()
        
        # 悬浮的播放列表面板
        self.playlist_floating = self.build_playlist_floating_panel()
        
        # 使用Stack布局：视频在最底层，悬浮面板在上面
        main_stack = ft.Stack(
            [
                # 底层：视频区域（全屏）
                self.video_panel,
                
                # 悬浮EPG面板（左侧）- 增加高度
                ft.Container(
                    content=self.epg_floating if not self.epg_collapsed else self.build_epg_toggle_button(),
                    left=10,
                    top=30,
                    bottom=100,
                ),
                
                # 悬浮播放列表面板（右侧）- 增加高度
                ft.Container(
                    content=self.playlist_floating if not self.playlist_collapsed else self.build_playlist_toggle_button(),
                    right=10,
                    top=30,
                    bottom=100,
                ),
                
                # 底部响应区域（用于触发显示悬浮面板）- 在悬浮窗下方，只覆盖底部一小条
                ft.GestureDetector(
                    content=ft.Container(
                        width=None,
                        height=30,  # 只覆盖底部30像素
                        bgcolor="#00000001",  # 几乎透明但可接收事件
                    ),
                    on_enter=self._on_enter_bottom_area,
                    bottom=0,
                    left=0,
                    right=0,
                ),
                
                # 悬浮控制面板（底部）- 在响应区域上方
                self.floating_panel_container,
            ],
            expand=True,
        )
        
        # 添加到页面
        self.page.add(main_stack)
    
    def build_epg_toggle_button(self):
        """构建EPG展开按钮（半透明悬浮）"""
        return ft.Container(
            width=36,
            height=80,
            bgcolor="#1e1e1e80",  # 半透明背景
            border_radius=ft.BorderRadius(top_right=8, bottom_right=8, top_left=0, bottom_left=0),
            content=ft.IconButton(
                ft.Icons.CHEVRON_RIGHT,
                icon_color="white",
                tooltip="展开节目单",
                on_click=self._toggle_epg_panel,
            ),
            padding=0,
        )
    
    def build_playlist_toggle_button(self):
        """构建播放列表展开按钮（半透明悬浮）"""
        return ft.Container(
            width=36,
            height=80,
            bgcolor="#1e1e1e80",  # 半透明背景
            border_radius=ft.BorderRadius(top_left=8, bottom_left=8, top_right=0, bottom_right=0),
            content=ft.IconButton(
                ft.Icons.CHEVRON_LEFT,
                icon_color="white",
                tooltip="展开播放列表",
                on_click=self._toggle_playlist_panel,
            ),
            padding=0,
        )
    
    def build_epg_floating_panel(self):
        """构建悬浮EPG面板"""
        # 标题栏
        title_bar = ft.Row([
            ft.IconButton(
                ft.Icons.CHEVRON_LEFT,
                icon_color="white",
                tooltip="收起",
                on_click=self._toggle_epg_panel
            ),
            ft.Text("节目单", size=16, color="white", weight=ft.FontWeight.BOLD, expand=True),
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER)
        
        # 日期选择
        date_row = ft.Row([
            ft.IconButton(ft.Icons.CHEVRON_LEFT, icon_color="#888", icon_size=18),
            ft.Text("2026-04-02", size=12, color="white"),
            ft.IconButton(ft.Icons.CHEVRON_RIGHT, icon_color="#888", icon_size=18),
        ], alignment=ft.MainAxisAlignment.CENTER, spacing=5)
        
        # EPG列表
        epg_items = []
        current_channel_epg = EPG_DATA.get(self.current_channel["name"], [])
        for i, program in enumerate(current_channel_epg):
            program_item = ft.Container(
                content=ft.Row([
                    ft.Text(program["time"], size=11, color="#aaa", width=45),
                    ft.Column([
                        ft.Text(program["title"], size=13, color="white"),
                        ft.Text(program["description"], size=10, color="#888"),
                    ], expand=True, spacing=2),
                    ft.Icon(ft.Icons.REPLAY, size=14, color="#4CAF50"),
                ], spacing=8),
                padding=8,
                bgcolor="#2d2d2d80",  # 半透明
                border_radius=4,
                margin=ft.Margin(0, 3, 0, 3),
                on_click=lambda e, idx=i: self.select_program(idx),
                ink=True,  # 添加点击效果
            )
            epg_items.append(program_item)
        
        # 滚动视图
        epg_view = ft.ListView(
            controls=epg_items,
            expand=True,
            padding=8,
        )
        
        # 整体面板
        panel = ft.Container(
            width=260,
            height=None,
            bgcolor="#1e1e1ecc",  # 半透明背景
            border_radius=8,
            padding=10,
            content=ft.Column([
                title_bar,
                date_row,
                epg_view,
            ], spacing=8, tight=True),
        )
        
        return panel
    
    def build_playlist_floating_panel(self):
        """构建悬浮播放列表面板"""
        # 标题栏
        title_bar = ft.Row([
            ft.Text("播放列表", size=16, color="white", weight=ft.FontWeight.BOLD, expand=True),
            ft.IconButton(
                ft.Icons.CHEVRON_RIGHT,
                icon_color="white",
                tooltip="收起",
                on_click=self._toggle_playlist_panel
            ),
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER)
        
        # 搜索框
        search_box = ft.TextField(
            hint_text="搜索频道...",
            bgcolor="#2d2d2d80",  # 半透明
            color="white",
            border_color="#444",
            height=36,
            prefix_icon=ft.Icons.SEARCH,
            text_size=12,
        )
        
        # 频道列表
        channels = []
        for channel in CHANNELS:
            channel_item = ft.Container(
                content=ft.Row([
                    ft.Text(channel["logo"], size=20),
                    ft.Column([
                        ft.Text(channel["name"], size=13, color="white", weight=ft.FontWeight.BOLD),
                        ft.Text(channel["current_program"], size=11, color="#888"),
                    ], spacing=2, expand=True),
                ], spacing=8),
                padding=8,
                bgcolor="#2d2d2d80" if channel != self.current_channel else "#4CAF5030",  # 半透明
                border_radius=4,
                margin=ft.Margin(0, 3, 0, 3),
                on_click=lambda e, c=channel: self.select_channel(c),
            )
            channels.append(channel_item)
        
        # 滚动视图
        playlist_view = ft.ListView(
            controls=channels,
            expand=True,
            padding=8,
        )
        
        # 整体面板
        panel = ft.Container(
            width=240,
            height=None,
            bgcolor="#1e1e1ecc",  # 半透明背景
            border_radius=8,
            padding=10,
            content=ft.Column([
                title_bar,
                search_box,
                playlist_view,
            ], spacing=8, tight=True),
        )
        
        return panel
    
    def _toggle_playlist_panel(self, e):
        """切换播放列表面板展开/收起"""
        self.playlist_collapsed = not self.playlist_collapsed
        # 重新构建界面
        self.page.clean()
        self.build_ui()
    
    def _toggle_epg_panel(self, e):
        """切换EPG面板展开/收起"""
        self.epg_collapsed = not self.epg_collapsed
        # 重新构建界面
        self.page.clean()
        self.build_ui()
    
    def _setup_menu_bar(self):
        """设置菜单栏"""
        # 下拉菜单实现
        self.file_menu = ft.PopupMenuButton(
            content=ft.Row([
                ft.Text("文件", color="white"),
                ft.Icon(ft.Icons.ARROW_DROP_DOWN, color="white", size=18)
            ], spacing=2),
            items=[
                ft.PopupMenuItem(content=ft.Row([ft.Icon(ft.Icons.CREATE_NEW_FOLDER, size=18), ft.Text("新建播放列表")]), on_click=self._menu_new_playlist),
                ft.PopupMenuItem(content=ft.Row([ft.Icon(ft.Icons.FOLDER_OPEN, size=18), ft.Text("打开播放列表...")]), on_click=self._menu_open_playlist),
                ft.PopupMenuItem(content=ft.Row([ft.Icon(ft.Icons.SAVE, size=18), ft.Text("保存播放列表")]), on_click=self._menu_save_playlist),
                ft.PopupMenuItem(content=ft.Row([ft.Icon(ft.Icons.SAVE_AS, size=18), ft.Text("另存为...")]), on_click=self._menu_save_playlist_as),
                ft.PopupMenuItem(),  # 分隔线
                ft.PopupMenuItem(content=ft.Row([ft.Icon(ft.Icons.IMPORT_EXPORT, size=18), ft.Text("导入频道...")]), on_click=self._menu_import_channels),
                ft.PopupMenuItem(content=ft.Row([ft.Icon(ft.Icons.DOWNLOAD, size=18), ft.Text("导出频道...")]), on_click=self._menu_export_channels),
                ft.PopupMenuItem(),  # 分隔线
                ft.PopupMenuItem(content=ft.Row([ft.Icon(ft.Icons.EXIT_TO_APP, size=18), ft.Text("退出")]), on_click=self._menu_exit),
            ]
        )
        
        self.edit_menu = ft.PopupMenuButton(
            content=ft.Row([
                ft.Text("编辑", color="white"),
                ft.Icon(ft.Icons.ARROW_DROP_DOWN, color="white", size=18)
            ], spacing=2),
            items=[
                ft.PopupMenuItem(content=ft.Row([ft.Icon(ft.Icons.UNDO, size=18), ft.Text("撤销")]), on_click=self._menu_undo),
                ft.PopupMenuItem(content=ft.Row([ft.Icon(ft.Icons.REDO, size=18), ft.Text("重做")]), on_click=self._menu_redo),
                ft.PopupMenuItem(),  # 分隔线
                ft.PopupMenuItem(content=ft.Row([ft.Icon(ft.Icons.SELECT_ALL, size=18), ft.Text("全选")]), on_click=self._menu_select_all),
                ft.PopupMenuItem(content=ft.Row([ft.Icon(ft.Icons.DELETE, size=18), ft.Text("删除选中")]), on_click=self._menu_delete_selected),
                ft.PopupMenuItem(),  # 分隔线
                ft.PopupMenuItem(content=ft.Row([ft.Icon(ft.Icons.ADD, size=18), ft.Text("添加频道...")]), on_click=self._menu_add_channel),
            ]
        )
        
        self.view_menu = ft.PopupMenuButton(
            content=ft.Row([
                ft.Text("视图", color="white"),
                ft.Icon(ft.Icons.ARROW_DROP_DOWN, color="white", size=18)
            ], spacing=2),
            items=[
                ft.PopupMenuItem(content=ft.Row([ft.Icon(ft.Icons.LIST_ALT, size=18), ft.Text("显示/隐藏节目单")]), on_click=self._menu_toggle_epg),
                ft.PopupMenuItem(content=ft.Row([ft.Icon(ft.Icons.PLAYLIST_PLAY, size=18), ft.Text("显示/隐藏播放列表")]), on_click=self._menu_toggle_playlist),
                ft.PopupMenuItem(),  # 分隔线
                ft.PopupMenuItem(content=ft.Row([ft.Icon(ft.Icons.FULLSCREEN, size=18), ft.Text("全屏模式")]), on_click=self._menu_fullscreen),
                ft.PopupMenuItem(content=ft.Row([ft.Icon(ft.Icons.REFRESH, size=18), ft.Text("刷新界面")]), on_click=self._menu_refresh),
                ft.PopupMenuItem(content=ft.Row([ft.Icon(ft.Icons.RESTART_ALT, size=18), ft.Text("重置布局")]), on_click=self._menu_reset_layout),
            ]
        )
        
        self.tools_menu = ft.PopupMenuButton(
            content=ft.Row([
                ft.Text("工具", color="white"),
                ft.Icon(ft.Icons.ARROW_DROP_DOWN, color="white", size=18)
            ], spacing=2),
            items=[
                ft.PopupMenuItem(content=ft.Row([ft.Icon(ft.Icons.SEARCH, size=18), ft.Text("扫描频道...")]), on_click=self._menu_scan_channels),
                ft.PopupMenuItem(content=ft.Row([ft.Icon(ft.Icons.CHECK_CIRCLE, size=18), ft.Text("验证频道...")]), on_click=self._menu_validate_channels),
                ft.PopupMenuItem(),  # 分隔线
                ft.PopupMenuItem(content=ft.Row([ft.Icon(ft.Icons.SORT, size=18), ft.Text("智能排序")]), on_click=self._menu_smart_sort),
                ft.PopupMenuItem(content=ft.Row([ft.Icon(ft.Icons.VISIBILITY_OFF, size=18), ft.Text("隐藏无效项")]), on_click=self._menu_hide_invalid),
                ft.PopupMenuItem(content=ft.Row([ft.Icon(ft.Icons.VISIBILITY, size=18), ft.Text("恢复隐藏项")]), on_click=self._menu_restore_hidden),
                ft.PopupMenuItem(),  # 分隔线
                ft.PopupMenuItem(content=ft.Row([ft.Icon(ft.Icons.EDIT, size=18), ft.Text("频道管理")]), on_click=self._menu_channel_manager),
                ft.PopupMenuItem(content=ft.Row([ft.Icon(ft.Icons.MAP, size=18), ft.Text("频道映射")]), on_click=self._menu_channel_mapping),
                ft.PopupMenuItem(),  # 分隔线
                ft.PopupMenuItem(content=ft.Row([ft.Icon(ft.Icons.STAR, size=18), ft.Text("收藏管理")]), on_click=self._menu_favorites),
                ft.PopupMenuItem(),  # 分隔线
                ft.PopupMenuItem(content=ft.Row([ft.Icon(ft.Icons.SETTINGS, size=18), ft.Text("网络设置...")]), on_click=self._menu_network_settings),
                ft.PopupMenuItem(content=ft.Row([ft.Icon(ft.Icons.PLAY_CIRCLE, size=18), ft.Text("播放器设置...")]), on_click=self._menu_player_settings),
            ]
        )
        
        self.help_menu = ft.PopupMenuButton(
            content=ft.Row([
                ft.Text("帮助", color="white"),
                ft.Icon(ft.Icons.ARROW_DROP_DOWN, color="white", size=18)
            ], spacing=2),
            items=[
                ft.PopupMenuItem(content=ft.Row([ft.Icon(ft.Icons.HELP, size=18), ft.Text("使用说明")]), on_click=self._menu_help),
                ft.PopupMenuItem(content=ft.Row([ft.Icon(ft.Icons.INFO, size=18), ft.Text("关于")]), on_click=self._menu_about),
                ft.PopupMenuItem(),  # 分隔线
                ft.PopupMenuItem(content=ft.Row([ft.Icon(ft.Icons.LANGUAGE, size=18), ft.Text("中文 / English")]), on_click=self._toggle_language),
            ]
        )
        
        # 菜单栏 - 半透明悬浮样式
        menu_bar = ft.Container(
            content=ft.Row([
                ft.Container(
                    content=self.file_menu,
                    padding=ft.Padding(8, 4, 8, 4),
                    bgcolor="#2d2d2d80",
                    border_radius=4,
                ),
                ft.Container(
                    content=self.edit_menu,
                    padding=ft.Padding(8, 4, 8, 4),
                    bgcolor="#2d2d2d80",
                    border_radius=4,
                ),
                ft.Container(
                    content=self.view_menu,
                    padding=ft.Padding(8, 4, 8, 4),
                    bgcolor="#2d2d2d80",
                    border_radius=4,
                ),
                ft.Container(
                    content=self.tools_menu,
                    padding=ft.Padding(8, 4, 8, 4),
                    bgcolor="#2d2d2d80",
                    border_radius=4,
                ),
                ft.Container(
                    content=self.help_menu,
                    padding=ft.Padding(8, 4, 8, 4),
                    bgcolor="#2d2d2d80",
                    border_radius=4,
                ),
            ], spacing=5),
            padding=8,
            bgcolor="#00000000",  # 透明背景
        )
        
        # 添加到页面
        self.page.add(menu_bar)
    
    # ========== 文件菜单功能 ==========
    def _menu_new_playlist(self, e):
        """新建播放列表"""
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text("新建播放列表功能"),
            duration=2000
        )
        self.page.snack_bar.open = True
        self.page.update()
    
    def _menu_save_playlist_as(self, e):
        """另存为"""
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text("另存为功能"),
            duration=2000
        )
        self.page.snack_bar.open = True
        self.page.update()
    
    def _menu_open_playlist(self, e):
        """打开播放列表"""
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text("打开播放列表功能 - 选择文件对话框"),
            duration=2000
        )
        self.page.snack_bar.open = True
        self.page.update()
    
    def _menu_save_playlist(self, e):
        """保存播放列表"""
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text("保存播放列表功能"),
            duration=2000
        )
        self.page.snack_bar.open = True
        self.page.update()
    
    def _menu_import_channels(self, e):
        """导入频道"""
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text("导入频道功能"),
            duration=2000
        )
        self.page.snack_bar.open = True
        self.page.update()
    
    def _menu_export_channels(self, e):
        """导出频道"""
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text("导出频道功能"),
            duration=2000
        )
        self.page.snack_bar.open = True
        self.page.update()
    
    def _menu_exit(self, e):
        """退出程序"""
        self.page.window.close()
    
    # ========== 编辑菜单功能 ==========
    def _menu_undo(self, e):
        """撤销"""
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text("撤销功能"),
            duration=2000
        )
        self.page.snack_bar.open = True
        self.page.update()
    
    def _menu_redo(self, e):
        """重做"""
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text("重做功能"),
            duration=2000
        )
        self.page.snack_bar.open = True
        self.page.update()
    
    def _menu_select_all(self, e):
        """全选"""
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text("全选功能"),
            duration=2000
        )
        self.page.snack_bar.open = True
        self.page.update()
    
    def _menu_delete_selected(self, e):
        """删除选中"""
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text("删除选中功能"),
            duration=2000
        )
        self.page.snack_bar.open = True
        self.page.update()
    
    def _menu_add_channel(self, e):
        """添加频道"""
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text("添加频道功能"),
            duration=2000
        )
        self.page.snack_bar.open = True
        self.page.update()
    
    # ========== 视图菜单功能 ==========
    def _menu_toggle_epg(self, e):
        """切换EPG面板"""
        self._toggle_epg_panel(e)
    
    def _menu_toggle_playlist(self, e):
        """切换播放列表面板"""
        self._toggle_playlist_panel(e)
    
    def _menu_fullscreen(self, e):
        """全屏模式"""
        self.page.window.full_screen = not self.page.window.full_screen
        self.page.update()
    
    def _menu_refresh(self, e):
        """刷新界面"""
        self.page.clean()
        self.build_ui()
    
    def _menu_reset_layout(self, e):
        """重置布局"""
        self.epg_collapsed = True
        self.playlist_collapsed = True
        self.is_fullscreen = False
        self.page.window.full_screen = False
        self.page.clean()
        self.build_ui()
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text("布局已重置"),
            duration=2000
        )
        self.page.snack_bar.open = True
        self.page.update()
    
    # ========== 工具菜单功能 ==========
    def _menu_scan_channels(self, e):
        """扫描频道"""
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text("频道扫描功能"),
            duration=2000
        )
        self.page.snack_bar.open = True
        self.page.update()
    
    def _menu_validate_channels(self, e):
        """验证频道"""
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text("频道验证功能"),
            duration=2000
        )
        self.page.snack_bar.open = True
        self.page.update()
    
    def _menu_smart_sort(self, e):
        """智能排序"""
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text("智能排序功能"),
            duration=2000
        )
        self.page.snack_bar.open = True
        self.page.update()
    
    def _menu_hide_invalid(self, e):
        """隐藏无效项"""
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text("隐藏无效项功能"),
            duration=2000
        )
        self.page.snack_bar.open = True
        self.page.update()
    
    def _menu_restore_hidden(self, e):
        """恢复隐藏项"""
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text("恢复隐藏项功能"),
            duration=2000
        )
        self.page.snack_bar.open = True
        self.page.update()
    
    def _menu_channel_manager(self, e):
        """频道管理"""
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text("频道管理功能"),
            duration=2000
        )
        self.page.snack_bar.open = True
        self.page.update()
    
    def _menu_channel_mapping(self, e):
        """频道映射"""
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text("频道映射功能"),
            duration=2000
        )
        self.page.snack_bar.open = True
        self.page.update()
    
    def _menu_favorites(self, e):
        """收藏管理"""
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text("收藏管理功能"),
            duration=2000
        )
        self.page.snack_bar.open = True
        self.page.update()
    
    def _menu_network_settings(self, e):
        """网络设置"""
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text("网络设置功能"),
            duration=2000
        )
        self.page.snack_bar.open = True
        self.page.update()
    
    def _menu_player_settings(self, e):
        """播放器设置"""
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text("播放器设置功能"),
            duration=2000
        )
        self.page.snack_bar.open = True
        self.page.update()
    
    # ========== 帮助菜单功能 ==========
    def _menu_help(self, e):
        """使用说明"""
        if lang_manager.current_language == "zh":
            title = "使用说明"
            content = [
                ft.Text("IPTV Scanner Editor Pro 使用说明:", size=14, weight=ft.FontWeight.BOLD),
                ft.Text(""),
                ft.Text("1. 播放控制: 使用底部控制面板", size=12),
                ft.Text("2. 频道切换: 点击右侧播放列表", size=12),
                ft.Text("3. 查看节目单: 点击左侧节目单面板", size=12),
                ft.Text("4. 更多功能: 使用菜单栏", size=12),
            ]
            close_btn = "关闭"
        else:
            title = "Help"
            content = [
                ft.Text("IPTV Scanner Editor Pro Help:", size=14, weight=ft.FontWeight.BOLD),
                ft.Text(""),
                ft.Text("1. Playback Control: Use bottom control panel", size=12),
                ft.Text("2. Channel Switch: Click right playlist", size=12),
                ft.Text("3. View EPG: Click left EPG panel", size=12),
                ft.Text("4. More Features: Use menu bar", size=12),
            ]
            close_btn = "Close"
        
        self.page.dialog = ft.AlertDialog(
            title=ft.Text(title),
            content=ft.Column(content, tight=True, spacing=4),
            actions=[
                ft.TextButton(close_btn, on_click=lambda e: self._close_dialog(e))
            ]
        )
        self.page.dialog.open = True
        self.page.update()
    
    def _menu_about(self, e):
        """关于"""
        if lang_manager.current_language == "zh":
            title = "关于 IPTV Scanner Editor Pro"
            content = [
                ft.Text("IPTV Scanner Editor Pro", size=16, weight=ft.FontWeight.BOLD),
                ft.Text("版本: 1.0.0", size=12),
                ft.Text(""),
                ft.Text("一个功能强大的 IPTV 频道扫描、验证、编辑和管理工具。", size=12),
                ft.Text(""),
                ft.Text("主要功能:", size=12, weight=ft.FontWeight.BOLD),
                ft.Text("• 智能频道扫描", size=11),
                ft.Text("• 高级流验证", size=11),
                ft.Text("• 智能频道管理", size=11),
                ft.Text("• 集成视频播放", size=11),
                ft.Text("• 数据导入导出", size=11),
            ]
            close_btn = "关闭"
        else:
            title = "About IPTV Scanner Editor Pro"
            content = [
                ft.Text("IPTV Scanner Editor Pro", size=16, weight=ft.FontWeight.BOLD),
                ft.Text("Version: 1.0.0", size=12),
                ft.Text(""),
                ft.Text("A powerful IPTV channel scanning, validation, editing and management tool.", size=12),
                ft.Text(""),
                ft.Text("Main Features:", size=12, weight=ft.FontWeight.BOLD),
                ft.Text("• Smart Channel Scan", size=11),
                ft.Text("• Advanced Stream Validation", size=11),
                ft.Text("• Smart Channel Management", size=11),
                ft.Text("• Integrated Video Playback", size=11),
                ft.Text("• Data Import/Export", size=11),
            ]
            close_btn = "Close"
        
        self.page.dialog = ft.AlertDialog(
            title=ft.Text(title),
            content=ft.Column(content, tight=True, spacing=4),
            actions=[
                ft.TextButton(close_btn, on_click=lambda e: self._close_dialog(e))
            ]
        )
        self.page.dialog.open = True
        self.page.update()
    
    def _close_dialog(self, e):
        """关闭对话框"""
        self.page.dialog.open = False
        self.page.update()
    
    def build_video_panel(self):
        """构建视频播放面板 - 全屏扩展"""
        # 视频容器 - 使用expand填满所有可用空间
        video_container = ft.Container(
            expand=True,
            bgcolor="#000000",
        )
        
        # 视频播放区域（居中显示）- 只显示大播放图标背景
        video_placeholder = ft.Column([
            ft.Row([
                ft.Icon(ft.Icons.PLAY_CIRCLE_OUTLINE, size=200, color="#1a1a1a"),
            ], alignment=ft.MainAxisAlignment.CENTER),
        ], alignment=ft.MainAxisAlignment.CENTER, expand=True)
        
        video_container.content = video_placeholder
        
        return video_container
    
    def build_floating_panel(self):
        """构建悬浮控制面板"""
        # 悬浮面板 - 优化高度和padding
        panel = ft.Container(
            width=None,
            height=150,
            bgcolor="#1e1e1ecc",  # 半透明背景
            border_radius=8,
            padding=ft.Padding(20, 10, 20, 10),
        )
        
        # 第一行：媒体信息 - 优化字体大小和间距
        media_info = ft.Text(
            "📺 1920×1080  H.264  4.5Mbps  25fps  "
            "🔊 AAC  128kbps  2.0ch  48kHz  "
            "📡 延迟:45ms  丢包:0%  缓冲:100%",
            size=12,
            color="#ffffff",
        )
        
        # 分隔线1 - 媒体信息和节目信息之间
        separator1 = ft.Container(
            height=1,
            bgcolor="#666666",
            margin=ft.Margin(0, 8, 0, 8),
        )
        
        # 第二行：节目信息 - LOGO为长方形，名字在左，描述在右
        program_info = ft.Row([
            # 左侧：LOGO + 频道名称
            ft.Row([
                # LOGO区域 - 长方形
                ft.Container(
                    content=ft.Row([
                        ft.Text(self.current_channel["logo"], size=40),
                    ], alignment=ft.MainAxisAlignment.CENTER, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    width=80,
                    height=50,
                    bgcolor="#2d2d2d80",
                    border_radius=6,
                    margin=ft.Margin(0, 0, 12, 0),
                ),
                # 频道名称和当前节目
                ft.Column([
                    ft.Text(self.current_channel["name"], size=16, color="#ffffff", weight=ft.FontWeight.BOLD),
                    ft.Text(self.current_channel["current_program"], size=13, color="#4CAF50"),
                ], spacing=3, alignment=ft.MainAxisAlignment.CENTER),
            ], spacing=0),
            
            # 右侧：节目描述（多行）
            ft.Container(
                content=ft.Text(
                    "第一集：1915年，陈独秀创办《青年杂志》，倡导民主与科学，新文化运动由此发端。本剧展现了从新文化运动到中国共产党建立这段波澜壮阔的历史画卷...", 
                    size=12, 
                    color="#bbbbbb",
                    max_lines=2,
                    overflow=ft.TextOverflow.ELLIPSIS,
                ),
                expand=True,
                padding=ft.Padding(20, 0, 0, 0),
            ),
        ], spacing=0)
        
        # 分隔线2 - 节目信息和播放控制之间
        separator2 = ft.Container(
            height=1,
            bgcolor="#666666",
            margin=ft.Margin(0, 8, 0, 8),
        )
        
        # 第三行：播放控制 - 使用Row布局，全屏按钮靠右
        controls = ft.Row([
            # 左侧占位，让中间内容居中
            ft.Container(width=30),
            # 主控制区域（居中）
            ft.Row([
                ft.IconButton(ft.Icons.SKIP_PREVIOUS, icon_color="#ffffff", icon_size=20),
                ft.IconButton(ft.Icons.PLAY_CIRCLE_OUTLINE, icon_color="#ffffff", icon_size=30),
                ft.IconButton(ft.Icons.SKIP_NEXT, icon_color="#ffffff", icon_size=20),
                ft.Container(width=10),
                ft.Text("00:23:15", size=11, color="#ffffff", width=50),
                ft.Container(
                    content=ft.ProgressBar(value=0.3, color="#4CAF50", bgcolor="#666666"),
                    width=140,
                    height=4,
                ),
                ft.Text("01:30:00", size=11, color="#ffffff", width=50),
                ft.Container(width=10),
                ft.IconButton(ft.Icons.VOLUME_UP, icon_color="#ffffff", icon_size=16),
                ft.Container(
                    content=ft.Slider(value=0.7, inactive_color="#666666", active_color="#4CAF50"),
                    width=100,
                ),
            ], alignment=ft.MainAxisAlignment.CENTER, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            # 全屏按钮（靠右下）
            ft.Container(
                content=ft.IconButton(
                    ft.Icons.FULLSCREEN if not self.is_fullscreen else ft.Icons.FULLSCREEN_EXIT,
                    icon_color="#ffffff",
                    icon_size=24,
                    on_click=self._toggle_fullscreen
                ),
                margin=ft.Margin(10, 0, 0, 0),
            ),
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER)
        
        # 布局
        layout = ft.Column([
            media_info,
            separator1,
            program_info,
            separator2,
            controls,
        ], spacing=0, tight=True)
        
        panel.content = layout
        return panel
    
    def select_channel(self, channel):
        """选择频道"""
        self.current_channel = channel
        # 重新构建界面以更新选中状态
        self.page.clean()
        self.build_ui()
        
    def select_program(self, program_index):
        """选择节目进行回放"""
        current_channel_epg = EPG_DATA.get(self.current_channel["name"], [])
        if 0 <= program_index < len(current_channel_epg):
            selected_program = current_channel_epg[program_index]
            # 这里可以实现回放逻辑
            print(f"选择回放节目: {selected_program['title']} - {selected_program['time']}")
            # 可以添加提示或开始回放
    
    def update_epg(self):
        """更新EPG节目单"""
        pass
    
    def update_floating_panel(self):
        """更新悬浮面板"""
        pass
    
    def _on_enter_bottom_area(self, e):
        """鼠标进入底部响应区域 - 显示面板"""
        if not self.floating_panel_visible:
            self.floating_panel_visible = True
            self.floating_panel_wrapper.opacity = 1.0
            self.page.update()

    def _on_hover_floating_panel(self, e):
        """鼠标悬停/离开悬浮面板"""
        if e.data is False:  # 鼠标离开面板，隐藏
            if self.floating_panel_visible:
                self.floating_panel_visible = False
                self.floating_panel_wrapper.opacity = 0.0
                self.page.update()
    
    def _on_keyboard_event(self, e: ft.KeyboardEvent):
        """键盘事件处理"""
        # ESC键退出全屏
        if e.key == "Escape" and self.is_fullscreen:
            self._exit_fullscreen()
    
    def _toggle_fullscreen(self, e=None):
        """切换全屏状态"""
        self.is_fullscreen = not self.is_fullscreen
        self.page.window.full_screen = self.is_fullscreen
        
        # 重新构建界面以更新全屏按钮图标
        self.page.clean()
        self.build_ui()
    
    def _exit_fullscreen(self):
        """退出全屏"""
        self.is_fullscreen = False
        self.page.window.full_screen = False
        
        # 重新构建界面以更新全屏按钮图标
        self.page.clean()
        self.build_ui()
    
    def _toggle_language(self, e):
        """切换语言"""
        if lang_manager.current_language == "zh":
            lang_manager.set_language("en")
        else:
            lang_manager.set_language("zh")
        
        # 重新构建界面以更新语言
        self.page.clean()
        self.build_ui()
        
        # 显示提示
        message = "语言已切换为 English" if lang_manager.current_language == "en" else "Language switched to 中文"
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text(message),
            duration=2000
        )
        self.page.snack_bar.open = True
        self.page.update()

def main(page: ft.Page):
    """主函数"""
    IPTVPlayer(page)

# 运行应用
ft.run(main)
