package com.iptv.scanner.editor.pro.data.store

import android.content.SharedPreferences
import com.iptv.scanner.editor.pro.data.BookmarkItem
import org.json.JSONArray
import org.json.JSONObject

/**
 * 书签域存储：以 url 为 key 的 dict，值为书签数组。
 *
 * - 同 url 同位置（1s 容差）覆盖
 * - 每个 url 最多 100 条，全局最多 500 个 url
 */
class BookmarkStore(private val prefs: SharedPreferences) {

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
     * 添加书签（同 URL 1s 容差内覆盖 name 和 createdAt）。
     * @return 写入后的该 URL 书签列表
     */
    fun addBookmark(url: String, position: Long, name: String = ""): List<BookmarkItem> {
        val map = parseBookmarkMap(prefs.getString(KEY_BOOKMARKS, "{}") ?: "{}").toMutableMap()
        val list = (map[url] ?: emptyList()).toMutableList()
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
            if (list.size > MAX_BOOKMARK_PER_URL) {
                list.sortBy { it.createdAt }
                list.subList(0, list.size - MAX_BOOKMARK_PER_URL).clear()
            }
        }
        map[url] = list
        if (map.size > MAX_BOOKMARK_URLS) {
            val sortedUrls = map.entries.sortedBy { ent -> ent.value.minOf { it.createdAt } }
                .map { it.key }
            sortedUrls.take(map.size - MAX_BOOKMARK_URLS).forEach { map.remove(it) }
        }
        saveBookmarkMap(map)
        return map[url]?.sortedBy { it.position } ?: emptyList()
    }

    /** 删除指定书签（1s 容差） */
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

    companion object {
        private const val KEY_BOOKMARKS = "bookmarks"
        private const val MAX_BOOKMARK_URLS = 500
        private const val MAX_BOOKMARK_PER_URL = 100
    }
}