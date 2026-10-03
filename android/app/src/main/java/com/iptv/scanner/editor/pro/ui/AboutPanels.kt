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
// 关于面板
// -----------------------------------------------------------------

/**
 * 关于面板：版本信息 + 检查更新 + 功能说明。
 */
@Composable
fun AboutPanel(viewModel: AppViewModel) {
    val currentVersion = remember { viewModel.getCurrentVersion() }
    val updateState by viewModel.updateState.collectAsState()

    PanelScaffold(
        title = "关于",
        subtitle = "ISEP",
        onClose = { viewModel.toggleAboutPanel() }
    ) {
        SectionLabel("版本信息")
        Surface(
            color = MaterialTheme.colorScheme.surfaceVariant,
            shape = RoundedCornerShape(8.dp),
            modifier = Modifier.fillMaxWidth()
        ) {
            Column(modifier = Modifier.padding(16.dp)) {
                InfoRow("应用名称", "ISEP")
                InfoRow("版本", currentVersion)
                InfoRow("播放引擎", "mpv (libmpv)")
                InfoRow("UI 框架", "Jetpack Compose")
                InfoRow("Python 引擎", "Chaquopy")
            }
        }

        SectionLabel("版本检查")
        Row(
            modifier = Modifier.fillMaxWidth().padding(vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            OutlinedButton(
                onClick = { viewModel.checkForUpdates(auto = false) },
                enabled = updateState !is UpdateState.Checking,
                modifier = Modifier.tvFocusBorder()
            ) {
                if (updateState is UpdateState.Checking) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(16.dp),
                        strokeWidth = 2.dp,
                        color = MaterialTheme.colorScheme.primary
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text("检查中...")
                } else {
                    Text("检查更新")
                }
            }
            when (updateState) {
                is UpdateState.Checking -> {}
                is UpdateState.UpToDate -> {
                    Text("当前已是最新版本", color = Color(0xFF4CAF50), fontSize = 13.sp)
                }
                is UpdateState.UpdateAvailable -> {
                    val info = updateState as UpdateState.UpdateAvailable
                    Text(
                        "发现新版本 v${info.latestVersion}（当前 v$currentVersion）",
                        color = MaterialTheme.colorScheme.tertiary,
                        fontSize = 13.sp,
                        fontWeight = FontWeight.Medium
                    )
                }
                is UpdateState.Error -> {
                    val err = updateState as UpdateState.Error
                    Text("检查失败: ${err.message}", color = Color(0xFFEF5350), fontSize = 13.sp)
                }
                else -> {}
            }
        }

        SectionLabel("功能特性")
        val features = listOf(
            "频道播放：支持 HLS/RTSP/RTMP/HTTP 等协议",
            "订阅源管理：M3U 播放列表 CRUD + 自动加载",
            "EPG 节目单：XMLTV 格式，按频道/日期/搜索",
            "回看/时移：catchup-source 支持，EPG 过去节目回看",
            "视频调整：亮度/对比度/饱和度/色调/Gamma/旋转/翻转",
            "音频调整：音轨切换/延迟/10段EQ预设",
            "字幕：轨道切换/延迟/缩放/位置/外挂加载",
            "截图：仅画面/含字幕/含 OSD",
            "播放控制：循环/AB循环/逐帧/速度/章节",
            "局域网管理：TV 端遥控器扫码管理（5分钟自动停止）",
            "备份恢复：订阅源/EPG源/收藏/历史/队列/播放器设置",
            "TV 适配：DPAD 遥控器/手机触摸双模式"
        )
        features.forEach { feature ->
            Text(
                text = "• $feature",
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                fontSize = 12.sp,
                modifier = Modifier.padding(vertical = 2.dp, horizontal = 4.dp)
            )
        }

        Spacer(modifier = Modifier.height(32.dp))
    }
}
/**
 * 更新提示对话框：发现新版本时弹出，提供应用内直接下载安装功能。
 *
 * 与 PC 端 UpdateController 的更新提示对齐。
 * 改进：TV 端跳转浏览器不便，改为通过 DownloadManager 直接下载 APK 并调起系统安装器。
 *
 * UI 状态：
 * - Idle / UpdateAvailable：显示「立即更新」按钮
 * - Downloading(progress)：显示进度条 + 「取消」按钮（禁用关闭）
 * - Completed：显示「立即安装」按钮（自动调起安装，按钮作为备用入口）
 * - Error：显示错误信息 + 「重试」按钮
 */
