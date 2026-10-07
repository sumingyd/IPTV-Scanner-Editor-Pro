package com.iptv.scanner.editor.pro.ui

import android.content.Intent
import android.content.res.Configuration
import android.net.Uri
import android.os.Build
import android.util.Log
import com.iptv.scanner.editor.pro.data.BookmarkItem
import com.iptv.scanner.editor.pro.data.ReminderItem
import com.iptv.scanner.editor.pro.data.ResumeItem
import com.iptv.scanner.editor.pro.data.ScanResult
import com.iptv.scanner.editor.pro.data.SubtitleItem
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Canvas
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
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.systemBarsPadding
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Analytics
import androidx.compose.material.icons.filled.CalendarMonth
import androidx.compose.material.icons.filled.CameraAlt
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.History
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.Radar
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Subtitles
import androidx.compose.material.icons.filled.SyncAlt
import androidx.compose.material.icons.filled.Bookmark
import androidx.compose.material.icons.filled.DeleteOutline
import androidx.compose.material.icons.filled.FileDownload
import androidx.compose.material.icons.filled.PlaylistAdd
import androidx.compose.material.icons.filled.VideoLibrary
import androidx.compose.material.icons.filled.Link
import androidx.compose.material.icons.filled.PlayCircle
import androidx.compose.material.icons.filled.Download
import androidx.compose.material.icons.filled.UploadFile
import androidx.compose.material.icons.filled.MusicNote
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.FileOpen
import androidx.compose.material.icons.filled.Movie
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Divider
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Slider
import androidx.compose.material3.SliderDefaults
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.foundation.focusGroup
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.iptv.scanner.editor.pro.data.MappingEntry
import com.iptv.scanner.editor.pro.ui.theme.tvFocusBorder
import com.iptv.scanner.editor.pro.ui.theme.tvTextField
import com.iptv.scanner.editor.pro.ui.theme.rememberPlayerOverlayColors
import org.json.JSONArray
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
// -----------------------------------------------------------------
// 打开网络流 URL 对话框
// -----------------------------------------------------------------

@Composable
fun OpenUrlDialog(viewModel: AppViewModel) {
    val open by viewModel.openUrlDialogOpen.collectAsState()
    if (!open) return

    var url by remember { mutableStateOf("") }
    val isAptv = LocalConfiguration.current.orientation == Configuration.ORIENTATION_PORTRAIT

    if (isAptv) {
        // iOS APTV 风格：居中圆角卡片 + 输入框
        androidx.compose.ui.window.Dialog(
            onDismissRequest = { viewModel.toggleOpenUrlDialog() },
            properties = androidx.compose.ui.window.DialogProperties(usePlatformDefaultWidth = false)
        ) {
            Surface(
                shape = RoundedCornerShape(16.dp),
                color = MaterialTheme.colorScheme.surface,
                tonalElevation = 6.dp,
                modifier = Modifier.fillMaxWidth().padding(horizontal = 40.dp)
            ) {
                Column(modifier = Modifier.padding(24.dp)) {
                    Text(
                        text = "打开网络流",
                        fontSize = 17.sp,
                        fontWeight = FontWeight.SemiBold,
                        color = MaterialTheme.colorScheme.onSurface
                    )
                    Spacer(modifier = Modifier.height(8.dp))
                    Text(
                        text = "输入 M3U/M3U8/HLS/RTSP/RTMP 等协议 URL",
                        fontSize = 12.sp,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    Spacer(modifier = Modifier.height(12.dp))
                    OutlinedTextField(
                        value = url,
                        onValueChange = { url = it },
                        placeholder = { Text("https://example.com/stream.m3u8") },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth()
                    )
                    Spacer(modifier = Modifier.height(24.dp))
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.End,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            text = "取消",
                            fontSize = 16.sp,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier
                                .clickable { viewModel.toggleOpenUrlDialog() }
                                .padding(horizontal = 12.dp, vertical = 8.dp)
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(
                            text = "播放",
                            fontSize = 16.sp,
                            fontWeight = FontWeight.Medium,
                            color = AptvAccent,
                            modifier = Modifier
                                .clickable {
                                    viewModel.playUrl(url.trim())
                                    url = ""
                                }
                                .padding(horizontal = 12.dp, vertical = 8.dp)
                        )
                    }
                }
            }
        }
    } else {
        AlertDialog(
            onDismissRequest = { viewModel.toggleOpenUrlDialog() },
            title = { Text("打开网络流") },
            text = {
                Column {
                    Text(
                        "输入 M3U/M3U8/HLS/RTSP/RTMP 等协议 URL",
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        fontSize = 12.sp
                    )
                    Spacer(modifier = Modifier.height(8.dp))
                    OutlinedTextField(
                        value = url,
                        onValueChange = { url = it },
                        placeholder = { Text("https://example.com/stream.m3u8") },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth().tvTextField()
                    )
                }
            },
            confirmButton = {
                TextButton(
                    onClick = {
                        viewModel.playUrl(url.trim())
                        url = ""
                    },
                    modifier = Modifier.tvFocusBorder()
                ) { Text("播放", color = if (isAptv) AptvAccent else MaterialTheme.colorScheme.primary) }
            },
            dismissButton = {
                TextButton(
                    onClick = { viewModel.toggleOpenUrlDialog() },
                    modifier = Modifier.tvFocusBorder()
                ) { Text("取消") }
            }
        )
    }
}
/**
 * 退出确认对话框：按 BACK 键退出时提示选择退出方式。
 * - 进入画中画：继续在小窗口中观看
 * - 立即退出：直接退出应用
 * - 打开设置：不退出，转而打开播放器设置面板
 * - 取消：继续使用
 */
