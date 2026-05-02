"""
订阅控制器 - 负责订阅源管理、EPG加载、频道分组等
从 pyqt_player.py 提取的独立模块
"""

import re
import sys
import hashlib
import os
import requests
from typing import Optional, Dict, Any
from datetime import datetime
from PyQt6.QtCore import QThread, pyqtSignal, QTimer

from core.log_manager import global_logger as logger
from core.config_manager import ConfigManager
from core.subscription_manager import global_subscription_manager
from utils.general_utils import get_display_channel_name


class SubscriptionWorker(QThread):
    """后台线程处理订阅更新"""
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, callback, parent=None):
        super().__init__(parent)
        self._callback = callback

    def run(self):
        try:
            result = self._callback()
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class SubscriptionController:
    """订阅控制器 - 管理所有订阅源相关的逻辑"""

    def __init__(self, main_window):
        self.window = main_window
        self._subscription_checked = False
        self._workers = []
        self._last_header_attrs = {}
        self._last_header_epg_url = None

    def handle_playlist_subscription(self, need_update: bool, playlist_url: str, source_index=None):
        """在后台线程中处理列表订阅（按源索引独立判断）"""
        try:
            global CHANNELS

            if not playlist_url:
                logger.debug("无播放列表URL，跳过订阅处理")
                return

            logger.debug(f"处理列表订阅: url={playlist_url[:50]}..., need_update={need_update}, source_index={source_index}")

            if need_update:
                logger.info(f"需要更新订阅源，开始下载: {playlist_url[:50]}...")
                content = self._download_subscription_content(playlist_url)

                if content:
                    self._save_to_local_cache(content, playlist_url)
                    self._process_m3u_content(content, playlist_url, source_index)
                else:
                    logger.warning(f"下载订阅内容为空: {playlist_url}")
            else:
                logger.debug("使用缓存数据，无需更新")
                cached_content = self._load_from_local_cache(playlist_url)
                if cached_content:
                    logger.debug("从本地缓存加载M3U数据")
                    self._process_m3u_content(cached_content, playlist_url, source_index)
                else:
                    logger.warning("本地缓存不存在，强制重新下载")
                    content = self._download_subscription_content(playlist_url)
                    if content:
                        self._save_to_local_cache(content, playlist_url)
                        self._process_m3u_content(content, playlist_url, source_index)

        except Exception as e:
            logger.error(f"处理列表订阅失败: {e}", exc_info=True)

    def _download_subscription_content(self, url: str) -> Optional[str]:
        """下载订阅内容"""
        config = ConfigManager()
        timeout = int(config.get_value('Network', 'timeout', '30') or 30)

        headers = {}
        user_agent = config.get_value('Network', 'user_agent', '')
        referer = config.get_value('Network', 'referer', '')
        if user_agent:
            headers['User-Agent'] = user_agent
        if referer:
            headers['Referer'] = referer

        try:
            response = requests.get(url, timeout=timeout, headers=headers,
                                   allow_redirects=True, verify=False)
            response.raise_for_status()
            return response.text
        except requests.exceptions.Timeout:
            logger.warning(f"下载超时: {url}")
            return None
        except Exception as e:
            logger.error(f"下载失败: {url}, 错误: {e}")
            return None

    def _get_cache_file_path(self, url: str) -> str:
        """获取缓存文件路径（基于URL的hash）"""
        cache_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'cache')
        os.makedirs(cache_dir, exist_ok=True)
        url_hash = hashlib.md5(url.encode()).hexdigest()
        return os.path.join(cache_dir, f'm3u_{url_hash}.cache')

    def _save_to_local_cache(self, content: str, url: str):
        """保存M3U内容到本地缓存"""
        try:
            cache_path = self._get_cache_file_path(url)
            with open(cache_path, 'w', encoding='utf-8') as f:
                f.write(content)
            logger.debug(f"M3U内容已保存到本地缓存: {cache_path}")
        except Exception as e:
            logger.warning(f"保存M3U缓存失败: {e}")

    def _load_from_local_cache(self, url: str) -> str | None:
        """从本地缓存加载M3U内容"""
        try:
            cache_path = self._get_cache_file_path(url)
            if not os.path.exists(cache_path):
                return None
            with open(cache_path, 'r', encoding='utf-8') as f:
                content = f.read()
            logger.debug(f"从本地缓存加载M3U内容: {cache_path}, 大小: {len(content)} 字节")
            return content
        except Exception as e:
            logger.warning(f"加载M3U缓存失败: {e}")
            return None

    def _process_m3u_content(self, content: str, file_path: str, source_index=None):
        """处理M3U内容（纯Python解析，避免子线程中操作Qt对象）"""
        try:
            # 使用纯 Python 方式解析 M3U 内容（不依赖 Qt 对象）
            channels_data, header_attrs = self._parse_m3u_content_pure_python(content)
            self._last_header_attrs = header_attrs

            if not channels_data:
                logger.warning(f"M3U内容解析为空: {file_path[:50]}...")
                return

            logger.info(f"M3U处理完成，共 {len(channels_data)} 个频道（数据已准备就绪，等待主线程回调刷新UI）")

            # 保存原始文件内容到配置
            config = ConfigManager()

            if file_path.startswith('http'):
                config.add_recent_file(file_path)

                # 更新订阅源的最后下载时间（用于缓存判断）
                sources = global_subscription_manager.get_playlist_sources()
                for idx, src in enumerate(sources):
                    if src.get('url') == file_path:
                        global_subscription_manager.update_playlist_source_last_update(
                            idx, datetime.now().isoformat()
                        )
                        break

            # 获取主模块和 ApplicationState
            import sys
            main_module = sys.modules.get('__main__')
            app_state = getattr(__import__('core.application_state', fromlist=['application_state']), 'app_state', None)

            # 同时更新所有相关的数据源（关键：必须修改原列表对象，而不是创建新列表）

            # 1. 更新 ApplicationState 的 _channels（使用 clear + extend 保持引用不变）
            if app_state and hasattr(app_state, '_channels'):
                app_state._channels.clear()
                app_state._channels.extend(channels_data)

            # 2. 更新 __main__ 模块的 CHANNELS（如果存在且是同一个对象）
            if main_module and hasattr(main_module, 'CHANNELS'):
                if main_module.CHANNELS is not app_state._channels:
                    main_module.CHANNELS.clear()
                    main_module.CHANNELS.extend(channels_data)

            # 3. 记录文件头EPG地址（在订阅EPG加载后再作为补充源加载）
            epg_url = header_attrs.get('epg_url', '')
            if epg_url:
                self._last_header_epg_url = epg_url
                logger.info(f"M3U文件头包含EPG地址: {epg_url[:80]}，将在订阅EPG加载后补充")
            else:
                self._last_header_epg_url = None

        except Exception as e:
            logger.error(f"处理M3U内容失败: {e}", exc_info=True)

    def _parse_m3u_content_pure_python(self, content: str) -> tuple:
        """纯 Python 解析 M3U 内容（不依赖 Qt 对象，线程安全）

        Args:
            content: M3U 文件内容

        Returns:
            频道数据列表
        """
        channels = []
        lines = content.split('\n')

        current_channel = None
        url = None
        header_attrs = {}

        for line in lines:
            line = line.strip()

            if not line:
                continue

            # M3U 文件头 - 提取全局属性（EPG地址、回看参数等）
            if line.startswith('#EXTM3U'):
                from services.m3u_parser import extract_header_attributes
                header_attrs = extract_header_attributes(line)
                if header_attrs.get('epg_url'):
                    logger.info(f"M3U文件头发现EPG地址: {header_attrs['epg_url'][:80]}")
                continue

            # EXTINF 行（频道信息）
            if line.startswith('#EXTINF:'):
                extinf_line = line[8:]  # 去掉 '#EXTINF:'
                current_channel = self._parse_extinf(extinf_line)
                # 继承全局回看参数（频道级别未设置时使用全局设置）
                if current_channel and header_attrs:
                    for k, v in header_attrs.items():
                        if k == 'epg_url':
                            continue
                        field_map = {
                            'catchup': 'catchup',
                            'catchup-correction': 'catchup_correction',
                            'catchup-source': 'catchup_source',
                            'catchup-days': 'catchup_days',
                            'catchup-type': 'catchup',
                        }
                        field = field_map.get(k, k.replace('-', '_'))
                        if not current_channel.get(field):
                            current_channel[field] = v
                            if '_all_tags' in current_channel:
                                current_channel['_all_tags'][k] = v
                continue

            # URL 行
            if not line.startswith('#') and current_channel is not None:
                url = line.strip()
                current_channel['url'] = url

                # 添加到频道列表
                channels.append(current_channel)
                current_channel = None
                url = None

        # 设置频道 ID
        for i, ch in enumerate(channels):
            ch['id'] = i + 1

        return channels, header_attrs

    def _parse_extinf(self, extinf_line: str) -> dict:
        """解析 EXTINF 行"""
        channel_data = {
            "id": 0,
            "name": '未命名',
            "url": '',
            "logo": '',
            "group": '未分类',
            "_groups": ['未分类'],
            "tvg_id": '',
            "tvg_chno": '',
            "tvg_shift": '',
            "catchup": '',
            "catchup_days": '',
            "catchup_source": '',
            "catchup_correction": '',
            "resolution": '',
            "current_program": '',
            "_raw_extinf": extinf_line,
            "_all_tags": {}
        }

        name = ''
        if ',' in extinf_line:
            parts = extinf_line.rsplit(',', 1)
            name = parts[1].strip()
            attr_part = parts[0]
        else:
            name = extinf_line.strip()
            attr_part = ''

        channel_data['name'] = name or '未命名'

        attrs_pattern = r'([\w-]+)=["\']([^"\']*)["\']'
        matches = re.findall(attrs_pattern, attr_part)

        all_tags = {}
        groups = []

        for key, value in matches:
            all_tags[key] = value
            if key == 'tvg-id':
                channel_data['tvg_id'] = value
            elif key == 'tvg-chno':
                channel_data['tvg_chno'] = value
            elif key == 'tvg-shift':
                channel_data['tvg_shift'] = value
            elif key == 'group-title' and value:
                split_groups = [g.strip() for g in value.split(';') if g.strip()]
                groups.extend(split_groups)
            elif key == 'tvg-logo':
                channel_data['logo'] = value
            elif key == 'catchup':
                channel_data['catchup'] = value
            elif key == 'catchup-days':
                channel_data['catchup_days'] = value
            elif key == 'catchup-source':
                channel_data['catchup_source'] = value
            elif key == 'catchup-correction':
                channel_data['catchup_correction'] = value
            elif key == 'catchup-type':
                if not channel_data['catchup']:
                    channel_data['catchup'] = value

        if groups:
            channel_data['_groups'] = groups
            channel_data['group'] = groups[0]

        channel_data['_all_tags'] = all_tags

        return channel_data

    def _get_display_channel_name(self, channel: Dict[str, Any]) -> str:
        """获取用于显示的频道名称（委托给通用工具函数）"""
        language_manager = getattr(self.window, 'language_manager', None)
        return get_display_channel_name(channel, language_manager)

    def _should_update_source(self, source: dict, source_index: int) -> bool:
        """判断订阅源是否需要更新（基于缓存机制）

        Args:
            source: 订阅源配置字典
            source_index: 订阅源索引

        Returns:
            True 表示需要更新，False 表示使用缓存
        """
        # 获取最后更新时间
        last_update_str = source.get('last_update', '')

        if not last_update_str:
            logger.debug(f"订阅源 '{source.get('name', '')}' 无缓存记录，需要下载")
            return True

        try:
            last_update = datetime.fromisoformat(last_update_str)
        except (ValueError, TypeError):
            logger.warning(f"订阅源 '{source.get('name', '')}' 缓存时间格式无效: {last_update_str}，需要重新下载")
            return True

        # 获取更新间隔配置（分钟）
        config = ConfigManager()
        update_interval = int(config.get_value('PlaylistSources', 'update_interval', '60') or 60)

        now = datetime.now()
        elapsed = (now - last_update).total_seconds() / 60  # 转换为分钟

        if elapsed >= update_interval:
            logger.info(f"订阅源 '{source.get('name', '')}' 缓存已过期（上次: {last_update_str}, 已过 {elapsed:.0f} 分钟, 间隔: {update_interval} 分钟）")
            return True

        logger.debug(f"订阅源 '{source.get('name', '')}' 缓存有效（上次: {last_update_str}, 已过 {elapsed:.0f} 分钟, 间隔: {update_interval} 分钟）")
        return False

    def start_subscription_timers(self):
        """启动订阅更新定时器"""
        logger.debug("start_subscription_timers: 开始")

        try:
            global EPG_DATA, CHANNELS

            active_source = global_subscription_manager.get_active_playlist_source()
            playlist_url = active_source.get('url', '') if active_source else ''

            if not playlist_url:
                logger.debug("无活跃的播放列表源")
                return

            # 启动后台更新
            worker = SubscriptionWorker(
                lambda: self._do_start_subscription(playlist_url),
                self.window
            )
            worker.finished.connect(self._on_subscription_finished)
            worker.error.connect(lambda err: logger.error(f"订阅更新错误: {err}"))
            self._workers.append(worker)
            worker.start()

        except Exception as e:
            logger.error(f"启动订阅定时器失败: {e}", exc_info=True)

    def _do_start_subscription(self, playlist_url: str):
        """执行订阅更新"""
        sources = global_subscription_manager.get_playlist_sources()
        if not sources:
            logger.warning("没有配置播放列表源")
            return False

        for i, source in enumerate(sources):
            if source.get('url') == playlist_url:
                need_update = self._should_update_source(source, i)
                logger.debug(f"订阅源 '{source.get('name', '')}' 需要更新: {need_update}")
                self.handle_playlist_subscription(need_update, playlist_url, i)

                from PyQt6.QtCore import QMetaObject, Qt, QThread
                if QThread.currentThread() != self.window.thread():
                    QMetaObject.invokeMethod(
                        self.window, "_do_on_playlist_updated_in_main_thread",
                        Qt.ConnectionType.QueuedConnection
                    )
                else:
                    self.window._do_on_playlist_updated_in_main_thread()
                break

        final_need_epg = [True]

        def status_callback(msg):
            logger.debug(f"EPG加载状态: {msg}")

        need_download_epg = not global_subscription_manager.is_epg_valid()

        if not need_download_epg:
            logger.debug("EPG缓存有效，从本地缓存加载")
            cached_loaded = global_subscription_manager.load_cached_epg_data()
            if cached_loaded:
                main_module = sys.modules.get('__main__')
                if main_module:
                    main_module.EPG_DATA = global_subscription_manager._epg_data
                success = True
            else:
                logger.warning("EPG缓存加载失败，重新下载")
                need_download_epg = True

        if need_download_epg:
            logger.info("EPG缓存无效或不存在，重新下载所有EPG源")
            success = global_subscription_manager.load_all_epg_data(status_callback)
            if success:
                main_module = sys.modules.get('__main__')
                if main_module:
                    main_module.EPG_DATA = global_subscription_manager._epg_data

            # EPG重新下载时，补充加载M3U文件头中的EPG
            header_epg_url = getattr(self, '_last_header_epg_url', None)
            if header_epg_url:
                epg_sources = global_subscription_manager.get_epg_sources()
                existing_urls = [src.get('url', '') for src in epg_sources] if epg_sources else []
                if header_epg_url in existing_urls:
                    logger.info(f"M3U文件头EPG已存在于订阅源中，跳过")
                else:
                    logger.info(f"补充加载M3U文件头EPG: {header_epg_url[:80]}")
                    try:
                        header_success = global_subscription_manager.load_single_epg(header_epg_url)
                        if header_success:
                            main_module = sys.modules.get('__main__')
                            if main_module:
                                main_module.EPG_DATA = global_subscription_manager._epg_data
                    except Exception as epg_err:
                        logger.warning(f"补充加载M3U文件头EPG失败: {epg_err}")

        return success

    def _on_subscription_finished(self, result):
        """订阅更新完成回调 - EPG加载完成后刷新EPG列表（在主线程中执行）"""
        logger.debug("EPG数据加载完成，准备刷新EPG列表")

        def refresh_ui():
            try:
                if hasattr(self.window, '_populate_epg_list'):
                    self.window._populate_epg_list()
                    logger.debug("刷新UI: EPG列表已填充")

                if hasattr(self.window, 'status_bar_show_message'):
                    main_module = sys.modules.get('__main__')
                    channels_count = 0
                    if main_module:
                        channels_in_main = getattr(main_module, 'CHANNELS', None)
                        channels_count = len(channels_in_main) if channels_in_main else 0
                    tr = getattr(self.window.language_manager, 'tr', lambda x, y: y) if hasattr(self.window, 'language_manager') else lambda x, y: y
                    self.window.status_bar_show_message(tr("channels_loaded", "Channels loaded: {count}").format(count=channels_count))

            except Exception as e:
                logger.error(f"刷新UI失败: {e}", exc_info=True)

        QTimer.singleShot(0, refresh_ui)

    def update_playlist_subscription(self, source_index=None):
        """更新列表订阅 - 线程安全版本"""
        try:
            global CHANNELS

            sources = global_subscription_manager.get_playlist_sources()

            if not sources:
                logger.warning("没有配置播放列表源")
                return

            target_source = sources[source_index] if source_index is not None else sources[0]
            playlist_url = target_source.get('url', '')

            if playlist_url:
                self.handle_playlist_subscription(True, playlist_url, source_index)

        except Exception as e:
            logger.error(f"更新列表订阅失败: {e}", exc_info=True)

    def update_channel_groups(self):
        """从CHANNELS中提取分组并更新下拉框"""
        if hasattr(self.window, '_update_groups_for'):
            self.window._update_groups_for('subscription')
            self.window._update_groups_for('local')

    def reload_subscription(self):
        """重新加载订阅源"""
        try:
            sources = global_subscription_manager.get_playlist_sources()
            if sources:
                for i, source in enumerate(sources):
                    if source.get('enabled', True):
                        self.update_playlist_subscription(i)

            logger.info("订阅源重新加载完成")
        except Exception as e:
            logger.error(f"重新加载订阅源失败: {e}", exc_info=True)
