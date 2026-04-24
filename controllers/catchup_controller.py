"""
回看/时移控制器 - 管理EPG回看、时移模式的所有逻辑
从 pyqt_player.py 提取的独立模块
"""

import re


class CatchupController:
    """回看/时移控制器"""

    def __init__(self, main_window):
        self.window = main_window

    def replace_catchup_variables(self, catchup_source, start_time, end_time):
        """替换回看URL中的时间变量占位符"""
        if not catchup_source:
            return catchup_source

        url = catchup_source

        def format_time(dt, fmt):
            timezone = None
            base_fmt = fmt

            if '|utc' in fmt.lower() or ':utc' in fmt.lower():
                timezone = 'utc'
                base_fmt = re.split(r'[|:]', fmt)[0]
            elif '|local' in fmt.lower() or ':local' in fmt.lower():
                timezone = 'local'
                base_fmt = re.split(r'[|:]', fmt)[0]

            target_dt = dt
            if timezone == 'utc':
                import datetime as dt_module
                if dt.tzinfo is None:
                    utc_offset = dt_module.datetime.now() - dt_module.datetime.utcnow()
                    target_dt = dt - utc_offset
                else:
                    target_dt = dt.astimezone(dt_module.timezone.utc)
            elif timezone == 'local':
                target_dt = dt

            fmt_map = {
                'yyyy': target_dt.strftime('%Y'),
                'yy': target_dt.strftime('%y'),
                'MM': target_dt.strftime('%m'),
                'dd': target_dt.strftime('%d'),
                'HH': target_dt.strftime('%H'),
                'mm': target_dt.strftime('%M'),
                'ss': target_dt.strftime('%S'),
                'yyyyMMddHHmmss': target_dt.strftime('%Y%m%d%H%M%S'),
                'yyyyMMddHHmm': target_dt.strftime('%Y%m%d%H%M'),
                'yyyyMMdd': target_dt.strftime('%Y%m%d'),
                'HHmmss': target_dt.strftime('%H%M%S'),
                'HHmm': target_dt.strftime('%H%M'),
                'yyyy-MM-dd': target_dt.strftime('%Y-%m-%d'),
                'yyyy-MM-ddTHH:mm:ss': target_dt.strftime('%Y-%m-%dT%H:%M:%S'),
                'yyyy-MM-dd HH:mm:ss': target_dt.strftime('%Y-%m-%d %H:%M:%S'),
                'unix': str(int(target_dt.timestamp())),
                'unix_ms': str(int(target_dt.timestamp() * 1000)),
                '10': str(int(target_dt.timestamp())),
                '13': str(int(target_dt.timestamp() * 1000)),
            }
            return fmt_map.get(base_fmt, target_dt.strftime(base_fmt))

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

        replacements = {
            '${start}': start_ts, '${end}': end_ts,
            '${timestamp}': start_ts, '${start_utc}': start_ts, '${end_utc}': end_ts,
            '${start_ms}': start_ts_ms, '${end_ms}': end_ts_ms,
            '${offset}': start_ts,
            '${duration}': str(int((end_time - start_time).total_seconds())),
            '${duration_ms}': str(int((end_time - start_time).total_seconds() * 1000)),
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

    def start_catchup(self, program):
        """启动回看功能"""
        from core.log_manager import global_logger as logger
        from datetime import datetime

        if not self.window.current_channel:
            return

        channel_name = self.window.current_channel.get("name", "")
        tr = getattr(self.window.language_manager, 'tr', lambda x, y: x)
        catchup_source = self.window.current_channel.get('catchup_source', '')

        start_time = datetime.fromisoformat(program.get('start', ''))
        end_time = datetime.fromisoformat(program.get('end', ''))
        title = program.get('title', tr("unknown_program", "Unknown Program"))

        catchup_url = catchup_source
        if catchup_source:
            catchup_url = self.replace_catchup_variables(catchup_source, start_time, end_time)
            logger.debug(f"构建回看URL: {catchup_url}")

        catchup_template = tr('catchup_playing', '正在回看: {name}')
        self.window.status_bar_show_message(f"{catchup_template.format(name=channel_name)} - {title}")

        if self.window.player_controller:
            self.window.original_channel = self.window.current_channel.copy()
            self.window.catchup_program = {
                'start': start_time, 'end': end_time,
                'title': title, 'desc': program.get('desc', '')
            }
            self.window.is_catchup_mode = True

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

        if hasattr(self.window, 'original_channel') and self.window.original_channel:
            channel_name = self.window.original_channel.get("name", tr("unknown_channel", "Unknown Channel"))
            self.window.status_bar_show_message(f"{tr('back_to_live', 'Back to live')}: {channel_name}")
            self.window.play_channel(self.window.original_channel)

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
        """退出时移模式，取消暂停恢复直播"""
        from core.log_manager import global_logger as logger

        if hasattr(self.window, 'playback_ctrl'):
            self.window.playback_ctrl._exit_catchup_mode()

        if hasattr(self.window, 'program_progress') and self.window.program_progress:
            self._set_progress_range(100)
            self._set_progress_value(0)

        if self.window.player_controller:
            self.window.player_controller.pause()

        channel_name = self.window.current_channel.get("name", "") if self.window.current_channel else ""
        tr = getattr(self.window.language_manager, 'tr', lambda x, y: x)
        self.window.status_bar_show_message(f"{tr('back_to_live', 'Back to live')}: {channel_name}")

    def _set_progress_value(self, seconds):
        """设置进度条值（委托给主窗口）"""
        if hasattr(self.window, '_set_progress_value'):
            self.window._set_progress_value(seconds)

    def _set_progress_range(self, total):
        """设置进度条范围（委托给主窗口）"""
        if hasattr(self.window, '_set_progress_range'):
            self.window._set_progress_range(total)
