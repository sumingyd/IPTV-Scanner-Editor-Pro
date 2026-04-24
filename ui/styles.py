import os


class AppStyles:
    """应用样式管理类 - 支持多主题"""

    _current_theme = 'dark'
    _arrow_cache = {}
    _check_cache = {}

    @classmethod
    def _get_arrow_image(cls, color: str) -> str:
        if color in cls._arrow_cache:
            cached = cls._arrow_cache[color]
            if os.path.exists(cached):
                return cached.replace('\\', '/')

        import tempfile
        cache_dir = os.path.join(tempfile.gettempdir(), 'iptv_player_icons')
        os.makedirs(cache_dir, exist_ok=True)

        safe_name = color.lstrip('#')
        svg_path = os.path.join(cache_dir, f'arrow_down_{safe_name}.svg')

        svg_content = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="6" viewBox="0 0 10 6">'
            f'<path d="M0 0 L5 6 L10 0 Z" fill="{color}"/>'
            f'</svg>'
        )

        with open(svg_path, 'w', encoding='utf-8') as f:
            f.write(svg_content)

        cls._arrow_cache[color] = svg_path
        return svg_path.replace('\\', '/')

    @classmethod
    def _get_check_image(cls, color: str) -> str:
        if color in cls._check_cache:
            cached = cls._check_cache[color]
            if os.path.exists(cached):
                return cached.replace('\\', '/')

        import tempfile
        cache_dir = os.path.join(tempfile.gettempdir(), 'iptv_player_icons')
        os.makedirs(cache_dir, exist_ok=True)

        safe_name = color.lstrip('#')
        svg_path = os.path.join(cache_dir, f'check_{safe_name}.svg')

        svg_content = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16">'
            f'<path d="M3 8 L6.5 11.5 L13 4.5" stroke="{color}" stroke-width="2.5" '
            f'fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
            f'</svg>'
        )

        with open(svg_path, 'w', encoding='utf-8') as f:
            f.write(svg_content)

        cls._check_cache[color] = svg_path
        return svg_path.replace('\\', '/')

    _radio_cache = {}

    @classmethod
    def _get_radio_dot_image(cls, color: str) -> str:
        if color in cls._radio_cache:
            cached = cls._radio_cache[color]
            if os.path.exists(cached):
                return cached.replace('\\', '/')

        import tempfile
        cache_dir = os.path.join(tempfile.gettempdir(), 'iptv_player_icons')
        os.makedirs(cache_dir, exist_ok=True)

        safe_name = color.lstrip('#')
        svg_path = os.path.join(cache_dir, f'radio_dot_{safe_name}.svg')

        svg_content = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16">'
            f'<circle cx="8" cy="8" r="4" fill="{color}"/>'
            f'</svg>'
        )

        with open(svg_path, 'w', encoding='utf-8') as f:
            f.write(svg_content)

        cls._radio_cache[color] = svg_path
        return svg_path.replace('\\', '/')

    _spinup_cache = {}
    _spindown_cache = {}

    @classmethod
    def _get_spin_up_image(cls, color: str) -> str:
        if color in cls._spinup_cache:
            cached = cls._spinup_cache[color]
            if os.path.exists(cached):
                return cached.replace('\\', '/')

        import tempfile
        cache_dir = os.path.join(tempfile.gettempdir(), 'iptv_player_icons')
        os.makedirs(cache_dir, exist_ok=True)

        safe_name = color.lstrip('#')
        svg_path = os.path.join(cache_dir, f'spin_up_{safe_name}.svg')

        svg_content = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="6" viewBox="0 0 10 6">'
            f'<path d="M0 6 L5 0 L10 6 Z" fill="{color}"/>'
            f'</svg>'
        )

        with open(svg_path, 'w', encoding='utf-8') as f:
            f.write(svg_content)

        cls._spinup_cache[color] = svg_path
        return svg_path.replace('\\', '/')

    @classmethod
    def _get_spin_down_image(cls, color: str) -> str:
        if color in cls._spindown_cache:
            cached = cls._spindown_cache[color]
            if os.path.exists(cached):
                return cached.replace('\\', '/')

        import tempfile
        cache_dir = os.path.join(tempfile.gettempdir(), 'iptv_player_icons')
        os.makedirs(cache_dir, exist_ok=True)

        safe_name = color.lstrip('#')
        svg_path = os.path.join(cache_dir, f'spin_down_{safe_name}.svg')

        svg_content = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="6" viewBox="0 0 10 6">'
            f'<path d="M0 0 L5 6 L10 0 Z" fill="{color}"/>'
            f'</svg>'
        )

        with open(svg_path, 'w', encoding='utf-8') as f:
            f.write(svg_content)

        cls._spindown_cache[color] = svg_path
        return svg_path.replace('\\', '/')

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
            'player_background': '#1a1a1a',
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
            'player_panel_secondary': '#555555',
            'player_panel_disabled': '#777777',
            'player_panel_hint': '#888888',
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
            'window': '#1a1a2e',
            'window_text': '#eaeaea',
            'base': '#222240',
            'alternate_base': '#28284a',
            'button': '#28284a',
            'light': '#303055',
            'mid': '#3a3a60',
            'dark': '#454570',
            'highlight': '#2a2a50',
            'highlighted_text': '#7c8aff',
            'link': '#7c8aff',
            'link_visited': '#9580ff',
            'tooltip_base': '#28284a',
            'tooltip_text': '#eaeaea',
            'placeholder': '#808090',
            'accent': '#6b7bff',
            'accent_hover': '#5b6bef',
            'accent_pressed': '#4b5bdf',
            'success': '#5fcf73',
            'warning': '#ffaa70',
            'error': '#ff6060',
            'info': '#5090ff',
            'table_header': '#28284a',
            'table_header_gradient_start': '#303055',
            'table_header_gradient_middle': '#28284a',
            'table_header_gradient_end': '#202038',
            'table_header_text': '#d0d0e0',
            'table_header_hover': '#6b7bff',
            'table_border': '#3a3a60',
            'table_grid': '#303055',
            'table_alternate': '#202038',
            'table_hover': '#2a2a50',
            'table_selection': '#5b6bef',
            'table_selection_text': '#ffffff',
            'player_background': '#16162a',
            'player_panel': '#222240',
            'player_panel_text': '#eaeaea',
            'player_panel_secondary': '#888898',
            'player_panel_disabled': '#585878',
            'player_panel_hint': '#484868',
            'player_button': 'rgba(40, 40, 74, 0.95)',
            'player_combo': 'rgba(34, 34, 64, 0.9)',
            'player_line': '#3a3a60',
            'player_accent': '#7c8aff',
            'player_success': '#5fcf73',
            'player_warning': '#ff6060',
            'player_slider_track': '#3a3a60',
            'player_slider_fill': '#6b7bff',
            'player_slider_handle': '#eaeaea',
            'player_volume_track': '#303055',
            'player_video_placeholder': '#16162a',
            'window_opacity': 255,
            'shadow_light': 'rgba(100,100,160,0.5)',
            'shadow_dark': 'rgba(0,0,0,0.7)',
            'neumorphic_light': '#303055',
            'neumorphic_dark': '#181830',
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
            'player_panel_secondary': '#5a5f7a',
            'player_panel_disabled': '#8086a0',
            'player_panel_hint': '#9095b0',
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
            'window_opacity': 255,
            'shadow_light': 'rgba(255,255,255,0.95)',
            'shadow_dark': 'rgba(163,177,198,0.7)',
            'neumorphic_light': '#ecf1f9',
            'neumorphic_dark': '#bec6d2',
        },
        'apple_tv': {
            'window': '#000000',
            'window_text': '#f5f5f7',
            'base': '#1c1c1e',
            'alternate_base': '#2c2c2e',
            'button': '#3a3a3c',
            'light': '#48484a',
            'mid': '#636366',
            'dark': '#8e8e93',
            'highlight': '#0a2540',
            'highlighted_text': '#007aff',
            'link': '#007aff',
            'link_visited': '#5856d6',
            'tooltip_base': '#2c2c2e',
            'tooltip_text': '#f5f5f7',
            'placeholder': '#8e8e93',
            'accent': '#007aff',
            'accent_hover': '#0066d6',
            'accent_pressed': '#0055b3',
            'success': '#30d158',
            'warning': '#ff9f0a',
            'error': '#ff453a',
            'info': '#007aff',
            'table_header': '#1c1c1e',
            'table_header_gradient_start': '#2c2c2e',
            'table_header_gradient_middle': '#1c1c1e',
            'table_header_gradient_end': '#0f0f10',
            'table_header_text': '#f5f5f7',
            'table_header_hover': '#007aff',
            'table_border': '#3a3a3c',
            'table_grid': '#2c2c2e',
            'table_alternate': '#161618',
            'table_hover': '#0a2540',
            'table_selection': '#007aff',
            'table_selection_text': '#ffffff',
            'player_background': '#000000',
            'player_panel': '#1c1c1e',
            'player_panel_text': '#f5f5f7',
            'player_panel_secondary': '#98989d',
            'player_panel_disabled': '#636366',
            'player_panel_hint': '#48484a',
            'player_button': 'rgba(58, 58, 60, 0.9)',
            'player_combo': 'rgba(28, 28, 30, 0.85)',
            'player_line': '#38383a',
            'player_accent': '#007aff',
            'player_success': '#30d158',
            'player_warning': '#ff453a',
            'player_slider_track': '#3a3a3c',
            'player_slider_fill': '#007aff',
            'player_slider_handle': '#f5f5f7',
            'player_volume_track': '#2c2c2e',
            'player_video_placeholder': '#000000',
            'window_opacity': 240,
            'shadow_light': 'rgba(255,255,255,0.08)',
            'shadow_dark': 'rgba(0,0,0,0.5)',
            'neumorphic_light': '#2c2c2e',
            'neumorphic_dark': '#0f0f10',
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
        return (
            f"border: 2px solid;"
            f"border-top-color: {c['shadow_dark']};"
            f"border-left-color: {c['shadow_dark']};"
            f"border-bottom-color: {c['shadow_light']};"
            f"border-right-color: {c['shadow_light']};"
        )

    @staticmethod
    def _neumorphic_raised():
        c = AppStyles._get_colors()
        return (
            f"border: 2px solid;"
            f"border-top-color: {c['shadow_light']};"
            f"border-left-color: {c['shadow_light']};"
            f"border-bottom-color: {c['shadow_dark']};"
            f"border-right-color: {c['shadow_dark']};"
        )

    @staticmethod
    def main_window_style() -> str:
        colors = AppStyles._get_colors()
        neo = AppStyles.is_neumorphic()
        btn_bg = colors['neumorphic_light'] if neo else colors['button']
        btn_hover = colors['neumorphic_dark'] if neo else colors['light']
        btn_pressed = colors['neumorphic_dark'] if neo else colors['dark']
        if neo:
            raised = AppStyles._neumorphic_raised()
            inset = AppStyles._neumorphic_inset()
            return f"""
                QMainWindow {{
                    background-color: transparent;
                    color: {colors['window_text']};
                    font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
                    font-size: 13px;
                }}
                QWidget#mainContainer {{
                    background-color: {colors['window']};
                    border-radius: 10px;
                    border: 1px solid {colors['mid']};
                }}
                QWidget#contentArea {{
                    background-color: {colors['player_background']};
                    border-bottom-left-radius: 10px;
                    border-bottom-right-radius: 10px;
                }}
                QGroupBox {{
                    border: none;
                    border-radius: 10px;
                    margin-top: 12px;
                    padding-top: 16px;
                    font-weight: 600;
                    font-size: 13px;
                    background-color: {colors['alternate_base']};
                    color: {colors['window_text']};
                    {raised}
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
                    border-radius: 6px;
                    padding: 6px 10px;
                    padding-right: 32px;
                    font-size: 13px;
                    background-color: {colors['neumorphic_light']};
                    color: {colors['window_text']};
                    {inset}
                }}
                QSpinBox:focus {{
                    border: 2px solid {colors['accent']};
                    border-radius: 6px;
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
                    image: url({AppStyles._get_spin_up_image(colors['window_text'])});
                    width: 10px;
                    height: 6px;
                }}
                QSpinBox::down-arrow {{
                    image: url({AppStyles._get_spin_down_image(colors['window_text'])});
                    width: 10px;
                    height: 6px;
                }}
                QSpinBox::up-button:hover::up-arrow {{
                    image: url({AppStyles._get_spin_up_image(colors['accent'])});
                }}
                QSpinBox::down-button:hover::down-arrow {{
                    image: url({AppStyles._get_spin_down_image(colors['accent'])});
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
        return f"""
            QMainWindow {{
                background-color: transparent;
                color: {colors['window_text']};
                font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
                font-size: 13px;
            }}
            QWidget#mainContainer {{
                background-color: {colors['window']};
                border-radius: 10px;
                border: 1px solid {colors['mid']};
            }}
            QWidget#contentArea {{
                background-color: {colors['player_background']};
                border-bottom-left-radius: 10px;
                border-bottom-right-radius: 10px;
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
                image: url({AppStyles._get_spin_up_image(colors['window_text'])});
                width: 10px;
                height: 6px;
            }}
            QSpinBox::down-arrow {{
                image: url({AppStyles._get_spin_down_image(colors['window_text'])});
                width: 10px;
                height: 6px;
            }}
            QSpinBox::up-button:hover::up-arrow {{
                image: url({AppStyles._get_spin_up_image(colors['accent'])});
            }}
            QSpinBox::down-button:hover::down-arrow {{
                image: url({AppStyles._get_spin_down_image(colors['accent'])});
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
        neo = AppStyles.is_neumorphic()
        if neo:
            inset = AppStyles._neumorphic_inset()
            raised = AppStyles._neumorphic_raised()
            return f"""
                QTableView {{
                    border: none;
                    border-radius: 6px;
                    alternate-background-color: {colors['table_alternate']};
                    selection-background-color: {colors['table_selection']};
                    selection-color: {colors['table_selection_text']};
                    gridline-color: {colors['table_grid']};
                    font-size: 12px;
                    font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
                    background-color: {colors['alternate_base']};
                    {inset}
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
                    border-right: 1px solid {colors['shadow_dark']};
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
                border-bottom-left-radius: 10px;
                border-bottom-right-radius: 10px;
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
        colors = AppStyles._get_colors()
        return f"""
            * {{
                font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
            }}
            QWidget {{
                background-color: transparent;
            }}
            QLabel {{
                border: none;
                background-color: transparent;
                color: {colors['player_panel_text']};
            }}
            QListWidget {{
                border: none;
                background-color: {colors['player_panel']};
                color: {colors['player_panel_text']};
                outline: none;
            }}
            QComboBox {{
                border: none;
                background-color: {colors['player_combo']};
                color: {colors['player_panel_text']};
                padding: 2px 6px;
            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: center right;
                width: 16px;
                border: none;
            }}
            QComboBox::down-arrow {{
                image: url({AppStyles._get_arrow_image(colors['player_panel_secondary'])});
                width: 10px;
                height: 6px;
            }}
            QToolButton {{
                padding: 0px;
                margin: 0px;
                border: none;
            }}
            QPushButton {{
                padding: 0px;
                margin: 0px;
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
                padding: 0px;
                margin: 0px;
                border: none;
            }}
            QToolButton:hover {{
                background-color: {colors['player_accent']};
            }}
            QToolButton:pressed {{
                background-color: {colors['player_panel_text']};
                color: {colors['player_button']};
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
                padding: 0px;
                margin: 0px;
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
    def player_catchup_indicator_style() -> str:
        colors = AppStyles._get_colors()
        return f"""
            QLabel {{
                color: {colors['player_accent']};
                font-size: 11px;
                background-color: transparent;
                padding: 1px 4px;
                border: 1px solid {colors['player_accent']};
                border-radius: 3px;
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
                font-size: 16px;
                padding: 0px;
                margin: 0px;
                border: none;
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
                padding: 4px 8px;
                border: 1px solid {colors['player_line']};
                border-radius: 4px;
                font-size: 12px;
                min-width: 80px;
            }}
            QComboBox:hover {{
                border: 1px solid {colors['player_accent']};
            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: right center;
                width: 16px;
                border-left: none;
                border-top-right-radius: 4px;
                border-bottom-right-radius: 4px;
            }}
            QComboBox::down-arrow {{
                image: url({AppStyles._get_arrow_image(colors['player_panel_secondary'])});
                width: 10px;
                height: 6px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {colors['player_panel']};
                color: {colors['player_panel_text']};
                selection-background-color: {colors['player_accent']};
                selection-color: {colors['player_panel_text']};
                border: 1px solid {colors['player_line']};
                outline: none;
            }}
        """

    @staticmethod
    def player_tab_style() -> str:
        colors = AppStyles._get_colors()
        return f"""
            QTabWidget::pane {{
                border: none;
                background-color: transparent;
            }}
            QTabBar::tab {{
                background-color: {colors['player_combo']};
                color: {colors['player_panel_text']};
                padding: 5px 10px;
                border: 1px solid {colors['player_line']};
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                font-size: 11px;
                min-width: 90px;
            }}
            QTabBar::tab:selected {{
                background-color: {colors['player_accent']};
                color: white;
            }}
            QTabBar::tab:hover:!selected {{
                background-color: {colors['player_panel']};
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
                color: {colors['player_panel_hint']};
                background-color: {colors['player_video_placeholder']};
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
                padding: 2px;
            }}
            QListWidget::item {{
                padding: 2px 4px;
                min-height: 26px;
                max-height: 32px;
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
        colors = AppStyles._get_colors()
        return f"""
            QLabel {{
                font-size: 24px;
                background-color: transparent;
                color: {colors['player_panel_secondary']};
                qproperty-alignment: AlignVCenter | AlignHCenter;
            }}
        """

    @staticmethod
    def player_background_style() -> str:
        colors = AppStyles._get_colors()
        return f"background-color: {colors['player_background']};"

    @staticmethod
    def title_bar_style() -> str:
        colors = AppStyles._get_colors()
        title_bg = colors.get('window', '#1e1e1e')
        title_text = colors.get('window_text', '#ffffff')
        accent_color = colors.get('accent', '#0078d4')
        return f"""
            QWidget#titleBar {{
                background-color: {title_bg};
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
            }}
            QWidget#titleBar > QPushButton {{
                background-color: transparent;
                color: {title_text};
                border: none;
                font-size: 14px;
                padding: 4px 12px;
                margin: 2px;
                border-radius: 4px;
            }}
            QWidget#titleBar > QPushButton:hover {{
                background-color: {accent_color};
            }}
            QWidget#titleBar > QPushButton#closeButton:hover {{
                background-color: #e81123;
            }}
        """

    @staticmethod
    def title_label_style() -> str:
        colors = AppStyles._get_colors()
        title_text = colors.get('window_text', '#ffffff')
        return f"color: {title_text}; font-size: 13px; font-weight: bold; background: transparent; padding-left: 6px;"

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
                    {AppStyles._neumorphic_raised()}
                }}
                QMenuBar::item:selected {{
                    color: {menu_hover_text};
                    background-color: {menu_hover_bg};
                    border: 2px solid {colors['accent']};
                    border-radius: 6px;
                }}
                QMenu {{
                    background-color: {menu_bg};
                    color: {menu_text};
                    border-radius: 8px;
                    padding: 4px;
                    border: 2px solid;
                    border-top-color: {colors['shadow_light']};
                    border-left-color: {colors['shadow_light']};
                    border-bottom-color: {colors['shadow_dark']};
                    border-right-color: {colors['shadow_dark']};
                }}
                QMenu::item {{
                    padding: 6px 24px;
                    margin: 2px;
                    border-radius: 6px;
                }}
                QMenu::item:selected {{
                    color: {menu_hover_text};
                    background-color: {menu_hover_bg};
                    border: 1px solid {colors['accent']};
                    border-radius: 6px;
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
        if neo:
            raised = AppStyles._neumorphic_raised()
            inset = AppStyles._neumorphic_inset()
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
                    border-radius: 6px;
                    font-size: 12px;
                    font-weight: 500;
                    background-color: {btn_bg};
                    color: {colors['window_text']};
                    {raised}
                }}
                QDialog QPushButton:hover {{
                    background-color: {btn_hover};
                    border: 2px solid {colors['accent']};
                    border-radius: 6px;
                }}
                QDialog QPushButton:pressed {{
                    background-color: {btn_pressed};
                    {inset}
                    border-radius: 6px;
                }}
                QDialog QGroupBox {{
                    border: none;
                    border-radius: 10px;
                    margin-top: 12px;
                    padding-top: 18px;
                    background-color: {colors['alternate_base']};
                    {raised}
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
                    border-radius: 6px;
                    padding: 6px 10px;
                    font-size: 13px;
                    background-color: {input_bg};
                    color: {colors['window_text']};
                    {inset}
                }}
                QDialog QLineEdit:focus, QDialog QComboBox:focus {{
                    border: 2px solid {colors['accent']};
                    border-radius: 6px;
                    outline: none;
                }}
                QDialog QComboBox QAbstractItemView {{
                    background-color: {colors['window']};
                    color: {colors['window_text']};
                    border: 1px solid {colors['mid']};
                    border-radius: 4px;
                }}
                QDialog QComboBox::drop-down {{
                    subcontrol-origin: padding;
                    subcontrol-position: center right;
                    width: 20px;
                    border: none;
                }}
                QDialog QComboBox::down-arrow {{
                    image: url({AppStyles._get_arrow_image(colors['window_text'])});
                    width: 10px;
                    height: 6px;
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
                    border-radius: 4px;
                    background-color: {input_bg};
                    {inset}
                }}
                QDialog QCheckBox::indicator:checked {{
                    background-color: {colors['accent']};
                    border: 2px solid {colors['accent']};
                    border-radius: 4px;
                    image: url({AppStyles._get_check_image('white')});
                }}
                QDialog QCheckBox::indicator:hover {{
                    border: 2px solid {colors['accent']};
                    border-radius: 4px;
                }}
                QDialog QCheckBox::indicator:pressed {{
                    background-color: {colors['accent_pressed']};
                    border: 2px solid {colors['accent_pressed']};
                    border-radius: 4px;
                }}
                QDialog QTextEdit {{
                    border-radius: 6px;
                    padding: 10px;
                    font-size: 13px;
                    background-color: {input_bg};
                    color: {colors['window_text']};
                    {inset}
                }}
                QDialog QTextEdit:focus {{
                    border: 2px solid {colors['accent']};
                    border-radius: 6px;
                    outline: none;
                }}
            """
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
            QDialog QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: center right;
                width: 20px;
                border: none;
            }}
            QDialog QComboBox::down-arrow {{
                image: url({AppStyles._get_arrow_image(colors['window_text'])});
                width: 10px;
                height: 6px;
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
                image: url({AppStyles._get_check_image('white')});
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
        neo = AppStyles.is_neumorphic()
        if neo:
            inset = AppStyles._neumorphic_inset()
            return f"""
                QProgressBar {{
                    border-radius: 6px;
                    text-align: center;
                    height: 24px;
                    background-color: {colors['alternate_base']};
                    font-size: 11px;
                    font-weight: 500;
                    font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
                    color: {colors['window_text']};
                    {inset}
                }}
                QProgressBar::chunk {{
                    background-color: {colors['accent']};
                    border-radius: 5px;
                    margin: 1px;
                }}
            """
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
        neo = AppStyles.is_neumorphic()
        if neo:
            raised = AppStyles._neumorphic_raised()
            inset = AppStyles._neumorphic_inset()
            return f"""
                QToolButton {{
                    border: none;
                    border-radius: 6px;
                    padding: 4px 8px;
                    margin: 1px;
                    background-color: {colors['neumorphic_light']};
                    min-width: 60px;
                    min-height: 28px;
                    color: {colors['window_text']};
                    font-size: 12px;
                    font-weight: 500;
                    font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
                    {raised}
                }}
                QToolButton:hover {{
                    background-color: {colors['neumorphic_dark']};
                    border: 2px solid {colors['accent']};
                    border-radius: 6px;
                    color: {colors['accent']};
                }}
                QToolButton:pressed {{
                    background-color: {colors['neumorphic_dark']};
                    {inset}
                    border-radius: 6px;
                    color: {colors['accent_pressed']};
                }}
                QToolButton::menu-indicator {{
                    width: 0px;
                }}
            """
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
        neo = AppStyles.is_neumorphic()
        if neo:
            inset = AppStyles._neumorphic_inset()
            raised = AppStyles._neumorphic_raised()
            return f"""
                QListWidget {{
                    border: none;
                    border-radius: 8px;
                    padding: 4px;
                    background-color: {colors['alternate_base']};
                    font-size: 13px;
                    {inset}
                }}
                QListWidget::item {{
                    border: none;
                    border-radius: 6px;
                    padding: 8px 12px;
                    margin: 2px;
                    background-color: {colors['neumorphic_light']};
                    color: {colors['window_text']};
                    {raised}
                }}
                QListWidget::item:hover {{
                    background-color: {colors['highlight']};
                    border: 1px solid {colors['accent']};
                    border-radius: 6px;
                }}
                QListWidget::item:selected {{
                    background-color: {colors['accent']};
                    color: white;
                    border: 1px solid {colors['accent_pressed']};
                    border-radius: 6px;
                }}
                QListWidget::item:selected:hover {{
                    background-color: {colors['accent_hover']};
                }}
            """
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
        neo = AppStyles.is_neumorphic()
        if neo:
            raised = AppStyles._neumorphic_raised()
            return f"""
                QLabel {{
                    color: {colors['accent']};
                    font-size: 12px;
                    padding: 8px 12px;
                    background-color: {colors['neumorphic_light']};
                    border-radius: 6px;
                    font-weight: 500;
                    {raised}
                }}
            """
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
        neo = AppStyles.is_neumorphic()
        if neo:
            raised = AppStyles._neumorphic_raised()
            return f"""
                QLabel {{
                    color: {colors['window_text']};
                    font-size: 12px;
                    padding: 8px 12px;
                    background-color: {colors['neumorphic_light']};
                    border-radius: 6px;
                    font-weight: 500;
                    {raised}
                }}
            """
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
            QStatusBar {{
                color: {colors['error']};
                font-weight: bold;
            }}
        """

    @staticmethod
    def apply_button_style() -> str:
        colors = AppStyles._get_colors()
        return f"""
            QPushButton {{
                background-color: {colors['success']};
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #45a049;
            }}
            QPushButton:pressed {{
                background-color: #388e3c;
            }}
        """

    @staticmethod
    def cancel_button_style() -> str:
        colors = AppStyles._get_colors()
        return f"""
            QPushButton {{
                background-color: {colors['error']};
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: #da190b;
            }}
            QPushButton:pressed {{
                background-color: #c62828;
            }}
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
        neo = AppStyles.is_neumorphic()
        if neo:
            raised = AppStyles._neumorphic_raised()
            inset = AppStyles._neumorphic_inset()
            return f"""
                QTabWidget {{
                    background-color: {colors['window']};
                    border: none;
                    border-radius: 8px;
                    font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
                }}
                QTabWidget::pane {{
                    border: none;
                    border-radius: 0 0 8px 8px;
                    background-color: {colors['window']};
                    margin-top: -1px;
                    {inset}
                }}
                QTabBar {{
                    background-color: {colors['alternate_base']};
                    border-bottom: none;
                    border-radius: 8px 8px 0 0;
                }}
                QTabBar::tab {{
                    background-color: {colors['alternate_base']};
                    border: none;
                    border-radius: 6px 6px 0 0;
                    padding: 8px 16px;
                    margin-right: 4px;
                    margin-top: 4px;
                    font-size: 13px;
                    font-weight: 500;
                    color: {colors['window_text']};
                }}
                QTabBar::tab:selected {{
                    background-color: {colors['neumorphic_light']};
                    color: {colors['accent']};
                    font-weight: 600;
                    {raised}
                }}
                QTabBar::tab:hover:!selected {{
                    background-color: {colors['light']};
                    color: {colors['accent']};
                }}
                QTabBar::tab:first {{
                    margin-left: 4px;
                }}
                QTabBar::tab:last {{
                    margin-right: 0;
                }}
            """
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
        if neo:
            raised = AppStyles._neumorphic_raised()
            inset = AppStyles._neumorphic_inset()
            return f"""
                QPushButton {{
                    background-color: {btn_bg};
                    color: {colors['window_text']};
                    {raised}
                    border-radius: 6px;
                    padding: 4px 12px;
                    min-width: 0px;
                    font-weight: 500;
                    font-size: 12px;
                    font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
                }}
                QPushButton:hover {{
                    background-color: {btn_hover};
                    border: 2px solid {colors['accent']};
                    border-radius: 6px;
                }}
                QPushButton:pressed {{
                    background-color: {btn_pressed};
                    {inset}
                    border-radius: 6px;
                }}
                QPushButton:disabled {{
                    background-color: {colors['light']};
                    border: 1px solid {colors['mid']};
                    border-radius: 6px;
                    color: {colors['placeholder']};
                }}
            """
        return f"""
            QPushButton {{
                background-color: {btn_bg};
                color: {colors['window_text']};
                border: 1px solid {colors['mid']};
                border-radius: 4px;
                padding: 4px 12px;
                min-width: 0px;
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
        if neo:
            inset = AppStyles._neumorphic_inset()
            return f"""
                QLineEdit {{
                    background-color: {input_bg};
                    color: {colors['window_text']};
                    {inset}
                    border-radius: 6px;
                    padding: 6px;
                    font-size: 12px;
                    font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
                }}
                QLineEdit:focus {{
                    border: 2px solid {colors['accent']};
                    border-radius: 6px;
                    outline: none;
                }}
                QLineEdit:disabled {{
                    background-color: {colors['light']};
                    border: 1px solid {colors['mid']};
                    border-radius: 6px;
                    color: {colors['placeholder']};
                }}
            """
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
        if neo:
            inset = AppStyles._neumorphic_inset()
            return f"""
                QComboBox {{
                    background-color: {input_bg};
                    color: {colors['window_text']};
                    {inset}
                    border-radius: 6px;
                    padding: 6px;
                    font-size: 12px;
                    font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
                    min-width: 120px;
                }}
                QComboBox:focus {{
                    border: 2px solid {colors['accent']};
                    border-radius: 6px;
                    outline: none;
                }}
                QComboBox:disabled {{
                    background-color: {colors['light']};
                    border: 1px solid {colors['mid']};
                    border-radius: 6px;
                    color: {colors['placeholder']};
                }}
                QComboBox::drop-down {{
                    subcontrol-origin: padding;
                    subcontrol-position: center right;
                    width: 20px;
                    border: none;
                }}
                QComboBox::down-arrow {{
                    image: url({AppStyles._get_arrow_image(colors['window_text'])});
                    width: 10px;
                    height: 6px;
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
                subcontrol-origin: padding;
                subcontrol-position: center right;
                width: 20px;
                border: none;
            }}
            QComboBox::down-arrow {{
                image: url({AppStyles._get_arrow_image(colors['window_text'])});
                width: 10px;
                height: 6px;
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
    def url_combo_style() -> str:
        colors = AppStyles._get_colors()
        neo = AppStyles.is_neumorphic()
        input_bg = colors['neumorphic_light'] if neo else colors['alternate_base']
        border = ""
        radius = "4px"
        if neo:
            border = AppStyles._neumorphic_inset()
            radius = "6px"
        return f"""
            QComboBox {{
                background-color: {input_bg};
                color: {colors['window_text']};
                border: 1px solid {colors['mid']};
                border-radius: {radius};
                padding: 2px 20px 2px 6px;
                font-size: 12px;
                font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
                {border}
            }}
            QComboBox:focus {{
                border-color: {colors['accent']};
                outline: none;
            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: center right;
                width: 18px;
                border: none;
            }}
            QComboBox::down-arrow {{
                image: url({AppStyles._get_arrow_image(colors['window_text'])});
                width: 10px;
                height: 6px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {colors['alternate_base']};
                color: {colors['window_text']};
                border: 1px solid {colors['mid']};
                selection-background-color: {colors['accent']};
                selection-color: white;
                padding: 2px;
                outline: none;
            }}
            QComboBox QAbstractItemView::item {{
                padding: 3px 6px;
            }}
            QComboBox QAbstractItemView::item:hover {{
                background-color: {colors['accent']};
                color: white;
            }}
            QComboBox QLineEdit {{
                background-color: transparent;
                border: none;
                padding: 0;
                font-size: 12px;
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
        if neo:
            inset = AppStyles._neumorphic_inset()
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
                    border-radius: 4px;
                    background-color: {chk_bg};
                    {inset}
                }}
                QCheckBox::indicator:checked {{
                    background-color: {colors['accent']};
                    border: 2px solid {colors['accent']};
                    border-radius: 4px;
                    image: url({AppStyles._get_check_image('white')});
                }}
                QCheckBox::indicator:hover {{
                    border: 2px solid {colors['accent']};
                    border-radius: 4px;
                }}
            """
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
                image: url({AppStyles._get_check_image('white')});
            }}
            QCheckBox::indicator:hover {{
                border-color: {colors['accent']};
            }}
        """

    @staticmethod
    def common_radio_button_style() -> str:
        colors = AppStyles._get_colors()
        neo = AppStyles.is_neumorphic()
        chk_bg = colors['neumorphic_light'] if neo else colors['alternate_base']
        if neo:
            inset = AppStyles._neumorphic_inset()
            return f"""
                QRadioButton {{
                    color: {colors['window_text']};
                    font-size: 12px;
                    font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
                    spacing: 8px;
                }}
                QRadioButton::indicator {{
                    width: 16px;
                    height: 16px;
                    border-radius: 8px;
                    background-color: {chk_bg};
                    {inset}
                }}
                QRadioButton::indicator:checked {{
                    background-color: {colors['accent']};
                    border: 3px solid {colors['accent']};
                    border-radius: 8px;
                    image: url({AppStyles._get_radio_dot_image('white')});
                }}
                QRadioButton::indicator:hover {{
                    border: 2px solid {colors['accent']};
                    border-radius: 8px;
                }}
            """
        return f"""
            QRadioButton {{
                color: {colors['window_text']};
                font-size: 12px;
                font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
                spacing: 8px;
            }}
            QRadioButton::indicator {{
                width: 16px;
                height: 16px;
                border: 2px solid {colors['mid']};
                border-radius: 8px;
                background-color: {chk_bg};
            }}
            QRadioButton::indicator:checked {{
                background-color: {colors['accent']};
                border-color: {colors['accent']};
                image: url({AppStyles._get_radio_dot_image('white')});
            }}
            QRadioButton::indicator:hover {{
                border-color: {colors['accent']};
            }}
        """

    @staticmethod
    def common_group_box_style() -> str:
        colors = AppStyles._get_colors()
        neo = AppStyles.is_neumorphic()
        if neo:
            raised = AppStyles._neumorphic_raised()
            return f"""
                QGroupBox {{
                    background-color: {colors['alternate_base']};
                    color: {colors['window_text']};
                    border: none;
                    border-radius: 10px;
                    margin-top: 12px;
                    padding-top: 16px;
                    font-weight: 600;
                    font-size: 13px;
                    font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
                    {raised}
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
        neo = AppStyles.is_neumorphic()
        if neo:
            raised = AppStyles._neumorphic_raised()
            return f"""
                QWidget {{
                    background-color: {colors['alternate_base']};
                    border: none;
                    border-radius: 10px;
                    padding: 12px;
                    {raised}
                }}
            """
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
        neo = AppStyles.is_neumorphic()
        if neo:
            raised = AppStyles._neumorphic_raised()
            return f"""
                QWidget {{
                    background-color: {colors['alternate_base']};
                    border: none;
                    border-radius: 10px;
                    {raised}
                }}
            """
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
            if neo:
                raised = AppStyles._neumorphic_raised()
                inset = AppStyles._neumorphic_inset()
                return f"""
                    QPushButton {{
                        background-color: {colors['accent']};
                        color: white;
                        {raised}
                        border-radius: 6px;
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
                        {inset}
                        border-radius: 6px;
                    }}
                """
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
        if neo:
            raised = AppStyles._neumorphic_raised()
            inset = AppStyles._neumorphic_inset()
            return f"""
                QPushButton {{
                    background-color: {btn_bg};
                    color: {colors['window_text']};
                    {raised}
                    border-radius: 6px;
                    padding: 6px 12px;
                    font-weight: 500;
                    font-size: 12px;
                    font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
                }}
                QPushButton:hover {{
                    background-color: {btn_hover};
                    border: 2px solid {colors['accent']};
                    border-radius: 6px;
                }}
                QPushButton:pressed {{
                    background-color: {colors['neumorphic_dark']};
                    {inset}
                    border-radius: 6px;
                }}
                QPushButton:disabled {{
                    background-color: {colors['light']};
                    border: 1px solid {colors['mid']};
                    border-radius: 6px;
                    color: {colors['placeholder']};
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
