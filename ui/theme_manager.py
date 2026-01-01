"""
主题管理器 - 负责监听系统主题变化并更新界面样式
"""

from PyQt6 import QtCore, QtWidgets, QtGui
from ui.styles import AppStyles


class ThemeManager(QtCore.QObject):
    """主题管理器，监听系统主题变化并更新界面样式"""
    
    # 单例实例
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        super().__init__()
        if not hasattr(self, '_initialized'):
            self._initialized = True
            self._windows = []
            self._is_dark_mode = self._detect_system_theme()
            self._setup_theme_listener()
    
    def _detect_system_theme(self) -> bool:
        """检测当前系统主题是否为深色模式"""
        try:
            # 获取系统调色板
            palette = QtGui.QGuiApplication.palette()
            # 计算窗口背景亮度
            bg_color = palette.color(QtGui.QPalette.ColorRole.Window)
            # 如果亮度小于128，认为是深色模式
            return bg_color.lightness() < 128
        except Exception:
            # 默认返回浅色模式
            return False
    
    def _setup_theme_listener(self):
        """设置主题变化监听器"""
        # 在Windows上，我们可以使用定时器定期检查主题变化
        # 因为Qt没有直接提供系统主题变化信号
        self._theme_check_timer = QtCore.QTimer()
        self._theme_check_timer.timeout.connect(self._check_theme_change)
        self._theme_check_timer.start(1000)  # 每秒检查一次
    
    def _check_theme_change(self):
        """检查系统主题是否发生变化"""
        current_dark_mode = self._detect_system_theme()
        if current_dark_mode != self._is_dark_mode:
            self._is_dark_mode = current_dark_mode
            self._update_all_windows()
    
    def register_window(self, window: QtWidgets.QWidget):
        """注册窗口，使其能够接收主题变化更新"""
        if window not in self._windows:
            self._windows.append(window)
            # 立即应用当前主题
            self._apply_theme_to_window(window)
    
    def unregister_window(self, window: QtWidgets.QWidget):
        """取消注册窗口"""
        if window in self._windows:
            self._windows.remove(window)
    
    def _update_all_windows(self):
        """更新所有注册的窗口"""
        for window in self._windows:
            self._apply_theme_to_window(window)
    
    def _apply_theme_to_window(self, window: QtWidgets.QWidget):
        """应用主题到指定窗口"""
        try:
            # 重新设置窗口样式
            window.setStyleSheet("")
            
            # 根据窗口类型应用不同的样式
            if isinstance(window, QtWidgets.QMainWindow):
                # 主窗口样式
                window.setStyleSheet(AppStyles.main_window_style())
                
                # 查找并更新子控件
                self._update_child_widgets(window)
                
            elif isinstance(window, QtWidgets.QDialog):
                # 对话框样式
                window.setStyleSheet(AppStyles.dialog_style())
                
                # 查找并更新子控件
                self._update_child_widgets(window)
            
            # 强制刷新窗口
            window.update()
            QtWidgets.QApplication.processEvents()
            
        except Exception as e:
            print(f"应用主题到窗口失败: {e}")
    
    def _update_child_widgets(self, parent: QtWidgets.QWidget):
        """更新子控件的样式"""
        try:
            # 更新按钮样式
            buttons = parent.findChildren(QtWidgets.QPushButton)
            for button in buttons:
                # 检查按钮是否有特殊样式
                if hasattr(button, 'style_type'):
                    if button.style_type == 'apply':
                        button.setStyleSheet(AppStyles.apply_button_style())
                    elif button.style_type == 'cancel':
                        button.setStyleSheet(AppStyles.cancel_button_style())
                    else:
                        button.setStyleSheet(AppStyles.button_style())
                else:
                    button.setStyleSheet(AppStyles.button_style())
            
            # 更新列表样式
            tables = parent.findChildren(QtWidgets.QTableView)
            for table in tables:
                table.setStyleSheet(AppStyles.list_style())
            
            # 更新状态栏样式
            statusbars = parent.findChildren(QtWidgets.QStatusBar)
            for statusbar in statusbars:
                statusbar.setStyleSheet(AppStyles.statusbar_style())
            
            # 更新标签页样式
            tab_widgets = parent.findChildren(QtWidgets.QTabWidget)
            for tab_widget in tab_widgets:
                tab_widget.setStyleSheet(AppStyles.tab_widget_style())
            
            # 更新工具栏按钮样式
            tool_buttons = parent.findChildren(QtWidgets.QToolButton)
            for tool_button in tool_buttons:
                tool_button.setStyleSheet(AppStyles.toolbar_button_style())
            
        except Exception as e:
            print(f"更新子控件样式失败: {e}")
    
    def get_current_theme(self) -> str:
        """获取当前主题名称"""
        return "dark" if self._is_dark_mode else "light"
    
    def is_dark_mode(self) -> bool:
        """检查当前是否为深色模式"""
        return self._is_dark_mode


# 全局主题管理器实例
theme_manager = ThemeManager()


def get_theme_manager() -> ThemeManager:
    """获取主题管理器实例"""
    return theme_manager
