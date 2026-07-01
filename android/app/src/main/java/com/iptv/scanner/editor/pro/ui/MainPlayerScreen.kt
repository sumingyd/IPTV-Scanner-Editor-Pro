package com.iptv.scanner.editor.pro.ui

import android.content.Context
import android.util.Log
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
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
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CalendarMonth
import androidx.compose.material.icons.filled.Menu
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.VideoLibrary
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import com.iptv.scanner.editor.pro.data.ReminderItem
import com.iptv.scanner.editor.pro.data.UserPrefs
import com.iptv.scanner.editor.pro.mpv.MPVView
import com.iptv.scanner.editor.pro.player.ExoPlayerView
import com.iptv.scanner.editor.pro.player.IjkVideoView
import com.iptv.scanner.editor.pro.player.PlayerType
import com.iptv.scanner.editor.pro.player.VlcVideoView

/**
 * 主播放屏：MPVView + 透明控制层 + 面板抽屉 + OSD 浮层。
 *
 * 层次结构（从底到顶）：
 * 1. MPVView（全屏视频渲染，SurfaceView，setZOrderOnTop=true）
 * 2. 透明点击层（点击切换控制层显示/隐藏，仅当无面板打开时启用）
 * 3. 控制层（顶部侧边栏按钮 + 底部 ControlPanel，仅当 controlsVisible=true 且无面板打开时显示）
 * 4. 面板层（ChannelsPanel 右抽屉 / EpgPanel 左抽屉 / MainMenuPanel 全屏覆盖）
 * 5. OSD 浮层（顶部居中，3 秒自动隐藏，最顶层确保反馈可见）
 *
 * 与 PC 端 mobile/index.html 主框架对齐：
 * - 点击视频区域切换控制层
 * - 控制层显示时，顶部有 3 个面板入口（频道列表/EPG/菜单）
 * - 控制层底部是 ControlPanel（3 行布局）
 * - 面板打开时控制层自动隐藏
 */
