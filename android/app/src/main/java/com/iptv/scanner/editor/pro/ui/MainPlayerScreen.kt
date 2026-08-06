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
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import coil.compose.AsyncImage
import kotlinx.coroutines.delay
import com.iptv.scanner.editor.pro.data.ReminderItem
import com.iptv.scanner.editor.pro.data.UserPrefs
import com.iptv.scanner.editor.pro.data.IptvChannel
import com.iptv.scanner.editor.pro.mpv.MPVView
import com.iptv.scanner.editor.pro.mpv.MPVTextureView
import com.iptv.scanner.editor.pro.mpv.MPVViewLike
import com.iptv.scanner.editor.pro.player.PlayerType
import com.iptv.scanner.editor.pro.player.ProgressHelper
import com.iptv.scanner.editor.pro.ui.AppViewModel.ChannelTab
import com.iptv.scanner.editor.pro.ui.theme.PlayerOverlayColors
import com.iptv.scanner.editor.pro.ui.theme.rememberPlayerOverlayColors
import androidx.media3.ui.PlayerView
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
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
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.input.pointer.detectVerticalDragGestures
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.graphics.asComposeRenderEffect
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
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import java.io.File

/**
 * 主播放屏：MPVView + 透明控制层 + 面板抽屉 + OSD 浮层。
 *
 * 层次结构（从底到顶）：
 * 1. MPVView（全屏视频渲染，SurfaceView，默认 Z-order：渲染在普通 View 下方，通过透明 "打孔" 显示视频）
 * 2. 透明点击层（点击切换控制层显示/隐藏，仅当无面板打开时启用）
 * 3. 控制层（顶部侧边栏按钮 + 底部 ControlPanel，仅当 controlsVisible=true 且无面板打开时显示）
 * 4. 面板层（ChannelsPanel 右抽屉 / EpgPanel 左抽屉 / MainMenuPanel 全屏覆盖）
 * 5. OSD 浮层（顶部居中，3 秒自动隐藏，最顶层确保反馈可见）
 *
 * 与 PC 端主框架对齐：
 * - 点击视频区域切换控制层
 * - 控制层显示时，顶部有 3 个面板入口（频道列表/EPG/菜单）
 * - 控制层底部是 ControlPanel（3 行布局）
 * - 面板打开时控制层自动隐藏
 */
@Composable
fun MainPlayerScreen(viewModel: AppViewModel) {
    val uiMode by viewModel.uiMode.collectAsState()

    val controlsVisible by viewModel.controlsVisible.collectAsState()
    val channelsPanelOpen by viewModel.channelsPanelOpen.collectAsState()
    val epgPanelOpen by viewModel.epgPanelOpen.collectAsState()
    val menuPanelOpen by viewModel.menuPanelOpen.collectAsState()
    val tvUnifiedPanelOpen by viewModel.tvUnifiedPanelOpen.collectAsState()
    val fileBrowserOpen by viewModel.fileBrowserOpen.collectAsState()
    val sourceManagerOpen by viewModel.sourceManagerOpen.collectAsState()
    val playerSettingsOpen by viewModel.playerSettingsOpen.collectAsState()
    val videoSettingsOpen by viewModel.videoSettingsOpen.collectAsState()
    val audioSettingsOpen by viewModel.audioSettingsOpen.collectAsState()
    val subtitleSettingsOpen by viewModel.subtitleSettingsOpen.collectAsState()
    val subtitleSearchOpen by viewModel.subtitleSearchOpen.collectAsState()
    val playbackPanelOpen by viewModel.playbackPanelOpen.collectAsState()
    val screenshotPanelOpen by viewModel.screenshotPanelOpen.collectAsState()
    val viewSettingsOpen by viewModel.viewSettingsOpen.collectAsState()
    val aboutPanelOpen by viewModel.aboutPanelOpen.collectAsState()
    val mappingPanelOpen by viewModel.mappingPanelOpen.collectAsState()
    val avSyncPanelOpen by viewModel.avSyncPanelOpen.collectAsState()
    val networkPanelOpen by viewModel.networkPanelOpen.collectAsState()
    val toolsPanelOpen by viewModel.toolsPanelOpen.collectAsState()
    val scanPanelOpen by viewModel.scanPanelOpen.collectAsState()
    val reminderPanelOpen by viewModel.reminderPanelOpen.collectAsState()
    val resumePanelOpen by viewModel.resumePanelOpen.collectAsState()
    val bookmarkPanelOpen by viewModel.bookmarkPanelOpen.collectAsState()
    val epgTimelineOpen by viewModel.epgTimelineOpen.collectAsState()
    val searchPanelOpen by viewModel.searchPanelOpen.collectAsState()
    val streamQualityPanelOpen by viewModel.streamQualityPanelOpen.collectAsState()
    val recentPanelOpen by viewModel.recentPanelOpen.collectAsState()
    val clipExportPanelOpen by viewModel.clipExportPanelOpen.collectAsState()
    val audioVisualizerOpen by viewModel.audioVisualizerOpen.collectAsState()
    val lyricsOpen by viewModel.lyricsOpen.collectAsState()
    val exitConfirmOpen by viewModel.exitConfirmOpen.collectAsState()
    val channelInfoOpen by viewModel.channelInfoOpen.collectAsState()
    val openUrlDialogOpen by viewModel.openUrlDialogOpen.collectAsState()
    val updateDialogOpen by viewModel.updateDialogOpen.collectAsState()
    val triggeredReminder by viewModel.triggeredReminder.collectAsState()
    val osd by viewModel.osd.collectAsState()

    val player = viewModel.mpv  // 当前 Player 实例（类型为 Player 接口）
    val paused by player.paused.collectAsState()
    val videoWidth by player.videoWidth.collectAsState()
    val videoHeight by player.videoHeight.collectAsState()
    val fileLoaded by player.fileLoaded.collectAsState()
    val showHome by viewModel.showHome.collectAsState()
    val portraitTab by viewModel.portraitTab.collectAsState()
    val landscapeSidebarVisible by viewModel.landscapeSidebarVisible.collectAsState()
    val multiViewState by viewModel.multiViewState.collectAsState()

    // 系统返回键处理：侧边栏→退出多画面→返回首页→退出确认
    BackHandler(enabled = true) {
        when {
            landscapeSidebarVisible || channelsPanelOpen || epgPanelOpen || menuPanelOpen || tvUnifiedPanelOpen ||
            fileBrowserOpen || sourceManagerOpen || playerSettingsOpen || videoSettingsOpen ||
            audioSettingsOpen || subtitleSettingsOpen || subtitleSearchOpen || playbackPanelOpen ||
            screenshotPanelOpen || viewSettingsOpen || aboutPanelOpen || mappingPanelOpen ||
            avSyncPanelOpen || networkPanelOpen || toolsPanelOpen || scanPanelOpen ||
            reminderPanelOpen || resumePanelOpen || bookmarkPanelOpen || epgTimelineOpen ||
            searchPanelOpen || streamQualityPanelOpen || recentPanelOpen || clipExportPanelOpen ||
            audioVisualizerOpen || lyricsOpen || channelInfoOpen || openUrlDialogOpen -> {
                viewModel.closeAllPanels()
            }
            multiViewState.active -> {
                viewModel.exitMultiView()
            }
            !showHome -> {
                viewModel.showHomeScreen()
            }
            else -> {
                if (exitConfirmOpen) {
                    viewModel.dismissExitConfirm()
                } else {
                    viewModel.showExitConfirm()
                }
            }
        }
    }

    // SAF 文件选择器 —— 打开播放列表（M3U/M3U8）
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

    // 主题自适应覆盖颜色
    val oc = rememberPlayerOverlayColors()


    // 文件加载完成时触发续播位置恢复（与 PC 端 _on_file_loaded 对齐）
    // 同时应用 HDR 配置（与 PC 端 _apply_hdr_on_file_loaded 对齐）
    LaunchedEffect(fileLoaded) {
        if (fileLoaded) {
            val url = viewModel.getCurrentPlaybackUrl()
            if (url.isNotEmpty()) {
                viewModel.onFileLoadedForResume(url)
            }
            // 应用 HDR 配置（检测视频是否 HDR 并按当前模式应用）
            viewModel.applyHdrOnFileLoaded()
        }
    }

    // 所有模式初始自动隐藏控制面板（几秒后自动隐藏，避免一直显示）
    LaunchedEffect(uiMode) {
        viewModel.showControlsAutoHide()
    }

    // 视频宽高比：用于 SurfaceView 比例保持（解决竖屏下视频被拉长铺满的问题）。
    // 根因：vo=mediacodec_embed 直接用 MediaCodec 渲染到 Surface buffer，不经过 GPU 渲染管线，
    // mpv 的 keepaspect/keepaspect-window 选项对 mediacodec_embed 不生效。
    // 如果 SurfaceView 全屏（fillMaxSize），Surface buffer 是全屏尺寸（如竖屏 1440x2984），
    // MediaCodec 会把视频帧拉伸到 buffer 尺寸，破坏 16:9 比例。
    // 用 aspectRatio modifier 限制 SurfaceView 尺寸，让 Surface buffer 匹配视频比例，
    // 视频会居中显示并保持比例（上下/左右黑边）。
    // vo=gpu 时也兼容（mpv 内部 keepaspect 已处理，aspectRatio 只影响 SurfaceView 外框，不影响渲染）。
    val aspectRatio = if (videoWidth > 0 && videoHeight > 0) {
        videoWidth.toFloat() / videoHeight.toFloat()
    } else {
        16f / 9f  // 默认 16:9（未加载时）
    }

    val anyPanelOpen by viewModel.anyPanelOpenFlow.collectAsState()
    val showControls = controlsVisible && !anyPanelOpen

    val anyFullScreenPanel by remember {
        derivedStateOf {
            menuPanelOpen || sourceManagerOpen || playerSettingsOpen ||
                    videoSettingsOpen || audioSettingsOpen || subtitleSettingsOpen || subtitleSearchOpen ||
                    playbackPanelOpen || screenshotPanelOpen || viewSettingsOpen || aboutPanelOpen ||
                    mappingPanelOpen || avSyncPanelOpen || networkPanelOpen || toolsPanelOpen || scanPanelOpen ||
                    reminderPanelOpen || resumePanelOpen || bookmarkPanelOpen ||
                    epgTimelineOpen || searchPanelOpen || streamQualityPanelOpen ||
                    recentPanelOpen || clipExportPanelOpen || audioVisualizerOpen || lyricsOpen ||
                    exitConfirmOpen || openUrlDialogOpen || updateDialogOpen ||
                    channelInfoOpen
        }
    }
    val configuration = LocalConfiguration.current
    val isPortrait = configuration.orientation == Configuration.ORIENTATION_PORTRAIT
    // 竖屏 PHONE 模式：默认上下分屏（视频 16:9 + 频道列表）
    val portraitSplit = uiMode.isPhone && isPortrait && !multiViewState.active
    // 横屏 PHONE 模式：使用 compact 抽屉
    val landscapeCompact = uiMode.isPhone && !isPortrait

// -----------------------------------------------------------------
// 屏幕旋转修复：检测方向变化，恢复播放
//
// 根因：movableContentOf 在竖屏→横屏切换时可能销毁旧 AndroidView（onRelease→destroy），
// destroy() 中 stop + playlist-clear 清除了播放状态。虽然 MPVView.destroy() 会保存
// savedPlaybackPath 供新 MPVView 恢复，但如果不触发 AndroidView 重建（movableContentOf
// 保留了 View），则只有 surfaceDestroyed→surfaceCreated。
//
// surfaceCreated 现在会重新 loadfile 恢复渲染（与 TextureView 行为对齐）。
// suppressFileErrorFlag 由 onSurfaceAboutToDestroy 设置，onSurfaceRebuilt 延迟清除。
//
// 本 LaunchedEffect 作为兜底：延迟检查视频是否恢复，未恢复则重新加载文件。
// -----------------------------------------------------------------
LaunchedEffect(isPortrait) {
if (viewModel.playerType.value == PlayerType.MPV && viewModel.mpv.fileLoaded.value) {
Log.i("MainPlayerScreen", "Rotation detected: isPortrait=$isPortrait")
// 等待 surfaceCreated 完成 VO 重建 + loadfile
kotlinx.coroutines.delay(800)
// 兜底检查：如果视频仍未恢复，尝试重新加载
val path = viewModel.mpvGetPath()
val w = viewModel.mpv.videoWidth.value
val h = viewModel.mpv.videoHeight.value
Log.i("MainPlayerScreen", "After rotation: path=$path, ${w}x${h}")
if (path.isNotEmpty() && (w == 0 || h == 0)) {
Log.i("MainPlayerScreen", "Video not restored after rotation, reloading: $path")
viewModel.mpvSuppressFileError()
viewModel.mpv.playFile(path)
kotlinx.coroutines.delay(500)
viewModel.mpvClearSuppressFileError()
} else if (path.isEmpty()) {
val savedPath = com.iptv.scanner.editor.pro.mpv.MPVView.savedPlaybackPath
if (savedPath != null) {
Log.i("MainPlayerScreen", "Path empty after rotation, restoring from saved: $savedPath")
viewModel.mpvSuppressFileError()
viewModel.mpv.playFile(savedPath)
kotlinx.coroutines.delay(500)
viewModel.mpvClearSuppressFileError()
}
}
}
}

    Box(
        modifier = Modifier
            .fillMaxSize()
            // 关键：不能设置不透明 background！
            // SurfaceView 默认 Z-order 在普通 View 后面，不透明 background 会遮挡视频画面
            // 黑色背景由 Activity window background + SurfaceView 自身提供
    ) {
        val playerType by viewModel.playerType.collectAsState()
        // rememberUpdatedState：确保 movableContentOf 内部的 lambda 始终引用最新的 playerType
        // （movableContentOf 被 remember 缓存后，内部 lambda 不会随外层 recompose 自动更新）
        val playerTypeUpdated = rememberUpdatedState(playerType)

        // -----------------------------------------------------------------
        // 1. 底层：播放器 View 容器
        //
        // 关键设计：不使用 key(playerType) 重建视图！
        // 而是用一个 FrameLayout 容器，根据 playerType 动态切换子 View。
        // 这样切换内核时视图不会销毁重建，只是替换子 View + attachView。
        // -----------------------------------------------------------------
        val createPlayerView: (android.content.Context) -> android.view.View = { ctx ->
            // 创建容器
            val container = android.widget.FrameLayout(ctx)
            container
        }

        // update 回调：每次 playerType 变化时执行，动态替换子 View
        val updatePlayerView: (android.view.View) -> Unit = view@ { container ->
            if (container !is android.widget.FrameLayout) return@view
            val ctx = container.context
            val pType = playerTypeUpdated.value
            val player = viewModel.mpv

            // 检查当前容器中的子 View 是否已匹配 playerType
            val currentChild = container.getChildAt(0)
            val childMatches = when {
                currentChild is MPVViewLike -> pType == PlayerType.MPV
                currentChild is PlayerView -> pType == PlayerType.EXO
                else -> false
            }
            if (childMatches) return@view  // 已匹配，无需切换

            // 移除旧子 View（不调用 detach/destroy，只从容器移除）
            if (currentChild != null) {
                container.removeView(currentChild)
                Log.i("MainPlayerScreen", "Removed old player view: ${currentChild.javaClass.simpleName}")
            }

            // 创建新子 View 并 attach
            when (pType) {
                PlayerType.MPV -> {
                    // 始终使用 SurfaceView（MPVView）。
                    // TextureView 在部分设备上 GPU vo 无法渲染（如华为 LYA-AL00），
                    // SurfaceView + mediacodec_embed 可以直接用 MediaCodec 渲染到 Surface。
                    val mpvView: MPVViewLike = MPVView(ctx)
                    val configDir = ctx.getDir("mpv_config", Context.MODE_PRIVATE).absolutePath
                    val cacheDir = ctx.cacheDir.absolutePath
                    val userPrefs = UserPrefs.getInstance()
                    try {
                        mpvView.initialize(configDir, cacheDir, vo = userPrefs.getVo(), hwdec = userPrefs.getHwdec())
                        player.attachView(mpvView)
                        Log.i("MainPlayerScreen", "MPVView attached in container")
                    } catch (e: Throwable) {
                        Log.e("MainPlayerScreen", "MPVView init failed", e)
                    }
                    val view = mpvView.asView()
                    container.addView(view, android.widget.FrameLayout.LayoutParams(
                        android.widget.FrameLayout.LayoutParams.MATCH_PARENT,
                        android.widget.FrameLayout.LayoutParams.MATCH_PARENT
                    ))
                    // attachView 完成后，检查是否有待播放的 URL
                    val pendingUrl = viewModel.pendingSwitchPlayUrl.value
                    if (pendingUrl.isNotEmpty()) {
                        viewModel.clearPendingSwitchPlayUrl()
                        view.post {
                            Log.i("MainPlayerScreen", "playFile after MPV attach: $pendingUrl")
                            viewModel.mpv.playFile(pendingUrl)
                        }
                    }
                }
                PlayerType.EXO -> {
                    val exoView = android.view.LayoutInflater.from(ctx)
                        .inflate(com.iptv.scanner.editor.pro.R.layout.exo_player_texture_view, null) as PlayerView
                    player.attachView(exoView)
                    Log.i("MainPlayerScreen", "PlayerView (TextureView) attached in container, type=$pType")
                    container.addView(exoView, android.widget.FrameLayout.LayoutParams(
                        android.widget.FrameLayout.LayoutParams.MATCH_PARENT,
                        android.widget.FrameLayout.LayoutParams.MATCH_PARENT
                    ))
                    // attachView 完成后，检查是否有待播放的 URL
                    val pendingUrl = viewModel.pendingSwitchPlayUrl.value
                    if (pendingUrl.isNotEmpty()) {
                        viewModel.clearPendingSwitchPlayUrl()
                        exoView.post {
                            Log.i("MainPlayerScreen", "playFile after EXO attach: $pendingUrl")
                            viewModel.mpv.playFile(pendingUrl)
                        }
                    }
                }
            }
        }

        val onReleasePlayer: (android.view.View) -> Unit = { container ->
            // 容器销毁时，清理子 View
            if (container is android.widget.FrameLayout) {
                for (i in 0 until container.childCount) {
                    val child = container.getChildAt(i)
                    when (child) {
                        is MPVViewLike -> child.destroy()
                        is PlayerView -> child.player = null
                    }
                }
                container.removeAllViews()
            }
            Log.i("MainPlayerScreen", "onRelease: container destroyed")
        }

        // 关键：不使用 remember(portraitSplit)！
        // portraitSplit 变化（竖屏→横屏旋转）时会创建新的 movableContentOf，
        // 导致旧的 AndroidView 被 dispose（onRelease → MPVView.destroy() → stop + playlist-clear），
        // 新的 AndroidView 创建新 MPVView 但文件已被 stop，surfaceCreated 时 path 为空 → 黑屏。
        //
        // 使用 remember（无 key）让同一个 movableContentOf 在竖屏/横屏布局之间移动，
        // SurfaceView 被 reparent 时只触发 surfaceDestroyed → surfaceCreated 生命周期，
        // MPVView 在 surfaceCreated 中检测到 path 非空会自动恢复渲染，无需重新 loadfile。
        val primaryPlayer = remember {
            movableContentOf {
                AndroidView(
                    factory = createPlayerView,
                    update = updatePlayerView,
                    onRelease = onReleasePlayer,
                    modifier = Modifier.fillMaxSize()
                )
            }
        }

            // -----------------------------------------------------------------
            // 布局：PHONE 竖屏 = 上下分屏 | PHONE 横屏 / TV = 全屏 + 抽屉
            //
            // 竖屏分屏：视频 16:9（fillMaxWidth + aspectRatio）+ 频道列表填满剩余
            // 横屏全屏：视频居中 + compact 抽屉（频道/EPG 宽度 1/4，无标题无搜索）
            // TV 全屏：视频居中 + 统一面板（DPAD 导航）
            // -----------------------------------------------------------------
            if (portraitSplit) {

                // ---- 竖屏布局 ----
                // 播放器始终在固定位置渲染（16:9 视频区域），不移动。
                // showHome=true 时首页 UI 覆盖播放器（不透明背景完全遮盖，但 Surface 活跃）。
                // showHome=false 时播放器正常显示。
                // 这避免了 movableContentOf 移动 SurfaceView 导致的 surface 销毁/重建，
                // 彻底解决返回播放页无画面问题。
                Box(modifier = Modifier.fillMaxSize().systemBarsPadding()) {
                    // 播放器 + 控制栏（始终在组合树中，Surface 不被销毁）
                    Column(modifier = Modifier.fillMaxSize()) {
                        PortraitInfoBarV2(viewModel = viewModel)
                        Box(modifier = Modifier.fillMaxWidth().height(1.dp).background(oc.divider))
                        Box(
                            modifier = Modifier
                                .fillMaxWidth()
                                .aspectRatio(16f / 9f)
                                .background(Color.Black)
                        ) {
                            primaryPlayer()
                            // 竖屏快速换台：向上滑动=上一频道，向下滑动=下一频道
                            if (!showHome && !anyPanelOpen) {
                                val haptic = androidx.compose.ui.platform.LocalHapticFeedback.current
                                Box(
                                    modifier = Modifier
                                        .fillMaxSize()
                                        .pointerInput(Unit) {
                                            var totalY = 0f
                                            var triggered = false
                                            detectVerticalDragGestures(
                                                onDragStart = {
                                                    totalY = 0f
                                                    triggered = false
                                                },
                                                onDragEnd = {
                                                    totalY = 0f
                                                    triggered = false
                                                },
                                                onVerticalDrag = { change, dragAmount ->
                                                    change.consume()
                                                    totalY += dragAmount
                                                    val threshold = 80f
                                                    if (!triggered && kotlin.math.abs(totalY) > threshold) {
                                                        triggered = true
                                                        if (totalY < 0) {
                                                            viewModel.prevChannel()
                                                        } else {
                                                            viewModel.nextChannel()
                                                        }
                                                        haptic.performHapticFeedback(androidx.compose.ui.hapticfeedback.HapticFeedbackType.LongPress)
                                                    }
                                                }
                                            )
                                        }
                                )
                            }
                        }
                        PortraitMediaInfoBar(viewModel = viewModel)
                        PortraitControlsV2(viewModel = viewModel)
                        Box(modifier = Modifier.fillMaxWidth().height(1.dp).background(oc.divider))
                        Box(
                            modifier = Modifier
                                .fillMaxWidth()
                                .weight(1f)
                                .background(MaterialTheme.colorScheme.background)
                        ) {
                            PortraitPlayerDynamicContent(viewModel = viewModel)
                        }
                    }

                    if (showHome) {
                        // 首页 UI 覆盖播放器（不透明背景完全遮盖播放器）
                        Column(
                            modifier = Modifier
                                .fillMaxSize()
                                .background(MaterialTheme.colorScheme.background)
                        ) {
                            // 迷你播放器条
                            val fileLoaded2 by viewModel.mpv.fileLoaded.collectAsState()
                            val currentCh by viewModel.currentChannel.collectAsState()
                            val displayInfo by viewModel.channelDisplayInfo.collectAsState()
                            val paused2 by viewModel.mpv.paused.collectAsState()
                            // 频道播放：currentCh 不为 null；本地视频：currentCh 为 null 但 displayInfo.name 有值
                            val hasMini = fileLoaded2 && (currentCh != null || displayInfo.name.isNotEmpty())
                            if (hasMini) {
                                MiniPlayerBar(
                                    viewModel = viewModel,
                                    channelName = currentCh?.name ?: displayInfo.name,
                                    channelLogo = currentCh?.logo ?: "",
                                    groupName = currentCh?.group ?: "",
                                    isPaused = paused2,
                                    onClick = { viewModel.showPlayerScreen() },
                                    onPlayPause = { viewModel.mpv.togglePause() }
                                )
                            }
                            // 内容区域
                            Box(modifier = Modifier.weight(1f)) {
                                when (portraitTab) {
                                    AppViewModel.PortraitTab.HOME -> PortraitHomeScreen(
                                        viewModel = viewModel,
                                        playlistLauncher = playlistLauncher,
                                        videoLauncher = videoLauncher
                                    )
                                    AppViewModel.PortraitTab.LIST -> PortraitListScreen(
                                        viewModel = viewModel,
                                        playlistLauncher = playlistLauncher,
                                        videoLauncher = videoLauncher
                                    )
                                    AppViewModel.PortraitTab.TOOLS -> PortraitToolsContent(viewModel = viewModel)
                                    AppViewModel.PortraitTab.SETTINGS -> PortraitSettingsContent(viewModel = viewModel)
                                }
                            }
                            PortraitBottomTabBar(viewModel = viewModel)
                        }
                    }
                }
            } else {
                // ---- 非竖屏模式 ----

                if (landscapeCompact) {
                    // ---- PHONE 横屏：沉浸式侧边栏布局 ----
                    LandscapePlayerLayout(
                        viewModel = viewModel,
                        primaryPlayer = { primaryPlayer() },
                        videoAspectRatio = aspectRatio
                    )
                } else if (multiViewState.active) {
                    // ---- TV 多画面模式：沉浸式侧边栏 + 底栏 ----
                    TvPlayerLayout(
                        viewModel = viewModel,
                        primaryPlayer = {
                            MultiViewOverlay(
                                state = multiViewState,
                                primaryContent = { primaryPlayer() },
                                getSubPlayer = { idx -> viewModel.getSubPlayer(idx) },
                                onViewportClick = { idx ->
                                    viewModel.setFocusedViewport(idx)
                                    val viewport = multiViewState.viewports.getOrNull(idx)
                                    if (viewport != null && viewport.isEmpty) {
                                        viewModel.setLandscapeSidebarVisible(true)
                                    }
                                },
                                onViewportClose = { idx -> viewModel.removeFromMultiView(idx) },
                                onToggleMute = { idx -> viewModel.toggleMultiViewMute(idx) }
                            )
                        },
                        videoAspectRatio = aspectRatio
                    )
                } else {
                    // ---- TV 单画面模式：沉浸式侧边栏 + 底栏 ----
                    TvPlayerLayout(
                        viewModel = viewModel,
                        primaryPlayer = { primaryPlayer() },
                        videoAspectRatio = aspectRatio
                    )
                }
            }

        // 主菜单（全屏覆盖）— 仅 PHONE 模式使用
        if (menuPanelOpen && !uiMode.isTV) {
            MainMenuPanel(viewModel = viewModel)
        }

        // TV 端统一面板（三列：模式切换 + 频道列表/主菜单 + EPG 节目单）
        if (tvUnifiedPanelOpen) {
            TvUnifiedPanel(viewModel = viewModel)
        }

        // 频道列表面板（菜单 → 频道列表）
        // 渲染在 TvUnifiedPanel 之后，覆盖在视频之上；自带的 PanelHeader 提供关闭按钮
        if (channelsPanelOpen) {
            ChannelsPanel(viewModel = viewModel)
        }

        // 节目单面板（菜单 → 节目单 EPG）
        if (epgPanelOpen) {
            EpgPanel(viewModel = viewModel)
        }

        // 文件浏览器（全屏覆盖，SAF 不可用时的替代方案）
        if (fileBrowserOpen) {
            FileBrowserPanel(viewModel = viewModel)
        }

        // 订阅源管理
        if (sourceManagerOpen) {
            PortraitPanelDialog(onDismiss = { viewModel.toggleSourceManager() }) {
                SourceManagerPanel(viewModel = viewModel)
            }
        }

        // 播放器设置
        if (playerSettingsOpen) {
            PortraitPanelDialog(onDismiss = { viewModel.togglePlayerSettings() }) {
                PlayerSettingsPanel(viewModel = viewModel)
            }
        }

        // 视频设置
        if (videoSettingsOpen) {
            PortraitPanelDialog(onDismiss = { viewModel.toggleVideoSettings() }) {
                VideoSettingsPanel(viewModel = viewModel)
            }
        }

        // 音频设置
        if (audioSettingsOpen) {
            PortraitPanelDialog(onDismiss = { viewModel.toggleAudioSettings() }) {
                AudioSettingsPanel(viewModel = viewModel)
            }
        }

        // 字幕设置
        if (subtitleSettingsOpen) {
            PortraitPanelDialog(onDismiss = { viewModel.toggleSubtitleSettings() }) {
                SubtitleSettingsPanel(viewModel = viewModel)
            }
        }
        if (subtitleSearchOpen) {
            PortraitPanelDialog(onDismiss = { viewModel.toggleSubtitleSearchPanel() }) {
                SubtitleSearchPanel(viewModel = viewModel)
            }
        }

        // 播放设置
        if (playbackPanelOpen) {
            PortraitPanelDialog(onDismiss = { viewModel.togglePlaybackPanel() }) {
                PlaybackPanel(viewModel = viewModel)
            }
        }

        // 截图
        if (screenshotPanelOpen) {
            PortraitPanelDialog(onDismiss = { viewModel.toggleScreenshotPanel() }) {
                ScreenshotPanel(viewModel = viewModel)
            }
        }

        // 视图设置
        if (viewSettingsOpen) {
            PortraitPanelDialog(onDismiss = { viewModel.toggleViewSettings() }) {
                ViewSettingsPanel(viewModel = viewModel)
            }
        }

        // 关于
        if (aboutPanelOpen) {
            PortraitPanelDialog(onDismiss = { viewModel.toggleAboutPanel() }) {
                AboutPanel(viewModel = viewModel)
            }
        }

        // 频道映射
        if (mappingPanelOpen) {
            PortraitPanelDialog(onDismiss = { viewModel.toggleMappingPanel() }) {
                MappingPanel(viewModel = viewModel)
            }
        }

        // A/V 同步监控
        if (avSyncPanelOpen) {
            PortraitPanelDialog(onDismiss = { viewModel.toggleAvSyncPanel() }) {
                AvSyncPanel(viewModel = viewModel)
            }
        }

        // 网络增强
        if (networkPanelOpen) {
            PortraitPanelDialog(onDismiss = { viewModel.toggleNetworkPanel() }) {
                NetworkPanel(viewModel = viewModel)
            }
        }

        // 工具
        if (toolsPanelOpen) {
            PortraitPanelDialog(onDismiss = { viewModel.toggleToolsPanel() }) {
                ToolsPanel(viewModel = viewModel)
            }
        }

        // URL 范围扫描
        if (scanPanelOpen) {
            PortraitPanelDialog(onDismiss = { viewModel.toggleScanPanel() }) {
                ScanPanel(viewModel = viewModel)
            }
        }

        // 节目提醒管理
        if (reminderPanelOpen) {
            PortraitPanelDialog(onDismiss = { viewModel.toggleReminderPanel() }) {
                ReminderPanel(viewModel = viewModel)
            }
        }

        // 续播位置管理
        if (resumePanelOpen) {
            PortraitPanelDialog(onDismiss = { viewModel.toggleResumePanel() }) {
                ResumePanel(viewModel = viewModel)
            }
        }

        // 书签管理
        if (bookmarkPanelOpen) {
            PortraitPanelDialog(onDismiss = { viewModel.toggleBookmarkPanel() }) {
                BookmarkPanel(viewModel = viewModel)
            }
        }

        // EPG 时间线视图
        if (epgTimelineOpen) {
            PortraitPanelDialog(onDismiss = { viewModel.toggleEpgTimelinePanel() }) {
                EpgTimelinePanel(viewModel = viewModel)
            }
        }

        // 全局搜索
        if (searchPanelOpen) {
            PortraitPanelDialog(onDismiss = { viewModel.toggleSearchPanel() }) {
                SearchPanel(viewModel = viewModel)
            }
        }

        // 流质量检测
        if (streamQualityPanelOpen) {
            PortraitPanelDialog(onDismiss = { viewModel.toggleStreamQualityPanel() }) {
                StreamQualityPanel(viewModel = viewModel)
            }
        }

        // 最近打开
        if (recentPanelOpen) {
            PortraitPanelDialog(onDismiss = { viewModel.toggleRecentPanel() }) {
                RecentFilesPanel(viewModel = viewModel)
            }
        }

// 切片导出
if (clipExportPanelOpen) {
    PortraitPanelDialog(onDismiss = { viewModel.toggleClipExportPanel() }) {
        ClipExportPanel(viewModel = viewModel)
    }
}

// 音频可视化
if (audioVisualizerOpen) {
    PortraitPanelDialog(onDismiss = { viewModel.toggleAudioVisualizer() }) {
        AudioVisualizerPanel(viewModel = viewModel)
    }
}

// 歌词
if (lyricsOpen) {
    PortraitPanelDialog(onDismiss = { viewModel.toggleLyricsPanel() }) {
        LyricsPanel(viewModel = viewModel)
    }
}

        // 提醒触发弹窗（节目即将开始时弹出，全屏遮罩）
        if (triggeredReminder != null) {
            ReminderPopup(
                reminder = triggeredReminder!!,
                onAccept = { viewModel.acceptTriggeredReminder() },
                onDismiss = { viewModel.dismissTriggeredReminder() }
            )
        }

        // 打开网络流 URL 对话框（AlertDialog，独立 window，自身控制可见性）
        OpenUrlDialog(viewModel = viewModel)

        // 新版本更新提示对话框（发现新版本时自动弹出，也可从"关于"面板手动触发）
        UpdateDialog(viewModel = viewModel)

        // 退出确认对话框（BACK 键退出时提示：立即退出 / 进入 PiP）
        ExitConfirmDialog(viewModel = viewModel)

        // 频道信息详情对话框（信息栏"信息"按钮触发）
        if (channelInfoOpen) {
            ChannelInfoDialog(viewModel = viewModel)
        }

        // -----------------------------------------------------------------
        // 5. OSD 浮层（顶部居中，最顶层）— 竖屏模式下不显示
        // -----------------------------------------------------------------
        if (!portraitSplit) {
        AnimatedVisibility(
            visible = osd != null,
            enter = fadeIn(),
            exit = fadeOut(),
            modifier = Modifier.align(Alignment.TopCenter)
        ) {
            osd?.let { info ->
                OsdView(
                    title = info.title,
                    subtitle = info.subtitle,
                    extra = info.extra
                )
            }
        }
        }
    }
}

