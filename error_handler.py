"""用户友好的错误处理系统"""

from PyQt6 import QtWidgets, QtCore
from typing import Optional, Callable, Any, Dict
from log_manager import global_logger as logger


class ErrorHandler:
    """用户友好的错误处理系统"""
    
    def __init__(self, parent_window: Optional[QtWidgets.QWidget] = None):
        """初始化错误处理器"""
        self.parent_window = parent_window
        self._status_bar = None
    
    def set_status_bar(self, status_bar: QtWidgets.QStatusBar):
        """设置状态栏用于显示错误消息"""
        self._status_bar = status_bar
    
    def show_error_dialog(self, title: str, message: str, 
                         details: Optional[str] = None,
                         parent: Optional[QtWidgets.QWidget] = None):
        """显示错误对话框"""
        parent = parent or self.parent_window
        if not parent:
            logger.error(f"无法显示错误对话框，缺少父窗口: {title} - {message}")
            return
        
        try:
            # 创建错误对话框
            dialog = QtWidgets.QMessageBox(parent)
            dialog.setWindowTitle(title)
            dialog.setText(message)
            dialog.setIcon(QtWidgets.QMessageBox.Icon.Critical)
            
            # 如果有详细信息，添加详细文本
            if details:
                dialog.setDetailedText(details)
            
            # 添加标准按钮
            dialog.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Ok)
            
            # 显示对话框
            dialog.exec()
            
            logger.error(f"用户错误提示: {title} - {message}")
            if details:
                logger.debug(f"错误详情: {details}")
                
        except Exception as e:
            logger.error(f"显示错误对话框失败: {e}")
    
    def show_warning_dialog(self, title: str, message: str,
                           details: Optional[str] = None,
                           parent: Optional[QtWidgets.QWidget] = None):
        """显示警告对话框"""
        parent = parent or self.parent_window
        if not parent:
            logger.warning(f"无法显示警告对话框，缺少父窗口: {title} - {message}")
            return
        
        try:
            # 创建警告对话框
            dialog = QtWidgets.QMessageBox(parent)
            dialog.setWindowTitle(title)
            dialog.setText(message)
            dialog.setIcon(QtWidgets.QMessageBox.Icon.Warning)
            
            # 如果有详细信息，添加详细文本
            if details:
                dialog.setDetailedText(details)
            
            # 添加标准按钮
            dialog.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Ok)
            
            # 显示对话框
            dialog.exec()
            
            logger.warning(f"用户警告提示: {title} - {message}")
            if details:
                logger.debug(f"警告详情: {details}")
                
        except Exception as e:
            logger.error(f"显示警告对话框失败: {e}")
    
    def show_info_dialog(self, title: str, message: str,
                        details: Optional[str] = None,
                        parent: Optional[QtWidgets.QWidget] = None):
        """显示信息对话框"""
        parent = parent or self.parent_window
        if not parent:
            logger.info(f"无法显示信息对话框，缺少父窗口: {title} - {message}")
            return
        
        try:
            # 创建信息对话框
            dialog = QtWidgets.QMessageBox(parent)
            dialog.setWindowTitle(title)
            dialog.setText(message)
            dialog.setIcon(QtWidgets.QMessageBox.Icon.Information)
            
            # 如果有详细信息，添加详细文本
            if details:
                dialog.setDetailedText(details)
            
            # 添加标准按钮
            dialog.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Ok)
            
            # 显示对话框
            dialog.exec()
            
            logger.info(f"用户信息提示: {title} - {message}")
            if details:
                logger.debug(f"信息详情: {details}")
                
        except Exception as e:
            logger.error(f"显示信息对话框失败: {e}")
    
    def show_status_message(self, message: str, timeout: int = 3000):
        """在状态栏显示消息"""
        if self._status_bar:
            try:
                self._status_bar.showMessage(message, timeout)
                logger.debug(f"状态栏消息: {message}")
            except Exception as e:
                logger.error(f"显示状态栏消息失败: {e}")
        else:
            logger.debug(f"状态栏消息（无状态栏）: {message}")
    
    def handle_exception(self, exception: Exception, 
                        user_message: Optional[str] = None,
                        show_dialog: bool = True,
                        log_level: str = 'error',
                        context: Optional[Dict[str, Any]] = None):
        """处理异常 - 增强版本"""
        # 构建详细的错误信息
        error_info = self._build_error_info(exception, user_message, context)
        
        # 记录异常
        if log_level == 'error':
            logger.error(error_info['log_message'], exc_info=True)
        elif log_level == 'warning':
            logger.warning(error_info['log_message'], exc_info=True)
        else:
            logger.info(error_info['log_message'], exc_info=True)
        
        # 显示错误对话框
        if show_dialog and self.parent_window:
            self.show_error_dialog(
                title=error_info['title'],
                message=error_info['user_message'],
                details=error_info['details']
            )
        
        # 在状态栏显示消息
        self.show_status_message(error_info['status_message'])
        
        return error_info
    
    def _build_error_info(self, exception: Exception, user_message: Optional[str], context: Optional[Dict]) -> Dict[str, str]:
        """构建详细的错误信息"""
        import traceback
        import sys
        
        # 获取异常类型和消息
        exception_type = type(exception).__name__
        exception_message = str(exception)
        
        # 构建用户友好的消息
        if user_message:
            user_friendly_message = user_message
        else:
            user_friendly_message = self._get_user_friendly_message(exception)
        
        # 构建详细错误信息
        details_parts = []
        details_parts.append(f"异常类型: {exception_type}")
        details_parts.append(f"异常消息: {exception_message}")
        
        # 添加堆栈跟踪
        tb_lines = traceback.format_exception(type(exception), exception, exception.__traceback__)
        details_parts.append("堆栈跟踪:")
        details_parts.extend(tb_lines)
        
        # 添加上下文信息
        if context:
            details_parts.append("上下文信息:")
            for key, value in context.items():
                details_parts.append(f"  {key}: {value}")
        
        # 确定错误级别和标题
        if isinstance(exception, (KeyboardInterrupt, SystemExit)):
            log_level = 'info'
            title = "操作中断"
        elif isinstance(exception, (ValueError, TypeError, AttributeError)):
            log_level = 'warning'
            title = "输入错误"
        elif isinstance(exception, (FileNotFoundError, PermissionError)):
            log_level = 'warning'
            title = "文件操作错误"
        elif isinstance(exception, (ConnectionError, TimeoutError)):
            log_level = 'warning'
            title = "网络连接错误"
        else:
            log_level = 'error'
            title = "系统错误"
        
        return {
            'title': title,
            'user_message': user_friendly_message,
            'status_message': f"{title}: {user_friendly_message}",
            'log_message': f"{user_friendly_message} [{exception_type}: {exception_message}]",
            'details': '\n'.join(details_parts),
            'log_level': log_level,
            'exception_type': exception_type
        }
    
    def _get_user_friendly_message(self, exception: Exception) -> str:
        """获取用户友好的错误消息"""
        exception_type = type(exception)
        exception_message = str(exception)
        
        # 根据异常类型提供友好的错误消息
        if exception_type == FileNotFoundError:
            return f"文件未找到: {exception_message}"
        elif exception_type == PermissionError:
            return f"没有权限访问文件: {exception_message}"
        elif exception_type == ConnectionError:
            return f"网络连接失败: {exception_message}"
        elif exception_type == TimeoutError:
            return f"操作超时: {exception_message}"
        elif exception_type == ValueError:
            return f"输入值无效: {exception_message}"
        elif exception_type == TypeError:
            return f"类型错误: {exception_message}"
        elif exception_type == AttributeError:
            return f"对象属性错误: {exception_message}"
        elif exception_type == KeyboardInterrupt:
            return "操作被用户中断"
        elif exception_type == SystemExit:
            return "程序正在退出"
        else:
            return f"发生未知错误: {exception_message}"
    
    def safe_execute(self, func: Callable, *args, 
                    user_message: Optional[str] = None,
                    show_dialog: bool = True,
                    default_return: Any = None,
                    **kwargs) -> Any:
        """安全执行函数，自动处理异常"""
        try:
            return func(*args, **kwargs)
        except Exception as e:
            self.handle_exception(
                exception=e,
                user_message=user_message or f"执行 {func.__name__} 失败",
                show_dialog=show_dialog
            )
            return default_return


