from typing import Dict, Any, List, Optional, Tuple
from core.log_manager import global_logger as logger


class ChannelQuickJumpService:
    def __init__(self):
        self._pypinyin_available = False
        try:
            import pypinyin
            self._pypinyin_available = True
        except ImportError:
            pass

    def get_pinyin_initials(self, text: str) -> str:
        if not text:
            return ''
        if self._pypinyin_available:
            try:
                import pypinyin
                initials = pypinyin.lazy_pinyin(text, style=pypinyin.Style.FIRST_LETTER)
                return ''.join(initials).lower()
            except Exception:
                pass
        result = []
        for ch in text:
            if 'a' <= ch.lower() <= 'z':
                result.append(ch.lower())
            elif '\u4e00' <= ch <= '\u9fff':
                result.append(ch.lower())
        return ''.join(result)

    def find_best_match(self, query: str, channels: List[Dict[str, Any]],
                        max_results: int = 10) -> List[Tuple[int, float]]:
        if not query or not channels:
            return []
        query = query.strip().lower()
        results = []

        for idx, ch in enumerate(channels):
            name = ch.get('name', '')
            if not name:
                continue
            name_lower = name.lower()
            pinyin = self.get_pinyin_initials(name)

            score = 0.0
            if name_lower.startswith(query):
                score = 100.0
            elif pinyin.startswith(query):
                score = 90.0
            elif query in name_lower:
                score = 80.0
            elif query in pinyin:
                score = 70.0
            else:
                continue

            results.append((idx, score))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:max_results]

    def find_single_match(self, query: str, channels: List[Dict[str, Any]]) -> Optional[int]:
        matches = self.find_best_match(query, channels, max_results=1)
        if matches:
            return matches[0][0]
        return None