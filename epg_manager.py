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
        self._name_index: Dict[str, List[str]] = {}  # channel_name -> List[channel_id]
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

    def load_epg_data(self, progress_signal=None, finished_signal=None) -> None:
        """异步加载EPG数据到内存(事件驱动模式)"""
        from PyQt6.QtCore import QThread, pyqtSignal
        from queue import Queue
        
        class EPGParserThread(QThread):
            progress = pyqtSignal(float)
            finished = pyqtSignal(bool)
            
            def __init__(self, file_path):
                super().__init__()
                self.file_path = file_path
                self.queue = Queue()
                self.running = True
                
            def run(self):
                try:
                    # 分块读取文件
                    chunk_size = 1024 * 1024  # 1MB
                    with open(self.file_path, 'rb') as f:
                        while self.running:
                            chunk = f.read(chunk_size)
                            if not chunk:
                                break
                            self.queue.put(chunk)
                            self.progress.emit(f.tell() / os.path.getsize(self.file_path))
                            
                    # 解析XML
                    import lxml.etree as ET
                    parser = ET.XMLParser(recover=True, encoding='utf-8')
                    
                    # 流式解析
                    context = ET.iterparse(self.queue, events=('start', 'end'), parser=parser)
                    self.epg_data = {}
                    self._name_index = {}
                    
                    for event, elem in context:
                        if not self.running:
                            break
                            
                        if event == 'start' and elem.tag == 'channel':
                            channel_id = elem.get('id')
                            if channel_id:
                                names = [e.text for e in elem.xpath('display-name') if e.text]
                                self.epg_data[channel_id] = EPGChannel(
                                    id=channel_id,
                                    name=names[0] if names else channel_id,
                                    programs=[]
                                )
                                for name in names:
                                    self._name_index.setdefault(name.lower(), []).append(channel_id)
                                
                        elif event == 'end' and elem.tag == 'programme':
                            try:
                                channel_id = elem.get('channel')
                                if channel_id in self.epg_data:
                                    self.epg_data[channel_id].programs.append(EPGProgram(
                                        channel_id=channel_id,
                                        title=elem.xpath('title/text()')[0] if elem.xpath('title/text()') else '',
                                        start_time=elem.get('start'),
                                        end_time=elem.get('stop'),
                                        description=elem.xpath('desc/text()')[0] if elem.xpath('desc/text()') else ''
                                    ))
                            except Exception as e:
                                logger.warning(f"解析节目出错: {str(e)}")
                            finally:
                                elem.clear()
                                
                    self.loaded = True
                    self.finished.emit(True)
                    
                except Exception as e:
                    logger.error(f"EPG解析失败: {str(e)}")
                    self.finished.emit(False)
                    
            def stop(self):
                self.running = False
                
        if not self.epg_config:
            if finished_signal:
                finished_signal.emit(False)
            return

        local_file = self.epg_config.local_file
        if not os.path.exists(local_file):
            logger.warning(f"EPG文件不存在: {local_file}")
            if finished_signal:
                finished_signal.emit(False)
            return

        self.parser_thread = EPGParserThread(local_file)
        if progress_signal:
            self.parser_thread.progress.connect(progress_signal)
        if finished_signal:
            self.parser_thread.finished.connect(finished_signal)
        self.parser_thread.start()

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