// -----------------------------------------------------------------
// 顶部信息条 + 面板入口按钮
// -----------------------------------------------------------------

@Composable
private fun TopBar(
    channelName: String,
    mode: String,
    paused: Boolean,
    isTV: Boolean,
    onChannelsClick: () -> Unit,
    onEpgClick: () -> Unit,
    onMenuClick: () -> Unit
) {
    val oc = rememberPlayerOverlayColors()
    Surface(
        color = oc.topBarBg,
        modifier = Modifier.fillMaxWidth()
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 8.dp, vertical = 6.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            // 左侧：频道名 + 暂停状态
            Row(
                verticalAlignment = Alignment.CenterVertically,
                modifier = Modifier.weight(1f)
            ) {
                Text(
                    text = channelName,
                    style = MaterialTheme.typography.titleMedium,
                    color = oc.textPrimary,
                    fontWeight = FontWeight.Medium,
                    maxLines = 1
                )
                if (paused) {
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = "（已暂停）",
                        color = oc.iconTintActive,
                        fontSize = 12.sp
                    )
                }
            }

            // 右侧：面板入口按钮（TV 模式下隐藏，由 MENU 键和方向键替代）
            if (!isTV) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    IconButton(onClick = onChannelsClick) {
                        Icon(
                            Icons.Default.VideoLibrary,
                            contentDescription = "频道列表",
                            tint = oc.iconTint
                        )
                    }
                    IconButton(onClick = onEpgClick) {
                        Icon(
                            Icons.Default.CalendarMonth,
                            contentDescription = "EPG 节目单",
                            tint = oc.iconTint
                        )
                    }
                    IconButton(onClick = onMenuClick) {
                        Icon(
                            Icons.Default.Menu,
                            contentDescription = "主菜单",
                            tint = oc.iconTint
                        )
                    }
                }
            }
            Spacer(modifier = Modifier.width(4.dp))
            Text(
                text = mode,
                style = MaterialTheme.typography.labelSmall,
                color = oc.textSecondary
            )
        }
    }
}

// -----------------------------------------------------------------
// 分屏模式视频区域（独立 composable，避免 ColumnScope/RowScope 与 AnimatedVisibility 冲突）
// -----------------------------------------------------------------

