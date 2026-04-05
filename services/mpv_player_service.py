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
    print(f"使用libmpv-2.dll: {libmpv_path}")
else:
    print(f"未找到libmpv-2.dll: {libmpv_path}")

# 定义libmpv相关的结构体和函数
try:
    # 加载libmpv-2.dll
    libmpv = ctypes.CDLL(libmpv_path)
    print("成功使用ctypes加载libmpv-2.dll")
    
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
    
    print("成功定义libmpv相关的结构体和函数")
except Exception as e:
    print(f"使用ctypes加载libmpv-2.dll失败: {str(e)}")
    libmpv = None

# 尝试导入mpv
try:
    import mpv
    print("成功导入mpv模块")
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
                    self.logger.info(f"成功使用字符串设置窗口ID: {window_id_int}")
            except Exception as e:
                self.logger.error(f"设置窗口ID失败: {str(e)}")
            
            # 设置其他属性
            libmpv.mpv_set_property_string(self.mpv_handle, b'vo', b'gpu')
            libmpv.mpv_set_property_string(self.mpv_handle, b'hwdec', b'auto')
            libmpv.mpv_set_property_string(self.mpv_handle, b'osc', b'no')
            libmpv.mpv_set_property_string(self.mpv_handle, b'osd-bar', b'no')
            libmpv.mpv_set_property_string(self.mpv_handle, b'log-level', b'error')
            
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
                libmpv.mpv_command(self.mpv_handle, cmd_ptr)
            self.logger.info("切换暂停状态")
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
            if self.mpv_handle:
                volume_str = f"{volume}".encode('utf-8')
                libmpv.mpv_set_property_string(self.mpv_handle, b'volume', volume_str)
            self.logger.info(f"设置音量: {volume}")
        except Exception as e:
            self.logger.error(f"设置音量失败: {str(e)}")
    
    def get_volume(self):
        """获取当前音量
        Returns:
            音量值 (0-100)
        """
        try:
            # 由于使用ctypes，暂时返回默认音量
            return 50  # 默认音量
        except Exception as e:
            self.logger.error(f"获取音量失败: {str(e)}")
            return 50
    
    def get_current_time(self):
        """获取当前播放时间
        Returns:
            当前播放时间（毫秒）
        """
        try:
            # 由于使用ctypes，暂时返回0
            return 0
        except Exception as e:
            self.logger.error(f"获取当前时间失败: {str(e)}")
            return 0
    
    def get_total_time(self):
        """获取总播放时间
        Returns:
            总播放时间（毫秒）
        """
        try:
            # 由于使用ctypes，暂时返回0
            return 0
        except Exception as e:
            self.logger.error(f"获取总时间失败: {str(e)}")
            return 0

    def get_position(self):
        """获取当前播放位置
        Returns:
            当前播放位置（0-1之间的浮点数）
        """
        try:
            # 由于使用ctypes，暂时返回0
            return 0
        except Exception as e:
            self.logger.error(f"获取播放位置失败: {str(e)}")
            return 0
    


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
        # 延迟获取媒体信息，确保媒体已加载
        QTimer.singleShot(2000, self._try_get_media_info)
    
    def _try_get_media_info(self):
        """尝试获取媒体信息"""
        if not self.mpv_handle:
            return
        
        try:
            # 尝试获取媒体信息，使用多种属性名称
            video_codec = (self._get_mpv_property_string('video-codec') or 
                          self._get_mpv_property_string('current-tracks/video/title'))
            width = self._get_mpv_property_int('width')
            height = self._get_mpv_property_int('height')
            fps = self._get_mpv_property_double('fps') or self._get_mpv_property_double('container-fps')
            
            audio_codec = (self._get_mpv_property_string('audio-codec') or 
                          self._get_mpv_property_string('current-tracks/audio/title'))
            channels = self._get_mpv_property_int('audio-channels') or self._get_mpv_property_int('audio-params/channels')
            sample_rate = self._get_mpv_property_int('audio-samplerate') or self._get_mpv_property_int('audio-params/samplerate')
            
            format_name = self._get_mpv_property_string('file-format') or self._get_mpv_property_string('format')
            duration = self._get_mpv_property_double('duration')
            protocol = self._get_mpv_property_string('file-protocol') or self._get_mpv_property_string('protocol')
            
            # 构建媒体信息
            media_info = {
                'format': format_name or '未知',
                'duration': duration or 0,
                'protocol': protocol or '未知',
                'video': {
                    'codec': video_codec or '未知',
                    'width': width or 0,
                    'height': height or 0,
                    'frame_rate': fps or 0,
                    'bit_rate': 0
                },
                'audio': {
                    'codec': audio_codec or '未知',
                    'channels': channels or 0,
                    'sample_rate': sample_rate or 0,
                    'bit_rate': 0
                }
            }
            
            self.logger.info(f"获取到媒体信息: {media_info}")
            self.media_info_ready.emit(media_info)
            
            # 如果没有获取到关键信息，再尝试几次
            if (video_codec == '未知' and audio_codec == '未知' and format_name == '未知'):
                if not hasattr(self, '_media_info_attempts'):
                    self._media_info_attempts = 0
                self._media_info_attempts += 1
                if self._media_info_attempts < 5:  # 最多尝试5次
                    QTimer.singleShot(1000, self._try_get_media_info)
                else:
                    self._media_info_attempts = 0
                
        except Exception as e:
            self.logger.error(f"使用libmpv获取媒体信息失败: {str(e)}")
    
    def _get_mpv_property_string(self, property_name):
        """获取mpv字符串属性"""
        try:
            value = ctypes.c_char_p()
            result = libmpv.mpv_get_property_string(
                self.mpv_handle,
                property_name.encode('utf-8'),
                ctypes.byref(value)
            )
            if result < 0 or not value.value:
                return None
            property_value = value.value.decode('utf-8')
            libmpv.mpv_free(value)
            return property_value
        except Exception:
            return None
    
    def _get_mpv_property_int(self, property_name):
        """获取mpv整数属性"""
        try:
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
        except Exception:
            return None
    
    def _get_mpv_property_double(self, property_name):
        """获取mpv浮点数属性"""
        try:
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
        except Exception:
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
