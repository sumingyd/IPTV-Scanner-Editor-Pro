from PyQt6 import QtCore, QtWidgets
from ui.styles import AppStyles
from utils.singleton import Singleton


class ThemeManager(Singleton, QtCore.QObject):
    theme_changed = QtCore.pyqtSignal(str)

    def __init__(self):
        if self._initialized:
            return
        QtCore.QObject.__init__(self)
        self._windows = []
        from core.config_manager import ConfigManager
        self.config = ConfigManager()
        saved = self.config.load_theme_settings()
        if saved in ('default', '默认主题'):
            saved = 'dark'
        self._current_theme = saved if saved in AppStyles.get_available_themes() else 'dark'
        AppStyles.set_theme(self._current_theme)
        self._initialized = True

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

    def _is_in_managed_widget(self, widget):
        """检查控件是否在有独立样式管理的容器内（标题栏、菜单栏、dock）"""
        w = widget.parent()
        while w:
            if isinstance(w, QtWidgets.QDockWidget):
                return True
            if isinstance(w, QtWidgets.QMenuBar):
                return True
            if isinstance(w, QtWidgets.QWidget) and w.objectName() == "titleBar":
                return True
            w = w.parent()
        return False

    def _update_child_widgets(self, parent: QtWidgets.QWidget):
        style_map = {
            QtWidgets.QPushButton: lambda w: AppStyles.button_style() if not hasattr(w, 'style_type') else (
                AppStyles.apply_button_style() if w.style_type == 'apply' else
                AppStyles.cancel_button_style() if w.style_type == 'cancel' else
                AppStyles.button_style()
            ),
            QtWidgets.QTableView: lambda w: AppStyles.list_style(),
            QtWidgets.QStatusBar: lambda w: AppStyles.statusbar_style(),
            QtWidgets.QTabWidget: lambda w: AppStyles.tab_widget_style(),
            QtWidgets.QToolButton: lambda w: AppStyles.toolbar_button_style(),
            QtWidgets.QLineEdit: lambda w: AppStyles.common_line_edit_style() if (not w.styleSheet() or 'common_line_edit' not in w.styleSheet()) else None,
            QtWidgets.QComboBox: lambda w: AppStyles.common_combo_box_style() if (not w.styleSheet() or 'common_combo' not in w.styleSheet()) else None,
            QtWidgets.QLabel: lambda w: AppStyles.common_label_style() if not w.styleSheet() else None,
            QtWidgets.QCheckBox: lambda w: AppStyles.common_check_box_style() if not w.styleSheet() else None,
            QtWidgets.QProgressBar: lambda w: AppStyles.progress_style() if not w.styleSheet() else None,
            QtWidgets.QGroupBox: lambda w: AppStyles.common_group_box_style() if not w.styleSheet() else None,
        }
        for widget_type, style_func in style_map.items():
            try:
                for widget in parent.findChildren(widget_type):
                    if self._is_in_managed_widget(widget):
                        continue
                    style = style_func(widget)
                    if style:
                        widget.setStyleSheet(style)
            except Exception:
                pass
        try:
            for spin_box in parent.findChildren(QtWidgets.QSpinBox):
                if not spin_box.styleSheet() and hasattr(AppStyles, 'common_spin_box_style'):
                    spin_box.setStyleSheet(AppStyles.common_spin_box_style())
        except Exception:
            pass

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
