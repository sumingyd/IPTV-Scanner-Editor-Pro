"""全新的进度条管理器 - 简化设计，直接更新UI"""

from PyQt6 import QtCore, QtWidgets
from log_manager import global_logger


class SimpleProgressManager(QtCore.QObject):
    """简单的进度条管理器，直接更新进度条UI"""
    
    def __init__(self, progress_bar: QtWidgets.QProgressBar):
        super().__init__()
        self.logger = global_logger
        self.progress_bar = progress_bar
        
        # 初始化进度条
        self._init_progress_bar()
        
    def _init_progress_bar(self):
        """初始化进度条设置"""
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p%")
        self.progress_bar.hide()  # 初始隐藏
        
    def connect_scanner(self, scanner):
        """连接扫描器的进度更新信号"""
        try:
            # 连接进度更新信号
            scanner.progress_updated.connect(self._on_progress_updated)
            self.logger.info("进度条信号连接成功")
            
            # 连接扫描完成信号
            scanner.scan_completed.connect(self._on_scan_completed)
            
        except Exception as e:
            self.logger.error(f"连接进度条信号失败: {e}")
            
    def _on_progress_updated(self, current: int, total: int):
        """处理进度更新信号"""
        try:
            self.logger.info(f"收到进度更新信号: current={current}, total={total}")
            
            # 确保在主线程中执行
            if QtCore.QThread.currentThread() != self.thread():
                self.logger.debug("不在主线程，使用QTimer调度")
                QtCore.QTimer.singleShot(0, lambda: self._update_progress(current, total))
            else:
                self.logger.debug("在主线程，直接更新")
                self._update_progress(current, total)
                
        except Exception as e:
            self.logger.error(f"处理进度更新信号失败: {e}")
            
    def _update_progress(self, current: int, total: int):
        """更新进度条"""
        try:
            # 计算百分比
            if total <= 0:
                progress_value = 0
            else:
                progress_value = int(current / total * 100)
                progress_value = max(0, min(100, progress_value))  # 确保在0-100范围内
            
            # 显示进度条
            if not self.progress_bar.isVisible():
                self.progress_bar.show()
                self.logger.info(f"显示进度条，当前值: {progress_value}%")
            
            # 更新进度值
            old_value = self.progress_bar.value()
            if old_value != progress_value:
                self.progress_bar.setValue(progress_value)
                self.logger.info(f"进度条更新: {old_value}% -> {progress_value}% ({current}/{total})")
                
        except Exception as e:
            self.logger.error(f"更新进度条失败: {e}")
            
    def _on_scan_completed(self):
        """处理扫描完成"""
        try:
            # 扫描完成后隐藏进度条
            self.progress_bar.hide()
            self.progress_bar.setValue(0)
            self.logger.debug("扫描完成，隐藏进度条")
        except Exception as e:
            self.logger.error(f"处理扫描完成失败: {e}")
            
    def show(self):
        """显示进度条"""
        try:
            self.progress_bar.show()
            self.progress_bar.setValue(0)
        except Exception as e:
            self.logger.error(f"显示进度条失败: {e}")
            
    def hide(self):
        """隐藏进度条"""
        try:
            self.progress_bar.hide()
            self.progress_bar.setValue(0)
        except Exception as e:
            self.logger.error(f"隐藏进度条失败: {e}")
            
    def reset(self):
        """重置进度条"""
        try:
            self.progress_bar.setValue(0)
        except Exception as e:
            self.logger.error(f"重置进度条失败: {e}")