@Composable
private fun SplitVideoArea(
    primaryPlayer: @Composable () -> Unit,
    aspectRatio: Float,
    showControls: Boolean,
    anyPanelOpen: Boolean,
    paused: Boolean,
    viewModel: AppViewModel,
    modifier: Modifier = Modifier
) {
    val mpv = viewModel.mpv
    val muted by mpv.muted.collectAsState()
    val volume by mpv.volume.collectAsState()
    val showExitCatchup by viewModel.showExitCatchup.collectAsState()
    val playbackState by viewModel.playbackState.collectAsState()
    val oc = rememberPlayerOverlayColors()

    Box(
        modifier = modifier
            .background(Color.Black)
    ) {
        // 播放器（居中保持比例）
        Box(
            modifier = Modifier
                .align(Alignment.Center)
                .aspectRatio(aspectRatio)
        ) {
            primaryPlayer()
        }
        // 点击层：点击切换控制层显示/隐藏
        if (!anyPanelOpen) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .clickable { viewModel.toggleControls() }
            )
        }
        // 控制层（简化版：右上角菜单按钮 + QuickActionBar + 底部播放控制）
        AnimatedVisibility(
            visible = showControls,
            enter = fadeIn(),
            exit = fadeOut()
        ) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .background(oc.scrim)
            ) {
                Box(
                    modifier = Modifier
                        .fillMaxSize()
                ) {
                    // 右上角：菜单按钮
                    IconButton(
                        onClick = { viewModel.showMenuPanel() },
                        modifier = Modifier
                            .align(Alignment.TopEnd)
                            .padding(8.dp)
                    ) {
                        Icon(
                            Icons.Default.Menu,
                            contentDescription = "主菜单",
                            tint = oc.iconTint
                        )
                    }
                    // 底部控制栏：QuickActionBar + 进度条 + 控制按钮
                    Column(
                        modifier = Modifier
                            .align(Alignment.BottomCenter)
                            .fillMaxWidth()
                    ) {
                        // 快捷工具栏
                        QuickActionBar(
                            viewModel = viewModel,
                            orientation = QuickActionBarOrientation.Portrait
                        )
                        // 进度条
                        PortraitProgressBar(viewModel = viewModel)
                        // 控制按钮行
                        PortraitControlButtons(
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
        }
    }
}

/**
 * 竖屏信息栏：频道名 + 台标 + 媒体信息 + EPG + EPG查看按钮
 */
@Composable
private fun PortraitInfoBar(viewModel: AppViewModel) {
    val currentChannel by viewModel.currentChannel.collectAsState()
    val mpv = viewModel.mpv
    val videoWidth by mpv.videoWidth.collectAsState()
    val videoHeight by mpv.videoHeight.collectAsState()
    val fileLoaded by mpv.fileLoaded.collectAsState()
    val playbackState by viewModel.playbackState.collectAsState()
    val oc = rememberPlayerOverlayColors()

    // 当前 EPG 节目（2秒刷新）
    var currentProgram by remember { mutableStateOf<com.iptv.scanner.editor.pro.data.IptvEpgProgram?>(null) }
    LaunchedEffect(Unit) {
        while (true) {
            currentProgram = viewModel.getCurrentProgram()
            delay(2_000L)
        }
    }

    // 媒体徽章数据（1秒刷新）
    var mediaTick by remember { mutableStateOf(0L) }
    LaunchedEffect(fileLoaded) {
        while (fileLoaded) {
            mediaTick = System.currentTimeMillis()
            delay(1_000L)
        }
    }

    Surface(
        color = oc.infoBarBg,
        modifier = Modifier.fillMaxWidth()
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 12.dp, vertical = 6.dp)
        ) {
            // 第一行：台标 + 频道名 + EPG节目 + EPG查看按钮
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically
            ) {
                // 台标
                if (currentChannel != null && currentChannel!!.logo.isNotEmpty()) {
                    AsyncImage(
                        model = currentChannel!!.logo,
                        contentDescription = currentChannel!!.name,
                        modifier = Modifier
                            .size(32.dp)
                            .clip(RoundedCornerShape(4.dp)),
                        contentScale = ContentScale.Fit
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                }
                // 频道名 + EPG节目名
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = currentChannel?.name ?: "未选择频道",
                        color = oc.textPrimary,
                        fontSize = 14.sp,
                        fontWeight = FontWeight.Medium,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                    if (currentProgram != null && currentProgram!!.title.isNotEmpty()) {
                        Text(
                            text = currentProgram!!.title,
                            color = oc.textSecondary,
                            fontSize = 12.sp,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis
                        )
                    } else if (currentChannel != null && currentChannel!!.group.isNotEmpty()) {
                        Text(
                            text = currentChannel!!.group,
                            color = oc.textSecondary,
                            fontSize = 12.sp,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis
                        )
                    }
                }
                // 回看/时移指示器
                if (playbackState.mode.isCatchupOrTimeshift) {
                    val indicatorText = when (playbackState.mode) {
                        com.iptv.scanner.editor.pro.player.PlayMode.CATCHUP -> "回看"
                        com.iptv.scanner.editor.pro.player.PlayMode.TIMESHIFT -> "时移"
                        else -> ""
                    }
                    Surface(
                        color = oc.iconTintActive.copy(alpha = 0.15f),
                        shape = RoundedCornerShape(4.dp),
                        modifier = Modifier.clip(RoundedCornerShape(4.dp)).padding(end = 4.dp)
                    ) {
                        Text(
                            text = indicatorText,
                            color = oc.iconTintActive,
                            fontSize = 10.sp,
                            modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp)
                        )
                    }
                }
                // EPG 查看按钮
                IconButton(
                    onClick = { viewModel.showEpgPanel() },
                    modifier = Modifier.size(36.dp)
                ) {
                    Icon(
                        Icons.Default.CalendarMonth,
                        contentDescription = "查看EPG",
                        tint = oc.accent,
                        modifier = Modifier.size(22.dp)
                    )
                }
            }
            // 第二行：媒体信息徽章（紧凑显示）
            if (fileLoaded) {
                val mediaInfo = remember(mediaTick, videoWidth, videoHeight) {
                    buildPortraitMediaInfo(mpv, videoWidth, videoHeight)
                }
                if (mediaInfo.isNotEmpty()) {
                    Row(
                        modifier = Modifier.fillMaxWidth().padding(top = 2.dp),
                        horizontalArrangement = Arrangement.spacedBy(6.dp)
                    ) {
                        mediaInfo.take(3).forEach { info ->
                            Surface(
                                color = oc.badgeBg,
                                shape = RoundedCornerShape(4.dp),
                                modifier = Modifier.clip(RoundedCornerShape(4.dp))
                            ) {
                                Text(
                                    text = info,
                                    color = oc.badgeText,
                                    fontSize = 10.sp,
                                    modifier = Modifier.padding(horizontal = 5.dp, vertical = 1.dp),
                                    maxLines = 1
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}

/** 构建竖屏媒体信息（最多3条：分辨率+编解码、音频、网络） */
private fun buildPortraitMediaInfo(
    mpv: com.iptv.scanner.editor.pro.player.Player,
    videoWidth: Int,
    videoHeight: Int
): List<String> {
    val result = mutableListOf<String>()
    // 视频：编解码器 + 分辨率
    val vcodec = mpv.getPropertyString("video-codec") ?: ""
    val codecName = vcodec.split(" ").firstOrNull()?.takeIf { it.isNotEmpty() } ?: ""
    val resStr = if (videoWidth > 0 && videoHeight > 0) "${videoWidth}x${videoHeight}" else ""
    val videoInfo = listOfNotNull(
        codecName.takeIf { it.isNotEmpty() },
        resStr.takeIf { it.isNotEmpty() }
    ).joinToString(" ")
    if (videoInfo.isNotEmpty()) result.add(videoInfo)
    // 音频
    val acodec = mpv.getPropertyString("audio-codec") ?: ""
    if (acodec.isNotEmpty()) {
        val aName = acodec.split(" ").firstOrNull() ?: acodec
        result.add(aName)
    }
    // 网络/协议
    val protocol = mpv.getPropertyString("file-format") ?: mpv.getPropertyString("stream-open") ?: ""
    if (protocol.isNotEmpty()) {
        result.add(protocol.take(10))
    }
    return result
}

/** 竖屏进度条（精简版） */
@Composable
private fun PortraitProgressBar(viewModel: AppViewModel) {
    val oc = rememberPlayerOverlayColors()
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
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 12.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(
            text = progressInfo.startLabel,
            color = oc.textSecondary,
            fontSize = 10.sp
        )
        Slider(
            value = if (dragging) dragPercent else (progressInfo.percent / 100f),
            onValueChange = { dragging = true; dragPercent = it },
            onValueChangeFinished = {
                viewModel.seekProgress(dragPercent * 100f)
                dragging = false
            },
            modifier = Modifier.weight(1f).padding(horizontal = 8.dp),
            colors = SliderDefaults.colors(
                thumbColor = oc.accent,
                activeTrackColor = oc.accent,
                inactiveTrackColor = oc.trackInactive
            )
        )
        Text(
            text = progressInfo.endLabel,
            color = oc.textSecondary,
            fontSize = 10.sp
        )
    }
}

/** 竖屏控制按钮行 */
@Composable
private fun PortraitControlButtons(
    paused: Boolean,
    muted: Boolean,
    volume: Int,
    showExitCatchup: Boolean,
    playbackMode: com.iptv.scanner.editor.pro.player.PlayMode,
    onPlayPause: () -> Unit,
    onStop: () -> Unit,
    onPrev: () -> Unit,
    onNext: () -> Unit,
    onMute: () -> Unit,
    onVolumeChange: (Float) -> Unit,
    onExitCatchup: () -> Unit
) {
    val oc = rememberPlayerOverlayColors()
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 12.dp, vertical = 4.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(4.dp)
    ) {
        IconButton(onClick = onPrev, modifier = Modifier.size(36.dp)) {
            Icon(Icons.Default.SkipPrevious, contentDescription = "上一频道", tint = oc.iconTint)
        }
        IconButton(onClick = onPlayPause, modifier = Modifier.size(40.dp)) {
            Icon(
                imageVector = if (paused) Icons.Default.PlayArrow else Icons.Default.Pause,
                contentDescription = if (paused) "播放" else "暂停",
                tint = oc.iconTint,
                modifier = Modifier.size(28.dp)
            )
        }
        IconButton(onClick = onStop, modifier = Modifier.size(36.dp)) {
            Icon(Icons.Default.Stop, contentDescription = "停止", tint = oc.iconTint)
        }
        IconButton(onClick = onNext, modifier = Modifier.size(36.dp)) {
            Icon(Icons.Default.SkipNext, contentDescription = "下一频道", tint = oc.iconTint)
        }
        Spacer(modifier = Modifier.width(8.dp))
        IconButton(onClick = onMute, modifier = Modifier.size(36.dp)) {
            Icon(
                imageVector = if (muted || volume == 0) Icons.Default.VolumeOff else Icons.Default.VolumeUp,
                contentDescription = "静音",
                tint = if (muted) oc.iconTintActive else oc.iconTint
            )
        }
        Slider(
            value = volume.toFloat(),
            onValueChange = onVolumeChange,
            valueRange = 0f..130f,
            modifier = Modifier.weight(1f).height(24.dp),
            colors = SliderDefaults.colors(
                thumbColor = oc.accent,
                activeTrackColor = oc.accent,
                inactiveTrackColor = oc.trackInactive
            )
        )
        Text(
            text = volume.toString(),
            color = oc.textSecondary,
            fontSize = 11.sp,
            modifier = Modifier.width(28.dp)
        )
        if (showExitCatchup) {
            Spacer(modifier = Modifier.width(4.dp))
            IconButton(onClick = onExitCatchup, modifier = Modifier.size(36.dp)) {
                Box(
                    modifier = Modifier
                        .size(28.dp)
                        .clip(RoundedCornerShape(4.dp))
                        .background(oc.iconTintActive),
                    contentAlignment = Alignment.Center
                ) {
                    Text(
                        text = if (playbackMode == com.iptv.scanner.editor.pro.player.PlayMode.TIMESHIFT) "时移" else "回看",
                        color = Color.White,
                        fontSize = 9.sp,
                        fontWeight = FontWeight.Bold
                    )
                }
            }
        }
    }
}

// -----------------------------------------------------------------
// OSD 浮层
// -----------------------------------------------------------------

@Composable
private fun OsdView(
    title: String,
    subtitle: String,
    extra: String
) {
    Surface(
        color = MaterialTheme.colorScheme.surface.copy(alpha = 0.9f),
        shape = RoundedCornerShape(8.dp),
        modifier = Modifier
            .statusBarsPadding()
            .padding(top = 48.dp)
            .padding(horizontal = 16.dp)
    ) {
        Column(
            modifier = Modifier
                .padding(horizontal = 16.dp, vertical = 10.dp)
        ) {
            Text(
                text = title,
                color = MaterialTheme.colorScheme.onSurface,
                fontSize = 14.sp,
                fontWeight = FontWeight.Medium
            )
            if (subtitle.isNotEmpty()) {
                Spacer(modifier = Modifier.height(2.dp))
                Text(
                    text = subtitle,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    fontSize = 12.sp
                )
            }
            if (extra.isNotEmpty()) {
                Spacer(modifier = Modifier.height(2.dp))
                Text(
                    text = extra,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    fontSize = 11.sp
                )
            }
        }
    }
}

// -----------------------------------------------------------------
// 提醒触发弹窗（节目即将开始时弹出）
// 与 PC 端 ui/dialogs/reminder_popup.py 对齐
// -----------------------------------------------------------------

/**
 * 提醒弹窗：节目即将开始时弹出，提供"切换频道"和"稍后"两个选项。
 *
 * - 全屏半透明遮罩
 * - 中央卡片显示节目信息
 * - "切换频道"：切到目标频道并关闭弹窗
 * - "稍后"：仅关闭弹窗
 */
@Composable
private fun ReminderPopup(
    reminder: ReminderItem,
    onAccept: () -> Unit,
    onDismiss: () -> Unit
) {
    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(Color(0xAA000000))
            .clickable(enabled = false) {},  // 阻断背景点击
        contentAlignment = Alignment.Center
    ) {
        Surface(
            color = MaterialTheme.colorScheme.surfaceVariant,
            shape = RoundedCornerShape(12.dp),
            modifier = Modifier.fillMaxWidth(0.85f)
        ) {
            Column(
                modifier = Modifier.padding(20.dp),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                // 顶部图标
                Icon(
                    Icons.Default.Notifications,
                    contentDescription = null,
                    tint = Color(0xFFFFC107),
                    modifier = Modifier
                        .width(48.dp)
                        .height(48.dp)
                )
                Spacer(modifier = Modifier.height(12.dp))

                // 标题
                Text(
                    text = "节目即将开始",
                    color = MaterialTheme.colorScheme.onSurface,
                    fontSize = 18.sp,
                    fontWeight = FontWeight.Medium
                )
                Spacer(modifier = Modifier.height(16.dp))

                // 节目信息卡片
                Surface(
                    color = MaterialTheme.colorScheme.surfaceVariant,
                    shape = RoundedCornerShape(8.dp),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Column(modifier = Modifier.padding(12.dp)) {
                        Text(
                            text = reminder.programTitle.ifBlank { "（未命名节目）" },
                            color = MaterialTheme.colorScheme.onSurface,
                            fontSize = 15.sp,
                            fontWeight = FontWeight.Medium,
                            maxLines = 2
                        )
                        if (reminder.channelName.isNotEmpty()) {
                            Spacer(modifier = Modifier.height(4.dp))
                            Text(
                                text = "频道: ${reminder.channelName}",
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                fontSize = 12.sp
                            )
                        }
                        if (reminder.startTs > 0) {
                            Spacer(modifier = Modifier.height(2.dp))
                            val timeStr = java.text.SimpleDateFormat(
                                "MM-dd HH:mm",
                                java.util.Locale.getDefault()
                            ).format(java.util.Date(reminder.startTs))
                            Text(
                                text = "开始: $timeStr",
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                fontSize = 12.sp
                            )
                        }
                    }
                }
                Spacer(modifier = Modifier.height(20.dp))

                // 按钮行
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(12.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    OutlinedButton(
                        onClick = onDismiss,
                        modifier = Modifier.weight(1f)
                    ) {
                        Text("稍后", color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    Button(
                        onClick = onAccept,
                        colors = ButtonDefaults.buttonColors(
                            containerColor = MaterialTheme.colorScheme.secondary
                        ),
                        modifier = Modifier.weight(1f)
                    ) {
                        Text("切换频道", color = MaterialTheme.colorScheme.onSecondary)
                    }
                }
            }
        }
    }
}

// -----------------------------------------------------------------
// 快捷工具栏 (QuickActionBar)
//
// 在视频控制层中提供常用功能的快捷入口，避免每次都要打开主菜单。
// 图标颜色随深色/浅色主题自适应。
// -----------------------------------------------------------------

/** QuickActionBar 朝向 */
enum class QuickActionBarOrientation { Portrait, Landscape }

/**
 * 快捷工具栏：截图 / 比例 / 锁定 / 画中画 / 音频可视化 / 歌词 / 主题切换
 *
 * - 深色主题：白色图标，激活态橙色
 * - 浅色主题：深色图标，激活态橙色
 * 所有颜色通过 [rememberPlayerOverlayColors] 自动适配。
 */
@Composable
private fun QuickActionBar(
    viewModel: AppViewModel,
    orientation: QuickActionBarOrientation
) {
    val oc = rememberPlayerOverlayColors()
    val controlsPinned by viewModel.controlsPinned.collectAsState()
    val themeMode by viewModel.themeMode.collectAsState()
    val audioVisualizerOpen by viewModel.audioVisualizerOpen.collectAsState()
    val lyricsOpen by viewModel.lyricsOpen.collectAsState()
    val aspectRatioIdx by viewModel.aspectRatioIdx.collectAsState()

    val aspectLabels = listOf("默认", "16:9", "4:3", "拉伸")

    Surface(
        color = Color.Transparent,
        modifier = Modifier.fillMaxWidth()
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = if (orientation == QuickActionBarOrientation.Landscape) 16.dp else 12.dp, vertical = 2.dp),
            horizontalArrangement = Arrangement.spacedBy(if (orientation == QuickActionBarOrientation.Landscape) 6.dp else 4.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            // 截图
            QuickActionItem(
                icon = Icons.Default.CropFree,
                label = "截图",
                tint = oc.iconTint,
                onClick = { viewModel.takeScreenshot("video") }
            )
            // 画面比例
            QuickActionItem(
                icon = Icons.Default.AspectRatio,
                label = aspectLabels.getOrElse(aspectRatioIdx) { "比例" },
                tint = if (aspectRatioIdx > 0) oc.accent else oc.iconTint,
                onClick = { viewModel.cycleAspectRatio() }
            )
            // 锁定控制层
            QuickActionItem(
                icon = if (controlsPinned) Icons.Default.Lock else Icons.Default.LockOpen,
                label = if (controlsPinned) "已锁" else "锁定",
                tint = if (controlsPinned) oc.accent else oc.iconTint,
                onClick = { viewModel.toggleControlsPinned() }
            )
            // 画中画
            QuickActionItem(
                icon = Icons.Default.PictureInPicture,
                label = "PiP",
                tint = oc.iconTint,
                onClick = { viewModel.enterPip() }
            )
            // 音频可视化
            QuickActionItem(
                icon = Icons.Default.MusicNote,
                label = "频谱",
                tint = if (audioVisualizerOpen) oc.accent else oc.iconTint,
                onClick = { viewModel.toggleAudioVisualizer() }
            )
            // 歌词
            QuickActionItem(
                icon = Icons.Default.MusicNote,
                label = "歌词",
                tint = if (lyricsOpen) oc.accent else oc.iconTint,
                onClick = { viewModel.toggleLyricsPanel() }
            )
            Spacer(modifier = Modifier.weight(1f))
            // 主题切换（深色↔浅色快速切换）
            QuickActionItem(
                icon = Icons.Default.Brightness4,
                label = when (themeMode) { "light" -> "浅色"; "system" -> "系统"; else -> "深色" },
                tint = oc.iconTint,
                onClick = {
                    val next = when (themeMode) {
                        "dark" -> "light"
                        "light" -> "system"
                        else -> "dark"
                    }
                    viewModel.setThemeMode(next)
                }
            )
        }
    }
}

/** QuickActionBar 单个快捷按钮 */
@Composable
private fun QuickActionItem(
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    label: String,
    tint: Color,
    onClick: () -> Unit
) {
    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        modifier = Modifier
            .clip(RoundedCornerShape(8.dp))
            .clickable(onClick = onClick)
            .padding(horizontal = 6.dp, vertical = 2.dp)
    ) {
        Icon(
            imageVector = icon,
            contentDescription = label,
            tint = tint,
            modifier = Modifier.size(20.dp)
        )
        Text(
            text = label,
            color = tint,
            fontSize = 9.sp,
            maxLines = 1
        )
    }
}

// ============================================================
// 竖屏新布局组件
// ============================================================

/**
 * 竖屏视频区域（固定 16:9，纯视频无覆盖层）
 */
@Composable
private fun PortraitVideoArea(
    primaryPlayer: @Composable () -> Unit,
    aspectRatio: Float,
    anyPanelOpen: Boolean,
    viewModel: AppViewModel
) {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .aspectRatio(16f / 9f)
            .background(Color.Black)
    ) {
        // 播放器（居中保持比例）
        Box(
            modifier = Modifier
                .align(Alignment.Center)
                .aspectRatio(aspectRatio)
        ) {
            primaryPlayer()
        }
    }
}

/**
 * 竖屏固定工具栏：上一频道/播放暂停/下一频道/静音/音量/截图/比例/画中画
 */
@Composable
private fun PortraitToolbar(viewModel: AppViewModel) {
    val mpv = viewModel.mpv
    val paused by mpv.paused.collectAsState()
    val muted by mpv.muted.collectAsState()
    val volume by mpv.volume.collectAsState()
    val showExitCatchup by viewModel.showExitCatchup.collectAsState()
    val playbackState by viewModel.playbackState.collectAsState()
    val aspectRatioIdx by viewModel.aspectRatioIdx.collectAsState()
    val oc = rememberPlayerOverlayColors()

    Surface(
        color = oc.infoBarBg,
        modifier = Modifier.fillMaxWidth()
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 8.dp, vertical = 2.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(2.dp)
        ) {
            // 上一频道
            IconButton(onClick = { viewModel.prevChannel() }, modifier = Modifier.size(34.dp)) {
                Icon(Icons.Default.SkipPrevious, contentDescription = "上一频道", tint = oc.iconTint, modifier = Modifier.size(22.dp))
            }
            // 播放/暂停
            IconButton(onClick = { mpv.togglePause() }, modifier = Modifier.size(38.dp)) {
                Icon(
                    imageVector = if (paused) Icons.Default.PlayArrow else Icons.Default.Pause,
                    contentDescription = if (paused) "播放" else "暂停",
                    tint = oc.iconTint,
                    modifier = Modifier.size(26.dp)
                )
            }
            // 下一频道
            IconButton(onClick = { viewModel.nextChannel() }, modifier = Modifier.size(34.dp)) {
                Icon(Icons.Default.SkipNext, contentDescription = "下一频道", tint = oc.iconTint, modifier = Modifier.size(22.dp))
            }
            // 静音
            IconButton(onClick = { mpv.toggleMute() }, modifier = Modifier.size(34.dp)) {
                Icon(
                    imageVector = if (muted || volume == 0) Icons.Default.VolumeOff else Icons.Default.VolumeUp,
                    contentDescription = "静音",
                    tint = if (muted) oc.iconTintActive else oc.iconTint,
                    modifier = Modifier.size(20.dp)
                )
            }
            // 音量滑块
            Slider(
                value = volume.toFloat(),
                onValueChange = { mpv.setVolume(it.toInt()) },
                valueRange = 0f..130f,
                modifier = Modifier.weight(1f).height(24.dp),
                colors = SliderDefaults.colors(
                    thumbColor = oc.accent,
                    activeTrackColor = oc.accent,
                    inactiveTrackColor = oc.trackInactive
                )
            )
            // 截图
            IconButton(onClick = { viewModel.takeScreenshot("video") }, modifier = Modifier.size(34.dp)) {
                Icon(Icons.Default.CropFree, contentDescription = "截图", tint = oc.iconTint, modifier = Modifier.size(20.dp))
            }
            // 画面比例
            IconButton(onClick = { viewModel.cycleAspectRatio() }, modifier = Modifier.size(34.dp)) {
                Icon(Icons.Default.AspectRatio, contentDescription = "画面比例", tint = if (aspectRatioIdx > 0) oc.accent else oc.iconTint, modifier = Modifier.size(20.dp))
            }
            // 画中画
            IconButton(onClick = { viewModel.enterPip() }, modifier = Modifier.size(34.dp)) {
                Icon(Icons.Default.PictureInPicture, contentDescription = "画中画", tint = oc.iconTint, modifier = Modifier.size(20.dp))
            }
            // 回看/时移退出
            if (showExitCatchup) {
                IconButton(onClick = { viewModel.exitCatchup() }, modifier = Modifier.size(34.dp)) {
                    Box(
                        modifier = Modifier
                            .size(26.dp)
                            .clip(RoundedCornerShape(4.dp))
                            .background(oc.iconTintActive),
                        contentAlignment = Alignment.Center
                    ) {
                        Text(
                            text = if (playbackState.mode == com.iptv.scanner.editor.pro.player.PlayMode.TIMESHIFT) "时移" else "回看",
                            color = Color.White,
                            fontSize = 9.sp,
                            fontWeight = FontWeight.Bold
                        )
                    }
                }
            }
        }
    }
}

