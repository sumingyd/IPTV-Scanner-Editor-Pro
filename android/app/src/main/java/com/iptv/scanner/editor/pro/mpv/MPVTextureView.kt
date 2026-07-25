package com.iptv.scanner.editor.pro.mpv

import android.content.Context

import android.graphics.SurfaceTexture
import android.util.AttributeSet
import android.util.Log
import android.view.Surface
import android.view.TextureView
import android.view.View
import `is`.xyz.mpv.MPVLib
import com.iptv.scanner.editor.pro.data.UserPrefs

/**
 * 基于 TextureView 的 MPV 视频渲染视图。
 *
 * 与 [MPVView]（SurfaceView 版本）功能完全一致，但使用 TextureView 替代 SurfaceView。
 *
 * 使用场景：竖屏分屏布局。SurfaceView 会在窗口级别创建独立 surface layer，
 * 可能"打孔"覆盖整个窗口（包括信息栏等非视频区域），导致 UI 不可见。
 * TextureView 是普通 View，受 Compose 布局系统完全约束，无 Z-order 问题。
 *
 * 共享状态：mpv 核心状态（nativeInstanceCreated 等）存储在 [MPVView] 的 companion object 中，
 * 两个类共享同一份状态，确保切换 SurfaceView ↔ TextureView 时 mpv 实例正确复用。
 *
 * 性能差异：TextureView 比 SurfaceView 多一次 GPU 纹理拷贝，
 * 在高端设备上差异不明显，低端设备可能增加 1-2 帧延迟。
 */
