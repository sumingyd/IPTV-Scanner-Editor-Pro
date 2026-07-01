package com.iptv.scanner.editor.pro.ui

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Pause
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.SkipNext
import androidx.compose.material.icons.filled.SkipPrevious
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material.icons.filled.VolumeOff
import androidx.compose.material.icons.filled.VolumeUp
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Slider
import androidx.compose.material3.SliderDefaults
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
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.iptv.scanner.editor.pro.player.PlayMode
import com.iptv.scanner.editor.pro.player.ProgressHelper
import com.iptv.scanner.editor.pro.ui.theme.tvFocusBorder
import kotlinx.coroutines.delay

/**
 * 控制面板：3 行布局，对齐 PC 端 mobile/index.html panelControls。
 *
 * - 第 1 行：媒体信息徽章（视频/HDR/音频/网络/缓冲）
 * - 第 2 行：节目信息（频道名 + 节目名 + 时间徽章 + 回看指示器 + 状态徽章）
 * - 第 3 行：控制按钮（上一/播放/停止/下一 + 进度条 + 静音/音量 + 速度/比例/音轨/字幕/退出回看/全屏）
 *
 * 与内存规则对齐：
 * - Control panel must use 3-row layout matching PC端
 * - Control panel media info (first row) and program info (second row) must match PC端 display format
 * - Live progress bar logic must match PC端 (4 种分支)
 * - Exit catchup must set playMode='live'
 */
@Composable
fun ControlPanel(viewModel: AppViewModel) {
    val mpv = viewModel.mpv
    val paused by mpv.paused.collectAsState()
    val muted by mpv.muted.collectAsState()
    val volume by mpv.volume.collectAsState()
    val timePos by mpv.timePos.collectAsState()
    val duration by mpv.duration.collectAsState()
    val videoWidth by mpv.videoWidth.collectAsState()
    val videoHeight by mpv.videoHeight.collectAsState()
    val mediaTitle by mpv.mediaTitle.collectAsState()
    val fileLoaded by mpv.fileLoaded.collectAsState()
    val currentChannel by viewModel.currentChannel.collectAsState()
    val playbackState by viewModel.playbackState.collectAsState()
    val showExitCatchup by viewModel.showExitCatchup.collectAsState()
    val currentProgram = remember { mutableStateOf<com.iptv.scanner.editor.pro.data.IptvEpgProgram?>(null) }

    // 周期刷新：当前节目（2 秒）+ 媒体徽章数据（1 秒，对齐 PC 端 updateCtrlInfo 频率）
    var mediaBadgeTick by remember { mutableStateOf(0L) }
    LaunchedEffect(Unit) {
        while (true) {
            currentProgram.value = viewModel.getCurrentProgram()
            delay(2_000L)
        }
    }
    LaunchedEffect(fileLoaded) {
        // 文件加载后才需要刷新媒体徽章（码率/缓冲等动态值）
        while (fileLoaded) {
            mediaBadgeTick = System.currentTimeMillis()
            delay(1_000L)
        }
    }

    Surface(
        color = Color(0xCC000000),
        modifier = Modifier.fillMaxWidth()
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 12.dp, vertical = 8.dp)
        ) {
            // -----------------------------------------------------------------
            // 第 1 行：媒体信息徽章（对齐 PC 端 updateMediaBadges：5 徽章 13 字段）
            // -----------------------------------------------------------------
            MediaBadgesRow(
                mpv = mpv,
                videoWidth = videoWidth,
                videoHeight = videoHeight,
                fileLoaded = fileLoaded,
                tick = mediaBadgeTick
            )

            Spacer(modifier = Modifier.height(6.dp))

            // -----------------------------------------------------------------
            // 第 2 行：节目信息
            // -----------------------------------------------------------------
            ProgramInfoRow(
                channel = currentChannel,
                mediaTitle = mediaTitle,
                program = currentProgram.value,
                playbackState = playbackState,
                videoWidth = videoWidth,
                videoHeight = videoHeight
            )

            Spacer(modifier = Modifier.height(8.dp))

            // -----------------------------------------------------------------
            // 第 3 行：进度条 + 控制按钮
            // -----------------------------------------------------------------
            ProgressBar(viewModel = viewModel)

            Spacer(modifier = Modifier.height(8.dp))

            ControlButtonsRow(
                paused = paused,
                muted = muted,
                volume = volume,
                isTV = viewModel.uiMode.value.isTV,
                showExitCatchup = showExitCatchup,
                playbackMode = playbackState.mode,
                onPlayPause = { mpv.togglePause() },
                onStop = { viewModel.stopPlay() },
                onPrev = { viewModel.prevChannel() },
                onNext = { viewModel.nextChannel() },
                onMute = { mpv.toggleMute() },
                onVolumeChange = { mpv.setVolume(it.toInt()) },
                onExitCatchup = { viewModel.exitCatchup() }
            )
        }
    }
}

