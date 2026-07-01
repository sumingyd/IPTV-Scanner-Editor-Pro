package com.iptv.scanner.editor.pro.player

import android.content.Context
import android.os.Handler
import android.os.Looper
import android.util.Log
import androidx.media3.common.C
import androidx.media3.common.MediaItem
import androidx.media3.common.PlaybackParameters
import androidx.media3.common.Player as Media3Player
import androidx.media3.common.Timeline
import androidx.media3.common.TrackSelectionOverride
import androidx.media3.common.Tracks
import androidx.media3.common.VideoSize
import androidx.media3.exoplayer.ExoPlayer
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import org.json.JSONArray
import org.json.JSONObject
import kotlin.math.roundToInt

/**
 * ExoPlayer (androidx.media3) 播放器控制器，实现 [Player] 接口。
 *
 * 设计要点：
 * 1. 封装 [ExoPlayer]，在构造时创建实例（ExoPlayer.Builder(context).build()）
 * 2. 用 [MutableStateFlow] + [asStateFlow] 管理 14 个可观察状态，与 MpvController 对齐
 * 3. 实现 [Media3Player.Listener] 回调，把 ExoPlayer 事件转发到 StateFlow
 * 4. ExoPlayer 没有位置变化回调，用 [Handler.postDelayed] 每 500ms 轮询 currentPosition
 * 5. 音量映射：mpv 标准 0-130 ↔ ExoPlayer 0f-1f（volume/130f）
 * 6. trackListJson 构建为 mpv 兼容格式（JSONArray，元素含 type/id/title/lang），
 *    与 MorePanels.kt 的 parseTracks 兼容
 * 7. 音轨/字幕轨切换通过 TrackSelectionParameters 控制
 *
 * 与 MpvController 的差异：
 * - ExoPlayer 无 property 概念，getPropertyX 返回 null，setPropertyX 为 no-op
 * - 字幕延迟/缩放/位置不支持（ExoPlayer 无此能力），为 no-op
 * - 外挂字幕运行时添加不支持（需侧载），addSubtitleFile 为 no-op
 * - ExoPlayer 实例在 Controller 中创建（非单例），detach 时 release
 *
 * 所有 ExoPlayer 调用必须在主线程执行（ExoPlayer 线程安全要求）。
 */
class ExoPlayerController(context: Context) : Player {

    /** 被 UI 层（ExoPlayerView）访问以绑定 Surface */
    val exoPlayer: ExoPlayer = ExoPlayer.Builder(context).build()

    private val mainHandler = Handler(Looper.getMainLooper())

    // 当前播放 URL（用于 savePlaybackState / mediaTitle 兜底）
    private var currentUrl: String? = null

    // 当前音轨/字幕轨索引（用于 cycleAudio/cycleSub 循环切换）
    private var currentAudioIndex = 0
    private var currentSubIndex = 0

    // 非静音时的真实音量（用于解除静音时恢复，mpv 标准 0-130）
    private var nonMuteVolume = 100

    // 字幕可见性（ExoPlayer 无直接查询接口，内部维护）
    private var subVisible = true

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
    // 能力声明与播放器类型
    // -----------------------------------------------------------------
    override val capabilities: PlayerCapabilities = PlayerCapabilities(
        supportsSpeedControl = true,
        supportsTrackList = true,
        supportsAddSubtitleFile = false,
        supportsChapters = true
    )

    override val playerType: PlayerType = PlayerType.EXO

    // -----------------------------------------------------------------
    // 位置轮询（ExoPlayer 无位置变化回调，需主动轮询）
    // -----------------------------------------------------------------
    private val progressRunnable = object : Runnable {
        override fun run() {
            if (exoPlayer.playbackState != Media3Player.STATE_IDLE) {
                _timePos.value = exoPlayer.currentPosition / 1000.0
                val dur = exoPlayer.duration
                if (dur > 0) _duration.value = dur / 1000.0
            }
            mainHandler.postDelayed(this, PROGRESS_INTERVAL_MS)
        }
    }

