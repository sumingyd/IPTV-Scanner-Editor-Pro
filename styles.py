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
    def progress_style():  
        """进度条样式"""
        return"""
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
