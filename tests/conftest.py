import sys
import os
import pytest
from unittest.mock import MagicMock, patch, PropertyMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class MockMainWindow:
    """模拟 MainWindowProtocol 的最小实现，用于 Mixin 单元测试"""

    def __init__(self):
        self.config = MagicMock()
        self.language_manager = MagicMock()
        self.language_manager.tr = lambda key, default='': default
        self.status_bar = MagicMock()
        self._server_action = MagicMock()
        self._system_tray = MagicMock()
        self._is_hidden_to_tray = False
        self._was_playing_before_tray = False
        self._tray_hidden_docks = []
        self._force_quit = False
        self.player_controller = MagicMock()
        self.player_controller.is_playing = False
        self.player_controller.is_paused = False
        self.update_ctrl = MagicMock()
        self.ui_ctrl = MagicMock()
        self.sub_channel_list = MagicMock()
        self.local_channel_list = MagicMock()
        self._sub_channels = []
        self._local_channels = []
        self.play_state = MagicMock()
        self.play_state.is_catchup_or_timeshift = False
        self.event_handler = MagicMock()
        self.config_manager = MagicMock()

    def status_bar_show_message(self, message, timeout=0):
        if self.status_bar:
            self.status_bar.showMessage(message, timeout)

    def show(self):
        pass

    def hide(self):
        pass

    def activateWindow(self):
        pass

    def raise_(self):
        pass

    def close(self):
        pass

    def setAttribute(self, *args, **kwargs):
        pass


@pytest.fixture
def mock_main_window():
    return MockMainWindow()