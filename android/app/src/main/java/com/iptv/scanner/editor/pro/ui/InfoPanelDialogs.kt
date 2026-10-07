package com.iptv.scanner.editor.pro.ui

import android.content.Context
import android.content.res.Configuration
import android.util.Log
import androidx.compose.runtime.key
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.clickable
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.systemBarsPadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.ui.draw.blur
import androidx.compose.ui.draw.shadow
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AspectRatio
import androidx.compose.material.icons.filled.Brightness4
import androidx.compose.material.icons.filled.CalendarMonth
import androidx.compose.material.icons.filled.CropFree
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.LockOpen
import androidx.compose.material.icons.filled.Menu
import androidx.compose.material.icons.filled.MusicNote
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.Pause
import androidx.compose.material.icons.filled.PictureInPicture
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.SkipNext
import androidx.compose.material.icons.filled.SkipPrevious
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material.icons.filled.VideoLibrary
import androidx.compose.material.icons.filled.VolumeOff
import androidx.compose.material.icons.filled.VolumeUp
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.RadioButton
import androidx.activity.compose.BackHandler
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Slider
import androidx.compose.material3.SliderDefaults
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.movableContentOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.derivedStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.text.style.TextAlign
import com.iptv.scanner.editor.pro.R
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import coil.compose.AsyncImage
import kotlinx.coroutines.delay
import com.iptv.scanner.editor.pro.data.ReminderItem
import com.iptv.scanner.editor.pro.data.UserPrefs
import com.iptv.scanner.editor.pro.data.IptvChannel
import com.iptv.scanner.editor.pro.mpv.MPVView
import com.iptv.scanner.editor.pro.mpv.MPVViewLike
import com.iptv.scanner.editor.pro.player.PlayerType
import com.iptv.scanner.editor.pro.player.ProgressHelper
import com.iptv.scanner.editor.pro.ui.ChannelTab
import com.iptv.scanner.editor.pro.ui.theme.PlayerOverlayColors
import com.iptv.scanner.editor.pro.ui.theme.rememberPlayerOverlayColors
import androidx.media3.ui.PlayerView
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material.icons.filled.Build
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Star
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.Favorite
import androidx.compose.material.icons.filled.FavoriteBorder
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.ChevronRight
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.DeleteSweep
import androidx.compose.material3.AlertDialog
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.gestures.detectVerticalDragGestures
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.graphics.asComposeRenderEffect
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.foundation.layout.PaddingValues
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import android.net.Uri
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.material.icons.filled.FileOpen
import androidx.compose.material.icons.filled.Movie
import androidx.compose.material.icons.filled.PlayCircle
import androidx.compose.material.icons.filled.Link
import androidx.compose.material.icons.filled.Web
import androidx.compose.material.icons.filled.Radar
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.GridView
import androidx.compose.material.icons.filled.ViewList
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.GridItemSpan
import androidx.compose.foundation.lazy.grid.items as gridItems
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.rememberScrollState
import com.iptv.scanner.editor.pro.player.CatchupHelper
import androidx.compose.material.icons.filled.History
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.material3.SheetState
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.filled.Cloud
import androidx.compose.material.icons.filled.Folder
import androidx.compose.material.icons.filled.SwapHoriz
import java.io.File

@Composable
internal fun OsdView(
    title: String,
    subtitle: String,
    extra: String
) {
    Surface(
        color = MaterialTheme.colorScheme.surface.copy(alpha = 0.9f),
        shape = RoundedCornerShape(8.dp),
        modifier = Modifier
            .statusBarsPadding()
            .padding(top = 48.dp)
            .padding(horizontal = 16.dp)
    ) {
        Column(
            modifier = Modifier
                .padding(horizontal = 16.dp, vertical = 10.dp)
        ) {
            Text(
                text = title,
                color = MaterialTheme.colorScheme.onSurface,
                fontSize = 14.sp,
                fontWeight = FontWeight.Medium
            )
            if (subtitle.isNotEmpty()) {
                Spacer(modifier = Modifier.height(2.dp))
                Text(
                    text = subtitle,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    fontSize = 12.sp
                )
            }
            if (extra.isNotEmpty()) {
                Spacer(modifier = Modifier.height(2.dp))
                Text(
                    text = extra,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    fontSize = 11.sp
                )
            }
        }
    }
}

