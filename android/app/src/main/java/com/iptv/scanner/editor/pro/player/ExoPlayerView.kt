package com.iptv.scanner.editor.pro.player

import android.content.Context
import android.util.AttributeSet
import android.view.SurfaceHolder
import android.view.SurfaceView

/**
 * ExoPlayer 视频渲染视图，基于 [SurfaceView]。
 *
 * 设计要点（与 MPVView 对齐）：
 * 1. 使用 SurfaceView 而非 TextureView：ExoPlayer 通过 setVideoSurfaceHolder
 *    绑定 Surface 进行 MediaCodec 直接渲染，SurfaceView 的 Surface 由
 *    ANativeWindow 支撑，兼容性最佳
 * 2. ExoPlayer 实例在 [ExoPlayerController] 中创建，本类仅持有 Controller 引用
 *    用于 surface 生命周期回调时绑定/解绑
 * 3. surfaceCreated 时调用 setVideoSurfaceHolder，surfaceDestroyed 时 clearVideoSurface
 * 4. surfaceChanged 无需处理（ExoPlayer 自动适配 surface 尺寸变化）
 *
 * 与 MPVView 的差异：
 * - 不需要 initialize（ExoPlayer 在 Controller 构造时已创建）
 * - 不需要 vo/hwdec 配置（ExoPlayer 内部管理解码与渲染）
 * - SurfaceView 默认 Z-order，Compose 控制层可叠加其上（容器需透明背景）
 *
 * companion 中的 DEFAULT_VO / DEFAULT_HWDEC 仅为兼容 PlayerSettingsPanel 的
 * vo/hwdec 显示逻辑（ExoPlayer 不使用这些参数，但 UI 面板可能读取常量做判断）。
 */
class ExoPlayerView @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null
) : SurfaceView(context, attrs), SurfaceHolder.Callback {

    private var controller: ExoPlayerController? = null

    /**
     * 绑定 [ExoPlayerController]，注册 SurfaceHolder.Callback。
     * 由 ExoPlayerController.attachView 调用。
     */
    fun attachController(controller: ExoPlayerController) {
        this.controller = controller
        holder.addCallback(this)
    }

    // ---- SurfaceHolder.Callback ----

    override fun surfaceCreated(holder: SurfaceHolder) {
        // 将 SurfaceHolder 绑定到 ExoPlayer，开始视频渲染
        controller?.exoPlayer?.setVideoSurfaceHolder(holder)
    }

    override fun surfaceChanged(holder: SurfaceHolder, format: Int, width: Int, height: Int) {
        // ExoPlayer 自动处理 surface 尺寸变化，无需手动干预
    }

    override fun surfaceDestroyed(holder: SurfaceHolder) {
        // 解绑 Surface，停止渲染（避免 surface 释放后继续写入导致崩溃）
        controller?.exoPlayer?.clearVideoSurface()
    }

    companion object {
        /** 默认 video output 标识（仅为兼容 PlayerSettingsPanel 显示，ExoPlayer 不使用） */
        const val DEFAULT_VO = "exo"

        /** 默认硬件解码标识（仅为兼容 PlayerSettingsPanel 显示，ExoPlayer 不使用） */
        const val DEFAULT_HWDEC = "auto"
    }
}
