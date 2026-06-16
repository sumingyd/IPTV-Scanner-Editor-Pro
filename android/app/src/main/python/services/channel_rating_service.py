import json
import threading
from typing import Dict, Any, List, Optional
from core.log_manager import global_logger as logger


class ChannelRatingService:
    STABLE = 'stable'
    UNSTABLE = 'unstable'
    FAILED = 'failed'
    ALL_RATINGS = [STABLE, UNSTABLE, FAILED]

    def __init__(self, config_manager=None):
        self._config = config_manager
        self._lock = threading.RLock()
        self._ratings: Dict[str, str] = {}
        self._load_from_config()

    def _load_from_config(self):
        with self._lock:
            if not self._config:
                return
            try:
                count = int(self._config.get_value('ChannelRatings', 'count', '0') or '0')
                for i in range(count):
                    url = self._config.get_value('ChannelRatings', f'url_{i}', '')
                    rating = self._config.get_value('ChannelRatings', f'rating_{i}', '')
                    if url and rating:
                        self._ratings[url] = rating
            except Exception as e:
                logger.error(f"加载频道评分失败: {e}")

    def _save_to_config(self):
        if not self._config:
            return
        with self._lock:
            try:
                old_count = int(self._config.get_value('ChannelRatings', 'count', '0') or '0')
                items = list(self._ratings.items())
                self._config.set_value('ChannelRatings', 'count', str(len(items)))
                for i, (url, rating) in enumerate(items):
                    self._config.set_value('ChannelRatings', f'url_{i}', url)
                    self._config.set_value('ChannelRatings', f'rating_{i}', rating)
                for i in range(len(items), old_count + 1):
                    self._config.remove_option('ChannelRatings', f'url_{i}')
                    self._config.remove_option('ChannelRatings', f'rating_{i}')
                self._config.save_config()
            except Exception as e:
                logger.error(f"保存频道评分失败: {e}")

    def get_rating(self, channel: Dict[str, Any]) -> Optional[str]:
        url = channel.get('url', '')
        with self._lock:
            return self._ratings.get(url)

    def set_rating(self, channel: Dict[str, Any], rating: str):
        if rating not in self.ALL_RATINGS:
            return
        url = channel.get('url', '')
        if not url:
            return
        with self._lock:
            self._ratings[url] = rating
            self._save_to_config()

    def remove_rating(self, channel: Dict[str, Any]):
        url = channel.get('url', '')
        with self._lock:
            if url in self._ratings:
                del self._ratings[url]
                self._save_to_config()

    def get_channels_by_rating(self, channels: List[Dict[str, Any]],
                               rating: str) -> List[Dict[str, Any]]:
        with self._lock:
            return [ch for ch in channels if self._ratings.get(ch.get('url', '')) == rating]

    def get_rating_counts(self, channels: List[Dict[str, Any]]) -> Dict[str, int]:
        counts = {r: 0 for r in self.ALL_RATINGS}
        counts['unrated'] = 0
        with self._lock:
            for ch in channels:
                r = self._ratings.get(ch.get('url', ''))
                if r in counts:
                    counts[r] += 1
                else:
                    counts['unrated'] += 1
        return counts