// -----------------------------------------------------------------
// 竖屏首页（Home Screen）
// -----------------------------------------------------------------

/**
 * 竖屏首页：用户打开 App 首先看到的界面。
 *
 * 布局：
 * 1. 顶部 App 标题栏（logo + 菜单按钮）
 * 2. 快捷入口网格（频道列表 / 打开本地文件 / 打开播放列表 / 网络流 / 订阅源 / 扫描整理）
 * 3. 正在播放卡片（如果有视频在播放，显示迷你播放器条，点击返回播放器）
 * 4. 最近播放（水平滚动频道卡片）
 * 5. 收藏频道（水平滚动频道卡片）
 */
@Composable
private fun PortraitHomeScreen(
    viewModel: AppViewModel,
    playlistLauncher: androidx.activity.result.ActivityResultLauncher<Array<String>>,
    videoLauncher: androidx.activity.result.ActivityResultLauncher<Array<String>>
) {
    val oc = rememberPlayerOverlayColors()
    val channels by viewModel.channels.collectAsState()
    val history by viewModel.history.collectAsState()
    val favorites by viewModel.favorites.collectAsState()
    val currentChannel by viewModel.currentChannel.collectAsState()
    val displayInfo by viewModel.channelDisplayInfo.collectAsState()
    val fileLoaded by viewModel.mpv.fileLoaded.collectAsState()
    val paused by viewModel.mpv.paused.collectAsState()

    val recentChannels = remember(history, channels) {
        history.mapNotNull { idx -> channels.getOrNull(idx) }.take(20)
    }
    val favChannels = remember(favorites, channels) {
        favorites.mapNotNull { idx -> channels.getOrNull(idx) }.take(20)
    }

    // 通过 URL 查找频道索引（比 indexOf 更稳健，避免频道属性变更后匹配失败）
    fun findChannelIdx(channel: IptvChannel): Int = channels.indexOfFirst { it.url == channel.url }

    val bgColor = MaterialTheme.colorScheme.background

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(bgColor)
    ) {
        // 1. App 标题栏（无菜单按钮，功能入口在工具和设置页）
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .height(52.dp)
                .padding(horizontal = 16.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = "ISEP",
                style = MaterialTheme.typography.titleLarge,
                color = MaterialTheme.colorScheme.primary,
                fontWeight = FontWeight.Bold
            )
            Spacer(modifier = Modifier.weight(1f))
            Text(
                text = "IPTV Studio",
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }

        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            contentPadding = PaddingValues(bottom = 72.dp)
        ) {
            // 2. 快捷入口网格
            item {
                QuickActionGrid(
                    viewModel = viewModel,
                    playlistLauncher = playlistLauncher,
                    videoLauncher = videoLauncher
                )
            }

            // 3. 正在播放卡片
            if (fileLoaded && (currentChannel != null || displayInfo.name.isNotEmpty())) {
                item {
                    MiniPlayerCard(
                        viewModel = viewModel,
                        channelName = currentChannel?.name ?: displayInfo.name,
                        channelLogo = currentChannel?.logo ?: "",
                        groupName = currentChannel?.group ?: "",
                        isPaused = paused,
                        oc = oc,
                        onClick = { viewModel.showPlayerScreen() },
                        onPlayPause = { viewModel.mpv.togglePause() }
                    )
                }
            }

            // 4. 最近播放
            if (recentChannels.isNotEmpty()) {
                item {
                    HomeSectionHeader(title = "最近播放", oc = oc)
                }
                item {
                    LazyRow(
                        modifier = Modifier.fillMaxWidth(),
                        contentPadding = PaddingValues(horizontal = 12.dp),
                        horizontalArrangement = Arrangement.spacedBy(10.dp)
                    ) {
                        items(recentChannels) { channel ->
                            HomeChannelCard(
                                channel = channel,
                                oc = oc,
                                onClick = {
                                    val idx = findChannelIdx(channel)
                                    if (idx >= 0) viewModel.playChannel(idx)
                                }
                            )
                        }
                    }
                }
            }

            // 5. 收藏频道
            item {
                Spacer(modifier = Modifier.height(16.dp))
                HomeSectionHeader(title = "收藏频道", oc = oc)
            }
            if (favChannels.isNotEmpty()) {
                item {
                    LazyRow(
                        modifier = Modifier.fillMaxWidth(),
                        contentPadding = PaddingValues(horizontal = 12.dp),
                        horizontalArrangement = Arrangement.spacedBy(10.dp)
                    ) {
                        items(favChannels) { channel ->
                            HomeChannelCard(
                                channel = channel,
                                oc = oc,
                                onClick = {
                                    val idx = findChannelIdx(channel)
                                    if (idx >= 0) viewModel.playChannel(idx)
                                }
                            )
                        }
                    }
                }
            } else {
                // 无收藏时显示空状态提示
                item {
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(horizontal = 16.dp, vertical = 16.dp),
                        contentAlignment = Alignment.Center
                    ) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Icon(
                                Icons.Default.FavoriteBorder,
                                contentDescription = null,
                                tint = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.3f),
                                modifier = Modifier.size(32.dp)
                            )
                            Spacer(modifier = Modifier.height(6.dp))
                            Text(
                                text = "暂无收藏频道",
                                color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.5f),
                                fontSize = 12.sp
                            )
                            Spacer(modifier = Modifier.height(2.dp))
                            Text(
                                text = "在频道列表中长按频道可添加收藏",
                                color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.4f),
                                fontSize = 10.sp
                            )
                        }
                    }
                }
            }

            // 空状态提示
            if (recentChannels.isEmpty() && favChannels.isEmpty() && channels.isEmpty()) {
                item {
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(top = 48.dp),
                        contentAlignment = Alignment.Center
                    ) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Icon(
                                Icons.Default.VideoLibrary,
                                contentDescription = null,
                                tint = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.4f),
                                modifier = Modifier.size(48.dp)
                            )
                            Spacer(modifier = Modifier.height(12.dp))
                            Text(
                                text = "暂无频道",
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                fontSize = 14.sp
                            )
                            Spacer(modifier = Modifier.height(4.dp))
                            Text(
                                text = "点击「打开播放列表」或「订阅源管理」添加频道",
                                color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.6f),
                                fontSize = 12.sp
                            )
                        }
                    }
                }
            }
        }
    }
}

/** 快捷入口网格：3列2行 */
@Composable
private fun QuickActionGrid(
    viewModel: AppViewModel,
    playlistLauncher: androidx.activity.result.ActivityResultLauncher<Array<String>>,
    videoLauncher: androidx.activity.result.ActivityResultLauncher<Array<String>>
) {
    val oc = rememberPlayerOverlayColors()
    val actions = listOf(
        QuickAction(Icons.Default.VideoLibrary, "频道列表", "浏览所有频道") {
            viewModel.setPortraitTab(AppViewModel.PortraitTab.LIST)
        },
        QuickAction(Icons.Default.Movie, "本地文件", "播放视频/音频") {
            if (!viewModel.isSafAvailable()) {
                viewModel.showMediaFileBrowser()
            } else {
                videoLauncher.launch(arrayOf("video/*", "audio/*", "application/x-matroska", "application/octet-stream"))
            }
        },
        QuickAction(Icons.Default.FileOpen, "播放列表", "导入 M3U/M3U8") {
            if (!viewModel.isSafAvailable()) {
                viewModel.showFileBrowser()
            } else {
                playlistLauncher.launch(arrayOf(
                    "application/x-mpegurl", "application/vnd.apple.mpegurl",
                    "audio/x-mpegurl", "video/x-mpegurl",
                    "text/plain", "application/octet-stream"
                ))
            }
        },
        QuickAction(Icons.Default.Link, "网络流", "输入 URL 播放") {
            viewModel.toggleOpenUrlDialog()
        },
        QuickAction(Icons.Default.Web, "订阅源", "管理 M3U 订阅") {
            viewModel.setSourceTab(AppViewModel.SourceTab.PLAYLIST)
            viewModel.toggleSourceManager()
        },
        QuickAction(Icons.Default.Radar, "扫描整理", "URL 范围扫描") {
            viewModel.toggleScanPanel()
        }
    )

    Column(modifier = Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 8.dp)) {
        actions.chunked(3).forEach { rowActions ->
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                rowActions.forEach { action ->
                    QuickActionCard(action = action, oc = oc, modifier = Modifier.weight(1f))
                }
                repeat(3 - rowActions.size) {
                    Spacer(modifier = Modifier.weight(1f))
                }
            }
            Spacer(modifier = Modifier.height(10.dp))
        }
    }
}

private data class QuickAction(
    val icon: androidx.compose.ui.graphics.vector.ImageVector,
    val title: String,
    val subtitle: String,
    val onClick: () -> Unit
)

@Composable
private fun QuickActionCard(
    action: QuickAction,
    oc: PlayerOverlayColors,
    modifier: Modifier = Modifier
) {
    Surface(
        color = MaterialTheme.colorScheme.surfaceVariant,
        shape = RoundedCornerShape(14.dp),
        modifier = modifier
            .height(108.dp)
            .clip(RoundedCornerShape(14.dp))
            .clickable(onClick = action.onClick)
    ) {
        Column(
            modifier = Modifier.fillMaxSize().padding(8.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center
        ) {
            Box(
                modifier = Modifier
                    .size(36.dp)
                    .clip(CircleShape)
                    .background(MaterialTheme.colorScheme.primary.copy(alpha = 0.12f)),
                contentAlignment = Alignment.Center
            ) {
                Icon(
                    imageVector = action.icon,
                    contentDescription = action.title,
                    tint = MaterialTheme.colorScheme.primary,
                    modifier = Modifier.size(22.dp)
                )
            }
            Spacer(modifier = Modifier.height(6.dp))
            Text(
                text = action.title,
                color = MaterialTheme.colorScheme.onSurface,
                fontSize = 13.sp,
                fontWeight = FontWeight.Medium,
                maxLines = 1
            )
            Spacer(modifier = Modifier.height(2.dp))
            Text(
                text = action.subtitle,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                fontSize = 10.sp,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
                textAlign = androidx.compose.ui.text.style.TextAlign.Center
            )
        }
    }
}

/** 首页分组标题 */
@Composable
private fun HomeSectionHeader(title: String, oc: PlayerOverlayColors) {
    Text(
        text = title,
        color = MaterialTheme.colorScheme.onBackground,
        fontSize = 15.sp,
        fontWeight = FontWeight.SemiBold,
        modifier = Modifier.padding(horizontal = 16.dp, vertical = 6.dp)
    )
}

/** 正在播放迷你卡片（含节目名 + 媒体信息标识） */
@Composable
private fun MiniPlayerCard(
    viewModel: AppViewModel,
    channelName: String,
    channelLogo: String,
    groupName: String,
    isPaused: Boolean,
    oc: PlayerOverlayColors,
    onClick: () -> Unit,
    onPlayPause: () -> Unit
) {
    val currentIdx by viewModel.currentIdx.collectAsState()
    val epgCacheVersion by viewModel.epgCacheVersion.collectAsState()
    val player = viewModel.mpv
    val videoWidth by player.videoWidth.collectAsState()
    val videoHeight by player.videoHeight.collectAsState()

    // 获取当前节目
    val currentProgram = remember(currentIdx, epgCacheVersion) {
        if (currentIdx >= 0) viewModel.getCachedCurrentProgram(currentIdx) else null
    }

    // 获取媒体信息
    var mediaInfo by remember { mutableStateOf(emptyMap<String, String?>()) }
    LaunchedEffect(videoWidth, videoHeight) {
        if (videoWidth > 0) {
            mediaInfo = player.getMediaInfo()
        }
    }

    Surface(
        color = MaterialTheme.colorScheme.primary.copy(alpha = 0.08f),
        shape = RoundedCornerShape(12.dp),
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.primary.copy(alpha = 0.25f)),
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 12.dp, vertical = 4.dp)
            .clip(RoundedCornerShape(12.dp))
            .clickable(onClick = onClick)
    ) {
        Column(
            modifier = Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 8.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically
            ) {
                // 频道 logo（带自适应背景色）
                if (channelLogo.isNotEmpty()) {
                    Box(
                        modifier = Modifier
                            .size(32.dp)
                            .clip(RoundedCornerShape(4.dp))
                            .background(MaterialTheme.colorScheme.surfaceVariant),
                        contentAlignment = Alignment.Center
                    ) {
                        AsyncImage(
                            model = channelLogo,
                            contentDescription = null,
                            modifier = Modifier.fillMaxSize().padding(2.dp),
                            contentScale = ContentScale.Fit
                        )
                    }
                    Spacer(modifier = Modifier.width(10.dp))
                } else {
                    Icon(
                        Icons.Default.PlayArrow,
                        contentDescription = null,
                        tint = MaterialTheme.colorScheme.primary,
                        modifier = Modifier.size(24.dp)
                    )
                    Spacer(modifier = Modifier.width(10.dp))
                }
                // 频道名 + 分组 + 节目名
                Column(modifier = Modifier.weight(1f)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(
                            text = channelName,
                            color = MaterialTheme.colorScheme.onSurface,
                            fontSize = 14.sp,
                            fontWeight = FontWeight.Medium,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis
                        )
                        if (groupName.isNotEmpty()) {
                            Spacer(modifier = Modifier.width(6.dp))
                            Surface(
                                color = MaterialTheme.colorScheme.primary.copy(alpha = 0.12f),
                                shape = RoundedCornerShape(3.dp)
                            ) {
                                Text(
                                    text = groupName,
                                    color = MaterialTheme.colorScheme.primary,
                                    fontSize = 10.sp,
                                    modifier = Modifier.padding(horizontal = 4.dp, vertical = 1.dp),
                                    maxLines = 1
                                )
                            }
                        }
                    }
                    // 当前节目名（无 EPG 时显示「精彩节目」占位）
                    val progTitle = currentProgram?.title?.ifEmpty { null } ?: "精彩节目"
                    Text(
                        text = progTitle,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        fontSize = 11.sp,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                    // 媒体信息标识行
                    if (mediaInfo.isNotEmpty() || videoWidth > 0) {
                        Row(
                            modifier = Modifier.padding(top = 3.dp),
                            horizontalArrangement = Arrangement.spacedBy(4.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            // 视频编码
                            mediaInfo["videoCodec"]?.takeIf { it.isNotEmpty() && it != "null" }?.let { codec ->
                                val cleanCodec = codec.removePrefix("video/").removePrefix("audio/").uppercase()
                                MiniBadge(cleanCodec)
                            }
                            // 分辨率
                            if (videoWidth > 0 && videoHeight > 0) {
                                val resLabel = if (videoHeight >= 2160) "4K"
                                    else if (videoHeight >= 1080) "1080P"
                                    else if (videoHeight >= 720) "720P"
                                    else if (videoHeight >= 480) "480P"
                                    else "${videoHeight}P"
                                MiniBadge(resLabel)
                            }
                            // 音频编码
                            mediaInfo["audioCodec"]?.takeIf { it.isNotEmpty() && it != "null" }?.let { codec ->
                                val cleanCodec = codec.removePrefix("audio/").uppercase()
                                MiniBadge(cleanCodec)
                            }
                            // FPS
                            mediaInfo["fps"]?.takeIf { it.isNotEmpty() && it != "null" && it != "0" && it != "0.000" }?.let { fps ->
                                val fpsVal = fps.toFloatOrNull()
                                MiniBadge(if (fpsVal != null) "${fpsVal.toInt()}fps" else "${fps}fps")
                            }
                        }
                    }
                }
                // 播放/暂停按钮
                IconButton(onClick = onPlayPause, modifier = Modifier.size(36.dp)) {
                    Icon(
                        imageVector = if (isPaused) Icons.Default.PlayArrow else Icons.Default.Pause,
                        contentDescription = if (isPaused) "播放" else "暂停",
                        tint = MaterialTheme.colorScheme.primary,
                        modifier = Modifier.size(22.dp)
                    )
                }
            }
        }
    }
}

