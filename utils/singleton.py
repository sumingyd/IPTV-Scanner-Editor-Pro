import threading
from typing import Any


class Singleton:
    _instances: dict[type, Any] = {}
    _global_lock = threading.Lock()

    def __new__(cls, *args, **kwargs) -> Any:
        if cls not in Singleton._instances:
            with Singleton._global_lock:
                if cls not in Singleton._instances:
                    instance = super().__new__(cls)
                    instance._initialized = False
                    Singleton._instances[cls] = instance
        return Singleton._instances[cls]

    @classmethod
    def reset_instance(cls):
        """重置单例实例（仅用于测试，生产环境调用可能导致持有旧引用的代码出现不可预期行为）"""
        with Singleton._global_lock:
            instance = Singleton._instances.pop(cls, None)
            if instance is not None:
                instance._initialized = False
