from PyQt6 import QtCore, QtGui, QtWidgets
from log_manager import LogManager

class AppStyles:
    @staticmethod
    def _init_logger():
        logger = LogManager()
        logger.info("应用样式初始化完成")
        return logger

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
    def epg_program_style():
        """EPG节目单样式(适配深色/浅色模式)"""
        return """
            QScrollArea#epg_container {
                background-color: palette(base);
                border: none;
            }
            QWidget#epg_container_widget {
                background-color: palette(base);
            }
            QWidget#epg_program {
                background-color: palette(base);
                border-bottom: 1px solid palette(mid);
                padding: 8px;
            }
            QWidget#epg_program_current {
                background-color: palette(highlight);
                border-bottom: 1px solid palette(mid);
                padding: 8px;
                margin: 0;
            }
            QLabel#epg_title {
                color: palette(text);
                font-size: 14px;
            }
            QLabel#epg_title_current {
                color: white;
                font-weight: bold;
                font-size: 14px;
            }
            QLabel#epg_time {
                color: palette(placeholderText);
                font-size: 12px;
            }
            QLabel#epg_time_current {
                color: white;
                font-weight: bold;
                font-size: 12px;
            }
        """

    @staticmethod
    def list_style() -> str:
        return """
            QTableView {
                border: 1px solid palette(mid);
                alternate-background-color: palette(alternateBase);
                selection-background-color: palette(highlight);
                selection-color: palette(highlightedText);
            }
            QHeaderView::section {
                background-color: palette(button);
                padding: 4px;
                border: 1px solid palette(mid);
                color: palette(windowText);
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
    def epg_style() -> str:
        return """
            QTableWidget {
                font-size: 12px;
                alternate-background-color: #f0f0f0;
            }
            QTableWidget::item {
                padding: 5px;
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
