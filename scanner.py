import asyncio
import subprocess
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor
from PyQt6 import QtWidgets
from PyQt6.QtCore import QObject, pyqtSignal
from utils import setup_logger
from qasync import asyncSlot
from utils import parse_ip_range
from playlist_io import PlaylistHandler

logger = setup_logger('Scanner')

class StreamScanner(QObject):
    progress_updated = pyqtSignal(int, str)    # 进度百分比, 状态信息
    scan_finished = pyqtSignal(list)           # 有效频道列表
    channel_found = pyqtSignal(dict)           # 单个有效频道信息
    error_occurred = pyqtSignal(str)           # 错误信息

    def __init__(self):
        """流媒体扫描器
        功能:
            1. 初始化扫描参数
            2. 加载播放列表处理器
            3. 初始化扫描状态
        """
        super().__init__()
        self._is_scanning = False
        self._timeout = 5  # 默认超时时间为 5 秒
        self._thread_count = 10  # 默认线程数为 10
        self._scan_lock = asyncio.Lock()  # 扫描任务锁
        self.playlist = PlaylistHandler()  # 播放列表处理器
        self._start_time = 0  # 扫描开始时间
        self._scanned_count = 0  # 已扫描IP计数器
        # 创建固定大小的线程池
        self._executor = None

    def set_timeout(self, timeout: int) -> None:
        """设置超时时间（单位：秒）"""
        self._timeout = timeout

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
    async def start_scan(self, ip_pattern: str) -> None:
        """启动扫描任务
        参数:
            ip_pattern: IP地址模式字符串
        功能:
            1. 检查是否有正在进行的扫描
            2. 初始化扫描状态
            3. 保存扫描地址到缓存
            4. 开始扫描任务
        """
        # 保存扫描地址到缓存
        self.playlist.update_scan_address(ip_pattern)
        async with self._scan_lock:
            if self._is_scanning:
                self.error_occurred.emit("已有扫描任务正在进行")
                return

            self._is_scanning = True
            self._start_time = asyncio.get_event_loop().time()
            self._scanned_count = 0  # 重置计数器
            try:
                await self._scan_task(ip_pattern)
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
            
            # 创建线程池，大小与并发数一致
            self._executor = ThreadPoolExecutor(max_workers=self._thread_count)
            
            async def probe_url(url: str) -> tuple[str, Optional[Dict]]:
                try:
                    result = await self._probe_stream(url)
                    return (url, result)
                finally:
                    await asyncio.get_event_loop().run_in_executor(None, QtWidgets.QApplication.processEvents)
            
            # 创建所有探测任务
            tasks = [asyncio.create_task(probe_url(url)) for url in urls]
            
            # 使用asyncio.as_completed处理结果
            for future in asyncio.as_completed(tasks):
                try:
                    result = await future
                    url, result = result if isinstance(result, tuple) else (None, result)
                    
                    if url is None:
                        logger.debug("跳过无效URL")
                        continue
                        
                    self._scanned_count += 1
                    
                    if result is not None:
                        channel_name = f"频道 {len(valid_channels) + 1}"
                        channel_info = {
                            'name': channel_name,
                            'url': url,
                            'width': result['width'],
                            'height': result['height'],
                            'codec': result['codec'],
                            'resolution': f"{result['width']}x{result['height']}"
                        }
                        valid_channels.append(channel_info)
                        self.channel_found.emit(channel_info)
                    
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
                        f"有效: {len(valid_channels)}"
                    ]
                    status_msg = " | ".join(filter(None, status_parts))
                    self.progress_updated.emit(progress, status_msg)
                    
                except Exception:
                    pass
            
            # 等待所有任务完成
            await asyncio.gather(*tasks, return_exceptions=True)
            
            if self._is_scanning:
                elapsed = asyncio.get_event_loop().time() - self._start_time
                self.scan_finished.emit(valid_channels)
                self.progress_updated.emit(100, f"扫描完成，耗时 {elapsed:.1f} 秒")
                
        except Exception as e:
            self.error_occurred.emit(f"扫描错误: {str(e)}")
            raise
        finally:
            self._is_scanning = False

    async def _probe_stream(self, url: str) -> Optional[Dict]:
        """探测单个流媒体信息"""
        try:
            loop = asyncio.get_running_loop()
        except Exception:
            return None
            
        try:
            result = await loop.run_in_executor(
                self._executor,
                self._run_ffprobe, 
                url
            )
            return result
        except Exception:
            return None
        finally:
            await asyncio.sleep(0)
            
    def _run_ffprobe(self, url: str) -> Optional[Dict]:
        """执行ffprobe命令的同步方法
        参数:
            url: 要探测的流媒体URL
        返回:
            包含视频信息的字典(codec,width,height)或None
        功能:
            1. 使用CREATE_NO_WINDOW标志避免弹出窗口
            2. 严格的错误处理和日志记录
            3. 优化超时处理
            4. 处理打包环境下的路径问题
        """
        try:
            # 尝试多种方式查找ffprobe路径
            ffprobe_path = None
            possible_paths = [
                'ffprobe',  # 系统PATH中的ffprobe
                './ffprobe.exe',  # 当前目录
                './bin/ffprobe.exe',  # bin子目录
                './ffmpeg/bin/ffprobe.exe',  # ffmpeg子目录
            ]
            
            for path in possible_paths:
                try:
                    subprocess.run([path, '-version'], 
                                 stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL,
                                 creationflags=subprocess.CREATE_NO_WINDOW,
                                 timeout=1)
                    ffprobe_path = path
                    break
                except:
                    continue
            
            if not ffprobe_path:
                logger.error("无法找到ffprobe可执行文件")
                return None

            # 构建ffprobe命令
            cmd = [
                ffprobe_path,
                '-v', 'quiet',  # 更安静的日志级别
                '-hide_banner',  # 隐藏banner信息
                '-loglevel', 'fatal',  # 只显示致命错误
                '-select_streams', 'v:0',
                '-show_entries', 'stream=codec_name,width,height',
                '-of', 'csv=p=0',
                '-timeout', str(self._timeout * 1_000_000),
                url
            ]
            
            # 执行命令
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                timeout=self._timeout,
                creationflags=subprocess.CREATE_NO_WINDOW,
                shell=False,
                check=False,
                start_new_session=True
            )
            
            # 处理结果
            if result.returncode != 0:
                logger.debug(f"ffprobe失败: {url} - 返回码:{result.returncode}")
                return None
                
            # 解析输出
            output = result.stdout.decode('utf-8', errors='ignore').strip()
            lines = [line for line in output.splitlines() if line.strip()]
            if not lines or len(lines[0].split(',')) < 3:
                logger.debug(f"ffprobe输出格式错误: {url} - 输出:{output}")
                return None
                
            # 提取视频信息
            video_info = lines[0].split(',')
            return {
                'codec': video_info[0],
                'width': int(video_info[1]),
                'height': int(video_info[2])
            }
            
        except subprocess.TimeoutExpired:
            logger.debug(f"ffprobe超时: {url}")
            return None
        except Exception as e:
            logger.error(f"ffprobe异常 - 命令: {' '.join(cmd)}\n错误: {str(e)}\n路径: {ffprobe_path}")
            return None

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
            
        self._is_scanning = False
        
        # 关闭线程池
        if self._executor:
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
            except (RuntimeError, AttributeError):
                pass
            
        self.progress_updated.emit(0, "已停止")