# 全局错误处理器实例
_global_error_handler: Optional[ErrorHandler] = None


def init_global_error_handler(parent_window: QtWidgets.QWidget) -> ErrorHandler:
    """初始化全局错误处理器"""
    global _global_error_handler
    _global_error_handler = ErrorHandler(parent_window)
    return _global_error_handler


def get_global_error_handler() -> ErrorHandler:
    """获取全局错误处理器"""
    global _global_error_handler
    if _global_error_handler is None:
        raise RuntimeError("全局错误处理器未初始化，请先调用 init_global_error_handler")
    return _global_error_handler


def safe_execute_global(func: Callable, *args, **kwargs) -> Any:
    """使用全局错误处理器安全执行函数"""
    try:
        handler = get_global_error_handler()
        return handler.safe_execute(func, *args, **kwargs)
    except RuntimeError:
        # 如果全局错误处理器未初始化，直接执行函数
        logger.warning("全局错误处理器未初始化，直接执行函数")
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"函数执行失败: {e}", exc_info=True)
            return None


# ============================================================================
# 便捷工具函数
# ============================================================================

def show_error(title: str, message: str, parent: Optional[QtWidgets.QWidget] = None):
    """显示错误对话框的便捷函数"""
    try:
        # 首先尝试使用全局错误处理器
        handler = get_global_error_handler()
        handler.show_error_dialog(title, message, parent=parent)
    except RuntimeError:
        # 如果全局错误处理器未初始化，尝试从父窗口获取
        if parent and hasattr(parent, 'error_handler') and parent.error_handler:
            parent.error_handler.show_error_dialog(title, message, parent=parent)
        else:
            # 最后回退到QMessageBox
            QtWidgets.QMessageBox.critical(parent, title, message)


