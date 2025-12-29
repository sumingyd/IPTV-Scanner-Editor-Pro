"""
配置变更通知器
提供统一的配置变更通知机制，消除重复的配置加载逻辑
"""

from typing import Dict, Any, Callable, List
from core.log_manager import global_logger

logger = global_logger


class ConfigChangeNotifier:
    """配置变更通知器（观察者模式）"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._observers: Dict[str, List[Callable]] = {}
        self._initialized = True
        logger.info("配置变更通知器已初始化")

    def register_observer(self, config_key: str, callback: Callable):
        """注册配置变更观察者

        Args:
            config_key: 配置键，格式为'section.key'或'section.*'或'*'
            callback: 回调函数，接收(section, key, old_value, new_value)参数
        """
        if config_key not in self._observers:
            self._observers[config_key] = []

        if callback not in self._observers[config_key]:
            self._observers[config_key].append(callback)
            logger.debug(f"注册配置观察者: {config_key} -> {callback.__name__}")

    def unregister_observer(self, config_key: str, callback: Callable):
        """注销配置变更观察者"""
        if config_key in self._observers and callback in self._observers[config_key]:
            self._observers[config_key].remove(callback)
            logger.debug(f"注销配置观察者: {config_key} -> {callback.__name__}")

            # 如果该键没有观察者了，删除键
            if not self._observers[config_key]:
                del self._observers[config_key]

    def notify_change(self, section: str, key: str, old_value: Any, new_value: Any):
        """通知配置变更

        Args:
            section: 配置节
            key: 配置键
            old_value: 旧值
            new_value: 新值
        """
        # 构建完整的配置键
        full_key = f"{section}.{key}"

        # 收集所有需要通知的观察者
        observers_to_notify = []

        # 匹配精确键
        if full_key in self._observers:
            observers_to_notify.extend(self._observers[full_key])

        # 匹配节通配符
        section_wildcard = f"{section}.*"
        if section_wildcard in self._observers:
            observers_to_notify.extend(self._observers[section_wildcard])

        # 匹配全局通配符
        if "*" in self._observers:
            observers_to_notify.extend(self._observers["*"])

        # 去重
        unique_observers = list(set(observers_to_notify))

        # 通知所有观察者
        for observer in unique_observers:
            try:
                observer(section, key, old_value, new_value)
                logger.debug(f"通知配置变更: {full_key} -> {observer.__name__}")
            except Exception as e:
                logger.error(f"配置变更通知失败 {full_key} -> {observer.__name__}: {e}")

    def clear_observers(self):
        """清除所有观察者"""
        self._observers.clear()
        logger.info("已清除所有配置观察者")


# 全局配置变更通知器实例
_global_config_notifier: ConfigChangeNotifier = None


def get_config_notifier() -> ConfigChangeNotifier:
    """获取全局配置变更通知器"""
    global _global_config_notifier
    if _global_config_notifier is None:
        _global_config_notifier = ConfigChangeNotifier()
    return _global_config_notifier


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

    Args:
        config_key: 配置键，格式为'section.key'或'section.*'或'*'

    Returns:
        装饰器函数
    """
    def decorator(func):
        # 注册观察者
        register_config_observer(config_key, func)

        # 返回原始函数
        return func

    return decorator


# 配置变更上下文管理器
class ConfigChangeContext:
    """配置变更上下文管理器"""

    def __init__(self, section: str, key: str, old_value: Any):
        self.section = section
        self.key = key
        self.old_value = old_value

    def __enter__(self):
        """进入上下文"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出上下文时通知变更"""
        if exc_type is None:
            # 没有异常，通知变更
            from core.config_manager import ConfigManager
            config = ConfigManager()
            new_value = config.get_value(self.section, self.key)
            if new_value != self.old_value:
                notify_config_change(self.section, self.key, self.old_value, new_value)

        # 不处理异常，让异常正常传播
        return False


# 便捷函数：创建配置变更上下文
def config_change_context(section: str, key: str):
    """创建配置变更上下文管理器（便捷函数）

    Args:
        section: 配置节
        key: 配置键

    Returns:
        配置变更上下文管理器
    """
    from core.config_manager import ConfigManager
    config = ConfigManager()
    old_value = config.get_value(section, key)
    return ConfigChangeContext(section, key, old_value)
