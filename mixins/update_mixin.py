from PySide6.QtCore import QThread, Slot
from core.log_manager import global_logger as logger


class UpdateMixin:
    """从 IPTVPlayer 提取的更新检查职责"""

    def _check_for_updates_async(self):
        if QThread.currentThread() != self.thread():
            from utils.thread_safety import invoke_on_thread
            invoke_on_thread(self, self._do_check_for_updates_async)
            return
        self._do_check_for_updates_async()

    @Slot()
    def _do_check_for_updates_async(self):
        self.update_ctrl.check_for_updates()

    def _on_update_found(self, latest_version, current_version):
        self.update_ctrl._on_update_found(latest_version, current_version)

    def _on_update_check_completed(self, success, message):
        self.update_ctrl._on_update_check_completed(success, message)