@Composable
fun ExitConfirmDialog(viewModel: AppViewModel) {
    val open by viewModel.exitConfirmOpen.collectAsState()
    if (!open) return

    val context = androidx.compose.ui.platform.LocalContext.current
    val activity = context as? android.app.Activity
    val isAptv = LocalConfiguration.current.orientation == Configuration.ORIENTATION_PORTRAIT

    if (isAptv) {
        // iOS APTV 风格：居中圆角卡片 + 纵向操作列表
        androidx.compose.ui.window.Dialog(
            onDismissRequest = { viewModel.dismissExitConfirm() },
            properties = androidx.compose.ui.window.DialogProperties(usePlatformDefaultWidth = false)
        ) {
            Surface(
                shape = RoundedCornerShape(16.dp),
                color = MaterialTheme.colorScheme.surface,
                tonalElevation = 6.dp,
                modifier = Modifier.fillMaxWidth().padding(horizontal = 40.dp)
            ) {
                Column(modifier = Modifier.padding(20.dp)) {
                    Text(
                        text = "退出应用",
                        fontSize = 17.sp,
                        fontWeight = FontWeight.SemiBold,
                        color = MaterialTheme.colorScheme.onSurface,
                        modifier = Modifier.fillMaxWidth()
                    )
                    Spacer(modifier = Modifier.height(8.dp))
                    Text(
                        text = "请选择退出方式：",
                        fontSize = 14.sp,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    Spacer(modifier = Modifier.height(20.dp))
                    // PiP
                    if (activity != null &&
                        Build.VERSION.SDK_INT >= Build.VERSION_CODES.O &&
                        activity.packageManager.hasSystemFeature("android.software.picture_in_picture")
                    ) {
                        Text(
                            text = "画中画",
                            fontSize = 16.sp,
                            color = MaterialTheme.colorScheme.primary,
                            modifier = Modifier.fillMaxWidth().clickable {
                                viewModel.dismissExitConfirm()
                                try {
                                    val builder = android.app.PictureInPictureParams.Builder()
                                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                                        builder.setAutoEnterEnabled(true)
                                        builder.setSeamlessResizeEnabled(true)
                                    }
                                    activity.enterPictureInPictureMode(builder.build())
                                } catch (e: Exception) {
                                    Log.e("ExitConfirmDialog", "PiP failed", e)
                                }
                            }.padding(vertical = 12.dp)
                        )
                    }
                    // 立即退出
                    Text(
                        text = "立即退出",
                        fontSize = 16.sp,
                        color = MaterialTheme.colorScheme.error,
                        modifier = Modifier.fillMaxWidth().clickable {
                            viewModel.dismissExitConfirm()
                            viewModel.stopPlay()
                            activity?.finishAffinity()
                        }.padding(vertical = 12.dp)
                    )
                    // 打开设置
                    Text(
                        text = "打开设置",
                        fontSize = 16.sp,
                        color = MaterialTheme.colorScheme.primary,
                        modifier = Modifier.fillMaxWidth().clickable {
                            viewModel.dismissExitConfirm()
                            viewModel.togglePlayerSettings()
                        }.padding(vertical = 12.dp)
                    )
                    HorizontalDivider(
                        color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.3f),
                        modifier = Modifier.padding(vertical = 4.dp)
                    )
                    // 取消
                    Text(
                        text = "取消",
                        fontSize = 16.sp,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.fillMaxWidth().clickable { viewModel.dismissExitConfirm() }
                            .padding(vertical = 12.dp)
                    )
                }
            }
        }
    } else {
        AlertDialog(
            onDismissRequest = { viewModel.dismissExitConfirm() },
            title = { Text("退出应用", fontWeight = FontWeight.Bold) },
            text = {
                Text(
                    "您正在退出应用，请选择退出方式：",
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    fontSize = 14.sp
                )
            },
            confirmButton = {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    // 进入 PiP
                    if (activity != null &&
                        Build.VERSION.SDK_INT >= Build.VERSION_CODES.O &&
                        activity.packageManager.hasSystemFeature("android.software.picture_in_picture")
                    ) {
                        TextButton(
                            onClick = {
                                viewModel.dismissExitConfirm()
                                try {
                                    val builder = android.app.PictureInPictureParams.Builder()
                                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                                        builder.setAutoEnterEnabled(true)
                                        builder.setSeamlessResizeEnabled(true)
                                    }
                                    activity.enterPictureInPictureMode(builder.build())
                                } catch (e: Exception) {
                                    Log.e("ExitConfirmDialog", "PiP failed", e)
                                }
                            },
                            modifier = Modifier.tvFocusBorder()
                        ) { Text("画中画") }
                    }
                    // 立即退出
                    TextButton(
                        onClick = {
                            viewModel.dismissExitConfirm()
                            // 先停止播放，避免 Activity finish 后 mpv 在后台继续播放
                            viewModel.stopPlay()
                            activity?.finishAffinity()
                        },
                        modifier = Modifier.tvFocusBorder()
                    ) { Text("立即退出", color = if (isAptv) AptvAccent else Color(0xFFEF5350)) }
                }
            },
            dismissButton = {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    // 打开设置：不退出，转而打开播放器设置面板
                    TextButton(
                        onClick = {
                            viewModel.dismissExitConfirm()
                            viewModel.togglePlayerSettings()
                        },
                        modifier = Modifier.tvFocusBorder()
                    ) { Text("打开设置") }
                    // 取消
                    TextButton(
                        onClick = { viewModel.dismissExitConfirm() },
                        modifier = Modifier.tvFocusBorder()
                    ) { Text("取消") }
                }
            }
        )
    }
}
// =================================================================
// 工具面板
// =================================================================

