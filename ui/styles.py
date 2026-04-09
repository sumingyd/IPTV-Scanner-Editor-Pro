class AppStyles:
    """应用样式管理类 - 支持多主题"""

    _current_theme = 'dark'

    THEME_COLORS = {
        'dark': {
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
            'window_opacity': 220,
            'shadow_light': 'rgba(255,255,255,0.05)',
            'shadow_dark': 'rgba(0,0,0,0.4)',
            'neumorphic_light': '#323232',
            'neumorphic_dark': '#0a0a0a',
        },
        'light': {
            'window': '#f0f0f0',
            'window_text': '#333333',
            'base': '#ffffff',
            'alternate_base': '#e8e8e8',
            'button': '#d0d0d0',
            'light': '#e0e0e0',
            'mid': '#c0c0c0',
            'dark': '#a0a0a0',
            'highlight': '#cce0ff',
            'highlighted_text': '#2a6eff',
            'link': '#2a6eff',
            'link_visited': '#6a5eff',
            'tooltip_base': '#ffffff',
            'tooltip_text': '#333333',
            'placeholder': '#999999',
            'accent': '#2a6eff',
            'accent_hover': '#1a5eff',
            'accent_pressed': '#0a4eff',
            'success': '#4CAF50',
            'warning': '#FF9800',
            'error': '#f44336',
            'info': '#2196F3',
            'table_header': '#d8d8d8',
            'table_header_gradient_start': '#e8e8e8',
            'table_header_gradient_middle': '#d8d8d8',
            'table_header_gradient_end': '#c8c8c8',
            'table_header_text': '#333333',
            'table_header_hover': '#2a6eff',
            'table_border': '#c0c0c0',
            'table_grid': '#d0d0d0',
            'table_alternate': '#f5f5f5',
            'table_hover': '#cce0ff',
            'table_selection': '#2a6eff',
            'table_selection_text': '#ffffff',
            'player_background': '#e0e0e0',
            'player_panel': '#f0f0f0',
            'player_panel_text': '#333333',
            'player_panel_secondary': '#666666',
            'player_panel_disabled': '#999999',
            'player_panel_hint': '#aaaaaa',
            'player_button': 'rgba(200, 200, 200, 0.9)',
            'player_combo': 'rgba(220, 220, 220, 0.8)',
            'player_line': '#c0c0c0',
            'player_accent': '#2a6eff',
            'player_success': '#4CAF50',
            'player_warning': '#ff6464',
            'player_slider_track': '#c0c0c0',
            'player_slider_fill': '#2a6eff',
            'player_slider_handle': '#333333',
            'player_volume_track': '#d0d0d0',
            'player_video_placeholder': '#e0e0e0',
            'window_opacity': 240,
            'shadow_light': 'rgba(255,255,255,0.8)',
            'shadow_dark': 'rgba(0,0,0,0.12)',
            'neumorphic_light': '#ffffff',
            'neumorphic_dark': '#d0d0d0',
        },
        'neumorphic_dark': {
            'window': '#1e1e2e',
            'window_text': '#e0e0f0',
            'base': '#252538',
            'alternate_base': '#2a2a3d',
            'button': '#2a2a3d',
            'light': '#323248',
            'mid': '#3a3a50',
            'dark': '#454560',
            'highlight': '#3a3a5a',
            'highlighted_text': '#8a9eff',
            'link': '#8a9eff',
            'link_visited': '#a08aff',
            'tooltip_base': '#2a2a3d',
            'tooltip_text': '#e0e0f0',
            'placeholder': '#707090',
            'accent': '#7c8aff',
            'accent_hover': '#6c7aef',
            'accent_pressed': '#5c6adf',
            'success': '#6bcf7f',
            'warning': '#ffb060',
            'error': '#ff6b6b',
            'info': '#5ca0ff',
            'table_header': '#2a2a3d',
            'table_header_gradient_start': '#323248',
            'table_header_gradient_middle': '#2a2a3d',
            'table_header_gradient_end': '#222236',
            'table_header_text': '#c0c0e0',
            'table_header_hover': '#7c8aff',
            'table_border': '#3a3a50',
            'table_grid': '#323248',
            'table_alternate': '#222236',
            'table_hover': '#3a3a5a',
            'table_selection': '#5c6adf',
            'table_selection_text': '#ffffff',
            'player_background': '#1a1a28',
            'player_panel': '#252538',
            'player_panel_text': '#e0e0f0',
            'player_panel_secondary': '#9090b0',
            'player_panel_disabled': '#606080',
            'player_panel_hint': '#505070',
            'player_button': 'rgba(42, 42, 61, 0.95)',
            'player_combo': 'rgba(37, 37, 56, 0.9)',
            'player_line': '#3a3a50',
            'player_accent': '#8a9eff',
            'player_success': '#6bcf7f',
            'player_warning': '#ff6b6b',
            'player_slider_track': '#3a3a50',
            'player_slider_fill': '#7c8aff',
            'player_slider_handle': '#e0e0f0',
            'player_volume_track': '#323248',
            'player_video_placeholder': '#1a1a28',
            'window_opacity': 230,
            'shadow_light': 'rgba(60,60,90,0.3)',
            'shadow_dark': 'rgba(0,0,0,0.6)',
            'neumorphic_light': '#303048',
            'neumorphic_dark': '#18182a',
        },
        'neumorphic_light': {
            'window': '#e0e5ec',
            'window_text': '#44476a',
            'base': '#e0e5ec',
            'alternate_base': '#d1d9e6',
            'button': '#d1d9e6',
            'light': '#e0e5ec',
            'mid': '#b8bec7',
            'dark': '#a0a6b0',
            'highlight': '#d6e4ff',
            'highlighted_text': '#4a6eff',
            'link': '#4a6eff',
            'link_visited': '#6a5eef',
            'tooltip_base': '#e0e5ec',
            'tooltip_text': '#44476a',
            'placeholder': '#9ba4b5',
            'accent': '#4a6eff',
            'accent_hover': '#3a5eef',
            'accent_pressed': '#2a4edf',
            'success': '#4caf50',
            'warning': '#ff9800',
            'error': '#f44336',
            'info': '#2196f3',
            'table_header': '#d1d9e6',
            'table_header_gradient_start': '#e0e5ec',
            'table_header_gradient_middle': '#d1d9e6',
            'table_header_gradient_end': '#c8d0da',
            'table_header_text': '#44476a',
            'table_header_hover': '#4a6eff',
            'table_border': '#b8bec7',
            'table_grid': '#c8d0da',
            'table_alternate': '#e8ecf2',
            'table_hover': '#d6e4ff',
            'table_selection': '#4a6eff',
            'table_selection_text': '#ffffff',
            'player_background': '#d1d9e6',
            'player_panel': '#e0e5ec',
            'player_panel_text': '#44476a',
            'player_panel_secondary': '#7a7f9a',
            'player_panel_disabled': '#9ba4b5',
            'player_panel_hint': '#b0b5c5',
            'player_button': 'rgba(209, 217, 230, 0.95)',
            'player_combo': 'rgba(224, 229, 236, 0.9)',
            'player_line': '#b8bec7',
            'player_accent': '#4a6eff',
            'player_success': '#4caf50',
            'player_warning': '#ff6464',
            'player_slider_track': '#b8bec7',
            'player_slider_fill': '#4a6eff',
            'player_slider_handle': '#44476a',
            'player_volume_track': '#c8d0da',
            'player_video_placeholder': '#d1d9e6',
            'window_opacity': 245,
            'shadow_light': 'rgba(255,255,255,0.75)',
            'shadow_dark': 'rgba(163,177,198,0.6)',
            'neumorphic_light': '#e8edf4',
            'neumorphic_dark': '#c8cdd4',
        },
    }

    @staticmethod
    def _get_colors():
        return AppStyles.THEME_COLORS.get(AppStyles._current_theme, AppStyles.THEME_COLORS['dark'])

    @staticmethod
    def set_theme(theme_name):
        AppStyles._current_theme = theme_name

    @staticmethod
    def get_theme():
        return AppStyles._current_theme

    @staticmethod
    def get_available_themes():
        return list(AppStyles.THEME_COLORS.keys())

    @staticmethod
    def is_neumorphic():
        return AppStyles._current_theme in ('neumorphic_dark', 'neumorphic_light')

    @staticmethod
    def _neumorphic_inset():
        c = AppStyles._get_colors()
        return f"box-shadow: inset 3px 3px 6px {c['shadow_dark']}, inset -3px -3px 6px {c['shadow_light']};"

    @staticmethod
    def _neumorphic_raised():
        c = AppStyles._get_colors()
        return f"box-shadow: 4px 4px 8px {c['shadow_dark']}, -4px -4px 8px {c['shadow_light']};"

    @staticmethod
    def main_window_style() -> str:
        colors = AppStyles._get_colors()
        neo = AppStyles.is_neumorphic()
        btn_bg = colors['neumorphic_light'] if neo else colors['button']
        btn_hover = colors['neumorphic_dark'] if neo else colors['light']
        btn_pressed = colors['neumorphic_dark'] if neo else colors['dark']
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
                background-color: {btn_bg};
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
            QHeaderView::section:first {{ min-width: 60px; }}
            QHeaderView::section:nth-child(2) {{ min-width: 180px; }}
            QHeaderView::section:nth-child(3) {{ min-width: 100px; }}
            QHeaderView::section:nth-child(4) {{ min-width: 250px; }}
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
        colors = AppStyles._get_colors()
        return f"""
            QLabel {{
                color: {colors['player_panel_text']};
                font-size: 12px;
            }}
        """

    @staticmethod
    def player_epg_title_style() -> str:
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
        colors = AppStyles._get_colors()
        return f"""
            QFrame {{
                background-color: {colors['player_line']};
                max-height: 1px;
            }}
        """

    @staticmethod
    def player_video_placeholder_style() -> str:
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
        return """
            QLabel {
                font-size: 24px;
                background-color: transparent;
            }
        """

    @staticmethod
    def player_background_style() -> str:
        colors = AppStyles._get_colors()
        return f"background-color: {colors['player_background']};"

    @staticmethod
    def player_menu_bar_style() -> str:
        colors = AppStyles._get_colors()
        neo = AppStyles.is_neumorphic()
        menu_bg = colors['base']
        menu_text = colors['window_text']
        menu_hover_bg = colors['neumorphic_light'] if neo else colors['highlight']
        menu_hover_text = colors['accent'] if neo else colors['highlighted_text']
        menu_border = colors['shadow_dark'] if neo else colors['mid']
        if neo:
            return f"""
                QMenuBar {{
                    background-color: {menu_bg};
                    color: {menu_text};
                    padding: 2px;
                    border-bottom: 2px solid {colors['shadow_dark']};
                }}
                QMenuBar::item {{
                    padding: 4px 10px;
                    margin: 2px;
                    border-radius: 6px;
                    background-color: {menu_bg};
                }}
                QMenuBar::item:selected {{
                    color: {menu_hover_text};
                    background-color: {menu_hover_bg};
                    border: 1px solid {colors['shadow_light']};
                }}
                QMenu {{
                    background-color: {menu_bg};
                    color: {menu_text};
                    border-radius: 8px;
                    padding: 4px;
                    border: 1px solid {menu_border};
                }}
                QMenu::item {{
                    padding: 6px 24px;
                    margin: 2px;
                    border-radius: 6px;
                }}
                QMenu::item:selected {{
                    color: {menu_hover_text};
                    background-color: {menu_hover_bg};
                    border: 1px solid {colors['shadow_light']};
                }}
                QMenu::separator {{
                    height: 1px;
                    background-color: {colors['shadow_dark']};
                    margin: 4px 8px;
                }}
            """
        return f"""
            QMenuBar {{
                background-color: {menu_bg};
                color: {menu_text};
                padding: 2px;
            }}
            QMenuBar::item {{
                padding: 4px 8px;
                margin: 2px;
                border-radius: 4px;
            }}
            QMenuBar::item:selected {{
                background-color: {menu_hover_bg};
                color: {menu_hover_text};
            }}
            QMenu {{
                background-color: {menu_bg};
                color: {menu_text};
                border-radius: 4px;
                padding: 2px;
                border: 1px solid {menu_border};
            }}
            QMenu::item {{
                padding: 4px 20px;
                margin: 2px;
                border-radius: 4px;
            }}
            QMenu::item:selected {{
                background-color: {menu_hover_bg};
                color: {menu_hover_text};
            }}
        """

    @staticmethod
    def popup_dialog_style() -> str:
        colors = AppStyles._get_colors()
        opacity = colors.get('window_opacity', 220) / 255.0
        window_bg = colors['player_panel']
        neo = AppStyles.is_neumorphic()
        btn_bg = colors['neumorphic_light'] if neo else colors['button']
        btn_hover = colors['neumorphic_dark'] if neo else colors['light']
        btn_pressed = colors['neumorphic_dark'] if neo else colors['dark']
        input_bg = colors['neumorphic_light'] if neo else colors['alternate_base']
        return f"""
            QDialog {{
                background-color: {window_bg};
                color: {colors['window_text']};
                border: 1px solid {colors['mid']};
                border-radius: 12px;
                font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
            }}
            QDialog > QWidget {{
                background-color: {window_bg};
                border-radius: 12px;
            }}
            QDialog QLabel {{
                color: {colors['window_text']};
                font-size: 13px;
            }}
            QDialog QPushButton {{
                min-width: 70px;
                padding: 6px 12px;
                border-radius: 4px;
                font-size: 12px;
                font-weight: 500;
                background-color: {btn_bg};
                color: {colors['window_text']};
                border: 1px solid {colors['mid']};
            }}
            QDialog QPushButton:hover {{
                background-color: {btn_hover};
                border-color: {colors['accent']};
            }}
            QDialog QPushButton:pressed {{
                background-color: {btn_pressed};
                border-color: {colors['accent_pressed']};
            }}
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
            QDialog QLineEdit, QDialog QComboBox {{
                border: 1px solid {colors['mid']};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 13px;
                background-color: {input_bg};
                color: {colors['window_text']};
            }}
            QDialog QLineEdit:focus, QDialog QComboBox:focus {{
                border-color: {colors['accent']};
                outline: none;
            }}
            QDialog QComboBox QAbstractItemView {{
                background-color: {colors['window']};
                color: {colors['window_text']};
                border: 1px solid {colors['mid']};
                border-radius: 4px;
            }}
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
                background-color: {input_bg};
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
            QDialog QTextEdit {{
                border: 1px solid {colors['mid']};
                border-radius: 6px;
                padding: 10px;
                font-size: 13px;
                background-color: {input_bg};
                color: {colors['window_text']};
            }}
            QDialog QTextEdit:focus {{
                border-color: {colors['accent']};
                outline: none;
            }}
        """

    @staticmethod
    def dialog_style() -> str:
        return AppStyles.popup_dialog_style()

    @staticmethod
    def progress_style() -> str:
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
        colors = AppStyles._get_colors()
        return f"""
            QStatusBar {{{{
                color: {colors['error']};
                font-weight: bold;
            }}}}
        """

    @staticmethod
    def apply_button_style() -> str:
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

    @staticmethod
    def common_button_style() -> str:
        colors = AppStyles._get_colors()
        neo = AppStyles.is_neumorphic()
        btn_bg = colors['neumorphic_light'] if neo else colors['button']
        btn_hover = colors['neumorphic_dark'] if neo else colors['light']
        btn_pressed = colors['neumorphic_dark'] if neo else colors['dark']
        return f"""
            QPushButton {{
                background-color: {btn_bg};
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
                background-color: {btn_hover};
                border-color: {colors['accent']};
            }}
            QPushButton:pressed {{
                background-color: {btn_pressed};
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
        colors = AppStyles._get_colors()
        neo = AppStyles.is_neumorphic()
        input_bg = colors['neumorphic_light'] if neo else colors['alternate_base']
        return f"""
            QLineEdit {{
                background-color: {input_bg};
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
        colors = AppStyles._get_colors()
        neo = AppStyles.is_neumorphic()
        input_bg = colors['neumorphic_light'] if neo else colors['alternate_base']
        return f"""
            QComboBox {{
                background-color: {input_bg};
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
        return AppStyles.list_style()

    @staticmethod
    def common_check_box_style() -> str:
        colors = AppStyles._get_colors()
        neo = AppStyles.is_neumorphic()
        chk_bg = colors['neumorphic_light'] if neo else colors['alternate_base']
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
                background-color: {chk_bg};
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
        colors = AppStyles._get_colors()
        return f"""
            QWidget {{
                background-color: {colors['alternate_base']};
                border: 1px solid {colors['mid']};
                border-radius: 8px;
                padding: 12px;
            }}
        """

    @staticmethod
    def side_panel_style() -> str:
        colors = AppStyles._get_colors()
        return f"""
            QWidget {{
                background-color: {colors['alternate_base']};
                border-radius: 8px;
            }}
        """

    @staticmethod
    def section_title_style() -> str:
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
        colors = AppStyles._get_colors()
        return f"""
            QLabel {{
                font-size: 11px;
                color: {colors['window_text']};
            }}
        """

    @staticmethod
    def hint_label_style() -> str:
        colors = AppStyles._get_colors()
        return f"""
            QLabel {{
                font-size: 10px;
                color: {colors['mid']};
            }}
        """

    @staticmethod
    def button_style(active=False):
        colors = AppStyles._get_colors()
        neo = AppStyles.is_neumorphic()
        btn_bg = colors['neumorphic_light'] if neo else colors['button']
        btn_hover = colors['neumorphic_dark'] if neo else colors['light']
        if active:
            return f"""
                QPushButton {{
                    background-color: {colors['accent']};
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 6px 12px;
                    font-weight: 500;
                    font-size: 12px;
                    font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
                }}
                QPushButton:hover {{
                    background-color: {colors['accent_hover']};
                }}
                QPushButton:pressed {{
                    background-color: {colors['accent_pressed']};
                }}
            """
        return f"""
            QPushButton {{
                background-color: {btn_bg};
                color: {colors['window_text']};
                border: 1px solid {colors['mid']};
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: 500;
                font-size: 12px;
                font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
            }}
            QPushButton:hover {{
                background-color: {btn_hover};
                border-color: {colors['accent']};
            }}
            QPushButton:pressed {{
                background-color: {colors['accent_pressed']};
                border-color: {colors['accent_pressed']};
            }}
            QPushButton:disabled {{
                background-color: {colors['light']};
                border-color: {colors['mid']};
                color: {colors['placeholder']};
            }}
        """
