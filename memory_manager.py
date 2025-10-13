"""内存管理工具 - 优化内存使用"""

import gc
import weakref
import threading
import time
from typing import Dict, Any, Optional
from log_manager import LogManager, global_logger

logger = global_logger


class MemoryManager:
    """内存管理器，提供内存优化功能"""
    
    _instance: Optional['MemoryManager'] = None
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
            
        self._object_pools: Dict[str, list] = {}
        self._weak_refs: Dict[str, weakref.WeakValueDictionary] = {}
        self._cache: Dict[str, Any] = {}
        self._lock = threading.Lock()
        self._initialized = True
        
        logger.info("内存管理器已初始化")
    
    def create_object_pool(self, pool_name: str, factory_func, max_size: int = 100):
        """创建对象池
        
        Args:
            pool_name: 对象池名称
            factory_func: 对象工厂函数
            max_size: 最大池大小
        """
        with self._lock:
            if pool_name not in self._object_pools:
                self._object_pools[pool_name] = {
                    'pool': [],
                    'factory': factory_func,
                    'max_size': max_size,
                    'created': 0,
                    'reused': 0
                }
                logger.debug(f"创建对象池: {pool_name}, 最大大小: {max_size}")
    
    def get_from_pool(self, pool_name: str, *args, **kwargs):
        """从对象池获取对象
        
        Args:
            pool_name: 对象池名称
            *args, **kwargs: 传递给工厂函数的参数
            
        Returns:
            对象实例
        """
        with self._lock:
            if pool_name not in self._object_pools:
                logger.warning(f"对象池 {pool_name} 不存在")
                return None
                
            pool_info = self._object_pools[pool_name]
            pool = pool_info['pool']
            
            if pool:
                # 从池中获取对象
                obj = pool.pop()
                pool_info['reused'] += 1
                logger.debug(f"从对象池 {pool_name} 复用对象，池大小: {len(pool)}")
                return obj
            else:
                # 创建新对象
                obj = pool_info['factory'](*args, **kwargs)
                pool_info['created'] += 1
                logger.debug(f"从对象池 {pool_name} 创建新对象，已创建: {pool_info['created']}")
                return obj
    
    def return_to_pool(self, pool_name: str, obj):
        """将对象返回到对象池
        
        Args:
            pool_name: 对象池名称
            obj: 要返回的对象
        """
        with self._lock:
            if pool_name not in self._object_pools:
                logger.warning(f"对象池 {pool_name} 不存在")
                return
                
            pool_info = self._object_pools[pool_name]
            pool = pool_info['pool']
            
            if len(pool) < pool_info['max_size']:
                pool.append(obj)
                logger.debug(f"对象返回到池 {pool_name}，池大小: {len(pool)}")
            else:
                logger.debug(f"对象池 {pool_name} 已满，丢弃对象")
    
    def register_weak_ref(self, ref_name: str, obj):
        """注册弱引用
        
        Args:
            ref_name: 引用名称
            obj: 要引用的对象
        """
        with self._lock:
            if ref_name not in self._weak_refs:
                self._weak_refs[ref_name] = weakref.WeakValueDictionary()
            
            self._weak_refs[ref_name][id(obj)] = obj
            logger.debug(f"注册弱引用: {ref_name}, 对象ID: {id(obj)}")
    
    def get_weak_ref(self, ref_name: str, obj_id: int):
        """获取弱引用对象
        
        Args:
            ref_name: 引用名称
            obj_id: 对象ID
            
        Returns:
            对象实例或None
        """
        with self._lock:
            if ref_name in self._weak_refs:
                return self._weak_refs[ref_name].get(obj_id)
            return None
    
    def cache_object(self, key: str, obj: Any, max_age: Optional[int] = None):
        """缓存对象
        
        Args:
            key: 缓存键
            obj: 要缓存的对象
            max_age: 最大缓存时间（秒）
        """
        with self._lock:
            cache_entry = {
                'object': obj,
                'timestamp': time.time() if max_age else None,
                'max_age': max_age
            }
            self._cache[key] = cache_entry
            logger.debug(f"缓存对象: {key}")
    
    def get_cached_object(self, key: str):
        """获取缓存对象
        
        Args:
            key: 缓存键
            
        Returns:
            缓存的对象或None
        """
        with self._lock:
            if key in self._cache:
                entry = self._cache[key]
                
                # 检查缓存是否过期
                if entry['max_age'] and entry['timestamp']:
                    current_time = time.time()
                    if current_time - entry['timestamp'] > entry['max_age']:
                        del self._cache[key]
                        logger.debug(f"缓存对象 {key} 已过期")
                        return None
                
                logger.debug(f"从缓存获取对象: {key}")
                return entry['object']
            
            return None
    
    def clear_cache(self, key: Optional[str] = None):
        """清除缓存
        
        Args:
            key: 要清除的缓存键，如果为None则清除所有缓存
        """
        with self._lock:
            if key:
                if key in self._cache:
                    del self._cache[key]
                    logger.debug(f"清除缓存: {key}")
            else:
                cache_size = len(self._cache)
                self._cache.clear()
                logger.debug(f"清除所有缓存，共 {cache_size} 个对象")
    
    def optimize_memory(self):
        """优化内存使用"""
        logger.info("开始内存优化...")
        
        # 强制垃圾回收
        collected = gc.collect()
        logger.debug(f"垃圾回收完成，回收对象: {collected}")
        
        # 清理过期的缓存
        current_time = time.time()
        expired_keys = []
        
        with self._lock:
            for key, entry in self._cache.items():
                if entry['max_age'] and entry['timestamp']:
                    if current_time - entry['timestamp'] > entry['max_age']:
                        expired_keys.append(key)
            
            for key in expired_keys:
                del self._cache[key]
        
        if expired_keys:
            logger.debug(f"清理过期缓存: {len(expired_keys)} 个对象")
        
        # 清理对象池（保留一半对象）
        for pool_name, pool_info in self._object_pools.items():
            pool = pool_info['pool']
            if len(pool) > pool_info['max_size'] // 2:
                remove_count = len(pool) - pool_info['max_size'] // 2
                for _ in range(remove_count):
                    pool.pop()
                logger.debug(f"清理对象池 {pool_name}，移除 {remove_count} 个对象")
        
        logger.info("内存优化完成")
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """获取内存统计信息
        
        Returns:
            内存统计信息字典
        """
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        
        stats = {
            'rss': memory_info.rss,  # 物理内存使用
            'vms': memory_info.vms,  # 虚拟内存使用
            'object_pools': {},
            'cache_size': len(self._cache),
            'weak_refs': sum(len(refs) for refs in self._weak_refs.values())
        }
        
        # 对象池统计
        for pool_name, pool_info in self._object_pools.items():
            stats['object_pools'][pool_name] = {
                'pool_size': len(pool_info['pool']),
                'created': pool_info['created'],
                'reused': pool_info['reused'],
                'max_size': pool_info['max_size']
            }
        
        return stats
    
    def log_memory_stats(self):
        """记录内存统计信息到日志"""
        stats = self.get_memory_stats()
        
        logger.info(f"内存使用统计 - RSS: {stats['rss'] / 1024 / 1024:.2f} MB, "
                   f"VMS: {stats['vms'] / 1024 / 1024:.2f} MB, "
                   f"缓存对象: {stats['cache_size']}, "
                   f"弱引用: {stats['weak_refs']}")
        
        for pool_name, pool_stats in stats['object_pools'].items():
            logger.info(f"对象池 {pool_name} - 大小: {pool_stats['pool_size']}/"
                       f"{pool_stats['max_size']}, 创建: {pool_stats['created']}, "
                       f"复用: {pool_stats['reused']}")


# 全局内存管理器实例
_global_memory_manager: Optional[MemoryManager] = None


def get_memory_manager() -> MemoryManager:
    """获取全局内存管理器
    
    Returns:
        全局内存管理器实例
    """
    global _global_memory_manager
    if _global_memory_manager is None:
        _global_memory_manager = MemoryManager()
    return _global_memory_manager


def optimize_memory():
    """优化内存使用（便捷函数）"""
    manager = get_memory_manager()
    manager.optimize_memory()


def log_memory_stats():
    """记录内存统计信息（便捷函数）"""
    manager = get_memory_manager()
    manager.log_memory_stats()


# 内存优化装饰器
def memory_optimized(func):
    """内存优化装饰器，在函数执行前后进行内存优化"""
    def wrapper(*args, **kwargs):
        # 函数执行前优化内存
        optimize_memory()
        
        try:
            result = func(*args, **kwargs)
            return result
        finally:
            # 函数执行后优化内存
            optimize_memory()
    
    return wrapper
