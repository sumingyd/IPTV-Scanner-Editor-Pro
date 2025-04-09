import configparser
from pathlib import Path
import os
import sys

class ConfigHandler:
    """配置处理器"""
    def __init__(self):
        self.config = configparser.ConfigParser()
        self.config_file = self._get_config_path()
        self._load_config()

    def _get_config_path(self) -> Path:
        """获取配置文件路径"""
        if getattr(sys, 'frozen', False):
            # 打包环境下使用sys.executable所在目录
            base_dir = Path(sys.executable).parent
        else:
            # 开发环境下使用当前文件所在目录
            base_dir = Path(__file__).parent
        
        return base_dir / '.iptv_manager.ini'

    def _load_config(self) -> None:
        """加载配置文件"""
        if not self.config_file.exists():
            self._create_default_config()
        else:
            try:
                self.config.read(self.config_file, encoding='utf-8')
            except Exception as e:
                print(f"加载配置文件失败: {str(e)}")
                self._create_default_config()

    def _create_default_config(self) -> None:
        """创建默认配置文件"""
        self.config['Scanner'] = {
            'timeout': '10',
            'ffprobe_path': str(Path(__file__).parent / 'ffmpeg' / 'bin' / 'ffprobe.exe'),
            'thread_count': '10'
        }
        self.config['EPG'] = {
            'main_url': '',
            'backup_urls': '',
            'cache_ttl': '3600'
        }
        self.save_config()

    def save_config(self) -> None:
        """保存配置文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                self.config.write(f)
        except Exception as e:
            print(f"保存配置文件失败: {str(e)}")

    def get_config_value(self, section: str, key: str, default=None):
        """获取配置值"""
        try:
            return self.config.get(section, key, fallback=default)
        except Exception:
            return default
