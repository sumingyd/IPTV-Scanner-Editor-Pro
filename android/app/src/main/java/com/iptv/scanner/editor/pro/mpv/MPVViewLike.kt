package com.iptv.scanner.editor.pro.mpv

import android.view.View

interface MPVViewLike {
var onInstanceRecreated: (() -> Unit)?
/** Surface 重建回调（surfaceCreated 后触发），MpvController 注册以取消 pendingEndFileError */
var onSurfaceRebuilt: (() -> Unit)?
var pendingResumePos: Double
val isSurfaceValid: Boolean
    fun initialize(configDir: String, cacheDir: String, vo: String, hwdec: String)
    fun destroy()
    fun playFile(path: String)
    fun stop()
    fun forceRecreate()
    fun markInstanceDead()
    fun reattachSurfaceWithVo(vo: String)
    fun getDiagnosticInfo(): String
    fun setVoInUse(vo: String)
    fun asView(): View
}
