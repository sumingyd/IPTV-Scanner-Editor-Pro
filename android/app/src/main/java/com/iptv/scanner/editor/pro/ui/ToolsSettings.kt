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
internal fun PortraitToolsContent(viewModel: AppViewModel) {
    val oc = rememberPlayerOverlayColors()
    val controlsPinned by viewModel.controlsPinned.collectAsState()
    val themeMode by viewModel.themeMode.collectAsState()
    val audioVisualizerOpen by viewModel.audioVisualizerOpen.collectAsState()
    val lyricsOpen by viewModel.lyricsOpen.collectAsState()
    val playerType by viewModel.playerType.collectAsState()
    val isMpv = playerType == PlayerType.MPV

    // SAF 文件选择器 —— 打开播放列表
    val playlistLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.OpenDocument()
    ) { uri: Uri? ->
        if (uri != null) viewModel.importPlaylist(uri)
    }

    // SAF 文件选择器 —— 打开本地视频/音频
    val videoLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.OpenDocument()
    ) { uri: Uri? ->
        if (uri != null) viewModel.playLocalVideo(uri.toString())
    }

    LazyColumn(modifier = Modifier.fillMaxSize()) {
        item { PortraitSectionHeader(stringResource(R.string.tools_file), oc) }
        item {
            PortraitListRow(stringResource(R.string.tools_open_local_file), stringResource(R.string.tools_open_local_file_desc), oc) {
                if (!viewModel.isSafAvailable()) {
                    viewModel.showMediaFileBrowser()
                } else {
                    videoLauncher.launch(arrayOf("video/*", "audio/*", "application/x-matroska", "application/octet-stream"))
                }
            }
        }
        item {
            PortraitListRow(stringResource(R.string.tools_open_playlist), stringResource(R.string.tools_open_playlist_desc), oc) {
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
        }
        item {
            PortraitListRow(stringResource(R.string.tools_open_network_stream), stringResource(R.string.tools_open_network_stream_desc), oc) {
                viewModel.toggleOpenUrlDialog()
            }
        }
        item {
            PortraitListRow(stringResource(R.string.tools_recent), stringResource(R.string.tools_recent_desc), oc) { viewModel.toggleRecentPanel() }
        }
        item { PortraitSectionHeader(stringResource(R.string.tools_tools), oc) }
        item {
            PortraitListRow(stringResource(R.string.tools_screenshot), stringResource(R.string.tools_screenshot_desc), oc, disabled = !isMpv) { viewModel.takeScreenshot("video") }
        }
        item {
            PortraitListRow(stringResource(R.string.tools_clip_export), stringResource(R.string.tools_clip_export_desc), oc, disabled = !isMpv) { viewModel.toggleClipExportPanel() }
        }
        item {
            PortraitListRow(stringResource(R.string.tools_audio_visualizer), stringResource(R.string.tools_audio_visualizer_desc), oc, active = audioVisualizerOpen) { viewModel.toggleAudioVisualizer() }
        }
        item {
            PortraitListRow(stringResource(R.string.tools_lyrics), stringResource(R.string.tools_lyrics_desc), oc, active = lyricsOpen, disabled = !isMpv) { viewModel.toggleLyricsPanel() }
        }
        item {
            PortraitListRow(stringResource(R.string.tools_lock_controls), stringResource(R.string.tools_lock_controls_desc), oc, active = controlsPinned) { viewModel.toggleControlsPinned() }
        }
        item {
            PortraitListRow(stringResource(R.string.tools_refresh), stringResource(R.string.tools_refresh_desc), oc) { viewModel.refreshUi() }
        }
        item {
            PortraitListRow(stringResource(R.string.tools_save_as_m3u), stringResource(R.string.tools_save_as_m3u_desc), oc) { viewModel.saveAsM3u() }
        }
        item { PortraitSectionHeader(stringResource(R.string.tools_advanced), oc) }
        item {
            PortraitListRow(stringResource(R.string.tools_epg_timeline), stringResource(R.string.tools_epg_timeline_desc), oc) { viewModel.toggleEpgTimelinePanel() }
        }
        item {
            PortraitListRow(stringResource(R.string.tools_global_search), stringResource(R.string.tools_global_search_desc), oc) { viewModel.toggleSearchPanel() }
        }
        item {
            PortraitListRow(stringResource(R.string.tools_stream_quality), stringResource(R.string.tools_stream_quality_desc), oc, disabled = !isMpv) { viewModel.toggleStreamQualityPanel() }
        }
        item {
            PortraitListRow(stringResource(R.string.tools_url_scan), stringResource(R.string.tools_url_scan_desc), oc) { viewModel.toggleScanPanel() }
        }
        item {
            PortraitListRow(stringResource(R.string.tools_reminder), stringResource(R.string.tools_reminder_desc), oc) { viewModel.toggleReminderPanel() }
        }
        item {
            PortraitListRow(stringResource(R.string.tools_resume), stringResource(R.string.tools_resume_desc), oc) { viewModel.toggleResumePanel() }
        }
        item {
            PortraitListRow(stringResource(R.string.tools_bookmark), stringResource(R.string.tools_bookmark_desc), oc, disabled = !isMpv) { viewModel.toggleBookmarkPanel() }
        }
        item {
            PortraitListRow(stringResource(R.string.tools_av_sync), stringResource(R.string.tools_av_sync_desc), oc, disabled = !isMpv) { viewModel.toggleAvSyncPanel() }
        }
    }
}

