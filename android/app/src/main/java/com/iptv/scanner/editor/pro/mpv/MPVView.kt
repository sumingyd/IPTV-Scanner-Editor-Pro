package com.iptv.scanner.editor.pro.mpv

import android.content.Context
import android.graphics.PixelFormat
import android.util.AttributeSet
import android.util.Log
import android.view.SurfaceHolder
import android.view.SurfaceView
import android.view.View
import `is`.xyz.mpv.MPVLib
import com.iptv.scanner.editor.pro.data.UserPrefs

/**
 * 基于 SurfaceView 的 MPV 视频渲染视图。
 *
 * 生命周期策略（keep-alive）：
 * - MPVLib.create() 只在进程首次使用 MPV 时调用一次
 * - MPVLib.destroy() **永远不调用**（进程退出时 OS 自动回收）
 * - 切换播放器时：destroy() 只做 stop + playlist-clear + detachSurface
 * - 切回 MPV 时：initialize() 复用实例，surfaceCreated() 重新 attachSurface + 设置 vo
 *
 * 根因：MPVLib.destroy() 在部分设备（如华为 Kirin arm64）上会 SIGSEGV，
 * 即使已先调用 stop() + detachSurface()。mpv 内部线程的清理时机不可控，
 * destroy() 可能在线程仍持有锁/资源时释放底层结构，导致 use-after-free。
 * keep-alive 策略从根本上避免 destroy() 调用，以内存换稳定性。
 *
 * 状态重置（防止多次复用后状态累积残留）：
 * - destroy() 中：stop + playlist-clear + vo=null + force-window=no + detachSurface
 * - surfaceCreated() 中：attachSurface + force-window=yes + vo=voInUse
 * - playlist-clear 清除 mpv 内部播放列表，防止旧 path 残留导致双重 loadfile
 * - vo=null → vo=voInUse 的切换强制 vo 模块重新初始化，防止渲染状态累积
 */
