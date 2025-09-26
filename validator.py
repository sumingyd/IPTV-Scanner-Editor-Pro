import subprocess
import threading
import time
import json
import sys
import os
from typing import Dict, Optional
from log_manager import LogManager
from language_manager import LanguageManager

class StreamValidator:
    """使用ffmpeg检测视频流有效性"""
    
    _active_processes = []
    _process_lock = threading.Lock()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    def __init__(self, main_window=None):
        self.logger = LogManager()
        self._current_process = None
        # 使用主窗口的语言管理器，避免重复加载
        self.main_window = main_window
        if main_window and hasattr(main_window, 'language_manager'):
            self.language_manager = main_window.language_manager
        else:
            # 如果没有传入主窗口，创建独立的语言管理器（用于独立测试）
            self.language_manager = LanguageManager()
            self.language_manager.load_available_languages()

    @classmethod
    def terminate_all(cls):
        """终止所有活动的验证进程"""
        with cls._process_lock:
            for process in cls._active_processes:
                try:
                    if process.poll() is None:  # 检查进程是否仍在运行
                        process.kill()
                except:
                    pass
            cls._active_processes = []


    def _get_ffmpeg_path(self):
        """获取ffmpeg路径"""
        import os
        import sys
        
        # 记录所有尝试的路径
        tried_paths = []
        
        # 1. 尝试从打包后的路径查找
        if getattr(sys, 'frozen', False):
            base_path = os.path.dirname(sys.executable)
            exe_path = os.path.join(base_path, 'ffmpeg', 'bin', 'ffmpeg.exe')
            tried_paths.append(f"打包路径: {exe_path}")
            if os.path.exists(exe_path):
                return exe_path
        
        # 2. 尝试从开发环境路径查找
        dev_path = os.path.join(os.path.dirname(__file__), 'ffmpeg', 'bin', 'ffmpeg.exe')
        tried_paths.append(f"开发路径: {dev_path}")
        if os.path.exists(dev_path):
            return dev_path
            
        # 3. 尝试从系统PATH查找
        try:
            from shutil import which
            path = which('ffmpeg')
            tried_paths.append(f"系统PATH查找")
            if path:
                return path
        except ImportError:
            tried_paths.append("无法导入shutil.which")
            pass
            
        # 记录所有尝试过的路径
        self.logger.warning(
            "无法找到ffmpeg，尝试了以下路径:\n" + 
            "\n".join(tried_paths) +
            "\n将尝试直接调用'ffmpeg'"
        )
        return 'ffmpeg'  # 最后尝试直接调用

    def _get_ffprobe_path(self):
        """获取ffprobe路径"""
        import os
        import sys
        
        # 记录所有尝试的路径
        tried_paths = []
        
        # 1. 尝试从打包后的路径查找
        if getattr(sys, 'frozen', False):
            base_path = os.path.dirname(sys.executable)
            exe_path = os.path.join(base_path, 'ffmpeg', 'bin', 'ffprobe.exe')
            tried_paths.append(f"打包路径: {exe_path}")
            if os.path.exists(exe_path):
                return exe_path
        
        # 2. 尝试从开发环境路径查找
        dev_path = os.path.join(os.path.dirname(__file__), 'ffmpeg', 'bin', 'ffprobe.exe')
        tried_paths.append(f"开发路径: {dev_path}")
        if os.path.exists(dev_path):
            return dev_path
            
        # 3. 尝试从系统PATH查找
        try:
            from shutil import which
            path = which('ffprobe')
            tried_paths.append(f"系统PATH查找")
            if path:
                return path
        except ImportError:
            tried_paths.append("无法导入shutil.which")
            pass
            
        # 记录所有尝试过的路径
        self.logger.warning(
            "无法找到ffprobe，尝试了以下路径:\n" + 
            "\n".join(tried_paths) +
            "\n将尝试直接调用'ffprobe'"
        )
        return 'ffprobe'  # 最后尝试直接调用

    def _is_multicast_url(self, url: str) -> bool:
        """判断是否为组播地址"""
        url_lower = url.lower()
        # 包含/rtp/、/udp/、/rtsp/或以rtp://、udp://、rtsp://开头的URL视为组播
        return (url_lower.startswith(('rtp://', 'udp://', 'rtsp://')) or
                any(x in url_lower for x in ['/rtp/', '/udp/', '/rtsp/']))


    def _clean_channel_name(self, name: str) -> str:
        """清理频道名"""
        if not name:
            # 不使用语言管理器，直接返回空字符串
            return ''
            
        # 不再去除清晰度后缀，保持原始名称
        return name.strip()

    def _build_ffmpeg_command(self, url: str, duration: float = 3.0) -> list:
        """构建ffmpeg命令"""
        ffmpeg_path = self._get_ffmpeg_path()
        cmd = [
            ffmpeg_path,
            '-v', 'error',
            '-timeout', '5000000',  # 5秒超时
            '-t', str(duration),    # 拉取时长
            '-i', url,
            '-f', 'null',           # 输出到空设备
            '-'
        ]
        
        # 添加headers
        if hasattr(self, 'headers') and self.headers:
            for key, value in self.headers.items():
                if value:
                    cmd.extend(['-headers', f'{key}: {value}'])
        
        return cmd

    def _run_ffmpeg_test(self, url: str, timeout: int, max_retries: int = 2) -> Dict:
        """运行ffmpeg测试流有效性"""
        result = {
            'valid': False,
            'latency': None,
            'error': None,
            'retries': 0
        }
        
        start_time = time.time()
        
        for attempt in range(max_retries + 1):
            result['retries'] = attempt
            cmd = self._build_ffmpeg_command(url, min(3.0, timeout / 2))
            
            # 在Windows上需要处理特殊字符
            if sys.platform == 'win32':
                cmd = [arg.replace('^', '^^').replace('&', '^&') for arg in cmd]
            
            # 设置环境变量和工作目录
            env = os.environ.copy()
            env['PATH'] = os.path.dirname(self._get_ffmpeg_path()) + os.pathsep + env['PATH']
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=False,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0,
                shell=False,
                env=env,
                cwd=os.path.dirname(self._get_ffmpeg_path())
            )
            
            # 跟踪活动进程
            with self._process_lock:
                self._active_processes.append(process)
            self._current_process = process
            
            try:
                # 记录命令开始执行时间
                exec_start = time.time()
                stdout_bytes, stderr_bytes = process.communicate(timeout=timeout)
                exec_end = time.time()
                
                stdout = stdout_bytes.decode('utf-8', errors='replace') if stdout_bytes else ''
                stderr = stderr_bytes.decode('utf-8', errors='replace') if stderr_bytes else ''

                if process.returncode == 0:
                    # ffmpeg成功拉取流
                    result['valid'] = True
                    result['latency'] = int((exec_end - exec_start) * 1000)
                    break
                else:
                    # ffmpeg失败，记录错误信息
                    error_output = stderr.strip() or stdout.strip()
                    if error_output:
                        result['error'] = error_output
                    else:
                        result['error'] = f"ffmpeg返回错误代码: {process.returncode}"
                    
                    # 如果不是最后一次尝试，等待一下再重试
                    if attempt < max_retries:
                        time.sleep(0.5)
                        
            except subprocess.TimeoutExpired:
                process.kill()
                result['error'] = "拉流超时"
                # 超时不重试
                break
            except Exception as e:
                result['error'] = str(e)
                # 其他异常不重试
                break
            finally:
                # 清理已完成进程
                with self._process_lock:
                    if process in self._active_processes:
                        self._active_processes.remove(process)
        
        result['latency'] = result.get('latency', int((time.time() - start_time) * 1000))
        return result

    def _run_ffprobe(self, url: str, timeout: int) -> Dict:
        """执行ffprobe命令获取流详细信息"""
        result = {}
        
        ffprobe_path = self._get_ffprobe_path()
        cmd = [
            ffprobe_path,
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            '-show_programs',
            url
        ]
        
        # 在Windows上需要处理特殊字符
        if sys.platform == 'win32':
            cmd = [arg.replace('^', '^^').replace('&', '^&') for arg in cmd]
        
        # 设置环境变量和工作目录
        env = os.environ.copy()
        env['PATH'] = os.path.dirname(self._get_ffprobe_path()) + os.pathsep + env['PATH']
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=False,
            creationflags=subprocess.CREATE_NO_WINDOW,
            shell=True if sys.platform == 'win32' else False,
            env=env,
            cwd=os.path.dirname(self._get_ffprobe_path())
        )
        
        # 跟踪活动进程
        with self._process_lock:
            self._active_processes.append(process)
        self._current_process = process
        
        try:
            stdout_bytes, stderr_bytes = process.communicate(timeout=timeout)
            stdout = stdout_bytes.decode('utf-8', errors='replace')
            stderr = stderr_bytes.decode('utf-8', errors='replace')

            if process.returncode == 0:
                try:
                    data = json.loads(stdout)
                    result.update(self._parse_ffprobe_output(data))
                except json.JSONDecodeError:
                    result['error'] = stderr.strip()
            else:
                result['error'] = stderr.strip()
                
        except subprocess.TimeoutExpired:
            process.kill()
            result['error'] = "ffprobe超时"
        except Exception as e:
            result['error'] = str(e)
        finally:
            # 清理已完成进程
            with self._process_lock:
                if process in self._active_processes:
                    self._active_processes.remove(process)
                
        return result

    def _parse_ffprobe_output(self, data: Dict) -> Dict:
        """解析ffprobe输出"""
        result = {}
        
        # 获取频道名
        service_name = None
        if 'programs' in data and data['programs']:
            program = data['programs'][0]
            if 'tags' in program and 'service_name' in program['tags']:
                service_name = program['tags']['service_name']
        elif 'streams' in data and data['streams']:
            for stream in data['streams']:
                if 'tags' in stream and 'service_name' in stream['tags']:
                    service_name = stream['tags']['service_name']
                    break
        elif 'format' in data and 'tags' in data['format'] and 'service_name' in data['format']['tags']:
            service_name = data['format']['tags']['service_name']
            
        if service_name:
            result['service_name'] = self._clean_channel_name(service_name)
        else:
            result['service_name'] = ''

        # 获取分辨率
        if 'streams' in data and data['streams']:
            stream = next((s for s in data['streams'] if s.get('codec_type') == 'video'), data['streams'][0])
            if 'width' in stream and 'height' in stream:
                result['resolution'] = f"{stream['width']}x{stream['height']}"
            elif 'coded_width' in stream and 'coded_height' in stream:
                result['resolution'] = f"{stream['coded_width']}x{stream['coded_height']}"
            else:
                result['resolution'] = ''
                
            if 'codec_name' in stream:
                result['codec'] = stream['codec_name']
            if 'bit_rate' in stream:
                result['bitrate'] = stream['bit_rate']
                
        return result

    def validate_stream(self, url: str, raw_channel_name: str = None, timeout: int = 10) -> Dict:
        """验证视频流有效性
        
        Args:
            url: 要检测的流地址
            raw_channel_name: 从URL提取的原始频道名
            timeout: 超时时间(秒)
            
        Returns:
            Dict: 包含检测结果的字典，包含以下字段：
                - url: 原始URL
                - valid: 是否有效
                - latency: 延迟(毫秒)
                - error: 错误信息(如果有)
                - retries: 重试次数
                - service_name: 频道名称(从流中提取)
                - resolution: 分辨率
                - codec: 视频编码
                - bitrate: 比特率
        """
        # 统一结果结构
        result = {
            'url': url,
            'valid': False,
            'latency': None,
            'error': None,
            'retries': 0,
            'service_name': None,
            'resolution': None,
            'codec': None,
            'bitrate': None
        }
            
        try:
            # 执行ffmpeg流验证
            test_result = self._run_ffmpeg_test(url, timeout, max_retries=1)
            
            # 合并结果
            result.update(test_result)
            
            # 如果流有效，使用ffprobe获取详细信息
            if result['valid']:
                probe_result = self._run_ffprobe(url, timeout)
                
                # 优先使用ffprobe获取的service_name
                if probe_result.get('service_name'):
                    result['service_name'] = probe_result['service_name']
                
                # 合并其他详细信息
                result.update({k: v for k, v in probe_result.items() if k not in ['service_name', 'error']})
            
            # 如果没获取到service_name，从URL提取
            if not result.get('service_name'):
                from channel_mappings import extract_channel_name_from_url
                result['service_name'] = extract_channel_name_from_url(url)
                
        except Exception as e:
            result['error'] = str(e)
            self.logger.error(f"验证流 {url} 时出错: {e}")
            
        return result
