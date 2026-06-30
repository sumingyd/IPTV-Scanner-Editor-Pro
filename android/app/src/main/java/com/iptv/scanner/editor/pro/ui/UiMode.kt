package com.iptv.scanner.editor.pro.ui

import android.content.Context
import android.content.res.Configuration
import android.os.Build

/**
 * UI 模式：手机触摸 vs TV 遥控器。
 *
 * 设计差异（用户明确要求）：
 * - PHONE：底部控制面板（3 行：媒体信息 / 节目信息 / 控制条）+ 左右抽屉（频道列表 / EPG）
 *   触摸交互，点击/滑动为主
 * - TV：左侧频道导航栏（DPAD 上下切换）+ 顶部信息条 + 中央播放 + 右侧 EPG 抽屉
 *   DPAD 焦点导航，方向键 + 确认键为主
 *
 * 判断标准（与 Android Leanback 一致）：
 * 1. UI_MODE_TYPE_TELEVISION（系统声明 TV 模式）
 * 2. FEATURE_LEANBACK（系统支持 Leanback TV 启动器）
 * 3. Build.VERSION.SDK_INT >= 21 且无触屏（FEATURE_TOUCHSCREEN=false）
 *
 * 注意：部分 TV 盒子（如小米盒子）同时具备触屏和 TV 模式，以 UI_MODE_TYPE_TELEVISION 优先。
 */
enum class UiMode {
    PHONE,
    TV;

    val isTV: Boolean get() = this == TV
    val isPhone: Boolean get() = this == PHONE
}

object UiModeDetector {
    /**
     * 检测当前设备应该使用哪种 UI 模式。
     * 在 Activity 创建时调用一次，结果缓存在 ViewModel 中。
     */
    fun detect(context: Context): UiMode {
        // 1. 系统声明 TV 模式（最可靠）
        val currentModeType = context.resources.configuration.uiMode and Configuration.UI_MODE_TYPE_MASK
        if (currentModeType == Configuration.UI_MODE_TYPE_TELEVISION) {
            return UiMode.TV
        }

        // 2. 支持 Leanback（TV 启动器特性）
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP
            && context.packageManager.hasSystemFeature("android.software.leanback")
        ) {
            return UiMode.TV
        }

        // 3. 无触屏设备（部分老旧 TV）
        if (!context.packageManager.hasSystemFeature("android.hardware.touchscreen")) {
            return UiMode.TV
        }

        return UiMode.PHONE
    }
}
