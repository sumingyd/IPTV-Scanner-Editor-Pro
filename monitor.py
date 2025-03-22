import time
import platform
import subprocess
from typing import Dict, Any
from PyQt6.QtCore import QThread, pyqtSignal
import psutil

class PlayerMonitor(QThread):
    """播放器性能监控线程
    
    功能特性:
    - 实时监测CPU/内存/GPU使用率
    - 支持NVIDIA/AMD/Intel显卡检测
    - 跨平台兼容（Windows/Linux/macOS）
    - 安全线程退出机制
    """
    
    update_signal = pyqtSignal(dict)  # 信号参数格式: {指标名称: 数值}

    def __init__(self, player):
        super().__init__()
        self.player = player
        self._is_running = False
        self._gpu_type = self._detect_gpu()
        self._last_stats = {}  # 用于存储上一次的监控数据

    def _detect_gpu(self) -> str:
        """检测显卡类型"""
        try:
            # 检测NVIDIA
            subprocess.check_output(['nvidia-smi'], stderr=subprocess.DEVNULL)
            return 'nvidia'
        except (FileNotFoundError, subprocess.CalledProcessError):
            try:
                # 检测AMD
                subprocess.check_output(['rocm-smi'], stderr=subprocess.DEVNULL)
                return 'amd'
            except (FileNotFoundError, subprocess.CalledProcessError):
                # 检测Intel
                if 'intel' in platform.processor().lower():
                    return 'intel'
        return 'unknown'

    def run(self) -> None:
        """主监控循环"""
        self._is_running = True
        while self._is_running:
            try:
                stats = {
                    'cpu': psutil.cpu_percent(interval=0.5),
                    'memory': psutil.virtual_memory().percent,
                    'gpu': self._get_gpu_usage(),
                    'buffer': self._get_buffer_level(),
                    'timestamp': time.time()
                }
                
                # 仅在数据发生变化时发送信号
                if stats != self._last_stats:
                    self.update_signal.emit(stats)
                    self._last_stats = stats
            except Exception as e:
                self.update_signal.emit({'error': str(e)})
            
            time.sleep(1)

    def _get_gpu_usage(self) -> float:
        """获取GPU使用率"""
        try:
            if self._gpu_type == 'nvidia':
                cmd = ['nvidia-smi', '--query-gpu=utilization.gpu', '--format=csv,noheader,nounits']
                output = subprocess.check_output(cmd, timeout=2).decode().strip()
                return float(output.split('\n')[0])
            
            elif self._gpu_type == 'amd':
                cmd = ['rocm-smi', '--showuse', '--csv']
                output = subprocess.check_output(cmd, timeout=2).decode()
                return float(output.split(',')[1].strip('%'))
            
            elif self._gpu_type == 'intel':
                cmd = ['intel_gpu_top', '-o', '-']
                output = subprocess.check_output(cmd, timeout=2).decode()
                return float(output.splitlines()[1].split()[2])
            
        except (subprocess.SubprocessError, IndexError, ValueError):
            return -1.0

    def _get_buffer_level(self) -> float:
        """获取缓冲区状态"""
        try:
            stats = self.player.media_player.get_stats()
            buffer_level = (stats.i_decoded_audio + stats.i_decoded_video) / 1000.0  # 转换为KB
            logger.debug("当前缓冲区状态: %.2f KB", buffer_level)  # 增加日志
            return buffer_level
        except AttributeError:
            return 0.0

    def stop(self) -> None:
        """安全停止监控"""
        self._is_running = False
        self.wait(2000)  # 最多等待2秒

    def __del__(self) -> None:
        """析构时自动停止"""
        self.stop()