// -----------------------------------------------------------------
// 第 1 行：媒体信息徽章（对齐 PC 端 updateMediaBadges：5 徽章 13 字段）
// -----------------------------------------------------------------

/**
 * 媒体信息徽章行：与 PC 端 server/mobile/index.html updateMediaBadges() 完全对齐。
 *
 * 5 个徽章（颜色对齐 PC 端 ctrl-badge 样式）：
 * 1. 视频徽章：硬件解码 + 视频编解码器 + 分辨率 + 帧率 + 视频码率（灰色）
 * 2. HDR 徽章：HDR10 / HLG（橙色）
 * 3. 音频徽章：音频编解码器 + 声道 + 采样率 + 码率（灰色）
 * 4. 网络徽章：格式 + 协议 + 总码率 + 缓存速度（灰色）
 * 5. 缓冲徽章：缓冲百分比（绿色，仅缓冲中显示）
 *
 * 用 FlowRow 自动换行，适配手机窄屏和 TV 宽屏。
 */
@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun MediaBadgesRow(
    mpv: com.iptv.scanner.editor.pro.player.Player,
    videoWidth: Int,
    videoHeight: Int,
    fileLoaded: Boolean,
    tick: Long
) {
    if (!fileLoaded) return

    // 从 mpv 实时读取属性（用 tick + fileLoaded 作为 key，每秒刷新动态值如码率/缓冲）
    val videoCodec = remember(tick, fileLoaded) { mpv.getPropertyString("video-codec") ?: "" }
    val audioCodec = remember(tick, fileLoaded) { mpv.getPropertyString("audio-codec") ?: "" }
    val hwdec = remember(tick, fileLoaded) { mpv.getPropertyString("hwdec-current") ?: "" }
    val fps = remember(tick, fileLoaded) {
        mpv.getPropertyDouble("container-fps") ?: mpv.getPropertyDouble("estimated-vf-fps") ?: 0.0
    }
    val gamma = remember(tick, fileLoaded) { mpv.getPropertyString("video-params/gamma") ?: "" }
    val isHdr = gamma == "pq" || gamma == "hlg"

    // 新增字段（对齐 PC 端）
    val videoBitrate = remember(tick, fileLoaded) { mpv.getPropertyDouble("video-bitrate") ?: 0.0 }
    // 注意：用 channel-count 而非 channels。
    // mpv-android 不支持用 INT64 读取 audio-params/channels（PC 端桌面版支持，会自动转换 "stereo"->2）。
    // channels 是字符串（如 "stereo"/"mono"/"5.1"），channel-count 是 int。
    val audioChannels = remember(tick, fileLoaded) { mpv.getPropertyInt("audio-params/channel-count") ?: 0 }
    val audioSamplerate = remember(tick, fileLoaded) { mpv.getPropertyInt("audio-params/samplerate") ?: 0 }
    val audioBitrate = remember(tick, fileLoaded) { mpv.getPropertyDouble("audio-bitrate") ?: 0.0 }
    val fileFormat = remember(tick, fileLoaded) { mpv.getPropertyString("file-format") ?: "" }
    val protocol = remember(tick, fileLoaded) { mpv.getPropertyString("protocol") ?: "" }
    val cacheDuration = remember(tick, fileLoaded) { mpv.getPropertyDouble("demuxer-cache-duration") ?: 0.0 }
    val demuxerBitrate = remember(tick, fileLoaded) { mpv.getPropertyDouble("demuxer-bitrate") ?: 0.0 }
    val bufferingState = remember(tick, fileLoaded) { mpv.getPropertyInt("cache-buffering-state") ?: -1 }

    // 视频徽章（对齐 PC 端 ctrlVideoInfo）
    val videoInfo = buildString {
        if (hwdec.isNotEmpty() && hwdec != "no") append("硬件解码: $hwdec | ")
        if (videoCodec.isNotEmpty()) append("视频: $videoCodec | ")
        if (videoWidth > 0 && videoHeight > 0) append("分辨率: ${videoWidth}x${videoHeight} | ")
        if (fps > 0) append("帧率: ${"%.0f".format(fps)}fps | ")
        if (videoBitrate > 0) append("视频码率: ${formatBitrate(videoBitrate)}")
    }.trimEnd(' ', '|', ' ')

    // 音频徽章（对齐 PC 端 ctrlAudioInfo）
    val audioInfo = buildString {
        if (audioCodec.isNotEmpty()) append("音频: $audioCodec | ")
        if (audioChannels > 0) {
            val ch = when (audioChannels) {
                1 -> "单声道"
                2 -> "立体声"
                6 -> "5.1声道"
                8 -> "7.1声道"
                else -> "${audioChannels}声道"
            }
            append("声道: $ch | ")
        }
        if (audioSamplerate > 0) {
            val sr = if (audioSamplerate >= 1000) {
                "${"%.1f".format(audioSamplerate / 1000.0)}kHz"
            } else {
                "${audioSamplerate}Hz"
            }
            append("采样率: $sr | ")
        }
        if (audioBitrate > 0) append("码率: ${formatBitrate(audioBitrate)}")
    }.trimEnd(' ', '|', ' ')

    // 网络徽章（对齐 PC 端 ctrlNetworkInfo）
    val networkInfo = buildString {
        if (fileFormat.isNotEmpty()) append("格式: $fileFormat | ")
        if (protocol.isNotEmpty()) append("协议: $protocol | ")
        val totalBr = videoBitrate + audioBitrate
        if (totalBr > 0) {
            append("码率: ${formatBitrate(totalBr)} | ")
        } else if (demuxerBitrate > 0) {
            append("码率: ${formatBitrate(demuxerBitrate)} | ")
        }
        if (cacheDuration > 0) append("缓存: ${"%.1f".format(cacheDuration)}s")
    }.trimEnd(' ', '|', ' ')

    if (videoInfo.isEmpty() && audioInfo.isEmpty() && networkInfo.isEmpty() && !isHdr && bufferingState < 0) return

    FlowRow(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(6.dp),
        verticalArrangement = Arrangement.spacedBy(4.dp)
    ) {
        if (videoInfo.isNotEmpty()) {
            Badge(text = videoInfo, color = Color(0xFFBDBDBD))
        }
        if (isHdr) {
            Badge(text = if (gamma == "pq") "HDR10" else "HLG", color = Color(0xFFFF9800))
        }
        if (audioInfo.isNotEmpty()) {
            Badge(text = audioInfo, color = Color(0xFFBDBDBD))
        }
        if (networkInfo.isNotEmpty()) {
            Badge(text = networkInfo, color = Color(0xFFBDBDBD))
        }
        // 缓冲徽章：仅缓冲中显示（0 < bufState < 100）
        if (bufferingState in 1..99) {
            Badge(text = "缓冲 $bufferingState%", color = Color(0xFF4CAF50))
        }
    }
}

