"""
日志记录辅助工具
提供统一的日志记录模式，消除重复的日志记录和不一致的日志级别
"""

from typing import Dict, Callable
from core.log_manager import global_logger
import functools
import time

logger = global_logger


class LoggingHelper:
    """日志记录辅助工具（单例模式）"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        # 日志模式缓存，避免重复记录相同的错误
        self._logged_patterns: Dict[str, int] = {}
        # 日志级别映射
        self._level_mapping = {
            'config_error': 'error',
            'network_error': 'error',
            'file_error': 'error',
            'ui_error': 'error',
            'scan_error': 'error',
            'validation_error': 'error',
            'player_error': 'error',
            'config_warning': 'warning',
            'network_warning': 'warning',
            'file_warning': 'warning',
            'ui_warning': 'warning',
            'scan_warning': 'warning',
            'validation_warning': 'warning',
            'player_warning': 'warning',
            'config_info': 'info',
            'network_info': 'info',
            'file_info': 'info',
            'ui_info': 'info',
            'scan_info': 'info',
            'validation_info': 'info',
            'player_info': 'info',
        }

        # 重复日志抑制阈值（秒）
        self._suppression_threshold = 60  # 60秒内不重复记录相同错误

        self._initialized = True

    def log_with_level(self, level: str, message: str, exc_info: bool = False,
                       suppress_duplicate: bool = True, **kwargs):
        """
        根据指定的级别记录日志

        Args:
            level: 日志级别 ('debug', 'info', 'warning', 'error', 'critical')
            message: 日志消息
            exc_info: 是否记录异常信息
            suppress_duplicate: 是否抑制重复日志
            **kwargs: 额外参数
        """
        if suppress_duplicate:
            # 检查是否在阈值内重复记录
            pattern_key = f"{level}:{message}"
            current_time = time.time()
            last_time = self._logged_patterns.get(pattern_key, 0)

            if current_time - last_time < self._suppression_threshold:
                return  # 抑制重复日志

            self._logged_patterns[pattern_key] = current_time

        # 根据级别记录日志
        if level == 'debug':
            logger.debug(message)
        elif level == 'info':
            logger.info(message)
        elif level == 'warning':
            logger.warning(message)
        elif level == 'error':
            logger.error(message, exc_info=exc_info)
        elif level == 'critical':
            logger.critical(message)
        else:
            logger.info(message)  # 默认使用info级别

    def log_error(self, error_type: str, message: str, exc_info: bool = False,
                  suppress_duplicate: bool = True, **kwargs):
        """
        记录错误日志，根据错误类型自动确定级别

        Args:
            error_type: 错误类型（如 'config_error', 'network_error' 等）
            message: 错误消息
            exc_info: 是否记录异常信息
            suppress_duplicate: 是否抑制重复日志
            **kwargs: 额外参数
        """
        level = self._level_mapping.get(error_type, 'error')
        self.log_with_level(level, message, exc_info, suppress_duplicate, **kwargs)

    def log_warning(self, warning_type: str, message: str,
                    suppress_duplicate: bool = True, **kwargs):
        """
        记录警告日志，根据警告类型自动确定级别

        Args:
            warning_type: 警告类型（如 'config_warning', 'network_warning' 等）
            message: 警告消息
            suppress_duplicate: 是否抑制重复日志
            **kwargs: 额外参数
        """
        level = self._level_mapping.get(warning_type, 'warning')
        self.log_with_level(level, message, suppress_duplicate=suppress_duplicate, **kwargs)

    def log_info(self, info_type: str, message: str,
                 suppress_duplicate: bool = False, **kwargs):
        """
        记录信息日志，根据信息类型自动确定级别

        Args:
            info_type: 信息类型（如 'config_info', 'network_info' 等）
            message: 信息消息
            suppress_duplicate: 是否抑制重复日志
            **kwargs: 额外参数
        """
        level = self._level_mapping.get(info_type, 'info')
        self.log_with_level(level, message, suppress_duplicate=suppress_duplicate, **kwargs)

    def clear_pattern_cache(self):
        """清空日志模式缓存"""
        self._logged_patterns.clear()

    def set_suppression_threshold(self, seconds: int):
        """设置重复日志抑制阈值（秒）"""
        self._suppression_threshold = seconds


# 全局日志辅助工具实例
logging_helper = LoggingHelper()


def log_function_call(func: Callable):
    """
    函数调用日志装饰器

    Args:
        func: 要装饰的函数
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        func_name = func.__name__
        module_name = func.__module__

        # 记录函数开始
        logging_helper.log_info('function_call', f"开始执行函数: {module_name}.{func_name}")

        try:
            start_time = time.time()
            result = func(*args, **kwargs)
            elapsed_time = time.time() - start_time

            # 记录函数成功完成
            logging_helper.log_info('function_call',
                                    f"函数执行成功: {module_name}.{func_name}, 耗时: {elapsed_time:.3f}秒")
            return result
        except Exception as e:
            # 记录函数执行失败
            error_msg = f"函数执行失败: {module_name}.{func_name}, 错误: {type(e).__name__}: {str(e)}"
            logging_helper.log_error('function_error', error_msg, exc_info=True)
            raise

    return wrapper


