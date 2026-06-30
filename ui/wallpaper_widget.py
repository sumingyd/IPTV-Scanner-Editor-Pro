"""空闲态银河壁纸组件。

播放器未播放时显示的动态银河背景，移植自 Mineradio wallpaper.html 的椭圆轨道粒子系统。
作为 QLabel 的 drop-in 替换挂到 video_frame 上，复用现有的 show/hide/setPixmap 生命周期。
"""
import math

from PySide6.QtCore import QTimer, Qt, QRectF
from PySide6.QtGui import QPainter, QColor, QBrush, QRadialGradient, QPixmap
from PySide6.QtWidgets import QWidget

from services.audio_visual_service import _galaxy_rand


class WallpaperWidget(QWidget):
    """空闲态银河壁纸：椭圆轨道粒子 + 闪烁色循环 + 中心光晕 + App 图标。

    粒子分布在多层椭圆环上，按各自速度沿轨道运行；闪烁强度决定亮度与颜色
    （暖黄高亮 / 翠绿次级 / 冷青光晕）。无音频输入，粒子以默认速度运行。
    仅在可见时驱动动画（showEvent/hideEvent 控制定时器），不可见时零开销。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._particles = []
        self._time = 0.0
        self._icon_pixmap = None
        self._timer = QTimer(self)
        self._timer.setInterval(16)  # ~60fps
        self._timer.timeout.connect(self._on_tick)

    # ---- QLabel 兼容 API ----
    def setPixmap(self, pixmap: QPixmap):
        """存储图标 pixmap，居中绘制在银河壁纸上方（带柔和光晕）。"""
        self._icon_pixmap = pixmap
        self.update()

    def setText(self, _text: str):
        """兼容 QLabel API：空操作（壁纸不需要文字）。"""
        pass

    def setAlignment(self, _alignment):
        """兼容 QLabel API：空操作（壁纸始终居中渲染）。"""
        pass

    def setStyleSheet(self, _style: str):
        """兼容 QLabel API：空操作（壁纸自行绘制背景，不使用 QSS）。"""
        pass

    # ---- 动画驱动 ----
    def _on_tick(self):
        self._time += 1 / 60.0
        # 更新粒子轨道相位（无音频，使用默认速度）
        for p in self._particles:
            p['phase'] = (p['phase'] + p['speed_base']) % math.tau
        self.update()

    def showEvent(self, event):
        super().showEvent(event)
        self._timer.start()

    def hideEvent(self, event):
        super().hideEvent(event)
        self._timer.stop()

    # ---- 粒子池管理 ----
    def _ensure_particles(self, w: int, h: int):
        """根据屏幕面积自适应粒子数量（与 audio_visual_service galaxy 同算法）。"""
        target = min(760, max(420, int((w * h) / 4200)))
        while len(self._particles) < target:
            i = len(self._particles) + 1
            self._particles.append({
                'seed': i * 11.37,
                'phase': _galaxy_rand(i) * math.tau,
                'lane': _galaxy_rand(i * 2.7),
                'z': _galaxy_rand(i * 5.9),
                'size': 0.6 + _galaxy_rand(i * 4.2) * 2.4,
                'twinkle_freq': 0.50 + _galaxy_rand(i * 9.1) * 0.42,
                'wobble_freq': 0.22 + _galaxy_rand(i * 8.5) * 0.18,
                'speed_base': 0.009 + _galaxy_rand(i * 3.1) * 0.021,
                'y_skew': 1.0 + _galaxy_rand(i * 6.4) * 0.16,
            })
        if len(self._particles) > target + 80:
            self._particles = self._particles[:target + 80]

    # ---- 绘制 ----
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        h = self.height()
        if w <= 0 or h <= 0:
            painter.end()
            return

        # 深色径向渐变背景
        bg = QRadialGradient(w / 2, h / 2, max(w, h) * 0.7)
        bg.setColorAt(0, QColor(10, 12, 20))
        bg.setColorAt(1, QColor(5, 6, 8))
        painter.fillRect(0, 0, w, h, QBrush(bg))

        self._ensure_particles(w, h)

        cx = w / 2
        # 中心点带轻微上下浮动（呼吸感）
        cy = h / 2 + math.sin(self._time * 0.28) * h * 0.018
        rx = w * 0.40
        ry = h * 0.30
        now = self._time

        # 颜色调色板（与 Mineradio wallpaper / audio_visual galaxy 一致）
        highlight = QColor(255, 240, 184)   # #fff0b8 暖黄
        secondary = QColor(156, 255, 223)   # #9cffdf 翠绿
        glow = QColor(156, 255, 223)        # 同 secondary

        painter.setPen(Qt.PenStyle.NoPen)

        # 1. 中心径向光晕
        aura_radius = max(w, h) * 0.54
        aura = QRadialGradient(cx, cy, aura_radius)
        aura.setColorAt(0, QColor(highlight.red(), highlight.green(), highlight.blue(), 30))
        aura.setColorAt(0.34, QColor(secondary.red(), secondary.green(), secondary.blue(), 20))
        aura.setColorAt(1, QColor(0, 0, 0, 0))
        painter.setBrush(QBrush(aura))
        painter.drawRect(QRectF(0, 0, w, h))

        # 2. 椭圆轨道粒子（Plus 复合模式叠加发光）
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
        for p in self._particles:
            seed = p['seed']
            angle = (p['phase'] + math.sin(now * 0.07 + seed) * 0.14) % math.tau
            ring = 0.18 + p['z'] * 0.82
            wobble = math.sin(now * p['wobble_freq'] + seed) * 12
            x = cx + math.cos(angle) * rx * ring + math.sin(now * 0.11 + seed) * 24
            y = cy + math.sin(angle * p['y_skew']) * ry * ring + wobble
            tw = (0.5 + 0.5 * math.sin(now * p['twinkle_freq'] + seed)) ** 4
            r = max(0.7, p['size'] * (0.8 + tw * 1.2))
            if tw > 0.74:
                col = highlight
            elif p['lane'] > 0.55:
                col = secondary
            else:
                col = glow
            alpha = int((0.045 + tw * 0.18) * 255)
            alpha = max(0, min(255, alpha))
            if alpha < 4:
                continue
            grad = QRadialGradient(x, y, r * 2.2)
            grad.setColorAt(0, QColor(255, 255, 255, min(255, int(alpha * 0.9))))
            grad.setColorAt(0.3, QColor(col.red(), col.green(), col.blue(), alpha))
            grad.setColorAt(1, QColor(col.red(), col.green(), col.blue(), 0))
            painter.setBrush(QBrush(grad))
            painter.drawEllipse(QRectF(x - r * 2.2, y - r * 2.2, r * 4.4, r * 4.4))
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

        # 3. 居中绘制 App 图标（带柔和光晕）
        if self._icon_pixmap and not self._icon_pixmap.isNull():
            icon_size = min(w, h) * 0.16
            # 图标光晕
            halo = QRadialGradient(cx, cy, icon_size * 1.5)
            halo.setColorAt(0, QColor(255, 240, 184, 45))
            halo.setColorAt(0.5, QColor(156, 255, 223, 22))
            halo.setColorAt(1, QColor(0, 0, 0, 0))
            painter.setBrush(QBrush(halo))
            painter.drawEllipse(QRectF(cx - icon_size * 1.5, cy - icon_size * 1.5,
                                       icon_size * 3, icon_size * 3))
            # 图标本体
            ix = cx - icon_size / 2
            iy = cy - icon_size / 2
            painter.setOpacity(0.85)
            painter.drawPixmap(QRectF(ix, iy, icon_size, icon_size),
                               self._icon_pixmap,
                               QRectF(0, 0, self._icon_pixmap.width(), self._icon_pixmap.height()))
            painter.setOpacity(1.0)

        painter.end()