// -----------------------------------------------------------------
// 提醒触发弹窗（节目即将开始时弹出）
// 与 PC 端 ui/dialogs/reminder_popup.py 对齐
/**
 * 提醒弹窗：节目即将开始时弹出，提供"切换频道"和"稍后"两个选项。
 *
 * - 全屏半透明遮罩
 * - 中央卡片显示节目信息
 * - "切换频道"：切到目标频道并关闭弹窗
 * - "稍后"：仅关闭弹窗
 */
@Composable
internal fun ReminderPopup(
    reminder: ReminderItem,
    onAccept: () -> Unit,
    onDismiss: () -> Unit
) {
    val isAptv = LocalConfiguration.current.orientation == Configuration.ORIENTATION_PORTRAIT
    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(Color(0xAA000000))
            .clickable(enabled = false) {},  // 阻断背景点击
        contentAlignment = Alignment.Center
    ) {
        Surface(
            color = if (isAptv) MaterialTheme.colorScheme.surface else MaterialTheme.colorScheme.surfaceVariant,
            shape = RoundedCornerShape(12.dp),
            modifier = Modifier.fillMaxWidth(0.85f)
        ) {
            Column(
                modifier = Modifier.padding(20.dp),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                // 顶部图标
                Icon(
                    Icons.Default.Notifications,
                    contentDescription = null,
                    tint = if (isAptv) AptvAccent else Color(0xFFFFC107),
                    modifier = Modifier
                        .width(48.dp)
                        .height(48.dp)
                )
                Spacer(modifier = Modifier.height(12.dp))

                // 标题
                Text(
                    text = "节目即将开始",
                    color = MaterialTheme.colorScheme.onSurface,
                    fontSize = 18.sp,
                    fontWeight = FontWeight.Medium
                )
                Spacer(modifier = Modifier.height(16.dp))

                // 节目信息卡片
                Surface(
                    color = MaterialTheme.colorScheme.surfaceVariant,
                    shape = RoundedCornerShape(8.dp),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Column(modifier = Modifier.padding(12.dp)) {
                        Text(
                            text = reminder.programTitle.ifBlank { "（未命名节目）" },
                            color = MaterialTheme.colorScheme.onSurface,
                            fontSize = 15.sp,
                            fontWeight = FontWeight.Medium,
                            maxLines = 2
                        )
                        if (reminder.channelName.isNotEmpty()) {
                            Spacer(modifier = Modifier.height(4.dp))
                            Text(
                                text = "频道: ${reminder.channelName}",
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                fontSize = 12.sp
                            )
                        }
                        if (reminder.startTs > 0) {
                            Spacer(modifier = Modifier.height(2.dp))
                            val timeStr = java.text.SimpleDateFormat(
                                "MM-dd HH:mm",
                                java.util.Locale.getDefault()
                            ).format(java.util.Date(reminder.startTs))
                            Text(
                                text = "开始: $timeStr",
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                fontSize = 12.sp
                            )
                        }
                    }
                }
                Spacer(modifier = Modifier.height(20.dp))

                // 按钮行
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(12.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    OutlinedButton(
                        onClick = onDismiss,
                        modifier = Modifier.weight(1f)
                    ) {
                        Text("稍后", color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    Button(
                        onClick = onAccept,
                        colors = ButtonDefaults.buttonColors(
                            containerColor = if (isAptv) AptvAccent else MaterialTheme.colorScheme.secondary
                        ),
                        modifier = Modifier.weight(1f)
                    ) {
                        Text("切换频道", color = if (isAptv) Color.White else MaterialTheme.colorScheme.onSecondary)
                    }
                }
            }
        }
    }
}

// -----------------------------------------------------------------
// 快捷工具栏 (QuickActionBar)
//
// 在视频控制层中提供常用功能的快捷入口，避免每次都要打开主菜单。
// 图标颜色随深色/浅色主题自适应。
/**
 * 频道信息详情对话框
 */
@Composable
internal fun ChannelInfoDialog(viewModel: AppViewModel) {
    val currentChannel by viewModel.currentChannel.collectAsState()
    val mpv = viewModel.mpv
    val videoWidth by mpv.videoWidth.collectAsState()
    val videoHeight by mpv.videoHeight.collectAsState()
    val currentProgram = viewModel.getCurrentProgram()
    val oc = rememberPlayerOverlayColors()
    val isAptv = LocalConfiguration.current.orientation == Configuration.ORIENTATION_PORTRAIT
    val accentColor = if (isAptv) AptvAccent else oc.accent

AlertDialog(
onDismissRequest = { viewModel.toggleChannelInfo() },
containerColor = if (isAptv) MaterialTheme.colorScheme.surface else oc.topBarBg.copy(alpha = 0.80f),
shape = RoundedCornerShape(20.dp),
modifier = Modifier.border(1.dp, accentColor.copy(alpha = 0.35f), RoundedCornerShape(20.dp)),
        title = {
            Row(verticalAlignment = Alignment.CenterVertically) {
                if (currentChannel != null && currentChannel!!.logo.isNotEmpty()) {
                    AsyncImage(
                        model = currentChannel!!.logo,
                        contentDescription = null,
                        modifier = Modifier
                            .size(48.dp)
                            .clip(RoundedCornerShape(4.dp)),
                        contentScale = ContentScale.Fit
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                }
                Text(
                    text = currentChannel?.name ?: "频道信息",
                    color = if (isAptv) MaterialTheme.colorScheme.onSurface else oc.textPrimary,
                    fontSize = 16.sp,
                    fontWeight = FontWeight.Medium
                )
            }
        },
        text = {
            Column(modifier = Modifier.fillMaxWidth()) {
                currentChannel?.let { ch ->
                    InfoRow("频道名", ch.name, oc, isAptv)
                    if (ch.group.isNotEmpty()) InfoRow("分类", ch.group, oc, isAptv)
                    if (ch.tvgId.isNotEmpty()) InfoRow("TVG-ID", ch.tvgId, oc, isAptv)
                    if (ch.tvgName.isNotEmpty()) InfoRow("TVG-Name", ch.tvgName, oc, isAptv)
                    if (ch.tvgChno.isNotEmpty()) InfoRow("频道号", ch.tvgChno, oc, isAptv)
                    if (ch.resolution.isNotEmpty()) InfoRow("分辨率", ch.resolution, oc, isAptv)
                    if (videoWidth > 0 && videoHeight > 0) {
                        InfoRow("视频尺寸", "${videoWidth}x${videoHeight}", oc, isAptv)
                    }
if (ch.catchup.isNotEmpty() && ch.catchup != "none") {
    if (ch.catchupDays.isNotEmpty()) InfoRow("回看天数", ch.catchupDays, oc, isAptv)
}
if (ch.source.isNotEmpty()) InfoRow("来源", ch.source, oc, isAptv)
// 状态字段仅在有实际状态时显示（去掉“待检测”）
if (ch.status.isNotEmpty() && ch.status != "待检测") InfoRow("状态", ch.status, oc, isAptv)
InfoRow("URL", ch.url, oc, isAptv)
// 回看 URL
if (ch.catchup.isNotEmpty() && ch.catchup != "none") {
    val catchupUrl = if (ch.catchupSource.isNotEmpty()) ch.catchupSource else ch.catchup
    InfoRow("回看URL", catchupUrl, oc, isAptv)
}
                    // 当前节目
                    if (currentProgram != null && currentProgram.title.isNotEmpty()) {
                        Spacer(modifier = Modifier.height(8.dp))
                        Text(
                            text = "当前节目",
                            color = accentColor,
                            fontSize = 12.sp,
                            fontWeight = FontWeight.Medium
                        )
                        Text(
                            text = currentProgram.title,
                            color = if (isAptv) MaterialTheme.colorScheme.onSurface else oc.textPrimary,
                            fontSize = 13.sp,
                            modifier = Modifier.padding(top = 2.dp)
                        )
                    }
                } ?: run {
                    Text(
                        text = "未选择频道",
                        color = if (isAptv) MaterialTheme.colorScheme.onSurfaceVariant else oc.textSecondary,
                        fontSize = 14.sp
                    )
                }
            }
        },
        confirmButton = {
            Button(
                onClick = { viewModel.toggleChannelInfo() },
                colors = ButtonDefaults.buttonColors(containerColor = accentColor)
            ) {
                Text("关闭", color = if (isAptv) Color.White else MaterialTheme.colorScheme.onSecondary)
            }
        }
    )
}
@Composable
internal fun InfoRow(label: String, value: String, oc: PlayerOverlayColors, isAptv: Boolean = false) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 3.dp),
        verticalAlignment = Alignment.Top
    ) {
        Text(
            text = "$label:",
            color = if (isAptv) MaterialTheme.colorScheme.onSurfaceVariant else oc.textSecondary,
            fontSize = 12.sp,
            modifier = Modifier.width(60.dp)
        )
        Text(
            text = value,
            color = if (isAptv) MaterialTheme.colorScheme.onSurface else oc.textPrimary,
            fontSize = 12.sp,
            modifier = Modifier.weight(1f),
            maxLines = 5,
            overflow = TextOverflow.Ellipsis
        )
    }
}
/**
 * 视频参数信息行：显示视频编码、分辨率、音频编码、HDR/WCG 信息
 */
