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

        MPVLib.setOptionString("vo", "gpu")
        MPVLib.setOptionString("hwdec", "auto")
        MPVLib.setOptionString("keep-open", "yes")

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