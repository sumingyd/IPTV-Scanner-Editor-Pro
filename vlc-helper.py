import vlc
import platform
import logging
from typing import List, Optional
from pathlib import Path
from utils import ConfigHandler, check_gpu_driver

logger = logging.getLogger('VLC-Helper')

def create_vlc_instance(retry_count: int = 3) -> Optional[vlc.Instance]:
    """创建智能配置的VLC实例，去掉调试日志"""
    config = ConfigHandler()
    for attempt in range(retry_count):
        try:
            args = _generate_vlc_args(config, attempt)
            instance = vlc.Instance(args)

            # 验证实例有效性
            if _validate_instance(instance):
                return instance

        except Exception:
            if attempt == retry_count - 1:
                return _create_fallback_instance(config)
    return None

def _generate_vlc_args(config: ConfigHandler, attempt: int) -> List[str]:
    """生成动态VLC参数"""
    log_file = str(Path.home() / 'vlc-debug.log')  # 将日志文件保存到用户主目录
    args = [
        '--avcodec-hw=none',  # 强制禁用硬件解码
        '--no-hw-decoder',  # 禁用所有硬件解码器
        '--no-d3d11',  # 显式禁用 Direct3D11
        '--network-caching=' + config.config['Player'].get(
            'network_cache', 
            '3000' if attempt == 0 else str(3000 + attempt * 1000)
        ),
        '--drop-late-frames=1',
        '--skip-frames=1',
        '--adaptive-logic=rate',
        '--live-caching=300',
        '--clock-jitter=0',
        '--clock-synchro=99',
        '--no-xlib',  # Linux系统禁用Xlib
        '--verbose=4',  # 最高级别的日志
        '--file-logging',
        f'--logfile={log_file}'  # 使用格式化字符串确保路径正确
    ]

    # 平台特定参数
    if platform.system() == 'Windows':
        args += [
            '--directx-hw-yuv',
            '--winrt-swapchain=enable'
        ]
    elif platform.system() == 'Darwin':
        args += [
            '--vout=macosx',
            '--no-macosx-interface'
        ]
        
    return args

def _validate_instance(instance: vlc.Instance) -> bool:
    """验证VLC实例有效性"""
    try:
        test_media = instance.media_new('')
        return test_media is not None
    except Exception as e:
        logger.warning("VLC实例验证失败: %s", str(e))
        return False

def _create_fallback_instance(config: ConfigHandler) -> vlc.Instance:
    """创建降级实例"""
    logger.warning("启用软件解码回退模式")
    return vlc.Instance([
        '--avcodec-hw=none',
        '--network-caching=5000',
        '--drop-late-frames=2',
        '--no-hw-decoder'
    ])