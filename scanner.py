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
from async_utils import AsyncWorker, asyncSlot
from playlist_io import PlaylistHandler
from utils import setup_logger, parse_ip_range

logger = setup_logger('Scanner')

class StreamScanner(QObject):
    progress_updated = pyqtSignal(int, str)    # 进度百分比, 状态信息
    scan_finished = pyqtSignal(dict)           # 扫描结果字典
    channel_found = pyqtSignal(dict)           # 单个有效频道信息
    error_occurred = pyqtSignal(str)           # 错误信息
    ffprobe_missing = pyqtSignal()             # ffprobe缺失信号
    scan_started = pyqtSignal(str)             # 扫描开始信号，带扫描地址
    scan_stopped = pyqtSignal()                # 扫描停止信号
    stats_updated = pyqtSignal(str)            # 统计信息更新
    def __init__(self):
        super().__init__()
        logger.info("初始化StreamScanner")
        self._is_scanning = False
        self._timeout = 5
        self._thread_count = 10
        self._scan_lock = asyncio.Lock()
        self.playlist = PlaylistHandler()
        self._executor = None
        self._ffprobe_available = False
        self._user_agent = None
        self._referer = None
        self._active_tasks = set()
        self._active_processes = set()
        logger.debug(f"初始化完成: timeout={self._timeout}, thread_count={self._thread_count}")
        
        # 初始化ffprobe路径，与validator.py保持一致
        from utils import ConfigHandler
        import os
        import sys
        if getattr(sys, 'frozen', False):
            self._ffprobe_path = os.path.join(sys._MEIPASS, 'ffmpeg', 'bin', 'ffprobe.exe')
        else:
            config = ConfigHandler()
            self._ffprobe_path = config.config.get('Scanner', 'ffprobe_path', 
                            fallback=os.path.join(os.path.dirname(__file__), '..', 'ffmpeg', 'bin', 'ffprobe.exe'))

    def set_timeout(self, timeout: int) -> None:
        logger.info(f"设置超时时间: {timeout}s")
        self._timeout = timeout

    def set_user_agent(self, user_agent: str) -> None:
        logger.debug(f"设置User-Agent: {user_agent}")
        self._user_agent = user_agent

    def set_referer(self, referer: str) -> None:
        logger.debug(f"设置Referer: {referer}")
        self._referer = referer

    def set_thread_count(self, thread_count: int) -> None:
        logger.info(f"设置线程数: {thread_count}")
        self._thread_count = thread_count

    @asyncSlot()
    async def toggle_scan(self, ip_pattern: str) -> asyncio.Task:
        """切换扫描状态"""
        logger.info(f"切换扫描状态, 当前状态: {'扫描中' if self._is_scanning else '空闲'}")
        if self._is_scanning:
            logger.info("正在停止扫描...")
            await self._stop_scanning()
            self.scan_stopped.emit()
            logger.info("扫描已停止")
            return

        async with self._scan_lock:
            if self._is_scanning:
                logger.debug("扫描已在运行中，忽略重复启动")
                return

            try:
                logger.info(f"开始扫描IP模式: {ip_pattern}")
                self._is_scanning = True
                self.scan_started.emit(ip_pattern)
                self._executor = ThreadPoolExecutor(max_workers=self._thread_count)
                self._active_tasks.clear()
                logger.debug(f"创建线程池，线程数: {self._thread_count}, 超时: {self._timeout}s")
            except Exception as e:
                error_msg = f"扫描启动失败: {str(e)}"
                logger.error(error_msg, exc_info=True)
                self.error_occurred.emit(error_msg)
                self._is_scanning = False
                logger.error("扫描启动失败，状态已重置")
                raise
                
                # 解析IP范围
                urls = list(parse_ip_range(ip_pattern))
                logger.debug(f"解析IP范围完成，生成URL数量: {len(urls)}")
                if not urls:
                    error_msg = "未生成任何扫描地址"
                    logger.error(error_msg)
                    self.error_occurred.emit(error_msg)
                    return

                # 创建扫描任务
                task = asyncio.create_task(self._run_scan(urls))
                self._active_tasks.add(task)
                task.add_done_callback(lambda t: self._active_tasks.discard(t))
                logger.debug(f"创建扫描任务，当前活动任务数: {len(self._active_tasks)}")
                
                logger.info("扫描任务已启动")
                return task
            except Exception as e:
                error_msg = f"扫描启动失败: {str(e)}"
                logger.error(error_msg, exc_info=True)
                self.error_occurred.emit(error_msg)
                self._is_scanning = False
                logger.error("扫描启动失败，状态已重置")
                raise

    async def _run_scan(self, urls: List[str]) -> None:
        """执行扫描任务"""
        start_time = time.time()
        logger.info(f"开始执行扫描任务，URL总数: {len(urls)}")
        try:
            total = len(urls)
            valid_channels = []
            invalid_count = 0
            logger.debug(f"初始状态: valid={len(valid_channels)}, invalid={invalid_count}")
            
            # 分批处理
            batch_size = min(100, max(10, self._thread_count * 2))
            logger.debug(f"使用批量处理，每批大小: {batch_size}")
            for i in range(0, total, batch_size):
                if not self._is_scanning:
                    logger.info("扫描被手动停止，中止处理")
                    break
                    
                batch = urls[i:i + batch_size]
                logger.debug(f"处理批次 {i//batch_size + 1}/{total//batch_size + 1}, 当前进度: {i}/{total}")
                results = await self._process_batch(batch)
                logger.debug(f"批次处理完成，结果数: {len(results)}")
                
                for url, result in results:
                    if result:
                        channel = {
                            'name': f"频道 {len(valid_channels) + 1}",
                            'url': url,
                            'width': result.get('width', 0),
                            'height': result.get('height', 0),
                            'latency': result.get('latency', 0.0),
                            'valid': result.get('valid', False)
                        }
                        valid_channels.append(channel)
                        self.channel_found.emit(channel)
                        logger.debug(f"发现有效频道: {url}, 分辨率: {result.get('width')}x{result.get('height')}")
                    else:
                        invalid_count += 1
                        logger.debug(f"无效URL: {url}")
                    
                    # 更新进度
                    progress = int((i + len(results)) / total * 100)
                    status = f"进度: {i + len(results)}/{total} | 有效: {len(valid_channels)} | 无效: {invalid_count}"
                    self.progress_updated.emit(progress, status)
                    logger.debug(f"进度更新: {progress}% - {status}")

            if self._is_scanning:
                elapsed = time.time() - start_time
                self.scan_finished.emit({
                    'channels': valid_channels,
                    'total': total,
                    'invalid': invalid_count,
                    'elapsed': elapsed
                })
                logger.info(f"扫描完成 - 有效: {len(valid_channels)}/{total}, 耗时: {elapsed:.2f}s")
        finally:
            self._is_scanning = False
            if self._executor:
                logger.debug("关闭线程池")
                self._executor.shutdown(wait=False)
                self._executor = None
            logger.debug("扫描任务清理完成")

    async def _process_batch(self, batch: List[str]) -> List[tuple]:
        """处理一批URL"""
        tasks = []
        logger.debug(f"开始处理批次，URL数量: {len(batch)}")
        for url in batch:
            if not self._is_scanning:
                logger.debug("扫描被停止，中止批次处理")
                break
            task = asyncio.create_task(self._probe_stream(url))
            self._active_tasks.add(task)
            task.add_done_callback(lambda t: self._active_tasks.discard(t))
            tasks.append(task)
            logger.debug(f"创建探测任务: {url}")
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        logger.debug(f"批次处理完成，结果数: {len(results)}")
        return results

    async def _probe_stream(self, url: str) -> Optional[Dict]:
        """探测单个流媒体"""
        try:
            if not self._is_scanning:
                logger.debug("扫描已停止，跳过探测")
                return None
                
            # 检查ffprobe可用性
            if not self._ffprobe_available:
                logger.debug("ffprobe未验证，开始检查")
                await self._check_ffprobe()
                if not self._ffprobe_available:
                    logger.warning("ffprobe不可用，仅能进行基本连接检测")
                
            # 执行探测
            logger.debug(f"开始探测流媒体: {url}")
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                self._executor,
                self._run_probe,
                url
            )
            logger.debug(f"探测完成: {url}, 结果: {result is not None}")
            return (url, result)
        except Exception as e:
            logger.error(f"探测失败: {url} - {str(e)}", exc_info=True)
            return (url, None)

    def _run_probe(self, url: str) -> Optional[Dict]:
        """执行实际的探测命令"""
        try:
            # 使用ffprobe探测流媒体信息
            cmd = [
                self._find_ffprobe(),
                '-v', 'error',
                '-select_streams', 'v:0',
                '-show_entries', 'stream=codec_name,width,height',
                '-show_entries', 'format=start_time',
                '-of', 'json',
                '-timeout', str(self._timeout * 1_000_000),
                url
            ]
            logger.debug(f"执行ffprobe命令: {' '.join(cmd)}")
            logger.debug(f"探测参数: timeout={self._timeout}s, user_agent={self._user_agent}, referer={self._referer}")
            
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            self._active_processes.add(proc.pid)
            
            try:
                stdout, stderr = proc.communicate(timeout=self._timeout)
                if proc.returncode == 0:
                    data = json.loads(stdout.decode('utf-8'))
                    logger.debug(f"ffprobe output for {url}: {data}")
                    if data.get('streams'):
                        start_time = data.get('format', {}).get('start_time')
                        if start_time is None:
                            logger.debug(f"ffprobe未返回start_time: {url}")
                            latency = 0.0
                        else:
                            latency = float(start_time)
                            logger.debug(f"计算延迟: {url} - {latency}秒")
                        return {
                            'codec': data['streams'][0].get('codec_name', 'unknown'),
                            'width': int(data['streams'][0].get('width', 0)),
                            'height': int(data['streams'][0].get('height', 0)),
                            'latency': latency,
                            'valid': True
                        }
                    else:
                        logger.debug(f"No streams found in ffprobe output for {url}")
                else:
                    logger.debug(f"ffprobe failed for {url}, stderr: {stderr.decode('utf-8')}")
            finally:
                if proc.poll() is None:
                    proc.kill()
                self._active_processes.discard(proc.pid)
                
        except Exception:
            pass
        return None

    async def _check_ffprobe(self) -> None:
        """检查ffprobe是否可用"""
        try:
            ffprobe_path = self._find_ffprobe()
            logger.debug(f"检查ffprobe可用性，路径: {ffprobe_path}")
            
            proc = await asyncio.create_subprocess_exec(
                ffprobe_path, '-version',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            await proc.wait()
            self._ffprobe_available = proc.returncode == 0
            if not self._ffprobe_available:
                logger.error(f"ffprobe不可用，路径: {ffprobe_path}, 返回码: {proc.returncode}")
                self.ffprobe_missing.emit()
        except Exception as e:
            logger.warning(f"ffprobe检查失败: {str(e)}")
            self._ffprobe_available = False
            self.ffprobe_missing.emit()

    def _find_ffprobe(self) -> str:
        """查找ffprobe路径"""
        logger.debug(f"使用ffprobe路径: {self._ffprobe_path}")
        if not Path(self._ffprobe_path).exists():
            logger.error(f"ffprobe文件不存在: {self._ffprobe_path}")
            self.ffprobe_missing.emit()
        return self._ffprobe_path

    def stop_scan(self) -> None:
        """停止扫描"""
        if not self._is_scanning:
            return
            
        self._is_scanning = False
        for task in self._active_tasks:
            if not task.done():
                task.cancel()

    async def _stop_scanning(self) -> None:
        """停止所有扫描任务并清理资源"""
        logger.info("开始停止扫描任务...")
        self.stop_scan()
        
        # 终止所有子进程
        logger.debug(f"正在终止 {len(self._active_processes)} 个子进程")
        for pid in list(self._active_processes):
            try:
                proc = psutil.Process(pid)
                if proc.is_running():
                    try:
                        logger.debug(f"终止进程 PID: {pid}")
                        proc.terminate()
                        await asyncio.sleep(0.1)
                        if proc.is_running():
                            logger.debug(f"强制终止进程 PID: {pid}")
                            proc.kill()
                    except Exception as e:
                        logger.warning(f"终止进程时出错 PID: {pid}, 错误: {str(e)}")
            except psutil.NoSuchProcess:
                logger.debug(f"进程已不存在 PID: {pid}")
        self._active_processes.clear()
        
        # 取消所有异步任务
        logger.debug(f"正在取消 {len(self._active_tasks)} 个异步任务")
        tasks = list(self._active_tasks)
        for task in tasks:
            if not task.done():
                logger.debug(f"取消任务: {task}")
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    logger.debug("任务已取消")
                except Exception as e:
                    logger.warning(f"取消任务时出错: {str(e)}", exc_info=True)
        self._active_tasks.clear()
        
        # 关闭线程池
        if self._executor:
            try:
                logger.debug("正在关闭线程池...")
                self._executor.shutdown(wait=False, cancel_futures=True)
                logger.debug("线程池已关闭")
            except Exception as e:
                logger.warning(f"关闭线程池时出错: {str(e)}")
            self._executor = None
        
        # 确保状态重置
        self._is_scanning = False

    async def cleanup(self) -> None:
        """清理资源"""
        return await self._stop_scanning()
