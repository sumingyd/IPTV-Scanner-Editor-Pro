import subprocess
import threading
import time
import json
import sys
import os
import urllib.parse
from typing import Dict
from core.log_manager import global_logger
from core.language_manager import LanguageManager


class StreamValidator:
    """使用ffmpeg检测视频流有效性"""

    _active_processes = []
    _process_lock = threading.Lock()
    _ffmpeg_path_cache = None
    _ffprobe_path_cache = None
    headers = {
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/91.0.4472.124 Safari/537.36'
        )
    }
    timeout = None  # 不再使用硬编码默认值，从调用者传入
    # 限制同时运行的ffprobe进程数量，避免资源竞争
    _max_concurrent_processes = None  # 不再硬编码，从调用者传入
    _semaphore = None

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
                        except subprocess.TimeoutExpired:
                            # 如果优雅终止失败，强制终止
                            process.kill()
                            process.wait()
                            terminated_count += 1
                    else:
                        # 进程已经结束
                        terminated_count += 1
                except Exception:
                    failed_count += 1

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
            tried_paths.append("系统PATH查找")
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

    def _quick_tcp_check(self, url: str, timeout: int = 1) -> bool:
        """TCP连接快速检查 - 先检查基本连通性"""
        import socket
        from urllib.parse import urlparse

        try:
            parsed = urlparse(url)
            host = parsed.hostname
            if not host:
                return False

            # 对于UDP/RTP协议，不进行TCP检查，直接返回True
            # 因为这些是面向无连接的协议，TCP检查没有意义
            scheme = parsed.scheme.lower()
            if scheme in ['udp', 'rtp', 'rtsp']:
                return True

            # 获取端口
            port = parsed.port
            if not port:
                # 根据协议使用默认端口
                if scheme == 'http':
                    port = 80
                elif scheme == 'https':
                    port = 443
                else:
                    port = 80  # 其他协议默认80

            # 解析主机名（支持域名和IP）
            try:
                # 如果是IP地址，直接使用
                socket.inet_aton(host)
                ip = host
            except socket.error:
                # 如果是域名，解析为IP
                ip = socket.gethostbyname(host)

            # 尝试TCP连接
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((ip, port))
            sock.close()

            return result == 0  # 0表示连接成功
        except Exception:
            return False

    def _run_ffprobe_test(self, url: str, timeout: int) -> Dict:
        """运行ffprobe测试流有效性 - 优化版本，记录错误类型"""
        result = {}

        try:
            # 1. 先进行快速TCP检查（1秒超时）
            tcp_timeout = min(1, timeout // 3)  # 使用1秒或timeout的1/3
            if not self._quick_tcp_check(url, tcp_timeout):
                result['error'] = "TCP连接失败"
                result['error_type'] = 'tcp_failed'  # 记录错误类型
                return result

            # 2. 确保信号量已初始化
            if self._semaphore is None:
                default_max_processes = 5
                self._max_concurrent_processes = default_max_processes
                self._semaphore = threading.Semaphore(default_max_processes)

            # 3. 获取信号量，限制并发进程数
            with self._semaphore:
                ffprobe_path = self._get_ffprobe_path()

                # 构建优化的ffprobe命令
                # 使用更小的探测大小和更合适的参数
                cmd = [
                    ffprobe_path,
                    '-v', 'error',
                    '-timeout', f'{timeout * 1000000}',  # 使用传入的timeout（秒转微秒）
                    '-probesize', '500000',  # 减少到500KB（原10MB）
                    '-analyzeduration', '1000000',  # 分析时长1秒
                    '-show_entries', 'format=duration:stream=codec_type',  # 只获取必要信息
                    '-of', 'json',  # JSON格式输出
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
                # 使用传入的timeout作为Python超时
                python_timeout = timeout
                stdout_bytes, stderr_bytes = process.communicate(timeout=python_timeout)
                stdout = stdout_bytes.decode('utf-8', errors='replace') if stdout_bytes else ''
                stderr = stderr_bytes.decode('utf-8', errors='replace') if stderr_bytes else ''

                # 检查输出
                error_output = stderr.strip() or stdout.strip()
                return_code = process.returncode

                # 严格判断：只有返回码为0才认为是有效流
                # 移除"可接受错误"逻辑，避免错判
                if return_code == 0:
                    # 尝试解析JSON输出，验证是否有有效数据
                    try:
                        if stdout.strip():
                            data = json.loads(stdout)
                            # 检查是否有有效的流信息
                            has_video = False
                            if 'streams' in data:
                                for stream in data['streams']:
                                    if stream.get('codec_type') == 'video':
                                        has_video = True
                                        break

                            if has_video or 'format' in data:
                                # 有视频流或格式信息，认为是有效流
                                pass
                            else:
                                result['error'] = "未检测到视频流"
                        else:
                            result['error'] = "ffprobe返回空输出"
                    except json.JSONDecodeError:
                        # 即使JSON解析失败，只要ffprobe返回0，也认为是有效
                        # 有些流可能返回非JSON格式但仍然是有效的
                        pass
                    except Exception as e:
                        result['error'] = f"解析输出失败: {str(e)}"
                else:
                    # ffprobe失败，记录错误信息
                    result['error'] = error_output[:200] if error_output else f"返回代码: {return_code}"

                    # 根据错误信息判断错误类型
                    error_lower = error_output.lower() if error_output else ""
                    if "timeout" in error_lower or "超时" in error_lower:
                        result['error_type'] = 'timeout'
                    elif "connection" in error_lower or "连接" in error_lower:
                        result['error_type'] = 'connection_failed'
                    elif "not found" in error_lower or "404" in error_lower:
                        result['error_type'] = 'not_found'
                    elif "permission" in error_lower or "权限" in error_lower:
                        result['error_type'] = 'permission_denied'
                    else:
                        result['error_type'] = 'ffprobe_error'

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
                    except json.JSONDecodeError:
                        result['error'] = "JSON解析失败"
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
                # 传递错误类型
                if 'error_type' in ffprobe_result:
                    result['error_type'] = ffprobe_result['error_type']
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
