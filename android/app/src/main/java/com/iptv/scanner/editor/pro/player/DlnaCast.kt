package com.iptv.scanner.editor.pro.player

import android.content.Context
import android.net.wifi.WifiManager
import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.BufferedReader
import java.io.InputStream
import java.io.OutputStream
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.MulticastSocket
import java.net.Socket
import java.net.SocketTimeoutException
import java.util.Locale
import javax.xml.parsers.DocumentBuilderFactory

/**
 * DLNA 投屏：SSDP 设备搜索 + AVTransport SOAP 控制推流。
 *
 * 流程：
 * 1. search()：组播 M-SEARCH 到 239.255.255.250:1900，收集响应中的设备描述 URL
 * 2. 解析设备描述 XML：取 friendlyName + AVTransport service 的 controlURL
 * 3. cast()：SOAP SetAVTransportURI 把频道流 URL 交给电视播放器 + Play 启动
 * 4. stop()/pause()：SOAP 控制（电视端停止/暂停播放）
 */

/** 一台局域网内的 DLNA 渲染设备（电视/盒子） */
data class DlnaDevice(
    val name: String,
    /** 设备描述 XML 的 URL（http://ip:port/desc） */
    val location: String,
    /** AVTransport controlURL 的绝对地址 */
    val controlUrl: String,
    /** AVTransport serviceType（SOAP action 命名空间） */
    val serviceType: String,
    /** 设备 IP（用于展示） */
    val host: String
)

object DlnaCast {
    private const val TAG = "DlnaCast"
    private const val SSDP_ADDR = "239.255.255.250"
    private const val SSDP_PORT = 1900
    private const val SEARCH_ST = "urn:schemas-upnp-org:service:AVTransport:1"
    private const val SEARCH_TIMEOUT_MS = 4000

    /**
     * SSDP 搜索局域网内的 DLNA 渲染设备（AVTransport 服务）。
     * 返回解析完成的设备列表（可能为空：电视未开/不在同一网段）。
     */
    suspend fun search(context: Context): List<DlnaDevice> = withContext(Dispatchers.IO) {
        val multicastLock: WifiManager.MulticastLock? = try {
            val wm = context.applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
            wm.createMulticastLock("iptv-dlna-search").apply { setReferenceCounted(false); acquire() }
        } catch (e: Exception) {
            Log.w(TAG, "multicast lock failed: ${e.message}")
            null
        }
        try {
            val locations = mutableSetOf<String>()
            val socket = MulticastSocket(null).apply {
                reuseAddress = true
                bind(InetSocketAddress(SSDP_PORT + (0..2000).random()))
                soTimeout = 800
            }
            try {
                val group = InetAddress.getByName(SSDP_ADDR)
                val msearch = buildString {
                    append("M-SEARCH * HTTP/1.1\r\n")
                    append("HOST: $SSDP_ADDR:$SSDP_PORT\r\n")
                    append("MAN: \"ssdp:discover\"\r\n")
                    append("MX: 3\r\n")
                    append("ST: $SEARCH_ST\r\n\r\n")
                }.toByteArray()
                // 发 3 轮提高发现率
                repeat(3) {
                    socket.send(DatagramPacket(msearch, msearch.size, group, SSDP_PORT))
                    val buf = ByteArray(2048)
                    val deadline = System.currentTimeMillis() + 1200
                    while (System.currentTimeMillis() < deadline) {
                        try {
                            val pkt = DatagramPacket(buf, buf.size)
                            socket.receive(pkt)
                            val text = String(buf, 0, pkt.length, Charsets.UTF_8)
                            if (text.contains("AVTransport", ignoreCase = true)) {
                                val loc = Regex("(?i)LOCATION:\\s*(\\S+)").find(text)?.groupValues?.get(1)
                                if (loc != null) locations.add(loc)
                            }
                        } catch (_: SocketTimeoutException) {
                        }
                    }
                }
            } finally {
                socket.close()
            }
            Log.i(TAG, "ssdp found ${locations.size} AVTransport locations")
            locations.mapNotNull { parseDevice(it) }.distinctBy { it.host + it.name }
        } finally {
            try { multicastLock?.release() } catch (_: Exception) {}
        }
    }

