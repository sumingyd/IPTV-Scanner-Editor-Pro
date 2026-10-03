"""窗口布局域存储 — 窗口几何/面板可见性/UI 设置/主题/关闭行为。"""

from core.log_manager import global_logger as logger


class WindowLayoutStore:
    """窗口布局配置域存储，通过 facade 访问共享 ConfigParser。"""

    def __init__(self, facade):
        self._facade = facade

    def save_window_layout(self, x, y, width, height, dividers):
        """保存窗口布局（包括位置和大小）"""
        self._facade.set_value('UI', 'window_x', str(x))
        self._facade.set_value('UI', 'window_y', str(y))
        self._facade.set_value('UI', 'window_width', str(width))
        self._facade.set_value('UI', 'window_height', str(height))
        for i, pos in enumerate(dividers):
            self._facade.set_value('UI', f'divider_{i}', str(pos))
        return self._facade.save_config()

    def load_window_layout(
            self, default_x=100,
            default_y=100,
            default_width=800,
            default_height=600,
            default_dividers=None
            ):
        """加载窗口布局（包括位置和大小）"""
        def _load_int(section, key, default):
            val = self._facade.get_value(section, key)
            if val is not None:
                try:
                    return int(val)
                except (ValueError, TypeError):
                    pass
            return default
        x = _load_int('UI', 'window_x', default_x)
        y = _load_int('UI', 'window_y', default_y)
        width = _load_int('UI', 'window_width', default_width)
        height = _load_int('UI', 'window_height', default_height)
        dividers = []
        i = 0
        while True:
            pos = self._facade.get_value('UI', f'divider_{i}')
            if pos is None:
                break
            try:
                dividers.append(int(pos))
            except (ValueError, TypeError):
                logger.debug(f"divider_{i} 值无效: {pos}，跳过")
            i += 1
        return x, y, width, height, dividers or default_dividers

    def save_ui_settings(self, settings: dict):
        """保存UI相关设置"""
        for key, value in settings.items():
            self._facade.set_value('UI', key, str(value))
        return self._facade.save_config()

    def load_ui_settings(self, defaults: dict | None = None) -> dict:
        """加载 UI 相关设置"""
        defaults = defaults or {}
        settings = {}
        for key, default_value in defaults.items():
            value = self._facade.get_value('UI', key)
            if value is not None:
                try:
                    if isinstance(default_value, bool):
                        settings[key] = self._facade._parse_bool(value)
                    elif isinstance(default_value, int):
                        settings[key] = int(value)
                    elif isinstance(default_value, float):
                        settings[key] = float(value)
                    else:
                        settings[key] = value
                except (ValueError, TypeError):
                    settings[key] = default_value
            else:
                settings[key] = default_value
        return settings

    def save_theme_settings(self, color_mode, visual_style='flat'):
        self._facade.set_value('Theme', 'color_mode', color_mode)
        self._facade.set_value('VisualStyle', 'current_style', visual_style)
        self._facade.set_value('Theme', 'current_theme', f"{color_mode}+{visual_style}")
        return self._facade.save_config()

    def load_theme_settings(self):
        color_mode = self._facade.get_value('Theme', 'color_mode', '')
        visual_style = self._facade.get_value('VisualStyle', 'current_style', '')
        if not color_mode:
            old_theme = self._facade.get_value('Theme', 'current_theme', 'dark') or 'dark'
            from ui.styles import AppStyles
            if old_theme in AppStyles._OLD_THEME_MAPPING:
                color_mode, visual_style = AppStyles._OLD_THEME_MAPPING[old_theme]
            else:
                if '+' in old_theme:
                    parts = old_theme.split('+')
                    color_mode = parts[0] if len(parts) > 0 else 'dark'
                    visual_style = parts[1] if len(parts) > 1 else 'flat'
                else:
                    color_mode = 'dark'
                    visual_style = 'flat'
        if not visual_style:
            visual_style = 'flat'
        return color_mode, visual_style

    def save_close_behavior(self, action: str):
        """保存关闭行为设置，action: 'minimize_tray' 或 'exit'"""
        self._facade.set_value('UI', 'close_action', action)
        return self._facade.save_config()

    def load_close_behavior(self) -> str | None:
        """加载关闭行为设置，返回 'minimize_tray'、'exit' 或 None（未设置则弹窗询问）"""
        value = self._facade.get_value('UI', 'close_action')
        if value in ('minimize_tray', 'exit'):
            return value
        return None

    def clear_close_behavior(self):
        """清除记住的关闭行为设置"""
        facade = self._facade
        with facade._lock:
            if facade.config.has_section('UI') and facade.config.has_option('UI', 'close_action'):
                facade.config.remove_option('UI', 'close_action')
        return facade.save_config()