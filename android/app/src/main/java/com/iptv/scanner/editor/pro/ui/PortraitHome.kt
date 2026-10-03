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
import com.iptv.scanner.editor.pro.mpv.MPVTextureView
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

/**
 * 竖屏首页：用户打开 App 首先看到的界面。
 *
 * 布局：
 * 1. 顶部 App 标题栏（logo + 菜单按钮）
 * 2. 快捷入口网格（频道列表 / 打开本地文件 / 打开播放列表 / 网络流 / 订阅源 / 扫描整理）
 * 3. 正在播放卡片（如果有视频在播放，显示迷你播放器条，点击返回播放器）
 * 4. 最近播放（水平滚动频道卡片）
 * 5. 收藏频道（水平滚动频道卡片）
 */
@Composable
internal fun PortraitHomeScreen(
    viewModel: AppViewModel,
    playlistLauncher: androidx.activity.result.ActivityResultLauncher<Array<String>>,
    videoLauncher: androidx.activity.result.ActivityResultLauncher<Array<String>>
) {
    val oc = rememberPlayerOverlayColors()
    val channels by viewModel.channels.collectAsState()
    val history by viewModel.history.collectAsState()
    val favorites by viewModel.favorites.collectAsState()
    val currentChannel by viewModel.currentChannel.collectAsState()
    val displayInfo by viewModel.channelDisplayInfo.collectAsState()
    val fileLoaded by viewModel.mpv.fileLoaded.collectAsState()
    val paused by viewModel.mpv.paused.collectAsState()

    val recentChannels = remember(history, channels) {
        history.mapNotNull { idx -> channels.getOrNull(idx) }.take(20)
    }
    val favChannels = remember(favorites, channels) {
        favorites.mapNotNull { idx -> channels.getOrNull(idx) }.take(20)
    }

    // 通过 URL 查找频道索引（比 indexOf 更稳健，避免频道属性变更后匹配失败）
    fun findChannelIdx(channel: IptvChannel): Int = channels.indexOfFirst { it.url == channel.url }

    val bgColor = MaterialTheme.colorScheme.background

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(bgColor)
    ) {
        // 1. App 标题栏（无菜单按钮，功能入口在工具和设置页）
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .height(52.dp)
                .padding(horizontal = 16.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = "ISEP",
                style = MaterialTheme.typography.titleLarge,
                color = MaterialTheme.colorScheme.primary,
                fontWeight = FontWeight.Bold
            )
            Spacer(modifier = Modifier.weight(1f))
            Text(
                text = "IPTV Studio",
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }

        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            contentPadding = PaddingValues(bottom = 72.dp)
        ) {
            // 2. 快捷入口网格
            item {
                QuickActionGrid(
                    viewModel = viewModel,
                    playlistLauncher = playlistLauncher,
                    videoLauncher = videoLauncher
                )
            }

            // 3. 正在播放卡片
            if (fileLoaded && (currentChannel != null || displayInfo.name.isNotEmpty())) {
                item {
                    MiniPlayerCard(
                        viewModel = viewModel,
                        channelName = currentChannel?.name ?: displayInfo.name,
                        channelLogo = currentChannel?.logo ?: "",
                        groupName = currentChannel?.group ?: "",
                        isPaused = paused,
                        oc = oc,
                        onClick = { viewModel.showPlayerScreen() },
                        onPlayPause = { viewModel.mpv.togglePause() }
                    )
                }
            }

            // 4. 最近播放
            if (recentChannels.isNotEmpty()) {
                item {
                    HomeSectionHeader(title = "最近播放", oc = oc)
                }
                item {
                    LazyRow(
                        modifier = Modifier.fillMaxWidth(),
                        contentPadding = PaddingValues(horizontal = 12.dp),
                        horizontalArrangement = Arrangement.spacedBy(10.dp)
                    ) {
                        items(recentChannels) { channel ->
                            HomeChannelCard(
                                channel = channel,
                                oc = oc,
                                onClick = {
                                    val idx = findChannelIdx(channel)
                                    if (idx >= 0) viewModel.playChannel(idx)
                                }
                            )
                        }
                    }
                }
            }

            // 5. 收藏频道
            item {
                Spacer(modifier = Modifier.height(16.dp))
                HomeSectionHeader(title = "收藏频道", oc = oc)
            }
            if (favChannels.isNotEmpty()) {
                item {
                    LazyRow(
                        modifier = Modifier.fillMaxWidth(),
                        contentPadding = PaddingValues(horizontal = 12.dp),
                        horizontalArrangement = Arrangement.spacedBy(10.dp)
                    ) {
                        items(favChannels) { channel ->
                            HomeChannelCard(
                                channel = channel,
                                oc = oc,
                                onClick = {
                                    val idx = findChannelIdx(channel)
                                    if (idx >= 0) viewModel.playChannel(idx)
                                }
                            )
                        }
                    }
                }
            } else {
                // 无收藏时显示空状态提示
                item {
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(horizontal = 16.dp, vertical = 16.dp),
                        contentAlignment = Alignment.Center
                    ) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Icon(
                                Icons.Default.FavoriteBorder,
                                contentDescription = null,
                                tint = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.3f),
                                modifier = Modifier.size(48.dp)
                            )
                            Spacer(modifier = Modifier.height(6.dp))
                            Text(
                                text = "暂无收藏频道",
                                color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.5f),
                                fontSize = 12.sp
                            )
                            Spacer(modifier = Modifier.height(2.dp))
                            Text(
                                text = stringResource(R.string.hint_long_press_favorite),
                                color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.4f),
                                fontSize = 10.sp
                            )
                        }
                    }
                }
            }

            // 空状态提示
            if (recentChannels.isEmpty() && favChannels.isEmpty() && channels.isEmpty()) {
                item {
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(top = 48.dp),
                        contentAlignment = Alignment.Center
                    ) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Icon(
                                Icons.Default.VideoLibrary,
                                contentDescription = null,
                                tint = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.4f),
                                modifier = Modifier.size(48.dp)
                            )
                            Spacer(modifier = Modifier.height(12.dp))
                            Text(
                                text = "暂无频道",
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                fontSize = 14.sp
                            )
                            Spacer(modifier = Modifier.height(4.dp))
                            Text(
                                text = "点击「打开播放列表」或「订阅源管理」添加频道",
                                color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.6f),
                                fontSize = 12.sp
                            )
                        }
                    }
                }
            }
        }
    }
}
/** 快捷入口网格：3列2行 */
@Composable
private fun QuickActionGrid(
    viewModel: AppViewModel,
    playlistLauncher: androidx.activity.result.ActivityResultLauncher<Array<String>>,
    videoLauncher: androidx.activity.result.ActivityResultLauncher<Array<String>>
) {
    val oc = rememberPlayerOverlayColors()
    val actions = listOf(
        QuickAction(Icons.Default.VideoLibrary, stringResource(R.string.quick_channel_list), stringResource(R.string.quick_channel_list_desc)) {
            viewModel.setPortraitTab(PortraitTab.LIST)
        },
        QuickAction(Icons.Default.Movie, "本地文件", "播放视频/音频") {
            if (!viewModel.isSafAvailable()) {
                viewModel.showMediaFileBrowser()
            } else {
                videoLauncher.launch(arrayOf("video/*", "audio/*", "application/x-matroska", "application/octet-stream"))
            }
        },
        QuickAction(Icons.Default.FileOpen, "播放列表", "导入 M3U/M3U8") {
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
        QuickAction(Icons.Default.Link, "网络流", "输入 URL 播放") {
            viewModel.toggleOpenUrlDialog()
        },
        QuickAction(Icons.Default.Web, "订阅源", "管理 M3U 订阅") {
            viewModel.setSourceTab(SourceTab.PLAYLIST)
            viewModel.toggleSourceManager()
        },
        QuickAction(Icons.Default.Radar, "扫描整理", "URL 范围扫描") {
            viewModel.toggleScanPanel()
        }
    )

    Column(modifier = Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 8.dp)) {
        actions.chunked(3).forEach { rowActions ->
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                rowActions.forEach { action ->
                    QuickActionCard(action = action, oc = oc, modifier = Modifier.weight(1f))
                }
                repeat(3 - rowActions.size) {
                    Spacer(modifier = Modifier.weight(1f))
                }
            }
            Spacer(modifier = Modifier.height(10.dp))
        }
    }
}
private data class QuickAction(
    val icon: androidx.compose.ui.graphics.vector.ImageVector,
    val title: String,
    val subtitle: String,
    val onClick: () -> Unit
)
@Composable
private fun QuickActionCard(
    action: QuickAction,
    oc: PlayerOverlayColors,
    modifier: Modifier = Modifier
) {
    Surface(
        color = MaterialTheme.colorScheme.surfaceVariant,
        shape = RoundedCornerShape(14.dp),
        modifier = modifier
            .height(108.dp)
            .clip(RoundedCornerShape(14.dp))
            .clickable(onClick = action.onClick)
    ) {
        Column(
            modifier = Modifier.fillMaxSize().padding(8.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center
        ) {
            Box(
                modifier = Modifier
                    .size(36.dp)
                    .clip(CircleShape)
                    .background(MaterialTheme.colorScheme.primary.copy(alpha = 0.12f)),
                contentAlignment = Alignment.Center
            ) {
                Icon(
                    imageVector = action.icon,
                    contentDescription = action.title,
                    tint = MaterialTheme.colorScheme.primary,
                    modifier = Modifier.size(22.dp)
                )
            }
            Spacer(modifier = Modifier.height(6.dp))
            Text(
                text = action.title,
                color = MaterialTheme.colorScheme.onSurface,
                fontSize = 13.sp,
                fontWeight = FontWeight.Medium,
                maxLines = 1
            )
            Spacer(modifier = Modifier.height(2.dp))
            Text(
                text = action.subtitle,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                fontSize = 10.sp,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
                textAlign = androidx.compose.ui.text.style.TextAlign.Center
            )
        }
    }
}
/** 首页分组标题 */
@Composable
private fun HomeSectionHeader(title: String, oc: PlayerOverlayColors) {
    Text(
        text = title,
        color = MaterialTheme.colorScheme.onBackground,
        fontSize = 15.sp,
        fontWeight = FontWeight.SemiBold,
        modifier = Modifier.padding(horizontal = 16.dp, vertical = 6.dp)
    )
}
/** 正在播放迷你卡片（含节目名 + 媒体信息标识） */
@Composable
private fun MiniPlayerCard(
    viewModel: AppViewModel,
    channelName: String,
    channelLogo: String,
    groupName: String,
    isPaused: Boolean,
    oc: PlayerOverlayColors,
    onClick: () -> Unit,
    onPlayPause: () -> Unit
) {
    val currentIdx by viewModel.currentIdx.collectAsState()
    val epgCacheVersion by viewModel.epgCacheVersion.collectAsState()
    val player = viewModel.mpv
    val videoWidth by player.videoWidth.collectAsState()
    val videoHeight by player.videoHeight.collectAsState()

    // 获取当前节目
    val currentProgram = remember(currentIdx, epgCacheVersion) {
        if (currentIdx >= 0) viewModel.getCachedCurrentProgram(currentIdx) else null
    }

    // 获取媒体信息
    var mediaInfo by remember { mutableStateOf(emptyMap<String, String?>()) }
    LaunchedEffect(videoWidth, videoHeight) {
        if (videoWidth > 0) {
            mediaInfo = player.getMediaInfo()
        }
    }

    Surface(
        color = MaterialTheme.colorScheme.primary.copy(alpha = 0.08f),
        shape = RoundedCornerShape(12.dp),
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.primary.copy(alpha = 0.25f)),
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 12.dp, vertical = 4.dp)
            .clip(RoundedCornerShape(12.dp))
            .clickable(onClick = onClick)
    ) {
        Column(
            modifier = Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 8.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically
            ) {
                // 频道 logo（带自适应背景色）
                if (channelLogo.isNotEmpty()) {
                    Box(
                        modifier = Modifier
                            .size(48.dp)
                            .clip(RoundedCornerShape(4.dp))
                            .background(MaterialTheme.colorScheme.surfaceVariant),
                        contentAlignment = Alignment.Center
                    ) {
                        AsyncImage(
                            model = channelLogo,
                            contentDescription = null,
                            modifier = Modifier.fillMaxSize().padding(2.dp),
                            contentScale = ContentScale.Fit
                        )
                    }
                    Spacer(modifier = Modifier.width(10.dp))
                } else {
                    Icon(
                        Icons.Default.PlayArrow,
                        contentDescription = null,
                        tint = MaterialTheme.colorScheme.primary,
                        modifier = Modifier.size(24.dp)
                    )
                    Spacer(modifier = Modifier.width(10.dp))
                }
                // 频道名 + 分组 + 节目名
                Column(modifier = Modifier.weight(1f)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(
                            text = channelName,
                            color = MaterialTheme.colorScheme.onSurface,
                            fontSize = 14.sp,
                            fontWeight = FontWeight.Medium,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis
                        )
                        if (groupName.isNotEmpty()) {
                            Spacer(modifier = Modifier.width(6.dp))
                            Surface(
                                color = MaterialTheme.colorScheme.primary.copy(alpha = 0.12f),
                                shape = RoundedCornerShape(3.dp)
                            ) {
                                Text(
                                    text = groupName,
                                    color = MaterialTheme.colorScheme.primary,
                                    fontSize = 10.sp,
                                    modifier = Modifier.padding(horizontal = 4.dp, vertical = 1.dp),
                                    maxLines = 1
                                )
                            }
                        }
                    }
                    // 当前节目名（无 EPG 时显示「精彩节目」占位）
                    val progTitle = currentProgram?.title?.ifEmpty { null } ?: "精彩节目"
                    Text(
                        text = progTitle,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        fontSize = 11.sp,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                    // 媒体信息标识行
                    if (mediaInfo.isNotEmpty() || videoWidth > 0) {
                        Row(
                            modifier = Modifier.padding(top = 3.dp),
                            horizontalArrangement = Arrangement.spacedBy(4.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            // 视频编码
                            mediaInfo["videoCodec"]?.takeIf { it.isNotEmpty() && it != "null" }?.let { codec ->
                                val cleanCodec = codec.removePrefix("video/").removePrefix("audio/").uppercase()
                                MiniBadge(cleanCodec)
                            }
                            // 分辨率
                            if (videoWidth > 0 && videoHeight > 0) {
                                val resLabel = if (videoHeight >= 2160) "4K"
                                    else if (videoHeight >= 1080) "1080P"
                                    else if (videoHeight >= 720) "720P"
                                    else if (videoHeight >= 480) "480P"
                                    else "${videoHeight}P"
                                MiniBadge(resLabel)
                            }
                            // 音频编码
                            mediaInfo["audioCodec"]?.takeIf { it.isNotEmpty() && it != "null" }?.let { codec ->
                                val cleanCodec = codec.removePrefix("audio/").uppercase()
                                MiniBadge(cleanCodec)
                            }
                            // FPS
                            mediaInfo["fps"]?.takeIf { it.isNotEmpty() && it != "null" && it != "0" && it != "0.000" }?.let { fps ->
                                val fpsVal = fps.toFloatOrNull()
                                MiniBadge(if (fpsVal != null) "${fpsVal.toInt()}fps" else "${fps}fps")
                            }
                        }
                    }
                }
                // 播放/暂停按钮
                IconButton(onClick = onPlayPause, modifier = Modifier.size(36.dp)) {
                    Icon(
                        imageVector = if (isPaused) Icons.Default.PlayArrow else Icons.Default.Pause,
                        contentDescription = if (isPaused) "播放" else "暂停",
                        tint = MaterialTheme.colorScheme.primary,
                        modifier = Modifier.size(22.dp)
                    )
                }
            }
        }
    }
}
/**
 * 迷你播放器条：在所有 Tab 页面顶部显示的简洁播放器条。
 * 点击进入播放器模式，右侧有播放/暂停按钮。
 * 显示频道名 + 当前节目名（无 EPG 时显示「精彩节目」）。
 */
