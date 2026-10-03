package com.iptv.scanner.editor.pro.data.store

import android.content.SharedPreferences

/**
 * 网络设置域存储：HTTP Referer / Proxy / Headers。
 *
 * 仅对 MPV 播放器生效（通过 setPropertyString 下发到 mpv）。
 */
class NetworkSettingsStore(private val prefs: SharedPreferences) {

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

    companion object {
        private const val KEY_HTTP_REFERER = "http_referer"
        private const val KEY_HTTP_PROXY = "http_proxy"
        private const val KEY_HTTP_HEADERS = "http_headers"
    }
}