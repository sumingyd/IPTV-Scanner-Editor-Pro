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
    player_state_changed = pyqtSignal(int)
    channel_selected = pyqtSignal(object)

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
