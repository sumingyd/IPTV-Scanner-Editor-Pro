import asyncio
import logging
import time
from enum import Enum, auto
from PyQt6.QtCore import QObject, pyqtSignal, QThreadPool, QRunnable

class TaskState(Enum):
    PENDING = auto()
    RUNNING = auto()
    CANCELLED = auto()
    FINISHED = auto()
    FAILED = auto()

class AsyncWorker(QObject):
    _active_workers = set()  # 类变量跟踪所有活跃任务
    finished = pyqtSignal(object)  # 任务完成时发射，携带结果
    error = pyqtSignal(Exception)  # 任务出错时发射，携带异常
    cancelled = pyqtSignal()       # 任务被取消时发射
    timeout = pyqtSignal()         # 任务超时信号

    def __init__(self, coro, timeout=None):
        super().__init__()
        self._coro = coro  # 确保传入的是一个协程
        self._task = None
        self._is_cancelled = False
        self._timeout = timeout
        self._start_time = None
        self._state = TaskState.PENDING
        self.__class__._active_workers.add(self)

    def __del__(self):
        self.__class__._active_workers.discard(self)

    @classmethod
    async def cancel_all(cls, timeout=None):
        """强制取消所有任务
        Args:
            timeout: 超时时间(秒)，None表示不超时
        """
        async def _cancel_tasks():
            tasks = []
            workers = list(cls._active_workers)
            for worker in workers:
                try:
                    if worker._task and not worker._task.done():
                        tasks.append(worker._task)
                        worker._task.cancel()
                        worker._is_cancelled = True
                except Exception:
                    pass
            
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            # 确保清理所有worker引用
            for worker in workers:
                cls._active_workers.discard(worker)

        try:
            # 获取当前事件循环
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 如果已有循环运行，创建任务并等待完成
                if timeout is not None:
                    task = loop.create_task(asyncio.wait_for(_cancel_tasks(), timeout))
                else:
                    task = loop.create_task(_cancel_tasks())
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            else:
                # 没有运行中的循环，创建新循环
                if timeout is not None:
                    await asyncio.wait_for(_cancel_tasks(), timeout)
                else:
                    await _cancel_tasks()
        except asyncio.TimeoutError:
            logger = logging.getLogger('AsyncWorker')
            logger.warning("取消任务超时，强制清理")
            # 超时后确保清理所有worker
            workers = list(cls._active_workers)
            for worker in workers:
                try:
                    if worker._task and not worker._task.done():
                        worker._task.cancel()
                    cls._active_workers.discard(worker)
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"取消任务时发生错误: {str(e)}")
            raise

    async def run(self):
        """执行异步任务（修正版）"""
        try:
            # 检查事件循环状态
            loop = asyncio.get_running_loop()
            if loop.is_closed():
                raise RuntimeError("事件循环已关闭")
                
            # 检查任务状态
            if self._is_cancelled:
                self._state = TaskState.CANCELLED
                return
            
            # 确保没有其他任务正在运行
            for worker in self.__class__._active_workers:
                if worker != self and worker._state == TaskState.RUNNING:
                    await worker.cancel()
                    await asyncio.sleep(0.1)  # 给取消操作一点时间
            
            self._state = TaskState.RUNNING
            self._start_time = time.time()
            
            if self._timeout:
                result = await asyncio.wait_for(self._coro, timeout=self._timeout)
            else:
                result = await self._coro
                
            self._state = TaskState.FINISHED
            self.finished.emit(result)
            
        except asyncio.TimeoutError:
            self._state = TaskState.FAILED
            self.timeout.emit()
        except asyncio.CancelledError:
            self._state = TaskState.CANCELLED
            self.cancelled.emit()
        except Exception as e:
            self._state = TaskState.FAILED
            self.error.emit(e)

    def start(self):
        """启动异步任务"""
        if self._is_cancelled:
            return
        # 在主事件循环中创建任务
        self._task = asyncio.create_task(self.run())

    def cancel(self):
        """取消任务"""
        if self._task and not self._task.done():
            self._is_cancelled = True
            self._task.cancel()

    def is_finished(self) -> bool:
        """检查任务是否已完成"""
        return self._state in (TaskState.FINISHED, TaskState.FAILED, TaskState.CANCELLED)

    def get_state(self) -> TaskState:
        """获取任务当前状态"""
        return self._state

    def get_runtime(self) -> float:
        """获取任务运行时间(秒)"""
        if self._start_time is None:
            return 0.0
        return time.time() - self._start_time
