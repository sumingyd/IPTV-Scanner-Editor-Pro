import os
import requests
import xml.etree.ElementTree as ET
from typing import List, Dict, Optional
from dataclasses import asdict
from epg_model import EPGConfig, EPGChannel, EPGProgram
from config_manager import ConfigManager
from log_manager import LogManager
logger = LogManager()

class EPGManager:
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self.epg_config = self.config_manager.load_epg_config()
        self.epg_data: Dict[str, EPGChannel] = {}  # channel_id -> EPGChannel
        self.loaded = False

    def download_epg(self, force_update=False) -> bool:
        """下载EPG XML文件"""
        if not self.epg_config:
            logger.error("EPG配置未加载")
            return False

        local_file = self.epg_config.local_file
        if os.path.exists(local_file) and not force_update:
            logger.info(f"使用本地EPG文件: {local_file}")
            return True

        try:
            # 如果是合并模式，下载并合并所有源
            if self.epg_config.merge_sources:
                merged_data = None
                for source in self.epg_config.sources:
                    response = requests.get(source.url, timeout=30)
                    if response.status_code == 200:
                        if merged_data is None:
                            merged_data = response.text
                        else:
                            # 简单合并XML内容（实际实现需要更复杂的合并逻辑）
                            merged_data += "\n" + response.text
                
                if merged_data:
                    with open(local_file, 'w', encoding='utf-8') as f:
                        f.write(merged_data)
                    return True
            else:
                # 只下载主EPG源
                primary_source = next((s for s in self.epg_config.sources if s.is_primary), None)
                if primary_source:
                    response = requests.get(primary_source.url, timeout=30)
                    if response.status_code == 200:
                        with open(local_file, 'w', encoding='utf-8') as f:
                            f.write(response.text)
                        return True
        except Exception as e:
            logger.error(f"下载EPG失败: {str(e)}")
        
        return False

    def load_epg_data(self) -> bool:
        """加载EPG数据到内存"""
        if not self.epg_config:
            return False

        local_file = self.epg_config.local_file
        if not os.path.exists(local_file):
            logger.warning(f"EPG文件不存在: {local_file}")
            return False

        try:
            # 先读取文件内容
            with open(local_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 尝试修复常见的XML格式问题
            content = content.strip()
            if not content.startswith('<?xml'):
                content = '<?xml version="1.0" encoding="UTF-8"?>\n' + content
            
            # 解析XML
            try:
                root = ET.fromstring(content)
            except ET.ParseError:
                # 尝试修复多个根节点的问题
                if content.count('<?xml') > 1:
                    parts = content.split('<?xml')
                    content = parts[0] + '\n'.join(['<root>'] + ['<?xml' + p for p in parts[1:]]) + '</root>'
                    root = ET.fromstring(content)
                else:
                    raise
            
            # 解析XML数据（简化版，实际需要根据EPG XML格式调整）
            for channel_elem in root.findall('.//channel'):
                channel_id = channel_elem.get('id')
                name = channel_elem.findtext('display-name')
                
                programs = []
                for program_elem in root.findall(f'.//programme[@channel="{channel_id}"]'):
                    programs.append(EPGProgram(
                        channel_id=channel_id,
                        title=program_elem.findtext('title'),
                        start_time=program_elem.get('start'),
                        end_time=program_elem.get('stop'),
                        description=program_elem.findtext('desc', '')
                    ))
                
                self.epg_data[channel_id] = EPGChannel(
                    id=channel_id,
                    name=name,
                    programs=programs
                )
            
            self.loaded = True
            return True
        except Exception as e:
            logger.error(f"解析EPG数据失败: {str(e)}")
            return False

    def get_channel_programs(self, channel_id: str) -> Optional[List[EPGProgram]]:
        """获取指定频道的节目单"""
        if not self.loaded:
            if not self.load_epg_data():
                return None
        
        channel = self.epg_data.get(channel_id)
        return channel.programs if channel else None

    def get_channel_names(self) -> List[str]:
        """获取所有频道名称"""
        if not self.loaded:
            if not self.load_epg_data():
                return []
        
        return [channel.name for channel in self.epg_data.values()]

    def refresh_epg(self, force_update=False) -> bool:
        """刷新EPG数据"""
        if self.download_epg(force_update):
            return self.load_epg_data()
        return False
