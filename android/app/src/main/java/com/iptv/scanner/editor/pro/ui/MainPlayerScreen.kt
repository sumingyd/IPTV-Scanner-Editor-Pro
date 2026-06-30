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
import androidx.compose.material.icons.filled.VideoLibrary
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import com.iptv.scanner.editor.pro.mpv.MPVView
import com.iptv.scanner.editor.pro.mpv.MpvController

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
    val osd by viewModel.osd.collectAsState()

    val mpv = MpvController.getInstance()
    val paused by mpv.paused.collectAsState()

    // 是否有任何面板打开（控制层在面板打开时自动隐藏）
    val anyPanelOpen = channelsPanelOpen || epgPanelOpen || menuPanelOpen
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
        // 1. 底层：MPVView
        // -----------------------------------------------------------------
        AndroidView(
            factory = { ctx ->
                Log.i("MainPlayerScreen", "Creating MPVView, uiMode=$uiMode")
                val mpvView = MPVView(ctx)
                val configDir = ctx.getDir("mpv_config", Context.MODE_PRIVATE).absolutePath
                val cacheDir = ctx.cacheDir.absolutePath
                try {
                    mpvView.initialize(configDir, cacheDir)
                    // 绑定 MpvController（注册 EventObserver，转发 mpv 事件到 StateFlow）
                    mpv.attach(mpvView)
                    Log.i("MainPlayerScreen", "MPVView initialized + MpvController attached")
                } catch (e: Throwable) {
                    Log.e("MainPlayerScreen", "MPVView initialize failed", e)
                }
                mpvView
            },
            update = { /* MPVView 的 surfaceChanged 等回调内部已处理 */ },
            modifier = Modifier.fillMaxSize()
        )

        // Activity 销毁时 detach MpvController
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
