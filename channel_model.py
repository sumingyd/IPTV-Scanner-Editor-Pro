from PyQt6 import QtCore, QtGui
from typing import List, Dict, Any
from log_manager import LogManager
from styles import AppStyles
logger = LogManager()

class ChannelListModel(QtCore.QAbstractTableModel):
    """频道列表数据模型"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.channels: List[Dict[str, Any]] = []
        self.headers = ["序号", "频道名称", "分辨率", "URL", "分组", "Logo地址", "状态", "延迟(ms)"]
        
        # 状态标签更新回调
        self.update_status_label = None
        
        # 频道名称和分组缓存(用于自动补全)
        self._name_cache = set()
        self._group_cache = set()
        
        # 语言管理器引用
        self._language_manager = None

    def set_language_manager(self, language_manager):
        """设置语言管理器"""
        self._language_manager = language_manager
        # 通知视图更新表头
        self.headerDataChanged.emit(QtCore.Qt.Orientation.Horizontal, 0, len(self.headers) - 1)
        # 强制刷新整个视图以确保表头更新
        self.dataChanged.emit(
            self.index(0, 0),
            self.index(self.rowCount() - 1 if self.rowCount() > 0 else 0, self.columnCount() - 1)
        )

    def rowCount(self, parent=QtCore.QModelIndex()) -> int:
        """返回行数(频道数量)"""
        return len(self.channels)

    def clear(self):
        """清空频道列表"""
        self.beginResetModel()
        self.channels = []
        self.endResetModel()

    def columnCount(self, parent=QtCore.QModelIndex()) -> int:
        """返回列数"""
        return len(self.headers)

    def data(self, index: QtCore.QModelIndex, role: int = QtCore.Qt.ItemDataRole.DisplayRole):
        """返回单元格数据"""
        if not index.isValid() or not (0 <= index.row() < len(self.channels)):
            return None

        channel = self.channels[index.row()]
        col = index.column()

        if role == QtCore.Qt.ItemDataRole.DisplayRole:
            if col == 0:  # 序号
                return str(index.row() + 1)
            elif col == 1:  # 频道名称
                return channel.get('name', '未命名')
            elif col == 2:  # 分辨率
                return channel.get('resolution', '')
            elif col == 3:  # URL
                return channel.get('url', '')
            elif col == 4:  # 分组
                return channel.get('group', '未分类')
            elif col == 5:  # Logo地址
                return channel.get('logo_url', channel.get('logo', ''))
            elif col == 6:  # 状态
                return channel.get('status', '待检测')
            elif col == 7:  # 延迟(ms)
                return str(channel.get('latency', ''))
        elif role == QtCore.Qt.ItemDataRole.TextAlignmentRole:
            return QtCore.Qt.AlignmentFlag.AlignVCenter | QtCore.Qt.AlignmentFlag.AlignLeft
        elif role == QtCore.Qt.ItemDataRole.BackgroundRole:
            if not channel.get('valid', True):
                return QtGui.QColor('#ffdddd')  # 无效项背景色
            else:
                return QtGui.QColor(AppStyles.table_bg_color())  # 使用styles中定义的表格背景色
        elif role == QtCore.Qt.ItemDataRole.ForegroundRole:
            if not channel.get('valid', True):
                return QtGui.QColor('#ff6666')  # 无效项文字颜色(红色)
            elif channel.get('status') == '待检测':
                return QtGui.QColor('#999999')  # 待检测文字颜色(灰色)
            else:
                return QtGui.QColor(AppStyles.text_color())  # 使用styles中定义的主题文字颜色
            
            # 数据加载完成后自动调整列宽
            if role == QtCore.Qt.ItemDataRole.DisplayRole and index.column() == 0:
                view = self.parent()
                if view and hasattr(view, 'resizeColumnsToContents'):
                    view.resizeColumnsToContents()
        return None

    def headerData(self, section: int, orientation: QtCore.Qt.Orientation,
                  role: int = QtCore.Qt.ItemDataRole.DisplayRole):
        """返回表头数据"""
        if role != QtCore.Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == QtCore.Qt.Orientation.Horizontal:
            # 使用语言管理器翻译表头
            header_text = self.headers[section]
            if hasattr(self, '_language_manager') and self._language_manager:
                if header_text == "序号":
                    return self._language_manager.tr('serial_number', 'No.')
                elif header_text == "频道名称":
                    return self._language_manager.tr('channel_name', 'Channel Name')
                elif header_text == "分辨率":
                    return self._language_manager.tr('resolution', 'Resolution')
                elif header_text == "URL":
                    return self._language_manager.tr('channel_url', 'URL')
                elif header_text == "分组":
                    return self._language_manager.tr('channel_group', 'Group')
                elif header_text == "Logo地址":
                    return self._language_manager.tr('logo_address', 'Logo Address')
                elif header_text == "状态":
                    return self._language_manager.tr('status', 'Status')
                elif header_text == "延迟(ms)":
                    return self._language_manager.tr('latency_ms', 'Latency(ms)')
            return header_text
        return str(section + 1) if section > 0 else ""  # 序号列不显示行号

    def flags(self, index: QtCore.QModelIndex) -> QtCore.Qt.ItemFlag:
        """返回项标志"""
        if not index.isValid():
            return QtCore.Qt.ItemFlag.NoItemFlags
        return (QtCore.Qt.ItemFlag.ItemIsEnabled | 
                QtCore.Qt.ItemFlag.ItemIsSelectable |
                QtCore.Qt.ItemFlag.ItemIsDragEnabled |
                QtCore.Qt.ItemFlag.ItemIsDropEnabled)
                
    def supportedDropActions(self) -> QtCore.Qt.DropAction:
        """支持的拖放操作"""
        return QtCore.Qt.DropAction.MoveAction
        
    def mimeTypes(self) -> List[str]:
        """支持的MIME类型"""
        return ['application/x-channel-row']
        
    def mimeData(self, indexes: List[QtCore.QModelIndex]) -> QtCore.QMimeData:
        """创建拖放数据"""
        mime_data = QtCore.QMimeData()
        mime_data.setData('application/x-channel-row', 
                         str(indexes[0].row()).encode())
        return mime_data
        
    def dropMimeData(self, data: QtCore.QMimeData, action: QtCore.Qt.DropAction,
                    row: int, column: int, parent: QtCore.QModelIndex) -> bool:
        """处理拖放数据"""
        if not data.hasFormat('application/x-channel-row'):
            return False
            
        if action == QtCore.Qt.DropAction.IgnoreAction:
            return True
            
        # 获取拖动源行
        source_row = int(data.data('application/x-channel-row').data().decode())
        
        # 计算目标行
        if row == -1:
            if parent.isValid():
                row = parent.row()
            else:
                row = self.rowCount()
                
        # 移动行
        self.moveRow(source_row, row)
        return True
        
    def moveRow(self, source_row: int, target_row: int) -> bool:
        """移动行到新位置"""
        if source_row == target_row or not (0 <= source_row < len(self.channels)):
            return False
            
        # 确保目标行在有效范围内
        target_row = min(max(0, target_row), len(self.channels))
        
        self.beginResetModel()
        channel = self.channels.pop(source_row)
        if target_row > source_row:
            target_row -= 1
        self.channels.insert(target_row, channel)
        self.endResetModel()
        return True

    def get_channel(self, index: int) -> Dict[str, Any]:
        """根据索引获取频道信息"""
        if 0 <= index < len(self.channels):
            return self.channels[index]
        return {}

    def add_channel(self, channel_info: Dict[str, Any]):
        """添加频道到模型"""
        if isinstance(channel_info, dict) and channel_info.get('batch') and channel_info.get('channels'):
            # 批量添加模式
            channels = channel_info['channels']
            if not channels:
                return
                
            # 批量处理所有频道
            self.beginInsertRows(QtCore.QModelIndex(), len(self.channels), len(self.channels) + len(channels) - 1)
            for channel in channels:
                # 检查是否已存在相同URL的频道
                existing_index = -1
                for i, c in enumerate(self.channels):
                    if c.get('url') == channel.get('url'):
                        existing_index = i
                        break
                        
                if existing_index >= 0:
                    # 更新现有频道
                    self.channels[existing_index].update(channel)
                    # 更新名称和分组缓存
                    if 'name' in channel:
                        self._name_cache.add(channel['name'])
                    if 'group' in channel:
                        self._group_cache.add(channel['group'])
                else:
                    # 添加新频道
                    self.channels.append(channel)
                    # 更新名称和分组缓存
                    if 'name' in channel:
                        self._name_cache.add(channel['name'])
                    if 'group' in channel:
                        self._group_cache.add(channel['group'])
            self.endInsertRows()
        else:
            # 单个添加模式
            existing_index = -1
            for i, channel in enumerate(self.channels):
                if channel.get('url') == channel_info.get('url'):
                    existing_index = i
                    break
                    
            if existing_index >= 0:
                # 更新现有频道信息
                self.channels[existing_index].update(channel_info)
                # 通知视图更新
                index = self.index(existing_index, 0)
                self.dataChanged.emit(index, index)
                # 更新名称和分组缓存
                if 'name' in channel_info:
                    self._name_cache.add(channel_info['name'])
                if 'group' in channel_info:
                    self._group_cache.add(channel_info['group'])
            else:
                # 添加新频道
                self.beginInsertRows(QtCore.QModelIndex(), len(self.channels), len(self.channels))
                self.channels.append(channel_info)
                # 更新名称和分组缓存
                if 'name' in channel_info:
                    self._name_cache.add(channel_info['name'])
                if 'group' in channel_info:
                    self._group_cache.add(channel_info['group'])
                self.endInsertRows()

    def hide_invalid(self):
        """隐藏无效频道"""
        if not hasattr(self, '_original_channels'):
            self._original_channels = self.channels.copy()
        self.beginResetModel()
        self.channels = [c for c in self.channels if c.get('valid', True)]
        self.endResetModel()

    def show_all(self):
        """显示所有频道"""
        self.beginResetModel()
        # 重新加载所有频道数据
        if hasattr(self, '_original_channels'):
            self.channels = self._original_channels.copy()
        self.endResetModel()

    def get_name_suggestions(self) -> List[str]:
        """获取频道名称建议列表"""
        return sorted(self._name_cache)

    def get_group_suggestions(self) -> List[str]:
        """获取分组建议列表"""
        return sorted(self._group_cache)
        
    def get_all_channel_names(self) -> List[str]:
        """获取所有频道名称列表"""
        return sorted(self._name_cache)

    def to_m3u(self) -> str:
        """将频道列表转换为M3U格式字符串"""
        from channel_mappings import get_channel_info
        logger = LogManager()
        lines = ["#EXTM3U"]
        for channel in self.channels:
            channel_name = channel.get('name', '')
            # 获取频道信息(包含logo地址)
            channel_info = get_channel_info(channel_name)
            logger.debug(f"处理频道: {channel_name}, 获取到的信息: {channel_info}")
            
            # EXTINF行 - 简化格式
            logo_url = channel_info.get('logo_url') or channel.get('logo')
            resolution = channel.get('resolution', '')
            
            extinf = (
                f"#EXTINF:-1 "
                f"tvg-id=\"{channel.get('tvg_id', '')}\" "
                f"tvg-name=\"{channel_info['standard_name']}\" "
                f"tvg-logo=\"{logo_url if logo_url else ''}\" "
                f"group-title=\"{channel.get('group', '未分类')}\" "
                f"resolution=\"{channel.get('resolution', '')}\" "
                f",{channel_info['standard_name']}"
            )
            lines.append(extinf)
            
            # URL行
            lines.append(channel.get('url', ''))
        
        # 添加来源信息
        from datetime import datetime
        lines.append("\n# Generated by IPTV Scanner Editor Pro")
        lines.append(f"# Saved at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("# GitHub: https://github.com/your-repo/IPTV-Scanner-Editor-Pro")
        return "\n".join(lines)

    def to_txt(self) -> str:
        """将频道列表转换为TXT格式字符串"""
        lines = []
        for channel in self.channels:
            # 格式: 频道名称,URL,分组,Logo地址,状态,延迟
            line = f"{channel.get('name', '未命名')},{channel.get('url', '')},{channel.get('group', '未分类')},{channel.get('status', '待检测')},{channel.get('latency', '')}"
            lines.append(line)
        return "\n".join(lines)

    def to_excel(self, file_path: str) -> bool:
        """将频道列表保存为Excel文件"""
        try:
            from openpyxl import Workbook
            wb = Workbook()
            ws = wb.active
            ws.title = "频道列表"
            
            # 写入表头
            ws.append(["频道名称", "URL", "分组", "Logo地址", "分辨率", "状态", "延迟(ms)"])
            
            # 写入数据
            for channel in self.channels:
                ws.append([
                    channel.get('name', '未命名'),
                    channel.get('url', ''),
                    channel.get('group', '未分类'),
                    channel.get('logo_url', channel.get('logo', '')),
                    channel.get('resolution', ''),
                    channel.get('status', '待检测'),
                    channel.get('latency', '')
                ])
            
            wb.save(file_path)
            return True
        except Exception as e:
            logger.error(f"保存Excel文件失败: {str(e)}", exc_info=True)
            return False

    def from_excel(self, file_path: str) -> bool:
        """从Excel文件加载频道列表"""
        wb = None
        try:
            from openpyxl import load_workbook
            wb = load_workbook(file_path)
            ws = wb.active
            
            self.beginResetModel()
            self.channels = []
            self._name_cache = set()
            self._group_cache = set()
            
            # 检查表头是否匹配
            headers = [cell.value for cell in ws[1]]
            expected_headers = ["频道名称", "URL", "分组", "Logo地址", "分辨率", "状态", "延迟(ms)"]
            if headers != expected_headers:
                logger.warning(f"Excel表头不匹配，期望: {expected_headers}，实际: {headers}")
            
            # 处理数据行
            for row in ws.iter_rows(min_row=2, values_only=True):
                if not row or not row[0]:  # 跳过空行
                    continue
                    
                try:
                    channel = {
                        'name': str(row[0]) if row[0] else '未命名',
                        'url': str(row[1]) if row[1] else '',
                        'group': str(row[2]) if len(row) > 2 and row[2] else '未分类',
                        'logo_url': str(row[3]) if len(row) > 3 and row[3] else '',
                        'logo': str(row[3]) if len(row) > 3 and row[3] else '',
                        'resolution': str(row[4]) if len(row) > 4 and row[4] else '',
                        'status': str(row[5]) if len(row) > 5 and row[5] else '待检测',
                        'latency': str(row[6]) if len(row) > 6 and row[6] else '',
                        'valid': False
                    }
                    
                    self.channels.append(channel)
                    self._name_cache.add(channel['name'])
                    self._group_cache.add(channel['group'])
                    logger.debug(f"成功加载频道: {channel['name']}")
                except Exception as e:
                    logger.error(f"处理Excel行失败: {row}, 错误: {str(e)}")
                    continue
            
            self.endResetModel()
            logger.info(f"成功从Excel加载 {len(self.channels)} 个频道")
            return True
        except Exception as e:
            logger.error(f"加载Excel文件失败: {str(e)}", exc_info=True)
            return False
        finally:
            if wb:
                wb.close()
                logger.debug("已释放Excel文件资源")

    def removeRow(self, row: int, parent=QtCore.QModelIndex()) -> bool:
        """删除指定行"""
        if not (0 <= row < len(self.channels)):
            return False
            
        # 获取要删除的频道信息
        channel = self.channels[row]
        
        # 通知视图即将删除行
        self.beginRemoveRows(parent, row, row)
        
        # 从列表中移除
        self.channels.pop(row)
        
        # 更新名称和分组缓存
        if 'name' in channel:
            self._name_cache.discard(channel['name'])
        if 'group' in channel:
            self._group_cache.discard(channel['group'])
            
        # 完成删除操作
        self.endRemoveRows()
        return True

    def set_channel_valid(self, url: str, valid: bool = True) -> bool:
        """设置频道的有效性状态"""
        for i, channel in enumerate(self.channels):
            if channel.get('url') == url:
                self.channels[i]['valid'] = valid
                self.channels[i]['status'] = '有效' if valid else '无效'
                return True
        return False

    def update_channel(self, index: int, new_channel: Dict[str, Any]) -> bool:
        """更新指定索引的频道数据"""
        if not (0 <= index < len(self.channels)):
            return False
            
        # 更新频道数据
        self.channels[index].update(new_channel)
        
        # 更新名称和分组缓存
        if 'name' in new_channel:
            self._name_cache.add(new_channel['name'])
        if 'group' in new_channel:
            self._group_cache.add(new_channel['group'])
            
        # 通知视图更新
        self.dataChanged.emit(
            self.index(index, 0),
            self.index(index, self.columnCount() - 1)
        )
        return True

    def update_view(self):
        """批量更新视图"""
        if self.channels:
            top_left = self.index(0, 0)
            bottom_right = self.index(len(self.channels)-1, len(self.headers)-1)
            self.dataChanged.emit(top_left, bottom_right)

    def sort_channels(self):
        """智能排序频道列表"""
        # 定义组名优先级顺序
        group_priority = {
            '央视频道': 0,
            'CETV': 1,
            'CGTN': 2,
            '卫视': 3,
            '国际频道': 4,
            '特色频道': 5,
            '山东频道': 6,
            '市级频道': 7,
            '滨州': 8,
            '德州': 9,
            '东营': 10,
            '菏泽': 11,
            '济南': 12,
            '济宁': 13,
            '聊城': 14,
            '临沂': 15,
            '青岛': 16,
            '日照': 17,
            '泰安': 18,
            '威海': 19,
            '潍坊': 20,
            '烟台': 21,
            '淄博': 22
        }

        def get_resolution_value(resolution):
            """解析分辨率字符串，返回宽度值"""
            if not resolution:
                return 0
            try:
                parts = resolution.split('x')
                if len(parts) == 2:
                    return int(parts[0]) * int(parts[1])  # 返回像素总数
                return 0
            except:
                return 0

        def get_cctv_number(name):
            """解析CCTV频道编号"""
            if not name:
                return 999
                
            # 定义精确的频道顺序
            cctv_order = [
                'CCTV-1 综合',
                'CCTV-2 财经',
                'CCTV-3 综艺',
                'CCTV-4 (亚洲)',
                'CCTV-4 (欧洲)',
                'CCTV-4 (美洲)',
                'CCTV-5 体育',
                'CCTV-5+ 体育赛事',
                'CCTV-6 电影',
                'CCTV-7 国防军事',
                'CCTV-8 电视剧',
                'CCTV-9 纪录',
                'CCTV-10 科教',
                'CCTV-11 戏曲',
                'CCTV-12 社会与法',
                'CCTV-13 新闻',
                'CCTV-14 少儿',
                'CCTV-15 音乐',
                'CCTV-16 奥林匹克',
                'CCTV-17 农业农村',
                'CCTV-4K 超高清',
                'CCTV-8K 超高清',
                'CCTV-中视购物',
                '央广购物'
            ]
            
            # 查找频道在顺序列表中的位置
            for i, channel_name in enumerate(cctv_order):
                if channel_name in name:  # 部分匹配
                    return i
                    
            # 非CCTV频道或未匹配的频道
            return 999

        def get_group_priority(group):
            """获取组名优先级"""
            if not group:
                return len(group_priority) + 1  # 未分类的组放在最后
            for key in group_priority:
                if key in group:  # 部分匹配
                    return group_priority[key]
            return len(group_priority) + 1  # 未匹配的组放在最后

        # 开始排序
        self.beginResetModel()
        
        # 先按分辨率分组(1920x1080及以上为一组)
        hd_threshold = 1920 * 1080
        self.channels.sort(key=lambda x: (
            get_resolution_value(x.get('resolution', '')) < hd_threshold,  # False(高分辨率)在前
            get_group_priority(x.get('group', '')),  # 按组优先级
            get_cctv_number(x.get('name', '')) if '央视频道' in x.get('group', '') else 0,  # CCTV频道特殊排序
            x.get('name', '')  # 按频道名称字母顺序
        ))
        
        self.endResetModel()

    def parse_file_content(self, content: str) -> List[Dict[str, Any]]:
        """解析文件内容并返回频道列表"""
        try:
            channels = []
            name_cache = set()
            group_cache = set()
            lines = content.splitlines()
            current_channel = None
            
            # Excel文件现在由list_manager.py处理
            # 这里只处理文本内容
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                    
                # 处理M3U文件头
                if line == "#EXTM3U":
                    continue
                    
                # 处理EXTINF行
                if line.startswith("#EXTINF:"):
                    # 找到最后一个逗号作为频道名分隔符
                    last_comma = line.rfind(",")
                    if last_comma > 0:
                        # 分割属性部分和频道名称部分
                        attrs_part = line[8:last_comma].strip()  # 去掉#EXTINF:
                        name = line[last_comma+1:].strip()
                        
                        # 处理带引号的频道名
                        if name.startswith('"') and name.endswith('"'):
                            name = name[1:-1]
                        
                        # 初始化频道信息
                        current_channel = {
                            'name': name,
                            'group': "未分类",
                            'tvg_id': "",
                            'logo': "",
                            'valid': False,
                            'status': '待检测'
                        }
                        
                        # 解析各个属性
                        attrs = attrs_part.split()
                        for attr in attrs:
                            if "=" in attr:
                                key, value = attr.split("=", 1)
                                value = value.strip('"')
                                if key == "group-title":
                                    current_channel['group'] = value
                                elif key == "tvg-id":
                                    current_channel['tvg_id'] = value
                                elif key == "tvg-logo":
                                    current_channel['logo'] = value
                    continue
                    
                # 处理分辨率标签
                if line.startswith("#EXTVLCOPT:video-resolution=") and current_channel:
                    resolution = line.split("=")[1].strip()
                    current_channel['resolution'] = resolution
                    
                # 处理URL行
                if line and not line.startswith("#") and current_channel:
                    current_channel['url'] = line
                    channels.append(current_channel)
                    # 更新名称和分组缓存
                    if 'name' in current_channel:
                        name_cache.add(current_channel['name'])
                    if 'group' in current_channel:
                        group_cache.add(current_channel['group'])
                    current_channel = None
            
            return channels
        except Exception as e:
            logger.error(f"频道模型-解析文件内容失败: {str(e)}", exc_info=True)
            return None

    def load_from_file(self, content: str) -> bool:
        """从文件内容加载频道列表"""
        try:
            self.beginResetModel()
            self.channels = []
            self._name_cache = set()
            self._group_cache = set()
            
            channels = self.parse_file_content(content)
            if channels is None:
                return False
                
            self.channels = channels
            self._name_cache = set(c['name'] for c in channels if 'name' in c)
            self._group_cache = set(c['group'] for c in channels if 'group' in c)
            
            # 通知UI更新状态标签
            if hasattr(self, 'update_status_label'):
                self.update_status_label("请点击检测有效性按钮")
            
            self.endResetModel()
            
            # 数据加载完成后调整列宽
            view = self.parent()
            if view and hasattr(view, 'resizeColumnsToContents'):
                view.resizeColumnsToContents()
                
            return True
        except Exception as e:
            logger.error(f"频道模型-加载频道列表失败: {str(e)}", exc_info=True)
            return False
