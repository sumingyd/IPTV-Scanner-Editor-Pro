import logging
import platform
import time
from typing import Tuple
import sys
from pathlib import Path

# 多级颜色日志格式化器
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

# 聚合相似日志的处理器
class AggregatedLogHandler(logging.Handler):
    """聚合相似日志的处理器"""
    def __init__(self, target_handler, threshold=5):
        super().__init__()
        self.target_handler = target_handler
        self.threshold = threshold
        self.log_cache = {}
        self.last_flush = time.time()
        
    def emit(self, record):
        # 提取日志消息中的动态部分(如URL、数字等)并用通配符替换
        msg = record.msg
        if 'ffprobe output for' in msg:
            # 聚合所有ffprobe output日志
            key = (record.levelno, 'ffprobe output for *')
        elif '计算延迟:' in msg:
            # 聚合所有延迟计算日志
            key = (record.levelno, '计算延迟: *')
        elif '执行ffprobe命令:' in msg:
            # 聚合所有ffprobe命令日志
            key = (record.levelno, '执行ffprobe命令: *')
        else:
            # 其他日志保持原样
            key = (record.levelno, msg)
            
        if key in self.log_cache:
            self.log_cache[key] += 1
        else:
            self.log_cache[key] = 1
            
        # 定期刷新缓存(至少每秒一次)
        if (time.time() - self.last_flush) >= 1.0 or len(self.log_cache) >= 10:
            self.flush()
            
    def flush(self):
        for (levelno, msg), count in self.log_cache.items():
            if count > self.threshold:
                record = logging.LogRecord(
                    name='',
                    level=levelno,
                    pathname='',
                    lineno=0,
                    msg=f"[聚合日志] {msg} (共{count}次)",
                    args=(),
                    exc_info=None
                )
                self.target_handler.emit(record)
            else:
                for _ in range(count):
                    record = logging.LogRecord(
                        name='',
                        level=levelno,
                        pathname='',
                        lineno=0,
                        msg=msg,
                        args=(),
                        exc_info=None
                    )
                    self.target_handler.emit(record)
        self.log_cache.clear()
        self.last_flush = time.time()

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

# 配置跨平台日志记录器
def setup_logger(name: str, level=None) -> logging.Logger:
    """配置跨平台日志记录器(增强版)
    参数:
        name: 日志记录器名称
        level: 日志级别(默认为从配置读取)
    功能:
        1. 支持日志级别控制
        2. 添加聚合日志功能
        3. 优化日志格式
        4. 增加线程/进程ID信息
        5. 支持性能监控
    """
    from config_manager import ConfigHandler
    
    logger = logging.getLogger(name)
    
    # 从配置读取日志级别
    config = ConfigHandler()
    log_level = config.get_config_value('DEFAULT', 'log_level', 'INFO').upper()
    level = getattr(logging, log_level, logging.INFO) if level is None else level
    
    logger.setLevel(level)
    logger.addFilter(VlcWarningFilter())
    
    if logger.hasHandlers():
        return logger

    # 解析配置
    config = ConfigHandler()
    log_mode = config.get_config_value('DEFAULT', 'log_mode', 'overwrite')
    
    # 基础Handler配置
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s:%(lineno)d [%(process)d:%(thread)d] - %(message)s'
    )
    
    # 文件Handler
    log_file = Path('iptv_manager.log').resolve()
    file_handler = logging.FileHandler(
        log_file,
        mode='w' if log_mode == 'overwrite' else 'a',
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    
    # 添加聚合日志处理器(处理所有handler)
    aggregated_handler = AggregatedLogHandler(file_handler)
    logger.addHandler(aggregated_handler)
    
    # 控制台Handler(可选) - 也使用聚合
    if config.get_config_value('DEFAULT', 'console_log', 'false').lower() == 'true':
        console_handler = logging.StreamHandler()
        if platform.system() != 'Windows':
            console_handler.setFormatter(EnhancedFormatter())
        else:
            console_handler.setFormatter(logging.Formatter('[%(levelname)s] %(message)s'))
        aggregated_console_handler = AggregatedLogHandler(console_handler)
        logger.addHandler(aggregated_console_handler)

    # 为所有Handler添加过滤器
    vlc_filter = VlcWarningFilter()
    for handler in logger.handlers:
        handler.addFilter(vlc_filter)
    
    # 特别处理VLC自有日志
    vlc_logger = logging.getLogger('VLC')
    for handler in vlc_logger.handlers:
        handler.addFilter(vlc_filter)
    
    return logger