@Composable
internal fun PortraitMediaInfoBar(viewModel: AppViewModel) {
    val player = viewModel.mpv
    val fileLoaded by player.fileLoaded.collectAsState()
    val videoWidth by player.videoWidth.collectAsState()
    val videoHeight by player.videoHeight.collectAsState()
    val playerType by viewModel.playerType.collectAsState()
    val oc = rememberPlayerOverlayColors()

    // 1秒刷新媒体信息
    var tick by remember { mutableStateOf(0L) }
    LaunchedEffect(fileLoaded) {
        if (fileLoaded) {
            while (true) {
                tick = System.currentTimeMillis()
                delay(2000L)
            }
        }
    }

    val mediaInfo = remember(tick, fileLoaded, videoWidth, videoHeight) {
        // 只有在文件已加载且视频尺寸有效时才获取媒体信息
        // 停止状态（fileLoaded=false）不显示任何媒体信息
        if (fileLoaded && (videoWidth > 0 || videoHeight > 0)) player.getMediaInfo() else emptyMap()
    }

    // 停止状态（未加载文件）不显示媒体信息栏
    if (!fileLoaded) {
        Box(modifier = Modifier.fillMaxWidth().height(0.dp))
        return
    }

    Surface(
        color = oc.infoBarBg,
        modifier = Modifier
            .fillMaxWidth()
            .padding(top = 2.dp)  // 与视频区域间距
    ) {
        if (mediaInfo.isNotEmpty()) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(28.dp)
                    .padding(horizontal = 8.dp, vertical = 2.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                // 视频编码（清理前缀：video/hevc → HEVC）
                mediaInfo["videoCodec"]?.takeIf { it.isNotEmpty() && it != "null" }?.let { codec ->
                    val cleanCodec = codec.removePrefix("video/").removePrefix("audio/").uppercase()
                    MediaBadge(label = cleanCodec, oc = oc)
                }
                // 分辨率
                if (videoWidth > 0 && videoHeight > 0) {
                    val resLabel = if (videoHeight >= 2160) "4K"
                        else if (videoHeight >= 1080) "1080P"
                        else if (videoHeight >= 720) "720P"
                        else if (videoHeight >= 480) "480P"
                        else "${videoHeight}P"
                    MediaBadge(label = resLabel, oc = oc)
                    MediaBadge(label = "${videoWidth}×${videoHeight}", oc = oc, isAccent = false)
                }
                // FPS
                mediaInfo["fps"]?.takeIf { it.isNotEmpty() && it != "null" && it != "0" && it != "0.000" }?.let { fps ->
                    val fpsVal = fps.toFloatOrNull()
                    val fpsLabel = if (fpsVal != null) "${fpsVal.toInt()}fps" else "${fps}fps"
                    MediaBadge(label = fpsLabel, oc = oc)
                }
                // 音频编码（清理前缀：audio/aac → AAC）
                mediaInfo["audioCodec"]?.takeIf { it.isNotEmpty() && it != "null" }?.let { codec ->
                    val cleanCodec = codec.removePrefix("audio/").removePrefix("video/").uppercase()
                    MediaBadge(label = cleanCodec, oc = oc, isAccent = false)
                }
                // HDR / HLG / WCG 检测
                val primaries = mediaInfo["videoPrimaries"]
                val gamma = mediaInfo["videoGamma"]
                if (primaries == "bt.2020" || primaries == "bt.2100") {
                    when (gamma) {
                        "pq" -> MediaBadge(label = "HDR10", oc = oc, isHighlight = true)
                        "hlg" -> MediaBadge(label = "HLG", oc = oc, isHighlight = true)
                        else -> MediaBadge(label = "WCG", oc = oc)
                    }
                }
                // 硬件解码
                mediaInfo["hwdec"]?.takeIf { it.isNotEmpty() && it != "null" && it != "no" }?.let { hwdec ->
                    MediaBadge(label = "HW", oc = oc, isAccent = false)
                }
            }
        } else {
            // 文件已加载但视频尺寸未知（纯音频流），显示播放器类型
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(22.dp)
                    .padding(horizontal = 8.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = "内核: ${playerType.name}",
                    color = oc.textSecondary,
                    fontSize = 10.sp
                )
            }
        }
    }
}
@Composable
private fun MediaBadge(
    label: String,
    oc: PlayerOverlayColors,
    isAccent: Boolean = true,
    isHighlight: Boolean = false
) {
    // 统一颜色：所有 badge 用 AptvAccent，除 HDR/HLG 高亮外
    val bg = if (isHighlight) Color(0xFFFF6B00).copy(alpha = 0.2f)
             else AptvAccent.copy(alpha = 0.15f)
    val fg = if (isHighlight) Color(0xFFFF9800)
             else AptvAccent
    Surface(
        color = bg,
        shape = RoundedCornerShape(3.dp)
    ) {
        Text(
            text = label,
            color = fg,
            fontSize = 9.sp,
            fontWeight = FontWeight.Medium,
            modifier = Modifier.padding(horizontal = 4.dp, vertical = 1.dp),
            maxLines = 1
        )
    }
}
/**
 * 竖屏模式面板弹窗包装器：将全屏面板包装为居中弹窗
 * 半透明背景 + 圆角 + 边框，点击外部关闭
 */
