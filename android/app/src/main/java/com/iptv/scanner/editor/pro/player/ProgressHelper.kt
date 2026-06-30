package com.iptv.scanner.editor.pro.player

import com.iptv.scanner.editor.pro.data.IptvChannel
import com.iptv.scanner.editor.pro.data.IptvEpgProgram
import java.util.Calendar
import java.util.Locale

/**
 * 进度条计算工具：与 PC 端 [controllers/progress_controller.py] 的 update_progress 对齐。
 *
 * 4 种分支判断顺序（不可颠倒）：
 * 1. catchup（非 timeshift）→ 基于 mpv timePos（实际播放位置）
 * 2. timeshift → 基于 now - timeshift - program_start（墙钟时间偏移）
 * 3. live+EPG → 基于 now - program_start（墙钟时间）
 * 4. VOD（仅本地文件 + duration<86400）→ 基于 mpv timePos/duration
 * 5. live 无 EPG → 整点区间，基于当前分钟秒
 *
 * 关键注意：
 * - VOD 判断必须包含 isLocal 检查，避免 HLS 直播流（有 duration）被误判为 VOD
 * - catchup 必须基于 mpv timePos，因为回看节目已结束（now > endTs），用墙钟时间会 clamp 到 100%
 * - timeshift 基于墙钟偏移：elapsed = now - startTs - liveTimeshiftSeconds
 */
object ProgressHelper {

    /**
     * 进度条计算结果。
     *
     * @param percent 进度百分比（0-100）
     * @param startLabel 左侧时间标签（如 "20:00"）
     * @param endLabel 右侧时间标签（如 "21:00"）
     * @param mode 进度条模式（用于 UI 调试和样式区分）
     * @param totalSec 总时长（秒，用于 seek 计算）
     * @param currentSec 当前位置（秒，用于 seek 计算）
     */
    data class ProgressInfo(
        val percent: Float,
        val startLabel: String,
        val endLabel: String,
        val mode: ProgressMode,
        val totalSec: Long,
        val currentSec: Long,
    )

    enum class ProgressMode {
        CATCHUP,       // 回看模式
        TIMESHIFT_EPG, // 时移+EPG
        TIMESHIFT_LIVE,// 时移但无 EPG（整点区间）
        LIVE_EPG,      // 直播+EPG
        VOD,           // 本地文件 VOD
        LIVE_HOURLY,   // 直播无 EPG（整点区间）
    }

    /** 占位结果（无播放时） */
    private val EMPTY = ProgressInfo(0f, "--:--", "--:--", ProgressMode.LIVE_HOURLY, 0L, 0L)

    /**
     * 计算当前进度条信息。
     *
     * @param state 当前 PlaybackState
     * @param channel 当前频道（用于判断 isLocal 和 catchup 支持）
     * @param currentProgram 当前 EPG 节目（可能为 null）
     * @param mpvTimePos mpv 当前播放位置（秒）
     * @param mpvDuration mpv 总时长（秒）
     * @return ProgressInfo
     */
    fun computeProgress(
        state: PlaybackState,
        channel: IptvChannel?,
        currentProgram: IptvEpgProgram?,
        mpvTimePos: Double,
        mpvDuration: Double,
    ): ProgressInfo {
        if (channel == null) return EMPTY

        val nowMs = System.currentTimeMillis()

        // 分支 1：回看模式（catchup 但非 timeshift）
        if (state.mode.isCatchup && !state.mode.isTimeshift) {
            return computeCatchupProgress(state, mpvTimePos)
        }

        // 分支 2：时移模式
        if (state.mode.isTimeshift) {
            return computeTimeshiftProgress(state, currentProgram, nowMs)
        }

        // 分支 3：直播 + EPG（优先于 VOD 判断）
        if (currentProgram != null) {
            val (startMs, endMs) = extractProgramTs(currentProgram)
            if (startMs > 0 && endMs > startMs) {
                return computeLiveEpgProgress(startMs, endMs, state.liveTimeshiftSeconds, nowMs)
            }
        }

        // 分支 4：VOD 模式（仅本地文件 + duration>0 + duration<86400）
        val isLocal = isLocalFile(channel.url)
        if (isLocal && mpvDuration > 0 && mpvDuration < 86400) {
            return computeVodProgress(mpvTimePos, mpvDuration)
        }

        // 分支 5：直播无 EPG（默认）
        return computeLiveHourlyProgress(state.liveTimeshiftSeconds, nowMs)
    }

