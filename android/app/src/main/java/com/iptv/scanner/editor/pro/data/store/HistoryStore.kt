package com.iptv.scanner.editor.pro.data.store

import android.content.SharedPreferences
import org.json.JSONArray

/**
 * 历史域存储：idx-based + URL-based 播放历史管理。
 *
 * 按时间倒序，最多 MAX_HISTORY(100) 条。
 * idx 版本和 URL 版本双写，读取时优先用 URL 匹配。
 */
class HistoryStore(private val prefs: SharedPreferences) {

    // -----------------------------------------------------------------
    // idx-based 历史
    // -----------------------------------------------------------------

    fun getHistory(): List<Int> {
        val arr = prefs.getString(KEY_HISTORY, "[]") ?: "[]"
        return parseIntArray(arr)
    }

    /** 添加到历史（去重后插入队首，最多 100 条） */
    fun addToHistory(idx: Int) {
        synchronized(this) {
            val cur = getHistory().toMutableList()
            cur.remove(idx)
            cur.add(0, idx)
            if (cur.size > MAX_HISTORY) {
                cur.subList(MAX_HISTORY, cur.size).clear()
            }
            prefs.edit().putString(KEY_HISTORY, JSONArray(cur).toString()).apply()
        }
    }

    fun clearHistory() {
        prefs.edit().putString(KEY_HISTORY, "[]").apply()
    }

    // 批量恢复用 commit()（同步写入）保证一致性
    fun setHistory(history: List<Int>) {
        synchronized(this) {
            prefs.edit().putString(KEY_HISTORY, JSONArray(history).toString()).commit()
        }
    }

    // -----------------------------------------------------------------
    // URL-based 历史（更稳健）
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
        private const val KEY_HISTORY = "history"
        private const val KEY_HISTORY_URLS = "history_urls"
        private const val MAX_HISTORY = 100
    }
}