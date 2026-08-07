package com.iptv.scanner.editor.pro.ui

import android.util.Log
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

// =================================================================
// 性能优化：EPG 增量更新
// =================================================================
//
// 在 AppViewModel 中添加以下属性和方法：
//
// ```kotlin
// /** EPG 上次更新时间戳（用于增量更新判断） */
// private val _epgLastUpdateTime = MutableStateFlow(0L)
// val epgLastUpdateTime: StateFlow<Long> = _epgLastUpdateTime.asStateFlow()
//
// /** EPG 各源的缓存版本号（url -> version），用于增量更新判断 */
// private val _epgSourceVersions = MutableStateFlow<Map<String, Long>>(emptyMap())
// val epgSourceVersions: StateFlow<Map<String, Long>> = _epgSourceVersions.asStateFlow()
//
// /**
//  * EPG 增量更新：只重新下载变化的 EPG 源并合并。
//  *
//  * 策略：
//  * 1. 获取所有 EPG 源的 Last-Modified / ETag（通过 HTTP HEAD 请求）
//  * 2. 与 _epgSourceVersions 中缓存的上次版本比较
//  * 3. 只有变化的源才重新下载和解析
//  * 4. 合并到现有 EPG 缓存中
//  *
//  * 优点：避免每次全量重新下载所有 EPG 源（可能数十 MB），
//  * 只下载变化的源（通常 0-1 个），大幅减少网络流量和解析时间。
//  */
// fun incrementalEpgUpdate() {
//     viewModelScope.launch {
//         val epgSources = _epgSources.value
//         if (epgSources.isEmpty()) return@launch
//
//         val cachedVersions = _epgSourceVersions.value
//         val changedSources = mutableListOf<IptvEpgSource>()
//
//         // 检查每个源的 Last-Modified / ETag
//         for (source in epgSources) {
//             val lastVersion = cachedVersions[source.url] ?: 0L
//             val currentVersion = withContext(Dispatchers.IO) {
//                 // 通过 HTTP HEAD 获取 Last-Modified 或 ETag
//                 try {
//                     val conn = java.net.URL(source.url).openConnection() as java.net.HttpURLConnection
//                     conn.requestMethod = "HEAD"
//                     conn.connectTimeout = 5000
//                     conn.readTimeout = 5000
//                     conn.connect()
//                     // 使用 Last-Modified 或 ETag 作为版本标识
//                     val lastMod = conn.getLastModified()
//                     val etag = conn.getHeaderField("ETag") ?: ""
//                     conn.disconnect()
//                     if (lastMod > 0) lastMod else etag.hashCode().toLong().let { if (it < 0) -it else it }
//                 } catch (e: Exception) {
//                     Log.w(TAG, "EPG HEAD check failed for ${source.url}: ${e.message}")
//                     -1L // 检查失败，保守地认为需要重新下载
//                 }
//             }
//             if (currentVersion < 0 || currentVersion != lastVersion) {
//                 changedSources.add(source)
//             }
//         }
//
//         if (changedSources.isEmpty()) {
//             Log.i(TAG, "EPG incremental update: no changes detected")
//             showOsd("EPG", "已是最新")
//             return@launch
//         }
//
//         Log.i(TAG, "EPG incremental update: ${changedSources.size}/${epgSources.size} sources changed")
//
//         // 只重新加载变化的源
//         for (source in changedSources) {
//             repository.reloadEpg(source.url)
//         }
//
//         // 更新版本缓存
//         val newVersions = cachedVersions.toMutableMap()
//         for (source in changedSources) {
//             val conn = withContext(Dispatchers.IO) {
//                 try {
//                     val c = java.net.URL(source.url).openConnection() as java.net.HttpURLConnection
//                     c.requestMethod = "HEAD"
//                     c.connectTimeout = 5000
//                     c.connect()
//                     val mod = c.getLastModified()
//                     c.disconnect()
//                     mod
//                 } catch (_: Exception) { 0L }
//             }
//             newVersions[source.url] = conn
//         }
//         _epgSourceVersions.value = newVersions
//         _epgLastUpdateTime.value = System.currentTimeMillis()
//
//         // 重新加载 EPG 数据
//         loadCurrentEpg()
//         showOsd("EPG", "增量更新完成（${changedSources.size} 个源）")
//     }
// }
// ```

