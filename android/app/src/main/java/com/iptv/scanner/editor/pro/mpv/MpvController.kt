package com.iptv.scanner.editor.pro.mpv

import android.util.Log
import `is`.xyz.mpv.MPVLib
import com.iptv.scanner.editor.pro.data.UserPrefs
import com.iptv.scanner.editor.pro.player.Player
import com.iptv.scanner.editor.pro.player.PlayerCapabilities
import com.iptv.scanner.editor.pro.player.PlayerType
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * Compose 友好的 mpv 控制器：单例，持有 MPVView 引用，
 * 把 MPVLib 的属性/命令包装为 StateFlow + 命令方法。
 *
 * 设计要点：
 * 1. 单例对应 MPVLib 单例，attach/detach 管理 MPVView 生命周期
 * 2. 所有 MPVLib.command/setProperty 调用 post 到 MPVView 线程（mpv 要求同线程访问）
 * 3. 实现 EventObserver，把 mpv 属性变化转发到 StateFlow，Compose 直接观察
 * 4. 高级功能（chapters / track-list / HDR 重建协调 / 画面调整 / 音频 EQ / 字幕样式 /
 *    截图 / A-B 循环 / frame-step）直接调 mpv，不走 Python
 *
 * 与 PC 端 services/mpv_player_service.py 的对应关系：
 * - 章节：get_chapter_list/set_chapter/chapter_next/chapter_prev
 * - 轨道：get_track_list/set_track/add_subtitle_file
 * - 画面：set_video_rotate/set_video_flip/set_video_crop + brightness/contrast/saturation/hue/gamma
 * - 音频：set_audio_delay/set_audio_eq（10 段 EQ via af=lavfi=[equalizer=...]）
 * - 字幕：set_sub_delay/set_sub_scale/set_sub_visibility + apply_sub_style
 * - 截图：screenshot_to_file（mode: video/subtitles/window/each-frame）
 * - A/B 循环：ab_loop_set_a/b/clear + loop-file/loop-playlist
 *
 * 注意：HDR 模式切换和 hwdec 切换需要重建 mpv（option 不能运行时改），
 *      MpvController 暴露 savePlaybackState/restorePlaybackState 给 ViewModel 协调重建。
 *      实际重建由 Activity 销毁旧 MPVView + 创建新 MPVView 完成。
 */
class MpvController : MPVLib.EventObserver, Player {

    override val playerType = PlayerType.MPV

    /** MPV 功能最完整，所有 capability 均为 true */
    override val capabilities = PlayerCapabilities(
        supportsBrightness = true, supportsContrast = true, supportsSaturation = true,
        supportsHue = true, supportsGamma = true, supportsVideoRotate = true,
        supportsVideoFlip = true, supportsVideoCrop = true, supportsAudioDelay = true,
        supportsAudioEq = true, supportsSubDelay = true, supportsSubScale = true,
        supportsSubPos = true, supportsAbLoop = true, supportsLoopFile = true,
        supportsFrameStep = true, supportsChapters = true, supportsScreenshot = true,
        supportsOsd = true, supportsAddSubtitleFile = true,
        supportsSpeedControl = true, supportsTrackList = true,
        supportsHardwareDecodeSwitch = true
    )

    @Volatile
    private var mpvView: MPVViewLike? = null

    /**
     * 黑屏 fallback 标志：vo=gpu 在部分 GPU（如 Mali-G76）上存在 EGL 兼容性问题导致黑屏。
     * 检测到黑屏后自动切换到 vo=mediacodec_embed（仅 fallback 一次，避免循环）。
     */
    @Volatile
    private var voFallbackTriggered = false

    // -----------------------------------------------------------------
    // StateFlow（Compose 可观察状态）— override Player 接口
    // -----------------------------------------------------------------
    private val _timePos = MutableStateFlow(0.0)
    override val timePos: StateFlow<Double> = _timePos.asStateFlow()

    private val _duration = MutableStateFlow(0.0)
    override val duration: StateFlow<Double> = _duration.asStateFlow()

    private val _paused = MutableStateFlow(true)
    override val paused: StateFlow<Boolean> = _paused.asStateFlow()

    private val _volume = MutableStateFlow(100)
    override val volume: StateFlow<Int> = _volume.asStateFlow()

    private val _muted = MutableStateFlow(false)
    override val muted: StateFlow<Boolean> = _muted.asStateFlow()

    private val _mediaTitle = MutableStateFlow("")
    override val mediaTitle: StateFlow<String> = _mediaTitle.asStateFlow()

    private val _trackListJson = MutableStateFlow("")
    override val trackListJson: StateFlow<String> = _trackListJson.asStateFlow()

    private val _eofReached = MutableStateFlow(false)
    override val eofReached: StateFlow<Boolean> = _eofReached.asStateFlow()

    private val _fileLoaded = MutableStateFlow(false)
    override val fileLoaded: StateFlow<Boolean> = _fileLoaded.asStateFlow()

    private val _currentChapter = MutableStateFlow(-1)
    override val currentChapter: StateFlow<Int> = _currentChapter.asStateFlow()

    private val _chapterCount = MutableStateFlow(0)
    override val chapterCount: StateFlow<Int> = _chapterCount.asStateFlow()

    private val _videoWidth = MutableStateFlow(0)
    override val videoWidth: StateFlow<Int> = _videoWidth.asStateFlow()

    private val _videoHeight = MutableStateFlow(0)
    override val videoHeight: StateFlow<Int> = _videoHeight.asStateFlow()

    /**
     * VO 自动 fallback 回调（由黑屏检测触发）。
     * AppViewModel 注册此回调以同步 UI 状态（_currentVo / _currentHwdec）。
     */
    @Volatile
    var onVoFallback: ((String, String) -> Unit)? = null

    /**
     * 文件加载出错回调（由 MPV_EVENT_END_FILE with error 触发）。
     * AppViewModel 注册此回调以在文件加载出错时立即换源，
     * 而不必等待超时定时器触发（默认 5-30s 太慢，坏流可能在几秒内耗尽内存）。
     */
    @Volatile
    var onFileError: (() -> Unit)? = null

    private val _speed = MutableStateFlow(1.0)
    override val speed: StateFlow<Double> = _speed.asStateFlow()

