import sys

from core.log_manager import global_logger as logger


class EventMixin:
    """从 IPTVPlayer 提取的Qt事件覆写和拖放修复职责"""

    def mousePressEvent(self, event):
        """鼠标按下事件"""
        if getattr(self, 'is_fullscreen', False):
            self._on_mouse_activity()
        if self.pip_mode:
            if self.pip_ctrl.handle_mouse_press(event):
                return
        if not self.window_ctrl.handle_mouse_press_event(event):
            self.update_floating_position()
            super().mousePressEvent(event)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                path = url.toLocalFile()
                if path.lower().endswith(self.ALL_DROP_EXTENSIONS):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if not path:
                continue
            if path.lower().endswith(self.PLAYLIST_EXTENSIONS):
                if hasattr(self, 'settings_ops'):
                    self.settings_ops.open_specific_file(path)
                event.acceptProposedAction()
                return
            elif path.lower().endswith(self.VIDEO_EXTENSIONS):
                self._add_local_video_and_track(path)
                logger.info(f"拖放打开视频文件: {path}")
                event.acceptProposedAction()
                return
        event.ignore()

    def _fix_win32_drag_drop(self):
        """修复 Win32 无边框窗口拖放失效问题

        Qt6 的 FramelessWindowHint + WA_TranslucentBackground 会导致
        Windows OLE 拖放目标未注册，需要在窗口显示后手动初始化 OLE 并重新注册。
        """
        if sys.platform != 'win32':
            return
        try:
            import ctypes
            from ctypes import wintypes
            ole32 = ctypes.windll.ole32
            ole32.OleInitialize(None)
            hwnd = int(self.winId())
            user32 = ctypes.windll.user32
            user32.DragAcceptFiles(hwnd, True)
        except Exception:
            pass

    def mouseMoveEvent(self, event):
        """鼠标移动事件"""
        if getattr(self, 'is_fullscreen', False):
            self._on_mouse_activity()
        if self.pip_mode:
            if self.pip_ctrl.handle_mouse_move(event):
                return
        if not self.window_ctrl.handle_mouse_move_event(event):
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """鼠标释放事件"""
        if self.pip_mode:
            if self.pip_ctrl.handle_mouse_release(event):
                return
        self.window_ctrl.handle_mouse_release_event(event)
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        """鼠标双击事件 - 视频区域双击切换全屏，标题栏双击最大化"""
        if self.pip_mode:
            return
        if not self.window_ctrl.handle_mouse_double_click_event(event):
            if hasattr(self, 'video_widget') and self.video_widget:
                gpos = event.globalPosition().toPoint()
                vw_geo = self.video_widget.geometry()
                vw_global = self.video_widget.mapToGlobal(vw_geo.topLeft())
                if (vw_global.x() <= gpos.x() <= vw_global.x() + vw_geo.width() and
                        vw_global.y() <= gpos.y() <= vw_global.y() + vw_geo.height()):
                    self.toggle_fullscreen()
                    event.accept()
                    return
            super().mouseDoubleClickEvent(event)

    def wheelEvent(self, event):
        """滚轮事件 - 调节音量"""
        if self.pip_mode:
            return
        if getattr(self, 'is_fullscreen', False):
            self._on_mouse_activity()
        delta = event.angleDelta().y()
        if delta != 0 and hasattr(self, 'event_handler'):
            step = 5
            self.event_handler._adjust_volume(step if delta > 0 else -step)

    def enterEvent(self, event):
        """鼠标进入窗口"""
        if self.pip_mode:
            self.pip_ctrl.show_overlay()
        elif not getattr(self, '_floating_hidden', False) and not getattr(self, 'is_fullscreen', False):
            self._show_floating_panels_on_enter()
        super().enterEvent(event)

    def leaveEvent(self, event):
        """鼠标离开窗口"""
        from PySide6.QtCore import QTimer
        if self.pip_mode:
            QTimer.singleShot(50, self.pip_ctrl.delayed_hide_overlay)
        elif not getattr(self, '_floating_hidden', False) and not getattr(self, 'is_fullscreen', False):
            QTimer.singleShot(50, self._delayed_hide_floating_panels)
        super().leaveEvent(event)