/**
 * 码率格式化（对齐 PC 端 formatBitrate）。
 * 输入单位：bits/sec
 */
private fun formatBitrate(bitrate: Double): String {
    return if (bitrate >= 1_000_000) {
        "${"%.1f".format(bitrate / 1_000_000)}Mbps"
    } else if (bitrate >= 1_000) {
        "${"%.0f".format(bitrate / 1_000)}Kbps"
    } else {
        "${"%.0f".format(bitrate)}bps"
    }
}

@Composable
private fun Badge(text: String, color: Color) {
    Surface(
        color = color.copy(alpha = 0.15f),
        shape = RoundedCornerShape(4.dp),
        modifier = Modifier.clip(RoundedCornerShape(4.dp))
    ) {
        Text(
            text = text,
            color = color,
            fontSize = 10.sp,
            modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp),
            maxLines = 1,
            overflow = TextOverflow.Ellipsis
        )
    }
}

// -----------------------------------------------------------------
// 第 2 行：节目信息
// -----------------------------------------------------------------

@Composable
private fun ProgramInfoRow(
    channel: com.iptv.scanner.editor.pro.data.IptvChannel?,
    mediaTitle: String,
    program: com.iptv.scanner.editor.pro.data.IptvEpgProgram?,
    playbackState: com.iptv.scanner.editor.pro.player.PlaybackState,
    videoWidth: Int,
    videoHeight: Int
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically
    ) {
        // 频道名
        Text(
            text = channel?.name ?: "未选择频道",
            color = Color.White,
            fontSize = 14.sp,
            fontWeight = FontWeight.Medium,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
            modifier = Modifier.weight(1f, fill = false)
        )

        // 分隔符 + 节目名
        if (program != null && program.title.isNotEmpty()) {
            Text(
                text = " · ${program.title}",
                color = Color(0xFFCCCCCC),
                fontSize = 13.sp,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
                modifier = Modifier.weight(1f, fill = false)
            )
        } else if (mediaTitle.isNotEmpty() && mediaTitle != channel?.name) {
            Text(
                text = " · $mediaTitle",
                color = Color(0xFFCCCCCC),
                fontSize = 13.sp,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
                modifier = Modifier.weight(1f, fill = false)
            )
        }

        Spacer(modifier = Modifier.width(8.dp))

        // 回看/时移指示器
        if (playbackState.mode.isCatchupOrTimeshift) {
            val indicatorText = when (playbackState.mode) {
                PlayMode.CATCHUP -> "回看"
                PlayMode.TIMESHIFT -> "时移"
                else -> ""
            }
            Badge(text = indicatorText, color = Color(0xFFFFA500))
            Spacer(modifier = Modifier.width(6.dp))
        }

        // 状态徽章
        StatusBadge(playbackState = playbackState)
    }
}

