from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QIcon
from PySide6.QtWidgets import QListWidget
from core.log_manager import global_logger as logger


class ThumbnailMixin:
    """从 IPTVPlayer 提取的缩略图/Logo 回调职责"""

    def _on_logo_cache_loaded(self, url, pixmap):
        self.ui_ctrl._on_logo_cache_loaded(url, pixmap)

    def _on_thumbnail_ready(self, channel_name, url):
        self._update_grid_thumbnail(url)

    def _on_player_thumbnail_captured(self, url):
        self._update_grid_thumbnail(url)

    def _update_grid_thumbnail(self, url):
        from services.thumbnail_service import get_thumbnail_path
        thumb_path = get_thumbnail_path(url)
        if not thumb_path:
            return
        for list_widget in (self.sub_channel_list, self.local_channel_list):
            if list_widget.viewMode() != QListWidget.ViewMode.IconMode:
                continue
            channels = self._sub_channels if list_widget is self.sub_channel_list else self._local_channels
            match_idx = None
            for ci, ch in enumerate(channels or []):
                if ch.get('url', '') == url:
                    match_idx = ci
                    break
            if match_idx is None:
                continue
            item = list_widget.item(match_idx)
            if item and item.data(Qt.ItemDataRole.UserRole) == match_idx:
                px = QPixmap(thumb_path)
                if not px.isNull():
                    scaled = px.scaled(210, 118, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    item.setIcon(QIcon(scaled))