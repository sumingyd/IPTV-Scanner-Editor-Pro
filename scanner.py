import asyncio
import subprocess
import json
import sys
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
    scan_finished = pyqtSignal(list)           # 有效频道列表
    channel_found = pyqtSignal(dict)           # 单个有效频道信息
    error_occurred = pyqtSignal(str)           # 错误信息
    ffprobe_missing = pyqtSignal()             # 新增：ffprobe缺失信号

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
        else:
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
        """探测单个流媒体信息（增强版）"""
        try:
            # 首次使用时检查ffprobe可用性
            if not self._ffprobe_checked:
                await self._check_ffprobe()
                self._ffprobe_checked = True

            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                self._executor,
                self._run_ffprobe, 
                url
            )
            return result
        except Exception as e:
            logger.error(f"探测流媒体出错: {str(e)}")
            return None

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
        try:
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
                '-timeout', str(self._timeout * 1_000_000),
            ]
            
            # 添加User-Agent和Referer头
            if self._user_agent:
                cmd.extend(['-user_agent', self._user_agent])
            if self._referer:
                cmd.extend(['-headers', f"Referer: {self._referer}"])
                
            cmd.append(url)

            # 3. 执行命令
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=self._timeout,
                creationflags=subprocess.CREATE_NO_WINDOW,
                check=False
            )

            # 4. 处理结果
            if result.returncode == 0:
                output = json.loads(result.stdout.decode('utf-8'))
                if 'streams' in output and len(output['streams']) > 0:
                    stream = output['streams'][0]
                    return {
                        'codec': stream.get('codec_name', 'unknown'),
                        'width': int(stream.get('width', 0)),
                        'height': int(stream.get('height', 0)),
                        'valid': True
                    }
            return None

        except subprocess.TimeoutExpired:
            logger.debug(f"检测超时: {url}")
            return None
        except Exception as e:
            logger.error(f"ffprobe执行异常: {str(e)}")
            return None

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
