"""macOS 上使用 mpv render API 渲染视频到 QOpenGLWidget。

mpv v0.41+ 在 macOS 上不再支持 wid 嵌入式渲染，标准方案是使用
vo=libmpv + render API，由宿主程序提供 OpenGL 上下文并把帧渲染到 FBO。

实现要点：
- 子类化 QOpenGLWidget，让 Qt 负责 GL 上下文的生命周期
- 在 initializeGL() 中创建 mpv_render_context（此时 Qt 已 makeCurrent）
- 在 paintGL() 中调用 mpv_render_context_render 把帧绘制到默认 FBO
- mpv 通过 update_callback 通知需要重绘，信号转发到 GUI 线程触发 update()
- macOS OpenGL 3.2+ 仅支持 Core Profile，使用 CompatibilityProfile+3.2 是无效组合
"""

import sys
import ctypes

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QSurfaceFormat
from PySide6.QtOpenGLWidgets import QOpenGLWidget

from core.log_manager import global_logger as logger


class MpvGLWidget(QOpenGLWidget):
    """使用 mpv render API 渲染视频的 QOpenGLWidget（macOS 专用）。"""

    # mpv 渲染线程通过此信号触发 GUI 线程的重绘请求
    _render_update_signal = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._render_ctx = None
        self._mpv_handle = None
        self._on_render_update_cb = None
        self._gl_ready = False

        # macOS OpenGL 3.2+ 只支持 Core Profile；
        # CompatibilityProfile + version(3,2) 是无效组合，会导致上下文创建失败。
        fmt = QSurfaceFormat()
        fmt.setVersion(3, 2)
        fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
        fmt.setDepthBufferSize(0)
        fmt.setStencilBufferSize(0)
        fmt.setSwapInterval(0)
        self.setFormat(fmt)

        self.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DontCreateNativeAncestors, True)
        self.setMinimumSize(1, 1)

        # update_callback 来自 mpv 渲染线程，必须通过 QueuedConnection 转发到 GUI 线程
        self._render_update_signal.connect(
            self._on_render_update_main, Qt.ConnectionType.QueuedConnection
        )

    # ------------------------------------------------------------------
    # 对外接口
    # ------------------------------------------------------------------
    def setup_render_context(self, mpv_handle):
        """保存 mpv handle；真正的 render context 在 initializeGL 中创建。

        mpv_render_context_create 要求调用线程已拥有当前 OpenGL 上下文，
        QOpenGLWidget 的 GL 上下文只在 initializeGL / paintGL / resizeGL 期间
        处于 current 状态，因此这里不能直接创建，只能保存 handle 并触发
        一次 update()，让 Qt 在下一帧 paintEvent 前调用 initializeGL。
        """
        if sys.platform != 'darwin':
            return False
        try:
            from services.mpv_common import init_render_api, MPV_AVAILABLE
            if not MPV_AVAILABLE:
                logger.error("libmpv不可用，无法创建render context")
                return False
            init_render_api()
            self._mpv_handle = mpv_handle
            # 触发 paintEvent -> initializeGL（第一次绘制时）
            self.update()
            logger.info("mpv render context 初始化请求已提交(vo=libmpv, 等待GL上下文就绪)")
            return True
        except Exception as e:
            logger.error(f"setup_render_context失败: {e}")
            return False

    def cleanup(self):
        """释放 render context 资源。

        必须在 mpv_handle 销毁之前调用，否则会泄漏 GL 资源。
        """
        if self._render_ctx:
            try:
                from services.mpv_common import render_context_free
                render_context_free(self._render_ctx)
            except Exception as e:
                logger.warning(f"render_context_free异常: {e}")
            self._render_ctx = None
        self._on_render_update_cb = None
        self._gl_ready = False

    # ------------------------------------------------------------------
    # QOpenGLWidget 钩子
    # ------------------------------------------------------------------
    def initializeGL(self):
        """Qt 在第一次 paintEvent 前调用，此时 GL 上下文已 current。"""
        if not self._mpv_handle or self._render_ctx:
            return
        try:
            from services.mpv_common import (
                render_context_create,
                render_context_set_update_callback,
            )
            self._render_ctx = render_context_create(self._mpv_handle)
            if not self._render_ctx:
                logger.error("创建mpv render context失败")
                return
            # 必须保留 CFUNCTYPE 实例引用，否则会被 GC 导致崩溃
            self._on_render_update_cb = ctypes.CFUNCTYPE(
                None, ctypes.c_void_p
            )(self._on_render_update_cb_impl)
            render_context_set_update_callback(
                self._render_ctx, self._on_render_update_cb, ctypes.c_void_p(0)
            )
            self._gl_ready = True
            logger.info("mpv render context 创建成功(vo=libmpv, OpenGL Core Profile 3.2)")
        except Exception as e:
            logger.error(f"initializeGL 创建 render context 失败: {e}")
            self._gl_ready = False

    def paintGL(self):
        if not self._gl_ready or not self._render_ctx:
            return
        try:
            fbo = self.defaultFramebufferObject()
            w = self.width()
            h = self.height()
            if w <= 0 or h <= 0:
                return
            from services.mpv_common import (
                render_context_render,
                render_context_report_swap,
            )
            ret = render_context_render(self._render_ctx, fbo, w, h, flip_y=True)
            if ret < 0:
                # 错误码改为 warning 级别，便于排查渲染问题
                logger.warning(f"mpv_render_context_render 错误码: {ret}")
            render_context_report_swap(self._render_ctx)
        except Exception as e:
            logger.warning(f"paintGL 异常: {e}")

    def resizeGL(self, w, h):
        if self._gl_ready:
            self.update()

    # ------------------------------------------------------------------
    # mpv update_callback 处理
    # ------------------------------------------------------------------
    def _on_render_update_cb_impl(self, _ctx_ptr):
        """由 mpv 渲染线程调用：通知有新帧需要重绘。

        不能在此直接调用 self.update()（跨线程访问 GUI），
        通过 signal 触发 GUI 线程响应。
        """
        try:
            self._render_update_signal.emit()
        except Exception:
            # 信号发射失败时静默忽略，避免在退出阶段崩溃
            pass

    def _on_render_update_main(self):
        """GUI 线程响应 mpv 重绘请求。"""
        if self._gl_ready:
            self.update()
