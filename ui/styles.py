import os
import tempfile
import atexit
import shutil


_SVG_TMPDIR: str = tempfile.mkdtemp(prefix='iptv_svg_')
atexit.register(shutil.rmtree, _SVG_TMPDIR, ignore_errors=True)


def color_to_qcolor(color_str):
    if not color_str:
        from PyQt6.QtGui import QColor
        return QColor()
    if color_str.startswith('#'):
        from PyQt6.QtGui import QColor
        return QColor(color_str)
    if color_str.startswith('rgba('):
        try:
            inner = color_str[5:].rstrip(')')
            parts = [p.strip() for p in inner.split(',')]
            from PyQt6.QtGui import QColor
            return QColor(int(parts[0]), int(parts[1]), int(parts[2]), int(float(parts[3]) * 255))
        except Exception:
            from PyQt6.QtGui import QColor
            return QColor()
    if color_str.startswith('rgb('):
        try:
            inner = color_str[4:].rstrip(')')
            parts = [p.strip() for p in inner.split(',')]
            from PyQt6.QtGui import QColor
            return QColor(int(parts[0]), int(parts[1]), int(parts[2]))
        except Exception:
            from PyQt6.QtGui import QColor
            return QColor()
    from PyQt6.QtGui import QColor
    return QColor(color_str)


def color_to_hex(color_str):
    qc = color_to_qcolor(color_str)
    if qc.isValid():
        return qc.name()
    return color_str


