import os
import sys
import threading
import logging
from typing import Optional, List, Dict

from core.config_manager import ConfigManager
from services.m3u_parser import load_m3u_from_url_data, parse_m3u_content

logger = logging.getLogger('server.context')


class StandaloneScanner:
    """独立模式（Android/无 GUI）下的扫描器

    不依赖 PySide6，使用 requests + 线程池实现：
    - 重新加载订阅源（start_scan）
    - 验证频道 URL 可达性（start_validate）
    - 维护扫描统计与停止控制
    """

    def __init__(self, ctx: "ServerContext"):
        self._ctx = ctx
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.stats: Dict[str, int] = {
            'total': 0,
            'valid': 0,
            'invalid': 0,
            'scanned': 0,
        }
        self.running = False
        self.last_message = '空闲'

    def is_scanning(self) -> bool:
        return self.running

    def start_scan(self, url: str = '') -> bool:
        """开始扫描：重新加载订阅源

        - url 为空：重新加载所有已配置的订阅源
        - url 非空：将该 URL 作为新订阅源添加并加载
        返回 True 表示已成功启动，False 表示已有扫描在运行
        """
        with self._lock:
            if self.running:
                return False
            self.running = True
            self._stop_event.clear()
            self.stats = {'total': 0, 'valid': 0, 'invalid': 0, 'scanned': 0}
        self._thread = threading.Thread(target=self._scan_worker, args=(url,), daemon=True)
        self._thread.start()
        return True

    def stop_scan(self):
        """请求停止扫描"""
        self._stop_event.set()

    def get_status(self) -> Dict:
        with self._lock:
            return {
                'running': self.running,
                'total': self.stats.get('total', 0),
                'valid': self.stats.get('valid', 0),
                'invalid': self.stats.get('invalid', 0),
                'scanned': self.stats.get('scanned', 0),
                'message': self.last_message,
            }

    def _scan_worker(self, url: str):
        """扫描工作线程"""
        try:
            config = self._ctx.get_config()
            if not config:
                self.last_message = '配置未初始化'
                return

            # 收集要扫描的源
            sources_to_scan = []
            if url:
                # 单 URL 扫描：临时加入源列表
                sources_to_scan.append({'url': url, 'name': url, 'enabled': True})
            else:
                # 扫描所有已配置的源
                try:
                    sources_to_scan = config.load_playlist_sources()
                except Exception as e:
                    logger.warning(f"加载订阅源列表失败: {e}")
                    sources_to_scan = []

            if not sources_to_scan:
                self.last_message = '无订阅源'
                return

            self.last_message = f'正在加载 {len(sources_to_scan)} 个订阅源'
            all_channels: List[Dict] = []
            with self._lock:
                self.stats['total'] = len(sources_to_scan)

            for idx, source in enumerate(sources_to_scan):
                if self._stop_event.is_set():
                    self.last_message = '已停止'
                    break
                src_url = source.get('url', '')
                if not src_url or not source.get('enabled', True):
                    continue
                try:
                    import requests
                    resp = requests.get(src_url, timeout=15, headers={'User-Agent': 'IPTV-Scanner/1.0'})
                    content = load_m3u_from_url_data(resp.content)
                    channels, _ = parse_m3u_content(content)
                    if channels:
                        all_channels.extend(channels)
                        with self._lock:
                            self.stats['valid'] += len(channels)
                    self.last_message = f'已加载 {src_url[:40]}: {len(channels)} 个频道'
                except Exception as e:
                    logger.warning(f"扫描源 {src_url} 失败: {e}")
                    with self._lock:
                        self.stats['invalid'] += 1
                    self.last_message = f'加载失败: {src_url[:40]}'
                finally:
                    with self._lock:
                        self.stats['scanned'] = idx + 1

            # 更新 context 的频道列表
            if all_channels and not self._stop_event.is_set():
                self._ctx._channels = all_channels
                import time
                self._ctx._last_load_time = time.time()
                self.last_message = f'完成：共 {len(all_channels)} 个频道'
                logger.info(f"独立模式扫描完成，加载了 {len(all_channels)} 个频道")
            elif self._stop_event.is_set():
                self.last_message = '已停止'
            else:
                self.last_message = '未加载到任何频道'
        except Exception as e:
            logger.error(f"独立模式扫描异常: {e}")
            self.last_message = f'扫描异常: {e}'
        finally:
            with self._lock:
                self.running = False


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
        self._standalone_scanner: Optional[StandaloneScanner] = None
        self._epg_parser = None  # standalone 模式下使用的 EPG 解析器

        if self._standalone:
            self._config = ConfigManager()
            self._standalone_scanner = StandaloneScanner(self)
            import threading
            threading.Thread(target=self._load_channels_from_file, daemon=True).start()
            # 异步初始化 EPG 解析器（不依赖 PySide6）
            threading.Thread(target=self._init_epg_parser, daemon=True).start()

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
        return self._epg_parser

    def _init_epg_parser(self):
        """独立模式：初始化 EPG 解析器（使用 SubscriptionManager 单例）

        SubscriptionManager 不依赖 PySide6，可在 Android/无 GUI 环境运行。
        若已配置 EPG 订阅源，则后台加载 EPG 数据。
        """
        try:
            from core.subscription_manager import SubscriptionManager
            sm = SubscriptionManager()
            self._epg_parser = sm
            # 若已有 EPG 源则尝试加载缓存或后台拉取
            sources = sm.get_epg_sources() if hasattr(sm, 'get_epg_sources') else []
            if sources:
                logger.info(f"独立模式：检测到 {len(sources)} 个 EPG 源，开始后台加载 EPG 数据")
                threading.Thread(target=self._load_epg_async, args=(sm,), daemon=True).start()
            else:
                logger.info("独立模式：未配置 EPG 源，跳过 EPG 加载")
        except Exception as e:
            logger.error(f"独立模式初始化 EPG 解析器失败: {e}")

    def _load_epg_async(self, sm):
        """后台加载 EPG 数据"""
        try:
            sm.load_all_epg_data()
        except Exception as e:
            logger.error(f"独立模式后台加载 EPG 失败: {e}")

    def reload_epg(self):
        """重新加载 EPG 数据（添加 EPG 源后调用）"""
        if not self._standalone or not self._epg_parser:
            return False
        import threading
        threading.Thread(target=self._load_epg_async, args=(self._epg_parser,), daemon=True).start()
        return True

    def get_scan_dialog(self):
        if self._main_window and hasattr(self._main_window, '_scan_dialog'):
            return self._main_window._scan_dialog
        return None

    def get_standalone_scanner(self) -> Optional[StandaloneScanner]:
        """获取独立模式扫描器（standalone 模式下可用）"""
        return self._standalone_scanner

    def get_main_window(self):
        return self._main_window

    def is_standalone(self):
        return self._standalone