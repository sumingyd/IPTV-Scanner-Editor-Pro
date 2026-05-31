from PyQt6.QtWidgets import QProxyStyle, QStyle
from PyQt6.QtGui import QPainter, QRegion, QBitmap
from PyQt6.QtCore import Qt, QRect


class MenuRoundedProxyStyle(QProxyStyle):
    def drawControl(self, element, option, painter, widget):
        if element == QStyle.ControlElement.CE_PopupMenu:
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
            if radius > 0:
                painter.save()
                painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                rect = widget.rect() if widget else option.rect
                region = QRegion(rect)
                bitmap = QBitmap(rect.width(), rect.height())
                bitmap.clear()
                bmp_painter = QPainter(bitmap)
                bmp_painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                bmp_painter.setBrush(Qt.GlobalColor.black)
                bmp_painter.setPen(Qt.PenStyle.NoPen)
                bmp_painter.drawRoundedRect(QRect(0, 0, rect.width(), rect.height()), radius, radius)
                bmp_painter.end()
                region = QRegion(bitmap)
                region.translate(rect.topLeft())
                painter.setClipRegion(region)
                super().drawControl(element, option, painter, widget)
                painter.restore()
                return
        super().drawControl(element, option, painter, widget)