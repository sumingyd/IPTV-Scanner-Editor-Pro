from typing import Any, Dict

from PySide6.QtCore import QTimer
from core.log_manager import global_logger as logger


class PlaybackMixin:
    """从 IPTVPlayer 提取的播放控制职责"""

    def toggle_osd(self, checked=None):
        self.ui_ctrl.toggle_osd(checked)

    def toggle_play(self):
        self.playback_ctrl.toggle_play()

    def stop_playback(self):
        self.playback_ctrl.stop_playback()

    def set_volume(self, value):
        self.playback_ctrl.set_volume(value)
        if not self._suppress_volume_osd and not self._osd_visible:
            self._show_osd_feedback(f"{self.language_manager.tr('osd_volume', 'Volume')}: {value}%")

    def toggle_mute(self):
        self._suppress_volume_osd = True
        self.playback_ctrl.toggle_mute()
        if not self._osd_visible:
            if self.playback_ctrl.is_muted_state:
                self._show_osd_feedback(self.language_manager.tr('osd_muted', 'Muted'))
            else:
                vol = self.volume_slider.value() if hasattr(self, 'volume_slider') else 0
                self._show_osd_feedback(f"{self.language_manager.tr('osd_volume', 'Volume')}: {vol}%")
        self._suppress_volume_osd = False

    def _show_osd_feedback(self, text: str):
        if hasattr(self, 'player_controller') and self.player_controller:
            self.player_controller.show_osd(text, 2000)

    def play_channel(self, channel):
        if self.playback_ctrl._is_switching:
            return
        self.playback_ctrl.play_channel(channel)
        if channel and channel.get('url'):
            self.favorites_ctrl.on_channel_played(channel)

    def _do_play_channel(self, channel):
        self.playback_ctrl._do_play_channel(channel)

    def on_play_error(self, error_msg):
        tr = self.language_manager.tr
        logger.error(f"播放错误：{error_msg}")
        if self.current_channel:
            channel_name = self.current_channel.get('name', tr('unknown_channel', 'Unknown Channel'))
            self.status_bar_show_message(f"{tr('play_error', 'Play Error')}: {channel_name} - {error_msg}")
        else:
            self.status_bar_show_message(f"{tr('play_error', 'Play Error')}: {error_msg}")

    def _on_reconnect_requested(self, url):
        tr = self.language_manager.tr
        if self.current_channel:
            channel_name = self.current_channel.get('name', '')
            self.status_bar_show_message(
                f"{tr('reconnecting', 'Reconnecting')}: {channel_name} "
                f"({self.player_controller._reconnect_count}/{self.player_controller._max_reconnect})")
        QTimer.singleShot(self.RECONNECT_DELAY_MS, lambda: self._do_reconnect(url))

    def _on_timeshift_continue(self):
        if self.play_state.is_timeshift:
            logger.info("时移流播放到终点，自动续播")
            self.catchup_ctrl.continue_timeshift()

    def _do_reconnect(self, url):
        if self.player_controller._user_stopped:
            return
        if self.current_channel:
            if self.play_state.is_catchup_or_timeshift:
                tr = self.language_manager.tr
                channel_name = self.current_channel.get('name', '')
                logger.info(f"时移/回看播放失败，自动退回直播: {channel_name}")
                self.status_bar_show_message(
                    f"{tr('timeshift_failed_back_to_live', '时移播放失败，退回直播')}: {channel_name}"
                )
            self.playback_ctrl.play_channel(self.current_channel)

    def on_live_media_info_updated(self, info: Dict[str, Any]):
        self.ui_ctrl.on_live_media_info_updated(info)

    def adjust_window_size_to_video(self):
        if not self.player_controller:
            return

        try:
            resolution = self.player_controller.get_video_resolution()
            if not resolution or resolution == "未知":
                return

            parts = resolution.split('x')
            if len(parts) != 2:
                return

            video_width = int(parts[0])
            video_height = int(parts[1])

            if video_width <= 0 or video_height <= 0:
                return

            current_height = self.height()
            current_width = self.width()

            max_video_width = 1920
            if video_width > max_video_width:
                original_video_width = video_width
                video_width = max_video_width
                video_height = int(video_height * (max_video_width / original_video_width))

            scale = current_height / video_height
            new_window_width = int(video_width * scale)
            new_window_width = max(800, min(new_window_width, 1920))

            if abs(new_window_width - current_width) < 50:
                return

            current_geometry = self.geometry()
            center_x = current_geometry.x() + current_geometry.width() // 2
            center_y = current_geometry.y() + current_geometry.height() // 2

            new_x = center_x - new_window_width // 2
            new_y = center_y - current_height // 2

            self.setGeometry(new_x, new_y, new_window_width, current_height)

        except Exception as e:
            logger.debug(f"调整窗口大小异常: {e}")

    def update_media_info(self):
        self.ui_ctrl.update_media_info()

    def _on_playback_position_updated(self, current_time_ms, total_time_ms, position):
        prev_total = getattr(self, '_cached_total_time_ms', 0) or 0
        self._cached_current_time_ms = current_time_ms
        self._cached_total_time_ms = total_time_ms
        self._cached_position = position
        if ((not prev_total or prev_total <= 0) and total_time_ms and total_time_ms > 0
                and self._is_local_file()):
            logger.warning(f"[GOT_DURATION] total={total_time_ms:.0f}ms cur={current_time_ms:.0f}ms pos={position:.4f}")
        self.update_floating_panel_info()

    def update_floating_panel_info(self):
        self.ui_ctrl.update_floating_panel_info()