package com.iptv.scanner.editor.pro.ui

import android.app.Activity
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInHorizontally
import androidx.compose.animation.slideOutHorizontally
import androidx.compose.animation.core.tween
import androidx.compose.runtime.DisposableEffect

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
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
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons

import androidx.compose.material.icons.filled.Stop
import androidx.compose.material.icons.automirrored.filled.Backspace
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Slider
import androidx.compose.material3.SliderDefaults
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.derivedStateOf
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.blur
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.foundation.gestures.detectTapGestures

import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalContext
import androidx.compose.runtime.CompositionLocalProvider
import coil.compose.AsyncImage
import com.iptv.scanner.editor.pro.data.IptvChannel
import com.iptv.scanner.editor.pro.data.IptvEpgProgram
import com.iptv.scanner.editor.pro.player.PlayMode
import com.iptv.scanner.editor.pro.player.PlaybackState
import com.iptv.scanner.editor.pro.player.ProgressHelper
import com.iptv.scanner.editor.pro.ui.theme.rememberPlayerOverlayColors
import com.iptv.scanner.editor.pro.ui.theme.tvFocusBorder
import kotlinx.coroutines.delay
import kotlin.math.abs


private val TV_BOTTOM_BAR_HEIGHT = 100.dp

/**
 * 根据点击位置计算多画面视口索引。
 * DUAL: 左=0, 右=1
 * QUAD: 左上=0, 右上=1, 左下=2, 右下=3
 * NINE: 3x3网格, 左上=0, ... 右下=8
 */
private fun computeViewportIndex(
    x: Float, y: Float, w: Float, h: Float, layout: MultiViewLayout
): Int {
    if (w <= 0 || h <= 0) return -1
    return when (layout) {
        MultiViewLayout.DUAL -> if (x < w / 2f) 0 else 1
        MultiViewLayout.QUAD -> {
            val col = if (x < w / 2f) 0 else 1
            val row = if (y < h / 2f) 0 else 1
            row * 2 + col
        }
        MultiViewLayout.NINE -> {
            val col = (x / (w / 3f)).toInt().coerceIn(0, 2)
            val row = (y / (h / 3f)).toInt().coerceIn(0, 2)
            row * 3 + col
        }
        MultiViewLayout.SINGLE -> 0
    }
}

// 侧边栏风格配色
private val SIDEBAR_GRADIENT_START = Color(0xFF036D80)
private val SIDEBAR_GRADIENT_END = Color(0xFF052D49)
private val ACCENT_GREEN = Color(0xFF70C439)
private val ACCENT_CYAN = Color(0xFF00BCD4)
private val ICON_BG = Color(0x32FFFFFF)
private val TIME_BG = Color(0x26000000)

