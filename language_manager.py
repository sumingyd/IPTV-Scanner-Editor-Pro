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
        # 如果已经加载过，直接返回缓存结果
        if hasattr(self, '_languages_loaded') and self._languages_loaded:
            return self.available_languages
            
        self.available_languages = {}
        try:
            # 首先尝试从打包后的路径查找
            import sys
            if getattr(sys, 'frozen', False):
                # 打包后的路径 - 尝试多个可能的路径
                base_path = os.path.dirname(sys.executable)
                
                # 尝试1: 可执行文件同目录下的locales文件夹
                locales_path = os.path.join(base_path, 'locales')
                if os.path.exists(locales_path):
                    self.locales_dir = locales_path
                    logger.info(f"使用打包后的语言目录: {locales_path}")
                else:
                    # 尝试2: _MEIPASS临时解压目录 (PyInstaller运行时)
                    if hasattr(sys, '_MEIPASS'):
                        meipass_locales = os.path.join(sys._MEIPASS, 'locales')
                        if os.path.exists(meipass_locales):
                            self.locales_dir = meipass_locales
                            logger.info(f"使用_MEIPASS语言目录: {meipass_locales}")
                    # 尝试3: 当前工作目录下的locales文件夹
                    cwd_locales = os.path.join(os.getcwd(), 'locales')
                    if os.path.exists(cwd_locales):
                        self.locales_dir = cwd_locales
                        logger.info(f"使用当前工作目录语言目录: {cwd_locales}")
            
            if not os.path.exists(self.locales_dir):
                # 如果目录不存在，尝试创建
                try:
                    os.makedirs(self.locales_dir)
                    logger.warning(f"语言目录不存在，已创建: {self.locales_dir}")
                except:
                    logger.error(f"无法创建语言目录: {self.locales_dir}")
                self._languages_loaded = True
                return self.available_languages
            
            # 查找所有json语言文件
            json_files = glob.glob(os.path.join(self.locales_dir, '*.json'))
            logger.info(f"找到语言文件: {json_files}")
            
            # 如果没有找到文件，尝试从打包资源中加载
            if not json_files and getattr(sys, 'frozen', False):
                logger.warning("未找到语言文件，尝试从打包资源加载")
                # 尝试加载内置的语言文件
                self._load_builtin_languages()
            else:
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
                            logger.info(f"成功加载语言: {lang_code} ({display_name})")
                    except Exception as e:
                        logger.error(f"加载语言文件失败 {json_file}: {str(e)}")
                    
        except Exception as e:
            logger.error(f"扫描语言文件失败: {str(e)}")
            
        logger.info(f"可用语言: {list(self.available_languages.keys())}")
        self._languages_loaded = True
        return self.available_languages

    def _load_builtin_languages(self):
        """加载内置的语言文件（用于打包环境）"""
        try:
            # 内置的语言文件数据
            builtin_languages = {
                'zh': {
                    'language_name': '中文',
                    'app_title': 'IPTV扫描编辑器专业版',
                    'video_playback': '视频播放',
                    'play': '播放',
                    'pause': '暂停',
                    'stop': '停止',
                    'volume': '音量',
                    'scan_settings': '扫描设置',
                    'address_format': '地址格式',
                    'address_example': '地址示例',
                    'input_address': '输入地址',
                    'timeout_description': '设置扫描超时时间（秒）',
                    'thread_count_description': '设置扫描线程数',
                    'user_agent': 'User-Agent',
                    'referer': 'Referer',
                    'progress': '进度',
                    'timeout': '超时',
                    'thread_count': '线程数',
                    'full_scan': '完整扫描',
                    'stop_scan': '停止扫描',
                    'generate_list': '生成列表',
                    'total_channels': '总数',
                    'valid': '有效',
                    'invalid': '无效',
                    'time_elapsed': '耗时',
                    'channel_list': '频道列表',
                    'validate_effectiveness': '检测有效性',
                    'hide_invalid': '隐藏无效项',
                    'smart_sort': '智能排序',
                    'please_load_list': '请先加载列表',
                    'channel_edit': '频道编辑',
                    'channel_name': '频道名称',
                    'channel_group': '频道分组',
                    'logo_address': 'Logo地址',
                    'channel_url': '频道URL',
                    'edit_channel': '编辑频道',
                    'add_channel': '添加频道',
                    'operation': '操作',
                    'open_list': '打开列表',
                    'save_list': '保存列表',
                    'language': '语言',
                    'about': '关于',
                    'required': '必填',
                    'optional': '可选',
                    'optional_default': '可选，为空使用默认值',
                    'optional_not_used': '可选，为空不使用',
                    'serial_number': '序号',
                    'resolution': '分辨率',
                    'status': '状态',
                    'latency_ms': '延迟(ms)'
                },
                'en': {
                    'language_name': 'English',
                    'app_title': 'IPTV Scanner Editor Pro',
                    'video_playback': 'Video Playback',
                    'play': 'Play',
                    'pause': 'Pause',
                    'stop': 'Stop',
                    'volume': 'Volume',
                    'scan_settings': 'Scan Settings',
                    'address_format': 'Address Format',
                    'address_example': 'Address Example',
                    'input_address': 'Input Address',
                    'timeout_description': 'Set scan timeout (seconds)',
                    'thread_count_description': 'Set number of scan threads',
                    'user_agent': 'User-Agent',
                    'referer': 'Referer',
                    'progress': 'Progress',
                    'timeout': 'Timeout',
                    'thread_count': 'Thread Count',
                    'full_scan': 'Full Scan',
                    'stop_scan': 'Stop Scan',
                    'generate_list': 'Generate List',
                    'total_channels': 'Total Channels',
                    'valid': 'Valid',
                    'invalid': 'Invalid',
                    'time_elapsed': 'Time Elapsed',
                    'channel_list': 'Channel List',
                    'validate_effectiveness': 'Validate Effectiveness',
                    'hide_invalid': 'Hide Invalid',
                    'smart_sort': 'Smart Sort',
                    'please_load_list': 'Please load list first',
                    'channel_edit': 'Channel Edit',
                    'channel_name': 'Channel Name',
                    'channel_group': 'Channel Group',
                    'logo_address': 'Logo Address',
                    'channel_url': 'Channel URL',
                    'edit_channel': 'Edit Channel',
                    'add_channel': 'Add Channel',
                    'operation': 'Operation',
                    'open_list': 'Open List',
                    'save_list': 'Save List',
                    'language': 'Language',
                    'about': 'About',
                    'required': 'Required',
                    'optional': 'Optional',
                    'optional_default': 'Optional, use default if empty',
                    'optional_not_used': 'Optional, not used if empty',
                    'serial_number': 'No.',
                    'resolution': 'Resolution',
                    'status': 'Status',
                    'latency_ms': 'Latency(ms)'
                }
            }
            
            for lang_code, data in builtin_languages.items():
                self.available_languages[lang_code] = {
                    'file': f'builtin:{lang_code}',
                    'display_name': data.get('language_name', lang_code),
                    'data': data
                }
                logger.info(f"成功加载内置语言: {lang_code}")
                
        except Exception as e:
            logger.error(f"加载内置语言失败: {str(e)}")
    
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
            
            # 更新映射状态标签
            if hasattr(main_window, 'mapping_status_label'):
                from channel_mappings import remote_mappings
                if remote_mappings:
                    main_window.mapping_status_label.setText(
                        self.tr('mapping_loaded', 'Remote mapping loaded')
                    )
                else:
                    main_window.mapping_status_label.setText(
                        self.tr('mapping_failed', 'Remote mapping load failed')
                    )
            
            logger.info(f"UI文本已更新到语言: {self.current_language}")
            
        except Exception as e:
            logger.error(f"更新UI文本失败: {str(e)}")
