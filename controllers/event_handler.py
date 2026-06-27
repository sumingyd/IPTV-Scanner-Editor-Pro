"""
事件处理器 - 负责键盘快捷键、事件过滤、窗口事件等
从 pyqt_player.py 提取的独立模块
"""

from PySide6.QtCore import Qt, QEvent, QTimer
from controllers.main_window_protocol import MainWindowProtocol


class EventHandler:
    """事件处理器 - 统一管理所有事件处理逻辑"""

    def __init__(self, main_window: MainWindowProtocol):
        self.window: MainWindowProtocol = main_window
        self._shortcuts = {}  # 快捷键映射表

    def _is_main_window_focused(self) -> bool:
        """判断当前焦点是否在主窗口上（排除悬浮面板、对话框等）"""
        from PySide6.QtWidgets import QApplication
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

        if not getattr(self.window, 'pip_mode', False):
            if obj is getattr(self.window, 'video_widget', None):
                if event_type == QEvent.Type.Wheel:
                    if hasattr(self.window, 'wheelEvent'):
                        self.window.wheelEvent(event)
                        return True
                elif event_type == QEvent.Type.MouseButtonDblClick:
                    if hasattr(self.window, 'mouseDoubleClickEvent'):
                        self.window.mouseDoubleClickEvent(event)
                        return True

        manually_hidden = getattr(self.window, 'panel_vis', None) and self.window.panel_vis.manually_hidden
        if not getattr(self.window, 'pip_mode', False) and not getattr(self.window, 'is_fullscreen', False) and not manually_hidden:
            if event_type == QEvent.Type.Leave:
                if obj is self.window or obj is getattr(self.window, 'video_widget', None) or obj is getattr(self.window, 'central_widget', None):
                    if hasattr(self.window, '_delayed_hide_floating_panels'):
                        from PySide6.QtCore import QTimer
                        QTimer.singleShot(200, self.window._delayed_hide_floating_panels)
            elif event_type == QEvent.Type.Enter:
                if obj is self.window or obj is getattr(self.window, 'video_widget', None):
                    if hasattr(self.window, '_show_floating_panels_on_enter'):
                        self.window._show_floating_panels_on_enter()
                else:
                    for panel_name in ('epg_panel', 'playlist_panel', 'floating_panel'):
                        panel = getattr(self.window, panel_name, None)
                        if panel and obj is panel:
                            if hasattr(self.window, '_show_floating_panels_on_enter'):
                                self.window._show_floating_panels_on_enter()
                            break

        return False

    def _is_input_widget_focused(self) -> bool:
        """判断当前焦点是否在输入控件上（编辑框、文本框等）"""
        from PySide6.QtWidgets import QApplication, QLineEdit, QTextEdit, QComboBox, QSpinBox
        focus_widget = QApplication.focusWidget()
        if focus_widget:
            if isinstance(focus_widget, (QLineEdit, QTextEdit, QSpinBox)):
                return True
            if isinstance(focus_widget, QComboBox) and focus_widget.isEditable():
                return True
        return False

    def _is_handled_shortcut(self, key, modifiers) -> bool:
        """判断按键组合是否由 eventFilter 统一处理（用于拦截 ShortcutOverride）"""
        if self._is_input_widget_focused():
            return False
        if modifiers == Qt.KeyboardModifier.NoModifier:
            global_keys = (Qt.Key.Key_Space, Qt.Key.Key_Escape,
                           Qt.Key.Key_F, Qt.Key.Key_E,
                           Qt.Key.Key_L, Qt.Key.Key_M,
                           Qt.Key.Key_Y, Qt.Key.Key_Tab,
                           Qt.Key.Key_F5, Qt.Key.Key_F11,
                           Qt.Key.Key_Backspace, Qt.Key.Key_S,
                           Qt.Key.Key_Period, Qt.Key.Key_Comma,
                           Qt.Key.Key_P,
                           # 字幕快捷键
                           Qt.Key.Key_V, Qt.Key.Key_Z, Qt.Key.Key_X,
                           Qt.Key.Key_Q, Qt.Key.Key_W,
                           # 视频图像调整快捷键
                           Qt.Key.Key_3, Qt.Key.Key_4,
                           Qt.Key.Key_5, Qt.Key.Key_6,
                           Qt.Key.Key_7, Qt.Key.Key_8,
                           Qt.Key.Key_9, Qt.Key.Key_0,
                           Qt.Key.Key_R, Qt.Key.Key_T,
                           # 音频调整快捷键
                           Qt.Key.Key_Minus, Qt.Key.Key_Equal,
                           Qt.Key.Key_G, Qt.Key.Key_H)
            main_only_keys = (Qt.Key.Key_Up, Qt.Key.Key_Down,
                              Qt.Key.Key_Left, Qt.Key.Key_Right)
            if key == Qt.Key.Key_Backspace and self._is_input_widget_focused():
                return False
            if key in global_keys:
                return True
            if key in main_only_keys and self._is_main_window_focused():
                return True
            return False
        elif modifiers == Qt.KeyboardModifier.ControlModifier:
            return key in (Qt.Key.Key_O, Qt.Key.Key_S, Qt.Key.Key_Q,
                           Qt.Key.Key_U, Qt.Key.Key_M)
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
            if self._is_input_widget_focused():
                return False
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
                        self._seek_relative(-10)
                    elif key == Qt.Key.Key_Right:
                        self._seek_relative(10)
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
                    if self._is_input_widget_focused():
                        return False
                    if hasattr(w, 'switch_to_previous_channel'):
                        w.switch_to_previous_channel()
                    return True
                elif key == Qt.Key.Key_S:
                    if hasattr(w, 'media_ctrl'):
                        w.media_ctrl.take_screenshot()
                    return True
                elif key == Qt.Key.Key_Period:
                    if hasattr(w, 'media_ctrl'):
                        w.media_ctrl.adjust_speed(0.1)
                    return True
                elif key == Qt.Key.Key_Comma:
                    if hasattr(w, 'media_ctrl'):
                        w.media_ctrl.adjust_speed(-0.1)
                    return True
                elif key == Qt.Key.Key_P:
                    if hasattr(w, 'pip_ctrl'):
                        w.pip_ctrl.toggle()
                    return True
                # 字幕可见性切换（V）
                elif key == Qt.Key.Key_V:
                    if hasattr(w, 'media_ctrl'):
                        w.media_ctrl.toggle_subtitle_visibility()
                    return True
                # 字幕延迟 -0.1/+0.1（Z/X）
                elif key == Qt.Key.Key_Z:
                    if hasattr(w, 'media_ctrl'):
                        w.media_ctrl.adjust_subtitle_delay(-0.1)
                    return True
                elif key == Qt.Key.Key_X:
                    if hasattr(w, 'media_ctrl'):
                        w.media_ctrl.adjust_subtitle_delay(0.1)
                    return True
                # 字幕缩放 -0.1/+0.1（Q/W）
                elif key == Qt.Key.Key_Q:
                    if hasattr(w, 'media_ctrl'):
                        w.media_ctrl.adjust_subtitle_scale(-0.1)
                    return True
                elif key == Qt.Key.Key_W:
                    if hasattr(w, 'media_ctrl'):
                        w.media_ctrl.adjust_subtitle_scale(0.1)
                    return True
                # 视频图像调整：亮度(3/4) 对比度(5/6) 饱和度(7/8) Gamma(9/0)
                elif key == Qt.Key.Key_3:
                    if hasattr(w, 'media_ctrl'):
                        w.media_ctrl.adjust_video_eq('brightness', -2)
                    return True
                elif key == Qt.Key.Key_4:
                    if hasattr(w, 'media_ctrl'):
                        w.media_ctrl.adjust_video_eq('brightness', 2)
                    return True
                elif key == Qt.Key.Key_5:
                    if hasattr(w, 'media_ctrl'):
                        w.media_ctrl.adjust_video_eq('contrast', -2)
                    return True
                elif key == Qt.Key.Key_6:
                    if hasattr(w, 'media_ctrl'):
                        w.media_ctrl.adjust_video_eq('contrast', 2)
                    return True
                elif key == Qt.Key.Key_7:
                    if hasattr(w, 'media_ctrl'):
                        w.media_ctrl.adjust_video_eq('saturation', -2)
                    return True
                elif key == Qt.Key.Key_8:
                    if hasattr(w, 'media_ctrl'):
                        w.media_ctrl.adjust_video_eq('saturation', 2)
                    return True
                elif key == Qt.Key.Key_9:
                    if hasattr(w, 'media_ctrl'):
                        w.media_ctrl.adjust_video_eq('gamma', -2)
                    return True
                elif key == Qt.Key.Key_0:
                    if hasattr(w, 'media_ctrl'):
                        w.media_ctrl.adjust_video_eq('gamma', 2)
                    return True
                # 画面旋转循环（R）/ 翻转循环（T）
                elif key == Qt.Key.Key_R:
                    if hasattr(w, 'media_ctrl'):
                        w.media_ctrl.cycle_video_rotate(90)
                    return True
                elif key == Qt.Key.Key_T:
                    if hasattr(w, 'media_ctrl'):
                        w.media_ctrl.toggle_video_flip()
                    return True
                # 音频延迟 -0.1/+0.1（-/=）
                elif key == Qt.Key.Key_Minus:
                    if hasattr(w, 'media_ctrl'):
                        w.media_ctrl.adjust_audio_delay(-0.1)
                    return True
                elif key == Qt.Key.Key_Equal:
                    if hasattr(w, 'media_ctrl'):
                        w.media_ctrl.adjust_audio_delay(0.1)
                    return True
                # 音调补偿 -0.05/+0.05（G/H）
                elif key == Qt.Key.Key_G:
                    if hasattr(w, 'media_ctrl'):
                        w.media_ctrl.adjust_audio_pitch(-0.05)
                    return True
                elif key == Qt.Key.Key_H:
                    if hasattr(w, 'media_ctrl'):
                        w.media_ctrl.adjust_audio_pitch(0.05)
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
                elif key == Qt.Key.Key_M:
                    if hasattr(w, 'toggle_mute'):
                        w.toggle_mute()
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
        if hasattr(self.window, 'playlist_tab') and self.window.playlist_tab:
            if self.window.playlist_tab.currentIndex() == 1:
                channel_list = self.window.local_channel_list
            else:
                channel_list = self.window.sub_channel_list
        elif hasattr(self.window, 'channel_list'):
            channel_list = self.window.channel_list
        else:
            return

        current_row = channel_list.currentRow()
        total_rows = channel_list.count()

        if total_rows == 0:
            return

        new_row = (current_row + direction) % total_rows
        channel_list.setCurrentRow(new_row)

        item = channel_list.currentItem()
        if item and hasattr(self.window, 'select_channel'):
            self.window.select_channel(item, source_list=channel_list)

    def _adjust_volume(self, delta: int):
        """调整音量（delta为正增大，为负减小）"""
        if not hasattr(self.window, 'volume_slider'):
            return

        current = self.window.volume_slider.value()
        new_vol = max(0, min(100, current + delta))

        if new_vol != current:
            self.window.volume_slider.setValue(new_vol)

    def _is_local_file_playing(self) -> bool:
        """判断当前是否在播放本地视频文件或回看/时移（支持seek）"""
        w = self.window
        if not hasattr(w, 'player_controller') or not w.player_controller or not w.player_controller.is_playing:
            return False
        if hasattr(w, '_is_local_file') and w._is_local_file():
            return True
        if hasattr(w, 'play_state') and w.play_state.is_catchup_or_timeshift:
            return True
        return False

    def _seek_relative(self, seconds: float):
        """相对跳转（seconds为正快进，为负快退）"""
        w = self.window
        if not hasattr(w, 'player_controller') or not w.player_controller:
            return
        if not w.player_controller.is_playing:
            return
        try:
            w.player_controller.seek_relative_seconds(seconds)
        except Exception as e:
            from core.log_manager import global_logger as logger
            logger.debug(f"快进快退失败: {e}")

    def _on_mouse_activity(self):
        """鼠标活动回调 - 通知主窗口"""
        if hasattr(self.window, '_on_mouse_activity'):
            self.window._on_mouse_activity()

    def showEvent(self, event):
        """窗口首次显示后，延迟定位悬浮窗"""
        if hasattr(self.window, 'showEvent'):
            from PySide6.QtWidgets import QMainWindow
            QMainWindow.showEvent(self.window, event)

        has_panels = (hasattr(self.window, 'epg_dock') and self.window.epg_dock and
                      hasattr(self.window, 'playlist_dock') and self.window.playlist_dock and
                      hasattr(self.window, 'floating_dock') and self.window.floating_dock)

        if has_panels and not getattr(self.window, '_initial_position_fixed', False):
            from PySide6.QtCore import QTimer
            QTimer.singleShot(50, self._deferred_position_docks)
            QTimer.singleShot(200, self._deferred_position_docks)

    def _deferred_position_docks(self):
        """延迟到事件循环下一帧执行定位（确保主窗口geometry已稳定）"""
        try:
            from PySide6.QtWidgets import QApplication
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

                self.window.epg_visible = True
                self.window.playlist_visible = True
                self.window.floating_panel_visible = True

                if hasattr(self.window, 'epg_dock') and self.window.epg_dock:
                    epg_w = max(200, settings.get('epg_width', 280))
                    self.window.epg_dock.setMinimumWidth(epg_w)
                    self.window.epg_dock.resize(epg_w, self.window.epg_dock.height())
                if hasattr(self.window, 'playlist_dock') and self.window.playlist_dock:
                    pl_w = max(200, settings.get('playlist_width', epg_w))
                    self.window.playlist_dock.setMinimumWidth(pl_w)
                    self.window.playlist_dock.resize(pl_w, self.window.playlist_dock.height())
                if hasattr(self.window, 'floating_dock') and self.window.floating_dock:
                    self.window.floating_dock.setMinimumWidth(max(480, settings.get('floating_width', 1050)))

            self.window.update_floating_position()
        except Exception as e:
            from core.log_manager import global_logger as logger
            logger.error(f"延迟定位悬浮窗失败: {e}")

    def changeEvent(self, event):
        """窗口状态变化事件"""
        if not self.window:
            return
        if hasattr(self.window, 'changeEvent'):
            try:
                from PySide6.QtWidgets import QMainWindow
                QMainWindow.changeEvent(self.window, event)
            except (AttributeError, TypeError):
                pass

        if event.type() == QEvent.Type.ActivationChange:
            if self.window and self.window.isActiveWindow():
                if not getattr(self.window, 'pip_mode', False):
                    if hasattr(self.window, 'raise_floating_panels'):
                        self.window.raise_floating_panels()
                    if getattr(self.window, 'is_fullscreen', False):
                        if getattr(self.window, 'panel_vis', None) and self.window.panel_vis.is_auto_hidden:
                            if hasattr(self.window, '_show_floating_panels_on_enter'):
                                self.window._show_floating_panels_on_enter()
                    if hasattr(self.window, '_on_main_window_activated'):
                        self.window._on_main_window_activated()
            else:
                if hasattr(self.window, '_on_main_window_deactivated'):
                    self.window._on_main_window_deactivated()

    def moveEvent(self, event):
        """窗口移动事件 - 跟随定位浮动Dock（节流）"""
        if getattr(self.window, 'pip_mode', False):
            if hasattr(self.window, 'pip_ctrl'):
                self.window.pip_ctrl._update_overlay_geometry()
            return
        self._schedule_position_update()

    def resizeEvent(self, event):
        """窗口大小变化事件 - 跟随重定位浮动Dock（节流）"""
        if getattr(self.window, 'pip_mode', False):
            if hasattr(self.window, 'pip_ctrl'):
                self.window.pip_ctrl._update_overlay_geometry()
                self.window.pip_ctrl._update_video_geometry()
            return
        self._schedule_position_update()

    def _schedule_position_update(self):
        if not hasattr(self, '_position_timer'):
            from PySide6.QtCore import QTimer
            self._position_timer = QTimer()
            self._position_timer.setSingleShot(True)
            self._position_timer.setInterval(16)
            self._position_timer.timeout.connect(self._do_position_update)
        if not self._position_timer.isActive():
            self._position_timer.start()

    def _do_position_update(self):
        if hasattr(self.window, 'update_floating_position'):
            self.window.update_floating_position()

    def closeEvent(self, event):
        """窗口关闭事件"""
        from core.log_manager import global_logger as logger
        logger.debug("关闭事件 - 清理所有资源")

        if hasattr(self.window, '_stop_auto_hide_timer'):
            self.window._stop_auto_hide_timer()

        try:
            from ui.theme_manager import get_theme_manager
            tm = get_theme_manager()
            tm._stop_system_theme_watcher()
            tm._windows.clear()
        except Exception as e:
            logger.debug(f"清理主题管理器失败: {e}")

        # 1. 保存窗口布局
        if hasattr(self.window, 'settings_ops'):
            try:
                self.window.settings_ops.save_window_layout()
            except Exception as e:
                logger.error(f"保存窗口布局失败: {e}")

        # 1.5 保存当前频道
        if hasattr(self.window, 'current_channel') and hasattr(self.window, 'config'):
            try:
                ch = self.window.current_channel
                if ch:
                    ch_name = ch.get('name', '')
                    ch_idx = -1
                    channels = getattr(self.window, '_sub_channels', [])
                    for i, c in enumerate(channels):
                        if c.get('name', '') == ch_name:
                            ch_idx = i
                            break
                    if ch_idx < 0:
                        channels = getattr(self.window, '_local_channels', [])
                        for i, c in enumerate(channels):
                            if c.get('name', '') == ch_name:
                                ch_idx = i
                                break
                    is_local = getattr(self.window, 'channel_list', None) is getattr(self.window, 'local_channel_list', None)
                    ch_file = getattr(self.window, '_local_playlist_path', '') if is_local else getattr(self.window, '_subscription_url', '')
                    self.window.config.save_last_channel(ch_file, ch_name, ch_idx)
            except Exception as e:
                logger.debug(f"保存最后频道失败: {e}")

        # 2. 先停止所有可能访问mpv_handle的定时器（必须在终止MPV之前！）
        timer_attrs = ['update_timer', '_source_timeout_timer', '_auto_hide_timer']
        for attr in timer_attrs:
            timer = getattr(self.window, attr, None)
            if timer:
                try:
                    timer.stop()
                except Exception as e:
                    logger.debug(f"停止定时器{attr}失败: {e}")
        if hasattr(self, '_position_timer'):
            try:
                self._position_timer.stop()
            except Exception as e:
                logger.debug(f"停止位置定时器失败: {e}")

        # 3. 终止MPV播放器（定时器已停止，不会再访问mpv_handle）
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

        # 3.5 终止多画面控制器
        if hasattr(self.window, 'multi_screen_ctrl') and self.window.multi_screen_ctrl:
            try:
                self.window.multi_screen_ctrl.terminate()
            except Exception as e:
                logger.error(f"终止多画面控制器失败: {e}")

        # 4. 关闭扫描窗口
        scan_dialog = getattr(self.window, '_scan_dialog', None) or getattr(self.window, 'scan_window', None)
        if scan_dialog:
            try:
                scan_dialog.close()
                scan_dialog.deleteLater()
            except Exception as e:
                logger.debug(f"关闭扫描窗口失败: {e}")
            self.window._scan_dialog = None
            self.window.scan_window = None

        # 5. 关闭所有悬浮窗
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

        # 6. 停止缩略图服务
        if hasattr(self.window, '_thumbnail_service'):
            try:
                self.window._thumbnail_service.stop()
            except Exception as e:
                logger.debug(f"停止缩略图服务失败: {e}")

        # 6.5 停止台标缓存服务
        logo_svc = getattr(self.window, '_logo_cache_service', None)
        if logo_svc:
            try:
                warmup_timer = getattr(logo_svc, '_warmup_timer', None)
                if warmup_timer:
                    warmup_timer.stop()
            except Exception as e:
                logger.debug(f"停止台标缓存定时器失败: {e}")

        # 6.6 停止DNS预取/连接预热
        for svc_name in ('_dns_prefetcher', '_connection_preheater'):
            svc = getattr(self.window, svc_name, None)
            if svc:
                for method_name in ('shutdown', 'stop'):
                    if hasattr(svc, method_name):
                        try:
                            getattr(svc, method_name)()
                        except Exception as e:
                            logger.debug(f"停止{svc_name}失败: {e}")
                        break

        # 6.7 停止EPG提醒服务
        epg_reminder = getattr(self.window, 'epg_reminder_ctrl', None)
        if epg_reminder and hasattr(epg_reminder, '_reminder_service'):
            try:
                epg_reminder._reminder_service.stop()
            except Exception as e:
                logger.debug(f"停止EPG提醒服务失败: {e}")

        # 6.8 停止FCC服务
        fcc_service = getattr(self.window, '_fcc_service', None)
        if fcc_service and hasattr(fcc_service, 'stop'):
            try:
                fcc_service.stop()
            except Exception as e:
                logger.debug(f"停止FCC服务失败: {e}")

        # 6.9 清理系统托盘
        tray = getattr(self.window, '_system_tray', None)
        if tray:
            try:
                tray.hide()
                tray.deleteLater()
            except Exception as e:
                logger.debug(f"清理系统托盘失败: {e}")
            self.window._system_tray = None

        # 6.7 执行注册的资源清理器
        try:
            from utils.resource_cleaner import cleanup_all
            cleanup_all()
        except Exception as e:
            logger.debug(f"执行资源清理器失败: {e}")

        # 7. 等待后台工作线程完成
        if hasattr(self.window, 'subscription_ctrl'):
            for worker in self.window.subscription_ctrl._workers:
                if worker.isRunning():
                    try:
                        worker.requestInterruption()
                        if not worker.wait(3000):
                            logger.warning(f"工作线程 {worker} 未在3秒内退出，将随进程终止")
                    except Exception as e:
                        logger.debug(f"等待工作线程失败: {e}")

        # 7.5 断开控制器与主窗口的引用循环
        controller_attrs = [
            'window_ctrl', 'playback_ctrl', 'epg_ctrl', 'channel_ctrl',
            'settings_ops', 'ui_ctrl', 'subscription_ctrl', 'subscription_ui_ctrl',
            'catchup_ctrl', 'pip_ctrl', 'media_ctrl', 'update_ctrl',
            'favorites_ctrl', 'epg_reminder_ctrl', 'event_handler',
        ]
        for attr in controller_attrs:
            ctrl = getattr(self.window, attr, None)
            if ctrl is not None:
                try:
                    if hasattr(ctrl, 'window'):
                        ctrl.window = None
                except Exception as e:
                    logger.debug(f"断开控制器{attr}引用失败: {e}")

        # 8. 退出应用
        event.accept()

        from PySide6.QtWidgets import QApplication
        try:
            QApplication.instance().quit()
        except Exception:
            pass

    def register_shortcut(self, key_sequence: str, callback):
        """注册自定义快捷键"""
        self._shortcuts[key_sequence] = callback

    def unregister_shortcut(self, key_sequence: str):
        """注销快捷键"""
        if key_sequence in self._shortcuts:
            del self._shortcuts[key_sequence]
