import requests
import os
import re
from typing import Dict, List
from log_manager import LogManager

# 创建全局日志管理器实例
logger = LogManager()

# 默认远程URL - 优先使用CSV格式，如果不存在则尝试TXT格式
DEFAULT_REMOTE_URL = "https://raw.githubusercontent.com/sumingyd/IPTV-Scanner-Editor-Pro/main/local_channel_mappings.csv"

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
        logger.error(f"提取频道名失败: {e}")
        return url  # 如果提取失败，返回完整URL

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

def load_mappings_from_file(file_path: str) -> Dict[str, dict]:
    """从文件加载映射规则，支持txt和csv格式"""
    mappings = {}
    try:
        if file_path.lower().endswith('.csv'):
            # 加载CSV格式
            import csv
            with open(file_path, 'r', encoding='utf-8-sig') as f:  # 使用utf-8-sig处理BOM
                reader = csv.DictReader(f)
                for row in reader:
                    # 处理可能的BOM字符
                    standard_name = row.get('standard_name', '').strip().lstrip('\ufeff')
                    
                    # 跳过分组标题行
                    if standard_name.startswith('##########') and standard_name.endswith('##########'):
                        continue
                    
                    raw_names = [name.strip() for name in row.get('raw_names', '').split(',')] if row.get('raw_names') else []
                    logo_url = row.get('logo_url', '').strip() if row.get('logo_url') else None
                    group_name = row.get('group_name', '').strip() if row.get('group_name') else None
                    
                    if standard_name:  # 确保标准名称不为空
                        mappings[standard_name] = {
                            'raw_names': raw_names,
                            'logo_url': logo_url if logo_url and logo_url.lower() not in ['', 'none', 'null'] else None,
                            'group_name': group_name if group_name and group_name.lower() not in ['', 'none', 'null'] else None
                        }
        else:
            # 加载txt格式（向后兼容）
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        mappings.update(parse_mapping_line(line))
    except Exception as e:
        logger.error(f"加载映射文件 {file_path} 失败: {e}")
    return mappings

def load_remote_mappings() -> Dict[str, dict]:
    """加载远程映射规则"""
    try:
        from config_manager import ConfigManager
        config = ConfigManager()
        try:
            remote_url = config.get('channel_mappings', 'remote_url', DEFAULT_REMOTE_URL)
        except AttributeError:
            remote_url = DEFAULT_REMOTE_URL
        
        # 增加重试机制和SSL错误处理
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # 先尝试CSV格式
                response = requests.get(remote_url, timeout=10, verify=False)  # 临时禁用SSL验证
                if response.status_code == 404:
                    # 如果CSV格式不存在，尝试TXT格式（向后兼容）
                    txt_url = remote_url.replace('.csv', '.txt')
                    logger.info(f"CSV映射文件不存在，尝试TXT格式: {txt_url}")
                    response = requests.get(txt_url, timeout=10, verify=False)
                
                response.raise_for_status()
                
                # 根据文件扩展名确定格式
                if remote_url.endswith('.csv') or response.url.endswith('.csv'):
                    file_ext = '.csv'
                else:
                    file_ext = '.txt'
                
                # 创建临时文件保存远程内容
                temp_file = f"remote_mappings{file_ext}"
                with open(temp_file, 'w', encoding='utf-8') as f:
                    f.write(response.text)
                
                # 从临时文件加载映射
                mappings = load_mappings_from_file(temp_file)
                os.remove(temp_file)
                logger.info(f"成功加载远程映射规则，共 {len(mappings)} 条映射")
                return mappings
                
            except requests.exceptions.SSLError as e:
                logger.warning(f"SSL错误 (尝试 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    import time
                    time.sleep(2)  # 等待2秒后重试
                else:
                    raise e
            except Exception as e:
                logger.error(f"加载远程映射失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    import time
                    time.sleep(2)  # 等待2秒后重试
                else:
                    raise e
                    
        return {}  # 所有重试都失败
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

# 加载远程映射规则
remote_mappings = load_remote_mappings()

# 记录加载状态
if remote_mappings:
    logger.info("成功加载远程映射规则")
else:
    logger.error("远程映射加载失败，将跳过频道名映射")

# 使用远程映射
combined_mappings = remote_mappings

# 创建反向映射
REVERSE_MAPPINGS = create_reverse_mappings(combined_mappings)

def get_channel_info(raw_name: str) -> dict:
    """获取频道信息(标准名称、logo地址和分组名)
    返回格式: {'standard_name': str, 'logo_url': str, 'group_name': str}
    """
    if not raw_name or raw_name.isspace():
        return {'standard_name': '', 'logo_url': None}
    
    # 标准化输入名称 - 保留原始空格，仅去除首尾空格并转换为小写
    normalized_name = raw_name.strip().lower()
    
    # 如果原始名称为空，直接返回
    if not normalized_name:
        return {'standard_name': raw_name, 'logo_url': None}
    
    # 检查远程映射(原始名称) - 使用精确匹配
    try:
        reverse_remote = create_reverse_mappings(remote_mappings)
        for raw_pattern, info in reverse_remote.items():
            # 跳过空的原始模式
            if not raw_pattern or raw_pattern.isspace():
                continue
                
            normalized_pattern = re.sub(r'\s+', ' ', raw_pattern.strip()).lower()
            
            # 精确匹配（必须完全一致）
            if normalized_name == normalized_pattern:
                logger.debug(f"从远程映射找到精确匹配: {raw_pattern} -> {info['standard_name']}")
                return info
                
    except Exception as e:
        logger.error(f"远程映射查找失败: {e}")
        
    # 检查标准名称映射(如果输入的是标准名称)
    try:
        for standard_name, info in combined_mappings.items():
            # 跳过空的标准名称
            if not standard_name or standard_name.isspace():
                continue
                
            normalized_standard = re.sub(r'\s+', ' ', standard_name.strip()).lower()
            
            # 精确匹配（必须完全一致）
            if normalized_name == normalized_standard:
                logger.debug(f"从标准名称找到精确匹配: {standard_name}")
                return {
                    'standard_name': standard_name,
                    'logo_url': info['logo_url']
                }
                
    except Exception as e:
        logger.error(f"标准名称查找失败: {e}")
        
    # 都没有匹配则返回原始名称
    logger.debug(f"没有找到匹配的映射，返回原始名称: {raw_name}")
    return {'standard_name': raw_name, 'logo_url': None}
