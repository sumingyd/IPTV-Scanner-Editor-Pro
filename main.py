from PyQt6 import QtWidgets, QtCore, QtGui
import time
import threading
import os
import sys
import random

# 核心模块导入
from channel_model import ChannelListModel
from ui_builder import UIBuilder
from config_manager import ConfigManager
from log_manager import LogManager, global_logger
from scanner_controller import ScannerController
from styles import AppStyles
from player_controller import PlayerController
from list_manager import ListManager
from url_parser import URLRangeParser
from language_manager import LanguageManager
from ui_optimizer import get_ui_optimizer
from error_handler import init_global_error_handler

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        # 在UI构建前完全隐藏窗口，防止任何闪动
        self.hide()
        
        # 初始化配置和日志管理器
        self.config = ConfigManager()
        self.logger = global_logger
        
        # 初始化语言管理器（确保在UI构建前可用）
        self.language_manager = LanguageManager()
        self.language_manager.load_available_languages()
        
        # 立即加载保存的语言设置，确保UI构建时使用正确的语言
        language_code = self.config.load_language_settings()
        if self.language_manager.set_language(language_code):
            self.logger.info(f"语言设置已加载: {language_code}")
        
        # 确保在主线程创建
        
        # 构建UI
        self.ui = UIBuilder(self)
        self.ui.build_ui()
        
        # 立即更新UI文本到当前语言
        if hasattr(self, 'language_manager'):
            self.language_manager.update_ui_texts(self)
        
        # 设置窗口图标
        if os.path.exists('logo.ico'):
            self.setWindowIcon(QtGui.QIcon('logo.ico'))
        
        # 立即加载配置到UI
        self._load_config()
        
        # 初始化主窗口的后续设置
        self._init_main_window()
        
        # 用于管理所有定时器
        self._timers = []
        
        # 确保所有定时器在主线程创建
        QtCore.QTimer.singleShot(0, self._init_timers)
        
        
    def _init_timers(self):
        """在主线程初始化所有定时器"""
        # 定时器管理器：统一管理所有定时器
        # 当前暂无需要管理的定时器，保留结构便于扩展
        pass
        
    def _stop_all_timers(self):
        """安全停止所有定时器"""
        if hasattr(self, '_timers'):
            for timer in self._timers:
                if timer.isActive():
                    if QtCore.QThread.currentThread() == timer.thread():
                        timer.stop()
                    else:
                        QtCore.QMetaObject.invokeMethod(timer, "stop", QtCore.Qt.ConnectionType.QueuedConnection)
            self._timers.clear()
        
    def _init_main_window(self):
        """初始化主窗口的后续设置"""
        # 使用UI构建器中已经创建的模型，避免重复设置
        # 模型已经在ui_builder.py的_setup_channel_list方法中正确设置
        self.model = self.ui.main_window.model
        
        # 设置模型的父对象为主窗口，确保可以访问UI层的方法
        self.model.setParent(self)
        
        # 初始化控制器
        self.init_controllers()

        # 初始化UI优化器和错误处理器
        self.ui_optimizer = get_ui_optimizer()
        self.error_handler = init_global_error_handler(self)
        
        # 优化频道列表视图性能
        self.ui_optimizer.optimize_table_view(self.ui.main_window.channel_list)

        # UI构建完成后加载配置
        self._load_config()
        
        # 连接信号槽
        self._connect_signals()

    def init_controllers(self):
        """初始化所有控制器"""
        # 确保只创建一个扫描器对象
        if not hasattr(self, 'scanner') or self.scanner is None:
            self.scanner = ScannerController(self.model, self)
        self.player_controller = PlayerController(self.ui.main_window.player, self.model)
        self.list_manager = ListManager(self.model)
        
        # 立即连接进度条更新信号
        self._connect_progress_signals()
        
        # 初始化播放器按钮状态
        self._on_play_state_changed(self.player_controller.is_playing)

    def _connect_progress_signals(self):
        """连接进度条更新信号"""
        self.logger.debug("开始连接进度条更新信号")
        
        # 检查是否已经连接过信号
        if hasattr(self, '_progress_signals_connected') and self._progress_signals_connected:
            self.logger.debug("进度条信号已经连接，跳过重复连接")
            return
            
        # 进度更新信号 - 更新状态栏的进度条
        def update_progress_bars(cur, total):
            progress_value = int(cur / total * 100) if total > 0 else 0
            self.logger.debug(f"UI进度条更新函数调用: {cur}/{total} -> {progress_value}%")
            
            # 检查进度条对象是否存在
            if not hasattr(self.ui.main_window, 'progress_indicator'):
                self.logger.error("进度条对象不存在")
                return
                
            if self.ui.main_window.progress_indicator is None:
                self.logger.error("进度条对象为None")
                return
                
            # 设置进度条值
            try:
                self.ui.main_window.progress_indicator.setValue(progress_value)
                self.logger.debug(f"进度条值已设置为: {progress_value}%")
            except Exception as e:
                self.logger.error(f"设置进度条值失败: {e}")
            
        # 检查扫描器对象和信号
        self.logger.debug(f"扫描器对象: {self.scanner}")
        self.logger.debug(f"进度条更新信号: {self.scanner.progress_updated}")
        
        # 连接信号
        self.scanner.progress_updated.connect(update_progress_bars)
        self.logger.debug("进度条更新信号已连接")
        
        # 扫描开始时显示状态栏进度条
        self.scanner.progress_updated.connect(
            lambda cur, total: self.ui.main_window.progress_indicator.show() if total > 0 else None
        )
        
        # 扫描完成时隐藏状态栏进度条
        self.scanner.scan_completed.connect(
            lambda: self.ui.main_window.progress_indicator.hide()
        )
        
        # 标记信号已连接
        self._progress_signals_connected = True
        

    # 废弃方法已移除：_update_validate_status
    # 功能已迁移到状态栏统计标签

    def _load_config(self):
        """加载保存的配置到UI"""
        try:
            settings = self.config.load_network_settings()
            if settings['url']:
                self.ui.main_window.ip_range_input.setText(settings['url'])
            self.ui.main_window.timeout_input.setValue(int(settings['timeout']))
            self.ui.main_window.thread_count_input.setValue(int(settings['threads']))
            if settings['user_agent']:
                self.ui.main_window.user_agent_input.setText(settings['user_agent'])
            if settings['referer']:
                self.ui.main_window.referer_input.setText(settings['referer'])
            
            # 加载语言设置（不在这里更新UI文本，由后台任务统一处理）
            language_code = self.config.load_language_settings()
            if hasattr(self, 'language_manager'):
                self.language_manager.set_language(language_code)
                    
        except Exception as e:
            self.logger.error(f"加载配置失败: {e}")
            # 设置默认值
            self.ui.main_window.timeout_input.setValue(10)
            self.ui.main_window.thread_count_input.setValue(5)

    def _connect_signals(self):
        """连接所有信号和槽"""
        # 连接频道列表选择信号
        self.ui.main_window.channel_list.selectionModel().selectionChanged.connect(
            self._on_channel_selected
        )
        
        # 连接扫描按钮
        try:
            self.ui.main_window.scan_btn.clicked.disconnect()
        except:
            pass
        self.ui.main_window.scan_btn.clicked.connect(self._on_scan_clicked)
                
        # 工具栏按钮现在在UI构建器中直接连接信号，不需要在这里手动连接
                
        # 连接播放控制信号
        self.ui.main_window.volume_slider.valueChanged.connect(
            self._on_volume_changed)
        self.ui.main_window.pause_btn.clicked.connect(
            self._on_pause_clicked)
        self.ui.main_window.stop_btn.clicked.connect(
            self._on_stop_clicked)
        
        # 连接播放状态变化信号
        self.player_controller.play_state_changed.connect(
            self._on_play_state_changed)
        
        # 连接频道列表双击事件
        self.ui.main_window.channel_list.doubleClicked.connect(self._play_selected_channel)
        
        # 连接有效性检测按钮
        self.ui.main_window.btn_validate.clicked.connect(self._on_validate_clicked)
        
        # 连接隐藏无效项按钮
        self.ui.main_window.btn_hide_invalid.clicked.connect(self._on_hide_invalid_clicked)
        
        # 连接直接生成列表按钮
        self.ui.main_window.generate_btn.clicked.connect(self._on_generate_clicked)
        
        # 有效性检测完成时也隐藏状态栏进度条
        self.scanner.scan_completed.connect(
            lambda: self.ui.main_window.progress_indicator.hide()
        )
        
        # 频道发现信号
        self.scanner.channel_found.connect(self._on_channel_found)
        
        # 扫描完成信号
        self.scanner.scan_completed.connect(self._on_scan_completed)
        
        # 统计信息更新信号 - 使用QueuedConnection确保跨线程安全
        self.logger.debug(f"开始连接统计信息更新信号，扫描器对象: {self.scanner}")
        self.logger.debug(f"扫描器信号: {self.scanner.stats_updated}")
        self.scanner.stats_updated.connect(self._update_stats_display, QtCore.Qt.ConnectionType.QueuedConnection)
        self.logger.debug("统计信息更新信号已连接 (QueuedConnection)")

    def _on_scan_clicked(self):
        """处理扫描按钮点击事件 - 使用QTimer避免UI阻塞"""
        if self.scanner.is_scanning():
            # 停止扫描 - 立即响应
            self.scanner.stop_scan()
            self._set_scan_button_text('full_scan', '完整扫描')
        else:
            # 检查地址是否为空
            url = self.ui.main_window.ip_range_input.text()
            if not url.strip():
                self.logger.warning("请输入扫描地址")
                self.ui.main_window.statusBar().showMessage("请输入扫描地址", 3000)
                return
                
            # 使用QTimer延迟执行扫描，避免UI阻塞
            QtCore.QTimer.singleShot(0, lambda: self._start_scan_delayed(url))
            
    def _start_scan_delayed(self, url):
        """延迟启动扫描，避免UI阻塞"""
        # 开始扫描前清空列表
        self.model.clear()
        timeout = self.ui.main_window.timeout_input.value()
        threads = self.ui.main_window.thread_count_input.value()
        self.scanner.start_scan(url, threads, timeout)
        self._set_scan_button_text('stop_scan', '停止扫描')
        
    def _set_scan_button_text(self, translation_key, default_text):
        """设置扫描按钮文本（统一处理语言管理器）"""
        if hasattr(self, 'language_manager') and self.language_manager:
            self.ui.main_window.scan_btn.setText(
                self.language_manager.tr(translation_key, default_text)
            )
        else:
            self.ui.main_window.scan_btn.setText(default_text)

    def _validate_all_channels(self, timeout: int, threads: int):
        """验证所有频道的有效性"""
        self.scanner.timeout = timeout
        self.scanner.stop_event.clear()
        
        # 初始化统计信息
        self.scanner.stats = {
            'total': self.ui.main_window.model.rowCount(),
            'valid': 0,
            'invalid': 0,
            'start_time': time.time(),
            'elapsed': 0
        }
        
        # 填充任务队列
        for i in range(self.ui.main_window.model.rowCount()):
            channel = self.ui.main_window.model.get_channel(i)
            self.scanner.worker_queue.put(channel['url'])
            
        # 创建工作线程
        self.scanner.workers = []
        for i in range(threads):
            worker = threading.Thread(
                target=self.scanner._worker,
                name=f"ValidatorWorker-{i}",
                daemon=True
            )
            worker.start()
            self.scanner.workers.append(worker)
            
        # 启动统计更新线程
        stats_thread = threading.Thread(
            target=self.scanner._update_stats,
            name="StatsUpdater",
            daemon=True
        )
        stats_thread.start()

    def _on_volume_changed(self, value):
        """处理音量滑块变化"""
        self.player_controller.set_volume(value)

    def _on_pause_clicked(self):
        """处理暂停/播放按钮点击"""
        # 立即更新按钮文本，避免异步延迟
        current_playing = self.player_controller.is_playing
        self._set_pause_button_text(not current_playing)
        
        # 执行暂停/播放操作
        self.player_controller.toggle_pause()

    def _on_stop_clicked(self):
        """处理停止按钮点击"""
        self.player_controller.stop()
        self._set_pause_button_text(False)
        
    def _set_pause_button_text(self, is_playing):
        """设置暂停/播放按钮文本（统一处理语言管理器）"""
        if hasattr(self, 'language_manager') and self.language_manager:
            if is_playing:
                self.ui.main_window.pause_btn.setText(
                    self.language_manager.tr('pause', 'Pause')
                )
            else:
                self.ui.main_window.pause_btn.setText(
                    self.language_manager.tr('play', 'Play')
                )
        else:
            self.ui.main_window.pause_btn.setText("暂停" if is_playing else "播放")

    def _on_play_state_changed(self, is_playing):
        """处理播放状态变化"""
        # 更新停止按钮状态
        self.ui.main_window.stop_btn.setEnabled(is_playing)
        self.ui.main_window.stop_btn.setStyleSheet(
            AppStyles.button_style(active=is_playing)
        )
        
        # 更新暂停/播放按钮文本
        self._set_pause_button_text(is_playing)

    def _open_list(self):
        """打开列表文件"""
        try:
            success, error_msg = self.list_manager.open_list(self)
                
            if success:
                self.ui.main_window.btn_hide_invalid.setEnabled(False)
                self.ui.main_window.btn_validate.setEnabled(True)
                self.ui.main_window.statusBar().showMessage("列表加载成功", 3000)
                
                # 强制触发模型重置信号
                self.model.modelReset.emit()
                return True
            else:
                self.logger.warning(f"打开列表失败: {error_msg}")
                self.ui.main_window.statusBar().showMessage(f"打开列表失败: {error_msg}", 3000)
                return False
        except Exception as e:
            error_msg = f"打开列表失败: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            self.ui.main_window.statusBar().showMessage(error_msg, 3000)
            return False

    def _save_list(self):
        """保存列表文件"""
        try:
            result = self.list_manager.save_list(self)
            if result:
                self.logger.info("列表保存成功")
                self.ui.main_window.statusBar().showMessage("列表保存成功", 3000)
                return True
            else:
                self.logger.warning("列表保存失败")
                self.ui.main_window.statusBar().showMessage("列表保存失败", 3000)
                return False
                    
        except Exception as e:
            self.logger.error(f"保存列表失败: {e}", exc_info=True)
            self.ui.main_window.statusBar().showMessage(f"保存列表失败: {str(e)}", 3000)
            return False

    def _on_validate_clicked(self):
        """处理有效性检测按钮点击事件"""
        if not self.ui.main_window.model.rowCount():
            self.logger.warning("请先加载列表")
            return
            
        if not hasattr(self.scanner, 'is_validating') or not self.scanner.is_validating:
            # 开始有效性检测
            timeout = self.ui.main_window.timeout_input.value()
            threads = self.ui.main_window.thread_count_input.value()
            self.scanner.start_validation(
                self.ui.main_window.model,
                threads,
                timeout
            )
            self.ui.main_window.btn_validate.setText("停止检测")
            self.ui.main_window.btn_hide_invalid.setEnabled(True)
            self.ui.main_window.btn_hide_invalid.setStyleSheet(
                AppStyles.button_style(active=True)
            )
            
            # 连接验证结果信号
            self.scanner.channel_validated.connect(self._on_channel_validated)
        else:
            # 停止有效性检测
            self.scanner.stop_validation()
            self.ui.main_window.btn_validate.setText("检测有效性")
            
    def _on_channel_selected(self):
        """处理频道选择事件"""
        selected = self.ui.main_window.channel_list.selectedIndexes()
        if not selected:
            return
            
        # 获取选中的频道
        row = selected[0].row()
        self.current_channel_index = row


    def _on_channel_validated(self, index, valid, latency, resolution):
        """处理频道验证结果"""
        channel = self.ui.main_window.model.get_channel(index)
        channel['valid'] = valid
        channel['latency'] = latency
        channel['resolution'] = resolution
        channel['status'] = '有效' if valid else '无效'
        
        # 通知模型更新
        self.ui.main_window.model.dataChanged.emit(
            self.ui.main_window.model.index(index, 0),
            self.ui.main_window.model.index(index, self.ui.main_window.model.columnCount() - 1)
        )

    def _on_generate_clicked(self):
        """处理直接生成列表按钮点击事件"""
        # 获取输入地址
        url = self.ui.main_window.ip_range_input.text()
        if not url.strip():
            self.logger.warning("请输入生成地址")
            self.ui.main_window.statusBar().showMessage("请输入生成地址", 3000)
            return
            
        # 清空当前列表
        self.model.clear()
        
        # 使用扫描器的URL生成器生成地址
        url_parser = URLRangeParser()
        url_generator = url_parser.parse_url(url)
        
        # 添加生成的地址到列表
        count = 0
        for batch in url_generator:
            for url in batch:
                channel = {
                    'name': f"生成频道-{count+1}",
                    'group': "生成频道",
                    'url': url,
                    'valid': False,
                    'latency': 0,
                    'status': '未检测'
                }
                self.model.add_channel(channel)
                count += 1
                
        self.ui.main_window.statusBar().showMessage(f"已生成 {count} 个频道", 3000)

    def _on_hide_invalid_clicked(self):
        """处理隐藏无效项按钮点击事件"""
        if self.ui.main_window.btn_hide_invalid.text() == "隐藏无效项":
            self.ui.main_window.model.hide_invalid()
            self.ui.main_window.btn_hide_invalid.setText("恢复隐藏项")
        else:
            self.ui.main_window.model.show_all()
            self.ui.main_window.btn_hide_invalid.setText("隐藏无效项")

    def _play_selected_channel(self, index):
        """播放选中的频道"""
        if not index.isValid():
            return
            
        channel = self.ui.main_window.model.get_channel(index.row())
        if not channel or not channel.get('url'):
            return
            
        if not hasattr(self, 'player_controller') or not self.player_controller:
            from player_controller import PlayerController
            self.player_controller = PlayerController(
                self.ui.main_window.player,
                self.model
            )
            
        # 保存当前选中的频道索引
        self.current_channel_index = index.row()
            
        if self.player_controller.play_channel(channel, self.current_channel_index):
            # 使用语言管理器设置暂停按钮文本
            if hasattr(self, 'language_manager') and self.language_manager:
                self.ui.main_window.pause_btn.setText(
                    self.language_manager.tr('pause', 'Pause')
                )
            else:
                self.ui.main_window.pause_btn.setText("暂停")
            self.current_channel = channel

    @QtCore.pyqtSlot(dict)
    def _on_channel_found(self, channel_info):
        """处理发现有效频道事件"""
        self.ui.main_window.model.add_channel(channel_info)
        
        # 添加频道后强制触发列宽调整
        if hasattr(self.ui.main_window, 'channel_list'):
            header = self.ui.main_window.channel_list.horizontalHeader()
            from PyQt6.QtCore import QTimer
            from PyQt6.QtWidgets import QHeaderView
            QTimer.singleShot(0, lambda: header.resizeSections(QHeaderView.ResizeMode.ResizeToContents))

    def _on_scan_completed(self):
        """处理扫描完成事件"""
        self.ui.main_window.scan_btn.setText("完整扫描")
        self.ui.main_window.btn_validate.setText("检测有效性")
        self.logger.info("扫描完成")
        
        # 启用智能排序按钮
        self.ui.main_window.btn_smart_sort.setEnabled(True)
        self.ui.main_window.btn_smart_sort.setStyleSheet(
            AppStyles.button_style(active=True)
        )
        
        # 扫描完成后调整列宽
        if hasattr(self.ui.main_window, 'channel_list'):
            header = self.ui.main_window.channel_list.horizontalHeader()
            header.resizeSections(QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        
        # 检查是否需要重试扫描
        if hasattr(self.ui.main_window, 'enable_retry_checkbox') and self.ui.main_window.enable_retry_checkbox.isChecked():
            self._start_retry_scan()

    @QtCore.pyqtSlot(dict)
    def _update_stats_display(self, stats_data):
        """更新统计信息显示（统一使用状态栏的统计标签）"""
        try:
            # 检查UI对象是否存在
            if not hasattr(self.ui, 'main_window') or not self.ui.main_window:
                self.logger.error("UI主窗口对象不存在")
                return
                
            if not hasattr(self.ui.main_window, 'stats_label') or not self.ui.main_window.stats_label:
                self.logger.error("状态栏统计标签不存在")
                return
            
            # 修复：stats_data现在直接包含stats字典
            stats = stats_data.get('stats', stats_data)
            elapsed = time.strftime("%H:%M:%S", time.gmtime(stats.get('elapsed', 0)))
            
            # 使用语言管理器翻译统计标签
            if hasattr(self, 'language_manager') and self.language_manager:
                total_text = self.language_manager.tr('total_channels', 'Total Channels')
                valid_text = self.language_manager.tr('valid', 'Valid')
                invalid_text = self.language_manager.tr('invalid', 'Invalid')
                time_text = self.language_manager.tr('time_elapsed', 'Time Elapsed')
                
                # 更新状态栏的统一统计标签
                stats_text = (
                    f"{total_text}: {stats.get('total', 0)} | "
                    f"{valid_text}: {stats.get('valid', 0)} | "
                    f"{invalid_text}: {stats.get('invalid', 0)} | "
                    f"{time_text}: {elapsed}"
                )
                self.ui.main_window.stats_label.setText(stats_text)
            else:
                # 更新状态栏的统一统计标签
                stats_text = (
                    f"总数: {stats.get('total', 0)} | "
                    f"有效: {stats.get('valid', 0)} | "
                    f"无效: {stats.get('invalid', 0)} | "
                    f"耗时: {elapsed}"
                )
                self.ui.main_window.stats_label.setText(stats_text)
        except Exception as e:
            self.logger.error(f"更新统计信息显示失败: {e}", exc_info=True)

    def _on_about_clicked(self):
        """处理关于按钮点击事件"""
        try:
            from about_dialog import AboutDialog
            
            # 确保在主线程中创建对话框
            dialog = AboutDialog(self)
            dialog.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)
            
            # 确保事件循环正确处理
            def show_dialog():
                try:
                    dialog.show()
                    # 立即更新UI文本到当前语言
                    if hasattr(dialog, 'update_ui_texts'):
                        dialog.update_ui_texts()
                except Exception as e:
                    self.logger.error(f"显示对话框出错: {e}")
            
            # 使用定时器确保UI更新
            QtCore.QTimer.singleShot(0, show_dialog)
            
        except ImportError as e:
            self.logger.error(f"导入AboutDialog失败: {e}")
            QtWidgets.QMessageBox.critical(
                self,
                "错误",
                "无法加载关于对话框模块"
            )
        except Exception as e:
            self.logger.error(f"显示关于对话框失败: {e}")
            QtWidgets.QMessageBox.critical(
                self,
                "错误", 
                f"无法显示关于对话框: {str(e)}"
            )
            
    def _on_mapping_clicked(self):
        """处理映射管理按钮点击事件"""
        try:
            from mapping_manager_dialog import MappingManagerDialog
            
            # 确保在主线程中创建对话框
            dialog = MappingManagerDialog(self)
            dialog.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)
            
            # 确保事件循环正确处理
            def show_dialog():
                try:
                    dialog.exec()
                except Exception as e:
                    self.logger.error(f"显示映射管理器出错: {e}")
            
            # 使用定时器确保UI更新
            QtCore.QTimer.singleShot(0, show_dialog)
            
        except ImportError as e:
            self.logger.error(f"导入MappingManagerDialog失败: {e}")
            QtWidgets.QMessageBox.critical(
                self,
                "错误",
                "无法加载映射管理器模块"
            )
        except Exception as e:
            self.logger.error(f"显示映射管理器失败: {e}")
            QtWidgets.QMessageBox.critical(
                self,
                "错误", 
                f"无法显示映射管理器: {str(e)}"
            )
            
    @QtCore.pyqtSlot(object, object, str, str)
    def _finish_refresh_channel_wrapper(self, index, new_channel_info, mapped_name, raw_name):
        """包装方法：在主线程中调用 _finish_refresh_channel"""
        try:
            self.logger.info(f"包装方法开始: 索引 {index.row()}, 原始名: {raw_name}, 新名: {mapped_name}")
            # 调用实际的完成方法
            self.ui._finish_refresh_channel(index, new_channel_info, mapped_name, raw_name)
            self.logger.info("包装方法完成")
        except Exception as e:
            self.logger.error(f"包装方法调用失败: {e}", exc_info=True)

    def init_background_tasks(self):
        """在后台线程执行的初始化任务"""
        self._load_config()
        
        # 加载保存的语言设置
        language_code = self.config.load_language_settings()
        if hasattr(self, 'language_manager') and self.language_manager.set_language(language_code):
            self.language_manager.update_ui_texts(self)

    def _start_retry_scan(self):
        """开始重试扫描 - 对第一次扫描中失效的URL进行再次扫描"""
        try:
            # 获取第一次扫描的所有URL（从扫描器统计信息中获取）
            if not hasattr(self.scanner, '_all_scanned_urls') or not self.scanner._all_scanned_urls:
                self.logger.info("没有找到第一次扫描的URL记录，无法进行重试扫描")
                self.ui.main_window.statusBar().showMessage("没有找到第一次扫描的URL记录，无法进行重试扫描", 3000)
                return
            
            # 获取当前频道列表中所有有效频道的URL
            valid_urls = set()
            for i in range(self.model.rowCount()):
                channel = self.model.get_channel(i)
                if channel.get('valid', False):
                    valid_urls.add(channel['url'])
            
            # 计算需要重试扫描的URL（第一次扫描的所有URL中，不在有效频道列表中的）
            all_scanned_urls = set(self.scanner._all_scanned_urls)
            invalid_urls = list(all_scanned_urls - valid_urls)
            
            if not invalid_urls:
                self.logger.info("没有需要重试扫描的失效URL")
                self.ui.main_window.statusBar().showMessage("没有需要重试扫描的失效URL", 3000)
                return
            
            self.logger.info(f"开始重试扫描，共 {len(invalid_urls)} 个失效URL")
            self.ui.main_window.statusBar().showMessage(f"开始重试扫描，共 {len(invalid_urls)} 个失效URL")
            
            # 设置重试扫描状态
            self._retry_scan_count = 0
            self._retry_found_channels = 0
            self._retry_urls = invalid_urls.copy()
            self._retry_loop_enabled = hasattr(self.ui.main_window, 'loop_scan_checkbox') and self.ui.main_window.loop_scan_checkbox.isChecked()
            
            # 开始重试扫描
            self._do_retry_scan()
            
        except Exception as e:
            self.logger.error(f"开始重试扫描失败: {e}", exc_info=True)
            self.ui.main_window.statusBar().showMessage(f"重试扫描失败: {str(e)}", 3000)
    
    def _do_retry_scan(self):
        """执行重试扫描"""
        if not hasattr(self, '_retry_urls') or not self._retry_urls:
            self.logger.info("重试扫描完成")
            self.ui.main_window.statusBar().showMessage("重试扫描完成", 3000)
            return
        
        # 更新重试计数
        self._retry_scan_count += 1
        self.logger.info(f"开始第 {self._retry_scan_count} 轮重试扫描，剩余 {len(self._retry_urls)} 个URL")
        self.ui.main_window.statusBar().showMessage(f"第 {self._retry_scan_count} 轮重试扫描，剩余 {len(self._retry_urls)} 个URL")
        
        # 创建临时扫描器进行重试扫描
        from scanner_controller import ScannerController
        temp_scanner = ScannerController(self.model, self)
        
        # 设置扫描参数
        timeout = self.ui.main_window.timeout_input.value()
        threads = self.ui.main_window.thread_count_input.value()
        
        # 连接信号
        temp_scanner.channel_found.connect(self._on_retry_channel_found)
        temp_scanner.scan_completed.connect(lambda: self._on_retry_scan_completed(temp_scanner))
        
        # 开始扫描
        temp_scanner.start_scan_from_urls(self._retry_urls, threads, timeout)
        
        # 更新按钮状态
        self.ui.main_window.scan_btn.setText(f"重试扫描中...")
    
    def _on_retry_channel_found(self, channel_info):
        """处理重试扫描中发现的频道"""
        self._retry_found_channels += 1
        self.logger.info(f"重试扫描发现有效频道: {channel_info['name']}")
        
        # 从重试列表中移除这个URL
        if hasattr(self, '_retry_urls') and channel_info['url'] in self._retry_urls:
            self._retry_urls.remove(channel_info['url'])
        
        # 更新主统计信息中的有效频道计数
        if hasattr(self.scanner, 'stats'):
            with self.scanner.stats_lock:
                self.scanner.stats['valid'] += 1
                # 更新统计显示
                self._update_stats_display({'stats': self.scanner.stats})
    
    def _on_retry_scan_completed(self, temp_scanner):
        """处理重试扫描完成"""
        try:
            # 清理临时扫描器
            temp_scanner.stop_scan()
            
            # 检查是否需要继续循环扫描
            if (self._retry_loop_enabled and 
                hasattr(self, '_retry_found_channels') and 
                self._retry_found_channels > 0 and
                hasattr(self, '_retry_urls') and 
                self._retry_urls):
                
                current_found = self._retry_found_channels
                # 重置发现计数，继续下一轮扫描
                self._retry_found_channels = 0
                self.logger.info(f"循环扫描：第 {self._retry_scan_count} 轮发现 {current_found} 个频道，继续扫描")
                self.ui.main_window.statusBar().showMessage(f"循环扫描：第 {self._retry_scan_count} 轮发现 {current_found} 个频道，继续第 {self._retry_scan_count + 1} 轮", 3000)
                
                # 延迟后继续扫描
                QtCore.QTimer.singleShot(1000, self._do_retry_scan)
            else:
                # 重试扫描完成
                total_found = getattr(self, '_retry_found_channels', 0)
                self.logger.info(f"重试扫描完成，共发现 {total_found} 个有效频道")
                self.ui.main_window.statusBar().showMessage(f"重试扫描完成，共发现 {total_found} 个有效频道", 5000)
                self.ui.main_window.scan_btn.setText("完整扫描")
                
                # 清理重试相关属性
                if hasattr(self, '_retry_urls'):
                    del self._retry_urls
                if hasattr(self, '_retry_scan_count'):
                    del self._retry_scan_count
                if hasattr(self, '_retry_found_channels'):
                    del self._retry_found_channels
                if hasattr(self, '_retry_loop_enabled'):
                    del self._retry_loop_enabled
                    
        except Exception as e:
            self.logger.error(f"处理重试扫描完成失败: {e}", exc_info=True)
            self.ui.main_window.statusBar().showMessage("重试扫描完成处理失败", 3000)
            self.ui.main_window.scan_btn.setText("完整扫描")

    def save_before_exit(self):
        """程序退出前保存所有配置"""
        try:
           
            # 保存窗口布局
            size = self.size()
            dividers = [
                *self.ui.main_window.main_splitter.sizes(),
                *self.ui.main_window.left_splitter.sizes(),
            ]
            self.config.save_window_layout(size.width(), size.height(), dividers)
            
            # 保存网络设置
            self.config.save_network_settings(
                self.ui.main_window.ip_range_input.text(),
                self.ui.main_window.timeout_input.value(),
                self.ui.main_window.thread_count_input.value(),
                self.ui.main_window.user_agent_input.text(),
                self.ui.main_window.referer_input.text()
            )
            
            # 保存语言设置
            if hasattr(self, 'language_manager'):
                self.config.save_language_settings(self.language_manager.current_language)
                
            self.logger.info("程序退出前配置已保存")
        except Exception as e:
            self.logger.error(f"保存退出配置失败: {e}")