    // -----------------------------------------------------------------
    // 各分支实现
    // -----------------------------------------------------------------

    /** 分支 1：回看模式进度（基于 mpv timePos） */
    private fun computeCatchupProgress(state: PlaybackState, mpvTimePos: Double): ProgressInfo {
        val program = state.catchupProgram ?: return EMPTY
        val totalSec = program.durationSec
        if (totalSec <= 0) return EMPTY

        // 回看基于 mpv 播放位置
        val elapsedSec = mpvTimePos.toLong().coerceIn(0L, totalSec)
        val percent = (elapsedSec.toFloat() / totalSec.toFloat() * 100f).coerceIn(0f, 100f)

        return ProgressInfo(
            percent = percent,
            startLabel = formatHM(program.startMs),
            endLabel = formatHM(program.endMs),
            mode = ProgressMode.CATCHUP,
            totalSec = totalSec,
            currentSec = elapsedSec,
        )
    }

    /** 分支 2：时移模式进度（基于墙钟时间偏移） */
    private fun computeTimeshiftProgress(
        state: PlaybackState,
        currentProgram: IptvEpgProgram?,
        nowMs: Long,
    ): ProgressInfo {
        // 时移但无 EPG：整点区间
        if (currentProgram == null && state.catchupProgram == null) {
            return computeLiveHourlyProgress(state.liveTimeshiftSeconds, nowMs)
        }

        // 时移 + EPG/program：基于 now - timeshift - start
        val program = state.catchupProgram
        val (startMs, endMs) = if (program != null) {
            program.startMs to program.endMs
        } else {
            extractProgramTs(currentProgram!!)
        }

        if (startMs <= 0 || endMs <= startMs) return EMPTY

        val totalSec = ((endMs - startMs) / 1000).coerceAtLeast(1L)
        val nowSec = nowMs / 1000
        val startSec = startMs / 1000
        val elapsedSec: Long = if (state.liveTimeshiftSeconds > 0) {
            // 时移偏移：elapsed = now - start - timeshift
            (nowSec - startSec - state.liveTimeshiftSeconds).coerceIn(0L, totalSec)
        } else {
            // 无偏移：直接用墙钟时间
            (nowSec - startSec).coerceIn(0L, totalSec)
        }
        val percent = (elapsedSec.toFloat() / totalSec.toFloat() * 100f).coerceIn(0f, 100f)

        return ProgressInfo(
            percent = percent,
            startLabel = formatHM(startMs),
            endLabel = formatHM(endMs),
            mode = ProgressMode.TIMESHIFT_EPG,
            totalSec = totalSec,
            currentSec = elapsedSec,
        )
    }

    /** 分支 3：直播 + EPG 进度（基于墙钟时间） */
    private fun computeLiveEpgProgress(
        startMs: Long,
        endMs: Long,
        liveTimeshiftSeconds: Long,
        nowMs: Long,
    ): ProgressInfo {
        val totalSec = ((endMs - startMs) / 1000).coerceAtLeast(1L)
        val nowSec = nowMs / 1000
        val startSec = startMs / 1000

        val elapsedSec: Long = if (liveTimeshiftSeconds > 0) {
            (nowSec - startSec - liveTimeshiftSeconds).coerceIn(0L, totalSec)
        } else {
            (nowSec - startSec).coerceIn(0L, totalSec)
        }
        val percent = (elapsedSec.toFloat() / totalSec.toFloat() * 100f).coerceIn(0f, 100f)

        return ProgressInfo(
            percent = percent,
            startLabel = formatHM(startMs),
            endLabel = formatHM(endMs),
            mode = ProgressMode.LIVE_EPG,
            totalSec = totalSec,
            currentSec = elapsedSec,
        )
    }

