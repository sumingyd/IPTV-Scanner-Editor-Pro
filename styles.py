from PyQt6 import QtCore, QtGui, QtWidgets

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
    def statusbar_style() -> str:
        return """
            QStatusBar {
                background-color: palette(base);
                border-top: 1px solid palette(mid);
                padding: 2px;
            }
            QStatusBar QLabel {
                color: palette(text);
            }
        """

    @staticmethod
    def progress_style() -> str:
        return """
            QProgressBar {
                border: 1px solid palette(mid);
                border-radius: 3px;
                text-align: center;
                background-color: palette(base);
                color: palette(text);
            }
            QProgressBar::chunk {
                background-color: palette(highlight);
                width: 10px;
            }
        """

    @staticmethod
    def splitter_handle_style() -> str:
        return """
                    QSplitter::handle {
                        background: transparent;
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
    def status_label_style() -> str:
        return """
            QLabel {
                color: palette(windowText);
                font-weight: bold;
            }
        """

    @staticmethod
    def epg_sidebar_style():
        return """
            QWidget#epg_sidebar {
                background: rgba(40, 40, 45, 220);
                border-left: 1px solid #555;
            }
            QLabel#epg_title {
                color: #4a7eff;
                font-size: 16px;
                font-weight: bold;
                padding-bottom: 8px;
                border-bottom: 1px solid #555;
            }
            QListWidget#epg_list {
                background: transparent;
                border: none;
                font-size: 13px;
                outline: 0;
            }
            QListWidget#epg_list::item {
                padding: 8px;
                border-bottom: 1px solid #333;
                color: #ddd;
            }
            QListWidget#epg_list::item:selected {
                background: rgba(74, 126, 255, 150);
                color: white;
            }
            QPushButton#epg_toggle_btn {
                background: rgba(50, 50, 50, 150);
                color: white;
                border: none;
                font-weight: bold;
                min-width: 20px;
                max-width: 20px;
            }
            QPushButton#epg_nav_btn {
                background: rgba(70, 70, 70, 150);
                color: white;
                border: none;
                min-width: 30px;
                max-width: 30px;
                min-height: 25px;
            }
        """