/**
 * 工具面板：工具入口列表，与 PC 端"工具"菜单组对齐。
 * 点击各工具项跳转到对应面板或显示 OSD 提示。
 */
@Composable
fun ToolsPanel(viewModel: AppViewModel) {
    // SAF 文件选择器 —— 打开播放列表
    val playlistLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.OpenDocument()
    ) { uri: Uri? ->
        if (uri != null) viewModel.importPlaylist(uri)
    }

    // SAF 文件选择器 —— 打开本地视频/音频
    val videoLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.OpenDocument()
    ) { uri: Uri? ->
        if (uri != null) viewModel.playLocalVideo(uri.toString())
    }

    PanelScaffold(
        title = "工具",
        subtitle = "搜索 / EPG时间线 / 提醒 / 续播 / 书签 / 映射 / 扫描 / 流质量",
        onClose = { viewModel.toggleToolsPanel() },
        scrollable = false
    ) {
        val tools = listOf(
            // —— 文件快捷入口 ——
            ToolEntry("打开播放列表", "选择设备上的 M3U/M3U8 文件", Icons.Default.FileOpen) {
                viewModel.toggleToolsPanel()
                if (!viewModel.isSafAvailable()) {
                    viewModel.showFileBrowser()
                } else {
                    playlistLauncher.launch(arrayOf(
                        "application/x-mpegurl", "application/vnd.apple.mpegurl",
                        "audio/x-mpegurl", "video/x-mpegurl",
                        "text/plain", "application/octet-stream"
                    ))
                }
            },
            ToolEntry("打开本地文件", "播放设备上的视频/音频文件", Icons.Default.Movie) {
                viewModel.toggleToolsPanel()
                if (!viewModel.isSafAvailable()) {
                    viewModel.showMediaFileBrowser()
                } else {
                    videoLauncher.launch(arrayOf("video/*", "audio/*", "application/x-matroska", "application/octet-stream"))
                }
            },
            // —— 原有工具 ——
            ToolEntry("搜索", "全局搜索频道和节目", Icons.Default.Search) {
                viewModel.toggleToolsPanel()
                viewModel.toggleSearchPanel()
            },
            ToolEntry("EPG 时间线", "节目时间线视图", Icons.Default.CalendarMonth) {
                viewModel.toggleToolsPanel()
                viewModel.toggleEpgTimelinePanel()
            },
            ToolEntry("提醒管理", "节目提醒列表", Icons.Default.Notifications) {
                viewModel.toggleToolsPanel()
                viewModel.toggleReminderPanel()
            },
            ToolEntry("续播位置", "本地文件/点播断点续播", Icons.Default.History) {
                viewModel.toggleToolsPanel()
                viewModel.toggleResumePanel()
            },
            ToolEntry("书签管理", "播放位置书签（增删查/跳转）", Icons.Default.Bookmark) {
                viewModel.toggleToolsPanel()
                viewModel.toggleBookmarkPanel()
            },
            ToolEntry("频道映射", "远程映射 + 用户映射管理", Icons.Default.SyncAlt) {
                viewModel.toggleToolsPanel()
                viewModel.toggleMappingPanel()
            },
            ToolEntry("扫描整理", "URL 范围扫描（StandaloneScanner）", Icons.Default.Radar) {
                viewModel.toggleToolsPanel()
                viewModel.toggleScanPanel()
            },
            ToolEntry("流质量检测", "码率 / 分辨率 / 编解码器", Icons.Default.Analytics) {
                viewModel.toggleToolsPanel()
                viewModel.toggleStreamQualityPanel()
            }
        )
        LazyColumn(modifier = Modifier.fillMaxWidth()) {
            items(tools) { tool ->
                ToolEntryRow(tool)
                HorizontalDivider(color = MaterialTheme.colorScheme.surfaceVariant)
            }
        }
    }
}
private data class ToolEntry(
    val title: String,
    val desc: String,
    val icon: androidx.compose.ui.graphics.vector.ImageVector,
    val onClick: () -> Unit
)

@Composable
private fun ToolEntryRow(tool: ToolEntry) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable { tool.onClick() }
            .tvFocusBorder()
            .padding(vertical = 12.dp, horizontal = 4.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Icon(
            imageVector = tool.icon,
            contentDescription = tool.title,
            tint = MaterialTheme.colorScheme.primary,
            modifier = Modifier.size(28.dp)
        )
        Spacer(modifier = Modifier.width(12.dp))
        Column(modifier = Modifier.weight(1f)) {
            Text(text = tool.title, color = MaterialTheme.colorScheme.onSurface, fontSize = 14.sp, fontWeight = FontWeight.Medium)
            Text(text = tool.desc, color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 12.sp)
        }
    }
}

