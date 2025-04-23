import subprocess
import time
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
                '-v', 'error',
                '-select_streams', 'v:0',
                '-show_entries', 'stream=codec_name,width,height,bit_rate',
                '-of', 'default=noprint_wrappers=1',
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
                width = height = None
                for line in stdout.splitlines():
                    if 'width=' in line:
                        width = line.split('=')[1]
                    elif 'height=' in line:
                        height = line.split('=')[1]
                    elif 'codec_name=' in line:
                        result['codec'] = line.split('=')[1]
                    elif 'bit_rate=' in line:
                        result['bitrate'] = line.split('=')[1]
                
                if width is not None and height is not None:
                    result['resolution'] = f"{width}x{height}"
            else:
                result['error'] = stderr.strip()
                
        except Exception as e:
            self.logger.error(f"检测流 {url} 时出错: {str(e)}")
            result['error'] = str(e)
            
        return result


if __name__ == "__main__":
    # 测试代码
    validator = StreamValidator()
    
    test_urls = [
        "http://example.com/stream.m3u8",  # 无效URL
        "rtmp://live.example.com/live/stream",  # 可能有效的RTMP
        "http://192.168.1.1:5000/stream.ts"  # 本地测试流
    ]
    
    for url in test_urls:
        print(f"\n检测URL: {url}")
        result = validator.validate_stream(url, timeout=5)
        print("结果:")
        for k, v in result.items():
            print(f"{k}: {v}")