@Composable
internal fun MiniPlayerBar(
    viewModel: AppViewModel,
    channelName: String,
    channelLogo: String,
    groupName: String,
    isPaused: Boolean,
    onClick: () -> Unit,
    onPlayPause: () -> Unit
) {
    val currentIdx by viewModel.currentIdx.collectAsState()
    val epgCacheVersion by viewModel.epgCacheVersion.collectAsState()

    // 获取当前节目
    val currentProgram = remember(currentIdx, epgCacheVersion) {
        if (currentIdx >= 0) viewModel.getCachedCurrentProgram(currentIdx) else null
    }
    val progTitle = currentProgram?.title?.ifEmpty { null } ?: "精彩节目"

    Surface(
        color = MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.5f),
        modifier = Modifier
            .fillMaxWidth()
            .height(48.dp)
            .clickable(onClick = onClick)
    ) {
        Row(
            modifier = Modifier
                .fillMaxSize()
                .padding(horizontal = 12.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            // 播放/暂停按钮
            IconButton(onClick = onPlayPause, modifier = Modifier.size(48.dp)) {
                Icon(
                    imageVector = if (isPaused) Icons.Default.PlayArrow else Icons.Default.Pause,
                    contentDescription = if (isPaused) "播放" else "暂停",
                    tint = MaterialTheme.colorScheme.primary,
                    modifier = Modifier.size(20.dp)
                )
            }
            Spacer(modifier = Modifier.width(8.dp))
            // 频道 logo（带自适应背景色，确保浅色台标在浅色模式下可见）
            if (channelLogo.isNotEmpty()) {
                Box(
                    modifier = Modifier
                        .size(28.dp)
                        .clip(RoundedCornerShape(4.dp))
                        .background(MaterialTheme.colorScheme.surfaceVariant),
                    contentAlignment = Alignment.Center
                ) {
                    AsyncImage(
                        model = channelLogo,
                        contentDescription = null,
                        modifier = Modifier.fillMaxSize().padding(2.dp),
                        contentScale = ContentScale.Fit
                    )
                }
                Spacer(modifier = Modifier.width(8.dp))
            }
            // 频道名 + 节目名
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = channelName,
                    color = MaterialTheme.colorScheme.onSurface,
                    fontSize = 13.sp,
                    fontWeight = FontWeight.Medium,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
                Text(
                    text = progTitle,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    fontSize = 10.sp,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
            }
            // 分组标签
            if (groupName.isNotEmpty()) {
                Surface(
                    color = MaterialTheme.colorScheme.primary.copy(alpha = 0.12f),
                    shape = RoundedCornerShape(3.dp)
                ) {
                    Text(
                        text = groupName,
                        color = MaterialTheme.colorScheme.primary,
                        fontSize = 9.sp,
                        modifier = Modifier.padding(horizontal = 4.dp, vertical = 1.dp),
                        maxLines = 1
                    )
                }
            }
            Spacer(modifier = Modifier.width(4.dp))
            Icon(
                imageVector = Icons.AutoMirrored.Filled.ArrowBack,
                contentDescription = "进入播放器",
                tint = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier
                    .size(18.dp)
                    .rotate(180f)  // 箭头朝右，表示"进入"
            )
        }
    }
}
/** 迷你信息标签 */
@Composable
internal fun MiniBadge(label: String) {
    Surface(
        color = MaterialTheme.colorScheme.primary.copy(alpha = 0.15f),
        shape = RoundedCornerShape(3.dp)
    ) {
        Text(
            text = label,
            color = MaterialTheme.colorScheme.primary,
            fontSize = 9.sp,
            fontWeight = FontWeight.Medium,
            modifier = Modifier.padding(horizontal = 4.dp, vertical = 1.dp),
            maxLines = 1
        )
    }
}
/** 首页频道卡片（水平滚动列表中的单个卡片） */
@Composable
private fun HomeChannelCard(
    channel: IptvChannel,
    oc: PlayerOverlayColors,
    onClick: () -> Unit
) {
    Surface(
        color = MaterialTheme.colorScheme.surfaceVariant,
        shape = RoundedCornerShape(10.dp),
        modifier = Modifier
            .width(120.dp)
            .height(72.dp)
            .clip(RoundedCornerShape(10.dp))
            .clickable(onClick = onClick)
    ) {
        Row(
            modifier = Modifier.fillMaxSize().padding(8.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            if (channel.logo.isNotEmpty()) {
                Box(
                    modifier = Modifier
                        .size(40.dp)
                        .clip(RoundedCornerShape(4.dp))
                        .background(MaterialTheme.colorScheme.surfaceVariant),
                    contentAlignment = Alignment.Center
                ) {
                    AsyncImage(
                        model = channel.logo,
                        contentDescription = channel.name,
                        modifier = Modifier.fillMaxSize().padding(2.dp),
                        contentScale = ContentScale.Fit
                    )
                }
                Spacer(modifier = Modifier.width(8.dp))
            } else {
                Box(
                    modifier = Modifier
                        .size(40.dp)
                        .clip(CircleShape)
                        .background(MaterialTheme.colorScheme.primary.copy(alpha = 0.12f)),
                    contentAlignment = Alignment.Center
                ) {
                    Icon(
                        Icons.Default.PlayArrow,
                        contentDescription = null,
                        tint = MaterialTheme.colorScheme.primary,
                        modifier = Modifier.size(20.dp)
                    )
                }
                Spacer(modifier = Modifier.width(8.dp))
            }
            Text(
                text = channel.name,
                color = MaterialTheme.colorScheme.onSurface,
                fontSize = 12.sp,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
                modifier = Modifier.weight(1f)
            )
        }
    }
}
