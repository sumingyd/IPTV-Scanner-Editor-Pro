"""断点续播域存储 — 播放位置/上次频道（JSON 文件存储）。"""

import os
import time

from core.log_manager import global_logger as logger


class ResumeStore:
    """断点续播配置域存储，持有独立 JSON 缓存。"""

    _RESUME_MAX_ENTRIES = 200
    _RESUME_MIN_POSITION_SEC = 5.0
    _RESUME_TOLERANCE_SEC = 3.0

    def __init__(self, facade, resume_file: str):
        self._facade = facade
        self._resume_file = resume_file
        self._resume_cache: dict | None = None

    def save_last_channel(self, file_path, channel_name, channel_index):
        self._facade.set_value('Player', 'last_channel_file', file_path or '')
        self._facade.set_value('Player', 'last_channel_name', channel_name or '')
        self._facade.set_value('Player', 'last_channel_index', str(channel_index if channel_index is not None else -1))
        return self._facade.save_config()

    def load_last_channel(self):
        f = self._facade
        return {
            'file': f.get_value('Player', 'last_channel_file', ''),
            'name': f.get_value('Player', 'last_channel_name', ''),
            'index': f._parse_int(f.get_value('Player', 'last_channel_index', '-1'), -1),
        }

    def _load_resume_cache(self) -> dict:
        """懒加载断点缓存"""
        if self._resume_cache is not None:
            return self._resume_cache
        cache = {}
        try:
            if os.path.exists(self._resume_file):
                import json
                with open(self._resume_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        cache = data
        except Exception as e:
            logger.debug(f"加载断点缓存失败: {e}")
        self._resume_cache = cache
        return cache

    def _save_resume_cache(self):
        """保存断点缓存到 JSON 文件"""
        try:
            import json
            import tempfile
            cache = self._resume_cache or {}
            config_dir = os.path.dirname(self._resume_file)
            fd, tmp_path = tempfile.mkstemp(dir=config_dir, suffix='.tmp', prefix='resume_')
            try:
                with os.fdopen(fd, 'w', encoding='utf-8') as f:
                    json.dump(cache, f, ensure_ascii=False, indent=2)
                os.replace(tmp_path, self._resume_file)
            except Exception:
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
                raise
        except Exception as e:
            logger.error(f"保存断点缓存失败: {e}")

    def save_resume_position(self, url: str, position: float, duration: float, name: str = ''):
        """保存播放位置
        - position < _RESUME_MIN_POSITION_SEC 时不保存（视为开头）
        - duration > 0 且 position + _RESUME_TOLERANCE_SEC >= duration 时删除断点（视为已播完）
        """
        if not url or position < self._RESUME_MIN_POSITION_SEC:
            return
        with self._facade._lock:
            cache = self._load_resume_cache()
            if duration and duration > 0 and position + self._RESUME_TOLERANCE_SEC >= duration:
                if url in cache:
                    cache.pop(url, None)
                    self._save_resume_cache()
                return
            entry = {
                'url': url,
                'position': float(position),
                'duration': float(duration) if duration else 0.0,
                'name': name or '',
                'updated_at': int(time.time()),
            }
            cache[url] = entry
            if len(cache) > self._RESUME_MAX_ENTRIES:
                sorted_items = sorted(cache.items(), key=lambda kv: kv[1].get('updated_at', 0))
                while len(cache) > self._RESUME_MAX_ENTRIES:
                    k, _ = sorted_items.pop(0)
                    cache.pop(k, None)
            self._save_resume_cache()

    def load_resume_position(self, url: str) -> dict | None:
        """加载指定 URL 的播放位置"""
        if not url:
            return None
        with self._facade._lock:
            cache = self._load_resume_cache()
            entry = cache.get(url)
            if not entry:
                return None
            return dict(entry)

    def load_all_resume_positions(self) -> list:
        """加载所有断点（按 updated_at 降序）"""
        with self._facade._lock:
            cache = self._load_resume_cache()
            items = [dict(v) for v in cache.values()]
        items.sort(key=lambda x: x.get('updated_at', 0), reverse=True)
        return items

    def clear_resume_position(self, url: str):
        """清除指定 URL 的断点"""
        if not url:
            return
        with self._facade._lock:
            cache = self._load_resume_cache()
            if url in cache:
                cache.pop(url, None)
                self._save_resume_cache()

    def clear_all_resume_positions(self):
        """清除所有断点"""
        with self._facade._lock:
            self._resume_cache = {}
            try:
                if os.path.exists(self._resume_file):
                    os.remove(self._resume_file)
            except Exception as e:
                logger.debug(f"清除断点文件失败: {e}")