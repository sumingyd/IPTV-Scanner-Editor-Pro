import os
import sys
import logging


def get_resource_path(relative_path: str) -> str:
    """获取资源文件的绝对路径"""
    if getattr(sys, 'frozen', False):
        # 打包成exe的情况
        base_path = os.path.dirname(sys.executable)
    else:
        # 开发环境
        base_path = os.path.dirname(__file__)

    return os.path.join(base_path, relative_path)


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


def format_file_size(size_bytes: int) -> str:
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
        # 先尝试断开现有连接
        signal.disconnect()
    except (TypeError, RuntimeError):
        # 如果没有连接，会抛出TypeError或RuntimeError
        pass

    try:
        # 建立新连接
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
