import re
from datetime import datetime, timedelta, timezone
from core.play_state import PlayMode
from controllers.main_window_protocol import MainWindowProtocol


class CatchupController:

    CATCHUP_TYPES = {
        'default', 'append', 'shift', 'flussonic', 'fs',
        'xc', 'xtream', 'vod', 'timemachine'
    }

    def __init__(self, main_window: MainWindowProtocol):
        self.window: MainWindowProtocol = main_window
        self._original_channel: dict | None = None
        self._catchup_program: dict | None = None

    @property
    def original_channel(self) -> dict | None:
        return self._original_channel

    @original_channel.setter
    def original_channel(self, value: dict | None):
        self._original_channel = value
        self.window.original_channel = value

    @property
    def catchup_program(self) -> dict | None:
        return self._catchup_program

    @catchup_program.setter
    def catchup_program(self, value: dict | None):
        self._catchup_program = value
        self.window.catchup_program = value

    def _enter_catchup_state(self, channel: dict, program: dict, mode: PlayMode = PlayMode.CATCHUP):
        self.original_channel = channel.copy()
        self.catchup_program = program
        self.window.play_state.mode = mode
        self.window._live_timeshift_seconds = 0

    def _clear_catchup_state(self, set_state='idle'):
        self._original_channel = None
        self._catchup_program = None
        if set_state == 'live':
            self.window.play_state.set_live()
        elif set_state == 'idle':
            self.window.play_state.set_idle()
        self.window._live_timeshift_seconds = 0
        self.window.catchup_program = None

    def replace_catchup_variables(self, catchup_source, start_time, end_time):
        if not catchup_source:
            return catchup_source

        url = catchup_source

        def apply_timezone_offset(dt, offset_str):
            if not offset_str:
                return dt
            offset_str = offset_str.strip()
            if offset_str.lower() == 'utc':
                if dt.tzinfo is None:
                    local_tz = datetime.now().astimezone().tzinfo
                    dt = dt.replace(tzinfo=local_tz)
                return dt.astimezone(timezone.utc).replace(tzinfo=None)
            if offset_str.lower() == 'local':
                return dt
            m = re.match(r'^([+-])(\d{1,2}):?(\d{2})$', offset_str)
            if m:
                sign = 1 if m.group(1) == '+' else -1
                hours = int(m.group(2))
                minutes = int(m.group(3))
                offset = timedelta(hours=hours, minutes=minutes) * sign
                target_tz = timezone(offset)
                if dt.tzinfo is None:
                    local_tz = datetime.now().astimezone().tzinfo
                    dt = dt.replace(tzinfo=local_tz)
                return dt.astimezone(target_tz).replace(tzinfo=None)
            return dt

        def format_time(dt, fmt):
            timezone_spec = None
            base_fmt = fmt

            parts = re.split(r'[|]', fmt, maxsplit=1)
            if len(parts) > 1:
                base_fmt = parts[0]
                timezone_spec = parts[1]
            elif ':utc' in fmt.lower():
                timezone_spec = 'utc'
                base_fmt = re.split(r'[:]', fmt, maxsplit=1)[0]
            elif ':local' in fmt.lower():
                timezone_spec = 'local'
                base_fmt = re.split(r'[:]', fmt, maxsplit=1)[0]

            target_dt = dt
            if timezone_spec:
                target_dt = apply_timezone_offset(dt, timezone_spec)

            fmt_map = {
                'yyyyMMddHHmmss': target_dt.strftime('%Y%m%d%H%M%S'),
                'yyyyMMddHHmm': target_dt.strftime('%Y%m%d%H%M'),
                'yyyyMMdd': target_dt.strftime('%Y%m%d'),
                'HHmmss': target_dt.strftime('%H%M%S'),
                'HHmm': target_dt.strftime('%H%M'),
                'yyyy-MM-dd': target_dt.strftime('%Y-%m-%d'),
                'yyyy-MM-ddTHH:mm:ss': target_dt.strftime('%Y-%m-%dT%H:%M:%S'),
                'yyyy-MM-dd HH:mm:ss': target_dt.strftime('%Y-%m-%d %H:%M:%S'),
                'yyyy': target_dt.strftime('%Y'),
                'yy': target_dt.strftime('%y'),
                'MM': target_dt.strftime('%m'),
                'dd': target_dt.strftime('%d'),
                'HH': target_dt.strftime('%H'),
                'mm': target_dt.strftime('%M'),
                'ss': target_dt.strftime('%S'),
                'unix': str(int(target_dt.timestamp())),
                'unix_ms': str(int(target_dt.timestamp() * 1000)),
                '10': str(int(target_dt.timestamp())),
                '13': str(int(target_dt.timestamp() * 1000)),
            }
            if base_fmt in fmt_map:
                result = fmt_map[base_fmt]
            else:
                try:
                    py_fmt = base_fmt
                    py_fmt = py_fmt.replace('yyyy', '%Y')
                    py_fmt = py_fmt.replace('yy', '%y')
                    py_fmt = py_fmt.replace('MM', '%m')
                    py_fmt = py_fmt.replace('dd', '%d')
                    py_fmt = py_fmt.replace('HH', '%H')
                    py_fmt = py_fmt.replace('mm', '%M')
                    py_fmt = py_fmt.replace('ss', '%S')
                    result = target_dt.strftime(py_fmt)
                except Exception:
                    result = target_dt.strftime('%Y%m%d%H%M%S')
            return result

        def replace_braced_vars(url, dt, prefix):
            for m in re.finditer(r'\$\{\(' + re.escape(prefix) + r'\)([^}]+)\}', url):
                fmt = m.group(1)
                replacement = format_time(dt, fmt)
                url = url.replace(m.group(0), replacement)
            return url

        url = replace_braced_vars(url, start_time, 'b')
        url = replace_braced_vars(url, end_time, 'e')
        url = replace_braced_vars(url, start_time, 'start')
        url = replace_braced_vars(url, end_time, 'end')

        start_ts = str(int(start_time.timestamp()))
        end_ts = str(int(end_time.timestamp()))
        start_ts_ms = str(int(start_time.timestamp() * 1000))
        end_ts_ms = str(int(end_time.timestamp() * 1000))
        duration_sec = int((end_time - start_time).total_seconds())

        replacements = {
            '${start}': start_ts, '${end}': end_ts,
            '${timestamp}': start_ts, '${start_utc}': start_ts, '${end_utc}': end_ts,
            '${start_ms}': start_ts_ms, '${end_ms}': end_ts_ms,
            '${offset}': start_ts,
            '${duration}': str(duration_sec),
            '${duration_ms}': str(duration_sec * 1000),
            '{start}': start_ts, '{end}': end_ts,
            '{timestamp}': start_ts, '{offset}': start_ts,
        }
        for placeholder, value in replacements.items():
            url = url.replace(placeholder, value)

        date_fields = [
            ('${start_year}', '%Y'), ('${start_month}', '%m'), ('${start_day}', '%d'),
            ('${start_hour}', '%H'), ('${start_minute}', '%M'), ('${start_second}', '%S'),
            ('${end_year}', '%Y'), ('${end_month}', '%m'), ('${end_day}', '%d'),
            ('${end_hour}', '%H'), ('${end_minute}', '%M'), ('${end_second}', '%S'),
        ]
        for placeholder, fmt in date_fields:
            url = url.replace(placeholder, (start_time if 'start' in placeholder else end_time).strftime(fmt))

        return url

    def build_catchup_url(self, channel, start_time, end_time):
        from core.log_manager import global_logger as logger

        catchup_type = (channel.get('catchup', '') or '').lower().strip()
        catchup_source = channel.get('catchup_source', '')
        catchup_correction = channel.get('catchup_correction', '')
        live_url = channel.get('url', '')

        logger.debug(f"build_catchup_url: type={catchup_type}, correction={catchup_correction}, "
                     f"start={start_time}, end={end_time}, "
                     f"start_ts={int(start_time.timestamp())}, end_ts={int(end_time.timestamp())}")

        if catchup_correction:
            try:
                offset = float(catchup_correction)
                tz_offset = timezone(timedelta(hours=offset))
                local_tz = start_time.astimezone().tzinfo if start_time.tzinfo else datetime.now().astimezone().tzinfo
                start_time = start_time.replace(tzinfo=local_tz).astimezone(tz_offset).replace(tzinfo=None)
                end_time = end_time.replace(tzinfo=local_tz).astimezone(tz_offset).replace(tzinfo=None)
            except (ValueError, TypeError):
                pass

        if catchup_source:
            catchup_url = self.replace_catchup_variables(catchup_source, start_time, end_time)
        else:
            catchup_url = ''

        if catchup_type == 'append':
            if catchup_url:
                if catchup_url.startswith('?') or catchup_url.startswith('&'):
                    return live_url + catchup_url
                sep = '&' if '?' in live_url else '?'
                return live_url + sep + catchup_url
            return live_url

        elif catchup_type in ('flussonic', 'fs'):
            if catchup_url:
                return catchup_url
            ts_start = int(start_time.timestamp())
            ts_end = int(end_time.timestamp())
            return f"{live_url}/{ts_start}-{ts_end}.m3u8"

        elif catchup_type in ('xc', 'xtream'):
            if catchup_url:
                return catchup_url
            ts_start = int(start_time.timestamp())
            ts_end = int(end_time.timestamp())
            duration = int((end_time - start_time).total_seconds())
            sep = '&' if '?' in live_url else '?'
            return f"{live_url}{sep}start={ts_start}&end={ts_end}&duration={duration}"

        elif catchup_type == 'shift':
            if catchup_url:
                return catchup_url
            offset = int((datetime.now() - start_time).total_seconds())
            sep = '&' if '?' in live_url else '?'
            return f"{live_url}{sep}timeshift={offset}"

        elif catchup_type in ('default', 'vod', 'timemachine', ''):
            return catchup_url if catchup_url else live_url

        return catchup_url if catchup_url else live_url

    def start_catchup(self, program):
        from core.log_manager import global_logger as logger

        if not self.window.current_channel:
            return

        channel_name = self.window.current_channel.get("name", "")
        tr = getattr(self.window.language_manager, 'tr', lambda x, y: x)

        start_str = program.get('start', '')
        end_str = program.get('end', '')
        if not start_str or not end_str:
            logger.warning(f"回看节目缺少时间信息: start={start_str!r}, end={end_str!r}")
            return
        try:
            start_time = datetime.fromisoformat(start_str)
            end_time = datetime.fromisoformat(end_str)
        except (ValueError, TypeError) as e:
            logger.warning(f"回看节目时间格式无效: {e}")
            return
        title = program.get('title', tr("unknown_program", "Unknown Program"))

        catchup_url = self.build_catchup_url(self.window.current_channel, start_time, end_time)
        logger.debug(f"构建回看URL: {catchup_url}")

        if not catchup_url or not catchup_url.strip():
            logger.warning(f"回看URL构建失败: channel={channel_name}, catchup_source={self.window.current_channel.get('catchup_source', '')!r}")
            no_support_msg = tr('catchup_not_supported', '该频道不支持回看')
            self.window.status_bar_show_message(no_support_msg)
            return

        catchup_template = tr('catchup_playing', '正在回看: {name}')
        self.window.status_bar_show_message(f"{catchup_template.format(name=channel_name)} - {title}")

        if self.window.player_controller:
            self._enter_catchup_state(self.window.current_channel, {
                'start': start_time, 'end': end_time,
                'title': title, 'desc': program.get('desc', '')
            }, mode=PlayMode.CATCHUP)

            if hasattr(self.window, '_cancel_source_timeout'):
                self.window._cancel_source_timeout()

            if hasattr(self.window, 'video_placeholder') and self.window.video_placeholder:
                self.window.video_placeholder.hide()
            if hasattr(self.window, 'video_widget') and self.window.video_widget and self.window.video_frame:
                self.window.video_widget.setGeometry(0, 0, self.window.video_frame.width(), self.window.video_frame.height())
            if hasattr(self.window, 'floating_panel') and self.window.floating_panel:
                self.window.floating_panel.raise_()

            for attr in ['_catchup_start_time', '_catchup_start_progress',
                         '_target_catchup_progress', '_disable_progress_auto_update']:
                if hasattr(self.window, attr):
                    setattr(self.window, attr, None if 'time' in attr or 'progress' in attr else False)

            if hasattr(self.window, 'program_progress'):
                self._set_progress_value(0)

            if hasattr(self.window, 'speed_button') and self.window.player_controller:
                current_speed = self.window.player_controller.get_speed()
                if abs(current_speed - 1.0) > 0.01:
                    self.window.player_controller.set_speed(1.0)
                    self.window.speed_button.setText("1.0x")

            self.window.player_controller.play(catchup_url, f"{channel_name} - {title} (回看)")
            self.add_exit_catchup_button()
            if hasattr(self.window, 'media_ctrl'):
                self.window.media_ctrl.update_catchup_indicator()
            if hasattr(self.window, '_populate_epg_list'):
                self.window._populate_epg_list()

    def add_exit_catchup_button(self):
        from core.log_manager import global_logger as logger

        if hasattr(self.window, 'exit_catchup_button') and self.window.exit_catchup_button:
            try:
                tr = getattr(self.window.language_manager, 'tr', lambda x, y: x)
                self.window.exit_catchup_button.setText(tr("exit_catchup", "退出回看"))
                self.window.exit_catchup_button.show()
                self.window.exit_catchup_button.raise_()
                logger.debug("退出回看按钮已显示")
            except Exception as e:
                logger.error(f"显示退出回看按钮失败: {e}")

    def exit_catchup(self):
        from datetime import datetime, timedelta
        from core.log_manager import global_logger as logger

        saved_original_channel = self.original_channel or self.window.current_channel

        if hasattr(self.window, 'playback_ctrl'):
            self.window.playback_ctrl._exit_catchup_mode()

        self.window.current_epg_date = datetime.now().date()
        if hasattr(self.window, 'epg_ctrl'):
            self.window.epg_ctrl.update_epg_date_display()

        if hasattr(self.window, '_populate_epg_list'):
            self.window._populate_epg_list()

        if saved_original_channel:
            tr = self.window.language_manager.tr
            channel_name = saved_original_channel.get("name", tr("unknown_channel", "Unknown Channel"))
            self.window.status_bar_show_message(f"{tr('back_to_live', 'Back to live')}: {channel_name}")
            self.window.current_channel = saved_original_channel
            self.window.play_channel(saved_original_channel)
            if hasattr(self.window, 'update_channel_info_on_selection'):
                self.window.update_channel_info_on_selection()

        self._clear_catchup_state()

    def show_exit_timeshift_button(self):
        from core.log_manager import global_logger as logger

        if hasattr(self.window, 'exit_catchup_button') and self.window.exit_catchup_button:
            try:
                tr = getattr(self.window.language_manager, 'tr', lambda x, y: x)
                self.window.exit_catchup_button.setText(tr("exit_timeshift", "退出时移"))
                self.window.exit_catchup_button.show()
                self.window.exit_catchup_button.raise_()
                logger.debug("退出时移按钮已显示")
            except Exception as e:
                logger.error(f"显示退出时移按钮失败: {e}")

    def exit_timeshift(self):
        from core.log_manager import global_logger as logger

        saved_original = self.original_channel or self.window.current_channel

        if hasattr(self.window, 'playback_ctrl'):
            self.window.playback_ctrl._exit_catchup_mode()

        if hasattr(self.window, 'program_progress') and self.window.program_progress:
            self._set_progress_range(3600)
            self._set_progress_value(0)

        channel_name = self.window.current_channel.get("name", "") if self.window.current_channel else ""
        tr = getattr(self.window.language_manager, 'tr', lambda x, y: x)
        self.window.status_bar_show_message(f"{tr('back_to_live', 'Back to live')}: {channel_name}")

        if saved_original and hasattr(self.window, 'play_channel'):
            self.window.current_channel = saved_original
            self.window.play_channel(saved_original)
            if hasattr(self.window, 'update_channel_info_on_selection'):
                self.window.update_channel_info_on_selection()
        elif self.window.player_controller and self.window.current_channel:
            url = self.window.current_channel.get('url', '')
            if url:
                self.window.player_controller.play(url, channel_name)

        self._clear_catchup_state()

    def _set_progress_value(self, seconds):
        if hasattr(self.window, '_set_progress_value'):
            self.window._set_progress_value(seconds)

    def _set_progress_range(self, total):
        if hasattr(self.window, '_set_progress_range'):
            self.window._set_progress_range(total)

    def seek_catchup(self, position):
        w = self.window
        if self.catchup_program is None or self.original_channel is None:
            from core.log_manager import global_logger as logger
            logger.error("回看模式但缺少必要信息")
            w.status_bar.showMessage(w.language_manager.tr("catchup_error", "Catchup error: Missing information"))
            return

        try:
            from core.log_manager import global_logger as logger
            from datetime import timedelta, datetime

            if self._try_mpv_seek(position):
                return

            channel_name = self.original_channel.get("name", w.language_manager.tr("unknown_channel", "Unknown Channel"))
            title = self.catchup_program.get('title', w.language_manager.tr('unknown_program', 'Unknown Program'))

            catchup_source = self.original_channel.get('catchup_source', '')
            catchup_type = (self.original_channel.get('catchup', '') or '').lower().strip()

            if not catchup_source and not catchup_type:
                w.status_bar_show_message(w.language_manager.tr("catchup_not_supported", "This channel does not support catchup"))
                return

            start_time = self.catchup_program.get('start')
            end_time = self.catchup_program.get('end')

            if not (start_time and end_time):
                logger.error("回看节目信息不完整")
                w.status_bar.showMessage(w.language_manager.tr("catchup_error", "Catchup error: Missing program information"))
                return

            new_start_time = start_time + timedelta(seconds=position)
            now = datetime.now()

            if new_start_time >= end_time:
                ch_name, tvg_id, tvg_name, comma_name = w._get_epg_match_params()
                current_program = w.epg_parser.get_current_program(ch_name, tvg_id, tvg_name=tvg_name, comma_name=comma_name)
                if current_program:
                    new_program_start = datetime.fromisoformat(current_program.get('start', ''))
                    new_program_end = datetime.fromisoformat(current_program.get('end', ''))
                    if new_start_time >= new_program_start and new_start_time < new_program_end:
                        start_time = new_program_start
                        end_time = new_program_end
                        self.catchup_program = {
                            'start': start_time, 'end': end_time,
                            'title': current_program.get('title', title),
                            'desc': current_program.get('desc', ''),
                        }
                        w._progress_program_start = start_time
                        w._progress_program_end = end_time
                        total_duration = int((end_time - start_time).total_seconds())
                        if total_duration > 0:
                            self._set_progress_range(total_duration)
                        position = (new_start_time - start_time).total_seconds()
                        new_start_time = start_time + timedelta(seconds=position)
                        logger.info(f"时移跨节目 -> 新节目 {start_time}~{end_time}, position={position:.0f}s")

            new_end_time = end_time
            if new_start_time >= new_end_time:
                new_start_time = min(new_start_time, now - timedelta(seconds=5))
                new_end_time = max(new_end_time, now)
                logger.info(f"时移超范围 -> 限制到 {new_start_time}~{new_end_time}")

            if new_end_time - new_start_time < timedelta(seconds=30):
                new_end_time = new_start_time + timedelta(minutes=30)
                logger.info(f"时移窗口过短 -> 扩展endTime到 {new_end_time}")

            catchup_url = self.build_catchup_url(self.original_channel, new_start_time, new_end_time)

            logger.info(f"时移重新构建URL -> new_start={new_start_time}, end={new_end_time}, url={catchup_url}")

            catchup_msg = w.language_manager.tr('catchup_playing', '正在回看: {name}')
            w.status_bar.showMessage(f"{catchup_msg.format(name=channel_name)} - {title}")

            w._pending_catchup_progress = position

            import time as _time
            w._catchup_start_time = _time.time()
            w._catchup_start_progress = position

            if hasattr(w, 'player_controller') and w.player_controller:
                w.player_controller.play(catchup_url, f"{channel_name} - {title} (回看)")
        except Exception as e:
            from core.log_manager import global_logger as logger
            logger.error(f"重新构建回看 URL 失败：{e}")
            w.status_bar.showMessage(w.language_manager.tr("catchup_seek_error", "Catchup seek failed"))

    def _try_mpv_seek(self, position):
        w = self.window
        from core.log_manager import global_logger as logger

        if not hasattr(w, 'player_controller') or not w.player_controller:
            return False
        if not w.player_controller.is_playing:
            return False

        catchup_start_progress = getattr(w, '_catchup_start_progress', None)
        if catchup_start_progress is None:
            return False

        target_mpv_pos = position - catchup_start_progress
        if target_mpv_pos < 0:
            return False

        seek_range = w.player_controller.get_available_seek_range()
        buffer_start = seek_range.get('buffer_start', 0)
        buffer_end = seek_range.get('buffer_end', 0)
        time_pos = seek_range.get('time_pos', 0)
        cache_duration = seek_range.get('cache_duration', 0)

        if cache_duration < 2 and buffer_end <= buffer_start:
            return False

        if target_mpv_pos < buffer_start:
            logger.info(f"回看seek超出缓冲区前部: target_mpv={target_mpv_pos:.1f}s < buffer_start={buffer_start:.1f}s, 需重建URL")
            return False

        if target_mpv_pos > buffer_end + 5:
            logger.info(f"回看seek超出缓冲区后部: target_mpv={target_mpv_pos:.1f}s > buffer_end={buffer_end:.1f}s, 需重建URL")
            return False

        target_mpv_pos = max(buffer_start, min(target_mpv_pos, buffer_end))

        if abs(target_mpv_pos - time_pos) < 0.5:
            logger.debug(f"回看seek跳过: target_mpv={target_mpv_pos:.1f}s 与当前位置{time_pos:.1f}s差<0.5s")
            return True

        logger.info(f"回看MPV seek: position={position:.1f}s -> target_mpv={target_mpv_pos:.1f}s "
                    f"(start_progress={catchup_start_progress:.1f}s, time_pos={time_pos:.1f}s)")

        w.player_controller.seek_absolute(target_mpv_pos)

        import time as _time
        w._catchup_start_time = _time.time()
        w._catchup_start_progress = position

        return True

    def start_live_timeshift_from_progress(self, slider_seconds, catchup_source):
        w = self.window
        from datetime import timedelta, datetime
        from core.log_manager import global_logger as logger

        program_start = w._progress_program_start
        program_end = w._progress_program_end

        if program_start is None:
            logger.warning("直播时移(进度条) -> program_start 为 None，无法执行时移")
            return

        target_wallclock = program_start + timedelta(seconds=slider_seconds)
        now = datetime.now()

        if target_wallclock >= now:
            target_wallclock = now - timedelta(seconds=5)

        if target_wallclock < program_start:
            target_wallclock = program_start

        end_time = program_end if program_end else now

        timeshift_url = self.build_catchup_url(w.current_channel, target_wallclock, end_time)

        channel_name = w.current_channel.get('name', '')
        program_title = ''
        try:
            ch_name, tvg_id, tvg_name, comma_name = w._get_epg_match_params()
            prog = w.epg_parser.get_current_program(ch_name, tvg_id, tvg_name=tvg_name, comma_name=comma_name)
            if prog:
                program_title = prog.get('title', '')
        except Exception as e:
            logger.debug(f"EPG获取节目标题失败: {e}")

        offset_from_start = int((target_wallclock - program_start).total_seconds())
        m, s = divmod(offset_from_start, 60)
        h, m = divmod(m, 60)
        offset_str = f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"

        logger.info(f"直播时移(进度条) -> 从 {target_wallclock} 开始播放，offset={offset_str}, url={timeshift_url}")

        tr = w.language_manager.tr
        w.status_bar_show_message(
            f"{tr('timeshift_playing', '正在时移')}: {channel_name}"
            + (f" - {program_title}" if program_title else "")
            + f"  [{offset_str}]"
        )

        if hasattr(w, '_cancel_source_timeout'):
            w._cancel_source_timeout()

        if hasattr(w, 'video_placeholder') and w.video_placeholder:
            w.video_placeholder.hide()
        if hasattr(w, 'video_widget') and w.video_widget and w.video_frame:
            w.video_widget.setGeometry(0, 0, w.video_frame.width(), w.video_frame.height())
        if hasattr(w, 'floating_panel') and w.floating_panel:
            if not w.floating_panel.isVisible():
                w.floating_panel.show()

        for attr in ['_target_catchup_progress', '_disable_progress_auto_update']:
            if hasattr(w, attr):
                setattr(w, attr, False)

        offset_seconds = int((target_wallclock - program_start).total_seconds())
        import time as _time
        w._catchup_start_time = _time.time()
        w._catchup_start_progress = offset_seconds

        w._timeshift_start_time = target_wallclock
        w.play_state.set_timeshift()
        w._live_timeshift_seconds = max(0, (datetime.now() - target_wallclock).total_seconds())
        self.original_channel = w.current_channel.copy()
        self.catchup_program = {
            'start': program_start,
            'end': end_time,
            'title': program_title or tr('timeshift_label', '时移'),
            'desc': '',
        }

        total_duration = int((end_time - program_start).total_seconds())
        if total_duration > 0:
            self._set_progress_range(total_duration)
            self._set_progress_value(offset_seconds)
            w._progress_time_mode = 'epg'
            w._progress_program_start = program_start
            w._progress_program_end = end_time

        if w.player_controller:
            w.player_controller.play(timeshift_url, f"{channel_name} (时移 {offset_str})")
        w._show_exit_timeshift_button()
        w.media_ctrl.update_catchup_indicator()
        w._populate_epg_list()
