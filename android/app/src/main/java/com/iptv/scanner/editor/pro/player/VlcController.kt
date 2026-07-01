package com.iptv.scanner.editor.pro.player

import android.content.Context
import android.net.Uri
import android.os.Handler
import android.os.Looper
import android.util.Log
import java.io.File
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import org.json.JSONArray
import org.json.JSONObject
import org.videolan.libvlc.LibVLC
import org.videolan.libvlc.Media
import org.videolan.libvlc.MediaPlayer
import org.videolan.libvlc.interfaces.IMedia

/**
 * VLC 播放器控制器：封装 org.videolan.libvlc 的 LibVLC + MediaPlayer，
 * 实现 [Player] 接口，统一到与 MpvController 对齐的 StateFlow + 方法 API。
 *
 * 设计要点：
 * 1. LibVLC 实例在构造函数中创建（带全局选项：RTSP-TCP/网络缓存/硬解码等）
 * 2. MediaPlayer 实例在构造函数中创建，注册 [MediaPlayer.EventListener] 回调
 * 3. 所有 14 个状态用 MutableStateFlow 管理，通过 asStateFlow() 暴露只读引用
 * 4. VLC 事件回调（Playing/Paused/EndReached/TimeChanged 等）驱动 StateFlow 更新
 * 5. VLC 的 TimeChanged 事件可能不频繁，用 Handler 每 500ms 轮询 currentPosition 补充
 * 6. VLC 音量 0-100（100=正常），Player 接口用 0-130（100=正常），直接透传（VLC 支持 >100）
 * 7. VLC 时间用毫秒，接口用秒，转换：sec = ms / 1000.0
 * 8. VLC 字幕延迟用微秒（libvlc_video_set_spu_delay），转换：us = sec * 1_000_000
 * 9. trackListJson 构建为与 mpv track-list 兼容的 JSON 数组格式
 *
 * 与 MpvController 的差异：
 * - VLC 不支持画面 EQ / 音频 EQ / AB循环 / 逐帧 / 章节 / 截图 / OSD（capabilities 全 false）
 * - VLC 支持：速度控制 / 轨道列表 / 外挂字幕 / 字幕延迟
 * - VLC 的 getPropertyX/command 返回 null/no-op（mpv 专属功能）
 */
class VlcController(context: Context) : Player, MediaPlayer.EventListener {

    companion object {
        private const val TAG = "VlcController"

        /** 位置轮询间隔（毫秒），VLC 的 TimeChanged 事件可能不频繁 */
        private const val POSITION_POLL_INTERVAL_MS = 500L
    }

    // -----------------------------------------------------------------
    // VLC 核心实例
    // -----------------------------------------------------------------

    /**
     * LibVLC 实例（全局选项：RTSP-TCP / 网络缓存 / 硬解码 / 全屏）。
     * 在构造函数中创建，在 [detach] 中释放。
     */
    private val libVLC: LibVLC = LibVLC(
        context,
        arrayListOf(
            "--rtsp-tcp",               // RTSP 强制 TCP（避免 UDP 丢包）
            "--network-caching=1000",   // 网络缓存 1 秒（平衡延迟与卡顿）
            "--live-caching=1000",      // 直播缓存 1 秒
            "--codec=mediacodec_ndk",   // 硬件解码（MediaCodec NDK 接口）
            "--fullscreen",             // 全屏渲染
            "--no-drop-late-frames",    // 不丢弃迟到帧（减少画面跳跃）
            "--no-skip-frames"          // 不跳帧（保证画面连续性）
        )
    )

    /**
     * VLC MediaPlayer 实例。
     * 对外可见，供 [VlcVideoView] 访问 vlcVout 进行 Surface 绑定。
     */
    val mediaPlayer: MediaPlayer = MediaPlayer(libVLC).apply {
        setEventListener(this@VlcController)
    }

    // -----------------------------------------------------------------
    // StateFlow（14 个，与 MpvController / Player 接口对齐）
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

    private val _videoWidth = MutableStateFlow(0)
    override val videoWidth: StateFlow<Int> = _videoWidth.asStateFlow()

    private val _videoHeight = MutableStateFlow(0)
    override val videoHeight: StateFlow<Int> = _videoHeight.asStateFlow()

    private val _speed = MutableStateFlow(1.0)
    override val speed: StateFlow<Double> = _speed.asStateFlow()