@Composable
fun PortraitPanelDialog(
    onDismiss: () -> Unit,
    content: @Composable () -> Unit
) {
    val oc = rememberPlayerOverlayColors()
    val isAndroid12Plus = android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.S
    val dialogShape = RoundedCornerShape(20.dp)
    val configuration = androidx.compose.ui.platform.LocalConfiguration.current
    val isLandscape = configuration.orientation == android.content.res.Configuration.ORIENTATION_LANDSCAPE
    val context = androidx.compose.ui.platform.LocalContext.current
    val isTv = context.packageManager.hasSystemFeature(android.content.pm.PackageManager.FEATURE_LEANBACK)
    val origDensity = androidx.compose.ui.platform.LocalDensity.current
    val dpiScale = if (isTv || isLandscape) (configuration.screenHeightDp / 720f).coerceIn(0.55f, 1f) else 1f
    val scaledDensity = androidx.compose.ui.unit.Density(origDensity.density * dpiScale, origDensity.fontScale)
    val scaledContent: @Composable () -> Unit = {
        androidx.compose.runtime.CompositionLocalProvider(androidx.compose.ui.platform.LocalDensity provides scaledDensity) {
            content()
        }
    }
    if (isTv) {
        Box(
            modifier = Modifier
                .fillMaxSize()
                .background(Color.Black.copy(alpha = 0.5f))
        ) {
            Box(
                modifier = Modifier
                    .align(Alignment.Center)
                    .fillMaxWidth(0.75f)
                    .fillMaxHeight(0.82f)
            ) {
                Surface(
                    color = oc.topBarBg.copy(alpha = 0.85f),
                    shape = dialogShape,
                    border = BorderStroke(1.dp, oc.accent.copy(alpha = 0.35f)),
                    modifier = Modifier.matchParentSize()
                ) {
                    scaledContent()
                }
            }
        }
    } else if (isLandscape) {
        Dialog(
            onDismissRequest = onDismiss,
            properties = DialogProperties(
                usePlatformDefaultWidth = false,
                dismissOnBackPress = true,
                dismissOnClickOutside = false
            )
        ) {
            Box(
                modifier = Modifier
                    .fillMaxWidth(0.75f)
                    .fillMaxHeight(0.82f)
            ) {
                if (isAndroid12Plus) {
                    Box(
                        modifier = Modifier
                            .matchParentSize()
                            .blur(25.dp)
                            .background(oc.topBarBg.copy(alpha = 0.55f), dialogShape)
                    )
                }
                Surface(
                    color = if (isAndroid12Plus) oc.topBarBg.copy(alpha = 0.30f) else oc.topBarBg.copy(alpha = 0.80f),
                    shape = dialogShape,
                    border = BorderStroke(1.dp, oc.accent.copy(alpha = 0.35f)),
                    modifier = Modifier.matchParentSize()
                ) {
                    scaledContent()
                }
            }
        }
    } else {
        // ---- 手机竖屏：APTV 式全屏 push 页（右侧滑入，实底背景，BACK 关闭） ----
        Dialog(
            onDismissRequest = onDismiss,
            properties = DialogProperties(
                usePlatformDefaultWidth = false,
                dismissOnBackPress = true,
                dismissOnClickOutside = false
            )
        ) {
            var pushVisible by remember { mutableStateOf(false) }
            LaunchedEffect(Unit) { pushVisible = true }
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .background(Color.Black.copy(alpha = 0.55f))
                    .clickable { onDismiss() }
            ) {
                androidx.compose.animation.AnimatedVisibility(
                    visible = pushVisible,
                    enter = androidx.compose.animation.slideInHorizontally(
                        initialOffsetX = { it },
                        animationSpec = androidx.compose.animation.core.tween(220)
                    ),
                    exit = androidx.compose.animation.slideOutHorizontally(
                        targetOffsetX = { it },
                        animationSpec = androidx.compose.animation.core.tween(180)
                    ),
                    modifier = Modifier.fillMaxSize()
                ) {
                    // 实底全屏页：消费自身点击（不透传 scrim），避免误触关闭
                    Surface(
                        color = MaterialTheme.colorScheme.background,
                        modifier = Modifier
                            .fillMaxSize()
                            .clickable(
                                interactionSource = remember { androidx.compose.foundation.interaction.MutableInteractionSource() },
                                indication = null
                            ) { }
                    ) {
                        // APTV 风格开关：竖屏 push 页内的共用基座组件（PanelScaffold 等）切换 APTV 样式
                        // 同时覆盖 MaterialTheme primary 色为 AptvAccent，让 Switch/RadioButton/FilterChip 等自动适配
                        androidx.compose.runtime.CompositionLocalProvider(LocalAptvStyle provides true) {
                            val aptvScheme = MaterialTheme.colorScheme.copy(
                                primary = AptvAccent,
                                onPrimary = Color.White,
                                primaryContainer = AptvAccent.copy(alpha = 0.15f),
                                onPrimaryContainer = AptvAccent,
                            )
                            MaterialTheme(colorScheme = aptvScheme) {
                                scaledContent()
                            }
                        }
                    }
                }
            }
        }
    }
}
