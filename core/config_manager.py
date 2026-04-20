import configparser
import os
import threading
from .log_manager import global_logger as logger
from utils.config_notifier import notify_config_change


class ConfigManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, config_file='config.ini'):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._initialized = False
                    import sys
                    if getattr(sys, 'frozen', False):
                        config_dir = os.path.dirname(sys.executable)
                    else:
                        current_dir = os.path.dirname(os.path.abspath(__file__))
                        config_dir = os.path.dirname(current_dir)
                    instance.config_file = os.path.join(config_dir, config_file)
                    instance.config = configparser.ConfigParser(interpolation=None)
                    instance._lock = threading.Lock()
                    instance.load_config()
                    instance._initialized = True
                    cls._instance = instance
        return cls._instance

    def __init__(self, config_file='config.ini'):
        # 单例模式下，__init__可能会被多次调用，所以什么都不做
        pass

    def save_window_layout(self, x, y, width, height, dividers):
        """保存窗口布局（包括位置和大小）"""
        self.set_value('UI', 'window_x', str(x))
        self.set_value('UI', 'window_y', str(y))
        self.set_value('UI', 'window_width', str(width))
        self.set_value('UI', 'window_height', str(height))
        for i, pos in enumerate(dividers):
            self.set_value('UI', f'divider_{i}', str(pos))
        return self.save_config()  # 确保立即保存到文件

    def load_window_layout(
            self, default_x=100,
            default_y=100,
            default_width=800,
            default_height=600,
            default_dividers=None
            ):
        """加载窗口布局（包括位置和大小）"""
        x = int(self.get_value('UI', 'window_x', default_x) or default_x)
        y = int(self.get_value('UI', 'window_y', default_y) or default_y)
        width = int(self.get_value('UI', 'window_width', default_width) or default_width)
        height = int(self.get_value('UI', 'window_height', default_height) or default_height)
        dividers = []
        i = 0
        while True:
            pos = self.get_value('UI', f'divider_{i}')
            if pos is None:
                break
            dividers.append(int(pos))
            i += 1
        return x, y, width, height, dividers or default_dividers

    def save_network_settings(self, url, timeout, threads, user_agent, referer, enable_retry=None, loop_scan=None):
        """保存网络设置"""
        self.set_value('Network', 'url', url)
        self.set_value('Network', 'timeout', str(timeout))
        self.set_value('Network', 'threads', str(threads))
        self.set_value('Network', 'user_agent', user_agent)
        self.set_value('Network', 'referer', referer)

        # 保存重试设置（如果提供了）
        if enable_retry is not None:
            self.set_value('Network', 'enable_retry', str(enable_retry))
        if loop_scan is not None:
            self.set_value('Network', 'loop_scan', str(loop_scan))

        return self.save_config()  # 确保立即保存到文件

    def load_network_settings(self):
        """加载网络设置"""
        return {
            'url': self.get_value('Network', 'url', ''),
            'timeout': int(self.get_value('Network', 'timeout', '5') or '5'),
            'threads': int(self.get_value('Network', 'threads', '4') or '4'),
            'user_agent': self.get_value('Network', 'user_agent', ''),
            'referer': self.get_value('Network', 'referer', ''),
            'enable_retry': self.get_value('Network', 'enable_retry', 'False').lower() == 'true',
            'loop_scan': self.get_value('Network', 'loop_scan', 'False').lower() == 'true'
        }

    def save_language_settings(self, language_code):
        """保存语言设置"""
        self.set_value('Language', 'current_language', language_code)
        return self.save_config()

    def load_language_settings(self):
        """加载语言设置"""
        return self.get_value('Language', 'current_language', 'zh')

    def save_scan_retry_settings(self, enable_retry, loop_scan):
        """保存扫描重试设置"""
        self.set_value('ScanRetry', 'enable_retry', str(enable_retry))
        self.set_value('ScanRetry', 'loop_scan', str(loop_scan))
        return self.save_config()  # 确保立即保存到文件

    def load_scan_retry_settings(self):
        """加载扫描重试设置"""
        return {
            'enable_retry': self.get_value('ScanRetry', 'enable_retry', 'False').lower() == 'true',
            'loop_scan': self.get_value('ScanRetry', 'loop_scan', 'False').lower() == 'true'
        }

    def save_sort_config(self, sort_config):
        """保存排序配置"""
        # 保存优先级设置
        self.set_value('SortConfig', 'primary_field', sort_config['primary']['field'])
        self.set_value('SortConfig', 'primary_method', sort_config['primary']['method'])
        self.set_value('SortConfig', 'secondary_field', sort_config['secondary']['field'])
        self.set_value('SortConfig', 'secondary_method', sort_config['secondary']['method'])
        self.set_value('SortConfig', 'tertiary_field', sort_config['tertiary']['field'])
        self.set_value('SortConfig', 'tertiary_method', sort_config['tertiary']['method'])

        # 保存分组优先级
        group_priority = sort_config.get('group_priority', [])
        self.set_value('SortConfig', 'group_priority_count', str(len(group_priority)))
        for i, group in enumerate(group_priority):
            self.set_value('SortConfig', f'group_priority_{i}', group)

        return self.save_config()

    def load_sort_config(self):
        """加载排序配置"""
        default_config = {
            'primary': {'field': 'group', 'method': 'custom'},
            'secondary': {'field': 'name', 'method': 'alphabetical'},
            'tertiary': {'field': 'resolution', 'method': 'quality_high_to_low'},
            'group_priority': []
        }

        try:
            config = {
                'primary': {
                    'field': self.get_value('SortConfig', 'primary_field', 'group'),
                    'method': self.get_value('SortConfig', 'primary_method', 'custom')
                },
                'secondary': {
                    'field': self.get_value('SortConfig', 'secondary_field', 'name'),
                    'method': self.get_value('SortConfig', 'secondary_method', 'alphabetical')
                },
                'tertiary': {
                    'field': self.get_value('SortConfig', 'tertiary_field', 'resolution'),
                    'method': self.get_value('SortConfig', 'tertiary_method', 'quality_high_to_low')
                },
                'group_priority': []
            }

            # 加载分组优先级
            group_count = int(self.get_value('SortConfig', 'group_priority_count', '0') or '0')
            for i in range(group_count):
                group = self.get_value('SortConfig', f'group_priority_{i}')
                if group:
                    config['group_priority'].append(group)

            return config
        except Exception as e:
            logger.error(f"加载排序配置失败: {str(e)}")
            return default_config

    def load_config(self):
        if os.path.exists(self.config_file):
            try:
                self.config.read(self.config_file, encoding='utf-8')
                logger.info(f"配置管理-成功加载配置文件: {self.config_file}")
                return True
            except configparser.Error as e:
                logger.error(f"配置管理-解析配置文件失败: {str(e)}", exc_info=True)
                return False
            except IOError as e:
                logger.error(f"配置管理-读取配置文件失败: {str(e)}", exc_info=True)
                return False
            except Exception as e:
                logger.error(f"配置管理-加载配置文件失败: {str(e)}", exc_info=True)
                return False
        logger.warning(f"配置管理-配置文件不存在: {self.config_file}")
        return False

    def save_config(self):
        try:
            # 确保配置目录存在
            config_dir = os.path.dirname(self.config_file)
            if not os.path.exists(config_dir):
                os.makedirs(config_dir)
                logger.info(f"配置管理-创建配置目录: {config_dir}")
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                self.config.write(f)
            logger.info(f"配置管理-成功保存配置文件: {self.config_file}")
            return True
        except IOError as e:
            logger.error(f"配置管理-写入配置文件失败: {str(e)}", exc_info=True)
            return False
        except Exception as e:
            logger.error(f"配置管理-保存配置文件失败: {str(e)}", exc_info=True)
            return False

    def get_value(self, section, key, default=None):
        try:
            return self.config.get(section, key)
        except configparser.NoSectionError:
            logger.debug(f"配置管理- section不存在: {section}")
            return default
        except configparser.NoOptionError:
            logger.debug(f"配置管理- option不存在: {section}.{key}")
            return default
        except Exception as e:
            logger.error(f"配置管理-获取配置值失败: {str(e)}", exc_info=True)
            return default

    def set_value(self, section, key, value):
        try:
            if not self.config.has_section(section):
                self.config.add_section(section)
                logger.debug(f"配置管理-创建section: {section}")

            # 获取旧值
            old_value = self.get_value(section, key)

            # 设置新值
            self.config.set(section, key, value)

            # 通知配置变更
            if old_value != value:
                notify_config_change(section, key, old_value, value)
                logger.debug(f"配置管理-配置变更: {section}.{key} = {old_value} -> {value}")
        except Exception as e:
            logger.error(f"配置管理-设置配置值失败: {str(e)}", exc_info=True)

    def save_ui_settings(self, settings: dict):
        """保存UI相关设置"""
        for key, value in settings.items():
            self.set_value('UI', key, str(value))
        return self.save_config()

    def load_ui_settings(self, defaults: dict | None = None) -> dict:
        """加载 UI 相关设置"""
        defaults = defaults or {}
        settings = {}
        for key, default_value in defaults.items():
            value = self.get_value('UI', key)
            if value is not None:
                # 根据默认值的类型进行转换
                if isinstance(default_value, bool):
                    settings[key] = value.lower() == 'true'
                elif isinstance(default_value, int):
                    settings[key] = int(value)
                elif isinstance(default_value, float):
                    settings[key] = float(value)
                else:
                    settings[key] = value
            else:
                settings[key] = default_value
        return settings

    def save_player_settings(self, volume: int, mute: bool = False):
        """保存播放器设置"""
        self.set_value('Player', 'volume', str(volume))
        self.set_value('Player', 'mute', str(mute))
        return self.save_config()

    def load_player_settings(self) -> dict:
        """加载播放器设置"""
        return {
            'volume': int(self.get_value('Player', 'volume', '50') or '50'),
            'mute': self.get_value('Player', 'mute', 'False').lower() == 'true'
        }

    def save_list_settings(self, auto_save: bool = True, backup_count: int = 3):
        """保存列表相关设置"""
        self.set_value('List', 'auto_save', str(auto_save))
        self.set_value('List', 'backup_count', str(backup_count))
        return self.save_config()

    def load_list_settings(self) -> dict:
        """加载列表相关设置"""
        return {
            'auto_save': self.get_value('List', 'auto_save', 'True').lower() == 'true',
            'backup_count': int(self.get_value('List', 'backup_count', '3') or '3')
        }

    def save_validation_settings(self, auto_validate: bool = False, validate_timeout: int = 10):
        """保存验证相关设置"""
        self.set_value('Validation', 'auto_validate', str(auto_validate))
        self.set_value('Validation', 'validate_timeout', str(validate_timeout))
        return self.save_config()

    def load_validation_settings(self) -> dict:
        """加载验证相关设置"""
        return {
            'auto_validate': self.get_value('Validation', 'auto_validate', 'False').lower() == 'true',
            'validate_timeout': int(self.get_value('Validation', 'validate_timeout', '10') or '10')
        }

    def save_mapping_settings(self, enable_mapping: bool = True):
        """保存映射功能设置"""
        self.set_value('Mapping', 'enable_mapping', str(enable_mapping))
        return self.save_config()

    def load_mapping_settings(self) -> dict:
        """加载映射功能设置"""
        return {
            'enable_mapping': self.get_value('Mapping', 'enable_mapping', 'True').lower() == 'true'
        }
    
    def save_playlist_sources(self, sources: list):
        """保存多个直播源配置

        Args:
            sources: 直播源列表，每个元素为字典格式：
                    {'url': str, 'name': str, 'enabled': bool, 'last_update': str|None}
        """
        self.set_value('PlaylistSources', 'count', str(len(sources)))
        for i, source in enumerate(sources):
            self.set_value('PlaylistSources', f'url_{i}', source.get('url', ''))
            self.set_value('PlaylistSources', f'name_{i}', source.get('name', f'Source {i+1}'))
            self.set_value('PlaylistSources', f'enabled_{i}', str(source.get('enabled', True)))
            self.set_value('PlaylistSources', f'last_update_{i}', source.get('last_update', '') or '')
        self._cleanup_legacy_playlist_keys()
        return self.save_config()
    
    def _cleanup_legacy_playlist_keys(self):
        """清理旧[Playlist]段中已迁移到[PlaylistSources]的遗留键"""
        legacy_keys = ['url', 'name', 'last_update', 'last_url']
        for key in legacy_keys:
            if self.config.has_option('Playlist', key):
                self.config.remove_option('Playlist', key)
                logger.debug(f"配置清理-移除旧键: Playlist.{key}")
        if self.config.has_option('Playlist', 'update_interval'):
            old_val = self.get_value('Playlist', 'update_interval')
            if old_val and not self.config.has_option('PlaylistSources', 'update_interval'):
                self.set_value('PlaylistSources', 'update_interval', old_val)
            self.config.remove_option('Playlist', 'update_interval')
            logger.debug("配置清理-迁移 Playlist.update_interval -> PlaylistSources.update_interval")
        if self.config.has_section('Playlist') and not self.config.options('Playlist'):
            self.config.remove_section('Playlist')
            logger.debug("配置清理-移除空段: [Playlist]")
    
    def load_playlist_sources(self) -> list:
        """加载多个直播源配置

        Returns:
            直播源列表
        """
        sources = []
        count = int(self.get_value('PlaylistSources', 'count', '0') or '0')
        for i in range(count):
            url = self.get_value('PlaylistSources', f'url_{i}')
            if url:
                sources.append({
                    'url': url,
                    'name': self.get_value('PlaylistSources', f'name_{i}', f'Source {i+1}'),
                    'enabled': self.get_value('PlaylistSources', f'enabled_{i}', 'True').lower() == 'true',
                    'last_update': self.get_value('PlaylistSources', f'last_update_{i}', '') or None
                })
        
        if not sources:
            legacy_url = self.get_value('Playlist', 'url', '')
            if legacy_url:
                sources.append({
                    'url': legacy_url,
                    'name': self.get_value('Playlist', 'name', 'Default'),
                    'enabled': True
                })
                self._cleanup_legacy_playlist_keys()
                if sources:
                    self.save_playlist_sources(sources)
        return sources
    
    def get_active_playlist_source(self) -> dict | None:
        """获取当前启用的直播源

        Returns:
            当前启用的直播源字典，如果没有则返回None
        """
        sources = self.load_playlist_sources()
        for source in sources:
            if source.get('enabled'):
                return source
        return sources[0] if sources else None
    
    def set_active_playlist_source(self, index: int):
        """设置指定索引的直播源为启用状态

        Args:
            index: 直播源索引
        """
        sources = self.load_playlist_sources()
        if 0 <= index < len(sources):
            for i, source in enumerate(sources):
                source['enabled'] = (i == index)
            self.save_playlist_sources(sources)
    
    def get_active_playlist_source_index(self) -> int:
        """获取当前启用的直播源索引

        Returns:
            启用源的索引，没有则返回 -1
        """
        sources = self.load_playlist_sources()
        for i, source in enumerate(sources):
            if source.get('enabled'):
                return i
        return 0 if sources else -1
    
    def update_playlist_source_last_update(self, index: int, timestamp: str):
        """更新指定索引直播源的更新时间

        Args:
            index: 源索引
            timestamp: ISO格式时间字符串
        """
        sources = self.load_playlist_sources()
        if 0 <= index < len(sources):
            sources[index]['last_update'] = timestamp
            self.save_playlist_sources(sources)
    
    def save_epg_sources(self, sources: list):
        """保存多个EPG源配置

        Args:
            sources: EPG源列表，每个元素为字典格式：
                    {'url': str, 'name': str}
        """
        self.set_value('EPGSources', 'count', str(len(sources)))
        for i, source in enumerate(sources):
            self.set_value('EPGSources', f'url_{i}', source.get('url', ''))
            self.set_value('EPGSources', f'name_{i}', source.get('name', f'EPG {i+1}'))
        self._cleanup_legacy_epg_keys()
        return self.save_config()
    
    def _cleanup_legacy_epg_keys(self):
        """清理旧[EPG]段中已迁移到[EPGSources]的遗留键"""
        legacy_keys = ['epg_url', 'epg_source', 'last_update', 'last_url']
        for key in legacy_keys:
            if self.config.has_option('EPG', key):
                self.config.remove_option('EPG', key)
                logger.debug(f"配置清理-移除旧键: EPG.{key}")
        if self.config.has_option('EPG', 'update_interval'):
            old_val = self.get_value('EPG', 'update_interval')
            if old_val and not self.config.has_option('EPGSources', 'update_interval'):
                self.set_value('EPGSources', 'update_interval', old_val)
            self.config.remove_option('EPG', 'update_interval')
            logger.debug("配置清理-迁移 EPG.update_interval -> EPGSources.update_interval")
        if self.config.has_section('EPG') and not self.config.options('EPG'):
            self.config.remove_section('EPG')
            logger.debug("配置清理-移除空段: [EPG]")
    
    def load_epg_sources(self) -> list:
        """加载多个EPG源配置

        Returns:
            EPG源列表
        """
        sources = []
        count = int(self.get_value('EPGSources', 'count', '0') or '0')
        for i in range(count):
            url = self.get_value('EPGSources', f'url_{i}')
            if url:
                sources.append({
                    'url': url,
                    'name': self.get_value('EPGSources', f'name_{i}', f'EPG {i+1}')
                })
        
        if not sources:
            legacy_url = self.get_value('EPG', 'epg_url', '')
            if legacy_url:
                sources.append({
                    'url': legacy_url,
                    'name': self.get_value('EPG', 'epg_source', 'Default')
                })
                self._cleanup_legacy_epg_keys()
                if sources:
                    self.save_epg_sources(sources)
        return sources
    
    def save_recent_files(self, recent_files):
        """保存最近打开的文件列表"""
        # 限制最近打开文件的数量为10个
        recent_files = recent_files[:10]
        self.set_value('RecentFiles', 'count', str(len(recent_files)))
        for i, file_path in enumerate(recent_files):
            self.set_value('RecentFiles', f'file_{i}', file_path)
        return self.save_config()
    
    def load_recent_files(self):
        """加载最近打开的文件列表"""
        recent_files = []
        count = int(self.get_value('RecentFiles', 'count', '0') or '0')
        for i in range(count):
            file_path = self.get_value('RecentFiles', f'file_{i}')
            if file_path:
                recent_files.append(file_path)
        return recent_files
    
    def add_recent_file(self, file_path):
        recent_files = self.load_recent_files()
        if file_path in recent_files:
            recent_files.remove(file_path)
        recent_files.insert(0, file_path)
        return self.save_recent_files(recent_files)

    def remove_recent_file(self, file_path):
        recent_files = self.load_recent_files()
        if file_path in recent_files:
            recent_files.remove(file_path)
            self.save_recent_files(recent_files)
            return True
        return False
    
    def save_theme_settings(self, theme_name):
        """保存主题设置"""
        self.set_value('Theme', 'current_theme', theme_name)
        return self.save_config()
    
    def load_theme_settings(self):
        """加载主题设置"""
        return self.get_value('Theme', 'current_theme', 'dark')

    def save_all_settings(self, settings_dict: dict):
        """保存所有设置"""
        for section, section_settings in settings_dict.items():
            for key, value in section_settings.items():
                self.set_value(section, key, str(value))
        return self.save_config()

    def save_playback_settings(self, settings=None):
        defaults = {
            'hwdec': True,
            'cache_secs': 1.0,
            'demuxer_max_bytes_mib': 16,
            'demuxer_max_back_bytes_mib': 4,
            'fcc_prefetch_count': 2,
            'source_timeout_sec': 3,
            'enable_protocol_adaptive': True,
            'hls_start_at_live_edge': False,
            'hls_readahead_secs': 0,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'tls_verify': False,
            'http_headers': '',
            'rtsp_transport': 'tcp',
            'rtsp_user_agent': 'VLC/3.0.18Libmpv',
            'network_timeout_sec': 0,
        }
        if settings:
            defaults.update(settings)
        for key, value in defaults.items():
            if isinstance(value, bool):
                self.set_value('Playback', key, str(value))
            elif isinstance(value, float):
                self.set_value('Playback', key, str(value))
            elif isinstance(value, int):
                self.set_value('Playback', key, str(value))
            else:
                self.set_value('Playback', key, str(value))
        return self.save_config()

    def load_playback_settings(self):
        defaults = {
            'hwdec': True,
            'cache_secs': 1.0,
            'demuxer_max_bytes_mib': 16,
            'demuxer_max_back_bytes_mib': 4,
            'fcc_prefetch_count': 2,
            'source_timeout_sec': 3,
            'enable_protocol_adaptive': True,
            'hls_start_at_live_edge': False,
            'hls_readahead_secs': 0,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'tls_verify': False,
            'http_headers': '',
            'rtsp_transport': 'tcp',
            'rtsp_user_agent': 'VLC/3.0.18Libmpv',
            'network_timeout_sec': 0,
        }
        result = {}
        for key, default in defaults.items():
            raw = self.get_value('Playback', key)
            if raw is None:
                result[key] = default
            elif isinstance(default, bool):
                result[key] = raw.lower() == 'true'
            elif isinstance(default, float):
                try:
                    result[key] = float(raw)
                except (ValueError, TypeError):
                    result[key] = default
            elif isinstance(default, int):
                try:
                    result[key] = int(raw)
                except (ValueError, TypeError):
                    result[key] = default
            else:
                result[key] = raw
        return result

    def save_last_channel(self, file_path, channel_name, channel_index):
        self.set_value('Player', 'last_channel_file', file_path or '')
        self.set_value('Player', 'last_channel_name', channel_name or '')
        self.set_value('Player', 'last_channel_index', str(channel_index if channel_index is not None else -1))
        return self.save_config()

    def load_last_channel(self):
        return {
            'file': self.get_value('Player', 'last_channel_file', ''),
            'name': self.get_value('Player', 'last_channel_name', ''),
            'index': int(self.get_value('Player', 'last_channel_index', '-1') or '-1'),
        }

    def save_timeshift_settings(self, settings):
        for key, value in settings.items():
            self.set_value('Timeshift', key, str(value))
        return self.save_config()

    def load_timeshift_settings(self):
        return {
            'enabled': self.get_value('Timeshift', 'enabled', 'True').lower() == 'true',
            'default_offset_minutes': int(self.get_value('Timeshift', 'default_offset_minutes', '30') or '30'),
            'url_format': self.get_value('Timeshift', 'url_format', ''),
            'time_encoding': self.get_value('Timeshift', 'time_encoding', 'unix'),
            'start_key': self.get_value('Timeshift', 'start_key', 'startTime'),
            'end_key': self.get_value('Timeshift', 'end_key', 'endTime'),
            'layout': self.get_value('Timeshift', 'layout', 'start_end'),
        }

    def save_channel_merge_settings(self, settings):
        for key, value in settings.items():
            self.set_value('ChannelMerge', key, str(value))
        return self.save_config()

    def load_channel_merge_settings(self):
        return {
            'enabled': self.get_value('ChannelMerge', 'enabled', 'True').lower() == 'true',
            'merge_mode': self.get_value('ChannelMerge', 'merge_mode', 'append'),
            'prefer_source': self.get_value('ChannelMerge', 'prefer_source', 'file'),
        }

    def load_all_settings(self) -> dict:
        """加载所有设置"""
        all_settings = {}
        for section in self.config.sections():
            all_settings[section] = {}
            for key in self.config.options(section):
                all_settings[section][key] = self.config.get(section, key)
        return all_settings
