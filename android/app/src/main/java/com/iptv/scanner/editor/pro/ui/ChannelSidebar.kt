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
 * 竖屏列表页：APTV风格全屏布局，支持分组底部弹窗、订阅源选择、列表/宫格模式
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
internal fun PortraitListScreen(
    viewModel: AppViewModel,
    playlistLauncher: androidx.activity.result.ActivityResultLauncher<Array<String>>,
    videoLauncher: androidx.activity.result.ActivityResultLauncher<Array<String>>
) {
    val channels by viewModel.channels.collectAsState()
    val currentIdx by viewModel.currentIdx.collectAsState()
    val fileLoaded by viewModel.mpv.fileLoaded.collectAsState()
    val favorites by viewModel.favorites.collectAsState()
    val selectedGroup by viewModel.selectedGroup.collectAsState()
    val listSourceTab by viewModel.listSourceTab.collectAsState()
    val viewMode by viewModel.listViewMode.collectAsState()
    val epgCacheVersion by viewModel.epgCacheVersion.collectAsState()
    val history by viewModel.history.collectAsState()
    val sources by viewModel.sources.collectAsState()
    val selectedSource by viewModel.selectedSource.collectAsState()
    val thumbnailPaths by viewModel.thumbnailPaths.collectAsState()
    val scanResults by viewModel.scanResults.collectAsState()

    // 延迟映射：url -> latency(ms)，优先使用实时测量值，回退到扫描结果
    val liveLatencyMap by viewModel.liveLatencyMap.collectAsState()
    val latencyMap = remember(scanResults, liveLatencyMap) {
        val merged = mutableMapOf<String, Int>()
        scanResults.forEach { if (it.latency > 0) merged[it.url] = it.latency }
        liveLatencyMap.forEach { (url, lat) -> if (lat > 0) merged[url] = lat }
        merged
    }

    val thumbnailEnabled by viewModel.thumbnailEnabled.collectAsState()
    val thumbnailGenProgress by viewModel.thumbnailGenProgress.collectAsState()
    val mediaInfoMap by viewModel.mediaInfoMap.collectAsState()

    // 预加载 EPG 和缩略图
    LaunchedEffect(channels.size) {
        if (channels.isNotEmpty()) {
            viewModel.preloadEpgForAllChannels()
            viewModel.loadThumbnailPaths()
            viewModel.loadScanResultsCache()
            kotlinx.coroutines.delay(3000)
            viewModel.fetchMediaInfoForChannels(channels)
            kotlinx.coroutines.delay(15000)
            viewModel.preloadEpgForAllChannels()
        }
    }

    // 根据数据源 + 订阅源过滤频道
    val filteredChannels = remember(channels, listSourceTab, selectedSource) {
        when (listSourceTab) {
            ListSourceTab.SUBSCRIPTION -> {
                val sub = channels.filter { it.source.isNotEmpty() }
                if (selectedSource.isNotEmpty()) sub.filter { it.source == selectedSource } else sub
            }
            ListSourceTab.LOCAL -> channels.filter { it.source.isEmpty() }
        }
    }

    // 分组（含频道数量，按 M3U 首次出现顺序排列）
    val groupList = remember(filteredChannels) {
        val groupOrder = filteredChannels.map { it.group.ifEmpty { "未分组" } }.distinct()
        val groupCounts = filteredChannels.groupingBy { it.group.ifEmpty { "未分组" } }.eachCount()
        groupOrder.map { it to (groupCounts[it] ?: 0) }
    }

    // 当前分组下的频道
    val displayChannels = remember(filteredChannels, selectedGroup) {
        if (selectedGroup.isEmpty()) filteredChannels
        else filteredChannels.filter { it.group == selectedGroup }
    }


    // 本地文件历史
    val localHistory = remember(history, channels) {
        history.mapNotNull { idx -> channels.getOrNull(idx) }
            .filter { it.source.isEmpty() }
            .take(20)
    }

    // 订阅源名称映射
    val sourceDisplayName = remember(sources, selectedSource) {
        if (selectedSource.isEmpty()) "全部订阅"
        else sources.find { it.url == selectedSource }?.name?.ifEmpty { selectedSource.substringAfterLast("/").take(20) }
            ?: selectedSource.substringAfterLast("/").take(20)
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
    ) {
        // APTV风格顶部栏：分组按钮(左) + 3个功能按钮(右)
        var showGroupSheet by remember { mutableStateOf(false) }
        var showSourceSheet by remember { mutableStateOf(false) }
        var viewMenuExpanded by remember { mutableStateOf(false) }

        Row(
            modifier = Modifier
                .fillMaxWidth()
                .height(44.dp)
                .padding(horizontal = 12.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            // 左侧：分组按钮 → 底部弹窗（带背景的可点击按钮）
            Surface(
                color = MaterialTheme.colorScheme.primary.copy(alpha = 0.15f),
                shape = RoundedCornerShape(20.dp),
                modifier = Modifier.clickable { showGroupSheet = true }
            ) {
                Text(
                    text = if (selectedGroup.isEmpty()) "全部频道" else selectedGroup,
                    color = MaterialTheme.colorScheme.primary,
                    fontSize = 14.sp,
                    fontWeight = FontWeight.Medium,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.padding(horizontal = 16.dp, vertical = 6.dp)
                )
            }

            Spacer(modifier = Modifier.weight(1f))

            // 右侧按钮1：订阅/本地切换
            IconButton(onClick = {
                viewModel.setListSourceTab(
                    if (listSourceTab == ListSourceTab.SUBSCRIPTION) ListSourceTab.LOCAL
                    else ListSourceTab.SUBSCRIPTION
                )
            }) {
                Icon(
                    imageVector = if (listSourceTab == ListSourceTab.SUBSCRIPTION) Icons.Default.Cloud else Icons.Default.Folder,
                    contentDescription = "订阅/本地",
                    tint = MaterialTheme.colorScheme.onBackground
                )
            }

            // 右侧按钮2：订阅源选择（仅订阅模式且多源时）
            if (listSourceTab == ListSourceTab.SUBSCRIPTION && sources.size > 1) {
                IconButton(onClick = { showSourceSheet = true }) {
                    Icon(
                        imageVector = Icons.Default.SwapHoriz,
                        contentDescription = "订阅源",
                        tint = MaterialTheme.colorScheme.onBackground
                    )
                }
            }

            // 右侧按钮3：列表/宫格切换 + 下拉菜单
            Box {
                IconButton(onClick = {
                    viewModel.setListViewMode(
                        if (viewMode == ListViewMode.LIST) ListViewMode.THUMBNAIL
                        else ListViewMode.LIST
                    )
                }) {
                    Icon(
                        imageVector = if (viewMode == ListViewMode.LIST) Icons.Default.ViewList else Icons.Default.GridView,
                        contentDescription = "切换视图",
                        tint = MaterialTheme.colorScheme.onBackground
                    )
                }
                DropdownMenu(
                    expanded = viewMenuExpanded,
                    onDismissRequest = { viewMenuExpanded = false }
                ) {
                    DropdownMenuItem(
                        text = { Text(if (thumbnailGenProgress != null) "停止获取预览图" else "开始获取预览图") },
                        onClick = {
                            viewMenuExpanded = false
                            if (thumbnailGenProgress == null) {
                                viewModel.setThumbnailEnabled(true)
                                viewModel.generateMissingThumbnails(displayChannels)
                            } else {
                                viewModel.setThumbnailEnabled(false)
                            }
                        }
                    )
                    DropdownMenuItem(
                        text = { Text("刷新预览图") },
                        onClick = {
                            viewMenuExpanded = false
                            viewModel.setThumbnailEnabled(true)
                            viewModel.refreshMissingThumbnails()
                        }
                    )
                    DropdownMenuItem(
                        text = { Text("刷新无预览频道") },
                        onClick = {
                            viewMenuExpanded = false
                            viewModel.setThumbnailEnabled(true)
                            viewModel.generateMissingThumbnails(displayChannels)
                        }
                    )
                    DropdownMenuItem(
                        text = { Text("清除预览图") },
                        onClick = {
                            viewMenuExpanded = false
                            viewModel.clearAllThumbnails()
                        }
                    )
                }
            }
            IconButton(onClick = { viewMenuExpanded = true }) {
                Icon(
                    imageVector = Icons.Default.MoreVert,
                    contentDescription = "菜单",
                    tint = MaterialTheme.colorScheme.onBackground
                )
            }

            // 本地模式：清空按钮
            if (listSourceTab == ListSourceTab.LOCAL && filteredChannels.isNotEmpty()) {
                var showClearDialog by remember { mutableStateOf(false) }
                IconButton(onClick = { showClearDialog = true }) {
                    Icon(
                        imageVector = Icons.Default.DeleteSweep,
                        contentDescription = "清空本地列表",
                        tint = MaterialTheme.colorScheme.error
                    )
                }
                if (showClearDialog) {
                    AlertDialog(
                        onDismissRequest = { showClearDialog = false },
                        title = { Text("清空本地列表") },
                        text = { Text("确定要清空所有本地频道吗？此操作不可撤销。") },
                        confirmButton = {
                            TextButton(onClick = {
                                viewModel.clearLocalChannels()
                                showClearDialog = false
                            }) { Text("清空", color = MaterialTheme.colorScheme.error) }
                        },
                        dismissButton = {
                            TextButton(onClick = { showClearDialog = false }) { Text("取消") }
                        }
                    )
                }
            }
        }

        // 缩略图生成进度提示已移除（后台静默执行）

        // 分组选择底部弹窗
        if (showGroupSheet) {
            val sheetState = rememberModalBottomSheetState()
            ModalBottomSheet(
                onDismissRequest = { showGroupSheet = false },
                sheetState = sheetState,
                containerColor = MaterialTheme.colorScheme.surface
            ) {
                LazyColumn(
                    modifier = Modifier.fillMaxWidth().padding(bottom = 24.dp),
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {
                    item {
                        Text(
                            text = "选择分组",
                            fontSize = 16.sp,
                            fontWeight = FontWeight.SemiBold,
                            color = MaterialTheme.colorScheme.onSurface,
                            modifier = Modifier.padding(vertical = 8.dp)
                        )
                    }
                    item {
                        Surface(
                            color = if (selectedGroup.isEmpty()) MaterialTheme.colorScheme.primaryContainer else Color.Transparent,
                            shape = RoundedCornerShape(8.dp),
                            modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 2.dp).clickable {
                                viewModel.setSelectedGroup("")
                                showGroupSheet = false
                            }
                        ) {
                            Row(
                                modifier = Modifier.padding(horizontal = 16.dp, vertical = 12.dp).fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween
                            ) {
                                Text("全部频道", fontSize = 15.sp, color = MaterialTheme.colorScheme.onSurface)
                                Text("${filteredChannels.size}", fontSize = 13.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                        }
                    }
                    items(groupList) { (group, count) ->
                        Surface(
                            color = if (selectedGroup == group) MaterialTheme.colorScheme.primaryContainer else Color.Transparent,
                            shape = RoundedCornerShape(8.dp),
                            modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 2.dp).clickable {
                                viewModel.setSelectedGroup(group)
                                showGroupSheet = false
                            }
                        ) {
                            Row(
                                modifier = Modifier.padding(horizontal = 16.dp, vertical = 12.dp).fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween
                            ) {
                                Text(group, fontSize = 15.sp, color = MaterialTheme.colorScheme.onSurface, maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f))
                                Text("$count", fontSize = 13.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                        }
                    }
                }
            }
        }

        // 订阅源选择底部弹窗
        if (showSourceSheet) {
            val sourceSheetState = rememberModalBottomSheetState()
            val sourceChannelCounts = remember(channels, sources) {
                sources.associate { src ->
                    src.url to channels.count { it.source == src.url }
                }
            }
            ModalBottomSheet(
                onDismissRequest = { showSourceSheet = false },
                sheetState = sourceSheetState,
                containerColor = MaterialTheme.colorScheme.surface
            ) {
                LazyColumn(
                    modifier = Modifier.fillMaxWidth().padding(bottom = 24.dp),
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {
                    item {
                        Text(
                            text = "选择订阅源",
                            fontSize = 16.sp,
                            fontWeight = FontWeight.SemiBold,
                            color = MaterialTheme.colorScheme.onSurface,
                            modifier = Modifier.padding(vertical = 8.dp)
                        )
                    }
                    item {
                        Surface(
                            color = if (selectedSource.isEmpty()) MaterialTheme.colorScheme.primaryContainer else Color.Transparent,
                            shape = RoundedCornerShape(8.dp),
                            modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 2.dp).clickable {
                                viewModel.setSelectedSource("")
                                showSourceSheet = false
                            }
                        ) {
                            Column(modifier = Modifier.padding(horizontal = 16.dp, vertical = 10.dp).fillMaxWidth()) {
                                Text("全部订阅", fontSize = 15.sp, color = MaterialTheme.colorScheme.onSurface)
                                Text("${channels.count { it.source.isNotEmpty() }} 个频道", fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                        }
                    }
                    items(sources) { src ->
                        val name = src.name.ifEmpty { src.url.substringAfterLast("/").take(30) }
                        val count = sourceChannelCounts[src.url] ?: 0
                        Surface(
                            color = if (selectedSource == src.url) MaterialTheme.colorScheme.primaryContainer else Color.Transparent,
                            shape = RoundedCornerShape(8.dp),
                            modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 2.dp).clickable {
                                viewModel.setSelectedSource(src.url)
                                showSourceSheet = false
                            }
                        ) {
                            Column(modifier = Modifier.padding(horizontal = 16.dp, vertical = 10.dp).fillMaxWidth()) {
                                Text(name, fontSize = 15.sp, color = MaterialTheme.colorScheme.onSurface, maxLines = 1, overflow = TextOverflow.Ellipsis)
                                Text("$count 个频道", fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                        }
                    }
                }
            }
        }

        // 本地列表为空时显示快捷入口
        if (listSourceTab == ListSourceTab.LOCAL && filteredChannels.isEmpty()) {
            Column(
                modifier = Modifier.fillMaxSize().padding(16.dp),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                Spacer(modifier = Modifier.height(32.dp))
                if (localHistory.isNotEmpty()) {
                    Text(
                        text = "最近播放",
                        color = MaterialTheme.colorScheme.onBackground,
                        fontSize = 15.sp,
                        fontWeight = FontWeight.SemiBold,
                        modifier = Modifier.fillMaxWidth()
                    )
                    Spacer(modifier = Modifier.height(8.dp))
                    localHistory.forEach { channel ->
                        val idx = channels.indexOfFirst { it.url == channel.url }
                        Surface(
                            color = MaterialTheme.colorScheme.surfaceVariant,
                            shape = RoundedCornerShape(8.dp),
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(vertical = 3.dp)
                                .clickable { if (idx >= 0) viewModel.playChannel(idx) }
                        ) {
                            Row(
                                modifier = Modifier.padding(12.dp),
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Icon(Icons.Default.PlayArrow, contentDescription = null, tint = MaterialTheme.colorScheme.primary, modifier = Modifier.size(24.dp))
                                Spacer(modifier = Modifier.width(10.dp))
                                Text(
                                    text = channel.name,
                                    color = MaterialTheme.colorScheme.onSurface,
                                    fontSize = 14.sp,
                                    maxLines = 1,
                                    overflow = TextOverflow.Ellipsis,
                                    modifier = Modifier.weight(1f)
                                )
                            }
                        }
                    }
                }
                Spacer(modifier = Modifier.height(24.dp))
                Text("暂无本地文件\n点击下方按钮打开本地视频/音乐", color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 14.sp, textAlign = androidx.compose.ui.text.style.TextAlign.Center)
                Spacer(modifier = Modifier.height(8.dp))
                TextButton(onClick = {
                    if (!viewModel.isSafAvailable()) viewModel.showMediaFileBrowser()
                    else videoLauncher.launch(arrayOf("video/*", "audio/*", "application/x-matroska", "application/octet-stream"))
                }) { Text("打开本地文件") }
                Spacer(modifier = Modifier.height(4.dp))
                TextButton(onClick = {
                    if (!viewModel.isSafAvailable()) viewModel.showFileBrowser()
                    else playlistLauncher.launch(arrayOf(
                        "application/x-mpegurl", "application/vnd.apple.mpegurl",
                        "audio/x-mpegurl", "video/x-mpegurl",
                        "text/plain", "application/octet-stream"
                    ))
                }) { Text("导入播放列表") }
            }
            return
        }

        if (displayChannels.isEmpty()) {
            Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Text("暂无频道", color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 14.sp)
            }
            return
        }

        // ---- APTV风格全宽布局（无左右分栏） ----
        Box(modifier = Modifier.fillMaxSize()) {
            if (viewMode == ListViewMode.LIST) {
                ChannelListPanel(
                    displayChannels = displayChannels,
                    channels = channels,
                    currentIdx = currentIdx,
                    fileLoaded = fileLoaded,
                    favorites = favorites,
                        epgCacheVersion = epgCacheVersion,
                        thumbnailPaths = thumbnailPaths,
                        thumbnailEnabled = thumbnailEnabled,
                        viewModel = viewModel,
                        showDelete = listSourceTab == ListSourceTab.LOCAL,
                        onDelete = { idx -> viewModel.deleteChannel(idx) },
                        latencyMap = latencyMap,
                        mediaInfoMap = mediaInfoMap
                    )
                } else {
                    ChannelThumbnailPanel(
                        displayChannels = displayChannels,
                        channels = channels,
                        currentIdx = currentIdx,
                        fileLoaded = fileLoaded,
                        favorites = favorites,
                        thumbnailPaths = thumbnailPaths,
                        thumbnailEnabled = thumbnailEnabled,
                        viewModel = viewModel,
                        showDelete = listSourceTab == ListSourceTab.LOCAL,
                        onDelete = { idx -> viewModel.deleteChannel(idx) },
                        latencyMap = latencyMap,
                        groupList = groupList,
                        mediaInfoMap = mediaInfoMap
                    )
                }
            }

    }
}
/** 右侧频道列表（列表模式） */
@OptIn(ExperimentalFoundationApi::class)
@Composable
private fun ChannelListPanel(
    displayChannels: List<IptvChannel>,
    channels: List<IptvChannel>,
    currentIdx: Int,
    fileLoaded: Boolean = false,
    favorites: Set<Int>,
    epgCacheVersion: Int,
    thumbnailPaths: Map<String, String>,
    thumbnailEnabled: Boolean = false,
    viewModel: AppViewModel,
    showDelete: Boolean = false,
    onDelete: (Int) -> Unit = {},
    latencyMap: Map<String, Int> = emptyMap(),
    mediaInfoMap: Map<String, String> = emptyMap()
) {
    val listState = rememberLazyListState()
    LaunchedEffect(displayChannels, currentIdx) {
        if (currentIdx >= 0) {
            val scrollTarget = displayChannels.indexOfFirst { it == channels.getOrNull(currentIdx) }
            if (scrollTarget >= 0) {
                listState.scrollToItem(scrollTarget)
            }
        }
    }
    LazyColumn(
        state = listState,
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(bottom = 72.dp, top = 4.dp)
    ) {
        items(displayChannels) { channel ->
            val idx = channels.indexOf(channel)
            val isCurrent = fileLoaded && idx == currentIdx
            val isFav = favorites.contains(idx)
            val canCatchup = CatchupHelper.isCatchupEnabled(channel)
            val currentProgram = if (idx >= 0) {
                remember(epgCacheVersion, idx) { viewModel.getCachedCurrentProgram(idx) }
            } else null
            val thumbPath = thumbnailPaths[channel.url]
            val hasThumb = thumbPath != null && File(thumbPath).exists()
            val latency = latencyMap[channel.url]

            Surface(
                color = if (isCurrent) MaterialTheme.colorScheme.primaryContainer
                    else MaterialTheme.colorScheme.surfaceVariant,
                shape = RoundedCornerShape(8.dp),
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 6.dp, vertical = 2.dp)
                    .combinedClickable(
                        onClick = { if (idx >= 0) viewModel.playChannel(idx) },
                        onLongClick = {
                            if (idx >= 0) {
                                viewModel.toggleFavoriteByIndex(idx)
                            }
                        }
                    )
            ) {
                Row(
                    modifier = Modifier.padding(horizontal = 8.dp, vertical = 6.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    // 第一列：预览图或台标（底部覆盖分组）
                    Box(
                        modifier = Modifier
                            .size(72.dp, 40.dp)
                            .clip(RoundedCornerShape(4.dp))
                            .background(Color.Black),
                        contentAlignment = Alignment.Center
                    ) {
                        if (hasThumb) {
                            AsyncImage(
                                model = thumbPath,
                                contentDescription = channel.name,
                                modifier = Modifier.fillMaxSize(),
                                contentScale = ContentScale.Crop
                            )
                        } else if (channel.logo.isNotEmpty()) {
                            AsyncImage(
                                model = channel.logo,
                                contentDescription = channel.name,
                                modifier = Modifier.fillMaxSize().padding(4.dp),
                                contentScale = ContentScale.Fit
                            )
                        } else {
                            Icon(Icons.Default.PlayArrow, contentDescription = null, tint = MaterialTheme.colorScheme.primary.copy(alpha = 0.4f), modifier = Modifier.size(20.dp))
                        }
                        // 底部覆盖分组标识
                        Surface(
                            color = Color.Black.copy(alpha = 0.6f),
                            shape = RoundedCornerShape(2.dp),
                            modifier = Modifier.align(Alignment.BottomCenter).fillMaxWidth()
                        ) {
                            Text(
                                text = channel.group.ifEmpty { "未分组" },
                                color = Color.White,
                                fontSize = 7.sp,
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis,
                                modifier = Modifier.padding(horizontal = 2.dp, vertical = 0.dp)
                            )
                        }
                    }
                    Spacer(modifier = Modifier.width(8.dp))
                    // 第二列：频道名 / 节目名 / 媒体标识
                    Column(modifier = Modifier.weight(1f)) {
                        // 第1行：频道名称 + 延迟
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(
                                text = channel.name,
                                color = if (isCurrent) MaterialTheme.colorScheme.onPrimaryContainer else MaterialTheme.colorScheme.onSurface,
                                fontSize = 14.sp,
                                fontWeight = if (isCurrent) FontWeight.Medium else FontWeight.Normal,
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis,
                                modifier = Modifier.weight(1f)
                            )
                            if (latency != null && latency > 0) {
                                val latColor = when { latency < 200 -> Color(0xFF4CAF50); latency < 500 -> Color(0xFFFFC107); else -> Color(0xFFF44336) }
                                Text("${latency}ms", color = latColor, fontSize = 10.sp, fontWeight = FontWeight.Medium)
                            }
                        }
                        // 第2行：当前节目名称
                        currentProgram?.let { prog ->
                            Text(
                                text = if (prog.title.isNotEmpty()) prog.title else "精彩节目",
                                color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = if (prog.title.isNotEmpty()) 1f else 0.6f),
                                fontSize = 11.sp,
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis
                            )
                        } ?: Text("精彩节目", color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.6f), fontSize = 11.sp, maxLines = 1)
                        // 第3行：媒体标识badge（圆角矩形，与竖屏播放界面一致）
                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                            mediaInfoMap[channel.url]?.split(" ")?.forEach { badge ->
                                if (badge.isNotEmpty()) {
                                    Surface(color = MaterialTheme.colorScheme.primary.copy(alpha = 0.15f), shape = RoundedCornerShape(4.dp)) {
                                        Text(badge, color = MaterialTheme.colorScheme.primary, fontSize = 9.sp, fontWeight = FontWeight.Medium, modifier = Modifier.padding(horizontal = 5.dp, vertical = 1.dp))
                                    }
                                }
                            }
                            if (isFav) {
                                Surface(color = Color(0xFFFFC107).copy(alpha = 0.15f), shape = RoundedCornerShape(4.dp)) {
                                    Text("收藏", color = Color(0xFFFFC107), fontSize = 9.sp, fontWeight = FontWeight.Medium, modifier = Modifier.padding(horizontal = 5.dp, vertical = 1.dp))
                                }
                            }
                        }
                    }
                    // 第三列：回看图标 + 台标
                    if (canCatchup || channel.logo.isNotEmpty()) {
                        Spacer(modifier = Modifier.width(6.dp))
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            if (canCatchup) {
                                Icon(Icons.Default.History, contentDescription = "可回看", tint = MaterialTheme.colorScheme.tertiary, modifier = Modifier.size(16.dp))
                            }
                            if (channel.logo.isNotEmpty()) {
                                if (canCatchup) Spacer(modifier = Modifier.height(2.dp))
                                AsyncImage(
                                    model = channel.logo,
                                    contentDescription = null,
                                    modifier = Modifier.size(22.dp).clip(RoundedCornerShape(2.dp)),
                                    contentScale = ContentScale.Fit
                                )
                            }
                        }
                    }
                    // 删除按钮
                    if (showDelete && idx >= 0) {
                        Spacer(modifier = Modifier.width(4.dp))
                        Icon(Icons.Default.Close, contentDescription = "删除", tint = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.size(18.dp).clickable { onDelete(idx) })
                    }
                }
            }
        }
    }
}
/** 右侧频道列表（缩略图模式） */
@OptIn(ExperimentalFoundationApi::class)
@Composable
private fun ChannelThumbnailPanel(
    displayChannels: List<IptvChannel>,
    channels: List<IptvChannel>,
    currentIdx: Int,
    fileLoaded: Boolean = false,
    favorites: Set<Int>,
    thumbnailPaths: Map<String, String>,
    thumbnailEnabled: Boolean = false,
    viewModel: AppViewModel,
    showDelete: Boolean = false,
    onDelete: (Int) -> Unit = {},
    latencyMap: Map<String, Int> = emptyMap(),
    groupList: List<Pair<String, Int>> = emptyList(),
    mediaInfoMap: Map<String, String> = emptyMap()
) {
    val epgCacheVersion by viewModel.epgCacheVersion.collectAsState()

    LazyVerticalGrid(
        columns = GridCells.Fixed(2),
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(start = 6.dp, top = 4.dp, end = 6.dp, bottom = 80.dp),
        horizontalArrangement = Arrangement.spacedBy(6.dp),
        verticalArrangement = Arrangement.spacedBy(6.dp)
    ) {
        gridItems(displayChannels) { channel ->
            val idx = channels.indexOf(channel)
            val isCurrent = fileLoaded && idx == currentIdx
            val isFav = favorites.contains(idx)
            val canCatchup = CatchupHelper.isCatchupEnabled(channel)
            val thumbPath = thumbnailPaths[channel.url]
            val hasThumb = thumbPath != null && File(thumbPath).exists()
            val latency = latencyMap[channel.url]
            val currentProgram = if (idx >= 0) {
                remember(epgCacheVersion, idx) { viewModel.getCachedCurrentProgram(idx) }
            } else null
            val channelGroup = channel.group.ifEmpty { "未分组" }

            Surface(
                color = if (isCurrent) MaterialTheme.colorScheme.primaryContainer
                    else MaterialTheme.colorScheme.surfaceVariant,
                shape = RoundedCornerShape(10.dp),
                modifier = Modifier.combinedClickable(
                    onClick = { if (idx >= 0) viewModel.playChannel(idx) },
                    onLongClick = {
                        if (idx >= 0) {
                            viewModel.toggleFavoriteByIndex(idx)
                        }
                    }
                )
            ) {
                Column(modifier = Modifier.fillMaxWidth()) {
                    // 预览图/台标区域（16:9）
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .aspectRatio(16f / 9f)
                            .background(Color.Black)
                    ) {
                        if (hasThumb) {
                            AsyncImage(
                                model = thumbPath,
                                contentDescription = channel.name,
                                modifier = Modifier.fillMaxSize(),
                                contentScale = ContentScale.Crop
                            )
                        } else if (channel.logo.isNotEmpty()) {
                            AsyncImage(
                                model = channel.logo,
                                contentDescription = channel.name,
                                modifier = Modifier.fillMaxSize().padding(12.dp),
                                contentScale = ContentScale.Fit
                            )
                        } else {
                            Box(
                                modifier = Modifier.fillMaxSize(),
                                contentAlignment = Alignment.Center
                            ) {
                                Icon(Icons.Default.PlayArrow, contentDescription = null, tint = MaterialTheme.colorScheme.primary.copy(alpha = 0.3f), modifier = Modifier.size(28.dp))
                            }
                        }
                        // 右下角分组标识
                        Surface(
                            color = Color.Black.copy(alpha = 0.6f),
                            shape = RoundedCornerShape(4.dp),
                            modifier = Modifier.align(Alignment.BottomEnd).padding(4.dp)
                        ) {
                            Text(
                                text = channelGroup,
                                color = Color.White,
                                fontSize = 8.sp,
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis,
                                modifier = Modifier.padding(horizontal = 4.dp, vertical = 1.dp)
                            )
                        }
                        // 左下角延迟标识
                        if (latency != null && latency > 0) {
                            val latColor = when { latency < 200 -> Color(0xFF4CAF50); latency < 500 -> Color(0xFFFFC107); else -> Color(0xFFF44336) }
                            Surface(
                                color = Color.Black.copy(alpha = 0.6f),
                                shape = RoundedCornerShape(4.dp),
                                modifier = Modifier.align(Alignment.BottomStart).padding(4.dp)
                            ) {
                                Text("${latency}ms", color = latColor, fontSize = 8.sp, fontWeight = FontWeight.Medium, modifier = Modifier.padding(horizontal = 4.dp, vertical = 1.dp))
                            }
                        }
                        // 右上角：播放中
                        if (isCurrent) {
                            Surface(
                                color = MaterialTheme.colorScheme.primary,
                                shape = RoundedCornerShape(4.dp),
                                modifier = Modifier.align(Alignment.TopEnd).padding(3.dp)
                            ) {
                                Text("播放中", color = MaterialTheme.colorScheme.onPrimary, fontSize = 8.sp, fontWeight = FontWeight.Bold, modifier = Modifier.padding(horizontal = 4.dp, vertical = 1.dp))
                            }
                        }
                        // 删除按钮
                        if (showDelete && idx >= 0) {
                            Box(
                                modifier = Modifier.align(Alignment.TopStart).padding(4.dp).clip(CircleShape).background(Color.Black.copy(alpha = 0.6f)).clickable { onDelete(idx) }.padding(4.dp)
                            ) {
                                Icon(Icons.Default.Close, contentDescription = "删除", tint = Color.White, modifier = Modifier.size(14.dp))
                            }
                        }
                    }
                    // 下方紧凑信息区
                    Column(
                        modifier = Modifier.fillMaxWidth().padding(horizontal = 6.dp, vertical = 2.dp)
                    ) {
                        // 第1行：频道名称
                        Text(
                            text = channel.name,
                            color = if (isCurrent) MaterialTheme.colorScheme.onPrimaryContainer else MaterialTheme.colorScheme.onSurface,
                            fontSize = 12.sp,
                            fontWeight = if (isCurrent) FontWeight.Medium else FontWeight.Normal,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis
                        )
                        // 第2行：当前节目名称
                        currentProgram?.let { prog ->
                            Text(
                                text = if (prog.title.isNotEmpty()) prog.title else "精彩节目",
                                color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = if (prog.title.isNotEmpty()) 1f else 0.6f),
                                fontSize = 10.sp,
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis
                            )
                        }
                        // 第3行：媒体标识badge（圆角矩形，与列表/竖屏一致）
                        val badges = mutableListOf<String>()
                        mediaInfoMap[channel.url]?.split(" ")?.forEach { if (it.isNotEmpty()) badges.add(it) }
                        if (canCatchup) badges.add("回看")
                        if (isFav) badges.add("收藏")
                        if (badges.isNotEmpty()) {
                            Row(horizontalArrangement = Arrangement.spacedBy(3.dp)) {
                                badges.forEach { badge ->
                                    Surface(color = MaterialTheme.colorScheme.primary.copy(alpha = 0.15f), shape = RoundedCornerShape(4.dp)) {
                                        Text(badge, color = MaterialTheme.colorScheme.primary, fontSize = 8.sp, fontWeight = FontWeight.Medium, maxLines = 1, modifier = Modifier.padding(horizontal = 4.dp, vertical = 0.dp))
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
/**
 * 竖屏频道列表项
 * 台标 + 频道名(+回看标识) + 当前节目名 + 节目单按钮
 */
@Composable
internal fun PortraitChannelListItem(
    channel: IptvChannel,
    channelIdx: Int,
    isPlaying: Boolean,
    oc: PlayerOverlayColors,
    viewModel: AppViewModel,
    epgCacheVersion: Int,
    onPlay: () -> Unit,
    onEpg: () -> Unit
) {
    // 获取缓存的当前节目
    var currentProgram by remember { mutableStateOf<com.iptv.scanner.editor.pro.data.IptvEpgProgram?>(null) }
    LaunchedEffect(channelIdx, epgCacheVersion) {
        currentProgram = viewModel.getCachedCurrentProgram(channelIdx)
        while (true) {
            delay(5_000L)
            currentProgram = viewModel.getCachedCurrentProgram(channelIdx)
        }
    }

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 4.dp, vertical = 2.dp)
            .then(if (isPlaying) Modifier.border(1.dp, oc.accent.copy(alpha = 0.40f), RoundedCornerShape(8.dp)) else Modifier)
            .clickable(onClick = onPlay)
            .padding(horizontal = 8.dp, vertical = 4.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        // 台标
        if (channel.logo.isNotEmpty()) {
            AsyncImage(
                model = channel.logo,
                contentDescription = channel.name,
                modifier = Modifier
                    .size(36.dp)
                    .clip(RoundedCornerShape(4.dp)),
                contentScale = ContentScale.Fit
            )
            Spacer(modifier = Modifier.width(8.dp))
        } else {
            // 无台标占位
            Box(
                modifier = Modifier
                    .size(36.dp)
                    .clip(RoundedCornerShape(4.dp))
                    .background(oc.badgeBg),
                contentAlignment = Alignment.Center
            ) {
                Text(
                    text = channel.name.take(1),
                    color = oc.textSecondary,
                    fontSize = 14.sp
                )
            }
            Spacer(modifier = Modifier.width(8.dp))
        }

        // 频道名 + 节目名
        Column(modifier = Modifier.weight(1f)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    text = channel.name,
                    color = if (isPlaying) oc.accent else oc.textPrimary,
                    fontSize = 14.sp,
                    fontWeight = if (isPlaying) FontWeight.Medium else FontWeight.Normal,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
            }
            // 当前节目名
            if (currentProgram != null && currentProgram!!.title.isNotEmpty()) {
                Text(
                    text = currentProgram!!.title,
                    color = oc.textSecondary,
                    fontSize = 11.sp,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
            } else {
                Text(
                    text = "精彩节目",
                    color = oc.textSecondary,
                    fontSize = 11.sp,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
            }
        }

        // 回看标识（居右，节目单按钮左边）
        if (channel.catchup.isNotEmpty() && channel.catchup != "none") {
            Surface(
                color = oc.accent.copy(alpha = 0.15f),
                shape = RoundedCornerShape(3.dp)
            ) {
                Text(
                    text = "回看",
                    color = oc.accent,
                    fontSize = 9.sp,
                    modifier = Modifier.padding(horizontal = 4.dp, vertical = 1.dp)
                )
            }
            Spacer(modifier = Modifier.width(2.dp))
        }

        // 节目单按钮
        IconButton(
            onClick = onEpg,
            modifier = Modifier.size(48.dp)
        ) {
            Icon(
                Icons.Default.CalendarMonth,
                    contentDescription = stringResource(R.string.cd_program_guide),
                tint = oc.iconTint,
                modifier = Modifier.size(18.dp)
            )
        }
    }
}
