package com.iptv.scanner.editor.pro.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.gestures.detectVerticalDragGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.systemBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Cast
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.filled.Pause
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.SkipNext
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material.icons.filled.Fullscreen
import androidx.compose.material.icons.filled.VolumeOff
import androidx.compose.material.icons.filled.VolumeUp
import androidx.compose.material.icons.filled.Favorite
import androidx.compose.material.icons.filled.FavoriteBorder
import androidx.compose.material.icons.filled.Info
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.luminance
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import coil.compose.AsyncImage
import com.iptv.scanner.editor.pro.player.ProgressHelper
import com.iptv.scanner.editor.pro.ui.theme.GlassPanel
import com.iptv.scanner.editor.pro.ui.theme.rememberPlayerOverlayColors
import com.iptv.scanner.editor.pro.ui.theme.tvFocusBorder
import kotlinx.coroutines.delay

/**
 * 横屏分屏播放布局（TV/横屏新默认布局）：
 * - 左列（58%）：顶部频道信息条 + 16:9 视频窗口 + 常驻控制条（节目/进度/播放/切台/工具/全屏）
 * - 右列（42%）：常驻暗玻璃面板 = 顶部收藏/投屏/信息 + 分段控件（分类/频道/节目/信息）+ 内容区
 *   （复用竖屏播放页视频下方4大内容组件）
 *
 * 全屏模式（setLandscapeSplitMode(false)）保持原有 TvPlayerLayout 沉浸式布局不变。
 *
 * 视觉规范（与项目硬约束对齐）：
 * - 右列面板使用 GlassPanel(overlayDark=true)：暗玻璃霜层 + DarkOverlayTheme 白系文字
 * - 主色 AptvAccent 橙红；分段控件选中态白亮玻璃凸起
 * - 视频窗口圆角黑底（与竖屏画布视频窗口一致）；SurfaceView 由 movableContent 移动，不重建
 */
