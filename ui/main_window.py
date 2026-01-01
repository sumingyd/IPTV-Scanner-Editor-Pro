"""
主窗口模块 - 负责主窗口UI和事件处理
精简版本，只包含核心功能
"""

import os
from PyQt6 import QtWidgets, QtCore, QtGui

# 导入自定义模块
from ui.builder import UIBuilder
from services.scanner_service import ScannerController
from ui.styles import AppStyles
from services.player_service import PlayerController
from services.list_service import ListManager
from services.url_parser_service import URLRangeParser
from ui.optimizer import get_ui_optimizer
from utils.error_handler import init_global_error_handler
from utils.resource_cleaner import register_cleanup
from utils.general_utils import safe_connect_button
from utils.progress_manager import init_progress_manager
from utils.config_notifier import register_config_observer
from utils.scan_state_manager import get_scan_state_manager, register_retry_task, RetryScanStateContext
from utils.logging_helper import (
    log_ui_info, log_ui_warning, log_ui_error, log_scan_info,
    log_scan_warning, log_config_error, log_config_info
)


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

        # 扫描状态管理器
        self.scan_state_manager = get_scan_state_manager()
        self.retry_id = 'main_retry'

        # 注册重试扫描任务
        register_retry_task(self.retry_id, self)

        # 在UI构建前完全隐藏窗口，防止任何闪动
        self.hide()

        # 创建UI构建器实例
        self.ui = UIBuilder(self)
        self.ui.build_ui()

        # 立即更新UI文本到当前语言
        if hasattr(self, 'language_manager'):
            self.language_manager.update_ui_texts(self)

        # 设置窗口图标
        if os.path.exists('resources/logo.ico'):
            self.setWindowIcon(QtGui.QIcon('resources/logo.ico'))

        # 初始化主窗口的后续设置
        self._init_main_window()
        self._timers = []
        QtCore.QTimer.singleShot(0, self._init_timers)

        # 延迟显示窗口，确保UI完全初始化后再显示
        QtCore.QTimer.singleShot(100, self.show)

        # 在窗口显示后延迟检查新版本
        QtCore.QTimer.singleShot(500, self._check_for_updates_async)

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
                        QtCore.QMetaObject.invokeMethod(
                            timer, "stop", QtCore.Qt.ConnectionType.QueuedConnection
                        )
            self._timers.clear()

    def _init_main_window(self):
        """初始化主窗口的后续设置"""
        self.model = self.ui.main_window.model
        self.model.setParent(self)

        # 初始化进度条管理器（必须在 init_controllers 之前）
        self.progress_manager = init_progress_manager(
            self.ui.main_window.progress_indicator,
            self.ui.main_window.statusBar()
        )

        self.init_controllers()

        self.ui_optimizer = get_ui_optimizer()
        self.error_handler = init_global_error_handler(self)

        self.ui_optimizer.optimize_table_view(
            self.ui.main_window.channel_list
        )

        self._load_config()
        self._connect_signals()
        self._register_cleanup_handlers()
        self._register_config_observers()

    def init_controllers(self):
        """初始化所有控制器"""
        log_ui_info("=== 初始化控制器 ===")

        if not hasattr(self, 'scanner') or self.scanner is None:
            log_scan_info("创建ScannerController实例")
            self.scanner = ScannerController(self.model, self)
            log_scan_info(f"ScannerController创建完成: {self.scanner}")
        else:
            log_scan_info(f"ScannerController已存在: {self.scanner}")

        self.player_controller = PlayerController(
            self.ui.main_window.player, self.model
        )
        self.list_manager = ListManager(self.model)

        self._connect_progress_signals()
        self._on_play_state_changed(self.player_controller.is_playing)

        log_ui_info("=== 控制器初始化完成 ===")

    def _connect_progress_signals(self):
        """连接进度条更新信号"""
        # 使用进度条管理器注册扫描进度回调
        self.progress_manager.register_progress_callback(
            'scan',
            self._update_scan_progress
        )

        # 启动自动更新
        self.progress_manager.start_auto_update(
            self._update_scan_progress,
            interval=500
        )

        log_ui_info("进度条信号已连接")

    def _update_scan_progress(self):
        """更新扫描进度（使用进度条管理器）"""
        try:
            if hasattr(self.scanner, 'stats'):
                stats = self.scanner.stats
                total = stats.get('total', 0)
                valid = stats.get('valid', 0)
                invalid = stats.get('invalid', 0)

                current = valid + invalid

                if total > 0:
                    # 使用进度条管理器更新进度
                    self.progress_manager.update_progress_from_stats(
                        current,
                        total,
                        f"扫描进度: {current}/{total}"
                    )

                    # 检查是否完成
                    if current >= total and total > 0:
                        self.progress_manager.complete_progress("扫描完成")
                        self._set_scan_button_text('full_scan', '完整扫描')
                        self._set_append_scan_button_text('append_scan', '追加扫描')

        except AttributeError as e:
            log_scan_warning(f"扫描进度更新失败: {e}")
        except Exception as e:
            log_scan_warning(f"扫描进度更新时发生意外错误: {e}")

    def _on_scan_completed_for_progress(self):
        """处理扫描完成，隐藏进度条"""
        try:
            self.progress_manager.hide_progress()
        except AttributeError as e:
            log_ui_warning(f"隐藏进度条失败: {e}")
        except Exception as e:
            log_ui_warning(f"隐藏进度条时发生意外错误: {e}")

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
            log_config_error(f"加载配置失败: {e}")
            self.ui.main_window.timeout_input.setValue(10)
            self.ui.main_window.thread_count_input.setValue(5)

    def _register_config_observers(self):
        """注册配置变更观察者"""
        # 注册网络配置变更观察者
        register_config_observer("Network.*", self._on_network_config_changed)
        register_config_observer("ScanRetry.*", self._on_scan_retry_config_changed)
        register_config_observer("Language.current_language", self._on_language_config_changed)

        log_config_info("配置变更观察者已注册")

    def _on_network_config_changed(self, section, key, old_value, new_value):
        """处理网络配置变更"""
        log_config_info(f"网络配置变更: {section}.{key} = {old_value} -> {new_value}")

        # 更新对应的UI控件
        if key == 'url':
            self.ui.main_window.ip_range_input.setText(new_value)
        elif key == 'timeout':
            self.ui.main_window.timeout_input.setValue(int(new_value))
        elif key == 'threads':
            self.ui.main_window.thread_count_input.setValue(int(new_value))
        elif key == 'user_agent':
            self.ui.main_window.user_agent_input.setText(new_value)
        elif key == 'referer':
            self.ui.main_window.referer_input.setText(new_value)
        elif key == 'enable_retry':
            self.ui.main_window.enable_retry_checkbox.setChecked(new_value.lower() == 'true')
        elif key == 'loop_scan':
            self.ui.main_window.loop_scan_checkbox.setChecked(new_value.lower() == 'true')

    def _on_scan_retry_config_changed(self, section, key, old_value, new_value):
        """处理扫描重试配置变更"""
        log_config_info(f"扫描重试配置变更: {section}.{key} = {old_value} -> {new_value}")

        if key == 'enable_retry':
            self.ui.main_window.enable_retry_checkbox.setChecked(new_value.lower() == 'true')
        elif key == 'loop_scan':
            self.ui.main_window.loop_scan_checkbox.setChecked(new_value.lower() == 'true')

    def _on_language_config_changed(self, section, key, old_value, new_value):
        """处理语言配置变更"""
        log_config_info(f"语言配置变更: {section}.{key} = {old_value} -> {new_value}")

        if hasattr(self, 'language_manager'):
            self.language_manager.set_language(new_value)
            self.language_manager.update_ui_texts(self)

    def _connect_signals(self):
        """连接所有信号和槽"""
        log_ui_info("=== 开始连接信号 ===")

        self.ui.main_window.channel_list.selectionModel().selectionChanged.connect(
            self._on_channel_selected
        )

        safe_connect_button(self.ui.main_window.scan_btn, self._on_scan_clicked)
        safe_connect_button(self.ui.main_window.append_scan_btn, self._on_append_scan_clicked)

        self.ui.main_window.volume_slider.valueChanged.connect(
            self._on_volume_changed
        )
        safe_connect_button(self.ui.main_window.pause_btn, self._on_pause_clicked)
        safe_connect_button(self.ui.main_window.stop_btn, self._on_stop_clicked)

        self.player_controller.play_state_changed.connect(
            self._on_play_state_changed)

        self.ui.main_window.channel_list.doubleClicked.connect(self._play_selected_channel)

        safe_connect_button(self.ui.main_window.btn_validate, self._on_validate_clicked)
        safe_connect_button(self.ui.main_window.btn_hide_invalid, self._on_hide_invalid_clicked)
        safe_connect_button(self.ui.main_window.generate_btn, self._on_generate_clicked)

        # 连接扫描器信号
        log_ui_info("连接扫描器信号...")

        # 检查scanner对象是否存在
        if not hasattr(self, 'scanner') or self.scanner is None:
            log_ui_error("scanner对象不存在，无法连接信号")
            return

        log_ui_info(f"scanner对象: {self.scanner}")

        try:
            self.scanner.channel_found.connect(self._on_channel_found)
            log_ui_info("channel_found信号已连接")
        except Exception as e:
            log_ui_error(f"连接channel_found信号失败: {e}")

        try:
            self.scanner.scan_completed.connect(self._on_scan_completed)
            log_ui_info("scan_completed信号已连接到 _on_scan_completed")
        except Exception as e:
            log_ui_error(f"连接scan_completed信号失败: {e}")

        try:
            self.scanner.stats_updated.connect(
                self._update_stats_display,
                QtCore.Qt.ConnectionType.QueuedConnection
            )
            log_ui_info("stats_updated信号已连接")
        except Exception as e:
            log_ui_error(f"连接stats_updated信号失败: {e}")

        log_ui_info("=== 信号连接完成 ===")

    def _on_scan_clicked(self):
        """处理扫描按钮点击事件"""
        if self.scanner.is_scanning():
            self.scanner.stop_scan()
            self._set_scan_button_text('full_scan', '完整扫描')
            self._set_append_scan_button_text('append_scan', '追加扫描')
        else:
            url = self.ui.main_window.ip_range_input.text()
            if not url.strip():
                log_ui_warning("请输入扫描地址")
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
                log_ui_warning("请输入扫描地址")
                self.ui.main_window.statusBar().showMessage("请输入扫描地址", 3000)
                return

            QtCore.QTimer.singleShot(0, lambda: self._start_scan_delayed(url, clear_list=False))

    def _start_scan_delayed(self, url, clear_list=True):
        """延迟启动扫描，避免UI阻塞"""
        if clear_list:
            self.model.clear()
            log_scan_info("开始完整扫描，清空现有列表")
        else:
            log_scan_info("开始追加扫描，保留现有列表")

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
            QtCore.QTimer.singleShot(
                0, lambda: header.resizeSections(QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
                )

    @QtCore.pyqtSlot()
    def _on_scan_completed(self):
        """处理扫描完成事件"""
        # 检查是否是重试扫描刚刚开始的情况
        is_retry = self.scan_state_manager.is_retry_scan(self.retry_id)
        retry_count = self.scan_state_manager.get_retry_count(self.retry_id)
        if is_retry and retry_count > 0:
            # 检查扫描器是否正在扫描
            if hasattr(self, 'scanner') and self.scanner and self.scanner.is_scanning():
                self.logger.info("重试扫描进行中，跳过完成处理")
                return

        # 隐藏进度条
        self.progress_manager.hide_progress()

        # 只有在扫描真正完成时才更新按钮文本
        is_retry_scan = self.scan_state_manager.is_retry_scan(self.retry_id)
        if not is_retry_scan or (is_retry_scan and not self.scanner.is_scanning()):
            self._set_scan_button_text('full_scan', '完整扫描')
            self._set_append_scan_button_text('append_scan', '追加扫描')

        self.ui.main_window.btn_validate.setText("检测有效性")

        # 更新UI状态
        self.ui.main_window.btn_smart_sort.setEnabled(True)
        self.ui.main_window.btn_smart_sort.setStyleSheet(
            AppStyles.button_style(active=True)
        )

        if hasattr(self.ui.main_window, 'channel_list'):
            header = self.ui.main_window.channel_list.horizontalHeader()
            header.resizeSections(QtWidgets.QHeaderView.ResizeMode.ResizeToContents)

        # 检查是否需要重试扫描
        if not self.scan_state_manager.is_retry_scan(self.retry_id):
            # 这是第一次扫描完成，检查是否需要重试
            if self.ui.main_window.enable_retry_checkbox.isChecked():
                self.logger.info("开始重试扫描")
                self._handle_retry_scan()
            else:
                self.logger.info("扫描完成")
        else:
            # 这是重试扫描完成，处理循环扫描逻辑
            self.logger.info("重试扫描完成")
            self._handle_retry_scan_completed()

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

        # 注册配置保存处理器（应该在清理前执行）
        register_cleanup(self.save_before_exit, "save_config_before_exit")
        handler_names.append("save_config_before_exit")

        register_cleanup(self._stop_all_timers, "stop_all_timers")
        handler_names.append("stop_all_timers")

        # 进度条管理器清理
        register_cleanup(self.progress_manager.stop_auto_update, "progress_manager_stop_auto_update")
        handler_names.append("progress_manager_stop_auto_update")

        register_cleanup(self.progress_manager.hide_progress, "progress_manager_hide_progress")
        handler_names.append("progress_manager_hide_progress")

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

    def _handle_retry_scan(self):
        """处理重试扫描"""
        self.logger.info("=== _handle_retry_scan 方法开始 ===")

        # 使用重试扫描状态上下文管理器
        with RetryScanStateContext(self.retry_id, self):
            self._handle_retry_scan_internal()

    def _handle_retry_scan_internal(self):
        """内部重试扫描处理方法"""
        # 收集失败的频道
        self._collect_failed_channels()

        failed_channels = self.scan_state_manager.get_failed_channels(self.retry_id)
        self.logger.info(f"收集到的失败频道数量: {len(failed_channels)}")

        if not failed_channels:
            self.logger.info("没有失败的频道需要重试")
            self.ui.main_window.statusBar().showMessage("没有失败的频道需要重试", 3000)
            self.logger.info("=== _handle_retry_scan 方法结束（无失败频道）===")
            return

        # 记录当前的有效频道数，用于判断是否找到了新的有效频道
        current_valid_count = self._count_valid_channels()
        self.scan_state_manager.update_last_retry_valid_count(self.retry_id, current_valid_count)
        self.logger.info(f"当前有效频道数: {current_valid_count}")

        # 启动重试扫描
        self._start_retry_scan()

        self.logger.info("=== _handle_retry_scan 方法结束 ===")

    def _collect_failed_channels(self):
        """收集失败的频道URL"""
        # 从扫描状态管理器获取无效的URL列表
        if hasattr(self, 'scanner') and self.scanner:
            # 获取扫描状态管理器中的无效URL
            invalid_urls = self.scanner.scan_state_manager.get_invalid_urls(self.scanner.scan_id)

            # 添加到重试扫描状态管理器
            for url in invalid_urls:
                self.scan_state_manager.add_failed_channel(self.retry_id, url)

            self.logger.info(f"从扫描状态管理器获取失败频道: {len(invalid_urls)} 个")

            # 调试：记录前5个无效URL
            for i in range(min(5, len(invalid_urls))):
                url = invalid_urls[i]
                self.logger.info(f"无效URL {i}: {url[:50]}")
        else:
            self.logger.warning("ScannerController不存在，无法获取失败频道列表")

        failed_channels = self.scan_state_manager.get_failed_channels(self.retry_id)
        self.logger.info(f"收集完成: 失败频道数={len(failed_channels)}")

    def _count_valid_channels(self):
        """统计有效频道数量"""
        valid_count = 0
        for i in range(self.model.rowCount()):
            channel = self.model.get_channel(i)
            if channel.get('valid', False):
                valid_count += 1
        return valid_count

    def _start_retry_scan(self):
        """启动重试扫描"""
        # 更新重试扫描状态
        self.scan_state_manager.update_retry_state(self.retry_id, {
            'is_retry_scan': True
        })

        # 增加重试计数
        retry_count = self.scan_state_manager.increment_retry_count(self.retry_id)

        failed_channels = self.scan_state_manager.get_failed_channels(self.retry_id)
        self.logger.info(f"开始第 {retry_count} 次重试扫描，共 {len(failed_channels)} 个频道")
        self.ui.main_window.statusBar().showMessage(f"开始第 {retry_count} 次重试扫描...", 3000)

        # 使用扫描服务的 start_scan_from_urls 方法
        timeout = self.ui.main_window.timeout_input.value()
        threads = self.ui.main_window.thread_count_input.value()
        user_agent = self.ui.main_window.user_agent_input.text()
        referer = self.ui.main_window.referer_input.text()

        self.scanner.start_scan_from_urls(
            failed_channels,
            threads,
            timeout,
            user_agent,
            referer
        )

        # 更新按钮文本
        self._set_scan_button_text('stop_scan', '停止扫描')
        self._set_append_scan_button_text('stop_scan', '停止扫描')

    def _handle_retry_scan_completed(self):
        """处理重试扫描完成"""
        # 计算本次重试找到的有效频道数
        current_valid_count = self._count_valid_channels()
        last_retry_valid_count = self.scan_state_manager.get_last_retry_valid_count(self.retry_id)
        new_valid_count = current_valid_count - last_retry_valid_count

        retry_count = self.scan_state_manager.get_retry_count(self.retry_id)
        self.logger.info(f"第 {retry_count} 次重试扫描完成，找到 {new_valid_count} 个新的有效频道")

        # 检查是否需要继续循环扫描
        if self.ui.main_window.loop_scan_checkbox.isChecked() and new_valid_count > 0:
            # 找到了新的有效频道，继续扫描
            self.logger.info("循环扫描启用，继续扫描失败的频道")
            self.ui.main_window.statusBar().showMessage(f"找到 {new_valid_count} 个新频道，继续扫描...", 3000)

            # 重新收集失败的频道并继续扫描
            QtCore.QTimer.singleShot(1000, self._continue_loop_scan)
        else:
            # 循环扫描未启用或没有找到新的有效频道，结束重试
            self._finish_retry_scan()

    def _continue_loop_scan(self):
        """继续循环扫描"""
        # 重新收集失败的频道
        self._collect_failed_channels()

        failed_channels = self.scan_state_manager.get_failed_channels(self.retry_id)
        if not failed_channels:
            self.logger.info("所有频道都已有效，循环扫描结束")
            self.ui.main_window.statusBar().showMessage("所有频道都已有效，循环扫描结束", 3000)
            self._finish_retry_scan()
            return

        # 更新有效频道计数
        current_valid_count = self._count_valid_channels()
        self.scan_state_manager.update_last_retry_valid_count(self.retry_id, current_valid_count)

        # 继续重试扫描
        self._start_retry_scan()

    def _finish_retry_scan(self):
        """完成重试扫描"""
        # 更新重试扫描状态
        self.scan_state_manager.update_retry_state(self.retry_id, {
            'is_retry_scan': False
        })

        total_valid = self._count_valid_channels()
        retry_count = self.scan_state_manager.get_retry_count(self.retry_id)

        self.logger.info(f"重试扫描完成，共进行 {retry_count} 次重试，总计有效频道: {total_valid}")
        self.ui.main_window.statusBar().showMessage(f"重试扫描完成，总计有效频道: {total_valid}", 5000)

        # 重置重试状态（通过RetryScanStateContext的__exit__方法自动处理）
        # 更新按钮文本
        self._set_scan_button_text('full_scan', '完整扫描')
        self._set_append_scan_button_text('append_scan', '追加扫描')

    def _check_for_updates_async(self):
        """异步检查新版本"""
        try:
            # 在后台线程中执行版本检查
            from PyQt6.QtCore import QThread, pyqtSignal
            import asyncio
            import aiohttp

            class UpdateCheckThread(QThread):
                """版本检查线程"""
                update_found = pyqtSignal(str, str)  # 最新版本号, 当前版本号
                check_completed = pyqtSignal(bool, str)  # 是否成功, 消息

                def run(self):
                    try:
                        # 创建新的事件循环
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)

                        # 获取当前版本
                        from ui.dialogs.about_dialog import AboutDialog
                        current_version = AboutDialog.CURRENT_VERSION

                        # 获取最新版本（设置超时避免长时间等待）
                        latest_version, _, _ = loop.run_until_complete(
                            asyncio.wait_for(self._get_latest_version(), timeout=15)
                        )

                        if latest_version and not latest_version.startswith("("):
                            # 检查是否有新版本
                            if self._is_newer_version(current_version, latest_version):
                                self.update_found.emit(latest_version, current_version)
                                self.check_completed.emit(True, f"发现新版本: {latest_version}")
                            else:
                                self.check_completed.emit(True, "当前已是最新版本")
                        else:
                            # 网络错误或其他问题，静默处理，不显示给用户
                            self.check_completed.emit(False, f"版本检查失败: {latest_version}")

                    except asyncio.TimeoutError:
                        # 超时错误，静默处理
                        self.check_completed.emit(False, "版本检查超时")
                    except Exception as e:
                        # 其他异常，静默处理
                        self.check_completed.emit(False, f"版本检查异常: {str(e)}")
                    finally:
                        try:
                            loop.close()
                        except Exception:
                            pass

                async def _get_latest_version(self):
                    """从GitHub获取最新版本信息"""
                    try:
                        async with aiohttp.ClientSession() as session:
                            async with session.get(
                                "https://api.github.com/repos/sumingyd/IPTV-Scanner-Editor-Pro/releases/latest",
                                headers={'User-Agent': 'IPTV-Scanner-Editor-Pro'},
                                timeout=aiohttp.ClientTimeout(total=10)
                            ) as response:
                                if response.status == 200:
                                    data = await response.json()
                                    version = data.get('tag_name', '').lstrip('v')
                                    return version, None, None
                                elif response.status == 403:
                                    return "(API限制)", None, None
                                else:
                                    return "(获取失败)", None, None
                    except asyncio.TimeoutError:
                        return "(请求超时)", None, None
                    except Exception:
                        return "(获取失败)", None, None

                def _is_newer_version(self, current_version, latest_version):
                    """比较版本号，判断最新版本是否比当前版本新"""
                    try:
                        # 将版本号转换为数字列表进行比较
                        current_parts = list(map(int, current_version.split('.')))
                        latest_parts = list(map(int, latest_version.split('.')))

                        # 确保两个版本号有相同的长度
                        max_length = max(len(current_parts), len(latest_parts))
                        current_parts.extend([0] * (max_length - len(current_parts)))
                        latest_parts.extend([0] * (max_length - len(latest_parts)))

                        # 逐位比较
                        for i in range(max_length):
                            if latest_parts[i] > current_parts[i]:
                                return True
                            elif latest_parts[i] < current_parts[i]:
                                return False
                        return False  # 版本相同
                    except (ValueError, AttributeError):
                        # 如果版本号格式不正确，使用字符串比较
                        return latest_version > current_version

            # 创建并启动版本检查线程
            self.update_check_thread = UpdateCheckThread()
            self.update_check_thread.setParent(self)
            self.update_check_thread.update_found.connect(self._on_update_found)
            self.update_check_thread.check_completed.connect(self._on_update_check_completed)
            self.update_check_thread.start()

        except Exception as e:
            self.logger.error(f"启动版本检查失败: {str(e)}")

    def _on_update_found(self, latest_version, current_version):
        """发现新版本时的处理"""
        try:
            # 在窗口标题添加提示
            original_title = self.windowTitle()
            if " - 有新版本" not in original_title:
                new_title = f"{original_title} - 有新版本 {latest_version}"
                self.setWindowTitle(new_title)

            # 在状态栏用红字显示提示
            status_message = f"发现新版本 {latest_version} (当前版本 {current_version})"
            self.ui.main_window.statusBar().showMessage(status_message, 10000)  # 显示10秒

            # 设置状态栏消息为红色
            self.ui.main_window.statusBar().setStyleSheet(AppStyles.statusbar_error_style())

            # 10秒后恢复状态栏样式
            QtCore.QTimer.singleShot(10000, lambda: self.ui.main_window.statusBar().setStyleSheet(""))

            self.logger.info(f"发现新版本: {latest_version} (当前版本: {current_version})")

        except Exception as e:
            self.logger.error(f"更新界面提示失败: {str(e)}")

    def _on_update_check_completed(self, success, message):
        """版本检查完成时的处理"""
        if success:
            self.logger.info(f"版本检查完成: {message}")
        else:
            self.logger.warning(f"版本检查失败: {message}")
