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
import com.iptv.scanner.editor.pro.mpv.MPVTextureView
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
    // 竖屏：手机竖屏观看
    // 横屏：手机横屏 + TV横屏，统一侧边栏风格，支持触控+遥控器
    val portraitSplit = isPortrait && !multiViewState.active

    // 全局EPG预加载（竖屏+横屏统一）：频道加载后立即预加载，15秒后重试
    val globalChannels by viewModel.channels.collectAsState()
    LaunchedEffect(globalChannels.size) {
        if (globalChannels.isNotEmpty()) {
            viewModel.preloadEpgForAllChannels()
            kotlinx.coroutines.delay(15000)
            viewModel.preloadEpgForAllChannels()
        }
    }

// -----------------------------------------------------------------
// 屏幕旋转修复：检测方向变化，恢复播放
//
// 优化策略：
// 1. 使用 remember（无 key）保持同一个 movableContentOf，避免旋转时重建 AndroidView
// 2. 旋转只触发 surfaceDestroyed → surfaceCreated 生命周期
// 3. surfaceCreated 中检测到 path 非空会自动恢复渲染
// 4. 本 LaunchedEffect 作为快速兜底：缩短等待时间至 300ms，
//    使用渐进式重试（300ms → 500ms → 800ms），减少旋转中断时间
// -----------------------------------------------------------------
LaunchedEffect(isPortrait) {
if (viewModel.playerType.value == PlayerType.MPV && viewModel.mpv.fileLoaded.value) {
Log.i("MainPlayerScreen", "Rotation detected: isPortrait=$isPortrait")
// 快速检测：300ms 后检查视频是否恢复（surfaceCreated 通常在 100-200ms 内完成）
kotlinx.coroutines.delay(300)
var path = viewModel.mpvGetPath()
var w = viewModel.mpv.videoWidth.value
var h = viewModel.mpv.videoHeight.value
Log.i("MainPlayerScreen", "After rotation (300ms): path=$path, ${w}x${h}")
if (path.isNotEmpty() && (w == 0 || h == 0)) {
// 第一次重试：等待 200ms 后再次检查
kotlinx.coroutines.delay(200)
w = viewModel.mpv.videoWidth.value
h = viewModel.mpv.videoHeight.value
if (w == 0 || h == 0) {
Log.i("MainPlayerScreen", "Video not restored after 500ms, reloading: $path")
viewModel.mpvSuppressFileError()
viewModel.mpv.playFile(path)
kotlinx.coroutines.delay(300)
viewModel.mpvClearSuppressFileError()
}
} else if (path.isEmpty()) {
val savedPath = com.iptv.scanner.editor.pro.mpv.MPVView.sharedState.savedPlaybackPath
if (savedPath != null) {
Log.i("MainPlayerScreen", "Path empty after rotation, restoring from saved: $savedPath")
viewModel.mpvSuppressFileError()
viewModel.mpv.playFile(savedPath)
kotlinx.coroutines.delay(500)
viewModel.mpvClearSuppressFileError()
}
}
// 恢复音量和静音状态（MPV 属性在 loadfile 后可能被重置）
val savedVol = viewModel.mpv.volume.value
val savedMute = viewModel.mpv.muted.value
if (savedVol > 0) viewModel.mpv.setVolume(savedVol)
viewModel.mpv.setMute(savedMute)
}
// ExoPlayer: 旋转后检查播放状态，恢复音频和音量
if (viewModel.playerType.value == PlayerType.EXO && viewModel.mpv.fileLoaded.value) {
Log.i("MainPlayerScreen", "Rotation detected (EXO): isPortrait=$isPortrait")
kotlinx.coroutines.delay(300)
if (viewModel.mpv.paused.value) {
Log.i("MainPlayerScreen", "EXO paused after rotation, resuming")
viewModel.mpv.setPause(false)
}
// 恢复音量和静音状态
val savedVol = viewModel.mpv.volume.value
val savedMute = viewModel.mpv.muted.value
if (savedVol > 0) viewModel.mpv.setVolume(savedVol)
viewModel.mpv.setMute(savedMute)
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
                                    PortraitTab.HOME -> PortraitHomeScreen(
                                        viewModel = viewModel,
                                        playlistLauncher = playlistLauncher,
                                        videoLauncher = videoLauncher
                                    )
                                    PortraitTab.LIST -> PortraitListScreen(
                                        viewModel = viewModel,
                                        playlistLauncher = playlistLauncher,
                                        videoLauncher = videoLauncher
                                    )
                                    PortraitTab.TOOLS -> PortraitToolsContent(viewModel = viewModel)
                                    PortraitTab.SETTINGS -> PortraitSettingsContent(viewModel = viewModel)
                                }
                            }
                            PortraitBottomTabBar(viewModel = viewModel)
                        }
                    }
                }
            } else {
                // ---- 横屏模式（手机横屏 + TV横屏统一） ----

                if (multiViewState.active) {
                    // ---- 多画面模式：沉浸式侧边栏 + 底栏 ----
                    TvPlayerLayout(
                        viewModel = viewModel,
                        primaryPlayer = {
                            MultiViewOverlay(
                                state = multiViewState,
                                primaryContent = { primaryPlayer() },
                                getSubPlayer = { idx -> viewModel.getSubPlayer(idx) },
                                onViewportClick = { idx ->
                                    viewModel.setFocusedViewport(idx)
                                },
                                onViewportClose = { idx -> viewModel.removeFromMultiView(idx) },
                                onToggleMute = { idx -> viewModel.toggleMultiViewMute(idx) },
                                onExit = { viewModel.exitMultiView() }
                            )
                        },
                        videoAspectRatio = aspectRatio
                    )
                } else {
                    // ---- 单画面模式：侧边栏风格沉浸式侧边栏 + 底栏 ----
                    TvPlayerLayout(
                        viewModel = viewModel,
                        primaryPlayer = { primaryPlayer() },
                        videoAspectRatio = aspectRatio
                    )
                }
            }

        // 主菜单 — PHONE 全屏覆盖 / TV 侧边栏风格右侧菜单
        if (menuPanelOpen) {
            MainMenuPanel(viewModel = viewModel)
        }

        // TV 端频道列表（侧边栏风格左侧面板：分组 + 频道 + EPG + 描述）
        if (tvUnifiedPanelOpen) {
            val origDensity = androidx.compose.ui.platform.LocalDensity.current
            val dpiScale = (configuration.screenHeightDp / 720f).coerceIn(0.55f, 1f)
            val scaledDensity = androidx.compose.ui.unit.Density(origDensity.density * dpiScale, origDensity.fontScale)
            androidx.compose.runtime.CompositionLocalProvider(androidx.compose.ui.platform.LocalDensity provides scaledDensity) {
                TvUnifiedPanel(viewModel = viewModel)
            }
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
