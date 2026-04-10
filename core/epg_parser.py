import os
import sys
import json
import threading
import requests
from datetime import datetime, timedelta
from .log_manager import global_logger as logger

class EPGParser:
    """EPG节目单解析器"""
    
    def __init__(self):
        self.epg_data = {}
        self.last_update = None
        self.update_lock = threading.Lock()
        # 从配置文件加载last_update
        from core.config_manager import ConfigManager
        config = ConfigManager()
        last_update_str = config.get_value('EPG', 'last_update', None)
        if last_update_str:
            try:
                from datetime import datetime
                self.last_update = datetime.fromisoformat(last_update_str)
            except Exception:
                pass
    
    def load_cached_epg_data(self):
        """从缓存文件加载EPG数据"""
        import os
        from core.config_manager import ConfigManager
        config = ConfigManager()
        cache_dir = config.get_value('General', 'cache_dir', 'cache')
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
        
        epg_cache_file = os.path.join(cache_dir, 'epg_cache.json')
        if os.path.exists(epg_cache_file):
            try:
                import json
                with open(epg_cache_file, 'r', encoding='utf-8') as f:
                    self.epg_data = json.load(f)
            except Exception as e:
                logger.error(f"加载EPG缓存数据失败: {e}")
                self.epg_data = {}
    
    def save_cached_epg_data(self):
        """保存EPG数据到缓存文件"""
        import os
        from core.config_manager import ConfigManager
        config = ConfigManager()
        cache_dir = config.get_value('General', 'cache_dir', 'cache')
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
        
        epg_cache_file = os.path.join(cache_dir, 'epg_cache.json')
        try:
            import json
            with open(epg_cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.epg_data, f, ensure_ascii=False, indent=2)
            logger.info(f"EPG数据已保存到缓存文件: {epg_cache_file}")
        except Exception as e:
            logger.error(f"保存EPG缓存数据失败: {e}")
    
    def load_epg_from_url(self, epg_url, status_callback=None):
        """从URL加载EPG数据"""
        if not epg_url:
            logger.warning("EPG URL未设置")
            if status_callback:
                status_callback("EPG URL未设置")
            return False
        
        # 检查是否已经有当天的EPG数据
        if self.last_update and (datetime.now() - self.last_update).total_seconds() < 86400:
            # 如果EPG数据为空，重新下载
            if len(self.epg_data) == 0:
                logger.warning("EPG数据为空，重新下载")
                if status_callback:
                    status_callback("EPG数据为空，重新下载")
            else:
                if status_callback:
                    status_callback("使用缓存的EPG数据")
                return True
        
        if status_callback:
            status_callback("正在下载EPG数据...")
        
        try:
            response = requests.get(epg_url, timeout=30)
            response.raise_for_status()
            
            # 检查是否是.gz压缩文件
            content = response.content
            if epg_url.endswith('.gz') or response.headers.get('Content-Encoding') == 'gzip':
                logger.info("检测到.gz压缩文件，正在解压...")
                import gzip
                from io import BytesIO
                try:
                    with gzip.GzipFile(fileobj=BytesIO(content)) as f:
                        content = f.read()
                except Exception as e:
                    logger.error(f"解压.gz文件失败: {e}")
                    return False
            
            # 转换为文本
            try:
                epg_content = content.decode('utf-8')
            except UnicodeDecodeError:
                try:
                    epg_content = content.decode('gbk')
                except UnicodeDecodeError:
                    logger.error("无法解码EPG文件内容")
                    return False
            
            content_length = len(epg_content)
            if content_length == 0:
                logger.error("EPG数据为空")
                if status_callback:
                    status_callback("EPG数据为空")
                return False
            
            if status_callback:
                status_callback("正在解析EPG数据...")
            
            self.epg_data = self.parse_epg_data(epg_content)
            self.last_update = datetime.now()
            # 保存last_update到配置文件
            from core.config_manager import ConfigManager
            config = ConfigManager()
            config.set_value('EPG', 'last_update', self.last_update.isoformat())
            config.save_config()
            
            # 保存EPG数据到缓存文件
            self.save_cached_epg_data()
            
            if status_callback:
                status_callback(f"EPG数据下载成功，包含 {len(self.epg_data)} 个频道")
            
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"EPG数据下载失败: {e}")
            return False
        except Exception as e:
            logger.error(f"加载EPG数据失败: {e}")
            return False
    
    def parse_epg_data(self, epg_content):
        """解析EPG数据"""
        # 这里需要根据实际的EPG格式进行解析
        # 假设EPG数据是JSON格式，结构为 {"channel_name": [{"title": "节目名称", "start": "开始时间", "end": "结束时间", "desc": "节目描述"}]}
        try:
            return json.loads(epg_content)
        except json.JSONDecodeError:
            # 如果不是JSON格式，尝试解析其他格式
            return self.parse_epg_xml(epg_content)
    
    def parse_epg_xml(self, epg_content):
        """解析XML格式的EPG数据"""
        # 实现XML格式的EPG解析
        result = {}
        try:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(epg_content)
            
            # 解析频道和节目信息
            channels = root.findall('.//channel')
            
            # 如果有channel元素，解析它们
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
            
            # 解析节目信息
            # 使用更通用的查找方式，查找所有的programme元素
            programmes = list(root.iter('programme'))
            
            for programme in programmes:
                channel_id = programme.get('channel')
                start = programme.get('start')
                # 同时支持end和stop属性
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
                    # 转换时间格式
                    try:
                        # 清理时间字符串，只保留数字部分
                        def clean_time_str(time_str):
                            return ''.join(c for c in time_str if c.isdigit())[:14]
                        
                        start_clean = clean_time_str(start)
                        start_time = datetime.strptime(start_clean, '%Y%m%d%H%M%S')
                        
                        # 处理end属性为None的情况
                        if end:
                            end_clean = clean_time_str(end)
                            end_time = datetime.strptime(end_clean, '%Y%m%d%H%M%S')
                        else:
                            # 如果end为None，假设节目持续30分钟
                            end_time = start_time + timedelta(minutes=30)
                        
                        # 如果没有channel元素或者channel_id不在result中，创建一个新的entry
                        if channel_id not in result:
                            result[channel_id] = []
                        
                        # 添加节目信息
                        result[channel_id].append({
                            'title': title,
                            'desc': desc or '',
                            'start': start_time.isoformat(),
                            'end': end_time.isoformat()
                        })
                    except Exception as e:
                        logger.error(f"解析节目时间失败: {e}")
                        pass
            
            return result
        except Exception as e:
            logger.error(f"XML格式EPG解析失败: {e}")
            return {}
    
    def get_channel_epg(self, channel_name, tvg_id=None):
        """获取指定频道的节目单"""
        with self.update_lock:
            # 首先尝试使用tvg-id匹配
            if tvg_id:
                # 直接使用tvg_id匹配
                if tvg_id in self.epg_data:
                    return self.epg_data[tvg_id]
                # 尝试使用tvg_id的小写形式匹配
                tvg_id_lower = tvg_id.lower()
                for epg_channel_id, programs in self.epg_data.items():
                    if epg_channel_id.lower() == tvg_id_lower:
                        return programs
            # 然后尝试使用频道名称匹配
            if channel_name:
                # 直接使用频道名称匹配
                if channel_name in self.epg_data:
                    return self.epg_data[channel_name]
                # 尝试使用频道名称的小写形式匹配
                channel_name_lower = channel_name.lower()
                for epg_channel_id, programs in self.epg_data.items():
                    if epg_channel_id.lower() == channel_name_lower:
                        return programs
            if channel_name:
                channel_name_lower = channel_name.lower()
                for epg_channel_id, programs in self.epg_data.items():
                    epg_lower = epg_channel_id.lower()
                    if len(channel_name_lower) >= 3 and (channel_name_lower in epg_lower or epg_lower in channel_name_lower):
                        if len(channel_name_lower) >= len(epg_lower) * 0.6 or len(epg_lower) >= len(channel_name_lower) * 0.6:
                            return programs
            if channel_name:
                channel_name_short = channel_name[:8]
                channel_name_short_lower = channel_name_short.lower()
                if len(channel_name_short_lower) >= 3:
                    for epg_channel_id, programs in self.epg_data.items():
                        epg_lower = epg_channel_id.lower()
                        if channel_name_short_lower in epg_lower or epg_lower in channel_name_short_lower:
                            if len(channel_name_short_lower) >= len(epg_lower) * 0.6 or len(epg_lower) >= len(channel_name_short_lower) * 0.6:
                                return programs
            if channel_name:
                import re
                numbers = re.findall(r'\d+', channel_name)
                if numbers:
                    longest_number = max(numbers, key=len)
                    if len(longest_number) >= 2:
                        for epg_channel_id, programs in self.epg_data.items():
                            if longest_number in epg_channel_id and channel_name[:2].lower() in epg_channel_id.lower():
                                return programs
            if channel_name:
                import re
                simplified_name = re.sub(r'[^a-zA-Z0-9]', '', channel_name).lower()
                if len(simplified_name) >= 3:
                    for epg_channel_id, programs in self.epg_data.items():
                        simplified_epg_channel = re.sub(r'[^a-zA-Z0-9]', '', epg_channel_id).lower()
                        if simplified_name == simplified_epg_channel:
                            return programs
            return []
    
    def get_current_program(self, channel_name, tvg_id=None):
        """获取当前正在播放的节目"""
        epg_list = self.get_channel_epg(channel_name, tvg_id)
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
    
    def get_next_program(self, channel_name, tvg_id=None):
        """获取下一个节目"""
        epg_list = self.get_channel_epg(channel_name, tvg_id)
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
    
    def refresh_epg(self, epg_url):
        """刷新EPG数据"""
        return self.load_epg_from_url(epg_url)
    
    def is_epg_valid(self):
        """检查EPG数据是否有效"""
        if not self.epg_data:
            return False
        
        # 检查EPG数据是否过期（超过24小时）
        if self.last_update and (datetime.now() - self.last_update).total_seconds() > 86400:
            return False
        
        return True

# 全局EPG解析器实例
global_epg_parser = EPGParser()