/**
 * 播放工具面板：播放时常用工具入口（截图/切片/EPG时间线/搜索/提醒/续播/书签/可视化/歌词）。
 * 从控制条"播放工具"按钮或设置页"播放工具"项进入，与 [ToolsPanel] 的通用工具列表互补。
 */
@Composable
fun PlayerToolsPanel(viewModel: AppViewModel) {
    PanelScaffold(
        title = "播放工具",
        subtitle = "截图 / 切片 / EPG时间线 / 搜索 / 提醒 / 续播 / 书签",
        onClose = { viewModel.togglePlayerToolsPanel() },
        scrollable = false
    ) {
        val tools = listOf(
            ToolEntry("截图", "截取当前画面", Icons.Default.CameraAlt) {
                viewModel.togglePlayerToolsPanel()
                viewModel.toggleScreenshotPanel()
            },
            ToolEntry("切片导出", "截取视频片段", Icons.Default.Movie) {
                viewModel.togglePlayerToolsPanel()
                viewModel.toggleClipExportPanel()
            },
            ToolEntry("EPG 时间线", "节目时间线视图", Icons.Default.CalendarMonth) {
                viewModel.togglePlayerToolsPanel()
                viewModel.toggleEpgTimelinePanel()
            },
            ToolEntry("搜索", "全局搜索频道和节目", Icons.Default.Search) {
                viewModel.togglePlayerToolsPanel()
                viewModel.toggleSearchPanel()
            },
            ToolEntry("提醒管理", "节目提醒列表", Icons.Default.Notifications) {
                viewModel.togglePlayerToolsPanel()
                viewModel.toggleReminderPanel()
            },
            ToolEntry("续播位置", "本地文件/点播断点续播", Icons.Default.History) {
                viewModel.togglePlayerToolsPanel()
                viewModel.toggleResumePanel()
            },
            ToolEntry("书签管理", "播放位置书签", Icons.Default.Bookmark) {
                viewModel.togglePlayerToolsPanel()
                viewModel.toggleBookmarkPanel()
            },
            ToolEntry("音频可视化", "频谱/波形可视化", Icons.Default.Analytics) {
                viewModel.togglePlayerToolsPanel()
                viewModel.toggleAudioVisualizer()
            },
            ToolEntry("歌词", "加载/显示歌词", Icons.Default.Subtitles) {
                viewModel.togglePlayerToolsPanel()
                viewModel.toggleLyricsPanel()
            }
        )
        LazyColumn(modifier = Modifier.fillMaxWidth()) {
            items(tools) { tool ->
                ToolEntryRow(tool)
                HorizontalDivider(color = MaterialTheme.colorScheme.surfaceVariant)
            }
        }
    }
}

// -----------------------------------------------------------------
// 节目提醒管理面板（与 PC 端 ui/dialogs/reminder_manager_dialog.py 对齐）
// -----------------------------------------------------------------

/**
 * 提醒管理面板：列出所有已设置的节目提醒，支持删除/清空。
 *
 * - 顶部显示总数和清空按钮
 * - 列表项显示频道名 / 节目标题 / 开始时间 / 倒计时
 * - 即将开始（<5 分钟）的提醒高亮显示
 * - 空列表显示占位提示
 */
