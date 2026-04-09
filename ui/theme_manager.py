from PyQt6 import QtCore, QtWidgets
from ui.styles import AppStyles


class ThemeManager(QtCore.QObject):
    theme_changed = QtCore.pyqtSignal(str)

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
            from core.config_manager import ConfigManager
            self.config = ConfigManager()
            saved = self.config.load_theme_settings()
            if saved in ('default', '默认主题'):
                saved = 'dark'
            self._current_theme = saved if saved in AppStyles.get_available_themes() else 'dark'
            AppStyles.set_theme(self._current_theme)

    def register_window(self, window: QtWidgets.QWidget):
        if window not in self._windows:
            self._windows.append(window)
            self._apply_theme_to_window(window)

    def unregister_window(self, window: QtWidgets.QWidget):
        if window in self._windows:
            self._windows.remove(window)

    def _update_all_windows(self):
        for window in self._windows:
            self._apply_theme_to_window(window)

    def _apply_theme_to_window(self, window: QtWidgets.QWidget):
        try:
            window.setStyleSheet("")
            if isinstance(window, QtWidgets.QMainWindow):
                window.setStyleSheet(AppStyles.main_window_style())
                self._update_child_widgets(window)
            elif isinstance(window, QtWidgets.QDialog):
                window.setStyleSheet(AppStyles.dialog_style())
                self._update_child_widgets(window)
            window.update()
            QtWidgets.QApplication.processEvents()
        except Exception as e:
            print(f"应用主题到窗口失败: {e}")

    def _update_child_widgets(self, parent: QtWidgets.QWidget):
        try:
            for button in parent.findChildren(QtWidgets.QPushButton):
                if hasattr(button, 'style_type'):
                    if button.style_type == 'apply':
                        button.setStyleSheet(AppStyles.apply_button_style())
                    elif button.style_type == 'cancel':
                        button.setStyleSheet(AppStyles.cancel_button_style())
                    else:
                        button.setStyleSheet(AppStyles.button_style())
                else:
                    button.setStyleSheet(AppStyles.button_style())

            for table in parent.findChildren(QtWidgets.QTableView):
                table.setStyleSheet(AppStyles.list_style())

            for statusbar in parent.findChildren(QtWidgets.QStatusBar):
                statusbar.setStyleSheet(AppStyles.statusbar_style())

            for tab_widget in parent.findChildren(QtWidgets.QTabWidget):
                tab_widget.setStyleSheet(AppStyles.tab_widget_style())

            for tool_button in parent.findChildren(QtWidgets.QToolButton):
                tool_button.setStyleSheet(AppStyles.toolbar_button_style())
        except Exception as e:
            print(f"更新子控件样式失败: {e}")

    def get_current_theme(self) -> str:
        return self._current_theme

    def set_theme(self, theme_name: str):
        if theme_name in AppStyles.get_available_themes():
            self._current_theme = theme_name
            AppStyles.set_theme(theme_name)
            self.config.save_theme_settings(theme_name)
            self._update_all_windows()
            self.theme_changed.emit(theme_name)

    def get_available_themes(self) -> list:
        return AppStyles.get_available_themes()


theme_manager = ThemeManager()


def get_theme_manager() -> ThemeManager:
    return theme_manager
