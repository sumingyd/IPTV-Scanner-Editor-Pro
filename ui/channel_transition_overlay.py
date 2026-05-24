from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QTimer
from PyQt6.QtGui import QPainter, QColor, QPixmap, QFont
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
        self._name_label.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        top_row.addWidget(self._name_label, 1)

        card_layout.addLayout(top_row)

        self._info_label = QLabel()
        self._info_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._info_label.setFont(QFont("Segoe UI", 10))
        card_layout.addWidget(self._info_label)

        layout.addWidget(self._card)
        self.hide()

    def show_transition(self, channel_name: str, logo_pixmap: QPixmap = None, info_text: str = ""):
        self._name_label.setText(channel_name)
        colors = AppStyles._get_colors()
        text_color = colors.get('player_panel_text', '#ffffff')
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
        if bg_color.startswith('rgba('):
            self._card.setStyleSheet(f"background: {bg_color}; border-radius: 8px;")
        else:
            self._card.setStyleSheet(f"background: {bg_color}; border-radius: 8px;")

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

    opacity = property(get_opacity, set_opacity)

    def paintEvent(self, event):
        if self._opacity <= 0:
            return
        painter = QPainter(self)
        painter.setOpacity(self._opacity)
        painter.end()
        super().paintEvent(event)
