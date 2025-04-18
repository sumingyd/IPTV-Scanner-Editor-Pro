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
        
        # 先加载配置再构建UI
        self.ui = UIBuilder(self)
        self.ui.build_ui()

    def save_before_exit(self):
        """程序退出前保存所有配置"""
        try:
            # 保存窗口布局
            size = self.size()
            dividers = [
                *self.ui.main_window.main_splitter.sizes(),
                *self.ui.main_window.left_splitter.sizes(),
                *self.ui.main_window.right_splitter.sizes(),
                *self.ui.main_window.h_splitter.sizes()
            ]
            self.config.save_window_layout(size.width(), size.height(), dividers)
            
            # 保存网络设置
            self.config.save_network_settings(
                self.ui.main_window.ip_range_input.text(),
                self.ui.main_window.timeout_input.value(),
                self.ui.main_window.thread_count_input.value(),
                self.ui.main_window.user_agent_input.text(),
                self.ui.main_window.referer_input.text()
            )
            self.logger.info("程序退出前配置已保存")
        except Exception as e:
            self.logger.error(f"保存退出配置失败: {e}")
        
        # 加载保存的网络设置
        try:
            settings = self.config.load_network_settings()
            if settings['url']:
                self.ui.main_window.ip_range_input.setText(settings['url'])
            self.ui.main_window.timeout_input.setValue(int(settings['timeout']))
            self.ui.main_window.thread_count_input.setValue(int(settings['threads']))
            if settings['user_agent']:
                self.ui.main_window.user_agent_input.setText(settings['user_agent'])
            if settings['referer']:
                self.ui.main_window.referer_input.setText(settings['referer'])
        except Exception as e:
            self.logger.error(f"加载网络设置失败: {e}")
            # 设置默认值
            self.ui.main_window.timeout_input.setValue(10)
            self.ui.main_window.thread_count_input.setValue(5)
        
        # 记录启动日志
        self.logger.info("应用程序启动")

def main():
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    
    # 确保程序退出前保存所有配置
    app.aboutToQuit.connect(window.save_before_exit)
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
