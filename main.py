from PyQt6 import QtWidgets, QtCore, QtGui
import time
import threading
from channel_model import ChannelListModel
from ui_builder import UIBuilder
from config_manager import ConfigManager
from log_manager import LogManager
from scanner_controller import ScannerController
from styles import AppStyles
import sys

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        # 初始化配置和日志管理器
        self.config = ConfigManager()
        self.logger = LogManager()
        
        # 构建UI
        self.ui = UIBuilder(self)
        self.ui.build_ui()
        
        # 初始化控制器(确保模型已由UIBuilder初始化)
        self.scanner = ScannerController(self.model)
        from player_controller import PlayerController
        from list_manager import ListManager
        self.player_controller = PlayerController(self.ui.main_window.player, self.model)
        self.list_manager = ListManager(self.model)
        
        # UI构建完成后加载配置
        self._load_config()
        
        
        # 连接信号槽
        self._connect_signals()

    def _update_validate_status(self, message):
        """更新有效性检测状态标签"""
        self.ui.main_window.validate_stats_label.setText(message)
        message == "请点击检测有效性按钮"

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
        except Exception as e:
            self.logger.error(f"加载网络设置失败: {e}")
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
                
        # 连接工具栏按钮
        for action in self.ui.main_window.findChildren(QtGui.QAction):
            try:
                action.triggered.disconnect()
            except:
                pass
            if "打开列表" in action.text():
                action.triggered.connect(self._open_list)
            elif "保存列表" in action.text():
                action.triggered.connect(self._save_list)
            elif "关于" in action.text():
                action.triggered.connect(self._on_about_clicked)
                
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
        
        # 进度更新信号
        self.scanner.progress_updated.connect(
            lambda cur, total: self.ui.main_window.scan_progress.setValue(
                int(cur / total * 100) if total > 0 else 0
            )
        )
        
        # 频道发现信号
        self.scanner.channel_found.connect(self._on_channel_found)
        
        # 扫描完成信号
        self.scanner.scan_completed.connect(self._on_scan_completed)
        
        # 统计信息更新信号
        self.scanner.stats_updated.connect(self._update_stats_display)

    def _on_scan_clicked(self):
        """处理扫描按钮点击事件"""
        if self.scanner.is_scanning():
            # 停止扫描
            self.scanner.stop_scan()
            self.ui.main_window.scan_btn.setText("完整扫描")
        else:
            # 检查地址是否为空
            url = self.ui.main_window.ip_range_input.text()
            if not url.strip():
                self.logger.warning("请输入扫描地址")
                self.ui.main_window.statusBar().showMessage("请输入扫描地址", 3000)
                return
                
            # 开始扫描前清空列表
            self.model.clear()
            timeout = self.ui.main_window.timeout_input.value()
            threads = self.ui.main_window.thread_count_input.value()
            self.scanner.start_scan(url, threads, timeout)
            self.ui.main_window.scan_btn.setText("停止扫描")

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
        is_playing = self.player_controller.toggle_pause()
        self.ui.main_window.pause_btn.setText("暂停" if is_playing else "播放")

    def _on_stop_clicked(self):
        """处理停止按钮点击"""
        self.player_controller.stop()
        self.ui.main_window.pause_btn.setText("播放")

    def _on_play_state_changed(self, is_playing):
        """处理播放状态变化"""
        self.ui.main_window.stop_btn.setEnabled(is_playing)
        self.ui.main_window.stop_btn.setStyleSheet(
            AppStyles.button_style(active=is_playing)
        )

    def _open_list(self):
        """打开列表文件"""
        try:
            result = self.list_manager.open_list(self)
                
            if result:
                self.ui.main_window.btn_hide_invalid.setEnabled(False)
                self.ui.main_window.btn_validate.setEnabled(True)
                self.ui.main_window.statusBar().showMessage("列表加载成功", 3000)
                
                # 强制触发模型重置信号
                self.model.modelReset.emit()
                return True
            else:
                self.logger.warning("打开列表失败")
                self.ui.main_window.statusBar().showMessage("打开列表失败", 3000)
                return False
        except Exception as e:
            self.logger.error(f"打开列表失败: {str(e)}", exc_info=True)
            self.ui.main_window.statusBar().showMessage(f"打开列表失败: {str(e)}", 3000)
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
            
        if self.player_controller.play_channel(channel):
            self.ui.main_window.pause_btn.setText("暂停")
            self.current_channel = channel

    def _on_channel_found(self, channel_info):
        """处理发现有效频道事件"""
        self.ui.main_window.model.add_channel(channel_info)

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

    def _update_stats_display(self, stats_data):
        """更新统计信息显示"""
        if stats_data.get('is_validation', False):
            # 更新检测有效性统计标签
            self.ui.main_window.validate_stats_label.setText(stats_data['text'])
        else:
            # 更新扫描统计信息
            stats = stats_data.get('stats', {})
            elapsed = time.strftime("%H:%M:%S", time.gmtime(stats.get('elapsed', 0)))
            self.ui.main_window.detailed_stats_label.setText(
                f"总数: {stats.get('total', 0)} | "
                f"有效: {stats.get('valid', 0)} | "
                f"无效: {stats.get('invalid', 0)} | "
                f"耗时: {elapsed}"
            )

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
            self.logger.info("程序退出前配置已保存")
        except Exception as e:
            self.logger.error(f"保存退出配置失败: {e}")

def main():
    # 设置事件循环策略为Windows策略(兼容性更好)
    if sys.platform == "win32":
        import asyncio
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    # 创建应用实例
    app = QtWidgets.QApplication(sys.argv)
    
    # 创建主窗口
    window = MainWindow()
    window.show()
    
    # 确保程序退出前保存所有配置
    app.aboutToQuit.connect(window.save_before_exit)
    
    # 启动事件循环
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
