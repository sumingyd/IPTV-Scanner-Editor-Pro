import re
import uuid
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
        self.config = ConfigHandler()
        self.parser = PlaylistParser()
        self.converter = PlaylistConverter(EPGManager())

    def save_playlist(self, channels: List[Dict], path: str) -> bool:
        """保存播放列表到文件"""
        try:
            # 参数校验
            if not channels or not isinstance(channels, list):
                logger.error("无效的频道列表")
                return False
                
            path = Path(path).resolve()
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

    def _format_txt(self, channels: List[Dict]) -> str:
        """生成TXT格式内容"""
        lines = []
        current_group = None
        
        for chan in channels:
            # 确保group字段存在，默认值为"未分类"
            group = chan.get('group', '未分类')
            
            if group != current_group:
                current_group = group
                lines.append(f"#group={current_group}")
            
            line = (
                f"{chan['name']} "
                f"[{chan.get('width', 0)}x{chan.get('height', 0)}],"
                f"{chan['url']}"
            )
            lines.append(line)
        
        return '\n'.join(lines)
