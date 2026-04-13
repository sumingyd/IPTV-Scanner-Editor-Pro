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
        """从缓存文件加载 EPG 数据"""
        import os
        from core.config_manager import ConfigManager
        config = ConfigManager()
        cache_dir = config.get_value('General', 'cache_dir', 'cache') or 'cache'
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
        """保存 EPG 数据到缓存文件"""
        import os
        from core.config_manager import ConfigManager
        config = ConfigManager()
        cache_dir = config.get_value('General', 'cache_dir', 'cache') or 'cache'
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
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': '*/*'
            }

            logger.info(f"正在下载 EPG 数据: {epg_url}")
            response = requests.get(epg_url, timeout=30, headers=headers, allow_redirects=True)
            response.raise_for_status()

            logger.info(f"EPG 数据下载成功: Content-Length={len(response.content)}")

            # 检查是否是.gz压缩文件
            content = response.content
            is_gz_file = epg_url.endswith('.gz') or response.headers.get('Content-Encoding') == 'gzip'

            if is_gz_file:
                # 验证是否真的是 gzip 文件（检查 magic bytes: 0x1f 0x8b）
                is_really_gzip = len(content) >= 2 and content[0] == 0x1f and content[1] == 0x8b

                if is_really_gzip:
                    logger.info("检测到.gz压缩文件，正在解压...")
                    import gzip
                    from io import BytesIO
                    try:
                        with gzip.GzipFile(fileobj=BytesIO(content)) as f:
                            content = f.read()
                    except Exception as e:
                        logger.error(f"解压.gz文件失败: {e}")
                        return False
                else:
                    # Content-Encoding 说 gzip 但实际不是（可能是服务器自动压缩的 XML）
                    logger.info("响应头标记为 gzip 但实际内容非 gzip 格式，跳过解压")

            # 验证数据新鲜度：检查是否包含今天或昨天的节目
            today_str = datetime.now().strftime('%Y%m%d')
            yesterday_str = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')

            # 在内容中搜索今天的日期
            has_today = today_str in content.decode('utf-8', errors='ignore')
            has_yesterday = yesterday_str in content.decode('utf-8', errors='ignore')

            if not has_today and not has_yesterday:
                logger.warning(f"EPG数据可能已过期！不包含今天({today_str})或昨天({yesterday_str})的节目")
            
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
        with self.update_lock:
            if tvg_id:
                if tvg_id in self.epg_data:
                    return self.epg_data[tvg_id]
                tvg_id_lower = tvg_id.lower()
                for epg_channel_id, programs in self.epg_data.items():
                    if epg_channel_id.lower() == tvg_id_lower:
                        return programs

            if channel_name:
                if channel_name in self.epg_data:
                    return self.epg_data[channel_name]

            try:
                from services.epg_matcher import EpgMatcher
                epg_channels = {epg_id: epg_id for epg_id in self.epg_data.keys()}
                matched_id = EpgMatcher.match(channel_name, epg_channels, tvg_id=tvg_id)
                if matched_id and matched_id in self.epg_data:
                    return self.epg_data[matched_id]
            except Exception as ex:
                logger.warning(f"EpgMatcher 匹配异常: {ex}")

            if channel_name:
                channel_name_lower = channel_name.lower()
                for epg_channel_id, programs in self.epg_data.items():
                    epg_lower = epg_channel_id.lower()
                    if len(channel_name_lower) >= 3 and (channel_name_lower in epg_lower or epg_lower in channel_name_lower):
                        if len(channel_name_lower) >= len(epg_lower) * 0.6 or len(epg_lower) >= len(channel_name_lower) * 0.6:
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
