import os
import traceback
import requests
import time
import xml.etree.ElementTree as ET
from typing import List, Dict, Optional
from dataclasses import asdict
from PyQt6.QtCore import QThread, pyqtSignal
from epg_model import EPGConfig, EPGChannel, EPGProgram, EPGSource
from config_manager import ConfigManager
from log_manager import LogManager

logger = LogManager()

class EPGManager(QThread):
    progress = pyqtSignal(float, str)  # 进度百分比, 状态消息
    finished = pyqtSignal(bool)  # 是否成功
    
    def __init__(self, config_manager: ConfigManager):
        super().__init__()
        self.config_manager = config_manager
        self.epg_config = self.config_manager.load_epg_config()
        self.epg_data: Dict[str, EPGChannel] = {}
        self._name_index: Dict[str, List[str]] = {}
        self.loaded = False
        self._operation = None  # 'update' or 'load'
        self._result = False  # 操作结果
        
    @property
    def result(self) -> bool:
        """获取操作结果"""
        return self._result
        
    def get_result(self) -> bool:
        """获取操作结果(兼容旧方法)"""
        return self._result
        
    def refresh_epg(self, force_update=False, is_init=False):
        """启动EPG刷新流程
        Args:
            force_update: 是否强制更新
            is_init: 是否为初始化加载(不显示警告)
        """
        if self.isRunning():
            if not is_init:
                logger.warning("EPG操作正在进行中，忽略本次请求")
            return
            
        self._operation = 'update' if force_update else 'load'
        logger.info(f"准备启动EPG操作: {self._operation}")
        self.start()
        
    def run(self):
        """执行EPG操作的主线程方法"""
        op_id = str(int(time.time() * 1000))[-6:]  # 生成6位操作ID
        try:
            logger.info(f"[{op_id}] 开始EPG操作: {self._operation}")
            
            if self._operation == 'update':
                result = self._update_epg(op_id)
            elif self._operation == 'load':
                result = self._load_epg(op_id)
            else:
                raise ValueError(f"[{op_id}] 未知的EPG操作类型: {self._operation}")
                
            if result:
                logger.info(f"[{op_id}] EPG操作成功: {self._operation}")
                self.finished.emit(True)
            else:
                raise Exception(f"[{op_id}] EPG操作未完成")
                
        except Exception as e:
            logger.error(f"[{op_id}] EPG操作失败: {str(e)}")
            logger.error(f"[{op_id}] 详细错误信息:\n{traceback.format_exc()}")
            self.finished.emit(False)
            
    def _update_epg(self, op_id: str) -> bool:
        """更新EPG数据流程"""
        self.progress.emit(0, f"[{op_id}] 开始更新EPG数据...")
        
        # 1. 下载EPG数据
        self.progress.emit(0.3, "正在下载EPG数据...")
        if not self._download_epg():
            raise Exception("EPG下载失败")
            
        # 2. 解析EPG数据
        self.progress.emit(0.7, "正在解析EPG数据...")
        if not self._parse_epg():
            raise Exception("EPG解析失败")
            
        self.progress.emit(1.0, "EPG更新完成")
        
    def _load_epg(self, op_id: str) -> bool:
        """加载EPG数据流程"""
        self.progress.emit(0, f"[{op_id}] 开始加载EPG数据...")
        
        try:
            # 1. 检查本地文件
            local_file = self.epg_config.local_file
            if not os.path.exists(local_file):
                raise FileNotFoundError(f"[{op_id}] EPG文件不存在: {local_file}")
            if not os.access(local_file, os.R_OK):
                raise PermissionError(f"[{op_id}] 无读取权限: {local_file}")
                
            # 2. 解析EPG数据
            self.progress.emit(0.5, "正在解析EPG数据...")
            parse_result = self._parse_epg()
            if not parse_result:
                raise Exception(f"[{op_id}] EPG解析失败")
                
            self.progress.emit(1.0, "EPG加载完成")
            return True
            
        except Exception as e:
            logger.error(f"[{op_id}] 加载EPG失败: {str(e)}")
            raise
        
    def _download_epg(self) -> bool:
        """下载EPG文件"""
        local_file = self.epg_config.local_file
        logger.info(f"开始下载EPG, 保存路径: {local_file}")
        logger.info(f"合并模式: {self.epg_config.merge_sources}")
        
        # 如果是合并模式，下载并合并所有源
        if self.epg_config.merge_sources:
            merged_data = None
            for source in self.epg_config.sources:
                for attempt in range(3):  # 重试3次
                    try:
                        headers = {
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                            'Accept': 'text/xml,application/xml'
                        }
                        time.sleep(5 * (attempt + 1))  # 重试间隔
                        response = requests.get(source.url, headers=headers, timeout=30)
                        if response.status_code == 200:
                            content = response.text
                            if '<?xml' in content:
                                content = content[content.index('<?xml'):]
                            xml_content = content[content.index('?>')+2:] if '?>' in content else content
                            if merged_data is None:
                                merged_data = f'<?xml version="1.0" encoding="UTF-8"?>\n<merged_epg>\n{xml_content}'
                            else:
                                merged_data += f'\n{xml_content}'
                            break
                    except Exception as e:
                        if attempt == 2:
                            logger.error(f"EPG源[{source.url}]下载失败: {str(e)}")
                            return False
                        logger.warning(f"EPG源[{source.url}]下载尝试{attempt+1}失败: {str(e)}\n{traceback.format_exc()}")
            
            if merged_data:
                try:
                    with open(local_file, 'w', encoding='utf-8') as f:
                        f.write(merged_data + '\n</merged_epg>')
                    return True
                except Exception as e:
                    logger.error(f"写入合并EPG文件失败: {str(e)}")
                    return False
        else:
            # 只下载主EPG源
            primary_source = next((s for s in self.epg_config.sources if s.is_primary), None)
            if primary_source:
                for attempt in range(3):
                    try:
                        response = requests.get(primary_source.url, timeout=30)
                        if response.status_code == 200:
                            with open(local_file, 'w', encoding='utf-8') as f:
                                f.write(response.text)
                            return True
                    except Exception as e:
                        if attempt == 2:
                            logger.error(f"主EPG源下载失败: {str(e)}")
                            return False
                        logger.warning(f"主EPG源下载尝试{attempt+1}失败: {str(e)}\n{traceback.format_exc()}")
        return False
        
    def _parse_epg(self) -> bool:
        """解析EPG文件"""
        try:
            import lxml.etree as ET
            self.epg_data = {}
            self._name_index = {}
            
            context = ET.iterparse(self.epg_config.local_file, events=('start', 'end'), recover=True)
            
            for event, elem in context:
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
            return True
            
        except ET.XMLSyntaxError as e:
            logger.error(f"EPG文件格式错误: {str(e)}\n文件路径: {self.epg_config.local_file}")
            try:
                with open(self.epg_config.local_file, 'rb') as f:
                    logger.error(f"文件开头内容(hex): {f.read(100).hex()}")
            except Exception as e:
                logger.error(f"无法读取文件内容: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"EPG解析失败: {str(e)}")
            return False
            
    def get_channel_programs(self, channel_name: str) -> Optional[List[EPGProgram]]:
        """获取频道节目单(支持模糊匹配)
        Args:
            channel_name: 频道名称(支持模糊匹配)
        """
        if not self.loaded:
            return None
            
        # 1. 尝试精确匹配(不区分大小写)
        normalized_name = channel_name.lower().strip()
        for name, ids in self._name_index.items():
            if name == normalized_name:
                channel = self.epg_data.get(ids[0])
                return channel.programs if channel else []
                
        # 2. 尝试包含匹配(频道名称包含在EPG名称中)
        for name, ids in self._name_index.items():
            if normalized_name in name or name in normalized_name:
                channel = self.epg_data.get(ids[0])
                return channel.programs if channel else []
                
        # 3. 尝试部分匹配(去除空格和特殊字符后匹配)
        clean_name = ''.join(c for c in normalized_name if c.isalnum())
        for name, ids in self._name_index.items():
            clean_epg_name = ''.join(c for c in name if c.isalnum())
            if clean_name in clean_epg_name or clean_epg_name in clean_name:
                channel = self.epg_data.get(ids[0])
                return channel.programs if channel else []
                
        return None

    def get_channel_names(self) -> List[str]:
        """获取所有频道名称列表"""
        if not self.loaded:
            return []
        return list(self._name_index.keys())
