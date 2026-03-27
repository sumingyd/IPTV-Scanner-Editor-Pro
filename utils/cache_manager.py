import os
import json
import time
from typing import Any, Dict, Optional
import hashlib


class CacheManager:
    """缓存管理器，用于缓存频繁访问的数据"""

    def __init__(self, cache_dir: str = 'cache', max_size: int = 1000, max_age: int = 3600):
        """初始化缓存管理器

        Args:
            cache_dir: 缓存目录
            max_size: 最大缓存项数量
            max_age: 缓存项最大存活时间（秒）
        """
        self.cache_dir = os.path.join(os.path.dirname(__file__), cache_dir)
        self.max_size = max_size
        self.max_age = max_age
        self._cache: Dict[str, Dict] = {}
        self._load_cache()

    def _get_cache_file(self) -> str:
        """获取缓存文件路径"""
        return os.path.join(self.cache_dir, 'cache.json')

    def _ensure_cache_dir(self):
        """确保缓存目录存在"""
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)

    def _load_cache(self):
        """从文件加载缓存"""
        try:
            cache_file = self._get_cache_file()
            if os.path.exists(cache_file):
                with open(cache_file, 'r', encoding='utf-8') as f:
                    self._cache = json.load(f)
                # 清理过期缓存
                self._clean_expired()
        except Exception as e:
            print(f"加载缓存失败: {e}")
            self._cache = {}

    def _save_cache(self):
        """保存缓存到文件"""
        try:
            self._ensure_cache_dir()
            cache_file = self._get_cache_file()
            # 清理过期缓存
            self._clean_expired()
            # 限制缓存大小
            if len(self._cache) > self.max_size:
                # 按时间排序，删除最旧的缓存
                sorted_items = sorted(self._cache.items(), key=lambda x: x[1]['timestamp'])
                self._cache = dict(sorted_items[-self.max_size:])
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(self._cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存缓存失败: {e}")

    def _clean_expired(self):
        """清理过期缓存"""
        current_time = time.time()
        expired_keys = []
        for key, item in self._cache.items():
            if current_time - item['timestamp'] > self.max_age:
                expired_keys.append(key)
        for key in expired_keys:
            del self._cache[key]

    def _generate_key(self, data: Any) -> str:
        """生成缓存键

        Args:
            data: 要缓存的数据

        Returns:
            str: 缓存键
        """
        if isinstance(data, str):
            key = data
        else:
            key = str(data)
        return hashlib.md5(key.encode('utf-8')).hexdigest()

    def get(self, key: Any) -> Optional[Any]:
        """获取缓存

        Args:
            key: 缓存键

        Returns:
            Any: 缓存的数据，如果不存在或已过期则返回None
        """
        cache_key = self._generate_key(key)
        if cache_key in self._cache:
            item = self._cache[cache_key]
            if time.time() - item['timestamp'] <= self.max_age:
                return item['data']
            else:
                del self._cache[cache_key]
                self._save_cache()
        return None

    def set(self, key: Any, data: Any) -> bool:
        """设置缓存

        Args:
            key: 缓存键
            data: 要缓存的数据

        Returns:
            bool: 是否设置成功
        """
        try:
            cache_key = self._generate_key(key)
            self._cache[cache_key] = {
                'data': data,
                'timestamp': time.time()
            }
            self._save_cache()
            return True
        except Exception as e:
            print(f"设置缓存失败: {e}")
            return False

    def delete(self, key: Any) -> bool:
        """删除缓存

        Args:
            key: 缓存键

        Returns:
            bool: 是否删除成功
        """
        try:
            cache_key = self._generate_key(key)
            if cache_key in self._cache:
                del self._cache[cache_key]
                self._save_cache()
            return True
        except Exception as e:
            print(f"删除缓存失败: {e}")
            return False

    def clear(self) -> bool:
        """清空缓存

        Returns:
            bool: 是否清空成功
        """
        try:
            self._cache = {}
            self._save_cache()
            return True
        except Exception as e:
            print(f"清空缓存失败: {e}")
            return False

    def get_size(self) -> int:
        """获取缓存大小

        Returns:
            int: 缓存项数量
        """
        return len(self._cache)


# 全局缓存管理器实例
cache_manager = CacheManager()


def get_cache() -> CacheManager:
    """获取缓存管理器实例

    Returns:
        CacheManager: 缓存管理器实例
    """
    return cache_manager


def cache_result(func):
    """缓存函数结果的装饰器

    Args:
        func: 要缓存结果的函数

    Returns:
        function: 包装后的函数
    """
    def wrapper(*args, **kwargs):
        # 生成缓存键
        key = f"{func.__name__}:{args}:{kwargs}"
        # 尝试从缓存获取
        cached_result = cache_manager.get(key)
        if cached_result is not None:
            return cached_result
        # 执行函数
        result = func(*args, **kwargs)
        # 缓存结果
        cache_manager.set(key, result)
        return result
    return wrapper