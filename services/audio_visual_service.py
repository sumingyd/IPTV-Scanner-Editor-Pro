import math
import random
import subprocess
import threading
import time
import os

from collections import deque

import numpy as np
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import QTimer, Qt, QRectF, QPointF
from PySide6.QtGui import (QPainter, QColor, QLinearGradient, QRadialGradient,
                            QPen, QBrush, QFont, QPixmap, QImage, QPolygonF,
                            QConicalGradient)

AUDIO_EXTENSIONS = ('.mp3', '.flac', '.wav', '.aac', '.ogg', '.opus', '.wma', '.m4a',
                    '.ape', '.alac', '.wv', '.tta', '.dts', '.ac3', '.mid', '.midi')

AUDIO_VISUAL_STYLES = {
    'spectrum': {
        'name_key': 'audio_vis_spectrum',
        'name_default': '3D频谱',
    },
    'waves': {
        'name_key': 'audio_vis_waves',
        'name_default': '3D波形',
    },
    'circular': {
        'name_key': 'audio_vis_circular',
        'name_default': '3D环形',
    },
    'terrain': {
        'name_key': 'audio_vis_terrain',
        'name_default': '3D地形',
    },
    'cosmos': {
        'name_key': 'audio_vis_cosmos',
        'name_default': '3D宇宙',
    },
    'fluid': {
        'name_key': 'audio_vis_fluid',
        'name_default': '3D流体',
    },
    'ripple': {
        'name_key': 'audio_vis_ripple',
        'name_default': '粒子震荡洞洞波',
    },
    'none': {
        'name_key': 'audio_vis_none',
        'name_default': '关闭可视化',
    },
}

STYLE_KEYS = [k for k in AUDIO_VISUAL_STYLES if k != 'none']

FFT_SIZE = 4096
SAMPLE_RATE = 44100
AUDIO_CHANNELS = 2
NUM_BARS = 64


class AudioPCMProvider:
    def __init__(self):
        self._pcm_mono = np.zeros(0, dtype=np.float32)
        self._pcm_left = np.zeros(0, dtype=np.float32)
        self._pcm_right = np.zeros(0, dtype=np.float32)
        self._sample_rate = SAMPLE_RATE
        self._duration = 0.0
        self._time_pos = 0.0
        self._loading = False

    def start(self, file_path):
        self._pcm_mono = np.zeros(0, dtype=np.float32)
        self._pcm_left = np.zeros(0, dtype=np.float32)
        self._pcm_right = np.zeros(0, dtype=np.float32)
        self._duration = 0.0
        self._time_pos = 0.0
        self._loading = True
        import threading
        threading.Thread(target=self._decode_file, args=(file_path,), daemon=True).start()

    def stop(self):
        self._pcm_mono = np.zeros(0, dtype=np.float32)
        self._pcm_left = np.zeros(0, dtype=np.float32)
        self._pcm_right = np.zeros(0, dtype=np.float32)
        self._duration = 0.0

    def update_time_pos(self, time_pos):
        self._time_pos = max(0.0, time_pos)

    def get_samples(self, count=FFT_SIZE):
        if len(self._pcm_mono) == 0:
            return np.zeros(count, dtype=np.float32)
        idx = int(self._time_pos * self._sample_rate)
        start = max(0, idx - count)
        end = start + count
        if end > len(self._pcm_mono):
            end = len(self._pcm_mono)
            start = max(0, end - count)
        chunk = self._pcm_mono[start:end]
        if len(chunk) < count:
            padded = np.zeros(count, dtype=np.float32)
            padded[:len(chunk)] = chunk
            return padded
        return chunk

    def get_stereo_samples(self, count=256):
        if len(self._pcm_left) == 0:
            return np.zeros(count, dtype=np.float32), np.zeros(count, dtype=np.float32)
        idx = int(self._time_pos * self._sample_rate)
        start = max(0, idx - count)
        end = start + count
        left = self._pcm_left[start:end]
        right = self._pcm_right[start:end]
        if len(left) < count:
            padded_l = np.zeros(count, dtype=np.float32)
            padded_r = np.zeros(count, dtype=np.float32)
            padded_l[:len(left)] = left
            padded_r[:len(right)] = right
            return padded_l, padded_r
        return left, right

    def _decode_file(self, file_path):
        from core.log_manager import global_logger as _log
        try:
            native_path = os.path.normpath(file_path)
            _log.info(f"音频可视化: 开始预解码 {native_path}")
            cmd = [
                'ffmpeg', '-i', native_path,
                '-f', 's16le', '-acodec', 'pcm_s16le',
                '-ar', str(SAMPLE_RATE), '-ac', str(AUDIO_CHANNELS),
                '-v', 'error', '-'
            ]
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            chunks = []
            while True:
                raw = proc.stdout.read(SAMPLE_RATE * AUDIO_CHANNELS * 2)
                if not raw:
                    break
                samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
                chunks.append(samples)
            stderr_out = proc.stderr.read().decode('utf-8', errors='ignore') if proc.stderr else ''
            proc.wait()
            if chunks:
                all_samples = np.concatenate(chunks)
                self._pcm_left = all_samples[0::2].copy()
                self._pcm_right = all_samples[1::2].copy()
                self._pcm_mono = (self._pcm_left + self._pcm_right) / 2.0
                self._duration = len(self._pcm_mono) / self._sample_rate
                _log.info(f"音频可视化: 预解码完成, {self._duration:.1f}s, {len(self._pcm_mono)} samples")
            else:
                _log.warning(f"音频可视化: 预解码无数据, stderr={stderr_out[:500]}")
        except Exception as e:
            _log.error(f"音频可视化: 预解码失败 {e}")
        finally:
            self._loading = False


def compute_spectrum(samples, fft_size=FFT_SIZE, num_bars=NUM_BARS):
    if len(samples) < fft_size:
        padded = np.zeros(fft_size, dtype=np.float32)
        padded[:len(samples)] = samples
        samples = padded
    window = np.hanning(fft_size)
    windowed = samples[-fft_size:] * window
    fft_data = np.fft.rfft(windowed)
    magnitudes = np.abs(fft_data)
    freqs = np.fft.rfftfreq(fft_size, 1.0 / SAMPLE_RATE)
    min_freq = 20
    max_freq = min(18000, SAMPLE_RATE / 2)
    freq_res = SAMPLE_RATE / fft_size
    linear_bars = int(num_bars * 0.5)
    log_bars = num_bars - linear_bars
    linear_freqs = np.linspace(min_freq, 500, linear_bars + 1)
    min_bin_width = freq_res * 1.5
    for i in range(linear_bars):
        if linear_freqs[i + 1] - linear_freqs[i] < min_bin_width:
            linear_freqs[i + 1] = linear_freqs[i] + min_bin_width
    log_freqs = np.logspace(np.log10(max(500, linear_freqs[-1])), np.log10(max_freq), log_bars + 1)
    bar_freqs = np.concatenate([linear_freqs, log_freqs[1:]])
    bars = np.zeros(num_bars)
    for i in range(num_bars):
        mask = (freqs >= bar_freqs[i]) & (freqs < bar_freqs[i + 1])
        if np.any(mask):
            bars[i] = np.mean(magnitudes[mask])
    ref = np.percentile(magnitudes, 90) * 4.0
    if ref > 0:
        bars = bars / ref
    return np.clip(bars, 0, 1)


def _project_3d(x, y, z, w, h, cam_dist=8.0, fov_scale=0.1, pitch=0.45, yaw=0.0):
    cos_p = math.cos(-pitch)
    sin_p = math.sin(-pitch)
    cos_y = math.cos(yaw)
    sin_y = math.sin(yaw)
    y1 = y * cos_p - z * sin_p
    z1 = y * sin_p + z * cos_p
    x2 = x * cos_y - z1 * sin_y
    z2 = x * sin_y + z1 * cos_y
    y2 = y1
    depth = z2 + cam_dist
    if depth < 0.3:
        depth = 0.3
    scale = cam_dist / depth
    sx = w / 2 + x2 * scale * w * fov_scale
    sy = h / 2 - y2 * scale * h * fov_scale
    return sx, sy, depth, scale


