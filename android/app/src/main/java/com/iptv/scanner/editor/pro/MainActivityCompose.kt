package com.iptv.scanner.editor.pro

import android.app.PictureInPictureParams
import android.os.Build
import android.os.Bundle
import android.util.Log
import android.view.KeyEvent
import android.view.WindowManager
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.viewModels
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.lifecycle.lifecycleScope
import com.iptv.scanner.editor.pro.mpv.MpvController
import com.iptv.scanner.editor.pro.ui.AppViewModel
import com.iptv.scanner.editor.pro.ui.MainPlayerScreen
import com.iptv.scanner.editor.pro.ui.SplashScreen
import com.iptv.scanner.editor.pro.ui.UiMode
import com.iptv.scanner.editor.pro.ui.theme.IptvTheme
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.filterIsInstance
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

/**
 * Compose 主入口 Activity。
 *
 * 替换原 [MainActivity]（Java + WebView 三层架构），改为：
 * - Jetpack Compose 原生 UI（无 WebView）
 * - Chaquopy 直调 Python（无 HTTP 服务）
 * - MPVView 作为 AndroidView 嵌入（保留 mpv 渲染）
 *
 * 生命周期：
 * - onCreate → 初始化 ViewModel → setContent（IptvTheme 包裹）
 *   - initState == Idle/Initializing/Failed → SplashScreen
 *   - initState == Ready → MainPlayerScreen
 * - onUserLeaveHint → 自动进入 PiP（如果正在播放）
 * - onDestroy → 当前播放器 stop+detach + MpvController 兜底 detach（移除 EventObserver）
 *
 * TV 模式 DPAD 按键处理（onKeyDown）：
 * - DPAD_UP/DOWN → 上一/下一频道
 * - DPAD_LEFT/RIGHT → 直播模式：切换面板（左=EPG，右=频道列表）
 *                     回看/时移/本地视频：seek ±10 秒
 * - DPAD_CENTER/ENTER → 短按打开统一面板，长按显示控制层
 * - MENU（KEYCODE_MENU=82）→ 关闭当前面板再开主菜单
 * - BACK → 关闭面板 → 退出回看/时移 → 退出
 * - STOP → 退出回看/时移（恢复直播）或停止播放
 *
 * 媒体键处理（TV 和 PHONE 模式通用，不受面板状态影响）：
 * - MEDIA_PLAY/PAUSE/PLAY_PAUSE → 播放控制
 * - MEDIA_NEXT/PREVIOUS → 切换频道
 * - MEDIA_STOP → 停止播放
 * - MEDIA_STEP_FORWARD/FAST_FORWARD → 快进 30 秒
 * - MEDIA_STEP_BACKWARD/REWIND → 快退 30 秒
 * - VOLUME_MUTE → 静音切换
 */
class MainActivityCompose : ComponentActivity() {

    companion object {
        private const val TAG = "MainActivityCompose"
    }

    /** OK 键长按标记：长按显示控制层，跳过短按逻辑（打开统一面板） */
    private var okKeyLongPressed = false