    private val _currentChapter = MutableStateFlow(-1)
    override val currentChapter: StateFlow<Int> = _currentChapter.asStateFlow()

    private val _chapterCount = MutableStateFlow(0)
    override val chapterCount: StateFlow<Int> = _chapterCount.asStateFlow()

    // -----------------------------------------------------------------
    // 能力声明
    // -----------------------------------------------------------------

    /**
     * VLC 能力声明：
     * - 支持速度控制（mediaPlayer.rate 可运行时调整）
     * - 支持轨道列表（getAudioTracks/getSpuTracks）
     * - 支持外挂字幕（:sub-file 媒体选项）
     * - 支持字幕延迟（spuDelay 微秒级调整）
     * - 不支持画面 EQ / 音频 EQ / AB循环 / 逐帧 / 章节 / 截图 / OSD
     */
    override val capabilities: PlayerCapabilities = PlayerCapabilities(
        supportsSpeedControl = true,
        supportsTrackList = true,
        supportsAddSubtitleFile = true,
        supportsSubDelay = true,
        supportsAudioDelay = false,
        supportsSubScale = false,
        supportsSubPos = false,
        supportsHardwareDecodeSwitch = true
    )

    override val playerType: PlayerType = PlayerType.VLC

    // -----------------------------------------------------------------
    // 内部状态
    // -----------------------------------------------------------------

    /** 当前播放的 URL（用于 savePlaybackState） */
    private var currentUrl: String? = null

    /** 待执行的 seek（restorePlaybackState 后等 Playing 事件再 seek） */
    private var pendingSeek: Double? = null

    /** 上次选中的字幕轨 ID（用于 setSubVisibility 切换显示/隐藏） */
    private var lastSpuTrack: Int = -1

    /** 字幕显示状态（VLC 无直接属性，需自行跟踪） */
    private var subVisible: Boolean = true

    /** 当前字幕延迟（秒），用于 adjustSubDelay 增量计算 */
    private var currentSubDelay: Double = 0.0

    /** 静音前的音量（用于取消静音时恢复） */
    private var preMuteVolume: Int = 100

    /** 已加载的外挂字幕路径列表（playFile 时作为 :sub-file 选项添加） */
    private val subtitlePaths = mutableListOf<String>()

    /** 当前是否使用硬件解码（运行时可切换，影响 media.setHWDecoderEnabled） */
    @Volatile
    private var hardwareDecode = true

    /** 主线程 Handler（用于位置轮询） */
    private val handler = Handler(Looper.getMainLooper())

    /** 位置轮询 Runnable：VLC 的 TimeChanged 事件可能不频繁，定时补充更新 */
    private val positionPollRunnable = object : Runnable {
        override fun run() {
            if (!_paused.value && _fileLoaded.value && !_eofReached.value) {
                try {
                    val timeMs = mediaPlayer.time
                    if (timeMs >= 0) {
                        _timePos.value = timeMs / 1000.0
                    }
                } catch (e: Exception) {
                    // MediaPlayer 可能未就绪，忽略
                }
                handler.postDelayed(this, POSITION_POLL_INTERVAL_MS)
            }
        }
    }

    // -----------------------------------------------------------------
    // 生命周期
    // -----------------------------------------------------------------

    /**
     * 绑定 [VlcVideoView]，委托给 view.attachController(this) 注册 Surface 回调。
     * 如果 view 不是 VlcVideoView，打印警告并忽略。
     */
    override fun attachView(view: Any) {
        if (view is VlcVideoView) {
            view.attachController(this)
            Log.i(TAG, "VlcController attached to VlcVideoView")
        } else {
            Log.w(TAG, "attachView: view is not VlcVideoView (${view::class.simpleName})")
        }
    }

    /**
     * 释放资源：停止轮询、移除事件监听、停止播放、释放 MediaPlayer 和 LibVLC。
     * VlcVideoView 的 surfaceDestroyed 应在此之前调用（detachViews）。
     */
    override fun detach() {
        stopPolling()
        try {
            mediaPlayer.setEventListener(null)
            mediaPlayer.stop()
            // vlcVout 应由 VlcVideoView.surfaceDestroyed 调用 detachViews，
            // 但以防万一，检查并补调
            if (mediaPlayer.vlcVout.areViewsAttached()) {
                mediaPlayer.vlcVout.detachViews()
            }
            mediaPlayer.release()
            libVLC.release()
        } catch (e: Exception) {
            Log.e(TAG, "detach failed", e)
        }
        _fileLoaded.value = false
        _eofReached.value = false
        _paused.value = true
        _timePos.value = 0.0
        _duration.value = 0.0
        Log.i(TAG, "VlcController detached")
    }

