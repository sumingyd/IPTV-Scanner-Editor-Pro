package com.iptv.scanner.editor.pro.data

import android.content.Context
import android.content.SharedPreferences
import org.json.JSONArray
import org.json.JSONObject

/**
 * 用户偏好持久化：收藏 / 历史 / 队列。
 *
 * 与 PC 端 user_settings.json 和 Web storage（localStorage）对齐。
 * 使用 SharedPreferences + JSON 简单存储，避免引入 Room/DataStore 等重依赖。
 *
 * 存储 key：
 * - "favorites"：Set<Int>，收藏的频道 idx 列表
 * - "history"：List<Int>，最近播放的频道 idx（按时间倒序，最多 100）
 * - "queue"：List<Int>，播放队列
 * - "favorites_urls"：Set<String>，收藏的频道 URL 列表（URL 比 idx 更稳健）
 * - "history_urls"：List<String>，最近播放的频道 URL（按时间倒序，最多 100）
 * - "queue_urls"：List<String>，播放队列 URL
 *
 * 注意：频道 idx 在订阅源重载后可能失效。新增 URL 版本的存储作为补充，
 * idx 和 URL 双写，读取时优先用 URL 匹配，idx 作为快速路径。
 */
class UserPrefs private constructor() {

    private lateinit var prefs: SharedPreferences

    fun init(context: Context) {
        prefs = context.applicationContext.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
    }

    // -----------------------------------------------------------------
    // 收藏
    // -----------------------------------------------------------------

    fun getFavorites(): Set<Int> {
        val arr = prefs.getString(KEY_FAVORITES, "[]") ?: "[]"
        return parseIntArray(arr).toSet()
    }

    fun isFavorite(idx: Int): Boolean = getFavorites().contains(idx)

    fun toggleFavorite(idx: Int): Boolean {
        val cur = getFavorites().toMutableSet()
        val added = if (cur.contains(idx)) {
            cur.remove(idx)
            false
        } else {
            cur.add(idx)
            true
        }
        prefs.edit().putString(KEY_FAVORITES, JSONArray(cur.toList()).toString()).apply()
        return added
    }

    // -----------------------------------------------------------------
    // 历史
    // -----------------------------------------------------------------

    fun getHistory(): List<Int> {
        val arr = prefs.getString(KEY_HISTORY, "[]") ?: "[]"
        return parseIntArray(arr)
    }

    /** 添加到历史（去重后插入队首，最多 100 条） */
    fun addToHistory(idx: Int) {
        val cur = getHistory().toMutableList()
        cur.remove(idx)
        cur.add(0, idx)
        if (cur.size > MAX_HISTORY) {
            cur.subList(MAX_HISTORY, cur.size).clear()
        }
        prefs.edit().putString(KEY_HISTORY, JSONArray(cur).toString()).apply()
    }

    fun clearHistory() {
        prefs.edit().putString(KEY_HISTORY, "[]").apply()
    }

    // -----------------------------------------------------------------
    // 队列
    // -----------------------------------------------------------------

    fun getQueue(): List<Int> {
        val arr = prefs.getString(KEY_QUEUE, "[]") ?: "[]"
        return parseIntArray(arr)
    }

    fun addToQueue(idx: Int) {
        val cur = getQueue().toMutableList()
        if (!cur.contains(idx)) {
            cur.add(idx)
            prefs.edit().putString(KEY_QUEUE, JSONArray(cur).toString()).apply()
        }
    }

    fun removeFromQueue(idx: Int) {
        val cur = getQueue().toMutableList()
        cur.remove(idx)
        prefs.edit().putString(KEY_QUEUE, JSONArray(cur).toString()).apply()
    }

    fun clearQueue() {
        prefs.edit().putString(KEY_QUEUE, "[]").apply()
    }

    // -----------------------------------------------------------------
    // 上次播放频道（启动时恢复）
    // -----------------------------------------------------------------

    /** 获取上次播放频道的 URL（启动时按 URL 在频道列表中查找并恢复播放） */
    fun getLastChannelUrl(): String = prefs.getString(KEY_LAST_CHANNEL_URL, "") ?: ""

    /** 保存上次播放频道的 URL（playChannel 时调用） */
    fun setLastChannelUrl(url: String) {
        prefs.edit().putString(KEY_LAST_CHANNEL_URL, url).apply()
    }

    /** 启动时是否自动续播上次频道（默认开启） */
    fun isAutoResumeOnStart(): Boolean = prefs.getBoolean(KEY_AUTO_RESUME, DEFAULT_AUTO_RESUME)

    fun setAutoResumeOnStart(enabled: Boolean) {
        prefs.edit().putBoolean(KEY_AUTO_RESUME, enabled).apply()
    }

    // -----------------------------------------------------------------
    // 批量恢复（备份恢复时一次性写入，替代逐条 add）
    // -----------------------------------------------------------------

    fun setFavorites(favorites: Set<Int>) {
        prefs.edit().putString(KEY_FAVORITES, JSONArray(favorites.toList()).toString()).commit()
    }

    fun setHistory(history: List<Int>) {
        prefs.edit().putString(KEY_HISTORY, JSONArray(history).toString()).commit()
    }

    fun setQueue(queue: List<Int>) {
        prefs.edit().putString(KEY_QUEUE, JSONArray(queue).toString()).commit()
    }

    // -----------------------------------------------------------------
    // 播放器设置（vo / hwdec）
    //
    // 持久化用户选择的渲染后端和硬件解码模式。
    // - 同设备升级后保留用户选择
    // - 黑屏 fallback 成功后持久化结果，避免每次启动都黑屏 2 秒再探测
    // - 提供重置接口，用户可手动回到默认值重新探测
    //
    // 与 MPVView.DEFAULT_VO / DEFAULT_HWDEC 默认值对齐。
    // -----------------------------------------------------------------

    /** 获取持久化的 video output，默认 "gpu"（与 MPVView.DEFAULT_VO 一致） */
    fun getVo(): String = prefs.getString(KEY_VO, DEFAULT_VO_VALUE) ?: DEFAULT_VO_VALUE

    fun setVo(vo: String) {
        prefs.edit().putString(KEY_VO, vo).apply()
    }

