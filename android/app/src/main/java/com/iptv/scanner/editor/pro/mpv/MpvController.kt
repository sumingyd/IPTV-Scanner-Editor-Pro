package com.iptv.scanner.editor.pro.mpv

import android.util.Log
import `is`.xyz.mpv.MPVLib
import com.iptv.scanner.editor.pro.data.UserPrefs
import com.iptv.scanner.editor.pro.mpv.controller.MpvAudioEqController
import com.iptv.scanner.editor.pro.mpv.controller.MpvControllerHost
import com.iptv.scanner.editor.pro.mpv.controller.MpvFilterController
import com.iptv.scanner.editor.pro.mpv.controller.MpvPlaybackController
import com.iptv.scanner.editor.pro.mpv.controller.MpvScreenshotController
import com.iptv.scanner.editor.pro.mpv.controller.MpvSubtitleController
import com.iptv.scanner.editor.pro.mpv.controller.MpvVideoEqController
import com.iptv.scanner.editor.pro.player.Player
import com.iptv.scanner.editor.pro.player.PlayerCapabilities
import com.iptv.scanner.editor.pro.player.PlayerType
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * Compose 友好的 mpv 控制器门面：单例，持有 MPVView 引用，
 * 把 MPVLib 的属性/命令包装为 StateFlow + 命令方法。
 *
 * 门面委托 6 个子控制器：
 * - MpvPlaybackController：播放控制（playFile/stop/pause/seek/volume/speed/音轨/章节/AB循环/逐帧）
 * - MpvVideoEqController：视频均衡（亮度/对比度/饱和度/色相/Gamma/反交错/旋转/翻转/裁剪/3D）
 * - MpvAudioEqController：音频均衡（延迟/10段EQ/音调/声道信息/声道监控）
 * - MpvSubtitleController：字幕（可见性/延迟/缩放/位置/样式）
 * - MpvScreenshotController：截图
 * - MpvFilterController：滤镜（360°/运动补偿/超分辨率/着色器）
 *
 * 门面保留：生命周期管理、EventObserver、StateFlow 声明、通用属性/命令 API、媒体信息。
 */
class MpvController : MPVLib.EventObserver, Player, MpvControllerHost {

    override val playerType = PlayerType.MPV

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

    // -----------------------------------------------------------------
    // StateFlow（Compose 可观察状态）
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

    @Volatile
    var onFileError: (() -> Unit)? = null

    @Volatile
    private var suppressFileErrorFlag = false

    private val _speed = MutableStateFlow(1.0)
    override val speed: StateFlow<Double> = _speed.asStateFlow()

    @Volatile
    private var _hwdecCache: String = "auto-copy"

    @Volatile
    private var _voCache: String = "gpu"

    private val unavailableProperties = mutableSetOf<String>()

    // -----------------------------------------------------------------
    // 子控制器
    // -----------------------------------------------------------------
    private val playbackController = MpvPlaybackController(this)
    private val videoEqController = MpvVideoEqController(this)
    private val audioEqController = MpvAudioEqController(this)
    private val subtitleController = MpvSubtitleController(this)
    private val screenshotController = MpvScreenshotController(this)
    private val filterController = MpvFilterController(this)

    // -----------------------------------------------------------------
    // MpvControllerHost 实现
    // -----------------------------------------------------------------
    override fun postOnUiThread(block: () -> Unit) {
        val v = mpvView
        if (v != null) {
            v.asView().post { block() }
        } else {
            Log.w(TAG, "MPVView not attached, skip command")
        }
    }

    override fun getMpvView(): MPVViewLike? = mpvView

    override fun isFileLoaded(): Boolean = _fileLoaded.value

    override fun getCurrentVolume(): Int = _volume.value

    // -----------------------------------------------------------------
    // 生命周期
    // -----------------------------------------------------------------
    fun attach(view: MPVViewLike) {
        this.mpvView = view
        MPVLib.addObserver(this)
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

        try {
            val currentPause = MPVLib.getPropertyBoolean("pause") ?: true
            _paused.value = currentPause
            Log.i(TAG, "attach: synced pause state from mpv: $currentPause")
        } catch (e: Throwable) {
            Log.w(TAG, "attach: sync pause state failed: ${e.message}")
        }

        videoEqController.setDeinterlace(UserPrefs.getInstance().getDeinterlace())

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
            videoEqController.setDeinterlace(UserPrefs.getInstance().getDeinterlace())
        }

