import asyncio
import subprocess
import json
import sys
import psutil
import time
from pathlib import Path
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor
from PyQt6 import QtWidgets
from PyQt6.QtCore import QObject, pyqtSignal
from playlist_io import PlaylistHandler
from utils import setup_logger
from qasync import asyncSlot
from utils import parse_ip_range

logger = setup_logger('Scanner')

class StreamScanner(QObject):
    progress_updated = pyqtSignal(int, str)    # 进度百分比, 状态信息
    scan_finished = pyqtSignal(dict)           # 扫描结果字典
    channel_found = pyqtSignal(dict)           # 单个有效频道信息
    error_occurred = pyqtSignal(str)           # 错误信息
    ffprobe_missing = pyqtSignal()             # 新增：ffprobe缺失信号
    validation_status = pyqtSignal(str)        # 新增：验证状态信息

    def __init__(self):
        """流媒体扫描器
        功能:
            1. 初始化扫描参数
            2. 加载播放列表处理器
            3. 初始化扫描状态
        """
        super().__init__()
        self._is_scanning = False
        self._timeout = 5
        self._thread_count = 10
        self._scan_lock = asyncio.Lock()
        self.playlist = PlaylistHandler()
        self._start_time = 0
        self._scanned_count = 0
        self._executor = None
        self._ffprobe_checked = False  # 是否已检查ffprobe
        self._ffprobe_available = False  # ffprobe是否可用
        self._user_agent = None  # 自定义User-Agent
        self._referer = None  # 自定义Referer
        self._tasks = []  # 跟踪所有扫描任务
        self._active_processes = set()  # 跟踪所有活动的ffprobe进程

    def set_timeout(self, timeout: int) -> None:
        """设置超时时间（单位：秒）"""
        self._timeout = timeout

    def set_user_agent(self, user_agent: str) -> None:
        """设置自定义User-Agent"""
        self._user_agent = user_agent

    def set_referer(self, referer: str) -> None:
        """设置自定义Referer"""
        self._referer = referer

    def set_thread_count(self, thread_count: int) -> None:
        """设置线程数"""
        self._thread_count = thread_count

    def get_elapsed_time(self) -> float:
        """获取扫描耗时(秒)"""
        if not hasattr(self, '_start_time'):
            return 0.0
        return asyncio.get_event_loop().time() - self._start_time

    def get_scanned_count(self) -> int:
        """获取已扫描IP数量"""
        return self._scanned_count

    @asyncSlot()
    async def toggle_scan(self, ip_pattern: str) -> None:
        """切换扫描状态
        参数:
            ip_pattern: IP地址模式字符串
        功能:
            1. 如果正在扫描则停止扫描
            2. 如果未扫描则开始扫描
        """
        if self._is_scanning:
            self.stop_scan()
            self.progress_updated.emit(0, "已停止")
            return

        async with self._scan_lock:
            if self._is_scanning:
                self.error_occurred.emit("已有扫描任务正在进行")
                return

            self._is_scanning = True
            self._start_time = asyncio.get_event_loop().time()
            self._scanned_count = 0  # 重置计数器
            try:
                await self._scan_task(ip_pattern)
            except Exception as e:
                logger.error(f"扫描任务异常: {str(e)}")
                self.error_occurred.emit(f"扫描错误: {str(e)}")
            finally:
                self._is_scanning = False

    async def _scan_task(self, ip_pattern: str) -> None:
        """执行扫描的核心任务"""
        try:
            try:
                urls = parse_ip_range(ip_pattern)
                logger.debug(f"解析后的URL列表: {urls[:5]}... (共{len(urls)}个)")
                if not urls:
                    logger.error(f"未生成任何扫描地址: {ip_pattern}")
                    self.error_occurred.emit("未生成任何扫描地址，请检查输入格式")
                    return
                
                # 验证生成的URL格式
                invalid_urls = [url for url in urls if not url.startswith(('http://', 'https://'))]
                if invalid_urls:
                    logger.error(f"生成无效URL: {invalid_urls[:3]}... (共{len(invalid_urls)}个)")
                    self.error_occurred.emit(f"生成{len(invalid_urls)}个无效URL，请检查输入格式")
                    return
                    
            except ValueError as e:
                logger.error(f"地址解析失败: {ip_pattern} - {str(e)}")
                self.error_occurred.emit(f"地址解析错误: {str(e)}")
                return
            except Exception as e:
                logger.error(f"地址解析异常: {ip_pattern} - {str(e)}")
                self.error_occurred.emit(f"地址解析异常: {str(e)}")
                return
                
            total = len(urls)
            valid_channels = []
            invalid_count = 0
            
            # 创建线程池，大小与并发数一致
            self._executor = ThreadPoolExecutor(max_workers=self._thread_count)
            
            async def probe_url(url: str) -> tuple[str, Optional[Dict]]:
                try:
                    # 增加扫描状态检查
                    if not self._is_scanning:
                        raise asyncio.CancelledError("扫描已停止")
                    result = await self._probe_stream(url)
                    return (url, result)
                except asyncio.CancelledError:
                    logger.debug(f"探测任务被正常取消: {url}")
                    raise
                except Exception as e:
                    logger.error(f"探测URL出错: {url} - {str(e)}")
                    return (url, None)
                finally:
                    try:
                        await asyncio.get_event_loop().run_in_executor(None, QtWidgets.QApplication.processEvents)
                    except:
                        pass
            
            # 创建所有探测任务并保存到_tasks列表
            self._tasks = []
            for url in urls:
                if not self._is_scanning:
                    break
                task = asyncio.create_task(probe_url(url), name=f"probe_{url}")
                self._tasks.append(task)
            
            # 使用asyncio.as_completed处理结果
            for future in asyncio.as_completed(self._tasks):
                try:
                    # 增加扫描状态检查
                    if not self._is_scanning:
                        logger.debug("扫描已停止，取消剩余任务")
                        break
                        
                    result = await future
                    url, result = result if  isinstance(result, tuple) else (None, result)
                    
                    if url is None:
                        logger.debug("跳过无效URL")
                        continue
                        
                    self._scanned_count += 1
                    
                    if result is not None and result.get('valid', True):
                        channel_name = f"频道 {len(valid_channels) + 1}"
                        channel_info = {
                            'name': channel_name,
                            'url': url,
                            'width': result['width'],
                            'height': result['height'],
                            'codec': result['codec'],
                            'resolution': f"{result['width']}x{result['height']}"
                        }
                        logger.info(f"发现有效频道: {channel_name} - URL: {url}")
                        valid_channels.append(channel_info)
                        self.channel_found.emit(channel_info)
                    else:
                        invalid_count += 1
                        logger.info(f"频道无效: {url}")
                    
                    # 更新进度
                    progress = int((self._scanned_count / total) * 100)
                    elapsed = self.get_elapsed_time()
                    scan_speed = self._scanned_count / elapsed if elapsed > 0 else 0
                    remaining = (total - self._scanned_count) / scan_speed if scan_speed > 0 else 0
                    
                    current_ip = url.split('/')[-1].split(':')[0] if url else ""
                    status_parts = [
                        f"进度: {self._scanned_count}/{total} ({progress}%)", 
                        f"速度: {scan_speed:.1f} IP/s",
                        f"剩余: {int(remaining)}s",
                        f"当前: {current_ip}",
                        f"有效: {len(valid_channels)}",
                        f"无效: {invalid_count}"
                    ]
                    status_msg = " | ".join(filter(None, status_parts))
                    self.progress_updated.emit(progress, status_msg)
                    
                except Exception:
                    pass
            
            # 等待所有任务完成
            await asyncio.gather(*self._tasks, return_exceptions=True)
            
            if self._is_scanning:
                elapsed = asyncio.get_event_loop().time() - self._start_time
                # 将无效数量附加到频道列表
                for chan in valid_channels:
                    chan['_invalid_count'] = invalid_count
                self.scan_finished.emit({
                    'channels': valid_channels,
                    'total': len(urls),
                    'invalid': invalid_count,
                    'elapsed': elapsed
                })
                self.progress_updated.emit(100, f"扫描完成 - 总数: {len(urls)} | 有效: {len(valid_channels)} | 无效: {invalid_count} | 耗时: {elapsed:.1f}秒")
                
        except Exception as e:
            self.error_occurred.emit(f"扫描错误: {str(e)}")
            raise
        finally:
            self._is_scanning = False

    async def _probe_stream(self, url: str) -> Optional[Dict]:
        """探测单个流媒体信息（增强版）"""
        proc = None
        try:
            logger.info(f"开始验证频道: {url}")
            
            # 首次使用时检查ffprobe可用性
            if not self._ffprobe_checked:
                logger.info("首次使用，检查ffprobe可用性")
                await self._check_ffprobe()
                self._ffprobe_checked = True
                logger.info(f"ffprobe可用状态: {self._ffprobe_available}")

            # 检查是否已取消
            if not self._is_scanning:
                logger.info("验证任务被取消(扫描状态检查)")
                raise asyncio.CancelledError("扫描已停止")

            # 再次检查扫描状态
            if not self._is_scanning:
                logger.info("验证任务被取消(二次状态检查)")
                raise asyncio.CancelledError("扫描已停止")

            # 确保线程池已初始化
            if not self._executor or self._executor._shutdown:
                logger.info("重新初始化线程池")
                self._executor = ThreadPoolExecutor(max_workers=self._thread_count)

            loop = asyncio.get_running_loop()
            future = loop.run_in_executor(
                self._executor,
                self._run_ffprobe, 
                url
            )
            logger.info(f"已提交验证任务: {url}")
            
            # 添加取消回调
            def _cancel_probe(_):
                if proc and proc.poll() is None:
                    logger.info(f"取消验证任务并终止进程: {url}")
                    proc.kill()
            
            future.add_done_callback(_cancel_probe)
            logger.info(f"已添加取消回调: {url}")
            
            try:
                result = await future
                logger.info(f"验证任务完成: {url} - 结果: {result is not None}")
                if result is None:
                    logger.warning(f"频道验证失败: {url}")
                else:
                    logger.info(f"频道验证成功: {url} - 分辨率: {result.get('width', 0)}x{result.get('height', 0)}")
                return result
            except asyncio.CancelledError:
                logger.info(f"验证任务被取消: {url}")
                if proc and proc.poll() is None:
                    proc.kill()
                return None
            except Exception as e:
                logger.error(f"验证任务异常: {url} - {str(e)}")
                if proc and proc.poll() is None:
                    proc.kill()
                return None
        except asyncio.CancelledError:
            logger.debug(f"探测任务被取消: {url}")
            if proc and proc.poll() is None:
                proc.kill()
            raise
        except Exception as e:
            logger.error(f"探测流媒体出错: {str(e)}")
            if proc and proc.poll() is None:
                proc.kill()
            return None
        finally:
            if proc and proc.poll() is None:
                proc.kill()

    async def _check_ffprobe(self):
        """检查ffprobe是否可用"""
        try:
            # 尝试运行ffprobe
            proc = await asyncio.create_subprocess_exec(
                'ffprobe', '-version',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            await proc.wait()
            self._ffprobe_available = proc.returncode == 0
            
            if not self._ffprobe_available:
                self.ffprobe_missing.emit()
        except Exception as e:
            logger.warning(f"ffprobe检查失败: {str(e)}")
            self._ffprobe_available = False
            self.ffprobe_missing.emit()

    def _run_ffprobe(self, url: str) -> Optional[Dict]:
        """执行ffprobe命令（增强错误处理）"""
        proc = None
        try:
            # 检查点1 - 方法开始时
            if not self._is_scanning:
                raise asyncio.CancelledError("扫描已停止")
            
            # 检查点2 - 命令执行前
            if not self._is_scanning:
                raise asyncio.CancelledError("扫描已停止")
            
            # 检查点3 - 查找ffprobe路径后
            # 1. 尝试查找ffprobe路径
            ffprobe_path = self._find_ffprobe()
            if not ffprobe_path:
                logger.warning("ffprobe未找到，将仅检测基本连接性")
                return self._basic_stream_check(url, self._user_agent, self._referer)

            # 2. 构建ffprobe命令
            cmd = [
                ffprobe_path,
                '-v', 'error',
                '-select_streams', 'v:0',
                '-show_entries', 'stream=codec_name,width,height',
                '-of', 'json',
                '-timeout', str(self._timeout * 1_000_000)
            ]
            
            # 添加User-Agent和Referer头
            # 添加更完整的请求头设置
            headers = []
            if self._user_agent:
                headers.append(f"User-Agent: {self._user_agent}")
            if self._referer:
                headers.append(f"Referer: {self._referer}")
            if headers:
                cmd.extend(['-headers', '\r\n'.join(headers)])
                
            cmd.append(url)

            # 3. 执行命令（使用Popen而不是run以便可以终止）
            # 增加详细的日志记录
            logger.debug(f"执行ffprobe命令: {' '.join(cmd)}")
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            logger.debug(f"启动ffprobe进程(PID: {proc.pid})检测URL: {url}")
            self._active_processes.add(proc.pid)

            # 4. 等待结果或取消
            # 增加重试机制
            max_retries = 1
            for attempt in range(max_retries + 1):
                try:
                    stdout, stderr = proc.communicate(timeout=self._timeout)
                    logger.debug(f"ffprobe检测完成(返回码: {proc.returncode})")
                    if proc.returncode == 0:
                        break
                    logger.debug(f"ffprobe错误输出: {stderr.decode('utf-8', errors='ignore')}")
                except subprocess.TimeoutExpired:
                    proc.kill()
                    stdout, stderr = proc.communicate()
                    logger.debug(f"检测超时: {url}, 错误输出: {stderr.decode('utf-8', errors='ignore')}")
                    if attempt == max_retries:
                        return None
                    # 重试前等待1秒
                    time.sleep(1)
                    continue

            # 5. 处理结果
            if proc.returncode == 0:
                output = json.loads(stdout.decode('utf-8'))
                if 'streams' in output and len(output['streams']) > 0:
                    stream = output['streams'][0]
                    result = {
                        'codec': stream.get('codec_name', 'unknown'),
                        'width': int(stream.get('width', 0)),
                        'height': int(stream.get('height', 0)),
                        'valid': True
                    }
                    logger.info(f"频道验证成功: {url} - 分辨率: {result['width']}x{result['height']} 编码: {result['codec']}")
                    return result
            logger.info(f"频道验证失败: {url} - 返回码: {proc.returncode}")
            return None

        except Exception as e:
            logger.error(f"ffprobe执行异常: {str(e)}")
            if proc and proc.poll() is None:
                proc.kill()
            return None
        finally:
            if proc and proc.poll() is None:
                proc.kill()

    def _find_ffprobe(self) -> Optional[str]:
        """查找ffprobe可执行文件路径"""
        # 检查系统PATH
        if self._is_command_available('ffprobe'):
            return 'ffprobe'
        
        # 检查常见路径
        possible_paths = [
            'ffprobe.exe',
            '/usr/bin/ffprobe',
            '/usr/local/bin/ffprobe',
            str(Path(__file__).parent / 'ffmpeg' / 'bin' / 'ffprobe.exe'),
        ]
        
        for path in possible_paths:
            if self._is_command_available(path):
                return path
        return None

    def _is_command_available(self, cmd: str) -> bool:
        """检查命令是否可用"""
        try:
            subprocess.run([cmd, '-version'],
                         stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL,
                         creationflags=subprocess.CREATE_NO_WINDOW,
                         timeout=1)
            return True
        except:
            return False

    def _basic_stream_check(self, url: str, user_agent: str = None, referer: str = None) -> Optional[Dict]:
        """基本流检测（当ffprobe不可用时使用）"""
        try:
            # 使用curl进行简单HTTP检测
            curl_cmd = 'curl' if not sys.platform == 'win32' else 'curl.exe'
            if not self._is_command_available(curl_cmd):
                return None
                
            cmd = [curl_cmd, '-I', '-m', str(self._timeout)]
            
            # 添加User-Agent和Referer头
            if user_agent:
                cmd.extend(['-A', user_agent])
            if referer:
                cmd.extend(['-H', f"Referer: {referer}"])
                
            cmd.append(url)
            
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=self._timeout,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            return {
                'codec': 'unknown',
                'width': 0,
                'height': 0,
                'valid': result.returncode == 0
            }
        except:
            return None

    async def validate_playlist(self, playlist_data: list) -> dict:
        """验证播放列表有效性
        参数:
            playlist_data: 播放列表数据 [{'name': str, 'url': str}, ...] 或 [url1, url2, ...]
        返回:
            {'valid': list, 'invalid': list} 有效和无效的频道列表
        """
        if not playlist_data:
            self.error_occurred.emit("播放列表为空")
            self.validation_status.emit("错误: 播放列表为空")
            return {'valid': [], 'invalid': []}

        # 处理纯URL列表的情况
        if isinstance(playlist_data[0], str):
            playlist_data = [{'url': url} for url in playlist_data]

        logger.info("开始验证播放列表...")
        self._is_scanning = True
        self._start_time = asyncio.get_event_loop().time()
        self.validation_status.emit(f"准备检测播放列表有效性: 共 {len(playlist_data)} 个频道 (通过打开列表按钮加载列表后点击检测有效性)")
        valid_channels = []
        invalid_channels = []
        total = len(playlist_data)
        
        # 初始化线程池
        self._executor = ThreadPoolExecutor(max_workers=self._thread_count)
        
        try:
            # 创建验证任务
            self._tasks = []
            for item in playlist_data:
                if not self._is_scanning:
                    logger.info("验证任务被取消")
                    break
                    
                url = item.get('url', '')
                if not url:
                    logger.warning(f"频道缺少URL: {item.get('name', '未命名')}")
                    invalid_channels.append(item)
                    continue
                    
                logger.info(f"开始验证频道: {url}")
                task = asyncio.create_task(
                    self._validate_channel(item),
                    name=f"validate_{url}"
                )
                self._tasks.append(task)
            
            # 处理验证结果
            for future in asyncio.as_completed(self._tasks):
                try:
                    result = await future
                    if result and result.get('valid', False):
                        valid_channels.append(result)
                        self.channel_found.emit(result)
                        logger.info(f"频道验证成功: {result.get('url')}")
                    else:
                        invalid_channels.append(result)
                        logger.info(f"频道验证失败: {result.get('url')}")
                    
                    # 更新进度
                    current = len(valid_channels) + len(invalid_channels)
                    progress = int(current / total * 100)
                    status = f"验证中: {len(valid_channels)}有效/{len(invalid_channels)}无效 ({current}/{total})"
                    self.progress_updated.emit(progress, status)
                    logger.debug(f"进度更新: {status}")
                    
                except Exception as e:
                    logger.error(f"验证任务异常: {str(e)}")
                    continue
            
            # 验证完成
            logger.info(f"播放列表验证完成 - 有效: {len(valid_channels)} 无效: {len(invalid_channels)}")
            self.scan_finished.emit({
                'channels': valid_channels,
                'total': total,
                'invalid': len(invalid_channels),
                'elapsed': asyncio.get_event_loop().time() - self._start_time
            })
            self.validation_status.emit(f"播放列表验证完成 - 总数: {total} | 有效: {len(valid_channels)} | 无效: {len(invalid_channels)} | 耗时: {asyncio.get_event_loop().time() - self._start_time:.1f}秒")
            self.progress_updated.emit(100, f"验证完成 - 总数: {total} | 有效: {len(valid_channels)} | 无效: {len(invalid_channels)} | 耗时: {asyncio.get_event_loop().time() - self._start_time:.1f}秒")
            
            return {
                'valid': valid_channels,
                'invalid': invalid_channels
            }
            
        finally:
            self._is_scanning = False
            if self._executor:
                self._executor.shutdown(wait=False)
            self._tasks = []

    async def _validate_channel(self, channel_data: dict) -> dict:
        """验证单个频道有效性"""
        try:
            url = channel_data.get('url', '')
            if not url:
                self.validation_status.emit(f"跳过无效URL: {channel_data.get('name', '未命名')}")
                return {**channel_data, 'valid': False}
                
            self.validation_status.emit(f"正在验证: {channel_data.get('name', url)}")
            result = await self._probe_stream(url)
            if result and result.get('valid', False):
                self.validation_status.emit(f"验证成功: {channel_data.get('name', url)}")
                return {
                    **channel_data,
                    'valid': True,
                    'width': result.get('width', 0),
                    'height': result.get('height', 0),
                    'codec': result.get('codec', 'unknown')
                }
            self.validation_status.emit(f"验证失败: {channel_data.get('name', url)}")
            return {**channel_data, 'valid': False}
        except Exception as e:
            logger.error(f"验证频道出错: {str(e)}")
            self.validation_status.emit(f"验证异常: {channel_data.get('name', url)} - {str(e)}")
            return {**channel_data, 'valid': False}

    def stop_scan(self) -> None:
        """增强停止方法
        功能:
            1. 停止扫描任务
            2. 清理资源
            3. 更新UI状态
        注意:
            所有子进程操作都确保使用CREATE_NO_WINDOW标志
        """
        if not self._is_scanning:
            return
            
        logger.debug("开始停止扫描...")
        self._is_scanning = False
        
        # 取消所有任务并记录状态
        cancelled_count = 0
        for task in self._tasks:
            if not task.done():
                logger.debug(f"取消任务: {task.get_name()}")
                task.cancel()
                cancelled_count += 1
        logger.debug(f"共取消{cancelled_count}个任务")
        
        # 终止所有活动的ffprobe进程
        if hasattr(self, '_active_processes') and self._active_processes:
            logger.debug(f"终止{len(self._active_processes)}个ffprobe进程...")
            for pid in list(self._active_processes):
                try:
                    proc = psutil.Process(pid)
                    proc.terminate()
                    logger.debug(f"已终止进程PID: {pid}")
                except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                    logger.debug(f"终止进程失败(PID:{pid}): {str(e)}")
            self._active_processes.clear()
            
        # 关闭线程池
        if self._executor:
            logger.debug("关闭线程池...")
            self._executor.shutdown(wait=False, cancel_futures=True)
            self._executor = None
            
        if hasattr(self, 'valid_channels'):
            self.valid_channels.clear()
            
        # 安全释放锁
        if self._scan_lock.locked():
            try:
                # 只有锁的持有者才能释放
                if self._scan_lock._owner == asyncio.current_task():
                    self._scan_lock.release()
                    logger.debug("已释放扫描锁")
            except (RuntimeError, AttributeError) as e:
                logger.debug(f"释放锁时出错: {str(e)}")
                pass
            
        logger.debug("扫描已完全停止")
        self.progress_updated.emit(0, "已停止")

    async def cleanup(self) -> None:
        """清理所有资源"""
        logger.debug("开始清理扫描器资源...")
        self._is_scanning = False
        self._is_validating = False
        
        # 取消所有任务
        for task in self._tasks:
            if not task.done():
                task.cancel()
        
        # 终止所有活动进程
        if hasattr(self, '_active_processes') and self._active_processes:
            for pid in list(self._active_processes):
                try:
                    proc = psutil.Process(pid)
                    proc.terminate()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            self._active_processes.clear()
        
        # 关闭线程池
        if self._executor:
            self._executor.shutdown(wait=False, cancel_futures=True)
            self._executor = None
        
        logger.debug("扫描器资源清理完成")
