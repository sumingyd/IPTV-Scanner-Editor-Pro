import flet as ft

# 模拟频道数据
CHANNELS = [
    {"id": 1, "name": "CCTV-1 综合", "url": "http://example.com/cctv1", "logo": "📺", "current_program": "新闻联播"},
    {"id": 2, "name": "CCTV-2 财经", "url": "http://example.com/cctv2", "logo": "📈", "current_program": "经济半小时"},
    {"id": 3, "name": "CCTV-3 综艺", "url": "http://example.com/cctv3", "logo": "🎭", "current_program": "星光大道"},
    {"id": 4, "name": "CCTV-4 国际", "url": "http://example.com/cctv4", "logo": "🌏", "current_program": "中国新闻"},
    {"id": 5, "name": "CCTV-5 体育", "url": "http://example.com/cctv5", "logo": "⚽", "current_program": "体育新闻"},
]

def main(page: ft.Page):
    page.title = "IPTV Scanner Editor Pro"
    page.bgcolor = "#121212"
    page.window.width = 1200
    page.window.height = 700
    
    # 主布局：左侧播放列表 + 中间视频 + 右侧EPG
    main_row = ft.Row([
        # 左侧播放列表
        ft.Container(
            width=280,
            height=700,
            bgcolor="#1e1e1e",
            content=ft.Column([
                ft.Container(
                    content=ft.Text("播放列表", size=18, color="white", weight=ft.FontWeight.BOLD),
                    padding=15
                ),
                ft.Container(
                    content=ft.TextField(
                        hint_text="搜索频道...",
                        bgcolor="#2d2d2d",
                        color="white",
                        border_color="#444",
                        height=40,
                        prefix_icon=ft.Icons.SEARCH,
                    ),
                    padding=ft.Padding(15, 0, 15, 0)
                ),
                ft.ListView(
                    controls=[
                        ft.Container(
                            content=ft.Row([
                                ft.Text(channel["logo"], size=24),
                                ft.Column([
                                    ft.Text(channel["name"], size=14, color="white", weight=ft.FontWeight.BOLD),
                                    ft.Text(channel["current_program"], size=12, color="#888"),
                                    ft.Text(channel["url"], size=10, color="#666"),
                                ], spacing=2, expand=True),
                            ], spacing=10),
                            padding=10,
                            bgcolor="#2d2d2d",
                            border_radius=6,
                            margin=ft.Margin(10, 5, 10, 5),
                        )
                        for channel in CHANNELS
                    ],
                    expand=True
                )
            ], spacing=10)
        ),
        
        # 中间视频播放区域
        ft.Container(
            width=640,
            height=700,
            bgcolor="#000000",
            content=ft.Column([
                ft.Icon(ft.Icons.PLAY_CIRCLE_OUTLINE, size=100, color="#888"),
                ft.Text("点击播放按钮开始播放", size=16, color="#888"),
            ], alignment=ft.MainAxisAlignment.CENTER, spacing=20)
        ),
        
        # 右侧EPG节目单
        ft.Container(
            width=280,
            height=700,
            bgcolor="#1e1e1e",
            content=ft.Column([
                ft.Container(
                    content=ft.Text("节目单", size=18, color="white", weight=ft.FontWeight.BOLD),
                    padding=15
                ),
                ft.Container(
                    content=ft.Row([
                        ft.IconButton(ft.Icons.CHEVRON_LEFT, icon_color="#888"),
                        ft.Text("2026-04-02", size=14, color="white"),
                        ft.IconButton(ft.Icons.CHEVRON_RIGHT, icon_color="#888"),
                    ], alignment=ft.MainAxisAlignment.CENTER),
                    padding=ft.Padding(15, 0, 15, 0)
                ),
                ft.ListView(
                    controls=[
                        ft.Container(
                            content=ft.Row([
                                ft.Text("18:30", size=12, color="#aaa", width=60),
                                ft.Column([
                                    ft.Text("新闻联播", size=14, color="white"),
                                    ft.Text("全国新闻联播", size=12, color="#888"),
                                ], expand=True),
                                ft.Icon(ft.Icons.REPLAY, size=16, color="#4CAF50"),
                            ], spacing=10),
                            padding=10,
                            bgcolor="#2d2d2d",
                            border_radius=6,
                            margin=ft.Margin(10, 5, 10, 5),
                        ),
                        ft.Container(
                            content=ft.Row([
                                ft.Text("19:00", size=12, color="#aaa", width=60),
                                ft.Column([
                                    ft.Text("天气预报", size=14, color="white"),
                                    ft.Text("全国天气预报", size=12, color="#888"),
                                ], expand=True),
                                ft.Icon(ft.Icons.REPLAY, size=16, color="#4CAF50"),
                            ], spacing=10),
                            padding=10,
                            bgcolor="#2d2d2d",
                            border_radius=6,
                            margin=ft.Margin(10, 5, 10, 5),
                        ),
                        ft.Container(
                            content=ft.Row([
                                ft.Text("19:30", size=12, color="#aaa", width=60),
                                ft.Column([
                                    ft.Text("焦点访谈", size=14, color="white"),
                                    ft.Text("焦点访谈节目", size=12, color="#888"),
                                ], expand=True),
                                ft.Icon(ft.Icons.REPLAY, size=16, color="#4CAF50"),
                            ], spacing=10),
                            padding=10,
                            bgcolor="#2d2d2d",
                            border_radius=6,
                            margin=ft.Margin(10, 5, 10, 5),
                        ),
                    ],
                    expand=True
                )
            ], spacing=10)
        ),
    ], spacing=0)
    
    # 悬浮控制面板
    floating_panel = ft.Container(
        width=1180,
        height=180,
        bgcolor="rgba(30, 30, 30, 0.95)",
        border_radius=ft.BorderRadius(top_left=8, top_right=8, bottom_left=0, bottom_right=0),
        padding=20,
        content=ft.Column([
            # 媒体信息
            ft.Text(
                "📺 1920×1080  H.264  4.5Mbps  25fps  "
                "🔊 AAC  128kbps  2.0ch  48kHz  "
                "📡 延迟:45ms  丢包:0%  缓冲:100%",
                size=12,
                color="#ccc",
            ),
            ft.Container(height=1, bgcolor="#444", margin=ft.Margin(0, 10, 0, 10)),
            # 节目信息
            ft.Row([
                ft.Text("📺", size=48),
                ft.Column([
                    ft.Text("CCTV-1 综合 - 新闻联播", size=18, color="white", weight=ft.FontWeight.BOLD),
                    ft.Text("全国新闻联播节目，报道国内外重要新闻", size=14, color="#888"),
                ], expand=True, spacing=5),
            ], spacing=20),
            ft.Container(height=10),
            # 播放控制
            ft.Row([
                ft.IconButton(ft.Icons.SKIP_PREVIOUS, icon_color="#aaa"),
                ft.IconButton(ft.Icons.PLAY_CIRCLE_OUTLINE, icon_color="#fff", icon_size=40),
                ft.IconButton(ft.Icons.SKIP_NEXT, icon_color="#aaa"),
                ft.Container(width=20),
                ft.Text("00:23:15", size=14, color="#aaa", width=80),
                ft.ProgressBar(value=0.3, color="#4CAF50", bgcolor="#444", expand=True, height=6),
                ft.Text("01:30:00", size=14, color="#aaa", width=80),
                ft.Container(width=20),
                ft.IconButton(ft.Icons.VOLUME_UP, icon_color="#aaa"),
                ft.Slider(value=0.7, inactive_color="#444", active_color="#4CAF50", width=100),
                ft.Container(width=20),
                ft.Dropdown(
                    value="超清",
                    options=[
                        ft.dropdown.Option("超清"),
                        ft.dropdown.Option("高清"),
                        ft.dropdown.Option("标清"),
                    ],
                    bgcolor="#2d2d2d",
                    color="white",
                    border_color="#444",
                    width=80,
                ),
                ft.Container(width=20),
                ft.IconButton(ft.Icons.FULLSCREEN, icon_color="#aaa"),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        ], spacing=0)
    )
    
    # 添加到页面
    page.add(main_row)
    page.add(floating_panel)

# 运行应用
ft.app(target=main)