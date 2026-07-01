package com.iptv.scanner.editor.pro.ui

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
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
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ExitToApp
import androidx.compose.material.icons.automirrored.filled.ListAlt
import androidx.compose.material.icons.filled.CalendarMonth
import androidx.compose.material.icons.filled.ClosedCaption
import androidx.compose.material.icons.filled.Equalizer
import androidx.compose.material.icons.filled.Favorite
import androidx.compose.material.icons.filled.FileOpen
import androidx.compose.material.icons.filled.GraphicEq
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.Link
import androidx.compose.material.icons.filled.Menu
import androidx.compose.material.icons.filled.Movie
import androidx.compose.material.icons.filled.PlayCircle
import androidx.compose.material.icons.filled.Public
import androidx.compose.material.icons.filled.ScreenshotMonitor
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.SyncAlt
import androidx.compose.material.icons.filled.Tune
import androidx.compose.material.icons.filled.VideoLibrary
import androidx.compose.material.icons.filled.VideoSettings
import androidx.compose.material.icons.filled.Web
import androidx.compose.material.icons.filled.ViewInAr
import androidx.compose.material3.Divider
import androidx.compose.material3.Icon
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
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
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.iptv.scanner.editor.pro.data.IptvChannel
import com.iptv.scanner.editor.pro.data.IptvEpgProgram
import com.iptv.scanner.editor.pro.ui.theme.tvFocusBorder
import java.util.Locale

/**
 * TV 端统一面板：三列布局（模式切换 + 主内容 + EPG 节目单）。
 *
 * 设计目的：
 * - 解决 TV 端遥控器上下键被切频道占用、无法快速打开列表的问题
 * - MENU 键打开统一面板，默认焦点在频道列表，快速切换频道
 *
 * 三列布局：
 * - 第一列（72dp）：模式切换图标（频道列表 / 主菜单），垂直排列
 * - 第二列（360dp）：频道列表 或 主菜单项（根据第一列选中图标）
 * - 第三列（剩余空间）：当前频道的节目单 + 选中节目描述（仅频道列表模式）
 *
 * 焦点导航：
 * - 默认焦点在第二列（频道列表）
 * - DPAD LEFT/RIGHT：在列之间切换焦点（Compose 焦点系统自动处理）
 * - DPAD UP/DOWN：在当前列内导航
 * - BACK：关闭面板
 * - CENTER/ENTER：确认（播放频道 / 打开菜单项 / 选择节目）
 *
 * 与内存规则对齐：
 * - TV remote DPAD navigation: when any panel is open, direction keys + CENTER/ENTER are handled by Compose focus system
 */
