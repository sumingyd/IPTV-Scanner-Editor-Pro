import vlc
import asyncio
import platform
import logging
import sys
import os
from typing import List
from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtCore import pyqtSignal
from utils import ConfigHandler, check_gpu_driver
from async_utils import AsyncWorker

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
                # 检查打包环境下的VLC路径
                if getattr(sys, 'frozen', False):
                    vlc_path = os.path.join(sys._MEIPASS, 'vlc')
                    os.environ['VLC_PLUGIN_PATH'] = os.path.join(vlc_path, 'plugins')
                
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
        """生成VLC启动参数
        包含隐藏窗口、控制台输出和硬件加速配置
        """
        args = [
            '--no-video-title-show',
            '--network-caching=3000',
            '--skip-frames',
            '--quiet',
            '--no-xlib',  # Linux/macOS隐藏X11窗口
            '--no-qt-error-dialogs',  # 隐藏Qt错误对话框
            '--no-qt-video-autoresize',  # 禁用自动调整大小
            '--no-embedded-video'  # 防止嵌入式视频弹出
        ]
        
        # 平台特定参数
        if platform.system() == 'Windows':
            args += [
                '--dshow-vdev=none',  # 隐藏Windows视频设备
                '--dshow-adev=none',  # 隐藏Windows音频设备
                '--no-dshow-config',  # 禁用Windows配置对话框
                '--directx-hw-yuv'
            ]
        
        # 硬件加速配置
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
        self.video_frame.setStyleSheet("""
            QFrame {
                background-color: black;
                border: 2px solid #444;
                border-radius: 6px;
            }
            QFrame:hover {
                border-color: #888;
                border-width: 3px;
            }
        """)
        self.video_frame.setGraphicsEffect(QtWidgets.QGraphicsDropShadowEffect(
            blurRadius=15,
            xOffset=3,
            yOffset=3,
            color=QtGui.QColor(0, 0, 0, 100)
        ))
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

    async def stop(self) -> None:
        """停止播放(异步方法)
        1. 检查当前是否正在播放
        2. 如果未播放则直接返回
        3. 如果正在播放则调用异步释放
        """
        try:
            logger.debug(f"stop: 开始停止播放 (active={self._is_active})")
            
            if not self._is_active:
                logger.debug("stop: 播放器未激活，无需停止")
                return
                
            if not self.media_player:
                logger.debug("stop: media_player为None")
                self._is_active = False
                self.state_changed.emit("播放已停止")
                return
                
            try:
                is_playing = self.media_player.is_playing()
                logger.debug(f"stop: 当前播放状态 - is_playing={is_playing}")
                
                if not is_playing:
                    logger.debug("stop: 当前没有播放内容，无需停止")
                    self._is_active = False
                    self.state_changed.emit("播放已停止")
                    return
                    
                logger.debug("stop: 正在异步停止播放...")
                await asyncio.wait_for(self._run_release_sync(), timeout=5.0)
                self._is_active = False
                self.state_changed.emit("播放已停止")
            except asyncio.TimeoutError:
                logger.warning("stop: 异步释放超时，强制停止")
                self.force_stop()
            except Exception as e:
                logger.error(f"stop: 播放状态检查失败 - {str(e)}")
                self.force_stop()
        except Exception as e:
            logger.error(f"stop: 方法异常 - {str(e)}")
            self.force_stop()

    def async_release(self):
        """异步释放资源(调用同步释放的异步版本)"""
        try:
            logger.debug("async_release: 开始异步释放资源")
            
            if not self._is_active:
                logger.debug("async_release: 播放器未激活")
                return
                
            self._is_active = False
            
            if not self.media_player:
                logger.debug("async_release: media_player为None")
                self.state_changed.emit("播放已停止")
                return
                
            try:
                # 使用AsyncWorker管理同步释放任务
                worker = AsyncWorker(self._release_sync)
                worker.finished.connect(lambda: self.state_changed.emit("播放已停止"))
                worker.error.connect(lambda e: logger.error(f"异步释放失败: {str(e)}"))
                worker.start()
            except Exception as e:
                logger.error(f"async_release: 内部异常 - {str(e)}")
                self.force_stop()
        except Exception as e:
            logger.error(f"async_release: 方法异常 - {str(e)}")
            self.force_stop()

    async def _run_release_sync(self):
        """在异步上下文中运行同步释放"""
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(None, self._release_sync)
        except Exception as e:
            logger.error(f"_run_release_sync失败: {str(e)}")
            raise
        

    def force_stop(self):
        """强制停止播放(调用同步释放)"""
        try:
            logger.debug("force_stop: 强制停止播放")
            self._release_sync()
        except Exception as e:
            logger.error(f"强制停止失败: {str(e)}")
            try:
                if self.media_player:
                    self.media_player.stop()
                    self.media_player.release()
            except Exception as inner_e:
                logger.error(f"强制释放失败: {str(inner_e)}")
        finally:
            self.media_player = None
            self._is_active = False

    def _setup_connections(self):
        """初始化信号连接"""
        try:
            event_manager = self.media_player.event_manager()
            event_manager.event_attach(vlc.EventType.MediaPlayerPlaying, self._on_play)
            event_manager.event_attach(vlc.EventType.MediaPlayerStopped, self._on_stop)
            event_manager.event_attach(vlc.EventType.MediaPlayerPaused, self._on_pause)
        except Exception as e:
            pass

    
    def _init_managers(self):
        """初始化管理器（关键！）"""
        VLCInstanceManager.initialize(self.config)

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
        """资源清理（调用同步释放）"""
        try:
            logger.debug("__del__: 对象销毁中...")
            self._release_sync()
        except Exception as e:
            logger.error(f"资源清理失败: {str(e)}")

    def _release_sync(self):
        """同步释放资源（用于关闭事件）"""
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                if self.media_player:
                    # 先停止播放
                    try:
                        self.media_player.stop()
                    except Exception as e:
                        logger.debug(f"停止播放失败(尝试 {attempt+1}): {str(e)}")

                    # 释放媒体资源
                    media = self.media_player.get_media()
                    if media:
                        try:
                            media.release()
                        except Exception as e:
                            logger.debug(f"媒体释放异常(尝试 {attempt+1}): {str(e)}")
                    
                    # 释放播放器
                    try:
                        self.media_player.release()
                        if attempt == max_attempts - 1:
                            logger.warning(f"资源释放不完全，已尝试{max_attempts}次")
                    except Exception as e:
                        logger.debug(f"播放器释放异常(尝试 {attempt+1}): {str(e)}")
                
                # 释放VLC实例
                if hasattr(self, 'instance') and self.instance:
                    try:
                        self.instance.release()
                    except Exception as e:
                        logger.debug(f"实例释放异常(尝试 {attempt+1}): {str(e)}")
                
                # 检查是否完全释放
                if attempt < max_attempts - 1 and (
                    (self.media_player and not hasattr(self.media_player, 'is_released')) or
                    (hasattr(self.media_player, 'is_released') and not self.media_player.is_released())
                ):
                    logger.debug(f"资源未完全释放，准备重试(尝试 {attempt+1})")
                    continue
                else:
                    break
                    
            except Exception as e:
                logger.error(f"同步释放失败(尝试 {attempt+1}): {str(e)}")
                if attempt == max_attempts - 1:
                    logger.error("资源释放最终失败")
            finally:
                self.media_player = None
                if hasattr(self, 'instance'):
                    self.instance = None
