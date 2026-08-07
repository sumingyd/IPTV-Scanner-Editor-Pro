package com.iptv.scanner.editor.pro.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.iptv.scanner.editor.pro.data.IptvChannel
import com.iptv.scanner.editor.pro.ui.theme.tvFocusBorder

// =================================================================
// 频道编辑功能：编辑对话框 + 批量编辑面板
// =================================================================

/**
 * 频道编辑对话框。
 *
 * 支持编辑频道名称、URL、分组、台标 URL。
 * 通过 viewModel 调用 repository.updateChannel() 保存。
 */
@Composable
fun ChannelEditDialog(
    viewModel: AppViewModel,
    channel: IptvChannel,
    onDismiss: () -> Unit
) {
    var name by remember { mutableStateOf(channel.name) }
    var url by remember { mutableStateOf(channel.url) }
    var group by remember { mutableStateOf(channel.group) }
    var logo by remember { mutableStateOf(channel.logo) }
    var saving by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf("") }

    val channels by viewModel.channels.collectAsState()
    val idx = channels.indexOf(channel)

    AlertDialog(
        onDismissRequest = { if (!saving) onDismiss() },
        title = { Text("编辑频道") },
        text = {
            Column(modifier = Modifier.fillMaxWidth()) {
                OutlinedTextField(
                    value = name,
                    onValueChange = { name = it },
                    label = { Text("频道名称") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp)
                )
                OutlinedTextField(
                    value = url,
                    onValueChange = { url = it },
                    label = { Text("频道 URL") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp)
                )
                OutlinedTextField(
                    value = group,
                    onValueChange = { group = it },
                    label = { Text("分组") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp)
                )
                OutlinedTextField(
                    value = logo,
                    onValueChange = { logo = it },
                    label = { Text("台标 URL") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp)
                )
                if (error.isNotEmpty()) {
                    Text(error, color = MaterialTheme.colorScheme.error, fontSize = 12.sp,
                        modifier = Modifier.padding(top = 4.dp))
                }
            }
        },
        confirmButton = {
            Button(
                onClick = {
                    if (idx < 0) { onDismiss(); return@Button }
                    saving = true
                    error = ""
                    viewModel.updateChannel(idx, mapOf(
                        "name" to name.trim(),
                        "url" to url.trim(),
                        "group" to group.trim(),
                        "tvg-logo" to logo.trim()
                    ))
                    saving = false
                    onDismiss()
                },
                enabled = !saving && name.isNotBlank() && url.isNotBlank()
            ) {
                if (saving) {
                    CircularProgressIndicator(modifier = Modifier.size(16.dp), strokeWidth = 2.dp)
                } else {
                    Text("保存")
                }
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss, enabled = !saving) { Text("取消") }
        }
    )
}

// =================================================================
// 频道去重 UI
// =================================================================

/**
 * 频道去重面板。
 *
 * 检测重复频道（按名称/URL/名称+URL），显示重复列表，
 * 用户选择保留哪个，删除其余。
 */
@Composable
fun ChannelDedupPanel(
    viewModel: AppViewModel,
    onDismiss: () -> Unit
) {
    val channels by viewModel.channels.collectAsState()
    val oc = rememberPlayerOverlayColors()

    // 去重模式
    var dedupMode by remember { mutableStateOf(DedupMode.NAME_URL) }

    // 检测重复
    val duplicates = remember(channels, dedupMode) {
        findDuplicates(channels, dedupMode)
    }

    // 已选保留项
    val keepIndices = remember { mutableStateListOf<Int>() }

    Surface(
        color = MaterialTheme.colorScheme.surface,
        modifier = Modifier.fillMaxSize()
    ) {
        Column(modifier = Modifier.fillMaxSize().padding(16.dp)) {
            // 标题栏
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Column {
                    Text("频道去重", style = MaterialTheme.typography.titleMedium,
                        color = MaterialTheme.colorScheme.onSurface, fontWeight = FontWeight.SemiBold)
                    Text("发现 ${duplicates.size} 组重复频道",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                IconButton(onClick = onDismiss) {
                    Icon(Icons.Default.Close, contentDescription = "关闭")
                }
            }

            Spacer(modifier = Modifier.height(12.dp))

            // 去重模式选择
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                FilterChip(
                    selected = dedupMode == DedupMode.NAME,
                    onClick = { dedupMode = DedupMode.NAME },
                    label = { Text("按名称") }
                )
                FilterChip(
                    selected = dedupMode == DedupMode.URL,
                    onClick = { dedupMode = DedupMode.URL },
                    label = { Text("按 URL") }
                )
                FilterChip(
                    selected = dedupMode == DedupMode.NAME_URL,
                    onClick = { dedupMode = DedupMode.NAME_URL },
                    label = { Text("名称+URL") }
                )
            }

            Spacer(modifier = Modifier.height(12.dp))

            if (duplicates.isEmpty()) {
                Box(
                    modifier = Modifier.fillMaxSize(),
                    contentAlignment = Alignment.Center
                ) {
                    Text("未发现重复频道", color = MaterialTheme.colorScheme.onSurfaceVariant,
                        fontSize = 14.sp)
                }
            } else {
                // 重复列表
                LazyColumn(
                    modifier = Modifier.weight(1f),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    itemsIndexed(duplicates) { _, group ->
                        DuplicateGroupItem(
                            group = group,
                            keepIndices = keepIndices,
                            onDelete = { idx ->
                                viewModel.deleteChannel(idx)
                            }
                        )
                    }
                }

                Spacer(modifier = Modifier.height(12.dp))

                // 操作按钮
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    Button(
                        onClick = {
                            // 自动保留每组第一个，删除其余
                            duplicates.forEach { group ->
                                group.drop(1).forEach { (_, idx) ->
                                    viewModel.deleteChannel(idx)
                                }
                            }
                            onDismiss()
                        },
                        modifier = Modifier.weight(1f)
                    ) {
                        Text("自动去重（保留首个）")
                    }
                    TextButton(onClick = onDismiss) { Text("关闭") }
                }
            }
        }
    }
}

