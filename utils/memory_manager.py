import gc
import weakref
import threading
import time
from typing import Dict, Any, Optional, Callable, List
from core.log_manager import global_logger
from utils.singleton import Singleton

logger = global_logger


class MemoryManager(Singleton):

    def __init__(self):
        if self._initialized:
            return

        self._object_pools: Dict[str, Dict[str, Any]] = {}
        self._weak_refs: Dict[str, weakref.WeakValueDictionary] = {}
        self._cache: Dict[str, Any] = {}
        self._lock = threading.Lock()
        # 动态扩缩容配置
        self._auto_resize_enabled = True  # 是否启用动态扩缩容
        self._resize_threshold_high = 0.8  # 高水位阈值（利用率超过此值触发扩容）
        self._resize_threshold_low = 0.2  # 低水位阈值（利用率低于此值触发缩容）
        self._max_pool_multiplier = 4  # 最大扩容倍数（相对于初始max_size）
        self._initialized = True

        logger.info("内存管理器已初始化（支持动态扩缩容）")

    def create_object_pool(self, pool_name: str, factory_func: Callable, max_size: int = 100):
        """创建对象池"""
        with self._lock:
            if pool_name not in self._object_pools:
                self._object_pools[pool_name] = {
                    'pool': [],
                    'factory': factory_func,
                    'max_size': max_size,
                    'initial_max_size': max_size,  # 保存初始大小
                    'created': 0,
                    'reused': 0,
                    'peak_usage': 0  # 峰值使用量统计
                }
                logger.debug(f"创建对象池: {pool_name}, 最大大小: {max_size}（支持动态扩缩容）")

    def get_from_pool(self, pool_name: str, *args, **kwargs):
        """从对象池获取对象（支持动态扩容）"""
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
                
                # 更新峰值使用统计
                current_usage = pool_info['created'] - len(pool)
                if current_usage > pool_info.get('peak_usage', 0):
                    pool_info['peak_usage'] = current_usage
                
                return obj
            else:
                # 创建新对象前检查是否需要扩容
                if self._auto_resize_enabled and self._should_expand_pool(pool_info):
                    self._expand_pool(pool_info)
                
                obj = pool_info['factory'](*args, **kwargs)
                pool_info['created'] += 1
                return obj

    def _should_expand_pool(self, pool_info: Dict) -> bool:
        """判断是否应该扩容"""
        max_size = pool_info['max_size']
        initial_size = pool_info.get('initial_max_size', max_size)

        # 未达到最大扩容限制才考虑扩容
        if max_size >= initial_size * self._max_pool_multiplier:
            return False

        # 真正的使用率 = 正在外部使用的对象数 / max_size
        # 正在外部使用的对象数 = 总创建数 - 当前在池中的数量
        in_use = pool_info['created'] - len(pool_info['pool'])
        if max_size > 0:
            usage_rate = in_use / max_size
            return usage_rate > self._resize_threshold_high

        return False

    def _expand_pool(self, pool_info: Dict):
        """扩容对象池"""
        old_max = pool_info['max_size']
        initial_size = pool_info.get('initial_max_size', old_max)
        
        # 计算新的max_size（翻倍，但不超过上限）
        new_max = min(old_max * 2, initial_size * self._max_pool_multiplier)
        
        pool_info['max_size'] = new_max
        logger.info(f"对象池自动扩容: {old_max} -> {new_max}（上限: {initial_size * self._max_pool_multiplier}）")

    def _should_shrink_pool(self, pool_info: Dict) -> bool:
        """判断是否应该缩容"""
        current_size = len(pool_info['pool'])
        max_size = pool_info['max_size']
        initial_size = pool_info.get('initial_max_size', max_size)

        # 使用率低且大于初始大小才考虑缩容
        if max_size > initial_size and current_size > 0:
            # 真正的使用率 = 正在外部使用的对象数 / max_size
            in_use = pool_info['created'] - current_size
            if max_size > 0:
                usage_rate = max(0, in_use) / max_size
                # 占用率（池中闲置对象 / max_size）
                occupancy_rate = current_size / max_size
                return usage_rate < self._resize_threshold_low and occupancy_rate < self._resize_threshold_low

        return False

    def _shrink_pool(self, pool_info: Dict):
        """缩容对象池"""
        old_max = pool_info['max_size']
        initial_size = pool_info.get('initial_max_size', old_max)
        pool = pool_info['pool']
        
        # 计算新的max_size（减半，但不小于初始大小）
        new_max = max(old_max // 2, initial_size)
        
        # 如果新大小小于当前池中对象数量，先移除多余对象
        while len(pool) > new_max and pool:
            pool.pop()
        
        pool_info['max_size'] = new_max
        logger.info(f"对象池自动缩容: {old_max} -> {new_max}（初始大小: {initial_size}）")

    def return_to_pool(self, pool_name: str, obj):
        """将对象返回到对象池（支持动态缩容）"""
        with self._lock:
            if pool_name not in self._object_pools:
                logger.warning(f"对象池 {pool_name} 不存在")
                return

            pool_info = self._object_pools[pool_name]
            pool = pool_info['pool']

            if len(pool) < pool_info['max_size']:
                pool.append(obj)
                
                # 检查是否需要缩容（在返回对象时异步检查）
                if self._auto_resize_enabled and len(pool) > 10:
                    if self._should_shrink_pool(pool_info):
                        self._shrink_pool(pool_info)

    def register_weak_ref(self, ref_name: str, obj):
        """注册弱引用"""
        with self._lock:
            if ref_name not in self._weak_refs:
                self._weak_refs[ref_name] = weakref.WeakValueDictionary()
            self._weak_refs[ref_name][id(obj)] = obj

    def get_weak_ref(self, ref_name: str, obj_id: int):
        """获取弱引用对象"""
        with self._lock:
            if ref_name in self._weak_refs:
                return self._weak_refs[ref_name].get(obj_id)
            return None

    def cache_object(self, key: str, obj: Any, max_age: Optional[int] = None):
        """缓存对象"""
        with self._lock:
            self._cache[key] = {
                'object': obj,
                'timestamp': time.time() if max_age else None,
                'max_age': max_age
            }

    def get_cached_object(self, key: str):
        """获取缓存对象"""
        with self._lock:
            if key in self._cache:
                entry = self._cache[key]
                if entry['max_age'] and entry['timestamp']:
                    if time.time() - entry['timestamp'] > entry['max_age']:
                        del self._cache[key]
                        return None
                return entry['object']

            return None

    def clear_cache(self, key: Optional[str] = None):
        """清除缓存"""
        with self._lock:
            if key:
                if key in self._cache:
                    del self._cache[key]
            else:
                self._cache.clear()

    def optimize_memory(self):
        """优化内存使用"""
        logger.info("开始内存优化...")

        # 强制垃圾回收
        gc.collect()

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

        # 清理对象池（保留一半对象）
        for pool_name, pool_info in self._object_pools.items():
            pool = pool_info['pool']
            if len(pool) > pool_info['max_size'] // 2:
                remove_count = len(pool) - pool_info['max_size'] // 2
                for _ in range(remove_count):
                    pool.pop()

        logger.info("内存优化完成")

    def get_memory_stats(self) -> Dict[str, Any]:
        """获取内存统计信息"""
        try:
            import psutil
            import os

            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()

            stats = {
                'rss': memory_info.rss,
                'vms': memory_info.vms,
                'object_pools': {},
                'cache_size': len(self._cache),
                'weak_refs': sum(len(refs) for refs in self._weak_refs.values())
            }

            for pool_name, pool_info in self._object_pools.items():
                stats['object_pools'][pool_name] = {
                    'pool_size': len(pool_info['pool']),
                    'created': pool_info['created'],
                    'reused': pool_info['reused'],
                    'max_size': pool_info['max_size'],
                    'initial_max_size': pool_info.get('initial_max_size', pool_info['max_size']),
                    'peak_usage': pool_info.get('peak_usage', 0),
                    'usage_rate': f"{(pool_info['created'] / (pool_info['created'] + pool_info['reused']) * 100):.1f}%" if (pool_info['created'] + pool_info['reused']) > 0 else "N/A"
                }

            return stats
        except ImportError:
            return {
                'rss': 0, 'vms': 0, 'object_pools': {},
                'cache_size': len(self._cache),
                'weak_refs': sum(len(refs) for refs in self._weak_refs.values())
            }

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

# 全局内存管理器访问函数
def get_memory_manager() -> MemoryManager:
    """获取全局内存管理器"""
    return MemoryManager()


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
