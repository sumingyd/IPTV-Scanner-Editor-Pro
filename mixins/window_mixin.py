from PySide6.QtWidgets import QDialog

from core.log_manager import global_logger as logger
from ui.styles import AppStyles
from utils.platform_utils import is_wayland, wayland_move, wayland_set_geometry


class WindowMixin:
    """从 IPTVPlayer 提取的窗口事件/定位/全屏/覆盖层职责"""

    def eventFilter(self, obj, event):
        return self.event_handler.eventFilter(obj, event)

    def update_floating_position(self):
        if not hasattr(self, 'video_frame') or self.video_frame is None:
            return

        if hasattr(self, 'video_widget') and self.video_widget:
            self.video_widget.setGeometry(0, 0, self.video_frame.width(), self.video_frame.height())

        if hasattr(self, 'video_placeholder') and self.video_placeholder:
            self.video_placeholder.setGeometry(0, 0, self.video_frame.width(), self.video_frame.height())

        self._update_video_overlay_position()

    def _raise_overlay_above_video(self):
        if not hasattr(self, '_video_overlay_label') or not self._video_overlay_label:
            return
        self._video_overlay_label.raise_()
        from utils.platform_utils import is_windows
        if is_windows():
            try:
                hwnd = int(self._video_overlay_label.winId())
                import ctypes
                SWP_NOMOVE = 0x0002
                SWP_NOSIZE = 0x0001
                SWP_NOACTIVATE = 0x0010
                SWP_SHOWWINDOW = 0x0040
                ctypes.windll.user32.SetWindowPos(
                    hwnd, -1, 0, 0, 0, 0,
                    SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW
                )
                ctypes.windll.user32.SetWindowPos(
                    hwnd, -2, 0, 0, 0, 0,
                    SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW
                )
            except Exception:
                pass

    def _update_video_overlay_position(self):
        if not hasattr(self, '_video_overlay_label') or not self._video_overlay_label:
            return
        if not hasattr(self, 'video_frame') or not self.video_frame:
            return
        self._video_overlay_label.adjustSize()
        w = self._video_overlay_label.width()
        h = self._video_overlay_label.height()
        fw = self.video_frame.width()
        fh = self.video_frame.height()
        self._video_overlay_label.setGeometry(12, fh - h - 12, w, h)
        if self._video_overlay_label.isVisible():
            self._raise_overlay_above_video()

        self._position_floating_docks()

    def _position_floating_docks(self):
        import time
        now = time.time()
        if hasattr(self, '_last_position_time') and now - self._last_position_time < 0.05:
            return
        self._last_position_time = now
        if hasattr(self, '_main_container') and self._main_container.layout():
            self._main_container.layout().activate()

        if is_wayland():
            return

        mw = self.geometry()
        if mw.isEmpty():
            return

        mw_x, mw_y, mw_w, mw_h = mw.x(), mw.y(), mw.width(), mw.height()

        gap = 8
        title_bar_h = 32
        menu_bar_h = 28 if (hasattr(self, '_custom_menu_bar') and self._custom_menu_bar and self._custom_menu_bar.isVisible()) else 0
        floating_dock = self.floating_dock
        if floating_dock:
            if floating_dock.isVisible():
                control_panel_h = floating_dock.height()
                self._last_control_panel_h = control_panel_h
            else:
                control_panel_h = getattr(self, '_last_control_panel_h', floating_dock.height() or 170)
        else:
            control_panel_h = 170
        status_bar_h = 25

        side_top = mw_y + title_bar_h + menu_bar_h + gap
        side_h = mw_h - title_bar_h - menu_bar_h - control_panel_h - status_bar_h - gap * 2

        if hasattr(self, 'epg_dock') and self.epg_dock:
            if not hasattr(self, '_epg_dock_w') or self._epg_dock_w <= 0:
                self._epg_dock_w = self.epg_dock.width()
            wayland_move(self.epg_dock, mw_x + gap, side_top)
            self.epg_dock.setMinimumHeight(max(150, side_h))
            self.epg_dock.setMaximumHeight(max(150, side_h))
            self.epg_dock.setFixedWidth(self._epg_dock_w)

        if hasattr(self, 'playlist_dock') and self.playlist_dock:
            if not hasattr(self, '_playlist_dock_w') or self._playlist_dock_w <= 0:
                self._playlist_dock_w = self.playlist_dock.width()
            pl_w = self._playlist_dock_w
            wayland_move(self.playlist_dock, mw_x + mw_w - pl_w - gap, side_top)
            self.playlist_dock.setMinimumHeight(max(150, side_h))
            self.playlist_dock.setMaximumHeight(max(150, side_h))
            self.playlist_dock.setFixedWidth(pl_w)

        if hasattr(self, 'floating_dock') and self.floating_dock:
            fl_w = min(mw_w - gap * 2, 1050)
            self.floating_dock.setMinimumWidth(max(fl_w, 360))
            fl_x = mw_x + (mw_w - self.floating_dock.width()) // 2
            fl_y = mw_y + mw_h - control_panel_h - status_bar_h - gap
            wayland_move(self.floating_dock, fl_x, fl_y)

    def toggle_fullscreen(self, checked=None):
        if checked is not None and self.fullscreen_button.isCheckable():
            want_fullscreen = bool(checked)
        else:
            want_fullscreen = not self.is_fullscreen

        if want_fullscreen == self.is_fullscreen:
            logger.debug(f"toggle_fullscreen跳过: checked={checked}, is_fullscreen={self.is_fullscreen}, btn_checkable={self.fullscreen_button.isCheckable()}")
            return

        self.is_fullscreen = want_fullscreen

        if self.is_fullscreen:
            self._before_fullscreen_geo = self.geometry()
            logger.debug(f"进入全屏: 保存geometry={self._before_fullscreen_geo.getRect()}, screen={self.screen().geometry().getRect() if self.screen() else None}")
            self.panel_vis.set_auto_hide_visible()
            self.panel_vis.save_context('fullscreen')
            if hasattr(self, '_title_bar') and self._title_bar:
                self._title_bar.hide()
            if hasattr(self, '_custom_menu_bar') and self._custom_menu_bar:
                self._custom_menu_bar.hide()
            if self.status_bar:
                self.status_bar.hide()
            self.showFullScreen()
            screen = self.screen()
            if screen:
                geo = screen.geometry()
                wayland_set_geometry(self, geo.x(), geo.y(), geo.width(), geo.height())
            logger.debug(f"进入全屏后: geometry={self.geometry().getRect()}, isFullScreen={self.isFullScreen()}")
            self.unsetCursor()
            is_local = self._is_local_file() if hasattr(self, '_is_local_file') else False
            self.panel_vis.set_all_visible(is_local_file=is_local)
            self._sync_panel_actions()
            self._restart_auto_hide_timer()
        else:
            self._stop_auto_hide_timer()
            self.unsetCursor()
            saved = self.panel_vis.restore_context('fullscreen')
            logger.debug(f"退出全屏: showNormal前geometry={self.geometry().getRect()}, isFullScreen={self.isFullScreen()}, saved_geo={getattr(self, '_before_fullscreen_geo', None)}")
            self.showNormal()
            saved_geo = getattr(self, '_before_fullscreen_geo', None)
            if saved_geo:
                wayland_set_geometry(self, saved_geo.x(), saved_geo.y(), saved_geo.width(), saved_geo.height())
            logger.debug(f"退出全屏后: geometry={self.geometry().getRect()}, isFullScreen={self.isFullScreen()}")
            if saved:
                if saved.get('title_bar', True) and hasattr(self, '_title_bar') and self._title_bar:
                    self._title_bar.show()
                if saved.get('menu_bar', True) and hasattr(self, '_custom_menu_bar') and self._custom_menu_bar:
                    self._custom_menu_bar.show()
                if saved.get('status_bar', True) and self.status_bar:
                    self.status_bar.show()
            self.panel_vis.set_auto_hide_visible()
            self._sync_panel_actions()
            self.update_floating_position()

    def refresh_ui(self):
        self.populate_channel_list(source='auto')
        self.populate_epg_list()

    def reset_layout(self):
        self.panel_vis.reset()
        self._sync_panel_actions()
        self.resize(1280, 806)

    def open_scan_ui(self):
        try:
            from ui.dialogs.scan_channel_dialog import ScanChannelDialog
            from PySide6.QtCore import Qt

            dialog = ScanChannelDialog(self)
            self._scan_dialog = dialog

            dialog.show()

            logger.info("成功打开扫描界面")
        except Exception as ex:
            logger.error(f"打开扫描界面失败: {str(ex)}")

    def _raise_floating_panels(self):
        self.raise_()
        self.update_floating_position()
        for panel_attr in ['epg_panel', 'playlist_panel', 'floating_panel']:
            panel = getattr(self, panel_attr, None)
            if panel and panel.isVisible():
                panel.show()
        self._raise_child_dialogs()

    def _raise_child_dialogs(self):
        for dialog in self.findChildren(QDialog):
            if dialog.isVisible() and not dialog.isModal():
                dialog.raise_()

    def open_channel_mapping(self):
        try:
            from ui.dialogs.mapping_manager_dialog import MappingManagerDialog
            from PySide6.QtCore import Qt

            dialog = MappingManagerDialog(self)
            dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
            dialog.exec()

            logger.info("成功打开频道映射管理器")
        except Exception as ex:
            logger.error(f"打开频道映射管理器失败: {str(ex)}")

    def _center_dialog_on_screen(self, dialog):
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app:
            screen = app.primaryScreen()
            if screen:
                screen_geometry = screen.availableGeometry()
                dialog.adjustSize()
                dialog_size = dialog.size()
                x = (screen_geometry.width() - dialog_size.width()) // 2 + screen_geometry.x()
                y = (screen_geometry.height() - dialog_size.height()) // 2 + screen_geometry.y()
                wayland_move(dialog, x, y)

    def showEvent(self, event):
        if hasattr(self, 'event_handler') and self.event_handler:
            self.event_handler.showEvent(event)
        else:
            super().showEvent(event)
        self._fix_win32_drag_drop()

    def changeEvent(self, event):
        if hasattr(self, 'event_handler') and self.event_handler:
            self.event_handler.changeEvent(event)
        else:
            super().changeEvent(event)

    def moveEvent(self, event):
        if hasattr(self, 'event_handler') and self.event_handler:
            self.event_handler.moveEvent(event)
        else:
            super().moveEvent(event)

    def resizeEvent(self, event):
        if hasattr(self, 'event_handler') and self.event_handler:
            self.event_handler.resizeEvent(event)
        else:
            super().resizeEvent(event)

    def closeEvent(self, event):
        if getattr(self, '_is_hidden_to_tray', False):
            if hasattr(self, 'event_handler') and self.event_handler:
                self.event_handler.closeEvent(event)
            else:
                super().closeEvent(event)
            return

        if getattr(self, '_force_quit', False):
            self._force_quit = False
            try:
                from server.app import stop_server
                stop_server()
            except Exception:
                pass
            if hasattr(self, 'event_handler') and self.event_handler:
                self.event_handler.closeEvent(event)
            else:
                super().closeEvent(event)
            return

        config = self.config or self.config_manager
        if config:
            close_action = config.load_close_behavior()
            if close_action == 'minimize_tray':
                event.ignore()
                self._do_close_minimize_tray()
                return
            elif close_action == 'exit':
                try:
                    stop_server()
                except Exception:
                    pass
                if hasattr(self, 'event_handler') and self.event_handler:
                    self.event_handler.closeEvent(event)
                else:
                    super().closeEvent(event)
                return

        from PySide6.QtWidgets import QMessageBox, QCheckBox
        tr = self.language_manager.tr
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle(tr('close_confirm_title', '关闭确认'))
        msg_box.setText(tr('close_confirm_text', '关闭后将无法接收节目提醒，是否最小化到系统托盘继续运行提醒功能？'))
        msg_box.setIcon(QMessageBox.Icon.Question)
        min_btn = msg_box.addButton(tr('close_minimize_tray', '最小化到托盘'), QMessageBox.ButtonRole.YesRole)
        close_btn = msg_box.addButton(tr('close_exit', '直接退出'), QMessageBox.ButtonRole.NoRole)
        cancel_btn = msg_box.addButton(tr('cancel', '取消'), QMessageBox.ButtonRole.RejectRole)
        msg_box.setDefaultButton(min_btn)

        remember_cb = QCheckBox(tr('close_remember_choice', '记住选择，不再询问'))
        msg_box.setCheckBox(remember_cb)

        msg_box.setStyleSheet(AppStyles.close_confirm_dialog_style())
        msg_box.exec()
        clicked = msg_box.clickedButton()
        if clicked == cancel_btn or clicked is None:
            event.ignore()
            return

        remember = remember_cb.isChecked()
        if clicked == min_btn:
            if remember and config:
                config.save_close_behavior('minimize_tray')
            event.ignore()
            self._do_close_minimize_tray()
            return
        if remember and config:
            config.save_close_behavior('exit')
        if hasattr(self, 'event_handler') and self.event_handler:
            self.event_handler.closeEvent(event)
        else:
            super().closeEvent(event)