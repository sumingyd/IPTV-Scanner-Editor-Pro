"""MpvSubtitle — 从 MpvPlayerController 提取的子控制器。"""

from core.log_manager import global_logger as logger


class MpvSubtitle:
    """MpvSubtitle — 通过 facade 访问 mpv 实例和播放器。"""

    def __init__(self, facade):
        self._facade = facade

    def adjust_sub_delay(self, delta: float) -> float:
        """相对调整字幕延迟，返回新值"""
        new_delay = round(self._facade.get_sub_delay() + delta, 3)
        self._facade.set_sub_delay(new_delay)
        return new_delay

    def adjust_sub_scale(self, delta: float) -> float:
        new_scale = round(max(0.1, min(10.0, self._facade.get_sub_scale() + delta)), 2)
        self._facade.set_sub_scale(new_scale)
        return new_scale

    def apply_sub_style(self, style: dict) -> bool:
        """应用字幕样式到 mpv 属性
        style 字典支持键:
          color: 字幕颜色（#RRGGBB 或 #AARRGGBB）
          border_color: 边框颜色
          shadow_color: 阴影颜色
          font: 字体名称
          font_size: 字体大小
          border_size: 边框粗细
          shadow_offset: 阴影偏移
          bold/italic: 布尔
          margin_x/margin_y: 边距
          align_x/align_y: 对齐方式
        """
        if not self._facade.mpv_handle or self._facade._terminated:
            return False
        try:
            mapping = {
                'color': 'sub-color',
                'border_color': 'sub-border-color',
                'shadow_color': 'sub-shadow-color',
                'font': 'sub-font',
                'font_size': 'sub-font-size',
                'border_size': 'sub-border-size',
                'shadow_offset': 'sub-shadow-offset',
                'margin_x': 'sub-margin-x',
                'margin_y': 'sub-margin-y',
                'align_x': 'sub-align-x',
                'align_y': 'sub-align-y',
            }
            for key, prop in mapping.items():
                if key in style and style[key] is not None and style[key] != '':
                    self._facade._set_mpv_string(prop, str(style[key]))
            if 'bold' in style:
                self._facade._set_mpv_string('sub-bold', 'yes' if style['bold'] else 'no')
            if 'italic' in style:
                self._facade._set_mpv_string('sub-italic', 'yes' if style['italic'] else 'no')
            return True
        except Exception as e:
            self._facade.logger.error(f"应用字幕样式失败: {e}")
            return False

    def get_sub_delay(self) -> float:
        try:
            v = self._facade._get_mpv_property_double('sub-delay')
            return float(v) if v is not None else 0.0
        except Exception:
            return 0.0

    def get_sub_pos(self) -> int:
        try:
            v = self._facade._get_mpv_property_int('sub-pos')
            return int(v) if v is not None else 100
        except Exception:
            return 100

    def get_sub_scale(self) -> float:
        try:
            v = self._facade._get_mpv_property_double('sub-scale')
            return float(v) if v is not None else 1.0
        except Exception:
            return 1.0

    def get_sub_style(self) -> dict:
        """读取当前字幕样式"""
        result = {}
        try:
            for key, prop in {
                'color': 'sub-color',
                'border_color': 'sub-border-color',
                'shadow_color': 'sub-shadow-color',
                'font': 'sub-font',
                'font_size': 'sub-font-size',
                'border_size': 'sub-border-size',
                'shadow_offset': 'sub-shadow-offset',
                'margin_x': 'sub-margin-x',
                'margin_y': 'sub-margin-y',
                'align_x': 'sub-align-x',
                'align_y': 'sub-align-y',
            }.items():
                v = self._facade._get_mpv_property_string(prop)
                if v:
                    result[key] = v
            bv = self._facade._get_mpv_property_string('sub-bold')
            result['bold'] = (bv == 'yes')
            iv = self._facade._get_mpv_property_string('sub-italic')
            result['italic'] = (iv == 'yes')
        except Exception as _e:
            global_logger.debug(f"unexpected error: {_e}")
        return result

    def get_sub_visibility(self) -> bool:
        try:
            v = self._facade._get_mpv_property_string('sub-visibility')
            return v != 'no'
        except Exception:
            return True

    def set_sub_delay(self, delay: float) -> bool:
        """设置字幕延迟（秒，可负）"""
        try:
            self._facade._set_mpv_string('sub-delay', f"{delay:.3f}")
            return True
        except Exception as e:
            self._facade.logger.error(f"设置字幕延迟失败: {e}")
            return False

    def set_sub_pos(self, pos: int) -> bool:
        """设置字幕垂直位置（0-100，0=顶部，100=底部）"""
        pos = max(0, min(100, int(pos)))
        try:
            self._facade._set_mpv_string('sub-pos', f"{pos}")
            return True
        except Exception as e:
            self._facade.logger.error(f"设置字幕位置失败: {e}")
            return False

    def set_sub_scale(self, scale: float) -> bool:
        """设置字幕缩放（0.1-10.0）"""
        scale = max(0.1, min(10.0, float(scale)))
        try:
            self._facade._set_mpv_string('sub-scale', f"{scale:.2f}")
            return True
        except Exception as e:
            self._facade.logger.error(f"设置字幕缩放失败: {e}")
            return False

    def set_sub_visibility(self, visible: bool) -> bool:
        try:
            self._facade._set_mpv_string('sub-visibility', 'yes' if visible else 'no')
            return True
        except Exception as e:
            self._facade.logger.error(f"设置字幕可见性失败: {e}")
            return False

    def toggle_sub_visibility(self) -> bool:
        new_state = not self._facade.get_sub_visibility()
        self._facade.set_sub_visibility(new_state)
        return new_state

