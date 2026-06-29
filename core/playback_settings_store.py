"""按 URL 持久化每个文件的播放设置（音量/字幕轨/音轨/比例/翻转/旋转等）"""
import os
import json
import threading
import time
from core.log_manager import global_logger as logger

# 最多保存多少个文件的设置（LRU 淘汰）
_MAX_ENTRIES = 300


class PlaybackSettingsStore:
    """按 URL 存储播放设置，JSON 文件持久化，线程安全"""

    def __init__(self, config_dir: str):
        self._file = os.path.join(config_dir, 'playback_settings.json')
        self._lock = threading.Lock()
        self._cache: dict = {}
        self._load()

    def _load(self):
        try:
            if os.path.exists(self._file):
                with open(self._file, 'r', encoding='utf-8') as f:
                    self._cache = json.load(f) or {}
        except Exception as e:
            logger.warning(f"加载播放设置失败: {e}")
            self._cache = {}

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self._file), exist_ok=True)
            with open(self._file, 'w', encoding='utf-8') as f:
                json.dump(self._cache, f, ensure_ascii=False, indent=1)
        except Exception as e:
            logger.warning(f"保存播放设置失败: {e}")

    def load_settings(self, url: str) -> dict:
        """读取指定 URL 的播放设置，无则返回空 dict"""
        if not url:
            return {}
        with self._lock:
            entry = self._cache.get(url)
            if not entry:
                return {}
            return dict(entry.get('settings', {}))

    def save_settings(self, url: str, settings: dict, name: str = ''):
        """保存指定 URL 的播放设置"""
        if not url or not settings:
            return
        with self._lock:
            entry = {
                'url': url,
                'name': name or '',
                'settings': settings,
                'updated_at': int(time.time()),
            }
            self._cache[url] = entry
            # LRU 淘汰
            if len(self._cache) > _MAX_ENTRIES:
                sorted_items = sorted(self._cache.items(),
                                      key=lambda kv: kv[1].get('updated_at', 0))
                while len(self._cache) > _MAX_ENTRIES:
                    k, _ = sorted_items.pop(0)
                    self._cache.pop(k, None)
            self._save()

    def clear_settings(self, url: str):
        with self._lock:
            if url in self._cache:
                self._cache.pop(url, None)
                self._save()

    def clear_all(self):
        with self._lock:
            self._cache = {}
            self._save()
