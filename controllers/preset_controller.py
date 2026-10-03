"""PresetController — 从 MediaController 提取的子控制器。"""

from core.log_manager import global_logger as logger
from utils.thread_safety import safe_single_shot
from utils.delay_constants import DelayMs


class PresetController:
    """PresetController — 通过 facade 访问主窗口和播放器。"""

    def __init__(self, facade):
        self._facade = facade

    def apply_custom_preset(self, name: str):
        """应用指定预设"""
        try:
            from services.preset_manager_service import get_preset_manager
            pm = get_preset_manager()
            settings = pm.get_preset(name)
            if not settings:
                logger.warning(f"预设 '{name}' 不存在")
                return
            pc = self._facade.window.player_controller
            if pc and pc.is_playing:
                # 应用图像参数
                eq_keys = ('brightness', 'contrast', 'saturation', 'hue',
                           'gamma', 'sharpness', 'video_rotate', 'video_flip')
                eq = {k: settings[k] for k in eq_keys if k in settings}
                if eq:
                    pc.apply_video_eq(eq)
                # 应用运动补偿
                mc_strength = settings.get('motion_comp', 'off')
                mc_fps = int(settings.get('motion_comp_fps', 60))
                if hasattr(pc, 'set_motion_compensation'):
                    pc.set_motion_compensation(mc_strength, mc_fps)
                # 应用分辨率提升
                sr_scale = settings.get('superres_scale', 'off')
                sr_detail = int(settings.get('superres_detail', 0))
                if hasattr(pc, 'set_super_resolution'):
                    pc.set_super_resolution(sr_scale, sr_detail)
                # 应用着色器
                shader = settings.get('shader_preset', 'off')
                if hasattr(pc, 'set_user_shader'):
                    pc.set_user_shader(shader)
            tr = self._facade.window.language_manager.tr
            if hasattr(self._facade.window, '_show_osd_feedback'):
                self._facade.window._show_osd_feedback(
                    f"{tr('preset_applied', '预设已应用')}: {name}"
                )
        except Exception as e:
            logger.error(f"应用预设失败: {e}")

    def apply_smart_preset(self, preset_name: str):
        """应用智能预设

        :param preset_name: 'auto' / 'performance' / 'quality' / 'anime' / 'sports'
        """
        try:
            from services.hardware_detect_service import get_hardware_detect_service
            hw = get_hardware_detect_service()
            if preset_name == 'auto':
                settings = hw.get_recommended_settings()
            elif preset_name == 'performance':
                settings = {
                    'motion_comp': 'off', 'motion_comp_fps': 60,
                    'superres_scale': 'bilinear', 'superres_detail': 0,
                    'shader_preset': 'off',
                }
            elif preset_name == 'quality':
                settings = {
                    'motion_comp': 'medium', 'motion_comp_fps': 60,
                    'superres_scale': 'ewa_lanczossharp', 'superres_detail': 40,
                    'shader_preset': 'auto',
                }
            elif preset_name == 'anime':
                settings = {
                    'motion_comp': 'low', 'motion_comp_fps': 60,
                    'superres_scale': 'ewa_lanczos', 'superres_detail': 20,
                    'shader_preset': 'anime4k',
                }
            elif preset_name == 'sports':
                settings = {
                    'motion_comp': 'high', 'motion_comp_fps': 60,
                    'superres_scale': 'lanczos', 'superres_detail': 30,
                    'shader_preset': 'off',
                }
            else:
                return
            # 应用各项设置
            self._facade.set_motion_compensation(
                settings['motion_comp'], settings['motion_comp_fps']
            )
            self._facade.set_super_resolution(
                settings['superres_scale'], settings['superres_detail']
            )
            shader = settings.get('shader_preset', 'off')
            if shader == 'auto':
                # auto 模式：检查是否有可用着色器
                pc = self._facade.window.player_controller
                if pc and hasattr(pc, 'list_available_shaders'):
                    available = pc.list_available_shaders()
                    if available:
                        shader = available[0]['preset']
                    else:
                        shader = 'off'
                else:
                    shader = 'off'
            self._facade.set_user_shader(shader)
            # 保存到配置
            tr = self._facade.window.language_manager.tr
            if hasattr(self._facade.window, '_show_osd_feedback'):
                preset_labels = {
                    'auto': tr('preset_auto', '智能推荐'),
                    'performance': tr('preset_performance', '性能优先'),
                    'quality': tr('preset_quality', '画质优先'),
                    'anime': tr('preset_anime', '动画优化'),
                    'sports': tr('preset_sports', '体育直播'),
                }
                label = preset_labels.get(preset_name, preset_name)
                self._facade.window._show_osd_feedback(
                    f"{tr('osd_smart_preset', '智能预设')}: {label}"
                )
        except Exception as e:
            logger.error(f"应用智能预设失败: {e}")

    def bind_channel_preset(self, channel_name: str, preset_name: str) -> bool:
        """绑定频道到预设"""
        try:
            from services.preset_manager_service import get_preset_manager
            pm = get_preset_manager()
            return pm.bind_channel_preset(channel_name, preset_name)
        except Exception as e:
            logger.error(f"绑定频道预设失败: {e}")
            return False

    def delete_custom_preset(self, name: str) -> bool:
        """删除自定义预设"""
        try:
            from services.preset_manager_service import get_preset_manager
            pm = get_preset_manager()
            return pm.delete_preset(name)
        except Exception as e:
            logger.error(f"删除预设失败: {e}")
            return False

    def export_presets(self, file_path: str) -> bool:
        """导出预设到文件"""
        try:
            from services.preset_manager_service import get_preset_manager
            pm = get_preset_manager()
            return pm.export_presets(file_path)
        except Exception as e:
            logger.error(f"导出预设失败: {e}")
            return False

    def get_channel_preset(self, channel_name: str):
        """获取频道绑定的预设名"""
        try:
            from services.preset_manager_service import get_preset_manager
            pm = get_preset_manager()
            return pm.get_channel_preset(channel_name)
        except Exception:
            return None

    def import_presets(self, file_path: str, overwrite: bool = False) -> int:
        """从文件导入预设"""
        try:
            from services.preset_manager_service import get_preset_manager
            pm = get_preset_manager()
            count = pm.import_presets(file_path, overwrite)
            tr = self._facade.window.language_manager.tr
            if hasattr(self._facade.window, '_show_osd_feedback') and count > 0:
                self._facade.window._show_osd_feedback(
                    f"{tr('presets_imported', '已导入')} {count} {tr('presets_count', '个预设')}"
                )
            return count
        except Exception as e:
            logger.error(f"导入预设失败: {e}")
            return 0

    def list_custom_presets(self) -> list:
        """列出所有预设"""
        try:
            from services.preset_manager_service import get_preset_manager
            pm = get_preset_manager()
            return pm.list_presets(include_builtin=True)
        except Exception as e:
            logger.error(f"列出预设失败: {e}")
            return []

    def save_custom_preset(self, name: str, settings: dict,
                           description: str = '') -> bool:
        """保存自定义预设"""
        try:
            from services.preset_manager_service import get_preset_manager
            pm = get_preset_manager()
            return pm.save_preset(name, settings, description)
        except Exception as e:
            logger.error(f"保存预设失败: {e}")
            return False

