import threading
from typing import List, Dict, Any
from utils.singleton import Singleton


class ApplicationState(Singleton):

    def __init__(self):
        if self._initialized:
            return
        
        # 频道列表（默认为空，需要用户打开播放列表文件）
        self._channels: List[Dict[str, Any]] = []
        
        # 频道分组（从实际数据中提取，初始为空）
        self._channel_groups: List[str] = ["All Channels"]
        
        # EPG 节目单数据（初始为空字典）
        self._epg_data: Dict[str, Any] = {}
        
        self._channels_lock = threading.Lock()
        self._groups_lock = threading.Lock()
        self._epg_lock = threading.Lock()
        
        self._initialized = True
    
    @property
    def channels(self) -> List[Dict[str, Any]]:
        with self._channels_lock:
            return self._channels.copy()

    @channels.setter
    def channels(self, value: List[Dict[str, Any]]):
        with self._channels_lock:
            self._channels = value

    def replace_channels(self, new_channels: List[Dict[str, Any]]):
        with self._channels_lock:
            self._channels = list(new_channels)

    def get_channel_by_index(self, idx: int) -> Dict[str, Any] | None:
        """获取频道（浅拷贝）。修改返回值中的嵌套结构会影响原始数据，如需完全隔离请自行deepcopy"""
        with self._channels_lock:
            if 0 <= idx < len(self._channels):
                return dict(self._channels[idx])
            return None

    @property
    def channel_count(self) -> int:
        with self._channels_lock:
            return len(self._channels)

    @property
    def channel_groups(self) -> List[str]:
        with self._groups_lock:
            return self._channel_groups.copy()

    @channel_groups.setter
    def channel_groups(self, value: List[str]):
        with self._groups_lock:
            self._channel_groups = value

    @property
    def epg_data(self) -> Dict[str, Any]:
        with self._epg_lock:
            return self._epg_data.copy()

    @epg_data.setter
    def epg_data(self, value: Dict[str, Any]):
        with self._epg_lock:
            self._epg_data = value

    def update_epg_data(self, new_data: Dict[str, Any]):
        with self._epg_lock:
            self._epg_data.clear()
            self._epg_data.update(new_data)

    def get_epg_channel_count(self) -> int:
        with self._epg_lock:
            return len(self._epg_data)

    def get_epg_sample(self) -> tuple:
        with self._epg_lock:
            if not self._epg_data:
                return (None, None)
            sample_channel = list(self._epg_data.keys())[0]
            sample_date = None
            if sample_channel and self._epg_data[sample_channel]:
                sample_date = self._epg_data[sample_channel][0].get('start', 'N/A')
            return (sample_channel, sample_date)

    def clear_all(self):
        with self._channels_lock:
            self._channels.clear()
        with self._groups_lock:
            self._channel_groups = ["All Channels"]
        with self._epg_lock:
            self._epg_data.clear()


# 全局单例实例
app_state = ApplicationState()
