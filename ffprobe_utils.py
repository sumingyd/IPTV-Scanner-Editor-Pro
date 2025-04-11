import os
import sys
import asyncio
import subprocess
import json
from pathlib import Path
from typing import Tuple, Optional, Dict, Any

import psutil
from utils import setup_logger, ConfigHandler

logger = setup_logger('FFProbe')

class FFProbeHelper:
    """FFProbe工具类，封装ffprobe相关操作"""
    
    def __init__(self):
        self._ffprobe_path = self._find_ffprobe()
        self._timeout = 10  # 默认超时时间(秒)
        self._active_processes = set()  # 跟踪活动进程
        
    def _find_ffprobe(self) -> str:
        """查找ffprobe可执行文件路径"""
        if getattr(sys, 'frozen', False):
            path = os.path.join(sys._MEIPASS, 'ffmpeg', 'bin', 'ffprobe.exe')
        else:
            config = ConfigHandler()
            path = config.config.get('Scanner', 'ffprobe_path', 
                    fallback=os.path.join(os.path.dirname(__file__), '..', 'ffmpeg', 'bin', 'ffprobe.exe'))
        
        if not Path(path).exists():
            logger.error(f"ffprobe文件不存在: {path}")
            raise FileNotFoundError(f"ffprobe not found at {path}")
        return path
    
    def set_timeout(self, timeout: int) -> None:
        """设置探测超时时间(秒)"""
        self._timeout = timeout
    
    async def probe_stream(
        self, 
        url: str,
        check_video: bool = True,
        check_latency: bool = True
    ) -> Tuple[bool, float, int, int]:
        """
        探测流媒体信息
        返回: (是否有效, 延迟秒数, 宽度, 高度)
        """
        valid = False
        latency = 0.0
        width = 0
        height = 0
        
        try:
            # 检查视频流信息
            if check_video:
                cmd = self._build_video_cmd(url)
                result = await self._run_command(cmd)
                if result and result.get('streams'):
                    valid = True
                    width = int(result['streams'][0].get('width', 0))
                    height = int(result['streams'][0].get('height', 0))
            
            # 检查延迟
            if valid and check_latency:
                cmd = self._build_latency_cmd(url)
                result = await self._run_command(cmd)
                if result and result.get('format'):
                    latency = float(result['format'].get('start_time', 0.0))
            
            return (valid, latency, width, height)
        except Exception as e:
            logger.error(f"探测流媒体失败: {url} - {str(e)}")
            return (False, 0.0, 0, 0)
    
    def _build_video_cmd(self, url: str) -> list:
        """构建视频流探测命令"""
        return [
            self._ffprobe_path,
            '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=codec_name,width,height',
            '-of', 'json',
            '-timeout', str(self._timeout * 1_000_000),
            url
        ]
    
    def _build_latency_cmd(self, url: str) -> list:
        """构建延迟探测命令"""
        return [
            self._ffprobe_path,
            '-v', 'error',
            '-show_entries', 'format=start_time',
            '-of', 'json',
            '-timeout', str(self._timeout * 1_000_000),
            url
        ]
    
    async def _run_command(self, cmd: list) -> Optional[Dict[str, Any]]:
        """执行ffprobe命令并返回解析后的JSON结果"""
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        self._active_processes.add(proc.pid)
        
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=self._timeout
            )
            if proc.returncode == 0:
                return json.loads(stdout.decode('utf-8'))
            logger.debug(f"ffprobe命令失败: {stderr.decode('utf-8')}")
            return None
        finally:
            if proc.returncode is None:
                proc.kill()
            self._active_processes.discard(proc.pid)
    
    async def cleanup(self):
        """清理所有活动进程"""
        for pid in list(self._active_processes):
            try:
                proc = psutil.Process(pid)
                proc.kill()
            except psutil.NoSuchProcess:
                pass
        self._active_processes.clear()
