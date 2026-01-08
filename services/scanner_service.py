import threading
import queue
import time
from typing import List, Dict
from services.url_parser_service import URLRangeParser
from core.log_manager import global_logger
from models.channel_model import ChannelListModel
from PyQt6 import QtCore
from PyQt6.QtCore import pyqtSignal, QObject
from models.channel_mappings import extract_channel_name_from_url
from utils.scan_state_manager import get_scan_state_manager, ScanStateContext


class ScannerController(QObject):
    """扫描控制器，管理多线程扫描过程"""

    # 定义信号
    progress_updated = pyqtSignal(int, int)  # 当前进度, 总数
    channel_found = pyqtSignal(dict)  # 有效的频道信息
    scan_completed = pyqtSignal()
    stats_updated = pyqtSignal(dict)  # 统计信息

    # 在类定义中声明信号
    channel_validated = pyqtSignal(int, bool, int, str)

    def __init__(self, model: ChannelListModel, main_window=None) -> None:
        super().__init__()
        self.logger = global_logger
        self.model = model
        self.main_window = main_window
        self.url_parser = URLRangeParser()
        self.is_validating = False
        self.stats_lock = threading.Lock()
        self.scan_queue = queue.Queue()  # 扫描专用队列
        self.validation_queue = queue.Queue()  # 验证专用队列
        self.stop_event = threading.Event()
        self.workers: List[threading.Thread] = []
        self.timeout = 10  # 默认超时时间
        self.channel_counter = 0
        self.counter_lock = threading.Lock()
        self._batch_timer = None  # 不再使用批量定时器
        self.stats: Dict[str, any] = {
            'total': 0,
            'valid': 0,
            'invalid': 0,
            'start_time': 0,
            'elapsed': 0
        }
        # 记录无效的URL，用于重试扫描
        self.invalid_urls = []
        self.invalid_urls_lock = threading.Lock()

        # 扫描状态管理器
        self.scan_state_manager = get_scan_state_manager()
        self.scan_id = 'main_scan'

    def _force_ui_refresh(self):
        """强制刷新UI"""
        try:
            if hasattr(self.model, 'update_view'):
                self.model.update_view()
            elif hasattr(self.model, 'layoutChanged'):
                self.model.layoutChanged.emit()
        except Exception:
            pass

    def _worker(self) -> None:
        """工作线程函数"""
        while not self.stop_event.is_set():
            try:
                url = self.scan_queue.get_nowait()
            except queue.Empty:
                break

            try:
                result = self._check_channel(url)
                valid = result['valid']
                latency = result['latency']
                resolution = result.get('resolution', '')

                # 构建频道信息
                channel_info = self._build_channel_info(
                    url, valid, latency, resolution, result
                    )
                if not channel_info:
                    # 即使构建失败，也要确保统计信息更新
                    with self.stats_lock:
                        self.stats['invalid'] += 1

                        current = self.stats['valid'] + self.stats['invalid']
                        total = self.stats['total']

                        # 立即更新进度，确保状态栏进度条正常显示
                        import functools
                        QtCore.QTimer.singleShot(
                            0, functools.partial(
                                self.progress_updated.emit, current, total
                                ),
                            )
                    continue

                # 确保频道信息包含必要字段
                channel_info.setdefault(
                    'name', channel_info.get(
                        'raw_name', extract_channel_name_from_url(url)
                        )
                    )

                # 只添加有效频道到列表
                if valid:
                    # 使用 functools.partial 确保频道信息正确传递
                    import functools
                    QtCore.QTimer.singleShot(
                        0, functools.partial(
                            self._handle_channel_add, channel_info.copy()
                            )
                    )

                # 统计信息更新 - 确保无论有效还是无效都更新
                with self.stats_lock:
                    if valid:
                        self.stats['valid'] += 1
                    else:
                        self.stats['invalid'] += 1
                        # 记录无效URL
                        with self.invalid_urls_lock:
                            self.invalid_urls.append(url)

                        # 更新扫描状态管理器中的无效URL
                        self.scan_state_manager.add_invalid_url(self.scan_id, url)

                    current = self.stats['valid'] + self.stats['invalid']
                    total = self.stats['total']

                if total <= 0:
                    # 使用一个合理的估计值，避免除零错误
                    estimated_total = 100
                    total = estimated_total

                    # 发送进度更新信号
                    import functools
                    QtCore.QTimer.singleShot(
                        0, functools.partial(
                            self.progress_updated.emit, current, total
                        )
                    )

            except Exception:
                # 即使出现异常，也要确保统计信息更新
                with self.stats_lock:
                    self.stats['invalid'] += 1

                    current = self.stats['valid'] + self.stats['invalid']
                    total = self.stats['total']

                    if total <= 0:
                        # 使用一个合理的估计值，避免除零错误
                        estimated_total = 100
                        total = estimated_total

                    # 发送进度更新信号
                    import functools
                    QtCore.QTimer.singleShot(
                        0, functools.partial(
                            self.progress_updated.emit, current, total
                        )
                    )

                # 继续处理下一个URL，不中断线程
                continue

        # 工作线程结束时强制刷新UI
        QtCore.QTimer.singleShot(0, self._force_ui_refresh)

        # 确保发送最终的进度更新
        with self.stats_lock:
            current = self.stats['valid'] + self.stats['invalid']
            total = self.stats['total']
            if current < total:
                # 使用QTimer在主线程中安全地更新进度
                import functools
                QtCore.QTimer.singleShot(
                    0, functools.partial(
                        self.progress_updated.emit, total, total
                    )
                )

        # 注意：不再在工作线程中触发扫描完成信号
        # 扫描完成信号由 _update_stats 线程统一处理，避免重复触发

    def _process_valid_channel(self, channel_info: dict):
        """处理有效频道"""
        self.model.add_channel(channel_info)

    def _add_channel_and_refresh(self, channel_info: dict):
        """添加频道并强制刷新UI"""
        # 扫描生成的频道，不是从文件加载的
        self.model.add_channel(channel_info, is_from_file=False)
        # 强制刷新UI
        self._force_ui_refresh()

    def _handle_channel_add(self, channel_info: dict):
        """处理频道添加"""
        self._add_channel_and_refresh(channel_info)

        # 添加频道后强制触发列宽调整
        if hasattr(self.model, 'parent') and self.model.parent():
            view = self.model.parent()
            if hasattr(view, 'resizeColumnsToContents'):
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(0, view.resizeColumnsToContents)

    def _build_channel_info(
        self, url: str, valid: bool, latency: int,
        resolution: str, result: dict
    ) -> dict:
        """构建基本的频道信息字典 - 简化版本，详细信息异步获取"""
        from models.channel_mappings import extract_channel_name_from_url

        try:
            # 直接从URL提取频道名，不再尝试从媒体信息获取原始名称
            channel_name = extract_channel_name_from_url(url)

            # 构建基本频道信息（不包含详细信息）
            channel_info = {
                'url': url,
                'name': channel_name,  # 使用从URL提取的名称
                'raw_name': channel_name,
                'valid': valid,
                'latency': latency,
                'resolution': '',  # 初始为空，异步获取
                'status': '有效' if valid else '无效',
                'group': '未分类',  # 初始分组
                'logo_url': None,
                'needs_details': valid  # 标记需要获取详细信息
            }

            # 如果频道有效，启动异步获取详细信息
            if valid:
                self._start_async_details_fetch(channel_info.copy())

            return channel_info

        except Exception as e:
            # 返回基本的频道信息，即使构建失败
            return {
                'url': url,
                'name': extract_channel_name_from_url(url),
                'raw_name': extract_channel_name_from_url(url),
                'valid': valid,
                'latency': latency,
                'resolution': '',
                'status': '有效' if valid else '无效',
                'group': '未分类',
                'logo_url': None,
                'error': str(e),
                'needs_details': False
            }

    def _start_async_details_fetch(self, channel_info: dict):
        """启动异步获取频道详细信息"""
        # 创建线程来获取详细信息
        thread = threading.Thread(
            target=self._fetch_channel_details,
            args=(channel_info,),
            name=f"DetailsFetcher-{channel_info['url'][-20:]}",
            daemon=True
        )
        thread.start()

    def _fetch_channel_details(self, channel_info: dict):
        """获取频道详细信息（分辨率、编码、映射等）"""
        max_retries = 3
        retry_delays = [1, 2, 3]  # 重试延迟（秒）

        for retry_count in range(max_retries):
            try:
                url = channel_info['url']

                # 首先获取映射信息 - 使用从URL提取的名称进行映射
                from models.channel_mappings import mapping_manager
                channel_info_for_fingerprint = {
                    'service_name': channel_info['raw_name'],  # 使用从URL提取的名称
                    'resolution': '',  # 初始为空，优先从映射获取
                    'codec': '',
                    'bitrate': ''
                }

                mapped_info = mapping_manager.get_channel_info(
                    channel_info['raw_name'],  # 使用从URL提取的名称
                    url,
                    channel_info_for_fingerprint
                )

                # 更新频道信息
                updated_info = channel_info.copy()

                # 优先使用映射中的分辨率
                if mapped_info and mapped_info.get('resolution'):
                    updated_info['resolution'] = mapped_info['resolution']
                else:
                    # 如果映射中没有分辨率，再使用ffprobe获取
                    from services.validator_service import StreamValidator
                    validator = StreamValidator(self.main_window)
                    probe_result = validator._run_ffprobe(url, timeout=10)
                    
                    if probe_result.get('resolution'):
                        updated_info['resolution'] = probe_result['resolution']
                    if probe_result.get('codec'):
                        updated_info['codec'] = probe_result['codec']
                    if probe_result.get('bitrate'):
                        updated_info['bitrate'] = probe_result['bitrate']

                # 更新其他映射信息
                if mapped_info:
                    standard_name = mapped_info.get(
                        'standard_name', updated_info['raw_name']
                    )
                    updated_info['name'] = standard_name
                    updated_info['group'] = mapped_info.get(
                        'group_name', '未分类'
                    )

                    # 确保logo_url是有效的URL字符串，不是None或空字符串
                    logo_url = mapped_info.get('logo_url')
                    if logo_url and isinstance(logo_url, str) and logo_url.strip():
                        updated_info['logo_url'] = logo_url.strip()
                    else:
                        updated_info['logo_url'] = None

                    # 更新其他映射字段
                    if mapped_info.get('tvg_id'):
                        updated_info['tvg_id'] = mapped_info['tvg_id']
                    if mapped_info.get('tvg_chno'):
                        updated_info['tvg_chno'] = mapped_info['tvg_chno']
                    if mapped_info.get('tvg_shift'):
                        updated_info['tvg_shift'] = mapped_info['tvg_shift']
                    if mapped_info.get('catchup'):
                        updated_info['catchup'] = mapped_info['catchup']
                    if mapped_info.get('catchup_days'):
                        updated_info['catchup_days'] = mapped_info['catchup_days']
                    if mapped_info.get('catchup_source'):
                        updated_info['catchup_source'] = mapped_info['catchup_source']

                    updated_info['fingerprint'] = (
                        mapping_manager.create_channel_fingerprint(
                            url, channel_info_for_fingerprint
                        )
                    )

                # 确保所有必要的字段都存在
                updated_info.setdefault('resolution', '')
                updated_info.setdefault('group', '未分类')
                updated_info.setdefault('logo_url', None)
                updated_info.setdefault('status', '有效')

                # 标记详细信息已获取
                updated_info['needs_details'] = False

                # 在主线程中更新频道信息 - 使用functools.partial避免lambda作用域问题
                import functools
                QtCore.QTimer.singleShot(
                    0, functools.partial(self._update_channel_details, updated_info)
                )

                # 成功获取，跳出重试循环
                return

            except Exception as e:
                self.logger.warning(
                    f"获取频道详细信息失败 (重试 {retry_count + 1}/{max_retries}): {e}"
                )
                if retry_count < max_retries - 1:
                    time.sleep(retry_delays[retry_count])
                else:
                    # 即使失败，也标记为不需要再获取
                    channel_info['needs_details'] = False
                    # 确保频道信息有必要的字段
                    channel_info.setdefault('resolution', '')
                    channel_info.setdefault('group', '未分类')
                    channel_info.setdefault('logo_url', None)
                    # 使用functools.partial避免lambda作用域问题
                    import functools
                    QtCore.QTimer.singleShot(
                        0, functools.partial(self._update_channel_details, channel_info)
                    )

    def _update_channel_details(self, channel_info: dict):
        """更新频道详细信息"""
        try:
            # 使用现有的update_channel_by_url方法更新频道信息
            url = channel_info.get('url')
            if url:
                success = self.model.update_channel_by_url(url, channel_info)
                if not success:
                    pass
            else:
                pass

            # 刷新UI
            self._force_ui_refresh()

        except Exception:
            pass

    def _check_channel(
        self, url: str, raw_channel_name: str = None
    ) -> Dict[str, any]:
        """检查频道有效性"""
        from services.validator_service import StreamValidator
        # 使用主窗口的语言管理器（如果可用）
        validator = StreamValidator(self.main_window)
        return validator.validate_stream(
            url,
            raw_channel_name=raw_channel_name,
            timeout=self.timeout
        )

    def _fill_queue(self):
        """动态填充扫描队列"""
        try:
            for batch in self.url_generator:
                if self.stop_event.is_set():
                    break

                with self.stats_lock:
                    self.stats['total'] += len(batch)

                for url in batch:
                    if self.stop_event.is_set():
                        break
                    self.scan_queue.put(url)
                    # 记录所有扫描的URL（用于重试扫描）
                    self._all_scanned_urls.append(url)

                # 保持队列适度填充，避免内存占用过高
                while self.scan_queue.qsize() > 10000 and not self.stop_event.is_set():
                    time.sleep(0.1)

        except Exception:
            pass
        finally:
            pass

    def is_scanning(self):
        """检查是否正在扫描"""
        return len(self.workers) > 0 and not self.stop_event.is_set()

    def start_scan(
        self, base_url: str, thread_count: int = 10, timeout: int = 10,
        user_agent: str = None, referer: str = None
    ) -> None:
        """开始扫描 - 优化版本"""
        # 确保停止之前的扫描
        self.stop_scan()
        self.stop_event.clear()

        # 使用扫描状态上下文管理器
        with ScanStateContext(self.scan_id, self):
            self._start_scan_internal(base_url, thread_count, timeout, user_agent, referer)

    def _start_scan_internal(
        self, base_url: str, thread_count: int = 10, timeout: int = 10,
        user_agent: str = None, referer: str = None
    ) -> None:
        """内部扫描启动方法"""

        # 保存超时时间和线程数到实例变量
        self.timeout = timeout

        from services.validator_service import StreamValidator
        StreamValidator.timeout = timeout
        if user_agent:
            StreamValidator.headers['User-Agent'] = user_agent
        if referer:
            StreamValidator.headers['Referer'] = referer

        # 初始化统计信息
        self.stats = {
            'total': 0,  # 初始为0，由填充线程动态更新
            'valid': 0,
            'invalid': 0,
            'start_time': time.time(),
            'elapsed': 0
        }

        # 更新扫描状态管理器
        self.scan_state_manager.update_scan_state(self.scan_id, {
            'is_scanning': True,
            'scanner': self
        })
        self.scan_state_manager.update_stats(self.scan_id, self.stats)

        # 初始化队列和生成器
        self.scan_queue = queue.Queue()
        self.url_generator = self.url_parser.parse_url(base_url)

        # 记录所有扫描的URL（用于重试扫描）
        self._all_scanned_urls = []

        # 预填充第一批URL
        try:
            first_batch = next(self.url_generator)
            for url in first_batch:
                self.scan_queue.put(url)
                self._all_scanned_urls.append(url)
            self.stats['total'] = len(first_batch)
        except StopIteration:
            self.logger.warning("没有可扫描的URL")
            return

        # 启动队列填充线程
        self.filler_thread = threading.Thread(
            target=self._fill_queue,
            name="QueueFiller",
            daemon=True
        )
        self.filler_thread.start()
        optimal_threads = thread_count if thread_count > 0 else 1  # 至少1个线程

        # 使用优化后的线程数
        self.workers = []
        for i in range(optimal_threads):
            worker = threading.Thread(
                target=self._worker,
                name=f"ScannerWorker-{i}",
                daemon=True
            )
            worker.start()
            self.workers.append(worker)

        stats_thread = threading.Thread(
            target=self._update_stats,
            name="StatsUpdater",
            daemon=True
        )
        stats_thread.start()

        # 扫描开始时发送进度更新信号
        QtCore.QTimer.singleShot(0, lambda: self.progress_updated.emit(0, 1))

    def start_scan_from_urls(
        self, urls: list, thread_count: int = 10, timeout: int = 10,
        user_agent: str = None, referer: str = None
    ):
        """从URL列表开始扫描（用于重试扫描）"""
        # 确保停止之前的扫描
        self.stop_scan()
        self.stop_event.clear()

        # 清空无效URL列表，避免累积
        with self.invalid_urls_lock:
            self.invalid_urls.clear()

        # 清空扫描状态管理器中的无效URL
        self.scan_state_manager.clear_invalid_urls(self.scan_id)

        # 使用扫描状态上下文管理器
        with ScanStateContext(self.scan_id, self):
            self._start_scan_from_urls_internal(urls, thread_count, timeout, user_agent, referer)

    def _start_scan_from_urls_internal(
        self, urls: list, thread_count: int = 10, timeout: int = 10,
        user_agent: str = None, referer: str = None
    ):
        """内部从URL列表开始扫描方法"""

        from services.validator_service import StreamValidator
        StreamValidator.timeout = timeout
        if user_agent:
            StreamValidator.headers['User-Agent'] = user_agent
        if referer:
            StreamValidator.headers['Referer'] = referer

        # 初始化统计信息
        self.stats = {
            'total': len(urls),
            'valid': 0,
            'invalid': 0,
            'start_time': time.time(),
            'elapsed': 0
        }

        # 更新扫描状态管理器
        self.scan_state_manager.update_scan_state(self.scan_id, {
            'is_scanning': True,
            'scanner': self
        })
        self.scan_state_manager.update_stats(self.scan_id, self.stats)

        # 初始化队列
        self.scan_queue = queue.Queue()

        # 填充队列
        for url in urls:
            self.scan_queue.put(url)

        # 使用用户设置的线程数
        self.workers = []
        for i in range(thread_count):
            worker = threading.Thread(
                target=self._worker,
                name=f"RetryScannerWorker-{i}",
                daemon=True
            )
            worker.start()
            self.workers.append(worker)

        stats_thread = threading.Thread(
            target=self._update_stats,
            name="RetryStatsUpdater",
            daemon=True
        )
        stats_thread.start()

    def stop_scan(self):
        """停止扫描 - 快速响应版本，避免程序假死"""
        # 设置停止事件，让所有工作线程知道应该停止
        self.stop_event.set()

        # 更新扫描状态管理器
        self.scan_state_manager.update_scan_state(self.scan_id, {
            'is_scanning': False
        })

        # 立即清空所有队列，避免新任务被处理
        self._clear_all_queues()

        # 立即终止所有FFmpeg/VLC进程
        self._terminate_all_processes()

        # 快速清理工作线程（不等待太长时间）
        self._cleanup_workers_fast()

        # 清理其他资源
        self._cleanup_other_resources()

    def _clear_all_queues(self):
        """清空所有队列"""
        # 清空扫描队列
        while not self.scan_queue.empty():
            try:
                self.scan_queue.get_nowait()
            except queue.Empty:
                break

        # 清空验证队列
        while not self.validation_queue.empty():
            try:
                self.validation_queue.get_nowait()
            except queue.Empty:
                break

        # 如果有队列填充线程，设置标志让它停止
        if hasattr(self, 'filler_thread') and self.filler_thread and self.filler_thread.is_alive():
            pass

    def _terminate_all_processes(self):
        """终止所有FFmpeg/VLC进程"""
        try:
            from services.validator_service import StreamValidator
            StreamValidator.terminate_all()
        except Exception:
            pass

    def _cleanup_workers_fast(self):
        """快速清理工作线程"""
        if not self.workers:
            return

        # 记录当前存活的线程
        alive_workers = [w for w in self.workers if w.is_alive()]

        if not alive_workers:
            self.workers = []
            return

        # 第一次尝试：快速等待（0.5秒）
        for worker in alive_workers:
            worker.join(timeout=0.5)

        # 检查哪些线程仍然存活
        still_alive = [w for w in alive_workers if w.is_alive()]

        if still_alive:
            # 记录警告但不阻塞UI
            self.logger.warning(f"{len(still_alive)} 个工作线程仍在运行，将在后台清理")

            # 启动后台线程来等待这些线程
            cleanup_thread = threading.Thread(
                target=self._background_cleanup,
                args=(still_alive,),
                name="BackgroundCleanup",
                daemon=True
            )
            cleanup_thread.start()

        # 清空工作线程列表，让扫描按钮可以立即响应
        self.workers = []

    def _background_cleanup(self, workers):
        """在后台清理工作线程"""
        try:
            # 等待最多3秒
            for worker in workers:
                worker.join(timeout=3.0)

            # 检查是否还有存活的线程
            still_alive = [w for w in workers if w.is_alive()]
            if still_alive:
                self.logger.warning(f"后台清理后仍有 {len(still_alive)} 个线程存活")
        except Exception:
            pass

    def _cleanup_other_resources(self):
        """清理其他资源"""
        # 停止批量更新定时器
        if hasattr(self, '_batch_timer') and self._batch_timer and self._batch_timer.isActive():
            self._batch_timer.stop()

        # 清理统计更新线程
        if hasattr(self, 'stats_thread') and self.stats_thread and self.stats_thread.is_alive():
            self.stats_thread.join(timeout=0.5)

        # 强制垃圾回收
        import gc
        gc.collect()

    def start_validation(self, model, threads, timeout, user_agent=None, referer=None):
        """开始有效性验证"""
        self.is_validating = True
        self.stop_event.clear()
        self.timeout = timeout

        # 更新扫描状态管理器
        self.scan_state_manager.update_scan_state(self.scan_id, {
            'is_validating': True
        })

        # 设置验证器的headers，与扫描逻辑相同
        from services.validator_service import StreamValidator
        StreamValidator.timeout = timeout
        if user_agent:
            StreamValidator.headers['User-Agent'] = user_agent
        if referer:
            StreamValidator.headers['Referer'] = referer

        self.stats = {
            'total': model.rowCount(),
            'valid': 0,
            'invalid': 0,
            'start_time': time.time(),
            'elapsed': 0
        }

        for i in range(model.rowCount()):
            channel = model.get_channel(i)
            self.validation_queue.put((channel['url'], i))

        self.workers = []
        for i in range(threads):
            worker = threading.Thread(
                target=self._validation_worker,
                name=f"ValidationWorker-{i}",
                daemon=True
            )
            worker.start()
            self.workers.append(worker)

        stats_thread = threading.Thread(
            target=self._update_stats,
            name="ValidationStatsUpdater",
            daemon=True
        )
        stats_thread.start()

        # 验证开始时发送进度更新信号
        QtCore.QTimer.singleShot(0, lambda: self.progress_updated.emit(0, 1))

    def stop_validation(self):
        """停止有效性验证"""
        self.stop_event.set()
        self.is_validating = False

        # 更新扫描状态管理器
        self.scan_state_manager.update_scan_state(self.scan_id, {
            'is_validating': False
        })

        # 清空任务队列
        while not self.validation_queue.empty():
            try:
                self.validation_queue.get_nowait()
            except queue.Empty:
                break

        # 终止所有验证进程
        from services.validator_service import StreamValidator
        StreamValidator.terminate_all()

        # 立即终止工作线程
        for worker in self.workers:
            if worker.is_alive():
                worker.join(timeout=0.1)

        self.workers = []
        self.worker_queue = queue.Queue()
        # 不再记录验证停止日志，避免控制台输出

    def _validation_worker(self):
        """有效性验证工作线程 - 修改为与扫描逻辑相同"""
        while not self.stop_event.is_set():
            try:
                url, index = self.validation_queue.get_nowait()
                result = self._check_channel(url)
                valid = result['valid']
                latency = result['latency']
                resolution = result.get('resolution', '')

                # 使用QTimer在主线程中安全地更新模型状态 - 使用functools.partial避免lambda作用域问题
                import functools
                QtCore.QTimer.singleShot(0, functools.partial(self.model.set_channel_valid, url, valid))

                # 每10次更新批量刷新一次视图
                if index % 10 == 0:
                    QtCore.QTimer.singleShot(0, self.model.update_view)

                # 使用QTimer在主线程中安全地发射信号 - 使用functools.partial避免lambda作用域问题
                QtCore.QTimer.singleShot(
                    0, functools.partial(
                        self.channel_validated.emit, index, valid,
                        latency, resolution
                    )
                )

                with self.stats_lock:
                    # 统计所有被检测的频道，无论是否映射成功
                    if valid:  # 使用valid字段判断有效性
                        self.stats['valid'] += 1
                    else:
                        self.stats['invalid'] += 1

                    # 发送进度更新信号
                    current = self.stats['valid'] + self.stats['invalid']
                    total = self.stats['total']

                    # 即使total为0也发送进度更新信号，但使用默认值
                    if total <= 0:
                        total = 1  # 避免除零错误

                    # 使用QTimer在主线程中安全地更新进度
                    QtCore.QTimer.singleShot(
                        0, functools.partial(
                            self.progress_updated.emit, current, total
                        )
                    )
            except queue.Empty:
                break
            except Exception as e:
                self.logger.error(f"验证线程错误: {e}", exc_info=True)
                continue

    def _update_stats(self):
        """更新统计信息线程"""
        try:
            # 简化逻辑：只要没有停止事件就持续更新统计信息
            while not self.stop_event.is_set():
                try:
                    # 使用锁确保获取最新的统计信息
                    with self.stats_lock:
                        self.stats['elapsed'] = time.time() - self.stats['start_time']

                        # 更新扫描状态管理器中的统计信息
                        self.scan_state_manager.update_stats(self.scan_id, self.stats)

                        # 直接调用主窗口的更新方法，避免信号连接问题
                        if self.main_window and hasattr(self.main_window, '_update_stats_display'):
                            # 修复：使用functools.partial确保参数正确传递
                            import functools
                            stats_copy = self.stats.copy()
                            is_validating = self.is_validating
                            QtCore.QTimer.singleShot(0, functools.partial(
                                self.main_window._update_stats_display,
                                {
                                    'stats': stats_copy,
                                    'is_validation': is_validating
                                }
                            ))
                        else:
                            # 备用方案：仍然使用信号
                            QtCore.QTimer.singleShot(0, lambda: self.stats_updated.emit({
                                'stats': self.stats.copy(),
                                'is_validation': self.is_validating
                            }))

                    # 检查扫描是否完成：所有工作线程都完成且队列为空
                    workers_alive = (
                        any(w.is_alive() for w in self.workers)
                        if self.workers else False
                    )
                    queue_empty = (
                        self.scan_queue.empty()
                        if hasattr(self, 'scan_queue') else True
                    )
                    validation_queue_empty = (
                        self.validation_queue.empty()
                        if hasattr(self, 'validation_queue') else True
                    )

                    # 如果所有工作线程都完成且队列为空，则扫描完成
                    if not workers_alive and queue_empty and validation_queue_empty:
                        break

                    time.sleep(0.5)  # 恢复到合理的更新频率，避免UI假死
                except RuntimeError:
                    break

            # 检查扫描是否被用户停止
            if self.stop_event.is_set():
                self.logger.info("扫描被用户停止")
            else:
                # 整合日志：扫描完成，触发重试扫描
                self.logger.info(
                    f"扫描完成: 总数={self.stats['total']}, "
                    f"有效={self.stats['valid']}, "
                    f"无效={self.stats['invalid']}"
                )

                # 直接调用主窗口的方法
                try:
                    if self.main_window and hasattr(self.main_window, '_on_scan_completed'):
                        callback = self.main_window._on_scan_completed
                        QtCore.QTimer.singleShot(0, callback)
                    else:
                        self.logger.warning("无法调用主窗口方法")
                except Exception as e:
                    self.logger.error(f"调用主窗口方法失败: {e}")
        finally:
            # 等待所有工作线程完成，确保最终的统计信息被发送
            for worker in self.workers:
                if worker.is_alive():
                    worker.join(timeout=1.0)

            # 发送最终的统计信息更新
            try:
                with self.stats_lock:
                    self.stats['elapsed'] = time.time() - self.stats['start_time']

                    if self.main_window and hasattr(self.main_window, '_update_stats_display'):
                        import functools
                        stats_copy = self.stats.copy()
                        is_validating = self.is_validating
                        QtCore.QTimer.singleShot(0, functools.partial(
                            self.main_window._update_stats_display,
                            {
                                'stats': stats_copy,
                                'is_validation': is_validating
                            }
                        ))
                    else:
                        QtCore.QTimer.singleShot(0, lambda: self.stats_updated.emit({
                            'stats': self.stats.copy(),
                            'is_validation': self.is_validating
                        }))
            except Exception as e:
                self.logger.error(f"发送最终统计信息失败: {e}")
