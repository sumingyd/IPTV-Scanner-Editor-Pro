import os
from typing import Dict, Optional, Any
from PySide6.QtCore import QObject, QTimer
from core.log_manager import global_logger as logger
from ui.multi_screen_widget import MultiScreenWidget, MultiScreenCell


class MultiScreenController(QObject):

    def __init__(self, main_window):
        super().__init__()
        self.window = main_window
        self._widget: Optional[MultiScreenWidget] = None
        self._players: Dict[int, Any] = {}
        self._active = False
        self._info_timer: Optional[QTimer] = None

    @property
    def is_active(self) -> bool:
        return self._active

    @property
    def widget(self) -> Optional[MultiScreenWidget]:
        return self._widget

    def enter_multi_screen(self, count: int = 4):
        if self._active:
            if self._widget and self._widget.grid_count == count:
                return
            self._stop_all_cells()
            self._widget.set_layout(count)
            return

        pip_ctrl = getattr(self.window, 'pip_ctrl', None)
        if pip_ctrl and pip_ctrl.is_active:
            pip_ctrl.toggle()
            logger.info("多画面与PiP互斥：自动退出PiP模式")

        w = self.window
        if not hasattr(w, 'video_frame') or not w.video_frame:
            return

        self._widget = MultiScreenWidget()
        self._widget.cell_channel_dropped.connect(self._on_channel_dropped)
        self._widget.cell_close_requested.connect(self._on_cell_close)
        self._widget.cell_volume_changed.connect(self._on_volume_changed)
        self._widget.cell_audio_track_changed.connect(self._on_audio_track_changed)
        self._widget.cell_clicked.connect(self._on_cell_clicked)
        self._widget.global_mute_toggled.connect(self._on_global_mute_toggled)
        self._widget.set_layout(count)

        self._replace_video_frame(w, self._widget)

        self._active = True
        self._start_info_timer()

        if hasattr(w, 'status_bar_show_message'):
            tr = w.language_manager.tr
            w.status_bar_show_message(tr('multi_screen_entered', '多画面模式'))

    def _replace_video_frame(self, w, new_widget):
        video_frame = w.video_frame
        parent = video_frame.parent()
        if not parent:
            return

        layout = parent.layout()
        if not layout:
            return

        for i in range(layout.count()):
            item = layout.itemAt(i)
            if item and item.widget() == video_frame:
                stretch = layout.stretch(i)
                layout.removeWidget(video_frame)
                video_frame.hide()
                layout.insertWidget(i, new_widget, stretch)
                return

        if hasattr(w, 'top_layout'):
            top_layout = w.top_layout
            for i in range(top_layout.count()):
                item = top_layout.itemAt(i)
                if item and item.widget() == video_frame:
                    stretch = top_layout.stretch(i)
                    top_layout.removeWidget(video_frame)
                    video_frame.hide()
                    top_layout.insertWidget(i, new_widget, stretch)
                    return

    def exit_multi_screen(self):
        if not self._active:
            return

        w = self.window
        self._stop_all_cells()

        if self._info_timer:
            self._info_timer.stop()
            self._info_timer = None

        if self._widget and hasattr(w, 'video_frame'):
            self._restore_video_frame(w, self._widget, w.video_frame)
            w.video_frame.show()

            self._widget.setParent(None)
            self._widget.deleteLater()
            self._widget = None

        self._active = False

        if hasattr(w, 'status_bar_show_message'):
            tr = w.language_manager.tr
            w.status_bar_show_message(tr('multi_screen_exited', '已退出多画面模式'))

    def _restore_video_frame(self, w, old_widget, video_frame):
        parent = old_widget.parent()
        if not parent:
            return

        layout = parent.layout()
        if layout:
            for i in range(layout.count()):
                item = layout.itemAt(i)
                if item and item.widget() == old_widget:
                    stretch = layout.stretch(i)
                    layout.removeWidget(old_widget)
                    layout.insertWidget(i, video_frame, stretch)
                    return

        if hasattr(w, 'top_layout'):
            top_layout = w.top_layout
            for i in range(top_layout.count()):
                item = top_layout.itemAt(i)
                if item and item.widget() == old_widget:
                    stretch = top_layout.stretch(i)
                    top_layout.removeWidget(old_widget)
                    top_layout.insertWidget(i, video_frame, stretch)
                    return

    def toggle(self, count: int = 4):
        if self._active and self._widget and self._widget.grid_count == count:
            self.exit_multi_screen()
        else:
            self.enter_multi_screen(count)

    def play_in_cell(self, index: int, channel: dict):
        if not self._active or not self._widget:
            return

        cell = self._widget.get_cell(index)
        if not cell:
            return

        self._stop_cell(index)

        try:
            from services.mpv_player_service import MpvPlayerController
            player = MpvPlayerController(cell.video_frame)
            cell.player = player

            player.play_error.connect(lambda err, idx=index: self._on_cell_error(idx, err))

            url = channel.get('url', '')
            if url:
                player.play(url)
                player.set_volume(cell._volume_slider.value())

            cell.set_channel(channel)
            self._players[index] = player

        except Exception as e:
            logger.error(f"多画面播放失败 cell={index}: {e}")

    def play_in_empty_cell(self, channel: dict) -> bool:
        if not self._active or not self._widget:
            return False
        cell = self._widget.find_empty_cell()
        if cell:
            self.play_in_cell(cell.index, channel)
            return True
        return False

    def _stop_cell(self, index: int):
        player = self._players.pop(index, None)
        if player:
            try:
                player.stop()
                player.terminate()
            except Exception as e:
                logger.debug(f"停止cell播放器失败: {e}")

        if self._widget:
            cell = self._widget.get_cell(index)
            if cell:
                cell.player = None
                cell.clear_channel()

    def _stop_all_cells(self):
        for index in list(self._players.keys()):
            self._stop_cell(index)

    def _on_channel_dropped(self, index: int, channel: dict):
        self.play_in_cell(index, channel)

    def _on_cell_close(self, index: int):
        self._stop_cell(index)

    def _on_volume_changed(self, index: int, volume: int):
        player = self._players.get(index)
        if player:
            try:
                player.set_volume(volume)
            except Exception:
                pass

        if self._widget:
            cell = self._widget.get_cell(index)
            if cell:
                cell._volume_pct.setText(f"{volume}%")

    def _on_audio_track_changed(self, index: int, track_id: int):
        player = self._players.get(index)
        if player:
            try:
                player.send_command(['aid', str(track_id)])
            except Exception as e:
                logger.debug(f"切换音轨失败: {e}")

    def _on_cell_error(self, index: int, error_msg: str):
        logger.warning(f"多画面cell={index}播放错误: {error_msg}")
        cell = self._widget.get_cell(index) if self._widget else None
        if cell:
            try:
                from PySide6.QtWidgets import QApplication
                QApplication.processEvents()
            except Exception:
                pass

    def _on_cell_clicked(self, index: int):
        pass

    def _on_global_mute_toggled(self, muted: bool):
        for index, player in list(self._players.items()):
            if not player:
                continue
            try:
                if muted:
                    player.set_volume(0)
                else:
                    cell = self._widget.get_cell(index) if self._widget else None
                    vol = cell._volume_slider.value() if cell else 80
                    player.set_volume(vol)
            except Exception:
                pass

    def _start_info_timer(self):
        if self._info_timer:
            self._info_timer.stop()
        self._info_timer = QTimer(self)
        self._info_timer.timeout.connect(self._update_cells_info)
        self._info_timer.start(2000)

    def _update_cells_info(self):
        if not self._active or not self._widget:
            return
        for index, player in list(self._players.items()):
            if not player or not player.is_playing:
                continue
            cell = self._widget.get_cell(index)
            if not cell:
                continue
            try:
                tracks = player.get_track_list('audio')
                if tracks:
                    current_titles = []
                    for i in range(cell._audio_combo.count()):
                        current_titles.append(cell._audio_combo.itemText(i))
                    new_titles = [t.get('title', '') or t.get('lang', '') or self.window.language_manager.tr('ctx_audio_track_n', 'Track {}').format(t.get('id', 0)) for t in tracks]
                    if current_titles != new_titles:
                        cell.set_audio_tracks(tracks, tr=self.window.language_manager.tr)
            except Exception:
                pass

    def terminate(self):
        self._stop_all_cells()
        if self._info_timer:
            self._info_timer.stop()
            self._info_timer = None
        if self._widget:
            self._widget.setParent(None)
            self._widget.deleteLater()
            self._widget = None
        self._active = False