@Composable
fun TvPlayerLayout(
    viewModel: AppViewModel,
    primaryPlayer: @Composable () -> Unit,
    videoAspectRatio: Float
) {
    val oc = rememberPlayerOverlayColors()
    val sidebarVisible by viewModel.landscapeSidebarVisible.collectAsState()
    val controlsVisible by viewModel.controlsVisible.collectAsState()
    val controlsPinned by viewModel.controlsPinned.collectAsState()
    val displayInfo by viewModel.channelDisplayInfo.collectAsState()
    val paused by viewModel.mpv.paused.collectAsState()
    val fileLoaded by viewModel.mpv.fileLoaded.collectAsState()
    val videoWidth by viewModel.mpv.videoWidth.collectAsState()
    val videoHeight by viewModel.mpv.videoHeight.collectAsState()
    val showExitCatchup by viewModel.showExitCatchup.collectAsState()
    val playbackState by viewModel.playbackState.collectAsState()
    val currentEpg by viewModel.currentEpg.collectAsState()
    val channelNumberInput by viewModel.channelNumberInput.collectAsState()
    val channelNumDisplay by viewModel.channelNumDisplay.collectAsState()
    val osdShowTime by viewModel.osdShowTime.collectAsState()
    val osdShowNetSpeed by viewModel.osdShowNetSpeed.collectAsState()

    val currentProgram = remember(currentEpg) {
        ProgressHelper.findCurrentProgram(currentEpg, System.currentTimeMillis())
    }

    val showOverlays by derivedStateOf { sidebarVisible || controlsVisible || controlsPinned }
    val multiViewState by viewModel.multiViewState.collectAsState()
    val multiViewStateUpdated = rememberUpdatedState(multiViewState)

    // 横屏全屏：隐藏系统状态栏和导航栏（滑动可临时唤出）
    val context = LocalContext.current
    DisposableEffect(Unit) {
        val activity = context as? Activity
        val window = activity?.window
        val controller = window?.let {
            androidx.core.view.WindowCompat.getInsetsController(it, it.decorView)
        }
        controller?.systemBarsBehavior =
            androidx.core.view.WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
        controller?.hide(androidx.core.view.WindowInsetsCompat.Type.systemBars())
        onDispose {
            controller?.show(androidx.core.view.WindowInsetsCompat.Type.systemBars())
        }
    }

    // DPI自适应缩放：以TV横屏720dp高度为基准，手机横屏高度不足时缩小UI。
    // 下限 0.55→0.70：0.55 时 Material 48dp 最小触控目标实际仅 ~26dp、
    // 28dp 图标按钮 ~15dp，触控体验不可用；0.70 下视频区缩小有限但
    // 触控目标恢复到可点范围（TV 端 screenHeightDp≥720 不受影响）。
    val configuration = LocalConfiguration.current
    val origDensity = LocalDensity.current
    val dpiScale = (configuration.screenHeightDp / 720f).coerceIn(0.70f, 1f)
    val scaledDensity = Density(origDensity.density * dpiScale, origDensity.fontScale)

    Box(modifier = Modifier.fillMaxSize()) {
        primaryPlayer()

        // 触控分区由 Activity dispatchTouchEvent 处理（Compose 无法拦截 AndroidView 触控）
        // 多画面模式下 dispatchTouchEvent 跳过分区toggle，触控直接传递给 MultiViewOverlay

        CompositionLocalProvider(LocalDensity provides scaledDensity) {
        // 侧边栏风格：右上角时间组（始终显示）
        if (osdShowTime) {
            TvTimeGroup(
                modifier = Modifier.align(Alignment.TopEnd),
                channelNumberInput = channelNumberInput,
                channelNumDisplay = channelNumDisplay
            )
        } else if (channelNumberInput.isNotEmpty() || channelNumDisplay.isNotEmpty()) {
            // 即使关闭时间显示，数字选台/切台时仍显示频道号
            TvTimeGroup(
                modifier = Modifier.align(Alignment.TopEnd),
                channelNumberInput = channelNumberInput,
                channelNumDisplay = channelNumDisplay
            )
        }

        // 侧边栏风格：右下角网速显示
        if (fileLoaded && !sidebarVisible && osdShowNetSpeed) {
            TvNetSpeed(
                modifier = Modifier.align(Alignment.BottomEnd),
                mpv = viewModel.mpv
            )
        }


        AnimatedVisibility(
            visible = sidebarVisible,
            enter = slideInHorizontally(initialOffsetX = { -it / 2 }, animationSpec = tween(150)),
            exit = slideOutHorizontally(targetOffsetX = { -it / 2 }, animationSpec = tween(120)),
            modifier = Modifier.align(Alignment.CenterStart)
        ) {
            val isAndroid12Plus = android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.S
            Box(modifier = Modifier.fillMaxHeight().fillMaxWidth(0.82f).padding(start = 16.dp, top = 10.dp, bottom = TV_BOTTOM_BAR_HEIGHT)) {
                TvUnifiedPanel(viewModel = viewModel)
            }
        }

        Box(
            modifier = Modifier
                .align(Alignment.BottomCenter)
                .width(820.dp)
                .padding(vertical = 8.dp)
        ) {
            AnimatedVisibility(
                visible = showOverlays && !sidebarVisible,
                enter = fadeIn(),
                exit = fadeOut()
            ) {
                TvBottomBar(
                    viewModel = viewModel,
                    displayInfo = displayInfo,
                    paused = paused,
                    fileLoaded = fileLoaded,
                    videoWidth = videoWidth,
                    videoHeight = videoHeight,
                    showExitCatchup = showExitCatchup,
                    playbackMode = playbackState.mode,
                    currentProgram = currentProgram,
                    epgList = currentEpg
                )
            }
        }
        } // CompositionLocalProvider
    }
}