def log_class_methods(cls):
    """
    类方法日志装饰器（类装饰器）

    Args:
        cls: 要装饰的类
    """
    for name, method in cls.__dict__.items():
        if callable(method) and not name.startswith('_'):
            setattr(cls, name, log_function_call(method))
    return cls


# 便捷函数
def log_config_error(message: str, exc_info: bool = False):
    """记录配置错误"""
    logging_helper.log_error('config_error', message, exc_info)


def log_network_error(message: str, exc_info: bool = False):
    """记录网络错误"""
    logging_helper.log_error('network_error', message, exc_info)


def log_file_error(message: str, exc_info: bool = False):
    """记录文件错误"""
    logging_helper.log_error('file_error', message, exc_info)


def log_ui_error(message: str, exc_info: bool = False):
    """记录UI错误"""
    logging_helper.log_error('ui_error', message, exc_info)


def log_scan_error(message: str, exc_info: bool = False):
    """记录扫描错误"""
    logging_helper.log_error('scan_error', message, exc_info)


def log_validation_error(message: str, exc_info: bool = False):
    """记录验证错误"""
    logging_helper.log_error('validation_error', message, exc_info)


def log_player_error(message: str, exc_info: bool = False):
    """记录播放器错误"""
    logging_helper.log_error('player_error', message, exc_info)


def log_config_warning(message: str):
    """记录配置警告"""
    logging_helper.log_warning('config_warning', message)


def log_network_warning(message: str):
    """记录网络警告"""
    logging_helper.log_warning('network_warning', message)


def log_file_warning(message: str):
    """记录文件警告"""
    logging_helper.log_warning('file_warning', message)


def log_ui_warning(message: str):
    """记录UI警告"""
    logging_helper.log_warning('ui_warning', message)


def log_scan_warning(message: str):
    """记录扫描警告"""
    logging_helper.log_warning('scan_warning', message)


def log_validation_warning(message: str):
    """记录验证警告"""
    logging_helper.log_warning('validation_warning', message)


def log_player_warning(message: str):
    """记录播放器警告"""
    logging_helper.log_warning('player_warning', message)


def log_config_info(message: str):
    """记录配置信息"""
    logging_helper.log_info('config_info', message)


def log_network_info(message: str):
    """记录网络信息"""
    logging_helper.log_info('network_info', message)


def log_file_info(message: str):
    """记录文件信息"""
    logging_helper.log_info('file_info', message)


def log_ui_info(message: str):
    """记录UI信息"""
    logging_helper.log_info('ui_info', message)


def log_scan_info(message: str):
    """记录扫描信息"""
    logging_helper.log_info('scan_info', message)


def log_validation_info(message: str):
    """记录验证信息"""
    logging_helper.log_info('validation_info', message)


def log_player_info(message: str):
    """记录播放器信息"""
    logging_helper.log_info('player_info', message)


# 导出常用函数
__all__ = [
    'logging_helper',
    'log_function_call',
    'log_class_methods',
    'log_config_error',
    'log_network_error',
    'log_file_error',
    'log_ui_error',
    'log_scan_error',
    'log_validation_error',
    'log_player_error',
    'log_config_warning',
    'log_network_warning',
    'log_file_warning',
    'log_ui_warning',
    'log_scan_warning',
    'log_validation_warning',
    'log_player_warning',
    'log_config_info',
    'log_network_info',
    'log_file_info',
    'log_ui_info',
    'log_scan_info',
    'log_validation_info',
    'log_player_info',
]
