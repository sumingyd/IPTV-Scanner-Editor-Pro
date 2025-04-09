import platform
import re
import subprocess
from pathlib import Path
import sys
import time
import logging
from typing import List, Tuple, Dict, Any
from itertools import product
from logger_utils import setup_logger
from config_manager import ConfigHandler

logger = setup_logger('Utils')

# 验证URL格式是否合法
def is_valid_pattern(pattern: str) -> bool:
    """验证URL格式是否合法"""
    regex = r'^https?://[^\s]+$'
    return re.match(regex, pattern) is not None

# 解析IP/URL范围模式生成所有可能的URL组合
def parse_ip_range(pattern: str) -> List[str]:
    """解析IP/URL范围模式生成所有可能的URL组合"""
    if not pattern:
        raise ValueError("频道地址不能为空")

    if not is_valid_pattern(pattern):
        raise ValueError(f"无效的频道地址格式: {pattern}")

    # 特殊处理包含端口号的URL
    if ':' in pattern and '/' in pattern:
        base_url, port_part = pattern.rsplit(':', 1)
        port = port_part.split('/')[-1]
        if port.isdigit():
            pattern = base_url + ':' + port_part
    
    logger.debug(f"解析前的原始模式: {pattern}")

    # 匹配方括号内的多范围模式
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
            start = int(start_str.strip())
            end = int(end_str.strip())
            
            if start > end:
                raise ValueError(f"无效范围 {start}-{end}")
                
            # 保持数字位数一致
            if start_str.startswith('0') or end_str.startswith('0'):
                digits = max(len(start_str), len(end_str))
                range_options.extend(
                    [f"{num:0{digits}d}" for num in range(start, end+1)]
                )
            else:
                range_options.extend(str(num) for num in range(start, end+1))
        
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

    if not result:
        raise ValueError(f"无法解析地址格式: {pattern}")

    logger.debug(f"生成的URL示例: {result[:3]}... (共{len(result)}个)")
    return result

# 性能监控装饰器
def log_performance(func):
    """性能监控装饰器"""
    def wrapper(*args, **kwargs):
        start_time = time.time()
        logger = logging.getLogger('Performance')
        try:
            result = func(*args, **kwargs)
            elapsed = (time.time() - start_time) * 1000
            logger.info(f"{func.__name__} 耗时: {elapsed:.2f}ms")
            return result
        except Exception as e:
            elapsed = (time.time() - start_time) * 1000
            logger.error(f"{func.__name__} 执行失败(耗时: {elapsed:.2f}ms): {str(e)}")
            raise
    return wrapper

# 记录内存使用情况
def log_memory_usage():
    """记录内存使用情况"""
    import psutil
    process = psutil.Process()
    mem_info = process.memory_info()
    logger = logging.getLogger('Memory')
    logger.debug(
        f"内存使用: RSS={mem_info.rss/1024/1024:.2f}MB, "
        f"VMS={mem_info.vms/1024/1024:.2f}MB"
    )

# 检测显卡信息（跨平台）
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
        logger.error(f"显卡检测失败: {str(e)}")
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

# 过滤 VLC 媒体播放器 的日志信息
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
