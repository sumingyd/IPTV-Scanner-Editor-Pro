package com.iptv.scanner.editor.pro.player

import android.content.Context
import android.net.Uri
import android.os.Handler
import android.os.Looper
import android.util.Log
import android.view.SurfaceHolder
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import tv.danmaku.ijk.media.player.IMediaPlayer
import tv.danmaku.ijk.media.player.IjkMediaPlayer

/**
 * IJKPlayer 控制器：封装 tv.danmaku.ijk.media.player.IjkMediaPlayer，
 * 实现 [Player] 接口，与 MPV/ExoPlayer/VLC 实现统一 API。
 *
 * 设计要点：
 * 1. 持有一个持久 [ijkPlayer] 实例，[stop] 时 release + 重建，[playFile] 时 reset + 复用
 * 2. 用 [MutableStateFlow] 管理所有 14 个状态，与 MpvController 对齐
 * 3. 实现 IMediaPlayer 的 6 个回调（Prepared/Completion/Info/VideoSize/Error/SeekComplete）
 *    把 IJK 事件转发到 StateFlow，Compose 直接观察
 * 4. 用 [Handler] 轮询 currentPosition 更新 timePos（IJK 无属性观察机制）
 * 5. capabilities 仅声明 IJK 实际支持的功能（变速），
 *    其余高级功能（EQ/AB循环/逐帧/章节/截图/HDR/轨道列表 等）返回 false/no-op
 *
 * IJK 与 mpv 的差异：
 * - seekTo 用毫秒（mpv 用秒）
 * - setVolume 用 0.0~1.0 浮点（mpv 用 0~130 整数），内部做映射
 * - setSpeed 支持运行时变速（与 mpv 一致）
 * - 字幕：仅支持显示开关，不支持延迟/缩放/位置调整
 * - 外挂字幕：IJK 需在 setDataSource 之前设置，运行时不支持（capabilities 声明 false）
 * - 轨道切换：腾讯 IoT fork 不提供 TrackInfo/setAudioTrack/setSubtitleTrack，轨道切换不可用
 *
 * @see Player 接口定义
 * @see com.iptv.scanner.editor.pro.mpv.MpvController MPV 完整实现（参考模式）
 */
class IjkController(private val context: Context) : Player {

    // -----------------------------------------------------------------
    // IjkMediaPlayer 实例（持久，stop 时 release + 重建）
    // -----------------------------------------------------------------

    /**
     * IjkMediaPlayer 实例（可空）。
     *
     * 为可空的原因：腾讯 IoT 的 IJKPlayer fork 只提供 arm64 和 armv7a 两个 ABI 的 native 库，
     * 在 x86/x86_64 设备（主要是模拟器）上 IjkMediaPlayer 类初始化会因找不到 .so 而抛
     * UnsatisfiedLinkError / ExceptionInInitializerError。
     * 此时 [nativeAvailable] 为 false，[ijkPlayer] 为 null，所有方法安全降级。
     */
    @Volatile
    var ijkPlayer: IjkMediaPlayer? = null
        private set

    /**
     * native 库是否可用。
     *
     * false 的情况：x86/x86_64 设备上无 IJK native 库（.so 加载失败）。
     * 此时所有播放操作安全降级（返回 false / no-op / 空值），
     * UI 应提示用户切换到 MPV/ExoPlayer/VLC 播放器。
     */
    val nativeAvailable: Boolean

    /** 绑定的 IjkVideoView（由 attachView 设置） */
    @Volatile
    private var videoView: IjkVideoView? = null

    /** 当前 SurfaceHolder（由 IjkVideoView 回调同步） */
    @Volatile
    private var currentHolder: SurfaceHolder? = null

    /** 当前播放 URL（用于 savePlaybackState） */
    @Volatile
    private var currentUrl: String = ""

    /** 当前是否使用硬件解码（运行时可切换，影响 mediacodec option） */
    @Volatile
    private var hardwareDecode = true

    /** 挂起的 seek 位置（restorePlaybackState 设置，onPrepared 后执行） */
    @Volatile
    private var pendingSeek: Double? = null

    /** 字幕可见性（IJK 无查询 API，本地跟踪） */
    @Volatile
    private var subVisible = true

    /** 当前音轨 ID（1-based，用于 cycleAudio） */
    @Volatile
    private var currentAudioTrackId = 1

    /** 当前字幕轨 ID（1-based，用于 cycleSub） */
    @Volatile
    private var currentSubTrackId = 1