    /** 解析设备描述 XML，提取名称与 AVTransport controlURL */
    private fun parseDevice(location: String): DlnaDevice? {
        return try {
            val url = java.net.URL(location)
            val xml = url.readText(Charsets.UTF_8)
            val factory = DocumentBuilderFactory.newInstance()
            factory.isNamespaceAware = true
            try {
                factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true)
            } catch (_: Exception) {
            }
            val doc = factory.newDocumentBuilder()
                .parse(java.io.ByteArrayInputStream(xml.toByteArray(Charsets.UTF_8)))
            val nameNode = doc.getElementsByTagName("friendlyName").item(0)
            val name = if (nameNode != null) nameNode.textContent.trim() else "未知设备"
            var serviceType = ""
            var controlPath = ""
            val services = doc.getElementsByTagName("service")
            val count = services.length
            for (i in 0 until count) {
                val node = services.item(i)
                val children = node.childNodes
                val n = children.length
                for (j in 0 until n) {
                    val child = children.item(j)
                    when (child.nodeName) {
                        "serviceType" -> if (child.textContent.contains("AVTransport")) {
                            serviceType = child.textContent.trim()
                        }
                        "controlURL" -> if (serviceType.isNotEmpty() && controlPath.isEmpty()) {
                            controlPath = child.textContent.trim()
                        }
                    }
                }
                if (serviceType.isNotEmpty() && controlPath.isNotEmpty()) break
            }
            if (serviceType.isEmpty() || controlPath.isEmpty()) {
                Log.w(TAG, "no AVTransport in $location")
                return null
            }
            val absControl = if (controlPath.startsWith("http")) controlPath
            else java.net.URL(url, controlPath).toString()
            DlnaDevice(
                name = name,
                location = location,
                controlUrl = absControl,
                serviceType = serviceType,
                host = url.host
            )
        } catch (e: Exception) {
            Log.w(TAG, "parseDevice failed: $location ${e.message}")
            null
        }
    }

    /** 投播：把流 URL 交给电视播放（SetAVTransportURI + Play） */
    suspend fun cast(device: DlnaDevice, mediaUrl: String, title: String): Boolean =
        withContext(Dispatchers.IO) {
            val okUri = soap(device, "SetAVTransportURI", """
                <InstanceID>0</InstanceID>
                <CurrentURI>${escape(mediaUrl)}</CurrentURI>
                <CurrentURIMetaData></CurrentURIMetaData>
            """.trimIndent())
            if (!okUri) return@withContext false
            // 部分电视需要小间隔再发 Play
            Thread.sleep(150)
            soap(device, "Play", "<InstanceID>0</InstanceID><Speed>1</Speed>")
        }

    /** 停止电视端播放 */
    suspend fun stop(device: DlnaDevice): Boolean = withContext(Dispatchers.IO) {
        soap(device, "Stop", "<InstanceID>0</InstanceID>")
    }

    /** SOAP AVTransport action 调用 */
    private fun soap(device: DlnaDevice, action: String, argsXml: String): Boolean {
        var socket: Socket? = null
        return try {
            val body = buildString {
                append("<?xml version=\"1.0\" encoding=\"utf-8\"?>")
                append("<s:Envelope xmlns:s=\"http://schemas.xmlsoap.org/soap/envelope/\" s:encodingStyle=\"http://schemas.xmlsoap.org/soap/encoding/\">")
                append("<s:Body><u:$action xmlns:u=\"${device.serviceType}\">")
                append(argsXml)
                append("</u:$action></s:Body></s:Envelope>")
            }
            val header = buildString {
                append("POST ${java.net.URL(device.controlUrl).path} HTTP/1.1\r\n")
                append("HOST: ${java.net.URL(device.controlUrl).authority}\r\n")
                append("CONTENT-LENGTH: ${body.toByteArray().size}\r\n")
                append("CONTENT-TYPE: text/xml; charset=\"utf-8\"\r\n")
                append("SOAPACTION: \"${device.serviceType}#$action\"\r\n\r\n")
            }
            val url = java.net.URL(device.controlUrl)
            socket = Socket()
            socket.connect(InetSocketAddress(url.host, if (url.port > 0) url.port else 80), 5000)
            socket.soTimeout = 8000
            val out: OutputStream = socket.getOutputStream()
            out.write((header + body).toByteArray(Charsets.UTF_8))
            out.flush()
            val reader = BufferedReader(
                java.io.InputStreamReader(socket.getInputStream(), Charsets.UTF_8)
            )
            val status = reader.readLine() ?: ""
            // 跳过 headers
            var line = reader.readLine()
            while (line != null && line.isNotEmpty()) line = reader.readLine()
            val ok = status.contains(" 200", ignoreCase = false)
            Log.i(TAG, "SOAP $action -> $status")
            ok
        } catch (e: Exception) {
            Log.w(TAG, "SOAP $action failed: ${e.message}")
            false
        } finally {
            try { socket?.close() } catch (_: Exception) {}
        }
    }

    private fun escape(s: String): String =
        s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\"", "&quot;")
}
