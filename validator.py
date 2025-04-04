import asyncio
from typing import List, Dict, Union, Optional
from PyQt6.QtCore import QObject, pyqtSignal
from qasync import asyncSlot
from utils import setup_logger, ConfigHandler
import subprocess
import os

logger = setup_logger('Validator')

class StreamValidator(QObject):
    """流媒体有效性验证器"""
    progress_updated = pyqtSignal(int, str)  # 进度百分比, 状态信息
    validation_finished = pyqtSignal(dict)   # 验证结果字典
    error_occurred = pyqtSignal(str)         # 错误信息
    channel_validated = pyqtSignal(dict)     # 单个频道验证结果
    
    def __init__(self):
        super().__init__()
        self._timeout = 10  # 默认超时时间(秒)
        self.config = ConfigHandler()
        self._timeout = self.config.config.getint('Scanner', 'timeout', fallback=10)
        self._ffprobe_path = os.path.join('ffmpeg', 'bin', 'ffprobe.exe')
        self._is_running = False
        self._active_processes = []  # 跟踪所有活动的ffprobe进程
        self._current_url = None  # 当前正在验证的URL

    def set_timeout(self, timeout: int) -> None:
        """设置验证超时时间(秒)"""
        self._timeout = timeout

    def is_running(self) -> bool:
        """检查验证是否在进行中"""
        return self._is_running

    @asyncSlot()
    async def validate_playlist(self, playlist_data: Union[List[Dict], List[str]], max_workers: int) -> Dict:
        """验证播放列表有效性
        Args:
            playlist_data: 播放列表数据
            max_workers: 最大并行任务数(从UI界面获取)
        """
        if not playlist_data:
            error_msg = "播放列表为空"
            logger.error(error_msg)
            self.error_occurred.emit(error_msg)
            return {'valid': [], 'invalid': []}
            
        # 确保在停止验证时能正确处理信号量
        semaphore = None
        
        logger.info(f"开始验证播放列表，共{len(playlist_data)}个频道，最大并发数: {max_workers}")

        # 处理纯URL字符串列表的情况
        if isinstance(playlist_data[0], str):
            playlist_data = [{'url': url} for url in playlist_data]

        self._is_running = True
        total = len(playlist_data)
        valid_channels = []
        invalid_channels = []
        
        try:
            # 创建信号量控制并发数(确保在1-50之间)
            max_workers = max(1, min(max_workers, 50))  # 限制最大50个并发
            semaphore = asyncio.Semaphore(max_workers)
            logger.info(f"验证参数 - 超时时间: {self._timeout}s, ffprobe路径: {self._ffprobe_path}, 并发数: {max_workers}")
            
            async def validate_one(channel: Dict) -> Optional[Dict]:
                async with semaphore:
                    url = channel.get('url', '')
                    if not url:
                        return {**channel, 'valid': False}
                    
                    try:
                        logger.info(f"开始验证频道: {url}")
                        valid, latency, width, height = await self._validate_channel(url)
                        result = {
                            **channel,
                            'valid': valid,
                            'latency': latency if valid else 0.0,
                            'width': width,
                            'height': height
                        }
                        logger.info(f"频道验证完成: {url} - 结果: {'有效' if valid else '无效'}" + 
                                  (f", 延迟: {latency:.2f}s" if valid else "") +
                                  (f", 分辨率: {width}x{height}" if valid and width and height else ""))
                        
                        # 实时发射单个频道结果
                        result = {
                            'index': playlist_data.index(channel),
                            'url': url,
                            'valid': valid,
                            'latency': latency,
                            'width': width,
                            'height': height,
                            'progress': int((playlist_data.index(channel) + 1) / total * 100)
                        }
                        logger.debug(f"发射频道验证结果: {result}")
                        # 确保分辨率数据有效时才发射
                        if width > 0 and height > 0:
                            self.channel_validated.emit(result)
                        else:
                            self.channel_validated.emit({
                                'index': result['index'],
                                'url': result['url'],
                                'valid': result['valid'],
                                'latency': result['latency'],
                                'width': 0,
                                'height': 0,
                                'progress': result['progress']
                            })
                        
                        return result
                    except Exception as e:
                        error_msg = f"验证失败: {url} - {str(e)}"
                        logger.warning(error_msg)
                        return {**channel, 'valid': False}

            # 并行验证所有频道
            tasks = [validate_one(channel) for channel in playlist_data]
            try:
                results = await asyncio.gather(*tasks, return_exceptions=True)
            except asyncio.CancelledError:
                logger.info("验证任务已被取消")
                return {'valid': [], 'invalid': []}
            
            for i, result in enumerate(results):
                if not self._is_running:  # 检查是否被停止
                    break
                    
                channel = playlist_data[i]
                url = channel.get('url', '')
                if not url:
                    invalid_channels.append({**channel, 'valid': False})
                    continue
                
                try:
                    valid, latency, width, height = await self._validate_channel(url)
                    if valid:
                        valid_channels.append({**channel, 'valid': True, 'latency': latency, 'width': width, 'height': height})
                    else:
                        invalid_channels.append({**channel, 'valid': False, 'latency': 0.0, 'width': 0, 'height': 0})
                except Exception as e:
                    logger.warning(f"验证失败: {url} - {str(e)}")
                    invalid_channels.append({**channel, 'valid': False, 'width': 0, 'height': 0})
                
                # 发送单个频道验证结果
                result = {
                    'index': i,
                    'url': url,
                    'valid': valid,
                    'latency': latency,
                    'width': width,
                    'height': height,
                    'progress': int((i + 1) / total * 100)
                }
                self.channel_validated.emit(result)
                
                # 更新进度
                status_msg = f"验证进度: {len(valid_channels)}有效/{len(invalid_channels)}无效"
                if valid_channels:
                    avg_latency = sum(c['latency'] for c in valid_channels) / len(valid_channels)
                    status_msg += f" | 平均延迟: {avg_latency:.2f}s"
                self.progress_updated.emit(result['progress'], status_msg)

            # 验证完成
            result = {
                'valid': valid_channels,
                'invalid': invalid_channels,
                'total': total
            }
            logger.info(f"播放列表验证完成 - 有效: {len(valid_channels)}, 无效: {len(invalid_channels)}, " +
                       f"成功率: {len(valid_channels)/total*100:.1f}%")
            self.validation_finished.emit(result)
            return result
            
        except Exception as e:
            logger.error(f"验证出错: {str(e)}")
            self.error_occurred.emit(f"验证出错: {str(e)}")
            return {'valid': [], 'invalid': []}
        finally:
            self._is_running = False

    async def _validate_channel(self, url: str) -> tuple[bool, float, int, int]:
        """使用ffprobe验证单个频道并返回(是否有效, 延迟秒数, 宽度, 高度)"""
        self._current_url = url
        # 验证命令
        validate_cmd = [
            self._ffprobe_path,
            '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=codec_name,width,height',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            url
        ]
        
        # 延迟和分辨率测量命令
        latency_cmd = [
            self._ffprobe_path,
            '-v', 'error',
            '-show_entries', 'format=start_time',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            url
        ]
        
        # 执行验证
        validate_proc = await asyncio.create_subprocess_exec(
            *validate_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        self._active_processes.append(validate_proc)
        
        try:
            stdout, stderr = await asyncio.wait_for(validate_proc.communicate(), timeout=self._timeout)
            valid = validate_proc.returncode == 0
            
            # 如果有效则测量延迟和获取分辨率
            latency = 0.0
            width = 0
            height = 0
            if valid:
                # 解析分辨率信息
                output = stdout.decode().strip().split('\n')
                if len(output) >= 3:
                    width = int(output[1]) if output[1] else 0
                    height = int(output[2]) if output[2] else 0
                latency_proc = await asyncio.create_subprocess_exec(
                    *latency_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                self._active_processes.append(latency_proc)
                try:
                    stdout, _ = await asyncio.wait_for(latency_proc.communicate(), timeout=self._timeout)
                    if latency_proc.returncode == 0:
                        latency = float(stdout.decode().strip())
                finally:
                    if latency_proc.returncode is None:
                        latency_proc.terminate()
                    try:
                        self._active_processes.remove(latency_proc)
                    except ValueError:
                        pass
            
            return (valid, float(latency) if latency else 0.0, width, height)
        except asyncio.TimeoutError:
            return (False, 0.0, 0, 0)
        finally:
            self._current_url = None
            if validate_proc.returncode is None:
                validate_proc.terminate()
            try:
                self._active_processes.remove(validate_proc)
            except ValueError:
                pass

    async def stop_validation(self):
        """停止验证"""
        if not self._is_running:
            logger.debug("验证未运行，无需停止")
            return
            
        logger.info("用户请求停止验证")
        self._is_running = False
        
        try:
            # 获取当前所有运行中的任务
            current_task = asyncio.current_task()
            all_tasks = [t for t in asyncio.all_tasks() if t is not current_task]
            
            # 优雅地取消所有相关任务
            cancel_tasks = []
            for task in all_tasks:
                try:
                    if not task.done():
                        task.cancel()
                        cancel_tasks.append(task)
                except Exception as e:
                    logger.warning(f"取消任务时出错: {str(e)}")
            
            # 等待所有任务处理取消
            if cancel_tasks:
                try:
                    await asyncio.wait(cancel_tasks, timeout=1)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    pass
            
            # 终止所有活动的ffprobe进程
            terminate_tasks = []
            for proc in self._active_processes[:]:  # 创建副本遍历
                if proc.returncode is None:
                    try:
                        proc.terminate()
                        # 显式创建等待任务
                        task = asyncio.create_task(proc.wait())
                        terminate_tasks.append(task)
                        logger.debug(f"正在终止ffprobe进程: {proc.pid}")
                    except ProcessLookupError:
                        self._active_processes.remove(proc)
            
            # 强制终止所有进程(三重保障)
            for proc in self._active_processes[:]:
                if proc.returncode is None:
                    try:
                        proc.kill()
                    except ProcessLookupError:
                        pass
                    finally:
                        if proc in self._active_processes:
                            self._active_processes.remove(proc)
            
            # 等待所有进程终止完成
            if terminate_tasks:
                try:
                    done, pending = await asyncio.wait(terminate_tasks, timeout=2)
                    # 取消未完成的任务
                    for task in pending:
                        task.cancel()
                except asyncio.CancelledError:
                    pass
            
            # 确保所有资源释放
            self._active_processes.clear()
            self._current_url = None
            
            # 发送停止信号
            self.progress_updated.emit(0, "验证已停止")
            self.validation_finished.emit({'valid': [], 'invalid': [], 'total': 0})
            logger.info(f"验证已完全停止，共终止了{len(terminate_tasks)}个后台进程和{len(all_tasks)}个异步任务")
            
            # 确保事件循环处理完成
            await asyncio.sleep(0)
        except Exception as e:
            logger.error(f"停止验证时发生错误: {str(e)}")
            raise