    /** 音轨总数（updateTrackInfo 时更新） */
    @Volatile
    private var audioTrackCount = 0

    /** 字幕轨总数 */
    @Volatile
    private var subTrackCount = 0

    /** 音轨 ID(1-based) → 轨道数组绝对索引 的映射（腾讯 IoT fork 无 TrackInfo，始终为空） */
    private val audioTrackIndices = mutableListOf<Int>()

    /** 字幕轨 ID(1-based) → 轨道数组绝对索引 的映射（腾讯 IoT fork 无 TrackInfo，始终为空） */
    private val subTrackIndices = mutableListOf<Int>()

    private val handler = Handler(Looper.getMainLooper())

    init {
        // 尝试创建 IjkMediaPlayer 实例。
        // 在 x86/x86_64 设备上，IjkMediaPlayer 类的 static 块加载 native 库时会抛
        // UnsatisfiedLinkError / ExceptionInInitializerError，此时 nativeAvailable=false。
        val (available, player) = tryCreatePlayer()
        nativeAvailable = available
        ijkPlayer = player
        if (!available) {
            Log.e(TAG, "IJK native library not available on this ABI (likely x86/x86_64). " +
                "IJK player will be disabled. Please use MPV/ExoPlayer/VLC instead.")
        }
    }

    /**
     * 尝试创建 IjkMediaPlayer 实例。
     * 返回 (nativeAvailable, player)：成功时 (true, 实例)，失败时 (false, null)。
     */
    private fun tryCreatePlayer(): Pair<Boolean, IjkMediaPlayer?> {
        return try {
            val p = IjkMediaPlayer()
            setListeners(p)
            true to p
        } catch (e: UnsatisfiedLinkError) {
            Log.e(TAG, "Failed to load IJK native library: ${e.message}")
            false to null
        } catch (e: ExceptionInInitializerError) {
            Log.e(TAG, "IJK class initialization failed: ${e.message}")
            false to null
        } catch (e: NoClassDefFoundError) {
            Log.e(TAG, "IJK class not found: ${e.message}")
            false to null
        }
    }

    // -----------------------------------------------------------------
    // 14 个 StateFlow（与 MpvController 对齐）
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

    override val capabilities: PlayerCapabilities = PlayerCapabilities(
        supportsSpeedControl = true,
        supportsTrackList = false,
        supportsAddSubtitleFile = false,
        supportsHardwareDecodeSwitch = true
    )

    override val playerType: PlayerType = PlayerType.IJK

    // -----------------------------------------------------------------
    // 实例创建与监听器
    // -----------------------------------------------------------------

    /** 创建新的 IjkMediaPlayer 实例并设置所有回调（native 不可用时返回 null） */
    private fun createPlayer(): IjkMediaPlayer? {
        return try {
            val p = IjkMediaPlayer()
            setListeners(p)
            p
        } catch (e: Throwable) {
            Log.e(TAG, "createPlayer failed: ${e.message}")
            null
        }
    }

    /** 注册 6 个回调监听器（SAM 转换） */
    private fun setListeners(p: IjkMediaPlayer) {
        p.setOnPreparedListener { mp -> onPrepared(mp) }
        p.setOnCompletionListener { mp -> onCompletion(mp) }
        // 腾讯 IoT fork 的 OnInfoListener 接口扩展了两个方法：
        // - onInfoSEI(mp, what, extra, sei): SEI 信息回调（直播场景的 SEI 数据）
        // - onInfoAudioPcmData(mp, data, size): 音频 PCM 数据回调
        // 必须实现这两个方法，否则编译报错 "does not implement abstract member"
        p.setOnInfoListener(object : IMediaPlayer.OnInfoListener {
            override fun onInfo(mp: IMediaPlayer?, what: Int, extra: Int): Boolean {
                onInfo(mp, what, extra)
                return true
            }
            override fun onInfoSEI(mp: IMediaPlayer?, what: Int, extra: Int, sei: String?): Boolean {
                // SEI 信息回调，暂不处理
                return false
            }
            override fun onInfoAudioPcmData(mp: IMediaPlayer?, data: ByteArray?, size: Int) {
                // 音频 PCM 数据回调，暂不处理
            }
        })
        p.setOnVideoSizeChangedListener { mp, width, height, _, _ ->
            onVideoSizeChanged(mp, width, height)
        }
        p.setOnErrorListener { mp, what, extra ->
            onError(mp, what, extra)
            true
        }
        p.setOnSeekCompleteListener { mp -> onSeekComplete(mp) }
    }

