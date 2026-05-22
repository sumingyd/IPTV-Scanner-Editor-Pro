import os
import threading
import requests
from datetime import datetime, timedelta
from .log_manager import global_logger as logger
from .config_manager import ConfigManager
from utils.singleton import Singleton


class SubscriptionManager(Singleton):

    def __init__(self):
        if self._initialized:
            return

        self._config = ConfigManager()
        self._epg_data = {}
        self._last_epg_update = None
        self._epg_lock = threading.RLock()
        self._update_callbacks = []
        self._initialized = True

    def _get_cache_dir(self) -> str:
        from models.channel_mappings import get_app_data_dir
        cache_dir = self._config.get_value('General', 'cache_dir', 'cache') or 'cache'
        if not os.path.isabs(cache_dir):
            cache_dir = os.path.join(get_app_data_dir(), cache_dir)
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir, exist_ok=True)
        return cache_dir
    
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

    def get_epg_channel_count(self) -> int:
        """获取EPG数据中的频道数量

        Returns:
            有EPG数据的频道数量
        """
        return len(self._epg_data) if self._epg_data else 0

    def get_epg_program_count(self) -> int:
        """获取EPG数据中的节目总数

        Returns:
            所有频道的节目总数
        """
        if not self._epg_data:
            return 0
        return sum(len(progs) for progs in self._epg_data.values())

    def has_epg_data(self) -> bool:
        """是否有EPG数据

        Returns:
            是否存在任何EPG数据
        """
        return bool(self._epg_data)
    
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
        """加载单个EPG源的数据并合并到现有数据中（用于从M3U文件的tvg-url等场景）

        同一个频道只保留已有数据，新源仅补充不存在的频道。

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
                    new_channels = 0
                    for channel_id, programs in data.items():
                        if channel_id not in self._epg_data:
                            self._epg_data[channel_id] = programs
                            new_channels += 1
                    self._last_epg_update = datetime.now()

                total_channels = len(data)
                total_programs = sum(len(progs) for progs in data.values())

                logger.info(f"EPG补充源加载成功: {total_channels} 个频道, {total_programs} 个节目, 新增 {new_channels} 个频道")

                if status_callback:
                    status_callback(f"EPG数据加载成功: {total_channels} 个频道")

                self._save_epg_cache(self._epg_data)
                if new_channels > 0:
                    self._notify_update_callbacks()

                return True
            else:
                logger.warning("EPG补充源数据为空")
                if status_callback:
                    status_callback("EPG数据为空")
                return False

        except Exception as e:
            logger.error(f"加载EPG补充源失败: {e}")
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

            # requests 在 Content-Encoding: gzip 时已自动解压，
            # 仅对 URL 以 .gz 结尾且内容仍带有 gzip 魔术字节的情况手动解压
            content_encoding = response.headers.get('Content-Encoding', '')
            url_is_gz = epg_url.lower().endswith('.gz')
            already_decompressed = 'gzip' in content_encoding.lower()
            if url_is_gz and not already_decompressed and len(content) >= 2 and content[0] == 0x1f and content[1] == 0x8b:
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


    def _parse_xmltv_time(self, time_str):
        time_str = time_str.strip()
        parts = time_str.split()
        dt_part = parts[0][:14]
        tz_part = parts[1] if len(parts) > 1 else None
        dt = datetime.strptime(dt_part, '%Y%m%d%H%M%S')
        if tz_part:
            sign = 1 if tz_part[0] == '+' else -1
            tz_hours = int(tz_part[1:3])
            tz_minutes = int(tz_part[3:5]) if len(tz_part) >= 5 else 0
            offset = timedelta(hours=tz_hours, minutes=tz_minutes) * sign
            dt_utc = dt - offset
            import time as _time
            local_offset = timedelta(seconds=-_time.timezone)
            if _time.daylight:
                local_offset = timedelta(seconds=-_time.altzone)
            dt = dt_utc + local_offset
        return dt

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
                        start_time = self._parse_xmltv_time(start)

                        if end:
                            end_time = self._parse_xmltv_time(end)
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
            except (ValueError, KeyError):
                continue
        return None
    
    def register_update_callback(self, callback):
        with self._epg_lock:
            if callback not in self._update_callbacks:
                self._update_callbacks.append(callback)
    
    def unregister_update_callback(self, callback):
        with self._epg_lock:
            if callback in self._update_callbacks:
                self._update_callbacks.remove(callback)
    
    def _notify_update_callbacks(self):
        """通知所有注册的更新回调（确保在主线程执行）"""
        with self._epg_lock:
            callbacks = list(self._update_callbacks)
        for callback in callbacks:
            try:
                # 如果当前在子线程，通过 QMetaObject.invokeMethod 调度到主线程
                from PyQt6.QtCore import QThread, QMetaObject, Qt
                from PyQt6.QtWidgets import QApplication
                main_thread = QApplication.instance().thread() if QApplication.instance() else None
                if main_thread and QThread.currentThread() != main_thread:
                    # 使用 Qt.ConnectionType.QueuedConnection 将回调 marshal 到主线程
                    # 由于 callback 可能不是 QObject 方法，用 QTimer.singleShot 代替
                    from PyQt6.QtCore import QTimer
                    # 捕获 callback 避免闭包引用问题
                    QTimer.singleShot(0, callback)
                else:
                    callback()
            except Exception as e:
                logger.error(f"执行EPG更新回调失败: {e}")
    
    def _save_epg_cache(self, data: dict):
        """保存EPG数据到缓存文件

        Args:
            data: EPG数据字典
        """
        import json
        
        cache_dir = self._get_cache_dir()
        
        cache_file = os.path.join(cache_dir, 'epg_cache.json')
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, separators=(',', ':'))
            logger.info(f"EPG数据已保存到缓存: {cache_file}")
        except Exception as e:
            logger.error(f"保存EPG缓存失败: {e}")
    
    def load_cached_epg_data(self) -> bool:
        """从缓存加载EPG数据

        Returns:
            是否成功加载
        """
        import json
        
        cache_dir = self._get_cache_dir()
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
        cache_dir = self._get_cache_dir()
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
