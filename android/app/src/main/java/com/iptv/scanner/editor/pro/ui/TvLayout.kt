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
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Pause
import androidx.compose.material.icons.filled.SkipNext
import androidx.compose.material.icons.filled.SkipPrevious
import androidx.compose.material.icons.filled.FullscreenExit
import androidx.compose.material.icons.automirrored.filled.Backspace
import androidx.compose.material3.Icon
import androidx.compose.material3.Slider
import androidx.compose.material3.SliderDefaults
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
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
import com.iptv.scanner.editor.pro.ui.theme.GlassPanel
import com.iptv.scanner.editor.pro.ui.theme.tvFocusBorder
import kotlinx.coroutines.delay
import kotlin.math.abs

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

// 侧边栏风格配色（主色统一为竖屏 APTV 橙红 AptvAccent）
private val SIDEBAR_GRADIENT_START = Color(0xFF036D80)
private val SIDEBAR_GRADIENT_END = Color(0xFF052D49)
private val ICON_BG = Color(0x32FFFFFF)
private val TIME_BG = Color(0x26000000)
/** 底栏可读性底色：玻璃霜层上垫深色底 */
// 底栏不再叠加实底 scrim：深色可读性由玻璃材质 overlayDark 暗玻璃霜层提供
/** 行间分隔条颜色 */
private val TV_ROW_DIVIDER = Color(0x1FFFFFFF)

