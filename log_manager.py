import logging
import os
from logging.handlers import RotatingFileHandler

class LogManager:
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
        
    def __init__(self, log_file='app.log', max_bytes=5*1024*1024, backup_count=3):
        if self._initialized:
            return
            
        self.log_file = os.path.join(os.path.dirname(__file__), log_file)
        self.logger = logging.getLogger('IPTVLogger')
        self.logger.setLevel(logging.DEBUG)
        
        # 清空现有日志文件
        with open(self.log_file, 'w', encoding='utf-8') as f:
            pass
            
        # 确保只有一个handler
        if not self.logger.handlers:
            handler = RotatingFileHandler(
                self.log_file, 
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding='utf-8',
                mode='w'
            )
            handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            ))
            self.logger.addHandler(handler)
            
        self._initialized = True
    
    def debug(self, message):
        self.logger.debug(message)
        
    def info(self, message):
        self.logger.info(message)
        
    def warning(self, message):
        self.logger.warning(message)
        
    def error(self, message, exc_info=False):
        """记录错误日志
        :param message: 错误消息
        :param exc_info: 是否记录异常信息
        """
        if exc_info:
            self.logger.error(message, exc_info=True)
        else:
            self.logger.error(message)
        
    def critical(self, message):
        self.logger.critical(message)
