import os
from typing import Dict, Any, Optional
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import QTimer
from core.play_state import PlayMode
from core.log_manager import global_logger as logger
from controllers.main_window_protocol import MainWindowProtocol
from ui.styles import AppStyles


class PlaybackController:

    def __init__(self, main_window: MainWindowProtocol):
        self.window: MainWindowProtocol = main_window
        self._is_muted = False
        self._pre_mute_volume = 0
        self.current_channel: Optional[Dict[str, Any]] = None
        self._is_switching = False
        self._live_timeshift_seconds = 0
        self._last_program_id = None

    def toggle_play(self):
        pc = getattr(self.window, 'player_controller', None)
        if not pc:
            return
        if pc.is_paused or pc.is_playing:
            pc.pause()

    def stop_playback(self):
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

        btn_color = AppStyles._get_colors().get('player_panel_text', '#ffffff')

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
                self.window.volume_slider.setValue(self._pre_mute_volume)
            self._update_volume_icon(self._pre_mute_volume)
        else:
            self._is_muted = True
            self._pre_mute_volume = self.window.player_controller.get_volume()
            self.window.player_controller.set_volume(0)
            if self.window.volume_slider:
                self.window.volume_slider.setValue(0)
            self._update_volume_icon(0)

    def _update_volume_icon(self, volume: int):
        if not self.window.volume_button:
            return

        color = AppStyles._get_colors().get('player_panel_text', '#ffffff')
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
            except Exception as e:
                logger.debug(f"恢复播放速度失败: {e}")

        url = channel.get('url', '')
        name = channel.get('name', '')

        self.window.player_controller.play(url)
        self.current_channel = channel
        self.window.play_state.set_live()

    def _exit_catchup_mode(self):
        catchup_ctrl = getattr(self.window, 'catchup_ctrl', None)
        if catchup_ctrl:
            catchup_ctrl._clear_catchup_state()

        if hasattr(self.window, 'exit_catchup_button'):
            self.window.exit_catchup_button.hide()

        for attr in ['_catchup_start_time', '_catchup_start_progress',
                     '_target_catchup_progress', '_disable_progress_auto_update',
                     '_pending_catchup_progress',
                     '_ts_max_shift', '_ts_current_offset', '_ts_range',
                     '_timeshift_enter_time_ms', '_timeshift_start_time']:
            if hasattr(self.window, attr):
                delattr(self.window, attr)
            if hasattr(self, attr):
                delattr(self, attr)

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

    @property
    def is_muted_state(self) -> bool:
        return self._is_muted
