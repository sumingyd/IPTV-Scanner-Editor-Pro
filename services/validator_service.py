import subprocess
import threading
import time
import json
import sys
import os
import urllib.parse
from typing import Dict, Optional
from core.log_manager import LogManager, global_logger
from core.language_manager import LanguageManager

class StreamValidator:
    """使用ffmpeg检测视频流有效性"""
    
    _active_processes = []
    _process_lock = threading.Lock()
    _ffmpeg_path_cache = None
    _ffprobe_path_cache = None
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    timeout = 10  # 默认超时时间
    # 限制同时运行的ffprobe进程数量，避免资源竞争
    _max_concurrent_processes = 5
    _semaphore = threading.Semaphore(_max_concurrent_processes)

    def __init__(self, main_window=None):
        self.logger = global_logger
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
        """终止所有活动的验证进程 - 增强版本"""
        import logging
        logger = logging.getLogger('IPTVScanner')
        
        with cls._process_lock:
            processes_to_terminate = cls._active_processes.copy()
            cls._active_processes = []
            
            terminated_count = 0
            failed_count = 0
            
            for process in processes_to_terminate:
                try:
                    if process.poll() is None:  # 检查进程是否仍在运行
                        # 先尝试优雅终止
                        process.terminate()
                        try:
                            process.wait(timeout=1.0)  # 等待1秒
                            terminated_count += 1
                            # 不再记录DEBUG日志
                        except subprocess.TimeoutExpired:
                            # 如果优雅终止失败，强制终止
                            process.kill()
                            process.wait()
                            terminated_count += 1
                            # 不再记录DEBUG日志
                    else:
                        # 进程已经结束
                        terminated_count += 1
                        # 不再记录DEBUG日志
                except Exception as e:
                    failed_count += 1
                    # 不再记录DEBUG日志
            
            # 不再记录清理完成日志



    def _get_ffprobe_path(self):
        """获取ffprobe路径 - 带缓存版本"""
        if self._ffprobe_path_cache is not None:
            return self._ffprobe_path_cache
            
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
                self._ffprobe_path_cache = exe_path
                return exe_path
        
        # 2. 尝试从开发环境路径查找 - 项目根目录
        # 获取项目根目录（当前文件向上两级）
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)  # 从services目录到项目根目录
        dev_path = os.path.join(project_root, 'ffmpeg', 'bin', 'ffprobe.exe')
        tried_paths.append(f"开发路径: {dev_path}")
        if os.path.exists(dev_path):
            self._ffprobe_path_cache = dev_path
            return dev_path
            
        # 3. 尝试从系统PATH查找
        try:
            from shutil import which
            path = which('ffprobe')
            tried_paths.append(f"系统PATH查找")
            if path:
                self._ffprobe_path_cache = path
                return path
        except ImportError:
            tried_paths.append("无法导入shutil.which")
            self.logger.debug("shutil.which导入失败，使用备用方案")
            
        # 记录所有尝试过的路径
        self.logger.warning(
            "无法找到ffprobe，尝试了以下路径:\n" + 
            "\n".join(tried_paths) +
            "\n将尝试直接调用'ffprobe'"
        )
        self._ffprobe_path_cache = 'ffprobe'  # 缓存结果
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

    def _optimize_url_for_network(self, url: str) -> str:
        """优化URL以提高网络请求效率"""
        try:
            parsed = urllib.parse.urlparse(url)
            
            # 如果是HTTP/HTTPS协议，添加连接优化参数
            if parsed.scheme in ['http', 'https']:
                # 添加连接复用参数 - 移除可能导致问题的参数
                # 让ffmpeg使用默认的网络设置，避免参数冲突
                pass
            
            return url
        except Exception:
            return url



    def _run_ffprobe_test(self, url: str, timeout: int) -> Dict:
        """运行ffprobe测试流有效性 - 快速验证方法"""
        result = {}
        
        try:
            ffprobe_path = self._get_ffprobe_path()
            
            # 构建ffprobe命令 - 增加超时时间
            # 用户手动测试使用5秒超时，但某些URL需要更长时间
            # 使用10秒超时（10000000微秒）
            cmd = [
                ffprobe_path,
                '-v', 'error',
                '-timeout', '10000000',  # 10秒超时（增加超时时间）
                '-probesize', '10000000',
                '-show_format',
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
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0,
                shell=False,
                env=env,
                cwd=os.path.dirname(self._get_ffprobe_path())
            )
            
            # 跟踪活动进程
            with self._process_lock:
                self._active_processes.append(process)
            self._current_process = process
            
            try:
                # 增加超时时间：使用timeout + 2秒，确保比ffprobe的-timeout更长
                # ffprobe的-timeout是5000000微秒（5秒），所以Python超时至少7秒
                python_timeout = max(timeout, 7)  # 至少7秒
                stdout_bytes, stderr_bytes = process.communicate(timeout=python_timeout)
                stdout = stdout_bytes.decode('utf-8', errors='replace') if stdout_bytes else ''
                stderr = stderr_bytes.decode('utf-8', errors='replace') if stderr_bytes else ''

                # 检查是否为可接受的错误
                error_output = stderr.strip() or stdout.strip()
                return_code = process.returncode
                
                # 定义可接受的错误模式
                # 注意：'Stream ends prematurely' 不应该视为可接受，因为用户测试无法播放
                acceptable_errors = [
                    'Error number -138 occurred',
                    'non-existing PPS',
                    'decode_slice_header error',
                    'no frame',
                    'sps_id out of range'
                ]
                
                is_acceptable_error = False
                if error_output:
                    for acceptable_error in acceptable_errors:
                        if acceptable_error in error_output:
                            is_acceptable_error = True
                            break
                
                if return_code == 0 or is_acceptable_error:
                    # ffprobe成功或可接受错误，流有效
                    # 不再同步获取详细信息，验证成功后立即返回
                    # 详细信息将在后台异步获取（由ScannerController处理）
                    
                    # 如果是可接受错误，记录警告但不标记为错误
                    if is_acceptable_error:
                        result['warning'] = error_output[:200]  # 只取前200字符
                else:
                    # ffprobe失败，记录错误信息
                    result['error'] = error_output[:200] if error_output else f"返回代码: {return_code}"
                    
            except subprocess.TimeoutExpired:
                if process:
                    process.kill()
                result['error'] = f"ffprobe超时 ({timeout}秒)"
            except Exception as e:
                result['error'] = str(e)
            finally:
                # 清理已完成进程
                if process:
                    with self._process_lock:
                        if process in self._active_processes:
                            self._active_processes.remove(process)
        except Exception as e:
            result['error'] = str(e)
                
        return result

    def _run_ffprobe(self, url: str, timeout: int) -> Dict:
        """执行ffprobe命令获取流详细信息 - 简化日志输出"""
        result = {}
        
        try:
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
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0,
                shell=True if sys.platform == 'win32' else False,  # Windows上使用shell=True
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
                        if stdout.strip():  # 确保stdout不为空
                            data = json.loads(stdout)
                            result.update(self._parse_ffprobe_output(data))
                        else:
                            result['error'] = "ffprobe返回空输出"
                    except json.JSONDecodeError as e:
                        result['error'] = f"JSON解析失败"
                    except Exception as e:
                        result['error'] = str(e)
                else:
                    result['error'] = stderr.strip() or f"返回代码: {process.returncode}"
                    
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
        except Exception as e:
            result['error'] = str(e)
                
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
        """验证视频流有效性 - 只使用ffprobe验证"""
        # 统一结果结构
        result = {
            'url': url,
            'valid': False,
            'latency': None,
            'error': None,
            'warning': None,
            'retries': 0,
            'service_name': None,
            'resolution': None,
            'codec': None,
            'bitrate': None
        }
            
        try:
            # 只使用ffprobe验证
            start_time = time.time()
            ffprobe_result = self._run_ffprobe_test(url, timeout)
            ffprobe_latency = int((time.time() - start_time) * 1000)
            
            # ffprobe验证成功条件：没有错误信息（警告可以接受）
            has_error = 'error' in ffprobe_result and ffprobe_result['error']
            has_warning = 'warning' in ffprobe_result and ffprobe_result['warning']
            
            if not has_error:
                # ffprobe验证成功（可能有警告），流有效
                result['valid'] = True
                result['latency'] = ffprobe_latency
                
                # 从ffprobe结果中提取信息
                if ffprobe_result.get('service_name'):
                    result['service_name'] = ffprobe_result['service_name']
                if ffprobe_result.get('resolution'):
                    result['resolution'] = ffprobe_result['resolution']
                if ffprobe_result.get('codec'):
                    result['codec'] = ffprobe_result['codec']
                if ffprobe_result.get('bitrate'):
                    result['bitrate'] = ffprobe_result['bitrate']
                
                # 如果有警告，记录警告信息
                if has_warning:
                    result['warning'] = ffprobe_result['warning']
                    # 不再记录警告日志，避免控制台输出
                # 验证成功不记录日志
            else:
                # ffprobe验证失败，流无效
                result['valid'] = False
                result['latency'] = ffprobe_latency
                result['error'] = ffprobe_result.get('error', 'ffprobe验证失败')
                # 不再记录错误日志，避免控制台输出
            
            # 确保有频道名
            if not result.get('service_name'):
                from models.channel_mappings import extract_channel_name_from_url
                result['service_name'] = extract_channel_name_from_url(url)
                
        except Exception as e:
            result['error'] = str(e)
            # 记录严重错误
            self.logger.error(f"验证流 {url} 时发生严重错误: {e}")
            
        return result
