from typing import Optional, Dict, Any, List
from PyQt6 import QtCore, QtGui
from PyQt6.QtCore import Qt, QModelIndex

class ChannelListModel(QtCore.QAbstractTableModel):
    def __init__(self, data: Optional[List[Dict]] = None):
        super().__init__()
        self.channels = data if data is not None else []
        self.headers = ["频道名称", "分辨率", "URL", "分组", "状态", "延迟(ms)"]

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None
            
        if role == Qt.ItemDataRole.DisplayRole:
            chan = self.channels[index.row()]
            if index.column() == 0:
                return chan.get('name', '未命名频道')
            elif index.column() == 1:
                return f"{chan.get('width', 0)}x{chan.get('height', 0)}"
            elif index.column() == 2:
                return chan.get('url', '无地址')
            elif index.column() == 3:
                return chan.get('group', '未分类')
            elif index.column() == 4:
                if 'valid' in chan:
                    if chan.get('validating', False):
                        return "⏳"
                    return "✓" if chan['valid'] else "✗"
                return ""
            elif index.column() == 5:
                if 'latency' in chan and chan['latency'] > 0:
                    return f"{int(chan['latency']*1000)}ms"
                return ""
        elif role == Qt.ItemDataRole.UserRole:
            return self.channels[index.row()]
        elif role == Qt.ItemDataRole.ForegroundRole:
            if index.column() == 4:
                if 'valid' in self.channels[index.row()]:
                    return QtGui.QColor('#4CAF50') if self.channels[index.row()]['valid'] else QtGui.QColor('#F44336')
        elif role == Qt.ItemDataRole.TextAlignmentRole:
            if index.column() in (4, 5):
                return Qt.AlignmentFlag.AlignCenter
        return None

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self.channels)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self.headers)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.headers[section]
        return None