    // -----------------------------------------------------------------
    // 基础播放控制
    // -----------------------------------------------------------------

    /**
     * 播放文件或 URL。
     *
     * VLC 流程：
     * 1. 从 URL 创建 [Media] 对象
     * 2. 启用硬件解码（setHWDecoderEnabled）
     * 3. 添加外挂字幕（:sub-file 选项，需在播放前添加）
     * 4. 设置为 MediaPlayer 的 media，play()
     * 5. 速度在 Playing 事件中通过 mediaPlayer.rate 设置（media 的 :rate 只支持整数）
     */
    override fun playFile(url: String) {
        currentUrl = url
        _eofReached.value = false
        _fileLoaded.value = false
        _timePos.value = 0.0
        _duration.value = 0.0

        try {
            val uri = if (url.startsWith("/")) {
                Uri.fromFile(File(url))
            } else {
                Uri.parse(url)
            }
            val media = Media(libVLC, uri)
            // 启用/禁用硬件解码（与 LibVLC 的 --codec=mediacodec_ndk 一致，软解时禁用）
            media.setHWDecoderEnabled(hardwareDecode, false)
            media.addOption(":fullscreen")

            // 添加已注册的外挂字幕文件
            for (subPath in subtitlePaths) {
                media.addOption(":sub-file=$subPath")
            }

            mediaPlayer.media = media
            media.release() // MediaPlayer 持有引用，释放本地包装
            mediaPlayer.play()

            _mediaTitle.value = extractTitle(url)
        } catch (e: Exception) {
            Log.e(TAG, "playFile failed: $url", e)
        }
    }

    override fun stop() {
        try {
            mediaPlayer.stop()
        } catch (e: Exception) {
            Log.w(TAG, "stop failed: ${e.message}")
        }
        stopPolling()
        _fileLoaded.value = false
        _eofReached.value = false
        _timePos.value = 0.0
    }

    /**
     * 切换暂停/播放。
     * VLC 的 pause() 是 toggle 语义，play() 始终恢复播放。
     */
    override fun togglePause() {
        try {
            if (_paused.value) {
                mediaPlayer.play()
            } else {
                mediaPlayer.pause()
            }
        } catch (e: Exception) {
            Log.w(TAG, "togglePause failed: ${e.message}")
        }
    }

    override fun setPause(p: Boolean) {
        if (p == _paused.value) return
        togglePause()
    }

    /**
     * 跳转到指定位置（秒）。
     * VLC 用毫秒：mediaPlayer.time = (seconds * 1000).toLong()
     */
    override fun seekTo(seconds: Double) {
        try {
            mediaPlayer.time = (seconds * 1000).toLong()
            _timePos.value = seconds
        } catch (e: Exception) {
            Log.w(TAG, "seekTo($seconds) failed: ${e.message}")
        }
    }

    override fun seekRelative(seconds: Double) {
        val target = (_timePos.value + seconds).coerceAtLeast(0.0)
        val dur = _duration.value
        if (dur > 0) {
            seekTo(target.coerceAtMost(dur))
        } else {
            seekTo(target)
        }
    }

    override fun seekAbsolute(seconds: Double) {
        seekTo(seconds)
    }

    // -----------------------------------------------------------------
    // 音量 / 静音 / 速度
    // -----------------------------------------------------------------

    /**
     * 设置音量（0-130，Player 接口标准）。
     *
     * VLC 音量范围 0-200（100=正常，>100 为增益），Player 接口 0-130（100=正常）。
     * 直接透传：100=正常保持一致，130=30% 增益（VLC 支持）。
     */
    override fun setVolume(v: Int) {
        val clamped = v.coerceIn(0, 130)
        try {
            // VLC 接受 0-200，接口最大 130 在 VLC 支持范围内
            mediaPlayer.volume = clamped
        } catch (e: Exception) {
            Log.w(TAG, "setVolume($clamped) failed: ${e.message}")
        }
        _volume.value = clamped
        if (clamped > 0) {
            _muted.value = false
        }
    }