@Composable
fun ReminderPanel(viewModel: AppViewModel) {
    val reminders by viewModel.reminders.collectAsState()
    val now = System.currentTimeMillis()
    val timeFmt = remember { SimpleDateFormat("MM-dd HH:mm", Locale.getDefault()) }

    PanelScaffold(
        title = "节目提醒",
        subtitle = "已设置 ${reminders.size} 条提醒",
        onClose = { viewModel.toggleReminderPanel() },
        actions = {
            if (reminders.isNotEmpty()) {
                OutlinedButton(
                    onClick = { viewModel.clearReminders() },
                    modifier = Modifier.tvFocusBorder()
                ) {
                    Icon(Icons.Default.Close, contentDescription = null, tint = Color(0xFFFF5252))
                    Spacer(modifier = Modifier.width(4.dp))
                    Text("清空", color = Color(0xFFFF5252))
                }
            }
        }
    ) {
        if (reminders.isEmpty()) {
            Box(
                modifier = Modifier.fillMaxWidth().padding(top = 60.dp),
                contentAlignment = Alignment.Center
            ) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Icon(
                        Icons.Default.Notifications,
                        contentDescription = null,
                        tint = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.size(48.dp)
                    )
                    Spacer(modifier = Modifier.height(8.dp))
                    Text("暂无节目提醒", color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 13.sp)
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        "在节目单中点击当前或未来节目可设置提醒",
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        fontSize = 11.sp
                    )
                }
            }
            return@PanelScaffold
        }

        // 按开始时间升序排序
        val sorted = remember(reminders) { reminders.sortedBy { it.startTs } }

        SettingsGroup("提醒列表") {
            LazyColumn(
                modifier = Modifier.fillMaxWidth().heightIn(max = 500.dp)
            ) {
                items(sorted, key = { it.id }) { item ->
                    ReminderRow(
                        item = item,
                        now = now,
                        timeFmt = timeFmt,
                        onDelete = { viewModel.removeReminder(item.id) }
                    )
                    HorizontalDivider(color = MaterialTheme.colorScheme.surfaceVariant)
                }
            }
        }
    }
}
@Composable
private fun ReminderRow(
    item: ReminderItem,
    now: Long,
    timeFmt: SimpleDateFormat,
    onDelete: () -> Unit
) {
    val remainingMs = item.startTs - now
    val isUpcoming = remainingMs in 0..5 * 60 * 1000L  // 5 分钟内即将开始
    val isPast = remainingMs < 0  // 已开始（但未结束）

    val titleColor = when {
        isUpcoming -> Color(0xFFFFC107)  // 黄色高亮
        isPast -> MaterialTheme.colorScheme.onSurfaceVariant
        else -> MaterialTheme.colorScheme.onSurface
    }

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 12.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Column(modifier = Modifier.weight(1f)) {
            // 节目标题
            Text(
                text = item.programTitle.ifBlank { "（未命名节目）" },
                color = titleColor,
                fontSize = 14.sp,
                fontWeight = if (isUpcoming) FontWeight.Medium else FontWeight.Normal,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis
            )
            // 频道名
            if (item.channelName.isNotEmpty()) {
                Text(
                    text = item.channelName,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    fontSize = 12.sp,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.padding(top = 2.dp)
                )
            }
            // 时间 + 倒计时
            Row(
                modifier = Modifier.padding(top = 3.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = timeFmt.format(Date(item.startTs)),
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    fontSize = 11.sp
                )
                val remainingText = when {
                    remainingMs > 0 -> {
                        val min = remainingMs / 60_000
                        if (min > 0) "${min}分钟后" else "即将开始"
                    }
                    remainingMs > -60 * 60 * 1000L -> "已开始"  // 1 小时内
                    else -> "已过期"
                }
                val remainingColor = when {
                    isUpcoming -> Color(0xFFFFC107)
                    isPast -> MaterialTheme.colorScheme.onSurfaceVariant
                    else -> MaterialTheme.colorScheme.primary
                }
                Text(remainingText, color = remainingColor, fontSize = 11.sp)
            }
        }
        IconButton(onClick = onDelete, modifier = Modifier.size(32.dp).tvFocusBorder()) {
            Icon(
                Icons.Default.Close,
                contentDescription = "删除",
                tint = Color(0xFFE57373),
                modifier = Modifier.size(16.dp)
            )
        }
    }
}
// -----------------------------------------------------------------
// 续播位置管理面板（与 PC 端 ui/dialogs/resume_position_dialog.py 对齐）
// -----------------------------------------------------------------

/**
 * 续播位置面板：列出所有已保存的播放断点，支持恢复/删除/清空。
 *
 * - 顶部显示总数和清空按钮
 * - 列表项显示名称 + 位置/时长 + 更新时间
 * - 点击"恢复"调用 playResume 切换并 seek
 * - 空列表显示占位提示
 */
@Composable
fun ResumePanel(viewModel: AppViewModel) {
    val resumeList by viewModel.resumeList.collectAsState()
    val timeFmt = remember { SimpleDateFormat("MM-dd HH:mm", Locale.getDefault()) }

    PanelScaffold(
        title = "续播位置",
        subtitle = "已保存 ${resumeList.size} 条断点",
        onClose = { viewModel.toggleResumePanel() },
        actions = {
            if (resumeList.isNotEmpty()) {
                OutlinedButton(
                    onClick = { viewModel.clearResumeList() },
                    modifier = Modifier.tvFocusBorder()
                ) {
                    Icon(Icons.Default.Close, contentDescription = null, tint = Color(0xFFFF5252))
                    Spacer(modifier = Modifier.width(4.dp))
                    Text("清空", color = Color(0xFFFF5252))
                }
            }
        }
    ) {
        if (resumeList.isEmpty()) {
            Box(
                modifier = Modifier.fillMaxWidth().padding(top = 60.dp),
                contentAlignment = Alignment.Center
            ) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Icon(
                        Icons.Default.History,
                        contentDescription = null,
                        tint = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.size(48.dp)
                    )
                    Spacer(modifier = Modifier.height(8.dp))
                    Text("暂无续播记录", color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 13.sp)
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        "播放本地文件或点播流时自动保存断点",
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        fontSize = 11.sp
                    )
                }
            }
            return@PanelScaffold
        }

        // 按更新时间降序排序（最近观看在前）
        val sorted = remember(resumeList) { resumeList.sortedByDescending { it.updatedAt } }

        SettingsGroup("断点列表") {
            LazyColumn(
                modifier = Modifier.fillMaxWidth().heightIn(max = 500.dp)
            ) {
                items(sorted, key = { it.id }) { item ->
                    ResumeRow(
                        item = item,
                        timeFmt = timeFmt,
                        onPlay = { viewModel.playResume(item) },
                        onDelete = { viewModel.removeResume(item.url) }
                    )
                    HorizontalDivider(color = MaterialTheme.colorScheme.surfaceVariant)
                }
            }
        }
    }
}
@Composable
private fun ResumeRow(
    item: ResumeItem,
    timeFmt: SimpleDateFormat,
    onPlay: () -> Unit,
    onDelete: () -> Unit
) {
    // 格式化时长 mm:ss 或 hh:mm:ss
    fun fmt(sec: Long): String {
        if (sec <= 0) return "00:00"
        val h = sec / 3600
        val m = (sec % 3600) / 60
        val s = sec % 60
        return if (h > 0) "%02d:%02d:%02d".format(h, m, s) else "%02d:%02d".format(m, s)
    }

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 12.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Column(modifier = Modifier.weight(1f)) {
            // 名称
            Text(
                text = item.name.ifBlank { item.url },
                color = MaterialTheme.colorScheme.onSurface,
                fontSize = 14.sp,
                fontWeight = FontWeight.Medium,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis
            )
            // 位置 / 时长
            Row(
                modifier = Modifier.padding(top = 3.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                val progress = if (item.duration > 0) {
                    (item.position.toFloat() / item.duration.toFloat()).coerceIn(0f, 1f)
                } else 0f
                Text(
                    text = "${fmt(item.position)} / ${fmt(item.duration)}",
                    color = MaterialTheme.colorScheme.primary,
                    fontSize = 11.sp
                )
                if (progress > 0) {
                    Text(
                        text = "${(progress * 100).toInt()}%",
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        fontSize = 11.sp
                    )
                }
            }
            // 更新时间 + URL
            Row(
                modifier = Modifier.padding(top = 2.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = timeFmt.format(Date(item.updatedAt)),
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    fontSize = 11.sp
                )
                if (item.channelIdx >= 0) {
                    Surface(
                        color = MaterialTheme.colorScheme.primary.copy(alpha = 0.15f),
                        shape = RoundedCornerShape(3.dp)
                    ) {
                        Text(
                            text = "频道",
                            color = MaterialTheme.colorScheme.primary,
                            fontSize = 10.sp,
                            modifier = Modifier.padding(horizontal = 4.dp, vertical = 1.dp)
                        )
                    }
                } else {
                    Surface(
                        color = Color(0xFF4CAF50).copy(alpha = 0.15f),
                        shape = RoundedCornerShape(3.dp)
                    ) {
                        Text(
                            text = "本地",
                            color = Color(0xFF4CAF50),
                            fontSize = 10.sp,
                            modifier = Modifier.padding(horizontal = 4.dp, vertical = 1.dp)
                        )
                    }
                }
            }
        }
        // 恢复按钮
        OutlinedButton(
            onClick = onPlay,
            modifier = Modifier.tvFocusBorder()
        ) {
            Text("恢复", color = MaterialTheme.colorScheme.primary, fontSize = 12.sp)
        }
        Spacer(modifier = Modifier.width(4.dp))
        IconButton(onClick = onDelete, modifier = Modifier.size(32.dp).tvFocusBorder()) {
            Icon(
                Icons.Default.Close,
                contentDescription = "删除",
                tint = Color(0xFFE57373),
                modifier = Modifier.size(16.dp)
            )
        }
    }
}
// -----------------------------------------------------------------
// 书签管理面板（与 PC 端 ui/dialogs/bookmark_dialog.py 对齐）
// -----------------------------------------------------------------

