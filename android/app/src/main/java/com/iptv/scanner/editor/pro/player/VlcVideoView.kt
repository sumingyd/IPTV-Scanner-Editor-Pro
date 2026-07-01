package com.iptv.scanner.editor.pro.player

import android.content.Context
import android.util.AttributeSet
import android.util.Log
import android.view.SurfaceHolder
import android.view.SurfaceView

/**
 * 基于 SurfaceView 的 VLC 视频渲染视图。
 *
 * 与 [MPVView] 设计对齐：使用 SurfaceView 而非 TextureView，
 * 因为 VLC 的 IVLCVout 通过 ANativeWindow 直接绑定 Surface 渲染，
 * TextureView 的 SurfaceTexture 不兼容。
 *
 * 生命周期：
 * 1. [VlcController.attachView] → 调用 [attachController] → 注册 SurfaceHolder.Callback
 * 2. surfaceCreated → vlcVout.setVideoView(this) + attachViews（VLC 绑定 Surface）
 * 3. surfaceChanged → vlcVout.setWindowSize(w, h)（通知 VLC Surface 尺寸变化）
 * 4. surfaceDestroyed → vlcVout.detachViews()（VLC 解绑 Surface）
 * 5. VlcController.detach → mediaPlayer.release() + libVLC.release()
 *
 * SurfaceHolder.Callback 注册时机：
 * - 在 [attachController] 中调用 holder.addCallback(this)
 * - 如果 Surface 已创建，addCallback 会立即触发 surfaceCreated
 * - 如果 Surface 未创建，等 SurfaceView layout 后系统触发 surfaceCreated
 */
class VlcVideoView @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null
) : SurfaceView(context, attrs), SurfaceHolder.Callback {

    companion object {
        private const val TAG = "VlcVideoView"

        /**
         * 默认 video output 标识（仅为兼容显示，VLC 使用自有渲染管线）。
         * 与 [MPVView.DEFAULT_VO] 对齐，UI 层统一显示播放器 vo/hwdec 信息。
         */
        const val DEFAULT_VO = "vlc"

        /**
         * 默认硬件解码模式标识（仅为兼容显示）。
         * VLC 的硬解通过 --codec=mediacodec_ndk 配置，非 mpv 的 hwdec 体系。
         */
        const val DEFAULT_HWDEC = "auto"
    }

    /** 持有的 VLC 控制器引用（由 attachController 设置） */
    private var controller: VlcController? = null

    /**
     * 绑定 [VlcController]，注册 SurfaceHolder.Callback。
     *
     * 由 [VlcController.attachView] 调用，将 Controller 与 View 关联：
     * - 存储 controller 引用
     * - 注册 SurfaceHolder.Callback（若 Surface 已存在会立即触发 surfaceCreated）
     */
    fun attachController(controller: VlcController) {
        this.controller = controller
        holder.addCallback(this)
        Log.i(TAG, "VlcVideoView attached to VlcController")
    }

    // -----------------------------------------------------------------
    // SurfaceHolder.Callback 实现
    // -----------------------------------------------------------------

    /**
     * Surface 创建时调用。
     *
     * VLC 绑定流程：
     * 1. vlcVout.setVideoView(this) — 设置渲染目标 View
     * 2. vlcVout.attachViews() — 绑定 Surface 并启动渲染
     *
     * 注意：若 vlcVout 已 attached（重复调用场景），跳过避免异常。
     */
    override fun surfaceCreated(holder: SurfaceHolder) {
        Log.i(TAG, "surfaceCreated: attaching VLC vlcVout")
        attachToVlc()
    }

    /**
     * Surface 尺寸变化时调用。
     * 通知 VLC 新的窗口尺寸，VLC 内部据此调整渲染区域（保持视频比例）。
     */
    override fun surfaceChanged(holder: SurfaceHolder, format: Int, width: Int, height: Int) {
        Log.d(TAG, "surfaceChanged: ${width}x$height")
        val c = controller ?: return
        try {
            c.mediaPlayer.vlcVout.setWindowSize(width, height)
        } catch (e: Exception) {
            Log.e(TAG, "setWindowSize failed", e)
        }
    }

    /**
     * Surface 销毁时调用（Activity onPause/onDestroy、View 从层级移除）。
     * 解绑 VLC 的 Surface 引用，避免 VLC 向已销毁的 Surface 渲染导致崩溃。
     */
    override fun surfaceDestroyed(holder: SurfaceHolder) {
        Log.i(TAG, "surfaceDestroyed: detaching VLC vlcVout")
        detachFromVlc()
    }

    // -----------------------------------------------------------------
    // 内部方法
    // -----------------------------------------------------------------

    /**
     * 将 VLC vlcVout 绑定到当前 Surface。
     * 检查 areViewsAttached() 避免重复绑定。
     */
    private fun attachToVlc() {
        val c = controller ?: return
        try {
            val vout = c.mediaPlayer.vlcVout
            if (!vout.areViewsAttached()) {
                vout.setVideoView(this)
                vout.attachViews()
                Log.i(TAG, "vlcVout attached (SurfaceView)")
            }
        } catch (e: Exception) {
            Log.e(TAG, "attachToVlc failed", e)
        }
    }

    /**
     * 将 VLC vlcVout 从当前 Surface 解绑。
     */
    private fun detachFromVlc() {
        val c = controller ?: return
        try {
            val vout = c.mediaPlayer.vlcVout
            if (vout.areViewsAttached()) {
                vout.detachViews()
                Log.i(TAG, "vlcVout detached")
            }
        } catch (e: Exception) {
            Log.e(TAG, "detachFromVlc failed", e)
        }
    }
}
