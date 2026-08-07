package com.iptv.scanner.editor.pro.ui

import android.app.Activity
import android.content.Intent
import android.os.Bundle
import android.speech.RecognizerIntent
import android.view.WindowManager
import androidx.activity.ComponentActivity
import androidx.activity.compose.ManagedActivityResultLauncher
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.ActivityResult
import androidx.activity.result.contract.ActivityResultContracts
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
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
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
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import coil.compose.AsyncImage
import com.iptv.scanner.editor.pro.data.IptvChannel
import com.iptv.scanner.editor.pro.ui.theme.rememberPlayerOverlayColors
import com.iptv.scanner.editor.pro.ui.theme.tvFocusBorder
import kotlinx.coroutines.delay
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

// =================================================================
// 1. 竖屏全屏支持（手机竖屏视频/竖屏直播）
// =================================================================

/**
 * 竖屏全屏状态管理：在 AppViewModel 中添加以下属性：
 *
 * ```kotlin
 * // 竖屏全屏模式：true=竖屏视频填满屏幕（不强制旋转到横屏）
 * private val _portraitFullscreen = MutableStateFlow(false)
 * val portraitFullscreen: StateFlow<Boolean> = _portraitFullscreen.asStateFlow()
 *
 * fun togglePortraitFullscreen() {
 *     _portraitFullscreen.value = !_portraitFullscreen.value
 *     // 设置 Activity 屏幕方向为竖屏
 *     // 在 MainActivityCompose 中监听此状态
 * }
 *
 * fun setPortraitFullscreen(enabled: Boolean) {
 *     _portraitFullscreen.value = enabled
 * }
 * ```
 *
 * 在 MainPlayerScreen.kt 的竖屏布局中：
 * ```kotlin
 * val portraitFullscreen by viewModel.portraitFullscreen.collectAsState()
 *
 * if (portraitFullscreen) {
 *     // 竖屏全屏：视频填满整个屏幕，隐藏所有控制栏
 *     Box(modifier = Modifier.fillMaxSize().background(Color.Black)) {
 *         primaryPlayer()
 *         // 点击切换控制栏显示
 *         // 手势控制：左半屏亮度，右半屏音量，双击暂停
 *     }
 * } else {
 *     // 原有竖屏分屏布局
 * }
 * ```
 */

// =================================================================
// 2. TV 屏保功能（长时间无操作时显示时钟+台标轮播）
// =================================================================

/**
 * TV 屏保 Composable。
 *
 * 在 TvPlayerLayout 中调用。当控制层和侧边栏都隐藏超过 5 分钟时显示。
 *
 * 显示内容：
 * - 大号时钟（居中）
 * - 频道台标轮播（底部，每 10 秒切换一个台标）
 *
 * 用户按下任意键（方向键/确认键/菜单键）退出屏保。
 */
@Composable
fun TvScreensaver(
    viewModel: AppViewModel,
    modifier: Modifier = Modifier
) {
    val channels by viewModel.channels.collectAsState()
    val currentIdx by viewModel.currentIdx.collectAsState()
    val oc = rememberPlayerOverlayColors()

    // 台标轮播索引
    var logoIndex by remember { mutableStateOf(0) }
    var showScreensaver by remember { mutableStateOf(false) }
    var lastActivityTime by remember { mutableStateOf(System.currentTimeMillis()) }

    // 屏保触发定时器：5 分钟无操作
    LaunchedEffect(Unit) {
        while (true) {
            delay(1000)
            val idleTime = System.currentTimeMillis() - lastActivityTime
            if (idleTime > 300_000 && !showScreensaver) { // 5 分钟
                showScreensaver = true
                logoIndex = 0
            }
        }
    }

    // 台标轮播定时器：每 10 秒切换
    LaunchedEffect(showScreensaver) {
        while (showScreensaver && channels.isNotEmpty()) {
            delay(10_000)
            logoIndex = (logoIndex + 1) % channels.size.coerceAtLeast(1)
        }
    }

    // 任意触摸/按键重置计时器（由外部调用 resetScreensaverTimer）
    // 这里监听 controlsVisible 变化
    val controlsVisible by viewModel.controlsVisible.collectAsState()
    val sidebarVisible by viewModel.landscapeSidebarVisible.collectAsState()
    LaunchedEffect(controlsVisible, sidebarVisible) {
        lastActivityTime = System.currentTimeMillis()
        if (showScreensaver && (controlsVisible || sidebarVisible)) {
            showScreensaver = false
        }
    }

    AnimatedVisibility(
        visible = showScreensaver,
        enter = fadeIn(),
        exit = fadeOut(),
        modifier = modifier
    ) {
        Box(
            modifier = Modifier
                .fillMaxSize()
                .background(Color.Black.copy(alpha = 0.85f))
                .clickable {
                    showScreensaver = false
                    lastActivityTime = System.currentTimeMillis()
                    viewModel.setControlsVisible(true)
                }
        ) {
            // 大号时钟（居中）
            Column(
                modifier = Modifier
                    .align(Alignment.Center)
                    .padding(32.dp),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                val timeStr = remember {
                    object {
                        fun format(): String {
                            return SimpleDateFormat("HH:mm", Locale.getDefault()).format(Date())
                        }
                    }
                }
                // 每秒刷新时钟
                var clockTick by remember { mutableStateOf(0) }
                LaunchedEffect(Unit) {
                    while (true) {
                        clockTick++
                        delay(1000)
                    }
                }
                Text(
                    text = timeStr.format(),
                    color = Color.White,
                    fontSize = 72.sp,
                    fontWeight = FontWeight.Light
                )
                Spacer(modifier = Modifier.height(8.dp))
                val dateStr = SimpleDateFormat("yyyy年MM月dd日 EEEE", Locale.CHINESE).format(Date())
                Text(
                    text = dateStr,
                    color = Color.White.copy(alpha = 0.7f),
                    fontSize = 18.sp
                )
            }

            // 台标轮播（底部）
            if (channels.isNotEmpty()) {
                val ch = channels.getOrNull(logoIndex)
                if (ch != null && ch.logo.isNotEmpty()) {
                    AsyncImage(
                        model = ch.logo,
                        contentDescription = null,
                        modifier = Modifier
                            .align(Alignment.BottomCenter)
                            .padding(bottom = 48.dp)
                            .size(120.dp)
                            .clip(RoundedCornerShape(16.dp))
                    )
                    Text(
                        text = ch.name,
                        color = Color.White.copy(alpha = 0.6f),
                        fontSize = 14.sp,
                        modifier = Modifier
                            .align(Alignment.BottomCenter)
                            .padding(bottom = 20.dp)
                    )
                }
            }

            // 提示文字
            Text(
                text = "按任意键退出屏保",
                color = Color.White.copy(alpha = 0.3f),
                fontSize = 12.sp,
                modifier = Modifier
                    .align(Alignment.TopEnd)
                    .padding(16.dp)
            )
        }
    }
}