    // -----------------------------------------------------------------
    // 生命周期
    // -----------------------------------------------------------------
    /**
     * 绑定 MPVView 实例，注册 EventObserver，补充观察 MPVView 未观察的属性。
     * 必须在 MPVView.initialize() 之后调用。
     */
    fun attach(view: MPVViewLike) {
        this.mpvView = view
        MPVLib.addObserver(this)
        // MPVView.observeProperties() 已观察 time-pos/duration/pause/eof-reached/volume/mute/media-title/track-list
        // 这里补充观察 chapter/chapter-count/width/height/speed/path
        try {
            MPVLib.observeProperty("chapter", MPVLib.MpvFormat.MPV_FORMAT_INT64)
            MPVLib.observeProperty("chapter-count", MPVLib.MpvFormat.MPV_FORMAT_INT64)
            MPVLib.observeProperty("width", MPVLib.MpvFormat.MPV_FORMAT_INT64)
            MPVLib.observeProperty("height", MPVLib.MpvFormat.MPV_FORMAT_INT64)
            MPVLib.observeProperty("speed", MPVLib.MpvFormat.MPV_FORMAT_DOUBLE)
            MPVLib.observeProperty("path", MPVLib.MpvFormat.MPV_FORMAT_STRING)
            MPVLib.observeProperty("sub-visibility", MPVLib.MpvFormat.MPV_FORMAT_FLAG)
        } catch (e: Throwable) {
            Log.w(TAG, "observeProperty failed: ${e.message}")
        }

        // 同步查询 mpv 当前 pause 状态，防止 detach() 中 _paused=true 残留导致 UI 误显示"已暂停"。
        // detach() 会将 _paused 设为 true（安全默认值），但切回 MPV 复用实例时，
        // mpv 内部 pause 可能是 false（上次 playFile 已解除暂停），若不同步更新，
        // UI 会一直显示"已暂停"直到下一个 pause 属性变更事件到达。
        try {
            val currentPause = MPVLib.getPropertyBoolean("pause") ?: true
            _paused.value = currentPause
            Log.i(TAG, "attach: synced pause state from mpv: $currentPause")
        } catch (e: Throwable) {
            Log.w(TAG, "attach: sync pause state failed: ${e.message}")
        }

        // 播放器设置持久化：如果该设备已确认需要 vo fallback（黑屏检测曾触发过），
        // 直接设置标志跳过本次黑屏探测。此时 MPVView 已用持久化的 mediacodec_embed 初始化，
        // 无需再等待 2 秒黑屏。
        // 用户可通过 resetPlayerSettings() 重置，重新走黑屏检测流程。
        if (UserPrefs.getInstance().isVoFallbackConfirmed()) {
            voFallbackTriggered = true
            Log.i(TAG, "vo fallback already confirmed, skip black screen detection")
        }

        // 重置 fbo-format 降级标志（新会话/新 Surface 重新探测）
        fboFormatDowngraded = false

        // 应用反交错设置（与 PC 端 _ensure_mpv_initialized 行 420-426 对齐）。
        // deinterlace 是运行时属性，在 attach 阶段设置确保首次播放即生效。
        setDeinterlace(UserPrefs.getInstance().getDeinterlace())

        // 注册 mpv 核心重建回调：当核心 shutdown 后由 ensureInstanceAlive() 重建时，
        // 需要重新注册 MpvController 的额外 observeProperty（chapter/width/height 等）。
        // MPVView.observeProperties() 只注册基本属性，MpvController 的额外属性需要在此补充。
        view.onInstanceRecreated = {
            Log.i(TAG, "onInstanceRecreated: re-observing properties after mpv core re-creation")
            try {
                MPVLib.observeProperty("chapter", MPVLib.MpvFormat.MPV_FORMAT_INT64)
                MPVLib.observeProperty("chapter-count", MPVLib.MpvFormat.MPV_FORMAT_INT64)
                MPVLib.observeProperty("width", MPVLib.MpvFormat.MPV_FORMAT_INT64)
                MPVLib.observeProperty("height", MPVLib.MpvFormat.MPV_FORMAT_INT64)
                MPVLib.observeProperty("speed", MPVLib.MpvFormat.MPV_FORMAT_DOUBLE)
                MPVLib.observeProperty("path", MPVLib.MpvFormat.MPV_FORMAT_STRING)
                MPVLib.observeProperty("sub-visibility", MPVLib.MpvFormat.MPV_FORMAT_FLAG)
            } catch (e: Throwable) {
                Log.w(TAG, "onInstanceRecreated: observeProperty failed: ${e.message}")
            }
            // 重新应用反交错设置
            setDeinterlace(UserPrefs.getInstance().getDeinterlace())
        }

        Log.i(TAG, "MpvController attached to MPVView")
    }

    /** Player 接口实现：转发到 attach(MPVView) */
    override fun attachView(view: Any) {
        if (view is MPVViewLike) {
            attach(view)
        } else {
            Log.w(TAG, "attachView: view is not MPVViewLike (${view.javaClass.name}), ignored")
        }
    }

    /**
     * 解绑 MPVView，移除 EventObserver。
     * 在 Activity.onDestroy 或切换内核时调用。
     *
     * 线程安全：stop() 和 onInstanceRecreated 清理通过 postOnUiThread 在 mpv 线程执行，
     * 避免在调用线程直接调用 MPVLib.command 违反 mpv 线程安全要求。
     * mpvView 引用在 post 之前捕获（val v = mpvView），确保异步 lambda 能正确访问。
     * this.mpvView = null 在 post 之后立即执行，阻止后续命令进入旧 view。
     */
    override fun detach() {
        val v = mpvView
        if (v != null) {
            v.asView().post {
                try {
                    v.stop()
                } catch (e: Throwable) {
                    Log.w(TAG, "detach: stop failed: ${e.message}")
                }
                v.onInstanceRecreated = null
            }
        }
        this.mpvView = null
        _fileLoaded.value = false
        _eofReached.value = false
        _timePos.value = 0.0
        _duration.value = 0.0
        _paused.value = true
        Log.i(TAG, "MpvController detached")
    }


    /**
     * 运行时切换 vo/hwdec（用户在播放器设置面板切换时调用）。
     *
     * 实现方式：通过 detach/reattach 循环强制 VO 模块重建（reattachSurfaceWithVo）。
     * 这比仅 setPropertyString("vo", ...) 更可靠，尤其是跨类型切换
     * （gpu↔mediacodec_embed）时能确保旧 VO 模块完全释放、新 VO 模块正确初始化。
     *
     * @param vo "gpu" / "gpu-next" / "mediacodec_embed"
     * @param hwdec "auto-copy" / "mediacodec" / "no"
     * @return 非空字符串表示有文件在播放（已重新加载），null 表示无文件
     */
    fun setVoAndHwdec(vo: String, hwdec: String): String? {
        // 用 _fileLoaded.value 判断是否有文件在播放（同步可读的 StateFlow），
        // 避免 MPVLib.getPropertyString("path") 在 mpv 状态异常时抛异常返回 null，
        // 导致 UI 误提示"重启后生效"。
        val hasFile = _fileLoaded.value
        postOnUiThread {
            try {
                // 关键修复：使用 detach/reattach 循环强制 VO 模块重建。
                // 仅 setPropertyString("vo", vo) 在部分设备上不会真正释放旧 VO 模块
                // 并初始化新 VO（尤其是 gpu↔mediacodec_embed 跨类型切换），
                // 导致用户以为切换了 VO 但实际仍在用旧 VO（黑屏）。
                MPVLib.setPropertyString("hwdec", hwdec)
                _hwdecCache = hwdec
                mpvView?.reattachSurfaceWithVo(vo)
                _voCache = vo

                // 重新加载当前文件以触发新 vo 渲染
                val path = MPVLib.getPropertyString("path")
                if (path != null && path.isNotEmpty()) {
                    MPVLib.command(arrayOf("loadfile", path))
                    MPVLib.setPropertyBoolean("pause", false)
                }
                // 重置 voFallbackTriggered：
                // - 切换到 gpu / gpu-next：重新启用黑屏检测，清除持久化的 fallback 标记
                //   （用户主动切回 gpu/gpu-next，说明设备 GPU 正常，不应再被持久化锁定）
                // - 切换到 mediacodec_embed：标记已 fallback（不需要再检测）
                voFallbackTriggered = (vo == "mediacodec_embed")
                if (vo == "gpu" || vo == "gpu-next") {
                    UserPrefs.getInstance().setVoFallbackConfirmed(false)
                    fboFormatDowngraded = false  // 重置降级标志，允许重新探测
                }
                Log.i(TAG, "setVoAndHwdec: vo=$vo, hwdec=$hwdec, voFallbackTriggered=$voFallbackTriggered, hasFile=$hasFile")
                Log.i(TAG, "diagnostic: ${mpvView?.getDiagnosticInfo()}")
            } catch (e: Throwable) {
                Log.e(TAG, "setVoAndHwdec failed", e)
            }
        }
        return if (hasFile) "reloaded" else null
    }

