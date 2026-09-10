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


private val TV_BOTTOM_BAR_HEIGHT = 100.dp

// 酷9风格配色
private val KU9_GRADIENT_START = Color(0xFF036D80)
private val KU9_GRADIENT_END = Color(0xFF052D49)
private val KU9_ACCENT_GREEN = Color(0xFF70C439)
private val KU9_ACCENT_CYAN = Color(0xFF00BCD4)
private val KU9_ICON_BG = Color(0x32FFFFFF)
private val KU9_TIME_BG = Color(0x26000000)

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
    val ku9ShowTime by viewModel.ku9ShowTime.collectAsState()
    val ku9ShowNetSpeed by viewModel.ku9ShowNetSpeed.collectAsState()

    val currentProgram = remember(currentEpg) {
        ProgressHelper.findCurrentProgram(currentEpg, System.currentTimeMillis())
    }

    val showOverlays by derivedStateOf { sidebarVisible || controlsVisible || controlsPinned }

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

    // DPI自适应缩放：以TV横屏720dp高度为基准，手机横屏高度不足时缩小UI
    val configuration = LocalConfiguration.current
    val origDensity = LocalDensity.current
    val dpiScale = (configuration.screenHeightDp / 720f).coerceIn(0.55f, 1f)
    val scaledDensity = Density(origDensity.density * dpiScale, origDensity.fontScale)

    Box(modifier = Modifier.fillMaxSize()) {
        primaryPlayer()

        CompositionLocalProvider(LocalDensity provides scaledDensity) {
        // 酷9风格：右上角时间组（始终显示）
        if (ku9ShowTime) {
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

        // 酷9风格：右下角网速显示
        if (fileLoaded && !sidebarVisible && ku9ShowNetSpeed) {
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
        // 酷9风格：数字选台时显示大字号频道号
        if (channelNumberInput.isNotEmpty()) {
            Surface(
                color = KU9_TIME_BG,
                shape = RoundedCornerShape(8.dp)
            ) {
                Text(
                    text = channelNumberInput,
                    color = KU9_ACCENT_GREEN,
                    fontSize = 72.sp,
                    fontWeight = FontWeight.Bold,
                    modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp)
                )
            }
            Spacer(modifier = Modifier.height(6.dp))
        } else if (channelNumDisplay.isNotEmpty()) {
            // 切台时显示频道号
            Surface(
                color = KU9_TIME_BG,
                shape = RoundedCornerShape(8.dp)
            ) {
                Text(
                    text = channelNumDisplay,
                    color = KU9_ACCENT_GREEN,
                    fontSize = 48.sp,
                    fontWeight = FontWeight.Bold,
                    modifier = Modifier.padding(horizontal = 12.dp, vertical = 2.dp)
                )
            }
            Spacer(modifier = Modifier.height(6.dp))
        }
        Surface(
            color = KU9_TIME_BG,
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
            color = KU9_TIME_BG,
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

    // 酷9风格状态标签
    val statusTag = when {
        !fileLoaded -> null
        playbackMode == PlayMode.TIMESHIFT -> "时移" to Color(0xFF2979FF)
        showExitCatchup -> "回看" to Color(0xFFFFA500)
        else -> "直播" to KU9_ACCENT_GREEN
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
            Box(modifier = Modifier.matchParentSize().clip(RoundedCornerShape(12.dp)).blur(15.dp).background(Color(0x88333333)))
        }
        Surface(
            color = if (isAndroid12Plus) Color(0xCC333333) else Color(0xD0333333),
            shape = RoundedCornerShape(12.dp)
        ) {
            Column(modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp)) {
                // 第1行：Logo + 频道号 + 频道名 + 状态标签 + 技术标签
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(
                        modifier = Modifier.size(96.dp, 64.dp).clip(RoundedCornerShape(8.dp)).background(KU9_ICON_BG),
                        contentAlignment = Alignment.Center
                    ) {
                        if (displayInfo.logo.isNotEmpty()) {
                            AsyncImage(model = displayInfo.logo, contentDescription = displayInfo.name, modifier = Modifier.fillMaxSize().padding(6.dp), contentScale = ContentScale.Fit)
                        } else {
                            Text(
                                text = displayInfo.name.take(2).ifEmpty { "·" },
                                color = Color.White,
                                fontSize = 24.sp,
                                fontWeight = FontWeight.Bold
                            )
                        }
                    }
                    Spacer(modifier = Modifier.width(14.dp))
                    if (displayInfo.idx >= 0) {
                        Text(
                            text = String.format("%03d", displayInfo.idx + 1),
                            color = KU9_ACCENT_CYAN,
                            fontSize = 14.sp,
                            fontWeight = FontWeight.Medium
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                    }
                    Text(
                        text = displayInfo.name.ifEmpty { "未选择频道" },
                        color = if (displayInfo.idx >= 0) oc.textPrimary else oc.textSecondary,
                        fontSize = 20.sp, fontWeight = FontWeight.Bold,
                        maxLines = 1, overflow = TextOverflow.Ellipsis
                    )
                    Spacer(modifier = Modifier.weight(1f))
                    if (statusTag != null) {
                        Surface(color = statusTag.second.copy(alpha = 0.25f), shape = RoundedCornerShape(4.dp)) {
                            Text(text = statusTag.first, color = statusTag.second, fontSize = 12.sp, fontWeight = FontWeight.Medium, modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp))
                        }
                        Spacer(modifier = Modifier.width(4.dp))
                    }
                    if (paused && fileLoaded) {
                        Surface(color = Color(0x30FFFFFF), shape = RoundedCornerShape(4.dp)) {
                            Text("暂停", color = Color.White, fontSize = 11.sp, modifier = Modifier.padding(horizontal = 5.dp, vertical = 2.dp))
                        }
                        Spacer(modifier = Modifier.width(4.dp))
                    }
                    mediaInfoBadges.forEach { info: String ->
                        Surface(color = Color(0x30FFFFFF), shape = RoundedCornerShape(4.dp)) {
                            Text(text = info, color = Color(0xCCFFFFFF), fontSize = 11.sp, modifier = Modifier.padding(horizontal = 5.dp, vertical = 2.dp))
                        }
                        Spacer(modifier = Modifier.width(4.dp))
                    }
                }

                // 第2行：当前节目名 + 时间范围 + 进度条 + 时间戳 + 距结束 + 按钮（始终显示）
                Spacer(modifier = Modifier.height(6.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                        // 日期
                        val dateText = remember(tick) { dateFmt.format(java.util.Date(tick)) }
                        Text(text = dateText, color = oc.textSecondary, fontSize = 12.sp)
                        Spacer(modifier = Modifier.width(8.dp))
                        // 当前节目名
                        if (currentProgram != null && currentProgram.title.isNotEmpty()) {
                            Text(
                                text = currentProgram.title,
                                color = oc.textPrimary,
                                fontSize = 15.sp,
                                maxLines = 1, overflow = TextOverflow.Ellipsis,
                                modifier = Modifier.weight(1f)
                            )
                        } else {
                            Text(
                                text = "精彩节目",
                                color = KU9_ACCENT_CYAN,
                                fontSize = 15.sp,
                                modifier = Modifier.weight(1f)
                            )
                        }
                        if (currentProgram != null && currentProgram.stopTs > 0) {
                            Spacer(modifier = Modifier.width(8.dp))
                            val timeRange = remember(currentProgram) {
                                val start = timeFmt.format(java.util.Date(currentProgram.startTs * 1000L))
                                val end = timeFmt.format(java.util.Date(currentProgram.stopTs * 1000L))
                                "$start-$end"
                            }
                            Text(text = timeRange, color = oc.textSecondary, fontSize = 12.sp)
                        }
                        Spacer(modifier = Modifier.width(8.dp))
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
                        Slider(
                            value = if (hasEpg) progress.percent / 100f else 0f,
                            onValueChange = { if (hasEpg) viewModel.seekProgress(it * 100f) },
                            enabled = hasEpg,
                            modifier = Modifier.width(200.dp).height(10.dp),
                            colors = SliderDefaults.colors(thumbColor = Color(0xFF2979FF), activeTrackColor = Color(0xFF2979FF), inactiveTrackColor = Color(0x30FFFFFF))
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        val posText = remember(tick, timePos, playbackMode, showExitCatchup) {
                            if (playbackMode == PlayMode.LIVE && !showExitCatchup) {
                                fullTimeFmt.format(java.util.Date(tick))
                            } else if (timePos > 0) {
                                fullTimeFmt.format(java.util.Date((timePos * 1000L).toLong()))
                            } else ""
                        }
                        if (posText.isNotEmpty()) {
                            Text(text = posText, color = oc.textSecondary, fontSize = 12.sp)
                        }
                        if (remainText != null) {
                            Spacer(modifier = Modifier.width(6.dp))
                            Text(text = remainText, color = KU9_ACCENT_CYAN, fontSize = 11.sp)
                        }
                        if (showExitCatchup) {
                            Spacer(modifier = Modifier.width(4.dp))
                            IconButton(onClick = { viewModel.exitCatchup() }, modifier = Modifier.size(28.dp).tvFocusBorder()) {
                                Icon(Icons.AutoMirrored.Filled.Backspace, "退出回看", tint = oc.accent, modifier = Modifier.size(16.dp))
                            }
                        }
                        Spacer(modifier = Modifier.width(2.dp))
                        IconButton(onClick = { viewModel.stopPlay() }, modifier = Modifier.size(28.dp).tvFocusBorder()) {
                            Icon(Icons.Default.Stop, "停止", tint = oc.iconTint, modifier = Modifier.size(16.dp))
                        }
                    }

                // 第3行：当前节目描述 + 下一节目预告（始终显示，无节目单时占位）
                run {
                    val hasDesc = currentProgram != null && currentProgram.desc.isNotEmpty()
                    val hasNext = nextProgram != null
                    Spacer(modifier = Modifier.height(4.dp))
                    Row(verticalAlignment = Alignment.CenterVertically) {
                            // 节目描述（有则显示，无则占位"精彩节目"）
                            if (hasDesc) {
                                Text(
                                    text = currentProgram!!.desc,
                                    color = oc.textSecondary.copy(alpha = 0.85f),
                                    fontSize = 12.sp,
                                    maxLines = 1, overflow = TextOverflow.Ellipsis,
                                    modifier = Modifier.weight(1f)
                                )
                            } else {
                                Text(
                                    text = "精彩节目",
                                    color = oc.textSecondary.copy(alpha = 0.6f),
                                    fontSize = 12.sp,
                                    maxLines = 1,
                                    modifier = Modifier.weight(1f)
                                )
                            }
                            // 下一节目预告（紧跟描述或左对齐）
                            if (hasNext) {
                                Spacer(modifier = Modifier.width(12.dp))
                                val nextStart = remember(nextProgram) {
                                    timeFmt.format(java.util.Date(nextProgram!!.startTs * 1000L))
                                }
                                Text(
                                    text = "下一节目 $nextStart ",
                                    color = KU9_ACCENT_CYAN,
                                    fontSize = 12.sp,
                                    fontWeight = FontWeight.Medium
                                )
                                Text(
                                    text = nextProgram!!.title,
                                    color = Color(0xB3FFFFFF),
                                    fontSize = 12.sp,
                                    maxLines = 1, overflow = TextOverflow.Ellipsis,
                                    modifier = Modifier.width(200.dp)
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
