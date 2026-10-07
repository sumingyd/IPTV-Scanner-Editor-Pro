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
import androidx.compose.material.icons.filled.Cast
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
import androidx.compose.material.icons.filled.Language
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
internal fun PortraitBottomTabBar(
    viewModel: AppViewModel,
    modifier: Modifier = Modifier
) {
    val portraitTab by viewModel.portraitTab.collectAsState()
    val bgColor = MaterialTheme.colorScheme.surface
    // APTV 风格竖屏强调色（红粉），不影响横屏/TV 主题
    val accentColor = AptvAccent
    val tabShape = RoundedCornerShape(20.dp)
    val isAndroid12Plus = android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.S

    val tabItems = listOf(
        Triple(Icons.Default.Language, stringResource(R.string.tab_home), PortraitTab.CHANNELS),
        Triple(Icons.Default.Favorite, stringResource(R.string.tab_list), PortraitTab.FAVORITES),
        Triple(Icons.Default.Build, stringResource(R.string.tab_tools), PortraitTab.TOOLS),
        Triple(Icons.Default.Settings, stringResource(R.string.tab_settings), PortraitTab.SETTINGS)
    )

    val tabContent: @Composable RowScope.() -> Unit = {
        tabItems.forEach { (icon, label, tab) ->
            val isSelected = portraitTab == tab
            val tint = if (isSelected) accentColor else MaterialTheme.colorScheme.onSurfaceVariant
            Column(
                horizontalAlignment = Alignment.CenterHorizontally,
                modifier = Modifier
                    .height(48.dp)
                    .clip(RoundedCornerShape(10.dp))
                    .then(if (isSelected) Modifier.border(1.dp, accentColor.copy(alpha = 0.50f), RoundedCornerShape(10.dp)) else Modifier)
                    .clickable {
                        viewModel.setPortraitTab(tab)
                    }
                    .padding(horizontal = 18.dp, vertical = 4.dp)
            ) {
                Icon(imageVector = icon, contentDescription = label, tint = tint, modifier = Modifier.size(22.dp))
                Spacer(modifier = Modifier.height(2.dp))
                Text(
                    text = label,
                    color = tint,
                    fontSize = 10.sp,
                    fontWeight = if (isSelected) FontWeight.Medium else FontWeight.Normal
                )
            }
        }
    }

    if (isAndroid12Plus) {
        Box(
            modifier = modifier
                .fillMaxWidth()
                .padding(horizontal = 12.dp, vertical = 4.dp)
                .navigationBarsPadding()
                .height(56.dp)
                .shadow(8.dp, tabShape)
        ) {
            Box(
                modifier = Modifier
                    .matchParentSize()
                    .blur(20.dp)
                    .background(bgColor.copy(alpha = 0.50f), tabShape)
            )
            Surface(
                color = bgColor.copy(alpha = 0.85f),
                shape = tabShape,
                border = BorderStroke(1.dp, accentColor.copy(alpha = 0.20f)),
                modifier = Modifier.matchParentSize()
            ) {
                Row(
                    modifier = Modifier.fillMaxSize(),
                    horizontalArrangement = Arrangement.SpaceEvenly,
                    verticalAlignment = Alignment.CenterVertically,
                    content = tabContent
                )
            }
        }
    } else {
        Surface(
            color = bgColor.copy(alpha = 0.90f),
            shape = tabShape,
            border = BorderStroke(1.dp, accentColor.copy(alpha = 0.20f)),
            modifier = modifier
                .fillMaxWidth()
                .padding(horizontal = 12.dp, vertical = 4.dp)
                .navigationBarsPadding()
                .height(56.dp)
                .shadow(8.dp, tabShape)
        ) {
            Row(
                modifier = Modifier.fillMaxSize(),
                horizontalArrangement = Arrangement.SpaceEvenly,
                verticalAlignment = Alignment.CenterVertically,
                content = tabContent
            )
        }
    }
}
/**
 * 第一排：信息栏
 * 居中显示台标+频道名+分类，右侧收藏和信息按钮
 */
