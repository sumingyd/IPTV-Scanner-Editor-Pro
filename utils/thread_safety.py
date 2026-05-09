import threading
from concurrent.futures import Future
from PyQt6.QtCore import QThread, QTimer, QObject


class ThreadSafeQObject(QObject):
    """线程安全的 Qt 对象基类，确保所有公共方法都在主线程中执行"""

    def _ensure_main_thread(self, func, *args, **kwargs):
        """确保方法在主线程中执行，如果不是则转发到主线程"""
        if QThread.currentThread() != self.thread():
            QTimer.singleShot(0, lambda: func(*args, **kwargs))
            return False
        return True

    def _run_on_main_thread_async(self, func, *args, **kwargs) -> Future:
        """在线程安全的方式下执行函数，并返回Future对象以获取结果
        
        Args:
            func: 要执行的函数
            *args, **kwargs: 函数参数
            
        Returns:
            Future: 可以用来获取执行结果或异常的Future对象
        """
        future = Future()
        
        def wrapper():
            try:
                result = func(*args, **kwargs)
                future.set_result(result)
            except Exception as e:
                future.set_exception(e)
        
        if QThread.currentThread() != self.thread():
            QTimer.singleShot(0, wrapper)
        else:
            wrapper()
            
        return future


def run_on_main_thread(owner_obj, func, *args, **kwargs):
    """通用工具函数：确保函数在 owner_obj 所在线程中执行（无返回值版本）

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


def run_on_main_thread_async(owner_obj, func, *args, **kwargs) -> Future:
    """通用工具函数：确保函数在 owner_obj 所在线程中执行（带返回值版本）
    
    这个版本的函数返回一个Future对象，可以用来：
    - 获取函数的返回值
    - 捕获执行过程中的异常
    - 添加完成回调
    
    Args:
        owner_obj: Qt 对象，用于判断目标线程
        func: 要执行的函数
        *args, **kwargs: 函数参数
        
    Returns:
        Future: 可以用来获取执行结果或异常的Future对象
        
    使用示例:
        >>> future = run_on_main_thread_async(main_window, some_function, arg1, arg2)
        >>> result = future.result(timeout=5.0)  # 阻塞等待结果
        >>> 
        >>> # 或者使用回调方式
        >>> def on_done(future):
        ...     try:
        ...         result = future.result()
        ...         print(f"成功: {result}")
        ...     except Exception as e:
        ...         print(f"失败: {e}")
        >>> future.add_done_callback(on_done)
    """
    future = Future()
    
    def wrapper():
        try:
            result = func(*args, **kwargs)
            future.set_result(result)
        except Exception as e:
            future.set_exception(e)
    
    if QThread.currentThread() != owner_obj.thread():
        QTimer.singleShot(0, wrapper)
    else:
        wrapper()
    
    return future


class MainThreadExecutor:
    """主线程执行器 - 用于在主线程中执行任务并获取结果"""

    @staticmethod
    def submit(owner_obj, func, *args, **kwargs) -> Future:
        """提交任务到主线程执行"""
        return run_on_main_thread_async(owner_obj, func, *args, **kwargs)


main_thread_executor = MainThreadExecutor()
