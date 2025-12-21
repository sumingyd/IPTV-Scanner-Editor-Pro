"""
应用程序核心模块 - 负责协调所有模块
"""

import sys
import os
from PyQt6 import QtWidgets, QtCore, QtGui

# 导入自定义模块
from .config_manager import ConfigManager
from .log_manager import global_logger
from .language_manager import LanguageManager
from utils.error_handler import init_global_error_handler
from utils.resource_cleaner import get_resource_cleaner, register_cleanup, cleanup_all
from utils.general_utils import safe_connect, safe_connect_button


class Application:
    """应用程序主类，负责协调所有模块"""
    
    def __init__(self):
        self.logger = global_logger
        self.config = ConfigManager()
        self.language_manager = LanguageManager()
        self.main_window = None
        self.ui = None
        
    def initialize(self):
        """初始化应用程序"""
        try:
            self.logger.info("初始化应用程序...")
            
            # 加载语言设置
            self.language_manager.load_available_languages()
            language_code = self.config.load_language_settings()
            self.language_manager.set_language(language_code)
            
            self.logger.info("应用程序初始化完成")
            return True
        except Exception as e:
            self.logger.error(f"应用程序初始化失败: {e}", exc_info=True)
            return False
    
    def create_main_window(self):
        """创建主窗口"""
        from ui.main_window import MainWindow
        self.main_window = MainWindow(self)
        return self.main_window
    
    def run(self):
        """运行应用程序"""
        try:
            # 初始化应用程序
            if not self.initialize():
                self.logger.error("应用程序初始化失败，无法启动")
                return False
            
            # 创建主窗口
            self.main_window = self.create_main_window()
            if not self.main_window:
                self.logger.error("创建主窗口失败")
                return False
            
            # 显示主窗口
            self.main_window.show()
            
            self.logger.info("应用程序启动成功")
            return True
        except Exception as e:
            self.logger.error(f"应用程序运行失败: {e}", exc_info=True)
            return False
    
    def cleanup(self):
        """清理应用程序资源"""
        self.logger.info("清理应用程序资源...")
        
        # 清理主窗口资源
        if self.main_window:
            self.main_window.save_before_exit()
        
        # 使用全局资源清理器
        cleanup_all()
        
        self.logger.info("应用程序资源清理完成")


def create_application():
    """创建应用程序实例"""
    return Application()


def setup_application_font(app):
    """设置应用程序字体"""
    font_family = "Microsoft YaHei"  # 微软雅黑字体
    font = QtGui.QFont(font_family)
    font.setPointSize(9)  # 设置字体大小
    app.setFont(font)  # 设置应用程序字体
    # 设置应用程序样式表，确保所有控件使用统一字体
    app.setStyleSheet(f"""
        QWidget {{
            font-family: "{font_family}";
            font-size: 9pt;
        }}
    """)
    return app