@Composable
private fun TvTimeGroup(modifier: Modifier = Modifier, channelNumberInput: String = "", channelNumDisplay: String = "") {
    var tick by remember { mutableStateOf(0L) }
    LaunchedEffect(Unit) { while (true) { tick = System.currentTimeMillis(); delay(1000L) } }
    val dateText = remember(tick) {
        val fmt = java.text.SimpleDateFormat("MM/dd EE", java.util.Locale.CHINESE)
        fmt.format(java.util.Date(tick))
    }
    val timeText = remember(tick) {
        val fmt = java.text.SimpleDateFormat("HH:mm:ss", java.util.Locale.getDefault())
        fmt.format(java.util.Date(tick))
    }
    Column(
        modifier = modifier.padding(top = 15.dp, end = 15.dp),
        horizontalAlignment = Alignment.End
    ) {
        // 侧边栏风格：数字选台时显示大字号频道号
        if (channelNumberInput.isNotEmpty()) {
            Surface(
                color = TIME_BG,
                shape = RoundedCornerShape(8.dp)
            ) {
                Text(
                    text = channelNumberInput,
                    color = ACCENT_GREEN,
                    fontSize = 72.sp,
                    fontWeight = FontWeight.Bold,
                    modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp)
                )
            }
            Spacer(modifier = Modifier.height(6.dp))
        } else if (channelNumDisplay.isNotEmpty()) {
            // 切台时显示频道号
            Surface(
                color = TIME_BG,
                shape = RoundedCornerShape(8.dp)
            ) {
                Text(
                    text = channelNumDisplay,
                    color = ACCENT_GREEN,
                    fontSize = 48.sp,
                    fontWeight = FontWeight.Bold,
                    modifier = Modifier.padding(horizontal = 12.dp, vertical = 2.dp)
                )
            }
            Spacer(modifier = Modifier.height(6.dp))
        }
        Surface(
            color = TIME_BG,
            shape = RoundedCornerShape(8.dp)
        ) {
            Column(
                modifier = Modifier.padding(horizontal = 10.dp, vertical = 4.dp),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                Text(text = dateText, color = Color.White, fontSize = 11.sp)
                Text(text = timeText, color = Color.White, fontSize = 14.sp, fontWeight = FontWeight.Medium)
            }
        }
    }
}

@Composable
private fun TvNetSpeed(modifier: Modifier = Modifier, mpv: com.iptv.scanner.editor.pro.player.Player) {
    var tick by remember { mutableStateOf(0L) }
    LaunchedEffect(Unit) { while (true) { tick = System.currentTimeMillis(); delay(1000L) } }
    val speedText = remember(tick) {
        val cacheSpeed = mpv.getPropertyDouble("cache-speed") ?: 0.0
        val videoBitrate = mpv.getPropertyInt("video-bitrate") ?: 0
        if (cacheSpeed > 0) {
            formatNetSpeed(cacheSpeed.toLong())
        } else if (videoBitrate > 0) {
            formatNetSpeed(videoBitrate.toLong() / 8)
        } else {
            null
        }
    }
    if (speedText != null) {
        Surface(
            color = TIME_BG,
            shape = RoundedCornerShape(4.dp),
            modifier = modifier.padding(bottom = 12.dp, end = 15.dp)
        ) {
            Text(
                text = speedText,
                color = Color.White,
                fontSize = 11.sp,
                modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp)
            )
        }
    }
}

private fun formatNetSpeed(bytesPerSec: Long): String {
    if (bytesPerSec <= 0) return ""
    val kb = bytesPerSec / 1024.0
    val mb = kb / 1024.0
    return when {
        mb >= 1.0 -> "%.1f MB/s".format(mb)
        kb >= 1.0 -> "%.0f KB/s".format(kb)
        else -> "$bytesPerSec B/s"
    }
}