    /**
     * 切换硬件/软件解码（实现 Player.setHardwareDecode）。
     *
     * - vo=gpu / gpu-next：硬解 hwdec=auto-copy 或 auto（保留用户选择），软解 hwdec=no
     * - vo=mediacodec_embed：固定硬解（mediacodec），不支持软解，返回 false
     *
     * 切换后自动重新加载当前文件以应用新 hwdec。
     */
    override fun setHardwareDecode(enabled: Boolean): Boolean {
        val currentVo = try {
            _voCache
        } catch (e: Throwable) { "gpu" }

        if (!enabled && currentVo == "mediacodec_embed") {
            Log.w(TAG, "setHardwareDecode: vo=mediacodec_embed 不支持软解")
            return false
        }

        val currentHwdec = _hwdecCache
        val hwdec = when {
            !enabled -> "no"
            currentVo == "mediacodec_embed" -> "mediacodec"
            // 保留用户之前的选择：如果已经是 auto（4K HDR 直接输出），启用硬解时保持
            currentHwdec == "auto" -> "auto"
            else -> "auto-copy"
        }
        setVoAndHwdec(currentVo, hwdec)
        Log.i(TAG, "setHardwareDecode: enabled=$enabled, vo=$currentVo, hwdec=$hwdec")
        return true
    }

    /** 查询当前是否使用硬件解码 */
    override fun isHardwareDecodeEnabled(): Boolean {
        return try {
            val hwdec = _hwdecCache
            hwdec != "no"
        } catch (e: Throwable) { true }
    }

    @Volatile
    private var _hwdecCache: String = "auto-copy"

    @Volatile
    private var _voCache: String = "gpu"

    /**
     * 设置反交错（deinterlace）。
     *
     * 与 PC 端 _ensure_mpv_initialized 行 420-426 对齐：
     * mpv 的 deinterlace 属性只支持 yes/no，UI 层的 "auto" 转换为 "yes"
     * （mpv 会自动检测隔行内容并应用 yadif 滤镜）。
     * 该属性为运行时可改属性，无需重新加载文件即可生效。
     *
     * @param value "no"（关闭）或 "auto"（自动检测）
     */
    fun setDeinterlace(value: String) {
        val mpvValue = if (value == "auto") "yes" else "no"
        postOnUiThread {
            try {
                MPVLib.setPropertyString("deinterlace", mpvValue)
                Log.i(TAG, "setDeinterlace: value=$value → mpv=$mpvValue")
            } catch (e: Throwable) {
                Log.e(TAG, "setDeinterlace failed", e)
            }
        }
    }

    /**
     * 运行时切换 MPV 日志等级。
     *
     * mpv 的 msg-level 既是启动选项（setOptionString）也是运行时属性（setPropertyString），
     * 因此无需重建 mpv 实例即可实时切换日志输出量。
     *
     * 与 MPVView.initialize 中的 setOptionString("msg-level", ...) 配合：
     * - 首次创建 mpv 实例时通过 setOptionString 设置初始值
     * - 运行时用户切换日志等级时通过此方法用 setPropertyString 更新
     *
     * @param level 日志等级：debug/info/warn/error
     */
    fun setMpvLogLevel(level: String) {
        val mpvMsgLevel = when (level) {
            "debug" -> "all=trace"
            "info" -> "all=info"
            "warn" -> "all=warn"
            "error" -> "all=error"
            else -> "all=info"
        }
        postOnUiThread {
            try {
                MPVLib.setPropertyString("msg-level", mpvMsgLevel)
                Log.i(TAG, "setMpvLogLevel: level=$level → msg-level=$mpvMsgLevel")
            } catch (e: Throwable) {
                Log.e(TAG, "setMpvLogLevel failed", e)
            }
        }
    }

    /**
     * 获取视频宽高比（用于 PiP 窗口比例设置，消除黑边）。
     * @return Rational(w, h) 或 null（无视频信息时）
     */
    fun getVideoAspectRatio(): android.util.Rational? {
        val w = _videoWidth.value
        val h = _videoHeight.value
        if (w <= 0 || h <= 0) return null
        // 约分以避免 Rational 分子分母过大抛 IllegalArgumentException
        val g = gcd(w, h)
        return try {
            android.util.Rational(w / g, h / g)
        } catch (e: Throwable) {
            null
        }
    }

    /**
     * 获取 MPVView 在屏幕上的可见矩形（用于 PiP 进入动画的 sourceBoundsHint）。
     * @return Rect 或 null（无 view 时）
     */
    fun getVideoBoundsOnScreen(): android.graphics.Rect? {
        val view = mpvView ?: return null
        val rect = android.graphics.Rect()
        val visible = view.asView().getGlobalVisibleRect(rect)
        return if (visible) rect else null
    }

    private fun gcd(a: Int, b: Int): Int = if (b == 0) a else gcd(b, a % b)

    // -----------------------------------------------------------------
    // 基础播放控制
    // -----------------------------------------------------------------
    @Volatile
    private var needPreStop = false

    @Volatile
    private var pendingLoadUrl: String = ""

    @Volatile
    private var loadingUrl: String = ""

    override fun playFile(url: String) {
        pendingLoadUrl = url
        postOnUiThread {
            if (pendingLoadUrl != url) {
                Log.i(TAG, "playFile: skipped, superseded by newer request (pending=$pendingLoadUrl, this=$url)")
                return@postOnUiThread
            }
            if (needPreStop) {
                try {
                    MPVLib.command(arrayOf("stop"))
                    MPVLib.command(arrayOf("playlist-clear"))
                    Log.i(TAG, "playFile: pre-stop + playlist-clear (recovering from error)")
                } catch (e: Throwable) {
                    Log.w(TAG, "playFile: pre-stop failed: ${e.message}")
                }
                needPreStop = false
            }
            setupProtocolOptions(url)
            _paused.value = false
            mpvView?.playFile(url)
        }
    }

    fun markNeedPreStop() {
        needPreStop = true
        Log.i(TAG, "markNeedPreStop: next playFile will pre-stop before loadfile")
    }

    fun getPath(): String {
        return try {
            MPVLib.getPropertyString("path") ?: ""
        } catch (e: Throwable) {
            Log.w(TAG, "getPath failed: ${e.message}")
            ""
        }
    }

    override fun stop() = postOnUiThread {
        mpvView?.stop()
    }

    override fun refreshSurface() {
        postOnUiThread {
            try {
                val vo = _voCache
                mpvView?.reattachSurfaceWithVo(vo)
                Log.i(TAG, "refreshSurface: reattached surface with vo=$vo")
            } catch (e: Exception) {
                Log.w(TAG, "refreshSurface failed: ${e.message}")
            }
        }
    }

    /**
     * 强制重建 mpv 核心。
     *
     * 当连续超时换源仍无法恢复播放时，调用此方法强制关闭并重建 mpv 核心，
     * 彻底清除卡死的 demuxer 和所有内部状态。
     *
     * 内部流程：
     * 1. MPVView.forceRecreate() 发送 quit 命令关闭旧核心
     * 2. 设置 forceRecreatePending 标志
     * 3. 下次 playFile() → ensureInstanceAlive() 检测到标志后重建核心
     */
    fun forceRecreate() = postOnUiThread {
        mpvView?.forceRecreate()
    }
    override fun togglePause() = postOnUiThread { MPVLib.command(arrayOf("cycle", "pause")) }
    override fun setPause(p: Boolean) = postOnUiThread { MPVLib.setPropertyBoolean("pause", p) }

    override fun seekTo(seconds: Double) =
        postOnUiThread { MPVLib.setPropertyDouble("time-pos", seconds) }

    override fun seekRelative(seconds: Double) =
        postOnUiThread { MPVLib.command(arrayOf("seek", seconds.toString(), "relative")) }

    override fun seekAbsolute(seconds: Double) =
        postOnUiThread { MPVLib.command(arrayOf("seek", seconds.toString(), "absolute")) }

