import sys
import os
import pytest
from unittest.mock import MagicMock, patch, PropertyMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mixins.server_mixin import ServerMixin
from mixins.tray_mixin import TrayMixin
from mixins.update_mixin import UpdateMixin
from mixins.thumbnail_mixin import ThumbnailMixin
from tests.conftest import MockMainWindow


class _ServerTestHost(MockMainWindow, ServerMixin):
    pass


class _TrayTestHost(MockMainWindow, TrayMixin):
    pass


class _UpdateTestHost(MockMainWindow, UpdateMixin):
    pass


class _ThumbnailTestHost(MockMainWindow, ThumbnailMixin):
    pass


class TestServerMixin:
    def setup_method(self):
        self.host = _ServerTestHost()

    @patch('mixins.server_mixin.logger')
    def test_auto_start_server_disabled(self, mock_logger):
        self.host.config.load_server_settings.return_value = {'auto_start': False}
        with patch('server.app.set_main_window') as mock_set, \
             patch('server.app.start_server') as mock_start:
            self.host._auto_start_server()
            mock_set.assert_called_once_with(self.host)
            mock_start.assert_not_called()

    @patch('mixins.server_mixin.logger')
    def test_auto_start_server_enabled(self, mock_logger):
        self.host.config.load_server_settings.return_value = {
            'auto_start': True, 'port': 9090, 'host': '0.0.0.0'
        }
        mock_server = MagicMock()
        mock_server.is_running.return_value = True
        with patch('server.app.set_main_window'), \
             patch('server.app.start_server') as mock_start, \
             patch('server.app.get_server', return_value=mock_server):
            self.host._auto_start_server()
            mock_start.assert_called_once_with(host='0.0.0.0', port=9090)

    @patch('mixins.server_mixin.logger')
    def test_auto_start_server_exception(self, mock_logger):
        self.host.config.load_server_settings.side_effect = Exception("test error")
        self.host._auto_start_server()
        mock_logger.error.assert_called_once()

    @patch('mixins.server_mixin.logger')
    def test_toggle_server_running(self, mock_logger):
        mock_server = MagicMock()
        mock_server.is_running.return_value = True
        with patch('server.app.set_main_window'), \
             patch('server.app.get_server', return_value=mock_server), \
             patch('server.app.stop_server') as mock_stop:
            self.host._toggle_server()
            mock_stop.assert_called_once()
            self.host._server_action.setText.assert_called_once()

    @patch('mixins.server_mixin.logger')
    def test_toggle_server_not_running(self, mock_logger):
        mock_server = MagicMock()
        mock_server.is_running.return_value = False
        self.host.config.load_server_settings.return_value = {
            'port': 8080, 'host': '0.0.0.0'
        }
        with patch('server.app.set_main_window'), \
             patch('server.app.get_server', return_value=mock_server), \
             patch('server.app.start_server') as mock_start:
            self.host._toggle_server()
            mock_start.assert_called_once()

    @patch('mixins.server_mixin.logger')
    def test_open_server_api(self, mock_logger):
        mock_server = MagicMock()
        mock_server.port = 8080
        mock_server.is_running.return_value = True
        with patch('server.app.get_server', return_value=mock_server), \
             patch('webbrowser.open') as mock_open:
            self.host._open_server_api()
            mock_open.assert_called_once_with('http://localhost:8080/')

    @patch('mixins.server_mixin.logger')
    def test_open_server_api_exception(self, mock_logger):
        with patch('server.app.get_server', side_effect=Exception("test")):
            self.host._open_server_api()
            mock_logger.error.assert_called_once()


