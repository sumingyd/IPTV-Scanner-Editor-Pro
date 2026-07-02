import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from utils.singleton import Singleton
from utils.platform_utils import get_android_data_dir


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
        # Android Chaquopy 环境：优先使用 IPTV_DATA_DIR（已指向 ISEPP 目录）
        android_data = get_android_data_dir()
        if android_data:
            return os.path.join(android_data, log_file)
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

            # 每次启动时清除旧日志文件，确保非追加模式。
            # RotatingFileHandler 在 Python 3.9+ 强制 delay=True，mode='w' 可能不按预期截断
            # （首次 emit 时 shouldRollover → _open 用 mode='w'，但某些环境下仍追加），
            # 手动删除旧文件是最可靠的非追加方案。
            if os.path.exists(self.log_file):
                try:
                    os.remove(self.log_file)
                except Exception:
                    pass
            # 清除轮转备份文件
            for i in range(1, self.backup_count + 1):
                backup_file = f"{self.log_file}.{i}"
                if os.path.exists(backup_file):
                    try:
                        os.remove(backup_file)
                    except Exception:
                        pass

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
