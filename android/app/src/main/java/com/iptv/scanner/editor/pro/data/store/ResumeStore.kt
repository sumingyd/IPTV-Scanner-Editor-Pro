package com.iptv.scanner.editor.pro.data.store

import android.content.SharedPreferences
import com.iptv.scanner.editor.pro.data.ResumeItem
import org.json.JSONArray
import org.json.JSONObject

/**
 * 续播域存储：持久化播放位置，下次加载同一 URL 时自动恢复。
 *
 * - 最多保存 200 条
 * - 直播流（duration=0 或 dur>86400）不保存
 * - 距结尾 <3s 视为已播完，自动删除
 */
class ResumeStore(private val prefs: SharedPreferences) {

    fun getResumeList(): List<ResumeItem> {
        val json = prefs.getString(KEY_RESUME, "[]") ?: "[]"
        return parseResumeList(json)
    }

    fun getResume(url: String): ResumeItem? =
        getResumeList().firstOrNull { it.url == url }

    /**
     * 保存/更新续播位置。
     * - position < 5 秒：不保存
     * - duration>0 且 position+3 >= duration：视为已播完，删除已有记录
     * - 超过 200 条：按 updatedAt 升序淘汰最旧
     * @return 写入后的最新列表
     */
    fun saveResume(item: ResumeItem): List<ResumeItem> {
        if (item.duration > 0 && item.position + 3 >= item.duration) {
            val cur = getResumeList().toMutableList()
            cur.removeAll { it.url == item.url }
            saveResumeList(cur)
            return cur
        }
        if (item.position < MIN_RESUME_POSITION_SEC) return getResumeList()

        val cur = getResumeList().toMutableList()
        cur.removeAll { it.url == item.url }
        cur.add(item)
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

    companion object {
        private const val KEY_RESUME = "resume_positions"
        private const val MAX_RESUME_ENTRIES = 200
        private const val MIN_RESUME_POSITION_SEC = 5L
    }
}