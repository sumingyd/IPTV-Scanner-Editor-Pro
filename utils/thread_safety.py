from concurrent.futures import Future
from PySide6.QtCore import QThread, QTimer, QObject, Signal, Qt, Slot


class _CallbackRelay(QObject):
    """跨线程回调中继器 - 使用信号-槽机制确保回调在目标线程执行

    PySide6 中 QTimer.singleShot(0, callback) 从非主线程调用不会生效，
    需要使用信号-槽的 QueuedConnection 来实现跨线程调用。
    """
    _callback_signal = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._callback_signal.connect(self._invoke, Qt.ConnectionType.QueuedConnection)

    def invoke(self, callback):
        self._callback_signal.emit(callback)

    @Slot(object)
    def _invoke(self, callback):
        try:
            callback()
        except Exception:
            pass


_relay_instances = {}


def _get_relay_for_thread(owner_obj):
    """获取或创建与 owner_obj 关联的回调中继器"""
    owner_id = id(owner_obj)
    if owner_id not in _relay_instances:
        relay = _CallbackRelay()
        relay.moveToThread(owner_obj.thread())
        _relay_instances[owner_id] = relay
    return _relay_instances[owner_id]


def invoke_on_thread(owner_obj, callback):
    """线程安全地调用回调函数，确保在 owner_obj 所在线程执行

    替代 QTimer.singleShot(0, callback) 的跨线程调用方式。
    在 PySide6 中，QTimer.singleShot 从非主线程调用不生效，
    此函数使用信号-槽机制确保回调正确投递到目标线程。

    Args:
        owner_obj: Qt 对象，用于确定目标线程
        callback: 要在目标线程执行的回调函数
    """
    if QThread.currentThread() == owner_obj.thread():
        callback()
    else:
        relay = _get_relay_for_thread(owner_obj)
        relay.invoke(callback)


class ThreadSafeQObject(QObject):
    """线程安全的 Qt 对象基类，确保所有公共方法都在主线程中执行"""

    def _ensure_main_thread(self, func, *args, **kwargs):
        """确保方法在主线程中执行，如果不是则转发到主线程

        返回值:
            True  - 当前已在主线程，调用者应继续执行后续逻辑
            False - 已转发到主线程，调用者应立即 return，不可继续执行

        警告: 忽略返回值继续执行会导致逻辑在错误的线程上运行！
        典型用法:
            if not self._ensure_main_thread(self._some_method, *args):
                return
        """
        if QThread.currentThread() != self.thread():
            invoke_on_thread(self, lambda: func(*args, **kwargs))
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
            invoke_on_thread(self, wrapper)
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
        invoke_on_thread(owner_obj, lambda: func(*args, **kwargs))
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
    """
    future = Future()

    def wrapper():
        try:
            result = func(*args, **kwargs)
            future.set_result(result)
        except Exception as e:
            future.set_exception(e)

    if QThread.currentThread() != owner_obj.thread():
        invoke_on_thread(owner_obj, wrapper)
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
