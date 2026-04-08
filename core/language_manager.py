import json
import os
import glob
from pathlib import Path
from core.log_manager import LogManager
from PyQt6.QtCore import QObject, pyqtSignal

logger = LogManager()


class LanguageManager(QObject):
    # 定义语言切换信号
    language_changed = pyqtSignal()

    def __init__(self, locales_dir='locales'):
        super().__init__()
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
                else:
                    # 尝试2: _MEIPASS临时解压目录 (PyInstaller运行时)
                    if hasattr(sys, '_MEIPASS'):
                        meipass_locales = os.path.join(sys._MEIPASS, 'locales')
                        if os.path.exists(meipass_locales):
                            self.locales_dir = meipass_locales
                    # 尝试3: 当前工作目录下的locales文件夹
                    cwd_locales = os.path.join(os.getcwd(), 'locales')
                    if os.path.exists(cwd_locales):
                        self.locales_dir = cwd_locales

            if not os.path.exists(self.locales_dir):
                # 如果目录不存在，尝试创建
                try:
                    os.makedirs(self.locales_dir)
                    logger.warning(f"语言目录不存在，已创建: {self.locales_dir}")
                except OSError as e:
                    logger.error(f"无法创建语言目录 {self.locales_dir}: {e}")
                except Exception as e:
                    logger.error(f"创建语言目录时发生意外错误: {e}")
                self._languages_loaded = True
                return self.available_languages

            # 查找所有json语言文件
            json_files = glob.glob(os.path.join(self.locales_dir, '*.json'))

            # 如果没有找到文件，加载内置的语言文件
            if not json_files:
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
                    except Exception as e:
                        logger.error(f"加载语言文件失败 {json_file}: {str(e)}")

        except Exception as e:
            logger.error(f"扫描语言文件失败: {str(e)}")

        # 整合日志：记录加载结果
        if self.available_languages:
            loaded_languages = list(self.available_languages.keys())
            logger.info(f"成功加载 {len(loaded_languages)} 种语言: {', '.join(loaded_languages)}")
        else:
            logger.warning("未找到可用的语言文件")

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
                    'latency_ms': '延迟(ms)',
                    'tvg_id': 'TVG-ID',
                    'tvg_chno': 'TVG频道号',
                    'tvg_shift': 'TVG时移',
                    'catchup': '回看',
                    'catchup_days': '回看天数',
                    'catchup_source': '回看源',
                    'about_dialog_title': '关于 IPTV Scanner Editor Pro',
                    'current_version': '当前版本',
                    'latest_version': '最新版本',
                    'build_date': '编译日期',
                    'qt_version': 'QT版本',
                    'close_button': '关闭',
                    'checking_update': '检测中...',
                    'update_timeout': '请求超时',
                    'update_failed': '获取失败',
                    'api_limit': 'API限制',
                    'update_progress_title': '在线更新',
                    'update_checking': '正在检查更新...',
                    'update_downloading': '正在下载更新...',
                    'update_complete': '更新下载完成，请重启应用',
                    'update_error': '更新失败',
                    'network_error': '网络错误',
                    'feature_intro': '主要功能说明',
                    'smart_scan': '智能频道扫描',
                    'advanced_validation': '高级流验证',
                    'intelligent_management': '智能频道管理',
                    'integrated_playback': '集成视频播放',
                    'advanced_config': '高级配置管理',
                    'professional_tools': '专业工具集成',
                    'usage_method': '使用方法',
                    'scan_usage': '在扫描设置中输入地址格式，点击"完整扫描"开始',
                    'validation_usage': '打开播放列表后点击"检测有效性"按钮',
                    'management_usage': '右键频道列表或拖拽调整顺序',
                    'playback_usage': '双击频道列表中的任意频道',
                    'config_usage': '所有设置自动保存，无需手动操作',
                    'tools_usage': '通过工具栏访问各专业工具',
                    'cancel_button': '取消',
                    'update_complete': '更新下载完成，请重启应用',
                    'update_success': '更新完成',
                    'file': '文件',
                    'edit': '编辑',
                    'view': '视图',
                    'tools': '工具',
                    'help': '帮助',
                    'new_playlist': '新建播放列表',
                    'open_playlist': '打开播放列表',
                    'save_playlist': '保存播放列表',
                    'save_as': '另存为...',
                    'import_channels': '导入频道',
                    'export_channels': '导出频道',
                    'exit': '退出',
                    'undo': '撤销',
                    'redo': '重做',
                    'select_all': '全选',
                    'delete_selected': '删除选中',
                    'add_channel': '添加频道',
                    'show_epg': '显示节目单',
                    'show_playlist': '显示播放列表',
                    'fullscreen': '全屏模式',
                    'refresh': '刷新',
                    'reset_layout': '重置布局',
                    'scan_channels': '扫描频道',
                    'verify_channels': '验证频道',
                    'smart_sort': '智能排序',
                    'hide_invalid': '隐藏无效项',
                    'restore_hidden': '恢复隐藏项',
                    'channel_management': '频道管理',
                    'channel_mapping': '频道映射',
                    'favorite_management': '收藏管理',
                    'network_settings': '网络设置',
                    'player_settings': '播放器设置',
                    'usage_instructions': '使用说明',
                    'about': '关于',
                    'language': '语言',
                    'chinese': '中文',
                    'english': 'English',
                    'loading_channels': '正在加载频道...',
                    'channels_loaded': '成功加载 {count} 个频道',
                    'file_format_error': '文件格式不正确或为空',
                    'open_file_error': '打开文件失败: {error}',
                    'save_success': '保存成功',
                    'save_error': '保存文件失败: {error}',
                    'no_content': '没有可保存的内容',
                    'file_selection_error': '文件选择失败: {error}',
                    'app_name': 'IPTV Scanner Editor Pro',
                    'version': '版本 1.0.0',
                    'description': 'IPTV 频道扫描和编辑工具',
                    'usage_title': '使用说明',
                    'usage_content': '1. 点击\'文件\'菜单打开播放列表\n2. 选择频道开始播放\n3. 使用工具栏控制播放\n4. 点击\'工具\'菜单扫描和验证频道',
                    'about_title': '关于',
                    'about_content': 'IPTV Scanner Editor Pro\n版本 1.0.0\n\nIPTV 频道扫描和编辑工具\n\n© 2026 IPTV Scanner Editor Pro',
                    'epg_title': '节目单',
                    'channel_list': '频道列表',
                    'not_playing': '未播放',
                    'language_changed': '语言已切换'
            },
                'en': {
                    'language_name': 'English',
                    'app_title': 'IPTV Scanner Editor Pro',
                    'app_title_zh': 'IPTV 专业扫描编辑工具',
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
                    'latency_ms': 'Latency(ms)',
                    'tvg_id': 'TVG-ID',
                    'tvg_chno': 'TVG Channel No.',
                    'tvg_shift': 'TVG Shift',
                    'catchup': 'Catchup',
                    'catchup_days': 'Catchup Days',
                    'catchup_source': 'Catchup Source',
                    'about_dialog_title': 'About IPTV Scanner Editor Pro',
                    'current_version': 'Current Version',
                    'latest_version': 'Latest Version',
                    'build_date': 'Build Date',
                    'qt_version': 'QT Version',
                    'close_button': 'Close',
                    'checking_update': 'Checking...',
                    'update_timeout': 'Request Timeout',
                    'update_failed': 'Failed to Fetch',
                    'api_limit': 'API Limit',
                    'update_progress_title': 'Online Update',
                    'update_checking': 'Checking for updates...',
                    'update_downloading': 'Downloading update...',
                    'update_complete': 'Update downloaded, please restart the application',
                    'update_error': 'Update Failed',
                    'network_error': 'Network Error',
                    'feature_intro': 'Main Features',
                    'smart_scan': 'Smart Channel Scanning',
                    'advanced_validation': 'Advanced Stream Validation',
                    'intelligent_management': 'Intelligent Channel Management',
                    'integrated_playback': 'Integrated Video Playback',
                    'advanced_config': 'Advanced Configuration Management',
                    'professional_tools': 'Professional Tools Integration',
                    'usage_method': 'Usage Method',
                'scan_usage': 'Enter address format in scan settings, click "Full Scan" to start',
                'validation_usage': 'Open playlist and click "Validate Effectiveness" button',
                'management_usage': 'Right-click channel list or drag to adjust order',
                'playback_usage': 'Double-click any channel in the channel list',
                'config_usage': 'All settings are automatically saved, no manual operation required',
                'tools_usage': 'Access professional tools through the toolbar',
                'file': 'File',
                'edit': 'Edit',
                'view': 'View',
                'tools': 'Tools',
                'help': 'Help',
                'new_playlist': 'New Playlist',
                'open_playlist': 'Open Playlist',
                'save_playlist': 'Save Playlist',
                'save_as': 'Save As...',
                'import_channels': 'Import Channels',
                'export_channels': 'Export Channels',
                'exit': 'Exit',
                'undo': 'Undo',
                'redo': 'Redo',
                'select_all': 'Select All',
                'delete_selected': 'Delete Selected',
                'add_channel': 'Add Channel',
                'show_epg': 'Show EPG',
                'show_playlist': 'Show Playlist',
                'fullscreen': 'Fullscreen',
                'refresh': 'Refresh',
                'reset_layout': 'Reset Layout',
                'scan_channels': 'Scan Channels',
                'verify_channels': 'Verify Channels',
                'smart_sort': 'Smart Sort',
                'hide_invalid': 'Hide Invalid',
                'restore_hidden': 'Restore Hidden',
                'channel_management': 'Channel Management',
                'channel_mapping': 'Channel Mapping',
                'favorite_management': 'Favorite Management',
                'network_settings': 'Network Settings',
                'player_settings': 'Player Settings',
                'usage_instructions': 'Usage Instructions',
                'about': 'About',
                'language': 'Language',
                'chinese': '中文',
                'english': 'English',
                'loading_channels': 'Loading channels...',
                'channels_loaded': 'Successfully loaded {count} channels',
                'file_format_error': 'File format is incorrect or empty',
                'open_file_error': 'Failed to open file: {error}',
                'save_success': 'Save successful',
                'save_error': 'Failed to save file: {error}',
                'no_content': 'No content to save',
                'file_selection_error': 'File selection failed: {error}',
                'app_name': 'IPTV Scanner Editor Pro',
                'version': 'Version 1.0.0',
                'description': 'IPTV channel scanning and editing tool',
                'usage_title': 'Usage Instructions',
                'usage_content': '1. Click \'File\' menu to open playlist\n2. Select channel to start playing\n3. Use toolbar to control playback\n4. Click \'Tools\' menu to scan and verify channels',
                'about_title': 'About',
                'about_content': 'IPTV Scanner Editor Pro\nVersion 1.0.0\n\nIPTV channel scanning and editing tool\n\n© 2026 IPTV Scanner Editor Pro',
                'epg_title': 'Program Guide',
                'channel_list': 'Channel List',
                'not_playing': 'Not playing',
                'language_changed': 'Language changed'
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
            # 发出语言切换信号
            self.language_changed.emit()
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
            # 更新窗口标题（包含版本号）
            from ui.dialogs.about_dialog import AboutDialog
            version = AboutDialog.CURRENT_VERSION
            if self.current_language == 'zh':
                main_window.setWindowTitle(f"IPTV 专业扫描编辑工具 v{version}")
            else:
                main_window.setWindowTitle(f"IPTV Scanner Editor Pro v{version}")

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
                main_window.timeout_description_label.setText(
                    self.tr('timeout_description', 'Set scan timeout (seconds)'))
            if hasattr(main_window, 'thread_count_label'):
                main_window.thread_count_label.setText(
                    self.tr('thread_count_description', 'Set number of scan threads'))
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
                # 根据扫描状态设置正确的按钮文本
                if hasattr(main_window, 'scanner') and main_window.scanner.is_scanning():
                    main_window.scan_btn.setText(self.tr('stop_scan', 'Stop Scan'))
                else:
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
            if hasattr(main_window, 'btn_sort_config'):
                main_window.btn_sort_config.setText(self.tr('sort_config_button', 'Sort Config'))
            if hasattr(main_window, 'validate_stats_label'):
                main_window.validate_stats_label.setText(self.tr('please_load_list', 'Please load list first'))

            # 更新频道编辑区域
            if hasattr(main_window, 'edit_group') and hasattr(main_window.edit_group, 'setTitle'):
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
            if hasattr(main_window, 'mapping_action'):
                main_window.mapping_action.setText(f"🗺️ {self.tr('mapping_manager', 'Channel Mapping Manager')}")

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
                main_window.user_agent_input.setPlaceholderText(
                    self.tr('optional_default', 'Optional, use default if empty'))
            if hasattr(main_window, 'referer_input'):
                main_window.referer_input.setPlaceholderText(
                    self.tr('optional_not_used', 'Optional, not used if empty'))

            # 更新频道列表表头
            if hasattr(main_window, 'model') and main_window.model:
                main_window.model.set_language_manager(self)

            # 更新映射状态标签
            if hasattr(main_window, 'mapping_status_label'):
                from models.channel_mappings import mapping_manager
                if mapping_manager.remote_mappings:
                    main_window.mapping_status_label.setText(
                        self.tr('mapping_loaded', 'Remote mapping loaded')
                    )
                else:
                    main_window.mapping_status_label.setText(
                        self.tr('mapping_failed', 'Remote mapping load failed')
                    )

            # 更新重试扫描选项
            if hasattr(main_window, 'retry_label'):
                main_window.retry_label.setText(self.tr('retry_options', 'Scan Retry Options') + "：")
            if hasattr(main_window, 'enable_retry_checkbox'):
                main_window.enable_retry_checkbox.setText(self.tr('enable_retry_scan', 'Enable Retry Scan'))
                main_window.enable_retry_checkbox.setToolTip(
                    self.tr('retry_scan_tooltip', 'After the first scan completes, retry scanning failed channels'))
            if hasattr(main_window, 'loop_scan_checkbox'):
                main_window.loop_scan_checkbox.setText(self.tr('loop_scan', 'Loop Scan'))
                main_window.loop_scan_checkbox.setToolTip(
                    self.tr('loop_scan_tooltip',
                            'If retry scan finds valid channels, continue scanning failed channels '
                            'until no new valid channels are found'))
            if hasattr(main_window, 'retry_row_label'):
                main_window.retry_row_label.setText(self.tr('retry_options', 'Scan Retry Options') + "：")

            # 更新频道列表拖拽提示
            if hasattr(main_window, 'ui') and hasattr(main_window.ui, 'update_channel_drag_hint'):
                main_window.ui.update_channel_drag_hint()

            # 更新所有打开的关于对话框
            self._update_about_dialogs(main_window)

            logger.info(f"UI文本已更新到语言: {self.current_language}")

        except Exception as e:
            logger.error(f"更新UI文本失败: {str(e)}")

    def _update_about_dialogs(self, main_window):
        """更新所有打开的关于对话框"""
        try:
            # 导入QtWidgets模块
            from PyQt6 import QtWidgets

            # 查找所有打开的关于对话框
            for widget in main_window.findChildren(QtWidgets.QDialog):
                if hasattr(widget, 'update_ui_texts'):
                    widget.update_ui_texts()
        except Exception as e:
            logger.debug(f"更新关于对话框失败: {e}")
