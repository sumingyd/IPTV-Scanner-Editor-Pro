package com.iptv.scanner.editor.pro

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import android.util.Log
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat

/**
 * EPG 节目提醒系统通知。
 *
 * 应用内弹窗（_triggeredReminder）仅在应用前台可见；切到后台/PiP 时
 * 由本通知兜底（进程存活期间 checkReminders 仍在轮询）。
 * Android 13+ 需 POST_NOTIFICATIONS 运行时授权（MainActivity 启动时申请），
 * 未授权时静默跳过，应用内弹窗不受影响。
 */
object EpgReminderNotifier {

    private const val TAG = "EpgReminderNotifier"
    private const val CHANNEL_ID = "epg_reminders"
    private const val NOTIFICATION_ID = 2001

    fun ensureChannel(context: Context) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val nm = context.getSystemService(Context.NOTIFICATION_SERVICE) as? NotificationManager ?: return
        if (nm.getNotificationChannel(CHANNEL_ID) != null) return
        val channel = NotificationChannel(
            CHANNEL_ID,
            "节目提醒",
            NotificationManager.IMPORTANCE_HIGH
        ).apply {
            description = "EPG 节目即将开始的提醒通知"
        }
        nm.createNotificationChannel(channel)
    }

    /** 触发提醒时投递系统通知；通知栏点击回主界面（用户可在应用内切换到该频道） */
    fun notifyProgramStart(context: Context, channelName: String, programTitle: String) {
        ensureChannel(context)
        if (!NotificationManagerCompat.from(context).areNotificationsEnabled()) {
            Log.v(TAG, "notifications disabled, skip system reminder")
            return
        }
        val launchIntent = Intent(context, MainActivityCompose::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP
        }
        val pending = PendingIntent.getActivity(
            context,
            0,
            launchIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        val notification = NotificationCompat.Builder(context, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_launcher_foreground)
            .setContentTitle(channelName.ifEmpty { "节目提醒" })
            .setContentText("$programTitle 即将开始")
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setCategory(NotificationCompat.CATEGORY_REMINDER)
            .setAutoCancel(true)
            .setContentIntent(pending)
            .build()
        try {
            NotificationManagerCompat.from(context).notify(NOTIFICATION_ID, notification)
        } catch (e: SecurityException) {
            Log.w(TAG, "notify failed: ${e.message}")
        }
    }
}