@Composable
internal fun TvSplitLayout(
    viewModel: AppViewModel,
    primaryPlayer: @Composable () -> Unit
) {
    val oc = rememberPlayerOverlayColors()
    val liquidGlass by viewModel.liquidGlass.collectAsState()
    val displayInfo by viewModel.channelDisplayInfo.collectAsState()
    val currentChannel by viewModel.currentChannel.collectAsState()
    val favorites by viewModel.favorites.collectAsState()
    val currentIdx by viewModel.currentIdx.collectAsState()
    val paused by viewModel.mpv.paused.collectAsState()
    val fileLoaded by viewModel.mpv.fileLoaded.collectAsState()
    val muted by viewModel.mpv.muted.collectAsState()
    val dlnaConnected by viewModel.dlnaConnected.collectAsState()
    val currentEpg by viewModel.currentEpg.collectAsState()

    val currentProgram = remember(currentEpg) {
        ProgressHelper.findCurrentProgram(currentEpg, System.currentTimeMillis())
    }
    val isFavorite = currentIdx >= 0 && favorites.contains(currentIdx)

    // 进度数据（1秒刷新）
    var tick by remember { mutableStateOf(0L) }
    androidx.compose.runtime.LaunchedEffect(Unit) {
        while (true) {
            tick = System.currentTimeMillis()
            delay(1000L)
        }
    }
    val timeFmt = remember { java.text.SimpleDateFormat("HH:mm", java.util.Locale.getDefault()) }

    // 统一画布背景（与横屏首页一致）：深/浅主题渐变底 + 三色光斑。
    // 修复分屏左列无背景透出窗口白底、深色主题下顶栏浅色文字不可见的问题
    val canvasDark = MaterialTheme.colorScheme.background.luminance() < 0.5f
    Row(
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
            .drawBehind {
                drawRect(
                    androidx.compose.ui.graphics.Brush.verticalGradient(
                        if (canvasDark) listOf(
                            androidx.compose.ui.graphics.Color(0xFF0B0F1A),
                            androidx.compose.ui.graphics.Color(0xFF151B2C)
                        ) else listOf(
                            androidx.compose.ui.graphics.Color(0xFFE9EEF7),
                            androidx.compose.ui.graphics.Color(0xFFF9FBFF)
                        )
                    )
                )
                val g = if (canvasDark) 0.32f else 0.24f
                drawCircle(
                    brush = androidx.compose.ui.graphics.Brush.radialGradient(
                        listOf(androidx.compose.ui.graphics.Color(0x5B8CFF).copy(alpha = g), androidx.compose.ui.graphics.Color.Transparent)
                    ),
                    radius = size.width * 0.85f,
                    center = androidx.compose.ui.geometry.Offset(size.width * 0.15f, size.height * 0.12f)
                )
                drawCircle(
                    brush = androidx.compose.ui.graphics.Brush.radialGradient(
                        listOf(androidx.compose.ui.graphics.Color(0xC084FC).copy(alpha = g * 0.85f), androidx.compose.ui.graphics.Color.Transparent)
                    ),
                    radius = size.width * 0.75f,
                    center = androidx.compose.ui.geometry.Offset(size.width * 0.95f, size.height * 0.52f)
                )
                drawCircle(
                    brush = androidx.compose.ui.graphics.Brush.radialGradient(
                        listOf(androidx.compose.ui.graphics.Color(0x34D399).copy(alpha = g * 0.7f), androidx.compose.ui.graphics.Color.Transparent)
                    ),
                    radius = size.width * 0.7f,
                    center = androidx.compose.ui.geometry.Offset(size.width * 0.2f, size.height * 0.95f)
                )
            }
            .systemBarsPadding()
            .padding(6.dp)
    ) {
        // ==================== 左列：视频 + 控制条 ====================
        Column(
            modifier = Modifier
                .weight(0.58f)
                .fillMaxHeight()
                .padding(end = 6.dp)
        ) {
            // 顶部信息条：返回首页 + 台标 + 频道名 + 分组
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(44.dp)
                    .padding(bottom = 4.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                IconButton(
                    onClick = { viewModel.showHomeScreen() },
                    modifier = Modifier.size(36.dp).tvFocusBorder()
                ) {
                    Icon(
                        Icons.AutoMirrored.Filled.ArrowBack,
                        contentDescription = "返回首页",
                        tint = oc.iconTint,
                        modifier = Modifier.size(22.dp)
                    )
                }
                Spacer(modifier = Modifier.width(4.dp))
                // 台标（浅色主题下白色台标加 surfaceVariant 衬底，避免幽灵化）
                if (displayInfo.logo.isNotEmpty()) {
                    Box(
                        modifier = Modifier
                            .size(34.dp)
                            .clip(RoundedCornerShape(5.dp))
                            .background(MaterialTheme.colorScheme.surfaceVariant),
                        contentAlignment = Alignment.Center
                    ) {
                        AsyncImage(
                            model = displayInfo.logo,
                            contentDescription = displayInfo.name,
                            modifier = Modifier.fillMaxSize().padding(3.dp),
                            contentScale = ContentScale.Fit
                        )
                    }
                    Spacer(modifier = Modifier.width(8.dp))
                }
                Text(
                    text = displayInfo.name.ifEmpty { "未选择频道" },
                    color = oc.textPrimary,
                    fontSize = 17.sp,
                    fontWeight = FontWeight.Bold,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
                if (displayInfo.group.isNotEmpty()) {
                    Spacer(modifier = Modifier.width(6.dp))
                    Surface(
                        color = AptvAccent.copy(alpha = 0.12f),
                        shape = RoundedCornerShape(4.dp)
                    ) {
                        Text(
                            text = displayInfo.group,
                            color = AptvAccent,
                            fontSize = 11.sp,
                            modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp),
                            maxLines = 1
                        )
                    }
                }
            }

            // 视频窗口：圆角黑底（movableContent 移动 SurfaceView，不重建）
            val videoWidth by viewModel.mpv.videoWidth.collectAsState()
            val videoHeight by viewModel.mpv.videoHeight.collectAsState()
            val videoAspectRatio = if (videoWidth > 0 && videoHeight > 0) {
                videoWidth.toFloat() / videoHeight.toFloat()
            } else 16f / 9f
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .weight(1f),
                contentAlignment = Alignment.Center
            ) {
                Box(
                    modifier = Modifier
                        .aspectRatio(videoAspectRatio)
                        .clip(RoundedCornerShape(12.dp))
                        .background(Color.Black)
                ) {
                    primaryPlayer()
                    // 视频触控层：单击暂停/恢复 + 双击全屏 + 上下滑切台（与竖屏一致）
                    if (fileLoaded) {
                        val haptic = LocalHapticFeedback.current
                        Box(
                            modifier = Modifier
                                .fillMaxSize()
                                .pointerInput(Unit) {
                                    detectTapGestures(
                                        onTap = {
                                            if (viewModel.mpv.paused.value) viewModel.mpv.setPause(false)
                                            else viewModel.mpv.setPause(true)
                                        },
                                        onDoubleTap = {
                                            viewModel.setLandscapeSplitMode(false)
                                        }
                                    )
                                }
                                .pointerInput(Unit) {
                                    var totalY = 0f
                                    var triggered = false
                                    detectVerticalDragGestures(
                                        onDragStart = { totalY = 0f; triggered = false },
                                        onDragEnd = { totalY = 0f; triggered = false },
                                        onVerticalDrag = { change, dragAmount ->
                                            change.consume()
                                            totalY += dragAmount
                                            val threshold = 80f
                                            if (!triggered && kotlin.math.abs(totalY) > threshold) {
                                                triggered = true
                                                if (totalY < 0) viewModel.prevChannel() else viewModel.nextChannel()
                                                haptic.performHapticFeedback(HapticFeedbackType.LongPress)
                                            }
                                        }
                                    )
                                }
                        )
                    }
                }
            }

            // 控制条（常驻，图2样式）
            GlassPanel(
                liquidGlass = liquidGlass,
                cornerRadius = 12.dp,
                overlayDark = true,
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 6.dp)
            ) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 12.dp, vertical = 8.dp)
                ) {
                    // 行1：节目名 + 直播状态 + 进度条 + 时间范围 + 静音 + 播放/暂停 + 下一台
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Column(modifier = Modifier.weight(1f)) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                // 直播/回看红点
                                Box(
                                    modifier = Modifier
                                        .size(6.dp)
                                        .clip(RoundedCornerShape(3.dp))
                                        .background(AptvAccent)
                                )
                                Spacer(modifier = Modifier.width(5.dp))
                                Text(
                                    text = currentProgram?.title?.ifEmpty { null }
                                        ?: displayInfo.name.ifEmpty { "精彩节目" },
                                    color = oc.textPrimary,
                                    fontSize = 14.sp,
                                    fontWeight = FontWeight.Medium,
                                    maxLines = 1,
                                    overflow = TextOverflow.Ellipsis,
                                    modifier = Modifier.weight(1f, fill = false)
                                )
                            }
                        }
                        // 进度条 + 时间范围（有节目时显示）
                        if (currentProgram != null && currentProgram.stopTs > 0) {
                            val timeRange = remember(currentProgram) {
                                val start = timeFmt.format(java.util.Date(currentProgram.startTs * 1000L))
                                val end = timeFmt.format(java.util.Date(currentProgram.stopTs * 1000L))
                                "$start-$end"
                            }
                            val progress = remember(tick, currentProgram) {
                                val nowSec = System.currentTimeMillis() / 1000L
                                val total = (currentProgram.stopTs - currentProgram.startTs).coerceAtLeast(1)
                                val elapsed = (nowSec - currentProgram.startTs).coerceIn(0, total)
                                elapsed.toFloat() / total
                            }
                            Box(
                                modifier = Modifier
                                    .width(120.dp)
                                    .height(3.dp)
                                    .clip(RoundedCornerShape(1.5.dp))
                                    .background(Color(0x30FFFFFF))
                            ) {
                                Box(
                                    modifier = Modifier
                                        .fillMaxHeight()
                                        .fillMaxWidth(progress)
                                        .clip(RoundedCornerShape(1.5.dp))
                                        .background(AptvAccent)
                                )
                            }
                            Spacer(modifier = Modifier.width(8.dp))
                            Text(text = timeRange, color = oc.textSecondary, fontSize = 12.sp)
                        }
                        Spacer(modifier = Modifier.width(6.dp))
                        // 静音
                        IconButton(
                            onClick = { viewModel.mpv.setMute(!muted) },
                            modifier = Modifier.size(34.dp).tvFocusBorder()
                        ) {
                            Icon(
                                if (muted) Icons.Default.VolumeOff else Icons.Default.VolumeUp,
                                contentDescription = if (muted) "取消静音" else "静音",
                                tint = if (muted) oc.iconTintActive else oc.iconTint,
                                modifier = Modifier.size(20.dp)
                            )
                        }
                        // 播放/暂停
                        IconButton(
                            onClick = { viewModel.mpv.setPause(!paused) },
                            modifier = Modifier.size(40.dp).tvFocusBorder()
                        ) {
                            Icon(
                                if (paused) Icons.Default.PlayArrow else Icons.Default.Pause,
                                contentDescription = if (paused) "播放" else "暂停",
                                tint = oc.accent,
                                modifier = Modifier.size(26.dp)
                            )
                        }
                        // 下一台
                        IconButton(
                            onClick = { viewModel.nextChannel() },
                            modifier = Modifier.size(34.dp).tvFocusBorder()
                        ) {
                            Icon(
                                Icons.Default.SkipNext,
                                contentDescription = "下一个频道",
                                tint = oc.iconTint,
                                modifier = Modifier.size(20.dp)
                            )
                        }
                    }

                    // 行2：停止 + 播放工具 + 播放器设置 + spacer + 收藏 + 全屏
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        IconButton(
                            onClick = { viewModel.stopPlay() },
                            modifier = Modifier.size(34.dp).tvFocusBorder()
                        ) {
                            Icon(Icons.Default.Stop, "停止", tint = oc.iconTint, modifier = Modifier.size(18.dp))
                        }
                        IconButton(
                            onClick = { viewModel.togglePlayerToolsPanel() },
                            modifier = Modifier.size(34.dp).tvFocusBorder()
                        ) {
                            Icon(Icons.Default.MoreVert, "播放工具", tint = oc.iconTint, modifier = Modifier.size(18.dp))
                        }
                        IconButton(
                            onClick = { viewModel.togglePlayerSettings() },
                            modifier = Modifier.size(34.dp).tvFocusBorder()
                        ) {
                            Icon(Icons.Default.Settings, "播放器设置", tint = oc.iconTint, modifier = Modifier.size(18.dp))
                        }
                        Spacer(modifier = Modifier.weight(1f))
                        // 收藏
                        IconButton(
                            onClick = { viewModel.toggleFavorite() },
                            modifier = Modifier.size(34.dp).tvFocusBorder()
                        ) {
                            Icon(
                                if (isFavorite) Icons.Default.Favorite else Icons.Default.FavoriteBorder,
                                contentDescription = "收藏",
                                tint = if (isFavorite) Color(0xFFFFC107) else oc.iconTint,
                                modifier = Modifier.size(18.dp)
                            )
                        }
                        // 全屏：切回传统全屏布局
                        IconButton(
                            onClick = { viewModel.setLandscapeSplitMode(false) },
                            modifier = Modifier.size(34.dp).tvFocusBorder()
                        ) {
                            Icon(
                                Icons.Default.Fullscreen,
                                contentDescription = "全屏",
                                tint = oc.iconTint,
                                modifier = Modifier.size(20.dp)
                            )
                        }
                    }
                }
            }
        }

        // ==================== 右列：常驻面板（竖屏4大内容） ====================
        GlassPanel(
            liquidGlass = liquidGlass,
            cornerRadius = 12.dp,
            overlayDark = true,
            modifier = Modifier
                .weight(0.42f)
                .fillMaxHeight()
        ) {
            SplitSidePanel(viewModel = viewModel)
        }
    }
}

