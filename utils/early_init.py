import sys
import os


def _patch_py314_traceback_bug():
    """Python 3.14 traceback.FrameSummary.line 在 self._lines 为 None 时崩溃。

    AttributeError: 'NoneType' object has no attribute 'partition'
      File "traceback.py", line 379, in line
        return self._lines.partition("\\n")[0].strip()

    当帧来自已卸载模块或 C 扩展时 _lines 可能为 None。
    此 monkey-patch 让 line 属性安全返回 None。"""
    try:
        import traceback as _tb
        _FrameSummary = _tb.FrameSummary
        _orig_line = _FrameSummary.line.fget

        def _safe_line(self):
            if getattr(self, '_lines', None) is None:
                return None
            try:
                return _orig_line(self)
            except AttributeError:
                return None

        _FrameSummary.line = property(_safe_line)
    except Exception:
        pass


def _patch_py314_asyncio_exception_handler():
    """Python 3.14 asyncio Handle.__init__ 在某些场景下抛出
    TypeError: __init__() should return None, not 'NoneType'

    这会导致 asyncio 默认异常处理器崩溃，进而触发 traceback 格式化崩溃。
    安装自定义异常处理器，避免 traceback 格式化时访问坏帧。"""
    try:
        import asyncio

        def _safe_exception_handler(loop, context):
            msg = context.get('message', 'Unhandled exception in asyncio')
            exception = context.get('exception')
            if exception is not None:
                import logging
                logging.getLogger('asyncio').error(
                    "%s: %s", msg, exception, exc_info=False
                )
            else:
                import logging
                logging.getLogger('asyncio').error(msg)

        _orig_set_handler = asyncio.AbstractEventLoop.set_exception_handler

        def _patched_set_handler(self, handler):
            _orig_set_handler(self, handler or _safe_exception_handler)

        asyncio.AbstractEventLoop.set_exception_handler = _patched_set_handler
    except Exception:
        pass


def _patch_py314_gc_threshold():
    """Python 3.14 GC 在多线程 native 操作（datetime/shiboken）期间触发 access violation。

    增大 GC 阈值减少自动触发频率，由 QTimer 定期手动 collect 替代。"""
    try:
        import gc
        gc.set_threshold(10000, 50, 50)
    except Exception:
        pass


def setup_environment():
    _patch_py314_traceback_bug()
    _patch_py314_asyncio_exception_handler()
    _patch_py314_gc_threshold()
    if sys.platform == 'darwin' and getattr(sys, 'frozen', False):
        try:
            import certifi
            os.environ['SSL_CERT_FILE'] = certifi.where()
            os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()
        except ImportError:
            _cert_path = os.path.join(os.path.dirname(sys.executable), 'resources', 'cert.pem')
            if os.path.exists(_cert_path):
                os.environ['SSL_CERT_FILE'] = _cert_path
                os.environ['REQUESTS_CA_BUNDLE'] = _cert_path

    if sys.platform.startswith('linux') and 'ANDROID_ARGUMENT' not in os.environ:
        session_type = os.environ.get('XDG_SESSION_TYPE', '').lower()
        wayland_display = os.environ.get('WAYLAND_DISPLAY', '')
        is_wayland_env = (session_type == 'wayland') or (bool(wayland_display) and session_type != 'x11')
        if is_wayland_env and not os.environ.get('QT_QPA_PLATFORM'):
            os.environ['QT_QPA_PLATFORM'] = 'xcb'

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))