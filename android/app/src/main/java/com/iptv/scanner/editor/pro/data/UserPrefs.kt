package com.iptv.scanner.editor.pro.data

import android.content.Context
import android.content.SharedPreferences
import org.json.JSONArray
import org.json.JSONObject

/**
 * 用户偏好持久化：收藏 / 历史 / 队列。
 *
 * 与 PC 端 user_settings.json 和 mobile storage（localStorage）对齐。
 * 使用 SharedPreferences + JSON 简单存储，避免引入 Room/DataStore 等重依赖。
 *
 * 存储 key：
 * - "favorites"：Set<Int>，收藏的频道 idx 列表
 * - "history"：List<Int>，最近播放的频道 idx（按时间倒序，最多 100）
 * - "queue"：List<Int>，播放队列
 *
 * 注意：频道 idx 是 channels 数组的下标，与 PC 端 mobile/index.html state.currentIdx 一致。
 * 当订阅源重载导致 channels 顺序变化时，idx 可能失效——这种情况下 UI 应优雅降级
 * （idx 越界时跳过）。
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
    // 批量恢复（备份恢复时一次性写入，替代逐条 add）
    // -----------------------------------------------------------------

    fun setFavorites(favorites: Set<Int>) {
        prefs.edit().putString(KEY_FAVORITES, JSONArray(favorites.toList()).toString()).apply()
    }

    fun setHistory(history: List<Int>) {
        prefs.edit().putString(KEY_HISTORY, JSONArray(history).toString()).apply()
    }

    fun setQueue(queue: List<Int>) {
        prefs.edit().putString(KEY_QUEUE, JSONArray(queue).toString()).apply()
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

    /** 重置播放器设置为默认值（用户换设备或想重新探测时调用） */
    fun resetPlayerSettings() {
        prefs.edit()
            .remove(KEY_VO)
            .remove(KEY_HWDEC)
            .remove(KEY_VO_FALLBACK)
            .remove(KEY_PLAYER_TYPE)
            .remove(KEY_HDR_MODE)
            .apply()
    }

    // -----------------------------------------------------------------
    // 播放器类型（MPV / EXO / VLC / IJK）
    //
    // 持久化用户选择的播放器内核，下次启动自动恢复。
    // 默认 "MPV"（功能最完整）。
    // -----------------------------------------------------------------

    /** 获取持久化的播放器类型名称（PlayerType.name()），默认 "MPV" */
    fun getPlayerType(): String = prefs.getString(KEY_PLAYER_TYPE, "MPV") ?: "MPV"

    fun setPlayerType(type: String) {
        prefs.edit().putString(KEY_PLAYER_TYPE, type).apply()
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
    // 工具
    // -----------------------------------------------------------------

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
        private const val MAX_HISTORY = 100

        // 播放器设置 key
        private const val KEY_VO = "player_vo"
        private const val KEY_HWDEC = "player_hwdec"
        private const val KEY_VO_FALLBACK = "player_vo_fallback_confirmed"
        private const val KEY_PLAYER_TYPE = "player_type"
        private const val KEY_HDR_MODE = "hdr_output_mode"
        private const val DEFAULT_HDR_MODE = "disable"

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

        @Volatile
        private var INSTANCE: UserPrefs? = null

        fun getInstance(): UserPrefs =
            INSTANCE ?: synchronized(this) {
                INSTANCE ?: UserPrefs().also { INSTANCE = it }
            }

        fun init(context: Context) = getInstance().init(context)
    }
}