    @Suppress("DEPRECATION")
    private val viewModel: AppViewModel by viewModels {
        AppViewModel.factory(application)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // 启用 edge-to-edge（沉浸式布局）：让内容绘制到状态栏/导航栏后面。
        // Android 15 (targetSdk 35) 已强制此行为，旧版本需主动调用以保持一致。
        // 视频播放器全屏沉浸（延伸到状态栏后），控制层/面板通过 systemBarsPadding 避让系统栏。
        enableEdgeToEdge()
        Log.i(TAG, "onCreate")

        // 处理外部文件打开（intent-filter 文件关联）
        handleIntent(intent)

        // 注入 PiP 回调（ViewModel 不能直接调用 Activity 方法）
        viewModel.onEnterPip = { enterPipManual() }

        setContent {
            val themeMode by viewModel.themeMode.collectAsState()
            IptvTheme(themeMode = themeMode) {
                val initState by viewModel.initState.collectAsState()
                when (initState) {
                    is AppViewModel.InitState.Ready -> MainPlayerScreen(viewModel)
                    else -> SplashScreen(viewModel)
                }
            }
        }

        // 监听初始化完成，自动恢复上次播放的频道（如果有）
        lifecycleScope.launch {
            viewModel.initState
                .filterIsInstance<AppViewModel.InitState.Ready>()
                .distinctUntilChanged()
                .collect { state ->
                    Log.i(TAG, "Init Ready, channels=${state.status.channelsTotal}")
                    // 恢复上次播放的频道：等待 channels 加载完成（startInitialization 已触发 loadChannels）
                    if (state.status.channelsTotal > 0 && viewModel.currentIdx.value < 0) {
                        val startTime = System.currentTimeMillis()
                        // 最多等待 5 秒 channels 加载完成
                        while (isActive && viewModel.channels.value.isEmpty() &&
                            System.currentTimeMillis() - startTime < 5_000L
                        ) {
                            delay(200L)
                        }
                        if (viewModel.channels.value.isNotEmpty() && viewModel.currentIdx.value < 0) {
                            // 优先按 URL 恢复上次播放的频道，找不到则播放第一个
                            viewModel.restoreLastChannel()
                            Log.i(TAG, "Auto-restored last channel")
                        }
                    }
                }
        }

        // 保持屏幕常亮：视频加载后避免系统进入屏保/休眠（TV 端长时间播放必备）。
        // 根因：Android TV 系统默认在一段时间无操作后触发屏保（Daydream/Standby），
        // 视频播放类 APP 必须主动设置 FLAG_KEEP_SCREEN_ON 阻止系统熄屏。
        // fileLoaded=true（视频已加载，含播放/暂停状态）→ 屏幕常亮
        // fileLoaded=false（未加载/已停止）→ 清除 FLAG，允许系统正常休眠
        // 注：StateFlow 本身已去重（distinctUntilChanged 对 StateFlow 是 no-op）
        lifecycleScope.launch {
            viewModel.mpv.fileLoaded
                .collect { loaded ->
                    if (loaded) {
                        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
                        Log.i(TAG, "Keep screen on: video loaded")
                    } else {
                        window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
                        Log.i(TAG, "Allow screen sleep: no video loaded")
                    }
                }
        }
    }

