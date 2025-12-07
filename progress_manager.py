"""进度条管理器 - 简化进度条更新逻辑"""

from PyQt6 import QtCore, QtWidgets
from log_manager import global_logger


class ProgressManager(QtCore.QObject):
    """进度条管理器，统一管理进度条显示和更新"""
    
    def __init__(self, progress_bar: QtWidgets.QProgressBar):
        super().__init__()
        self.logger = global_logger
        self.progress_bar = progress_bar
        self._connected = False
        
        # 初始化进度条
        self._init_progress_bar()
        
    def _init_progress_bar(self):
        """初始化进度条设置"""
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.hide()  # 初始隐藏
        
    def connect_scanner(self, scanner):
        """连接扫描器的进度更新信号"""
        if self._connected:
            self.logger.debug("进度条信号已经连接，跳过重复连接")
            return
            
        try:
            # 连接进度更新信号
            scanner.progress_updated.connect(self.update_progress)
            self.logger.debug("进度条更新信号已连接")
            
            # 连接扫描开始信号
            scanner.progress_updated.connect(
                lambda cur, total: self.show_progress() if total > 0 else None
            )
            
            # 连接扫描完成信号
            scanner.scan_completed.connect(self.hide_progress)
            
            self._connected = True
            self.logger.info("进度条管理器连接完成")
            
        except Exception as e:
            self.logger.error(f"连接进度条信号失败: {e}")
            
    def update_progress(self, current: int, total: int):
        """更新进度条
        
        Args:
            current: 当前进度
            total: 总进度
        """
        try:
            # 确保在主线程中执行
            if QtCore.QThread.currentThread() != self.thread():
                QtCore.QTimer.singleShot(0, lambda: self._update_progress_internal(current, total))
            else:
                self._update_progress_internal(current, total)
                
        except Exception as e:
            self.logger.error(f"更新进度条失败: {e}")
            
    def _update_progress_internal(self, current: int, total: int):
        """内部方法：更新进度条"""
        try:
            # 计算百分比
            if total <= 0:
                progress_value = 0
            else:
                progress_value = int(current / total * 100)
                progress_value = max(0, min(100, progress_value))  # 确保在0-100范围内
            
            # 确保进度条可见
            if not self.progress_bar.isVisible():
                self.progress_bar.show()
                self.logger.info(f"显示进度条，当前值: {progress_value}%")
                
            # 更新进度值
            old_value = self.progress_bar.value()
            if old_value != progress_value:
                self.progress_bar.setValue(progress_value)
                self.logger.info(f"进度条更新: {old_value}% -> {progress_value}% ({current}/{total})")
                
                # 强制UI更新
                from PyQt6 import QtWidgets
                QtWidgets.QApplication.processEvents()
                
                # 额外检查：确保进度条值真的被设置了
                actual_value = self.progress_bar.value()
                if actual_value != progress_value:
                    self.logger.error(f"进度条值设置失败！期望: {progress_value}%，实际: {actual_value}%")
                    # 尝试再次设置
                    self.progress_bar.setValue(progress_value)
            
        except Exception as e:
            self.logger.error(f"内部更新进度条失败: {e}")
            
    def show_progress(self):
        """显示进度条"""
        try:
            self.progress_bar.show()
            self.progress_bar.setValue(0)
            self.logger.debug("显示进度条")
        except Exception as e:
            self.logger.error(f"显示进度条失败: {e}")
            
    def hide_progress(self):
        """隐藏进度条"""
        try:
            self.progress_bar.hide()
            self.progress_bar.setValue(0)
            self.logger.debug("隐藏进度条")
        except Exception as e:
            self.logger.error(f"隐藏进度条失败: {e}")
            
    def reset(self):
        """重置进度条"""
        try:
            self.progress_bar.setValue(0)
            self.logger.debug("重置进度条")
        except Exception as e:
            self.logger.error(f"重置进度条失败: {e}")
