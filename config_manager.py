import configparser
import os
from epg_model import EPGSource, EPGConfig

class ConfigManager:
    def __init__(self, config_file='config.ini'):
        self.config_file = os.path.abspath(os.path.join(os.path.dirname(__file__), config_file))
        self.config = configparser.ConfigParser()
        if not os.path.exists(os.path.dirname(self.config_file)):
            os.makedirs(os.path.dirname(self.config_file))
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
            self.config.read(self.config_file)
            return True
        return False
        
    def save_config(self):
        try:
            with open(self.config_file, 'w') as f:
                self.config.write(f)
            return True
        except Exception as e:
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

    def save_epg_config(self, epg_config):
        """保存EPG配置"""
        # 清除旧的EPG配置
        if self.config.has_section('EPG'):
            self.config.remove_section('EPG')
        
        # 添加新的EPG配置
        self.config.add_section('EPG')
        self.set_value('EPG', 'merge_sources', '1' if epg_config.merge_sources else '0')
        self.set_value('EPG', 'local_file', epg_config.local_file)
        
        # 保存主EPG源
        primary_sources = [s for s in epg_config.sources if s.is_primary]
        if primary_sources:
            self.set_value('EPG', 'primary_url', primary_sources[0].url)
        
        # 保存备用EPG源（按顺序保存）
        secondary_sources = [s for s in epg_config.sources if not s.is_primary]
        for i, source in enumerate(secondary_sources):
            self.set_value('EPG', f'secondary_{i}_url', source.url)
        
        return self.save_config()

    def load_epg_config(self):
        """加载EPG配置"""
        if not self.config.has_section('EPG'):
            return EPGConfig(
                sources=[],
                merge_sources=False,
                local_file='epg.xml'
            )
            
        sources = []
        # 加载主EPG源
        primary_url = self.get_value('EPG', 'primary_url')
        if primary_url:
            sources.append(EPGSource(url=primary_url, is_primary=True))
        
        # 加载备用EPG源
        i = 0
        while True:
            url = self.get_value('EPG', f'secondary_{i}_url')
            if url is None:  # 明确检查None而不是隐式bool转换
                break
            sources.append(EPGSource(url=url))
            i += 1
        
        # 处理合并选项
        merge_val = self.get_value('EPG', 'merge_sources')
        merge_sources = merge_val == '1' if merge_val is not None else False
        
        return EPGConfig(
            sources=sources,
            merge_sources=merge_sources,
            local_file=self.get_value('EPG', 'local_file', 'epg.xml')
        )