class MPVView @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null
) : SurfaceView(context, attrs), SurfaceHolder.Callback, MPVViewLike {

    // 保存初始化参数，用于 mpv 核心 shutdown 后重新创建实例
    private var savedConfigDir: String? = null
    private var savedCacheDir: String? = null
    private var savedHwdec: String = DEFAULT_HWDEC

    /**
     * mpv 核心重建回调。当 ensureInstanceAlive() 重新创建 mpv 实例后调用，
     * 让外部（MpvController）能重新注册 observeProperty 和同步状态。
     */
    override var onInstanceRecreated: (() -> Unit)? = null

    override fun asView(): View = this

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
        myGeneration = ++activeGeneration
        Log.i(TAG, "initialize: generation=$myGeneration, vo=$vo, hwdec=$hwdec")

        if (nativeInstanceCreated) {
            // 复用现有 native mpv 实例（不 destroy + create）
            Log.i(TAG, "initialize: reusing existing native mpv instance (generation=$myGeneration)")
            try {
                // 运行时更新 hwdec（vo 由 surfaceCreated 设置，此时 surface 还没创建）
                MPVLib.setPropertyString("hwdec", hwdec)
                // 更新日志等级（运行时可切换）
                updateLogLevel()
            } catch (e: Throwable) {
                Log.w(TAG, "initialize: reuse setPropertyString failed: ${e.message}")
            }
            // 清除 filePath，防止 surfaceCreated 走 filePath 分支加载旧路径
            filePath = null
            // 标记实例为活跃（surfaceDestroyed/destroy 会设为 false）
            nativeInstanceAlive = true
            holder.setFormat(PixelFormat.RGBA_8888)
            holder.addCallback(this)
            return
        }

        // 首次创建或 shutdown 后重建：MPVLib.create + 完整初始化
        // 关键：如果 native 句柄已存在（keep-alive 策略下 destroy 永不调用），
        // 跳过 create() 直接 init()，避免 "mpv is already initialized" 错误导致 native 崩溃。
        // 场景：mpv 核心 shutdown 后 markInstanceDead() 重置 nativeInstanceCreated=false，
        // 但 native 句柄仍然存在，ensureInstanceAlive() 走重建路径时需要跳过 create()。
        if (nativeHandleCreated) {
            Log.i(TAG, "initialize: native handle already exists, skipping create() (init only)")
        } else {
            Log.i(TAG, "initialize: creating new native mpv instance")
            MPVLib.create(context)
            nativeHandleCreated = true
        }

        MPVLib.setOptionString("config", "yes")
        MPVLib.setOptionString("config-dir", configDir)
        for (opt in arrayOf("gpu-shader-cache-dir", "icc-cache-dir"))
            MPVLib.setOptionString(opt, cacheDir)

        MPVLib.setOptionString("vo", vo)
        MPVLib.setOptionString("hwdec", hwdec)
        // keep-open=always：stop 期间也保留最后一帧，避免换台黑屏闪烁。
        // 与 PC 端不同，Android 端在 loadfile 前会发送 stop（对齐 PC 端 play_file 的逻辑），
        // 用 always 确保 stop → loadfile 之间画面不消失。
        // yes 只在 EOF 时保留，stop 会清空画面；always 在 stop 时也保留。
        MPVLib.setOptionString("keep-open", "always")
        MPVLib.setOptionString("keepaspect", "yes")
        MPVLib.setOptionString("keepaspect-window", "no")
        // FBO 格式：根据 HDR 模式选择。
        // rgba16hf（16-bit 半浮点）允许 HDR 内容以高色深渲染，但很多 GPU（尤其
        // 电视盒子如 Homatics、部分 Mali/Adreno）不支持 16-bit 浮点帧缓冲，
        // EGL 初始化成功但 FBO 创建失败 → 黑屏（无画面）。
        // 默认用 rgba8（8-bit，全设备兼容），仅在 HDR 模式非 disable 时使用 rgba16hf。
        val hdrMode = UserPrefs.getInstance().getHdrMode()
        val fboFormat = if (hdrMode == "disable") "rgba8" else "rgba16hf"
        MPVLib.setOptionString("fbo-format", fboFormat)
        // target-colorspace-hint：仅 HDR 模式启用。
        // 部分设备显示控制器无法处理 colorspace 切换信号，会导致黑屏。
        if (hdrMode != "disable") {
            MPVLib.setOptionString("target-colorspace-hint", "yes")
        }

        MPVLib.setOptionString("framedrop", "all")
        MPVLib.setOptionString("video-sync", "audio")
        MPVLib.setOptionString("cache-pause-initial", "no")

        // 缓存大小：Android TV 内存有限（通常 1-2GB），过大的 demuxer 缓存在播放坏流时
        // 会导致 native 内存耗尽 → malloc 返回 null → SIGABRT 崩溃。
        // 32MiB 前向 + 8MiB 后向足够流畅播放，同时将 OOM 风险降到最低。
        MPVLib.setOptionString("demuxer-max-bytes", "32MiB")
        MPVLib.setOptionString("demuxer-max-back-bytes", "8MiB")
        MPVLib.setOptionString("demuxer-readahead-secs", "10")
        MPVLib.setOptionString("demuxer-seekable-cache", "yes")
        MPVLib.setOptionString("force-seekable", "yes")
        // 不等待缓存填满就开始播放，实现秒开（与 PC 端 cache-pause-initial=no 配合）
        MPVLib.setOptionString("demuxer-cache-wait", "no")

        // 网络超时：缩短到 8 秒（原来 30 秒太长）。
        // 坏流场景：mpv demuxer 线程会卡在网络读取上，30s 超时期间所有
        // 后续 loadfile 命令都无法执行，导致切到坏频道后所有频道都无法播放。
        // 8s 足够覆盖合法流的连接时间，同时配合 startTimeoutSwitchSource
        // 中的 stop 命令（5s 超时换源时先 stop 强制中断 demuxer）双重保障。
        MPVLib.setOptionString("network-timeout", "8")
        MPVLib.setOptionString("source-timeout", "8")
        MPVLib.setOptionString("stream-open-timeout", "8")
        // demuxer 读取超时：lavf 读取数据超时后触发 end-file 事件，
        // 防止坏流时 demuxer 无限重试消耗内存。
        MPVLib.setOptionString("demuxer-read-timeout", "5")

        MPVLib.setOptionString("stream-lavf-o", "verify=1")
        MPVLib.setOptionString("tls-verify", "yes")

        val cpuCount = Runtime.getRuntime().availableProcessors()
        val threads = maxOf(2, cpuCount / 2)
        MPVLib.setOptionString("vd-lavc-threads", threads.toString())

        // force-window 和 idle 必须在 init() 之前设置！
        // libmpv 的 mpv_set_option_string() 只在 mpv_initialize() 之前有效，
        // init() 之后调用会静默失败（返回错误码但代码未检查），导致选项从未生效。
        // - force-window=no：无文件时不创建视频窗口（避免空窗口占用 GPU 资源）
        // - idle=yes：mpv 核心永不自动退出，即使文件加载失败也保持存活。
        //   原来用 idle=once，但文件加载失败后核心会自动 shutdown（触发
        //   MPV_EVENT_SHUTDOWN），而 keep-alive 策略下无法重新 create() 或
        //   init()（native 句柄已存在且无法被 destroy），导致应用崩溃。
        //   idle=yes 确保核心在任何情况下都不会自动关闭，从根本上避免
        //   需要重建核心的场景。
        MPVLib.setOptionString("force-window", "no")
        MPVLib.setOptionString("idle", "yes")

        MPVLib.init()

        updateLogLevel()

        nativeInstanceAlive = true
        nativeInstanceCreated = true

        holder.setFormat(PixelFormat.RGBA_8888)
        holder.addCallback(this)
        observeProperties()
    }

    /**
     * 更新 mpv 日志等级（运行时切换）。
     * 通过 setPropertyString("msg-level", ...) 实现，无需重启。
     */
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
        holder.removeCallback(this)
        if (myGeneration != activeGeneration) {
            Log.i(TAG, "destroy: skipped (myGen=$myGeneration, activeGen=$activeGeneration)")
            return
        }
        // keep-alive：不调用 MPVLib.destroy()，只做状态重置
        if (nativeInstanceAlive) {
            try {
                MPVLib.command(arrayOf("stop"))
                // playlist-clear 清除 mpv 内部播放列表，防止下次复用时旧 path 残留
                MPVLib.command(arrayOf("playlist-clear"))
                MPVLib.setPropertyString("force-window", "no")
                // 设置 vo=null 释放 vo 模块资源（GPU/EGL 上下文），
                // surfaceCreated 时会重新设置 vo=voInUse 恢复渲染
                MPVLib.setPropertyString("vo", "null")
                MPVLib.detachSurface()
            } catch (e: Throwable) {
                Log.w(TAG, "destroy: reset failed: ${e.message}")
            }
            nativeInstanceAlive = false
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

    private var filePath: String? = null
    private var voInUse: String = DEFAULT_VO

    @Volatile
    private var myGeneration: Int = 0

    @Volatile
    override var pendingResumePos: Double = -1.0

    override fun setVoInUse(vo: String) {
        voInUse = vo
    }

    override val isSurfaceValid: Boolean
        get() = holder.surface != null && holder.surface.isValid

    /**
     * 运行时强制重新初始化 VO 模块（detach → vo=null → reattach → vo=newVo）。
     *
     * 根因：仅 setPropertyString("vo", newVo) 在部分设备上不会真正释放旧 VO 模块
     * 并初始化新 VO。例如从 gpu（EGL）切换到 mediacodec_embed（Surface 直渲），
     * mpv 可能仍使用旧 gpu VO 导致黑屏。
     *
     * 本方法通过完整的 detach/reattach 循环强制 VO 模块重建：
     * 1. force-window=no + vo=null + detachSurface → 释放旧 VO 资源
     * 2. attachSurface + force-window=yes + vo=newVo → 初始化新 VO
     *
     * 调用后需重新 loadfile 触发新 VO 渲染。
     */
    override fun reattachSurfaceWithVo(vo: String) {
        voInUse = vo
        Log.i(TAG, "reattachSurfaceWithVo: switching to vo=$vo")
        try {
            // Step 1: 释放当前 VO 模块
            MPVLib.setPropertyString("force-window", "no")
            MPVLib.setPropertyString("vo", "null")
            MPVLib.detachSurface()
            Log.i(TAG, "reattachSurfaceWithVo: detached old VO")

            // Step 2: 重新 attach surface 并设置新 VO
            val s = holder.surface
            if (s != null && s.isValid) {
                MPVLib.attachSurface(s)
                // setPropertyString（非 setOptionString）：init() 之后只能用属性方式设置
                MPVLib.setPropertyString("force-window", "yes")
                MPVLib.setPropertyString("vo", vo)
                Log.i(TAG, "reattachSurfaceWithVo: attached surface with vo=$vo")
            } else {
                // Surface 不可用：只设置 vo，等 surfaceCreated 回调时 attach
                MPVLib.setPropertyString("vo", vo)
                Log.w(TAG, "reattachSurfaceWithVo: surface not valid, vo set without reattach")
            }
        } catch (e: Throwable) {
            Log.e(TAG, "reattachSurfaceWithVo failed", e)
        }
    }

    /**
     * 诊断信息：返回当前 VO、hwdec、surface 状态、视频尺寸等。
     * 用于日志输出和用户报告问题时的诊断。
     */
    override fun getDiagnosticInfo(): String {
        val vo = try { MPVLib.getPropertyString("vo") ?: "unknown" } catch (_: Throwable) { "error" }
        val hwdec = try { MPVLib.getPropertyString("hwdec") ?: "unknown" } catch (_: Throwable) { "error" }
        val hwdecCurrent = try { MPVLib.getPropertyString("hwdec-current") ?: "none" } catch (_: Throwable) { "error" }
        val videoFormat = try { MPVLib.getPropertyString("video-format") ?: "none" } catch (_: Throwable) { "error" }
        val width = try { MPVLib.getPropertyInt("width") ?: 0 } catch (_: Throwable) { -1 }
        val height = try { MPVLib.getPropertyInt("height") ?: 0 } catch (_: Throwable) { -1 }
        val surfaceValid = holder.surface?.isValid ?: false
        return "vo=$vo, hwdec=$hwdec, hwdec-current=$hwdecCurrent, " +
            "video-format=$videoFormat, ${width}x${height}, " +
            "surfaceValid=$surfaceValid, voInUse=$voInUse"
    }


    override fun playFile(path: String) {
        // 确保 mpv 核心存活：如果核心已 shutdown，先重新创建
        if (!ensureInstanceAlive()) {
            Log.e(TAG, "playFile: mpv instance not alive, cannot play")
            return
        }
        val s = holder.surface
        if (s != null && s.isValid) {
            MPVLib.command(arrayOf("loadfile", path))
            MPVLib.setPropertyBoolean("pause", false)
        } else {
            filePath = path
        }
    }

    /**
     * 标记 native mpv 实例已死亡（由 MPV_EVENT_SHUTDOWN 触发）。
     *
     * mpv 核心在某些坏流场景下会自动 shutdown（如加载无法解析的 m3u8），
     * shutdown 后所有 MPVLib 命令都发到已死的实例上，静默失败。
     * 此方法重置 nativeInstanceCreated 标志，使下次 initialize/ensureInstanceAlive
     * 能重新创建 mpv 实例。
     */
    override fun markInstanceDead() {
        Log.w(TAG, "markInstanceDead: mpv core shutdown detected, marking instance as dead")
        nativeInstanceCreated = false
        nativeInstanceAlive = false
    }

    /**
     * 确保 mpv 核心存活。如果核心已 shutdown，使用保存的参数重新创建。
     *
     * @return true 如果核心存活（原本就活着或成功重建），false 如果无法重建
     */
    private fun ensureInstanceAlive(): Boolean {
        // 检查强制重建标志：forceRecreate() 已通过 stop+playlist-clear 重置状态
        if (forceRecreatePending) {
            forceRecreatePending = false
            Log.i(TAG, "ensureInstanceAlive: forceRecreatePending=true, state already reset by forceRecreate()")
            // idle=yes 确保核心仍然存活，forceRecreate 只做了状态重置（stop + playlist-clear），
            // 不需要重建核心。如果核心确实已 shutdown（极端情况），下面的检查会处理。
        }
        // 核心存活检查：如果核心已创建且活跃，直接返回
        if (nativeInstanceCreated && nativeInstanceAlive) {
            return true
        } else if (nativeInstanceCreated && !nativeHandleCreated) {
            // nativeInstanceCreated=true 但 nativeInstanceAlive=false 且无 native 句柄：
            // 实例存在但未活跃（destroy() 后状态），surfaceCreated 会恢复
            return true
        } else if (nativeInstanceCreated) {
            // nativeInstanceCreated=true + nativeHandleCreated=true 但 nativeInstanceAlive=false：
            // mpv 核心已 shutdown（markInstanceDead），native 句柄仍存在（keep-alive）。
            // idle=yes 下核心不应 shutdown，但若发生，返回 false 防止在已死句柄上操作。
            Log.w(TAG, "ensureInstanceAlive: instance created but not alive (core shutdown?), returning false")
            return false
        }
        // 核心 shutdown 后需要重建（idle=yes 下不应发生，此处为安全兜底）
        // 安全检查：如果 native 句柄已存在（keep-alive），不要尝试在已终止的句柄上
        // 调用 setOptionString/init —— libmpv 的 mpv_initialize() 只能调用一次，
        // 在已终止的句柄上调用会导致 native 崩溃（SIGABRT）。
        // 此时返回 false，让 playFile 跳过本次播放，避免崩溃。
        if (nativeHandleCreated) {
            Log.e(TAG, "ensureInstanceAlive: core has shutdown but native handle still exists (keep-alive). " +
                "Cannot safely re-initialize. Returning false to avoid native crash.")
            return false
        }
        val configDir = savedConfigDir ?: return false
        val cacheDir = savedCacheDir ?: return false
        Log.i(TAG, "ensureInstanceAlive: re-creating mpv instance after shutdown")
        try {
            // nativeInstanceCreated 为 false（首次创建或 native 句柄不存在），
            // 走完整初始化路径：create() + setOptionString + init() + observeProperties()。
            initialize(configDir, cacheDir, vo = voInUse, hwdec = savedHwdec)
            // 重新 attach surface（initialize 中已 addCallback，但 surface 可能已存在）
            val s = holder.surface
            if (s != null && s.isValid) {
                MPVLib.attachSurface(s)
                MPVLib.setPropertyString("force-window", "yes")
                MPVLib.setPropertyString("vo", voInUse)
                Log.i(TAG, "ensureInstanceAlive: surface re-attached")
            }
            // 通知外部（MpvController）核心已重建，重新注册 observeProperty
            onInstanceRecreated?.invoke()
            return true
        } catch (e: Throwable) {
            Log.e(TAG, "ensureInstanceAlive: re-create failed", e)
            // 恢复状态：重建失败时标记为死亡，下次 playFile 会再次尝试
            nativeInstanceCreated = false
            nativeInstanceAlive = false
            return false
        }
    }

    override fun stop() {
        if (!nativeInstanceCreated || !nativeInstanceAlive) return
        try {
            MPVLib.command(arrayOf("stop"))
        } catch (e: Throwable) {
            Log.w(TAG, "stop failed: ${e.message}")
        }
    }

    // ---- SurfaceHolder.Callback ----

    override fun surfaceCreated(holder: SurfaceHolder) {
        Log.i(TAG, "surfaceCreated: attaching surface (vo=$voInUse)")
        try {
            // 先 vo=null 销毁旧 VO 模块（释放旧 EGLSurface），
            // 再 attachSurface + vo=voInUse 创建新 VO（使用新 Surface 创建 EGLSurface）。
            //
            // 根因：Surface 重建后（屏幕旋转/返回后台），vo=gpu 的 EGLSurface 被销毁。
            // 仅 attachSurface + vo=voInUse（vo 未变化时是 no-op）不会触发 EGLSurface 重建 → 黑屏。
            // vo=null → vo=voInUse 的完整切换强制 VO 模块销毁并重建，新 VO 会创建新 EGLSurface。
            //
            // vo=null 不会影响文件的加载状态（path 仍非空，解码器仍运行），
            // 新 VO 创建后会自动从解码器接收帧并渲染 → 无需重新 loadfile。
            MPVLib.setPropertyString("vo", "null")
            MPVLib.attachSurface(holder.surface)
            // force-window 在 init() 之后只能用 setPropertyString（运行时属性），
            // setOptionString 在 init() 后静默失败，曾导致 force-window 从未设为 yes。
            MPVLib.setPropertyString("force-window", "yes")
            MPVLib.setPropertyString("vo", voInUse)
            Log.i(TAG, "surfaceCreated: attachSurface OK, vo=$voInUse (forced VO reinit)")
        } catch (e: Throwable) {
            Log.e(TAG, "surfaceCreated: attachSurface FAILED", e)
        }

        if (filePath != null) {
            Log.i(TAG, "surfaceCreated: 播放缓存的 filePath=$filePath")
            MPVLib.command(arrayOf("loadfile", filePath as String))
            MPVLib.setPropertyBoolean("pause", false)
            filePath = null
        } else {
            // 文件已在播放时不要重新 loadfile！
            //
            // vo=null → vo=voInUse 的 VO 重建会让 mpv 自动在新 Surface 上恢复渲染，
            // 无需重新 loadfile。重新 loadfile 会导致 END_FILE → onFileError 误触发。
            //
            // （PiP 场景同理：detachSurface/attachSurface 后 VO 重建即恢复渲染）
            val currentPath = try { MPVLib.getPropertyString("path") } catch (_: Exception) { "" }
            if (!currentPath.isNullOrEmpty()) {
                Log.i(TAG, "surfaceCreated: file already playing ($currentPath), VO reinit should restore render")
                MPVLib.setPropertyBoolean("pause", false)
            } else {
                Log.i(TAG, "surfaceCreated: no pending filePath, waiting for external playFile")
            }
        }
    }

    override fun surfaceChanged(holder: SurfaceHolder, format: Int, width: Int, height: Int) {
        MPVLib.setPropertyString("android-surface-size", "${width}x$height")
    }

    override fun surfaceDestroyed(holder: SurfaceHolder) {
        if (!nativeInstanceAlive) {
            Log.i(TAG, "surfaceDestroyed: native instance not active, skipping")
            return
        }
        Log.i(TAG, "surfaceDestroyed: detaching surface")
        try {
            // 不设置 force-window=no 和 vo=null：保持 VO 模块活跃，只解除 Surface 引用。
            // surfaceCreated 时会先 vo=null 再 vo=voInUse 强制 VO 完全重建。
            //
            // 如果这里设 vo=null，surfaceCreated 时 vo 已经是 null，再设 vo=null 是 no-op，
            // 无法触发 VO 重建（mpv 认为 vo 没有变化）→ EGLSurface 不重建 → 黑屏。
            // 保持 vo=voInUse，让 surfaceCreated 的 vo=null → vo=voInUse 是有效切换。
            MPVLib.detachSurface()
        } catch (e: Throwable) {
            Log.w(TAG, "surfaceDestroyed: detachSurface failed: ${e.message}")
        }
    }

    companion object {
        private const val TAG = "mpv"

        const val DEFAULT_VO = "gpu"
        const val DEFAULT_HWDEC = "auto-copy"

        /**
         * native mpv 实例是否处于活跃状态（有 MPVView 关联，可以接收命令）。
         * destroy() 设为 false，initialize() 设为 true。
         * surfaceDestroyed() 检查此标志，为 false 时跳过 native 调用。
         */
        @Volatile
        internal var nativeInstanceAlive = false

        /**
         * native mpv 实例是否已创建（MPVLib.create 至少调用过一次）。
         * 一旦为 true 永远为 true（keep-alive 策略不 destroy）。
         * initialize() 用此标志判断是首次创建还是复用。
         *
         * 注意：markInstanceDead() 会将此标志重置为 false，表示 mpv 核心已 shutdown
         * 需要 ensureInstanceAlive() 重建。但底层 native 句柄仍然存在（keep-alive 不
         * 调用 MPVLib.destroy()），重建时应跳过 create() 直接 init()。
         * 参见 [nativeHandleCreated]。
         */
        @Volatile
        internal var nativeInstanceCreated = false

        /**
         * native mpv 句柄是否已创建（MPVLib.create() 调用成功后置 true，永不重置）。
         *
         * 与 [nativeInstanceCreated] 的区别：
         * - nativeInstanceCreated 会被 markInstanceDead() 重置（表示核心需重建）
         * - nativeHandleCreated 永不重置（表示 native 句柄存在，重建时跳过 create）
         *
         * 根因修复：keep-alive 策略下 MPVLib.destroy() 永不调用，native 句柄一直存在。
         * 当 mpv 核心 shutdown 后 markInstanceDead() 重置 nativeInstanceCreated=false，
         * ensureInstanceAlive() 误以为需要重新 create()，但 MPVLib.create() 检测到
         * 句柄已存在会报 "mpv is already initialized" 错误，后续 init() 在异常状态下
         * 执行导致 native 崩溃（SIGABRT/SIGSEGV）。
         * 修复：用 nativeHandleCreated 标志跳过 create()，直接 init() 重新初始化核心。
         */
        @Volatile
        internal var nativeHandleCreated = false

        @Volatile
        internal var activeGeneration: Int = 0

        /**
         * 强制重建标志：由 forceRecreate() 设置。
         * ensureInstanceAlive() 检测到此标志时，即使 nativeInstanceCreated=true
         * 也会强制标记为死亡并重建核心，用于清除卡死的 demuxer。
         */
        @Volatile
        internal var forceRecreatePending = false
    }

    /**
     * 强制重置 mpv 核心状态（不终止核心）。
     *
     * 用于连续超时换源场景：当 stop 命令无法清除卡死的 demuxer 时，
     * 通过 stop + playlist-clear + vo 重置来强制清除内部状态。
     *
     * 关键变更：不再发送 quit 命令！
     * 原实现发送 quit 终止 mpv 核心，然后尝试通过 ensureInstanceAlive() 重建。
     * 但 keep-alive 策略下 native 句柄无法被 destroy()（会 SIGSEGV），
     * 而 MPVLib.create() 检测到句柄已存在会拒绝创建（"mpv is already initialized"），
     * 导致 init() 在已终止的句柄上执行 → native 崩溃。
     *
     * 配合 idle=yes，mpv 核心永不自动关闭，forceRecreate 只需重置状态而非重建核心。
     * demuxer-read-timeout=5 确保卡死的 demuxer 最终会超时释放。
     */
    override fun forceRecreate() {
        Log.w(TAG, "forceRecreate: resetting mpv state (stop + playlist-clear, no quit)")
        forceRecreatePending = true
        try {
            MPVLib.command(arrayOf("stop"))
            MPVLib.command(arrayOf("playlist-clear"))
        } catch (e: Throwable) {
            Log.w(TAG, "forceRecreate: reset commands failed: ${e.message}")
        }
    }
}
