package com.iptv.scanner.editor.pro.mpv

import android.content.Context
import android.util.AttributeSet
import android.util.Log
import android.view.SurfaceHolder
import android.view.SurfaceView
import `is`.xyz.mpv.MPVLib

class MPVView @JvmOverloads constructor(context: Context, attrs: AttributeSet? = null) : SurfaceView(context, attrs), SurfaceHolder.Callback {

    fun initialize(configDir: String, cacheDir: String) {
        MPVLib.create(context)

        MPVLib.setOptionString("config", "yes")
        MPVLib.setOptionString("config-dir", configDir)
        for (opt in arrayOf("gpu-shader-cache-dir", "icc-cache-dir"))
            MPVLib.setOptionString(opt, cacheDir)

        /* VO/HWDEC：与 PC 端 services/mpv_player_service.py 对齐 */
        MPVLib.setOptionString("vo", "gpu")
        MPVLib.setOptionString("hwdec", "auto-safe")
        MPVLib.setOptionString("keep-open", "yes")

        /* 性能与音画同步（与 PC 端 _ensure_mpv_initialized 行 339-363 一致）：
         * - framedrop=vo：视频输出慢时丢帧，避免渲染积压阻塞 GUI
         * - video-sync=audio：以音频时钟为同步基准，视频帧迟到时丢帧而非阻塞
         * - cache-pause-initial=no：初始缓存阶段不暂停，避免直播流启动卡顿
         * 这三个参数是解决音画不同步和帧率低的核心 */
        MPVLib.setOptionString("framedrop", "vo")
        MPVLib.setOptionString("video-sync", "audio")
        MPVLib.setOptionString("cache-pause-initial", "no")

        /* 缓冲与预读：与 PC 端 _setup_protocol_options 对齐
         * - cache=yes：启用 demuxer 缓存
         * - cache-secs=10：移动端 10 秒（PC 端直播 3600s，但移动端内存有限）
         * - demuxer-max-bytes=50MiB：与 JS 默认对齐
         * - demuxer-max-back-bytes=25MiB：允许向后 seek
         * - demuxer-readahead-secs=10：预读 10 秒
         * - demuxer-seekable-cache=yes：缓存可 seek（时移/回看必需）
         * - force-seekable=yes：强制可 seek */
        MPVLib.setOptionString("cache", "yes")
        MPVLib.setOptionString("cache-secs", "10")
        MPVLib.setOptionString("demuxer-max-bytes", "50MiB")
        MPVLib.setOptionString("demuxer-max-back-bytes", "25MiB")
        MPVLib.setOptionString("demuxer-readahead-secs", "10")
        MPVLib.setOptionString("demuxer-seekable-cache", "yes")
        MPVLib.setOptionString("force-seekable", "yes")

        /* 网络/直播优化（与 PC 端对齐，但 source-timeout 更宽松避免移动网络抖动） */
        MPVLib.setOptionString("network-timeout", "30")
        MPVLib.setOptionString("source-timeout", "10")
        MPVLib.setOptionString("stream-open-timeout", "30")

        /* 移动端解码优化：2 线程（PC 端 max(2, cpu//2)） */
        MPVLib.setOptionString("vd-lavc-threads", "2")

        /* 队列优化：移动端 GPU 调度抖动大，启用队列平滑输出 */
        MPVLib.setOptionString("vd-queue-enable", "yes")
        MPVLib.setOptionString("ad-queue-enable", "yes")

        MPVLib.init()

        MPVLib.setOptionString("force-window", "no")
        MPVLib.setOptionString("idle", "once")

        holder.addCallback(this)
        observeProperties()
    }

    fun destroy() {
        holder.removeCallback(this)
        MPVLib.destroy()
    }

    private fun observeProperties() {
        MPVLib.observeProperty("time-pos", MPVLib.MpvFormat.MPV_FORMAT_DOUBLE)
        MPVLib.observeProperty("duration", MPVLib.MpvFormat.MPV_FORMAT_DOUBLE)
        MPVLib.observeProperty("pause", MPVLib.MpvFormat.MPV_FORMAT_FLAG)
        MPVLib.observeProperty("eof-reached", MPVLib.MpvFormat.MPV_FORMAT_FLAG)
        MPVLib.observeProperty("volume", MPVLib.MpvFormat.MPV_FORMAT_INT64)
        MPVLib.observeProperty("mute", MPVLib.MpvFormat.MPV_FORMAT_FLAG)
        MPVLib.observeProperty("media-title", MPVLib.MpvFormat.MPV_FORMAT_STRING)
        MPVLib.observeProperty("track-list", MPVLib.MpvFormat.MPV_FORMAT_NODE)
    }

    private var filePath: String? = null

    fun playFile(path: String) {
        if (holder.surface != null && holder.surface.isValid) {
            MPVLib.command(arrayOf("loadfile", path))
            // 显式解除暂停：keep-open=yes 会让 mpv 在 stop/idle 后保留 pause=true，
            // 不显式恢复会导致新文件加载后不播放（一直显示已暂停）
            MPVLib.setPropertyBoolean("pause", false)
        } else {
            filePath = path
        }
    }

    fun stop() {
        MPVLib.command(arrayOf("stop"))
    }

    private var voInUse: String = "gpu"

    override fun surfaceChanged(holder: SurfaceHolder, format: Int, width: Int, height: Int) {
        MPVLib.setPropertyString("android-surface-size", "${width}x$height")
    }

    override fun surfaceCreated(holder: SurfaceHolder) {
        Log.w(TAG, "attaching surface")
        MPVLib.attachSurface(holder.surface)
        MPVLib.setOptionString("force-window", "yes")

        if (filePath != null) {
            MPVLib.command(arrayOf("loadfile", filePath as String))
            MPVLib.setPropertyBoolean("pause", false)
            filePath = null
        } else {
            MPVLib.setPropertyString("vo", voInUse)
        }
    }

    override fun surfaceDestroyed(holder: SurfaceHolder) {
        Log.w(TAG, "detaching surface")
        MPVLib.setPropertyString("vo", "null")
        MPVLib.setPropertyString("force-window", "no")
        MPVLib.detachSurface()
    }

    companion object {
        private const val TAG = "mpv"
    }
}