    /** 获取持久化的 hwdec 模式，默认 "auto-copy"（与 MPVView.DEFAULT_HWDEC 一致） */
    fun getHwdec(): String =
        prefs.getString(KEY_HWDEC, DEFAULT_HWDEC_VALUE) ?: DEFAULT_HWDEC_VALUE

    fun setHwdec(hwdec: String) {
        prefs.edit().putString(KEY_HWDEC, hwdec).apply()
    }

    /**
     * 是否已确认该设备需要 vo fallback（黑屏检测曾触发过）。
     * - true：下次启动直接用持久化的 vo（跳过 2 秒黑屏探测）
     * - false：默认值，启动后正常走黑屏检测
     */
    fun isVoFallbackConfirmed(): Boolean = prefs.getBoolean(KEY_VO_FALLBACK, false)

    fun setVoFallbackConfirmed(confirmed: Boolean) {
        prefs.edit().putBoolean(KEY_VO_FALLBACK, confirmed).apply()
    }

    // -----------------------------------------------------------------
    // HDR 输出模式（与 PC 端 hdr_output_mode 对齐）
    //
    // 模式：auto / tonemap / passthrough / disable
    // 默认 disable（强制 SDR，与 PC 端默认值一致）
    // -----------------------------------------------------------------

    /** 获取 HDR 输出模式，默认 "disable" */
    fun getHdrMode(): String = prefs.getString(KEY_HDR_MODE, DEFAULT_HDR_MODE) ?: DEFAULT_HDR_MODE

    fun setHdrMode(mode: String) {
        prefs.edit().putString(KEY_HDR_MODE, mode).apply()
    }

    /** 获取 RTSP 传输协议，默认 "tcp"（更稳定），可选 "udp"（更低延迟但可能丢包） */
    fun getRtspTransport(): String = prefs.getString(KEY_RTSP_TRANSPORT, DEFAULT_RTSP_TRANSPORT) ?: DEFAULT_RTSP_TRANSPORT

    fun setRtspTransport(transport: String) {
        prefs.edit().putString(KEY_RTSP_TRANSPORT, transport).apply()
    }

    // -----------------------------------------------------------------
    // 反交错（deinterlace）
    //
    // 隔行扫描视频（如 1080i TV 流）会出现横线梳齿，开启反交错可消除。
    // mpv 的 deinterlace 属性只支持 yes/no，UI 层提供 "no"(关闭) / "auto"(自动) 两个选项，
    // "auto" 在下发到 mpv 时转换为 "yes"（mpv 会自动检测隔行内容并应用 yadif 滤镜）。
    // 与 PC 端 _load_playback_settings 的 'deinterlace': 'no' 默认值对齐。
    // -----------------------------------------------------------------

    /** 获取反交错设置，默认 "no"（关闭），可选 "auto"（自动检测隔行内容） */
    fun getDeinterlace(): String = prefs.getString(KEY_DEINTERLACE, DEFAULT_DEINTERLACE) ?: DEFAULT_DEINTERLACE

    fun setDeinterlace(value: String) {
        prefs.edit().putString(KEY_DEINTERLACE, value).apply()
    }

    /** 重置播放器设置为默认值（用户换设备或想重新探测时调用） */
    fun resetPlayerSettings() {
        prefs.edit()
            .remove(KEY_VO)
            .remove(KEY_HWDEC)
            .remove(KEY_VO_FALLBACK)
            .remove(KEY_PLAYER_TYPE)
            .remove(KEY_HDR_MODE)
            .remove(KEY_RTSP_TRANSPORT)
            .remove(KEY_DEINTERLACE)
            .remove(KEY_TIMEOUT_SWITCH_SOURCE)
            .remove(KEY_RECONNECT_INDEX)
            .remove(KEY_SCREEN_LOCK)
            .remove(KEY_SPEED_PARAMS)
            .apply()
    }

    // -----------------------------------------------------------------
    // 播放器类型（MPV / ExoPlayer 两内核可切换，每种都支持硬解/软解）
    // -----------------------------------------------------------------

    /**
     * 获取持久化的播放器类型名称。
     * - "MPV"：mpv 内核（默认，功能最完整）
     * - "EXO"：ExoPlayer 内核（HLS/DASH/RTSP 兼容性好）
     * - "SYSTEM"：旧版兼容映射，自动转为 "EXO"
     */
    fun getPlayerType(): String = prefs.getString(KEY_PLAYER_TYPE, DEFAULT_PLAYER_TYPE) ?: DEFAULT_PLAYER_TYPE

    fun setPlayerType(type: String) {
        prefs.edit().putString(KEY_PLAYER_TYPE, type).apply()
    }

    // -----------------------------------------------------------------
    // 超时换源（与酷9 LIVE_CONNECT_TIMEOUT 对齐）
    //
    // 0=5s, 1=10s, 2=15s, 3=20s, 4=25s, 5=30s
    // 播放超时后自动切换到下一个源
    // -----------------------------------------------------------------

/** 获取超时换源档位（0-5），默认 2（15秒） */
fun getTimeoutSwitchSource(): Int = prefs.getInt(KEY_TIMEOUT_SWITCH_SOURCE, DEFAULT_TIMEOUT_SWITCH_SOURCE)

    fun setTimeoutSwitchSource(value: Int) {
        prefs.edit().putInt(KEY_TIMEOUT_SWITCH_SOURCE, value).apply()
    }

    /** 超时换源档位对应的毫秒值 */
    fun getTimeoutMs(): Long = when (getTimeoutSwitchSource()) {
        0 -> 5_000L
        1 -> 10_000L
        2 -> 15_000L
        3 -> 20_000L
        4 -> 25_000L
        5 -> 30_000L
        else -> 10_000L
    }

    // -----------------------------------------------------------------
    // 断线重连（与酷9 RECONNECT_INDEX 对齐）
    //
    // 0=关闭, 1=1s, 2=3s, 3=5s, 4=10s, 5=20s
    // -----------------------------------------------------------------

    /** 获取断线重连档位（0-5），默认 0（关闭） */
    fun getReconnectIndex(): Int = prefs.getInt(KEY_RECONNECT_INDEX, DEFAULT_RECONNECT_INDEX)

    fun setReconnectIndex(value: Int) {
        prefs.edit().putInt(KEY_RECONNECT_INDEX, value).apply()
    }

    /** 断线重连档位对应的延迟毫秒值，0 表示关闭 */
    fun getReconnectDelayMs(): Long = when (getReconnectIndex()) {
        0 -> 0L
        1 -> 1_000L
        2 -> 3_000L
        3 -> 5_000L
        4 -> 10_000L
        5 -> 20_000L
        else -> 0L
    }

    // -----------------------------------------------------------------
    // 开机自启动（与酷9 BOOT_START 对齐）
    // -----------------------------------------------------------------

    /** 是否开启开机自启动，默认 false */
    fun getBootStart(): Boolean = prefs.getBoolean(KEY_BOOT_START, false)

    fun setBootStart(enabled: Boolean) {
        prefs.edit().putBoolean(KEY_BOOT_START, enabled).apply()
    }

    // -----------------------------------------------------------------
    // EPG 时区偏移（与酷9 TIME_ZONE_SELECT 对齐）
    //
    // 0=默认时区, 1=-12h, 2=-11h, ..., 13=+0h(默认), ..., 24=+11h, 25=+12h
    // -----------------------------------------------------------------

    /** 获取 EPG 时区偏移档位（0-25），默认 0（默认时区） */
    fun getEpgTimezoneOffset(): Int = prefs.getInt(KEY_EPG_TIMEZONE_OFFSET, 0)

    fun setEpgTimezoneOffset(value: Int) {
        prefs.edit().putInt(KEY_EPG_TIMEZONE_OFFSET, value.coerceIn(0, 25)).apply()
    }

    /** EPG 时区偏移的小时数（-12 到 +12，0 表示默认） */
    fun getEpgTimezoneOffsetHours(): Int {
        val idx = getEpgTimezoneOffset()
        if (idx == 0) return 0
        return idx - 13  // 1→-12, 13→0, 25→+12
    }

    // -----------------------------------------------------------------
    // EPG 缓存定时策略（与酷9 EPGCACHE_SELECT 对齐）
    //
    // 0=关闭缓存, 1=每天2点, 2=每天4点, 3=每天6点, 4=每天8点,
    // 5=每天10点, 6=每天12点, 7=每天14点, 8=每天16点,
    // 9=每天18点, 10=每天20点, 11=每天22点
    // -----------------------------------------------------------------

    /** 获取 EPG 缓存定时档位（0-11），默认 4（每天8点） */
    fun getEpgCacheSchedule(): Int = prefs.getInt(KEY_EPG_CACHE_SCHEDULE, DEFAULT_EPG_CACHE_SCHEDULE)

    fun setEpgCacheSchedule(value: Int) {
        prefs.edit().putInt(KEY_EPG_CACHE_SCHEDULE, value.coerceIn(0, 11)).apply()
    }

    /** EPG 缓存定时档位对应的小时（0-23），-1 表示关闭 */
    fun getEpgCacheHour(): Int {
        val idx = getEpgCacheSchedule()
        if (idx == 0) return -1
        return (idx - 1) * 2  // 1→0, 2→2, 3→4, ..., 11→20
    }

    // -----------------------------------------------------------------
    // 画面锁定/换源不黑屏（与酷9 EYE_PROTECTION 对齐）
    //
    // true=切换源时保持最后一个画面（keep-open）
    // false=切换源黑屏一下
    // -----------------------------------------------------------------

    /** 是否开启画面锁定（换源不黑屏），默认 true */
    fun getScreenLock(): Boolean = prefs.getBoolean(KEY_SCREEN_LOCK, true)

    fun setScreenLock(enabled: Boolean) {
        prefs.edit().putBoolean(KEY_SCREEN_LOCK, enabled).apply()
    }

    // -----------------------------------------------------------------
    // 分屏模式（手机端：视频+频道列表并排显示）
    // -----------------------------------------------------------------

    /** 是否开启分屏模式（手机端视频与频道列表并排），默认 false */
    fun getSplitMode(): Boolean = prefs.getBoolean(KEY_SPLIT_MODE, false)

    fun setSplitMode(enabled: Boolean) {
        prefs.edit().putBoolean(KEY_SPLIT_MODE, enabled).apply()
    }

    // -----------------------------------------------------------------
    // 倍速双步进控制（与酷9 Speed_value 对齐）
    //
    // 格式: min,max,slowStep,fastStep,fastStep2,fastStep2Threshold
    // 例如: 0.5,3,0.25,0.5,1,2
    // -----------------------------------------------------------------

    /** 获取倍速参数字符串，默认 "0.5,3,0.25,0.5,1,2" */
    fun getSpeedParams(): String = prefs.getString(KEY_SPEED_PARAMS, DEFAULT_SPEED_PARAMS) ?: DEFAULT_SPEED_PARAMS

    fun setSpeedParams(params: String) {
        prefs.edit().putString(KEY_SPEED_PARAMS, params).apply()
    }

    /** 解析倍速参数为 SpeedConfig */
    fun getSpeedConfig(): SpeedConfig {
        val parts = getSpeedParams().split(",")
        return try {
            SpeedConfig(
                min = parts.getOrNull(0)?.toDoubleOrNull() ?: 0.5,
                max = parts.getOrNull(1)?.toDoubleOrNull() ?: 3.0,
                slowStep = parts.getOrNull(2)?.toDoubleOrNull() ?: 0.25,
                fastStep = parts.getOrNull(3)?.toDoubleOrNull() ?: 0.5,
                fastStep2 = parts.getOrNull(4)?.toDoubleOrNull() ?: 1.0,
                fastStep2Threshold = parts.getOrNull(5)?.toDoubleOrNull() ?: 2.0
            )
        } catch (e: Exception) {
            SpeedConfig()
        }
    }

    // -----------------------------------------------------------------
    // 二级分组模式（与酷9 GROUP_PARS_SET_SELECT 对齐）
    //
    // 0=传统分组（仅网络列表分组）
    // 1=列表分组（所有列表分组）
    // 2=二级分组模式1（所有分组显示二级分组）
    // 3=二级分组模式2（分组数<1的隐藏二级分组）
    // -----------------------------------------------------------------

    /** 获取分组模式（0-3），默认 3 */
    fun getGroupMode(): Int = prefs.getInt(KEY_GROUP_MODE, DEFAULT_GROUP_MODE)

    fun setGroupMode(value: Int) {
        prefs.edit().putInt(KEY_GROUP_MODE, value.coerceIn(0, 3)).apply()
    }

    // -----------------------------------------------------------------
    // 频道级播放器设置（per-channel override）
    //
    // 开启后，每个频道可记忆各自的 vo / hwdec / HDR 模式。
    // 切换频道时自动应用该频道的设置（如有），实现不同频道用不同最佳配置。
    // 未设置的项目使用全局默认值。
    // -----------------------------------------------------------------

    /** 是否开启频道级播放器设置 */
    fun isPerChannelPlayerSettings(): Boolean =
        prefs.getBoolean(KEY_PER_CHANNEL_SETTINGS, false)

    fun setPerChannelPlayerSettings(enabled: Boolean) {
        prefs.edit().putBoolean(KEY_PER_CHANNEL_SETTINGS, enabled).apply()
    }

    /** 读取指定频道的播放器设置（null 表示未设置） */
    fun getChannelSettings(idx: Int): ChannelPlayerSettings? {
        val json = prefs.getString("$KEY_CHANNEL_SETTINGS_PREFIX$idx", null) ?: return null
        return try {
            val obj = JSONObject(json)
            ChannelPlayerSettings(
                playerType = obj.optString("player_type").takeIf { it.isNotEmpty() },
                vo = obj.optString("vo").takeIf { it.isNotEmpty() },
                hwdec = obj.optString("hwdec").takeIf { it.isNotEmpty() },
                hdrMode = obj.optString("hdr_mode").takeIf { it.isNotEmpty() }
            )
        } catch (e: Exception) { null }
    }

    /** 保存指定频道的播放器设置 */
    fun setChannelSettings(idx: Int, settings: ChannelPlayerSettings) {
        val obj = JSONObject().apply {
            settings.playerType?.let { put("player_type", it) }
            settings.vo?.let { put("vo", it) }
            settings.hwdec?.let { put("hwdec", it) }
            settings.hdrMode?.let { put("hdr_mode", it) }
        }
        prefs.edit().putString("$KEY_CHANNEL_SETTINGS_PREFIX$idx", obj.toString()).apply()
    }

    /** 删除指定频道的播放器设置 */
    fun removeChannelSettings(idx: Int) {
        prefs.edit().remove("$KEY_CHANNEL_SETTINGS_PREFIX$idx").apply()
    }

    // -----------------------------------------------------------------
    // 日志等级（与 PC 端 core/log_manager.py 对齐）
    //
    // 控制日志输出等级（debug / info / warn / error）。
    // 默认 info（与 PC 端一致）。
    // 同时影响：mpv msg-level、Python logging（app.log 文件 + logcat）。
    // -----------------------------------------------------------------

    /** 获取日志等级，默认 "info" */
    fun getLogLevel(): String = prefs.getString(KEY_LOG_LEVEL, DEFAULT_LOG_LEVEL) ?: DEFAULT_LOG_LEVEL

    /** 设置日志等级 */
    fun setLogLevel(level: String) {
        prefs.edit().putString(KEY_LOG_LEVEL, level).apply()
    }

    // -----------------------------------------------------------------
    // 主题模式（深色/浅色/跟随系统）
    //
    // 与 PC 端 ThemeManager 的 color_mode 对齐。
    // "dark"=深色（默认，视频播放沉浸感）
    // "light"=浅色
    // "system"=跟随系统
    // -----------------------------------------------------------------

    /** 获取主题模式，默认 "dark" */
    fun getThemeMode(): String = prefs.getString(KEY_THEME_MODE, DEFAULT_THEME_MODE) ?: DEFAULT_THEME_MODE

    /** 设置主题模式 */
    fun setThemeMode(mode: String) {
        prefs.edit().putString(KEY_THEME_MODE, mode).apply()
    }

    // -----------------------------------------------------------------
    // 最近打开文件/URL（与 PC 端 recent_menu 对齐）
    //
    // 存储最近打开的播放列表文件、网络流 URL、本地视频文件。
    // 最多 20 条，按时间倒序。
    // -----------------------------------------------------------------

    fun getRecentFiles(): List<RecentEntry> {
        val json = prefs.getString(KEY_RECENT_FILES, "[]") ?: "[]"
        return parseRecentFiles(json)
    }

    fun addRecentFile(entry: RecentEntry) {
        val cur = getRecentFiles().toMutableList()
        cur.removeAll { it.uri == entry.uri }
        cur.add(0, entry)
        if (cur.size > MAX_RECENT_FILES) {
            cur.subList(MAX_RECENT_FILES, cur.size).clear()
        }
        saveRecentFiles(cur)
    }

    fun removeRecentFile(uri: String) {
        val cur = getRecentFiles().toMutableList()
        cur.removeAll { it.uri == uri }
        saveRecentFiles(cur)
    }

    fun clearRecentFiles() {
        prefs.edit().putString(KEY_RECENT_FILES, "[]").apply()
    }

    private fun saveRecentFiles(list: List<RecentEntry>) {
        val arr = JSONArray()
        list.forEach { item ->
            arr.put(JSONObject().apply {
                put("uri", item.uri)
                put("name", item.name)
                put("type", item.type)
                put("ts", item.timestamp)
            })
        }
        prefs.edit().putString(KEY_RECENT_FILES, arr.toString()).apply()
    }

    private fun parseRecentFiles(json: String): List<RecentEntry> {
        if (json.isEmpty()) return emptyList()
        return try {
            val arr = JSONArray(json)
            (0 until arr.length()).mapNotNull { idx ->
                val obj = arr.optJSONObject(idx) ?: return@mapNotNull null
                RecentEntry(
                    uri = obj.optString("uri"),
                    name = obj.optString("name"),
                    type = obj.optString("type"),
                    timestamp = obj.optLong("ts", 0),
                )
            }
        } catch (e: Exception) {
            emptyList()
        }
    }

    // -----------------------------------------------------------------
    // 局域网管理设置
    //
    // 自动关闭开关：开启后 5 分钟自动停止服务器（默认开启）
    // 关闭后服务器持续运行，直到手动停止
    // -----------------------------------------------------------------

    /** 获取局域网管理是否自动关闭（5 分钟超时），默认 true */
    fun getAdminAutoStop(): Boolean = prefs.getBoolean(KEY_ADMIN_AUTO_STOP, DEFAULT_ADMIN_AUTO_STOP)

    fun setAdminAutoStop(enabled: Boolean) {
        prefs.edit().putBoolean(KEY_ADMIN_AUTO_STOP, enabled).apply()
    }

    // -----------------------------------------------------------------
    // 网络增强设置（HTTP Referer / Proxy / Headers）
    //
    // 持久化用户配置的 HTTP 网络参数，用于绕过防盗链 / 代理 / 自定义头。
    // 仅对 MPV 播放器生效（通过 setPropertyString 下发到 mpv）。
    // -----------------------------------------------------------------

    fun getHttpReferer(): String = prefs.getString(KEY_HTTP_REFERER, "") ?: ""
    fun setHttpReferer(value: String) {
        prefs.edit().putString(KEY_HTTP_REFERER, value).apply()
    }
    fun getHttpProxy(): String = prefs.getString(KEY_HTTP_PROXY, "") ?: ""
    fun setHttpProxy(value: String) {
        prefs.edit().putString(KEY_HTTP_PROXY, value).apply()
    }
    fun getHttpHeaders(): String = prefs.getString(KEY_HTTP_HEADERS, "") ?: ""
    fun setHttpHeaders(value: String) {
        prefs.edit().putString(KEY_HTTP_HEADERS, value).apply()
    }

    // -----------------------------------------------------------------
    // 节目提醒（与 PC 端 services/epg_reminder_service.py 对齐）
    //
    // 持久化 EPG 节目提醒，启动时加载，定时检查并在节目开始前 60 秒触发。
    // 存储 key "epg_reminders"：JSONArray of ReminderItem。
    // -----------------------------------------------------------------

    fun getReminders(): List<ReminderItem> {
        val json = prefs.getString(KEY_REMINDERS, "[]") ?: "[]"
        return parseReminders(json)
    }

    fun hasReminder(id: String): Boolean = getReminders().any { it.id == id }

    /** 添加提醒（去重），返回是否新增成功 */
    fun addReminder(item: ReminderItem): Boolean {
        val cur = getReminders().toMutableList()
        if (cur.any { it.id == item.id }) return false
        cur.add(item)
        saveReminders(cur)
        return true
    }

    /** 删除指定 ID 的提醒，返回是否删除了 */
    fun removeReminder(id: String): Boolean {
        val cur = getReminders().toMutableList()
        val removed = cur.removeAll { it.id == id }
        if (removed) saveReminders(cur)
        return removed
    }

    fun clearReminders() {
        prefs.edit().putString(KEY_REMINDERS, "[]").apply()
    }

    fun setReminders(list: List<ReminderItem>) {
        saveReminders(list)
    }

    private fun saveReminders(list: List<ReminderItem>) {
        val arr = JSONArray()
        list.forEach { item ->
            arr.put(JSONObject().apply {
                put("id", item.id)
                put("channel_idx", item.channelIdx)
                put("channel_name", item.channelName)
                put("tvg_id", item.tvgId)
                put("program_title", item.programTitle)
                put("start_ts", item.startTs)
                put("stop_ts", item.stopTs)
                put("created_at", item.createdAt)
            })
        }
        prefs.edit().putString(KEY_REMINDERS, arr.toString()).apply()
    }

    private fun parseReminders(json: String): List<ReminderItem> {
        if (json.isEmpty()) return emptyList()
        return try {
            val arr = JSONArray(json)
            (0 until arr.length()).mapNotNull { idx ->
                val obj = arr.optJSONObject(idx) ?: return@mapNotNull null
                ReminderItem(
                    id = obj.optString("id"),
                    channelIdx = obj.optInt("channel_idx", -1),
                    channelName = obj.optString("channel_name"),
                    tvgId = obj.optString("tvg_id"),
                    programTitle = obj.optString("program_title"),
                    startTs = obj.optLong("start_ts", 0),
                    stopTs = obj.optLong("stop_ts", 0),
                    createdAt = obj.optLong("created_at", 0),
                )
            }
        } catch (e: Exception) {
            emptyList()
        }
    }

    // -----------------------------------------------------------------
    // 续播位置（与 PC 端 core/config_manager.py resume_positions.json 对齐）
    //
    // 持久化播放位置，下次加载同一 URL 时自动恢复。
    // - 最多保存 200 条（与 PC 端 _RESUME_MAX_ENTRIES 一致）
    // - 直播流（duration=0 或 dur>86400）不保存
    // - 距结尾 <3s 视为已播完，自动删除
    // -----------------------------------------------------------------

    fun getResumeList(): List<ResumeItem> {
        val json = prefs.getString(KEY_RESUME, "[]") ?: "[]"
        return parseResumeList(json)
    }

    fun getResume(url: String): ResumeItem? =
        getResumeList().firstOrNull { it.url == url }

    /**
     * 保存/更新续播位置。
     * - position < 5 秒：不保存（与 PC 端 _RESUME_MIN_POSITION_SEC 一致）
     * - duration>0 且 position+3 >= duration：视为已播完，删除已有记录
     * - 超过 200 条：按 updatedAt 升序淘汰最旧
     * @return 写入后的最新列表
     */
    fun saveResume(item: ResumeItem): List<ResumeItem> {
        // 已播完 → 删除
        if (item.duration > 0 && item.position + 3 >= item.duration) {
            val cur = getResumeList().toMutableList()
            cur.removeAll { it.url == item.url }
            saveResumeList(cur)
            return cur
        }
        // 太短不保存
        if (item.position < MIN_RESUME_POSITION_SEC) return getResumeList()

        val cur = getResumeList().toMutableList()
        // 移除同 url 旧记录
        cur.removeAll { it.url == item.url }
        cur.add(item)
        // 限流：最多 MAX_RESUME_ENTRIES 条，淘汰最旧
        if (cur.size > MAX_RESUME_ENTRIES) {
            val sorted = cur.sortedBy { it.updatedAt }
            cur.removeAll(sorted.take(cur.size - MAX_RESUME_ENTRIES))
        }
        saveResumeList(cur)
        return cur
    }

    fun removeResume(url: String): Boolean {
        val cur = getResumeList().toMutableList()
        val removed = cur.removeAll { it.url == url }
        if (removed) saveResumeList(cur)
        return removed
    }

    fun clearResume() {
        prefs.edit().putString(KEY_RESUME, "[]").apply()
    }

    private fun saveResumeList(list: List<ResumeItem>) {
        val arr = JSONArray()
        list.forEach { item ->
            arr.put(JSONObject().apply {
                put("id", item.id)
                put("url", item.url)
                put("name", item.name)
                put("channel_idx", item.channelIdx)
                put("position", item.position)
                put("duration", item.duration)
                put("updated_at", item.updatedAt)
            })
        }
        prefs.edit().putString(KEY_RESUME, arr.toString()).apply()
    }

    private fun parseResumeList(json: String): List<ResumeItem> {
        if (json.isEmpty()) return emptyList()
        return try {
            val arr = JSONArray(json)
            (0 until arr.length()).mapNotNull { idx ->
                val obj = arr.optJSONObject(idx) ?: return@mapNotNull null
                ResumeItem(
                    id = obj.optString("id"),
                    url = obj.optString("url"),
                    name = obj.optString("name"),
                    channelIdx = obj.optInt("channel_idx", -1),
                    position = obj.optLong("position", 0),
                    duration = obj.optLong("duration", 0),
                    updatedAt = obj.optLong("updated_at", 0),
                )
            }
        } catch (e: Exception) {
            emptyList()
        }
    }

    // -----------------------------------------------------------------
    // 书签（与 PC 端 core/config_manager.py bookmarks.json 对齐）
    //
    // JSON 结构：以 url 为 key 的 dict，值为书签数组。
    // - 同 url 同位置（0.5s 容差）覆盖
    // - 每个 url 最多 100 条，全局最多 500 个 url
    // -----------------------------------------------------------------

    /** 加载指定 URL 的书签（按 position 升序） */
    fun getBookmarks(url: String): List<BookmarkItem> {
        val json = prefs.getString(KEY_BOOKMARKS, "{}") ?: "{}"
        return parseBookmarkMap(json)[url]?.sortedBy { it.position } ?: emptyList()
    }

    /** 加载所有书签（按 created_at 降序） */
    fun getAllBookmarks(): List<BookmarkItem> {
        val json = prefs.getString(KEY_BOOKMARKS, "{}") ?: "{}"
        return parseBookmarkMap(json).values.flatten().sortedByDescending { it.createdAt }
    }

    /**
     * 添加书签（同 URL 0.5s 容差内覆盖 name 和 createdAt）。
     * @return 写入后的该 URL 书签列表
     */
    fun addBookmark(url: String, position: Long, name: String = ""): List<BookmarkItem> {
        val map = parseBookmarkMap(prefs.getString(KEY_BOOKMARKS, "{}") ?: "{}").toMutableMap()
        val list = (map[url] ?: emptyList()).toMutableList()
        // 0.5s 容差匹配
        val existingIdx = list.indexOfFirst { kotlin.math.abs(it.position - position) < 1 }
        val item = BookmarkItem(
            id = "${url}_$position",
            url = url,
            name = name,
            position = position,
            createdAt = System.currentTimeMillis(),
        )
        if (existingIdx >= 0) {
            list[existingIdx] = item
        } else {
            list.add(item)
            // 限流：每 URL 最多 100 条
            if (list.size > MAX_BOOKMARK_PER_URL) {
                list.sortBy { it.createdAt }
                list.subList(0, list.size - MAX_BOOKMARK_PER_URL).clear()
            }
        }
        map[url] = list
        // 限流：全局最多 500 个 URL
        if (map.size > MAX_BOOKMARK_URLS) {
            val sortedUrls = map.entries.sortedBy { ent -> ent.value.minOf { it.createdAt } }
                .map { it.key }
            sortedUrls.take(map.size - MAX_BOOKMARK_URLS).forEach { map.remove(it) }
        }
        saveBookmarkMap(map)
        return map[url]?.sortedBy { it.position } ?: emptyList()
    }

    /** 删除指定书签（0.5s 容差） */
    fun deleteBookmark(url: String, position: Long): Boolean {
        val map = parseBookmarkMap(prefs.getString(KEY_BOOKMARKS, "{}") ?: "{}").toMutableMap()
        val list = map[url] ?: return false
        val removed = list.filterNot { kotlin.math.abs(it.position - position) < 1 }
        if (removed.size == list.size) return false
        if (removed.isEmpty()) {
            map.remove(url)
        } else {
            map[url] = removed
        }
        saveBookmarkMap(map)
        return true
    }

    /** 清除指定 URL 的所有书签 */
    fun clearBookmarks(url: String) {
        val map = parseBookmarkMap(prefs.getString(KEY_BOOKMARKS, "{}") ?: "{}").toMutableMap()
        map.remove(url)
        saveBookmarkMap(map)
    }

    /** 清除所有书签 */
    fun clearAllBookmarks() {
        prefs.edit().putString(KEY_BOOKMARKS, "{}").apply()
    }

    private fun saveBookmarkMap(map: Map<String, List<BookmarkItem>>) {
        val obj = JSONObject()
        map.forEach { (url, list) ->
            val arr = JSONArray()
            list.forEach { item ->
                arr.put(JSONObject().apply {
                    put("id", item.id)
                    put("url", item.url)
                    put("name", item.name)
                    put("position", item.position)
                    put("created_at", item.createdAt)
                })
            }
            obj.put(url, arr)
        }
        prefs.edit().putString(KEY_BOOKMARKS, obj.toString()).apply()
    }

    private fun parseBookmarkMap(json: String): Map<String, List<BookmarkItem>> {
        if (json.isEmpty()) return emptyMap()
        return try {
            val obj = JSONObject(json)
            obj.keys().asSequence().associateWith { url ->
                val arr = obj.optJSONArray(url) ?: return@associateWith emptyList()
                (0 until arr.length()).mapNotNull { idx ->
                    val item = arr.optJSONObject(idx) ?: return@mapNotNull null
                    BookmarkItem(
                        id = item.optString("id"),
                        url = item.optString("url"),
                        name = item.optString("name"),
                        position = item.optLong("position", 0),
                        createdAt = item.optLong("created_at", 0),
                    )
                }
            }
        } catch (e: Exception) {
            emptyMap()
        }
    }

    // -----------------------------------------------------------------
    // 收藏（URL 版本，更稳健）
    // -----------------------------------------------------------------

    fun getFavoriteUrls(): Set<String> {
        val arr = prefs.getString(KEY_FAVORITES_URLS, "[]") ?: "[]"
        return parseStringArray(arr).toSet()
    }

    fun isFavoriteUrl(url: String): Boolean = getFavoriteUrls().contains(url)

    fun toggleFavoriteUrl(url: String): Boolean {
        val cur = getFavoriteUrls().toMutableSet()
        val added = if (cur.contains(url)) {
            cur.remove(url)
            false
        } else {
            cur.add(url)
            true
        }
        prefs.edit().putString(KEY_FAVORITES_URLS, JSONArray(cur.toList()).toString()).apply()
        return added
    }

    fun setFavoriteUrls(urls: Set<String>) {
        prefs.edit().putString(KEY_FAVORITES_URLS, JSONArray(urls.toList()).toString()).apply()
    }

    // -----------------------------------------------------------------
    // 历史（URL 版本，更稳健）
    // -----------------------------------------------------------------

    fun getHistoryUrls(): List<String> {
        val arr = prefs.getString(KEY_HISTORY_URLS, "[]") ?: "[]"
        return parseStringArray(arr)
    }

    fun addToHistoryUrl(url: String) {
        val cur = getHistoryUrls().toMutableList()
        cur.remove(url)
        cur.add(0, url)
        if (cur.size > MAX_HISTORY) {
            cur.subList(MAX_HISTORY, cur.size).clear()
        }
        prefs.edit().putString(KEY_HISTORY_URLS, JSONArray(cur).toString()).apply()
    }

    fun setHistoryUrls(urls: List<String>) {
        prefs.edit().putString(KEY_HISTORY_URLS, JSONArray(urls).toString()).apply()
    }

    // -----------------------------------------------------------------
    // 队列（URL 版本）
    // -----------------------------------------------------------------

    fun getQueueUrls(): List<String> {
        val arr = prefs.getString(KEY_QUEUE_URLS, "[]") ?: "[]"
        return parseStringArray(arr)
    }

    fun addToQueueUrl(url: String) {
        val cur = getQueueUrls().toMutableList()
        if (!cur.contains(url)) {
            cur.add(url)
            prefs.edit().putString(KEY_QUEUE_URLS, JSONArray(cur).toString()).apply()
        }
    }

    fun removeFromQueueUrl(url: String) {
        val cur = getQueueUrls().toMutableList()
        cur.remove(url)
        prefs.edit().putString(KEY_QUEUE_URLS, JSONArray(cur).toString()).apply()
    }

    fun setQueueUrls(urls: List<String>) {
        prefs.edit().putString(KEY_QUEUE_URLS, JSONArray(urls).toString()).apply()
    }

    // -----------------------------------------------------------------
    // 工具
    // -----------------------------------------------------------------

    private fun parseStringArray(json: String): List<String> {
        if (json.isEmpty()) return emptyList()
        return try {
            val arr = JSONArray(json)
            (0 until arr.length()).mapNotNull { idx ->
                arr.optString(idx, "").takeIf { it.isNotEmpty() }
            }
        } catch (e: Exception) {
            emptyList()
        }
    }

    private fun parseIntArray(json: String): List<Int> {
        if (json.isEmpty()) return emptyList()
        return try {
            val arr = JSONArray(json)
            (0 until arr.length()).mapNotNull { idx ->
                arr.optInt(idx, -1).takeIf { it >= 0 }
            }
        } catch (e: Exception) {
            emptyList()
        }
    }

    companion object {
        private const val PREFS_NAME = "iptv_user_prefs"
        private const val KEY_FAVORITES = "favorites"
        private const val KEY_HISTORY = "history"
        private const val KEY_QUEUE = "queue"
        // URL 版本的存储（比 idx 更稳健，订阅源重载后不会失效）
        private const val KEY_FAVORITES_URLS = "favorites_urls"
        private const val KEY_HISTORY_URLS = "history_urls"
        private const val KEY_QUEUE_URLS = "queue_urls"
        private const val MAX_HISTORY = 100
        // 上次播放的频道 URL（启动时按 URL 查找频道恢复播放，URL 比 idx 更稳健）
        private const val KEY_LAST_CHANNEL_URL = "last_channel_url"
        // 启动自动续播开关（默认开启）
        private const val KEY_AUTO_RESUME = "auto_resume_on_start"
        private const val DEFAULT_AUTO_RESUME = true

        // 播放器设置 key
        private const val KEY_VO = "player_vo"
        private const val KEY_HWDEC = "player_hwdec"
        private const val KEY_VO_FALLBACK = "player_vo_fallback_confirmed"
        private const val KEY_PLAYER_TYPE = "player_type"
        private const val DEFAULT_PLAYER_TYPE = "MPV"
        private const val KEY_HDR_MODE = "hdr_output_mode"
        private const val DEFAULT_HDR_MODE = "disable"

        // 超时换源
        private const val KEY_TIMEOUT_SWITCH_SOURCE = "timeout_switch_source"
        private const val DEFAULT_TIMEOUT_SWITCH_SOURCE = 2

        // 断线重连
        private const val KEY_RECONNECT_INDEX = "reconnect_index"
        private const val DEFAULT_RECONNECT_INDEX = 0

        // 开机自启动
        private const val KEY_BOOT_START = "boot_start"

        // EPG 时区偏移
        private const val KEY_EPG_TIMEZONE_OFFSET = "epg_timezone_offset"

        // EPG 缓存定时
        private const val KEY_EPG_CACHE_SCHEDULE = "epg_cache_schedule"
        private const val DEFAULT_EPG_CACHE_SCHEDULE = 4

        // 画面锁定（换源不黑屏）
        private const val KEY_SCREEN_LOCK = "screen_lock"

        // 分屏模式（手机端：视频+频道列表并排显示）
        private const val KEY_SPLIT_MODE = "split_mode"

        // 倍速双步进参数
        private const val KEY_SPEED_PARAMS = "speed_params"
        private const val DEFAULT_SPEED_PARAMS = "0.5,3,0.25,0.5,1,2"

        // 二级分组模式
        private const val KEY_GROUP_MODE = "group_mode"
        private const val DEFAULT_GROUP_MODE = 3
        private const val KEY_RTSP_TRANSPORT = "rtsp_transport"
        private const val DEFAULT_RTSP_TRANSPORT = "tcp"
        private const val KEY_DEINTERLACE = "deinterlace"
        private const val DEFAULT_DEINTERLACE = "no"
        // 频道级播放器设置（per-channel override）
        private const val KEY_PER_CHANNEL_SETTINGS = "per_channel_player_settings"
        private const val KEY_CHANNEL_SETTINGS_PREFIX = "channel_settings_"

        // 局域网管理设置 key
        private const val KEY_ADMIN_AUTO_STOP = "admin_auto_stop"
        private const val DEFAULT_ADMIN_AUTO_STOP = true

        // 网络增强设置 key
        private const val KEY_HTTP_REFERER = "http_referer"
        private const val KEY_HTTP_PROXY = "http_proxy"
        private const val KEY_HTTP_HEADERS = "http_headers"

        // 节目提醒 key
        private const val KEY_REMINDERS = "epg_reminders"

        // 续播位置 key 与常量（与 PC 端 core/config_manager.py 对齐）
        private const val KEY_RESUME = "resume_positions"
        private const val MAX_RESUME_ENTRIES = 200
        private const val MIN_RESUME_POSITION_SEC = 5L

        // 书签 key 与常量（与 PC 端 core/config_manager.py 对齐）
        private const val KEY_BOOKMARKS = "bookmarks"
        private const val MAX_BOOKMARK_URLS = 500
        private const val MAX_BOOKMARK_PER_URL = 100

        // 播放器默认值（与 MPVView.DEFAULT_VO / DEFAULT_HWDEC 保持一致）
        // 这里用字符串常量而非引用 MPVView，避免 UserPrefs 反向依赖 mpv 层
        private const val DEFAULT_VO_VALUE = "gpu"
        private const val DEFAULT_HWDEC_VALUE = "auto-copy"

        // 日志等级（与 PC 端 core/log_manager.py 对齐）
        // 可选值：debug / info / warn / error
        // 同时控制 mpv msg-level 和 Python logging（app.log 文件 + logcat）
        private const val KEY_LOG_LEVEL = "log_level"
        private const val DEFAULT_LOG_LEVEL = "info"

        // 主题模式
        private const val KEY_THEME_MODE = "theme_mode"
        private const val DEFAULT_THEME_MODE = "dark"

        // 最近打开
        private const val KEY_RECENT_FILES = "recent_files"
        private const val MAX_RECENT_FILES = 20

        // TV 开机直接播放（跳过首页直接全屏播放上次频道）
        private const val KEY_DIRECT_PLAY_ON_BOOT = "direct_play_on_boot"
        private const val DEFAULT_DIRECT_PLAY_ON_BOOT = false

        // TV 屏保超时（分钟，0=关闭）
        private const val KEY_SCREENSAVER_TIMEOUT = "screensaver_timeout"
        private const val DEFAULT_SCREENSAVER_TIMEOUT = 5

        // 竖屏全屏模式（竖屏视频填满屏幕，不强制旋转）
        private const val KEY_PORTRAIT_FULLSCREEN = "portrait_fullscreen"
        private const val DEFAULT_PORTRAIT_FULLSCREEN = false

        @Volatile
        private var INSTANCE: UserPrefs? = null

        fun getInstance(): UserPrefs =
            INSTANCE ?: synchronized(this) {
                INSTANCE ?: UserPrefs().also { INSTANCE = it }
            }

        fun init(context: Context) = getInstance().init(context)
    }

    // -----------------------------------------------------------------
    // TV 开机直接播放（跳过首页直接全屏播放上次频道）
    // -----------------------------------------------------------------

    /** 是否开启 TV 开机直接播放，默认 false */
    fun isDirectPlayOnBoot(): Boolean = prefs.getBoolean(KEY_DIRECT_PLAY_ON_BOOT, DEFAULT_DIRECT_PLAY_ON_BOOT)

    fun setDirectPlayOnBoot(enabled: Boolean) {
        prefs.edit().putBoolean(KEY_DIRECT_PLAY_ON_BOOT, enabled).apply()
    }

    // -----------------------------------------------------------------
    // TV 屏保超时（分钟，0=关闭屏保）
    // -----------------------------------------------------------------

    /** 获取屏保超时分钟数，默认 5 分钟，0=关闭 */
    fun getScreensaverTimeout(): Int = prefs.getInt(KEY_SCREENSAVER_TIMEOUT, DEFAULT_SCREENSAVER_TIMEOUT)

    fun setScreensaverTimeout(minutes: Int) {
        prefs.edit().putInt(KEY_SCREENSAVER_TIMEOUT, minutes.coerceAtLeast(0)).apply()
    }

    // -----------------------------------------------------------------
    // 竖屏全屏模式（竖屏视频/竖屏直播时填满屏幕，不强制旋转到横屏）
    // -----------------------------------------------------------------

    /** 是否开启竖屏全屏，默认 false */
    fun isPortraitFullscreen(): Boolean = prefs.getBoolean(KEY_PORTRAIT_FULLSCREEN, DEFAULT_PORTRAIT_FULLSCREEN)

    fun setPortraitFullscreen(enabled: Boolean) {
        prefs.edit().putBoolean(KEY_PORTRAIT_FULLSCREEN, enabled).apply()
    }
}
