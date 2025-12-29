"""
统一的进度条管理器
提供统一的进度条管理接口，消除重复的进度条处理逻辑
"""

from PyQt6 import QtWidgets, QtCore
from typing import Optional, Callable
from core.log_manager import global_logger

logger = global_logger


class ProgressManager:
    """统一的进度条管理器"""

    _instance: Optional['ProgressManager'] = None

    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """初始化进度条管理器"""
        if self._initialized:
            return

        self._progress_bar: Optional[QtWidgets.QProgressBar] = None
        self._status_bar: Optional[QtWidgets.QStatusBar] = None
        self._progress_timer: Optional[QtCore.QTimer] = None
        self._current_task: Optional[str] = None
        self._progress_callbacks = {}
        self._initialized = True

        logger.info("进度条管理器已初始化")

    def set_progress_bar(self, progress_bar: QtWidgets.QProgressBar):
        """设置进度条控件"""
        self._progress_bar = progress_bar
        if self._progress_bar:
            self._progress_bar.setRange(0, 100)
            self._progress_bar.setValue(0)
            self._progress_bar.setTextVisible(True)
            self._progress_bar.setFormat("%p%")
            self._progress_bar.hide()
            logger.debug("进度条控件已设置")

    def set_status_bar(self, status_bar: QtWidgets.QStatusBar):
        """设置状态栏"""
        self._status_bar = status_bar
        logger.debug("状态栏已设置")

    def start_progress(self, task_name: str, max_value: int = 100):
        """开始进度显示

        Args:
            task_name: 任务名称
            max_value: 最大值，默认为100
        """
        if not self._progress_bar:
            logger.warning("进度条未设置，无法开始进度显示")
            return

        self._current_task = task_name
        self._progress_bar.setRange(0, max_value)
        self._progress_bar.setValue(0)
        self._progress_bar.show()

        if self._status_bar:
            self._status_bar.showMessage(f"开始{task_name}...", 3000)

        logger.info(f"开始进度显示: {task_name}")

    def update_progress(self, value: int, message: Optional[str] = None):
        """更新进度值

        Args:
            value: 进度值
            message: 可选的状态消息
        """
        if not self._progress_bar:
            return

        old_value = self._progress_bar.value()
        if old_value != value:
            self._progress_bar.setValue(value)

            if message and self._status_bar:
                self._status_bar.showMessage(message, 1000)

    def update_progress_from_stats(self, current: int, total: int, message: Optional[str] = None):
        """从统计信息更新进度

        Args:
            current: 当前进度
            total: 总进度
            message: 可选的状态消息
        """
        if not self._progress_bar or total <= 0:
            return

        progress_value = int(current / total * 100)
        progress_value = max(0, min(100, progress_value))

        # 如果进度条不可见且总数大于0，显示进度条
        if not self._progress_bar.isVisible() and total > 0:
            self._progress_bar.show()

        self.update_progress(progress_value, message)

    def hide_progress(self):
        """隐藏进度条"""
        if self._progress_bar:
            self._progress_bar.hide()
            self._progress_bar.setValue(0)

        self._current_task = None

        if self._progress_timer and self._progress_timer.isActive():
            self._progress_timer.stop()

    def complete_progress(self, message: Optional[str] = None):
        """完成进度显示

        Args:
            message: 完成消息
        """
        if self._progress_bar:
            self._progress_bar.setValue(self._progress_bar.maximum())

            # 延迟隐藏进度条，让用户看到完成状态
            QtCore.QTimer.singleShot(500, self.hide_progress)

        if message and self._status_bar:
            self._status_bar.showMessage(message, 3000)

        if self._current_task:
            logger.info(f"进度完成: {self._current_task}")
            self._current_task = None

    def start_auto_update(self, update_callback: Callable, interval: int = 500):
        """启动自动更新进度

        Args:
            update_callback: 更新回调函数
            interval: 更新间隔（毫秒）
        """
        if self._progress_timer and self._progress_timer.isActive():
            self._progress_timer.stop()

        self._progress_timer = QtCore.QTimer()
        self._progress_timer.timeout.connect(update_callback)
        self._progress_timer.start(interval)

        logger.debug(f"启动自动进度更新，间隔: {interval}ms")

    def stop_auto_update(self):
        """停止自动更新进度"""
        if self._progress_timer and self._progress_timer.isActive():
            self._progress_timer.stop()
            logger.debug("停止自动进度更新")

    def register_progress_callback(self, task_type: str, callback: Callable):
        """注册进度回调函数

        Args:
            task_type: 任务类型（如'scan', 'refresh'等）
            callback: 回调函数
        """
        self._progress_callbacks[task_type] = callback
        logger.debug(f"注册进度回调: {task_type}")

    def get_progress_callback(self, task_type: str) -> Optional[Callable]:
        """获取进度回调函数

        Args:
            task_type: 任务类型

        Returns:
            回调函数或None
        """
        return self._progress_callbacks.get(task_type)

    def is_progress_visible(self) -> bool:
        """检查进度条是否可见"""
        return self._progress_bar.isVisible() if self._progress_bar else False

    def get_current_task(self) -> Optional[str]:
        """获取当前任务名称"""
        return self._current_task


# 全局进度条管理器实例
_global_progress_manager: Optional[ProgressManager] = None


def get_progress_manager() -> ProgressManager:
    """获取全局进度条管理器"""
    global _global_progress_manager
    if _global_progress_manager is None:
        _global_progress_manager = ProgressManager()
    return _global_progress_manager


def init_progress_manager(
    progress_bar: QtWidgets.QProgressBar,
    status_bar: Optional[QtWidgets.QStatusBar] = None
) -> ProgressManager:
    """初始化进度条管理器

    Args:
        progress_bar: 进度条控件
        status_bar: 状态栏控件

    Returns:
        进度条管理器实例
    """
    manager = get_progress_manager()
    manager.set_progress_bar(progress_bar)
    if status_bar:
        manager.set_status_bar(status_bar)
    return manager


# 便捷装饰器
def with_progress(task_name: str, max_value: int = 100):
    """带进度显示的装饰器

    Args:
        task_name: 任务名称
        max_value: 最大值

    Returns:
        装饰器函数
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            manager = get_progress_manager()
            manager.start_progress(task_name, max_value)

            try:
                result = func(*args, **kwargs)
                manager.complete_progress(f"{task_name}完成")
                return result
            except Exception as e:
                manager.hide_progress()
                logger.error(f"{task_name}失败: {e}")
                raise

        return wrapper
    return decorator
