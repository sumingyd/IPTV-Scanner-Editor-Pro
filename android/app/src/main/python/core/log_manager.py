import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from utils.singleton import Singleton


class LogManager(Singleton):

    def __init__(self, log_file: str = 'app.log', max_bytes: int = 5*1024*1024,
                 backup_count: int = 0, level: int = logging.INFO):
        if self._initialized:
            return

        self.log_file = self._get_log_path(log_file)
        self.level = level
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self._setup_logger()
        self._initialized = True

    def _get_log_path(self, log_file: str) -> str:
        if getattr(sys, 'frozen', False):
            log_dir = os.path.dirname(sys.executable)
        else:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            log_dir = os.path.dirname(current_dir)
        return os.path.join(log_dir, log_file)

    def _setup_logger(self):
        try:
            self.logger = logging.getLogger('IPTVScanner')
            self.logger.setLevel(self.level)

            if self.logger.handlers:
                return

            log_dir = os.path.dirname(self.log_file)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir)

            file_handler = RotatingFileHandler(
                self.log_file,
                maxBytes=self.max_bytes,
                backupCount=self.backup_count,
                encoding='utf-8',
                mode='w'
            )
            file_handler.setLevel(self.level)

            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
        except Exception as e:
            print(f"配置日志记录器失败: {e}")

    def debug(self, message: str):
        self.logger.debug(message)

    def info(self, message: str):
        self.logger.info(message)

    def warning(self, message: str):
        self.logger.warning(message)

    def error(self, message: str, exc_info: bool = False):
        if exc_info:
            self.logger.error(message, exc_info=True)
        else:
            self.logger.error(message)

    def critical(self, message: str):
        self.logger.critical(message)

    def set_level(self, level: int):
        self.logger.setLevel(level)
        for handler in self.logger.handlers:
            handler.setLevel(level)

    def get_logger(self) -> logging.Logger:
        return self.logger


global_logger = LogManager()


def get_logger(name: str = 'IPTVScanner') -> logging.Logger:
    return logging.getLogger(name)
