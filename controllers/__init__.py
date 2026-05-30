import importlib as _importlib

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
}


def __getattr__(name):
    if name in _CONTROLLER_MODULES:
        module = _importlib.import_module(_CONTROLLER_MODULES[name], __name__)
        cls = getattr(module, name)
        globals()[name] = cls
        return cls
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = list(_CONTROLLER_MODULES.keys())
