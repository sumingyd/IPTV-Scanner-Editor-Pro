import requests
from typing import Dict
import types
from log_manager import LogManager

# 默认远程URL
DEFAULT_REMOTE_URL = "https://raw.githubusercontent.com/sumingyd/IPTV-Scanner-Editor-Pro/main/channel_mappings.py"

def load_mappings() -> Dict[str, dict]:
    """加载映射规则，从远程获取"""
    logger = LogManager()
    try:
        from config_manager import ConfigManager
        config = ConfigManager()
        try:
            remote_url = config.get('channel_mappings', 'remote_url', DEFAULT_REMOTE_URL)
        except AttributeError:
            # 兼容旧版本ConfigManager
            remote_url = DEFAULT_REMOTE_URL
        
        # 从远程加载.py文件
        response = requests.get(remote_url, timeout=10)
        response.raise_for_status()
        
        # 创建临时模块来执行远程代码
        remote_module = types.ModuleType("remote_channel_mappings")
        exec(response.text, remote_module.__dict__)
        
        # 提取映射数据
        return {
            'RESOLUTION_SUFFIXES': getattr(remote_module, 'RESOLUTION_SUFFIXES', []),
            'CITY_ABBREVIATIONS': getattr(remote_module, 'CITY_ABBREVIATIONS', {}),
            'SPECIAL_MAPPINGS': getattr(remote_module, 'SPECIAL_MAPPINGS', {})
        }
    except Exception as e:
        logger.error(f"加载远程映射失败: {e}, 使用内置默认值")
        return {
            'RESOLUTION_SUFFIXES': ['SD', 'HD', 'FHD', '4K', '8K'],
            'CITY_ABBREVIATIONS': {
                'XM': '厦门', 'BJ': '北京', 'SH': '上海',
                'GZ': '广州', 'SZ': '深圳', 'TJ': '天津',
                'CQ': '重庆', 'CD': '成都', 'NJ': '南京',
                'HZ': '杭州', 'WH': '武汉'
            },
            'SPECIAL_MAPPINGS': {
                # 频道名映射
                'XMSD': '厦门卫视', 'XMWS': '厦门卫视',
                'CCTV1': 'CCTV-1综合', 'CCTV2': 'CCTV-2财经',
                
                # URL域名映射
                'example.com': '示例电视台',
                'live.tv': '直播电视台',
                'iptv.provider': 'IPTV提供商频道'
            }
        }

# 导出映射规则
mappings = load_mappings()
RESOLUTION_SUFFIXES = mappings.get('RESOLUTION_SUFFIXES', [])
CITY_ABBREVIATIONS = mappings.get('CITY_ABBREVIATIONS', {})
SPECIAL_MAPPINGS = mappings.get('SPECIAL_MAPPINGS', {})