    override fun adjustVolume(delta: Int) {
        setVolume(_volume.value + delta)
    }

    /**
     * 切换静音。
     * VLC Android 3.6.x 无直接 setMute 方法，用音量 0/恢复实现。
     */
    override fun toggleMute() {
        setMute(!_muted.value)
    }

    override fun setMute(m: Boolean) {
        if (m) {
            if (!_muted.value) {
                preMuteVolume = _volume.value
            }
            try {
                mediaPlayer.volume = 0
            } catch (e: Exception) {
                Log.w(TAG, "setMute(true) failed: ${e.message}")
            }
            _muted.value = true
        } else {
            try {
                mediaPlayer.volume = preMuteVolume
            } catch (e: Exception) {
                Log.w(TAG, "setMute(false) failed: ${e.message}")
            }
            _muted.value = false
        }
    }

    /**
     * 设置播放速度。
     * VLC 的 mediaPlayer.rate 接受 Float，可运行时调整（无需重载 media）。
     */
    override fun setSpeed(s: Double) {
        _speed.value = s
        try {
            mediaPlayer.rate = s.toFloat()
        } catch (e: Exception) {
            Log.w(TAG, "setSpeed($s) failed: ${e.message}")
        }
    }

    // -----------------------------------------------------------------
    // 音轨 / 字幕轨
    // -----------------------------------------------------------------

    /**
     * 循环切换音轨。
     * 遍历 getAudioTracks()，在当前轨道后选择下一个。
     */
    override fun cycleAudio() {
        try {
            val tracks = mediaPlayer.audioTracks ?: return
            if (tracks.isEmpty()) return
            val currentId = mediaPlayer.audioTrack
            val currentIndex = tracks.indexOfFirst { it.id == currentId }
            val nextIndex = if (currentIndex < 0) 0 else (currentIndex + 1) % tracks.size
            mediaPlayer.audioTrack = tracks[nextIndex].id
            updateTrackList()
        } catch (e: Exception) {
            Log.w(TAG, "cycleAudio failed: ${e.message}")
        }
    }

    /**
     * 循环切换字幕轨。
     * 遍历 getSpuTracks()，在当前轨道后选择下一个（包含 -1=禁用）。
     */
    override fun cycleSub() {
        try {
            val tracks = mediaPlayer.spuTracks ?: return
            if (tracks.isEmpty()) return
            val currentId = mediaPlayer.spuTrack
            // 构建包含"禁用"选项的列表：[-1, track1.id, track2.id, ...]
            val allIds = mutableListOf<Int>().apply {
                add(-1)
                tracks.forEach { add(it.id) }
            }
            val currentIndex = allIds.indexOf(currentId)
            val nextIndex = if (currentIndex < 0) 1 else (currentIndex + 1) % allIds.size
            val nextId = allIds[nextIndex]
            mediaPlayer.spuTrack = nextId
            if (nextId > 0) lastSpuTrack = nextId
            updateTrackList()
        } catch (e: Exception) {
            Log.w(TAG, "cycleSub failed: ${e.message}")
        }
    }

    override fun setAudioTrack(id: Int) {
        try {
            mediaPlayer.audioTrack = id
            updateTrackList()
        } catch (e: Exception) {
            Log.w(TAG, "setAudioTrack($id) failed: ${e.message}")
        }
    }

    override fun setSubTrack(id: Int) {
        try {
            mediaPlayer.spuTrack = id
            if (id > 0) {
                lastSpuTrack = id
                subVisible = true
            }
            updateTrackList()
        } catch (e: Exception) {
            Log.w(TAG, "setSubTrack($id) failed: ${e.message}")
        }
    }

    /**
     * 加载外挂字幕文件。
     *
     * VLC 的 :sub-file 选项必须在 media 播放前添加。
     * 如果当前有文件在播放，需要重载 media 才能生效（保存/恢复播放位置）。
     */
    override fun addSubtitleFile(path: String) {
        subtitlePaths.add(path)
        // 如果已有文件在播放，重载以加载新字幕
        val url = currentUrl
        if (url != null && _fileLoaded.value) {
            val savedTime = _timePos.value
            playFile(url)
            if (savedTime > 0) {
                pendingSeek = savedTime
            }
        }
    }