    /**
     * 根据 URL 协议设置 mpv 解复用器/缓存选项。
     * 与 PC 端 services/mpv_player_service.py _setup_protocol_options 对齐。
     *
     * FCC 优化（快速换台）：
     * - 直播流使用小 readahead（1-3s），确保切台后尽快出画
     * - VOD/HLS 点播使用较大 readahead（10s），平衡起播速度与播放流畅性
     * - 配合 keep-open=yes 在切台间隙保持最后一帧，消除黑屏
     *
     * MPVView.initialize() 已设置通用缓冲（demuxer-max-bytes=16MiB,
     * demuxer-readahead-secs=1, force-seekable=yes），本方法针对特定协议覆盖。
     *
     * 本地文件不设置协议选项（直接 return）。
     */
    private fun setupProtocolOptions(url: String) {
        if (url.isEmpty()) return
        val u = url.lowercase()
        val isNetwork = u.startsWith("http://") || u.startsWith("https://") ||
                u.startsWith("rtsp://") || u.startsWith("rtp://") || u.startsWith("udp://") ||
                ".m3u8" in u
        if (!isNetwork) return  // 本地文件不设置协议选项

        val isFcc = "?fcc=" in u
        try {
            when {
                // HLS (m3u8)：与 PC 端 _setup_protocol_options 对齐
                ".m3u8" in u || "format=hls" in u -> {
                    MPVLib.setPropertyString("demuxer-lavf-format", "")
                    MPVLib.setPropertyString("cache", "yes")
                    MPVLib.setPropertyString("force-seekable", "yes")
                    MPVLib.setPropertyString("demuxer-readahead-secs", "120")
                    MPVLib.setPropertyString("cache-secs", "3600")
                    MPVLib.setPropertyString("prefetch-playlist", "yes")
                    Log.i(TAG, "HLS options: readahead=120s, cache-secs=3600, prefetch=yes")
                }
                // RTSP：与 PC 端对齐，区分 tcp/udp 传输
                u.startsWith("rtsp://") -> {
                    val transport = UserPrefs.getInstance().getRtspTransport()
                    MPVLib.setPropertyString("rtsp-transport", transport)
                    MPVLib.setPropertyString("user-agent", "VLC/3.0.18Libmpv")
                    MPVLib.setPropertyString("cache", "yes")
                    MPVLib.setPropertyString("demuxer-lavf-format", "")
                    MPVLib.setPropertyString("cache-secs", "60")
                    if (transport == "udp") {
                        // RTSP over UDP：小 probe 快速识别，低 readahead
                        MPVLib.setPropertyString("demuxer-lavf-probesize", "500000")
                        MPVLib.setPropertyString("demuxer-lavf-analyzeduration", "1")
                        MPVLib.setPropertyString("demuxer-readahead-secs", "5")
                        MPVLib.setPropertyString("force-seekable", "no")
                        Log.i(TAG, "RTSP-UDP options: probesize=500K, readahead=5s")
                    } else {
                        // RTSP over TCP：需要足够 probe 识别编码（如 CAVS）
                        MPVLib.setPropertyString("demuxer-lavf-probesize", "5000000")
                        MPVLib.setPropertyString("demuxer-lavf-analyzeduration", "5")
                        MPVLib.setPropertyString("demuxer-readahead-secs", "10")
                        Log.i(TAG, "RTSP-TCP options: probesize=5M, readahead=10s")
                    }
                }
                // MPEG-TS / UDP / RTP：IPTV 直播流，与 PC 端 looks_ts 分支对齐
                // 关键：用 probesize+analyzeduration 控制流识别速度（而非缩小 readahead）
                // cache-pause-initial=no + demuxer-cache-wait=no 确保不等待缓冲直接出画
                u.endsWith(".ts") || u.startsWith("udp://") || "/rtp/" in u || u.startsWith("rtp://") -> {
                    MPVLib.setPropertyString("demuxer", "lavf")
                    MPVLib.setPropertyString("demuxer-lavf-format", "mpegts")
                    MPVLib.setPropertyString("demuxer-lavf-buffersize", "128000")
                    if (isFcc) {
                        // FCC 快速换台：rtp2httpd 代理已预加入组播，流数据即时可用
                        // probesize 2MB 足够识别 H.264/H.265/CAVS 等编码
                        // analyzeduration 1s 进一步减少首帧等待（FCC 代理已缓冲流数据）
                        MPVLib.setPropertyString("demuxer-lavf-probesize", "2000000")
                        MPVLib.setPropertyString("demuxer-lavf-analyzeduration", "1")
                        // FCC 代理已预缓冲流数据，无需大 readahead，减少移动端内存压力
                        MPVLib.setPropertyString("demuxer-readahead-secs", "10")
                        MPVLib.setPropertyString("cache-secs", "60")
                    } else {
                        // 非 FCC 直播流：probesize 2MB 足够识别 H.264/H.265/CAVS 等编码
                        // 注意：Android ARM64 的 CAVS 解码器（libcavsdec）在缺少序列头时
                        // 可能 SIGSEGV，这是 llawsxx/FFmpeg patch 的 ARM64 特有 bug
                        MPVLib.setPropertyString("demuxer-lavf-probesize", "2000000")
                        MPVLib.setPropertyString("demuxer-lavf-analyzeduration", "1")
                        MPVLib.setPropertyString("demuxer-readahead-secs", "15")
                        MPVLib.setPropertyString("cache-secs", "120")
                    }
                    MPVLib.setPropertyString("cache", "yes")
                    MPVLib.setPropertyString("force-seekable", "yes")
                    MPVLib.setPropertyString("demuxer-seekable-cache", "yes")
                    Log.i(TAG, "TS/UDP/RTP options: probesize=${if (isFcc) "2M" else "2M"}, readahead=${if (isFcc) "10s" else "15s"}, fcc=$isFcc")
                }
                else -> {
                    // 通用网络流：与 PC 端默认分支对齐
                    MPVLib.setPropertyString("demuxer-lavf-format", "")
                    if (isFcc) {
                        // FCC 频道：降低探测参数和 readahead 加速首帧
                        MPVLib.setPropertyString("demuxer-lavf-probesize", "2000000")
                        MPVLib.setPropertyString("demuxer-lavf-analyzeduration", "1")
                        MPVLib.setPropertyString("demuxer-readahead-secs", "10")
                        MPVLib.setPropertyString("cache-secs", "60")
                    } else {
                        MPVLib.setPropertyString("demuxer-lavf-probesize", "5000000")
                        MPVLib.setPropertyString("demuxer-lavf-analyzeduration", "5")
                        MPVLib.setPropertyString("demuxer-readahead-secs", "15")
                        MPVLib.setPropertyString("cache-secs", "120")
                    }
                    MPVLib.setPropertyString("cache", "yes")
                    MPVLib.setPropertyString("force-seekable", "yes")
                    Log.i(TAG, "Generic stream options: probesize=${if (isFcc) "2M" else "5M"}, readahead=${if (isFcc) "10s" else "15s"}, fcc=$isFcc")
                }
            }
        } catch (e: Throwable) {
            Log.w(TAG, "setupProtocolOptions failed: ${e.message}")
        }
    }

    // -----------------------------------------------------------------
    // 音量 / 静音 / 速度
    // -----------------------------------------------------------------
    override fun setVolume(v: Int) =
        postOnUiThread { MPVLib.setPropertyInt("volume", v.coerceIn(0, 130)) }

    override fun adjustVolume(delta: Int) {
        val cur = _volume.value
        setVolume(cur + delta)
    }

    override fun toggleMute() = postOnUiThread { MPVLib.command(arrayOf("cycle", "mute")) }
    override fun setMute(m: Boolean) = postOnUiThread { MPVLib.setPropertyBoolean("mute", m) }

    override fun setSpeed(s: Double) =
        postOnUiThread { MPVLib.setPropertyDouble("speed", s.coerceIn(0.01, 100.0)) }

    // -----------------------------------------------------------------
    // 音轨 / 字幕轨
    // -----------------------------------------------------------------
    override fun cycleAudio() = postOnUiThread { MPVLib.command(arrayOf("cycle", "audio")) }
    override fun cycleSub() = postOnUiThread { MPVLib.command(arrayOf("cycle", "sub")) }