from PyQt6 import QtWidgets, QtCore, QtGui
from about_dialog import AboutDialog  # 引入版本号

class LoadingScreen(QtWidgets.QWidget):
    def __init__(self, main_window=None):
        super().__init__()
        self.main_window = main_window
        self.current_step = 0
        self.steps = [
            "正在初始化应用程序...",
            "加载配置文件...",
            "初始化语言管理器...",
            "构建用户界面...",
            "初始化频道模型...",
            "加载频道映射规则...",
            "初始化扫描控制器...",
            "初始化播放器控制器...",
            "连接信号和槽...",
            "加载用户设置...",
            "准备就绪..."
        ]

        # 设置窗口大小和位置 - 更大气现代的尺寸
        self.setFixedSize(700, 450)
        self.setWindowFlags(
            QtCore.Qt.WindowType.FramelessWindowHint |
            QtCore.Qt.WindowType.WindowStaysOnTopHint
        )
        
        # 居中显示
        screen = QtWidgets.QApplication.primaryScreen()
        screen_geometry = screen.availableGeometry()
        x = (screen_geometry.width() - self.width()) // 2
        y = (screen_geometry.height() - self.height()) // 2
        self.move(x, y)

        # 设置现代化渐变背景 - 使用Qt支持的CSS属性
        self.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #0a192f, stop:0.3 #112240, stop:0.6 #1a365d, stop:1 #2d4a7c);
                border: 3px solid qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4cc9f0, stop:0.5 #4361ee, stop:1 #3a0ca3);
                border-radius: 20px;
            }
        """)

        # 主布局 - 更优雅的间距
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(50, 50, 50, 40)
        main_layout.setSpacing(30)

        # 应用程序标题区域 - 现代化设计
        title_layout = QtWidgets.QVBoxLayout()
        title_layout.setSpacing(10)
        
        # 主标题 - 添加发光效果
        self.title = QtWidgets.QLabel("IPTV Scanner Editor Pro")
        self.title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.title.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 36px;
                font-weight: 900;
                background: transparent;
                padding: 12px;
                letter-spacing: 1.5px;
                font-family: 'Microsoft YaHei', 'Segoe UI', sans-serif;
            }
        """)
        title_layout.addWidget(self.title)
        
        # 副标题 - 添加渐变效果
        self.subtitle = QtWidgets.QLabel("Professional Scanning & Editing Tool")
        self.subtitle.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.subtitle.setStyleSheet("""
            QLabel {
                color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4cc9f0, stop:0.5 #4361ee, stop:1 #3a0ca3);
                font-size: 18px;
                font-weight: 600;
                background: transparent;
                padding: 6px;
                letter-spacing: 0.8px;
                opacity: 0.95;
                font-family: 'Microsoft YaHei', 'Segoe UI', sans-serif;
            }
        """)
        title_layout.addWidget(self.subtitle)
        
        main_layout.addLayout(title_layout)

        # 状态文本区域 - 现代化卡片设计
        self.status_text = QtWidgets.QLabel(self.steps[0])
        self.status_text.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.status_text.setStyleSheet("""
            QLabel {
                color: #e2f3f5;
                font-size: 18px;
                font-weight: 500;
                background: rgba(30, 58, 138, 0.4);
                padding: 20px 30px;
                border: 2px solid rgba(76, 201, 240, 0.5);
                border-radius: 15px;
                margin: 15px 0px;
                min-height: 30px;
                font-family: 'Microsoft YaHei', 'Segoe UI', sans-serif;
            }
        """)
        main_layout.addWidget(self.status_text)

        # 进度条区域
        progress_container = QtWidgets.QWidget()
        progress_layout = QtWidgets.QVBoxLayout(progress_container)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        progress_layout.setSpacing(20)

        # 进度条 - 现代化风格
        self.progress = QtWidgets.QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setStyleSheet("""
            QProgressBar {
                border: 4px solid rgba(76, 201, 240, 0.4);
                border-radius: 18px;
                height: 28px;
                background: rgba(10, 25, 47, 0.9);
                padding: 3px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4cc9f0, stop:0.4 #4361ee, stop:0.7 #7209b7, stop:1 #3a0ca3);
                border-radius: 14px;
                border: 1px solid rgba(255, 255, 255, 0.4);
            }
        """)
        progress_layout.addWidget(self.progress)

        # 进度信息 - 现代化设计
        progress_info_layout = QtWidgets.QHBoxLayout()
        progress_info_layout.setContentsMargins(0, 8, 0, 0)
        
        self.progress_percent = QtWidgets.QLabel("0%")
        self.progress_percent.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.progress_percent.setStyleSheet("""
            QLabel {
                color: #4cc9f0;
                font-size: 24px;
                font-weight: bold;
                background: transparent;
                font-family: 'Microsoft YaHei', 'Segoe UI', sans-serif;
            }
        """)
        progress_info_layout.addWidget(self.progress_percent)
        
        main_layout.addWidget(progress_container)

        # 底部信息区域 - 现代化设计
        footer_layout = QtWidgets.QHBoxLayout()
        
        # 左侧：加载提示
        self.loading_hint = QtWidgets.QLabel("正在加载，请稍候...")
        self.loading_hint.setStyleSheet("""
            QLabel {
                color: #90e0ef;
                font-size: 14px;
                background: transparent;
                padding: 6px 12px;
                opacity: 0.9;
                font-family: 'Microsoft YaHei', 'Segoe UI', sans-serif;
            }
        """)
        footer_layout.addWidget(self.loading_hint)
        
        footer_layout.addStretch()
        
        # 右侧：版本号
        self.version = QtWidgets.QLabel(f"Version {AboutDialog.CURRENT_VERSION}")
        self.version.setStyleSheet("""
            QLabel {
                color: #a8dadc;
                font-size: 14px;
                font-weight: 600;
                background: rgba(30, 58, 138, 0.5);
                padding: 8px 16px;
                border-radius: 8px;
                border: 1px solid rgba(76, 201, 240, 0.3);
                font-family: 'Microsoft YaHei', 'Segoe UI', sans-serif;
            }
        """)
        footer_layout.addWidget(self.version)
        
        main_layout.addLayout(footer_layout)

        # 设置加载屏幕的窗口标题
        self.setWindowTitle(f"IPTV Scanner Editor Pro v{AboutDialog.CURRENT_VERSION}")

        # 初始化进度条同步定时器
        self.progress_timer = QtCore.QTimer()
        self.progress_timer.timeout.connect(self._update_progress_sync)
        self.progress_timer.start(40)  # 每40ms更新一次进度，更流畅
        
        # 启动时间记录
        self.start_time = time.time()
        self.step_start_time = time.time()
        self.current_step_duration = random.uniform(0.12, 0.25)  # 优化时间间隔
        self.current_progress = 0
        self.target_progress = 0
        self.animation_completed = False
        
        # 添加淡入动画
        self.opacity_effect = QtWidgets.QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.opacity_animation = QtCore.QPropertyAnimation(self.opacity_effect, b"opacity")
        self.opacity_animation.setDuration(400)
        self.opacity_animation.setStartValue(0)
        self.opacity_animation.setEndValue(1)
        self.opacity_animation.setEasingCurve(QtCore.QEasingCurve.Type.OutCubic)
        self.opacity_animation.start()

    def _update_progress_sync(self):
        """同步更新进度条和状态文本"""
        current_time = time.time()
        elapsed_in_step = current_time - self.step_start_time
        
        # 检查是否需要进入下一步
        if elapsed_in_step >= self.current_step_duration and self.current_step < len(self.steps):
            # 记录当前步骤完成信息
            step_name = self.steps[self.current_step]
            global_logger.info(f"[启动动画] 步骤 {self.current_step + 1}/{len(self.steps)} 完成: '{step_name}' - 用时: {elapsed_in_step:.2f}秒")
            
            # 进入下一步
            self.current_step += 1
            if self.current_step < len(self.steps):
                # 更新状态文本
                step_name = self.steps[self.current_step]
                self.status_text.setText(step_name)
                # 重置步骤计时器
                self.step_start_time = current_time
                self.current_step_duration = random.uniform(0.1, 0.3)  # 进一步缩短延迟时间
                # 计算目标进度
                self.target_progress = int((self.current_step / len(self.steps)) * 100)
                
                global_logger.info(f"[启动动画] 开始步骤 {self.current_step + 1}/{len(self.steps)}: '{step_name}' - 目标进度: {self.target_progress}% - 预计用时: {self.current_step_duration:.2f}秒")
            else:
                # 最后一步，直接到100%
                self.target_progress = 100
                global_logger.info(f"[启动动画] 所有步骤完成，目标进度设为100%")
        
        # 立即更新进度条到目标进度，确保与文字提示同步
        if self.current_progress != self.target_progress:
            self.current_progress = self.target_progress
            self.progress.setValue(self.current_progress)
            self.progress_percent.setText(f"{self.current_progress}%")
            
            # 如果达到100%，触发UI初始化
            if self.current_progress >= 100:
                total_time = time.time() - self.start_time
                global_logger.info(f"[启动动画] 进度条达到100% - 总用时: {total_time:.2f}秒")
                self.progress_timer.stop()
                self.animation_completed = True
                global_logger.info(f"[启动动画] 进度条定时器已停止，立即显示主窗口...")
                # 立即显示主窗口，不再延迟
                QtCore.QTimer.singleShot(0, self.start_ui_init)
        
        # 强制UI更新
        QtWidgets.QApplication.processEvents()

    def update_progress(self, value, status_text=None):
        """更新进度条和状态文本"""
        self.progress.setValue(value)
        self.progress_percent.setText(f"{value}%")
        
        if status_text:
            self.status_text.setText(status_text)

    @QtCore.pyqtSlot()
    def start_ui_init(self):
        """进度条完成后触发UI初始化"""
        if self.animation_completed:
            global_logger.info(f"[启动动画] 启动动画窗口即将关闭，准备创建并显示主窗口")
            self.close()
            global_logger.info(f"[启动动画] 启动动画窗口已关闭")
            
            # 在启动动画完成后创建主窗口，避免窗口闪动
            try:
                window = MainWindow()
                window.show()
                global_logger.info(f"[启动动画] 主窗口已创建并显示")
                
                # 设置应用程序的主窗口引用
                QtWidgets.QApplication.instance().main_window = window
            except Exception as e:
                global_logger.error(f"[启动动画] 创建主窗口失败: {e}")
                QtWidgets.QApplication.instance().quit()