    // -----------------------------------------------------------------
    // 字幕显示与样式
    // -----------------------------------------------------------------

    /**
     * 设置字幕显示开关。
     * VLC 无直接属性，通过切换 spuTrack 实现：
     * - 显示：恢复 lastSpuTrack
     * - 隐藏：设置 spuTrack = -1（禁用）
     */
    override fun setSubVisibility(v: Boolean) {
        subVisible = v
        try {
            if (v) {
                if (lastSpuTrack > 0) {
                    mediaPlayer.spuTrack = lastSpuTrack
                }
            } else {
                val cur = mediaPlayer.spuTrack
                if (cur > 0) lastSpuTrack = cur
                mediaPlayer.spuTrack = -1
            }
            updateTrackList()
        } catch (e: Exception) {
            Log.w(TAG, "setSubVisibility($v) failed: ${e.message}")
        }
    }

    override fun toggleSubVisibility() {
        setSubVisibility(!subVisible)
    }

    /**
     * 设置字幕延迟（秒）。
     * VLC 的 spuDelay 使用微秒（libvlc_video_set_spu_delay）。
     * 转换：us = sec * 1_000_000
     */
    override fun setSubDelay(delaySec: Double) {
        currentSubDelay = delaySec
        try {
            mediaPlayer.spuDelay = (delaySec * 1_000_000).toLong()
        } catch (e: Exception) {
            Log.w(TAG, "setSubDelay($delaySec) failed: ${e.message}")
        }
    }

    override fun adjustSubDelay(delta: Double) {
        setSubDelay(currentSubDelay + delta)
    }

    /** VLC 不支持字幕缩放（no-op） */
    override fun setSubScale(scale: Double) {
        Log.d(TAG, "setSubScale not supported by VLC")
    }

    /** VLC 不支持字幕位置（no-op） */
    override fun setSubPos(pos: Int) {
        Log.d(TAG, "setSubPos not supported by VLC")
    }

    // -----------------------------------------------------------------
    // 媒体信息
    // -----------------------------------------------------------------

    /**
     * 获取媒体信息（codec/分辨率/帧率/码率等）。
     * 从 [IMedia.getTrack] 获取轨道信息，返回统一 Map 供 UI 读取。
     */
    override fun getMediaInfo(): Map<String, String?> {
        val info = mutableMapOf<String, String?>()
        try {
            val media = mediaPlayer.media ?: return info
            val count = media.trackCount
            for (i in 0 until count) {
                val track = media.getTrack(i) ?: continue
                when (track.type) {
                    IMedia.Track.Type.Video -> {
                        val vTrack = track as? IMedia.VideoTrack ?: continue
                        info["video-codec"] = track.codec?.takeIf { it.isNotEmpty() }
                        info["video-width"] = vTrack.width.toString()
                        info["video-height"] = vTrack.height.toString()
                        // VLC VideoTrack 用 frameRateNum/frameRateDen 表示帧率
                        if (vTrack.frameRateDen > 0) {
                            val fps = vTrack.frameRateNum.toFloat() / vTrack.frameRateDen
                            if (fps > 0) info["video-fps"] = "%.2f".format(fps)
                        }
                        if (track.bitrate > 0) {
                            info["video-bitrate"] = "${track.bitrate / 1000} kbps"
                        }
                    }
                    IMedia.Track.Type.Audio -> {
                        val aTrack = track as? IMedia.AudioTrack ?: continue
                        info["audio-codec"] = track.codec?.takeIf { it.isNotEmpty() }
                        if (aTrack.channels > 0) {
                            info["audio-channels"] = aTrack.channels.toString()
                        }
                        // VLC AudioTrack 用 rate 表示采样率（不是 sampleRate）
                        if (aTrack.rate > 0) {
                            info["audio-samplerate"] = "${aTrack.rate} Hz"
                        }
                        if (track.bitrate > 0) {
                            info["audio-bitrate"] = "${track.bitrate / 1000} kbps"
                        }
                    }
                }
            }
        } catch (e: Exception) {
            Log.w(TAG, "getMediaInfo failed: ${e.message}")
        }
        return info
    }

    // -----------------------------------------------------------------
    // 硬件解码切换
    // -----------------------------------------------------------------