    /** 应用默认解码/网络选项（每次 playFile 时在 reset 后调用） */
    private fun applyDefaultOptions(p: IjkMediaPlayer?) {
        if (p == null) return
        // OPT_CATEGORY_PLAYER：硬件解码 + RTSP over TCP
        // mediacodec：1=硬解，0=软解（根据 hardwareDecode 状态切换）
        p.setOption(IjkMediaPlayer.OPT_CATEGORY_PLAYER, "mediacodec", if (hardwareDecode) 1L else 0L)
        if (hardwareDecode) {
            p.setOption(IjkMediaPlayer.OPT_CATEGORY_PLAYER, "mediacodec-auto-rotate", 1L)
        }
        p.setOption(IjkMediaPlayer.OPT_CATEGORY_PLAYER, "rtsp-tcp", 1L)
        // OPT_CATEGORY_FORMAT：缓冲与封包
        p.setOption(IjkMediaPlayer.OPT_CATEGORY_FORMAT, "buffer_size", 1521024L)
        p.setOption(IjkMediaPlayer.OPT_CATEGORY_FORMAT, "infbuf", 1L)
        p.setOption(IjkMediaPlayer.OPT_CATEGORY_FORMAT, "packet-buffering", 0L)
        // OPT_CATEGORY_CODEC：解码循环过滤（8 = skip all，提升性能）
        p.setOption(IjkMediaPlayer.OPT_CATEGORY_CODEC, "skip_loop_filter", 8L)
    }

    // -----------------------------------------------------------------
    // IMediaPlayer 回调处理
    // -----------------------------------------------------------------

    private fun onPrepared(mp: IMediaPlayer) {
        Log.i(TAG, "onPrepared")
        _fileLoaded.value = true
        _eofReached.value = false
        _paused.value = false
        // 获取时长（IJK 在 prepared 后才能取到）
        try {
            val durMs = mp.duration
            if (durMs > 0) _duration.value = durMs / 1000.0
        } catch (e: Exception) {
            Log.w(TAG, "onPrepared getDuration failed: ${e.message}")
        }
        // 解析轨道信息（音轨/字幕轨）
        updateTrackInfo()
        // 执行挂起的 seek（restorePlaybackState 设置的恢复位置）
        pendingSeek?.let { seek ->
            pendingSeek = null
            try {
                mp.seekTo((seek * 1000).toLong())
            } catch (e: Exception) {
                Log.w(TAG, "onPrepared pending seek failed: ${e.message}")
            }
        }
        // prepareAsync 只准备不播放，需显式 start
        try {
            mp.start()
        } catch (e: Exception) {
            Log.w(TAG, "onPrepared start failed: ${e.message}")
        }
        // 恢复音量/速度到之前的设置（reset 会清除）
        applyVolume()
        if (_speed.value != 1.0) {
            try {
                (mp as? IjkMediaPlayer)?.setSpeed(_speed.value.toFloat())
            } catch (e: Exception) { }
        }
        startPolling()
    }

    private fun onCompletion(mp: IMediaPlayer) {
        Log.i(TAG, "onCompletion")
        _eofReached.value = true
        _paused.value = true
        stopPolling()
    }

    private fun onInfo(mp: IMediaPlayer?, what: Int, extra: Int) {
        when (what) {
            IMediaPlayer.MEDIA_INFO_BUFFERING_START ->
                Log.d(TAG, "info: buffering start")
            IMediaPlayer.MEDIA_INFO_BUFFERING_END ->
                Log.d(TAG, "info: buffering end")
            IMediaPlayer.MEDIA_INFO_METADATA_UPDATE -> {
                // 元数据更新时刷新轨道列表
                updateTrackInfo()
            }
            else -> Log.d(TAG, "info: what=$what extra=$extra")
        }
    }

    private fun onVideoSizeChanged(mp: IMediaPlayer, width: Int, height: Int) {
        if (width > 0 && height > 0) {
            _videoWidth.value = width
            _videoHeight.value = height
        }
    }

    private fun onError(mp: IMediaPlayer, what: Int, extra: Int) {
        Log.e(TAG, "onError: what=$what extra=$extra")
        _fileLoaded.value = false
    }

    private fun onSeekComplete(mp: IMediaPlayer) {
        try {
            _timePos.value = mp.currentPosition / 1000.0
        } catch (e: Exception) {
            Log.w(TAG, "onSeekComplete currentPosition failed: ${e.message}")
        }
    }

