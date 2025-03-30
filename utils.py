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
    支持格式:
        1. 多个范围: http://192.168.50.1:20231/rtp/239.[1-20].[1-20].[1-20]:5002
        2. 非IP部分的URL: http://150.138.8.143/00/SNM/CHANNEL[00000311-00001000]/index.m3u8
        3. 混合格式: http://192.168.50.1:20231/rtp/239.21.[1-5].[1-255]:5002
        4. 带步长的范围: http://192.168.50.1:20231/rtp/239.1.[1-20/2].1:5002
    异常:
        ValueError: 当输入格式无效或范围定义错误时抛出
    示例:
        >>> parse_ip_range("http://192.168.1.1/rtp/239.1.[1-3]:5002")
        [
            'http://192.168.1.1/rtp/239.1.1:5002',
            'http://192.168.1.1/rtp/239.1.2:5002',
            'http://192.168.1.1/rtp/239.1.3:5002'
        ]
    功能增强:
        1. 支持多个独立范围表达式
        2. 优化性能，减少内存使用
        3. 更严格的输入验证
    """
    if not pattern:
        raise ValueError("频道地址不能为空")

    # 验证输入格式
    if not is_valid_pattern(pattern):
        raise ValueError(f"无效的频道地址格式: {pattern}")

    # 特殊处理包含端口号的URL
    if ':' in pattern and '/' in pattern:
        # 分割出端口号部分单独处理
        base_url, port_part = pattern.rsplit(':', 1)
        port = port_part.split('/')[-1]
        # 仅当端口号是纯数字时才进行替换
        if port.isdigit():
            # 保留原始端口号格式
            pattern = base_url + ':' + port_part
    
    logger.debug(f"解析前的原始模式: {pattern}")
    
    # 解析每个段
    segments = []
    for seg in pattern.split('/'):
        # 支持方括号和圆括号两种格式
        if ('[' in seg and ']' in seg) or ('(' in seg and ')' in seg):
            # 处理范围部分
            open_char = '[' if '[' in seg else '('
            close_char = ']' if '[' in seg else ')'
            start_idx = seg.find(open_char)
            end_idx = seg.find(close_char)
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
                        start_str, end_str = range_part.split('-')
                        start = int(start_str)
                        end = int(end_str)
                        step = int(step)
                        # 获取原始数字位数
                        digits = len(start_str)
                    else:
                        start_str, end_str = part.split('-')
                        start = int(start_str)
                        end = int(end_str)
                        step = 1
                        # 获取原始数字位数
                        digits = len(start_str)
                    
                    # 检查 start 和 end 的有效性
                    if start > end:
                        raise ValueError(f"无效的范围: {start} > {end}")
                    if start == end:
                        ranges.append(str(start).zfill(digits))
                    else:
                        # 使用生成器表达式减少内存使用，并补零
                        ranges.extend(str(x).zfill(digits) for x in range(start, end + 1, step))
                else:
                    ranges.append(part)

            # 生成所有组合(处理嵌套范围)
            current_segments = []
            for r in ranges:
                # 检查当前r是否包含范围表达式
                if ('[' in r and ']' in r) or ('(' in r and ')' in r):
                    # 递归处理嵌套范围
                    nested = parse_ip_range(prefix + r + suffix)
                    current_segments.extend(nested)
                else:
                    # 检查当前r是否包含未解析的范围表达式
                    if ('[' in r or ']' in r or '(' in r or ')' in r):
                        # 递归处理不完整的范围表达式
                        nested = parse_ip_range(prefix + r + suffix)
                        current_segments.extend(nested)
                    else:
                        # 处理IP段中的范围表达式
                        if '.' in prefix and any(c.isdigit() for c in r):
                            # 如果是IP段，直接添加数字部分
                            current_segments.append(prefix + r + suffix)
                        else:
                            # 其他情况保持原样
                            current_segments.append(prefix + r + suffix)
            segments.append(current_segments)
        else:
            segments.append([seg])

    # 使用生成器表达式减少内存使用
    urls = []
    for combo in product(*segments):
        url = '/'.join(combo)
        # 处理IP段中的范围表达式
        if '[' in url or '(' in url:
            urls.extend(parse_ip_range(url))
        else:
            urls.append(url)
    logger.debug(f"生成的URL示例: {urls[:3]}... (共{len(urls)}个)")
    return urls

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