def main():
    # 移除弃用的 asyncio 设置，使用默认事件循环策略
    # 注意：Python 3.8+ 在 Windows 上默认使用 ProactorEventLoop
    # 如果需要兼容旧代码，可以保留但会显示弃用警告
    
    app = QtWidgets.QApplication(sys.argv)
    
    # 设置应用程序字体，避免Fixedsys字体缺失警告
    font_family = "Microsoft YaHei"
    font = QtGui.QFont(font_family)
    font.setPointSize(9)
    app.setFont(font)
    app.setStyleSheet(f"""
        QWidget {{
            font-family: "{font_family}";
            font-size: 9pt;
        }}
    """)

    # 第一步：立即显示启动动画
    loading_screen = LoadingScreen()
    loading_screen.show()
    app.processEvents()  # 强制立即显示启动动画
    
    # 第二步：启动动画完全控制初始化过程
    # 启动动画会通过定时器逐步更新，完成后自动创建并显示主窗口
    # 将主窗口创建延迟到启动动画完成后，避免窗口闪动
    loading_screen.main_window = None  # 先设置为None，稍后创建
    
    # 第三步：启动动画完全控制初始化过程
    # 启动动画会通过定时器逐步更新，完成后自动创建并显示主窗口

    def cleanup():
        if hasattr(app, 'main_window'):
            app.main_window.save_before_exit()
    app.aboutToQuit.connect(cleanup)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