@Composable
fun UpdateDialog(viewModel: AppViewModel) {
    val open by viewModel.updateDialogOpen.collectAsState()
    if (!open) return

    val updateState by viewModel.updateState.collectAsState()
    val currentVersion = remember { viewModel.getCurrentVersion() }
    val apkState by viewModel.apkDownloadState.collectAsState()

    val info = updateState as? UpdateState.UpdateAvailable
    if (info == null) {
        viewModel.dismissUpdateDialog()
        return
    }

    val isDownloading = apkState is ApkDownloadState.Downloading
    val progress = (apkState as? ApkDownloadState.Downloading)?.progress ?: 0

    AlertDialog(
        onDismissRequest = {
            // 下载中不允许点外部关闭（防止误触中断下载）
            if (!isDownloading) viewModel.dismissUpdateDialog()
        },
        title = { Text("发现新版本", fontWeight = FontWeight.Bold) },
        text = {
            Column {
                Text(
                    "新版本 v${info.latestVersion} 已发布",
                    color = MaterialTheme.colorScheme.tertiary,
                    fontSize = 15.sp,
                    fontWeight = FontWeight.Medium
                )
                Spacer(modifier = Modifier.height(8.dp))
                Text(
                    "当前版本：v$currentVersion",
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    fontSize = 13.sp
                )
                Spacer(modifier = Modifier.height(12.dp))

                when (val s = apkState) {
                    is ApkDownloadState.Idle -> {
                        Text(
                            "点击「立即更新」开始下载并安装最新版 APK。",
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            fontSize = 13.sp
                        )
                    }
                    is ApkDownloadState.Downloading -> {
                        Text(
                            "正在下载更新包… ${s.progress}%",
                            color = MaterialTheme.colorScheme.primary,
                            fontSize = 13.sp,
                            fontWeight = FontWeight.Medium
                        )
                        Spacer(modifier = Modifier.height(8.dp))
                        LinearProgressIndicator(
                            progress = { s.progress / 100f },
                            modifier = Modifier.fillMaxWidth(),
                            color = MaterialTheme.colorScheme.primary,
                            trackColor = MaterialTheme.colorScheme.surfaceVariant
                        )
                        Spacer(modifier = Modifier.height(4.dp))
                        Text(
                            "下载过程中请保持网络畅通，完成后将自动弹出安装界面。",
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            fontSize = 11.sp
                        )
                    }
                    is ApkDownloadState.Completed -> {
                        Text(
                            "下载完成，正在启动安装程序…",
                            color = Color(0xFF4CAF50),
                            fontSize = 13.sp,
                            fontWeight = FontWeight.Medium
                        )
                        Spacer(modifier = Modifier.height(4.dp))
                        Text(
                            "若安装界面未自动弹出，请点击「立即安装」重试。",
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            fontSize = 11.sp
                        )
                    }
                    is ApkDownloadState.Error -> {
                        Text(
                            s.message,
                            color = Color(0xFFE57373),
                            fontSize = 13.sp
                        )
                        Spacer(modifier = Modifier.height(4.dp))
                        Text(
                            "请重试，或点击「浏览器下载」跳转 GitHub 手动安装。",
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            fontSize = 11.sp
                        )
                    }
                }
            }
        },
        confirmButton = {
            when (apkState) {
                is ApkDownloadState.Idle -> {
                    TextButton(
                        onClick = { viewModel.downloadAndInstallApk(info.downloadUrl) },
                        modifier = Modifier.tvFocusBorder()
                    ) { Text("立即更新") }
                }
                is ApkDownloadState.Downloading -> {
                    // 下载中只显示取消按钮
                    TextButton(
                        onClick = { viewModel.cancelApkDownload() },
                        modifier = Modifier.tvFocusBorder()
                    ) { Text("取消下载", color = Color(0xFFE57373)) }
                }
                is ApkDownloadState.Completed -> {
                    TextButton(
                        onClick = { viewModel.installDownloadedApk() },
                        modifier = Modifier.tvFocusBorder()
                    ) { Text("立即安装") }
                }
                is ApkDownloadState.Error -> {
                    TextButton(
                        onClick = { viewModel.downloadAndInstallApk(info.downloadUrl) },
                        modifier = Modifier.tvFocusBorder()
                    ) { Text("重试") }
                }
            }
        },
        dismissButton = {
            when {
                isDownloading -> {
                    // 下载中不显示 dismissButton（避免误触关闭对话框）
                }
                apkState is ApkDownloadState.Completed -> {
                    TextButton(
                        onClick = { viewModel.dismissUpdateDialog() },
                        modifier = Modifier.tvFocusBorder()
                    ) { Text("关闭") }
                }
                else -> {
                    val context = androidx.compose.ui.platform.LocalContext.current
                    TextButton(
                        onClick = {
                            // 备用方案：跳转浏览器（用于下载失败或特殊场景）
                            val intent = Intent(Intent.ACTION_VIEW, Uri.parse(info.downloadUrl))
                            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                            try {
                                context.startActivity(intent)
                                viewModel.dismissUpdateDialog()
                            } catch (e: Exception) {
                                Log.e("UpdateDialog", "open browser failed", e)
                            }
                        },
                        modifier = Modifier.tvFocusBorder()
                    ) { Text(if (apkState is ApkDownloadState.Error) "浏览器下载" else "稍后提醒") }
                }
            }
        }
    )
}
