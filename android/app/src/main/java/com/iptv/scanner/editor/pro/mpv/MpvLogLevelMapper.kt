package com.iptv.scanner.editor.pro.mpv

/**
 * mpv 日志等级映射工具。
 *
 * 将用户可配置的日志等级（debug/info/warn/error）映射为 mpv msg-level 值。
 */
object MpvLogLevelMapper {
    fun toMpvValue(level: String): String = when (level) {
        "debug" -> "all=trace"
        "info" -> "all=info"
        "warn" -> "all=warn"
        "error" -> "all=error"
        else -> "all=info"
    }
}