@Composable
fun TvPlayerLayout(
    viewModel: AppViewModel,
    primaryPlayer: @Composable () -> Unit,
    videoAspectRatio: Float,
    homeOverlay: Boolean = false
) {
    val oc = rememberPlayerOverlayColors()
    // 横屏分屏模式（默认开启）：左视频+控制条 / 右常驻面板。
    // 多画面模式保持全屏（MultiViewOverlay 需要整个屏幕网格）。
    val splitModePref by viewModel.landscapeSplitMode.collectAsState()
    val multiActive by viewModel.multiViewState.collectAsState()
    val useSplitTarget = splitModePref && !multiActive.active

    // movableContent 视频节点（AndroidView）跨布局迁移必须两帧完成：
    // 同帧「移除旧布局树 + 插入新布局树 + 搬迁节点」会触发 Compose
    // CopyNodesToNewAnchorLocation → insertAt「already has a parent」崩溃
    // （ACRA 实测 IllegalStateException at LayoutNode.insertAt）。
    // 切换时第一帧先摘下视频节点渲染空布局，下一帧再放入新布局；
    // movable 完全离开组合后状态释放，重新放入即全新节点，不会再撞旧父节点。
    val useSplitState = remember { androidx.compose.runtime.mutableStateOf(useSplitTarget) }
    val playerPlacedState = remember { androidx.compose.runtime.mutableStateOf(true) }
    androidx.compose.runtime.LaunchedEffect(useSplitTarget) {
        if (useSplitState.value != useSplitTarget) {
            playerPlacedState.value = false
            useSplitState.value = useSplitTarget
            androidx.compose.runtime.withFrameNanos { }
        }
        playerPlacedState.value = true
    }
    val useSplit = useSplitState.value

    if (useSplit) {
        // ---- 分屏布局：系统栏保持可见（状态栏时间/电量可读） ----
        val context = LocalContext.current
        DisposableEffect(Unit) {
            val activity = context as? Activity
            val controller = activity?.window?.let {
                androidx.core.view.WindowCompat.getInsetsController(it, it.decorView)
            }
            controller?.systemBarsBehavior =
                androidx.core.view.WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
            controller?.show(androidx.core.view.WindowInsetsCompat.Type.systemBars())
            onDispose { }
        }
        // DPI 自适应缩放（基准 900dp、下限 0.60，与横屏首页一致）：
        // 手机横屏/小平板缩小分屏 UI 提升内容密度，TV 端 ≥900dp 不缩放
        val splitOrigDensity = LocalDensity.current
        val splitDpiScale = (LocalConfiguration.current.screenHeightDp / 900f).coerceIn(0.60f, 1f)
        androidx.compose.runtime.CompositionLocalProvider(
            LocalDensity provides Density(splitOrigDensity.density * splitDpiScale, splitOrigDensity.fontScale)
        ) {
            // 橙红主色作用域：分屏页 accent（播放按钮等）与首页/竖屏 APTV 风格统一
            androidx.compose.runtime.CompositionLocalProvider(LocalAptvStyle provides true) {
                TvSplitLayout(
                    viewModel = viewModel,
                    primaryPlayer = { if (playerPlacedState.value) primaryPlayer() }
                )
            }
        }
        return
    }

    // ---- 以下为传统全屏布局（保持不变） ----
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

    // 横屏全屏：隐藏系统状态栏和导航栏（滑动可临时唤出）；首页覆盖时保持可见
    val context = LocalContext.current
    val bottomBarStyle by viewModel.bottomBarStyle.collectAsState()
    DisposableEffect(homeOverlay) {
        val activity = context as? Activity
        val window = activity?.window
        val controller = window?.let {
            androidx.core.view.WindowCompat.getInsetsController(it, it.decorView)
        }
        controller?.systemBarsBehavior =
            androidx.core.view.WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
        if (homeOverlay) {
            controller?.show(androidx.core.view.WindowInsetsCompat.Type.systemBars())
        } else {
            controller?.hide(androidx.core.view.WindowInsetsCompat.Type.systemBars())
        }
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
        if (playerPlacedState.value) primaryPlayer()

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
            // 底栏与侧边栏互斥显示（showOverlays && !sidebarVisible），无需预留底栏高度，
            // 侧边栏直接贴到屏幕底部，避免底部空出一大块
            Box(modifier = Modifier.fillMaxHeight().fillMaxWidth(0.82f).padding(start = 16.dp, top = 10.dp, bottom = 10.dp)) {
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
                    epgList = currentEpg,
                    style = bottomBarStyle
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
                    color = AptvAccent,
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
                    color = AptvAccent,
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
    epgList: List<IptvEpgProgram>,
    style: Int = 0
) {
    // 底栏呼出时把焦点落到播放/暂停键：DPAD 直接在底栏内移动焦点（Activity dispatchKeyEvent 已放行），
    // 不再需要 TAB 键临时导航。AnimatedVisibility 内每次呼出都是新组合，effect 重新执行。
    val barFocus = remember { FocusRequester() }
    LaunchedEffect(Unit) {
        kotlinx.coroutines.delay(80)
        runCatching { barFocus.requestFocus() }
    }
    when (style) {
        1 -> TvBottomBarStyleB(viewModel, displayInfo, paused, fileLoaded, videoWidth, videoHeight, showExitCatchup, playbackMode, currentProgram, epgList, barFocus)
        2 -> TvBottomBarStyleC(viewModel, displayInfo, paused, fileLoaded, videoWidth, videoHeight, showExitCatchup, playbackMode, currentProgram, epgList, barFocus)
        3 -> TvBottomBarStyleD(viewModel, displayInfo, paused, fileLoaded, videoWidth, videoHeight, showExitCatchup, playbackMode, currentProgram, epgList, barFocus)
        else -> TvBottomBarStyleA(viewModel, displayInfo, paused, fileLoaded, videoWidth, videoHeight, showExitCatchup, playbackMode, currentProgram, epgList, barFocus)
    }
}

/** 共享：计算播放进度（直播有 EPG 用节目时间轴，点播用 timePos/duration），无进度返回 null */
private fun computeTvBarProgress(currentProgram: IptvEpgProgram?, timePos: Double, duration: Double): Float? {
    if (currentProgram != null && currentProgram.startTs > 0 && currentProgram.stopTs > currentProgram.startTs) {
        val nowSec = System.currentTimeMillis() / 1000L
        val total = currentProgram.stopTs - currentProgram.startTs
        val elapsed = (nowSec - currentProgram.startTs).coerceIn(0L, total)
        return elapsed.toFloat() / total
    }
    if (duration > 0 && timePos > 0) return (timePos / duration).toFloat().coerceIn(0f, 1f)
    return null
}

@Composable
private fun TvBottomBarStyleA(
    viewModel: AppViewModel,
    displayInfo: ChannelDisplayInfo,
    paused: Boolean,
    fileLoaded: Boolean,
    videoWidth: Int,
    videoHeight: Int,
    showExitCatchup: Boolean,
    playbackMode: PlayMode,
    currentProgram: IptvEpgProgram?,
    epgList: List<IptvEpgProgram>,
    barFocus: FocusRequester? = null
) {
    val mpv = viewModel.mpv
    val liquidGlass by viewModel.liquidGlass.collectAsState()

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
        else -> "直播" to AptvAccent
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

    GlassPanel(liquidGlass = liquidGlass, cornerRadius = 8.dp, overlayDark = true) {
            // oc 必须在 GlassPanel（DarkOverlayTheme 作用域）内获取：底栏是暗玻璃覆盖层，
            // 浅色主题下若在外层取色会得到黑字/黑图标，落在暗玻璃上不可读
            val oc = rememberPlayerOverlayColors()
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 20.dp, vertical = 10.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                // 台标：置于底栏左侧，随三行内容整体垂直居中（不再嵌在第1行上部）
                // 104dp 宽：适配长条状台标（如 CCTV 组合标），方形标 ContentScale.Fit 自动居中
                Box(
                    modifier = Modifier.size(104.dp, 50.dp).clip(RoundedCornerShape(6.dp)).background(ICON_BG),
                    contentAlignment = Alignment.Center
                ) {
                    if (displayInfo.logo.isNotEmpty()) {
                        AsyncImage(model = displayInfo.logo, contentDescription = displayInfo.name, modifier = Modifier.fillMaxSize().padding(3.dp), contentScale = ContentScale.Fit)
                    } else {
                        Text(
                            text = displayInfo.name.take(2).ifEmpty { "·" },
                            color = Color.White,
                            fontSize = 15.sp,
                            fontWeight = FontWeight.Bold
                        )
                    }
                }
                Spacer(modifier = Modifier.width(14.dp))
                // 竖分隔条：台标列与右侧信息列分隔
                Box(modifier = Modifier.width(1.dp).height(50.dp).background(TV_ROW_DIVIDER))
                Spacer(modifier = Modifier.width(14.dp))
                // 右侧信息列：三行（频道信息 / 当前节目+进度 / 下一档节目）
                Column(modifier = Modifier.weight(1f)) {
                // 第1行：频道号 + 频道名 + spacer + 状态标签 + 技术标签组
                Row(verticalAlignment = Alignment.CenterVertically) {
                    if (displayInfo.idx >= 0) {
                        Text(
                            text = String.format("%03d", displayInfo.idx + 1),
                            color = AptvAccent,
                            fontSize = 14.sp,
                            fontWeight = FontWeight.Medium
                        )
                        Spacer(modifier = Modifier.width(5.dp))
                        Box(modifier = Modifier.width(1.dp).height(13.dp).background(Color(0x60FFFFFF)))
                        Spacer(modifier = Modifier.width(5.dp))
                    }
                    Text(
                        text = displayInfo.name.ifEmpty { "未选择频道" },
                        color = if (displayInfo.idx >= 0) oc.textPrimary else oc.textSecondary,
                        fontSize = 18.sp, fontWeight = FontWeight.Bold,
                        maxLines = 1, overflow = TextOverflow.Ellipsis
                    )
                    Spacer(modifier = Modifier.weight(1f))
                    if (statusTag != null) {
                        Surface(color = statusTag.second.copy(alpha = 0.25f), shape = RoundedCornerShape(4.dp)) {
                            Text(text = statusTag.first, color = statusTag.second, fontSize = 11.sp, fontWeight = FontWeight.Medium, modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp))
                        }
                        Spacer(modifier = Modifier.width(5.dp))
                    }
                    if (paused && fileLoaded) {
                        Surface(color = Color(0x30FFFFFF), shape = RoundedCornerShape(4.dp)) {
                            Text("暂停", color = Color.White, fontSize = 11.sp, modifier = Modifier.padding(horizontal = 5.dp, vertical = 2.dp))
                        }
                        Spacer(modifier = Modifier.width(5.dp))
                    }
                    mediaInfoBadges.forEach { info: String ->
                        Surface(color = Color(0x30FFFFFF), shape = RoundedCornerShape(4.dp)) {
                            Text(text = info, color = Color(0xCCFFFFFF), fontSize = 11.sp, modifier = Modifier.padding(horizontal = 5.dp, vertical = 2.dp))
                        }
                        Spacer(modifier = Modifier.width(4.dp))
                    }
                }

                // 行间分隔条
                Box(modifier = Modifier.fillMaxWidth().padding(top = 6.dp).height(1.dp).background(TV_ROW_DIVIDER))

                // 第2行：当前节目时间范围 + 节目名 + 进度条(细线) + 时间戳 + 距结束 + 按钮
                Spacer(modifier = Modifier.height(6.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                        if (currentProgram != null && currentProgram.title.isNotEmpty()) {
                            if (currentProgram.stopTs > 0) {
                                val timeRange = remember(currentProgram) {
                                    val start = timeFmt.format(java.util.Date(currentProgram.startTs * 1000L))
                                    val end = timeFmt.format(java.util.Date(currentProgram.stopTs * 1000L))
                                    "$start-$end"
                                }
                                Text(text = timeRange, color = Color(0xFFa0a0a0), fontSize = 13.sp)
                                Spacer(modifier = Modifier.width(8.dp))
                            }
                            Text(
                                text = currentProgram.title,
                                color = oc.textPrimary,
                                fontSize = 14.sp,
                                maxLines = 1, overflow = TextOverflow.Ellipsis,
                                modifier = Modifier.weight(1f)
                            )
                        } else {
                            Text(
                                text = "精彩节目",
                                color = oc.textSecondary.copy(alpha = 0.6f),
                                fontSize = 14.sp,
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
                                        .background(AptvAccent)
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
                            Text(text = posText, color = Color(0xFFa0a0a0), fontSize = 12.sp)
                        }
                        if (remainText != null) {
                            Spacer(modifier = Modifier.width(6.dp))
                            Text(text = remainText, color = AptvAccent, fontSize = 11.sp)
                        }
                        if (showExitCatchup) {
                            Spacer(modifier = Modifier.width(4.dp))
                            IconButton(onClick = { viewModel.exitCatchup() }, modifier = Modifier.size(30.dp).tvFocusBorder()) {
                                Icon(Icons.AutoMirrored.Filled.Backspace, "退出回看", tint = oc.accent, modifier = Modifier.size(16.dp))
                            }
                        }
                        Spacer(modifier = Modifier.width(2.dp))
                        // 播放/暂停按钮：原底栏无播放控制，暂停后用户无从恢复
                        // barFocus：底栏呼出时初始焦点落点，DPAD 可直接在底栏内移动
                        IconButton(
                            onClick = { viewModel.mpv.setPause(!paused) },
                            modifier = Modifier
                                .size(30.dp)
                                .then(if (barFocus != null) Modifier.focusRequester(barFocus) else Modifier)
                                .tvFocusBorder()
                        ) {
                            Icon(
                                if (paused) Icons.Default.PlayArrow else Icons.Default.Pause,
                                contentDescription = if (paused) "播放" else "暂停",
                                tint = oc.accent,
                                modifier = Modifier.size(16.dp)
                            )
                        }
                        Spacer(modifier = Modifier.width(2.dp))
                        IconButton(onClick = { viewModel.stopPlay() }, modifier = Modifier.size(30.dp).tvFocusBorder()) {
                            Icon(Icons.Default.Stop, "停止", tint = oc.iconTint, modifier = Modifier.size(16.dp))
                        }
                        Spacer(modifier = Modifier.width(2.dp))
                        // 返回分屏：从全屏一键回到左右分屏播放页（不用记忆 BACK 链路）
                        IconButton(onClick = { viewModel.setLandscapeSplitMode(true) }, modifier = Modifier.size(30.dp).tvFocusBorder()) {
                            Icon(Icons.Default.FullscreenExit, "返回分屏", tint = oc.iconTint, modifier = Modifier.size(16.dp))
                        }
                    }

                // 第3行：下一节目时间范围 + 下一节目名
                run {
                    val hasNext = nextProgram != null
                    // 行间分隔条
                    Box(modifier = Modifier.fillMaxWidth().padding(top = 6.dp).height(1.dp).background(TV_ROW_DIVIDER))
                    Spacer(modifier = Modifier.height(3.dp))
                    Row(verticalAlignment = Alignment.CenterVertically) {
                            if (hasNext) {
                                val nextStart = remember(nextProgram) {
                                    timeFmt.format(java.util.Date(nextProgram!!.startTs * 1000L))
                                }
                                val nextEnd = remember(nextProgram) {
                                    timeFmt.format(java.util.Date(nextProgram!!.stopTs * 1000L))
                                }
                                Text(text = "$nextStart-$nextEnd", color = Color(0xFFa0a0a0), fontSize = 13.sp)
                                Spacer(modifier = Modifier.width(8.dp))
                                Text(
                                    text = nextProgram!!.title,
                                    color = Color(0xB3FFFFFF),
                                    fontSize = 14.sp,
                                    maxLines = 1, overflow = TextOverflow.Ellipsis,
                                    modifier = Modifier.weight(1f)
                                )
                            } else {
                                val dateText = remember(tick) { dateFmt.format(java.util.Date(tick)) }
                                Text(
                                    text = dateText,
                                    color = Color(0xFFa0a0a0),
                                    fontSize = 13.sp,
                                    modifier = Modifier.weight(1f)
                                )
                            }
                        }
                } // 右侧信息列 Column（三行）
            } // 底栏外层 Row（台标列 + 信息列）

    }
}

}  // TvBottomBarStyleA

/**
 * 底栏样式 B：单行紧凑式 —— 小台标 + 频道号/名 + 状态 + 节目名/进度 + 播放控制一行排布。
 * 适合喜欢信息密度高、底栏不占垂直空间的场景。
 */
@Composable
private fun TvBottomBarStyleB(
    viewModel: AppViewModel,
    displayInfo: ChannelDisplayInfo,
    paused: Boolean,
    fileLoaded: Boolean,
    videoWidth: Int,
    videoHeight: Int,
    showExitCatchup: Boolean,
    playbackMode: PlayMode,
    currentProgram: IptvEpgProgram?,
    epgList: List<IptvEpgProgram>,
    barFocus: FocusRequester? = null
) {
    val mpv = viewModel.mpv
    val liquidGlass by viewModel.liquidGlass.collectAsState()
    var tick by remember { mutableStateOf(0L) }
    LaunchedEffect(Unit) { while (true) { tick = System.currentTimeMillis(); delay(1000L) } }
    val timeFmt = remember { java.text.SimpleDateFormat("HH:mm", java.util.Locale.getDefault()) }

    val statusTag = when {
        !fileLoaded -> null
        playbackMode == PlayMode.TIMESHIFT -> "时移" to Color(0xFF2979FF)
        showExitCatchup -> "回看" to Color(0xFFFFA500)
        else -> "直播" to AptvAccent
    }

    GlassPanel(liquidGlass = liquidGlass, cornerRadius = 8.dp, overlayDark = true) {
        val oc = rememberPlayerOverlayColors()
        val timePos by mpv.timePos.collectAsState()
        val duration by mpv.duration.collectAsState()
        val progress = computeTvBarProgress(currentProgram, timePos, duration)

        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 14.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            // 小台标
            Box(
                modifier = Modifier.size(52.dp, 30.dp).clip(RoundedCornerShape(5.dp)).background(ICON_BG),
                contentAlignment = Alignment.Center
            ) {
                if (displayInfo.logo.isNotEmpty()) {
                    AsyncImage(model = displayInfo.logo, contentDescription = displayInfo.name, modifier = Modifier.fillMaxSize().padding(2.dp), contentScale = ContentScale.Fit)
                } else {
                    Text(text = displayInfo.name.take(2).ifEmpty { "·" }, color = Color.White, fontSize = 12.sp, fontWeight = FontWeight.Bold)
                }
            }
            Spacer(modifier = Modifier.width(10.dp))
            // 频道号 + 名
            if (displayInfo.idx >= 0) {
                Text(text = String.format("%03d", displayInfo.idx + 1), color = AptvAccent, fontSize = 13.sp, fontWeight = FontWeight.Medium)
                Spacer(modifier = Modifier.width(5.dp))
            }
            Text(
                text = displayInfo.name.ifEmpty { "未选择频道" },
                color = oc.textPrimary, fontSize = 15.sp, fontWeight = FontWeight.Bold,
                maxLines = 1, overflow = TextOverflow.Ellipsis,
                modifier = Modifier.weight(0.9f, fill = false)
            )
            if (statusTag != null) {
                Spacer(modifier = Modifier.width(6.dp))
                Surface(color = statusTag.second.copy(alpha = 0.25f), shape = RoundedCornerShape(4.dp)) {
                    Text(text = statusTag.first, color = statusTag.second, fontSize = 10.sp, fontWeight = FontWeight.Medium, modifier = Modifier.padding(horizontal = 5.dp, vertical = 1.dp))
                }
            }
            Spacer(modifier = Modifier.width(8.dp))
            // 节目名 + 细进度（weight 占据剩余空间）
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = currentProgram?.title?.ifEmpty { null } ?: "精彩节目",
                    color = oc.textSecondary, fontSize = 12.sp,
                    maxLines = 1, overflow = TextOverflow.Ellipsis
                )
                if (progress != null) {
                    Spacer(modifier = Modifier.height(3.dp))
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(2.dp)
                            .clip(RoundedCornerShape(1.dp))
                            .background(Color(0x30FFFFFF))
                    ) {
                        Box(
                            modifier = Modifier
                                .fillMaxHeight()
                                .fillMaxWidth(progress)
                                .clip(RoundedCornerShape(1.dp))
                                .background(AptvAccent)
                        )
                    }
                }
            }
            Spacer(modifier = Modifier.width(6.dp))
            // 播放控制组
            IconButton(onClick = { viewModel.prevChannel() }, modifier = Modifier.size(30.dp).tvFocusBorder()) {
                Icon(Icons.Default.SkipPrevious, "上一个频道", tint = oc.iconTint, modifier = Modifier.size(16.dp))
            }
            IconButton(
                onClick = { viewModel.mpv.setPause(!paused) },
                modifier = Modifier
                    .size(34.dp)
                    .then(if (barFocus != null) Modifier.focusRequester(barFocus) else Modifier)
                    .tvFocusBorder()
            ) {
                Icon(if (paused) Icons.Default.PlayArrow else Icons.Default.Pause, if (paused) "播放" else "暂停", tint = oc.accent, modifier = Modifier.size(18.dp))
            }
            IconButton(onClick = { viewModel.nextChannel() }, modifier = Modifier.size(30.dp).tvFocusBorder()) {
                Icon(Icons.Default.SkipNext, "下一个频道", tint = oc.iconTint, modifier = Modifier.size(16.dp))
            }
            IconButton(onClick = { viewModel.stopPlay() }, modifier = Modifier.size(30.dp).tvFocusBorder()) {
                Icon(Icons.Default.Stop, "停止", tint = oc.iconTint, modifier = Modifier.size(15.dp))
            }
            IconButton(onClick = { viewModel.setLandscapeSplitMode(true) }, modifier = Modifier.size(30.dp).tvFocusBorder()) {
                Icon(Icons.Default.FullscreenExit, "返回分屏", tint = oc.iconTint, modifier = Modifier.size(15.dp))
            }
        }
    }
}

