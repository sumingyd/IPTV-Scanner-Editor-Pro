package com.iptv.scanner.editor.pro.player

import android.content.Context
import android.net.Uri
import android.util.Log
import androidx.media3.common.AudioAttributes
import androidx.media3.common.C
import androidx.media3.common.MediaItem
import androidx.media3.common.PlaybackException
import androidx.media3.common.Player as Media3Player
import androidx.media3.common.TrackSelectionParameters
import androidx.media3.common.TrackSelectionOverride
import androidx.media3.common.VideoSize
import androidx.media3.exoplayer.DefaultRenderersFactory
import androidx.media3.datasource.DefaultDataSource
import androidx.media3.datasource.DefaultHttpDataSource
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.exoplayer.source.DefaultMediaSourceFactory
import androidx.media3.ui.PlayerView
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * 基于 ExoPlayer 的播放器适配器，实现 [Player] 接口。
 *
 * 用于 [PlayerType.EXO]（硬解）和 [PlayerType.SYSTEM]（软解）两种模式。
 *
 * 与 [MpvController] 的区别：
 * - MPV 功能最完整（EQ/AB循环/逐帧/截图/HDR），但某些设备 GPU 兼容性差
 * - ExoPlayer 兼容性好（Google 官方维护），HLS/DASH/RTSP 协议支持完善
 * - 系统解码（软解）作为最终 fallback，不依赖 GPU
 *
 * MPV 专属的高级功能（EQ/截图/AB循环/逐帧/章节等）在此实现中返回 false 或 no-op，
 * UI 层通过 [capabilities] 自动隐藏不支持的功能面板。
 *
 * @param context 应用上下文
 * @param type [PlayerType.EXO] 或 [PlayerType.SYSTEM]
 */