    /**
     * 设置音轨。id 对应 track-list 中 type=audio 项的 id。
     * 与 PC 端 set_track 一致：先 setPropertyInt，失败回退 command。
     */
    override fun setAudioTrack(id: Int) = postOnUiThread {
        try {
            MPVLib.setPropertyInt("aid", id)
        } catch (e: Exception) {
            MPVLib.command(arrayOf("set", "aid", id.toString()))
        }
    }

    override fun setSubTrack(id: Int) = postOnUiThread {
        try {
            MPVLib.setPropertyInt("sid", id)
        } catch (e: Exception) {
            MPVLib.command(arrayOf("set", "sid", id.toString()))
        }
    }

    /** 加载外挂字幕文件（select 表示立即选中） */
    override fun addSubtitleFile(path: String) =
        postOnUiThread { MPVLib.command(arrayOf("sub-add", path, "select")) }

    // -----------------------------------------------------------------
    // 字幕显示与样式
    // -----------------------------------------------------------------
    override fun setSubVisibility(v: Boolean) =
        postOnUiThread { MPVLib.setPropertyBoolean("sub-visibility", v) }

    override fun toggleSubVisibility() =
        postOnUiThread { MPVLib.command(arrayOf("cycle", "sub-visibility")) }

    override fun setSubDelay(delaySec: Double) =
        postOnUiThread { MPVLib.setPropertyDouble("sub-delay", delaySec) }

    override fun adjustSubDelay(delta: Double) = postOnUiThread {
        val cur = try { MPVLib.getPropertyDouble("sub-delay") ?: 0.0 } catch (_: Throwable) { 0.0 }
        MPVLib.setPropertyDouble("sub-delay", (cur + delta).coerceIn(-10.0, 10.0))
    }

    override fun setSubScale(scale: Double) =
        postOnUiThread { MPVLib.setPropertyDouble("sub-scale", scale.coerceIn(0.1, 10.0)) }

    override fun setSubPos(pos: Int) =
        postOnUiThread { MPVLib.setPropertyInt("sub-pos", pos.coerceIn(0, 100)) }

    /**
     * 批量应用字幕样式。style 的 key 是 mpv sub-* 属性后缀（如 "color"/"font-size"/"font"）。
     * 与 PC 端 apply_sub_style 对齐。
     */
    fun applySubStyle(style: Map<String, String>) = postOnUiThread {
        style.forEach { (k, v) -> MPVLib.setPropertyString("sub-$k", v) }
    }

    // -----------------------------------------------------------------
    // 章节
    // -----------------------------------------------------------------
    override fun setChapter(idx: Int): Boolean {
        postOnUiThread {
            try {
                MPVLib.setPropertyInt("chapter", idx)
            } catch (e: Exception) {
                MPVLib.command(arrayOf("set", "chapter", idx.toString()))
            }
        }
        return true
    }

    override fun chapterNext(): Boolean {
        postOnUiThread { MPVLib.command(arrayOf("add", "chapter", "1")) }
        return true
    }

    override fun chapterPrev(): Boolean {
        postOnUiThread { MPVLib.command(arrayOf("add", "chapter", "-1")) }
        return true
    }

    // -----------------------------------------------------------------
    // 画面调整（video EQ + 翻转 / 旋转 / 裁剪）
    // -----------------------------------------------------------------
    override fun setBrightness(v: Int): Boolean {
        postOnUiThread { MPVLib.setPropertyInt("brightness", v.coerceIn(-100, 100)) }
        return true
    }

    override fun setContrast(v: Int): Boolean {
        postOnUiThread { MPVLib.setPropertyInt("contrast", v.coerceIn(-100, 100)) }
        return true
    }

    override fun setSaturation(v: Int): Boolean {
        postOnUiThread { MPVLib.setPropertyInt("saturation", v.coerceIn(-100, 100)) }
        return true
    }

    override fun setHue(v: Int): Boolean {
        postOnUiThread { MPVLib.setPropertyInt("hue", v.coerceIn(-100, 100)) }
        return true
    }

    override fun setGamma(v: Int): Boolean {
        postOnUiThread { MPVLib.setPropertyInt("gamma", v.coerceIn(-100, 100)) }
        return true
    }

    override fun setVideoRotate(degree: Int): Boolean {
        postOnUiThread { MPVLib.setPropertyInt("video-rotate", degree) }
        return true
    }

    /**
     * 设置视频翻转。mode: "" / "horizontal" / "vertical" / "both"
     * 与 PC 端 set_video_flip 一致：先 remove 旧 @iptv_flip，再 add 新的。
     * 注意：hwdec 必须为 auto-copy 才能用 vf 滤镜（auto 模式直接输出，vf 不可用）。
     */
    override fun setVideoFlip(mode: String): Boolean {
        postOnUiThread {
            MPVLib.command(arrayOf("vf", "remove", "@iptv_flip"))
            val filters = when (mode) {
                "horizontal" -> listOf("hflip")
                "vertical" -> listOf("vflip")
                "both" -> listOf("hflip", "vflip")
                else -> emptyList()
            }
            if (filters.isNotEmpty()) {
                val expr = "lavfi=[" + filters.joinToString(",") + "]"
                MPVLib.command(arrayOf("vf", "add", "@iptv_flip:$expr"))
            }
        }
        return true
    }

    /**
     * 设置视频裁剪（黑边裁剪）。w/h=0 表示清除。
     */
    override fun setVideoCrop(x: Int, y: Int, w: Int, h: Int): Boolean {
        postOnUiThread {
            MPVLib.command(arrayOf("vf", "remove", "@iptv_crop"))
            if (w > 0 && h > 0) {
                MPVLib.command(arrayOf("vf", "add", "@iptv_crop:crop=$w:$h:$x:$y"))
            }
        }
        return true
    }

    override fun clearVideoCrop() {
        postOnUiThread { MPVLib.command(arrayOf("vf", "remove", "@iptv_crop")) }
    }

    override fun clearAllVideoFilters() {
        postOnUiThread {
            MPVLib.command(arrayOf("vf", "remove", "@iptv_flip"))
            MPVLib.command(arrayOf("vf", "remove", "@iptv_crop"))
            MPVLib.command(arrayOf("vf", "remove", "@iptv_360"))
        }
    }

    // -----------------------------------------------------------------
    // 3D 立体模式与 360° 视角（与 PC 端 set_video_stereo_mode / set_360_view 对齐）
    // -----------------------------------------------------------------

    /**
     * 设置 3D 立体模式。
     * mode: "mono" / "sbs" / "sbs2" / "ab" / "ab2"
     * 直接设置 mpv 的 video-stereo-mode 属性（运行时可改）。
     */
    override fun setVideoStereoMode(mode: String): Boolean {
        postOnUiThread { MPVLib.setPropertyString("video-stereo-mode", mode) }
        return true
    }

    override fun getVideoStereoMode(): String? {
        return MPVLib.getPropertyString("video-stereo-mode")
    }

    /**
     * 设置 360° 视角（panorama 滤镜）。
     * 先 remove 旧 @iptv_360，再 add 新的。
     * 注意：panorama 滤镜需 ffmpeg 编译时启用，部分设备可能不可用。
     * hwdec 必须为 auto-copy 才能用 vf 滤镜（auto 模式直接输出，vf 不可用）。
     */
    override fun set360View(yaw: Double, pitch: Double, roll: Double, projection: String): Boolean {
        postOnUiThread {
            MPVLib.command(arrayOf("vf", "remove", "@iptv_360"))
            val expr = "lavfi=[panorama=e=$projection:yaw=$yaw:pitch=$pitch:roll=$roll]"
            MPVLib.command(arrayOf("vf", "add", "@iptv_360:$expr"))
        }
        return true
    }

    override fun clear360Filter() {
        postOnUiThread { MPVLib.command(arrayOf("vf", "remove", "@iptv_360")) }
    }

    // -----------------------------------------------------------------
    // 音频调整
    // -----------------------------------------------------------------
    override fun setAudioDelay(delaySec: Double): Boolean {
        postOnUiThread { MPVLib.setPropertyDouble("audio-delay", delaySec.coerceIn(-10.0, 10.0)) }
        return true
    }