/**
 * 通知 ViewModel 重置屏保计时器（外部调用）。
 * 在 MainActivityCompose 的 onKeyDown 中调用。
 */
fun AppViewModel.resetScreensaverTimer() {
    // 触发 controlsVisible 变化即可重置（TvScreensaver 监听此变化）
    if (!controlsVisible.value) {
        setControlsVisible(true)
    }
}

// =================================================================
// 3. TV 语音搜索
// =================================================================

/**
 * TV 语音搜索 Composable。
 *
 * 使用 Android 系统 SpeechRecognizer 通过遥控器语音键触发。
 * 搜索结果在 SearchPanel 中显示。
 *
 * 使用方式：
 * ```kotlin
 * val voiceSearchLauncher = rememberLauncherForActivityResult(
 *     ActivityResultContracts.StartActivityForResult()
 * ) { result ->
 *     if (result.resultCode == Activity.RESULT_OK) {
 *         val text = result.data?.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)
 *             ?.firstOrNull()
 *         if (!text.isNullOrEmpty()) {
 *             viewModel.setSearchQuery(text)
 *             viewModel.performSearch()
 *         }
 *     }
 * }
 *
 * VoiceSearchButton(onClick = {
 *     val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
 *         putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
 *         putExtra(RecognizerIntent.EXTRA_LANGUAGE, "zh-CN")
 *         putExtra(RecognizerIntent.EXTRA_PROMPT, "说出频道名称...")
 *     }
 *     voiceSearchLauncher.launch(intent)
 * })
 * ```
 */
@Composable
fun VoiceSearchButton(
    onClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    val oc = rememberPlayerOverlayColors()
    IconButton(
        onClick = onClick,
        modifier = modifier.tvFocusBorder()
    ) {
        Icon(
            Icons.Default.Mic,
            contentDescription = "语音搜索",
            tint = oc.iconTint
        )
    }
}

// =================================================================
// 4. TV 频道预览条（底部横向频道缩略图/台标列表）
// =================================================================

/**
 * TV 频道预览条。
 *
 * 在 TvPlayerLayout 底部显示，横向滚动的频道列表。
 * 每个频道显示台标+名称，当前频道高亮。
 *
 * DPAD 左右键在预览条中切换频道焦点，CENTER 键播放选中频道。
 */
