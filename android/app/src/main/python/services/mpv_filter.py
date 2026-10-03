"""MpvFilter — 从 MpvPlayerController 提取的子控制器。"""

from core.log_manager import global_logger as logger


class MpvFilter:
    """MpvFilter — 通过 facade 访问 mpv 实例和播放器。"""

    def __init__(self, facade):
        self._facade = facade

    def ab_loop_clear(self) -> bool:
        """清除 AB 循环"""
        ok1 = self._facade._set_mpv_string('ab-loop-a', 'no') >= 0
        ok2 = self._facade._set_mpv_string('ab-loop-b', 'no') >= 0
        return ok1 and ok2

    def ab_loop_get_status(self) -> dict:
        """读取 AB 循环状态"""
        a = self._facade._get_mpv_property_double('ab-loop-a')
        b = self._facade._get_mpv_property_double('ab-loop-b')
        # mpv 中 'no' 通常返回 None 或字符串 'no'
        a_val = None if (a is None or a == 'no') else float(a)
        b_val = None if (b is None or b == 'no') else float(b)
        return {
            'a': a_val,
            'b': b_val,
            'active': a_val is not None and b_val is not None,
        }

    def ab_loop_set_a(self) -> float:
        """将当前位置设为 A 点，返回 A 点时间（秒）"""
        pos = self._facade._get_mpv_property_double('time-pos')
        if pos is None:
            pos = 0.0
        self._facade._set_mpv_string('ab-loop-a', f"{pos:.3f}")
        return float(pos)

    def ab_loop_set_b(self) -> float:
        """将当前位置设为 B 点，返回 B 点时间（秒）"""
        pos = self._facade._get_mpv_property_double('time-pos')
        if pos is None:
            pos = 0.0
        self._facade._set_mpv_string('ab-loop-b', f"{pos:.3f}")
        return float(pos)

    def clear_360_filter(self) -> bool:
        """清除 360° 视角滤镜"""
        if not self._facade.mpv_handle or self._facade._terminated:
            return False
        try:
            self._facade.send_command(['vf', 'remove', '@iptv_360'])
            return True
        except Exception:
            return False

    def frame_back_step(self) -> bool:
        """后退一帧"""
        return self._facade.send_command(['frame-back-step']) == 0

    def frame_step(self) -> bool:
        """前进一帧（mpv 会自动暂停）"""
        return self._facade.send_command(['frame-step']) == 0

    def get_360_view(self) -> dict:
        """读取当前 360° 视角设置
        返回 {'yaw','pitch','roll','projection','active'}；滤镜不可用时 active=False
        """
        result = {'yaw': 0.0, 'pitch': 0.0, 'roll': 0.0,
                  'projection': 'equirect', 'active': False}
        if not self._facade.mpv_handle or self._facade._terminated:
            return result
        try:
            import re
            vf = self._facade._get_mpv_property_string('vf')
            if not vf:
                return result
            import json
            data = json.loads(vf) if isinstance(vf, str) else vf
            for item in data.get('vf', []):
                params = item.get('params', {})
                label = params.get('@label', '') or item.get('label', '')
                if label != '@iptv_360':
                    continue
                # lavfi 滤镜的 params 通常含 'graph' 字段
                graph = params.get('graph', '') or params.get('lavfi', '')
                if not graph:
                    continue
                m = re.search(r'e=(\w+)', graph)
                if m:
                    result['projection'] = m.group(1)
                m = re.search(r'yaw=(-?[\d.]+)', graph)
                if m:
                    result['yaw'] = float(m.group(1))
                m = re.search(r'pitch=(-?[\d.]+)', graph)
                if m:
                    result['pitch'] = float(m.group(1))
                m = re.search(r'roll=(-?[\d.]+)', graph)
                if m:
                    result['roll'] = float(m.group(1))
                result['active'] = True
                break
        except Exception as _e:
            global_logger.debug(f"unexpected error: {_e}")
        return result

    def get_loop_file(self) -> str:
        return self._facade._get_mpv_property_string('loop-file') or 'no'

    def get_loop_playlist(self) -> str:
        return self._facade._get_mpv_property_string('loop-playlist') or 'no'

    def get_video_stereo_mode(self) -> str:
        """读取当前 3D 立体模式"""
        v = self._facade._get_mpv_property_string('video-stereo-mode')
        if v and v in self._facade._STEREO_MODES:
            return v
        return 'mono'

    def set_360_view(self, yaw: float, pitch: float, roll: float,
                     projection: str = 'equirect') -> bool:
        """设置 360° 视频视角
        yaw:   -180~180 度（偏航）
        pitch:  -90~ 90 度（俯仰）
        roll:  -180~180 度（滚转）
        projection: 'flat' / 'equirect' / 'cubemap'
        返回成功与否；滤镜不可用时返回 False
        """
        if not self._facade.mpv_handle or self._facade._terminated:
            return False
        if projection not in self._facade._360_PROJECTIONS:
            projection = 'equirect'
        yaw = max(-180.0, min(180.0, float(yaw)))
        pitch = max(-90.0, min(90.0, float(pitch)))
        roll = max(-180.0, min(180.0, float(roll)))
        # 移除旧滤镜
        try:
            self._facade.send_command(['vf', 'remove', '@iptv_360'])
        except Exception as _e:
            global_logger.debug(f"unexpected error: {_e}")
        # 全 0 视角等同于无滤镜
        if yaw == 0.0 and pitch == 0.0 and roll == 0.0:
            return True
        # 构建 lavfi panorama 滤镜
        cmd = (f"@iptv_360:lavfi=[panorama=e={projection}:"
               f"yaw={yaw:.3f}:pitch={pitch:.3f}:roll={roll:.3f}]")
        return self._facade.send_command(['vf', 'add', cmd]) == 0

    def set_loop_file(self, mode: str) -> bool:
        """设置单文件循环模式
        mode: 'no' / 'inf' / 'yes' 或 'once'
        """
        if mode not in ('no', 'inf', 'yes', 'once'):
            mode = 'no'
        if mode == 'once':
            mode = '1'
        return self._facade._set_mpv_string('loop-file', mode) >= 0

    def set_loop_playlist(self, mode: str) -> bool:
        """设置播放列表循环模式（'no' / 'inf' / 'force'）"""
        if mode not in ('no', 'inf', 'force'):
            mode = 'no'
        return self._facade._set_mpv_string('loop-playlist', mode) >= 0

    def set_video_stereo_mode(self, mode: str) -> bool:
        """设置 3D 立体显示模式
        mode: 'mono' / 'sbs' / 'sbs2' / 'ab' / 'ab2'
        """
        if not self._facade.mpv_handle or self._facade._terminated:
            return False
        if mode not in self._facade._STEREO_MODES:
            mode = 'mono'
        return self._facade._set_mpv_string('video-stereo-mode', mode) >= 0

