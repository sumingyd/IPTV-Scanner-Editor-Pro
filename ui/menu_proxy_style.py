from PySide6.QtWidgets import QProxyStyle, QStyle
from PySide6.QtGui import QPainter, QRegion, QBitmap
from PySide6.QtCore import Qt, QRect


class MenuRoundedProxyStyle(QProxyStyle):
    def drawPrimitive(self, element, option, painter, widget):
        if element == QStyle.PrimitiveElement.PE_PanelMenu:
            radius = self._parse_menu_radius(widget)
            if radius > 0:
                painter.save()
                painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                rect = widget.rect() if widget else option.rect
                clip_region = self._create_rounded_clip_region(rect, radius)
                painter.setClipRegion(clip_region)
                super().drawPrimitive(element, option, painter, widget)
                painter.restore()
                return
        if element == QStyle.PrimitiveElement.PE_IndicatorItemViewItemCheck:
            if widget and self._is_menu_widget(widget):
                radius = self._parse_menu_radius(widget)
                if radius > 0:
                    painter.save()
                    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                    parent_rect = widget.rect()
                    clip_region = self._create_rounded_clip_region(parent_rect, radius)
                    painter.setClipRegion(clip_region)
                    super().drawPrimitive(element, option, painter, widget)
                    painter.restore()
                    return
        super().drawPrimitive(element, option, painter, widget)

    def drawControl(self, element, option, painter, widget):
        if element == QStyle.ControlElement.CE_MenuItem:
            if widget:
                radius = self._parse_menu_radius(widget)
                if radius > 0:
                    painter.save()
                    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                    parent_rect = widget.rect()
                    clip_region = self._create_rounded_clip_region(parent_rect, radius)
                    painter.setClipRegion(clip_region)
                    super().drawControl(element, option, painter, widget)
                    painter.restore()
                    return
        super().drawControl(element, option, painter, widget)

    @staticmethod
    def _is_menu_widget(widget):
        from PySide6.QtWidgets import QMenu
        while widget:
            if isinstance(widget, QMenu):
                return True
            widget = widget.parent()
        return False

    @staticmethod
    def _parse_menu_radius(widget):
        try:
            from ui.styles import AppStyles
            r = AppStyles._get_style_border_radius()
            return max(r - 2, 4)
        except Exception:
            pass
        radius = 0
        if widget:
            ss = widget.styleSheet()
            if 'border-radius' in ss:
                try:
                    for part in ss.split(';'):
                        part = part.strip()
                        if part.startswith('border-radius') and 'px' in part:
                            val = part.split(':')[1].strip().replace('px', '').strip()
                            radius = int(val)
                            break
                except Exception:
                    pass
        return radius

    @staticmethod
    def _create_rounded_clip_region(rect, radius):
        bitmap = QBitmap(rect.width(), rect.height())
        bitmap.clear()
        bmp_painter = QPainter(bitmap)
        bmp_painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        bmp_painter.setBrush(Qt.GlobalColor.black)
        bmp_painter.setPen(Qt.PenStyle.NoPen)
        bmp_painter.drawRoundedRect(QRect(0, 0, rect.width(), rect.height()), radius, radius)
        bmp_painter.end()
        clip_region = QRegion(bitmap)
        clip_region.translate(rect.topLeft())
        return clip_region
