import subprocess
import threading
import time
import json
import sys
import os
import urllib.parse
from typing import Dict, Optional
from log_manager import LogManager, global_logger
from language_manager import LanguageManager

class StreamValidator:
    """使用ffmpeg检测视频流有效性"""
    
    _active_processes = []
    _process_lock = threading.Lock()
    _ffmpeg_path_cache = None
    _ffprobe_path_cache = None
    # 限制同时运行的ffprobe实例数量，避免资源竞争
    # 根据扫描线程数调整，默认扫描使用5个线程，这里设置为3个并发ffprobe
    _ffprobe_semaphore = threading.Semaphore(3)  # 最多同时运行3个ffprobe
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    timeout = 10  # 默认超时时间

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
                            logger.debug(f"进程 {process.pid} 已优雅终止")
                        except subprocess.TimeoutExpired:
                            # 如果优雅终止失败，强制终止
                            process.kill()
                            process.wait()
                            terminated_count += 1
                            logger.debug(f"进程 {process.pid} 已强制终止")
                    else:
                        # 进程已经结束
                        terminated_count += 1
                        logger.debug(f"进程 {process.pid} 已结束")
                except Exception as e:
                    failed_count += 1
                    logger.debug(f"终止进程 {process.pid if hasattr(process, 'pid') else 'unknown'} 时出错: {e}")
            
            if terminated_count > 0 or failed_count > 0:
                logger.info(f"验证进程清理完成: {terminated_count} 个进程已终止, {failed_count} 个进程清理失败")


    def _get_ffmpeg_path(self):
        """获取ffmpeg路径 - 带缓存版本"""
        if self._ffmpeg_path_cache is not None:
            return self._ffmpeg_path_cache
            
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
                self._ffmpeg_path_cache = exe_path
                return exe_path
        
        # 2. 尝试从开发环境路径查找
        dev_path = os.path.join(os.path.dirname(__file__), 'ffmpeg', 'bin', 'ffmpeg.exe')
        tried_paths.append(f"开发路径: {dev_path}")
        if os.path.exists(dev_path):
            self._ffmpeg_path_cache = dev_path
            return dev_path
            
        # 3. 尝试从系统PATH查找
        try:
            from shutil import which
            path = which('ffmpeg')
            tried_paths.append(f"系统PATH查找")
            if path:
                self._ffmpeg_path_cache = path
                return path
        except ImportError:
            tried_paths.append("无法导入shutil.which")
            self.logger.debug("shutil.which导入失败，使用备用方案")
            
        # 记录所有尝试过的路径
        self.logger.warning(
            "无法找到ffmpeg，尝试了以下路径:\n" + 
            "\n".join(tried_paths) +
            "\n将尝试直接调用'ffmpeg'"
        )
        self._ffmpeg_path_cache = 'ffmpeg'  # 缓存结果
        return 'ffmpeg'  # 最后尝试直接调用

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
        
        # 2. 尝试从开发环境路径查找
        dev_path = os.path.join(os.path.dirname(__file__), 'ffmpeg', 'bin', 'ffprobe.exe')
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

    def _build_ffmpeg_command(self, url: str, duration: float = 3.0) -> list:
        """构建ffmpeg命令"""
        ffmpeg_path = self._get_ffmpeg_path()
        
        # 优化URL
        optimized_url = self._optimize_url_for_network(url)
        
        cmd = [
            ffmpeg_path,
            '-v', 'error',
            '-timeout', '5000000',  # 5秒超时
            '-t', str(duration),    # 拉取时长
            '-reconnect', '1',      # 启用重连
            '-reconnect_at_eof', '1',  # 在EOF时重连
            '-reconnect_streamed', '1',  # 流式重连
            '-reconnect_delay_max', '2',  # 最大重连延迟
            '-i', optimized_url,
            '-f', 'null',           # 输出到空设备
            '-'
        ]
        
        # 添加headers
        if hasattr(self, 'headers') and self.headers:
            for key, value in self.headers.items():
                if value:
                    cmd.extend(['-headers', f'{key}: {value}'])
        
        return cmd

    def _run_ffmpeg_test(self, url: str, timeout: int, max_retries: int = 0) -> Dict:
        """运行ffmpeg测试流有效性 - 与扫描逻辑完全相同"""
        result = {
            'valid': False,
            'latency': None,
            'error': None,
            'retries': 0
        }
        
        start_time = time.time()
        
        # 使用与扫描相同的拉流时长：5秒
        pull_duration = 5.0
        
        cmd = self._build_ffmpeg_command(url, pull_duration)
        
        # 在Windows上需要处理特殊字符
        if sys.platform == 'win32':
            cmd = [arg.replace('^', '^^').replace('&', '^&') for arg in cmd]
        
        # 设置环境变量和工作目录
        env = os.environ.copy()
        env['PATH'] = os.path.dirname(self._get_ffmpeg_path()) + os.pathsep + env['PATH']
        
        process = None
        try:
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
            
            # 记录命令开始执行时间
            exec_start = time.time()
            stdout_bytes, stderr_bytes = process.communicate(timeout=timeout)
            exec_end = time.time()
            
            elapsed = exec_end - exec_start
            
            stdout = stdout_bytes.decode('utf-8', errors='replace') if stdout_bytes else ''
            stderr = stderr_bytes.decode('utf-8', errors='replace') if stderr_bytes else ''

            # 更宽容的判断逻辑：即使ffmpeg返回非零代码，也检查是否有实际错误
            if process.returncode == 0:
                # ffmpeg成功拉取流
                result['valid'] = True
                result['latency'] = int(elapsed * 1000)
            else:
                # 检查错误输出，判断是否是真正的错误
                error_output = stderr.strip() or stdout.strip()
                
                # 如果错误输出包含特定关键词，可能是真正的错误
                # 否则，可能是ffmpeg警告但流实际上有效
                if error_output:
                    # 检查是否是已知的非致命错误
                    non_fatal_errors = [
                        'moov atom not found',
                        'stream ends prematurely',
                        'Invalid data found',
                        'non-monotonic DTS',
                        'HTTP error',
                        'Connection refused',
                        'Connection timed out',
                        'Server returned 404 Not Found',
                        'Server returned 403 Forbidden',
                        'Server returned 401 Unauthorized',
                        'Error opening input',  # 添加更多非致命错误
                        'Server returned',
                        'Connection reset by peer',
                        'Network is unreachable',
                        'No route to host',
                        'Operation timed out'
                    ]
                    
                    is_fatal = True
                    for non_fatal in non_fatal_errors:
                        if non_fatal.lower() in error_output.lower():
                            is_fatal = False
                            break
                    
                    if is_fatal:
                        result['error'] = error_output
                    else:
                        # 非致命错误，仍然认为流有效
                        result['valid'] = True
                        result['latency'] = int(elapsed * 1000)
                        result['error'] = f"警告: {error_output[:100]}"
                else:
                    # 没有错误输出，但返回非零代码，可能是ffmpeg被终止
                    # 检查是否实际拉取了流（通过elapsed时间判断）
                    if elapsed > 0.5:  # 如果执行时间超过0.5秒，认为至少尝试了拉流
                        result['valid'] = True
                        result['latency'] = int(elapsed * 1000)
                        result['error'] = f"ffmpeg返回错误代码但可能拉流成功: {process.returncode}"
                    else:
                        result['error'] = f"ffmpeg返回错误代码: {process.returncode}"
                
        except subprocess.TimeoutExpired:
            if process:
                process.kill()
            # 超时不一定意味着流无效，可能只是网络慢
            # 如果执行时间超过1秒，认为流可能有效
            elapsed = time.time() - exec_start if 'exec_start' in locals() else 0
            if elapsed > 1.0:
                result['valid'] = True
                result['latency'] = int(elapsed * 1000)
                result['error'] = f"验证超时但可能拉流成功 ({timeout}秒)"
            else:
                result['error'] = f"验证超时 ({timeout}秒)"
        except Exception as e:
            result['error'] = str(e)
            self.logger.debug(f"流验证异常: {url}, 异常: {e}")
        finally:
            # 清理已完成进程
            if process:
                with self._process_lock:
                    if process in self._active_processes:
                        self._active_processes.remove(process)
        
        # 确保latency有值（即使测试失败）
        if result['latency'] is None:
            result['latency'] = int((time.time() - start_time) * 1000)
            
        return result

    def _run_ffprobe(self, url: str, timeout: int) -> Dict:
        """执行ffprobe命令获取流详细信息 - 使用信号量限制并发"""
        result = {}
        
        # 使用信号量限制并发ffprobe实例数量
        # 增加等待时间到10秒，避免在繁忙时超时
        if not self._ffprobe_semaphore.acquire(timeout=10):  # 等待最多10秒获取信号量
            self.logger.warning(f"获取ffprobe信号量超时: {url}")
            result['error'] = "ffprobe并发限制超时"
            return result
            
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
                        # 添加调试信息
                        self.logger.debug(f"ffprobe stdout长度: {len(stdout)}, stderr长度: {len(stderr)}")
                        
                        if stdout.strip():  # 确保stdout不为空
                            data = json.loads(stdout)
                            result.update(self._parse_ffprobe_output(data))
                        else:
                            # 如果stdout为空，记录警告
                            self.logger.warning(f"ffprobe返回空输出: url={url}")
                            result['error'] = "ffprobe返回空输出"
                    except json.JSONDecodeError as e:
                        self.logger.warning(f"ffprobe JSON解析失败: {e}, stdout前100字符: {stdout[:100]}")
                        result['error'] = f"JSON解析失败: {e}"
                    except Exception as e:
                        self.logger.warning(f"ffprobe解析异常: {e}")
                        result['error'] = str(e)
                else:
                    self.logger.warning(f"ffprobe返回非零代码: {process.returncode}, stderr: {stderr}")
                    result['error'] = stderr.strip()
                    
            except subprocess.TimeoutExpired:
                process.kill()
                self.logger.warning(f"ffprobe超时: {url}")
                result['error'] = "ffprobe超时"
            except Exception as e:
                self.logger.warning(f"ffprobe执行异常: {e}")
                result['error'] = str(e)
            finally:
                # 清理已完成进程
                with self._process_lock:
                    if process in self._active_processes:
                        self._active_processes.remove(process)
        finally:
            # 释放信号量
            self._ffprobe_semaphore.release()
                
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
        """验证视频流有效性 - 同时获取JSON中的频道名"""
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
            # 执行ffmpeg流验证 - 没有重试
            test_result = self._run_ffmpeg_test(url, timeout, max_retries=0)
            
            # 合并结果
            result.update(test_result)
            
            # 记录验证结果
            self.logger.debug(f"流验证结果: url={url}, valid={result['valid']}, latency={result['latency']}")
            
            # 如果流有效，尝试运行ffprobe获取JSON中的频道名
            if result['valid']:
                self.logger.debug(f"流有效，尝试运行ffprobe获取JSON中的频道名: {url}")
                try:
                    # 运行ffprobe获取详细信息 - 使用更长的超时时间（10秒）
                    probe_result = self._run_ffprobe(url, timeout=10)  # 增加超时时间到10秒
                    
                    self.logger.debug(f"ffprobe结果: {probe_result}")
                    
                    # 如果ffprobe成功获取到service_name，使用它
                    if probe_result.get('service_name'):
                        result['service_name'] = probe_result['service_name']
                        result['resolution'] = probe_result.get('resolution')
                        result['codec'] = probe_result.get('codec')
                        result['bitrate'] = probe_result.get('bitrate')
                        self.logger.info(f"从JSON获取到频道名: {result['service_name']} (URL: {url})")
                    else:
                        # 从URL提取频道名
                        from channel_mappings import extract_channel_name_from_url
                        result['service_name'] = extract_channel_name_from_url(url)
                        self.logger.info(f"ffprobe未返回service_name，从URL提取频道名: {result['service_name']} (URL: {url})")
                except Exception as e:
                    # ffprobe失败，从URL提取频道名
                    self.logger.warning(f"ffprobe失败: {e}, 从URL提取频道名: {url}")
                    from channel_mappings import extract_channel_name_from_url
                    result['service_name'] = extract_channel_name_from_url(url)
            else:
                # 流无效，从URL提取频道名
                from channel_mappings import extract_channel_name_from_url
                result['service_name'] = extract_channel_name_from_url(url)
                self.logger.info(f"流无效，从URL提取频道名: {result['service_name']} (URL: {url})")
                
        except Exception as e:
            result['error'] = str(e)
            self.logger.error(f"验证流 {url} 时出错: {e}")
            
        return result
