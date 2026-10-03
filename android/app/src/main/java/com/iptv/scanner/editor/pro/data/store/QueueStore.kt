package com.iptv.scanner.editor.pro.data.store

import android.content.SharedPreferences
import org.json.JSONArray

/**
 * 队列域存储：idx-based + URL-based 播放队列管理。
 */
class QueueStore(private val prefs: SharedPreferences) {

    // -----------------------------------------------------------------
    // idx-based 队列
    // -----------------------------------------------------------------

    fun getQueue(): List<Int> {
        val arr = prefs.getString(KEY_QUEUE, "[]") ?: "[]"
        return parseIntArray(arr)
    }

    fun addToQueue(idx: Int) {
        synchronized(this) {
            val cur = getQueue().toMutableList()
            if (!cur.contains(idx)) {
                cur.add(idx)
                prefs.edit().putString(KEY_QUEUE, JSONArray(cur).toString()).apply()
            }
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

    // 批量恢复用 commit()（同步写入）保证一致性
    fun setQueue(queue: List<Int>) {
        synchronized(this) {
            prefs.edit().putString(KEY_QUEUE, JSONArray(queue).toString()).commit()
        }
    }

    // -----------------------------------------------------------------
    // URL-based 队列
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
        private const val KEY_QUEUE = "queue"
        private const val KEY_QUEUE_URLS = "queue_urls"
    }
}