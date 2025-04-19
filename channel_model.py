from PyQt6 import QtCore, QtGui
from typing import List, Dict, Any
from log_manager import LogManager

class ChannelListModel(QtCore.QAbstractTableModel):
    """频道列表数据模型"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = LogManager()
        self.channels: List[Dict[str, Any]] = []
        self.headers = ["频道名称", "分辨率", "URL", "分组", "状态", "延迟(ms)"]
        self.logger.info("频道列表模型初始化完成")
        
        # 状态标签更新回调
        self.update_status_label = None

    def rowCount(self, parent=QtCore.QModelIndex()) -> int:
        """返回行数(频道数量)"""
        return len(self.channels)

    def columnCount(self, parent=QtCore.QModelIndex()) -> int:
        """返回列数"""
        return len(self.headers)

    def data(self, index: QtCore.QModelIndex, role: int = QtCore.Qt.ItemDataRole.DisplayRole):
        """返回单元格数据"""
        if not index.isValid() or not (0 <= index.row() < len(self.channels)):
            self.logger.debug(f"无效的索引请求: row={index.row()}, column={index.column()}")
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
        return QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable

    def get_channel(self, index: int) -> Dict[str, Any]:
        """根据索引获取频道信息"""
        if 0 <= index < len(self.channels):
            return self.channels[index]
        return {}

    def add_channel(self, channel_info: Dict[str, Any]):
        """添加频道到模型"""
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

    def load_from_file(self, content: str) -> bool:
        """从文件内容加载频道列表"""
        try:
            self.beginResetModel()
            self.channels = []
            lines = content.splitlines()
            current_channel = None
            
            # 通知UI更新状态标签
            if hasattr(self, 'update_status_label'):
                self.update_status_label("请点击检测有效性按钮")
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                    
                # 处理M3U文件头
                if line == "#EXTM3U":
                    continue
                    
                # 处理EXTINF行
                if line.startswith("#EXTINF:"):
                    parts = line.split(",", 1)
                    if len(parts) > 1:
                        name = parts[1].strip()
                        # 尝试提取分组信息
                        group = "未分类"
                        if "group-title=" in line:
                            group_start = line.find("group-title=") + 12
                            group_end = line.find('"', group_start)
                            if group_end > group_start:
                                group = line[group_start:group_end]
                        current_channel = {
                            'name': name,
                            'group': group,
                            'valid': False,  # 初始状态为待检测
                            'status': '待检测'
                        }
                    continue
                    
                # 处理URL行
                if line and not line.startswith("#") and current_channel:
                    current_channel['url'] = line
                    self.channels.append(current_channel)
                    current_channel = None
            
            self.endResetModel()
            return True
        except Exception as e:
            self.logger.error(f"加载频道列表失败: {str(e)}", exc_info=True)
            return False
