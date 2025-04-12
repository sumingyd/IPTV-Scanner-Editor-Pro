from PyQt6 import QtWidgets, QtCore
import requests
from lxml import etree
from datetime import datetime, timedelta
import re
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse
import hashlib
import time
import sys
import asyncio
from pathlib import Path
from logger_utils import setup_logger
from config_manager import ConfigHandler

logger = setup_logger('EPGManager')

# EPG管理
class EPGManager(QtCore.QObject):
    # 定义信号
    progress_signal = QtCore.pyqtSignal(str)
    
    _instance = None
    
    # 初始化
    def __init__(self, parent=None):
        super().__init__(parent)  # 总是先调用父类初始化
        
        if EPGManager._instance is None:
            logger.info("初始化EPGManager")
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
            
            EPGManager._instance = self
        else:
            # 返回已存在的实例
            self.__dict__ = EPGManager._instance.__dict__

    # 初始化EPG UI组件
    def _init_epg_ui(self) -> None:
        """初始化EPG UI组件"""
        logger.debug("初始化EPG UI组件")
        if not self.parent:
            logger.debug("无父组件，跳过UI初始化")
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
        logger.info(f"加载EPG配置 - 主URL: {self.main_url}, 备用URLs: {self.backup_urls}")
        
        self.epg_sources = {
            'main': self.main_url,
            'backups': self.backup_urls,
            'cache_ttl': self.config.config.getint('EPG', 'cache_ttl', fallback=3600)
        }

    # 保存EPG数据源配置
    def save_epg_sources(self, main_url: str, backup_urls: str, cache_ttl: int) -> None:
        """保存EPG数据源配置"""
        logger.info(f"保存EPG配置 - 主URL: {main_url}, 备用URLs: {backup_urls}, 缓存TTL: {cache_ttl}")
        self.main_url = main_url
        self.backup_urls = [url.strip() for url in backup_urls.split(',') if url.strip()]
        logger.debug(f"更新后的EPG配置 - 主URL: {self.main_url}, 备用URLs: {self.backup_urls}")
        self.epg_sources = {
            'main': self.main_url,
            'backups': self.backup_urls,
            'cache_ttl': cache_ttl
        }

    # 保存EPG设置并关闭对话框
    def _save_epg_settings(self, main_url: str, backup_urls: str, cache_ttl: int, dialog: QtWidgets.QDialog) -> None:
        """保存EPG设置并关闭对话框"""
        logger.info("保存EPG设置")
        self.save_epg_sources(main_url, backup_urls, cache_ttl)
        self.config.config['EPG'] = {
            'main_url': main_url,
            'backup_urls': backup_urls,
            'cache_ttl': str(cache_ttl)
        }
        self.config.save_config()
        dialog.accept()

    # 下载 EPG 数据并缓存
    async def _download_epg(self, url: str, force_refresh: bool = False, max_retries: int = 3) -> Optional[bytes]:
        """下载 EPG 数据并缓存
        参数:
            url: 要下载的EPG URL
            force_refresh: 是否强制刷新跳过缓存
            max_retries: 最大重试次数
        """
        cache_key = self.cache_manager.generate_cache_key(url)
        
        # 强制刷新时完全跳过缓存检查
        if not force_refresh:
            # 非强制刷新时检查缓存
            try:
                if cached_data := self.cache_manager.load_cache(cache_key):
                    logger.debug(f"从缓存加载: {cache_key}")
                    return cached_data
            except Exception as e:
                logger.warning(f"加载缓存失败: {str(e)}，继续尝试下载")

        # 带重试机制的下载
        for attempt in range(1, max_retries + 1):
            try:
                headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
                logger.debug(f"尝试下载EPG数据 (尝试 {attempt}/{max_retries}): {url}")
                
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
                try:
                    self.cache_manager.save_cache(cache_key, content)
                    logger.debug(f"成功保存缓存: {cache_key}")
                    return content
                except Exception as e:
                    logger.error(f"保存缓存失败: {str(e)}，但仍返回下载内容")
                    return content

            except requests.exceptions.RequestException as e:
                logger.warning(f"EPG下载失败 (尝试 {attempt}/{max_retries}) [{url}]: {str(e)}")
                if attempt < max_retries:
                    await asyncio.sleep(2 ** attempt)  # 指数退避
                else:
                    logger.error(f"EPG下载最终失败 [{url}]")
            except Exception as e:
                logger.exception(f"未知下载错误: {str(e)}")
                break

        return None

    # 解析XMLTV格式数据
    def _parse_xmltv(self, xml_content: bytes) -> Dict[str, Dict]:
        """解析XMLTV格式数据"""
        logger.debug("开始解析XMLTV数据")
        try:
            root = etree.fromstring(xml_content)
            logger.debug(f"解析到XML根节点: {root.tag}")
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
            
            logger.info(f"成功解析XMLTV数据，共{len(channels)}个频道")
            return channels
        except etree.XMLSyntaxError as e:
            logger.error(f"XML解析错误: {str(e)}")
        except Exception as e:
            logger.exception(f"EPG解析异常: {str(e)}")
        logger.warning("XMLTV解析失败，返回空数据")
        return {}

    # 频道名称模糊匹配
    def match_channel_name(self, partial: str, max_results: int = 10) -> List[str]:
        """频道名称模糊匹配"""
        logger.debug(f"开始频道名称模糊匹配: {partial}")
        if not partial or not isinstance(partial, str):
            logger.warning("无效的频道名称输入")
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
        logger.debug(f"检查频道匹配: {channel_name}")
        if not channel_name or not isinstance(channel_name, str):
            logger.warning("无效的频道名称输入")
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
        logger.info("显示EPG管理对话框")
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
        """保存EPG数据到本地文件(使用缓存key作为文件名)"""
        logger.info("开始保存EPG数据到本地文件")
        try:
            cache_key = self.cache_manager.generate_cache_key(self.epg_sources['main'])
            local_path = self.cache_manager.get_cache_path(cache_key)
            logger.debug(f"本地文件路径: {local_path}")
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

    # 带进度显示的EPG加载
    async def load_epg_with_progress(self, main_window, force_refresh: bool = False) -> bool:
        """
        带进度显示的EPG加载
        职责:
        1. 加载EPG数据并更新进度显示
        2. 处理加载过程中的错误和状态
        3. 记录详细的操作日志
        
        参数:
            main_window: 主窗口对象，用于更新进度显示
            force_refresh: 是否强制从网络刷新数据
            
        返回:
            bool: 加载是否成功
        """
        logger.info(f"开始带进度显示的EPG加载，强制刷新: {force_refresh}")
        try:
            logger.debug("调用底层load_epg方法")
            result = await self.load_epg(force_refresh)
            if result:
                logger.info("EPG加载成功")
            else:
                logger.warning("EPG加载失败")
            return result
        except Exception as e:
            logger.error(f"EPG加载过程中发生异常: {str(e)}", exc_info=True)
            self.progress_signal.emit(f"EPG加载错误: {str(e)}")
            raise

    # 智能加载EPG数据(优先缓存，自动更新)
    async def load_epg(self, force_refresh: bool = False) -> bool:
        """
        智能加载EPG数据(优先缓存，自动更新)
        流程:
        1. 强制刷新时完全跳过缓存检查
        2. 非强制刷新时尝试从缓存加载
        3. 缓存无效则从网络下载
        4. 解析并更新EPG数据
        
        参数:
            force_refresh: 是否跳过缓存强制从网络刷新
            
        返回:
            bool: 加载是否成功
        """
        logger.info(f"开始加载EPG数据，强制刷新: {force_refresh}")
        self.progress_signal.emit("开始EPG加载流程...")
        
        try:
            logger.debug(f"EPG源配置 - 主URL: {self.epg_sources['main']}, 备用URLs: {self.epg_sources['backups']}")
            
            # 强制刷新时完全跳过缓存检查
            if force_refresh:
                logger.info("强制刷新模式，完全跳过缓存检查")
                self.progress_signal.emit("强制刷新模式，跳过所有缓存检查...")
                content = None
            else:
                # 尝试从缓存加载
                if latest_cache := self.cache_manager.get_latest_cache():
                    try:
                        self.progress_signal.emit("正在读取缓存...")
                        logger.debug(f"尝试加载缓存文件: {latest_cache}")
                        with open(latest_cache, "rb") as f:
                            content = f.read()
                        
                        # 同步执行XML解析以确保日志顺序正确
                        self.progress_signal.emit("正在解析缓存数据...")
                        parsed_data = self._parse_xmltv(content)
                        
                        if parsed_data:
                            self.epg_data = parsed_data
                            logger.info(f"成功从缓存加载EPG数据: {latest_cache.name}")
                            self.progress_signal.emit(f"从缓存加载 EPG 数据: {latest_cache.name}")
                            return True
                        else:
                            logger.warning("缓存文件解析失败，尝试更新...")
                            self.progress_signal.emit("缓存文件解析失败，尝试更新...")
                    except Exception as e:
                        logger.error(f"加载缓存文件失败: {str(e)}，尝试更新...")
                        self.progress_signal.emit(f"加载缓存文件失败: {str(e)}，尝试更新...")
            
            # 检查是否设置了EPG源
            if not self.epg_sources['main'] and not self.epg_sources['backups']:
                logger.error("未设置EPG数据源地址")
                self.progress_signal.emit("错误: 未设置EPG数据源地址")
                return False
            
            # 下载EPG数据
            self.progress_signal.emit("正在下载EPG数据...")
            content = None
            
            # 优先尝试主源
            if self.epg_sources['main']:
                logger.debug(f"尝试从主源下载: {self.epg_sources['main']}")
                content = await self._download_epg(self.epg_sources['main'], force_refresh)
            
            # 主源失败时尝试备用源
            if not content and self.epg_sources['backups']:
                for backup_url in self.epg_sources['backups']:
                    logger.debug(f"尝试从备用源下载: {backup_url}")
                    self.progress_signal.emit(f"正在尝试备用源: {backup_url}")
                    content = await self._download_epg(backup_url, force_refresh)
                    if content:
                        break

            if content:
                self.progress_signal.emit("正在解析EPG数据...")
                try:
                    # 同步执行XML解析以确保日志顺序正确
                    parsed_data = self._parse_xmltv(content)
                    
                    if parsed_data:
                        self.epg_data = parsed_data
                        logger.info("EPG数据解析成功")
                        
                        # 立即保存到本地文件
                        self.progress_signal.emit("正在保存EPG数据...")
                        if self.save_local_epg():
                            logger.info("EPG数据保存成功")
                            self.progress_signal.emit("EPG数据更新成功")
                            return True
                        else:
                            logger.warning("EPG数据保存失败")
                            self.progress_signal.emit("EPG数据保存失败")
                    else:
                        logger.warning("EPG数据解析失败")
                        self.progress_signal.emit("EPG数据解析失败")
                except Exception as e:
                    logger.error(f"EPG解析过程中发生异常: {str(e)}")
                    self.progress_signal.emit(f"EPG解析错误: {str(e)}")
            else:
                logger.error("所有EPG源下载失败")
                self.progress_signal.emit("所有EPG源下载失败")
            
            return False
        except Exception as e:
            self.progress_signal.emit(f"EPG 操作失败: {str(e)}")
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
            
        # 尝试创建缓存目录，最多重试3次
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                self.cache_dir.mkdir(parents=True, exist_ok=True)
                logger.debug(f"成功创建缓存目录: {self.cache_dir}")
                break
            except Exception as e:
                logger.error(f"创建缓存目录失败 (尝试 {attempt}/{max_retries}): {self.cache_dir}, 错误: {str(e)}")
                if attempt == max_retries:
                    logger.critical("无法创建缓存目录，EPG功能将受限")
                    # 设置一个临时目录作为后备
                    self.cache_dir = Path("/tmp/epg-xml") if sys.platform != "win32" else Path("C:/Temp/epg-xml")
                    try:
                        self.cache_dir.mkdir(parents=True, exist_ok=True)
                        logger.warning(f"使用临时目录作为缓存: {self.cache_dir}")
                    except Exception as e:
                        logger.critical(f"也无法创建临时缓存目录: {str(e)}")
                        raise RuntimeError("无法创建任何缓存目录") from e
                else:
                    time.sleep(1)  # 等待1秒后重试

    # 生成缓存文件名
    def generate_cache_key(self, url: str) -> str:
        """生成缓存文件名"""
        logger.debug(f"为URL生成缓存key: {url}")
        parsed = urlparse(url)
        return hashlib.md5(f"{parsed.netloc}{parsed.path}".encode()).hexdigest()

    # 获取缓存文件路径
    def get_cache_path(self, key: str) -> Path:
        """获取缓存文件路径"""
        path = self.cache_dir / f"{key}.xml"
        logger.debug(f"获取缓存文件路径: {path}")
        return path

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
        logger.debug("查找最新缓存文件")
        cache_files = sorted(self.cache_dir.glob("*.xml"), key=lambda f: f.stat().st_mtime, reverse=True)
        latest = cache_files[0] if cache_files else None
        logger.debug(f"最新缓存文件: {latest}")
        return latest
