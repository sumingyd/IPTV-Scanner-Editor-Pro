import configparser
import os
import threading
from log_manager import LogManager
logger = LogManager()

class ConfigManager:
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, config_file='config.ini'):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
        
    def __init__(self, config_file='config.ini'):
        if self._initialized:
            return
            
        # 使用程序所在目录存放配置文件
        import sys
        if getattr(sys, 'frozen', False):
            # 打包成exe的情况
            config_dir = os.path.dirname(sys.executable)
        else:
            # 开发环境
            config_dir = os.path.dirname(__file__)
        self.config_file = os.path.join(config_dir, config_file)
        self.config = configparser.ConfigParser()
        self._lock = threading.Lock()
        # 初始化时立即加载已有配置
        self.load_config()
        self._initialized = True
        
    def save_window_layout(self, width, height, dividers):
        """保存窗口布局"""
        self.set_value('UI', 'window_width', str(width))
        self.set_value('UI', 'window_height', str(height))
        for i, pos in enumerate(dividers):
            self.set_value('UI', f'divider_{i}', str(pos))
        return self.save_config()  # 确保立即保存到文件
            
    def load_window_layout(self, default_width=800, default_height=600, default_dividers=None):
        """加载窗口布局"""
        width = int(self.get_value('UI', 'window_width', default_width))
        height = int(self.get_value('UI', 'window_height', default_height))
        dividers = []
        i = 0
        while True:
            pos = self.get_value('UI', f'divider_{i}')
            if pos is None:
                break
            dividers.append(int(pos))
            i += 1
        return width, height, dividers or default_dividers
        
    def save_network_settings(self, url, timeout, threads, user_agent, referer):
        """保存网络设置"""
        self.set_value('Network', 'url', url)
        self.set_value('Network', 'timeout', str(timeout))
        self.set_value('Network', 'threads', str(threads))
        self.set_value('Network', 'user_agent', user_agent)
        self.set_value('Network', 'referer', referer)
        return self.save_config()  # 确保立即保存到文件
        
    def load_network_settings(self):
        """加载网络设置"""
        return {
            'url': self.get_value('Network', 'url', ''),
            'timeout': int(self.get_value('Network', 'timeout', '30')),
            'threads': int(self.get_value('Network', 'threads', '5')),
            'user_agent': self.get_value('Network', 'user_agent', ''),
            'referer': self.get_value('Network', 'referer', '')
        }
        
    def save_language_settings(self, language_code):
        """保存语言设置"""
        self.set_value('Language', 'current_language', language_code)
        return self.save_config()
        
    def load_language_settings(self):
        """加载语言设置"""
        return self.get_value('Language', 'current_language', 'zh')
        
    def save_scan_retry_settings(self, enable_retry, loop_scan):
        """保存扫描重试设置"""
        self.set_value('ScanRetry', 'enable_retry', str(enable_retry))
        self.set_value('ScanRetry', 'loop_scan', str(loop_scan))
        return self.save_config()  # 确保立即保存到文件
        
    def load_scan_retry_settings(self):
        """加载扫描重试设置"""
        return {
            'enable_retry': self.get_value('ScanRetry', 'enable_retry', 'False').lower() == 'true',
            'loop_scan': self.get_value('ScanRetry', 'loop_scan', 'False').lower() == 'true'
        }
        
    def save_sort_config(self, sort_config):
        """保存排序配置"""
        # 保存优先级设置
        self.set_value('SortConfig', 'primary_field', sort_config['primary']['field'])
        self.set_value('SortConfig', 'primary_method', sort_config['primary']['method'])
        self.set_value('SortConfig', 'secondary_field', sort_config['secondary']['field'])
        self.set_value('SortConfig', 'secondary_method', sort_config['secondary']['method'])
        self.set_value('SortConfig', 'tertiary_field', sort_config['tertiary']['field'])
        self.set_value('SortConfig', 'tertiary_method', sort_config['tertiary']['method'])
        
        # 保存分组优先级
        group_priority = sort_config.get('group_priority', [])
        self.set_value('SortConfig', 'group_priority_count', str(len(group_priority)))
        for i, group in enumerate(group_priority):
            self.set_value('SortConfig', f'group_priority_{i}', group)
            
        return self.save_config()
        
    def load_sort_config(self):
        """加载排序配置"""
        default_config = {
            'primary': {'field': 'group', 'method': 'custom'},
            'secondary': {'field': 'name', 'method': 'alphabetical'},
            'tertiary': {'field': 'resolution', 'method': 'quality_high_to_low'},
            'group_priority': []
        }
        
        try:
            config = {
                'primary': {
                    'field': self.get_value('SortConfig', 'primary_field', 'group'),
                    'method': self.get_value('SortConfig', 'primary_method', 'custom')
                },
                'secondary': {
                    'field': self.get_value('SortConfig', 'secondary_field', 'name'),
                    'method': self.get_value('SortConfig', 'secondary_method', 'alphabetical')
                },
                'tertiary': {
                    'field': self.get_value('SortConfig', 'tertiary_field', 'resolution'),
                    'method': self.get_value('SortConfig', 'tertiary_method', 'quality_high_to_low')
                },
                'group_priority': []
            }
            
            # 加载分组优先级
            group_count = int(self.get_value('SortConfig', 'group_priority_count', '0'))
            for i in range(group_count):
                group = self.get_value('SortConfig', f'group_priority_{i}')
                if group:
                    config['group_priority'].append(group)
                    
            return config
        except Exception as e:
            logger.error(f"加载排序配置失败: {str(e)}")
            return default_config
        
    def load_config(self):
        if os.path.exists(self.config_file):
            try:
                self.config.read(self.config_file)
                return True
            except Exception as e:
                logger.error(f"配置管理-加载配置文件失败: {str(e)}", exc_info=True)
                return False
        logger.warning(f"配置管理-配置文件不存在: {self.config_file}")
        return False
        
    def save_config(self):
        try:
            with open(self.config_file, 'w') as f:
                self.config.write(f)
            return True
        except Exception as e:
            logger.error(f"配置管理-保存配置文件失败: {str(e)}", exc_info=True)
            return False
            
    def get_value(self, section, key, default=None):
        try:
            return self.config.get(section, key)
        except (configparser.NoSectionError, configparser.NoOptionError):
            return default
            
    def set_value(self, section, key, value):
        if not self.config.has_section(section):
            self.config.add_section(section)
        self.config.set(section, key, value)
