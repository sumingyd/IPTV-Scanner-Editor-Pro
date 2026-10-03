package com.iptv.scanner.editor.pro.mpv.controller

import `is`.xyz.mpv.MPVLib

/**
 * 字幕子控制器：字幕可见性/延迟/缩放/位置/批量样式应用。
 */
class MpvSubtitleController(private val host: MpvControllerHost) {

    fun setSubVisibility(v: Boolean) =
        host.postOnUiThread { MPVLib.setPropertyBoolean("sub-visibility", v) }

    fun toggleSubVisibility() =
        host.postOnUiThread { MPVLib.command(arrayOf("cycle", "sub-visibility")) }

    fun setSubDelay(delaySec: Double) =
        host.postOnUiThread { MPVLib.setPropertyDouble("sub-delay", delaySec) }

    fun adjustSubDelay(delta: Double) = host.postOnUiThread {
        val cur = try { MPVLib.getPropertyDouble("sub-delay") ?: 0.0 } catch (_: Throwable) { 0.0 }
        MPVLib.setPropertyDouble("sub-delay", (cur + delta).coerceIn(-10.0, 10.0))
    }

    fun setSubScale(scale: Double) =
        host.postOnUiThread { MPVLib.setPropertyDouble("sub-scale", scale.coerceIn(0.1, 10.0)) }

    fun setSubPos(pos: Int) =
        host.postOnUiThread { MPVLib.setPropertyInt("sub-pos", pos.coerceIn(0, 100)) }

    fun applySubStyle(style: Map<String, String>) = host.postOnUiThread {
        style.forEach { (k, v) -> MPVLib.setPropertyString("sub-$k", v) }
    }
}