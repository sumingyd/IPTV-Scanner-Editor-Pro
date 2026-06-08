"""
媒体控制控制器 - 负责右键菜单、截图、音轨/字幕、倍速/画面比例等媒体相关控制
从 pyqt_player.py 提取的独立模块
"""

import os
import re

from core.log_manager import global_logger as logger
from controllers.main_window_protocol import MainWindowProtocol


class MediaController:
    """媒体控制控制器 - 统一管理媒体相关的所有控制逻辑"""

    SPEED_STEPS = [0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 3.0, 5.0]
    ASPECT_CYCLE = ['default', '16:9', '4:3', 'stretch', 'fill']

    def __init__(self, main_window: MainWindowProtocol):
        self.window: MainWindowProtocol = main_window
        self._current_aspect_idx = 0

    @property
    def is_osd_visible(self):
        return getattr(self.window, '_osd_visible', False)

    def show_video_context_menu(self, pos):
        from PyQt6.QtWidgets import QMenu
        from ui.styles import AppStyles
        tr = self.window.language_manager.tr
        menu = QMenu(self.window)
        menu.setStyleSheet(AppStyles.player_menu_bar_style())

        pc = self.window.player_controller
        is_playing = pc and (pc.is_playing or getattr(pc, 'is_paused', False))

        if is_playing:
            play_pause_text = tr("ctx_pause", "Pause") if not getattr(pc, 'is_paused', False) else tr("ctx_play", "Play")
            menu.addAction(play_pause_text, lambda *a: self.window.playback_ctrl.toggle_play())
            menu.addAction(tr("ctx_stop", "Stop"), lambda *a: self.window.playback_ctrl.stop_playback())

            menu.addSeparator()

            menu.addAction(tr("ctx_prev_channel", "Previous Channel"), lambda *a: self.window.event_handler._switch_channel(-1))
            menu.addAction(tr("ctx_next_channel", "Next Channel"), lambda *a: self.window.event_handler._switch_channel(1))

            menu.addSeparator()

        speed_menu = menu.addMenu(tr("ctx_speed", "Speed"))
        try:
            current_speed = pc.get_speed() if pc and pc.is_playing else 1.0
        except Exception:
            current_speed = 1.0
        for s in self.SPEED_STEPS:
            label = f"{s}x" + (" ✓" if abs(current_speed - s) < 0.01 else "")
            speed_menu.addAction(label, lambda *a, speed=s: self._set_speed(speed))

        volume_menu = menu.addMenu(tr("ctx_volume", "Volume"))
        try:
            current_vol = pc.get_volume() if pc and pc.is_playing else 80
            is_muted = pc.get_mute() if pc and pc.is_playing else False
        except Exception:
            current_vol = 80
            is_muted = False
        mute_text = tr("ctx_unmute", "Unmute") if is_muted else tr("ctx_mute", "Mute")
        volume_menu.addAction(mute_text, lambda *a: self.window.toggle_mute())
        volume_menu.addSeparator()
        for v in (0, 25, 50, 75, 100, 125, 150):
            label = f"{v}%" + (" ✓" if not is_muted and abs(current_vol - v) < 2 else "")
            volume_menu.addAction(label, lambda *a, vol=v: self._set_volume(vol))

        aspect_menu = menu.addMenu(tr("ctx_aspect_ratio", "Aspect Ratio"))
        aspect_labels = {
            'default': tr("ctx_aspect_default", "Default"),
            '16:9': '16:9',
            '4:3': '4:3',
            'stretch': tr("ctx_aspect_stretch", "Stretch"),
            'fill': tr("ctx_aspect_fill", "Fill"),
        }
        current_ratio = self.ASPECT_CYCLE[self._current_aspect_idx]
        for ratio in self.ASPECT_CYCLE:
            label = aspect_labels.get(ratio, ratio) + (" ✓" if ratio == current_ratio else "")
            aspect_menu.addAction(label, lambda *a, r=ratio: self._set_aspect(r))

        if is_playing:
            audio_menu = menu.addMenu(tr("ctx_audio_track", "Audio Track"))
            self._populate_audio_menu(audio_menu)

            sub_menu = menu.addMenu(tr("ctx_subtitle", "Subtitle"))
            self._populate_subtitle_menu(sub_menu)

        menu.addSeparator()

        if is_playing:
            menu.addAction(tr("ctx_screenshot", "Screenshot\tS"), lambda *a: self._take_screenshot())

        menu.addAction(tr("ctx_fullscreen", "Fullscreen\tF11"), lambda *a: self.window.toggle_fullscreen())
        menu.addAction(tr("ctx_pip", "Picture-in-Picture\tP"), lambda *a: self.window.pip_ctrl.toggle())

        menu.addSeparator()

        view_menu = menu.addMenu(tr("ctx_view", "View"))
        epg_action = view_menu.addAction(tr("ctx_epg", "EPG List\tE"))
        epg_action.setCheckable(True)
        epg_action.setChecked(self.window.epg_visible)
        epg_action.triggered.connect(lambda *a: self.window.toggle_epg())
        playlist_action = view_menu.addAction(tr("ctx_playlist", "Playlist\tL"))
        playlist_action.setCheckable(True)
        playlist_action.setChecked(self.window.playlist_visible)
        playlist_action.triggered.connect(lambda *a: self.window.toggle_playlist())
        panel_action = view_menu.addAction(tr("ctx_control_panel", "Control Panel\tM"))
        panel_action.setCheckable(True)
        panel_action.setChecked(self.window.floating_panel_visible)
        panel_action.triggered.connect(lambda *a: self.window.toggle_floating_panel())
        view_menu.addSeparator()
        view_menu.addAction(tr("ctx_hide_panels", "Hide Floating Panels\tY"), lambda *a: self.window.toggle_hide_floating())
        view_menu.addAction(tr("ctx_reset_layout", "Reset Layout"), lambda *a: self.window.reset_layout())

        menu.addSeparator()

        menu.addAction(tr("ctx_open_stream", "Open Stream\tCtrl+U"), lambda *a: self.window._open_stream())
        menu.addAction(tr("ctx_open_video", "Open Video\tCtrl+Shift+O"), lambda *a: self.window._open_video_file())
        menu.addAction(tr("ctx_scan", "Scan & Organize"), lambda *a: self.window.open_scan_ui())

        menu.exec(self.window.video_frame.mapToGlobal(pos))

    def take_screenshot(self):
        self._take_screenshot()

    def _take_screenshot(self):
        pc = self.window.player_controller
        if not pc or not pc.is_playing:
            return
        try:
            from datetime import datetime
            from PyQt6.QtWidgets import QApplication
            from PyQt6.QtGui import QPixmap

            screenshot_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'screenshots')
            os.makedirs(screenshot_dir, exist_ok=True)

            channel_name = ''
            current = self.window.current_channel
            if current:
                channel_name = current.get('name', '')
                channel_name = re.sub(r'[\\/:*?"<>|]', '_', channel_name)

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{channel_name}_{timestamp}.png" if channel_name else f"screenshot_{timestamp}.png"
            filepath = os.path.join(screenshot_dir, filename)

            pc.send_command(['screenshot-to-file', filepath, 'video'])

            def _copy_to_clipboard():
                try:
                    clipboard = QApplication.clipboard()
                    pixmap = QPixmap(filepath)
                    if not pixmap.isNull():
                        clipboard.setPixmap(pixmap)
                except Exception:
                    pass

            from PyQt6.QtCore import QTimer
            QTimer.singleShot(500, _copy_to_clipboard)

            self.window.status_bar_show_message(
                f"{self.window.language_manager.tr('screenshot_saved', 'Screenshot saved')}: {filename}")
        except Exception as e:
            logger.error(f"截图失败: {e}")

    def _populate_audio_menu(self, menu):
        menu.clear()
        pc = self.window.player_controller
        tr = self.window.language_manager.tr
        if not pc or not pc.is_playing:
            act = menu.addAction(tr('ctx_no_audio_track', 'No Audio Tracks'))
            act.setEnabled(False)
            return
        tracks = pc.get_track_list('audio')
        current_id = pc.get_current_track('audio')
        if not tracks:
            act = menu.addAction(tr('ctx_no_audio_track', 'No Audio Tracks'))
            act.setEnabled(False)
        else:
            actions = []
            for t in tracks:
                label = t.get('title') or t.get('lang') or tr('ctx_audio_track_n', 'Track {}').format(t['id'])
                if t.get('lang') and t.get('title') and t['lang'] != t['title']:
                    label = f"{t['title']} ({t['lang']})"
                act = menu.addAction(label)
                act.setCheckable(True)
                act.setChecked(t['id'] == current_id)
                actions.append((act, t['id'], label))
            for act, tid, label in actions:
                act.triggered.connect(
                    lambda checked, tid=tid, label=label, actions=actions: self._on_audio_track_selected(tid, label, actions)
                )

    def _on_audio_track_selected(self, track_id, label, actions):
        pc = self.window.player_controller
        if not pc:
            return
        success = pc.set_track('audio', track_id)
        if success:
            for act, tid, _ in actions:
                act.setChecked(tid == track_id)
            tr = self.window.language_manager.tr
            osd_text = tr('osd_audio_track', 'Audio: {}').format(label)
            if hasattr(self.window, '_show_osd_feedback'):
                self.window._show_osd_feedback(osd_text)
        else:
            tr = self.window.language_manager.tr
            fallback_id = self._try_fallback_track(pc, 'audio', track_id)
            if fallback_id is not None:
                fallback_label = ''
                for act, tid, lbl in actions:
                    if tid == fallback_id:
                        fallback_label = lbl
                        act.setChecked(True)
                    else:
                        act.setChecked(False)
                osd_text = tr('osd_audio_track_fallback', 'Audio track unavailable, switched to: {}').format(fallback_label)
                if hasattr(self.window, '_show_osd_feedback'):
                    self.window._show_osd_feedback(osd_text)
            else:
                osd_text = tr('osd_audio_track_failed', 'Audio track switch failed')
                if hasattr(self.window, '_show_osd_feedback'):
                    self.window._show_osd_feedback(osd_text)

    def _populate_subtitle_menu(self, menu):
        menu.clear()
        pc = self.window.player_controller
        tr = self.window.language_manager.tr
        if not pc or not pc.is_playing:
            act = menu.addAction(tr('ctx_no_subtitle', 'No Subtitle'))
            act.setEnabled(False)
            return
        current_id = pc.get_current_track('sub')
        tracks = pc.get_track_list('sub')
        sub_actions = []
        no_sub = menu.addAction(tr("ctx_no_subtitle", "No Subtitle"))
        no_sub.setCheckable(True)
        no_sub.setChecked(current_id is None or current_id == 0)
        sub_actions.append((no_sub, 0, tr("ctx_no_subtitle", "No Subtitle")))
        if tracks:
            menu.addSeparator()
            for t in tracks:
                label = t.get('title') or t.get('lang') or tr('ctx_subtitle_track_n', 'Sub {}').format(t['id'])
                if t.get('lang') and t.get('title') and t['lang'] != t['title']:
                    label = f"{t['title']} ({t['lang']})"
                act = menu.addAction(label)
                act.setCheckable(True)
                act.setChecked(t['id'] == current_id)
                sub_actions.append((act, t['id'], label))
        for act, tid, label in sub_actions:
            act.triggered.connect(
                lambda checked, tid=tid, label=label, actions=sub_actions: self._on_sub_track_selected(tid, label, actions)
            )
        menu.addSeparator()
        menu.addAction(tr("ctx_load_subtitle", "Load Subtitle..."), lambda *a: self._load_external_subtitle())

    def _on_sub_track_selected(self, track_id, label, actions):
        pc = self.window.player_controller
        if not pc:
            return
        if track_id == 0:
            pc.set_track('sub', 'no')
            for act, tid, _ in actions:
                act.setChecked(tid == 0)
            tr = self.window.language_manager.tr
            osd_text = tr('osd_subtitle_track', 'Subtitle: {}').format(label)
            if hasattr(self.window, '_show_osd_feedback'):
                self.window._show_osd_feedback(osd_text)
            return
        success = pc.set_track('sub', track_id)
        if success:
            for act, tid, _ in actions:
                act.setChecked(tid == track_id)
            tr = self.window.language_manager.tr
            osd_text = tr('osd_subtitle_track', 'Subtitle: {}').format(label)
            if hasattr(self.window, '_show_osd_feedback'):
                self.window._show_osd_feedback(osd_text)
        else:
            tr = self.window.language_manager.tr
            fallback_id = self._try_fallback_track(pc, 'sub', track_id)
            if fallback_id is not None:
                fallback_label = ''
                for act, tid, lbl in actions:
                    if tid == fallback_id:
                        fallback_label = lbl
                        act.setChecked(True)
                    else:
                        act.setChecked(False)
                osd_text = tr('osd_sub_track_fallback', 'Subtitle track unavailable, switched to: {}').format(fallback_label)
                if hasattr(self.window, '_show_osd_feedback'):
                    self.window._show_osd_feedback(osd_text)
            else:
                osd_text = tr('osd_subtitle_track_failed', 'Subtitle track switch failed')
                if hasattr(self.window, '_show_osd_feedback'):
                    self.window._show_osd_feedback(osd_text)

    def _try_fallback_track(self, pc, track_type, failed_id):
        try:
            tracks = pc.get_track_list(track_type)
            if not tracks:
                return None
            current = pc.get_current_track(track_type)
            for t in tracks:
                if t['id'] != failed_id and t['id'] != current:
                    if pc.set_track(track_type, t['id']):
                        logger.info(f"轨道降级切换: {track_type} 从 {failed_id} 降级到 {t['id']}")
                        return t['id']
            if current and current != failed_id:
                return current
        except Exception as e:
            logger.debug(f"轨道降级切换失败: {e}")
        return None

    def show_audio_track_menu(self):
        pc = self.window.player_controller
        if not pc or not pc.is_playing:
            return
        from PyQt6.QtWidgets import QMenu
        from ui.styles import AppStyles
        menu = QMenu(self.window)
        menu.setStyleSheet(AppStyles.player_menu_bar_style())
        self._populate_audio_menu(menu)
        btn = self.window.audio_track_button
        menu.exec(btn.mapToGlobal(btn.rect().bottomLeft()))

    def show_sub_track_menu(self):
        pc = self.window.player_controller
        if not pc or not pc.is_playing:
            return
        from PyQt6.QtWidgets import QMenu
        from ui.styles import AppStyles
        menu = QMenu(self.window)
        menu.setStyleSheet(AppStyles.player_menu_bar_style())
        self._populate_subtitle_menu(menu)
        btn = self.window.sub_track_button
        menu.exec(btn.mapToGlobal(btn.rect().bottomLeft()))

    def show_speed_menu(self):
        from PyQt6.QtWidgets import QMenu
        from ui.styles import AppStyles
        tr = self.window.language_manager.tr
        menu = QMenu(self.window)
        menu.setStyleSheet(AppStyles.player_menu_bar_style())
        pc = self.window.player_controller
        try:
            current_speed = pc.get_speed() if pc and pc.is_playing else 1.0
        except Exception:
            current_speed = 1.0
        for s in self.SPEED_STEPS:
            label = f"{s}x" + (" ✓" if abs(current_speed - s) < 0.01 else "")
            menu.addAction(label, lambda *a, speed=s: self._set_speed(speed))
        btn = self.window.speed_button
        menu.exec(btn.mapToGlobal(btn.rect().bottomLeft()))

    def show_aspect_menu(self):
        from PyQt6.QtWidgets import QMenu
        from ui.styles import AppStyles
        tr = self.window.language_manager.tr
        menu = QMenu(self.window)
        menu.setStyleSheet(AppStyles.player_menu_bar_style())
        aspect_labels = {
            'default': tr("ctx_aspect_default", "Default"),
            '16:9': '16:9',
            '4:3': '4:3',
            'stretch': tr("ctx_aspect_stretch", "Stretch"),
            'fill': tr("ctx_aspect_fill", "Fill"),
        }
        current_ratio = self.ASPECT_CYCLE[self._current_aspect_idx]
        for ratio in self.ASPECT_CYCLE:
            label = aspect_labels.get(ratio, ratio) + (" ✓" if ratio == current_ratio else "")
            menu.addAction(label, lambda *a, r=ratio: self._set_aspect(r))
        btn = getattr(self.window, 'aspect_button', None)
        if btn:
            menu.exec(btn.mapToGlobal(btn.rect().bottomLeft()))

    def _load_external_subtitle(self):
        pc = self.window.player_controller
        if not pc or not pc.is_playing:
            return
        from PyQt6.QtWidgets import QFileDialog
        tr = self.window.language_manager.tr
        file_path, _ = QFileDialog.getOpenFileName(
            self.window, tr("ctx_load_subtitle", "Load Subtitle..."), '',
            tr("ctx_subtitle_files", "Subtitle Files") + " (*.srt *.ass *.ssa *.sub *.idx *.vtt *.lrc);;" + tr("ctx_all_files", "All Files") + " (*)"
        )
        if file_path:
            if pc.add_subtitle_file(file_path):
                self.window._show_osd_feedback(f"{tr('ctx_subtitle', 'Subtitle')}: {file_path.split('/')[-1].split(chr(92))[-1]}")

    def adjust_speed(self, delta):
        pc = self.window.player_controller
        if not pc:
            return
        current = pc.get_speed()
        new_speed = round(max(0.1, min(10.0, current + delta)), 1)
        pc.set_speed(new_speed)
        speed_btn = self.window.speed_button
        if speed_btn:
            speed_btn.setText(f"{new_speed}x")
        if not self.is_osd_visible:
            self.window._show_osd_feedback(f"{self.window.language_manager.tr('osd_speed', 'Speed')}: {new_speed}x")

    def cycle_speed(self):
        pc = self.window.player_controller
        if not pc:
            return
        current = pc.get_speed()
        idx = 0
        for i, s in enumerate(self.SPEED_STEPS):
            if abs(current - s) < 0.01:
                idx = i
                break
        next_idx = (idx + 1) % len(self.SPEED_STEPS)
        new_speed = self.SPEED_STEPS[next_idx]
        pc.set_speed(new_speed)
        speed_btn = self.window.speed_button
        if speed_btn:
            speed_btn.setText(f"{new_speed}x")
        if not self.is_osd_visible:
            self.window._show_osd_feedback(f"{self.window.language_manager.tr('osd_speed', 'Speed')}: {new_speed}x")

    def cycle_aspect_ratio(self):
        pc = self.window.player_controller
        if not pc:
            return
        self._current_aspect_idx = (self._current_aspect_idx + 1) % len(self.ASPECT_CYCLE)
        ratio = self.ASPECT_CYCLE[self._current_aspect_idx]
        pc.set_aspect_ratio(ratio)
        tr = self.window.language_manager.tr
        labels = {
            'default': tr('ctx_aspect_default', 'Default'),
            '16:9': '16:9',
            '4:3': '4:3',
            'stretch': tr('ctx_aspect_stretch', 'Stretch'),
            'fill': tr('ctx_aspect_fill', 'Fill')
        }
        aspect_btn = getattr(self.window, 'aspect_button', None)
        if aspect_btn:
            aspect_btn.setText(labels.get(ratio, tr('ctx_aspect_default', 'Default')))
        if hasattr(self.window, '_show_osd_feedback'):
            osd_text = f"{tr('osd_aspect_ratio', 'Aspect')}: {labels.get(ratio, tr('ctx_aspect_default', 'Default'))}"
            self.window._show_osd_feedback(osd_text)
        self._save_aspect_ratio(ratio)

    def _save_aspect_ratio(self, ratio):
        try:
            self.window.config.set_value('Player', 'aspect_ratio', ratio)
            self.window.config.save_config()
        except Exception as e:
            logger.debug(f"保存画面比例设置失败: {e}")

    def restore_aspect_ratio(self):
        try:
            ratio = self.window.config.get_value('Player', 'aspect_ratio', 'default') or 'default'
            if ratio in self.ASPECT_CYCLE:
                self._current_aspect_idx = self.ASPECT_CYCLE.index(ratio)
            else:
                self._current_aspect_idx = 0
                ratio = 'default'
            pc = self.window.player_controller
            if pc:
                pc.set_aspect_ratio(ratio)
            tr = self.window.language_manager.tr
            labels = {
                'default': tr('ctx_aspect_default', 'Default'),
                '16:9': '16:9',
                '4:3': '4:3',
                'stretch': tr('ctx_aspect_stretch', 'Stretch'),
                'fill': tr('ctx_aspect_fill', 'Fill')
            }
            aspect_btn = getattr(self.window, 'aspect_button', None)
            if aspect_btn:
                aspect_btn.setText(labels.get(ratio, tr('ctx_aspect_default', 'Default')))
        except Exception as e:
            logger.debug(f"恢复画面比例失败: {e}")

    def _set_speed(self, speed):
        pc = self.window.player_controller
        if not pc or not pc.is_playing:
            return
        try:
            pc.set_speed(speed)
        except Exception:
            return
        speed_btn = self.window.speed_button
        if speed_btn:
            speed_btn.setText(f"{speed}x")
        if not self.is_osd_visible:
            self.window._show_osd_feedback(f"{self.window.language_manager.tr('osd_speed', 'Speed')}: {speed}x")

    def _set_volume(self, volume):
        pc = self.window.player_controller
        if not pc:
            return
        try:
            pc.set_volume(volume)
        except Exception:
            return
        volume_slider = self.window.volume_slider
        if volume_slider:
            volume_slider.setValue(volume)
        playback_ctrl = getattr(self.window, 'playback_ctrl', None)
        if playback_ctrl:
            playback_ctrl._update_volume_icon(volume)
        if not self.is_osd_visible:
            self.window._show_osd_feedback(f"{self.window.language_manager.tr('osd_volume', 'Volume')}: {volume}%")

    def _set_aspect(self, ratio):
        pc = self.window.player_controller
        if not pc:
            return
        try:
            pc.set_aspect_ratio(ratio)
        except Exception:
            return
        if ratio in self.ASPECT_CYCLE:
            self._current_aspect_idx = self.ASPECT_CYCLE.index(ratio)
        tr = self.window.language_manager.tr
        labels = {
            'default': tr('ctx_aspect_default', 'Default'),
            '16:9': '16:9',
            '4:3': '4:3',
            'stretch': tr('ctx_aspect_stretch', 'Stretch'),
            'fill': tr('ctx_aspect_fill', 'Fill')
        }
        aspect_btn = getattr(self.window, 'aspect_button', None)
        if aspect_btn:
            aspect_btn.setText(labels.get(ratio, tr('ctx_aspect_default', 'Default')))
        if hasattr(self.window, '_show_osd_feedback'):
            self.window._show_osd_feedback(f"{tr('osd_aspect_ratio', 'Aspect')}: {labels.get(ratio, tr('ctx_aspect_default', 'Default'))}")
        self._save_aspect_ratio(ratio)

    def update_catchup_indicator(self):
        try:
            indicator = getattr(self.window, 'catchup_indicator', None)
            if not indicator:
                return

            is_timeshift = self.window.play_state.is_timeshift
            is_catchup = self.window.play_state.is_catchup

            if is_timeshift:
                indicator.setText(self.window.language_manager.tr('timeshift_watching', '正在时移观看'))
                indicator.show()
            elif is_catchup and not is_timeshift:
                indicator.setText(self.window.language_manager.tr('catchup_playing_label', '正在回看'))
                indicator.show()
            elif self.window.current_channel and (
                self.window.current_channel.get('catchup_source', '')
                or self.window.current_channel.get('catchup', '')
            ):
                indicator.setText(self.window.language_manager.tr('catchup_available', '可回放'))
                indicator.show()
            else:
                indicator.hide()
        except Exception as e:
            logger.debug(f"更新回看指示器失败: {e}")