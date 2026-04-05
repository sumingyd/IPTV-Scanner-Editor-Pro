import sys
import json
import subprocess
import os
import time
from PyQt6.QtCore import QObject, pyqtSignal, QThread
from PyQt6.QtGui import QImage, QPixmap
from core.log_manager import global_logger
from ffpyplayer.player import MediaPlayer
from ffpyplayer.tools import set_log_level

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

class FFmpegPlayerController(QObject):
    play_error = pyqtSignal(str)
    play_state_changed = pyqtSignal(bool)  # True=播放中, False=停止
    media_info_ready = pyqtSignal(dict)  # 当获取到信息时发射此信号
    video_frame_ready = pyqtSignal(QImage)  # 视频帧就绪信号

    def __init__(self, video_widget, channel_model=None):
        super().__init__()
        self.logger = global_logger
        self.video_widget = video_widget
        self.channel_model = channel_model
        self.player = None
        self.is_playing = False
        self.current_url = None
        self.media_info = {}
        self.playback_thread = None
        
        # 禁用ffpyplayer日志
        set_log_level("quiet")
        
        # 连接信号
        self.media_info_ready.connect(self._on_media_info_ready)

    def _on_media_info_ready(self, info):
        """当获取到信息时调用"""
        self.media_info = info

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
            
            # 记录当前URL
            self.current_url = url
            
            # 创建新的播放器实例
            self.player = MediaPlayer(url)
            
            # 启动播放线程
            self.playback_thread = PlaybackThread(self.player, self)
            self.playback_thread.start()
            
            # 获取媒体信息
            self._get_media_info(url)
            
            # 标记为播放中
            self.is_playing = True
            self.play_state_changed.emit(True)
            
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
            if self.playback_thread:
                self.playback_thread.stop()
                self.playback_thread.wait()
                self.playback_thread = None
            
            if self.player:
                self.player.stop()
                self.player = None
            
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
            if self.player:
                self.player.toggle_pause()
                self.logger.info("暂停播放")
        except Exception as e:
            self.logger.error(f"暂停播放失败: {str(e)}")

    def set_volume(self, volume):
        """设置音量
        Args:
            volume: 音量值 (0-100)
        """
        try:
            if self.player:
                self.player.set_volume(volume / 100.0)
                self.logger.info(f"设置音量: {volume}")
        except Exception as e:
            self.logger.error(f"设置音量失败: {str(e)}")

    def get_volume(self):
        """获取当前音量
        Returns:
            音量值 (0-100)
        """
        try:
            if self.player:
                return int(self.player.get_volume() * 100)
            return 50  # 默认音量
        except Exception as e:
            self.logger.error(f"获取音量失败: {str(e)}")
            return 50

    def _get_media_info(self, url):
        """获取媒体信息
        Args:
            url: 媒体URL
        """
        try:
            # 使用ffprobe获取媒体信息
            info = self._get_ffprobe_info(url)
            if info:
                self.media_info_ready.emit(info)
            else:
                # 如果ffprobe失败，尝试从播放器获取
                if self.player:
                    metadata = self.player.get_metadata()
                    if metadata:
                        info = {
                            'format': metadata.get('format', ''),
                            'duration': metadata.get('duration', 0),
                        }
                        self.media_info_ready.emit(info)
        except Exception as e:
            self.logger.error(f"获取媒体信息失败: {str(e)}")

    def _get_ffprobe_path(self):
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

class PlaybackThread(QThread):
    def __init__(self, player, controller):
        super().__init__()
        self.player = player
        self.controller = controller
        self.running = True

    def run(self):
        """播放线程主函数"""
        while self.running:
            try:
                # 获取视频帧
                frame, val = self.player.get_frame()
                if val != 'eof' and frame is not None:
                    # 转换为QImage
                    img, t = frame
                    if img is not None:
                        w, h, channels = img.shape
                        if channels == 3:
                            qimg = QImage(img.data, w, h, 3 * w, QImage.Format_RGB888)
                            self.controller.video_frame_ready.emit(qimg)
                
                # 短暂休眠，避免CPU占用过高
                time.sleep(0.01)
            except Exception as e:
                self.controller.logger.error(f"播放线程错误: {str(e)}")
                break

    def stop(self):
        """停止播放线程"""
        self.running = False
