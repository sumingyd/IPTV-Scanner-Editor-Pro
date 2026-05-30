"""
UI控制器 - 负责OSD显示、媒体信息更新、样式管理等
从 pyqt_player.py 提取的独立模块
"""

import re
from typing import Optional, Dict, Any
from datetime import timedelta
from PyQt6.QtCore import QTimer
from controllers.main_window_protocol import MainWindowProtocol


class UIController:
    """UI控制器 - 管理所有UI显示相关的逻辑"""

    def __init__(self, main_window: MainWindowProtocol):
        self.window: MainWindowProtocol = main_window
        self._osd_visible = False
        self._osd_timer = QTimer()
        self._osd_timer.setInterval(1000)
        self._osd_timer.timeout.connect(self._refresh_osd)

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

        self._refresh_osd()
        self._osd_timer.start()

    def _refresh_osd(self):
        """刷新OSD内容（由定时器驱动）"""
        pc = self.window.player_controller
        if not pc or not pc.is_playing:
            return
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
        """构建OSD文本内容 - 结构化排版"""
        lines = []

        current = self.window.current_channel
        channel_name = ''
        play_url = ''
        if current and isinstance(current, dict):
            channel_name = current.get('name', '') or ''
            play_url = current.get('url', '') or ''

        if channel_name:
            lines.append(channel_name)

        tr = self.window.language_manager.tr

        vline = []
        w = info.get('width', 0) or 0
        h = info.get('height', 0) or 0
        dw = info.get('dwidth', 0) or 0
        dh = info.get('dheight', 0) or 0
        if w > 0 and h > 0:
            res = f'{w}x{h}'
            if dw > 0 and dh > 0 and (dw != w or dh != h):
                res += f' ({dw}x{dh})'
            vline.append(f'{tr("osd_resolution", "Resolution")}: {res}')

        vcodec = info.get('video_codec', '') or ''
        if vcodec:
            vline.append(f'{tr("osd_codec", "Codec")}: {vcodec}')

        fps = info.get('fps', 0) or 0
        if fps > 0:
            fps_str = f'{fps:.2f}' if fps < 10 else f'{fps:.1f}'
            vline.append(f'{tr("osd_fps", "FPS")}: {fps_str}')

        ar = info.get('aspect_ratio', '') or ''
        if ar and ar != '0' and ar != '1.7778':
            vline.append(f'{tr("osd_ar", "AR")}: {ar}')

        hw = info.get('hwdec', '') or ''
        if hw and hw != 'no':
            vline.append(f'{tr("osd_hwdec", "HWDec")}: {hw}')

        colormatrix = info.get('colormatrix', '') or ''
        gamma = info.get('gamma', '') or ''
        sig_peak = info.get('sig_peak', 0) or 0
        try:
            from services.mpv_player_service import MpvPlayerController
            hdr_type = MpvPlayerController.detect_hdr_type(colormatrix, gamma, sig_peak)
        except Exception:
            hdr_type = ''
        if hdr_type:
            vline.append(f'{tr("osd_dynamic", "Dynamic")}: {hdr_type}')

        if vline:
            lines.append('  '.join(vline))

        pix_line = []
        pix_fmt = info.get('pixel_format', '') or ''
        if pix_fmt:
            pix_line.append(f'{tr("osd_pixel", "Pixel")}: {pix_fmt}')
        if colormatrix:
            pix_line.append(f'{tr("osd_matrix", "Matrix")}: {colormatrix}')
        color_primaries = info.get('color_primaries', '') or ''
        if color_primaries:
            pix_line.append(f'{tr("osd_prim", "Prim")}: {color_primaries}')
        if gamma:
            pix_line.append(f'{tr("osd_tf", "TF")}: {gamma}')
        colorlevels = info.get('colorlevels', '') or ''
        if colorlevels:
            pix_line.append(f'{tr("osd_range", "Range")}: {colorlevels}')
        sig_avg = info.get('sig_avg', 0) or 0
        if sig_peak > 0:
            pix_line.append(f'{tr("osd_peak", "Peak")}: {sig_peak:.1f}')
        if sig_avg > 0:
            pix_line.append(f'{tr("osd_avg", "Avg")}: {sig_avg:.1f}')
        if pix_line:
            lines.append('  '.join(pix_line))

        aline = []
        acodec = info.get('audio_codec', '') or ''
        if acodec:
            aline.append(f'{tr("osd_codec", "Codec")}: {acodec}')
        audio_channels = info.get('audio_channels', 0) or 0
        if audio_channels > 0:
            ch_map = {1: tr('osd_mono', 'Mono'), 2: tr('osd_stereo', 'Stereo'), 6: '5.1', 8: '7.1'}
            ch_label = ch_map.get(audio_channels, f'{audio_channels}{tr("osd_ch_suffix", "ch")}')
            aline.append(f'{tr("osd_channels", "Channels")}: {ch_label}')
        sample_rate = info.get('sample_rate', 0) or 0
        if sample_rate > 0:
            if sample_rate >= 1000:
                aline.append(f'{tr("osd_rate", "Rate")}: {sample_rate / 1000:.1f}kHz')
            else:
                aline.append(f'{tr("osd_rate", "Rate")}: {sample_rate}Hz')
        a_br = info.get('audio_bitrate', 0) or 0
        if a_br > 0:
            aline.append(f'{tr("osd_bitrate", "Bitrate")}: {self.format_bitrate(a_br)}')
        if aline:
            lines.append('  '.join(aline))

        br_line = []
        v_br = info.get('video_bitrate', 0) or 0
        if v_br > 0:
            br_line.append(f'{tr("osd_video_br", "Video")}: {self.format_bitrate(v_br)}')
        cache_speed = info.get('cache_speed', 0) or 0
        if cache_speed > 0:
            br_line.append(f'{tr("osd_cache", "Cache")}: {self.format_bitrate(cache_speed)}')
        if br_line:
            lines.append('  '.join(br_line))

        container_line = []
        container = info.get('container', '') or ''
        unknown_marker = tr('unknown', 'Unknown')
        if container and container not in ('未知', 'Unknown', unknown_marker):
            container_line.append(f'{tr("osd_container", "Container")}: {container}')
        protocol = info.get('protocol', '') or ''
        if not protocol:
            cached_media = getattr(pc, 'media_info', None) or {}
            if isinstance(cached_media, dict):
                protocol = cached_media.get('protocol', '') or ''
        if protocol and protocol not in ('未知', 'Unknown', unknown_marker):
            container_line.append(f'{tr("osd_protocol", "Protocol")}: {protocol}')
        demuxer = info.get('demuxer', '') or ''
        if demuxer:
            container_line.append(f'{tr("osd_demuxer", "Demuxer")}: {demuxer}')
        if container_line:
            lines.append('  '.join(container_line))

        if play_url:
            display_url = play_url
            if len(display_url) > 80:
                half = 37
                display_url = display_url[:half] + '...' + display_url[-half:]
            lines.append(f'{tr("osd_url", "URL")}: {display_url}')

        total_time = pc.get_total_time() or 0
        is_live = (total_time or 0) <= 0

        if is_live:
            lines.append(tr('osd_live', '● LIVE'))
        else:
            current_time = pc.get_current_time() or 0
            from datetime import timedelta
            cur_td = timedelta(seconds=current_time) if current_time else None
            tot_td = timedelta(seconds=total_time) if total_time else None
            cur_str = str(cur_td).split('.')[0] if cur_td else '--:--:--'
            tot_str = str(tot_td).split('.')[0] if tot_td else '--:--:--'
            if total_time > 0 and current_time > 0:
                pct = current_time / total_time * 100
                lines.append(f'{cur_str} / {tot_str}  ({pct:.1f}%)')
            else:
                lines.append(f'{cur_str} / {tot_str}')

        return '\n'.join(lines)

    def _hide_osd(self):
        self._osd_timer.stop()
        self.window.panel_vis.restore_context('osd')

        pc = self.window.player_controller
        if pc:
            pc.send_command([b'show-text', b'', b'0'])

    @staticmethod
    def format_bitrate(bps: float) -> str:
        if bps >= 1000000:
            return f"{bps/1000000:.1f}MB/s"
        elif bps >= 1000:
            return f"{bps/1000:.1f}KB/s"
        else:
            return f"{bps:.0f}B/s"

    @staticmethod
    def shorten_codec_name(codec_name: str) -> str:
        if not codec_name:
            return ''
        if 'H.264' in codec_name or 'AVC' in codec_name or 'h264' in codec_name.lower():
            return 'H.264'
        if 'H.265' in codec_name or 'HEVC' in codec_name or 'hevc' in codec_name.lower():
            return 'H.265'
        if 'MPEG-2' in codec_name or 'mpeg2' in codec_name.lower():
            return 'MPEG-2'
        if 'MPEG-4' in codec_name or 'mpeg4' in codec_name.lower():
            return 'MPEG-4'
        if 'MP3' in codec_name or 'MPEG audio layer 3' in codec_name:
            return 'MP3'
        if 'AAC' in codec_name or 'aac' in codec_name.lower():
            return 'AAC'
        if 'AC-3' in codec_name or 'AC3' in codec_name or 'ac3' in codec_name.lower():
            return 'AC3'
        return codec_name[:10] if len(codec_name) > 10 else codec_name

    def format_media_info(self, info: Dict[str, Any], tr) -> Dict[str, str]:
        """输入扁平dict，返回格式化后的 {video_text, audio_text, network_text}"""
        from services.mpv_player_service import MpvPlayerController

        video_parts = []

        hw = info.get('hwdec', '')
        if hw and hw != 'no':
            video_parts.append("{}: {}".format(tr('hwdec_label', 'HW') or 'HW', hw))

        video_codec = info.get('video_codec', '')
        if video_codec and video_codec != '未知':
            codec_short = self.shorten_codec_name(video_codec)
            video_parts.append("{}: {}".format(tr('vcodec_label', 'Video') or 'Video', codec_short))

        video_width = info.get('width', 0)
        video_height = info.get('height', 0)
        if video_width > 0 and video_height > 0:
            video_parts.append("{}: {}x{}".format(tr('resolution_label', 'Resolution') or 'Resolution', video_width, video_height))

        hdr_type = MpvPlayerController.detect_hdr_type(
            info.get('colormatrix', ''),
            info.get('gamma', ''),
            info.get('sig_peak', 0)
        )
        if hdr_type:
            video_parts.append("{}: {}".format(tr('hdr_label', 'HDR') or 'HDR', hdr_type))

        fps = info.get('fps', 0)
        if fps and fps > 0:
            video_parts.append("{}: {:.0f}fps".format(tr('frame_rate_label', 'FPS') or 'FPS', fps))

        v_br = info.get('video_bitrate', 0)
        a_br = info.get('audio_bitrate', 0)
        total_br = v_br + a_br
        if total_br and total_br > 0:
            video_parts.append(self.format_bitrate(total_br))

        video_text = " | ".join(video_parts) if video_parts else (tr('live_stream', 'Live Stream') or 'Live Stream')

        audio_parts = []

        audio_codec = info.get('audio_codec', '')
        if audio_codec and audio_codec != '未知':
            audio_codec = re.sub(r'\s*\(.*?\)\s*', '', audio_codec).strip()
            audio_parts.append("{}: {}".format(tr('acodec_label', 'Audio') or 'Audio', audio_codec))

        channels = info.get('audio_channels', 0)
        if channels and channels > 0:
            audio_parts.append("{}: {}ch".format(tr('channel_count_label', 'Channels') or 'Channels', channels))

        sample_rate = info.get('sample_rate', 0)
        if sample_rate and sample_rate > 0:
            audio_parts.append("{}: {}Hz".format(tr('sample_rate_label', 'Sample Rate') or 'Sample Rate', sample_rate))

        if a_br and a_br > 0:
            audio_parts.append("{}: {}".format(tr('bitrate_label', 'Bitrate') or 'Bitrate', self.format_bitrate(a_br)))

        audio_text = ' | '.join(audio_parts) if audio_parts else tr('no_audio_info', 'No audio info available')

        network_parts = []
        container = info.get('container', '')
        proto = info.get('protocol', '')

        if container and container != '未知':
            network_parts.append(f"{tr('format_label', 'Format')}: {container}")
        if proto and proto != '未知':
            network_parts.append(f"{tr('protocol_label', 'Protocol')}: {proto}")

        network_text = ' | '.join(network_parts) if network_parts else tr('no_network_info', 'No network info available')

        return {
            'video_text': video_text,
            'audio_text': audio_text,
            'network_text': network_text,
        }

    def update_media_info_labels(self, info: Dict[str, Any], tr):
        """格式化媒体信息并写入标签"""
        result = self.format_media_info(info, tr)
        self.window.video_info.setText(result['video_text'])
        self.window.audio_info.setText(result['audio_text'])
        self.window.network_info.setText(result['network_text'])

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

            self._reapply_side_panel_styles()
            self._reapply_floating_panel_styles()

        except Exception as e:
            from core.log_manager import global_logger as logger
            logger.error(f"重新应用样式失败: {e}")

    def on_live_media_info_updated(self, info: Dict[str, Any]):
        """持续更新媒体信息 - 信息稳定后才更新UI，避免闪烁"""
        from core.log_manager import global_logger as logger

        if not info:
            return
        try:
            tr = self.window.language_manager.tr

            key = (
                info.get('width', 0),
                info.get('height', 0),
                info.get('video_codec', ''),
                info.get('audio_codec', ''),
                info.get('fps', 0),
                info.get('hwdec', ''),
                info.get('video_bitrate', 0),
                info.get('audio_bitrate', 0),
                info.get('audio_channels', 0),
                info.get('sample_rate', 0),
                info.get('colormatrix', ''),
                info.get('gamma', ''),
                info.get('sig_peak', 0),
            )
            if self.window._last_info_key == key:
                return
            self.window._last_info_key = key

            has_video = info.get('width', 0) > 0 and info.get('height', 0) > 0
            has_codec = bool(info.get('video_codec', ''))

            if not has_video and not has_codec:
                info = self.window._last_media_info.copy()
                if not info:
                    return
            elif not has_video and has_codec:
                cached = self.window._last_media_info
                if cached.get('width', 0) > 0 and cached.get('height', 0) > 0:
                    merged = dict(info)
                    for k in ('width', 'height', 'fps', 'video_bitrate', 'colormatrix', 'gamma', 'sig_peak'):
                        if k in cached and cached[k]:
                            merged[k] = cached[k]
                    info = merged
                else:
                    self.window._last_media_info.update(info)
            else:
                self.window._last_media_info = info.copy()

            if 'protocol' not in info or not info['protocol']:
                proto = self.window.player_controller._guess_protocol(self.window.current_channel.get('url', '') if self.window.current_channel else '')
                if proto:
                    info['protocol'] = proto

            self.update_media_info_labels(info, tr)
            self.window._network_base_info = self.window.network_info.text()

        except RuntimeError:
            pass

    def update_media_info(self):
        """更新媒体信息显示"""
        from core.log_manager import global_logger as logger
        from datetime import datetime

        is_catchup = self.window.play_state.is_catchup_or_timeshift
        is_timeshift = self.window.play_state.is_timeshift

        if self.window.current_channel:
            display_name = self.window._get_display_channel_name(self.window.current_channel)
            self.window.channel_name.setText(display_name)

            if is_catchup and self.window.catchup_program is not None:
                try:
                    program_name = self.window.catchup_program.get('title', '')
                    self.window.current_program.setText(f"· {program_name}" if program_name else "")
                except Exception:
                    self.window.current_program.setText("")
            else:
                try:
                    channel_name, tvg_id, tvg_name, comma_name = self.window._get_epg_match_params()
                    if channel_name:
                        current_program = self.window.epg_parser.get_current_program(channel_name, tvg_id, tvg_name=tvg_name, comma_name=comma_name)
                        if current_program:
                            program_name = current_program.get("title", "")
                            self.window.current_program.setText(f"· {program_name}" if program_name else "")
                        else:
                            self.window.current_program.setText("")
                except Exception:
                    self.window.current_program.setText("")

        try:
            if self.window.current_channel:
                if is_catchup and self.window.catchup_program is not None:
                    try:
                        start_time = self.window.catchup_program.get('start')
                        end_time = self.window.catchup_program.get('end')
                        title = self.window.catchup_program.get('title', '')
                        desc = self.window.catchup_program.get('desc', '')
                        if not desc or desc.strip() == '':
                            channel_name, tvg_id, tvg_name, comma_name = self.window._get_epg_match_params()
                            if channel_name:
                                cp_start = start_time
                                cp_end = end_time
                                if cp_start and cp_end:
                                    all_programs = self.window.epg_parser.get_channel_epg(channel_name, tvg_id, tvg_name=tvg_name, comma_name=comma_name)
                                    if all_programs:
                                        for prog in all_programs:
                                            try:
                                                ps = prog.get('start', '')
                                                pe = prog.get('end', '')
                                                if ps and pe:
                                                    ps_dt = datetime.fromisoformat(str(ps)) if isinstance(ps, str) else ps
                                                    pe_dt = datetime.fromisoformat(str(pe)) if isinstance(pe, str) else pe
                                                    if ps_dt == cp_start and pe_dt == cp_end:
                                                        desc = prog.get('desc', '')
                                                        if not title or title.strip() == '':
                                                            title = prog.get('title', title)
                                                        break
                                            except Exception:
                                                continue
                            if not desc or desc.strip() == '':
                                desc = self.window.language_manager.tr('no_program_desc', 'No program description')
                        self.window.program_desc.setText(desc)
                        self.window.current_program.setText(f"· {title}" if title else "")
                        if start_time and end_time:
                            start_str = start_time.strftime("%H:%M")
                            end_str = end_time.strftime("%H:%M")
                            self.window.time_label.setText(f"{start_str} - {end_str}")
                            self.window.remain_label.hide()
                        else:
                            self.window.time_label.setText("--:-- - --:--")
                            self.window.remain_label.hide()
                    except Exception as e:
                        logger.error(f"处理回看节目信息失败: {e}")
                        if self.window.catchup_program is not None:
                            title = self.window.catchup_program.get('title', '')
                            self.window.current_program.setText(f"· {title}" if title else "")
                        self.window.program_desc.setText(self.window.language_manager.tr("catchup_current_program", "Catching up current program"))
                        self.window.time_label.setText("--:-- - --:--")
                        self.window.remain_label.hide()
                else:
                    self.window.remain_label.show()
                    channel_name, tvg_id, tvg_name, comma_name = self.window._get_epg_match_params()
                    is_local = self.window._is_local_file()
                    if is_local:
                        self.window.program_desc.setText(self.window.language_manager.tr("local_video_file", "本地视频文件"))
                        self.window.current_program.setText("")
                        self.window.remain_label.setText(self.window.language_manager.tr("playing_label", "Playing..."))
                    elif channel_name:
                        current_program = self.window.epg_parser.get_current_program(channel_name, tvg_id, tvg_name=tvg_name, comma_name=comma_name)
                        if current_program:
                            self.window.program_desc.setText(current_program.get("desc", self.window.language_manager.tr("no_program_desc", "No program description")))
                            try:
                                start_time = datetime.fromisoformat(current_program.get('start', ''))
                                end_time = datetime.fromisoformat(current_program.get('end', ''))
                                start_str = start_time.strftime("%H:%M")
                                end_str = end_time.strftime("%H:%M")
                                self.window.progress_start.setText(start_str)
                                self.window.time_label.setText(f"{start_str} - {end_str}")
                                self.window.remain_label.setText(self.window.language_manager.tr("playing_label", "Playing..."))
                            except (ValueError, KeyError, TypeError):
                                current_time = datetime.now()
                                start_hour = current_time.strftime("%H:00")
                                end_hour = (current_time.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)).strftime("%H:00")
                                self.window.progress_start.setText(start_hour)
                                self.window.time_label.setText(f"{current_time.strftime('%H:%M')}")
                                self.window.remain_label.setText(self.window.language_manager.tr("playing_label", "Playing..."))
                        else:
                            self.window.program_desc.setText(self.window.language_manager.tr("playing_current_channel", "Playing current channel"))
                            current_time = datetime.now()
                            start_hour = current_time.strftime("%H:00")
                            end_hour = (current_time.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)).strftime("%H:00")
                            self.window.progress_start.setText(start_hour)
                            self.window.progress_end.setText(end_hour)
                            self.window.time_label.setText(f"{current_time.strftime('%H:%M')}")
                            self.window.remain_label.setText(self.window.language_manager.tr("playing_label", "Playing..."))
                            minutes = current_time.minute
                            seconds = current_time.second
                            self.window._set_progress_value(minutes * 60 + seconds)
                    else:
                        self.window.program_desc.setText(self.window.language_manager.tr("playing_current_channel", "Playing current channel"))
                        current_time = datetime.now()
                        start_hour = current_time.strftime("%H:00")
                        end_hour = (current_time.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)).strftime("%H:00")
                        self.window.progress_start.setText(start_hour)
                        self.window.progress_end.setText(end_hour)
                        self.window.time_label.setText(f"{current_time.strftime('%H:%M')}")
                        self.window.remain_label.setText(self.window.language_manager.tr("playing_label", "Playing..."))
                        minutes = current_time.minute
                        seconds = current_time.second
                        self.window._set_progress_value(minutes * 60 + seconds)
        except Exception:
            if is_catchup:
                self.window.program_desc.setText(self.window.language_manager.tr("catchup_current_program", "Catching up current program"))
                self.window.time_label.setText("--:-- - --:--")
                self.window.remain_label.hide()
            else:
                self.window.remain_label.show()
                self.window.program_desc.setText(self.window.language_manager.tr("playing_current_channel", "Playing current channel"))
                current_time = datetime.now()
                start_hour = current_time.strftime("%H:00")
                end_hour = (current_time.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)).strftime("%H:00")
                self.window.progress_start.setText(start_hour)
                self.window.progress_end.setText(end_hour)
                self.window.time_label.setText(f"{current_time.strftime('%H:%M')}")
                self.window.remain_label.setText(self.window.language_manager.tr("playing_label", "Playing..."))
                minutes = current_time.minute
                seconds = current_time.second
                self.window._set_progress_value(minutes * 60 + seconds)

    def update_floating_panel_info(self):
        """更新浮动面板信息"""
        from core.log_manager import global_logger as logger

        if not self.window.player_controller or not self.window.current_channel:
            return

        import time as _time
        now = _time.monotonic()
        if now - getattr(self.window, '_last_epg_refresh', 0) >= 30:
            self.window._last_epg_refresh = now
            if hasattr(self.window, 'epg_content') and self.window.epg_content.isVisible() and not self.window._is_local_file():
                self.window.populate_epg_list()

        self.window._check_program_change()

        import time as _time2
        now2 = _time2.monotonic()
        is_catchup_mode = self.window.play_state.is_catchup_or_timeshift
        interval = 2 if is_catchup_mode else 5
        if now2 - getattr(self, '_last_media_info_update', 0) >= interval:
            self._last_media_info_update = now2
            self.update_media_info()

        if hasattr(self.window, 'buffer_info') and self.window.player_controller:
            buffer_state = self.window.player_controller.get_buffer_state()
            if buffer_state:
                if buffer_state.get('buffering'):
                    self.window.buffer_info.setText("...")
                    self.window.buffer_info.show()
                else:
                    cache_dur = buffer_state.get('cache_duration', 0)
                    if cache_dur > 0:
                        self.window.buffer_info.setText(f"{cache_dur:.0f}s")
                        self.window.buffer_info.show()
                    else:
                        self.window.buffer_info.hide()
                self._update_cache_bar(buffer_state)
            else:
                self._clear_cache_bar()

        current_time_ms = getattr(self.window, '_cached_current_time_ms', 0)
        total_time_ms = getattr(self.window, '_cached_total_time_ms', 0)
        position = getattr(self.window, '_cached_position', 0)

        is_catchup = self.window.play_state.is_catchup_or_timeshift
        if not hasattr(self.window, 'last_catchup_state') or self.window.last_catchup_state != is_catchup:
            logger.debug(f"回看模式状态: {is_catchup}")
            self.window.last_catchup_state = is_catchup

        if hasattr(self.window, '_video_overlay_label'):
            if is_catchup:
                is_timeshift = self.window.play_state.is_timeshift
                mode = 'timeshift' if is_timeshift else 'catchup'
                label = self.window.language_manager.tr('timeshift_label', '时移') if is_timeshift else self.window.language_manager.tr('catchup_label', '回看')
                self.window._video_overlay_label.set_mode(mode, label)
                if not self.window._video_overlay_label.isVisible():
                    self.window._video_overlay_label.show()
                    self.window._update_video_overlay_position()
                self.window._raise_overlay_above_video()
            else:
                if self.window._video_overlay_label.isVisible():
                    self.window._video_overlay_label.hide()

        self.window.progress_ctrl.update_progress(current_time_ms, total_time_ms, position)

    def _update_cache_bar(self, buffer_state: dict):
        progress = getattr(self.window, 'program_progress', None)
        if not progress or not hasattr(progress, 'set_cache_range'):
            return

        pc = self.window.player_controller
        if not pc or not pc.is_playing:
            progress.clear_cache_range()
            return

        total_seconds = getattr(self.window, '_progress_total_seconds', 0)
        if total_seconds <= 0:
            progress.clear_cache_range()
            return

        seek_range = pc.get_available_seek_range()
        buffer_start = seek_range.get('buffer_start', 0)
        buffer_end = seek_range.get('buffer_end', 0)
        time_pos = seek_range.get('time_pos', 0)

        if buffer_end <= buffer_start or total_seconds <= 0:
            progress.clear_cache_range()
            return

        start_ratio = max(0.0, (buffer_start - time_pos + self.window.program_progress.value()) / total_seconds)
        end_ratio = min(1.0, (buffer_end - time_pos + self.window.program_progress.value()) / total_seconds)

        if end_ratio - start_ratio < 0.005:
            progress.clear_cache_range()
            return

        progress.set_cache_range(start_ratio, end_ratio)
    def _clear_cache_bar(self):
        progress = getattr(self.window, 'program_progress', None)
        if progress and hasattr(progress, 'clear_cache_range'):
            progress.clear_cache_range()


    def _reapply_side_panel_styles(self):
        from core.log_manager import global_logger as logger
        from ui.styles import AppStyles
        from PyQt6.QtCore import QSize
        from PyQt6 import QtWidgets
        from PyQt6.QtGui import QIcon

        try:
            if hasattr(self.window, 'epg_title'):
                self.window.epg_title.setStyleSheet(AppStyles.player_epg_title_style())
            if hasattr(self.window, 'playlist_title'):
                self.window.playlist_title.setStyleSheet(AppStyles.player_playlist_title_style())
            if hasattr(self.window, 'epg_prev_day'):
                self.window.epg_prev_day.setStyleSheet(AppStyles.player_date_button_style())
                date_icon_color = AppStyles._get_colors().get('player_panel_text', '#ffffff')
                icon_path = AppStyles.get_icon('chevron_left', date_icon_color, 12)
                if icon_path:
                    self.window.epg_prev_day.setIcon(QIcon(icon_path))
            if hasattr(self.window, 'epg_next_day'):
                self.window.epg_next_day.setStyleSheet(AppStyles.player_date_button_style())
                date_icon_color = AppStyles._get_colors().get('player_panel_text', '#ffffff')
                icon_path = AppStyles.get_icon('chevron_right', date_icon_color, 12)
                if icon_path:
                    self.window.epg_next_day.setIcon(QIcon(icon_path))
            if hasattr(self.window, 'epg_date_label'):
                self.window.epg_date_label.setStyleSheet(AppStyles.player_date_label_style())
            if hasattr(self.window, 'epg_content'):
                self.window.epg_content.setStyleSheet(AppStyles.player_list_style())
            if hasattr(self.window, 'epg_empty_label'):
                self.window.epg_empty_label.setStyleSheet(AppStyles.player_empty_label_style())
            if hasattr(self.window, 'sub_group_combo'):
                self.window.sub_group_combo.setStyleSheet(AppStyles.player_group_combo_style())
            if hasattr(self.window, 'local_group_combo'):
                self.window.local_group_combo.setStyleSheet(AppStyles.player_group_combo_style())
            if hasattr(self.window, 'playlist_tab'):
                self.window.playlist_tab.setStyleSheet(AppStyles.player_tab_style())
            for list_attr in ['sub_channel_list', 'local_channel_list']:
                cl = getattr(self.window, list_attr, None)
                if cl:
                    cl.setStyleSheet(AppStyles.player_list_style())
                    name_style = AppStyles.player_channel_list_name_style()
                    for i in range(cl.count()):
                        item = cl.item(i)
                        item.setSizeHint(QSize(0, 40))
                        item_widget = cl.itemWidget(item)
                        if item_widget:
                            for label in item_widget.findChildren(QtWidgets.QLabel):
                                if label.objectName() == "channel_logo_label":
                                    label.setFixedSize(44, 32)
                                else:
                                    label.setStyleSheet(name_style)
            for empty_attr in ['sub_empty_label', 'local_empty_label']:
                el = getattr(self.window, empty_attr, None)
                if el:
                    el.setStyleSheet(AppStyles.player_empty_label_style())
            for search_attr in ['sub_search_input', 'local_search_input']:
                si = getattr(self.window, search_attr, None)
                if si:
                    si.setStyleSheet(AppStyles.player_search_input_style())
            for btn_attr in ['sub_view_grid_btn', 'local_view_grid_btn', 'sub_view_list_btn', 'local_view_list_btn']:
                vb = getattr(self.window, btn_attr, None)
                if vb:
                    vb.setStyleSheet(AppStyles.player_button_style())
            btn_color = AppStyles._get_colors().get('player_panel_text', '#ffffff')
            for btn_name in ['sub_view_list_btn', 'sub_view_grid_btn', 'local_view_list_btn', 'local_view_grid_btn']:
                btn = getattr(self.window, btn_name, None)
                if btn:
                    icon_name = 'list_view' if 'list' in btn_name else 'grid_view'
                    icon_path = AppStyles.get_icon(icon_name, btn_color)
                    if icon_path:
                        btn.setIcon(QIcon(icon_path))
            tab = getattr(self.window, 'playlist_tab', None)
            if tab:
                for i in range(tab.count()):
                    icon_name = 'signal' if i == 0 else 'folder'
                    icon_path = AppStyles.get_icon(icon_name, btn_color, 14)
                    if icon_path:
                        tab.setTabIcon(i, QIcon(icon_path))
        except Exception as e:
            logger.error(f"重新应用侧边栏样式失败: {e}")

    def _reapply_floating_panel_styles(self):
        from core.log_manager import global_logger as logger
        from ui.styles import AppStyles
        from PyQt6.QtWidgets import QToolButton, QSlider, QComboBox, QFrame, QLabel
        from PyQt6.QtGui import QIcon, QPixmap
        from PyQt6.QtCore import Qt

        try:
            if not hasattr(self.window, 'floating_panel'):
                return
            fp = self.window.floating_panel
            colors = AppStyles._get_colors()
            btn_color = colors.get('player_panel_text', '#ffffff')

            if hasattr(self.window, 'video_info'):
                self.window.video_info.setStyleSheet(AppStyles.player_media_badge_style())
            if hasattr(self.window, 'audio_info'):
                self.window.audio_info.setStyleSheet(AppStyles.player_media_badge_style())
            if hasattr(self.window, 'network_info'):
                self.window.network_info.setStyleSheet(AppStyles.player_media_badge_style())
            if hasattr(self.window, 'buffer_info'):
                self.window.buffer_info.setStyleSheet(AppStyles.player_media_badge_style())

            # 媒体信息3个图标
            for icon_attr, icon_name in [('video_info_icon', 'tv'), ('audio_info_icon', 'speaker'), ('network_info_icon', 'signal')]:
                icon_label = getattr(self.window, icon_attr, None)
                if icon_label:
                    icon_path = AppStyles.get_icon(icon_name, btn_color, 14)
                    if icon_path:
                        pixmap = QPixmap(icon_path)
                        if not pixmap.isNull():
                            icon_label.setPixmap(pixmap.scaled(14, 14, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                    icon_label.setStyleSheet("background: transparent; border: none;")

            if hasattr(self.window, 'channel_logo'):
                self.window.channel_logo.setStyleSheet(AppStyles.player_channel_logo_style())
            if hasattr(self.window, 'channel_name'):
                self.window.channel_name.setStyleSheet(AppStyles.player_channel_name_style())
            if hasattr(self.window, 'current_program'):
                self.window.current_program.setStyleSheet(AppStyles.player_program_style())
            if hasattr(self.window, 'program_desc'):
                self.window.program_desc.setStyleSheet(AppStyles.player_program_desc_style())
            if hasattr(self.window, 'time_label'):
                self.window.time_label.setStyleSheet(AppStyles.player_time_badge_style())
            if hasattr(self.window, 'remain_label'):
                self.window.remain_label.setStyleSheet(AppStyles.player_status_badge_style())
            if hasattr(self.window, 'progress_start'):
                self.window.progress_start.setStyleSheet(AppStyles.player_progress_label_style())
            if hasattr(self.window, 'progress_end'):
                self.window.progress_end.setStyleSheet(AppStyles.player_progress_label_style())
            for tool_btn in fp.findChildren(QToolButton):
                tool_btn.setStyleSheet(AppStyles.player_button_style())

            if hasattr(self.window, 'volume_button'):
                vol = self.window.volume_slider.value() if hasattr(self.window, 'volume_slider') else 80
                icon_name = 'volume_mute' if vol == 0 else ('volume_low' if vol < 50 else 'volume')
                self.window.volume_button.setIcon(QIcon(AppStyles.get_icon(icon_name, btn_color)))
            icon_btn_map = {
                'stop_button': 'stop',
                'prev_ch_button': 'prev', 'next_ch_button': 'next',
                'speed_button': 'speed', 'aspect_button': 'aspect',
                'audio_track_button': 'audio_track', 'sub_track_button': 'subtitle',
                'pip_button': 'pip', 'fullscreen_button': 'fullscreen',
            }
            for attr, icon_name in icon_btn_map.items():
                btn = getattr(self.window, attr, None)
                if btn:
                    btn.setIcon(QIcon(AppStyles.get_icon(icon_name, btn_color)))
            play_btn = getattr(self.window, 'play_button', None)
            if play_btn:
                is_paused = hasattr(self.window, 'player_controller') and hasattr(self.window.player_controller, 'player') and self.window.player_controller.player.pause
                play_icon = 'pause' if is_paused else 'play'
                play_btn.setIcon(QIcon(AppStyles.get_icon(play_icon, btn_color)))
            if hasattr(self.window, 'exit_catchup_button'):
                self.window.exit_catchup_button.setStyleSheet(AppStyles.player_button_style())
                icon_path = AppStyles.get_icon('prev', btn_color)
                if icon_path:
                    self.window.exit_catchup_button.setIcon(QIcon(icon_path))
            if hasattr(self.window, 'catchup_indicator'):
                self.window.catchup_indicator.setStyleSheet(AppStyles.player_catchup_indicator_style())
            for slider in fp.findChildren(QSlider):
                slider.setStyleSheet(AppStyles.player_slider_style())
            if hasattr(self.window, 'volume_slider'):
                self.window.volume_slider.setStyleSheet(AppStyles.player_volume_slider_style())
            for combo in fp.findChildren(QComboBox):
                combo.setStyleSheet(AppStyles.player_group_combo_style())
            for frame in fp.findChildren(QFrame):
                if frame.styleSheet() and 'max-height' in frame.styleSheet():
                    frame.setStyleSheet(AppStyles.player_line_style())

            # 进度条滑块handle需要强制刷新
            progress_slider = getattr(self.window, 'progress_slider', None)
            if progress_slider:
                progress_slider.setStyleSheet(AppStyles.player_slider_style())
                progress_slider.update()

            # 重新设置控制面板中各QLabel的文字颜色（排除已单独处理的）
            for label in fp.findChildren(QLabel):
                name = label.objectName()
                if label is getattr(self.window, 'program_desc', None):
                    continue
                if label is getattr(self.window, 'current_program', None):
                    continue
                if name in ('channel_name', 'channel_logo',
                            'time_label', 'remain_label', 'progress_start', 'progress_end',
                            'video_info', 'audio_info', 'network_info', 'buffer_info',
                            'video_info_icon', 'audio_info_icon', 'network_info_icon',
                            'catchup_indicator'):
                    continue
                if label.pixmap() is not None:
                    continue
                existing = label.styleSheet()
                if existing and 'color:' in existing:
                    label.setStyleSheet(AppStyles.player_label_style())
        except Exception as e:
            logger.error(f"重新应用悬浮面板样式失败: {e}")

    def _on_logo_cache_loaded(self, url, pixmap):
        """台标加载完成的回调"""
        from core.log_manager import global_logger as logger
        from PyQt6.QtWidgets import QListWidget
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QIcon
        from PyQt6 import QtWidgets

        logger.debug(f"台标加载完成: {url[:50]}..., pixmap有效: {not pixmap.isNull()}")

        if self.window.current_channel:
            logo = self.window.current_channel.get('logo', '')
            if logo:
                logo = logo.strip('`"\'')
                if logo == url and hasattr(self.window, 'channel_logo'):
                    scaled = self.window._logo_cache_service.scale_logo_pixmap_to_fit(pixmap, self.window.channel_logo.width(), self.window.channel_logo.height())
                    self.window.channel_logo.setPixmap(scaled)
                    self.window.channel_logo.setText("")

        for list_widget in (self.window.sub_channel_list, self.window.local_channel_list):
            channels = self.window._sub_channels if list_widget is self.window.sub_channel_list else self.window._local_channels
            is_grid = list_widget.viewMode() == QListWidget.ViewMode.IconMode
            match_idx = None
            for ci, ch in enumerate(channels):
                ch_logo = ch.get('logo', '')
                if ch_logo:
                    ch_logo = ch_logo.strip('`"\'')
                    if ch_logo == url:
                        match_idx = ci
                        break

            if match_idx is None:
                continue
            for i in range(list_widget.count()):
                item = list_widget.item(i)
                if not item:
                    continue
                if item.data(Qt.ItemDataRole.UserRole) == match_idx:
                    if is_grid:
                        ch_url = channels[match_idx].get('url', '')
                        if self.window.player_controller and ch_url:
                            thumb_path = self.window.player_controller.get_thumbnail_path(ch_url)
                            if thumb_path:
                                break
                        scaled = pixmap.scaled(160, 90, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                        item.setIcon(QIcon(scaled))
                    else:
                        item_widget = list_widget.itemWidget(item)
                        if item_widget:
                            logo_label = item_widget.findChild(QtWidgets.QLabel, "channel_logo_label")
                            if logo_label:
                                scaled = self.window._logo_cache_service.scale_logo_pixmap_to_fit(
                                    pixmap,
                                    logo_label.width() if logo_label.width() > 0 else 34,
                                    logo_label.height() if logo_label.height() > 0 else 34
                                )
                                logo_label.setPixmap(scaled)
                    break

    def _set_log_level(self, level_name, level_value):
        from core.log_manager import global_logger
        from core.config_manager import ConfigManager
        global_logger.set_level(level_value)
        ConfigManager().set_value('UI', 'log_level', level_name)
        ConfigManager().save_config()
        global_logger.info(f"日志等级切换为: {level_name}")

    def setup_menu_bar(self, skip_recent_files=False):
        """设置菜单栏"""
        from PyQt6.QtWidgets import QMenuBar
        from PyQt6.QtGui import QAction
        from ui.styles import AppStyles
        from core.log_manager import global_logger as logger

        if hasattr(self.window, '_custom_menu_bar') and self.window._custom_menu_bar:
            menu_bar = self.window._custom_menu_bar
            menu_bar.clear()
        else:
            menu_bar = QMenuBar()
            menu_bar.setObjectName("customMenuBar")
            self.window._custom_menu_bar = menu_bar

        menu_bar.setStyleSheet(AppStyles.player_menu_bar_style())

        try:
            tr = self.window.language_manager.tr

            file_menu = menu_bar.addMenu(tr("menu_file", "File"))
            recent_menu = None
            if file_menu:
                open_playlist = QAction(tr("menu_open_playlist", "Open Playlist\tCtrl+O"), self.window)
                open_playlist.triggered.connect(self.window.open_playlist)
                file_menu.addAction(open_playlist)

                open_stream = QAction(tr("menu_open_stream", "Open Stream\tCtrl+U"), self.window)
                open_stream.triggered.connect(self.window._open_stream)
                file_menu.addAction(open_stream)

                open_video = QAction(tr("menu_open_video", "Open Video\tCtrl+Shift+O"), self.window)
                open_video.triggered.connect(self.window._open_video_file)
                file_menu.addAction(open_video)

                recent_menu = file_menu.addMenu(tr("menu_recent_open", "Recent"))

                save_as = QAction(tr("menu_save_as", "Save As...\tCtrl+S"), self.window)
                save_as.triggered.connect(self.window.save_as)
                file_menu.addAction(save_as)

                file_menu.addSeparator()

                exit_action = QAction(tr("menu_exit", "Exit\tCtrl+Q"), self.window)
                exit_action.triggered.connect(self.window.close)
                file_menu.addAction(exit_action)

            self.window.recent_menu = recent_menu

            if not skip_recent_files:
                self.window.update_recent_files_menu()

            playback_menu = menu_bar.addMenu(tr("menu_playback", "Playback"))

            prev_channel = QAction(tr("menu_prev_channel", "Previous Channel\t↑"), self.window)
            prev_channel.triggered.connect(lambda: self.window.event_handler._switch_channel(-1) if hasattr(self.window, 'event_handler') else None)
            playback_menu.addAction(prev_channel)

            next_channel = QAction(tr("menu_next_channel", "Next Channel\t↓"), self.window)
            next_channel.triggered.connect(lambda: self.window.event_handler._switch_channel(1) if hasattr(self.window, 'event_handler') else None)
            playback_menu.addAction(next_channel)

            back_channel = QAction(tr("menu_back_channel", "Switch Back\tBackspace"), self.window)
            back_channel.triggered.connect(lambda: self.window.switch_to_previous_channel() if hasattr(self.window, 'switch_to_previous_channel') else None)
            playback_menu.addAction(back_channel)

            playback_menu.addSeparator()

            play_pause = QAction(tr("menu_play_pause", "Play/Pause\tSpace"), self.window)
            play_pause.triggered.connect(lambda: self.window.playback_ctrl.toggle_play() if hasattr(self.window, 'playback_ctrl') else None)
            playback_menu.addAction(play_pause)

            stop_play = QAction(tr("menu_stop", "Stop\tEsc"), self.window)
            stop_play.triggered.connect(lambda: self.window.playback_ctrl.stop_playback() if hasattr(self.window, 'playback_ctrl') else None)
            playback_menu.addAction(stop_play)

            playback_menu.addSeparator()

            seek_back = QAction(tr("menu_seek_back", "Seek Back\t←"), self.window)
            seek_back.triggered.connect(lambda: self.window.event_handler._seek_relative(-10) if hasattr(self.window, 'event_handler') else None)
            playback_menu.addAction(seek_back)

            seek_forward = QAction(tr("menu_seek_forward", "Seek Forward\t→"), self.window)
            seek_forward.triggered.connect(lambda: self.window.event_handler._seek_relative(10) if hasattr(self.window, 'event_handler') else None)
            playback_menu.addAction(seek_forward)

            playback_menu.addSeparator()

            vol_up = QAction(tr("menu_vol_up", "Volume Up\tScroll Up"), self.window)
            vol_up.triggered.connect(lambda: self.window.event_handler._adjust_volume(5) if hasattr(self.window, 'event_handler') else None)
            playback_menu.addAction(vol_up)

            vol_down = QAction(tr("menu_vol_down", "Volume Down\tScroll Down"), self.window)
            vol_down.triggered.connect(lambda: self.window.event_handler._adjust_volume(-5) if hasattr(self.window, 'event_handler') else None)
            playback_menu.addAction(vol_down)

            mute_action = QAction(tr("menu_mute", "Mute\tCtrl+M"), self.window)
            mute_action.triggered.connect(lambda: self.window.toggle_mute() if hasattr(self.window, 'toggle_mute') else None)
            playback_menu.addAction(mute_action)

            playback_menu.addSeparator()

            speed_up = QAction(tr("menu_speed_up", "Speed Up\t."), self.window)
            speed_up.triggered.connect(lambda: self.window.media_ctrl.adjust_speed(0.1))
            playback_menu.addAction(speed_up)

            speed_down = QAction(tr("menu_speed_down", "Speed Down\t,"), self.window)
            speed_down.triggered.connect(lambda: self.window.media_ctrl.adjust_speed(-0.1))
            playback_menu.addAction(speed_down)

            playback_menu.addSeparator()

            screenshot = QAction(tr("menu_screenshot", "Screenshot\tS"), self.window)
            screenshot.triggered.connect(lambda: self.window.media_ctrl.take_screenshot())
            playback_menu.addAction(screenshot)

            playback_menu.addSeparator()

            audio_menu = playback_menu.addMenu(tr("ctx_audio_track", "Audio Track"))
            audio_menu.aboutToShow.connect(lambda: self.window.media_ctrl._populate_audio_menu(audio_menu))

            subtitle_menu = playback_menu.addMenu(tr("ctx_subtitle", "Subtitle"))
            subtitle_menu.aboutToShow.connect(lambda: self.window.media_ctrl._populate_subtitle_menu(subtitle_menu))

            view_menu = menu_bar.addMenu(tr("menu_view", "View"))

            show_epg = QAction(tr("menu_epg_list", "EPG List\tE"), self.window)
            show_epg.setCheckable(True)
            show_epg.setChecked(self.window.epg_visible)
            show_epg.triggered.connect(self.window.toggle_epg)
            view_menu.addAction(show_epg)
            self.window._epg_menu_action = show_epg

            show_playlist = QAction(tr("menu_playlist", "Playlist\tL"), self.window)
            show_playlist.setCheckable(True)
            show_playlist.setChecked(self.window.playlist_visible)
            show_playlist.triggered.connect(self.window.toggle_playlist)
            view_menu.addAction(show_playlist)
            self.window._playlist_menu_action = show_playlist

            show_floating = QAction(tr("menu_control_panel", "Control Panel\tM"), self.window)
            show_floating.setCheckable(True)
            show_floating.setChecked(self.window.floating_panel_visible)
            show_floating.triggered.connect(self.window.toggle_floating_panel)
            view_menu.addAction(show_floating)
            self.window._floating_menu_action = show_floating

            hide_all_floating = QAction(tr("menu_hide_floating", "Hide Floating Panels\tY"), self.window)
            hide_all_floating.triggered.connect(lambda: self.window.toggle_hide_floating())
            view_menu.addAction(hide_all_floating)
            self.window._hide_floating_action = hide_all_floating

            show_osd = QAction(tr("menu_osd_toggle", "OSD Mask\tTab"), self.window)
            show_osd.setCheckable(True)
            show_osd.setChecked(self.window._osd_visible)
            show_osd.triggered.connect(lambda c: self.window.toggle_osd(c))
            view_menu.addAction(show_osd)
            self.window._osd_menu_action = show_osd

            view_menu.addSeparator()

            fullscreen = QAction(tr("menu_fullscreen", "Fullscreen\tF11"), self.window)
            fullscreen.setCheckable(True)
            fullscreen.triggered.connect(self.window.toggle_fullscreen)
            view_menu.addAction(fullscreen)
            self.window._fullscreen_menu_action = fullscreen

            pip_action = QAction(tr("menu_pip", "Picture-in-Picture\tP"), self.window)
            pip_action.setCheckable(True)
            pip_action.triggered.connect(self.window.pip_ctrl.toggle)
            view_menu.addAction(pip_action)
            self.window._pip_menu_action = pip_action

            view_menu.addSeparator()
            multi_screen_menu = view_menu.addMenu(tr("menu_multi_screen", "Multi Screen"))

            ms_4 = QAction(tr("menu_multi_2x2", "2×2 (4 Screens)"), self.window)
            ms_4.triggered.connect(lambda: self.window.multi_screen_ctrl.toggle(4))
            multi_screen_menu.addAction(ms_4)

            ms_9 = QAction(tr("menu_multi_3x3", "3×3 (9 Screens)"), self.window)
            ms_9.triggered.connect(lambda: self.window.multi_screen_ctrl.toggle(9))
            multi_screen_menu.addAction(ms_9)

            ms_exit = QAction(tr("menu_multi_exit", "Exit Multi Screen"), self.window)
            ms_exit.triggered.connect(self.window.multi_screen_ctrl.exit_multi_screen)
            multi_screen_menu.addAction(ms_exit)

            refresh = QAction(tr("menu_refresh", "Refresh\tF5"), self.window)
            refresh.triggered.connect(self.window.refresh_ui)
            view_menu.addAction(refresh)

            reset_layout = QAction(tr("menu_reset_layout", "Reset Layout"), self.window)
            reset_layout.triggered.connect(self.window.reset_layout)
            view_menu.addAction(reset_layout)

            tools_menu = menu_bar.addMenu(tr("menu_tools", "Tools"))

            scan_channels = QAction(tr("menu_scan_channels", "Scan & Organize"), self.window)
            scan_channels.triggered.connect(self.window.open_scan_ui)
            tools_menu.addAction(scan_channels)

            channel_mapping = QAction(tr("menu_mapping", "Mapping"), self.window)
            channel_mapping.triggered.connect(self.window.open_channel_mapping)
            tools_menu.addAction(channel_mapping)

            tools_menu.addSeparator()

            player_settings = QAction(tr("menu_subscription_settings", "Subscription Settings"), self.window)
            player_settings.triggered.connect(self.window.player_settings)
            tools_menu.addAction(player_settings)

            tools_menu.addSeparator()

            file_assoc = QAction(tr("menu_file_association", "File Association"), self.window)
            file_assoc.triggered.connect(self.window._toggle_file_association)
            tools_menu.addAction(file_assoc)

            language_menu = menu_bar.addMenu(tr("language", "Language"))

            current_language = self.window.language_manager.current_language

            chinese = QAction(tr("chinese", "中文"), self.window)
            chinese.setCheckable(True)
            chinese.setChecked(current_language == "zh")
            chinese.triggered.connect(lambda: self.window.set_language("zh"))
            language_menu.addAction(chinese)

            english = QAction(tr("english", "English"), self.window)
            english.setCheckable(True)
            english.setChecked(current_language == "en")
            english.triggered.connect(lambda: self.window.set_language("en"))
            language_menu.addAction(english)

            from PyQt6.QtGui import QActionGroup
            lang_group = QActionGroup(self.window)
            lang_group.setExclusive(True)
            lang_group.addAction(chinese)
            lang_group.addAction(english)

            theme_menu = menu_bar.addMenu(tr("menu_theme", "Theme"))

            theme_manager = self.window._theme_manager

            color_mode_menu = theme_menu.addMenu(tr("menu_color_mode", "颜色模式"))
            color_modes = theme_manager.get_available_color_modes()
            color_mode_group = QActionGroup(self.window)
            color_mode_group.setExclusive(True)
            for mode in color_modes:
                display = tr(f"color_mode_{mode}", mode)
                action = QAction(display, self.window)
                action.setCheckable(True)
                action.setChecked(mode == theme_manager.get_color_mode())
                action.triggered.connect(lambda checked, m=mode: self.window.set_color_mode(m))
                color_mode_group.addAction(action)
                color_mode_menu.addAction(action)

            theme_menu.addSeparator()

            visual_style_menu = theme_menu.addMenu(tr("menu_visual_style", "视觉风格"))
            styles = theme_manager.get_available_visual_styles()
            style_group = QActionGroup(self.window)
            style_group.setExclusive(True)
            for style in styles:
                display = tr(f"visual_style_{style}", style)
                action = QAction(display, self.window)
                action.setCheckable(True)
                action.setChecked(style == theme_manager.get_visual_style())
                action.triggered.connect(lambda checked, s=style: self.window.set_visual_style(s))
                style_group.addAction(action)
                visual_style_menu.addAction(action)

            help_menu = menu_bar.addMenu(tr("menu_help", "Help"))

            usage_instructions = QAction(tr("menu_instructions", "Instructions"), self.window)
            usage_instructions.triggered.connect(self.window.show_usage_instructions)
            help_menu.addAction(usage_instructions)

            about = QAction(tr("menu_about", "About"), self.window)
            about.triggered.connect(self.window.show_about)
            help_menu.addAction(about)

            help_menu.addSeparator()
            try:
                log_menu = help_menu.addMenu(tr("menu_log_level", "日志等级"))

                import logging
                from core.log_manager import global_logger
                from core.config_manager import ConfigManager
                log_levels = [
                    ('DEBUG', logging.DEBUG, tr("log_level_debug", "调试")),
                    ('INFO', logging.INFO, tr("log_level_info", "信息")),
                    ('WARNING', logging.WARNING, tr("log_level_warning", "警告")),
                    ('ERROR', logging.ERROR, tr("log_level_error", "错误")),
                ]
                current_level_name = ConfigManager().get_value('UI', 'log_level', 'INFO')
                log_group = QActionGroup(self.window)
                log_group.setExclusive(True)
                for name, level, label in log_levels:
                    action = QAction(label, self.window)
                    action.setCheckable(True)
                    action.setChecked(name == current_level_name)
                    action.triggered.connect(lambda checked, n=name, l=level: self._set_log_level(n, l))
                    log_menu.addAction(action)
                    log_group.addAction(action)
                current_level = getattr(logging, current_level_name, logging.INFO)
                global_logger.set_level(current_level)
            except Exception:
                pass

        except Exception as e:
            logger.error(f"创建菜单栏失败: {str(e)}")

        if hasattr(self.window, '_custom_menu_bar') and self.window._custom_menu_bar and hasattr(self.window, 'main_layout'):
            if self.window._custom_menu_bar.parent() != self.window._main_container:
                self.window.main_layout.insertWidget(1, self.window._custom_menu_bar)