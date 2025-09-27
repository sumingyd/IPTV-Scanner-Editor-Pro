import json
import os
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt
from log_manager import LogManager
from channel_mappings import mapping_manager

class MappingManagerDialog(QtWidgets.QDialog):
    """频道映射管理器对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = LogManager()
        self.parent = parent
        self.setWindowTitle("频道映射管理器")
        self.setMinimumSize(800, 600)
        self.setup_ui()
        self.load_mappings()
        
        # 获取语言管理器
        if parent and hasattr(parent, 'language_manager'):
            self.language_manager = parent.language_manager
        else:
            from language_manager import LanguageManager
            self.language_manager = LanguageManager()
            self.language_manager.load_available_languages()
            self.language_manager.set_language('zh')
        
        self.update_ui_texts()
        
    def setup_ui(self):
        """设置用户界面"""
        layout = QtWidgets.QVBoxLayout(self)
        
        # 创建选项卡
        self.tab_widget = QtWidgets.QTabWidget()
        
        # 用户映射管理选项卡
        self.user_mapping_tab = self.create_user_mapping_tab()
        self.tab_widget.addTab(self.user_mapping_tab, "用户映射管理")
        
        # 频道指纹查看选项卡
        self.fingerprint_tab = self.create_fingerprint_tab()
        self.tab_widget.addTab(self.fingerprint_tab, "频道指纹")
        
        # 映射建议选项卡
        self.suggestion_tab = self.create_suggestion_tab()
        self.tab_widget.addTab(self.suggestion_tab, "映射建议")
        
        layout.addWidget(self.tab_widget)
        
        # 按钮区域
        button_layout = QtWidgets.QHBoxLayout()
        
        self.refresh_cache_btn = QtWidgets.QPushButton("刷新远程映射缓存")
        self.refresh_cache_btn.clicked.connect(self.refresh_cache)
        
        self.export_mappings_btn = QtWidgets.QPushButton("导出用户映射")
        self.export_mappings_btn.clicked.connect(self.export_mappings)
        
        self.import_mappings_btn = QtWidgets.QPushButton("导入用户映射")
        self.import_mappings_btn.clicked.connect(self.import_mappings)
        
        self.close_btn = QtWidgets.QPushButton("关闭")
        self.close_btn.clicked.connect(self.accept)
        
        button_layout.addWidget(self.refresh_cache_btn)
        button_layout.addWidget(self.export_mappings_btn)
        button_layout.addWidget(self.import_mappings_btn)
        button_layout.addStretch()
        button_layout.addWidget(self.close_btn)
        
        layout.addLayout(button_layout)
        
    def create_user_mapping_tab(self):
        """创建用户映射管理选项卡"""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        
        # 搜索和过滤区域
        search_layout = QtWidgets.QHBoxLayout()
        self.search_input = QtWidgets.QLineEdit()
        self.search_input.setPlaceholderText("搜索频道名...")
        self.search_input.textChanged.connect(self.filter_mappings)
        
        # 搜索选项
        self.search_options = QtWidgets.QComboBox()
        self.search_options.currentTextChanged.connect(self.filter_mappings)
        
        self.search_label = QtWidgets.QLabel("搜索:")
        self.search_scope_label = QtWidgets.QLabel("搜索范围:")
        
        search_layout.addWidget(self.search_label)
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(self.search_scope_label)
        search_layout.addWidget(self.search_options)
        search_layout.addStretch()
        
        layout.addLayout(search_layout)
        
        # 映射列表
        self.mapping_table = QtWidgets.QTableWidget()
        self.mapping_table.setColumnCount(4)
        self.mapping_table.setHorizontalHeaderLabels(["标准名称", "原始名称", "分组", "LOGO地址"])
        self.mapping_table.horizontalHeader().setStretchLastSection(True)
        self.mapping_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.mapping_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        
        layout.addWidget(self.mapping_table)
        
        # 操作按钮
        button_layout = QtWidgets.QHBoxLayout()
        
        self.add_mapping_btn = QtWidgets.QPushButton("添加映射")
        self.add_mapping_btn.clicked.connect(self.add_mapping)
        
        self.edit_mapping_btn = QtWidgets.QPushButton("编辑映射")
        self.edit_mapping_btn.clicked.connect(self.edit_mapping)
        
        self.delete_mapping_btn = QtWidgets.QPushButton("删除映射")
        self.delete_mapping_btn.clicked.connect(self.delete_mapping)
        
        button_layout.addWidget(self.add_mapping_btn)
        button_layout.addWidget(self.edit_mapping_btn)
        button_layout.addWidget(self.delete_mapping_btn)
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
        
        return widget
        
    def create_fingerprint_tab(self):
        """创建频道指纹查看选项卡"""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        
        # 指纹列表
        self.fingerprint_table = QtWidgets.QTableWidget()
        self.fingerprint_table.setColumnCount(5)
        self.fingerprint_table.setHorizontalHeaderLabels(["指纹ID", "原始名称", "映射名称", "出现次数", "最后出现"])
        self.fingerprint_table.horizontalHeader().setStretchLastSection(True)
        self.fingerprint_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        
        layout.addWidget(self.fingerprint_table)
        
        # 操作按钮
        button_layout = QtWidgets.QHBoxLayout()
        
        self.clear_fingerprints_btn = QtWidgets.QPushButton("清空指纹数据")
        self.clear_fingerprints_btn.clicked.connect(self.clear_fingerprints)
        
        self.analyze_fingerprints_btn = QtWidgets.QPushButton("分析不稳定映射")
        self.analyze_fingerprints_btn.clicked.connect(self.analyze_fingerprints)
        
        button_layout.addWidget(self.clear_fingerprints_btn)
        button_layout.addWidget(self.analyze_fingerprints_btn)
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
        
        return widget
        
    def create_suggestion_tab(self):
        """创建映射建议选项卡"""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        
        # 建议列表
        self.suggestion_table = QtWidgets.QTableWidget()
        self.suggestion_table.setColumnCount(4)
        self.suggestion_table.setHorizontalHeaderLabels(["原始名称", "建议映射", "置信度", "操作"])
        self.suggestion_table.horizontalHeader().setStretchLastSection(True)
        
        layout.addWidget(self.suggestion_table)
        
        # 刷新按钮
        self.refresh_suggestions_btn = QtWidgets.QPushButton("刷新建议")
        self.refresh_suggestions_btn.clicked.connect(self.refresh_suggestions)
        layout.addWidget(self.refresh_suggestions_btn)
        
        return widget
        
    def load_mappings(self):
        """加载映射数据"""
        self.load_user_mappings()
        self.load_fingerprints()
        self.load_suggestions()
        
    def load_user_mappings(self):
        """加载用户映射到表格"""
        self.mapping_table.setRowCount(0)
        
        row = 0
        for standard_name, mapping_data in mapping_manager.user_mappings.items():
            for raw_name in mapping_data.get('raw_names', []):
                self.mapping_table.insertRow(row)
                
                # 标准名称
                self.mapping_table.setItem(row, 0, QtWidgets.QTableWidgetItem(standard_name))
                
                # 原始名称
                self.mapping_table.setItem(row, 1, QtWidgets.QTableWidgetItem(raw_name))
                
                # 分组
                group = mapping_data.get('group_name', '未分类')
                self.mapping_table.setItem(row, 2, QtWidgets.QTableWidgetItem(group))
                
                # LOGO地址
                logo_url = mapping_data.get('logo_url', '')
                self.mapping_table.setItem(row, 3, QtWidgets.QTableWidgetItem(logo_url))
                
                row += 1
                
        # 调整列宽
        self.mapping_table.resizeColumnsToContents()
        
    def load_fingerprints(self):
        """加载频道指纹到表格"""
        self.fingerprint_table.setRowCount(0)
        
        row = 0
        for fingerprint_id, fingerprint_data in mapping_manager.channel_fingerprints.items():
            self.fingerprint_table.insertRow(row)
            
            # 指纹ID（截断显示）
            fingerprint_display = fingerprint_id[:8] + "..."
            self.fingerprint_table.setItem(row, 0, QtWidgets.QTableWidgetItem(fingerprint_display))
            self.fingerprint_table.item(row, 0).setToolTip(fingerprint_id)
            
            # 原始名称
            raw_name = fingerprint_data.get('raw_name', '')
            self.fingerprint_table.setItem(row, 1, QtWidgets.QTableWidgetItem(raw_name))
            
            # 映射名称
            mapped_name = fingerprint_data.get('mapped_name', '')
            self.fingerprint_table.setItem(row, 2, QtWidgets.QTableWidgetItem(mapped_name))
            
            # 出现次数
            count = fingerprint_data.get('count', 0)
            self.fingerprint_table.setItem(row, 3, QtWidgets.QTableWidgetItem(str(count)))
            
            # 最后出现时间
            last_seen = fingerprint_data.get('last_seen', 0)
            if last_seen:
                from datetime import datetime
                last_seen_str = datetime.fromtimestamp(last_seen).strftime('%Y-%m-%d %H:%M:%S')
            else:
                last_seen_str = "未知"
            self.fingerprint_table.setItem(row, 4, QtWidgets.QTableWidgetItem(last_seen_str))
            
            row += 1
            
        # 调整列宽
        self.fingerprint_table.resizeColumnsToContents()
        
    def load_suggestions(self):
        """加载映射建议"""
        self.suggestion_table.setRowCount(0)
        
        # 使用分析得到的建议数据
        if not hasattr(self, 'suggestion_mappings') or not self.suggestion_mappings:
            # 如果没有建议数据，显示提示信息
            self.suggestion_table.insertRow(0)
            self.suggestion_table.setItem(0, 0, QtWidgets.QTableWidgetItem("暂无建议"))
            self.suggestion_table.setItem(0, 1, QtWidgets.QTableWidgetItem("请先进行扫描并点击'刷新建议'"))
            self.suggestion_table.setItem(0, 2, QtWidgets.QTableWidgetItem("-"))
            return
        
        # 显示真实的建议数据
        row = 0
        for suggestion in self.suggestion_mappings:
            self.suggestion_table.insertRow(row)
            
            # 原始名称
            self.suggestion_table.setItem(row, 0, QtWidgets.QTableWidgetItem(suggestion['raw_name']))
            
            # 建议映射
            self.suggestion_table.setItem(row, 1, QtWidgets.QTableWidgetItem(suggestion['suggested_mapping']))
            
            # 置信度
            confidence = suggestion['confidence']
            if confidence >= 0.8:
                confidence_text = "高"
            elif confidence >= 0.5:
                confidence_text = "中"
            else:
                confidence_text = "低"
            self.suggestion_table.setItem(row, 2, QtWidgets.QTableWidgetItem(f"{confidence_text} ({confidence:.1%})"))
            
            # 操作按钮
            apply_btn = QtWidgets.QPushButton("应用")
            apply_btn.clicked.connect(lambda checked, r=row: self.apply_suggestion(r))
            self.suggestion_table.setCellWidget(row, 3, apply_btn)
            
            row += 1
        
        # 调整列宽
        self.suggestion_table.resizeColumnsToContents()
        
    def filter_mappings(self):
        """过滤映射列表"""
        search_text = self.search_input.text().lower()
        search_option = self.search_options.currentText()
        
        for row in range(self.mapping_table.rowCount()):
            should_show = False
            
            if not search_text:  # 如果没有搜索文本，显示所有行
                should_show = True
            else:
                if search_option == "搜索所有字段":
                    # 搜索所有列
                    for col in range(self.mapping_table.columnCount()):
                        item = self.mapping_table.item(row, col)
                        if item and search_text in item.text().lower():
                            should_show = True
                            break
                elif search_option == "仅搜索标准名称":
                    # 只搜索标准名称列（第0列）
                    item = self.mapping_table.item(row, 0)
                    if item and search_text in item.text().lower():
                        should_show = True
                elif search_option == "仅搜索原始名称":
                    # 只搜索原始名称列（第1列）
                    item = self.mapping_table.item(row, 1)
                    if item and search_text in item.text().lower():
                        should_show = True
                elif search_option == "仅搜索分组":
                    # 只搜索分组列（第2列）
                    item = self.mapping_table.item(row, 2)
                    if item and search_text in item.text().lower():
                        should_show = True
                    
            self.mapping_table.setRowHidden(row, not should_show)
            
    def add_mapping(self):
        """添加新的映射"""
        dialog = MappingEditDialog(self)
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            mapping_data = dialog.get_mapping_data()
            if mapping_data:
                mapping_manager.add_user_mapping(
                    mapping_data['raw_name'],
                    mapping_data['standard_name'],
                    mapping_data.get('logo_url'),
                    mapping_data.get('group_name')
                )
                self.load_user_mappings()
                self.logger.info(f"添加用户映射: {mapping_data['raw_name']} -> {mapping_data['standard_name']}")
                
    def edit_mapping(self):
        """编辑选中的映射"""
        selected_rows = self.mapping_table.selectionModel().selectedRows()
        if not selected_rows:
            QtWidgets.QMessageBox.warning(self, 
                self.language_manager.tr('warning', 'Warning'), 
                self.language_manager.tr('select_mapping_to_edit', 'Please select a mapping to edit')
            )
            return
            
        row = selected_rows[0].row()
        standard_name = self.mapping_table.item(row, 0).text()
        raw_name = self.mapping_table.item(row, 1).text()
        group_name = self.mapping_table.item(row, 2).text()
        logo_url = self.mapping_table.item(row, 3).text()
        
        dialog = MappingEditDialog(self, standard_name, raw_name, group_name, logo_url)
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            new_data = dialog.get_mapping_data()
            if new_data:
                # 先删除旧的，再添加新的
                mapping_manager.remove_user_mapping(standard_name)
                mapping_manager.add_user_mapping(
                    new_data['raw_name'],
                    new_data['standard_name'],
                    new_data.get('logo_url'),
                    new_data.get('group_name')
                )
                self.load_user_mappings()
                self.logger.info(f"编辑用户映射: {raw_name} -> {new_data['standard_name']}")
                
    def delete_mapping(self):
        """删除选中的映射"""
        selected_rows = self.mapping_table.selectionModel().selectedRows()
        if not selected_rows:
            QtWidgets.QMessageBox.warning(self, 
                self.language_manager.tr('warning', 'Warning'), 
                self.language_manager.tr('select_mapping_to_delete', 'Please select a mapping to delete')
            )
            return
            
        row = selected_rows[0].row()
        standard_name = self.mapping_table.item(row, 0).text()
        raw_name = self.mapping_table.item(row, 1).text()
        
        reply = QtWidgets.QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除映射 '{raw_name} -> {standard_name}' 吗？",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
        )
        
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            mapping_manager.remove_user_mapping(standard_name)
            self.load_user_mappings()
            self.logger.info(f"删除用户映射: {raw_name} -> {standard_name}")
            
    def refresh_cache(self):
        """刷新远程映射缓存"""
        mapping_manager.refresh_cache()
        QtWidgets.QMessageBox.information(self, "成功", "远程映射缓存已刷新")
        
    def export_mappings(self):
        """导出用户映射到CSV文件"""
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "导出用户映射", "user_mappings.csv", "CSV文件 (*.csv)"
        )
        
        if file_path:
            try:
                import csv
                with open(file_path, 'w', encoding='utf-8-sig', newline='') as f:
                    writer = csv.writer(f)
                    # 写入表头
                    writer.writerow(['standard_name', 'raw_names', 'logo_url', 'group_name'])
                    
                    # 写入数据
                    for standard_name, mapping_data in mapping_manager.user_mappings.items():
                        raw_names = ','.join(mapping_data.get('raw_names', []))
                        logo_url = mapping_data.get('logo_url', '')
                        group_name = mapping_data.get('group_name', '')
                        writer.writerow([standard_name, raw_names, logo_url, group_name])
                        
                QtWidgets.QMessageBox.information(self, "成功", f"用户映射已导出到: {file_path}")
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "错误", f"导出失败: {str(e)}")
                
    def import_mappings(self):
        """从CSV文件导入用户映射"""
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "导入用户映射", "", "CSV文件 (*.csv)"
        )
        
        if file_path:
            try:
                import csv
                imported_mappings = {}
                
                with open(file_path, 'r', encoding='utf-8-sig') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        standard_name = row.get('standard_name', '').strip()
                        if not standard_name:
                            continue
                            
                        raw_names = [name.strip() for name in row.get('raw_names', '').split(',') if name.strip()]
                        logo_url = row.get('logo_url', '').strip()
                        group_name = row.get('group_name', '').strip()
                        
                        imported_mappings[standard_name] = {
                            'raw_names': raw_names,
                            'logo_url': logo_url if logo_url else None,
                            'group_name': group_name if group_name else None
                        }
                
                # 合并映射
                mapping_manager.user_mappings.update(imported_mappings)
                mapping_manager._save_user_mappings()
                mapping_manager.combined_mappings = mapping_manager._combine_mappings()
                mapping_manager.reverse_mappings = mapping_manager.create_reverse_mappings(mapping_manager.combined_mappings)
                
                self.load_user_mappings()
                QtWidgets.QMessageBox.information(self, "成功", f"用户映射已从CSV文件导入")
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "错误", f"导入失败: {str(e)}")
                
    def clear_fingerprints(self):
        """清空指纹数据"""
        reply = QtWidgets.QMessageBox.question(
            self,
            "确认清空",
            "确定要清空所有频道指纹数据吗？",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
        )
        
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            mapping_manager.channel_fingerprints.clear()
            mapping_manager._save_channel_fingerprints()
            self.load_fingerprints()
            self.logger.info("已清空频道指纹数据")
            
    def analyze_fingerprints(self):
        """分析不稳定的映射"""
        unstable_mappings = []
        suggestion_mappings = []
        
        # 分析指纹数据，找出不稳定的映射
        for fingerprint_id, data in mapping_manager.channel_fingerprints.items():
            count = data.get('count', 0)
            raw_name = data.get('raw_name', '')
            mapped_name = data.get('mapped_name', '')
            
            if count >= 3:
                # 检查这个原始名称是否有多个不同的映射
                same_raw_mappings = []
                for fp_id, fp_data in mapping_manager.channel_fingerprints.items():
                    if fp_data.get('raw_name') == raw_name and fp_data.get('mapped_name') != raw_name:
                        same_raw_mappings.append(fp_data)
                
                # 如果同一个原始名称有多个不同的映射，说明不稳定
                if len(same_raw_mappings) > 1:
                    # 找出最频繁的映射
                    mapping_counts = {}
                    for mapping in same_raw_mappings:
                        mapped_name = mapping.get('mapped_name', '')
                        mapping_counts[mapped_name] = mapping_counts.get(mapped_name, 0) + mapping.get('count', 0)
                    
                    # 按出现次数排序
                    sorted_mappings = sorted(mapping_counts.items(), key=lambda x: x[1], reverse=True)
                    
                    if len(sorted_mappings) > 1:
                        # 有多个不同的映射，说明不稳定
                        unstable_mappings.append({
                            'raw_name': raw_name,
                            'mappings': sorted_mappings,
                            'total_count': count
                        })
                
                # 如果映射名称与原始名称不同，且出现次数较多，可以作为建议
                if mapped_name != raw_name and count >= 2:
                    suggestion_mappings.append({
                        'raw_name': raw_name,
                        'suggested_mapping': mapped_name,
                        'confidence': min(count / 10.0, 1.0),  # 置信度基于出现次数
                        'count': count
                    })
                
        # 显示分析结果
        if unstable_mappings:
            message = "发现以下可能不稳定的映射:\n\n"
            for mapping in unstable_mappings:
                message += f"频道: {mapping['raw_name']}\n"
                message += "可能的映射:\n"
                for mapped_name, count in mapping['mappings'][:3]:  # 显示前3个
                    message += f"  - {mapped_name} (出现{count}次)\n"
                message += "\n"
                
            QtWidgets.QMessageBox.information(self, "不稳定映射分析", message)
        else:
            QtWidgets.QMessageBox.information(self, "分析结果", "未发现明显不稳定的映射")
        
        # 将建议映射保存到实例变量中，供映射建议选项卡使用
        self.suggestion_mappings = suggestion_mappings
            
    def refresh_suggestions(self):
        """刷新映射建议"""
        # 重新分析指纹数据以获取最新的建议
        self.analyze_fingerprints()
        
        # 加载建议到表格
        self.load_suggestions()
        
        if self.suggestion_mappings:
            QtWidgets.QMessageBox.information(self, "成功", f"已生成 {len(self.suggestion_mappings)} 条映射建议")
        else:
            QtWidgets.QMessageBox.information(self, "提示", "暂无映射建议，请先进行扫描以收集数据")
        
    def apply_suggestion(self, row_index):
        """应用映射建议"""
        if not hasattr(self, 'suggestion_mappings') or row_index >= len(self.suggestion_mappings):
            QtWidgets.QMessageBox.warning(self, "错误", "无法应用此建议")
            return
        
        suggestion = self.suggestion_mappings[row_index]
        raw_name = suggestion['raw_name']
        suggested_mapping = suggestion['suggested_mapping']
        
        # 确认应用建议
        reply = QtWidgets.QMessageBox.question(
            self,
            "确认应用建议",
            f"确定要将 '{raw_name}' 映射到 '{suggested_mapping}' 吗？",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
        )
        
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            # 应用映射建议
            mapping_manager.add_user_mapping(raw_name, suggested_mapping)
            
            # 从建议列表中移除已应用的项
            self.suggestion_mappings.pop(row_index)
            
            # 重新加载建议列表
            self.load_suggestions()
            
            # 重新加载用户映射列表
            self.load_user_mappings()
            
            QtWidgets.QMessageBox.information(self, "成功", f"已应用映射建议: {raw_name} -> {suggested_mapping}")
    
    def update_ui_texts(self):
        """更新UI文本到当前语言"""
        if not hasattr(self, 'language_manager') or not self.language_manager.translations:
            return
            
        try:
            # 更新窗口标题
            self.setWindowTitle(self.language_manager.tr('mapping_manager', 'Channel Mapping Manager'))
            
            # 更新选项卡标题
            self.tab_widget.setTabText(0, self.language_manager.tr('user_mapping_management', 'User Mapping Management'))
            self.tab_widget.setTabText(1, self.language_manager.tr('channel_fingerprints', 'Channel Fingerprints'))
            self.tab_widget.setTabText(2, self.language_manager.tr('mapping_suggestions', 'Mapping Suggestions'))
            
            # 更新按钮文本
            self.refresh_cache_btn.setText(self.language_manager.tr('refresh_remote_cache', 'Refresh Remote Cache'))
            self.export_mappings_btn.setText(self.language_manager.tr('export_user_mappings', 'Export User Mappings'))
            self.import_mappings_btn.setText(self.language_manager.tr('import_user_mappings', 'Import User Mappings'))
            self.close_btn.setText(self.language_manager.tr('close', 'Close'))
            
            # 更新用户映射管理选项卡
            self.search_input.setPlaceholderText(self.language_manager.tr('search_channel_name', 'Search channel name...'))
            
            # 更新搜索标签
            self.search_label.setText(self.language_manager.tr('search', 'Search') + ":")
            self.search_scope_label.setText(self.language_manager.tr('search_scope', 'Search Scope') + ":")
            
            # 更新搜索选项
            self.search_options.clear()
            self.search_options.addItems([
                self.language_manager.tr('search_all_fields', 'Search All Fields'),
                self.language_manager.tr('search_standard_name_only', 'Search Standard Name Only'),
                self.language_manager.tr('search_raw_name_only', 'Search Raw Name Only'),
                self.language_manager.tr('search_group_only', 'Search Group Only')
            ])
            
            self.mapping_table.setHorizontalHeaderLabels([
                self.language_manager.tr('standard_name', 'Standard Name'),
                self.language_manager.tr('raw_name', 'Raw Name'),
                self.language_manager.tr('group', 'Group'),
                self.language_manager.tr('logo_address', 'Logo Address')
            ])
            self.add_mapping_btn.setText(self.language_manager.tr('add_mapping', 'Add Mapping'))
            self.edit_mapping_btn.setText(self.language_manager.tr('edit_mapping', 'Edit Mapping'))
            self.delete_mapping_btn.setText(self.language_manager.tr('delete_mapping', 'Delete Mapping'))
            
            # 更新频道指纹选项卡
            self.fingerprint_table.setHorizontalHeaderLabels([
                self.language_manager.tr('fingerprint_id', 'Fingerprint ID'),
                self.language_manager.tr('raw_name', 'Raw Name'),
                self.language_manager.tr('mapped_name', 'Mapped Name'),
                self.language_manager.tr('occurrence_count', 'Occurrence Count'),
                self.language_manager.tr('last_seen', 'Last Seen')
            ])
            self.clear_fingerprints_btn.setText(self.language_manager.tr('clear_fingerprint_data', 'Clear Fingerprint Data'))
            self.analyze_fingerprints_btn.setText(self.language_manager.tr('analyze_unstable_mappings', 'Analyze Unstable Mappings'))
            
            # 更新映射建议选项卡
            self.suggestion_table.setHorizontalHeaderLabels([
                self.language_manager.tr('raw_name', 'Raw Name'),
                self.language_manager.tr('suggested_mapping', 'Suggested Mapping'),
                self.language_manager.tr('confidence', 'Confidence'),
                self.language_manager.tr('operation', 'Operation')
            ])
            self.refresh_suggestions_btn.setText(self.language_manager.tr('refresh_suggestions', 'Refresh Suggestions'))
            
            self.logger.info(f"映射管理器UI文本已更新到语言: {self.language_manager.current_language}")
            
        except Exception as e:
            self.logger.error(f"更新映射管理器UI文本失败: {str(e)}")


class MappingEditDialog(QtWidgets.QDialog):
    """映射编辑对话框"""
    
    def __init__(self, parent=None, standard_name="", raw_name="", group_name="", logo_url=""):
        super().__init__(parent)
        self.standard_name = standard_name
        self.raw_name = raw_name
        self.group_name = group_name
        self.logo_url = logo_url
        
        self.setWindowTitle("编辑映射" if standard_name else "添加映射")
        self.setup_ui()
        
    def setup_ui(self):
        """设置用户界面"""
        layout = QtWidgets.QVBoxLayout(self)
        
        # 表单布局
        form_layout = QtWidgets.QFormLayout()
        
        # 标准名称输入
        self.standard_name_input = QtWidgets.QLineEdit(self.standard_name)
        self.standard_name_input.setPlaceholderText("输入标准频道名称，如'CCTV-1 综合'")
        form_layout.addRow("标准名称:", self.standard_name_input)
        
        # 原始名称输入
        self.raw_name_input = QtWidgets.QLineEdit(self.raw_name)
        self.raw_name_input.setPlaceholderText("输入原始频道名称，如'CCTV1'")
        form_layout.addRow("原始名称:", self.raw_name_input)
        
        # 分组输入
        self.group_name_input = QtWidgets.QLineEdit(self.group_name)
        self.group_name_input.setPlaceholderText("输入分组名称，如'央视频道'")
        form_layout.addRow("分组:", self.group_name_input)
        
        # LOGO地址输入
        self.logo_url_input = QtWidgets.QLineEdit(self.logo_url)
        self.logo_url_input.setPlaceholderText("输入LOGO图片URL地址")
        form_layout.addRow("LOGO地址:", self.logo_url_input)
        
        layout.addLayout(form_layout)
        
        # 按钮区域
        button_layout = QtWidgets.QHBoxLayout()
        
        self.ok_btn = QtWidgets.QPushButton("确定")
        self.ok_btn.clicked.connect(self.accept)
        
        self.cancel_btn = QtWidgets.QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(self.ok_btn)
        button_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(button_layout)
        
    def get_mapping_data(self):
        """获取映射数据"""
        standard_name = self.standard_name_input.text().strip()
        raw_name = self.raw_name_input.text().strip()
        group_name = self.group_name_input.text().strip()
        logo_url = self.logo_url_input.text().strip()
        
        if not standard_name or not raw_name:
            QtWidgets.QMessageBox.warning(self, "输入错误", "标准名称和原始名称不能为空")
            return None
            
        return {
            'standard_name': standard_name,
            'raw_name': raw_name,
            'group_name': group_name if group_name else None,
            'logo_url': logo_url if logo_url else None
        }
