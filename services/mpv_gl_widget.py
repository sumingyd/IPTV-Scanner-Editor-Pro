import ctypes
import sys

from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QSurfaceFormat

from core.log_manager import global_logger as logger


class MpvGLWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._render_ctx = None
        self._mpv_handle = None
        self._gl_widget = None
        self._on_render_update_cb = None
        self._pending_render = False
        self._render_timer = QTimer(self)
        self._render_timer.setInterval(16)
        self._render_timer.timeout.connect(self._do_render)
        self.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DontCreateNativeAncestors, True)

    def setup_render_context(self, mpv_handle):
        if sys.platform != 'darwin':
            return False
        try:
            from services.mpv_common import (
                init_render_api, render_context_create,
                render_context_set_update_callback, MPV_AVAILABLE,
            )
            if not MPV_AVAILABLE:
                logger.error("libmpv不可用，无法创建render context")
                return False
            init_render_api()
            self._mpv_handle = mpv_handle
            self._render_ctx = render_context_create(mpv_handle)
            if not self._render_ctx:
                logger.error("创建mpv render context失败")
                return False
            self._on_render_update_cb = ctypes.CFUNCTYPE(None, ctypes.c_void_p)(self._on_render_update)
            render_context_set_update_callback(self._render_ctx, self._on_render_update_cb, ctypes.c_void_p(0))
            self._try_create_gl_widget()
            logger.info("mpv render context创建成功(vo=libmpv)")
            return True
        except Exception as e:
            logger.error(f"setup_render_context失败: {e}")
            return False

    def _try_create_gl_widget(self):
        try:
            from PySide6.QtOpenGLWidgets import QOpenGLWidget
            from PySide6.QtGui import QOpenGLContext

            fmt = QSurfaceFormat()
            fmt.setVersion(3, 2)
            fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CompatibilityProfile)
            fmt.setDepthBufferSize(0)
            fmt.setStencilBufferSize(0)
            fmt.setSwapInterval(0)
            QSurfaceFormat.setDefaultFormat(fmt)

            inner = QOpenGLWidget(self)
            inner.setFormat(fmt)
            inner.setMinimumSize(1, 1)
            self._gl_widget = inner

            layout = __import__('PySide6.QtWidgets', fromlist=['QVBoxLayout']).QVBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(inner)

            inner.update()

            from PySide6.QtCore import QTimer as _QT
            _QT.singleShot(200, self._initial_render)
        except ImportError:
            logger.warning("QOpenGLWidget不可用，使用QWindow方案")
            self._try_create_qwindow()

    def _try_create_qwindow(self):
        try:
            from PySide6.QtGui import QWindow, QSurfaceFormat
            from PySide6.QtOpenGL import QOpenGLContext

            fmt = QSurfaceFormat()
            fmt.setVersion(3, 2)
            fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CompatibilityProfile)
            fmt.setDepthBufferSize(0)
            fmt.setStencilBufferSize(0)

            self._qwindow = QWindow(self.windowHandle())
            self._qwindow.setSurfaceType(QWindow.SurfaceType.OpenGLSurface)
            self._qwindow.setFormat(fmt)
            self._qwindow.create()

            self._gl_ctx = QOpenGLContext(self)
            self._gl_ctx.setFormat(fmt)
            self._gl_ctx.create()
            self._gl_ctx.makeCurrent(self._qwindow)

            from PySide6.QtCore import QTimer as _QT
            _QT.singleShot(200, self._initial_render)
        except Exception as e:
            logger.error(f"创建QWindow GL上下文失败: {e}")

    def _initial_render(self):
        if self._gl_widget:
            self._gl_widget.makeCurrent()
        self._do_render()
        self._render_timer.start()

    def _on_render_update(self, ctx_ptr):
        self._pending_render = True

    def _do_render(self):
        if not self._render_ctx or not self._pending_render:
            return
        self._pending_render = False
        try:
            if self._gl_widget:
                self._gl_widget.makeCurrent()
                fbo = self._gl_widget.defaultFramebufferObject()
                w = self._gl_widget.width()
                h = self._gl_widget.height()
            else:
                return
            if w <= 0 or h <= 0:
                return
            from services.mpv_common import render_context_render, render_context_report_swap
            ret = render_context_render(self._render_ctx, fbo, w, h, flip_y=True)
            if ret < 0:
                logger.debug(f"render_context_render: {ret}")
            if self._gl_widget:
                self._gl_widget.doneCurrent()
                self._gl_widget.update()
            render_context_report_swap(self._render_ctx)
        except Exception as e:
            logger.debug(f"_do_render异常: {e}")

    def cleanup(self):
        self._render_timer.stop()
        if self._render_ctx:
            try:
                from services.mpv_common import render_context_free
                render_context_free(self._render_ctx)
            except Exception:
                pass
            self._render_ctx = None
        self._on_render_update_cb = None

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._gl_widget:
            self._gl_widget.setGeometry(0, 0, self.width(), self.height())
        if self._render_ctx:
            self._pending_render = True