@Composable
private fun DuplicateGroupItem(
    group: List<Pair<IptvChannel, Int>>,
    keepIndices: MutableList<Int>,
    onDelete: (Int) -> Unit
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant
        )
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            Text("重复组（${group.size} 个）",
                fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant,
                fontWeight = FontWeight.Medium)
            Spacer(modifier = Modifier.height(8.dp))
            group.forEach { (channel, idx) ->
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(vertical = 4.dp)
                        .clickable {
                            // 切换保留选择
                            if (keepIndices.contains(idx)) {
                                keepIndices.remove(idx)
                            } else {
                                keepIndices.add(idx)
                            }
                        },
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    val isKept = keepIndices.contains(idx) || keepIndices.isEmpty()
                    Icon(
                        imageVector = if (isKept) Icons.Default.Check else Icons.Default.Delete,
                        contentDescription = null,
                        tint = if (isKept) MaterialTheme.colorScheme.primary
                               else MaterialTheme.colorScheme.error,
                        modifier = Modifier.size(20.dp)
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Column(modifier = Modifier.weight(1f)) {
                        Text(channel.name, fontSize = 13.sp, maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                            color = MaterialTheme.colorScheme.onSurface)
                        Text(channel.url, fontSize = 10.sp, maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                            color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    IconButton(
                        onClick = { onDelete(idx) },
                        modifier = Modifier.size(32.dp)
                    ) {
                        Icon(Icons.Default.Delete, contentDescription = "删除",
                            tint = MaterialTheme.colorScheme.error, modifier = Modifier.size(16.dp))
                    }
                }
            }
        }
    }
}

enum class DedupMode(val displayName: String) {
    NAME("按名称"),
    URL("按 URL"),
    NAME_URL("名称+URL")
}

private fun findDuplicates(
    channels: List<IptvChannel>,
    mode: DedupMode
): List<List<Pair<IptvChannel, Int>>> {
    val groups = mutableMapOf<String, MutableList<Pair<IptvChannel, Int>>>()
    channels.forEachIndexed { idx, ch ->
        val key = when (mode) {
            DedupMode.NAME -> ch.name.lowercase().trim()
            DedupMode.URL -> ch.url.trim()
            DedupMode.NAME_URL -> "${ch.name.lowercase().trim()}|${ch.url.trim()}"
        }
        groups.getOrPut(key) { mutableListOf() }.add(ch to idx)
    }
    return groups.values.filter { it.size > 1 }
}

// =================================================================
// 自动分类 / 名称清理面板
// =================================================================

/**
 * 自动分类与名称清理面板。
 *
 * 功能：
 * - 自动分类：按规则自动将频道归类到对应分组
 * - 名称清理：去除多余括号、HD/4K 后缀、空格等
 * - 匹配台标：批量匹配频道台标
 *
 * 调用 viewModel.batchEditChannels() 触发后端处理。
 */
