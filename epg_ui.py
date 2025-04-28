import time
import datetime
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
        
        # 创建主布局
        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        # 创建滚动区域
        self.scroll_area = QtWidgets.QScrollArea()
        self.scroll_area.setObjectName("epg_scroll_area")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # 初始化容器
        self.container = QtWidgets.QWidget()
        self.container.setObjectName("epg_container_widget")
        self.scroll_area.setWidget(self.container)
        
        # 节目列表布局
        self.program_layout = QtWidgets.QVBoxLayout()
        self.program_layout.setContentsMargins(0, 0, 0, 0)
        self.program_layout.setSpacing(2)
        self.container.setLayout(self.program_layout)
        
        # 添加滚动区域到主布局
        self.main_layout.addWidget(self.scroll_area)
        
        # 直接使用全局logger
        import logging
        self.logger = logging.getLogger('IPTVLogger')
        
        # 当前节目索引
        self.current_program_index = -1
        
        # 当前节目索引
        self.current_program_index = -1
        
    def update_programs(self, channel_name: str, programs: List[EPGProgram]):
        """更新节目单显示"""
        # 清空现有内容
        while self.program_layout.count():
            item = self.program_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # 如果没有节目数据，显示提示信息
        if not programs:
            no_program = QtWidgets.QLabel(f"频道 {channel_name} 无节目数据")
            no_program.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            no_program.setStyleSheet("color: #999; font-size: 14px;")
            self.program_layout.addWidget(no_program)
            return
            
        # 获取当前时间
        current_time = time.strftime("%H%M")
        
        # 按日期分组节目
        date_groups = {}
        for program in programs:
            # 提取日期部分
            date_str = program.start_time[:8] if len(program.start_time) >= 8 else "00000000"
            
            # 格式化日期显示
            try:
                date = datetime.datetime.strptime(date_str, "%Y%m%d").strftime("%Y年%m月%d日")
            except:
                date = "未知日期"
                
            if date not in date_groups:
                date_groups[date] = []
            date_groups[date].append(program)
        
        # 按日期排序
        sorted_dates = sorted(date_groups.keys())
        
        # 添加每个节目项
        self.program_items = []  # 保存所有节目项的引用
        program_index = 0
        for date in sorted_dates:
            # 添加日期标题
            date_label = QtWidgets.QLabel(f"<b>{date}</b>")
            date_label.setStyleSheet("""
                QLabel {
                    color: #666;
                    font-size: 14px;
                    padding: 5px;
                    border-bottom: 1px solid #eee;
                }
            """)
            self.program_layout.addWidget(date_label)
            
            # 添加该日期的所有节目
            for program in date_groups[date]:
                item = self._add_program_item(program, current_time, program_index)
                if item:  # 确保item创建成功
                    self.program_items.append((program_index, item, program))
                program_index += 1
            
        # 确保UI更新完成并高亮当前节目
        def highlight_after_layout():
            self._highlight_current_program()
            # 强制重绘确保高亮效果
            self.container.update()
            self.update()
            
        QtCore.QTimer.singleShot(100, highlight_after_layout)
        
    def _highlight_current_program(self):
        """高亮并滚动到当前节目"""
        if hasattr(self, 'current_program_index') and self.current_program_index >= 0:
            try:
                # 检查索引是否有效
                if self.current_program_index >= len(self.program_items):
                    self.logger.error(f"索引{self.current_program_index}超出范围(最大{len(self.program_items)-1})")
                    return
                
                # 从保存的节目项列表中获取当前节目项
                current_item = None
                for idx, item, program in self.program_items:
                    if idx == self.current_program_index:
                        current_item = item
                        break
                
                if not current_item:
                    for idx, item, program in self.program_items:
                        self.logger.debug(f"索引={idx}, 标题={program.title}, 指针={id(item)}")
                    return
                if not current_item:
                    self.logger.debug(f"高亮失败: 未找到索引{self.current_program_index}对应的节目项")
                    return
                
                # 强制更新UI
                self.container.update()
                self.container.updateGeometry()
                
                # 确保样式表应用
                # 确保控件对象名正确设置
                current_item.setObjectName("epg_program_current")
                for child in current_item.findChildren(QtWidgets.QLabel):
                    if child.objectName().endswith("_current"):
                        child.setObjectName(child.objectName())
                
                # 使用统一的样式表
                current_item.setStyleSheet(AppStyles.epg_program_style())
                current_item.style().unpolish(current_item)
                current_item.style().polish(current_item)
                current_item.update()
                # 确保布局已完成
                QtWidgets.QApplication.processEvents()
                
                # 计算滚动位置
                item_pos = current_item.pos().y()
                scroll_pos = item_pos - int((self.height() - current_item.height()) / 2)
                
                # 执行滚动
                scroll_bar = self.verticalScrollBar()
                scroll_bar.setValue(scroll_pos)
                
                # 强制重绘
                current_item.update()
                self.update()
            except Exception:
                pass
            
    def _add_program_item(self, program: EPGProgram, current_time: str, index: int):
        """添加单个节目项"""
        # 格式化时间 (处理完整时间戳格式和多种时间格式)
        def format_time(time_str):
            if not time_str:
                return "00:00"
            
            # 处理完整时间戳格式 "20250418004200 +0000"
            if len(time_str) >= 14 and time_str[8:10].isdigit() and time_str[10:12].isdigit():
                return f"{time_str[8:10]}:{time_str[10:12]}"
            
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
        
        # 创建节目项容器
        item = QtWidgets.QWidget()
        item.setObjectName("epg_program")
        
        # 判断是否是当前节目
        is_current = False
        try:
            # 获取当前日期和时间
            now = datetime.datetime.now()
            current_date = now.strftime("%Y%m%d")
            current_hh = int(current_time[:2])
            current_mm = int(current_time[2:4])
            
            # 解析节目开始日期和时间
            start_time_str = program.start_time
            if len(start_time_str) >= 14:  # 完整时间戳格式 "20250418004200 +0000"
                start_date = start_time_str[:8]
                start_hh = int(start_time_str[8:10])
                start_mm = int(start_time_str[10:12])
            elif ':' in start_time_str:  # HH:MM:SS格式
                parts = start_time_str.split(':')
                start_date = current_date  # 使用当前日期
                start_hh = int(parts[0])
                start_mm = int(parts[1])
            else:  # HHMMSS或HHMM格式
                start_date = current_date  # 使用当前日期
                start_hh = int(start_time_str[:2])
                start_mm = int(start_time_str[2:4])
            
            # 解析节目结束日期和时间
            end_time_str = program.end_time
            if len(end_time_str) >= 14:  # 完整时间戳格式
                end_date = end_time_str[:8]
                end_hh = int(end_time_str[8:10])
                end_mm = int(end_time_str[10:12])
            elif ':' in end_time_str:  # HH:MM:SS格式
                parts = end_time_str.split(':')
                end_date = current_date  # 使用当前日期
                end_hh = int(parts[0])
                end_mm = int(parts[1])
            else:  # HHMMSS或HHMM格式
                end_date = current_date  # 使用当前日期
                end_hh = int(end_time_str[:2])
                end_mm = int(end_time_str[2:4])
            
            # 转换为datetime对象进行比较
            try:
                # 解析开始时间
                start_dt = datetime.datetime.strptime(f"{start_date}{start_hh:02d}{start_mm:02d}", "%Y%m%d%H%M")
                
                # 解析结束时间，处理跨日情况
                if end_hh < start_hh or (end_hh == start_hh and end_mm < start_mm):
                    # 跨日节目，结束日期是开始日期的下一天
                    end_dt = datetime.datetime.strptime(f"{start_date}{end_hh:02d}{end_mm:02d}", "%Y%m%d%H%M") + datetime.timedelta(days=1)
                else:
                    # 非跨日节目
                    end_dt = datetime.datetime.strptime(f"{start_date}{end_hh:02d}{end_mm:02d}", "%Y%m%d%H%M")
                
                # 比较当前时间是否在节目时间段内
                is_current = start_dt <= now < end_dt
                
                # 特殊处理午夜后的节目(00:00-06:00)
                if 0 <= now.hour < 6:
                    # 检查是否是前一天的跨日节目
                    prev_day = (now - datetime.timedelta(days=1)).strftime("%Y%m%d")
                    if start_date == prev_day and end_dt.date() == now.date():
                        is_current = True
                
            except Exception as e:
                is_current = False
        except Exception as e:
            import traceback
            traceback.print_exc()
            is_current = False
        
        # 重置所有可能的高亮项
        for i in range(self.program_layout.count()):
            item = self.program_layout.itemAt(i).widget()
            if item and item.objectName() == "epg_program_current":
                item.setObjectName("epg_program")
                for child in item.findChildren(QtWidgets.QLabel):
                    if child.objectName().endswith("_current"):
                        child.setObjectName(child.objectName().replace("_current", ""))
                item.setStyleSheet(AppStyles.epg_program_style())
        
        # 创建节目项容器
        item = QtWidgets.QWidget()
        item.setObjectName("epg_program")
        
        # 创建水平布局
        item_layout = QtWidgets.QHBoxLayout(item)  # 直接设置给item
        item_layout.setContentsMargins(5, 5, 5, 5)
        item_layout.setSpacing(10)
        
        # 创建时间区域
        time_widget = QtWidgets.QWidget()
        time_layout = QtWidgets.QVBoxLayout(time_widget)  # 直接设置给time_widget
        time_layout.setSpacing(2)
        
        start_label = QtWidgets.QLabel(start_time)
        time_layout.addWidget(start_label)
        
        end_label = QtWidgets.QLabel(end_time)
        time_layout.addWidget(end_label)
        
        # 创建节目名称标签
        title_label = QtWidgets.QLabel(f"<b>{program.title}</b>")
        title_label.setWordWrap(True)
        
        # 添加到主布局
        item_layout.addWidget(time_widget, stretch=1)
        item_layout.addWidget(title_label, stretch=3)
        
        if is_current:
            self.current_program_index = index
            item.setObjectName("epg_program_current")
            title_label.setObjectName("epg_title_current")
            start_label.setObjectName("epg_time_current")
        
        self.program_layout.addWidget(item)
        return item  # 确保返回创建的item对象

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