    // -----------------------------------------------------------------
    // 位置轮询（Handler.postDelayed，间隔 500ms）
    // -----------------------------------------------------------------

    private val positionPollRunnable = object : Runnable {
        override fun run() {
            try {
                val p = ijkPlayer
                if (p != null && !_paused.value && _fileLoaded.value) {
                    val posMs = p.currentPosition
                    if (posMs >= 0) _timePos.value = posMs / 1000.0
                }
            } catch (e: Exception) {
                Log.w(TAG, "poll currentPosition failed: ${e.message}")
            }
            handler.postDelayed(this, POLL_INTERVAL_MS)
        }
    }

    private fun startPolling() {
        handler.removeCallbacks(positionPollRunnable)
        handler.postDelayed(positionPollRunnable, POLL_INTERVAL_MS)
    }

    private fun stopPolling() {
        handler.removeCallbacks(positionPollRunnable)
    }

    // -----------------------------------------------------------------
    // 生命周期
    // -----------------------------------------------------------------

    override fun attachView(view: Any) {
        if (view is IjkVideoView) {
            videoView = view
            view.attachController(this)
            Log.i(TAG, "attachView: IjkVideoView attached")
        } else {
            Log.w(TAG, "attachView: unsupported view type ${view.javaClass.name}")
        }
    }

    override fun detach() {
        stopPolling()
        // 先解绑 View 和 Holder，避免 surfaceDestroyed 回调调用已释放的 ijkPlayer
        videoView = null
        currentHolder = null
        try {
            ijkPlayer?.release()
        } catch (e: Exception) {
            Log.w(TAG, "detach release failed: ${e.message}")
        }
        // 置 null，避免后续 attachSurface 调用已释放的 native 实例导致闪退。
        // 场景：switchPlayer 中 detach() 先于 key(playerType) 触发的 View 销毁执行，
        // 旧 IjkVideoView 销毁时 surfaceDestroyed → attachSurface(null) → ijkPlayer?.setDisplay(null)
        // 若 ijkPlayer 仍指向已 release 的实例，native 调用会闪退。
        ijkPlayer = null
        currentUrl = ""
        // 重置状态（避免 Compose 用旧值）
        _fileLoaded.value = false
        _eofReached.value = false
        _timePos.value = 0.0
        _duration.value = 0.0
        _paused.value = true
        _trackListJson.value = ""
        _mediaTitle.value = ""
        _videoWidth.value = 0
        _videoHeight.value = 0
        Log.i(TAG, "IjkController detached")
    }

    /**
     * Surface 回调（由 IjkVideoView 调用）：
     * 更新 currentHolder 并绑定到 ijkPlayer.setDisplay。
     */
    fun attachSurface(holder: SurfaceHolder?) {
        currentHolder = holder
        try {
            ijkPlayer?.setDisplay(holder)
        } catch (e: Exception) {
            Log.w(TAG, "attachSurface setDisplay failed: ${e.message}")
        }
    }

    // -----------------------------------------------------------------
    // 基础播放控制
    // -----------------------------------------------------------------

    override fun playFile(url: String) {
        Log.i(TAG, "playFile: $url")
        if (!nativeAvailable) {
            Log.e(TAG, "playFile: IJK native library not available on this device")
            return
        }
        currentUrl = url
        _eofReached.value = false
        _fileLoaded.value = false
        _timePos.value = 0.0
        _duration.value = 0.0
        _trackListJson.value = ""
        _videoWidth.value = 0
        _videoHeight.value = 0
        audioTrackIndices.clear()
        subTrackIndices.clear()
        audioTrackCount = 0
        subTrackCount = 0

        // reset 可能因实例已 release 而抛异常，此时重建实例
        try {
            ijkPlayer?.reset()
        } catch (e: Exception) {
            Log.w(TAG, "playFile: reset failed, recreating player: ${e.message}")
            ijkPlayer = createPlayer()
        }

        val p = ijkPlayer
        if (p == null) {
            Log.e(TAG, "playFile: IjkMediaPlayer instance is null")
            return
        }

        applyDefaultOptions(p)

        // 设置数据源（content:// URI 需用 Context+Uri 重载）
        try {
            if (url.startsWith("content://")) {
                p.setDataSource(context, Uri.parse(url))
            } else {
                p.setDataSource(url)
            }
        } catch (e: Exception) {
            Log.e(TAG, "playFile: setDataSource failed", e)
            return
        }

        // 绑定 Surface（如果已就绪）
        currentHolder?.let { holder ->
            try {
                p.setDisplay(holder)
            } catch (e: Exception) {
                Log.w(TAG, "playFile: setDisplay failed: ${e.message}")
            }
        }

        // 媒体标题（从 URL 提取文件名，去 query 参数）
        val title = url.substringAfterLast('/').substringBefore('?')
        _mediaTitle.value = title.ifEmpty { url }

        try {
            p.prepareAsync()
        } catch (e: Exception) {
            Log.e(TAG, "playFile: prepareAsync failed", e)
        }
    }

