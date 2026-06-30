package com.iptv.scanner.editor.pro.player

import android.util.Log
import com.iptv.scanner.editor.pro.data.IptvChannel
import java.text.SimpleDateFormat
import java.util.Calendar
import java.util.Date
import java.util.Locale
import java.util.TimeZone

/**
 * Catchup URL 构建工具：与 PC 端 [controllers/catchup_controller.py] 和
 * mobile [server/mobile/index.html] 的 catchup 逻辑完全对齐。
 *
 * 支持的 catchup 类型（与 PC 端 CATCHUP_TYPES 一致）：
 * - default / '' / vod / timemachine：直接返回 catchup_source 或 live_url
 * - append：live_url + sep + catchup_source（自动选 ? 或 &）
 * - flussonic / fs：catchup_source 或 `{live_url}/{ts_start}-{ts_end}.m3u8`
 * - xc / xtream：catchup_source 或 `{live_url}{sep}start={ts_start}&end={ts_end}&duration={dur}`
 * - shift：catchup_source 或 `{live_url}{sep}timeshift={offset}`
 * - pltv：catchup_source 或将 /PLTV/ 替换为 /TVOD/ 并追加 ?playseek={start}-{end}
 *
 * 模板变量（与 PC 端 replace_catchup_variables 对齐）：
 * - `${(b)fmt}` / `${(e)fmt}` / `${(start)fmt}` / `${(end)fmt}`：花括号带前缀变量
 * - `${start}` / `${end}` / `${timestamp}` / `${start_utc}` / `${end_utc}` / `${start_ms}` / `${end_ms}`
 * - `${offset}` / `${duration}` / `${duration_ms}`
 * - `{start}` / `{end}` / `{timestamp}` / `{offset}`：无 $ 简单变量
 * - `${start_year}` ... `${end_second}`：日期组件
 *
 * fmt 支持的时区后缀：`|utc` / `|local` / `|+HH:MM` / `|-HH:MM`
 * fmt 支持的格式：yyyyMMddHHmmss / yyyyMMddHHmm / yyyyMMdd / HHmmss / HHmm
 *   / yyyy-MM-dd / yyyy-MM-ddTHH:mm:ss / yyyy-MM-dd HH:mm:ss / yyyy / yy / MM / dd / HH / mm / ss
 *   / unix / unix_ms / 10 / 13
 */
object CatchupHelper {

    private const val TAG = "CatchupHelper"

    /**
     * 构建 catchup URL。返回 null 表示该频道不支持回看。
     *
     * @param channel 频道（含 catchup / catchup_source / url）
     * @param startMs 节目开始时间戳（毫秒）
     * @param endMs 节目结束时间戳（毫秒）
     * @return catchup URL，或 null 表示不支持
     */
    fun buildCatchupUrl(channel: IptvChannel, startMs: Long, endMs: Long): String? {
        val liveUrl = channel.url.ifEmpty { return null }
        val catchupType = channel.catchup.trim().lowercase(Locale.US)
        val catchupSource = channel.catchupSource.trim()

        // Fallback：catchup 和 catchup_source 都为空时，尝试从 URL 检测 PLTV/SNM 模式
        val effectiveType: String
        val effectiveSource: String
        if (catchupSource.isEmpty() && catchupType.isEmpty()) {
            val detected = detectCatchupPattern(liveUrl)
            if (detected == null) {
                Log.d(TAG, "Channel ${channel.name} not catchup-enabled")
                return null
            }
            effectiveType = detected
            effectiveSource = ""  // 检测到的类型由 buildXxxUrl 内部生成
        } else {
            effectiveType = catchupType
            effectiveSource = catchupSource
        }

        return when (effectiveType) {
            "append" -> buildAppendUrl(liveUrl, effectiveSource, startMs, endMs)
            "flussonic", "fs" -> buildFlussonicUrl(liveUrl, effectiveSource, startMs, endMs)
            "xc", "xtream" -> buildXcUrl(liveUrl, effectiveSource, startMs, endMs)
            "shift" -> buildShiftUrl(liveUrl, effectiveSource, startMs, endMs)
            "pltv" -> buildPltvUrl(liveUrl, effectiveSource, startMs, endMs)
            "default", "vod", "timemachine", "" -> {
                // 直接返回 catchup_source（已替换变量），或回退到 live_url
                if (effectiveSource.isNotEmpty()) {
                    replaceCatchupVariables(effectiveSource, startMs, endMs)
                } else {
                    liveUrl
                }
            }
            else -> {
                // 未知类型，尝试直接用 catchup_source
                if (effectiveSource.isNotEmpty()) {
                    replaceCatchupVariables(effectiveSource, startMs, endMs)
                } else {
                    Log.w(TAG, "Unknown catchup type '$effectiveType' and no catchup_source")
                    null
                }
            }
        }
    }