@Composable
private fun StatusBadge(
    playbackState: com.iptv.scanner.editor.pro.player.PlaybackState
) {
    val text = when {
        playbackState.mode == PlayMode.IDLE -> "已停止"
        else -> "播放中"
    }
    Badge(text = text, color = Color(0xFF888888))
}

// -----------------------------------------------------------------
// 第 3 行：进度条
// -----------------------------------------------------------------

@Composable
private fun ProgressBar(viewModel: AppViewModel) {
    // 每秒刷新进度条
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

    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically
    ) {
        // 开始时间标签
        Text(
            text = progressInfo.startLabel,
            color = Color(0xFFCCCCCC),
            fontSize = 11.sp,
            modifier = Modifier.padding(end = 8.dp)
        )

        // 进度条
        Slider(
            value = if (dragging) dragPercent else (progressInfo.percent / 100f),
            onValueChange = {
                dragging = true
                dragPercent = it
            },
            onValueChangeFinished = {
                viewModel.seekProgress(dragPercent * 100f)
                dragging = false
            },
            modifier = Modifier.weight(1f),
            colors = SliderDefaults.colors(
                thumbColor = Color(0xFF4A9EFF),
                activeTrackColor = Color(0xFF4A9EFF),
                inactiveTrackColor = Color(0xFF444444)
            )
        )

        // 结束时间标签
        Text(
            text = progressInfo.endLabel,
            color = Color(0xFFCCCCCC),
            fontSize = 11.sp,
            modifier = Modifier.padding(start = 8.dp)
        )
    }
}

