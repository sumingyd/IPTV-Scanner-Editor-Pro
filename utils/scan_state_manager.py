"""
扫描状态管理器
提供统一的扫描状态管理，消除重复的扫描状态跟踪逻辑
"""

from typing import Dict, Any, List, Optional
from core.log_manager import global_logger
import threading
import time

logger = global_logger


class ScanStateManager:
    """扫描状态管理器（单例模式）"""

    _instance = None
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

        self._lock = threading.Lock()
        self._scan_states: Dict[str, Dict[str, Any]] = {}
        self._retry_states: Dict[str, Dict[str, Any]] = {}
        self._initialized = True
        logger.info("扫描状态管理器已初始化")

    def register_scan(self, scan_id: str, scanner=None):
        """注册扫描任务

        Args:
            scan_id: 扫描ID，可以是'scan'、'validation'、'retry_scan'等
            scanner: 扫描器对象（可选）
        """
        with self._lock:
            if scan_id not in self._scan_states:
                self._scan_states[scan_id] = {
                    'is_scanning': False,
                    'is_validating': False,
                    'stats': {
                        'total': 0,
                        'valid': 0,
                        'invalid': 0,
                        'start_time': 0,
                        'elapsed': 0
                    },
                    'invalid_urls': [],
                    'scanner': scanner,
                    'last_update': time.time()
                }
                logger.debug(f"注册扫描任务: {scan_id}")

    def unregister_scan(self, scan_id: str):
        """注销扫描任务"""
        with self._lock:
            if scan_id in self._scan_states:
                del self._scan_states[scan_id]
                logger.debug(f"注销扫描任务: {scan_id}")

    def update_scan_state(self, scan_id: str, state: Dict[str, Any]):
        """更新扫描状态"""
        with self._lock:
            if scan_id in self._scan_states:
                self._scan_states[scan_id].update(state)
                self._scan_states[scan_id]['last_update'] = time.time()
                logger.debug(f"更新扫描状态: {scan_id} -> {state}")

    def get_scan_state(self, scan_id: str) -> Optional[Dict[str, Any]]:
        """获取扫描状态"""
        with self._lock:
            return self._scan_states.get(scan_id)

    def is_scanning(self, scan_id: str = 'scan') -> bool:
        """检查是否正在扫描"""
        with self._lock:
            if scan_id in self._scan_states:
                return self._scan_states[scan_id].get('is_scanning', False)
            return False

    def is_validating(self, scan_id: str = 'validation') -> bool:
        """检查是否正在验证"""
        with self._lock:
            if scan_id in self._scan_states:
                return self._scan_states[scan_id].get('is_validating', False)
            return False

    def update_stats(self, scan_id: str, stats: Dict[str, Any]):
        """更新统计信息"""
        with self._lock:
            if scan_id in self._scan_states:
                self._scan_states[scan_id]['stats'].update(stats)
                self._scan_states[scan_id]['last_update'] = time.time()
                logger.debug(f"更新统计信息: {scan_id} -> {stats}")

    def get_stats(self, scan_id: str) -> Optional[Dict[str, Any]]:
        """获取统计信息"""
        with self._lock:
            if scan_id in self._scan_states:
                return self._scan_states[scan_id].get('stats')
            return None

    def add_invalid_url(self, scan_id: str, url: str):
        """添加无效URL"""
        with self._lock:
            if scan_id in self._scan_states:
                if url not in self._scan_states[scan_id]['invalid_urls']:
                    self._scan_states[scan_id]['invalid_urls'].append(url)
                    logger.debug(f"添加无效URL: {scan_id} -> {url[:50]}...")

    def get_invalid_urls(self, scan_id: str) -> List[str]:
        """获取无效URL列表"""
        with self._lock:
            if scan_id in self._scan_states:
                return self._scan_states[scan_id].get('invalid_urls', [])
            return []

    def clear_invalid_urls(self, scan_id: str):
        """清空无效URL列表"""
        with self._lock:
            if scan_id in self._scan_states:
                self._scan_states[scan_id]['invalid_urls'] = []
                logger.debug(f"清空无效URL列表: {scan_id}")

    # 重试扫描状态管理
    def register_retry_scan(self, retry_id: str, main_window=None):
        """注册重试扫描任务"""
        with self._lock:
            if retry_id not in self._retry_states:
                self._retry_states[retry_id] = {
                    'is_retry_scan': False,
                    'failed_channels': [],
                    'retry_count': 0,
                    'last_retry_valid_count': 0,
                    'main_window': main_window,
                    'last_update': time.time()
                }
                logger.debug(f"注册重试扫描任务: {retry_id}")

    def update_retry_state(self, retry_id: str, state: Dict[str, Any]):
        """更新重试扫描状态"""
        with self._lock:
            if retry_id in self._retry_states:
                self._retry_states[retry_id].update(state)
                self._retry_states[retry_id]['last_update'] = time.time()
                logger.debug(f"更新重试扫描状态: {retry_id} -> {state}")

    def get_retry_state(self, retry_id: str) -> Optional[Dict[str, Any]]:
        """获取重试扫描状态"""
        with self._lock:
            return self._retry_states.get(retry_id)

    def is_retry_scan(self, retry_id: str = 'retry') -> bool:
        """检查是否正在重试扫描"""
        with self._lock:
            if retry_id in self._retry_states:
                return self._retry_states[retry_id].get('is_retry_scan', False)
            return False

    def add_failed_channel(self, retry_id: str, url: str):
        """添加失败频道"""
        with self._lock:
            if retry_id in self._retry_states:
                if url not in self._retry_states[retry_id]['failed_channels']:
                    self._retry_states[retry_id]['failed_channels'].append(url)
                    logger.debug(f"添加失败频道: {retry_id} -> {url[:50]}...")

    def get_failed_channels(self, retry_id: str) -> List[str]:
        """获取失败频道列表"""
        with self._lock:
            if retry_id in self._retry_states:
                return self._retry_states[retry_id].get('failed_channels', [])
            return []

    def clear_failed_channels(self, retry_id: str):
        """清空失败频道列表"""
        with self._lock:
            if retry_id in self._retry_states:
                self._retry_states[retry_id]['failed_channels'] = []
                logger.debug(f"清空失败频道列表: {retry_id}")

    def increment_retry_count(self, retry_id: str) -> int:
        """增加重试计数并返回新值"""
        with self._lock:
            if retry_id in self._retry_states:
                self._retry_states[retry_id]['retry_count'] += 1
                count = self._retry_states[retry_id]['retry_count']
                logger.debug(f"增加重试计数: {retry_id} -> {count}")
                return count
            return 0

    def reset_retry_count(self, retry_id: str):
        """重置重试计数"""
        with self._lock:
            if retry_id in self._retry_states:
                self._retry_states[retry_id]['retry_count'] = 0
                logger.debug(f"重置重试计数: {retry_id}")

    def get_retry_count(self, retry_id: str) -> int:
        """获取重试计数"""
        with self._lock:
            if retry_id in self._retry_states:
                return self._retry_states[retry_id].get('retry_count', 0)
            return 0

    def update_last_retry_valid_count(self, retry_id: str, count: int):
        """更新上一次重试的有效频道数"""
        with self._lock:
            if retry_id in self._retry_states:
                self._retry_states[retry_id]['last_retry_valid_count'] = count
                logger.debug(f"更新上一次重试有效频道数: {retry_id} -> {count}")

    def get_last_retry_valid_count(self, retry_id: str) -> int:
        """获取上一次重试的有效频道数"""
        with self._lock:
            if retry_id in self._retry_states:
                return self._retry_states[retry_id].get('last_retry_valid_count', 0)
            return 0

    def clear_all_states(self):
        """清除所有状态"""
        with self._lock:
            self._scan_states.clear()
            self._retry_states.clear()
            logger.info("已清除所有扫描状态")