    // -----------------------------------------------------------------
    // Media3Player.Listener：把 ExoPlayer 事件转发到 StateFlow
    // -----------------------------------------------------------------
    private val listener = object : Media3Player.Listener {

        override fun onPlaybackStateChanged(playbackState: Int) {
            when (playbackState) {
                Media3Player.STATE_READY -> {
                    _fileLoaded.value = true
                    _eofReached.value = false
                    val dur = exoPlayer.duration
                    if (dur > 0) _duration.value = dur / 1000.0
                }
                Media3Player.STATE_ENDED -> {
                    _eofReached.value = true
                    _fileLoaded.value = false
                }
                Media3Player.STATE_IDLE -> {
                    _fileLoaded.value = false
                    _eofReached.value = false
                }
                Media3Player.STATE_BUFFERING -> {
                    // 缓冲中：保持 fileLoaded 不变（避免 UI 闪烁）
                }
            }
        }

        override fun onIsPlayingChanged(isPlaying: Boolean) {
            _paused.value = !isPlaying
        }

        override fun onPositionDiscontinuity(
            oldPosition: Media3Player.PositionInfo,
            newPosition: Media3Player.PositionInfo,
            reason: Int
        ) {
            _timePos.value = exoPlayer.currentPosition / 1000.0
        }

        override fun onTimelineChanged(timeline: Timeline, reason: Int) {
            val dur = exoPlayer.duration
            if (dur > 0) _duration.value = dur / 1000.0
        }

        override fun onTracksChanged(tracks: Tracks) {
            _trackListJson.value = buildTrackListJson()
        }

        override fun onVideoSizeChanged(videoSize: VideoSize) {
            _videoWidth.value = videoSize.width
            _videoHeight.value = videoSize.height
        }

        override fun onVolumeChanged(volume: Float) {
            // ExoPlayer volume 为 0f-1f，映射回 mpv 标准 0-130
            val isMuted = volume <= 0f
            _muted.value = isMuted
            // 静音时不更新 _volume（保持真实音量值，与 mpv 行为一致）
            if (!isMuted) {
                val v = (volume * 130f).roundToInt().coerceIn(0, 130)
                _volume.value = v
                nonMuteVolume = v
            }
        }

        override fun onPlaybackParametersChanged(playbackParameters: PlaybackParameters) {
            _speed.value = playbackParameters.speed.toDouble()
        }

        override fun onMediaItemTransition(mediaItem: MediaItem?, reason: Int) {
            val title = mediaItem?.mediaMetadata?.title?.toString()
            _mediaTitle.value = if (!title.isNullOrEmpty()) {
                title
            } else {
                currentUrl?.substringAfterLast('/') ?: ""
            }
        }
    }

    init {
        // 同步初始音量：_volume 默认 100，ExoPlayer 默认 1f（=130），需对齐
        exoPlayer.volume = 100f / 130f
        exoPlayer.addListener(listener)
        mainHandler.postDelayed(progressRunnable, PROGRESS_INTERVAL_MS)
        Log.i(TAG, "ExoPlayerController created")
    }

    // -----------------------------------------------------------------
    // 生命周期
    // -----------------------------------------------------------------
    override fun attachView(view: Any) {
        if (view is ExoPlayerView) {
            view.attachController(this)
        } else {
            Log.w(TAG, "attachView: unexpected view type ${view?.javaClass?.name}")
        }
    }

    override fun detach() {
        mainHandler.removeCallbacks(progressRunnable)
        exoPlayer.removeListener(listener)
        exoPlayer.release()
        // 重置状态（避免 Compose 用旧值）
        _fileLoaded.value = false
        _eofReached.value = false
        _timePos.value = 0.0
        _duration.value = 0.0
        _paused.value = true
        _trackListJson.value = ""
        _videoWidth.value = 0
        _videoHeight.value = 0
        Log.i(TAG, "ExoPlayerController detached and released")
    }

    // -----------------------------------------------------------------
    // 基础播放控制
    // -----------------------------------------------------------------
    override fun playFile(url: String) {
        currentUrl = url
        _eofReached.value = false
        _fileLoaded.value = false
        val mediaItem = MediaItem.fromUri(url)
        exoPlayer.setMediaItem(mediaItem)
        exoPlayer.prepare()
        exoPlayer.playWhenReady = true
    }

    override fun stop() {
        exoPlayer.stop()
        _fileLoaded.value = false
        _timePos.value = 0.0
    }

    override fun togglePause() {
        exoPlayer.playWhenReady = !exoPlayer.playWhenReady
    }

    override fun setPause(p: Boolean) {
        exoPlayer.playWhenReady = !p
    }

    override fun seekTo(seconds: Double) {
        exoPlayer.seekTo((seconds * 1000).toLong())
    }

