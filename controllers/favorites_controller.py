from typing import Dict, Any, List, Optional
from PyQt6.QtCore import QTimer
from core.log_manager import global_logger as logger
from controllers.main_window_protocol import MainWindowProtocol


class FavoritesController:
    def __init__(self, main_window: MainWindowProtocol):
        self.window: MainWindowProtocol = main_window
        self._service = None

    def init_service(self, config_manager):
        from services.favorites_service import FavoritesService
        self._service = FavoritesService(config_manager)

    @property
    def service(self):
        return self._service

    def on_channel_played(self, channel: Dict[str, Any]):
        if self._service and channel and channel.get('url'):
            self._service.record_play(channel)

    def toggle_favorite(self, channel: Optional[Dict[str, Any]] = None):
        ch = channel or getattr(self.window, 'current_channel', None)
        if not ch or not self._service:
            return
        is_fav = self._service.toggle_favorite(ch)
        self._update_favorite_button_icon(ch)
        tr = self.window.language_manager.tr
        if is_fav:
            self.window.status_bar_show_message(tr('added_to_favorites', '已添加到收藏夹'))
        else:
            self.window.status_bar_show_message(tr('removed_from_favorites', '已从收藏夹移除'))
        return is_fav

    def is_favorite(self, channel: Optional[Dict[str, Any]] = None) -> bool:
        ch = channel or getattr(self.window, 'current_channel', None)
        if not ch or not self._service:
            return False
        return self._service.is_favorite(ch)

    def _update_favorite_button_icon(self, channel: Optional[Dict[str, Any]] = None):
        btn = getattr(self.window, 'favorite_button', None)
        if not btn:
            return
        from ui.styles import AppStyles
        from PyQt6.QtGui import QIcon
        btn_color = AppStyles._get_colors().get('player_panel_text', AppStyles._safe_fallback('player_panel_text'))
        is_fav = self.is_favorite(channel)
        icon_name = 'favorite_filled' if is_fav else 'favorite'
        icon_path = AppStyles.get_icon(icon_name, btn_color)
        if icon_path:
            btn.setIcon(QIcon(icon_path))

    def update_favorite_button_state(self):
        self._update_favorite_button_icon()

    def get_favorites(self) -> List[Dict[str, Any]]:
        if self._service:
            return self._service.get_favorites()
        return []

    def get_play_history(self) -> List[Dict[str, Any]]:
        if self._service:
            return self._service.get_play_history()
        return []

    def populate_favorites_tab(self):
        list_widget = getattr(self.window, 'fav_channel_list', None)
        if not list_widget:
            return
        list_widget.clear()
        if not self._service:
            return
        from PyQt6.QtWidgets import QListWidgetItem, QListWidget
        from PyQt6.QtCore import Qt, QSize
        from PyQt6 import QtWidgets
        from ui.styles import AppStyles
        w = self.window
        tr = w.language_manager.tr
        name_style = AppStyles.player_channel_list_name_style()
        channels = self._service.get_favorites()
        for idx, channel in enumerate(channels):
            try:
                channel_name = channel.get('name', tr('unnamed', 'Unnamed'))
                item_widget = QtWidgets.QWidget()
                item_layout = QtWidgets.QHBoxLayout(item_widget)
                item_layout.setContentsMargins(5, 2, 5, 2)
                item_layout.setSpacing(8)
                logo_label = QtWidgets.QLabel()
                logo_label.setFixedSize(44, 32)
                logo_label.setStyleSheet("background-color: transparent; border: none;")
                logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                logo_label.setObjectName("channel_logo_label")
                name_label = QtWidgets.QLabel(channel_name)
                name_label.setStyleSheet(name_style)
                name_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
                name_label.setWordWrap(False)
                item_layout.addWidget(logo_label, 0, Qt.AlignmentFlag.AlignVCenter)
                item_layout.addWidget(name_label, 1, Qt.AlignmentFlag.AlignVCenter)
                item = QListWidgetItem()
                item.setSizeHint(QSize(0, 40))
                item.setData(Qt.ItemDataRole.UserRole, idx)
                list_widget.addItem(item)
                list_widget.setItemWidget(item, item_widget)
                logo_url = channel.get('logo', '')
                if logo_url:
                    logo_cache = getattr(w, '_logo_cache_service', None)
                    if logo_cache:
                        cached = logo_cache.get(logo_url)
                        if cached:
                            scaled = logo_cache.scale_logo_pixmap_to_fit(cached, 44, 32)
                            logo_label.setPixmap(scaled)
                        else:
                            logo_cache.fetch_async(logo_url)
            except Exception as e:
                if logger:
                    logger.debug(f"填充收藏项失败: {e}")
        empty_label = getattr(self.window, 'fav_empty_label', None)
        if empty_label:
            if len(channels) == 0:
                empty_label.show()
            else:
                empty_label.hide()

    def populate_history_tab(self):
        list_widget = getattr(self.window, 'history_channel_list', None)
        if not list_widget:
            return
        list_widget.clear()
        if not self._service:
            return
        from PyQt6.QtWidgets import QListWidgetItem, QListWidget
        from PyQt6.QtCore import Qt, QSize
        from PyQt6 import QtWidgets
        from ui.styles import AppStyles
        w = self.window
        tr = w.language_manager.tr
        name_style = AppStyles.player_channel_list_name_style()
        channels = self._service.get_play_history()
        for idx, channel in enumerate(channels):
            try:
                channel_name = channel.get('name', tr('unnamed', 'Unnamed'))
                play_time = channel.get('play_time', '')
                time_str = ''
                if play_time:
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(play_time)
                        time_str = dt.strftime('%m/%d %H:%M')
                    except Exception:
                        pass
                display_name = f"{channel_name}  {time_str}" if time_str else channel_name
                item_widget = QtWidgets.QWidget()
                item_layout = QtWidgets.QHBoxLayout(item_widget)
                item_layout.setContentsMargins(5, 2, 5, 2)
                item_layout.setSpacing(8)
                logo_label = QtWidgets.QLabel()
                logo_label.setFixedSize(44, 32)
                logo_label.setStyleSheet("background-color: transparent; border: none;")
                logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                logo_label.setObjectName("channel_logo_label")
                name_label = QtWidgets.QLabel(display_name)
                name_label.setStyleSheet(name_style)
                name_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
                name_label.setWordWrap(False)
                item_layout.addWidget(logo_label, 0, Qt.AlignmentFlag.AlignVCenter)
                item_layout.addWidget(name_label, 1, Qt.AlignmentFlag.AlignVCenter)
                item = QListWidgetItem()
                item.setSizeHint(QSize(0, 40))
                item.setData(Qt.ItemDataRole.UserRole, idx)
                list_widget.addItem(item)
                list_widget.setItemWidget(item, item_widget)
                logo_url = channel.get('logo', '')
                if logo_url:
                    logo_cache = getattr(w, '_logo_cache_service', None)
                    if logo_cache:
                        cached = logo_cache.get(logo_url)
                        if cached:
                            scaled = logo_cache.scale_logo_pixmap_to_fit(cached, 44, 32)
                            logo_label.setPixmap(scaled)
                        else:
                            logo_cache.fetch_async(logo_url)
            except Exception as e:
                if logger:
                    logger.debug(f"填充历史项失败: {e}")
        empty_label = getattr(self.window, 'history_empty_label', None)
        if empty_label:
            if len(channels) == 0:
                empty_label.show()
            else:
                empty_label.hide()

    def on_favorite_item_clicked(self, item):
        if not self._service:
            return
        idx = item.data(Qt.ItemDataRole.UserRole)
        favorites = self._service.get_favorites()
        if isinstance(idx, int) and 0 <= idx < len(favorites):
            channel = favorites[idx]
            self._play_from_entry(channel)

    def on_history_item_clicked(self, item):
        if not self._service:
            return
        idx = item.data(Qt.ItemDataRole.UserRole)
        history = self._service.get_play_history()
        if isinstance(idx, int) and 0 <= idx < len(history):
            channel = history[idx]
            self._play_from_entry(channel)

    def _play_from_entry(self, channel: Dict[str, Any]):
        w = self.window
        url = channel.get('url', '')
        name = channel.get('name', '')
        if not url:
            return
        existing_ch = None
        for ch_list in (getattr(w, '_sub_channels', []), getattr(w, '_local_channels', [])):
            for ch in ch_list:
                if ch.get('url', '') == url:
                    existing_ch = ch
                    break
            if existing_ch:
                break
        if existing_ch:
            w.current_channel = existing_ch
            w.update_channel_info_on_selection()
            w.play_channel(existing_ch)
        else:
            w.current_channel = channel
            if hasattr(w, 'channel_name'):
                w.channel_name.setText(name)
            w.play_channel(channel)