    /**
     * 切换硬件/软件解码。
     *
     * VLC 通过 [Media.setHWDecoderEnabled] 控制，是 Media 级别选项，
     * 切换后需重新播放当前 URL 才能生效。
     *
     * 注意：LibVLC 全局选项 `--codec=mediacodec_ndk` 仍在，但
     * `setHWDecoderEnabled(false)` 会覆盖该 Media 的硬解设置。
     */
    override fun setHardwareDecode(enabled: Boolean): Boolean {
        if (hardwareDecode == enabled) return true
        hardwareDecode = enabled
        Log.i(TAG, "setHardwareDecode: enabled=$enabled")
        // 重新播放当前 URL 以应用新设置
        val url = currentUrl
        if (url != null && url.isNotEmpty()) {
            val pos = _timePos.value
            playFile(url)
            // 恢复播放进度（异步，等 Playing 事件后 seek）
            if (pos > 0) {
                pendingSeek = pos
            }
        }
        return true
    }

    override fun isHardwareDecodeEnabled(): Boolean = hardwareDecode

    // -----------------------------------------------------------------
    // 播放状态保存/恢复
    // -----------------------------------------------------------------

    /**
     * 保存当前播放状态（url + timePos），用于切换播放器时保持连续性。
     * 返回 null 表示当前无文件播放。
     */
    override fun savePlaybackState(): Pair<String, Double>? {
        val url = currentUrl ?: return null
        if (url.isEmpty()) return null
        return url to _timePos.value
    }

    /**
     * 恢复播放状态：加载 url 并在 Playing 事件后 seek 到 timePosSec。
     */
    override fun restorePlaybackState(url: String, timePosSec: Double) {
        playFile(url)
        if (timePosSec > 0) {
            pendingSeek = timePosSec
        }
    }

    // -----------------------------------------------------------------
    // MediaPlayer.EventListener 实现
    // -----------------------------------------------------------------

    /**
     * VLC 事件回调（在 VLC 内部线程调用，StateFlow.value 线程安全）。
     * 将 VLC 事件映射到 StateFlow 更新。
     */
    override fun onEvent(event: MediaPlayer.Event) {
        when (event.type) {
            MediaPlayer.Event.Playing -> {
                _paused.value = false
                _fileLoaded.value = true
                _eofReached.value = false
                startPolling()
                // 应用当前速度（mediaPlayer.rate 可运行时设置）
                if (_speed.value != 1.0) {
                    try { mediaPlayer.rate = _speed.value.toFloat() } catch (e: Exception) { }
                }
                // 处理待执行的 seek（restorePlaybackState）
                pendingSeek?.let { seek ->
                    pendingSeek = null
                    seekTo(seek)
                }
                updateTrackList()
                updateVideoSize()
            }

            MediaPlayer.Event.Paused -> {
                _paused.value = true
                stopPolling()
            }

            MediaPlayer.Event.Stopped -> {
                stopPolling()
            }

            MediaPlayer.Event.EndReached -> {
                _eofReached.value = true
                _paused.value = true
                stopPolling()
            }

            MediaPlayer.Event.TimeChanged -> {
                // VLC TimeChanged 可能不频繁，轮询补充
                try {
                    val timeMs = event.timeChanged
                    if (timeMs >= 0) {
                        _timePos.value = timeMs / 1000.0
                    }
                } catch (e: Exception) { }
            }

            MediaPlayer.Event.LengthChanged -> {
                try {
                    val lenMs = event.lengthChanged
                    _duration.value = if (lenMs > 0) lenMs / 1000.0 else 0.0
                } catch (e: Exception) { }
            }

            MediaPlayer.Event.Vout -> {
                // 视频输出层变化，更新视频尺寸和轨道信息
                updateVideoSize()
                updateTrackList()
            }

            MediaPlayer.Event.ESAdded,
            MediaPlayer.Event.ESDeleted,
            MediaPlayer.Event.ESSelected -> {
                // 基本流增删/选择，更新轨道列表
                updateTrackList()
            }

            MediaPlayer.Event.MediaChanged -> {
                _fileLoaded.value = false
                _eofReached.value = false
                _timePos.value = 0.0
                _duration.value = 0.0
            }

            MediaPlayer.Event.Opening -> {
                // 媒体正在打开，可更新标题
                try {
                    val media = mediaPlayer.media
                    val title = media?.getMeta(IMedia.Meta.Title)
                    _mediaTitle.value = if (!title.isNullOrEmpty()) title else extractTitle(currentUrl ?: "")
                } catch (e: Exception) { }
            }

            MediaPlayer.Event.EncounteredError -> {
                Log.e(TAG, "VLC encountered error")
            }

            MediaPlayer.Event.Buffering -> {
                // 缓冲中，暂不处理（UI 可通过 fileLoaded 判断就绪）
            }
        }
    }

