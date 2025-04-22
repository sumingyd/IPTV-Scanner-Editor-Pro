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
        return """
        #epg_container {
            background-color: #f5f5f5;
            border: none;
        }
        #epg_container_widget {
            background-color: #f5f5f5;
        }
        #epg_program {
            background-color: white;
            border-bottom: 1px solid #eee;
            padding: 8px;
        }
        #epg_program_current {
            background-color: #e6f7ff;
            border-bottom: 2px solid #1890ff;
            padding: 8px;
        }
        #epg_title {
            color: #333;
            font-size: 14px;
        }
        #epg_title_current {
            color: #1890ff;
            font-size: 14px;
            font-weight: bold;
        }
        #epg_time {
            color: #666;
            font-size: 12px;
        }
        #epg_time_current {
            color: #1890ff;
            font-size: 12px;
            font-weight: bold;
        }
        QPushButton:enabled {
            background-color: #1890ff;
            color: white;
            border: none;
            padding: 5px 10px;
            border-radius: 4px;
        }
        QPushButton:disabled {
            background-color: #d9d9d9;
            color: #999;
            border: none;
            padding: 5px 10px;
            border-radius: 4px;
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
    def dialog_style() -> str:
        return """
            QDialog {
                background-color: palette(window);
                color: palette(windowText);
            }
            QDialog QGroupBox {
                border: 1px solid #ccc;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 15px;
            }
            QDialog QLineEdit {
                padding: 5px;
                border: 1px solid #ccc;
                border-radius: 3px;
            }
            QDialog QPushButton {
                min-width: 80px;
                padding: 5px 10px;
            }
        """

    @staticmethod
    def epg_program_style() -> str:
        """EPG节目单样式"""
        return """
            /* 节目单容器样式 */
            QWidget#epg_container {
                background: transparent;
            }
            
            /* 普通节目项样式 */
            QGroupBox.epg_program {
                border: 1px solid #444;
                border-radius: 4px;
                margin-top: 5px;
                margin-bottom: 5px;
                padding: 5px;
            }
            
            /* 当前播放节目样式 */
            QGroupBox.epg_program_current {
                border: 2px solid #4CAF50;
                background: rgba(76, 175, 80, 0.1);
            }
            
            /* 节目标题样式 */
            QLabel.epg_title {
                margin: 2px;
                font-weight: bold;
            }
            
            /* 当前播放节目标题样式 */
            QLabel.epg_title_current {
                margin: 2px;
                font-weight: bold;
                color: #4CAF50;
            }
            
            /* 节目描述样式 */
            QLabel.epg_desc {
                margin: 2px;
                word-wrap: break-word;
            }
        """
