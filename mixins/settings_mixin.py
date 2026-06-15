from core.log_manager import global_logger as logger
from ui.styles import AppStyles


class SettingsMixin:
    """从 IPTVPlayer 提取的设置/主题/语言/对话框职责"""

    def set_language(self, language: str):
        self.settings_ops.set_language(language)

    def set_theme(self, theme: str):
        self.settings_ops.set_theme(theme)

    def set_color_mode(self, mode: str):
        self.settings_ops.set_color_mode(mode)

    def set_visual_style(self, style: str):
        self.settings_ops.set_visual_style(style)

    def show_about(self):
        self.settings_ops.show_about()

    def player_settings(self):
        self.settings_ops.player_settings()

    def _toggle_file_association(self):
        from ui.dialogs.file_association_dialog import FileAssociationDialog
        dialog = FileAssociationDialog(self)
        dialog.exec()

    def _reset_statusbar_style(self):
        self.status_bar.setStyleSheet(AppStyles.statusbar_style())

    def _cancel_source_timeout(self):
        if hasattr(self, '_source_timeout_timer') and self._source_timeout_timer:
            self._source_timeout_timer.stop()

    def _on_source_timeout(self, channel):
        if not self.player_controller or not self.player_controller.is_playing:
            return
        if self.play_state.is_catchup_or_timeshift:
            return
        logger.debug(f"源超时（无备用源可切换）: {channel.get('name', '')}")