@Composable
private fun TvBottomBar(
    viewModel: AppViewModel,
    displayInfo: ChannelDisplayInfo,
    paused: Boolean,
    fileLoaded: Boolean,
    videoWidth: Int,
    videoHeight: Int,
    showExitCatchup: Boolean,
    playbackMode: PlayMode,
    currentProgram: IptvEpgProgram?,
    epgList: List<IptvEpgProgram>
) {
    val oc = rememberPlayerOverlayColors()
    val mpv = viewModel.mpv

    var tick by remember { mutableStateOf(0L) }
    LaunchedEffect(Unit) { while (true) { tick = System.currentTimeMillis(); delay(1000L) } }

    val mediaInfoBadges = if (fileLoaded) remember(tick, videoWidth, videoHeight) {
        buildTvMediaBadges(mpv, videoWidth, videoHeight, viewModel.getCurrentPlaybackUrl())
    } else emptyList()

    val isAndroid12Plus = android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.S
    val timeFmt = remember { java.text.SimpleDateFormat("HH:mm", java.util.Locale.getDefault()) }
    val dateFmt = remember { java.text.SimpleDateFormat("MM月dd日 EE", java.util.Locale.CHINESE) }
    val fullTimeFmt = remember { java.text.SimpleDateFormat("HH:mm:ss", java.util.Locale.getDefault()) }

    // 侧边栏风格状态标签
    val statusTag = when {
        !fileLoaded -> null
        playbackMode == PlayMode.TIMESHIFT -> "时移" to Color(0xFF2979FF)
        showExitCatchup -> "回看" to Color(0xFFFFA500)
        else -> "直播" to ACCENT_GREEN
    }

    // 下一节目
    val nextProgram = remember(currentProgram, epgList) {
        if (currentProgram != null && currentProgram.stopTs > 0) {
            epgList.firstOrNull { it.startTs >= currentProgram.stopTs && it.title.isNotEmpty() }
        } else null
    }

    // 距结束时间
    val remainText = remember(tick, currentProgram) {
        if (currentProgram != null && currentProgram.stopTs > 0) {
            val nowSec = tick / 1000L
            val diff = currentProgram.stopTs - nowSec
            if (diff > 0) {
                val min = diff / 60
                if (min > 0) "距结束 ${min}分钟" else "距结束 ${diff}秒"
            } else null
        } else null
    }

    Box {
        if (isAndroid12Plus) {
            Box(modifier = Modifier.matchParentSize().clip(RoundedCornerShape(8.dp)).blur(15.dp).background(Color(0x881a1a2e)))
        }
        Surface(
            color = if (isAndroid12Plus) Color(0xE61a1a2e) else Color(0xF01a1a2e),
            shape = RoundedCornerShape(8.dp)
        ) {
            Column(modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 6.dp)) {
                // 第1行：台标 + 频道号 + 频道名 + spacer + 状态标签 + 技术标签组
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(
                        modifier = Modifier.size(48.dp, 36.dp).clip(RoundedCornerShape(4.dp)).background(ICON_BG),
                        contentAlignment = Alignment.Center
                    ) {
                        if (displayInfo.logo.isNotEmpty()) {
                            AsyncImage(model = displayInfo.logo, contentDescription = displayInfo.name, modifier = Modifier.fillMaxSize().padding(3.dp), contentScale = ContentScale.Fit)
                        } else {
                            Text(
                                text = displayInfo.name.take(2).ifEmpty { "·" },
                                color = Color.White,
                                fontSize = 14.sp,
                                fontWeight = FontWeight.Bold
                            )
                        }
                    }
                    Spacer(modifier = Modifier.width(8.dp))
                    if (displayInfo.idx >= 0) {
                        Text(
                            text = String.format("%03d", displayInfo.idx + 1),
                            color = Color(0xFF4a90d9),
                            fontSize = 13.sp,
                            fontWeight = FontWeight.Medium
                        )
                        Spacer(modifier = Modifier.width(4.dp))
                        Box(modifier = Modifier.width(1.dp).height(12.dp).background(Color(0x60FFFFFF)))
                        Spacer(modifier = Modifier.width(4.dp))
                    }
                    Text(
                        text = displayInfo.name.ifEmpty { "未选择频道" },
                        color = if (displayInfo.idx >= 0) oc.textPrimary else oc.textSecondary,
                        fontSize = 16.sp, fontWeight = FontWeight.Bold,
                        maxLines = 1, overflow = TextOverflow.Ellipsis
                    )
                    Spacer(modifier = Modifier.weight(1f))
                    if (statusTag != null) {
                        Surface(color = statusTag.second.copy(alpha = 0.25f), shape = RoundedCornerShape(3.dp)) {
                            Text(text = statusTag.first, color = statusTag.second, fontSize = 10.sp, fontWeight = FontWeight.Medium, modifier = Modifier.padding(horizontal = 5.dp, vertical = 1.dp))
                        }
                        Spacer(modifier = Modifier.width(4.dp))
                    }
                    if (paused && fileLoaded) {
                        Surface(color = Color(0x30FFFFFF), shape = RoundedCornerShape(3.dp)) {
                            Text("暂停", color = Color.White, fontSize = 10.sp, modifier = Modifier.padding(horizontal = 4.dp, vertical = 1.dp))
                        }
                        Spacer(modifier = Modifier.width(4.dp))
                    }
                    mediaInfoBadges.forEach { info: String ->
                        Surface(color = Color(0x30FFFFFF), shape = RoundedCornerShape(3.dp)) {
                            Text(text = info, color = Color(0xCCFFFFFF), fontSize = 10.sp, modifier = Modifier.padding(horizontal = 4.dp, vertical = 1.dp))
                        }
                        Spacer(modifier = Modifier.width(3.dp))
                    }
                }

                // 第2行：当前节目时间范围 + 节目名 + 进度条(细线) + 时间戳 + 距结束 + 按钮
                Spacer(modifier = Modifier.height(4.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                        if (currentProgram != null && currentProgram.title.isNotEmpty()) {
                            if (currentProgram.stopTs > 0) {
                                val timeRange = remember(currentProgram) {
                                    val start = timeFmt.format(java.util.Date(currentProgram.startTs * 1000L))
                                    val end = timeFmt.format(java.util.Date(currentProgram.stopTs * 1000L))
                                    "$start-$end"
                                }
                                Text(text = timeRange, color = Color(0xFFa0a0a0), fontSize = 12.sp)
                                Spacer(modifier = Modifier.width(6.dp))
                            }
                            Text(
                                text = currentProgram.title,
                                color = oc.textPrimary,
                                fontSize = 13.sp,
                                maxLines = 1, overflow = TextOverflow.Ellipsis,
                                modifier = Modifier.weight(1f)
                            )
                        } else {
                            Text(
                                text = "精彩节目",
                                color = oc.textSecondary.copy(alpha = 0.6f),
                                fontSize = 13.sp,
                                modifier = Modifier.weight(1f)
                            )
                        }
                        val timePos by mpv.timePos.collectAsState()
                        val duration by mpv.duration.collectAsState()
                        val progress = remember(tick, timePos, duration, displayInfo, currentProgram) {
                            val fakeChannel = if (displayInfo.idx >= 0) IptvChannel(
                                name = displayInfo.name,
                                url = if (displayInfo.isLocal) "file:///local" else "http://live",
                                group = displayInfo.group,
                                logo = displayInfo.logo
                            ) else null
                            ProgressHelper.computeProgress(
                                viewModel.playbackState.value,
                                fakeChannel, currentProgram, timePos, duration
                            )
                        }
                        val hasEpg = currentProgram != null && currentProgram.stopTs > 0
                        if (hasEpg) {
                            Spacer(modifier = Modifier.width(8.dp))
                            // 细线进度条
                            Box(
                                modifier = Modifier
                                    .width(180.dp)
                                    .height(3.dp)
                                    .clip(RoundedCornerShape(1.5.dp))
                                    .background(Color(0x30FFFFFF))
                            ) {
                                Box(
                                    modifier = Modifier
                                        .fillMaxHeight()
                                        .width(with(androidx.compose.ui.platform.LocalDensity.current) { (180.dp * (progress.percent / 100f)).toPx().toDp() })
                                        .clip(RoundedCornerShape(1.5.dp))
                                        .background(Color(0xFF4a90d9))
                                )
                            }
                            Spacer(modifier = Modifier.width(8.dp))
                        }
                        val posText = remember(tick, timePos, playbackMode, showExitCatchup) {
                            if (playbackMode == PlayMode.LIVE && !showExitCatchup) {
                                fullTimeFmt.format(java.util.Date(tick))
                            } else if (timePos > 0) {
                                fullTimeFmt.format(java.util.Date((timePos * 1000L).toLong()))
                            } else ""
                        }
                        if (posText.isNotEmpty()) {
                            Text(text = posText, color = Color(0xFFa0a0a0), fontSize = 11.sp)
                        }
                        if (remainText != null) {
                            Spacer(modifier = Modifier.width(6.dp))
                            Text(text = remainText, color = Color(0xFF4a90d9), fontSize = 10.sp)
                        }
                        if (showExitCatchup) {
                            Spacer(modifier = Modifier.width(4.dp))
                            IconButton(onClick = { viewModel.exitCatchup() }, modifier = Modifier.size(28.dp).tvFocusBorder()) {
                                Icon(Icons.AutoMirrored.Filled.Backspace, "退出回看", tint = oc.accent, modifier = Modifier.size(14.dp))
                            }
                        }
                        Spacer(modifier = Modifier.width(2.dp))
                        IconButton(onClick = { viewModel.stopPlay() }, modifier = Modifier.size(28.dp).tvFocusBorder()) {
                            Icon(Icons.Default.Stop, "停止", tint = oc.iconTint, modifier = Modifier.size(14.dp))
                        }
                    }

                // 第3行：下一节目时间范围 + 下一节目名
                run {
                    val hasNext = nextProgram != null
                    Spacer(modifier = Modifier.height(2.dp))
                    Row(verticalAlignment = Alignment.CenterVertically) {
                            if (hasNext) {
                                val nextStart = remember(nextProgram) {
                                    timeFmt.format(java.util.Date(nextProgram!!.startTs * 1000L))
                                }
                                val nextEnd = remember(nextProgram) {
                                    timeFmt.format(java.util.Date(nextProgram!!.stopTs * 1000L))
                                }
                                Text(text = "$nextStart-$nextEnd", color = Color(0xFFa0a0a0), fontSize = 12.sp)
                                Spacer(modifier = Modifier.width(6.dp))
                                Text(
                                    text = nextProgram!!.title,
                                    color = Color(0xB3FFFFFF),
                                    fontSize = 13.sp,
                                    maxLines = 1, overflow = TextOverflow.Ellipsis,
                                    modifier = Modifier.weight(1f)
                                )
                            } else {
                                val dateText = remember(tick) { dateFmt.format(java.util.Date(tick)) }
                                Text(
                                    text = dateText,
                                    color = Color(0xFFa0a0a0),
                                    fontSize = 12.sp,
                                    modifier = Modifier.weight(1f)
                                )
                            }
                        }
            }
        }
    }
}

}  // TvBottomBar


