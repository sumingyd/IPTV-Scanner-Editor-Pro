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
from error_handler import init_global_error_handler, show_error, show_warning, show_info, show_confirm
from resource_cleaner import get_resource_cleaner, register_cleanup, cleanup_all

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        # 在UI构建前完全隐藏窗口，防止任何闪动
        self.hide()
        self.config = ConfigManager()
        self.logger = global_logger
        self.language_manager = LanguageManager()
        self.language_manager.load_available_languages()
        language_code = self.config.load_language_settings()
        if self.language_manager.set_language(language_code):
            pass
        
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
        self._init_main_window()
        self._timers = []
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
        
        # 注册资源清理处理器
        self._register_cleanup_handlers()

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
        """连接进度条更新信号 - 使用简单的定时器方案"""
        
        # 检查进度条对象是否存在
        if not hasattr(self.ui.main_window, 'progress_indicator'):
            return
            
        if self.ui.main_window.progress_indicator is None:
            return
            
        # 初始化进度条
        self.ui.main_window.progress_indicator.setRange(0, 100)
        self.ui.main_window.progress_indicator.setValue(0)
        self.ui.main_window.progress_indicator.setTextVisible(True)
        self.ui.main_window.progress_indicator.setFormat("%p%")
        self.ui.main_window.progress_indicator.hide()
        
        # 创建定时器来定期更新进度条
        self.progress_timer = QtCore.QTimer()
        self.progress_timer.timeout.connect(self._update_progress_from_stats)
        self.progress_timer.start(500)  # 每500ms更新一次
        
        # 连接扫描完成信号
        self.scanner.scan_completed.connect(self._on_scan_completed_for_progress)

    def _update_progress_from_stats(self):
        """从统计信息更新进度条"""
        try:
            # 获取统计信息
            if hasattr(self.scanner, 'stats'):
                stats = self.scanner.stats
                total = stats.get('total', 0)
                valid = stats.get('valid', 0)
                invalid = stats.get('invalid', 0)
                
                current = valid + invalid
                
                # 计算百分比
                if total <= 0:
                    progress_value = 0
                else:
                    progress_value = int(current / total * 100)
                    progress_value = max(0, min(100, progress_value))
                
                # 显示进度条
                if not self.ui.main_window.progress_indicator.isVisible() and total > 0:
                    self.ui.main_window.progress_indicator.show()
                
                # 更新进度值
                old_value = self.ui.main_window.progress_indicator.value()
                if old_value != progress_value:
                    self.ui.main_window.progress_indicator.setValue(progress_value)
                    
                    # 关键修复：当进度达到100%时，自动恢复按钮文本
                    if progress_value >= 100 and old_value < 100:
                        # 恢复两个扫描按钮的文本
                        self._set_scan_button_text('full_scan', '完整扫描')
                        self._set_append_scan_button_text('append_scan', '追加扫描')
                        # 隐藏进度条
                        self.ui.main_window.progress_indicator.hide()
                        self.ui.main_window.progress_indicator.setValue(0)
                    
        except Exception as e:
            pass
            
    def _on_scan_completed_for_progress(self):
        """处理扫描完成，隐藏进度条"""
        try:
            # 扫描完成后隐藏进度条
            self.ui.main_window.progress_indicator.hide()
            self.ui.main_window.progress_indicator.setValue(0)
        except Exception as e:
            pass


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
        
        # 连接追加扫描按钮
        try:
            self.ui.main_window.append_scan_btn.clicked.disconnect()
        except:
            pass
        self.ui.main_window.append_scan_btn.clicked.connect(self._on_append_scan_clicked)
                
                
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
        
        # 频道发现信号
        self.scanner.channel_found.connect(self._on_channel_found)
        
        # 扫描完成信号
        self.scanner.scan_completed.connect(self._on_scan_completed)
        
        # 统计信息更新信号 - 使用QueuedConnection确保跨线程安全
        self.scanner.stats_updated.connect(self._update_stats_display, QtCore.Qt.ConnectionType.QueuedConnection)

    def _on_scan_clicked(self):
        """处理扫描按钮点击事件 - 使用QTimer避免UI阻塞"""
        if self.scanner.is_scanning():
            # 停止扫描 - 立即响应
            self.scanner.stop_scan()
            # 停止扫描后，两个按钮都应该恢复
            self._set_scan_button_text('full_scan', '完整扫描')
            self._set_append_scan_button_text('append_scan', '追加扫描')
        else:
            # 检查地址是否为空
            url = self.ui.main_window.ip_range_input.text()
            if not url.strip():
                self.logger.warning("请输入扫描地址")
                self.ui.main_window.statusBar().showMessage("请输入扫描地址", 3000)
                return
                
            # 使用QTimer延迟执行扫描，避免UI阻塞
            QtCore.QTimer.singleShot(0, lambda: self._start_scan_delayed(url, clear_list=True))
    
    def _on_append_scan_clicked(self):
        """处理追加扫描按钮点击事件"""
        if self.scanner.is_scanning():
            # 停止扫描 - 立即响应
            self.scanner.stop_scan()
            # 停止扫描后，两个按钮都应该恢复
            self._set_scan_button_text('full_scan', '完整扫描')
            self._set_append_scan_button_text('append_scan', '追加扫描')
        else:
            # 检查地址是否为空
            url = self.ui.main_window.ip_range_input.text()
            if not url.strip():
                self.logger.warning("请输入扫描地址")
                self.ui.main_window.statusBar().showMessage("请输入扫描地址", 3000)
                return
                
            # 使用QTimer延迟执行追加扫描，避免UI阻塞
            QtCore.QTimer.singleShot(0, lambda: self._start_scan_delayed(url, clear_list=False))
            
    def _start_scan_delayed(self, url, clear_list=True):
        """延迟启动扫描，避免UI阻塞"""
        # 根据参数决定是否清空列表
        if clear_list:
            self.model.clear()
            self.logger.info("开始完整扫描，清空现有列表")
        else:
            self.logger.info("开始追加扫描，保留现有列表")
            
        timeout = self.ui.main_window.timeout_input.value()
        threads = self.ui.main_window.thread_count_input.value()
        self.scanner.start_scan(url, threads, timeout)
        
        # 根据扫描类型设置按钮文本
        if clear_list:
            self._set_scan_button_text('stop_scan', '停止扫描')
        else:
            self._set_append_scan_button_text('stop_scan', '停止扫描')
        
    def _set_button_text(self, button, translation_key, default_text):
        """通用按钮文本设置函数（统一处理语言管理器）"""
        if hasattr(self, 'language_manager') and self.language_manager:
            button.setText(self.language_manager.tr(translation_key, default_text))
        else:
            button.setText(default_text)

    def _set_scan_button_text(self, translation_key, default_text):
        """设置扫描按钮文本（向后兼容）"""
        self._set_button_text(self.ui.main_window.scan_btn, translation_key, default_text)
    
    def _set_append_scan_button_text(self, translation_key, default_text):
        """设置追加扫描按钮文本（向后兼容）"""
        self._set_button_text(self.ui.main_window.append_scan_btn, translation_key, default_text)

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
        """设置暂停/播放按钮文本（使用通用函数）"""
        if is_playing:
            self._set_button_text(self.ui.main_window.pause_btn, 'pause', '暂停')
        else:
            self._set_button_text(self.ui.main_window.pause_btn, 'play', '播放')

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
        # 重置扫描按钮文本
        self._set_scan_button_text('full_scan', '完整扫描')
        self._set_append_scan_button_text('append_scan', '追加扫描')
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
        
        # 扫描完成后加载网络Logo
        self.logger.info("扫描完成，开始加载网络Logo")
        QtCore.QTimer.singleShot(100, self.ui._load_network_logos)
        
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
            # 使用统一的错误处理
            show_error("错误", "无法加载关于对话框模块", parent=self)
        except Exception as e:
            self.logger.error(f"显示关于对话框失败: {e}")
            # 使用统一的错误处理
            show_error("错误", f"无法显示关于对话框: {str(e)}", parent=self)
            
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
            # 使用统一的错误处理
            show_error("错误", "无法加载映射管理器模块", parent=self)
        except Exception as e:
            self.logger.error(f"显示映射管理器失败: {e}")
            # 使用统一的错误处理
            show_error("错误", f"无法显示映射管理器: {str(e)}", parent=self)
            
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
                
                # 恢复两个扫描按钮的文本
                self._set_scan_button_text('full_scan', '完整扫描')
                self._set_append_scan_button_text('append_scan', '追加扫描')
                
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
            # 恢复两个扫描按钮的文本
            self._set_scan_button_text('full_scan', '完整扫描')
            self._set_append_scan_button_text('append_scan', '追加扫描')

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

    def closeEvent(self, event):
        """重写窗口关闭事件，确保资源正确清理"""
        self._cleanup_resources()
        event.accept()

    def _cleanup_resources(self):
        """清理所有资源"""
        self.logger.info("开始清理程序资源...")
        
        # 使用全局资源清理器
        cleanup_all()
        
        self.logger.info("所有资源已清理")
    
    def _register_cleanup_handlers(self):
        """注册资源清理处理器"""
        self.logger.info("注册资源清理处理器...")
        
        # 注册定时器清理
        register_cleanup(self._stop_all_timers, "stop_all_timers")
        
        # 注册进度条定时器清理
        if hasattr(self, 'progress_timer'):
            def stop_progress_timer():
                if self.progress_timer.isActive():
                    self.progress_timer.stop()
            register_cleanup(stop_progress_timer, "stop_progress_timer")
        
        # 注册扫描器清理
        if hasattr(self, 'scanner'):
            register_cleanup(self.scanner.stop_scan, "scanner_stop_scan")
        
        # 注册播放器资源释放
        if hasattr(self, 'player_controller'):
            register_cleanup(self.player_controller.release, "player_release")
        
        # 注册验证器进程清理
        from validator import StreamValidator
        register_cleanup(StreamValidator.terminate_all, "validator_terminate_all")
        
        # 注册内存优化
        from memory_manager import optimize_memory
        register_cleanup(optimize_memory, "optimize_memory")
        
        self.logger.info(f"已注册 {len(get_resource_cleaner()._cleanup_handlers)} 个资源清理处理器")

def main():
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

    # 直接创建并显示主窗口，去掉启动动画
    try:
        window = MainWindow()
        window.show()
        app.main_window = window
    except Exception as e:
        global_logger.error(f"创建主窗口失败: {e}")
        QtWidgets.QApplication.instance().quit()

    def cleanup():
        if hasattr(app, 'main_window'):
            app.main_window.save_before_exit()
    app.aboutToQuit.connect(cleanup)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
