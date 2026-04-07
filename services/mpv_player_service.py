import sys
import json
import subprocess
import os
import time
import ctypes
from ctypes import wintypes
from PyQt6.QtCore import QObject, pyqtSignal, QThread, QCoreApplication, QTimer, QRunnable
from PyQt6.QtGui import QImage, QPixmap
from core.log_manager import global_logger

# 设置环境变量，告诉python-mpv在哪里找到mpv
mpv_dir = os.path.join(os.getcwd(), 'mpv')
os.environ['MPV_HOME'] = mpv_dir
os.environ['PATH'] = mpv_dir + os.pathsep + os.environ['PATH']

# 检查是否存在libmpv-2.dll
libmpv_path = os.path.join(mpv_dir, 'libmpv-2.dll')
if os.path.exists(libmpv_path):
    # 设置MPV_LIBRARY环境变量，指定libmpv-2.dll的路径
    os.environ['MPV_LIBRARY'] = libmpv_path

else:
    print(f"未找到libmpv-2.dll: {libmpv_path}")

# 定义libmpv相关的结构体和函数
try:
    # 加载libmpv-2.dll
    libmpv = ctypes.CDLL(libmpv_path)

    
    # 定义函数类型
    libmpv.mpv_create.restype = ctypes.c_void_p
    libmpv.mpv_create.argtypes = []
    
    libmpv.mpv_initialize.restype = ctypes.c_int
    libmpv.mpv_initialize.argtypes = [ctypes.c_void_p]
    
    libmpv.mpv_set_property_string.restype = ctypes.c_int
    libmpv.mpv_set_property_string.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p]
    
    libmpv.mpv_set_property.restype = ctypes.c_int
    libmpv.mpv_set_property.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int, ctypes.c_void_p]
    
    libmpv.mpv_command.restype = ctypes.c_int
    libmpv.mpv_command.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_char_p)]
    
    libmpv.mpv_destroy.restype = None
    libmpv.mpv_destroy.argtypes = [ctypes.c_void_p]
    
    libmpv.mpv_observe_property.restype = ctypes.c_int
    libmpv.mpv_observe_property.argtypes = [ctypes.c_void_p, ctypes.c_uint64, ctypes.c_char_p, ctypes.c_int]
    
    libmpv.mpv_set_wakeup_callback.restype = None
    libmpv.mpv_set_wakeup_callback.argtypes = [ctypes.c_void_p, ctypes.CFUNCTYPE(None, ctypes.c_void_p), ctypes.c_void_p]
    
    libmpv.mpv_wait_event.restype = ctypes.c_void_p
    libmpv.mpv_wait_event.argtypes = [ctypes.c_void_p, ctypes.c_double]
    
    # 添加获取属性的函数
    libmpv.mpv_get_property_string.restype = ctypes.c_int
    libmpv.mpv_get_property_string.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.POINTER(ctypes.c_char_p)]
    
    libmpv.mpv_free.restype = None
    libmpv.mpv_free.argtypes = [ctypes.c_void_p]
    
    # 定义事件结构体
    class mpv_event(ctypes.Structure):
        _fields_ = [
            ('event_id', ctypes.c_int),
            ('error', ctypes.c_int),
            ('reply_userdata', ctypes.c_uint64),
            ('data', ctypes.c_void_p)
        ]
    
    # 事件ID
    MPV_EVENT_NONE = 0
    MPV_EVENT_SHUTDOWN = 1
    MPV_EVENT_LOG_MESSAGE = 2
    MPV_EVENT_GET_PROPERTY_REPLY = 3
    MPV_EVENT_SET_PROPERTY_REPLY = 4
    MPV_EVENT_COMMAND_REPLY = 5
    MPV_EVENT_START_FILE = 6
    MPV_EVENT_END_FILE = 7
    MPV_EVENT_FILE_LOADED = 8
    MPV_EVENT_CLIENT_MESSAGE = 9
    MPV_EVENT_VIDEO_RECONFIG = 10
    MPV_EVENT_AUDIO_RECONFIG = 11
    MPV_EVENT_SEEK = 12
    MPV_EVENT_PLAYBACK_RESTART = 13
    MPV_EVENT_PROPERTY_CHANGE = 14
    MPV_EVENT_QUEUE_OVERFLOW = 15
    MPV_EVENT_ERROR = 16
    
    # 属性格式
    MPV_FORMAT_STRING = 0
    MPV_FORMAT_OSD_STRING = 1
    MPV_FORMAT_FLAG = 2
    MPV_FORMAT_INT64 = 3
    MPV_FORMAT_DOUBLE = 4
    MPV_FORMAT_NODE = 5
    