class MPVTextureView @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null
) : TextureView(context, attrs), TextureView.SurfaceTextureListener, MPVViewLike {

    private val TAG = "MPVTextureView"

    private var savedConfigDir: String? = null
    private var savedCacheDir: String? = null
    private var savedHwdec: String = MPVView.DEFAULT_HWDEC

    override var onInstanceRecreated: (() -> Unit)? = null

    override fun asView(): View = this

    /** 当前 Surface（从 SurfaceTexture 创建） */
    @Volatile
    private var surface: Surface? = null

    @Volatile
    override var pendingResumePos: Double = -1.0

    private var filePath: String? = null
    private var voInUse: String = MPVView.DEFAULT_VO

    @Volatile
    private var myGeneration: Int = 0

    override val isSurfaceValid: Boolean
        get() = surface != null && surface!!.isValid

    override fun initialize(
        configDir: String,
        cacheDir: String,
        vo: String,
        hwdec: String
    ) {
        voInUse = vo
        savedConfigDir = configDir
        savedCacheDir = cacheDir
        savedHwdec = hwdec
        myGeneration = ++MPVView.activeGeneration
        Log.i(TAG, "initialize: generation=$myGeneration, vo=$vo, hwdec=$hwdec")

        // TextureView 必须设为不透明！
        // isOpaque=false 会导致 surface 带 alpha 通道，mpv GPU VO 渲染的视频变成透明（不可见）。
        isOpaque = true

        if (MPVView.nativeInstanceCreated) {
            // 复用现有 native mpv 实例
            Log.i(TAG, "initialize: reusing existing native mpv instance (generation=$myGeneration)")
            try {
                MPVLib.setPropertyString("hwdec", hwdec)
                updateLogLevel()
            } catch (e: Throwable) {
                Log.w(TAG, "initialize: reuse setPropertyString failed: ${e.message}")
            }
            filePath = null
            MPVView.nativeInstanceAlive = true
            surfaceTextureListener = this
            // 关键：SurfaceTexture 可能已经可用（TextureView 在 initialize 之前已布局），
            // 此时 onSurfaceTextureAvailable 不会再触发，需要手动 attach。
            val st = surfaceTexture
            if (st != null) {
                Log.i(TAG, "initialize: SurfaceTexture already available, manually attaching")
                val s = Surface(st)
                surface = s
                try {
                    reattachSurfaceWithVo(voInUse)
                    MPVLib.setPropertyString("force-window", "yes")
                    Log.i(TAG, "initialize: manual attachSurface OK (TextureView), vo=$voInUse")
                } catch (e: Throwable) {
                    Log.e(TAG, "initialize: manual attachSurface FAILED", e)
                }
            }
            return
        }

        // 首次创建或 shutdown 后重建
        if (MPVView.nativeHandleCreated) {
            Log.i(TAG, "initialize: native handle already exists, skipping create() (init only)")
        } else {
            Log.i(TAG, "initialize: creating new native mpv instance")
            MPVLib.create(context)
            MPVView.nativeHandleCreated = true
        }

        MPVLib.setOptionString("config", "yes")
        MPVLib.setOptionString("config-dir", configDir)
        for (opt in arrayOf("gpu-shader-cache-dir", "icc-cache-dir"))
            MPVLib.setOptionString(opt, cacheDir)

        MPVLib.setOptionString("vo", vo)
        MPVLib.setOptionString("hwdec", hwdec)
        MPVLib.setOptionString("keep-open", "yes")
        MPVLib.setOptionString("keepaspect", "yes")
        MPVLib.setOptionString("keepaspect-window", "no")

        val hdrMode = UserPrefs.getInstance().getHdrMode()
        val fboFormat = if (hdrMode == "disable") "rgba8" else "rgba16hf"
        MPVLib.setOptionString("fbo-format", fboFormat)
        if (hdrMode != "disable") {
            MPVLib.setOptionString("target-colorspace-hint", "yes")
        }

        MPVLib.setOptionString("framedrop", "all")
        MPVLib.setOptionString("video-sync", "audio")
        MPVLib.setOptionString("cache-pause-initial", "no")

        MPVLib.setOptionString("demuxer-max-bytes", "32MiB")
        MPVLib.setOptionString("demuxer-max-back-bytes", "8MiB")
        MPVLib.setOptionString("demuxer-readahead-secs", "10")
        MPVLib.setOptionString("demuxer-seekable-cache", "yes")
        MPVLib.setOptionString("force-seekable", "yes")
        MPVLib.setOptionString("demuxer-cache-wait", "no")

        MPVLib.setOptionString("network-timeout", "8")
        MPVLib.setOptionString("source-timeout", "8")
        MPVLib.setOptionString("stream-open-timeout", "8")
        MPVLib.setOptionString("demuxer-read-timeout", "5")

        MPVLib.setOptionString("stream-lavf-o", "verify=1")
        MPVLib.setOptionString("tls-verify", "yes")

        val cpuCount = Runtime.getRuntime().availableProcessors()
        val threads = maxOf(2, cpuCount / 2)
        MPVLib.setOptionString("vd-lavc-threads", threads.toString())

        MPVLib.setOptionString("force-window", "no")
        MPVLib.setOptionString("idle", "yes")

        MPVLib.init()

        updateLogLevel()

        MPVView.nativeInstanceAlive = true
        MPVView.nativeInstanceCreated = true

        surfaceTextureListener = this
        observeProperties()
    }

    private fun updateLogLevel() {
        try {
            val logLevel = UserPrefs.getInstance().getLogLevel()
            val mpvMsgLevel = when (logLevel) {
                "debug" -> "all=trace"
                "info" -> "all=info"
                "warn" -> "all=warn"
                "error" -> "all=error"
                else -> "all=info"
            }
            MPVLib.setPropertyString("msg-level", mpvMsgLevel)
        } catch (e: Throwable) {
            Log.w(TAG, "updateLogLevel failed: ${e.message}")
        }
    }

    override fun destroy() {
        surfaceTextureListener = null
        if (myGeneration != MPVView.activeGeneration) {
            Log.i(TAG, "destroy: skipped (myGen=$myGeneration, activeGen=${MPVView.activeGeneration})")
            return
        }
        if (MPVView.nativeInstanceAlive) {
            try {
                MPVLib.command(arrayOf("stop"))
                MPVLib.command(arrayOf("playlist-clear"))
                MPVLib.setPropertyString("force-window", "no")
                MPVLib.setPropertyString("vo", "null")
                MPVLib.detachSurface()
            } catch (e: Throwable) {
                Log.w(TAG, "destroy: reset failed: ${e.message}")
            }
            MPVView.nativeInstanceAlive = false
            Log.i(TAG, "destroy: instance kept alive, state reset (gen=$myGeneration)")
        }
    }

    private fun observeProperties() {
        MPVLib.observeProperty("time-pos", MPVLib.MpvFormat.MPV_FORMAT_DOUBLE)
        MPVLib.observeProperty("duration", MPVLib.MpvFormat.MPV_FORMAT_DOUBLE)
        MPVLib.observeProperty("pause", MPVLib.MpvFormat.MPV_FORMAT_FLAG)
        MPVLib.observeProperty("eof-reached", MPVLib.MpvFormat.MPV_FORMAT_FLAG)
        MPVLib.observeProperty("volume", MPVLib.MpvFormat.MPV_FORMAT_INT64)
        MPVLib.observeProperty("mute", MPVLib.MpvFormat.MPV_FORMAT_FLAG)
        MPVLib.observeProperty("media-title", MPVLib.MpvFormat.MPV_FORMAT_STRING)
        MPVLib.observeProperty("track-list", MPVLib.MpvFormat.MPV_FORMAT_NODE)
    }

    override fun setVoInUse(vo: String) {
        voInUse = vo
    }

    override fun reattachSurfaceWithVo(vo: String) {
        voInUse = vo
        Log.i(TAG, "reattachSurfaceWithVo: switching to vo=$vo")
        try {
            MPVLib.setPropertyString("force-window", "no")
            MPVLib.setPropertyString("vo", "null")
            MPVLib.detachSurface()

            val s = surface
            if (s != null && s.isValid) {
                MPVLib.attachSurface(s)
                MPVLib.setPropertyString("force-window", "yes")
                MPVLib.setPropertyString("vo", vo)
                Log.i(TAG, "reattachSurfaceWithVo: attached surface with vo=$vo")
            } else {
                MPVLib.setPropertyString("vo", vo)
                Log.w(TAG, "reattachSurfaceWithVo: surface not valid, vo set without reattach")
            }
        } catch (e: Throwable) {
            Log.e(TAG, "reattachSurfaceWithVo failed", e)
        }
    }

    override fun getDiagnosticInfo(): String {
        val vo = try { MPVLib.getPropertyString("vo") ?: "unknown" } catch (_: Throwable) { "error" }
        val hwdec = try { MPVLib.getPropertyString("hwdec") ?: "unknown" } catch (_: Throwable) { "error" }
        val hwdecCurrent = try { MPVLib.getPropertyString("hwdec-current") ?: "none" } catch (_: Throwable) { "error" }
        val videoFormat = try { MPVLib.getPropertyString("video-format") ?: "none" } catch (_: Throwable) { "error" }
        val width = try { MPVLib.getPropertyInt("width") ?: 0 } catch (_: Throwable) { -1 }
        val height = try { MPVLib.getPropertyInt("height") ?: 0 } catch (_: Throwable) { -1 }
        val surfaceValid = surface?.isValid ?: false
        return "vo=$vo, hwdec=$hwdec, hwdec-current=$hwdecCurrent, " +
            "video-format=$videoFormat, ${width}x${height}, " +
            "surfaceValid=$surfaceValid, voInUse=$voInUse"
    }


    override fun playFile(path: String) {
        if (!ensureInstanceAlive()) {
            Log.e(TAG, "playFile: mpv instance not alive, cannot play")
            return
        }
        val s = surface
        if (s != null && s.isValid) {
            MPVLib.command(arrayOf("loadfile", path))
            MPVLib.setPropertyBoolean("pause", false)
        } else {
            filePath = path
        }
    }

    override fun markInstanceDead() {
        Log.w(TAG, "markInstanceDead: mpv core shutdown detected, marking instance as dead")
        MPVView.nativeInstanceCreated = false
        MPVView.nativeInstanceAlive = false
    }


    private fun ensureInstanceAlive(): Boolean {
        if (MPVView.forceRecreatePending) {
            MPVView.forceRecreatePending = false
            Log.i(TAG, "ensureInstanceAlive: forceRecreatePending=true, state already reset")
        }
        if (MPVView.nativeInstanceCreated && MPVView.nativeInstanceAlive) {
            return true
        } else if (MPVView.nativeInstanceCreated) {
            return true
        }
        if (MPVView.nativeHandleCreated) {
            Log.e(TAG, "ensureInstanceAlive: core shutdown but native handle exists. Returning false.")
            return false
        }
        val configDir = savedConfigDir ?: return false
        val cacheDir = savedCacheDir ?: return false
        Log.i(TAG, "ensureInstanceAlive: re-creating mpv instance after shutdown")
        try {
            initialize(configDir, cacheDir, vo = voInUse, hwdec = savedHwdec)
            val s = surface
            if (s != null && s.isValid) {
                MPVLib.attachSurface(s)
                MPVLib.setPropertyString("force-window", "yes")
                MPVLib.setPropertyString("vo", voInUse)
                Log.i(TAG, "ensureInstanceAlive: surface re-attached")
            }
            onInstanceRecreated?.invoke()
            return true
        } catch (e: Throwable) {
            Log.e(TAG, "ensureInstanceAlive: re-create failed", e)
            MPVView.nativeInstanceCreated = false
            MPVView.nativeInstanceAlive = false
            return false
        }
    }

    override fun stop() {
        if (!MPVView.nativeInstanceCreated || !MPVView.nativeInstanceAlive) return
        try {
            MPVLib.command(arrayOf("stop"))
        } catch (e: Throwable) {
            Log.w(TAG, "stop failed: ${e.message}")
        }
    }

    // ---- TextureView.SurfaceTextureListener ----

    override fun onSurfaceTextureAvailable(surfaceTexture: SurfaceTexture, width: Int, height: Int) {
        Log.i(TAG, "onSurfaceTextureAvailable: attaching surface (vo=$voInUse, ${width}x${height})")
        try {
            surface?.release()
            val s = Surface(surfaceTexture)
            surface = s
            // 使用 reattachSurfaceWithVo 而非 attachSurface：它会先 vo=null 再 vo=voInUse，
            // 强制 GPU vo 模块释放并重新绑定到新 Surface，解决首次渲染黑屏问题。
            reattachSurfaceWithVo(voInUse)
            MPVLib.setPropertyString("force-window", "yes")
            Log.i(TAG, "attachSurface OK (TextureView), vo=$voInUse")
        } catch (e: Throwable) {
            Log.e(TAG, "attachSurface FAILED", e)
        }

        if (filePath != null) {
            Log.i(TAG, "onSurfaceTextureAvailable: playing cached filePath=$filePath")
            MPVLib.command(arrayOf("loadfile", filePath as String))
            MPVLib.setPropertyBoolean("pause", false)
            filePath = null
        } else {
            val currentPath = try { MPVLib.getPropertyString("path") } catch (_: Exception) { "" }
            if (!currentPath.isNullOrEmpty()) {
                Log.i(TAG, "onSurfaceTextureAvailable: re-loading current path=$currentPath")
                MPVLib.command(arrayOf("loadfile", currentPath))
                MPVLib.setPropertyBoolean("pause", false)
            } else {
                Log.i(TAG, "onSurfaceTextureAvailable: no pending filePath, waiting for external playFile")
            }
        }
    }

    override fun onSurfaceTextureSizeChanged(surfaceTexture: SurfaceTexture, width: Int, height: Int) {
        MPVLib.setPropertyString("android-surface-size", "${width}x$height")
    }

    override fun onSurfaceTextureDestroyed(surfaceTexture: SurfaceTexture): Boolean {
        if (!MPVView.nativeInstanceAlive) {
            Log.i(TAG, "onSurfaceTextureDestroyed: native instance not active, skipping")
            surface?.release()
            surface = null
            return true
        }
        Log.i(TAG, "onSurfaceTextureDestroyed: detaching surface")
        try {
            MPVLib.setPropertyString("force-window", "no")
            MPVLib.detachSurface()
        } catch (e: Throwable) {
            Log.w(TAG, "onSurfaceTextureDestroyed: detachSurface failed: ${e.message}")
        }
        surface?.release()
        surface = null
        return true
    }

    override fun onSurfaceTextureUpdated(surfaceTexture: SurfaceTexture) {
        // mpv 内部处理渲染，无需回调
    }

    override fun forceRecreate() {
        Log.w(TAG, "forceRecreate: resetting mpv state (stop + playlist-clear, no quit)")
        MPVView.forceRecreatePending = true
        try {
            MPVLib.command(arrayOf("stop"))
            MPVLib.command(arrayOf("playlist-clear"))
        } catch (e: Throwable) {
            Log.w(TAG, "forceRecreate: reset commands failed: ${e.message}")
        }
    }
}
