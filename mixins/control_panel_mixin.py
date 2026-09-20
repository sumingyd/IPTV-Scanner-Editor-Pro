from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QToolButton, QSlider, QSizePolicy, QDockWidget,
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon

from core.log_manager import global_logger as logger
from ui.styles import AppStyles



class ControlPanelMixin:
    """从 IPTVPlayer 提取的底部控制面板UI构建职责"""

    def _create_bottom_panel(self, show=True):
        """创建底部悬浮控制面板"""
        logger.debug("_create_bottom_panel: 开始")

        self._create_panel(show=show)

        logger.debug("_create_bottom_panel: 完成")

    def _create_panel(self, show=True):
        """创建底部控制面板（QDockWidget 停靠底部）"""
        logger.debug("_create_panel: 开始")
        tr = self.language_manager.tr

        floating_container = QWidget()
        floating_container.setObjectName("panelContainer")
        floating_container.setStyleSheet("background-color: transparent;")
        floating_container.setMinimumHeight(120)
        floating_container.setMinimumWidth(360)
        floating_container.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.floating_layout = QVBoxLayout(floating_container)
        self.floating_layout.setContentsMargins(8, 8, 8, 8)
        self.floating_layout.setSpacing(3)

        self._create_media_row()

        from ui.floating_dialog import FloatingDockWidget
        self.floating_dock = FloatingDockWidget(tr("control_panel", "Control Panel"), self)
        self.floating_dock.setWidget(floating_container)
        self.floating_dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetClosable | QDockWidget.DockWidgetFeature.DockWidgetMovable | QDockWidget.DockWidgetFeature.DockWidgetFloatable)
        self.floating_dock.setObjectName("floating_dock")
        if hasattr(self, 'floating_panel'):
            self.floating_panel = None
        self.floating_panel = self.floating_dock

        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.floating_dock)
        self.floating_dock.setFloating(True)
        if not show:
            self.floating_dock.hide()

        logger.debug("_create_panel: 完成")

    def _set_info_label_icon(self, icon_label: QLabel, icon_name: str):
        """设置信息行前的小图标"""
        color = AppStyles.get_color('player_panel_text')
        icon_path = AppStyles.get_icon(icon_name, color, 16)
        if icon_path:
            from PySide6.QtGui import QPixmap
            pixmap = QPixmap(icon_path)
            if not pixmap.isNull():
                icon_label.setPixmap(pixmap)
                icon_label.setFixedSize(16, 16)
                icon_label.setAlignment(Qt.AlignmentFlag.AlignVCenter)

    def _create_media_row(self):
        """创建媒体信息行"""
        logger.debug("_create_media_row: 开始")
        tr = self.language_manager.tr

        self.media_row = QHBoxLayout()
        self.media_row.setSpacing(6)

        self.video_info_icon = QLabel()
        self.video_info_icon.setStyleSheet("background: transparent; border: none;")
        self._set_info_label_icon(self.video_info_icon, 'tv')
        self.media_row.addWidget(self.video_info_icon)

        self.video_info = QLabel()
        self.video_info.setStyleSheet(AppStyles.player_media_badge_style())
        self.video_info.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.video_info.setFixedHeight(22)
        self.video_info.setToolTip(tr('tooltip_video_info', '视频信息'))
        self.video_info.setText(tr('not_playing', 'Not playing'))
        self.media_row.addWidget(self.video_info)

        self.hdr_badge = QLabel()
        self.hdr_badge.setStyleSheet(AppStyles.player_hdr_badge_style())
        self.hdr_badge.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.hdr_badge.setFixedHeight(22)
        self.hdr_badge.setToolTip(tr('tooltip_hdr', 'HDR状态'))
        self.hdr_badge.hide()
        self.media_row.addWidget(self.hdr_badge)

        self.media_row.addSpacing(6)

        self.audio_info_icon = QLabel()
        self.audio_info_icon.setStyleSheet("background: transparent; border: none;")
        self._set_info_label_icon(self.audio_info_icon, 'speaker')
        self.media_row.addWidget(self.audio_info_icon)

        self.audio_info = QLabel()
        self.audio_info.setStyleSheet(AppStyles.player_media_badge_style())
        self.audio_info.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.audio_info.setFixedHeight(22)
        self.audio_info.setToolTip(tr('tooltip_audio_info', '音频信息'))
        self.audio_info.setText("--")
        self.media_row.addWidget(self.audio_info)

        self.media_row.addSpacing(6)

        self.network_info_icon = QLabel()
        self.network_info_icon.setStyleSheet("background: transparent; border: none;")
        self._set_info_label_icon(self.network_info_icon, 'signal')
        self.media_row.addWidget(self.network_info_icon)

        self.network_info = QLabel()
        self.network_info.setStyleSheet(AppStyles.player_media_badge_style())
        self.network_info.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.network_info.setFixedHeight(22)
        self.network_info.setToolTip(tr('tooltip_network_info', '网络信息'))
        self.network_info.setText("--")
        self.media_row.addWidget(self.network_info)

        self.buffer_info = QLabel("")
        self.buffer_info.setStyleSheet(AppStyles.player_media_badge_style())
        self.buffer_info.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.buffer_info.setFixedHeight(22)
        self.buffer_info.setToolTip(tr('tooltip_buffer_info', '缓冲信息'))
        self.buffer_info.hide()
        self.media_row.addWidget(self.buffer_info)

        self.media_row.addStretch()
        self.floating_layout.addLayout(self.media_row)

        line1 = QFrame()
        line1.setFrameShape(QFrame.Shape.HLine)
        line1.setStyleSheet(AppStyles.player_line_style())
        self.floating_layout.addWidget(line1)

        self._create_info_row()

        logger.debug("_create_media_row: 完成")

    def _create_info_row(self):
        """创建节目信息行"""
        logger.debug("_create_info_row: 开始")
        tr = self.language_manager.tr

        info_layout = QHBoxLayout()
        info_layout.setSpacing(12)

        self.channel_logo = QLabel()
        self.channel_logo.setStyleSheet(AppStyles.player_channel_logo_style())
        self.channel_logo.setFixedSize(self.CHANNEL_LOGO_WIDTH, self.CHANNEL_LOGO_HEIGHT)
        self.channel_logo.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter)
        from utils.general_utils import set_default_channel_logo
        set_default_channel_logo(self.channel_logo, 100, 36)
        info_layout.addWidget(self.channel_logo, 0, Qt.AlignmentFlag.AlignVCenter)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        text_layout.setContentsMargins(0, 0, 0, 0)

        row1 = QHBoxLayout()
        row1.setSpacing(8)
        self.channel_name = QLabel(tr("no_channel_selected", "No channel selected"))
        self.channel_name.setStyleSheet(AppStyles.player_channel_name_style())
        row1.addWidget(self.channel_name, 0)
        self.current_program = QLabel("")
        self.current_program.setObjectName("current_program")
        self.current_program.setStyleSheet(AppStyles.player_program_style())
        self.current_program.setAutoFillBackground(False)
        self.current_program.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.current_program.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        row1.addWidget(self.current_program, 1)
        self.time_label = QLabel("--:-- - --:--")
        self.time_label.setStyleSheet(AppStyles.player_time_badge_style())
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row1.addWidget(self.time_label, 0)
        self.catchup_indicator = QLabel("")
        self.catchup_indicator.setStyleSheet(AppStyles.player_catchup_indicator_style())
        self.catchup_indicator.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.catchup_indicator.hide()
        row1.addWidget(self.catchup_indicator, 0)
        self.remain_label = QLabel(tr("waiting_to_play", "Waiting to play..."))
        self.remain_label.setStyleSheet(AppStyles.player_status_badge_style())
        self.remain_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.remain_label.setMinimumWidth(70)
        row1.addWidget(self.remain_label, 0)
        text_layout.addLayout(row1)

        self.program_desc = QLabel(tr("open_playlist_or_import", "Open a playlist file or import channels to start watching"))
        self.program_desc.setObjectName("program_desc")
        self.program_desc.setStyleSheet(AppStyles.player_program_desc_style())
        self.program_desc.setAutoFillBackground(False)
        self.program_desc.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.program_desc.setWordWrap(True)
        self.program_desc.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.program_desc.setFixedHeight(self.PROGRAM_DESC_HEIGHT)
        self.program_desc.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        # 空态引导 CTA：文案为引导语时可点击打开订阅；业务描述更新无需感知
        self.program_desc.setCursor(Qt.CursorShape.PointingHandCursor)
        self.program_desc.setToolTip(tr("tooltip_open_playlist_cta", "点击打开订阅文件"))
        self.program_desc.mousePressEvent = self._on_program_desc_clicked
        self.program_desc.enterEvent = self._on_program_desc_enter
        text_layout.addWidget(self.program_desc, 0, Qt.AlignmentFlag.AlignTop)

        info_layout.addLayout(text_layout)

        info_widget = QWidget()
        info_widget.setLayout(info_layout)
        info_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.floating_layout.addWidget(info_widget)

        line2 = QFrame()
        line2.setFrameShape(QFrame.Shape.HLine)
        line2.setStyleSheet(AppStyles.player_line_style())
        self.floating_layout.addWidget(line2)

        self._create_control_row()

        logger.debug("_create_info_row: 完成")

    def _create_control_row(self):
        """创建控制行"""
        logger.debug("_create_control_row: 开始")
        tr = self.language_manager.tr

        self.control_row = QHBoxLayout()
        self.control_row.setSpacing(8)

        btn_color = AppStyles.get_color('player_panel_text')
        btn_icon_size = QSize(20, 20)
        self.prev_ch_button = QToolButton()
        self.prev_ch_button.setIcon(QIcon(AppStyles.get_icon('prev', btn_color)))  # type: ignore[arg-type]
        self.prev_ch_button.setIconSize(btn_icon_size)
        self.prev_ch_button.setFixedSize(self.CTRL_BUTTON_WIDTH, self.CTRL_BUTTON_HEIGHT)
        self.prev_ch_button.setStyleSheet(AppStyles.player_button_style())
        self.prev_ch_button.clicked.connect(lambda: getattr(self, 'event_handler', None) and self.event_handler._switch_channel(-1))
        self.prev_ch_button.setToolTip(tr("panel_prev_ch", "上一频道"))
        self.control_row.addWidget(self.prev_ch_button)

        self.play_button = QToolButton()
        self.play_button.setIcon(QIcon(AppStyles.get_icon('play', btn_color)))  # type: ignore[arg-type]
        self.play_button.setIconSize(btn_icon_size)
        self.play_button.setFixedSize(self.CTRL_BUTTON_WIDTH, self.CTRL_BUTTON_HEIGHT)
        self.play_button.setStyleSheet(AppStyles.player_button_style())
        self.play_button.clicked.connect(self.toggle_play)
        self.play_button.setToolTip(tr("panel_play", "播放/暂停"))
        self.control_row.addWidget(self.play_button)

        self.next_ch_button = QToolButton()
        self.next_ch_button.setIcon(QIcon(AppStyles.get_icon('next', btn_color)))  # type: ignore[arg-type]
        self.next_ch_button.setIconSize(btn_icon_size)
        self.next_ch_button.setFixedSize(self.CTRL_BUTTON_WIDTH, self.CTRL_BUTTON_HEIGHT)
        self.next_ch_button.setStyleSheet(AppStyles.player_button_style())
        self.next_ch_button.clicked.connect(lambda: getattr(self, 'event_handler', None) and self.event_handler._switch_channel(1))
        self.next_ch_button.setToolTip(tr("panel_next_ch", "下一频道"))
        self.control_row.addWidget(self.next_ch_button)

        self.stop_button = QToolButton()
        self.stop_button.setIcon(QIcon(AppStyles.get_icon('stop', btn_color)))  # type: ignore[arg-type]
        self.stop_button.setIconSize(btn_icon_size)
        self.stop_button.setFixedSize(self.CTRL_BUTTON_WIDTH, self.CTRL_BUTTON_HEIGHT)
        self.stop_button.setStyleSheet(AppStyles.player_button_style())
        self.stop_button.clicked.connect(self.stop_playback)
        self.stop_button.setToolTip(tr("panel_stop", "停止"))
        self.control_row.addWidget(self.stop_button)

        self.progress_group = QHBoxLayout()
        self.progress_group.setSpacing(4)

        self.progress_start = QLabel("--:--")
        self.progress_start.setStyleSheet(AppStyles.player_progress_label_style())
        self.progress_group.addWidget(self.progress_start)

        from ui.cache_progress_slider import CacheProgressSlider
        self.program_progress = CacheProgressSlider(Qt.Orientation.Horizontal)
        self.program_progress.setRange(0, 3600)
        self.program_progress.setValue(0)
        self.program_progress.setSingleStep(1)
        self.program_progress.setPageStep(30)
        self.program_progress.setStyleSheet(AppStyles.player_slider_style())
        self.program_progress.set_cache_color(AppStyles._get_colors().get('player_cache_bar', 'rgba(76,175,80,0.4)'))
        self.program_progress.setToolTip(tr("panel_progress", "节目进度"))
        self.program_progress.sliderReleased.connect(self.on_progress_slider_released)
        self.program_progress.sliderPressed.connect(self._on_progress_slider_pressed)
        self.program_progress.preview_position_changed.connect(self._on_progress_preview)
        self._progress_total_seconds = 3600
        self.progress_group.addWidget(self.program_progress, 1)

        self.progress_end = QLabel("--:--")
        self.progress_end.setStyleSheet(AppStyles.player_progress_label_style())
        self.progress_group.addWidget(self.progress_end)

        self.control_row.addLayout(self.progress_group, 1)

        self.volume_button = QToolButton()
        self.volume_button.setIcon(QIcon(AppStyles.get_icon('volume', btn_color)))  # type: ignore[arg-type]
        self.volume_button.setIconSize(btn_icon_size)
        self.volume_button.setFixedSize(36, 32)
        self.volume_button.setStyleSheet(AppStyles.player_button_style())
        self.volume_button.clicked.connect(self.toggle_mute)
        self.volume_button.setToolTip(tr("panel_volume", "音量"))
        self.control_row.addWidget(self.volume_button)

        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(80)
        self.volume_slider.setFixedWidth(90)
        self.volume_slider.setStyleSheet(AppStyles.player_volume_slider_style())
        self.volume_slider.setToolTip(tr("panel_volume_slider", "音量调节"))
        self.volume_slider.valueChanged.connect(self.set_volume)
        self.control_row.addWidget(self.volume_slider)

        self.exit_catchup_button = QToolButton()
        self.exit_catchup_button.setIcon(QIcon(AppStyles.get_icon('exit_catchup', btn_color)))  # type: ignore[arg-type]
        self.exit_catchup_button.setIconSize(btn_icon_size)

        self.exit_catchup_button.setFixedSize(36, 32)
        self.exit_catchup_button.setStyleSheet(AppStyles.player_button_style())
        self.exit_catchup_button.clicked.connect(self.exit_catchup)
        self.exit_catchup_button.setToolTip(tr("panel_exit_catchup", "退出回看"))
        self.exit_catchup_button.hide()
        # 按钮保留为成员以兼容旧引用，但不单独上屏——统一收入“更多”菜单

        self.speed_button = QToolButton()
        self.speed_button.setIcon(QIcon(AppStyles.get_icon('speed', btn_color)))  # type: ignore[arg-type]
        self.speed_button.setIconSize(btn_icon_size)
        self.speed_button.setText("1.0x")
        self.speed_button.setFixedSize(50, 32)
        self.speed_button.setStyleSheet(AppStyles.player_button_style())
        self.speed_button.clicked.connect(self.media_ctrl.show_speed_menu)
        self.speed_button.setToolTip(tr("panel_speed", "播放速度"))

        self.aspect_button = QToolButton()
        self.aspect_button.setIcon(QIcon(AppStyles.get_icon('aspect', btn_color)))  # type: ignore[arg-type]
        self.aspect_button.setIconSize(btn_icon_size)
        self.aspect_button.setFixedSize(36, 32)
        self.aspect_button.setStyleSheet(AppStyles.player_button_style())
        self.aspect_button.clicked.connect(self.media_ctrl.show_aspect_menu)
        self.aspect_button.setToolTip(tr("panel_aspect", "画面比例"))

        self.audio_track_button = QToolButton()
        self.audio_track_button.setIcon(QIcon(AppStyles.get_icon('audio_track', btn_color)))  # type: ignore[arg-type]
        self.audio_track_button.setIconSize(btn_icon_size)
        self.audio_track_button.setToolTip(self.language_manager.tr("panel_audio_track", "Audio Track"))
        self.audio_track_button.setFixedSize(36, 32)
        self.audio_track_button.setStyleSheet(AppStyles.player_button_style())
        self.audio_track_button.clicked.connect(self.media_ctrl.show_audio_track_menu)

        self.sub_track_button = QToolButton()
        self.sub_track_button.setIcon(QIcon(AppStyles.get_icon('subtitle', btn_color)))  # type: ignore[arg-type]
        self.sub_track_button.setIconSize(btn_icon_size)
        self.sub_track_button.setToolTip(self.language_manager.tr("panel_subtitle", "Subtitle"))
        self.sub_track_button.setFixedSize(36, 32)
        self.sub_track_button.setStyleSheet(AppStyles.player_button_style())
        self.sub_track_button.clicked.connect(self.media_ctrl.show_sub_track_menu)

        self.pip_button = QToolButton()
        self.pip_button.setIcon(QIcon(AppStyles.get_icon('pip', btn_color)))  # type: ignore[arg-type]
        self.pip_button.setIconSize(btn_icon_size)
        self.pip_button.setFixedSize(self.CTRL_BUTTON_WIDTH, self.CTRL_BUTTON_HEIGHT)
        self.pip_button.setStyleSheet(AppStyles.player_button_style())
        self.pip_button.clicked.connect(self.pip_ctrl.toggle)
        self.pip_button.setToolTip(tr("panel_pip", "画中画"))

        self._create_more_menu()

        self.more_button = QToolButton()
        self.more_button.setIcon(QIcon(AppStyles.get_icon('more', btn_color)))  # type: ignore[arg-type]
        self.more_button.setIconSize(btn_icon_size)
        self.more_button.setFixedSize(self.CTRL_BUTTON_WIDTH, self.CTRL_BUTTON_HEIGHT)
        self.more_button.setStyleSheet(AppStyles.player_button_style())
        self.more_button.clicked.connect(self._show_more_menu)
        self.more_button.setToolTip(tr("panel_more", "更多"))
        self.control_row.addWidget(self.more_button)

        self.fullscreen_button = QToolButton()
        self.fullscreen_button.setIcon(QIcon(AppStyles.get_icon('fullscreen', btn_color)))  # type: ignore[arg-type]
        self.fullscreen_button.setIconSize(btn_icon_size)
        self.fullscreen_button.setFixedSize(self.CTRL_BUTTON_WIDTH, self.CTRL_BUTTON_HEIGHT)
        self.fullscreen_button.setStyleSheet(AppStyles.player_button_style())
        self.fullscreen_button.clicked.connect(self.toggle_fullscreen)
        self.fullscreen_button.setToolTip(tr("panel_fullscreen", "全屏"))
        self.control_row.addWidget(self.fullscreen_button)

        self.floating_layout.addLayout(self.control_row)

        logger.debug("_create_control_row: 完成")

    def _create_more_menu(self):
        """创建“更多”菜单：收纳次级控制按钮（倍速/比例/音轨/字幕/画中画/退出回看）"""
        from PySide6.QtWidgets import QMenu

        self._more_menu = QMenu(self)
        self._more_menu.setStyleSheet(AppStyles.player_menu_bar_style())
        mc = self.media_ctrl
        self._more_menu.addAction(self.language_manager.tr("panel_speed", "播放速度"), mc.show_speed_menu)
        self._more_menu.addAction(self.language_manager.tr("panel_aspect", "画面比例"), mc.show_aspect_menu)
        self._more_menu.addAction(self.language_manager.tr("panel_audio_track", "音轨"), mc.show_audio_track_menu)
        self._more_menu.addAction(self.language_manager.tr("panel_subtitle", "字幕"), mc.show_sub_track_menu)
        self._more_menu.addAction(self.language_manager.tr("panel_pip", "画中画"), self.pip_ctrl.toggle)
        self._more_menu.addSeparator()
        self._more_catchup_action = self._more_menu.addAction(
            self.language_manager.tr("panel_exit_catchup", "退出回看"), self.exit_catchup
        )
        self._more_catchup_action.setVisible(False)

    def _show_more_menu(self):
        """弹出“更多”菜单（向上弹出，避免被屏幕底部裁剪）"""
        from PySide6.QtCore import QPoint

        menu = self._more_menu
        btn = self.more_button
        menu.adjustSize()
        top_left = btn.mapToGlobal(btn.rect().topLeft())
        y = top_left.y() - menu.height() - 4
        if y < 0:
            y = btn.mapToGlobal(btn.rect().bottomLeft()).y()
        menu.exec(QPoint(top_left.x(), y))

    def _set_exit_catchup_visible(self, visible: bool, text: str = None):
        """回看/时移模式切换时同步“更多”菜单中的退出项。

        exit_catchup_button 保留为成员仅作状态/文案载体（旧引用兼容），
        不再单独上屏；菜单项的可见性与文案以此为准。
        """
        if text is not None and getattr(self, 'exit_catchup_button', None) is not None:
            self.exit_catchup_button.setText(text)
        action = getattr(self, '_more_catchup_action', None)
        if action is not None:
            action.setVisible(visible)
            if text is not None:
                action.setText(text)

    def _is_program_desc_cta(self) -> bool:
        """节目描述当前是否为空态引导文案（与语言切换无关，直接比较 tr 结果）"""
        if not hasattr(self, 'program_desc'):
            return False
        cta_text = self.language_manager.tr(
            "open_playlist_or_import", "Open a playlist file or import channels to start watching"
        )
        return self.program_desc.text() == cta_text

    def _on_program_desc_clicked(self, event):
        """空态引导文案可点击：打开订阅选择；业务描述文本走 QLabel 默认行为"""
        if event.button() == Qt.MouseButton.LeftButton and self._is_program_desc_cta():
            event.accept()
            self.open_playlist()
            return
        QLabel.mousePressEvent(self.program_desc, event)

    def _on_program_desc_enter(self, event):
        """悬停时按文案判断手型光标与提示，避免业务描述残留 CTA 交互暗示"""
        if self._is_program_desc_cta():
            self.program_desc.setCursor(Qt.CursorShape.PointingHandCursor)
            self.program_desc.setToolTip(self.language_manager.tr("tooltip_open_playlist_cta", "点击打开订阅文件"))
        else:
            self.program_desc.setCursor(Qt.CursorShape.ArrowCursor)
            self.program_desc.setToolTip("")
        QLabel.enterEvent(self.program_desc, event)