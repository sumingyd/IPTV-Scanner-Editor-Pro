"""
EPG节目单控制器 - 负责EPG数据管理、显示、交互
从 pyqt_player.py 提取的独立模块
"""

import sys
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta, date
from PyQt6.QtWidgets import QListWidgetItem, QDateEdit, QStyledItemDelegate, QStyleOptionViewItem
from PyQt6.QtGui import QAction, QColor, QPainter, QFontMetrics
from PyQt6.QtCore import Qt, QTimer

from core.log_manager import global_logger as logger


class EPGItemDelegate(QStyledItemDelegate):
    STATUS_COLORS = {
        'live': (QColor(231, 76, 60), QColor(255, 255, 255)),
        'past': (QColor(149, 165, 166, 160), QColor(255, 255, 255, 200)),
        'catchup': (QColor(52, 152, 219, 180), QColor(255, 255, 255)),
    }

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
        super().paint(painter, option, index)

        data = index.data(Qt.ItemDataRole.UserRole)
        if not data:
            return

        font = option.font
        fm = QFontMetrics(font)
        badges = []

        if data.get('is_live'):
            badges.append(('LIVE', 'live'))
        elif data.get('is_past'):
            badges.append(('✓', 'past'))

        if data.get('is_catchup'):
            badges.append((data.get('catchup_label', '↩'), 'catchup'))

        if not badges:
            return

        x = option.rect.right() - 4
        y = option.rect.top() + (option.rect.height() - (fm.height() + 4)) // 2

        painter.save()
        for text, status_type in reversed(badges):
            text_width = fm.horizontalAdvance(text) + 8
            text_height = fm.height() + 4
            bg_color, text_color = self.STATUS_COLORS.get(status_type, self.STATUS_COLORS['past'])
            bg_rect = type(option.rect)(x - text_width, y, text_width, text_height)

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(bg_color)
            painter.drawRoundedRect(bg_rect, 3, 3)

            painter.setPen(text_color)
            painter.setFont(font)
            painter.drawText(bg_rect, Qt.AlignmentFlag.AlignCenter, text)

            x -= text_width + 4
        painter.restore()


