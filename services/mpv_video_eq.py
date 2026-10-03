"""MpvVideoEq — 从 MpvPlayerController 提取的子控制器。"""

from core.log_manager import global_logger as logger


class MpvVideoEq:
    """MpvVideoEq — 通过 facade 访问 mpv 实例和播放器。"""

    def __init__(self, facade):
        self._facade = facade

    def _disable_deinterlace_filter(self):
        """禁用反交错滤镜"""
        if not self._facade.mpv_handle or self._facade._terminated:
            return
        try:
            self._facade.send_command(['vf', 'remove', '@iptv_deint'])
            self._facade.logger.info("反交错滤镜已移除")
        except Exception as _e:
            global_logger.debug(f"unexpected error: {_e}")

    def _enable_deinterlace_filter(self):
        """启用 yadif bob 反交错滤镜（mode=1，50i→50p，保持运动流畅）

        使用 vf 滤镜链的命名标签 @iptv_deint 管理，便于运行时添加/移除。
        与 mpv 的 deinterlace 属性区别：
        - deinterlace=yes：内部用 yadif mode=0（frame mode），50i→25p，帧率减半，运动卡顿
        - yadif=mode=1（field/bob mode）：50i→50p，保持原始帧率，运动流畅
        注意：lavfi/vf 滤镜需要 copy-back 硬解（hwdec=auto-copy）或软解（hwdec=no）。
        """
        if not self._facade.mpv_handle or self._facade._terminated:
            return
        try:
            self._facade.send_command(['vf', 'remove', '@iptv_deint'])
        except Exception as _e:
            global_logger.debug(f"unexpected error: {_e}")
        ret = self._facade.send_command(['vf', 'add', '@iptv_deint:yadif=mode=1'])
        if ret != 0:
            cur_hwdec = ''
            try:
                cur_hwdec = self._facade._get_mpv_property_string('hwdec') or ''
            except Exception as _e:
                global_logger.debug(f"unexpected error: {_e}")
            self._facade.logger.warning(
                f"yadif bob 反交错滤镜添加失败(ret={ret})，当前 hwdec='{cur_hwdec}'。"
                f"若为原生硬解(auto)，请在播放设置中改为 copy-back(auto-copy) 或软解(no)"
            )
        else:
            self._facade.logger.info("yadif bob 反交错滤镜已添加 (mode=1, 50i→50p)")

    def adjust_video_eq(self, key: str, delta) -> float:
        """相对调整图像参数，返回新值
        key: brightness/contrast/saturation/hue/gamma (int，步进 delta 整数)
              sharpness (float，步进 0.05)
        """
        if key in ('brightness', 'contrast', 'saturation', 'hue', 'gamma'):
            cur = getattr(self, f'get_{key}')()
            new_v = max(-100, min(100, int(cur + delta)))
            getattr(self, f'set_{key}')(new_v)
            return float(new_v)
        elif key == 'sharpness':
            cur = self._facade.get_sharpness()
            new_v = round(max(-1.0, min(1.0, cur + delta)), 3)
            self._facade.set_sharpness(new_v)
            return new_v
        return 0.0

    def apply_video_eq(self, eq: dict) -> bool:
        """批量应用图像参数（dict 可含上述 key 与 video_rotate/video_flip/crop_*）"""
        if not self._facade.mpv_handle or self._facade._terminated:
            return False
        try:
            int_keys = ('brightness', 'contrast', 'saturation', 'hue', 'gamma')
            for k in int_keys:
                if k in eq and eq[k] is not None:
                    getattr(self, f'set_{k}')(eq[k])
            if 'sharpness' in eq and eq['sharpness'] is not None:
                self._facade.set_sharpness(eq['sharpness'])
            if 'video_rotate' in eq and eq['video_rotate'] is not None:
                self._facade.set_video_rotate(int(eq['video_rotate']))
            if 'video_flip' in eq and eq['video_flip'] is not None:
                self._facade.set_video_flip(eq['video_flip'])
            if 'crop_w' in eq and 'crop_h' in eq:
                self._facade.set_video_crop(int(eq.get('crop_x', 0)), int(eq.get('crop_y', 0)),
                                    int(eq['crop_w']), int(eq['crop_h']))
            return True
        except Exception as e:
            self._facade.logger.error(f"应用视频参数失败: {e}")
            return False

    def clear_all_video_filters(self) -> bool:
        """清除所有由本程序添加的视频滤镜"""
        if not self._facade.mpv_handle or self._facade._terminated:
            return False
        for label in ('@iptv_flip', '@iptv_crop', '@iptv_360', '@iptv_mc', '@iptv_sr'):
            try:
                self._facade.send_command(['vf', 'remove', label])
            except Exception as _e:
                global_logger.debug(f"unexpected error: {_e}")
        return True

    def clear_video_crop(self) -> bool:
        """清除画面裁剪"""
        if not self._facade.mpv_handle or self._facade._terminated:
            return False
        try:
            self._facade.send_command(['vf', 'remove', '@iptv_crop'])
            return True
        except Exception:
            return False

    def get_brightness(self) -> int:
        v = self._facade._get_mpv_property_int('brightness')
        return int(v) if v is not None else 0

    def get_contrast(self) -> int:
        v = self._facade._get_mpv_property_int('contrast')
        return int(v) if v is not None else 0

    def get_gamma(self) -> int:
        v = self._facade._get_mpv_property_int('gamma')
        return int(v) if v is not None else 0

    def get_hue(self) -> int:
        v = self._facade._get_mpv_property_int('hue')
        return int(v) if v is not None else 0

    def get_saturation(self) -> int:
        v = self._facade._get_mpv_property_int('saturation')
        return int(v) if v is not None else 0

    def get_sharpness(self) -> float:
        v = self._facade._get_mpv_property_double('sharpen')
        return float(v) if v is not None else 0.0

    def get_video_eq(self) -> dict:
        """读取当前所有视频图像参数"""
        return {
            'brightness': self._facade.get_brightness(),
            'contrast': self._facade.get_contrast(),
            'saturation': self._facade.get_saturation(),
            'hue': self._facade.get_hue(),
            'gamma': self._facade.get_gamma(),
            'sharpness': self._facade.get_sharpness(),
            'video_rotate': self._facade.get_video_rotate(),
        }

    def get_video_flip(self) -> str:
        """读取当前 flip 状态"""
        try:
            vf = self._facade._get_mpv_property_string('vf')
            if not vf:
                return ''
            import json
            data = json.loads(vf) if isinstance(vf, str) else vf
            # mpv 返回的 vf JSON 结构：
            # {"vf": [{"name": "lavfi", "params": {"graph": "hflip"}, "label": "iptv_flip"}, ...]}
            # 通过 label 识别本程序添加的翻转滤镜，再解析 graph 判断方向
            for item in data.get('vf', []):
                label = item.get('label', '') or ''
                if label != 'iptv_flip':
                    continue
                name = item.get('name', '')
                if name != 'lavfi':
                    continue
                graph = (item.get('params', {}) or {}).get('graph', '') or ''
                has_hflip = 'hflip' in graph
                has_vflip = 'vflip' in graph
                if has_hflip and has_vflip:
                    return 'both'
                if has_hflip:
                    return 'horizontal'
                if has_vflip:
                    return 'vertical'
            return ''
        except Exception:
            return ''

    def get_video_rotate(self) -> int:
        v = self._facade._get_mpv_property_int('video-rotate')
        return int(v) if v is not None else 0

    def reset_video_eq(self):
        """重置图像参数为默认（0）"""
        self._facade.set_brightness(0)
        self._facade.set_contrast(0)
        self._facade.set_saturation(0)
        self._facade.set_hue(0)
        self._facade.set_gamma(0)
        self._facade.set_sharpness(0.0)

    def set_brightness(self, v: int) -> bool:
        v = max(-100, min(100, int(v)))
        return self._facade._set_mpv_string('brightness', str(v)) >= 0

    def set_contrast(self, v: int) -> bool:
        v = max(-100, min(100, int(v)))
        return self._facade._set_mpv_string('contrast', str(v)) >= 0

    def set_gamma(self, v: int) -> bool:
        v = max(-100, min(100, int(v)))
        return self._facade._set_mpv_string('gamma', str(v)) >= 0

    def set_hue(self, v: int) -> bool:
        v = max(-100, min(100, int(v)))
        return self._facade._set_mpv_string('hue', str(v)) >= 0

    def set_saturation(self, v: int) -> bool:
        v = max(-100, min(100, int(v)))
        return self._facade._set_mpv_string('saturation', str(v)) >= 0

    def set_sharpness(self, v: float) -> bool:
        v = max(-1.0, min(1.0, float(v)))
        return self._facade._set_mpv_string('sharpen', f"{v:.3f}") >= 0

    def set_video_crop(self, x: int, y: int, w: int, h: int) -> bool:
        """设置画面裁剪（x,y 起点；w,h 大小，0 表示使用视频原尺寸）"""
        if not self._facade.mpv_handle or self._facade._terminated:
            return False
        # 清除旧裁剪
        try:
            self._facade.send_command(['vf', 'remove', '@iptv_crop'])
        except Exception as _e:
            global_logger.debug(f"unexpected error: {_e}")
        if w <= 0 or h <= 0:
            return True
        # crop=w:h:x:y
        cmd = f"@iptv_crop:crop={w}:{h}:{x}:{y}"
        return self._facade.send_command(['vf', 'add', cmd]) == 0

    def set_video_flip(self, mode: str) -> bool:
        """设置画面翻转
        mode: '' / 'horizontal' / 'vertical' / 'both'
        使用 mpv 的 lavfi 滤镜包装 FFmpeg 的 hflip/vflip：
          - horizontal: lavfi=[hflip]
          - vertical:   lavfi=[vflip]
          - both:       lavfi=[hflip,vflip]  （方括号内的逗号属于 FFmpeg filter_graph，不会被 mpv 当滤镜分隔符）
        注意：lavfi 滤镜需要 copy-back 硬解（hwdec=auto-copy）或软解（hwdec=no）。
              原生硬解（hwdec=auto）下解码帧留在 GPU，lavfi 无法访问帧数据，滤镜不生效。
        """
        if not self._facade.mpv_handle or self._facade._terminated:
            return False
        # 通过 vf 滤镜实现；先清除已有 flip 滤镜，再添加新的
        try:
            self._facade.send_command(['vf', 'remove', '@iptv_flip'])
        except Exception as _e:
            global_logger.debug(f"unexpected error: {_e}")
        if not mode:
            return True
        if mode == 'horizontal':
            filter_str = 'lavfi=[hflip]'
        elif mode == 'vertical':
            filter_str = 'lavfi=[vflip]'
        elif mode == 'both':
            filter_str = 'lavfi=[hflip,vflip]'
        else:
            return False
        # 使用命名标签便于后续替换
        ret = self._facade.send_command(['vf', 'add', f'@iptv_flip:{filter_str}'])
        if ret != 0:
            # 滤镜添加失败：常见原因是原生硬解（hwdec=auto）下 lavfi 不可用
            cur_hwdec = self._facade._get_mpv_property_string('hwdec') or ''
            self._facade.logger.warning(
                f"翻转滤镜添加失败(ret={ret})，filter='{filter_str}'，当前 hwdec='{cur_hwdec}'。"
                f"若为原生硬解(auto)，请在播放设置中改为 copy-back(auto-copy) 或软解(no)"
            )
            return False
        self._facade.logger.info(f"翻转滤镜已添加: {filter_str}")
        return True

    def set_video_rotate(self, degree: int) -> bool:
        """设置画面旋转（0/90/180/270）"""
        degree = int(degree)
        if degree not in (0, 90, 180, 270):
            degree = 0
        # 通过 video-rotate 属性设置（mpv 0.27+）
        return self._facade._set_mpv_string('video-rotate', str(degree)) >= 0

