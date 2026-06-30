package com.iptv.scanner.editor.pro.mpv

import android.util.Log
import `is`.xyz.mpv.MPVLib
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
class MpvController : MPVLib.EventObserver {

    @Volatile
    private var mpvView: MPVView? = null

    // -----------------------------------------------------------------
    // StateFlow（Compose 可观察状态）
    // -----------------------------------------------------------------
    private val _timePos = MutableStateFlow(0.0)
    val timePos: StateFlow<Double> = _timePos.asStateFlow()

    private val _duration = MutableStateFlow(0.0)
    val duration: StateFlow<Double> = _duration.asStateFlow()

    private val _paused = MutableStateFlow(true)
    val paused: StateFlow<Boolean> = _paused.asStateFlow()

    private val _volume = MutableStateFlow(100)
    val volume: StateFlow<Int> = _volume.asStateFlow()

    private val _muted = MutableStateFlow(false)
    val muted: StateFlow<Boolean> = _muted.asStateFlow()

    private val _mediaTitle = MutableStateFlow("")
    val mediaTitle: StateFlow<String> = _mediaTitle.asStateFlow()

    private val _trackListJson = MutableStateFlow("")
    val trackListJson: StateFlow<String> = _trackListJson.asStateFlow()

    private val _eofReached = MutableStateFlow(false)
    val eofReached: StateFlow<Boolean> = _eofReached.asStateFlow()

    private val _fileLoaded = MutableStateFlow(false)
    val fileLoaded: StateFlow<Boolean> = _fileLoaded.asStateFlow()

    private val _currentChapter = MutableStateFlow(-1)
    val currentChapter: StateFlow<Int> = _currentChapter.asStateFlow()

    private val _chapterCount = MutableStateFlow(0)
    val chapterCount: StateFlow<Int> = _chapterCount.asStateFlow()

    private val _videoWidth = MutableStateFlow(0)
    val videoWidth: StateFlow<Int> = _videoWidth.asStateFlow()

    private val _videoHeight = MutableStateFlow(0)
    val videoHeight: StateFlow<Int> = _videoHeight.asStateFlow()