/**
 * 书签面板：添加/跳转/删除/清空书签。
 *
 * - 顶部：添加书签按钮 + 视图切换（当前文件/所有文件）
 * - 列表：书签项显示名称 + 位置时间 + 创建时间 + 跳转/删除按钮
 * - 底部：清除当前/清除全部
 * - 空列表显示占位提示
 */
@Composable
fun BookmarkPanel(viewModel: AppViewModel) {
    val showCurrent by viewModel.bookmarkShowCurrent.collectAsState()
    val currentBookmarks by viewModel.currentBookmarks.collectAsState()
    val allBookmarks by viewModel.allBookmarks.collectAsState()
    val timeFmt = remember { SimpleDateFormat("MM-dd HH:mm", Locale.getDefault()) }

    val displayList = if (showCurrent) currentBookmarks else allBookmarks

    PanelScaffold(
        title = "书签",
        subtitle = "已保存 ${displayList.size} 条书签",
        onClose = { viewModel.toggleBookmarkPanel() },
        actions = {
            if (displayList.isNotEmpty()) {
                OutlinedButton(
                    onClick = {
                        if (showCurrent) viewModel.clearCurrentBookmarks()
                        else viewModel.clearAllBookmarks()
                    },
                    modifier = Modifier.tvFocusBorder()
                ) {
                    Icon(Icons.Default.Close, contentDescription = null, tint = Color(0xFFFF5252))
                    Spacer(modifier = Modifier.width(4.dp))
                    Text(
                        if (showCurrent) "清除当前" else "清空全部",
                        color = Color(0xFFFF5252)
                    )
                }
            }
        }
    ) {
        // 添加书签按钮
        OutlinedButton(
            onClick = { viewModel.addBookmark() },
            modifier = Modifier.fillMaxWidth().tvFocusBorder()
        ) {
            Icon(Icons.Default.Bookmark, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
            Spacer(modifier = Modifier.width(6.dp))
            Text("在当前位置添加书签", color = MaterialTheme.colorScheme.primary)
        }

        Spacer(modifier = Modifier.height(12.dp))

        // 视图切换
        SelectionGroup(
            title = "视图",
            options = listOf(
                "current" to "当前文件 (${currentBookmarks.size})",
                "all" to "所有文件 (${allBookmarks.size})"
            ),
            selectedKey = if (showCurrent) "current" else "all",
            onSelect = { key -> viewModel.setBookmarkShowCurrent(key == "current") }
        )

        Spacer(modifier = Modifier.height(12.dp))

        if (displayList.isEmpty()) {
            Box(
                modifier = Modifier.fillMaxWidth().padding(top = 40.dp),
                contentAlignment = Alignment.Center
            ) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Icon(
                        Icons.Default.Bookmark,
                        contentDescription = null,
                        tint = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.size(48.dp)
                    )
                    Spacer(modifier = Modifier.height(8.dp))
                    Text(
                        if (showCurrent) "当前文件暂无书签" else "暂无任何书签",
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        fontSize = 13.sp
                    )
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        "点击上方按钮在当前位置添加书签",
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        fontSize = 11.sp
                    )
                }
            }
            return@PanelScaffold
        }

        SettingsGroup("书签列表") {
            LazyColumn(
                modifier = Modifier.fillMaxWidth().heightIn(max = 500.dp)
            ) {
                items(displayList, key = { it.id }) { item ->
                    BookmarkRow(
                        item = item,
                        timeFmt = timeFmt,
                        onGoto = { viewModel.gotoBookmark(item) },
                        onDelete = { viewModel.deleteBookmark(item) }
                    )
                    HorizontalDivider(color = MaterialTheme.colorScheme.surfaceVariant)
                }
            }
        }
    }
}
@Composable
private fun BookmarkRow(
    item: BookmarkItem,
    timeFmt: SimpleDateFormat,
    onGoto: () -> Unit,
    onDelete: () -> Unit
) {
    // 格式化秒为 mm:ss 或 hh:mm:ss
    fun fmt(sec: Long): String {
        if (sec <= 0) return "00:00"
        val h = sec / 3600
        val m = (sec % 3600) / 60
        val s = sec % 60
        return if (h > 0) "%02d:%02d:%02d".format(h, m, s) else "%02d:%02d".format(m, s)
    }

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 12.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Column(modifier = Modifier.weight(1f)) {
            // 名称
            Text(
                text = item.name.ifBlank { "书签 @${fmt(item.position)}" },
                color = MaterialTheme.colorScheme.onSurface,
                fontSize = 14.sp,
                fontWeight = FontWeight.Medium,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis
            )
            // 位置时间
            Row(
                modifier = Modifier.padding(top = 3.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Surface(
                    color = MaterialTheme.colorScheme.primary.copy(alpha = 0.15f),
                    shape = RoundedCornerShape(3.dp)
                ) {
                    Text(
                        text = fmt(item.position),
                        color = MaterialTheme.colorScheme.primary,
                        fontSize = 11.sp,
                        modifier = Modifier.padding(horizontal = 4.dp, vertical = 1.dp)
                    )
                }
                Text(
                    text = timeFmt.format(Date(item.createdAt)),
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    fontSize = 11.sp
                )
            }
            // URL（所有文件视图下显示）
            if (item.url.isNotEmpty()) {
                Text(
                    text = item.url,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    fontSize = 10.sp,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.padding(top = 2.dp)
                )
            }
        }
        // 跳转按钮
        OutlinedButton(
            onClick = onGoto,
            modifier = Modifier.tvFocusBorder()
        ) {
            Text("跳转", color = MaterialTheme.colorScheme.primary, fontSize = 12.sp)
        }
        Spacer(modifier = Modifier.width(4.dp))
        IconButton(onClick = onDelete, modifier = Modifier.size(32.dp).tvFocusBorder()) {
            Icon(
                Icons.Default.Close,
                contentDescription = "删除",
                tint = Color(0xFFE57373),
                modifier = Modifier.size(16.dp)
            )
        }
    }
}
/**
 * 音频可视化面板（与 PC 端 audio_visual 对齐）。
 * 实时频谱波形 Canvas 绘制。
 */
