from PyQt6.QtCore import pyqtSlot
from async_utils import AsyncWorker

class SignalConnector:
    def __init__(self, main_window):
        self.main_window = main_window

    def connect_signals(self):
        """连接所有信号与槽"""
        # 扫描器信号
        self.main_window.scanner.progress_updated.connect(self.main_window.update_progress)
        self.main_window.scanner.scan_finished.connect(self.main_window.handle_scan_results)
        self.main_window.scanner.channel_found.connect(self.main_window.handle_channel_found)
        self.main_window.scanner.error_occurred.connect(self.main_window.show_error)
        
        # 列表选择信号
        self.main_window.channel_list.selectionModel().currentChanged.connect(
            self.main_window.on_channel_selected)
            
        # 播放器信号
        self.main_window.player.state_changed.connect(self.main_window._handle_player_state)
        
        # 验证器信号
        self.main_window.validator.progress_updated.connect(self.main_window.validator.update_progress)
        self.main_window.validator.validation_finished.connect(
            self.main_window.validator.handle_validation_complete)
        self.main_window.validator.error_occurred.connect(self.main_window.show_error)
        self.main_window.validator.channel_validated.connect(
            self.main_window.validator.handle_channel_validation)
