"""
主窗口模块 - 负责主窗口UI和事件处理
精简版本，只包含核心功能
"""

import os
from PyQt6 import QtWidgets, QtCore, QtGui

# 导入自定义模块
from models.channel_model import ChannelListModel
from ui.builder import UIBuilder
from services.scanner_service import ScannerController
from ui.styles import AppStyles
from services.player_service import PlayerController
from services.list_service import ListManager
from services.url_parser_service import URLRangeParser
from ui.optimizer import get_ui_optimizer
from utils.error_handler import init_global_error_handler
from utils.resource_cleaner import get_resource_cleaner, register_cleanup, cleanup_all
from utils.general_utils import safe_connect, safe_connect_button


class MainWindow(QtWidgets.QMainWindow):
    """主窗口类，继承自QMainWindow"""
    
    def __init__(self, application=None):
        super().__init__()
        
        # 保存应用程序引用
        self.application = application
        if application:
            self.config = application.config
            self.logger = application.logger
            self.language_manager = application.language_manager
        else:
            from core.config_manager import ConfigManager
            from core.log_manager import global_logger
            from core.language_manager import LanguageManager
            self.config = ConfigManager()
            self.logger = global_logger
            self.language_manager = LanguageManager()
            self.language_manager.load_available_languages()
            language_code = self.config.load_language_settings()
            self.language_manager.set_language(language_code)
        
        # 在UI构建前完全隐藏窗口，防止任何闪动
        self.hide()
        
        # 创建UI构建器实例
        self.ui = UIBuilder(self)
        self.ui.build_ui()
        
        # 立即更新UI文本到当前语言
        if hasattr(self, 'language_manager'):
            self.language_manager.update_ui_texts(self)
        
        # 设置窗口图标
        if os.path.exists('logo.ico'):
            self.setWindowIcon(QtGui.QIcon('logo.ico'))

        # 初始化主窗口的后续设置
        self._init_main_window()
        self._timers = []
        QtCore.QTimer.singleShot(0, self._init_timers)
        
        # 延迟显示窗口，确保UI完全初始化后再显示
        QtCore.QTimer.singleShot(100, self.show)
    
    def _init_timers(self):
        """在主线程初始化所有定时器"""
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
        self.model.setParent(self)
        
        self.init_controllers()
        
        self.ui_optimizer = get_ui_optimizer()
        self.error_handler = init_global_error_handler(self)
        
        self.ui_optimizer.optimize_table_view(self.ui.main_window.channel_list)
        
        self._load_config()
        self._connect_signals()
        self._register_cleanup_handlers()
    
    def init_controllers(self):
        """初始化所有控制器"""
        if not hasattr(self, 'scanner') or self.scanner is None:
            self.scanner = ScannerController(self.model, self)
        self.player_controller = PlayerController(self.ui.main_window.player, self.model)
        self.list_manager = ListManager(self.model)
        
        self._connect_progress_signals()
        self._on_play_state_changed(self.player_controller.is_playing)
    
    def _connect_progress_signals(self):
        """连接进度条更新信号"""
        if not hasattr(self.ui.main_window, 'progress_indicator'):
            return
            
        if self.ui.main_window.progress_indicator is None:
            return
            
        self.ui.main_window.progress_indicator.setRange(0, 100)
        self.ui.main_window.progress_indicator.setValue(0)
        self.ui.main_window.progress_indicator.setTextVisible(True)
        self.ui.main_window.progress_indicator.setFormat("%p%")
        self.ui.main_window.progress_indicator.hide()
        
        self.progress_timer = QtCore.QTimer()
        self.progress_timer.timeout.connect(self._update_progress_from_stats)
        self.progress_timer.start(500)
        
        self.scanner.scan_completed.connect(self._on_scan_completed_for_progress)
    
    def _update_progress_from_stats(self):
        """从统计信息更新进度条"""
        try:
            if hasattr(self.scanner, 'stats'):
                stats = self.scanner.stats
                total = stats.get('total', 0)
                valid = stats.get('valid', 0)
                invalid = stats.get('invalid', 0)
                
                current = valid + invalid
                
                if total <= 0:
                    progress_value = 0
                else:
                    progress_value = int(current / total * 100)
                    progress_value = max(0, min(100, progress_value))
                
                if not self.ui.main_window.progress_indicator.isVisible() and total > 0:
                    self.ui.main_window.progress_indicator.show()
                
                old_value = self.ui.main_window.progress_indicator.value()
                if old_value != progress_value:
                    self.ui.main_window.progress_indicator.setValue(progress_value)
                    
                    if progress_value >= 100 and old_value < 100:
                        self._set_scan_button_text('full_scan', '完整扫描')
                        self._set_append_scan_button_text('append_scan', '追加扫描')
                        self._hide_progress_indicator()
                        
        except AttributeError as e:
            self.logger.debug(f"进度条更新失败: {e}")
        except Exception as e:
            self.logger.warning(f"进度条更新时发生意外错误: {e}")
            
    def _on_scan_completed_for_progress(self):
        """处理扫描完成，隐藏进度条"""
        try:
            self._hide_progress_indicator()
        except AttributeError as e:
            self.logger.debug(f"隐藏进度条失败: {e}")
        except Exception as e:
            self.logger.warning(f"隐藏进度条时发生意外错误: {e}")

    def _hide_progress_indicator(self):
        """统一隐藏进度条的方法"""
        if hasattr(self.ui.main_window, 'progress_indicator'):
            self.ui.main_window.progress_indicator.hide()
            self.ui.main_window.progress_indicator.setValue(0)
    
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
            
            # 加载重试设置
            if 'enable_retry' in settings:
                self.ui.main_window.enable_retry_checkbox.setChecked(settings['enable_retry'])
            if 'loop_scan' in settings:
                self.ui.main_window.loop_scan_checkbox.setChecked(settings['loop_scan'])
            
            language_code = self.config.load_language_settings()
            
            if hasattr(self, 'language_manager'):
                self.language_manager.set_language(language_code)
                    
        except Exception as e:
            self.logger.error(f"加载配置失败: {e}")
            self.ui.main_window.timeout_input.setValue(10)
            self.ui.main_window.thread_count_input.setValue(5)
    
    def _connect_signals(self):
        """连接所有信号和槽"""
        self.ui.main_window.channel_list.selectionModel().selectionChanged.connect(
            self._on_channel_selected
        )
        
        safe_connect_button(self.ui.main_window.scan_btn, self._on_scan_clicked)
        safe_connect_button(self.ui.main_window.append_scan_btn, self._on_append_scan_clicked)
                
        self.ui.main_window.volume_slider.valueChanged.connect(
            self._on_volume_changed)
        safe_connect_button(self.ui.main_window.pause_btn, self._on_pause_clicked)
        safe_connect_button(self.ui.main_window.stop_btn, self._on_stop_clicked)
        
        self.player_controller.play_state_changed.connect(
            self._on_play_state_changed)
        
        self.ui.main_window.channel_list.doubleClicked.connect(self._play_selected_channel)
        
        safe_connect_button(self.ui.main_window.btn_validate, self._on_validate_clicked)
        safe_connect_button(self.ui.main_window.btn_hide_invalid, self._on_hide_invalid_clicked)
        safe_connect_button(self.ui.main_window.generate_btn, self._on_generate_clicked)
        
        self.scanner.channel_found.connect(self._on_channel_found)
        self.scanner.scan_completed.connect(self._on_scan_completed)
        
        self.scanner.stats_updated.connect(
            self._update_stats_display,
            QtCore.Qt.ConnectionType.QueuedConnection
        )
    
    def _on_scan_clicked(self):
        """处理扫描按钮点击事件"""
        if self.scanner.is_scanning():
            self.scanner.stop_scan()
            self._set_scan_button_text('full_scan', '完整扫描')
            self._set_append_scan_button_text('append_scan', '追加扫描')
        else:
            url = self.ui.main_window.ip_range_input.text()
            if not url.strip():
                self.logger.warning("请输入扫描地址")
                self.ui.main_window.statusBar().showMessage("请输入扫描地址", 3000)
                return
                
            QtCore.QTimer.singleShot(0, lambda: self._start_scan_delayed(url, clear_list=True))
    
    def _on_append_scan_clicked(self):
        """处理追加扫描按钮点击事件"""
        if self.scanner.is_scanning():
            self.scanner.stop_scan()
            self._set_scan_button_text('full_scan', '完整扫描')
            self._set_append_scan_button_text('append_scan', '追加扫描')
        else:
            url = self.ui.main_window.ip_range_input.text()
            if not url.strip():
                self.logger.warning("请输入扫描地址")
                self.ui.main_window.statusBar().showMessage("请输入扫描地址", 3000)
                return
                
            QtCore.QTimer.singleShot(0, lambda: self._start_scan_delayed(url, clear_list=False))
            
    def _start_scan_delayed(self, url, clear_list=True):
        """延迟启动扫描，避免UI阻塞"""
        if clear_list:
            self.model.clear()
            self.logger.info("开始完整扫描，清空现有列表")
        else:
            self.logger.info("开始追加扫描，保留现有列表")
            
        timeout = self.ui.main_window.timeout_input.value()
        threads = self.ui.main_window.thread_count_input.value()
        
        self.scanner.start_scan(url, threads, timeout)
        
        if clear_list:
            self._set_scan_button_text('stop_scan', '停止扫描')
        else:
            self._set_append_scan_button_text('stop_scan', '停止扫描')
        
    def _set_button_text(self, button, translation_key, default_text):
        """通用按钮文本设置函数"""
        if hasattr(self, 'language_manager') and self.language_manager:
            button.setText(self.language_manager.tr(translation_key, default_text))
        else:
            button.setText(default_text)

    def _set_scan_button_text(self, translation_key, default_text):
        """设置扫描按钮文本"""
        self._set_button_text(self.ui.main_window.scan_btn, translation_key, default_text)
    
    def _set_append_scan_button_text(self, translation_key, default_text):
        """设置追加扫描按钮文本"""
        self._set_button_text(self.ui.main_window.append_scan_btn, translation_key, default_text)

    def _on_volume_changed(self, value):
        """处理音量滑块变化"""
        self.player_controller.set_volume(value)

    def _on_pause_clicked(self):
        """处理暂停/播放按钮点击"""
        if not self.player_controller.is_playing:
            selected = self.ui.main_window.channel_list.selectedIndexes()
            if not selected:
                self.logger.warning("请先选择一个频道")
                self.ui.main_window.statusBar().showMessage("请先选择一个频道", 3000)
                self._set_pause_button_text(False)
                return
                
            self._play_selected_channel(selected[0])
        else:
            self.player_controller.toggle_pause()
            self._set_pause_button_text(not self.player_controller.is_playing)

    def _on_stop_clicked(self):
        """处理停止按钮点击"""
        self.player_controller.stop()
        self._set_pause_button_text(False)
        
    def _set_pause_button_text(self, is_playing):
        """设置暂停/播放按钮文本"""
        if is_playing:
            self._set_button_text(self.ui.main_window.pause_btn, 'pause', '暂停')
        else:
            self._set_button_text(self.ui.main_window.pause_btn, 'play', '播放')

    def _on_play_state_changed(self, is_playing):
        """处理播放状态变化"""
        self.logger.info(f"播放状态变化: is_playing={is_playing}")
        
        from ui.optimizer import batch_update
        
        def update_ui_state():
            self.ui.main_window.stop_btn.setEnabled(is_playing)
            self.ui.main_window.stop_btn.setStyleSheet(
                AppStyles.button_style(active=is_playing)
            )
            
            self._set_pause_button_text(is_playing)
            
            if hasattr(self.ui.main_window, 'pause_btn'):
                self.ui.main_window.pause_btn.repaint()
            if hasattr(self.ui.main_window, 'stop_btn'):
                self.ui.main_window.stop_btn.repaint()
                
            self.logger.info(f"停止按钮启用状态: {self.ui.main_window.stop_btn.isEnabled()}")
        
        batch_update(update_ui_state)

    def _on_validate_clicked(self):
        """处理有效性检测按钮点击事件"""
        if not self.ui.main_window.model.rowCount():
            self.logger.warning("请先加载列表")
            return
            
        if not hasattr(self.scanner, 'is_validating') or not self.scanner.is_validating:
            timeout = self.ui.main_window.timeout_input.value()
            threads = self.ui.main_window.thread_count_input.value()
            user_agent = self.ui.main_window.user_agent_input.text()
            referer = self.ui.main_window.referer_input.text()
            self.scanner.start_validation(
                self.ui.main_window.model,
                threads,
                timeout,
                user_agent,
                referer
            )
            self.ui.main_window.btn_validate.setText("停止检测")
            self.ui.main_window.btn_hide_invalid.setEnabled(True)
            self.ui.main_window.btn_hide_invalid.setStyleSheet(
                AppStyles.button_style(active=True)
            )
            
            self.scanner.channel_validated.connect(self._on_channel_validated)
        else:
            self.scanner.stop_validation()
            self.ui.main_window.btn_validate.setText("检测有效性")
            
    def _on_channel_selected(self):
        """处理频道选择事件"""
        selected = self.ui.main_window.channel_list.selectedIndexes()
        if not selected:
            return
            
        row = selected[0].row()
        self.current_channel_index = row

    def _on_channel_validated(self, index, valid, latency, resolution):
        """处理频道验证结果"""
        channel_info = {
            'valid': valid,
            'latency': latency,
            'resolution': resolution,
            'status': '有效' if valid else '无效'
        }
        
        self.ui.main_window.model.update_channel(index, channel_info)

    def _on_generate_clicked(self):
        """处理直接生成列表按钮点击事件"""
        url = self.ui.main_window.ip_range_input.text()
        if not url.strip():
            self.logger.warning("请输入生成地址")
            self.ui.main_window.statusBar().showMessage("请输入生成地址", 3000)
            return
            
        self.model.clear()
        
        url_parser = URLRangeParser()
        url_generator = url_parser.parse_url(url)
        
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

    def _open_list(self):
        """打开列表文件"""
        try:
            success, error_msg = self.list_manager.open_list(self)
                
            if success:
                self.ui.main_window.btn_hide_invalid.setEnabled(False)
                self.ui.main_window.btn_validate.setEnabled(True)
                self.ui.main_window.statusBar().showMessage("列表加载成功", 3000)
                
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

    def _play_selected_channel(self, index):
        """播放选中的频道"""
        if not index.isValid():
            return
            
        channel = self.ui.main_window.model.get_channel(index.row())
        if not channel or not channel.get('url'):
            return
            
        if not hasattr(self, 'player_controller') or not self.player_controller:
            from services.player_service import PlayerController
            self.player_controller = PlayerController(
                self.ui.main_window.player,
                self.model
            )
            
        self.current_channel_index = index.row()
            
        if self.player_controller.play_channel(channel, self.current_channel_index):
            if hasattr(self, 'language_manager') and self.language_manager:
                self.ui.main_window.pause_btn.setText(
                    self.language_manager.tr('pause', 'Pause')
                )
            else:
                self.ui.main_window.pause_btn.setText("暂停")
            self.current_channel = channel

    def save_before_exit(self):
        """退出前保存配置"""
        try:
            if hasattr(self, 'config'):
                self.config.save_network_settings(
                    url=self.ui.main_window.ip_range_input.text(),
                    timeout=self.ui.main_window.timeout_input.value(),
                    threads=self.ui.main_window.thread_count_input.value(),
                    user_agent=self.ui.main_window.user_agent_input.text(),
                    referer=self.ui.main_window.referer_input.text(),
                    enable_retry=self.ui.main_window.enable_retry_checkbox.isChecked(),
                    loop_scan=self.ui.main_window.loop_scan_checkbox.isChecked()
                )
                self.logger.info("配置已保存")
        except Exception as e:
            self.logger.error(f"保存配置失败: {e}")

    @QtCore.pyqtSlot(dict)
    def _on_channel_found(self, channel_info):
        """处理发现有效频道事件"""
        self.ui.main_window.model.add_channel(channel_info)
        
        if hasattr(self.ui.main_window, 'channel_list'):
            header = self.ui.main_window.channel_list.horizontalHeader()
            QtCore.QTimer.singleShot(0, lambda: header.resizeSections(QtWidgets.QHeaderView.ResizeMode.ResizeToContents))

    def _on_scan_completed(self):
        """处理扫描完成事件"""
        self._set_scan_button_text('full_scan', '完整扫描')
        self._set_append_scan_button_text('append_scan', '追加扫描')
        self.ui.main_window.btn_validate.setText("检测有效性")
        self.logger.info("扫描完成")
        
        self.ui.main_window.btn_smart_sort.setEnabled(True)
        self.ui.main_window.btn_smart_sort.setStyleSheet(
            AppStyles.button_style(active=True)
        )
        
        if hasattr(self.ui.main_window, 'channel_list'):
            header = self.ui.main_window.channel_list.horizontalHeader()
            header.resizeSections(QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        
        self.logger.info("扫描完成")

    @QtCore.pyqtSlot(dict)
    def _update_stats_display(self, stats_data):
        """更新统计信息显示"""
        try:
            if not hasattr(self.ui, 'main_window') or not self.ui.main_window:
                self.logger.error("UI主窗口对象不存在")
                return
                
            if not hasattr(self.ui.main_window, 'stats_label') or not self.ui.main_window.stats_label:
                self.logger.error("状态栏统计标签不存在")
                return
            
            import time
            stats = stats_data.get('stats', stats_data)
            elapsed = time.strftime("%H:%M:%S", time.gmtime(stats.get('elapsed', 0)))
            
            if hasattr(self, 'language_manager') and self.language_manager:
                total_text = self.language_manager.tr('total_channels', 'Total Channels')
                valid_text = self.language_manager.tr('valid', 'Valid')
                invalid_text = self.language_manager.tr('invalid', 'Invalid')
                time_text = self.language_manager.tr('time_elapsed', 'Time Elapsed')
                
                stats_text = (
                    f"{total_text}: {stats.get('total', 0)} | "
                    f"{valid_text}: {stats.get('valid', 0)} | "
                    f"{invalid_text}: {stats.get('invalid', 0)} | "
                    f"{time_text}: {elapsed}"
                )
                self.ui.main_window.stats_label.setText(stats_text)
            else:
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
            from ui.dialogs.about_dialog import AboutDialog
            
            dialog = AboutDialog(self)
            dialog.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)
            
            def show_dialog():
                try:
                    dialog.show()
                    if hasattr(dialog, 'update_ui_texts'):
                        dialog.update_ui_texts()
                except Exception as e:
                    self.logger.error(f"显示对话框出错: {e}")
            
            QtCore.QTimer.singleShot(0, show_dialog)
            
        except ImportError as e:
            self.logger.error(f"导入AboutDialog失败: {e}")
            from utils.error_handler import show_error
            show_error("错误", "无法加载关于对话框模块", parent=self)
        except Exception as e:
            self.logger.error(f"显示关于对话框失败: {e}")
            from utils.error_handler import show_error
            show_error("错误", f"无法显示关于对话框: {str(e)}", parent=self)
            
    def _on_mapping_clicked(self):
        """处理映射管理按钮点击事件"""
        try:
            from ui.dialogs.mapping_manager_dialog import MappingManagerDialog
            
            dialog = MappingManagerDialog(self)
            dialog.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)
            
            def show_dialog():
                try:
                    dialog.exec()
                except Exception as e:
                    self.logger.error(f"显示映射管理器出错: {e}")
            
            QtCore.QTimer.singleShot(0, show_dialog)
            
        except ImportError as e:
            self.logger.error(f"导入MappingManagerDialog失败: {e}")
            from utils.error_handler import show_error
            show_error("错误", "无法加载映射管理器模块", parent=self)
        except Exception as e:
            self.logger.error(f"显示映射管理器失败: {e}")
            from utils.error_handler import show_error
            show_error("错误", f"无法显示映射管理器: {str(e)}", parent=self)

    def _register_cleanup_handlers(self):
        """注册资源清理处理器"""
        self.logger.info("注册资源清理处理器...")
        
        # 收集所有处理器名称用于整合日志
        handler_names = []
        
        register_cleanup(self._stop_all_timers, "stop_all_timers")
        handler_names.append("stop_all_timers")
        
        if hasattr(self, 'progress_timer'):
            def stop_progress_timer():
                if self.progress_timer.isActive():
                    self.progress_timer.stop()
            register_cleanup(stop_progress_timer, "stop_progress_timer")
            handler_names.append("stop_progress_timer")
        
        if hasattr(self, 'scanner'):
            register_cleanup(self.scanner.stop_scan, "scanner_stop_scan")
            handler_names.append("scanner_stop_scan")
        
        if hasattr(self, 'player_controller'):
            register_cleanup(self.player_controller.release, "player_release")
            handler_names.append("player_release")
        
        from services.validator_service import StreamValidator
        register_cleanup(StreamValidator.terminate_all, "validator_terminate_all")
        handler_names.append("validator_terminate_all")
        
        from utils.memory_manager import optimize_memory
        register_cleanup(optimize_memory, "optimize_memory")
        handler_names.append("optimize_memory")
        
        # 整合日志：显示所有注册的处理器
        self.logger.info(f"已注册 {len(handler_names)} 个资源清理处理器: {', '.join(handler_names)}")
