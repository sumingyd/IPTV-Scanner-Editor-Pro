import subprocess
import time
import json
import sys
import os
from typing import Dict, Optional
from log_manager import LogManager

class StreamValidator:
    """使用ffprobe检测视频流有效性"""
    
    def __init__(self):
        self.logger = LogManager()

    def _get_ffprobe_path(self):
        """获取ffprobe路径"""
        import os
        import sys
        
        # 记录所有尝试的路径
        tried_paths = []
        
        # 1. 尝试从打包后的路径查找
        if getattr(sys, 'frozen', False):
            base_path = os.path.dirname(sys.executable)
            exe_path = os.path.join(base_path, 'ffmpeg', 'bin', 'ffprobe.exe')
            tried_paths.append(f"打包路径: {exe_path}")
            if os.path.exists(exe_path):
                return exe_path
        
        # 2. 尝试从开发环境路径查找
        dev_path = os.path.join(os.path.dirname(__file__), 'ffmpeg', 'bin', 'ffprobe.exe')
        tried_paths.append(f"开发路径: {dev_path}")
        if os.path.exists(dev_path):
            return dev_path
            
        # 3. 尝试从系统PATH查找
        try:
            from shutil import which
            path = which('ffprobe')
            tried_paths.append(f"系统PATH查找")
            if path:
                return path
        except ImportError:
            tried_paths.append("无法导入shutil.which")
            pass
            
        # 记录所有尝试过的路径
        self.logger.warning(
            "无法找到ffprobe，尝试了以下路径:\n" + 
            "\n".join(tried_paths) +
            "\n将尝试直接调用'ffprobe'"
        )
        return 'ffprobe'  # 最后尝试直接调用

    def _is_multicast_url(self, url: str) -> bool:
        """判断是否为组播地址"""
        url_lower = url.lower()
        # 包含/rtp/、/udp/、/rtsp/或以rtp://、udp://、rtsp://开头的URL视为组播
        return (url_lower.startswith(('rtp://', 'udp://', 'rtsp://')) or
                any(x in url_lower for x in ['/rtp/', '/udp/', '/rtsp/']))

    def _validate_unicast(self, url: str, timeout: int) -> Dict:
        """验证单播流"""
        result = {
            'url': url,
            'valid': False,
            'latency': None,
            'resolution': None,
            'codec': None,
            'bitrate': None,
            'error': None
        }
        
        # 直接使用ffprobe获取流信息
        ffprobe_path = self._get_ffprobe_path()
        cmd = [
            ffprobe_path,
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            '-show_programs',
            url
        ]
        try:
            result.update(self._run_ffprobe(cmd, timeout))
        except Exception as e:
            result['error'] = str(e)
            
        return result

    def _validate_multicast(self, url: str, timeout: int) -> Dict:
        """验证组播流"""
        result = {
            'url': url,
            'valid': False,
            'latency': None,
            'resolution': None,
            'codec': None,
            'bitrate': None,
            'error': None,
            'service_name': None
        }
        
        try:
            # 直接使用ffprobe获取流信息
            ffprobe_path = self._get_ffprobe_path()
            cmd = [
                ffprobe_path,
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                '-show_programs',
                url
            ]
            probe_result = self._run_ffprobe(cmd, timeout)
            
            # 解析ffprobe输出获取service_name
            if 'programs' in probe_result and probe_result['programs']:
                program = probe_result['programs'][0]
                if 'tags' in program and 'service_name' in program['tags']:
                    result['service_name'] = program['tags']['service_name']
            
            # 更新其他结果
            result.update(probe_result)
            
            # 如果没获取到分辨率但获取到了其他信息，尝试从错误输出中提取
            if not result.get('resolution') and probe_result.get('error'):
                error = probe_result['error']
                if 'Video:' in error:
                    import re
                    match = re.search(r'(\d{3,4}x\d{3,4})', error)
                    if match:
                        result['resolution'] = match.group(1)
            
            # 基于分辨率判断有效性
            result['valid'] = bool(result.get('resolution'))
            
        except Exception as e:
            result['error'] = str(e)
            
        return result

    def _run_ffprobe(self, cmd: list, timeout: int) -> Dict:
        """执行ffprobe命令并解析结果"""
        result = {}
        start_time = time.time()

        # 在Windows上需要处理特殊字符
        if sys.platform == 'win32':
            cmd = [arg.replace('^', '^^').replace('&', '^&') for arg in cmd]
        
        # 设置环境变量和工作目录
        env = os.environ.copy()
        env['PATH'] = os.path.dirname(self._get_ffprobe_path()) + os.pathsep + env['PATH']
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=False,
            creationflags=subprocess.CREATE_NO_WINDOW,
            shell=True if sys.platform == 'win32' else False,
            env=env,
            cwd=os.path.dirname(self._get_ffprobe_path())
        )
        
        try:
            # 记录命令开始执行时间
            exec_start = time.time()
            stdout_bytes, stderr_bytes = process.communicate(timeout=timeout)
            exec_end = time.time()
            
            stdout = stdout_bytes.decode('utf-8', errors='replace')
            stderr = stderr_bytes.decode('utf-8', errors='replace')

            
            if process.returncode == 0:
                try:
                    data = json.loads(stdout)
                    result.update(self._parse_ffprobe_output(data))
                except json.JSONDecodeError:
                    # 如果JSON解析失败，尝试从stderr提取信息
                    result['error'] = stderr.strip()
                    if not result['error']:
                        result['error'] = '无法解析ffprobe输出'
            else:
                result['error'] = stderr.strip()
                if not result['error']:
                    result['error'] = f"ffprobe返回错误代码: {process.returncode}"
                
        except subprocess.TimeoutExpired:
            process.kill()
            result['error'] = '检测超时'
        except Exception as e:
            result['error'] = str(e)
            
        result['latency'] = int((time.time() - start_time) * 1000)
        return result

    def _parse_ffprobe_output(self, data: Dict) -> Dict:
        """解析ffprobe输出"""
        result = {}
        
        # 获取频道名
        service_name = None
        if 'programs' in data and data['programs']:
            program = data['programs'][0]
            if 'tags' in program and 'service_name' in program['tags']:
                service_name = program['tags']['service_name']
        elif 'streams' in data and data['streams']:
            for stream in data['streams']:
                if 'tags' in stream and 'service_name' in stream['tags']:
                    service_name = stream['tags']['service_name']
                    break
        elif 'format' in data and 'tags' in data['format'] and 'service_name' in data['format']['tags']:
            service_name = data['format']['tags']['service_name']
            
        if service_name:
            result['service_name'] = self._clean_channel_name(service_name)
        else:
            result['service_name'] = "未知频道"

        # 获取分辨率
        if 'streams' in data and data['streams']:
            stream = next((s for s in data['streams'] if s.get('codec_type') == 'video'), data['streams'][0])
            if 'width' in stream and 'height' in stream:
                result['resolution'] = f"{stream['width']}x{stream['height']}"
            elif 'coded_width' in stream and 'coded_height' in stream:
                result['resolution'] = f"{stream['coded_width']}x{stream['coded_height']}"
            else:
                result['resolution'] = "未知分辨率"
                
            if 'codec_name' in stream:
                result['codec'] = stream['codec_name']
            if 'bit_rate' in stream:
                result['bitrate'] = stream['bit_rate']
                
        return result

    def _clean_channel_name(self, name: str) -> str:
        """清理频道名"""
        if not name:
            return "未知频道"
            
        # 去除清晰度后缀
        suffixes = ['-SD', '-HD', '-FHD', '-4K', '-8K', 'SD', 'HD', 'FHD', '4K', '8K']
        for suffix in suffixes:
            if name.endswith(suffix):
                name = name[:-len(suffix)]
                break
        return name

    def validate_stream(self, url: str, raw_channel_name: str = None, timeout: int = 10) -> Dict:
        """验证视频流有效性
        
        Args:
            url: 要检测的流地址
            raw_channel_name: 从URL提取的原始频道名
            timeout: 超时时间(秒)
            
        Returns:
            Dict: 包含检测结果的字典，包含以下字段：
                - url: 原始URL
                - valid: 是否有效(基于分辨率判断)
                - latency: 延迟(毫秒)
                - resolution: 分辨率
                - codec: 视频编码
                - bitrate: 比特率
                - service_name: 频道名称(仅从流中提取)
                - error: 错误信息(如果有)
        """
        # 统一结果结构
        result = {
            'url': url,
            'valid': False,
            'latency': None,
            'resolution': None,
            'codec': None,
            'bitrate': None,
            'service_name': None,
            'error': None
        }
            
        try:
            # 执行流验证
            is_multicast = self._is_multicast_url(url)
            if is_multicast:
                probe_result = self._validate_multicast(url, timeout)
                # 组播流优先使用ffprobe获取的service_name
                if probe_result.get('service_name'):
                    result['service_name'] = probe_result['service_name']
            else:
                probe_result = self._validate_unicast(url, timeout)
            
            # 合并其他结果
            probe_result.pop('service_name', None)
            result.update(probe_result)
            
            # 统一有效性判断标准：基于分辨率
            result['valid'] = bool(result.get('resolution'))
                
        except Exception as e:
            result['error'] = str(e)
            self.logger.error(f"验证流 {url} 时出错: {e}")
            
        return result
