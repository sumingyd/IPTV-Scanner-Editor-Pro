from PyQt6 import QtCore, QtWidgets
from core.log_manager import LogManager
from ui.styles import AppStyles


class SortConfigDialog(QtWidgets.QDialog):
    """排序配置对话框"""

    def __init__(self, parent=None, model=None):
        super().__init__(parent)
        self.logger = LogManager()
        self.model = model
        self.language_manager = None

        # 排序条件选项
        self.sort_fields = [
            ('group', '分组'),
            ('name', '名称'),
            ('resolution', '分辨率'),
            ('latency', '延迟'),
            ('status', '状态')
        ]

        # 排序方式选项（使用国际化键）
        self.sort_methods = {
            'group': [
                ('custom', 'custom_order'),
                ('alphabetical', 'alphabetical'),
                ('reverse_alphabetical', 'reverse_alphabetical')
            ],
            'name': [
                ('alphabetical', 'alphabetical'),
                ('reverse_alphabetical', 'reverse_alphabetical'),
                ('pinyin', 'pinyin')
            ],
            'resolution': [
                ('quality_high_to_low', 'quality_high_to_low'),
                ('quality_low_to_high', 'quality_low_to_high'),
                ('width_high_to_low', 'width_high_to_low'),
                ('width_low_to_high', 'width_low_to_high')
            ],
            'latency': [
                ('low_to_high', 'low_to_high'),
                ('high_to_low', 'high_to_low')
            ],
            'status': [
                ('valid_first', 'valid_first'),
                ('invalid_first', 'invalid_first')
            ]
        }

        # 从配置文件加载排序配置
        self.sort_config = self.load_config_from_file()

        # 分组优先级列表
        self.group_priority = []

        self.init_ui()
        # 先尝试从配置加载分组优先级，如果没有配置再加载默认分组
        if not self.load_group_priority_from_config():
            self.load_group_priority()

    def set_language_manager(self, language_manager):
        """设置语言管理器"""
        self.language_manager = language_manager
        self.update_ui_texts()

    def update_ui_texts(self):
        """更新UI文本"""
        if not self.language_manager:
            return

        # 更新对话框标题
        self.setWindowTitle(self.language_manager.tr('sort_config', 'Sort Configuration'))

        # 更新标签文本
        self.priority_label.setText(self.language_manager.tr('sort_priority', 'Sort Priority'))
        self.group_priority_label.setText(self.language_manager.tr('group_priority', 'Group Priority'))

        # 更新按钮文本
        self.apply_btn.setText(self.language_manager.tr('apply_sort', 'Apply Sort'))
        self.cancel_btn.setText(self.language_manager.tr('cancel', 'Cancel'))

        # 更新排序字段显示名称
        field_mapping = {
            'group': self.language_manager.tr('channel_group', 'Group'),
            'name': self.language_manager.tr('channel_name', 'Name'),
            'resolution': self.language_manager.tr('resolution', 'Resolution'),
            'latency': self.language_manager.tr('latency', 'Latency'),
            'status': self.language_manager.tr('status', 'Status')
        }

        # 更新下拉框选项
        for i, (field_key, _) in enumerate(self.sort_fields):
            display_name = field_mapping.get(field_key, field_key)
            self.primary_combo.setItemText(i, display_name)
            self.secondary_combo.setItemText(i, display_name)
            self.tertiary_combo.setItemText(i, display_name)

        # 更新优先级行标签
        self.primary_row_label.setText(self.language_manager.tr('primary_priority', 'Primary Priority'))
        self.secondary_row_label.setText(self.language_manager.tr('secondary_priority', 'Secondary Priority'))
        self.tertiary_row_label.setText(self.language_manager.tr('tertiary_priority', 'Tertiary Priority'))

        # 更新方法标签
        self.primary_method_label.setText(self.language_manager.tr('sort_method', 'Sort Method'))
        self.secondary_method_label.setText(self.language_manager.tr('sort_method', 'Sort Method'))
        self.tertiary_method_label.setText(self.language_manager.tr('sort_method', 'Sort Method'))

        # 重新加载排序方式下拉框的国际化文本
        self.reload_method_combo_texts()

        # 更新分组提示信息
        self.update_group_hint()

        # 更新拖拽提示信息
        drag_hint_text = self.language_manager.tr(
            'drag_hint',
            '💡 Tip: Drag group names to adjust priority order. '
            'Insertion position will be shown during dragging.')
        self.drag_hint_label.setText(drag_hint_text)

    def update_group_hint(self):
        """更新分组优先级提示信息"""
        if not self.language_manager:
            return

        # 使用 is_list_empty 方法来判断频道列表是否为空
        if self.is_list_empty():
            # 列表为空的情况 - 从配置文件加载
            hint_text = self.language_manager.tr(
                'group_hint_empty',
                'Tip: The channel list is currently empty. '
                'Groups are loaded from saved configuration. '
                'You can drag to adjust their priority order.')
        else:
            # 列表不为空的情况
            hint_text = self.language_manager.tr(
                'group_hint_normal',
                'Tip: The following shows all group names from the current list. '
                'You can drag to adjust their priority order.')

        self.group_hint_label.setText(hint_text)

    def init_ui(self):
        """初始化用户界面"""
        self.setWindowTitle("排序配置")
        self.setModal(True)
        self.resize(600, 700)

        # 应用统一的对话框样式和按钮样式
        self.setStyleSheet(AppStyles.dialog_style() + AppStyles.button_style())

        # 主布局
        main_layout = QtWidgets.QVBoxLayout(self)

        # 排序优先级设置区域
        self.priority_label = QtWidgets.QLabel("排序优先级设置：")
        main_layout.addWidget(self.priority_label)

        # 优先级设置表单
        priority_layout = QtWidgets.QFormLayout()

        # 第一优先级
        primary_layout = QtWidgets.QHBoxLayout()
        self.primary_combo = QtWidgets.QComboBox()
        for field_key, field_name in self.sort_fields:
            self.primary_combo.addItem(field_name, field_key)
        primary_layout.addWidget(self.primary_combo)

        primary_layout.addSpacing(10)
        self.primary_method_label = QtWidgets.QLabel("排序方式：")
        primary_layout.addWidget(self.primary_method_label)

        self.primary_method_combo = QtWidgets.QComboBox()
        primary_layout.addWidget(self.primary_method_combo)
        primary_layout.addStretch()

        self.primary_row_label = QtWidgets.QLabel("第一优先级：")
        priority_layout.addRow(self.primary_row_label, primary_layout)

        # 第二优先级
        secondary_layout = QtWidgets.QHBoxLayout()
        self.secondary_combo = QtWidgets.QComboBox()
        for field_key, field_name in self.sort_fields:
            self.secondary_combo.addItem(field_name, field_key)
        secondary_layout.addWidget(self.secondary_combo)

        secondary_layout.addSpacing(10)
        self.secondary_method_label = QtWidgets.QLabel("排序方式：")
        secondary_layout.addWidget(self.secondary_method_label)

        self.secondary_method_combo = QtWidgets.QComboBox()
        secondary_layout.addWidget(self.secondary_method_combo)
        secondary_layout.addStretch()

        self.secondary_row_label = QtWidgets.QLabel("第二优先级：")
        priority_layout.addRow(self.secondary_row_label, secondary_layout)

        # 第三优先级
        tertiary_layout = QtWidgets.QHBoxLayout()
        self.tertiary_combo = QtWidgets.QComboBox()
        for field_key, field_name in self.sort_fields:
            self.tertiary_combo.addItem(field_name, field_key)
        tertiary_layout.addWidget(self.tertiary_combo)

        tertiary_layout.addSpacing(10)
        self.tertiary_method_label = QtWidgets.QLabel("排序方式：")
        tertiary_layout.addWidget(self.tertiary_method_label)

        self.tertiary_method_combo = QtWidgets.QComboBox()
        tertiary_layout.addWidget(self.tertiary_method_combo)
        tertiary_layout.addStretch()

        self.tertiary_row_label = QtWidgets.QLabel("第三优先级：")
        priority_layout.addRow(self.tertiary_row_label, tertiary_layout)

        main_layout.addLayout(priority_layout)
        main_layout.addSpacing(20)

        # 分组优先级设置区域
        self.group_priority_label = QtWidgets.QLabel("分组优先级设置：")
        main_layout.addWidget(self.group_priority_label)

        # 添加提示信息
        self.group_hint_label = QtWidgets.QLabel("")
        self.group_hint_label.setStyleSheet(AppStyles.group_hint_label_style())
        self.group_hint_label.setWordWrap(True)
        main_layout.addWidget(self.group_hint_label)

        # 分组列表控件 - 改进拖拽体验
        self.group_list_widget = QtWidgets.QListWidget()
        self.group_list_widget.setDragDropMode(QtWidgets.QAbstractItemView.DragDropMode.InternalMove)
        self.group_list_widget.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.group_list_widget.setDropIndicatorShown(True)  # 显示拖拽指示器
        self.group_list_widget.setDefaultDropAction(QtCore.Qt.DropAction.MoveAction)  # 设置默认拖拽动作为移动
        self.group_list_widget.setStyleSheet(AppStyles.drag_list_style())

        main_layout.addWidget(self.group_list_widget)

        # 添加拖拽操作提示
        self.drag_hint_label = QtWidgets.QLabel("")
        self.drag_hint_label.setStyleSheet(AppStyles.drag_hint_label_style())
        self.drag_hint_label.setWordWrap(True)
        main_layout.addWidget(self.drag_hint_label)

        # 按钮区域
        button_layout = QtWidgets.QHBoxLayout()
        self.apply_btn = QtWidgets.QPushButton("应用排序")
        self.apply_btn.setStyleSheet(AppStyles.apply_button_style())
        self.apply_btn.clicked.connect(self.apply_sort)

        self.cancel_btn = QtWidgets.QPushButton("取消")
        self.cancel_btn.setStyleSheet(AppStyles.cancel_button_style())
        self.cancel_btn.clicked.connect(self.reject)

        button_layout.addStretch()
        button_layout.addWidget(self.apply_btn)
        button_layout.addWidget(self.cancel_btn)

        main_layout.addLayout(button_layout)

        # 连接信号
        self.primary_combo.currentTextChanged.connect(self.on_primary_field_changed)
        self.secondary_combo.currentTextChanged.connect(self.on_secondary_field_changed)
        self.tertiary_combo.currentTextChanged.connect(self.on_tertiary_field_changed)
        self.primary_method_combo.currentTextChanged.connect(self.update_group_priority_enabled)

        # 加载默认配置
        self.load_default_config()

    def on_primary_field_changed(self):
        """第一优先级字段改变时更新排序方式选项"""
        field_key = self.primary_combo.currentData()
        self.update_method_combo(self.primary_method_combo, field_key)

    def on_secondary_field_changed(self):
        """第二优先级字段改变时更新排序方式选项"""
        field_key = self.secondary_combo.currentData()
        self.update_method_combo(self.secondary_method_combo, field_key)

    def on_tertiary_field_changed(self):
        """第三优先级字段改变时更新排序方式选项"""
        field_key = self.tertiary_combo.currentData()
        self.update_method_combo(self.tertiary_method_combo, field_key)

    def update_method_combo(self, combo, field_key):
        """更新排序方式下拉框选项"""
        combo.clear()
        methods = self.sort_methods.get(field_key, [])
        for method_key, method_name_key in methods:
            # 使用国际化文本
            display_name = (self.language_manager.tr(method_name_key, method_name_key)
                            if self.language_manager else method_name_key)
            combo.addItem(display_name, method_key)

        # 检查是否需要禁用分组自定义排序
        self.update_group_priority_enabled()

    def update_group_priority_enabled(self):
        """更新分组自定义排序的启用状态"""
        # 检查第一优先级是否是分组且排序方式不是自定义
        primary_field = self.primary_combo.currentData()
        primary_method = self.primary_method_combo.currentData() if self.primary_method_combo.count() > 0 else None

        # 如果第一优先级是分组且排序方式不是自定义，则禁用分组自定义排序
        if primary_field == 'group' and primary_method != 'custom':
            self.group_list_widget.setEnabled(False)
            self.group_priority_label.setEnabled(False)
        else:
            self.group_list_widget.setEnabled(True)
            self.group_priority_label.setEnabled(True)

    def reload_method_combo_texts(self):
        """重新加载排序方式下拉框的国际化文本"""
        if not self.language_manager:
            return

        # 重新加载所有排序方式下拉框的文本
        for combo in [self.primary_method_combo, self.secondary_method_combo, self.tertiary_method_combo]:
            if combo.count() > 0:
                # 保存当前选中的方法
                current_method = combo.currentData()

                # 重新设置所有项的文本
                for i in range(combo.count()):
                    method_key = combo.itemData(i)
                    # 找到对应的国际化键
                    method_name_key = None
                    for field_methods in self.sort_methods.values():
                        for mk, mnk in field_methods:
                            if mk == method_key:
                                method_name_key = mnk
                                break
                        if method_name_key:
                            break

                    if method_name_key:
                        display_name = self.language_manager.tr(method_name_key, method_name_key)
                        combo.setItemText(i, display_name)

                # 恢复选中的方法
                for i in range(combo.count()):
                    if combo.itemData(i) == current_method:
                        combo.setCurrentIndex(i)
                        break

    def load_group_priority(self):
        """从模型中加载分组优先级"""
        if not self.model:
            return

        # 获取所有分组
        groups = set()
        for i in range(self.model.rowCount()):
            channel = self.model.get_channel(i)
            group = channel.get('group', '未分类')
            groups.add(group)

        # 添加到分组列表
        self.group_list_widget.clear()
        for group in sorted(groups):
            item = QtWidgets.QListWidgetItem(group)
            self.group_list_widget.addItem(item)

        # 如果没有分组，添加默认分组
        if self.group_list_widget.count() == 0:
            default_groups = ['央视频道', '卫视', '国际频道', '特色频道', '山东频道', '市级频道', '未分类']
            for group in default_groups:
                item = QtWidgets.QListWidgetItem(group)
                self.group_list_widget.addItem(item)

        # 更新提示信息
        self.update_group_hint()

    def is_list_empty(self):
        """检查频道列表是否为空"""
        if not self.model:
            return True
        return self.model.rowCount() == 0

    def load_default_config(self):
        """加载默认排序配置"""
        # 设置下拉框选中项
        for i in range(self.primary_combo.count()):
            if self.primary_combo.itemData(i) == self.sort_config['primary']['field']:
                self.primary_combo.setCurrentIndex(i)
                break

        for i in range(self.secondary_combo.count()):
            if self.secondary_combo.itemData(i) == self.sort_config['secondary']['field']:
                self.secondary_combo.setCurrentIndex(i)
                break

        for i in range(self.tertiary_combo.count()):
            if self.tertiary_combo.itemData(i) == self.sort_config['tertiary']['field']:
                self.tertiary_combo.setCurrentIndex(i)
                break

        # 更新排序方式下拉框
        self.update_method_combo(self.primary_method_combo, self.sort_config['primary']['field'])
        self.update_method_combo(self.secondary_method_combo, self.sort_config['secondary']['field'])
        self.update_method_combo(self.tertiary_method_combo, self.sort_config['tertiary']['field'])

        # 设置排序方式
        for i in range(self.primary_method_combo.count()):
            if self.primary_method_combo.itemData(i) == self.sort_config['primary']['method']:
                self.primary_method_combo.setCurrentIndex(i)
                break

        for i in range(self.secondary_method_combo.count()):
            if self.secondary_method_combo.itemData(i) == self.sort_config['secondary']['method']:
                self.secondary_method_combo.setCurrentIndex(i)
                break

        for i in range(self.tertiary_method_combo.count()):
            if self.tertiary_method_combo.itemData(i) == self.sort_config['tertiary']['method']:
                self.tertiary_method_combo.setCurrentIndex(i)
                break

        # 加载分组优先级顺序
        self.load_group_priority_from_config()

    def load_group_priority_from_config(self):
        """从配置中加载分组优先级顺序"""
        if not self.sort_config.get('group_priority'):
            return False

        # 清空当前列表
        self.group_list_widget.clear()

        # 按照配置中的顺序添加分组
        for group in self.sort_config['group_priority']:
            item = QtWidgets.QListWidgetItem(group)
            self.group_list_widget.addItem(item)

        return True

    def get_sort_config(self):
        """获取排序配置"""
        config = {
            'primary': {
                'field': self.primary_combo.currentData(),
                'method': self.primary_method_combo.currentData()
            },
            'secondary': {
                'field': self.secondary_combo.currentData(),
                'method': self.secondary_method_combo.currentData()
            },
            'tertiary': {
                'field': self.tertiary_combo.currentData(),
                'method': self.tertiary_method_combo.currentData()
            },
            'group_priority': []
        }

        # 获取分组优先级
        for i in range(self.group_list_widget.count()):
            group_name = self.group_list_widget.item(i).text()
            config['group_priority'].append(group_name)

        return config

    def load_config_from_file(self):
        """从配置文件加载排序配置"""
        try:
            # 使用父窗口的配置管理器
            if self.parent() and hasattr(self.parent(), 'config'):
                return self.parent().config.load_sort_config()
            else:
                # 回退到直接导入
                from core.config_manager import ConfigManager
                config_manager = ConfigManager()
                return config_manager.load_sort_config()
        except Exception as e:
            self.logger.error(f"从配置文件加载排序配置失败: {str(e)}")
            # 返回默认配置
            return {
                'primary': {'field': 'group', 'method': 'custom'},
                'secondary': {'field': 'name', 'method': 'alphabetical'},
                'tertiary': {'field': 'resolution', 'method': 'quality_high_to_low'},
                'group_priority': []
            }

    def save_config_to_file(self, sort_config):
        """保存排序配置到文件"""
        try:
            # 使用父窗口的配置管理器
            if self.parent() and hasattr(self.parent(), 'config'):
                return self.parent().config.save_sort_config(sort_config)
            else:
                # 回退到直接导入
                from core.config_manager import ConfigManager
                config_manager = ConfigManager()
                return config_manager.save_sort_config(sort_config)
        except Exception as e:
            self.logger.error(f"保存排序配置到文件失败: {str(e)}")
            return False

    def apply_sort(self):
        """应用排序配置"""
        self.sort_config = self.get_sort_config()
        # 保存配置到文件
        if self.save_config_to_file(self.sort_config):
            self.logger.info("排序配置已保存到配置文件")
        else:
            self.logger.warning("排序配置保存到配置文件失败")
        self.accept()

    def get_config(self):
        """获取最终的排序配置"""
        return self.sort_config
