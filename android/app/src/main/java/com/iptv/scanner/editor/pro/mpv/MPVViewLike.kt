package com.iptv.scanner.editor.pro.mpv

import android.view.View

interface MPVViewLike {
    var onInstanceRecreated: (() -> Unit)?
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
