import vlc
import asyncio
import platform
import logging
from typing import List
from PyQt6 import QtWidgets, QtCore
from PyQt6.QtCore import pyqtSignal
from utils import ConfigHandler, check_gpu_driver

logger = logging.getLogger('Player')

class VLCInstanceManager:
    _instance = None
    _config = None
    
    @classmethod
    def initialize(cls, config: ConfigHandler):
        cls._config = config
        
    @classmethod
    def get_instance(cls) -> vlc.Instance:
        if not cls._instance:
            try:
                args = cls._generate_vlc_args()
                cls._instance = vlc.Instance(args)
                if not cls._instance:
                    raise RuntimeError("VLC实例创建失败")
            except Exception as e:
                logger.error(f"VLC实例创建失败: {str(e)}")
                raise
        return cls._instance
    
    @classmethod
    def _generate_vlc_args(cls) -> List[str]:
        args = [
            '--no-video-title-show',
            '--network-caching=3000',
            '--drop-late-frames',
            '--skip-frames',
            '--quiet'
        ]
        
        hw_mode = cls._config.config['DEFAULT'].get('hardware_accel', 'auto')
        if hw_mode == 'auto':
            gpu_type, _ = check_gpu_driver()
            if 'amd' in gpu_type.lower():
                args += ['--avcodec-hw=dxva2', '--vout=direct3d11']
            elif 'nvidia' in gpu_type.lower():
                args += ['--avcodec-hw=d3d11va', '--vout=direct3d11']
            else:
                args += ['--avcodec-hw=none']
        elif hw_mode != 'none':
            args += [f'--avcodec-hw={hw_mode}']
            
        if platform.system() == 'Windows':
            args += ['--directx-hw-yuv']
        return args


class VLCPlayer(QtWidgets.QWidget):
    state_changed = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = ConfigHandler()
        VLCInstanceManager.initialize(self.config)
        self.media_player = None
        self._release_lock = asyncio.Lock()
        self._is_active = False
        self._init_vlc()
        self._init_ui()
        self._setup_connections()

    def _init_vlc(self):
        try:
            self.media_player = VLCInstanceManager.get_instance().media_player_new()
            self._is_active = True
            QtCore.QTimer.singleShot(100, self._bind_video_window)
        except Exception as e:
            logger.error(f"初始化失败: {str(e)}")
            self.state_changed.emit("初始化失败")

    def _init_ui(self):
        self.video_frame = QtWidgets.QFrame()
        self.video_frame.setStyleSheet("background-color: black;")
        self.video_frame.setMinimumSize(640, 360)
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.video_frame)
        self.setLayout(layout)

    def _bind_video_window(self):
        if not self._is_active or not self.media_player:
            return
            
        try:
            win_id = int(self.video_frame.winId())
            if platform.system() == 'Windows':
                self.media_player.set_hwnd(win_id)
            else:
                self.media_player.set_xwindow(win_id)
        except Exception as e:
            logger.error(f"窗口绑定失败: {str(e)}")
            QtCore.QTimer.singleShot(100, self._bind_video_window)

    async def async_play(self, url: str, retry=3) -> bool:
        if not self._is_active:
            self._init_vlc()
            
        for attempt in range(retry):
            try:
                media = VLCInstanceManager.get_instance().media_new(url)
                self.media_player.set_media(media)
                
                if self.media_player.play() == -1:
                    raise RuntimeError("播放失败")
                    
                if await self._wait_for_playback():
                    return True
            except Exception as e:
                if attempt == retry - 1:
                    self.stop()
        return False

    async def _wait_for_playback(self, timeout=10) -> bool:
        start_time = asyncio.get_event_loop().time()
        while (asyncio.get_event_loop().time() - start_time) < timeout:
            await asyncio.sleep(0.5)
            if self.media_player.is_playing():
                return True
        return False

    def toggle_pause(self) -> None:
        if not self._is_active:
            return
            
        try:
            if self.media_player.is_playing():
                self.media_player.pause()
                self.state_changed.emit("已暂停")
            else:
                self.media_player.play()
                self.state_changed.emit("播放中")
        except Exception as e:
            logger.error(f"暂停失败: {str(e)}")
            self._init_vlc()

    async def async_release(self):
        async with self._release_lock:
            try:
                if self.media_player:
                    self.media_player.stop()
                    await asyncio.sleep(0.1)
                    try:
                        self.media_player.release()
                    except Exception as e:
                        logger.error(f"媒体资源释放失败: {str(e)}")
                        raise
            except Exception as e:
                logger.error(f"释放失败: {str(e)}")
                raise
            finally:
                self.media_player = None
                self._is_active = False
                self.state_changed.emit("播放已停止")

    def stop(self) -> None:
        if self._is_active:
            self.force_stop()
            asyncio.create_task(self.async_release())

    def force_stop(self):
        try:
            if self.media_player:
                self.media_player.stop()
                self.media_player.release()
        except Exception as e:
            logger.error(f"强制停止失败: {str(e)}")
        finally:
            self.media_player = None
            self._is_active = False
