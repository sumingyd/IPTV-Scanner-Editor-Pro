import configparser
import os
from log_manager import LogManager
logger = LogManager()

class ConfigManager:
    def __init__(self, config_file='config.ini'):
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
        # 初始化时立即加载已有配置
        self.load_config()
        
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
