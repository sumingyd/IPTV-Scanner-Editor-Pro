"""
core/event_bus.py - 共先有控制目标，规则其他控制
"""
from PySide6.QtCore import QObject, Signal


class EventBus(QObject):
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "_initialized"):
            super().__init__()
            self._initialized = True

    play_requested = Signal(object)
    stop_requested = Signal()
    pause_requested = Signal()
    volume_changed = Signal(int)
    mute_toggled = Signal(bool)
    playback_position_updated = Signal(float, float, float)

    channel_selected = Signal(object)
    channel_list_updated = Signal()
    channel_switched = Signal(object, object)

    epg_loaded = Signal(str, list)
    epg_refresh_requested = Signal()

    catchup_started = Signal(object)
    catchup_ended = Signal()
    timeshift_started = Signal(int)

    mode_switched = Signal(str)
    fullscreen_toggled = Signal(bool)
    panel_visibility_changed = Signal(str, bool)

    node_service_ready = Signal(str)
    node_service_error = Signal(str)