@Composable
fun ChannelBatchOpsPanel(
    viewModel: AppViewModel,
    onDismiss: () -> Unit
) {
    var processing by remember { mutableStateOf(false) }
    var resultMsg by remember { mutableStateOf("") }
    var overwriteGroups by remember { mutableStateOf(false) }
    var overwriteLogo by remember { mutableStateOf(true) }

    Surface(
        color = MaterialTheme.colorScheme.surface,
        modifier = Modifier.fillMaxSize()
    ) {
        Column(modifier = Modifier.fillMaxSize().padding(16.dp)) {
            // 标题栏
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Text("批量操作", style = MaterialTheme.typography.titleMedium,
                    color = MaterialTheme.colorScheme.onSurface, fontWeight = FontWeight.SemiBold)
                IconButton(onClick = onDismiss) {
                    Icon(Icons.Default.Close, contentDescription = "关闭")
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            if (processing) {
                Box(
                    modifier = Modifier.fillMaxSize(),
                    contentAlignment = Alignment.Center
                ) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        CircularProgressIndicator()
                        Spacer(modifier = Modifier.height(12.dp))
                        Text("处理中...", color = MaterialTheme.colorScheme.onSurfaceVariant,
                            fontSize = 14.sp)
                    }
                }
                return@Column
            }

            if (resultMsg.isNotEmpty()) {
                Card(
                    modifier = Modifier.fillMaxWidth().padding(bottom = 12.dp),
                    colors = CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.3f)
                    )
                ) {
                    Text(resultMsg, modifier = Modifier.padding(12.dp),
                        color = MaterialTheme.colorScheme.onSurface, fontSize = 13.sp)
                }
            }

            // 自动分类
            BatchOpCard(
                title = "自动分类",
                description = "按频道名称规则自动归类到对应分组（央视/卫视/地方/4K等）"
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text("覆盖已有分组", fontSize = 12.sp,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.weight(1f))
                    Switch(
                        checked = overwriteGroups,
                        onCheckedChange = { overwriteGroups = it }
                    )
                }
                Spacer(modifier = Modifier.height(8.dp))
                Button(
                    onClick = {
                        processing = true
                        viewModel.batchEditChannels("auto_classify",
                            "{\"overwrite\": $overwriteGroups}")
                    },
                    modifier = Modifier.fillMaxWidth()
                ) { Text("执行自动分类") }
            }

            Spacer(modifier = Modifier.height(12.dp))

            // 名称清理
            BatchOpCard(
                title = "名称清理",
                description = "去除多余括号、HD/4K 后缀、空格等，规范化频道名"
            ) {
                Button(
                    onClick = {
                        processing = true
                        viewModel.batchEditChannels("clean_names", "{}")
                    },
                    modifier = Modifier.fillMaxWidth()
                ) { Text("执行名称清理") }
            }

            Spacer(modifier = Modifier.height(12.dp))

            // 匹配台标
            BatchOpCard(
                title = "匹配台标",
                description = "批量匹配频道台标图片"
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text("仅填充空位", fontSize = 12.sp,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.weight(1f))
                    Switch(
                        checked = !overwriteLogo,
                        onCheckedChange = { overwriteLogo = !it }
                    )
                }
                Spacer(modifier = Modifier.height(8.dp))
                Button(
                    onClick = {
                        processing = true
                        viewModel.batchEditChannels("match_logo",
                            "{\"overwrite\": $overwriteLogo}")
                    },
                    modifier = Modifier.fillMaxWidth()
                ) { Text("执行台标匹配") }
            }

            Spacer(modifier = Modifier.height(12.dp))

            // 按组排序
            BatchOpCard(
                title = "按组排序",
                description = "按频道分组自动排序"
            ) {
                Button(
                    onClick = {
                        processing = true
                        viewModel.batchEditChannels("sort_by_group", "{}")
                    },
                    modifier = Modifier.fillMaxWidth()
                ) { Text("执行排序") }
            }
        }
    }

    // 监听批量编辑结果
    val batchResult by viewModel.batchEditResult.collectAsState()
    LaunchedEffect(batchResult) {
        if (batchResult.isNotEmpty()) {
            processing = false
            resultMsg = batchResult
        }
    }
}

@Composable
private fun BatchOpCard(
    title: String,
    description: String,
    content: @Composable () -> Unit
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant
        )
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            Text(title, fontSize = 15.sp, fontWeight = FontWeight.Medium,
                color = MaterialTheme.colorScheme.onSurface)
            Spacer(modifier = Modifier.height(4.dp))
            Text(description, fontSize = 12.sp,
                color = MaterialTheme.colorScheme.onSurfaceVariant)
            Spacer(modifier = Modifier.height(12.dp))
            content()
        }
    }
}
