import re
import threading
from core.log_manager import global_logger

_MAX_CACHE_SIZE = 5000


class EpgMatcher:
    _smart_cache = {}
    _cache_lock = threading.Lock()

    @classmethod
    def match(cls, channel_name, epg_channels, tvg_id=None, tvg_name=None, comma_name=None):
        if not channel_name and not tvg_id and not tvg_name and not comma_name:
            return None

        cache_key = (channel_name, tvg_id, tvg_name, comma_name)
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

        result = None

        if tvg_name:
            for epg_id, epg_display_name in candidates:
                if tvg_name == epg_display_name or tvg_name == epg_id:
                    result = epg_id
                    break

        if result is None and tvg_id:
            for epg_id, epg_display_name in candidates:
                if tvg_id == epg_id:
                    result = epg_id
                    break

        if result is None and comma_name:
            for epg_id, epg_display_name in candidates:
                if comma_name == epg_display_name or comma_name == epg_id:
                    result = epg_id
                    break

        if result is None and channel_name:
            for epg_id, epg_display_name in candidates:
                if channel_name == epg_display_name or channel_name == epg_id:
                    result = epg_id
                    break

        with cls._cache_lock:
            if len(cls._smart_cache) >= _MAX_CACHE_SIZE:
                keys = list(cls._smart_cache.keys())
                for k in keys[:len(keys) // 2]:
                    del cls._smart_cache[k]
            cls._smart_cache[cache_key] = result

        return result

    @classmethod
    def clear_cache(cls):
        with cls._cache_lock:
            cls._smart_cache.clear()
