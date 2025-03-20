import requests
from lxml import etree
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse
import hashlib
import time
from utils import setup_logger, ConfigHandler

logger = setup_logger('EPGManager')

class EPGManager:
    def __init__(self):
        self.config = ConfigHandler()
        self.epg_data: Dict[str, Dict] = {}
        self._name_index: Dict[str, List[str]] = {}  # 频道名称倒排索引
        self._init_epg_sources()
        
    def _init_epg_sources(self) -> None:
        """初始化EPG数据源配置"""
        self.epg_sources = {
            'main': self.config.config.get(
                'EPG', 
                'main_url',
                fallback='https://epg.pw/xmltv/epg_CN.xml'
            ),
            'backups': [
                url.strip() for url in 
                self.config.config.get(
                    'EPG',
                    'backup_urls',
                    fallback=','.join([
                        'https://example.com/backup1.xml',
                        'https://example.com/backup2.xml'
                    ])
                ).split(',')
                if url.strip()
            ],
            'cache_ttl': self.config.config.getint(
                'EPG', 
                'cache_ttl',
                fallback=3600
            )
        }

    def _download_epg(self, url: str) -> Optional[bytes]:
        """下载EPG数据并缓存"""
        try:
            # 检查缓存有效性
            cache_key = self._generate_cache_key(url)
            cached_data = self._load_cache(cache_key)
            if cached_data:
                return cached_data

            # 发起带重试的请求
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            resp = requests.get(
                url,
                headers=headers,
                timeout=15,
                allow_redirects=True,
                stream=True
            )
            resp.raise_for_status()

            # 保存缓存
            content = resp.content
            self._save_cache(cache_key, content)
            return content
        except requests.exceptions.RequestException as e:
            logger.error(f"EPG下载失败 [{url}]: {str(e)}")
        except Exception as e:
            logger.exception(f"未知下载错误: {str(e)}")
        return None

    def _parse_xmltv(self, xml_content: bytes) -> Dict[str, Dict]:
        """解析XMLTV格式数据"""
        try:
            root = etree.fromstring(xml_content)
            channels = {}
            
            # 解析频道信息
            for channel in root.xpath('//channel'):
                if not (chan_id := channel.get('id')):
                    continue
                
                # 获取频道名称（兼容多语言）
                names = [
                    elem.text 
                    for elem in channel.xpath('display-name')
                    if elem.text
                ]
                primary_name = names[0] if names else '未知频道'
                
                # 构建频道数据
                channels[chan_id] = {
                    'id': chan_id,
                    'names': names,
                    'icon': channel.xpath('icon/@src')[0] if channel.xpath('icon') else '',
                    'programmes': self._parse_programmes(chan_id, root)
                }
                
                # 构建名称索引
                for name in names:
                    self._name_index.setdefault(name.lower(), []).append(chan_id)
            
            return channels
        except etree.XMLSyntaxError as e:
            logger.error(f"XML解析错误: {str(e)}")
        except Exception as e:
            logger.exception(f"EPG解析异常: {str(e)}")
        return {}

    def _parse_programmes(self, chan_id: str, root: etree._Element) -> List[Dict]:
        """解析节目单数据"""
        programmes = []
        for prog in root.xpath(f'//programme[@channel="{chan_id}"]'):
            try:
                start = datetime.strptime(prog.get('start'), '%Y%m%d%H%M%S %z')
                stop = datetime.strptime(prog.get('stop'), '%Y%m%d%H%M%S %z')
                
                programmes.append({
                    'title': prog.xpath('title/text()')[0] if prog.xpath('title') else '',
                    'start': start,
                    'end': stop,
                    'duration': (stop - start).total_seconds(),
                    'description': prog.xpath('desc/text()')[0] if prog.xpath('desc') else '',
                    'category': prog.xpath('category/text()')[0] if prog.xpath('category') else '',
                })
            except Exception as e:
                logger.warning(f"节目单解析失败: {str(e)}")
        return programmes

    def refresh_epg(self) -> bool:
        """刷新EPG数据"""
        success = False
        content = None
        
        # 尝试主源
        if content := self._download_epg(self.epg_sources['main']):
            success = True
        else:
            # 尝试备用源
            for backup_url in self.epg_sources['backups']:
                if content := self._download_epg(backup_url):
                    success = True
                    break
        
        if content and (parsed_data := self._parse_xmltv(content)):
            self.epg_data = parsed_data
            logger.info(f"EPG更新成功 频道数: {len(self.epg_data)} 节目总数: {sum(len(c['programmes']) for c in self.epg_data.values())}")
            return True
        return False

    def match_channel_name(self, partial: str, max_results: int = 10) -> List[str]:
        """频道名称模糊匹配"""
        partial = partial.lower().strip()
        matches = []
        
        # 优先完全匹配
        if chan_ids := self._name_index.get(partial):
            matches.extend(chan_ids)
        
        # 模糊搜索
        for name, chan_ids in self._name_index.items():
            if partial in name and name not in matches:
                matches.extend(chan_ids)
        
        # 去重并获取频道信息
        unique_channels = {}
        for chan_id in list(dict.fromkeys(matches)):
            if chan := self.epg_data.get(chan_id):
                unique_channels[chan['names'][0]] = chan
        
        # 按名称长度排序
        return sorted(
            unique_channels.keys(),
            key=lambda x: (len(x), x)
        )[:max_results]

    # 缓存管理方法
    def _generate_cache_key(self, url: str) -> str:
        """生成缓存键"""
        parsed = urlparse(url)
        return hashlib.md5(f"{parsed.netloc}{parsed.path}".encode()).hexdigest()

    def _cache_file_path(self, key: str) -> str:
        """获取缓存文件路径"""
        return f"epg_cache/{key}.xml"

    def _load_cache(self, key: str) -> Optional[bytes]:
        """加载缓存数据"""
        try:
            cache_path = self._cache_file_path(key)
            with open(cache_path, 'rb') as f:
                if time.time() - f.stat().st_mtime < self.epg_sources['cache_ttl']:
                    return f.read()
        except FileNotFoundError:
            pass
        except Exception as e:
            logger.warning(f"缓存加载失败: {str(e)}")
        return None

    def _save_cache(self, key: str, data: bytes) -> None:
        """保存缓存数据"""
        try:
            cache_path = self._cache_file_path(key)
            Path(cache_path).parent.mkdir(parents=True, exist_ok=True)
            with open(cache_path, 'wb') as f:
                f.write(data)
        except Exception as e:
            logger.warning(f"缓存保存失败: {str(e)}")