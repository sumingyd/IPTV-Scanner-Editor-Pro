package com.iptv.scanner.editor.pro.player

import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress
import java.net.URI

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
 *
 * 优化点：
 * - 持久化 DatagramSocket，避免每次通知创建/关闭 socket 的开销
 * - LEAVE+JOIN 合并为单个 UDP 包发送，减少网络往返
 * - UDP send() 本身非阻塞（fire-and-forget），无需额外线程
 */
object FccHelper {
    private const val TAG = "FccHelper"

    // 持久化 UDP socket —— 避免每次通知都创建/关闭 socket
    @Volatile
    private var persistentSock: DatagramSocket? = null
    private val sockLock = Any()

    internal fun getUdpSocket(): DatagramSocket {
        persistentSock?.let { return it }
        synchronized(sockLock) {
            persistentSock?.let { return it }
            // DatagramSocket.send() 对 UDP 是非阻塞的（fire-and-forget），
            // 不设置 soTimeout（仅影响 receive()）
            val sock = DatagramSocket()
            persistentSock = sock
            Log.d(TAG, "FCC持久化UDP socket已创建")
            return sock
        }
    }

    fun closeUdpSocket() {
        synchronized(sockLock) {
            persistentSock?.let {
                try { it.close() } catch (_: Exception) {}
            }
            persistentSock = null
        }
    }

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
            if (isMulticastIp(host) && uri.port > 0) {
                return Pair(host, uri.port)
            }
            val path = uri.path ?: return null
            val mcastRegex = Regex("""/rtp/(\d+\.\d+\.\d+\.\d+):(\d+)""")
            val match = mcastRegex.find(path) ?: return null
            val ip = match.groupValues[1]
            val port = match.groupValues[2].toIntOrNull() ?: return null
            if (isMulticastIp(ip)) Pair(ip, port) else null
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
     * 使用持久化 socket，LEAVE+JOIN 合并为单个 UDP 包。
     * @param fccIp FCC 代理IP
     * @param fccPort FCC 代理端口
     * @param leaveAddr 要离开的组播地址 (ip, port)，可为 null
     * @param joinAddr 要加入的组播地址 (ip, port)，可为 null
     * @return 是否发送成功
     */
    suspend fun sendFccNotification(
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

    private suspend fun sendUdp(ip: String, port: Int, data: ByteArray): Boolean = withContext(Dispatchers.IO) {
        try {
            val sock = getUdpSocket()
            val addr = InetAddress.getByName(ip)
            val packet = DatagramPacket(data, data.size, addr, port)
            sock.send(packet)
            Log.i(TAG, "FCC通知已发送: $ip:$port, 数据: ${String(data)}")
            true
        } catch (e: Exception) {
            Log.e(TAG, "FCC通知发送失败: ip=$ip port=$port error=${e.javaClass.simpleName}: ${e.message}", e)
            false
        }
    }
}

/**
 * FCC 快速换台服务管理器。
 * 跟踪当前播放频道的组播地址，换台时自动向 FCC 代理发送 leave/join。
 *
 * 与 PC 端 services/fcc_service.py FCCService 对齐。
 *
 * 优化点：
 * - LEAVE+JOIN 合并为单个 UDP 包，一次 socket 操作完成换台通知
 * - 使用持久化非阻塞 socket，消除每次创建/关闭 socket 的开销
 * - 无需额外线程：单包发送足够快（微秒级），不会阻塞 UI 线程
 */
class FccService {
    private var currentMulticast: Pair<String, Int>? = null
    private var currentFcc: Pair<String, Int>? = null

    /**
     * 频道切换时调用——合并 LEAVE+JOIN 为单个 UDP 包同步发送。
     * 非阻塞 socket + send() 耗时 < 0.1ms，无需异步线程。
     * @param newUrl 新频道的URL（含 ?fcc= 参数）
     */
    suspend fun onChannelChange(newUrl: String) {
        val fccAddr = FccHelper.parseFccFromUrl(newUrl)
        val newMulticast = FccHelper.parseMulticastFromUrl(newUrl)

        Log.i("FccService", "onChannelChange: fccAddr=$fccAddr, newMulticast=$newMulticast, url=$newUrl")

        if (fccAddr == null) {
            currentMulticast = newMulticast
            currentFcc = null
            return
        }

        val leaveAddr = currentMulticast
        val joinAddr = newMulticast

        currentMulticast = newMulticast
        currentFcc = fccAddr

        if (leaveAddr == joinAddr) return

        if (joinAddr != null || leaveAddr != null) {
            try {
                FccHelper.sendFccNotification(
                    fccAddr.first, fccAddr.second,
                    leaveAddr = leaveAddr,
                    joinAddr = joinAddr
                )
            } catch (e: Exception) {
                Log.e("FccService", "FCC通知发送失败: ${e.message}", e)
            }
        }
    }

    /**
     * 停止播放时调用——发送 leave 通知。
     */
    fun onStop() {
        val fcc = currentFcc
        val leave = currentMulticast
        if (fcc != null && leave != null) {
            try {
                val messages = "LEAVE ${leave.first} ${leave.second}\n"
                val payload = messages.toByteArray(Charsets.UTF_8)
                Thread {
                    try {
                        val sock = FccHelper.getUdpSocket()
                        val addr = InetAddress.getByName(fcc.first)
                        val packet = DatagramPacket(payload, payload.size, addr, fcc.second)
                        sock.send(packet)
                        Log.i("FccService", "FCC leave通知已发送: ${fcc.first}:${fcc.second}")
                    } catch (e: Exception) {
                        Log.e("FccService", "FCC leave通知失败: ${e.message}")
                    }
                }.start()
            } catch (e: Exception) {
                Log.e("FccService", "FCC leave通知失败: ${e.message}")
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
