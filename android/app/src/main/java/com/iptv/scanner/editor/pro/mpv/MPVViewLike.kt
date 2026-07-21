package com.iptv.scanner.editor.pro.mpv

import android.view.View

/**
 * MPVView 和 MPVTextureView 的公共接口。
 *
 * MpvController 通过此接口操作播放器视图，无需关心底层是 SurfaceView 还是 TextureView。
 * - SurfaceView（MPVView）：性能更好，但会在窗口级别"打孔"，可能覆盖其他 UI 元素。
 * - TextureView（MPVTextureView）：普通 View，无 Z-order 问题，适合需要与其他 UI 元素共存的布局（如竖屏分屏）。
 */
interface MPVViewLike {
    /** mpv 核心重建回调 */
    var onInstanceRecreated: (() -> Unit)?

    /** 续播位置（Surface 重建后恢复） */
    var pendingResumePos: Double

    /** Surface 是否有效 */
    val isSurfaceValid: Boolean

    /** 初始化 mpv 实例（复用或首次创建） */
    fun initialize(configDir: String, cacheDir: String, vo: String, hwdec: String)

    /** 销毁视图（keep-alive：不销毁 mpv 核心，只重置状态 + detach surface） */
    fun destroy()

    /** 播放文件 */
    fun playFile(path: String)

    /** 停止播放 */
    fun stop()

    /** 强制重置 mpv 状态 */
    fun forceRecreate()

    /** 标记 mpv 核心已死亡 */
    fun markInstanceDead()


    /** 重新 attach surface 并切换 VO */
    fun reattachSurfaceWithVo(vo: String)

    /** 获取诊断信息 */
    fun getDiagnosticInfo(): String

    /** 设置当前使用的 VO */
    fun setVoInUse(vo: String)

    /** 返回 View 实例（用于 postDelayed 等 View 方法） */
    fun asView(): View
}