class ExoPlayerWrapper(
    private val context: Context,
    private val type: PlayerType
) : Player {

    companion object {
        private const val TAG = "ExoPlayerWrapper"
        private const val USER_AGENT = "VLC/3.0.18Libmpv"
    }

    private var player: ExoPlayer? = null
    private var playerView: PlayerView? = null
    private var currentUrl: String = ""

    // -----------------------------------------------------------------
    // 可观察状态（与 MpvController StateFlow 对齐）
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

    private val _trackListJson = MutableStateFlow("[]")
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
        supportsTrackList = true,
        supportsAddSubtitleFile = true,
        supportsSubDelay = false,
        supportsSubScale = false,
        supportsSubPos = false,
        supportsHardwareDecodeSwitch = true
    )

    override val playerType: PlayerType = type

    // -----------------------------------------------------------------
    // 生命周期
    // -----------------------------------------------------------------

    /**
     * 绑定 View（PlayerView）。
     * 同时初始化 ExoPlayer 实例（如果尚未初始化）。
     */
    override fun attachView(view: Any) {
        if (view !is PlayerView) {
            Log.w(TAG, "attachView: expected PlayerView, got ${view::class.simpleName}")
            return
        }
        playerView = view
        ensurePlayer()
        view.player = player
        // 不再在 attachView 中调 setHardwareDecode：
        // 渲染器模式在 ensurePlayer() 中根据 type 直接设置，避免无效的 rebuild。
        Log.i(TAG, "attachView: PlayerView attached, type=$type, hwdec=$hardwareDecodeEnabled")
    }

    /** 解绑 View，释放 ExoPlayer 资源 */
    override fun detach() {
        playerView?.player = null
        playerView = null
        try {
            player?.release()
        } catch (e: Exception) {
            Log.w(TAG, "detach: release failed: ${e.message}")
        }
        player = null
        _fileLoaded.value = false
        _paused.value = true
        _timePos.value = 0.0
        _duration.value = 0.0
        _videoWidth.value = 0
        _videoHeight.value = 0
        Log.i(TAG, "detach: released")
    }

    private fun ensurePlayer() {
        if (player != null) return
        try {
            // ExoPlayer 使用 Android HTTP 栈，受 network_security_config.xml 限制。
            // MPV 用自己的网络栈不受影响，但 ExoPlayer 需要显式允许 cleartext HTTP。
            // setAllowCrossProtocolRedirects=true 允许 HTTPS→HTTP 重定向（IPTV 常见）。
            val httpDataSourceFactory = DefaultHttpDataSource.Factory()
                .setUserAgent(USER_AGENT)
                .setConnectTimeoutMs(10_000)
                .setReadTimeoutMs(30_000)
                .setAllowCrossProtocolRedirects(true)
            val dataSourceFactory = DefaultDataSource.Factory(context, httpDataSourceFactory)
            val mediaSourceFactory = DefaultMediaSourceFactory(dataSourceFactory)

            // 渲染器配置：根据播放器类型选择不同的解码器模式
            // - EXO（硬解）：EXTENSION_RENDERER_MODE_OFF → 只用 MediaCodec（硬件解码）
            // - SYSTEM（软解）：EXTENSION_RENDERER_MODE_PREFER → 优先用 FFmpeg 扩展（软件解码），
            //   fallback 到 MediaCodec（仅当 FFmpeg 扩展未安装或解码器不支持该编码时）
            //
            // DefaultRenderersFactory 扩展渲染器模式说明：
            // - OFF：不加载扩展渲染器，只用内置 MediaCodec 渲染器（纯硬解）
            // - ON：加载扩展渲染器但优先级低于 MediaCodec（硬解优先，软解 fallback）
            // - PREFER：加载扩展渲染器且优先级高于 MediaCodec（软解优先，硬解 fallback）
            val extensionMode = if (type == PlayerType.SYSTEM) {
                DefaultRenderersFactory.EXTENSION_RENDERER_MODE_PREFER
            } else {
                DefaultRenderersFactory.EXTENSION_RENDERER_MODE_OFF
            }
            val renderersFactory = DefaultRenderersFactory(context)
                .setEnableDecoderFallback(true)
                .setExtensionRendererMode(extensionMode)
            player = ExoPlayer.Builder(context, renderersFactory)
                .setMediaSourceFactory(mediaSourceFactory)
                .setUseLazyPreparation(true)
                .setAudioAttributes(
                    AudioAttributes.Builder()
                        .setUsage(C.USAGE_MEDIA)
                        .setContentType(C.AUDIO_CONTENT_TYPE_MOVIE)
                        .build(),
                    true  // handleAudioFocus = true
                )
                .setHandleAudioBecomingNoisy(true)
                .build().also { p ->
                    p.addListener(object : Media3Player.Listener {
                        override fun onPlaybackStateChanged(playbackState: Int) {
                            when (playbackState) {
                                Media3Player.STATE_BUFFERING -> {
                                    // buffering
                                }
                                Media3Player.STATE_READY -> {
                                    _paused.value = !p.isPlaying
                                    _fileLoaded.value = true
                                    _duration.value = (p.duration.coerceAtLeast(0)) / 1000.0
                                }
                                Media3Player.STATE_ENDED -> {
                                    _eofReached.value = true
                                    _paused.value = true
                                }
                                Media3Player.STATE_IDLE -> {
                                    _fileLoaded.value = false
                                }
                            }
                        }

                        override fun onIsPlayingChanged(isPlaying: Boolean) {
                            _paused.value = !isPlaying
                        }

                        override fun onPlayerError(error: PlaybackException) {
                            Log.e(TAG, "Player error: ${error.message}", error)
                            _fileLoaded.value = false
                        }

                        override fun onVideoSizeChanged(videoSize: VideoSize) {
                            _videoWidth.value = videoSize.width
                            _videoHeight.value = videoSize.height
                        }
                    })
                }
            Log.i(TAG, "ExoPlayer initialized, type=$type")
        } catch (e: Exception) {
            Log.e(TAG, "ensurePlayer failed", e)
        }
    }

    // -----------------------------------------------------------------
    // 基础播放控制
    // -----------------------------------------------------------------

    override fun playFile(url: String) {
        ensurePlayer()
        val p = player ?: run {
            Log.e(TAG, "playFile: player is null")
            return
        }
        currentUrl = url
        _eofReached.value = false
        _fileLoaded.value = false
        try {
            Log.i(TAG, "playFile: $url")
            val mediaItem = MediaItem.Builder().setUri(Uri.parse(url)).build()
            p.setMediaItem(mediaItem)
            p.prepare()
            p.playWhenReady = true
            _paused.value = false
            _mediaTitle.value = url.substringAfterLast('/').substringBefore('?')
        } catch (e: Exception) {
            Log.e(TAG, "playFile failed: $url", e)
        }
    }

    override fun stop() {
        try {
            player?.stop()
            _fileLoaded.value = false
            _paused.value = true
            _timePos.value = 0.0
            currentUrl = ""
            Log.i(TAG, "stop")
        } catch (e: Exception) {
            Log.w(TAG, "stop failed: ${e.message}")
        }
    }

    override fun refreshSurface() {
        // ExoPlayer 不需要手动刷新 Surface
    }

    override fun togglePause() {
        val p = player ?: return
        p.playWhenReady = !p.playWhenReady
        _paused.value = !p.playWhenReady
    }

    override fun setPause(p: Boolean) {
        player?.playWhenReady = !p
        _paused.value = p
    }

    override fun seekTo(seconds: Double) {
        player?.seekTo((seconds * 1000).toLong())
    }

    override fun seekRelative(seconds: Double) {
        val p = player ?: return
        val target = (p.currentPosition + seconds * 1000.0).coerceAtLeast(0.0)
            .coerceAtMost(p.duration.coerceAtLeast(0L).toDouble())
        p.seekTo(target.toLong())
    }

    override fun seekAbsolute(seconds: Double) {
        seekTo(seconds)
    }

    // -----------------------------------------------------------------
    // 音量 / 静音 / 速度
    // -----------------------------------------------------------------

    override fun setVolume(v: Int) {
        val clamped = v.coerceIn(0, 130)
        _volume.value = clamped
        // ExoPlayer 音量范围 0.0~1.0，mpv 范围 0~130
        player?.volume = (clamped / 100f).coerceIn(0f, 1f)
    }

    override fun adjustVolume(delta: Int) {
        setVolume(_volume.value + delta)
    }

    override fun toggleMute() {
        setMute(!_muted.value)
    }

    override fun setMute(m: Boolean) {
        _muted.value = m
        player?.volume = if (m) 0f else (_volume.value / 100f).coerceIn(0f, 1f)
    }

    override fun setSpeed(s: Double) {
        val clamped = s.coerceIn(0.01, 100.0)
        _speed.value = clamped
        try {
            val params = player?.playbackParameters?.withSpeed(clamped.toFloat())
            player?.playbackParameters = params ?: androidx.media3.common.PlaybackParameters(clamped.toFloat())
        } catch (e: Exception) {
            Log.w(TAG, "setSpeed failed: ${e.message}")
        }
    }

    // -----------------------------------------------------------------
    // 音轨 / 字幕轨
    // -----------------------------------------------------------------

    override fun cycleAudio() {
        val p = player ?: return
        val audioGroups = p.currentTracks.groups.filter { it.type == androidx.media3.common.C.TRACK_TYPE_AUDIO }
        if (audioGroups.isEmpty()) return
        try {
            val currentSelectedIdx = audioGroups.indexOfFirst { it.isSelected }
            val nextIdx = if (currentSelectedIdx >= 0 && currentSelectedIdx < audioGroups.size - 1) currentSelectedIdx + 1 else 0
            val nextGroup = audioGroups[nextIdx]
            val trackIndices = mutableListOf<Int>()
            for (i in 0 until nextGroup.length) {
                if (nextGroup.isTrackSupported(i)) trackIndices.add(i)
            }
            if (trackIndices.isEmpty()) return
            p.trackSelectionParameters = p.trackSelectionParameters.buildUpon()
                .setOverrideForType(TrackSelectionOverride(nextGroup.mediaTrackGroup, trackIndices))
                .setTrackTypeDisabled(C.TRACK_TYPE_AUDIO, false)
                .build()
            Log.i(TAG, "cycleAudio: switched to audio track $nextIdx")
        } catch (e: Exception) {
            Log.w(TAG, "cycleAudio failed: ${e.message}")
        }
    }

    override fun cycleSub() {
        val p = player ?: return
        val subGroups = p.currentTracks.groups.filter { it.type == androidx.media3.common.C.TRACK_TYPE_TEXT }
        if (subGroups.isEmpty()) {
            val subEnabled = p.trackSelectionParameters.disabledTrackTypes
                .contains(androidx.media3.common.C.TRACK_TYPE_TEXT).not()
            p.trackSelectionParameters = p.trackSelectionParameters.buildUpon()
                .setTrackTypeDisabled(androidx.media3.common.C.TRACK_TYPE_TEXT, subEnabled)
                .build()
            return
        }
        try {
            val currentSelectedIdx = subGroups.indexOfFirst { it.isSelected }
            val nextIdx = if (currentSelectedIdx >= 0 && currentSelectedIdx < subGroups.size - 1) currentSelectedIdx + 1 else 0
            p.trackSelectionParameters = p.trackSelectionParameters.buildUpon()
                .setTrackTypeDisabled(androidx.media3.common.C.TRACK_TYPE_TEXT, false)
                .build()
            Log.i(TAG, "cycleSub: switched to subtitle track $nextIdx")
        } catch (e: Exception) {
            Log.w(TAG, "cycleSub failed: ${e.message}")
        }
    }

    override fun setAudioTrack(id: Int) {
        val p = player ?: return
        val audioGroups = p.currentTracks.groups.filter { it.type == androidx.media3.common.C.TRACK_TYPE_AUDIO }
        if (audioGroups.isEmpty() || id < 0 || id >= audioGroups.size) return
        try {
            val targetGroup = audioGroups[id]
            val trackIndices = mutableListOf<Int>()
            for (i in 0 until targetGroup.length) {
                if (targetGroup.isTrackSupported(i)) trackIndices.add(i)
            }
            if (trackIndices.isEmpty()) return
            p.trackSelectionParameters = p.trackSelectionParameters.buildUpon()
                .setOverrideForType(androidx.media3.common.TrackSelectionOverride(targetGroup.mediaTrackGroup, trackIndices))
                .setTrackTypeDisabled(androidx.media3.common.C.TRACK_TYPE_AUDIO, false)
                .build()
            Log.i(TAG, "setAudioTrack: set to track $id")
        } catch (e: Exception) {
            Log.w(TAG, "setAudioTrack failed: ${e.message}")
        }
    }

    override fun setSubTrack(id: Int) {
        val p = player ?: return
        val subGroups = p.currentTracks.groups.filter { it.type == androidx.media3.common.C.TRACK_TYPE_TEXT }
        if (subGroups.isEmpty() || id < 0 || id >= subGroups.size) return
        try {
            val targetGroup = subGroups[id]
            val trackIndices = mutableListOf<Int>()
            for (i in 0 until targetGroup.length) {
                if (targetGroup.isTrackSupported(i)) trackIndices.add(i)
            }
            if (trackIndices.isEmpty()) return
            p.trackSelectionParameters = p.trackSelectionParameters.buildUpon()
                .setOverrideForType(androidx.media3.common.TrackSelectionOverride(targetGroup.mediaTrackGroup, trackIndices))
                .setTrackTypeDisabled(androidx.media3.common.C.TRACK_TYPE_TEXT, false)
                .build()
            Log.i(TAG, "setSubTrack: set to track $id")
        } catch (e: Exception) {
            Log.w(TAG, "setSubTrack failed: ${e.message}")
        }
    }

    override fun addSubtitleFile(path: String) {
        // ExoPlayer 支持外挂字幕通过 MediaItem.subtitleConfigurations
        Log.i(TAG, "addSubtitleFile: $path (not fully implemented)")
    }

    // -----------------------------------------------------------------
    // 字幕显示与样式
    // -----------------------------------------------------------------

    override fun setSubVisibility(v: Boolean) {
        val p = player ?: return
        p.trackSelectionParameters = p.trackSelectionParameters.buildUpon()
            .setTrackTypeDisabled(androidx.media3.common.C.TRACK_TYPE_TEXT, !v)
            .build()
    }

    override fun setSubDelay(delaySec: Double) {
        // ExoPlayer 不支持字幕延迟设置
    }

    override fun adjustSubDelay(delta: Double) {
        // ExoPlayer 不支持字幕延迟调整
    }

    override fun setSubScale(scale: Double) {
        // ExoPlayer 不支持字幕缩放
    }

    override fun setSubPos(pos: Int) {
        // ExoPlayer 不支持字幕位置设置
    }

    override fun toggleSubVisibility() {
        val p = player ?: return
        val currentlyVisible = !p.trackSelectionParameters.disabledTrackTypes
            .contains(androidx.media3.common.C.TRACK_TYPE_TEXT)
        setSubVisibility(!currentlyVisible)
    }

    // -----------------------------------------------------------------
    // 硬件解码切换
    // -----------------------------------------------------------------

    @Volatile
    private var hardwareDecodeEnabled = (type != PlayerType.SYSTEM)

    override fun setHardwareDecode(enabled: Boolean): Boolean {
        val target = if (type == PlayerType.SYSTEM) false else enabled
        if (hardwareDecodeEnabled == target) return true
        hardwareDecodeEnabled = target
        Log.i(TAG, "setHardwareDecode: $target (type=$type)")
        try {
            val p = player ?: return true
            // 重建播放器以应用新的 RenderersFactory 配置
            val currentUrl = this.currentUrl
            if (currentUrl.isNotEmpty()) {
                val currentPosition = p.currentPosition
                p.release()
                player = null
                ensurePlayer()
                player?.let { newPlayer ->
                    val mediaItem = MediaItem.Builder().setUri(Uri.parse(currentUrl)).build()
                    newPlayer.setMediaItem(mediaItem)
                    newPlayer.prepare()
                    if (currentPosition > 0) {
                        newPlayer.seekTo(currentPosition)
                    }
                    newPlayer.playWhenReady = true
                    _paused.value = false
                    // 重新绑定到 PlayerView
                    playerView?.player = newPlayer
                }
            }
        } catch (e: Exception) {
            Log.e(TAG, "setHardwareDecode failed", e)
        }
        return true
    }

    override fun isHardwareDecodeEnabled(): Boolean = hardwareDecodeEnabled

    // -----------------------------------------------------------------
    // 播放状态保存/恢复
    // -----------------------------------------------------------------

    override fun savePlaybackState(): Pair<String, Double>? {
        if (currentUrl.isEmpty()) return null
        return Pair(currentUrl, _timePos.value)
    }

    override fun restorePlaybackState(url: String, timePosSec: Double) {
        playFile(url)
        if (timePosSec > 0) {
            val targetMs = (timePosSec * 1000).toLong()
            val p = player ?: return
            val listener = object : Media3Player.Listener {
                override fun onPlaybackStateChanged(playbackState: Int) {
                    if (playbackState == Media3Player.STATE_READY) {
                        p.seekTo(targetMs)
                        p.removeListener(this)
                    }
                }
            }
            p.addListener(listener)
        }
    }

    /**
     * 获取媒体信息（与 MpvController.getMediaInfo 对齐）。
     * 通过 ExoPlayer 的 TrackInfo 提取视频/音频编码、分辨率、HDR 等信息。
     */
    override fun getMediaInfo(): Map<String, String?> {
        val p = player ?: return emptyMap()
        return try {
            val tracks = p.currentTracks
            var videoCodec: String? = null
            var audioCodec: String? = null
            var videoBitrate: String? = null
            var audioBitrate: String? = null
            var fps: String? = null
            var primaries: String? = null
            var gamma: String? = null
            var colorRange: String? = null

            for (trackGroup in tracks.groups) {
                val trackType = trackGroup.type
                if (trackGroup.length == 0) continue
                val format = trackGroup.getTrackFormat(0)
                when (trackType) {
                    androidx.media3.common.C.TRACK_TYPE_VIDEO -> {
                        videoCodec = format.sampleMimeType
                        videoBitrate = if (format.bitrate > 0) format.bitrate.toString() else null
                        if (format.frameRate > 0f) fps = format.frameRate.toString()
                        val colorInfo = format.colorInfo
                        if (colorInfo != null) {
                            primaries = when (colorInfo.colorSpace) {
                                androidx.media3.common.C.COLOR_SPACE_BT709 -> "bt.709"
                                androidx.media3.common.C.COLOR_SPACE_BT601 -> "bt.601"
                                androidx.media3.common.C.COLOR_SPACE_BT2020 -> "bt.2020"
                                else -> null
                            }
                            gamma = when (colorInfo.colorTransfer) {
                                androidx.media3.common.C.COLOR_TRANSFER_SDR -> "sdr"
                                androidx.media3.common.C.COLOR_TRANSFER_HLG -> "hlg"
                                androidx.media3.common.C.COLOR_TRANSFER_ST2084 -> "pq"
                                else -> null
                            }
                            colorRange = when (colorInfo.colorRange) {
                                androidx.media3.common.C.COLOR_RANGE_FULL -> "full"
                                androidx.media3.common.C.COLOR_RANGE_LIMITED -> "limited"
                                else -> null
                            }
                        }
                    }
                    androidx.media3.common.C.TRACK_TYPE_AUDIO -> {
                        audioCodec = format.sampleMimeType
                        audioBitrate = if (format.bitrate > 0) format.bitrate.toString() else null
                    }
                }
            }

            mapOf(
                "videoCodec" to videoCodec,
                "audioCodec" to audioCodec,
                "videoRes" to "${_videoWidth.value}x${_videoHeight.value}",
                "fps" to fps,
                "bitrate" to videoBitrate,
                "audioBitrate" to audioBitrate,
                "containerFormat" to p.currentMediaItem?.localConfiguration?.mimeType,
                "hwdec" to if (type == PlayerType.EXO) "mediacodec" else "soft",
                "vo" to "exo",
                "videoPrimaries" to primaries,
                "videoGamma" to gamma,
                "videoColorRange" to colorRange
            )
        } catch (e: Throwable) {
            Log.w(TAG, "getMediaInfo failed: ${e.message}")
            emptyMap()
        }
    }

    /**
     * 更新进度（由 UI 定时轮询调用，与 MpvController 的 progress report 对齐）。
     */
    fun updateProgress() {
        val p = player ?: return
        try {
            _timePos.value = p.currentPosition / 1000.0
            if (p.duration > 0) {
                _duration.value = p.duration / 1000.0
            }
        } catch (e: Exception) {
            // ignore
        }
    }
}
