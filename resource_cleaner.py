"""全局资源清理器"""

import gc
import threading
import weakref
from typing import List, Callable, Optional
from log_manager import global_logger

logger = global_logger


class ResourceCleaner:
    """全局资源清理器"""
    
    _instance: Optional['ResourceCleaner'] = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._cleanup_handlers: List[Callable] = []
        self._weak_handlers = weakref.WeakValueDictionary()
        self._lock = threading.Lock()
        self._initialized = True
        
        logger.info("资源清理器已初始化")
    
    def register_cleanup_handler(self, handler: Callable, name: Optional[str] = None):
        """注册清理处理器
        
        Args:
            handler: 清理函数
            name: 处理器名称（可选），用于调试
        """
        with self._lock:
            self._cleanup_handlers.append(handler)
            if name:
                self._weak_handlers[name] = handler
            logger.debug(f"注册清理处理器: {name or handler.__name__}")
    
    def unregister_cleanup_handler(self, handler: Callable):
        """注销清理处理器"""
        with self._lock:
            if handler in self._cleanup_handlers:
                self._cleanup_handlers.remove(handler)
                # 从弱引用字典中删除
                to_remove = []
                for name, h in self._weak_handlers.items():
                    if h == handler:
                        to_remove.append(name)
                for name in to_remove:
                    del self._weak_handlers[name]
                logger.debug(f"注销清理处理器: {handler.__name__}")
    
    def cleanup_all(self):
        """执行所有清理操作"""
        logger.info("开始全局资源清理...")
        
        # 按注册顺序执行清理处理器
        handlers_to_execute = []
        with self._lock:
            handlers_to_execute = self._cleanup_handlers.copy()
        
        success_count = 0
        error_count = 0
        
        for handler in handlers_to_execute:
            handler_name = None
            with self._lock:
                # 查找处理器名称
                for name, h in self._weak_handlers.items():
                    if h == handler:
                        handler_name = name
                        break
            
            try:
                handler()
                success_count += 1
                logger.debug(f"清理处理器执行成功: {handler_name or handler.__name__}")
            except Exception as e:
                error_count += 1
                logger.error(f"清理处理器执行失败 {handler_name or handler.__name__}: {e}")
        
        # 强制垃圾回收
        collected = gc.collect()
        logger.debug(f"垃圾回收完成，回收对象: {collected}")
        
        # 清理弱引用字典中的无效引用
        with self._lock:
            # 创建副本以避免在迭代时修改
            weak_items = list(self._weak_handlers.items())
            for name, handler in weak_items:
                if handler is None:
                    del self._weak_handlers[name]
        
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
            self._weak_handlers.clear()
            logger.info(f"已清除所有清理处理器，共 {handler_count} 个")


# 全局资源清理器实例
_global_cleaner: Optional[ResourceCleaner] = None


def get_resource_cleaner() -> ResourceCleaner:
    """获取全局资源清理器
    
    Returns:
        全局资源清理器实例
    """
    global _global_cleaner
    if _global_cleaner is None:
        _global_cleaner = ResourceCleaner()
    return _global_cleaner


def register_cleanup(handler: Callable, name: Optional[str] = None):
    """注册清理函数（便捷函数）
    
    Args:
        handler: 清理函数
        name: 处理器名称（可选）
    """
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
            # 函数执行后清理资源
            try:
                cleanup_all()
            except Exception as e:
                logger.error(f"自动资源清理失败: {e}")
    
    return wrapper


# 上下文管理器
class ResourceCleanupContext:
    """资源清理上下文管理器"""
    
    def __enter__(self):
        """进入上下文"""
        logger.debug("进入资源清理上下文")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出上下文时清理资源"""
        logger.debug("退出资源清理上下文，执行清理")
        try:
            cleanup_all()
        except Exception as e:
            logger.error(f"上下文资源清理失败: {e}")
        
        # 不处理异常，让异常正常传播
        return False


# 便捷函数：创建资源清理上下文
def resource_cleanup_context():
    """创建资源清理上下文管理器（便捷函数）"""
    return ResourceCleanupContext()
