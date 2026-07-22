package com.iptv.scanner.editor.pro.ui

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInHorizontally
import androidx.compose.animation.slideOutHorizontally
import androidx.compose.animation.core.tween
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
import androidx.compose.material.icons.filled.PlayArrow
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
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import coil.compose.AsyncImage
import com.iptv.scanner.editor.pro.data.IptvChannel
import com.iptv.scanner.editor.pro.data.IptvEpgProgram
import com.iptv.scanner.editor.pro.player.PlayMode
import com.iptv.scanner.editor.pro.player.PlaybackState
import com.iptv.scanner.editor.pro.player.ProgressHelper
import com.iptv.scanner.editor.pro.ui.theme.rememberPlayerOverlayColors
import com.iptv.scanner.editor.pro.ui.theme.tvFocusBorder
import kotlinx.coroutines.delay


private val TV_BOTTOM_BAR_HEIGHT = 80.dp

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

    val currentProgram = remember(currentEpg) {
        ProgressHelper.findCurrentProgram(currentEpg, System.currentTimeMillis())
    }

    val showOverlays by derivedStateOf { sidebarVisible || controlsVisible || controlsPinned }


    Box(modifier = Modifier.fillMaxSize()) {
        primaryPlayer()

        if (!showOverlays) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .clickable(
                        indication = null,
                        interactionSource = remember { MutableInteractionSource() }
                    ) { viewModel.showControlsAutoHide() }
            )
        }

        AnimatedVisibility(
            visible = sidebarVisible,
            enter = slideInHorizontally(initialOffsetX = { -it / 2 }, animationSpec = tween(150)),
            exit = slideOutHorizontally(targetOffsetX = { -it / 2 }, animationSpec = tween(120)),
            modifier = Modifier.align(Alignment.CenterStart)
        ) {
            val isAndroid12Plus = android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.S
            Box(modifier = Modifier.fillMaxHeight().fillMaxWidth(0.85f).padding(bottom = TV_BOTTOM_BAR_HEIGHT)) {
                if (isAndroid12Plus) {
                    Box(modifier = Modifier.matchParentSize().blur(20.dp).background(oc.topBarBg.copy(alpha = 0.40f)))
                }
                Surface(
                    color = if (isAndroid12Plus) oc.topBarBg.copy(alpha = 0.25f) else oc.topBarBg.copy(alpha = 0.85f),
                    modifier = Modifier.matchParentSize()
                ) {
                    TvUnifiedPanel(viewModel = viewModel)
                }
            }
        }

        Box(
            modifier = Modifier
                .align(Alignment.BottomStart)
                .fillMaxWidth()

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
                    currentProgram = currentProgram
                )
            }
        }
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
    currentProgram: IptvEpgProgram?
) {
    val oc = rememberPlayerOverlayColors()
    val mpv = viewModel.mpv

    var tick by remember { mutableStateOf(0L) }
    LaunchedEffect(Unit) { while (true) { tick = System.currentTimeMillis(); delay(1000L) } }

    val mediaInfoBadges = if (fileLoaded) remember(tick, videoWidth, videoHeight) {
        buildTvMediaBadges(mpv, videoWidth, videoHeight)
    } else emptyList()

    val isAndroid12Plus = android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.S

    Box {
        if (isAndroid12Plus) {
            Box(modifier = Modifier.matchParentSize().blur(15.dp).background(oc.topBarBg.copy(alpha = 0.35f)))
        }
        Surface(
            color = if (isAndroid12Plus) oc.topBarBg.copy(alpha = 0.20f) else oc.topBarBg.copy(alpha = 0.85f),
            shape = RoundedCornerShape(0.dp)
        ) {
            Column(modifier = Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 8.dp)) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Box(
                        modifier = Modifier.size(44.dp).clip(RoundedCornerShape(8.dp)).background(Color(0x18FFFFFF)),
                        contentAlignment = Alignment.Center
                    ) {
                        if (displayInfo.logo.isNotEmpty()) {
                            AsyncImage(model = displayInfo.logo, contentDescription = displayInfo.name, modifier = Modifier.fillMaxSize().padding(4.dp), contentScale = ContentScale.Fit)
                        } else {
                            Icon(Icons.Default.PlayArrow, contentDescription = null, tint = oc.accent, modifier = Modifier.size(22.dp))
                        }
                    }

                    Spacer(modifier = Modifier.width(12.dp))

                    Column(modifier = Modifier.weight(1f)) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(
                                text = displayInfo.name.ifEmpty { "未选择频道" },
                                color = if (displayInfo.idx >= 0) oc.textPrimary else oc.textSecondary,
                                fontSize = 16.sp, fontWeight = FontWeight.SemiBold,
                                maxLines = 1, overflow = TextOverflow.Ellipsis
                            )
                            if (showExitCatchup) {
                                Spacer(modifier = Modifier.width(6.dp))
                                Surface(color = oc.accent.copy(alpha = 0.2f), shape = RoundedCornerShape(4.dp)) {
                                    Text(text = if (playbackMode == PlayMode.TIMESHIFT) "时移" else "回看", color = oc.accent, fontSize = 10.sp, modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp))
                                }
                            }
                            if (paused && fileLoaded) {
                                Spacer(modifier = Modifier.width(6.dp))
                                Surface(color = oc.badgeBg, shape = RoundedCornerShape(4.dp)) {
                                    Text("已暂停", color = oc.badgeText, fontSize = 10.sp, modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp))
                                }
                            }
                            mediaInfoBadges.forEach { info: String ->
                                Spacer(modifier = Modifier.width(5.dp))
                                Surface(color = oc.badgeBg, shape = RoundedCornerShape(4.dp)) {
                                    Text(text = info, color = oc.badgeText, fontSize = 10.sp, modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp))
                                }
                            }
                        }
                        if (fileLoaded && currentProgram != null && currentProgram.title.isNotEmpty()) {
                            Spacer(modifier = Modifier.height(2.dp))
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Text(text = currentProgram.title, color = oc.textSecondary, fontSize = 13.sp, fontWeight = FontWeight.Medium, maxLines = 1, overflow = TextOverflow.Ellipsis)
                                if (currentProgram.desc.isNotEmpty()) {
                                    Spacer(modifier = Modifier.width(8.dp))
                                    Text(text = currentProgram.desc, color = oc.textSecondary.copy(alpha = 0.6f), fontSize = 11.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
                                }
                            }
                        }
                    }
                }

                if (fileLoaded) {
                    Spacer(modifier = Modifier.height(6.dp))
                    Row(modifier = Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
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
                        Text(text = progress.startLabel, color = oc.textSecondary, fontSize = 11.sp, modifier = Modifier.width(48.dp))
                        Slider(
                            value = progress.percent / 100f,
                            onValueChange = { viewModel.seekProgress(it * 100f) },
                            modifier = Modifier.weight(1f).height(20.dp),
                            colors = SliderDefaults.colors(thumbColor = oc.accent, activeTrackColor = oc.accent, inactiveTrackColor = oc.trackInactive)
                        )
                        Text(text = progress.endLabel, color = oc.textSecondary, fontSize = 11.sp, modifier = Modifier.width(48.dp))

                        if (showExitCatchup) {
                            Spacer(modifier = Modifier.width(10.dp))
                            IconButton(onClick = { viewModel.exitCatchup() }, modifier = Modifier.size(36.dp).tvFocusBorder()) {
                                Icon(Icons.AutoMirrored.Filled.Backspace, "退出回看", tint = oc.accent, modifier = Modifier.size(20.dp))
                            }
                        }
                        Spacer(modifier = Modifier.width(6.dp))
                        IconButton(onClick = { viewModel.stopPlay() }, modifier = Modifier.size(36.dp).tvFocusBorder()) {
                            Icon(Icons.Default.Stop, "停止", tint = oc.iconTint, modifier = Modifier.size(20.dp))
                        }
                    }
                }
            }
        }
    }
}