except Exception as e:
    print(f"使用ctypes加载libmpv-2.dll失败: {str(e)}")
    libmpv = None

# 尝试导入mpv
try:
    import mpv

except Exception as e:
    print(f"导入mpv模块失败: {str(e)}")
    mpv = None

# 编码映射表 - 将 FourCC 编码转换为人类可读的名称
VIDEO_CODEC_MAP = {
    'h264': 'H.264',
    'avc1': 'H.264',
    'h265': 'H.265',
    'hevc': 'H.265',
    'vp9': 'VP9',
    'vp8': 'VP8',
    'av01': 'AV1',
    'mpeg': 'MPEG-2',
    'mp2v': 'MPEG-2',
    'mp4v': 'MPEG-4',
    'divx': 'DivX',
    'xvid': 'XviD',
    'wmv3': 'WMV3',
    'wmv2': 'WMV2',
    'wmv1': 'WMV1',
    'theo': 'Theora',
    'flv1': 'FLV',
    'rv40': 'RealVideo 4',
    'rv30': 'RealVideo 3',
    '462h': 'H.264',  # 常见的 H.264 变体
    '462H': 'H.264',
    'avc3': 'H.264',
    'hvc1': 'H.265',
    'hev1': 'H.265',
    'vp09': 'VP9',
    'av00': 'AV1',
}

AUDIO_CODEC_MAP = {
    'aac': 'AAC',
    'mp3': 'MP3',
    'mp2': 'MP2',
    'mp1': 'MP1',
    'ac3': 'AC-3',
    'eac3': 'E-AC-3',
    'dts': 'DTS',
    'dtsh': 'DTS-HD',
    'opus': 'Opus',
    'vorb': 'Vorbis',
    'flac': 'FLAC',
    'alac': 'ALAC',
    'wma': 'WMA',
    'pcm': 'PCM',
    'twos': 'PCM',
    'sowt': 'PCM',
    'lpcm': 'PCM',
    'agpm': 'AAC',  # 常见的 AAC 变体
    'aacp': 'AAC+',
    'aach': 'AAC-HE',
    'mp4a': 'AAC',
    'ac-3': 'AC-3',
    'dtsc': 'DTS',
    'dtsh': 'DTS-HD',
    'dtse': 'DTS-HD Master Audio',
}

