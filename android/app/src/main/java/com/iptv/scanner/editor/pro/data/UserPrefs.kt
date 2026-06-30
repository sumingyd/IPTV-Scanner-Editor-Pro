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

        @Volatile
        private var INSTANCE: UserPrefs? = null

        fun getInstance(): UserPrefs =
            INSTANCE ?: synchronized(this) {
                INSTANCE ?: UserPrefs().also { INSTANCE = it }
            }

        fun init(context: Context) = getInstance().init(context)
    }
}