# 全局扫描状态管理器实例
_global_scan_state_manager: ScanStateManager = None


def get_scan_state_manager() -> ScanStateManager:
    """获取全局扫描状态管理器"""
    global _global_scan_state_manager
    if _global_scan_state_manager is None:
        _global_scan_state_manager = ScanStateManager()
    return _global_scan_state_manager


# 便捷函数
def register_scan_task(scan_id: str, scanner=None):
    """注册扫描任务（便捷函数）"""
    manager = get_scan_state_manager()
    manager.register_scan(scan_id, scanner)


def update_scan_stats(scan_id: str, stats: Dict[str, Any]):
    """更新扫描统计信息（便捷函数）"""
    manager = get_scan_state_manager()
    manager.update_stats(scan_id, stats)


def get_scan_stats(scan_id: str) -> Optional[Dict[str, Any]]:
    """获取扫描统计信息（便捷函数）"""
    manager = get_scan_state_manager()
    return manager.get_stats(scan_id)


def is_scan_in_progress(scan_id: str = 'scan') -> bool:
    """检查扫描是否在进行中（便捷函数）"""
    manager = get_scan_state_manager()
    return manager.is_scanning(scan_id)


def register_retry_task(retry_id: str, main_window=None):
    """注册重试扫描任务（便捷函数）"""
    manager = get_scan_state_manager()
    manager.register_retry_scan(retry_id, main_window)


def update_retry_state(retry_id: str, state: Dict[str, Any]):
    """更新重试扫描状态（便捷函数）"""
    manager = get_scan_state_manager()
    manager.update_retry_state(retry_id, state)


def is_retry_in_progress(retry_id: str = 'retry') -> bool:
    """检查重试扫描是否在进行中（便捷函数）"""
    manager = get_scan_state_manager()
    return manager.is_retry_scan(retry_id)


# 扫描状态上下文管理器
class ScanStateContext:
    """扫描状态上下文管理器"""

    def __init__(self, scan_id: str, scanner=None):
        self.scan_id = scan_id
        self.scanner = scanner

    def __enter__(self):
        """进入上下文时注册扫描任务"""
        register_scan_task(self.scan_id, self.scanner)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出上下文时注销扫描任务"""
        if exc_type is None:
            # 没有异常，正常退出
            manager = get_scan_state_manager()
            manager.unregister_scan(self.scan_id)

        # 不处理异常，让异常正常传播
        return False


# 重试扫描状态上下文管理器
class RetryScanStateContext:
    """重试扫描状态上下文管理器"""

    def __init__(self, retry_id: str, main_window=None):
        self.retry_id = retry_id
        self.main_window = main_window

    def __enter__(self):
        """进入上下文时注册重试扫描任务"""
        register_retry_task(self.retry_id, self.main_window)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出上下文时重置重试状态"""
        if exc_type is None:
            # 没有异常，正常退出
            manager = get_scan_state_manager()
            manager.reset_retry_count(self.retry_id)
            manager.clear_failed_channels(self.retry_id)

        # 不处理异常，让异常正常传播
        return False
