import os
import sys
import logging
import time
import re
from typing import Any, Dict, List, Optional


def get_display_channel_name(channel: Dict[str, Any], language_manager=None) -> str:
    """统一的频道显示名称获取函数

    Args:
        channel: 频道数据字典
        language_manager: 语言管理器实例（可选，用于国际化）

    Returns:
        str: 格式化后的频道显示名称

    功能：
    - 支持国际化（通过language_manager）
    - 处理逗号分隔的名称（取最后一部分）
    - 添加频道号前缀（如果有tvg_chno）
    - 添加分组名后缀（如果不同于默认分组）
    """
    if not channel:
        return 'Unknown Channel'

    tr = getattr(language_manager, 'tr', lambda x, y: x) if language_manager else lambda x, y: x

    all_tags = channel.get('_all_tags', {})
    name = all_tags.get('name') or channel.get('name', '') or ''
    number = channel.get('tvg_chno', '')
    group_name = all_tags.get('group-name') or ''

    # 处理逗号分隔的名称（如 "CCTV1,央视一套" 取 "央视一套"）
    if ',' in name:
        parts = name.split(',', 1)
        if len(parts) > 1 and parts[1].strip():
            name = parts[1].strip()

    # 添加频道号
    if number and name:
        name = f"{number} {name}"

    # 添加分组名（如果不同于默认分组）
    if group_name and group_name != channel.get('group', ''):
        name = f"{name} ({group_name})"

    return name or tr('unknown_channel', 'Unknown Channel')


def get_resource_path(relative_path: str) -> str:
    """获取资源文件的绝对路径"""
    if getattr(sys, 'frozen', False):
        # 打包成exe的情况
        base_path = os.path.dirname(sys.executable)
    else:
        # 开发环境
        base_path = os.path.dirname(__file__)

    return os.path.join(base_path, relative_path)


def get_icon_path() -> str:
    """获取程序图标logo.ico的绝对路径（兼容PyInstaller打包和开发环境）"""
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, 'resources', 'logo.ico')


def get_project_root() -> str:
    """获取项目根目录"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        # 从utils目录向上两级到项目根目录
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def is_valid_url(url: str) -> bool:
    """检查URL是否有效"""
    if not url or not isinstance(url, str):
        return False

    # 基本URL格式检查
    url = url.strip()
    if not url:
        return False

    # 检查常见协议
    valid_schemes = ('http://', 'https://', 'rtp://', 'udp://', 'rtsp://', 'file://')
    return any(url.startswith(scheme) for scheme in valid_schemes)


def format_file_size(size_bytes: float) -> str:
    """格式化文件大小"""
    if size_bytes == 0:
        return "0 B"

    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1

    return f"{size_bytes:.2f} {size_names[i]}"


def truncate_text(text: str, max_length: int = 50, suffix: str = "...") -> str:
    """截断文本，超过最大长度时添加后缀"""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def safe_connect(signal, slot):
    """安全连接信号，避免重复连接

    Args:
        signal: PyQt信号对象
        slot: 槽函数或可调用对象

    Returns:
        bool: 连接是否成功
    """
    try:
        signal.disconnect(slot)
    except (TypeError, RuntimeError):
        pass

    try:
        signal.connect(slot)
        return True
    except Exception as e:
        logging.getLogger('utils').error(f"连接信号失败: {e}")
        return False


def safe_connect_button(button, callback):
    """安全连接按钮点击信号

    Args:
        button: QPushButton或类似按钮对象
        callback: 回调函数

    Returns:
        bool: 连接是否成功
    """
    return safe_connect(button.clicked, callback)


def format_time(seconds: float) -> str:
    """格式化时间（秒）为时分秒格式"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    elif minutes > 0:
        return f"{minutes:02d}:{secs:02d}"
    else:
        return f"00:{secs:02d}"


def retry_operation(operation, max_retries: int = 3, delay: float = 1.0, exceptions: tuple = (Exception,)) -> Any:
    """带重试机制的操作执行

    Args:
        operation: 要执行的操作函数
        max_retries: 最大重试次数
        delay: 重试间隔（秒）
        exceptions: 要捕获的异常类型

    Returns:
        Any: 操作的返回值

    Raises:
        Exception: 如果所有重试都失败
    """
    for attempt in range(max_retries):
        try:
            return operation()
        except exceptions as e:
            if attempt == max_retries - 1:
                raise
            time.sleep(delay)
            logging.getLogger('utils').warning(f"操作失败，重试 {attempt + 1}/{max_retries}: {e}")


def deep_merge_dicts(target: Dict, source: Dict) -> Dict:
    """深度合并两个字典

    Args:
        target: 目标字典
        source: 源字典

    Returns:
        Dict: 合并后的字典
    """
    for key, value in source.items():
        if key in target and isinstance(target[key], dict) and isinstance(value, dict):
            deep_merge_dicts(target[key], value)
        else:
            target[key] = value
    return target


def sanitize_filename(filename: str) -> str:
    """清理文件名，移除或替换无效字符

    Args:
        filename: 原始文件名

    Returns:
        str: 清理后的文件名
    """
    # 移除或替换Windows文件名中的无效字符
    invalid_chars = '\\/:*?"<>|'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    return filename.strip()


