import re
import threading
import unicodedata
from collections import OrderedDict
from core.log_manager import global_logger

_MAX_CACHE_SIZE = 5000

_COMMON_ALIASES = {
    'cctv1': 'CCTV-1 综合',
    'cctv2': 'CCTV-2 财经',
    'cctv3': 'CCTV-3 综艺',
    'cctv4': 'CCTV-4 中文国际',
    'cctv5': 'CCTV-5 体育',
    'cctv5plus': 'CCTV-5+ 体育赛事',
    'cctv6': 'CCTV-6 电影',
    'cctv7': 'CCTV-7 国防军事',
    'cctv8': 'CCTV-8 电视剧',
    'cctv9': 'CCTV-9 纪录',
    'cctv10': 'CCTV-10 科教',
    'cctv11': 'CCTV-11 戏曲',
    'cctv12': 'CCTV-12 社会与法',
    'cctv13': 'CCTV-13 新闻',
    'cctv14': 'CCTV-14 少儿',
    'cctv15': 'CCTV-15 音乐',
    'cctv16': 'CCTV-16 奥林匹克',
    'cctv17': 'CCTV-17 农业农村',
    'cctv5plus': 'CCTV-5+ 体育赛事',
    'cctv4k': 'CCTV-4K 超高清',
}

_PINYIN_MAP = {
    '央视一套': 'CCTV-1 综合', '央视二套': 'CCTV-2 财经', '央视三套': 'CCTV-3 综艺',
    '央视四套': 'CCTV-4 中文国际', '央视五套': 'CCTV-5 体育', '央视六套': 'CCTV-6 电影',
    '央视七套': 'CCTV-7 国防军事', '央视八套': 'CCTV-8 电视剧', '央视九套': 'CCTV-9 纪录',
    '央视十套': 'CCTV-10 科教', '央视十一套': 'CCTV-11 戏曲', '央视十二套': 'CCTV-12 社会与法',
    '央视十三套': 'CCTV-13 新闻', '央视十四套': 'CCTV-14 少儿', '央视十五套': 'CCTV-15 音乐',
    '新闻频道': 'CCTV-13 新闻', '体育频道': 'CCTV-5 体育', '电影频道': 'CCTV-6 电影',
    '综艺频道': 'CCTV-3 综艺', '戏曲频道': 'CCTV-11 戏曲', '音乐频道': 'CCTV-15 音乐',
    '少儿频道': 'CCTV-14 少儿', '科教频道': 'CCTV-10 科教', '纪录频道': 'CCTV-9 纪录',
    '农业农村频道': 'CCTV-17 农业农村',
}


def _normalize(name):
    if not name:
        return ''
    name = unicodedata.normalize('NFKC', name)
    name = name.lower().strip()
    name = re.sub(r'(\d)\s*\+\s*', r'\1plus', name)
    name = re.sub(r'[\s\-_·.]+', '', name)
    name = name.replace('（', '(').replace('）', ')')
    name = name.replace('：', ':').replace('，', ',')
    name = re.sub(r'[()（）:：,，]', '', name)
    return name


def _levenshtein_distance(s1, s2):
    if len(s1) < len(s2):
        return _levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    prev_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = prev_row[j + 1] + 1
            deletions = curr_row[j] + 1
            substitutions = prev_row[j] + (c1 != c2)
            curr_row.append(min(insertions, deletions, substitutions))
        prev_row = curr_row
    return prev_row[-1]


def _similarity(s1, s2):
    if not s1 or not s2:
        return 0.0
    max_len = max(len(s1), len(s2))
    if max_len == 0:
        return 1.0
    dist = _levenshtein_distance(s1, s2)
    return 1.0 - dist / max_len


class EpgMatcher:
    _smart_cache: OrderedDict = OrderedDict()
    _cache_lock = threading.Lock()

    @classmethod
    def _build_index(cls, epg_channels):
        by_id = {}
        by_name = {}
        by_norm_name = {}
        if isinstance(epg_channels, dict):
            for epg_id, epg_display_name in epg_channels.items():
                by_id[epg_id] = epg_id
                if epg_display_name not in by_name:
                    by_name[epg_display_name] = epg_id
                norm = _normalize(epg_display_name)
                if norm and norm not in by_norm_name:
                    by_norm_name[norm] = epg_id
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
                norm = _normalize(epg_display_name)
                if norm and norm not in by_norm_name:
                    by_norm_name[norm] = epg_id
        return by_id, by_name, by_norm_name

    @classmethod
    def _fuzzy_match_by_normalize(cls, name, by_norm_name):
        if not name:
            return None
        norm = _normalize(name)
        if not norm:
            return None
        if norm in by_norm_name:
            return by_norm_name[norm]
        alias = _COMMON_ALIASES.get(norm)
        if alias:
            alias_norm = _normalize(alias)
            if alias_norm in by_norm_name:
                return by_norm_name[alias_norm]
        pinyin_match = _PINYIN_MAP.get(name.strip())
        if pinyin_match:
            pinyin_norm = _normalize(pinyin_match)
            if pinyin_norm in by_norm_name:
                return by_norm_name[pinyin_norm]
        return None

    @classmethod
    def _fuzzy_match_by_similarity(cls, name, by_norm_name, threshold=0.7):
        if not name:
            return None
        norm = _normalize(name)
        if not norm:
            return None
        best_score = 0.0
        best_result = None
        for epg_norm, epg_id in by_norm_name.items():
            if abs(len(epg_norm) - len(norm)) > max(len(norm), len(epg_norm)) * 0.4:
                continue
            score = _similarity(norm, epg_norm)
            if score > best_score:
                best_score = score
                best_result = epg_id
        if best_score >= threshold:
            return best_result
        return None

    @classmethod
    def match(cls, channel_name, epg_channels, tvg_id=None, tvg_name=None, comma_name=None):
        if not channel_name and not tvg_id and not tvg_name and not comma_name:
            return None

        cache_key = (channel_name, tvg_id, tvg_name, comma_name)
        with cls._cache_lock:
            if cache_key in cls._smart_cache:
                cls._smart_cache.move_to_end(cache_key)
                return cls._smart_cache[cache_key]

        by_id, by_name, by_norm_name = cls._build_index(epg_channels)

        result = None

        if tvg_name:
            result = by_name.get(tvg_name) or by_id.get(tvg_name)

        if result is None and tvg_id:
            result = by_id.get(tvg_id)

        if result is None and comma_name:
            result = by_name.get(comma_name) or by_id.get(comma_name)

        if result is None and channel_name:
            result = by_name.get(channel_name) or by_id.get(channel_name)

        if result is None and tvg_name:
            result = cls._fuzzy_match_by_normalize(tvg_name, by_norm_name)

        if result is None and comma_name:
            result = cls._fuzzy_match_by_normalize(comma_name, by_norm_name)

        if result is None and channel_name:
            result = cls._fuzzy_match_by_normalize(channel_name, by_norm_name)

        if result is None and channel_name:
            result = cls._fuzzy_match_by_similarity(channel_name, by_norm_name)

        if result is None and tvg_name:
            result = cls._fuzzy_match_by_similarity(tvg_name, by_norm_name)

        with cls._cache_lock:
            if len(cls._smart_cache) >= _MAX_CACHE_SIZE:
                cls._smart_cache.popitem(last=False)
            cls._smart_cache[cache_key] = result

        return result

    @classmethod
    def clear_cache(cls):
        with cls._cache_lock:
            cls._smart_cache.clear()
