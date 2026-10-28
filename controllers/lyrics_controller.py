"""LyricsController — 从 MediaController 提取的子控制器。"""

from core.log_manager import global_logger as logger
from utils.thread_safety import safe_single_shot
from utils.delay_constants import DelayMs
from PySide6.QtWidgets import QFileDialog


class LyricsController:
    """LyricsController — 通过 facade 访问主窗口和播放器。"""

    def __init__(self, facade):
        self._facade = facade

    def _create_lyrics_widget(self):
        from ui.lyrics_widget import LyricsWidget
        lw = LyricsWidget(self._facade.window.video_frame)
        lw.hide()
        self._facade.window._lyrics_widget = lw

    def _load_external_lyrics(self):
        tr = self._facade.window.language_manager.tr
        file_path, _ = QFileDialog.getOpenFileName(
            self._facade.window, tr("ctx_load_lyrics", "加载外部歌词..."), '',
            tr("lyrics_files", "歌词文件") + " (*.lrc *.txt);;" + tr("all_files", "所有文件") + " (*)"
        )
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    lyrics = f.read()
                if not hasattr(self._facade.window, '_lyrics_widget') or not self._facade.window._lyrics_widget:
                    self._facade._create_lyrics_widget()
                is_lrc = file_path.lower().endswith('.lrc') or '[' in lyrics
                self._facade.window._lyrics_widget.set_lyrics(lyrics, is_lrc=is_lrc)
                self._facade.window._lyrics_widget.show()
                self._facade.window._lyrics_widget.raise_()
                self._facade.window._lyrics_widget.start()
            except Exception as e:
                logger.debug(f"启动歌词控件失败: {e}")

    def _populate_lyrics_menu(self, menu):
        tr = self._facade.window.language_manager.tr
        show_label = tr("ctx_show_lyrics", "显示歌词")
        menu.addAction(show_label, lambda *a: self._facade._toggle_lyrics(True))
        hide_label = tr("ctx_hide_lyrics", "隐藏歌词")
        menu.addAction(hide_label, lambda *a: self._facade._toggle_lyrics(False))
        menu.addSeparator()
        load_label = tr("ctx_load_lyrics", "加载外部歌词...")
        menu.addAction(load_label, lambda *a: self._facade._load_external_lyrics())
        self._populate_lyrics_display_menu(menu)

    def _populate_lyrics_display_menu(self, menu):
        """歌词显示设置子菜单：位置 / 形式 / 字号（任务B）。"""
        tr = self._facade.window.language_manager.tr
        if not hasattr(self._facade.window, '_lyrics_widget') or not self._facade.window._lyrics_widget:
            self._facade._create_lyrics_widget()
        lw = self._facade.window._lyrics_widget

        menu.addSeparator()
        pos_menu = menu.addMenu(tr("lyrics_pos_menu", "歌词位置"))
        for key, label_key, label_def in (
            ('top', "lyrics_pos_top", "顶部"),
            ('center', "lyrics_pos_center", "居中"),
            ('bottom', "lyrics_pos_bottom", "底部"),
        ):
            label = tr(label_key, label_def)
            if lw.get_position_mode() == key:
                label += " ✓"
            pos_menu.addAction(label, lambda *a, k=key: lw.set_position_mode(k))

        mode_menu = menu.addMenu(tr("lyrics_mode_menu", "歌词形式"))
        for key, label_key, label_def in (
            ('single', "lyrics_mode_single", "单行大字"),
            ('multi', "lyrics_mode_multi", "多行滚动"),
        ):
            label = tr(label_key, label_def)
            if lw.get_display_mode() == key:
                label += " ✓"
            mode_menu.addAction(label, lambda *a, k=key: lw.set_display_mode(k))

        font_menu = menu.addMenu(tr("lyrics_font_menu", "字号"))
        for key, label_key, label_def in (
            ('small', "lyrics_font_small", "小"),
            ('medium', "lyrics_font_medium", "中"),
            ('large', "lyrics_font_large", "大"),
        ):
            label = tr(label_key, label_def)
            if lw.get_font_scale_mode() == key:
                label += " ✓"
            font_menu.addAction(label, lambda *a, k=key: lw.set_font_scale(k))

    def _refresh_lyrics(self):
        if not hasattr(self._facade.window, '_lyrics_widget') or not self._facade.window._lyrics_widget:
            return
        ch = self._facade.window.current_channel
        if not ch:
            return
        url = ch.get('url', '')
        if not url:
            return
        from services.audio_visual_service import extract_lyrics
        lyrics = extract_lyrics(url)
        if lyrics:
            self._facade.window._lyrics_widget.set_lyrics(lyrics, is_lrc='[' in lyrics)
        else:
            tr = self._facade.window.language_manager.tr
            self._facade.window._lyrics_widget.set_lyrics(tr("no_lyrics", "未找到内嵌歌词"), is_lrc=False)

    def _toggle_lyrics(self, show):
        if not hasattr(self._facade.window, '_lyrics_widget') or not self._facade.window._lyrics_widget:
            self._facade._create_lyrics_widget()
        lw = self._facade.window._lyrics_widget
        if show:
            vf = self._facade.window.video_frame
            if vf:
                lw.setGeometry(0, 0, vf.width(), vf.height())
            lw.show()
            lw.raise_()
            lw.start()
            self._facade._refresh_lyrics()
        else:
            lw.stop()
            lw.hide()