    override fun adjustAudioDelay(delta: Double): Boolean {
        postOnUiThread {
            val cur = try { MPVLib.getPropertyDouble("audio-delay") ?: 0.0 } catch (_: Throwable) { 0.0 }
            MPVLib.setPropertyDouble("audio-delay", (cur + delta).coerceIn(-10.0, 10.0))
        }
        return true
    }

    /**
     * 设置 10 段均衡器。gains 长度必须为 10，每段 -12 ~ +12 dB。
     * 与 PC 端 set_audio_eq 一致：先 remove @iptv_eq，全 0 不添加，否则 add equalizer=g1:g2:...:g10。
     */
    override fun setAudioEq(gains: List<Float>): Boolean {
        postOnUiThread {
            MPVLib.command(arrayOf("af", "remove", "@iptv_eq"))
            if (gains.size != 10 || gains.all { it == 0f }) return@postOnUiThread
            val eqStr = gains.joinToString(":") { "%.1f".format(it) }
            MPVLib.command(arrayOf("af", "add", "@iptv_eq:equalizer=$eqStr"))
        }
        return true
    }

    override fun resetAudioEq(): Boolean {
        postOnUiThread { MPVLib.command(arrayOf("af", "remove", "@iptv_eq")) }
        return true
    }

    /**
     * 设置音频音调（变调不变速）。与 PC 端 set_audio_pitch 一致。
     * 注意：audio-pitch-correction 是 mpv Flag（yes/no），不是浮点。
     * 保留 0.0~2.0 接口仅用于 UI 兼容：>=0.5 映射 yes，<0.5 映射 no。
     */
    override fun setAudioPitch(pitch: Double): Boolean {
        val flagVal = if (pitch >= 0.5) "yes" else "no"
        postOnUiThread { MPVLib.setPropertyString("audio-pitch-correction", flagVal) }
        return true
    }

    // -----------------------------------------------------------------
    // 截图
    // -----------------------------------------------------------------
    /**
     * 截图到文件。mode:
     *  - "video": 仅画面（不含 OSD/字幕）
     *  - "subtitles": 含字幕
     *  - "window": 含 OSD
     *  - "each-frame": 连续截图（每帧）
     */
    override fun screenshotToFile(path: String, mode: String): Boolean {
        postOnUiThread { MPVLib.command(arrayOf("screenshot-to-file", path, mode)) }
        return true
    }

    // -----------------------------------------------------------------
    // A/B 循环 + 单文件/列表循环 + 逐帧
    // -----------------------------------------------------------------
    override fun setAbLoopA(): Boolean {
        postOnUiThread {
            val t = MPVLib.getPropertyDouble("time-pos") ?: 0.0
            MPVLib.setPropertyDouble("ab-loop-a", t)
        }
        return true
    }

    override fun setAbLoopB(): Boolean {
        postOnUiThread {
            val t = MPVLib.getPropertyDouble("time-pos") ?: 0.0
            MPVLib.setPropertyDouble("ab-loop-b", t)
        }
        return true
    }

    override fun clearAbLoop() {
        postOnUiThread {
            MPVLib.setPropertyString("ab-loop-a", "no")
            MPVLib.setPropertyString("ab-loop-b", "no")
        }
    }

    /** mode: "no" / "inf" / "yes" / "once" */
    override fun setLoopFile(mode: String): Boolean {
        postOnUiThread { MPVLib.setPropertyString("loop-file", mode) }
        return true
    }

    /** mode: "no" / "inf" / "force" */
    override fun setLoopPlaylist(mode: String): Boolean {
        postOnUiThread { MPVLib.setPropertyString("loop-playlist", mode) }
        return true
    }

    override fun frameStep(): Boolean {
        postOnUiThread { MPVLib.command(arrayOf("frame-step")) }
        return true
    }

    override fun frameBackStep(): Boolean {
        postOnUiThread { MPVLib.command(arrayOf("frame-back-step")) }
        return true
    }

    // -----------------------------------------------------------------
    // OSD
    // -----------------------------------------------------------------
    override fun showOsd(text: String, durationMs: Int) {
        postOnUiThread { MPVLib.command(arrayOf("show-text", text, durationMs.toString())) }
    }

    // -----------------------------------------------------------------
    // 通用 API（覆盖所有未封装的 mpv 属性/命令）
    // -----------------------------------------------------------------
    override fun setPropertyString(name: String, value: String) =
        postOnUiThread { MPVLib.setPropertyString(name, value) }

    override fun setPropertyInt(name: String, value: Int) =
        postOnUiThread { MPVLib.setPropertyInt(name, value) }

    override fun setPropertyDouble(name: String, value: Double) =
        postOnUiThread { MPVLib.setPropertyDouble(name, value) }

    override fun setPropertyBoolean(name: String, value: Boolean) =
        postOnUiThread { MPVLib.setPropertyBoolean(name, value) }

    /**
     * 同步读取属性（在调用线程执行，注意 mpv 线程安全）。libmpv 未初始化时返回 null，避免 native 崩溃。
     *
     * 注意：mpv-android 构建中部分属性（如 protocol、demuxer-bitrate、estimated-vfps）不存在，
     * native 层会打印 "property not found" 错误日志。使用 try-catch 包裹以避免日志刷屏，
     * 同时返回 null 让 UI 层优雅降级。
     */
    override fun getPropertyString(name: String): String? =
        if (mpvView != null) {
            try { MPVLib.getPropertyString(name) } catch (e: Throwable) { null }
        } else null

    override fun getPropertyInt(name: String): Int? =
        if (mpvView != null) {
            try { MPVLib.getPropertyInt(name) } catch (e: Throwable) { null }
        } else null

    override fun getPropertyDouble(name: String): Double? =
        if (mpvView != null) {
            try { MPVLib.getPropertyDouble(name) } catch (e: Throwable) { null }
        } else null

    override fun getPropertyBoolean(name: String): Boolean? =
        if (mpvView != null) {
            try { MPVLib.getPropertyBoolean(name) } catch (e: Throwable) { null }
        } else null

    override fun command(args: Array<String>) = postOnUiThread { MPVLib.command(args) }

    // -----------------------------------------------------------------
    // 媒体信息（Player 接口实现）
    // -----------------------------------------------------------------
    /**
     * 获取媒体信息（codec/bitrate/fps/cacheDuration 等），UI 层 MediaBadgesRow 通过 key 读取。
     * 与 PC 端 MediaBadgesRow 显示的 key 对齐：
     * - videoCodec / audioCodec / videoRes / fps / bitrate / cacheDuration / avdiff
     */
    override fun getMediaInfo(): Map<String, String?> {
        if (mpvView == null) return emptyMap()
        return try {
                mapOf(
                "videoCodec" to safeGet("video-format"),
                "audioCodec" to safeGet("audio-codec-name"),
                "videoRes" to "${_videoWidth.value}x${_videoHeight.value}",
                "fps" to safeGet("container-fps"),
                "displayFps" to safeGet("display-fps"),
                "bitrate" to safeGet("video-bitrate"),
                "audioBitrate" to safeGet("audio-bitrate"),
                "cacheDuration" to safeGet("demuxer-cache-duration"),
                "avdiff" to safeGet("total-avsync-change"),
                "containerFormat" to safeGet("file-format"),
                "hwdec" to safeGet("hwdec-current"),
                "vo" to safeGet("vo"),
                "videoPrimaries" to safeGet("video-params/primaries"),
                "videoGamma" to safeGet("video-params/gamma"),
                "videoColorRange" to safeGet("video-params/color-range")
            )
        } catch (e: Throwable) {
            Log.w(TAG, "getMediaInfo failed: ${e.message}")
            emptyMap()
        }
    }

    private fun safeGet(name: String): String? =
        try { MPVLib.getPropertyString(name) } catch (_: Throwable) { null }

