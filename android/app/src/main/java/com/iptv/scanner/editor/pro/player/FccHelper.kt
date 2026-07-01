package com.iptv.scanner.editor.pro.player

import android.util.Log
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress
import java.net.URI
import kotlin.concurrent.thread

/**
 * FCC (Fast Channel Change) 快速换台辅助类
 *
 * IPTV 组播场景中，FCC 代理用于加速频道切换：
 * - 客户端换台时通过 UDP 向 FCC 代理发送 leave/join 通知
 * - FCC 代理在服务端侧完成 IGMP leave/join，快速转发新频道流
 * - 客户端无需等待 IGMP 加入延迟
 *
 * URL 格式示例：
 *   rtp://239.1.1.1:5002?fcc=150.138.8.132:8027
 *   udp://239.2.1.5:5000?fcc=10.0.0.1:9000
 *   http://proxy/rtp/239.1.1.1:5002?fcc=150.138.8.132:8027
 *
 * FCC 通知协议（UDP 文本）：
 *   LEAVE <multicast_ip> <multicast_port>\n
 *   JOIN <multicast_ip> <multicast_port>\n
 *
 * 与 PC 端 services/fcc_service.py 对齐。
 */
object FccHelper {
    private const val TAG = "FccHelper"

    /**
     * 从频道 URL 中解析 FCC 代理地址。
     * @param url 频道URL，如 rtp://239.1.1.1:5002?fcc=150.138.8.132:8027
     * @return (fccIp, fccPort) 或 null
     */
    fun parseFccFromUrl(url: String?): Pair<String, Int>? {
        if (url == null || !url.contains("?fcc=", ignoreCase = true)) return null
        return try {
            val uri = URI(url)
            val query = uri.query ?: return null
            val params = mutableMapOf<String, String>()
            for (pair in query.split("&")) {
                val idx = pair.indexOf("=")
                if (idx >= 0) {
                    params[pair.substring(0, idx)] = pair.substring(idx + 1)
                }
            }
            val fccVal = params["fcc"] ?: return null
            if (fccVal.isBlank()) return null
            if (":" in fccVal) {
                val idx = fccVal.lastIndexOf(":")
                val ip = fccVal.substring(0, idx)
                val port = fccVal.substring(idx + 1).toInt()
                Pair(ip, port)
            } else {
                Pair(fccVal, 8027)
            }
        } catch (e: Exception) {
            Log.d(TAG, "解析FCC参数失败: ${e.message}, url=$url")
            null
        }
    }

    /**
     * 从 URL 中提取组播地址和端口。
     * @param url 如 rtp://239.1.1.1:5002?fcc=...
     * @return (multicastIp, multicastPort) 或 null（非组播地址时）
     */
    fun parseMulticastFromUrl(url: String?): Pair<String, Int>? {
        if (url == null) return null
        return try {
            val uri = URI(url)
            val host = uri.host ?: return null
            val port = uri.port
            if (port <= 0) return null
            if (!isMulticastIp(host)) return null
            Pair(host, port)
        } catch (e: Exception) {
            null
        }
    }

    /**
     * 判断是否为组播IP地址（224.0.0.0 ~ 239.255.255.255）
     */
    private fun isMulticastIp(ip: String): Boolean {
        return try {
            val parts = ip.split(".")
            if (parts.size != 4) return false
            val first = parts[0].toInt()
            first in 224..239
        } catch (e: Exception) {
            false
        }
    }

    /**
     * 向 FCC 代理发送换台通知（UDP）。
     * @param fccIp FCC 代理IP
     * @param fccPort FCC 代理端口
     * @param leaveAddr 要离开的组播地址 (ip, port)，可为 null
     * @param joinAddr 要加入的组播地址 (ip, port)，可为 null
     * @return 是否发送成功
     */
    fun sendFccNotification(
        fccIp: String,
        fccPort: Int,
        leaveAddr: Pair<String, Int>? = null,
        joinAddr: Pair<String, Int>? = null
    ): Boolean {
        val messages = mutableListOf<String>()
        if (leaveAddr != null) messages.add("LEAVE ${leaveAddr.first} ${leaveAddr.second}")
        if (joinAddr != null) messages.add("JOIN ${joinAddr.first} ${joinAddr.second}")
        if (messages.isEmpty()) return true

        val payload = (messages.joinToString("\n") + "\n").toByteArray(Charsets.UTF_8)
        return sendUdp(fccIp, fccPort, payload)
    }

    private fun sendUdp(ip: String, port: Int, data: ByteArray, timeoutMs: Int = 1000): Boolean {
        var sock: DatagramSocket? = null
        return try {
            sock = DatagramSocket()
            sock.soTimeout = timeoutMs
            val addr = InetAddress.getByName(ip)
            val packet = DatagramPacket(data, data.size, addr, port)
            sock.send(packet)
            Log.d(TAG, "FCC通知已发送: $ip:$port, 数据: ${String(data)}")
            true
        } catch (e: Exception) {
            Log.d(TAG, "FCC通知发送失败: ${e.message}")
            false
        } finally {
            sock?.close()
        }
    }

