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
    # 限制同时运行的ffprobe实例数量，避免资源竞争
    # 根据扫描线程数调整，默认扫描使用5个线程，这里设置为3个并发ffprobe
    _ffprobe_semaphore = threading.Semaphore(3)  # 最多同时运行3个ffprobe
    # 限制同时运行的ffmpeg验证实例数量，避免资源竞争
    _ffmpeg_semaphore = threading.Semaphore(3)  # 最多同时运行3个ffmpeg验证
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
        
        # 2. 尝试从开发环境路径查找 - 项目根目录
        # 获取项目根目录（当前文件向上两级）
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)  # 从services目录到项目根目录
        dev_path = os.path.join(project_root, 'ffmpeg', 'bin', 'ffmpeg.exe')
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

    def _build_ffmpeg_command(self, url: str, duration: float = 3.0) -> list:
        """构建ffmpeg命令"""
        ffmpeg_path = self._get_ffmpeg_path()
        
        # 优化URL
        optimized_url = self._optimize_url_for_network(url)
        
        # 检查是否为4K流（根据URL或频道名判断）
        is_4k_stream = '4k' in url.lower() or '4K' in url or '2160' in url
        
        cmd = [
            ffmpeg_path,
            '-v', 'error',
            '-timeout', '10000000' if is_4k_stream else '5000000',  # 4K流使用10秒超时
            '-t', str(duration),
            '-reconnect', '1',
            '-reconnect_at_eof', '1',
            '-reconnect_streamed', '1',
            '-reconnect_delay_max', '5' if is_4k_stream else '2',  # 4K流使用更长的重连延迟
        ]
        
        # 为4K流添加额外的优化参数
        if is_4k_stream:
            cmd.extend([
                '-analyzeduration', '10000000',  # 增加分析时长
                '-probesize', '10000000',        # 增加探测大小
                '-threads', '2',                 # 使用2个线程
            ])
        
        cmd.extend([
            '-i', optimized_url,
            '-f', 'null',
            '-'
        ])
        
        # 添加headers
        if hasattr(self, 'headers') and self.headers:
            for key, value in self.headers.items():
                if value:
                    cmd.extend(['-headers', f'{key}: {value}'])
        
        return cmd

    def _run_ffmpeg_test(self, url: str, timeout: int, max_retries: int = 0) -> Dict:
        """运行ffmpeg测试流有效性 - 使用信号量限制并发"""
        result = {
            'valid': False,
            'latency': None,
            'error': None,
            'retries': 0
        }
        
        # 使用信号量限制并发ffmpeg验证实例数量
        if not self._ffmpeg_semaphore.acquire(timeout=5):  # 等待最多5秒获取信号量
            result['error'] = "ffmpeg并发限制超时"
            return result
            
        try:
            start_time = time.time()
            
            # 使用正常的拉流时长：3秒
            pull_duration = 3.0
            
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

                # 正常的判断逻辑
                if process.returncode == 0:
                    # ffmpeg成功拉取流
                    result['valid'] = True
                    result['latency'] = int(elapsed * 1000)
                    self.logger.debug(f"ffmpeg验证成功，执行时间: {elapsed:.2f}秒")
                else:
                    # 检查错误输出
                    error_output = stderr.strip() or stdout.strip()
                    
                    if error_output:
                        # 检查是否是真正的致命错误
                        fatal_errors = [
                            'Connection refused',
                            'Connection timed out',
                            'Server returned 404',
                            'Server returned 403',
                            'Server returned 401',
                            'Error opening input',
                            'Connection reset by peer',
                            'Network is unreachable',
                            'No route to host',
                            'Operation timed out',
                            'Invalid data found',
                            'stream ends prematurely',
                            'HTTP error',
                            '403 Forbidden',
                            '404 Not Found',
                            '500 Internal Server Error',
                            '502 Bad Gateway',
                            '503 Service Unavailable',
                            'Unable to open',
                            'No such file or directory',
                            'Permission denied'
                        ]
                        
                        is_fatal = False
                        for fatal in fatal_errors:
                            if fatal.lower() in error_output.lower():
                                is_fatal = True
                                break
                        
                        if is_fatal:
                            result['error'] = error_output[:200]  # 只取前200字符
                            self.logger.debug(f"ffmpeg致命错误: {error_output[:100]}")
                        else:
                            # 非致命错误，可能仍然有效
                            result['valid'] = True
                            result['latency'] = int(elapsed * 1000)
                            result['error'] = f"警告: {error_output[:100]}"
                            self.logger.debug(f"ffmpeg非致命错误但认为有效: {elapsed:.2f}秒")
                    else:
                        # 没有错误输出但返回非零代码，这种情况通常无效
                        result['valid'] = False
                        result['error'] = f"无错误输出但返回代码: {process.returncode}"
                        self.logger.debug(f"ffmpeg无错误输出但返回非零代码: {process.returncode}")
                        
            except subprocess.TimeoutExpired:
                if process:
                    process.kill()
                # 超时意味着流无效
                result['error'] = f"验证超时 ({timeout}秒)"
                # 移除调试日志，整合日志会记录验证失败
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
                
        finally:
            # 释放信号量
            self._ffmpeg_semaphore.release()
            
        return result

    def _run_ffprobe(self, url: str, timeout: int) -> Dict:
        """执行ffprobe命令获取流详细信息 - 简化日志输出"""
        result = {}
        
        # 使用信号量限制并发ffprobe实例数量
        if not self._ffprobe_semaphore.acquire(timeout=5):  # 等待最多5秒获取信号量
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

    def _try_vlc_validation(self, url: str, timeout: int = 10) -> bool:
        """尝试使用VLC验证流有效性 - 真正播放几秒来获取分辨率信息"""
        try:
            import vlc
            import time
            
            # 创建VLC实例
            vlc_args = [
                '--no-xlib', 
                '--quiet',
                '--no-stats',
                '--no-video-title-show',
                '--no-osd',
                '--no-spu',
                '--no-snapshot-preview'
            ]
            instance = vlc.Instance(vlc_args)
            
            # 创建媒体
            media = instance.media_new(url)
            
            # 设置超时和缓存
            media.add_option(f':network-timeout={timeout * 1000}')
            media.add_option(f':file-caching={timeout * 1000}')
            media.add_option(':no-video')  # 不显示视频窗口
            
            # 创建播放器
            player = instance.media_player_new()
            player.set_media(media)
            
            # 开始播放
            player.play()
            
            # 等待VLC开始播放
            start_time = time.time()
            played_time = 0
            has_played = False
            
            while time.time() - start_time < timeout:
                state = player.get_state()
                
                # 检查状态
                if state == vlc.State.Playing:
                    # VLC正在播放，记录播放时间
                    if not has_played:
                        has_played = True
                        play_start_time = time.time()
                    
                    # 如果已经开始播放，检查播放时长
                    if has_played:
                        played_time = time.time() - play_start_time
                        
                        # 至少播放3秒，确保能获取到分辨率信息
                        if played_time >= 3.0:
                            # 停止播放并清理资源
                            player.stop()
                            player.release()
                            instance.release()
                            return True
                    
                    time.sleep(0.5)  # 播放中，等待更长时间
                    
                elif state == vlc.State.Opening:
                    # VLC正在打开，继续等待
                    time.sleep(0.1)
                    
                elif state in [vlc.State.Error, vlc.State.Ended, vlc.State.Stopped, vlc.State.NothingSpecial]:
                    # VLC报告错误或停止，认为流无效
                    player.stop()
                    player.release()
                    instance.release()
                    return False
                else:
                    # 其他状态，继续等待
                    time.sleep(0.1)
            
            # 超时，停止播放并清理资源
            player.stop()
            player.release()
            instance.release()
            
            # 如果已经开始播放但播放时间不足3秒，认为无效
            if has_played and played_time < 3.0:
                self.logger.debug(f"VLC播放时间不足: {played_time:.2f}秒")
                return False
            else:
                # 根本没有开始播放
                return False
            
        except Exception as e:
            self.logger.debug(f"VLC验证异常: {e}")
            return False

    def validate_stream(self, url: str, raw_channel_name: str = None, timeout: int = 10) -> Dict:
        """验证视频流有效性 - ffmpeg+VLC双验证，整合日志输出"""
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
            # 第一步：并行尝试ffmpeg和VLC验证
            ffmpeg_result = self._run_ffmpeg_test(url, timeout, max_retries=0)
            
            # VLC验证（备用验证方法）- 增加超时时间到10秒
            vlc_valid = False
            try:
                vlc_valid = self._try_vlc_validation(url, timeout=10)
            except Exception:
                pass  # VLC验证异常静默处理
            
            # 第二步：判断有效性 - ffmpeg或VLC有一个成功就认为有效
            ffmpeg_valid = ffmpeg_result['valid']
            
            # 整合日志：只在验证失败时记录详细信息
            if ffmpeg_valid or vlc_valid:
                # ffmpeg或VLC验证成功，流有效
                result['valid'] = True
                result['latency'] = ffmpeg_result['latency']
                
                if ffmpeg_result.get('error'):
                    result['error'] = ffmpeg_result['error']
                
                # 只在DEBUG级别记录验证成功
                self.logger.debug(f"验证成功 - URL: {url}, 延迟: {ffmpeg_result['latency']}ms")
                
                # 确保有频道名
                if not result.get('service_name'):
                    from models.channel_mappings import extract_channel_name_from_url
                    result['service_name'] = extract_channel_name_from_url(url)
                    
                return result
            else:
                # ffmpeg和VLC都验证失败，流无效
                # 增加重试机制：如果第一次验证失败（超时或并发限制超时），重试一次
                should_retry = False
                retry_reason = ""
                
                if ffmpeg_result.get('error'):
                    error_msg = ffmpeg_result['error']
                    if '超时' in error_msg or '并发限制超时' in error_msg:
                        should_retry = True
                        retry_reason = "超时" if '超时' in error_msg else "并发限制"
                
                if should_retry:
                    # 只在DEBUG级别记录重试
                    self.logger.debug(f"第一次验证{retry_reason}，重试一次: {url}")
                    # 重试一次，使用更长的超时时间
                    ffmpeg_result = self._run_ffmpeg_test(url, timeout + 5, max_retries=0)
                    ffmpeg_valid = ffmpeg_result['valid']
                    
                    if ffmpeg_valid:
                        result['valid'] = True
                        result['latency'] = ffmpeg_result['latency']
                        result['retries'] = 1
                        # 只在DEBUG级别记录重试成功
                        self.logger.debug(f"重试成功 - URL: {url}, 延迟: {ffmpeg_result['latency']}ms")
                        
                        # 确保有频道名
                        if not result.get('service_name'):
                            from models.channel_mappings import extract_channel_name_from_url
                            result['service_name'] = extract_channel_name_from_url(url)
                            
                        return result
                
                result['valid'] = False
                result['latency'] = ffmpeg_result['latency']
                result['error'] = ffmpeg_result.get('error', 'ffmpeg和VLC验证都失败')
                
                # 只在INFO级别记录验证失败（重要信息）
                self.logger.info(f"验证失败 - URL: {url}, 错误: {result['error']}")
                
                # 无效的流确保有频道名
                if not result.get('service_name'):
                    from models.channel_mappings import extract_channel_name_from_url
                    result['service_name'] = extract_channel_name_from_url(url)
                    
                return result
                
        except Exception as e:
            result['error'] = str(e)
            # 记录严重错误
            self.logger.error(f"验证流 {url} 时发生严重错误: {e}")
            
        return result