/**
 * 底栏样式 C：居中控制台式 —— 顶部频道信息一行居中，中央大号播放控制按钮组，
 * 底部细进度条。适合遥控器操作（按钮大、居中易定位）。
 */
@Composable
private fun TvBottomBarStyleC(
    viewModel: AppViewModel,
    displayInfo: ChannelDisplayInfo,
    paused: Boolean,
    fileLoaded: Boolean,
    videoWidth: Int,
    videoHeight: Int,
    showExitCatchup: Boolean,
    playbackMode: PlayMode,
    currentProgram: IptvEpgProgram?,
    epgList: List<IptvEpgProgram>,
    barFocus: FocusRequester? = null
) {
    val mpv = viewModel.mpv
    val liquidGlass by viewModel.liquidGlass.collectAsState()
    var tick by remember { mutableStateOf(0L) }
    LaunchedEffect(Unit) { while (true) { tick = System.currentTimeMillis(); delay(1000L) } }
    val timeFmt = remember { java.text.SimpleDateFormat("HH:mm", java.util.Locale.getDefault()) }

    val statusTag = when {
        !fileLoaded -> null
        playbackMode == PlayMode.TIMESHIFT -> "时移" to Color(0xFF2979FF)
        showExitCatchup -> "回看" to Color(0xFFFFA500)
        else -> "直播" to AptvAccent
    }

    GlassPanel(liquidGlass = liquidGlass, cornerRadius = 12.dp, overlayDark = true) {
        val oc = rememberPlayerOverlayColors()
        val timePos by mpv.timePos.collectAsState()
        val duration by mpv.duration.collectAsState()
        val progress = computeTvBarProgress(currentProgram, timePos, duration)

        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 24.dp, vertical = 10.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            // 行1：频道号 + 名 + 状态 + 节目时间范围
            Row(verticalAlignment = Alignment.CenterVertically) {
                if (displayInfo.idx >= 0) {
                    Text(text = String.format("%03d", displayInfo.idx + 1), color = AptvAccent, fontSize = 14.sp, fontWeight = FontWeight.Medium)
                    Spacer(modifier = Modifier.width(6.dp))
                }
                Text(
                    text = displayInfo.name.ifEmpty { "未选择频道" },
                    color = oc.textPrimary, fontSize = 16.sp, fontWeight = FontWeight.Bold,
                    maxLines = 1, overflow = TextOverflow.Ellipsis
                )
                if (statusTag != null) {
                    Spacer(modifier = Modifier.width(8.dp))
                    Surface(color = statusTag.second.copy(alpha = 0.25f), shape = RoundedCornerShape(4.dp)) {
                        Text(text = statusTag.first, color = statusTag.second, fontSize = 11.sp, fontWeight = FontWeight.Medium, modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp))
                    }
                }
                if (currentProgram != null && currentProgram.stopTs > 0) {
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = "${timeFmt.format(java.util.Date(currentProgram.startTs * 1000L))}-${timeFmt.format(java.util.Date(currentProgram.stopTs * 1000L))}",
                        color = Color(0xFFa0a0a0), fontSize = 12.sp
                    )
                }
            }
            Spacer(modifier = Modifier.height(8.dp))
            // 行2：居中大号控制按钮组
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(18.dp)) {
                IconButton(onClick = { viewModel.prevChannel() }, modifier = Modifier.size(40.dp).tvFocusBorder()) {
                    Icon(Icons.Default.SkipPrevious, "上一个频道", tint = oc.textPrimary, modifier = Modifier.size(26.dp))
                }
                Surface(color = AptvAccent.copy(alpha = 0.18f), shape = androidx.compose.foundation.shape.CircleShape) {
                    IconButton(
                        onClick = { viewModel.mpv.setPause(!paused) },
                        modifier = Modifier
                            .size(52.dp)
                            .then(if (barFocus != null) Modifier.focusRequester(barFocus) else Modifier)
                            .tvFocusBorder()
                    ) {
                        Icon(if (paused) Icons.Default.PlayArrow else Icons.Default.Pause, if (paused) "播放" else "暂停", tint = oc.accent, modifier = Modifier.size(30.dp))
                    }
                }
                IconButton(onClick = { viewModel.nextChannel() }, modifier = Modifier.size(40.dp).tvFocusBorder()) {
                    Icon(Icons.Default.SkipNext, "下一个频道", tint = oc.textPrimary, modifier = Modifier.size(26.dp))
                }
                IconButton(onClick = { viewModel.stopPlay() }, modifier = Modifier.size(36.dp).tvFocusBorder()) {
                    Icon(Icons.Default.Stop, "停止", tint = oc.textSecondary, modifier = Modifier.size(20.dp))
                }
                IconButton(onClick = { viewModel.setLandscapeSplitMode(true) }, modifier = Modifier.size(36.dp).tvFocusBorder()) {
                    Icon(Icons.Default.FullscreenExit, "返回分屏", tint = oc.textSecondary, modifier = Modifier.size(20.dp))
                }
            }
            // 行3：居中细进度条 + 时间
            if (progress != null) {
                Spacer(modifier = Modifier.height(8.dp))
                Box(
                    modifier = Modifier
                        .fillMaxWidth(0.72f)
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
            }
        }
    }
}

