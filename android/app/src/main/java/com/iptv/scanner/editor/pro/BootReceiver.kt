package com.iptv.scanner.editor.pro

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.os.Build
import android.util.Log

/**
 * 开机自启动接收器（与侧边栏 BOOT_START 对齐）。
 *
 * 接收 BOOT_COMPLETED 广播后，根据用户设置决定是否启动 MainActivity。
 * 在 Android 10+ 上，应用需在用户手动启动一次后才能接收 BOOT_COMPLETED。
 *
 * 注意：Google Play 政策限制开机自启动权限，但本应用面向 IPTV 盒子/电视，
 * 不在 Play Store 分发，因此使用此功能是合理的。
 */
class BootReceiver : BroadcastReceiver() {
    companion object {
        private const val TAG = "BootReceiver"
    }

    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != Intent.ACTION_BOOT_COMPLETED &&
            intent.action != "android.intent.action.QUICKBOOT_POWERON" &&
            intent.action != "com.htc.intent.action.QUICKBOOT_POWERON"
        ) {
            return
        }

        Log.i(TAG, "Received boot completed broadcast")

        // 安全初始化 UserPrefs（开机自启动时 Application.onCreate 可能未执行）
        com.iptv.scanner.editor.pro.data.UserPrefs.init(context)

        // 读取用户设置：是否开机自启动
        val userPrefs = com.iptv.scanner.editor.pro.data.UserPrefs.getInstance()
        if (!userPrefs.getBootStart()) {
            Log.i(TAG, "Boot start disabled, skipping")
            return
        }

        try {
            val launchIntent = Intent(context, MainActivityCompose::class.java).apply {
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP)
            }
            context.startActivity(launchIntent)
            Log.i(TAG, "Launched MainActivity on boot")
        } catch (e: Exception) {
            Log.e(TAG, "Failed to launch on boot", e)
        }
    }
}
