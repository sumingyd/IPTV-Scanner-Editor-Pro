# 导入PyQt6 GUI框架的核心模块
from PyQt6 import QtWidgets, QtCore, QtGui
# 导入时间相关操作模块
import time
# 导入多线程编程模块
import threading
# 导入操作系统接口模块
import os
# 导入系统相关模块
import sys
# 导入随机数生成模块
import random

# 核心模块导入 - 从自定义模块导入应用程序需要的各个组件
# 从channel_model模块导入ChannelListModel类
from channel_model import ChannelListModel
# 从ui_builder模块导入UIBuilder类
from ui_builder import UIBuilder
# 从config_manager模块导入ConfigManager类
from config_manager import ConfigManager
# 从log_manager模块导入LogManager类和global_logger全局对象
from log_manager import LogManager, global_logger
# 从scanner_controller模块导入ScannerController类
from scanner_controller import ScannerController
# 从styles模块导入AppStyles类
from styles import AppStyles
# 从player_controller模块导入PlayerController类
from player_controller import PlayerController
# 从list_manager模块导入ListManager类
from list_manager import ListManager
# 从url_parser模块导入URLRangeParser类
from url_parser import URLRangeParser
# 从language_manager模块导入LanguageManager类
from language_manager import LanguageManager
# 从ui_optimizer模块导入get_ui_optimizer函数
from ui_optimizer import get_ui_optimizer
# 从error_handler模块导入各种错误处理和消息显示函数
from error_handler import init_global_error_handler, show_error, show_warning, show_info, show_confirm
# 从resource_cleaner模块导入资源清理相关函数
from resource_cleaner import get_resource_cleaner, register_cleanup, cleanup_all
# 从utils模块导入工具函数
from utils import safe_connect, safe_connect_button

