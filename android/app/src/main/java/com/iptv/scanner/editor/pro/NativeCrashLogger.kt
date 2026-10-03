package com.iptv.scanner.editor.pro

import android.content.Context
import android.os.Build
import android.util.Log
import java.io.File
import java.io.IOException
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * 原生崩溃（SIGSEGV/SIGABRT 等）日志收集器。
 *
 * ACRA 只能捕获 Java 层异常（UncaughtExceptionHandler），无法捕获 native 信号崩溃。
 * 本类通过后台 logcat 进程记录日志，下次启动时检测上次是否异常退出，
 * 若是则将 logcat 日志保存为崩溃报告。
 *
 * 工作原理：
 * 1. 应用启动时调用 [checkPreviousCrash]：检查 "session_alive" 标记文件
 *    - 若存在且内容为 "true"，说明上次没有正常退出（被 SIGSEGV 杀死）
 *    - 将当前 logcat 缓冲区中的崩溃日志保存到崩溃报告目录
 *    - 标记文件重置为 "true"（本次会话开始）
 * 2. 应用正常退出时调用 [markCleanExit]：标记文件写入 "false"
 * 3. 后台 logcat 进程持续将日志写入临时文件（环形缓冲，限制大小）
 *
 * 崩溃报告保存路径：getFilesDir()/crash-reports/crash_<timestamp>.txt
 *
 * 与 ACRA 配合：
 * - Java 异常 → ACRA 捕获，保存到 getFilesDir()/ACRA/
 * - Native 崩溃 → 本类捕获，保存到 getFilesDir()/crash-reports/
 * - 两种报告都可在 设置 > 崩溃日志 中查看
 */
object NativeCrashLogger {
    private const val TAG = "NativeCrashLogger"

    /** 会话标记文件（标记上次会话是否正常退出） */
    private const val SESSION_FILE = "session_alive"

    /** logcat 临时文件（后台进程持续写入） */
    private const val LOGCAT_TEMP_FILE = "logcat_buffer.txt"

    /** logcat 临时文件最大大小（1MB，超出后截断旧数据） */
    private const val MAX_LOGCAT_FILE_SIZE = 1L * 1024 * 1024

    /** 崩溃报告目录名 */
    private const val CRASH_DIR = "crash-reports"

    /** 最多保留的崩溃报告数量 */
    private const val MAX_CRASH_FILES = 20

    @Volatile
    private var logcatProcess: Process? = null

    /**
     * 停止 logcat 后台进程，释放资源。
     * 在 Application.onTerminate 或 Activity.onDestroy 中调用。
     */
    fun stop() {
        try {
            logcatProcess?.let { proc ->
                proc.destroy()
                // 确保进程完全终止，避免僵尸进程
                if (!proc.waitFor(2, java.util.concurrent.TimeUnit.SECONDS)) {
                    proc.destroyForcibly()
                    proc.waitFor(1, java.util.concurrent.TimeUnit.SECONDS)
                }
            }
        } catch (e: Exception) {
            Log.w(TAG, "stop logcat process failed: ${e.message}")
        } finally {
            logcatProcess = null
        }
    }

    /**
     * 在 Application.onCreate 中调用。
     *
     * 1. 检查上次会话是否异常退出，若是则保存崩溃日志
     * 2. 启动后台 logcat 进程记录本次会话日志
     * 3. 标记本次会话为 "alive"（未正常退出状态）
     */
    fun init(context: Context) {
        checkPreviousCrash(context)
        startLogcatCapture(context)
        markSessionAlive(context)
    }

    /**
     * 检查上次会话是否异常退出。
     * 若 session_alive 文件内容为 "true"，说明上次没有调用 markCleanExit（被 native 崩溃杀死）。
     */
    private fun checkPreviousCrash(context: Context) {
        try {
            val sessionFile = File(context.filesDir, SESSION_FILE)
            if (sessionFile.exists()) {
                val content = sessionFile.readText().trim()
                if (content == "true") {
                    // 上次会话异常退出（native 崩溃），保存 logcat 缓冲区作为崩溃报告
                    saveCrashReport(context)
                }
            }
        } catch (e: Exception) {
            Log.w(TAG, "checkPreviousCrash failed: ${e.message}")
        }
    }

