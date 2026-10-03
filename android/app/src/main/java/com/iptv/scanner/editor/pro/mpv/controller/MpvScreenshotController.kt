package com.iptv.scanner.editor.pro.mpv.controller

import `is`.xyz.mpv.MPVLib

/**
 * 截图子控制器：screenshot-to-file 命令封装。
 */
class MpvScreenshotController(private val host: MpvControllerHost) {

    fun screenshotToFile(path: String, mode: String): Boolean {
        host.postOnUiThread { MPVLib.command(arrayOf("screenshot-to-file", path, mode)) }
        return true
    }
}