    override fun seekRelative(seconds: Double) {
        val targetMs = exoPlayer.currentPosition + (seconds * 1000).toLong()
        exoPlayer.seekTo(targetMs)
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
        nonMuteVolume = clamped
        // 静音时不改变 ExoPlayer 实际音量（保持 0f），解除静音时再恢复
        if (!_muted.value) {
            exoPlayer.volume = clamped / 130f
        }
    }

    override fun adjustVolume(delta: Int) {
        setVolume(_volume.value + delta)
    }

    override fun toggleMute() {
        setMute(!_muted.value)
    }

    override fun setMute(m: Boolean) {
        _muted.value = m
        exoPlayer.volume = if (m) 0f else (nonMuteVolume / 130f)
    }

    override fun setSpeed(s: Double) {
        val clamped = s.coerceIn(0.01, 100.0)
        exoPlayer.playbackParameters = PlaybackParameters(clamped.toFloat())
    }

    // -----------------------------------------------------------------
    // 音轨 / 字幕轨
    // -----------------------------------------------------------------
    override fun cycleAudio() {
        val audioGroups = exoPlayer.currentTracks.groups.filter { it.type == C.TRACK_TYPE_AUDIO }
        if (audioGroups.isEmpty()) return
        currentAudioIndex = (currentAudioIndex + 1) % audioGroups.size
        setAudioTrack(currentAudioIndex + 1)
    }

    override fun cycleSub() {
        val subGroups = exoPlayer.currentTracks.groups.filter { it.type == C.TRACK_TYPE_TEXT }
        if (subGroups.isEmpty()) return
        // 循环：字幕1 → 字幕2 → ... → 关闭 → 字幕1
        currentSubIndex = (currentSubIndex + 1) % (subGroups.size + 1)
        if (currentSubIndex == subGroups.size) {
            // 关闭字幕
            val params = exoPlayer.trackSelectionParameters.buildUpon()
                .setTrackTypeDisabled(C.TRACK_TYPE_TEXT, true)
                .build()
            exoPlayer.trackSelectionParameters = params
            subVisible = false
        } else {
            setSubTrack(currentSubIndex + 1)
        }
    }

    override fun setAudioTrack(id: Int) {
        val audioGroups = exoPlayer.currentTracks.groups.filter { it.type == C.TRACK_TYPE_AUDIO }
        if (audioGroups.isEmpty()) return
        val targetIdx = (id - 1).coerceIn(0, audioGroups.lastIndex)
        currentAudioIndex = targetIdx
        val targetGroup = audioGroups[targetIdx]
        val override = TrackSelectionOverride(targetGroup.mediaTrackGroup, 0)
        val params = exoPlayer.trackSelectionParameters.buildUpon()
            .setTrackTypeDisabled(C.TRACK_TYPE_AUDIO, false)
            .setOverrideForType(override)
            .build()
        exoPlayer.trackSelectionParameters = params
    }

    override fun setSubTrack(id: Int) {
        val subGroups = exoPlayer.currentTracks.groups.filter { it.type == C.TRACK_TYPE_TEXT }
        if (subGroups.isEmpty()) return
        val targetIdx = (id - 1).coerceIn(0, subGroups.lastIndex)
        currentSubIndex = targetIdx
        subVisible = true
        val targetGroup = subGroups[targetIdx]
        val override = TrackSelectionOverride(targetGroup.mediaTrackGroup, 0)
        val params = exoPlayer.trackSelectionParameters.buildUpon()
            .setTrackTypeDisabled(C.TRACK_TYPE_TEXT, false)
            .setOverrideForType(override)
            .build()
        exoPlayer.trackSelectionParameters = params
    }

    override fun addSubtitleFile(path: String) {
        // ExoPlayer 需要通过 MediaItem.SubtitleConfiguration 侧载字幕，
        // 运行时添加外挂字幕暂不支持（capabilities.supportsAddSubtitleFile = false）
        Log.w(TAG, "addSubtitleFile not supported by ExoPlayer")
    }

    // -----------------------------------------------------------------
    // 字幕显示与样式
    // -----------------------------------------------------------------
    override fun setSubVisibility(v: Boolean) {
        subVisible = v
        val params = exoPlayer.trackSelectionParameters.buildUpon()
            .setTrackTypeDisabled(C.TRACK_TYPE_TEXT, !v)
            .build()
        exoPlayer.trackSelectionParameters = params
    }

    override fun toggleSubVisibility() {
        setSubVisibility(!subVisible)
    }

