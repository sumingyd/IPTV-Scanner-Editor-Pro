"""公共工具模块，包含重复使用的功能"""

import os
import sys
import logging
from typing import Optional, Callable, Any
from functools import wraps

def get_resource_path(relative_path: str) -> str:
    """获取资源文件的绝对路径
    
    Args:
        relative_path: 相对于程序目录的相对路径
        
    Returns:
        资源文件的绝对路径
    """
    if getattr(sys, 'frozen', False):
        # 打包成exe的情况
        base_path = os.path.dirname(sys.executable)
    else:
        # 开发环境
        base_path = os.path.dirname(__file__)
    
    return os.path.join(base_path, relative_path)

def safe_execute(func, default_return=None, *args, **kwargs):
    """安全执行函数，捕获异常并返回默认值
    
    Args:
        func: 要执行的函数
        default_return: 异常时的默认返回值
        *args, **kwargs: 函数参数
        
    Returns:
        函数执行结果或默认值
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        logger = logging.getLogger('utils')
        logger.error(f"函数 {func.__name__} 执行失败: {e}")
        return default_return

def exception_handler(logger_name: str = 'default', default_return=None):
    """异常处理装饰器，减少重复的try/except代码
    
    Args:
        logger_name: 日志记录器名称
        default_return: 异常时的默认返回值
        
    Returns:
        装饰器函数
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger = logging.getLogger(logger_name)
                logger.error(f"函数 {func.__name__} 执行失败: {e}", exc_info=True)
                return default_return
        return wrapper
    return decorator

def ui_exception_handler(logger_name: str = 'ui', show_message: bool = True):
    """UI异常处理装饰器，专门用于UI操作
    
    Args:
        logger_name: 日志记录器名称
        show_message: 是否显示错误消息
        
    Returns:
        装饰器函数
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger = logging.getLogger(logger_name)
                logger.error(f"UI操作 {func.__name__} 执行失败: {e}", exc_info=True)
                
                # 如果函数有self参数且show_message为True，尝试显示错误消息
                if show_message and args and hasattr(args[0], 'ui'):
                    try:
                        main_window = args[0].ui.main_window if hasattr(args[0].ui, 'main_window') else args[0]
                        if hasattr(main_window, 'statusBar'):
                            main_window.statusBar().showMessage(f"操作失败: {str(e)}", 3000)
                    except:
                        pass
                return None
        return wrapper
    return decorator

def is_valid_url(url: str) -> bool:
    """检查URL是否有效
    
    Args:
        url: 要检查的URL
        
    Returns:
        URL是否有效
    """
    if not url or not isinstance(url, str):
        return False
    
    # 基本URL格式检查
    url = url.strip()
    if not url:
        return False
    
    # 检查常见协议
    valid_schemes = ('http://', 'https://', 'rtp://', 'udp://', 'rtsp://', 'file://')
    return any(url.startswith(scheme) for scheme in valid_schemes)

def format_file_size(size_bytes: int) -> str:
    """格式化文件大小
    
    Args:
        size_bytes: 文件大小（字节）
        
    Returns:
        格式化后的文件大小字符串
    """
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.2f} {size_names[i]}"

def truncate_text(text: str, max_length: int = 50, suffix: str = "...") -> str:
    """截断文本，超过最大长度时添加后缀
    
    Args:
        text: 要截断的文本
        max_length: 最大长度
        suffix: 后缀字符串
        
    Returns:
        截断后的文本
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix
