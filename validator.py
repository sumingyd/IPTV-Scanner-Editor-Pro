import asyncio
from typing import List, Dict, Union, Optional
from PyQt6.QtCore import QObject, pyqtSignal
from qasync import asyncSlot
from utils import setup_logger
from ffprobe_utils import FFProbeHelper

logger = setup_logger('Validator')

# 流媒体有效性验证器
class StreamValidator(QObject):
    """流媒体有效性验证器"""
    progress_updated = pyqtSignal(int, str)  # 进度百分比, 状态信息
    validation_finished = pyqtSignal(dict)   # 验证结果字典
    error_occurred = pyqtSignal(str)         # 错误信息
    channel_validated = pyqtSignal(dict)     # 单个频道验证结果
    
    def __init__(self):
        super().__init__()
        self.ffprobe = FFProbeHelper()
        self._is_running = False
        self._current_url = None  # 当前正在验证的URL
        self._active_processes = []  # 跟踪所有活动进程

    # 设置验证超时时间
    def set_timeout(self, timeout: int) -> None:
        """设置验证超时时间(秒)"""
        self._timeout = timeout

    # 检查验证是否在进行中
    def is_running(self) -> bool:
        """检查验证是否在进行中"""
        return self._is_running

    # 验证播放列表有效性
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
            return {'valid': [], 'invalid': [], 'total': 0}
        finally:
            self._is_running = False

    async def _validate_channel(self, url: str) -> tuple[bool, float, int, int]:
        """使用ffprobe验证单个频道并返回(是否有效, 延迟秒数, 宽度, 高度)"""
        self._current_url = url
        try:
            valid, latency, width, height = await self.ffprobe.probe_stream(url)
            return (valid, latency, width, height)
        except Exception as e:
            logger.error(f"验证频道失败: {url} - {str(e)}")
            return (False, 0.0, 0, 0)
        finally:
            self._current_url = None

    #停止验证
    async def stop_validation(self):
        """停止验证"""
        if not self._is_running:
            return
            
        logger.info("停止验证中...")
        self._is_running = False
        
        try:
            # 取消所有任务
            current_task = asyncio.current_task()
            tasks = [t for t in asyncio.all_tasks() if t is not current_task]
            for task in tasks:
                task.cancel()
            await asyncio.wait(tasks, timeout=1)
            
            # 终止所有进程
            for proc in self._active_processes[:]:
                if proc.returncode is None:
                    try:
                        proc.terminate()
                        await asyncio.wait_for(proc.wait(), timeout=1)
                        if proc.returncode is None:
                            proc.kill()
                    except:
                        pass
            await asyncio.sleep(0.5)
            
            # 清理资源
            self._active_processes.clear()
            self._current_url = None
            
            # 发送停止信号
            self.progress_updated.emit(0, "验证已停止")
            self.validation_finished.emit({'valid': [], 'invalid': [], 'total': 0})
        except Exception as e:
            logger.error(f"停止验证出错: {str(e)}")

    # 窗口关闭时清理资源
    def cleanup(self):
        """窗口关闭时清理资源"""
        if self._is_running:
            asyncio.create_task(self.stop_validation())
        
        # 安全清理进程资源
        if hasattr(self, '_active_processes'):
            # 强制终止任何剩余进程
            for proc in self._active_processes[:]:
                if proc and proc.returncode is None:
                    try:
                        proc.kill()
                    except:
                        pass
            self._active_processes.clear()

    # 处理单个频道的验证结果
    def handle_channel_validation(self, result: dict):
        """处理单个频道的验证结果"""
        url = result['url']
        valid = result['valid']
        latency = result.get('latency', 0.0)
        width = result.get('width', 0)
        height = result.get('height', 0)
        
        # 返回处理后的结果
        return {
            'url': url,
            'valid': valid,
            'latency': latency,
            'width': width,
            'height': height
        }

    # 处理验证完成事件
    def handle_validation_complete(self, result: dict):
        """处理验证完成事件"""
        valid_count = len(result['valid'])
        total = result['total']
        return {
            'valid': result['valid'],
            'invalid': result['invalid'],
            'total': total,
            'valid_count': valid_count,
            'message': f"检测完成 - 有效: {valid_count}/{total}"
        }

    # 更新验证进度
    def update_progress(self, percent: int, msg: str):
        """更新验证进度"""
        self.progress_updated.emit(percent, msg)