# 定义主窗口类，继承自QMainWindow
class MainWindow(QtWidgets.QMainWindow):
    # 初始化方法，构造主窗口对象
    def __init__(self) -> None:
        # 调用父类QMainWindow的初始化方法
        super().__init__()
        # 在UI构建前完全隐藏窗口，防止任何闪动
        self.hide()
        # 创建配置管理器实例，用于管理应用程序配置
        self.config = ConfigManager()
        # 获取全局日志记录器实例
        self.logger = global_logger
        # 创建语言管理器实例
        self.language_manager = LanguageManager()
        # 加载所有可用的语言文件
        self.language_manager.load_available_languages()
        # 从配置加载语言设置，获取语言代码
        language_code = self.config.load_language_settings()
        # 设置应用程序语言，根据配置的语言代码
        if self.language_manager.set_language(language_code):
            # 语言设置成功后的占位符，暂无其他操作
            pass
        
        # 创建UI构建器实例，传入当前窗口对象作为参数
        self.ui = UIBuilder(self)
        # 调用UI构建器构建用户界面
        self.ui.build_ui()
        
        # 立即更新UI文本到当前语言
        if hasattr(self, 'language_manager'):
            # 调用语言管理器更新所有UI文本为当前语言
            self.language_manager.update_ui_texts(self)
        
        # 设置窗口图标，如果图标文件存在的话
        if os.path.exists('logo.ico'):
            # 使用logo.ico文件作为窗口图标
            self.setWindowIcon(QtGui.QIcon('logo.ico'))

        # 初始化主窗口的后续设置
        self._init_main_window()
        # 初始化定时器列表，用于存储所有定时器对象
        self._timers = []
        # 使用单次定时器延迟初始化所有定时器，确保在主线程执行
        QtCore.QTimer.singleShot(0, self._init_timers)
    # 初始化所有定时器的方法
    def _init_timers(self):
        """在主线程初始化所有定时器"""
        # 定时器管理器：统一管理所有定时器
        # 当前暂无需要管理的定时器，保留结构便于扩展
        pass
        
    # 安全停止所有定时器的方法
    def _stop_all_timers(self):
        """安全停止所有定时器"""
        # 检查是否存在定时器列表属性
        if hasattr(self, '_timers'):
            # 遍历所有定时器
            for timer in self._timers:
                # 检查定时器是否正在运行
                if timer.isActive():
                    # 检查定时器是否在当前线程中
                    if QtCore.QThread.currentThread() == timer.thread():
                        # 在当前线程直接停止定时器
                        timer.stop()
                    else:
                        # 在其他线程，通过信号队列方式停止定时器
                        QtCore.QMetaObject.invokeMethod(timer, "stop", QtCore.Qt.ConnectionType.QueuedConnection)
            # 清空定时器列表
            self._timers.clear()
        
    # 初始化主窗口后续设置的方法
    def _init_main_window(self) -> None:
        """初始化主窗口的后续设置"""
        # 从UI获取频道列表数据模型
        self.model = self.ui.main_window.model
        
        # 设置模型的父对象为主窗口，确保可以访问UI层的方法
        self.model.setParent(self)
        
        # 初始化所有控制器
        self.init_controllers()

        # 初始化UI优化器和错误处理器
        self.ui_optimizer = get_ui_optimizer()
        self.error_handler = init_global_error_handler(self)
        
        # 优化频道列表视图性能，提高表格渲染效率
        self.ui_optimizer.optimize_table_view(self.ui.main_window.channel_list)

        # UI构建完成后再次加载配置，确保UI元素正确显示配置值
        self._load_config()
        
        # 连接各种信号和槽函数
        self._connect_signals()
        
        # 注册资源清理处理器，确保程序退出时正确释放资源
        self._register_cleanup_handlers()

    # 初始化所有控制器的方法
    def init_controllers(self):
        """初始化所有控制器"""
        # 确保只创建一个扫描器对象，避免重复创建
        if not hasattr(self, 'scanner') or self.scanner is None:
            self.scanner = ScannerController(self.model, self)
        # 创建播放器控制器，控制音视频播放
        self.player_controller = PlayerController(self.ui.main_window.player, self.model)
        # 创建列表管理器，管理频道列表操作
        self.list_manager = ListManager(self.model)
        
        # 立即连接进度条更新信号，确保扫描进度能实时显示
        self._connect_progress_signals()
        
        # 初始化播放器按钮状态，根据播放状态设置按钮图标和文本
        self._on_play_state_changed(self.player_controller.is_playing)

    # 连接进度条更新信号的方法
    def _connect_progress_signals(self):
        """连接进度条更新信号 - 使用简单的定时器方案"""
        
        # 检查进度条对象是否存在，避免属性访问错误
        if not hasattr(self.ui.main_window, 'progress_indicator'):
            return
            
        # 检查进度条是否为None，避免空对象错误
        if self.ui.main_window.progress_indicator is None:
            return
            
        # 初始化进度条范围和初始值
        self.ui.main_window.progress_indicator.setRange(0, 100)
        self.ui.main_window.progress_indicator.setValue(0)
        # 设置进度条文本可见
        self.ui.main_window.progress_indicator.setTextVisible(True)
        # 设置进度条显示格式为百分比
        self.ui.main_window.progress_indicator.setFormat("%p%")
        # 初始隐藏进度条
        self.ui.main_window.progress_indicator.hide()
        
        # 创建定时器来定期更新进度条
        self.progress_timer = QtCore.QTimer()
        # 连接定时器的timeout信号到进度更新方法
        self.progress_timer.timeout.connect(self._update_progress_from_stats)
        # 启动定时器，每500ms更新一次
        self.progress_timer.start(500)
        
        # 连接扫描完成信号到进度条完成处理方法
        self.scanner.scan_completed.connect(self._on_scan_completed_for_progress)

    # 从统计信息更新进度条的方法
    def _update_progress_from_stats(self):
        """从统计信息更新进度条"""
        try:
            # 获取扫描器的统计信息
            if hasattr(self.scanner, 'stats'):
                # 获取扫描统计字典
                stats = self.scanner.stats
                # 获取总扫描数量
                total = stats.get('total', 0)
                # 获取有效数量
                valid = stats.get('valid', 0)
                # 获取无效数量
                invalid = stats.get('invalid', 0)
                
                # 计算当前已处理的数量
                current = valid + invalid
                
                # 计算百分比进度
                if total <= 0:
                    # 如果总数为0，进度为0
                    progress_value = 0
                else:
                    # 计算百分比
                    progress_value = int(current / total * 100)
                    # 确保进度值在0-100范围内
                    progress_value = max(0, min(100, progress_value))
                
                # 如果进度条未显示且有扫描任务，则显示进度条
                if not self.ui.main_window.progress_indicator.isVisible() and total > 0:
                    self.ui.main_window.progress_indicator.show()
                
                # 获取旧进度值
                old_value = self.ui.main_window.progress_indicator.value()
                # 如果进度值发生变化，则更新进度条
                if old_value != progress_value:
                    self.ui.main_window.progress_indicator.setValue(progress_value)
                    
                    # 关键修复：当进度达到100%时，自动恢复按钮文本
                    if progress_value >= 100 and old_value < 100:
                        # 恢复完整扫描按钮的文本
                        self._set_scan_button_text('full_scan', '完整扫描')
                        # 恢复追加扫描按钮的文本
                        self._set_append_scan_button_text('append_scan', '追加扫描')
                        # 隐藏进度条
                        self.ui.main_window.progress_indicator.hide()
                        # 重置进度条值为0
                        self.ui.main_window.progress_indicator.setValue(0)
                    
        except AttributeError as e:
            # 如果UI组件不存在，记录调试信息
            self.logger.debug(f"进度条更新失败，UI组件可能未初始化: {e}")
        except Exception as e:
            # 记录其他异常，但不影响主程序运行
            self.logger.warning(f"进度条更新时发生意外错误: {e}")
            
    # 处理扫描完成时进度条更新的方法
    def _on_scan_completed_for_progress(self):
        """处理扫描完成，隐藏进度条"""
        try:
            self._hide_progress_indicator()
        except AttributeError as e:
            # 如果UI组件不存在，记录调试信息
            self.logger.debug(f"隐藏进度条失败，UI组件可能未初始化: {e}")
        except Exception as e:
            # 记录其他异常，但不影响主程序运行
            self.logger.warning(f"隐藏进度条时发生意外错误: {e}")

    def _hide_progress_indicator(self):
        """统一隐藏进度条的方法"""
        if hasattr(self.ui.main_window, 'progress_indicator'):
            self.ui.main_window.progress_indicator.hide()
            self.ui.main_window.progress_indicator.setValue(0)

    # 加载配置文件到UI的方法
    def _load_config(self) -> None:
        """加载保存的配置到UI"""
        try:
            # 从配置管理器加载网络设置
            settings = self.config.load_network_settings()
            
            # 设置IP范围输入框的文本，如果配置中有URL值
            if settings['url']:
                self.ui.main_window.ip_range_input.setText(settings['url'])
            
            # 设置超时时间的值，转换为整数
            self.ui.main_window.timeout_input.setValue(int(settings['timeout']))
            
            # 设置线程数量的值，转换为整数
            self.ui.main_window.thread_count_input.setValue(int(settings['threads']))
            
            # 设置用户代理输入框的文本，如果配置中有user_agent值
            if settings['user_agent']:
                self.ui.main_window.user_agent_input.setText(settings['user_agent'])
            
            # 设置来源引用输入框的文本，如果配置中有referer值
            if settings['referer']:
                self.ui.main_window.referer_input.setText(settings['referer'])
            
            # 加载语言设置（不在这里更新UI文本，由后台任务统一处理）
            language_code = self.config.load_language_settings()
            
            # 如果语言管理器已初始化，则设置应用程序语言
            if hasattr(self, 'language_manager'):
                self.language_manager.set_language(language_code)
                    
        except Exception as e:
            # 配置加载失败时记录错误日志
            self.logger.error(f"加载配置失败: {e}")
            # 设置默认值，确保程序能正常运行
            self.ui.main_window.timeout_input.setValue(10)  # 默认超时10秒
            self.ui.main_window.thread_count_input.setValue(5)  # 默认5个线程

    # 连接所有信号和槽函数的方法
    def _connect_signals(self) -> None:
        """连接所有信号和槽"""
        # 连接频道列表选择信号：当列表选择发生变化时触发
        self.ui.main_window.channel_list.selectionModel().selectionChanged.connect(
            self._on_channel_selected  # 连接到频道选择处理方法
        )
        
        # 使用safe_connect_button连接按钮信号，避免重复连接
        safe_connect_button(self.ui.main_window.scan_btn, self._on_scan_clicked)
        safe_connect_button(self.ui.main_window.append_scan_btn, self._on_append_scan_clicked)
                
        # 连接播放控制信号
        # 音量滑块值改变时触发音量改变事件
        self.ui.main_window.volume_slider.valueChanged.connect(
            self._on_volume_changed)
        # 暂停按钮点击时触发暂停事件
        safe_connect_button(self.ui.main_window.pause_btn, self._on_pause_clicked)
        # 停止按钮点击时触发停止事件
        safe_connect_button(self.ui.main_window.stop_btn, self._on_stop_clicked)
        
        # 连接播放状态变化信号：当播放状态改变时更新UI
        self.player_controller.play_state_changed.connect(
            self._on_play_state_changed)
        
        # 连接频道列表双击事件：双击频道时播放选中的频道
        self.ui.main_window.channel_list.doubleClicked.connect(self._play_selected_channel)
        
        # 连接有效性检测按钮：点击时验证频道有效性
        safe_connect_button(self.ui.main_window.btn_validate, self._on_validate_clicked)
        
        # 连接隐藏无效项按钮：点击时隐藏无效的频道
        safe_connect_button(self.ui.main_window.btn_hide_invalid, self._on_hide_invalid_clicked)
        
        # 连接直接生成列表按钮：点击时生成频道列表
        safe_connect_button(self.ui.main_window.generate_btn, self._on_generate_clicked)
        
        # 频道发现信号：当扫描器发现新频道时触发
        self.scanner.channel_found.connect(self._on_channel_found)
        
        # 扫描完成信号：当扫描任务完成时触发
        self.scanner.scan_completed.connect(self._on_scan_completed)
        
        # 统计信息更新信号 - 使用QueuedConnection确保跨线程安全
        self.scanner.stats_updated.connect(
            self._update_stats_display,  # 连接到统计信息显示更新方法
            QtCore.Qt.ConnectionType.QueuedConnection  # 使用队列连接确保线程安全
        )

    # 处理扫描按钮点击事件的方法
    def _on_scan_clicked(self) -> None:
        """处理扫描按钮点击事件 - 使用QTimer避免UI阻塞"""
        # 检查扫描器当前是否正在扫描
        if self.scanner.is_scanning():
            # 如果正在扫描，则停止扫描 - 立即响应
            self.scanner.stop_scan()
            # 停止扫描后，两个按钮都应该恢复原始文本
            self._set_scan_button_text('full_scan', '完整扫描')
            self._set_append_scan_button_text('append_scan', '追加扫描')
        else:
            # 如果未在扫描，则开始新的扫描
            # 检查地址输入框是否为空
            url = self.ui.main_window.ip_range_input.text()
            if not url.strip():  # 检查去除空格后是否为空
                self.logger.warning("请输入扫描地址")  # 记录警告日志
                self.ui.main_window.statusBar().showMessage("请输入扫描地址", 3000)  # 状态栏显示提示3秒
                return  # 返回，不执行扫描
                
            # 使用QTimer延迟执行扫描，避免UI阻塞
            # singleShot(0)表示尽快执行，但不阻塞当前事件循环
            QtCore.QTimer.singleShot(0, lambda: self._start_scan_delayed(url, clear_list=True))
    
    # 处理追加扫描按钮点击事件的方法
    def _on_append_scan_clicked(self) -> None:
        """处理追加扫描按钮点击事件"""
        # 检查扫描器当前是否正在扫描
        if self.scanner.is_scanning():
            # 如果正在扫描，则停止扫描 - 立即响应
            self.scanner.stop_scan()
            # 停止扫描后，两个按钮都应该恢复原始文本
            self._set_scan_button_text('full_scan', '完整扫描')
            self._set_append_scan_button_text('append_scan', '追加扫描')
        else:
            # 如果未在扫描，则开始追加扫描
            # 检查地址输入框是否为空
            url = self.ui.main_window.ip_range_input.text()
            if not url.strip():  # 检查去除空格后是否为空
                self.logger.warning("请输入扫描地址")  # 记录警告日志
                self.ui.main_window.statusBar().showMessage("请输入扫描地址", 3000)  # 状态栏显示提示3秒
                return  # 返回，不执行追加扫描
                
            # 使用QTimer延迟执行追加扫描，避免UI阻塞
            QtCore.QTimer.singleShot(0, lambda: self._start_scan_delayed(url, clear_list=False))
            
    # 延迟启动扫描的方法，避免UI阻塞
    def _start_scan_delayed(self, url, clear_list=True):
        """延迟启动扫描，避免UI阻塞"""
        # 根据参数决定是否清空现有列表
        if clear_list:
            # 如果是完整扫描，清空现有频道列表
            self.model.clear()
            self.logger.info("开始完整扫描，清空现有列表")  # 记录信息日志
        else:
            # 如果是追加扫描，保留现有列表
            self.logger.info("开始追加扫描，保留现有列表")  # 记录信息日志
            
        # 获取超时时间和线程数配置
        timeout = self.ui.main_window.timeout_input.value()
        threads = self.ui.main_window.thread_count_input.value()
        
        # 启动扫描器开始扫描
        self.scanner.start_scan(url, threads, timeout)
        
        # 根据扫描类型设置按钮文本
        if clear_list:
            # 完整扫描时设置扫描按钮为"停止扫描"
            self._set_scan_button_text('stop_scan', '停止扫描')
        else:
            # 追加扫描时设置追加扫描按钮为"停止扫描"
            self._set_append_scan_button_text('stop_scan', '停止扫描')
        
    # 通用按钮文本设置函数
    def _set_button_text(self, button, translation_key, default_text):
        """通用按钮文本设置函数（统一处理语言管理器）"""
        # 检查语言管理器是否存在
        if hasattr(self, 'language_manager') and self.language_manager:
            # 使用语言管理器翻译按钮文本
            button.setText(self.language_manager.tr(translation_key, default_text))
        else:
            # 如果没有语言管理器，使用默认文本
            button.setText(default_text)

    # 设置扫描按钮文本的方法（向后兼容）
    def _set_scan_button_text(self, translation_key, default_text):
        """设置扫描按钮文本（向后兼容）"""
        # 调用通用方法设置扫描按钮文本
        self._set_button_text(self.ui.main_window.scan_btn, translation_key, default_text)
    
    # 设置追加扫描按钮文本的方法（向后兼容）
    def _set_append_scan_button_text(self, translation_key, default_text):
        """设置追加扫描按钮文本（向后兼容）"""
        # 调用通用方法设置追加扫描按钮文本
        self._set_button_text(self.ui.main_window.append_scan_btn, translation_key, default_text)

    # 验证所有频道有效性的方法
    def _validate_all_channels(self, timeout: int, threads: int):
        """验证所有频道的有效性"""
        # 设置扫描器的超时时间
        self.scanner.timeout = timeout
        # 清除停止事件标志，准备开始验证
        self.scanner.stop_event.clear()
        
        # 初始化统计信息字典
        self.scanner.stats = {
            'total': self.ui.main_window.model.rowCount(),  # 总频道数
            'valid': 0,      # 有效频道数（初始为0）
            'invalid': 0,    # 无效频道数（初始为0）
            'start_time': time.time(),  # 开始时间戳
            'elapsed': 0     # 已用时间（初始为0）
        }
        
        # 填充任务队列：将所有频道的URL放入队列
        for i in range(self.ui.main_window.model.rowCount()):
            # 获取第i个频道的频道信息
            channel = self.ui.main_window.model.get_channel(i)
            # 将频道URL放入工作队列
            self.scanner.worker_queue.put(channel['url'])
            
        # 创建工作线程
        self.scanner.workers = []  # 初始化工作线程列表
        for i in range(threads):  # 根据指定的线程数创建线程
            # 创建验证工作线程
            worker = threading.Thread(
                target=self.scanner._worker,  # 线程执行扫描器的工作方法
                name=f"ValidatorWorker-{i}",   # 线程名称，方便调试
                daemon=True                    # 设置为守护线程，主线程退出时自动结束
            )
            worker.start()                     # 启动线程
            self.scanner.workers.append(worker)  # 将线程添加到列表
            
        # 启动统计更新线程
        stats_thread = threading.Thread(
            target=self.scanner._update_stats,  # 线程执行统计信息更新方法
            name="StatsUpdater",                # 线程名称
            daemon=True                         # 守护线程
        )
        stats_thread.start()  # 启动统计更新线程

    # 处理音量滑块值变化的方法
    def _on_volume_changed(self, value):
        """处理音量滑块变化"""
        # 调用播放器控制器的设置音量方法
        self.player_controller.set_volume(value)

    # 处理暂停/播放按钮点击的方法
    def _on_pause_clicked(self):
        """处理暂停/播放按钮点击"""
        # 如果没有频道正在播放，尝试播放选中的频道
        if not self.player_controller.is_playing:
            # 检查是否有选中的频道
            selected = self.ui.main_window.channel_list.selectedIndexes()
            if not selected:
                # 如果没有选中频道，显示提示并恢复按钮文本
                self.logger.warning("请先选择一个频道")
                self.ui.main_window.statusBar().showMessage("请先选择一个频道", 3000)
                # 恢复按钮文本为"播放"
                self._set_pause_button_text(False)
                return
                
            # 播放选中的频道
            self._play_selected_channel(selected[0])
        else:
            # 如果正在播放，执行暂停/播放操作
            self.player_controller.toggle_pause()  # 切换播放/暂停状态
            # 更新按钮文本
            self._set_pause_button_text(not self.player_controller.is_playing)

    # 处理停止按钮点击的方法
    def _on_stop_clicked(self):
        """处理停止按钮点击"""
        # 调用播放器控制器的停止方法
        self.player_controller.stop()
        # 将暂停按钮文本设置为播放状态
        self._set_pause_button_text(False)
        
    # 设置暂停/播放按钮文本的方法
    def _set_pause_button_text(self, is_playing):
        """设置暂停/播放按钮文本（使用通用函数）"""
        if is_playing:
            # 如果正在播放，设置为暂停文本
            self._set_button_text(self.ui.main_window.pause_btn, 'pause', '暂停')
        else:
            # 如果没有播放，设置为播放文本
            self._set_button_text(self.ui.main_window.pause_btn, 'play', '播放')

    # 处理播放状态变化的方法
    def _on_play_state_changed(self, is_playing):
        """处理播放状态变化"""
        self.logger.info(f"播放状态变化: is_playing={is_playing}")
        
        # 使用批量UI更新优化性能
        from ui_optimizer import batch_update
        
        def update_ui_state():
            # 更新停止按钮状态：只有正在播放时才启用
            self.ui.main_window.stop_btn.setEnabled(is_playing)
            # 根据播放状态设置停止按钮样式
            self.ui.main_window.stop_btn.setStyleSheet(
                AppStyles.button_style(active=is_playing)  # 使用应用程序样式
            )
            
            # 更新暂停/播放按钮文本
            self._set_pause_button_text(is_playing)
            
            # 强制刷新UI，确保按钮状态立即更新
            if hasattr(self.ui.main_window, 'pause_btn'):
                self.ui.main_window.pause_btn.repaint()
            if hasattr(self.ui.main_window, 'stop_btn'):
                self.ui.main_window.stop_btn.repaint()
                
            # 记录停止按钮状态
            self.logger.info(f"停止按钮启用状态: {self.ui.main_window.stop_btn.isEnabled()}")
        
        # 使用批量更新，避免频繁的UI重绘
        batch_update(update_ui_state)

    # 打开列表文件的方法
    def _open_list(self):
        """打开列表文件"""
        try:
            # 调用列表管理器的打开列表方法
            success, error_msg = self.list_manager.open_list(self)
                
            if success:
                # 成功打开后，禁用隐藏无效项按钮
                self.ui.main_window.btn_hide_invalid.setEnabled(False)
                # 启用有效性检测按钮
                self.ui.main_window.btn_validate.setEnabled(True)
                # 在状态栏显示成功消息3秒
                self.ui.main_window.statusBar().showMessage("列表加载成功", 3000)
                
                # 强制触发模型重置信号，刷新UI显示
                self.model.modelReset.emit()
                return True  # 返回成功标志
            else:
                # 打开失败时记录警告日志
                self.logger.warning(f"打开列表失败: {error_msg}")
                # 在状态栏显示错误消息3秒
                self.ui.main_window.statusBar().showMessage(f"打开列表失败: {error_msg}", 3000)
                return False  # 返回失败标志
        except Exception as e:
            # 捕获异常并处理
            error_msg = f"打开列表失败: {str(e)}"
            self.logger.error(error_msg, exc_info=True)  # 记录错误日志并包含堆栈信息
            self.ui.main_window.statusBar().showMessage(error_msg, 3000)  # 显示错误消息
            return False  # 返回失败标志

    # 保存列表文件的方法
    def _save_list(self):
        """保存列表文件"""
        try:
            # 调用列表管理器的保存列表方法
            result = self.list_manager.save_list(self)
            if result:
                # 保存成功时记录信息日志
                self.logger.info("列表保存成功")
                # 在状态栏显示成功消息3秒
                self.ui.main_window.statusBar().showMessage("列表保存成功", 3000)
                return True  # 返回成功标志
            else:
                # 保存失败时记录警告日志
                self.logger.warning("列表保存失败")
                # 在状态栏显示失败消息3秒
                self.ui.main_window.statusBar().showMessage("列表保存失败", 3000)
                return False  # 返回失败标志
                    
        except Exception as e:
            # 捕获异常并处理
            self.logger.error(f"保存列表失败: {e}", exc_info=True)  # 记录错误日志
            self.ui.main_window.statusBar().showMessage(f"保存列表失败: {str(e)}", 3000)  # 显示错误消息
            return False  # 返回失败标志

    # 处理有效性检测按钮点击事件的方法
    def _on_validate_clicked(self):
        """处理有效性检测按钮点击事件"""
        # 检查列表是否为空
        if not self.ui.main_window.model.rowCount():
            self.logger.warning("请先加载列表")
            return  # 返回，不执行验证
            
        # 检查是否正在验证
        if not hasattr(self.scanner, 'is_validating') or not self.scanner.is_validating:
            # 开始有效性检测
            timeout = self.ui.main_window.timeout_input.value()  # 获取超时时间
            threads = self.ui.main_window.thread_count_input.value()  # 获取线程数
            user_agent = self.ui.main_window.user_agent_input.text()  # 获取用户代理
            referer = self.ui.main_window.referer_input.text()  # 获取来源引用
            self.scanner.start_validation(
                self.ui.main_window.model,  # 传入频道模型
                threads,  # 线程数
                timeout,  # 超时时间
                user_agent,  # 用户代理
                referer  # 来源引用
            )
            # 设置验证按钮文本为"停止检测"
            self.ui.main_window.btn_validate.setText("停止检测")
            # 启用隐藏无效项按钮
            self.ui.main_window.btn_hide_invalid.setEnabled(True)
            # 设置隐藏无效项按钮样式为活动状态
            self.ui.main_window.btn_hide_invalid.setStyleSheet(
                AppStyles.button_style(active=True)
            )
            
            # 连接验证结果信号，用于接收频道验证结果
            self.scanner.channel_validated.connect(self._on_channel_validated)
        else:
            # 如果正在验证，则停止验证
            self.scanner.stop_validation()
            # 恢复验证按钮文本为"检测有效性"
            self.ui.main_window.btn_validate.setText("检测有效性")
            
    # 处理频道选择事件的方法
    def _on_channel_selected(self):
        """处理频道选择事件"""
        # 获取选中的索引
        selected = self.ui.main_window.channel_list.selectedIndexes()
        if not selected:  # 如果没有选中任何项
            return
            
        # 获取选中的行号
        row = selected[0].row()
        # 保存当前选中的频道索引
        self.current_channel_index = row

    # 处理频道验证结果的方法
    def _on_channel_validated(self, index, valid, latency, resolution):
        """处理频道验证结果"""
        # 使用模型的update_channel方法更新频道信息
        channel_info = {
            'valid': valid,  # 有效性标志
            'latency': latency,  # 延迟时间
            'resolution': resolution,  # 分辨率
            'status': '有效' if valid else '无效'  # 状态文本
        }
        
        # 更新模型中的频道信息
        self.ui.main_window.model.update_channel(index, channel_info)

    # 处理直接生成列表按钮点击事件的方法
    def _on_generate_clicked(self):
        """处理直接生成列表按钮点击事件"""
        # 获取输入地址
        url = self.ui.main_window.ip_range_input.text()
        if not url.strip():  # 检查地址是否为空
            self.logger.warning("请输入生成地址")
            self.ui.main_window.statusBar().showMessage("请输入生成地址", 3000)
            return  # 返回，不执行生成
            
        # 清空当前列表
        self.model.clear()
        
        # 使用URL解析器生成地址
        url_parser = URLRangeParser()  # 创建URL解析器实例
        url_generator = url_parser.parse_url(url)  # 解析URL并生成地址生成器
        
        # 添加生成的地址到列表
        count = 0  # 计数器
        for batch in url_generator:  # 遍历生成器返回的批次
            for url in batch:  # 遍历批次中的每个URL
                channel = {  # 创建频道字典
                    'name': f"生成频道-{count+1}",  # 频道名称
                    'group': "生成频道",  # 分组名称
                    'url': url,  # 频道URL
                    'valid': False,  # 有效性标志（默认无效）
                    'latency': 0,  # 延迟时间（默认0）
                    'status': '未检测'  # 状态（默认未检测）
                }
                self.model.add_channel(channel)  # 添加频道到模型
                count += 1  # 计数器加1
                
        # 在状态栏显示生成结果
        self.ui.main_window.statusBar().showMessage(f"已生成 {count} 个频道", 3000)

    # 处理隐藏无效项按钮点击事件的方法
    def _on_hide_invalid_clicked(self):
        """处理隐藏无效项按钮点击事件"""
        # 根据当前按钮文本判断要执行的操作
        if self.ui.main_window.btn_hide_invalid.text() == "隐藏无效项":
            # 调用模型的隐藏无效项方法
            self.ui.main_window.model.hide_invalid()
            # 更新按钮文本为"恢复隐藏项"
            self.ui.main_window.btn_hide_invalid.setText("恢复隐藏项")
        else:
            # 调用模型的显示所有项方法
            self.ui.main_window.model.show_all()
            # 更新按钮文本为"隐藏无效项"
            self.ui.main_window.btn_hide_invalid.setText("隐藏无效项")

    # 播放选中频道的方法
    def _play_selected_channel(self, index):
        """播放选中的频道"""
        if not index.isValid():  # 检查索引是否有效
            return
            
        # 获取选中频道的频道信息
        channel = self.ui.main_window.model.get_channel(index.row())
        if not channel or not channel.get('url'):  # 检查频道或URL是否存在
            return
            
        # 检查播放器控制器是否存在
        if not hasattr(self, 'player_controller') or not self.player_controller:
            # 如果不存在，导入并创建播放器控制器
            from player_controller import PlayerController
            self.player_controller = PlayerController(
                self.ui.main_window.player,  # 播放器对象
                self.model  # 频道模型
            )
            
        # 保存当前选中的频道索引
        self.current_channel_index = index.row()
            
        # 播放选中的频道
        if self.player_controller.play_channel(channel, self.current_channel_index):
            # 使用语言管理器设置暂停按钮文本
            if hasattr(self, 'language_manager') and self.language_manager:
                self.ui.main_window.pause_btn.setText(
                    self.language_manager.tr('pause', 'Pause')  # 翻译"暂停"
                )
            else:
                # 如果没有语言管理器，使用默认文本
                self.ui.main_window.pause_btn.setText("暂停")
            # 保存当前频道信息
            self.current_channel = channel

    # 处理发现有效频道事件的方法（PyQt槽函数）
    @QtCore.pyqtSlot(dict)
    def _on_channel_found(self, channel_info):
        """处理发现有效频道事件"""
        # 添加发现的频道到模型
        self.ui.main_window.model.add_channel(channel_info)
        
        # 添加频道后强制触发列宽调整
        if hasattr(self.ui.main_window, 'channel_list'):
            header = self.ui.main_window.channel_list.horizontalHeader()  # 获取表头
            from PyQt6.QtCore import QTimer
            from PyQt6.QtWidgets import QHeaderView
            # 延迟执行列宽调整，确保UI已更新
            QTimer.singleShot(0, lambda: header.resizeSections(QHeaderView.ResizeMode.ResizeToContents))

    # 处理扫描完成事件的方法
    def _on_scan_completed(self):
        """处理扫描完成事件"""
        # 重置扫描按钮文本
        self._set_scan_button_text('full_scan', '完整扫描')
        self._set_append_scan_button_text('append_scan', '追加扫描')
        # 重置验证按钮文本
        self.ui.main_window.btn_validate.setText("检测有效性")
        self.logger.info("扫描完成")  # 记录信息日志
        
        # 启用智能排序按钮
        self.ui.main_window.btn_smart_sort.setEnabled(True)
        self.ui.main_window.btn_smart_sort.setStyleSheet(
            AppStyles.button_style(active=True)  # 设置活动样式
        )
        
        # 扫描完成后调整列宽
        if hasattr(self.ui.main_window, 'channel_list'):
            header = self.ui.main_window.channel_list.horizontalHeader()
            header.resizeSections(QtWidgets.QHeaderView.ResizeMode.ResizeToContents)  # 根据内容调整列宽
        
        # 扫描完成后加载网络Logo
        self.logger.info("扫描完成，开始加载网络Logo")
        # 延迟100毫秒后加载网络Logo
        QtCore.QTimer.singleShot(100, self.ui._load_network_logos)
        
        # 检查是否需要重试扫描
        if hasattr(self.ui.main_window, 'enable_retry_checkbox') and self.ui.main_window.enable_retry_checkbox.isChecked():
            self._start_retry_scan()  # 开始重试扫描

    # 更新统计信息显示的方法（PyQt槽函数）
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
            stats = stats_data.get('stats', stats_data)  # 获取统计信息字典
            # 将秒数格式化为HH:MM:SS时间格式
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
                # 如果没有语言管理器，使用默认文本
                stats_text = (
                    f"总数: {stats.get('total', 0)} | "
                    f"有效: {stats.get('valid', 0)} | "
                    f"无效: {stats.get('invalid', 0)} | "
                    f"耗时: {elapsed}"
                )
                self.ui.main_window.stats_label.setText(stats_text)
        except Exception as e:
            # 捕获异常并记录错误日志
            self.logger.error(f"更新统计信息显示失败: {e}", exc_info=True)

    # 处理关于按钮点击事件的方法
    def _on_about_clicked(self):
        """处理关于按钮点击事件"""
        try:
            from about_dialog import AboutDialog  # 导入关于对话框
            
            # 确保在主线程中创建对话框
            dialog = AboutDialog(self)
            # 设置对话框为应用程序模态（阻止与其他窗口交互）
            dialog.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)
            
            # 确保事件循环正确处理
            def show_dialog():
                try:
                    dialog.show()  # 显示对话框
                    # 立即更新UI文本到当前语言
                    if hasattr(dialog, 'update_ui_texts'):
                        dialog.update_ui_texts()
                except Exception as e:
                    self.logger.error(f"显示对话框出错: {e}")
            
            # 使用定时器确保UI更新
            QtCore.QTimer.singleShot(0, show_dialog)
            
        except ImportError as e:
            # 导入失败时处理
            self.logger.error(f"导入AboutDialog失败: {e}")
            # 使用统一的错误处理
            show_error("错误", "无法加载关于对话框模块", parent=self)
        except Exception as e:
            # 其他异常处理
            self.logger.error(f"显示关于对话框失败: {e}")
            # 使用统一的错误处理
            show_error("错误", f"无法显示关于对话框: {str(e)}", parent=self)
            
    # 处理映射管理按钮点击事件的方法
    def _on_mapping_clicked(self):
        """处理映射管理按钮点击事件"""
        try:
            from mapping_manager_dialog import MappingManagerDialog  # 导入映射管理器对话框
            
            # 确保在主线程中创建对话框
            dialog = MappingManagerDialog(self)
            # 设置对话框为应用程序模态
            dialog.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)
            
            # 确保事件循环正确处理
            def show_dialog():
                try:
                    dialog.exec()  # 以模态方式显示对话框
                except Exception as e:
                    self.logger.error(f"显示映射管理器出错: {e}")
            
            # 使用定时器确保UI更新
            QtCore.QTimer.singleShot(0, show_dialog)
            
        except ImportError as e:
            # 导入失败时处理
            self.logger.error(f"导入MappingManagerDialog失败: {e}")
            # 使用统一的错误处理
            show_error("错误", "无法加载映射管理器模块", parent=self)
        except Exception as e:
            # 其他异常处理
            self.logger.error(f"显示映射管理器失败: {e}")
            # 使用统一的错误处理
            show_error("错误", f"无法显示映射管理器: {str(e)}", parent=self)
            
    # 包装方法：在主线程中调用 _finish_refresh_channel（PyQt槽函数）
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

    # 在后台线程执行的初始化任务
    def init_background_tasks(self):
        """在后台线程执行的初始化任务"""
        # 注意：_load_config() 已在 _init_main_window() 中调用，此处不再重复调用
        
        # 加载保存的语言设置
        language_code = self.config.load_language_settings()
        # 设置语言并更新UI文本
        if hasattr(self, 'language_manager') and self.language_manager.set_language(language_code):
            self.language_manager.update_ui_texts(self)

    # 开始重试扫描的方法
    def _start_retry_scan(self):
        """开始重试扫描 - 对第一次扫描中失效的URL进行再次扫描"""
        try:
            # 获取第一次扫描的所有URL（从扫描器统计信息中获取）
            if not hasattr(self.scanner, '_all_scanned_urls') or not self.scanner._all_scanned_urls:
                self.logger.info("没有找到第一次扫描的URL记录，无法进行重试扫描")
                self.ui.main_window.statusBar().showMessage("没有找到第一次扫描的URL记录，无法进行重试扫描", 3000)
                return
            
            # 获取当前频道列表中所有有效频道的URL
            valid_urls = set()  # 使用集合去重
            for i in range(self.model.rowCount()):
                channel = self.model.get_channel(i)
                if channel.get('valid', False):  # 检查频道是否有效
                    valid_urls.add(channel['url'])  # 添加到有效URL集合
            
            # 计算需要重试扫描的URL（第一次扫描的所有URL中，不在有效频道列表中的）
            all_scanned_urls = set(self.scanner._all_scanned_urls)
            invalid_urls = list(all_scanned_urls - valid_urls)  # 计算差集
            
            if not invalid_urls:
                self.logger.info("没有需要重试扫描的失效URL")
                self.ui.main_window.statusBar().showMessage("没有需要重试扫描的失效URL", 3000)
                return
            
            self.logger.info(f"开始重试扫描，共 {len(invalid_urls)} 个失效URL")
            self.ui.main_window.statusBar().showMessage(f"开始重试扫描，共 {len(invalid_urls)} 个失效URL")
            
            # 设置重试扫描状态
            self._retry_scan_count = 0  # 重试轮次计数器
            self._retry_found_channels = 0  # 发现的有效频道计数器
            self._retry_urls = invalid_urls.copy()  # 复制需要重试的URL列表
            # 检查是否启用循环扫描
            self._retry_loop_enabled = hasattr(self.ui.main_window, 'loop_scan_checkbox') and self.ui.main_window.loop_scan_checkbox.isChecked()
            
            # 开始重试扫描
            self._do_retry_scan()
            
        except Exception as e:
            # 捕获异常并处理
            self.logger.error(f"开始重试扫描失败: {e}", exc_info=True)
            self.ui.main_window.statusBar().showMessage(f"重试扫描失败: {str(e)}", 3000)
    
    # 执行重试扫描的方法
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
    
    # 处理重试扫描中发现频道的方法（信号槽）
    def _on_retry_channel_found(self, channel_info):
        """处理重试扫描中发现的频道"""
        self._retry_found_channels += 1  # 增加发现计数
        self.logger.info(f"重试扫描发现有效频道: {channel_info['name']}")
        
        # 从重试列表中移除这个URL（避免重复扫描）
        if hasattr(self, '_retry_urls') and channel_info['url'] in self._retry_urls:
            self._retry_urls.remove(channel_info['url'])
        
        # 更新主统计信息中的有效频道计数
        if hasattr(self.scanner, 'stats'):
            with self.scanner.stats_lock:  # 使用锁确保线程安全
                self.scanner.stats['valid'] += 1  # 增加有效计数
                # 更新统计显示
                self._update_stats_display({'stats': self.scanner.stats})
    
    # 处理重试扫描完成的方法
    def _on_retry_scan_completed(self, temp_scanner):
        """处理重试扫描完成"""
        try:
            # 清理临时扫描器
            temp_scanner.stop_scan()
            
            # 检查是否需要继续循环扫描
            if (self._retry_loop_enabled and  # 循环扫描启用
                hasattr(self, '_retry_found_channels') and  # 发现计数存在
                self._retry_found_channels > 0 and  # 本轮发现有效频道
                hasattr(self, '_retry_urls') and  # 重试URL列表存在
                self._retry_urls):  # 还有URL需要重试
                
                current_found = self._retry_found_channels
                # 重置发现计数，继续下一轮扫描
                self._retry_found_channels = 0
                self.logger.info(f"循环扫描：第 {self._retry_scan_count} 轮发现 {current_found} 个频道，继续扫描")
                self.ui.main_window.statusBar().showMessage(f"循环扫描：第 {self._retry_scan_count} 轮发现 {current_found} 个频道，继续第 {self._retry_scan_count + 1} 轮", 3000)
                
                # 延迟1秒后继续扫描（给UI更新时间）
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
            # 捕获异常并处理
            self.logger.error(f"处理重试扫描完成失败: {e}", exc_info=True)
            self.ui.main_window.statusBar().showMessage("重试扫描完成处理失败", 3000)
            # 恢复两个扫描按钮的文本
            self._set_scan_button_text('full_scan', '完整扫描')
            self._set_append_scan_button_text('append_scan', '追加扫描')

    # 程序退出前保存所有配置的方法
    def save_before_exit(self):
        """程序退出前保存所有配置"""
        try:
            # 保存窗口布局
            size = self.size()  # 获取窗口大小
            dividers = [  # 获取分割器位置
                *self.ui.main_window.main_splitter.sizes(),
                *self.ui.main_window.left_splitter.sizes(),
            ]
            self.config.save_window_layout(size.width(), size.height(), dividers)
            
            # 保存网络设置
            self.config.save_network_settings(
                self.ui.main_window.ip_range_input.text(),  # IP范围
                self.ui.main_window.timeout_input.value(),  # 超时时间
                self.ui.main_window.thread_count_input.value(),  # 线程数
                self.ui.main_window.user_agent_input.text(),  # 用户代理
                self.ui.main_window.referer_input.text()  # 来源引用
            )
            
            # 保存语言设置
            if hasattr(self, 'language_manager'):
                self.config.save_language_settings(self.language_manager.current_language)
                
            self.logger.info("程序退出前配置已保存")
        except Exception as e:
            self.logger.error(f"保存退出配置失败: {e}")

    # 重写窗口关闭事件的方法
    def closeEvent(self, event):
        """重写窗口关闭事件，确保资源正确清理"""
        self._cleanup_resources()  # 清理资源
        event.accept()  # 接受关闭事件

    # 清理所有资源的方法
    def _cleanup_resources(self):
        """清理所有资源"""
        self.logger.info("开始清理程序资源...")
        
        # 使用全局资源清理器
        cleanup_all()  # 调用全局清理函数
        
        self.logger.info("所有资源已清理")
    
    # 注册资源清理处理器的方法
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

