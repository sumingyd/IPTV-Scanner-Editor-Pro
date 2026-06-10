import threading
from enum import Enum, auto
from typing import Dict, Optional, Callable
from core.log_manager import global_logger as logger


class AutoHideState(Enum):
    VISIBLE = auto()
    AUTO_HIDDEN = auto()


class PanelVisibilityManager:

    PANELS = ('epg', 'playlist', 'floating')

    def __init__(self, window):
        self._window = window
        self._visible: Dict[str, bool] = {p: True for p in self.PANELS}
        self._manually_hidden = False
        self._auto_hide_state = AutoHideState.VISIBLE
        self._saved_states: Dict[str, Dict[str, bool]] = {}
        self._auto_hide_saved: Dict[str, bool] = {}
        self._lock = threading.RLock()
        self._listeners = []

    @property
    def epg_visible(self) -> bool:
        with self._lock:
            return self._visible['epg']

    @property
    def playlist_visible(self) -> bool:
        with self._lock:
            return self._visible['playlist']

    @property
    def floating_visible(self) -> bool:
        with self._lock:
            return self._visible['floating']

    @property
    def manually_hidden(self) -> bool:
        with self._lock:
            return self._manually_hidden

    @property
    def auto_hide_state(self) -> AutoHideState:
        with self._lock:
            return self._auto_hide_state

    @property
    def is_auto_hide_visible(self) -> bool:
        with self._lock:
            return self._auto_hide_state == AutoHideState.VISIBLE

    @property
    def is_auto_hidden(self) -> bool:
        with self._lock:
            return self._auto_hide_state == AutoHideState.AUTO_HIDDEN

    def get_visible(self, panel: str) -> bool:
        with self._lock:
            return self._visible.get(panel, False)

    def set_visible(self, panel: str, visible: bool):
        with self._lock:
            old = self._visible.get(panel, False)
            self._visible[panel] = visible
        if old != visible:
            self._apply_panel(panel, visible)
            self._notify(panel, visible)

    def toggle(self, panel: str) -> bool:
        with self._lock:
            new_val = not self._visible.get(panel, False)
        self.set_visible(panel, new_val)
        return new_val

    def save_context(self, context: str) -> Dict[str, bool]:
        with self._lock:
            state = {
                'epg': self._visible['epg'],
                'playlist': self._visible['playlist'],
                'floating': self._visible['floating'],
                'manually_hidden': self._manually_hidden,
            }
        extra = self._collect_extra_context(context)
        state.update(extra)
        with self._lock:
            self._saved_states[context] = dict(state)
        logger.debug(f"面板状态已保存: context={context}, state={state}")
        return state

    def restore_context(self, context: str) -> Optional[Dict[str, bool]]:
        with self._lock:
            saved = self._saved_states.pop(context, None)
        if saved is None:
            logger.debug(f"面板状态恢复: 未找到 context={context}")
            return None
        logger.debug(f"面板状态恢复: context={context}, state={saved}")
        self._restore_from_saved(saved)
        return saved

    def get_saved_context(self, context: str) -> Optional[Dict[str, bool]]:
        with self._lock:
            return self._saved_states.get(context)

    def _collect_extra_context(self, context: str) -> Dict[str, bool]:
        extra = {}
        if context in ('fullscreen', 'pip'):
            w = self._window
            extra['title_bar'] = hasattr(w, '_title_bar') and w._title_bar and w._title_bar.isVisible()
            extra['menu_bar'] = hasattr(w, '_custom_menu_bar') and w._custom_menu_bar and w._custom_menu_bar.isVisible()
            extra['status_bar'] = hasattr(w, 'status_bar') and w.status_bar and w.status_bar.isVisible()
        return extra

    def _restore_from_saved(self, saved: Dict[str, bool]):
        for panel in self.PANELS:
            if panel in saved:
                self.set_visible(panel, saved[panel])

        with self._lock:
            self._manually_hidden = saved.get('manually_hidden', False)

        w = self._window
        if 'title_bar' in saved and hasattr(w, '_title_bar') and w._title_bar:
            w._title_bar.setVisible(saved['title_bar'])
        if 'menu_bar' in saved and hasattr(w, '_custom_menu_bar') and w._custom_menu_bar:
            w._custom_menu_bar.setVisible(saved['menu_bar'])
        if 'status_bar' in saved and hasattr(w, 'status_bar') and w.status_bar:
            w.status_bar.setVisible(saved['status_bar'])

    def save_auto_hide_state(self):
        with self._lock:
            self._auto_hide_saved = {p: self._visible[p] for p in self.PANELS}

    def restore_auto_hide_state(self, is_local_file: bool = False):
        with self._lock:
            saved = dict(self._auto_hide_saved)
            self._auto_hide_saved = {}
            self._auto_hide_state = AutoHideState.VISIBLE
        for panel in self.PANELS:
            if panel == 'epg' and is_local_file:
                self.set_visible(panel, False)
            else:
                self.set_visible(panel, saved.get(panel, True))

    def hide_all(self):
        with self._lock:
            self._saved_states['_manual_hide'] = {p: self._visible[p] for p in self.PANELS}
        for panel in self.PANELS:
            self.set_visible(panel, False)
        with self._lock:
            self._manually_hidden = True

    def restore_from_manual_hide(self, is_local_file: bool = False):
        with self._lock:
            saved = self._saved_states.pop('_manual_hide', {})
            self._manually_hidden = False
            self._auto_hide_state = AutoHideState.VISIBLE
        for panel in self.PANELS:
            if panel == 'epg' and is_local_file:
                self.set_visible(panel, False)
            else:
                self.set_visible(panel, saved.get(panel, True))

    def auto_hide_all(self):
        self.save_auto_hide_state()
        for panel in self.PANELS:
            self.set_visible(panel, False)
        with self._lock:
            self._auto_hide_state = AutoHideState.AUTO_HIDDEN

    def set_all_visible(self, is_local_file: bool = False):
        for panel in self.PANELS:
            if panel == 'epg' and is_local_file:
                self.set_visible(panel, False)
            else:
                self.set_visible(panel, True)
        with self._lock:
            self._manually_hidden = False
            self._auto_hide_state = AutoHideState.VISIBLE

    def set_auto_hide_visible(self):
        with self._lock:
            self._auto_hide_state = AutoHideState.VISIBLE
            self._auto_hide_saved = {}

    def reset(self):
        for panel in self.PANELS:
            self.set_visible(panel, True)
        with self._lock:
            self._manually_hidden = False
            self._auto_hide_state = AutoHideState.VISIBLE
            self._saved_states.clear()
            self._auto_hide_saved = {}

    def _apply_panel(self, panel: str, visible: bool):
        w = self._window
        panel_map = {
            'epg': ('epg_panel', 'epg_dock'),
            'playlist': ('playlist_panel', 'playlist_dock'),
            'floating': ('floating_panel', None),
        }
        attrs = panel_map.get(panel, ())
        for attr in attrs:
            if attr and hasattr(w, attr):
                widget = getattr(w, attr)
                if widget:
                    widget.setVisible(visible)

        if panel in self.PANELS and hasattr(w, '_sync_panel_actions'):
            w._sync_panel_actions()

        if visible and hasattr(w, 'update_floating_position'):
            from PySide6.QtCore import QTimer
            if not getattr(w, '_position_update_pending', False):
                w._position_update_pending = True
                QTimer.singleShot(0, lambda: (setattr(w, '_position_update_pending', False), w.update_floating_position()))

    def add_listener(self, callback: Callable[[str, bool], None]):
        with self._lock:
            self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[str, bool], None]):
        with self._lock:
            if callback in self._listeners:
                self._listeners.remove(callback)

    def _notify(self, panel: str, visible: bool):
        with self._lock:
            listeners = list(self._listeners)
        for callback in listeners:
            try:
                callback(panel, visible)
            except Exception as e:
                logger.error(f"面板可见性监听器回调异常: {e}")
