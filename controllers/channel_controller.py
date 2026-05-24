"""
频道列表控制器 - 负责频道信息显示、分组切换等
从 pyqt_player.py 提取的独立模块
"""

from typing import Dict, Any

from core.application_state import app_state
from utils.general_utils import get_display_channel_name
from controllers.main_window_protocol import MainWindowProtocol


class ChannelController:
    """频道列表控制器 - 管理频道信息显示和分组切换"""

    def __init__(self, main_window: MainWindowProtocol):
        self.window: MainWindowProtocol = main_window

    def on_group_changed(self, group_name: str):
        """处理分组切换事件"""
        self.window._populate_channel_list(source='auto')

    def _get_current_channels(self):
        """获取当前活跃的频道列表"""
        if getattr(self.window, '_local_channels', None) and getattr(self.window, '_sub_channels', None):
            playlist_tab = getattr(self.window, 'playlist_tab', None)
            if playlist_tab and playlist_tab.currentIndex() == 1:
                return self.window._local_channels
            return self.window._sub_channels
        return app_state.channels

    def _get_display_channel_name(self, channel: Dict[str, Any]) -> str:
        """获取频道的显示名称（委托给通用工具函数）"""
        language_manager = getattr(self.window, 'language_manager', None)
        return get_display_channel_name(channel, language_manager)

    def _update_channel_info(self, channel: Dict[str, Any]):
        """更新频道信息显示区域"""
        if not self.window.channel_name:
            return

        display_name = self._get_display_channel_name(channel)
        self.window.channel_name.setText(display_name)

        if self.window.channel_logo:
            logo_url = channel.get('logo') or channel.get('logo_url')
            if not logo_url:
                self.window.channel_logo.setText("")

    def update_channel_info_on_selection(self):
        """当选择变化时更新频道信息"""
        if not self.window.channel_list:
            return

        current_item = self.window.channel_list.currentItem()
        if current_item and hasattr(self.window, 'select_channel'):
            self.window.select_channel(current_item)

    @property
    def channel_count(self) -> int:
        """当前频道数量"""
        return len(app_state.channels)

    @property
    def current_group(self) -> str:
        """当前选中的分组名称"""
        if self.window.group_combo:
            return self.window.group_combo.currentText()
        return ""