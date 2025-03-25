import re
import sys
import uuid
import platform
import json
from pathlib import Path
from typing import List, Dict, Optional
from urllib.parse import urlparse
from utils import setup_logger, ConfigHandler
from epg_manager import EPGManager

logger = setup_logger('PlaylistIO')

class PlaylistParser:
    @staticmethod
    def parse_txt(content: str) -> List[Dict]:
        """解析增强型TXT格式
        
        支持格式：
        - 频道名称[宽x高],URL
        - 分组标记：#group=分组名称
        """
        channels = []
        current_group = "未分类"
        pattern = re.compile(
            r"^(?P<name>[^\[\]]+?)\s*"          # 频道名称
            r"\[(?P<width>\d+)[*x](?P<height>\d+)\]\s*,"  # 分辨率
            r"(?P<url>https?://\S+)$",          # URL
            re.IGNORECASE
        )
        
        for line in content.split('\n'):
            line = line.strip()
            if not line:
                continue
            
            # 处理分组标记
            if line.startswith("#group="):
                current_group = line.split("=", 1)[1].strip()
                continue
            
            # 跳过注释行
            if line.startswith("#"):
                continue
            
            if match := pattern.match(line):
                groups = match.groupdict()
                channels.append({
                    'name': groups['name'].strip(),
                    'width': int(groups['width']),
                    'height': int(groups['height']),
                    'url': groups['url'].strip(),
                    'group': current_group
                })
            else:
                logger.warning(f"无法解析的行: {line}")
        
        return channels

    @staticmethod
    def parse_m3u(content: str) -> List[Dict]:
        """解析增强型M3U格式
        
        支持属性：
        - tvg-id
        - tvg-name
        - tvg-logo
        - group-title
        - 其他扩展属性
        """
        channels = []
        current = {}
        
        for line in content.split('\n'):
            line = line.strip()
            if not line:
                continue
            
            if line.startswith("#EXTM3U"):
                continue  # 跳过头信息
            
            if line.startswith("#EXTINF"):
                # 解析EXTINF行
                current = {}
                meta_part = line.split(',', 1)
                if len(meta_part) > 1:
                    current['name'] = meta_part[1].strip()
                
                # 提取属性
                attrs = re.findall(r'([a-zA-Z-]+)="([^"]*)"', meta_part[0])
                current.update({k.lower(): v for k, v in attrs})
            
            elif line.startswith(('http://', 'https://', 'rtp://', 'rtsp://')):
                # 处理URL行
                current['url'] = line
                current.setdefault('group-title', '未分类')
                
                # 规范化字段
                channels.append({
                    'name': current.get('tvg-name') or current.get('name', '未知频道'),
                    'width': int(current.get('width', 0)),
                    'height': int(current.get('height', 0)),
                    'url': line,
                    'group': current.get('group-title', '未分类'),
                    'logo': current.get('tvg-logo', ''),
                    'id': current.get('tvg-id', str(uuid.uuid4()))
                })
                current = {}
        
        return channels

class PlaylistConverter:
    def __init__(self, epg_manager):
        self.epg = epg_manager
        self._cache = {}  # 频道信息缓存

    def _get_epg_info(self, channel_name: str) -> Dict:
        """获取EPG信息并缓存"""
        if channel_name not in self._cache:
            matches = self.epg.match_channel_name(channel_name)
            if matches:
                self._cache[channel_name] = self.epg.epg_data[matches[0]]
            else:
                self._cache[channel_name] = {
                    'id': str(uuid.uuid4()),
                    'logo': ''
                }
        return self._cache[channel_name]

    def txt_to_m3u(self, channels: List[Dict]) -> str:
        """转换到标准M3U格式"""
        header = (
            '#EXTM3U '
            'x-tvg-url="{epg_url}"\n'
            '#EXT-X-VERSION:3\n'
            '#EXT-X-INDEPENDENT-SEGMENTS\n'
        )
        
        entries = []
        for chan in channels:
            epg_info = self._get_epg_info(chan['name'])
            
            extinf = (
                f'#EXTINF:-1 '
                f'tvg-id="{epg_info["id"]}" '
                f'tvg-name="{chan["name"]}" '
                f'tvg-logo="{epg_info.get("logo", "")}" '
                f'group-title="{chan["group"]}",'
                f'{chan["name"]}\n'
                f'{chan["url"]}'
            )
            entries.append(extinf)
        
        return header.format(epg_url=self.epg.epg_sources['main']) + '\n'.join(entries)

