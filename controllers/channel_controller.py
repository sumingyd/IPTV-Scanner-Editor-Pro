"""
频道列表控制器 - 负责频道列表的填充、更新、选择等
从 pyqt_player.py 提取的独立模块
"""

from typing import Dict, Any, Optional
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QListWidgetItem

from core.log_manager import global_logger as logger
from core.application_state import app_state
from utils.general_utils import get_display_channel_name


class ChannelController:
    """频道列表控制器 - 管理频道列表的所有逻辑"""

    def __init__(self, main_window):
        self.window = main_window

    def populate_channel_list(self):
        """填充频道列表"""
        if not hasattr(self.window, 'channel_list') or not hasattr(self.window, 'channel_model'):
            return

        self.window.channel_list.clear()

        channels = app_state.channels

        if not channels:
            logger.debug("频道数据为空，跳过填充")
            return

        for i, channel in enumerate(channels):
            item = QListWidgetItem()

            name = channel.get('name', '')
            group = channel.get('group', '')
            resolution = channel.get('resolution', '')

            display_text = f"{name}"
            if resolution:
                display_text += f" [{resolution}]"
            if group:
                display_text += f" - {group}"

            item.setText(display_text)
            item.setData(Qt.ItemDataRole.UserRole, channel)

            logo_url = channel.get('logo_url')
            if logo_url:
                pass

            self.window.channel_list.addItem(item)

    def on_group_changed(self, group_name: str):
        """处理分组切换事件"""
        if hasattr(self.window, '_populate_channel_list'):
            self.window._populate_channel_list(source='auto')

    def select_channel(self, item: QListWidgetItem):
        """处理频道选择事件"""
        if not item:
            return

        channel = item.data(Qt.ItemDataRole.UserRole)
        if channel is None:
            return

        if isinstance(channel, int):
            idx = channel
            channels = self._get_current_channels()
            if 0 <= idx < len(channels):
                channel = channels[idx]
            else:
                return

        if hasattr(self.window, 'current_channel'):
            self.window.current_channel = channel

        self._update_channel_info(channel)

        if hasattr(self.window, 'epg_ctrl'):
            self.window.epg_ctrl.populate_epg_list()

        if hasattr(self.window, 'playback_ctrl'):
            self.window.playback_ctrl.play_channel(channel)

    def _get_current_channels(self):
        """获取当前活跃的频道列表"""
        if hasattr(self.window, '_local_channels') and hasattr(self.window, '_sub_channels'):
            if hasattr(self.window, 'playlist_tab'):
                if self.window.playlist_tab.currentIndex() == 1:
                    return self.window._local_channels
            return self.window._sub_channels
        return app_state.channels

    def _get_display_channel_name(self, channel: Dict[str, Any]) -> str:
        """获取频道的显示名称（委托给通用工具函数）"""
        language_manager = getattr(self.window, 'language_manager', None)
        return get_display_channel_name(channel, language_manager)

    def _update_channel_info(self, channel: Dict[str, Any]):
        """更新频道信息显示区域"""
        if not hasattr(self.window, 'channel_name'):
            return

        display_name = self._get_display_channel_name(channel)
        self.window.channel_name.setText(display_name)

        if hasattr(self.window, 'channel_logo'):
            logo_url = channel.get('logo_url')
            if logo_url:
                pass
            else:
                self.window.channel_logo.setText("📺")

        if hasattr(self.window, 'video_info'):
            resolution = channel.get('resolution', '')
            if resolution:
                self.window.video_info.setText(f"📺 {resolution}")

    def update_channel_info_on_selection(self):
        """当选择变化时更新频道信息"""
        if not hasattr(self.window, 'channel_list'):
            return

        current_item = self.window.channel_list.currentItem()
        if current_item:
            self.select_channel(current_item)

    @property
    def channel_count(self) -> int:
        """当前频道数量"""
        return len(app_state.channels)

    @property
    def current_group(self) -> str:
        """当前选中的分组名称"""
        if hasattr(self.window, 'group_combo'):
            return self.window.group_combo.currentText()
        return ""
