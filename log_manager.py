"""全局日志管理器 - 单例模式，统一管理所有日志记录"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from typing import Optional


class LogManager:
    """全局日志管理器（单例模式）
    
    统一管理应用程序的所有日志记录，避免多实例竞争和日志混乱。
    支持文件轮转和控制台输出。
    """
    
    _instance: Optional['LogManager'] = None
    _initialized: bool = False
    
    def __new__(cls, *args, **kwargs):
        """单例模式实现"""
        if not cls._instance:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
        
    def __init__(self, log_file: str = 'app.log', max_bytes: int = 5*1024*1024, 
                 backup_count: int = 3, level: int = logging.DEBUG):
        """初始化日志管理器
        
        Args:
            log_file: 日志文件名
            max_bytes: 单个日志文件最大字节数
            backup_count: 备份文件数量
            level: 日志级别
        """
        if self._initialized:
            return
            
        self.log_file = self._get_log_path(log_file)
        self.level = level
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        
        # 配置日志记录器
        self._setup_logger()
        
        self._initialized = True
    
    def _get_log_path(self, log_file: str) -> str:
        """获取日志文件路径
        
        Args:
            log_file: 日志文件名
            
        Returns:
            日志文件的完整路径
        """
        if getattr(sys, 'frozen', False):
            # 打包成exe的情况
            log_dir = os.path.dirname(sys.executable)
        else:
            # 开发环境
            log_dir = os.path.dirname(__file__)
        return os.path.join(log_dir, log_file)
    
    def _setup_logger(self):
        """配置日志记录器"""
        # 获取全局日志记录器
        self.logger = logging.getLogger('IPTVScanner')
        self.logger.setLevel(self.level)
        
        # 避免重复添加handler
        if self.logger.handlers:
            return
            
        # 创建文件handler（轮转文件）
        file_handler = RotatingFileHandler(
            self.log_file,
            maxBytes=self.max_bytes,
            backupCount=self.backup_count,
            encoding='utf-8',
            mode='a'
        )
        file_handler.setLevel(self.level)
        
        # 创建控制台handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.WARNING)  # 控制台只显示警告及以上级别
        
        # 设置日志格式
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        # 添加handler
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        
        # 清空日志文件内容（每次启动时）
        self._clear_log_file()
    
    def _clear_log_file(self):
        """清空日志文件内容"""
        try:
            with open(self.log_file, 'w', encoding='utf-8') as f:
                f.write('')
        except Exception as e:
            print(f"清空日志文件失败: {e}")
    
    def debug(self, message: str):
        """记录调试信息
        
        Args:
            message: 调试消息
        """
        self.logger.debug(message)
        
    def info(self, message: str):
        """记录普通信息
        
        Args:
            message: 信息消息
        """
        self.logger.info(message)
        
    def warning(self, message: str):
        """记录警告信息
        
        Args:
            message: 警告消息
        """
        self.logger.warning(message)
        
    def error(self, message: str, exc_info: bool = False):
        """记录错误信息
        
        Args:
            message: 错误消息
            exc_info: 是否记录异常堆栈信息
        """
        if exc_info:
            self.logger.error(message, exc_info=True)
        else:
            self.logger.error(message)
        
    def critical(self, message: str):
        """记录严重错误信息
        
        Args:
            message: 严重错误消息
        """
        self.logger.critical(message)
    
    def set_level(self, level: int):
        """设置日志级别
        
        Args:
            level: 日志级别
        """
        self.logger.setLevel(level)
        for handler in self.logger.handlers:
            handler.setLevel(level)
    
    def get_logger(self) -> logging.Logger:
        """获取底层的logging.Logger对象
        
        Returns:
            底层的日志记录器
        """
        return self.logger


# 全局日志管理器实例
global_logger = LogManager()


def get_logger(name: str = 'IPTVScanner') -> logging.Logger:
    """获取指定名称的日志记录器
    
    Args:
        name: 日志记录器名称
        
    Returns:
        配置好的日志记录器
    """
    return logging.getLogger(name)