    /**
     * 从 URL 中提取原始播放地址（去除 FCC 代理参数）。
     *
     * 处理两种 URL 格式：
     * 1. 直接 RTP/UDP URL：rtp://239.1.1.1:5002?fcc=150.138.8.132:8027
     *    → 返回 rtp://239.1.1.1:5002（去除 ?fcc= 查询参数）
     * 2. HTTP 代理 URL：http://proxy/rtp/239.1.1.1:5002?fcc=150.138.8.132:8027
     *    → 返回 rtp://239.1.1.1:5002（从路径中提取 RTP 地址）
     *
     * 与 PC 端 mpv_player_service.py _extract_original_url() 对齐。
     */
    fun extractOriginalUrl(url: String): String {
        // 格式 2：HTTP 代理 URL（路径包含 /rtp/）
        if ("/rtp/" in url && "fcc=" in url) {
            try {
                val qIdx = url.indexOf("?")
                val pathPart = if (qIdx >= 0) url.substring(0, qIdx) else url
                val rtpIdx = pathPart.indexOf("/rtp/")
                if (rtpIdx >= 0) {
                    val rtpPart = pathPart.substring(rtpIdx + "/rtp/".length)
                    val originalUrl = "rtp://$rtpPart"
                    Log.i(TAG, "从 FCC URL 提取原始地址：$originalUrl")
                    return originalUrl
                }
            } catch (e: Exception) {
                Log.d(TAG, "提取原始 URL 失败: ${e.message}")
            }
        }

        // 格式 1：直接 RTP/UDP URL（去除 ?fcc= 查询参数）
        val fccIdx = url.indexOf("?fcc=", ignoreCase = true)
        if (fccIdx < 0) return url

        // 检查是否有其他查询参数（&）
        val ampIdx = url.indexOf('&', fccIdx)
        return if (ampIdx >= 0) {
            // 有其他参数：保留 ? 和其他参数，去掉 fcc= 部分
            url.substring(0, fccIdx) + "?" + url.substring(ampIdx + 1)
        } else {
            // 只有 fcc 参数：去掉整个 query
            url.substring(0, fccIdx)
        }
    }
}

/**
 * FCC 快速换台服务管理器。
 * 跟踪当前播放频道的组播地址，换台时自动向 FCC 代理发送 leave/join。
 *
 * 与 PC 端 services/fcc_service.py FCCService 对齐。
 */
class FccService {
    private var currentMulticast: Pair<String, Int>? = null
    private var currentFcc: Pair<String, Int>? = null

    /**
     * 频道切换时调用——同步发送 FCC join 通知，异步发送 leave 通知。
     * JOIN 同步发送确保新频道流尽快转发；LEAVE 异步发送避免阻塞切台流程。
     * @param newUrl 新频道的URL（含 ?fcc= 参数）
     */
    fun onChannelChange(newUrl: String) {
        val fccAddr = FccHelper.parseFccFromUrl(newUrl)
        val newMulticast = FccHelper.parseMulticastFromUrl(newUrl)

        if (fccAddr == null) {
            currentMulticast = newMulticast
            currentFcc = null
            return
        }

        val leaveAddr = currentMulticast
        val joinAddr = newMulticast

        currentMulticast = newMulticast
        currentFcc = fccAddr

        // 同一组播地址，无需通知
        if (leaveAddr == joinAddr) return

        // 同步发送 JOIN（快速加入新频道流）
        if (joinAddr != null) {
            try {
                FccHelper.sendFccNotification(fccAddr.first, fccAddr.second, null, joinAddr)
            } catch (e: Exception) {
                Log.d("FccService", "FCC join同步发送失败: ${e.message}")
            }
        }

        // 异步发送 LEAVE（不阻塞切台流程）
        if (leaveAddr != null) {
            thread(isDaemon = true, name = "fcc-leave") {
                try {
                    FccHelper.sendFccNotification(fccAddr.first, fccAddr.second, leaveAddr, null)
                } catch (e: Exception) {
                    Log.d("FccService", "FCC leave异步发送失败: ${e.message}")
                }
            }
        }
    }

    /**
     * 停止播放时调用——异步发送 leave 通知。
     */
    fun onStop() {
        val fcc = currentFcc
        val leave = currentMulticast
        if (fcc != null && leave != null) {
            thread(isDaemon = true, name = "fcc-stop") {
                try {
                    FccHelper.sendFccNotification(fcc.first, fcc.second, leave, null)
                } catch (e: Exception) {
                    Log.d("FccService", "FCC stop通知失败: ${e.message}")
                }
            }
        }
        currentMulticast = null
        currentFcc = null
    }

    /**
     * 重置状态（不发送 leave 通知）。
     */
    fun reset() {
        currentMulticast = null
        currentFcc = null
    }
}
