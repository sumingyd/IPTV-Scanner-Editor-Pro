"""
频道列表控制器 - 负责频道列表的填充、更新、选择等
从 pyqt_player.py 提取的独立模块
"""

from typing import Dict, Any, Optional
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QListWidgetItem


class ChannelController:
    """频道列表控制器 - 管理频道列表的所有逻辑"""

    def __init__(self, main_window):
        self.window = main_window

    def populate_channel_list(self):
        """填充频道列表"""
        import sys
        from core.log_manager import global_logger as logger

        if not hasattr(self.window, 'channel_list') or not hasattr(self.window, 'channel_model'):
            return

        self.window.channel_list.clear()

        # 获取频道数据（从全局变量 CHANNELS）
        main_module = sys.modules.get('__main__')
        channels = getattr(main_module, 'CHANNELS', []) if main_module else []

        if not channels:
            logger.debug("频道数据为空，跳过填充")
            return

        for i, channel in enumerate(channels):
            item = QListWidgetItem()
            
            # 构建显示文本
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
            
            # 设置图标（如果有logo）
            logo_url = channel.get('logo_url')
            if logo_url:
                # TODO: 异步加载logo
                pass
            
            self.window.channel_list.addItem(item)

    def on_group_changed(self, group_name: str):
        """处理分组切换事件"""
        # 获取频道数据（从全局变量 CHANNELS）
        import sys
        from core.log_manager import global_logger as logger

        main_module = sys.modules.get('__main__')
        channels = getattr(main_module, 'CHANNELS', []) if main_module else []

        # 过滤指定分组的频道
        filtered_channels = [
            ch for ch in channels
            if ch.get('group') == group_name or group_name == "All Channels"
        ]

        logger.debug(f"分组切换: {group_name}, 过滤后 {len(filtered_channels)} 个频道")

        # 刷新UI（走防抖路径，避免重复填充）
        if hasattr(self.window, '_populate_channel_list'):
            self.window._populate_channel_list()

    def select_channel(self, item: QListWidgetItem):
        """处理频道选择事件"""
        if not item:
            return
            
        channel = item.data(Qt.ItemDataRole.UserRole)
        if not channel:
            return
        
        # 更新当前选中项
        if hasattr(self.window, 'current_channel'):
            self.window.current_channel = channel
        
        # 更新频道信息显示
        self._update_channel_info(channel)
        
        # 如果有播放控制器，开始播放
        if hasattr(self.window, 'playback_ctrl'):
            self.window.playback_ctrl.play_channel(channel)

    def _get_display_channel_name(self, channel: Dict[str, Any]) -> str:
        """获取频道的显示名称"""
        if not channel:
            return ""
            
        name = channel.get('name', '')
        number = channel.get('tvg_chno', '')
        
        if number:
            return f"{number} {name}"
        return name

    def _update_channel_info(self, channel: Dict[str, Any]):
        """更新频道信息显示区域"""
        if not hasattr(self.window, 'channel_name'):
            return
            
        display_name = self._get_display_channel_name(channel)
        self.window.channel_name.setText(display_name)
        
        # 更新其他信息
        if hasattr(self.window, 'channel_logo'):
            logo_url = channel.get('logo_url')
            if logo_url:
                # TODO: 加载并显示logo
                pass
            else:
                self.window.channel_logo.setText("📺")
        
        # 更新分辨率等信息
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
        import sys
        main_module = sys.modules.get('__main__')
        channels = getattr(main_module, 'CHANNELS', []) if main_module else []
        return len(channels)

    @property
    def current_group(self) -> str:
        """当前选中的分组名称"""
        if hasattr(self.window, 'group_combo'):
            return self.window.group_combo.currentText()
        return ""