def show_warning(title: str, message: str, parent: Optional[QtWidgets.QWidget] = None):
    """显示警告对话框的便捷函数"""
    try:
        # 首先尝试使用全局错误处理器
        handler = get_global_error_handler()
        handler.show_warning_dialog(title, message, parent=parent)
    except RuntimeError:
        # 如果全局错误处理器未初始化，尝试从父窗口获取
        if parent and hasattr(parent, 'error_handler') and parent.error_handler:
            parent.error_handler.show_warning_dialog(title, message, parent=parent)
        else:
            # 最后回退到QMessageBox
            QtWidgets.QMessageBox.warning(parent, title, message)


def show_info(title: str, message: str, parent: Optional[QtWidgets.QWidget] = None):
    """显示信息对话框的便捷函数"""
    try:
        # 首先尝试使用全局错误处理器
        handler = get_global_error_handler()
        handler.show_info_dialog(title, message, parent=parent)
    except RuntimeError:
        # 如果全局错误处理器未初始化，尝试从父窗口获取
        if parent and hasattr(parent, 'error_handler') and parent.error_handler:
            parent.error_handler.show_info_dialog(title, message, parent=parent)
        else:
            # 最后回退到QMessageBox
            QtWidgets.QMessageBox.information(parent, title, message)


def show_confirm(title: str, message: str, parent: Optional[QtWidgets.QWidget] = None) -> bool:
    """显示确认对话框"""
    reply = QtWidgets.QMessageBox.question(
        parent,
        title,
        message,
        QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
    )
    return reply == QtWidgets.QMessageBox.StandardButton.Yes


def show_error_with_details(title: str, message: str, details: str, parent: Optional[QtWidgets.QWidget] = None):
    """显示带详细信息的错误对话框"""
    try:
        # 首先尝试使用全局错误处理器
        handler = get_global_error_handler()
        handler.show_error_dialog(title, message, details=details, parent=parent)
    except RuntimeError:
        # 如果全局错误处理器未初始化，尝试从父窗口获取
        if parent and hasattr(parent, 'error_handler') and parent.error_handler:
            parent.error_handler.show_error_dialog(title, message, details=details, parent=parent)
        else:
            # 最后回退到QMessageBox
            dialog = QtWidgets.QMessageBox(parent)
            dialog.setWindowTitle(title)
            dialog.setText(message)
            dialog.setIcon(QtWidgets.QMessageBox.Icon.Critical)
            dialog.setDetailedText(details)
            dialog.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Ok)
            dialog.exec()
