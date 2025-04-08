class AppStyles: #应用样式
    """样式定义类"""
    #按钮样式
    @staticmethod
    def button_style(active=False):  
        """按钮样式
        :param active: 是否激活状态
        """
        return """
        QPushButton {
            background-color: %s;
            color: palette(buttonText);
            border: 1px solid palette(mid);
            padding: 8px 16px;
            border-radius: 4px;
            font-weight: bold;
            min-width: 80px;
            font-size: 14px;
        }
        QPushButton::text {
            color: palette(windowText);
        }
        QPushButton:hover {
            background-color: palette(light);
            border-color: palette(highlight);
        }
        QPushButton:pressed {
            background-color: palette(mid);
            color: palette(highlightedText);
        }
        QPushButton:disabled {
            background-color: palette(window);
            color: palette(mid);
        }
        """ % ("palette(highlight)" if active else "palette(button)")
    #列表样式
    @staticmethod
    def list_style():  
        """列表样式"""
        return """
        QTableView {
            border: 1px solid palette(mid);
            border-radius: 6px;
            gridline-color: transparent;
            font-size: 13px;
            background: palette(base);
        }
        QTableView::item {
            padding: 10px 8px;
            border-bottom: 1px solid palette(alternate-base);
        }
        QTableView::item:nth-child(even) {
            background-color: palette(alternate-base);
        }
        QTableView::item:nth-child(odd) {
            background-color: palette(base);
        }
        QTableView::item:selected {
            background: palette(highlight);
            color: palette(highlighted-text);
            border-left: 4px solid palette(dark);
        }
        QTableView::item:hover {
            background: palette(light);
            border-left: 4px solid palette(highlight);
        }
        QHeaderView::section {
            background: palette(button);
            padding: 10px 8px;
            border: none;
            border-bottom: 2px solid palette(highlight);
            font-weight: bold;
            font-size: 13px;
            color: palette(window-text);
        }
        QHeaderView::section:hover {
            background: palette(mid);
            color: palette(highlight);
        }
        QHeaderView::section:pressed {
            background: palette(dark);
        }
    """
        #进度条样式
    @staticmethod
    def main_window_style():
        """主窗口样式"""
        return """
        QMainWindow {
            background: palette(window);
            border: 1px solid palette(mid);
        }
        QMainWindow::separator {
            width: 1px;
            background: palette(mid);
        }
        """

    @staticmethod
    def statusbar_style():
        """状态栏样式"""
        return """
        QStatusBar {
            background: palette(window);
            border-top: 1px solid palette(mid);
            padding: 4px 12px;
            font-size: 13px;
            color: palette(window-text);
            min-height: 28px;
            border-radius: 0 0 6px 6px;
        }
        QStatusBar::item {
            border: none;
            padding: 0 8px;
            border-radius: 3px;
        }
        QStatusBar::item:hover {
            background: rgba(0,0,0,0.05);
        }
        QStatusBar QLabel {
            background: transparent;
            padding: 2px 8px;
            font-weight: 500;
            border-radius: 3px;
        }
        QStatusBar QLabel:hover {
            background: rgba(0,0,0,0.05);
        }
        QStatusBar QLabel[status="error"] {
            color: palette(highlight);
            font-weight: bold;
            background: rgba(255,0,0,0.1);
            padding: 2px 10px;
        }
        QStatusBar QLabel[status="success"] {
            color: palette(highlight);
            font-weight: bold;
            background: rgba(0,255,0,0.1);
            padding: 2px 10px;
        }
        QStatusBar QLabel[status="warning"] {
            color: palette(highlight);
            font-weight: bold;
            background: rgba(255,165,0,0.1);
            padding: 2px 10px;
        }
        """

    @staticmethod
    def splitter_handle_style(orientation="horizontal"):
        """简洁圆角分割线样式
        - 垂直分隔条(左右拖动): 细线(2px) + 圆角
        - 水平分隔条(上下拖动): 稍粗(4px) + 圆角
        """
        if orientation == "vertical":
            return """
            QSplitter::handle {
                background: #42A5F5;
                width: 2px;
                margin: 0 1px;  /* 左右留1px间隙 */
                border-radius: 3px;
                border: 1px solid #64B5F6;
            }
            """
        else:
            return """
            QSplitter::handle {
                background: #42A5F5;
                height: 4px;
                margin: 1px 0;  /* 上下留1px间隙 */
                border-radius: 3px;
                border: 1px solid #64B5F6;
            }
            """
        
    @staticmethod
    def progress_style():  
        """进度条样式"""
        return """
        QProgressBar {
            border: 2px solid palette(mid);
            border-radius: 8px;
            text-align: center;
            background: palette(base);
            height: 24px;
            min-width: 200px;
            font-size: 12px;
            color: palette(window-text);
        }
        QProgressBar::chunk {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #4FC3F7, stop:0.5 #29B6F6, stop:1 #039BE5);
            border-radius: 6px;
            border: 1px solid rgba(255,255,255,0.3);
            width: 0px;
            margin: 0px;
        }
        QProgressBar::chunk:hover {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #81D4FA, stop:0.5 #4FC3F7, stop:1 #29B6F6);
        }
    """

    @staticmethod
    def status_label_style():
        """状态标签样式"""
        return """
        QLabel {
            color: palette(windowText);
            font-weight: bold;
        }
        """

    @staticmethod
    def input_style():
        """输入框样式"""
        return """
        QLineEdit {
            min-height: 32px;
            padding: 5px 10px;
            border: 1px solid palette(mid);
            border-radius: 4px;
            background: palette(base);
            color: palette(text);
        }
        QLineEdit:hover {
            border-color: palette(highlight);
        }
        QLineEdit:focus {
            border: 2px solid palette(highlight);
            padding: 4px 9px;
        }
        """

    @staticmethod
    def toolbar_button_style():
        """工具栏按钮样式"""
        return """
        QPushButton {
            background-color: palette(button);
            color: palette(buttonText);
            border: 1px solid palette(mid);
            padding: 6px 12px;
            border-radius: 4px;
            font-weight: bold;
            min-width: 80px;
            font-size: 13px;
        }
        QPushButton:hover {
            background-color: palette(light);
            border-color: palette(highlight);
        }
        QPushButton:pressed {
            background-color: palette(mid);
            color: palette(highlightedText);
        }
        """

    @staticmethod
    def checkbox_style():
        """复选框样式"""
        return """
        QCheckBox {
            spacing: 5px;
            color: palette(windowText);
        }
        QCheckBox::indicator {
            width: 16px;
            height: 16px;
        }
        QCheckBox::indicator:checked {
            background-color: palette(highlight);
            border: 1px solid palette(dark);
        }
        QCheckBox::indicator:unchecked {
            background-color: palette(base);
            border: 1px solid palette(mid);
        }
        """

    @staticmethod
    def stats_label_style():
        """统计标签样式"""
        return """
        QLabel {
            color: palette(windowText);
            font-weight: bold;
        }
        """

    @staticmethod
    def player_button_style():
        """播放器控制按钮样式"""
        return """
        QPushButton {
            background-color: palette(button);
            color: palette(buttonText);
            border: 1px solid palette(mid);
            padding: 6px 12px;
            border-radius: 4px;
            font-weight: bold;
            min-width: 80px;
            font-size: 13px;
        }
        QPushButton:hover {
            background-color: palette(light);
            border-color: palette(highlight);
        }
        QPushButton:pressed {
            background-color: palette(mid);
            color: palette(highlightedText);
        }
        """

    @staticmethod
    def match_status_style(color="#666"):
        """匹配状态标签样式"""
        return f"""
        QLabel {{
            color: {color};
            font-weight: bold;
        }}
        """

    @staticmethod
    def epg_status_style(is_matched=True):
        """EPG状态标签样式"""
        if is_matched:
            return """
            QLabel {
                color: #4CAF50;
                font-weight: bold;
            }
            """
        else:
            return """
            QLabel {
                color: #FF9800;
                font-weight: bold;
            }
            """
