package com.iptv.scanner.editor.pro.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/**
 * IPTV 数据模型。对应 android_bridge.py 中各入口函数返回的 JSON 结构。
 *
 * 设计要点：
 * - 所有类用 @Serializable，支持 kotlinx-serialization JSON 反序列化
 * - 字段命名与 Python 端保持一致（snake_case 转 camelCase 用 @SerialName 映射）
 * - 可空字段用 String?（Python 端可能返回 None）
 * - 默认值确保反序列化不失败
 */

// -----------------------------------------------------------------
// 状态与频道
// -----------------------------------------------------------------

@Serializable
data class IptvStatus(
    @SerialName("inited") val inited: Boolean = false,
    @SerialName("channels_total") val channelsTotal: Int = 0,
    @SerialName("source_loading") val sourceLoading: Boolean = false,
    @SerialName("source_message") val sourceMessage: String = "",
)

@Serializable
data class IptvChannel(
    @SerialName("id") val id: Int = 0,
    @SerialName("name") val name: String = "",
    @SerialName("url") val url: String = "",
    @SerialName("group") val group: String = "",
    @SerialName("logo") val logo: String = "",
    @SerialName("tvg_id") val tvgId: String = "",
    @SerialName("tvg_name") val tvgName: String = "",
    @SerialName("tvg_chno") val tvgChno: String = "",
    @SerialName("tvg_shift") val tvgShift: String = "",
    @SerialName("catchup") val catchup: String = "",
    @SerialName("catchup_days") val catchupDays: String = "",
    @SerialName("catchup_source") val catchupSource: String = "",
    @SerialName("catchup_correction") val catchupCorrection: String = "",
    @SerialName("fcc") val fcc: String = "",
    @SerialName("resolution") val resolution: String = "",
    /** valid: True=有效, False=无效, null=未检测 */
    @SerialName("valid") val valid: Boolean? = null,
    @SerialName("status") val status: String = "待检测",
)

@Serializable
data class IptvChannelsPage(
    @SerialName("total") val total: Int = 0,
    @SerialName("page") val page: Int = 1,
    @SerialName("size") val size: Int = 100,
    @SerialName("channels") val channels: List<IptvChannel> = emptyList(),
)

@Serializable
data class IptvGroup(
    @SerialName("name") val name: String = "",
    @SerialName("count") val count: Int = 0,
)

// -----------------------------------------------------------------
// 订阅源
// -----------------------------------------------------------------

@Serializable
data class IptvSource(
    @SerialName("url") val url: String = "",
    @SerialName("name") val name: String = "",
    @SerialName("enabled") val enabled: Boolean = true,
    @SerialName("last_update") val lastUpdate: String? = null,
)

@Serializable
data class IptvEpgSource(
    @SerialName("url") val url: String = "",
    @SerialName("name") val name: String = "",
    @SerialName("last_update") val lastUpdate: String? = null,
)

@Serializable
data class IptvSourceStatus(
    @SerialName("loading") val loading: Boolean = false,
    @SerialName("message") val message: String = "",
    @SerialName("channels_total") val channelsTotal: Int = 0,
)

// -----------------------------------------------------------------
// EPG
// -----------------------------------------------------------------

@Serializable
data class IptvEpgProgram(
    @SerialName("title") val title: String = "",
    @SerialName("desc") val desc: String = "",
    @SerialName("start") val start: String = "",
    /** XMLTV 标准用 stop，部分接口用 end，两者都接受 */
    @SerialName("stop") val stop: String = "",
    @SerialName("end") val end: String = "",
    @SerialName("start_ts") val startTs: Long = 0,
    @SerialName("stop_ts") val stopTs: Long = 0,
)

@Serializable
data class IptvEpgList(
    @SerialName("programmes") val programmes: List<IptvEpgProgram> = emptyList(),
    @SerialName("matched") val matched: Boolean = false,
)

@Serializable
data class IptvEpgStatus(
    @SerialName("has_epg_data") val hasEpgData: Boolean = false,
    @SerialName("channel_count") val channelCount: Int = 0,
    @SerialName("program_count") val programCount: Int = 0,
)

