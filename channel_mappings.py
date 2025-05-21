import requests
import os
import re
from typing import Dict, List
from log_manager import LogManager

# 默认远程URL
DEFAULT_REMOTE_URL = "https://raw.githubusercontent.com/sumingyd/IPTV-Scanner-Editor-Pro/main/local_channel_mappings.txt"

def extract_channel_name_from_url(url: str) -> str:
    """从URL提取频道名，支持多种协议格式"""
    try:
        # 标准化URL为小写
        url_lower = url.lower()
        
        # 组播地址提取 - 保留完整组播地址作为频道名
        for proto in ['rtp', 'stp', 'udp', 'rtsp']:
            proto_prefix = f'/{proto}/'
            if proto_prefix in url_lower:
                full_addr = url.split(proto_prefix)[1].split('?')[0].split('#')[0].strip()
                return full_addr
        
        # 处理单播URL中的频道ID模式
        if '/channel' in url_lower:
            import re
            match = re.search(r'/channel(\d+)/', url_lower)
            if match:
                return f"CHANNEL{match.group(1)}"
        
        # 处理PLTV/数字/数字/数字/index.m3u8模式
        if '/pltv/' in url_lower and '/index.m3u8' in url_lower:
            import re
            match = re.search(r'/pltv/(\d+)/(\d+)/(\d+)/', url_lower)
            if match:
                return f"PLTV_{match.group(3)}"

        # 处理数字ID.smil/.smail格式
        if url_lower.endswith(('.smil', '.smail')):
            import re
            match = re.search(r'/(\d+)\.(smil|smail)$', url_lower)
            if match:
                return match.group(1)
        
        # HTTP/HTTPS地址提取
        if url_lower.startswith(('http://', 'https://')):
            # 移除查询参数和片段标识符
            clean_url = url.split('?')[0].split('#')[0]
            parts = [p for p in clean_url.split('/') if p]  # 过滤空部分
            
            # 1. 优先提取路径中的数字ID - 检查所有部分
            for part in parts:
                # 先尝试直接匹配纯数字
                if part.isdigit():
                    return part
                # 尝试从混合字符串中提取数字
                digits = ''.join(filter(str.isdigit, part))
                if digits:
                    return digits
            
            # 2. 处理特殊文件名情况
            for i in range(len(parts)):
                part = parts[i]
                if part in ['playlist.m3u8', 'index.m3u8']:
                    # 尝试从整个URL路径中提取数字ID
                    for p in parts:
                        if p.isdigit():
                            return p
                    # 如果没有数字，返回前一部分
                    prev_part = parts[i-1] if i > 0 else part
                    # 检查前一部分是否是数字ID
                    if prev_part.isdigit():
                        return prev_part
                    return prev_part
            
            # 3. 处理类似3221225530这样的长数字ID
            last_part = parts[-1]
            if last_part.isdigit() and len(last_part) >= 6:  # 长数字ID
                return last_part
            
            # 4. 最后处理默认情况
            return parts[-1].split('.')[0] if '.' in parts[-1] else parts[-1]
        
        # 默认提取URL最后部分
        return url.split('/')[-1].split('?')[0].split('#')[0].strip()
    except Exception as e:
        LogManager().error(f"提取频道名失败: {e}")
        return url  # 如果提取失败，返回完整URL

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
    新格式: 标准名称 = "原始名称1" "原始名称2" = logo地址 = 分组名
    """
    if '=' not in line:
        return {}
    
    parts = [p.strip() for p in line.split('=', 3)]
    standard_name = parts[0]
    
    # 解析原始名称列表 - 保留引号内的原始空格
    import shlex
    raw_names = []
    try:
        # 使用shlex处理带引号的字符串
        parsed = shlex.split(parts[1])
        for name in parsed:
            # 只去除最外层的引号，保留内部空格
            if (name.startswith('"') and name.endswith('"')) or (name.startswith("'") and name.endswith("'")):
                name = name[1:-1]
            raw_names.append(name)
    except:
        # 如果解析失败，回退到原始方法
        raw_names = [name.strip('"\' ') for name in parts[1].split()]
    
    # 解析logo地址(如果有)
    logo_url = parts[2].strip('"\' ') if len(parts) > 2 else None
    
    # 解析分组名(如果有)
    group_name = parts[3].strip('"\' ') if len(parts) > 3 else None
    
    return {
        standard_name: {
            'raw_names': raw_names,
            'logo_url': logo_url if logo_url and logo_url.lower() not in ['', 'none', 'null'] else None,
            'group_name': group_name if group_name and group_name.lower() not in ['', 'none', 'null'] else None
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
    返回格式: {raw_name: {'standard_name': str, 'logo_url': str, 'group_name': str}}
    """
    reverse_mappings = {}
    for standard_name, data in mappings.items():
        for raw_name in data['raw_names']:
            reverse_mappings[raw_name] = {
                'standard_name': standard_name,
                'logo_url': data['logo_url'],
                'group_name': data.get('group_name')
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
    """获取频道信息(标准名称、logo地址和分组名)
    返回格式: {'standard_name': str, 'logo_url': str, 'group_name': str}
    """
    logger = LogManager()
    if not raw_name or raw_name.isspace():
        logger.debug(f"get_channel_info: 空频道名输入")
        return {'standard_name': '', 'logo_url': None}
    
    # 标准化输入名称 - 保留原始空格，仅去除首尾空格并转换为小写
    normalized_name = raw_name.strip().lower()
    logger.debug(f"get_channel_info: 查找频道 '{raw_name}' (标准化: '{normalized_name}')")
    
    # 1. 先检查远程映射(原始名称)
    try:
        reverse_remote = create_reverse_mappings(remote_mappings)
        for raw_pattern, info in reverse_remote.items():
            normalized_pattern = re.sub(r'\s+', ' ', raw_pattern.strip()).lower()
            if normalized_name == normalized_pattern:
                logger.debug(f"从远程映射找到匹配: {raw_pattern} -> {info}")
                return info
    except Exception as e:
        logger.error(f"远程映射查找失败: {e}")
        
    # 2. 再检查本地映射(原始名称)
    try:
        reverse_local = create_reverse_mappings(local_mappings)
        for raw_pattern, info in reverse_local.items():
            normalized_pattern = re.sub(r'\s+', ' ', raw_pattern.strip()).lower()
            if normalized_name == normalized_pattern:
                logger.debug(f"从本地映射找到匹配: {raw_pattern} -> {info}")
                return info
    except Exception as e:
        logger.error(f"本地映射查找失败: {e}")
        
    # 3. 检查标准名称映射(如果输入的是标准名称)
    try:
        for standard_name, info in combined_mappings.items():
            normalized_standard = re.sub(r'\s+', ' ', standard_name.strip()).lower()
            if normalized_name == normalized_standard:
                logger.debug(f"从标准名称找到匹配: {standard_name} -> {info}")
                return {
                    'standard_name': standard_name,
                    'logo_url': info['logo_url']
                }
    except Exception as e:
        logger.error(f"标准名称查找失败: {e}")
        
    # 都没有匹配则返回原始名称
    logger.debug(f"没有找到匹配的映射，返回原始名称")
    return {'standard_name': raw_name, 'logo_url': None}
