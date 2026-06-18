import math
import random
import subprocess
import threading
import time
import os

from collections import deque

import numpy as np
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import QTimer, Qt, QRectF
from PySide6.QtGui import (QPainter, QColor, QLinearGradient, QRadialGradient,
                            QPen, QBrush, QFont, QPixmap, QImage)

AUDIO_EXTENSIONS = ('.mp3', '.flac', '.wav', '.aac', '.ogg', '.opus', '.wma', '.m4a',
                    '.ape', '.alac', '.wv', '.tta', '.dts', '.ac3', '.mid', '.midi')

AUDIO_VISUAL_STYLES = {
    'spectrum': {
        'name_key': 'audio_vis_spectrum',
        'name_default': '频谱',
    },
    'mirror_bars': {
        'name_key': 'audio_vis_mirror_bars',
        'name_default': '镜像柱状',
    },
    'circular': {
        'name_key': 'audio_vis_circular',
        'name_default': '环形频谱',
    },
    'waves': {
        'name_key': 'audio_vis_waves',
        'name_default': '波形',
    },
    'vector_scope': {
        'name_key': 'audio_vis_vectorscope',
        'name_default': '矢量示波器',
    },
    'particles': {
        'name_key': 'audio_vis_particles',
        'name_default': '粒子脉冲',
    },
    'mountain': {
        'name_key': 'audio_vis_mountain',
        'name_default': '山脉频谱',
    },
    'spectrogram': {
        'name_key': 'audio_vis_spectrogram',
        'name_default': '瀑布流',
    },
    'aurora': {
        'name_key': 'audio_vis_aurora',
        'name_default': '极光',
    },
    'starfield': {
        'name_key': 'audio_vis_starfield',
        'name_default': '星场',
    },
    'cosmos': {
        'name_key': 'audio_vis_cosmos',
        'name_default': '宇宙',
    },
    'warp': {
        'name_key': 'audio_vis_warp',
        'name_default': '曲速',
    },
    'fluid': {
        'name_key': 'audio_vis_fluid',
        'name_default': '流体',
    },
    'milkdrop': {
        'name_key': 'audio_vis_milkdrop',
        'name_default': '经典',
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
NUM_BARS = 128


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
    bar_freqs = np.logspace(np.log10(min_freq), np.log10(max_freq), num_bars + 1)
    bars = np.zeros(num_bars)
    for i in range(num_bars):
        mask = (freqs >= bar_freqs[i]) & (freqs < bar_freqs[i + 1])
        if np.any(mask):
            bars[i] = np.mean(magnitudes[mask])
    ref = np.percentile(magnitudes, 85) * 2.5
    if ref > 0:
        bars = bars / ref
    return np.clip(bars, 0, 1)


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
        self._scope_trail = deque(maxlen=400)
        self._particles = []
        self._dust = []
        self._cover_pixmap = None
        self._frame_count = 0
        self._spectrogram_history = deque(maxlen=120)
        self._star_stars = []
        self._aurora_phase = 0.0
        self._cosmos_bg_stars = []
        self._cosmos_particles = []
        self._cosmos_meteors = []
        self._cosmos_rotation = 0.0
        self._warp_streaks = []
        self._warp_rings = []
        self._warp_sparks = []
        self._warp_prev_bass = 0.0
        self._fluid_hue = 0.0
        self._fluid_phase = 0.0
        self._fluid_buf = None
        self._fluid_buf_w = 0
        self._fluid_buf_h = 0
        self._milk_hue = 0.0
        self._milk_phase = 0.0
        self._milk_rot = 0.0
        self._milk_zoom = 1.0
        self._milk_buf = None
        self._milk_buf_w = 0
        self._milk_buf_h = 0
        self._bar_colors = [QColor.fromHsv(int(200 + i * 160 / NUM_BARS) % 360, 230, 255) for i in range(NUM_BARS)]
        self._bar_colors_dim = [QColor.fromHsv(int(200 + i * 160 / NUM_BARS) % 360, 180, 80) for i in range(NUM_BARS)]
        self._bar_colors_peak = [QColor.fromHsv(int(200 + i * 160 / NUM_BARS) % 360, 160, 255) for i in range(NUM_BARS)]
        self._bloom_img = None
        self._bloom_w = 0
        self._bloom_h = 0
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
        if style_key == 'particles':
            self._particles = []
            self._dust = []
        elif style_key == 'starfield':
            self._star_stars = []
        elif style_key == 'spectrogram':
            self._spectrogram_history.clear()
        elif style_key == 'cosmos':
            self._cosmos_bg_stars = []
            self._cosmos_particles = []
            self._cosmos_meteors = []
        elif style_key == 'warp':
            self._warp_streaks = []
            self._warp_rings = []
            self._warp_sparks = []
        elif style_key == 'fluid':
            self._fluid_buf = None
        elif style_key == 'milkdrop':
            self._milk_buf = None
        self._scope_trail.clear()
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
        needs_bars = self._style in ('spectrum', 'mirror_bars', 'circular', 'mountain', 'particles', 'spectrogram', 'aurora', 'starfield', 'cosmos', 'warp', 'fluid', 'milkdrop')
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
        if self._style == 'vector_scope':
            left, right = self._pcm.get_stereo_samples(512)
            if len(left) > 0 and len(right) > 0:
                step = max(1, len(left) // 80)
                for j in range(0, len(left), step):
                    self._scope_trail.append((float(left[j]), float(right[j])))
        if self._style == 'spectrogram':
            self._spectrogram_history.append(self._smooth_bars.copy())
        if self._style == 'aurora':
            self._aurora_phase += 0.02 + float(np.mean(self._bars[:8])) * 0.05
        if self._style == 'starfield':
            self._update_starfield()
        if self._style == 'cosmos':
            self._update_cosmos()
        if self._style == 'particles':
            self._update_particles()
        if self._style == 'spectrum':
            self._update_dust()
        if self._style == 'warp':
            self._update_warp()
        if self._style == 'fluid':
            self._update_fluid()
        if self._style == 'milkdrop':
            self._update_milkdrop()

    def _update_starfield(self):
        w = self.width()
        h = self.height()
        if w <= 0 or h <= 0:
            return
        bass = float(np.mean(self._bars[:8]))
        mid = float(np.mean(self._bars[8:30]))
        speed = 0.5 + bass * 8 + mid * 3
        if len(self._star_stars) < 300 and self._frame_count % 2 == 0:
            for _ in range(max(1, int(bass * 5))):
                self._star_stars.append({
                    'x': random.uniform(-1, 1),
                    'y': random.uniform(-1, 1),
                    'z': random.uniform(0.01, 1.0),
                    'hue': random.randint(180, 300),
                })
        alive = []
        for s in self._star_stars:
            s['z'] -= speed * 0.005
            if s['z'] > 0.005:
                alive.append(s)
        self._star_stars = alive[-600:]

    def _update_particles(self):
        w = self.width()
        h = self.height()
        if w <= 0 or h <= 0:
            return
        bass = float(np.mean(self._bars[:8]))
        mid = float(np.mean(self._bars[8:30]))
        high = float(np.mean(self._bars[30:]))
        cx, cy = w / 2, h / 2
        energy = bass + mid + high
        if energy > 0.2:
            count = int(energy * 8) + 2
            for _ in range(count):
                angle = random.uniform(0, 2 * math.pi)
                speed = 1.0 + bass * 8 + mid * 3
                dist = random.uniform(0, min(w, h) * 0.15)
                hue = random.randint(140, 340)
                self._particles.append({
                    'x': cx + math.cos(angle) * dist,
                    'y': cy + math.sin(angle) * dist,
                    'vx': math.cos(angle) * speed,
                    'vy': math.sin(angle) * speed,
                    'life': 1.0,
                    'size': 1.5 + bass * 5 + random.random() * 2,
                    'hue': hue,
                    'type': 'burst',
                })
        if self._frame_count % 3 == 0 and len(self._particles) < 2000:
            for _ in range(3):
                self._particles.append({
                    'x': random.uniform(0, w),
                    'y': random.uniform(0, h),
                    'vx': random.uniform(-0.3, 0.3),
                    'vy': random.uniform(-0.5, -0.1),
                    'life': random.uniform(0.5, 1.0),
                    'size': random.uniform(0.5, 2),
                    'hue': random.randint(180, 260),
                    'type': 'dust',
                })
        alive = []
        for p in self._particles:
            p['x'] += p['vx']
            p['y'] += p['vy']
            if p['type'] == 'burst':
                p['vx'] *= 0.99
                p['vy'] *= 0.99
                p['life'] -= 0.012
            else:
                p['life'] -= 0.005
            if p['life'] > 0 and -50 <= p['x'] <= w + 50 and -50 <= p['y'] <= h + 50:
                alive.append(p)
        self._particles = alive[-2000:]

    def _update_dust(self):
        w = self.width()
        h = self.height()
        if w <= 0 or h <= 0:
            return
        if self._frame_count % 4 == 0 and len(self._dust) < 80:
            self._dust.append({
                'x': random.uniform(0, w),
                'y': random.uniform(0, h),
                'vx': random.uniform(-0.2, 0.2),
                'vy': random.uniform(-0.3, 0.1),
                'life': 1.0,
                'size': random.uniform(0.5, 1.5),
            })
        alive = []
        for d in self._dust:
            d['x'] += d['vx']
            d['y'] += d['vy']
            d['life'] -= 0.003
            if d['life'] > 0 and 0 <= d['x'] <= w and 0 <= d['y'] <= h:
                alive.append(d)
        self._dust = alive

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
        if len(self._cosmos_bg_stars) < 400:
            for _ in range(5):
                self._cosmos_bg_stars.append({
                    'x': random.uniform(0, w),
                    'y': random.uniform(0, h),
                    'size': random.uniform(0.3, 1.5),
                    'twinkle': random.uniform(0, math.pi * 2),
                    'speed': random.uniform(0.02, 0.06),
                })
        for s in self._cosmos_bg_stars:
            s['twinkle'] += s['speed']
        energy = bass + mid + high
        if energy > 0.15:
            count = int(energy * 10) + 3
            for _ in range(count):
                angle = random.uniform(0, 2 * math.pi)
                speed = 0.8 + bass * 10 + mid * 4
                dist = random.uniform(0, min(w, h) * 0.08)
                hue = random.randint(160, 320)
                self._cosmos_particles.append({
                    'x': cx + math.cos(angle) * dist,
                    'y': cy + math.sin(angle) * dist,
                    'vx': math.cos(angle) * speed,
                    'vy': math.sin(angle) * speed,
                    'life': 1.0,
                    'size': 1 + bass * 4 + random.random() * 2,
                    'hue': hue,
                })
        alive = []
        for p in self._cosmos_particles:
            p['x'] += p['vx']
            p['y'] += p['vy']
            p['vx'] *= 0.995
            p['vy'] *= 0.995
            p['life'] -= 0.008
            if p['life'] > 0 and -100 <= p['x'] <= w + 100 and -100 <= p['y'] <= h + 100:
                alive.append(p)
        self._cosmos_particles = alive[-3000:]
        if random.random() < 0.02 + bass * 0.15:
            side = random.randint(0, 3)
            if side == 0:
                mx, my = random.uniform(0, w), 0
            elif side == 1:
                mx, my = w, random.uniform(0, h)
            elif side == 2:
                mx, my = random.uniform(0, w), h
            else:
                mx, my = 0, random.uniform(0, h)
            tx = cx + random.uniform(-w * 0.3, w * 0.3)
            ty = cy + random.uniform(-h * 0.3, h * 0.3)
            dx, dy = tx - mx, ty - my
            dist = math.sqrt(dx * dx + dy * dy) + 1
            speed = 4 + bass * 8
            self._cosmos_meteors.append({
                'x': mx, 'y': my,
                'vx': dx / dist * speed,
                'vy': dy / dist * speed,
                'life': 1.0,
                'len': 30 + bass * 40,
                'hue': random.randint(30, 60),
            })
        m_alive = []
        for m in self._cosmos_meteors:
            m['x'] += m['vx']
            m['y'] += m['vy']
            m['life'] -= 0.02
            if m['life'] > 0 and -50 <= m['x'] <= w + 50 and -50 <= m['y'] <= h + 50:
                m_alive.append(m)
        self._cosmos_meteors = m_alive[-30:]

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
            'mirror_bars': self._paint_mirror_bars,
            'circular': self._paint_circular,
            'waves': self._paint_waves,
            'vector_scope': self._paint_scope,
            'particles': self._paint_particles,
            'mountain': self._paint_mountain,
            'spectrogram': self._paint_spectrogram,
            'aurora': self._paint_aurora,
            'starfield': self._paint_starfield,
            'cosmos': self._paint_cosmos,
            'warp': self._paint_warp,
            'fluid': self._paint_fluid,
            'milkdrop': self._paint_milkdrop,
        }
        paint_fn = style_map.get(self._style, self._paint_spectrum)
        painter.setOpacity(self._fade_alpha)
        paint_fn(painter, w, h)


        painter.end()

    def _paint_bloom(self, painter, w, h):
        if self._bloom_w != w or self._bloom_h != h or self._bloom_img is None:
            self._bloom_img = QImage(w // 4, h // 4, QImage.Format.Format_ARGB32)
            self._bloom_w = w
            self._bloom_h = h
        bw = self._bloom_img.width()
        bh = self._bloom_img.height()
        small_painter = QPainter(self._bloom_img)
        small_painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        small_painter.scale(bw / w, bh / h)
        style_map = {
            'spectrum': self._paint_spectrum,
            'mirror_bars': self._paint_mirror_bars,
            'circular': self._paint_circular,
            'mountain': self._paint_mountain,
            'cosmos': self._paint_cosmos,
            'warp': self._paint_warp,
        }
        paint_fn = style_map.get(self._style)
        if paint_fn:
            small_painter.fillRect(0, 0, w, h, QColor(0, 0, 0, 0))
            paint_fn(small_painter, w, h)
        small_painter.end()
        painter.setOpacity(0.25)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.drawImage(QRectF(-8, -8, w + 16, h + 16), self._bloom_img)
        painter.setOpacity(1.0)

    def _paint_spectrum(self, painter, w, h):
        bars = self._smooth_bars
        peaks = self._peak_bars
        n = len(bars)
        bass = float(np.mean(bars[:8]))
        if bass > 0.1:
            painter.setPen(Qt.PenStyle.NoPen)
            grad = QRadialGradient(w / 2, h, h * 0.6)
            grad.setColorAt(0, QColor(30, 60, 150, int(bass * 40)))
            grad.setColorAt(1, QColor(5, 5, 10, 0))
            painter.setBrush(QBrush(grad))
            painter.drawRect(QRectF(0, 0, w, h))
        painter.setPen(Qt.PenStyle.NoPen)
        for d in self._dust:
            alpha = int(d['life'] * 60)
            painter.setBrush(QColor(150, 200, 255, alpha))
            painter.drawEllipse(QRectF(d['x'] - d['size'], d['y'] - d['size'], d['size'] * 2, d['size'] * 2))
        margin = 8
        total_w = w - margin * 2
        bar_w = max(1, total_w / n - 1)
        gap = 1
        painter.setPen(Qt.PenStyle.NoPen)
        for i in range(n):
            val = bars[i]
            bar_h = val * h * 0.88
            x = margin + i * (bar_w + gap)
            y = h - bar_h
            painter.setBrush(self._bar_colors[i])
            painter.drawRect(QRectF(x, y, bar_w, bar_h))
            painter.setBrush(self._bar_colors_dim[i])
            painter.drawRect(QRectF(x, y, bar_w, max(1, bar_h * 0.15)))
            peak_val = peaks[i]
            if peak_val > 0.02:
                peak_y = h - peak_val * h * 0.88
                painter.setBrush(self._bar_colors_peak[i])
                painter.drawRect(QRectF(x, peak_y - 2, bar_w, 2))
        reflect_h = h * 0.15
        grad = QLinearGradient(0, h, 0, h + reflect_h)
        grad.setColorAt(0, QColor(80, 150, 255, 30))
        grad.setColorAt(1, QColor(0, 0, 0, 0))
        painter.setBrush(QBrush(grad))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(QRectF(0, h, w, reflect_h))

    def _paint_mirror_bars(self, painter, w, h):
        bars = self._smooth_bars
        n = len(bars)
        margin = 6
        total_w = w - margin * 2
        bar_w = max(1, total_w / n - 1)
        gap = 1
        cy = h / 2
        max_h = cy * 0.92
        painter.setPen(Qt.PenStyle.NoPen)
        for i in range(n):
            val = bars[i]
            bar_h = val * max_h
            x = margin + i * (bar_w + gap)
            painter.setBrush(self._bar_colors[i])
            painter.drawRect(QRectF(x, cy - bar_h, bar_w, bar_h))
            dim = QColor(self._bar_colors[i])
            dim.setAlpha(120)
            painter.setBrush(dim)
            painter.drawRect(QRectF(x, cy, bar_w, bar_h))
        painter.setPen(QPen(QColor(100, 200, 255, 60), 1))
        painter.drawLine(0, int(cy), w, int(cy))

    def _paint_circular(self, painter, w, h):
        bars = self._smooth_bars
        n = len(bars)
        cx, cy = w / 2, h / 2
        radius = min(w, h) * 0.2
        max_bar = min(w, h) * 0.28
        for i in range(n):
            val = bars[i]
            angle = i * 360.0 / n - 90
            rad = math.radians(angle)
            x1 = cx + radius * math.cos(rad)
            y1 = cy + radius * math.sin(rad)
            bar_len = val * max_bar
            x2 = cx + (radius + bar_len) * math.cos(rad)
            y2 = cy + (radius + bar_len) * math.sin(rad)
            painter.setPen(QPen(self._bar_colors[i], max(2, 360 / n * 0.5)))
            painter.drawLine(int(x1), int(y1), int(x2), int(y2))
        painter.setPen(Qt.PenStyle.NoPen)
        grad = QRadialGradient(cx, cy, radius)
        grad.setColorAt(0, QColor(10, 10, 25, 230))
        grad.setColorAt(1, QColor(5, 5, 15, 100))
        painter.setBrush(QBrush(grad))
        painter.drawEllipse(QRectF(cx - radius, cy - radius, radius * 2, radius * 2))
        bass = float(np.mean(bars[:8]))
        if bass > 0.15:
            pulse_r = radius * (1 + bass * 0.12)
            painter.setPen(QPen(QColor(100, 180, 255, int(bass * 100)), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QRectF(cx - pulse_r, cy - pulse_r, pulse_r * 2, pulse_r * 2))

    def _paint_waves(self, painter, w, h):
        n = len(self._wave_left)
        cy = h / 2
        from PySide6.QtCore import QPointF
        for ch_idx, (wave_data, base_alpha, width) in enumerate([
            (self._wave_left, 220, 3.0), (self._wave_right, 140, 2.0)
        ]):
            grad = QLinearGradient(0, 0, w, 0)
            if ch_idx == 0:
                grad.setColorAt(0, QColor(0, 180, 255, base_alpha))
                grad.setColorAt(0.5, QColor(80, 255, 200, base_alpha))
                grad.setColorAt(1, QColor(200, 100, 255, base_alpha))
            else:
                grad.setColorAt(0, QColor(255, 80, 200, base_alpha))
                grad.setColorAt(0.5, QColor(255, 200, 80, base_alpha))
                grad.setColorAt(1, QColor(80, 200, 255, base_alpha))
            painter.setPen(QPen(QBrush(grad), width))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            from PySide6.QtGui import QPolygonF
            points = QPolygonF()
            for i in range(n):
                x = i * w / (n - 1)
                y = cy + wave_data[i] * h * 0.42
                points.append(QPointF(x, y))
            if points.size() > 1:
                painter.drawPolyline(points)
            if ch_idx == 0:
                fill_pts = QPolygonF()
                fill_pts.append(QPointF(0, cy))
                for i in range(n):
                    x = i * w / (n - 1)
                    y = cy + wave_data[i] * h * 0.42
                    fill_pts.append(QPointF(x, y))
                fill_pts.append(QPointF(w, cy))
                painter.setPen(Qt.PenStyle.NoPen)
                fill_grad = QLinearGradient(0, cy - h * 0.4, 0, cy + h * 0.4)
                fill_grad.setColorAt(0, QColor(0, 150, 255, 25))
                fill_grad.setColorAt(0.5, QColor(0, 200, 255, 10))
                fill_grad.setColorAt(1, QColor(0, 150, 255, 25))
                painter.setBrush(QBrush(fill_grad))
                painter.drawPolygon(fill_pts)

    def _paint_scope(self, painter, w, h):
        cx, cy = w / 2, h / 2
        radius = min(w, h) * 0.4
        painter.setPen(QPen(QColor(30, 30, 45), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QRectF(cx - radius, cy - radius, radius * 2, radius * 2))
        painter.drawLine(int(cx - radius), int(cy), int(cx + radius), int(cy))
        painter.drawLine(int(cx), int(cy - radius), int(cx), int(cy + radius))
        trail = list(self._scope_trail)
        n = len(trail)
        if n < 2:
            return
        for i in range(1, n):
            alpha = int(20 + 235 * i / n)
            lx, ly = trail[i - 1]
            rx, ry = trail[i]
            x1 = cx + lx * radius
            y1 = cy - ly * radius
            x2 = cx + rx * radius
            y2 = cy - ry * radius
            hue = (int(time.time() * 60) + i * 3) % 360
            width = 1.0 + 2.0 * i / n
            painter.setPen(QPen(QColor.fromHsv(hue, 230, 255, alpha), width))
            painter.drawLine(int(x1), int(y1), int(x2), int(y2))
        last = trail[-1]
        px = cx + last[0] * radius
        py = cy - last[1] * radius
        painter.setPen(Qt.PenStyle.NoPen)
        grad = QRadialGradient(px, py, 14)
        grad.setColorAt(0, QColor(255, 255, 255, 240))
        grad.setColorAt(0.4, QColor(100, 200, 255, 120))
        grad.setColorAt(1, QColor(0, 100, 255, 0))
        painter.setBrush(QBrush(grad))
        painter.drawEllipse(QRectF(px - 14, py - 14, 28, 28))

    def _paint_particles(self, painter, w, h):
        bars = self._smooth_bars
        bass = float(np.mean(bars[:8]))
        mid = float(np.mean(bars[8:30]))
        cx, cy = w / 2, h / 2
        painter.setPen(Qt.PenStyle.NoPen)
        for i in range(3):
            r = min(w, h) * (0.15 + i * 0.08)
            pulse = r + bass * min(w, h) * 0.03 * (3 - i)
            alpha = int(20 + bass * 40 - i * 8)
            painter.setPen(QPen(QColor(80, 160, 255, max(5, alpha)), 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QRectF(cx - pulse, cy - pulse, pulse * 2, pulse * 2))
        painter.setPen(Qt.PenStyle.NoPen)
        for p in self._particles:
            alpha = int(p['life'] * 220)
            size = p['size'] * (0.3 + p['life'] * 0.7)
            if p['type'] == 'dust':
                painter.setBrush(QColor(120, 180, 255, int(alpha * 0.3)))
                painter.drawEllipse(QRectF(p['x'] - size, p['y'] - size, size * 2, size * 2))
            else:
                painter.setBrush(QColor.fromHsv(p['hue'], 200, 255, alpha))
                painter.drawEllipse(QRectF(p['x'] - size, p['y'] - size, size * 2, size * 2))
        inner_r = min(w, h) * 0.12
        for i in range(len(bars)):
            val = bars[i]
            if val < 0.03:
                continue
            angle = i * 2 * math.pi / len(bars)
            x1 = cx + inner_r * math.cos(angle)
            y1 = cy + inner_r * math.sin(angle)
            bar_len = val * min(w, h) * 0.35
            x2 = cx + (inner_r + bar_len) * math.cos(angle)
            y2 = cy + (inner_r + bar_len) * math.sin(angle)
            painter.setPen(QPen(self._bar_colors[i % len(self._bar_colors)], 2))
            painter.drawLine(int(x1), int(y1), int(x2), int(y2))

    def _paint_mountain(self, painter, w, h):
        bars = self._smooth_bars
        n = len(bars)
        from PySide6.QtGui import QPolygonF
        from PySide6.QtCore import QPointF
        for layer, (y_scale, color_top, color_mid, color_bot) in enumerate([
            (0.6, QColor(40, 80, 160, 60), QColor(20, 40, 100, 40), QColor(5, 15, 50, 20)),
            (0.75, QColor(60, 140, 220, 120), QColor(30, 80, 160, 80), QColor(10, 30, 80, 40)),
            (0.9, QColor(100, 220, 255, 200), QColor(50, 140, 220, 140), QColor(20, 60, 120, 60)),
        ]):
            points = QPolygonF()
            points.append(QPointF(0, h))
            for i in range(n):
                x = i * w / (n - 1)
                y = h - bars[i] * h * y_scale
                points.append(QPointF(x, y))
            points.append(QPointF(w, h))
            grad = QLinearGradient(0, 0, 0, h)
            grad.setColorAt(0, color_top)
            grad.setColorAt(0.4, color_mid)
            grad.setColorAt(1, color_bot)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(grad))
            painter.drawPolygon(points)
        painter.setPen(QPen(QColor(140, 230, 255, 180), 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        line_pts = QPolygonF()
        for i in range(n):
            x = i * w / (n - 1)
            y = h - bars[i] * h * 0.9
            line_pts.append(QPointF(x, y))
        if line_pts.size() > 1:
            painter.drawPolyline(line_pts)

    def _paint_spectrogram(self, painter, w, h):
        history = list(self._spectrogram_history)
        n = len(history)
        if n == 0:
            return
        row_h = max(1, h / n)
        num_bars = len(history[0]) if n > 0 else NUM_BARS
        col_w = max(1, w / num_bars)
        painter.setPen(Qt.PenStyle.NoPen)
        for row_idx, frame in enumerate(history):
            y = h - (row_idx + 1) * row_h
            age = 1.0 - row_idx / max(n, 1)
            for bar_idx in range(len(frame)):
                val = frame[bar_idx]
                if val < 0.01:
                    continue
                x = bar_idx * col_w
                r = int(val * 80 * age)
                g = int(val * 200 * age)
                b = int((0.3 + val * 0.7) * 255 * age)
                painter.setBrush(QColor(r, g, b, int(val * 255 * age)))
                painter.drawRect(QRectF(x, y, col_w + 1, row_h + 1))
        grad = QLinearGradient(0, 0, 0, h * 0.15)
        grad.setColorAt(0, QColor(5, 5, 10, 200))
        grad.setColorAt(1, QColor(5, 5, 10, 0))
        painter.setBrush(QBrush(grad))
        painter.drawRect(QRectF(0, 0, w, h * 0.15))

    def _paint_aurora(self, painter, w, h):
        bars = self._smooth_bars
        bass = float(np.mean(bars[:8]))
        mid = float(np.mean(bars[8:30]))
        from PySide6.QtGui import QPolygonF
        from PySide6.QtCore import QPointF
        for layer in range(4):
            phase = self._aurora_phase + layer * 0.8
            y_base = h * (0.25 + layer * 0.1)
            amplitude = h * (0.06 + bass * 0.10 + mid * 0.06)
            hue_base = int(120 + layer * 50 + math.sin(phase * 0.3) * 25) % 360
            for strip in range(4):
                strip_phase = phase + strip * 0.5
                band_half = 25 + strip * 12 + bass * 15
                points_top = QPolygonF()
                points_bot = QPolygonF()
                for x in range(0, w + 12, 12):
                    wave = math.sin(x * 0.004 + strip_phase) * amplitude
                    wave += math.sin(x * 0.009 + strip_phase * 1.4) * amplitude * 0.35
                    wave += math.sin(x * 0.002 + strip_phase * 0.6) * amplitude * 0.5
                    y = y_base + wave
                    points_top.append(QPointF(x, y - band_half))
                    points_bot.append(QPointF(x, y + band_half))
                all_pts = QPolygonF()
                for i in range(points_top.size()):
                    all_pts.append(points_top.at(i))
                for i in range(points_bot.size() - 1, -1, -1):
                    all_pts.append(points_bot.at(i))
                hue = (hue_base + strip * 25) % 360
                alpha = int(18 + bass * 35 - strip * 4 - layer * 3)
                alpha = max(3, min(120, alpha))
                grad = QLinearGradient(0, y_base - band_half - amplitude, 0, y_base + band_half + amplitude)
                grad.setColorAt(0, QColor.fromHsv(hue, 140, 255, 0))
                grad.setColorAt(0.3, QColor.fromHsv(hue, 150, 255, alpha))
                grad.setColorAt(0.5, QColor.fromHsv(hue, 130, 255, int(alpha * 1.3)))
                grad.setColorAt(0.7, QColor.fromHsv(hue, 150, 255, alpha))
                grad.setColorAt(1, QColor.fromHsv(hue, 140, 255, 0))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(grad))
                painter.drawPolygon(all_pts)

    def _paint_starfield(self, painter, w, h):
        cx, cy = w / 2, h / 2
        bass = float(np.mean(self._bars[:8]))
        painter.setPen(Qt.PenStyle.NoPen)
        for s in self._star_stars:
            if s['z'] <= 0.005:
                continue
            sx = cx + s['x'] / s['z'] * w * 0.3
            sy = cy + s['y'] / s['z'] * h * 0.3
            if not (0 <= sx <= w and 0 <= sy <= h):
                continue
            depth = 1.0 - s['z']
            size = max(1.5, depth * 5 + bass * 2)
            alpha = int(min(200, depth * 250))
            hue = s['hue']
            grad = QRadialGradient(sx, sy, size * 2.5)
            grad.setColorAt(0, QColor.fromHsv(hue, 100, 255, alpha))
            grad.setColorAt(0.3, QColor.fromHsv(hue, 130, 240, int(alpha * 0.6)))
            grad.setColorAt(1, QColor.fromHsv(hue, 160, 200, 0))
            painter.setBrush(QBrush(grad))
            painter.drawEllipse(QRectF(sx - size * 2.5, sy - size * 2.5, size * 5, size * 5))
            if depth > 0.6:
                tail_len = depth * 12 + bass * 6
                prev_z = s['z'] + 0.02
                px = cx + s['x'] / prev_z * w * 0.3
                py = cy + s['y'] / prev_z * h * 0.3
                tail_grad = QLinearGradient(px, py, sx, sy)
                tail_grad.setColorAt(0, QColor.fromHsv(hue, 120, 255, 0))
                tail_grad.setColorAt(1, QColor.fromHsv(hue, 120, 255, int(alpha * 0.4)))
                painter.setPen(QPen(QBrush(tail_grad), max(1, size * 0.5)))
                painter.drawLine(int(px), int(py), int(sx), int(sy))
                painter.setPen(Qt.PenStyle.NoPen)
        painter.setPen(Qt.PenStyle.NoPen)
        grad = QRadialGradient(cx, cy, min(w, h) * 0.35)
        grad.setColorAt(0, QColor(15, 20, 60, int(20 + bass * 40)))
        grad.setColorAt(1, QColor(5, 5, 10, 0))
        painter.setBrush(QBrush(grad))
        painter.drawRect(QRectF(0, 0, w, h))

    def _paint_cosmos(self, painter, w, h):
        bars = self._smooth_bars
        bass = float(np.mean(bars[:8]))
        mid = float(np.mean(bars[8:30]))
        high = float(np.mean(bars[30:]))
        cx, cy = w / 2, h / 2
        painter.setPen(Qt.PenStyle.NoPen)
        for s in self._cosmos_bg_stars:
            brightness = 0.4 + 0.6 * (0.5 + 0.5 * math.sin(s['twinkle']))
            alpha = int(brightness * 180)
            size = s['size'] * (0.8 + bass * 0.4)
            painter.setBrush(QColor(200, 220, 255, alpha))
            painter.drawEllipse(QRectF(s['x'] - size, s['y'] - size, size * 2, size * 2))
        nebula_r = min(w, h) * 0.4
        for i in range(3):
            angle = self._cosmos_rotation + i * 2.1
            nx = cx + math.cos(angle) * nebula_r * 0.3
            ny = cy + math.sin(angle) * nebula_r * 0.2
            hue = int(200 + i * 60 + self._cosmos_rotation * 20) % 360
            grad = QRadialGradient(nx, ny, nebula_r * (0.5 + bass * 0.2))
            grad.setColorAt(0, QColor.fromHsv(hue, 120, 200, int(15 + bass * 25)))
            grad.setColorAt(0.5, QColor.fromHsv(hue, 140, 180, int(8 + mid * 15)))
            grad.setColorAt(1, QColor.fromHsv(hue, 160, 150, 0))
            painter.setBrush(QBrush(grad))
            painter.drawEllipse(QRectF(nx - nebula_r, ny - nebula_r, nebula_r * 2, nebula_r * 2))
        ring_r = min(w, h) * 0.18
        for i in range(len(bars)):
            val = bars[i]
            if val < 0.02:
                continue
            angle = i * 2 * math.pi / len(bars) + self._cosmos_rotation
            x1 = cx + ring_r * math.cos(angle)
            y1 = cy + ring_r * math.sin(angle)
            bar_len = val * min(w, h) * 0.3
            x2 = cx + (ring_r + bar_len) * math.cos(angle)
            y2 = cy + (ring_r + bar_len) * math.sin(angle)
            hue = int(180 + i * 180 / len(bars)) % 360
            painter.setPen(QPen(QColor.fromHsv(hue, 200, 255, int(40 + val * 200)), max(1, 2 - val)))
            painter.drawLine(int(x1), int(y1), int(x2), int(y2))
        painter.setPen(Qt.PenStyle.NoPen)
        core_r = ring_r * 0.6
        grad = QRadialGradient(cx, cy, core_r)
        grad.setColorAt(0, QColor(20, 25, 50, 240))
        grad.setColorAt(0.6, QColor(15, 18, 40, 200))
        grad.setColorAt(1, QColor(8, 10, 25, 80))
        painter.setBrush(QBrush(grad))
        painter.drawEllipse(QRectF(cx - core_r, cy - core_r, core_r * 2, core_r * 2))
        if bass > 0.15:
            for i in range(3):
                pulse_r = ring_r * (1.05 + i * 0.08 + bass * 0.1)
                painter.setPen(QPen(QColor(80, 160, 255, int(bass * 60 - i * 15)), 1))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(QRectF(cx - pulse_r, cy - pulse_r, pulse_r * 2, pulse_r * 2))
        painter.setPen(Qt.PenStyle.NoPen)
        for p in self._cosmos_particles:
            alpha = int(p['life'] * 200)
            size = p['size'] * (0.3 + p['life'] * 0.7)
            painter.setBrush(QColor.fromHsv(p['hue'], 180, 255, alpha))
            painter.drawEllipse(QRectF(p['x'] - size, p['y'] - size, size * 2, size * 2))
        for m in self._cosmos_meteors:
            alpha = int(m['life'] * 220)
            tail_x = m['x'] - m['vx'] / (abs(m['vx']) + abs(m['vy']) + 0.01) * m['len']
            tail_y = m['y'] - m['vy'] / (abs(m['vx']) + abs(m['vy']) + 0.01) * m['len']
            grad = QLinearGradient(tail_x, tail_y, m['x'], m['y'])
            grad.setColorAt(0, QColor.fromHsv(m['hue'], 100, 255, 0))
            grad.setColorAt(0.7, QColor.fromHsv(m['hue'], 120, 255, int(alpha * 0.5)))
            grad.setColorAt(1, QColor(255, 255, 255, alpha))
            painter.setPen(QPen(QBrush(grad), 2))
            painter.drawLine(int(tail_x), int(tail_y), int(m['x']), int(m['y']))
            painter.setPen(Qt.PenStyle.NoPen)
            head_grad = QRadialGradient(m['x'], m['y'], 4)
            head_grad.setColorAt(0, QColor(255, 255, 255, alpha))
            head_grad.setColorAt(1, QColor.fromHsv(m['hue'], 100, 255, 0))
            painter.setBrush(QBrush(head_grad))
            painter.drawEllipse(QRectF(m['x'] - 4, m['y'] - 4, 8, 8))

    def _update_warp(self):
        w = self.width()
        h = self.height()
        if w <= 0 or h <= 0:
            return
        cx, cy = w / 2, h / 2
        bass = float(np.mean(self._bars[:8]))
        mid = float(np.mean(self._bars[8:30]))
        high = float(np.mean(self._bars[30:]))
        energy = bass + mid + high
        bass_hit = bass - self._warp_prev_bass
        if bass_hit < 0:
            bass_hit = 0
        self._warp_prev_bass = bass
        if self._frame_count % 2 == 0:
            count = 2 + int(energy * 8)
            for _ in range(count):
                angle = random.uniform(0, 2 * math.pi)
                dist = random.uniform(0, min(w, h) * 0.02)
                speed = 1.5 + energy * 10
                hue = random.randint(180, 280)
                z = random.uniform(0.3, 1.0)
                self._warp_streaks.append({
                    'x': cx + math.cos(angle) * dist,
                    'y': cy + math.sin(angle) * dist,
                    'angle': angle,
                    'speed': speed,
                    'life': 1.0,
                    'size': 1 + energy * 2,
                    'hue': hue,
                    'z': z,
                })
        alive = []
        for s in self._warp_streaks:
            s['x'] += math.cos(s['angle']) * s['speed'] * s['z']
            s['y'] += math.sin(s['angle']) * s['speed'] * s['z']
            s['speed'] *= 1.02
            s['life'] -= 0.008
            if s['life'] > 0 and -100 <= s['x'] <= w + 100 and -100 <= s['y'] <= h + 100:
                alive.append(s)
        self._warp_streaks = alive[-3000:]
        if bass_hit > 0.06 or (bass > 0.35 and self._frame_count % 25 == 0):
            self._warp_rings.append({
                'r': 5,
                'max_r': min(w, h) * (0.5 + bass * 0.5),
                'speed': 3 + bass * 12 + bass_hit * 30,
                'life': 1.0,
                'hue': random.randint(180, 280),
                'width': 2 + bass * 4,
            })
            spark_count = int(bass * 40 + bass_hit * 80) + 10
            for _ in range(spark_count):
                angle = random.uniform(0, 2 * math.pi)
                speed = 1.5 + bass * 12 + bass_hit * 25
                hue = random.randint(160, 300)
                z = random.uniform(0.2, 1.0)
                self._warp_sparks.append({
                    'x': cx,
                    'y': cy,
                    'vx': math.cos(angle) * speed * z,
                    'vy': math.sin(angle) * speed * z,
                    'life': 1.0,
                    'size': 1.5 + bass * 4 + random.random() * 2,
                    'hue': hue,
                    'z': z,
                    'trail': [(cx, cy)],
                })
        r_alive = []
        for ring in self._warp_rings:
            ring['r'] += ring['speed']
            ring['speed'] *= 0.99
            ring['life'] -= 0.012
            if ring['life'] > 0 and ring['r'] < ring['max_r'] * 1.5:
                r_alive.append(ring)
        self._warp_rings = r_alive[-20:]
        s_alive = []
        for sp in self._warp_sparks:
            sp['x'] += sp['vx']
            sp['y'] += sp['vy']
            sp['vx'] *= 0.985
            sp['vy'] *= 0.985
            sp['life'] -= 0.012
            sp['trail'].append((sp['x'], sp['y']))
            if len(sp['trail']) > 12:
                sp['trail'] = sp['trail'][-12:]
            if sp['life'] > 0 and -80 <= sp['x'] <= w + 80 and -80 <= sp['y'] <= h + 80:
                s_alive.append(sp)
        self._warp_sparks = s_alive[-2500:]

    def _paint_warp(self, painter, w, h):
        bars = self._smooth_bars
        bass = float(np.mean(bars[:8]))
        mid = float(np.mean(bars[8:30]))
        cx, cy = w / 2, h / 2
        painter.setPen(Qt.PenStyle.NoPen)
        core_r = min(w, h) * 0.04
        grad = QRadialGradient(cx, cy, core_r * 3)
        grad.setColorAt(0, QColor(200, 230, 255, int(80 + bass * 150)))
        grad.setColorAt(0.3, QColor(100, 160, 255, int(30 + bass * 60)))
        grad.setColorAt(1, QColor(20, 40, 100, 0))
        painter.setBrush(QBrush(grad))
        painter.drawEllipse(QRectF(cx - core_r * 3, cy - core_r * 3, core_r * 6, core_r * 6))
        for s in self._warp_streaks:
            alpha = int(s['life'] * 200 * s['z'])
            tail_len = s['speed'] * 2.5 * s['z']
            tx = s['x'] - math.cos(s['angle']) * tail_len
            ty = s['y'] - math.sin(s['angle']) * tail_len
            grad = QLinearGradient(tx, ty, s['x'], s['y'])
            grad.setColorAt(0, QColor.fromHsv(s['hue'], 120, 255, 0))
            grad.setColorAt(0.6, QColor.fromHsv(s['hue'], 140, 255, int(alpha * 0.4)))
            grad.setColorAt(1, QColor.fromHsv(s['hue'], 100, 255, alpha))
            painter.setPen(QPen(QBrush(grad), max(1, s['size'] * 0.8 * s['z'])))
            painter.drawLine(int(tx), int(ty), int(s['x']), int(s['y']))
        painter.setPen(Qt.PenStyle.NoPen)
        for ring in self._warp_rings:
            r = ring['r']
            alpha = int(ring['life'] * 180)
            hue = ring['hue']
            painter.setPen(QPen(QColor.fromHsv(hue, 160, 255, alpha), ring['width'] * ring['life']))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))
            if ring['life'] > 0.5:
                inner_r = r * 0.95
                painter.setPen(QPen(QColor.fromHsv(hue, 100, 255, int(alpha * 0.3)), ring['width'] * ring['life'] * 2))
                painter.drawEllipse(QRectF(cx - inner_r, cy - inner_r, inner_r * 2, inner_r * 2))
        painter.setPen(Qt.PenStyle.NoPen)
        for sp in self._warp_sparks:
            trail = sp['trail']
            n = len(trail)
            if n < 2:
                continue
            z = sp['z']
            for i in range(1, n):
                frac = i / n
                alpha = int(sp['life'] * 200 * frac * z)
                if alpha < 2:
                    continue
                x1, y1 = trail[i - 1]
                x2, y2 = trail[i]
                painter.setPen(QPen(QColor.fromHsv(sp['hue'], 160, 255, alpha), max(1, sp['size'] * frac * z)))
                painter.drawLine(int(x1), int(y1), int(x2), int(y2))
            painter.setPen(Qt.PenStyle.NoPen)
            alpha = int(sp['life'] * 220 * z)
            size = sp['size'] * (0.3 + sp['life'] * 0.7) * z
            painter.setBrush(QColor.fromHsv(sp['hue'], 180, 255, alpha))
            painter.drawEllipse(QRectF(sp['x'] - size, sp['y'] - size, size * 2, size * 2))
        inner_r = min(w, h) * 0.06
        for i in range(len(bars)):
            val = bars[i]
            if val < 0.03:
                continue
            angle = i * 2 * math.pi / len(bars)
            bar_len = val * min(w, h) * 0.15
            x1 = cx + inner_r * math.cos(angle)
            y1 = cy + inner_r * math.sin(angle)
            x2 = cx + (inner_r + bar_len) * math.cos(angle)
            y2 = cy + (inner_r + bar_len) * math.sin(angle)
            hue = int(180 + i * 180 / len(bars)) % 360
            painter.setPen(QPen(QColor.fromHsv(hue, 180, 255, int(30 + val * 180)), max(1, 2)))
            painter.drawLine(int(x1), int(y1), int(x2), int(y2))
        painter.setPen(Qt.PenStyle.NoPen)

    def _update_fluid(self):
        self._fluid_hue = (self._fluid_hue + 0.3) % 360
        bass = float(np.mean(self._bars[:8]))
        mid = float(np.mean(self._bars[8:30]))
        self._fluid_phase += 0.02 + bass * 0.06 + mid * 0.03

    def _update_milkdrop(self):
        self._milk_hue = (self._milk_hue + 0.4) % 360
        bass = float(np.mean(self._bars[:8]))
        mid = float(np.mean(self._bars[8:30]))
        self._milk_phase += 0.015 + bass * 0.05
        self._milk_rot += 0.002 + bass * 0.01
        self._milk_zoom = 1.0 + bass * 0.05

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
            freq = 20 + i * (18000 - 20) / n
            angle = phase + i * 0.15 + math.sin(phase * 0.7 + i * 0.05) * 2
            dist = 30 + val * min(w, h) * 0.35
            px = cx + math.cos(angle) * dist * 0.3
            py = cy + math.sin(angle) * dist * 0.3
            size = 3 + val * 15
            bar_hue = int(hue + i * 2.8) % 360
            alpha = int(val * 200)
            grad = QRadialGradient(px, py, size)
            grad.setColorAt(0, QColor.fromHsv(bar_hue, 180, 255, alpha))
            grad.setColorAt(0.5, QColor.fromHsv(bar_hue, 200, 220, int(alpha * 0.5)))
            grad.setColorAt(1, QColor.fromHsv(bar_hue, 220, 180, 0))
            fade_painter.setPen(Qt.PenStyle.NoPen)
            fade_painter.setBrush(QBrush(grad))
            fade_painter.drawEllipse(QRectF(px - size, py - size, size * 2, size * 2))

        for layer in range(3):
            points = []
            y_base = h * (0.3 + layer * 0.15)
            amp = h * (0.05 + bass * 0.12)
            for x in range(0, w + 10, 10):
                wave = math.sin(x * 0.006 + phase + layer * 1.2) * amp
                wave += math.sin(x * 0.013 + phase * 1.5 + layer * 0.8) * amp * 0.4
                wave += math.cos(x * 0.003 + phase * 0.5 + layer * 2.1) * amp * 0.3
                y = y_base + wave
                points.append((x, y))
            for i in range(len(points) - 1):
                x1, y1 = points[i]
                x2, y2 = points[i + 1]
                line_hue = int(hue + layer * 80 + i * 0.5) % 360
                alpha = int(40 + bass * 80)
                fade_painter.setPen(QPen(QColor.fromHsv(line_hue, 150, 255, alpha), 2 + bass * 3))
                fade_painter.drawLine(int(x1), int(y1), int(x2), int(y2))

        fade_painter.end()
        painter.drawImage(0, 0, self._fluid_buf)

    def _paint_milkdrop(self, painter, w, h):
        bars = self._smooth_bars
        bass = float(np.mean(bars[:8]))
        mid = float(np.mean(bars[8:30]))
        high = float(np.mean(bars[30:]))
        cx, cy = w / 2, h / 2
        phase = self._milk_phase
        hue = self._milk_hue

        if self._milk_buf is None or self._milk_buf_w != w or self._milk_buf_h != h:
            self._milk_buf = QImage(w, h, QImage.Format.Format_ARGB32)
            self._milk_buf.fill(QColor(0, 0, 0, 0))
            self._milk_buf_w = w
            self._milk_buf_h = h

        temp_buf = QImage(w, h, QImage.Format.Format_ARGB32)
        temp_painter = QPainter(temp_buf)
        temp_painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        fade_alpha = max(6, min(30, int(10 + (bass + mid) * 12)))
        temp_painter.fillRect(0, 0, w, h, QColor(0, 0, 0, fade_alpha))
        temp_painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        temp_painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        zoom = self._milk_zoom
        rot = self._milk_rot
        temp_painter.translate(cx, cy)
        temp_painter.rotate(math.degrees(rot))
        temp_painter.scale(1.0 / zoom, 1.0 / zoom)
        temp_painter.translate(-cx, -cy)
        temp_painter.setOpacity(0.95)
        temp_painter.drawImage(0, 0, self._milk_buf)
        temp_painter.end()

        draw_painter = QPainter(temp_buf)
        draw_painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        draw_painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        n = len(bars)
        for i in range(0, n, 2):
            val = bars[i]
            if val < 0.02:
                continue
            angle = i * 2 * math.pi / n + phase * 0.3
            dist = 20 + val * min(w, h) * 0.3
            px = cx + math.cos(angle) * dist
            py = cy + math.sin(angle) * dist
            size = 4 + val * 20
            bar_hue = int(hue + i * 2.8) % 360
            alpha = int(val * 180)
            grad = QRadialGradient(px, py, size)
            grad.setColorAt(0, QColor.fromHsv(bar_hue, 170, 255, alpha))
            grad.setColorAt(0.6, QColor.fromHsv(bar_hue, 200, 220, int(alpha * 0.4)))
            grad.setColorAt(1, QColor.fromHsv(bar_hue, 220, 180, 0))
            draw_painter.setPen(Qt.PenStyle.NoPen)
            draw_painter.setBrush(QBrush(grad))
            draw_painter.drawEllipse(QRectF(px - size, py - size, size * 2, size * 2))

        for layer in range(4):
            y_base = h * (0.2 + layer * 0.15)
            amp = h * (0.04 + bass * 0.10 + mid * 0.05)
            prev = None
            for x in range(0, w + 12, 12):
                wave = math.sin(x * 0.005 + phase + layer * 1.5) * amp
                wave += math.sin(x * 0.011 + phase * 1.3 + layer * 0.9) * amp * 0.35
                wave += math.cos(x * 0.003 + phase * 0.6 + layer * 2.3) * amp * 0.3
                y = y_base + wave
                if prev is not None:
                    line_hue = int(hue + layer * 90 + x * 0.1) % 360
                    alpha = int(30 + bass * 60)
                    draw_painter.setPen(QPen(QColor.fromHsv(line_hue, 140, 255, alpha), 1.5 + bass * 2))
                    draw_painter.drawLine(int(prev[0]), int(prev[1]), int(x), int(y))
                prev = (x, y)

        if bass > 0.25:
            ring_r = min(w, h) * 0.1 * (1 + bass * 0.5)
            ring_hue = int(hue + 60) % 360
            draw_painter.setPen(QPen(QColor.fromHsv(ring_hue, 150, 255, int(bass * 120)), 2))
            draw_painter.setBrush(Qt.BrushStyle.NoBrush)
            draw_painter.drawEllipse(QRectF(cx - ring_r, cy - ring_r, ring_r * 2, ring_r * 2))

        draw_painter.end()
        self._milk_buf = temp_buf
        painter.drawImage(0, 0, self._milk_buf)


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
        audio = mutagen.File(file_path)
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
        audio = mutagen.File(file_path)
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