/**
 * 底栏样式 D：左信息右控制式 —— 左侧两行信息（频道行 + 节目/进度行），
 * 右侧竖分隔线 + 播放控制按钮组。信息与控制分区明确。
 */
@Composable
private fun TvBottomBarStyleD(
    viewModel: AppViewModel,
    displayInfo: ChannelDisplayInfo,
    paused: Boolean,
    fileLoaded: Boolean,
    videoWidth: Int,
    videoHeight: Int,
    showExitCatchup: Boolean,
    playbackMode: PlayMode,
    currentProgram: IptvEpgProgram?,
    epgList: List<IptvEpgProgram>,
    barFocus: FocusRequester? = null
) {
    val mpv = viewModel.mpv
    val liquidGlass by viewModel.liquidGlass.collectAsState()
    var tick by remember { mutableStateOf(0L) }
    LaunchedEffect(Unit) { while (true) { tick = System.currentTimeMillis(); delay(1000L) } }
    val timeFmt = remember { java.text.SimpleDateFormat("HH:mm", java.util.Locale.getDefault()) }

    val statusTag = when {
        !fileLoaded -> null
        playbackMode == PlayMode.TIMESHIFT -> "时移" to Color(0xFF2979FF)
        showExitCatchup -> "回看" to Color(0xFFFFA500)
        else -> "直播" to AptvAccent
    }

    GlassPanel(liquidGlass = liquidGlass, cornerRadius = 8.dp, overlayDark = true) {
        val oc = rememberPlayerOverlayColors()
        val timePos by mpv.timePos.collectAsState()
        val duration by mpv.duration.collectAsState()
        val progress = computeTvBarProgress(currentProgram, timePos, duration)

        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 9.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            // 左侧信息区（两行）
            Column(modifier = Modifier.weight(1f)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    if (displayInfo.idx >= 0) {
                        Text(text = String.format("%03d", displayInfo.idx + 1), color = AptvAccent, fontSize = 13.sp, fontWeight = FontWeight.Medium)
                        Spacer(modifier = Modifier.width(5.dp))
                    }
                    Text(
                        text = displayInfo.name.ifEmpty { "未选择频道" },
                        color = oc.textPrimary, fontSize = 15.sp, fontWeight = FontWeight.Bold,
                        maxLines = 1, overflow = TextOverflow.Ellipsis
                    )
                    if (statusTag != null) {
                        Spacer(modifier = Modifier.width(6.dp))
                        Surface(color = statusTag.second.copy(alpha = 0.25f), shape = RoundedCornerShape(4.dp)) {
                            Text(text = statusTag.first, color = statusTag.second, fontSize = 10.sp, fontWeight = FontWeight.Medium, modifier = Modifier.padding(horizontal = 5.dp, vertical = 1.dp))
                        }
                    }
                }
                Spacer(modifier = Modifier.height(4.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        text = currentProgram?.title?.ifEmpty { null } ?: "精彩节目",
                        color = oc.textSecondary, fontSize = 12.sp,
                        maxLines = 1, overflow = TextOverflow.Ellipsis,
                        modifier = Modifier.weight(1f, fill = false)
                    )
                    if (progress != null) {
                        Spacer(modifier = Modifier.width(8.dp))
                        Box(
                            modifier = Modifier
                                .width(110.dp)
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
                    }
                }
            }
            // 竖分隔条
            Box(modifier = Modifier.width(1.dp).height(36.dp).background(TV_ROW_DIVIDER))
            Spacer(modifier = Modifier.width(10.dp))
            // 右侧控制区
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                IconButton(onClick = { viewModel.prevChannel() }, modifier = Modifier.size(32.dp).tvFocusBorder()) {
                    Icon(Icons.Default.SkipPrevious, "上一个频道", tint = oc.iconTint, modifier = Modifier.size(18.dp))
                }
                IconButton(
                    onClick = { viewModel.mpv.setPause(!paused) },
                    modifier = Modifier
                        .size(36.dp)
                        .then(if (barFocus != null) Modifier.focusRequester(barFocus) else Modifier)
                        .tvFocusBorder()
                ) {
                    Icon(if (paused) Icons.Default.PlayArrow else Icons.Default.Pause, if (paused) "播放" else "暂停", tint = oc.accent, modifier = Modifier.size(20.dp))
                }
                IconButton(onClick = { viewModel.nextChannel() }, modifier = Modifier.size(32.dp).tvFocusBorder()) {
                    Icon(Icons.Default.SkipNext, "下一个频道", tint = oc.iconTint, modifier = Modifier.size(18.dp))
                }
                IconButton(onClick = { viewModel.stopPlay() }, modifier = Modifier.size(30.dp).tvFocusBorder()) {
                    Icon(Icons.Default.Stop, "停止", tint = oc.iconTint, modifier = Modifier.size(16.dp))
                }
                IconButton(onClick = { viewModel.setLandscapeSplitMode(true) }, modifier = Modifier.size(30.dp).tvFocusBorder()) {
                    Icon(Icons.Default.FullscreenExit, "返回分屏", tint = oc.iconTint, modifier = Modifier.size(16.dp))
                }
            }
        }
    }
}

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
