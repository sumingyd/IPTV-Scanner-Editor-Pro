from PySide6.QtCore import Qt, Slot
from core.log_manager import global_logger as logger
from core.application_state import app_state


class PanelMixin:
    """从 IPTVPlayer 提取的面板可见性/自动隐藏职责"""

    def toggle_playlist(self, checked=None):
        if self.panel_vis.is_auto_hidden:
            self._auto_restore_panels()
            return
        if checked is None:
            self.playlist_visible = not self.playlist_panel.isVisible()
        else:
            self.playlist_visible = checked
        self._sync_panel_actions()

    def toggle_floating_panel(self, checked=None):
        if self.panel_vis.is_auto_hidden:
            self._auto_restore_panels()
            return
        if checked is None:
            self.floating_panel_visible = not self.floating_panel.isVisible()
        else:
            self.floating_panel_visible = checked
        self._sync_panel_actions()

    def toggle_hide_floating(self, checked=None):
        if self.panel_vis.manually_hidden:
            is_local = self._is_local_file() if hasattr(self, '_is_local_file') else False
            self.panel_vis.restore_from_manual_hide(is_local_file=is_local)
        else:
            if self.panel_vis.is_auto_hidden:
                self.panel_vis._auto_hide_saved = dict(self.panel_vis._auto_hide_saved or {})
                self.panel_vis.set_auto_hide_visible()
            self.panel_vis.hide_all()
        self._sync_panel_actions()

    def _show_floating_panels_on_enter(self):
        if self.panel_vis.manually_hidden:
            return
        if getattr(self, 'is_fullscreen', False):
            return
        if getattr(self, '_pip_mode', False):
            return
        if not self.panel_vis.is_auto_hidden:
            return

        is_local = self._is_local_file() if hasattr(self, '_is_local_file') else False
        self.panel_vis.restore_auto_hide_state(is_local_file=is_local)
        self._sync_panel_actions()
        self._raise_child_dialogs()

    def _delayed_hide_floating_panels(self):
        if self.panel_vis.manually_hidden:
            return
        if getattr(self, 'is_fullscreen', False):
            return
        if getattr(self, '_pip_mode', False):
            return
        if not self.panel_vis.is_auto_hide_visible:
            return
        cursor_pos = self.cursor().pos()
        if self.rect().contains(self.mapFromGlobal(cursor_pos)):
            return
        if hasattr(self, 'epg_panel') and self.epg_panel.isVisible() and self.epg_panel.geometry().contains(cursor_pos):
            return
        if hasattr(self, 'playlist_panel') and self.playlist_panel.isVisible() and self.playlist_panel.geometry().contains(cursor_pos):
            return
        if hasattr(self, 'floating_panel') and self.floating_panel.isVisible() and self.floating_panel.geometry().contains(cursor_pos):
            return

        self.panel_vis.auto_hide_all()
        self._sync_panel_actions()

    def _auto_hide_panels(self):
        if not getattr(self, 'is_fullscreen', False):
            return
        if self.panel_vis.manually_hidden:
            return
        if not self.panel_vis.is_auto_hide_visible:
            return

        self.panel_vis.auto_hide_all()
        self.setCursor(Qt.CursorShape.BlankCursor)
        self._sync_panel_actions()

    def _auto_restore_panels(self):
        if not getattr(self, 'is_fullscreen', False):
            if not self.panel_vis.manually_hidden:
                self._show_floating_panels_on_enter()
            return
        if not self.panel_vis.is_auto_hidden:
            return
        if self.panel_vis.manually_hidden:
            return

        is_local = self._is_local_file() if hasattr(self, '_is_local_file') else False
        self.panel_vis.restore_auto_hide_state(is_local_file=is_local)
        self.unsetCursor()
        self._sync_panel_actions()
        self._restart_auto_hide_timer()
        self._raise_child_dialogs()

    def _restart_auto_hide_timer(self):
        if getattr(self, 'is_fullscreen', False) and not self.panel_vis.manually_hidden:
            if not hasattr(self, '_auto_hide_timer'):
                from PySide6.QtCore import QTimer
                self._auto_hide_timer = QTimer(self)
                self._auto_hide_timer.setSingleShot(True)
                self._auto_hide_timer.setInterval(self.AUTO_HIDE_INTERVAL_MS)
                self._auto_hide_timer.timeout.connect(self._auto_hide_panels)
            if self.panel_vis.is_auto_hide_visible:
                self._auto_hide_timer.start()

    def _stop_auto_hide_timer(self):
        if hasattr(self, '_auto_hide_timer') and self._auto_hide_timer:
            self._auto_hide_timer.stop()

    def _on_mouse_activity(self):
        if getattr(self, 'is_fullscreen', False) and not self.panel_vis.manually_hidden:
            if self.panel_vis.is_auto_hidden:
                self._auto_restore_panels()
            elif self.panel_vis.is_auto_hide_visible:
                self._restart_auto_hide_timer()

    def _sync_panel_actions(self):
        for attr, visible in [
            ('_epg_menu_action', self.epg_visible),
            ('_playlist_menu_action', self.playlist_visible),
            ('_floating_menu_action', self.floating_panel_visible),
            ('_osd_menu_action', self._osd_visible),
            ('_fullscreen_menu_action', getattr(self, 'is_fullscreen', False)),
            ('_pip_menu_action', self.pip_ctrl.is_active if hasattr(self, 'pip_ctrl') else False),
        ]:
            action = getattr(self, attr, None)
            if action:
                action.blockSignals(True)
                action.setChecked(visible)
                action.blockSignals(False)

    def _handle_playlist_subscription(self, need_update, playlist_url, source_index=None):
        self.subscription_ctrl.handle_playlist_subscription(need_update, playlist_url, source_index)

    def start_subscription_timers(self):
        logger.debug("start_subscription_timers: 开始")
        self.subscription_ctrl.start_subscription_timers()
        logger.debug("start_subscription_timers: 完成")

    def reload_subscription(self):
        if self.subscription_ctrl:
            self.subscription_ctrl.reload_subscription()

    def update_playlist_subscription(self, source_index=None):
        self.subscription_ctrl.update_playlist_subscription(source_index)

    @Slot()
    def _do_on_playlist_updated_in_main_thread(self):
        try:
            message = getattr(self, '_pending_update_message', '')
            self._pending_update_message = None
            logger.info(f"_do_on_playlist_updated_in_main_thread: 开始更新UI, CHANNELS数量={app_state.channel_count}")
            if hasattr(self, 'playlist_tab'):
                self.playlist_tab.setCurrentIndex(0)
            try:
                self.populate_channel_list(source='subscription')
            except Exception as ex:
                logger.error(f"populate_channel_list失败: {ex}")
            try:
                self._populate_epg_list()
            except Exception as ex:
                logger.error(f"_populate_epg_list失败: {ex}")
            if hasattr(self, 'update_floating_position'):
                self.update_floating_position()
            self.status_bar.showMessage(message)
            logger.info("_do_on_playlist_updated_in_main_thread: UI更新完成")
        except Exception as ex:
            logger.error(f"在主线程更新UI失败: {ex}")

    @Slot()
    def _do_show_status_bar_message(self):
        msg = getattr(self, '_pending_status_bar_msg', '')
        self._pending_status_bar_msg = None
        self.status_bar_show_message(msg)

    @Slot()
    def _do_on_epg_cache(self):
        self.epg_list_updated.emit()
        self.status_bar_show_message(self.language_manager.tr("epg_using_cache", "Using cached EPG data"))

    @Slot()
    def _do_on_epg_success(self):
        self.epg_list_updated.emit()
        self.status_bar_show_message(self.language_manager.tr("epg_sub_updated", "EPG subscription updated"))

    def raise_floating_panels(self):
        self.update_floating_position()
        if hasattr(self, 'epg_panel') and self.epg_panel and self.epg_visible:
            if not self.epg_panel.isVisible():
                self.epg_panel.show()
        if hasattr(self, 'playlist_panel') and self.playlist_panel and self.playlist_visible:
            if not self.playlist_panel.isVisible():
                self.playlist_panel.show()
        if hasattr(self, 'floating_panel') and self.floating_panel and self.floating_panel_visible:
            if not self.floating_panel.isVisible():
                self.floating_panel.show()
        self._raise_child_dialogs()

    def _reapply_side_panel_styles(self):
        self.ui_ctrl._reapply_side_panel_styles()

    def _reapply_floating_panel_styles(self):
        self.ui_ctrl._reapply_floating_panel_styles()