@Composable
fun MainPlayerScreen(viewModel: AppViewModel) {
    val uiMode by viewModel.uiMode.collectAsState()
    val currentChannel by viewModel.currentChannel.collectAsState()
    val controlsVisible by viewModel.controlsVisible.collectAsState()
    val channelsPanelOpen by viewModel.channelsPanelOpen.collectAsState()
    val epgPanelOpen by viewModel.epgPanelOpen.collectAsState()
    val menuPanelOpen by viewModel.menuPanelOpen.collectAsState()
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
    val triggeredReminder by viewModel.triggeredReminder.collectAsState()
    val osd by viewModel.osd.collectAsState()

    // 多播放器支持：根据 playerType 创建对应 View
    val playerType by viewModel.playerType.collectAsState()
    val player = viewModel.mpv  // 当前 Player 实例（类型为 Player 接口）
    val paused by player.paused.collectAsState()
    val videoWidth by player.videoWidth.collectAsState()
    val videoHeight by player.videoHeight.collectAsState()
    val fileLoaded by player.fileLoaded.collectAsState()

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

    // 是否有任何面板打开（控制层在面板打开时自动隐藏）
    // 注意：openUrlDialogOpen 不计入，因为 AlertDialog 有独立 scrim，不需要隐藏控制层
    val anyPanelOpen = channelsPanelOpen || epgPanelOpen || menuPanelOpen ||
            sourceManagerOpen || playerSettingsOpen ||
            videoSettingsOpen || audioSettingsOpen || subtitleSettingsOpen || subtitleSearchOpen ||
            playbackPanelOpen || screenshotPanelOpen || viewSettingsOpen || aboutPanelOpen ||
            mappingPanelOpen || avSyncPanelOpen || networkPanelOpen || toolsPanelOpen || scanPanelOpen ||
            reminderPanelOpen || resumePanelOpen || bookmarkPanelOpen ||
            epgTimelineOpen || searchPanelOpen
    // 控制层是否应该显示
    val showControls = controlsVisible && !anyPanelOpen

    Box(
        modifier = Modifier
            .fillMaxSize()
            // 关键：不能设置不透明 background！
            // SurfaceView 默认 Z-order 在普通 View 后面，不透明 background 会遮挡视频画面
            // 黑色背景由 Activity window background + SurfaceView 自身提供
    ) {
        // -----------------------------------------------------------------
        // 1. 底层：播放器 View（根据 playerType 创建 MPVView/ExoPlayerView/VlcVideoView/IjkVideoView）
        //
        // 用 key(playerType) 强制在切换播放器时重建 View（AndroidView 的 factory 不会因
        // state 变化重新执行，必须用 key 包裹才能销毁旧 View 创建新 View）。
        //
        // 关键：不用 fillMaxSize！用 aspectRatio 让 SurfaceView 尺寸匹配视频比例。
        // 这样 Surface buffer 尺寸 = 视频比例尺寸，MediaCodec 不会拉伸视频。
        // SurfaceView 居中显示，上下/左右黑边由根 Box 的黑色背景提供。
        // -----------------------------------------------------------------
        key(playerType) {
            AndroidView(
                factory = { ctx ->
                    Log.i("MainPlayerScreen", "Creating player view, playerType=$playerType, uiMode=$uiMode")
                    when (playerType) {
                        PlayerType.MPV -> {
                            // MPVView 需要先 initialize(configDir, cacheDir, vo, hwdec) 创建 mpv 实例
                            // 再 attach 到 MpvController（注册 EventObserver 转发事件到 StateFlow）
                            val mpvView = MPVView(ctx)
                            val configDir = ctx.getDir("mpv_config", Context.MODE_PRIVATE).absolutePath
                            val cacheDir = ctx.cacheDir.absolutePath
                            // 从 UserPrefs 读取持久化的 vo/hwdec：
                            // - 首次安装用默认值 gpu/auto-copy
                            // - 黑屏 fallback 成功后持久化为 mediacodec_embed，下次直接用，跳过黑屏探测
                            val userPrefs = UserPrefs.getInstance()
                            val vo = userPrefs.getVo()
                            val hwdec = userPrefs.getHwdec()
                            try {
                                mpvView.initialize(configDir, cacheDir, vo = vo, hwdec = hwdec)
                                // 绑定 Player（attachView 转发到 MpvController.attach）
                                player.attachView(mpvView)
                                Log.i("MainPlayerScreen", "MPVView initialized (vo=$vo, hwdec=$hwdec) + attached")
                            } catch (e: Throwable) {
                                Log.e("MainPlayerScreen", "MPVView initialize failed", e)
                            }
                            // 切换播放器后的状态恢复（consumePendingRestore 返回非 null 表示有待恢复状态）
                            viewModel.consumePendingRestore()?.let { (url, time) ->
                                Log.i("MainPlayerScreen", "Restoring playback: $url @ ${time}s")
                                player.restorePlaybackState(url, time)
                            }
                            mpvView
                        }
                        PlayerType.EXO -> {
                            val exoView = ExoPlayerView(ctx)
                            player.attachView(exoView)
                            viewModel.consumePendingRestore()?.let { (url, time) ->
                                Log.i("MainPlayerScreen", "Restoring playback (Exo): $url @ ${time}s")
                                player.restorePlaybackState(url, time)
                            }
                            exoView
                        }
                        PlayerType.VLC -> {
                            val vlcView = VlcVideoView(ctx)
                            player.attachView(vlcView)
                            viewModel.consumePendingRestore()?.let { (url, time) ->
                                Log.i("MainPlayerScreen", "Restoring playback (VLC): $url @ ${time}s")
                                player.restorePlaybackState(url, time)
                            }
                            vlcView
                        }
                        PlayerType.IJK -> {
                            val ijkView = IjkVideoView(ctx)
                            player.attachView(ijkView)
                            viewModel.consumePendingRestore()?.let { (url, time) ->
                                Log.i("MainPlayerScreen", "Restoring playback (IJK): $url @ ${time}s")
                                player.restorePlaybackState(url, time)
                            }
                            ijkView
                        }
                    }
                },
                update = { /* 各 View 的 surfaceChanged 等回调内部已处理 */ },
                modifier = Modifier
                    .align(Alignment.Center)
                    .aspectRatio(aspectRatio)
            )
        }

        // Activity 销毁时 detach 播放器
        // 注：真正的 detach 在 Activity.onDestroy 里调用，这里只做占位
        DisposableEffect(Unit) {
            onDispose { /* 见 Activity.onDestroy */ }
        }

        // -----------------------------------------------------------------
        // 2. 透明点击层（点击切换控制层显示/隐藏）
        // -----------------------------------------------------------------
        // 仅当无面板打开时启用点击切换（面板打开时点击由面板自身处理）
        if (!anyPanelOpen) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .clickable { viewModel.toggleControls() }
            )
        }

        // -----------------------------------------------------------------
        // 3. 控制层（顶部侧边栏按钮 + 底部 ControlPanel）
        // -----------------------------------------------------------------
        AnimatedVisibility(
            visible = showControls,
            enter = fadeIn(),
            exit = fadeOut()
        ) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .background(Color(0x66000000))
            ) {
                Column(
                    modifier = Modifier.fillMaxSize(),
                    verticalArrangement = Arrangement.SpaceBetween
                ) {
                    // ----------------- 顶部：频道名 + 面板入口按钮 -----------------
                    TopBar(
                        channelName = currentChannel?.name ?: "未选择频道",
                        mode = if (uiMode.isTV) "TV" else "PHONE",
                        paused = paused,
                        onChannelsClick = { viewModel.showChannelsPanel() },
                        onEpgClick = { viewModel.showEpgPanel() },
                        onMenuClick = { viewModel.showMenuPanel() }
                    )

                    // ----------------- 中间空白（让视频可见）-----------------

                    // ----------------- 底部：ControlPanel（3 行布局） -----------------
                    ControlPanel(viewModel = viewModel)
                }
            }
        }

        // -----------------------------------------------------------------
        // 4. 面板层
        // -----------------------------------------------------------------
        // 频道列表（右侧抽屉）
        if (channelsPanelOpen) {
            Row(modifier = Modifier.fillMaxSize()) {
                // 左侧空白可点击关闭
                Box(
                    modifier = Modifier
                        .weight(1f)
                        .fillMaxHeight()
                        .background(Color(0x88000000))
                        .clickable { viewModel.toggleChannelsPanel() }
                )
                // 右侧面板
                ChannelsPanel(viewModel = viewModel)
            }
        }

        // EPG 节目单（左侧抽屉）
        if (epgPanelOpen) {
            Row(modifier = Modifier.fillMaxSize()) {
                // 左侧面板
                EpgPanel(viewModel = viewModel)
                // 右侧空白可点击关闭
                Box(
                    modifier = Modifier
                        .weight(1f)
                        .fillMaxHeight()
                        .background(Color(0x88000000))
                        .clickable { viewModel.toggleEpgPanel() }
                )
            }
        }

        // 主菜单（全屏覆盖）
        if (menuPanelOpen) {
            MainMenuPanel(viewModel = viewModel)
        }

        // 订阅源管理（全屏覆盖）
        if (sourceManagerOpen) {
            SourceManagerPanel(viewModel = viewModel)
        }

        // 播放器设置（全屏覆盖，主菜单 → 设置 → 播放器设置）
        if (playerSettingsOpen) {
            PlayerSettingsPanel(viewModel = viewModel)
        }

        // 视频设置（全屏覆盖，主菜单 → 播放 → 视频）
        if (videoSettingsOpen) {
            VideoSettingsPanel(viewModel = viewModel)
        }

        // 音频设置（全屏覆盖，主菜单 → 播放 → 音频）
        if (audioSettingsOpen) {
            AudioSettingsPanel(viewModel = viewModel)
        }

        // 字幕设置（全屏覆盖，含外挂字幕文件选择器）
        if (subtitleSettingsOpen) {
            SubtitleSettingsPanel(viewModel = viewModel)
        }
        if (subtitleSearchOpen) {
            SubtitleSearchPanel(viewModel = viewModel)
        }

        // 播放设置（全屏覆盖，主菜单 → 播放 → 播放）
        if (playbackPanelOpen) {
            PlaybackPanel(viewModel = viewModel)
        }

        // 截图（全屏覆盖，主菜单 → 播放 → 截图）
        if (screenshotPanelOpen) {
            ScreenshotPanel(viewModel = viewModel)
        }

        // 视图设置（全屏覆盖，主菜单 → 播放 → 视图）
        if (viewSettingsOpen) {
            ViewSettingsPanel(viewModel = viewModel)
        }

        // 关于（全屏覆盖，主菜单 → 播放 → 关于）
        if (aboutPanelOpen) {
            AboutPanel(viewModel = viewModel)
        }

        // 频道映射（全屏覆盖，主菜单 → 文件 → 频道映射）
        if (mappingPanelOpen) {
            MappingPanel(viewModel = viewModel)
        }

        // A/V 同步监控（全屏覆盖，主菜单 → 播放 → A/V 同步监控）
        if (avSyncPanelOpen) {
            AvSyncPanel(viewModel = viewModel)
        }

        // 网络增强（全屏覆盖，主菜单 → 播放 → 网络增强）
        if (networkPanelOpen) {
            NetworkPanel(viewModel = viewModel)
        }

        // 工具（全屏覆盖，主菜单 → 播放 → 工具）
        if (toolsPanelOpen) {
            ToolsPanel(viewModel = viewModel)
        }

        // URL 范围扫描（全屏覆盖，工具 → 扫描整理）
        if (scanPanelOpen) {
            ScanPanel(viewModel = viewModel)
        }

        // 节目提醒管理（全屏覆盖，工具 → 提醒管理）
        if (reminderPanelOpen) {
            ReminderPanel(viewModel = viewModel)
        }

        // 续播位置管理（全屏覆盖，工具 → 续播位置）
        if (resumePanelOpen) {
            ResumePanel(viewModel = viewModel)
        }

        // 书签管理（全屏覆盖，工具 → 书签）
        if (bookmarkPanelOpen) {
            BookmarkPanel(viewModel = viewModel)
        }

        // EPG 时间线视图（全屏覆盖，工具 → EPG 时间线）
        if (epgTimelineOpen) {
            EpgTimelinePanel(viewModel = viewModel)
        }

        // 全局搜索（全屏覆盖，工具 → 搜索）
        if (searchPanelOpen) {
            SearchPanel(viewModel = viewModel)
        }

        // 流质量检测（全屏覆盖，工具 → 流质量检测）
        if (streamQualityPanelOpen) {
            StreamQualityPanel(viewModel = viewModel)
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

        // -----------------------------------------------------------------
        // 5. OSD 浮层（顶部居中，最顶层）
        // -----------------------------------------------------------------
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

// -----------------------------------------------------------------
// 顶部信息条 + 面板入口按钮
// -----------------------------------------------------------------

@Composable
private fun TopBar(
    channelName: String,
    mode: String,
    paused: Boolean,
    onChannelsClick: () -> Unit,
    onEpgClick: () -> Unit,
    onMenuClick: () -> Unit
) {
    Surface(
        color = Color(0xCC000000),
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
                    color = Color.White,
                    fontWeight = FontWeight.Medium,
                    maxLines = 1
                )
                if (paused) {
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = "（已暂停）",
                        color = Color(0xFFFFA500),
                        fontSize = 12.sp
                    )
                }
            }

            // 右侧：面板入口按钮
            Row(verticalAlignment = Alignment.CenterVertically) {
                IconButton(onClick = onChannelsClick) {
                    Icon(
                        Icons.Default.VideoLibrary,
                        contentDescription = "频道列表",
                        tint = Color.White
                    )
                }
                IconButton(onClick = onEpgClick) {
                    Icon(
                        Icons.Default.CalendarMonth,
                        contentDescription = "EPG 节目单",
                        tint = Color.White
                    )
                }
                IconButton(onClick = onMenuClick) {
                    Icon(
                        Icons.Default.Menu,
                        contentDescription = "主菜单",
                        tint = Color.White
                    )
                }
                Spacer(modifier = Modifier.width(4.dp))
                Text(
                    text = mode,
                    style = MaterialTheme.typography.labelSmall,
                    color = Color(0xFF888888)
                )
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
        color = Color(0xE6000000),
        shape = RoundedCornerShape(8.dp),
        modifier = Modifier
            .padding(top = 56.dp)
            .padding(horizontal = 16.dp)
    ) {
        Column(
            modifier = Modifier
                .padding(horizontal = 16.dp, vertical = 10.dp)
        ) {
            Text(
                text = title,
                color = Color.White,
                fontSize = 14.sp,
                fontWeight = FontWeight.Medium
            )
            if (subtitle.isNotEmpty()) {
                Spacer(modifier = Modifier.height(2.dp))
                Text(
                    text = subtitle,
                    color = Color(0xFFCCCCCC),
                    fontSize = 12.sp
                )
            }
            if (extra.isNotEmpty()) {
                Spacer(modifier = Modifier.height(2.dp))
                Text(
                    text = extra,
                    color = Color(0xFF888888),
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
            color = Color(0xFF1F1F1F),
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
                    color = Color.White,
                    fontSize = 18.sp,
                    fontWeight = FontWeight.Medium
                )
                Spacer(modifier = Modifier.height(16.dp))

                // 节目信息卡片
                Surface(
                    color = Color(0xFF2A2A2A),
                    shape = RoundedCornerShape(8.dp),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Column(modifier = Modifier.padding(12.dp)) {
                        Text(
                            text = reminder.programTitle.ifBlank { "（未命名节目）" },
                            color = Color.White,
                            fontSize = 15.sp,
                            fontWeight = FontWeight.Medium,
                            maxLines = 2
                        )
                        if (reminder.channelName.isNotEmpty()) {
                            Spacer(modifier = Modifier.height(4.dp))
                            Text(
                                text = "频道: ${reminder.channelName}",
                                color = Color(0xFFAAAAAA),
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
                                color = Color(0xFFAAAAAA),
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
                        Text("稍后", color = Color(0xFFCCCCCC))
                    }
                    Button(
                        onClick = onAccept,
                        colors = ButtonDefaults.buttonColors(
                            containerColor = Color(0xFF4A9EFF)
                        ),
                        modifier = Modifier.weight(1f)
                    ) {
                        Text("切换频道", color = Color.White)
                    }
                }
            }
        }
    }
}