/**
 * 迷你播放器条：在所有 Tab 页面顶部显示的简洁播放器条。
 * 点击进入播放器模式，右侧有播放/暂停按钮。
 * 显示频道名 + 当前节目名（无 EPG 时显示「精彩节目」）。
 */
@Composable
private fun MiniPlayerBar(
    viewModel: AppViewModel,
    channelName: String,
    channelLogo: String,
    groupName: String,
    isPaused: Boolean,
    onClick: () -> Unit,
    onPlayPause: () -> Unit
) {
    val currentIdx by viewModel.currentIdx.collectAsState()
    val epgCacheVersion by viewModel.epgCacheVersion.collectAsState()

    // 获取当前节目
    val currentProgram = remember(currentIdx, epgCacheVersion) {
        if (currentIdx >= 0) viewModel.getCachedCurrentProgram(currentIdx) else null
    }
    val progTitle = currentProgram?.title?.ifEmpty { null } ?: "精彩节目"

    Surface(
        color = MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.5f),
        modifier = Modifier
            .fillMaxWidth()
            .height(48.dp)
            .clickable(onClick = onClick)
    ) {
        Row(
            modifier = Modifier
                .fillMaxSize()
                .padding(horizontal = 12.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            // 播放/暂停按钮
            IconButton(onClick = onPlayPause, modifier = Modifier.size(32.dp)) {
                Icon(
                    imageVector = if (isPaused) Icons.Default.PlayArrow else Icons.Default.Pause,
                    contentDescription = if (isPaused) "播放" else "暂停",
                    tint = MaterialTheme.colorScheme.primary,
                    modifier = Modifier.size(20.dp)
                )
            }
            Spacer(modifier = Modifier.width(8.dp))
            // 频道 logo（带自适应背景色，确保浅色台标在浅色模式下可见）
            if (channelLogo.isNotEmpty()) {
                Box(
                    modifier = Modifier
                        .size(28.dp)
                        .clip(RoundedCornerShape(4.dp))
                        .background(MaterialTheme.colorScheme.surfaceVariant),
                    contentAlignment = Alignment.Center
                ) {
                    AsyncImage(
                        model = channelLogo,
                        contentDescription = null,
                        modifier = Modifier.fillMaxSize().padding(2.dp),
                        contentScale = ContentScale.Fit
                    )
                }
                Spacer(modifier = Modifier.width(8.dp))
            }
            // 频道名 + 节目名
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = channelName,
                    color = MaterialTheme.colorScheme.onSurface,
                    fontSize = 13.sp,
                    fontWeight = FontWeight.Medium,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
                Text(
                    text = progTitle,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    fontSize = 10.sp,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
            }
            // 分组标签
            if (groupName.isNotEmpty()) {
                Surface(
                    color = MaterialTheme.colorScheme.primary.copy(alpha = 0.12f),
                    shape = RoundedCornerShape(3.dp)
                ) {
                    Text(
                        text = groupName,
                        color = MaterialTheme.colorScheme.primary,
                        fontSize = 9.sp,
                        modifier = Modifier.padding(horizontal = 4.dp, vertical = 1.dp),
                        maxLines = 1
                    )
                }
            }
            Spacer(modifier = Modifier.width(4.dp))
            Icon(
                imageVector = Icons.AutoMirrored.Filled.ArrowBack,
                contentDescription = "进入播放器",
                tint = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier
                    .size(18.dp)
                    .rotate(180f)  // 箭头朝右，表示"进入"
            )
        }
    }
}

/** 迷你信息标签 */
@Composable
private fun MiniBadge(label: String) {
    Surface(
        color = MaterialTheme.colorScheme.primary.copy(alpha = 0.15f),
        shape = RoundedCornerShape(3.dp)
    ) {
        Text(
            text = label,
            color = MaterialTheme.colorScheme.primary,
            fontSize = 9.sp,
            fontWeight = FontWeight.Medium,
            modifier = Modifier.padding(horizontal = 4.dp, vertical = 1.dp),
            maxLines = 1
        )
    }
}

/** 首页频道卡片（水平滚动列表中的单个卡片） */
@Composable
private fun HomeChannelCard(
    channel: IptvChannel,
    oc: PlayerOverlayColors,
    onClick: () -> Unit
) {
    Surface(
        color = MaterialTheme.colorScheme.surfaceVariant,
        shape = RoundedCornerShape(10.dp),
        modifier = Modifier
            .width(120.dp)
            .height(72.dp)
            .clip(RoundedCornerShape(10.dp))
            .clickable(onClick = onClick)
    ) {
        Row(
            modifier = Modifier.fillMaxSize().padding(8.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            if (channel.logo.isNotEmpty()) {
                Box(
                    modifier = Modifier
                        .size(40.dp)
                        .clip(RoundedCornerShape(4.dp))
                        .background(MaterialTheme.colorScheme.surfaceVariant),
                    contentAlignment = Alignment.Center
                ) {
                    AsyncImage(
                        model = channel.logo,
                        contentDescription = channel.name,
                        modifier = Modifier.fillMaxSize().padding(2.dp),
                        contentScale = ContentScale.Fit
                    )
                }
                Spacer(modifier = Modifier.width(8.dp))
            } else {
                Box(
                    modifier = Modifier
                        .size(40.dp)
                        .clip(CircleShape)
                        .background(MaterialTheme.colorScheme.primary.copy(alpha = 0.12f)),
                    contentAlignment = Alignment.Center
                ) {
                    Icon(
                        Icons.Default.PlayArrow,
                        contentDescription = null,
                        tint = MaterialTheme.colorScheme.primary,
                        modifier = Modifier.size(20.dp)
                    )
                }
                Spacer(modifier = Modifier.width(8.dp))
            }
            Text(
                text = channel.name,
                color = MaterialTheme.colorScheme.onSurface,
                fontSize = 12.sp,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
                modifier = Modifier.weight(1f)
            )
        }
    }
}

/**
 * 竖屏列表页：左右分栏布局（左=分组列表，右=频道列表），支持多订阅切换、回看标识、列表/缩略图模式
 */
@Composable
private fun PortraitListScreen(
    viewModel: AppViewModel,
    playlistLauncher: androidx.activity.result.ActivityResultLauncher<Array<String>>,
    videoLauncher: androidx.activity.result.ActivityResultLauncher<Array<String>>
) {
    val channels by viewModel.channels.collectAsState()
    val currentIdx by viewModel.currentIdx.collectAsState()
    val favorites by viewModel.favorites.collectAsState()
    val selectedGroup by viewModel.selectedGroup.collectAsState()
    val listSourceTab by viewModel.listSourceTab.collectAsState()
    val viewMode by viewModel.listViewMode.collectAsState()
    val epgCacheVersion by viewModel.epgCacheVersion.collectAsState()
    val history by viewModel.history.collectAsState()
    val sources by viewModel.sources.collectAsState()
    val selectedSource by viewModel.selectedSource.collectAsState()
    val thumbnailPaths by viewModel.thumbnailPaths.collectAsState()

    // 预加载 EPG 和缩略图
    LaunchedEffect(channels.size) {
        if (channels.isNotEmpty()) {
            viewModel.preloadEpgForAllChannels()
            viewModel.loadThumbnailPaths()
        }
    }

    // 根据数据源 + 订阅源过滤频道
    val filteredChannels = remember(channels, listSourceTab, selectedSource) {
        when (listSourceTab) {
            AppViewModel.ListSourceTab.SUBSCRIPTION -> {
                val sub = channels.filter { it.source.isNotEmpty() }
                if (selectedSource.isNotEmpty()) sub.filter { it.source == selectedSource } else sub
            }
            AppViewModel.ListSourceTab.LOCAL -> channels.filter { it.source.isEmpty() }
        }
    }

    // 分组（含频道数量，按 M3U 首次出现顺序排列）
    val groupList = remember(filteredChannels) {
        val groupOrder = filteredChannels.map { it.group.ifEmpty { "未分组" } }.distinct()
        val groupCounts = filteredChannels.groupingBy { it.group.ifEmpty { "未分组" } }.eachCount()
        groupOrder.map { it to (groupCounts[it] ?: 0) }
    }

    // 当前分组下的频道
    val displayChannels = remember(filteredChannels, selectedGroup) {
        if (selectedGroup.isEmpty()) filteredChannels
        else filteredChannels.filter { it.group == selectedGroup }
    }

    // 缩略图模式下自动生成缺失的缩略图
    LaunchedEffect(viewMode, displayChannels.size) {
        if (viewMode == AppViewModel.ListViewMode.THUMBNAIL && displayChannels.isNotEmpty()) {
            viewModel.generateMissingThumbnails(displayChannels)
        }
    }

    // 本地文件历史
    val localHistory = remember(history, channels) {
        history.mapNotNull { idx -> channels.getOrNull(idx) }
            .filter { it.source.isEmpty() }
            .take(20)
    }

    // 订阅源名称映射
    val sourceDisplayName = remember(sources, selectedSource) {
        if (selectedSource.isEmpty()) "全部订阅"
        else sources.find { it.url == selectedSource }?.name?.ifEmpty { selectedSource.substringAfterLast("/").take(20) }
            ?: selectedSource.substringAfterLast("/").take(20)
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
    ) {
        // 顶部标题栏：标题 + 视图切换
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .height(44.dp)
                .padding(horizontal = 12.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = "频道列表",
                style = MaterialTheme.typography.titleMedium,
                color = MaterialTheme.colorScheme.onBackground,
                fontWeight = FontWeight.Bold
            )

            Spacer(modifier = Modifier.weight(1f))

            // 数据源切换
            Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                listOf(
                    AppViewModel.ListSourceTab.SUBSCRIPTION to "订阅",
                    AppViewModel.ListSourceTab.LOCAL to "本地"
                ).forEach { (tab, label) ->
                    FilterChip(
                        selected = listSourceTab == tab,
                        onClick = { viewModel.setListSourceTab(tab) },
                        label = { Text(label, fontSize = 11.sp) },
                        colors = FilterChipDefaults.filterChipColors(
                            selectedContainerColor = MaterialTheme.colorScheme.primary,
                            selectedLabelColor = MaterialTheme.colorScheme.onPrimary,
                            containerColor = MaterialTheme.colorScheme.surfaceVariant,
                            labelColor = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    )
                }
            }

            Spacer(modifier = Modifier.width(4.dp))

            // 视图模式切换按钮
            IconButton(onClick = {
                viewModel.setListViewMode(
                    if (viewMode == AppViewModel.ListViewMode.LIST) AppViewModel.ListViewMode.THUMBNAIL
                    else AppViewModel.ListViewMode.LIST
                )
            }) {
                Icon(
                    imageVector = if (viewMode == AppViewModel.ListViewMode.LIST) Icons.Default.GridView else Icons.Default.ViewList,
                    contentDescription = "切换视图",
                    tint = MaterialTheme.colorScheme.onBackground
                )
            }

            // 本地模式：清空按钮
            if (listSourceTab == AppViewModel.ListSourceTab.LOCAL && filteredChannels.isNotEmpty()) {
                var showClearDialog by remember { mutableStateOf(false) }
                IconButton(onClick = { showClearDialog = true }) {
                    Icon(
                        imageVector = Icons.Default.DeleteSweep,
                        contentDescription = "清空本地列表",
                        tint = MaterialTheme.colorScheme.error
                    )
                }
                if (showClearDialog) {
                    AlertDialog(
                        onDismissRequest = { showClearDialog = false },
                        title = { Text("清空本地列表") },
                        text = { Text("确定要清空所有本地频道吗？此操作不可撤销。") },
                        confirmButton = {
                            TextButton(onClick = {
                                viewModel.clearLocalChannels()
                                showClearDialog = false
                            }) { Text("清空", color = MaterialTheme.colorScheme.error) }
                        },
                        dismissButton = {
                            TextButton(onClick = { showClearDialog = false }) { Text("取消") }
                        }
                    )
                }
            }
        }

        // 订阅源横向滚动标签（仅订阅模式且多订阅源时显示）
        if (listSourceTab == AppViewModel.ListSourceTab.SUBSCRIPTION && sources.size > 1) {
            LazyRow(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 8.dp, vertical = 2.dp),
                horizontalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                // 「全部」标签
                item {
                    FilterChip(
                        selected = selectedSource.isEmpty(),
                        onClick = { viewModel.setSelectedSource("") },
                        label = { Text("全部", fontSize = 11.sp) },
                        colors = FilterChipDefaults.filterChipColors(
                            selectedContainerColor = MaterialTheme.colorScheme.primary,
                            selectedLabelColor = MaterialTheme.colorScheme.onPrimary,
                            containerColor = MaterialTheme.colorScheme.surfaceVariant,
                            labelColor = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    )
                }
                items(sources) { src ->
                    val name = src.name.ifEmpty { src.url.substringAfterLast("/").take(15) }
                    FilterChip(
                        selected = selectedSource == src.url,
                        onClick = { viewModel.setSelectedSource(src.url) },
                        label = { Text(name, fontSize = 11.sp, maxLines = 1, overflow = TextOverflow.Ellipsis) },
                        colors = FilterChipDefaults.filterChipColors(
                            selectedContainerColor = MaterialTheme.colorScheme.primary,
                            selectedLabelColor = MaterialTheme.colorScheme.onPrimary,
                            containerColor = MaterialTheme.colorScheme.surfaceVariant,
                            labelColor = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    )
                }
            }
        }

        // 本地列表为空时显示快捷入口
        if (listSourceTab == AppViewModel.ListSourceTab.LOCAL && filteredChannels.isEmpty()) {
            Column(
                modifier = Modifier.fillMaxSize().padding(16.dp),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                Spacer(modifier = Modifier.height(32.dp))
                if (localHistory.isNotEmpty()) {
                    Text(
                        text = "最近播放",
                        color = MaterialTheme.colorScheme.onBackground,
                        fontSize = 15.sp,
                        fontWeight = FontWeight.SemiBold,
                        modifier = Modifier.fillMaxWidth()
                    )
                    Spacer(modifier = Modifier.height(8.dp))
                    localHistory.forEach { channel ->
                        val idx = channels.indexOfFirst { it.url == channel.url }
                        Surface(
                            color = MaterialTheme.colorScheme.surfaceVariant,
                            shape = RoundedCornerShape(8.dp),
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(vertical = 3.dp)
                                .clickable { if (idx >= 0) viewModel.playChannel(idx) }
                        ) {
                            Row(
                                modifier = Modifier.padding(12.dp),
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Icon(Icons.Default.PlayArrow, contentDescription = null, tint = MaterialTheme.colorScheme.primary, modifier = Modifier.size(24.dp))
                                Spacer(modifier = Modifier.width(10.dp))
                                Text(
                                    text = channel.name,
                                    color = MaterialTheme.colorScheme.onSurface,
                                    fontSize = 14.sp,
                                    maxLines = 1,
                                    overflow = TextOverflow.Ellipsis,
                                    modifier = Modifier.weight(1f)
                                )
                            }
                        }
                    }
                }
                Spacer(modifier = Modifier.height(24.dp))
                Text("暂无本地文件\n点击下方按钮打开本地视频/音乐", color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 14.sp, textAlign = androidx.compose.ui.text.style.TextAlign.Center)
                Spacer(modifier = Modifier.height(8.dp))
                TextButton(onClick = {
                    if (!viewModel.isSafAvailable()) viewModel.showMediaFileBrowser()
                    else videoLauncher.launch(arrayOf("video/*", "audio/*", "application/x-matroska", "application/octet-stream"))
                }) { Text("打开本地文件") }
                Spacer(modifier = Modifier.height(4.dp))
                TextButton(onClick = {
                    if (!viewModel.isSafAvailable()) viewModel.showFileBrowser()
                    else playlistLauncher.launch(arrayOf(
                        "application/x-mpegurl", "application/vnd.apple.mpegurl",
                        "audio/x-mpegurl", "video/x-mpegurl",
                        "text/plain", "application/octet-stream"
                    ))
                }) { Text("导入播放列表") }
            }
            return
        }

        if (displayChannels.isEmpty()) {
            Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Text("暂无频道", color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 14.sp)
            }
            return
        }

        // ---- 左右分栏布局 ----
        Row(modifier = Modifier.fillMaxSize()) {
            // 左侧：分组列表（固定宽度，可滚动）
            GroupSidebar(
                groupList = groupList,
                selectedGroup = selectedGroup,
                onSelect = { viewModel.setSelectedGroup(it) },
                modifier = Modifier.width(100.dp)
            )
            // 分隔线
            Box(modifier = Modifier.width(1.dp).fillMaxHeight().background(MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.5f)))
            // 右侧：频道列表
            Box(modifier = Modifier.weight(1f)) {
                if (viewMode == AppViewModel.ListViewMode.LIST) {
                    ChannelListPanel(
                        displayChannels = displayChannels,
                        channels = channels,
                        currentIdx = currentIdx,
                        favorites = favorites,
                        epgCacheVersion = epgCacheVersion,
                        thumbnailPaths = thumbnailPaths,
                        viewModel = viewModel,
                        showDelete = listSourceTab == AppViewModel.ListSourceTab.LOCAL,
                        onDelete = { idx -> viewModel.deleteChannel(idx) }
                    )
                } else {
                    ChannelThumbnailPanel(
                        displayChannels = displayChannels,
                        channels = channels,
                        currentIdx = currentIdx,
                        favorites = favorites,
                        thumbnailPaths = thumbnailPaths,
                        viewModel = viewModel,
                        showDelete = listSourceTab == AppViewModel.ListSourceTab.LOCAL,
                        onDelete = { idx -> viewModel.deleteChannel(idx) }
                    )
                }
            }
        }
    }
}

/** 订阅源选择器（下拉菜单） */
@Composable
private fun SourceSelectorBox(
    label: String,
    sources: List<com.iptv.scanner.editor.pro.data.IptvSource>,
    selectedSource: String,
    onSelect: (String) -> Unit
) {
    var expanded by remember { mutableStateOf(false) }
    Box {
        Surface(
            color = MaterialTheme.colorScheme.surfaceVariant,
            shape = RoundedCornerShape(8.dp),
            modifier = Modifier.clickable { expanded = true }
        ) {
            Row(
                modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Icon(
                    Icons.Default.Web,
                    contentDescription = null,
                    tint = MaterialTheme.colorScheme.primary,
                    modifier = Modifier.size(14.dp)
                )
                Spacer(modifier = Modifier.width(4.dp))
                Text(
                    text = label,
                    color = MaterialTheme.colorScheme.onSurface,
                    fontSize = 11.sp,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.widthIn(max = 80.dp)
                )
                Icon(
                    Icons.Default.KeyboardArrowDown,
                    contentDescription = null,
                    tint = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.size(14.dp)
                )
            }
        }
        DropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            DropdownMenuItem(
                text = { Text("全部订阅", fontSize = 13.sp) },
                onClick = { onSelect(""); expanded = false }
            )
            sources.forEach { src ->
                DropdownMenuItem(
                    text = { Text(src.name.ifEmpty { src.url.substringAfterLast("/").take(30) }, fontSize = 13.sp, maxLines = 1, overflow = TextOverflow.Ellipsis) },
                    onClick = { onSelect(src.url); expanded = false }
                )
            }
        }
    }
}