class PlaylistHandler:
    def __init__(self):
        """播放列表处理器
        功能:
            1. 初始化配置和解析器
            2. 加载上次的扫描地址缓存
        """
        self.config = ConfigHandler()
        self.parser = PlaylistParser()
        self.converter = PlaylistConverter(EPGManager())
        self._load_scan_address_cache()

    def _load_scan_address_cache(self) -> None:
        """加载扫描地址缓存
        功能:
            1. 检查缓存文件是否存在
            2. 如果不存在则初始化空值并创建隐藏文件
            3. 如果存在则读取上次扫描地址
        """
        self.scan_address = ''  # 默认空值
        
        try:
            # 获取缓存文件路径(程序所在目录/.config_cache)
            cfg_path = Path(__file__).parent / ".config_cache"
            
            # 如果文件不存在则创建空文件并返回
            if not cfg_path.exists():
                # 确保父目录存在
                cfg_path.parent.mkdir(parents=True, exist_ok=True)
                # 创建空JSON文件
                with open(cfg_path, 'w', encoding='utf-8') as f:
                    json.dump({'scan_address': ''}, f)
                # 设置文件隐藏属性(仅Windows)
                if platform.system() == 'Windows':
                    import ctypes
                    ctypes.windll.kernel32.SetFileAttributesW(str(cfg_path), 2)
                return
                
            # 读取JSON格式缓存
            with open(cfg_path, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
                self.scan_address = cache_data.get('scan_address', '')
                
            # 设置文件隐藏属性(仅Windows)
            if platform.system() == 'Windows':
                import ctypes
                ctypes.windll.kernel32.SetFileAttributesW(str(cfg_path), 2)
            
        except Exception as e:
            logger.error(f"加载扫描地址缓存失败: {str(e)}")
            # 确保scan_address为空字符串
            self.scan_address = ''

    def _save_scan_address_cache(self, address: str) -> None:
        """保存扫描地址到缓存
        参数:
            address: 要保存的扫描地址
        功能:
            1. 验证地址有效性
            2. 更新JSON缓存文件
            3. 设置文件隐藏属性
        """
        if not isinstance(address, str):
            return
            
        try:
            # 获取缓存文件路径(程序所在目录/.config_cache)
            cfg_path = Path(__file__).parent / ".config_cache"
            
            # 确保父目录存在
            cfg_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 读取现有缓存或创建新缓存
            cache_data = {'scan_address': address}
            if cfg_path.exists():
                try:
                    with open(cfg_path, 'r', encoding='utf-8') as f:
                        cache_data = json.load(f)
                        cache_data['scan_address'] = address
                except json.JSONDecodeError:
                    # 如果文件损坏则创建新缓存
                    cache_data = {'scan_address': address}
            
            # 使用临时文件确保原子性写入
            temp_path = cfg_path.with_suffix('.tmp')
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            
            # 原子性替换文件
            if platform.system() == 'Windows':
                # Windows需要先删除目标文件
                if cfg_path.exists():
                    cfg_path.unlink()
            temp_path.replace(cfg_path)
                
            # 设置文件隐藏属性(仅Windows)
            if platform.system() == 'Windows':
                import ctypes
                ctypes.windll.kernel32.SetFileAttributesW(str(cfg_path), 2)
            
        except Exception as e:
            logger.error(f"保存扫描地址缓存失败: {str(e)}")

    def save_playlist(self, channels: List[Dict], path: str) -> bool:
        """保存播放列表到文件
        参数:
            channels: 频道列表
            path: 保存路径
        返回:
            bool: 是否保存成功
        """
        try:
            # 参数校验
            if not channels or not isinstance(channels, list):
                logger.error("无效的频道列表")
                return False
                
            # 处理打包环境下的路径问题
            if getattr(sys, 'frozen', False):
                # 打包成exe后的处理
                path = Path(path).absolute()
            else:
                # 正常Python环境处理
                path = Path(path).resolve()
                
            # 确保目录存在
            path.parent.mkdir(parents=True, exist_ok=True)
            
            # 生成内容
            content = self._generate_content(path.suffix, channels)
            if not content:
                logger.error("生成内容失败")
                return False
                
            # 写入文件
            with open(path, 'w', encoding='utf-8', newline='\n') as f:
                f.write(content)
            
            logger.info(f"成功保存播放列表到: {path}")
            return True
        except PermissionError:
            logger.error("文件写入权限被拒绝")
        except ValueError as e:
            logger.error(f"不支持的格式: {e}")
        except Exception as e:
            logger.exception(f"保存播放列表失败: {e}")
        return False

    def _generate_content(self, ext: str, channels: List[Dict]) -> str:
        """生成文件内容"""
        ext = ext.lower()
        if ext == '.txt':
            return self._format_txt(channels)
        elif ext in ('.m3u', '.m3u8'):
            return self.converter.txt_to_m3u(channels)
        else:
            raise ValueError(f"不支持的格式: {ext}")

    def update_scan_address(self, address: str) -> None:
        """更新扫描地址并保存到缓存
        参数:
            address: 扫描地址字符串
        """
        if not address:
            return
        self.scan_address = address
        self._save_scan_address_cache(address)

    def get_scan_address(self) -> str:
        """获取缓存的扫描地址
        返回:
            str: 上次使用的扫描地址
        """
        return self.scan_address

    def _format_txt(self, channels: List[Dict]) -> str:
        """生成增强型TXT格式内容，包含所有支持的参数
        参数:
            channels: 频道列表
        返回:
            str: 格式化后的文本内容
        """
        lines = []
        current_group = None
        
        for chan in channels:
            # 确保group字段存在，默认值为"未分类"
            group = chan.get('group', '未分类')
            
            if group != current_group:
                current_group = group
                lines.append(f"#group={current_group}")
            
            # 获取EPG信息
            epg_info = self.converter._get_epg_info(chan['name'])
            
            # 构建完整参数行
            line = (
                f"{chan['name']} "
                f"[{chan.get('width', 0)}x{chan.get('height', 0)}],"
                f"{chan['url']} "
                f"#id={epg_info['id']} "
                f"#logo={epg_info.get('logo', '')} "
                f"#tvg-name={chan['name']} "
                f"#tvg-id={epg_info['id']} "
                f"#group-title={group}"
            )
            lines.append(line)
        
        return '\n'.join(lines)
