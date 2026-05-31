import os
from typing import Dict, Any, Optional
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import QTimer
from core.play_state import PlayMode
from core.log_manager import global_logger as logger
from controllers.main_window_protocol import MainWindowProtocol
from ui.styles import AppStyles
from services.fcc_service import FCCService


class PlaybackController:

    def __init__(self, main_window: MainWindowProtocol):
        self.window: MainWindowProtocol = main_window
        self._is_muted = False
        self._pre_mute_volume = 0
        self.current_channel: Optional[Dict[str, Any]] = None
        self._is_switching = False
        self._live_timeshift_seconds = 0
        self._last_program_id = None
        self.fcc = FCCService()

    def toggle_play(self):
        pc = getattr(self.window, 'player_controller', None)
        if not pc:
            return
        if pc.is_paused or pc.is_playing:
            pc.pause()
        elif self.current_channel or getattr(self.window, 'current_channel', None):
            ch = self.current_channel or self.window.current_channel
            self.play_channel(ch)

    def stop_playback(self):
        self.fcc.on_stop()
        if hasattr(self.window, 'player_controller') and self.window.player_controller:
            self.window.player_controller.stop()

        if hasattr(self.window, 'video_widget') and self.window.video_widget:
            self.window.video_widget.hide()
        if hasattr(self.window, 'video_placeholder') and self.window.video_placeholder:
            self.window.video_placeholder.show()

            from utils.general_utils import get_icon_path
            ico_path = get_icon_path()
            if os.path.exists(ico_path):
                icon = QIcon(ico_path)
                from PyQt6.QtWidgets import QApplication
                screen = QApplication.primaryScreen()
                dpr = screen.devicePixelRatio() if screen else 1.0
                size = int(256 * dpr)
                pixmap = icon.pixmap(size, size, QIcon.Mode.Normal, QIcon.State.On)
                if not pixmap.isNull():
                    pixmap.setDevicePixelRatio(dpr)
                    self.window.video_placeholder.setPixmap(pixmap)
                else:
                    self.window.video_placeholder.setText("")
            else:
                self.window.video_placeholder.setText("")

        self.current_channel = None
        self.window.play_state.set_idle()

        self._reset_ui_to_initial_state()

        if hasattr(self.window, 'language_manager'):
            tr = self.window.language_manager.tr
            self.window.status_bar_show_message(tr('playback_stopped', 'Playback stopped'))

    def _reset_ui_to_initial_state(self):
        ui_elements = {
            'play_button': ("play", "setIcon_name"),
            'channel_name': ("no_channel_selected,No Channel Selected", "setText_tr"),
            'current_program': ("select_channel_to_play,Select a channel to play", "setText_tr"),
            'channel_logo': (None, "clear_pixmap"),
            'video_info': ("not_playing,Not Playing", "setText_tr"),
            'audio_info': ("--", "setText"),
            'network_info': ("--", "setText"),
            'program_desc': ("open_playlist_or_import,Open playlist or import file", "setText_tr"),
            'time_label': ("--:-- - --:--", "setText"),
            'remain_label': ("waiting_to_play,Waiting to play", "setText_tr"),
            'progress_start': ("--:--", "setText"),
            'progress_end': ("--:--", "setText"),
        }

        btn_color = AppStyles._get_colors().get('player_panel_text', AppStyles._safe_fallback('player_panel_text'))

        for attr_name, (value, action) in ui_elements.items():
            if not hasattr(self.window, attr_name):
                continue

            element = getattr(self.window, attr_name)

            if action == "setText":
                element.setText(value)
            elif action == "setIcon_name":
                icon_path = AppStyles.get_icon(value, btn_color)
                if icon_path:
                    element.setIcon(QIcon(icon_path))
            elif action == "setText_tr" and hasattr(self.window, 'language_manager'):
                tr = self.window.language_manager.tr
                parts = value.split(',', 1)
                key = parts[0]
                fallback = parts[1] if len(parts) > 1 else key
                element.setText(tr(key, fallback) or fallback)
            elif action == "clear_pixmap":
                from utils.general_utils import set_default_channel_logo
                set_default_channel_logo(element, element.width() or 100, element.height() or 36)

        if hasattr(self.window, 'program_progress') and hasattr(self.window, '_set_progress_value'):
            self.window._set_progress_value(0)
        if hasattr(self.window, 'program_progress'):
            self.window.program_progress.setRange(0, 3600)
        if hasattr(self.window, '_progress_total_seconds'):
            self.window._progress_total_seconds = 3600
        if hasattr(self.window, '_progress_time_mode'):
            self.window._progress_time_mode = 'hour'
        if hasattr(self.window, '_progress_program_start'):
            self.window._progress_program_start = None
        if hasattr(self.window, '_progress_program_end'):
            self.window._progress_program_end = None
        if hasattr(self.window, 'current_channel'):
            self.window.current_channel = None

    def set_volume(self, value: int):
        if hasattr(self.window, 'player_controller') and self.window.player_controller:
            self.window.player_controller.set_volume(value)
            if not self._is_muted:
                self._update_volume_icon(value)

    def toggle_mute(self):
        if not self.window.player_controller:
            return

        if self._is_muted:
            self._is_muted = False
            self.window.player_controller.set_volume(self._pre_mute_volume)
            if self.window.volume_slider:
                self.window.volume_slider.blockSignals(True)
                self.window.volume_slider.setValue(self._pre_mute_volume)
                self.window.volume_slider.blockSignals(False)
            self._update_volume_icon(self._pre_mute_volume)
        else:
            self._is_muted = True
            self._pre_mute_volume = self.window.player_controller.get_volume()
            self.window.player_controller.set_volume(0)
            if self.window.volume_slider:
                self.window.volume_slider.blockSignals(True)
                self.window.volume_slider.setValue(0)
                self.window.volume_slider.blockSignals(False)
            self._update_volume_icon(0)

    def _update_volume_icon(self, volume: int):
        if not self.window.volume_button:
            return

        color = AppStyles._get_colors().get('player_panel_text', AppStyles._safe_fallback('player_panel_text'))
        if volume == 0:
            icon_name = 'volume_mute'
        elif volume < 50:
            icon_name = 'volume_low'
        else:
            icon_name = 'volume'
        icon_path = AppStyles.get_icon(icon_name, color)
        if icon_path:
            self.window.volume_button.setIcon(QIcon(icon_path))

    def play_channel(self, channel: Dict[str, Any]):
        if self._is_switching:
            from core.log_manager import global_logger as logger
            logger.debug("play_channel: 忽略重复的频道切换请求")
            return

        self._is_switching = True

        try:
            from core.log_manager import global_logger as logger
            logger.debug(f"play_channel: 开始切换频道 {channel.get('name', '?')} url={channel.get('url', '?')}")
            self._do_play_channel(channel)
        finally:
            QTimer.singleShot(500, lambda: setattr(self, '_is_switching', False))

    def _do_play_channel(self, channel: Dict[str, Any]):
        if not (hasattr(self.window, 'player_controller') and self.window.player_controller and channel):
            return

        self._live_timeshift_seconds = 0
        self._last_program_id = None

        if self.window.play_state.is_catchup_or_timeshift:
            self._exit_catchup_mode()

        if hasattr(self.window, 'player_controller') and self.window.player_controller:
            try:
                current_speed = self.window.player_controller.get_speed()
                if abs(current_speed - 1.0) > 0.01:
                    self.window.player_controller.set_speed(1.0)
                    if hasattr(self.window, 'speed_button'):
                        self.window.speed_button.setText("1.0x")
                    if hasattr(self.window, '_show_osd_feedback'):
                        tr = self.window.language_manager.tr
                        self.window._show_osd_feedback(f"{tr('osd_speed', 'Speed')}: 1.0x")
            except Exception as e:
                logger.debug(f"恢复播放速度失败: {e}")

        url = channel.get('url', '')
        name = channel.get('name', '')

        self.fcc.on_channel_change(url)
        self.window.player_controller.play(url)
        self.current_channel = channel
        self.window.play_state.set_live()

        self._prefetch_adjacent_channels(channel)

    def _exit_catchup_mode(self):
        catchup_ctrl = getattr(self.window, 'catchup_ctrl', None)
        if catchup_ctrl:
            catchup_ctrl._clear_catchup_state(set_state='live')

        if hasattr(self.window, 'exit_catchup_button'):
            self.window.exit_catchup_button.hide()

        for attr in ['_catchup_start_time', '_catchup_start_progress',
                     '_target_catchup_progress', '_disable_progress_auto_update',
                     '_pending_catchup_progress',
                     '_timeshift_enter_time_ms', '_timeshift_start_time']:
            if hasattr(self.window, attr):
                setattr(self.window, attr, None if 'time' in attr or 'progress' in attr or 'shift' in attr or 'range' in attr else False)
            if hasattr(self, attr):
                setattr(self, attr, None if 'time' in attr or 'progress' in attr or 'shift' in attr or 'range' in attr else False)

        if hasattr(self.window, 'program_progress'):
            self.window.program_progress.setValue(0)
            self.window.program_progress.setRange(0, 3600)

        if hasattr(self.window, '_progress_total_seconds'):
            self.window._progress_total_seconds = 3600
        if hasattr(self.window, '_progress_time_mode'):
            self.window._progress_time_mode = 'hour'
        if hasattr(self.window, '_progress_program_start'):
            self.window._progress_program_start = None
        if hasattr(self.window, '_progress_program_end'):
            self.window._progress_program_end = None

        if hasattr(self.window, 'progress_start'):
            self.window.progress_start.setText("--:--")
        if hasattr(self.window, 'progress_end'):
            self.window.progress_end.setText("--:--")

        if hasattr(self.window, 'current_program'):
            self.window.current_program.setText("")
        if hasattr(self.window, 'remain_label') and hasattr(self.window, 'language_manager'):
            self.window.remain_label.setText(
                self.window.language_manager.tr("waiting_to_play", "Waiting to play..."))
        if hasattr(self.window, 'time_label'):
            from datetime import datetime
            current_time = datetime.now().strftime("%H:%M")
            self.window.time_label.setText(current_time)

    @property
    def is_playing(self) -> bool:
        if self.window.play_state.is_idle:
            return False
        window_ch = getattr(self.window, 'current_channel', None)
        return (self.current_channel is not None) or (window_ch is not None)

    def _prefetch_adjacent_channels(self, current_channel):
        try:
            channel_list = None
            if hasattr(self.window, 'playlist_tab') and self.window.playlist_tab:
                if self.window.playlist_tab.currentIndex() == 1:
                    channel_list = self.window.local_channel_list
                else:
                    channel_list = self.window.sub_channel_list
            elif hasattr(self.window, 'channel_list'):
                channel_list = self.window.channel_list
            if not channel_list:
                return

            current_row = channel_list.currentRow()
            total = channel_list.count()
            if total <= 1:
                return

            next_urls = []
            for delta in [1, -1]:
                adj_row = (current_row + delta) % total
                if adj_row == current_row:
                    continue
                item = channel_list.item(adj_row)
                if item:
                    ch_data = item.data(256)
                    if ch_data and isinstance(ch_data, dict):
                        adj_url = ch_data.get('url', '')
                        if adj_url:
                            next_urls.append(adj_url)

            if not next_urls:
                return

            dns_prefetcher = getattr(self.window, '_dns_prefetcher', None)
            conn_preheater = getattr(self.window, '_connection_preheater', None)

            for url in next_urls:
                if dns_prefetcher:
                    dns_prefetcher.prefetch(url)
                if conn_preheater:
                    conn_preheater.preheat(url)

            logger.debug(f"预取{len(next_urls)}个相邻频道的DNS/TCP连接")
        except Exception as e:
            logger.debug(f"预取相邻频道失败(非致命): {e}")

    @property
    def is_muted_state(self) -> bool:
        return self._is_muted

    def handle_play_state_change(self, is_playing):
        from ui.styles import AppStyles
        from PyQt6.QtGui import QIcon
        from core.log_manager import global_logger as logger

        w = self.window
        tr = w.language_manager.tr
        btn_color = AppStyles._get_colors().get('player_panel_text', AppStyles._safe_fallback('player_panel_text'))
        if is_playing:
            pause_path = AppStyles.get_icon('pause', btn_color)
            if pause_path:
                w.play_button.setIcon(QIcon(pause_path))
            w.pip_ctrl._update_play_btn()
            w._cancel_source_timeout()
            if hasattr(w, 'video_placeholder') and w.video_placeholder:
                w.video_placeholder.hide()
            if hasattr(w, 'video_widget') and w.video_widget and w.video_frame:
                w.video_widget.setGeometry(0, 0, w.video_frame.width(), w.video_frame.height())
                w.video_widget.show()
            w._last_info_key = None
            w.update_timer.start(1000)
            if w._is_local_file():
                if hasattr(w, 'epg_panel') and w.epg_panel:
                    if not hasattr(w, '_epg_hidden_by_local_file'):
                        w._epg_hidden_by_local_file = w.epg_visible
                    w.epg_visible = False
            elif hasattr(w, 'epg_panel') and w.epg_panel:
                if hasattr(w, '_epg_hidden_by_local_file'):
                    was_visible = w._epg_hidden_by_local_file
                    del w._epg_hidden_by_local_file
                    if was_visible:
                        w.epg_visible = True
                elif getattr(w, 'epg_visible', True) and not w.epg_panel.isVisible():
                    w.epg_visible = True
            if w.current_channel:
                channel_name = w.current_channel.get('name', tr('unknown_channel', 'Unknown Channel'))
                if w.play_state.is_catchup_or_timeshift:
                    catchup_playing_text = tr('catchup_playing', '正在回看: {name}')
                    w.status_bar.showMessage(catchup_playing_text.format(name=channel_name))
                    if getattr(w, '_pending_catchup_progress', None) is not None:
                        try:
                            progress_value = w._pending_catchup_progress
                            w._pending_catchup_progress = None
                            w._set_progress_value(progress_value)
                            w._target_catchup_progress = progress_value
                            import time
                            w._catchup_start_time = time.time()
                            w._catchup_start_progress = progress_value
                            logger.debug(f"记录回看开始时间：{w._catchup_start_time}，开始进度：{progress_value}%")
                            logger.debug(f"已设置回看进度条，保存目标值：{progress_value}%，保留禁用标志")
                        except Exception as e:
                            logger.error(f"设置回看进度条失败：{e}")
                else:
                    w.status_bar_show_message(f"{tr('playing', 'Playing')}: {channel_name}")
        else:
            play_path = AppStyles.get_icon('play', btn_color)
            if play_path:
                w.play_button.setIcon(QIcon(play_path))
            w.pip_ctrl._update_play_btn()
            if hasattr(w, 'update_timer'):
                w.update_timer.stop()
            if w.play_state.is_idle:
                return
            if w.current_channel:
                channel_name = w.current_channel.get('name', tr('unknown_channel', 'Unknown Channel'))
                if w.play_state.is_catchup_or_timeshift:
                    catchup_paused_text = tr('catchup_paused', '回看暂停: {name}')
                    w.status_bar_show_message(catchup_paused_text.format(name=channel_name))
                else:
                    w.status_bar_show_message(f"{tr('paused', 'Paused')}: {channel_name}")

    def seek_live(self, position):
        from core.log_manager import global_logger as logger

        w = self.window
        if not w.current_channel or not w.player_controller:
            return

        seek_range = w.player_controller.get_available_seek_range()
        max_back = seek_range.get('max_back', 0)
        cache_duration = seek_range.get('cache_duration', 0)
        buffer_start = seek_range.get('buffer_start', 0)
        buffer_end = seek_range.get('buffer_end', 0)
        time_pos = seek_range.get('time_pos', 0)

        logger.info(f"直播拖动进度条 -> slider={position}s, "
                    f"time_pos={time_pos:.1f}s, buffer={buffer_start:.1f}s~{buffer_end:.1f}s, "
                    f"max_back={max_back}s, mode={getattr(w, '_progress_time_mode', '?')}")

        if max_back == 0 and cache_duration < 5:
            logger.warning(f"直播拖动进度条 -> 无法回退（缓冲区为空，cache={cache_duration:.1f}s）")
            w.status_bar_show_message(w.language_manager.tr("cannot_seek_live", "无法回退：直播流缓冲区不足"))
            return

        target_pos = w._map_slider_to_stream_position(position, seek_range)

        logger.info(f"直播拖动进度条 -> 映射后 target_pos={target_pos:.1f}s, "
                    f"clamp后={max(buffer_start, min(target_pos, buffer_end)):.1f}s")

        if target_pos < buffer_start:
            catchup_source = w.current_channel.get('catchup_source', '') if w.current_channel else ''
            if catchup_source and getattr(w, '_progress_time_mode', None) == 'epg' and w._progress_program_start:
                w._start_live_timeshift_from_progress(position, catchup_source)
                return
            elif catchup_source:
                w.status_bar_show_message(
                    w.language_manager.tr(
                        "timeshift_beyond_cache_no_epg",
                        "超出缓冲范围，无节目信息，无法自动时移"
                    )
                )
            else:
                w.status_bar_show_message(
                    w.language_manager.tr(
                        "timeshift_beyond_cache",
                        "超出缓冲范围，无法跳转到更早时间"
                    )
                )
            return

        target_pos = max(buffer_start, min(target_pos, buffer_end))

        timeshift = getattr(w, '_live_timeshift_seconds', 0)
        if timeshift > 0 and time_pos < 1:
            effective_pos = buffer_end - timeshift
        elif time_pos > 1:
            effective_pos = time_pos
        else:
            effective_pos = buffer_end

        if abs(target_pos - effective_pos) < 1:
            logger.info(f"直播拖动进度条 -> 跳过（目标{target_pos:.1f}s与当前位置{effective_pos:.1f}s差<1s, timeshift={timeshift}s）")
            return

        logger.info(f"直播拖动进度条 -> seek到 {target_pos:.1f}s")

        w.player_controller.seek_absolute(target_pos)

        if target_pos < buffer_end - 1:
            w._live_timeshift_seconds = buffer_end - target_pos
        else:
            w._live_timeshift_seconds = 0