#############################
    def _setup_connections(self):
        """初始化信号连接"""
        try:
            event_manager = self.media_player.event_manager()
            event_manager.event_attach(vlc.EventType.MediaPlayerPlaying, self._on_play)
            event_manager.event_attach(vlc.EventType.MediaPlayerStopped, self._on_stop)
            event_manager.event_attach(vlc.EventType.MediaPlayerPaused, self._on_pause)
        except Exception as e:
            pass

    def _generate_hw_args(self, hw_mode: str) -> List[str]:
        """修正后的参数生成逻辑"""
        args = [
            '--no-video-title-show',
            '--network-caching=3000',
            '--skip-frames'
        ]
        
        # 硬件加速配置
        hw_map = {
            'auto': self._auto_detect_hw,
            'none': lambda: ['--avcodec-hw=none'],
            'd3d11va': lambda: ['--avcodec-hw=d3d11va', '--vout=direct3d11'],
            'vaapi': lambda: ['--avcodec-hw=vaapi', '--vout=vaapi'],
            'dxva2': lambda: ['--avcodec-hw=dxva2', '--vout=direct3d11']
        }
        
        if hw_mode in hw_map:
            args += hw_map[hw_mode]()
        else:
            args += ['--avcodec-hw=none']
        
        return args
    
    def _init_managers(self):
        """初始化管理器（关键！）"""
        VLCInstanceManager.initialize(self.config)
#############################
    def set_volume(self, volume: int) -> None:
        """设置音量 (0-100)"""
        try:
            if 0 <= volume <= 100:
                self.media_player.audio_set_volume(volume)
            else:
                logger.warning(f"无效的音量值: {volume}")
        except Exception as e:
            logger.error(f"音量设置失败: {str(e)}")
            raise

    def _on_play(self, event):
        """播放事件处理"""
        self.state_changed.emit("正在播放...")

    def _on_pause(self, event):
        """暂停事件处理"""
        self.state_changed.emit("播放已暂停")

    def _on_stop(self, event):
        """停止事件处理"""
        self.state_changed.emit("播放停止")

    def __del__(self):
        """资源清理（优化版）"""
        try:
            from async_utils import AsyncWorker
            # 取消所有异步任务
            AsyncWorker.cancel_all()
            
            # 确保停止播放
            if self.media_player and self.media_player.is_playing():
                self.media_player.stop()
                
            # 释放媒体资源
            if self.media_player:
                media = self.media_player.get_media()
                if media:
                    media.release()
                self.media_player.release()
                self.media_player = None
                
            # 释放 VLC 实例
            if self.instance:
                self.instance.release()
                self.instance = None
                
        except Exception as e:
            logger.error(f"资源清理失败: {str(e)}")

    def _release_sync(self):
        """同步释放资源（用于关闭事件）"""
        try:
            if self.media_player:
                self.media_player.stop()
                self.media_player.release()
            if self.instance:
                self.instance.release()
        except Exception as e:
            logger.error(f"同步释放失败: {str(e)}")
        finally:
            self.media_player = None
            self.instance = None
