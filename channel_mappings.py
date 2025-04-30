import requests
import os
from typing import Dict, List
from log_manager import LogManager

# 默认远程URL
DEFAULT_REMOTE_URL = "https://raw.githubusercontent.com/sumingyd/IPTV-Scanner-Editor-Pro/main/local_channel_mappings.txt"
# 本地映射文件路径
LOCAL_MAPPING_FILE = "local_channel_mappings.txt"

def parse_mapping_line(line: str) -> Dict[str, List[str]]:
    """解析单行映射规则"""
    if '=' not in line:
        return {}
    
    standard_name, raw_names = line.split('=', 1)
    standard_name = standard_name.strip()
    raw_names = [name.strip('"\' ') for name in raw_names.split()]
    
    return {standard_name: raw_names}

def load_mappings_from_file(file_path: str) -> Dict[str, List[str]]:
    """从文件加载映射规则"""
    mappings = {}
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    mappings.update(parse_mapping_line(line))
    except Exception as e:
        LogManager().error(f"加载映射文件 {file_path} 失败: {e}")
    return mappings

def load_remote_mappings() -> Dict[str, List[str]]:
    """加载远程映射规则"""
    logger = LogManager()
    try:
        from config_manager import ConfigManager
        config = ConfigManager()
        try:
            remote_url = config.get('channel_mappings', 'remote_url', DEFAULT_REMOTE_URL)
        except AttributeError:
            remote_url = DEFAULT_REMOTE_URL
        
        response = requests.get(remote_url, timeout=10)
        response.raise_for_status()
        
        # 创建临时文件保存远程内容
        temp_file = "remote_mappings.tmp"
        with open(temp_file, 'w', encoding='utf-8') as f:
            f.write(response.text)
        
        # 从临时文件加载映射
        mappings = load_mappings_from_file(temp_file)
        os.remove(temp_file)
        return mappings
    except Exception as e:
        logger.error(f"加载远程映射失败: {e}, 使用本地映射")
        return {}

def create_reverse_mappings(mappings: Dict[str, List[str]]) -> Dict[str, str]:
    """创建反向映射字典"""
    reverse_mappings = {}
    for standard_name, raw_names in mappings.items():
        for raw_name in raw_names:
            reverse_mappings[raw_name] = standard_name
    return reverse_mappings

# 加载映射规则
local_mappings = load_mappings_from_file(LOCAL_MAPPING_FILE)
remote_mappings = load_remote_mappings()

# 合并映射规则(本地优先)
combined_mappings = {**remote_mappings, **local_mappings}

# 创建反向映射
REVERSE_MAPPINGS = create_reverse_mappings(combined_mappings)

def get_standard_name(raw_name: str) -> str:
    """获取标准化频道名"""
    return REVERSE_MAPPINGS.get(raw_name, raw_name)