class AppStyles:
    """应用样式管理类 - 支持颜色模式×视觉风格双维度主题"""

    _color_mode = 'dark'
    _visual_style = 'flat'
    _current_theme = 'dark'
    _arrow_cache = {}
    _check_cache = {}
    _radio_cache = {}
    _spinup_cache = {}
    _spindown_cache = {}
    _icon_cache = {}

    # 固定颜色常量（不随主题变化）
    COLOR_WHITE          = '#ffffff'
    COLOR_CLOSE_HOVER    = '#e81123'

    AVAILABLE_COLOR_MODES = ['auto', 'dark', 'light']
    AVAILABLE_VISUAL_STYLES = ['neumorphic', 'flat', 'skeuomorphic', 'frosted', 'win11', 'mac', 'ios']

    _OLD_THEME_MAPPING = {
        'dark': ('dark', 'flat'),
        'light': ('light', 'flat'),
        'dark_blue': ('dark', 'neumorphic'),
        'neumorphic_light': ('light', 'neumorphic'),
        'github_dark': ('dark', 'flat'),
    }

    @classmethod
    def _get_svg_image(cls, cache: dict, filename_prefix: str, svg_content: str) -> str:
        """通用 SVG 图标缓存辅助：将 SVG 写入临时文件（每种变体只写一次），
        返回文件路径供 Qt QSS image: url(...) 使用。
        Qt 的 QSS 不支持 data URI，必须使用文件路径。"""
        if filename_prefix in cache:
            return cache[filename_prefix]
        path = os.path.join(_SVG_TMPDIR, f'{filename_prefix}.svg')
        with open(path, 'w', encoding='utf-8') as f:
            f.write(svg_content)
        # Qt QSS 在 Windows 下需要正斜杠路径
        path = path.replace('\\', '/')
        cache[filename_prefix] = path
        return path

    @classmethod
    def _get_arrow_image(cls, color: str) -> str:
        color = color_to_hex(color)
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="6" viewBox="0 0 10 6">'
            f'<path d="M0 0 L5 6 L10 0 Z" fill="{color}"/>'
            f'</svg>'
        )
        return cls._get_svg_image(cls._arrow_cache, f'arrow_down_{color.lstrip("#")}', svg)

    @classmethod
    def _get_check_image(cls, color: str) -> str:
        color = color_to_hex(color)
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16">'
            f'<path d="M3 8 L6.5 11.5 L13 4.5" stroke="{color}" stroke-width="2.5" '
            f'fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
            f'</svg>'
        )
        return cls._get_svg_image(cls._check_cache, f'check_{color.lstrip("#")}', svg)

    @classmethod
    def _get_radio_dot_image(cls, color: str) -> str:
        color = color_to_hex(color)
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16">'
            f'<circle cx="8" cy="8" r="4" fill="{color}"/>'
            f'</svg>'
        )
        return cls._get_svg_image(cls._radio_cache, f'radio_dot_{color.lstrip("#")}', svg)

    @classmethod
    def _get_spin_up_image(cls, color: str) -> str:
        color = color_to_hex(color)
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="6" viewBox="0 0 10 6">'
            f'<path d="M0 6 L5 0 L10 6 Z" fill="{color}"/>'
            f'</svg>'
        )
        return cls._get_svg_image(cls._spinup_cache, f'spin_up_{color.lstrip("#")}', svg)

    @classmethod
    def _get_spin_down_image(cls, color: str) -> str:
        color = color_to_hex(color)
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="6" viewBox="0 0 10 6">'
            f'<path d="M0 0 L5 6 L10 0 Z" fill="{color}"/>'
            f'</svg>'
        )
        return cls._get_svg_image(cls._spindown_cache, f'spin_down_{color.lstrip("#")}', svg)

    @classmethod
    def get_icon(cls, name: str, color: str = None, size: int = 16) -> str:
        if color is None:
            color = cls._get_colors().get('window_text', '#ffffff')
        color = color_to_hex(color)
        key = f'{name}_{size}_{color.lstrip("#")}'
        if key in cls._icon_cache:
            return cls._icon_cache[key]
        svg = cls._build_icon_svg(name, color, size)
        if svg is None:
            return None
        return cls._get_svg_image(cls._icon_cache, key, svg)

    @classmethod
    def _build_icon_svg(cls, name: str, color: str, size: int) -> str:
        s = size
        h = s / 2
        p = s * 0.15
        icons = {
            'play': (
                f'<polygon points="{s*0.3},{p} {s*0.8},{h} {s*0.3},{s-p}" fill="{color}"/>'
            ),
            'pause': (
                f'<rect x="{p}" y="{p}" width="{s*0.3}" height="{s-p*2}" rx="1" fill="{color}"/>'
                f'<rect x="{s*0.55}" y="{p}" width="{s*0.3}" height="{s-p*2}" rx="1" fill="{color}"/>'
            ),
            'stop': (
                f'<rect x="{p}" y="{p}" width="{s-p*2}" height="{s-p*2}" rx="2" fill="{color}"/>'
            ),
            'prev': (
                f'<polygon points="{h},{p} {p},{h} {h},{s-p}" fill="{color}"/>'
                f'<rect x="{s*0.6}" y="{p}" width="{s*0.12}" height="{s-p*2}" rx="1" fill="{color}"/>'
            ),
            'next': (
                f'<polygon points="{h},{p} {s-p},{h} {h},{s-p}" fill="{color}"/>'
                f'<rect x="{s*0.28}" y="{p}" width="{s*0.12}" height="{s-p*2}" rx="1" fill="{color}"/>'
            ),
            'backward': (
                f'<polygon points="{s*0.55},{p} {p},{h} {s*0.55},{s-p}" fill="{color}"/>'
                f'<polygon points="{s-p},{p} {s*0.55},{h} {s-p},{s-p}" fill="{color}"/>'
            ),
            'volume': (
                f'<path d="M{p+s*0.05},{h} L{p+s*0.05},{h-s*0.15} L{p+s*0.3},{h-s*0.3} L{p+s*0.3},{h+s*0.3} L{p+s*0.05},{h+s*0.15} Z" fill="{color}"/>'
                f'<path d="M{p+s*0.38},{h-s*0.17} A{s*0.17},{s*0.17} 0 0,1 {p+s*0.38},{h+s*0.17}" stroke="{color}" stroke-width="{s*0.07}" fill="none" stroke-linecap="round"/>'
                f'<path d="M{p+s*0.5},{h-s*0.28} A{s*0.28},{s*0.28} 0 0,1 {p+s*0.5},{h+s*0.28}" stroke="{color}" stroke-width="{s*0.07}" fill="none" stroke-linecap="round"/>'
            ),
            'volume_low': (
                f'<path d="M{p+s*0.05},{h} L{p+s*0.05},{h-s*0.15} L{p+s*0.3},{h-s*0.3} L{p+s*0.3},{h+s*0.3} L{p+s*0.05},{h+s*0.15} Z" fill="{color}"/>'
                f'<path d="M{p+s*0.38},{h-s*0.17} A{s*0.17},{s*0.17} 0 0,1 {p+s*0.38},{h+s*0.17}" stroke="{color}" stroke-width="{s*0.07}" fill="none" stroke-linecap="round"/>'
            ),
            'volume_mute': (
                f'<path d="M{p+s*0.05},{h} L{p+s*0.05},{h-s*0.15} L{p+s*0.3},{h-s*0.3} L{p+s*0.3},{h+s*0.3} L{p+s*0.05},{h+s*0.15} Z" fill="{color}"/>'
                f'<line x1="{p+s*0.4}" y1="{h-s*0.15}" x2="{p+s*0.65}" y2="{h+s*0.15}" stroke="{color}" stroke-width="{s*0.07}" stroke-linecap="round"/>'
            ),
            'fullscreen': (
                f'<path d="M{p},{p+s*0.25} L{p},{p} L{p+s*0.25},{p}" stroke="{color}" stroke-width="{s*0.08}" fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
                f'<path d="M{s-p-s*0.25},{p} L{s-p},{p} L{s-p},{p+s*0.25}" stroke="{color}" stroke-width="{s*0.08}" fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
                f'<path d="M{s-p},{s-p-s*0.25} L{s-p},{s-p} L{s-p-s*0.25},{s-p}" stroke="{color}" stroke-width="{s*0.08}" fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
                f'<path d="M{p+s*0.25},{s-p} L{p},{s-p} L{p},{s-p-s*0.25}" stroke="{color}" stroke-width="{s*0.08}" fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
            ),
            'restore': (
                f'<path d="M{p+s*0.15},{p+s*0.35} L{p+s*0.15},{p+s*0.15} L{p+s*0.35},{p+s*0.15}" stroke="{color}" stroke-width="{s*0.08}" fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
                f'<path d="M{s-p-s*0.15},{s-p-s*0.35} L{s-p-s*0.15},{s-p-s*0.15} L{s-p-s*0.35},{s-p-s*0.15}" stroke="{color}" stroke-width="{s*0.08}" fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
                f'<rect x="{p}" y="{p+s*0.25}" width="{s-p*2-s*0.05}" height="{s-p*2-s*0.05}" rx="1" stroke="{color}" stroke-width="{s*0.08}" fill="none"/>'
            ),
            'minimize': (
                f'<line x1="{p}" y1="{h}" x2="{s-p}" y2="{h}" stroke="{color}" stroke-width="{s*0.1}" stroke-linecap="round"/>'
            ),
            'close': (
                f'<line x1="{p}" y1="{p}" x2="{s-p}" y2="{s-p}" stroke="{color}" stroke-width="{s*0.1}" stroke-linecap="round"/>'
                f'<line x1="{s-p}" y1="{p}" x2="{p}" y2="{s-p}" stroke="{color}" stroke-width="{s*0.1}" stroke-linecap="round"/>'
            ),
            'list_view': (
                f'<rect x="{p}" y="{p}" width="{s-p*2}" height="{s*0.08}" rx="1" fill="{color}"/>'
                f'<rect x="{p}" y="{h-s*0.04}" width="{s-p*2}" height="{s*0.08}" rx="1" fill="{color}"/>'
                f'<rect x="{p}" y="{s-p-s*0.08}" width="{s-p*2}" height="{s*0.08}" rx="1" fill="{color}"/>'
            ),
            'grid_view': (
                f'<rect x="{p}" y="{p}" width="{h-p-s*0.04}" height="{h-p-s*0.04}" rx="1" fill="{color}"/>'
                f'<rect x="{h+s*0.04}" y="{p}" width="{h-p-s*0.04}" height="{h-p-s*0.04}" rx="1" fill="{color}"/>'
                f'<rect x="{p}" y="{h+s*0.04}" width="{h-p-s*0.04}" height="{h-p-s*0.04}" rx="1" fill="{color}"/>'
                f'<rect x="{h+s*0.04}" y="{h+s*0.04}" width="{h-p-s*0.04}" height="{h-p-s*0.04}" rx="1" fill="{color}"/>'
            ),
            'pip': (
                f'<rect x="{p}" y="{p}" width="{s-p*2}" height="{s-p*2}" rx="2" stroke="{color}" stroke-width="{s*0.08}" fill="none"/>'
                f'<rect x="{h}" y="{h}" width="{h-p}" height="{h-p}" rx="1" fill="{color}"/>'
            ),
            'speed': (
                f'<circle cx="{h}" cy="{h}" r="{h-p}" stroke="{color}" stroke-width="{s*0.08}" fill="none"/>'
                f'<line x1="{h}" y1="{h}" x2="{h}" y2="{p+s*0.15}" stroke="{color}" stroke-width="{s*0.08}" stroke-linecap="round"/>'
                f'<line x1="{h}" y1="{h}" x2="{h+s*0.2}" y2="{h}" stroke="{color}" stroke-width="{s*0.08}" stroke-linecap="round"/>'
            ),
            'aspect': (
                f'<rect x="{p}" y="{p}" width="{s-p*2}" height="{s-p*2}" rx="2" stroke="{color}" stroke-width="{s*0.08}" fill="none"/>'
                f'<line x1="{p+s*0.15}" y1="{s-p}" x2="{p+s*0.15}" y2="{s-p-s*0.2}" stroke="{color}" stroke-width="{s*0.06}" stroke-linecap="round"/>'
                f'<line x1="{p}" y1="{s-p-s*0.15}" x2="{p+s*0.2}" y2="{s-p-s*0.15}" stroke="{color}" stroke-width="{s*0.06}" stroke-linecap="round"/>'
            ),
            'audio_track': (
                f'<path d="M{h},{p+s*0.1} L{h},{s-p-s*0.15} Q{h},{s-p} {h-s*0.15},{s-p}" stroke="{color}" stroke-width="{s*0.08}" fill="none" stroke-linecap="round"/>'
                f'<circle cx="{h-s*0.15}" cy="{s-p-s*0.1}" r="{s*0.1}" stroke="{color}" stroke-width="{s*0.08}" fill="none"/>'
                f'<line x1="{h}" y1="{p+s*0.1}" x2="{s-p}" y2="{p+s*0.25}" stroke="{color}" stroke-width="{s*0.08}" stroke-linecap="round"/>'
            ),
            'subtitle': (
                f'<rect x="{p}" y="{h-s*0.15}" width="{s-p*2}" height="{s*0.3}" rx="2" stroke="{color}" stroke-width="{s*0.08}" fill="none"/>'
                f'<line x1="{p+s*0.15}" y1="{h}" x2="{p+s*0.4}" y2="{h}" stroke="{color}" stroke-width="{s*0.06}" stroke-linecap="round"/>'
            ),
            'pin': (
                f'<path d="M{h},{p+s*0.2} L{h},{s-p-s*0.15}" stroke="{color}" stroke-width="{s*0.08}" fill="none" stroke-linecap="round"/>'
                f'<circle cx="{h}" cy="{p+s*0.2}" r="{s*0.12}" stroke="{color}" stroke-width="{s*0.08}" fill="none"/>'
                f'<line x1="{p+s*0.2}" y1="{s-p-s*0.15}" x2="{s-p-s*0.2}" y2="{s-p-s*0.15}" stroke="{color}" stroke-width="{s*0.08}" stroke-linecap="round"/>'
            ),
            'pin_active': (
                f'<path d="M{h},{p+s*0.2} L{h},{s-p-s*0.15}" stroke="{color}" stroke-width="{s*0.08}" stroke-linecap="round"/>'
                f'<circle cx="{h}" cy="{p+s*0.2}" r="{s*0.12}" fill="{color}"/>'
                f'<line x1="{p+s*0.2}" y1="{s-p-s*0.15}" x2="{s-p-s*0.2}" y2="{s-p-s*0.15}" stroke="{color}" stroke-width="{s*0.08}" stroke-linecap="round"/>'
            ),
            'tv': (
                f'<rect x="{p+s*0.05}" y="{h-s*0.25}" width="{s-p*2-s*0.1}" height="{h-p-s*0.05}" rx="1.5" stroke="{color}" stroke-width="{s*0.09}" fill="none"/>'
                f'<line x1="{h-s*0.12}" y1="{p+s*0.05}" x2="{h-s*0.12}" y2="{h-s*0.25}" stroke="{color}" stroke-width="{s*0.09}" stroke-linecap="round"/>'
                f'<line x1="{h+s*0.12}" y1="{p+s*0.05}" x2="{h+s*0.12}" y2="{h-s*0.25}" stroke="{color}" stroke-width="{s*0.09}" stroke-linecap="round"/>'
            ),
            'speaker': (
                f'<path d="M{p+s*0.05},{h} L{p+s*0.05},{h-s*0.15} L{p+s*0.3},{h-s*0.3} L{p+s*0.3},{h+s*0.3} L{p+s*0.05},{h+s*0.15} Z" fill="{color}"/>'
                f'<path d="M{p+s*0.45},{h-s*0.22} A{s*0.22},{s*0.22} 0 0,1 {p+s*0.45},{h+s*0.22}" stroke="{color}" stroke-width="{s*0.1}" fill="none" stroke-linecap="round"/>'
            ),
            'signal': (
                f'<circle cx="{p+s*0.2}" cy="{s-p-s*0.1}" r="{s*0.08}" fill="{color}"/>'
                f'<path d="M{p+s*0.38},{s-p-s*0.1} A{s*0.25},{s*0.25} 0 0,1 {p+s*0.2},{s-p-s*0.35}" stroke="{color}" stroke-width="{s*0.1}" fill="none" stroke-linecap="round"/>'
                f'<path d="M{p+s*0.58},{s-p-s*0.1} A{s*0.45},{s*0.45} 0 0,1 {p+s*0.2},{s-p-s*0.55}" stroke="{color}" stroke-width="{s*0.1}" fill="none" stroke-linecap="round"/>'
            ),
            'calendar': (
                f'<rect x="{p}" y="{p+s*0.25}" width="{s-p*2}" height="{s-p-s*0.25}" rx="2" stroke="{color}" stroke-width="{s*0.08}" fill="none"/>'
                f'<line x1="{p}" y1="{p+s*0.45}" x2="{s-p}" y2="{p+s*0.45}" stroke="{color}" stroke-width="{s*0.06}"/>'
                f'<line x1="{h-s*0.15}" y1="{p}" x2="{h-s*0.15}" y2="{p+s*0.35}" stroke="{color}" stroke-width="{s*0.08}" stroke-linecap="round"/>'
                f'<line x1="{h+s*0.15}" y1="{p}" x2="{h+s*0.15}" y2="{p+s*0.35}" stroke="{color}" stroke-width="{s*0.08}" stroke-linecap="round"/>'
            ),
            'folder': (
                f'<path d="M{p},{p+s*0.25} L{p},{s-p} Q{p},{s-p} {p+s*0.05},{s-p} L{s-p-s*0.05},{s-p} Q{s-p},{s-p} {s-p},{s-p} L{s-p},{p+s*0.25} Z" stroke="{color}" stroke-width="{s*0.08}" fill="none" stroke-linejoin="round"/>'
                f'<path d="M{p},{p+s*0.25} L{p},{p+s*0.15} Q{p},{p+s*0.1} {p+s*0.05},{p+s*0.1} L{p+s*0.3},{p+s*0.1} L{p+s*0.4},{p+s*0.25}" stroke="{color}" stroke-width="{s*0.08}" fill="none" stroke-linejoin="round"/>'
            ),
            'settings': (
                f'<circle cx="{h}" cy="{h}" r="{s*0.2}" stroke="{color}" stroke-width="{s*0.08}" fill="none"/>'
                f'<path d="M{h},{p} L{h},{p+s*0.2} M{h},{s-p-s*0.2} L{h},{s-p} M{p},{h} L{p+s*0.2},{h} M{s-p-s*0.2},{h} L{s-p},{h}" stroke="{color}" stroke-width="{s*0.08}" stroke-linecap="round"/>'
                f'<path d="M{p+s*0.15},{p+s*0.15} L{p+s*0.25},{p+s*0.25} M{s-p-s*0.25},{s-p-s*0.25} L{s-p-s*0.15},{s-p-s*0.15} M{s-p-s*0.15},{p+s*0.15} L{s-p-s*0.25},{p+s*0.25} M{p+s*0.25},{s-p-s*0.25} L{p+s*0.15},{s-p-s*0.15}" stroke="{color}" stroke-width="{s*0.08}" stroke-linecap="round"/>'
            ),
            'edit': (
                f'<path d="M{s-p-s*0.3},{p+s*0.2} L{p+s*0.3},{s-p-s*0.2} L{p+s*0.15},{s-p} L{p},{s-p-s*0.15} L{s-p-s*0.3},{p+s*0.2} Z" stroke="{color}" stroke-width="{s*0.08}" fill="none" stroke-linejoin="round"/>'
                f'<line x1="{s-p-s*0.45}" y1="{p+s*0.35}" x2="{s-p-s*0.15}" y2="{p+s*0.05}" stroke="{color}" stroke-width="{s*0.08}" stroke-linecap="round"/>'
            ),
            'save': (
                f'<rect x="{p}" y="{p}" width="{s-p*2}" height="{s-p*2}" rx="2" stroke="{color}" stroke-width="{s*0.08}" fill="none"/>'
                f'<rect x="{p+s*0.2}" y="{p}" width="{s-p*2-s*0.4}" height="{s*0.3}" fill="{color}"/>'
                f'<rect x="{p+s*0.25}" y="{h}" width="{s-p*2-s*0.5}" height="{s*0.25}" rx="1" stroke="{color}" stroke-width="{s*0.06}" fill="none"/>'
            ),
            'refresh': (
                f'<path d="M{s-p},{h} A{h-p},{h-p} 0 1,1 {h},{p}" stroke="{color}" stroke-width="{s*0.08}" fill="none" stroke-linecap="round"/>'
                f'<polygon points="{h},{p} {h+s*0.15},{p+s*0.2} {h-s*0.15},{p+s*0.2}" fill="{color}"/>'
            ),
            'check': (
                f'<path d="M{p+s*0.2},{h} L{h-s*0.1},{s-p-s*0.15} L{s-p},{p+s*0.2}" stroke="{color}" stroke-width="{s*0.1}" fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
            ),
            'hourglass': (
                f'<path d="M{p+s*0.2},{p} L{s-p-s*0.2},{p} L{h},{h} L{s-p-s*0.2},{s-p} L{p+s*0.2},{s-p} L{h},{h} Z" stroke="{color}" stroke-width="{s*0.08}" fill="none" stroke-linejoin="round"/>'
            ),
            'chevron_left': (
                f'<polyline points="{s-p},{p} {p},{h} {s-p},{s-p}" stroke="{color}" stroke-width="{s*0.1}" fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
            ),
            'chevron_right': (
                f'<polyline points="{p},{p} {s-p},{h} {p},{s-p}" stroke="{color}" stroke-width="{s*0.1}" fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
            ),
        }
        body = icons.get(name)
        if body is None:
            return None
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 {size} {size}">'
            f'{body}'
            f'</svg>'
        )

    COLOR_PALETTES = {
        'dark': {
            'window': '#000000',
            'window_text': '#ffffff',
            'base': '#1a1a1a',
            'alternate_base': '#2a2a2a',
            'button': '#3a3a3a',
            'light': '#444444',
            'mid': '#555555',
            'dark': '#666666',
            'highlight': '#2a3a5a',
            'highlighted_text': '#6a9eff',
            'bright_text': '#ffffff',
            'link': '#6a9eff',
            'link_visited': '#8a7eff',
            'tooltip_base': '#2a2a2a',
            'tooltip_text': '#f0f0f0',
            'placeholder': '#aaaaaa',
            'accent': '#4a7eff',
            'accent_hover': '#3a6eff',
            'accent_pressed': '#2a5eff',
            'success': '#4CAF50',
            'warning': '#FF9800',
            'error': '#f44336',
            'error_background': '#3a1a1a',
            'info': '#2196F3',
            'table_header': '#3a3a3a',
            'table_header_gradient_start': '#444444',
            'table_header_gradient_middle': '#3a3a3a',
            'table_header_gradient_end': '#2a2a2a',
            'table_header_text': '#ffffff',
            'table_header_hover': '#4a7eff',
            'table_border': '#555555',
            'table_grid': '#444444',
            'table_alternate': '#1a1a1a',
            'table_hover': '#2a3a5a',
            'table_selection': '#4a7eff',
            'table_selection_text': '#ffffff',
            'player_background': '#1a1a1a',
            'player_panel': '#2a2a2a',
            'player_panel_text': '#ffffff',
            'player_panel_secondary': '#aaaaaa',
            'player_panel_disabled': '#888888',
            'player_panel_hint': '#888888',
            'player_button': 'rgba(60, 60, 60, 0.9)',
            'player_combo': 'rgba(45, 45, 45, 0.8)',
            'player_line': '#555555',
            'player_accent': '#6a9eff',
            'player_success': '#4CAF50',
            'player_warning': '#ff6464',
            'player_slider_track': '#555555',
            'player_slider_fill': '#4CAF50',
            'player_slider_handle': '#ffffff',
            'player_cache_bar': 'rgba(76, 175, 80, 0.4)',
            'player_volume_track': '#444444',
            'player_video_placeholder': '#1a1a1a',
            'window_opacity': 220,
            'shadow_light': 'rgba(255,255,255,0.05)',
            'shadow_dark': 'rgba(0,0,0,0.4)',
            'neumorphic_light': '#323232',
            'neumorphic_dark': '#0a0a0a',
        },
        'light': {
            'window': '#f0f0f0',
            'window_text': '#333333',
            'base': '#ffffff',
            'alternate_base': '#e8e8e8',
            'button': '#d0d0d0',
            'light': '#e0e0e0',
            'mid': '#c0c0c0',
            'dark': '#a0a0a0',
            'highlight': '#cce0ff',
            'highlighted_text': '#2a6eff',
            'bright_text': '#000000',
            'link': '#2a6eff',
            'link_visited': '#6a5eff',
            'tooltip_base': '#ffffff',
            'tooltip_text': '#333333',
            'placeholder': '#767676',
            'accent': '#2a6eff',
            'accent_hover': '#1a5eff',
            'accent_pressed': '#0a4eff',
            'success': '#4CAF50',
            'warning': '#FF9800',
            'error': '#f44336',
            'error_background': '#ffdddd',
            'info': '#2196F3',
            'table_header': '#d8d8d8',
            'table_header_gradient_start': '#e8e8e8',
            'table_header_gradient_middle': '#d8d8d8',
            'table_header_gradient_end': '#c8c8c8',
            'table_header_text': '#333333',
            'table_header_hover': '#2a6eff',
            'table_border': '#c0c0c0',
            'table_grid': '#d0d0d0',
            'table_alternate': '#f5f5f5',
            'table_hover': '#cce0ff',
            'table_selection': '#2a6eff',
            'table_selection_text': '#ffffff',
            'player_background': '#e0e0e0',
            'player_panel': '#f0f0f0',
            'player_panel_text': '#333333',
            'player_panel_secondary': '#555555',
            'player_panel_disabled': '#999999',
            'player_panel_hint': '#aaaaaa',
            'player_button': 'rgba(200, 200, 200, 0.9)',
            'player_combo': 'rgba(220, 220, 220, 0.8)',
            'player_line': '#c0c0c0',
            'player_accent': '#2a6eff',
            'player_success': '#4CAF50',
            'player_warning': '#ff6464',
            'player_slider_track': '#c0c0c0',
            'player_slider_fill': '#2a6eff',
            'player_slider_handle': '#333333',
            'player_cache_bar': 'rgba(42, 110, 255, 0.35)',
            'player_volume_track': '#d0d0d0',
            'player_video_placeholder': '#e0e0e0',
            'window_opacity': 240,
            'shadow_light': 'rgba(255,255,255,0.8)',
            'shadow_dark': 'rgba(0,0,0,0.12)',
            'neumorphic_light': '#ffffff',
            'neumorphic_dark': '#d0d0d0',
        },
    }

    @classmethod
    def _style_modifier_flat(cls, colors, color_mode):
        return colors.copy()

    @classmethod
    def _style_modifier_neumorphic(cls, colors, color_mode):
        c = colors.copy()
        if color_mode == 'dark':
            c['shadow_light'] = 'rgba(100,100,160,0.5)'
            c['shadow_dark'] = 'rgba(0,0,0,0.7)'
            c['neumorphic_light'] = '#303055'
            c['neumorphic_dark'] = '#181830'
            c['window'] = '#1a1a2e'
            c['window_text'] = '#eaeaea'
            c['base'] = '#222240'
            c['alternate_base'] = '#28284a'
            c['button'] = '#28284a'
            c['light'] = '#303055'
            c['mid'] = '#3a3a60'
            c['dark'] = '#454570'
            c['highlight'] = '#2a2a50'
            c['highlighted_text'] = '#7c8aff'
            c['bright_text'] = '#eaeaea'
            c['link'] = '#7c8aff'
            c['link_visited'] = '#9580ff'
            c['tooltip_base'] = '#28284a'
            c['tooltip_text'] = '#eaeaea'
            c['placeholder'] = '#808090'
            c['accent'] = '#6b7bff'
            c['accent_hover'] = '#5b6bef'
            c['accent_pressed'] = '#4b5bdf'
            c['success'] = '#5fcf73'
            c['warning'] = '#ffaa70'
            c['error'] = '#ff6060'
            c['error_background'] = '#2a1a20'
            c['info'] = '#5090ff'
            c['table_header'] = '#28284a'
            c['table_header_gradient_start'] = '#303055'
            c['table_header_gradient_middle'] = '#28284a'
            c['table_header_gradient_end'] = '#202038'
            c['table_header_text'] = '#d0d0e0'
            c['table_header_hover'] = '#6b7bff'
            c['table_border'] = '#3a3a60'
            c['table_grid'] = '#303055'
            c['table_alternate'] = '#202038'
            c['table_hover'] = '#2a2a50'
            c['table_selection'] = '#5b6bef'
            c['player_background'] = '#16162a'
            c['player_panel'] = '#222240'
            c['player_panel_text'] = '#eaeaea'
            c['player_panel_secondary'] = '#888898'
            c['player_panel_disabled'] = '#585878'
            c['player_panel_hint'] = '#6a6a8a'
            c['player_button'] = 'rgba(40, 40, 74, 0.95)'
            c['player_combo'] = 'rgba(34, 34, 64, 0.9)'
            c['player_line'] = '#3a3a60'
            c['player_accent'] = '#7c8aff'
            c['player_slider_track'] = '#3a3a60'
            c['player_slider_fill'] = '#6b7bff'
            c['player_slider_handle'] = '#eaeaea'
            c['player_cache_bar'] = 'rgba(107, 123, 255, 0.35)'
            c['player_volume_track'] = '#303055'
            c['player_video_placeholder'] = '#16162a'
        else:
            c['shadow_light'] = 'rgba(255,255,255,0.95)'
            c['shadow_dark'] = 'rgba(163,177,198,0.7)'
            c['neumorphic_light'] = '#ecf1f9'
            c['neumorphic_dark'] = '#bec6d2'
            c['window'] = '#e0e5ec'
            c['window_text'] = '#44476a'
            c['base'] = '#e0e5ec'
            c['alternate_base'] = '#d1d9e6'
            c['button'] = '#d1d9e6'
            c['light'] = '#e0e5ec'
            c['mid'] = '#b8bec7'
            c['dark'] = '#a0a6b0'
            c['highlight'] = '#d6e4ff'
            c['highlighted_text'] = '#4a6eff'
            c['bright_text'] = '#44476a'
            c['link'] = '#4a6eff'
            c['link_visited'] = '#6a5eef'
            c['tooltip_base'] = '#e0e5ec'
            c['tooltip_text'] = '#44476a'
            c['placeholder'] = '#9ba4b5'
            c['accent'] = '#4a6eff'
            c['accent_hover'] = '#3a5eef'
            c['accent_pressed'] = '#2a4edf'
            c['success'] = '#4caf50'
            c['warning'] = '#ff9800'
            c['error'] = '#f44336'
            c['error_background'] = '#f5d0d0'
            c['info'] = '#2196f3'
            c['table_header'] = '#d1d9e6'
            c['table_header_gradient_start'] = '#e0e5ec'
            c['table_header_gradient_middle'] = '#d1d9e6'
            c['table_header_gradient_end'] = '#c8d0da'
            c['table_header_text'] = '#44476a'
            c['table_header_hover'] = '#4a6eff'
            c['table_border'] = '#b8bec7'
            c['table_grid'] = '#c8d0da'
            c['table_alternate'] = '#e8ecf2'
            c['table_hover'] = '#d6e4ff'
            c['table_selection'] = '#4a6eff'
            c['player_background'] = '#d1d9e6'
            c['player_panel'] = '#e0e5ec'
            c['player_panel_text'] = '#44476a'
            c['player_panel_secondary'] = '#5a5f7a'
            c['player_panel_disabled'] = '#8086a0'
            c['player_panel_hint'] = '#7a7f9a'
            c['player_button'] = 'rgba(209, 217, 230, 0.95)'
            c['player_combo'] = 'rgba(224, 229, 236, 0.9)'
            c['player_line'] = '#b8bec7'
            c['player_accent'] = '#4a6eff'
            c['player_slider_track'] = '#b8bec7'
            c['player_slider_fill'] = '#4a6eff'
            c['player_slider_handle'] = '#44476a'
            c['player_cache_bar'] = 'rgba(74, 110, 255, 0.3)'
            c['player_volume_track'] = '#c8d0da'
            c['player_video_placeholder'] = '#d1d9e6'
        return c

    @classmethod
    def _style_modifier_skeuomorphic(cls, colors, color_mode):
        c = colors.copy()
        if color_mode == 'dark':
            c['shadow_dark'] = 'rgba(0,0,0,0.6)'
            c['shadow_light'] = 'rgba(255,255,255,0.08)'
            c['neumorphic_light'] = '#383838'
            c['neumorphic_dark'] = '#080808'
            c['gradient_start'] = '#404040'
            c['gradient_end'] = '#2a2a2a'
            c['border_3d_light'] = 'rgba(255,255,255,0.15)'
            c['border_3d_dark'] = 'rgba(0,0,0,0.5)'
        else:
            c['shadow_dark'] = 'rgba(0,0,0,0.25)'
            c['shadow_light'] = 'rgba(255,255,255,0.9)'
            c['neumorphic_light'] = '#f0f0f0'
            c['neumorphic_dark'] = '#c8c8c8'
            c['gradient_start'] = '#e8e8e8'
            c['gradient_end'] = '#d0d0d0'
            c['border_3d_light'] = 'rgba(255,255,255,0.8)'
            c['border_3d_dark'] = 'rgba(0,0,0,0.15)'
        return c

    @classmethod
    def _style_modifier_frosted(cls, colors, color_mode):
        c = colors.copy()
        if color_mode == 'dark':
            c['window'] = 'rgba(20, 20, 20, 0.82)'
            c['base'] = 'rgba(30, 30, 30, 0.78)'
            c['alternate_base'] = 'rgba(40, 40, 40, 0.75)'
            c['button'] = 'rgba(55, 55, 55, 0.72)'
            c['player_panel'] = 'rgba(35, 35, 35, 0.78)'
            c['player_button'] = 'rgba(60, 60, 60, 0.7)'
            c['player_combo'] = 'rgba(45, 45, 45, 0.65)'
            c['player_background'] = 'rgba(26, 26, 26, 0.85)'
            c['player_slider_track'] = 'rgba(85, 85, 85, 0.6)'
            c['player_volume_track'] = 'rgba(68, 68, 68, 0.6)'
            c['player_line'] = 'rgba(85, 85, 85, 0.5)'
            c['table_alternate'] = 'rgba(26, 26, 26, 0.7)'
            c['table_header'] = 'rgba(58, 58, 58, 0.7)'
            c['tooltip_base'] = 'rgba(42, 42, 42, 0.85)'
            c['backdrop_tint'] = 'rgba(0, 0, 0, 0.3)'
            c['frosted_opacity'] = 0.78
        else:
            c['window'] = 'rgba(240, 240, 240, 0.82)'
            c['base'] = 'rgba(255, 255, 255, 0.78)'
            c['alternate_base'] = 'rgba(232, 232, 232, 0.75)'
            c['button'] = 'rgba(210, 210, 210, 0.72)'
            c['player_panel'] = 'rgba(245, 245, 245, 0.78)'
            c['player_button'] = 'rgba(200, 200, 200, 0.7)'
            c['player_combo'] = 'rgba(220, 220, 220, 0.65)'
            c['player_background'] = 'rgba(26, 26, 26, 0.85)'
            c['player_slider_track'] = 'rgba(160, 160, 160, 0.5)'
            c['player_volume_track'] = 'rgba(180, 180, 180, 0.5)'
            c['player_line'] = 'rgba(180, 180, 180, 0.4)'
            c['table_alternate'] = 'rgba(240, 240, 240, 0.7)'
            c['table_header'] = 'rgba(230, 230, 230, 0.7)'
            c['tooltip_base'] = 'rgba(252, 252, 252, 0.85)'
            c['backdrop_tint'] = 'rgba(255, 255, 255, 0.2)'
            c['frosted_opacity'] = 0.82
        return c

    @classmethod
    def _style_modifier_win11(cls, colors, color_mode):
        c = colors.copy()
        if color_mode == 'dark':
            c['window'] = '#202020'
            c['base'] = '#2d2d2d'
            c['button'] = '#383838'
            c['accent'] = '#60cdff'
            c['accent_hover'] = '#4cc2ff'
            c['accent_pressed'] = '#38b8ff'
            c['mica_color'] = '#1c1c1c'
            c['card_color'] = '#2d2d2d'
        else:
            c['window'] = '#f3f3f3'
            c['base'] = '#ffffff'
            c['button'] = '#e5e5e5'
            c['accent'] = '#005fb8'
            c['accent_hover'] = '#004e99'
            c['accent_pressed'] = '#003d75'
            c['mica_color'] = '#f9f9f9'
            c['card_color'] = '#ffffff'
        c['font_family'] = "'Segoe UI Variable', 'Segoe UI', 'Microsoft YaHei', sans-serif"
        c['border_thin'] = 'rgba(255,255,255,0.08)' if color_mode == 'dark' else 'rgba(0,0,0,0.06)'
        c['shadow_subtle'] = '0 2px 4px rgba(0,0,0,0.16)' if color_mode == 'dark' else '0 2px 4px rgba(0,0,0,0.08)'
        return c

    @classmethod
    def _style_modifier_mac(cls, colors, color_mode):
        c = colors.copy()
        if color_mode == 'dark':
            c['window'] = '#2d2d2d'
            c['base'] = '#333333'
            c['button'] = '#3e3e3e'
            c['accent'] = '#0a84ff'
            c['accent_hover'] = '#0070e0'
            c['accent_pressed'] = '#0058b0'
            c['window_text'] = '#f5f5f7'
            c['shadow_dark'] = 'rgba(0,0,0,0.3)'
            c['shadow_light'] = 'rgba(255,255,255,0.06)'
        else:
            c['window'] = '#f5f5f7'
            c['base'] = '#ffffff'
            c['button'] = '#e8e8ed'
            c['accent'] = '#0066cc'
            c['accent_hover'] = '#0055aa'
            c['accent_pressed'] = '#004488'
            c['window_text'] = '#1d1d1f'
            c['shadow_dark'] = 'rgba(0,0,0,0.1)'
            c['shadow_light'] = 'rgba(255,255,255,0.9)'
        c['font_family'] = "'SF Pro Display', 'SF Pro', 'Segoe UI', 'Microsoft YaHei', sans-serif"
        return c

    @classmethod
    def _style_modifier_ios(cls, colors, color_mode):
        c = colors.copy()
        if color_mode == 'dark':
            c['window'] = '#1c1c1e'
            c['base'] = '#2c2c2e'
            c['button'] = '#3a3a3c'
            c['accent'] = '#0a84ff'
            c['accent_hover'] = '#0070e0'
            c['accent_pressed'] = '#0058b0'
            c['window_text'] = '#f5f5f7'
            c['shadow_dark'] = 'rgba(0,0,0,0.2)'
            c['shadow_light'] = 'rgba(255,255,255,0.04)'
        else:
            c['window'] = '#f2f2f7'
            c['base'] = '#ffffff'
            c['button'] = '#e5e5ea'
            c['accent'] = '#007aff'
            c['accent_hover'] = '#0062cc'
            c['accent_pressed'] = '#004d99'
            c['window_text'] = '#1c1c1e'
            c['shadow_dark'] = 'rgba(0,0,0,0.06)'
            c['shadow_light'] = 'rgba(255,255,255,0.95)'
        c['font_family'] = "'SF Pro Display', 'SF Pro', 'Segoe UI', 'Microsoft YaHei', sans-serif"
        return c

    STYLE_MODIFIERS = {
        'flat': _style_modifier_flat,
        'neumorphic': _style_modifier_neumorphic,
        'skeuomorphic': _style_modifier_skeuomorphic,
        'frosted': _style_modifier_frosted,
        'win11': _style_modifier_win11,
        'mac': _style_modifier_mac,
        'ios': _style_modifier_ios,
    }

    THEME_COLORS = COLOR_PALETTES

    @classmethod
    def _detect_system_color_mode(cls):
        try:
            import ctypes
            registry = ctypes.windll.advapi32
            key = ctypes.c_ulong()
            access = 0x20019
            result = registry.RegOpenKeyExW(0x80000001, r'Software\Microsoft\Windows\CurrentVersion\Themes\Personalize', 0, access, ctypes.byref(key))
            if result == 0:
                value = ctypes.c_ulong()
                size = ctypes.c_ulong(4)
                registry.RegQueryValueExW(key.value, 'AppsUseLightTheme', 0, None, ctypes.byref(value), ctypes.byref(size))
                registry.RegCloseKey(key.value)
                return 'light' if value.value == 1 else 'dark'
        except Exception:
            pass
        try:
            from PyQt6.QtCore import QCoreApplication
            palette = QCoreApplication.instance().palette() if QCoreApplication.instance() else None
            if palette:
                from PyQt6.QtGui import QPalette
                window_bg = palette.color(QPalette.ColorRole.Window)
                text_color = palette.color(QPalette.ColorRole.WindowText)
                if text_color.lightness() > window_bg.lightness():
                    return 'dark'
                return 'light'
        except Exception:
            pass
        return 'dark'

    @classmethod
    def _get_effective_color_mode(cls):
        if cls._color_mode == 'auto':
            return cls._detect_system_color_mode()
        return cls._color_mode

    @classmethod
    def _get_colors(cls):
        effective_mode = cls._get_effective_color_mode()
        base_colors = cls.COLOR_PALETTES.get(effective_mode, cls.COLOR_PALETTES['dark'])
        style = cls._visual_style
        if style == 'neumorphic':
            return cls._style_modifier_neumorphic(base_colors.copy(), effective_mode)
        elif style == 'skeuomorphic':
            return cls._style_modifier_skeuomorphic(base_colors.copy(), effective_mode)
        elif style == 'frosted':
            return cls._style_modifier_frosted(base_colors.copy(), effective_mode)
        elif style == 'win11':
            return cls._style_modifier_win11(base_colors.copy(), effective_mode)
        elif style == 'mac':
            return cls._style_modifier_mac(base_colors.copy(), effective_mode)
        elif style == 'ios':
            return cls._style_modifier_ios(base_colors.copy(), effective_mode)
        return base_colors.copy()

    COLOR_KEYS = frozenset({
        'accent', 'window', 'window_text', 'base', 'alternate_base',
        'button', 'button_text', 'button_hover', 'button_pressed',
        'light', 'mid', 'dark', 'shadow_dark', 'shadow_light',
        'neumorphic_light', 'neumorphic_dark', 'midlight',
        'highlight', 'highlighted_text', 'tooltip_base', 'tooltip_text',
        'table_alternate', 'border', 'border_focus', 'text',
        'disabled_text', 'bright_text',
    })

    @classmethod
    def set_theme(cls, theme_name):
        if '+' in theme_name:
            parts = theme_name.split('+')
            if len(parts) == 2:
                cls._color_mode = parts[0]
                cls._visual_style = parts[1]
                cls._current_theme = theme_name
                return
        mapping = cls._OLD_THEME_MAPPING.get(theme_name)
        if mapping:
            cls._color_mode, cls._visual_style = mapping
        else:
            cls._color_mode = theme_name
            cls._visual_style = 'flat'
        cls._current_theme = f"{cls._color_mode}+{cls._visual_style}"

    @classmethod
    def set_color_mode(cls, mode):
        if mode in cls.AVAILABLE_COLOR_MODES:
            cls._color_mode = mode
            cls._current_theme = f"{cls._color_mode}+{cls._visual_style}"

    @classmethod
    def set_visual_style(cls, style):
        if style in cls.AVAILABLE_VISUAL_STYLES:
            cls._visual_style = style
            cls._current_theme = f"{cls._color_mode}+{cls._visual_style}"

    @staticmethod
    def get_theme():
        return AppStyles._current_theme

    @classmethod
    def get_color_mode(cls):
        return cls._color_mode

    @classmethod
    def get_visual_style(cls):
        return cls._visual_style

    @classmethod
    def is_style(cls, style_name):
        return cls._visual_style == style_name

    @staticmethod
    def get_available_themes():
        return list(AppStyles._OLD_THEME_MAPPING.keys()) + [f"{m}+{s}" for m in ('dark', 'light') for s in AppStyles.AVAILABLE_VISUAL_STYLES]

    @staticmethod
    def is_neumorphic():
        return AppStyles._visual_style == 'neumorphic'

    @classmethod
    def _get_style_border_radius(cls):
        radii = {
            'flat': 4,
            'neumorphic': 10,
            'skeuomorphic': 6,
            'frosted': 12,
            'win11': 8,
            'mac': 10,
            'ios': 14,
        }
        return radii.get(cls._visual_style, 4)

    @classmethod
    def _get_style_shadow(cls):
        c = cls._get_colors()
        effective = cls._get_effective_color_mode()
        shadows = {
            'flat': f"0 1px 3px {c['shadow_dark']}",
            'neumorphic': f"4px 4px 8px {c['shadow_dark']}, -4px -4px 8px {c['shadow_light']}",
            'skeuomorphic': f"2px 2px 6px {c.get('shadow_dark', 'rgba(0,0,0,0.3)')}, -1px -1px 3px {c.get('shadow_light', 'rgba(255,255,255,0.1)')}",
            'frosted': f"0 4px 16px {c.get('shadow_dark', 'rgba(0,0,0,0.2)')}",
            'win11': f"0 2px 4px {c.get('shadow_dark', 'rgba(0,0,0,0.16)')}",
            'mac': f"0 1px 4px {c.get('shadow_dark', 'rgba(0,0,0,0.1)')}, 0 0 0 0.5px {c.get('border_thin', 'rgba(0,0,0,0.04)')}",
            'ios': f"0 1px 3px {c.get('shadow_dark', 'rgba(0,0,0,0.06)')}",
        }
        return shadows.get(cls._visual_style, f"0 1px 3px {c['shadow_dark']}")

    @classmethod
    def _get_style_inset(cls):
        c = cls._get_colors()
        if cls._visual_style == 'neumorphic':
            return (
                f"border: 2px solid;"
                f"border-top-color: {c['shadow_dark']};"
                f"border-left-color: {c['shadow_dark']};"
                f"border-bottom-color: {c['shadow_light']};"
                f"border-right-color: {c['shadow_light']};"
            )
        if cls._visual_style == 'skeuomorphic':
            return (
                f"border: 2px solid;"
                f"border-top-color: {c.get('border_3d_dark', c['shadow_dark'])};"
                f"border-left-color: {c.get('border_3d_dark', c['shadow_dark'])};"
                f"border-bottom-color: {c.get('border_3d_light', c['shadow_light'])};"
                f"border-right-color: {c.get('border_3d_light', c['shadow_light'])};"
            )
        return f"border: 1px solid {c.get('mid', '#555')};"

    @classmethod
    def _get_style_raised(cls):
        c = cls._get_colors()
        if cls._visual_style == 'neumorphic':
            return (
                f"border: 2px solid;"
                f"border-top-color: {c['shadow_light']};"
                f"border-left-color: {c['shadow_light']};"
                f"border-bottom-color: {c['shadow_dark']};"
                f"border-right-color: {c['shadow_dark']};"
            )
        if cls._visual_style == 'skeuomorphic':
            return (
                f"border: 2px solid;"
                f"border-top-color: {c.get('border_3d_light', c['shadow_light'])};"
                f"border-left-color: {c.get('border_3d_light', c['shadow_light'])};"
                f"border-bottom-color: {c.get('border_3d_dark', c['shadow_dark'])};"
                f"border-right-color: {c.get('border_3d_dark', c['shadow_dark'])};"
            )
        return f"border: 1px solid {c.get('mid', '#555')};"

    @staticmethod
    def _neumorphic_inset():
        return AppStyles._get_style_inset()

    @staticmethod
    def _neumorphic_raised():
        return AppStyles._get_style_raised()

    @classmethod
    def _get_style_font_family(cls):
        fonts = {
            'win11': "'Segoe UI Variable', 'Segoe UI', 'Microsoft YaHei', sans-serif",
            'mac': "'SF Pro Display', 'Helvetica Neue', 'Segoe UI', 'Microsoft YaHei', sans-serif",
            'ios': "'SF Pro Display', 'Helvetica Neue', 'Segoe UI', 'Microsoft YaHei', sans-serif",
        }
        return fonts.get(cls._visual_style, "'Segoe UI', 'Microsoft YaHei', sans-serif")

    @classmethod
    def _style_btn_decoration(cls, colors, hover=False, pressed=False, disabled=False, accent_color=None):
        c = colors
        style = cls._visual_style
        r = cls._get_style_border_radius()
        ac = accent_color or c['accent']
        if disabled:
            if style in ('neumorphic',):
                return f"background-color: {c['light']}; border: 1px solid {c['mid']}; border-radius: {r}px; color: {c['placeholder']};"
            return f"background-color: {c['light']}; border-color: {c['mid']}; color: {c['placeholder']};"
        if pressed:
            if style == 'neumorphic':
                return f"background-color: {c['neumorphic_dark']}; {cls._get_style_inset()} border-radius: {r}px;"
            elif style == 'skeuomorphic':
                return f"background-color: {c.get('gradient_end', c['dark'])}; border: 2px inset {c.get('border_3d_dark', c['mid'])}; border-radius: {r}px;"
            elif style == 'frosted':
                return f"background-color: {c['dark']}; border: 1px solid rgba(255,255,255,0.15); border-radius: {r}px;"
            elif style == 'win11':
                return f"background-color: {c['dark']}; border: 1px solid {c.get('border_thin', c['mid'])}; border-radius: {r}px;"
            elif style == 'mac':
                return f"background-color: {c['dark']}; border: none; border-radius: {r}px;"
            elif style == 'ios':
                return f"background-color: {c['dark']}; border: none; border-radius: {r}px;"
            return f"background-color: {c['dark']}; border-color: {c.get('accent_pressed', ac)};"
        if hover:
            if style == 'neumorphic':
                return f"background-color: {c['neumorphic_dark']}; border: 2px solid {ac}; border-radius: {r}px;"
            elif style == 'skeuomorphic':
                return f"background-color: {c.get('gradient_start', c['light'])}; border: 2px outset {ac}; border-radius: {r}px;"
            elif style == 'frosted':
                return f"background-color: {c['light']}; border: 1px solid rgba(255,255,255,0.2); border-radius: {r}px;"
            elif style == 'win11':
                return f"background-color: {c['light']}; border: 1px solid {ac}; border-radius: {r}px;"
            elif style == 'mac':
                return f"background-color: {c['light']}; border: none; border-radius: {r}px;"
            elif style == 'ios':
                return f"background-color: {c['light']}; border: none; border-radius: {r}px;"
            return f"background-color: {c['light']}; border-color: {ac};"
        if style == 'neumorphic':
            return f"background-color: {c['neumorphic_light']}; {cls._get_style_raised()} border-radius: {r}px;"
        elif style == 'skeuomorphic':
            return f"background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {c.get('gradient_start', c['light'])}, stop:1 {c['button']}); border: 2px outset {c.get('border_3d_light', c['mid'])}; border-radius: {r}px;"
        elif style == 'frosted':
            return f"background-color: {c['button']}; border: 1px solid rgba(255,255,255,0.1); border-radius: {r}px;"
        elif style == 'win11':
            return f"background-color: {c['button']}; border: 1px solid {c.get('border_thin', c['mid'])}; border-radius: {r}px;"
        elif style == 'mac':
            return f"background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {c['light']}, stop:0.95 {c['button']}, stop:1 {c['dark']}); border: none; border-radius: {r}px;"
        elif style == 'ios':
            return f"background-color: {c['button']}; border: none; border-radius: {r}px;"
        return f"background-color: {c['button']}; border: 1px solid {c['mid']}; border-radius: {r}px;"

    @classmethod
    def _style_input_decoration(cls, colors, focus=False, disabled=False):
        c = colors
        style = cls._visual_style
        r = cls._get_style_border_radius()
        if disabled:
            return f"background-color: {c['light']}; border: 1px solid {c['mid']}; border-radius: {r}px; color: {c['placeholder']};"
        if focus:
            if style == 'neumorphic':
                return f"border: 2px solid {c['accent']}; border-radius: {r}px; outline: none;"
            elif style == 'skeuomorphic':
                return f"border: 2px solid {c['accent']}; border-radius: {r}px; outline: none;"
            return f"border-color: {c['accent']}; outline: none;"
        if style == 'neumorphic':
            return f"background-color: {c['neumorphic_light']}; {cls._get_style_inset()} border-radius: {r}px;"
        elif style == 'skeuomorphic':
            return f"background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {c.get('gradient_start', c['light'])}, stop:1 {c['alternate_base']}); border: 2px inset {c.get('border_3d_dark', c['mid'])}; border-radius: {r}px;"
        elif style == 'frosted':
            return f"background-color: {c['alternate_base']}; border: 1px solid rgba(255,255,255,0.1); border-radius: {r}px;"
        elif style == 'win11':
            return f"background-color: {c['alternate_base']}; border: 1px solid {c.get('border_thin', c['mid'])}; border-radius: {r}px; border-bottom: 2px solid {c['accent']};"
        elif style == 'mac':
            return f"background-color: {c['alternate_base']}; border: none; border-radius: {r}px;"
        elif style == 'ios':
            return f"background-color: {c['alternate_base']}; border: none; border-radius: {r}px;"
        return f"background-color: {c['alternate_base']}; border: 1px solid {c['mid']}; border-radius: {r}px;"

    @classmethod
    def _style_group_decoration(cls, colors):
        c = colors
        style = cls._visual_style
        r = cls._get_style_border_radius()
        if style == 'neumorphic':
            return f"background-color: {c['alternate_base']}; border: none; border-radius: {r}px; {cls._get_style_raised()}"
        elif style == 'skeuomorphic':
            return f"background-color: {c['alternate_base']}; border: 2px outset {c.get('border_3d_light', c['mid'])}; border-radius: {r}px;"
        elif style == 'frosted':
            return f"background-color: {c['alternate_base']}; border: 1px solid rgba(255,255,255,0.1); border-radius: {r}px;"
        elif style == 'win11':
            return f"background-color: {c.get('card_color', c['alternate_base'])}; border: 1px solid {c.get('border_thin', c['mid'])}; border-radius: {r}px;"
        elif style == 'mac':
            return f"background-color: {c['alternate_base']}; border: none; border-radius: {r}px;"
        elif style == 'ios':
            return f"background-color: {c['alternate_base']}; border: none; border-radius: {r}px;"
        return f"background-color: {c['alternate_base']}; border: 1px solid {c['mid']}; border-radius: {r}px;"

    @classmethod
    def _style_menu_decoration(cls, colors):
        c = colors
        style = cls._visual_style
        if style == 'neumorphic':
            return f"background-color: {c['base']}; padding: 4px; border: 2px solid; border-top-color: {c['shadow_light']}; border-left-color: {c['shadow_light']}; border-bottom-color: {c['shadow_dark']}; border-right-color: {c['shadow_dark']};"
        elif style == 'skeuomorphic':
            return f"background-color: {c['base']}; padding: 4px; border: 2px outset {c.get('border_3d_light', c['mid'])};"
        elif style == 'frosted':
            return f"background-color: {c['base']}; padding: 4px; border: 1px solid rgba(255,255,255,0.1);"
        elif style == 'win11':
            return f"background-color: {c['base']}; padding: 4px; border: 1px solid {c.get('border_thin', c['mid'])};"
        elif style == 'mac':
            return f"background-color: {c['base']}; padding: 4px; border: none;"
        elif style == 'ios':
            return f"background-color: {c['base']}; padding: 4px; border: none;"
        return f"background-color: {c['base']}; padding: 2px; border: 1px solid {c['mid']};"

    @classmethod
    def _style_padding(cls, widget_type='button'):
        style = cls._visual_style
        if widget_type == 'button':
            pads = {'win11': '8px 16px', 'ios': '10px 20px', 'mac': '8px 16px'}
            return pads.get(style, '6px 12px')
        elif widget_type == 'input':
            pads = {'win11': '8px 12px', 'ios': '10px 14px', 'mac': '8px 12px'}
            return pads.get(style, '6px')
        return '6px 12px'

    @classmethod
    def _style_slider_decoration(cls, colors):
        c = colors
        style = cls._visual_style
        r = cls._get_style_border_radius()
        groove_h = 6 if style in ('neumorphic', 'skeuomorphic') else 4
        handle_size = 14 if style in ('neumorphic', 'skeuomorphic', 'ios') else 10
        handle_margin = -((handle_size - groove_h) // 2)
        if style == 'neumorphic':
            groove = f"background: {c['neumorphic_light']}; height: {groove_h}px; {cls._get_style_inset()} border-radius: {r}px;"
            handle = f"background: {c['neumorphic_light']}; width: {handle_size}px; height: {handle_size}px; {cls._get_style_raised()} border-radius: {handle_size // 2}px; margin: {handle_margin}px 0;"
        elif style == 'skeuomorphic':
            groove = f"background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {c.get('gradient_start', c['light'])}, stop:1 {c.get('gradient_end', c['dark'])}); height: {groove_h}px; border: 1px inset {c.get('border_3d_dark', c['mid'])}; border-radius: {r}px;"
            handle = f"background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {c.get('gradient_start', c['light'])}, stop:1 {c['button']}); width: {handle_size}px; height: {handle_size}px; border: 2px outset {c.get('border_3d_light', c['mid'])}; border-radius: {handle_size // 2}px; margin: {handle_margin}px 0;"
        elif style == 'frosted':
            groove = f"background: {c['player_slider_track']}; height: {groove_h}px; border: 1px solid rgba(255,255,255,0.1); border-radius: {r}px;"
            handle = f"background: {c['player_slider_handle']}; width: {handle_size}px; height: {handle_size}px; border: 1px solid rgba(255,255,255,0.2); border-radius: {handle_size // 2}px; margin: {handle_margin}px 0;"
        elif style == 'win11':
            groove = f"background: {c['player_slider_track']}; height: {groove_h}px; border: none; border-radius: {r}px;"
            handle = f"background: {c['accent']}; width: {handle_size}px; height: {handle_size}px; border: none; border-radius: {handle_size // 2}px; margin: {handle_margin}px 0;"
        elif style == 'mac':
            groove = f"background: {c['player_slider_track']}; height: {groove_h}px; border: none; border-radius: {r}px;"
            handle = f"background: {c['player_slider_handle']}; width: {handle_size}px; height: {handle_size}px; border: none; border-radius: {handle_size // 2}px; margin: {handle_margin}px 0;"
        elif style == 'ios':
            groove = f"background: {c['player_slider_track']}; height: {groove_h}px; border: none; border-radius: {r}px;"
            handle = f"background: white; width: {handle_size}px; height: {handle_size}px; border: 1px solid rgba(0,0,0,0.15); border-radius: {handle_size // 2}px; margin: {handle_margin}px 0;"
        else:
            groove = f"background: {c['player_slider_track']}; height: {groove_h}px; border-radius: 2px;"
            handle = f"background: {c['player_slider_handle']}; width: {handle_size}px; height: {handle_size}px; border-radius: {handle_size // 2}px; margin: {handle_margin}px 0;"
        sub_page = f"background: {c['player_slider_fill']}; height: {groove_h}px; border-radius: 2px;"
        return groove, sub_page, handle

    @classmethod
    def _style_progress_decoration(cls, colors):
        c = colors
        style = cls._visual_style
        r = cls._get_style_border_radius()
        if style == 'neumorphic':
            return (
                f"background-color: {c['neumorphic_light']}; {cls._get_style_inset()} border-radius: {r}px;",
                f"background-color: {c['accent']}; border-radius: {r}px;"
            )
        elif style == 'skeuomorphic':
            return (
                f"background-color: {c.get('gradient_start', c['light'])}; border: 1px inset {c.get('border_3d_dark', c['mid'])}; border-radius: {r}px;",
                f"background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {c['accent']}, stop:1 {c.get('accent_pressed', c['dark'])}); border-radius: {r}px;"
            )
        elif style == 'frosted':
            return (
                f"background-color: {c['alternate_base']}; border: 1px solid rgba(255,255,255,0.1); border-radius: {r}px;",
                f"background-color: {c['accent']}; border-radius: {r}px;"
            )
        elif style == 'win11':
            return (
                f"background-color: {c.get('card_color', c['alternate_base'])}; border: 1px solid {c.get('border_thin', c['mid'])}; border-radius: {r}px;",
                f"background-color: {c['accent']}; border-radius: {r}px;"
            )
        elif style in ('mac', 'ios'):
            return (
                f"background-color: {c['alternate_base']}; border: none; border-radius: {r}px;",
                f"background-color: {c['accent']}; border-radius: {r}px;"
            )
        return (
            f"background-color: {c['alternate_base']}; border-radius: {r}px;",
            f"background-color: {c['accent']}; border-radius: {r}px;"
        )

    @classmethod
    def _style_scrollbar_decoration(cls, colors):
        c = colors
        style = cls._visual_style
        r = cls._get_style_border_radius()
        if style == 'neumorphic':
            return (
                f"background-color: {c['neumorphic_light']}; width: 10px; border: none;",
                f"background-color: {c['neumorphic_light']}; {cls._get_style_raised()} border-radius: 5px; min-height: 40px; margin: 2px;",
                f"background-color: {c['neumorphic_dark']}; {cls._get_style_inset()} border-radius: 5px; min-height: 40px; margin: 2px;"
            )
        elif style == 'skeuomorphic':
            return (
                f"background-color: {c['alternate_base']}; width: 10px; border: 1px solid {c.get('border_3d_dark', c['mid'])};",
                f"background-color: {c['button']}; border: 1px outset {c.get('border_3d_light', c['mid'])}; border-radius: 5px; min-height: 40px; margin: 2px;",
                f"background-color: {c['dark']}; border: 1px inset {c.get('border_3d_dark', c['mid'])}; border-radius: 5px; min-height: 40px; margin: 2px;"
            )
        elif style == 'frosted':
            return (
                f"background-color: transparent; width: 10px; border: none;",
                f"background-color: rgba(255,255,255,0.15); border: 1px solid rgba(255,255,255,0.1); border-radius: 5px; min-height: 40px; margin: 2px;",
                f"background-color: rgba(255,255,255,0.25); border: 1px solid rgba(255,255,255,0.15); border-radius: 5px; min-height: 40px; margin: 2px;"
            )
        elif style == 'win11':
            return (
                f"background-color: transparent; width: 10px; border: none;",
                f"background-color: {c.get('border_thin', c['mid'])}; border: none; border-radius: 5px; min-height: 40px; margin: 2px;",
                f"background-color: {c['mid']}; border: none; border-radius: 5px; min-height: 40px; margin: 2px;"
            )
        elif style in ('mac', 'ios'):
            return (
                f"background-color: transparent; width: 8px; border: none;",
                f"background-color: {c['mid']}; border: none; border-radius: 4px; min-height: 30px; margin: 2px;",
                f"background-color: {c['accent']}; border: none; border-radius: 4px; min-height: 30px; margin: 2px;"
            )
        return (
            f"background-color: {c['alternate_base']}; width: 10px; border: none;",
            f"background-color: {c['mid']}; border-radius: 5px; min-height: 40px; margin: 2px;",
            f"background-color: {c['accent']}; border-radius: 6px; min-height: 40px; margin: 2px;"
        )

    @classmethod
    def _style_checkbox_indicator_decoration(cls, colors, checked=False):
        c = colors
        style = cls._visual_style
        r = cls._get_style_border_radius()
        indicator_r = max(r - 4, 3)
        if style == 'neumorphic':
            bg = c['accent'] if checked else c['neumorphic_light']
            border = f"border: 2px solid {c['accent']};" if checked else cls._get_style_inset()
            return f"background-color: {bg}; {border} border-radius: {indicator_r}px;"
        elif style == 'skeuomorphic':
            bg = c['accent'] if checked else c.get('gradient_start', c['light'])
            border = f"border: 2px solid {c['accent']};" if checked else f"border: 2px inset {c.get('border_3d_dark', c['mid'])};"
            return f"background-color: {bg}; {border} border-radius: {indicator_r}px;"
        elif style == 'frosted':
            bg = c['accent'] if checked else c['alternate_base']
            border = f"border: 1px solid {c['accent']};" if checked else "border: 1px solid rgba(255,255,255,0.1);"
            return f"background-color: {bg}; {border} border-radius: {indicator_r}px;"
        elif style == 'win11':
            bg = c['accent'] if checked else c['alternate_base']
            border = f"border: 1px solid {c['accent']};" if checked else f"border: 1px solid {c.get('border_thin', c['mid'])};"
            return f"background-color: {bg}; {border} border-radius: {indicator_r}px;"
        elif style in ('mac', 'ios'):
            bg = c['accent'] if checked else c['alternate_base']
            border = f"border: none;" if not checked else "border: none;"
            return f"background-color: {bg}; {border} border-radius: {indicator_r}px;"
        bg = c['accent'] if checked else c['alternate_base']
        border = f"border: 2px solid {c['accent']};" if checked else f"border: 2px solid {c['mid']};"
        return f"background-color: {bg}; {border} border-radius: {indicator_r}px;"

    @classmethod
    def _style_dock_title_decoration(cls, colors):
        c = colors
        style = cls._visual_style
        r = cls._get_style_border_radius()
        if style == 'neumorphic':
            return f"background-color: {c['base']}; {cls._get_style_raised()} border-radius: {r}px; padding: 6px;"
        elif style == 'skeuomorphic':
            return f"background-color: {c['base']}; border: 2px outset {c.get('border_3d_light', c['mid'])}; border-radius: {r}px; padding: 4px;"
        elif style == 'frosted':
            return f"background-color: {c['base']}; border: 1px solid rgba(255,255,255,0.1); border-radius: {r}px; padding: 4px;"
        elif style == 'win11':
            return f"background-color: {c.get('card_color', c['base'])}; border: none; border-bottom: 1px solid {c.get('border_thin', c['mid'])}; border-radius: {r}px; padding: 4px;"
        elif style in ('mac', 'ios'):
            return f"background-color: {c['base']}; border: none; border-radius: {r}px; padding: 6px;"
        return f"background-color: {c['base']}; border: none; padding: 4px;"

    @classmethod
    def _style_tooltip_decoration(cls, colors):
        c = colors
        style = cls._visual_style
        r = cls._get_style_border_radius()
        if style == 'neumorphic':
            return f"background-color: {c.get('tooltip_base', c['base'])}; {cls._get_style_raised()} border-radius: {r}px; padding: 6px;"
        elif style == 'skeuomorphic':
            return f"background-color: {c.get('tooltip_base', c['base'])}; border: 2px outset {c.get('border_3d_light', c['mid'])}; border-radius: {r}px; padding: 4px;"
        elif style == 'frosted':
            return f"background-color: {c.get('tooltip_base', c['base'])}; border: 1px solid rgba(255,255,255,0.15); border-radius: {r}px; padding: 6px;"
        elif style == 'win11':
            return f"background-color: {c.get('card_color', c['base'])}; border: 1px solid {c.get('border_thin', c['mid'])}; border-radius: {r}px; padding: 6px;"
        elif style in ('mac', 'ios'):
            return f"background-color: {c.get('tooltip_base', c['base'])}; border: none; border-radius: {r}px; padding: 6px;"
        return f"background-color: {c.get('tooltip_base', c['base'])}; border: 1px solid {c['mid']}; padding: 4px;"

    @staticmethod
    def main_window_style() -> str:
        colors = AppStyles._get_colors()
        r = AppStyles._get_style_border_radius()
        ff = AppStyles._get_style_font_family()
        style = AppStyles._visual_style
        if style == 'frosted':
            mw_colors = {}
            for k, v in colors.items():
                mw_colors[k] = color_to_hex(v) if isinstance(v, str) and v.startswith('rgba') else v
        else:
            mw_colors = colors
        container_bg = mw_colors['window']
        content_bg = mw_colors.get('player_background', mw_colors['window'])
        input_bg = mw_colors.get('input_bg', mw_colors['alternate_base'])
        dock_bg = mw_colors.get('dock_bg', mw_colors['base'])
        tooltip_bg = mw_colors.get('tooltip_base', mw_colors['base'])
        grp_dec = AppStyles._style_group_decoration(mw_colors)
        inp_dec = AppStyles._style_input_decoration(mw_colors)
        btn_dec = AppStyles._style_btn_decoration(mw_colors)
        btn_dec_hover = AppStyles._style_btn_decoration(mw_colors, hover=True)
        btn_dec_pressed = AppStyles._style_btn_decoration(mw_colors, pressed=True)
        container_border = "none" if style in ('neumorphic', 'mac', 'ios') else f"1px solid {mw_colors['mid']}"
        spinbox_border = AppStyles._style_input_decoration(mw_colors)
        spinbox_focus = AppStyles._style_input_decoration(mw_colors, focus=True)
        slider_groove, slider_sub_page, slider_handle = AppStyles._style_slider_decoration(mw_colors)
        progress_bg, progress_chunk = AppStyles._style_progress_decoration(mw_colors)
        sb_track_v, sb_handle_v, sb_handle_v_hover = AppStyles._style_scrollbar_decoration(mw_colors)
        sb_track_h = sb_track_v.replace('width: 10px', 'height: 10px').replace('border: none;', 'border: none;')
        sb_handle_h = sb_handle_v.replace('min-height: 40px', 'min-width: 40px').replace('margin: 2px;', 'margin: 2px;')
        sb_handle_h_hover = sb_handle_v_hover.replace('min-height: 40px', 'min-width: 40px').replace('margin: 2px;', 'margin: 2px;')
        sb_handle_h_pressed = sb_handle_h_hover
        chk_indicator = AppStyles._style_checkbox_indicator_decoration(mw_colors)
        chk_indicator_checked = AppStyles._style_checkbox_indicator_decoration(mw_colors, checked=True)
        dock_title_dec = AppStyles._style_dock_title_decoration(mw_colors)
        tooltip_dec = AppStyles._style_tooltip_decoration(mw_colors)
        return f"""
            QMainWindow {{
                background-color: transparent;
                color: {mw_colors['window_text']};
                font-family: {ff};
                font-size: 13px;
            }}
            QWidget#mainContainer {{
                background-color: {container_bg};
                border-radius: {r}px;
                border: {container_border};
            }}
            QWidget#contentArea {{
                background-color: {content_bg};
                border-bottom-left-radius: {r}px;
                border-bottom-right-radius: {r}px;
            }}
            QLabel {{
                color: {mw_colors['window_text']};
                background-color: transparent;
                font-family: {ff};
            }}
            QPushButton {{
                color: {mw_colors['window_text']};
                padding: 6px 12px;
                font-weight: 500;
                font-size: 12px;
                font-family: {ff};
                {btn_dec}
            }}
            QPushButton:hover {{
                color: {mw_colors['window_text']};
                {btn_dec_hover}
            }}
            QPushButton:pressed {{
                color: {mw_colors['window_text']};
                {btn_dec_pressed}
            }}
            QPushButton:disabled {{
                background-color: {mw_colors['light']};
                color: {mw_colors['placeholder']};
            }}
            QLineEdit {{
                color: {mw_colors['window_text']};
                padding: 6px;
                font-size: 12px;
                font-family: {ff};
                {inp_dec}
            }}
            QLineEdit:focus {{
                border-color: {mw_colors['accent']};
                outline: none;
            }}
            QComboBox {{
                color: {mw_colors['window_text']};
                padding: 6px;
                font-size: 12px;
                font-family: {ff};
                {inp_dec}
            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: center right;
                width: 20px;
                border: none;
            }}
            QComboBox::down-arrow {{
                image: url({AppStyles._get_arrow_image(mw_colors['window_text'])});
                width: 10px;
                height: 6px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {mw_colors['base']};
                color: {mw_colors['window_text']};
                selection-background-color: {mw_colors['accent']};
                selection-color: {AppStyles.COLOR_WHITE};
                border: 1px solid {mw_colors['mid']};
                outline: none;
            }}
            QTableView {{
                background-color: {mw_colors['alternate_base']};
                alternate-background-color: {mw_colors['table_alternate']};
                selection-background-color: {mw_colors['table_selection']};
                selection-color: {mw_colors['table_selection_text']};
                gridline-color: {mw_colors['table_grid']};
                color: {mw_colors['window_text']};
                font-size: 12px;
                font-family: {ff};
            }}
            QTableView::item {{
                padding: 6px 10px;
                color: {mw_colors['window_text']};
            }}
            QTableView::item:hover {{
                background-color: {mw_colors['table_hover']};
            }}
            QTableView::item:selected {{
                background-color: {mw_colors['table_selection']};
                color: {mw_colors['table_selection_text']};
            }}
            QHeaderView {{
                background-color: {mw_colors['table_header']};
            }}
            QHeaderView::section {{
                background-color: {mw_colors['table_header']};
                color: {mw_colors['window_text']};
                padding: 8px 12px;
                font-weight: 600;
                font-size: 12px;
                font-family: {ff};
                border: none;
                border-right: 1px solid {mw_colors['mid']};
            }}
            QListWidget {{
                background-color: {mw_colors['alternate_base']};
                color: {mw_colors['window_text']};
                font-family: {ff};
                outline: none;
            }}
            QListWidget::item {{
                padding: 4px 8px;
                color: {mw_colors['window_text']};
            }}
            QListWidget::item:hover {{
                background-color: {mw_colors['highlight']};
            }}
            QListWidget::item:selected {{
                background-color: {mw_colors['accent']};
                color: {AppStyles.COLOR_WHITE};
            }}
            QTextEdit {{
                background-color: {input_bg};
                color: {mw_colors['window_text']};
                font-family: {ff};
            }}
            QToolButton {{
                color: {mw_colors['window_text']};
                font-family: {ff};
            }}
            QSlider::groove:horizontal {{
                {slider_groove}
            }}
            QSlider::sub-page:horizontal {{
                {slider_sub_page}
            }}
            QSlider::handle:horizontal {{
                {slider_handle}
            }}
            QDockWidget {{
                color: {mw_colors['window_text']};
                font-family: {ff};
            }}
            QDockWidget::title {{
                {dock_title_dec}
                color: {mw_colors['window_text']};
            }}
            QToolTip {{
                {tooltip_dec}
                color: {mw_colors.get('tooltip_text', mw_colors['window_text'])};
                font-family: {ff};
            }}
            QGroupBox {{
                margin-top: 12px;
                padding-top: 16px;
                font-weight: 600;
                font-size: 13px;
                color: {mw_colors['window_text']};
                font-family: {ff};
                {grp_dec}
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
                color: {mw_colors['window_text']};
                font-weight: 600;
            }}
            QSplitter::handle {{
                background-color: {mw_colors['mid']};
            }}
            QSplitter::handle:hover {{
                background-color: {mw_colors['highlight']};
            }}
            QCheckBox {{
                color: {mw_colors['window_text']};
                font-size: 13px;
                font-family: {ff};
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 16px; height: 16px;
                {chk_indicator}
            }}
            QCheckBox::indicator:checked {{
                {chk_indicator_checked}
                image: url({AppStyles._get_check_image(AppStyles.COLOR_WHITE)});
            }}
            QCheckBox::indicator:hover {{
                border: 2px solid {mw_colors['accent']};
            }}
            QRadioButton {{
                color: {mw_colors['window_text']};
                font-family: {ff};
                spacing: 8px;
            }}
            QRadioButton::indicator {{
                width: 14px; height: 14px;
                {chk_indicator}
            }}
            QRadioButton::indicator:checked {{
                {chk_indicator_checked}
            }}
            QProgressBar {{
                {progress_bg}
                color: {mw_colors['window_text']};
                text-align: center;
                font-family: {ff};
                min-height: 8px;
            }}
            QProgressBar::chunk {{
                {progress_chunk}
            }}
            QSpinBox {{
                padding: 6px 10px;
                padding-right: 32px;
                font-size: 13px;
                color: {mw_colors['window_text']};
                {spinbox_border}
            }}
            QSpinBox:focus {{
                {spinbox_focus}
            }}
            QSpinBox::up-button, QSpinBox::down-button {{
                width: 28px;
                border: none;
                border-left: 1px solid {mw_colors['mid']};
                background-color: {mw_colors['button']};
                min-width: 0;
                min-height: 0;
                padding: 0;
            }}
            QSpinBox::up-button {{
                subcontrol-origin: border;
                subcontrol-position: right top;
                border-top-right-radius: {r}px;
            }}
            QSpinBox::down-button {{
                subcontrol-origin: border;
                subcontrol-position: right bottom;
                border-bottom-right-radius: {r}px;
            }}
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
                background-color: {mw_colors['accent']};
            }}
            QSpinBox::up-button:pressed, QSpinBox::down-button:pressed {{
                background-color: {mw_colors['accent_pressed']};
            }}
            QSpinBox::up-arrow {{
                image: url({AppStyles._get_spin_up_image(mw_colors['window_text'])});
                width: 10px;
                height: 6px;
            }}
            QSpinBox::down-arrow {{
                image: url({AppStyles._get_spin_down_image(mw_colors['window_text'])});
                width: 10px;
                height: 6px;
            }}
            QSpinBox::up-button:hover::up-arrow {{
                image: url({AppStyles._get_spin_up_image(mw_colors['accent'])});
            }}
            QSpinBox::down-button:hover::down-arrow {{
                image: url({AppStyles._get_spin_down_image(mw_colors['accent'])});
            }}
            QScrollBar:vertical {{
                {sb_track_v}
                margin: 2px 0;
            }}
            QScrollBar::handle:vertical {{
                {sb_handle_v}
            }}
            QScrollBar::handle:vertical:hover {{
                {sb_handle_v_hover}
            }}
            QScrollBar::handle:vertical:pressed {{
                {sb_handle_v_hover}
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
                border: none;
                background-color: transparent;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background-color: transparent;
            }}
            QScrollBar:horizontal {{
                {sb_track_h}
                margin: 0 2px;
            }}
            QScrollBar::handle:horizontal {{
                {sb_handle_h}
            }}
            QScrollBar::handle:horizontal:hover {{
                {sb_handle_h_hover}
            }}
            QScrollBar::handle:horizontal:pressed {{
                {sb_handle_h_pressed}
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                width: 0px;
                border: none;
                background-color: transparent;
            }}
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
                background-color: transparent;
            }}
        """

    @staticmethod
    def list_style() -> str:
        colors = AppStyles._get_colors()
        r = AppStyles._get_style_border_radius()
        ff = AppStyles._get_style_font_family()
        style = AppStyles._visual_style
        if style == 'neumorphic':
            tv_border = f"border: none; {AppStyles._get_style_inset()}"
        elif style == 'skeuomorphic':
            tv_border = f"border: 2px outset {colors.get('border_3d_light', colors['mid'])};"
        elif style == 'frosted':
            tv_border = "border: 1px solid rgba(255,255,255,0.1);"
        elif style == 'win11':
            tv_border = f"border: 1px solid {colors.get('border_thin', colors['mid'])};"
        elif style in ('mac', 'ios'):
            tv_border = "border: none;"
        else:
            tv_border = f"border: 2px solid {colors['table_border']};"
        hdr_sep = colors['shadow_dark'] if style in ('neumorphic', 'skeuomorphic') else colors['table_border']
        return f"""
            QTableView {{
                {tv_border}
                border-radius: {r}px;
                alternate-background-color: {colors['table_alternate']};
                selection-background-color: {colors['table_selection']};
                selection-color: {colors['table_selection_text']};
                gridline-color: {colors['table_grid']};
                font-size: 12px;
                font-family: {ff};
                background-color: {colors['alternate_base']};
            }}
            QTableView::item {{
                padding: 6px 10px;
                border-bottom: 1px solid {colors['table_grid']};
                color: {colors['window_text']};
            }}
            QTableView::item:hover {{
                background-color: {colors['table_hover']};
                border: 1px solid {colors['accent']};
                border-radius: 4px;
            }}
            QTableView::item:selected {{
                background-color: {colors['table_selection']};
                color: {colors['table_selection_text']};
                font-weight: 500;
                border: 1px solid {colors['accent_pressed']};
                border-radius: 4px;
            }}
            QTableView::item:selected:hover {{
                background-color: {colors['accent_hover']};
                border-color: {colors['accent_pressed']};
            }}
            QHeaderView {{
                background-color: {colors['table_header']};
                border: none;
            }}
            QHeaderView::section {{
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {colors['table_header_gradient_start']},
                    stop:0.5 {colors['table_header_gradient_middle']},
                    stop:1 {colors['table_header_gradient_end']});
                padding: 8px 12px;
                border: none;
                border-right: 1px solid {hdr_sep};
                color: {colors['window_text']};
                font-weight: 600;
                font-size: 12px;
                font-family: {ff};
            }}
            QHeaderView::section:last {{
                border-right: none;
            }}
            QHeaderView::section:first {{ min-width: 60px; }}
            QHeaderView::section:nth-child(2) {{ min-width: 180px; }}
            QHeaderView::section:nth-child(3) {{ min-width: 100px; }}
            QHeaderView::section:nth-child(4) {{ min-width: 250px; }}
            QTableView::item:drag {{
                background-color: {colors['table_selection']};
                color: {colors['table_selection_text']};
                border: 2px dashed {colors['accent_pressed']};
                border-radius: 4px;
                opacity: 0.7;
            }}
            QTableView::item:drop {{
                background-color: {colors['table_hover']};
                border: 2px solid {colors['accent']};
                border-radius: 4px;
            }}
        """

    @staticmethod
    def statusbar_style() -> str:
        colors = AppStyles._get_colors()
        r = AppStyles._get_style_border_radius()
        style = AppStyles._visual_style
        from ui.styles import color_to_hex
        sb_bg = colors['player_panel']
        if style == 'frosted':
            sb_bg = color_to_hex(colors['player_panel'])
        if style == 'neumorphic':
            sb_dec = f"background-color: {sb_bg}; {AppStyles._get_style_raised()}"
        elif style == 'skeuomorphic':
            sb_dec = f"background-color: {sb_bg}; border: 1px outset {colors.get('border_3d_light', colors['mid'])}"
        elif style == 'frosted':
            sb_dec = f"background-color: {sb_bg}; border: 1px solid rgba(255,255,255,0.1)"
        elif style == 'win11':
            sb_dec = f"background-color: {sb_bg}; border-top: 1px solid {colors.get('border_thin', colors['mid'])}"
        elif style in ('mac', 'ios'):
            sb_dec = f"background-color: {sb_bg}; border: none"
        else:
            sb_dec = f"background-color: {sb_bg}; border: none"
        return f"""
            QStatusBar {{
                {sb_dec}
                color: {colors['player_panel_text']};
                padding: 4px;
                border-bottom-left-radius: {r}px;
                border-bottom-right-radius: {r}px;
            }}
        """

    @staticmethod
    def player_toolbar_style() -> str:
        colors = AppStyles._get_colors()
        r = AppStyles._get_style_border_radius()
        style = AppStyles._visual_style
        btn_border = "none" if style in ('mac', 'ios') else f"1px solid {colors['player_line']}"
        return f"""
            QToolBar {{
                background-color: {colors['player_panel']};
                color: {colors['player_panel_text']};
                padding: 4px;
            }}
            QToolBar QPushButton {{
                background-color: {colors['player_button']};
                color: {colors['player_panel_text']};
                border: {btn_border};
                padding: 5px 10px;
                border-radius: {r}px;
                margin: 2px;
            }}
            QToolBar QPushButton:hover {{
                background-color: {colors['player_line']};
            }}
        """

    @staticmethod
    def player_panel_style() -> str:
        colors = AppStyles._get_colors()
        ff = AppStyles._get_style_font_family()
        r = AppStyles._get_style_border_radius()
        style = AppStyles._visual_style
        if style == 'neumorphic':
            combo_dec = f"border: none; background-color: {colors['player_combo']}; {AppStyles._get_style_inset()} border-radius: {r}px;"
            list_dec = f"{AppStyles._get_style_inset()} background-color: {colors['player_panel']};"
            btn_dec = f"background-color: {colors['player_button']}; {AppStyles._get_style_raised()} border-radius: {r}px;"
        elif style == 'skeuomorphic':
            combo_dec = f"border: 1px inset {colors.get('border_3d_dark', colors['mid'])}; background-color: {colors['player_combo']}; border-radius: {r}px;"
            list_dec = f"border: 1px outset {colors.get('border_3d_light', colors['mid'])}; background-color: {colors['player_panel']};"
            btn_dec = f"background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {colors.get('gradient_start', colors['light'])}, stop:1 {colors['player_button']}); border: 1px outset {colors.get('border_3d_light', colors['mid'])}; border-radius: {r}px;"
        elif style == 'frosted':
            combo_dec = f"border: 1px solid rgba(255,255,255,0.1); background-color: {colors['player_combo']}; border-radius: {r}px;"
            list_dec = f"border: 1px solid rgba(255,255,255,0.1); background-color: {colors['player_panel']};"
            btn_dec = f"background-color: {colors['player_button']}; border: 1px solid rgba(255,255,255,0.1); border-radius: {r}px;"
        elif style == 'win11':
            combo_dec = f"border: 1px solid {colors.get('border_thin', colors['mid'])}; background-color: {colors['player_combo']}; border-radius: {r}px; border-bottom: 2px solid {colors['accent']};"
            list_dec = f"border: 1px solid {colors.get('border_thin', colors['mid'])}; background-color: {colors['player_panel']};"
            btn_dec = f"background-color: {colors['player_button']}; border: 1px solid {colors.get('border_thin', colors['mid'])}; border-radius: {r}px;"
        elif style in ('mac', 'ios'):
            combo_dec = f"border: none; background-color: {colors['player_combo']}; border-radius: {r}px;"
            list_dec = f"border: none; background-color: {colors['player_panel']};"
            btn_dec = f"background-color: {colors['player_button']}; border: none; border-radius: {r}px;"
        else:
            combo_dec = f"border: 1px solid {colors['mid']}; background-color: {colors['player_combo']}; border-radius: {r}px;"
            list_dec = f"border: 1px solid {colors['mid']}; background-color: {colors['player_panel']};"
            btn_dec = f"background-color: {colors['player_button']}; border: 1px solid {colors.get('player_line', colors['mid'])}; border-radius: {r}px;"
        return f"""
            * {{
                font-family: {ff};
            }}
            QWidget {{
                background-color: transparent;
            }}
            QLabel {{
                color: {colors['player_panel_text']};
                background-color: transparent;
            }}
            QListWidget {{
                {list_dec}
                color: {colors['player_panel_text']};
                outline: none;
            }}
            QComboBox {{
                {combo_dec}
                color: {colors['player_panel_text']};
                padding: 2px 6px;
            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: center right;
                width: 16px;
                border: none;
            }}
            QComboBox::down-arrow {{
                image: url({AppStyles._get_arrow_image(colors['player_panel_secondary'])});
                width: 10px;
                height: 6px;
            }}
            QToolButton {{
                {btn_dec}
                padding: 0px;
                margin: 0px;
            }}
            QPushButton {{
                {btn_dec}
                padding: 0px;
                margin: 0px;
            }}
        """

    @staticmethod
    def player_button_style() -> str:
        colors = AppStyles._get_colors()
        r = AppStyles._get_style_border_radius()
        style = AppStyles._visual_style
        btn_dec = AppStyles._style_btn_decoration(colors)
        btn_dec_hover = AppStyles._style_btn_decoration(colors, hover=True)
        btn_dec_pressed = AppStyles._style_btn_decoration(colors, pressed=True)
        return f"""
            QToolButton {{
                color: {colors['player_panel_text']};
                font-size: 14px;
                {btn_dec}
                padding: 0px;
                margin: 0px;
            }}
            QToolButton:hover {{
                color: {colors['player_panel_text']};
                {btn_dec_hover}
            }}
            QToolButton:pressed {{
                color: {colors['player_button']};
                {btn_dec_pressed}
            }}
        """

    @staticmethod
    def player_slider_style() -> str:
        colors = AppStyles._get_colors()
        groove, sub_page, handle = AppStyles._style_slider_decoration(colors)
        return f"""
            QSlider {{
                background-color: transparent;
            }}
            QSlider::groove:horizontal {{ 
                {groove}
            }} 
            QSlider::sub-page:horizontal {{
                {sub_page}
            }}
            QSlider::handle:horizontal {{ 
                {handle}
            }}
        """

    @staticmethod
    def player_volume_slider_style() -> str:
        colors = AppStyles._get_colors()
        return f"""
            QSlider::groove:horizontal {{ 
                background: {colors['player_volume_track']}; 
                height: 4px; 
                border-radius: 2px;
            }} 
            QSlider::sub-page:horizontal {{
                background: {colors['player_slider_fill']};
                height: 4px;
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{ 
                background: {colors['player_slider_handle']}; 
                width: 12px; 
                height: 12px; 
                border-radius: 6px;
                margin: -4px 0;
            }}
        """

    @staticmethod
    def exit_catchup_button_style() -> str:
        colors = AppStyles._get_colors()
        r = AppStyles._get_style_border_radius()
        btn_dec = AppStyles._style_btn_decoration(colors)
        btn_hover = AppStyles._style_btn_decoration(colors, hover=True, accent_color=colors['error'])
        return f"""
            QToolButton {{
                color: {colors['window_text']};
                font-size: 12px;
                {btn_dec}
                padding: 0px;
                margin: 0px;
            }}
            QToolButton:hover {{
                {btn_hover}
            }}
        """

    @staticmethod
    def player_label_style() -> str:
        colors = AppStyles._get_colors()
        return f"""
            QLabel {{
                color: {colors['player_panel_secondary']};
                font-size: 12px;
                background-color: transparent;
            }}
        """

    @staticmethod
    def player_media_badge_style() -> str:
        colors = AppStyles._get_colors()
        return f"""
            QLabel {{
                color: {colors['player_panel_secondary']};
                font-size: 11px;
                background-color: transparent;
                padding: 1px 5px;
                border: 1px solid {colors['player_line']};
                border-radius: 3px;
            }}
        """

    @staticmethod
    def player_time_badge_style() -> str:
        colors = AppStyles._get_colors()
        return f"""
            QLabel {{
                color: {colors['player_panel_disabled']};
                font-size: 11px;
                background-color: transparent;
                padding: 1px 5px;
                border: 1px solid {colors['player_line']};
                border-radius: 3px;
            }}
        """

    @staticmethod
    def player_status_badge_style() -> str:
        colors = AppStyles._get_colors()
        return f"""
            QLabel {{
                color: {colors['player_success']};
                font-size: 11px;
                background-color: transparent;
                padding: 1px 5px;
                border: 1px solid {colors['player_success']};
                border-radius: 3px;
            }}
        """

    @staticmethod
    def player_channel_name_style() -> str:
        colors = AppStyles._get_colors()
        return f"""
            QLabel {{
                color: {colors['player_panel_text']};
                font-size: 18px;
                font-weight: bold;
                background-color: transparent;
                padding: 0px;
                margin: 0px;
                border: none;
            }}
        """

    @staticmethod
    def player_channel_list_name_style() -> str:
        colors = AppStyles._get_colors()
        return f"font-size: 12px; font-weight: bold; color: {colors['player_panel_text']}; background: transparent; border: none;"

    @staticmethod
    def player_program_style() -> str:
        colors = AppStyles._get_colors()
        return f"""
            QLabel {{
                color: {colors['player_success']};
                font-size: 13px;
                background-color: transparent;
                padding: 0px;
                margin: 0px;
                border: none;
            }}
        """

    @staticmethod
    def player_catchup_indicator_style() -> str:
        colors = AppStyles._get_colors()
        return f"""
            QLabel {{
                color: {colors['player_accent']};
                font-size: 11px;
                background-color: transparent;
                padding: 1px 4px;
                border: 1px solid {colors['player_accent']};
                border-radius: 3px;
            }}
        """

    @staticmethod
    def player_program_desc_style() -> str:
        colors = AppStyles._get_colors()
        return f"""
            QLabel {{
                color: {colors['player_panel_secondary']};
                font-size: 14px;
                background-color: transparent;
                padding: 0px;
                margin: 0px;
                border: none;
                max-height: 54px;
            }}
        """

    @staticmethod
    def player_date_button_style() -> str:
        colors = AppStyles._get_colors()
        return f"""
            QPushButton {{
                background-color: transparent;
                color: {colors['player_panel_disabled']};
                font-size: 16px;
                padding: 0px;
                margin: 0px;
                border: none;
            }}
        """

    @staticmethod
    def player_date_label_style() -> str:
        colors = AppStyles._get_colors()
        return f"""
            QLabel {{
                color: {colors['player_panel_text']};
                font-size: 12px;
            }}
        """

    @staticmethod
    def player_epg_title_style() -> str:
        colors = AppStyles._get_colors()
        return f"""
            QLabel {{
                color: {colors['player_panel_text']};
                font-size: 14px;
                font-weight: bold;
                padding: 8px;
                background-color: transparent;
            }}
        """

    @staticmethod
    def player_group_combo_style() -> str:
        colors = AppStyles._get_colors()
        return f"""
            QComboBox {{
                background-color: {colors['player_combo']};
                color: {colors['player_panel_text']};
                padding: 4px 8px;
                border: 1px solid {colors['player_line']};
                border-radius: 4px;
                font-size: 12px;
                min-width: 80px;
            }}
            QComboBox:hover {{
                border: 1px solid {colors['player_accent']};
            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: right center;
                width: 16px;
                border-left: none;
                border-top-right-radius: 4px;
                border-bottom-right-radius: 4px;
            }}
            QComboBox::down-arrow {{
                image: url({AppStyles._get_arrow_image(colors['player_panel_secondary'])});
                width: 10px;
                height: 6px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {colors['player_panel']};
                color: {colors['player_panel_text']};
                selection-background-color: {colors['player_accent']};
                selection-color: {colors['player_panel_text']};
                border: 1px solid {colors['player_line']};
                outline: none;
            }}
        """

    @staticmethod
    def player_tab_style() -> str:
        colors = AppStyles._get_colors()
        return f"""
            QTabWidget::pane {{
                border: none;
                background-color: transparent;
            }}
            QTabBar::tab {{
                background-color: {colors['player_combo']};
                color: {colors['player_panel_text']};
                padding: 5px 10px;
                border: 1px solid {colors['player_line']};
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                font-size: 11px;
                min-width: 90px;
            }}
            QTabBar::tab:selected {{
                background-color: {colors['player_accent']};
                color: {AppStyles.COLOR_WHITE};
            }}
            QTabBar::tab:hover:!selected {{
                background-color: {colors['player_panel']};
            }}
        """

    @staticmethod
    def player_playlist_title_style() -> str:
        colors = AppStyles._get_colors()
        return f"""
            QLabel {{
                color: {colors['player_panel_text']};
                font-size: 14px;
                font-weight: bold;
                padding: 8px;
                background-color: transparent;
            }}
        """

    @staticmethod
    def player_search_input_style() -> str:
        colors = AppStyles._get_colors()
        return f"""
            QLineEdit {{
                background-color: {colors['player_combo']};
                color: {colors['player_panel_text']};
                border: 1px solid {colors['player_line']};
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 12px;
            }}
            QLineEdit:focus {{
                border: 1px solid {colors['player_accent']};
            }}
            QLineEdit::clear-button {{
                subcontrol-origin: padding;
                subcontrol-position: right center;
                width: 16px;
            }}
        """

    @staticmethod
    def player_line_style() -> str:
        colors = AppStyles._get_colors()
        return f"""
            QFrame {{
                background-color: {colors['player_line']};
                max-height: 1px;
            }}
        """

    @staticmethod
    def player_video_placeholder_style() -> str:
        colors = AppStyles._get_colors()
        return f"""
            QLabel {{
                font-size: 200px;
                color: {colors['player_panel_hint']};
                background-color: {colors['player_video_placeholder']};
            }}
        """

    @staticmethod
    def player_empty_label_style() -> str:
        colors = AppStyles._get_colors()
        return f"""
            QLabel {{
                color: {colors['player_panel_hint']};
                font-size: 12px;
                background-color: transparent;
            }}
        """

    @staticmethod
    def player_list_style() -> str:
        colors = AppStyles._get_colors()
        return f"""
            QListWidget {{
                background-color: transparent;
                color: {colors['player_panel_text']};
                border: none;
                padding: 2px;
            }}
            QListWidget::item {{
                padding: 2px 4px;
                min-height: 26px;
                border: 1px solid transparent;
                border-radius: 3px;
            }}
            QListWidget::item:selected {{
                border: 1px solid {colors['player_accent']};
                background-color: {colors['highlight']};
                color: {colors['highlighted_text']};
            }}
            QListWidget::item:hover {{
                border: 1px solid {colors['player_line']};
                background-color: {colors['highlight']};
            }}
        """

    @staticmethod
    def player_progress_label_style() -> str:
        colors = AppStyles._get_colors()
        return f"""
            QLabel {{
                color: {colors['player_panel_disabled']};
                font-size: 11px;
                background-color: transparent;
            }}
        """

    @staticmethod
    def player_channel_logo_style() -> str:
        colors = AppStyles._get_colors()
        return f"""
            QLabel {{
                font-size: 24px;
                background-color: transparent;
                color: {colors['player_panel_secondary']};
                qproperty-alignment: AlignVCenter | AlignHCenter;
            }}
        """

    @staticmethod
    def player_background_style() -> str:
        colors = AppStyles._get_colors()
        return f"background-color: {colors['player_background']};"

    @staticmethod
    def title_bar_style() -> str:
        colors = AppStyles._get_colors()
        r = AppStyles._get_style_border_radius()
        style = AppStyles._visual_style
        title_bg = colors.get('window', '#1e1e1e')
        title_text = colors.get('window_text', '#ffffff')
        accent_color = colors.get('accent', '#0078d4')
        if style == 'neumorphic':
            btn_dec = f"background-color: transparent; border: none; font-size: 14px; padding: 4px 12px; margin: 2px; border-radius: {r}px;"
        elif style == 'skeuomorphic':
            btn_dec = f"background-color: transparent; border: 1px outset {colors.get('border_3d_light', colors['mid'])}; font-size: 14px; padding: 4px 12px; margin: 2px; border-radius: {r}px;"
        elif style == 'frosted':
            btn_dec = f"background-color: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.08); font-size: 14px; padding: 4px 12px; margin: 2px; border-radius: {r}px;"
        elif style == 'win11':
            btn_dec = f"background-color: transparent; border: none; font-size: 14px; padding: 4px 12px; margin: 2px; border-radius: {r}px;"
        elif style in ('mac', 'ios'):
            btn_dec = f"background-color: transparent; border: none; font-size: 14px; padding: 4px 14px; margin: 1px; border-radius: {r}px;"
        else:
            btn_dec = f"background-color: transparent; border: none; font-size: 14px; padding: 4px 12px; margin: 2px; border-radius: {r}px;"
        return f"""
            QWidget#titleBar {{
                background-color: {title_bg};
                border-top-left-radius: {r}px;
                border-top-right-radius: {r}px;
            }}
            QWidget#titleBar > QPushButton {{
                color: {title_text};
                {btn_dec}
            }}
            QWidget#titleBar > QPushButton:hover {{
                background-color: {accent_color};
                color: white;
            }}
            QWidget#titleBar > QPushButton#closeButton:hover {{
                background-color: {AppStyles.COLOR_CLOSE_HOVER};
                color: white;
            }}
        """

    @staticmethod
    def title_label_style() -> str:
        colors = AppStyles._get_colors()
        title_text = colors.get('window_text', '#ffffff')
        return f"color: {title_text}; font-size: 13px; font-weight: bold; background: transparent; padding-left: 6px;"

    @staticmethod
    def player_menu_bar_style() -> str:
        colors = AppStyles._get_colors()
        r = AppStyles._get_style_border_radius()
        ff = AppStyles._get_style_font_family()
        style = AppStyles._visual_style
        menu_bg = colors['base']
        menu_text = colors['window_text']
        menu_hover_bg = colors['neumorphic_light'] if style == 'neumorphic' else colors['highlight']
        menu_hover_text = colors['accent'] if style == 'neumorphic' else colors['highlighted_text']
        menu_dec = AppStyles._style_menu_decoration(colors)
        item_r = max(r - 2, 4)
        if style in ('neumorphic', 'skeuomorphic'):
            item_pad = "6px 24px"
        elif style == 'ios':
            item_pad = "8px 28px"
        else:
            item_pad = "4px 20px"
        if style == 'neumorphic':
            menubar_border_bottom = f"border-bottom: 2px solid {colors['shadow_dark']};"
            menubar_item_dec = AppStyles._style_btn_decoration(colors)
        elif style == 'skeuomorphic':
            menubar_border_bottom = f"border-bottom: 1px solid {colors.get('border_3d_dark', colors['mid'])};"
            menubar_item_dec = ""
        elif style == 'win11':
            menubar_border_bottom = f"border-bottom: 1px solid {colors.get('border_thin', colors['mid'])};"
            menubar_item_dec = ""
        else:
            menubar_border_bottom = ""
            menubar_item_dec = ""
        if style == 'neumorphic':
            item_selected_dec = f"background-color: {menu_hover_bg}; {AppStyles._get_style_inset()} border-radius: {item_r}px;"
        elif style == 'skeuomorphic':
            item_selected_dec = f"background-color: {menu_hover_bg}; border: 1px inset {colors.get('border_3d_dark', colors['mid'])}; border-radius: {item_r}px;"
        elif style == 'frosted':
            item_selected_dec = f"background-color: {menu_hover_bg}; border: 1px solid rgba(255,255,255,0.15); border-radius: {item_r}px;"
        elif style == 'win11':
            item_selected_dec = f"background-color: {menu_hover_bg}; border-bottom: 2px solid {colors['accent']}; border-radius: {item_r}px;"
        elif style in ('mac', 'ios'):
            item_selected_dec = f"background-color: {menu_hover_bg}; border-radius: {item_r}px;"
        else:
            item_selected_dec = f"background-color: {menu_hover_bg}; border: 1px solid {colors['accent']}; border-radius: {item_r}px;"
        return f"""
            QMenuBar {{
                background-color: {menu_bg};
                color: {menu_text};
                padding: 2px;
                {menubar_border_bottom}
            }}
            QMenuBar::item {{
                padding: 4px 10px;
                margin: 2px;
                border-radius: {item_r}px;
                {menubar_item_dec}
            }}
            QMenuBar::item:selected {{
                {item_selected_dec}
                color: {menu_hover_text};
            }}
            QMenu {{
                color: {menu_text};
                {menu_dec}
            }}
            QMenu::item {{
                padding: {item_pad};
                margin: 2px;
                border-radius: {item_r}px;
            }}
            QMenu::item:selected {{
                {item_selected_dec}
                color: {menu_hover_text};
            }}
            QMenu::separator {{
                height: 1px;
                background-color: {colors.get('shadow_dark', colors['mid'])};
                margin: 4px 8px;
            }}
        """

    @staticmethod
    def common_menu_style() -> str:
        colors = AppStyles._get_colors()
        r = AppStyles._get_style_border_radius()
        style = AppStyles._visual_style
        menu_bg = colors['base']
        menu_text = colors['window_text']
        menu_hover_bg = colors['neumorphic_light'] if style == 'neumorphic' else colors['highlight']
        menu_hover_text = colors['accent'] if style == 'neumorphic' else colors['highlighted_text']
        menu_dec = AppStyles._style_menu_decoration(colors)
        item_r = max(r - 2, 4)
        if style in ('neumorphic', 'skeuomorphic'):
            item_pad = "6px 24px"
        else:
            item_pad = "4px 20px"
        return f"""
            QMenu {{
                color: {menu_text};
                {menu_dec}
            }}
            QMenu::item {{
                padding: {item_pad};
                margin: 2px;
                border-radius: {item_r}px;
            }}
            QMenu::item:selected {{
                background-color: {menu_hover_bg};
                color: {menu_hover_text};
                border-radius: {item_r}px;
            }}
            QMenu::separator {{
                height: 1px;
                background-color: {colors.get('shadow_dark', colors['mid'])};
                margin: 4px 8px;
            }}
        """

    @staticmethod
    def popup_dialog_style() -> str:
        colors = AppStyles._get_colors()
        opacity = colors.get('window_opacity', 220) / 255.0
        window_bg = colors['player_panel']
        r = AppStyles._get_style_border_radius()
        ff = AppStyles._get_style_font_family()
        btn_dec = AppStyles._style_btn_decoration(colors)
        btn_hover = AppStyles._style_btn_decoration(colors, hover=True)
        btn_pressed = AppStyles._style_btn_decoration(colors, pressed=True)
        inp_dec = AppStyles._style_input_decoration(colors)
        inp_focus = AppStyles._style_input_decoration(colors, focus=True)
        grp_dec = AppStyles._style_group_decoration(colors)
        style = AppStyles._visual_style
        chk_bg = colors['neumorphic_light'] if style == 'neumorphic' else colors['alternate_base']
        chk_inset = AppStyles._get_style_inset() if style == 'neumorphic' else ""
        chk_border = f"2px solid {colors['mid']}" if style != 'neumorphic' else ""
        input_bg = colors['neumorphic_light'] if style == 'neumorphic' else colors['alternate_base']
        dialog_r = r + 4 if r > 4 else 12
        return f"""
            QDialog {{
                background-color: {window_bg};
                color: {colors['window_text']};
                border: 1px solid {colors['mid']};
                border-radius: {dialog_r}px;
                font-family: {ff};
            }}
            QDialog > QWidget {{
                background-color: {window_bg};
                border-radius: {dialog_r}px;
            }}
            QDialog QLabel {{
                color: {colors['window_text']};
                font-size: 12px;
            }}
            QDialog QPushButton {{
                min-width: 70px;
                padding: {AppStyles._style_padding('button')};
                font-size: 12px;
                font-weight: 500;
                color: {colors['window_text']};
                {btn_dec}
            }}
            QDialog QPushButton:hover {{
                {btn_hover}
            }}
            QDialog QPushButton:pressed {{
                {btn_pressed}
            }}
            QDialog QGroupBox {{
                margin-top: 12px;
                padding-top: 18px;
                {grp_dec}
            }}
            QDialog QGroupBox::title {{
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
                color: {colors['window_text']};
                font-weight: 600;
                font-size: 12px;
            }}
            QDialog QLineEdit, QDialog QComboBox {{
                padding: {AppStyles._style_padding('input')};
                font-size: 12px;
                color: {colors['window_text']};
                {inp_dec}
            }}
            QDialog QLineEdit:focus, QDialog QComboBox:focus {{
                {inp_focus}
            }}
            QDialog QComboBox QAbstractItemView {{
                background-color: {colors['window']};
                color: {colors['window_text']};
                border: 1px solid {colors['mid']};
                border-radius: 4px;
            }}
            QDialog QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: center right;
                width: 20px;
                border: none;
            }}
            QDialog QComboBox::down-arrow {{
                image: url({AppStyles._get_arrow_image(colors['window_text'])});
                width: 10px;
                height: 6px;
            }}
            QDialog QCheckBox {{
                color: {colors['window_text']};
                font-size: 12px;
                font-family: {ff};
                spacing: 8px;
            }}
            QDialog QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border-radius: 4px;
                background-color: {chk_bg};
                {chk_inset}
                border: {chk_border};
            }}
            QDialog QCheckBox::indicator:checked {{
                background-color: {colors['accent']};
                border: 2px solid {colors['accent']};
                border-radius: 4px;
                image: url({AppStyles._get_check_image(AppStyles.COLOR_WHITE)});
            }}
            QDialog QCheckBox::indicator:hover {{
                border: 2px solid {colors['accent']};
                border-radius: 4px;
            }}
            QDialog QCheckBox::indicator:pressed {{
                background-color: {colors['accent_pressed']};
                border: 2px solid {colors['accent_pressed']};
                border-radius: 4px;
            }}
            QDialog QTextEdit {{
                padding: 10px;
                font-size: 12px;
                color: {colors['window_text']};
                {inp_dec}
            }}
            QDialog QTextEdit:focus {{
                {inp_focus}
            }}
            QDialog QListWidget {{
                background-color: {input_bg};
                color: {colors['window_text']};
                border: 1px solid {colors['mid']};
                border-radius: {r}px;
            }}
            QDialog QListWidget::item {{
                padding: 4px 8px;
                border-radius: 4px;
            }}
            QDialog QListWidget::item:selected {{
                background-color: {colors['accent']};
                color: {colors['bright_text']};
            }}
            QDialog QListWidget::item:hover {{
                background-color: {colors['button']};
            }}
            QDialog QListWidget::indicator {{
                width: 16px;
                height: 16px;
                border: 1px solid {colors['mid']};
                border-radius: 4px;
                background-color: {input_bg};
            }}
            QDialog QListWidget::indicator:checked {{
                background-color: {colors['accent']};
                border-color: {colors['accent']};
                image: url({AppStyles._get_check_image(colors['bright_text'])});
            }}
            QDialog QListWidget::indicator:hover {{
                border-color: {colors['accent']};
            }}
        """

    @staticmethod
    def dialog_style() -> str:
        return AppStyles.popup_dialog_style()

    @staticmethod
    def progress_style() -> str:
        colors = AppStyles._get_colors()
        r = AppStyles._get_style_border_radius()
        ff = AppStyles._get_style_font_family()
        style = AppStyles._visual_style
        if style == 'neumorphic':
            progress_border = AppStyles._get_style_inset()
        elif style == 'skeuomorphic':
            progress_border = f"border: 2px inset {colors.get('border_3d_dark', colors['mid'])};"
        elif style in ('mac', 'ios'):
            progress_border = "border: none;"
        elif style == 'frosted':
            progress_border = "border: 1px solid rgba(255,255,255,0.1);"
        elif style == 'win11':
            progress_border = f"border: 1px solid {colors.get('border_thin', colors['mid'])};"
        else:
            progress_border = f"border: 1px solid {colors['mid']};"
        return f"""
            QProgressBar {{
                {progress_border}
                border-radius: {r}px;
                text-align: center;
                height: 24px;
                background-color: {colors['alternate_base']};
                font-size: 11px;
                font-weight: 500;
                font-family: {ff};
                color: {colors['window_text']};
            }}
            QProgressBar::chunk {{
                background-color: {colors['accent']};
                border-radius: {max(r-1, 3)}px;
                margin: 1px;
            }}
        """

    @staticmethod
    def toolbar_button_style() -> str:
        colors = AppStyles._get_colors()
        r = AppStyles._get_style_border_radius()
        ff = AppStyles._get_style_font_family()
        btn_dec = AppStyles._style_btn_decoration(colors)
        btn_hover = AppStyles._style_btn_decoration(colors, hover=True)
        btn_pressed = AppStyles._style_btn_decoration(colors, pressed=True)
        return f"""
            QToolButton {{
                padding: 4px 8px;
                margin: 1px;
                min-width: 60px;
                min-height: 28px;
                color: {colors['window_text']};
                font-size: 12px;
                font-weight: 500;
                font-family: {ff};
                {btn_dec}
            }}
            QToolButton:hover {{
                color: {colors['accent']};
                {btn_hover}
            }}
            QToolButton:pressed {{
                color: {colors['accent_pressed']};
                {btn_pressed}
            }}
            QToolButton::menu-indicator {{
                width: 0px;
            }}
        """

    @staticmethod
    def drag_list_style() -> str:
        colors = AppStyles._get_colors()
        r = AppStyles._get_style_border_radius()
        ff = AppStyles._get_style_font_family()
        style = AppStyles._visual_style
        if style == 'neumorphic':
            list_border = f"border: none; {AppStyles._get_style_inset()}"
            item_bg = colors['neumorphic_light']
            item_dec = AppStyles._get_style_raised()
        elif style == 'skeuomorphic':
            list_border = f"border: 2px outset {colors.get('border_3d_light', colors['mid'])};"
            item_bg = f"qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {colors.get('gradient_start', colors['light'])}, stop:1 {colors['button']})"
            item_dec = ""
        elif style == 'frosted':
            list_border = "border: 1px solid rgba(255,255,255,0.1);"
            item_bg = colors['light']
            item_dec = ""
        elif style == 'win11':
            list_border = f"border: 1px solid {colors.get('border_thin', colors['mid'])};"
            item_bg = colors['light']
            item_dec = ""
        elif style in ('mac', 'ios'):
            list_border = "border: none;"
            item_bg = colors['light']
            item_dec = ""
        else:
            list_border = f"border: 1px solid {colors['mid']};"
            item_bg = colors['light']
            item_dec = ""
        item_r = max(r - 2, 4)
        return f"""
            QListWidget {{
                {list_border}
                border-radius: {r}px;
                padding: 4px;
                background-color: {colors['alternate_base']};
                font-size: 13px;
            }}
            QListWidget::item {{
                border: 1px solid transparent;
                border-radius: {item_r}px;
                padding: 8px 12px;
                margin: 2px;
                background-color: {item_bg};
                color: {colors['window_text']};
                {item_dec}
            }}
            QListWidget::item:hover {{
                background-color: {colors['highlight']};
                border: 1px solid {colors['mid']};
            }}
            QListWidget::item:selected {{
                background-color: {colors['accent']};
                color: {AppStyles.COLOR_WHITE};
                border: 1px solid {colors['accent_pressed']};
            }}
            QListWidget::item:selected:hover {{
                background-color: {colors['accent_hover']};
            }}
        """

    @staticmethod
    def drag_hint_label_style() -> str:
        colors = AppStyles._get_colors()
        r = AppStyles._get_style_border_radius()
        btn_dec = AppStyles._style_btn_decoration(colors)
        return f"""
            QLabel {{
                color: {colors['accent']};
                font-size: 12px;
                padding: 8px 12px;
                font-weight: 500;
                {btn_dec}
            }}
        """

    @staticmethod
    def group_hint_label_style() -> str:
        colors = AppStyles._get_colors()
        r = AppStyles._get_style_border_radius()
        btn_dec = AppStyles._style_btn_decoration(colors)
        return f"""
            QLabel {{
                color: {colors['window_text']};
                font-size: 12px;
                padding: 8px 12px;
                font-weight: 500;
                {btn_dec}
                opacity: 0.8;
            }}
        """

    @staticmethod
    def statusbar_error_style() -> str:
        colors = AppStyles._get_colors()
        r = AppStyles._get_style_border_radius()
        style = AppStyles._visual_style
        from ui.styles import color_to_hex
        sb_bg = colors['player_panel']
        if style == 'frosted':
            sb_bg = color_to_hex(colors['player_panel'])
        if style == 'neumorphic':
            sb_dec = f"background-color: {sb_bg}; {AppStyles._get_style_raised()}"
        elif style == 'skeuomorphic':
            sb_dec = f"background-color: {sb_bg}; border: 1px outset {colors.get('border_3d_light', colors['mid'])}"
        elif style == 'frosted':
            sb_dec = f"background-color: {sb_bg}; border: 1px solid rgba(255,255,255,0.1)"
        elif style == 'win11':
            sb_dec = f"background-color: {sb_bg}; border-top: 1px solid {colors.get('border_thin', colors['mid'])}"
        elif style in ('mac', 'ios'):
            sb_dec = f"background-color: {sb_bg}; border: none"
        else:
            sb_dec = f"background-color: {sb_bg}; border: none"
        return f"""
            QStatusBar {{
                {sb_dec}
                color: {colors['error']};
                font-weight: bold;
                padding: 4px;
                border-bottom-left-radius: {r}px;
                border-bottom-right-radius: {r}px;
            }}
        """

    @staticmethod
    def apply_button_style() -> str:
        colors = AppStyles._get_colors()
        r = AppStyles._get_style_border_radius()
        ff = AppStyles._get_style_font_family()
        btn_dec = AppStyles._style_btn_decoration(colors, accent_color=colors['success'])
        btn_hover = AppStyles._style_btn_decoration(colors, hover=True, accent_color=colors['success'])
        btn_pressed = AppStyles._style_btn_decoration(colors, pressed=True, accent_color=colors['success'])
        pad = AppStyles._style_padding('button')
        return f"""
            QPushButton {{
                color: {colors['window_text']};
                {btn_dec}
                padding: {pad};
                font-weight: 500;
                font-size: 12px;
                font-family: {ff};
            }}
            QPushButton:hover {{
                {btn_hover}
            }}
            QPushButton:pressed {{
                {btn_pressed}
            }}
        """

    @staticmethod
    def cancel_button_style() -> str:
        colors = AppStyles._get_colors()
        r = AppStyles._get_style_border_radius()
        ff = AppStyles._get_style_font_family()
        btn_dec = AppStyles._style_btn_decoration(colors, accent_color=colors['error'])
        btn_hover = AppStyles._style_btn_decoration(colors, hover=True, accent_color=colors['error'])
        btn_pressed = AppStyles._style_btn_decoration(colors, pressed=True, accent_color=colors['error'])
        pad = AppStyles._style_padding('button')
        return f"""
            QPushButton {{
                color: {colors['window_text']};
                {btn_dec}
                padding: {pad};
                font-weight: 500;
                font-size: 12px;
                font-family: {ff};
            }}
            QPushButton:hover {{
                {btn_hover}
            }}
            QPushButton:pressed {{
                {btn_pressed}
            }}
        """

    @staticmethod
    def secondary_label_style() -> str:
        colors = AppStyles._get_colors()
        return f"""
            QLabel {{
                color: {colors['window_text']};
                padding: 0 5px;
                font-size: 13px;
                font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
                opacity: 0.8;
            }}
        """

    @staticmethod
    def tab_widget_style() -> str:
        colors = AppStyles._get_colors()
        r = AppStyles._get_style_border_radius()
        ff = AppStyles._get_style_font_family()
        style = AppStyles._visual_style
        grp_dec = AppStyles._style_group_decoration(colors)
        if style in ('neumorphic', 'mac', 'ios', 'frosted'):
            tab_border = "none"
            pane_border = "none"
            tabbar_bottom = "none"
        else:
            tab_border = f"1px solid {colors['mid']}"
            pane_border = f"1px solid {colors['mid']}"
            tabbar_bottom = f"1px solid {colors['mid']}"
        tab_r = max(r - 2, 4)
        if style == 'neumorphic':
            tab_selected_dec = AppStyles._get_style_raised()
            tab_selected_bg = colors['neumorphic_light']
        elif style == 'skeuomorphic':
            tab_selected_dec = f"border: 2px outset {colors.get('border_3d_light', colors['mid'])};"
            tab_selected_bg = colors.get('gradient_start', colors['window'])
        elif style in ('mac', 'ios'):
            tab_selected_dec = ""
            tab_selected_bg = colors['window']
        else:
            tab_selected_dec = ""
            tab_selected_bg = colors['window']
        return f"""
            QTabWidget {{
                background-color: {colors['window']};
                border: {tab_border};
                border-radius: {r}px;
                font-family: {ff};
            }}
            QTabWidget::pane {{
                border: {pane_border};
                border-radius: 0 0 {r}px {r}px;
                background-color: {colors['window']};
                margin-top: -1px;
            }}
            QTabBar {{
                background-color: {colors['alternate_base']};
                border-bottom: {tabbar_bottom};
                border-radius: {r}px {r}px 0 0;
            }}
            QTabBar::tab {{
                background-color: {colors['alternate_base']};
                border: {tab_border};
                border-bottom: none;
                border-radius: {tab_r}px {tab_r}px 0 0;
                padding: 8px 16px;
                margin-right: 4px;
                margin-top: 4px;
                font-size: 13px;
                font-weight: 500;
                color: {colors['window_text']};
                opacity: 0.8;
            }}
            QTabBar::tab:selected {{
                background-color: {tab_selected_bg};
                border-color: {colors['mid']};
                border-bottom-color: {colors['window']};
                color: {colors['accent']};
                font-weight: 600;
                opacity: 1.0;
                {tab_selected_dec}
            }}
            QTabBar::tab:hover:!selected {{
                background-color: {colors['light']};
                color: {colors['accent']};
                opacity: 0.9;
            }}
            QTabBar::tab:first {{
                margin-left: 4px;
            }}
            QTabBar::tab:last {{
                margin-right: 0;
            }}
        """

    @staticmethod
    def common_button_style() -> str:
        colors = AppStyles._get_colors()
        r = AppStyles._get_style_border_radius()
        ff = AppStyles._get_style_font_family()
        btn_dec = AppStyles._style_btn_decoration(colors)
        btn_hover = AppStyles._style_btn_decoration(colors, hover=True)
        btn_pressed = AppStyles._style_btn_decoration(colors, pressed=True)
        btn_disabled = AppStyles._style_btn_decoration(colors, disabled=True)
        pad = AppStyles._style_padding('button')
        return f"""
            QPushButton {{
                color: {colors['window_text']};
                {btn_dec}
                padding: {pad};
                min-width: 0px;
                font-weight: 500;
                font-size: 12px;
                font-family: {ff};
            }}
            QPushButton:hover {{
                {btn_hover}
            }}
            QPushButton:pressed {{
                {btn_pressed}
            }}
            QPushButton:disabled {{
                {btn_disabled}
            }}
        """

    @staticmethod
    def common_label_style() -> str:
        colors = AppStyles._get_colors()
        return f"""
            QLabel {{
                color: {colors['window_text']};
                font-size: 12px;
                font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
                background-color: transparent;
            }}
        """

    @staticmethod
    def common_line_edit_style() -> str:
        colors = AppStyles._get_colors()
        r = AppStyles._get_style_border_radius()
        ff = AppStyles._get_style_font_family()
        inp_dec = AppStyles._style_input_decoration(colors)
        inp_focus = AppStyles._style_input_decoration(colors, focus=True)
        inp_disabled = AppStyles._style_input_decoration(colors, disabled=True)
        pad = AppStyles._style_padding('input')
        return f"""
            QLineEdit {{
                color: {colors['window_text']};
                {inp_dec}
                padding: {pad};
                font-size: 12px;
                font-family: {ff};
            }}
            QLineEdit:focus {{
                {inp_focus}
            }}
            QLineEdit:disabled {{
                {inp_disabled}
            }}
        """

    @staticmethod
    def common_combo_box_style() -> str:
        colors = AppStyles._get_colors()
        r = AppStyles._get_style_border_radius()
        ff = AppStyles._get_style_font_family()
        inp_dec = AppStyles._style_input_decoration(colors)
        inp_focus = AppStyles._style_input_decoration(colors, focus=True)
        inp_disabled = AppStyles._style_input_decoration(colors, disabled=True)
        pad = AppStyles._style_padding('input')
        return f"""
            QComboBox {{
                color: {colors['window_text']};
                {inp_dec}
                padding: {pad};
                font-size: 12px;
                font-family: {ff};
                min-width: 120px;
            }}
            QComboBox:focus {{
                {inp_focus}
            }}
            QComboBox:disabled {{
                {inp_disabled}
            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: center right;
                width: 20px;
                border: none;
            }}
            QComboBox::down-arrow {{
                image: url({AppStyles._get_arrow_image(colors['window_text'])});
                width: 10px;
                height: 6px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {colors['alternate_base']};
                color: {colors['window_text']};
                border: 1px solid {colors['mid']};
                border-radius: 4px;
                padding: 4px;
            }}
            QComboBox QAbstractItemView::item {{
                padding: 6px 10px;
                margin: 2px 0;
            }}
            QComboBox QAbstractItemView::item:hover {{
                background-color: {colors['accent']};
                color: {AppStyles.COLOR_WHITE};
            }}
        """

    @staticmethod
    def url_combo_style() -> str:
        colors = AppStyles._get_colors()
        r = AppStyles._get_style_border_radius()
        ff = AppStyles._get_style_font_family()
        inp_dec = AppStyles._style_input_decoration(colors)
        inp_focus = AppStyles._style_input_decoration(colors, focus=True)
        return f"""
            QComboBox {{
                color: {colors['window_text']};
                {inp_dec}
                padding: 2px 20px 2px 6px;
                font-size: 12px;
                font-family: {ff};
            }}
            QComboBox:focus {{
                {inp_focus}
            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: center right;
                width: 18px;
                border: none;
            }}
            QComboBox::down-arrow {{
                image: url({AppStyles._get_arrow_image(colors['window_text'])});
                width: 10px;
                height: 6px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {colors['alternate_base']};
                color: {colors['window_text']};
                border: 1px solid {colors['mid']};
                selection-background-color: {colors['accent']};
                selection-color: {AppStyles.COLOR_WHITE};
                padding: 2px;
                outline: none;
            }}
            QComboBox QAbstractItemView::item {{
                padding: 3px 6px;
            }}
            QComboBox QAbstractItemView::item:hover {{
                background-color: {colors['accent']};
                color: {AppStyles.COLOR_WHITE};
            }}
            QComboBox QLineEdit {{
                background-color: transparent;
                border: none;
                padding: 0;
                font-size: 12px;
            }}
        """

    @staticmethod
    def table_style() -> str:
        return AppStyles.list_style()

    @staticmethod
    def common_check_box_style() -> str:
        colors = AppStyles._get_colors()
        r = AppStyles._get_style_border_radius()
        ff = AppStyles._get_style_font_family()
        style = AppStyles._visual_style
        chk_bg = colors['neumorphic_light'] if style == 'neumorphic' else colors['alternate_base']
        if style == 'neumorphic':
            chk_border_dec = AppStyles._get_style_inset()
        elif style == 'skeuomorphic':
            chk_border_dec = f"border: 2px inset {colors.get('border_3d_dark', colors['mid'])};"
        elif style in ('mac', 'ios'):
            chk_border_dec = "border: none;"
        elif style == 'frosted':
            chk_border_dec = "border: 1px solid rgba(255,255,255,0.1);"
        elif style == 'win11':
            chk_border_dec = f"border: 1px solid {colors.get('border_thin', colors['mid'])};"
        else:
            chk_border_dec = f"border: 2px solid {colors['mid']};"
        return f"""
            QCheckBox {{
                color: {colors['window_text']};
                font-size: 12px;
                font-family: {ff};
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border-radius: 4px;
                background-color: {chk_bg};
                {chk_border_dec}
            }}
            QCheckBox::indicator:checked {{
                background-color: {colors['accent']};
                border: 2px solid {colors['accent']};
                border-radius: 4px;
                image: url({AppStyles._get_check_image(AppStyles.COLOR_WHITE)});
            }}
            QCheckBox::indicator:hover {{
                border: 2px solid {colors['accent']};
                border-radius: 4px;
            }}
        """

    @staticmethod
    def common_radio_button_style() -> str:
        colors = AppStyles._get_colors()
        r = AppStyles._get_style_border_radius()
        ff = AppStyles._get_style_font_family()
        style = AppStyles._visual_style
        chk_bg = colors['neumorphic_light'] if style == 'neumorphic' else colors['alternate_base']
        if style == 'neumorphic':
            chk_border_dec = AppStyles._get_style_inset()
        elif style == 'skeuomorphic':
            chk_border_dec = f"border: 2px inset {colors.get('border_3d_dark', colors['mid'])};"
        elif style in ('mac', 'ios'):
            chk_border_dec = "border: none;"
        elif style == 'frosted':
            chk_border_dec = "border: 1px solid rgba(255,255,255,0.1);"
        elif style == 'win11':
            chk_border_dec = f"border: 1px solid {colors.get('border_thin', colors['mid'])};"
        else:
            chk_border_dec = f"border: 2px solid {colors['mid']};"
        return f"""
            QRadioButton {{
                color: {colors['window_text']};
                font-size: 12px;
                font-family: {ff};
                spacing: 8px;
            }}
            QRadioButton::indicator {{
                width: 16px;
                height: 16px;
                border-radius: 8px;
                background-color: {chk_bg};
                {chk_border_dec}
            }}
            QRadioButton::indicator:checked {{
                background-color: {colors['accent']};
                border: 3px solid {colors['accent']};
                border-radius: 8px;
                image: url({AppStyles._get_radio_dot_image(AppStyles.COLOR_WHITE)});
            }}
            QRadioButton::indicator:hover {{
                border: 2px solid {colors['accent']};
                border-radius: 8px;
            }}
        """

    @staticmethod
    def common_group_box_style() -> str:
        colors = AppStyles._get_colors()
        r = AppStyles._get_style_border_radius()
        ff = AppStyles._get_style_font_family()
        grp_dec = AppStyles._style_group_decoration(colors)
        return f"""
            QGroupBox {{
                color: {colors['window_text']};
                margin-top: 12px;
                padding-top: 16px;
                font-weight: 600;
                font-size: 13px;
                font-family: {ff};
                {grp_dec}
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
                color: {colors['window_text']};
                font-weight: 600;
                font-size: 13px;
                font-family: {ff};
            }}
        """

    @staticmethod
    def scroll_area_style() -> str:
        colors = AppStyles._get_colors()
        return f"""
            QScrollArea {{
                background-color: {colors['player_panel']};
                border: none;
            }}
            QScrollArea > QWidget > QWidget {{
                background-color: {colors['player_panel']};
            }}
        """

    @staticmethod
    def common_title_style() -> str:
        colors = AppStyles._get_colors()
        return f"""
            QLabel {{
                color: {colors['window_text']};
                font-size: 16px;
                font-weight: bold;
                font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
                background-color: transparent;
            }}
        """

    @staticmethod
    def common_link_style() -> str:
        colors = AppStyles._get_colors()
        return f"""
            QLabel {{
                color: {colors['link']};
                font-size: 12px;
                font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
                background-color: transparent;
                text-decoration: underline;
            }}
            QLabel:hover {{
                color: {colors['accent_hover']};
            }}
        """

    @staticmethod
    def common_area_style() -> str:
        colors = AppStyles._get_colors()
        grp_dec = AppStyles._style_group_decoration(colors)
        return f"""
            QWidget {{
                padding: 12px;
                {grp_dec}
            }}
        """

    @staticmethod
    def side_panel_style() -> str:
        colors = AppStyles._get_colors()
        r = AppStyles._get_style_border_radius()
        style = AppStyles._visual_style
        if style == 'neumorphic':
            panel_dec = f"border: none; {AppStyles._get_style_raised()}"
        elif style == 'skeuomorphic':
            panel_dec = f"border: 2px outset {colors.get('border_3d_light', colors['mid'])};"
        elif style == 'frosted':
            panel_dec = "border: 1px solid rgba(255,255,255,0.1);"
        elif style == 'win11':
            panel_dec = f"border: 1px solid {colors.get('border_thin', colors['mid'])};"
        elif style in ('mac', 'ios'):
            panel_dec = "border: none;"
        else:
            panel_dec = ""
        return f"""
            QWidget {{
                background-color: {colors['alternate_base']};
                border-radius: {r}px;
                {panel_dec}
            }}
        """

    @staticmethod
    def section_title_style() -> str:
        colors = AppStyles._get_colors()
        return f"""
            QLabel {{
                font-size: 13px;
                font-weight: bold;
                color: {colors['window_text']};
            }}
        """

    @staticmethod
    def small_label_style() -> str:
        colors = AppStyles._get_colors()
        return f"""
            QLabel {{
                font-size: 11px;
                color: {colors['window_text']};
            }}
        """

    @staticmethod
    def hint_label_style() -> str:
        colors = AppStyles._get_colors()
        return f"""
            QLabel {{
                font-size: 10px;
                color: {colors['mid']};
            }}
        """

    @staticmethod
    def button_style(active=False):
        colors = AppStyles._get_colors()
        r = AppStyles._get_style_border_radius()
        ff = AppStyles._get_style_font_family()
        if active:
            btn_dec = AppStyles._style_btn_decoration(colors, accent_color=colors['accent'])
            btn_hover = AppStyles._style_btn_decoration(colors, hover=True, accent_color=colors['accent'])
            btn_pressed = AppStyles._style_btn_decoration(colors, pressed=True, accent_color=colors['accent'])
        else:
            btn_dec = AppStyles._style_btn_decoration(colors)
            btn_hover = AppStyles._style_btn_decoration(colors, hover=True)
            btn_pressed = AppStyles._style_btn_decoration(colors, pressed=True)
            btn_disabled = AppStyles._style_btn_decoration(colors, disabled=True)
        pad = AppStyles._style_padding('button')
        if active:
            return f"""
                QPushButton {{
                    color: {colors['window_text']};
                    {btn_dec}
                    padding: {pad};
                    font-weight: 500;
                    font-size: 12px;
                    font-family: {ff};
                }}
                QPushButton:hover {{
                    {btn_hover}
                }}
                QPushButton:pressed {{
                    {btn_pressed}
                }}
            """
        return f"""
            QPushButton {{
                color: {colors['window_text']};
                {btn_dec}
                padding: {pad};
                font-weight: 500;
                font-size: 12px;
                font-family: {ff};
            }}
            QPushButton:hover {{
                {btn_hover}
            }}
            QPushButton:pressed {{
                {btn_pressed}
            }}
            QPushButton:disabled {{
                {btn_disabled}
            }}
        """