@Composable
fun TvUnifiedPanel(viewModel: AppViewModel) {
    val currentChannel by viewModel.currentChannel.collectAsState()
    val currentIdx by viewModel.currentIdx.collectAsState()
    val channels by viewModel.channels.collectAsState()
    val searchQuery by viewModel.searchQuery.collectAsState()
    val favorites by viewModel.favorites.collectAsState()
    val isFavorite = currentIdx >= 0 && favorites.contains(currentIdx)

    // EPG 数据
    val epg by viewModel.currentEpg.collectAsState()
    val epgLoading by viewModel.epgLoading.collectAsState()

    // 统一面板状态
    var unifiedMode by remember { mutableStateOf(UnifiedMode.CHANNELS) }
    var selectedProgram by remember { mutableStateOf<IptvEpgProgram?>(null) }

    // 焦点管理：初始焦点在第二列（频道列表）
    val column2Focus = remember { FocusRequester() }
    LaunchedEffect(Unit) {
        kotlin.runCatching { column2Focus.requestFocus() }
    }

    // 频道切换时刷新 EPG 并清空选中节目
    LaunchedEffect(currentIdx) {
        selectedProgram = null
        viewModel.fetchEpgForCurrent()
    }

    // 文件选择器（主菜单模式使用）
    val playlistLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.OpenDocument()
    ) { uri: Uri? ->
        if (uri != null) viewModel.importPlaylist(uri)
    }
    val videoLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.OpenDocument()
    ) { uri: Uri? ->
        if (uri != null) viewModel.playLocalVideo(uri.toString())
    }

    /** 关闭统一面板后执行操作 */
    fun closeAndRun(action: () -> Unit) {
        viewModel.toggleTvUnifiedPanel()
        action()
    }

    Surface(
        color = Color(0xE6000000),
        modifier = Modifier.fillMaxSize()
    ) {
        Row(modifier = Modifier.fillMaxSize()) {
            // -----------------------------------------------------------------
            // 第一列：模式切换图标
            // -----------------------------------------------------------------
            ModeColumn(
                mode = unifiedMode,
                onModeChange = { newMode ->
                    unifiedMode = newMode
                    selectedProgram = null
                },
                modifier = Modifier.width(72.dp)
            )

            // -----------------------------------------------------------------
            // 第二列：主内容（频道列表 或 主菜单）
            // -----------------------------------------------------------------
            when (unifiedMode) {
                UnifiedMode.CHANNELS -> ChannelsColumn(
                    viewModel = viewModel,
                    channels = channels,
                    currentIdx = currentIdx,
                    favorites = favorites,
                    searchQuery = searchQuery,
                    onSearchQueryChange = { viewModel.setSearchQuery(it) },
                    onChannelClick = { idx -> viewModel.playChannel(idx) },
                    modifier = Modifier.width(360.dp).focusRequester(column2Focus)
                )
                UnifiedMode.MENU -> MenuColumn(
                    viewModel = viewModel,
                    currentIdx = currentIdx,
                    isFavorite = isFavorite,
                    onOpenPlaylist = {
                        closeAndRun {
                            playlistLauncher.launch(arrayOf(
                                "application/x-mpegurl", "application/vnd.apple.mpegurl",
                                "audio/x-mpegurl", "video/x-mpegurl",
                                "text/plain", "application/octet-stream"
                            ))
                        }
                    },
                    onOpenUrl = { closeAndRun { viewModel.toggleOpenUrlDialog() } },
                    onOpenLocalVideo = {
                        closeAndRun {
                            videoLauncher.launch(arrayOf("video/*", "application/x-matroska", "application/octet-stream"))
                        }
                    },
                    onSources = {
                        closeAndRun {
                            viewModel.setSourceTab(AppViewModel.SourceTab.PLAYLIST)
                            viewModel.toggleSourceManager()
                        }
                    },
                    onEpgSources = {
                        closeAndRun {
                            viewModel.setSourceTab(AppViewModel.SourceTab.EPG)
                            viewModel.toggleSourceManager()
                        }
                    },
                    onMapping = { closeAndRun { viewModel.toggleMappingPanel() } },
                    onChannels = { closeAndRun { viewModel.showChannelsPanel() } },
                    onEpg = { closeAndRun { viewModel.showEpgPanel() } },
                    onSubtitle = { closeAndRun { viewModel.toggleSubtitleSettings() } },
                    onVideo = { closeAndRun { viewModel.toggleVideoSettings() } },
                    onAudio = { closeAndRun { viewModel.toggleAudioSettings() } },
                    onPlayback = { closeAndRun { viewModel.togglePlaybackPanel() } },
                    onScreenshot = { closeAndRun { viewModel.toggleScreenshotPanel() } },
                    onAvsync = { closeAndRun { viewModel.toggleAvSyncPanel() } },
                    onNetwork = { closeAndRun { viewModel.toggleNetworkPanel() } },
                    onTools = { closeAndRun { viewModel.toggleToolsPanel() } },
                    onView = { closeAndRun { viewModel.toggleViewSettings() } },
                    onSettings = { closeAndRun { viewModel.togglePlayerSettings() } },
                    onAbout = { closeAndRun { viewModel.toggleAboutPanel() } },
                    onToggleFavorite = { viewModel.toggleFavorite() },
                    onQuit = { viewModel.showOsd("退出", "请使用系统返回键退出") },
                    modifier = Modifier.width(360.dp).focusRequester(column2Focus)
                )
            }

            // -----------------------------------------------------------------
            // 第三列：EPG 节目单 + 描述（仅频道列表模式显示）
            // -----------------------------------------------------------------
            if (unifiedMode == UnifiedMode.CHANNELS && currentChannel != null) {
                EpgColumn(
                    channel = currentChannel!!,
                    epg = epg,
                    loading = epgLoading,
                    currentIdx = currentIdx,
                    selectedProgram = selectedProgram,
                    onProgramSelect = { program -> selectedProgram = program },
                    onProgramClick = { program ->
                        val now = System.currentTimeMillis()
                        val isPast = program.stopTs * 1000L < now
                        if (isPast) {
                            // 过去节目：触发回看
                            closeAndRun { viewModel.startCatchup(program) }
                        } else {
                            // 当前/未来节目：设置提醒
                            viewModel.toggleReminder(program, currentChannel)
                        }
                    },
                    isReminderSet = { program -> viewModel.isReminderSet(program) },
                    modifier = Modifier.weight(1f)
                )
            } else {
                // 主菜单模式或无频道：第三列占位
                Spacer(modifier = Modifier.weight(1f))
            }
        }
    }
}

