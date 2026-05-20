import threading
import queue
import time
import functools
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any
from services.url_parser_service import URLRangeParser
from core.log_manager import global_logger
from models.channel_model import ChannelListModel
from PyQt6 import QtCore
from PyQt6.QtCore import pyqtSignal, QObject
from models.channel_mappings import extract_channel_name_from_url
from utils.scan_state_manager import get_scan_state_manager, ScanStateContext


def calculate_optimal_queue_size(thread_count: int = 10) -> int:
    """根据系统资源动态计算最优队列大小
    
    Args:
        thread_count: 扫描线程数
        
    Returns:
        int: 最优队列大小（URL数量）
        
    算法说明：
    - 基于可用内存：每个URL条目约占用1KB内存
    - 基于线程数：队列应至少能容纳线程数 * 10 的任务量
    - 限制范围：1000 - 50000，避免过大或过小
    """
    try:
        import psutil
        
        # 获取系统资源信息
        memory_mb = psutil.virtual_memory().available / (1024 * 1024)
        cpu_count = psutil.cpu_count() or 4
        
        # 基于内存计算（使用5%的可用内存，假设每条目1KB）
        memory_based = int(memory_mb * 0.05 * 1024)  # 转换为条目数
        
        # 基于线程数计算（每个线程至少有10个待处理任务）
        thread_based = thread_count * 10
        
        # 基于CPU核心数计算（每个核心至少1000个任务）
        cpu_based = cpu_count * 1000
        
        # 取三者中的最小值，确保不会过度占用资源
        optimal = min(memory_based, thread_based, cpu_based)
        
        # 限制在合理范围内
        optimal = max(1000, min(optimal, 50000))
        
        return optimal
        
    except ImportError:
        # psutil不可用，使用基于线程数的简单计算
        return max(1000, thread_count * 100)
    except Exception as e:
        # 出错时返回保守的默认值
        global_logger.debug(f"计算最优队列大小失败: {e}，使用默认值")
        return 10000


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
        self._optimal_queue_size = 10000  # 动态计算的队列大小（默认值）
        self.stats: Dict[str, Any] = {
            'total': 0,
            'valid': 0,
            'invalid': 0,
            'start_time': 0,
            'elapsed': 0
        }
        # 记录无效的URL，用于重试扫描（委托给scan_state_manager）
        self._max_invalid_urls = 50000

        # 扫描状态管理器
        self.scan_state_manager = get_scan_state_manager()
        self.scan_id = 'main_scan'
        self._validator = None
        self._mapping_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="mapper")
        self._ui_batch_timer = None
        self._ui_batch_lock = threading.Lock()

    def _force_ui_refresh(self):
        try:
            if hasattr(self.model, 'update_view'):
                self.model.update_view()
            elif hasattr(self.model, 'layoutChanged'):
                self.model.layoutChanged.emit()
        except Exception as e:
            self.logger.debug(f"UI刷新失败: {e}")

    @staticmethod
    def _run_on_main(func, *args):
        QtCore.QTimer.singleShot(0, functools.partial(func, *args))

    def _worker(self) -> None:
        """工作线程函数"""
        while not self.stop_event.is_set():
            try:
                url = self.scan_queue.get(timeout=0.5)
            except queue.Empty:
                if hasattr(self, 'filler_thread') and not self.filler_thread.is_alive():
                    try:
                        url = self.scan_queue.get_nowait()
                    except queue.Empty:
                        break
                else:
                    continue

            try:
                result = self._check_channel(url)
                valid = result['valid']
                latency = result['latency']
                resolution = result.get('resolution', '')

                try:
                    channel_info = self._build_channel_info(
                        url, valid, latency, resolution, result
                    )
                except Exception:
                    channel_info = {
                        'url': url,
                        'name': url.split('/')[-1] if '/' in url else url,
                        'raw_name': url.split('/')[-1] if '/' in url else url,
                        'valid': valid,
                        'latency': latency,
                        'resolution': resolution,
                        'status': '有效' if valid else '无效',
                        'group': '未分类',
                        'logo_url': None,
                        'needs_details': False
                    }

                if valid:
                    channel_info.setdefault(
                        'name', channel_info.get(
                            'raw_name', extract_channel_name_from_url(url)
                        )
                    )
                    self._run_on_main(self._handle_channel_add, channel_info.copy())
                    self._start_async_mapping_check(channel_info.copy())

                with self.stats_lock:
                    if valid:
                        self.stats['valid'] += 1
                    else:
                        self.stats['invalid'] += 1
                        error_type = result.get('error_type') or 'unknown_error'
                        if self.stats['invalid'] % 50 == 1:
                            self.logger.debug(f"扫描进度: 有效={self.stats['valid']}, 无效={self.stats['invalid']}, 最新错误类型={error_type}")
                        self.scan_state_manager.add_invalid_url(self.scan_id, url, error_type)

                    current = self.stats['valid'] + self.stats['invalid']
                    total = self.stats['total']

                if total <= 0:
                    total = 100
                    self._run_on_main(self.progress_updated.emit, current, total)

            except Exception as e:
                self.logger.debug(f"扫描URL异常: {url} - {e}")
                with self.stats_lock:
                    self.stats['invalid'] += 1
                    self.scan_state_manager.add_invalid_url(self.scan_id, url, 'scan_exception')
                    current = self.stats['valid'] + self.stats['invalid']
                    total = self.stats['total']
                    if total <= 0:
                        total = 100
                    self._run_on_main(self.progress_updated.emit, current, total)

                continue

        QtCore.QTimer.singleShot(0, self._force_ui_refresh)

        with self.stats_lock:
            current = self.stats['valid'] + self.stats['invalid']
            total = self.stats['total']
            if current < total:
                self._run_on_main(self.progress_updated.emit, total, total)

    def _handle_channel_add(self, channel_info: dict):
        """处理频道添加：添加到模型、批量刷新UI"""
        self.model.add_channel(channel_info, is_from_file=False)
        self._schedule_ui_refresh()

    def _schedule_ui_refresh(self):
        """批量延迟刷新UI，避免每个频道都刷新"""
        with self._ui_batch_lock:
            if self._ui_batch_timer is not None:
                return
            self._ui_batch_timer = True
        
        def _do_refresh():
            with self._ui_batch_lock:
                self._ui_batch_timer = None
            self._force_ui_refresh()
            if hasattr(self.model, 'parent') and self.model.parent():
                view = self.model.parent()
                if hasattr(view, 'resizeColumnsToContents'):
                    view.resizeColumnsToContents()
        
        QtCore.QTimer.singleShot(200, _do_refresh)

    def _build_channel_info(
        self, url: str, valid: bool, latency: int,
        resolution: str, result: dict
    ) -> dict:
        """构建基本的频道信息字典 - 优化版本，只在异步线程中检查映射"""
        from models.channel_mappings import extract_channel_name_from_url

        try:
            # 直接从URL提取频道名
            channel_name = extract_channel_name_from_url(url)

            # 重要修改：验证有效后不立即检查映射！
            # 只在异步线程中检查映射，避免重复日志和性能浪费

            # 注意：这里不再调用 mapping_manager.get_channel_info
            # 映射检查将在异步线程 _fetch_channel_details 中进行

            # 构建频道信息（只包含基本信息，不包含映射信息）
            channel_info = {
                'url': url,
                'name': channel_name,  # 使用URL提取的名称
                'raw_name': channel_name,
                'valid': valid,
                'latency': latency,
                'resolution': result.get('resolution', ''),
                'status': '有效' if valid else '无效',
                'group': '未分类',  # 默认分组，异步线程中更新
                'logo_url': None,   # 默认无logo，异步线程中更新
                'needs_details': False  # 重要：这里设为False，异步线程中再决定是否需要获取详情
            }

            # 注意：这里不启动异步获取详细信息
            # 异步获取将在 _start_async_mapping_check 方法中决定

            return channel_info

        except Exception as e:
            # 返回基本的频道信息，即使构建失败
            return {
                'url': url,
                'name': extract_channel_name_from_url(url),
                'raw_name': extract_channel_name_from_url(url),
                'valid': valid,
                'latency': latency,
                'resolution': result.get('resolution', ''),
                'status': '有效' if valid else '无效',
                'group': '未分类',
                'logo_url': None,
                'error': str(e),
                'needs_details': False
            }

    def _start_async_details_fetch(self, channel_info: dict):
        if self._mapping_executor is None:
            self._mapping_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="mapper")
        self._mapping_executor.submit(self._fetch_channel_details, channel_info)

    def _fetch_channel_details(self, channel_info: dict):
        """获取频道详细信息（仅用于有映射的频道）"""
        max_retries = 3
        retry_delays = [1, 2, 3]  # 重试延迟（秒）

        for retry_count in range(max_retries):
            try:
                url = channel_info['url']

                # 获取映射信息
                from models.channel_mappings import mapping_manager
                channel_info_for_fingerprint = {
                    'service_name': channel_info['raw_name'],
                    'resolution': channel_info.get('resolution', ''),
                    'codec': channel_info.get('codec', ''),
                    'bitrate': channel_info.get('bitrate', '')
                }

                mapped_info = mapping_manager.get_channel_info(
                    channel_info['raw_name'],
                    url,
                    channel_info_for_fingerprint
                )

                # 更新频道信息
                updated_info = channel_info.copy()

                # 更新映射信息
                if mapped_info:
                    # 更新标准名称
                    if mapped_info.get('standard_name'):
                        updated_info['name'] = mapped_info['standard_name']

                    # 更新分组
                    if mapped_info.get('group_name'):
                        updated_info['group'] = mapped_info['group_name']

                    # 更新logo
                    logo_url = mapped_info.get('logo_url')
                    if logo_url and isinstance(logo_url, str) and logo_url.strip():
                        updated_info['logo_url'] = logo_url.strip()

                    # 更新分辨率（从映射文件中获取）
                    if mapped_info.get('resolution'):
                        updated_info['resolution'] = mapped_info['resolution']

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

                    # 创建指纹
                    updated_info['fingerprint'] = mapping_manager.create_channel_fingerprint(
                        url, channel_info_for_fingerprint
                    )

                updated_info['needs_details'] = False

                self._run_on_main(self._update_channel_details, updated_info)
                return

            except Exception as e:
                self.logger.warning(
                    f"获取频道详细信息失败 (重试 {retry_count + 1}/{max_retries}): {e}"
                )
                if retry_count < max_retries - 1:
                    time.sleep(retry_delays[retry_count])
                else:
                    channel_info['needs_details'] = False
                    self._run_on_main(self._update_channel_details, channel_info)

    def _start_async_mapping_check(self, channel_info: dict):
        """启动异步映射检查 - 所有有效频道都检查映射"""
        # 检查映射功能是否开启
        from models.channel_mappings import mapping_manager
        if not mapping_manager.enable_mapping:
            return
        
        # 所有有效的频道都需要检查映射
        # 无论是什么格式的URL（IP地址、域名、其他格式）

        # 直接启动异步映射检查
        self._start_async_details_fetch(channel_info)

    def _update_channel_details(self, channel_info: dict):
        """更新频道详细信息"""
        try:
            url = channel_info.get('url')
            if url:
                success = self.model.update_channel_by_url(url, channel_info)
                if not success:
                    self.logger.debug(f"按URL更新频道失败: {url}")
            else:
                self.logger.debug("频道信息缺少URL，跳过更新")

            self._force_ui_refresh()

        except Exception as e:
            self.logger.debug(f"更新频道详细信息失败: {e}")

    def _check_channel(
        self, url: str, raw_channel_name: str | None = None
    ) -> Dict[str, Any]:
        if self._validator is None:
            from services.mpv_validator_service import MpvStreamValidator
            self._validator = MpvStreamValidator(self.main_window)
        return self._validator.validate_stream(
            url,
            raw_channel_name=raw_channel_name,
            timeout=self.timeout
        )

    def _fill_queue(self):
        """动态填充扫描队列 - 优化版，避免内存爆炸"""
        try:
            batch_count = 0
            skip_urls = getattr(self, '_skip_urls', set())
            for batch in self.url_generator:
                if self.stop_event.is_set():
                    break

                batch_count += 1

                if skip_urls:
                    filtered = [url for url in batch if url not in skip_urls]
                    skipped = len(batch) - len(filtered)
                    with self.stats_lock:
                        self.stats['total'] += len(filtered)
                    if skipped > 0:
                        self.logger.debug(f"追加扫描跳过 {skipped} 个已存在URL")
                else:
                    filtered = batch
                    with self.stats_lock:
                        self.stats['total'] += len(batch)

                for url in filtered:
                    if self.stop_event.is_set():
                        break
                    self.scan_queue.put(url)

                # 保持队列适度填充，避免内存占用过高（使用动态计算的队列大小）
                while self.scan_queue.qsize() > self._optimal_queue_size and not self.stop_event.is_set():
                    time.sleep(0.1)

                # 每处理100个批次后稍微休息，避免CPU占用过高
                if batch_count % 100 == 0:
                    time.sleep(0.01)

        except Exception as e:
            self.logger.debug(f"队列填充线程异常: {e}")
        finally:
            self.logger.debug(f"队列填充完成，共处理 {batch_count} 个批次")

    def is_scanning(self):
        """检查是否正在扫描"""
        return len(self.workers) > 0 and not self.stop_event.is_set()

    def start_scan(
        self, base_url: str, thread_count: int = 10, timeout: int = 10,
        user_agent: str | None = None, referer: str | None = None,
        skip_urls: set | None = None
    ) -> None:
        """开始扫描 - 优化版本"""
        # 确保停止之前的扫描
        self.stop_scan()
        self.stop_event.clear()

        self._skip_urls = skip_urls or set()

        # 注册扫描状态（不使用上下文管理器，因为扫描是异步的）
        self.scan_state_manager.register_scan(self.scan_id, self)
        self._start_scan_internal(base_url, thread_count, timeout, user_agent, referer)

    def _start_scan_internal(
        self, base_url: str, thread_count: int = 10, timeout: int = 10,
        user_agent: str | None = None, referer: str | None = None
    ) -> None:
        """内部扫描启动方法"""

        self.timeout = timeout

        self.scan_state_manager.clear_invalid_urls(self.scan_id)

        self._optimal_queue_size = calculate_optimal_queue_size(thread_count)
        self.logger.debug(f"动态计算最优队列大小: {self._optimal_queue_size}（线程数: {thread_count}）")

        from services.mpv_validator_service import MpvStreamValidator
        MpvStreamValidator.set_max_concurrent(thread_count)
        MpvStreamValidator.reset_terminating()
        if user_agent is not None:
            MpvStreamValidator.set_user_agent(user_agent)
        if referer is not None:
            MpvStreamValidator.set_referer(referer)

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

        # 启动队列填充线程（不再预填充，所有URL都由填充线程处理）
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

        self.stats_thread = threading.Thread(
            target=self._update_stats,
            name="StatsUpdater",
            daemon=True
        )
        self.stats_thread.start()

        # 扫描开始时发送进度更新信号
        QtCore.QTimer.singleShot(0, lambda: self.progress_updated.emit(0, 1))

    def start_scan_from_urls(
        self, urls: list, thread_count: int = 10, timeout: int = 10,
        user_agent: str | None = None, referer: str | None = None
    ):
        """从URL列表开始扫描（用于重试扫描）"""
        # 确保停止之前的扫描
        self.stop_scan()
        self.stop_event.clear()

        # 清空扫描状态管理器中的无效URL
        self.scan_state_manager.clear_invalid_urls(self.scan_id)

        # 注册扫描状态（不使用上下文管理器，因为扫描是异步的）
        self.scan_state_manager.register_scan(self.scan_id, self)
        self._start_scan_from_urls_internal(urls, thread_count, timeout, user_agent, referer)

    def _start_scan_from_urls_internal(
        self, urls: list, thread_count: int = 10, timeout: int = 10,
        user_agent: str | None = None, referer: str | None = None
    ):
        """内部从URL列表开始扫描方法"""

        self.timeout = timeout

        from services.mpv_validator_service import MpvStreamValidator
        MpvStreamValidator.set_max_concurrent(thread_count)
        MpvStreamValidator.reset_terminating()
        if user_agent is not None:
            MpvStreamValidator.set_user_agent(user_agent)
        if referer is not None:
            MpvStreamValidator.set_referer(referer)

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

        self.stats_thread = threading.Thread(
            target=self._update_stats,
            name="RetryStatsUpdater",
            daemon=True
        )
        self.stats_thread.start()

    def stop_scan(self):
        self.stop_event.set()

        self.scan_state_manager.update_scan_state(self.scan_id, {
            'is_scanning': False
        })

        # 安全停止：1.设置终止标志（让工作线程尽快退出）
        from services.mpv_validator_service import MpvStreamValidator
        MpvStreamValidator.set_terminating()

        # 2.清空队列
        self._clear_all_queues()

        # 3.等待工作线程退出（足够长timeout确保线程退出）
        for worker in self.workers:
            if worker.is_alive():
                worker.join(timeout=3.0)
        self.workers = []
        self.worker_queue = queue.Queue()

        # 4.线程退出后安全销毁mpv句柄
        MpvStreamValidator.destroy_all_handles()

        # 5.清理其他资源
        self._cleanup_other_resources()

        if hasattr(self, '_mapping_executor') and self._mapping_executor:
            try:
                self._mapping_executor.shutdown(wait=False)
            except Exception:
                pass
            self._mapping_executor = None

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
        try:
            from services.mpv_validator_service import MpvStreamValidator
            MpvStreamValidator.terminate_all()
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
        if hasattr(self, 'stats_thread') and self.stats_thread and self.stats_thread.is_alive():
            self.stats_thread.join(timeout=0.5)

        import gc
        gc.collect(0)

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
        from services.mpv_validator_service import MpvStreamValidator
        MpvStreamValidator.set_max_concurrent(threads)
        if user_agent is not None:
            MpvStreamValidator.set_user_agent(user_agent)
        if referer is not None:
            MpvStreamValidator.set_referer(referer)

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

        self.stats_thread = threading.Thread(
            target=self._update_stats,
            name="ValidationStatsUpdater",
            daemon=True
        )
        self.stats_thread.start()

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

        # 安全停止：1.设置终止标志
        from services.mpv_validator_service import MpvStreamValidator
        MpvStreamValidator.set_terminating()

        # 2.清空任务队列
        while not self.validation_queue.empty():
            try:
                self.validation_queue.get_nowait()
            except queue.Empty:
                break

        # 3.等待工作线程退出
        for worker in self.workers:
            if worker.is_alive():
                worker.join(timeout=1.0)

        self.workers = []
        self.worker_queue = queue.Queue()

        # 4.线程退出后安全销毁mpv句柄
        MpvStreamValidator.destroy_all_handles()

    def _validation_worker(self):
        while not self.stop_event.is_set():
            try:
                try:
                    url, index = self.validation_queue.get(timeout=0.5)
                except queue.Empty:
                    break

                result = self._check_channel(url)
                valid = result['valid']
                latency = result['latency']
                resolution = result.get('resolution', '')

                self._run_on_main(self.model.set_channel_valid, url, valid)

                if index % 10 == 0:
                    QtCore.QTimer.singleShot(0, self.model.update_view)

                self._run_on_main(self.channel_validated.emit, index, valid, latency, resolution)

                with self.stats_lock:
                    if valid:
                        self.stats['valid'] += 1
                    else:
                        self.stats['invalid'] += 1

                    current = self.stats['valid'] + self.stats['invalid']
                    total = self.stats['total']
                    if total <= 0:
                        total = 1

                    self._run_on_main(self.progress_updated.emit, current, total)
            except queue.Empty:
                break
            except Exception as e:
                self.logger.error(f"验证线程错误: {e}", exc_info=True)
                continue

    def _update_stats(self):
        """更新统计信息线程"""
        import time
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
                            stats_copy = self.stats.copy()
                            is_validating = self.is_validating
                            try:
                                self._run_on_main(
                                    self.main_window._update_stats_display,
                                    {'stats': stats_copy, 'is_validation': is_validating}
                                )
                            except RuntimeError:
                                break
                        else:
                            stats_copy = self.stats.copy()
                            is_validating_copy = self.is_validating
                            QtCore.QTimer.singleShot(0, lambda sc=stats_copy, iv=is_validating_copy: self.stats_updated.emit({
                                'stats': sc, 'is_validation': iv
                            }))

                    # 检查扫描是否完成：填充线程结束、所有工作线程都完成且队列为空
                    filler_alive = (
                        self.filler_thread.is_alive()
                        if hasattr(self, 'filler_thread') and self.filler_thread else False
                    )
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

                    # 如果填充线程结束、所有工作线程都完成且队列为空，则扫描完成
                    if not filler_alive and not workers_alive and queue_empty and validation_queue_empty:
                        break

                    time.sleep(0.5)  # 恢复到合理的更新频率，避免UI假死
                except RuntimeError:
                    break

            if self.stop_event.is_set():
                self.logger.info("扫描被用户停止")
            elif self.is_validating:
                self.is_validating = False
                self.scan_state_manager.update_scan_state(self.scan_id, {
                    'is_validating': False
                })
                self.logger.info(
                    f"验证完成: 总数={self.stats['total']}, "
                    f"有效={self.stats['valid']}, "
                    f"无效={self.stats['invalid']}"
                )
                if self.main_window and hasattr(self.main_window, '_on_validation_completed'):
                    try:
                        QtCore.QTimer.singleShot(0, self.main_window._on_validation_completed)
                    except RuntimeError:
                        self.logger.debug("主窗口已销毁，跳过验证完成回调")
            else:
                self.logger.info(
                    f"扫描完成: 总数={self.stats['total']}, "
                    f"有效={self.stats['valid']}, "
                    f"无效={self.stats['invalid']}"
                )

                invalid_urls = self.scan_state_manager.get_invalid_urls(self.scan_id)
                if invalid_urls:
                    from collections import Counter
                    error_types = [item.get('error_type', 'unknown') for item in invalid_urls]
                    error_counts = Counter(error_types)
                    top_errors = error_counts.most_common(5)
                    error_summary = ", ".join([f"{err}({cnt})" for err, cnt in top_errors])
                    self.logger.info(f"无效URL错误类型分布（前5）: {error_summary}")
                    if 'timeout' in error_counts:
                        self.logger.warning(f"⚠️ 有 {error_counts['timeout']} 个URL因超时被标记为无效，考虑增加超时时间")
                    if 'mpv_create_failed' in error_counts:
                        self.logger.error(f"❌ 有 {error_counts['mpv_create_failed']} 个mpv实例创建失败，可能是资源不足")

                try:
                    if self.main_window and hasattr(self.main_window, '_on_scan_completed'):
                        callback = self.main_window._on_scan_completed
                        QtCore.QTimer.singleShot(0, callback)
                    else:
                        self.logger.warning("无法调用主窗口方法")
                except RuntimeError:
                    self.logger.debug("主窗口已销毁，跳过扫描完成回调")
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
                        stats_copy = self.stats.copy()
                        is_validating = self.is_validating
                        try:
                            self._run_on_main(
                                self.main_window._update_stats_display,
                                {'stats': stats_copy, 'is_validation': is_validating}
                            )
                        except RuntimeError:
                            pass
                    else:
                        try:
                            stats_copy = self.stats.copy()
                            is_validating_copy = self.is_validating
                            QtCore.QTimer.singleShot(0, lambda sc=stats_copy, iv=is_validating_copy: self.stats_updated.emit({
                                'stats': sc, 'is_validation': iv
                            }))
                        except RuntimeError:
                            pass
            except Exception as e:
                self.logger.error(f"发送最终统计信息失败: {e}")