class MpvPlayerController(QObject):
    play_error = pyqtSignal(str)
    play_state_changed = pyqtSignal(bool)  # True=播放中, False=停止
    media_info_ready = pyqtSignal(dict)  # 当获取到信息时发射此信号

    def __init__(self, video_widget, channel_model=None):
        super().__init__()
        self.logger = global_logger
        self.video_widget = video_widget
        self.channel_model = channel_model
        self.mpv_handle = None
        self.is_playing = False
        self.current_url = None
        self.media_info = {}
        self.event_timer = None
        
        # 初始化mpv播放器
        try:
            # 检查libmpv是否加载成功
            if libmpv is None:
                error_msg = "libmpv-2.dll加载失败"
                self.logger.error(error_msg)
                self.play_error.emit(error_msg)
                return
            
            # 创建mpv实例
            self.mpv_handle = libmpv.mpv_create()
            if not self.mpv_handle:
                error_msg = "创建mpv实例失败"
                self.logger.error(error_msg)
                self.play_error.emit(error_msg)
                return
            
            # 获取视频窗口的句柄
            window_id = self.video_widget.winId()
            # 确保window_id是整数
            if hasattr(window_id, 'value'):
                window_id = window_id.value
            
            # 设置窗口ID，确保mpv嵌入到PyQt窗口中
            try:
                # 直接使用字符串形式设置窗口ID
                window_id_int = int(window_id)
                window_id_str = f"{window_id_int}".encode('utf-8')
                result = libmpv.mpv_set_property_string(self.mpv_handle, b'wid', window_id_str)
                if result < 0:
                    self.logger.error(f"使用字符串设置窗口ID失败: {result}")
                else:
                    self.logger.debug(f"成功使用字符串设置窗口ID: {window_id_int}")
            except Exception as e:
                self.logger.error(f"设置窗口ID失败: {str(e)}")
            
            # 设置其他属性 - 优化内嵌渲染模式
            # 使用gpu渲染器，并指定窗口嵌入模式
            libmpv.mpv_set_property_string(self.mpv_handle, b'vo', b'gpu')
            # 启用硬件解码
            libmpv.mpv_set_property_string(self.mpv_handle, b'hwdec', b'auto')
            # 禁用内置控制器
            libmpv.mpv_set_property_string(self.mpv_handle, b'osc', b'no')
            libmpv.mpv_set_property_string(self.mpv_handle, b'osd-bar', b'no')
            # 设置日志级别
            libmpv.mpv_set_property_string(self.mpv_handle, b'log-level', b'error')
            # 禁用窗口装饰
            libmpv.mpv_set_property_string(self.mpv_handle, b'no-window-dragging', b'yes')
            # 确保视频渲染在正确的层级
            libmpv.mpv_set_property_string(self.mpv_handle, b'window-scale', b'1.0')
            # 禁用窗口边框
            libmpv.mpv_set_property_string(self.mpv_handle, b'border', b'no')
            
            # 初始化mpv
            result = libmpv.mpv_initialize(self.mpv_handle)
            if result < 0:
                error_msg = f"初始化mpv失败: {result}"
                self.logger.error(error_msg)
                self.play_error.emit(error_msg)
                libmpv.mpv_destroy(self.mpv_handle)
                self.mpv_handle = None
                return
            
            self.logger.info("mpv播放器初始化成功")
            
            # 启动事件处理定时器
            self.event_timer = QTimer(self)
            self.event_timer.timeout.connect(self._process_events)
            self.event_timer.start(100)  # 每100毫秒处理一次事件
            
        except Exception as e:
            error_msg = f"初始化mpv播放器失败: {str(e)}"
            self.logger.error(error_msg)
            self.play_error.emit(error_msg)
            if self.mpv_handle:
                libmpv.mpv_destroy(self.mpv_handle)
                self.mpv_handle = None
    
    def _process_events(self):
        """处理mpv事件"""
        if not self.mpv_handle:
            return
        
        try:
            while True:
                event_ptr = libmpv.mpv_wait_event(self.mpv_handle, 0)
                if not event_ptr:
                    break
                
                event = ctypes.cast(event_ptr, ctypes.POINTER(mpv_event)).contents
                event_id = event.event_id
                
                if event_id == MPV_EVENT_NONE:
                    break
                elif event_id == MPV_EVENT_PLAYBACK_RESTART:
                    self.is_playing = True
                    self.play_state_changed.emit(True)
                elif event_id == MPV_EVENT_END_FILE:
                    self.is_playing = False
                    self.play_state_changed.emit(False)
                elif event_id == MPV_EVENT_ERROR:
                    self.is_playing = False
                    self.play_state_changed.emit(False)
                
                # 释放事件 - 检查mpv_event_unref函数是否存在
                if hasattr(libmpv, 'mpv_event_unref'):
                    libmpv.mpv_event_unref(event_ptr)
        except Exception as e:
            self.logger.error(f"处理mpv事件失败: {str(e)}")
    
    def play(self, url, channel_name=None, **kwargs):
        """播放媒体
        Args:
            url: 媒体URL
            channel_name: 频道名称
            **kwargs: 其他参数
        """
        try:
            # 停止当前播放
            self.stop()
            
            if not self.mpv_handle:
                self.logger.error("mpv播放器未初始化")
                self.play_error.emit("mpv播放器未初始化")
                return False
            
            # 记录当前URL
            self.current_url = url
            
            # 构建播放命令
            cmd = [b'loadfile', url.encode('utf-8'), None]
            cmd_ptr = (ctypes.c_char_p * len(cmd))(*cmd)
            result = libmpv.mpv_command(self.mpv_handle, cmd_ptr)
            
            if result < 0:
                error_msg = f"播放失败: {result}"
                self.logger.error(error_msg)
                self.play_error.emit(error_msg)
                return False
            
            # 标记为播放中
            self.is_playing = True
            self.play_state_changed.emit(True)
            
            # 获取媒体信息
            self._get_media_info(url)
            
            self.logger.info(f"开始播放: {url}")
            
            return True
        except Exception as e:
            error_msg = f"播放失败: {str(e)}"
            self.logger.error(error_msg)
            self.play_error.emit(error_msg)
            return False
    
    def stop(self):
        """停止播放"""
        try:
            if self.mpv_handle:
                cmd = [b'stop', None]
                cmd_ptr = (ctypes.c_char_p * len(cmd))(*cmd)
                libmpv.mpv_command(self.mpv_handle, cmd_ptr)
            
            # 取消媒体信息获取任务
            if hasattr(self, '_media_info_timer') and self._media_info_timer:
                self._media_info_timer.stop()
            
            # 取消ffprobe任务
            if hasattr(self, '_current_ffprobe_worker') and self._current_ffprobe_worker:
                self._current_ffprobe_worker.is_running = False
                delattr(self, '_current_ffprobe_worker')
            
            self.is_playing = False
            self.play_state_changed.emit(False)
            self.current_url = None
            self.media_info = {}
            
            self.logger.info("停止播放")
        except Exception as e:
            self.logger.error(f"停止播放失败: {str(e)}")
    
    def pause(self):
        """暂停播放"""
        try:
            if self.mpv_handle:
                cmd = [b'cycle', b'pause', None]
                cmd_ptr = (ctypes.c_char_p * len(cmd))(*cmd)
                result = libmpv.mpv_command(self.mpv_handle, cmd_ptr)
                if result < 0:
                    self.logger.error(f"切换暂停状态失败，错误码: {result}")
                else:
                    self.logger.debug("切换暂停状态")
        except Exception as e:
            self.logger.error(f"暂停播放失败: {str(e)}")
    
    def toggle_pause(self):
        """切换暂停状态"""
        self.pause()
    
    def set_volume(self, volume):
        """设置音量
        Args:
            volume: 音量值 (0-100)
        """
        try:
            # 保存音量
            self._last_volume = volume
            
            if self.mpv_handle:
                # 使用字符串设置音量
                volume_str = f"{volume}".encode('utf-8')
                result = libmpv.mpv_set_property_string(self.mpv_handle, b'volume', volume_str)
                if result < 0:
                    self.logger.error(f"设置音量失败，错误码: {result}")
                else:
                    self.logger.debug(f"设置音量: {volume}")
        except Exception as e:
            self.logger.error(f"设置音量失败: {str(e)}")
    
    def get_volume(self):
        """获取当前音量
        Returns:
            音量值 (0-100)
        """
        try:
            if not hasattr(self, '_last_volume'):
                self._last_volume = 80  # 默认音量
            
            # 尝试从mpv获取音量
            volume_value = self._get_mpv_property_double('volume')
            if volume_value is not None:
                self._last_volume = int(volume_value)
            return self._last_volume
        except Exception:
            # 如果失败，返回上次保存的音量
            return getattr(self, '_last_volume', 80)
    
    def get_current_time(self):
        """获取当前播放时间
        Returns:
            当前播放时间（毫秒）
        """
        try:
            time_seconds = self._get_mpv_property_double('time-pos')
            if time_seconds:
                return int(time_seconds * 1000)
            return 0
        except Exception:
            # 静默处理异常，避免产生大量日志
            return 0
    
    def get_total_time(self):
        """获取总播放时间
        Returns:
            总播放时间（毫秒）
        """
        try:
            duration_seconds = self._get_mpv_property_double('duration')
            if duration_seconds:
                return int(duration_seconds * 1000)
            return 0
        except Exception:
            # 静默处理异常，避免产生大量日志
            return 0

    def get_position(self):
        """获取当前播放位置
        Returns:
            当前播放位置（0-1之间的浮点数）
        """
        try:
            percent_pos = self._get_mpv_property_double('percent-pos')
            if percent_pos:
                return percent_pos / 100.0
            return 0
        except Exception:
            # 静默处理异常，避免产生大量日志
            return 0
    
    def seek(self, position):
        """设置播放位置
        Args:
            position: 播放位置（0-1之间的浮点数）
        """
        try:
            if self.mpv_handle:
                # 保存当前播放状态
                is_playing = not self._get_mpv_property_string('pause') or self._get_mpv_property_string('pause') == 'no'
                
                # 使用绝对位置（秒）进行seek
                # 先获取总时长
                duration_seconds = self._get_mpv_property_double('duration')
                if duration_seconds:
                    # 计算目标位置（秒）
                    target_position = duration_seconds * position
                    # 使用绝对位置进行seek
                    cmd = [b'seek', f'{target_position}'.encode('utf-8'), b'absolute', None]
                    cmd_ptr = (ctypes.c_char_p * len(cmd))(*cmd)
                    result = libmpv.mpv_command(self.mpv_handle, cmd_ptr)
                    
                    if result < 0:
                        self.logger.error(f"使用绝对位置设置播放位置失败，错误码: {result}")
                        # 如果失败，尝试使用百分比
                        seek_percent = position * 100.0
                        cmd = [b'seek', f'{seek_percent}'.encode('utf-8'), b'absolute-percent', None]
                        cmd_ptr = (ctypes.c_char_p * len(cmd))(*cmd)
                        result = libmpv.mpv_command(self.mpv_handle, cmd_ptr)
                        
                        if result < 0:
                            self.logger.error(f"使用百分比设置播放位置失败，错误码: {result}")
                        else:
                            self.logger.debug(f"使用百分比设置播放位置: {position}")
                    else:
                        self.logger.debug(f"使用绝对位置设置播放位置: {position}")
                else:
                    # 如果获取不到总时长，使用百分比
                    seek_percent = position * 100.0
                    cmd = [b'seek', f'{seek_percent}'.encode('utf-8'), b'absolute-percent', None]
                    cmd_ptr = (ctypes.c_char_p * len(cmd))(*cmd)
                    result = libmpv.mpv_command(self.mpv_handle, cmd_ptr)
                    
                    if result < 0:
                        self.logger.error(f"设置播放位置失败，错误码: {result}")
                    else:
                        self.logger.debug(f"设置播放位置: {position}")
                
                # 恢复播放状态
                if is_playing:
                    # 确保视频继续播放
                    cmd = [b'cycle', b'pause', None]
                    cmd_ptr = (ctypes.c_char_p * len(cmd))(*cmd)
                    libmpv.mpv_command(self.mpv_handle, cmd_ptr)
        except Exception as e:
            self.logger.error(f"设置播放位置失败: {str(e)}")
    


    @staticmethod
    def _get_ffprobe_path():
        """获取ffprobe路径"""
        # 1. 尝试从系统路径查找
        exe_path = 'ffprobe.exe'
        try:
            subprocess.run([exe_path, '-version'], capture_output=True, check=True)
            return exe_path
        except:
            pass
        
        # 2. 尝试从当前目录查找
        exe_path = os.path.join(os.getcwd(), 'ffprobe.exe')
        if os.path.exists(exe_path):
            return exe_path
        
        # 3. 尝试从ffmpeg目录查找
        exe_path = os.path.join(os.getcwd(), 'ffmpeg', 'bin', 'ffprobe.exe')
        if os.path.exists(exe_path):
            return exe_path
        
        # 4. 尝试从程序目录的其他位置查找
        for root, dirs, files in os.walk(os.getcwd()):
            for file in files:
                if file.lower() == 'ffprobe.exe':
                    return os.path.join(root, file)
        
        return None
    
    def _get_media_info(self, url):
        """使用libmpv获取媒体信息
        Args:
            url: 媒体URL
        """
        # 取消之前的媒体信息获取任务
        if hasattr(self, '_media_info_timer') and self._media_info_timer:
            self._media_info_timer.stop()
        
        # 延迟获取媒体信息，确保媒体已加载
        self._media_info_timer = QTimer(self)
        self._media_info_timer.singleShot(2000, self._try_get_media_info)
    
    def _try_get_media_info(self):
        """尝试获取媒体信息"""
        if not self.mpv_handle:
            return
        
        try:
            # 直接使用ffprobe获取媒体信息
            if hasattr(self, 'current_url') and self.current_url:
                # 使用线程执行ffprobe，避免UI卡顿
                from PyQt6.QtCore import QThreadPool, QRunnable
                
                class FFProbeWorker(QRunnable):
                    def __init__(self, url, callback, parent):
                        super().__init__()
                        self.url = url
                        self.callback = callback
                        self.parent = parent
                        self.is_running = True
                    
                    def run(self):
                        try:
                            import subprocess
                            import json
                            
                            # 检查ffprobe是否存在
                            try:
                                subprocess.run(['ffprobe', '-version'], capture_output=True, text=True, timeout=5)
                            except Exception:
                                self.callback(None)
                                return
                            
                            # 检查是否已经被取消
                            if not self.is_running:
                                return
                            
                            # 构建ffprobe命令
                            cmd = [
                                'ffprobe',
                                '-v', 'quiet',
                                '-print_format', 'json',
                                '-show_format',
                                '-show_streams',
                                self.url
                            ]
                            
                            # 执行命令
                            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                            
                            # 检查是否已经被取消
                            if not self.is_running:
                                return
                            
                            if result.returncode == 0:
                                # 解析结果
                                data = json.loads(result.stdout)
                                
                                # 构建媒体信息
                                media_info = {
                                    'format': '未知',
                                    'duration': 0,
                                    'protocol': '未知',
                                    'video': {
                                        'codec': '未知',
                                        'width': 0,
                                        'height': 0,
                                        'frame_rate': 0,
                                        'bit_rate': 0
                                    },
                                    'audio': {
                                        'codec': '未知',
                                        'channels': 0,
                                        'sample_rate': 0,
                                        'bit_rate': 0
                                    }
                                }
                                
                                # 从当前URL获取协议信息
                                if '://' in self.url:
                                    media_info['protocol'] = self.url.split('://')[0].upper()
                                
                                # 处理格式信息
                                if 'format' in data:
                                    format_data = data['format']
                                    if 'format_name' in format_data:
                                        media_info['format'] = format_data['format_name']
                                    if 'duration' in format_data:
                                        try:
                                            media_info['duration'] = float(format_data['duration'])
                                        except:
                                            pass
                                
                                # 处理流信息
                                if 'streams' in data:
                                    for stream in data['streams']:
                                        if stream.get('codec_type') == 'video':
                                            if 'codec_name' in stream:
                                                media_info['video']['codec'] = stream['codec_name']
                                            if 'width' in stream:
                                                media_info['video']['width'] = stream['width']
                                            if 'height' in stream:
                                                media_info['video']['height'] = stream['height']
                                            if 'r_frame_rate' in stream:
                                                try:
                                                    num, den = map(int, stream['r_frame_rate'].split('/'))
                                                    if den > 0:
                                                        media_info['video']['frame_rate'] = num / den
                                                except:
                                                    pass
                                            if 'bit_rate' in stream:
                                                try:
                                                    media_info['video']['bit_rate'] = int(stream['bit_rate'])
                                                except:
                                                    pass
                                        elif stream.get('codec_type') == 'audio':
                                            if 'codec_name' in stream:
                                                media_info['audio']['codec'] = stream['codec_name']
                                            if 'channels' in stream:
                                                media_info['audio']['channels'] = stream['channels']
                                            if 'sample_rate' in stream:
                                                try:
                                                    media_info['audio']['sample_rate'] = int(stream['sample_rate'])
                                                except:
                                                    pass
                                            if 'bit_rate' in stream:
                                                try:
                                                    media_info['audio']['bit_rate'] = int(stream['bit_rate'])
                                                except:
                                                    pass
                                
                                # 记录获取到的媒体信息
                                self.callback(media_info)
                            else:
                                self.callback(None)
                        except Exception:
                            self.callback(None)
                
                # 取消之前的ffprobe任务
                if hasattr(self, '_current_ffprobe_worker') and self._current_ffprobe_worker:
                    self._current_ffprobe_worker.is_running = False
                
                # 启动线程
                def on_ffprobe_finished(media_info):
                    if media_info:
                        self.logger.info(f"使用ffprobe获取到媒体信息: {media_info}")
                        self.media_info_ready.emit(media_info)
                    # 清除当前worker
                    if hasattr(self, '_current_ffprobe_worker'):
                        delattr(self, '_current_ffprobe_worker')
                
                worker = FFProbeWorker(self.current_url, on_ffprobe_finished, self)
                self._current_ffprobe_worker = worker
                QThreadPool.globalInstance().start(worker)
                
        except Exception as e:
            self.logger.error(f"获取媒体信息失败: {str(e)}")
    
    def _get_mpv_property_string(self, property_name):
        """获取mpv字符串属性"""
        try:
            if not self.mpv_handle:
                return None
            
            value = ctypes.c_char_p()
            result = libmpv.mpv_get_property_string(
                self.mpv_handle,
                property_name.encode('utf-8'),
                ctypes.byref(value)
            )
            if result < 0:
                return None
            if not value.value:
                return None
            property_value = value.value.decode('utf-8')
            libmpv.mpv_free(value)
            return property_value
        except:
            return None
    
    def _get_mpv_property_int(self, property_name):
        """获取mpv整数属性"""
        try:
            if not self.mpv_handle:
                return None
            
            value = ctypes.c_int64()
            result = libmpv.mpv_get_property(
                self.mpv_handle,
                property_name.encode('utf-8'),
                MPV_FORMAT_INT64,
                ctypes.byref(value)
            )
            if result < 0:
                return None
            return value.value
        except:
            return None
    
    def _get_mpv_property_double(self, property_name):
        """获取mpv浮点数属性"""
        try:
            if not self.mpv_handle:
                return None
            
            value = ctypes.c_double()
            result = libmpv.mpv_get_property(
                self.mpv_handle,
                property_name.encode('utf-8'),
                MPV_FORMAT_DOUBLE,
                ctypes.byref(value)
            )
            if result < 0:
                return None
            return value.value
        except:
            return None
    
    from PyQt6.QtCore import pyqtSlot
    
    @pyqtSlot(dict)
    def _on_media_info_thread_finished(self, info):
        """媒体信息获取完成"""
        if info:
            self.media_info_ready.emit(info)
    
    @pyqtSlot(str)
    def _on_media_info_thread_error(self, error):
        """媒体信息获取错误"""
        self.logger.error(f"获取媒体信息失败: {error}")

