import asyncio
import psutil
import time
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor
from PyQt6 import QtWidgets
from PyQt6.QtCore import QObject, pyqtSignal
from async_utils import AsyncWorker, asyncSlot
from playlist_io import PlaylistHandler
from utils import setup_logger, parse_ip_range
from ffprobe_utils import FFProbeHelper

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
    
    def __init__(self, config_manager):
        super().__init__()
        logger.info("初始化StreamScanner")
        self._is_scanning = False
        self._scan_lock = asyncio.Lock()
        self.playlist = PlaylistHandler()
        self._executor = None
        self._ffprobe_available = False
        self._user_agent = None
        self._referer = None
        self._active_tasks = set()
        self._active_processes = set()
        self._ffprobe_checked = False
        
        if not config_manager:
            raise ValueError("config_manager参数不能为空")
            
        # 从配置管理器获取扫描器配置
        scanner_prefs = config_manager.get_scanner_prefs()
        self._timeout = scanner_prefs['timeout']
        self._thread_count = scanner_prefs['thread_count']
        
        # 参数验证
        if self._timeout <= 0:
            logger.warning(f"无效超时时间{self._timeout}s，重置为10s")
            self._timeout = 10
            
        if self._thread_count <= 0:
            logger.warning(f"无效线程数{self._thread_count}，重置为10")
            self._thread_count = 10
            
        # 设置User-Agent和Referer
        self._user_agent = scanner_prefs['user_agent']
        self._referer = scanner_prefs['referer']
            
        logger.debug(f"初始化完成: timeout={self._timeout}s, thread_count={self._thread_count}")
        
        self.ffprobe = FFProbeHelper()
        self.ffprobe.set_timeout(self._timeout)

    def set_timeout(self, timeout: int) -> None:
        logger.info(f"设置超时时间: {timeout}s")
        self._timeout = timeout
        self.ffprobe.set_timeout(timeout)

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
    async def toggle_scan(self, ip_pattern: str, timeout: int = None, thread_count: int = None) -> asyncio.Task:
        """切换扫描状态
        Args:
            ip_pattern: 扫描地址模式
            timeout: 超时时间(秒)
            thread_count: 线程数
        """
        logger.info(f"切换扫描状态, 当前状态: {'扫描中' if self._is_scanning else '空闲'}")
        if self._is_scanning:
            logger.info("正在停止扫描...")
            await self.stop_scan()
            self.scan_stopped.emit()
            logger.info("扫描已停止")
            return

        async with self._scan_lock:
            if self._is_scanning:
                logger.debug("扫描已在运行中，忽略重复启动")
                return

            try:
                # 应用传入参数
                if timeout is not None:
                    self.set_timeout(timeout)
                if thread_count is not None:
                    self.set_thread_count(thread_count)

                logger.info(f"开始扫描IP模式: {ip_pattern} (超时: {self._timeout}s, 线程: {self._thread_count})")
                self._is_scanning = True
                self.scan_started.emit(ip_pattern)
                # 确保线程数在合理范围内(1-50)
                actual_threads = max(1, min(self._thread_count, 50))
                self._executor = ThreadPoolExecutor(max_workers=actual_threads)
                logger.debug(f"实际使用的线程数: {thread_count}")
                self._active_tasks.clear()
                logger.debug(f"创建线程池，线程数: {self._thread_count}, 超时: {self._timeout}s")

                # 解析IP范围
                urls = list(parse_ip_range(ip_pattern))
                logger.debug(f"解析IP范围完成，生成URL数量: {len(urls)}")
                if not urls:
                    error_msg = "未生成任何扫描地址"
                    logger.error(error_msg)
                    self.error_occurred.emit(error_msg)
                    self._is_scanning = False
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
            
            # 根据线程数确定批次大小
            batch_size = self._thread_count
            for batch_start in range(0, total, batch_size):
                if not self._is_scanning:
                    logger.info("扫描被手动停止，中止处理")
                    break
                
                batch_end = min(batch_start + batch_size, total)
                batch = urls[batch_start:batch_end]
                
                # 并发处理当前批次
                results = await asyncio.gather(
                    *(self._probe_stream(url) for url in batch),
                    return_exceptions=True
                )
                
                # 处理结果
                for result in results:
                    if isinstance(result, Exception):
                        logger.error(f"扫描出错: {str(result)}")
                        invalid_count += 1
                        continue
                        
                    if result:
                        url, probe_result = result
                        if probe_result:
                            channel = {
                                'name': f"频道 {len(valid_channels) + 1}",
                                'url': url,
                                'width': probe_result.get('width', 0),
                                'height': probe_result.get('height', 0),
                                'latency': probe_result.get('latency', 0.0),
                                'valid': probe_result.get('valid', False)
                            }
                            valid_channels.append(channel)
                            self.channel_found.emit(channel)
                            logger.debug(f"发现有效频道: {url}, 分辨率: {probe_result.get('width')}x{probe_result.get('height')}")
                        else:
                            invalid_count += 1
                            logger.debug(f"无效URL: {url}")
                
                # 实时更新进度和状态
                progress = int(batch_end / total * 100)
                status = f"总频道: {total} | 有效: {len(valid_channels)} | 无效: {invalid_count}"
                self.progress_updated.emit(progress, f"正在扫描批次 {batch_start+1}-{batch_end}")
                self.stats_updated.emit(status)
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

    async def _check_ffprobe(self) -> bool:
        """检查ffprobe是否可用"""
        if self._ffprobe_checked:
            return self._ffprobe_available
            
        try:
            self._ffprobe_available = await self.ffprobe.check_available()
            if not self._ffprobe_available:
                self.ffprobe_missing.emit()
            self._ffprobe_checked = True
            return self._ffprobe_available
        except Exception as e:
            logger.error(f"检查ffprobe失败: {str(e)}")
            self._ffprobe_available = False
            self.ffprobe_missing.emit()
            return False

    async def _probe_stream(self, url: str) -> Optional[Dict]:
        """探测单个流媒体"""
        try:
            if not self._is_scanning:
                logger.debug("扫描已停止，跳过探测")
                return None
                
            # 检查ffprobe可用性
            if not self._ffprobe_checked:
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
            valid, latency, width, height = asyncio.run(
                self.ffprobe.probe_stream(url)
            )
            if valid:
                return {
                    'codec': 'unknown',  # 新版本不再返回codec信息
                    'width': width,
                    'height': height,
                    'latency': latency,
                    'valid': True
                }
        except Exception as e:
            logger.error(f"探测流媒体失败: {url} - {str(e)}")
        return None

    async def stop_scan(self, force: bool = False) -> None:
        """停止扫描
        Args:
            force: 是否强制立即停止(会直接kill进程)
        """
        if not self._is_scanning:
            return
            
        self._is_scanning = False
        
        # 终止所有子进程
        logger.info(f"正在停止扫描(force={force})...")
        for pid in list(self._active_processes):
            try:
                proc = psutil.Process(pid)
                if force:
                    proc.kill()
                else:
                    proc.terminate()
                    await asyncio.sleep(0.1)
                    if proc.is_running():
                        proc.kill()
            except psutil.NoSuchProcess:
                pass
        self._active_processes.clear()
        
        # 取消所有异步任务
        for task in list(self._active_tasks):
            if not task.done():
                task.cancel()
        self._active_tasks.clear()
        
        # 关闭线程池
        if self._executor:
            self._executor.shutdown(wait=not force, cancel_futures=True)
            self._executor = None

    async def cleanup(self) -> None:
        """清理资源"""
        await self.stop_scan()

    def is_scanning(self) -> bool:
        """返回当前扫描状态"""
        return self._is_scanning