/** 左侧分组侧栏 */
@Composable
private fun GroupSidebar(
    groupList: List<Pair<String, Int>>,
    selectedGroup: String,
    onSelect: (String) -> Unit,
    modifier: Modifier = Modifier
) {
    LazyColumn(
        modifier = modifier
            .fillMaxHeight()
            .background(MaterialTheme.colorScheme.surface),
        contentPadding = PaddingValues(vertical = 4.dp)
    ) {
        item {
            val isSelected = selectedGroup.isEmpty()
            Surface(
                color = if (isSelected) MaterialTheme.colorScheme.primaryContainer else Color.Transparent,
                shape = RoundedCornerShape(0.dp),
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable { onSelect("") }
            ) {
                Row(
                    modifier = Modifier.padding(horizontal = 10.dp, vertical = 10.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        text = "全部",
                        color = if (isSelected) MaterialTheme.colorScheme.onPrimaryContainer
                            else MaterialTheme.colorScheme.onSurface,
                        fontSize = 13.sp,
                        fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Normal,
                        maxLines = 1
                    )
                    Spacer(modifier = Modifier.weight(1f))
                    Text(
                        text = "${groupList.sumOf { it.second }}",
                        color = if (isSelected) MaterialTheme.colorScheme.onPrimaryContainer.copy(alpha = 0.7f)
                            else MaterialTheme.colorScheme.onSurfaceVariant,
                        fontSize = 10.sp
                    )
                }
            }
        }
        items(groupList) { (group, count) ->
            val isSelected = selectedGroup == group
            Surface(
                color = if (isSelected) MaterialTheme.colorScheme.primaryContainer else Color.Transparent,
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable { onSelect(if (group == "未分组") "" else group) }
            ) {
                Row(
                    modifier = Modifier.padding(horizontal = 10.dp, vertical = 8.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        text = group,
                        color = if (isSelected) MaterialTheme.colorScheme.onPrimaryContainer
                            else MaterialTheme.colorScheme.onSurface,
                        fontSize = 12.sp,
                        fontWeight = if (isSelected) FontWeight.Medium else FontWeight.Normal,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                        modifier = Modifier.weight(1f)
                    )
                    Text(
                        text = "$count",
                        color = if (isSelected) MaterialTheme.colorScheme.onPrimaryContainer.copy(alpha = 0.7f)
                            else MaterialTheme.colorScheme.onSurfaceVariant,
                        fontSize = 10.sp
                    )
                }
            }
        }
    }
}

/** 右侧频道列表（列表模式） */
@OptIn(ExperimentalFoundationApi::class)
@Composable
private fun ChannelListPanel(
    displayChannels: List<IptvChannel>,
    channels: List<IptvChannel>,
    currentIdx: Int,
    favorites: Set<Int>,
    epgCacheVersion: Int,
    thumbnailPaths: Map<String, String>,
    viewModel: AppViewModel,
    showDelete: Boolean = false,
    onDelete: (Int) -> Unit = {}
) {
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(bottom = 72.dp, top = 4.dp)
    ) {
        items(displayChannels) { channel ->
            val idx = channels.indexOf(channel)
            val isCurrent = idx == currentIdx
            val isFav = favorites.contains(idx)
            val canCatchup = CatchupHelper.isCatchupEnabled(channel)
            val currentProgram = if (idx >= 0) {
                remember(epgCacheVersion, idx) { viewModel.getCachedCurrentProgram(idx) }
            } else null

            Surface(
                color = if (isCurrent) MaterialTheme.colorScheme.primaryContainer
                    else MaterialTheme.colorScheme.surfaceVariant,
                shape = RoundedCornerShape(8.dp),
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 6.dp, vertical = 2.dp)
                    .combinedClickable(
                        onClick = { if (idx >= 0) viewModel.playChannel(idx) },
                        onLongClick = {
                            if (idx >= 0) {
                                viewModel.toggleFavoriteByIndex(idx)
                            }
                        }
                    )
            ) {
                Row(
                    modifier = Modifier.padding(horizontal = 8.dp, vertical = 8.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    // 台标（带自适应背景色，确保浅色台标在浅色模式下可见）
                    if (channel.logo.isNotEmpty()) {
                        Box(
                            modifier = Modifier
                                .size(36.dp)
                                .clip(RoundedCornerShape(4.dp))
                                .background(MaterialTheme.colorScheme.surfaceVariant),
                            contentAlignment = Alignment.Center
                        ) {
                            AsyncImage(
                                model = channel.logo,
                                contentDescription = channel.name,
                                modifier = Modifier.fillMaxSize().padding(2.dp),
                                contentScale = ContentScale.Fit
                            )
                        }
                        Spacer(modifier = Modifier.width(8.dp))
                    } else {
                        Box(
                            modifier = Modifier
                                .size(36.dp)
                                .clip(CircleShape)
                                .background(MaterialTheme.colorScheme.primary.copy(alpha = 0.12f)),
                            contentAlignment = Alignment.Center
                        ) {
                            Icon(Icons.Default.PlayArrow, contentDescription = null, tint = MaterialTheme.colorScheme.primary, modifier = Modifier.size(18.dp))
                        }
                        Spacer(modifier = Modifier.width(8.dp))
                    }
                    // 频道名 + 节目
                    Column(modifier = Modifier.weight(1f)) {
                        Text(
                            text = channel.name,
                            color = if (isCurrent) MaterialTheme.colorScheme.onPrimaryContainer
                                else MaterialTheme.colorScheme.onSurface,
                            fontSize = 13.sp,
                            fontWeight = if (isCurrent) FontWeight.Medium else FontWeight.Normal,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis
                        )
                        currentProgram?.let { prog ->
                            if (prog.title.isNotEmpty()) {
                                Text(
                                    text = prog.title,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                    fontSize = 10.sp,
                                    maxLines = 1,
                                    overflow = TextOverflow.Ellipsis
                                )
                            } else {
                                Text(
                                    text = "精彩节目",
                                    color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.6f),
                                    fontSize = 10.sp,
                                    maxLines = 1
                                )
                            }
                        } ?: run {
                            // 无 EPG 数据时显示「精彩节目」占位
                            Text(
                                text = "精彩节目",
                                color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.6f),
                                fontSize = 10.sp,
                                maxLines = 1
                            )
                        }
                    }
                    // 回看标识
                    if (canCatchup) {
                        Icon(
                            Icons.Default.History,
                            contentDescription = "可回看",
                            tint = MaterialTheme.colorScheme.tertiary,
                            modifier = Modifier.size(14.dp)
                        )
                        Spacer(modifier = Modifier.width(4.dp))
                    }
                    // 收藏标识
                    if (isFav) {
                        Icon(
                            Icons.Default.Favorite,
                            contentDescription = "已收藏",
                            tint = Color(0xFFFFC107),
                            modifier = Modifier.size(14.dp)
                        )
                    }
                    // 删除按钮（仅本地模式）
                    if (showDelete && idx >= 0) {
                        Spacer(modifier = Modifier.width(4.dp))
                        Icon(
                            Icons.Default.Close,
                            contentDescription = "删除",
                            tint = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier
                                .size(18.dp)
                                .clickable { onDelete(idx) }
                        )
                    }
                }
            }
        }
    }
}

/** 右侧频道列表（缩略图模式） */
@OptIn(ExperimentalFoundationApi::class)
@Composable
private fun ChannelThumbnailPanel(
    displayChannels: List<IptvChannel>,
    channels: List<IptvChannel>,
    currentIdx: Int,
    favorites: Set<Int>,
    thumbnailPaths: Map<String, String>,
    viewModel: AppViewModel,
    showDelete: Boolean = false,
    onDelete: (Int) -> Unit = {}
) {
    val thumbnailGenProgress by viewModel.thumbnailGenProgress.collectAsState()

    LazyVerticalGrid(
        columns = GridCells.Fixed(2),
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(start = 8.dp, top = 4.dp, end = 8.dp, bottom = 80.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        // 缩略图生成进度提示
        if (thumbnailGenProgress != null) {
            item(span = { GridItemSpan(2) }) {
                Surface(
                    color = MaterialTheme.colorScheme.primary.copy(alpha = 0.12f),
                    shape = RoundedCornerShape(8.dp),
                    modifier = Modifier.fillMaxWidth().padding(vertical = 2.dp)
                ) {
                    Row(
                        modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(16.dp),
                            strokeWidth = 2.dp,
                            color = MaterialTheme.colorScheme.primary
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(
                            text = "正在生成缩略图 ${thumbnailGenProgress!!.first}/${thumbnailGenProgress!!.second}",
                            color = MaterialTheme.colorScheme.primary,
                            fontSize = 12.sp
                        )
                    }
                }
            }
        }
        gridItems(displayChannels) { channel ->
            val idx = channels.indexOf(channel)
            val isCurrent = idx == currentIdx
            val isFav = favorites.contains(idx)
            val canCatchup = CatchupHelper.isCatchupEnabled(channel)
            // 只使用频道画面截图，不回退到台标
            val thumbPath = thumbnailPaths[channel.url]
            val hasThumb = thumbPath != null && File(thumbPath).exists()

            Surface(
                color = if (isCurrent) MaterialTheme.colorScheme.primaryContainer
                    else MaterialTheme.colorScheme.surfaceVariant,
                shape = RoundedCornerShape(10.dp),
                modifier = Modifier
                    .aspectRatio(16f / 9f)
                    .combinedClickable(
                        onClick = { if (idx >= 0) viewModel.playChannel(idx) },
                        onLongClick = {
                            if (idx >= 0) {
                                viewModel.toggleFavoriteByIndex(idx)
                            }
                        }
                    )
            ) {
                Box(modifier = Modifier.fillMaxSize()) {
                    // 频道画面截图
                    if (hasThumb) {
                        AsyncImage(
                            model = thumbPath,
                            contentDescription = channel.name,
                            modifier = Modifier.fillMaxSize(),
                            contentScale = ContentScale.Crop
                        )
                    } else {
                        // 无截图时显示占位符（等待缩略图生成）
                        Box(
                            modifier = Modifier
                                .fillMaxSize()
                                .background(MaterialTheme.colorScheme.surfaceVariant),
                            contentAlignment = Alignment.Center
                        ) {
                            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                Icon(
                                    Icons.Default.PlayArrow,
                                    contentDescription = null,
                                    tint = MaterialTheme.colorScheme.primary.copy(alpha = 0.3f),
                                    modifier = Modifier.size(28.dp)
                                )
                            }
                        }
                    }
                    // 底部渐变遮罩 + 频道名
                    Box(
                        modifier = Modifier
                            .align(Alignment.BottomCenter)
                            .fillMaxWidth()
                            .background(
                                Color.Black.copy(alpha = 0.55f)
                            )
                            .padding(horizontal = 6.dp, vertical = 4.dp)
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            if (canCatchup) {
                                Icon(
                                    Icons.Default.History,
                                    contentDescription = "可回看",
                                    tint = Color.White,
                                    modifier = Modifier.size(12.dp)
                                )
                                Spacer(modifier = Modifier.width(3.dp))
                            }
                            Text(
                                text = channel.name,
                                color = Color.White,
                                fontSize = 11.sp,
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis,
                                modifier = Modifier.weight(1f)
                            )
                            if (isFav) {
                                Icon(
                                    Icons.Default.Favorite,
                                    contentDescription = "已收藏",
                                    tint = Color(0xFFFFC107),
                                    modifier = Modifier.size(12.dp)
                                )
                            }
                        }
                    }
                    // 当前播放标识
                    if (isCurrent) {
                        Box(
                            modifier = Modifier
                                .align(Alignment.TopEnd)
                                .padding(4.dp)
                                .clip(CircleShape)
                                .background(MaterialTheme.colorScheme.primary)
                                .padding(horizontal = 6.dp, vertical = 2.dp)
                        ) {
                            Text("播放中", color = MaterialTheme.colorScheme.onPrimary, fontSize = 8.sp, fontWeight = FontWeight.Bold)
                        }
                    }
                    // 删除按钮（仅本地模式）
                    if (showDelete && idx >= 0) {
                        Box(
                            modifier = Modifier
                                .align(Alignment.TopStart)
                                .padding(4.dp)
                                .clip(CircleShape)
                                .background(Color.Black.copy(alpha = 0.6f))
                                .clickable { onDelete(idx) }
                                .padding(4.dp)
                        ) {
                            Icon(
                                Icons.Default.Close,
                                contentDescription = "删除",
                                tint = Color.White,
                                modifier = Modifier.size(14.dp)
                            )
                        }
                    }
                }
            }
        }
    }
}

/**
 * 播放器模式动态内容：订阅频道显示节目单，本地文件显示文件信息
 */
@Composable
private fun PortraitPlayerDynamicContent(viewModel: AppViewModel) {
    val currentIdx by viewModel.currentIdx.collectAsState()
    val currentChannel by viewModel.currentChannel.collectAsState()
    val player = viewModel.mpv
    val fileLoaded by player.fileLoaded.collectAsState()
    val videoWidth by player.videoWidth.collectAsState()
    val videoHeight by player.videoHeight.collectAsState()
    val duration by player.duration.collectAsState()
    val timePos by player.timePos.collectAsState()

    // 判断是订阅频道还是本地文件
    val isLocalFile = currentChannel == null || currentIdx < 0

    if (!fileLoaded) {
        Box(
            modifier = Modifier.fillMaxSize(),
            contentAlignment = Alignment.Center
        ) {
            Text(
                text = "未播放",
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                fontSize = 14.sp
            )
        }
        return
    }

    if (isLocalFile) {
        // 本地文件：显示文件信息 + 播放进度 + 最近文件
        PortraitLocalFileInfo(
            viewModel = viewModel,
            duration = duration,
            timePos = timePos,
            videoWidth = videoWidth,
            videoHeight = videoHeight
        )
    } else {
        // 订阅频道：显示节目单（EPG）
        PortraitEpgContent(viewModel = viewModel)
    }
}

/** 本地文件信息面板 */
@Composable
private fun PortraitLocalFileInfo(
    viewModel: AppViewModel,
    duration: Double,
    timePos: Double,
    videoWidth: Int,
    videoHeight: Int
) {
    val player = viewModel.mpv
    val channels by viewModel.channels.collectAsState()
    val history by viewModel.history.collectAsState()

    // 获取媒体信息
    var tick by remember { mutableStateOf(0L) }
    LaunchedEffect(Unit) {
        while (true) {
            tick = System.currentTimeMillis()
            delay(2000L)
        }
    }
    val mediaInfo = remember(tick) { player.getMediaInfo() }

    // 最近播放的本地文件
    val recentLocal = remember(history, channels) {
        history.mapNotNull { idx -> channels.getOrNull(idx) }
            .filter { it.source.isEmpty() }
            .take(10)
    }

    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(16.dp)
    ) {
        // 文件信息卡片
        item {
            Surface(
                color = MaterialTheme.colorScheme.surfaceVariant,
                shape = RoundedCornerShape(12.dp),
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text(
                        text = "文件信息",
                        style = MaterialTheme.typography.titleSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        fontWeight = FontWeight.Bold
                    )
                    Spacer(modifier = Modifier.height(8.dp))

                    // 媒体信息标识行
                    Row(
                        horizontalArrangement = Arrangement.spacedBy(4.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        mediaInfo["videoCodec"]?.takeIf { it.isNotEmpty() && it != "null" }?.let { codec ->
                            val cleanCodec = codec.removePrefix("video/").removePrefix("audio/").uppercase()
                            MiniBadge(cleanCodec)
                        }
                        if (videoWidth > 0 && videoHeight > 0) {
                            val resLabel = if (videoHeight >= 2160) "4K"
                                else if (videoHeight >= 1080) "1080P"
                                else if (videoHeight >= 720) "720P"
                                else if (videoHeight >= 480) "480P"
                                else "${videoHeight}P"
                            MiniBadge(resLabel)
                            MiniBadge("${videoWidth}×${videoHeight}")
                        }
                        mediaInfo["audioCodec"]?.takeIf { it.isNotEmpty() && it != "null" }?.let { codec ->
                            MiniBadge(codec.removePrefix("audio/").uppercase())
                        }
                        mediaInfo["fps"]?.takeIf { it.isNotEmpty() && it != "null" && it != "0" && it != "0.000" }?.let { fps ->
                            val fpsVal = fps.toFloatOrNull()
                            MiniBadge(if (fpsVal != null) "${fpsVal.toInt()}fps" else "${fps}fps")
                        }
                    }

                    Spacer(modifier = Modifier.height(12.dp))

                    // 播放进度
                    if (duration > 0) {
                        val progress = (timePos / duration * 100).coerceIn(0.0, 100.0)
                        Text(
                            text = "播放进度",
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            fontSize = 12.sp
                        )
                        Spacer(modifier = Modifier.height(4.dp))
                        LinearProgressIndicator(
                            progress = { (progress / 100).toFloat() },
                            modifier = Modifier.fillMaxWidth(),
                            color = MaterialTheme.colorScheme.primary,
                            trackColor = MaterialTheme.colorScheme.surfaceVariant
                        )
                        Spacer(modifier = Modifier.height(4.dp))
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            Text(
                                text = formatTime(timePos),
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                fontSize = 11.sp
                            )
                            Text(
                                text = formatTime(duration),
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                fontSize = 11.sp
                            )
                        }
                    }

                    Spacer(modifier = Modifier.height(12.dp))

                    // 文件路径
                    mediaInfo["fileFormat"]?.takeIf { it.isNotEmpty() && it != "null" }?.let { fmt ->
                        InfoRow("容器格式", fmt.uppercase())
                    }
                    mediaInfo["bitrate"]?.takeIf { it.isNotEmpty() && it != "null" && it != "0" }?.let { br ->
                        val brVal = br.toLongOrNull() ?: 0L
                        InfoRow("比特率", if (brVal > 1000000) "${brVal / 1000000} Mbps" else "${brVal / 1000} kbps")
                    }
                }
            }
        }

        // 音轨/字幕快速切换
        item {
            Spacer(modifier = Modifier.height(12.dp))
            Surface(
                color = MaterialTheme.colorScheme.surfaceVariant,
                shape = RoundedCornerShape(12.dp),
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text(
                        text = "音轨与字幕",
                        style = MaterialTheme.typography.titleSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        fontWeight = FontWeight.Bold
                    )
                    Spacer(modifier = Modifier.height(8.dp))
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        TextButton(
                            onClick = { viewModel.toggleAudioSettings() },
                            modifier = Modifier.weight(1f)
                        ) { Text("音轨设置") }
                        TextButton(
                            onClick = { viewModel.toggleSubtitleSettings() },
                            modifier = Modifier.weight(1f)
                        ) { Text("字幕设置") }
                    }
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        TextButton(
                            onClick = { viewModel.togglePlaybackPanel() },
                            modifier = Modifier.weight(1f)
                        ) { Text("播放速度") }
                        TextButton(
                            onClick = { viewModel.toggleBookmarkPanel() },
                            modifier = Modifier.weight(1f)
                        ) { Text("书签管理") }
                    }
                }
            }
        }

        // 最近播放的本地文件
        if (recentLocal.isNotEmpty()) {
            item {
                Spacer(modifier = Modifier.height(12.dp))
                Text(
                    text = "最近播放",
                    style = MaterialTheme.typography.titleSmall,
                    color = MaterialTheme.colorScheme.onBackground,
                    fontWeight = FontWeight.SemiBold
                )
                Spacer(modifier = Modifier.height(8.dp))
            }
            items(recentLocal) { channel ->
                val idx = channels.indexOfFirst { it.url == channel.url }
                Surface(
                    color = MaterialTheme.colorScheme.surface,
                    shape = RoundedCornerShape(8.dp),
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(vertical = 2.dp)
                        .clickable { if (idx >= 0) viewModel.playChannel(idx) }
                ) {
                    Row(
                        modifier = Modifier.padding(horizontal = 12.dp, vertical = 10.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Icon(
                            Icons.Default.Movie,
                            contentDescription = null,
                            tint = MaterialTheme.colorScheme.primary,
                            modifier = Modifier.size(20.dp)
                        )
                        Spacer(modifier = Modifier.width(10.dp))
                        Text(
                            text = channel.name,
                            color = MaterialTheme.colorScheme.onSurface,
                            fontSize = 13.sp,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                            modifier = Modifier.weight(1f)
                        )
                        Icon(
                            Icons.Default.PlayArrow,
                            contentDescription = "播放",
                            tint = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.size(18.dp)
                        )
                    }
                }
            }
        }
    }
}

