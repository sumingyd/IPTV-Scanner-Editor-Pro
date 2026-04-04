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
    
    def load_epg_from_url(self, epg_url):
        """从URL加载EPG数据"""
        if not epg_url:
            logger.warning("EPG URL未设置")
            return False
        
        # 检查是否已经有当天的EPG数据
        if self.last_update and (datetime.now() - self.last_update).total_seconds() < 86400:
            # 如果EPG数据为空，重新下载
            if len(self.epg_data) == 0:
                logger.warning("EPG数据为空，重新下载")
            else:
                return True
        
        try:
            logger.info(f"开始下载EPG数据: {epg_url}")
            response = requests.get(epg_url, timeout=30)
            response.raise_for_status()
            
            # 解析EPG数据
            self.epg_data = self.parse_epg_data(response.text)
            self.last_update = datetime.now()
            # 保存last_update到配置文件
            from core.config_manager import ConfigManager
            config = ConfigManager()
            config.set_value('EPG', 'last_update', self.last_update.isoformat())
            config.save_config()
            logger.info(f"EPG数据下载成功，包含 {len(self.epg_data)} 个频道")
            return True
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
            logger.warning("EPG数据不是JSON格式，尝试其他解析方式")
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
            for programme in root.iter('programme'):
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
                        # 假设时间格式为 YYYYMMDDHHMMSS timezone，例如 20240404180000 +0800
                        start_time = datetime.strptime(start[:14], '%Y%m%d%H%M%S')
                        
                        # 处理end属性为None的情况
                        if end:
                            end_time = datetime.strptime(end[:14], '%Y%m%d%H%M%S')
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
            
            logger.info(f"XML格式EPG解析成功，包含 {len(result)} 个频道")
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
            # 尝试使用频道名称的一部分匹配
            if channel_name:
                channel_name_lower = channel_name.lower()
                for epg_channel_id, programs in self.epg_data.items():
                    if channel_name_lower in epg_channel_id.lower() or epg_channel_id.lower() in channel_name_lower:
                        return programs
            # 尝试使用频道名称的前几个字符匹配
            if channel_name:
                channel_name_short = channel_name[:8]  # 取前8个字符
                channel_name_short_lower = channel_name_short.lower()
                for epg_channel_id, programs in self.epg_data.items():
                    if channel_name_short_lower in epg_channel_id.lower() or epg_channel_id.lower() in channel_name_short_lower:
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
