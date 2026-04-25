import threading
import requests
from datetime import datetime, timedelta
from .log_manager import global_logger as logger
from .config_manager import ConfigManager


class SubscriptionManager:
    """多源订阅管理器 - 负责管理多个直播源和EPG源的加载、切换和整合"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._initialized = False
                    cls._instance = instance
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._config = ConfigManager()
        self._epg_data = {}
        self._last_epg_update = None
        self._epg_lock = threading.RLock()
        self._update_callbacks = []
        self._initialized = True
    
    def get_playlist_sources(self) -> list:
        """获取所有直播源配置

        Returns:
            直播源列表
        """
        return self._config.load_playlist_sources()
    
    def add_playlist_source(self, url: str, name: str | None = None) -> int:
        """添加新的直播源

        Args:
            url: 直播源URL
            name: 直播源名称（可选）

        Returns:
            新添加的源索引
        """
        sources = self.get_playlist_sources()
        
        if not name:
            name = f"Source {len(sources) + 1}"
        
        new_source = {
            'url': url,
            'name': name,
            'enabled': len(sources) == 0
        }
        
        sources.append(new_source)
        self._config.save_playlist_sources(sources)
        
        logger.info(f"已添加直播源: {name} ({url})")
        return len(sources) - 1
    
    def remove_playlist_source(self, index: int):
        """删除指定索引的直播源

        Args:
            index: 要删除的源索引
        """
        sources = self.get_playlist_sources()
        if 0 <= index < len(sources):
            removed = sources.pop(index)
            
            was_enabled = removed.get('enabled', False)
            if was_enabled and sources:
                sources[0]['enabled'] = True
            
            self._config.save_playlist_sources(sources)
            logger.info(f"已删除直播源: {removed.get('name', 'Unknown')}")
    
    def update_playlist_source(self, index: int, url: str, name: str | None = None):
        """更新指定索引的直播源

        Args:
            index: 要更新的源索引
            url: 新的URL
            name: 新的名称（可选，不传则保留原名）
        """
        sources = self.get_playlist_sources()
        if 0 <= index < len(sources):
            source = sources[index]
            source['url'] = url
            if name:
                source['name'] = name
            self._config.save_playlist_sources(sources)
            logger.info(f"已更新直播源: {source.get('name', 'Unknown')} ({url})")
    
    def update_playlist_source_last_update(self, index: int, timestamp: str):
        """更新指定索引的直播源更新时间

        Args:
            index: 源索引
            timestamp: ISO格式时间字符串
        """
        self._config.update_playlist_source_last_update(index, timestamp)
    
    def set_active_playlist_source(self, index: int):
        """设置指定索引的直播源为当前启用状态

        Args:
            index: 源索引
        """
        self._config.set_active_playlist_source(index)
        source = self.get_active_playlist_source()
        if source:
            logger.info(f"已切换到直播源: {source.get('name', 'Unknown')} ({source.get('url', '')})")
    
    def get_active_playlist_source_index(self) -> int:
        """获取当前启用的直播源索引

        Returns:
            启用源的索引，没有则返回 -1
        """
        return self._config.get_active_playlist_source_index()
    
    def get_active_playlist_source(self) -> dict | None:
        """获取当前启用的直播源

        Returns:
            当前启用的直播源字典，如果没有则返回None
        """
        return self._config.get_active_playlist_source()
    
    def get_epg_sources(self) -> list:
        """获取所有EPG源配置

        Returns:
            EPG源列表
        """
        return self._config.load_epg_sources()
    
    def add_epg_source(self, url: str, name: str | None = None) -> int:
        """添加新的EPG源

        Args:
            url: EPG源URL
            name: EPG源名称（可选）

        Returns:
            新添加的源索引
        """
        sources = self.get_epg_sources()
        
        if not name:
            name = f"EPG {len(sources) + 1}"
        
        new_source = {
            'url': url,
            'name': name
        }
        
        sources.append(new_source)
        self._config.save_epg_sources(sources)
        
        logger.info(f"已添加EPG源: {name} ({url})")
        return len(sources) - 1
    
    def remove_epg_source(self, index: int):
        """删除指定索引的EPG源

        Args:
            index: 要删除的源索引
        """
        sources = self.get_epg_sources()
        if 0 <= index < len(sources):
            removed = sources.pop(index)
            self._config.save_epg_sources(sources)
            logger.info(f"已删除EPG源: {removed.get('name', 'Unknown')}")
    
    def update_epg_source(self, index: int, url: str, name: str | None = None):
        """更新指定索引的EPG源

        Args:
            index: 要更新的源索引
            url: 新的URL
            name: 新的名称（可选，不传则保留原名）
        """
        sources = self.get_epg_sources()
        if 0 <= index < len(sources):
            source = sources[index]
            source['url'] = url
            if name:
                source['name'] = name
            self._config.save_epg_sources(sources)
            logger.info(f"已更新EPG源: {source.get('name', 'Unknown')} ({url})")

    def update_epg_source_last_update(self, index: int, timestamp: str):
        """更新指定索引EPG源的更新时间

        Args:
            index: 源索引
            timestamp: ISO格式时间字符串
        """
        self._config.update_epg_source_last_update(index, timestamp)
    
    def load_all_epg_data(self, status_callback=None) -> bool:
        """加载所有EPG源的数据，多源依次替补

        同一个频道只使用第一个有该频道数据的EPG源，不合并多个源的数据。
        """
        sources = self.get_epg_sources()
        
        if not sources:
            logger.warning("没有配置任何EPG源")
            if status_callback:
                status_callback("没有配置任何EPG源")
            return False
        
        merged_data = {}
        total_sources = len(sources)

        for i, source in enumerate(sources):
            if status_callback:
                status_callback(f"正在加载EPG源 {i+1}/{total_sources}: {source.get('name', '')}")

            try:
                data = self._load_single_epg(source['url'])

                if data:
                    new_channels = 0
                    for channel_id, programs in data.items():
                        if channel_id not in merged_data:
                            merged_data[channel_id] = programs
                            new_channels += 1

                    logger.info(f"成功加载EPG源: {source.get('name', '')}, 包含 {len(data)} 个频道, 新增 {new_channels} 个频道")
                    self.update_epg_source_last_update(i, datetime.now().isoformat())
                else:
                    logger.warning(f"EPG源加载失败或无数据: {source.get('name', '')}")

            except Exception as e:
                logger.error(f"加载EPG源异常: {source.get('name', '')} - {str(e)}")
        
        with self._epg_lock:
            self._epg_data = merged_data
            self._last_epg_update = datetime.now()
        
        total_channels = len(merged_data)
        total_programs = sum(len(progs) for progs in merged_data.values())
        
        logger.info(f"EPG数据加载完成: 共 {total_sources} 个源, {total_channels} 个频道, {total_programs} 个节目")
        
        if status_callback:
            status_callback(f"EPG数据加载完成: {total_channels} 个频道, {total_programs} 个节目")
        
        self._save_epg_cache(merged_data)
        self._notify_update_callbacks()
        
        return len(merged_data) > 0
    
    def reload_single_epg_source(self, index: int, status_callback=None) -> bool:
        """增量重载单个EPG源，依次替补

        Args:
            index: 要重载的源索引
            status_callback: 状态回调函数

        Returns:
            是否成功
        """
        sources = self.get_epg_sources()
        if not (0 <= index < len(sources)):
            if status_callback:
                status_callback("无效的EPG源索引")
            return False
        
        source = sources[index]
        
        if status_callback:
            status_callback(f"正在更新EPG源: {source.get('name', '')}")

        try:
            data = self._load_single_epg(source['url'])
            
            if not data:
                logger.warning(f"EPG源增量加载失败或无数据: {source.get('name', '')}")
                if status_callback:
                    status_callback(f"EPG源加载失败: {source.get('name', '')}")
                return False
            
            with self._epg_lock:
                new_channels = 0
                for channel_id, programs in data.items():
                    if channel_id not in self._epg_data:
                        self._epg_data[channel_id] = programs
                        new_channels += 1
                
                self._last_epg_update = datetime.now()
            
            total_channels = len(self._epg_data)
            total_programs = sum(len(progs) for progs in self._epg_data.values())
            
            logger.info(f"EPG源增量更新成功: {source.get('name', '')}, 包含 {len(data)} 个频道, 新增 {new_channels} 个频道, 合计 {total_channels} 个频道, {total_programs} 个节目")
            self.update_epg_source_last_update(index, datetime.now().isoformat())
            
            if status_callback:
                status_callback(f"EPG源更新完成: {total_channels} 个频道, {total_programs} 个节目")
            
            self._save_epg_cache(self._epg_data)
            self._notify_update_callbacks()
            
            return True
            
        except Exception as e:
            logger.error(f"EPG源增量重载异常: {source.get('name', '')} - {str(e)}")
            return False
    
    def load_single_epg(self, epg_url: str, status_callback=None) -> bool:
        """加载单个EPG源的数据（用于从M3U文件的tvg-url等场景）

        Args:
            epg_url: EPG源URL
            status_callback: 状态回调函数

        Returns:
            是否成功加载
        """
        if not epg_url:
            logger.warning("EPG URL未设置")
            if status_callback:
                status_callback("EPG URL未设置")
            return False
        
        if status_callback:
            status_callback("正在下载EPG数据...")
        
        try:
            data = self._load_single_epg(epg_url)
            
            if data:
                with self._epg_lock:
                    self._epg_data = data
                    self._last_epg_update = datetime.now()
                
                total_channels = len(data)
                total_programs = sum(len(progs) for progs in data.values())
                
                logger.info(f"单源EPG数据加载成功: {total_channels} 个频道, {total_programs} 个节目")
                
                if status_callback:
                    status_callback(f"EPG数据加载成功: {total_channels} 个频道")
                
                self._save_epg_cache(data)
                self._notify_update_callbacks()
                
                return True
            else:
                logger.warning("单源EPG数据为空")
                if status_callback:
                    status_callback("EPG数据为空")
                return False
                
        except Exception as e:
            logger.error(f"加载单源EPG数据失败: {e}")
            if status_callback:
                status_callback(f"加载失败: {e}")
            return False
    
    def _load_single_epg(self, epg_url: str) -> dict:
        """加载单个EPG源的数据

        Args:
            epg_url: EPG源URL

        Returns:
            EPG数据字典
        """
        if not epg_url:
            return {}
        
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': '*/*'
            }
            
            logger.info(f"正在下载EPG数据: {epg_url}")
            response = requests.get(epg_url, timeout=30, headers=headers, allow_redirects=True)
            response.raise_for_status()
            
            content = response.content
            
            is_gz_file = epg_url.endswith('.gz') or response.headers.get('Content-Encoding') == 'gzip'
            if is_gz_file and len(content) >= 2 and content[0] == 0x1f and content[1] == 0x8b:
                import gzip
                from io import BytesIO
                with gzip.GzipFile(fileobj=BytesIO(content)) as f:
                    content = f.read()
            
            try:
                epg_content = content.decode('utf-8')
            except UnicodeDecodeError:
                try:
                    epg_content = content.decode('gbk')
                except UnicodeDecodeError:
                    logger.error("无法解码EPG文件内容")
                    return {}
            
            if not epg_content.strip():
                return {}
            
            return self._parse_epg_content(epg_content)
        
        except requests.exceptions.RequestException as e:
            logger.error(f"EPG数据下载失败: {e}")
            return {}
        except Exception as e:
            logger.error(f"加载EPG数据失败: {e}")
            return {}
    
    def _parse_epg_content(self, content: str) -> dict:
        """解析EPG内容

        Args:
            content: EPG内容字符串

        Returns:
            解析后的EPG数据字典
        """
        try:
            import json
            return json.loads(content)
        except json.JSONDecodeError:
            pass
        
        return self._parse_xml_epg(content)
    
    def _parse_xml_epg(self, content: str) -> dict:
        """解析XML格式的EPG数据

        Args:
            content: XML格式的EPG内容

        Returns:
            解析后的EPG数据字典
        """
        result = {}
        try:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(content)
            
            channels = root.findall('.//channel')
            if channels:
                for channel in channels:
                    channel_id = channel.get('id')
                    channel_name = None
                    for display_name in channel.findall('display-name'):
                        if display_name.text:
                            channel_name = display_name.text
                            break
                    if channel_id and channel_name:
                        result[channel_id] = []
            
            programmes = list(root.iter('programme'))
            
            for programme in programmes:
                channel_id = programme.get('channel')
                start = programme.get('start')
                end = programme.get('stop') or programme.get('end')
                title = None
                desc = None
                
                for title_elem in programme.findall('title'):
                    if title_elem.text:
                        title = title_elem.text
                        break
                
                for desc_elem in programme.findall('desc'):
                    if desc_elem.text:
                        desc = desc_elem.text
                        break
                
                if channel_id and start and title:
                    try:
                        def clean_time_str(time_str):
                            return ''.join(c for c in time_str if c.isdigit())[:14]
                        
                        start_clean = clean_time_str(start)
                        start_time = datetime.strptime(start_clean, '%Y%m%d%H%M%S')
                        
                        if end:
                            end_clean = clean_time_str(end)
                            end_time = datetime.strptime(end_clean, '%Y%m%d%H%M%S')
                        else:
                            end_time = start_time + timedelta(minutes=30)
                        
                        if channel_id not in result:
                            result[channel_id] = []
                        
                        result[channel_id].append({
                            'title': title,
                            'desc': desc or '',
                            'start': start_time.isoformat(),
                            'end': end_time.isoformat()
                        })
                    except Exception as e:
                        logger.debug(f"解析节目时间失败: {e}")
                        pass
            
            return result
        except Exception as e:
            logger.error(f"XML格式EPG解析失败: {e}")
            return {}
    
    def get_channel_epg(self, channel_name: str, tvg_id: str | None = None,
                        tvg_name: str | None = None, comma_name: str | None = None) -> list:
        """获取频道的EPG节目列表（仅精确匹配）

        匹配优先级：
        1. tvg-name 精确匹配
        2. tvg-id 精确匹配
        3. m3u标签行逗号后的频道名字精确匹配
        4. channel_name 精确匹配

        Args:
            channel_name: 频道名称
            tvg_id: TVG-ID（可选）
            tvg_name: TVG-NAME（可选）
            comma_name: m3u标签行逗号后的频道名字（可选）

        Returns:
            节目列表
        """
        with self._epg_lock:
            # 优先级1: tvg-name 精确匹配
            if tvg_name:
                if tvg_name in self._epg_data:
                    return self._epg_data[tvg_name]

            # 优先级2: tvg-id 精确匹配
            if tvg_id:
                if tvg_id in self._epg_data:
                    return self._epg_data[tvg_id]

            # 优先级3: comma_name 精确匹配
            if comma_name:
                if comma_name in self._epg_data:
                    return self._epg_data[comma_name]

            # 优先级4: channel_name 精确匹配
            if channel_name:
                if channel_name in self._epg_data:
                    return self._epg_data[channel_name]

            # 通过 EpgMatcher 进行精确匹配（匹配 epg_display_name）
            try:
                from services.epg_matcher import EpgMatcher
                epg_channels = {epg_id: epg_id for epg_id in self._epg_data.keys()}
                matched_id = EpgMatcher.match(
                    channel_name, epg_channels,
                    tvg_id=tvg_id, tvg_name=tvg_name, comma_name=comma_name
                )
                if matched_id and matched_id in self._epg_data:
                    return self._epg_data[matched_id]
            except Exception as ex:
                logger.warning(f"EpgMatcher 匹配异常: {ex}")

            return []
    
    def get_current_program(self, channel_name: str, tvg_id: str | None = None,
                            tvg_name: str | None = None, comma_name: str | None = None) -> dict | None:
        """获取当前正在播放的节目"""
        epg_list = self.get_channel_epg(channel_name, tvg_id, tvg_name=tvg_name, comma_name=comma_name)
        if not epg_list:
            return None
        
        now = datetime.now()
        for program in epg_list:
            try:
                start_time = datetime.fromisoformat(program.get('start', ''))
                end_time = datetime.fromisoformat(program.get('end', ''))
                if start_time <= now <= end_time:
                    return program
            except Exception:
                continue
        return None
    
    def get_next_program(self, channel_name: str, tvg_id: str | None = None,
                         tvg_name: str | None = None, comma_name: str | None = None) -> dict | None:
        """获取下一个节目"""
        epg_list = self.get_channel_epg(channel_name, tvg_id, tvg_name=tvg_name, comma_name=comma_name)
        if not epg_list:
            return None
        
        now = datetime.now()
        for program in epg_list:
            try:
                start_time = datetime.fromisoformat(program.get('start', ''))
                if start_time > now:
                    return program
            except:
                continue
        return None
    
    def register_update_callback(self, callback):
        """注册EPG更新回调函数

        Args:
            callback: 回调函数
        """
        if callback not in self._update_callbacks:
            self._update_callbacks.append(callback)
    
    def unregister_update_callback(self, callback):
        """注销EPG更新回调函数

        Args:
            callback: 回调函数
        """
        if callback in self._update_callbacks:
            self._update_callbacks.remove(callback)
    
    def _notify_update_callbacks(self):
        """通知所有注册的更新回调"""
        for callback in self._update_callbacks:
            try:
                callback()
            except Exception as e:
                logger.error(f"执行EPG更新回调失败: {e}")
    
    def _save_epg_cache(self, data: dict):
        """保存EPG数据到缓存文件

        Args:
            data: EPG数据字典
        """
        import os
        import json
        
        cache_dir = self._config.get_value('General', 'cache_dir', 'cache') or 'cache'
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
        
        cache_file = os.path.join(cache_dir, 'epg_cache.json')
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"EPG数据已保存到缓存: {cache_file}")
        except Exception as e:
            logger.error(f"保存EPG缓存失败: {e}")
    
    def load_cached_epg_data(self) -> bool:
        """从缓存加载EPG数据

        Returns:
            是否成功加载
        """
        import os
        import json
        
        cache_dir = self._config.get_value('General', 'cache_dir', 'cache') or 'cache'
        cache_file = os.path.join(cache_dir, 'epg_cache.json')
        
        if not os.path.exists(cache_file):
            return False
        
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            with self._epg_lock:
                self._epg_data = data
                self._last_epg_update = datetime.now()
            
            logger.debug(f"从缓存加载EPG数据成功: {len(data)} 个频道")
            return True
        except Exception as e:
            logger.error(f"加载EPG缓存失败: {e}")
            return False
    
    def is_epg_valid(self) -> bool:
        """检查EPG缓存数据是否有效（基于缓存文件修改时间和配置的更新间隔）

        Returns:
            是否有效
        """
        import os

        cache_dir = self._config.get_value('General', 'cache_dir', 'cache') or 'cache'
        cache_file = os.path.join(cache_dir, 'epg_cache.json')

        if not os.path.exists(cache_file):
            return False

        try:
            file_mtime = datetime.fromtimestamp(os.path.getmtime(cache_file))
            age_seconds = (datetime.now() - file_mtime).total_seconds()

            update_interval = int(self._config.get_value('EPGSources', 'update_interval', '60') or 60)
            max_age_seconds = update_interval * 60

            if age_seconds > max_age_seconds:
                logger.debug(f"EPG缓存文件已过期: {age_seconds/60:.0f} 分钟前 (配置间隔: {update_interval} 分钟)")
                return False

            return True
        except Exception as e:
            logger.debug(f"检查EPG缓存有效性失败: {e}")
            return False
    
    def refresh_epg(self, status_callback=None) -> bool:
        """刷新所有EPG数据

        Args:
            status_callback: 状态回调函数

        Returns:
            是否成功刷新
        """
        return self.load_all_epg_data(status_callback)


global_subscription_manager = SubscriptionManager()
