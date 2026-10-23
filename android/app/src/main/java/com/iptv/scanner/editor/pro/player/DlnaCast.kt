package com.iptv.scanner.editor.pro.player

import android.content.Context
import android.net.wifi.WifiManager
import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.withContext
import java.io.BufferedReader
import java.io.OutputStream
import java.net.DatagramPacket
import java.net.Inet4Address
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.MulticastSocket
import java.net.NetworkInterface
import java.net.Socket
import java.net.SocketTimeoutException
import javax.xml.parsers.DocumentBuilderFactory
import org.w3c.dom.Element
import org.w3c.dom.Node

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
    /** 监听窗口：覆盖搜索包发送 + 设备响应延迟（多数设备 1 秒内响应） */
    private const val SEARCH_TIMEOUT_MS = 4500L
    private const val DESC_TIMEOUT_MS = 3000
    /** 单次搜索最多解析的设备描述数量，避免 ssdp:all 返回过多条目 */
    private const val MAX_LOCATIONS = 32

    /**
     * 一次性发送多种搜索目标：不同电视的 SSDP 实现差异很大，
     * 部分机型只响应 MediaRenderer / ssdp:all，不响应 AVTransport 服务查询。
     */
    private val SEARCH_TARGETS = listOf(
        "urn:schemas-upnp-org:device:MediaRenderer:1",
        "urn:schemas-upnp-org:service:AVTransport:1",
        "ssdp:all"
    )

    /** SSDP 搜索局域网内的 DLNA 渲染设备（AVTransport 服务） */
    suspend fun search(context: Context): List<DlnaDevice> = discover(context, null)

    /**
     * 直接向指定 IP 发单播 M-SEARCH。
     * 组播被路由器/模拟器 NAT/AP 隔离拦截时，单播仍可拿到电视响应。
     */
    suspend fun searchHost(context: Context, host: String): List<DlnaDevice> =
        discover(context, host)

    private suspend fun discover(context: Context, directHost: String?): List<DlnaDevice> =
        withContext(Dispatchers.IO) {
            // 组播锁只对组播接收有意义；单播兜底不需要
            val multicastLock = if (directHost == null) acquireMulticastLock(context) else null
            try {
                val locations = collectLocations(directHost)
                Log.i(TAG, "ssdp found ${locations.size} locations (direct=$directHost)")
                if (locations.isEmpty()) return@withContext emptyList()
                val parsed = coroutineScope {
                    locations.take(MAX_LOCATIONS).map { loc ->
                        async(Dispatchers.IO) { parseDevice(loc) }
                    }.awaitAll()
                }
                parsed.filterNotNull().distinctBy { it.host + it.name }
            } finally {
                try { multicastLock?.release() } catch (_: Exception) {}
            }
        }

    private fun acquireMulticastLock(context: Context): WifiManager.MulticastLock? = try {
        val wm = context.applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
        wm.createMulticastLock("iptv-dlna-search").apply {
            setReferenceCounted(false)
            acquire()
        }
    } catch (e: Exception) {
        Log.w(TAG, "multicast lock failed: ${e.message}")
        null
    }

    /**
     * 发送 M-SEARCH 并收集所有响应里的 LOCATION。
     * 不再按响应头里的 AVTransport 过滤（ssdp:all 的响应头不含服务名），
     * 统一交给设备描述解析阶段判断是否具备 AVTransport 能力。
     */
    private fun collectLocations(directHost: String?): Set<String> {
        val locations = mutableSetOf<String>()
        val socket = MulticastSocket(null).apply {
            reuseAddress = true
            bind(InetSocketAddress(0))
            timeToLive = 2
            soTimeout = 400
        }
        try {
            try {
                preferredMulticastInterface()?.let { socket.networkInterface = it }
            } catch (e: Exception) {
                Log.w(TAG, "set multicast interface failed: ${e.message}")
            }
            if (directHost != null) {
                // 单播直连：仅探测用户指定的电视 IP
                val dest = InetAddress.getByName(directHost)
                repeat(2) { round ->
                    SEARCH_TARGETS.forEach { target ->
                        try {
                            socket.send(searchPacket(target, dest))
                        } catch (e: Exception) {
                            Log.w(TAG, "unicast send failed (${e.javaClass.simpleName}): ${e.message}")
                        }
                    }
                    if (round == 0) Thread.sleep(400)
                }
            } else {
                val group = InetAddress.getByName(SSDP_ADDR)
                // 两轮发送，间隔 400ms，提高丢包场景下的发现率
                repeat(2) { round ->
                    SEARCH_TARGETS.forEach { target ->
                        try { socket.send(searchPacket(target, group)) } catch (_: Exception) {}
                    }
                    if (round == 0) Thread.sleep(400)
                }
            }
            val deadline = System.currentTimeMillis() + SEARCH_TIMEOUT_MS
            val buf = ByteArray(4096)
            while (System.currentTimeMillis() < deadline) {
                try {
                    val pkt = DatagramPacket(buf, buf.size)
                    socket.receive(pkt)
                    val text = String(buf, 0, pkt.length, Charsets.UTF_8)
                    val loc = Regex("(?i)LOCATION:\\s*(\\S+)").find(text)?.groupValues?.get(1)
                    // 部分 NAS 会在响应里塞 127.0.0.1 的描述地址，无法从手机访问
                    if (loc != null && !loc.contains("127.0.0.1")) locations.add(loc)
                } catch (_: SocketTimeoutException) {
                } catch (e: Exception) {
                    Log.w(TAG, "ssdp receive failed: ${e.message}")
                }
            }
        } finally {
            try { socket.close() } catch (_: Exception) {}
        }
        return locations
    }

    private fun searchPacket(target: String, dest: InetAddress): DatagramPacket {
        // HOST 头按目标地址填写：组播时为组播地址，单播时为目标 IP
        // （RFC 2368 要求单播 M-SEARCH 的 HOST 指向探测目标）
        val host = if (dest is java.net.Inet4Address && !dest.isMulticastAddress) {
            dest.hostAddress ?: SSDP_ADDR
        } else {
            SSDP_ADDR
        }
        val payload = buildString {
            append("M-SEARCH * HTTP/1.1\r\n")
            append("HOST: $host:$SSDP_PORT\r\n")
            append("MAN: \"ssdp:discover\"\r\n")
            append("MX: 2\r\n")
            append("ST: $target\r\n")
            append("USER-AGENT: Android/1.0 UPnP/1.0 ISEP/1.0\r\n\r\n")
        }.toByteArray(Charsets.UTF_8)
        return DatagramPacket(payload, payload.size, dest, SSDP_PORT)
    }

    /**
     * 优先选择 Wi-Fi / 有线网卡发组播。
     * 多网卡（蜂窝、VPN、虚拟网卡）共存时，系统默认路由可能把组播发到错误的网卡。
     */
    private fun preferredMulticastInterface(): NetworkInterface? = try {
        NetworkInterface.getNetworkInterfaces().toList()
            .filter { it.isUp && !it.isLoopback && it.supportsMulticast() && it.hasIpv4() }
            .maxByOrNull { ni ->
                when {
                    ni.name.startsWith("wlan") -> 3
                    ni.name.startsWith("eth") -> 2
                    ni.name.startsWith("ap") -> 1
                    else -> 0
                }
            }
    } catch (_: Exception) {
        null
    }

    private fun NetworkInterface.hasIpv4(): Boolean =
        inetAddresses.toList().any { it is Inet4Address && !it.isLoopbackAddress }

    /** 解析设备描述 XML，提取名称与 AVTransport controlURL */
    private fun parseDevice(location: String): DlnaDevice? {
        return try {
            val url = java.net.URL(location)
            val xml = fetchText(url)
            val factory = DocumentBuilderFactory.newInstance()
            // 不做命名空间校验：部分电视（如 QQ 音乐 TV 版渲染器）的描述里
            // 含有未声明前缀的标签（<qq:...>），严格解析会直接抛异常。
            // 关闭后按标签名（去掉前缀）自行匹配，兼容性最好。
            factory.isNamespaceAware = false
            try {
                factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true)
            } catch (_: Exception) {
            }
            val doc = factory.newDocumentBuilder()
                .parse(java.io.ByteArrayInputStream(xml.toByteArray(Charsets.UTF_8)))
            val name = doc.elementsByLocalName("friendlyName")
                .firstOrNull()?.textContent?.trim().orEmpty().ifEmpty { "未知设备" }
            var serviceType = ""
            var controlPath = ""
            for (service in doc.elementsByLocalName("service")) {
                val st = service.directChildText("serviceType")
                if (!st.contains("AVTransport", ignoreCase = true)) continue
                val ctrl = service.directChildText("controlURL")
                if (ctrl.isNotEmpty()) {
                    serviceType = st
                    controlPath = ctrl
                    break
                }
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

    /** 读取设备描述：必须设置超时，否则个别不响应的设备会卡住整个搜索 */
    private fun fetchText(url: java.net.URL): String {
        val conn = url.openConnection()
        conn.connectTimeout = DESC_TIMEOUT_MS
        conn.readTimeout = DESC_TIMEOUT_MS
        conn.setRequestProperty("User-Agent", "Android/1.0 UPnP/1.0 ISEP/1.0")
        return conn.getInputStream().bufferedReader(Charsets.UTF_8).use { it.readText() }
    }

    /** 按标签本地名取所有元素（忽略命名空间前缀，配合非命名空间感知解析） */
    private fun org.w3c.dom.Document.elementsByLocalName(localName: String): List<Element> {
        val all = getElementsByTagName("*")
        val result = ArrayList<Element>()
        for (i in 0 until all.length) {
            val el = all.item(i) as? Element ?: continue
            val name = (el.localName ?: el.nodeName).substringAfter(':')
            if (name == localName) result.add(el)
        }
        return result
    }

    /** 取元素下指定本地名的直接子元素文本（兼容带命名空间前缀的描述 XML） */
    private fun Node.directChildText(localName: String): String {
        if (this !is Element) return ""
        val children = childNodes
        for (i in 0 until children.length) {
            val child = children.item(i)
            if (child is Element) {
                val name = (child.localName ?: child.nodeName).substringAfter(':')
                if (name == localName) return child.textContent?.trim().orEmpty()
            }
        }
        return ""
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
