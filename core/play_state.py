import threading
from enum import Enum, auto
from typing import Optional, Callable
from core.log_manager import global_logger as logger


class PlayMode(Enum):
    IDLE = auto()
    LIVE = auto()
    CATCHUP = auto()
    TIMESHIFT = auto()


class PlayStateManager:
    def __init__(self):
        self._mode = PlayMode.IDLE
        self._lock = threading.Lock()
        self._listeners = []

    @property
    def mode(self) -> PlayMode:
        with self._lock:
            return self._mode

    @mode.setter
    def mode(self, value: PlayMode):
        with self._lock:
            old = self._mode
            self._mode = value
        if old != value:
            logger.debug(f"播放模式变更: {old.name} -> {value.name}")
            self._notify(old, value)

    @property
    def is_idle(self) -> bool:
        with self._lock:
            return self._mode == PlayMode.IDLE

    @property
    def is_live(self) -> bool:
        with self._lock:
            return self._mode == PlayMode.LIVE

    @property
    def is_catchup(self) -> bool:
        with self._lock:
            return self._mode == PlayMode.CATCHUP

    @property
    def is_timeshift(self) -> bool:
        with self._lock:
            return self._mode == PlayMode.TIMESHIFT

    @property
    def is_playing(self) -> bool:
        with self._lock:
            return self._mode in (PlayMode.LIVE, PlayMode.CATCHUP, PlayMode.TIMESHIFT)

    @property
    def is_catchup_or_timeshift(self) -> bool:
        with self._lock:
            return self._mode in (PlayMode.CATCHUP, PlayMode.TIMESHIFT)

    def set_idle(self):
        self.mode = PlayMode.IDLE

    def set_live(self):
        self.mode = PlayMode.LIVE

    def set_catchup(self):
        self.mode = PlayMode.CATCHUP

    def set_timeshift(self):
        self.mode = PlayMode.TIMESHIFT

    def add_listener(self, callback: Callable[[PlayMode, PlayMode], None]):
        with self._lock:
            self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[PlayMode, PlayMode], None]):
        with self._lock:
            if callback in self._listeners:
                self._listeners.remove(callback)

    def _notify(self, old_mode: PlayMode, new_mode: PlayMode):
        with self._lock:
            listeners = list(self._listeners)
        for callback in listeners:
            try:
                callback(old_mode, new_mode)
            except Exception as e:
                logger.error(f"播放状态监听器回调异常: {e}")
