from PyQt6 import QtWidgets
import requests
from lxml import etree
from datetime import datetime, timedelta
import re
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse
import hashlib
import time
import sys
from pathlib import Path
from utils import setup_logger, ConfigHandler

logger = setup_logger('EPGManager')

# EPG管理
class EPGManager:
    # 初始化
    def __init__(self, parent=None):
        self.config = ConfigHandler()
        self.epg_data: Dict[str, Dict] = {}
        self._name_index: Dict[str, List[str]] = {}  # 频道名称倒排索引
        self.cache_manager = CacheManager(Path(__file__).parent / "epg-xml")  # 初始化缓存管理器
        self.main_url = ''
        self.backup_urls = []
        self._init_epg_sources()
        
        # EPG UI组件
        self.parent = parent
        self.epg_completer = None
        self.epg_match_label = None
        self._init_epg_ui()

    # 初始化EPG UI组件
    def _init_epg_ui(self) -> None:
        """初始化EPG UI组件"""
        if not self.parent:
            return
            
        from PyQt6.QtCore import Qt
        from PyQt6 import QtWidgets
        
        # 初始化自动补全器
        self.epg_completer = QtWidgets.QCompleter()
        self.epg_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.epg_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.epg_completer.setCompletionMode(QtWidgets.QCompleter.CompletionMode.PopupCompletion)
        self.epg_completer.setMaxVisibleItems(10)
        self.epg_completer.popup().setItemDelegate(QtWidgets.QStyledItemDelegate())
        self.epg_completer.popup().setAttribute(Qt.WidgetAttribute.WA_InputMethodEnabled, False)
        self.epg_completer.popup().setInputMethodHints(Qt.InputMethodHint.ImhNone)
        
        # 初始化EPG匹配状态标签
        self.epg_match_label = QtWidgets.QLabel("EPG状态: 未匹配")
        self.epg_match_label.setStyleSheet("font-weight: bold;")

    # 初始化EPG数据源配置
    def _init_epg_sources(self) -> None:
        """初始化EPG数据源配置"""
        self.main_url = self.config.config.get('EPG', 'main_url', fallback='')
        self.backup_urls = [
            url.strip() 
            for url in self.config.config.get('EPG', 'backup_urls', fallback='').split(',') 
            if url.strip()
        ]
        
        self.epg_sources = {
            'main': self.main_url,
            'backups': self.backup_urls,
            'cache_ttl': self.config.config.getint('EPG', 'cache_ttl', fallback=3600)
        }

    # 保存EPG数据源配置
    def save_epg_sources(self, main_url: str, backup_urls: str, cache_ttl: int) -> None:
        """保存EPG数据源配置"""
        self.main_url = main_url
        self.backup_urls = [url.strip() for url in backup_urls.split(',') if url.strip()]
        self.epg_sources = {
            'main': self.main_url,
            'backups': self.backup_urls,
            'cache_ttl': cache_ttl
        }

    # 下载 EPG 数据并缓存
    async def _download_epg(self, url: str) -> Optional[bytes]:
        """下载 EPG 数据并缓存"""
        try:
            # 检查缓存有效性
            cache_key = self.cache_manager.generate_cache_key(url)
            cached_data = self.cache_manager.load_cache(cache_key)
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
            self.cache_manager.save_cache(cache_key, content)
            return content
        except requests.exceptions.RequestException as e:
            logger.error(f"EPG 下载失败 [{url}]: {str(e)}")
        except Exception as e:
            logger.exception(f"未知下载错误: {str(e)}")
        return None

    # 解析XMLTV格式数据
    def _parse_xmltv(self, xml_content: bytes) -> Dict[str, Dict]:
        """解析XMLTV格式数据"""
        try:
            root = etree.fromstring(xml_content)
            channels = {}
            
            for channel in root.xpath('//channel'):
                if not (chan_id := channel.get('id')):
                    continue
                
                # 获取频道信息
                names = [
                    elem.text 
                    for elem in channel.xpath('display-name')
                    if elem.text
                ]
                
                # 解析节目单
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
                        continue
                
                # 构建频道数据
                channels[chan_id] = {
                    'id': chan_id,
                    'names': names,
                    'icon': channel.xpath('icon/@src')[0] if channel.xpath('icon') else '',
                    'programmes': programmes
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

    # 频道名称模糊匹配
    def match_channel_name(self, partial: str, max_results: int = 10) -> List[str]:
        """频道名称模糊匹配"""
        if not partial or not isinstance(partial, str):
            return []
            
        partial = partial.lower().strip()
        if not hasattr(self, '_name_index'):
            return []
            
        matches = []
        for name, chan_ids in self._name_index.items():
            if partial in name.lower():
                matches.extend(chan_ids)
                
        # 去重并获取频道名称
        unique_names = set()
        for chan_id in dict.fromkeys(matches):
            if chan := self.epg_data.get(str(chan_id)):
                for name in chan.get('names', []):
                    if partial in name.lower():
                        unique_names.add(name)
                        
        return sorted(unique_names, key=len)[:max_results]

    #检查频道名称是否匹配EPG数据
    def is_channel_matched(self, channel_name: str) -> bool:
        """检查频道名称是否匹配EPG数据"""
        if not channel_name or not isinstance(channel_name, str):
            return False
        return channel_name.lower() in self._name_index

    # 获取EPG匹配状态
    def get_epg_match_status(self, channel_name: str) -> Tuple[bool, str]:
        """获取EPG匹配状态和消息"""
        if not channel_name or not isinstance(channel_name, str):
            return False, "未匹配"
        is_matched = channel_name.lower() in self._name_index
        return is_matched, "✓ 已匹配" if is_matched else "⚠ 未匹配"

    # 更新自动补全模型
    def update_epg_completer(self, text: str) -> List[str]:
        """根据输入文本更新自动补全模型"""
        if not text or not isinstance(text, str):
            return []
            
        matches = self.match_channel_name(text)
        if self.epg_completer:
            from PyQt6 import QtCore, QtWidgets
            model = QtWidgets.QStringListModel(matches)
            self.epg_completer.setModel(model)
            
        if self.epg_match_label:
            is_matched, status = self.get_epg_match_status(text)
            self.epg_match_label.setText(f"EPG状态: {status}")
            color = "green" if is_matched else "red"
            self.epg_match_label.setStyleSheet(f"color: {color}; font-weight: bold;")
            
        return matches

    # 显示EPG管理对话框
    def show_epg_manager_dialog(self, parent=None) -> None:
        """显示EPG管理对话框"""
        dialog = QtWidgets.QDialog(parent)
        dialog.setWindowTitle("EPG 管理")
        layout = QtWidgets.QVBoxLayout()

        # 主源设置
        main_source_label = QtWidgets.QLabel("主源 URL：")
        main_source_input = QtWidgets.QLineEdit()
        main_source_input.setText(self.main_url)

        # 备用源设置
        backup_sources_label = QtWidgets.QLabel("备用源 URL（多个用逗号分隔）：")
        backup_sources_input = QtWidgets.QLineEdit()
        backup_sources_input.setText(','.join(self.backup_urls))

        # 缓存TTL设置
        ttl_label = QtWidgets.QLabel("缓存有效期（秒）：")
        ttl_input = QtWidgets.QSpinBox()
        ttl_input.setRange(60, 86400)
        ttl_input.setValue(self.epg_sources['cache_ttl'])

        # 保存按钮
        save_btn = QtWidgets.QPushButton("保存")
        save_btn.clicked.connect(lambda: self._save_epg_settings(
            main_source_input.text(),
            backup_sources_input.text(),
            ttl_input.value(),
            dialog
        ))

        layout.addWidget(main_source_label)
        layout.addWidget(main_source_input)
        layout.addWidget(backup_sources_label)
        layout.addWidget(backup_sources_input)
        layout.addWidget(ttl_label)
        layout.addWidget(ttl_input)
        layout.addWidget(save_btn)

        dialog.setLayout(layout)
        dialog.exec()

    # 保存EPG数据到本地文件
    def save_local_epg(self) -> bool:
        """保存EPG数据到本地文件"""
        try:
            local_path = self.cache_manager.cache_dir / "local_epg.xml"
            root = etree.Element("tv")
            
            # 添加所有频道
            for chan_id, channel in self.epg_data.items():
                chan_elem = etree.SubElement(root, "channel", id=chan_id)
                for name in channel.get('names', []):
                    etree.SubElement(chan_elem, "display-name").text = name
                if icon := channel.get('icon'):
                    etree.SubElement(chan_elem, "icon", src=icon)
                
                # 添加节目单
                for prog in channel.get('programmes', []):
                    prog_elem = etree.SubElement(
                        root, 
                        "programme", 
                        channel=chan_id,
                        start=prog['start'].strftime('%Y%m%d%H%M%S %z'),
                        stop=prog['end'].strftime('%Y%m%d%H%M%S %z')
                    )
                    etree.SubElement(prog_elem, "title").text = prog['title']
                    if desc := prog.get('description'):
                        etree.SubElement(prog_elem, "desc").text = desc
                    if cat := prog.get('category'):
                        etree.SubElement(prog_elem, "category").text = cat
            
            # 写入文件
            tree = etree.ElementTree(root)
            tree.write(local_path, encoding='utf-8', xml_declaration=True, pretty_print=True)
            logger.info(f"EPG数据已保存到本地文件: {local_path}")
            return True
        except Exception as e:
            logger.error(f"保存本地EPG文件失败: {str(e)}")
            return False

    # 智能加载EPG数据(优先缓存，自动更新)
    async def load_epg(self, progress_callback: Optional[callable] = None) -> bool:
        """智能加载EPG数据(优先缓存，自动更新)"""
        try:
            # 首先尝试从缓存加载
            if latest_cache := self.cache_manager.get_latest_cache():
                try:
                    with open(latest_cache, "rb") as f:
                        content = f.read()
                    if parsed_data := self._parse_xmltv(content):
                        self.epg_data = parsed_data
                        if progress_callback:
                            progress_callback(f"从缓存加载 EPG 数据: {latest_cache.name}")
                        return True
                    else:
                        if progress_callback:
                            progress_callback("缓存文件解析失败，尝试更新...")
                except Exception as e:
                    if progress_callback:
                        progress_callback(f"加载缓存文件失败: {str(e)}，尝试更新...")
            
            # 检查是否设置了EPG源
            if not self.epg_sources['main'] and not self.epg_sources['backups']:
                if progress_callback:
                    progress_callback("错误: 未设置EPG数据源地址")
                return False
            
            if progress_callback:
                progress_callback("正在下载 EPG 数据...")
            
            content = None
            if self.epg_sources['main']:
                content = await self._download_epg(self.epg_sources['main'])
            
            if not content and self.epg_sources['backups']:
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
                    # 更新成功后保存到本地文件
                    self.save_local_epg()
                    return True
                else:
                    if progress_callback:
                        progress_callback("EPG 数据解析失败")
            else:
                if progress_callback:
                    progress_callback("所有EPG源下载失败")
            return False
        except Exception as e:
            if progress_callback:
                progress_callback(f"EPG 操作失败: {str(e)}")
            logger.error(f"EPG 操作失败: {str(e)}")
            return False

# 缓存管理      
class CacheManager:
    #初始化
    def __init__(self, cache_dir: Path):
        # 打包成exe时使用sys.executable的目录作为基准路径
        if getattr(sys, 'frozen', False):
            base_dir = Path(sys.executable).parent
            self.cache_dir = base_dir / "epg-xml"
        else:
            self.cache_dir = cache_dir
            
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"创建缓存目录失败: {self.cache_dir}, 错误: {str(e)}")
            raise

    # 生成缓存文件名
    def generate_cache_key(self, url: str) -> str:
        """生成缓存文件名"""
        parsed = urlparse(url)
        return hashlib.md5(f"{parsed.netloc}{parsed.path}".encode()).hexdigest()

    # 获取缓存文件路径
    def get_cache_path(self, key: str) -> Path:
        """获取缓存文件路径"""
        return self.cache_dir / f"{key}.xml"

    # 保存缓存文件
    def save_cache(self, key: str, data: bytes) -> None:
        """保存缓存文件"""
        cache_path = self.get_cache_path(key)
        with open(cache_path, "wb") as f:
            f.write(data)
        logger.debug(f"缓存已保存: {cache_path}")

    # 加载缓存文件
    def load_cache(self, key: str) -> Optional[bytes]:
        """加载缓存文件"""
        cache_path = self.get_cache_path(key)
        if cache_path.exists():
            with open(cache_path, "rb") as f:
                return f.read()
        return None

    # 获取最新的缓存文件
    def get_latest_cache(self) -> Optional[Path]:
        """获取最新的缓存文件"""
        cache_files = sorted(self.cache_dir.glob("*.xml"), key=lambda f: f.stat().st_mtime, reverse=True)
        return cache_files[0] if cache_files else None
