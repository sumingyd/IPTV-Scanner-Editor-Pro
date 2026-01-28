"""用户友好的错误处理系统"""

from PyQt6 import QtWidgets
from typing import Optional, Callable, Any, Dict
from core.log_manager import global_logger as logger


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

    def _build_error_info(self, exception: Exception,
                          user_message: Optional[str],
                          context: Optional[Dict]) -> Dict[str, str]:
        """构建详细的错误信息"""
        import traceback

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


# ============================================================================
# 异常处理装饰器
# ============================================================================

def handle_exceptions(
    user_message: Optional[str] = None,
    show_dialog: bool = True,
    default_return: Any = None,
    log_level: str = 'error'
):
    """
    异常处理装饰器，用于自动处理函数中的异常

    参数:
        user_message: 用户友好的错误消息
        show_dialog: 是否显示错误对话框
        default_return: 异常发生时的默认返回值
        log_level: 日志级别 ('error', 'warning', 'info')

    使用示例:
        @handle_exceptions(user_message="加载文件失败", default_return=[])
        def load_file(file_path):
            # 可能会抛出异常的函数
            with open(file_path, 'r') as f:
                return f.read()
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # 获取错误处理器
                try:
                    handler = get_global_error_handler()
                except RuntimeError:
                    # 如果没有全局错误处理器，使用默认日志记录
                    logger = getattr(func, '__logger__', None)
                    if not logger:
                        from core.log_manager import global_logger
                        logger = global_logger

                    # 构建错误消息
                    error_msg = user_message or f"执行 {func.__name__} 失败"
                    full_msg = f"{error_msg}: {type(e).__name__}: {str(e)}"

                    # 记录日志
                    if log_level == 'error':
                        logger.error(full_msg, exc_info=True)
                    elif log_level == 'warning':
                        logger.warning(full_msg, exc_info=True)
                    else:
                        logger.info(full_msg, exc_info=True)

                    return default_return

                # 使用错误处理器处理异常
                handler.handle_exception(
                    exception=e,
                    user_message=user_message or f"执行 {func.__name__} 失败",
                    show_dialog=show_dialog,
                    log_level=log_level
                )
                return default_return

        # 复制原始函数的元数据
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        wrapper.__module__ = func.__module__

        return wrapper
    return decorator


def handle_specific_exceptions(
    exceptions: tuple,
    user_message: Optional[str] = None,
    show_dialog: bool = True,
    default_return: Any = None,
    log_level: str = 'error'
):
    """
    处理特定异常的装饰器

    参数:
        exceptions: 要处理的异常类型元组
        user_message: 用户友好的错误消息
        show_dialog: 是否显示错误对话框
        default_return: 异常发生时的默认返回值
        log_level: 日志级别

    使用示例:
        @handle_specific_exceptions(
            exceptions=(FileNotFoundError, PermissionError),
            user_message="文件操作失败",
            default_return=None
        )
        def open_file(file_path):
            return open(file_path, 'r')
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except exceptions as e:
                # 获取错误处理器
                try:
                    handler = get_global_error_handler()
                except RuntimeError:
                    # 如果没有全局错误处理器，使用默认日志记录
                    logger = getattr(func, '__logger__', None)
                    if not logger:
                        from core.log_manager import global_logger
                        logger = global_logger

                    # 构建错误消息
                    error_msg = user_message or f"执行 {func.__name__} 失败"
                    full_msg = f"{error_msg}: {type(e).__name__}: {str(e)}"

                    # 记录日志
                    if log_level == 'error':
                        logger.error(full_msg, exc_info=True)
                    elif log_level == 'warning':
                        logger.warning(full_msg, exc_info=True)
                    else:
                        logger.info(full_msg, exc_info=True)

                    return default_return

                # 使用错误处理器处理异常
                handler.handle_exception(
                    exception=e,
                    user_message=user_message or f"执行 {func.__name__} 失败",
                    show_dialog=show_dialog,
                    log_level=log_level
                )
                return default_return
            except Exception:
                # 其他异常重新抛出
                raise

        # 复制原始函数的元数据
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        wrapper.__module__ = func.__module__

        return wrapper
    return decorator


def retry_on_exception(
    max_retries: int = 3,
    delay: float = 1.0,
    exceptions: tuple = (Exception,),
    user_message: Optional[str] = None,
    show_dialog: bool = False
):
    """
    异常重试装饰器

    参数:
        max_retries: 最大重试次数
        delay: 重试延迟（秒）
        exceptions: 触发重试的异常类型
        user_message: 用户友好的错误消息
        show_dialog: 是否显示错误对话框

    使用示例:
        @retry_on_exception(max_retries=3, delay=2.0)
        def download_file(url):
            # 可能会失败的下载操作
            return requests.get(url).content
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            import time

            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    # 如果是最后一次尝试，处理异常
                    if attempt == max_retries - 1:
                        try:
                            handler = get_global_error_handler()
                            handler.handle_exception(
                                exception=e,
                                user_message=user_message or f"执行 {func.__name__} 失败（重试 {max_retries} 次后）",
                                show_dialog=show_dialog
                            )
                        except RuntimeError:
                            # 如果没有全局错误处理器，记录日志
                            from core.log_manager import global_logger
                            logger = global_logger
                            error_msg = user_message or f"执行 {func.__name__} 失败（重试 {max_retries} 次后）"
                            logger.error(f"{error_msg}: {type(e).__name__}: {str(e)}", exc_info=True)

                        raise

                    # 记录重试信息
                    try:
                        handler = get_global_error_handler()
                        handler.show_status_message(f"重试 {func.__name__}... (第 {attempt + 1} 次)")
                    except RuntimeError:
                        pass

                    # 等待后重试
                    time.sleep(delay)

            # 理论上不会执行到这里
            raise RuntimeError(f"函数 {func.__name__} 重试 {max_retries} 次后仍然失败")

        # 复制原始函数的元数据
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        wrapper.__module__ = func.__module__

        return wrapper
    return decorator


def log_execution_time(func):
    """
    记录函数执行时间的装饰器

    使用示例:
        @log_execution_time
        def process_data(data):
            # 耗时操作
            time.sleep(2)
            return processed_data
    """
    def wrapper(*args, **kwargs):
        import time
        from core.log_manager import global_logger

        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            elapsed_time = time.time() - start_time
            global_logger.debug(f"函数 {func.__name__} 执行时间: {elapsed_time:.3f} 秒")
            return result
        except Exception:
            elapsed_time = time.time() - start_time
            global_logger.error(f"函数 {func.__name__} 执行失败，耗时: {elapsed_time:.3f} 秒")
            raise

    # 复制原始函数的元数据
    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    wrapper.__module__ = func.__module__

    return wrapper
