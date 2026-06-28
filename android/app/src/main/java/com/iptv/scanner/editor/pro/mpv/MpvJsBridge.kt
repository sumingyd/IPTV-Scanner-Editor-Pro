package com.iptv.scanner.editor.pro.mpv

import android.webkit.JavascriptInterface
import android.webkit.WebView
import `is`.xyz.mpv.MPVLib

/**
 * JS↔Native 桥接：把 mpv 属性读写和命令暴露给 WebView。
 *
 * 设计原则：
 * - 通用 API（setPropertyString/getPropertyString/command）覆盖所有 mpv 功能，
 *   避免每加一个功能就要改 Kotlin 代码。
 * - 兼容旧 API（play/stop/setPause 等）保留向后兼容。
 * - 所有 mpv 调用都 post 到 MPVView 线程执行，保证线程安全。
 */
class MpvJsBridge(private val mpvView: MPVView, private val webView: WebView) : MPVLib.EventObserver {

    fun register() {
        MPVLib.addObserver(this)
        webView.addJavascriptInterface(this, "AndroidMpv")
    }

    fun unregister() {
        MPVLib.removeObserver(this)
    }

    // ------------------------------------------------------------------
    // 兼容旧 API（保留向后兼容）
    // ------------------------------------------------------------------
    @JavascriptInterface
    fun play(url: String) {
        mpvView.post { mpvView.playFile(url) }
    }

    @JavascriptInterface
    fun stop() {
        mpvView.post { mpvView.stop() }
    }

    @JavascriptInterface
    fun setPause(paused: Boolean) {
        mpvView.post { MPVLib.setPropertyBoolean("pause", paused) }
    }

    @JavascriptInterface
    fun togglePause() {
        mpvView.post { MPVLib.command(arrayOf("cycle", "pause")) }
    }

    @JavascriptInterface
    fun seek(seconds: Double) {
        mpvView.post { MPVLib.setPropertyDouble("time-pos", seconds) }
    }

    @JavascriptInterface
    fun seekRelative(seconds: Double) {
        mpvView.post { MPVLib.command(arrayOf("seek", seconds.toString(), "relative")) }
    }

    @JavascriptInterface
    fun setVolume(volume: Int) {
        mpvView.post { MPVLib.setPropertyInt("volume", volume) }
    }

    @JavascriptInterface
    fun toggleMute() {
        mpvView.post { MPVLib.command(arrayOf("cycle", "mute")) }
    }

    @JavascriptInterface
    fun setMute(muted: Boolean) {
        mpvView.post { MPVLib.setPropertyBoolean("mute", muted) }
    }

    @JavascriptInterface
    fun setSpeed(speed: Double) {
        mpvView.post { MPVLib.setPropertyDouble("speed", speed) }
    }

    @JavascriptInterface
    fun cycleAudio() {
        mpvView.post { MPVLib.command(arrayOf("cycle", "audio")) }
    }

    @JavascriptInterface
    fun cycleSub() {
        mpvView.post { MPVLib.command(arrayOf("cycle", "sub")) }
    }

    @JavascriptInterface
    fun setHwdec(mode: String) {
        mpvView.post { MPVLib.setPropertyString("hwdec", mode) }
    }

    // ------------------------------------------------------------------
    // 通用 mpv 属性 API（覆盖所有 PC 端高级功能）
    // ------------------------------------------------------------------
    @JavascriptInterface
    fun setPropertyString(name: String, value: String) {
        mpvView.post { MPVLib.setPropertyString(name, value) }
    }

    @JavascriptInterface
    fun setPropertyInt(name: String, value: Int) {
        mpvView.post { MPVLib.setPropertyInt(name, value) }
    }

    @JavascriptInterface
    fun setPropertyDouble(name: String, value: Double) {
        mpvView.post { MPVLib.setPropertyDouble(name, value) }
    }

    @JavascriptInterface
    fun setPropertyBoolean(name: String, value: Boolean) {
        mpvView.post { MPVLib.setPropertyBoolean(name, value) }
    }

    @JavascriptInterface
    fun getPropertyString(name: String): String {
        return MPVLib.getPropertyString(name) ?: ""
    }

    @JavascriptInterface
    fun getPropertyInt(name: String): Int {
        return MPVLib.getPropertyInt(name) ?: 0
    }

    @JavascriptInterface
    fun getPropertyDouble(name: String): Double {
        return MPVLib.getPropertyDouble(name) ?: 0.0
    }

    @JavascriptInterface
    fun getPropertyBoolean(name: String): Boolean {
        return MPVLib.getPropertyBoolean(name) ?: false
    }

    /**
     * 发送 mpv 命令。args 是 JSON 字符串数组，例如 ["seek","10","relative"]。
     */
    @JavascriptInterface
    fun command(jsonArgs: String) {
        try {
            val arr = org.json.JSONArray(jsonArgs)
            val args = Array(arr.length()) { arr.getString(it) }
            mpvView.post { MPVLib.command(args) }
        } catch (e: Exception) {
            // 静默忽略格式错误
        }
    }

    /**
     * 截图到指定路径（video 模式，不含 OSD）。
     */
    @JavascriptInterface
    fun screenshotToFile(path: String) {
        mpvView.post { MPVLib.command(arrayOf("screenshot-to-file", path, "video")) }
    }

    // ------------------------------------------------------------------
    // 旧的 getter（保留向后兼容）
    // ------------------------------------------------------------------
    @JavascriptInterface
    fun getTimePos(): Double {
        return MPVLib.getPropertyDouble("time-pos") ?: 0.0
    }

    @JavascriptInterface
    fun getDuration(): Double {
        return MPVLib.getPropertyDouble("duration") ?: 0.0
    }

    @JavascriptInterface
    fun getPause(): Boolean {
        return MPVLib.getPropertyBoolean("pause") ?: true
    }

    @JavascriptInterface
    fun getVolume(): Int {
        return MPVLib.getPropertyInt("volume") ?: 100
    }

    @JavascriptInterface
    fun getMute(): Boolean {
        return MPVLib.getPropertyBoolean("mute") ?: false
    }

    // ------------------------------------------------------------------
    // mpv 事件回传 JS
    // ------------------------------------------------------------------
    private fun sendToJS(js: String) {
        webView.post {
            webView.evaluateJavascript(js, null)
        }
    }

    override fun eventProperty(property: String) {}

    override fun eventProperty(property: String, value: Long) {
        sendToJS("if(window.onMpvProperty)onMpvProperty('$property',$value)")
    }

    override fun eventProperty(property: String, value: Boolean) {
        sendToJS("if(window.onMpvProperty)onMpvProperty('$property',$value)")
    }

    override fun eventProperty(property: String, value: String) {
        val escaped = value.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")
        sendToJS("if(window.onMpvProperty)onMpvProperty('$property','$escaped')")
    }

    override fun eventProperty(property: String, value: Double) {
        sendToJS("if(window.onMpvProperty)onMpvProperty('$property',$value)")
    }

    override fun event(eventId: Int) {
        sendToJS("if(window.onMpvEvent)onMpvEvent($eventId)")
    }
}
