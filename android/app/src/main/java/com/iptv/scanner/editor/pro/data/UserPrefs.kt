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

    /** 重置播放器设置为默认值（用户换设备或想重新探测时调用） */
    fun resetPlayerSettings() {
        prefs.edit()
            .remove(KEY_VO)
            .remove(KEY_HWDEC)
            .remove(KEY_VO_FALLBACK)
            .apply()
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