    override fun stop() {
        Log.i(TAG, "stop")
        stopPolling()
        _fileLoaded.value = false
        _eofReached.value = false
        _timePos.value = 0.0
        _duration.value = 0.0
        _trackListJson.value = ""
        audioTrackIndices.clear()
        subTrackIndices.clear()
        audioTrackCount = 0
        subTrackCount = 0
        try {
            ijkPlayer?.stop()
        } catch (e: Exception) {
            Log.w(TAG, "stop: stop failed: ${e.message}")
        }
        try {
            ijkPlayer?.release()
        } catch (e: Exception) {
            Log.w(TAG, "stop: release failed: ${e.message}")
        }
        // 重新创建实例供下次播放使用（native 不可用时为 null）
        ijkPlayer = createPlayer()
    }

    override fun togglePause() {
        setPause(!_paused.value)
    }

    override fun setPause(p: Boolean) {
        _paused.value = p
        try {
            if (p) ijkPlayer?.pause() else ijkPlayer?.start()
        } catch (e: Exception) {
            Log.w(TAG, "setPause($p) failed: ${e.message}")
        }
    }

    override fun seekTo(seconds: Double) {
        try {
            ijkPlayer?.seekTo((seconds * 1000).toLong())
            _timePos.value = seconds
        } catch (e: Exception) {
            Log.w(TAG, "seekTo($seconds) failed: ${e.message}")
        }
    }

    override fun seekRelative(seconds: Double) {
        seekTo(_timePos.value + seconds)
    }

    override fun seekAbsolute(seconds: Double) {
        seekTo(seconds)
    }

    // -----------------------------------------------------------------
    // 音量 / 静音 / 速度
    // -----------------------------------------------------------------

    override fun setVolume(v: Int) {
        _volume.value = v.coerceIn(0, 130)
        applyVolume()
    }

    override fun adjustVolume(delta: Int) {
        setVolume(_volume.value + delta)
    }

    override fun toggleMute() {
        setMute(!_muted.value)
    }

    override fun setMute(m: Boolean) {
        _muted.value = m
        applyVolume()
    }

    /**
     * 把当前音量/静音状态应用到 IjkMediaPlayer。
     * IJK setVolume 接受 0.0~1.0 浮点，mpv 用 0~130 整数，映射：ijkVol = mpvVol / 130。
     */
    private fun applyVolume() {
        val vol = if (_muted.value) 0f else _volume.value / 130f
        try {
            ijkPlayer?.setVolume(vol, vol)
        } catch (e: Exception) {
            Log.w(TAG, "applyVolume failed: ${e.message}")
        }
    }

    override fun setSpeed(s: Double) {
        val sp = s.coerceIn(0.25, 4.0)
        _speed.value = sp
        try {
            ijkPlayer?.setSpeed(sp.toFloat())
        } catch (e: Exception) {
            Log.w(TAG, "setSpeed($sp) failed: ${e.message}")
        }
    }

    // -----------------------------------------------------------------
    // 音轨 / 字幕轨
    // -----------------------------------------------------------------

    override fun cycleAudio() {
        if (audioTrackCount <= 0) return
        currentAudioTrackId = if (currentAudioTrackId >= audioTrackCount) 1 else currentAudioTrackId + 1
        setAudioTrack(currentAudioTrackId)
    }

    override fun cycleSub() {
        if (subTrackCount <= 0) return
        currentSubTrackId = if (currentSubTrackId >= subTrackCount) 1 else currentSubTrackId + 1
        setSubTrack(currentSubTrackId)
    }

    /**
     * 设置音轨。
     * 腾讯 IoT IJKPlayer fork 不提供 setAudioTrack 方法，此方法为 no-op。
     */
    override fun setAudioTrack(id: Int) {
        Log.w(TAG, "setAudioTrack: not supported by this IJK fork")
    }

    /**
     * 设置字幕轨。
     * 腾讯 IoT IJKPlayer fork 不提供 setSubtitleTrack 方法，此方法为 no-op。
     */
    override fun setSubTrack(id: Int) {
        Log.w(TAG, "setSubTrack: not supported by this IJK fork")
    }

