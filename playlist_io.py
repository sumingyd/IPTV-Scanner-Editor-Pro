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
            # 确保必要字段存在
            if not all(k in chan for k in ['name', 'url']):
                logger.warning(f"跳过无效频道数据: {chan}")
                continue
                
            # 设置默认值
            chan.setdefault('group', '未分类')
            
            try:
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
            except Exception as e:
                logger.error(f"生成M3U条目失败: {str(e)}")
                continue
        
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
            1. 使用ConfigHandler读取配置
            2. 从.iptv_manager.ini获取扫描地址
        """
        try:
            self.scan_address = self.config.config['Scanner'].get('scan_address', '')
        except Exception as e:
            logger.error(f"加载扫描地址失败: {str(e)}")
            self.scan_address = ''

    def _save_scan_address_cache(self, address: str) -> None:
        """保存扫描地址到配置文件
        参数:
            address: 要保存的扫描地址
        功能:
            1. 验证地址有效性
            2. 更新.iptv_manager.ini配置
        """
        if not isinstance(address, str):
            return
            
        try:
            if not self.config.config.has_section('Scanner'):
                self.config.config.add_section('Scanner')
            self.config.config['Scanner']['scan_address'] = address
            self.config.save_prefs()
        except Exception as e:
            logger.error(f"保存扫描地址失败: {str(e)}")

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
            try:
                if getattr(sys, 'frozen', False):
                    # 打包成exe后的处理
                    path = Path(path).absolute()
                else:
                    # 正常Python环境处理
                    path = Path(path).resolve()
                
                # 确保目录存在
                path.parent.mkdir(parents=True, exist_ok=True)
                
                # 记录完整路径用于调试
                logger.debug(f"尝试保存到路径: {str(path)}")
            except Exception as e:
                logger.error(f"路径处理失败: {str(e)}")
                raise
            
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
        """生成简化TXT格式内容
        参数:
            channels: 频道列表
        返回:
            str: 只包含频道名称、分辨率和URL的文本内容
        """
        lines = []
        current_group = None
        
        for chan in channels:
            # 确保必要字段存在
            if not all(k in chan for k in ['name', 'url']):
                logger.warning(f"跳过无效频道数据: {chan}")
                continue
                
            # 设置默认值
            chan.setdefault('group', '未分类')
            chan.setdefault('width', 0)
            chan.setdefault('height', 0)
            
            # 处理分组标记
            group = chan['group']
            if group != current_group:
                current_group = group
                lines.append(f"#group={current_group}")
            
            # 构建简化行(只保留名称、分辨率和URL)
            line = (
                f"{chan['name']} "
                f"[{chan['width']}x{chan['height']}],"
                f"{chan['url']}"
            )
            lines.append(line)
        
        return '\n'.join(lines)
