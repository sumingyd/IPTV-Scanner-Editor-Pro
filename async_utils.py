import asyncio
from PyQt6.QtCore import QObject, pyqtSignal

class AsyncWorker(QObject):
    finished = pyqtSignal(object)  # 任务完成时发射，携带结果
    error = pyqtSignal(Exception)  # 任务出错时发射，携带异常
    cancelled = pyqtSignal()       # 任务被取消时发射

    def __init__(self, coro):
        super().__init__()
        self._coro = coro  # 确保传入的是一个协程
        self._task = None
        self._is_cancelled = False

    async def run(self):
        """执行异步任务"""
        try:
            if self._is_cancelled:
                return
            # 直接 await 协程，而不是创建任务
            result = await self._coro
            self.finished.emit(result)
        except asyncio.CancelledError:
            self.cancelled.emit()
        except Exception as e:
            self.error.emit(e)

    def cancel(self):
        """取消任务"""
        if self._task and not self._task.done():
            self._is_cancelled = True
            self._task.cancel()

    def is_finished(self) -> bool:
        """检查任务是否已完成"""
        return self._task is None or self._task.done()