internal fun buildTvMediaBadges(mpv: com.iptv.scanner.editor.pro.player.Player, videoWidth: Int, videoHeight: Int): List<String> {
    val result = mutableListOf<String>()
    val mediaInfo = try { mpv.getMediaInfo() } catch (_: Exception) { emptyMap() }
    mediaInfo["videoCodec"]?.takeIf { it.isNotEmpty() && it != "null" }?.let { codec ->
        result.add(codec.removePrefix("video/").removePrefix("audio/").uppercase())
    }
    if (videoWidth > 0 && videoHeight > 0) {
        result.add(when { videoWidth >= 3800 -> "4K"; videoWidth >= 1900 -> "1080P"; videoWidth >= 1200 -> "720P"; else -> "${videoHeight}P" })
    }
    mediaInfo["audioCodec"]?.takeIf { it.isNotEmpty() && it != "null" }?.let { codec ->
        result.add(codec.removePrefix("audio/").uppercase())
    }
    mediaInfo["fps"]?.takeIf { it.isNotEmpty() && it != "null" && it != "0" && it != "0.000" }?.let { fps ->
        val fpsVal = fps.toFloatOrNull()
        result.add(if (fpsVal != null) "${fpsVal.toInt()}fps" else "${fps}fps")
    }
    return result.take(4)
}