# 主函数，应用程序入口点
def main():
    # 创建QApplication实例，传入命令行参数
    app = QtWidgets.QApplication(sys.argv)
    
    # 设置应用程序字体，避免Fixedsys字体缺失警告
    font_family = "Microsoft YaHei"  # 微软雅黑字体
    font = QtGui.QFont(font_family)
    font.setPointSize(9)  # 设置字体大小
    app.setFont(font)  # 设置应用程序字体
    # 设置应用程序样式表，确保所有控件使用统一字体
    app.setStyleSheet(f"""
        QWidget {{
            font-family: "{font_family}";
            font-size: 9pt;
        }}
    """)

    # 直接创建并显示主窗口，去掉启动动画
    try:
        window = MainWindow()  # 创建主窗口实例
        window.show()  # 显示主窗口
        app.main_window = window  # 将主窗口保存到应用程序属性中
    except Exception as e:
        # 创建主窗口失败时记录错误并退出应用程序
        global_logger.error(f"创建主窗口失败: {e}")
        QtWidgets.QApplication.instance().quit()

    # 清理函数，在应用程序退出前调用
    def cleanup():
        if hasattr(app, 'main_window'):
            app.main_window.save_before_exit()  # 保存退出前配置
    # 连接应用程序退出信号到清理函数
    app.aboutToQuit.connect(cleanup)

    # 启动应用程序事件循环
    sys.exit(app.exec())

# Python标准入口点
if __name__ == "__main__":
    main()  # 调用主函数