/**
 * 分屏右侧常驻面板：收藏/投屏/信息按钮行 + 分段控件 + 4大内容区。
 * GlassPanel(overlayDark) 内部已是 DarkOverlayTheme 白系作用域。
 */
@Composable
private fun SplitSidePanel(viewModel: AppViewModel) {
    val oc = rememberPlayerOverlayColors()
    val currentIdx by viewModel.currentIdx.collectAsState()
    val currentChannel by viewModel.currentChannel.collectAsState()
    val favorites by viewModel.favorites.collectAsState()
    val dlnaConnected by viewModel.dlnaConnected.collectAsState()
    val player = viewModel.mpv
    val fileLoaded by player.fileLoaded.collectAsState()

    // 本地文件 vs 订阅频道（与竖屏 PortraitPlayerDynamicContent 一致）
    val isLocalFile = currentChannel == null || currentIdx < 0

    var selectedTab by remember { mutableStateOf(0) }
    val tabs = if (isLocalFile) {
        listOf("信息", "最近文件")
    } else {
        listOf("分类", "频道", "节目", "信息")
    }
    androidx.compose.runtime.LaunchedEffect(tabs.size) {
        if (selectedTab >= tabs.size) selectedTab = 0
    }

    Column(modifier = Modifier.fillMaxSize()) {
        // 顶行：收藏 / 投屏 / 信息（右侧对齐，图2右上角按钮组）
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .height(44.dp)
                .padding(horizontal = 8.dp),
            horizontalArrangement = Arrangement.End,
            verticalAlignment = Alignment.CenterVertically
        ) {
            IconButton(
                onClick = { viewModel.toggleFavorite() },
                modifier = Modifier.size(34.dp).tvFocusBorder()
            ) {
                Icon(
                    if (favorites.contains(currentIdx)) Icons.Default.Favorite else Icons.Default.FavoriteBorder,
                    contentDescription = "收藏",
                    tint = if (favorites.contains(currentIdx)) Color(0xFFFFC107) else oc.iconTint,
                    modifier = Modifier.size(20.dp)
                )
            }
            IconButton(
                onClick = { viewModel.toggleDlnaPanel() },
                modifier = Modifier.size(34.dp).tvFocusBorder()
            ) {
                Icon(
                    Icons.Default.Cast,
                    contentDescription = "投屏",
                    tint = if (dlnaConnected != null) AptvAccent else oc.iconTint,
                    modifier = Modifier.size(20.dp)
                )
            }
            IconButton(
                onClick = { viewModel.toggleChannelInfo() },
                modifier = Modifier.size(34.dp).tvFocusBorder()
            ) {
                Icon(Icons.Default.Info, "频道信息", tint = oc.iconTint, modifier = Modifier.size(20.dp))
            }
        }

        // 分段控件：iOS 白亮玻璃凸起选中态（与竖屏播放页下方 TAB 一致）
        Surface(
            color = Color.White.copy(alpha = 0.08f),
            shape = RoundedCornerShape(12.dp),
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 8.dp, vertical = 2.dp)
        ) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 3.dp, vertical = 3.dp)
            ) {
                tabs.forEachIndexed { index, label ->
                    val isSelected = index == selectedTab
                    val tabShape = RoundedCornerShape(9.dp)
                    Box(
                        modifier = Modifier
                            .weight(1f)
                            .clip(tabShape)
                            .then(
                                if (isSelected) Modifier
                                    .background(Color.White.copy(alpha = 0.20f), tabShape)
                                    .border(1.dp, Color.White.copy(alpha = 0.45f), tabShape)
                                    .background(
                                        androidx.compose.ui.graphics.Brush.verticalGradient(
                                            0f to Color.White.copy(alpha = 0.22f),
                                            1f to Color.Transparent
                                        ),
                                        tabShape
                                    )
                                else Modifier
                            )
                            .clickable { selectedTab = index }
                            .padding(vertical = 7.dp),
                        contentAlignment = Alignment.Center
                    ) {
                        Text(
                            text = label,
                            color = if (isSelected) AptvAccent else oc.textSecondary,
                            fontSize = 13.sp,
                            fontWeight = if (isSelected) FontWeight.SemiBold else FontWeight.Normal,
                            textAlign = TextAlign.Center,
                            maxLines = 1
                        )
                    }
                }
            }
        }

        // 内容区：复用竖屏播放页视频下方4大内容
        Box(modifier = Modifier.fillMaxSize()) {
            if (!fileLoaded) {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Text(
                        text = "未在播放",
                        color = oc.textSecondary,
                        fontSize = 14.sp
                    )
                }
            } else {
                androidx.compose.animation.Crossfade(
                    targetState = selectedTab,
                    animationSpec = androidx.compose.animation.core.tween(durationMillis = 200),
                    label = "splitTab"
                ) { tab ->
                    if (isLocalFile) {
                        when (tab) {
                            0 -> {
                                val duration by player.duration.collectAsState()
                                val timePos by player.timePos.collectAsState()
                                val videoWidth by player.videoWidth.collectAsState()
                                val videoHeight by player.videoHeight.collectAsState()
                                PortraitLocalFileInfo(
                                    viewModel = viewModel,
                                    duration = duration,
                                    timePos = timePos,
                                    videoWidth = videoWidth,
                                    videoHeight = videoHeight
                                )
                            }
                            else -> PortraitRecentLocalFiles(viewModel = viewModel)
                        }
                    } else {
                        when (tab) {
                            0 -> PortraitCategoryContent(viewModel = viewModel, onGroupSelected = { selectedTab = 1 })
                            1 -> PortraitChannelOnlyList(viewModel = viewModel)
                            2 -> PortraitEpgContent(viewModel = viewModel)
                            else -> {
                                val duration by player.duration.collectAsState()
                                val timePos by player.timePos.collectAsState()
                                val videoWidth by player.videoWidth.collectAsState()
                                val videoHeight by player.videoHeight.collectAsState()
                                PortraitPlayerInfoPanel(
                                    viewModel = viewModel,
                                    duration = duration,
                                    timePos = timePos,
                                    videoWidth = videoWidth,
                                    videoHeight = videoHeight
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}