    /** 分支 4：VOD 进度（基于 mpv timePos/duration） */
    private fun computeVodProgress(mpvTimePos: Double, mpvDuration: Double): ProgressInfo {
        val totalSec = mpvDuration.toLong()
        val currentSec = mpvTimePos.toLong().coerceIn(0L, totalSec)
        val percent = if (totalSec > 0) {
            (currentSec.toFloat() / totalSec.toFloat() * 100f).coerceIn(0f, 100f)
        } else {
            0f
        }
        return ProgressInfo(
            percent = percent,
            startLabel = formatTime(currentSec),
            endLabel = formatTime(totalSec),
            mode = ProgressMode.VOD,
            totalSec = totalSec,
            currentSec = currentSec,
        )
    }

    /** 分支 5：直播无 EPG 进度（整点区间） */
    private fun computeLiveHourlyProgress(liveTimeshiftSeconds: Long, nowMs: Long): ProgressInfo {
        val cal = Calendar.getInstance().apply {
            timeInMillis = nowMs
            // 时移偏移：effective_time = now - timeshift
            if (liveTimeshiftSeconds > 0) {
                add(Calendar.SECOND, -liveTimeshiftSeconds.toInt())
            }
        }
        val hourStart = (cal.clone() as Calendar).apply {
            set(Calendar.MINUTE, 0)
            set(Calendar.SECOND, 0)
            set(Calendar.MILLISECOND, 0)
        }
        val hourEnd = (hourStart.clone() as Calendar).apply {
            add(Calendar.HOUR_OF_DAY, 1)
        }

        val totalSec = 3600L
        val currentSec = (cal.get(Calendar.MINUTE) * 60 + cal.get(Calendar.SECOND)).toLong()
        val percent = (currentSec.toFloat() / totalSec.toFloat() * 100f).coerceIn(0f, 100f)

        return ProgressInfo(
            percent = percent,
            startLabel = formatHM(hourStart.timeInMillis),
            endLabel = formatHM(hourEnd.timeInMillis),
            mode = ProgressMode.LIVE_HOURLY,
            totalSec = totalSec,
            currentSec = currentSec,
        )
    }

    // -----------------------------------------------------------------
    // 缓冲边界判断（用于 seek 时决定 mpv seek 还是重建 URL）
    // -----------------------------------------------------------------

    /**
     * 判断目标位置是否在缓冲区内（用于进度条 seek）。
     *
     * mpv 缓冲相关属性：
     * - demuxer-cache-duration：未播放的缓冲时长（当前位置到缓冲区末尾）
     * - demuxer-cache-time：已播放但仍在缓冲区中的最早时间点（绝对 mpv 时间）
     *
     * 缓冲区范围：[cacheTime, mpvTimePos + cacheDuration]
     *
     * @param mpvTimePos mpv 当前位置（秒）
     * @param cacheDuration mpv 未来缓冲时长（秒，demuxer-cache-duration）
     * @param cacheTime mpv 过去缓冲最早时间（秒，demuxer-cache-time），0 表示未知
     * @param targetPos 目标位置（秒，mpv 流位置）
     * @return true 表示在缓冲区内，可直接 mpv seek；false 表示需要重建 URL
     */
    fun isInBufferRange(mpvTimePos: Double, cacheDuration: Double, cacheTime: Double, targetPos: Double): Boolean {
        if (cacheDuration < 2.0) return false  // 未来缓冲不足
        val bufferEnd = mpvTimePos + cacheDuration + 5.0  // 未来缓冲末尾（+5s 容差）
        val bufferStart = if (cacheTime > 0) cacheTime else (mpvTimePos - 30.0).coerceAtLeast(0.0)  // 过去缓冲
        return targetPos in bufferStart..bufferEnd
    }