class TestTrayMixin:
    def setup_method(self):
        self.host = _TrayTestHost()

    def test_tray_show_window(self):
        self.host._is_hidden_to_tray = True
        self.host._tray_hidden_docks = []
        with patch.object(self.host, 'show'), \
             patch.object(self.host, 'activateWindow'), \
             patch.object(self.host, 'raise_'):
            self.host._tray_show_window()
            assert self.host._is_hidden_to_tray is False

    def test_tray_quit(self):
        self.host._is_hidden_to_tray = True
        with patch.object(self.host, 'close'):
            self.host._tray_quit()
            assert self.host._force_quit is True
            assert self.host._is_hidden_to_tray is False

    def test_do_close_minimize_tray_not_playing(self):
        self.host.player_controller.is_playing = False
        self.host._tray_hidden_docks = []
        with patch.object(self.host, 'hide'):
            self.host._do_close_minimize_tray()
            assert self.host._is_hidden_to_tray is True
            assert self.host._was_playing_before_tray is False

    def test_do_close_minimize_tray_playing(self):
        self.host.player_controller.is_playing = True
        self.host.player_controller.is_paused = False
        self.host._tray_hidden_docks = []
        with patch.object(self.host, 'hide'):
            self.host._do_close_minimize_tray()
            assert self.host._was_playing_before_tray is True

    def test_do_close_minimize_tray_hides_docks(self):
        self.host.player_controller.is_playing = False
        mock_dock = MagicMock()
        mock_dock.isVisible.return_value = True
        self.host.epg_dock = mock_dock
        self.host.playlist_dock = MagicMock()
        self.host.playlist_dock.isVisible.return_value = False
        self.host.floating_dock = MagicMock()
        self.host.floating_dock.isVisible.return_value = False
        with patch.object(self.host, 'hide'):
            self.host._do_close_minimize_tray()
            assert 'epg_dock' in self.host._tray_hidden_docks
            assert len(self.host._tray_hidden_docks) == 1


class TestUpdateMixin:
    def setup_method(self):
        self.host = _UpdateTestHost()

    def test_do_check_for_updates_async(self):
        self.host._do_check_for_updates_async()
        self.host.update_ctrl.check_for_updates.assert_called_once()

    def test_on_update_found(self):
        self.host._on_update_found('1.2.0', '1.1.0')
        self.host.update_ctrl._on_update_found.assert_called_once_with('1.2.0', '1.1.0')

    def test_on_update_check_completed(self):
        self.host._on_update_check_completed(True, 'OK')
        self.host.update_ctrl._on_update_check_completed.assert_called_once_with(True, 'OK')


class TestThumbnailMixin:
    def setup_method(self):
        self.host = _ThumbnailTestHost()

    def test_on_logo_cache_loaded_delegates(self):
        self.host._on_logo_cache_loaded('http://x.com/logo.png', MagicMock())
        self.host.ui_ctrl._on_logo_cache_loaded.assert_called_once()

    def test_on_thumbnail_ready_calls_update(self):
        with patch.object(self.host, '_update_grid_thumbnail') as mock_update:
            self.host._on_thumbnail_ready('ch1', 'http://x.com/stream.m3u8')
            mock_update.assert_called_once_with('http://x.com/stream.m3u8')

    def test_on_player_thumbnail_captured_calls_update(self):
        with patch.object(self.host, '_update_grid_thumbnail') as mock_update:
            self.host._on_player_thumbnail_captured('http://x.com/stream.m3u8')
            mock_update.assert_called_once_with('http://x.com/stream.m3u8')

    @patch('services.thumbnail_service.get_thumbnail_path', return_value=None)
    def test_update_grid_thumbnail_no_path(self, mock_get_path):
        self.host._update_grid_thumbnail('http://x.com/stream.m3u8')
        mock_get_path.assert_called_once_with('http://x.com/stream.m3u8')

    @patch('mixins.thumbnail_mixin.QIcon')
    @patch('mixins.thumbnail_mixin.QPixmap')
    @patch('services.thumbnail_service.get_thumbnail_path', return_value='/tmp/thumb.jpg')
    def test_update_grid_thumbnail_with_match(self, mock_get_path, mock_pixmap_cls, mock_qicon):
        from PySide6.QtWidgets import QListWidget
        mock_item = MagicMock()
        mock_item.data.return_value = 0
        mock_list = MagicMock()
        mock_list.viewMode.return_value = QListWidget.ViewMode.IconMode
        mock_list.item.return_value = mock_item
        self.host.sub_channel_list = mock_list
        self.host._sub_channels = [{'url': 'http://x.com/stream.m3u8', 'name': 'ch1'}]
        self.host.local_channel_list = MagicMock()
        self.host.local_channel_list.viewMode.return_value = 0
        self.host._local_channels = []

        mock_px = MagicMock()
        mock_px.isNull.return_value = False
        mock_scaled = MagicMock()
        mock_px.scaled.return_value = mock_scaled
        mock_pixmap_cls.return_value = mock_px

        self.host._update_grid_thumbnail('http://x.com/stream.m3u8')
        mock_item.setIcon.assert_called_once()