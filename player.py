from datetime import timedelta
import vlc
import asyncio
import platform
import logging
import sys
import os
from typing import List
from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtCore import pyqtSignal
from utils import check_gpu_driver
from signals import AppSignals
from config_manager import ConfigHandler
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
    
    # 生成VLC启动参数
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
    # 初始化
    def __init__(self, parent=None):
        super().__init__(parent)
        self.signals = parent.signals if hasattr(parent, 'signals') else AppSignals()
        self.config = ConfigHandler()
        VLCInstanceManager.initialize(self.config)
        self.media_player = None
        self._release_lock = asyncio.Lock()
        self._is_active = False
        self._is_closing = False  # 窗口关闭标志
        self._current_task = None  # 当前异步任务
        self._init_vlc()
        self._init_ui()
        self._setup_connections()

    # 初始化VLC
    def _init_vlc(self):
        try:
            self.media_player = VLCInstanceManager.get_instance().media_player_new()
            self._is_active = True
            QtCore.QTimer.singleShot(100, self._bind_video_window)
        except Exception as e:
            logger.error(f"初始化失败: {str(e)}")
            self.signals.player_state_changed.emit("初始化失败")

    # 初始化UI
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
        
        # EPG节目单显示区域
        self.epg_table = QtWidgets.QTableWidget()
        self.epg_table.setColumnCount(4)
        self.epg_table.setHorizontalHeaderLabels(["时间", "节目名称", "时长", "描述"])
        self.epg_table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.epg_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.epg_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.epg_table.setStyleSheet("""
            QTableWidget {
                background-color: #2d2d2d;
                color: #e0e0e0;
                border: 1px solid #444;
                border-radius: 4px;
                gridline-color: #444;
            }
            QHeaderView::section {
                background-color: #3a3a3a;
                padding: 5px;
                border: none;
            }
            QTableWidget::item {
                padding: 5px;
            }
            QTableWidget::item:selected {
                background-color: #4a4a4a;
            }
        """)
        self.epg_table.setMaximumHeight(200)
        
        # 主布局
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.video_frame)
        layout.addWidget(self.epg_table)
        self.setLayout(layout)

    # 绑定视频到窗口
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
                    
                self._current_task = asyncio.current_task()
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
                self.signals.player_state_changed.emit("已暂停")
            else:
                self.media_player.play()
                self.signals.player_state_changed.emit("播放中")
        except Exception as e:
            logger.error(f"暂停失败: {str(e)}")
            self._init_vlc()

    # 停止播放(异步方法)
    async def stop(self) -> None:
        """停止播放(异步方法)"""
        async with self._release_lock:
            if not self._is_active or not self.media_player or not hasattr(self.media_player, 'is_playing'):
                self._is_active = False
                self.signals.player_state_changed.emit("播放已停止")
                return
                
            try:
                if not self.media_player.is_playing():
                    self._is_active = False
                    self.signals.player_state_changed.emit("播放已停止")
                    return
                    
                # 双重检查锁内状态
                if not self.media_player or not hasattr(self.media_player, 'is_playing'):
                    self._is_active = False
                    self.signals.player_state_changed.emit("播放已停止")
                    return
                    
                await asyncio.wait_for(self._run_release_sync(), timeout=5.0)
                
                self._is_active = False
                self.signals.player_state_changed.emit("播放已停止")
            except asyncio.TimeoutError:
                logger.warning("异步释放超时，强制停止")
                self.force_stop()
            except asyncio.CancelledError:
                logger.debug("停止操作被取消")
                raise
            except Exception as e:
                logger.error(f"停止播放失败: {str(e)}")
                self.force_stop()

    # 异步释放资源
    def async_release(self):
        """异步释放资源"""
        if not self._is_active:
            return
            
        self._is_active = False
        
        if not self.media_player:
            self.signals.player_state_changed.emit("播放已停止")
            return
            
        try:
            # 创建worker前检查对象有效性
            if not self.media_player or not hasattr(self.media_player, 'is_playing'):
                self.signals.player_state_changed.emit("播放已停止")
                return
                
            worker = AsyncWorker(self._release_sync)
            worker.finished.connect(lambda: self.signals.player_state_changed.emit("播放已停止"))
            worker.error.connect(lambda e: logger.error(f"异步释放失败: {str(e)}"))
            worker.start()
        except Exception as e:
            logger.error(f"异步释放异常: {str(e)}")
            self.force_stop()

    # 在异步上下文中运行同步释放
    async def _run_release_sync(self):
        """在异步上下文中运行同步释放"""
        if not self.media_player or not hasattr(self.media_player, 'is_playing'):
            return
            
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(None, self._release_sync)
        except asyncio.CancelledError:
            logger.debug("_run_release_sync被取消")
        except Exception as e:
            logger.error(f"_run_release_sync失败: {str(e)}")
            raise
        
    # 强制停止播放(调用同步释放)
    def force_stop(self):
        """强制停止播放(调用同步释放)"""
        if not self._is_active:
            logger.debug("force_stop: 播放器已处于非活动状态")
            return
            
        try:
            logger.debug("force_stop: 开始强制停止播放")
            
            # 1. 停止播放
            if self.media_player and self.media_player.is_playing():
                self.media_player.stop()
                
            # 2. 释放媒体资源
            if self.media_player:
                media = self.media_player.get_media()
                if media:
                    media.release()
                    
            # 3. 释放播放器
            if self.media_player:
                self.media_player.release()
                
            logger.debug("force_stop: 强制停止完成")
        except Exception as e:
            logger.error(f"强制停止失败: {str(e)}", exc_info=True)
        finally:
            self.media_player = None
            self._is_active = False
            self.signals.player_state_changed.emit("播放已强制停止")

    # 初始化信号连接
    def _setup_connections(self):
        """初始化信号连接"""
        try:
            event_manager = self.media_player.event_manager()
            event_manager.event_attach(vlc.EventType.MediaPlayerPlaying, self._on_play)
            event_manager.event_attach(vlc.EventType.MediaPlayerStopped, self._on_stop)
            event_manager.event_attach(vlc.EventType.MediaPlayerPaused, self._on_pause)
        except Exception as e:
            pass
        
        # 连接EPG数据更新信号
        if hasattr(self.parent(), 'epg_updated'):
            self.parent().epg_updated.connect(self.update_epg_display)

    # 初始化管理器
    def _init_managers(self):
        """初始化管理器（关键！）"""
        VLCInstanceManager.initialize(self.config)

    # 设置音量
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

    # 播放事件处理
    def _on_play(self, event):
        """播放事件处理"""
        self.signals.player_state_changed.emit("正在播放...")
        self.update_epg_display()

    # 暂停事件处理
    def _on_pause(self, event):
        """暂停事件处理"""
        self.signals.player_state_changed.emit("播放已暂停")

    # 停止事件处理
    def _on_stop(self, event):
        """停止事件处理"""
        self.signals.player_state_changed.emit("播放停止")
        self.clear_epg_display()

    # 窗口关闭事件处理
    def closeEvent(self, event):
        """重写窗口关闭事件，确保同步释放资源"""
        logger.debug("closeEvent: 窗口关闭中...")
        # 设置关闭标志，阻止后续异步操作
        self._is_closing = True
        # 取消所有异步任务
        if hasattr(self, '_current_task') and self._current_task and not self._current_task.done():
            try:
                self._current_task.cancel()
            except Exception as e:
                logger.warning(f"取消播放任务失败: {str(e)}")
        # 同步释放资源
        try:
            self.force_stop()
        except Exception as e:
            logger.error(f"关闭时强制停止失败: {str(e)}")
        finally:
            event.accept()

    # 资源清理  
    def __del__(self):
        """资源清理（调用同步释放）"""
        try:
            logger.debug("__del__: 对象销毁中...")
            self._release_sync()
        except Exception as e:
            logger.error(f"资源清理失败: {str(e)}")

    # 同步释放资源
    def _release_sync(self):
        """同步释放资源"""
        if not self.media_player or not hasattr(self.media_player, 'is_playing'):
            logger.debug("_release_sync: 无效的media_player对象")
            return
            
        try:
            # 双重检查对象有效性
            if not self.media_player or not hasattr(self.media_player, 'is_playing'):
                return
                
            if self.media_player.is_playing():
                self.media_player.stop()
                
            media = self.media_player.get_media()
            if media and hasattr(media, 'release'):
                media.release()
                
            if hasattr(self.media_player, 'release'):
                self.media_player.release()
        except Exception as e:
            logger.error(f"资源释放失败: {str(e)}", exc_info=True)
        finally:
            self.media_player = None
            if hasattr(self, 'instance'):
                self.instance = None

    # 更新EPG显示
    def update_epg_display(self, channel_name: str = None):
        """更新EPG节目单显示"""
        if not hasattr(self, 'epg_table'):
            return
            
        try:
            # 获取当前播放的频道名称
            if not channel_name and hasattr(self.parent(), 'get_current_channel'):
                channel_name = self.parent().get_current_channel()
                
            if not channel_name:
                self.clear_epg_display()
                return
                
            # 从EPG管理器获取节目单
            if hasattr(self.parent(), 'epg_manager'):
                epg_data = self.parent().epg_manager.get_channel_epg(channel_name)
                if not epg_data:
                    self.clear_epg_display()
                    return
                    
                # 更新表格数据
                self.epg_table.setRowCount(len(epg_data))
                for row, program in enumerate(epg_data):
                    self.epg_table.setItem(row, 0, QtWidgets.QTableWidgetItem(
                        program['start'].strftime('%H:%M')))
                    self.epg_table.setItem(row, 1, QtWidgets.QTableWidgetItem(
                        program['title']))
                    self.epg_table.setItem(row, 2, QtWidgets.QTableWidgetItem(
                        str(timedelta(seconds=program['duration']))))
                    self.epg_table.setItem(row, 3, QtWidgets.QTableWidgetItem(
                        program['description']))
        except Exception as e:
            logger.error(f"更新EPG显示失败: {str(e)}")

    # 清空EPG显示
    def clear_epg_display(self):
        """清空EPG节目单显示"""
        if hasattr(self, 'epg_table'):
            self.epg_table.setRowCount(0)
