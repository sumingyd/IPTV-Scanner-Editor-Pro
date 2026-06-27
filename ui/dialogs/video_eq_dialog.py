"""视频图像调整对话框 - 亮度/对比度/饱和度/色调/Gamma/锐度 + 旋转/镜像"""
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QPushButton,
    QSlider, QCheckBox, QComboBox, QGroupBox, QWidget,
)
from PySide6.QtCore import Qt, Signal

from ui.floating_dialog import FloatingDialog
from ui.styles import AppStyles
from core.log_manager import global_logger as logger


class VideoEqualizerDialog(FloatingDialog):
    """视频图像调整对话框
    滑块拖动时实时应用到 mpv；保存按钮持久化到 config
    """

    style_saved = Signal(dict)

    # 整数参数列表（mpv 取值 -100~100）
    _INT_KEYS = ('brightness', 'contrast', 'saturation', 'hue', 'gamma')
    # 锐度使用 -100~100 的整数滑块映射到 mpv 的 -1.0~1.0
    _SHARP_KEY = 'sharpness'

    def __init__(self, main_window, parent=None):
        super().__init__(parent, frameless=False, stay_on_top=False)
        self.window = main_window
        tr = main_window.language_manager.tr
        self.setWindowTitle(tr('video_eq_title', '视频图像调整'))
        self.setMinimumSize(520, 560)
        self._loading = False
        self._setup_ui()
        self._apply_theme()
        try:
            from ui.theme_manager import get_theme_manager
            get_theme_manager().register_window(self)
        except Exception:
            pass
        # 初始回填
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

        # ===== 图像参数组 =====
        image_group = QGroupBox(tr('video_eq_group_image', '图像参数'))
        form = QFormLayout(image_group)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # 亮度/对比度/饱和度/色调/Gamma：-100 ~ 100
        self._int_sliders = {}
        self._int_labels = {}
        for key in self._INT_KEYS:
            label_key = f'video_eq_{key}'
            container, slider, value_label = self._make_int_slider(key, tr(label_key, key.capitalize()))
            form.addRow(tr(label_key, key.capitalize()), container)
            self._int_sliders[key] = slider
            self._int_labels[key] = value_label

        # 锐度：-100~100 整数滑块（映射到 -1.0~1.0）
        sharp_slider = QSlider(Qt.Orientation.Horizontal)
        sharp_slider.setRange(-100, 100)
        sharp_slider.setSingleStep(5)
        sharp_slider.setPageStep(20)
        sharp_slider.setValue(0)
        sharp_label = QLabel('0.00')
        sharp_label.setMinimumWidth(48)
        sharp_row = QHBoxLayout()
        sharp_row.addWidget(sharp_slider, 1)
        sharp_row.addWidget(sharp_label)
        sharp_container = QWidget()
        sharp_container.setLayout(sharp_row)
        sharp_slider.valueChanged.connect(lambda v: self._on_sharpness_changed(v, sharp_label))
        form.addRow(tr('video_eq_sharpness', '锐度'), sharp_container)
        self._sharpness_slider = sharp_slider
        self._sharpness_label = sharp_label

        layout.addWidget(image_group)

        # ===== 画面变换组 =====
        transform_group = QGroupBox(tr('video_eq_group_transform', '画面变换'))
        tform = QFormLayout(transform_group)
        tform.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # 旋转
        self.rotate_combo = QComboBox()
        self.rotate_combo.addItem('0°', 0)
        self.rotate_combo.addItem('90°', 90)
        self.rotate_combo.addItem('180°', 180)
        self.rotate_combo.addItem('270°', 270)
        self.rotate_combo.currentIndexChanged.connect(self._on_rotate_changed)
        tform.addRow(tr('video_eq_rotate', '旋转'), self.rotate_combo)

        # 翻转
        self.flip_combo = QComboBox()
        self.flip_combo.addItem(tr('video_eq_flip_none', '无'), '')
        self.flip_combo.addItem(tr('video_eq_flip_horizontal', '水平翻转'), 'horizontal')
        self.flip_combo.addItem(tr('video_eq_flip_vertical', '垂直翻转'), 'vertical')
        self.flip_combo.addItem(tr('video_eq_flip_both', '双向翻转'), 'both')
        self.flip_combo.currentIndexChanged.connect(self._on_flip_changed)
        tform.addRow(tr('video_eq_flip', '镜像翻转'), self.flip_combo)

        # 切换文件时自动重置
        self.reset_on_new_check = QCheckBox(tr('video_eq_reset_on_new_file', '切换文件时自动重置'))
        self.reset_on_new_check.toggled.connect(self._on_reset_on_new_toggled)
        tform.addRow('', self.reset_on_new_check)

        layout.addWidget(transform_group)

        # ===== 操作按钮 =====
        btn_row = QHBoxLayout()
        self.reset_btn = QPushButton(tr('video_eq_reset', '重置全部'))
        self.reset_btn.clicked.connect(self._reset_all)
        self.apply_btn = QPushButton(tr('video_eq_apply', '应用'))
        self.apply_btn.clicked.connect(self._apply_now)
        self.save_btn = QPushButton(tr('video_eq_save', '保存'))
        self.save_btn.clicked.connect(self._save)
        self.close_btn = QPushButton(tr('video_eq_close', '关闭'))
        self.close_btn.clicked.connect(self.close)
        btn_row.addWidget(self.reset_btn)
        btn_row.addStretch()
        btn_row.addWidget(self.apply_btn)
        btn_row.addWidget(self.save_btn)
        btn_row.addWidget(self.close_btn)
        layout.addLayout(btn_row)

    def _make_int_slider(self, key: str, label_text: str):
        """构造 -100~100 整数滑块 + 数值标签，返回 (container, slider, value_label)"""
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(-100, 100)
        slider.setSingleStep(1)
        slider.setPageStep(10)
        slider.setValue(0)
        value_label = QLabel('0')
        value_label.setMinimumWidth(36)
        slider.valueChanged.connect(lambda v, lbl=value_label, k=key: self._on_int_changed(k, v, lbl))
        row = QHBoxLayout()
        row.addWidget(slider, 1)
        row.addWidget(value_label)
        container = QWidget()
        container.setLayout(row)
        return container, slider, value_label

    # ---------- 数据加载/收集 ----------
    def _reload_from_config(self):
        """从配置加载并回填 UI"""
        try:
            cfg = self.window.config.load_video_eq()
        except Exception as e:
            logger.warning(f"加载视频 EQ 配置失败: {e}")
            cfg = {}
        self._loading = True
        try:
            self._set_ui_from_dict(cfg)
        finally:
            self._loading = False
        # 启动时同步应用到当前播放
        self._apply_now(silent=True)

    def _set_ui_from_dict(self, cfg: dict):
        """用字典回填所有 UI 控件"""
        for key in self._INT_KEYS:
            v = int(cfg.get(key, 0) or 0)
            v = max(-100, min(100, v))
            self._int_sliders[key].setValue(v)
            self._int_labels[key].setText(str(v))
        sharp = float(cfg.get('sharpness', 0.0) or 0.0)
        sharp = max(-1.0, min(1.0, sharp))
        self._sharpness_slider.setValue(int(round(sharp * 100)))
        self._sharpness_label.setText(f"{sharp:.2f}")
        rotate = int(cfg.get('video_rotate', 0) or 0)
        idx = self.rotate_combo.findData(rotate)
        if idx >= 0:
            self.rotate_combo.setCurrentIndex(idx)
        flip_mode = cfg.get('video_flip', '') or ''
        idx = self.flip_combo.findData(flip_mode)
        if idx >= 0:
            self.flip_combo.setCurrentIndex(idx)
        self.reset_on_new_check.setChecked(bool(cfg.get('reset_on_new_file', False)))

    def _collect_eq(self) -> dict:
        """从 UI 控件收集所有参数"""
        result = {}
        for key in self._INT_KEYS:
            result[key] = int(self._int_sliders[key].value())
        result['sharpness'] = round(self._sharpness_slider.value() / 100.0, 3)
        result['video_rotate'] = int(self.rotate_combo.currentData() or 0)
        result['video_flip'] = self.flip_combo.currentData() or ''
        result['reset_on_new_file'] = bool(self.reset_on_new_check.isChecked())
        return result

    # ---------- 事件处理 ----------
    def _on_int_changed(self, key: str, value: int, label: QLabel):
        label.setText(str(value))
        if self._loading:
            return
        pc = self.window.player_controller
        if pc and pc.is_playing:
            getattr(pc, f'set_{key}')(value)
            self._show_osd(f"{self.window.language_manager.tr(f'osd_video_{key}', key.capitalize())}: {value:+d}")

    def _on_sharpness_changed(self, value: int, label: QLabel):
        v = round(value / 100.0, 3)
        label.setText(f"{v:.2f}")
        if self._loading:
            return
        pc = self.window.player_controller
        if pc and pc.is_playing:
            pc.set_sharpness(v)
            self._show_osd(f"{self.window.language_manager.tr('osd_video_sharpness', 'Sharpness')}: {v:+.2f}")

    def _on_rotate_changed(self, idx: int):
        if self._loading:
            return
        degree = int(self.rotate_combo.currentData() or 0)
        pc = self.window.player_controller
        if pc and pc.is_playing:
            pc.set_video_rotate(degree)
            self._show_osd(f"{self.window.language_manager.tr('osd_video_rotate', 'Rotate')}: {degree}°")

    def _on_flip_changed(self, idx: int):
        if self._loading:
            return
        mode = self.flip_combo.currentData() or ''
        pc = self.window.player_controller
        if pc and pc.is_playing:
            pc.set_video_flip(mode)
            label = self.flip_combo.currentText()
            self._show_osd(f"{self.window.language_manager.tr('osd_video_flip', 'Flip')}: {label}")

    def _on_reset_on_new_toggled(self, checked: bool):
        if self._loading:
            return
        # 即时保存该选项
        try:
            cfg = self.window.config.load_video_eq()
            cfg['reset_on_new_file'] = bool(checked)
            self.window.config.save_video_eq(cfg)
        except Exception as e:
            logger.warning(f"保存 reset_on_new_file 失败: {e}")

    def _apply_now(self, silent: bool = False):
        """应用所有参数到当前播放"""
        eq = self._collect_eq()
        pc = self.window.player_controller
        if pc and pc.is_playing:
            pc.apply_video_eq(eq)
            if not silent:
                tr = self.window.language_manager.tr
                if hasattr(self.window, '_show_osd_feedback'):
                    self.window._show_osd_feedback(tr('video_eq_applied', '图像参数已应用'))
        elif not silent:
            tr = self.window.language_manager.tr
            if hasattr(self.window, '_show_osd_feedback'):
                self.window._show_osd_feedback(tr('video_eq_applied', '图像参数已应用'))

    def _save(self):
        """保存到配置文件"""
        try:
            eq = self._collect_eq()
            self.window.config.save_video_eq(eq)
            self.style_saved.emit(eq)
            tr = self.window.language_manager.tr
            if hasattr(self.window, '_show_osd_feedback'):
                self.window._show_osd_feedback(tr('video_eq_saved', '图像参数已保存'))
        except Exception as e:
            logger.error(f"保存视频 EQ 失败: {e}")

    def _reset_all(self):
        """重置所有参数为默认"""
        defaults = self.window.config.VIDEO_EQ_DEFAULTS.copy()
        self._loading = True
        try:
            self._set_ui_from_dict(defaults)
        finally:
            self._loading = False
        pc = self.window.player_controller
        if pc and pc.is_playing:
            # 仅重置图像参数，旋转/翻转也清除
            pc.reset_video_eq()
            pc.set_video_rotate(0)
            pc.set_video_flip('')
            pc.clear_video_crop()
        tr = self.window.language_manager.tr
        if hasattr(self.window, '_show_osd_feedback'):
            self.window._show_osd_feedback(tr('video_eq_reset_done', '图像参数已重置'))

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