    override fun setSubDelay(delaySec: Double) {
        // ExoPlayer 不支持字幕延迟调整
    }

    override fun adjustSubDelay(delta: Double) {
        // ExoPlayer 不支持字幕延迟调整
    }

    override fun setSubScale(scale: Double) {
        // ExoPlayer 不支持字幕缩放
    }

    override fun setSubPos(pos: Int) {
        // ExoPlayer 不支持字幕位置调整
    }

    // -----------------------------------------------------------------
    // 媒体信息
    // -----------------------------------------------------------------
    override fun getMediaInfo(): Map<String, String?> {
        val info = mutableMapOf<String, String?>()
        exoPlayer.videoFormat?.let { vf ->
            vf.sampleMimeType?.let { info["video-codec"] = it }
            if (vf.bitrate > 0) info["video-bitrate"] = vf.bitrate.toString()
            if (vf.frameRate > 0f) info["video-fps"] = vf.frameRate.toString()
            if (vf.width > 0) info["video-width"] = vf.width.toString()
            if (vf.height > 0) info["video-height"] = vf.height.toString()
        }
        exoPlayer.audioFormat?.let { af ->
            af.sampleMimeType?.let { info["audio-codec"] = it }
            if (af.bitrate > 0) info["audio-bitrate"] = af.bitrate.toString()
            if (af.sampleRate > 0) info["audio-samplerate"] = af.sampleRate.toString()
            if (af.channelCount > 0) info["audio-channels"] = af.channelCount.toString()
        }
        if (_duration.value > 0) info["duration"] = _duration.value.toString()
        return info
    }

    // -----------------------------------------------------------------
    // 播放状态保存/恢复（用于切换播放器时保持连续性）
    // -----------------------------------------------------------------
    override fun savePlaybackState(): Pair<String, Double>? {
        val url = currentUrl ?: return null
        if (url.isEmpty()) return null
        return url to _timePos.value
    }

    override fun restorePlaybackState(url: String, timePosSec: Double) {
        currentUrl = url
        _eofReached.value = false
        _fileLoaded.value = false
        val mediaItem = MediaItem.fromUri(url)
        // 用 setMediaItem 的 startPosition 参数恢复进度（ExoPlayer 推荐方式）
        val startMs = (timePosSec * 1000).toLong().coerceAtLeast(0L)
        exoPlayer.setMediaItem(mediaItem, startMs)
        exoPlayer.prepare()
        exoPlayer.playWhenReady = true
    }

    // -----------------------------------------------------------------
    // 内部：构建 mpv 兼容的 track-list JSON
    // -----------------------------------------------------------------
    /**
     * 构建 track-list JSON，格式与 mpv 兼容：
     * [{"type":"audio","id":1,"title":"...","lang":"..."}, ...]
     *
     * 每个 TrackGroup 作为一个轨道条目（组内多格式视为同一轨道）。
     * id 按类型分别从 1 递增（audio: 1,2,3... / video: 1,2,3... / sub: 1,2,3...）。
     * 与 MorePanels.kt 的 parseTracks 兼容。
     */
    private fun buildTrackListJson(): String {
        val arr = JSONArray()
        var audioId = 1
        var videoId = 1
        var subId = 1
        for (group in exoPlayer.currentTracks.groups) {
            if (group.length == 0) continue
            val typeStr = when (group.type) {
                C.TRACK_TYPE_AUDIO -> "audio"
                C.TRACK_TYPE_VIDEO -> "video"
                C.TRACK_TYPE_TEXT -> "sub"
                else -> continue
            }
            val format = group.getTrackFormat(0)
            val id = when (group.type) {
                C.TRACK_TYPE_AUDIO -> audioId++
                C.TRACK_TYPE_VIDEO -> videoId++
                C.TRACK_TYPE_TEXT -> subId++
                else -> continue
            }
            val obj = JSONObject()
            obj.put("type", typeStr)
            obj.put("id", id)
            // 标题优先用 label，其次 lang，最后兜底 "轨道 N"
            val title = format.label?.takeIf { it.isNotEmpty() }
                ?: format.language?.takeIf { it.isNotEmpty() }
                ?: "轨道 $id"
            obj.put("title", title)
            obj.put("lang", format.language ?: "")
            arr.put(obj)
        }
        return arr.toString()
    }

    companion object {
        private const val TAG = "ExoPlayerController"

        /** 位置轮询间隔（毫秒） */
        private const val PROGRESS_INTERVAL_MS = 500L
    }
}
