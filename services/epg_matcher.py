import re
import threading
from core.log_manager import global_logger


class EpgMatcher:
    _smart_cache = {}
    _cache_lock = threading.Lock()

    @classmethod
    def match(cls, channel_name, epg_channels, tvg_id=None, tvg_name=None, comma_name=None):
        """精确匹配EPG频道

        优先级：
        1. tvg-name 精确匹配
        2. tvg-id 精确匹配
        3. m3u标签行逗号后的频道名字精确匹配
        4. channel_name 精确匹配

        Args:
            channel_name: 频道名称（name字段）
            epg_channels: EPG频道字典 {epg_id: display_name, ...}
            tvg_id: 频道的tvg-id
            tvg_name: 频道的tvg-name
            comma_name: m3u标签行逗号后的频道名字
        """
        if not channel_name and not tvg_id and not tvg_name and not comma_name:
            return None

        cache_key = (channel_name, tvg_id, tvg_name, comma_name,
                     tuple(sorted(epg_channels.keys())) if isinstance(epg_channels, dict) else '')
        with cls._cache_lock:
            if cache_key in cls._smart_cache:
                return cls._smart_cache[cache_key]

        candidates = []
        if isinstance(epg_channels, dict):
            for epg_id, epg_display_name in epg_channels.items():
                candidates.append((epg_id, epg_display_name))
        elif isinstance(epg_channels, list):
            for item in epg_channels:
                if isinstance(item, dict):
                    candidates.append((item.get('id', ''), item.get('name', '')))
                elif isinstance(item, (list, tuple)) and len(item) >= 2:
                    candidates.append((item[0], item[1]))

        # 优先级1: tvg-name 精确匹配（与 epg_display_name 或 epg_id）
        if tvg_name:
            for epg_id, epg_display_name in candidates:
                if tvg_name == epg_display_name or tvg_name == epg_id:
                    with cls._cache_lock:
                        cls._smart_cache[cache_key] = epg_id
                    return epg_id

        # 优先级2: tvg-id 精确匹配
        if tvg_id:
            for epg_id, epg_display_name in candidates:
                if tvg_id == epg_id:
                    with cls._cache_lock:
                        cls._smart_cache[cache_key] = epg_id
                    return epg_id

        # 优先级3: m3u标签行逗号后的频道名字精确匹配
        if comma_name:
            for epg_id, epg_display_name in candidates:
                if comma_name == epg_display_name or comma_name == epg_id:
                    with cls._cache_lock:
                        cls._smart_cache[cache_key] = epg_id
                    return epg_id

        # 优先级4: channel_name 精确匹配
        if channel_name:
            for epg_id, epg_display_name in candidates:
                if channel_name == epg_display_name or channel_name == epg_id:
                    with cls._cache_lock:
                        cls._smart_cache[cache_key] = epg_id
                    return epg_id

        with cls._cache_lock:
            cls._smart_cache[cache_key] = None
        return None

    @classmethod
    def clear_cache(cls):
        with cls._cache_lock:
            cls._smart_cache.clear()