// =====================================================================
// 模式枚举
// =====================================================================

enum class UnifiedMode { CHANNELS, MENU }

// =====================================================================
// 第一列：模式切换图标
// =====================================================================

@Composable
private fun ModeColumn(
    mode: UnifiedMode,
    onModeChange: (UnifiedMode) -> Unit,
    modifier: Modifier = Modifier
) {
    Surface(
        color = Color(0xFF1A1A1A),
        modifier = modifier.fillMaxHeight()
    ) {
        Column(
            modifier = Modifier.fillMaxHeight().padding(vertical = 16.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(12.dp, Alignment.CenterVertically)
        ) {
            ModeIconButton(
                icon = Icons.AutoMirrored.Filled.ListAlt,
                label = "频道",
                isSelected = mode == UnifiedMode.CHANNELS,
                onClick = { onModeChange(UnifiedMode.CHANNELS) }
            )
            ModeIconButton(
                icon = Icons.Default.Menu,
                label = "菜单",
                isSelected = mode == UnifiedMode.MENU,
                onClick = { onModeChange(UnifiedMode.MENU) }
            )
        }
    }
}

@Composable
private fun ModeIconButton(
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    label: String,
    isSelected: Boolean,
    onClick: () -> Unit
) {
    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        modifier = Modifier
            .clip(RoundedCornerShape(8.dp))
            .background(if (isSelected) Color(0xFF2A4A6A) else Color.Transparent)
            .clickable { onClick() }
            .tvFocusBorder()
            .padding(horizontal = 8.dp, vertical = 10.dp)
    ) {
        Icon(
            imageVector = icon,
            contentDescription = label,
            tint = if (isSelected) Color(0xFF4A9EFF) else Color(0xFF888888),
            modifier = Modifier.size(28.dp)
        )
        Spacer(modifier = Modifier.height(4.dp))
        Text(
            text = label,
            color = if (isSelected) Color(0xFF4A9EFF) else Color(0xFF888888),
            fontSize = 10.sp
        )
    }
}

// =====================================================================
// 第二列：频道列表
// =====================================================================

