import os
import requests
import time
import xml.etree.ElementTree as ET
from typing import List, Dict, Optional
from dataclasses import asdict
from epg_model import EPGConfig, EPGChannel, EPGProgram, EPGSource
from config_manager import ConfigManager
from log_manager import LogManager
logger = LogManager()

class EPGManager:
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        # 确保EPG配置正确加载，如果不存在则创建默认配置
        self.epg_config = self.config_manager.load_epg_config()
        if not self.epg_config.sources:
            # 添加默认EPG源
            self.epg_config.sources.append(EPGSource(
                url="http://example.com/epg.xml",
                is_primary=True
            ))
            self.config_manager.save_epg_config(self.epg_config)
            
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

        # 如果是合并模式，下载并合并所有源
        if self.epg_config.merge_sources:
            merged_data = None
            for source in self.epg_config.sources:
                # 添加重试机制
                for attempt in range(3):
                    try:
                        # 增加请求头模拟浏览器访问
                        headers = {
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                            'Accept': 'text/xml,application/xml'
                        }
                        # 增加重试间隔(3秒)
                        time.sleep(3 * attempt)
                        response = requests.get(source.url, headers=headers, timeout=(10, 30))
                        if response.status_code == 200:
                            content = response.text
                            # 确保XML声明在开头
                            if '<?xml' in content:
                                content = content[content.index('<?xml'):]
                            # 提取XML内容部分(去掉声明)
                            xml_content = content[content.index('?>')+2:] if '?>' in content else content
                            if merged_data is None:
                                merged_data = f'<?xml version="1.0" encoding="UTF-8"?>\n<merged_epg>\n{xml_content}'
                            else:
                                merged_data += f'\n{xml_content}'
                            break
                    except requests.exceptions.RequestException as e:
                        if attempt == 2:
                            logger.error(f"EPG下载最终失败: {str(e)}")
                            return False
                        logger.warning(f"EPG下载尝试 {attempt+1} 失败: {str(e)}")
                
            if merged_data:
                try:
                    with open(local_file, 'w', encoding='utf-8') as f:
                        f.write(merged_data)
                    return True
                except IOError as e:
                    logger.error(f"写入EPG文件失败: {str(e)}")
                    return False
        else:
            # 只下载主EPG源
            primary_source = next((s for s in self.epg_config.sources if s.is_primary), None)
            if primary_source:
                for attempt in range(3):
                    try:
                        response = requests.get(primary_source.url, timeout=30)
                        if response.status_code == 200:
                            content = response.text
                            # 确保XML声明在开头
                            if '<?xml' in content:
                                content = content[content.index('<?xml'):]
                            try:
                                with open(local_file, 'w', encoding='utf-8') as f:
                                    f.write(content)
                                return True
                            except IOError as e:
                                logger.error(f"写入EPG文件失败: {str(e)}")
                                return False
                    except requests.exceptions.RequestException as e:
                        if attempt == 2:
                            logger.error(f"主EPG源下载最终失败: {str(e)}")
                            return False
                        logger.warning(f"主EPG源下载尝试 {attempt+1} 失败: {str(e)}")
        
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
            
            # 清理和修复XML内容
            content = content.strip()
            
            # 1. 确保有XML声明
            if not content.startswith('<?xml'):
                content = '<?xml version="1.0" encoding="UTF-8"?>\n' + content
            
            # 2. 深度清理和验证XML内容
            # 移除非法控制字符
            content = ''.join(char for char in content if ord(char) >= 32 or char in '\n\r\t')
            
            # 修复常见的XML格式问题
            content = content.replace('&', '&')  # 正确转义特殊字符
            content = content.replace('<', '<')  # 转义未闭合标签
            content = content.replace('>', '>')  # 转义未闭合标签
            content = content.replace(']]>', ']]>')  # 处理CDATA结束符
            
            # 移除BOM字符(如果存在)
            if content.startswith('\ufeff'):
                content = content[1:]
                
            # 验证XML基本结构
            if not ('<?xml' in content and '<tv' in content and '</tv>' in content):
                logger.error("EPG文件缺少必要的XML结构")
                return False
            
            # 3. 分块解析XML内容
            try:
                # 先尝试完整解析
                root = ET.fromstring(content)
            except ET.ParseError as e:
                logger.warning(f"完整解析失败({self.epg_config.local_file})，尝试分块解析: {str(e)}")
                # 分块处理XML内容
                chunks = []
                current_chunk = []
                for line in content.split('\n'):
                    try:
                        # 尝试解析当前行
                        ET.fromstring(f"<root>{line}</root>")
                        current_chunk.append(line)
                    except ET.ParseError:
                        if current_chunk:
                            chunks.append('\n'.join(current_chunk))
                            current_chunk = []
                
                if current_chunk:
                    chunks.append('\n'.join(current_chunk))
                
                # 尝试解析有效块
                valid_data = []
                for chunk in chunks:
                    try:
                        root = ET.fromstring(f"<root>{chunk}</root>")
                        valid_data.append(chunk)
                    except ET.ParseError:
                        logger.warning(f"忽略无效XML块: {chunk[:50]}...")
                
                if not valid_data:
                    logger.error("没有找到有效的XML数据块")
                    return False
                
                content = '<?xml version="1.0" encoding="UTF-8"?>\n<tv>\n' + \
                         '\n'.join(valid_data) + '\n</tv>'
                root = ET.fromstring(content)
            
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
        """刷新EPG数据
        Args:
            force_update: True表示强制下载更新，False表示优先使用本地文件
        Returns:
            bool: 是否成功加载EPG数据
        """
        operation = "强制刷新" if force_update else "刷新"
        logger.info(f"开始EPG刷新操作: {operation} (本地文件: {self.epg_config.local_file})")
        
        # 检查本地文件是否存在
        file_exists = os.path.exists(self.epg_config.local_file)
        logger.info(f"本地EPG文件状态: {'存在' if file_exists else '不存在'}")
        
        # 处理逻辑:
        # 1. 如果强制刷新 -> 直接下载更新
        # 2. 如果非强制刷新:
        #    a. 文件存在 -> 加载本地文件
        #    b. 文件不存在 -> 下载更新
        
        if force_update:
            logger.info("强制刷新模式，直接下载EPG数据...")
            if self.download_epg(force_update=True):
                logger.info("EPG数据下载完成，开始解析...")
                return self.load_epg_data()
        else:
            if file_exists:
                logger.info("优先加载本地EPG文件...")
                if self.load_epg_data():
                    logger.info("成功从本地文件加载EPG数据")
                    return True
                logger.warning("本地EPG文件加载失败，尝试下载更新...")
            
            logger.info("开始下载EPG数据...")
            if self.download_epg(force_update=True):
                logger.info("EPG数据下载完成，开始解析...")
                if self.load_epg_data():
                    logger.info("EPG数据加载成功")
                    return True
                logger.error("EPG数据解析失败")
        
        logger.error("EPG刷新操作失败")
        return False