@Composable
internal fun PortraitInfoBarV2(viewModel: AppViewModel) {
    val currentChannel by viewModel.currentChannel.collectAsState()
    val favorites by viewModel.favorites.collectAsState()
    val currentIdx by viewModel.currentIdx.collectAsState()
    val oc = rememberPlayerOverlayColors()

    // 磨砂玻璃背景：半透明色（文字不模糊）
    val glassBg = oc.topBarBg.copy(alpha = 0.80f)

    Surface(
        color = glassBg,
        modifier = Modifier.fillMaxWidth()
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .height(44.dp)
                .padding(horizontal = 4.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            // 左侧：返回首页按钮
            IconButton(
                onClick = { viewModel.showHomeScreen() },
                modifier = Modifier.size(40.dp)
            ) {
                Icon(
                    imageVector = Icons.AutoMirrored.Filled.ArrowBack,
                    contentDescription = "返回首页",
                    tint = AptvAccent,
                    modifier = Modifier.size(24.dp)
                )
            }
            // 居中：台标 + 频道名 + 分类
            Row(
                verticalAlignment = Alignment.CenterVertically,
                modifier = Modifier.weight(1f),
                horizontalArrangement = Arrangement.Center
            ) {
                // 台标
                if (currentChannel != null && currentChannel!!.logo.isNotEmpty()) {
                    AsyncImage(
                        model = currentChannel!!.logo,
                        contentDescription = currentChannel!!.name,
                        modifier = Modifier
                            .size(28.dp)
                            .clip(RoundedCornerShape(4.dp)),
                        contentScale = ContentScale.Fit
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                }
                // 频道名
                Text(
                    text = currentChannel?.name ?: "未选择频道",
                    color = oc.textPrimary,
                    fontSize = 15.sp,
                    fontWeight = FontWeight.Medium,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
                // 分类
                if (currentChannel != null && currentChannel!!.group.isNotEmpty()) {
                    Spacer(modifier = Modifier.width(6.dp))
                    Surface(
                        color = AptvAccent.copy(alpha = 0.12f),
                        shape = RoundedCornerShape(4.dp)
                    ) {
                        Text(
                            text = currentChannel!!.group,
                            color = AptvAccent,
                            fontSize = 11.sp,
                            modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp),
                            maxLines = 1
                        )
                    }
                }
            }
            // 右侧：收藏 + 投屏 + 信息按钮
            IconButton(
                onClick = { viewModel.toggleFavorite() },
                modifier = Modifier.size(36.dp)
            ) {
                Icon(
                    imageVector = if (favorites.contains(currentIdx)) Icons.Default.Favorite else Icons.Default.FavoriteBorder,
                    contentDescription = "收藏",
                    tint = if (favorites.contains(currentIdx)) Color(0xFFFFC107) else oc.iconTint,
                    modifier = Modifier.size(22.dp)
                )
            }
            IconButton(
                onClick = { viewModel.showOsd("投屏", "功能开发中") },
                modifier = Modifier.size(36.dp)
            ) {
                Icon(
                    Icons.Default.Cast,
                    contentDescription = "投屏",
                    tint = oc.iconTint,
                    modifier = Modifier.size(22.dp)
                )
            }
            IconButton(
                onClick = { viewModel.toggleChannelInfo() },
                modifier = Modifier.size(36.dp)
            ) {
                Icon(
                    Icons.Default.Info,
                    contentDescription = "频道信息",
                    tint = oc.iconTint,
                    modifier = Modifier.size(22.dp)
                )
            }
        }
    }
}
/**
 * 第三排：播放控制栏
 * 播放/停止按钮 + 圆点进度条
 */
@Composable
internal fun PortraitControlsV2(viewModel: AppViewModel) {
    val oc = rememberPlayerOverlayColors()

    // 进度数据（1秒刷新）
    var tick by remember { mutableStateOf(0L) }
    LaunchedEffect(Unit) {
        while (true) {
            tick = System.currentTimeMillis()
            delay(1000L)
        }
    }
    val progressInfo = remember(tick, viewModel.playbackState.value, viewModel.currentChannel.value, viewModel.currentEpg.value) {
        viewModel.computeProgress()
    }
    var dragging by remember { mutableStateOf(false) }
    var dragPercent by remember { mutableStateOf(0f) }

    // 磨砂玻璃背景：半透明色（文字不模糊）
    val glassBg = oc.infoBarBg.copy(alpha = 0.80f)

    Surface(
        color = glassBg,
        modifier = Modifier.fillMaxWidth()
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 8.dp, vertical = 4.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            // 停止按钮（不需要暂停按钮）
            IconButton(
                onClick = { viewModel.stopPlay() },
                modifier = Modifier.size(36.dp)
            ) {
                Icon(
                    Icons.Default.Stop,
                    contentDescription = "停止",
                    tint = oc.iconTint,
                    modifier = Modifier.size(24.dp)
                )
            }
            // 播放工具按钮：截图/切片/EPG时间轴/搜索/提醒/续播/书签等
            IconButton(
                onClick = { viewModel.togglePlayerToolsPanel() },
                modifier = Modifier.size(36.dp)
            ) {
                Icon(
                    Icons.Default.MoreVert,
                    contentDescription = "播放工具",
                    tint = oc.iconTint,
                    modifier = Modifier.size(20.dp)
                )
            }
            // 播放器设置按钮：打开完整设置面板（含内核选择/VO/HWDEC/HDR 等）
            IconButton(
                onClick = { viewModel.togglePlayerSettings() },
                modifier = Modifier.size(36.dp)
            ) {
                Icon(
                    Icons.Default.Settings,
                    contentDescription = "播放器设置",
                    tint = oc.iconTint,
                    modifier = Modifier.size(20.dp)
                )
            }
            // 时间标签 - 开始
            Text(
                text = progressInfo.startLabel,
                color = oc.textSecondary,
                fontSize = 10.sp,
                modifier = Modifier.padding(start = 4.dp)
            )
            // 圆点进度条
            DotProgressBar(
                progress = if (dragging) dragPercent else (progressInfo.percent / 100f),
                onSeek = { percent ->
                    dragPercent = percent
                    dragging = true
                },
                onSeekEnd = {
                    viewModel.seekProgress(dragPercent * 100f)
                    dragging = false
                },
                accentColor = AptvAccent,
                trackColor = oc.trackInactive,
                modifier = Modifier
                    .weight(1f)
                    .padding(horizontal = 8.dp)
                    .height(24.dp)
            )
            // 时间标签 - 结束
            Text(
                text = progressInfo.endLabel,
                color = oc.textSecondary,
                fontSize = 10.sp
            )
        }
    }
}
/**
 * 圆点进度条：用 Canvas 绘制轨道 + 圆点指示器
 */
