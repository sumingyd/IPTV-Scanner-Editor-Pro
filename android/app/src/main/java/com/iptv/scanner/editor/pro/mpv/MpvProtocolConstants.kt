package com.iptv.scanner.editor.pro.mpv

/**
 * MPV 协议相关常量。
 *
 * 统一管理 user-agent、超时、缓冲区大小等硬编码值。
 */
object MpvProtocolConstants {
    const val USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

    const val FCC_USER_AGENT = "VLC/3.0.18Libmpv"

    const val RW_TIMEOUT_MS = 30_000_000

    const val DEMUXER_MAX_BYTES_4K = "128MiB"
    const val DEMUXER_MAX_BYTES_DEFAULT = "48MiB"
    const val DEMUXER_MAX_BYTES_HIGH = "16MiB"
}