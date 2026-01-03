from PyQt6 import QtGui


class ThemeColors:
    """主题颜色配置"""

    # 浅色主题颜色
    LIGHT_THEME = {
        'window': '#ffffff',
        'window_text': '#333333',
        'base': '#ffffff',
        'alternate_base': '#f8f8f8',
        'button': '#f0f0f0',
        'light': '#f8f8f8',
        'mid': '#cccccc',
        'dark': '#999999',
        'highlight': '#f0f7ff',
        'highlighted_text': '#4a7eff',
        'link': '#4a7eff',
        'link_visited': '#8a4eff',
        'tooltip_base': '#ffffdc',
        'tooltip_text': '#333333',
        'placeholder': '#999999',
        'accent': '#4a7eff',
        'accent_hover': '#3a6eff',
        'accent_pressed': '#2a5eff',
        'success': '#4CAF50',
        'warning': '#FF9800',
        'error': '#f44336',
        'info': '#2196F3',
        'table_header': '#f0f0f0',
        'table_header_gradient_start': '#f8f8f8',
        'table_header_gradient_middle': '#e8e8e8',
        'table_header_gradient_end': '#d8d8d8',
        'table_border': '#cccccc',
        'table_grid': '#e0e0e0',
        'table_alternate': '#f8f8f8',
        'table_hover': '#f0f7ff',
        'table_selection': '#4a7eff',
        'table_selection_text': '#ffffff',
    }

    # 深色主题颜色
    DARK_THEME = {
        'window': '#1e1e1e',
        'window_text': '#f0f0f0',
        'base': '#2a2a2a',
        'alternate_base': '#333333',
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
        'placeholder': '#888888',
        'accent': '#6a9eff',
        'accent_hover': '#5a8eff',
        'accent_pressed': '#4a7eff',
        'success': '#66BB6A',
        'warning': '#FFB74D',
        'error': '#EF5350',
        'info': '#42A5F5',
        'table_header': '#3a3a3a',
        'table_header_gradient_start': '#444444',
        'table_header_gradient_middle': '#3a3a3a',
        'table_header_gradient_end': '#333333',
        'table_border': '#555555',
        'table_grid': '#444444',
        'table_alternate': '#333333',
        'table_hover': '#2a3a5a',
        'table_selection': '#6a9eff',
        'table_selection_text': '#ffffff',
    }

    @classmethod
    def get_colors(cls, is_dark_mode: bool = None):
        """获取当前主题的颜色配置"""
        if is_dark_mode is None:
            # 自动检测当前主题
            try:
                from ui.theme_manager import get_theme_manager
                theme_manager = get_theme_manager()
                is_dark_mode = theme_manager.is_dark_mode()
            except Exception:
                # 默认使用浅色主题
                is_dark_mode = False

        return cls.DARK_THEME if is_dark_mode else cls.LIGHT_THEME

    @classmethod
    def get_color(cls, color_name: str, is_dark_mode: bool = None):
        """获取特定颜色"""
        colors = cls.get_colors(is_dark_mode)
        return colors.get(color_name, '#000000')