    // -----------------------------------------------------------------
    // 内部方法
    // -----------------------------------------------------------------

    /** 启动位置轮询 */
    private fun startPolling() {
        handler.removeCallbacks(positionPollRunnable)
        handler.postDelayed(positionPollRunnable, POSITION_POLL_INTERVAL_MS)
    }

    /** 停止位置轮询 */
    private fun stopPolling() {
        handler.removeCallbacks(positionPollRunnable)
    }

    /**
     * 更新视频尺寸（从 IMedia.Track 获取 video 轨道的 width/height）。
     * 在 Vout 事件和 Playing 事件时调用。
     */
    private fun updateVideoSize() {
        try {
            val media = mediaPlayer.media ?: return
            val count = media.trackCount
            for (i in 0 until count) {
                val track = media.getTrack(i) ?: continue
                if (track.type == IMedia.Track.Type.Video) {
                    val vTrack = track as? IMedia.VideoTrack ?: continue
                    _videoWidth.value = vTrack.width
                    _videoHeight.value = vTrack.height
                    break
                }
            }
        } catch (e: Exception) {
            // 轨道信息可能尚未就绪
        }
    }

    /**
     * 构建与 mpv track-list 兼容的 JSON 数组。
     *
     * mpv 格式示例：
     * [{"id":1,"type":"audio","title":"#1: English","selected":true,"default":false},...]
     *
     * VLC 通过 getAudioTracks()/getSpuTracks() 获取 TrackDescription[]，
     * 加上 IMedia.Track 中的 video 轨道信息。
     */
    private fun updateTrackList() {
        val jsonArray = JSONArray()
        try {
            // 当前选中的轨道 ID
            val currentAudioId = try { mediaPlayer.audioTrack } catch (e: Exception) { -1 }
            val currentSpuId = try { mediaPlayer.spuTrack } catch (e: Exception) { -1 }

            // 视频轨道（VLC 通常只有一个激活视频轨）
            try {
                val media = mediaPlayer.media
                if (media != null) {
                    val count = media.trackCount
                    for (i in 0 until count) {
                        val track = media.getTrack(i) ?: continue
                        if (track.type == IMedia.Track.Type.Video) {
                            jsonArray.put(JSONObject().apply {
                                put("id", 1)
                                put("type", "video")
                                put("title", track.codec ?: "video")
                                put("selected", true)
                                put("default", true)
                                if (!track.language.isNullOrEmpty()) {
                                    put("lang", track.language)
                                }
                            })
                        }
                    }
                }
            } catch (e: Exception) { }

            // 音频轨道
            try {
                mediaPlayer.audioTracks?.forEach { td ->
                    jsonArray.put(JSONObject().apply {
                        put("id", td.id)
                        put("type", "audio")
                        put("title", td.name ?: "#${td.id}")
                        put("selected", td.id == currentAudioId)
                        put("default", false)
                    })
                }
            } catch (e: Exception) { }

            // 字幕轨道
            try {
                mediaPlayer.spuTracks?.forEach { td ->
                    jsonArray.put(JSONObject().apply {
                        put("id", td.id)
                        put("type", "sub")
                        put("title", td.name ?: "#${td.id}")
                        put("selected", td.id == currentSpuId)
                        put("default", false)
                    })
                }
            } catch (e: Exception) { }

            _trackListJson.value = jsonArray.toString()
        } catch (e: Exception) {
            Log.w(TAG, "updateTrackList failed: ${e.message}")
            _trackListJson.value = "[]"
        }
    }

    /**
     * 从 URL 提取媒体标题（用于显示）。
     * 优先取 URI 最后一段路径，失败回退到原始 URL。
     */
    private fun extractTitle(url: String): String {
        return try {
            val uri = Uri.parse(url)
            val segment = uri.lastPathSegment
            if (!segment.isNullOrEmpty()) segment else url
        } catch (e: Exception) {
            url
        }
    }
}