/** 信息行 */
@Composable
private fun InfoRow(label: String, value: String) {
    Row(
        modifier = Modifier.fillMaxWidth().padding(vertical = 2.dp),
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        Text(text = label, color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 12.sp)
        Text(text = value, color = MaterialTheme.colorScheme.onSurface, fontSize = 12.sp, fontWeight = FontWeight.Medium)
    }
}

/** 时间格式化 */
private fun formatTime(seconds: Double): String {
    if (seconds <= 0) return "00:00"
    val totalSec = seconds.toLong()
    val h = totalSec / 3600
    val m = (totalSec % 3600) / 60
    val s = totalSec % 60
    return if (h > 0) String.format("%d:%02d:%02d", h, m, s) else String.format("%02d:%02d", m, s)
}

// -----------------------------------------------------------------
// EPG 节目单内容（竖屏 Tab 内简化版）
// -----------------------------------------------------------------

@Composable
private fun PortraitEpgContent(viewModel: AppViewModel) {
    val epg by viewModel.currentEpg.collectAsState()
    val loading by viewModel.epgLoading.collectAsState()
    val currentChannel by viewModel.currentChannel.collectAsState()
    val oc = rememberPlayerOverlayColors()

    // 每秒刷新当前时间（用于高亮当前节目）
    var now by remember { mutableStateOf(System.currentTimeMillis()) }
    LaunchedEffect(Unit) {
        while (true) {
            now = System.currentTimeMillis()
            delay(1000L)
        }
    }

    Column(modifier = Modifier.fillMaxSize()) {
        // 标题栏
        Surface(color = oc.infoBarBg, modifier = Modifier.fillMaxWidth()) {
            Row(
                modifier = Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 6.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = "节目单",
                    color = oc.textPrimary,
                    fontSize = 14.sp,
                    fontWeight = FontWeight.Medium
                )
                Spacer(modifier = Modifier.width(8.dp))
                Text(
                    text = currentChannel?.name ?: "未选择频道",
                    color = oc.textSecondary,
                    fontSize = 12.sp,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
            }
        }
        // 内容
        when {
            loading -> {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Text("加载中...", color = oc.textSecondary, fontSize = 13.sp)
                }
            }
            epg.isEmpty() -> {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Text("暂无节目信息", color = oc.textSecondary, fontSize = 13.sp)
                }
            }
            else -> {
                LazyColumn(modifier = Modifier.fillMaxSize()) {
                    items(epg) { program ->
                        val isCurrent = portraitIsCurrentProgram(program, now)
                        val isPast = portraitIsPastProgram(program, now)
                        PortraitEpgItem(
                            program = program,
                            isCurrent = isCurrent,
                            isPast = isPast,
                            oc = oc,
                            onClick = {
                                if (isPast && !isCurrent) {
                                    viewModel.startCatchup(program)
                                } else {
                                    viewModel.toggleReminder(program, currentChannel)
                                }
                            }
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun PortraitEpgItem(
    program: com.iptv.scanner.editor.pro.data.IptvEpgProgram,
    isCurrent: Boolean,
    isPast: Boolean,
    oc: PlayerOverlayColors,
    onClick: () -> Unit
) {
    val bg = if (isCurrent) oc.accent.copy(alpha = 0.15f) else Color.Transparent
    val alpha = if (isPast && !isCurrent) 0.5f else 1f
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .background(bg)
            .clickable(onClick = onClick)
            .padding(horizontal = 12.dp, vertical = 8.dp)
    ) {
        // 时间
        val timeText = buildString {
            append(portraitFormatTime(program.start))
            if (program.stop.isNotEmpty() || program.end.isNotEmpty()) {
                append(" - ")
                append(portraitFormatTime(program.stop.ifEmpty { program.end }))
            }
        }
        Text(
            text = timeText,
            color = if (isCurrent) oc.accent else oc.textSecondary,
            fontSize = 11.sp,
            modifier = Modifier.width(90.dp)
        )
        // 节目标题
        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = program.title,
                color = if (isCurrent) oc.textPrimary else oc.textSecondary,
                fontSize = 13.sp,
                fontWeight = if (isCurrent) FontWeight.Medium else FontWeight.Normal,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis
            )
            if (isCurrent) {
                Surface(
                    color = oc.accent.copy(alpha = 0.2f),
                    shape = RoundedCornerShape(3.dp),
                    modifier = Modifier.padding(top = 2.dp)
                ) {
                    Text(
                        text = "正在播出",
                        color = oc.accent,
                        fontSize = 9.sp,
                        modifier = Modifier.padding(horizontal = 4.dp, vertical = 1.dp)
                    )
                }
            }
        }
    }
}

// EPG 时间解析/格式化辅助
private fun portraitParseTimeMs(iso: String, ts: Long): Long {
    if (ts > 0) return ts * 1000L
    if (iso.isEmpty()) return 0
    val patterns = listOf(
        "yyyy-MM-dd'T'HH:mm:ssXXX",
        "yyyy-MM-dd'T'HH:mm:ss'Z'",
        "yyyy-MM-dd'T'HH:mm:ss",
        "yyyy-MM-dd HH:mm:ss",
        "yyyy-MM-dd HH:mm"
    )
    for (pattern in patterns) {
        try {
            return java.text.SimpleDateFormat(pattern, java.util.Locale.US).parse(iso)?.time ?: continue
        } catch (_: Exception) {}
    }
    return 0
}

private fun portraitFormatTime(iso: String): String {
    if (iso.isEmpty()) return ""
    val ms = portraitParseTimeMs(iso, 0)
    if (ms <= 0) return iso
    val cal = java.util.Calendar.getInstance().apply { timeInMillis = ms }
    return String.format(java.util.Locale.US, "%02d:%02d", cal.get(java.util.Calendar.HOUR_OF_DAY), cal.get(java.util.Calendar.MINUTE))
}

private fun portraitIsCurrentProgram(program: com.iptv.scanner.editor.pro.data.IptvEpgProgram, nowMs: Long): Boolean {
    val startMs = portraitParseTimeMs(program.start, program.startTs)
    val endMs = portraitParseTimeMs(program.end.ifEmpty { program.stop }, program.stopTs)
    return startMs > 0 && endMs > startMs && nowMs >= startMs && nowMs < endMs
}

private fun portraitIsPastProgram(program: com.iptv.scanner.editor.pro.data.IptvEpgProgram, nowMs: Long): Boolean {
    val endMs = portraitParseTimeMs(program.end.ifEmpty { program.stop }, program.stopTs)
    return endMs > 0 && nowMs >= endMs
}

// -----------------------------------------------------------------
// 工具内容（竖屏 Tab）
// -----------------------------------------------------------------

@Composable
private fun PortraitToolsContent(viewModel: AppViewModel) {
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
        item { PortraitSectionHeader("文件", oc) }
        item {
            PortraitListRow("打开本地文件", "播放设备上的视频/音频文件", oc) {
                if (!viewModel.isSafAvailable()) {
                    viewModel.showMediaFileBrowser()
                } else {
                    videoLauncher.launch(arrayOf("video/*", "audio/*", "application/x-matroska", "application/octet-stream"))
                }
            }
        }
        item {
            PortraitListRow("打开播放列表", "导入 M3U/M3U8 文件", oc) {
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
            PortraitListRow("打开网络流", "输入 URL 播放", oc) {
                viewModel.toggleOpenUrlDialog()
            }
        }
        item {
            PortraitListRow("最近打开", "最近播放的文件", oc) { viewModel.toggleRecentPanel() }
        }
        item { PortraitSectionHeader("工具", oc) }
        item {
            PortraitListRow("截图", "截取当前画面", oc, disabled = !isMpv) { viewModel.takeScreenshot("video") }
        }
        item {
            PortraitListRow("切片导出", "导出视频片段", oc, disabled = !isMpv) { viewModel.toggleClipExportPanel() }
        }
        item {
            PortraitListRow("音频可视化", "频谱波形显示", oc, active = audioVisualizerOpen) { viewModel.toggleAudioVisualizer() }
        }
        item {
            PortraitListRow("歌词", "加载/显示歌词", oc, active = lyricsOpen, disabled = !isMpv) { viewModel.toggleLyricsPanel() }
        }
        item {
            PortraitListRow("锁定控制层", "防止误触", oc, active = controlsPinned) { viewModel.toggleControlsPinned() }
        }
        item {
            PortraitListRow("刷新", "重新加载频道/EPG", oc) { viewModel.refreshUi() }
        }
        item {
            PortraitListRow("另存为 M3U", "导出频道列表到下载目录", oc) { viewModel.saveAsM3u() }
        }
        item { PortraitSectionHeader("高级工具", oc) }
        item {
            PortraitListRow("EPG 时间线", "多频道节目时间线", oc) { viewModel.toggleEpgTimelinePanel() }
        }
        item {
            PortraitListRow("全局搜索", "搜索频道/节目", oc) { viewModel.toggleSearchPanel() }
        }
        item {
            PortraitListRow("流质量检测", "检测流质量", oc, disabled = !isMpv) { viewModel.toggleStreamQualityPanel() }
        }
        item {
            PortraitListRow("URL 范围扫描", "扫描整理 URL", oc) { viewModel.toggleScanPanel() }
        }
        item {
            PortraitListRow("节目提醒", "管理提醒", oc) { viewModel.toggleReminderPanel() }
        }
        item {
            PortraitListRow("续播位置", "管理续播", oc) { viewModel.toggleResumePanel() }
        }
        item {
            PortraitListRow("书签管理", "管理书签", oc, disabled = !isMpv) { viewModel.toggleBookmarkPanel() }
        }
        item {
            PortraitListRow("A/V 同步监控", "音视频同步", oc, disabled = !isMpv) { viewModel.toggleAvSyncPanel() }
        }
    }
}

// -----------------------------------------------------------------
// 设置内容（竖屏 Tab）
// -----------------------------------------------------------------

@Composable
private fun PortraitSettingsContent(viewModel: AppViewModel) {
    val oc = rememberPlayerOverlayColors()
    val themeMode by viewModel.themeMode.collectAsState()
    val autoResume by viewModel.autoResume.collectAsState()
    val playerType by viewModel.playerType.collectAsState()
    val isMpv = playerType == PlayerType.MPV

    LazyColumn(modifier = Modifier.fillMaxSize()) {
        item { PortraitSectionHeader("播放", oc) }
        item { PortraitListRow("播放器设置", "${playerType.displayName} 配置${if (isMpv) "（解码/硬件加速/HDR）" else ""}", oc) { viewModel.togglePlayerSettings() } }
        item { PortraitListRow("视频设置", "画面/比例", oc) { viewModel.toggleVideoSettings() } }
        item { PortraitListRow("音频设置", "音轨/音量${if (isMpv) "/均衡器" else ""}", oc) { viewModel.toggleAudioSettings() } }
        item { PortraitListRow("字幕设置", "字幕/外挂字幕", oc, disabled = !isMpv) { viewModel.toggleSubtitleSettings() } }
        item { PortraitListRow("播放设置", "速度/循环/续播", oc) { viewModel.togglePlaybackPanel() } }
        item { PortraitListRow("截图设置", "截图格式/路径", oc, disabled = !isMpv) { viewModel.toggleScreenshotPanel() } }
        item { PortraitListRow("视图设置", "界面/缩放/旋转", oc) { viewModel.toggleViewSettings() } }

        item { PortraitSectionHeader("频道与源", oc) }
        item { PortraitListRow("订阅源管理", "添加/删除订阅源", oc) { viewModel.toggleSourceManager() } }
        item { PortraitListRow("频道映射", "频道号映射", oc) { viewModel.toggleMappingPanel() } }
        item { PortraitListRow("网络增强", "缓存/重连/代理", oc) { viewModel.toggleNetworkPanel() } }

        item { PortraitSectionHeader("通用", oc) }
        item {
            val themeLabel = when (themeMode) { "light" -> "浅色"; "system" -> "跟随系统"; else -> "深色" }
            PortraitListRow("主题模式", "当前: $themeLabel", oc) {
                val next = when (themeMode) { "dark" -> "light"; "light" -> "system"; else -> "dark" }
                viewModel.setThemeMode(next)
            }
        }
        item {
            PortraitListRow("启动自动续播", if (autoResume) "已开启" else "已关闭", oc, active = autoResume) {
                viewModel.setAutoResume(!autoResume)
            }
        }
        item { PortraitListRow("关于", "版本/更新信息", oc) { viewModel.toggleAboutPanel() } }
    }
}

// -----------------------------------------------------------------
// 竖屏底部 Tab 栏
// -----------------------------------------------------------------

@Composable
private fun PortraitBottomTabBar(
    viewModel: AppViewModel,
    modifier: Modifier = Modifier
) {
    val portraitTab by viewModel.portraitTab.collectAsState()
    val bgColor = MaterialTheme.colorScheme.surface
    val accentColor = MaterialTheme.colorScheme.primary
    val tabShape = RoundedCornerShape(20.dp)
    val isAndroid12Plus = android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.S

    val tabItems = listOf(
        Triple(Icons.Default.Home, "首页", AppViewModel.PortraitTab.HOME),
        Triple(Icons.Default.VideoLibrary, "列表", AppViewModel.PortraitTab.LIST),
        Triple(Icons.Default.Build, "工具", AppViewModel.PortraitTab.TOOLS),
        Triple(Icons.Default.Settings, "设置", AppViewModel.PortraitTab.SETTINGS)
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
                        if (tab == AppViewModel.PortraitTab.HOME) {
                            viewModel.showHomeScreen()
                        }
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

@Composable
private fun PortraitTabItem(
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    label: String,
    isSelected: Boolean,
    oc: PlayerOverlayColors,
    onClick: () -> Unit
) {
val tint = if (isSelected) oc.accent else oc.iconTint
Column(
horizontalAlignment = Alignment.CenterHorizontally,
modifier = Modifier
.height(48.dp)
.clip(RoundedCornerShape(10.dp))
.then(if (isSelected) Modifier.border(1.dp, oc.accent.copy(alpha = 0.50f), RoundedCornerShape(10.dp)) else Modifier)
.clickable(onClick = onClick)
.padding(horizontal = 14.dp, vertical = 4.dp)
) {
        Icon(
            imageVector = icon,
            contentDescription = label,
            tint = tint,
            modifier = Modifier.size(24.dp)
        )
        Text(
            text = label,
            color = tint,
            fontSize = 11.sp,
            maxLines = 1
        )
    }
}

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
// ============================================================

/**
 * 第一排：信息栏
 * 居中显示台标+频道名+分类，右侧收藏和信息按钮
 */
@Composable
private fun PortraitInfoBarV2(viewModel: AppViewModel) {
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
                    tint = oc.iconTint,
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
                        color = oc.badgeBg,
                        shape = RoundedCornerShape(4.dp)
                    ) {
                        Text(
                            text = currentChannel!!.group,
                            color = oc.badgeText,
                            fontSize = 11.sp,
                            modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp),
                            maxLines = 1
                        )
                    }
                }
            }
            // 右侧：收藏 + 信息按钮
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
private fun PortraitControlsV2(viewModel: AppViewModel) {
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
                accentColor = oc.accent,
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

/**
 * 竖屏频道列表（频道Tab和收藏Tab共用）
 * 左列分组 + 右列频道（双列布局），无搜索框
 * 每项：台标 + 频道名(+回看标识) + 当前节目名 + 节目单按钮
 */
@Composable
private fun PortraitChannelList(
    viewModel: AppViewModel,
    showFavoritesOnly: Boolean
) {
    val channels by viewModel.channels.collectAsState()
    val currentIdx by viewModel.currentIdx.collectAsState()
    val favorites by viewModel.favorites.collectAsState()
    val selectedGroup by viewModel.selectedGroup.collectAsState()
    val allGroups by viewModel.groups.collectAsState()
    val channelsTab by viewModel.channelsTab.collectAsState()
    val epgCacheVersion by viewModel.epgCacheVersion.collectAsState()
    val oc = rememberPlayerOverlayColors()

    // 预加载所有频道的 EPG（仅需一次）
    LaunchedEffect(channels.size) {
        if (channels.isNotEmpty()) {
            viewModel.preloadEpgForAllChannels()
        }
    }

    // 分组列表
    val groups = remember(allGroups, channels, showFavoritesOnly) {
        if (showFavoritesOnly) {
            channels.mapIndexed { idx, c -> c to idx }
                .filter { (c, idx) -> favorites.contains(idx) }
                .map { it.first.group }
                .filter { it.isNotEmpty() }
                .distinct()
        } else if (channelsTab == ChannelTab.LOCAL) {
            channels
                .filter { it.source.isEmpty() || ProgressHelper.isLocalFile(it.url) }
                .map { it.group }
                .filter { it.isNotEmpty() }
                .distinct()
        } else {
            allGroups
        }
    }
    val showGroups = groups.isNotEmpty()

    // 根据是否收藏模式过滤频道
    val filteredChannels = remember(channels, favorites, showFavoritesOnly, selectedGroup, channelsTab) {
        val all = channels.mapIndexed { idx, c -> c to idx }
        val filtered = if (showFavoritesOnly) {
            all.filter { (c, idx) -> favorites.contains(idx) }
        } else if (channelsTab == ChannelTab.LOCAL) {
            all.filter { (c, _) -> c.source.isEmpty() || ProgressHelper.isLocalFile(c.url) }
        } else {
            all
        }
        filtered.filter { (c, _) ->
            val groupMatch = selectedGroup.isEmpty() || c.group == selectedGroup
            groupMatch
        }
    }

    if (filteredChannels.isEmpty()) {
        val emptyMsg = when {
            showFavoritesOnly -> "暂无收藏\n点击信息栏星标添加"
            channelsTab == ChannelTab.LOCAL -> "暂无本地视频\n暂无本地音乐\n暂无本地播放列表"
            else -> "暂无频道"
        }
        Box(
            modifier = Modifier.fillMaxSize(),
            contentAlignment = Alignment.Center
        ) {
            Text(
                text = emptyMsg,
                color = oc.textSecondary,
                fontSize = 13.sp,
                textAlign = androidx.compose.ui.text.style.TextAlign.Center
            )
        }
    } else {
        if (showGroups) {
            Row(modifier = Modifier.fillMaxSize()) {
                // 左列：分组列表
                PortraitGroupList(
                    groups = groups,
                    selectedGroup = selectedGroup,
                    onGroupSelected = { viewModel.setSelectedGroup(it) },
                    oc = oc,
                    modifier = Modifier.weight(0.35f)
                )
                // 分隔线
                Box(
                    modifier = Modifier
                        .fillMaxHeight()
                        .width(1.dp)
                        .background(oc.trackInactive)
                )
                // 右列：频道列表
                LazyColumn(
                    modifier = Modifier.weight(0.65f).fillMaxHeight(),
                    contentPadding = PaddingValues(vertical = 4.dp)
                ) {
                    items(
                        items = filteredChannels,
                        key = { (channel, idx) -> idx }
                    ) { (channel, idx) ->
                        PortraitChannelListItem(
                            channel = channel,
                            channelIdx = idx,
                            isPlaying = idx == currentIdx,
                            oc = oc,
                            viewModel = viewModel,
                            epgCacheVersion = epgCacheVersion,
                            onPlay = { viewModel.playChannel(idx) },
                            onEpg = { viewModel.playChannelAndShowEpg(idx) }
                        )
                    }
                }
            }
        } else {
            LazyColumn(
                modifier = Modifier.fillMaxSize(),
                contentPadding = PaddingValues(vertical = 4.dp)
            ) {
                items(
                    items = filteredChannels,
                    key = { (channel, idx) -> idx }
                ) { (channel, idx) ->
                    PortraitChannelListItem(
                        channel = channel,
                        channelIdx = idx,
                        isPlaying = idx == currentIdx,
                        oc = oc,
                        viewModel = viewModel,
                        epgCacheVersion = epgCacheVersion,
                        onPlay = { viewModel.playChannel(idx) },
                        onEpg = { viewModel.playChannelAndShowEpg(idx) }
                    )
                }
            }
        }
    }
}

/**
 * 竖屏分组列表（左列）
 */
@Composable
private fun PortraitGroupList(
    groups: List<String>,
    selectedGroup: String,
    onGroupSelected: (String) -> Unit,
    oc: PlayerOverlayColors,
    modifier: Modifier = Modifier
) {
    val allItems = remember(groups) { listOf("") + groups }
    LazyColumn(
        modifier = modifier.fillMaxHeight(),
        contentPadding = PaddingValues(vertical = 4.dp)
    ) {
        items(allItems, key = { it }) { group ->
            val isSelected = selectedGroup == group
            val label = if (group.isEmpty()) "全部" else group
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 4.dp, vertical = 2.dp)
                    .then(if (isSelected) Modifier.border(1.dp, oc.accent.copy(alpha = 0.50f), RoundedCornerShape(8.dp)) else Modifier)
                    .clickable { onGroupSelected(group) }
                    .padding(horizontal = 8.dp, vertical = 8.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Box(
                    modifier = Modifier
                        .width(3.dp)
                        .height(16.dp)
                        .clip(RoundedCornerShape(2.dp))
                        .background(if (isSelected) oc.accent else Color.Transparent)
                )
                Spacer(modifier = Modifier.width(6.dp))
                Text(
                    text = label,
                    color = if (isSelected) oc.accent else oc.textSecondary,
                    fontSize = 12.sp,
                    fontWeight = if (isSelected) FontWeight.Medium else FontWeight.Normal,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
            }
        }
    }
}

/**
 * 竖屏频道列表项
 * 台标 + 频道名(+回看标识) + 当前节目名 + 节目单按钮
 */
@Composable
private fun PortraitChannelListItem(
    channel: IptvChannel,
    channelIdx: Int,
    isPlaying: Boolean,
    oc: PlayerOverlayColors,
    viewModel: AppViewModel,
    epgCacheVersion: Int,
    onPlay: () -> Unit,
    onEpg: () -> Unit
) {
    // 获取缓存的当前节目
    var currentProgram by remember { mutableStateOf<com.iptv.scanner.editor.pro.data.IptvEpgProgram?>(null) }
    LaunchedEffect(channelIdx, epgCacheVersion) {
        currentProgram = viewModel.getCachedCurrentProgram(channelIdx)
        while (true) {
            delay(5_000L)
            currentProgram = viewModel.getCachedCurrentProgram(channelIdx)
        }
    }

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 4.dp, vertical = 2.dp)
            .then(if (isPlaying) Modifier.border(1.dp, oc.accent.copy(alpha = 0.40f), RoundedCornerShape(8.dp)) else Modifier)
            .clickable(onClick = onPlay)
            .padding(horizontal = 8.dp, vertical = 4.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        // 台标
        if (channel.logo.isNotEmpty()) {
            AsyncImage(
                model = channel.logo,
                contentDescription = channel.name,
                modifier = Modifier
                    .size(36.dp)
                    .clip(RoundedCornerShape(4.dp)),
                contentScale = ContentScale.Fit
            )
            Spacer(modifier = Modifier.width(8.dp))
        } else {
            // 无台标占位
            Box(
                modifier = Modifier
                    .size(36.dp)
                    .clip(RoundedCornerShape(4.dp))
                    .background(oc.badgeBg),
                contentAlignment = Alignment.Center
            ) {
                Text(
                    text = channel.name.take(1),
                    color = oc.textSecondary,
                    fontSize = 14.sp
                )
            }
            Spacer(modifier = Modifier.width(8.dp))
        }

        // 频道名 + 节目名
        Column(modifier = Modifier.weight(1f)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    text = channel.name,
                    color = if (isPlaying) oc.accent else oc.textPrimary,
                    fontSize = 14.sp,
                    fontWeight = if (isPlaying) FontWeight.Medium else FontWeight.Normal,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
            }
            // 当前节目名
            if (currentProgram != null && currentProgram!!.title.isNotEmpty()) {
                Text(
                    text = currentProgram!!.title,
                    color = oc.textSecondary,
                    fontSize = 11.sp,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
            } else {
                Text(
                    text = "精彩节目",
                    color = oc.textSecondary,
                    fontSize = 11.sp,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
            }
        }

        // 回看标识（居右，节目单按钮左边）
        if (channel.catchup.isNotEmpty() && channel.catchup != "none") {
            Surface(
                color = oc.accent.copy(alpha = 0.15f),
                shape = RoundedCornerShape(3.dp)
            ) {
                Text(
                    text = "回看",
                    color = oc.accent,
                    fontSize = 9.sp,
                    modifier = Modifier.padding(horizontal = 4.dp, vertical = 1.dp)
                )
            }
            Spacer(modifier = Modifier.width(2.dp))
        }

        // 节目单按钮
        IconButton(
            onClick = onEpg,
            modifier = Modifier.size(32.dp)
        ) {
            Icon(
                Icons.Default.CalendarMonth,
                contentDescription = "节目单",
                tint = oc.iconTint,
                modifier = Modifier.size(18.dp)
            )
        }
    }
}

/**
 * 频道信息详情对话框
 */
@Composable
private fun ChannelInfoDialog(viewModel: AppViewModel) {
    val currentChannel by viewModel.currentChannel.collectAsState()
    val mpv = viewModel.mpv
    val videoWidth by mpv.videoWidth.collectAsState()
    val videoHeight by mpv.videoHeight.collectAsState()
    val currentProgram = viewModel.getCurrentProgram()
    val oc = rememberPlayerOverlayColors()

AlertDialog(
onDismissRequest = { viewModel.toggleChannelInfo() },
containerColor = oc.topBarBg.copy(alpha = 0.80f),
shape = RoundedCornerShape(20.dp),
modifier = Modifier.border(1.dp, oc.accent.copy(alpha = 0.35f), RoundedCornerShape(20.dp)),
        title = {
            Row(verticalAlignment = Alignment.CenterVertically) {
                if (currentChannel != null && currentChannel!!.logo.isNotEmpty()) {
                    AsyncImage(
                        model = currentChannel!!.logo,
                        contentDescription = null,
                        modifier = Modifier
                            .size(32.dp)
                            .clip(RoundedCornerShape(4.dp)),
                        contentScale = ContentScale.Fit
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                }
                Text(
                    text = currentChannel?.name ?: "频道信息",
                    color = oc.textPrimary,
                    fontSize = 16.sp,
                    fontWeight = FontWeight.Medium
                )
            }
        },
        text = {
            Column(modifier = Modifier.fillMaxWidth()) {
                currentChannel?.let { ch ->
                    InfoRow("频道名", ch.name, oc)
                    if (ch.group.isNotEmpty()) InfoRow("分类", ch.group, oc)
                    if (ch.tvgId.isNotEmpty()) InfoRow("TVG-ID", ch.tvgId, oc)
                    if (ch.tvgName.isNotEmpty()) InfoRow("TVG-Name", ch.tvgName, oc)
                    if (ch.tvgChno.isNotEmpty()) InfoRow("频道号", ch.tvgChno, oc)
                    if (ch.resolution.isNotEmpty()) InfoRow("分辨率", ch.resolution, oc)
                    if (videoWidth > 0 && videoHeight > 0) {
                        InfoRow("视频尺寸", "${videoWidth}x${videoHeight}", oc)
                    }
if (ch.catchup.isNotEmpty() && ch.catchup != "none") {
    if (ch.catchupDays.isNotEmpty()) InfoRow("回看天数", ch.catchupDays, oc)
}
if (ch.source.isNotEmpty()) InfoRow("来源", ch.source, oc)
// 状态字段仅在有实际状态时显示（去掉“待检测”）
if (ch.status.isNotEmpty() && ch.status != "待检测") InfoRow("状态", ch.status, oc)
InfoRow("URL", ch.url, oc)
// 回看 URL
if (ch.catchup.isNotEmpty() && ch.catchup != "none") {
    val catchupUrl = if (ch.catchupSource.isNotEmpty()) ch.catchupSource else ch.catchup
    InfoRow("回看URL", catchupUrl, oc)
}
                    // 当前节目
                    if (currentProgram != null && currentProgram.title.isNotEmpty()) {
                        Spacer(modifier = Modifier.height(8.dp))
                        Text(
                            text = "当前节目",
                            color = oc.accent,
                            fontSize = 12.sp,
                            fontWeight = FontWeight.Medium
                        )
                        Text(
                            text = currentProgram.title,
                            color = oc.textPrimary,
                            fontSize = 13.sp,
                            modifier = Modifier.padding(top = 2.dp)
                        )
                    }
                } ?: run {
                    Text(
                        text = "未选择频道",
                        color = oc.textSecondary,
                        fontSize = 14.sp
                    )
                }
            }
        },
        confirmButton = {
            Button(
                onClick = { viewModel.toggleChannelInfo() },
                colors = ButtonDefaults.buttonColors(containerColor = oc.accent)
            ) {
                Text("关闭", color = MaterialTheme.colorScheme.onSecondary)
            }
        }
    )
}

@Composable
private fun InfoRow(label: String, value: String, oc: PlayerOverlayColors) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 3.dp),
        verticalAlignment = Alignment.Top
    ) {
        Text(
            text = "$label:",
            color = oc.textSecondary,
            fontSize = 12.sp,
            modifier = Modifier.width(60.dp)
        )
        Text(
            text = value,
            color = oc.textPrimary,
            fontSize = 12.sp,
            modifier = Modifier.weight(1f),
            maxLines = 5,
            overflow = TextOverflow.Ellipsis
        )
    }
}

