from PyQt6 import QtGui


class AppStyles:

    @staticmethod
    def main_window_style() -> str:
        """主窗口样式(自动适应深色/浅色模式)"""
        return """
            QMainWindow {
                background-color: palette(window);
                color: palette(windowText);
                font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
                font-size: 13px;
            }
            QGroupBox {
                border: 1px solid palette(mid);
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 16px;
                font-weight: 600;
                font-size: 13px;
                background-color: palette(base);
                color: palette(windowText);
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
                color: palette(windowText);
                font-weight: 600;
            }
            QSplitter::handle {
                background-color: palette(mid);
            }
            QSplitter::handle:hover {
                background-color: palette(highlight);
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
        return """
            QTableView {
                border: 1px solid palette(mid);
                border-radius: 6px;
                alternate-background-color: palette(alternate-base);
                selection-background-color: #4a7eff;
                selection-color: white;
                gridline-color: palette(mid);
                font-size: 12px;
                font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
                background-color: palette(base);
            }
            QTableView::item {
                padding: 6px 10px;
                border-bottom: 1px solid palette(mid);
                color: palette(windowText);
            }
            QTableView::item:hover {
                background-color: palette(highlight);
                border: 1px solid palette(mid);
                border-radius: 4px;
            }
            QTableView::item:selected {
                background-color: #4a7eff;
                color: white;
                font-weight: 500;
                border: 1px solid #2a5eff;
                border-radius: 4px;
            }
            QTableView::item:selected:hover {
                background-color: #3a6eff;
                border-color: #1a4eff;
            }
            QHeaderView {
                background-color: palette(button);
                border: none;
            }
            QHeaderView::section {
                background-color: palette(button);
                padding: 8px 12px;
                border: none;
                border-right: 1px solid palette(mid);
                color: palette(windowText);
                font-weight: 600;
                font-size: 12px;
                font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
            }
            QHeaderView::section:last {
                border-right: none;
            }
            QHeaderView::section:first {
                min-width: 60px;  /* 序号列最小宽度 */
            }
            QHeaderView::section:nth-child(2) {
                min-width: 180px; /* 频道名称列最小宽度 */
            }
            QHeaderView::section:nth-child(3) {
                min-width: 100px;  /* 分辨率列最小宽度 */
            }
            QHeaderView::section:nth-child(4) {
                min-width: 250px; /* URL列最小宽度 */
            }
            /* 拖拽时的视觉反馈 */
            QTableView::item:drag {
                background-color: #4a7eff;
                color: white;
                border: 2px dashed #2a5eff;
                border-radius: 4px;
                opacity: 0.7;
            }
            QTableView::item:drop {
                background-color: palette(highlight);
                border: 2px solid #4a7eff;
                border-radius: 4px;
            }
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