class AppStyles:

    @staticmethod
    def _get_colors():
        """获取当前主题的颜色"""
        return ThemeColors.get_colors()

    @staticmethod
    def main_window_style() -> str:
        """主窗口样式(自动适应深色/浅色模式)"""
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
                background-color: {colors['base']};
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
            /* 复选框样式 - 只设置字体，让系统处理显示 */
            QCheckBox {{
                color: {colors['window_text']};
                font-size: 13px;
                font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
                spacing: 8px;
            }}
        """

    @staticmethod
    def button_style(active: bool = False) -> str:
        base_style = """
            QPushButton {
                border: 1px solid #4a7eff;
                border-radius: 4px;
                padding: 6px 12px;
                min-width: 70px;
                min-height: 30px;
                background-color: #4a7eff;
                color: white;
                font-weight: 500;
                font-size: 12px;
                font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
            }
            QPushButton:hover {
                background-color: #3a6eff;
                border-color: #3a6eff;
            }
            QPushButton:pressed {
                background-color: #2a5eff;
                border-color: #2a5eff;
            }
            QPushButton:disabled {
                background-color: #cbd5e1;
                border-color: #a0aec0;
                color: #718096;
            }
        """

        if active:
            active_style = """
                QPushButton {
                    background-color: #2a5eff;
                    border-color: #2a5eff;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background-color: #1a4eff;
                    border-color: #1a4eff;
                }
                QPushButton:pressed {
                    background-color: #0a3eff;
                    border-color: #0a3eff;
                }
            """
            return base_style + active_style
        return base_style

    @staticmethod
    def list_style() -> str:
        """列表样式(自动适应深色/浅色模式)"""
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
                background-color: {colors['base']};
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
                min-width: 60px;  /* 序号列最小宽度 */
            }}
            QHeaderView::section:nth-child(2) {{
                min-width: 180px; /* 频道名称列最小宽度 */
            }}
            QHeaderView::section:nth-child(3) {{
                min-width: 100px;  /* 分辨率列最小宽度 */
            }}
            QHeaderView::section:nth-child(4) {{
                min-width: 250px; /* URL列最小宽度 */
            }}
            /* 拖拽时的视觉反馈 */
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
        """状态栏样式(自动适应深色/浅色模式)"""
        return """
            QStatusBar {
                background-color: palette(button);
                color: palette(windowText);
                border-top: 1px solid palette(mid);
                padding: 6px 12px;
                font-size: 12px;
                font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
                font-weight: 500;
            }
            QStatusBar::item {
                border: none;
                padding: 0 6px;
            }
            QStatusBar QLabel {
                color: palette(windowText);
                font-size: 12px;
                font-weight: 500;
                opacity: 0.8;
            }
        """

    @staticmethod
    def status_label_style() -> str:
        return """
            QLabel {
                color: palette(windowText);
                font-weight: bold;
            }
        """

    @staticmethod
    def progress_style() -> str:
        """进度条样式"""
        return """
            QProgressBar {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                text-align: center;
                height: 24px;
                background-color: #f1f5f9;
                font-size: 11px;
                font-weight: 500;
                font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
                color: #4a5568;
            }
            QProgressBar::chunk {
                background-color: #4a7eff;
                border-radius: 5px;
                margin: 1px;
            }
        """

    @staticmethod
    def toolbar_button_style() -> str:
        """工具栏按钮样式(emoji+文字，自动适应深色/浅色模式)"""
        return """
            QToolButton {
                border: 1px solid palette(mid);
                border-radius: 4px;
                padding: 4px 8px;
                margin: 1px;
                background-color: palette(button);
                min-width: 60px;
                min-height: 28px;
                color: palette(windowText);
                font-size: 12px;
                font-weight: 500;
                font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
            }
            QToolButton:hover {
                background-color: palette(highlight);
                border-color: palette(highlight);
                color: #4a7eff;
            }
            QToolButton:pressed {
                background-color: palette(mid);
                color: #2a5eff;
            }
            QToolButton::menu-indicator {
                width: 0px;
            }
        """

    @staticmethod
    def dialog_style() -> str:
        """对话框通用样式(自动适应深色/浅色模式)"""
        return """
            QDialog {
                background-color: palette(window);
                color: palette(windowText);
                border: 1px solid palette(mid);
                border-radius: 8px;
                font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
            }
            QDialog QLabel {
                color: palette(windowText);
                font-size: 13px;
                opacity: 0.9;
            }
            QDialog QPushButton {
                min-width: 70px;
                padding: 6px 12px;
                border-radius: 4px;
                font-size: 12px;
                font-weight: 500;
            }
            QDialog QGroupBox {
                border: 1px solid palette(mid);
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 18px;
                background-color: palette(alternate-base);
            }
            QDialog QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
                color: palette(windowText);
                font-weight: 600;
                font-size: 13px;
            }
            QDialog QLineEdit, QDialog QSpinBox, QDialog QComboBox {
                border: 1px solid palette(mid);
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 13px;
                background-color: palette(base);
                color: palette(windowText);
            }
            QDialog QLineEdit:focus, QDialog QSpinBox:focus, QDialog QComboBox:focus {
                border-color: #4a7eff;
                outline: none;
            }
            /* 复选框样式 - 只设置字体，让系统处理显示 */
            QCheckBox {
                color: palette(windowText);
                font-size: 13px;
                font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
                spacing: 8px;
            }
        """

    @staticmethod
    def text_color() -> QtGui.QColor:
        """返回主题文字颜色(自动适应深色/浅色模式)"""
        # 获取系统调色板
        palette = QtGui.QGuiApplication.palette()
        # 计算背景亮度来判断深浅色模式
        bg_color = palette.color(QtGui.QPalette.ColorRole.Window)
        is_dark = bg_color.lightness() < 128

        # 深色模式返回浅色，浅色模式返回深色
        if is_dark:
            return QtGui.QColor('#f0f0f0')  # 浅灰色
        else:
            return QtGui.QColor('#333333')  # 深灰色

    @staticmethod
    def table_bg_color() -> QtGui.QColor:
        """返回表格背景色(自动适应深色/浅色模式)"""
        # 获取系统调色板
        palette = QtGui.QGuiApplication.palette()
        # 计算背景亮度来判断深浅色模式
        bg_color = palette.color(QtGui.QPalette.ColorRole.Window)
        is_dark = bg_color.lightness() < 128

        # 深色模式返回深色背景，浅色模式返回浅色背景
        if is_dark:
            return QtGui.QColor('#2a2a2a')  # 深灰色
        else:
            return QtGui.QColor('#f8f8f8')  # 浅灰色

    @staticmethod
    def drag_list_style() -> str:
        """拖拽列表样式(自动适应深色/浅色模式)"""
        return """
            QListWidget {
                border: 1px solid palette(mid);
                border-radius: 8px;
                padding: 4px;
                background-color: palette(base);
                font-size: 13px;
            }
            QListWidget::item {
                border: 1px solid transparent;
                border-radius: 6px;
                padding: 8px 12px;
                margin: 2px;
                background-color: palette(alternate-base);
                color: palette(windowText);
            }
            QListWidget::item:hover {
                background-color: palette(highlight);
                border: 1px solid palette(mid);
            }
            QListWidget::item:selected {
                background-color: #4a7eff;
                color: white;
                border: 1px solid #2a5eff;
            }
            QListWidget::item:selected:hover {
                background-color: #3a6eff;
            }
        """

    @staticmethod
    def drag_hint_label_style() -> str:
        """拖拽提示标签样式(自动适应深色/浅色模式)"""
        return """
            QLabel {
                color: #4a7eff;
                font-size: 12px;
                padding: 8px 12px;
                background-color: palette(alternate-base);
                border-radius: 6px;
                font-weight: 500;
                border: 1px solid palette(mid);
            }
        """

    @staticmethod
    def group_hint_label_style() -> str:
        """分组提示标签样式(自动适应深色/浅色模式)"""
        return """
            QLabel {
                color: palette(windowText);
                font-size: 12px;
                padding: 8px 12px;
                background-color: palette(alternate-base);
                border-radius: 6px;
                font-weight: 500;
                border: 1px solid palette(mid);
                opacity: 0.8;
            }
        """

    @staticmethod
    def statusbar_error_style() -> str:
        """状态栏错误/警告样式（红色文字）"""
        return """
            QStatusBar {
                color: #ff0000;
                font-weight: bold;
            }
        """

    @staticmethod
    def apply_button_style() -> str:
        """应用按钮样式（绿色）"""
        return """
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """

    @staticmethod
    def cancel_button_style() -> str:
        """取消按钮样式（红色）"""
        return """
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
        """

    @staticmethod
    def secondary_label_style() -> str:
        """次要标签样式（灰色文字，带内边距）"""
        return """
            QLabel {
                color: palette(windowText);
                padding: 0 5px;
                font-size: 13px;
                font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
                opacity: 0.8;
            }
        """

    @staticmethod
    def tab_widget_style() -> str:
        """标签页控件样式(自动适应深色/浅色模式)"""
        return """
            QTabWidget {
                background-color: palette(window);
                border: 1px solid palette(mid);
                border-radius: 8px;
                font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
            }
            QTabWidget::pane {
                border: 1px solid palette(mid);
                border-radius: 0 0 8px 8px;
                background-color: palette(window);
                margin-top: -1px;
            }
            QTabBar {
                background-color: palette(button);
                border-bottom: 1px solid palette(mid);
                border-radius: 8px 8px 0 0;
            }
            QTabBar::tab {
                background-color: palette(button);
                border: 1px solid palette(mid);
                border-bottom: none;
                border-radius: 6px 6px 0 0;
                padding: 8px 16px;
                margin-right: 4px;
                margin-top: 4px;
                font-size: 13px;
                font-weight: 500;
                color: palette(windowText);
                opacity: 0.8;
            }
            QTabBar::tab:selected {
                background-color: palette(window);
                border-color: palette(mid);
                border-bottom-color: palette(window);
                color: #4a7eff;
                font-weight: 600;
                opacity: 1.0;
            }
            QTabBar::tab:hover:!selected {
                background-color: palette(alternate-base);
                color: #4a7eff;
                opacity: 0.9;
            }
            QTabBar::tab:first {
                margin-left: 4px;
            }
            QTabBar::tab:last {
                margin-right: 0;
            }
        """
