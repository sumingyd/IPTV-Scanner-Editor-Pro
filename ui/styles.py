class AppStyles:
    """应用样式管理类"""

    # 通用主题颜色
    THEME_COLORS = {
        'window': '#000000',
        'window_text': '#ffffff',
        'base': '#1a1a1a',
        'alternate_base': '#2a2a2a',
        'button': '#3a3a3a',
        'light': '#444444',
        'mid': '#555555',
        'dark': '#666666',
        'highlight': '#2a3a5a',
        'highlighted_text': '#6a9eff',
        'link': '#6a9eff',
        'link_visited': '#8a7eff',
        'tooltip_base': '#2a2a2a',
        'tooltip_text': '#f0f0f0',
        'placeholder': '#999999',
        'accent': '#4a7eff',
        'accent_hover': '#3a6eff',
        'accent_pressed': '#2a5eff',
        'success': '#4CAF50',
        'warning': '#FF9800',
        'error': '#f44336',
        'info': '#2196F3',
        'table_header': '#3a3a3a',
        'table_header_gradient_start': '#444444',
        'table_header_gradient_middle': '#3a3a3a',
        'table_header_gradient_end': '#2a2a2a',
        'table_header_text': '#ffffff',
        'table_header_hover': '#4a7eff',
        'table_border': '#555555',
        'table_grid': '#444444',
        'table_alternate': '#1a1a1a',
        'table_hover': '#2a3a5a',
        'table_selection': '#4a7eff',
        'table_selection_text': '#ffffff',
        
        # 播放器相关颜色
        'player_background': '#000000',
        'player_panel': '#2a2a2a',
        'player_panel_text': '#ffffff',
        'player_panel_secondary': '#aaaaaa',
        'player_panel_disabled': '#888888',
        'player_panel_hint': '#666666',
        'player_button': 'rgba(60, 60, 60, 0.9)',
        'player_combo': 'rgba(45, 45, 45, 0.8)',
        'player_line': '#555555',
        'player_accent': '#6a9eff',
        'player_success': '#4CAF50',
        'player_warning': '#ff6464',
        'player_slider_track': '#555555',
        'player_slider_fill': '#4CAF50',
        'player_slider_handle': '#ffffff',
        'player_volume_track': '#444444',
        'player_video_placeholder': '#1a1a1a',
        
        # 窗口透明度 (0-255, 用于无边框弹窗)
        'window_opacity': 220,
    }

    @staticmethod
    def _get_colors():
        """获取当前主题的颜色"""
        return AppStyles.THEME_COLORS

    @staticmethod
    def main_window_style() -> str:
        """主窗口样式"""
        colors = AppStyles._get_colors()
        return f"""
            QMainWindow {{
                background-color: {colors['window']};
                color: {colors['window_text']};
                font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
                font-size: 13px;
            }}
            QGroupBox {{
                border: 1px solid {colors['mid']};
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 16px;
                font-weight: 600;
                font-size: 13px;
                background-color: {colors['alternate_base']};
                color: {colors['window_text']};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
                color: {colors['window_text']};
                font-weight: 600;
            }}
            QSplitter::handle {{
                background-color: {colors['mid']};
            }}
            QSplitter::handle:hover {{
                background-color: {colors['highlight']};
            }}
            QCheckBox {{
                color: {colors['window_text']};
                font-size: 13px;
                font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
                spacing: 8px;
            }}
            
            /* SpinBox 统一样式 */
            QSpinBox {{
                border: 1px solid {colors['mid']};
                border-radius: 6px;
                padding: 6px 10px;
                padding-right: 32px;
                font-size: 13px;
                background-color: {colors['alternate_base']};
                color: {colors['window_text']};
            }}
            
            QSpinBox:focus {{
                border-color: {colors['accent']};
                outline: none;
            }}
            
            QSpinBox::up-button, QSpinBox::down-button {{
                width: 28px;
                border: none;
                border-left: 1px solid {colors['mid']};
                background-color: {colors['button']};
                min-width: 0;
                min-height: 0;
                padding: 0;
            }}
            
            QSpinBox::up-button {{
                subcontrol-origin: border;
                subcontrol-position: right top;
                border-top-right-radius: 6px;
            }}
            
            QSpinBox::down-button {{
                subcontrol-origin: border;
                subcontrol-position: right bottom;
                border-bottom-right-radius: 6px;
            }}
            
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
                background-color: {colors['accent']};
            }}
            
            QSpinBox::up-button:pressed, QSpinBox::down-button:pressed {{
                background-color: {colors['accent_pressed']};
            }}
            
            QSpinBox::up-arrow {{
                width: 12px;
                height: 12px;
                border-left: 6px solid transparent;
                border-right: 6px solid transparent;
                border-bottom: 8px solid {colors['window_text']};
                margin: 0 auto;
            }}
            
            QSpinBox::down-arrow {{
                width: 12px;
                height: 12px;
                border-left: 6px solid transparent;
                border-right: 6px solid transparent;
                border-top: 8px solid {colors['window_text']};
                margin: 0 auto;
            }}
            
            QSpinBox::up-button:hover::up-arrow {{
                border-bottom-color: {colors['accent']};
            }}
            
            QSpinBox::down-button:hover::down-arrow {{
                border-top-color: {colors['accent']};
            }}

            
            /* 滚动条统一样式 */
            QScrollBar:vertical {{
                border: none;
                background-color: {colors['alternate_base']};
                width: 10px;
                margin: 2px 0;
            }}
            
            QScrollBar::handle:vertical {{
                background-color: {colors['mid']};
                min-height: 40px;
                border-radius: 5px;
                margin: 2px;
            }}
            
            QScrollBar::handle:vertical:hover {{
                background-color: {colors['accent']};
                border-radius: 6px;
            }}
            
            QScrollBar::handle:vertical:pressed {{
                background-color: {colors['accent_pressed']};
                border-radius: 6px;
            }}
            
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
                border: none;
                background-color: transparent;
            }}
            
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background-color: transparent;
            }}
            
            QScrollBar:horizontal {{
                border: none;
                background-color: {colors['alternate_base']};
                height: 10px;
                margin: 0 2px;
            }}
            
            QScrollBar::handle:horizontal {{
                background-color: {colors['mid']};
                min-width: 40px;
                border-radius: 5px;
                margin: 2px;
            }}
            
            QScrollBar::handle:horizontal:hover {{
                background-color: {colors['accent']};
                border-radius: 6px;
            }}
            
            QScrollBar::handle:horizontal:pressed {{
                background-color: {colors['accent_pressed']};
                border-radius: 6px;
            }}
            
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                width: 0px;
                border: none;
                background-color: transparent;
            }}
            
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
                background-color: transparent;
            }}
        """



    @staticmethod
    def list_style() -> str:
        """列表样式"""
        colors = AppStyles._get_colors()
        return f"""
            QTableView {{
                border: 2px solid {colors['table_border']};
                border-radius: 6px;
                alternate-background-color: {colors['table_alternate']};
                selection-background-color: {colors['table_selection']};
                selection-color: {colors['table_selection_text']};
                gridline-color: {colors['table_grid']};
                font-size: 12px;
                font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
                background-color: {colors['alternate_base']};
            }}
            QTableView::item {{
                padding: 6px 10px;
                border-bottom: 1px solid {colors['table_grid']};
                color: {colors['window_text']};
            }}
            QTableView::item:hover {{
                background-color: {colors['table_hover']};
                border: 1px solid {colors['accent']};
                border-radius: 4px;
            }}
            QTableView::item:selected {{
                background-color: {colors['table_selection']};
                color: {colors['table_selection_text']};
                font-weight: 500;
                border: 1px solid {colors['accent_pressed']};
                border-radius: 4px;
            }}
            QTableView::item:selected:hover {{
                background-color: {colors['accent_hover']};
                border-color: {colors['accent_pressed']};
            }}
            QHeaderView {{
                background-color: {colors['table_header']};
                border: none;
            }}
            QHeaderView::section {{
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {colors['table_header_gradient_start']},
                    stop:0.5 {colors['table_header_gradient_middle']},
                    stop:1 {colors['table_header_gradient_end']});
                padding: 8px 12px;
                border: none;
                border-right: 1px solid {colors['table_border']};
                color: {colors['window_text']};
                font-weight: 600;
                font-size: 12px;
                font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
            }}
            QHeaderView::section:last {{
                border-right: none;
            }}
            QHeaderView::section:first {{
                min-width: 60px;
            }}
            QHeaderView::section:nth-child(2) {{
                min-width: 180px;
            }}
            QHeaderView::section:nth-child(3) {{
                min-width: 100px;
            }}
            QHeaderView::section:nth-child(4) {{
                min-width: 250px;
            }}
            QTableView::item:drag {{
                background-color: {colors['table_selection']};
                color: {colors['table_selection_text']};
                border: 2px dashed {colors['accent_pressed']};
                border-radius: 4px;
                opacity: 0.7;
            }}
            QTableView::item:drop {{
                background-color: {colors['table_hover']};
                border: 2px solid {colors['accent']};
                border-radius: 4px;
            }}
        """

    @staticmethod
    def statusbar_style() -> str:
        """状态栏样式"""
        colors = AppStyles._get_colors()
        return f"""
            QStatusBar {{
                background-color: {colors['player_panel']};
                color: {colors['player_panel_text']};
                padding: 4px;
            }}
        """

    @staticmethod
    def player_toolbar_style() -> str:
        """播放器工具栏样式"""
        colors = AppStyles._get_colors()
        return f"""
            QToolBar {{
                background-color: {colors['player_panel']};
                color: {colors['player_panel_text']};
                padding: 4px;
            }}
            QToolBar QPushButton {{
                background-color: {colors['player_button']};
                color: {colors['player_panel_text']};
                border: 1px solid {colors['player_line']};
                padding: 5px 10px;
                border-radius: 3px;
                margin: 2px;
            }}
            QToolBar QPushButton:hover {{
                background-color: {colors['player_line']};
            }}
        """

    @staticmethod
    def player_panel_style() -> str:
        """播放器面板样式"""
        colors = AppStyles._get_colors()
        return f"""
            QLabel {{
                border: none;
                background-color: transparent;
            }}
            QListWidget {{
                border: none;
                background-color: transparent;
            }}
            QComboBox {{
                border: none;
            }}
        """

    @staticmethod
    def player_button_style() -> str:
        """播放器按钮样式"""
        colors = AppStyles._get_colors()
        return f"""
            QToolButton {{
                color: {colors['player_panel_text']};
                font-size: 14px;
                background-color: {colors['player_button']};
                border-radius: 4px;
                border: none;
            }}
        """

    @staticmethod
    def player_slider_style() -> str:
        """播放器滑块样式"""
        colors = AppStyles._get_colors()
        return f"""
            QSlider {{
                background-color: transparent;
            }}
            QSlider::groove:horizontal {{ 
                background: {colors['player_slider_track']}; 
                height: 4px; 
                border-radius: 2px;
            }} 
            QSlider::sub-page:horizontal {{
                background: {colors['player_slider_fill']};
                height: 4px;
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{ 
                background: {colors['player_slider_handle']}; 
                width: 10px; 
                height: 10px; 
                border-radius: 5px;
                margin: -3px 0;
            }}
        """

    @staticmethod
    def player_volume_slider_style() -> str:
        """播放器音量滑块样式"""
        colors = AppStyles._get_colors()
        return f"""
            QSlider::groove:horizontal {{ 
                background: {colors['player_volume_track']}; 
                height: 4px; 
                border-radius: 2px;
            }} 
            QSlider::sub-page:horizontal {{
                background: {colors['player_slider_fill']};
                height: 4px;
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{ 
                background: {colors['player_slider_handle']}; 
                width: 12px; 
                height: 12px; 
                border-radius: 6px;
                margin: -4px 0;
            }}
        """

    @staticmethod
    def exit_catchup_button_style() -> str:
        """退出回看按钮样式"""
        colors = AppStyles._get_colors()
        return f"""
            QToolButton {{
                color: {colors['player_panel_text']};
                font-size: 12px;
                background-color: {colors['player_warning']};
                border-radius: 4px;
                border: none;
            }}
        """

    @staticmethod
    def player_label_style() -> str:
        """播放器标签样式"""
        colors = AppStyles._get_colors()
        return f"""
            QLabel {{
                color: {colors['player_panel_secondary']};
                font-size: 12px;
                background-color: transparent;
            }}
        """

    @staticmethod
    def player_channel_name_style() -> str:
        """播放器频道名称样式"""
        colors = AppStyles._get_colors()
        return f"""
            QLabel {{
                color: {colors['player_panel_text']};
                font-size: 18px;
                font-weight: bold;
                background-color: transparent;
            }}
        """

    @staticmethod
    def player_program_style() -> str:
        """播放器节目样式"""
        colors = AppStyles._get_colors()
        return f"""
            QLabel {{
                color: {colors['player_success']};
                font-size: 13px;
                background-color: transparent;
            }}
        """

    @staticmethod
    def player_program_desc_style() -> str:
        """播放器节目描述样式"""
        colors = AppStyles._get_colors()
        return f"""
            QLabel {{
                color: {colors['player_panel_secondary']};
                font-size: 14px;
                background-color: transparent;
            }}
        """

    @staticmethod
    def player_date_button_style() -> str:
        """播放器日期按钮样式"""
        colors = AppStyles._get_colors()
        return f"""
            QPushButton {{
                background-color: transparent;
                color: {colors['player_panel_disabled']};
                border: none;
                font-size: 12px;
            }}
        """

    @staticmethod
    def player_date_label_style() -> str:
        """播放器日期标签样式"""
        colors = AppStyles._get_colors()
        return f"""
            QLabel {{
                color: {colors['player_panel_text']};
                font-size: 12px;
            }}
        """

    @staticmethod
    def player_epg_title_style() -> str:
        """播放器EPG标题样式"""
        colors = AppStyles._get_colors()
        return f"""
            QLabel {{
                color: {colors['player_panel_text']};
                font-size: 14px;
                font-weight: bold;
                padding: 8px;
                background-color: transparent;
            }}
        """

    @staticmethod
    def player_group_combo_style() -> str:
        """播放器分组下拉框样式"""
        colors = AppStyles._get_colors()
        return f"""
            QComboBox {{
                background-color: {colors['player_combo']};
                color: {colors['player_panel_text']};
                padding: 4px;
                border: none;
                font-size: 12px;
            }}
        """

    @staticmethod
    def player_playlist_title_style() -> str:
        """播放器播放列表标题样式"""
        colors = AppStyles._get_colors()
        return f"""
            QLabel {{
                color: {colors['player_panel_text']};
                font-size: 14px;
                font-weight: bold;
                padding: 8px;
                background-color: transparent;
            }}
        """

    @staticmethod
    def player_line_style() -> str:
        """播放器分割线样式"""
        colors = AppStyles._get_colors()
        return f"""
            QFrame {{
                background-color: {colors['player_line']};
                max-height: 1px;
            }}
        """

    @staticmethod
    def player_video_placeholder_style() -> str:
        """播放器视频占位符样式"""
        colors = AppStyles._get_colors()
        return f"""
            QLabel {{
                font-size: 200px;
                color: {colors['player_video_placeholder']};
                background-color: transparent;
            }}
        """

    @staticmethod
    def player_empty_label_style() -> str:
        """播放器空状态标签样式"""
        colors = AppStyles._get_colors()
        return f"""
            QLabel {{
                color: {colors['player_panel_hint']};
                font-size: 12px;
                background-color: transparent;
            }}
        """

    @staticmethod
    def player_list_style() -> str:
        """播放器列表样式"""
        colors = AppStyles._get_colors()
        return f"""
            QListWidget {{
                background-color: transparent;
                color: {colors['player_panel_text']};
                border: none;
                padding: 5px;
            }}
        """

    @staticmethod
    def player_progress_label_style() -> str:
        """播放器进度标签样式"""
        colors = AppStyles._get_colors()
        return f"""
            QLabel {{
                color: {colors['player_panel_disabled']};
                font-size: 11px;
                background-color: transparent;
            }}
        """

    @staticmethod
    def player_channel_logo_style() -> str:
        """播放器频道LOGO样式"""
        return """
            QLabel {
                font-size: 24px;
                background-color: transparent;
            }
        """

    @staticmethod
    def player_background_style() -> str:
        """播放器背景样式"""
        colors = AppStyles._get_colors()
        return f"""
            background-color: {colors['player_background']};
        """

    @staticmethod
    def player_menu_bar_style() -> str:
        """播放器菜单栏样式"""
        colors = AppStyles._get_colors()
        return f"""
            QMenuBar {{
                background-color: {colors['player_panel']};
                color: {colors['player_panel_text']};
                padding: 2px;
            }}
            QMenuBar::item {{
                padding: 4px 8px;
                margin: 2px;
                border-radius: 4px;
            }}
            QMenuBar::item:selected {{
                background-color: {colors['player_line']};
            }}
            QMenu {{
                background-color: {colors['player_panel']};
                color: {colors['player_panel_text']};
                border-radius: 4px;
                padding: 2px;
            }}
            QMenu::item {{
                padding: 4px 20px;
                margin: 2px;
                border-radius: 4px;
            }}
            QMenu::item:selected {{
                background-color: {colors['player_line']};
            }}
        """

    @staticmethod
    def scan_window_style() -> str:
        """扫描频道窗口样式"""
        return AppStyles.popup_dialog_style()

    @staticmethod
    def progress_style() -> str:
        """进度条样式"""
        colors = AppStyles._get_colors()
        return f"""
            QProgressBar {{
                border: 1px solid {colors['mid']};
                border-radius: 6px;
                text-align: center;
                height: 24px;
                background-color: {colors['alternate_base']};
                font-size: 11px;
                font-weight: 500;
                font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
                color: {colors['window_text']};
            }}
            QProgressBar::chunk {{
                background-color: {colors['accent']};
                border-radius: 5px;
                margin: 1px;
            }}
        """

    @staticmethod
    def toolbar_button_style() -> str:
        """工具栏按钮样式"""
        colors = AppStyles._get_colors()
        return f"""
            QToolButton {{
                border: 1px solid {colors['mid']};
                border-radius: 4px;
                padding: 4px 8px;
                margin: 1px;
                background-color: {colors['button']};
                min-width: 60px;
                min-height: 28px;
                color: {colors['window_text']};
                font-size: 12px;
                font-weight: 500;
                font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
            }}
            QToolButton:hover {{
                background-color: {colors['light']};
                border-color: {colors['accent']};
                color: {colors['accent']};
            }}
            QToolButton:pressed {{
                background-color: {colors['dark']};
                color: {colors['accent_pressed']};
            }}
            QToolButton::menu-indicator {{
                width: 0px;
            }}
        """


    @staticmethod
    def drag_list_style() -> str:
        """拖拽列表样式"""
        colors = AppStyles._get_colors()
        return f"""
            QListWidget {{
                border: 1px solid {colors['mid']};
                border-radius: 8px;
                padding: 4px;
                background-color: {colors['alternate_base']};
                font-size: 13px;
            }}
            QListWidget::item {{
                border: 1px solid transparent;
                border-radius: 6px;
                padding: 8px 12px;
                margin: 2px;
                background-color: {colors['light']};
                color: {colors['window_text']};
            }}
            QListWidget::item:hover {{
                background-color: {colors['highlight']};
                border: 1px solid {colors['mid']};
            }}
            QListWidget::item:selected {{
                background-color: {colors['accent']};
                color: white;
                border: 1px solid {colors['accent_pressed']};
            }}
            QListWidget::item:selected:hover {{
                background-color: {colors['accent_hover']};
            }}
        """

    @staticmethod
    def drag_hint_label_style() -> str:
        """拖拽提示标签样式"""
        colors = AppStyles._get_colors()
        return f"""
            QLabel {{
                color: {colors['accent']};
                font-size: 12px;
                padding: 8px 12px;
                background-color: {colors['light']};
                border-radius: 6px;
                font-weight: 500;
                border: 1px solid {colors['mid']};
            }}
        """

    @staticmethod
    def group_hint_label_style() -> str:
        """分组提示标签样式"""
        colors = AppStyles._get_colors()
        return f"""
            QLabel {{
                color: {colors['window_text']};
                font-size: 12px;
                padding: 8px 12px;
                background-color: {colors['light']};
                border-radius: 6px;
                font-weight: 500;
                border: 1px solid {colors['mid']};
                opacity: 0.8;
            }}
        """

    @staticmethod
    def statusbar_error_style() -> str:
        """状态栏错误/警告样式"""
        colors = AppStyles._get_colors()
        return f"""
            QStatusBar {{{{
                color: {colors['error']};
                font-weight: bold;
            }}}}
        """


    @staticmethod
    def apply_button_style() -> str:
        """应用按钮样式"""
        colors = AppStyles._get_colors()
        return f"""
            QPushButton {{{{
                background-color: {colors['success']};
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }}}}
            QPushButton:hover {{{{
                background-color: {colors['success']};
                opacity: 0.9;
            }}}}
        """

    @staticmethod
    def cancel_button_style() -> str:
        """取消按钮样式"""
        colors = AppStyles._get_colors()
        return f"""
            QPushButton {{{{
                background-color: {colors['error']};
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }}}}
            QPushButton:hover {{{{
                background-color: {colors['error']};
                opacity: 0.9;
            }}}}
        """


    @staticmethod
    def secondary_label_style() -> str:
        """次要标签样式"""
        colors = AppStyles._get_colors()
        return f"""
            QLabel {{{{
                color: {colors['window_text']};
                padding: 0 5px;
                font-size: 13px;
                font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
                opacity: 0.8;
            }}}}
        """


    @staticmethod
    def tab_widget_style() -> str:
        """标签页控件样式"""
        colors = AppStyles._get_colors()
        return f"""
            QTabWidget {{
                background-color: {colors['window']};
                border: 1px solid {colors['mid']};
                border-radius: 8px;
                font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
            }}
            QTabWidget::pane {{
                border: 1px solid {colors['mid']};
                border-radius: 0 0 8px 8px;
                background-color: {colors['window']};
                margin-top: -1px;
            }}
            QTabBar {{
                background-color: {colors['alternate_base']};
                border-bottom: 1px solid {colors['mid']};
                border-radius: 8px 8px 0 0;
            }}
            QTabBar::tab {{
                background-color: {colors['alternate_base']};
                border: 1px solid {colors['mid']};
                border-bottom: none;
                border-radius: 6px 6px 0 0;
                padding: 8px 16px;
                margin-right: 4px;
                margin-top: 4px;
                font-size: 13px;
                font-weight: 500;
                color: {colors['window_text']};
                opacity: 0.8;
            }}
            QTabBar::tab:selected {{
                background-color: {colors['window']};
                border-color: {colors['mid']};
                border-bottom-color: {colors['window']};
                color: {colors['accent']};
                font-weight: 600;
                opacity: 1.0;
            }}
            QTabBar::tab:hover:!selected {{
                background-color: {colors['light']};
                color: {colors['accent']};
                opacity: 0.9;
            }}
            QTabBar::tab:first {{
                margin-left: 4px;
            }}
            QTabBar::tab:last {{
                margin-right: 0;
            }}
        """

    # 通用样式
    @staticmethod
    def common_button_style() -> str:
        """通用按钮样式"""
        colors = AppStyles._get_colors()
        return f"""
            QPushButton {{
                background-color: {colors['button']};
                color: {colors['window_text']};
                border: 1px solid {colors['mid']};
                border-radius: 4px;
                padding: 8px 16px;
                min-width: 100px;
                font-weight: 500;
                font-size: 12px;
                font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
            }}
            QPushButton:hover {{
                background-color: {colors['light']};
                border-color: {colors['accent']};
            }}
            QPushButton:pressed {{
                background-color: {colors['dark']};
                border-color: {colors['accent_pressed']};
            }}
            QPushButton:disabled {{
                background-color: {colors['light']};
                border-color: {colors['mid']};
                color: {colors['placeholder']};
            }}
        """

    @staticmethod
    def common_label_style() -> str:
        """通用标签样式"""
        colors = AppStyles._get_colors()
        return f"""
            QLabel {{
                color: {colors['window_text']};
                font-size: 12px;
                font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
                background-color: transparent;
            }}
        """

    @staticmethod
    def common_line_edit_style() -> str:
        """通用输入框样式"""
        colors = AppStyles._get_colors()
        return f"""
            QLineEdit {{
                background-color: {colors['alternate_base']};
                color: {colors['window_text']};
                border: 1px solid {colors['mid']};
                border-radius: 4px;
                padding: 6px;
                font-size: 12px;
                font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
            }}
            QLineEdit:focus {{
                border-color: {colors['accent']};
                outline: none;
            }}
            QLineEdit:disabled {{
                background-color: {colors['light']};
                border-color: {colors['mid']};
                color: {colors['placeholder']};
            }}
        """

    @staticmethod
    def common_combo_box_style() -> str:
        """通用下拉框样式"""
        colors = AppStyles._get_colors()
        return f"""
            QComboBox {{
                background-color: {colors['alternate_base']};
                color: {colors['window_text']};
                border: 1px solid {colors['mid']};
                border-radius: 4px;
                padding: 6px;
                font-size: 12px;
                font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
                min-width: 120px;
            }}
            QComboBox:focus {{
                border-color: {colors['accent']};
                outline: none;
            }}
            QComboBox:disabled {{
                background-color: {colors['light']};
                border-color: {colors['mid']};
                color: {colors['placeholder']};
            }}
            QComboBox::drop-down {{
                border: none;
                padding-right: 6px;
            }}
            QComboBox::down-arrow {{
                width: 8px;
                height: 8px;
                color: {colors['window_text']};
            }}
            QComboBox QAbstractItemView {{
                background-color: {colors['alternate_base']};
                color: {colors['window_text']};
                border: 1px solid {colors['mid']};
                border-radius: 4px;
                padding: 4px;
            }}
            QComboBox QAbstractItemView::item {{
                padding: 6px 10px;
                margin: 2px 0;
            }}
            QComboBox QAbstractItemView::item:hover {{
                background-color: {colors['accent']};
                color: white;
            }}
        """

    @staticmethod
    def table_style() -> str:
        """表格样式"""
        colors = AppStyles._get_colors()
        return f"""
            QTableView, QTableWidget {{
                border: 2px solid {colors['table_border']};
                border-radius: 6px;
                alternate-background-color: {colors['table_alternate']};
                selection-background-color: {colors['table_selection']};
                selection-color: {colors['table_selection_text']};
                gridline-color: {colors['table_grid']};
                font-size: 12px;
                font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
                background-color: {colors['alternate_base']};
            }}
            QTableView::item, QTableWidget::item {{
                padding: 6px 10px;
                border-bottom: 1px solid {colors['table_grid']};
                color: {colors['window_text']};
            }}
            QTableView::item:hover, QTableWidget::item:hover {{
                background-color: {colors['table_hover']};
                border: 1px solid {colors['accent']};
                border-radius: 4px;
            }}
            QTableView::item:selected, QTableWidget::item:selected {{
                background-color: {colors['table_selection']};
                color: {colors['table_selection_text']};
                font-weight: 500;
                border: 1px solid {colors['accent_pressed']};
                border-radius: 4px;
            }}
            QTableView::item:selected:hover, QTableWidget::item:selected:hover {{
                background-color: {colors['accent_hover']};
                border-color: {colors['accent_pressed']};
            }}
            QHeaderView {{
                background-color: {colors['table_header']};
                border: none;
            }}
            QHeaderView::section {{
                background-color: {colors['table_header']};
                color: {colors['table_header_text']};
                padding: 8px 12px;
                border: none;
                border-right: 1px solid {colors['table_grid']};
                font-weight: 600;
                font-size: 12px;
            }}
            QHeaderView::section:last {{
                border-right: none;
            }}
            QHeaderView::section:hover {{
                background-color: {colors['table_header_hover']};
            }}
        """

    @staticmethod
    def common_check_box_style() -> str:
        """通用复选框样式"""
        colors = AppStyles._get_colors()
        return f"""
            QCheckBox {{
                color: {colors['window_text']};
                font-size: 12px;
                font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border: 2px solid {colors['mid']};
                border-radius: 3px;
                background-color: {colors['alternate_base']};
            }}
            QCheckBox::indicator:checked {{
                background-color: {colors['accent']};
                border-color: {colors['accent']};
            }}
            QCheckBox::indicator:hover {{
                border-color: {colors['accent']};
            }}
        """

    @staticmethod
    def common_group_box_style() -> str:
        """通用分组框样式"""
        colors = AppStyles._get_colors()
        return f"""
            QGroupBox {{
                background-color: {colors['alternate_base']};
                color: {colors['window_text']};
                border: 1px solid {colors['mid']};
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 16px;
                font-weight: 600;
                font-size: 13px;
                font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
                color: {colors['window_text']};
                font-weight: 600;
                font-size: 13px;
                font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
            }}
        """

    @staticmethod
    def common_title_style() -> str:
        """通用标题文字样式"""
        colors = AppStyles._get_colors()
        return f"""
            QLabel {{
                color: {colors['window_text']};
                font-size: 16px;
                font-weight: bold;
                font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
                background-color: transparent;
            }}
        """

    @staticmethod
    def common_link_style() -> str:
        """通用链接文字样式"""
        colors = AppStyles._get_colors()
        return f"""
            QLabel {{
                color: {colors['link']};
                font-size: 12px;
                font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
                background-color: transparent;
                text-decoration: underline;
            }}
            QLabel:hover {{
                color: {colors['accent_hover']};
            }}
        """

    @staticmethod
    def common_area_style() -> str:
        """通用窗口内区域块样式"""
        colors = AppStyles._get_colors()
        return f"""
            QWidget {{
                background-color: {colors['alternate_base']};
                border: 1px solid {colors['mid']};
                border-radius: 8px;
                padding: 12px;
            }}
        """

    # 弹窗样式
    @staticmethod
    def popup_dialog_style() -> str:
        """通用弹窗窗口样式 - 支持无边框圆角窗口"""
        colors = AppStyles._get_colors()
        # 使用主题中的透明度设置
        opacity = colors.get('window_opacity', 220) / 255.0
        window_bg = f"rgba(0, 0, 0, {opacity:.2f})"  # 半透明黑色背景
        return f"""
            /* 窗口样式 - 用于无边框圆角窗口 */
            QDialog {{
                background-color: {window_bg};
                color: {colors['window_text']};
                border: 1px solid {colors['mid']};
                border-radius: 12px;
                font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
            }}
            
            /* 当使用 WA_TranslucentBackground 时，需要给内容widget设置背景 */
            QDialog > QWidget {{
                background-color: {window_bg};
                border-radius: 12px;
            }}
            
            /* 标签样式 */
            QDialog QLabel {{
                color: {colors['window_text']};
                font-size: 13px;
                opacity: 0.9;
            }}
            
            /* 按钮样式 */
            QDialog QPushButton {{
                min-width: 70px;
                padding: 6px 12px;
                border-radius: 4px;
                font-size: 12px;
                font-weight: 500;
                background-color: {colors['button']};
                color: {colors['window_text']};
                border: 1px solid {colors['mid']};
            }}
            
            QDialog QPushButton:hover {{
                background-color: {colors['light']};
                border-color: {colors['accent']};
            }}
            
            QDialog QPushButton:pressed {{
                background-color: {colors['dark']};
                border-color: {colors['accent_pressed']};
            }}
            
            /* 分组框样式 */
            QDialog QGroupBox {{
                border: 1px solid {colors['mid']};
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 18px;
                background-color: {colors['alternate_base']};
            }}
            
            QDialog QGroupBox::title {{
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
                color: {colors['window_text']};
                font-weight: 600;
                font-size: 13px;
            }}
            
            /* 输入框样式 - 不包含 SpinBox，让它使用默认样式 */
            QDialog QLineEdit, QDialog QComboBox {{
                border: 1px solid {colors['mid']};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 13px;
                background-color: {colors['alternate_base']};
                color: {colors['window_text']};
            }}
            
            QDialog QLineEdit:focus, QDialog QComboBox:focus {{
                border-color: {colors['accent']};
                outline: none;
            }}
            
            /* 下拉列表样式 */
            QDialog QComboBox QAbstractItemView {{
                background-color: {colors['window']};
                color: {colors['window_text']};
                border: 1px solid {colors['mid']};
                border-radius: 4px;
            }}
            
            /* 复选框样式 */
            QDialog QCheckBox {{
                color: {colors['window_text']};
                font-size: 13px;
                font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
                spacing: 8px;
            }}
            
            QDialog QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border: 2px solid {colors['mid']};
                border-radius: 4px;
                background-color: {colors['alternate_base']};
            }}
            
            QDialog QCheckBox::indicator:checked {{
                background-color: {colors['accent']};
                border-color: {colors['accent']};
            }}
            
            QDialog QCheckBox::indicator:hover {{
                border-color: {colors['accent']};
            }}
            
            QDialog QCheckBox::indicator:pressed {{
                background-color: {colors['accent_pressed']};
                border-color: {colors['accent_pressed']};
            }}
            
            /* 文本编辑框样式 */
            QDialog QTextEdit {{
                border: 1px solid {colors['mid']};
                border-radius: 6px;
                padding: 10px;
                font-size: 13px;
                background-color: {colors['alternate_base']};
                color: {colors['window_text']};
            }}
            
            QDialog QTextEdit:focus {{
                border-color: {colors['accent']};
                outline: none;
            }}
        """

    @staticmethod
    def dialog_style() -> str:
        """对话框通用样式"""
        return AppStyles.popup_dialog_style()

    @staticmethod
    def player_settings_dialog_style() -> str:
        """播放器设置对话框样式"""
        return AppStyles.popup_dialog_style()

    @staticmethod
    def about_dialog_style() -> str:
        """关于窗口样式"""
        return AppStyles.popup_dialog_style()

    @staticmethod
    def side_panel_style() -> str:
        """侧边栏面板样式（用于扫描设置和频道编辑面板）"""
        colors = AppStyles._get_colors()
        return f"""
            QWidget {{
                background-color: {colors['alternate_base']};
                border-radius: 8px;
            }}
        """

    @staticmethod
    def section_title_style() -> str:
        """区域标题样式"""
        colors = AppStyles._get_colors()
        return f"""
            QLabel {{
                font-size: 13px;
                font-weight: bold;
                color: {colors['window_text']};
            }}
        """

    @staticmethod
    def small_label_style() -> str:
        """小标签样式"""
        colors = AppStyles._get_colors()
        return f"""
            QLabel {{
                font-size: 11px;
                color: {colors['window_text']};
            }}
        """

    @staticmethod
    def hint_label_style() -> str:
        """提示标签样式（用于地址格式提示等）"""
        colors = AppStyles._get_colors()
        return f"""
            QLabel {{
                font-size: 10px;
                color: {colors['mid']};
            }}
        """

    @staticmethod
    def get_theme_name() -> str:
        """获取当前主题名称，用于主题切换功能"""
        return "默认主题"

    @staticmethod
    def get_theme_styles(theme_name: str = None) -> dict:
        """获取指定主题的所有样式，用于主题切换功能"""
        if theme_name is None:
            theme_name = AppStyles.get_theme_name()
        
        # 这里可以根据主题名称返回不同的样式配置
        # 目前只返回默认样式
        return {{
            'common_button': AppStyles.common_button_style(),
            'common_label': AppStyles.common_label_style(),
            'common_line_edit': AppStyles.common_line_edit_style(),
            'common_check_box': AppStyles.common_check_box_style(),
            'common_group_box': AppStyles.common_group_box_style(),
            'common_title': AppStyles.common_title_style(),
            'common_link': AppStyles.common_link_style(),
            'common_area': AppStyles.common_area_style(),
            'main_window': AppStyles.main_window_style(),
            'scan_window': AppStyles.scan_window_style(),
            'dialog': AppStyles.dialog_style(),
            'about_dialog': AppStyles.about_dialog_style(),
            'player_settings_dialog': AppStyles.player_settings_dialog_style(),
            'player_menu_bar': AppStyles.player_menu_bar_style(),
            'player_toolbar': AppStyles.player_toolbar_style(),
            'player_panel': AppStyles.player_panel_style(),
            'player_button': AppStyles.player_button_style(),
            'player_slider': AppStyles.player_slider_style(),
            'player_volume_slider': AppStyles.player_volume_slider_style(),
            'exit_catchup_button': AppStyles.exit_catchup_button_style(),
            'player_label': AppStyles.player_label_style(),
            'player_channel_name': AppStyles.player_channel_name_style(),
            'player_program': AppStyles.player_program_style(),
            'player_program_desc': AppStyles.player_program_desc_style(),
            'player_date_button': AppStyles.player_date_button_style(),
            'player_date_label': AppStyles.player_date_label_style(),
            'player_epg_title': AppStyles.player_epg_title_style(),
            'player_group_combo': AppStyles.player_group_combo_style(),
            'player_playlist_title': AppStyles.player_playlist_title_style(),
            'player_line': AppStyles.player_line_style(),
            'player_video_placeholder': AppStyles.player_video_placeholder_style(),
            'player_empty_label': AppStyles.player_empty_label_style(),
            'player_list': AppStyles.player_list_style(),
            'player_progress_label': AppStyles.player_progress_label_style(),
            'player_channel_logo': AppStyles.player_channel_logo_style(),
            'player_background': AppStyles.player_background_style(),
            'list': AppStyles.list_style(),
            'statusbar': AppStyles.statusbar_style(),
            'statusbar_error': AppStyles.statusbar_error_style(),
            'progress': AppStyles.progress_style(),
            'toolbar_button': AppStyles.toolbar_button_style(),
            'drag_list': AppStyles.drag_list_style(),
            'drag_hint_label': AppStyles.drag_hint_label_style(),
            'group_hint_label': AppStyles.group_hint_label_style(),
            'apply_button': AppStyles.apply_button_style(),
            'cancel_button': AppStyles.cancel_button_style(),
            'secondary_label': AppStyles.secondary_label_style(),
            'tab_widget': AppStyles.tab_widget_style(),
        }}
