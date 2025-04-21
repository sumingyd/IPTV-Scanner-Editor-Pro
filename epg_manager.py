from copy import deepcopy
from io import BytesIO
import os
import traceback
import requests
import time
import xml.etree.ElementTree as ET
from typing import List, Dict, Optional
from dataclasses import asdict
from PyQt6.QtCore import QThread, pyqtSignal
from epg_model import EPGConfig, EPGChannel, EPGProgram, EPGSource
from config_manager import ConfigManager
from log_manager import LogManager

logger = LogManager()

class EPGManager(QThread):
    progress = pyqtSignal(float, str)  # 进度百分比, 状态消息
    finished = pyqtSignal(bool)  # 是否成功
    
    def __init__(self, config_manager: ConfigManager):
        super().__init__()
        self.config_manager = config_manager
        try:
            self.epg_config = self.config_manager.load_epg_config()
            if not self.epg_config:
                logger.error("EPG配置加载失败: 返回None")
            elif not hasattr(self.epg_config, 'sources'):
                logger.error("EPG配置无效: 缺少sources属性")
        except Exception as e:
            logger.error(f"EPG配置加载异常: {str(e)}")
            raise
            
        self.epg_data: Dict[str, EPGChannel] = {}
        self._name_index: Dict[str, List[str]] = {}
        self.loaded = False
        self._operation = None  # 'update' or 'load'
        self._result = False  # 操作结果
        self.last_operation_status = None  # 最后操作状态
        
    @property
    def result(self) -> bool:
        """获取操作结果"""
        return self._result
        
    def get_result(self) -> bool:
        """获取操作结果(兼容旧方法)"""
        return self._result
        
    def refresh_epg(self, force_update=False, is_init=False):
        """启动EPG刷新流程
        Args:
            force_update: 是否强制更新
            is_init: 是否为初始化加载(不显示警告)
        """
        # 记录调用时间点
        call_time = time.time()
        logger.debug(f"refresh_epg调用时间: {call_time}")
        
        # 1. 检查线程状态
        if self.isRunning():
            if not is_init:
                logger.warning("EPG操作正在进行中，忽略本次请求")
            return False
            
        # 2. 验证配置
        if not self.epg_config:
            logger.error("EPG配置未加载")
            return False
            
        if not hasattr(self.epg_config, 'sources') or not self.epg_config.sources:
            logger.error("EPG源未配置")
            return False
            
        # 3. 设置操作类型
        self._operation = 'update' if force_update else 'load'
        logger.info(f"准备启动EPG操作: {self._operation}")
        
        # 4. 重置状态
        self._result = False
        
        # 5. 启动线程
        try:
            start_time = time.time()
            self.start()
            logger.debug(f"EPG线程启动时间: {start_time}, 耗时: {time.time()-start_time:.3f}s")
            return True
        except RuntimeError as e:
            if "Cannot start a thread that has already been started" in str(e):
                logger.warning("尝试重新创建线程实例")
                self.__init__(self.config_manager)
                try:
                    self.start()
                    return True
                except Exception as e:
                    logger.error(f"重新创建线程后启动失败: {str(e)}")
                    return False
            logger.error(f"EPG线程启动失败: {str(e)}")
            return False
        
    def run(self):
        """执行EPG操作的主线程方法"""
        op_id = str(int(time.time() * 1000))[-6:]  # 生成6位操作ID
        logger.info(f"[{op_id}] 开始EPG操作: {self._operation}")
        
        try:
            if self._operation == 'update':
                result = self._update_epg(op_id)
            elif self._operation == 'load':
                result = self._load_epg(op_id)
            else:
                raise ValueError(f"[{op_id}] 未知的EPG操作类型: {self._operation}")
                
            self.last_operation_status = result
            if result:
                logger.info(f"[{op_id}] EPG操作成功: {self._operation}")
                self.finished.emit(True)
            else:
                logger.warning(f"[{op_id}] EPG操作部分完成")
                self.finished.emit(True)  # 即使部分失败也视为成功
                
        except Exception as e:
            logger.error(f"[{op_id}] EPG操作遇到错误: {str(e)}")
            logger.debug(f"[{op_id}] 详细错误信息:\n{traceback.format_exc()}")
            self.finished.emit(True)  # 即使出错也视为成功，避免中断UI
            
    def _update_epg(self, op_id: str) -> bool:
        """更新EPG数据流程"""
        self.progress.emit(0, f"[{op_id}] 开始更新EPG数据...")
        
        # 1. 下载EPG数据
        self.progress.emit(0.3, "正在下载EPG数据...")
        download_success = False
        try:
            download_success = self._download_epg()
            if not download_success:
                logger.warning("部分EPG源下载失败，将继续处理可用数据")
            
            # 检查EPG文件是否存在
            if not os.path.exists(self.epg_config.local_file):
                logger.warning("没有可用的EPG文件，将尝试继续处理")
                return True  # 即使没有文件也返回True，不中断流程
        except Exception as e:
            logger.error(f"EPG下载过程中发生错误: {str(e)}")
            # 不抛出异常，继续执行
            
            # 2. 解析EPG数据
            self.progress.emit(0.7, "正在解析EPG数据...")
            if not self._parse_epg():
                raise Exception("EPG解析失败")
            
        # 不再创建备份文件
            
        self.progress.emit(1.0, "EPG更新完成")
        return True
        
    def _load_epg(self, op_id: str) -> bool:
        """加载EPG数据流程"""
        self.progress.emit(0, f"[{op_id}] 开始加载EPG数据...")
        
        try:
            # 1. 检查本地文件
            local_file = self.epg_config.local_file
            if not os.path.exists(local_file):
                raise FileNotFoundError(f"[{op_id}] EPG文件不存在: {local_file}")
            if not os.access(local_file, os.R_OK):
                raise PermissionError(f"[{op_id}] 无读取权限: {local_file}")
                
            # 2. 解析EPG数据
            self.progress.emit(0.5, "正在解析EPG数据...")
            parse_result = self._parse_epg()
            if not parse_result:
                raise Exception(f"[{op_id}] EPG解析失败")
                
            self.progress.emit(1.0, "EPG加载完成")
            return True
            
        except Exception as e:
            logger.error(f"[{op_id}] 加载EPG失败: {str(e)}")
            raise
        
    def _download_epg(self) -> bool:
        """下载EPG文件（修复版）
        返回值说明：
        True - 所有源下载成功
        False - 部分源下载失败但仍继续处理
        """
        local_file = self.epg_config.local_file
        logger.info(f"开始下载EPG，保存路径: {local_file}")
        logger.info(f"合并模式: {self.epg_config.merge_sources}")
        
        # 初始化下载状态
        all_success = True
        
        # 确保目录存在（增强路径处理）
        epg_dir = os.path.dirname(os.path.abspath(local_file))
        if not os.path.exists(epg_dir):
            try:
                os.makedirs(epg_dir, exist_ok=True)
                logger.info(f"创建EPG目录: {epg_dir}")
            except Exception as e:
                logger.error(f"无法创建EPG目录: {epg_dir}, 错误: {str(e)}")
                return False
        
        temp_file = local_file + ".tmp"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/xml,application/xml'
        }

        try:
            if self.epg_config.merge_sources:
                return self._download_merged_epg(local_file, temp_file, headers)
            else:
                return self._download_single_epg(local_file, temp_file, headers)
        except Exception as e:
            logger.error(f"EPG下载过程发生未捕获异常: {str(e)}\n{traceback.format_exc()}")
            return False

    def _download_merged_epg(self, local_file, temp_file, headers):
        """处理合并模式下载"""
        merged_data = {}  # 正确初始化字典
        ns = {'tv': 'http://www.xmltv.org/xmltv.dtd'}  # 添加命名空间处理
        all_success = True

        logger.info(f"开始合并模式下载，共{len(self.epg_config.sources)}个源")
        
        for source in self.epg_config.sources:
            for attempt in range(3):
                try:
                    time.sleep(5 * (attempt + 1))
                    logger.info(f"尝试下载源 [{source.url}] (第{attempt+1}次)")
                    
                    # 添加headers和stream参数（关键修复）
                    with requests.get(source.url, headers=headers, timeout=30, stream=True) as response:
                        response.raise_for_status()
                        # 强制获取原始字节内容并记录响应头
                        content = response.content
                        logger.debug(f"原始响应内容前100字节(hex): {content[:100].hex()}")
                        logger.debug(f"响应头: {response.headers}")
                        # 尝试从Content-Type获取编码
                        content_type = response.headers.get('Content-Type', '')
                        if 'charset=' in content_type:
                            declared_encoding = content_type.split('charset=')[1].split(';')[0].strip().lower()
                            logger.debug(f"从Content-Type检测到声明编码: {declared_encoding}")

                        # 增强XML验证和编码处理
                        if not content.strip():
                            raise ValueError("空响应内容")
                            
                        # 增强编码检测和转换
                        def detect_encoding(content):
                            # 记录原始内容前100字节用于调试
                            sample = content[:100] if isinstance(content, bytes) else content[:100].encode('latin1')
                            logger.debug(f"编码检测样本(hex): {sample.hex()}")
                            
                            # 先检查BOM标记
                            if isinstance(content, bytes):
                                if content.startswith(b'\xef\xbb\xbf'):
                                    logger.debug("检测到UTF-8 BOM标记")
                                    return 'utf-8-sig'
                                elif content.startswith(b'\xff\xfe'):
                                    logger.debug("检测到UTF-16 LE BOM标记")
                                    return 'utf-16-le'
                                elif content.startswith(b'\xfe\xff'):
                                    logger.debug("检测到UTF-16 BE BOM标记") 
                                    return 'utf-16-be'
                            
                            # 尝试常见中文编码(按可能性排序)
                            encodings = ['utf-8', 'gb18030', 'gbk', 'gb2312', 'big5', 'utf-16']
                            for enc in encodings:
                                try:
                                    test = content.decode(enc) if isinstance(content, bytes) else content.encode('latin1').decode(enc)
                                    # 严格验证是否为有效XML
                                    if '<?xml' in test and any(c in test for c in '<>?/'):
                                        logger.debug(f"成功检测到编码: {enc}")
                                        return enc
                                except Exception as e:
                                    logger.debug(f"编码{enc}检测失败: {str(e)}")
                                    continue
                            logger.warning("无法确定内容编码")
                            return None
                            
                        # 检测编码 - 优先使用Content-Type中声明的编码
                        detected_enc = None
                        if 'declared_encoding' in locals() and declared_encoding:
                            try:
                                # 先尝试使用声明的编码
                                test_content = content.decode(declared_encoding)
                                if '<?xml' in test_content:
                                    detected_enc = declared_encoding
                                    logger.debug(f"使用Content-Type声明的编码: {declared_encoding}")
                            except Exception as e:
                                logger.debug(f"Content-Type声明的编码{declared_encoding}无效: {str(e)}")
                        
                        # 如果声明编码无效，则自动检测
                        if not detected_enc:
                            detected_enc = detect_encoding(content)
                            if detected_enc:
                                logger.debug(f"自动检测到编码: {detected_enc}")
                        
                        if detected_enc:
                            content = content.decode(detected_enc) if isinstance(content, bytes) else content
                        else:
                            # 使用chardet作为后备方案
                            try:
                                import chardet # type: ignore
                                result = chardet.detect(content if isinstance(content, bytes) else content.encode('latin1'))
                                if result['confidence'] > 0.8:
                                    content = content.decode(result['encoding']) if isinstance(content, bytes) else content
                                    logger.debug(f"使用chardet检测到编码: {result['encoding']}")
                                else:
                                    raise ValueError("编码检测置信度不足")
                            except:
                                # 最终回退方案
                                content = content.decode('utf-8', errors='replace') if isinstance(content, bytes) else content
                                logger.warning("无法确定编码，使用UTF-8替换模式")
                        
                        # 统一转换为UTF-8并验证
                        try:
                            utf8_content = content.encode('utf-8').decode('utf-8')
                            if '<?xml' not in utf8_content:
                                raise ValueError("无效的XML内容")
                            
                            # 额外验证文本内容是否包含乱码
                            if any(ord(c) > 127 and not c.isprintable() for c in utf8_content):
                                raise ValueError("检测到可能的乱码字符")
                                
                            content = utf8_content
                        except Exception as e:
                            logger.error(f"UTF-8转换失败: {str(e)}")
                            # 尝试修复乱码
                            try:
                                content = content.encode('utf-8', errors='replace').decode('utf-8')
                                logger.warning("已替换无效字符继续处理")
                            except:
                                raise
                            
                        if '<?xml' not in content:
                            content = '<?xml version="1.0" encoding="UTF-8"?>\n' + content

                        # 使用defusedxml防御XML攻击
                        from defusedxml.ElementTree import fromstring
                        try:
                            root = fromstring(content.encode('utf-8') if isinstance(content, str) else content)
                        except:
                            root = fromstring(content)
                        
                        # 处理带命名空间的元素
                        channels = root.findall('.//tv:channel', namespaces=ns) or root.findall('channel')
                        programmes = root.findall('.//tv:programme', namespaces=ns) or root.findall('programme')

                        # 合并频道数据
                        for channel in channels:
                            self._merge_channel_data(merged_data, channel)
                        
                        # 合并节目数据
                        for programme in programmes:
                            self._merge_programme_data(merged_data, programme)

                        logger.info(f"成功下载并解析源 [{source.url}]")
                        break
                except Exception as e:
                    logger.warning(f"源 [{source.url}] 下载失败 (尝试 {attempt+1}/3): {str(e)}")
                    if attempt == 2:
                        logger.warning(f"最终无法下载源 [{source.url}]，已跳过")
                        all_success = False
                    continue

        if not merged_data:
            logger.error("没有有效的EPG数据可合并")
            # 即使没有数据也返回True，让流程继续
            return True
            
        write_result = self._write_merged_epg(merged_data, local_file, temp_file)
        if not write_result:
            logger.error("写入合并后的EPG文件失败")
            return False
            
        logger.info(f"EPG合并完成，共合并{len(merged_data)}个频道")
        return True

    def _merge_channel_data(self, merged_data, channel):
        """合并频道数据
        处理逻辑:
        1. 根据channel id进行合并
        2. 如果channel不存在则创建新记录
        3. 如果channel已存在则合并display-name
        4. 保留所有不重复的display-name
        """
        channel_id = channel.get('id')
        if not channel_id:
            return

        # 深拷贝频道元素并确保文本编码正确
        channel_copy = ET.Element('channel', attrib=channel.attrib)
        for elem in channel:
            # 确保文本编码正确
            if elem.text:
                try:
                    elem.text.encode('utf-8').decode('utf-8')
                except UnicodeError:
                    elem.text = elem.text.encode('utf-8', errors='replace').decode('utf-8')
            channel_copy.append(deepcopy(elem))

        if channel_id not in merged_data:
            merged_data[channel_id] = {
                'channel': channel_copy,
                'programmes': []
            }
        else:
            # 合并display-name (保留不重复的名称)
            existing_names = {e.text for e in merged_data[channel_id]['channel'].findall('display-name')}
            for name_elem in channel_copy.findall('display-name'):
                if name_elem.text not in existing_names:
                    merged_data[channel_id]['channel'].append(deepcopy(name_elem))

    def _merge_programme_data(self, merged_data, programme):
        """合并节目数据"""
        channel_id = programme.get('channel')
        if not channel_id or channel_id not in merged_data:
            return

        # 节目去重逻辑
        prog_key = (
            programme.get('start'),
            programme.get('stop'),
            programme.find('title').text if programme.find('title') is not None else None
        )

        # 检查重复节目
        existing_progs = merged_data[channel_id]['programmes']
        for existing in existing_progs:
            existing_key = (
                existing.get('start'),
                existing.get('stop'),
                existing.find('title').text if existing.find('title') is not None else None
            )
            if existing_key == prog_key:
                return

        # 添加新节目并确保文本编码正确
        prog_copy = deepcopy(programme)
        for elem in prog_copy:
            if elem.text:
                try:
                    elem.text.encode('utf-8').decode('utf-8')
                except UnicodeError:
                    elem.text = elem.text.encode('utf-8', errors='replace').decode('utf-8')
        merged_data[channel_id]['programmes'].append(prog_copy)

    def _write_merged_epg(self, merged_data, local_file, temp_file):
        """写入合并后的EPG文件"""
        try:
            # 创建XML树
            root = ET.Element('tv')
            for data in merged_data.values():
                root.append(data['channel'])
                for prog in data['programmes']:
                    root.append(prog)

            # 美化XML格式
            ET.indent(root)
            
            # 使用UTF-8编码写入并确保XML声明
            with open(temp_file, 'wb') as f:
                # 强制写入UTF-8 BOM头
                f.write(b'\xef\xbb\xbf')
                # 写入XML声明
                f.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
                # 写入XML内容，确保保留原始编码
                xml_content = ET.tostring(root, encoding='utf-8', xml_declaration=False)
                # 验证内容是否包含乱码
                try:
                    xml_content.decode('utf-8')
                except UnicodeDecodeError:
                    logger.warning("检测到合并内容中的编码问题，尝试修复")
                    xml_content = xml_content.decode('utf-8', errors='replace').encode('utf-8')
                f.write(xml_content)
                
            # 二次验证编码
            try:
                with open(temp_file, 'rb') as f:
                    content = f.read()
                # 确保内容能正确解码为UTF-8
                content.decode('utf-8')
            except UnicodeDecodeError:
                logger.error("生成的EPG文件编码验证失败")
                return False

            # 验证文件有效性
            if os.path.getsize(temp_file) < 1024:
                raise ValueError("生成的EPG文件过小，可能存在问题")

            # 使用绝对路径确保文件操作正确
            abs_temp = os.path.abspath(temp_file)
            abs_local = os.path.abspath(local_file)
            os.replace(abs_temp, abs_local)
            logger.info("EPG合并完成")
            return True
        except Exception as e:
            logger.error(f"写入EPG文件失败: {str(e)}")
            if os.path.exists(temp_file):
                os.remove(temp_file)
            return False

    def _download_single_epg(self, local_file, temp_file, headers):
        """处理单源下载"""
        primary_source = next((s for s in self.epg_config.sources if s.is_primary), None)
        if not primary_source:
            logger.error("未配置主EPG源")
            return False

        for attempt in range(3):
            try:
                time.sleep(5 * attempt)
                with requests.get(primary_source.url, headers=headers, timeout=30, stream=True) as response:
                    response.raise_for_status()
                    
                    # 流式写入文件
                    total_size = 0
                    with open(temp_file, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                                total_size += len(chunk)
                                if total_size > 1024 * 1024 * 100:  # 限制100MB
                                    raise ValueError("文件大小超过安全限制")

                    # 验证XML有效性
                    try:
                        with open(temp_file, 'r', encoding='utf-8') as f:
                            ET.parse(f)
                    except ET.ParseError:
                        raise ValueError("下载内容不是有效的XML格式")

                    os.replace(temp_file, local_file)
                    logger.info(f"EPG下载成功 ({primary_source.url})")
                    return True

            except Exception as e:
                logger.warning(f"主源下载失败 (尝试 {attempt+1}/3): {str(e)}")
                if attempt == 2:
                    logger.warning("所有下载尝试失败")
                    return True  # 返回True让流程继续

        return False

    def indent(elem, level=0):
        """美化XML输出"""
        i = "\n" + level*"  "
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = i + "  "
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
            for elem in elem:
                ET.indent(elem, level+1)
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
        else:
            if level and (not elem.tail or not elem.tail.strip()):
                elem.tail = i

    def _parse_epg(self) -> bool:
        """解析EPG文件"""
        try:
            # 使用标准库xml.etree.ElementTree进行安全解析
            import xml.etree.ElementTree as ET
            from defusedxml.ElementTree import parse
            
            self.epg_data = {}
            self._name_index = {}
            
            # 使用defusedxml防御XML攻击并处理编码
            try:
                # 先读取文件内容并验证编码
                with open(self.epg_config.local_file, 'rb') as f:
                    content = f.read()
                
                # 验证是否为有效UTF-8
                try:
                    content.decode('utf-8')
                except UnicodeDecodeError:
                    logger.warning("EPG文件不是有效的UTF-8编码，尝试修复")
                    content = content.decode('utf-8', errors='replace').encode('utf-8')
                
                # 解析XML
                tree = parse(BytesIO(content))
                root = tree.getroot()
                # 兼容旧Python版本的遍历方式
                context = ET.iterparse(BytesIO(content), events=('start', 'end'))
            except Exception as e:
                logger.error(f"EPG文件解析初始化失败: {str(e)}")
                return False
                
            # 手动控制解析上下文
            try:
                for event, elem in context:
                    if event == 'start' and elem.tag == 'channel':
                        channel_id = elem.get('id')
                        if channel_id:
                            names = [e.text for e in elem.findall('display-name') if e.text]
                            self.epg_data[channel_id] = EPGChannel(
                                id=channel_id,
                                name=names[0] if names else channel_id,
                                programs=[]
                            )
                            for name in names:
                                self._name_index.setdefault(name.lower(), []).append(channel_id)
                            
                    elif event == 'end' and elem.tag == 'programme':
                        try:
                            channel_id = elem.get('channel')
                            if channel_id in self.epg_data:
                                self.epg_data[channel_id].programs.append(EPGProgram(
                                    channel_id=channel_id,
                                title=elem.find('title').text if elem.find('title') is not None else '',
                                    start_time=elem.get('start'),
                                    end_time=elem.get('stop'),
                                    description=elem.find('desc').text if elem.find('desc') is not None else ''
                                ))
                        except Exception as e:
                            logger.warning(f"解析节目出错: {str(e)}")
                        finally:
                            elem.clear()
                
                self.loaded = True
                return True
            except Exception as e:
                logger.error(f"EPG解析过程中发生错误: {str(e)}")
                return False
            
        except ET.XMLSyntaxError as e:
            logger.error(f"EPG文件格式错误: {str(e)}\n文件路径: {self.epg_config.local_file}")
            try:
                with open(self.epg_config.local_file, 'rb') as f:
                    logger.error(f"文件开头内容(hex): {f.read(100).hex()}")
            except Exception as e:
                logger.error(f"无法读取文件内容: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"EPG解析失败: {str(e)}")
            return False
            
    def get_channel_programs(self, channel_name: str) -> Optional[List[EPGProgram]]:
        """获取频道节目单(增强版模糊匹配)
        Args:
            channel_name: 频道名称
        """
        if not self.loaded:
            logger.warning("EPG数据未加载")
            return None
            
        normalized_name = channel_name.lower().strip()
        logger.debug(f"开始查找频道: {normalized_name}")
        
        # 1. 精确匹配(不区分大小写)
        if normalized_name in self._name_index:
            logger.debug(f"精确匹配到频道: {normalized_name}")
            channel = self.epg_data.get(self._name_index[normalized_name][0])
            return channel.programs if channel else []
            
        # 2. 包含匹配(双向)
        for name, ids in self._name_index.items():
            if normalized_name in name or name in normalized_name:
                logger.debug(f"包含匹配到频道: {name} (原始: {normalized_name})")
                channel = self.epg_data.get(ids[0])
                return channel.programs if channel else []
                
        # 3. 相似度匹配(去除特殊字符)
        clean_name = ''.join(c for c in normalized_name if c.isalnum())
        for name, ids in self._name_index.items():
            clean_epg_name = ''.join(c for c in name if c.isalnum())
            # 双向包含匹配
            if clean_name in clean_epg_name or clean_epg_name in clean_name:
                logger.debug(f"相似度匹配到频道: {name} (原始: {normalized_name})")
                channel = self.epg_data.get(ids[0])
                return channel.programs if channel else []
                
        # 4. 尝试匹配频道ID
        for channel_id, channel in self.epg_data.items():
            if normalized_name == channel_id.lower():
                logger.debug(f"匹配到频道ID: {channel_id}")
                return channel.programs
                
        # 5. 最后尝试: 检查是否频道名称被包含在某个EPG名称中
        for name, ids in self._name_index.items():
            parts = name.split()
            for part in parts:
                if part == normalized_name:
                    logger.debug(f"部分匹配到频道: {name} (部分: {part})")
                    channel = self.epg_data.get(ids[0])
                    return channel.programs if channel else []
                    
        logger.warning(f"未找到匹配的频道: {normalized_name}")
        logger.debug(f"可用频道: {list(self._name_index.keys())}")
        return None

    def get_channel_names(self) -> List[str]:
        """获取所有频道名称列表"""
        if not self.loaded:
            return []
        return list(self._name_index.keys())