// =================================================================
// 性能优化：扫描进度通过 StateFlow 推送到 UI
// =================================================================
//
// 在 AppViewModel 中添加以下属性和方法：
//
// ```kotlin
// /** 扫描进度状态（实时推送到 UI） */
// data class ScanProgressState(
//     val active: Boolean = false,
//     val scanned: Int = 0,
//     val total: Int = 0,
//     val valid: Int = 0,
//     val invalid: Int = 0,
//     val currentIp: String = "",
//     val speed: Float = 0f,  // 每秒扫描数
//     val eta: Long = 0L,     // 预计剩余时间（秒）
//     val message: String = ""
// )
//
// private val _scanProgress = MutableStateFlow(ScanProgressState())
// val scanProgress: StateFlow<ScanProgressState> = _scanProgress.asStateFlow()
//
// /** 扫描进度推送定时器 */
// private var scanProgressJob: Job? = null
//
// /**
//  * 启动扫描进度推送。
//  *
//  * 在扫描启动时调用，每 500ms 从 repository 获取最新扫描状态并推送到 UI。
//  * 避免在主线程阻塞，通过 StateFlow 自动触发 UI 重组。
//  */
// fun startScanProgressPolling() {
//     scanProgressJob?.cancel()
//     scanProgressJob = viewModelScope.launch {
//         var lastScanned = 0
//         var lastTime = System.currentTimeMillis()
//         while (isActive) {
//             delay(500)
//             repository.getScanStatus().fold(
//                 onSuccess = { status ->
//                     val now = System.currentTimeMillis()
//                     val elapsed = (now - lastTime) / 1000.0
//                     val speed = if (elapsed > 0) {
//                         ((status.scanned - lastScanned) / elapsed).toFloat()
//                     } else 0f
//                     val eta = if (speed > 0 && status.total > 0) {
//                         ((status.total - status.scanned) / speed).toLong()
//                     } else 0L
//
//                     _scanProgress.value = ScanProgressState(
//                         active = status.active,
//                         scanned = status.scanned,
//                         total = status.total,
//                         valid = status.valid,
//                         invalid = status.invalid,
//                         currentIp = status.currentIp ?: "",
//                         speed = speed,
//                         eta = eta,
//                         message = status.message ?: ""
//                     )
//
//                     lastScanned = status.scanned
//                     lastTime = now
//
//                     if (!status.active) {
//                         // 扫描完成，停止轮询
//                         scanProgressJob?.cancel()
//                         scanProgressJob = null
//                     }
//                 },
//                 onFailure = { e ->
//                     Log.w(TAG, "scan progress poll failed: ${e.message}")
//                 }
//             )
//         }
//     }
// }
//
// /** 停止扫描进度推送 */
// fun stopScanProgressPolling() {
//     scanProgressJob?.cancel()
//     scanProgressJob = null
// }
// ```
//
// 在 ScanPanel.kt 中使用：
// ```kotlin
// @Composable
// fun ScanPanel(viewModel: AppViewModel) {
//     val scanProgress by viewModel.scanProgress.collectAsState()
//
//     if (scanProgress.active) {
//         // 显示实时进度条
//         LinearProgressIndicator(
//             progress = if (scanProgress.total > 0)
//                 scanProgress.scanned.toFloat() / scanProgress.total
//             else 0f,
//             modifier = Modifier.fillMaxWidth()
//         )
//         Text("已扫描 ${scanProgress.scanned}/${scanProgress.total} " +
//              "有效 ${scanProgress.valid} 无效 ${scanProgress.invalid}")
//         Text("速度: ${scanProgress.speed.toInt()}/s  " +
//              "预计剩余: ${scanProgress.eta / 60}分${scanProgress.eta % 60}秒")
//         if (scanProgress.currentIp.isNotEmpty()) {
//             Text("当前: ${scanProgress.currentIp}")
//         }
//     }
// }
// ```