@Composable
fun AudioVisualizerPanel(viewModel: AppViewModel) {
    val spectrum by viewModel.audioSpectrum.collectAsState()
    val mpv = viewModel.mpv
    val fileLoaded by mpv.fileLoaded.collectAsState()

    PanelScaffold(
        title = "音频可视化",
        onClose = { viewModel.toggleAudioVisualizer() }
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            if (!fileLoaded) {
                Box(
                    modifier = Modifier.fillMaxSize(),
                    contentAlignment = Alignment.Center
                ) {
                    Text("请先加载音视频", color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 14.sp)
                }
                return@PanelScaffold
            }

        // 在 Canvas 外部提取颜色（Canvas 内部不能调用 @Composable）
        val primaryColor = MaterialTheme.colorScheme.primary
        val outlineColor = MaterialTheme.colorScheme.outlineVariant

        // 频谱画布（美化版：渐变色 + 圆角条 + 底部镜像反射 + 中线）
        Canvas(
            modifier = Modifier
                .fillMaxWidth()
                .height(240.dp)
                .background(
                    MaterialTheme.colorScheme.surface,
                    shape = RoundedCornerShape(12.dp)
                )
                .clip(RoundedCornerShape(12.dp))
        ) {
            val barCount = spectrum.size
            if (barCount == 0) return@Canvas
            val barWidth = size.width / barCount
            val gap = barWidth * 0.15f
            val actualBarWidth = barWidth - gap
            val centerY = size.height * 0.5f
            val maxBarHeight = size.height * 0.42f

            // 中线
            drawLine(
                color = outlineColor.copy(alpha = 0.2f),
                    start = androidx.compose.ui.geometry.Offset(0f, centerY),
                    end = androidx.compose.ui.geometry.Offset(size.width, centerY),
                    strokeWidth = 1f
                )

                spectrum.forEachIndexed { i, amplitude ->
                    val barHeight = (amplitude * maxBarHeight)
                    val x = i * barWidth + gap / 2

                    // 上方频谱条（从中心向上）
                    val topY = centerY - barHeight
                    // 下方镜像反射（从中心向下，透明度渐减）
                    val bottomY = centerY + barHeight

                    // 渐变色：低频蓝 → 中频青 → 高频橙
                    val color = when {
                        amplitude < 0.33f -> primaryColor.copy(alpha = 0.7f + amplitude * 0.3f)
                        amplitude < 0.66f -> Color(0xFF00BCD4).copy(alpha = 0.8f)
                        else -> Color(0xFFFF9800).copy(alpha = 0.9f)
                    }
                    val reflectionColor = color.copy(alpha = 0.25f)

                    drawRoundRect(
                        color = color,
                        topLeft = androidx.compose.ui.geometry.Offset(x, topY),
                        size = androidx.compose.ui.geometry.Size(actualBarWidth, barHeight),
                        cornerRadius = androidx.compose.ui.geometry.CornerRadius(actualBarWidth * 0.3f, actualBarWidth * 0.3f)
                    )
                    // 镜像反射
                    drawRoundRect(
                        color = reflectionColor,
                        topLeft = androidx.compose.ui.geometry.Offset(x, centerY),
                        size = androidx.compose.ui.geometry.Size(actualBarWidth, barHeight),
                        cornerRadius = androidx.compose.ui.geometry.CornerRadius(actualBarWidth * 0.3f, actualBarWidth * 0.3f)
                    )
                }
            }

            // 信息行
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                val volume = mpv.getPropertyDouble("volume") ?: 100.0
                Text("音量: ${volume.toInt()}", color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 12.sp)
                Text("频段: ${spectrum.size}", color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 12.sp)
            }
        }
    }
}
/**
 * 歌词面板（与 PC 端 LyricsWidget 对齐）。
 * 支持 LRC 格式歌词加载、显示和同步高亮。
 */
