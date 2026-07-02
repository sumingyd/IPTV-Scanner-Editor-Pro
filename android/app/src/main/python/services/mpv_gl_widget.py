"""macOS 上使用 mpv render API 渲染视频到 QOpenGLWidget。

mpv v0.41+ 在 macOS 上不再支持 wid 嵌入式渲染，标准方案是使用
vo=libmpv + render API，由宿主程序提供 OpenGL 上下文并把帧渲染到 FBO。

实现要点：
- 子类化 QOpenGLWidget，让 Qt 负责 GL 上下文的生命周期
- render context 的创建逻辑在 _create_render_context_impl() 中，
  被 initializeGL() / setup_render_context() / paintGL() 三处复用：
  · initializeGL() 是标准入口（Qt 在第一次 paintGL 前调用，已 makeCurrent）
  · setup_render_context() 主动 makeCurrent 创建，处理 initializeGL()
    已被 show()+repaint() 过早触发的情况（initializeGL 只调用一次）
  · paintGL() 兜底，确保 render context 一定能被创建
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
        """保存 mpv handle 并尝试创建 render context。

        mpv_render_context_create 要求调用线程已拥有当前 OpenGL 上下文。
        QOpenGLWidget 的 GL 上下文只在 initializeGL / paintGL / resizeGL 期间
        处于 current 状态。

        关键问题：QOpenGLWidget.initializeGL() 只会在第一次 paintGL() 之前
        调用一次。如果在此之前 video_widget.show()+repaint() 已经触发过
        一次 paintEvent（此时 _mpv_handle 还没设置），initializeGL() 会被
        调用但什么都不做，之后 update() 只触发 paintGL() 而不会再调用
        initializeGL()，导致 render context 永远不会创建。

        解决方案：这里主动 makeCurrent() 并尝试创建 render context；
        若 GL 上下文还未就绪（makeCurrent 失败），则回退到 update()
        让 Qt 在下一帧 paintEvent 前调用 initializeGL()。paintGL() 中
        也加了兜底逻辑，确保 render context 一定能被创建。
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
            # 主动尝试创建 render context，处理 initializeGL() 已被过早调用的情况
            if not self._render_ctx:
                try:
                    self.makeCurrent()
                    try:
                        self._create_render_context_impl()
                    finally:
                        self.doneCurrent()
                except Exception as e:
                    # makeCurrent 失败说明 GL 上下文还未就绪，回退到 update() 触发 initializeGL
                    logger.debug(f"makeCurrent 创建 render context 失败，等待 initializeGL: {e}")
            # 触发 update：若 render context 已创建则走 paintGL 渲染；否则触发 initializeGL
            self.update()
            logger.info("mpv render context 初始化请求已提交(vo=libmpv, 等待GL上下文就绪)")
            return True
        except Exception as e:
            logger.error(f"setup_render_context失败: {e}")
            return False

    def cleanup(self):
        """释放 render context 资源。

        必须在 mpv_handle 销毁之前调用，否则会泄漏 GL 资源。
        同时重置 _mpv_handle，避免后续 paintGL() 兜底逻辑使用
        已失效的 handle 创建 render context（HDR 切换场景）。
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
        self._mpv_handle = None

    # ------------------------------------------------------------------
    # render context 创建（公共逻辑）
    # ------------------------------------------------------------------
    def _create_render_context_impl(self):
        """创建 mpv render context。调用前必须已经 makeCurrent。

        被 initializeGL() / setup_render_context() / paintGL() 三处复用，
        保证无论 initializeGL() 是否被过早触发，render context 都能被创建。
        """
        if not self._mpv_handle or self._render_ctx:
            return False
        try:
            from services.mpv_common import (
                render_context_create,
                render_context_set_update_callback,
            )
            self._render_ctx = render_context_create(self._mpv_handle)
            if not self._render_ctx:
                logger.error("创建mpv render context失败")
                return False
            # 必须保留 CFUNCTYPE 实例引用，否则会被 GC 导致崩溃
            self._on_render_update_cb = ctypes.CFUNCTYPE(
                None, ctypes.c_void_p
            )(self._on_render_update_cb_impl)
            render_context_set_update_callback(
                self._render_ctx, self._on_render_update_cb, ctypes.c_void_p(0)
            )
            self._gl_ready = True
            logger.info("mpv render context 创建成功(vo=libmpv, OpenGL Core Profile 3.2)")
            return True
        except Exception as e:
            logger.error(f"创建 render context 失败: {e}")
            self._gl_ready = False
            return False

    # ------------------------------------------------------------------
    # QOpenGLWidget 钩子
    # ------------------------------------------------------------------
    def initializeGL(self):
        """Qt 在第一次 paintEvent 前调用，此时 GL 上下文已 current。

        注意：initializeGL() 只会被调用一次。如果调用时 _mpv_handle 还没
        设置（例如 show()+repaint() 过早触发），这里会直接返回，render
        context 的创建由 setup_render_context() / paintGL() 兜底。
        """
        self._create_render_context_impl()

    def paintGL(self):
        # 兜底：若 initializeGL() 被过早调用导致 render context 未创建，
        # 在 paintGL() 中补创建（此时 GL 上下文已 current）
        if self._mpv_handle and not self._render_ctx and not self._gl_ready:
            self._create_render_context_impl()
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