    /**
     * TV 模式 DPAD 按键处理。
     *
     * 与 PC 端键盘快捷键对齐：
     * - 方向键：DPAD_UP/DOWN 切换频道，DPAD_LEFT/RIGHT 切换面板
     * - 确认键：短按打开统一面板，长按显示控制层
     * - MENU 键：主菜单
     * - BACK：关闭面板 / 退出
     *
     * PHONE 模式下也处理部分按键（BACK、MENU），方便外接键盘测试。
     */
    override fun onKeyDown(keyCode: Int, event: KeyEvent?): Boolean {
        // 初始化未完成时，按键交给系统处理
        val initState = viewModel.initState.value
        if (initState !is AppViewModel.InitState.Ready) {
            return super.onKeyDown(keyCode, event)
        }

        // 数字选台（与酷9 CHANNEL_NUMBER 对齐）：
        // 用户按数字键 0-9 时，累积输入并显示在 OSD 上。
        // 2秒内无新输入或按确认键(DPAD_CENTER/ENTER)时，切到对应频道。
        val digit = when (keyCode) {
            KeyEvent.KEYCODE_0 -> 0
            KeyEvent.KEYCODE_1 -> 1
            KeyEvent.KEYCODE_2 -> 2
            KeyEvent.KEYCODE_3 -> 3
            KeyEvent.KEYCODE_4 -> 4
            KeyEvent.KEYCODE_5 -> 5
            KeyEvent.KEYCODE_6 -> 6
            KeyEvent.KEYCODE_7 -> 7
            KeyEvent.KEYCODE_8 -> 8
            KeyEvent.KEYCODE_9 -> 9
            else -> -1
        }
        if (digit >= 0) {
            viewModel.inputChannelNumber(digit)
            return true
        }
        // 确认键：立即执行数字选台
        if (keyCode == KeyEvent.KEYCODE_DPAD_CENTER || keyCode == KeyEvent.KEYCODE_ENTER) {
            if (viewModel.commitChannelNumber()) {
                return true
            }
        }

        // BACK 键：先关闭面板 → 再退出多画面 → 再退出回看/时移 → 播放器模式返回首页 → 最后显示退出确认对话框
        if (keyCode == KeyEvent.KEYCODE_BACK) {
            if (viewModel.closeAnyPanel()) {
                return true
            }
            // 多画面激活时，BACK 退出多画面（释放副画面 Player）
            if (viewModel.multiViewState.value.active) {
                viewModel.exitMultiView()
                return true
            }
            // 在回看/时移模式下，BACK 退出回看/时移，恢复直播
            if (viewModel.playbackState.value.mode.isCatchupOrTimeshift) {
                viewModel.exitCatchup()
                return true
            }
            // 竖屏播放器模式（非首页），BACK 返回首页（视频继续播放）
            if (!viewModel.showHome.value) {
                viewModel.showHomeScreen()
                return true
            }
            // 首页模式下，显示退出确认对话框（立即退出 / 进入 PiP）
            viewModel.showExitConfirm()
            return true
        }

        // MENU 键：TV 模式打开统一面板，PHONE 模式打开主菜单
        if (keyCode == KeyEvent.KEYCODE_MENU) {
            val isTv = viewModel.uiMode.value == UiMode.TV
            when {
                isTv -> {
                    viewModel.setLandscapeSidebarVisible(!viewModel.landscapeSidebarVisible.value)
                }
                viewModel.menuPanelOpen.value -> {
                    viewModel.closeAllPanels()
                }
                viewModel.anyPanelOpen -> {
                    viewModel.closeAllPanels()
                    viewModel.toggleMenuPanel()
                }
                else -> {
                    viewModel.toggleMenuPanel()
                }
            }
            return true
        }

        // 媒体键处理（TV 和 PHONE 模式都工作，不受面板状态影响）
        // 与 PC 端 onRemoteKey 对齐
        when (keyCode) {
            KeyEvent.KEYCODE_MEDIA_PLAY -> {
                viewModel.mpv.setPause(false)
                return true
            }
            KeyEvent.KEYCODE_MEDIA_PAUSE -> {
                viewModel.mpv.setPause(true)
                return true
            }
            KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE -> {
                viewModel.mpv.togglePause()
                return true
            }
            KeyEvent.KEYCODE_MEDIA_NEXT -> {
                viewModel.nextChannel()
                return true
            }
            KeyEvent.KEYCODE_MEDIA_PREVIOUS -> {
                viewModel.prevChannel()
                return true
            }
            KeyEvent.KEYCODE_MEDIA_STOP -> {
                // 回看/时移模式下退出回看恢复直播，其他模式停止播放
                if (viewModel.playbackState.value.mode.isCatchupOrTimeshift) {
                    viewModel.exitCatchup()
                } else {
                    viewModel.stopPlay()
                }
                return true
            }
            KeyEvent.KEYCODE_MEDIA_STEP_FORWARD, KeyEvent.KEYCODE_MEDIA_FAST_FORWARD -> {
                viewModel.mpv.seekRelative(30.0)
                return true
            }
            KeyEvent.KEYCODE_MEDIA_STEP_BACKWARD, KeyEvent.KEYCODE_MEDIA_REWIND -> {
                viewModel.mpv.seekRelative(-30.0)
                return true
            }
            KeyEvent.KEYCODE_VOLUME_MUTE -> {
                viewModel.mpv.toggleMute()
                return true
            }
        }

        // 仅在 TV 模式下处理 DPAD 方向键
        val isTv = viewModel.uiMode.value == UiMode.TV
        if (!isTv) {
            // PHONE 模式下也处理一些快捷键（方便外接键盘测试）
            when (keyCode) {
                KeyEvent.KEYCODE_SPACE -> {
                    viewModel.mpv.togglePause()
                    return true
                }
                KeyEvent.KEYCODE_M -> {
                    viewModel.mpv.toggleMute()
                    return true
                }
                // 音量键交给系统处理（PHONE 模式不拦截，显示系统音量条）
            }
            return super.onKeyDown(keyCode, event)
        }

        // TV 模式 DPAD 处理
        // 面板打开时，方向键和确认键交给 Compose 焦点系统在面板内导航，
        // 不再全局拦截为切频道/切面板（与 PC 端面板内键盘导航一致）。
        // 字母键（SPACE/M）和音量键仍由这里处理播放控制。
        val isDpadNavigation = keyCode == KeyEvent.KEYCODE_DPAD_UP ||
                keyCode == KeyEvent.KEYCODE_DPAD_DOWN ||
                keyCode == KeyEvent.KEYCODE_DPAD_LEFT ||
                keyCode == KeyEvent.KEYCODE_DPAD_RIGHT ||
                keyCode == KeyEvent.KEYCODE_DPAD_CENTER ||
                keyCode == KeyEvent.KEYCODE_ENTER
        if (viewModel.anyPanelOpen && isDpadNavigation) {
            // 交给 Compose 焦点系统处理（在面板内导航/确认）
            return super.onKeyDown(keyCode, event)
        }

        // 多画面模式：方向键全部用于切换焦点视口（无面板打开时）。
        // 多画面激活时方向键不再切频道/seek，避免误切主画面频道；
        // 用户切主画面频道需通过统一面板的频道列表（点击频道调用 playChannel）。
        // moveMultiViewFocus 返回 false（如 DUAL 模式上下键）时也拦截，避免触发切频道。
        if (viewModel.multiViewState.value.active) {
            val direction = when (keyCode) {
                KeyEvent.KEYCODE_DPAD_LEFT -> 0
                KeyEvent.KEYCODE_DPAD_UP -> 1
                KeyEvent.KEYCODE_DPAD_RIGHT -> 2
                KeyEvent.KEYCODE_DPAD_DOWN -> 3
                else -> -1
            }
            if (direction >= 0) {
                viewModel.moveMultiViewFocus(direction)
                return true
            }
        }

        when (keyCode) {
            KeyEvent.KEYCODE_DPAD_UP -> {
                viewModel.prevChannel()
                return true
            }
            KeyEvent.KEYCODE_DPAD_DOWN -> {
                viewModel.nextChannel()
                return true
            }
            KeyEvent.KEYCODE_DPAD_LEFT -> {
                // 左键：快退
                // - 回看/本地视频：直接 seek
                // - 直播/时移：在缓冲区内快退，自动进入时移模式
                val mode = viewModel.playbackState.value.mode
                if (mode.isCatchup || viewModel.currentChannel.value == null) {
                    viewModel.mpv.seekRelative(-10.0)
                } else {
                    viewModel.seekLiveRelative(-10.0)
                }
                return true
            }
            KeyEvent.KEYCODE_DPAD_RIGHT -> {
                // 右键：快进
                // - 回看/本地视频：直接 seek
                // - 直播/时移：时移下快进，追赶到前沿自动切回直播；直播前沿提示
                val mode = viewModel.playbackState.value.mode
                if (mode.isCatchup || viewModel.currentChannel.value == null) {
                    viewModel.mpv.seekRelative(10.0)
                } else {
                    viewModel.seekLiveRelative(10.0)
                }
                return true
            }
            KeyEvent.KEYCODE_DPAD_CENTER, KeyEvent.KEYCODE_ENTER -> {
                // 多画面模式：OK 键打开统一面板，让用户在频道列表中选择频道添加到焦点视口。
                // （多画面模式下添加副画面的唯一入口；控制层可通过 MENU 键或其他方式显示）
                if (viewModel.multiViewState.value.active) {
                    viewModel.toggleTvUnifiedPanel()
                    return true
                }
                // OK 键：短按打开统一面板，长按显示控制层。
                // startTracking() 启动长按检测，onKeyLongPress 在长按超时（~500ms）后触发，
                // onKeyUp 在松开时触发：长按已处理则跳过，否则短按打开统一面板。
                //
                // 重要：长按期间系统会重复发送 ACTION_DOWN（key repeat，repeatCount > 0），
                // 不能在重复事件中重置 okKeyLongPressed，否则会覆盖 onKeyLongPress 设置的 true，
                // 导致松手时 onKeyUp 误判为短按，触发统一面板。
                if (event != null && event.repeatCount == 0) {
                    okKeyLongPressed = false
                    event.startTracking()
                }
                return true
            }
            KeyEvent.KEYCODE_SPACE -> {
                viewModel.mpv.togglePause()
                return true
            }
            KeyEvent.KEYCODE_M -> {
                viewModel.mpv.toggleMute()
                return true
            }
            KeyEvent.KEYCODE_VOLUME_UP -> {
                viewModel.mpv.adjustVolume(5)
                return true
            }
            KeyEvent.KEYCODE_VOLUME_DOWN -> {
                viewModel.mpv.adjustVolume(-5)
                return true
            }
        }

        return super.onKeyDown(keyCode, event)
    }