        view.onSurfaceRebuilt = {
            cancelPendingFileError()
            clearSuppressFileError(delayMs = 1000)
        }

        view.onSurfaceAboutToDestroy = {
            suppressFileError()
            Log.i(TAG, "onSurfaceAboutToDestroy: suppressFileError enabled")
        }

        Log.i(TAG, "MpvController attached to MPVView")
    }

    override fun attachView(view: Any) {
        if (view is MPVViewLike) {
            attach(view)
        } else {
            Log.w(TAG, "attachView: view is not MPVViewLike (${view.javaClass.name}), ignored")
        }
    }

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
        try {
            MPVLib.removeObserver(this)
        } catch (e: Exception) {
            Log.w(TAG, "detach: removeObserver failed: ${e.message}")
        }
        this.mpvView = null
        _fileLoaded.value = false
        _eofReached.value = false
        _timePos.value = 0.0
        _duration.value = 0.0
        _paused.value = true
        Log.i(TAG, "MpvController detached")
    }

    // -----------------------------------------------------------------
    // vo / hwdec（门面保留，涉及 _voCache/_hwdecCache 和 reattachSurfaceWithVo）
    // -----------------------------------------------------------------
    fun setVoAndHwdec(vo: String, hwdec: String): String? {
        val hasFile = _fileLoaded.value
        postOnUiThread {
            try {
                MPVLib.setPropertyString("hwdec", hwdec)
                _hwdecCache = hwdec
                mpvView?.reattachSurfaceWithVo(vo)
                _voCache = vo

                val path = MPVLib.getPropertyString("path")
                if (path != null && path.isNotEmpty()) {
                    MPVLib.command(arrayOf("loadfile", path))
                    MPVLib.setPropertyBoolean("pause", false)
                }
                Log.i(TAG, "setVoAndHwdec: vo=$vo, hwdec=$hwdec, hasFile=$hasFile")
                Log.i(TAG, "diagnostic: ${mpvView?.getDiagnosticInfo()}")
            } catch (e: Throwable) {
                Log.e(TAG, "setVoAndHwdec failed", e)
            }
        }
        return if (hasFile) "reloaded" else null
    }

    override fun setHardwareDecode(enabled: Boolean): Boolean {
        val currentVo = try { _voCache } catch (e: Throwable) { "gpu" }

        if (!enabled && currentVo == "mediacodec_embed") {
            Log.w(TAG, "setHardwareDecode: vo=mediacodec_embed 不支持软解")
            return false
        }

        val currentHwdec = _hwdecCache
        val hwdec = when {
            !enabled -> "no"
            currentVo == "mediacodec_embed" -> "mediacodec"
            currentHwdec == "auto" -> "auto"
            else -> "auto-copy"
        }
        setVoAndHwdec(currentVo, hwdec)
        Log.i(TAG, "setHardwareDecode: enabled=$enabled, vo=$currentVo, hwdec=$hwdec")
        return true
    }

    override fun isHardwareDecodeEnabled(): Boolean {
        return try {
            val hwdec = _hwdecCache
            hwdec != "no"
        } catch (e: Throwable) { true }
    }

    // -----------------------------------------------------------------
    // 日志等级 / 视频信息（门面保留，依赖 StateFlow）
    // -----------------------------------------------------------------
    fun setMpvLogLevel(level: String) {
        val mpvMsgLevel = MpvLogLevelMapper.toMpvValue(level)
        postOnUiThread {
            try {
                MPVLib.setPropertyString("msg-level", mpvMsgLevel)
                Log.i(TAG, "setMpvLogLevel: level=$level → msg-level=$mpvMsgLevel")
            } catch (e: Throwable) {
                Log.e(TAG, "setMpvLogLevel failed", e)
            }
        }
    }

    fun getVideoAspectRatio(): android.util.Rational? {
        val w = _videoWidth.value
        val h = _videoHeight.value
        if (w <= 0 || h <= 0) return null
        val g = gcd(w, h)
        return try {
            android.util.Rational(w / g, h / g)
        } catch (e: Throwable) {
            null
        }
    }

    fun getVideoBoundsOnScreen(): android.graphics.Rect? {
        val view = mpvView ?: return null
        val rect = android.graphics.Rect()
        val visible = view.asView().getGlobalVisibleRect(rect)
        return if (visible) rect else null
    }

    private fun gcd(a: Int, b: Int): Int = if (b == 0) a else gcd(b, a % b)

    // -----------------------------------------------------------------
    // Surface / 文件错误抑制（门面保留，涉及 suppressFileErrorFlag 和 mpvView）
    // -----------------------------------------------------------------
    override fun refreshSurface() {
        postOnUiThread {
            try {
                val vo = _voCache
                cancelPendingFileError()
                mpvView?.reattachSurfaceWithVo(vo)
                Log.i(TAG, "refreshSurface: reattached surface with vo=$vo")
            } catch (e: Exception) {
                Log.w(TAG, "refreshSurface failed: ${e.message}")
            }
        }
    }

    fun cancelPendingFileError() {
        playbackController.pendingEndFileError?.let { mpvView?.asView()?.removeCallbacks(it) }
        playbackController.pendingEndFileError = null
    }

    fun suppressFileError() {
        suppressFileErrorFlag = true
        cancelPendingFileError()
        Log.i(TAG, "suppressFileError: enabled")
    }

    fun clearSuppressFileError(delayMs: Long = 800) {
        mpvView?.asView()?.postDelayed({
            suppressFileErrorFlag = false
            Log.i(TAG, "clearSuppressFileError: disabled after ${delayMs}ms")
        }, delayMs)
    }

    fun forceRecreate() = postOnUiThread {
        mpvView?.forceRecreate()
    }

    // -----------------------------------------------------------------
    // 播放控制（委托 MpvPlaybackController）
    // -----------------------------------------------------------------
    override fun playFile(url: String) = playbackController.playFile(url)
    fun markNeedPreStop() = playbackController.markNeedPreStop()
    fun getPath(): String = playbackController.getPath()
    override fun stop() = playbackController.stop()
    override fun togglePause() = playbackController.togglePause()
    override fun setPause(p: Boolean) = playbackController.setPause(p)
    override fun seekTo(seconds: Double) = playbackController.seekTo(seconds)
    override fun seekRelative(seconds: Double) = playbackController.seekRelative(seconds)
    override fun seekAbsolute(seconds: Double) = playbackController.seekAbsolute(seconds)
    override fun setVolume(v: Int) = playbackController.setVolume(v)
    override fun adjustVolume(delta: Int) = playbackController.adjustVolume(delta)
    override fun toggleMute() = playbackController.toggleMute()
    override fun setMute(m: Boolean) = playbackController.setMute(m)
    override fun setSpeed(s: Double) = playbackController.setSpeed(s)
    override fun cycleAudio() = playbackController.cycleAudio()
    override fun cycleSub() = playbackController.cycleSub()
    override fun setAudioTrack(id: Int) = playbackController.setAudioTrack(id)
    override fun setSubTrack(id: Int) = playbackController.setSubTrack(id)
    override fun addSubtitleFile(path: String) = playbackController.addSubtitleFile(path)
    override fun setChapter(idx: Int): Boolean = playbackController.setChapter(idx)
    override fun chapterNext(): Boolean = playbackController.chapterNext()
    override fun chapterPrev(): Boolean = playbackController.chapterPrev()
    override fun setAbLoopA(): Boolean = playbackController.setAbLoopA()
    override fun setAbLoopB(): Boolean = playbackController.setAbLoopB()
    override fun clearAbLoop() = playbackController.clearAbLoop()
    override fun setLoopFile(mode: String): Boolean = playbackController.setLoopFile(mode)
    override fun setLoopPlaylist(mode: String): Boolean = playbackController.setLoopPlaylist(mode)
    override fun frameStep(): Boolean = playbackController.frameStep()
    override fun frameBackStep(): Boolean = playbackController.frameBackStep()
    override fun showOsd(text: String, durationMs: Int) = playbackController.showOsd(text, durationMs)

    // -----------------------------------------------------------------
    // 视频均衡（委托 MpvVideoEqController）
    // -----------------------------------------------------------------
    fun setDeinterlace(value: String) = videoEqController.setDeinterlace(value)
    override fun setBrightness(v: Int): Boolean = videoEqController.setBrightness(v)
    override fun setContrast(v: Int): Boolean = videoEqController.setContrast(v)
    override fun setSaturation(v: Int): Boolean = videoEqController.setSaturation(v)
    override fun setHue(v: Int): Boolean = videoEqController.setHue(v)
    override fun setGamma(v: Int): Boolean = videoEqController.setGamma(v)
    override fun setVideoRotate(degree: Int): Boolean = videoEqController.setVideoRotate(degree)
    override fun setVideoFlip(mode: String): Boolean = videoEqController.setVideoFlip(mode)
    override fun setVideoCrop(x: Int, y: Int, w: Int, h: Int): Boolean = videoEqController.setVideoCrop(x, y, w, h)
    override fun clearVideoCrop() = videoEqController.clearVideoCrop()
    override fun setVideoStereoMode(mode: String): Boolean = videoEqController.setVideoStereoMode(mode)
    override fun getVideoStereoMode(): String? = videoEqController.getVideoStereoMode()

    // -----------------------------------------------------------------
    // 音频均衡（委托 MpvAudioEqController）
    // -----------------------------------------------------------------
    override fun setAudioDelay(delaySec: Double): Boolean = audioEqController.setAudioDelay(delaySec)
    override fun adjustAudioDelay(delta: Double): Boolean = audioEqController.adjustAudioDelay(delta)
    override fun setAudioEq(gains: List<Float>): Boolean = audioEqController.setAudioEq(gains)
    override fun resetAudioEq(): Boolean = audioEqController.resetAudioEq()
    override fun setAudioPitch(pitch: Double): Boolean = audioEqController.setAudioPitch(pitch)
    override fun getAudioChannelInfo(): Map<String, Any> = audioEqController.getAudioChannelInfo()
    override fun startChannelMonitor(): Boolean = audioEqController.startChannelMonitor()
    override fun stopChannelMonitor() = audioEqController.stopChannelMonitor()
    override fun getChannelLevels(): Map<Int, Float> = audioEqController.getChannelLevels()

    // -----------------------------------------------------------------
    // 字幕（委托 MpvSubtitleController）
    // -----------------------------------------------------------------
    override fun setSubVisibility(v: Boolean) = subtitleController.setSubVisibility(v)
    override fun toggleSubVisibility() = subtitleController.toggleSubVisibility()
    override fun setSubDelay(delaySec: Double) = subtitleController.setSubDelay(delaySec)
    override fun adjustSubDelay(delta: Double) = subtitleController.adjustSubDelay(delta)
    override fun setSubScale(scale: Double) = subtitleController.setSubScale(scale)
    override fun setSubPos(pos: Int) = subtitleController.setSubPos(pos)
    fun applySubStyle(style: Map<String, String>) = subtitleController.applySubStyle(style)

    // -----------------------------------------------------------------
    // 截图（委托 MpvScreenshotController）
    // -----------------------------------------------------------------
    override fun screenshotToFile(path: String, mode: String): Boolean = screenshotController.screenshotToFile(path, mode)

    // -----------------------------------------------------------------
    // 滤镜（委托 MpvFilterController）
    // -----------------------------------------------------------------
    override fun clearAllVideoFilters() = filterController.clearAllVideoFilters()
    override fun set360View(yaw: Double, pitch: Double, roll: Double, projection: String): Boolean = filterController.set360View(yaw, pitch, roll, projection)
    override fun clear360Filter() = filterController.clear360Filter()
    override fun setMotionCompensation(strength: String, targetFps: Int): Boolean = filterController.setMotionCompensation(strength, targetFps)
    override fun clearMotionCompensation() = filterController.clearMotionCompensation()
    override fun setSuperResolution(scaleAlgo: String, detailEnhance: Int): Boolean = filterController.setSuperResolution(scaleAlgo, detailEnhance)
    override fun clearSuperResolution() = filterController.clearSuperResolution()
    override fun setUserShader(preset: String): Boolean = filterController.setUserShader(preset)
    override fun clearUserShader() = filterController.clearUserShader()

    // -----------------------------------------------------------------
    // 通用 API
    // -----------------------------------------------------------------
    override fun setPropertyString(name: String, value: String) =
        postOnUiThread { MPVLib.setPropertyString(name, value) }

    override fun setPropertyInt(name: String, value: Int) =
        postOnUiThread { MPVLib.setPropertyInt(name, value) }

    override fun setPropertyDouble(name: String, value: Double) =
        postOnUiThread { MPVLib.setPropertyDouble(name, value) }

    override fun setPropertyBoolean(name: String, value: Boolean) =
        postOnUiThread { MPVLib.setPropertyBoolean(name, value) }

    override fun getPropertyString(name: String): String? =
        if (mpvView != null) { try { MPVLib.getPropertyString(name) } catch (e: Throwable) { null } } else null

    override fun getPropertyInt(name: String): Int? =
        if (mpvView != null) { try { MPVLib.getPropertyInt(name) } catch (e: Throwable) { null } } else null

    override fun getPropertyDouble(name: String): Double? =
        if (mpvView != null) { try { MPVLib.getPropertyDouble(name) } catch (e: Throwable) { null } } else null

    override fun getPropertyBoolean(name: String): Boolean? =
        if (mpvView != null) { try { MPVLib.getPropertyBoolean(name) } catch (e: Throwable) { null } } else null

    override fun command(args: Array<String>) = postOnUiThread { MPVLib.command(args) }

    // -----------------------------------------------------------------
    // 媒体信息
    // -----------------------------------------------------------------
    override fun getMediaInfo(): Map<String, String?> {
        if (mpvView == null) return emptyMap()
        return try {
            mapOf(
                "videoCodec" to safeGet("video-format"),
                "audioCodec" to safeGet("audio-codec-name"),
                "videoRes" to "${_videoWidth.value}x${_videoHeight.value}",
                "fps" to safeGet("container-fps"),
                "displayFps" to safeGetDouble("display-fps"),
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

    private fun safeGet(name: String): String? {
        if (name in unavailableProperties) return null
        return try { MPVLib.getPropertyString(name) } catch (_: Throwable) { unavailableProperties.add(name); null }
    }

    private fun safeGetDouble(name: String): String? {
        if (name in unavailableProperties) return null
        return try {
            val v = MPVLib.getPropertyDouble(name)
            if (v != null && v > 0) String.format("%.1f", v) else null
        } catch (_: Throwable) { unavailableProperties.add(name); null }
    }

    // -----------------------------------------------------------------
    // HDR 重建协调
    // -----------------------------------------------------------------
    override fun savePlaybackState(): Pair<String, Double>? {
        return try {
            val url = MPVLib.getPropertyString("path") ?: return null
            if (url.isEmpty()) return null
            val time = MPVLib.getPropertyDouble("time-pos") ?: 0.0
            url to time
        } catch (e: Throwable) {
            Log.w(TAG, "savePlaybackState failed (MPVLib not initialized?): ${e.message}")
            null
        }
    }

    override fun restorePlaybackState(url: String, timePosSec: Double) {
        postOnUiThread {
            val v = mpvView
            if (v != null) {
                if (timePosSec > 0) {
                    v.pendingResumePos = timePosSec
                }
                v.playFile(url)
            } else {
                MPVLib.command(arrayOf("loadfile", url))
                if (timePosSec > 0) {
                    MPVLib.command(arrayOf("seek", timePosSec.toString(), "absolute", "exact"))
                }
                MPVLib.setPropertyBoolean("pause", false)
            }
        }
    }

    // -----------------------------------------------------------------
    // EventObserver 实现
    // -----------------------------------------------------------------
    override fun eventProperty(property: String) {}

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
            "sub-visibility" -> { }
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
            "path" -> { _eofReached.value = false }
        }
    }

    override fun event(eventId: Int) {
        when (eventId) {
            MPVLib.MpvEvent.MPV_EVENT_FILE_LOADED -> {
                _fileLoaded.value = true
                val loadedUrl = try { MPVLib.getPropertyString("path") ?: "" } catch (_: Throwable) { "" }
                playbackController.onFileLoaded(loadedUrl)
                _eofReached.value = false

                try {
                    val w = MPVLib.getPropertyInt("width") ?: 0
                    val h = MPVLib.getPropertyInt("height") ?: 0
                    if (w >= 3840 || h >= 2160) {
                        MPVLib.setPropertyString("demuxer-max-bytes", MpvProtocolConstants.DEMUXER_MAX_BYTES_4K)
                        MPVLib.setPropertyString("demuxer-max-back-bytes", "32MiB")
                        Log.i(TAG, "4K buffer adjusted: ${MpvProtocolConstants.DEMUXER_MAX_BYTES_4K}/32MiB (${w}x${h})")
                    } else {
                        MPVLib.setPropertyString("demuxer-max-bytes", MpvProtocolConstants.DEMUXER_MAX_BYTES_DEFAULT)
                        MPVLib.setPropertyString("demuxer-max-back-bytes", "12MiB")
                    }
                } catch (e: Throwable) {
                    Log.w(TAG, "buffer adjust failed: ${e.message}")
                }

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
            }
            MPVLib.MpvEvent.MPV_EVENT_START_FILE -> {
                _fileLoaded.value = false
                _eofReached.value = false
                playbackController.onStartFile()
                unavailableProperties.clear()
                cancelPendingFileError()
                Log.i(TAG, "MPV_EVENT_START_FILE: loadingUrl=${playbackController.loadingUrl}")
            }
            MPVLib.MpvEvent.MPV_EVENT_END_FILE -> {
                val wasLoaded = _fileLoaded.value
                _fileLoaded.value = false
                _videoWidth.value = 0
                _videoHeight.value = 0
                val endedUrl = try { MPVLib.getPropertyString("path") ?: "" } catch (_: Throwable) { "" }
                val replacedByNew = playbackController.loadingUrl.isNotEmpty() && endedUrl != playbackController.loadingUrl
                val wasPlaying = wasLoaded || endedUrl == playbackController.lastLoadedUrl

                cancelPendingFileError()

                if (suppressFileErrorFlag) {
                    Log.i(TAG, "MPV_EVENT_END_FILE: suppressed (surface rebuilding), wasLoaded=$wasLoaded")
                } else if (playbackController.switchingChannel) {
                    Log.i(TAG, "MPV_EVENT_END_FILE: suppressed (channel switching), wasLoaded=$wasLoaded")
                } else if (!wasPlaying && !replacedByNew) {
                    Log.w(TAG, "MPV_EVENT_END_FILE: file '$endedUrl' failed to load, notifying error")
                    postOnUiThread { onFileError?.invoke() }
                } else if (wasPlaying && !_eofReached.value) {
                    Log.i(TAG, "MPV_EVENT_END_FILE: stream '$endedUrl' ended mid-stream (wasLoaded=$wasLoaded), delayed error check 300ms")
                    val runnable = Runnable {
                        Log.w(TAG, "MPV_EVENT_END_FILE: stream ended mid-stream, no START_FILE followed, notifying error")
                        postOnUiThread { onFileError?.invoke() }
                    }
                    playbackController.pendingEndFileError = runnable
                    mpvView?.asView()?.postDelayed(runnable, 300)
                } else {
                    Log.i(TAG, "MPV_EVENT_END_FILE: stream '$endedUrl' ended normally (wasLoaded=$wasLoaded, eof=${_eofReached.value})")
                }
                playbackController.onEndFile()
            }
            MPVLib.MpvEvent.MPV_EVENT_SHUTDOWN -> {
                Log.w(TAG, "MPV_EVENT_SHUTDOWN: mpv core has shut down, marking instance as dead")
                _fileLoaded.value = false
                _eofReached.value = true
                mpvView?.markInstanceDead()
            }
        }
    }

    companion object {
        private const val TAG = "MpvController"

        @Volatile
        private var INSTANCE: MpvController? = null

        fun getInstance(): MpvController =
            INSTANCE ?: synchronized(this) {
                INSTANCE ?: MpvController().also { INSTANCE = it }
            }

        val CHANNEL_LAYOUT_MAP get() = MpvAudioEqController.CHANNEL_LAYOUT_MAP
        val CHANNEL_DISPLAY get() = MpvAudioEqController.CHANNEL_DISPLAY
    }
}