    // -----------------------------------------------------------------
    // HDR 重建协调（保存/恢复进度）
    // -----------------------------------------------------------------
    /**
     * 保存当前播放状态（用于 HDR 模式 / hwdec 模式切换 / 播放器切换前的重建）。
     * 返回 Pair<url, timePosSec>，重建后用 restorePlaybackState 恢复。
     * 返回 null 表示当前无文件播放。
     */
    override fun savePlaybackState(): Pair<String, Double>? {
        return try {
            val url = MPVLib.getPropertyString("path") ?: return null
            if (url.isEmpty()) return null
            val time = MPVLib.getPropertyDouble("time-pos") ?: 0.0
            url to time
        } catch (e: Throwable) {
            // MPVLib 可能因原生库加载失败而抛出 NoClassDefFoundError/UnsatisfiedLinkError
            // 此时 MPVView 未成功初始化，无状态可保存
            Log.w(TAG, "savePlaybackState failed (MPVLib not initialized?): ${e.message}")
            null
        }
    }

    /**
     * 重建后恢复播放状态。
     *
     * 关键修复：使用 [MPVView.playFile] 而非直接调用 MPVLib.command("loadfile")。
     *
     * 原因：Surface 重建后复用 native mpv 实例时，
     * mpv 的 vo 仍为 "null"（destroy() 时设置），Surface 尚未 attach。
     * 若直接 loadfile，mpv 在 vo=null + 无 Surface 的状态下加载文件，
     * 后续 surfaceCreated 恢复 vo 后 mpv 已陷入无法渲染的状态。
     *
     * playFile 会检查 Surface 有效性：
     * - Surface 未就绪 → 存入 filePath，等 surfaceCreated 时（vo 已恢复）才 loadfile
     * - Surface 已就绪 → 直接 loadfile（vo 已在 surfaceCreated 中恢复）
     *
     * seek 位置通过 [MPVView.pendingResumePos] 传递，
     * FILE_LOADED 事件回调中读取并执行 seek。
     */
    override fun restorePlaybackState(url: String, timePosSec: Double) {
        postOnUiThread {
            val v = mpvView
            if (v != null) {
                // 先设置 pendingResumePos，FILE_LOADED 事件回调中会读取并 seek
                if (timePosSec > 0) {
                    v.pendingResumePos = timePosSec
                }
                // 通过 playFile 加载：Surface 未就绪时延迟到 surfaceCreated
                v.playFile(url)
            } else {
                // mpvView 为 null 时的兜底（正常流程不应发生）
                MPVLib.command(arrayOf("loadfile", url))
                if (timePosSec > 0) {
                    MPVLib.command(arrayOf("seek", timePosSec.toString(), "absolute", "exact"))
                }
                MPVLib.setPropertyBoolean("pause", false)
            }
        }
    }

    // -----------------------------------------------------------------
    // 内部：把命令 post 到 MPVView 线程（mpv 要求同线程访问）
    // -----------------------------------------------------------------
    private fun postOnUiThread(block: () -> Unit) {
        val v = mpvView
        if (v != null) {
            v.asView().post { block() }
        } else {
            Log.w(TAG, "MPVView not attached, skip command")
        }
    }

    // -----------------------------------------------------------------
    // EventObserver 实现：把 mpv 属性变化转发到 StateFlow
    // -----------------------------------------------------------------
    override fun eventProperty(property: String) {
        // 空值属性变化（无 value 的属性）
    }

    override fun eventProperty(property: String, value: Long) {
        when (property) {
            "volume" -> _volume.value = value.toInt()
            "chapter" -> _currentChapter.value = value.toInt()
            "chapter-count" -> _chapterCount.value = value.toInt()
            "width" -> _videoWidth.value = value.toInt()
            "height" -> _videoHeight.value = value.toInt()
        }
    }

    override fun eventProperty(property: String, value: Boolean) {
        when (property) {
            "pause" -> _paused.value = value
            "mute" -> _muted.value = value
            "eof-reached" -> _eofReached.value = value
            "sub-visibility" -> { /* 由 UI 主动查询，不缓存 */ }
        }
    }

    override fun eventProperty(property: String, value: Double) {
        when (property) {
            "time-pos" -> _timePos.value = value
            "duration" -> _duration.value = value
            "speed" -> _speed.value = value
        }
    }

    override fun eventProperty(property: String, value: String) {
        when (property) {
            "media-title" -> _mediaTitle.value = value
            "track-list" -> _trackListJson.value = value
            "path" -> {
                // 路径变化意味着新文件加载，重置结束标志
                _eofReached.value = false
            }
        }
    }

    override fun event(eventId: Int) {
        when (eventId) {
            MPVLib.MpvEvent.MPV_EVENT_FILE_LOADED -> {
                _fileLoaded.value = true
                _eofReached.value = false
                loadingUrl = ""
                // Surface 重建后重新 loadfile，恢复播放位置（本地文件/VOD）
                // 直播流 pendingResumePos=-1.0 不 seek，从最新位置播放
                mpvView?.let { v ->
                    val pos = v.pendingResumePos
                    if (pos > 0) {
                        v.pendingResumePos = -1.0
                        postOnUiThread {
                            try {
                                MPVLib.command(arrayOf("seek", pos.toString(), "absolute"))
                            } catch (e: Throwable) {
                                Log.w(TAG, "resume seek after surface rebuild failed: ${e.message}")
                            }
                        }
                    }
                }
                // 黑屏检测：文件加载后 6 秒检查 videoWidth，若解码器没工作则 fallback。
                // 仅以 videoWidth==0 为准（不使用 estimated-vfps，避免 IPTV 流误判）。
                scheduleBlackScreenCheck()
            }
            MPVLib.MpvEvent.MPV_EVENT_START_FILE -> {
                _fileLoaded.value = false
                _eofReached.value = false
                loadingUrl = pendingLoadUrl
                Log.i(TAG, "MPV_EVENT_START_FILE: loadingUrl=$loadingUrl")
            }
            MPVLib.MpvEvent.MPV_EVENT_END_FILE -> {
                val wasLoaded = _fileLoaded.value
                _fileLoaded.value = false
                _videoWidth.value = 0
                _videoHeight.value = 0
                val endedUrl = try { MPVLib.getPropertyString("path") ?: "" } catch (_: Throwable) { "" }
                if (!wasLoaded) {
                    if (endedUrl != loadingUrl && loadingUrl.isNotEmpty()) {
                        Log.i(TAG, "MPV_EVENT_END_FILE: old stream '$endedUrl' replaced by '$loadingUrl', not an error")
                    } else {
                        Log.w(TAG, "MPV_EVENT_END_FILE: file '$endedUrl' failed to load, notifying error")
                        postOnUiThread { onFileError?.invoke() }
                    }
                }
                loadingUrl = ""
            }
            MPVLib.MpvEvent.MPV_EVENT_SHUTDOWN -> {
                Log.w(TAG, "MPV_EVENT_SHUTDOWN: mpv core has shut down, marking instance as dead")
                _fileLoaded.value = false
                _eofReached.value = true
                // 标记 native 实例已死亡，使下次 playFile 时能重新创建 mpv 实例。
                // 不在此处立即重建——重建需要在 UI 线程执行且涉及 surface 操作，
                // 由 playFile 中的 ensureInstanceAlive() 延迟处理更安全。
                mpvView?.markInstanceDead()
            }
        }
    }

    /** 黑屏检测重试计数（避免直播流缓冲期间 videoWidth 暂时为 0 导致误判） */
    private var blackScreenRetryCount = 0

    /**
     * 是否已尝试过 fbo-format 降级（rgba16hf → rgba8）。
     * 仅在 HDR 模式启用时 fbo-format 为 rgba16hf 才有意义。
     * HDR 关闭时 fbo-format 已默认为 rgba8，跳过降级直接 fallback。
     */
    @Volatile
    private var fboFormatDowngraded = false

