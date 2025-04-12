from PyQt6.QtCore import pyqtSignal, pyqtSlot, QObject
from async_utils import AsyncWorker

class AppSignals(QObject):
    """应用全局信号定义"""
    scan_started = pyqtSignal()
    scan_finished = pyqtSignal(list)
    validation_started = pyqtSignal() 
    validation_finished = pyqtSignal(dict)
    epg_update_started = pyqtSignal()
    epg_update_finished = pyqtSignal()
    player_state_changed = pyqtSignal(str)
    channel_selected = pyqtSignal(object)

class SignalConnector:
    def __init__(self, main_window):
        self.main_window = main_window

    def connect_signals(self):
        """连接所有信号与槽"""
        # 扫描器信号
        self.main_window.scanner.progress_updated.connect(
            lambda p, msg: (
                self.main_window.ui_builder.ui_manager.update_progress(self.main_window.scan_progress, p),
                self.main_window.ui_builder.ui_manager.update_status(msg)
            )
        )
        self.main_window.scanner.scan_finished.connect(self.main_window.handle_scan_results)
        self.main_window.scanner.channel_found.connect(self.main_window.handle_channel_found)
        self.main_window.scanner.error_occurred.connect(self.main_window.show_error)
        self.main_window.scanner.scan_stopped.connect(self.main_window._on_scan_stopped)
        self.main_window.scanner.scan_started.connect(
            lambda ip: (
                self.main_window.ui_builder.ui_manager.update_button_state(self.main_window.scan_btn, "停止扫描", True),
                self.main_window.ui_builder.ui_manager.update_status(f"开始扫描: {ip}")
            )
        )
        self.main_window.scanner.stats_updated.connect(
            lambda stats: self.main_window.ui_builder.ui_manager.update_status(stats)
        )
        
        # 列表选择信号
        self.main_window.channel_list.selectionModel().currentChanged.connect(
            self.main_window.on_channel_selected)
            
        # 播放器信号
        self.main_window.player.signals.player_state_changed.connect(self.main_window._handle_player_state)
        
        # 验证器信号
        self.main_window.validator.progress_updated.connect(self.main_window.validator.update_progress)
        self.main_window.validator.validation_finished.connect(
            self.main_window.validator.handle_validation_complete)
        self.main_window.validator.error_occurred.connect(self.main_window.show_error)
        self.main_window.validator.channel_validated.connect(
            self.main_window.validator.handle_channel_validation)