internal fun buildTvMediaBadges(mpv: com.iptv.scanner.editor.pro.player.Player, videoWidth: Int, videoHeight: Int, playbackUrl: String = ""): List<String> {
    val result = mutableListOf<String>()
    val mediaInfo = try { mpv.getMediaInfo() } catch (_: Exception) { emptyMap() }
    // 视频编码
    mediaInfo["videoCodec"]?.takeIf { it.isNotEmpty() && it != "null" }?.let { codec ->
        result.add(codec.removePrefix("video/").removePrefix("audio/").uppercase())
    }
    // 分辨率
    if (videoWidth > 0 && videoHeight > 0) {
        result.add(when { videoWidth >= 3800 -> "4K"; videoWidth >= 1900 -> "1080P"; videoWidth >= 1200 -> "720P"; else -> "${videoHeight}P" })
    }
    // 视频比特率
    val videoBitrate = try { mpv.getPropertyInt("video-bitrate") } catch (_: Exception) { null }
    if (videoBitrate != null && videoBitrate > 0) {
        val kbps = videoBitrate / 1000
        if (kbps >= 1000) {
            result.add("%.1fMbps".format(kbps / 1000.0))
        } else {
            result.add("${kbps}kbps")
        }
    }
    // HDR
    val gamma = mediaInfo["videoGamma"]
    val primaries = mediaInfo["videoPrimaries"]
    when {
        gamma == "hlg" -> result.add("HLG")
        gamma == "pq" -> result.add("HDR10")
        primaries == "bt.2020" -> result.add("HDR")
    }
    // 音频编码
    mediaInfo["audioCodec"]?.takeIf { it.isNotEmpty() && it != "null" }?.let { codec ->
        result.add(codec.removePrefix("audio/").uppercase())
    }
    // 音频声道
    val channels = try { mpv.getPropertyInt("audio-params/channels") } catch (_: Exception) { null }
    if (channels != null && channels > 0) {
        result.add(when (channels) { 1 -> "单声道"; 2 -> "立体声"; 6 -> "5.1ch"; 8 -> "7.1ch"; else -> "${channels}ch" })
    }
    // 帧率
    mediaInfo["fps"]?.takeIf { it.isNotEmpty() && it != "null" && it != "0" && it != "0.000" }?.let { fps ->
        val fpsVal = fps.toFloatOrNull()
        result.add(if (fpsVal != null) "${fpsVal.toInt()}fps" else "${fps}fps")
    }
    // 容器格式
    mediaInfo["containerFormat"]?.takeIf { it.isNotEmpty() && it != "null" }?.let { fmt ->
        val short = fmt.substringAfter("/").substringAfterLast(".")
        if (short.isNotEmpty()) result.add(short.uppercase())
    }
    // 协议
    if (playbackUrl.isNotEmpty()) {
        val proto = playbackUrl.substringBefore("://").lowercase()
        when (proto) {
            "http", "https" -> result.add("HTTP")
            "rtsp" -> result.add("RTSP")
            "udp", "rtp" -> result.add("UDP")
            "file" -> result.add("LOCAL")
        }
    }
    return result.take(8)
}