@Composable
fun LyricsPanel(viewModel: AppViewModel) {
    val lyricsLines by viewModel.lyricsLines.collectAsState()
    val currentLine by viewModel.currentLyricLine.collectAsState()
    val mpv = viewModel.mpv
    val fileLoaded by mpv.fileLoaded.collectAsState()

    // SAF 文件选择器（选择 .lrc 文件）
    val filePicker = rememberLauncherForActivityResult(
        ActivityResultContracts.OpenDocument()
    ) { uri ->
        if (uri != null) {
            viewModel.loadLyricsFromUri(uri.toString())
        }
    }

    PanelScaffold(
        title = "歌词",
        onClose = { viewModel.toggleLyricsPanel() }
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            // 操作栏
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                OutlinedButton(
                    onClick = { filePicker.launch(arrayOf("application/octet-stream", "text/plain", "*/*")) },
                    modifier = Modifier.tvFocusBorder()
                ) {
                    Icon(Icons.Default.UploadFile, contentDescription = null, modifier = Modifier.size(16.dp))
                    Spacer(modifier = Modifier.width(4.dp))
                    Text("加载 LRC", fontSize = 12.sp)
                }
                OutlinedButton(
                    onClick = { viewModel.clearLyrics() },
                    modifier = Modifier.tvFocusBorder()
                ) {
                    Icon(Icons.Default.Delete, contentDescription = null, modifier = Modifier.size(16.dp))
                    Spacer(modifier = Modifier.width(4.dp))
                    Text("清除", fontSize = 12.sp, color = Color(0xFFE57373))
                }
            }

            if (lyricsLines.isEmpty()) {
                Box(
                    modifier = Modifier.fillMaxSize(),
                    contentAlignment = Alignment.Center
                ) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Icon(
                            Icons.Default.MusicNote,
                            contentDescription = null,
                            tint = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.size(48.dp)
                        )
                        Spacer(modifier = Modifier.height(12.dp))
                        Text("点击「加载 LRC」导入歌词文件", color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 13.sp)
                        if (fileLoaded) {
                            Spacer(modifier = Modifier.height(4.dp))
                            Text("播放时将自动同步高亮", color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 11.sp)
                        }
                    }
                }
                return@Column
            }

            // 歌词列表
            LazyColumn(
                modifier = Modifier
                    .fillMaxSize()
                    .weight(1f),
                contentPadding = PaddingValues(vertical = 16.dp),
                verticalArrangement = Arrangement.spacedBy(4.dp)
            ) {
                itemsIndexed(lyricsLines) { index, line ->
                    val isCurrent = index == currentLine
                    val isPast = index < currentLine
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(horizontal = 12.dp, vertical = 4.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        // 时间标签
                        val min = line.time / 60000
                        val sec = (line.time % 60000) / 1000
                        Text(
                            text = String.format("%02d:%05.2f", min, sec),
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            fontSize = 11.sp,
                            modifier = Modifier.width(56.dp)
                        )
                        Text(
                            text = line.text,
                            color = when {
                                isCurrent -> Color(0xFF4CAF50)
                                isPast -> MaterialTheme.colorScheme.onSurfaceVariant
                                else -> MaterialTheme.colorScheme.onSurfaceVariant
                            },
                            fontSize = if (isCurrent) 16.sp else 14.sp,
                            fontWeight = if (isCurrent) FontWeight.Bold else FontWeight.Normal,
                            maxLines = 2,
                            overflow = TextOverflow.Ellipsis,
                            modifier = Modifier.weight(1f)
                        )
                    }
                }
            }
        }
    }
}