    /**
     * 黑屏检测 Runnable：检查 videoWidth，若解码器没工作则触发 vo fallback。
     *
     * 分级 Fallback 策略：
     * 1. videoWidth==0 + vo=gpu/gpu-next + fbo-format=rgba16hf + 未降级 →
     *    尝试 fbo-format=rgba8（解决不支持 rgba16hf 的 GPU）
     * 2. videoWidth==0 + 其他情况（fbo-format 已为 rgba8 或已降级）→
     *    切换到 mediacodec_embed（绕过 GPU 渲染管线）
     *
     * 判断依据（仅 videoWidth==0）：
     * - videoWidth==0 表示解码器没有输出视频帧，是确定的黑屏
     * - 不再使用 estimated-vfps：IPTV 直播流（通过 rt2phttpd HTTP 代理）的
     *   estimated-vfps 可能长时间为 0，即使视频正常渲染，会导致误判
     *
     * 防误判机制：
     * - 首次检测到 videoWidth==0 后 3 秒复查，连续两次确认才 fallback
     * - 首次检测在文件加载后 6 秒（scheduleBlackScreenCheck），复查在 9 秒
     *
     * 不持久化 fallback 结果：
     * - fallback 仅在本次会话生效，不写 setVoFallbackConfirmed(true)
     * - 避免误判永久化（曾出现 IPTV 流 estimated-vfps 误判导致用户设备
     *   被永久锁定为 mediacodec_embed，即使 GPU 正常）
     * - 用户若需永久切换 vo，可在播放器设置中手动切换
     */
    private val blackScreenCheckRunnable: Runnable = Runnable {
        if (voFallbackTriggered) return@Runnable
        if (!_fileLoaded.value) return@Runnable

        // 当前 vo：如果已经是 mediacodec_embed（用户手动切换），不需要 fallback
        val currentVo = try {
            MPVLib.getPropertyString("vo") ?: ""
        } catch (e: Throwable) {
            Log.w(TAG, "getPropertyString(vo) failed", e)
            ""
        }
        if (currentVo == "mediacodec_embed" || currentVo.isEmpty()) return@Runnable

        // 黑屏判断：仅以 videoWidth==0 为准
        // 注意：不使用 estimated-vfps，因为 IPTV 直播流（通过 rt2phttpd HTTP 代理）的
        // estimated-vfps 可能长时间为 0，即使视频正常渲染，会导致误判 fallback。
        val videoWidth = _videoWidth.value
        val estimatedVfps = try {
            MPVLib.getPropertyDouble("estimated-vfps") ?: 0.0
        } catch (_: Throwable) { 0.0 }

        Log.d(TAG, "blackScreenCheck: vo=$currentVo, videoWidth=$videoWidth, vfps=$estimatedVfps, attempt=${blackScreenRetryCount + 1}, fboDowngraded=$fboFormatDowngraded")

        // 黑屏条件：仅以 videoWidth==0 为准
        // 不使用 estimated-vfps 判断：IPTV 直播流的 estimated-vfps 经常长时间为0，
        // 即使视频正常渲染也会误判为 GPU 渲染失败，导致从 gpu 错误 fallback 到 gpu-next。
        val isBlackScreen = videoWidth == 0

        if (isBlackScreen) {
            blackScreenRetryCount++
            if (blackScreenRetryCount < 2) {
                // 首次检测到黑屏：可能是直播流还在缓冲，3 秒后复查
                Log.w(TAG, "Possible black screen (attempt $blackScreenRetryCount, videoWidth=$videoWidth, vfps=$estimatedVfps), retrying in 3s...")
                mpvView?.asView()?.postDelayed(blackScreenCheckRunnable, 3000)
                return@Runnable
            }
            // 连续两次检测到 videoWidth==0，确认黑屏
            // 检查当前 fbo-format：仅当为 rgba16hf 时才尝试降级
            val currentFboFormat = try {
                MPVLib.getPropertyString("fbo-format") ?: "rgba8"
            } catch (_: Throwable) { "rgba8" }
            if (!fboFormatDowngraded && currentFboFormat == "rgba16hf" &&
                (currentVo == "gpu" || currentVo == "gpu-next")) {
                // 第一级：fbo-format 降级（rgba16hf → rgba8）
                // 某些 GPU（如旧 Mali/Adreno）不支持 16-bit 浮点帧缓冲，
                // EGL 初始化成功但渲染失败导致黑屏。降级到 rgba8 可恢复渲染。
                Log.w(TAG, "Black screen confirmed (videoWidth=0, vo=$currentVo), trying fbo-format=rgba8 downgrade")
                fboFormatDowngraded = true
                blackScreenRetryCount = 0  // 重置计数，给降级后的 VO 第二次检测机会
                try {
                    // 尝试运行时修改 fbo-format（mpv gpu VO 支持运行时属性修改）
                    MPVLib.setPropertyString("fbo-format", "rgba8")
                    // 重新加载文件触发新 FBO 格式渲染
                    val path = MPVLib.getPropertyString("path")
                    if (path != null && path.isNotEmpty()) {
                        MPVLib.command(arrayOf("loadfile", path))
                        MPVLib.setPropertyBoolean("pause", false)
                    }
                    Log.i(TAG, "fbo-format downgraded to rgba8, reloading...")
                    // 6 秒后再次检测是否恢复
                    mpvView?.asView()?.postDelayed(blackScreenCheckRunnable, 6000)
                } catch (e: Throwable) {
                    Log.e(TAG, "fbo-format downgrade failed", e)
                    // 降级失败，直接 fallback 到 mediacodec_embed
                    fallbackToMediacodecEmbed()
                }
            } else {
                // 第二级：切换到 mediacodec_embed（绕过 GPU 渲染管线）
                fallbackToMediacodecEmbed()
            }
        }
    }

    /**
     * Fallback 到 mediacodec_embed VO（绕过 GPU 渲染管线，直接用 MediaCodec 渲染到 Surface）。
     */
    private fun fallbackToMediacodecEmbed() {
        Log.w(TAG, "Falling back to vo=mediacodec_embed")
        voFallbackTriggered = true
        try {
            MPVLib.setPropertyString("hwdec", "mediacodec")
            mpvView?.reattachSurfaceWithVo("mediacodec_embed")
            // 重新加载当前文件以触发 mediacodec 渲染
            val path = MPVLib.getPropertyString("path")
            if (path != null && path.isNotEmpty()) {
                MPVLib.command(arrayOf("loadfile", path))
                MPVLib.setPropertyBoolean("pause", false)
            }
            // 不持久化：仅本次会话生效，避免误判永久化
            Log.i(TAG, "Switched to vo=mediacodec_embed (session only, not persisted)")
            Log.i(TAG, "diagnostic: ${mpvView?.getDiagnosticInfo()}")
            // 通知 AppViewModel 更新 UI 状态（_currentVo / _currentHwdec）
            onVoFallback?.invoke("mediacodec_embed", "mediacodec")
        } catch (e: Throwable) {
            Log.e(TAG, "Fallback to mediacodec_embed failed", e)
        }
    }

    /**
     * 安排黑屏检测（在文件加载后 6 秒执行，给直播流足够缓冲时间，避免 videoWidth 误判）。
     */
    private fun scheduleBlackScreenCheck() {
        val view = mpvView ?: return
        view.asView().removeCallbacks(blackScreenCheckRunnable)
        blackScreenRetryCount = 0
        // 记录诊断信息，方便排查黑屏问题
        Log.i(TAG, "scheduleBlackScreenCheck: diagnostic=${mpvView?.getDiagnosticInfo()}")
        view.asView().postDelayed(blackScreenCheckRunnable, 6000)
    }

    companion object {
        private const val TAG = "MpvController"

        @Volatile
        private var INSTANCE: MpvController? = null

        fun getInstance(): MpvController =
            INSTANCE ?: synchronized(this) {
                INSTANCE ?: MpvController().also { INSTANCE = it }
            }
    }
}
