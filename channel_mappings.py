import requests
import os
from typing import Dict, List
from log_manager import LogManager

# 默认远程URL
DEFAULT_REMOTE_URL = "https://raw.githubusercontent.com/sumingyd/IPTV-Scanner-Editor-Pro/main/local_channel_mappings.txt"
def _get_local_mapping_path() -> str:
    """获取本地映射文件路径，处理开发环境和打包环境"""
    import os
    import sys
    
    # 1. 尝试从打包后的路径查找
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
        exe_path = os.path.join(base_path, 'local_channel_mappings.txt')
        if os.path.exists(exe_path):
            return exe_path
    
    # 2. 尝试从开发环境路径查找
    dev_path = os.path.join(os.path.dirname(__file__), 'local_channel_mappings.txt')
    if os.path.exists(dev_path):
        return dev_path
        
    # 3. 尝试当前目录
    current_path = 'local_channel_mappings.txt'
    return current_path

def parse_mapping_line(line: str) -> Dict[str, dict]:
    """解析单行映射规则
    新格式: 标准名称 = "原始名称1" "原始名称2" = logo地址
    """
    if '=' not in line:
        return {}
    
    parts = [p.strip() for p in line.split('=', 2)]
    standard_name = parts[0]
    
    # 解析原始名称列表
    raw_names = [name.strip('"\' ') for name in parts[1].split()]
    
    # 解析logo地址(如果有)
    logo_url = parts[2] if len(parts) > 2 else None
    
    return {
        standard_name: {
            'raw_names': raw_names,
            'logo_url': logo_url if logo_url and logo_url.lower() not in ['', 'none', 'null'] else None
        }
    }

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

def create_reverse_mappings(mappings: Dict[str, dict]) -> Dict[str, dict]:
    """创建反向映射字典
    返回格式: {raw_name: {'standard_name': str, 'logo_url': str}}
    """
    reverse_mappings = {}
    for standard_name, data in mappings.items():
        for raw_name in data['raw_names']:
            reverse_mappings[raw_name] = {
                'standard_name': standard_name,
                'logo_url': data['logo_url']
            }
    return reverse_mappings

# 加载映射规则 - 先尝试远程，失败后尝试本地
remote_mappings = load_remote_mappings()
local_mappings = load_mappings_from_file(_get_local_mapping_path())

# 记录加载状态
logger = LogManager()
if remote_mappings:
    logger.info("成功加载远程映射规则")
elif local_mappings:
    logger.warning("远程映射加载失败，使用本地映射")
else:
    logger.error("远程和本地映射都不可用，将跳过频道名映射")

# 合并映射规则(远程优先)
combined_mappings = {**local_mappings, **remote_mappings}

# 创建反向映射
REVERSE_MAPPINGS = create_reverse_mappings(combined_mappings)

def get_channel_info(raw_name: str) -> dict:
    """获取频道信息(标准名称和logo地址)
    返回格式: {'standard_name': str, 'logo_url': str}
    """
    if not raw_name or raw_name.isspace():
        return {'standard_name': '', 'logo_url': None}
    
    # 标准化输入名称
    normalized_name = raw_name.strip().lower()
    
    # 先检查远程映射
    try:
        reverse_remote = create_reverse_mappings(remote_mappings)
        for raw_pattern, info in reverse_remote.items():
            if normalized_name == raw_pattern.strip().lower():
                return info
    except Exception as e:
        LogManager().error(f"远程映射查找失败: {e}")
        
    # 再检查本地映射
    try:
        reverse_local = create_reverse_mappings(local_mappings)
        for raw_pattern, info in reverse_local.items():
            if normalized_name == raw_pattern.strip().lower():
                return info
    except Exception as e:
        LogManager().error(f"本地映射查找失败: {e}")
        
    # 都没有匹配则返回原始名称
    return {'standard_name': raw_name, 'logo_url': None}
