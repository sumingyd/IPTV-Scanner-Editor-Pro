import configparser
import os

class ConfigManager:
    def __init__(self, config_file='config.ini'):
        self.config_file = os.path.join(os.path.dirname(__file__), config_file)
        self.config = configparser.ConfigParser()
        
    def load_config(self):
        if os.path.exists(self.config_file):
            self.config.read(self.config_file)
            return True
        return False
        
    def save_config(self):
        with open(self.config_file, 'w') as f:
            self.config.write(f)
            
    def get_value(self, section, key, default=None):
        try:
            return self.config.get(section, key)
        except (configparser.NoSectionError, configparser.NoOptionError):
            return default
            
    def set_value(self, section, key, value):
        if not self.config.has_section(section):
            self.config.add_section(section)
        self.config.set(section, key, value)
