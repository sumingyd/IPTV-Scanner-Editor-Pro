import threading
import queue
import time
from typing import List, Dict
from url_parser import URLRangeParser
from log_manager import LogManager, global_logger
from channel_model import ChannelListModel
from PyQt6 import QtCore
from PyQt6.QtCore import pyqtSignal, QObject
from channel_mappings import extract_channel_name_from_url

class ScannerController(QObject):
    """扫描控制器，管理多线程扫描过程"""
    
    # 定义信号
    progress_updated = pyqtSignal(int, int)  # 当前进度, 总数
    channel_found = pyqtSignal(dict)  # 有效的频道信息
    scan_completed = pyqtSignal()
    stats_updated = pyqtSignal(dict)  # 统计信息
    
    # 在类定义中声明信号
    channel_validated = pyqtSignal(int, bool, int, str)  # index, valid, latency, resolution

    def __init__(self, model: ChannelListModel, main_window=None):
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
        self.workers = []
        self.timeout = 10  # 默认超时时间
        self.channel_counter = 0
        self.counter_lock = threading.Lock()
        
        # 移除批量处理相关属性，直接添加频道
        self._batch_timer = None  # 不再使用批量定时器
        
        # 信号连接由主窗口处理
        # self.channel_found.connect(self.model.add_channel)  # 由主窗口处理
        self.stats = {
            'total': 0,
            'valid': 0,
            'invalid': 0,
            'start_time': 0,
            'elapsed': 0
        }

    def _force_ui_refresh(self):
        """强制刷新UI"""
        try:
            if hasattr(self.model, 'update_view'):
                self.model.update_view()
            elif hasattr(self.model, 'layoutChanged'):
                self.model.layoutChanged.emit()
        except Exception as e:
            self.logger.debug(f"UI刷新失败: {e}")
        
    def _worker(self):
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
                channel_info = self._build_channel_info(url, valid, latency, resolution, result)
                if not channel_info:
                    # 即使构建失败，也要确保统计信息更新
                    with self.stats_lock:
                        self.stats['invalid'] += 1
                        
                        current = self.stats['valid'] + self.stats['invalid']
                        total = self.stats['total']
                        
                        # 立即更新进度，确保状态栏进度条正常显示
                        import functools
                        QtCore.QTimer.singleShot(0, functools.partial(self.progress_updated.emit, current, total))
                    continue
                
                # 确保频道信息包含必要字段
                channel_info.setdefault('name', channel_info.get('raw_name', extract_channel_name_from_url(url)))
                
                # 只记录有效频道的详细信息
                if valid:
                    log_msg = f"有效频道 - 原始名: {channel_info['raw_name']}, 映射名: {channel_info['name']}, 分组: {channel_info['group']}, URL: {url}"
                    self.logger.info(log_msg)
                    
                    # 使用 functools.partial 确保频道信息正确传递
                    import functools
                    QtCore.QTimer.singleShot(0, functools.partial(self._handle_channel_add, channel_info.copy()))
                
                # 统计信息更新 - 确保无论有效还是无效都更新
                with self.stats_lock:
                    if valid:
                        self.stats['valid'] += 1
                    else:
                        self.stats['invalid'] += 1
                    
                    current = self.stats['valid'] + self.stats['invalid']
                    total = self.stats['total']
                    
                    # 即使total为0也发送进度更新信号，但使用默认值
                    if total <= 0:
                        self.logger.warning(f"进度条更新: total={total}，使用默认值1避免除零错误")
                        total = 1  # 避免除零错误
                    
                    # 添加进度条更新追踪日志
                    progress_percent = int(current / total * 100)
                    progress_percent = max(0, min(100, progress_percent))  # 确保在0-100范围内
                    self.logger.debug(f"进度条更新: {current}/{total} ({progress_percent}%)")
                    
                    # 立即更新进度，确保状态栏进度条正常显示
                    # 使用QTimer在主线程中安全地更新进度
                    import functools
                    QtCore.QTimer.singleShot(0, functools.partial(self.progress_updated.emit, current, total))
                
            except Exception as e:
                self.logger.error(f"工作线程错误: {e}", exc_info=True)
                # 即使出现异常，也要确保统计信息更新
                with self.stats_lock:
                    self.stats['invalid'] += 1
                    
                    current = self.stats['valid'] + self.stats['invalid']
                    total = self.stats['total']
                    
                    # 即使total为0也发送进度更新信号，但使用默认值
                    if total <= 0:
                        self.logger.warning(f"进度条更新(异常): total={total}，使用默认值1避免除零错误")
                        total = 1  # 避免除零错误
                    
                    # 添加进度条更新追踪日志
                    progress_percent = int(current / total * 100)
                    progress_percent = max(0, min(100, progress_percent))  # 确保在0-100范围内
                    self.logger.debug(f"进度条更新(异常): {current}/{total} ({progress_percent}%)")
                    
                    # 立即更新进度，确保状态栏进度条正常显示
                    import functools
                    QtCore.QTimer.singleShot(0, functools.partial(self.progress_updated.emit, current, total))
                
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
                QtCore.QTimer.singleShot(0, functools.partial(self.progress_updated.emit, total, total))
        
    def _update_progress(self, valid: bool):
        """更新扫描进度"""
        with self.stats_lock:
            if valid:
                self.stats['valid'] += 1
            else:
                self.stats['invalid'] += 1
            
            current = self.stats['valid'] + self.stats['invalid']
            total = self.stats['total']
            
            # 使用QTimer在主线程中安全地更新进度
            import functools
            QtCore.QTimer.singleShot(0, functools.partial(self.progress_updated.emit, current, total))

    def _process_valid_channel(self, channel_info: dict):
        """处理有效频道"""
        self.model.add_channel(channel_info)
        self.logger.info(f"添加有效频道: {channel_info['name']}")

    def _add_channel_and_refresh(self, channel_info: dict):
        """添加频道并强制刷新UI"""
        self.model.add_channel(channel_info)
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

    def _build_channel_info(self, url: str, valid: bool, latency: int, resolution: str, result: dict) -> dict:
        """构建完整的频道信息字典"""
        from channel_mappings import mapping_manager, extract_channel_name_from_url
        
        try:
            # 获取原始频道名
            raw_name = result.get('service_name', '') or extract_channel_name_from_url(url)
            if not raw_name or raw_name == "未知频道":
                raw_name = extract_channel_name_from_url(url)
            
            # 获取映射信息（使用新的映射管理器，支持智能学习和指纹匹配）
            channel_info_for_fingerprint = {
                'service_name': result.get('service_name', ''),
                'resolution': resolution,
                'codec': result.get('codec', ''),
                'bitrate': result.get('bitrate', '')
            }
            
            mapped_info = mapping_manager.get_channel_info(raw_name, url, channel_info_for_fingerprint) if valid else None
            mapped_name = mapped_info.get('standard_name', raw_name) if mapped_info else raw_name
            
            # 构建频道信息
            channel_info = {
                'url': url,
                'name': mapped_name,
                'raw_name': raw_name,
                'valid': valid,
                'latency': latency,
                'resolution': resolution if resolution else '',
                'status': '有效' if valid else '无效',
                'group': mapped_info.get('group_name', '未分类') if mapped_info else '未分类',
                'logo_url': mapped_info.get('logo_url') if mapped_info else None,
                'fingerprint': mapping_manager.create_channel_fingerprint(url, channel_info_for_fingerprint) if valid else None
            }
            
            # 记录详细的映射信息用于调试
            if valid:
                if mapped_name != raw_name:
                    # 频道映射成功，不再输出调试信息
                    pass
                else:
                    self.logger.debug(f"频道未映射，使用原始名称: {raw_name}")
                    
            return channel_info
            
        except Exception as e:
            self.logger.error(f"构建频道信息失败: {e}", exc_info=True)
            # 返回基本的频道信息，即使映射失败
            return {
                'url': url,
                'name': extract_channel_name_from_url(url),
                'raw_name': extract_channel_name_from_url(url),
                'valid': valid,
                'latency': latency,
                'resolution': resolution if resolution else '',
                'status': '有效' if valid else '无效',
                'group': '未分类',
                'logo_url': None,
                'error': str(e)
            }

    def _check_channel(self, url: str, raw_channel_name: str = None) -> dict:
        """检查频道有效性"""
        from validator import StreamValidator
        # 使用主窗口的语言管理器（如果可用）
        validator = StreamValidator(self.main_window)
        return validator.validate_stream(url, raw_channel_name=raw_channel_name, timeout=self.timeout)
        
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
                    
        except Exception as e:
            self.logger.error(f"队列填充线程错误: {e}")
        finally:
            self.logger.info("URL生成完成，队列填充结束")

    def is_scanning(self):
        """检查是否正在扫描"""
        return len(self.workers) > 0 and not self.stop_event.is_set()

    def start_scan(self, base_url: str, thread_count: int = 10, timeout: int = 10, user_agent: str = None, referer: str = None):
        """开始扫描 - 优化版本"""
        # 确保停止之前的扫描
        self.stop_scan()
        self.stop_event.clear()
        
        from validator import StreamValidator
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
            
        # 智能线程数调整：根据CPU核心数和URL数量优化
        import multiprocessing
        cpu_count = multiprocessing.cpu_count()
        
        # 动态调整线程数
        if thread_count <= 0:
            # 自动模式：根据CPU核心数调整
            optimal_threads = min(cpu_count * 2, 20)  # 最多20个线程
        else:
            # 用户指定模式，但限制最大线程数
            optimal_threads = min(thread_count, 50)  # 最多50个线程
        
        self.logger.info(f"使用 {optimal_threads} 个线程进行扫描 (CPU核心数: {cpu_count})")
            
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
        
        # 扫描开始时重置进度条为0%
        self.logger.info("扫描开始，重置进度条为0%")
        QtCore.QTimer.singleShot(0, lambda: self.progress_updated.emit(0, 1))
        
        self.logger.info(f"开始扫描URL，使用 {optimal_threads} 个线程，超时时间: {timeout}秒")
        
    def start_scan_from_urls(self, urls: list, thread_count: int = 10, timeout: int = 10, user_agent: str = None, referer: str = None):
        """从URL列表开始扫描（用于重试扫描）"""
        # 确保停止之前的扫描
        self.stop_scan()
        self.stop_event.clear()
        
        from validator import StreamValidator
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
        
        self.logger.info(f"开始重试扫描，共 {len(urls)} 个URL，使用 {thread_count} 个线程，超时时间: {timeout}秒")
        
    def stop_scan(self):
        """停止扫描 - 优化版本，修复资源泄漏"""
        self.stop_event.set()
        
        # 首先停止批量更新定时器（如果存在且活动）
        if hasattr(self, '_batch_timer') and self._batch_timer and self._batch_timer.isActive():
            self._batch_timer.stop()
        
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
        
        # 终止所有FFmpeg进程
        from validator import StreamValidator
        StreamValidator.terminate_all()
                
        # 优雅地终止所有工作线程
        for worker in self.workers:
            if worker.is_alive():
                # 设置极短的超时时间，立即终止线程避免UI假死
                worker.join(timeout=0.1)
                # 如果线程仍然存活，强制终止
                if worker.is_alive():
                    # 不再输出警告日志
                    pass
                
        self.workers = []
        
        # 强制垃圾回收
        import gc
        gc.collect()
                
        self.logger.info("扫描已完全停止，所有资源已清理")

    def start_validation(self, model, threads, timeout):
        """开始有效性验证"""
        self.is_validating = True
        self.stop_event.clear()
        self.timeout = timeout
        
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
        
        # 验证开始时重置进度条为0%
        self.logger.info("有效性验证开始，重置进度条为0%")
        QtCore.QTimer.singleShot(0, lambda: self.progress_updated.emit(0, 1))

    def stop_validation(self):
        """停止有效性验证"""
        self.stop_event.set()
        self.is_validating = False
        
        # 清空任务队列
        while not self.validation_queue.empty():
            try:
                self.validation_queue.get_nowait()
            except queue.Empty:
                break
                
        # 终止所有验证进程
        from validator import StreamValidator
        StreamValidator.terminate_all()
                
        # 立即终止工作线程
        for worker in self.workers:
            if worker.is_alive():
                worker.join(timeout=0.1)
                
        self.workers = []
        self.worker_queue = queue.Queue()
        self.logger.info("有效性验证已立即停止，所有进程已终止")

    def _validation_worker(self):
        """有效性验证工作线程"""
        while not self.stop_event.is_set():
            try:
                url, index = self.validation_queue.get_nowait()
                time.sleep(0.01)
                
                result = self._check_channel(url)
                valid = result['valid']
                latency = result['latency']
                resolution = result.get('resolution', '')
                
                # 记录验证结果日志 - 使用模型中的频道名
                channel = self.model.get_channel(index)
                channel_name = channel.get('name', extract_channel_name_from_url(url))
                log_msg = f"有效性验证 - 频道: {channel_name}, URL: {url}, 状态: {'有效' if valid else '无效'}, 延迟: {latency}ms, 分辨率: {resolution}"
                self.logger.info(log_msg)
                
                # 使用QTimer在主线程中安全地更新模型状态
                QtCore.QTimer.singleShot(0, lambda: self.model.set_channel_valid(url, valid))
                
                # 每10次更新批量刷新一次视图
                if index % 10 == 0:
                    QtCore.QTimer.singleShot(0, self.model.update_view)
                
                # 使用QTimer在主线程中安全地发射信号
                QtCore.QTimer.singleShot(0, lambda: self.channel_validated.emit(index, valid, latency, resolution))
                
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
                        self.logger.warning(f"验证进度条更新: total={total}，使用默认值1避免除零错误")
                        total = 1  # 避免除零错误
                    
                    # 立即更新进度，确保状态栏进度条正常显示
                    # 使用QTimer在主线程中安全地更新进度
                    import functools
                    QtCore.QTimer.singleShot(0, functools.partial(self.progress_updated.emit, current, total))
            except queue.Empty:
                time.sleep(0.1)
                break
            except Exception as e:
                self.logger.error(f"验证线程错误: {e}", exc_info=True)
                time.sleep(0.1)
                # 继续处理下一个任务，不中断线程
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
                        
                        # 使用QTimer在主线程中安全地更新统计信息
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
                    workers_alive = any(w.is_alive() for w in self.workers) if self.workers else False
                    queue_empty = self.scan_queue.empty() if hasattr(self, 'scan_queue') else True
                    validation_queue_empty = self.validation_queue.empty() if hasattr(self, 'validation_queue') else True
                    
                    # 如果所有工作线程都完成且队列为空，则扫描完成
                    if not workers_alive and queue_empty and validation_queue_empty:
                        break
                    
                    time.sleep(0.5)  # 恢复到合理的更新频率，避免UI假死
                except RuntimeError:
                    break
                
            # 只有当确实有扫描或验证任务完成时才发射完成信号
            if not self.stop_event.is_set() and (self.stats['total'] > 0 or self.is_validating):
                try:
                    # 使用QTimer在主线程中安全地发射完成信号
                    QtCore.QTimer.singleShot(0, self.scan_completed.emit)
                except RuntimeError:
                    pass
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
