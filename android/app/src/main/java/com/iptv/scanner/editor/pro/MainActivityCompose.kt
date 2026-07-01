package com.iptv.scanner.editor.pro

import android.app.PictureInPictureParams
import android.os.Build
import android.os.Bundle
import android.util.Log
import android.view.KeyEvent
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
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
 * - onDestroy → MpvController.detach（移除 EventObserver）
 *
 * TV 模式 DPAD 按键处理（onKeyDown）：
 * - DPAD_UP/DOWN → 上一/下一频道
 * - DPAD_LEFT → 切换频道列表面板
 * - DPAD_RIGHT → 切换 EPG 面板
 * - DPAD_CENTER/ENTER → 播放/暂停 或 确认
 * - MENU（KEYCODE_MENU=82）→ 切换主菜单
 * - BACK → 关闭面板 / 退出
 */
class MainActivityCompose : ComponentActivity() {

    companion object {
        private const val TAG = "MainActivityCompose"
    }

    @Suppress("DEPRECATION")
    private val viewModel: AppViewModel by viewModels {
        AppViewModel.factory(application)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        Log.i(TAG, "onCreate")

        setContent {
            IptvTheme {
                val initState by viewModel.initState.collectAsState()
                when (initState) {
                    is AppViewModel.InitState.Ready -> MainPlayerScreen(viewModel)
                    else -> SplashScreen(viewModel)
                }
            }
        }

        // 监听初始化完成，自动加载第一个频道（如果有）
        lifecycleScope.launch {
            viewModel.initState
                .filterIsInstance<AppViewModel.InitState.Ready>()
                .distinctUntilChanged()
                .collect { state ->
                    Log.i(TAG, "Init Ready, channels=${state.status.channelsTotal}")
                    // 自动播放第一个频道：等待 channels 加载完成（startInitialization 已触发 loadChannels）
                    if (state.status.channelsTotal > 0 && viewModel.currentIdx.value < 0) {
                        val startTime = System.currentTimeMillis()
                        // 最多等待 5 秒 channels 加载完成
                        while (isActive && viewModel.channels.value.isEmpty() &&
                            System.currentTimeMillis() - startTime < 5_000L
                        ) {
                            delay(200L)
                        }
                        if (viewModel.channels.value.isNotEmpty() && viewModel.currentIdx.value < 0) {
                            viewModel.playChannel(0, silent = true)
                            Log.i(TAG, "Auto-played first channel")
                        }
                    }
                }
        }
    }

    /**
     * TV 模式 DPAD 按键处理。
     *
     * 与 PC 端 mobile/index.html 键盘快捷键对齐：
     * - 方向键：DPAD_UP/DOWN 切换频道，DPAD_LEFT/RIGHT 切换面板
     * - 确认键：播放/暂停
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

        // BACK 键：先关闭面板，再交给系统
        if (keyCode == KeyEvent.KEYCODE_BACK) {
            if (viewModel.closeAnyPanel()) {
                return true
            }
            // 无面板打开时，交给系统处理（不退出应用，让用户确认）
            return super.onKeyDown(keyCode, event)
        }

        // MENU 键：切换主菜单
        if (keyCode == KeyEvent.KEYCODE_MENU) {
            viewModel.toggleMenuPanel()
            return true
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

        // TV 模式 DPAD 处理
        // 面板打开时，方向键和确认键交给 Compose 焦点系统在面板内导航，
        // 不再全局拦截为切频道/切面板（与 PC 端 mobile/index.html 面板内键盘导航一致）。
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
                viewModel.toggleChannelsPanel()
                return true
            }
            KeyEvent.KEYCODE_DPAD_RIGHT -> {
                viewModel.toggleEpgPanel()
                return true
            }
            KeyEvent.KEYCODE_DPAD_CENTER, KeyEvent.KEYCODE_ENTER -> {
                viewModel.mpv.togglePause()
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
     * 用户按 HOME 键离开应用时自动进入 PiP（如果正在播放且支持 PiP）。
     *
     * PiP 增强（与 Android 最佳实践对齐）：
     * - setAspectRatio：按视频实际宽高比设置 PiP 窗口，消除黑边
     * - setSourceBoundsHint：从视频区域平滑动画过渡到 PiP 窗口
     * - Android 12+：setAutoEnterEnabled + setSeamlessResizeEnabled
     */
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
            Log.i(TAG, "Entered PiP: panels closed, controls hidden")
        } else {
            viewModel.showControls()
            Log.i(TAG, "Exited PiP: controls shown")
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        // 解绑 MpvController，移除 EventObserver
        // 注意：MPVView.destroy() 由 AndroidView 的 DisposableEffect 处理
        // 这里只 detach MpvController，避免泄漏
        try {
            MpvController.getInstance().detach()
        } catch (e: Throwable) {
            Log.w(TAG, "MpvController.detach failed: ${e.message}")
        }
        Log.i(TAG, "onDestroy")
    }
}
