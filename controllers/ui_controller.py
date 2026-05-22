"""
UI控制器 - 负责OSD显示、媒体信息更新、样式管理等
从 pyqt_player.py 提取的独立模块
"""

from typing import Optional, Dict, Any
from PyQt6.QtCore import QTimer
from controllers.main_window_protocol import MainWindowProtocol


class UIController:
    """UI控制器 - 管理所有UI显示相关的逻辑"""

    def __init__(self, main_window: MainWindowProtocol):
        self.window: MainWindowProtocol = main_window
        self._osd_visible = False

    @property
    def osd_visible(self) -> bool:
        return self._osd_visible

    @osd_visible.setter
    def osd_visible(self, value: bool):
        self._osd_visible = value

    def toggle_osd(self, checked=None):
        """切换OSD显示/隐藏"""
        if checked is None:
            self._osd_visible = not self._osd_visible
        else:
            self._osd_visible = checked

        self.window._osd_visible = self._osd_visible

        if self.window._osd_menu_action:
            self.window._osd_menu_action.setChecked(self._osd_visible)

        if self._osd_visible:
            self._show_osd()
        else:
            self._hide_osd()

    def _show_osd(self):
        self.window.panel_vis.save_context('osd')

        for panel_attr in ['epg_panel', 'playlist_panel']:
            panel = getattr(self.window, panel_attr, None)
            if panel and panel.isVisible():
                panel.hide()

        pc = self.window.player_controller
        if pc and pc.is_playing:
            try:
                info = pc.get_live_media_info()
            except Exception:
                info = None
            if not info:
                info = {}

            osd_text = self._build_osd_text(info, pc)
            if osd_text:
                pc.show_osd(osd_text, 86400000)

    def _build_osd_text(self, info: Dict[str, Any], pc) -> str:
        """构建OSD文本内容"""
        from core.log_manager import global_logger as logger

        channel_name = ''
        current = self.window.current_channel
        if current and isinstance(current, dict):
            channel_name = current.get('name', '') or ''

        lines = [channel_name] if channel_name else []

        if current and isinstance(current, dict):
            play_url = current.get('url', '') or ''
            if play_url:
                lines.append(play_url)

        vline_parts = []
        w = info.get('width', 0) or 0
        h = info.get('height', 0) or 0
        if w > 0 and h > 0:
            vline_parts.append("{}x{}".format(w, h))

        vcodec = info.get('video_codec', '') or ''
        if vcodec:
            vline_parts.append(vcodec)

        fps = info.get('fps', 0) or 0
        if fps > 0:
            vline_parts.append("{:.1f}fps".format(fps))

        hw = info.get('hwdec', '') or ''
        if hw and hw != 'no':
            vline_parts.append("[{}]".format(hw))

        colormatrix = info.get('colormatrix', '') or ''
        gamma = info.get('gamma', '') or ''
        sig_peak = info.get('sig_peak', 0) or 0
        try:
            from services.mpv_player_service import MpvPlayerController
            hdr_type = MpvPlayerController.detect_hdr_type(colormatrix, gamma, sig_peak)
        except Exception:
            hdr_type = ''
        if hdr_type and hdr_type != 'SDR':
            vline_parts.append(hdr_type)

        if vline_parts:
            lines.append("  ".join(vline_parts))

        pix_line = []
        pix_fmt = info.get('pixel_format', '') or ''
        color_primaries = info.get('color_primaries', '') or ''
        colorlevels = info.get('colorlevels', '') or ''
        sig_avg = info.get('sig_avg', 0) or 0

        if pix_fmt:
            pix_line.append(pix_fmt)
        if colormatrix:
            pix_line.append(colormatrix)
        if color_primaries:
            pix_line.append(color_primaries)
        if gamma:
            pix_line.append(gamma)
        if colorlevels:
            pix_line.append(colorlevels)
        if sig_peak > 0:
            pix_line.append("peak:{:.0f}".format(sig_peak))
        if sig_avg > 0:
            pix_line.append("avg:{:.0f}".format(sig_avg))
        if pix_line:
            lines.append("  ".join(pix_line))

        aline_parts = []
        acodec = info.get('audio_codec', '') or ''
        audio_channels = info.get('audio_channels', 0) or 0
        sample_rate = info.get('sample_rate', 0) or 0
        a_br = info.get('audio_bitrate', 0) or 0
        v_br = info.get('video_bitrate', 0) or 0

        if acodec:
            aline_parts.append(acodec)
        if audio_channels > 0:
            aline_parts.append("{}ch".format(audio_channels))
        if sample_rate > 0:
            aline_parts.append("{}Hz".format(sample_rate))
        if a_br > 0:
            aline_parts.append(self._format_bitrate(a_br))
        if v_br > 0:
            aline_parts.append("v:{}".format(self._format_bitrate(v_br)))
        if aline_parts:
            lines.append("  ".join(aline_parts))

        net_parts = []
        container = info.get('container', '') or ''
        cached_media = getattr(pc, 'media_info', None) or {}
        protocol = ''
        if isinstance(cached_media, dict):
            protocol = cached_media.get('protocol', '') or ''

        if container and container != '未知':
            net_parts.append(container)
        if protocol and protocol != '未知':
            net_parts.append(protocol)
        if net_parts:
            lines.append("[{}]".format("  ".join(net_parts)))

        total_time = pc.get_total_time() or 0
        is_live = (total_time or 0) <= 0

        if is_live:
            lines.append("\u25cf LIVE")
        else:
            current_time = pc.get_current_time() or 0
            from datetime import timedelta
            cur_td = timedelta(seconds=current_time) if current_time else None
            tot_td = timedelta(seconds=total_time) if total_time else None
            cur_str = str(cur_td).split('.')[0] if cur_td else '--:--:--'
            tot_str = str(tot_td).split('.')[0] if tot_td else '--:--:--'
            lines.append("{} / {}".format(cur_str, tot_str))

        return '\n'.join(lines)

    def _format_bitrate(self, bitrate: int) -> str:
        """格式化码率显示"""
        if bitrate >= 1000000:
            return "{:.1f}Mbps".format(bitrate / 1000000)
        elif bitrate >= 1000:
            return "{:.0f}Kbps".format(bitrate / 1000)
        else:
            return "{}bps".format(bitrate)

    def _hide_osd(self):
        self.window.panel_vis.restore_context('osd')

        pc = self.window.player_controller
        if pc:
            pc.send_command([b'show-text', b'', b'0'])

    def update_media_info_display(self, media_info: Dict[str, Any]):
        """更新媒体信息显示（视频、音频、网络信息标签）"""
        tr = self.window.language_manager.tr

        if not media_info:
            return

        video_info = media_info.get('video', {})
        audio_info = media_info.get('audio', {})

        self._update_video_label(video_info, tr)
        self._update_audio_label(audio_info, tr)
        self._update_network_label(media_info, tr)

    def _update_video_label(self, video_info: Dict[str, Any], tr):
        """更新视频信息标签"""
        parts = []

        codec = video_info.get('codec')
        if codec and codec != '未知':
            parts.append(f"{tr('codec_label', 'Codec')}: {codec}")

        width = video_info.get('width', 0)
        height = video_info.get('height', 0)
        if width > 0 and height > 0:
            parts.append(f"{tr('resolution_label', 'Resolution')}: {width}x{height}")

        frame_rate = video_info.get('frame_rate', 0)
        if frame_rate and frame_rate > 0:
            parts.append(f"{tr('frame_rate_label', 'Frame Rate')}: {frame_rate:.2f}fps")

        bit_rate = video_info.get('bit_rate', 0)
        if bit_rate and bit_rate > 0:
            parts.append(f"{tr('bitrate_label', 'Bitrate')}: {self._format_bitrate(bit_rate)}")

        pixel_format = video_info.get('pixel_format', '')
        if pixel_format and pixel_format != '未知':
            parts.append(f"{tr('pixel_format_label', 'Pixel Format')}: {pixel_format}")

        if parts:
            self.window.video_info.setText(' | '.join(parts))
        else:
            self.window.video_info.setText(tr('no_video_info', 'No video info available'))

    def _update_audio_label(self, audio_info: Dict[str, Any], tr):
        """更新音频信息标签"""
        parts = []

        codec = audio_info.get('codec')
        if codec and codec != '未知':
            import re
            codec = re.sub(r'\s*\(.*?\)\s*', '', codec).strip()
            parts.append(f"{tr('codec_label', 'Codec')}: {codec}")

        channels = audio_info.get('channels', 0)
        if channels and channels > 0:
            parts.append(f"{tr('channel_count_label', 'Channels')}: {channels}ch")

        sample_rate = audio_info.get('sample_rate', 0)
        if sample_rate and sample_rate > 0:
            parts.append(f"{tr('sample_rate_label', 'Sample Rate')}: {sample_rate}Hz")

        bit_rate = audio_info.get('bit_rate', 0)
        if bit_rate and bit_rate > 0:
            parts.append(f"{tr('bitrate_label', 'Bitrate')}: {self._format_bitrate(bit_rate)}")

        if parts:
            self.window.audio_info.setText(' | '.join(parts))
        else:
            self.window.audio_info.setText(tr('no_audio_info', 'No audio info available'))

    def _update_network_label(self, media_info: Dict[str, Any], tr):
        """更新网络/格式信息标签"""
        parts = []

        format_name = media_info.get('format')
        if format_name and format_name != '未知':
            parts.append(f"{tr('format_label', 'Format')}: {format_name}")

        protocol = media_info.get('protocol')
        if protocol and protocol != '未知':
            parts.append(f"{tr('protocol_label', 'Protocol')}: {protocol}")

        if parts:
            self.window.network_info.setText(' | '.join(parts))
        else:
            self.window.network_info.setText(tr('no_network_info', 'No network info available'))

    def reapply_all_styles(self):
        """重新应用所有样式（用于主题切换后）"""
        try:
            AppStyles = getattr(__import__('ui.styles', fromlist=['AppStyles']), 'AppStyles')

            self.window.setStyleSheet(AppStyles.main_window_style())

            if self.window._title_bar:
                self.window._title_bar.setStyleSheet(AppStyles.title_bar_style())
            if self.window._title_label:
                self.window._title_label.setStyleSheet(AppStyles.title_label_style())

            if self.window._custom_menu_bar:
                self.window._custom_menu_bar.setStyleSheet(AppStyles.player_menu_bar_style())

            if self.window.central_widget:
                self.window.central_widget.setStyleSheet(AppStyles.player_background_style())
            if self.window.video_frame:
                self.window.video_frame.setStyleSheet(AppStyles.player_background_style())
            if self.window.video_placeholder:
                self.window.video_placeholder.setStyleSheet(AppStyles.player_video_placeholder_style())
            if self.window.status_bar:
                self.window.status_bar.setStyleSheet(AppStyles.statusbar_style())
            if self.window.toolbar:
                self.window.toolbar.setStyleSheet(AppStyles.player_toolbar_style())

            for panel_attr in ['epg_dock', 'playlist_dock', 'floating_dock']:
                dock = getattr(self.window, panel_attr, None)
                if dock:
                    container = dock.widget()
                    if container:
                        container.setStyleSheet(AppStyles.player_panel_style())

            self.window._reapply_side_panel_styles()
            self.window._reapply_floating_panel_styles()

        except Exception as e:
            from core.log_manager import global_logger as logger
            logger.error(f"重新应用样式失败: {e}")