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
        from PySide6.QtWidgets import QMenu
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
        speed_menu.setStyleSheet(AppStyles.player_menu_bar_style())
        try:
            current_speed = pc.get_speed() if pc and pc.is_playing else 1.0
        except Exception:
            current_speed = 1.0
        for s in self.SPEED_STEPS:
            label = f"{s}x" + (" ✓" if abs(current_speed - s) < 0.01 else "")
            speed_menu.addAction(label, lambda *a, speed=s: self._set_speed(speed))

        volume_menu = menu.addMenu(tr("ctx_volume", "Volume"))
        volume_menu.setStyleSheet(AppStyles.player_menu_bar_style())
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
        aspect_menu.setStyleSheet(AppStyles.player_menu_bar_style())
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
            # 播放队列与控制入口
            menu.addAction(tr("ctx_playback_queue", "Playback Queue..."), lambda *a: self._show_playback_queue_dialog())

            audio_menu = menu.addMenu(tr("ctx_audio_track", "Audio Track"))
            audio_menu.setStyleSheet(AppStyles.player_menu_bar_style())
            self._populate_audio_menu(audio_menu)

            # 音频调整入口
            menu.addAction(tr("ctx_audio_eq", "Audio Equalizer..."), lambda *a: self._show_audio_eq_dialog())

            sub_menu = menu.addMenu(tr("ctx_subtitle", "Subtitle"))
            sub_menu.setStyleSheet(AppStyles.player_menu_bar_style())
            self._populate_subtitle_menu(sub_menu)

            # 视频图像调整入口
            menu.addAction(tr("ctx_video_eq", "Video Equalizer..."), lambda *a: self._show_video_eq_dialog())

        if is_playing and self._is_audio_only():
            vis_menu = menu.addMenu(tr("ctx_audio_visual", "音频可视化"))
            vis_menu.setStyleSheet(AppStyles.player_menu_bar_style())
            self._populate_visual_menu(vis_menu)

            lyrics_menu = menu.addMenu(tr("ctx_lyrics", "歌词"))
            lyrics_menu.setStyleSheet(AppStyles.player_menu_bar_style())
            self._populate_lyrics_menu(lyrics_menu)

        menu.addSeparator()

        if is_playing:
            menu.addAction(tr("ctx_screenshot", "Screenshot\tS"), lambda *a: self._take_screenshot())

        menu.addAction(tr("ctx_fullscreen", "Fullscreen\tF11"), lambda *a: self.window.toggle_fullscreen())
        menu.addAction(tr("ctx_pip", "Picture-in-Picture\tP"), lambda *a: self.window.pip_ctrl.toggle())

        menu.addSeparator()

        view_menu = menu.addMenu(tr("ctx_view", "View"))
        view_menu.setStyleSheet(AppStyles.player_menu_bar_style())
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
            from PySide6.QtWidgets import QApplication
            from PySide6.QtGui import QPixmap

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

            from PySide6.QtCore import QTimer
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
        menu.addAction(tr("ctx_download_subtitle", "Download Subtitle..."), lambda *a: self._download_subtitle())
        menu.addAction(tr("ctx_subtitle_style", "Subtitle Style..."), lambda *a: self._show_subtitle_style_dialog())
        menu.addSeparator()
        # 字幕可见性切换
        sub_visible = pc.get_sub_visibility() if hasattr(pc, 'get_sub_visibility') else True
        vis_act = menu.addAction(tr("ctx_sub_visibility", "Show Subtitle"))
        vis_act.setCheckable(True)
        vis_act.setChecked(sub_visible)
        vis_act.triggered.connect(lambda *a: self._toggle_sub_visibility())
        # 字幕延迟/缩放/位置快捷调整
        delay_menu = menu.addMenu(tr("ctx_sub_delay", "Subtitle Delay"))
        delay_menu.addAction('-0.5s', lambda *a: self._adjust_sub_delay(-0.5))
        delay_menu.addAction('-0.1s', lambda *a: self._adjust_sub_delay(-0.1))
        delay_menu.addAction('+0.1s', lambda *a: self._adjust_sub_delay(0.1))
        delay_menu.addAction('+0.5s', lambda *a: self._adjust_sub_delay(0.5))
        scale_menu = menu.addMenu(tr("ctx_sub_scale", "Subtitle Scale"))
        scale_menu.addAction('-0.1', lambda *a: self._adjust_sub_scale(-0.1))
        scale_menu.addAction('+0.1', lambda *a: self._adjust_sub_scale(0.1))
        scale_menu.addAction('1.0', lambda *a: self._set_sub_scale(1.0))
        pos_menu = menu.addMenu(tr("ctx_sub_pos", "Subtitle Position"))
        pos_menu.addAction(tr("ctx_sub_pos_up", "Up"), lambda *a: self._adjust_sub_pos(5))
        pos_menu.addAction(tr("ctx_sub_pos_down", "Down"), lambda *a: self._adjust_sub_pos(-5))
        pos_menu.addAction(tr("ctx_sub_pos_reset", "Reset"), lambda *a: self._set_sub_pos(100))

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
        from PySide6.QtWidgets import QMenu
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
        from PySide6.QtWidgets import QMenu
        from ui.styles import AppStyles
        menu = QMenu(self.window)
        menu.setStyleSheet(AppStyles.player_menu_bar_style())
        self._populate_subtitle_menu(menu)
        btn = self.window.sub_track_button
        menu.exec(btn.mapToGlobal(btn.rect().bottomLeft()))

    def show_speed_menu(self):
        from PySide6.QtWidgets import QMenu
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
        from PySide6.QtWidgets import QMenu
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
        from PySide6.QtWidgets import QFileDialog
        tr = self.window.language_manager.tr
        file_path, _ = QFileDialog.getOpenFileName(
            self.window, tr("ctx_load_subtitle", "Load Subtitle..."), '',
            tr("ctx_subtitle_files", "Subtitle Files") + " (*.srt *.ass *.ssa *.sub *.idx *.vtt *.lrc);;" + tr("ctx_all_files", "All Files") + " (*)"
        )
        if file_path:
            if pc.add_subtitle_file(file_path):
                self.window._show_osd_feedback(f"{tr('ctx_subtitle', 'Subtitle')}: {file_path.split('/')[-1].split(chr(92))[-1]}")

    # ---------- 字幕样式与控制（菜单入口） ----------
    def _show_subtitle_style_dialog(self):
        """打开字幕样式对话框"""
        try:
            from ui.dialogs.subtitle_style_dialog import SubtitleStyleDialog
            if not hasattr(self.window, '_subtitle_style_dialog') or not self.window._subtitle_style_dialog:
                self.window._subtitle_style_dialog = SubtitleStyleDialog(self.window)
            self.window._subtitle_style_dialog.show()
            self.window._subtitle_style_dialog.raise_()
            self.window._subtitle_style_dialog.activateWindow()
        except Exception as e:
            logger.error(f"打开字幕样式对话框失败: {e}")

    def _download_subtitle(self):
        """打开字幕下载对话框"""
        try:
            from ui.dialogs.subtitle_style_dialog import SubtitleDownloadDialog
            # 当前播放的视频文件路径
            video_path = ''
            pc = self.window.player_controller
            if pc and pc.is_playing:
                cur = getattr(pc, 'current_url', '') or getattr(pc, '_current_url', '')
                if cur and not cur.startswith(('http', 'rtp', 'udp', 'rtmp', 'rtsp')):
                    video_path = cur
            dialog = SubtitleDownloadDialog(self.window, video_file_path=video_path)
            dialog.show()
            dialog.raise_()
            dialog.activateWindow()
        except Exception as e:
            logger.error(f"打开字幕下载对话框失败: {e}")

    def _toggle_sub_visibility(self):
        pc = self.window.player_controller
        if not pc or not hasattr(pc, 'toggle_sub_visibility'):
            return
        new_state = pc.toggle_sub_visibility()
        tr = self.window.language_manager.tr
        if hasattr(self.window, '_show_osd_feedback'):
            osd_text = tr('osd_sub_visible', 'Subtitle: On') if new_state else tr('osd_sub_hidden', 'Subtitle: Off')
            self.window._show_osd_feedback(osd_text)

    def _adjust_sub_delay(self, delta: float):
        pc = self.window.player_controller
        if not pc or not hasattr(pc, 'adjust_sub_delay'):
            return
        new_delay = pc.adjust_sub_delay(delta)
        tr = self.window.language_manager.tr
        if hasattr(self.window, '_show_osd_feedback'):
            self.window._show_osd_feedback(f"{tr('osd_sub_delay', 'Subtitle Delay')}: {new_delay:+.3f}s")

    def _adjust_sub_scale(self, delta: float):
        pc = self.window.player_controller
        if not pc or not hasattr(pc, 'adjust_sub_scale'):
            return
        new_scale = pc.adjust_sub_scale(delta)
        tr = self.window.language_manager.tr
        if hasattr(self.window, '_show_osd_feedback'):
            self.window._show_osd_feedback(f"{tr('osd_sub_scale', 'Subtitle Scale')}: {new_scale:.2f}x")

    def _set_sub_scale(self, scale: float):
        pc = self.window.player_controller
        if not pc or not hasattr(pc, 'set_sub_scale'):
            return
        pc.set_sub_scale(scale)
        tr = self.window.language_manager.tr
        if hasattr(self.window, '_show_osd_feedback'):
            self.window._show_osd_feedback(f"{tr('osd_sub_scale', 'Subtitle Scale')}: {scale:.2f}x")

    def _adjust_sub_pos(self, delta: int):
        pc = self.window.player_controller
        if not pc or not hasattr(pc, 'get_sub_pos') or not hasattr(pc, 'set_sub_pos'):
            return
        new_pos = max(0, min(100, pc.get_sub_pos() + delta))
        pc.set_sub_pos(new_pos)
        tr = self.window.language_manager.tr
        if hasattr(self.window, '_show_osd_feedback'):
            self.window._show_osd_feedback(f"{tr('osd_sub_pos', 'Subtitle Position')}: {new_pos}")

    def _set_sub_pos(self, pos: int):
        pc = self.window.player_controller
        if not pc or not hasattr(pc, 'set_sub_pos'):
            return
        pc.set_sub_pos(pos)
        tr = self.window.language_manager.tr
        if hasattr(self.window, '_show_osd_feedback'):
            self.window._show_osd_feedback(f"{tr('osd_sub_pos', 'Subtitle Position')}: {pos}")

    def toggle_subtitle_visibility(self):
        """供快捷键调用"""
        pc = self.window.player_controller
        if not pc or not pc.is_playing:
            return
        self._toggle_sub_visibility()

    def adjust_subtitle_delay(self, delta: float):
        """供快捷键调用"""
        pc = self.window.player_controller
        if not pc or not pc.is_playing:
            return
        self._adjust_sub_delay(delta)

    def adjust_subtitle_scale(self, delta: float):
        """供快捷键调用"""
        pc = self.window.player_controller
        if not pc or not pc.is_playing:
            return
        self._adjust_sub_scale(delta)

    # ---------- 视频图像调整 ----------
    def _show_video_eq_dialog(self):
        """打开视频图像调整对话框"""
        try:
            from ui.dialogs.video_eq_dialog import VideoEqualizerDialog
            if not hasattr(self.window, '_video_eq_dialog') or not self.window._video_eq_dialog:
                self.window._video_eq_dialog = VideoEqualizerDialog(self.window)
            self.window._video_eq_dialog.show()
            self.window._video_eq_dialog.raise_()
            self.window._video_eq_dialog.activateWindow()
        except Exception as e:
            logger.error(f"打开视频 EQ 对话框失败: {e}")

    def adjust_video_eq(self, key: str, delta: float):
        """相对调整图像参数（供快捷键调用）
        key: brightness/contrast/saturation/hue/gamma（int 步进）
              sharpness（float 步进）
        """
        pc = self.window.player_controller
        if not pc or not pc.is_playing or not hasattr(pc, 'adjust_video_eq'):
            return
        new_v = pc.adjust_video_eq(key, delta)
        tr = self.window.language_manager.tr
        if hasattr(self.window, '_show_osd_feedback'):
            label_key = f'osd_video_{key}'
            if key == 'sharpness':
                self.window._show_osd_feedback(f"{tr(label_key, 'Sharpness')}: {new_v:+.2f}")
            else:
                self.window._show_osd_feedback(f"{tr(label_key, key.capitalize())}: {int(new_v):+d}")

    def cycle_video_rotate(self, step: int = 90):
        """循环切换画面旋转角度（0→90→180→270→0）"""
        pc = self.window.player_controller
        if not pc or not pc.is_playing or not hasattr(pc, 'get_video_rotate'):
            return
        cur = pc.get_video_rotate()
        new_degree = (cur + step) % 360
        pc.set_video_rotate(new_degree)
        tr = self.window.language_manager.tr
        if hasattr(self.window, '_show_osd_feedback'):
            self.window._show_osd_feedback(f"{tr('osd_video_rotate', 'Rotate')}: {new_degree}°")

    def toggle_video_flip(self):
        """循环切换画面翻转模式（无→水平→垂直→双向→无）"""
        pc = self.window.player_controller
        if not pc or not pc.is_playing or not hasattr(pc, 'get_video_flip'):
            return
        cur = pc.get_video_flip() or ''
        order = ['', 'horizontal', 'vertical', 'both']
        try:
            idx = order.index(cur)
        except ValueError:
            idx = -1
        new_mode = order[(idx + 1) % len(order)]
        pc.set_video_flip(new_mode)
        tr = self.window.language_manager.tr
        if hasattr(self.window, '_show_osd_feedback'):
            label_map = {
                '': tr('video_eq_flip_none', 'None'),
                'horizontal': tr('video_eq_flip_horizontal', 'Horizontal'),
                'vertical': tr('video_eq_flip_vertical', 'Vertical'),
                'both': tr('video_eq_flip_both', 'Both'),
            }
            self.window._show_osd_feedback(f"{tr('osd_video_flip', 'Flip')}: {label_map.get(new_mode, new_mode)}")

    def apply_video_eq_on_load(self):
        """在文件加载时应用已保存的视频 EQ 配置
        由播放器在加载新文件后调用；若启用 reset_on_new_file 则重置
        """
        try:
            cfg = self.window.config.load_video_eq()
        except Exception:
            return
        pc = self.window.player_controller
        if not pc or not hasattr(pc, 'apply_video_eq'):
            return
        if cfg.get('reset_on_new_file', False):
            pc.reset_video_eq()
            pc.set_video_rotate(0)
            pc.set_video_flip('')
            pc.clear_video_crop()
            return
        # 应用保存的图像参数
        eq = {k: cfg.get(k, 0) for k in ('brightness', 'contrast', 'saturation', 'hue', 'gamma', 'sharpness')}
        eq['video_rotate'] = cfg.get('video_rotate', 0)
        eq['video_flip'] = cfg.get('video_flip', '')
        pc.apply_video_eq(eq)

    # ---------- 音频系统增强 ----------
    def _show_audio_eq_dialog(self):
        """打开音频调整对话框"""
        try:
            from ui.dialogs.audio_eq_dialog import AudioEqualizerDialog
            if not hasattr(self.window, '_audio_eq_dialog') or not self.window._audio_eq_dialog:
                self.window._audio_eq_dialog = AudioEqualizerDialog(self.window)
            self.window._audio_eq_dialog.show()
            self.window._audio_eq_dialog.raise_()
            self.window._audio_eq_dialog.activateWindow()
        except Exception as e:
            logger.error(f"打开音频 EQ 对话框失败: {e}")

    def adjust_audio_delay(self, delta: float):
        """相对调整音频延迟（供快捷键调用）"""
        pc = self.window.player_controller
        if not pc or not pc.is_playing or not hasattr(pc, 'adjust_audio_delay'):
            return
        new_v = pc.adjust_audio_delay(delta)
        tr = self.window.language_manager.tr
        if hasattr(self.window, '_show_osd_feedback'):
            self.window._show_osd_feedback(f"{tr('osd_audio_delay', 'Audio Delay')}: {new_v:+.3f}s")

    def adjust_audio_pitch(self, delta: float):
        """相对调整音调补偿（供快捷键调用）"""
        pc = self.window.player_controller
        if not pc or not pc.is_playing or not hasattr(pc, 'adjust_audio_pitch'):
            return
        new_v = pc.adjust_audio_pitch(delta)
        tr = self.window.language_manager.tr
        if hasattr(self.window, '_show_osd_feedback'):
            self.window._show_osd_feedback(f"{tr('osd_audio_pitch', 'Pitch')}: {new_v:.2f}")

    def apply_audio_eq_on_load(self):
        """在文件加载时应用已保存的音频 EQ 配置"""
        try:
            cfg = self.window.config.load_audio_eq()
        except Exception:
            return
        pc = self.window.player_controller
        if not pc or not hasattr(pc, 'apply_audio_eq'):
            return
        if cfg.get('reset_on_new_file', False):
            pc.reset_audio_eq()
            return
        pc.apply_audio_eq(cfg)

    # ---------- 播放队列与控制 ----------
    def _show_playback_queue_dialog(self):
        """打开播放队列与控制对话框"""
        try:
            from ui.dialogs.playback_queue_dialog import PlaybackQueueDialog
            if not hasattr(self.window, '_playback_queue_dialog') or not self.window._playback_queue_dialog:
                self.window._playback_queue_dialog = PlaybackQueueDialog(self.window)
            self.window._playback_queue_dialog.show()
            self.window._playback_queue_dialog.raise_()
            self.window._playback_queue_dialog.activateWindow()
        except Exception as e:
            logger.error(f"打开播放队列对话框失败: {e}")

    def get_queue_controller(self):
        return getattr(self.window, 'file_queue_ctrl', None)

    def cycle_queue_mode(self):
        """循环切换队列模式"""
        qc = self.get_queue_controller()
        if not qc:
            return
        try:
            new_mode = qc.cycle_queue_mode()
            tr = self.window.language_manager.tr
            labels = {
                'none': tr('playback_queue_mode_none', 'No Loop'),
                'single': tr('playback_queue_mode_single', 'Loop Single File'),
                'all': tr('playback_queue_mode_all', 'Loop List'),
                'shuffle': tr('playback_queue_mode_shuffle', 'Shuffle'),
            }
            osd_text = f"{tr('osd_queue_mode', 'Queue Mode')}: {labels.get(new_mode, new_mode)}"
            if hasattr(self.window, '_show_osd_feedback'):
                self.window._show_osd_feedback(osd_text)
        except Exception as e:
            logger.debug(f"循环切换队列模式失败: {e}")

    def toggle_shuffle(self):
        """切换随机播放开关"""
        qc = self.get_queue_controller()
        if not qc:
            return
        try:
            is_on = qc.toggle_shuffle()
            tr = self.window.language_manager.tr
            key = 'osd_shuffle_on' if is_on else 'osd_shuffle_off'
            osd_text = tr(key, 'Shuffle: On' if is_on else 'Shuffle: Off')
            if hasattr(self.window, '_show_osd_feedback'):
                self.window._show_osd_feedback(osd_text)
        except Exception as e:
            logger.debug(f"切换随机播放失败: {e}")

    def play_next_file(self):
        """播放下一个文件"""
        qc = self.get_queue_controller()
        if not qc:
            return
        try:
            qc.play_next()
            tr = self.window.language_manager.tr
            if hasattr(self.window, '_show_osd_feedback'):
                self.window._show_osd_feedback(tr('osd_play_next', 'Next File'))
        except Exception as e:
            logger.debug(f"播放下一文件失败: {e}")

    def play_previous_file(self):
        """播放上一个文件"""
        qc = self.get_queue_controller()
        if not qc:
            return
        try:
            qc.play_previous()
            tr = self.window.language_manager.tr
            if hasattr(self.window, '_show_osd_feedback'):
                self.window._show_osd_feedback(tr('osd_play_prev', 'Previous File'))
        except Exception as e:
            logger.debug(f"播放上一文件失败: {e}")

    def ab_loop_set_a(self):
        """设置 A-B 循环 A 点"""
        qc = self.get_queue_controller()
        if not qc:
            return
        try:
            pos = qc.ab_loop_set_a()
            if pos is None:
                return
            tr = self.window.language_manager.tr
            if hasattr(self.window, '_show_osd_feedback'):
                self.window._show_osd_feedback(f"{tr('osd_ab_loop_a', 'A Point')}: {pos:.2f}s")
        except Exception as e:
            logger.debug(f"设置 A 点失败: {e}")

    def ab_loop_set_b(self):
        """设置 A-B 循环 B 点"""
        qc = self.get_queue_controller()
        if not qc:
            return
        try:
            pos = qc.ab_loop_set_b()
            if pos is None:
                return
            tr = self.window.language_manager.tr
            if hasattr(self.window, '_show_osd_feedback'):
                self.window._show_osd_feedback(f"{tr('osd_ab_loop_b', 'B Point')}: {pos:.2f}s")
        except Exception as e:
            logger.debug(f"设置 B 点失败: {e}")

    def ab_loop_clear(self):
        """清除 A-B 循环"""
        qc = self.get_queue_controller()
        if not qc:
            return
        try:
            qc.ab_loop_clear()
            tr = self.window.language_manager.tr
            if hasattr(self.window, '_show_osd_feedback'):
                self.window._show_osd_feedback(tr('osd_ab_loop_cleared', 'A-B Loop cleared'))
        except Exception as e:
            logger.debug(f"清除 A-B 循环失败: {e}")

    def frame_step(self):
        """前进一帧"""
        qc = self.get_queue_controller()
        if not qc:
            return
        try:
            qc.frame_step()
            tr = self.window.language_manager.tr
            if hasattr(self.window, '_show_osd_feedback'):
                self.window._show_osd_feedback(f"{tr('osd_frame_step', 'Frame')} >>")
        except Exception as e:
            logger.debug(f"前进一帧失败: {e}")

    def frame_back_step(self):
        """后退一帧"""
        qc = self.get_queue_controller()
        if not qc:
            return
        try:
            qc.frame_back_step()
            tr = self.window.language_manager.tr
            if hasattr(self.window, '_show_osd_feedback'):
                self.window._show_osd_feedback(f"<< {tr('osd_frame_step', 'Frame')}")
        except Exception as e:
            logger.debug(f"后退一帧失败: {e}")

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

    def _is_audio_only(self):
        pc = self.window.player_controller
        if not pc or not pc.is_playing:
            return False
        if hasattr(pc, 'audio_visual') and pc.audio_visual:
            return pc.audio_visual.is_audio_only
        return False

    def _populate_visual_menu(self, menu):
        from services.audio_visual_service import AUDIO_VISUAL_STYLES, STYLE_KEYS
        pc = self.window.player_controller
        tr = self.window.language_manager.tr
        current_style = 'none'
        if pc and hasattr(pc, 'audio_visual') and pc.audio_visual:
            current_style = pc.audio_visual.current_style

        for key in STYLE_KEYS:
            style = AUDIO_VISUAL_STYLES[key]
            label = tr(style['name_key'], style['name_default'])
            if key == current_style:
                label += " ✓"
            menu.addAction(label, lambda *a, k=key: self._set_visual_style(k))

        menu.addSeparator()

        random_label = tr("audio_vis_random", "随机效果")
        if current_style == 'random':
            random_label += " ✓"
        menu.addAction(random_label, lambda *a: self._set_visual_style('random'))

        menu.addSeparator()

        off_style = AUDIO_VISUAL_STYLES['none']
        off_label = tr(off_style['name_key'], off_style['name_default'])
        if current_style == 'none':
            off_label += " ✓"
        menu.addAction(off_label, lambda *a: self._set_visual_style('none'))

    def _set_visual_style(self, style_key):
        pc = self.window.player_controller
        if not pc or not hasattr(pc, 'audio_visual') or not pc.audio_visual:
            return
        tr = self.window.language_manager.tr
        if style_key == 'random':
            pc.audio_visual.apply_random_style()
        else:
            pc.audio_visual.apply_visual_style(style_key)
        pc.audio_visual.save_current_style()
        display = pc.audio_visual.get_style_display_name(pc.audio_visual.current_style, self.window.language_manager)
        if hasattr(self.window, '_show_osd_feedback'):
            self.window._show_osd_feedback(f"{tr('osd_audio_visual', '音频可视化')}: {display}")

    def _populate_lyrics_menu(self, menu):
        tr = self.window.language_manager.tr
        show_label = tr("ctx_show_lyrics", "显示歌词")
        menu.addAction(show_label, lambda *a: self._toggle_lyrics(True))
        hide_label = tr("ctx_hide_lyrics", "隐藏歌词")
        menu.addAction(hide_label, lambda *a: self._toggle_lyrics(False))
        menu.addSeparator()
        load_label = tr("ctx_load_lyrics", "加载外部歌词...")
        menu.addAction(load_label, lambda *a: self._load_external_lyrics())

    def _toggle_lyrics(self, show):
        if not hasattr(self.window, '_lyrics_widget') or not self.window._lyrics_widget:
            self._create_lyrics_widget()
        lw = self.window._lyrics_widget
        if show:
            vf = self.window.video_frame
            if vf:
                lw.setGeometry(0, 0, vf.width(), vf.height())
            lw.show()
            lw.raise_()
            lw.start()
            self._refresh_lyrics()
        else:
            lw.stop()
            lw.hide()

    def _create_lyrics_widget(self):
        from ui.lyrics_widget import LyricsWidget
        lw = LyricsWidget(self.window.video_frame)
        lw.hide()
        self.window._lyrics_widget = lw

    def _refresh_lyrics(self):
        if not hasattr(self.window, '_lyrics_widget') or not self.window._lyrics_widget:
            return
        ch = self.window.current_channel
        if not ch:
            return
        url = ch.get('url', '')
        if not url:
            return
        from services.audio_visual_service import extract_lyrics
        lyrics = extract_lyrics(url)
        if lyrics:
            self.window._lyrics_widget.set_lyrics(lyrics, is_lrc='[' in lyrics)
        else:
            tr = self.window.language_manager.tr
            self.window._lyrics_widget.set_lyrics(tr("no_lyrics", "未找到内嵌歌词"), is_lrc=False)

    def _load_external_lyrics(self):
        from PySide6.QtWidgets import QFileDialog
        tr = self.window.language_manager.tr
        file_path, _ = QFileDialog.getOpenFileName(
            self.window, tr("ctx_load_lyrics", "加载外部歌词..."), '',
            tr("lyrics_files", "歌词文件") + " (*.lrc *.txt);;" + tr("all_files", "所有文件") + " (*)"
        )
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    lyrics = f.read()
                if not hasattr(self.window, '_lyrics_widget') or not self.window._lyrics_widget:
                    self._create_lyrics_widget()
                is_lrc = file_path.lower().endswith('.lrc') or '[' in lyrics
                self.window._lyrics_widget.set_lyrics(lyrics, is_lrc=is_lrc)
                self.window._lyrics_widget.show()
                self.window._lyrics_widget.raise_()
                self.window._lyrics_widget.start()
            except Exception:
                pass