from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt
from log_manager import LogManager
from language_manager import LanguageManager

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
        
        # 默认排序配置
        self.sort_config = {
            'primary': {'field': 'group', 'ascending': True},
            'secondary': {'field': 'name', 'ascending': True},
            'tertiary': {'field': 'resolution', 'ascending': False}
        }
        
        # 分组优先级列表
        self.group_priority = []
        
        self.init_ui()
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
            
        # 更新方向标签
        self.primary_dir_label.setText(self.language_manager.tr('direction', 'Direction'))
        self.secondary_dir_label.setText(self.language_manager.tr('direction', 'Direction'))
        self.tertiary_dir_label.setText(self.language_manager.tr('direction', 'Direction'))
        
        # 更新方向选项
        self.primary_asc_radio.setText(self.language_manager.tr('ascending', 'Ascending'))
        self.primary_desc_radio.setText(self.language_manager.tr('descending', 'Descending'))
        self.secondary_asc_radio.setText(self.language_manager.tr('ascending', 'Ascending'))
        self.secondary_desc_radio.setText(self.language_manager.tr('descending', 'Descending'))
        self.tertiary_asc_radio.setText(self.language_manager.tr('ascending', 'Ascending'))
        self.tertiary_desc_radio.setText(self.language_manager.tr('descending', 'Descending'))
        
        # 更新优先级行标签
        self.primary_row_label.setText(self.language_manager.tr('primary_priority', 'Primary Priority'))
        self.secondary_row_label.setText(self.language_manager.tr('secondary_priority', 'Secondary Priority'))
        self.tertiary_row_label.setText(self.language_manager.tr('tertiary_priority', 'Tertiary Priority'))

    def init_ui(self):
        """初始化用户界面"""
        self.setWindowTitle("排序配置")
        self.setModal(True)
        self.resize(500, 600)
        
        # 主布局
        main_layout = QtWidgets.QVBoxLayout(self)
        
        # 排序优先级设置区域
        self.priority_label = QtWidgets.QLabel()
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
        self.primary_dir_label = QtWidgets.QLabel()
        primary_layout.addWidget(self.primary_dir_label)
        
        self.primary_asc_radio = QtWidgets.QRadioButton()
        self.primary_desc_radio = QtWidgets.QRadioButton()
        self.primary_asc_radio.setChecked(True)
        primary_layout.addWidget(self.primary_asc_radio)
        primary_layout.addWidget(self.primary_desc_radio)
        primary_layout.addStretch()
        
        self.primary_row_label = QtWidgets.QLabel()
        priority_layout.addRow(self.primary_row_label, primary_layout)
        
        # 第二优先级
        secondary_layout = QtWidgets.QHBoxLayout()
        self.secondary_combo = QtWidgets.QComboBox()
        for field_key, field_name in self.sort_fields:
            self.secondary_combo.addItem(field_name, field_key)
        secondary_layout.addWidget(self.secondary_combo)
        
        secondary_layout.addSpacing(10)
        self.secondary_dir_label = QtWidgets.QLabel()
        secondary_layout.addWidget(self.secondary_dir_label)
        
        self.secondary_asc_radio = QtWidgets.QRadioButton()
        self.secondary_desc_radio = QtWidgets.QRadioButton()
        self.secondary_asc_radio.setChecked(True)
        secondary_layout.addWidget(self.secondary_asc_radio)
        secondary_layout.addWidget(self.secondary_desc_radio)
        secondary_layout.addStretch()
        
        self.secondary_row_label = QtWidgets.QLabel()
        priority_layout.addRow(self.secondary_row_label, secondary_layout)
        
        # 第三优先级
        tertiary_layout = QtWidgets.QHBoxLayout()
        self.tertiary_combo = QtWidgets.QComboBox()
        for field_key, field_name in self.sort_fields:
            self.tertiary_combo.addItem(field_name, field_key)
        tertiary_layout.addWidget(self.tertiary_combo)
        
        tertiary_layout.addSpacing(10)
        self.tertiary_dir_label = QtWidgets.QLabel()
        tertiary_layout.addWidget(self.tertiary_dir_label)
        
        self.tertiary_asc_radio = QtWidgets.QRadioButton()
        self.tertiary_desc_radio = QtWidgets.QRadioButton()
        self.tertiary_asc_radio.setChecked(True)
        tertiary_layout.addWidget(self.tertiary_asc_radio)
        tertiary_layout.addWidget(self.tertiary_desc_radio)
        tertiary_layout.addStretch()
        
        self.tertiary_row_label = QtWidgets.QLabel()
        priority_layout.addRow(self.tertiary_row_label, tertiary_layout)
        
        main_layout.addLayout(priority_layout)
        main_layout.addSpacing(20)
        
        # 分组优先级设置区域
        self.group_priority_label = QtWidgets.QLabel("分组优先级设置：")
        main_layout.addWidget(self.group_priority_label)
        
        # 分组列表控件
        self.group_list_widget = QtWidgets.QListWidget()
        self.group_list_widget.setDragDropMode(QtWidgets.QAbstractItemView.DragDropMode.InternalMove)
        self.group_list_widget.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        main_layout.addWidget(self.group_list_widget)
        
        # 按钮区域
        button_layout = QtWidgets.QHBoxLayout()
        self.apply_btn = QtWidgets.QPushButton("应用排序")
        self.apply_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.apply_btn.clicked.connect(self.apply_sort)
        
        self.cancel_btn = QtWidgets.QPushButton("取消")
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
        """)
        self.cancel_btn.clicked.connect(self.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(self.apply_btn)
        button_layout.addWidget(self.cancel_btn)
        
        main_layout.addLayout(button_layout)
        
        # 加载默认配置
        self.load_default_config()
        
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
                
        # 设置排序方向
        if self.sort_config['primary']['ascending']:
            self.primary_asc_radio.setChecked(True)
        else:
            self.primary_desc_radio.setChecked(True)
            
        if self.sort_config['secondary']['ascending']:
            self.secondary_asc_radio.setChecked(True)
        else:
            self.secondary_desc_radio.setChecked(True)
            
        if self.sort_config['tertiary']['ascending']:
            self.tertiary_asc_radio.setChecked(True)
        else:
            self.tertiary_desc_radio.setChecked(True)
            
    def get_sort_config(self):
        """获取排序配置"""
        config = {
            'primary': {
                'field': self.primary_combo.currentData(),
                'ascending': self.primary_asc_radio.isChecked()
            },
            'secondary': {
                'field': self.secondary_combo.currentData(),
                'ascending': self.secondary_asc_radio.isChecked()
            },
            'tertiary': {
                'field': self.tertiary_combo.currentData(),
                'ascending': self.tertiary_asc_radio.isChecked()
            },
            'group_priority': []
        }
        
        # 获取分组优先级
        for i in range(self.group_list_widget.count()):
            group_name = self.group_list_widget.item(i).text()
            config['group_priority'].append(group_name)
            
        return config
        
    def apply_sort(self):
        """应用排序配置"""
        self.sort_config = self.get_sort_config()
        self.accept()
        
    def get_config(self):
        """获取最终的排序配置"""
        return self.sort_config
