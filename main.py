"""
IPTV扫描编辑器 - 主程序入口
使用新的模块化架构
"""

import sys
import os
from PyQt6 import QtWidgets, QtCore, QtGui

# 导入新的模块化架构
from core.application import create_application, setup_application_font
from ui.main_window import MainWindow
from core.log_manager import global_logger


def main():
    """主函数，应用程序入口点"""
    # 创建QApplication实例，传入命令行参数
    app = QtWidgets.QApplication(sys.argv)
    
    # 设置应用程序字体
    app = setup_application_font(app)
    
    # 创建应用程序实例
    application = create_application()
    
    # 初始化应用程序
    if not application.initialize():
        global_logger.error("应用程序初始化失败，无法启动")
        return 1
    
    try:
        # 创建主窗口
        window = MainWindow(application)
        window.show()
        
        # 将主窗口保存到应用程序属性中
        app.main_window = window
        
        # 清理函数，在应用程序退出前调用
        def cleanup():
            if hasattr(app, 'main_window'):
                app.main_window.save_before_exit()
        
        # 连接应用程序退出信号到清理函数
        app.aboutToQuit.connect(cleanup)
        
        global_logger.info("应用程序启动成功")
        
        # 启动应用程序事件循环
        return app.exec()
        
    except Exception as e:
        global_logger.error(f"创建主窗口失败: {e}", exc_info=True)
        QtWidgets.QApplication.instance().quit()
        return 1


# Python标准入口点
if __name__ == "__main__":
    sys.exit(main())
