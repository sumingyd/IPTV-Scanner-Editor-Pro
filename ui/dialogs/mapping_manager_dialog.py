from PyQt6 import QtWidgets, QtCore, QtGui
from core.log_manager import LogManager
from models.channel_mappings import mapping_manager
from utils.error_handler import show_error, show_warning, show_info, show_confirm
from ..floating_dialog import FloatingDialog


class MappingManagerDialog(FloatingDialog):
    """频道映射管理器对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = LogManager()
        self.parent = parent
        # 从主题获取透明度设置
        from ..styles import AppStyles
        colors = AppStyles._get_colors()
        self.opacity = colors.get('window_opacity', 220)

        # 获取语言管理器
        if parent and hasattr(parent, 'language_manager'):
            self.language_manager = parent.language_manager
        else:
            from core.language_manager import LanguageManager
            self.language_manager = LanguageManager()
            self.language_manager.load_available_languages()
            self.language_manager.set_language('zh')

        self.setWindowTitle(self.language_manager.tr('mapping_manager', 'Channel Mapping Manager'))
        self.setMinimumSize(800, 600)
        self.setup_ui()
        self.load_mappings()

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.dragging = True
            self.offset = event.position().toPoint()

    def mouseMoveEvent(self, event):
        if self.dragging:
            new_position = event.globalPosition().toPoint() - self.offset
            self.move(new_position)

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.dragging = False

    def paintEvent(self, event):
        """自定义绘制半透明背景和边框"""
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        
        from ui.styles import AppStyles
        colors = AppStyles._get_colors()
        neo = AppStyles.is_neumorphic()
        
        path = QtGui.QPainterPath()
        rect = QtCore.QRectF(self.rect().adjusted(1, 1, -1, -1))
        path.addRoundedRect(rect, 12, 12)
        
        bg_color = colors.get('window', '#333333')
        if bg_color.startswith('#'):
            r = int(bg_color[1:3], 16)
            g = int(bg_color[3:5], 16)
            b = int(bg_color[5:7], 16)
        else:
            r, g, b = 30, 30, 30
        painter.fillPath(path, QtGui.QColor(r, g, b, self.opacity))
        
        if not neo:
            border_color = colors.get('mid', '#999999')
            if border_color.startswith('#'):
                r = int(border_color[1:3], 16)
                g = int(border_color[3:5], 16)
                b = int(border_color[5:7], 16)
            else:
                r, g, b = 120, 120, 120
            painter.setPen(QtGui.QColor(r, g, b, 200))
            painter.drawPath(path)
        
        super().paintEvent(event)

    def setup_ui(self):
        """设置用户界面"""
        layout = QtWidgets.QVBoxLayout(self)
        tr = self.language_manager.tr

        from ui.styles import AppStyles

        self.setStyleSheet(AppStyles.dialog_style())

        self.tab_widget = QtWidgets.QTabWidget()
        self.tab_widget.setStyleSheet(AppStyles.tab_widget_style())

        self.user_mapping_tab = self.create_user_mapping_tab()
        self.tab_widget.addTab(self.user_mapping_tab, tr('user_mapping_management', 'User Mapping Management'))

        self.fingerprint_tab = self.create_fingerprint_tab()
        self.tab_widget.addTab(self.fingerprint_tab, tr('channel_fingerprints', 'Channel Fingerprints'))

        self.suggestion_tab = self.create_suggestion_tab()
        self.tab_widget.addTab(self.suggestion_tab, tr('mapping_suggestions', 'Mapping Suggestions'))

        layout.addWidget(self.tab_widget)

        button_layout = QtWidgets.QHBoxLayout()

        self.refresh_cache_btn = QtWidgets.QPushButton(tr('refresh_remote_cache', 'Refresh Remote Cache'))
        self.refresh_cache_btn.setStyleSheet(AppStyles.common_button_style())
        self.refresh_cache_btn.clicked.connect(self.refresh_cache)

        self.export_mappings_btn = QtWidgets.QPushButton(tr('export_user_mappings', 'Export User Mappings'))
        self.export_mappings_btn.setStyleSheet(AppStyles.common_button_style())
        self.export_mappings_btn.clicked.connect(self.export_mappings)

        self.import_mappings_btn = QtWidgets.QPushButton(tr('import_user_mappings', 'Import User Mappings'))
        self.import_mappings_btn.setStyleSheet(AppStyles.common_button_style())
        self.import_mappings_btn.clicked.connect(self.import_mappings)

        self.close_btn = QtWidgets.QPushButton(tr('close', 'Close'))
        self.close_btn.setStyleSheet(AppStyles.common_button_style())
        self.close_btn.clicked.connect(self.accept)

        button_layout.addWidget(self.refresh_cache_btn)
        button_layout.addWidget(self.export_mappings_btn)
        button_layout.addWidget(self.import_mappings_btn)
        button_layout.addStretch()
        button_layout.addWidget(self.close_btn)

        layout.addLayout(button_layout)

    def create_user_mapping_tab(self):
        """创建用户映射管理选项卡"""
        tr = self.language_manager.tr
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)

        from ui.styles import AppStyles

        search_layout = QtWidgets.QHBoxLayout()
        self.search_input = QtWidgets.QLineEdit()
        self.search_input.setStyleSheet(AppStyles.common_line_edit_style())
        self.search_input.setPlaceholderText(tr('search_channel_name', 'Search channel name...'))
        self.search_input.textChanged.connect(self.filter_mappings)

        self.search_options = QtWidgets.QComboBox()
        self.search_options.setStyleSheet(AppStyles.common_combo_box_style())
        self.search_options.currentTextChanged.connect(self.filter_mappings)

        self.search_label = QtWidgets.QLabel((tr('search', 'Search') or 'Search') + ":")
        self.search_label.setStyleSheet(AppStyles.common_label_style())
        self.search_scope_label = QtWidgets.QLabel((tr('search_scope', 'Search Scope') or 'Search Scope') + ":")
        self.search_scope_label.setStyleSheet(AppStyles.common_label_style())

        search_layout.addWidget(self.search_label)
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(self.search_scope_label)
        search_layout.addWidget(self.search_options)
        search_layout.addStretch()

        layout.addLayout(search_layout)

        self.mapping_table = QtWidgets.QTableWidget()
        self.mapping_table.setStyleSheet(AppStyles.table_style())
        self.mapping_table.setColumnCount(4)
        self.mapping_table.setHorizontalHeaderLabels([
            tr('standard_name', 'Standard Name'),
            tr('raw_name', 'Raw Name'),
            tr('group', 'Group'),
            tr('logo_address', 'Logo Address')
        ])
        self.mapping_table.horizontalHeader().setStretchLastSection(True)
        self.mapping_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.mapping_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)

        layout.addWidget(self.mapping_table)

        button_layout = QtWidgets.QHBoxLayout()

        self.add_mapping_btn = QtWidgets.QPushButton(tr('add_mapping', 'Add Mapping'))
        self.add_mapping_btn.setStyleSheet(AppStyles.common_button_style())
        self.add_mapping_btn.clicked.connect(self.add_mapping)

        self.edit_mapping_btn = QtWidgets.QPushButton(tr('edit_mapping', 'Edit Mapping'))
        self.edit_mapping_btn.setStyleSheet(AppStyles.common_button_style())
        self.edit_mapping_btn.clicked.connect(self.edit_mapping)

        self.delete_mapping_btn = QtWidgets.QPushButton(tr('delete_mapping', 'Delete Mapping'))
        self.delete_mapping_btn.setStyleSheet(AppStyles.common_button_style())
        self.delete_mapping_btn.clicked.connect(self.delete_mapping)

        button_layout.addWidget(self.add_mapping_btn)
        button_layout.addWidget(self.edit_mapping_btn)
        button_layout.addWidget(self.delete_mapping_btn)
        button_layout.addStretch()

        layout.addLayout(button_layout)

        return widget

    def create_fingerprint_tab(self):
        """创建频道指纹查看选项卡"""
        tr = self.language_manager.tr
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)

        from ui.styles import AppStyles

        self.fingerprint_table = QtWidgets.QTableWidget()
        self.fingerprint_table.setStyleSheet(AppStyles.table_style())
        self.fingerprint_table.setColumnCount(5)
        self.fingerprint_table.setHorizontalHeaderLabels([
            tr('fingerprint_id', 'Fingerprint ID'),
            tr('raw_name', 'Raw Name'),
            tr('mapped_name', 'Mapped Name'),
            tr('occurrence_count', 'Occurrence Count'),
            tr('last_seen', 'Last Seen')
        ])
        self.fingerprint_table.horizontalHeader().setStretchLastSection(True)
        self.fingerprint_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)

        layout.addWidget(self.fingerprint_table)

        button_layout = QtWidgets.QHBoxLayout()

        self.clear_fingerprints_btn = QtWidgets.QPushButton(tr('clear_fingerprint_data', 'Clear Fingerprint Data'))
        self.clear_fingerprints_btn.setStyleSheet(AppStyles.common_button_style())
        self.clear_fingerprints_btn.clicked.connect(self.clear_fingerprints)

        self.analyze_fingerprints_btn = QtWidgets.QPushButton(tr('analyze_unstable_mappings', 'Analyze Unstable Mappings'))
        self.analyze_fingerprints_btn.setStyleSheet(AppStyles.common_button_style())
        self.analyze_fingerprints_btn.clicked.connect(self.analyze_fingerprints)

        button_layout.addWidget(self.clear_fingerprints_btn)
        button_layout.addWidget(self.analyze_fingerprints_btn)
        button_layout.addStretch()

        layout.addLayout(button_layout)

        return widget

    def create_suggestion_tab(self):
        """创建映射建议选项卡"""
        tr = self.language_manager.tr
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)

        from ui.styles import AppStyles

        self.suggestion_table = QtWidgets.QTableWidget()
        self.suggestion_table.setStyleSheet(AppStyles.table_style())
        self.suggestion_table.setColumnCount(4)
        self.suggestion_table.setHorizontalHeaderLabels([
            tr('raw_name', 'Raw Name'),
            tr('suggested_mapping', 'Suggested Mapping'),
            tr('confidence', 'Confidence'),
            tr('operation', 'Operation')
        ])
        self.suggestion_table.horizontalHeader().setStretchLastSection(True)

        layout.addWidget(self.suggestion_table)

        self.refresh_suggestions_btn = QtWidgets.QPushButton(tr('refresh_suggestions', 'Refresh Suggestions'))
        self.refresh_suggestions_btn.setStyleSheet(AppStyles.common_button_style())
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
            # 使用统一的错误处理
            title = self.language_manager.tr('warning', 'Warning') or 'Warning'
            message = self.language_manager.tr('select_mapping_to_edit', 'Please select a mapping to edit') or 'Please select a mapping to edit'
            show_warning(title, message, parent=self)
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
            title = self.language_manager.tr('warning', 'Warning') or 'Warning'
            message = self.language_manager.tr('select_mapping_to_delete', 'Please select a mapping to delete') or 'Please select a mapping to delete'
            show_warning(title, message, parent=self)
            return

        row = selected_rows[0].row()
        standard_name = self.mapping_table.item(row, 0).text()
        raw_name = self.mapping_table.item(row, 1).text()

        # 使用统一的错误处理
        reply = show_confirm(
            "确认删除",
            f"确定要删除映射 '{raw_name} -> {standard_name}' 吗？",
            parent=self
        )

        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            mapping_manager.remove_user_mapping(standard_name)
            self.load_user_mappings()
            self.logger.info(f"删除用户映射: {raw_name} -> {standard_name}")

    def refresh_cache(self):
        """刷新远程映射缓存"""
        mapping_manager.refresh_cache()
        # 使用统一的错误处理
        show_info("成功", "远程映射缓存已刷新", parent=self)

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

                # 使用统一的错误处理
                show_info("成功", f"用户映射已导出到: {file_path}", parent=self)
            except Exception as e:
                # 使用统一的错误处理
                show_error("错误", f"导出失败: {str(e)}", parent=self)

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
                # 修复：正确调用create_reverse_mappings函数
                from models.channel_mappings import create_reverse_mappings
                mapping_manager.reverse_mappings = create_reverse_mappings(mapping_manager.combined_mappings)

                self.load_user_mappings()
                # 使用统一的错误处理
                show_info("成功", "用户映射已从CSV文件导入", parent=self)
            except Exception as e:
                # 使用统一的错误处理
                show_error("错误", f"导入失败: {str(e)}", parent=self)

    def clear_fingerprints(self):
        """清空指纹数据"""
        # 使用统一的错误处理
        reply = show_confirm(
            "确认清空",
            "确定要清空所有频道指纹数据吗？",
            parent=self
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

            # 使用统一的错误处理
            show_info("不稳定映射分析", message, parent=self)
        else:
            # 使用统一的错误处理
            show_info("分析结果", "未发现明显不稳定的映射", parent=self)

        # 将建议映射保存到实例变量中，供映射建议选项卡使用
        self.suggestion_mappings = suggestion_mappings

    def refresh_suggestions(self):
        """刷新映射建议"""
        # 重新分析指纹数据以获取最新的建议
        self.analyze_fingerprints()

        # 加载建议到表格
        self.load_suggestions()

        if self.suggestion_mappings:
            # 使用统一的错误处理
            show_info("成功", f"已生成 {len(self.suggestion_mappings)} 条映射建议", parent=self)
        else:
            # 使用统一的错误处理
            show_info("提示", "暂无映射建议，请先进行扫描以收集数据", parent=self)

    def apply_suggestion(self, row_index):
        """应用映射建议"""
        if not hasattr(self, 'suggestion_mappings') or row_index >= len(self.suggestion_mappings):
            # 使用统一的错误处理
            show_warning("错误", "无法应用此建议", parent=self)
            return

        suggestion = self.suggestion_mappings[row_index]
        raw_name = suggestion['raw_name']
        suggested_mapping = suggestion['suggested_mapping']

        # 确认应用建议
        # 使用统一的错误处理
        reply = show_confirm(
            "确认应用建议",
            f"确定要将 '{raw_name}' 映射到 '{suggested_mapping}' 吗？",
            parent=self
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

            # 使用统一的错误处理
            show_info("成功", f"已应用映射建议: {raw_name} -> {suggested_mapping}", parent=self)

    def update_ui_texts(self):
        """更新UI文本到当前语言"""
        if not hasattr(self, 'language_manager') or not self.language_manager.translations:
            return

        try:
            # 更新窗口标题
            self.setWindowTitle(self.language_manager.tr('mapping_manager', 'Channel Mapping Manager'))

            # 更新选项卡标题
            self.tab_widget.setTabText(0,
                                       self.language_manager.tr('user_mapping_management', 'User Mapping Management'))
            self.tab_widget.setTabText(1,
                                       self.language_manager.tr('channel_fingerprints', 'Channel Fingerprints'))
            self.tab_widget.setTabText(2,
                                       self.language_manager.tr('mapping_suggestions', 'Mapping Suggestions'))

            # 更新按钮文本
            self.refresh_cache_btn.setText(self.language_manager.tr('refresh_remote_cache', 'Refresh Remote Cache'))
            self.export_mappings_btn.setText(self.language_manager.tr('export_user_mappings', 'Export User Mappings'))
            self.import_mappings_btn.setText(self.language_manager.tr('import_user_mappings', 'Import User Mappings'))
            self.close_btn.setText(self.language_manager.tr('close', 'Close'))

            # 更新用户映射管理选项卡
            self.search_input.setPlaceholderText(
                self.language_manager.tr('search_channel_name', 'Search channel name...'))

            # 更新搜索标签
            search_text = self.language_manager.tr('search', 'Search') or 'Search'
            search_scope_text = self.language_manager.tr('search_scope', 'Search Scope') or 'Search Scope'
            self.search_label.setText(search_text + ":")
            self.search_scope_label.setText(search_scope_text + ":")

            # 更新搜索选项
            self.search_options.clear()
            search_all = self.language_manager.tr('search_all_fields', 'Search All Fields') or 'Search All Fields'
            search_standard = self.language_manager.tr('search_standard_name_only', 'Search Standard Name Only') or 'Search Standard Name Only'
            search_raw = self.language_manager.tr('search_raw_name_only', 'Search Raw Name Only') or 'Search Raw Name Only'
            search_group = self.language_manager.tr('search_group_only', 'Search Group Only') or 'Search Group Only'
            self.search_options.addItems([search_all, search_standard, search_raw, search_group])

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
            self.clear_fingerprints_btn.setText(
                self.language_manager.tr('clear_fingerprint_data', 'Clear Fingerprint Data'))
            self.analyze_fingerprints_btn.setText(
                self.language_manager.tr('analyze_unstable_mappings', 'Analyze Unstable Mappings'))

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

        if parent and hasattr(parent, 'language_manager'):
            self.language_manager = parent.language_manager
        else:
            from core.language_manager import LanguageManager
            self.language_manager = LanguageManager()
            self.language_manager.load_available_languages()
            self.language_manager.set_language('zh')

        tr = self.language_manager.tr
        self.setWindowTitle(tr('edit_mapping', 'Edit Mapping') if standard_name else tr('add_mapping', 'Add Mapping'))
        self.setup_ui()

    def setup_ui(self):
        """设置用户界面"""
        layout = QtWidgets.QVBoxLayout(self)
        tr = self.language_manager.tr

        from ui.styles import AppStyles

        self.setStyleSheet(AppStyles.dialog_style())

        form_layout = QtWidgets.QFormLayout()

        self.standard_name_input = QtWidgets.QLineEdit(self.standard_name)
        self.standard_name_input.setStyleSheet(AppStyles.common_line_edit_style())
        self.standard_name_input.setPlaceholderText(tr('standard_name_placeholder', 'Enter standard channel name') or 'Enter standard channel name')
        label1 = QtWidgets.QLabel((tr('standard_name', 'Standard Name') or 'Standard Name') + ":")
        label1.setStyleSheet(AppStyles.common_label_style())
        form_layout.addRow(label1, self.standard_name_input)

        self.raw_name_input = QtWidgets.QLineEdit(self.raw_name)
        self.raw_name_input.setStyleSheet(AppStyles.common_line_edit_style())
        self.raw_name_input.setPlaceholderText(tr('raw_name_placeholder', 'Enter raw channel name') or 'Enter raw channel name')
        label2 = QtWidgets.QLabel((tr('raw_name', 'Raw Name') or 'Raw Name') + ":")
        label2.setStyleSheet(AppStyles.common_label_style())
        form_layout.addRow(label2, self.raw_name_input)

        self.group_name_input = QtWidgets.QLineEdit(self.group_name)
        self.group_name_input.setStyleSheet(AppStyles.common_line_edit_style())
        self.group_name_input.setPlaceholderText(tr('group_placeholder', 'Enter group name') or 'Enter group name')
        label3 = QtWidgets.QLabel((tr('group', 'Group') or 'Group') + ":")
        label3.setStyleSheet(AppStyles.common_label_style())
        form_layout.addRow(label3, self.group_name_input)

        self.logo_url_input = QtWidgets.QLineEdit(self.logo_url)
        self.logo_url_input.setStyleSheet(AppStyles.common_line_edit_style())
        self.logo_url_input.setPlaceholderText(tr('logo_url_placeholder', 'Enter logo URL') or 'Enter logo URL')
        label4 = QtWidgets.QLabel((tr('logo_address', 'Logo Address') or 'Logo Address') + ":")
        label4.setStyleSheet(AppStyles.common_label_style())
        form_layout.addRow(label4, self.logo_url_input)

        layout.addLayout(form_layout)

        button_layout = QtWidgets.QHBoxLayout()

        self.ok_btn = QtWidgets.QPushButton(tr('ok_button', 'OK'))
        self.ok_btn.setStyleSheet(AppStyles.common_button_style())
        self.ok_btn.clicked.connect(self.accept)

        self.cancel_btn = QtWidgets.QPushButton(tr('cancel_button', 'Cancel'))
        self.cancel_btn.setStyleSheet(AppStyles.common_button_style())
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
            # 使用统一的错误处理
            show_warning("输入错误", "标准名称和原始名称不能为空", parent=self)
            return None

        return {
            'standard_name': standard_name,
            'raw_name': raw_name,
            'group_name': group_name if group_name else None,
            'logo_url': logo_url if logo_url else None
        }

    def paintEvent(self, event):
        """自定义绘制半透明背景和边框"""
        from PyQt6.QtGui import QPainter, QPainterPath, QColor, QPen
        from PyQt6.QtCore import QRectF
        from ui.styles import AppStyles
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        colors = AppStyles._get_colors()
        neo = AppStyles.is_neumorphic()
        
        path = QPainterPath()
        rect = QRectF(self.rect().adjusted(1, 1, -1, -1))
        path.addRoundedRect(rect, 12, 12)
        
        bg_color = colors.get('window', '#333333')
        if bg_color.startswith('#'):
            r = int(bg_color[1:3], 16)
            g = int(bg_color[3:5], 16)
            b = int(bg_color[5:7], 16)
        else:
            r, g, b = 30, 30, 30
        painter.fillPath(path, QColor(r, g, b, 220))
        
        if not neo:
            border_color = colors.get('mid', '#999999')
            if border_color.startswith('#'):
                r = int(border_color[1:3], 16)
                g = int(border_color[3:5], 16)
                b = int(border_color[5:7], 16)
            else:
                r, g, b = 120, 120, 120
            painter.setPen(QColor(r, g, b, 200))
            painter.drawPath(path)
        
        super().paintEvent(event)
