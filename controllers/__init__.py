import importlib as _importlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .catchup_controller import CatchupController
    from .channel_controller import ChannelController
    from .epg_controller import EPGController
    from .epg_reminder_controller import EpgReminderController
    from .event_handler import EventHandler
    from .favorites_controller import FavoritesController
    from .media_controller import MediaController
    from .pip_controller import PipController
    from .playback_controller import PlaybackController
    from .settings_file_ops import SettingsFileOperations
    from .subscription_controller import SubscriptionController
    from .subscription_ui_controller import SubscriptionUIController
    from .ui_controller import UIController
    from .update_controller import UpdateController
    from .window_controller import WindowController

_CONTROLLER_MODULES = {
    'WindowController': '.window_controller',
    'PlaybackController': '.playback_controller',
    'EPGController': '.epg_controller',
    'ChannelController': '.channel_controller',
    'SettingsFileOperations': '.settings_file_ops',
    'EventHandler': '.event_handler',
    'UIController': '.ui_controller',
    'SubscriptionController': '.subscription_controller',
    'SubscriptionUIController': '.subscription_ui_controller',
    'CatchupController': '.catchup_controller',
    'PipController': '.pip_controller',
    'MediaController': '.media_controller',
    'UpdateController': '.update_controller',
    'FavoritesController': '.favorites_controller',
    'EpgReminderController': '.epg_reminder_controller',
}


def __getattr__(name):
    if name in _CONTROLLER_MODULES:
        module = _importlib.import_module(_CONTROLLER_MODULES[name], __name__)
        cls = getattr(module, name)
        globals()[name] = cls
        return cls
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    'WindowController',
    'PlaybackController',
    'EPGController',
    'ChannelController',
    'SettingsFileOperations',
    'EventHandler',
    'UIController',
    'SubscriptionController',
    'SubscriptionUIController',
    'CatchupController',
    'PipController',
    'MediaController',
    'UpdateController',
    'FavoritesController',
    'EpgReminderController',
]

assert set(__all__) == set(_CONTROLLER_MODULES), "__all__ 与 _CONTROLLER_MODULES 不同步"