    /**
     * 检测 URL 是否包含 PLTV/SNM 模式（与 PC 端 m3u_parser.detect_catchup_pattern 对齐）。
     * 返回检测到的 catchup 类型，或 null 表示不支持。
     */
    fun detectCatchupPattern(url: String): String? {
        if (url.isEmpty()) return null
        // PLTV/.../TVOD 或 PLTV 模式
        if (url.contains("/PLTV/") || url.contains("PLTV")) return "pltv"
        // SNM 模式（部分运营商）
        if (url.contains("/SNM/")) return "shift"
        // 默认：含 catchup-source 的频道已在外部处理
        return null
    }

    /** 判断频道是否支持回看（catchup_source/catchup/detectCatchupPattern 任一存在） */
    fun isCatchupEnabled(channel: IptvChannel): Boolean {
        if (channel.catchupSource.trim().isNotEmpty()) return true
        if (channel.catchup.trim().isNotEmpty()) return true
        return detectCatchupPattern(channel.url) != null
    }

    // -----------------------------------------------------------------
    // 各类型 URL 构建实现
    // -----------------------------------------------------------------

    private fun buildAppendUrl(liveUrl: String, source: String, startMs: Long, endMs: Long): String? {
        val replaced = if (source.isNotEmpty()) replaceCatchupVariables(source, startMs, endMs) else ""
        val sep = if (liveUrl.contains('?')) "&" else "?"
        return if (replaced.isNotEmpty()) "$liveUrl$sep$replaced" else null
    }

    private fun buildFlussonicUrl(liveUrl: String, source: String, startMs: Long, endMs: Long): String? {
        if (source.isNotEmpty()) return replaceCatchupVariables(source, startMs, endMs)
        // 默认格式：{live_url}/{ts_start}-{ts_end}.m3u8（unix 秒）
        val startSec = startMs / 1000
        val endSec = endMs / 1000
        return "$liveUrl/$startSec-$endSec.m3u8"
    }

    private fun buildXcUrl(liveUrl: String, source: String, startMs: Long, endMs: Long): String? {
        if (source.isNotEmpty()) return replaceCatchupVariables(source, startMs, endMs)
        val startSec = startMs / 1000
        val endSec = endMs / 1000
        val duration = (endSec - startSec).coerceAtLeast(0L)
        val sep = if (liveUrl.contains('?')) "&" else "?"
        return "$liveUrl${sep}start=$startSec&end=$endSec&duration=$duration"
    }

    private fun buildShiftUrl(liveUrl: String, source: String, startMs: Long, endMs: Long): String? {
        if (source.isNotEmpty()) return replaceCatchupVariables(source, startMs, endMs)
        // 时移偏移量（秒，从节目开始到现在）
        val now = System.currentTimeMillis()
        val offset = ((now - startMs) / 1000).coerceAtLeast(0L)
        val sep = if (liveUrl.contains('?')) "&" else "?"
        return "$liveUrl${sep}timeshift=$offset"
    }

    private fun buildPltvUrl(liveUrl: String, source: String, startMs: Long, endMs: Long): String? {
        if (source.isNotEmpty()) return replaceCatchupVariables(source, startMs, endMs)
        // 将 /PLTV/ 替换为 /TVOD/，追加 ?playseek={start}-{end}（yyyyMMddHHmmss 格式）
        val tvodUrl = liveUrl.replace("/PLTV/", "/TVOD/")
        val fmt = SimpleDateFormat("yyyyMMddHHmmss", Locale.US).apply {
            timeZone = TimeZone.getTimeZone("UTC")
        }
        val startStr = fmt.format(Date(startMs))
        val endStr = fmt.format(Date(endMs))
        val sep = if (tvodUrl.contains('?')) "&" else "?"
        return "$tvodUrl${sep}playseek=$startStr-$endStr"
    }

    // -----------------------------------------------------------------
    // 模板变量替换（与 PC 端 replace_catchup_variables 对齐）
    // -----------------------------------------------------------------

