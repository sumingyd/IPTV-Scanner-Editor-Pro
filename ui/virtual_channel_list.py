from typing import Dict, Any, List, Optional, Callable
from PyQt6.QtWidgets import QListWidget, QListWidgetItem, QWidget
from PyQt6.QtCore import Qt, QTimer, QSize
from core.log_manager import global_logger as logger


class VirtualChannelListProxy:
    BATCH_SIZE = 200
    SCROLL_THRESHOLD = 50

    def __init__(self, list_widget: QListWidget):
        self._list_widget = list_widget
        self._all_channels: List[Dict[str, Any]] = []
        self._loaded_count = 0
        self._is_virtual = False
        self._create_item_func: Optional[Callable] = None
        self._scroll_timer = QTimer()
        self._scroll_timer.setSingleShot(True)
        self._scroll_timer.setInterval(50)
        self._scroll_timer.timeout.connect(self._on_scroll_delayed)

    @property
    def is_virtual(self) -> bool:
        return self._is_virtual

    def set_channels(self, channels: List[Dict[str, Any]],
                     create_item_func: Optional[Callable] = None,
                     force_virtual: bool = False):
        self._all_channels = channels
        self._create_item_func = create_item_func
        self._is_virtual = len(channels) > self.BATCH_SIZE or force_virtual

        if self._is_virtual:
            self._loaded_count = 0
            self._list_widget.clear()
            self._load_more(self.BATCH_SIZE)
            try:
                self._list_widget.verticalScrollBar().valueChanged.connect(
                    self._on_scroll, Qt.ConnectionType.UniqueConnection
                )
            except TypeError:
                pass
        else:
            self._loaded_count = len(channels)
            try:
                self._list_widget.verticalScrollBar().valueChanged.disconnect(self._on_scroll)
            except Exception:
                pass

    def _load_more(self, count: int):
        if not self._all_channels or self._loaded_count >= len(self._all_channels):
            return
        end = min(self._loaded_count + count, len(self._all_channels))
        from ui.styles import AppStyles
        name_style = AppStyles.player_channel_list_name_style()
        from PyQt6 import QtWidgets

        for idx in range(self._loaded_count, end):
            channel = self._all_channels[idx]
            try:
                if self._create_item_func:
                    self._create_item_func(self._list_widget, idx, channel)
                else:
                    channel_name = channel.get('name', 'Unnamed')
                    item_widget = QtWidgets.QWidget()
                    item_layout = QtWidgets.QHBoxLayout(item_widget)
                    item_layout.setContentsMargins(5, 2, 5, 2)
                    item_layout.setSpacing(8)

                    logo_label = QtWidgets.QLabel()
                    logo_label.setFixedSize(44, 32)
                    logo_label.setStyleSheet("background-color: transparent; border: none;")
                    logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    logo_label.setObjectName("channel_logo_label")

                    name_label = QtWidgets.QLabel(channel_name)
                    name_label.setStyleSheet(name_style)
                    name_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
                    name_label.setWordWrap(False)

                    item_layout.addWidget(logo_label, 0, Qt.AlignmentFlag.AlignVCenter)
                    item_layout.addWidget(name_label, 1, Qt.AlignmentFlag.AlignVCenter)

                    item = QListWidgetItem()
                    item.setSizeHint(QSize(0, 40))
                    item.setData(Qt.ItemDataRole.UserRole, idx)
                    self._list_widget.addItem(item)
                    self._list_widget.setItemWidget(item, item_widget)
            except Exception as e:
                logger.debug(f"虚拟列表加载项失败: {e}")

        self._loaded_count = end
        logger.debug(f"虚拟列表: 已加载 {self._loaded_count}/{len(self._all_channels)}")

    def _on_scroll(self, value):
        self._scroll_timer.start()

    def _on_scroll_delayed(self):
        if not self._is_virtual:
            return
        scrollbar = self._list_widget.verticalScrollBar()
        if scrollbar.value() >= scrollbar.maximum() - self.SCROLL_THRESHOLD:
            remaining = len(self._all_channels) - self._loaded_count
            if remaining > 0:
                self._load_more(min(self.BATCH_SIZE, remaining))

    def get_total_count(self) -> int:
        return len(self._all_channels)

    def get_loaded_count(self) -> int:
        return self._loaded_count

    def ensure_loaded(self, index: int):
        if not self._is_virtual:
            return
        if index >= self._loaded_count:
            self._load_more(index - self._loaded_count + self.BATCH_SIZE)

    def reset(self):
        self._all_channels = []
        self._loaded_count = 0
        self._is_virtual = False
        self._list_widget.clear()