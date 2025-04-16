from PyQt6 import QtWidgets
from ui_builder import UIBuilder
from config_manager import ConfigManager
from log_manager import LogManager
import sys

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        # 初始化配置和日志管理器
        self.config = ConfigManager()
        self.logger = LogManager()
        
        self.ui = UIBuilder(self)
        self.ui.build_ui()
        
        # 记录启动日志
        self.logger.info("应用程序启动")

def main():
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
