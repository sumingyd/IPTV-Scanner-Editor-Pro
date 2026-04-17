import re
import threading
from core.log_manager import global_logger


class EpgMatcher:
    _GARBAGE_WORDS = re.compile(
        r'(?:HD|SD|UHD|4K|8K|HEVC|H\.?265|H\.?264|AVC|HDR|FHD|超清|高清|标清|高清频道|频道|备用|测试|源\d*)',
        re.IGNORECASE
    )
    _PAREN_CONTENT = re.compile(r'[()（）\[\]【】].*?[()（）\[\]【]]]')
    _CN_NUM_MAP = {
        '一': '1', '二': '2', '三': '3', '四': '4', '五': '5',
        '六': '6', '七': '7', '八': '8', '九': '9', '十': '10',
        '零': '0',
    }
    _CN_NUM_RE = re.compile(r'[一二三四五六七八九十零]')
    _SATELLITE_SUFFIX = re.compile(r'(卫视|台|电视|频道)$')
    _NUMBER_RE = re.compile(r'(\d+)')
    _smart_cache = {}
    _cache_lock = threading.Lock()

    @classmethod
    def _cn_num_to_arabic(cls, s: str) -> str:
        def replacer(m: re.Match) -> str:
            return cls._CN_NUM_MAP.get(m.group(), m.group()) or m.group()
        return cls._CN_NUM_RE.sub(replacer, s)

    @classmethod
    def _clean_name(cls, name):
        if not name:
            return ''
        name = cls._PAREN_CONTENT.sub('', name)
        name = cls._GARBAGE_WORDS.sub('', name)
        name = cls._cn_num_to_arabic(name)
        name = name.strip()
        return name

    @classmethod
    def _extract_numbers(cls, name):
        return set(cls._NUMBER_RE.findall(name))

    @classmethod
    def _match_level(cls, ch_name, epg_name):
        if not ch_name or not epg_name:
            return 0
        if ch_name == epg_name:
            return 100
        if ch_name.lower() == epg_name.lower():
            return 95
        ch_clean = cls._clean_name(ch_name)
        epg_clean = cls._clean_name(epg_name)
        if not ch_clean or not epg_clean:
            return 0
        if ch_clean == epg_clean:
            return 90
        if ch_clean.lower() == epg_clean.lower():
            return 85
        ch_no_sat = cls._SATELLITE_SUFFIX.sub('', ch_clean)
        epg_no_sat = cls._SATELLITE_SUFFIX.sub('', epg_clean)
        if ch_no_sat and epg_no_sat:
            if ch_no_sat == epg_no_sat:
                return 80
            if ch_no_sat.lower() == epg_no_sat.lower():
                return 75
        ch_nums = cls._extract_numbers(ch_clean)
        epg_nums = cls._extract_numbers(epg_clean)
        if ch_nums and epg_nums:
            if ch_nums != epg_nums:
                return 0
        if ch_clean in epg_clean or epg_clean in ch_clean:
            return 60
        if ch_no_sat in epg_no_sat or epg_no_sat in ch_no_sat:
            return 55
        return 0

    @classmethod
    def match(cls, channel_name, epg_channels, tvg_id=None, tvg_name=None):
        if not channel_name and not tvg_id and not tvg_name:
            return None

        cache_key = (channel_name, tvg_id, tvg_name, tuple(sorted(epg_channels.keys())) if isinstance(epg_channels, dict) else '')
        with cls._cache_lock:
            if cache_key in cls._smart_cache:
                return cls._smart_cache[cache_key]

        best_match = None
        best_score = 0

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

        for epg_id, epg_display_name in candidates:
            score = 0
            if tvg_id and epg_id:
                if tvg_id == epg_id:
                    score = 100
                elif tvg_id.lower() == epg_id.lower():
                    score = 98
                if score >= best_score and score > 0:
                    best_match = epg_id
                    best_score = score
                    continue

            level = cls._match_level(tvg_name or channel_name, epg_display_name)
            if level > best_score:
                best_score = level
                best_match = epg_id

        if best_score >= 55:
            with cls._cache_lock:
                cls._smart_cache[cache_key] = best_match
            return best_match
        with cls._cache_lock:
            cls._smart_cache[cache_key] = None
        return None

    @classmethod
    def clear_cache(cls):
        with cls._cache_lock:
            cls._smart_cache.clear()