    private val _speed = MutableStateFlow(1.0)
    val speed: StateFlow<Double> = _speed.asStateFlow()

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
        Log.i(TAG, "MpvController attached to MPVView")
    }

    /**
     * 解绑 MPVView，移除 EventObserver。
     * 在 Activity.onDestroy 时调用。
     */
    fun detach() {
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

    // -----------------------------------------------------------------
    // 基础播放控制
    // -----------------------------------------------------------------
    fun playFile(url: String) = postOnUiThread { mpvView?.playFile(url) }
    fun stop() = postOnUiThread { mpvView?.stop() }
    fun togglePause() = postOnUiThread { MPVLib.command(arrayOf("cycle", "pause")) }
    fun setPause(p: Boolean) = postOnUiThread { MPVLib.setPropertyBoolean("pause", p) }

    fun seekTo(seconds: Double) =
        postOnUiThread { MPVLib.setPropertyDouble("time-pos", seconds) }

    fun seekRelative(seconds: Double) =
        postOnUiThread { MPVLib.command(arrayOf("seek", seconds.toString(), "relative")) }

    fun seekAbsolute(seconds: Double) =
        postOnUiThread { MPVLib.command(arrayOf("seek", seconds.toString(), "absolute")) }

    // -----------------------------------------------------------------
    // 音量 / 静音 / 速度
    // -----------------------------------------------------------------
    fun setVolume(v: Int) =
        postOnUiThread { MPVLib.setPropertyInt("volume", v.coerceIn(0, 130)) }

    fun adjustVolume(delta: Int) {
        val cur = _volume.value
        setVolume(cur + delta)
    }

    fun toggleMute() = postOnUiThread { MPVLib.command(arrayOf("cycle", "mute")) }
    fun setMute(m: Boolean) = postOnUiThread { MPVLib.setPropertyBoolean("mute", m) }

    fun setSpeed(s: Double) =
        postOnUiThread { MPVLib.setPropertyDouble("speed", s.coerceIn(0.01, 100.0)) }

    // -----------------------------------------------------------------
    // 音轨 / 字幕轨
    // -----------------------------------------------------------------
    fun cycleAudio() = postOnUiThread { MPVLib.command(arrayOf("cycle", "audio")) }
    fun cycleSub() = postOnUiThread { MPVLib.command(arrayOf("cycle", "sub")) }

    /**
     * 设置音轨。id 对应 track-list 中 type=audio 项的 id。
     * 与 PC 端 set_track 一致：先 setPropertyInt，失败回退 command。
     */
    fun setAudioTrack(id: Int) = postOnUiThread {
        try {
            MPVLib.setPropertyInt("aid", id)
        } catch (e: Exception) {
            MPVLib.command(arrayOf("set", "aid", id.toString()))
        }
    }

    fun setSubTrack(id: Int) = postOnUiThread {
        try {
            MPVLib.setPropertyInt("sid", id)
        } catch (e: Exception) {
            MPVLib.command(arrayOf("set", "sid", id.toString()))
        }
    }

    /** 加载外挂字幕文件（select 表示立即选中） */
    fun addSubtitleFile(path: String) =
        postOnUiThread { MPVLib.command(arrayOf("sub-add", path, "select")) }

    // -----------------------------------------------------------------
    // 字幕显示与样式
    // -----------------------------------------------------------------
    fun setSubVisibility(v: Boolean) =
        postOnUiThread { MPVLib.setPropertyBoolean("sub-visibility", v) }

    fun toggleSubVisibility() =
        postOnUiThread { MPVLib.command(arrayOf("cycle", "sub-visibility")) }

    fun setSubDelay(delaySec: Double) =
        postOnUiThread { MPVLib.setPropertyDouble("sub-delay", delaySec) }

    fun adjustSubDelay(delta: Double) {
        val cur = MPVLib.getPropertyDouble("sub-delay") ?: 0.0
        setSubDelay(cur + delta)
    }

    fun setSubScale(scale: Double) =
        postOnUiThread { MPVLib.setPropertyDouble("sub-scale", scale.coerceIn(0.1, 10.0)) }

    fun setSubPos(pos: Int) =
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
    fun setChapter(idx: Int) = postOnUiThread {
        try {
            MPVLib.setPropertyInt("chapter", idx)
        } catch (e: Exception) {
            MPVLib.command(arrayOf("set", "chapter", idx.toString()))
        }
    }

    fun chapterNext() = postOnUiThread { MPVLib.command(arrayOf("add", "chapter", "1")) }
    fun chapterPrev() = postOnUiThread { MPVLib.command(arrayOf("add", "chapter", "-1")) }

    // -----------------------------------------------------------------
    // 画面调整（video EQ + 翻转 / 旋转 / 裁剪）
    // -----------------------------------------------------------------
    fun setBrightness(v: Int) = postOnUiThread { MPVLib.setPropertyInt("brightness", v.coerceIn(-100, 100)) }
    fun setContrast(v: Int) = postOnUiThread { MPVLib.setPropertyInt("contrast", v.coerceIn(-100, 100)) }
    fun setSaturation(v: Int) = postOnUiThread { MPVLib.setPropertyInt("saturation", v.coerceIn(-100, 100)) }
    fun setHue(v: Int) = postOnUiThread { MPVLib.setPropertyInt("hue", v.coerceIn(-100, 100)) }
    fun setGamma(v: Int) = postOnUiThread { MPVLib.setPropertyInt("gamma", v.coerceIn(-100, 100)) }

    fun setVideoRotate(degree: Int) =
        postOnUiThread { MPVLib.setPropertyInt("video-rotate", degree) }

    /**
     * 设置视频翻转。mode: "" / "horizontal" / "vertical" / "both"
     * 与 PC 端 set_video_flip 一致：先 remove 旧 @iptv_flip，再 add 新的。
     * 注意：hwdec 必须为 auto-copy（默认）才能用 vf 滤镜。
     */
    fun setVideoFlip(mode: String) = postOnUiThread {
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

    /**
     * 设置视频裁剪（黑边裁剪）。w/h=0 表示清除。
     */
    fun setVideoCrop(x: Int, y: Int, w: Int, h: Int) = postOnUiThread {
        MPVLib.command(arrayOf("vf", "remove", "@iptv_crop"))
        if (w > 0 && h > 0) {
            MPVLib.command(arrayOf("vf", "add", "@iptv_crop:crop=$w:$h:$x:$y"))
        }
    }

    fun clearVideoCrop() = postOnUiThread { MPVLib.command(arrayOf("vf", "remove", "@iptv_crop")) }
    fun clearAllVideoFilters() = postOnUiThread {
        MPVLib.command(arrayOf("vf", "remove", "@iptv_flip"))
        MPVLib.command(arrayOf("vf", "remove", "@iptv_crop"))
    }

    // -----------------------------------------------------------------
    // 音频调整
    // -----------------------------------------------------------------
    fun setAudioDelay(delaySec: Double) =
        postOnUiThread { MPVLib.setPropertyDouble("audio-delay", delaySec.coerceIn(-10.0, 10.0)) }

    fun adjustAudioDelay(delta: Double) {
        val cur = MPVLib.getPropertyDouble("audio-delay") ?: 0.0
        setAudioDelay(cur + delta)
    }

    /**
     * 设置 10 段均衡器。gains 长度必须为 10，每段 -12 ~ +12 dB。
     * 与 PC 端 set_audio_eq 一致：先 remove @iptv_eq，全 0 不添加，否则 add equalizer=g1:g2:...:g10。
     */
    fun setAudioEq(gains: List<Float>) = postOnUiThread {
        MPVLib.command(arrayOf("af", "remove", "@iptv_eq"))
        if (gains.size != 10 || gains.all { it == 0f }) return@postOnUiThread
        val eqStr = gains.joinToString(":") { "%.1f".format(it) }
        MPVLib.command(arrayOf("af", "add", "@iptv_eq:equalizer=$eqStr"))
    }

    fun resetAudioEq() = postOnUiThread { MPVLib.command(arrayOf("af", "remove", "@iptv_eq")) }

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
    fun screenshotToFile(path: String, mode: String = "video") =
        postOnUiThread { MPVLib.command(arrayOf("screenshot-to-file", path, mode)) }

    // -----------------------------------------------------------------
    // A/B 循环 + 单文件/列表循环 + 逐帧
    // -----------------------------------------------------------------
    fun setAbLoopA() = postOnUiThread {
        val t = MPVLib.getPropertyDouble("time-pos") ?: 0.0
        MPVLib.setPropertyDouble("ab-loop-a", t)
    }

    fun setAbLoopB() = postOnUiThread {
        val t = MPVLib.getPropertyDouble("time-pos") ?: 0.0
        MPVLib.setPropertyDouble("ab-loop-b", t)
    }

    fun clearAbLoop() = postOnUiThread {
        MPVLib.setPropertyString("ab-loop-a", "no")
        MPVLib.setPropertyString("ab-loop-b", "no")
    }

    /** mode: "no" / "inf" / "yes" / "once" */
    fun setLoopFile(mode: String) =
        postOnUiThread { MPVLib.setPropertyString("loop-file", mode) }

    /** mode: "no" / "inf" / "force" */
    fun setLoopPlaylist(mode: String) =
        postOnUiThread { MPVLib.setPropertyString("loop-playlist", mode) }

    fun frameStep() = postOnUiThread { MPVLib.command(arrayOf("frame-step")) }
    fun frameBackStep() = postOnUiThread { MPVLib.command(arrayOf("frame-back-step")) }

    // -----------------------------------------------------------------
    // OSD
    // -----------------------------------------------------------------
    fun showOsd(text: String, durationMs: Int = 3000) =
        postOnUiThread { MPVLib.command(arrayOf("show-text", text, durationMs.toString())) }

    // -----------------------------------------------------------------
    // 通用 API（覆盖所有未封装的 mpv 属性/命令）
    // -----------------------------------------------------------------
    fun setPropertyString(name: String, value: String) =
        postOnUiThread { MPVLib.setPropertyString(name, value) }

    fun setPropertyInt(name: String, value: Int) =
        postOnUiThread { MPVLib.setPropertyInt(name, value) }

    fun setPropertyDouble(name: String, value: Double) =
        postOnUiThread { MPVLib.setPropertyDouble(name, value) }

    fun setPropertyBoolean(name: String, value: Boolean) =
        postOnUiThread { MPVLib.setPropertyBoolean(name, value) }

    /** 同步读取属性（在调用线程执行，注意 mpv 线程安全）。libmpv 未初始化时返回 null，避免 native 崩溃。 */
    fun getPropertyString(name: String): String? =
        if (mpvView != null) MPVLib.getPropertyString(name) else null
    fun getPropertyInt(name: String): Int? =
        if (mpvView != null) MPVLib.getPropertyInt(name) else null
    fun getPropertyDouble(name: String): Double? =
        if (mpvView != null) MPVLib.getPropertyDouble(name) else null
    fun getPropertyBoolean(name: String): Boolean? =
        if (mpvView != null) MPVLib.getPropertyBoolean(name) else null

    fun command(args: Array<String>) = postOnUiThread { MPVLib.command(args) }

    // -----------------------------------------------------------------
    // HDR 重建协调（保存/恢复进度）
    // -----------------------------------------------------------------
    /**
     * 保存当前播放状态（用于 HDR 模式 / hwdec 模式切换前的重建）。
     * 返回 Pair<url, timePosSec>，重建后用 restorePlaybackState 恢复。
     * 返回 null 表示当前无文件播放。
     */
    fun savePlaybackState(): Pair<String, Double>? {
        val url = MPVLib.getPropertyString("path") ?: return null
        if (url.isEmpty()) return null
        val time = MPVLib.getPropertyDouble("time-pos") ?: 0.0
        return url to time
    }

    /**
     * 重建后恢复播放状态。loadfile + seek absolute 恢复进度。
     * 注意：seek 在 file-loaded 事件后才会生效，调用方应在收到 fileLoaded 后再 seek。
     */
    fun restorePlaybackState(url: String, timePosSec: Double) = postOnUiThread {
        MPVLib.command(arrayOf("loadfile", url))
        if (timePosSec > 0) {
            // 用 absolute+exact 模式精确 seek
            MPVLib.command(arrayOf("seek", timePosSec.toString(), "absolute", "exact"))
        }
        MPVLib.setPropertyBoolean("pause", false)
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
