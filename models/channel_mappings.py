import requests
import os
import re
import json
import hashlib
import time
import threading
from typing import Dict, List
from core.log_manager import global_logger as logger

# 默认远程URL - 优先使用CSV格式，如果不存在则尝试TXT格式
DEFAULT_REMOTE_URL = "https://raw.githubusercontent.com/sumingyd/IPTV-Scanner-Editor-Pro/main/local_channel_mappings.csv"

# 本地缓存文件路径
CACHE_FILE = "channel_mappings_cache.json"
USER_MAPPINGS_FILE = "user_channel_mappings.json"
CHANNEL_FINGERPRINT_FILE = "channel_fingerprints.json"


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

                    # 新增字段
                    tvg_id = row.get('tvg_id', '').strip() if row.get('tvg_id') else None
                    tvg_chno = row.get('tvg_chno', '').strip() if row.get('tvg_chno') else None
                    tvg_shift = row.get('tvg_shift', '').strip() if row.get('tvg_shift') else None
                    catchup = row.get('catchup', '').strip() if row.get('catchup') else None
                    catchup_days = row.get('catchup_days', '').strip() if row.get('catchup_days') else None
                    catchup_source = row.get('catchup_source', '').strip() if row.get('catchup_source') else None

                    if standard_name:  # 确保标准名称不为空
                        mappings[standard_name] = {
                            'raw_names': raw_names,
                            'logo_url': logo_url if logo_url and logo_url.lower() not in ['', 'none', 'null'] else None,
                            'group_name': group_name if group_name and group_name.lower() not in ['', 'none', 'null'] else None,
                            'tvg_id': tvg_id if tvg_id and tvg_id.lower() not in ['', 'none', 'null'] else None,
                            'tvg_chno': tvg_chno if tvg_chno and tvg_chno.lower() not in ['', 'none', 'null'] else None,
                            'tvg_shift': tvg_shift if tvg_shift and tvg_shift.lower() not in ['', 'none', 'null'] else None,
                            'catchup': catchup if catchup and catchup.lower() not in ['', 'none', 'null'] else None,
                            'catchup_days': catchup_days if catchup_days and catchup_days.lower() not in ['', 'none', 'null'] else None,
                            'catchup_source': catchup_source if catchup_source and catchup_source.lower() not in ['', 'none', 'null'] else None
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


def load_remote_mappings() -> Dict[str, dict]:
    """加载远程映射规则 - 简化版本，不重试，不阻塞"""
    try:
        # 尝试从core目录导入ConfigManager
        try:
            from core.config_manager import ConfigManager
            config = ConfigManager()
            try:
                remote_url = config.get('channel_mappings', 'remote_url', DEFAULT_REMOTE_URL)
            except AttributeError:
                remote_url = DEFAULT_REMOTE_URL
        except ImportError:
            # 如果core.config_manager导入失败，尝试直接导入config_manager（旧结构）
            try:
                from config_manager import ConfigManager
                config = ConfigManager()
                try:
                    remote_url = config.get('channel_mappings', 'remote_url', DEFAULT_REMOTE_URL)
                except AttributeError:
                    remote_url = DEFAULT_REMOTE_URL
            except ImportError:
                # 如果都失败，使用默认URL
                remote_url = DEFAULT_REMOTE_URL

        # 简化版本：只尝试一次，不重试
        try:
            # 先尝试CSV格式
            response = requests.get(remote_url, timeout=5, verify=False)  # 减少超时时间到5秒
            if response.status_code == 404:
                # 如果CSV格式不存在，尝试TXT格式（向后兼容）
                txt_url = remote_url.replace('.csv', '.txt')
                logger.info(f"CSV映射文件不存在，尝试TXT格式: {txt_url}")
                response = requests.get(txt_url, timeout=5, verify=False)

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

        except Exception as e:
            # 只记录一次错误，不重试
            logger.warning(f"加载远程映射失败: {e}, 使用本地缓存")
            return {}

    except Exception as e:
        logger.warning(f"加载远程映射失败: {e}, 使用本地映射")
        return {}


class ChannelMappingManager:
    """频道映射管理器，包含本地缓存、频道指纹、智能学习和用户自定义映射功能"""

    def __init__(self):
        self.logger = logger
        self.cache_file = CACHE_FILE
        self.user_mappings_file = USER_MAPPINGS_FILE
        self.fingerprint_file = CHANNEL_FINGERPRINT_FILE
        self.cache_lock = threading.Lock()
        self.user_mappings_lock = threading.Lock()
        self.fingerprint_lock = threading.Lock()

        # 加载各种映射数据
        self.remote_mappings = self._load_cached_mappings()
        self.user_mappings = self._load_user_mappings()
        self.channel_fingerprints = self._load_channel_fingerprints()

        # 组合所有映射
        self.combined_mappings = self._combine_mappings()
        self.reverse_mappings = create_reverse_mappings(self.combined_mappings)

    def _load_cached_mappings(self) -> Dict[str, dict]:
        """加载缓存的远程映射规则"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 检查缓存是否过期（24小时）且不为空
                    mappings = data.get('mappings', {})
                    if time.time() - data.get('timestamp', 0) < 24 * 3600 and mappings:
                        self.logger.info(f"从缓存加载远程映射规则，共 {len(mappings)} 条映射")
                        return mappings
                    else:
                        self.logger.info("缓存已过期或为空，重新加载远程映射")
        except Exception as e:
            self.logger.error(f"加载缓存映射失败: {e}")

        # 缓存不存在、已过期或为空，重新加载远程映射
        return self._load_and_cache_remote_mappings()

    def _load_and_cache_remote_mappings(self) -> Dict[str, dict]:
        """加载远程映射并缓存到本地"""
        mappings = load_remote_mappings()

        # 缓存到本地文件
        try:
            with self.cache_lock:
                cache_data = {
                    'timestamp': time.time(),
                    'mappings': mappings
                }
                with open(self.cache_file, 'w', encoding='utf-8') as f:
                    json.dump(cache_data, f, ensure_ascii=False, indent=2)
                self.logger.info(f"远程映射已缓存到本地，共 {len(mappings)} 条映射")
        except Exception as e:
            self.logger.error(f"缓存远程映射失败: {e}")

        return mappings

    def _load_user_mappings(self) -> Dict[str, dict]:
        """加载用户自定义映射规则"""
        try:
            if os.path.exists(self.user_mappings_file):
                with open(self.user_mappings_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            self.logger.error(f"加载用户映射失败: {e}")
        return {}

    def _save_user_mappings(self):
        """保存用户自定义映射规则"""
        try:
            with self.user_mappings_lock:
                with open(self.user_mappings_file, 'w', encoding='utf-8') as f:
                    json.dump(self.user_mappings, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"保存用户映射失败: {e}")

    def _load_channel_fingerprints(self) -> Dict[str, dict]:
        """加载频道指纹数据"""
        try:
            if os.path.exists(self.fingerprint_file):
                with open(self.fingerprint_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            self.logger.error(f"加载频道指纹失败: {e}")
        return {}

    def _save_channel_fingerprints(self):
        """保存频道指纹数据"""
        try:
            with self.fingerprint_lock:
                with open(self.fingerprint_file, 'w', encoding='utf-8') as f:
                    json.dump(self.channel_fingerprints, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"保存频道指纹失败: {e}")

    def _combine_mappings(self) -> Dict[str, dict]:
        """组合远程映射和用户自定义映射（用户映射优先级更高）"""
        combined = self.remote_mappings.copy()
        combined.update(self.user_mappings)
        return combined

    def add_user_mapping(self, raw_name: str, standard_name: str, logo_url: str = None, group_name: str = None):
        """添加用户自定义映射"""
        if standard_name not in self.user_mappings:
            self.user_mappings[standard_name] = {
                'raw_names': [],
                'logo_url': logo_url,
                'group_name': group_name
            }

        if raw_name not in self.user_mappings[standard_name]['raw_names']:
            self.user_mappings[standard_name]['raw_names'].append(raw_name)

        # 更新组合映射和反向映射
        self.combined_mappings = self._combine_mappings()
        self.reverse_mappings = create_reverse_mappings(self.combined_mappings)

        # 保存用户映射
        self._save_user_mappings()

        self.logger.info(f"添加用户映射: {raw_name} -> {standard_name}")

    def remove_user_mapping(self, standard_name: str):
        """移除用户自定义映射"""
        if standard_name in self.user_mappings:
            del self.user_mappings[standard_name]
            self.combined_mappings = self._combine_mappings()
            self.reverse_mappings = create_reverse_mappings(self.combined_mappings)
            self._save_user_mappings()
            self.logger.info(f"移除用户映射: {standard_name}")

    def create_channel_fingerprint(self, url: str, channel_info: dict) -> str:
        """创建频道指纹"""
        # 使用URL和频道信息创建唯一指纹
        fingerprint_data = {
            'url': url,
            'service_name': channel_info.get('service_name', ''),
            'resolution': channel_info.get('resolution', ''),
            'codec': channel_info.get('codec', ''),
            'bitrate': channel_info.get('bitrate', '')
        }

        # 生成MD5哈希作为指纹
        fingerprint_str = json.dumps(fingerprint_data, sort_keys=True)
        return hashlib.md5(fingerprint_str.encode()).hexdigest()

    def learn_from_scan_result(self, url: str, raw_name: str, channel_info: dict, mapped_name: str):
        """从扫描结果中学习并完善映射规则"""
        fingerprint = self.create_channel_fingerprint(url, channel_info)

        # 记录指纹与映射关系
        if fingerprint not in self.channel_fingerprints:
            self.channel_fingerprints[fingerprint] = {
                'raw_name': raw_name,
                'mapped_name': mapped_name,
                'url': url,
                'last_seen': time.time(),
                'count': 1
            }
        else:
            self.channel_fingerprints[fingerprint]['count'] += 1
            self.channel_fingerprints[fingerprint]['last_seen'] = time.time()

        # 如果某个指纹频繁出现但映射不稳定，建议用户添加映射
        if self.channel_fingerprints[fingerprint]['count'] >= 3:
            current_mapped = self.channel_fingerprints[fingerprint]['mapped_name']
            if current_mapped != mapped_name:
                self.logger.warning(f"频道映射不稳定: {raw_name} -> {current_mapped} vs {mapped_name}")

        self._save_channel_fingerprints()

    def get_channel_info(self, raw_name: str, url: str = None, channel_info: dict = None) -> dict:
        """获取频道信息，支持智能学习和指纹匹配"""
        if not raw_name or raw_name.isspace():
            return {'standard_name': '', 'logo_url': None}

        # 标准化输入名称
        normalized_name = raw_name.strip().lower()

        if not normalized_name:
            return {'standard_name': raw_name, 'logo_url': None}

        # 1. 首先检查精确匹配
        result = self._get_exact_match(normalized_name)
        # 移除调试日志：精确匹配结果
        if result['standard_name'] != normalized_name:  # 如果找到了映射
            self.logger.info(f"找到映射: '{raw_name}' -> '{result['standard_name']}'")
            # 记录学习数据
            if url and channel_info:
                self.learn_from_scan_result(url, raw_name, channel_info, result['standard_name'])
            return result

        # 2. 如果没有精确匹配，尝试指纹匹配
        if url and channel_info:
            fingerprint = self.create_channel_fingerprint(url, channel_info)
            if fingerprint in self.channel_fingerprints:
                mapped_name = self.channel_fingerprints[fingerprint]['mapped_name']
                if mapped_name != raw_name:
                    self.logger.info(f"通过指纹匹配找到映射: {raw_name} -> {mapped_name}")
                    # 通过指纹匹配找到映射后，再次尝试获取完整的频道信息
                    fingerprint_result = self._get_exact_match(mapped_name.lower())
                    if fingerprint_result['standard_name'] != mapped_name:  # 如果找到了完整映射
                        return fingerprint_result
                    else:
                        # 如果没有找到完整映射，返回基本映射信息
                        return {'standard_name': mapped_name, 'logo_url': None}

            # 记录当前映射关系用于学习
            self.learn_from_scan_result(url, raw_name, channel_info, raw_name)

        # 3. 返回原始名称
        # 移除调试日志：没有找到匹配的映射
        return {'standard_name': raw_name, 'logo_url': None}

    def _get_exact_match(self, normalized_name: str) -> dict:
        """精确匹配映射规则"""
        # 首先检查反向映射（直接查找）
        try:
            # 直接检查反向映射字典中是否存在该名称
            if normalized_name in self.reverse_mappings:
                result = self.reverse_mappings[normalized_name]
                # 移除调试日志，整合到get_channel_info方法中
                return result
        except Exception as e:
            self.logger.error(f"反向映射查找失败: {e}")

        # 如果直接查找失败，尝试遍历反向映射（兼容旧逻辑）
        try:
            for raw_pattern, info in self.reverse_mappings.items():
                if not raw_pattern or raw_pattern.isspace():
                    continue
                normalized_pattern = re.sub(r'\s+', ' ', raw_pattern.strip()).lower()
                if normalized_name == normalized_pattern:
                    # 移除调试日志，整合到get_channel_info方法中
                    return info
        except Exception as e:
            self.logger.error(f"反向映射遍历查找失败: {e}")

        # 检查标准名称映射
        try:
            for standard_name, info in self.combined_mappings.items():
                if not standard_name or standard_name.isspace():
                    continue
                normalized_standard = re.sub(r'\s+', ' ', standard_name.strip()).lower()
                if normalized_name == normalized_standard:
                    result = {
                        'standard_name': standard_name,
                        'logo_url': info['logo_url'],
                        'group_name': info.get('group_name')
                    }
                    # 移除调试日志，整合到get_channel_info方法中
                    return result
        except Exception as e:
            self.logger.error(f"标准名称查找失败: {e}")

        # 移除调试日志
        return {'standard_name': normalized_name, 'logo_url': None}

    def get_mapping_suggestions(self, raw_name: str) -> List[str]:
        """获取映射建议"""
        suggestions = []

        # 基于指纹历史记录提供建议
        for fingerprint, data in self.channel_fingerprints.items():
            if data['raw_name'] == raw_name and data['mapped_name'] != raw_name:
                suggestions.append(data['mapped_name'])

        # 去重并返回
        return list(set(suggestions))

    def refresh_cache(self):
        """刷新远程映射缓存"""
        self.remote_mappings = self._load_and_cache_remote_mappings()
        self.combined_mappings = self._combine_mappings()
        self.reverse_mappings = create_reverse_mappings(self.combined_mappings)
        self.logger.info("远程映射缓存已刷新")


# 创建全局映射管理器实例（延迟加载）
_mapping_manager_instance = None


def get_mapping_manager():
    """获取映射管理器实例（延迟加载）"""
    global _mapping_manager_instance
    if _mapping_manager_instance is None:
        _mapping_manager_instance = ChannelMappingManager()
    return _mapping_manager_instance


class MappingManagerProxy:
    """映射管理器代理类，提供延迟加载功能"""

    def __init__(self):
        self._manager = None

    def _get_manager(self):
        if self._manager is None:
            self._manager = get_mapping_manager()
        return self._manager

    def __getattr__(self, name):
        # 当访问任何属性时，先获取实际的映射管理器实例
        return getattr(self._get_manager(), name)

    def __call__(self, *args, **kwargs):
        # 如果被当作函数调用，返回管理器实例
        return self._get_manager()


# 创建代理实例
mapping_manager = MappingManagerProxy()


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
    except (ValueError, IndexError) as e:
        logger.debug(f"使用shlex解析映射行失败，回退到原始方法: {e}")
        # 如果解析失败，回退到原始方法
        raw_names = [name.strip('"\' ') for name in parts[1].split()]
    except Exception as e:
        logger.warning(f"解析映射行时发生意外错误: {e}")
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


def get_channel_info(raw_name: str) -> dict:
    """获取频道信息(标准名称、logo地址和分组名)"""
    # 使用新的映射管理器
    return mapping_manager.get_channel_info(raw_name)


# 兼容性函数，保持原有接口
def get_channel_info_legacy(raw_name: str) -> dict:
    """旧版获取频道信息函数，保持向后兼容"""
    return mapping_manager.get_channel_info(raw_name)