class AudioVisualWidget(QWidget):
    def __init__(self, parent=None, player_controller=None):
        super().__init__(parent)
        self._style = 'spectrum'
        self._active = False
        self._pc = player_controller
        self._pcm = AudioPCMProvider()
        self._bars = np.zeros(NUM_BARS)
        self._smooth_bars = np.zeros(NUM_BARS)
        self._peak_bars = np.zeros(NUM_BARS)
        self._peak_decay = np.zeros(NUM_BARS, dtype=np.int32)
        self._wave_left = np.zeros(512)
        self._wave_right = np.zeros(512)
        self._cover_pixmap = None
        self._frame_count = 0

        self._cosmos_bg_stars = []
        self._cosmos_particles = []
        self._cosmos_meteors = []
        self._cosmos_rotation = 0.0
        self._fluid_hue = 0.0
        self._fluid_phase = 0.0
        self._fluid_buf = None
        self._fluid_buf_w = 0
        self._fluid_buf_h = 0
        self._spectrum_angle = 0.0
        self._ripple_phase = 0.0
        self._ripple_orb_x = 0.0
        self._ripple_cam_angle = 0.0
        self._ripple_ring_particles = []
        self._ripple_trail_particles = []
        self._ripple_bg_particles = []
        self._ripple_hue = 200.0
        self._bar_colors = [QColor.fromHsv(int(200 + i * 160 / NUM_BARS) % 360, 230, 255) for i in range(NUM_BARS)]
        self._bar_colors_dim = [QColor.fromHsv(int(200 + i * 160 / NUM_BARS) % 360, 180, 80) for i in range(NUM_BARS)]
        self._bar_colors_peak = [QColor.fromHsv(int(200 + i * 160 / NUM_BARS) % 360, 160, 255) for i in range(NUM_BARS)]
        self._random_mode = False
        self._random_timer = QTimer(self)
        self._random_timer.setInterval(15000)
        self._random_timer.timeout.connect(self._on_random_tick)
        self._fade_alpha = 1.0
        self._fade_state = 'visible'
        self._pending_style = None

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.setInterval(16)

    def set_style(self, style_key):
        is_random = (style_key == 'random')
        self._random_mode = is_random
        if is_random:
            style_key = random.choice(STYLE_KEYS)
            self._random_timer.start()
        else:
            self._random_timer.stop()
        if self._style == style_key and self._fade_state == 'visible':
            return
        if self._fade_alpha < 0.05:
            self._apply_style_now(style_key)
        else:
            self._pending_style = style_key
            self._fade_state = 'fading_out'

    def _apply_style_now(self, style_key):
        self._style = style_key
        if style_key == 'terrain':
            self._terrain_phase = 0.0
        elif style_key == 'cosmos':
            self._cosmos_bg_stars = []
            self._cosmos_particles = []
            self._cosmos_meteors = []
        elif style_key == 'fluid':
            self._fluid_buf = None
        elif style_key == 'ripple':
            self._ripple_phase = 0.0
            self._ripple_orb_x = 0.0
            self._ripple_cam_angle = 0.0
            self._ripple_ring_particles = []
            self._ripple_trail_particles = []
            self._ripple_bg_particles = []
            self._ripple_hue = 200.0
        self._peak_bars = np.zeros(NUM_BARS)
        self._peak_decay = np.zeros(NUM_BARS, dtype=np.int32)
        self._smooth_bars = np.zeros(NUM_BARS)

    def _on_random_tick(self):
        if not self._random_mode or not self._active:
            return
        available = [k for k in STYLE_KEYS if k != self._style]
        if available:
            new_style = random.choice(available)
        else:
            new_style = STYLE_KEYS[0]
        self._pending_style = new_style
        self._fade_state = 'fading_out'

    def get_style(self):
        return self._style

    def start(self, file_path=None):
        self._active = True
        if file_path and os.path.exists(file_path):
            self._pcm.start(file_path)
        self._timer.start()
        self.show()
        self.raise_()

    def stop(self):
        self._active = False
        self._pcm.stop()
        self._timer.stop()
        self.hide()

    def is_active(self):
        return self._active

    def set_cover(self, pixmap):
        self._cover_pixmap = pixmap

    def _tick(self):
        if not self._active:
            return
        self._sync_parent_size()
        self._update_fade()
        if self._pc and hasattr(self._pc, '_get_mpv_property_double'):
            try:
                t = self._pc._get_mpv_property_double('time-pos')
                if t is not None:
                    self._pcm.update_time_pos(t)
            except Exception:
                pass
        self._update_data()
        self.update()

    def _sync_parent_size(self):
        parent = self.parent()
        if parent:
            pw, ph = parent.width(), parent.height()
            if pw > 0 and ph > 0 and (self.width() != pw or self.height() != ph):
                self.setGeometry(0, 0, pw, ph)

    def _update_fade(self):
        if self._fade_state == 'fading_out':
            self._fade_alpha -= 0.06
            if self._fade_alpha <= 0.0:
                self._fade_alpha = 0.0
                if self._pending_style:
                    self._apply_style_now(self._pending_style)
                    self._pending_style = None
                self._fade_state = 'fading_in'
        elif self._fade_state == 'fading_in':
            self._fade_alpha += 0.04
            if self._fade_alpha >= 1.0:
                self._fade_alpha = 1.0
                self._fade_state = 'visible'

    def _update_data(self):
        self._frame_count += 1
        needs_bars = self._style in ('spectrum', 'circular', 'terrain', 'cosmos', 'fluid', 'ripple')
        if needs_bars:
            samples = self._pcm.get_samples(FFT_SIZE)
            self._bars = compute_spectrum(samples, FFT_SIZE, NUM_BARS)
            self._smooth_bars += (self._bars - self._smooth_bars) * 0.55
            for i in range(NUM_BARS):
                if self._bars[i] > self._peak_bars[i]:
                    self._peak_bars[i] = self._bars[i]
                    self._peak_decay[i] = 0
                else:
                    self._peak_decay[i] += 1
                    if self._peak_decay[i] > 10:
                        self._peak_bars[i] *= 0.9
        if self._style == 'waves':
            self._wave_left, self._wave_right = self._pcm.get_stereo_samples(512)
        if self._style == 'cosmos':
            self._update_cosmos()
        if self._style == 'terrain':
            self._terrain_phase += 0.015 + float(np.mean(self._bars[:8])) * 0.04
        if self._style == 'fluid':
            self._update_fluid()
        if self._style == 'spectrum':
            self._spectrum_angle += 0.003
        if self._style == 'ripple':
            self._update_ripple()


    def _update_cosmos(self):
        w = self.width()
        h = self.height()
        if w <= 0 or h <= 0:
            return
        bass = float(np.mean(self._bars[:8]))
        mid = float(np.mean(self._bars[8:30]))
        high = float(np.mean(self._bars[30:]))
        cx, cy = w / 2, h / 2
        self._cosmos_rotation += 0.003 + bass * 0.01
        if len(self._cosmos_bg_stars) < 300:
            for _ in range(5):
                self._cosmos_bg_stars.append({
                    'x': random.uniform(-4, 4),
                    'y': random.uniform(-3, 3),
                    'z': random.uniform(-8, 2),
                    'size': random.uniform(0.02, 0.08),
                    'twinkle': random.uniform(0, math.pi * 2),
                    'speed': random.uniform(0.02, 0.06),
                })
        for s in self._cosmos_bg_stars:
            s['twinkle'] += s['speed']
        energy = bass + mid + high
        if energy > 0.15:
            count = int(energy * 8) + 2
            for _ in range(count):
                angle = random.uniform(0, 2 * math.pi)
                speed = 0.03 + bass * 0.15
                dist = random.uniform(0, 0.3)
                hue = random.randint(160, 320)
                self._cosmos_particles.append({
                    'x': math.cos(angle) * dist,
                    'y': random.uniform(-0.1, 0.1),
                    'z': math.sin(angle) * dist,
                    'vx': math.cos(angle) * speed,
                    'vy': random.uniform(-0.005, 0.005),
                    'vz': math.sin(angle) * speed,
                    'life': 1.0,
                    'size': 0.03 + bass * 0.1 + random.random() * 0.03,
                    'hue': hue,
                })
        alive = []
        for p in self._cosmos_particles:
            p['x'] += p['vx']
            p['y'] += p['vy']
            p['z'] += p['vz']
            p['vx'] *= 0.995
            p['vy'] *= 0.995
            p['vz'] *= 0.995
            p['life'] -= 0.008
            if p['life'] > 0:
                alive.append(p)
        self._cosmos_particles = alive[-2000:]
        if random.random() < 0.02 + bass * 0.15:
            angle = random.uniform(0, 2 * math.pi)
            speed = 0.1 + bass * 0.2
            self._cosmos_meteors.append({
                'x': math.cos(angle) * 4,
                'y': random.uniform(-1, 1),
                'z': math.sin(angle) * 4,
                'vx': -math.cos(angle) * speed,
                'vy': random.uniform(-0.01, 0.01),
                'vz': -math.sin(angle) * speed,
                'life': 1.0,
                'len': 0.5 + bass * 1.0,
                'hue': random.randint(30, 60),
            })
        m_alive = []
        for m in self._cosmos_meteors:
            m['x'] += m['vx']
            m['y'] += m['vy']
            m['z'] += m['vz']
            m['life'] -= 0.02
            if m['life'] > 0:
                m_alive.append(m)
        self._cosmos_meteors = m_alive[-30:]

    def _update_fluid(self):
        self._fluid_hue = (self._fluid_hue + 0.3) % 360
        bass = float(np.mean(self._bars[:8]))
        mid = float(np.mean(self._bars[8:30]))
        self._fluid_phase += 0.02 + bass * 0.06 + mid * 0.03

    def _update_ripple(self):
        bass = float(np.mean(self._bars[:8]))
        mid = float(np.mean(self._bars[8:30]))
        self._ripple_phase += 0.012 + bass * 0.04
        self._ripple_hue = (self._ripple_hue + 0.4 + mid * 0.8) % 360
        # 光斑沿 X 轴匀速向右移动（较快，让伞面效果间距明显）
        self._ripple_orb_x += 0.12
        # 摄像机绕光斑缓慢旋转（多角度观看：后、左、前、右...）
        self._ripple_cam_angle += 0.006
        # 背景星空粒子
        if len(self._ripple_bg_particles) < 80:
            for _ in range(3):
                angle = random.uniform(0, 2 * math.pi)
                dist = random.uniform(2.5, 5.5)
                self._ripple_bg_particles.append({
                    'x': math.cos(angle) * dist,
                    'y': random.uniform(-0.4, 0.4),
                    'z': math.sin(angle) * dist,
                    'twinkle': random.uniform(0, math.pi * 2),
                    'speed': random.uniform(0.03, 0.08),
                    'size': random.uniform(0.02, 0.06),
                    'hue': random.randint(180, 320),
                })
        for p in self._ripple_bg_particles:
            p['twinkle'] += p['speed']
        # 每帧在光斑当前位置发射一圈粒子，半径基于节奏强度
        # 节奏强时半径大、粒子多；节奏弱时半径小、粒子少
        energy = bass * 0.7 + mid * 0.3
        num_emit = int(6 + energy * 18)
        radius = 0.15 + energy * 1.8
        orb_x = self._ripple_orb_x
        base_hue = int(self._ripple_hue) % 360
        for i in range(num_emit):
            angle = i * 2 * math.pi / num_emit + self._ripple_phase * 0.5
            self._ripple_ring_particles.append({
                'x': orb_x,
                'angle': angle,
                'r': radius * random.uniform(0.85, 1.15),
                'age': 0.0,
                'max_age': random.uniform(1.8, 3.0),
                'hue': (base_hue + random.randint(-20, 20)) % 360,
                'size_factor': random.uniform(0.6, 1.4),
            })
        # 路径粒子：光斑经过的路径留下持续的粒子轨迹线
        for _ in range(3):
            self._ripple_trail_particles.append({
                'x': orb_x,
                'y': random.uniform(-0.04, 0.04),
                'z': random.uniform(-0.04, 0.04),
                'age': 0.0,
                'max_age': random.uniform(6.0, 10.0),
                'hue': (base_hue + random.randint(-10, 10)) % 360,
                'size_factor': random.uniform(0.5, 1.0),
            })
        # 更新圆环粒子年龄，移除过期粒子
        alive = []
        for p in self._ripple_ring_particles:
            p['age'] += 1 / 60.0
            if p['age'] < p['max_age']:
                alive.append(p)
        if len(alive) > 2000:
            alive = alive[-2000:]
        self._ripple_ring_particles = alive
        # 更新路径粒子年龄，移除过期粒子
        trail_alive = []
        for p in self._ripple_trail_particles:
            p['age'] += 1 / 60.0
            if p['age'] < p['max_age']:
                trail_alive.append(p)
        if len(trail_alive) > 1500:
            trail_alive = trail_alive[-1500:]
        self._ripple_trail_particles = trail_alive

    def paintEvent(self, event):
        if not self._active:
            return
        painter = QPainter(self)
        w = self.width()
        h = self.height()
        if w <= 0 or h <= 0:
            painter.end()
            return

        painter.fillRect(0, 0, w, h, QColor(5, 5, 10))

        if self._cover_pixmap and not self._cover_pixmap.isNull():
            painter.setOpacity(0.06)
            scaled = self._cover_pixmap.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
            x = (w - scaled.width()) // 2
            y = (h - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)
            painter.setOpacity(1.0)

        style_map = {
            'spectrum': self._paint_spectrum,
            'waves': self._paint_waves,
            'circular': self._paint_circular,
            'terrain': self._paint_terrain,
            'cosmos': self._paint_cosmos,
            'fluid': self._paint_fluid,
            'ripple': self._paint_ripple,
        }
        paint_fn = style_map.get(self._style, self._paint_spectrum)
        painter.setOpacity(self._fade_alpha)
        paint_fn(painter, w, h)

        bass = float(np.mean(self._smooth_bars[:8])) if len(self._smooth_bars) > 0 else 0
        cx, cy = w / 2, h / 2
        max_dist = math.sqrt(cx * cx + cy * cy)
        vignette = QRadialGradient(cx, cy, max_dist)
        vignette.setColorAt(0, QColor(0, 0, 0, 0))
        vignette.setColorAt(0.45, QColor(0, 0, 0, 0))
        vignette.setColorAt(0.75, QColor(0, 0, 0, int(50 + (1 - min(bass * 2, 1)) * 70)))
        vignette.setColorAt(1, QColor(0, 0, 0, 210))
        painter.setOpacity(self._fade_alpha)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(vignette))
        painter.drawRect(QRectF(0, 0, w, h))

        painter.end()

    def _paint_spectrum(self, painter, w, h):
        bars = self._smooth_bars
        peaks = self._peak_bars
        n = len(bars)
        bass = float(np.mean(bars[:8]))
        mid = float(np.mean(bars[8:30]))
        cx = w / 2
        pitch = 0.5
        proj = lambda x, y, z: _project_3d(x, y, z, w, h, pitch=pitch)
        painter.setPen(Qt.PenStyle.NoPen)
        floor_grad = QRadialGradient(cx, h, h * 0.7)
        floor_grad.setColorAt(0, QColor(30, 60, 150, int(bass * 50)))
        floor_grad.setColorAt(1, QColor(5, 5, 10, 0))
        painter.setBrush(QBrush(floor_grad))
        painter.drawRect(QRectF(0, 0, w, h))

        grid_z_start = -2.0
        grid_z_end = 2.0
        grid_x_start = -4.0
        grid_x_end = 4.0
        grid_y_base = -1.5
        grid_steps_z = 10
        grid_steps_x = 12
        painter.setPen(QPen(QColor(40, 60, 120, 25), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for gi in range(grid_steps_z + 1):
            z = grid_z_start + gi * (grid_z_end - grid_z_start) / grid_steps_z
            sx1, sy1, _, _ = proj(grid_x_start, grid_y_base, z)
            sx2, sy2, _, _ = proj(grid_x_end, grid_y_base, z)
            painter.drawLine(int(sx1), int(sy1), int(sx2), int(sy2))
        for gi in range(grid_steps_x + 1):
            x = grid_x_start + gi * (grid_x_end - grid_x_start) / grid_steps_x
            sx1, sy1, _, _ = proj(x, grid_y_base, grid_z_start)
            sx2, sy2, _, _ = proj(x, grid_y_base, grid_z_end)
            painter.drawLine(int(sx1), int(sy1), int(sx2), int(sy2))

        bar_spacing = (grid_x_end - grid_x_start) / n
        bar_width_3d = bar_spacing * 0.7
        sorted_bars = []
        for i in range(n):
            x3d = grid_x_start + i * bar_spacing + bar_spacing * 0.15
            z3d = grid_z_start + 0.5 + (i % 3) * 0.3
            val = bars[i]
            peak_val = peaks[i]
            bar_h = val * 3.0
            peak_h = peak_val * 3.0
            sorted_bars.append((z3d, x3d, val, peak_val, bar_h, peak_h, i))
        sorted_bars.sort(key=lambda b: -b[0])

        painter.setPen(Qt.PenStyle.NoPen)
        for z3d, x3d, val, peak_val, bar_h, peak_h, i in sorted_bars:
            base_color = QColor(self._bar_colors[i])
            top_color = QColor(base_color)
            top_color.setRed(min(255, int(base_color.red() * 1.3)))
            top_color.setGreen(min(255, int(base_color.green() * 1.3)))
            top_color.setBlue(min(255, int(base_color.blue() * 1.3)))
            side_color = QColor(base_color)
            side_color.setRed(max(0, int(base_color.red() * 0.5)))
            side_color.setGreen(max(0, int(base_color.green() * 0.5)))
            side_color.setBlue(max(0, int(base_color.blue() * 0.5)))

            fl_sx, fl_sy, fl_d, fl_sc = proj(x3d, grid_y_base, z3d)
            fr_sx, fr_sy, fr_d, fr_sc = proj(x3d + bar_width_3d, grid_y_base, z3d)
            tl_sx, tl_sy, tl_d, tl_sc = proj(x3d, grid_y_base + bar_h, z3d)
            tr_sx, tr_sy, tr_d, tr_sc = proj(x3d + bar_width_3d, grid_y_base + bar_h, z3d)
            bl_sx, bl_sy, bl_d, bl_sc = proj(x3d, grid_y_base, z3d + bar_width_3d * 0.5)
            br_sx, br_sy, br_d, br_sc = proj(x3d + bar_width_3d, grid_y_base, z3d + bar_width_3d * 0.5)
            btl_sx, btl_sy, _, _ = proj(x3d, grid_y_base + bar_h, z3d + bar_width_3d * 0.5)
            btr_sx, btr_sy, _, _ = proj(x3d + bar_width_3d, grid_y_base + bar_h, z3d + bar_width_3d * 0.5)

            right_face = QPolygonF([
                QPointF(fr_sx, fr_sy), QPointF(tr_sx, tr_sy),
                QPointF(btr_sx, btr_sy), QPointF(br_sx, br_sy),
            ])
            painter.setBrush(side_color)
            painter.drawPolygon(right_face)

            top_face = QPolygonF([
                QPointF(tl_sx, tl_sy), QPointF(tr_sx, tr_sy),
                QPointF(btr_sx, btr_sy), QPointF(btl_sx, btl_sy),
            ])
            painter.setBrush(top_color)
            painter.drawPolygon(top_face)

            front_face = QPolygonF([
                QPointF(fl_sx, fl_sy), QPointF(fr_sx, fr_sy),
                QPointF(tr_sx, tr_sy), QPointF(tl_sx, tl_sy),
            ])
            front_grad = QLinearGradient(fl_sx, tl_sy, fl_sx, fl_sy)
            front_grad.setColorAt(0, base_color)
            front_grad.setColorAt(1, QColor(max(0, base_color.red() - 40), max(0, base_color.green() - 40), max(0, base_color.blue() - 40), base_color.alpha()))
            painter.setBrush(QBrush(front_grad))
            painter.drawPolygon(front_face)

            if peak_val > 0.02:
                pk_y = grid_y_base + peak_h
                pfl_sx, pfl_sy, _, _ = proj(x3d, pk_y, z3d)
                pfr_sx, pfr_sy, _, _ = proj(x3d + bar_width_3d, pk_y, z3d)
                pbtl_sx, pbtl_sy, _, _ = proj(x3d, pk_y, z3d + bar_width_3d * 0.5)
                pbtr_sx, pbtr_sy, _, _ = proj(x3d + bar_width_3d, pk_y, z3d + bar_width_3d * 0.5)
                peak_face = QPolygonF([
                    QPointF(pfl_sx, pfl_sy), QPointF(pfr_sx, pfr_sy),
                    QPointF(pbtr_sx, pbtr_sy), QPointF(pbtl_sx, pbtl_sy),
                ])
                painter.setBrush(self._bar_colors_peak[i])
                painter.drawPolygon(peak_face)

    def _paint_waves(self, painter, w, h):
        n = len(self._wave_left)
        if n < 2:
            return
        cy = h / 2
        cx = w / 2
        bass = float(np.mean(self._smooth_bars[:8])) if len(self._smooth_bars) > 0 else 0
        pitch = 0.45
        proj = lambda x, y, z: _project_3d(x, y, z, w, h, pitch=pitch)

        floor_y = -1.2
        grid_z_start = -3.0
        grid_z_end = 3.0
        grid_x_start = -4.0
        grid_x_end = 4.0
        painter.setPen(QPen(QColor(30, 50, 100, 20), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for gi in range(8):
            z = grid_z_start + gi * (grid_z_end - grid_z_start) / 7
            sx1, sy1, _, _ = proj(grid_x_start, floor_y, z)
            sx2, sy2, _, _ = proj(grid_x_end, floor_y, z)
            painter.drawLine(int(sx1), int(sy1), int(sx2), int(sy2))

        for ch_idx, (wave_data, base_alpha, ribbon_thick) in enumerate([
            (self._wave_left, 200, 0.15), (self._wave_right, 120, 0.10)
        ]):
            z_base = -0.5 + ch_idx * 1.0
            x_start = -3.5
            x_end = 3.5
            step = max(1, n // 80)
            top_pts = []
            bot_pts = []
            for i in range(0, n, step):
                x3d = x_start + (x_end - x_start) * i / (n - 1)
                amp = float(wave_data[i]) * 1.5
                y_top = floor_y + 0.3 + amp + ribbon_thick
                y_bot = floor_y + 0.3 + amp - ribbon_thick
                tsx, tsy, td, tsc = proj(x3d, y_top, z_base)
                bsx, bsy, bd, bsc = proj(x3d, y_bot, z_base)
                top_pts.append((tsx, tsy, td))
                bot_pts.append((bsx, bsy, bd))

            if len(top_pts) < 2:
                continue

            front_face = QPolygonF()
            for pt in top_pts:
                front_face.append(QPointF(pt[0], pt[1]))
            for pt in reversed(bot_pts):
                front_face.append(QPointF(pt[0], pt[1]))

            if ch_idx == 0:
                fill_color = QColor(0, 150, 255, int(base_alpha * 0.5))
                side_color = QColor(0, 80, 180, int(base_alpha * 0.3))
                edge_color = QColor(100, 200, 255, base_alpha)
            else:
                fill_color = QColor(255, 100, 150, int(base_alpha * 0.4))
                side_color = QColor(180, 50, 80, int(base_alpha * 0.25))
                edge_color = QColor(255, 150, 200, base_alpha)

            z_back = z_base + 0.3
            back_top_pts = []
            back_bot_pts = []
            for i in range(0, n, step):
                x3d = x_start + (x_end - x_start) * i / (n - 1)
                amp = float(wave_data[i]) * 1.5
                y_top = floor_y + 0.3 + amp + ribbon_thick
                y_bot = floor_y + 0.3 + amp - ribbon_thick
                tsx, tsy, _, _ = proj(x3d, y_top, z_back)
                bsx, bsy, _, _ = proj(x3d, y_bot, z_back)
                back_top_pts.append((tsx, tsy))
                back_bot_pts.append((bsx, bsy))

            if len(back_top_pts) >= 2:
                top_face = QPolygonF()
                for pt in top_pts:
                    top_face.append(QPointF(pt[0], pt[1]))
                for pt in reversed(back_top_pts):
                    top_face.append(QPointF(pt[0], pt[1]))
                painter.setPen(Qt.PenStyle.NoPen)
                top_grad = QLinearGradient(0, top_pts[0][1], 0, back_top_pts[0][1])
                top_grad.setColorAt(0, QColor(fill_color.red(), fill_color.green(), fill_color.blue(), int(fill_color.alpha() * 0.8)))
                top_grad.setColorAt(1, QColor(side_color.red(), side_color.green(), side_color.blue(), int(side_color.alpha() * 0.5)))
                painter.setBrush(QBrush(top_grad))
                painter.drawPolygon(top_face)

                right_face = QPolygonF()
                right_face.append(QPointF(top_pts[-1][0], top_pts[-1][1]))
                right_face.append(QPointF(back_top_pts[-1][0], back_top_pts[-1][1]))
                right_face.append(QPointF(back_bot_pts[-1][0], back_bot_pts[-1][1]))
                right_face.append(QPointF(bot_pts[-1][0], bot_pts[-1][1]))
                painter.setBrush(side_color)
                painter.drawPolygon(right_face)

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(fill_color))
            painter.drawPolygon(front_face)

            painter.setPen(QPen(edge_color, 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            for j in range(1, len(top_pts)):
                painter.drawLine(int(top_pts[j-1][0]), int(top_pts[j-1][1]),
                                 int(top_pts[j][0]), int(top_pts[j][1]))

        glow = QRadialGradient(cx, cy, min(w, h) * 0.45)
        glow.setColorAt(0, QColor(30, 100, 200, int(15 + bass * 30)))
        glow.setColorAt(0.6, QColor(10, 40, 100, 5))
        glow.setColorAt(1, QColor(0, 0, 0, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(glow))
        painter.drawRect(QRectF(0, 0, w, h))

    def _paint_circular(self, painter, w, h):
        bars = self._smooth_bars
        n = len(bars)
        bass = float(np.mean(bars[:8]))
        mid = float(np.mean(bars[8:30]))
        cx, cy = w / 2, h / 2
        pitch = 0.5
        proj = lambda x, y, z: _project_3d(x, y, z, w, h, pitch=pitch)

        ring_radius = 2.0
        bar_max_h = 2.5
        ring_y = 0.0
        tilt_angle = 0.4 + bass * 0.15

        painter.setPen(Qt.PenStyle.NoPen)
        floor_pts = []
        for ai in range(64):
            a = ai * 2 * math.pi / 64
            x = ring_radius * 1.8 * math.cos(a)
            z = ring_radius * 1.8 * math.sin(a)
            sx, sy, _, _ = proj(x, ring_y - 0.5, z)
            floor_pts.append(QPointF(sx, sy))
        if len(floor_pts) > 2:
            floor_grad = QRadialGradient(cx, cy, min(w, h) * 0.4)
            floor_grad.setColorAt(0, QColor(10, 15, 40, 80))
            floor_grad.setColorAt(1, QColor(5, 5, 15, 0))
            painter.setBrush(QBrush(floor_grad))
            painter.drawPolygon(QPolygonF(floor_pts))

        ring_base = []
        for i in range(n):
            angle = i * 2 * math.pi / n
            x = ring_radius * math.cos(angle)
            z = ring_radius * math.sin(angle)
            sx, sy, d, sc = proj(x, ring_y, z)
            ring_base.append((sx, sy, d, sc, angle, x, z))

        sorted_indices = sorted(range(n), key=lambda i: -ring_base[i][2])

        painter.setPen(Qt.PenStyle.NoPen)
        for idx in sorted_indices:
            val = bars[idx]
            if val < 0.01:
                continue
            sx, sy, d, sc, angle, x, z = ring_base[idx]
            bar_h = val * bar_max_h
            bar_w_3d = 0.12

            base_color = QColor(self._bar_colors[idx])
            top_color = QColor(base_color)
            top_color.setRed(min(255, int(base_color.red() * 1.3)))
            top_color.setGreen(min(255, int(base_color.green() * 1.3)))
            top_color.setBlue(min(255, int(base_color.blue() * 1.3)))
            side_color = QColor(base_color)
            side_color.setRed(max(0, int(base_color.red() * 0.5)))
            side_color.setGreen(max(0, int(base_color.green() * 0.5)))
            side_color.setBlue(max(0, int(base_color.blue() * 0.5)))

            dx = math.cos(angle) * bar_w_3d
            dz = math.sin(angle) * bar_w_3d
            nx = -math.sin(angle) * bar_w_3d * 0.5
            nz = math.cos(angle) * bar_w_3d * 0.5

            fl = proj(x - nx, ring_y, z - nz)
            fr = proj(x + dx - nx, ring_y, z + dz - nz)
            ftl = proj(x - nx, ring_y + bar_h, z - nz)
            ftr = proj(x + dx - nx, ring_y + bar_h, z + dz - nz)
            bl = proj(x - nx, ring_y, z - nz + bar_w_3d * 0.3)
            br = proj(x + dx - nx, ring_y, z + dz + bar_w_3d * 0.3)
            btl = proj(x - nx, ring_y + bar_h, z - nz + bar_w_3d * 0.3)
            btr = proj(x + dx - nx, ring_y + bar_h, z + dz + bar_w_3d * 0.3)

            front_face = QPolygonF([QPointF(fl[0], fl[1]), QPointF(fr[0], fr[1]),
                                     QPointF(ftr[0], ftr[1]), QPointF(ftl[0], ftl[1])])
            front_grad = QLinearGradient(fl[0], ftl[1], fl[0], fl[1])
            front_grad.setColorAt(0, base_color)
            front_grad.setColorAt(1, QColor(max(0, base_color.red() - 40), max(0, base_color.green() - 40), max(0, base_color.blue() - 40), base_color.alpha()))
            painter.setBrush(QBrush(front_grad))
            painter.drawPolygon(front_face)

            top_face = QPolygonF([QPointF(ftl[0], ftl[1]), QPointF(ftr[0], ftr[1]),
                                   QPointF(btr[0], btr[1]), QPointF(btl[0], btl[1])])
            painter.setBrush(top_color)
            painter.drawPolygon(top_face)

            right_face = QPolygonF([QPointF(fr[0], fr[1]), QPointF(br[0], br[1]),
                                     QPointF(btr[0], btr[1]), QPointF(ftr[0], ftr[1])])
            painter.setBrush(side_color)
            painter.drawPolygon(right_face)

        core_sx, core_sy, _, core_sc = proj(0, ring_y, 0)
        core_r = 15 * core_sc
        if core_r > 2:
            core_grad = QRadialGradient(core_sx, core_sy, core_r * 3)
            core_grad.setColorAt(0, QColor(255, 240, 255, int(100 + bass * 155)))
            core_grad.setColorAt(0.3, QColor(100, 180, 255, int(50 + bass * 80)))
            core_grad.setColorAt(1, QColor(20, 40, 100, 0))
            painter.setBrush(QBrush(core_grad))
            painter.drawEllipse(QRectF(core_sx - core_r * 3, core_sy - core_r * 3, core_r * 6, core_r * 6))

    def _paint_terrain(self, painter, w, h):
        bars = self._smooth_bars
        n = len(bars)
        bass = float(np.mean(bars[:8]))
        mid = float(np.mean(bars[8:30]))
        phase = self._terrain_phase
        pitch = 0.55
        yaw = 0.0
        painter.setPen(Qt.PenStyle.NoPen)

        grid_x = np.linspace(-4, 4, n)
        grid_z = np.linspace(-3, 3, 20)
        height_map = []
        for zi, z in enumerate(grid_z):
            row = []
            for xi, x in enumerate(grid_x):
                freq_idx = min(int(xi * n / n), n - 1)
                val = bars[freq_idx]
                h_val = val * 2.5
                h_val += math.sin(x * 0.8 + phase) * 0.3 * (1 + bass)
                h_val += math.cos(z * 0.6 + phase * 0.7) * 0.2 * (1 + mid)
                h_val += math.sin(x * 1.5 + z * 1.2 + phase * 1.3) * 0.15
                row.append(h_val)
            height_map.append(row)

        for zi in range(len(grid_z) - 2, -1, -1):
            z_back = grid_z[zi + 1]
            z_front = grid_z[zi]
            for xi in range(n - 1):
                x0 = grid_x[xi]
                x1 = grid_x[xi + 1]
                h00 = height_map[zi][xi]
                h10 = height_map[zi][xi + 1]
                h01 = height_map[zi + 1][xi]
                h11 = height_map[zi + 1][xi + 1]

                p00 = _project_3d(x0, h00, z_front, w, h, pitch=pitch, yaw=yaw)
                p10 = _project_3d(x1, h10, z_front, w, h, pitch=pitch, yaw=yaw)
                p01 = _project_3d(x0, h01, z_back, w, h, pitch=pitch, yaw=yaw)
                p11 = _project_3d(x1, h11, z_back, w, h, pitch=pitch, yaw=yaw)

                avg_h = (h00 + h10 + h01 + h11) / 4
                t = min(1.0, avg_h / 2.5)
                if t < 0.3:
                    r = int(10 + t * 80)
                    g = int(40 + t * 200)
                    b = int(80 + t * 150)
                elif t < 0.6:
                    r = int(30 + t * 100)
                    g = int(100 + t * 200)
                    b = int(180 + t * 75)
                else:
                    r = int(100 + t * 155)
                    g = int(180 + t * 75)
                    b = int(220 + t * 35)
                depth_fade = max(0.3, min(1.0, p00[3] * 0.35))
                alpha = int(200 * depth_fade)

                quad = QPolygonF([
                    QPointF(p00[0], p00[1]),
                    QPointF(p10[0], p10[1]),
                    QPointF(p11[0], p11[1]),
                    QPointF(p01[0], p01[1]),
                ])
                face_color = QColor(min(255, r), min(255, g), min(255, b), alpha)
                painter.setBrush(face_color)
                painter.drawPolygon(quad)

                if xi % 4 == 0 and zi % 2 == 0:
                    painter.setPen(QPen(QColor(min(255, r + 40), min(255, g + 40), min(255, b + 40), int(alpha * 0.3)), 1))
                    painter.drawLine(int(p00[0]), int(p00[1]), int(p10[0]), int(p10[1]))
                    painter.drawLine(int(p00[0]), int(p00[1]), int(p01[0]), int(p01[1]))
                    painter.setPen(Qt.PenStyle.NoPen)

        water_y = -0.2
        water_pts_front = []
        water_pts_back = []
        for xi in range(n):
            x = grid_x[xi]
            sf = _project_3d(x, water_y, grid_z[0], w, h, pitch=pitch, yaw=yaw)
            sb = _project_3d(x, water_y, grid_z[-1], w, h, pitch=pitch, yaw=yaw)
            water_pts_front.append(QPointF(sf[0], sf[1]))
            water_pts_back.append(QPointF(sb[0], sb[1]))
        if len(water_pts_front) > 2:
            water_poly = QPolygonF()
            for pt in water_pts_front:
                water_poly.append(pt)
            for pt in reversed(water_pts_back):
                water_poly.append(pt)
            water_grad = QLinearGradient(0, water_pts_front[0].y(), 0, water_pts_back[0].y())
            water_grad.setColorAt(0, QColor(20, 60, 140, 40))
            water_grad.setColorAt(0.5, QColor(10, 40, 120, 25))
            water_grad.setColorAt(1, QColor(5, 20, 80, 15))
            painter.setBrush(QBrush(water_grad))
            painter.drawPolygon(water_poly)

    def _paint_cosmos(self, painter, w, h):
        bars = self._smooth_bars
        bass = float(np.mean(bars[:8]))
        mid = float(np.mean(bars[8:30]))
        high = float(np.mean(bars[30:]))
        cx, cy = w / 2, h / 2
        pitch = 0.35
        proj = lambda x, y, z: _project_3d(x, y, z, w, h, pitch=pitch)
        painter.setPen(Qt.PenStyle.NoPen)

        for s in self._cosmos_bg_stars:
            sx, sy, depth, scale = proj(s['x'], s['y'], s['z'])
            if not (0 <= sx <= w and 0 <= sy <= h):
                continue
            brightness = 0.4 + 0.6 * (0.5 + 0.5 * math.sin(s['twinkle']))
            depth_fade = max(0.2, min(1.0, scale * 0.4))
            alpha = int(brightness * 200 * depth_fade)
            screen_size = max(1, s['size'] * scale * 40)
            grad = QRadialGradient(sx, sy, screen_size * 2)
            grad.setColorAt(0, QColor(255, 255, 255, int(alpha * 0.8)))
            grad.setColorAt(0.3, QColor(200, 220, 255, alpha))
            grad.setColorAt(1, QColor(100, 150, 255, 0))
            painter.setBrush(QBrush(grad))
            painter.drawEllipse(QRectF(sx - screen_size * 2, sy - screen_size * 2, screen_size * 4, screen_size * 4))

        core_sx, core_sy, core_d, core_sc = proj(0, 0, 0)
        core_r = max(5, 20 * core_sc)
        core_grad = QRadialGradient(core_sx, core_sy, core_r * 5)
        core_grad.setColorAt(0, QColor(255, 240, 255, int(150 + bass * 105)))
        core_grad.setColorAt(0.1, QColor(200, 180, 255, int(100 + bass * 80)))
        core_grad.setColorAt(0.3, QColor(120, 100, 230, int(40 + bass * 50)))
        core_grad.setColorAt(1, QColor(20, 15, 80, 0))
        painter.setBrush(QBrush(core_grad))
        painter.drawEllipse(QRectF(core_sx - core_r * 5, core_sy - core_r * 5, core_r * 10, core_r * 10))

        spiral_arms = 4
        for arm in range(spiral_arms):
            arm_angle = self._cosmos_rotation * 2 + arm * 2 * math.pi / spiral_arms
            for seg in range(25):
                t = seg / 25.0
                r = 0.3 + t * 3.0
                a = arm_angle + t * 3.5
                x3d = r * math.cos(a)
                z3d = r * math.sin(a)
                y3d = (math.sin(a * 2 + t * 4) * 0.3) * (1 - t * 0.5)
                sx, sy, d, sc = proj(x3d, y3d, z3d)
                if not (-20 <= sx <= w + 20 and -20 <= sy <= h + 20):
                    continue
                arm_val = bass * (1.0 - t * 0.6)
                dot_size = max(1, (0.04 + arm_val * 0.12) * sc * 30)
                hue = int(200 + arm * 40 + t * 60) % 360
                alpha = int((30 + arm_val * 150) * max(0.2, sc * 0.4) * (1.0 - t * 0.6))
                grad = QRadialGradient(sx, sy, dot_size * 2)
                grad.setColorAt(0, QColor(255, 255, 255, int(alpha * 0.5)))
                grad.setColorAt(0.3, QColor.fromHsv(hue, 160, 255, alpha))
                grad.setColorAt(1, QColor.fromHsv(hue, 180, 200, 0))
                painter.setBrush(QBrush(grad))
                painter.drawEllipse(QRectF(sx - dot_size * 2, sy - dot_size * 2, dot_size * 4, dot_size * 4))

        sorted_particles = sorted(self._cosmos_particles, key=lambda p: -proj(p['x'], p['y'], p['z'])[2])
        for p in sorted_particles:
            alpha = int(p['life'] * 200)
            sx, sy, d, sc = proj(p['x'], p['y'], p['z'])
            if not (-20 <= sx <= w + 20 and -20 <= sy <= h + 20):
                continue
            screen_size = max(1, p['size'] * sc * 30)
            depth_fade = max(0.2, min(1.0, sc * 0.4))
            grad = QRadialGradient(sx, sy, screen_size * 1.5)
            grad.setColorAt(0, QColor(255, 255, 255, int(alpha * 0.4 * depth_fade)))
            grad.setColorAt(0.4, QColor.fromHsv(p['hue'], 180, 255, int(alpha * depth_fade)))
            grad.setColorAt(1, QColor.fromHsv(p['hue'], 200, 200, 0))
            painter.setBrush(QBrush(grad))
            painter.drawEllipse(QRectF(sx - screen_size * 1.5, sy - screen_size * 1.5, screen_size * 3, screen_size * 3))

        for m in self._cosmos_meteors:
            alpha = int(m['life'] * 220)
            sx, sy, d, sc = proj(m['x'], m['y'], m['z'])
            tail_x = m['x'] - m['vx'] / (abs(m['vx']) + abs(m['vz']) + 0.01) * m['len']
            tail_z = m['z'] - m['vz'] / (abs(m['vx']) + abs(m['vz']) + 0.01) * m['len']
            tsx, tsy, _, _ = proj(tail_x, m['y'], tail_z)
            depth_fade = max(0.3, min(1.0, sc * 0.4))
            grad = QLinearGradient(tsx, tsy, sx, sy)
            grad.setColorAt(0, QColor.fromHsv(m['hue'], 100, 255, 0))
            grad.setColorAt(0.7, QColor.fromHsv(m['hue'], 120, 255, int(alpha * 0.5 * depth_fade)))
            grad.setColorAt(1, QColor(255, 255, 255, int(alpha * depth_fade)))
            painter.setPen(QPen(QBrush(grad), max(1, 2 * depth_fade)))
            painter.drawLine(int(tsx), int(tsy), int(sx), int(sy))
            painter.setPen(Qt.PenStyle.NoPen)

    def _paint_fluid(self, painter, w, h):
        bars = self._smooth_bars
        bass = float(np.mean(bars[:8]))
        mid = float(np.mean(bars[8:30]))
        high = float(np.mean(bars[30:]))
        cx, cy = w / 2, h / 2
        phase = self._fluid_phase
        hue = self._fluid_hue

        if self._fluid_buf is None or self._fluid_buf_w != w or self._fluid_buf_h != h:
            self._fluid_buf = QImage(w, h, QImage.Format.Format_ARGB32)
            self._fluid_buf.fill(QColor(0, 0, 0, 0))
            self._fluid_buf_w = w
            self._fluid_buf_h = h

        fade_painter = QPainter(self._fluid_buf)
        fade_painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        fade_alpha = max(8, min(40, int(12 + (bass + mid) * 15)))
        fade_painter.fillRect(0, 0, w, h, QColor(0, 0, 0, fade_alpha))
        fade_painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        fade_painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        n = len(bars)
        for i in range(n):
            val = bars[i]
            if val < 0.02:
                continue
            angle = phase + i * 0.15 + math.sin(phase * 0.7 + i * 0.05) * 2
            x3d = math.cos(angle) * (0.5 + val * 2.0) * 0.3
            y3d = math.sin(phase * 0.3 + i * 0.1) * val * 0.5
            z3d = math.sin(angle) * (0.5 + val * 2.0) * 0.3
            pitch = 0.45
            proj = lambda x, y, z: _project_3d(x, y, z, w, h, pitch=pitch)
            sx, sy, d, sc = proj(x3d, y3d, z3d)
            if not (-30 <= sx <= w + 30 and -30 <= sy <= h + 30):
                continue
            depth_fade = max(0.3, min(1.0, sc * 0.4))
            size = max(2, (3 + val * 15) * depth_fade)
            bar_hue = int(hue + i * 2.8) % 360
            alpha = int(val * 200 * depth_fade)
            grad = QRadialGradient(sx - size * 0.15, sy - size * 0.15, size * 1.5)
            grad.setColorAt(0, QColor(255, 255, 255, int(alpha * 0.4)))
            grad.setColorAt(0.3, QColor.fromHsv(bar_hue, 180, 255, alpha))
            grad.setColorAt(0.7, QColor.fromHsv(bar_hue, 200, 220, int(alpha * 0.4)))
            grad.setColorAt(1, QColor.fromHsv(bar_hue, 220, 180, 0))
            fade_painter.setPen(Qt.PenStyle.NoPen)
            fade_painter.setBrush(QBrush(grad))
            fade_painter.drawEllipse(QRectF(sx - size * 1.5, sy - size * 1.5, size * 3, size * 3))

        for layer in range(3):
            prev = None
            for xi in range(0, w + 12, 12):
                dist_from_center = abs(xi - cx) / (w / 2)
                depth_fade = max(0.3, 1.0 - dist_from_center * 0.5)
                wave = math.sin(xi * 0.006 + phase + layer * 1.2) * 40 * depth_fade * (1 + bass)
                wave += math.sin(xi * 0.013 + phase * 1.5 + layer * 0.8) * 15 * depth_fade * (1 + mid)
                y = h * (0.3 + layer * 0.15) + wave
                if prev is not None:
                    line_hue = int(hue + layer * 80 + xi * 0.1) % 360
                    alpha = int((40 + bass * 80) * depth_fade)
                    fade_painter.setPen(QPen(QColor.fromHsv(line_hue, 150, 255, alpha), (2 + bass * 3) * depth_fade))
                    fade_painter.drawLine(int(prev[0]), int(prev[1]), int(xi), int(y))
                prev = (xi, y)

        fade_painter.end()
        painter.drawImage(0, 0, self._fluid_buf)

    def _paint_ripple(self, painter, w, h):
        """粒子震荡洞洞波：光斑沿 X 轴匀速移动 + 节奏震荡粒子圆环 + 伞面效果 + 摄像机旋转"""
        bass = float(np.mean(self._smooth_bars[:8]))
        high = float(np.mean(self._smooth_bars[30:]))
        pitch = 0.42
        proj = lambda x, y, z: _project_3d(x, y, z, w, h, pitch=pitch)
        painter.setPen(Qt.PenStyle.NoPen)
        phase = self._ripple_phase
        base_hue = int(self._ripple_hue) % 360
        orb_x = self._ripple_orb_x
        # 摄像机绕 y 轴旋转（多角度观看光斑）
        cam_a = self._ripple_cam_angle
        cos_ca = math.cos(cam_a)
        sin_ca = math.sin(cam_a)

        # 1. 背景星空粒子（营造空间深度，高频驱动闪烁）
        for p in self._ripple_bg_particles:
            rx = p['x'] * cos_ca + p['z'] * sin_ca
            rz = -p['x'] * sin_ca + p['z'] * cos_ca
            sx, sy, depth, scale = proj(rx, p['y'], rz)
            if not (-20 <= sx <= w + 20 and -20 <= sy <= h + 20):
                continue
            brightness = 0.4 + 0.6 * (0.5 + 0.5 * math.sin(p['twinkle']))
            depth_fade = max(0.2, min(1.0, scale * 0.4))
            alpha = int(brightness * 170 * depth_fade * (1.0 + high * 0.5))
            alpha = min(255, alpha)
            screen_size = max(1, p['size'] * scale * 40)
            grad = QRadialGradient(sx, sy, screen_size * 2)
            grad.setColorAt(0, QColor(255, 255, 255, int(alpha * 0.8)))
            grad.setColorAt(0.3, QColor.fromHsv(p['hue'], 100, 255, alpha))
            grad.setColorAt(1, QColor.fromHsv(p['hue'], 150, 200, 0))
            painter.setBrush(QBrush(grad))
            painter.drawEllipse(QRectF(sx - screen_size * 2, sy - screen_size * 2, screen_size * 4, screen_size * 4))

        # 2. 路径粒子（光斑经过的路径留下的持续粒子轨迹线）
        for p in self._ripple_trail_particles:
            rel_x = p['x'] - orb_x
            rx = rel_x * cos_ca + p['z'] * sin_ca
            rz = -rel_x * sin_ca + p['z'] * cos_ca
            sx, sy, d, sc = proj(rx, p['y'], rz)
            if not (-40 <= sx <= w + 40 and -40 <= sy <= h + 40):
                continue
            depth_fade = max(0.1, min(1.0, sc * 0.5))
            life_ratio = p['age'] / p['max_age']
            life_fade = 1.0 - life_ratio * life_ratio
            size = max(0.6, (1.2 + high * 0.5) * depth_fade * p['size_factor'] * (0.4 + life_fade * 0.6))
            base_alpha = int(200 * life_fade * depth_fade)
            base_alpha = min(255, base_alpha)
            if base_alpha < 5:
                continue
            p_hue = p['hue']
            grad = QRadialGradient(sx, sy, size * 2)
            grad.setColorAt(0, QColor(255, 240, 200, min(255, int(base_alpha * 0.9))))
            grad.setColorAt(0.3, QColor.fromHsv(p_hue, 120, 255, base_alpha))
            grad.setColorAt(1, QColor.fromHsv(p_hue, 150, 200, 0))
            painter.setBrush(QBrush(grad))
            painter.drawEllipse(QRectF(sx - size * 2, sy - size * 2, size * 4, size * 4))

        # 3. 圆环粒子（主体）：光斑沿 X 轴移动时持续发射，粒子留在原地形成伞面
        # 摄像机跟随光斑并旋转，光斑在视角中心；过去的粒子在视角后方/侧方
        for p in self._ripple_ring_particles:
            rel_x = p['x'] - orb_x
            y3d = p['r'] * math.sin(p['angle'])
            z3d = p['r'] * math.cos(p['angle'])
            # 摄像机绕 y 轴旋转
            rx = rel_x * cos_ca + z3d * sin_ca
            rz = -rel_x * sin_ca + z3d * cos_ca
            sx, sy, d, sc = proj(rx, y3d, rz)
            if not (-40 <= sx <= w + 40 and -40 <= sy <= h + 40):
                continue
            depth_fade = max(0.1, min(1.0, sc * 0.5))
            life_ratio = p['age'] / p['max_age']
            life_fade = 1.0 - life_ratio * life_ratio
            size = max(0.8, (1.8 + high * 1.0) * depth_fade * p['size_factor'] * (0.5 + life_fade * 0.5))
            base_alpha = int(255 * life_fade * depth_fade)
            base_alpha = min(255, base_alpha)
            if base_alpha < 5:
                continue
            p_hue = p['hue']
            grad = QRadialGradient(sx, sy, size * 2.5)
            grad.setColorAt(0, QColor(255, 255, 255, min(255, int(base_alpha * 0.85))))
            grad.setColorAt(0.25, QColor.fromHsv(p_hue, 160, 255, base_alpha))
            grad.setColorAt(0.6, QColor.fromHsv(p_hue, 200, 220, int(base_alpha * 0.4)))
            grad.setColorAt(1, QColor.fromHsv(p_hue, 200, 200, 0))
            painter.setBrush(QBrush(grad))
            painter.drawEllipse(QRectF(sx - size * 2.5, sy - size * 2.5, size * 5, size * 5))

        # 4. 中心光斑（在视角中心，随节奏明暗变化 - 节奏越强亮度越高）
        core_sx, core_sy, _, core_sc = proj(0, 0, 0)
        core_r = max(5, 18 * core_sc)
        # 光芒线条（随节奏伸长）
        num_rays = 8
        ray_length = core_r * (2.5 + bass * 7)
        for i in range(num_rays):
            angle = i * 2 * math.pi / num_rays + phase * 0.3
            x2 = core_sx + math.cos(angle) * ray_length
            y2 = core_sy + math.sin(angle) * ray_length
            ray_alpha = int(60 + bass * 140)
            ray_grad = QLinearGradient(core_sx, core_sy, x2, y2)
            ray_grad.setColorAt(0, QColor(255, 255, 255, ray_alpha))
            ray_grad.setColorAt(0.3, QColor.fromHsv(base_hue, 120, 255, int(ray_alpha * 0.6)))
            ray_grad.setColorAt(1, QColor.fromHsv(base_hue, 150, 200, 0))
            painter.setPen(QPen(QBrush(ray_grad), max(1.0, 2 + bass * 3)))
            painter.drawLine(QPointF(core_sx, core_sy), QPointF(x2, y2))
        painter.setPen(Qt.PenStyle.NoPen)
        # 多层光晕（节奏越强亮度越高）
        brightness = 0.4 + bass * 0.6
        core_grad = QRadialGradient(core_sx, core_sy, core_r * 6)
        core_grad.setColorAt(0, QColor(255, 255, 255, int(min(255, 180 + bass * 75))))
        core_grad.setColorAt(0.05, QColor(220, 230, 255, int(min(255, 140 + bass * 100))))
        core_grad.setColorAt(0.2, QColor.fromHsv(base_hue, 140, 255, int((60 + bass * 100) * brightness)))
        core_grad.setColorAt(0.5, QColor.fromHsv(base_hue, 180, 200, int((20 + bass * 40) * brightness)))
        core_grad.setColorAt(1, QColor(20, 30, 80, 0))
        painter.setBrush(QBrush(core_grad))
        painter.drawEllipse(QRectF(core_sx - core_r * 6, core_sy - core_r * 6, core_r * 12, core_r * 12))


class AudioVisualService:
    def __init__(self, player_controller):
        self._pc = player_controller
        self._current_style = 'none'
        self._is_audio_only = False
        self._widget = None
        self._current_file = None

    @property
    def current_style(self):
        return self._current_style

    @property
    def is_audio_only(self):
        return self._is_audio_only

    def is_audio_file(self, url):
        if not url:
            return False
        path = url.split('?')[0].split('#')[0]
        return path.lower().endswith(AUDIO_EXTENSIONS)

    def prepare_before_loadfile(self, url):
        if not self.is_audio_file(url):
            self._is_audio_only = False
            self._hide_widget()
            self._current_style = 'none'
            self._current_file = None
            return
        self._is_audio_only = True
        self._current_file = url

    def auto_enable_if_audio(self):
        from core.log_manager import global_logger as _log
        if self.detect_audio_only():
            if self._current_style == 'none':
                saved = self._load_saved_style()
                if saved and saved != 'none':
                    self._current_style = saved
                else:
                    self._current_style = random.choice(STYLE_KEYS)
            _log.info(f"音频可视化自动启用: style={self._current_style}, file={self._current_file}")
            self._show_widget()
            self._auto_show_lyrics()
            return True
        else:
            if self._current_style != 'none':
                self._hide_widget()
            self._auto_hide_lyrics()
            return False

    def detect_audio_only(self):
        if not self._pc or not self._pc.is_playing:
            self._is_audio_only = False
            return False
        try:
            track_list_str = self._pc._get_mpv_property_string('track-list') or ''
            has_real_video = False
            has_audio = False
            if track_list_str:
                import json
                try:
                    tracks = json.loads(track_list_str)
                    for t in tracks:
                        if t.get('type') == 'video':
                            if not t.get('albumart', False):
                                has_real_video = True
                        elif t.get('type') == 'audio':
                            has_audio = True
                except Exception:
                    pass
            is_audio = has_audio and not has_real_video
            self._is_audio_only = is_audio
            return is_audio
        except Exception:
            self._is_audio_only = False
            return False

    def apply_visual_style(self, style_key):
        if style_key not in AUDIO_VISUAL_STYLES:
            return False
        self._current_style = style_key
        if style_key == 'none':
            self._hide_widget()
        else:
            self._show_widget()
        self.save_current_style()
        return True

    def clear_visual(self):
        self._hide_widget()
        self._current_style = 'none'
        self._auto_hide_lyrics()

    def _raise_lyrics_above(self):
        try:
            w = self._get_main_window()
            if w and hasattr(w, '_lyrics_widget') and w._lyrics_widget and w._lyrics_widget.isVisible():
                w._lyrics_widget.raise_()
        except Exception:
            pass

    def _auto_show_lyrics(self):
        try:
            from services.audio_visual_service import extract_lyrics
            lyrics = extract_lyrics(self._current_file) if self._current_file else None
            if not lyrics:
                return
            w = self._get_main_window()
            if not w:
                return
            if not hasattr(w, '_lyrics_widget') or not w._lyrics_widget:
                from ui.lyrics_widget import LyricsWidget
                w._lyrics_widget = LyricsWidget(w.video_frame)
            vf = w.video_frame
            if vf:
                w._lyrics_widget.setGeometry(0, 0, vf.width(), vf.height())
            w._lyrics_widget.set_lyrics(lyrics, is_lrc='[' in lyrics)
            w._lyrics_widget.show()
            w._lyrics_widget.raise_()
            w._lyrics_widget.start()
        except Exception:
            pass

    def _auto_hide_lyrics(self):
        try:
            w = self._get_main_window()
            if w and hasattr(w, '_lyrics_widget') and w._lyrics_widget:
                w._lyrics_widget.stop()
                w._lyrics_widget.hide()
        except Exception:
            pass

    def _get_main_window(self):
        if self._widget and self._widget.parent():
            p = self._widget.parent()
            while p:
                if hasattr(p, 'player_controller'):
                    return p
                p = p.parent()
        return None

    def apply_random_style(self):
        self._current_style = 'random'
        self._show_widget()
        self.save_current_style()
        return True

    def _show_widget(self):
        if not self._widget:
            return
        self._widget.set_style(self._current_style)
        parent = self._widget.parent()
        if parent:
            self._widget.setGeometry(0, 0, parent.width(), parent.height())
        if self._pc and hasattr(self._pc, 'video_widget'):
            self._pc.video_widget.hide()
        self._widget.start(self._current_file)
        self._raise_lyrics_above()

    def _hide_widget(self):
        if self._widget:
            self._widget.stop()
        if self._pc and hasattr(self._pc, 'video_widget'):
            self._pc.video_widget.show()

    def resize_widget(self):
        if self._widget and self._widget.isVisible():
            parent = self._widget.parent()
            if parent:
                self._widget.setGeometry(0, 0, parent.width(), parent.height())

    def _load_saved_style(self):
        try:
            from core.config_manager import ConfigManager
            config = ConfigManager()
            return config.get_value('Player', 'audio_visual_style', 'none') or 'none'
        except Exception:
            return 'none'

    def save_current_style(self):
        try:
            from core.config_manager import ConfigManager
            config = ConfigManager()
            config.set_value('Player', 'audio_visual_style', self._current_style)
            config.save_config()
        except Exception:
            pass

    def get_style_display_name(self, style_key, language_manager=None):
        style = AUDIO_VISUAL_STYLES.get(style_key)
        if not style:
            return style_key
        if language_manager:
            return language_manager.tr(style['name_key'], style['name_default'])
        return style['name_default']

    def get_all_styles(self):
        return AUDIO_VISUAL_STYLES


def extract_cover_art(file_path):
    try:
        import mutagen
        audio = mutagen.File(file_path)  # type: ignore[reportPrivateImportUsage]
        if audio is None:
            return None
        if hasattr(audio, 'tags') and audio.tags:
            for tag in audio.tags.values():
                if hasattr(tag, 'data') and hasattr(tag, 'mime_type'):
                    if tag.mime_type and tag.mime_type.startswith('image/'):
                        from PySide6.QtGui import QImage, QPixmap
                        img = QImage()
                        if img.loadFromData(tag.data):
                            return QPixmap.fromImage(img)
        if hasattr(audio, 'pictures'):
            for pic in audio.pictures:
                if pic.data and pic.mime and pic.mime.startswith('image/'):
                    from PySide6.QtGui import QImage, QPixmap
                    img = QImage()
                    if img.loadFromData(pic.data):
                        return QPixmap.fromImage(img)
    except Exception:
        pass
    return None


def extract_lyrics(file_path):
    try:
        import mutagen
        audio = mutagen.File(file_path)  # type: ignore[reportPrivateImportUsage]
        if audio is None:
            return None
        if hasattr(audio, 'tags') and audio.tags:
            for key in ('USLT', 'SYLT', 'lyrics:eng', 'lyrics', 'LYRICS', 'unsyncedlyrics'):
                if key in audio.tags:
                    val = audio.tags[key]
                    if hasattr(val, 'text'):
                        for t in val.text:
                            if isinstance(t, str) and t.strip():
                                return t.strip()
                    elif isinstance(val, list):
                        for item in val:
                            if hasattr(item, 'text'):
                                for t in item.text:
                                    if isinstance(t, str) and t.strip():
                                        return t.strip()
                            elif isinstance(item, str) and item.strip():
                                return item.strip()
        if hasattr(audio, 'get'):
            for key in ('lyrics', 'LYRICS', 'synctext'):
                val = audio.get(key)
                if val:
                    if isinstance(val, str):
                        return val.strip()
                    if isinstance(val, list):
                        for item in val:
                            text = str(item).strip()
                            if text:
                                return text
    except Exception:
        pass
    return None