    /**
     * 替换 catchup URL 中的模板变量。
     *
     * 支持的变量格式：
     * - `${(b|e|start|end)fmt}`：花括号带前缀，fmt 可带时区后缀 `|utc|local|+HH:MM|-HH:MM`
     * - `${name}`：简单变量（start/end/timestamp/start_utc/end_utc/start_ms/end_ms/offset/duration/duration_ms）
     * - `${start_year}` / `${end_month}` 等：日期组件
     * - `{start}` / `{end}` / `{timestamp}` / `{offset}`：无 $ 简单变量
     */
    fun replaceCatchupVariables(url: String, startMs: Long, endMs: Long): String {
        if (url.isEmpty()) return url
        val now = System.currentTimeMillis()
        val offsetSec = ((now - startMs) / 1000).coerceAtLeast(0L)
        val durationSec = ((endMs - startMs) / 1000).coerceAtLeast(0L)

        var result = url

        // 1. 花括号带前缀变量：${(b|e|start|end)fmt} 或 ${(b|e|start|end)}
        val prefixedPattern = Regex("""\$\{(b|e|start|end)(?:\}|([^}]*))\}""")
        result = prefixedPattern.replace(result) { m ->
            val prefix = m.groupValues[1]
            val fmt = m.groupValues[2].ifEmpty { "" }
            val ts = when (prefix) {
                "b", "start" -> startMs
                "e", "end" -> endMs
                else -> startMs
            }
            formatCatchupTime(ts, fmt)
        }

        // 2. 简单变量：${name}
        val simplePattern = Regex("""\$\{(\w+)\}""")
        result = simplePattern.replace(result) { m ->
            val name = m.groupValues[1]
            when (name) {
                "start" -> (startMs / 1000).toString()
                "end" -> (endMs / 1000).toString()
                "timestamp" -> (now / 1000).toString()
                "start_utc" -> (startMs / 1000).toString()
                "end_utc" -> (endMs / 1000).toString()
                "start_ms" -> startMs.toString()
                "end_ms" -> endMs.toString()
                "offset" -> offsetSec.toString()
                "duration" -> durationSec.toString()
                "duration_ms" -> (durationSec * 1000).toString()
                // 日期组件
                "start_year" -> formatDateComponent(startMs, "yyyy")
                "start_month" -> formatDateComponent(startMs, "MM")
                "start_day" -> formatDateComponent(startMs, "dd")
                "start_hour" -> formatDateComponent(startMs, "HH")
                "start_minute" -> formatDateComponent(startMs, "mm")
                "start_second" -> formatDateComponent(startMs, "ss")
                "end_year" -> formatDateComponent(endMs, "yyyy")
                "end_month" -> formatDateComponent(endMs, "MM")
                "end_day" -> formatDateComponent(endMs, "dd")
                "end_hour" -> formatDateComponent(endMs, "HH")
                "end_minute" -> formatDateComponent(endMs, "mm")
                "end_second" -> formatDateComponent(endMs, "ss")
                else -> m.value  // 未知变量，保留原样
            }
        }

        // 3. 无 $ 简单变量：{start} / {end} / {timestamp} / {offset}
        val noDollarPattern = Regex("""\{(start|end|timestamp|offset)\}""")
        result = noDollarPattern.replace(result) { m ->
            when (m.groupValues[1]) {
                "start" -> (startMs / 1000).toString()
                "end" -> (endMs / 1000).toString()
                "timestamp" -> (now / 1000).toString()
                "offset" -> offsetSec.toString()
                else -> m.value
            }
        }

        return result
    }

