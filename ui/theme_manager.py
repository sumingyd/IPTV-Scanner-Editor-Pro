"""
主题管理器 - 负责管理应用程序的主题切换
"""

from PyQt6 import QtCore, QtWidgets, QtGui
from ui.styles import AppStyles


class ThemeManager(QtCore.QObject):
    """主题管理器，管理应用程序的主题切换"""

    # 主题变化信号
    theme_changed = QtCore.pyqtSignal(str)

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
            # 加载主题设置
            from core.config_manager import ConfigManager
            self.config = ConfigManager()
            theme_name = self.config.load_theme_settings()
            # 如果加载到的是 "default"，转换为 "默认主题"
            if theme_name == "default":
                theme_name = "默认主题"
            self._current_theme = theme_name
            self._themes = self._load_available_themes()

    def _load_available_themes(self) -> list:
        """加载可用的主题列表"""
        # 从 AppStyles.get_theme_styles() 获取主题列表
        # 目前只支持默认主题
        return ["默认主题"]

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
        return self._current_theme

    def set_theme(self, theme_name: str):
        """设置主题"""
        if theme_name in self._themes:
            self._current_theme = theme_name
            # 保存主题设置
            self.config.save_theme_settings(theme_name)
            self._update_all_windows()
            self.theme_changed.emit(theme_name)

    def get_available_themes(self) -> list:
        """获取可用的主题列表"""
        return self._themes


# 全局主题管理器实例
theme_manager = ThemeManager()


def get_theme_manager() -> ThemeManager:
    """获取主题管理器实例"""
    return theme_manager
