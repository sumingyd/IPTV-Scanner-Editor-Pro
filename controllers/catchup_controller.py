"""
回看/时移控制器 - 管理EPG回看、时移模式的所有逻辑
从 pyqt_player.py 提取的独立模块
"""

import re
from datetime import datetime, timedelta, timezone


class CatchupController:
    """回看/时移控制器"""

    CATCHUP_TYPES = {
        'default', 'append', 'shift', 'flussonic', 'fs',
        'xc', 'xtream', 'vod', 'timemachine'
    }

    def __init__(self, main_window):
        self.window = main_window
        self._is_catchup_mode: bool = False
        self._original_channel: dict | None = None
        self._catchup_program: dict | None = None

    # ---- 状态属性（读写均操作 controller，并同步到 window） ----

    @property
    def is_catchup_mode(self) -> bool:
        return self._is_catchup_mode

    @is_catchup_mode.setter
    def is_catchup_mode(self, value: bool):
        self._is_catchup_mode = value
        self.window.is_catchup_mode = value

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

    def _enter_catchup_state(self, channel: dict, program: dict):
        """进入回看状态，集中设置所有状态字段"""
        self.original_channel = channel.copy()
        self.catchup_program = program
        self.is_catchup_mode = True

    def _clear_catchup_state(self):
        """清除回看状态"""
        self._is_catchup_mode = False
        self._original_channel = None
        self._catchup_program = None
        self.window.is_catchup_mode = False
        self.window._is_timeshift_mode = False
        self.window._live_timeshift_seconds = 0
        self.window.catchup_program = None

    def replace_catchup_variables(self, catchup_source, start_time, end_time):
        """替换回看URL中的时间变量占位符

        支持的变量格式:
        - ${(b)format} / ${(e)format} : 开始/结束时间
        - ${(start)format} / ${(end)format} : 同上
        - ${start} / ${end} : Unix时间戳
        - ${start_ms} / ${end_ms} : 毫秒时间戳
        - ${duration} / ${duration_ms} : 持续时间
        - ${(b)format|offset} : 带时区偏移，如 |-08:00 或 |+05:30
        - ${(b)format|utc} / ${(b)format|local} : UTC/本地时区

        支持的catchup类型:
        - default: catchup-source 为完整回看URL
        - append: catchup-source 附加到直播URL后
        - shift: 基于时移的回看
        - flussonic/fs: Flussonic服务器回看格式
        - xc/xtream: Xtream Codes回看格式
        """
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
        """根据频道的catchup类型构建回看URL

        Args:
            channel: 频道数据字典
            start_time: 回看开始时间
            end_time: 回看结束时间

        Returns:
            构建好的回看URL
        """
        catchup_type = (channel.get('catchup', '') or '').lower().strip()
        catchup_source = channel.get('catchup_source', '')
        catchup_correction = channel.get('catchup_correction', '')
        live_url = channel.get('url', '')

        # 应用 catchup-correction 时区偏移
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
        """启动回看功能"""
        from core.log_manager import global_logger as logger

        if not self.window.current_channel:
            return

        channel_name = self.window.current_channel.get("name", "")
        tr = getattr(self.window.language_manager, 'tr', lambda x, y: x)

        start_time = datetime.fromisoformat(program.get('start', ''))
        end_time = datetime.fromisoformat(program.get('end', ''))
        title = program.get('title', tr("unknown_program", "Unknown Program"))

        catchup_url = self.build_catchup_url(self.window.current_channel, start_time, end_time)
        logger.debug(f"构建回看URL: {catchup_url}")

        catchup_template = tr('catchup_playing', '正在回看: {name}')
        self.window.status_bar_show_message(f"{catchup_template.format(name=channel_name)} - {title}")

        if self.window.player_controller:
            self._enter_catchup_state(self.window.current_channel, {
                'start': start_time, 'end': end_time,
                'title': title, 'desc': program.get('desc', '')
            })

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
            if hasattr(self.window, '_update_catchup_indicator'):
                self.window._update_catchup_indicator()
            if hasattr(self.window, '_populate_epg_list'):
                self.window._populate_epg_list()

    def add_exit_catchup_button(self):
        """显示退出回看按钮"""
        from core.log_manager import global_logger as logger

        if hasattr(self.window, 'exit_catchup_button') and self.window.exit_catchup_button:
            try:
                self.window.exit_catchup_button.show()
                self.window.exit_catchup_button.raise_()
                logger.debug("退出回看按钮已显示")
            except Exception as e:
                logger.error(f"显示退出回看按钮失败: {e}")

    def exit_catchup(self):
        """退出回看，返回直播"""
        from datetime import datetime, timedelta
        from core.log_manager import global_logger as logger

        if hasattr(self.window, 'playback_ctrl'):
            self.window.playback_ctrl._exit_catchup_mode()

        self.window.current_epg_date = datetime.now().date()
        today = datetime.now().date()
        tr = getattr(self.window.language_manager, 'tr', lambda x, y: x)
        if hasattr(self.window, 'epg_date_label'):
            if self.window.current_epg_date == today:
                self.window.epg_date_label.setText(tr("today", "Today"))
            elif self.window.current_epg_date == today - timedelta(days=1):
                self.window.epg_date_label.setText(tr("yesterday", "Yesterday"))
            elif self.window.current_epg_date == today + timedelta(days=1):
                self.window.epg_date_label.setText(tr("tomorrow", "Tomorrow"))
            else:
                self.window.epg_date_label.setText(self.window.current_epg_date.strftime("%Y-%m-%d"))

        if hasattr(self.window, '_populate_epg_list'):
            self.window._populate_epg_list()

        if self.original_channel:
            channel_name = self.original_channel.get("name", tr("unknown_channel", "Unknown Channel"))
            self.window.status_bar_show_message(f"{tr('back_to_live', 'Back to live')}: {channel_name}")
            self.window.current_channel = self.original_channel
            self.window.play_channel(self.original_channel)
            if hasattr(self.window, 'update_channel_info_on_selection'):
                self.window.update_channel_info_on_selection()

        self._clear_catchup_state()

    def show_exit_timeshift_button(self):
        """显示退出时移按钮"""
        from core.log_manager import global_logger as logger

        if hasattr(self.window, 'exit_catchup_button') and self.window.exit_catchup_button:
            try:
                tr = getattr(self.window.language_manager, 'tr', lambda x, y: x)
                self.window.exit_catchup_button.setText(tr("exit_timeshift", "⏪ 退出时移"))
                self.window.exit_catchup_button.show()
                self.window.exit_catchup_button.raise_()
                logger.debug("退出时移按钮已显示")
            except Exception as e:
                logger.error(f"显示退出时移按钮失败: {e}")

    def on_timeshift_slider_seek(self):
        """时移模式下拖动进度条"""
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
        """退出时移模式，停止时移播放并恢复直播"""
        from core.log_manager import global_logger as logger

        if hasattr(self.window, 'playback_ctrl'):
            self.window.playback_ctrl._exit_catchup_mode()

        if hasattr(self.window, 'program_progress') and self.window.program_progress:
            self._set_progress_range(100)
            self._set_progress_value(0)

        channel_name = self.window.current_channel.get("name", "") if self.window.current_channel else ""
        tr = getattr(self.window.language_manager, 'tr', lambda x, y: x)
        self.window.status_bar_show_message(f"{tr('back_to_live', 'Back to live')}: {channel_name}")

        # 恢复直播：重新播放原始直播频道
        original = self.original_channel or self.window.current_channel
        if original and hasattr(self.window, 'play_channel'):
            self.window.current_channel = original
            self.window.play_channel(original)
            if hasattr(self.window, 'update_channel_info_on_selection'):
                self.window.update_channel_info_on_selection()
        elif self.window.player_controller and self.window.current_channel:
            url = self.window.current_channel.get('url', '')
            if url:
                self.window.player_controller.play(url, channel_name)

        self._clear_catchup_state()

    def _set_progress_value(self, seconds):
        """设置进度条值（委托给主窗口）"""
        if hasattr(self.window, '_set_progress_value'):
            self.window._set_progress_value(seconds)

    def _set_progress_range(self, total):
        """设置进度条范围（委托给主窗口）"""
        if hasattr(self.window, '_set_progress_range'):
            self.window._set_progress_range(total)
