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
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.SyncAlt
import androidx.compose.material.icons.filled.Tune
import androidx.compose.material.icons.filled.VideoLibrary
import androidx.compose.material.icons.filled.VideoSettings
import androidx.compose.material.icons.filled.Visibility
import androidx.compose.material.icons.filled.VisibilityOff
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
import androidx.compose.ui.focus.onFocusChanged
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
    val currentIdx by viewModel.currentIdx.collectAsState()
    val channels by viewModel.channels.collectAsState()
    val favorites by viewModel.favorites.collectAsState()
    val isFavorite = currentIdx >= 0 && favorites.contains(currentIdx)

    // EPG 数据（使用焦点频道的 EPG，而非当前播放频道的 EPG）
    val focusedEpg by viewModel.focusedEpg.collectAsState()
    val focusedEpgLoading by viewModel.focusedEpgLoading.collectAsState()
    val controlsPinned by viewModel.controlsPinned.collectAsState()

    // 统一面板状态
    var unifiedMode by remember { mutableStateOf(UnifiedMode.CHANNELS) }
    var selectedProgram by remember { mutableStateOf<IptvEpgProgram?>(null) }

    // 焦点频道索引（频道列表中当前聚焦的频道，用于 EPG 跟随显示）
    var focusedChannelIdx by remember { mutableStateOf(currentIdx) }
    val focusedChannel = remember(focusedChannelIdx, channels) {
        channels.getOrNull(focusedChannelIdx)
    }

    // 焦点管理：初始焦点在第二列（频道列表）
    val column2Focus = remember { FocusRequester() }
    LaunchedEffect(Unit) {
        kotlin.runCatching { column2Focus.requestFocus() }
    }

    // 焦点频道变化时刷新 EPG
    LaunchedEffect(focusedChannelIdx) {
        selectedProgram = null
        if (focusedChannelIdx >= 0) {
            viewModel.fetchEpgForChannel(focusedChannelIdx)
        }
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

    /** 关闭统一面板后执行操作（仅用于在统一面板之前渲染的 ChannelsPanel/EpgPanel，避免被统一面板遮挡） */
    fun closeAndRun(action: () -> Unit) {
        viewModel.toggleTvUnifiedPanel()
        action()
    }

    /**
     * 打开全屏覆盖子面板，同时关闭统一面板。
     *
     * 关键：必须关闭统一面板，让 TvUnifiedPanel 从 Compose 树中移除。
     * 否则 TvUnifiedPanel 残留在树中，子面板 focusGroup() 在 DPAD 边缘
     * 会让焦点逃逸到下层 TvUnifiedPanel 的菜单项（特别是 ModeIconButton 的
     * autoSelectOnFocus=true 会自动触发模式切换），导致遥控器操作下层菜单
     * 而非当前子面板。
     *
     * 子面板关闭后回到播放界面，用户按 MENU 键可重新打开主菜单。
     */
    fun openOverlay(action: () -> Unit) {
        viewModel.toggleTvUnifiedPanel()
        action()
    }

    Surface(
        color = Color(0xE6000000),
        modifier = Modifier.fillMaxSize()
    ) {
        Row(modifier = Modifier.fillMaxSize()) {
            // -----------------------------------------------------------------
            // 第一列：模式切换图标 + OSD 按钮
            // -----------------------------------------------------------------
            ModeColumn(
                mode = unifiedMode,
                controlsPinned = controlsPinned,
                onModeChange = { newMode ->
                    unifiedMode = newMode
                    selectedProgram = null
                },
                onOsd = {
                    // 切换控制层持久模式（pin/unpin），关闭面板
                    viewModel.toggleTvUnifiedPanel()
                    viewModel.toggleControlsPinned()
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
                    onChannelClick = { idx -> viewModel.playChannel(idx) },
                    onFocusedChannelChange = { idx -> focusedChannelIdx = idx },
                    modifier = Modifier.width(360.dp).focusRequester(column2Focus)
                )
                UnifiedMode.MENU -> MenuColumn(
                    viewModel = viewModel,
                    currentIdx = currentIdx,
                    isFavorite = isFavorite,
                    onOpenPlaylist = {
                        // FileBrowserPanel 在统一面板之后渲染；SAF launcher 是系统级浮层。
                        // 两者关闭后焦点自然回到统一面板菜单项。
                        openOverlay {
                            if (!viewModel.isSafAvailable()) {
                                viewModel.showFileBrowser()
                            } else {
                                playlistLauncher.launch(arrayOf(
                                    "application/x-mpegurl", "application/vnd.apple.mpegurl",
                                    "audio/x-mpegurl", "video/x-mpegurl",
                                    "text/plain", "application/octet-stream"
                                ))
                            }
                        }
                    },
                    onOpenUrl = { openOverlay { viewModel.toggleOpenUrlDialog() } },
                    onOpenLocalVideo = {
                        openOverlay {
                            if (!viewModel.isSafAvailable()) {
                                viewModel.showMediaFileBrowser()
                            } else {
                                videoLauncher.launch(arrayOf("video/*", "audio/*", "application/x-matroska", "application/octet-stream"))
                            }
                        }
                    },
                    onSources = {
                        openOverlay {
                            viewModel.setSourceTab(AppViewModel.SourceTab.PLAYLIST)
                            viewModel.toggleSourceManager()
                        }
                    },
                    onEpgSources = {
                        openOverlay {
                            viewModel.setSourceTab(AppViewModel.SourceTab.EPG)
                            viewModel.toggleSourceManager()
                        }
                    },
                    onMapping = { openOverlay { viewModel.toggleMappingPanel() } },
                    // ChannelsPanel/EpgPanel 在统一面板之前渲染，会被统一面板遮挡，必须先关闭统一面板
                    onChannels = { closeAndRun { viewModel.showChannelsPanel() } },
                    onEpg = { closeAndRun { viewModel.showEpgPanel() } },
                    onSubtitle = { openOverlay { viewModel.toggleSubtitleSettings() } },
                    onVideo = { openOverlay { viewModel.toggleVideoSettings() } },
                    onAudio = { openOverlay { viewModel.toggleAudioSettings() } },
                    onPlayback = { openOverlay { viewModel.togglePlaybackPanel() } },
                    onScreenshot = { openOverlay { viewModel.toggleScreenshotPanel() } },
                    onAvsync = { openOverlay { viewModel.toggleAvSyncPanel() } },
                    onNetwork = { openOverlay { viewModel.toggleNetworkPanel() } },
                    onTools = { openOverlay { viewModel.toggleToolsPanel() } },
                    onView = { openOverlay { viewModel.toggleViewSettings() } },
                    onSettings = { openOverlay { viewModel.togglePlayerSettings() } },
                    onAbout = { openOverlay { viewModel.toggleAboutPanel() } },
                    onToggleFavorite = { viewModel.toggleFavorite() },
                    onQuit = { viewModel.showOsd("退出", "请使用系统返回键退出") },
                    modifier = Modifier.width(360.dp).focusRequester(column2Focus)
                )
            }

            // -----------------------------------------------------------------
            // 第三列：EPG 节目单 + 描述（仅频道列表模式，跟随焦点频道）
            // -----------------------------------------------------------------
            if (unifiedMode == UnifiedMode.CHANNELS && focusedChannel != null) {
                EpgColumn(
                    channel = focusedChannel,
                    epg = focusedEpg,
                    loading = focusedEpgLoading,
                    currentIdx = currentIdx,
                    selectedProgram = selectedProgram,
                    onProgramSelect = { program -> selectedProgram = program },
                    onProgramClick = { program ->
                        val now = System.currentTimeMillis()
                        val isPast = program.stopTs * 1000L < now
                        if (isPast) {
                            // 过去节目：触发回看（先切换到焦点频道再回看）
                            viewModel.playChannel(focusedChannelIdx)
                            closeAndRun { viewModel.startCatchup(program) }
                        } else {
                            // 当前/未来节目：设置提醒
                            viewModel.toggleReminder(program, focusedChannel)
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
    controlsPinned: Boolean,
    onModeChange: (UnifiedMode) -> Unit,
    onOsd: () -> Unit,
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
                onClick = { onModeChange(UnifiedMode.CHANNELS) },
                autoSelectOnFocus = true
            )
            ModeIconButton(
                icon = Icons.Default.Menu,
                label = "菜单",
                isSelected = mode == UnifiedMode.MENU,
                onClick = { onModeChange(UnifiedMode.MENU) },
                autoSelectOnFocus = true
            )
            // OSD 按钮（切换控制层持久显示）：需要按 OK 键触发，不自动选中
            ModeIconButton(
                icon = if (controlsPinned) Icons.Default.Visibility else Icons.Default.VisibilityOff,
                label = "OSD",
                isSelected = controlsPinned,
                onClick = onOsd
            )
        }
    }
}

@Composable
private fun ModeIconButton(
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    label: String,
    isSelected: Boolean,
    onClick: () -> Unit,
    autoSelectOnFocus: Boolean = false
) {
    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        modifier = Modifier
            .clip(RoundedCornerShape(8.dp))
            .background(if (isSelected) Color(0xFF2A4A6A) else Color.Transparent)
            .tvFocusBorder()
            .onFocusChanged { state ->
                // 焦点切入时自动触发模式切换（TV 端无需按 OK 键）
                // 已选中的不重复触发，避免 recomposition 循环
                if (autoSelectOnFocus && state.isFocused && !isSelected) {
                    onClick()
                }
            }
            .clickable { onClick() }
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
    onChannelClick: (Int) -> Unit,
    onFocusedChannelChange: (Int) -> Unit,
    modifier: Modifier = Modifier
) {
    val filteredChannels = remember(channels) {
        channels.mapIndexed { idx, c -> c to idx }
    }

    // 滚动状态：用于面板打开时自动滚动到当前频道
    val listState = rememberLazyListState()
    // 当前频道项的焦点请求器（面板打开时将 DPAD 焦点移到当前播放频道）
    val currentChannelFocus = remember { FocusRequester() }

    // 面板打开时自动滚动到当前频道（居中显示）并将焦点移到当前频道
    LaunchedEffect(currentIdx, filteredChannels) {
        if (filteredChannels.isNotEmpty() && currentIdx >= 0) {
            val pos = filteredChannels.indexOfFirst { (_, idx) -> idx == currentIdx }
            if (pos >= 0) {
                // 第一阶段：先跳到目标位置（无动画），强制列表布局更新
                listState.scrollToItem(pos)
                kotlinx.coroutines.delay(50)
                // 第二阶段：根据视口高度和列表项高度计算居中偏移
                val layoutInfo = listState.layoutInfo
                val viewportHeight = layoutInfo.viewportSize.height
                val itemHeight = layoutInfo.visibleItemsInfo.firstOrNull()?.size ?: 56
                val visibleCount = if (itemHeight > 0) viewportHeight / itemHeight else 7
                val centeredPos = (pos - visibleCount / 2).coerceAtLeast(0)
                listState.scrollToItem(centeredPos)
                // 第三阶段：将焦点移到当前频道项
                kotlinx.coroutines.delay(30)
                kotlin.runCatching { currentChannelFocus.requestFocus() }
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
                    state = listState,
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
                            focusRequester = if (idx == currentIdx) currentChannelFocus else null,
                            onClick = { onChannelClick(idx) },
                            onFocusChange = { isFocused ->
                                if (isFocused) onFocusedChannelChange(idx)
                            }
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
    onClick: () -> Unit,
    onFocusChange: (Boolean) -> Unit = {},
    focusRequester: FocusRequester? = null
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .then(if (focusRequester != null) Modifier.focusRequester(focusRequester) else Modifier)
            .onFocusChanged { onFocusChange(it.isFocused) }
            .tvFocusBorder()
            .clickable { onClick() }
            .padding(horizontal = 12.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        // 频道台标（logo）：有 logo 显示图片，无 logo 显示圆点
        if (channel.logo.isNotEmpty()) {
            coil.compose.AsyncImage(
                model = channel.logo,
                contentDescription = channel.name,
                modifier = Modifier
                    .size(32.dp)
                    .clip(RoundedCornerShape(4.dp)),
                contentScale = androidx.compose.ui.layout.ContentScale.Fit
            )
        } else {
            Box(
                modifier = Modifier
                    .size(8.dp)
                    .clip(CircleShape)
                    .background(if (isPlaying) Color(0xFF4A9EFF) else Color(0xFF444444))
            )
        }
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
            TvMenuItem("打开本地文件", "播放设备视频/音频文件", Icons.Default.Movie, onOpenLocalVideo),
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
            .tvFocusBorder()
            .clickable { item.onClick() }
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
    val now = remember { System.currentTimeMillis() }

    // 自动滚动到当前直播节目（居中显示）
    LaunchedEffect(epg) {
        if (epg.isNotEmpty()) {
            val currentNow = System.currentTimeMillis()
            val currentProgIdx = epg.indexOfFirst { p ->
                p.startTs * 1000L <= currentNow && currentNow <= p.stopTs * 1000L
            }
            val targetIdx = if (currentProgIdx >= 0) currentProgIdx else 0
            if (targetIdx < epg.size) {
                // 第一阶段：先跳到目标项（无动画），强制列表布局更新
                listState.scrollToItem(targetIdx)
                // 第二阶段：等待布局完成后获取准确的视口和列表项尺寸
                kotlinx.coroutines.delay(50)
                val layoutInfo = listState.layoutInfo
                val viewportHeight = layoutInfo.viewportSize.height
                val itemHeight = layoutInfo.visibleItemsInfo.firstOrNull()?.size ?: 64
                val visibleCount = if (itemHeight > 0) viewportHeight / itemHeight else 5
                val centeredIdx = (targetIdx - visibleCount / 2).coerceAtLeast(0)
                listState.animateScrollToItem(centeredIdx)
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

                    // 下半部分：节目描述（优先显示用户选中节目，无选中时自动显示当前播出节目）
                    Box(
                        modifier = Modifier.weight(0.4f).fillMaxWidth().padding(12.dp)
                    ) {
                        // 优先使用用户选中的节目，否则自动查找当前正在播出的节目
                        val now = System.currentTimeMillis()
                        val currentProg = selectedProgram ?: epg.find { p ->
                            p.startTs * 1000L <= now && now <= p.stopTs * 1000L
                        }
                        if (currentProg != null) {
                            val isAuto = selectedProgram == null
                            Column {
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    Text(
                                        text = currentProg.title,
                                        color = Color.White,
                                        fontSize = 15.sp,
                                        fontWeight = FontWeight.Medium,
                                        maxLines = 2,
                                        overflow = TextOverflow.Ellipsis,
                                        modifier = Modifier.weight(1f)
                                    )
                                    if (isAuto) {
                                        Spacer(modifier = Modifier.width(6.dp))
                                        Text(
                                            text = "LIVE",
                                            color = Color(0xFFFF5252),
                                            fontSize = 10.sp,
                                            fontWeight = FontWeight.Bold
                                        )
                                    }
                                }
                                Spacer(modifier = Modifier.height(4.dp))
                                Text(
                                    text = "${formatTime(currentProg.start)} - ${formatTime(currentProg.stop)}",
                                    color = Color(0xFF4A9EFF),
                                    fontSize = 12.sp
                                )
                                Spacer(modifier = Modifier.height(8.dp))
                                Text(
                                    text = currentProg.desc.ifEmpty { "暂无节目描述" },
                                    color = Color(0xFFCCCCCC),
                                    fontSize = 12.sp,
                                    lineHeight = 18.sp,
                                    maxLines = 4,
                                    overflow = TextOverflow.Ellipsis
                                )
                            }
                        } else {
                            Text(
                                text = "暂无节目信息",
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
            .tvFocusBorder()
            .clickable {
                onSelect()
                onClick()
            }
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
