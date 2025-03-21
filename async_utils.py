from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
import asyncio
from typing import Any, Optional
from utils import setup_logger

logger = setup_logger('AsyncWorker')

class AsyncWorker(QObject):
    finished = pyqtSignal(object)      # 任务完成信号
    error = pyqtSignal(Exception)      # 错误信号
    cancelled = pyqtSignal()           # 取消信号

    def __init__(self, coroutine):
        super().__init__()
        self._coroutine = coroutine    # 要运行的协程
        self._task: Optional[asyncio.Task] = None  # 异步任务对象
        self._is_running = False       # 运行状态标志
        self._is_finished = False      # 完成状态标志
        self._result = None            # 任务结果
        self._exception = None         # 任务异常

    @pyqtSlot()
    async def run(self):
        """执行异步任务"""
        if self._is_running:
            logger.warning("任务已在运行中")
            return

        self._is_running = True
        self._is_finished = False
        self._result = None
        self._exception = None

        logger.debug("开始执行异步任务")

        try:
            self._task = asyncio.create_task(self._coroutine)
            self._result = await self._task
            self.finished.emit(self._result)
        except asyncio.CancelledError:
            logger.info("任务已被取消")
            self.cancelled.emit()
        except Exception as e:
            logger.error(f"任务执行失败: {str(e)}")
            self._exception = e
            self.error.emit(e)
        finally:
            self._is_running = False
            self._is_finished = True
            logger.debug("异步任务执行完成")

    def cancel(self):
        """取消任务"""
        if self._task and not self._task.done():
            logger.info("正在取消任务...")
            self._task.cancel()
        else:
            logger.warning("无法取消未运行的任务")

    def is_running(self) -> bool:
        """返回任务是否正在运行"""
        return self._is_running

    def is_finished(self) -> bool:
        """返回任务是否已完成"""
        return self._is_finished

    def result(self) -> Any:
        """获取任务结果（如果已完成）"""
        if self._task and self._task.done():
            return self._result
        return None

    def exception(self) -> Optional[Exception]:
        """获取任务异常（如果有）"""
        if self._task and self._task.done():
            return self._exception
        return None

    def __del__(self):
        """析构时自动取消任务"""
        self.cancel()