/**
 * 视频参数信息行：显示视频编码、分辨率、音频编码、HDR/WCG 信息
 */
@Composable
private fun PortraitMediaInfoBar(viewModel: AppViewModel) {
    val player = viewModel.mpv
    val fileLoaded by player.fileLoaded.collectAsState()
    val videoWidth by player.videoWidth.collectAsState()
    val videoHeight by player.videoHeight.collectAsState()
    val playerType by viewModel.playerType.collectAsState()
    val oc = rememberPlayerOverlayColors()

    // 1秒刷新媒体信息
    var tick by remember { mutableStateOf(0L) }
    LaunchedEffect(fileLoaded) {
        if (fileLoaded) {
            while (true) {
                tick = System.currentTimeMillis()
                delay(2000L)
            }
        }
    }

    val mediaInfo = remember(tick, fileLoaded, videoWidth, videoHeight) {
        // 只有在文件已加载且视频尺寸有效时才获取媒体信息
        // 停止状态（fileLoaded=false）不显示任何媒体信息
        if (fileLoaded && (videoWidth > 0 || videoHeight > 0)) player.getMediaInfo() else emptyMap()
    }

    // 停止状态（未加载文件）不显示媒体信息栏
    if (!fileLoaded) {
        Box(modifier = Modifier.fillMaxWidth().height(0.dp))
        return
    }

    Surface(
        color = oc.infoBarBg,
        modifier = Modifier
            .fillMaxWidth()
            .padding(top = 2.dp)  // 与视频区域间距
    ) {
        if (mediaInfo.isNotEmpty()) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(28.dp)
                    .padding(horizontal = 8.dp, vertical = 2.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                // 视频编码（清理前缀：video/hevc → HEVC）
                mediaInfo["videoCodec"]?.takeIf { it.isNotEmpty() && it != "null" }?.let { codec ->
                    val cleanCodec = codec.removePrefix("video/").removePrefix("audio/").uppercase()
                    MediaBadge(label = cleanCodec, oc = oc)
                }
                // 分辨率
                if (videoWidth > 0 && videoHeight > 0) {
                    val resLabel = if (videoHeight >= 2160) "4K"
                        else if (videoHeight >= 1080) "1080P"
                        else if (videoHeight >= 720) "720P"
                        else if (videoHeight >= 480) "480P"
                        else "${videoHeight}P"
                    MediaBadge(label = resLabel, oc = oc)
                    MediaBadge(label = "${videoWidth}×${videoHeight}", oc = oc, isAccent = false)
                }
                // FPS
                mediaInfo["fps"]?.takeIf { it.isNotEmpty() && it != "null" && it != "0" && it != "0.000" }?.let { fps ->
                    val fpsVal = fps.toFloatOrNull()
                    val fpsLabel = if (fpsVal != null) "${fpsVal.toInt()}fps" else "${fps}fps"
                    MediaBadge(label = fpsLabel, oc = oc)
                }
                // 音频编码（清理前缀：audio/aac → AAC）
                mediaInfo["audioCodec"]?.takeIf { it.isNotEmpty() && it != "null" }?.let { codec ->
                    val cleanCodec = codec.removePrefix("audio/").removePrefix("video/").uppercase()
                    MediaBadge(label = cleanCodec, oc = oc, isAccent = false)
                }
                // HDR / HLG / WCG 检测
                val primaries = mediaInfo["videoPrimaries"]
                val gamma = mediaInfo["videoGamma"]
                if (primaries == "bt.2020" || primaries == "bt.2100") {
                    when (gamma) {
                        "pq" -> MediaBadge(label = "HDR10", oc = oc, isHighlight = true)
                        "hlg" -> MediaBadge(label = "HLG", oc = oc, isHighlight = true)
                        else -> MediaBadge(label = "WCG", oc = oc)
                    }
                }
                // 硬件解码
                mediaInfo["hwdec"]?.takeIf { it.isNotEmpty() && it != "null" && it != "no" }?.let { hwdec ->
                    MediaBadge(label = "HW", oc = oc, isAccent = false)
                }
            }
        } else {
            // 文件已加载但视频尺寸未知（纯音频流），显示播放器类型
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(22.dp)
                    .padding(horizontal = 8.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = "内核: ${playerType.name}",
                    color = oc.textSecondary,
                    fontSize = 10.sp
                )
            }
        }
    }
}

@Composable
private fun MediaBadge(
    label: String,
    oc: PlayerOverlayColors,
    isAccent: Boolean = true,
    isHighlight: Boolean = false
) {
    // 统一颜色：所有 badge 用同一种背景和文字色，除 HDR/HLG 高亮外
    val bg = if (isHighlight) Color(0xFFFF6B00).copy(alpha = 0.2f)
             else oc.accent.copy(alpha = 0.15f)
    val fg = if (isHighlight) Color(0xFFFF9800)
             else oc.accent
    Surface(
        color = bg,
        shape = RoundedCornerShape(3.dp)
    ) {
        Text(
            text = label,
            color = fg,
            fontSize = 9.sp,
            fontWeight = FontWeight.Medium,
            modifier = Modifier.padding(horizontal = 4.dp, vertical = 1.dp),
            maxLines = 1
        )
    }
}

/**
 * 竖屏模式面板弹窗包装器：将全屏面板包装为居中弹窗
 * 半透明背景 + 圆角 + 边框，点击外部关闭
 */
@Composable
fun PortraitPanelDialog(
    onDismiss: () -> Unit,
    content: @Composable () -> Unit
) {
    val oc = rememberPlayerOverlayColors()
    val isAndroid12Plus = android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.S
    val dialogShape = RoundedCornerShape(20.dp)
    val configuration = androidx.compose.ui.platform.LocalConfiguration.current
    val isLandscape = configuration.orientation == android.content.res.Configuration.ORIENTATION_LANDSCAPE
    val context = androidx.compose.ui.platform.LocalContext.current
    val isTv = context.packageManager.hasSystemFeature(android.content.pm.PackageManager.FEATURE_LEANBACK)
    if (isTv) {
        Box(
            modifier = Modifier
                .fillMaxSize()
                .background(Color.Black.copy(alpha = 0.5f))
        ) {
            Box(
                modifier = Modifier
                    .align(Alignment.Center)
                    .fillMaxWidth(0.75f)
                    .fillMaxHeight(0.82f)
            ) {
                Surface(
                    color = oc.topBarBg.copy(alpha = 0.85f),
                    shape = dialogShape,
                    border = BorderStroke(1.dp, oc.accent.copy(alpha = 0.35f)),
                    modifier = Modifier.matchParentSize()
                ) {
                    content()
                }
            }
        }
    } else {
        Dialog(
            onDismissRequest = onDismiss,
            properties = DialogProperties(
                usePlatformDefaultWidth = false,
                dismissOnBackPress = true,
                dismissOnClickOutside = false
            )
        ) {
            Box(
                modifier = Modifier
                    .then(if (isLandscape) Modifier.fillMaxWidth(0.75f).fillMaxHeight(0.82f) else Modifier.fillMaxWidth(0.92f).fillMaxHeight(0.85f))
            ) {
                if (isAndroid12Plus) {
                    Box(
                        modifier = Modifier
                            .matchParentSize()
                            .blur(25.dp)
                            .background(oc.topBarBg.copy(alpha = 0.55f), dialogShape)
                    )
                }
                Surface(
                    color = if (isAndroid12Plus) oc.topBarBg.copy(alpha = 0.30f) else oc.topBarBg.copy(alpha = 0.80f),
                    shape = dialogShape,
                    border = BorderStroke(1.dp, oc.accent.copy(alpha = 0.35f)),
                    modifier = Modifier.matchParentSize()
                ) {
                    content()
                }
            }
        }
    }
}