    /**
     * 长按 OK 键（DPAD_CENTER/ENTER）显示控制层。
     *
     * 与 onKeyDown + onKeyUp 配合实现：
     * - onKeyDown: startTracking() 启动长按检测
     * - onKeyLongPress: 长按超时触发，显示控制层并标记
     * - onKeyUp: 松开时，长按已处理则跳过，否则短按打开统一面板
     *
     * 设计原因：短按打开统一面板后焦点会落到频道列表，
     * 若用长按打开统一面板，松开时的 KEYUP 会被 Compose 焦点系统消费，
     * 直接选中频道导致面板关闭。改为短按打开面板（无后续按键事件，
     * 不会误选），长按显示控制层（控制层不抢焦点）。
     */
    override fun onKeyLongPress(keyCode: Int, event: KeyEvent?): Boolean {
        if (keyCode == KeyEvent.KEYCODE_DPAD_CENTER || keyCode == KeyEvent.KEYCODE_ENTER) {
            okKeyLongPressed = true
            // TV 模式：长按显示控制层（auto-hide）
            if (viewModel.uiMode.value == UiMode.TV && !viewModel.anyPanelOpen) {
                viewModel.showControlsAutoHide()
                Log.i(TAG, "Long press OK: show controls")
                return true
            }
        }
        return super.onKeyLongPress(keyCode, event)
    }

