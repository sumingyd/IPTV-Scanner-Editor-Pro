from PyQt6 import QtCore, QtGui
from typing import List, Dict, Any
from log_manager import LogManager
logger = LogManager()

class ChannelListModel(QtCore.QAbstractTableModel):
    """频道列表数据模型"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.channels: List[Dict[str, Any]] = []
        self.headers = ["频道名称", "分辨率", "URL", "分组", "状态", "延迟(ms)"]
        
        # 状态标签更新回调
        self.update_status_label = None
        
        # 频道名称和分组缓存(用于自动补全)
        self._name_cache = set()
        self._group_cache = set()

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
            if col == 0:  # 频道名称
                return channel.get('name', '未命名')
            elif col == 1:  # 分辨率
                return channel.get('resolution', '')
            elif col == 2:  # URL
                return channel.get('url', '')
            elif col == 3:  # 分组
                return channel.get('group', '未分类')
            elif col == 4:  # 状态
                return channel.get('status', '待检测')
            elif col == 5:  # 延迟(ms)
                return str(channel.get('latency', ''))
        elif role == QtCore.Qt.ItemDataRole.TextAlignmentRole:
            return QtCore.Qt.AlignmentFlag.AlignVCenter | QtCore.Qt.AlignmentFlag.AlignLeft
        elif role == QtCore.Qt.ItemDataRole.BackgroundRole:
            if not channel.get('valid', True):
                return QtGui.QColor('#ffdddd')  # 无效项背景色
        elif role == QtCore.Qt.ItemDataRole.ForegroundRole:
            if not channel.get('valid', True):
                return QtGui.QColor('#333333')  # 无效项文字颜色
            elif channel.get('status') == '待检测':
                return QtGui.QColor('#333333')  # 待检测文字颜色
        return None

    def headerData(self, section: int, orientation: QtCore.Qt.Orientation,
                  role: int = QtCore.Qt.ItemDataRole.DisplayRole):
        """返回表头数据"""
        if role != QtCore.Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == QtCore.Qt.Orientation.Horizontal:
            return self.headers[section]
        return str(section + 1)

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
        # 检查是否已存在相同URL的频道
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
        else:
            # 添加新频道
            self.beginInsertRows(QtCore.QModelIndex(), len(self.channels), len(self.channels))
            self.channels.append(channel_info)
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
        lines = ["#EXTM3U"]
        for channel in self.channels:
            # 获取频道信息(包含logo地址)
            channel_info = get_channel_info(channel.get('name', ''))
            
            # EXTINF行 - 包含所有标准M3U标签
            extinf = (
                f"#EXTINF:-1 "
                f"tvg-id=\"{channel.get('tvg_id', '')}\" "
                f"tvg-name=\"{channel_info['standard_name']}\" "
                f"tvg-logo=\"{channel_info.get('logo_url', channel.get('logo', ''))}\" "
                f"group-title=\"{channel.get('group', '未分类')}\" "
                f"tvg-language=\"{channel.get('language', '')}\" "
                f"tvg-country=\"{channel.get('country', '')}\" "
                f",{channel_info['standard_name']}"
            )
            lines.append(extinf)
            
            # 添加其他扩展属性
            if channel.get('resolution'):
                lines.append(f"#EXTVLCOPT:video-resolution={channel.get('resolution')}")
            if channel.get('latency'):
                lines.append(f"#EXTVLCOPT:network-caching={channel.get('latency')}")
            
            # URL行
            lines.append(channel.get('url', ''))
        
        # 添加来源信息
        lines.append("\n# Generated by IPTV Scanner Editor Pro")
        lines.append("# GitHub: https://github.com/your-repo/IPTV-Scanner-Editor-Pro")
        return "\n".join(lines)

    def to_txt(self) -> str:
        """将频道列表转换为TXT格式字符串"""
        lines = []
        for channel in self.channels:
            # 简单格式: 频道名称,URL
            line = f"{channel.get('name', '未命名')},{channel.get('url', '')}"
            lines.append(line)
        return "\n".join(lines)

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

    def update_view(self):
        """批量更新视图"""
        if self.channels:
            top_left = self.index(0, 0)
            bottom_right = self.index(len(self.channels)-1, len(self.headers)-1)
            self.dataChanged.emit(top_left, bottom_right)

    def parse_file_content(self, content: str) -> List[Dict[str, Any]]:
        """解析文件内容并返回频道列表"""
        try:
            channels = []
            name_cache = set()
            group_cache = set()
            lines = content.splitlines()
            current_channel = None
            
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
            return True
        except Exception as e:
            logger.error(f"频道模型-加载频道列表失败: {str(e)}", exc_info=True)
            return False
