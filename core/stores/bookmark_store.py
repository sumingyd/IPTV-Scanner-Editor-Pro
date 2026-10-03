"""书签域存储 — 书签管理（JSON 文件存储）。"""

import os
import time

from core.log_manager import global_logger as logger


class BookmarkStore:
    """书签配置域存储，持有独立 JSON 缓存。"""

    _BOOKMARK_MAX_URLS = 500
    _BOOKMARK_MAX_PER_URL = 100
    _BOOKMARK_MATCH_TOLERANCE = 0.5

    def __init__(self, facade, bookmark_file: str):
        self._facade = facade
        self._bookmark_file = bookmark_file
        self._bookmark_cache: dict | None = None

    def _load_bookmark_cache(self) -> dict:
        """懒加载书签缓存"""
        if self._bookmark_cache is not None:
            return self._bookmark_cache
        cache = {}
        try:
            if os.path.exists(self._bookmark_file):
                import json
                with open(self._bookmark_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        cache = data
        except Exception as e:
            logger.debug(f"加载书签缓存失败: {e}")
        self._bookmark_cache = cache
        return cache

    def _save_bookmark_cache(self):
        """保存书签缓存到 JSON 文件"""
        try:
            import json
            import tempfile
            cache = self._bookmark_cache or {}
            config_dir = os.path.dirname(self._bookmark_file)
            fd, tmp_path = tempfile.mkstemp(dir=config_dir, suffix='.tmp', prefix='bm_')
            try:
                with os.fdopen(fd, 'w', encoding='utf-8') as f:
                    json.dump(cache, f, ensure_ascii=False, indent=2)
                os.replace(tmp_path, self._bookmark_file)
            except Exception:
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
                raise
        except Exception as e:
            logger.error(f"保存书签缓存失败: {e}")

    def save_bookmark(self, url: str, position: float, name: str = ''):
        """添加书签
        - position < 0 时不保存
        - 同一 URL 同一位置（容差内）的书签会被覆盖
        """
        if not url or position < 0:
            return
        with self._facade._lock:
            cache = self._load_bookmark_cache()
            marks = cache.get(url)
            if not isinstance(marks, list):
                marks = []
            replaced = False
            for i, m in enumerate(marks):
                if abs(float(m.get('position', 0)) - position) < self._BOOKMARK_MATCH_TOLERANCE:
                    marks[i] = {
                        'position': float(position),
                        'name': name or '',
                        'created_at': int(time.time()),
                    }
                    replaced = True
                    break
            if not replaced:
                marks.append({
                    'position': float(position),
                    'name': name or '',
                    'created_at': int(time.time()),
                })
            cache[url] = marks
            if len(cache) > self._BOOKMARK_MAX_URLS:
                sorted_items = sorted(cache.items(), key=lambda kv: max((m.get('created_at', 0) for m in kv[1]), default=0))
                while len(cache) > self._BOOKMARK_MAX_URLS:
                    k, _ = sorted_items.pop(0)
                    cache.pop(k, None)
            self._save_bookmark_cache()

    def load_bookmarks(self, url: str) -> list:
        """加载指定 URL 的所有书签"""
        if not url:
            return []
        with self._facade._lock:
            cache = self._load_bookmark_cache()
            marks = cache.get(url, [])
            return [dict(m) for m in marks]

    def load_all_bookmarks(self) -> list:
        """加载所有书签"""
        with self._facade._lock:
            cache = self._load_bookmark_cache()
            result = []
            for url, marks in cache.items():
                for m in marks:
                    item = dict(m)
                    item['url'] = url
                    result.append(item)
        result.sort(key=lambda x: x.get('created_at', 0), reverse=True)
        return result

    def delete_bookmark(self, url: str, position: float) -> bool:
        """删除指定 URL 和位置的书签"""
        if not url:
            return False
        with self._facade._lock:
            cache = self._load_bookmark_cache()
            marks = cache.get(url)
            if not marks:
                return False
            for i, m in enumerate(marks):
                if abs(float(m.get('position', 0)) - position) < self._BOOKMARK_MATCH_TOLERANCE:
                    marks.pop(i)
                    if not marks:
                        cache.pop(url, None)
                    self._save_bookmark_cache()
                    return True
            return False

    def clear_bookmarks(self, url: str):
        """清除指定 URL 的所有书签"""
        if not url:
            return
        with self._facade._lock:
            cache = self._load_bookmark_cache()
            if url in cache:
                cache.pop(url, None)
                self._save_bookmark_cache()

    def clear_all_bookmarks(self):
        """清除所有书签"""
        with self._facade._lock:
            self._bookmark_cache = {}
            try:
                if os.path.exists(self._bookmark_file):
                    os.remove(self._bookmark_file)
            except Exception as e:
                logger.debug(f"清除书签文件失败: {e}")