"""
services/node_service.py - Node.js 运行时服务管理模块

负责：
- 启动/停止 Node.js 进程（assets/node/index.js）
- 检测服务就绪状态
- 静默加载默认播放列表
- 服务状态信号通知

架构说明：
Python 桌面端通过 subprocess 启动 Node.js 服务容器，
Node 容器提供 migu API、M3U、EPG、流代理等能力，
实现 server + player 合体，多端多平台代码复用。
"""

import os
import sys
import socket
import subprocess
import time
from typing import Optional, Callable

from PySide6.QtCore import QObject, Signal, QTimer

from core.log_manager import global_logger as logger


class NodeService(QObject):
    """Node.js 服务管理器

    负责：
    - 启动/停止 Node.js 进程
    - 检测服务就绪状态
    - 静默加载默认播放列表
    - 服务状态信号通知
    """

    service_ready = Signal(str)
    service_error = Signal(str)
    service_stopped = Signal()
    playlist_loaded = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.process: Optional[subprocess.Popen] = None
        self.is_ready: bool = False
        self.base_url: Optional[str] = None

        self._auto_start: bool = True
        self._node_path: str = ""
        self._port: int = 2699
        self._script_dir: Optional[str] = None
        self._service_url: str = "http://127.0.0.1:2699"

        self.on_playlist_loaded: Optional[Callable] = None
        self.on_status_message: Optional[Callable[[str], None]] = None

        self._main_window = None

    def set_config(self, auto_start: bool, node_path: str, port: int, script_dir: str, service_url: str = None):
        self._auto_start = auto_start
        self._node_path = node_path
        self._port = port
        self._script_dir = script_dir
        self._service_url = service_url or f"http://127.0.0.1:{port}"
        self.base_url = self._service_url

    def set_main_window(self, main_window):
        self._main_window = main_window
        if hasattr(main_window, 'config') and main_window.config:
            node_config = main_window.config.get_node_config()
            self.set_config(
                auto_start=node_config.get('auto_start', True),
                node_path=node_config.get('node_path', 'huanghe.exe'),
                port=node_config.get('port', 2699),
                script_dir=self._get_node_script_dir(),
                service_url=node_config.get('service_url', f"http://127.0.0.1:{node_config.get('port', 2699)}")
            )

    def start(self, silent: bool = True) -> bool:
        if self.is_ready:
            logger.info("Node.js 服务已就绪，跳过启动")
            self.service_ready.emit(self.base_url)
            return True

        node_exe = self._get_node_executable(self._node_path)
        script_dir = self._script_dir or self._get_node_script_dir()

        index_js = os.path.join(script_dir, 'index.js')
        if not os.path.exists(index_js):
            logger.warning(f"Node.js 脚本不存在: {index_js}，跳过启动")
            if not silent:
                self._show_error_message(f"脚本不存在: {index_js}")
            self.service_error.emit(f"脚本不存在: {index_js}")
            return False

        if not node_exe:
            logger.warning(
                "未找到 Node.js 运行时，跳过启动服务。如需使用直播服务，请将 huanghe.exe 或 node 放在程序同目录或系统 PATH 中。")
            if not silent:
                self._show_error_message("未找到 Node.js 运行时，请安装 Node.js 或放置 huanghe.exe")
            self.service_error.emit("未找到 Node.js 运行时")
            return False

        self._ensure_node_deps(script_dir, node_exe)

        if self._is_port_occupied(self._port):
            logger.info(f"端口 {self._port} 已被占用，尝试连接现有服务")
            if self._check_service_ready_sync(max_retries=3):
                self.is_ready = True
                self.service_ready.emit(self.base_url)
                self._on_service_ready()
                return True
            return False

        try:
            creationflags = 0
            if sys.platform == 'win32':
                creationflags = subprocess.CREATE_NO_WINDOW

            self.process = subprocess.Popen(
                [node_exe, 'index.js'],
                cwd=script_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=creationflags,
                text=True
            )

            self._ready_retries = 0
            self._ready_timer = QTimer(self)
            self._ready_timer.setInterval(500)
            self._ready_timer.timeout.connect(self._check_ready_async)
            self._ready_timer.start()
            return True

        except Exception as e:
            logger.error(f"启动 Node.js 服务失败: {e}")
            if not silent:
                self._show_error_message(f"启动失败: {str(e)}")
            self.service_error.emit(str(e))
            return False

    def _check_ready_async(self):
        """异步检测服务就绪（不阻塞主线程）"""
        self._ready_retries += 1
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('127.0.0.1', self._port))
            sock.close()
            if result == 0:
                self._ready_timer.stop()
                self.is_ready = True
                self.service_ready.emit(self.base_url)
                self._on_service_ready()
                return
        except Exception:
            pass

        if self._ready_retries >= 30:
            self._ready_timer.stop()
            if self.process and self.process.poll() is not None:
                try:
                    stderr = self.process.stderr.read() if self.process.stderr else ''
                    logger.error(f"Node.js 服务启动失败: {stderr[:300]}")
                except Exception:
                    pass
            else:
                logger.warning("Node.js 服务启动超时")
            self.service_error.emit("服务启动超时")

    def _ensure_node_deps(self, script_dir: str, node_exe: str):
        """检查并安装 Node.js 依赖"""
        node_modules = os.path.join(script_dir, 'node_modules')
        if not os.path.exists(node_modules):
            logger.info("Node.js 依赖未安装，正在安装...")
            try:
                install_proc = subprocess.Popen(
                    [node_exe, 'install'],
                    cwd=script_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0,
                    text=True
                )
                install_proc.wait(timeout=60)
                if install_proc.returncode == 0:
                    logger.info("Node.js 依赖安装成功")
                else:
                    logger.warning(f"Node.js 依赖安装失败: exit code {install_proc.returncode}")
            except Exception as e:
                logger.warning(f"Node.js 依赖安装异常: {e}")

    def stop(self):
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=3)
                logger.info("Node.js 服务已停止")
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
                logger.info("Node.js 服务已被强制停止")
            except Exception as e:
                logger.error(f"停止 Node.js 服务失败: {e}")
            finally:
                self.process = None
                self.is_ready = False
                self.service_stopped.emit()

    def is_running(self) -> bool:
        return self.is_ready or (self.process is not None and self.process.poll() is None)

    def get_base_url(self) -> Optional[str]:
        return self.base_url

    def load_default_playlist_silent(self):
        if not self.is_ready:
            logger.warning("Node.js 服务未就绪，无法加载播放列表")
            self.playlist_loaded.emit(False)
            return

        if self._main_window and hasattr(self._main_window, '_apply_m3u_content'):
            url = f"{self.base_url}/m3u"
            try:
                import requests
                response = requests.get(
                    url,
                    timeout=10,
                    headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
                )
                response.raise_for_status()
                content = response.text

                if '#EXTM3U' in content:
                    self._main_window._apply_m3u_content(content, url)
                    self._show_status_message(
                        self._main_window.language_manager.tr("playlist_loaded", "播放列表加载成功")
                    )
                    logger.info("静默加载默认播放列表成功")
                    self.playlist_loaded.emit(True)
                else:
                    logger.warning("默认播放列表内容无效")
                    self.playlist_loaded.emit(False)
            except Exception as e:
                logger.warning(f"静默加载默认播放列表失败: {e}")
                self.playlist_loaded.emit(False)
        else:
            logger.warning("无法静默加载播放列表：主窗口引用未设置或缺少 _apply_m3u_content 方法")
            self.playlist_loaded.emit(False)

    def _get_node_executable(self, node_path: str) -> Optional[str]:
        import shutil

        if getattr(sys, 'frozen', False):
            exe_dir = os.path.dirname(sys.executable)
        else:
            exe_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        if os.path.isabs(node_path) and os.path.exists(node_path):
            return node_path

        rel_path = os.path.join(exe_dir, node_path)
        if os.path.exists(rel_path):
            return rel_path

        exe_node = os.path.join(exe_dir, 'huanghe.exe')
        if os.path.exists(exe_node):
            return exe_node

        node_in_path = shutil.which('node')
        if node_in_path:
            return node_in_path

        return None

    def _get_node_script_dir(self) -> str:
        if getattr(sys, 'frozen', False):
            if hasattr(sys, '_MEIPASS'):
                base_path = sys._MEIPASS
            else:
                base_path = os.path.dirname(sys.executable)
        else:
            base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        possible_paths = [
            os.path.join(base_path, 'assets', 'node'),
            os.path.join(base_path, 'node'),
            os.path.join(base_path, '.venv', 'library', 'node'),
            os.path.join(os.path.dirname(base_path), 'assets', 'node'),
        ]

        for script_dir in possible_paths:
            index_js = os.path.join(script_dir, 'index.js')
            if os.path.exists(index_js):
                logger.info(f"找到 Node.js 脚本目录: {script_dir}")
                return script_dir

        logger.warning(f"未找到 Node.js 脚本目录，尝试过的路径: {possible_paths}")
        return os.path.join(base_path, 'assets', 'node')

    def _is_port_occupied(self, port: int) -> bool:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('127.0.0.1', port))
        sock.close()
        return result == 0

    def _check_service_ready_sync(self, max_retries: int = 3) -> bool:
        """同步检测服务就绪（仅用于端口已占用时的快速探测，最多1.5秒）"""
        for i in range(max_retries):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(0.5)
                result = sock.connect_ex(('127.0.0.1', self._port))
                sock.close()
                if result == 0:
                    return True
            except Exception:
                pass
            time.sleep(0.5)
        return False

    def _on_service_ready(self):
        self._show_status_message(f"直播服务已启动 (端口 {self._port})")
        QTimer.singleShot(300, self.load_default_playlist_silent)

    def _show_status_message(self, message: str):
        if self.on_status_message:
            self.on_status_message(message)
        elif self._main_window and hasattr(self._main_window, 'status_bar_show_message'):
            self._main_window.status_bar_show_message(message)
        else:
            logger.info(message)

    def _show_error_message(self, message: str):
        if self._main_window and hasattr(self._main_window, 'show_error_message'):
            self._main_window.show_error_message(message)
        else:
            logger.error(message)


def get_node_service(parent=None) -> NodeService:
    if not hasattr(get_node_service, '_instance'):
        get_node_service._instance = NodeService(parent)
    return get_node_service._instance