    /**
     * 格式化 catchup 时间。与 PC 端 format_catchup_time 对齐。
     *
     * @param tsMs 时间戳（毫秒）
     * @param fmt 格式字符串，可能含时区后缀 `|utc|local|+HH:MM|-HH:MM`
     *   - 支持的格式：yyyyMMddHHmmss / yyyyMMddHHmm / yyyyMMdd / HHmmss / HHmm
     *     / yyyy-MM-dd / yyyy-MM-ddTHH:mm:ss / yyyy-MM-dd HH:mm:ss / yyyy / yy / MM / dd / HH / mm / ss
     *   - unix / unix_ms / 10 / 13：返回 unix 时间戳（秒/毫秒）
     *   - 空字符串：默认 yyyyMMddHHmmss
     */
    fun formatCatchupTime(tsMs: Long, fmt: String): String {
        if (fmt.isEmpty()) {
            // 默认格式：UTC yyyyMMddHHmmss
            return SimpleDateFormat("yyyyMMddHHmmss", Locale.US)
                .apply { timeZone = TimeZone.getTimeZone("UTC") }
                .format(Date(tsMs))
        }

        // 解析时区后缀
        val (formatPart, tzPart) = if (fmt.contains("|")) {
            val idx = fmt.lastIndexOf('|')
            fmt.substring(0, idx) to fmt.substring(idx + 1)
        } else {
            fmt to ""
        }

        // unix 时间戳特殊处理
        when (formatPart) {
            "unix", "10" -> return (tsMs / 1000).toString()
            "unix_ms", "13" -> return tsMs.toString()
        }

        // 时区选择
        val tz = when {
            tzPart.isEmpty() || tzPart == "local" -> TimeZone.getDefault()
            tzPart == "utc" -> TimeZone.getTimeZone("UTC")
            tzPart.startsWith("+") || tzPart.startsWith("-") -> TimeZone.getTimeZone("GMT$tzPart")
            else -> TimeZone.getTimeZone(tzPart)
        }

        val pattern = when (formatPart) {
            "yyyyMMddHHmmss", "" -> "yyyyMMddHHmmss"
            "yyyyMMddHHmm" -> "yyyyMMddHHmm"
            "yyyyMMdd" -> "yyyyMMdd"
            "HHmmss" -> "HHmmss"
            "HHmm" -> "HHmm"
            "yyyy-MM-dd" -> "yyyy-MM-dd"
            "yyyy-MM-ddTHH:mm:ss" -> "yyyy-MM-dd'T'HH:mm:ss"
            "yyyy-MM-dd HH:mm:ss" -> "yyyy-MM-dd HH:mm:ss"
            "yyyy" -> "yyyy"
            "yy" -> "yy"
            "MM" -> "MM"
            "dd" -> "dd"
            "HH" -> "HH"
            "mm" -> "mm"
            "ss" -> "ss"
            else -> formatPart  // 自定义格式直接用
        }

        return SimpleDateFormat(pattern, Locale.US).apply { timeZone = tz }.format(Date(tsMs))
    }

    private fun formatDateComponent(tsMs: Long, pattern: String): String =
        SimpleDateFormat(pattern, Locale.US).format(Date(tsMs))

    // -----------------------------------------------------------------
    // EPG 节目时间戳提取（与 mobile index.html 对齐）
    // -----------------------------------------------------------------

    /**
     * 从 IptvEpgProgram 提取开始/结束时间戳（毫秒）。
     * 优先使用 start_ts/stop_ts，否则解析 start/stop ISO 字符串。
     * 返回 Pair<startMs, endMs>，任一为 0 表示无效。
     */
    fun extractProgramTimestamps(program: com.iptv.scanner.editor.pro.data.IptvEpgProgram): Pair<Long, Long> {
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

    /** 解析 ISO 时间字符串为毫秒时间戳，失败返回 0 */
    private fun parseIsoToMs(iso: String): Long {
        if (iso.isEmpty()) return 0
        // 尝试常见 ISO 格式
        val patterns = listOf(
            "yyyy-MM-dd'T'HH:mm:ssXXX",
            "yyyy-MM-dd'T'HH:mm:ssXXX'Z'",
            "yyyy-MM-dd'T'HH:mm:ss'Z'",
            "yyyy-MM-dd'T'HH:mm:ss",
            "yyyy-MM-dd HH:mm:ss",
            "yyyy-MM-dd HH:mm",
        )
        for (pattern in patterns) {
            try {
                val sdf = SimpleDateFormat(pattern, Locale.US)
                val date = sdf.parse(iso) ?: continue
                return date.time
            } catch (_: Exception) {
                // 尝试下一个格式
            }
        }
        // 尝试纯数字时间戳
        return iso.toLongOrNull()?.let { if (it > 1_000_000_000_000L) it else it * 1000 } ?: 0
    }

    /**
     * 计算时移 targetWallclock（用于 startLiveTimeshift）。
     * @param programStartMs 节目开始时间戳（毫秒）
     * @param hourStartMs 当前小时整点时间戳（毫秒，无 EPG 时使用）
     * @param sliderSec 进度条点击位置（秒）
     * @param hasEpg 是否有 EPG（决定用 programStart 还是 hourStart）
     * @return targetWallclockMs，已限制不超过 now-5s
     */
    fun computeTimeshiftTarget(programStartMs: Long, hourStartMs: Long, sliderSec: Double, hasEpg: Boolean): Long {
        val base = if (hasEpg && programStartMs > 0) programStartMs else hourStartMs
        val target = base + (sliderSec * 1000).toLong()
        val now = System.currentTimeMillis()
        // 不超过当前时间，留 5 秒余量
        return target.coerceAtMost(now - 5_000L)
    }

    /**
     * 计算当前小时整点时间戳（毫秒）。
     */
    fun currentHourStartMs(): Long {
        val cal = Calendar.getInstance()
        cal.set(Calendar.MINUTE, 0)
        cal.set(Calendar.SECOND, 0)
        cal.set(Calendar.MILLISECOND, 0)
        return cal.timeInMillis
    }
}
