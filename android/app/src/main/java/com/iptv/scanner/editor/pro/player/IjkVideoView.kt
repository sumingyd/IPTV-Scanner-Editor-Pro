package com.iptv.scanner.editor.pro.player

import android.content.Context
import android.graphics.PixelFormat
import android.util.AttributeSet
import android.view.SurfaceHolder
import android.view.SurfaceView

/**
 * 基于 SurfaceView 的 IJKPlayer 视频渲染视图。
 *
 * 与 [com.iptv.scanner.editor.pro.mpv.MPVView] 对齐的设计：
 * - 使用 SurfaceView（ANativeWindow 支撑，IjkMediaPlayer.setDisplay 直接渲染）
 * - 不用 TextureView（IJK 的 SurfaceHolder 绑定方式不兼容 SurfaceTexture）
 * - SurfaceView 默认 Z-order 在普通 View 之后，Compose 控制层可叠加显示
 * - 像素格式设为 RGBA_8888（与 MPVView 一致，确保兼容性）
 *
 * 生命周期：
 * 1. Compose AndroidView 创建 IjkVideoView
 * 2. Controller.attachView(view) → view.attachController(this) → 注册 SurfaceHolder.Callback
 * 3. surfaceCreated → controller.attachSurface(holder) → ijkPlayer.setDisplay(holder)
 * 4. playFile 时 controller 在 prepareAsync 前调用 setDisplay(currentHolder)
 * 5. surfaceDestroyed → controller.attachSurface(null) → ijkPlayer.setDisplay(null)
 *
 * @see IjkController 控制器实现
 * @see com.iptv.scanner.editor.pro.mpv.MPVView MPV 的对应实现（参考模式）
 */
class IjkVideoView @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null
) : SurfaceView(context, attrs), SurfaceHolder.Callback {

    private var controller: IjkController? = null

    /**
     * 绑定控制器并注册 SurfaceHolder 回调。
     * 由 [IjkController.attachView] 调用。
     */
    fun attachController(controller: IjkController) {
        this.controller = controller
        // 像素格式与 MPVView 对齐（RGBA_8888）
        holder.setFormat(PixelFormat.RGBA_8888)
        holder.addCallback(this)
    }

    // ---- SurfaceHolder.Callback ----

    override fun surfaceCreated(holder: SurfaceHolder) {
        // 绑定 SurfaceHolder 到 IjkMediaPlayer
        controller?.attachSurface(holder)
    }

    override fun surfaceChanged(holder: SurfaceHolder, format: Int, width: Int, height: Int) {
        // surface 尺寸变化时重新绑定（IJK 的 setDisplay 可安全重复调用）
        controller?.attachSurface(holder)
    }

    override fun surfaceDestroyed(holder: SurfaceHolder) {
        // 解绑 Surface，避免 IJK 在 surface 销毁后继续渲染导致崩溃
        controller?.attachSurface(null)
    }

    companion object {
        /** 默认 video output 标识（仅为与 MPVView 兼容显示，IJK 无 vo 概念） */
        const val DEFAULT_VO = "ijk"

        /** 默认硬件解码标识（仅为与 MPVView 兼容显示，IJK 通过 option 配置） */
        const val DEFAULT_HWDEC = "auto"
    }
}
