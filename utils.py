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
        """安全初始化配置
        1. 创建默认配置
        2. 读取现有配置文件(如果存在)
        3. 迁移旧版本配置
        """
        self.config = configparser.ConfigParser()
        self.config.read_dict({
            'DEFAULT': {
                'hardware_accel': 'auto',
                'max_cache': '3000',
                'retry_count': '3',
                'log_mode': 'overwrite',
                'console_log': 'false'
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
        try:
            if cfg_path.exists():
                with open(cfg_path, 'r', encoding='utf-8') as f:
                    self.config.read_file(f)
            else:
                # 确保新文件有默认值
                self.save_prefs()
                
            self._migrate_old_config()
        except Exception as e:
            logger.error(f"初始化配置失败: {str(e)}")
            # 回退到默认配置
            self.config = configparser.ConfigParser()
            self.config.read_dict({
                'DEFAULT': {
                    'hardware_accel': 'auto',
                    'max_cache': '3000',
                    'retry_count': '3',
                    'log_mode': 'overwrite',
                    'console_log': 'false'
                }
            })

    def get_config_path(self) -> Path:
        """获取跨平台配置文件路径
        返回:
            Path: 配置文件路径对象
        功能:
            1. 确定配置文件路径(程序所在目录/.iptv_manager.ini)
            2. 确保目录存在
            3. 设置文件隐藏属性(Windows)或权限(Linux/macOS)
        """
        # 使用程序所在目录而不是代码目录
        config_path = Path.cwd() / '.iptv_manager.ini'
        
        try:
            # 确保父目录存在
            config_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 设置隐藏属性
            if platform.system() == 'Windows':
                import ctypes
                try:
                    # 如果文件不存在则创建空文件
                    if not config_path.exists():
                        config_path.touch()
                    # 设置隐藏属性
                    ctypes.windll.kernel32.SetFileAttributesW(str(config_path), 2)  # FILE_ATTRIBUTE_HIDDEN
                except Exception as e:
                    logger.debug(f"设置隐藏属性失败: {str(e)}")
            else:
                try:
                    # Linux/macOS设置权限和隐藏(以.开头)
                    config_path.chmod(0o600)
                except Exception as e:
                    logger.debug(f"设置权限失败: {str(e)}")
                    
            return config_path
        except Exception as e:
            logger.error(f"获取配置路径失败: {str(e)}")
            # 回退到临时目录
            return Path('/tmp/.iptv_manager.ini') if platform.system() != 'Windows' else Path('C:/Windows/Temp/.iptv_manager.ini')

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
        """安全保存配置
        功能:
            1. 使用临时文件避免写入中断
            2. 确保原子性写入
            3. 处理可能的异常情况
        """
        try:
            cfg_path = self.get_config_path()
            cfg_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 使用临时文件避免写入中断
            temp_path = cfg_path.with_suffix('.tmp')
            with open(temp_path, 'w', encoding='utf-8', newline='\n') as f:
                self.config.write(f)
            
            # 原子性替换
            if platform.system() == 'Windows':
                # Windows需要先删除目标文件
                if cfg_path.exists():
                    cfg_path.unlink()
            temp_path.replace(cfg_path)
            
            # 重新设置隐藏属性
            if platform.system() == 'Windows':
                import ctypes
                ctypes.windll.kernel32.SetFileAttributesW(str(cfg_path), 2)
        except Exception as e:
            logger.error(f"保存配置失败: {str(e)}")
            raise

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
    logger.addFilter(VlcWarningFilter())  # 新增过滤器
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
    
    logger.setLevel(logging.DEBUG)
    logger.addHandler(file_handler)
    
    # 默认不添加控制台handler
    if config.config['DEFAULT'].getboolean('console_log', False):
        console_handler = logging.StreamHandler()
        if platform.system() != 'Windows':
            console_handler.setFormatter(EnhancedFormatter())
        else:
            console_handler.setFormatter(logging.Formatter('[%(levelname)s] %(message)s'))
        logger.addHandler(console_handler)

    # 为所有Handler添加过滤器
    vlc_filter = VlcWarningFilter()
    for handler in logger.handlers:
        handler.addFilter(vlc_filter)
    
    # 特别处理VLC自有日志
    vlc_logger = logging.getLogger('VLC')
    for handler in vlc_logger.handlers:
        handler.addFilter(vlc_filter)
    
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
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
        text=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
        shell=False,
        check=True,
        start_new_session=True
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
        subprocess.check_output(
            ['nvidia-smi'], 
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
            shell=False,
            start_new_session=True
        )
        return ('nvidia', subprocess.getoutput('nvidia-smi --list-gpus'))
    except FileNotFoundError:
        # 检测AMD
        result = subprocess.run(
            ['lspci'], 
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
            shell=False,
            start_new_session=True
        )
        lspci = '\n'.join(line for line in result.stdout.splitlines() if 'VGA' in line)
        if 'AMD' in lspci:
            return ('amd', lspci)
        if 'Intel' in lspci:
            return ('intel', lspci)
        return ('unknown', lspci)

def _check_gpu_mac() -> Tuple[str, str]:
    """macOS系统检测"""
    result = subprocess.run(
        ['system_profiler', 'SPDisplaysDataType'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
        text=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
        shell=False,
        start_new_session=True
    )
    info = result.stdout
    if 'AMD' in info:
        return ('amd', info)
    if 'Intel' in info:
        return ('intel', info)
    if 'Apple M1' in info:
        return ('apple', info)
    return ('unknown', info)

def is_valid_pattern(pattern: str) -> bool:
    """验证URL格式是否合法
    参数:
        pattern: 待验证的URL字符串
    返回:
        bool: 如果格式合法返回True，否则返回False
    验证规则:
        1. 必须以http://或https://开头
        2. 不能包含空白字符
    示例:
        >>> is_valid_pattern("http://example.com")
        True
        >>> is_valid_pattern("invalid url")
        False
    """
    # 匹配包含多个范围的 URL
    regex = r'^https?://[^\s]+$'
    return re.match(regex, pattern) is not None

def parse_ip_range(pattern: str) -> List[str]:
    """解析IP/URL范围模式生成所有可能的URL组合
    参数:
        pattern: 包含范围模式的URL字符串
    返回:
        所有可能的URL组合列表
    增强功能:
        1. 支持方括号范围语法 [1-5,10-15]
        2. 支持多段范围组合（如239.21.[1-5].[1-10]）
        3. 自动补零保持数字位数一致
    示例:
        >>> parse_ip_range("http://192.168.1.1:20231/rtp/239.21.[1-5].[1-10]:5002")
        [
            'http://192.168.1.1:20231/rtp/239.21.01.01:5002',
            'http://192.168.1.1:20231/rtp/239.21.01.02:5002',
            ... # 所有组合
        ]
    """
    if not pattern:
        raise ValueError("频道地址不能为空")

    # 验证输入格式
    if not is_valid_pattern(pattern):
        raise ValueError(f"无效的频道地址格式: {pattern}")

    # 特殊处理包含端口号的URL
    if ':' in pattern and '/' in pattern:
        base_url, port_part = pattern.rsplit(':', 1)
        port = port_part.split('/')[-1]
        if port.isdigit():
            pattern = base_url + ':' + port_part
    
    logger.debug(f"解析前的原始模式: {pattern}")

    # 匹配方括号内的多范围模式（支持嵌套）
    range_pattern = re.compile(r'\[([^\]]+)\]')
    matches = range_pattern.findall(pattern)
    if not matches:
        return [pattern]

    # 准备替换组件
    replacements = []
    for match in matches:
        ranges = match.split(',')
        range_options = []
        for r in ranges:
            if '-' not in r:
                range_options.append(r.strip())
                continue
                
            start_str, end_str = r.split('-', 1)
            start_str = start_str.strip()
            end_str = end_str.strip()
            
            # 根据输入格式决定是否补零
            start = int(start_str)
            end = int(end_str)
            
            if start > end:
                raise ValueError(f"无效范围 {start}-{end}，起始值不能大于结束值")
                
            # 如果输入有前导零则补零，否则不补
            if start_str.startswith('0') or end_str.startswith('0'):
                digits = max(len(start_str), len(end_str))
                range_options.extend(
                    [f"{num:0{digits}d}" for num in range(start, end+1)]
                )
            else:
                range_options.extend(
                    [str(num) for num in range(start, end+1)]
                )
        
        replacements.append(range_options)

    # 生成所有组合
    parts = range_pattern.split(pattern)
    result = [parts[0]]  # 第一个静态部分
    
    for i, options in enumerate(replacements):
        temp = []
        for r in options:
            for s in result:
                temp.append(s + r + parts[2*i+2])  # 拼接后续静态部分
        result = temp

    # 处理未加方括号的简单范围（兼容旧格式）
    if not result:
        simple_match = re.search(r'(\D*)(\d+)-(\d+)(\D*)', pattern)
        if simple_match:
            prefix = simple_match.group(1)
            start_str = simple_match.group(2)
            end_str = simple_match.group(3)
            suffix = simple_match.group(4)
            
            start = int(start_str)
            end = int(end_str)
            
            if start > end:
                raise ValueError(f"无效范围 {start}-{end}，起始值不能大于结束值")
            
            # 如果输入有前导零则补零，否则不补
            if start_str.startswith('0') or end_str.startswith('0'):
                digits = max(len(start_str), len(end_str))
                result = [
                    f"{prefix}{num:0{digits}d}{suffix}" 
                    for num in range(start, end+1)
                ]
            else:
                result = [
                    f"{prefix}{num}{suffix}" 
                    for num in range(start, end+1)
                ]

    if not result:
        raise ValueError(f"无法解析地址格式: {pattern}")

    logger.debug(f"生成的URL示例: {result[:3]}... (共{len(result)}个)")
    return result

class VlcWarningFilter(logging.Filter):
    def filter(self, record):
        msg = record.getMessage().lower()
        blocked = [
            'thumbnailclip',
            'get_buffer',
            'thread_get_buffer',
            'decode_slice',
            'no frame',
            'd3d11',
            'dxva',
            'vaapi'
        ]
        return not any(kw in msg for kw in blocked)
