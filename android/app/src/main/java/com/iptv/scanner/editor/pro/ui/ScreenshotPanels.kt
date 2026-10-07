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
// 截图面板
// -----------------------------------------------------------------

/**
 * 截图面板：与 PC 端 controllers/screenshot_controller.py 对齐。
 *
 * 功能：
 * - 截图模式选择（仅画面/含字幕/含 OSD）
 * - 截图按钮
 * - 保存到 Pictures/IPTV_Screenshots 目录
 */
@Composable
fun ScreenshotPanel(viewModel: AppViewModel) {
    var mode by remember { mutableStateOf("video") }
    val fileLoaded by viewModel.mpv.fileLoaded.collectAsState()

    // 连拍截图状态
    val burstActive by viewModel.burstActive.collectAsState()
    val burstCount by viewModel.burstCount.collectAsState()
    val burstTotal by viewModel.burstTotal.collectAsState()
    var burstInterval by remember { mutableStateOf(2.0) }
    var burstTotalInput by remember { mutableStateOf(10) }

    PanelScaffold(
        title = "截图",
        subtitle = "单张 / 连拍 / 保存到 Pictures/IPTV_Screenshots",
        onClose = {
            // 关闭面板时停止连拍
            if (burstActive) viewModel.stopBurstScreenshot()
            viewModel.toggleScreenshotPanel()
        }
    ) {
        if (!fileLoaded) {
            Text("未在播放，无法截图", color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 12.sp)
        }

        SettingsGroup("截图模式") {
            SelectionGroup(
                title = "截图模式",
                options = listOf("video" to "仅画面", "subtitles" to "含字幕", "window" to "含 OSD"),
                selectedKey = mode,
                onSelect = { m -> mode = m }
            )

            Spacer(modifier = Modifier.height(16.dp))

            // 单张截图按钮
            Surface(
                color = MaterialTheme.colorScheme.secondary,
                shape = RoundedCornerShape(8.dp),
                modifier = Modifier
                    .fillMaxWidth()
                    .height(52.dp)
                    .clickable {
                        if (fileLoaded) viewModel.takeScreenshot(mode)
                        else viewModel.showOsd("未在播放")
                    }
                    .tvFocusBorder()
            ) {
                Row(
                    modifier = Modifier.fillMaxSize(),
                    horizontalArrangement = Arrangement.Center,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Icon(Icons.Default.CameraAlt, contentDescription = null, tint = MaterialTheme.colorScheme.onSurface)
                    Spacer(modifier = Modifier.width(8.dp))
                    Text("截图", color = MaterialTheme.colorScheme.onSurface, fontSize = 16.sp, fontWeight = FontWeight.Medium)
                }
            }

            Spacer(modifier = Modifier.height(20.dp))
        }

        SettingsGroup("连拍截图") {
            // -----------------------------------------------------------------
            // 连拍截图（与 PC 端 BurstScreenshotDialog 对齐）
            // -----------------------------------------------------------------
            DescText("按设定间隔自动截图，适合捕捉精彩瞬间")

            LabeledSlider(
                label = "间隔（秒）",
                value = burstInterval.toFloat(),
                range = 0.5f..60f,
                valueText = "${"%.1f".format(burstInterval)}s",
                onValueChange = { burstInterval = it.toDouble() },
                onReset = { burstInterval = 2.0 }
            )

            LabeledSlider(
                label = "总数（张）",
                value = burstTotalInput.toFloat(),
                range = 1f..999f,
                valueText = burstTotalInput.toString(),
                onValueChange = { burstTotalInput = it.toInt() },
                onReset = { burstTotalInput = 10 }
            )

            // 连拍进度
            if (burstActive) {
                Spacer(modifier = Modifier.height(8.dp))
                LinearProgressIndicator(
                    progress = { if (burstTotal > 0) burstCount.toFloat() / burstTotal else 0f },
                    modifier = Modifier.fillMaxWidth(),
                    color = MaterialTheme.colorScheme.secondary,
                    trackColor = MaterialTheme.colorScheme.surfaceVariant
                )
                Spacer(modifier = Modifier.height(4.dp))
                Text(
                    text = "进度：$burstCount / $burstTotal",
                    color = MaterialTheme.colorScheme.secondary,
                    fontSize = 12.sp
                )
            }

            Spacer(modifier = Modifier.height(8.dp))

            // 开始/停止连拍按钮
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                if (!burstActive) {
                    OutlinedButton(
                        onClick = {
                            if (fileLoaded) viewModel.startBurstScreenshot(burstInterval, burstTotalInput, mode)
                            else viewModel.showOsd("未在播放")
                        },
                        modifier = Modifier.tvFocusBorder()
                    ) { Text("开始连拍") }
                } else {
                    OutlinedButton(
                        onClick = { viewModel.stopBurstScreenshot() },
                        modifier = Modifier.tvFocusBorder()
                    ) { Text("停止连拍") }
                }
            }

            Spacer(modifier = Modifier.height(16.dp))
            DescText("截图自动保存到设备的 Pictures/IPTV_Screenshots 目录")
        }
    }
}
