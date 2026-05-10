"""
事件处理器 - 负责键盘快捷键、事件过滤、窗口事件等
从 pyqt_player.py 提取的独立模块
"""

from typing import Optional
from PyQt6.QtCore import Qt, QEvent, QTimer
from PyQt6.QtGui import QKeyEvent


class EventHandler:
    """事件处理器 - 统一管理所有事件处理逻辑"""

    def __init__(self, main_window):
        self.window = main_window
        self._shortcuts = {}  # 快捷键映射表

    def keyPressEvent(self, event: QKeyEvent) -> bool:
        """已废弃：所有快捷键统一由 eventFilter 处理，此方法保留为空"""
        return False

    def _is_main_window_focused(self) -> bool:
        """判断当前焦点是否在主窗口上（排除悬浮面板、对话框等）"""
        from PyQt6.QtWidgets import QApplication
        focus_widget = QApplication.focusWidget()
        if focus_widget is None:
            return self.window.isActiveWindow()
        window = focus_widget.window()
        return window is self.window

    def eventFilter(self, obj, event: QEvent) -> bool:
        """事件过滤器 - 在 app 级别统一处理所有快捷键（不受焦点影响）"""
        event_type = event.type()

        if event_type == QEvent.Type.ShortcutOverride:
            key = event.key()
            modifiers = event.modifiers()
            if self._is_handled_shortcut(key, modifiers):
                event.accept()
                return True

        if event_type == QEvent.Type.KeyPress:
            key = event.key()
            modifiers = event.modifiers()
            handled = self._handle_global_shortcut(key, modifiers)
            if handled:
                return True

        if getattr(self.window, 'is_fullscreen', False) and not getattr(self.window, '_floating_hidden', False):
            if obj is getattr(self.window, 'video_widget', None):
                if event_type in (QEvent.Type.MouseMove, QEvent.Type.MouseButtonPress, QEvent.Type.Wheel):
                    if hasattr(self.window, '_on_mouse_activity'):
                        self.window._on_mouse_activity()

        if not getattr(self.window, '_pip_mode', False) and not getattr(self.window, 'is_fullscreen', False) and not getattr(self.window, '_floating_hidden', False):
            if obj is getattr(self.window, 'video_widget', None):
                if event_type == QEvent.Type.Leave:
                    if hasattr(self.window, '_delayed_hide_floating_panels'):
                        from PyQt6.QtCore import QTimer
                        QTimer.singleShot(50, self.window._delayed_hide_floating_panels)
                elif event_type == QEvent.Type.Enter:
                    if hasattr(self.window, '_show_floating_panels_on_enter'):
                        self.window._show_floating_panels_on_enter()

        return False

    def _is_handled_shortcut(self, key, modifiers) -> bool:
        """判断按键组合是否由 eventFilter 统一处理（用于拦截 ShortcutOverride）"""
        if modifiers == Qt.KeyboardModifier.NoModifier:
            global_keys = (Qt.Key.Key_Space, Qt.Key.Key_Escape,
                           Qt.Key.Key_F, Qt.Key.Key_E,
                           Qt.Key.Key_L, Qt.Key.Key_M,
                           Qt.Key.Key_Y, Qt.Key.Key_Tab,
                           Qt.Key.Key_F5, Qt.Key.Key_F11,
                           Qt.Key.Key_Backspace, Qt.Key.Key_S,
                           Qt.Key.Key_Period, Qt.Key.Key_Comma,
                           Qt.Key.Key_P)
            main_only_keys = (Qt.Key.Key_Up, Qt.Key.Key_Down,
                              Qt.Key.Key_Left, Qt.Key.Key_Right)
            if key in global_keys:
                return True
            if key in main_only_keys and self._is_main_window_focused():
                return True
            return False
        elif modifiers == Qt.KeyboardModifier.ControlModifier:
            return key in (Qt.Key.Key_O, Qt.Key.Key_S, Qt.Key.Key_Q,
                           Qt.Key.Key_U)
        elif modifiers == (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier):
            if key == Qt.Key.Key_O:
                return True
            if key in (Qt.Key.Key_Left, Qt.Key.Key_Right) and self._is_main_window_focused():
                return True
            return False
        return False

    def _handle_global_shortcut(self, key, modifiers) -> bool:
        """统一快捷键分发（所有快捷键在此处理，保证可靠触发）"""
        from core.log_manager import global_logger as logger
        try:
            w = self.window

            if modifiers == Qt.KeyboardModifier.NoModifier:
                if key == Qt.Key.Key_Space:
                    if hasattr(w, 'playback_ctrl'):
                        w.playback_ctrl.toggle_play()
                    return True
                elif key == Qt.Key.Key_Escape:
                    if hasattr(w, 'isFullScreen') and w.isFullScreen():
                        w.toggle_fullscreen()
                    elif hasattr(w, 'playback_ctrl'):
                        w.playback_ctrl.stop_playback()
                    return True
                elif key in (Qt.Key.Key_Up, Qt.Key.Key_Down,
                             Qt.Key.Key_Left, Qt.Key.Key_Right):
                    if not self._is_main_window_focused():
                        return False
                    if key == Qt.Key.Key_Up:
                        self._switch_channel(-1)
                    elif key == Qt.Key.Key_Down:
                        self._switch_channel(1)
                    elif key == Qt.Key.Key_Left:
                        self._adjust_volume(-5)
                    elif key == Qt.Key.Key_Right:
                        self._adjust_volume(5)
                    return True
                elif key == Qt.Key.Key_F:
                    if hasattr(w, 'toggle_fullscreen'):
                        w.toggle_fullscreen()
                    return True
                elif key == Qt.Key.Key_E:
                    if hasattr(w, 'toggle_epg'):
                        w.toggle_epg(None)
                    return True
                elif key == Qt.Key.Key_L:
                    if hasattr(w, 'toggle_playlist'):
                        w.toggle_playlist(None)
                    return True
                elif key == Qt.Key.Key_M:
                    if hasattr(w, 'toggle_floating_panel'):
                        w.toggle_floating_panel(None)
                    return True
                elif key == Qt.Key.Key_Y:
                    if hasattr(w, 'toggle_hide_floating'):
                        logger.debug("eventFilter: Y key pressed, calling toggle_hide_floating")
                        w.toggle_hide_floating(None)
                    return True
                elif key == Qt.Key.Key_Tab:
                    if hasattr(w, 'toggle_osd'):
                        w.toggle_osd(None)
                    return True
                elif key == Qt.Key.Key_F5:
                    if hasattr(w, 'refresh_ui'):
                        w.refresh_ui()
                    return True
                elif key == Qt.Key.Key_F11:
                    if hasattr(w, 'toggle_fullscreen'):
                        w.toggle_fullscreen()
                    return True
                elif key == Qt.Key.Key_Backspace:
                    if hasattr(w, 'switch_to_previous_channel'):
                        w.switch_to_previous_channel()
                    return True
                elif key == Qt.Key.Key_S:
                    if hasattr(w, '_take_screenshot'):
                        w._take_screenshot()
                    return True
                elif key == Qt.Key.Key_Period:
                    if hasattr(w, '_adjust_speed'):
                        w._adjust_speed(0.1)
                    return True
                elif key == Qt.Key.Key_Comma:
                    if hasattr(w, '_adjust_speed'):
                        w._adjust_speed(-0.1)
                    return True
                elif key == Qt.Key.Key_P:
                    if hasattr(w, 'toggle_pip_mode'):
                        w.toggle_pip_mode()
                    return True

            elif modifiers == Qt.KeyboardModifier.ControlModifier:
                if key == Qt.Key.Key_O:
                    if hasattr(w, 'settings_ops'):
                        w.settings_ops.open_playlist()
                    return True
                elif key == Qt.Key.Key_S:
                    if hasattr(w, 'settings_ops'):
                        w.settings_ops.save_as()
                    return True
                elif key == Qt.Key.Key_Q:
                    w.close()
                    return True
                elif key == Qt.Key.Key_U:
                    if hasattr(w, '_open_stream'):
                        w._open_stream()
                    return True

            elif modifiers == (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier):
                if key in (Qt.Key.Key_Left, Qt.Key.Key_Right):
                    if not self._is_main_window_focused():
                        return False
                    if key == Qt.Key.Key_Left:
                        self._switch_channel(-1)
                    else:
                        self._switch_channel(1)
                    return True
                elif key == Qt.Key.Key_O:
                    if hasattr(w, '_open_video_file'):
                        w._open_video_file()
                    return True

        except Exception as e:
            logger.error(f"快捷键处理失败(key={key}, mod={modifiers}): {e}")

        return False

    def _switch_channel(self, direction: int):
        """切换频道（-1=上一个，1=下一个）"""
        if not hasattr(self.window, 'channel_list'):
            from core.log_manager import global_logger as logger
            logger.debug("_switch_channel: channel_list 不存在")
            return

        current_row = self.window.channel_list.currentRow()
        total_rows = self.window.channel_list.count()

        if total_rows == 0:
            from core.log_manager import global_logger as logger
            logger.debug("_switch_channel: 频道列表为空")
            return

        new_row = (current_row + direction) % total_rows
        self.window.channel_list.setCurrentRow(new_row)

        item = self.window.channel_list.currentItem()
        if item and hasattr(self.window, 'channel_ctrl'):
            self.window.channel_ctrl.select_channel(item)
        else:
            from core.log_manager import global_logger as logger
            logger.debug(f"_switch_channel: 无法选择频道 item={item} has_ctrl={hasattr(self.window, 'channel_ctrl')}")

    def _adjust_volume(self, delta: int):
        """调整音量（delta为正增大，为负减小）"""
        if not hasattr(self.window, 'volume_slider'):
            return

        current = self.window.volume_slider.value()
        new_vol = max(0, min(100, current + delta))

        if new_vol != current:
            self.window.volume_slider.setValue(new_vol)

    def _on_mouse_activity(self):
        """鼠标活动回调 - 通知主窗口"""
        if hasattr(self.window, '_on_mouse_activity'):
            self.window._on_mouse_activity()

    def showEvent(self, event):
        """窗口首次显示后，延迟定位悬浮窗"""
        if hasattr(self.window, 'showEvent'):
            orig_show = type(self.window).__bases__[0].showEvent
            orig_show(self.window, event)

        has_panels = (hasattr(self.window, 'epg_dock') and self.window.epg_dock and
                      hasattr(self.window, 'playlist_dock') and self.window.playlist_dock and
                      hasattr(self.window, 'floating_dock') and self.window.floating_dock)

        if has_panels and not getattr(self.window, '_initial_position_fixed', False):
            self.window._initial_position_fixed = True
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(50, self._deferred_position_docks)
            QTimer.singleShot(200, self._deferred_position_docks)

    def _deferred_position_docks(self):
        """延迟到事件循环下一帧执行定位（确保主窗口geometry已稳定）"""
        try:
            from PyQt6.QtWidgets import QApplication
            app = QApplication.instance()
            if app:
                app.processEvents()

            config = getattr(self.window, 'config', None)
            if config:
                defaults = {
                    'epg_visible': True,
                    'playlist_visible': True,
                    'floating_visible': True,
                    'epg_width': 280,
                    'playlist_width': 280,
                    'floating_width': 1050,
                }
                settings = config.load_ui_settings(defaults)

                self.window.epg_visible = settings.get('epg_visible', True)
                self.window.playlist_visible = settings.get('playlist_visible', True)
                self.window.floating_panel_visible = settings.get('floating_visible', True)

                if hasattr(self.window, 'epg_dock') and self.window.epg_dock:
                    self.window.epg_dock.setFixedWidth(max(200, settings.get('epg_width', 280)))
                if hasattr(self.window, 'playlist_dock') and self.window.playlist_dock:
                    self.window.playlist_dock.setFixedWidth(max(200, settings.get('playlist_width', 280)))
                if hasattr(self.window, 'floating_dock') and self.window.floating_dock:
                    self.window.floating_dock.setFixedWidth(max(600, settings.get('floating_width', 1050)))

            self.window.update_floating_position()
        except Exception as e:
            from core.log_manager import global_logger as logger
            logger.error(f"延迟定位悬浮窗失败: {e}")

    def changeEvent(self, event):
        """窗口状态变化事件"""
        if hasattr(self.window, 'changeEvent'):
            try:
                orig_change = type(self.window).__bases__[0].changeEvent
                orig_change(self.window, event)
            except:
                pass

        if event.type() == QEvent.Type.ActivationChange:
            if self.window.isActiveWindow():
                if not getattr(self.window, '_pip_mode', False):
                    if hasattr(self.window, 'raise_floating_panels'):
                        self.window.raise_floating_panels()
                    if getattr(self.window, 'is_fullscreen', False):
                        if getattr(self.window, '_auto_hide_state', 'visible') == 'auto_hidden':
                            if hasattr(self.window, '_show_floating_panels_on_enter'):
                                self.window._show_floating_panels_on_enter()
                    if hasattr(self.window, '_on_main_window_activated'):
                        self.window._on_main_window_activated()
            else:
                if hasattr(self.window, '_on_main_window_deactivated'):
                    self.window._on_main_window_deactivated()

    def moveEvent(self, event):
        """窗口移动事件 - 跟随定位浮动Dock"""
        if getattr(self.window, '_pip_mode', False):
            if hasattr(self.window, '_update_pip_overlay_geometry'):
                self.window._update_pip_overlay_geometry()
            return
        if hasattr(self.window, 'update_floating_position'):
            self.window.update_floating_position()

    def resizeEvent(self, event):
        """窗口大小变化事件 - 跟随重定位浮动Dock"""
        if getattr(self.window, '_pip_mode', False):
            if hasattr(self.window, '_update_pip_overlay_geometry'):
                self.window._update_pip_overlay_geometry()
            if hasattr(self.window, '_update_pip_video_geometry'):
                self.window._update_pip_video_geometry()
            return
        if hasattr(self.window, 'update_floating_position'):
            self.window.update_floating_position()

    def closeEvent(self, event):
        """窗口关闭事件"""
        from core.log_manager import global_logger as logger
        logger.debug("关闭事件 - 清理所有资源")

        if hasattr(self.window, '_stop_auto_hide_timer'):
            self.window._stop_auto_hide_timer()

        # 1. 保存窗口布局
        if hasattr(self.window, 'settings_ops'):
            try:
                self.window.settings_ops.save_window_layout()
            except Exception as e:
                logger.error(f"保存窗口布局失败: {e}")

        # 2. 彻底终止MPV播放器（关键修复！）
        if hasattr(self.window, 'player_controller') and self.window.player_controller:
            try:
                logger.debug("正在终止MPV播放器...")
                if hasattr(self.window.player_controller, 'terminate'):
                    self.window.player_controller.terminate()
                else:
                    self.window.player_controller.stop()
                logger.info("MPV播放器已终止")
            except Exception as e:
                logger.error(f"终止MPV播放器失败: {e}")

        # 3. 关闭扫描窗口
        scan_dialog = getattr(self.window, '_scan_dialog', None) or getattr(self.window, 'scan_window', None)
        if scan_dialog:
            try:
                scan_dialog.close()
                scan_dialog.deleteLater()
            except Exception:
                pass
            self.window._scan_dialog = None
            self.window.scan_window = None

        # 4. 关闭所有悬浮窗
        for panel_name in ['floating_panel', 'epg_panel', 'playlist_panel']:
            panel = getattr(self.window, panel_name, None)
            if panel:
                try:
                    logger.debug(f"关闭悬浮窗: {panel_name}")
                    panel.close()
                    panel.deleteLater()
                except Exception as e:
                    logger.error(f"关闭{panel_name}失败: {e}")
                setattr(self.window, panel_name, None)

        # 5. 停止所有定时器
        timer_attrs = ['update_timer', 'resize_timer', '_source_timeout_timer',
                       '_epg_update_timer']
        for attr in timer_attrs:
            timer = getattr(self.window, attr, None)
            if timer:
                try:
                    timer.stop()
                except Exception:
                    pass

        # 5.5 等待后台工作线程完成
        if hasattr(self.window, 'subscription_ctrl'):
            for worker in self.window.subscription_ctrl._workers:
                if worker.isRunning():
                    try:
                        worker.quit()
                        worker.wait(2000)
                    except Exception:
                        pass

        if hasattr(self.window, '_thumbnail_service'):
            try:
                self.window._thumbnail_service.stop()
            except Exception:
                pass

        # 6. 强制退出应用（使用sys.exit确保进程完全终止）
        event.accept()

        import sys
        from PyQt6.QtWidgets import QApplication
        try:
            QApplication.instance().quit()
        except Exception:
            pass

        import time
        time.sleep(0.2)  # 给Qt一点时间清理

        sys.exit(0)

    def register_shortcut(self, key_sequence: str, callback):
        """注册自定义快捷键"""
        self._shortcuts[key_sequence] = callback

    def unregister_shortcut(self, key_sequence: str):
        """注销快捷键"""
        if key_sequence in self._shortcuts:
            del self._shortcuts[key_sequence]
