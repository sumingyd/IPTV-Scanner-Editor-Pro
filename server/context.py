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
        self._scan_mode: Optional[str] = None  # 'subscription' 或 'range'
        self._scan_results: List[Dict] = []  # URL 范围扫描结果列表

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
            self._scan_mode = 'subscription'
        self._thread = threading.Thread(target=self._scan_worker, args=(url,), daemon=True)
        self._thread.start()
        return True

    def stop_scan(self):
        """请求停止扫描"""
        self._stop_event.set()

    def start_range_scan(self, base_url: str, timeout: int = 10, threads: int = 4) -> bool:
        """开始 URL 范围扫描（PC 端"扫描整理"功能）

        解析方括号范围表达式（如 rtp://239.1.1.[1-255]:5002），
        命名变量同步：[1-255:n] 定义变量 n，{n} 引用（两处 n 同步变化）。
        对每个 URL 做可达性检查（HTTP/HTTPS 用 requests HEAD），
        将有效 URL 添加为频道。rtp/udp/rtsp 等非 HTTP 协议直接添加不验证。
        """
        with self._lock:
            if self.running:
                return False
            self.running = True
            self._stop_event.clear()
            self.stats = {'total': 0, 'valid': 0, 'invalid': 0, 'scanned': 0}
            self._scan_mode = 'range'
        self._thread = threading.Thread(
            target=self._range_scan_worker, args=(base_url, timeout, threads), daemon=True
        )
        self._thread.start()
        return True

    def _range_scan_worker(self, base_url: str, timeout: int, threads: int):
        """URL 范围扫描工作线程"""
        try:
            from services.url_parser_service import URLRangeParser
            parser = URLRangeParser()
            # 先统计总 URL 数
            all_urls: List[str] = []
            for batch in parser.parse_url(base_url, batch_size=1000):
                for u in batch:
                    if self._stop_event.is_set():
                        break
                    all_urls.append(u)
                if self._stop_event.is_set():
                    break
            with self._lock:
                self.stats['total'] = len(all_urls)
                self._scan_results = []  # 清空上次扫描结果
            if not all_urls:
                self.last_message = '无 URL 可扫描（检查范围表达式）'
                return
            self.last_message = f'开始扫描 {len(all_urls)} 个 URL（{threads} 线程）'
            logger.info(f"URL 范围扫描：共 {len(all_urls)} 个 URL")

            from concurrent.futures import ThreadPoolExecutor, as_completed
            import requests as _requests
            import socket
            from urllib.parse import urlparse
            found_channels: List[Dict] = []
            scan_results: List[Dict] = []  # 完整扫描结果列表（含有效/无效）
            scanned_count = 0
            valid_count = 0
            invalid_count = 0

            def _check_one(u: str):
                """验证单个 URL，返回 (url, valid, status, latency_ms, channel_or_none)"""
                if self._stop_event.is_set():
                    return (u, False, '已取消', 0, None)
                low = u.lower()
                name = u.split('/')[-1] or u.split('://')[-1] or u
                import time as _t
                t0 = _t.time()
                # HTTP/HTTPS：用 HEAD 请求验证可达性
                if low.startswith('http://') or low.startswith('https://'):
                    try:
                        r = _requests.head(u, timeout=timeout, allow_redirects=True,
                                           headers={'User-Agent': 'IPTV-Scanner/1.0'})
                        latency = int((_t.time() - t0) * 1000)
                        if r.status_code < 400:
                            ch = {'name': name, 'url': u, 'group': '扫描结果', 'logo': '',
                                  'tvg_id': '', 'tvg_name': name, 'valid': True}
                            return (u, True, f'HTTP {r.status_code}', latency, ch)
                        return (u, False, f'HTTP {r.status_code}', latency, None)
                    except Exception as e:
                        latency = int((_t.time() - t0) * 1000)
                        return (u, False, f'错误: {str(e)[:60]}', latency, None)
                # RTSP：用 TCP socket 连接检查
                if low.startswith('rtsp://'):
                    try:
                        parsed = urlparse(u)
                        host = parsed.hostname or ''
                        port = parsed.port or 554
                        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        sock.settimeout(timeout)
                        sock.connect((host, port))
                        sock.close()
                        latency = int((_t.time() - t0) * 1000)
                        ch = {'name': name, 'url': u, 'group': '扫描结果', 'logo': '',
                              'tvg_id': '', 'tvg_name': name, 'valid': True}
                        return (u, True, 'RTSP 可达', latency, ch)
                    except Exception as e:
                        latency = int((_t.time() - t0) * 1000)
                        return (u, False, f'RTSP: {str(e)[:40]}', latency, None)
                # RTP/UDP：尝试加入组播组并接收数据包验证可达性
                # 与 PC 端 ffprobe 验证效果类似：能收到数据则视为有效
                if low.startswith('rtp://') or low.startswith('udp://'):
                    try:
                        parsed = urlparse(u)
                        host = parsed.hostname or ''
                        port = parsed.port or 5004
                        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
                        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                        # 短超时：扫描时使用 timeout/2（最多 5 秒），避免长时间阻塞
                        sock_timeout = min(max(timeout // 2, 1), 5) if timeout else 3
                        sock.settimeout(sock_timeout)
                        try:
                            # 组播地址（224.0.0.0 - 239.255.255.255）需要 join 才能接收
                            parts = host.split('.')
                            is_multicast = (len(parts) == 4
                                            and 224 <= int(parts[0]) <= 239
                                            and all(0 <= int(p) <= 255 for p in parts))
                            if is_multicast:
                                # IP_ADD_MEMBERSHIP：加入组播组
                                mreq = socket.inet_aton(host) + socket.inet_aton('0.0.0.0')
                                sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
                            # 绑定到组播端口（监听任意来源）
                            sock.bind(('', port))
                            # 尝试接收第一个数据包
                            data, addr = sock.recvfrom(2048)
                            latency = int((_t.time() - t0) * 1000)
                            ch = {'name': name, 'url': u, 'group': '扫描结果', 'logo': '',
                                  'tvg_id': '', 'tvg_name': name, 'valid': True}
                            return (u, True, f'收到数据 {len(data)}B', latency, ch)
                        finally:
                            try: sock.close()
                            except: pass
                    except socket.timeout:
                        latency = int((_t.time() - t0) * 1000)
                        # 超时未收到数据：不添加为频道（避免生成大量无效频道）
                        return (u, False, '超时无数据', latency, None)
                    except OSError as e:
                        latency = int((_t.time() - t0) * 1000)
                        # 组播 join 失败/权限不足等：标记无效但不影响其他扫描
                        return (u, False, f'无法验证: {str(e)[:40]}', latency, None)
                # 其他协议：标记为不支持
                return (u, False, '不支持的协议', 0, None)

            with ThreadPoolExecutor(max_workers=max(1, min(threads, 64))) as pool:
                futures = {pool.submit(_check_one, u): u for u in all_urls}
                for fut in as_completed(futures):
                    if self._stop_event.is_set():
                        break
                    scanned_count += 1
                    try:
                        url, valid, status, latency, ch = fut.result()
                        # 记录扫描结果（用于前端列表显示）
                        result_item = {
                            'url': url, 'name': ch['name'] if ch else url.split('/')[-1],
                            'valid': valid, 'status': status, 'latency': latency,
                            'group': '扫描结果'
                        }
                        scan_results.append(result_item)
                        if ch:
                            found_channels.append(ch)
                            if valid is True:
                                valid_count += 1
                        else:
                            invalid_count += 1
                    except Exception as e:
                        scan_results.append({
                            'url': futures[fut], 'name': futures[fut].split('/')[-1],
                            'valid': False, 'status': f'异常: {str(e)[:40]}', 'latency': 0,
                            'group': '扫描结果'
                        })
                        invalid_count += 1
                    with self._lock:
                        self.stats['scanned'] = scanned_count
                        self.stats['valid'] = valid_count
                        self.stats['invalid'] = invalid_count
                        self._scan_results = list(scan_results)  # 实时更新结果列表
                    if scanned_count % 10 == 0:
                        self.last_message = f'已扫描 {scanned_count}/{len(all_urls)}（有效 {valid_count}）'

            # 保存完整结果列表
            with self._lock:
                self._scan_results = scan_results
            if found_channels and not self._stop_event.is_set():
                # 追加到现有频道列表（不覆盖订阅源加载的频道）
                self._ctx._channels = self._ctx._channels + found_channels
                import time
                self._ctx._last_load_time = time.time()
                self.last_message = f'完成：发现 {len(found_channels)} 个有效频道'
                logger.info(f"URL 范围扫描完成，发现 {len(found_channels)} 个有效频道")
            elif self._stop_event.is_set():
                self.last_message = '已停止'
            else:
                self.last_message = f'完成：未发现有效频道（扫描 {scanned_count} 个）'
        except Exception as e:
            logger.error(f"URL 范围扫描异常: {e}")
            self.last_message = f'扫描异常: {e}'
        finally:
            with self._lock:
                self.running = False
                self._scan_mode = None

    def get_status(self) -> Dict:
        with self._lock:
            return {
                'running': self.running,
                'total': self.stats.get('total', 0),
                'valid': self.stats.get('valid', 0),
                'invalid': self.stats.get('invalid', 0),
                'scanned': self.stats.get('scanned', 0),
                'message': self.last_message,
                'mode': getattr(self, '_scan_mode', None),
            }

    def get_results(self) -> List[Dict]:
        """获取 URL 范围扫描结果列表"""
        with self._lock:
            return list(self._scan_results)

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
        import threading as _threading
        self._main_window = main_window
        self._config: Optional[ConfigManager] = None
        self._channels: List[Dict] = []
        self._sources: List[Dict] = []
        self._epg_data: Dict = {}
        self._standalone = main_window is None
        self._last_load_time = 0.0
        self._standalone_scanner: Optional[StandaloneScanner] = None
        self._epg_parser = None  # standalone 模式下使用的 EPG 解析器
        # 订阅源加载状态（独立于扫描整理功能）
        self._source_loading = False
        self._source_load_status: Dict = {'loading': False, 'total': 0, 'loaded': 0, 'channels': 0, 'message': '空闲'}
        self._source_load_lock = _threading.Lock()

        if self._standalone:
            self._config = ConfigManager()
            self._standalone_scanner = StandaloneScanner(self)
            _threading.Thread(target=self._load_channels_from_file, daemon=True).start()
            # 异步初始化 EPG 解析器（不依赖 PySide6）
            _threading.Thread(target=self._init_epg_parser, daemon=True).start()

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

    def reload_sources(self, url: str = '') -> bool:
        """重新加载订阅源（独立于扫描整理功能）

        - url 为空：重新加载所有已配置的订阅源
        - url 非空：加载指定 URL 的订阅源
        返回 True 表示已启动加载，False 表示已有加载在运行
        """
        with self._source_load_lock:
            if self._source_loading:
                return False
            self._source_loading = True
            self._source_load_status = {'loading': True, 'total': 0, 'loaded': 0, 'channels': 0, 'message': '开始加载'}
        import threading
        threading.Thread(target=self._reload_sources_worker, args=(url,), daemon=True).start()
        return True

    def _reload_sources_worker(self, url: str):
        """订阅源加载工作线程（后台静默执行，不使用扫描状态）"""
        try:
            config = self._config
            if not config:
                with self._source_load_lock:
                    self._source_loading = False
                    self._source_load_status = {'loading': False, 'total': 0, 'loaded': 0, 'channels': 0, 'message': '配置未初始化'}
                return

            # 收集要加载的源
            if url:
                sources = [{'url': url, 'name': url, 'enabled': True}]
            else:
                try:
                    sources = config.load_playlist_sources()
                except Exception as e:
                    logger.warning(f"加载订阅源列表失败: {e}")
                    sources = []

            with self._source_load_lock:
                self._source_load_status['total'] = len(sources)

            if not sources:
                with self._source_load_lock:
                    self._source_loading = False
                    self._source_load_status = {'loading': False, 'total': 0, 'loaded': 0, 'channels': 0, 'message': '无订阅源'}
                return

            all_channels: List[Dict] = []
            errors: List[str] = []  # 记录每个源的加载失败原因
            for idx, source in enumerate(sources):
                src_url = source.get('url', '')
                if not src_url or not source.get('enabled', True):
                    continue
                with self._source_load_lock:
                    self._source_load_status['loaded'] = idx + 1
                    self._source_load_status['message'] = f'加载中 {idx+1}/{len(sources)}'
                try:
                    import requests
                    resp = requests.get(src_url, timeout=15, headers={'User-Agent': 'IPTV-Scanner/1.0'})
                    if resp.status_code != 200:
                        err = f'HTTP {resp.status_code}'
                        errors.append(err)
                        logger.warning(f"加载源 {src_url} 失败: {err}")
                        continue
                    content = load_m3u_from_url_data(resp.content)
                    channels, _ = parse_m3u_content(content)
                    # 更新该源的 last_update 时间戳（无论是否解析到频道，HTTP 拉取已成功）
                    from datetime import datetime
                    config.update_playlist_source_last_update(idx, datetime.now().isoformat())
                    if channels:
                        all_channels.extend(channels)
                    else:
                        err = 'M3U 解析为空'
                        errors.append(err)
                        logger.warning(f"加载源 {src_url} M3U 解析为空（内容长度 {len(content)}）")
                except Exception as e:
                    err = str(e)[:60]
                    errors.append(err)
                    logger.warning(f"加载源 {src_url} 异常: {e}")

            # 更新频道列表
            if all_channels:
                self._channels = all_channels
                import time
                self._last_load_time = time.time()
                with self._source_load_lock:
                    self._source_loading = False
                    self._source_load_status = {'loading': False, 'total': len(sources), 'loaded': len(sources), 'channels': len(all_channels), 'message': f'完成：{len(all_channels)} 个频道'}
                logger.info(f"订阅源加载完成，共 {len(all_channels)} 个频道")
            else:
                # 加载到空列表时不覆盖已有频道，提示当前频道数和失败原因
                existing = len(self._channels)
                if existing > 0:
                    msg = f'本次未加载到新频道（现有 {existing} 个）'
                elif errors:
                    # 显示首个失败原因，让用户知道为什么加载失败
                    msg = f'加载失败：{errors[0]}'
                else:
                    msg = '未加载到频道'
                with self._source_load_lock:
                    self._source_loading = False
                    self._source_load_status = {'loading': False, 'total': len(sources), 'loaded': len(sources), 'channels': existing, 'message': msg}
        except Exception as e:
            logger.error(f"订阅源加载异常: {e}")
            with self._source_load_lock:
                self._source_loading = False
                self._source_load_status = {'loading': False, 'total': 0, 'loaded': 0, 'channels': 0, 'message': f'异常: {e}'}

    def get_source_load_status(self) -> Dict:
        """获取订阅源加载状态"""
        with self._source_load_lock:
            return dict(self._source_load_status)


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