    /**
     * 保存崩溃报告。
     * 从 logcat 缓冲区读取最近日志，加上设备信息，保存为崩溃报告文件。
     */
    private fun saveCrashReport(context: Context) {
        try {
            val crashDir = File(context.filesDir, CRASH_DIR).apply { mkdirs() }
            val timestamp = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.getDefault()).format(Date())
            val crashFile = File(crashDir, "crash_$timestamp.txt")

            // 先从 logcat 临时文件读取（后台进程记录的）
            val tempLogcat = File(context.filesDir, LOGCAT_TEMP_FILE)
            val logcatContent = if (tempLogcat.exists()) {
                tempLogcat.readText().take(512 * 1024)
            } else {
                "(logcat buffer not found)"
            }

            // 再从 logcat -d 读取缓冲区中残留的崩溃信息
            val dumpLogcat = try {
                val proc = Runtime.getRuntime().exec(arrayOf("logcat", "-d", "-t", "500"))
                val text = proc.inputStream.bufferedReader().readText()
                proc.waitFor()
                text
            } catch (e: Exception) {
                "(logcat dump failed: ${e.message})"
            }

            // 组装崩溃报告
            val report = buildString {
                appendLine("=== ISEP Native Crash Report ===")
                appendLine("Time: ${Date()}")
                appendLine("Device: ${Build.MANUFACTURER} ${Build.MODEL}")
                appendLine("Android: ${Build.VERSION.RELEASE} (API ${Build.VERSION.SDK_INT})")
                appendLine("ABI: ${Build.SUPPORTED_ABIS.joinToString(", ")}")
                appendLine("App Version: ${getAppVersion(context)}")
                appendLine()
                appendLine("=== Logcat Buffer (from background process) ===")
                appendLine(logcatContent)
                appendLine()
                appendLine("=== Logcat Dump (from system buffer) ===")
                appendLine(dumpLogcat)
            }

            crashFile.writeText(report)
            Log.i(TAG, "Crash report saved: ${crashFile.absolutePath}")

            // 清理临时 logcat 文件
            tempLogcat.delete()

            // 清理过旧的崩溃报告
            cleanupOldCrashReports(crashDir)
        } catch (e: Exception) {
            Log.e(TAG, "saveCrashReport failed", e)
        }
    }

    /**
     * 启动后台 logcat 进程，持续将日志写入临时文件。
     * 使用 -v threadtime 格式（含时间戳、PID、TID、级别、Tag）。
     * 过滤只保留与应用相关的日志（PID 过滤）。
     */
    private fun startLogcatCapture(context: Context) {
        try {
            val tempLogcat = File(context.filesDir, LOGCAT_TEMP_FILE)
            // 截断旧文件（避免无限增长）
            if (tempLogcat.exists() && tempLogcat.length() > MAX_LOGCAT_FILE_SIZE) {
                tempLogcat.delete()
            }

            val pid = android.os.Process.myPid()
            // logcat --pid=<pid> 只记录当前进程的日志
            // -v threadtime: 日期 时间 PID TID 级别 Tag 消息
            val cmd = arrayOf("logcat", "--pid=$pid", "-v", "threadtime")
            logcatProcess = ProcessBuilder(*cmd)
                .redirectOutput(tempLogcat)
                .redirectErrorStream(true)
                .start()

            Log.i(TAG, "Logcat capture started (pid=$pid, file=${tempLogcat.absolutePath})")
        } catch (e: Exception) {
            Log.w(TAG, "startLogcatCapture failed: ${e.message}")
        }
    }

    /**
     * 标记本次会话为 "alive"（未正常退出）。
     * 若下次启动时此标记仍为 "true"，说明本次被 native 崩溃杀死。
     */
    private fun markSessionAlive(context: Context) {
        try {
            File(context.filesDir, SESSION_FILE).writeText("true")
        } catch (e: Exception) {
            Log.w(TAG, "markSessionAlive failed: ${e.message}")
        }
    }

    /**
     * 标记正常退出（在 Activity.onDestroy 或 onTerminate 中调用）。
     * 写入 "false"，下次启动时不会误报崩溃。
     */
    fun markCleanExit(context: Context) {
        try {
            File(context.filesDir, SESSION_FILE).writeText("false")
            // 停止 logcat 进程并清理临时文件
            stop()
            File(context.filesDir, LOGCAT_TEMP_FILE).delete()
        } catch (e: Exception) {
            Log.w(TAG, "markCleanExit failed: ${e.message}")
        }
    }

    /**
     * 获取所有崩溃报告文件列表（按修改时间降序，最新的在前）。
     */
    fun getCrashReports(context: Context): List<File> {
        val dir = File(context.filesDir, CRASH_DIR)
        if (!dir.exists()) return emptyList()
        return dir.listFiles()
            ?.filter { it.isFile && it.name.startsWith("crash_") }
            ?.sortedByDescending { it.lastModified() }
            ?: emptyList()
    }

    /**
     * 读取指定崩溃报告的内容。
     */
    fun readCrashReport(file: File): String {
        return try {
            file.readText()
        } catch (e: IOException) {
            "读取失败: ${e.message}"
        }
    }

    /**
     * 删除指定崩溃报告。
     */
    fun deleteCrashReport(file: File): Boolean {
        return file.delete()
    }

    /**
     * 清除所有崩溃报告。
     */
    fun clearAllCrashReports(context: Context) {
        val dir = File(context.filesDir, CRASH_DIR)
        dir.listFiles()?.filter { it.isFile }?.forEach { it.delete() }
    }

    /**
     * 清理过旧的崩溃报告，只保留最近的 MAX_CRASH_FILES 条。
     */
    private fun cleanupOldCrashReports(crashDir: File) {
        val files = crashDir.listFiles()
            ?.filter { it.isFile && it.name.startsWith("crash_") }
            ?.sortedByDescending { it.lastModified() }
            ?: return
        if (files.size > MAX_CRASH_FILES) {
            files.drop(MAX_CRASH_FILES).forEach { it.delete() }
        }
    }

    private fun getAppVersion(context: Context): String {
        return try {
            val pm = context.packageManager
            val info = pm.getPackageInfo(context.packageName, 0)
            "${info.versionName} (${info.longVersionCode})"
        } catch (e: Exception) {
            "unknown"
        }
    }
}