@Composable
private fun DotProgressBar(
    progress: Float,
    onSeek: (Float) -> Unit,
    onSeekEnd: () -> Unit,
    accentColor: Color,
    trackColor: Color,
    modifier: Modifier = Modifier
) {
    val density = androidx.compose.ui.platform.LocalDensity.current
    val trackHeight = with(density) { 3.dp.toPx() }
    val dotRadius = with(density) { 6.dp.toPx() }

    Canvas(
        modifier = modifier
            .fillMaxSize()
            .pointerInput(Unit) {
                detectTapGestures(
                    onTap = { offset ->
                        val w = size.width.toFloat()
                        if (w > 0) {
                            val percent = (offset.x / w).coerceIn(0f, 1f)
                            onSeek(percent)
                            onSeekEnd()
                        }
                    }
                )
            }
    ) {
        val canvasW = size.width
        val canvasH = size.height
        val centerY = canvasH / 2f
        val progressW = canvasW * progress

        // 背景轨道
        drawRoundRect(
            color = trackColor,
            topLeft = androidx.compose.ui.geometry.Offset(0f, centerY - trackHeight / 2),
            size = androidx.compose.ui.geometry.Size(canvasW, trackHeight),
            cornerRadius = androidx.compose.ui.geometry.CornerRadius(trackHeight / 2, trackHeight / 2)
        )
        // 已播放轨道
        if (progressW > 0) {
            drawRoundRect(
                color = accentColor,
                topLeft = androidx.compose.ui.geometry.Offset(0f, centerY - trackHeight / 2),
                size = androidx.compose.ui.geometry.Size(progressW, trackHeight),
                cornerRadius = androidx.compose.ui.geometry.CornerRadius(trackHeight / 2, trackHeight / 2)
            )
        }
        // 圆点指示器
        drawCircle(
            color = accentColor,
            radius = dotRadius,
            center = androidx.compose.ui.geometry.Offset(progressW.coerceIn(0f, canvasW), centerY)
        )
    }
}
