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
    private var mpvView: MPVView? = null

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

    private val _speed = MutableStateFlow(1.0)
    override val speed: StateFlow<Double> = _speed.asStateFlow()

    // -----------------------------------------------------------------
    // 生命周期
    // -----------------------------------------------------------------
    /**
     * 绑定 MPVView 实例，注册 EventObserver，补充观察 MPVView 未观察的属性。
     * 必须在 MPVView.initialize() 之后调用。
     */
    fun attach(view: MPVView) {
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

        // 播放器设置持久化：如果该设备已确认需要 vo fallback（黑屏检测曾触发过），
        // 直接设置标志跳过本次黑屏探测。此时 MPVView 已用持久化的 mediacodec_embed 初始化，
        // 无需再等待 2 秒黑屏。
        // 用户可通过 resetPlayerSettings() 重置，重新走黑屏检测流程。
        if (UserPrefs.getInstance().isVoFallbackConfirmed()) {
            voFallbackTriggered = true
            Log.i(TAG, "vo fallback already confirmed, skip black screen detection")
        }

        Log.i(TAG, "MpvController attached to MPVView")
    }

    /** Player 接口实现：转发到 attach(MPVView) */
    override fun attachView(view: Any) {
        if (view is MPVView) {
            attach(view)
        } else {
            Log.w(TAG, "attachView: view is not MPVView (${view.javaClass.name}), ignored")
        }
    }

    /**
     * 解绑 MPVView，移除 EventObserver。
     * 在 Activity.onDestroy 时调用。
     */
    override fun detach() {
        MPVLib.removeObserver(this)
        this.mpvView = null
        // 重置状态（避免 Compose 用旧值）
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
     * 注意：vo 是 mpv 初始化参数，运行时切换可能不立即生效。
     * - setPropertyString("vo", ...) 会让 mpv 重新加载 vo 模块
     * - 更新 MPVView.voInUse，确保 surface 重建时用新 vo
     * - 重新加载当前文件触发新 vo 渲染
     * - 如果切换不生效，用户需重启 APP（MPVView.initialize 用新 vo 创建）
     *
     * @param vo "gpu" 或 "mediacodec_embed"
     * @param hwdec "auto-copy" / "mediacodec" / "no"
     * @return 当前文件路径（用于 UI 提示），null 表示无文件在播放
     */
    fun setVoAndHwdec(vo: String, hwdec: String): String? {
        postOnUiThread {
            try {
                MPVLib.setPropertyString("vo", vo)
                MPVLib.setPropertyString("hwdec", hwdec)
                mpvView?.setVoInUse(vo)
                // 重新加载当前文件以触发新 vo 渲染
                val path = MPVLib.getPropertyString("path")
                if (path != null && path.isNotEmpty()) {
                    MPVLib.command(arrayOf("loadfile", path))
                    MPVLib.setPropertyBoolean("pause", false)
                }
                // 重置 voFallbackTriggered：
                // - 切换到 gpu：重新启用黑屏检测（用户主动想测试 gpu）
                // - 切换到 mediacodec_embed：标记已 fallback（不需要再检测）
                voFallbackTriggered = (vo != "gpu")
                Log.i(TAG, "setVoAndHwdec: vo=$vo, hwdec=$hwdec, voFallbackTriggered=$voFallbackTriggered")
            } catch (e: Throwable) {
                Log.e(TAG, "setVoAndHwdec failed", e)
            }
        }
        return try { MPVLib.getPropertyString("path") } catch (e: Throwable) { null }
    }

    /**
     * 切换硬件/软件解码（实现 Player.setHardwareDecode）。
     *
     * - vo=gpu：硬解 hwdec=auto-copy，软解 hwdec=no
     * - vo=mediacodec_embed：固定硬解（mediacodec），不支持软解，返回 false
     *
     * 切换后自动重新加载当前文件以应用新 hwdec。
     */
    override fun setHardwareDecode(enabled: Boolean): Boolean {
        val currentVo = try {
            MPVLib.getPropertyString("vo") ?: "gpu"
        } catch (e: Throwable) { "gpu" }

        // vo=mediacodec_embed 固定硬解，不支持软解
        if (!enabled && currentVo == "mediacodec_embed") {
            Log.w(TAG, "setHardwareDecode: vo=mediacodec_embed 不支持软解")
            return false
        }

        val hwdec = when {
            !enabled -> "no"
            currentVo == "mediacodec_embed" -> "mediacodec"
            else -> "auto-copy"
        }
        setVoAndHwdec(currentVo, hwdec)
        Log.i(TAG, "setHardwareDecode: enabled=$enabled, vo=$currentVo, hwdec=$hwdec")
        return true
    }

    /** 查询当前是否使用硬件解码 */
    override fun isHardwareDecodeEnabled(): Boolean {
        return try {
            val hwdec = MPVLib.getPropertyString("hwdec") ?: "auto-copy"
            hwdec != "no"
        } catch (e: Throwable) { true }
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
        val visible = view.getGlobalVisibleRect(rect)
        return if (visible) rect else null
    }

    private fun gcd(a: Int, b: Int): Int = if (b == 0) a else gcd(b, a % b)

    // -----------------------------------------------------------------
    // 基础播放控制
    // -----------------------------------------------------------------
    override fun playFile(url: String) = postOnUiThread { mpvView?.playFile(url) }
    override fun stop() = postOnUiThread { mpvView?.stop() }
    override fun togglePause() = postOnUiThread { MPVLib.command(arrayOf("cycle", "pause")) }
    override fun setPause(p: Boolean) = postOnUiThread { MPVLib.setPropertyBoolean("pause", p) }

    override fun seekTo(seconds: Double) =
        postOnUiThread { MPVLib.setPropertyDouble("time-pos", seconds) }

    override fun seekRelative(seconds: Double) =
        postOnUiThread { MPVLib.command(arrayOf("seek", seconds.toString(), "relative")) }

    override fun seekAbsolute(seconds: Double) =
        postOnUiThread { MPVLib.command(arrayOf("seek", seconds.toString(), "absolute")) }

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

    override fun adjustSubDelay(delta: Double) {
        val cur = MPVLib.getPropertyDouble("sub-delay") ?: 0.0
        setSubDelay(cur + delta)
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
     * 注意：hwdec 必须为 auto-copy（默认）才能用 vf 滤镜。
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
     * hwdec 必须为 auto-copy（默认）才能用 vf 滤镜。
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
        val cur = MPVLib.getPropertyDouble("audio-delay") ?: 0.0
        setAudioDelay(cur + delta)
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
     * pitch: 0.0~2.0，1.0=正常。实际设置 mpv 的 audio-pitch-correction 属性。
     */
    override fun setAudioPitch(pitch: Double): Boolean {
        postOnUiThread { MPVLib.setPropertyDouble("audio-pitch-correction", pitch.coerceIn(0.0, 2.0)) }
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

    /** 同步读取属性（在调用线程执行，注意 mpv 线程安全）。libmpv 未初始化时返回 null，避免 native 崩溃。 */
    override fun getPropertyString(name: String): String? =
        if (mpvView != null) MPVLib.getPropertyString(name) else null

    override fun getPropertyInt(name: String): Int? =
        if (mpvView != null) MPVLib.getPropertyInt(name) else null

    override fun getPropertyDouble(name: String): Double? =
        if (mpvView != null) MPVLib.getPropertyDouble(name) else null

    override fun getPropertyBoolean(name: String): Boolean? =
        if (mpvView != null) MPVLib.getPropertyBoolean(name) else null

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
                "fps" to safeGet("estimated-vfps"),
                "displayFps" to safeGet("display-fps"),
                "bitrate" to safeGet("video-bitrate"),
                "audioBitrate" to safeGet("audio-bitrate"),
                "cacheDuration" to safeGet("cache-duration"),
                "avdiff" to safeGet("total-avsync-change"),
                "containerFormat" to safeGet("file-format"),
                "hwdec" to safeGet("hwdec-current"),
                "vo" to safeGet("vo")
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
        val url = MPVLib.getPropertyString("path") ?: return null
        if (url.isEmpty()) return null
        val time = MPVLib.getPropertyDouble("time-pos") ?: 0.0
        return url to time
    }

    /**
     * 重建后恢复播放状态。loadfile + seek absolute 恢复进度。
     * 注意：seek 在 file-loaded 事件后才会生效，调用方应在收到 fileLoaded 后再 seek。
     */
    override fun restorePlaybackState(url: String, timePosSec: Double) {
        postOnUiThread {
            MPVLib.command(arrayOf("loadfile", url))
            if (timePosSec > 0) {
                // 用 absolute+exact 模式精确 seek
                MPVLib.command(arrayOf("seek", timePosSec.toString(), "absolute", "exact"))
            }
            MPVLib.setPropertyBoolean("pause", false)
        }
    }

    // -----------------------------------------------------------------
    // 内部：把命令 post 到 MPVView 线程（mpv 要求同线程访问）
    // -----------------------------------------------------------------
    private fun postOnUiThread(block: () -> Unit) {
        val v = mpvView
        if (v != null) {
            v.post { block() }
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
                // 黑屏检测：文件加载后 6 秒检查 videoWidth 和 estimated-vfps，若渲染没工作则 fallback。
                // 根因：mpv 0.41.0 + Mali-G76 等部分 GPU 存在 EGL 渲染兼容性问题，
                // vo=gpu 会导致黑屏（有声音无画面）。用 mediacodec_embed 绕过 EGL 直接渲染到 Surface。
                scheduleBlackScreenCheck()
            }
            MPVLib.MpvEvent.MPV_EVENT_START_FILE -> {
                _fileLoaded.value = false
                _eofReached.value = false
            }
            MPVLib.MpvEvent.MPV_EVENT_END_FILE -> {
                // 文件结束（eof 或切换）：UI 自行根据 eof-reached 判断
            }
            MPVLib.MpvEvent.MPV_EVENT_SHUTDOWN -> {
                _fileLoaded.value = false
                _eofReached.value = true
            }
        }
    }

    /** 黑屏检测重试计数（避免直播流缓冲期间 estimated-vfps 暂时为 0 导致误判） */
    private var blackScreenRetryCount = 0

    /**
     * 黑屏检测 Runnable：检查 videoWidth 和 estimated-vfps，若渲染没工作则触发 vo fallback。
     *
     * 防误判机制：
     * - 直播流（HLS/RTMP）刚加载时 estimated-vfps 可能暂时为 0（缓冲未完成）
     * - 首次检测到"黑屏"后 3 秒复查，连续两次确认才 fallback
     * - 实际首次检测在文件加载后 6 秒（scheduleBlackScreenCheck），复查在 9 秒
     *
     * 为什么用 estimated-vfps 而非仅 videoWidth？
     * - vo=gpu 在部分 GPU（如 Mali-G76）存在 EGL 兼容性问题，导致渲染内容不到 Surface（黑屏有声音）
     * - 此时解码器正常工作，width/height 都有值，但渲染器没实际输出帧
     * - estimated-vfps（mpv 基于实际渲染帧计算的显示帧率）在渲染没工作时为 0
     * - 综合 width==0 || estimated-vfps<=0 判断黑屏更可靠
     */
    private val blackScreenCheckRunnable: Runnable = Runnable {
        if (voFallbackTriggered) return@Runnable
        if (!_fileLoaded.value) return@Runnable

        // 当前 vo：如果已经是 mediacodec_embed（用户手动切换或持久化的 fallback），不需要 fallback
        val currentVo = try {
            MPVLib.getPropertyString("vo") ?: ""
        } catch (e: Throwable) {
            Log.w(TAG, "getPropertyString(vo) failed", e)
            ""
        }
        if (currentVo == "mediacodec_embed" || currentVo.isEmpty()) return@Runnable

        // 黑屏判断：综合 videoWidth 和 estimated-vfps
        // - videoWidth==0：解码器没工作（极端情况）
        // - estimated-vfps<=0：渲染器没工作（EGL 兼容性问题，如 Mali-G76 vo=gpu 黑屏）
        //   注意：width 即使黑屏也有值（解码器已解码，只是 EGL 渲染不到 Surface）
        val videoWidth = _videoWidth.value
        val estimatedVfps = try {
            MPVLib.getPropertyString("estimated-vfps")?.toDoubleOrNull() ?: 0.0
        } catch (e: Throwable) {
            Log.w(TAG, "getPropertyString(estimated-vfps) failed", e)
            0.0
        }
        Log.d(
            TAG,
            "blackScreenCheck: vo=$currentVo, videoWidth=$videoWidth, estimatedVfps=$estimatedVfps, attempt=${blackScreenRetryCount + 1}"
        )

        if (videoWidth == 0 || estimatedVfps <= 0.0) {
            blackScreenRetryCount++
            if (blackScreenRetryCount < 2) {
                // 首次检测到"黑屏"：可能是直播流还在缓冲，3 秒后复查
                Log.w(
                    TAG,
                    "Possible black screen (attempt $blackScreenRetryCount, videoWidth=$videoWidth, estimatedVfps=$estimatedVfps), retrying in 3s..."
                )
                mpvView?.postDelayed(blackScreenCheckRunnable, 3000)
                return@Runnable
            }
            // 连续两次检测到黑屏，确认并非缓冲问题
            Log.w(
                TAG,
                "Black screen confirmed after 2 attempts (videoWidth=$videoWidth, estimatedVfps=$estimatedVfps), fallback to mediacodec_embed"
            )
            voFallbackTriggered = true
            try {
                MPVLib.setPropertyString("vo", "mediacodec_embed")
                MPVLib.setPropertyString("hwdec", "mediacodec")
                // 重新加载当前文件以触发 mediacodec 渲染
                val path = MPVLib.getPropertyString("path")
                if (path != null && path.isNotEmpty()) {
                    MPVLib.command(arrayOf("loadfile", path))
                    MPVLib.setPropertyBoolean("pause", false)
                }
                // 持久化 fallback 结果：下次启动直接用 mediacodec_embed，跳过黑屏探测
                val userPrefs = UserPrefs.getInstance()
                userPrefs.setVo("mediacodec_embed")
                userPrefs.setHwdec("mediacodec")
                userPrefs.setVoFallbackConfirmed(true)
                Log.i(TAG, "Switched to vo=mediacodec_embed, hwdec=mediacodec (persisted for next launch)")
            } catch (e: Throwable) {
                Log.e(TAG, "Fallback to mediacodec_embed failed", e)
            }
        }
    }

    /**
     * 安排黑屏检测（在文件加载后 6 秒执行，给直播流足够缓冲时间，避免 estimated-vfps 误判）。
     */
    private fun scheduleBlackScreenCheck() {
        val view = mpvView ?: return
        view.removeCallbacks(blackScreenCheckRunnable)
        blackScreenRetryCount = 0
        view.postDelayed(blackScreenCheckRunnable, 6000)
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
