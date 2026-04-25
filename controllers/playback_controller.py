"""
播放控制核心 - 负责播放/暂停/停止、音量控制、频道切换等
从 pyqt_player.py 提取的独立模块
"""

import os
from typing import Dict, Any, Optional
from PyQt6.QtWidgets import QLabel, QPushButton, QSlider
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtCore import QTimer


class PlaybackController:
    """播放控制核心 - 管理所有播放相关的逻辑"""

    def __init__(self, main_window):
        self.window = main_window
        self._is_muted = False
        self._pre_mute_volume = 0
        self._is_stopped = True
        self.current_channel: Optional[Dict[str, Any]] = None
        self._is_switching = False
        
        # 回看模式状态
        self.is_catchup_mode = False
        self.catchup_program = None
        self._live_timeshift_seconds = 0
        self._last_program_id = None

    def toggle_play(self):
        """切换播放/暂停"""
        if not self.current_channel:
            return
        if hasattr(self.window, 'player_controller') and self.window.player_controller:
            self.window.player_controller.pause()

    def stop_playback(self):
        """停止播放，恢复到初始状态"""
        if hasattr(self.window, 'player_controller') and self.window.player_controller:
            self.window.player_controller.stop()
        
        # 隐藏视频组件，显示占位符
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
                    self.window.video_placeholder.setText("📺")
            else:
                self.window.video_placeholder.setText("📺")

        # 重置UI元素
        self._reset_ui_to_initial_state()
        
        self.current_channel = None
        self._is_stopped = True
        
        if hasattr(self.window, 'language_manager'):
            tr = self.window.language_manager.tr
            self.window.status_bar_show_message(tr('playback_stopped', 'Playback stopped'))

    def _reset_ui_to_initial_state(self):
        """重置所有UI元素到初始状态"""
        ui_elements = {
            'play_button': ("▶", "setText"),
            'channel_name': ("no_channel_selected", "setText_tr"),
            'current_program': ("select_channel_to_play", "setText_tr"),
            'channel_logo': (None, "clear_pixmap"),
            'video_info': ("not_playing", "setText_tr_prefix"),
            'audio_info': ("🔊 --", "setText"),
            'network_info': ("📡 --", "setText"),
            'program_desc': ("open_playlist_or_import", "setText_tr"),
            'time_label': ("⏱ --:-- - --:--", "setText"),
            'remain_label': ("waiting_to_play", "setText_tr"),
            'progress_start': ("--:--", "setText"),
            'progress_end': ("--:--", "setText"),
        }
        
        for attr_name, (value, action) in ui_elements.items():
            if not hasattr(self.window, attr_name):
                continue
                
            element = getattr(self.window, attr_name)
            
            if action == "setText":
                element.setText(value)
            elif action == "setText_tr" and hasattr(self.window, 'language_manager'):
                tr = self.window.language_manager.tr
                element.setText(tr(value.split(',')[0], value.split(',')[1]) if ',' in value else tr(value))
            elif action == "setText_tr_prefix" and hasattr(self.window, 'language_manager'):
                tr = self.window.language_manager.tr
                element.setText(f"📺 {tr(value)}")
            elif action == "clear_pixmap":
                from utils.general_utils import set_default_channel_logo
                set_default_channel_logo(element, element.width() or 100, element.height() or 36)
        
        # 重置进度条
        if hasattr(self.window, 'program_progress') and hasattr(self.window, '_set_progress_value'):
            self.window._set_progress_value(0)

    def set_volume(self, value: int):
        """设置音量（0-100）"""
        if hasattr(self.window, 'player_controller') and self.window.player_controller:
            self.window.player_controller.set_volume(value)
            if not self._is_muted:
                self._update_volume_icon(value)

    def toggle_mute(self):
        """切换静音/取消静音"""
        if not hasattr(self.window, 'player_controller') or not self.window.player_controller:
            return
            
        if self._is_muted:
            # 取消静音
            self._is_muted = False
            if hasattr(self.window, 'player_controller'):
                self.window.player_controller.set_volume(self._pre_mute_volume)
            if hasattr(self.window, 'volume_slider'):
                self.window.volume_slider.setValue(self._pre_mute_volume)
            self._update_volume_icon(self._pre_mute_volume)
        else:
            # 静音
            self._is_muted = True
            if hasattr(self.window, 'player_controller'):
                self._pre_mute_volume = self.window.player_controller.get_volume()
                self.window.player_controller.set_volume(0)
            if hasattr(self.window, 'volume_slider'):
                self.window.volume_slider.setValue(0)
            if hasattr(self.window, 'volume_button'):
                self.window.volume_button.setText("🔇")

    def _update_volume_icon(self, volume: int):
        """根据音量更新音量图标"""
        if not hasattr(self.window, 'volume_button'):
            return
            
        if volume == 0:
            self.window.volume_button.setText("🔇")
        elif volume < 50:
            self.window.volume_button.setText("🔉")
        else:
            self.window.volume_button.setText("🔊")

    def play_channel(self, channel: Dict[str, Any]):
        """播放指定频道（带防抖动保护）"""
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
        """实际执行频道切换"""
        if not (hasattr(self.window, 'player_controller') and self.window.player_controller and channel):
            return

        self._live_timeshift_seconds = 0
        self._last_program_id = None

        if self.is_catchup_mode or (hasattr(self.window, 'is_catchup_mode') and self.window.is_catchup_mode):
            self._exit_catchup_mode()

        if hasattr(self.window, 'player_controller') and self.window.player_controller:
            try:
                current_speed = self.window.player_controller.get_speed()
                if abs(current_speed - 1.0) > 0.01:
                    self.window.player_controller.set_speed(1.0)
                    if hasattr(self.window, 'speed_button'):
                        self.window.speed_button.setText("1.0x")
            except Exception:
                pass

        url = channel.get('url', '')
        name = channel.get('name', '')

        self.window.player_controller.play(url)
        self.current_channel = channel
        self._is_stopped = False

    def _exit_catchup_mode(self):
        """退出回看模式"""
        self.is_catchup_mode = False
        self.catchup_program = None

        # 优先通过 CatchupController 统一清理状态，避免与其内部状态不同步
        catchup_ctrl = getattr(self.window, 'catchup_ctrl', None)
        if catchup_ctrl:
            catchup_ctrl._clear_catchup_state()
        else:
            # 降级处理：直接操作 window 属性
            if hasattr(self.window, 'is_catchup_mode'):
                self.window.is_catchup_mode = False
            if hasattr(self.window, 'catchup_program'):
                try:
                    delattr(self.window, 'catchup_program')
                except AttributeError:
                    pass

        if hasattr(self.window, 'exit_catchup_button'):
            self.window.exit_catchup_button.hide()

        for attr in ['_catchup_start_time', '_catchup_start_progress',
                     '_target_catchup_progress', '_disable_progress_auto_update',
                     '_pending_catchup_progress', '_is_timeshift_mode',
                     '_ts_max_shift', '_ts_current_offset', '_ts_range',
                     '_timeshift_enter_time_ms', '_timeshift_active', '_timeshift_start_time']:
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
            self.window.time_label.setText(f"⏱ {current_time}")
        if hasattr(self.window, 'program_desc') and hasattr(self.window, 'language_manager'):
            self.window.program_desc.setText(
                self.window.language_manager.tr("open_playlist_success", "Playlist opened, click a channel to play"))

    @property
    def is_playing(self) -> bool:
        """是否正在播放（以 window.current_channel 为权威来源，兼容自身副本）"""
        if self._is_stopped:
            return False
        # window.current_channel 是全局权威来源；self.current_channel 是本地副本
        # 二者任意一个非空都认为有频道选中
        window_ch = getattr(self.window, 'current_channel', None)
        return (self.current_channel is not None) or (window_ch is not None)

    @property
    def is_muted_state(self) -> bool:
        """当前是否静音"""
        return self._is_muted
