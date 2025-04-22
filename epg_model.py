from dataclasses import dataclass
from typing import List, Optional

@dataclass
class EPGSource:
    """EPG源配置"""
    url: str
    is_primary: bool = False

@dataclass
class EPGConfig:
    """EPG配置"""
    sources: List[EPGSource]
    merge_sources: bool = False  # 是否合并多个源
    last_update: Optional[str] = None  # 最后更新时间
    local_file: str = "epg.xml"  # 本地EPG文件路径

@dataclass
class EPGProgram:
    """EPG节目信息"""
    channel_id: str
    title: str
    start_time: str
    end_time: str
    description: str = ""

@dataclass
class EPGChannel:
    """EPG频道信息"""
    id: str
    name: str
    programs: List[EPGProgram]
