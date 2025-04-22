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
        lines = ["#EXTM3U"]
        for channel in self.channels:
            # EXTINF行 - 包含所有标准M3U标签
            extinf = (
                f"#EXTINF:-1 "
                f"tvg-id=\"{channel.get('tvg_id', '')}\" "
                f"tvg-name=\"{channel.get('name', '未命名')}\" "
                f"tvg-logo=\"{channel.get('logo', '')}\" "
                f"group-title=\"{channel.get('group', '未分类')}\" "
                f"tvg-language=\"{channel.get('language', '')}\" "
                f"tvg-country=\"{channel.get('country', '')}\" "
                f",{channel.get('name', '未命名')}"
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

    def load_from_file(self, content: str) -> bool:
        """从文件内容加载频道列表"""
        try:
            self.beginResetModel()
            self.channels = []
            self._name_cache = set()
            self._group_cache = set()
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
                    # 更新名称和分组缓存
                    if 'name' in current_channel:
                        self._name_cache.add(current_channel['name'])
                    if 'group' in current_channel:
                        self._group_cache.add(current_channel['group'])
                    current_channel = None
            
            self.endResetModel()
            return True
        except Exception as e:
            self.logger.error(f"加载频道列表失败: {str(e)}", exc_info=True)
            return False
