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

        /* 性能与音画同步（与 PC 端 _ensure_mpv_initialized 行 339-363 对齐，但 framedrop 调整）：
         * - framedrop=all：解码慢或输出慢时都丢帧
         *   PC 端用 framedrop=vo（只在输出慢时丢帧），但 Android 模拟器/低端设备解码慢，
         *   仅 vo 模式会导致解码队列积压、视频帧延迟显示（音频比画面快）。
         *   改用 all 模式在解码阶段就丢帧，减少积压延迟。性能充足时不会丢帧，无害。
         * - video-sync=audio：以音频时钟为同步基准，视频帧迟到时丢帧而非阻塞
         * - cache-pause-initial=no：初始缓存阶段不暂停，避免直播流启动卡顿 */
        MPVLib.setOptionString("framedrop", "all")
        MPVLib.setOptionString("video-sync", "audio")
        MPVLib.setOptionString("cache-pause-initial", "no")

        /* 音画同步增强：
         * 注意：不启用 audio-stream-silence（PC 端没有），该参数会让音频提前播放导致音画不同步
         * 注意：不启用 video-latency-hacks（PC 端也没有），该参数可能导致 PTS 处理偏差 */

        /* 缓冲与预读：与 PC 端 _load_playback_settings 默认值完全对齐
         * PC 端默认：cache-secs=1.0, demuxer-max-bytes=16MiB, demuxer-max-back-bytes=4MiB
         * 之前 Android 端设为 readahead=10s/max=50MiB/back=25MiB，导致视频解码队列过长产生 600ms 延迟
         * 现在完全对齐 PC 端的小缓冲策略，保持低延迟 */
        MPVLib.setOptionString("demuxer-max-bytes", "16MiB")
        MPVLib.setOptionString("demuxer-max-back-bytes", "4MiB")
        MPVLib.setOptionString("demuxer-readahead-secs", "1")
        MPVLib.setOptionString("demuxer-seekable-cache", "yes")
        MPVLib.setOptionString("force-seekable", "yes")

        /* 网络/直播优化（与 PC 端对齐，但 source-timeout 更宽松避免移动网络抖动） */
        MPVLib.setOptionString("network-timeout", "30")
        MPVLib.setOptionString("source-timeout", "10")
        MPVLib.setOptionString("stream-open-timeout", "30")

        /* 移动端解码优化：动态获取 CPU 核数（与 PC 端 _ensure_mpv_initialized 行 361-363 一致）
         * PC 端：threads = max(2, cpu_count // 2)
         * 之前 Android 端固定为 2，在多核设备上解码线程不足导致解码队列积压 */
        val cpuCount = Runtime.getRuntime().availableProcessors()
        val threads = maxOf(2, cpuCount / 2)
        MPVLib.setOptionString("vd-lavc-threads", threads.toString())

        /* 注意：不启用 vd-queue-enable/ad-queue-enable
         * 这两个参数会让解码器队列化数据，增加延迟导致音画不同步
         * PC 端也没有这两个参数 */

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