package com.iptv.scanner.editor.pro.data.store

import android.content.SharedPreferences

/**
 * EPG 设置域存储：时区偏移 + 缓存定时策略。
 *
 * 时区偏移：0=默认时区, 1=-12h, ..., 13=+0h, ..., 25=+12h
 * 缓存定时：0=关闭, 1=每天0点, 2=每天2点, ..., 11=每天20点
 */
class EpgSettingsStore(private val prefs: SharedPreferences) {

    /** 获取 EPG 时区偏移档位（0-25），默认 0（默认时区） */
    fun getEpgTimezoneOffset(): Int = prefs.getInt(KEY_EPG_TIMEZONE_OFFSET, 0)

    fun setEpgTimezoneOffset(value: Int) {
        prefs.edit().putInt(KEY_EPG_TIMEZONE_OFFSET, value.coerceIn(0, 25)).apply()
    }

    /** EPG 时区偏移的小时数（-12 到 +12，0 表示默认） */
    fun getEpgTimezoneOffsetHours(): Int {
        val idx = getEpgTimezoneOffset()
        if (idx == 0) return 0
        return idx - 13
    }

    /** 获取 EPG 缓存定时档位（0-11），默认 4（每天8点） */
    fun getEpgCacheSchedule(): Int = prefs.getInt(KEY_EPG_CACHE_SCHEDULE, DEFAULT_EPG_CACHE_SCHEDULE)

    fun setEpgCacheSchedule(value: Int) {
        prefs.edit().putInt(KEY_EPG_CACHE_SCHEDULE, value.coerceIn(0, 11)).apply()
    }

    /** EPG 缓存定时档位对应的小时（0-23），-1 表示关闭 */
    fun getEpgCacheHour(): Int {
        val idx = getEpgCacheSchedule()
        if (idx == 0) return -1
        return (idx - 1) * 2
    }

    companion object {
        private const val KEY_EPG_TIMEZONE_OFFSET = "epg_timezone_offset"
        private const val KEY_EPG_CACHE_SCHEDULE = "epg_cache_schedule"
        private const val DEFAULT_EPG_CACHE_SCHEDULE = 4
    }
}