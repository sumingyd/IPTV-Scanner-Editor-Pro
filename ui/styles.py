from PyQt6 import QtGui


class AppStyles:

    @staticmethod
    def main_window_style() -> str:
        return """
            QMainWindow {
                background-color: palette(window);
                color: palette(windowText);
            }
            QGroupBox {
                border: 1px solid #ccc;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 15px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px;
            }
        """

    @staticmethod
    def button_style(active: bool = False) -> str:
        base_style = """
            QPushButton {
                border: 1px solid #4a7eff;
                border-radius: 3px;
                padding: 5px 10px;
                min-width: 80px;
                background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #8fb5ff, stop: 1 #6a9eff);
                color: white;
            }
            QPushButton:hover {
                background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #7aa5ff, stop: 1 #5a8eff);
            }
            QPushButton:pressed {
                background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #5a8eff, stop: 1 #4a7eff);
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """

        if active:
            active_style = """
                QPushButton {
                    background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                        stop: 0 #4a7eff, stop: 1 #2a5eff);
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                        stop: 0 #3a6eff, stop: 1 #1a5eff);
                }
                QPushButton:pressed {
                    background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                        stop: 0 #1a5eff, stop: 1 #0a4eff);
                }
            """
            return base_style + active_style
        return base_style

    @staticmethod
    def list_style() -> str:
        return """
            QTableView {
                border: 1px solid palette(mid);
                alternate-background-color: palette(alternateBase);
                selection-background-color: palette(highlight);
                selection-color: palette(highlightedText);
            }
            QHeaderView {
                background-color: palette(button);
            }
            QHeaderView::section {
                background-color: palette(button);
                padding: 4px;
                border: 1px solid palette(mid);
                color: palette(windowText);
            }
            QHeaderView::section:first {
                min-width: 50px;  /* 序号列最小宽度 */
            }
            QHeaderView::section:nth-child(2) {
                min-width: 150px; /* 频道名称列最小宽度 */
            }
            QHeaderView::section:nth-child(3) {
                min-width: 80px;  /* 分辨率列最小宽度 */
            }
            QHeaderView::section:nth-child(4) {
                min-width: 200px; /* URL列最小宽度 */
            }
        """

    @staticmethod
    def statusbar_style() -> str:
        """状态栏样式(跟随系统深色/浅色模式)"""
        return """
            QStatusBar {
                background-color: palette(window);
                color: palette(windowText);
                border-top: 1px solid palette(mid);
                padding: 2px;
                font-size: 12px;
            }
            QStatusBar::item {
                border: none;
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
                border: 1px solid #ccc;
                border-radius: 3px;
                text-align: center;
                height: 20px;
            }
            QProgressBar::chunk {
                background-color: #1890ff;
                width: 10px;
            }
        """

    @staticmethod
    def toolbar_button_style() -> str:
        """工具栏按钮样式(emoji+文字)"""
        return """
            QToolButton {
                border: none;
                padding: 2px 5px;
                margin: 1px;
                background: transparent;
                min-width: 60px;
                min-height: 30px;
                color: palette(windowText);
            }
            QToolButton:hover {
                color: palette(highlight);
            }
            QToolButton:pressed {
                color: palette(highlightedText);
                background: palette(highlight);
            }
        """

    @staticmethod
    def dialog_style() -> str:
        """对话框通用样式"""
        return """
            QDialog {
                background-color: palette(window);
                color: palette(windowText);
                border: 1px solid palette(mid);
            }
            QDialog QLabel {
                color: palette(windowText);
            }
            QDialog QPushButton {
                min-width: 80px;
                padding: 5px;
            }
            QDialog QGroupBox {
                border: 1px solid palette(mid);
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 15px;
            }
            QDialog QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px;
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
        """拖拽列表样式"""
        return """
            QListWidget {
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 2px;
                background-color: white;
            }
            QListWidget::item {
                border: 1px solid transparent;
                border-radius: 3px;
                padding: 6px 8px;
                margin: 1px;
                background-color: #f8f9fa;
            }
            QListWidget::item:hover {
                background-color: #e9ecef;
                border: 1px solid #dee2e6;
            }
            QListWidget::item:selected {
                background-color: #007bff;
                color: white;
                border: 1px solid #0056b3;
            }
            QListWidget::item:selected:hover {
                background-color: #0056b3;
            }
        """

    @staticmethod
    def drag_hint_label_style() -> str:
        """拖拽提示标签样式"""
        return """
            QLabel {
                color: #007bff;
                font-size: 11px;
                padding: 5px;
                background-color: #e7f3ff;
                border-radius: 4px;
            }
        """

    @staticmethod
    def group_hint_label_style() -> str:
        """分组提示标签样式"""
        return """
            QLabel {
                color: #666;
                font-size: 11px;
                padding: 5px;
                background-color: #f5f5f5;
                border-radius: 4px;
            }
        """