    /**
     * 计算 seek 目标位置（mpv 流位置，秒）。
     * 用于直播进度条 seek。
     *
     * @param offsetSec 偏移秒数（now - targetWallclock）
     * @param mpvTimePos mpv 当前位置（秒）
     * @param cacheDuration mpv 未来缓冲时长（秒）
     * @param cacheTime mpv 过去缓冲最早时间（秒），0 表示未知
     * @return Pair<targetPos, inBuffer>，targetPos 是 mpv 流位置，inBuffer 表示是否在缓冲内
     */
    fun computeSeekTarget(
        offsetSec: Long,
        mpvTimePos: Double,
        cacheDuration: Double,
        cacheTime: Double = 0.0,
    ): Pair<Double, Boolean> {
        val targetPos = (mpvTimePos - offsetSec).coerceAtLeast(0.0)
        val inBuffer = isInBufferRange(mpvTimePos, cacheDuration, cacheTime, targetPos)
        return targetPos to inBuffer
    }

    // -----------------------------------------------------------------
    // 工具函数
    // -----------------------------------------------------------------

    /** 判断是否为本地文件（非 http/https/rtp/udp/rtsp 协议） */
    fun isLocalFile(url: String): Boolean {
        if (url.isEmpty()) return false
        val lower = url.lowercase(Locale.US)
        return !lower.startsWith("http://") &&
                !lower.startsWith("https://") &&
                !lower.startsWith("rtp://") &&
                !lower.startsWith("udp://") &&
                !lower.startsWith("rtsp://")
    }

    /** 从 EPG 节目提取时间戳（毫秒），优先用 start_ts/stop_ts */
    private fun extractProgramTs(program: IptvEpgProgram): Pair<Long, Long> {
        val startMs = if (program.startTs > 0) {
            program.startTs * 1000L
        } else {
            parseIsoToMs(program.start)
        }
        val endMs = if (program.stopTs > 0) {
            program.stopTs * 1000L
        } else if (program.end.isNotEmpty()) {
            parseIsoToMs(program.end)
        } else {
            parseIsoToMs(program.stop)
        }
        return startMs to endMs
    }

    private fun parseIsoToMs(iso: String): Long {
        if (iso.isEmpty()) return 0
        val patterns = listOf(
            "yyyy-MM-dd'T'HH:mm:ssXXX",
            "yyyy-MM-dd'T'HH:mm:ss'Z'",
            "yyyy-MM-dd'T'HH:mm:ss",
            "yyyy-MM-dd HH:mm:ss",
            "yyyy-MM-dd HH:mm",
        )
        for (pattern in patterns) {
            try {
                val sdf = java.text.SimpleDateFormat(pattern, Locale.US)
                return sdf.parse(iso)?.time ?: continue
            } catch (_: Exception) {
                // 尝试下一个格式
            }
        }
        return iso.toLongOrNull()?.let { if (it > 1_000_000_000_000L) it else it * 1000 } ?: 0
    }

    /** 格式化 HH:MM */
    private fun formatHM(tsMs: Long): String {
        if (tsMs <= 0) return "--:--"
        val cal = Calendar.getInstance().apply { timeInMillis = tsMs }
        return String.format(Locale.US, "%02d:%02d", cal.get(Calendar.HOUR_OF_DAY), cal.get(Calendar.MINUTE))
    }

    /** 格式化时间（秒 → M:SS 或 H:MM:SS） */
    fun formatTime(seconds: Long): String {
        if (seconds <= 0) return "00:00"
        val total = seconds
        val h = total / 3600
        val m = (total % 3600) / 60
        val s = total % 60
        return if (h > 0) String.format(Locale.US, "%02d:%02d:%02d", h, m, s)
        else String.format(Locale.US, "%02d:%02d", m, s)
    }

    /**
     * 从 EPG 列表中查找当前正在播放的节目。
     * @param programs EPG 节目列表
     * @param nowMs 当前时间戳（毫秒）
     * @return 当前节目，或 null
     */
    fun findCurrentProgram(programs: List<IptvEpgProgram>, nowMs: Long): IptvEpgProgram? {
        val nowSec = nowMs / 1000
        return programs.firstOrNull { p ->
            val startSec = if (p.startTs > 0) p.startTs else (parseIsoToMs(p.start) / 1000)
            val endSec = if (p.stopTs > 0) p.stopTs else (parseIsoToMs(if (p.end.isNotEmpty()) p.end else p.stop) / 1000)
            startSec > 0 && endSec > startSec && nowSec >= startSec && nowSec < endSec
        }
    }
}
