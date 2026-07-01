package com.iptv.scanner.editor.pro.ui

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.QrCode
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Save
import androidx.compose.material.icons.filled.SettingsBackupRestore
import androidx.compose.material.icons.filled.Timer
import androidx.compose.material.icons.filled.Wifi
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.iptv.scanner.editor.pro.data.IptvEpgSource
import com.iptv.scanner.editor.pro.data.IptvSource
import com.iptv.scanner.editor.pro.ui.theme.tvFocusBorder

/**
 * 订阅源管理面板（全屏覆盖）。
 *
 * 与 PC 端 订阅源管理 对齐：
 * - 频道订阅源 Tab：URL + 名称 + 启用开关 + 删除 + 添加 + 重载
 * - EPG 订阅源 Tab：URL + 名称 + 删除 + 添加 + 重载
 * - 重载后自动轮询加载状态，完成后刷新频道列表
 */
@Composable
fun SourceManagerPanel(viewModel: AppViewModel) {
    val sourceTab by viewModel.sourceTab.collectAsState()
    val sources by viewModel.sources.collectAsState()
    val epgSources by viewModel.epgSources.collectAsState()
    val sourceLoading by viewModel.sourceLoading.collectAsState()
    val sourceMessage by viewModel.sourceMessage.collectAsState()
    val adminUrl by viewModel.adminServerUrl.collectAsState()
    val adminRunning by viewModel.adminServerRunning.collectAsState()
    val adminCountdown by viewModel.adminCountdown.collectAsState()
    var showQrCode by remember { mutableStateOf(false) }

    // server 启动时自动展开二维码（TV 端遥控器操作繁琐，省去额外点击）
    LaunchedEffect(adminRunning) {
        if (adminRunning) showQrCode = true
    }

    Surface(
        color = Color(0xF0121212),
        modifier = Modifier.fillMaxSize()
    ) {
        Column(
            modifier = Modifier.fillMaxSize().padding(16.dp)
        ) {
            // 标题栏
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = "订阅源管理",
                    style = MaterialTheme.typography.headlineSmall,
                    color = Color.White
                )
                Row(verticalAlignment = Alignment.CenterVertically) {
                    // 局域网管理按钮
                    IconButton(onClick = { viewModel.toggleAdminServer() }, modifier = Modifier.tvFocusBorder()) {
                        Icon(
                            Icons.Default.Wifi,
                            contentDescription = "局域网管理",
                            tint = if (adminRunning) Color(0xFF4CAF50) else Color.White
                        )
                    }
                    // 二维码按钮（仅在服务器运行时显示）
                    if (adminRunning) {
                        IconButton(onClick = { showQrCode = !showQrCode }, modifier = Modifier.tvFocusBorder()) {
                            Icon(
                                Icons.Default.QrCode,
                                contentDescription = "二维码",
                                tint = if (showQrCode) Color(0xFF4A9EFF) else Color.White
                            )
                        }
                    }
                    // 重载按钮
                    if (sourceLoading) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(20.dp),
                            color = Color(0xFF4A9EFF),
                            strokeWidth = 2.dp
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                    } else {
                        IconButton(onClick = {
                            if (sourceTab == AppViewModel.SourceTab.PLAYLIST) {
                                viewModel.reloadSources()
                            } else {
                                viewModel.reloadEpgSources()
                            }
                        }, modifier = Modifier.tvFocusBorder()) {
                            Icon(Icons.Default.Refresh, contentDescription = "重载", tint = Color.White)
                        }
                    }
                    // 关闭按钮
                    IconButton(onClick = { viewModel.toggleSourceManager() }, modifier = Modifier.tvFocusBorder()) {
                        Icon(Icons.Default.Close, contentDescription = "关闭", tint = Color.White)
                    }
                }
            }

            // 局域网管理提示
            if (adminRunning && adminUrl.isNotEmpty()) {
                Spacer(modifier = Modifier.height(8.dp))
                LanAdminInfoBar(
                    url = adminUrl,
                    showQrCode = showQrCode,
                    onToggleQr = { showQrCode = it },
                    countdown = adminCountdown
                )
                // 自动关闭开关
                AdminAutoStopToggle(viewModel = viewModel)
            } else if (!adminRunning) {
                Spacer(modifier = Modifier.height(8.dp))
                Surface(
                    color = Color(0xFF1A237E),
                    shape = RoundedCornerShape(8.dp),
                    modifier = Modifier.fillMaxWidth().clickable { viewModel.toggleAdminServer() }
                ) {
                    Row(
                        modifier = Modifier.padding(12.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Icon(Icons.Default.Wifi, contentDescription = null, tint = Color(0xFF90CAF9))
                        Spacer(modifier = Modifier.width(8.dp))
                        Column {
                            Text(
                                text = "启动局域网管理",
                                style = MaterialTheme.typography.bodyMedium,
                                color = Color.White
                            )
                            Text(
                                text = "TV 端用遥控器输入不便，点击启动后用手机浏览器扫码管理",
                                style = MaterialTheme.typography.bodySmall,
                                color = Color(0xFF90CAF9)
                            )
                        }
                    }
                }
                // 自动关闭开关（启动前也可设置）
                AdminAutoStopToggle(viewModel = viewModel)
            }

            Spacer(modifier = Modifier.height(12.dp))

            // 备份与恢复（解决卸载重装/签名切换导致的数据丢失问题）
            BackupRestoreBar(viewModel)

            Spacer(modifier = Modifier.height(12.dp))

            // Tab 切换
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                FilterChip(
                    selected = sourceTab == AppViewModel.SourceTab.PLAYLIST,
                    onClick = { viewModel.setSourceTab(AppViewModel.SourceTab.PLAYLIST) },
                    label = { Text("频道源 (${sources.size})") }
                )
                FilterChip(
                    selected = sourceTab == AppViewModel.SourceTab.EPG,
                    onClick = { viewModel.setSourceTab(AppViewModel.SourceTab.EPG) },
                    label = { Text("EPG 源 (${epgSources.size})") }
                )
            }

            // 加载消息
            if (sourceMessage.isNotEmpty()) {
                Spacer(modifier = Modifier.height(8.dp))
                Text(
                    text = sourceMessage,
                    style = MaterialTheme.typography.bodySmall,
                    color = Color(0xFFCCCCCC),
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis
                )
            }

            Spacer(modifier = Modifier.height(12.dp))

            // 添加订阅源输入框
            when (sourceTab) {
                AppViewModel.SourceTab.PLAYLIST -> {
                    AddSourceRow(
                        placeholder = "输入 M3U 订阅源 URL",
                        onAdd = { url, name -> viewModel.addSource(url, name) }
                    )
                }
                AppViewModel.SourceTab.EPG -> {
                    AddSourceRow(
                        placeholder = "输入 EPG 订阅源 URL（XMLTV）",
                        onAdd = { url, name -> viewModel.addEpgSource(url, name) }
                    )
                }
            }

            Spacer(modifier = Modifier.height(12.dp))

            // 列表
            when (sourceTab) {
                AppViewModel.SourceTab.PLAYLIST -> {
                    if (sources.isEmpty()) {
                        EmptyHint("暂无频道订阅源，点击上方输入框添加")
                    } else {
                        LazyColumn(
                            modifier = Modifier.fillMaxSize(),
                            verticalArrangement = Arrangement.spacedBy(8.dp)
                        ) {
                            itemsIndexed(sources) { idx, source ->
                                SourceItem(
                                    source = source,
                                    index = idx,
                                    onToggle = { enabled -> viewModel.toggleSourceEnabled(idx, enabled) },
                                    onDelete = { viewModel.deleteSource(idx) }
                                )
                            }
                        }
                    }
                }
                AppViewModel.SourceTab.EPG -> {
                    if (epgSources.isEmpty()) {
                        EmptyHint("暂无 EPG 订阅源，点击上方输入框添加")
                    } else {
                        LazyColumn(
                            modifier = Modifier.fillMaxSize(),
                            verticalArrangement = Arrangement.spacedBy(8.dp)
                        ) {
                            itemsIndexed(epgSources) { idx, source ->
                                EpgSourceItem(
                                    source = source,
                                    index = idx,
                                    onDelete = { viewModel.deleteEpgSource(idx) }
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}

/**
 * 添加订阅源输入行
 */
@Composable
private fun AddSourceRow(placeholder: String, onAdd: (url: String, name: String) -> Unit) {
    var url by remember { mutableStateOf("") }
    var name by remember { mutableStateOf("") }

    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        OutlinedTextField(
            value = url,
            onValueChange = { url = it },
            placeholder = { Text(placeholder, color = Color(0xFF888888)) },
            modifier = Modifier.weight(1f),
            singleLine = true,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri),
            shape = RoundedCornerShape(8.dp)
        )
        OutlinedTextField(
            value = name,
            onValueChange = { name = it },
            placeholder = { Text("名称（可选）", color = Color(0xFF888888)) },
            modifier = Modifier.width(120.dp),
            singleLine = true,
            shape = RoundedCornerShape(8.dp)
        )
        IconButton(
            onClick = {
                if (url.isNotBlank()) {
                    onAdd(url.trim(), name.trim())
                    url = ""
                    name = ""
                }
            },
            modifier = Modifier.tvFocusBorder()
        ) {
            Icon(Icons.Default.Add, contentDescription = "添加", tint = Color(0xFF4A9EFF))
        }
    }
}

/**
 * 频道订阅源列表项
 */
@Composable
private fun SourceItem(
    source: IptvSource,
    index: Int,
    onToggle: (Boolean) -> Unit,
    onDelete: () -> Unit
) {
    Surface(
        color = Color(0xFF1E1E1E),
        shape = RoundedCornerShape(8.dp),
        modifier = Modifier.fillMaxWidth()
    ) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(12.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = source.name.ifEmpty { "订阅源 ${index + 1}" },
                    style = MaterialTheme.typography.bodyMedium,
                    color = Color.White,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
                Spacer(modifier = Modifier.height(2.dp))
                Text(
                    text = source.url,
                    style = MaterialTheme.typography.bodySmall,
                    color = Color(0xFF888888),
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
                if (source.lastUpdate != null && source.lastUpdate!!.isNotEmpty()) {
                    Text(
                        text = "更新: ${source.lastUpdate}",
                        style = MaterialTheme.typography.labelSmall,
                        color = Color(0xFF666666)
                    )
                }
            }
            // 启用开关
            Switch(
                checked = source.enabled,
                onCheckedChange = onToggle,
                modifier = Modifier.tvFocusBorder()
            )
            Spacer(modifier = Modifier.width(8.dp))
            // 删除按钮
            IconButton(onClick = onDelete, modifier = Modifier.tvFocusBorder()) {
                Icon(Icons.Default.Delete, contentDescription = "删除", tint = Color(0xFFE57373))
            }
        }
    }
}

/**
 * EPG 订阅源列表项
 */
@Composable
private fun EpgSourceItem(
    source: IptvEpgSource,
    index: Int,
    onDelete: () -> Unit
) {
    Surface(
        color = Color(0xFF1E1E1E),
        shape = RoundedCornerShape(8.dp),
        modifier = Modifier.fillMaxWidth()
    ) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(12.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = source.name.ifEmpty { "EPG 源 ${index + 1}" },
                    style = MaterialTheme.typography.bodyMedium,
                    color = Color.White,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
                Spacer(modifier = Modifier.height(2.dp))
                Text(
                    text = source.url,
                    style = MaterialTheme.typography.bodySmall,
                    color = Color(0xFF888888),
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
                if (source.lastUpdate != null && source.lastUpdate!!.isNotEmpty()) {
                    Text(
                        text = "更新: ${source.lastUpdate}",
                        style = MaterialTheme.typography.labelSmall,
                        color = Color(0xFF666666)
                    )
                }
            }
            IconButton(onClick = onDelete, modifier = Modifier.tvFocusBorder()) {
                Icon(Icons.Default.Delete, contentDescription = "删除", tint = Color(0xFFE57373))
            }
        }
    }
}

@Composable
private fun EmptyHint(text: String) {
    Box(
        modifier = Modifier.fillMaxWidth().padding(32.dp),
        contentAlignment = Alignment.Center
    ) {
        Text(
            text = text,
            style = MaterialTheme.typography.bodyMedium,
            color = Color(0xFF888888)
        )
    }
}

/**
 * 局域网管理自动关闭开关
 * 开启后 5 分钟自动停止服务器，关闭后持续运行直到手动停止
 */
@Composable
private fun AdminAutoStopToggle(viewModel: AppViewModel) {
    var autoStop by remember { mutableStateOf(viewModel.getAdminAutoStop()) }
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 4.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Icon(
            imageVector = Icons.Default.Timer,
            contentDescription = null,
            tint = Color(0xFFAAAAAA),
            modifier = Modifier.size(18.dp)
        )
        Spacer(modifier = Modifier.width(8.dp))
        Text(
            text = "5 分钟自动关闭",
            style = MaterialTheme.typography.bodySmall,
            color = Color(0xFFCCCCCC),
            modifier = Modifier.weight(1f)
        )
        Switch(
            checked = autoStop,
            onCheckedChange = {
                autoStop = it
                viewModel.setAdminAutoStop(it)
            },
            modifier = Modifier.tvFocusBorder()
        )
    }
}

