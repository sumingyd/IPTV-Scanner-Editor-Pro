package com.iptv.scanner.editor.pro

import android.os.Bundle
import android.util.Log
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import com.chaquo.python.Python
import com.iptv.scanner.editor.pro.mpv.MPVView
import `is`.xyz.mpv.MPVLib
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * 阶段 0 技术验证 Activity（独立于 MainActivity，不影响现有 WebView 流程）。
 *
 * 验证三件事：
 * 1. Compose 用 AndroidView 包装 MPVView 能正常渲染画面（同时排查 64 位手机无画面根因）
 * 2. Chaquopy 直调 ServerContext 能拿到频道数据（不经 HTTP）
 * 3. MPVLib JNI 调用是否成功（create / setOptionString / command / getPropertyString）
 *
 * 通过 adb 启动（默认 vo=gpu，与 PC 端一致）：
 *   adb shell am start -n com.iptv.scanner.editor.pro/.ComposeSpikeActivity
 *
 * 测试 vo=mediacodec_embed（设备 GPU 兼容性问题时的 fallback）：
 *   adb shell am start -n com.iptv.scanner.editor.pro/.ComposeSpikeActivity --es vo mediacodec_embed
 *
 * 采集 logcat：
 *   adb logcat -s IPTVSpike:* mpv:* IPTVMainActivity:* python:*
 */
class ComposeSpikeActivity : ComponentActivity() {

    companion object {
        const val TAG = "IPTVSpike"
        // 一个公开的低延迟 HLS 测试流，用于验证 MPVView 渲染
        const val TEST_URL = "http://192.168.50.1:20231/rtp/239.21.1.120:5002?fcc=150.138.8.132:8027"
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        Log.i(TAG, "ComposeSpikeActivity onCreate")

        // 从 Intent extra 读取 vo/hwdec，支持通过 adb 命令切换渲染后端用于测试不同设备。
        // 不在代码里硬编码任何特定 vo——默认与 PC 端一致（vo=gpu）。
        // MPVLib 是单例，不能在运行时 destroy/create，所以 vo 只能在 Activity 启动时决定。
        val voMode = intent.getStringExtra("vo") ?: MPVView.DEFAULT_VO
        val hwdecMode = when (voMode) {
            "mediacodec_embed" -> "mediacodec"
            else -> MPVView.DEFAULT_HWDEC
        }
        Log.i(TAG, "vo=$voMode, hwdec=$hwdecMode")

        // window background 在 SurfaceView 之下，不会遮挡视频画面
        // Compose 的 Surface/Column/Box 的不透明 background 会遮挡 SurfaceView（默认 Z-order 在普通 View 后面）
        window.decorView.setBackgroundColor(android.graphics.Color.BLACK)
        setContent {
            MaterialTheme {
                // 不用 Surface 包裹——Surface 的 color 会画不透明背景层，遮挡 SurfaceView
                SpikeScreen(voMode = voMode, hwdecMode = hwdecMode)
            }
        }
    }
}

