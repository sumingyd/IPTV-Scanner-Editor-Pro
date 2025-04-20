import time
from PyQt6 import QtWidgets, QtCore
from config_manager import ConfigManager
from epg_model import EPGConfig, EPGSource
from styles import AppStyles
from typing import List
from epg_model import EPGProgram

class EPGProgramWidget(QtWidgets.QWidget):
    """EPG节目单控件"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("epg_container")
        self.setStyleSheet(AppStyles.epg_program_style())
        
        self.layout = QtWidgets.QVBoxLayout()
        self.layout.setContentsMargins(5, 5, 5, 5)
        self.layout.setSpacing(5)
        self.setLayout(self.layout)
        
    def update_programs(self, channel_name: str, programs: List[EPGProgram]):
        # 调试输出节目数据
        print(f"更新节目单 - 频道: {channel_name}")
        for i, program in enumerate(programs):
            print(f"节目{i+1}: {program.title} | 开始: {program.start_time} | 结束: {program.end_time} | 描述: {program.description}")
        """更新节目单显示"""
        # 清空现有内容
        while self.layout.count():
            item = self.layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
                
        # 添加标题
        title = QtWidgets.QLabel(f"{channel_name} 节目单")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.layout.addWidget(title)
        
        # 获取当前时间
        current_time = time.strftime("%H%M")
        
        # 添加每个节目项
        for program in programs:
            self._add_program_item(program, current_time)
            
    def _add_program_item(self, program: EPGProgram, current_time: str):
        """添加单个节目项"""
        # 调试输出原始时间数据
        print(f"原始时间数据 - start: {program.start_time}, end: {program.end_time}")
        
        # 格式化时间 (处理多种时间格式)
        def format_time(time_str):
            if not time_str:
                return "00:00"
            # 处理HH:MM:SS格式
            if ':' in time_str:
                parts = time_str.split(':')
                return f"{parts[0]}:{parts[1]}"
            # 处理HHMMSS格式
            elif len(time_str) >= 6:
                return f"{time_str[:2]}:{time_str[2:4]}"
            # 处理HHMM格式
            elif len(time_str) >= 4:
                return f"{time_str[:2]}:{time_str[2:4]}"
            else:
                return "00:00"
                
        start_time = format_time(program.start_time)
        end_time = format_time(program.end_time)
        
        # 创建节目项
        item = QtWidgets.QGroupBox(f"{start_time} - {end_time}")
        item.setObjectName("epg_program")
        
        # 如果是当前播放的节目，高亮显示 (比较时间字符串)
        is_current = False
        try:
            # 转换为分钟数比较
            current_min = int(current_time[:2]) * 60 + int(current_time[2:4])
            start_min = int(program.start_time[:2]) * 60 + int(program.start_time[2:4])
            end_min = int(program.end_time[:2]) * 60 + int(program.end_time[2:4])
            is_current = (current_min >= start_min and current_min < end_min)
        except:
            # 如果转换失败，使用字符串比较
            is_current = (current_time >= program.start_time and 
                         current_time < program.end_time)
        if is_current:
            item.setObjectName("epg_program_current")
            
        item_layout = QtWidgets.QVBoxLayout()
        
        # 添加标题
        title_label = QtWidgets.QLabel(f"<b>{program.title}</b>")
        title_label.setObjectName("epg_title_current" if is_current else "epg_title")
        item_layout.addWidget(title_label)
        
        # 添加描述
        if program.description:
            desc_label = QtWidgets.QLabel(program.description)
            desc_label.setObjectName("epg_desc")
            item_layout.addWidget(desc_label)
            
        item.setLayout(item_layout)
        self.layout.addWidget(item)

class EPGManagementDialog(QtWidgets.QDialog):
    def __init__(self, parent, config_manager: ConfigManager, save_callback):
        super().__init__(parent)
        self.config_manager = config_manager
        self.save_callback = save_callback
        self.epg_config = self.config_manager.load_epg_config() or EPGConfig(sources=[])
        
        self.setWindowTitle("EPG源管理")
        self.setMinimumSize(600, 400)
        self.setStyleSheet(AppStyles.dialog_style())
        
        self._init_ui()
        self._load_config()

    def _init_ui(self):
        """初始化UI布局"""
        layout = QtWidgets.QVBoxLayout()
        
        # 主EPG源设置
        primary_group = QtWidgets.QGroupBox("主EPG源")
        primary_layout = QtWidgets.QFormLayout()
        
        self.primary_url_edit = QtWidgets.QLineEdit()
        primary_layout.addRow("主EPG源URL:", self.primary_url_edit)
        
        primary_group.setLayout(primary_layout)
        layout.addWidget(primary_group)
        
        # 备用EPG源列表
        backup_group = QtWidgets.QGroupBox("备用EPG源")
        backup_layout = QtWidgets.QVBoxLayout()
        
        self.backup_list = QtWidgets.QListWidget()
        self.backup_list.setSelectionMode(QtWidgets.QListWidget.SelectionMode.SingleSelection)
        
        self.add_backup_btn = QtWidgets.QPushButton("添加备用源")
        self.remove_backup_btn = QtWidgets.QPushButton("移除选中源")
        
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addWidget(self.add_backup_btn)
        btn_layout.addWidget(self.remove_backup_btn)
        
        backup_layout.addWidget(self.backup_list)
        backup_layout.addLayout(btn_layout)
        backup_group.setLayout(backup_layout)
        layout.addWidget(backup_group)
        
        # 合并选项
        self.merge_checkbox = QtWidgets.QCheckBox("合并多个EPG源数据")
        layout.addWidget(self.merge_checkbox)
        
        # 按钮组
        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok | 
            QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._on_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        self.setLayout(layout)
        
        # 连接信号
        self.add_backup_btn.clicked.connect(self._add_backup_source)
        self.remove_backup_btn.clicked.connect(self._remove_backup_source)

    def _load_config(self):
        """加载当前配置到UI"""
        # 清空备用源列表
        self.backup_list.clear()
        
        # 设置主EPG源
        primary_source = next((s for s in self.epg_config.sources if s.is_primary), None)
        if primary_source:
            self.primary_url_edit.setText(primary_source.url)
            
        # 设置备用EPG源
        for source in self.epg_config.sources:
            if not source.is_primary:
                self.backup_list.addItem(source.url)
                
        # 设置合并选项
        self.merge_checkbox.setChecked(bool(self.epg_config.merge_sources))

    def _add_backup_source(self):
        """添加备用EPG源"""
        url, ok = QtWidgets.QInputDialog.getText(
            self, "添加备用EPG源", "请输入备用EPG源URL:"
        )
        if ok and url:
            self.backup_list.addItem(url)

    def _remove_backup_source(self):
        """移除选中的备用EPG源"""
        if self.backup_list.currentRow() >= 0:
            self.backup_list.takeItem(self.backup_list.currentRow())

    def _on_accept(self):
        """处理确认按钮点击"""
        # 构建新的EPG配置
        new_config = EPGConfig(sources=[])
        new_config.merge_sources = self.merge_checkbox.isChecked()
        
        # 添加主EPG源
        primary_url = self.primary_url_edit.text().strip()
        if primary_url:
            new_config.sources.append(EPGSource(
                url=primary_url,
                is_primary=True
            ))
            
        # 添加备用EPG源
        for i in range(self.backup_list.count()):
            url = self.backup_list.item(i).text().strip()
            if url:
                new_config.sources.append(EPGSource(
                    url=url,
                    is_primary=False
                ))
        
        # 调用保存回调
        if self.save_callback(new_config):
            self.accept()