@Composable
fun TvChannelPreviewBar(
    viewModel: AppViewModel,
    modifier: Modifier = Modifier
) {
    val channels by viewModel.channels.collectAsState()
    val currentIdx by viewModel.currentIdx.collectAsState()
    val oc = rememberPlayerOverlayColors()
    val listState = rememberLazyListState()

    // 自动滚动到当前频道位置
    LaunchedEffect(currentIdx) {
        if (currentIdx >= 0 && currentIdx < channels.size) {
            listState.animateScrollToItem(
                index = (currentIdx - 2).coerceAtLeast(0)
            )
        }
    }

    Surface(
        color = oc.scrim,
        modifier = modifier.fillMaxWidth()
    ) {
        LazyRow(
            state = listState,
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 8.dp, vertical = 6.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            items(
                items = channels,
                key = { it.url }
            ) { channel ->
                val idx = channels.indexOf(channel)
                val isCurrent = idx == currentIdx
                TvChannelPreviewItem(
                    channel = channel,
                    isCurrent = isCurrent,
                    onClick = { viewModel.playChannel(idx) }
                )
            }
        }
    }
}

@Composable
private fun TvChannelPreviewItem(
    channel: IptvChannel,
    isCurrent: Boolean,
    onClick: () -> Unit
) {
    val oc = rememberPlayerOverlayColors()
    Column(
        modifier = Modifier
            .width(100.dp)
            .tvFocusBorder()
            .clip(RoundedCornerShape(8.dp))
            .background(
                if (isCurrent) oc.accent.copy(alpha = 0.2f) else Color.Transparent
            )
            .clickable(onClick = onClick)
            .padding(6.dp),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        // 台标
        if (channel.logo.isNotEmpty()) {
            AsyncImage(
                model = channel.logo,
                contentDescription = null,
                modifier = Modifier
                    .size(48.dp)
                    .clip(RoundedCornerShape(8.dp))
            )
        } else {
            // 无台标时显示占位圆
            Box(
                modifier = Modifier
                    .size(48.dp)
                    .clip(CircleShape)
                    .background(oc.trackInactive)
            )
        }
        Spacer(modifier = Modifier.height(4.dp))
        Text(
            text = channel.name,
            color = if (isCurrent) oc.accent else oc.textPrimary,
            fontSize = 11.sp,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
            fontWeight = if (isCurrent) FontWeight.Medium else FontWeight.Normal
        )
    }
}

// =================================================================
// 5. TV 焦点记忆
// =================================================================

/**
 * TV 焦点记忆管理器。
 *
 * 在 AppViewModel 中添加：
 * ```kotlin
 * /** 记住每个面板退出时的焦点位置 */
 * private val _savedFocusPositions = MutableStateFlow<Map<String, Int>>(emptyMap())
 * val savedFocusPositions: StateFlow<Map<String, Int>> = _savedFocusPositions.asStateFlow()
 *
 * fun saveFocusPosition(panelKey: String, position: Int) {
 *     _savedFocusPositions.value = _savedFocusPositions.value + (panelKey to position)
 * }
 *
 * fun getSavedFocusPosition(panelKey: String): Int {
 *     return _savedFocusPositions.value[panelKey] ?: 0
 * }
 *
 * fun clearFocusPosition(panelKey: String) {
 *     _savedFocusPositions.value = _savedFocusPositions.value - panelKey
 * }
 * ```
 *
 * 在 LazyColumn 的 LaunchedEffect 中恢复：
 * ```kotlin
 * val savedPos = viewModel.getSavedFocusPosition("channels")
 * LaunchedEffect(Unit) {
 *     listState.scrollToItem(savedPos)
 * }
 * ```
 *
 * 在面板关闭时保存：
 * ```kotlin
 * val firstVisible = listState.firstVisibleItemIndex
 * viewModel.saveFocusPosition("channels", firstVisible)
 * viewModel.toggleChannelsPanel()
 * ```
 */

// =================================================================
// 6. TV 自动播放（开机直接播放上次频道）
// =================================================================

/**
 * TV 自动播放功能。
 *
 * 在 UserPrefs 中已存在 isAutoResumeOnStart()，默认 true。
 * MainActivityCompose 已在 InitState.Ready 时调用 restoreLastChannel()。
 *
 * 增强项：增加"开机直接播放"设置项（跳过首页直接全屏播放）。
 *
 * 在 UserPrefs 中添加：
 * ```kotlin
 * // 开机直接播放（TV 端跳过首页直接全屏播放上次频道）
 * private const val KEY_DIRECT_PLAY_ON_BOOT = "direct_play_on_boot"
 * private const val DEFAULT_DIRECT_PLAY_ON_BOOT = false
 *
 * fun isDirectPlayOnBoot(): Boolean = prefs.getBoolean(KEY_DIRECT_PLAY_ON_BOOT, DEFAULT_DIRECT_PLAY_ON_BOOT)
 * fun setDirectPlayOnBoot(enabled: Boolean) {
 *     prefs.edit().putBoolean(KEY_DIRECT_PLAY_ON_BOOT, enabled).apply()
 * }
 * ```
 *
 * 在 MainActivityCompose 中：
 * ```kotlin
 * // 开机直接播放逻辑
 * if (userPrefs.isDirectPlayOnBoot() && uiMode.isTV) {
 *     viewModel.showPlayerScreen()  // 跳过首页直接全屏
 * }
 * ```
 */