@Composable
private fun SpikeScreen(voMode: String, hwdecMode: String) {
    val scope = rememberCoroutineScope()
    val mpvViewHolder = remember { mutableStateOf<MPVView?>(null) }

    var initStatus by remember { mutableStateOf("未初始化") }
    var statusJson by remember { mutableStateOf("") }
    var channelsJson by remember { mutableStateOf("") }
    var playLog by remember { mutableStateOf("") }
    var surfaceStatus by remember { mutableStateOf("未知") }
    var testUrl by remember { mutableStateOf(ComposeSpikeActivity.TEST_URL) }

    // 关键修复：MPVView 不放在 verticalScroll 里，否则 SurfaceView 的 surface 不会创建
    // 关键修复 2：不能设置不透明 background！SurfaceView 默认 Z-order 在普通 View 后面，
    // Column 的 background(Color.Black) 会画在 SurfaceView 前面，遮挡视频画面。
    // 黑色背景由 Activity window background 提供（在 SurfaceView 之下，不会遮挡）。
    Column(
        modifier = Modifier
            .fillMaxSize()
    ) {
        // ---- 固定区域：MPVView（不可滚动，确保 surface 正常创建）----
        Text(
            "IPTV Spike（阶段 0 验证）vo=$voMode",
            color = Color.White,
            style = MaterialTheme.typography.titleLarge,
            modifier = Modifier.padding(12.dp)
        )

        Box(
            modifier = Modifier
                .fillMaxWidth()
                .height(200.dp)
                // 关键：不能设置不透明 background！
                // SurfaceView 默认 Z-order 在普通 View 后面，不透明 background 会遮挡视频画面
        ) {
            AndroidView(
                factory = { ctx ->
                    Log.i(ComposeSpikeActivity.TAG, "AndroidView.factory: 创建 MPVView vo=$voMode hwdec=$hwdecMode")
                    val mpv = MPVView(ctx)
                    val configDir = ctx.getDir("mpv_config", android.content.Context.MODE_PRIVATE).absolutePath
                    val cacheDir = ctx.cacheDir.absolutePath
                    try {
                        mpv.initialize(configDir, cacheDir, vo = voMode, hwdec = hwdecMode)
                        Log.i(ComposeSpikeActivity.TAG, "MPVView.initialize OK vo=$voMode, isSurfaceValid=${mpv.isSurfaceValid}")
                    } catch (e: Throwable) {
                        Log.e(ComposeSpikeActivity.TAG, "MPVView.initialize FAILED", e)
                    }
                    mpvViewHolder.value = mpv
                    mpv
                },
                update = { mpv ->
                    val valid = mpv.isSurfaceValid
                    surfaceStatus = if (valid) "surface 有效" else "surface 无效"
                },
                modifier = Modifier
                    .fillMaxSize()
            )
        }

        Text("surface: $surfaceStatus", color = Color.Yellow, modifier = Modifier.padding(4.dp))

        // ---- 可滚动区域：控制按钮和日志 ----
        Column(
            modifier = Modifier
                .weight(1f)
                .verticalScroll(rememberScrollState())
                .padding(12.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            OutlinedTextField(
                value = testUrl,
                onValueChange = { testUrl = it },
                label = { Text("测试 URL", color = Color.White) },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true
            )

            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = {
                    val mpv = mpvViewHolder.value
                    if (mpv == null) {
                        playLog = "MPVView 未创建"
                        return@Button
                    }
                    val valid = mpv.isSurfaceValid
                    playLog = "playFile($testUrl), surfaceValid=$valid"
                    Log.i(ComposeSpikeActivity.TAG, "playFile: $testUrl, surfaceValid=$valid")
                    try {
                        mpv.playFile(testUrl)
                    } catch (e: Throwable) {
                        Log.e(ComposeSpikeActivity.TAG, "playFile FAILED", e)
                        playLog = "playFile 异常: ${e.message}"
                    }
                }) { Text("播放测试") }

                Button(onClick = {
                    val mpv = mpvViewHolder.value
                    if (mpv == null) return@Button
                    try {
                        val timePos = MPVLib.getPropertyDouble("time-pos")
                        val duration = MPVLib.getPropertyDouble("duration")
                        val paused = MPVLib.getPropertyBoolean("pause")
                        val mediaTitle = MPVLib.getPropertyString("media-title")
                        val vo = MPVLib.getPropertyString("vo")
                        val hwdec = MPVLib.getPropertyString("hwdec-current")
                        playLog = buildString {
                            appendLine("time-pos=$timePos")
                            appendLine("duration=$duration")
                            appendLine("pause=$paused")
                            appendLine("vo=$vo")
                            appendLine("hwdec-current=$hwdec")
                            appendLine("media-title=$mediaTitle")
                        }
                        Log.i(ComposeSpikeActivity.TAG, "getProperty: $playLog")
                    } catch (e: Throwable) {
                        Log.e(ComposeSpikeActivity.TAG, "getProperty FAILED", e)
                        playLog = "getProperty 异常: ${e.message}"
                    }
                }) { Text("查询状态") }

                Button(onClick = {
                    val mpv = mpvViewHolder.value
                    if (mpv == null) return@Button
                    try {
                        mpv.stop()
                        playLog = "stop 已调用"
                    } catch (e: Throwable) {
                        playLog = "stop 异常: ${e.message}"
                    }
                }) { Text("停止") }
            }

            Text(playLog, color = Color.Cyan, modifier = Modifier.fillMaxWidth())

            // ---- Chaquopy 直调测试 ----
            Text("【2】Chaquopy 直调 ServerContext（不经 HTTP）", color = Color.Yellow)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = {
                    scope.launch {
                        val result = withContext(Dispatchers.IO) {
                            try {
                                Python.getInstance()
                                    .getModule("android_bridge")
                                    .callAttr("spike_init")
                                    .toString()
                            } catch (e: Throwable) {
                                Log.e(ComposeSpikeActivity.TAG, "spike_init FAILED", e)
                                "EXC: ${e.message}"
                            }
                        }
                        initStatus = result
                    }
                }) { Text("spike_init") }

                Button(onClick = {
                    scope.launch {
                        val result = withContext(Dispatchers.IO) {
                            try {
                                Python.getInstance()
                                    .getModule("android_bridge")
                                    .callAttr("spike_get_status_json")
                                    .toString()
                            } catch (e: Throwable) {
                                "EXC: ${e.message}"
                            }
                        }
                        statusJson = result
                    }
                }) { Text("status") }

                Button(onClick = {
                    scope.launch {
                        val result = withContext(Dispatchers.IO) {
                            try {
                                Python.getInstance()
                                    .getModule("android_bridge")
                                    .callAttr("spike_get_channels_json", 10)
                                    .toString()
                            } catch (e: Throwable) {
                                "EXC: ${e.message}"
                            }
                        }
                        channelsJson = result
                    }
                }) { Text("channels") }
            }

            Text("init: $initStatus", color = Color.White)
            Text("status: $statusJson", color = Color.White)
            Text("channels: $channelsJson", color = Color.White)
        }
    }
}
