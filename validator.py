import subprocess
import time
import json
from typing import Dict, Optional
from log_manager import LogManager

class StreamValidator:
    """使用ffprobe检测视频流有效性"""
    
    def __init__(self):
        self.logger = LogManager()
        self.vlc_timeout = 10  # VLC验证超时时间(秒)
        
    def _get_vlc_path(self):
        """获取VLC路径"""
        import os
        import sys
        
        # 1. 尝试从打包后的路径查找
        if getattr(sys, 'frozen', False):
            base_path = os.path.dirname(sys.executable)
            exe_path = os.path.join(base_path, 'vlc', 'vlc.exe')
            if os.path.exists(exe_path):
                return exe_path
        
        # 2. 尝试从开发环境路径查找
        dev_path = os.path.join(os.path.dirname(__file__), 'vlc', 'vlc.exe')
        if os.path.exists(dev_path):
            return dev_path
            
        # 3. 尝试从系统PATH查找
        try:
            from shutil import which
            path = which('vlc')
            if path:
                return path
        except ImportError:
            pass
            
        return 'vlc'  # 最后尝试直接调用

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

    def _validate_with_vlc(self, url: str) -> bool:
        """使用VLC验证流是否可播放"""
        try:
            vlc_path = self._get_vlc_path()
            cmd = [
                vlc_path,
                '-I', 'dummy',  # 无界面模式
                '--play-and-exit',  # 播放后退出
                '--no-video-title-show',  # 不显示标题
                '--no-stats',  # 不显示统计信息
                '--no-snapshot-preview',  # 不显示截图预览
                '--quiet',  # 静默模式
                '--no-qt-error-dialogs',  # 不显示错误对话框
                '--no-qt-privacy-ask',  # 不显示隐私询问
                '--no-qt-video-autoresize',  # 不自动调整视频大小
                '--no-embedded-video',  # 不嵌入视频
                '--no-xlib',  # 禁用Xlib
                '--no-video',  # 禁用视频输出
                '--no-audio',  # 禁用音频输出
                '--no-osd',  # 禁用屏幕显示
                '--no-spu',  # 禁用字幕
                '--no-loop',  # 禁用循环
                '--no-repeat',  # 禁用重复
                '--no-random',  # 禁用随机播放
                '--no-sout-video',  # 禁用视频流输出
                '--no-sout-audio',  # 禁用音频流输出
                '--no-sout-spu',  # 禁用字幕流输出
                '--no-interact',  # 禁用交互
                url
            ]
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            try:
                _, _ = process.communicate(timeout=self.vlc_timeout)
                return process.returncode == 0
            except subprocess.TimeoutExpired:
                process.kill()
                return False
        except Exception as e:
            self.logger.warning(f"VLC验证失败: {str(e)}")
            return False

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
            # 先进行简单连接测试
            if url.startswith(('http://', 'https://')):
                import requests
                try:
                    response = requests.head(url, timeout=timeout/2)
                    if response.status_code < 400:
                        result['valid'] = True
                except requests.exceptions.RequestException as e:
                    result['error'] = f"连接失败: {str(e)}"
                    return result
            else:
                # 对于非HTTP协议，直接尝试连接
                try:
                    import socket
                    from urllib.parse import urlparse
                    parsed = urlparse(url)
                    host = parsed.hostname
                    port = parsed.port or 80
                    with socket.create_connection((host, port), timeout=timeout/2):
                        result['valid'] = True
                except Exception as e:
                    result['error'] = f"连接失败: {str(e)}"
                    return result
            
            # 如果连接成功，再获取详细信息
            if result['valid']:
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
                
                # 执行命令
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=False,  # 禁用自动解码
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                
                # 等待命令完成
                try:
                    stdout_bytes, stderr_bytes = process.communicate(timeout=timeout)
                    # 尝试UTF-8解码，失败则尝试GBK
                    try:
                        stdout = stdout_bytes.decode('utf-8', errors='replace')
                    except UnicodeDecodeError:
                        stdout = stdout_bytes.decode('gbk', errors='replace')
                    try:
                        stderr = stderr_bytes.decode('utf-8', errors='replace')
                    except UnicodeDecodeError:
                        stderr = stderr_bytes.decode('gbk', errors='replace')
                except subprocess.TimeoutExpired:
                    process.kill()
                    result['error'] = '检测超时'
                    return result
                
            # 计算延迟
            result['latency'] = int((time.time() - start_time) * 1000)
            
            # 解析输出
            if result['valid']:
                if process.returncode == 0:
                    try:
                        data = json.loads(stdout)
                        
                        # 尝试从不同位置获取频道名
                        service_name = None
                        
                        # 1. 首先尝试从programs获取
                        if 'programs' in data and len(data['programs']) > 0:
                            program = data['programs'][0]
                            if 'tags' in program and 'service_name' in program['tags']:
                                service_name = program['tags']['service_name']
                        
                        # 2. 如果没找到，尝试从streams获取
                        if not service_name and 'streams' in data and len(data['streams']) > 0:
                            for stream in data['streams']:
                                if 'tags' in stream and 'service_name' in stream['tags']:
                                    service_name = stream['tags']['service_name']
                                    break
                        
                        # 3. 如果还是没找到，尝试从format获取
                        if not service_name and 'format' in data and 'tags' in data['format'] and 'service_name' in data['format']['tags']:
                            service_name = data['format']['tags']['service_name']
                        
                        # 处理获取到的service_name
                        if service_name is not None:
                            try:
                                # 处理字符串类型的service_name
                                if isinstance(service_name, str):
                                    # 优先尝试直接处理原始字符串
                                    result['service_name'] = service_name
                                    
                                    # 如果包含乱码字符，尝试修复
                                    if any(c in service_name for c in ['', '?', '¿']):
                                        # 精简编码列表，优先中文编码
                                        encodings = [
                                            'gb18030',     # 首选中文编码
                                            'gbk',         # 次选
                                            'big5',        # 繁体中文
                                            'utf-8',       # Unicode
                                            'latin1'       # 最后尝试
                                        ]
                                        
                                        # 尝试直接解码原始字符串
                                        for encoding in encodings:
                                            try:
                                                decoded = service_name.encode('raw_unicode_escape').decode(encoding)
                                                if not any(c in decoded for c in ['', '?', '¿']):  # 检查常见乱码字符
                                                    result['service_name'] = decoded
                                                    break
                                            except Exception as e:
                                                continue
                                        
                                        # 如果直接解码失败，尝试自动探测(仅在chardet可用时)
                                        if 'service_name' not in result or any(c in result['service_name'] for c in ['', '?', '¿']):
                                            try:
                                                import chardet
                                                # 获取原始字节数据
                                                if isinstance(service_name, str):
                                                    byte_data = service_name.encode('raw_unicode_escape')
                                                else:
                                                    byte_data = service_name
                                                
                                                # 探测编码但限制为中文相关编码
                                                detected = chardet.detect(byte_data)
                                                if detected['confidence'] > 0.7:  # 置信度高于70%
                                                    # 只使用中文相关编码
                                                    chinese_encodings = ['gbk', 'gb18030', 'big5', 'utf-8', 'utf-16']
                                                    if detected['encoding'].lower() in chinese_encodings:
                                                        decoded = byte_data.decode(detected['encoding'])
                                                        result['service_name'] = decoded
                                            except ImportError:
                                                self.logger.info("chardet模块不可用，跳过自动编码探测")
                                            except Exception as e:
                                                self.logger.info(f"自动探测失败: {str(e)}")
                                        
                                        # 所有尝试失败，保留原始字符串
                                        if 'service_name' not in result:
                                            result['service_name'] = service_name
                                            self.logger.warning(f"无法解码service_name: {service_name}")
                            except Exception as e:
                                self.logger.error(f"处理service_name时发生异常: {str(e)}")
                                result['service_name'] = service_name
                            
                            # 处理bytes类型
                            if isinstance(service_name, bytes):
                                try:
                                    result['service_name'] = service_name.decode('utf-8')
                                except UnicodeDecodeError:
                                    try:
                                        result['service_name'] = service_name.decode('gbk', errors='replace')
                                    except UnicodeDecodeError:
                                        result['service_name'] = service_name.decode('latin1', errors='replace')
                            # 其他类型转换为字符串
                            else:
                                result['service_name'] = str(service_name)
                        
                        # 确保service_name字段存在
                        if 'service_name' not in result:
                            result['service_name'] = "未知频道"
                        
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
            
        # 如果ffprobe检测通过但仍有疑问，使用VLC二次验证
        if result['valid'] and result.get('error') is None:
            if not self._validate_with_vlc(url):
                result['valid'] = False
                result['error'] = "VLC验证失败"
            
        return result
