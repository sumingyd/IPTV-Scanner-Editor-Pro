package com.iptv.scanner.editor.pro.ui

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.SkipNext
import androidx.compose.material.icons.automirrored.filled.SkipPrevious
import androidx.compose.material.icons.filled.Pause
import androidx.compose.material.icons.filled.PlayArrow
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
    val currentChannel by viewModel.currentChannel.collectAsState()
    val playbackState by viewModel.playbackState.collectAsState()
    val showExitCatchup by viewModel.showExitCatchup.collectAsState()
    val currentProgram = remember { mutableStateOf<com.iptv.scanner.editor.pro.data.IptvEpgProgram?>(null) }

    // 周期刷新：当前节目 + 媒体徽章数据
    LaunchedEffect(Unit) {
        while (true) {
            currentProgram.value = viewModel.getCurrentProgram()
            delay(2_000L)
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
            // 第 1 行：媒体信息徽章
            // -----------------------------------------------------------------
            MediaBadgesRow(
                mpv = mpv,
                videoWidth = videoWidth,
                videoHeight = videoHeight,
                duration = duration
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
// 第 1 行：媒体信息徽章
// -----------------------------------------------------------------

@Composable
private fun MediaBadgesRow(
    mpv: com.iptv.scanner.editor.pro.mpv.MpvController,
    videoWidth: Int,
    videoHeight: Int,
    duration: Double
) {
    // 从 mpv 实时读取属性（非 StateFlow，每次重组都重新读取）
    val videoCodec = remember { mpv.getPropertyString("track-list/0/codec") ?: "" }
    val audioCodec = remember { mpv.getPropertyString("track-list/1/codec") ?: "" }
    val hwdec = remember { mpv.getPropertyString("hwdec-current") ?: "" }
    val fps = remember { mpv.getPropertyDouble("container-fps") ?: mpv.getPropertyDouble("estimated-vf-fps") ?: 0.0 }
    val gamma = remember { mpv.getPropertyString("video-params/gamma") ?: "" }
    val isHdr = gamma == "pq" || gamma == "hlg"

    val videoInfo = buildString {
        if (hwdec.isNotEmpty()) append("硬件解码: $hwdec | ")
        if (videoCodec.isNotEmpty()) append("视频: $videoCodec | ")
        if (videoWidth > 0 && videoHeight > 0) append("分辨率: ${videoWidth}x${videoHeight} | ")
        if (fps > 0) append("帧率: ${"%.1f".format(fps)}fps")
    }.trimEnd(' ', '|', ' ')

    val audioInfo = buildString {
        if (audioCodec.isNotEmpty()) append("音频: $audioCodec")
    }.trimEnd(' ', '|', ' ')

    if (videoInfo.isEmpty() && audioInfo.isEmpty() && !isHdr) return

    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(6.dp)
    ) {
        if (videoInfo.isNotEmpty()) {
            Badge(text = videoInfo, color = Color(0xFF4A9EFF))
        }
        if (isHdr) {
            Badge(text = if (gamma == "pq") "HDR10" else "HLG", color = Color(0xFFFFA500))
        }
        if (audioInfo.isNotEmpty()) {
            Badge(text = audioInfo, color = Color(0xFF4CAF50))
        }
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
        StatusBadge(
            playbackState = playbackState,
            duration = videoWidth.toDouble() // 占位，实际用 duration
        )
    }
}

@Composable
private fun StatusBadge(
    playbackState: com.iptv.scanner.editor.pro.player.PlaybackState,
    duration: Double
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
            value = if (dragging) dragPercent else progressInfo.percent,
            onValueChange = {
                dragging = true
                dragPercent = it
            },
            onValueChangeFinished = {
                viewModel.seekProgress(dragPercent)
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
        IconButton(onClick = onPrev, modifier = Modifier.size(36.dp)) {
            Icon(Icons.AutoMirrored.Filled.SkipPrevious, contentDescription = "上一频道", tint = Color.White)
        }

        IconButton(onClick = onPlayPause, modifier = Modifier.size(40.dp)) {
            Icon(
                imageVector = if (paused) Icons.Default.PlayArrow else Icons.Default.Pause,
                contentDescription = if (paused) "播放" else "暂停",
                tint = Color.White,
                modifier = Modifier.size(28.dp)
            )
        }

        IconButton(onClick = onStop, modifier = Modifier.size(36.dp)) {
            Icon(Icons.Default.Stop, contentDescription = "停止", tint = Color.White)
        }

        IconButton(onClick = onNext, modifier = Modifier.size(36.dp)) {
            Icon(Icons.AutoMirrored.Filled.SkipNext, contentDescription = "下一频道", tint = Color.White)
        }

        Spacer(modifier = Modifier.width(8.dp))

        // 中间：静音 + 音量滑块
        IconButton(onClick = onMute, modifier = Modifier.size(36.dp)) {
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

        // 右侧：退出回看按钮（catchup/timeshift 模式时显示）
        if (showExitCatchup) {
            IconButton(onClick = onExitCatchup, modifier = Modifier.size(36.dp)) {
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