// -----------------------------------------------------------------
// 第 3 行：控制按钮
// -----------------------------------------------------------------

@Composable
private fun ControlButtonsRow(
    paused: Boolean,
    muted: Boolean,
    volume: Int,
    isTV: Boolean,
    showExitCatchup: Boolean,
    playbackMode: PlayMode,
    onPlayPause: () -> Unit,
    onStop: () -> Unit,
    onPrev: () -> Unit,
    onNext: () -> Unit,
    onMute: () -> Unit,
    onVolumeChange: (Float) -> Unit,
    onExitCatchup: () -> Unit
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(4.dp)
    ) {
        // 左侧：频道切换 + 播放控制
        IconButton(onClick = onPrev, modifier = Modifier.size(36.dp).tvFocusBorder()) {
            Icon(Icons.Default.SkipPrevious, contentDescription = "上一频道", tint = Color.White)
        }

        IconButton(onClick = onPlayPause, modifier = Modifier.size(40.dp).tvFocusBorder()) {
            Icon(
                imageVector = if (paused) Icons.Default.PlayArrow else Icons.Default.Pause,
                contentDescription = if (paused) "播放" else "暂停",
                tint = Color.White,
                modifier = Modifier.size(28.dp)
            )
        }

        IconButton(onClick = onStop, modifier = Modifier.size(36.dp).tvFocusBorder()) {
            Icon(Icons.Default.Stop, contentDescription = "停止", tint = Color.White)
        }

        IconButton(onClick = onNext, modifier = Modifier.size(36.dp).tvFocusBorder()) {
            Icon(Icons.Default.SkipNext, contentDescription = "下一频道", tint = Color.White)
        }

        Spacer(modifier = Modifier.width(8.dp))

        // 中间：静音 + 音量滑块（TV 模式下隐藏，由遥控器音量键控制）
        if (!isTV) {
            IconButton(onClick = onMute, modifier = Modifier.size(36.dp).tvFocusBorder()) {
                Icon(
                    imageVector = if (muted || volume == 0) Icons.Default.VolumeOff else Icons.Default.VolumeUp,
                    contentDescription = "静音",
                    tint = if (muted) Color(0xFFFFA500) else Color.White
                )
            }

            Slider(
                value = volume.toFloat(),
                onValueChange = onVolumeChange,
                valueRange = 0f..130f,
                modifier = Modifier
                    .weight(1f)
                    .height(24.dp),
                colors = SliderDefaults.colors(
                    thumbColor = Color(0xFF4A9EFF),
                    activeTrackColor = Color(0xFF4A9EFF),
                    inactiveTrackColor = Color(0xFF444444)
                )
            )

            Text(
                text = volume.toString(),
                color = Color(0xFFCCCCCC),
                fontSize = 11.sp,
                modifier = Modifier.width(28.dp)
            )

            Spacer(modifier = Modifier.width(8.dp))
        } else {
            // TV 模式下用 Spacer 占据中间空间
            Spacer(modifier = Modifier.weight(1f))
        }

        // 右侧：退出回看按钮（catchup/timeshift 模式时显示）
        if (showExitCatchup) {
            IconButton(onClick = onExitCatchup, modifier = Modifier.size(36.dp).tvFocusBorder()) {
                Box(
                    modifier = Modifier
                        .size(28.dp)
                        .clip(RoundedCornerShape(4.dp))
                        .background(Color(0xFFFFA500)),
                    contentAlignment = Alignment.Center
                ) {
                    Text(
                        text = if (playbackMode == PlayMode.TIMESHIFT) "时移" else "回看",
                        color = Color.White,
                        fontSize = 9.sp,
                        fontWeight = FontWeight.Bold
                    )
                }
            }
        }
    }
}

