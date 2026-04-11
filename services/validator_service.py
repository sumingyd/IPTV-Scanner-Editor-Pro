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
from services.ffprobe_service import get_ffprobe_path as _get_ffprobe_path_global


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
        result = _get_ffprobe_path_global()
        self._ffprobe_path_cache = result
        return result

    def _is_multicast_url(self, url: str) -> bool:
        url_lower = url.lower()
        if url_lower.startswith(('rtp://', 'udp://')):
            return True
        if '/rtp/' in url_lower or '/udp/' in url_lower:
            return True
        if url_lower.startswith('rtsp://'):
            try:
                from urllib.parse import urlparse
                parsed = urlparse(url)
                host = parsed.hostname or ''
                import socket
                try:
                    socket.inet_aton(host)
                    first_octet = int(host.split('.')[0])
                    if 224 <= first_octet <= 239:
                        return True
                except socket.error:
                    pass
            except Exception:
                pass
        return False

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
            if scheme in ['udp', 'rtp']:
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
            # 设置TCP_NODELAY，减少延迟
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            result = sock.connect_ex((ip, port))
            sock.close()

            return result == 0  # 0表示连接成功
        except socket.gaierror:
            # 域名解析失败
            return False
        except socket.timeout:
            # 连接超时
            return False
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
                default_max_processes = 8  # 增加并发数
                self._max_concurrent_processes = default_max_processes
                self._semaphore = threading.Semaphore(default_max_processes)

            # 3. 获取信号量，限制并发进程数
            with self._semaphore:
                ffprobe_path = self._get_ffprobe_path()

                is_multicast = self._is_multicast_url(url)
                is_rtsp = url.lower().startswith('rtsp://')

                cmd = [
                    ffprobe_path,
                    '-hide_banner',
                    '-v', 'error',
                    '-timeout', f'{timeout * 1000000}',
                    '-probesize', '100000',
                    '-analyzeduration', '300000',
                    '-show_entries', 'stream=codec_type',
                    '-of', 'json',
                ]

                if is_rtsp:
                    if is_multicast:
                        cmd.extend([
                            '-rtsp_transport', 'udp',
                            '-max_delay', '5000000',
                        ])
                    else:
                        cmd.extend([
                            '-rtsp_transport', 'tcp',
                        ])

                if not is_rtsp:
                    cmd.extend([
                        '-reconnect', '1',
                        '-reconnect_at_eof', '1',
                        '-reconnect_streamed', '1',
                        '-reconnect_delay_max', '3',
                    ])

                cmd.append(url)

                env = os.environ.copy()
                env['PATH'] = os.path.dirname(self._get_ffprobe_path()) + os.pathsep + env['PATH']
                # 添加网络相关环境变量
                env['FFREPORT'] = ''  # 禁用ffmpeg报告

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
                error_output = stderr.strip()
                return_code = process.returncode

                # 对于所有类型的URL使用统一的严格验证标准
                # 返回码为0表示ffprobe执行成功
                if return_code != 0:
                    result['error'] = error_output[:200] if error_output else f"返回代码: {return_code}"

                # 对于所有URL，尝试解析JSON输出（即使stderr有警告信息）
                if not result.get('error'):
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

                            # 对于所有URL，都需要有视频流或格式信息
                            if not has_video and 'format' not in data:
                                result['error'] = "未检测到视频流或格式信息"
                        else:
                            # 对于所有URL，返回空输出认为是无效
                            result['error'] = "ffprobe返回空输出"
                    except json.JSONDecodeError:
                        # 对于所有URL，JSON解析失败认为是无效
                        result['error'] = "ffprobe返回无效的JSON格式"
                    except Exception as e:
                        # 对于所有URL，解析错误认为是无效
                        result['error'] = f"解析输出失败: {str(e)}"

                # 根据错误信息判断错误类型
                if result.get('error'):
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
                result['error_type'] = 'timeout'
            except Exception as e:
                result['error'] = str(e)
                result['error_type'] = 'unknown_error'
            finally:
                # 清理已完成进程
                if process:
                    with self._process_lock:
                        if process in self._active_processes:
                            self._active_processes.remove(process)
        except Exception as e:
            result['error'] = str(e)
            result['error_type'] = 'unknown_error'

        return result

    def validate_stream(self, url: str, raw_channel_name: str = None, timeout: int = 5) -> Dict:
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
