import os
import sys
import logging
from typing import Optional, List, Dict

from core.config_manager import ConfigManager
from services.m3u_parser import load_m3u_from_url_data, parse_m3u_content

logger = logging.getLogger('server.context')


class ServerContext:
    _instance = None

    def __init__(self, main_window=None):
        self._main_window = main_window
        self._config: Optional[ConfigManager] = None
        self._channels: List[Dict] = []
        self._sources: List[Dict] = []
        self._epg_data: Dict = {}
        self._standalone = main_window is None
        self._last_load_time = 0.0

        if self._standalone:
            self._config = ConfigManager()
            import threading
            threading.Thread(target=self._load_channels_from_file, daemon=True).start()

    @classmethod
    def get_instance(cls, main_window=None):
        if cls._instance is None:
            cls._instance = cls(main_window)
        elif main_window is not None:
            cls._instance._main_window = main_window
            cls._instance._standalone = False
        return cls._instance

    def _load_channels_from_file(self):
        if not self._config:
            return
        try:
            sources = self._config.load_playlist_sources()
            self._sources = sources
            all_channels = []
            for source in sources:
                if not source.get('enabled', True):
                    continue
                url = source.get('url', '')
                if not url:
                    continue
                try:
                    import requests
                    resp = requests.get(url, timeout=15)
                    content = load_m3u_from_url_data(resp.content)
                    channels, _ = parse_m3u_content(content)
                    if channels:
                        all_channels.extend(channels)
                except Exception as e:
                    logger.warning(f"加载源 {url} 失败: {e}")
            self._channels = all_channels
            import time
            self._last_load_time = time.time()
            logger.info(f"独立模式加载了 {len(all_channels)} 个频道")
        except Exception as e:
            logger.error(f"加载频道数据失败: {e}")

    def reload_if_needed(self, max_age=300):
        if not self._standalone:
            return
        import time
        if time.time() - self._last_load_time > max_age:
            self._load_channels_from_file()

    def get_all_channels(self) -> List[Dict]:
        if self._main_window:
            channels = []
            sub = getattr(self._main_window, '_sub_channels', [])
            local = getattr(self._main_window, '_local_channels', [])
            seen = set()
            for ch in sub:
                url = ch.get('url', '')
                if url and url not in seen:
                    channels.append(ch)
                    seen.add(url)
            for ch in local:
                url = ch.get('url', '')
                if url and url not in seen:
                    channels.append(ch)
                    seen.add(url)
            if not channels:
                model = getattr(self._main_window, 'channel_model', None)
                if model:
                    for i in range(model.rowCount()):
                        ch = model.get_channel(i)
                        if ch:
                            channels.append(ch)
            return channels
        self.reload_if_needed()
        return self._channels

    def get_channel_model(self):
        if self._main_window and hasattr(self._main_window, 'channel_model'):
            return self._main_window.channel_model
        return None

    def get_config(self) -> Optional[ConfigManager]:
        if self._main_window and hasattr(self._main_window, 'config'):
            return self._main_window.config
        return self._config

    def get_epg_parser(self):
        if self._main_window and hasattr(self._main_window, 'epg_parser'):
            return self._main_window.epg_parser
        return None

    def get_scan_dialog(self):
        if self._main_window and hasattr(self._main_window, '_scan_dialog'):
            return self._main_window._scan_dialog
        return None

    def get_main_window(self):
        return self._main_window

    def is_standalone(self):
        return self._standalone