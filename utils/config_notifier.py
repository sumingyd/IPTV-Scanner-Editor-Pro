"""
配置变更通知器
提供统一的配置变更通知机制，消除重复的配置加载逻辑
"""

from typing import Dict, Any, Callable, List
from core.log_manager import global_logger
from utils.singleton import Singleton
import threading

logger = global_logger


class ConfigChangeNotifier(Singleton):

    def __init__(self):
        if self._initialized:
            return

        self._observers: Dict[str, List[Callable]] = {}
        self._lock = threading.Lock()
        self._initialized = True
        logger.debug("配置变更通知器已初始化")

    def register_observer(self, config_key: str, callback: Callable):
        with self._lock:
            if config_key not in self._observers:
                self._observers[config_key] = []
            if callback not in self._observers[config_key]:
                self._observers[config_key].append(callback)

    def unregister_observer(self, config_key: str, callback: Callable):
        with self._lock:
            if config_key in self._observers and callback in self._observers[config_key]:
                self._observers[config_key].remove(callback)
                if not self._observers[config_key]:
                    del self._observers[config_key]

    def notify_change(self, section: str, key: str, old_value: Any, new_value: Any):
        full_key = f"{section}.{key}"
        with self._lock:
            observers_to_notify = []
            if full_key in self._observers:
                observers_to_notify.extend(self._observers[full_key])
            section_wildcard = f"{section}.*"
            if section_wildcard in self._observers:
                observers_to_notify.extend(self._observers[section_wildcard])
            if "*" in self._observers:
                observers_to_notify.extend(self._observers["*"])
            seen = set()
            unique_observers = []
            for obs in observers_to_notify:
                obs_id = id(obs)
                if obs_id not in seen:
                    seen.add(obs_id)
                    unique_observers.append(obs)

        for observer in unique_observers:
            try:
                observer(section, key, old_value, new_value)
            except Exception as e:
                logger.error(f"配置变更通知失败 {full_key}: {e}")

    def clear_observers(self):
        with self._lock:
            self._observers.clear()


def get_config_notifier() -> ConfigChangeNotifier:
    """获取全局配置变更通知器"""
    return ConfigChangeNotifier()


def register_config_observer(config_key: str, callback: Callable):
    """注册配置变更观察者（便捷函数）"""
    notifier = get_config_notifier()
    notifier.register_observer(config_key, callback)


def unregister_config_observer(config_key: str, callback: Callable):
    """注销配置变更观察者（便捷函数）"""
    notifier = get_config_notifier()
    notifier.unregister_observer(config_key, callback)


def notify_config_change(section: str, key: str, old_value: Any, new_value: Any):
    """通知配置变更（便捷函数）"""
    notifier = get_config_notifier()
    notifier.notify_change(section, key, old_value, new_value)


# 配置变更装饰器
def on_config_change(config_key: str):
    """配置变更装饰器

    注意：此装饰器仅适用于模块级函数，不适用于实例方法。
    对于实例方法，请在__init__中手动调用 register_config_observer。

    Args:
        config_key: 配置键，格式为'section.key'或'section.*'或'*'

    Returns:
        装饰器函数
    """
    def decorator(func):
        register_config_observer(config_key, func)
        return func

    return decorator


class ConfigChangeContext:
    """配置变更上下文管理器"""

    def __init__(self, section: str, key: str, old_value: Any):
        self.section = section
        self.key = key
        self.old_value = old_value

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            from core.config_manager import ConfigManager
            config = ConfigManager()
            new_value = config.get_value(self.section, self.key)
            if new_value != self.old_value:
                notify_config_change(self.section, self.key, self.old_value, new_value)
        return False


def config_change_context(section: str, key: str):
    """创建配置变更上下文管理器"""
    from core.config_manager import ConfigManager
    config = ConfigManager()
    old_value = config.get_value(section, key)
    return ConfigChangeContext(section, key, old_value)
