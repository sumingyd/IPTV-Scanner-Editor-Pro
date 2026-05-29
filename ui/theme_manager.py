from PyQt6 import QtCore, QtWidgets
from ui.styles import AppStyles
from utils.singleton import Singleton


class ThemeManager(Singleton, QtCore.QObject):
    theme_changed = QtCore.pyqtSignal(str)
    color_mode_changed = QtCore.pyqtSignal(str)
    visual_style_changed = QtCore.pyqtSignal(str)

    def __init__(self):
        if self._initialized:
            return
        QtCore.QObject.__init__(self)
        self._windows = []
        from core.config_manager import ConfigManager
        self.config = ConfigManager()
        color_mode, visual_style = self.config.load_theme_settings()
        self._color_mode = color_mode if color_mode in AppStyles.AVAILABLE_COLOR_MODES else 'dark'
        self._visual_style = visual_style if visual_style in AppStyles.AVAILABLE_VISUAL_STYLES else 'flat'
        self._current_theme = f"{self._color_mode}+{self._visual_style}"
        AppStyles.set_color_mode(self._color_mode)
        AppStyles.set_visual_style(self._visual_style)
        self._system_theme_timer = None
        if self._color_mode == 'auto':
            self._start_system_theme_watcher()
        self._initialized = True

    def _start_system_theme_watcher(self):
        if self._system_theme_timer is not None:
            return
        self._system_theme_timer = QtCore.QTimer(self)
        self._system_theme_timer.timeout.connect(self._check_system_theme_change)
        self._system_theme_timer.start(3000)
        self._last_detected_mode = AppStyles._detect_system_color_mode()

    def _stop_system_theme_watcher(self):
        if self._system_theme_timer is not None:
            self._system_theme_timer.stop()
            self._system_theme_timer = None

    def _check_system_theme_change(self):
        if self._color_mode != 'auto':
            return
        detected = AppStyles._detect_system_color_mode()
        if detected != self._last_detected_mode:
            self._last_detected_mode = detected
            self._update_all_windows()
            self.theme_changed.emit(self._current_theme)

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
        w = widget.parent()
        while w:
            if isinstance(w, QtWidgets.QDockWidget):
                return True
            w = w.parent()
        return False

    def _is_in_managed_widget(self, widget):
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
            QtWidgets.QTableWidget: lambda w: AppStyles.list_style(),
            QtWidgets.QListWidget: lambda w: AppStyles.list_style(),
            QtWidgets.QStatusBar: lambda w: AppStyles.statusbar_style(),
            QtWidgets.QTabWidget: lambda w: AppStyles.tab_widget_style(),
            QtWidgets.QToolButton: lambda w: AppStyles.toolbar_button_style(),
            QtWidgets.QLineEdit: lambda w: AppStyles.common_line_edit_style() if (not w.styleSheet() or 'common_line_edit' not in w.styleSheet()) else None,
            QtWidgets.QComboBox: lambda w: AppStyles.common_combo_box_style() if (not w.styleSheet() or 'common_combo' not in w.styleSheet()) else None,
            QtWidgets.QLabel: lambda w: AppStyles.common_label_style() if w.styleSheet() else None,
            QtWidgets.QCheckBox: lambda w: AppStyles.common_check_box_style() if w.styleSheet() else None,
            QtWidgets.QRadioButton: lambda w: AppStyles.common_radio_button_style() if hasattr(AppStyles, 'common_radio_button_style') and w.styleSheet() else None,
            QtWidgets.QProgressBar: lambda w: AppStyles.progress_style() if w.styleSheet() else None,
            QtWidgets.QGroupBox: lambda w: AppStyles.common_group_box_style() if w.styleSheet() else None,
            QtWidgets.QScrollArea: lambda w: AppStyles.scroll_area_style() if hasattr(AppStyles, 'scroll_area_style') and w.styleSheet() else None,
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
                if spin_box.styleSheet() and hasattr(AppStyles, 'common_spin_box_style'):
                    spin_box.setStyleSheet(AppStyles.common_spin_box_style())
                elif hasattr(AppStyles, 'common_spin_box_style'):
                    spin_box.setStyleSheet(AppStyles.common_spin_box_style())
        except Exception:
            pass

    def get_current_theme(self) -> str:
        return self._current_theme

    def get_color_mode(self) -> str:
        return self._color_mode

    def get_visual_style(self) -> str:
        return self._visual_style

    def get_available_color_modes(self) -> list:
        return AppStyles.AVAILABLE_COLOR_MODES

    def get_available_visual_styles(self) -> list:
        return AppStyles.AVAILABLE_VISUAL_STYLES

    def set_color_mode(self, mode: str):
        if mode not in AppStyles.AVAILABLE_COLOR_MODES:
            return
        self._color_mode = mode
        AppStyles.set_color_mode(mode)
        self._current_theme = f"{self._color_mode}+{self._visual_style}"
        self.config.save_theme_settings(self._color_mode, self._visual_style)
        if mode == 'auto':
            self._start_system_theme_watcher()
        else:
            self._stop_system_theme_watcher()
        self._update_all_windows()
        self.color_mode_changed.emit(mode)
        self.theme_changed.emit(self._current_theme)

    def set_visual_style(self, style: str):
        if style not in AppStyles.AVAILABLE_VISUAL_STYLES:
            return
        self._visual_style = style
        AppStyles.set_visual_style(style)
        self._current_theme = f"{self._color_mode}+{self._visual_style}"
        self.config.save_theme_settings(self._color_mode, self._visual_style)
        self._update_all_windows()
        self.visual_style_changed.emit(style)
        self.theme_changed.emit(self._current_theme)

    def set_theme(self, theme_name: str):
        old_themes = {'dark', 'light', 'dark_blue', 'neumorphic_light', 'github_dark'}
        if theme_name in old_themes:
            mapping = AppStyles._OLD_THEME_MAPPING.get(theme_name, ('dark', 'flat'))
            self._color_mode, self._visual_style = mapping
        elif '+' in theme_name:
            parts = theme_name.split('+')
            if len(parts) == 2:
                self._color_mode = parts[0] if parts[0] in AppStyles.AVAILABLE_COLOR_MODES else 'dark'
                self._visual_style = parts[1] if parts[1] in AppStyles.AVAILABLE_VISUAL_STYLES else 'flat'
        else:
            self._color_mode = theme_name if theme_name in AppStyles.AVAILABLE_COLOR_MODES else 'dark'
            self._visual_style = 'flat'
        AppStyles.set_color_mode(self._color_mode)
        AppStyles.set_visual_style(self._visual_style)
        self._current_theme = f"{self._color_mode}+{self._visual_style}"
        self.config.save_theme_settings(self._color_mode, self._visual_style)
        if self._color_mode == 'auto':
            self._start_system_theme_watcher()
        else:
            self._stop_system_theme_watcher()
        self._update_all_windows()
        self.theme_changed.emit(self._current_theme)

    def get_available_themes(self) -> list:
        return AppStyles.get_available_themes()


theme_manager = None


def get_theme_manager() -> ThemeManager:
    global theme_manager
    if theme_manager is None:
        theme_manager = ThemeManager()
    return theme_manager
