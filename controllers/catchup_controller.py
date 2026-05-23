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

    def _clear_catchup_state(self):
        self._original_channel = None
        self._catchup_program = None
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
        catchup_type = (channel.get('catchup', '') or '').lower().strip()
        catchup_source = channel.get('catchup_source', '')
        catchup_correction = channel.get('catchup_correction', '')
        live_url = channel.get('url', '')

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
                    delattr(self.window, attr)

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

    def on_timeshift_slider_seek(self):
        from core.log_manager import global_logger as logger

        new_offset = int(self.window.program_progress.value())
        max_shift = getattr(self.window, '_ts_max_shift', 300)
        new_offset = max(0, min(new_offset, max_shift))

        current_offset = getattr(self.window, '_ts_current_offset', 0)
        delta = new_offset - current_offset
        self.window._ts_current_offset = new_offset

        logger.info(f"时移模式拖动: {current_offset}s -> {new_offset}s (delta={delta:+d}s)")
        self.window.player_controller.seek_relative_seconds(delta)

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
