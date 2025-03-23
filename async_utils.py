import asyncio
from PyQt6.QtCore import QObject, pyqtSignal, QThreadPool, QRunnable

class AsyncWorker(QObject):
    _active_workers = set()  # 类变量跟踪所有活跃任务
    finished = pyqtSignal(object)  # 任务完成时发射，携带结果
    error = pyqtSignal(Exception)  # 任务出错时发射，携带异常
    cancelled = pyqtSignal()       # 任务被取消时发射

    def __init__(self, coro):
        super().__init__()
        self._coro = coro  # 确保传入的是一个协程
        self._task = None
        self._is_cancelled = False
        self.__class__._active_workers.add(self)

    def __del__(self):
        self.__class__._active_workers.discard(self)

    @classmethod
    def cancel_all(cls):
        """强制取消所有任务"""
        for worker in list(cls._active_workers):
            try:
                worker.cancel()
                if worker._task and not worker._task.done():
                    worker._task.cancel()  # 双重保障
            except Exception as e:
                pass

    async def run(self):
        """执行异步任务（修正版）"""
        try:
            if self._is_cancelled:
                return
            # 直接运行协程，不创建额外任务
            result = await self._coro
            self.finished.emit(result)
        except asyncio.CancelledError:
            self.cancelled.emit()
        except Exception as e:
            self.error.emit(e)

    def start(self):
        """启动异步任务"""
        if self._is_cancelled:
            return
        # 使用线程池运行任务
        runnable = AsyncRunnable(self)
        QThreadPool.globalInstance().start(runnable)

    def cancel(self):
        """取消任务"""
        if self._task and not self._task.done():
            self._is_cancelled = True
            self._task.cancel()

    def is_finished(self) -> bool:
        """检查任务是否已完成"""
        return self._task is None or self._task.done()


class AsyncRunnable(QRunnable):
    """用于在 QThreadPool 中运行异步任务的 Runnable"""
    def __init__(self, worker: AsyncWorker):
        super().__init__()
        self.worker = worker

    def run(self):
        """在单独的线程中运行任务"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self.worker._task = loop.create_task(self.worker.run())
        loop.run_until_complete(self.worker._task)
        loop.close()