"""
日志记录辅助工具
提供统一的日志记录模式，消除重复的日志记录和不一致的日志级别
"""

from typing import Dict, Callable
from core.log_manager import global_logger
from utils.singleton import Singleton
import functools
import time

logger = global_logger


class LoggingHelper(Singleton):

    def __init__(self):
        if self._initialized:
            return

        self._logged_patterns: Dict[str, float] = {}
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

        self._suppression_threshold = 60

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


# 便捷函数 —— 通过工厂函数动态生成，消除重复样板代码
def _make_log_func(category: str, level: str):
    """工厂函数：生成指定类别和级别的日志函数"""
    if level == 'error':
        def _log_func(message: str, exc_info: bool = False):
            logging_helper.log_error(f'{category}_error', message, exc_info)
        return _log_func
    elif level == 'warning':
        def _log_func(message: str):
            logging_helper.log_warning(f'{category}_warning', message)
        return _log_func
    elif level == 'info':
        def _log_func(message: str):
            logging_helper.log_info(f'{category}_info', message)
        return _log_func

_categories = ['config', 'network', 'file', 'ui', 'scan', 'validation', 'player']
for _cat in _categories:
    for _lvl in ['error', 'warning', 'info']:
        _func_name = f'log_{_cat}_{_lvl}'
        globals()[_func_name] = _make_log_func(_cat, _lvl)


__all__ = [
    'logging_helper',
    'log_function_call',
    'log_class_methods',
] + [f'log_{cat}_{lvl}' for cat in _categories for lvl in ['error', 'warning', 'info']]
