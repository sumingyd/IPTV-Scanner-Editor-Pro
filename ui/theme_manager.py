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
                if hasattr(window, 'reapply_styles'):
                    window.reapply_styles()
            window.update()
            QtWidgets.QApplication.processEvents()
        except Exception as e:
            print(f"应用主题到窗口失败: {e}")

    def _is_in_dock(self, widget):
        """检查控件是否在QDockWidget内部（dock内控件有独立的样式管理）"""
        w = widget.parent()
        while w:
            if isinstance(w, QtWidgets.QDockWidget):
                return True
            w = w.parent()
        return False

    def _update_child_widgets(self, parent: QtWidgets.QWidget):
        try:
            for button in parent.findChildren(QtWidgets.QPushButton):
                if self._is_in_dock(button):
                    continue
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
                if self._is_in_dock(tool_button):
                    continue
                tool_button.setStyleSheet(AppStyles.toolbar_button_style())

            for line_edit in parent.findChildren(QtWidgets.QLineEdit):
                if not line_edit.styleSheet() or 'common_line_edit' not in line_edit.styleSheet():
                    line_edit.setStyleSheet(AppStyles.common_line_edit_style())

            for combo_box in parent.findChildren(QtWidgets.QComboBox):
                if not combo_box.styleSheet() or 'common_combo' not in combo_box.styleSheet():
                    combo_box.setStyleSheet(AppStyles.common_combo_box_style())

            for label in parent.findChildren(QtWidgets.QLabel):
                if not label.styleSheet():
                    label.setStyleSheet(AppStyles.common_label_style())

            for check_box in parent.findChildren(QtWidgets.QCheckBox):
                if not check_box.styleSheet():
                    check_box.setStyleSheet(AppStyles.common_check_box_style())

            for progress_bar in parent.findChildren(QtWidgets.QProgressBar):
                if not progress_bar.styleSheet():
                    progress_bar.setStyleSheet(AppStyles.progress_style())

            for group_box in parent.findChildren(QtWidgets.QGroupBox):
                if not group_box.styleSheet():
                    group_box.setStyleSheet(AppStyles.common_group_box_style())

            for spin_box in parent.findChildren(QtWidgets.QSpinBox):
                if not spin_box.styleSheet():
                    spin_box.setStyleSheet(AppStyles.common_spin_box_style()) if hasattr(AppStyles, 'common_spin_box_style') else None

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
