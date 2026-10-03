package com.iptv.scanner.editor.pro.data.store

import android.content.SharedPreferences
import org.json.JSONArray

/**
 * 收藏域存储：idx-based + URL-based 收藏管理。
 *
 * idx 版本：频道在当前订阅源中的序号（重载后可能失效）。
 * URL 版本：频道 URL（比 idx 更稳健，订阅源重载后仍可匹配）。
 *
 * isFavorite 使用 favoritesCache 实现 O(1) 查询，频道列表渲染频繁调用。
 */
class FavoriteStore(private val prefs: SharedPreferences) {

    @Volatile
    private var favoritesCache: MutableSet<Int>? = null

    fun initCache() {
        favoritesCache = parseIntArray(prefs.getString(KEY_FAVORITES, "[]") ?: "[]").toMutableSet()
    }

    private fun ensureFavoritesCache(): MutableSet<Int> {
        return favoritesCache ?: synchronized(this) {
            favoritesCache ?: parseIntArray(prefs.getString(KEY_FAVORITES, "[]") ?: "[]").toMutableSet().also { favoritesCache = it }
        }
    }

    // -----------------------------------------------------------------
    // idx-based 收藏
    // -----------------------------------------------------------------

    fun getFavorites(): Set<Int> {
        val arr = prefs.getString(KEY_FAVORITES, "[]") ?: "[]"
        return parseIntArray(arr).toSet()
    }

    fun isFavorite(idx: Int): Boolean = ensureFavoritesCache().contains(idx)

    fun toggleFavorite(idx: Int): Boolean {
        synchronized(this) {
            val cur = ensureFavoritesCache()
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
    }

    // 批量恢复用 commit()（同步写入）保证一致性，避免恢复过程中崩溃丢失数据
    fun setFavorites(favorites: Set<Int>) {
        synchronized(this) {
            prefs.edit().putString(KEY_FAVORITES, JSONArray(favorites.toList()).toString()).commit()
            favoritesCache = favorites.toMutableSet()
        }
    }

    // -----------------------------------------------------------------
    // URL-based 收藏（更稳健）
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
        private const val KEY_FAVORITES = "favorites"
        private const val KEY_FAVORITES_URLS = "favorites_urls"
    }
}