// -----------------------------------------------------------------
// 扫描
// -----------------------------------------------------------------

@Serializable
data class ScanStatus(
    @SerialName("running") val running: Boolean = false,
    @SerialName("total") val total: Int = 0,
    @SerialName("valid") val valid: Int = 0,
    @SerialName("invalid") val invalid: Int = 0,
    @SerialName("scanned") val scanned: Int = 0,
    @SerialName("message") val message: String = "",
    /** 'subscription' 或 'range' 或 null */
    @SerialName("mode") val mode: String? = null,
)

@Serializable
data class ScanResult(
    @SerialName("url") val url: String = "",
    @SerialName("name") val name: String = "",
    @SerialName("valid") val valid: Boolean = false,
    @SerialName("status") val status: String = "",
    @SerialName("latency") val latency: Int = 0,
    @SerialName("group") val group: String = "",
)

// -----------------------------------------------------------------
// 频道映射
// -----------------------------------------------------------------

@Serializable
data class MappingEntry(
    @SerialName("unique_key") val uniqueKey: String = "",
    @SerialName("standard_name") val standardName: String = "",
    @SerialName("raw_name") val rawName: String = "",
    @SerialName("raw_names") val rawNames: List<String> = emptyList(),
    @SerialName("logo_url") val logoUrl: String? = null,
    @SerialName("group_name") val groupName: String? = null,
    @SerialName("tvg_id") val tvgId: String? = null,
    @SerialName("tvg_chno") val tvgChno: String? = null,
    @SerialName("tvg_shift") val tvgShift: String? = null,
    @SerialName("catchup") val catchup: String? = null,
    @SerialName("catchup_days") val catchupDays: String? = null,
    @SerialName("catchup_source") val catchupSource: String? = null,
    @SerialName("resolution") val resolution: String? = null,
)

// -----------------------------------------------------------------
// 字幕
// -----------------------------------------------------------------

@Serializable
data class SubtitleItem(
    @SerialName("source") val source: String = "",
    @SerialName("id") val id: String = "",
    @SerialName("file_name") val fileName: String = "",
    @SerialName("language") val language: String = "",
    @SerialName("language_id") val languageId: String = "",
    @SerialName("download_link") val downloadLink: String = "",
    @SerialName("zip_link") val zipLink: String = "",
    @SerialName("movie_name") val movieName: String = "",
    @SerialName("score") val score: Double = 0.0,
    @SerialName("rating") val rating: Double = 0.0,
    @SerialName("format") val format: String = "srt",
    @SerialName("encoding") val encoding: String = "UTF-8",
    @SerialName("title") val title: String = "",
    @SerialName("detail_url") val detailUrl: String = "",
    @SerialName("auto_download") val autoDownload: Boolean = false,
    @SerialName("bad") val bad: Boolean = false,
)

@Serializable
data class SubtitleSearchResponse(
    @SerialName("subtitles") val subtitles: List<SubtitleItem> = emptyList(),
    @SerialName("last_error") val lastError: String = "",
)

// -----------------------------------------------------------------
// 通用响应
// -----------------------------------------------------------------

@Serializable
data class OkResponse(
    @SerialName("ok") val ok: Boolean = false,
)

@Serializable
data class CountResponse(
    @SerialName("ok") val ok: Boolean = false,
    @SerialName("count") val count: Int = 0,
)

@Serializable
data class ImportedResponse(
    @SerialName("imported") val imported: Int = 0,
)

@Serializable
data class IdxResponse(
    @SerialName("idx") val idx: Int = 0,
)

@Serializable
data class StartedResponse(
    @SerialName("started") val started: Boolean = false,
)

@Serializable
data class PathResponse(
    @SerialName("path") val path: String = "",
)

@Serializable
data class ClearCacheResponse(
    @SerialName("ok") val ok: Boolean = false,
    @SerialName("deleted_count") val deletedCount: Int = 0,
)

@Serializable
data class M3uTextResponse(
    @SerialName("text") val text: String = "",
    @SerialName("count") val count: Int = 0,
)