@Composable
private fun ChannelsColumn(
    viewModel: AppViewModel,
    channels: List<IptvChannel>,
    currentIdx: Int,
    favorites: Set<Int>,
    searchQuery: String,
    onSearchQueryChange: (String) -> Unit,
    onChannelClick: (Int) -> Unit,
    modifier: Modifier = Modifier
) {
    val filteredChannels = remember(searchQuery, channels) {
        val query = searchQuery.lowercase()
        if (query.isEmpty()) {
            channels.mapIndexed { idx, c -> c to idx }
        } else {
            channels.mapIndexed { idx, c -> c to idx }
                .filter { (c, _) ->
                    c.name.lowercase().contains(query) || c.group.lowercase().contains(query)
                }
        }
    }

    Surface(
        color = Color(0xF0161616),
        modifier = modifier.fillMaxHeight()
    ) {
        Column(modifier = Modifier.fillMaxSize()) {
            // 标题
            Text(
                text = "频道列表",
                color = Color.White,
                fontSize = 14.sp,
                fontWeight = FontWeight.SemiBold,
                modifier = Modifier.padding(horizontal = 12.dp, vertical = 10.dp)
            )

            // 搜索框
            OutlinedTextField(
                value = searchQuery,
                onValueChange = onSearchQueryChange,
                placeholder = { Text("搜索频道...", color = Color(0xFF888888), fontSize = 13.sp) },
                leadingIcon = { Icon(Icons.Default.Search, contentDescription = null, tint = Color(0xFF888888)) },
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 12.dp, vertical = 4.dp),
                shape = RoundedCornerShape(8.dp),
                singleLine = true
            )

            Divider(color = Color(0xFF2A2A2A))

            // 频道列表
            if (filteredChannels.isEmpty()) {
                Box(
                    modifier = Modifier.fillMaxSize(),
                    contentAlignment = Alignment.Center
                ) {
                    Text(
                        text = if (channels.isEmpty()) "暂无频道\n请通过菜单添加订阅源" else "未找到匹配频道",
                        color = Color(0xFF888888),
                        fontSize = 13.sp,
                        lineHeight = 20.sp,
                        textAlign = androidx.compose.ui.text.style.TextAlign.Center
                    )
                }
            } else {
                LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = androidx.compose.foundation.layout.PaddingValues(vertical = 4.dp)
                ) {
                    items(
                        items = filteredChannels,
                        key = { (channel, idx) -> idx }
                    ) { (channel, idx) ->
                        TvChannelItem(
                            channel = channel,
                            isPlaying = idx == currentIdx,
                            isFavorite = favorites.contains(idx),
                            onClick = { onChannelClick(idx) }
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun TvChannelItem(
    channel: IptvChannel,
    isPlaying: Boolean,
    isFavorite: Boolean,
    onClick: () -> Unit
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable { onClick() }
            .tvFocusBorder()
            .padding(horizontal = 12.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        // 圆点
        Box(
            modifier = Modifier
                .size(8.dp)
                .clip(CircleShape)
                .background(if (isPlaying) Color(0xFF4A9EFF) else Color(0xFF444444))
        )
        Spacer(modifier = Modifier.width(10.dp))
        // 频道名 + 分组
        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = channel.name,
                color = if (isPlaying) Color(0xFF6A9EFF) else Color.White,
                fontSize = 14.sp,
                fontWeight = if (isPlaying) FontWeight.Medium else FontWeight.Normal,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis
            )
            if (channel.group.isNotEmpty()) {
                Text(
                    text = channel.group,
                    color = Color(0xFF888888),
                    fontSize = 11.sp,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
            }
        }
        // 收藏星标
        if (isFavorite) {
            Icon(
                imageVector = Icons.Default.Favorite,
                contentDescription = "收藏",
                tint = Color(0xFFFFD700),
                modifier = Modifier.size(14.dp)
            )
        }
    }
}

// =====================================================================
// 第二列：主菜单
// =====================================================================

@Composable
private fun MenuColumn(
    viewModel: AppViewModel,
    currentIdx: Int,
    isFavorite: Boolean,
    onOpenPlaylist: () -> Unit,
    onOpenUrl: () -> Unit,
    onOpenLocalVideo: () -> Unit,
    onSources: () -> Unit,
    onEpgSources: () -> Unit,
    onMapping: () -> Unit,
    onChannels: () -> Unit,
    onEpg: () -> Unit,
    onSubtitle: () -> Unit,
    onVideo: () -> Unit,
    onAudio: () -> Unit,
    onPlayback: () -> Unit,
    onScreenshot: () -> Unit,
    onAvsync: () -> Unit,
    onNetwork: () -> Unit,
    onTools: () -> Unit,
    onView: () -> Unit,
    onSettings: () -> Unit,
    onAbout: () -> Unit,
    onToggleFavorite: () -> Unit,
    onQuit: () -> Unit,
    modifier: Modifier = Modifier
) {
    val hasCurrentChannel = currentIdx >= 0

    val menuItems = remember(hasCurrentChannel, isFavorite) {
        listOf(
            // 快捷分组
            TvMenuItem("频道列表", "订阅 / 本地 / 收藏 / 历史 / 队列", Icons.AutoMirrored.Filled.ListAlt, onChannels, highlight = true),
            TvMenuItem("节目单 EPG", "当前频道节目 / 日期切换 / 提醒", Icons.Default.CalendarMonth, onEpg, highlight = true),
            // 文件分组
            TvMenuItem("打开播放列表", "选择 M3U/M3U8 文件", Icons.Default.FileOpen, onOpenPlaylist),
            TvMenuItem("打开网络流", "输入订阅源 URL", Icons.Default.Link, onOpenUrl),
            TvMenuItem("打开本地视频", "播放设备视频文件", Icons.Default.Movie, onOpenLocalVideo),
            TvMenuItem("订阅源管理", "添加 / 编辑 / 删除 M3U", Icons.Default.Web, onSources),
            TvMenuItem("EPG 订阅源", "管理节目单订阅地址", Icons.Default.CalendarMonth, onEpgSources),
            TvMenuItem("频道映射", "远程 + 用户映射管理", Icons.Default.SyncAlt, onMapping),
            // 播放分组
            TvMenuItem("字幕", "轨 / 显示 / 延迟 / 样式", Icons.Default.ClosedCaption, onSubtitle),
            TvMenuItem("视频", "图像 / 旋转 / 翻转 / 3D", Icons.Default.VideoSettings, onVideo),
            TvMenuItem("音频", "音轨 / 延迟 / EQ / 音调", Icons.Default.Equalizer, onAudio),
            TvMenuItem("播放", "速度 / 循环 / 随机 / AB", Icons.Default.PlayCircle, onPlayback),
            TvMenuItem("截图", "单张 / 连拍 / 含字幕", Icons.Default.ScreenshotMonitor, onScreenshot),
            TvMenuItem("A/V 同步", "数值 / 波形 / 延迟", Icons.Default.GraphicEq, onAvsync),
            TvMenuItem("网络增强", "Referer / Proxy / Headers", Icons.Default.Public, onNetwork),
            TvMenuItem("工具", "搜索 / 时间线 / 提醒 / 扫描", Icons.Default.Tune, onTools),
            TvMenuItem("视图", "视频比例 / OSD", Icons.Default.ViewInAr, onView),
            TvMenuItem("设置", "内核 / VO / HWDEC / HDR", Icons.Default.Settings, onSettings),
            TvMenuItem("关于", "版本 / 功能特性", Icons.Default.Info, onAbout),
            TvMenuItem(
                if (isFavorite) "取消收藏" else "收藏",
                if (hasCurrentChannel) "当前频道" else "未选择频道",
                Icons.Default.Favorite,
                onToggleFavorite,
                highlight = hasCurrentChannel
            ),
            TvMenuItem("退出", "关闭应用", Icons.AutoMirrored.Filled.ExitToApp, onQuit)
        )
    }

    Surface(
        color = Color(0xF0161616),
        modifier = modifier.fillMaxHeight()
    ) {
        Column(modifier = Modifier.fillMaxSize()) {
            Text(
                text = "主菜单",
                color = Color.White,
                fontSize = 14.sp,
                fontWeight = FontWeight.SemiBold,
                modifier = Modifier.padding(horizontal = 12.dp, vertical = 10.dp)
            )
            Divider(color = Color(0xFF2A2A2A))

            LazyColumn(
                modifier = Modifier.fillMaxSize(),
                contentPadding = androidx.compose.foundation.layout.PaddingValues(vertical = 4.dp)
            ) {
                items(
                    items = menuItems,
                    key = { it.title }
                ) { item ->
                    TvMenuItemRow(item)
                }
            }
        }
    }
}

private data class TvMenuItem(
    val title: String,
    val subtitle: String,
    val icon: androidx.compose.ui.graphics.vector.ImageVector,
    val onClick: () -> Unit,
    val highlight: Boolean = false
)

@Composable
private fun TvMenuItemRow(item: TvMenuItem) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable { item.onClick() }
            .tvFocusBorder()
            .padding(horizontal = 12.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Icon(
            imageVector = item.icon,
            contentDescription = null,
            tint = if (item.highlight) Color(0xFF4A9EFF) else Color(0xFFCCCCCC),
            modifier = Modifier.size(20.dp)
        )
        Spacer(modifier = Modifier.width(10.dp))
        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = item.title,
                color = if (item.highlight) Color(0xFF6A9EFF) else Color.White,
                fontSize = 14.sp,
                fontWeight = if (item.highlight) FontWeight.Medium else FontWeight.Normal,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis
            )
            Text(
                text = item.subtitle,
                color = Color(0xFF888888),
                fontSize = 11.sp,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis
            )
        }
    }
}

// =====================================================================
// 第三列：EPG 节目单 + 描述
// =====================================================================

@Composable
private fun EpgColumn(
    channel: IptvChannel,
    epg: List<IptvEpgProgram>,
    loading: Boolean,
    currentIdx: Int,
    selectedProgram: IptvEpgProgram?,
    onProgramSelect: (IptvEpgProgram) -> Unit,
    onProgramClick: (IptvEpgProgram) -> Unit,
    isReminderSet: (IptvEpgProgram) -> Boolean,
    modifier: Modifier = Modifier
) {
    val listState = rememberLazyListState()
    val now = System.currentTimeMillis()

    // 自动滚动到当前节目
    LaunchedEffect(epg, channel) {
        if (epg.isNotEmpty()) {
            val currentProgIdx = epg.indexOfFirst { p ->
                p.startTs * 1000L <= now && now <= p.stopTs * 1000L
            }
            val targetIdx = if (currentProgIdx >= 0) currentProgIdx else 0
            if (targetIdx < epg.size) {
                listState.animateScrollToItem(targetIdx)
            }
        }
    }

    Surface(
        color = Color(0xF0161616),
        modifier = modifier.fillMaxHeight()
    ) {
        Column(modifier = Modifier.fillMaxSize()) {
            // 标题
            Row(
                modifier = Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 10.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Icon(
                    imageVector = Icons.Default.VideoLibrary,
                    contentDescription = null,
                    tint = Color(0xFF4A9EFF),
                    modifier = Modifier.size(18.dp)
                )
                Spacer(modifier = Modifier.width(8.dp))
                Text(
                    text = "节目单",
                    color = Color.White,
                    fontSize = 14.sp,
                    fontWeight = FontWeight.SemiBold
                )
                Spacer(modifier = Modifier.width(8.dp))
                Text(
                    text = channel.name,
                    color = Color(0xFF888888),
                    fontSize = 12.sp,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.weight(1f)
                )
            }

            Divider(color = Color(0xFF2A2A2A))

            when {
                loading -> {
                    Box(
                        modifier = Modifier.fillMaxSize(),
                        contentAlignment = Alignment.Center
                    ) {
                        Text("加载节目单...", color = Color(0xFF888888), fontSize = 13.sp)
                    }
                }
                epg.isEmpty() -> {
                    Box(
                        modifier = Modifier.fillMaxSize(),
                        contentAlignment = Alignment.Center
                    ) {
                        Text("暂无节目单数据", color = Color(0xFF888888), fontSize = 13.sp)
                    }
                }
                else -> {
                    // 上半部分：节目列表（占 60%）
                    LazyColumn(
                        state = listState,
                        modifier = Modifier.weight(0.6f),
                        contentPadding = androidx.compose.foundation.layout.PaddingValues(vertical = 4.dp)
                    ) {
                        items(
                            items = epg,
                            key = { it.start + it.title }
                        ) { program ->
                            TvEpgItem(
                                program = program,
                                isCurrent = program.startTs * 1000L <= now && now <= program.stopTs * 1000L,
                                isPast = program.stopTs * 1000L < now,
                                isSelected = selectedProgram == program,
                                hasReminder = isReminderSet(program),
                                onClick = { onProgramClick(program) },
                                onSelect = { onProgramSelect(program) }
                            )
                        }
                    }

                    Divider(color = Color(0xFF2A2A2A))

                    // 下半部分：选中节目的描述（占 40%）
                    Box(
                        modifier = Modifier.weight(0.4f).fillMaxWidth().padding(12.dp)
                    ) {
                        val prog = selectedProgram
                        if (prog != null) {
                            Column {
                                Text(
                                    text = prog.title,
                                    color = Color.White,
                                    fontSize = 15.sp,
                                    fontWeight = FontWeight.Medium,
                                    maxLines = 2,
                                    overflow = TextOverflow.Ellipsis
                                )
                                Spacer(modifier = Modifier.height(4.dp))
                                Text(
                                    text = "${formatTime(prog.start)} - ${formatTime(prog.stop)}",
                                    color = Color(0xFF4A9EFF),
                                    fontSize = 12.sp
                                )
                                Spacer(modifier = Modifier.height(8.dp))
                                Text(
                                    text = prog.desc.ifEmpty { "暂无节目描述" },
                                    color = Color(0xFFCCCCCC),
                                    fontSize = 12.sp,
                                    lineHeight = 18.sp
                                )
                            }
                        } else {
                            Text(
                                text = "选择节目查看详情\n（按确认键可回看或设置提醒）",
                                color = Color(0xFF666666),
                                fontSize = 12.sp,
                                lineHeight = 18.sp
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun TvEpgItem(
    program: IptvEpgProgram,
    isCurrent: Boolean,
    isPast: Boolean,
    isSelected: Boolean,
    hasReminder: Boolean,
    onClick: () -> Unit,
    onSelect: () -> Unit
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .background(if (isCurrent) Color(0x304A9EFF) else Color.Transparent)
            .clickable {
                onSelect()
                onClick()
            }
            .tvFocusBorder()
            .padding(horizontal = 12.dp, vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        // 左侧蓝色边框（当前节目）
        if (isCurrent) {
            Box(
                modifier = Modifier
                    .width(3.dp)
                    .height(36.dp)
                    .background(Color(0xFF4A9EFF))
            )
            Spacer(modifier = Modifier.width(8.dp))
        }

        Column(modifier = Modifier.weight(1f)) {
            // 时间行
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    text = "${formatTime(program.start)} - ${formatTime(program.stop)}",
                    color = if (isPast) Color(0xFF666666) else Color(0xFFAAAAAA),
                    fontSize = 11.sp
                )
                if (isCurrent) {
                    Spacer(modifier = Modifier.width(6.dp))
                    Text(
                        text = "LIVE",
                        color = Color(0xFFFF5252),
                        fontSize = 10.sp,
                        fontWeight = FontWeight.Bold
                    )
                }
                if (hasReminder) {
                    Spacer(modifier = Modifier.width(6.dp))
                    Text(
                        text = "🔔",
                        fontSize = 10.sp
                    )
                }
            }
            Spacer(modifier = Modifier.height(2.dp))
            // 节目标题
            Text(
                text = program.title,
                color = when {
                    isPast -> Color(0xFF666666)
                    isCurrent -> Color(0xFF6A9EFF)
                    else -> Color.White
                },
                fontSize = 13.sp,
                fontWeight = if (isCurrent) FontWeight.Medium else FontWeight.Normal,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis
            )
        }
    }
}

// =====================================================================
// 辅助函数
// =====================================================================

private fun formatTime(iso: String): String {
    if (iso.isEmpty()) return ""
    val ms = parseTimeToMs(iso)
    if (ms <= 0) return iso
    val cal = java.util.Calendar.getInstance().apply { timeInMillis = ms }
    return String.format(Locale.US, "%02d:%02d", cal.get(java.util.Calendar.HOUR_OF_DAY), cal.get(java.util.Calendar.MINUTE))
}

/** 解析 ISO 8601 时间字符串为毫秒时间戳（与 EpgPanel.parseTimeToMs 对齐） */
private fun parseTimeToMs(iso: String): Long {
    if (iso.isEmpty()) return 0
    return try {
        // 支持 "2026-07-02T12:30:00" 和 "20260702123000" 两种格式
        val cleaned = iso.replace(" ", "T").substringBefore("+").substringBefore("Z")
        if (cleaned.length >= 15 && !cleaned.contains("-")) {
            // "20260702123000" 格式
            val year = cleaned.substring(0, 4).toInt()
            val month = cleaned.substring(4, 6).toInt() - 1
            val day = cleaned.substring(6, 8).toInt()
            val hour = cleaned.substring(8, 10).toInt()
            val minute = cleaned.substring(10, 12).toInt()
            val second = if (cleaned.length >= 14) cleaned.substring(12, 14).toInt() else 0
            java.util.Calendar.getInstance().apply {
                clear()
                set(year, month, day, hour, minute, second)
            }.timeInMillis
        } else {
            // "2026-07-02T12:30:00" 格式
            val parts = cleaned.split("T")
            val dateParts = parts[0].split("-")
            val timeParts = if (parts.size > 1) parts[1].split(":") else listOf("0", "0", "0")
            java.util.Calendar.getInstance().apply {
                clear()
                set(
                    dateParts[0].toInt(),
                    dateParts[1].toInt() - 1,
                    dateParts[2].toInt(),
                    timeParts.getOrElse(0) { "0" }.toInt(),
                    timeParts.getOrElse(1) { "0" }.toInt(),
                    timeParts.getOrElse(2) { "0" }.substring(0, 2).toInt()
                )
            }.timeInMillis
        }
    } catch (e: Exception) {
        0
    }
}
