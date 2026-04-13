import threading
from PyQt6.QtCore import QThread, QTimer, QObject


class ThreadSafeQObject(QObject):
    """线程安全的 Qt 对象基类，确保所有公共方法都在主线程中执行"""

    def _ensure_main_thread(self, func, *args, **kwargs):
        """确保方法在主线程中执行，如果不是则转发到主线程"""
        if QThread.currentThread() != self.thread():
            QTimer.singleShot(0, lambda: func(*args, **kwargs))
            return False
        return True


def run_on_main_thread(owner_obj, func, *args, **kwargs):
    """通用工具函数：确保函数在 owner_obj 所在线程中执行

    Args:
        owner_obj: Qt 对象，用于判断目标线程
        func: 要执行的函数
        *args, **kwargs: 函数参数

    Returns:
        bool: 如果当前就在目标线程返回 True，否则返回 False（已转发）
    """
    if QThread.currentThread() != owner_obj.thread():
        QTimer.singleShot(0, lambda: func(*args, **kwargs))
        return False
    return True
