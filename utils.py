import logging
import configparser
import platform
import re
import subprocess
from pathlib import Path
from typing import List, Tuple, Dict, Any
from itertools import product

logger = logging.getLogger('Utils')

class ConfigHandler:
    _instance = None
    
    def __new__(cls):
        if not cls._instance:
            cls._instance = super().__new__(cls)
            cls._instance._initialize_config()
        return cls._instance
    
    def _initialize_config(self) -> None:
        """安全初始化配置"""
        self.config = configparser.ConfigParser()
        self.config.read_dict({
            'DEFAULT': {
                'hardware_accel': 'auto',
                'max_cache': '3000',
                'retry_count': '3',
                'log_mode': 'overwrite'
            },
            'Player': {},
            'Scanner': {},
            'EPG': {
                'main_url': 'https://epg.pw/xmltv/epg_CN.xml',
                'cache_ttl': '3600'
            },
            'UserPrefs': {}
        })
        
        cfg_path = self.get_config_path()
        if cfg_path.exists():
            with open(cfg_path, 'r', encoding='utf-8') as f:
                self.config.read_file(f)
                
        self._migrate_old_config()

    def get_config_path(self) -> Path:
        """获取跨平台配置文件路径"""
        if platform.system() == 'Windows':
            return Path.home() / 'AppData' / 'Local' / 'iptv_manager.ini'
        return Path.home() / '.config' / 'iptv_manager.ini'

    def _migrate_old_config(self) -> None:
        """迁移旧版本配置"""
        old_path = Path.home() / '.iptv_manager.ini'
        if old_path.exists():
            try:
                self.config.read(old_path)
                old_path.rename(old_path.with_suffix('.ini.bak'))
                self.save_prefs()
            except Exception as e:
                logger.warning(f"配置迁移失败: {str(e)}")

    def save_prefs(self) -> None:
        """安全保存配置"""
        cfg_path = self.get_config_path()
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 使用临时文件避免写入中断
        temp_path = cfg_path.with_suffix('.tmp')
        with open(temp_path, 'w', encoding='utf-8', newline='\n') as f:
            self.config.write(f)
        temp_path.replace(cfg_path)

class EnhancedFormatter(logging.Formatter):
    """多级颜色日志格式化器"""
    
    COLORS = {
        logging.DEBUG: '\033[36m',     # Cyan
        logging.INFO: '\033[32m',      # Green
        logging.WARNING: '\033[33m',   # Yellow
        logging.ERROR: '\033[31m',     # Red
        logging.CRITICAL: '\033[31;1m' # Bold Red
    }
    RESET = '\033[0m'

    def format(self, record):
        color = self.COLORS.get(record.levelno, '')
        fmt = f"{color}[%(levelname)s] %(message)s{self.RESET}"
        return logging.Formatter(fmt).format(record)

def setup_logger(name: str) -> logging.Logger:
    """配置跨平台日志记录器"""
    logger = logging.getLogger(name)
    if logger.hasHandlers():
        return logger

    # 解析配置
    config = ConfigHandler()
    log_mode = config.config['DEFAULT'].get('log_mode', 'overwrite')
    
    # 文件Handler
    log_file = Path('iptv_manager.log').resolve()
    file_handler = logging.FileHandler(
        log_file,
        mode='w' if log_mode == 'overwrite' else 'a',
        encoding='utf-8'
    )
    file_formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(message)s'
    )
    file_handler.setFormatter(file_formatter)
    
    # 控制台Handler（带颜色）
    console_handler = logging.StreamHandler()
    if platform.system() != 'Windows':
        console_handler.setFormatter(EnhancedFormatter())
    else:
        console_handler.setFormatter(logging.Formatter('[%(levelname)s] %(message)s'))
    
    logger.setLevel(logging.DEBUG)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger

def check_gpu_driver() -> Tuple[str, str]:
    """检测显卡信息（跨平台）"""
    try:
        if platform.system() == 'Windows':
            return _check_gpu_windows()
        elif platform.system() == 'Linux':
            return _check_gpu_linux()
        elif platform.system() == 'Darwin':
            return _check_gpu_mac()
        return ('unknown', '')
    except Exception as e:
        logging.error(f"显卡检测失败: {str(e)}")
        return ('error', str(e))

def _check_gpu_windows() -> Tuple[str, str]:
    """Windows系统检测"""
    result = subprocess.run(
        ['powershell', 'Get-WmiObject Win32_VideoController'],
        capture_output=True, 
        text=True, 
        check=True
    )
    for line in result.stdout.splitlines():
        if 'Radeon' in line:
            return ('amd', line.strip())
        if 'NVIDIA' in line:
            return ('nvidia', line.strip())
        if 'Intel' in line:
            return ('intel', line.strip())
    return ('unknown', '')

def _check_gpu_linux() -> Tuple[str, str]:
    """Linux系统检测"""
    try:
        # 检测NVIDIA
        subprocess.check_output(['nvidia-smi'], stderr=subprocess.DEVNULL)
        return ('nvidia', subprocess.getoutput('nvidia-smi --list-gpus'))
    except FileNotFoundError:
        # 检测AMD
        lspci = subprocess.getoutput('lspci | grep VGA')
        if 'AMD' in lspci:
            return ('amd', lspci)
        if 'Intel' in lspci:
            return ('intel', lspci)
        return ('unknown', lspci)

def _check_gpu_mac() -> Tuple[str, str]:
    """macOS系统检测"""
    info = subprocess.getoutput('system_profiler SPDisplaysDataType')
    if 'AMD' in info:
        return ('amd', info)
    if 'Intel' in info:
        return ('intel', info)
    if 'Apple M1' in info:
        return ('apple', info)
    return ('unknown', info)

def is_valid_pattern(pattern: str) -> bool:
    """
    验证输入格式是否合法
    """
    # 匹配包含多个范围的 URL
    regex = r'^https?://[^\s]+$'
    return re.match(regex, pattern) is not None

def parse_ip_range(pattern: str) -> List[str]:
    """
    增强IP范围解析器，支持完整URL格式
    
    支持格式:
    - 多个范围: http://192.168.50.1:20231/rtp/239.[1-20].[1-20].[1-20]:5002
    - 非 IP 部分的 URL: http://150.138.8.143/00/SNM/CHANNEL[00000311-00001000]/index.m3u8
    - 混合格式: http://192.168.50.1:20231/rtp/239.21.1.[1-20]:5002
    """
    if not pattern:
        raise ValueError("频道地址不能为空")  # 修改提示信息

    # 验证输入格式
    if not is_valid_pattern(pattern):
        raise ValueError(f"无效的频道地址格式: {pattern}")  # 修改提示信息

    # 解析每个段
    segments = []
    for seg in pattern.split('/'):
        if '[' in seg and ']' in seg:
            # 处理范围部分
            start_idx = seg.find('[')
            end_idx = seg.find(']')
            prefix = seg[:start_idx]
            suffix = seg[end_idx + 1:]
            range_part = seg[start_idx + 1:end_idx]

            # 解析范围
            ranges = []
            parts = range_part.split(',')
            for part in parts:
                if '-' in part:
                    if '/' in part:
                        range_part, step = part.split('/', 1)
                        start, end = map(int, range_part.split('-'))
                        step = int(step)
                    else:
                        start, end = map(int, part.split('-'))
                        step = 1
                    
                    # 检查 start 和 end 的有效性
                    if start > end:
                        raise ValueError(f"无效的范围: {start} > {end}")
                    if start == end:
                        ranges.append(str(start))  # 如果 start == end，直接添加单个值
                    else:
                        ranges.extend(list(map(str, range(start, end + 1, step))))
                else:
                    ranges.append(part)  # 直接添加单个值

            # 生成所有组合
            segments.append([prefix + str(r) + suffix for r in ranges])
        else:
            # 非范围部分
            segments.append([seg])

    # 生成所有组合
    return ['/'.join(combo) for combo in product(*segments)]
