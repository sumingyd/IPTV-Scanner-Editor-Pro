"""全局资源清理器"""

import gc
import threading
from typing import List, Callable, Optional, Dict
from core.log_manager import global_logger
from utils.singleton import Singleton

logger = global_logger


class ResourceCleaner(Singleton):

    def __init__(self):
        if self._initialized:
            return

        # 统一用强引用列表存储 handler，名称→handler 的映射用普通字典
        self._cleanup_handlers: List[Callable] = []
        self._handler_names: Dict[str, Callable] = {}
        self._lock = threading.Lock()
        self._initialized = True

    def register_cleanup_handler(self, handler: Callable, name: Optional[str] = None):
        """注册清理处理器"""
        with self._lock:
            if handler not in self._cleanup_handlers:
                self._cleanup_handlers.append(handler)
            if name:
                self._handler_names[name] = handler

    def unregister_cleanup_handler(self, handler: Callable):
        """注销清理处理器"""
        with self._lock:
            if handler in self._cleanup_handlers:
                self._cleanup_handlers.remove(handler)
            # 从名称映射中移除
            to_remove = [n for n, h in self._handler_names.items() if h is handler]
            for n in to_remove:
                del self._handler_names[n]

    def cleanup_all(self):
        """执行所有清理操作"""
        logger.info("开始全局资源清理...")

        with self._lock:
            handlers_to_execute = self._cleanup_handlers.copy()
            # 构建反向映射用于日志
            name_map = {id(h): n for n, h in self._handler_names.items()}

        success_count = 0
        error_count = 0

        for handler in handlers_to_execute:
            handler_name = name_map.get(id(handler), getattr(handler, '__name__', repr(handler)))
            try:
                handler()
                success_count += 1
            except Exception as e:
                error_count += 1
                logger.error(f"清理处理器执行失败 {handler_name}: {e}")

        gc.collect()

        logger.info(f"全局资源清理完成: {success_count} 个处理器成功, {error_count} 个处理器失败")

    def get_handler_count(self) -> int:
        """获取注册的处理器数量"""
        with self._lock:
            return len(self._cleanup_handlers)

    def clear_all_handlers(self):
        """清除所有清理处理器"""
        with self._lock:
            handler_count = len(self._cleanup_handlers)
            self._cleanup_handlers.clear()
            self._handler_names.clear()
            logger.info(f"已清除所有清理处理器，共 {handler_count} 个")


def get_resource_cleaner() -> ResourceCleaner:
    """获取全局资源清理器"""
    return ResourceCleaner()


def register_cleanup(handler: Callable, name: Optional[str] = None):
    """注册清理函数（便捷函数）"""
    cleaner = get_resource_cleaner()
    cleaner.register_cleanup_handler(handler, name)


def unregister_cleanup(handler: Callable):
    """注销清理函数（便捷函数）"""
    cleaner = get_resource_cleaner()
    cleaner.unregister_cleanup_handler(handler)


def cleanup_all():
    """执行全局清理（便捷函数）"""
    cleaner = get_resource_cleaner()
    cleaner.cleanup_all()


def cleanup_on_exit():
    """程序退出时清理资源（便捷函数）"""
    logger.info("程序退出，执行资源清理...")
    cleanup_all()


# 资源清理装饰器
def auto_cleanup(func):
    """自动资源清理装饰器，在函数执行后自动清理资源"""
    def wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
            return result
        finally:
            try:
                cleanup_all()
            except Exception as e:
                logger.error(f"自动资源清理失败: {e}")

    return wrapper


# 上下文管理器
class ResourceCleanupContext:
    """资源清理上下文管理器"""

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            cleanup_all()
        except Exception as e:
            logger.error(f"上下文资源清理失败: {e}")
        return False


def resource_cleanup_context():
    """创建资源清理上下文管理器（便捷函数）"""
    return ResourceCleanupContext()

