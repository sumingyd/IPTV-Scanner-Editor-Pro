from typing import Dict, Any, List, Tuple
from difflib import SequenceMatcher
from urllib.parse import urlparse
from core.log_manager import global_logger as logger


class ChannelDedupService:
    def __init__(self, name_threshold: float = 0.8, url_similarity: bool = True):
        self._name_threshold = name_threshold
        self._url_similarity = url_similarity

    def find_duplicates(self, channels: List[Dict[str, Any]]) -> List[Tuple[int, int, float, str]]:
        results = []
        n = len(channels)

        url_groups = {}
        for i, ch in enumerate(channels):
            url = ch.get('url', '')
            if url:
                url_groups.setdefault(url, []).append(i)

        checked = set()
        for indices in url_groups.values():
            if len(indices) < 2:
                continue
            for a in range(len(indices)):
                for b in range(a + 1, len(indices)):
                    i, j = indices[a], indices[b]
                    pair = (min(i, j), max(i, j))
                    if pair not in checked:
                        checked.add(pair)
                        results.append((i, j, 1.0, 'url_exact'))

        name_groups = {}
        for i, ch in enumerate(channels):
            name = ch.get('name', '').strip().lower()
            if name:
                key = name[:3] if len(name) >= 3 else name
                name_groups.setdefault(key, []).append(i)

        for indices in name_groups.values():
            if len(indices) < 2:
                continue
            for a in range(len(indices)):
                for b in range(a + 1, len(indices)):
                    i, j = indices[a], indices[b]
                    pair = (min(i, j), max(i, j))
                    if pair in checked:
                        continue
                    checked.add(pair)
                    score, reason = self._similarity(channels[i], channels[j])
                    if score > 0:
                        results.append((i, j, score, reason))

        results.sort(key=lambda x: x[2], reverse=True)
        return results

    def _similarity(self, ch1: Dict[str, Any], ch2: Dict[str, Any]) -> Tuple[float, str]:
        url1 = ch1.get('url', '')
        url2 = ch2.get('url', '')
        if url1 and url2 and url1 == url2:
            return 1.0, 'url_exact'

        name1 = ch1.get('name', '').strip().lower()
        name2 = ch2.get('name', '').strip().lower()
        if not name1 or not name2:
            return 0.0, ''

        name_score = SequenceMatcher(None, name1, name2).ratio()
        if name_score >= self._name_threshold:
            url_score = 0.0
            if self._url_similarity and url1 and url2:
                try:
                    p1 = urlparse(url1)
                    p2 = urlparse(url2)
                    if p1.hostname == p2.hostname and p1.port == p2.port:
                        path_score = SequenceMatcher(None, p1.path, p2.path).ratio()
                        url_score = 0.5 + 0.5 * path_score
                    else:
                        url_score = SequenceMatcher(None, url1, url2).ratio()
                except Exception:
                    url_score = SequenceMatcher(None, url1, url2).ratio()
                combined = 0.6 * name_score + 0.4 * url_score
            else:
                combined = name_score
            if combined >= 0.6:
                return combined, 'name_similar'

        return 0.0, ''

    def deduplicate(self, channels: List[Dict[str, Any]],
                    strategy: str = 'keep_first') -> List[Dict[str, Any]]:
        duplicates = self.find_duplicates(channels)
        remove_indices = set()
        for i, j, score, reason in duplicates:
            if strategy == 'keep_first':
                remove_indices.add(j)
            elif strategy == 'keep_last':
                remove_indices.add(i)
            elif strategy == 'keep_shorter_url':
                if len(channels[i].get('url', '')) <= len(channels[j].get('url', '')):
                    remove_indices.add(j)
                else:
                    remove_indices.add(i)
        result = [ch for idx, ch in enumerate(channels) if idx not in remove_indices]
        logger.info(f"频道去重: 原始{len(channels)}个, 移除{len(remove_indices)}个重复, 保留{len(result)}个")
        return result

    def merge_duplicates(self, channels: List[Dict[str, Any]],
                         pairs: List[Tuple[int, int]]) -> List[Dict[str, Any]]:
        merged_indices = set()
        result = list(channels)
        for i, j in pairs:
            if i in merged_indices or j in merged_indices:
                continue
            ch1 = result[i]
            ch2 = result[j]
            merged = dict(ch1)
            for key in ('logo', 'logo_url', 'tvg_id', 'group', '_groups', 'catchup', 'catchup_days', 'catchup_source'):
                if not merged.get(key) and ch2.get(key):
                    merged[key] = ch2[key]
            result[i] = merged
            merged_indices.add(j)
        result = [ch for idx, ch in enumerate(result) if idx not in merged_indices]
        return result