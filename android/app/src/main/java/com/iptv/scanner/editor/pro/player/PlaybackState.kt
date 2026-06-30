package com.iptv.scanner.editor.pro.player

import com.iptv.scanner.editor.pro.data.IptvChannel
import com.iptv.scanner.editor.pro.data.IptvEpgProgram

/**
 * 播放状态：与 PC 端 [core/play_state.py] 的 PlayMode 对齐。
 *
 * 4 个状态：
 * - IDLE：未播放（停止后）
 * - LIVE：直播
 * - CATCHUP：回看（点击 EPG 过去节目触发）
 * - TIMESHIFT：时移（点击直播进度条超出缓冲触发）
 *
 * 注意：判断"在回看或时移模式"必须用 [isCatchupOrTimeshift]，
 * 判断"纯回看非时移"用 `mode == CATCHUP`。
 */
enum class PlayMode {
    IDLE,
    LIVE,
    CATCHUP,
    TIMESHIFT;

    val isLive: Boolean get() = this == LIVE
    val isCatchup: Boolean get() = this == CATCHUP
    val isTimeshift: Boolean get() = this == TIMESHIFT
    val isCatchupOrTimeshift: Boolean get() = this == CATCHUP || this == TIMESHIFT
    val isPlaying: Boolean get() = this != IDLE
}

/**
 * 回看/时移节目信息：与 PC 端 [controllers/catchup_controller.py] CatchupProgram 对齐。
 *
 * @param program 原始 EPG 节目（含 title/desc）
 * @param startMs 节目开始时间（墙钟时间戳，毫秒）
 * @param endMs 节目结束时间（墙钟时间戳，毫秒）
 */
data class CatchupProgram(
    val program: IptvEpgProgram,
    val startMs: Long,
    val endMs: Long,
) {
    val title: String get() = program.title
    val desc: String get() = program.desc
    val durationSec: Long get() = ((endMs - startMs) / 1000).coerceAtLeast(0L)
}

/**
 * 播放状态容器：封装 playMode + originalChannel + catchupProgram + liveTimeshiftSeconds。
 *
 * 与 PC 端 `CatchupController._original_channel` + `_catchup_program` + `window._live_timeshift_seconds` 对齐。
 * 与 mobile index.html `state.playMode/originalChannel/catchupProgram/liveTimeshiftSeconds` 对齐。
 *
 * @param mode 当前播放模式
 * @param originalChannel 进入回看/时移前的原始频道（用于退出回看后恢复直播）
 * @param catchupProgram 当前回看/时移的节目信息（含 start/end 时间戳）
 * @param liveTimeshiftSeconds 时移落后秒数（now - targetWallclock）
 * @param catchupStartMs 回看/时移开始时的墙钟时间戳（用于计算 elapsed，对应 PC 端 `_catchup_start_time`）
 * @param catchupStartProgressSec 回看/时移开始时的进度位置（秒，对应 PC 端 `_catchup_start_progress`）
 */
data class PlaybackState(
    val mode: PlayMode = PlayMode.IDLE,
    val originalChannel: IptvChannel? = null,
    val catchupProgram: CatchupProgram? = null,
    val liveTimeshiftSeconds: Long = 0L,
    val catchupStartMs: Long = 0L,
    val catchupStartProgressSec: Double = 0.0,
) {
    /** 进入回看/时移状态（统一入口，对应 PC 端 _enter_catchup_state） */
    fun enterCatchup(
        channel: IptvChannel,
        program: CatchupProgram,
        mode: PlayMode,
    ): PlaybackState = copy(
        mode = mode,
        originalChannel = channel,
        catchupProgram = program,
        liveTimeshiftSeconds = 0L,
        catchupStartMs = System.currentTimeMillis(),
        catchupStartProgressSec = 0.0,
    )

    /** 清空 catchup 状态（对应 PC 端 _clear_catchup_state） */
    fun clearCatchup(mode: PlayMode = PlayMode.IDLE): PlaybackState = copy(
        mode = mode,
        originalChannel = null,
        catchupProgram = null,
        liveTimeshiftSeconds = 0L,
        catchupStartMs = 0L,
        catchupStartProgressSec = 0.0,
    )

    /** 切换到直播模式（保留 originalChannel 以便退出回看按钮恢复） */
    fun switchToLive(): PlaybackState = copy(mode = PlayMode.LIVE)

    /** 切换到时移模式（保留 catchupProgram 和 originalChannel） */
    fun switchToTimeshift(offsetSec: Long): PlaybackState = copy(
        mode = PlayMode.TIMESHIFT,
        liveTimeshiftSeconds = offsetSec,
        catchupStartMs = System.currentTimeMillis(),
        catchupStartProgressSec = 0.0,
    )
}
