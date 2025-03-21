import vlc
import platform
import logging
from typing import List, Optional
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
    gpu_type, _ = check_gpu_driver()
    args = [
        '--avcodec-hw=any',
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
        '--no-xlib'  # Linux系统禁用Xlib
    ]

    # 平台特定参数
    if platform.system() == 'Windows':
        args += [
            '--directx-hw-yuv',
            '--d3d11vpu=enable',
            '--winrt-swapchain=enable'
        ]
    elif platform.system() == 'Darwin':
        args += [
            '--vout=macosx',
            '--no-macosx-interface'
        ]

    # 硬件加速优化
    hw_accel = config.config['Player'].get('hardware_accel', 'auto')
    if hw_accel == 'auto':
        if gpu_type == 'nvidia':
            args += ['--ffmpeg-hw', '--codec=avcodec,none']
        elif gpu_type == 'amd':
            args += ['--avcodec-hw=dxva2', '--disable-accelerated-video']
        elif gpu_type == 'intel':
            args += ['--avcodec-hw=vaapi', '--vdpau=disable']
    else:
        args += [f'--avcodec-hw={hw_accel}']

    # 调试参数
    if config.config.getboolean('Debug', 'enable_vlc_log', fallback=False):
        args += [
            '--verbose=2',
            '--file-logging',
            '--logfile=vlc-debug.log'
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

# 示例用法
if __name__ == "__main__":
    from utils import setup_logger
    setup_logger('VLC-Helper')
    
    instance = create_vlc_instance()
    if instance:
        player = instance.media_player_new()
        media = instance.media_new('rtp://239.1.1.1:5002')
        player.set_media(media)
        
        if player.play() == -1:
            logger.error("播放初始化失败")
        else:
            logger.info("播放已启动")
    else:
        logger.error("无法创建VLC实例")