    /**
     * OK 键松开：长按已处理（显示控制层）则跳过，否则短按打开统一面板。
     */
    override fun onKeyUp(keyCode: Int, event: KeyEvent?): Boolean {
        if (keyCode == KeyEvent.KEYCODE_DPAD_CENTER || keyCode == KeyEvent.KEYCODE_ENTER) {
            // 长按已处理（显示控制层），跳过短按逻辑
            if (okKeyLongPressed) {
                okKeyLongPressed = false
                return true
            }
            // 面板打开时交给 Compose 焦点系统处理（确认操作）
            if (viewModel.anyPanelOpen) {
                return super.onKeyUp(keyCode, event)
            }
            // 短按 OK 键：打开侧边栏（替代统一面板，适配无菜单键遥控器）
            viewModel.setLandscapeSidebarVisible(!viewModel.landscapeSidebarVisible.value)
            Log.i(TAG, "Short press OK: toggle sidebar")
            return true
        }
        return super.onKeyUp(keyCode, event)
    }

    /**
     * 用户按 HOME 键离开应用时自动进入 PiP（如果正在播放且支持 PiP）。
     *
     * PiP 增强（与 Android 最佳实践对齐）：
     * - setAspectRatio：按视频实际宽高比设置 PiP 窗口，消除黑边
     * - setSourceBoundsHint：从视频区域平滑动画过渡到 PiP 窗口
     * - Android 12+：setAutoEnterEnabled + setSeamlessResizeEnabled
     */
    /**
     * 手动进入 PiP 模式（主菜单/控制层按钮触发）。
     * 与 onUserLeaveHint 自动进入不同，这是用户主动请求 PiP。
     */
    fun enterPipManual() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
            && packageManager.hasSystemFeature("android.software.picture_in_picture")
        ) {
            try {
                val builder = PictureInPictureParams.Builder()
                val mpv = MpvController.getInstance()
                mpv.getVideoAspectRatio()?.let { ratio -> builder.setAspectRatio(ratio) }
                mpv.getVideoBoundsOnScreen()?.let { rect -> builder.setSourceRectHint(rect) }
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                    builder.setAutoEnterEnabled(true)
                    builder.setSeamlessResizeEnabled(true)
                }
                enterPictureInPictureMode(builder.build())
                Log.i(TAG, "Manual PiP entered")
            } catch (e: Exception) {
                Log.w(TAG, "Manual PiP failed: ${e.message}")
                viewModel.showOsd("画中画", "不支持或失败")
            }
        } else {
            viewModel.showOsd("画中画", "设备不支持")
        }
    }

    /**
     * 处理外部文件打开 Intent（文件关联）。
     * 支持 VIEW intent 打开 M3U/M3U8 播放列表和视频文件。
     */
    private fun handleIntent(intent: android.content.Intent?) {
        if (intent == null || intent.action != android.content.Intent.ACTION_VIEW) return
        val uri = intent.data ?: return
        val mimeType = intent.type ?: ""
        Log.i(TAG, "handleIntent: uri=$uri, mime=$mimeType")
        // 判断是播放列表还是视频文件
        val isPlaylist = mimeType.contains("mpegurl") ||
                uri.toString().lowercase().endsWith(".m3u") ||
                uri.toString().lowercase().endsWith(".m3u8")
        if (isPlaylist) {
            viewModel.openPlaylistFromUri(uri.toString(), uri.lastPathSegment ?: "播放列表")
        } else {
            viewModel.playLocalVideo(uri.toString())
        }
        // 清除 action 避免旋转屏幕时重复触发
        intent.action = null
    }

    override fun onNewIntent(intent: android.content.Intent) {
        super.onNewIntent(intent)
        handleIntent(intent)
    }

    override fun onUserLeaveHint() {
        super.onUserLeaveHint()
        val mpv = MpvController.getInstance()
        // 仅在播放中（fileLoaded 且 !paused）才自动进入 PiP
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
            && packageManager.hasSystemFeature("android.software.picture_in_picture")
            && mpv.fileLoaded.value && !mpv.paused.value
        ) {
            try {
                val builder = PictureInPictureParams.Builder()
                // 1. 设置视频宽高比（消除 PiP 窗口黑边）
                mpv.getVideoAspectRatio()?.let { ratio ->
                    builder.setAspectRatio(ratio)
                    Log.i(TAG, "PiP aspect ratio: $ratio")
                }
                // 2. 设置源矩形（动画从视频区域平滑过渡到 PiP 窗口）
                mpv.getVideoBoundsOnScreen()?.let { rect ->
                    builder.setSourceRectHint(rect)
                    Log.i(TAG, "PiP source bounds: $rect")
                }
                // 3. Android 12+：自动进入 PiP + 无缝调整大小
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                    builder.setAutoEnterEnabled(true)
                    builder.setSeamlessResizeEnabled(true)
                }
                enterPictureInPictureMode(builder.build())
                Log.i(TAG, "Auto-entered PiP on user leave")
            } catch (e: Exception) {
                Log.w(TAG, "Auto PiP failed: ${e.message}")
            }
        }
    }

    /**
     * PiP 模式变化回调：进入 PiP 时关闭所有面板并隐藏控制层（小窗口只显示视频），
     * 退出 PiP 时恢复控制层显示。
     */
    override fun onPictureInPictureModeChanged(isInPictureInPictureMode: Boolean) {
        super.onPictureInPictureModeChanged(isInPictureInPictureMode)
        if (isInPictureInPictureMode) {
            viewModel.closeAllPanels()
            viewModel.hideControls()
            // 进入 PiP 时保持播放器不动，不要重载
            Log.i(TAG, "Entered PiP: panels closed, controls hidden")
        } else {
            // 退出 PiP 时不要重载视频，只是恢复控制层
            viewModel.showControls()
            Log.i(TAG, "Exited PiP: controls shown")
        }
    }

    override fun onStop() {
        super.onStop()
        // 如果在 PiP 模式中被 stop，不要停止播放
        if (!isInPictureInPictureMode) {
            // 非画中画模式下离开应用时可以选择暂停（但保持视频状态）
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        // 停止并释放当前活跃播放器（MPV）
        // 注意：MPVView.destroy()（销毁 mpv 原生实例）由 AndroidView 的 onRelease 处理
        // 这里 stop + detach 当前播放器，避免 native 资源（解码器/缓冲队列/observer）泄漏
        try {
            val player = viewModel.mpv
            player.stop()
            player.detach()
        } catch (e: Throwable) {
            Log.w(TAG, "Player cleanup failed: ${e.message}")
        }
        // 兜底：确保 MpvController 的 EventObserver 被移除（即使当前播放器不是 MPV）
        try {
            val mpv = MpvController.getInstance()
            mpv.detach()
        } catch (e: Throwable) {
            Log.w(TAG, "MpvController cleanup failed: ${e.message}")
        }
        // 标记正常退出（NativeCrashLogger 据此判断下次启动是否需要保存崩溃日志）
        try {
            NativeCrashLogger.markCleanExit(application)
        } catch (e: Throwable) {
            Log.w(TAG, "NativeCrashLogger markCleanExit failed: ${e.message}")
        }
        Log.i(TAG, "onDestroy")
    }
}