class EPGController:
    """EPG节目单控制器 - 管理电子节目单的所有逻辑"""

    def __init__(self, main_window):
        self.window = main_window
        self._current_date = None  # 当前显示的日期

    def populate_epg_list(self):
        """填充EPG列表"""
        if not hasattr(self.window, 'epg_content'):
            logger.debug("EPG列表组件不存在，跳过填充")
            return

        self.window.epg_content.clear()

        # 重新应用样式（确保样式正确）
        try:
            AppStyles = __import__('ui.styles', fromlist=['AppStyles']).AppStyles
            self.window.epg_content.setStyleSheet(AppStyles.player_list_style())
        except:
            pass

        # 检查是否有当前频道
        if not hasattr(self.window, 'current_channel') or not self.window.current_channel:
            if hasattr(self.window, 'epg_empty_label'):
                self.window.epg_empty_label.show()
            logger.debug("无当前频道，显示空EPG提示")
            return

        # 获取当前频道信息
        channel_name = self.window.current_channel.get("name", "")
        tvg_id = self.window.current_channel.get("tvg_id", "")
        all_tags = self.window.current_channel.get("_all_tags", {})
        tvg_name = all_tags.get("tvg-name", "")

        comma_name = ''
        raw_extinf = self.window.current_channel.get('_raw_extinf', '')
        if raw_extinf and ',' in raw_extinf:
            comma_name = raw_extinf.split(',', 1)[-1].strip()
            if comma_name.startswith('"') and comma_name.endswith('"'):
                comma_name = comma_name[1:-1]

        logger.debug(f"EPG填充: 频道名称={channel_name}, tvg_id={tvg_id}, tvg_name={tvg_name}, comma_name={comma_name}")

        epg_list = []

        if hasattr(self.window, 'epg_parser') and self.window.epg_parser:
            try:
                epg_list = self.window.epg_parser.get_channel_epg(
                    channel_name, tvg_id, tvg_name=tvg_name, comma_name=comma_name
                )
                if epg_list:
                    from datetime import datetime
                    epg_list.sort(key=lambda x: datetime.fromisoformat(x.get('start', '')))
                    logger.debug(f"EPG填充: 从epg_parser获取到 {len(epg_list)} 个节目")
                else:
                    logger.debug(f"EPG填充: epg_parser未找到频道 {channel_name} 的数据")
            except Exception as e:
                logger.error(f"从epg_parser获取EPG失败: {e}")

        # 如果epg_parser没有数据，尝试从全局变量EPG获取
        if not epg_list:
            try:
                import sys
                main_module = sys.modules.get('__main__')
                EPG_DATA = getattr(main_module, 'EPG_DATA', None) if main_module else None

                if EPG_DATA and channel_name in EPG_DATA:
                    current_channel_epg = EPG_DATA[channel_name]
                    if current_channel_epg and len(current_channel_epg) > 0:
                        epg_list = []
                        from datetime import datetime, timedelta
                        for program_data in current_channel_epg:
                            try:
                                time_str = program_data.get('time', '')
                                if time_str:
                                    time_parts = time_str.split('-')
                                    if len(time_parts) == 2:
                                        start_hour, start_minute = map(int, time_parts[0].split(':'))
                                        end_hour, end_minute = map(int, time_parts[1].split(':'))

                                        now = datetime.now()
                                        today = now.date()
                                        current_hour = now.hour

                                        start_date = today
                                        end_date = today

                                        if end_hour < start_hour:
                                            if current_hour < start_hour:
                                                start_date = today - timedelta(days=1)
                                            end_date = today + timedelta(days=1)

                                        start_datetime = datetime.combine(start_date, datetime.min.time())
                                        start_datetime = start_datetime.replace(hour=start_hour, minute=start_minute)

                                        end_datetime = datetime.combine(end_date, datetime.min.time())
                                        end_datetime = end_datetime.replace(hour=end_hour, minute=end_minute)

                                        program = {
                                            'title': program_data.get('title', 'Unknown Program'),
                                            'desc': program_data.get('description', ''),
                                            'start': start_datetime.isoformat(),
                                            'end': end_datetime.isoformat(),
                                            'catchup_source': program_data.get('catchup_source', '')
                                        }
                                        epg_list.append(program)
                            except Exception as ex:
                                logger.warning(f"处理EPG节目失败: {ex}")
                                continue

                        if epg_list:
                            from datetime import datetime
                            epg_list.sort(key=lambda x: datetime.fromisoformat(x.get('start', '')))
                            logger.debug(f"从EPG_DATA获取到 {len(epg_list)} 个节目")
            except Exception as e:
                logger.error(f"从EPG_DATA获取数据失败: {e}")

        # 填充EPG列表
        if epg_list:
            # 按日期过滤：只显示当前选中日期的节目（默认今天）
            from datetime import datetime, date as date_type
            target_date = getattr(self.window, 'current_epg_date', None) or date_type.today()

            filtered_list = []
            for program in epg_list:
                start_str = program.get('start', '')
                if start_str:
                    try:
                        prog_date = datetime.fromisoformat(start_str).date()
                        if prog_date == target_date:
                            filtered_list.append(program)
                    except (ValueError, TypeError):
                        filtered_list.append(program)

            today = date_type.today()
            is_browsing_other_date = (target_date != today)

            if not filtered_list:
                if is_browsing_other_date:
                    logger.info(f"EPG: {target_date} 无节目数据")
                else:
                    logger.info(f"EPG: 今天无节目数据")
            else:
                logger.debug(f"EPG: 按日期 {target_date} 过滤，{len(epg_list)} -> {len(filtered_list)} 个节目")

            if hasattr(self.window, 'epg_empty_label'):
                if not filtered_list and is_browsing_other_date:
                    self.window.epg_empty_label.show()
                else:
                    self.window.epg_empty_label.hide()

            tr = getattr(self.window.language_manager, 'tr', lambda x, y: x) if hasattr(self.window, 'language_manager') else lambda x, y: x

            # 显示层去重：防止漏网的重复节目
            seen = set()
            deduped_list = []
            for program in filtered_list:
                key = (program.get('start', ''), program.get('title', ''))
                if key not in seen:
                    seen.add(key)
                    deduped_list.append(program)
            if len(deduped_list) < len(filtered_list):
                logger.debug(f"EPG显示层去重: {len(filtered_list)} -> {len(deduped_list)} 个节目")
            filtered_list = deduped_list

            # 获取当前时间用于判断节目状态
            now = datetime.now()

            channel_supports_catchup = bool(
                self.window.current_channel.get('catchup_source', '')
            ) if hasattr(self.window, 'current_channel') and self.window.current_channel else False

            for program in filtered_list:
                item = QListWidgetItem()

                start_time = program.get('start', '')
                end_time = program.get('end', '')
                title = program.get('title', '')

                # 格式化时间显示
                start_display = ''
                end_display = ''
                start_dt = None
                end_dt = None

                if start_time:
                    try:
                        start_dt = datetime.fromisoformat(start_time)
                        start_display = start_dt.strftime('%H:%M')
                    except:
                        start_display = start_time[:5] if len(start_time) >= 5 else start_time

                if end_time:
                    try:
                        end_dt = datetime.fromisoformat(end_time)
                        end_display = end_dt.strftime('%H:%M')
                    except:
                        end_display = end_time[:5] if len(end_time) >= 5 else end_time

                # 判断节目播放状态并添加状态标识
                status_text = ""
                is_past_program = False
                is_live = False
                if start_dt and end_dt:
                    if now < start_dt:
                        status_text = tr("epg_status_upcoming", "")
                    elif now > end_dt:
                        status_text = tr("epg_status_finished", "")
                        is_past_program = True
                    else:
                        status_text = tr("epg_status_live", "LIVE")
                        is_live = True

                display_text = f"{start_display} - {end_display}  {title}"
                item.setText(display_text)

                is_catchup = is_past_program and channel_supports_catchup

                item.setData(Qt.ItemDataRole.UserRole, {
                    'channel': channel_name,
                    'program': program,
                    'status': status_text,
                    'start_dt': start_dt,
                    'end_dt': end_dt,
                    'is_catchup': is_catchup,
                    'catchup_label': tr('catchup_available', '可回放') if is_catchup else '',
                    'is_live': is_live,
                    'is_past': is_past_program,
                })

                self.window.epg_content.addItem(item)

            logger.debug(f"EPG列表填充完成，共 {len(filtered_list)} 个节目")

            # 自动定位到当前正在播放的节目（使用过滤后的列表，确保索引匹配）
            self._scroll_to_current_program(filtered_list, now)
        else:
            if hasattr(self.window, 'epg_empty_label'):
                self.window.epg_empty_label.show()
            logger.debug(f"频道 {channel_name} 无EPG数据")

    def on_epg_item_clicked(self, item: QListWidgetItem):
        """处理EPG列表项点击事件"""
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return
            
        program = data.get('program')
        if not program:
            return
        
        from core.log_manager import global_logger as logger
        from datetime import datetime
        
        # 判断节目状态
        start_str = program.get('start', '')
        end_str = program.get('end', '')
        now = datetime.now()
        
        is_past_program = False
        if start_str and end_str:
            try:
                start_dt = datetime.fromisoformat(start_str)
                end_dt = datetime.fromisoformat(end_str)
                # 已结束或正在播放的节目都可以回看
                if end_dt < now or (start_dt <= now <= end_dt):
                    is_past_program = True
            except (ValueError, TypeError):
                pass
        
        # 检查当前频道是否支持回看功能
        channel_catchup = ''
        if hasattr(self.window, 'current_channel') and self.window.current_channel:
            channel_catchup = self.window.current_channel.get('catchup_source', '')
        
        # 如果是已播放/已结束的节目且频道支持回看，启动回看
        if is_past_program and channel_catchup and hasattr(self.window, 'start_catchup'):
            logger.info(f"用户点击EPG节目 '{program.get('title')}'，启动回看")
            self.window.start_catchup(program)
        elif not channel_catchup:
            logger.debug(f"频道不支持回看功能（无 catchup_source）")
        elif not is_past_program:
            logger.debug(f"点击的是未来节目，暂不支持预约播放")

    def update_epg_date_display(self):
        """更新EPG日期显示"""
        if not hasattr(self.window, 'current_epg_date'):
            return

        from datetime import date, timedelta
        today = date.today()

        if self.window.current_epg_date:
            # 更新日期标签显示
            if hasattr(self.window, 'epg_date_label'):
                if self.window.current_epg_date == today:
                    tr = getattr(self.window.language_manager, 'tr', lambda x, y: x)
                    self.window.epg_date_label.setText(tr("today", "Today"))
                elif self.window.current_epg_date == today - timedelta(days=1):
                    tr = getattr(self.window.language_manager, 'tr', lambda x, y: x)
                    self.window.epg_date_label.setText(tr("yesterday", "Yesterday"))
                elif self.window.current_epg_date == today + timedelta(days=1):
                    tr = getattr(self.window.language_manager, 'tr', lambda x, y: x)
                    self.window.epg_date_label.setText(tr("tomorrow", "Tomorrow"))
                else:
                    self.window.epg_date_label.setText(self.window.current_epg_date.strftime("%Y-%m-%d"))

    def on_prev_day(self):
        """切换到前一天"""
        from datetime import timedelta
        if not hasattr(self.window, 'current_epg_date') or not self.window.current_epg_date:
            return

        self.window.current_epg_date -= timedelta(days=1)
        self.update_epg_date_display()
        # 重新加载该日期的EPG数据
        if hasattr(self.window, 'populate_epg_list'):
            self.window.populate_epg_list()

    def on_next_day(self):
        """切换到后一天"""
        from datetime import timedelta
        if not hasattr(self.window, 'current_epg_date') or not self.window.current_epg_date:
            return

        self.window.current_epg_date += timedelta(days=1)
        self.update_epg_date_display()
        # 重新加载该日期的EPG数据
        if hasattr(self.window, 'populate_epg_list'):
            self.window.populate_epg_list()

    def _scroll_to_current_program(self, epg_list: list, now):
        """自动滚动到当前正在播放的节目"""
        if not epg_list or not hasattr(self.window, 'epg_content'):
            return

        from core.log_manager import global_logger as logger

        # 查找当前正在播放的节目（或即将开始的下一个节目）
        current_index = -1
        for i, program in enumerate(epg_list):
            start_str = program.get('start', '')
            end_str = program.get('end', '')
            
            try:
                start_dt = datetime.fromisoformat(start_str) if start_str else None
                end_dt = datetime.fromisoformat(end_str) if end_str else None
                
                if start_dt and end_dt:
                    if start_dt <= now <= end_dt:
                        # 正在播放的节目
                        current_index = i
                        break
                    elif start_dt > now and current_index == -1:
                        # 记录第一个未开始的节目作为备选
                        current_index = i
            except (ValueError, TypeError):
                continue

        # 如果没有找到，默认显示前几个节目
        if current_index < 0:
            current_index = 0

        # 使用 QTimer 延迟滚动，确保 UI 已渲染完成
        from PyQt6.QtCore import QTimer
        
        def do_scroll():
            if hasattr(self.window, 'epg_content') and self.window.epg_content.count() > current_index:
                item = self.window.epg_content.item(current_index)
                if item:
                    # 使用 PositionAtCenter 让当前播放的节目显示在列表中间
                    self.window.epg_content.scrollToItem(
                        item,
                        self.window.epg_content.ScrollHint.PositionAtCenter
                    )
                    logger.debug(f"EPG已定位到第 {current_index + 1} 个节目（居中显示）")

        QTimer.singleShot(100, do_scroll)

    def _load_epg_for_date(self, date):
        """加载指定日期的EPG数据"""
        # TODO: 实现按日期加载EPG数据的逻辑
        # 这里需要调用EPG服务获取指定日期的数据
        pass

    def toggle_epg(self, checked: bool):
        """切换EPG面板显示/隐藏"""
        if hasattr(self.window, 'epg_panel'):
            self.window.epg_panel.setVisible(checked)
            self.window.epg_visible = checked
            for action in self.window.findChildren(QAction):
                if action.text() and ('EPG' in action.text() or '节目' in action.text()) and action.isCheckable():
                    action.blockSignals(True)
                    action.setChecked(checked)
                    action.blockSignals(False)
                    break

    @property
    def has_epg_data(self) -> bool:
        """是否有EPG数据"""
        return hasattr(self.window, 'epg_data') and len(self.window.epg_data) > 0

    @property
    def current_program_count(self) -> int:
        """当前显示的节目数量"""
        if not hasattr(self.window, 'epg_data'):
            return 0
        return sum(len(progs) for progs in self.window.epg_data.values())
