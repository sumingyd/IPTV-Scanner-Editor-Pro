"""音频调整对话框 - 延迟/声道/设备/音调补偿 + 10 段均衡器"""
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QPushButton,
    QSlider, QCheckBox, QComboBox, QGroupBox, QWidget,
    QGridLayout, QDoubleSpinBox,
)
from PySide6.QtCore import Qt, Signal

from ui.floating_dialog import FloatingDialog
from ui.styles import AppStyles
from core.log_manager import global_logger as logger


# EQ 预设
EQ_PRESETS = {
    'flat':       [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    'bass':       [8, 6, 4, 2, 0, 0, 0, 0, 0, 0],
    'treble':     [0, 0, 0, 0, 0, 2, 4, 6, 8, 8],
    'vocal':      [-2, -2, 0, 2, 4, 4, 3, 1, 0, -1],
    'classical':  [3, 2, 1, 0, -1, -1, 0, 2, 3, 3],
    'pop':        [-1, 1, 3, 4, 3, 0, -1, -1, 1, 2],
    'rock':       [5, 3, 1, 0, -1, -1, 1, 3, 4, 4],
    'electronic': [4, 3, 0, -2, -2, 1, 2, 3, 4, 5],
}

# 声道布局选项
CHANNEL_OPTIONS = [
    ('auto', 'Auto'),
    ('mono', 'Mono'),
    ('1.0', '1.0'),
    ('2.0', '2.0 (Stereo)'),
    ('2.1', '2.1'),
    ('3.0', '3.0'),
    ('4.0', '4.0'),
    ('5.0', '5.0'),
    ('5.1', '5.1'),
    ('6.0', '6.0'),
    ('6.1', '6.1'),
    ('7.0', '7.0'),
    ('7.1', '7.1'),
]


class AudioEqualizerDialog(FloatingDialog):
    """音频调整对话框
    调整时实时应用到 mpv；保存按钮持久化到 config
    """

    style_saved = Signal(dict)

    def __init__(self, main_window, parent=None):
        super().__init__(parent, frameless=False, stay_on_top=False)
        self.window = main_window
        tr = main_window.language_manager.tr
        self.setWindowTitle(tr('audio_eq_title', '音频调整'))
        self.setMinimumSize(640, 640)
        self._loading = False
        self._eq_sliders = []
        self._eq_labels = []
        self._setup_ui()
        self._apply_theme()
        try:
            from ui.theme_manager import get_theme_manager
            get_theme_manager().register_window(self)
        except Exception:
            pass
        self._reload_from_config()

    def _apply_theme(self):
        c = AppStyles._get_colors()
        r = AppStyles._get_style_border_radius()
        text_color = c.get('window_text', '#ffffff')
        self.setStyleSheet(AppStyles.popup_dialog_style() + f"""
            QLabel {{ color: {text_color}; }}
            QGroupBox {{
                color: {text_color};
                border: 1px solid {c.get('mid', '#555')};
                border-radius: {r}px;
                margin-top: 12px; padding: 8px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin; left: 10px; padding: 0 4px;
            }}
            QSlider::groove:horizontal {{
                height: 4px; background: {c.get('mid', '#555')}; border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                width: 14px; height: 14px; margin: -5px 0;
                background: {c.get('accent', '#3a9')} border-radius: 7px;
            }}
            QSlider::handle:horizontal:hover {{
                background: {c.get('accent', '#3a9')} border: 2px solid #fff;
            }}
        """)

    def _setup_ui(self):
        tr = self.window.language_manager.tr
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # ===== 音频同步组 =====
        delay_group = QGroupBox(tr('audio_eq_group_delay', '音频同步'))
        dform = QFormLayout(delay_group)
        dform.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # 音频延迟：-10.0~10.0 秒
        self.delay_slider = QSlider(Qt.Orientation.Horizontal)
        self.delay_slider.setRange(-1000, 1000)
        self.delay_slider.setSingleStep(10)
        self.delay_slider.setPageStep(100)
        self.delay_slider.setValue(0)
        self.delay_label = QLabel('0.000s')
        self.delay_label.setMinimumWidth(60)
        self.delay_slider.valueChanged.connect(self._on_delay_changed)
        drow = QHBoxLayout()
        drow.addWidget(self.delay_slider, 1)
        drow.addWidget(self.delay_label)
        dcontainer = QWidget()
        dcontainer.setLayout(drow)
        dform.addRow(tr('audio_eq_delay', '音频延迟'), dcontainer)
        layout.addWidget(delay_group)

        # ===== 音调 + 声道 + 设备组 =====
        opt_group = QGroupBox(tr('audio_eq_group_pitch', '音调补偿') + ' / ' +
                              tr('audio_eq_group_channels', '声道布局') + ' / ' +
                              tr('audio_eq_group_device', '输出设备'))
        oform = QFormLayout(opt_group)
        oform.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # 音调补偿：0.0~2.0
        self.pitch_slider = QSlider(Qt.Orientation.Horizontal)
        self.pitch_slider.setRange(0, 200)
        self.pitch_slider.setSingleStep(5)
        self.pitch_slider.setPageStep(20)
        self.pitch_slider.setValue(100)
        self.pitch_label = QLabel('1.00')
        self.pitch_label.setMinimumWidth(48)
        self.pitch_slider.valueChanged.connect(self._on_pitch_changed)
        prows = QHBoxLayout()
        prows.addWidget(self.pitch_slider, 1)
        prows.addWidget(self.pitch_label)
        pcontainer = QWidget()
        pcontainer.setLayout(prows)
        oform.addRow(tr('audio_eq_pitch', '音调'), pcontainer)

        # 声道布局
        self.channels_combo = QComboBox()
        for val, label in CHANNEL_OPTIONS:
            self.channels_combo.addItem(label, val)
        self.channels_combo.currentIndexChanged.connect(self._on_channels_changed)
        oform.addRow(tr('audio_eq_channels', '声道'), self.channels_combo)

        # 输出设备
        self.device_combo = QComboBox()
        self.device_combo.addItem(tr('audio_eq_preset_flat', '默认') + ' (auto)', '')
        self.device_combo.currentIndexChanged.connect(self._on_device_changed)
        oform.addRow(tr('audio_eq_device', '设备'), self.device_combo)
        # 延迟加载设备列表（首次显示时）
        self._devices_loaded = False

        layout.addWidget(opt_group)

        # ===== 均衡器组 =====
        eq_group = QGroupBox(tr('audio_eq_group_equalizer', '均衡器'))
        eq_layout = QVBoxLayout(eq_group)

        # 预设按钮行
        preset_row = QHBoxLayout()
        preset_label = QLabel(tr('audio_eq_preset', '快速预设') + ':')
        preset_row.addWidget(preset_label)
        preset_keys = [
            ('flat', tr('audio_eq_preset_flat', '平直')),
            ('bass', tr('audio_eq_preset_bass', '重低音')),
            ('treble', tr('audio_eq_preset_treble', '高音')),
            ('vocal', tr('audio_eq_preset_vocal', '人声')),
            ('classical', tr('audio_eq_preset_classical', '古典')),
            ('pop', tr('audio_eq_preset_pop', '流行')),
            ('rock', tr('audio_eq_preset_rock', '摇滚')),
            ('electronic', tr('audio_eq_preset_electronic', '电子')),
        ]
        for key, label in preset_keys:
            btn = QPushButton(label)
            btn.clicked.connect(lambda checked, k=key: self._apply_preset(k))
            preset_row.addWidget(btn)
        preset_row.addStretch()
        eq_layout.addLayout(preset_row)

        # 10 段均衡器滑块网格
        from services.mpv_player_service import MpvPlayerController
        band_labels = MpvPlayerController.EQ_LABELS
        grid = QGridLayout()
        grid.setSpacing(6)
        for i, bl in enumerate(band_labels):
            # 频段标签
            lbl = QLabel(bl)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(lbl, 0, i)

            # 滑块（垂直）
            slider = QSlider(Qt.Orientation.Vertical)
            slider.setRange(-12, 12)
            slider.setSingleStep(1)
            slider.setPageStep(3)
            slider.setValue(0)
            slider.setFixedHeight(120)
            slider.valueChanged.connect(lambda v, idx=i: self._on_eq_band_changed(idx, v))
            grid.addWidget(slider, 1, i)

            # 数值标签
            val_lbl = QLabel('0')
            val_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            val_lbl.setMinimumWidth(36)
            grid.addWidget(val_lbl, 2, i)

            self._eq_sliders.append(slider)
            self._eq_labels.append(val_lbl)

        eq_layout.addLayout(grid)
        layout.addWidget(eq_group)

        # 切换文件时自动重置
        self.reset_on_new_check = QCheckBox(tr('audio_eq_reset_on_new_file', '切换文件时自动重置'))
        self.reset_on_new_check.toggled.connect(self._on_reset_on_new_toggled)
        layout.addWidget(self.reset_on_new_check)

        # ===== 操作按钮 =====
        btn_row = QHBoxLayout()
        self.reset_btn = QPushButton(tr('audio_eq_reset', '重置全部'))
        self.reset_btn.clicked.connect(self._reset_all)
        self.apply_btn = QPushButton(tr('audio_eq_apply', '应用'))
        self.apply_btn.clicked.connect(self._apply_now)
        self.save_btn = QPushButton(tr('audio_eq_save', '保存'))
        self.save_btn.clicked.connect(self._save)
        self.close_btn = QPushButton(tr('audio_eq_close', '关闭'))
        self.close_btn.clicked.connect(self.close)
        btn_row.addWidget(self.reset_btn)
        btn_row.addStretch()
        btn_row.addWidget(self.apply_btn)
        btn_row.addWidget(self.save_btn)
        btn_row.addWidget(self.close_btn)
        layout.addLayout(btn_row)

    def showEvent(self, event):
        super().showEvent(event)
        # 首次显示时加载音频设备列表
        if not self._devices_loaded:
            QTimer_singleShot = None
            try:
                from PySide6.QtCore import QTimer as _QTimer
                QTimer_singleShot = _QTimer.singleShot
            except Exception:
                pass
            if QTimer_singleShot:
                QTimer_singleShot(100, self._load_audio_devices)
            else:
                self._load_audio_devices()

    def _load_audio_devices(self):
        """从 mpv 加载音频设备列表"""
        if self._devices_loaded:
            return
        self._devices_loaded = True
        pc = self.window.player_controller
        if not pc or not hasattr(pc, 'get_audio_device_list'):
            return
        try:
            devices = pc.get_audio_device_list()
        except Exception as e:
            logger.debug(f"加载音频设备列表失败: {e}")
            return
        if not devices:
            return
        # 保留当前选择
        current = self.device_combo.currentData() or ''
        self._loading = True
        try:
            # 保留第一项（auto），追加新设备
            while self.device_combo.count() > 1:
                self.device_combo.removeItem(self.device_combo.count() - 1)
            for dev in devices:
                name = dev.get('name', '')
                desc = dev.get('description', name)
                if name:
                    self.device_combo.addItem(desc, name)
            idx = self.device_combo.findData(current)
            if idx >= 0:
                self.device_combo.setCurrentIndex(idx)
        finally:
            self._loading = False

    # ---------- 数据加载/收集 ----------
    def _reload_from_config(self):
        try:
            cfg = self.window.config.load_audio_eq()
        except Exception as e:
            logger.warning(f"加载音频 EQ 配置失败: {e}")
            cfg = {}
        self._loading = True
        try:
            self._set_ui_from_dict(cfg)
        finally:
            self._loading = False
        self._apply_now(silent=True)

    def _set_ui_from_dict(self, cfg: dict):
        # 音频延迟
        delay = float(cfg.get('audio_delay', 0.0) or 0.0)
        delay = max(-10.0, min(10.0, delay))
        self.delay_slider.setValue(int(round(delay * 100)))
        self.delay_label.setText(f"{delay:.3f}s")
        # 音调
        pitch = float(cfg.get('audio_pitch', 1.0) or 1.0)
        pitch = max(0.0, min(2.0, pitch))
        self.pitch_slider.setValue(int(round(pitch * 100)))
        self.pitch_label.setText(f"{pitch:.2f}")
        # 声道
        ch = cfg.get('audio_channels', 'auto') or 'auto'
        idx = self.channels_combo.findData(ch)
        if idx >= 0:
            self.channels_combo.setCurrentIndex(idx)
        # 设备
        dev = cfg.get('audio_device', '') or ''
        idx = self.device_combo.findData(dev)
        if idx >= 0:
            self.device_combo.setCurrentIndex(idx)
        # EQ
        eq = cfg.get('eq', [0.0] * 10) or [0.0] * 10
        if not isinstance(eq, list) or len(eq) != 10:
            eq = [0.0] * 10
        for i, g in enumerate(eq):
            v = int(round(max(-12.0, min(12.0, float(g)))))
            self._eq_sliders[i].setValue(v)
            self._eq_labels[i].setText(str(v))
        # 自动重置
        self.reset_on_new_check.setChecked(bool(cfg.get('reset_on_new_file', False)))

    def _collect_eq(self) -> dict:
        return {
            'audio_delay': round(self.delay_slider.value() / 100.0, 3),
            'audio_pitch': round(self.pitch_slider.value() / 100.0, 3),
            'audio_channels': self.channels_combo.currentData() or 'auto',
            'audio_device': self.device_combo.currentData() or '',
            'eq': [float(s.value()) for s in self._eq_sliders],
            'reset_on_new_file': bool(self.reset_on_new_check.isChecked()),
        }

    # ---------- 事件处理 ----------
    def _on_delay_changed(self, value: int):
        v = value / 100.0
        self.delay_label.setText(f"{v:+.3f}s")
        if self._loading:
            return
        pc = self.window.player_controller
        if pc and pc.is_playing and hasattr(pc, 'set_audio_delay'):
            pc.set_audio_delay(v)
            self._show_osd(f"{self.window.language_manager.tr('osd_audio_delay', 'Audio Delay')}: {v:+.3f}s")

    def _on_pitch_changed(self, value: int):
        v = value / 100.0
        self.pitch_label.setText(f"{v:.2f}")
        if self._loading:
            return
        pc = self.window.player_controller
        if pc and pc.is_playing and hasattr(pc, 'set_audio_pitch'):
            pc.set_audio_pitch(v)
            self._show_osd(f"{self.window.language_manager.tr('osd_audio_pitch', 'Pitch')}: {v:.2f}")

    def _on_channels_changed(self, idx: int):
        if self._loading:
            return
        ch = self.channels_combo.currentData() or 'auto'
        pc = self.window.player_controller
        if pc and pc.is_playing and hasattr(pc, 'set_audio_channels'):
            pc.set_audio_channels(ch)
            self._show_osd(f"{self.window.language_manager.tr('osd_audio_channels', 'Channels')}: {ch}")

    def _on_device_changed(self, idx: int):
        if self._loading:
            return
        dev = self.device_combo.currentData() or ''
        pc = self.window.player_controller
        if pc and pc.is_playing and hasattr(pc, 'set_audio_device'):
            if dev:
                pc.set_audio_device(dev)
            self._show_osd(f"{self.window.language_manager.tr('audio_eq_device', 'Device')}: {self.device_combo.currentText()}")

    def _on_eq_band_changed(self, idx: int, value: int):
        self._eq_labels[idx].setText(str(value))
        if self._loading:
            return
        pc = self.window.player_controller
        if pc and pc.is_playing and hasattr(pc, 'set_audio_eq_band'):
            pc.set_audio_eq_band(idx, float(value))
            self._show_osd(f"{self.window.language_manager.tr('osd_audio_eq_band', 'Band')} {idx+1}: {value:+d}dB")

    def _on_reset_on_new_toggled(self, checked: bool):
        if self._loading:
            return
        try:
            cfg = self.window.config.load_audio_eq()
            cfg['reset_on_new_file'] = bool(checked)
            self.window.config.save_audio_eq(cfg)
        except Exception as e:
            logger.warning(f"保存 reset_on_new_file 失败: {e}")

    def _apply_preset(self, key: str):
        gains = EQ_PRESETS.get(key)
        if not gains:
            return
        self._loading = True
        try:
            for i, g in enumerate(gains):
                self._eq_sliders[i].setValue(int(g))
                self._eq_labels[i].setText(str(int(g)))
        finally:
            self._loading = False
        pc = self.window.player_controller
        if pc and pc.is_playing and hasattr(pc, 'set_audio_eq'):
            pc.set_audio_eq([float(g) for g in gains])

    def _apply_now(self, silent: bool = False):
        eq = self._collect_eq()
        pc = self.window.player_controller
        if pc and pc.is_playing and hasattr(pc, 'apply_audio_eq'):
            pc.apply_audio_eq(eq)
            if not silent:
                tr = self.window.language_manager.tr
                if hasattr(self.window, '_show_osd_feedback'):
                    self.window._show_osd_feedback(tr('audio_eq_applied', '音频参数已应用'))
        elif not silent:
            tr = self.window.language_manager.tr
            if hasattr(self.window, '_show_osd_feedback'):
                self.window._show_osd_feedback(tr('audio_eq_applied', '音频参数已应用'))

    def _save(self):
        try:
            eq = self._collect_eq()
            self.window.config.save_audio_eq(eq)
            self.style_saved.emit(eq)
            tr = self.window.language_manager.tr
            if hasattr(self.window, '_show_osd_feedback'):
                self.window._show_osd_feedback(tr('audio_eq_saved', '音频参数已保存'))
        except Exception as e:
            logger.error(f"保存音频 EQ 失败: {e}")

    def _reset_all(self):
        defaults = self.window.config.AUDIO_EQ_DEFAULTS.copy()
        defaults['eq'] = [0.0] * 10
        self._loading = True
        try:
            self._set_ui_from_dict(defaults)
        finally:
            self._loading = False
        pc = self.window.player_controller
        if pc and pc.is_playing and hasattr(pc, 'reset_audio_eq'):
            pc.reset_audio_eq()
        tr = self.window.language_manager.tr
        if hasattr(self.window, '_show_osd_feedback'):
            self.window._show_osd_feedback(tr('audio_eq_reset_done', '音频参数已重置'))

    def _show_osd(self, text: str):
        if hasattr(self.window, '_show_osd_feedback'):
            self.window._show_osd_feedback(text)

    def closeEvent(self, event):
        try:
            from ui.theme_manager import get_theme_manager
            get_theme_manager().unregister_window(self)
        except Exception:
            pass
        super().closeEvent(event)
