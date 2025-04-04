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
        self._is_validating = False  # 新增验证状态标志
        self._timeout = 5
        self._thread_count = 10  # 扫描线程数
        self._validation_threads = 10  # 验证线程数
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
        self._batches = []  # 跟踪所有批次任务

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
        """切换扫描状态(增强版)
        参数:
            ip_pattern: IP地址模式字符串
        功能:
            1. 如果正在扫描则强制停止所有任务
            2. 如果未扫描则开始扫描
        改进:
            1. 更可靠的停止机制
            2. 更严格的锁管理
            3. 更完善的错误处理
        """
        if self._is_scanning:
            # 强制停止扫描并等待完成
            await self._stop_scanning()
            # 确保所有任务已完成
            await asyncio.sleep(0.1)  # 给取消操作一点时间
            self.progress_updated.emit(0, "已完全停止")
            return

        async with self._scan_lock:
            if self._is_scanning:
                self.error_occurred.emit("已有扫描任务正在进行")
                return

            try:
                # 重置状态
                self._is_scanning = True
                self._start_time = asyncio.get_event_loop().time()
                self._scanned_count = 0
                self._tasks = []
                self._batches = []
                
                # 执行扫描任务，使用shield防止取消
                scan_task = asyncio.create_task(self._scan_task(ip_pattern))
                await asyncio.shield(scan_task)
            except asyncio.CancelledError:
                logger.debug("扫描任务被正常取消")
                self.progress_updated.emit(0, "扫描已取消")
            except Exception as e:
                logger.error(f"扫描任务异常: {str(e)}")
                self.error_occurred.emit(f"扫描错误: {str(e)}")
            finally:
                # 确保状态被重置
                self._is_scanning = False
                # 清理资源
                if hasattr(self, '_executor') and self._executor:
                    self._executor.shutdown(wait=False)
                    self._executor = None

    async def _scan_task(self, ip_pattern: str) -> None:
        """执行扫描的核心任务(增强版)
        改进:
            1. 更频繁的状态检查
            2. 更可靠的取消处理
            3. 更完善的资源清理
        """
        try:
            # 检查点1 - 任务开始时
            if not self._is_scanning:
                raise asyncio.CancelledError("扫描已停止")
                
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
                
            # 检查点2 - URL解析完成后
            if not self._is_scanning:
                raise asyncio.CancelledError("扫描已停止")
                
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
            
            # 使用asyncio.as_completed处理结果，并确保所有future被正确处理
            pending = set(self._tasks)
            while pending and self._is_scanning:
                try:
                    # 等待第一个完成的任务
                    done, pending = await asyncio.wait(
                        pending,
                        return_when=asyncio.FIRST_COMPLETED
                    )
                    
                    for future in done:
                        try:
                            result = await future
                            url, result = result if isinstance(result, tuple) else (None, result)
                            
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
                        except asyncio.CancelledError:
                            logger.debug("任务被取消")
                            raise
                except Exception as e:
                    logger.debug(f"任务处理异常: {str(e)}")
                    continue
                    
            
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
                    logger.debug(f"ffprobe命令执行完成，返回码: {proc.returncode}")
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
        """验证播放列表有效性(增强分批处理版)
        参数:
            playlist_data: 播放列表数据 [{'name': str, 'url': str}, ...] 或 [url1, url2, ...]
        返回:
            {'valid': list, 'invalid': list} 有效和无效的频道列表
        优化点:
            1. 更智能的批次大小控制
            2. 批次间资源清理
            3. 更细致的进度反馈
        """
        # 检查播放列表数据有效性
        if not playlist_data or not isinstance(playlist_data, list):
            self.error_occurred.emit("播放列表为空或格式错误")
            self.validation_status.emit("错误: 播放列表为空或格式错误")
            return {'valid': [], 'invalid': []}

        # 更严格的状态检查 - 防止快速点击导致状态不一致
        if self._is_validating or self._is_scanning:
            logger.warning("已有任务正在进行")
            self.error_occurred.emit("已有任务正在进行")
            self.validation_status.emit("错误: 已有任务正在进行")
            return {'valid': [], 'invalid': []}

        # 原子性设置验证状态
        self._is_validating = True
        await asyncio.sleep(0)  # 确保状态变更立即生效

        # 处理纯URL列表的情况
        if isinstance(playlist_data[0], str):
            playlist_data = [{'url': url} for url in playlist_data]

        logger.info(f"开始验证播放列表(共{len(playlist_data)}个频道)...")
        self._start_time = asyncio.get_event_loop().time()
        self.validation_status.emit(f"准备检测播放列表有效性: 共 {len(playlist_data)} 个频道")
        valid_channels = []
        invalid_channels = []
        total = len(playlist_data)
        
        try:
            # 初始化验证线程池(确保只初始化一次)
            if (not hasattr(self, '_executor') or self._executor is None or self._executor._shutdown or 
                (hasattr(self._executor, '_max_workers') and self._executor._max_workers != self._validation_threads)):
                if hasattr(self, '_executor') and self._executor:
                    self._executor.shutdown(wait=False)
                self._executor = ThreadPoolExecutor(max_workers=self._validation_threads)
                logger.info(f"初始化验证线程池(线程数: {self._validation_threads})")
            
            # 三重检查验证状态
            if not self._is_validating or self._is_scanning:
                logger.warning("验证任务被取消(状态检查) - 可能由于状态冲突导致")
                self.validation_status.emit("验证被意外取消")
                self._is_validating = False
                raise asyncio.CancelledError("验证已停止")
            
            # 动态计算批次大小(基于线程数和列表大小)
            batch_size = min(
                max(self._thread_count * 2, 10),  # 最小10个/批
                min(self._thread_count * 10, 100), # 最大100个/批
                total // 10 or 1  # 确保至少有1个批次
            )
            
            processed = 0
            while processed < total and self._is_validating:
                # 检查是否已停止
                if not self._is_validating:
                    break
                    
                # 准备当前批次任务
                self._tasks = []
                
                # 获取当前批次数据
                batch_end = min(processed + batch_size, total)
                current_batch = playlist_data[processed:batch_end]
                batch_valid = 0
                batch_invalid = 0
                
                # 再次检查是否已停止
                if not self._is_validating:
                    break
                
                # 创建当前批次任务
                for item in current_batch:
                    # 检查是否已停止验证
                    if not self._is_validating:
                        logger.info("验证任务被取消(批次检查)")
                        break
                        
                    url = item.get('url', '')
                    if not url:
                        invalid_channels.append(item)
                        batch_invalid += 1
                        continue
                        
                    task = asyncio.create_task(
                        self._validate_channel(item),
                        name=f"validate_{url}"
                    )
                    self._tasks.append(task)
                
                # 处理当前批次结果
                for future in asyncio.as_completed(self._tasks):
                    # 检查是否已停止验证
                    if not self._is_validating:
                        logger.info("验证任务被取消(任务检查)")
                        break
                        
                    try:
                        result = await future
                        if result and result.get('valid', False):
                            valid_channels.append(result)
                            self.channel_found.emit(result)
                            batch_valid += 1
                        else:
                            invalid_channels.append(result)
                            batch_invalid += 1
                    except Exception:
                        continue
                
                # 更新进度
                processed = len(valid_channels) + len(invalid_channels)
                progress = int(processed / total * 100)
                status = (
                    f"验证进度: {len(valid_channels)}有效/{len(invalid_channels)}无效 ({processed}/{total}) | "
                    f"当前批次: {batch_valid}有效/{batch_invalid}无效 | "
                    f"验证速度: {batch_size/(asyncio.get_event_loop().time()-self._start_time):.1f}个/秒"
                )
                self.progress_updated.emit(progress, status)
                
                # 清理当前批次任务
                self._tasks = []
                processed = batch_end
                
                # 短暂暂停以保持UI响应
                await asyncio.sleep(0.1)
            
            # 验证完成
            elapsed = asyncio.get_event_loop().time() - self._start_time
            logger.info(f"播放列表验证完成 - 有效: {len(valid_channels)} 无效: {len(invalid_channels)} 耗时: {elapsed:.1f}秒")
            self.scan_finished.emit({
                'channels': valid_channels,
                'total': total,
                'invalid': len(invalid_channels),
                'elapsed': elapsed
            })
            self.validation_status.emit(
                f"验证完成 - 总数: {total} | "
                f"有效: {len(valid_channels)} | "
                f"无效: {len(invalid_channels)} | "
                f"耗时: {elapsed:.1f}秒 | "
                f"平均速度: {total/max(elapsed, 0.1):.1f}个/秒"
            )
            self.progress_updated.emit(100, 
                f"验证完成 - 总数: {total} | "
                f"有效: {len(valid_channels)} | "
                f"无效: {len(invalid_channels)} | "
                f"耗时: {elapsed:.1f}秒"
            )
            
            return {
                'valid': valid_channels,
                'invalid': invalid_channels
            }
            
        except asyncio.CancelledError:
            logger.info("验证任务被正常取消")
            self.validation_status.emit("验证已取消")
            raise
        except Exception as e:
            logger.error(f"验证过程中发生异常: {str(e)}")
            self.error_occurred.emit(f"验证错误: {str(e)}")
            self.validation_status.emit(f"验证错误: {str(e)}")
        finally:
            # 仅重置验证状态，不关闭线程池(可能被其他操作使用)
            self._is_validating = False
            self._tasks = []
            logger.info("验证任务清理完成")

    async def _validate_channel(self, channel_data: dict) -> dict:
        """验证单个频道有效性"""
        try:
            url = channel_data.get('url', '')
            if not url:
                self.validation_status.emit(f"跳过无效URL: {channel_data.get('name', '未命名')}")
                return {**channel_data, 'valid': False}
                
            # 检查是否已停止验证
            if not self._is_validating:
                logger.debug("验证已停止，跳过当前频道")
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
        """停止IP扫描方法"""
        if not self._is_scanning:
            return
        logger.info("停止IP扫描请求")
        self._is_scanning = False
        # 仅取消扫描相关任务
        for task in self._tasks:
            if not task.done() and task.get_name().startswith("probe_"):
                task.cancel()
        # 保留验证任务继续运行

    async def stop_validation(self) -> None:
        """停止有效性验证方法(增强版)
        改进:
            1. 更可靠的取消机制
            2. 更彻底的资源清理
            3. 更详细的状态跟踪
        """
        if not hasattr(self, '_is_validating') or not self._is_validating:
            logger.debug("无活动验证任务可停止")
            return
            
        logger.info("停止有效性验证请求")
        
        # 原子性设置验证状态
        self._is_validating = False
        await asyncio.sleep(0)  # 确保状态变更立即生效
        
        # 获取当前事件循环
        loop = asyncio.get_event_loop()
        
        # 取消所有验证任务
        cancelled_count = 0
        for task in self._tasks:
            if not task.done() and task.get_name().startswith("validate_"):
                task.cancel()
                cancelled_count += 1
                try:
                    await task  # 等待任务处理取消
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    logger.debug(f"任务取消时出错: {str(e)}")
        logger.info(f"已取消{cancelled_count}个验证任务")
                
        # 终止所有相关进程
        if hasattr(self, '_active_processes'):
            killed_count = 0
            for pid in list(self._active_processes):
                try:
                    proc = psutil.Process(pid)
                    if proc.is_running():
                        proc.kill()
                        killed_count += 1
                        logger.debug(f"已终止进程PID: {pid}")
                except psutil.NoSuchProcess:
                    pass
                except Exception as e:
                    logger.debug(f"终止进程时出错(PID:{pid}): {str(e)}")
            self._active_processes.clear()
            logger.info(f"已终止{killed_count}个相关进程")
            
        # 清理线程池中的待处理任务
        if hasattr(self, '_executor') and self._executor:
            try:
                # 取消线程池中所有待处理任务
                for future in self._executor._futures:
                    if not future.done():
                        future.cancel()
                logger.debug("已取消线程池中的待处理任务")
            except Exception as e:
                logger.debug(f"取消线程池任务时出错: {str(e)}")
        
        # 强制更新UI状态
        self.progress_updated.emit(0, "验证已停止")
        self.validation_status.emit("验证已完全停止")
        
        # 确保状态已同步
        await asyncio.sleep(0.1)
        logger.info("验证停止流程完成")

    async def _stop_scanning(self) -> None:
        """强制停止所有操作(紧急情况使用)
        改为异步方法以确保协程被正确等待"""
        logger.warning("强制停止所有操作")
        self._is_scanning = False
        if hasattr(self, '_is_validating'):
            self._is_validating = False
        
        # 取消所有任务
        for task in self._tasks:
            if not task.done():
                task.cancel()
        
        # 获取当前事件循环
        loop = asyncio.get_event_loop()
        
        # 强制取消所有任务(包括批次和当前任务)
        all_tasks = []
        for batch in self._batches:
            all_tasks.extend(batch)
        all_tasks.extend(self._tasks)
        
        # 取消并等待所有任务完成
        cancelled_count = 0
        for task in all_tasks:
            if not task.done():
                task.cancel()
                cancelled_count += 1
                try:
                    await task
                except:
                    pass
        logger.debug(f"已取消{cancelled_count}个任务")
        
        # 强制终止所有活动进程
        if hasattr(self, '_active_processes'):
            for pid in list(self._active_processes):
                try:
                    proc = psutil.Process(pid)
                    if proc.is_running():
                        proc.kill()
                        logger.debug(f"已强制终止进程PID: {pid}")
                except:
                    pass
            self._active_processes.clear()
        
        # 强制终止所有子进程
        try:
            current_process = psutil.Process()
            for child in current_process.children(recursive=True):
                try:
                    if child.is_running():
                        child.kill()
                        logger.debug(f"已强制终止子进程PID: {child.pid}")
                except:
                    pass
        except:
            pass
            
            # 安全关闭线程池
            if hasattr(self, '_executor') and self._executor is not None:
                try:
                    self._executor.shutdown(wait=False, cancel_futures=True)
                except Exception as e:
                    logger.error(f"关闭线程池时出错: {str(e)}")
                finally:
                    self._executor = None
                
        # 重置状态
        self._tasks = []
        self._batches = []
        
        logger.debug("所有任务和进程已强制停止")
        self.progress_updated.emit(0, "已完全停止")
        self.validation_status.emit("所有任务已强制停止")
        
        # 强制更新UI状态
        self.progress_updated.emit(0, "正在清理资源...")
        self.validation_status.emit("正在清理资源...")
        
        # 终止所有活动的ffprobe进程
        if hasattr(self, '_active_processes') and self._active_processes:
            logger.debug(f"终止{len(self._active_processes)}个ffprobe进程...")
            for pid in list(self._active_processes):
                try:
                    proc = psutil.Process(pid)
                    if proc.is_running():
                        try:
                            proc.terminate()
                            try:
                                proc.wait(timeout=0.5)
                            except (psutil.TimeoutExpired, psutil.NoSuchProcess):
                                try:
                                    proc.kill()
                                except:
                                    pass
                            logger.debug(f"已终止进程PID: {pid}")
                        except psutil.NoSuchProcess:
                            logger.debug(f"进程已终止(PID:{pid})")
                except Exception as e:
                    logger.debug(f"终止进程时出错(PID:{pid}): {str(e)}")
            self._active_processes.clear()
            
        # 强制终止所有子进程(包括残留进程)
        try:
            current_process = psutil.Process()
            children = current_process.children(recursive=True)
            for child in children:
                try:
                    if child.is_running():
                        try:
                            child.terminate()
                            try:
                                child.wait(timeout=0.5)
                            except (psutil.TimeoutExpired, psutil.NoSuchProcess):
                                try:
                                    child.kill()
                                except:
                                    pass
                            logger.debug(f"已终止子进程PID: {child.pid}")
                        except psutil.NoSuchProcess:
                            logger.debug(f"子进程已终止(PID:{child.pid})")
                except Exception as e:
                    logger.debug(f"终止子进程时出错(PID:{child.pid}): {str(e)}")
        except Exception as e:
            logger.error(f"终止子进程时出错: {str(e)}")
            
        # 强制重置UI状态
        self.progress_updated.emit(0, "已完全停止")
        self.validation_status.emit("验证已完全停止")
            
        # 强制终止所有子进程
        try:
            current_process = psutil.Process()
            children = current_process.children(recursive=True)
            for child in children:
                try:
                    child.terminate()
                    try:
                        child.wait(timeout=1)
                    except (psutil.TimeoutExpired, psutil.NoSuchProcess):
                        pass
                    logger.debug(f"已终止子进程PID: {child.pid}")
                except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                    logger.debug(f"终止子进程失败(PID:{child.pid}): {str(e)}")
        except Exception as e:
            logger.error(f"终止子进程时出错: {str(e)}")
            
        # 关闭线程池
        if self._executor:
            logger.debug("关闭线程池...")
            try:
                self._executor.shutdown(wait=False, cancel_futures=True)
            except Exception as e:
                logger.error(f"关闭线程池时出错: {str(e)}")
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
