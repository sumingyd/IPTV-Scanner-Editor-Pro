import subprocess
import time
import json
from typing import Dict, Optional
from log_manager import LogManager

class StreamValidator:
    """使用ffprobe检测视频流有效性"""
    
    def __init__(self):
        self.logger = LogManager()
        
    def validate_stream(self, url: str, timeout: int = 10) -> Dict:
        """验证视频流有效性
        
        Args:
            url: 要检测的流地址
            timeout: 超时时间(秒)
            
        Returns:
            Dict: 包含检测结果的字典
        """
        start_time = time.time()
        result = {
            'url': url,
            'valid': False,
            'latency': None,
            'resolution': None,
            'codec': None,
            'bitrate': None,
            'error': None
        }
        
        try:
            # 构建ffprobe命令
            cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                '-show_programs',
                '-timeout', str(timeout * 1000000),  # 微秒
                url
            ]
            
            # 执行命令
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            # 等待命令完成
            try:
                stdout, stderr = process.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                process.kill()
                result['error'] = '检测超时'
                return result
                
            # 计算延迟
            result['latency'] = int((time.time() - start_time) * 1000)
            
            # 解析输出
            if process.returncode == 0:
                result['valid'] = True
                
                try:
                    data = json.loads(stdout)
                    
                    # 从programs获取频道名
                    if 'programs' in data and len(data['programs']) > 0:
                        program = data['programs'][0]
                        if 'tags' in program and 'service_name' in program['tags']:
                            result['service_name'] = program['tags']['service_name']
                    
                    # 从streams获取分辨率等信息
                    if 'streams' in data and len(data['streams']) > 0:
                        stream = data['streams'][0]
                        if 'width' in stream and 'height' in stream:
                            result['resolution'] = f"{stream['width']}x{stream['height']}"
                        if 'codec_name' in stream:
                            result['codec'] = stream['codec_name']
                        if 'bit_rate' in stream:
                            result['bitrate'] = stream['bit_rate']
                except json.JSONDecodeError as e:
                    self.logger.error(f"JSON解析失败: {str(e)}")
                    result['error'] = "无法解析ffprobe输出"
            else:
                result['error'] = stderr.strip()
                
        except Exception as e:
            self.logger.error(f"检测流 {url} 时出错: {str(e)}")
            result['error'] = str(e)
            
        return result