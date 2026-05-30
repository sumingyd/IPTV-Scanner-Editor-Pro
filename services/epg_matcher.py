import re
import threading
from collections import OrderedDict
from core.log_manager import global_logger

_MAX_CACHE_SIZE = 5000


class EpgMatcher:
    _smart_cache: OrderedDict = OrderedDict()
    _cache_lock = threading.Lock()

    @classmethod
    def _build_index(cls, epg_channels):
        """构建哈希索引，O(1)精确匹配"""
        by_id = {}
        by_name = {}
        if isinstance(epg_channels, dict):
            for epg_id, epg_display_name in epg_channels.items():
                by_id[epg_id] = epg_id
                if epg_display_name not in by_name:
                    by_name[epg_display_name] = epg_id
        elif isinstance(epg_channels, list):
            for item in epg_channels:
                if isinstance(item, dict):
                    epg_id = item.get('id', '')
                    epg_display_name = item.get('name', '')
                elif isinstance(item, (list, tuple)) and len(item) >= 2:
                    epg_id, epg_display_name = item[0], item[1]
                else:
                    continue
                by_id[epg_id] = epg_id
                if epg_display_name not in by_name:
                    by_name[epg_display_name] = epg_id
        return by_id, by_name

    @classmethod
    def match(cls, channel_name, epg_channels, tvg_id=None, tvg_name=None, comma_name=None):
        if not channel_name and not tvg_id and not tvg_name and not comma_name:
            return None

        cache_key = (channel_name, tvg_id, tvg_name, comma_name)
        with cls._cache_lock:
            if cache_key in cls._smart_cache:
                cls._smart_cache.move_to_end(cache_key)
                return cls._smart_cache[cache_key]

        by_id, by_name = cls._build_index(epg_channels)

        result = None

        if tvg_name:
            result = by_name.get(tvg_name) or by_id.get(tvg_name)

        if result is None and tvg_id:
            result = by_id.get(tvg_id)

        if result is None and comma_name:
            result = by_name.get(comma_name) or by_id.get(comma_name)

        if result is None and channel_name:
            result = by_name.get(channel_name) or by_id.get(channel_name)

        with cls._cache_lock:
            if len(cls._smart_cache) >= _MAX_CACHE_SIZE:
                cls._smart_cache.popitem(last=False)
            cls._smart_cache[cache_key] = result

        return result

    @classmethod
    def clear_cache(cls):
        with cls._cache_lock:
            cls._smart_cache.clear()
