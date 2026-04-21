"""
订阅UI控制器 - 管理订阅设置对话框中的所有UI逻辑
从 pyqt_player.py 提取的独立模块
"""

from PyQt6.QtWidgets import QListWidgetItem, QApplication, QListWidget
from PyQt6 import QtCore


class SubscriptionUIController:
    """订阅UI控制器 - 管理订阅源设置对话框的所有逻辑"""

    def __init__(self, main_window):
        self.window = main_window

    def load_subscription_sources_to_ui(self, playlist_list_widget=None, epg_list_widget=None):
        """加载订阅源到UI控件（入口方法）"""
        from core.log_manager import global_logger as logger

        if playlist_list_widget and epg_list_widget:
            logger.info("load_subscription_sources_to_ui: 使用传入的参数")
            self._fill_widgets(playlist_list_widget, epg_list_widget)
            return

        logger.info("load_subscription_sources_to_ui: 参数为空，开始查找dialog中的QListWidget...")
        for top_widget in QApplication.topLevelWidgets():
            found = top_widget.findChildren(QListWidget)
            logger.info(f"  检查顶层窗口 {type(top_widget).__name__}: 找到 {len(found)} 个QListWidget")
            if len(found) >= 2:
                logger.info(f"  找到足够的widget，调用 _fill_widgets")
                result = self._fill_widgets(found[0], found[1])
                logger.info(f"  _fill_widgets 返回: {result}")
                return

        logger.warning("load_subscription_sources_to_ui: 未找到足够的QListWidget")

    def _fill_widgets(self, pl_widget, epg_widget):
        """实际填充数据到widget（独立方法，确保参数不会丢失）"""
        from core.log_manager import global_logger as logger
        from core.subscription_manager import global_subscription_manager

        logger.info(f"_fill_widgets: pl_widget={type(pl_widget).__name__}, epg_widget={type(epg_widget).__name__}")

        pl_widget.clear()

        try:
            playlist_sources = global_subscription_manager.get_playlist_sources()
            logger.info(f"加载直播源列表: {len(playlist_sources)} 个源")
        except Exception as e:
            logger.error(f"获取直播源列表失败: {e}")
            playlist_sources = []

        for source in playlist_sources:
            item = QListWidgetItem(f"{'✓ ' if source.get('enabled') else '  '}{source.get('name', 'Unnamed')}")
            item.setData(QtCore.Qt.ItemDataRole.UserRole, source)
            item.setFlags(item.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                QtCore.Qt.CheckState.Checked if source.get('enabled') else QtCore.Qt.CheckState.Unchecked
            )
            item.setToolTip(source.get('url', ''))
            pl_widget.addItem(item)

        epg_widget.clear()

        try:
            epg_sources = global_subscription_manager.get_epg_sources()
            logger.info(f"加载EPG源列表: {len(epg_sources)} 个源")
        except Exception as e:
            logger.error(f"获取EPG源列表失败: {e}")
            epg_sources = []

        for source in epg_sources:
            item = QListWidgetItem(f"{source.get('name', 'Unnamed')}")
            item.setData(QtCore.Qt.ItemDataRole.UserRole, source)
            item.setToolTip(source.get('url', ''))
            epg_widget.addItem(item)

        logger.info("_fill_widgets: 填充完成")
        return True

    def add_or_update_playlist_source(self):
        """从UI添加或更新直播源"""
        from core.subscription_manager import global_subscription_manager
        tr = getattr(self.window.language_manager, 'tr', lambda x, y: x) if hasattr(self.window, 'language_manager') else lambda x, y: x

        url = self.window.playlist_new_url_edit.text().strip()
        name = self.window.playlist_new_name_edit.text().strip() or None

        if not url:
            return

        if self.window._editing_playlist_index >= 0:
            global_subscription_manager.update_playlist_source(self.window._editing_playlist_index, url, name)
            sources = global_subscription_manager.get_playlist_sources()
            updated_source = sources[self.window._editing_playlist_index]

            item = self.window.playlist_list_widget.item(self.window._editing_playlist_index)
            if item:
                item.setText(f"{'✓ ' if updated_source.get('enabled') else '  '}{updated_source.get('name', 'Unnamed')}")
                item.setData(QtCore.Qt.ItemDataRole.UserRole, updated_source)
                item.setToolTip(updated_source.get('url', ''))

            self.window._editing_playlist_index = -1
            self.window._playlist_add_btn.setText(tr("add_source", "+ Add Source"))
        else:
            index = global_subscription_manager.add_playlist_source(url, name)
            sources = global_subscription_manager.get_playlist_sources()
            new_source = sources[index]

            item = QListWidgetItem(f"{'✓ ' if new_source.get('enabled') else '  '}{new_source.get('name', 'Unnamed')}")
            item.setData(QtCore.Qt.ItemDataRole.UserRole, new_source)
            item.setFlags(item.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                QtCore.Qt.CheckState.Checked if new_source.get('enabled') else QtCore.Qt.CheckState.Unchecked
            )
            item.setToolTip(new_source.get('url', ''))
            self.window.playlist_list_widget.addItem(item)

        self.window.playlist_new_url_edit.clear()
        self.window.playlist_new_name_edit.clear()

    def edit_playlist_source(self, item):
        """编辑选中的直播源：将数据回填到输入框"""
        if not item:
            return

        current_row = self.window.playlist_list_widget.row(item)
        if current_row < 0:
            return

        source = item.data(QtCore.Qt.ItemDataRole.UserRole)
        if not source:
            return

        self.window.playlist_new_url_edit.setText(source.get('url', ''))
        self.window.playlist_new_name_edit.setText(source.get('name', ''))

        self.window._editing_playlist_index = current_row
        tr = getattr(self.window.language_manager, 'tr', lambda x, y: x) if hasattr(self.window, 'language_manager') else lambda x, y: x
        self.window._playlist_add_btn.setText(tr("update_source", "✎ Update"))

    def remove_selected_playlist_source(self):
        """删除选中的直播源"""
        from core.subscription_manager import global_subscription_manager
        tr = getattr(self.window.language_manager, 'tr', lambda x, y: x) if hasattr(self.window, 'language_manager') else lambda x, y: x

        current_row = self.window.playlist_list_widget.currentRow()
        if current_row < 0:
            return

        global_subscription_manager.remove_playlist_source(current_row)
        self.window.playlist_list_widget.takeItem(current_row)

        if self.window._editing_playlist_index == current_row:
            self.window._editing_playlist_index = -1
            self.window._playlist_add_btn.setText(tr("add_source", "+ Add Source"))
            self.window.playlist_new_url_edit.clear()
            self.window.playlist_new_name_edit.clear()
        elif self.window._editing_playlist_index > current_row:
            self.window._editing_playlist_index -= 1

    def activate_playlist_source(self, item):
        """激活指定的直播源（点击切换，仅更新UI，保存时才生效）"""
        index = self.window.playlist_list_widget.row(item)
        if index >= 0:
            for i in range(self.window.playlist_list_widget.count()):
                list_item = self.window.playlist_list_widget.item(i)
                source = list_item.data(QtCore.Qt.ItemDataRole.UserRole)
                if source:
                    source['enabled'] = (i == index)
                    check_state = (
                        QtCore.Qt.CheckState.Checked if i == index 
                        else QtCore.Qt.CheckState.Unchecked
                    )
                    list_item.setCheckState(check_state)
                    prefix = '✓ ' if i == index else '  '
                    list_item.setText(f"{prefix}{source.get('name', 'Unnamed')}")

    def add_or_update_epg_source(self):
        """从UI添加或更新EPG源"""
        from core.subscription_manager import global_subscription_manager
        tr = getattr(self.window.language_manager, 'tr', lambda x, y: x) if hasattr(self.window, 'language_manager') else lambda x, y: x

        url = self.window.epg_new_url_edit.text().strip()
        name = self.window.epg_new_name_edit.text().strip() or None

        if not url:
            return

        if self.window._editing_epg_index >= 0:
            global_subscription_manager.update_epg_source(self.window._editing_epg_index, url, name)
            sources = global_subscription_manager.get_epg_sources()
            updated_source = sources[self.window._editing_epg_index]

            item = self.window.epg_list_widget.item(self.window._editing_epg_index)
            if item:
                item.setText(updated_source.get('name', 'Unnamed'))
                item.setData(QtCore.Qt.ItemDataRole.UserRole, updated_source)
                item.setToolTip(updated_source.get('url', ''))

            self.window._editing_epg_index = -1
            self.window._epg_add_btn.setText(tr("add_source", "+ Add Source"))
        else:
            index = global_subscription_manager.add_epg_source(url, name)
            sources = global_subscription_manager.get_epg_sources()
            new_source = sources[index]

            item = QListWidgetItem(new_source.get('name', 'Unnamed'))
            item.setData(QtCore.Qt.ItemDataRole.UserRole, new_source)
            item.setToolTip(new_source.get('url', ''))
            self.window.epg_list_widget.addItem(item)

        self.window.epg_new_url_edit.clear()
        self.window.epg_new_name_edit.clear()

    def edit_epg_source(self, item):
        """编辑选中的EPG源：将数据回填到输入框"""
        if not item:
            return

        current_row = self.window.epg_list_widget.row(item)
        if current_row < 0:
            return

        source = item.data(QtCore.Qt.ItemDataRole.UserRole)
        if not source:
            return

        self.window.epg_new_url_edit.setText(source.get('url', ''))
        self.window.epg_new_name_edit.setText(source.get('name', ''))

        self.window._editing_epg_index = current_row
        tr = getattr(self.window.language_manager, 'tr', lambda x, y: x) if hasattr(self.window, 'language_manager') else lambda x, y: x
        self.window._epg_add_btn.setText(tr("update_source", "✎ Update"))

    def remove_selected_epg_source(self):
        """删除选中的EPG源"""
        from core.subscription_manager import global_subscription_manager
        tr = getattr(self.window.language_manager, 'tr', lambda x, y: x) if hasattr(self.window, 'language_manager') else lambda x, y: x

        current_row = self.window.epg_list_widget.currentRow()
        if current_row < 0:
            return

        global_subscription_manager.remove_epg_source(current_row)
        self.window.epg_list_widget.takeItem(current_row)

        if self.window._editing_epg_index == current_row:
            self.window._editing_epg_index = -1
            self.window._epg_add_btn.setText(tr("add_source", "+ Add Source"))
            self.window.epg_new_url_edit.clear()
            self.window.epg_new_name_edit.clear()
        elif self.window._editing_epg_index > current_row:
            self.window._editing_epg_index -= 1
