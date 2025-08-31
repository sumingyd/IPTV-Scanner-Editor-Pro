import json
import os
import glob
from pathlib import Path
from log_manager import LogManager

logger = LogManager()

class LanguageManager:
    def __init__(self, locales_dir='locales'):
        self.locales_dir = locales_dir
        self.current_language = 'zh'  # 默认中文
        self.translations = {}
        self.available_languages = {}
        
    def load_available_languages(self):
        """加载所有可用的语言文件"""
        self.available_languages = {}
        try:
            if not os.path.exists(self.locales_dir):
                os.makedirs(self.locales_dir)
                logger.warning(f"语言目录不存在，已创建: {self.locales_dir}")
                return self.available_languages
            
            # 查找所有json语言文件
            json_files = glob.glob(os.path.join(self.locales_dir, '*.json'))
            for json_file in json_files:
                lang_code = Path(json_file).stem
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        # 获取语言的显示名称
                        display_name = data.get('language_name', lang_code)
                        self.available_languages[lang_code] = {
                            'file': json_file,
                            'display_name': display_name,
                            'data': data
                        }
                except Exception as e:
                    logger.error(f"加载语言文件失败 {json_file}: {str(e)}")
                    
        except Exception as e:
            logger.error(f"扫描语言文件失败: {str(e)}")
            
        return self.available_languages
    
    def set_language(self, lang_code):
        """设置当前语言"""
        if lang_code in self.available_languages:
            self.current_language = lang_code
            self.translations = self.available_languages[lang_code]['data']
            return True
        else:
            logger.warning(f"语言 {lang_code} 不可用")
            return False
    
    def get_translation(self, key, default=None):
        """获取翻译文本"""
        return self.translations.get(key, default)
    
    def tr(self, key, default=None):
        """翻译文本的快捷方法"""
        return self.get_translation(key, default)
    
    def get_language_list(self):
        """获取语言列表用于显示"""
        languages = []
        for lang_code, lang_info in self.available_languages.items():
            languages.append({
                'code': lang_code,
                'name': lang_info['display_name'],
                'file': lang_info['file']
            })
        return languages
    
    def update_ui_texts(self, main_window):
        """更新UI文本到当前语言"""
        if not self.translations:
            return
            
        try:
            # 更新窗口标题
            main_window.setWindowTitle(self.tr('app_title', 'IPTV Scanner Editor Pro'))
            
            # 更新视频播放区域
            if hasattr(main_window, 'player_group'):
                main_window.player_group.setTitle(self.tr('video_playback', 'Video Playback'))
            if hasattr(main_window, 'pause_btn'):
                main_window.pause_btn.setText(self.tr('play', 'Play'))
            if hasattr(main_window, 'stop_btn'):
                main_window.stop_btn.setText(self.tr('stop', 'Stop'))
            if hasattr(main_window, 'volume_label'):
                main_window.volume_label.setText(self.tr('volume', 'Volume'))
            
            # 更新扫描设置区域
            if hasattr(main_window, 'scan_group'):
                main_window.scan_group.setTitle(self.tr('scan_settings', 'Scan Settings'))
            if hasattr(main_window, 'address_format_label'):
                main_window.address_format_label.setText(self.tr('address_format', 'Address Format'))
            if hasattr(main_window, 'address_example_label'):
                main_window.address_example_label.setText(self.tr('address_example', 'Address Example'))
            if hasattr(main_window, 'input_address_label'):
                main_window.input_address_label.setText(self.tr('input_address', 'Input Address'))
            if hasattr(main_window, 'timeout_description_label'):
                main_window.timeout_description_label.setText(self.tr('timeout_description', 'Set scan timeout (seconds)'))
            if hasattr(main_window, 'thread_count_label'):
                main_window.thread_count_label.setText(self.tr('thread_count_description', 'Set number of scan threads'))
            if hasattr(main_window, 'user_agent_label'):
                main_window.user_agent_label.setText(self.tr('user_agent', 'User-Agent'))
            if hasattr(main_window, 'referer_label'):
                main_window.referer_label.setText(self.tr('referer', 'Referer'))
            if hasattr(main_window, 'progress_label'):
                main_window.progress_label.setText(self.tr('progress', 'Progress'))
            if hasattr(main_window, 'timeout_row_label'):
                main_window.timeout_row_label.setText(self.tr('timeout', 'Timeout') + "：")
            if hasattr(main_window, 'thread_row_label'):
                main_window.thread_row_label.setText(self.tr('thread_count', 'Thread Count') + "：")
            if hasattr(main_window, 'user_agent_row_label'):
                main_window.user_agent_row_label.setText(self.tr('user_agent', 'User-Agent') + "：")
            if hasattr(main_window, 'referer_row_label'):
                main_window.referer_row_label.setText(self.tr('referer', 'Referer') + "：")
            if hasattr(main_window, 'scan_btn'):
                main_window.scan_btn.setText(self.tr('full_scan', 'Full Scan'))
            if hasattr(main_window, 'generate_btn'):
                main_window.generate_btn.setText(self.tr('generate_list', 'Generate List'))
            if hasattr(main_window, 'detailed_stats_label'):
                # 详细统计标签需要动态更新，这里只设置初始文本
                main_window.detailed_stats_label.setText(
                    f"{self.tr('total_channels', 'Total Channels')}: 0 | "
                    f"{self.tr('valid', 'Valid')}: 0 | "
                    f"{self.tr('invalid', 'Invalid')}: 0 | "
                    f"{self.tr('time_elapsed', 'Time Elapsed')}: 0s"
                )
            
            # 更新频道列表区域
            if hasattr(main_window, 'list_group'):
                main_window.list_group.setTitle(self.tr('channel_list', 'Channel List'))
            if hasattr(main_window, 'btn_validate'):
                main_window.btn_validate.setText(self.tr('validate_effectiveness', 'Validate Effectiveness'))
            if hasattr(main_window, 'btn_hide_invalid'):
                main_window.btn_hide_invalid.setText(self.tr('hide_invalid', 'Hide Invalid'))
            if hasattr(main_window, 'btn_smart_sort'):
                main_window.btn_smart_sort.setText(self.tr('smart_sort', 'Smart Sort'))
            if hasattr(main_window, 'validate_stats_label'):
                main_window.validate_stats_label.setText(self.tr('please_load_list', 'Please load list first'))
            
            # 更新频道编辑区域
            if hasattr(main_window, 'edit_group'):
                main_window.edit_group.setTitle(self.tr('channel_edit', 'Channel Edit'))
            if hasattr(main_window, 'channel_name_label'):
                main_window.channel_name_label.setText(self.tr('channel_name', 'Channel Name'))
            if hasattr(main_window, 'channel_group_label'):
                main_window.channel_group_label.setText(self.tr('channel_group', 'Channel Group'))
            if hasattr(main_window, 'logo_address_label'):
                main_window.logo_address_label.setText(self.tr('logo_address', 'Logo Address'))
            if hasattr(main_window, 'channel_url_label'):
                main_window.channel_url_label.setText(self.tr('channel_url', 'Channel URL'))
            if hasattr(main_window, 'edit_channel_btn'):
                main_window.edit_channel_btn.setText(self.tr('edit_channel', 'Edit Channel'))
            if hasattr(main_window, 'add_channel_btn'):
                main_window.add_channel_btn.setText(self.tr('add_channel', 'Add Channel'))
            if hasattr(main_window, 'operation_label'):
                main_window.operation_label.setText(self.tr('operation', 'Operation') + ":")
            
            # 更新工具栏按钮文本
            if hasattr(main_window, 'open_action'):
                main_window.open_action.setText(f"📂 {self.tr('open_list', 'Open List')}")
            if hasattr(main_window, 'save_action'):
                main_window.save_action.setText(f"💾 {self.tr('save_list', 'Save List')}")
            if hasattr(main_window, 'language_button'):
                main_window.language_button.setText(f"🌐 {self.tr('language', 'Language')}")
            if hasattr(main_window, 'language_menu'):
                main_window.language_menu.setTitle(self.tr('language', 'Language'))
            if hasattr(main_window, 'about_action'):
                main_window.about_action.setText(f"ℹ️ {self.tr('about', 'About')}")
            
            # 更新占位符文本
            if hasattr(main_window, 'channel_name_edit'):
                main_window.channel_name_edit.setPlaceholderText(
                    self.tr('channel_name', 'Channel Name') + ' (' + self.tr('required', 'Required') + ')'
                )
            if hasattr(main_window, 'channel_group_edit'):
                main_window.channel_group_edit.setPlaceholderText(
                    self.tr('channel_group', 'Channel Group') + ' (' + self.tr('optional', 'Optional') + ')'
                )
            if hasattr(main_window, 'channel_logo_edit'):
                main_window.channel_logo_edit.setPlaceholderText(
                    self.tr('logo_address', 'Logo Address') + ' (' + self.tr('optional', 'Optional') + ')'
                )
            if hasattr(main_window, 'channel_url_edit'):
                main_window.channel_url_edit.setPlaceholderText(
                    self.tr('channel_url', 'Channel URL') + ' (' + self.tr('required', 'Required') + ')'
                )
            if hasattr(main_window, 'user_agent_input'):
                main_window.user_agent_input.setPlaceholderText(self.tr('optional_default', 'Optional, use default if empty'))
            if hasattr(main_window, 'referer_input'):
                main_window.referer_input.setPlaceholderText(self.tr('optional_not_used', 'Optional, not used if empty'))
            
            # 更新频道列表表头
            if hasattr(main_window, 'model') and main_window.model:
                main_window.model.set_language_manager(self)
            
            logger.info(f"UI文本已更新到语言: {self.current_language}")
            
        except Exception as e:
            logger.error(f"更新UI文本失败: {str(e)}")