// -----------------------------------------------------------------
// 设置内容（竖屏 Tab）
@Composable
internal fun PortraitSettingsContent(viewModel: AppViewModel) {
    val oc = rememberPlayerOverlayColors()
    val themeMode by viewModel.themeMode.collectAsState()
    val autoResume by viewModel.autoResume.collectAsState()
    val playerType by viewModel.playerType.collectAsState()
    val isMpv = playerType == PlayerType.MPV

    LazyColumn(modifier = Modifier.fillMaxSize()) {
        item { PortraitSectionHeader(stringResource(R.string.settings_playback), oc) }
        item {
            val mpvExtra = if (isMpv) stringResource(R.string.settings_mpv_config_extra) else ""
            PortraitListRow(stringResource(R.string.settings_player), stringResource(R.string.settings_player_desc, playerType.displayName, mpvExtra), oc) { viewModel.togglePlayerSettings() }
        }
        item { PortraitListRow(stringResource(R.string.settings_video), stringResource(R.string.settings_video_desc), oc) { viewModel.toggleVideoSettings() } }
        item {
            val audioDesc = if (isMpv) stringResource(R.string.settings_audio_desc_mpv) else stringResource(R.string.settings_audio_desc_exo)
            PortraitListRow(stringResource(R.string.settings_audio), audioDesc, oc) { viewModel.toggleAudioSettings() }
        }
        item { PortraitListRow(stringResource(R.string.settings_subtitle), stringResource(R.string.settings_subtitle_desc), oc, disabled = !isMpv) { viewModel.toggleSubtitleSettings() } }
        item { PortraitListRow(stringResource(R.string.settings_playback_settings), stringResource(R.string.settings_playback_desc), oc) { viewModel.togglePlaybackPanel() } }
        item { PortraitListRow(stringResource(R.string.settings_screenshot), stringResource(R.string.settings_screenshot_desc), oc, disabled = !isMpv) { viewModel.toggleScreenshotPanel() } }
        item { PortraitListRow(stringResource(R.string.settings_view), stringResource(R.string.settings_view_desc), oc) { viewModel.toggleViewSettings() } }

        item { PortraitSectionHeader(stringResource(R.string.settings_channels), oc) }
        item { PortraitListRow(stringResource(R.string.settings_source_manager), stringResource(R.string.settings_source_manager_desc), oc) { viewModel.toggleSourceManager() } }
        item { PortraitListRow(stringResource(R.string.settings_mapping), stringResource(R.string.settings_mapping_desc), oc) { viewModel.toggleMappingPanel() } }
        item { PortraitListRow(stringResource(R.string.settings_network), stringResource(R.string.settings_network_desc), oc) { viewModel.toggleNetworkPanel() } }

        item { PortraitSectionHeader(stringResource(R.string.settings_general), oc) }
        item {
            val themeLabel = when (themeMode) { "light" -> stringResource(R.string.settings_theme_light); "system" -> stringResource(R.string.settings_theme_system); else -> stringResource(R.string.settings_theme_dark) }
            PortraitListRow(stringResource(R.string.settings_theme), stringResource(R.string.settings_current, themeLabel), oc) {
                val next = when (themeMode) { "dark" -> "light"; "light" -> "system"; else -> "dark" }
                viewModel.setThemeMode(next)
            }
        }
        item {
            val resumeLabel = if (autoResume) stringResource(R.string.settings_enabled) else stringResource(R.string.settings_disabled)
            PortraitListRow(stringResource(R.string.settings_auto_resume), resumeLabel, oc, active = autoResume) {
                viewModel.setAutoResume(!autoResume)
            }
        }
        item { PortraitListRow(stringResource(R.string.settings_about), stringResource(R.string.settings_about_desc), oc) { viewModel.toggleAboutPanel() } }
    }
}

// -----------------------------------------------------------------
// 竖屏底部 Tab 栏
/** 竖屏列表行（工具/设置项通用） */
@Composable
private fun PortraitListRow(
    title: String,
    subtitle: String,
    oc: PlayerOverlayColors,
    active: Boolean = false,
    disabled: Boolean = false,
    onClick: () -> Unit
) {
    val titleColor = when {
        disabled -> oc.textSecondary.copy(alpha = 0.35f)
        active -> oc.accent
        else -> oc.textPrimary
    }
    val subColor = if (disabled) oc.textSecondary.copy(alpha = 0.25f) else oc.textSecondary
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .then(if (disabled) Modifier else Modifier.clickable(onClick = onClick))
            .padding(horizontal = 16.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = title,
                color = titleColor,
                fontSize = 14.sp,
                fontWeight = if (active) FontWeight.Medium else FontWeight.Normal
            )
            val displaySub = if (disabled && subtitle.isNotEmpty()) "$subtitle（当前内核不支持）" else subtitle
            if (displaySub.isNotEmpty()) {
                Text(
                    text = displaySub,
                    color = subColor,
                    fontSize = 12.sp,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
            }
        }
        if (active && !disabled) {
            Box(
                modifier = Modifier
                    .size(8.dp)
                    .clip(CircleShape)
                    .background(oc.accent)
            )
        }
    }
}
/** 竖屏分组标题 */
@Composable
private fun PortraitSectionHeader(
    title: String,
    oc: PlayerOverlayColors
) {
    Text(
        text = title,
        color = oc.accent,
        fontSize = 12.sp,
        fontWeight = FontWeight.Medium,
        modifier = Modifier
            .fillMaxWidth()
            .background(oc.badgeBg)
            .padding(horizontal = 16.dp, vertical = 6.dp)
    )
}

// ============================================================
// 竖屏新布局 V2 组件
