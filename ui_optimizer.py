"""UI响应优化工具 - 提升用户界面响应速度"""

from PyQt6 import QtCore, QtWidgets
from typing import Callable, Any, Optional
from log_manager import LogManager, global_logger

logger = global_logger


class UIOptimizer:
    """UI响应优化器，提供UI性能优化功能"""
    
    def __init__(self):
        self._batch_operations = []
        self._batch_timer = QtCore.QTimer()
        self._batch_timer.setSingleShot(True)
        self._batch_timer.timeout.connect(self._execute_batch_operations)
        self._batch_delay = 50  # 50ms延迟执行批量操作
        
        # UI更新统计
        self._update_stats = {
            'batch_operations': 0,
            'individual_updates': 0,
            'delayed_updates': 0
        }
    
    def batch_update(self, operation: Callable, *args, **kwargs):
        """批量更新UI操作
        
        Args:
            operation: 要执行的UI操作函数
            *args, **kwargs: 操作参数
        """
        self._batch_operations.append((operation, args, kwargs))
        self._update_stats['batch_operations'] += 1
        
        # 启动或重启定时器
        if not self._batch_timer.isActive():
            self._batch_timer.start(self._batch_delay)
    
    def _execute_batch_operations(self):
        """执行批量UI操作"""
        if not self._batch_operations:
            return
            
        operations = self._batch_operations.copy()
        self._batch_operations.clear()
        
        # 执行所有批量操作
        for operation, args, kwargs in operations:
            try:
                operation(*args, **kwargs)
            except Exception as e:
                logger.error(f"批量UI操作执行失败: {e}")
        
        logger.debug(f"执行了 {len(operations)} 个批量UI操作")
    
    def delayed_update(self, operation: Callable, delay_ms: int = 0, *args, **kwargs):
        """延迟更新UI操作
        
        Args:
            operation: 要执行的UI操作函数
            delay_ms: 延迟时间（毫秒）
            *args, **kwargs: 操作参数
        """
        self._update_stats['delayed_updates'] += 1
        QtCore.QTimer.singleShot(delay_ms, lambda: self._safe_execute(operation, *args, **kwargs))
    
    def _safe_execute(self, operation: Callable, *args, **kwargs):
        """安全执行UI操作"""
        try:
            operation(*args, **kwargs)
        except Exception as e:
            logger.error(f"UI操作执行失败: {e}")
    
    def optimize_list_view(self, list_view: QtWidgets.QAbstractItemView):
        """优化列表视图性能
        
        Args:
            list_view: 要优化的列表视图
        """
        # 设置虚拟化属性
        list_view.setUniformItemSizes(True)
        list_view.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel)
        
        # 禁用不必要的动画
        list_view.setProperty("showDropIndicator", False)
        
        # 优化选择行为
        list_view.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        
        logger.debug(f"优化列表视图: {list_view.objectName() or 'unnamed'}")
    
    def optimize_table_view(self, table_view: QtWidgets.QTableView):
        """优化表格视图性能
        
        Args:
            table_view: 要优化的表格视图
        """
        # 设置虚拟化属性
        table_view.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel)
        table_view.setHorizontalScrollMode(QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel)
        
        # 优化列宽调整策略
        header = table_view.horizontalHeader()
        header.setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(True)
        
        # 禁用交替行颜色（在某些系统上可能影响性能）
        table_view.setAlternatingRowColors(False)
        
        logger.debug(f"优化表格视图: {table_view.objectName() or 'unnamed'}")
    
    def suspend_updates(self, widget: QtWidgets.QWidget, operation: Callable, *args, **kwargs):
        """暂停UI更新，执行操作后恢复
        
        Args:
            widget: 要暂停更新的控件
            operation: 要执行的操作
            *args, **kwargs: 操作参数
        """
        try:
            widget.setUpdatesEnabled(False)
            result = operation(*args, **kwargs)
            return result
        finally:
            widget.setUpdatesEnabled(True)
    
    def throttle_updates(self, operation: Callable, throttle_time: int = 100):
        """节流UI更新操作
        
        Args:
            operation: 要节流的操作
            throttle_time: 节流时间（毫秒）
            
        Returns:
            节流后的函数
        """
        last_call_time = 0
        
        def throttled(*args, **kwargs):
            nonlocal last_call_time
            current_time = QtCore.QDateTime.currentMSecsSinceEpoch()
            
            if current_time - last_call_time >= throttle_time:
                last_call_time = current_time
                return operation(*args, **kwargs)
        
        return throttled
    
    def debounce_updates(self, operation: Callable, debounce_time: int = 300):
        """防抖UI更新操作
        
        Args:
            operation: 要防抖的操作
            debounce_time: 防抖时间（毫秒）
            
        Returns:
            防抖后的函数
        """
        timer = QtCore.QTimer()
        timer.setSingleShot(True)
        
        def debounced(*args, **kwargs):
            def execute():
                operation(*args, **kwargs)
            
            timer.timeout.connect(execute)
            timer.start(debounce_time)
        
        return debounced
    
    def get_update_stats(self) -> dict:
        """获取UI更新统计信息
        
        Returns:
            UI更新统计字典
        """
        return self._update_stats.copy()
    
    def reset_stats(self):
        """重置统计信息"""
        self._update_stats = {
            'batch_operations': 0,
            'individual_updates': 0,
            'delayed_updates': 0
        }


# 全局UI优化器实例
_global_ui_optimizer: Optional[UIOptimizer] = None


def get_ui_optimizer() -> UIOptimizer:
    """获取全局UI优化器
    
    Returns:
        全局UI优化器实例
    """
    global _global_ui_optimizer
    if _global_ui_optimizer is None:
        _global_ui_optimizer = UIOptimizer()
    return _global_ui_optimizer


def batch_update(operation: Callable, *args, **kwargs):
    """批量更新UI操作（便捷函数）"""
    optimizer = get_ui_optimizer()
    optimizer.batch_update(operation, *args, **kwargs)


def delayed_update(operation: Callable, delay_ms: int = 0, *args, **kwargs):
    """延迟更新UI操作（便捷函数）"""
    optimizer = get_ui_optimizer()
    optimizer.delayed_update(operation, delay_ms, *args, **kwargs)


def suspend_updates(widget: QtWidgets.QWidget, operation: Callable, *args, **kwargs):
    """暂停UI更新（便捷函数）"""
    optimizer = get_ui_optimizer()
    return optimizer.suspend_updates(widget, operation, *args, **kwargs)


# UI优化装饰器
def ui_optimized(optimization_type: str = "batch", **kwargs):
    """UI优化装饰器
    
    Args:
        optimization_type: 优化类型 ("batch", "delayed", "throttle", "debounce")
        **kwargs: 优化参数
    """
    def decorator(func: Callable) -> Callable:
        if optimization_type == "batch":
            def wrapper(*args, **inner_kwargs):
                batch_update(func, *args, **inner_kwargs)
            return wrapper
        
        elif optimization_type == "delayed":
            delay_ms = kwargs.get('delay_ms', 0)
            def wrapper(*args, **inner_kwargs):
                delayed_update(func, delay_ms, *args, **inner_kwargs)
            return wrapper
        
        elif optimization_type == "throttle":
            throttle_time = kwargs.get('throttle_time', 100)
            optimizer = get_ui_optimizer()
            return optimizer.throttle_updates(func, throttle_time)
        
        elif optimization_type == "debounce":
            debounce_time = kwargs.get('debounce_time', 300)
            optimizer = get_ui_optimizer()
            return optimizer.debounce_updates(func, debounce_time)
        
        else:
            return func
    
    return decorator
