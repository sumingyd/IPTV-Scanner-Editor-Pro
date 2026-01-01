from PyQt6 import QtGui


class AppStyles:

    @staticmethod
    def main_window_style() -> str:
        return """
            QMainWindow {
                background-color: #f5f7fa;
                color: #2d3748;
                font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
            }
            QGroupBox {
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 16px;
                font-weight: 600;
                font-size: 13px;
                background-color: white;
                color: #4a5568;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
                color: #4a5568;
                font-weight: 600;
            }
            QSplitter::handle {
                background-color: #e2e8f0;
            }
            QSplitter::handle:hover {
                background-color: #a0aec0;
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
        return """
            QTableView {
                border: 1px solid #e2e8f0;
                border-radius: 6px;
                alternate-background-color: #f8fafc;
                selection-background-color: #4a7eff;
                selection-color: white;
                gridline-color: #e2e8f0;
                font-size: 12px;
                font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
                background-color: white;
            }
            QTableView::item {
                padding: 6px 10px;
                border-bottom: 1px solid #f1f5f9;
            }
            QTableView::item:selected {
                background-color: #4a7eff;
                color: white;
                font-weight: 500;
            }
            QHeaderView {
                background-color: #f1f5f9;
                border: none;
            }
            QHeaderView::section {
                background-color: #f1f5f9;
                padding: 8px 12px;
                border: none;
                border-right: 1px solid #e2e8f0;
                color: #4a5568;
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
        """

    @staticmethod
    def statusbar_style() -> str:
        """状态栏样式(跟随系统深色/浅色模式)"""
        return """
            QStatusBar {
                background-color: #f1f5f9;
                color: #4a5568;
                border-top: 1px solid #e2e8f0;
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
                color: #718096;
                font-size: 12px;
                font-weight: 500;
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
        """工具栏按钮样式(emoji+文字)"""
        return """
            QToolButton {
                border: 1px solid #e2e8f0;
                border-radius: 4px;
                padding: 4px 8px;
                margin: 1px;
                background-color: white;
                min-width: 60px;
                min-height: 28px;
                color: #4a5568;
                font-size: 12px;
                font-weight: 500;
                font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
            }
            QToolButton:hover {
                background-color: #f1f5f9;
                border-color: #cbd5e1;
                color: #4a7eff;
            }
            QToolButton:pressed {
                background-color: #e2e8f0;
                color: #2a5eff;
            }
            QToolButton::menu-indicator {
                width: 0px;
            }
        """

    @staticmethod
    def dialog_style() -> str:
        """对话框通用样式"""
        return """
            QDialog {
                background-color: #ffffff;
                color: #333333;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
            }
            QDialog QLabel {
                color: #555;
                font-size: 13px;
            }
            QDialog QPushButton {
                min-width: 70px;
                padding: 6px 12px;
                border-radius: 4px;
                font-size: 12px;
                font-weight: 500;
            }
            QDialog QGroupBox {
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 18px;
                background-color: #f8f9fa;
            }
            QDialog QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
                color: #555;
                font-weight: 600;
                font-size: 13px;
            }
            QDialog QLineEdit, QDialog QSpinBox, QDialog QComboBox {
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 13px;
                background-color: white;
            }
            QDialog QLineEdit:focus, QDialog QSpinBox:focus, QDialog QComboBox:focus {
                border-color: #4a7eff;
                outline: none;
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
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 4px;
                background-color: white;
                font-size: 13px;
            }
            QListWidget::item {
                border: 1px solid transparent;
                border-radius: 6px;
                padding: 8px 12px;
                margin: 2px;
                background-color: #f8f9fa;
            }
            QListWidget::item:hover {
                background-color: #e9ecef;
                border: 1px solid #dee2e6;
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
        """拖拽提示标签样式"""
        return """
            QLabel {
                color: #4a7eff;
                font-size: 12px;
                padding: 8px 12px;
                background-color: #f0f5ff;
                border-radius: 6px;
                font-weight: 500;
                border: 1px solid #e0ebff;
            }
        """

    @staticmethod
    def group_hint_label_style() -> str:
        """分组提示标签样式"""
        return """
            QLabel {
                color: #666;
                font-size: 12px;
                padding: 8px 12px;
                background-color: #f8f9fa;
                border-radius: 6px;
                font-weight: 500;
                border: 1px solid #e9ecef;
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
                color: #666;
                padding: 0 5px;
            }
        """

    @staticmethod
    def tab_widget_style() -> str:
        """标签页控件样式"""
        return """
            QTabWidget {
                background-color: white;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
            }
            QTabWidget::pane {
                border: 1px solid #e0e0e0;
                border-radius: 0 0 8px 8px;
                background-color: white;
                margin-top: -1px;
            }
            QTabBar {
                background-color: #f8f9fa;
                border-bottom: 1px solid #e0e0e0;
                border-radius: 8px 8px 0 0;
            }
            QTabBar::tab {
                background-color: #f8f9fa;
                border: 1px solid #e0e0e0;
                border-bottom: none;
                border-radius: 6px 6px 0 0;
                padding: 8px 16px;
                margin-right: 4px;
                margin-top: 4px;
                font-size: 13px;
                font-weight: 500;
                color: #666;
            }
            QTabBar::tab:selected {
                background-color: white;
                border-color: #e0e0e0;
                border-bottom-color: white;
                color: #4a7eff;
                font-weight: 600;
            }
            QTabBar::tab:hover:!selected {
                background-color: #e9ecef;
                color: #4a7eff;
            }
            QTabBar::tab:first {
                margin-left: 4px;
            }
            QTabBar::tab:last {
                margin-right: 0;
            }
        """
