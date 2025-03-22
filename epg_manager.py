import requests
from lxml import etree
from datetime import datetime, timedelta
import re
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse
import hashlib
import time
from pathlib import Path
from utils import setup_logger, ConfigHandler

logger = setup_logger('EPGManager')

class EPGManager:
    def __init__(self):
        self.config = ConfigHandler()
        self.epg_data: Dict[str, Dict] = {}
        self._name_index: Dict[str, List[str]] = {}  # 频道名称倒排索引
        self._init_epg_sources()

    def load_cached_epg(self, progress_callback: Optional[callable] = None) -> bool:
        """从缓存加载 EPG 数据"""
        cache_dir = Path(__file__).parent / "epg_cache"
        if not cache_dir.exists():
            cache_dir.mkdir(parents=True, exist_ok=True)
            if progress_callback:
                progress_callback("缓存目录不存在，已创建")
            return False

        # 只加载最新的缓存文件
        cache_files = sorted(cache_dir.glob("*.xml"), key=lambda f: f.stat().st_mtime, reverse=True)
        if not cache_files:
            if progress_callback:
                progress_callback("未找到缓存文件")
            return False

        latest_cache = cache_files[0]
        try:
            with open(latest_cache, "rb") as f:
                content = f.read()
            if parsed_data := self._parse_xmltv(content):
                self.epg_data = parsed_data
                if progress_callback:
                    progress_callback(f"从缓存加载 EPG 数据: {latest_cache.name}")
                logger.info(f"从缓存加载 EPG 数据: {latest_cache.name}")
                logger.info(f"频道数: {len(self.epg_data)} 节目总数: {sum(len(c['programmes']) for c in self.epg_data.values())}")
                return True
        except Exception as e:
            if progress_callback:
                progress_callback(f"加载缓存文件失败: {str(e)}")
            logger.warning(f"加载缓存文件失败: {str(e)}")
        return False

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

    async def _download_epg(self, url: str) -> Optional[bytes]:
        """下载EPG数据并缓存"""
        try:
            # 检查缓存有效性
            cache_key = self._generate_cache_key(url)
            cached_data = self._load_cache(cache_key)
            if cached_data:
                logger.debug(f"从缓存加载: {cache_key}")
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
            logger.debug(f"缓存已保存: {cache_key}")
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
            except Exception:
                # 忽略解析失败的节目单
                continue
        return programmes

    async def refresh_epg(self, progress_callback: Optional[callable] = None) -> bool:
        """从网络更新 EPG 数据"""
        try:
            if progress_callback:
                progress_callback("正在下载 EPG 数据...")
            content = await self._download_epg(self.epg_sources['main'])
            if not content:
                # 尝试备用源
                for backup_url in self.epg_sources['backups']:
                    if progress_callback:
                        progress_callback(f"正在尝试备用源: {backup_url}")
                    content = await self._download_epg(backup_url)
                    if content:
                        break

            if content:
                if progress_callback:
                    progress_callback("正在解析 EPG 数据...")
                parsed_data = self._parse_xmltv(content)
                if parsed_data:
                    self.epg_data = parsed_data
                    if progress_callback:
                        progress_callback("EPG 数据更新成功")
                    logger.info(f"EPG更新成功 频道数: {len(self.epg_data)} 节目总数: {sum(len(c['programmes']) for c in self.epg_data.values())}")
                    return True
            return False
        except Exception as e:
            if progress_callback:
                progress_callback(f"EPG 更新失败: {str(e)}")
            logger.error(f"EPG更新失败: {str(e)}")
            return False

    def match_channel_name(self, partial: str, max_results: int = 10) -> List[str]:
        """频道名称模糊匹配（带异常保护版）"""
        try:
            # 输入验证
            if not partial or not isinstance(partial, str):
                return []
                
            partial = partial.lower().strip()
            matches = []

            # 保护性访问索引数据
            if not hasattr(self, '_name_index') or not isinstance(self._name_index, dict):
                logger.error("频道名称索引未正确初始化")
                return []

            # 将输入拆分为字符（带空值保护）
            partial_chars = set(partial) if partial else set()

            # 遍历索引（带类型检查）
            for name, chan_ids in self._name_index.items():
                if not isinstance(name, str) or not isinstance(chan_ids, list):
                    continue
                    
                name_lower = name.lower()
                if partial_chars.issubset(set(name_lower)):
                    # 过滤无效频道ID
                    matches.extend([cid for cid in chan_ids if isinstance(cid, (str, int))])

            # 保护性访问EPG数据
            if not hasattr(self, 'epg_data') or not isinstance(self.epg_data, dict):
                logger.error("EPG数据未正确加载")
                return []

            unique_channels = {}
            for chan_id in list(dict.fromkeys(matches)):
                # 类型安全访问
                chan = self.epg_data.get(str(chan_id)) if isinstance(chan_id, (str, int)) else None
                
                if chan and isinstance(chan, dict):
                    chan_names = chan.get('names', [])
                    # 过滤非列表类型的名称数据
                    if not isinstance(chan_names, list):
                        continue
                        
                    for chan_name in chan_names:
                        if isinstance(chan_name, str) and partial_chars.issubset(set(chan_name.lower())):
                            unique_channels[chan_name] = chan

            # 安全排序
            try:
                return sorted(
                    unique_channels.keys(),
                    key=lambda x: (
                        -sum(1 for char in partial_chars if char in x.lower()),
                        len(x),
                        x
                    )
                )[:max_results]
            except Exception as sort_error:
                logger.error(f"排序失败: {str(sort_error)}")
                return list(unique_channels.keys())[:max_results]

        except Exception as e:
            logger.error(f"频道匹配异常: {str(e)}", exc_info=True)
            return []

    # 缓存管理方法
    def _generate_cache_key(self, url: str) -> str:
        """生成缓存键"""
        parsed = urlparse(url)
        return hashlib.md5(f"{parsed.netloc}{parsed.path}".encode()).hexdigest()

    def _save_cache(self, key: str, data: bytes) -> None:
        """保存缓存数据"""
        try:
            cache_path = self._cache_file_path(key)
            Path(cache_path).parent.mkdir(parents=True, exist_ok=True)  # 创建缓存目录
            with open(cache_path, 'wb') as f:
                f.write(data)
            logger.debug(f"缓存已保存: {cache_path}")
        except Exception as e:
            logger.warning(f"缓存保存失败: {str(e)}")

    def _cache_file_path(self, key: str) -> str:
        """获取缓存文件路径，确保保存到程序目录下的 epg_cache 文件夹"""
        cache_dir = Path(__file__).parent / "epg_cache"
        cache_dir.mkdir(parents=True, exist_ok=True)  # 创建缓存目录
        return str(cache_dir / f"{key}.xml")

    def _load_cache(self, key: str) -> Optional[bytes]:
        """加载缓存数据"""
        try:
            cache_path = self._cache_file_path(key)
            if not Path(cache_path).exists():
                return None

            with open(cache_path, 'rb') as f:
                return f.read()
        except Exception:
            return None