class FFProbeWorker(QObject):
    """ffprobe工作线程"""
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    
    def __init__(self, url, ffprobe_path, logger):
        super().__init__()
        self.url = url
        self.ffprobe_path = ffprobe_path
        self.logger = logger
    
    def run(self):
        """执行ffprobe命令"""
        try:
            if not self.ffprobe_path:
                self.error.emit("未找到ffprobe可执行文件")
                return
            
            # 构建ffprobe命令
            cmd = [
                self.ffprobe_path,
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                self.url
            ]
            
            # 执行ffprobe命令，隐藏窗口
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10,
                startupinfo=startupinfo
            )
            
            if result.returncode != 0:
                self.error.emit(f"ffprobe执行失败: {result.stderr}")
                return
            
            data = json.loads(result.stdout)
            
            # 构建媒体信息
            info = {
                'format': data.get('format', {}).get('format_name', ''),
                'duration': float(data.get('format', {}).get('duration', 0)),
                'size': data.get('format', {}).get('size', 0),
                'bit_rate': data.get('format', {}).get('bit_rate', 0),
                'video': {},
                'audio': {}
            }
            
            # 提取视频流信息
            for stream in data.get('streams', []):
                if stream.get('codec_type') == 'video':
                    info['video']['codec'] = VIDEO_CODEC_MAP.get(stream.get('codec_name', '').lower(), stream.get('codec_name', ''))
                    info['video']['width'] = stream.get('width', 0)
                    info['video']['height'] = stream.get('height', 0)
                    info['video']['frame_rate'] = stream.get('r_frame_rate', '0/1').split('/')[0] if 'r_frame_rate' in stream else 0
                    info['video']['bit_rate'] = stream.get('bit_rate', 0)
                    break
            
            # 提取音频流信息
            for stream in data.get('streams', []):
                if stream.get('codec_type') == 'audio':
                    info['audio']['codec'] = AUDIO_CODEC_MAP.get(stream.get('codec_name', '').lower(), stream.get('codec_name', ''))
                    info['audio']['channels'] = stream.get('channels', 0)
                    info['audio']['sample_rate'] = stream.get('sample_rate', 0)
                    info['audio']['bit_rate'] = stream.get('bit_rate', 0)
                    break
            
            self.finished.emit(info)
        except Exception as e:
            self.error.emit(str(e))

    @staticmethod
    def _get_ffprobe_path():
        """获取ffprobe路径"""
        # 1. 尝试从打包后的路径查找
        if getattr(sys, 'frozen', False):
            base_path = os.path.dirname(sys.executable)
            exe_path = os.path.join(base_path, 'ffmpeg', 'bin', 'ffprobe.exe')
            if os.path.exists(exe_path):
                return exe_path
        
        # 2. 尝试从系统路径查找
        exe_path = 'ffprobe.exe'
        try:
            subprocess.run([exe_path, '-version'], capture_output=True, check=True)
            return exe_path
        except:
            pass
        
        # 3. 尝试从当前目录查找
        exe_path = os.path.join(os.getcwd(), 'ffprobe.exe')
        if os.path.exists(exe_path):
            return exe_path
        
        # 4. 尝试从ffmpeg目录查找
        exe_path = os.path.join(os.getcwd(), 'ffmpeg', 'bin', 'ffprobe.exe')
        if os.path.exists(exe_path):
            return exe_path
        
        # 5. 尝试从程序目录的其他位置查找
        for root, dirs, files in os.walk(os.getcwd()):
            for file in files:
                if file.lower() == 'ffprobe.exe':
                    return os.path.join(root, file)
        
        return None

    def _get_ffprobe_info(self, url):
        """使用ffprobe获取媒体信息
        Args:
            url: 媒体URL
        Returns:
            媒体信息字典
        """
        ffprobe_path = self._get_ffprobe_path()
        if not ffprobe_path:
            return None
        
        try:
            cmd = [
                ffprobe_path,
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                url
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                self.logger.error(f"ffprobe执行失败: {result.stderr}")
                return None
            
            data = json.loads(result.stdout)
            
            # 构建媒体信息
            info = {
                'format': data.get('format', {}).get('format_name', ''),
                'duration': float(data.get('format', {}).get('duration', 0)),
                'size': data.get('format', {}).get('size', 0),
                'bit_rate': data.get('format', {}).get('bit_rate', 0),
                'video': {},
                'audio': {}
            }
            
            # 提取视频流信息
            for stream in data.get('streams', []):
                if stream.get('codec_type') == 'video':
                    info['video']['codec'] = VIDEO_CODEC_MAP.get(stream.get('codec_name', '').lower(), stream.get('codec_name', ''))
                    info['video']['width'] = stream.get('width', 0)
                    info['video']['height'] = stream.get('height', 0)
                    info['video']['frame_rate'] = stream.get('r_frame_rate', '0/1').split('/')[0] if 'r_frame_rate' in stream else 0
                    info['video']['bit_rate'] = stream.get('bit_rate', 0)
                    break
            
            # 提取音频流信息
            for stream in data.get('streams', []):
                if stream.get('codec_type') == 'audio':
                    info['audio']['codec'] = AUDIO_CODEC_MAP.get(stream.get('codec_name', '').lower(), stream.get('codec_name', ''))
                    info['audio']['channels'] = stream.get('channels', 0)
                    info['audio']['sample_rate'] = stream.get('sample_rate', 0)
                    info['audio']['bit_rate'] = stream.get('bit_rate', 0)
                    break
            
            return info
        except Exception as e:
            self.logger.error(f"使用ffprobe获取媒体信息失败: {str(e)}")
            return None

# FFProbeRunnable类
class FFProbeRunnable(QRunnable):
    def __init__(self, worker):
        super().__init__()
        self.worker = worker
    
    def run(self):
        self.worker.run()