    /**
     * 加载外挂字幕文件。
     * IJK 需要在 setDataSource 之前设置字幕路径，运行时不支持（声明 capabilities=false）。
     */
    override fun addSubtitleFile(path: String) {
        Log.w(TAG, "addSubtitleFile not supported by IJK (requires setting before setDataSource)")
    }

    // -----------------------------------------------------------------
    // 字幕显示与样式
    // -----------------------------------------------------------------

    override fun setSubVisibility(v: Boolean) {
        subVisible = v
        try {
            ijkPlayer?.setOption(
                IjkMediaPlayer.OPT_CATEGORY_PLAYER,
                "subtitle",
                if (v) 1L else 0L
            )
        } catch (e: Exception) {
            Log.w(TAG, "setSubVisibility($v) failed: ${e.message}")
        }
    }

    override fun toggleSubVisibility() {
        setSubVisibility(!subVisible)
    }

    /** IJK 不支持运行时字幕延迟 */
    override fun setSubDelay(delaySec: Double) {
        Log.d(TAG, "setSubDelay: not supported by IJK")
    }

    override fun adjustSubDelay(delta: Double) {
        Log.d(TAG, "adjustSubDelay: not supported by IJK")
    }

    /** IJK 不支持字幕缩放 */
    override fun setSubScale(scale: Double) {
        Log.d(TAG, "setSubScale: not supported by IJK")
    }

    /** IJK 不支持字幕位置调整 */
    override fun setSubPos(pos: Int) {
        Log.d(TAG, "setSubPos: not supported by IJK")
    }

    // -----------------------------------------------------------------
    // 轨道列表与媒体信息
    // -----------------------------------------------------------------

    /**
     * 更新轨道列表。
     * 腾讯 IoT IJKPlayer fork 不包含 TrackInfo 类，轨道列表不可用，此方法为空实现。
     */
    private fun updateTrackInfo() {
        _trackListJson.value = ""
        audioTrackCount = 0
        subTrackCount = 0
    }

    /**
     * 获取媒体信息（从 IjkMediaPlayer.getMediaInfo 提取）。
     * UI 的 MediaBadgesRow 主要用 getPropertyX（IJK 返回 null 显示 N/A），
     * 此方法作为接口契约的补充实现。
     */
    override fun getMediaInfo(): Map<String, String?> {
        return try {
            val mi = ijkPlayer?.mediaInfo ?: return emptyMap()
            buildMap {
                put("player", mi.mMediaPlayerName)
                put("video-decoder", mi.mVideoDecoder)
                put("audio-decoder", mi.mAudioDecoder)
            }
        } catch (e: Exception) {
            Log.w(TAG, "getMediaInfo failed: ${e.message}")
            emptyMap()
        }
    }

    // -----------------------------------------------------------------
    // 硬件解码切换
    // -----------------------------------------------------------------

    /**
     * 切换硬件/软件解码。
     *
     * IJK 通过 `mediacodec` option 控制（1=硬解，0=软解），
     * 该 option 在每次 playFile 的 reset 后应用，所以切换后需重新播放当前 URL。
     */
    override fun setHardwareDecode(enabled: Boolean): Boolean {
        if (hardwareDecode == enabled) return true
        hardwareDecode = enabled
        Log.i(TAG, "setHardwareDecode: enabled=$enabled")
        if (!nativeAvailable) return false
        // 重新播放当前 URL 以应用新 mediacodec option
        if (currentUrl.isNotEmpty() && _fileLoaded.value) {
            val pos = _timePos.value
            playFile(currentUrl)
            if (pos > 0) {
                pendingSeek = pos
            }
        }
        return true
    }

    override fun isHardwareDecodeEnabled(): Boolean = hardwareDecode

    // -----------------------------------------------------------------
    // 播放状态保存/恢复（用于切换播放器时保持连续性）
    // -----------------------------------------------------------------

    override fun savePlaybackState(): Pair<String, Double>? {
        if (currentUrl.isEmpty() || !_fileLoaded.value) return null
        return currentUrl to _timePos.value
    }

    override fun restorePlaybackState(url: String, timePosSec: Double) {
        // 记录挂起 seek，onPrepared 后执行
        pendingSeek = if (timePosSec > 0) timePosSec else null
        playFile(url)
    }

    companion object {
        private const val TAG = "IjkController"
        private const val POLL_INTERVAL_MS = 500L
    }
}
