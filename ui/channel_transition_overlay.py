from typing import Optional
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QTimer, Property
from PySide6.QtGui import QPainter, QColor, QPixmap, QFont
from ui.styles import AppStyles


class ChannelTransitionOverlay(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self._opacity = 0.0
        self._fade_animation = None
        self._auto_hide_timer = QTimer(self)
        self._auto_hide_timer.setSingleShot(True)
        self._auto_hide_timer.timeout.connect(self._start_fade_out)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._card = QWidget()
        card_layout = QVBoxLayout(self._card)
        card_layout.setContentsMargins(24, 16, 24, 16)
        card_layout.setSpacing(8)

        top_row = QHBoxLayout()
        top_row.setSpacing(12)

        self._logo_label = QLabel()
        self._logo_label.setFixedSize(48, 48)
        self._logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top_row.addWidget(self._logo_label)

        self._name_label = QLabel()
        self._name_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        name_font = QFont(self._resolve_font_family(), 18)
        name_font.setBold(True)
        self._name_label.setFont(name_font)
        top_row.addWidget(self._name_label, 1)

        card_layout.addLayout(top_row)

        self._info_label = QLabel()
        self._info_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._info_label.setFont(QFont(self._resolve_font_family(), 10))
        card_layout.addWidget(self._info_label)

        layout.addWidget(self._card)
        self.hide()

        from ui.theme_manager import get_theme_manager
        get_theme_manager().theme_changed.connect(self._on_theme_changed)

    @staticmethod
    def _resolve_font_family() -> str:
        family = AppStyles._get_style_font_family().split(",")[0].strip("' ")
        return family if family else "sans-serif"

    def _on_theme_changed(self, _theme_name):
        if self._opacity > 0 and self._name_label.text():
            self._reapply_overlay_styles()

    def _reapply_overlay_styles(self):
        colors = AppStyles._get_colors()
        text_color = colors.get('player_panel_text', AppStyles._safe_fallback('player_panel_text'))
        self._name_label.setStyleSheet(f"color: {text_color}; background: transparent;")
        self._info_label.setStyleSheet(f"color: {colors.get('player_panel_secondary', '#aaaaaa')}; background: transparent;")
        bg_color = colors.get('player_panel', 'rgba(20,20,20,220)')
        r = AppStyles._get_style_border_radius()
        self._card.setStyleSheet(f"background: {bg_color}; border-radius: {r}px;")
        family = self._resolve_font_family()
        name_font = QFont(family, 18)
        name_font.setBold(True)
        self._name_label.setFont(name_font)
        self._info_label.setFont(QFont(family, 10))

    def show_transition(self, channel_name: str, logo_pixmap: Optional[QPixmap] = None, info_text: str = ""):
        self._name_label.setText(channel_name)
        colors = AppStyles._get_colors()
        text_color = colors.get('player_panel_text', AppStyles._safe_fallback('player_panel_text'))
        self._name_label.setStyleSheet(f"color: {text_color}; background: transparent;")
        self._info_label.setStyleSheet(f"color: {colors.get('player_panel_secondary', '#aaaaaa')}; background: transparent;")

        if info_text:
            self._info_label.setText(info_text)
            self._info_label.show()
        else:
            self._info_label.hide()

        if logo_pixmap and not logo_pixmap.isNull():
            scaled = logo_pixmap.scaled(48, 48, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self._logo_label.setPixmap(scaled)
            self._logo_label.show()
        else:
            self._logo_label.clear()
            self._logo_label.hide()

        bg_color = colors.get('player_panel', 'rgba(20,20,20,220)')
        r = AppStyles._get_style_border_radius()
        if bg_color.startswith('rgba('):
            self._card.setStyleSheet(f"background: {bg_color}; border-radius: {r}px;")
        else:
            self._card.setStyleSheet(f"background: {bg_color}; border-radius: {r}px;")

        self._opacity = 1.0
        self.update()
        self.show()
        self.raise_()

        self._auto_hide_timer.start(1500)

    def _start_fade_out(self):
        self._fade_animation = QPropertyAnimation(self, b"opacity")
        self._fade_animation.setDuration(300)
        self._fade_animation.setStartValue(1.0)
        self._fade_animation.setEndValue(0.0)
        self._fade_animation.setEasingCurve(QEasingCurve.Type.OutQuad)
        self._fade_animation.finished.connect(self._on_fade_finished)
        self._fade_animation.start()

    def _on_fade_finished(self):
        self.hide()
        self._opacity = 0.0
        self._fade_animation = None

    def get_opacity(self):
        return self._opacity

    def set_opacity(self, val):
        self._opacity = val
        self.update()

    opacity = Property(float, get_opacity, set_opacity)

    def paintEvent(self, event):
        if self._opacity <= 0:
            return
        painter = QPainter(self)
        painter.setOpacity(self._opacity)
        painter.end()
        super().paintEvent(event)
