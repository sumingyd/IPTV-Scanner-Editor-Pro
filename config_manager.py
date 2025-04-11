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

    def save_prefs(self, prefs: dict) -> None:
        """保存用户偏好设置
        Args:
            prefs: 包含所有偏好设置的字典，结构为:
                {
                    'window': {
                        'geometry': str,
                        'splitters': {
                            'left': list[int],
                            'right': list[int], 
                            'main': list[int],
                            'h': list[int]
                        }
                    },
                    'scanner': {
                        'address': str,
                        'timeout': int,
                        'thread_count': int,
                        'user_agent': str,
                        'referer': str
                    },
                    'player': {
                        'hardware_accel': str,
                        'volume': int
                    }
                }
        """
        try:
            # 保存窗口几何信息
            if 'window' in prefs:
                if 'geometry' in prefs['window']:
                    self.config['UserPrefs']['window_geometry'] = prefs['window']['geometry']
                
                if 'splitters' in prefs['window']:
                    splitters = prefs['window']['splitters']
                    if 'left' in splitters:
                        self.config['Splitters']['left_splitter'] = ','.join(map(str, splitters['left']))
                    if 'right' in splitters:
                        self.config['Splitters']['right_splitter'] = ','.join(map(str, splitters['right']))
                    if 'main' in splitters:
                        self.config['Splitters']['main_splitter'] = ','.join(map(str, splitters['main']))
                    if 'h' in splitters:
                        self.config['Splitters']['h_splitter'] = ','.join(map(str, splitters['h']))

            # 保存扫描配置
            if 'scanner' in prefs:
                scanner = prefs['scanner']
                if 'address' in scanner:
                    self.config['Scanner']['scan_address'] = scanner['address']
                if 'timeout' in scanner:
                    self.config['Scanner']['timeout'] = str(scanner['timeout'])
                if 'thread_count' in scanner:
                    self.config['Scanner']['thread_count'] = str(scanner['thread_count'])
                if 'user_agent' in scanner:
                    self.config['Scanner']['user_agent'] = scanner['user_agent']
                if 'referer' in scanner:
                    self.config['Scanner']['referer'] = scanner['referer']

            # 保存播放器配置
            if 'player' in prefs:
                player = prefs['player']
                if 'hardware_accel' in player:
                    self.config['Player']['hardware_accel'] = player['hardware_accel']
                if 'volume' in player:
                    self.config['Player']['volume'] = str(player['volume'])

            self.save_config()
        except Exception as e:
            raise

    def get_config_value(self, section: str, key: str, default=None):
        """获取配置值"""
        try:
            return self.config.get(section, key, fallback=default)
        except Exception:
            return default

    def get_window_prefs(self) -> dict:
        """获取窗口偏好设置"""
        return {
            'geometry': self.config.get('UserPrefs', 'window_geometry', fallback=''),
            'splitters': {
                'left': self.config.get('Splitters', 'left_splitter', fallback=''),
                'right': self.config.get('Splitters', 'right_splitter', fallback=''),
                'main': self.config.get('Splitters', 'main_splitter', fallback=''),
                'h': self.config.get('Splitters', 'h_splitter', fallback='')
            }
        }

    def get_scanner_prefs(self) -> dict:
        """获取扫描器偏好设置"""
        return {
            'address': self.config.get('Scanner', 'scan_address', fallback=''),
            'timeout': self.config.getint('Scanner', 'timeout', fallback=10),
            'thread_count': self.config.getint('Scanner', 'thread_count', fallback=10),
            'user_agent': self.config.get('Scanner', 'user_agent', fallback=''),
            'referer': self.config.get('Scanner', 'referer', fallback='')
        }

    def get_player_prefs(self) -> dict:
        """获取播放器偏好设置"""
        return {
            'hardware_accel': self.config.get('Player', 'hardware_accel', fallback='d3d11va'),
            'volume': self.config.getint('Player', 'volume', fallback=50)
        }