/**
 * 局域网管理信息栏（含二维码展开和自动停止倒计时）
 */
@Composable
private fun LanAdminInfoBar(
    url: String,
    showQrCode: Boolean,
    onToggleQr: (Boolean) -> Unit,
    countdown: Int = 0
) {
    Column {
        Surface(
            color = Color(0xFF1B5E20),
            shape = RoundedCornerShape(8.dp),
            modifier = Modifier.fillMaxWidth()
        ) {
            Row(
                modifier = Modifier.padding(12.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Icon(Icons.Default.Wifi, contentDescription = null, tint = Color(0xFFA5D6A7))
                Spacer(modifier = Modifier.width(8.dp))
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = "局域网管理已启动",
                        style = MaterialTheme.typography.bodyMedium,
                        color = Color.White
                    )
                    Text(
                        text = "$url/",
                        style = MaterialTheme.typography.bodySmall,
                        color = Color(0xFFA5D6A7),
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                }
                // 倒计时显示（mm:ss 格式）
                if (countdown > 0) {
                    val mm = countdown / 60
                    val ss = countdown % 60
                    Text(
                        text = "%d:%02d".format(mm, ss),
                        style = MaterialTheme.typography.bodyMedium,
                        color = Color(0xFFFFCC80),
                        modifier = Modifier.padding(end = 4.dp)
                    )
                }
                IconButton(onClick = { onToggleQr(!showQrCode) }, modifier = Modifier.tvFocusBorder()) {
                    Icon(
                        Icons.Default.QrCode,
                        contentDescription = "二维码",
                        tint = if (showQrCode) Color(0xFF4A9EFF) else Color.White
                    )
                }
            }
        }

        if (showQrCode) {
            Spacer(modifier = Modifier.height(12.dp))
            Surface(
                color = Color.White,
                shape = RoundedCornerShape(12.dp),
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(
                    modifier = Modifier.fillMaxWidth().padding(16.dp),
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {
                    Text(
                        text = "扫码管理",
                        style = MaterialTheme.typography.titleMedium,
                        color = Color.Black
                    )
                    Spacer(modifier = Modifier.height(8.dp))
                    // 生成二维码
                    val qrBitmap = remember(url) { QrCodeUtil.generate("$url/", 512) }
                    if (qrBitmap != null) {
                        Image(
                            bitmap = qrBitmap.asImageBitmap(),
                            contentDescription = "局域网管理二维码",
                            modifier = Modifier.size(240.dp)
                        )
                    } else {
                        Text(
                            text = "二维码生成失败",
                            style = MaterialTheme.typography.bodySmall,
                            color = Color.Red
                        )
                    }
                    Spacer(modifier = Modifier.height(8.dp))
                    Text(
                        text = "手机浏览器扫码或输入上方地址",
                        style = MaterialTheme.typography.bodySmall,
                        color = Color(0xFF666666)
                    )
                }
            }
        }
    }
}

/**
 * 备份与恢复操作栏
 *
 * 解决 debug→release 签名切换 / 卸载重装 导致的数据丢失问题：
 * - 导出：打包订阅源 + EPG 源 + 收藏/历史/队列 + 播放器设置，写入 Downloads/IPTV_backup_*.json
 * - 恢复：通过 SAF（Storage Access Framework）选择备份文件，恢复所有配置并触发 reload
 *
 * TV 端友好：用 OutlinedButton（可聚焦、方向键选中、OK 键触发）
 */
@Composable
private fun BackupRestoreBar(viewModel: AppViewModel) {
    // SAF 文件选择器：让用户选择 JSON 备份文件恢复
    val pickFileLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.OpenDocument()
    ) { uri ->
        // uri 可能为 null（用户取消选择）
        if (uri != null) {
            viewModel.importConfig(uri)
        }
    }

    Surface(
        color = Color(0xFF263238),
        shape = RoundedCornerShape(8.dp),
        modifier = Modifier.fillMaxWidth()
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            // 标题行：图标 + 标题 + 说明
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Default.Save, contentDescription = null, tint = Color(0xFF90CAF9))
                Spacer(modifier = Modifier.width(8.dp))
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = "备份与恢复",
                        style = MaterialTheme.typography.bodyMedium,
                        color = Color.White
                    )
                    Text(
                        text = "导出配置到下载目录，重装/换机后可恢复",
                        style = MaterialTheme.typography.bodySmall,
                        color = Color(0xFFB0BEC5)
                    )
                }
            }

            Spacer(modifier = Modifier.height(8.dp))

            // 操作按钮行：导出 / 恢复
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(
                    onClick = { viewModel.exportConfig() },
                    modifier = Modifier.weight(1f).tvFocusBorder()
                ) {
                    Icon(Icons.Default.Save, contentDescription = null, tint = Color(0xFF4A9EFF))
                    Spacer(modifier = Modifier.width(4.dp))
                    Text("导出配置")
                }
                OutlinedButton(
                    onClick = { pickFileLauncher.launch(arrayOf("application/json")) },
                    modifier = Modifier.weight(1f).tvFocusBorder()
                ) {
                    Icon(
                        Icons.Default.SettingsBackupRestore,
                        contentDescription = null,
                        tint = Color(0xFF66BB6A)
                    )
                    Spacer(modifier = Modifier.width(4.dp))
                    Text("恢复配置")
                }
            }
        }
    }
}
