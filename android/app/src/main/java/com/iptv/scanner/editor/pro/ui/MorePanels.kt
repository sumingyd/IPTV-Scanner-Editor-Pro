package com.iptv.scanner.editor.pro.ui

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CameraAlt
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Subtitles
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Slider
import androidx.compose.material3.SliderDefaults
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import org.json.JSONArray

/**
 * 更多功能面板集合：与 PC 端 controllers 对齐，直接调 MpvController。
 *
 * 包含：
 * - [OpenUrlDialog]：打开网络流 URL 输入对话框
 * - [VideoSettingsPanel]：视频设置（图像调整/旋转/翻转）
 * - [AudioSettingsPanel]：音频设置（音轨/延迟/EQ 预设）
 * - [SubtitleSettingsPanel]：字幕设置（轨/样式/延迟/位置/加载）
 * - [PlaybackPanel]：播放设置（循环/AB/逐帧/速度）
 * - [ScreenshotPanel]：截图（模式选择）
 * - [ViewSettingsPanel]：视图设置（视频比例）
 * - [AboutPanel]：关于
 *
 * 所有面板都是全屏覆盖式 Surface，与 [PlayerSettingsPanel] 风格一致。
 */

// -----------------------------------------------------------------
// 通用组件
// -----------------------------------------------------------------

/**
 * 设置面板脚手架：标题栏 + 可滚动内容区域。
 * 与 PlayerSettingsPanel 风格统一，避免每个面板重复写标题栏代码。
 */
@Composable
private fun PanelScaffold(
    title: String,
    subtitle: String = "",
    onClose: () -> Unit,
    actions: @Composable (() -> Unit) = {},
    content: @Composable () -> Unit
) {
    Surface(
        color = Color(0xF0121212),
        modifier = Modifier.fillMaxSize()
    ) {
        Column(
            modifier = Modifier.fillMaxSize().padding(16.dp)
        ) {
            // 标题栏
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = title,
                        style = MaterialTheme.typography.headlineSmall,
                        color = Color.White
                    )
                    if (subtitle.isNotEmpty()) {
                        Text(
                            text = subtitle,
                            color = Color(0xFF888888),
                            fontSize = 12.sp
                        )
                    }
                }
                Row(verticalAlignment = Alignment.CenterVertically) {
                    actions()
                    IconButton(onClick = onClose) {
                        Icon(Icons.Default.Close, contentDescription = "关闭", tint = Color.White)
                    }
                }
            }
            Spacer(modifier = Modifier.height(16.dp))
            // 可滚动内容
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .verticalScroll(rememberScrollState())
            ) {
                content()
            }
        }
    }
}

@Composable
private fun SectionLabel(text: String) {
    Text(
        text = text,
        color = Color(0xFF4A9EFF),
        fontSize = 14.sp,
        fontWeight = FontWeight.SemiBold,
        modifier = Modifier.padding(top = 12.dp, bottom = 4.dp)
    )
}

@Composable
private fun DescText(text: String) {
    Text(
        text = text,
        color = Color(0xFF888888),
        fontSize = 12.sp,
        modifier = Modifier.padding(bottom = 8.dp)
    )
}

/**
 * 带标签和重置按钮的滑块。
 */
@Composable
private fun LabeledSlider(
    label: String,
    value: Float,
    range: ClosedFloatingPointRange<Float>,
    valueText: String,
    onValueChange: (Float) -> Unit,
    onReset: () -> Unit
) {
    Column(modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp)) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(text = label, color = Color.White, fontSize = 13.sp)
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    text = valueText,
                    color = Color(0xFF4A9EFF),
                    fontSize = 13.sp,
                    modifier = Modifier.width(60.dp),
                    fontWeight = FontWeight.Medium
                )
                TextButton(onClick = onReset, modifier = Modifier.padding(start = 0.dp)) {
                    Text("重置", fontSize = 12.sp, color = Color(0xFF888888))
                }
            }
        }
        Slider(
            value = value,
            onValueChange = onValueChange,
            valueRange = range,
            modifier = Modifier.fillMaxWidth(),
            colors = SliderDefaults.colors(
                thumbColor = Color(0xFF4A9EFF),
                activeTrackColor = Color(0xFF4A9EFF),
                inactiveTrackColor = Color(0xFF444444)
            )
        )
    }
}

// -----------------------------------------------------------------
// 打开网络流 URL 对话框
// -----------------------------------------------------------------

@Composable
fun OpenUrlDialog(viewModel: AppViewModel) {
    val open by viewModel.openUrlDialogOpen.collectAsState()
    if (!open) return

    var url by remember { mutableStateOf("") }

    AlertDialog(
        onDismissRequest = { viewModel.toggleOpenUrlDialog() },
        title = { Text("打开网络流") },
        text = {
            Column {
                Text(
                    "输入 M3U/M3U8/HLS/RTSP/RTMP 等协议 URL",
                    color = Color(0xFF888888),
                    fontSize = 12.sp
                )
                Spacer(modifier = Modifier.height(8.dp))
                OutlinedTextField(
                    value = url,
                    onValueChange = { url = it },
                    placeholder = { Text("https://example.com/stream.m3u8") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth()
                )
            }
        },
        confirmButton = {
            TextButton(onClick = {
                viewModel.playUrl(url.trim())
                url = ""
            }) { Text("播放") }
        },
        dismissButton = {
            TextButton(onClick = { viewModel.toggleOpenUrlDialog() }) { Text("取消") }
        }
    )
}

// -----------------------------------------------------------------
// 视频设置面板
// -----------------------------------------------------------------

/**
 * 视频设置面板：与 PC 端 controllers/video_controller.py 对齐。
 *
 * 功能：
 * - 图像调整：亮度/对比度/饱和度/色调/Gamma
 * - 旋转：0/90/180/270
 * - 翻转：无/水平/垂直/both
 * - 一键重置
 */
@Composable
fun VideoSettingsPanel(viewModel: AppViewModel) {
    val mpv = viewModel.mpv
    val fileLoaded by mpv.fileLoaded.collectAsState()

    // 读取当前值（面板打开时读取一次）
    var brightness by remember { mutableStateOf(mpv.getPropertyInt("brightness") ?: 0) }
    var contrast by remember { mutableStateOf(mpv.getPropertyInt("contrast") ?: 0) }
    var saturation by remember { mutableStateOf(mpv.getPropertyInt("saturation") ?: 0) }
    var hue by remember { mutableStateOf(mpv.getPropertyInt("hue") ?: 0) }
    var gamma by remember { mutableStateOf(mpv.getPropertyInt("gamma") ?: 0) }
    var rotate by remember { mutableStateOf(mpv.getPropertyInt("video-rotate") ?: 0) }
    var flipMode by remember { mutableStateOf("none") }

    PanelScaffold(
        title = "视频设置",
        subtitle = "图像调整 / 旋转 / 翻转",
        onClose = { viewModel.toggleVideoSettings() },
        actions = {
            TextButton(onClick = {
                // 一键重置所有图像参数
                brightness = 0; contrast = 0; saturation = 0; hue = 0; gamma = 0
                rotate = 0; flipMode = "none"
                mpv.setBrightness(0); mpv.setContrast(0); mpv.setSaturation(0)
                mpv.setHue(0); mpv.setGamma(0); mpv.setVideoRotate(0); mpv.setVideoFlip("")
                viewModel.showOsd("视频设置", "已重置")
            }) { Text("全部重置", color = Color(0xFF888888), fontSize = 12.sp) }
        }
    ) {
        if (!fileLoaded) {
            Text("未在播放，调整将在播放后生效", color = Color(0xFF888888), fontSize = 12.sp)
        }

        SectionLabel("图像调整")
        LabeledSlider(
            label = "亮度", value = brightness.toFloat(), range = -100f..100f,
            valueText = brightness.toString(),
            onValueChange = { brightness = it.toInt(); mpv.setBrightness(brightness) },
            onReset = { brightness = 0; mpv.setBrightness(0) }
        )
        LabeledSlider(
            label = "对比度", value = contrast.toFloat(), range = -100f..100f,
            valueText = contrast.toString(),
            onValueChange = { contrast = it.toInt(); mpv.setContrast(contrast) },
            onReset = { contrast = 0; mpv.setContrast(0) }
        )
        LabeledSlider(
            label = "饱和度", value = saturation.toFloat(), range = -100f..100f,
            valueText = saturation.toString(),
            onValueChange = { saturation = it.toInt(); mpv.setSaturation(saturation) },
            onReset = { saturation = 0; mpv.setSaturation(0) }
        )
        LabeledSlider(
            label = "色调", value = hue.toFloat(), range = -100f..100f,
            valueText = hue.toString(),
            onValueChange = { hue = it.toInt(); mpv.setHue(hue) },
            onReset = { hue = 0; mpv.setHue(0) }
        )
        LabeledSlider(
            label = "Gamma", value = gamma.toFloat(), range = -100f..100f,
            valueText = gamma.toString(),
            onValueChange = { gamma = it.toInt(); mpv.setGamma(gamma) },
            onReset = { gamma = 0; mpv.setGamma(0) }
        )

        SectionLabel("旋转")
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            listOf(0, 90, 180, 270).forEach { deg ->
                FilterChip(
                    selected = rotate == deg,
                    onClick = { rotate = deg; mpv.setVideoRotate(deg) },
                    label = { Text("${deg}°") }
                )
            }
        }

        SectionLabel("翻转")
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            listOf("none" to "无", "horizontal" to "水平", "vertical" to "垂直", "both" to "both").forEach { (mode, label) ->
                FilterChip(
                    selected = flipMode == mode,
                    onClick = { flipMode = mode; mpv.setVideoFlip(mode) },
                    label = { Text(label) }
                )
            }
        }

        Spacer(modifier = Modifier.height(32.dp))
    }
}

// -----------------------------------------------------------------
// 音频设置面板
// -----------------------------------------------------------------

/** 解析 mpv track-list JSON，提取指定类型的轨道 */
private fun parseTracks(trackListJson: String, type: String): List<Pair<Int, String>> {
    if (trackListJson.isBlank()) return emptyList()
    return try {
        val arr = JSONArray(trackListJson)
        (0 until arr.length()).mapNotNull { i ->
            val obj = arr.getJSONObject(i)
            if (obj.optString("type") == type) {
                val id = obj.optInt("id")
                val title = obj.optString("title").ifEmpty { obj.optString("lang").ifEmpty { "轨道 $id" } }
                id to title
            } else null
        }
    } catch (e: Exception) {
        emptyList()
    }
}

/**
 * 音频设置面板：与 PC 端 controllers/audio_controller.py 对齐。
 *
 * 功能：
 * - 音轨选择（从 track-list 读取）
 * - 音频延迟（-10~10s）
 * - EQ 预设（正常/低音/高音/人声/流行/古典）
 */
@Composable
fun AudioSettingsPanel(viewModel: AppViewModel) {
    val mpv = viewModel.mpv
    val fileLoaded by mpv.fileLoaded.collectAsState()
    val trackListJson by mpv.trackListJson.collectAsState()

    // 音轨列表
    val audioTracks = remember(trackListJson) { parseTracks(trackListJson, "audio") }
    var currentAid by remember { mutableStateOf(0) }

    // 音频延迟
    var audioDelay by remember { mutableStateOf(mpv.getPropertyDouble("audio-delay") ?: 0.0) }

    // EQ 预设
    var eqPreset by remember { mutableStateOf("normal") }

    // 周期刷新当前 aid
    LaunchedEffect(trackListJson) {
        currentAid = mpv.getPropertyInt("aid") ?: 0
    }

    val eqPresets = remember {
        mapOf(
            "normal" to listOf(0f, 0f, 0f, 0f, 0f, 0f, 0f, 0f, 0f, 0f),
            "bass" to listOf(6f, 4f, 2f, 0f, 0f, 0f, 0f, 0f, 0f, 0f),
            "treble" to listOf(0f, 0f, 0f, 0f, 0f, 0f, 0f, 2f, 4f, 6f),
            "vocal" to listOf(0f, 0f, 0f, 2f, 4f, 4f, 4f, 2f, 0f, 0f),
            "pop" to listOf(-2f, 0f, 2f, 4f, 4f, 2f, 0f, -2f, -2f, 0f),
            "classic" to listOf(2f, 2f, 0f, 0f, 0f, 0f, 0f, 0f, 2f, 2f)
        )
    }

    PanelScaffold(
        title = "音频设置",
        subtitle = "音轨 / 延迟 / 均衡器",
        onClose = { viewModel.toggleAudioSettings() },
        actions = {
            TextButton(onClick = {
                audioDelay = 0.0; mpv.setAudioDelay(0.0)
                eqPreset = "normal"; mpv.resetAudioEq()
                viewModel.showOsd("音频设置", "已重置")
            }) { Text("重置", color = Color(0xFF888888), fontSize = 12.sp) }
        }
    ) {
        if (!fileLoaded) {
            Text("未在播放", color = Color(0xFF888888), fontSize = 12.sp)
        }

        SectionLabel("音轨")
        if (audioTracks.isEmpty()) {
            DescText("无可用音轨（单音频流）")
        } else {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                audioTracks.forEach { (id, title) ->
                    FilterChip(
                        selected = currentAid == id,
                        onClick = { currentAid = id; mpv.setAudioTrack(id) },
                        label = { Text(title, maxLines = 1) }
                    )
                }
            }
        }

        SectionLabel("音频延迟")
        LabeledSlider(
            label = "延迟（秒）",
            value = audioDelay.toFloat(),
            range = -10f..10f,
            valueText = "${"%.1f".format(audioDelay)}s",
            onValueChange = { audioDelay = it.toDouble(); mpv.setAudioDelay(audioDelay) },
            onReset = { audioDelay = 0.0; mpv.setAudioDelay(0.0) }
        )

        SectionLabel("均衡器预设")
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            listOf("normal" to "正常", "bass" to "低音", "treble" to "高音",
                "vocal" to "人声", "pop" to "流行", "classic" to "古典").forEach { (key, label) ->
                FilterChip(
                    selected = eqPreset == key,
                    onClick = {
                        eqPreset = key
                        mpv.setAudioEq(eqPresets[key] ?: emptyList())
                        viewModel.showOsd("EQ", label)
                    },
                    label = { Text(label) }
                )
            }
        }

        Spacer(modifier = Modifier.height(32.dp))
    }
}

// -----------------------------------------------------------------
// 字幕设置面板
// -----------------------------------------------------------------

/**
 * 字幕设置面板：与 PC 端 controllers/subtitle_controller.py 对齐。
 *
 * 功能：
 * - 字幕轨选择
 * - 字幕显示开关
 * - 字幕延迟（-10~10s）
 * - 字幕缩放（0.5~3.0）
 * - 字幕位置（0~100）
 * - 加载外挂字幕（文件选择器）
 */
@Composable
fun SubtitleSettingsPanel(viewModel: AppViewModel) {
    val mpv = viewModel.mpv
    val fileLoaded by mpv.fileLoaded.collectAsState()
    val trackListJson by mpv.trackListJson.collectAsState()

    // 字幕轨列表
    val subTracks = remember(trackListJson) { parseTracks(trackListJson, "sub") }
    var currentSid by remember { mutableStateOf(0) }
    var subVisible by remember { mutableStateOf(mpv.getPropertyBoolean("sub-visibility") ?: true) }
    var subDelay by remember { mutableStateOf(mpv.getPropertyDouble("sub-delay") ?: 0.0) }
    var subScale by remember { mutableStateOf(mpv.getPropertyDouble("sub-scale") ?: 1.0) }
    var subPos by remember { mutableStateOf(mpv.getPropertyInt("sub-pos") ?: 0) }

    // 文件选择器（加载外挂字幕）
    val subLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.OpenDocument()
    ) { uri: Uri? ->
        if (uri != null) viewModel.loadSubtitleFile(uri)
    }

    LaunchedEffect(trackListJson) {
        currentSid = mpv.getPropertyInt("sid") ?: 0
    }

    PanelScaffold(
        title = "字幕设置",
        subtitle = "轨道 / 延迟 / 缩放 / 位置 / 加载",
        onClose = { viewModel.toggleSubtitleSettings() },
        actions = {
            // 加载外挂字幕按钮
            IconButton(onClick = {
                subLauncher.launch(arrayOf(
                    "application/x-subrip", "text/plain", "application/octet-stream",
                    "application/x-srt", "application/x-ass", "application/x-ssa"
                ))
            }) {
                Icon(Icons.Default.Subtitles, contentDescription = "加载字幕", tint = Color.White)
            }
            TextButton(onClick = {
                subDelay = 0.0; mpv.setSubDelay(0.0)
                subScale = 1.0; mpv.setSubScale(1.0)
                subPos = 0; mpv.setSubPos(0)
                viewModel.showOsd("字幕设置", "已重置")
            }) { Text("重置", color = Color(0xFF888888), fontSize = 12.sp) }
        }
    ) {
        if (!fileLoaded) {
            Text("未在播放", color = Color(0xFF888888), fontSize = 12.sp)
        }

        // 字幕显示开关
        SectionLabel("字幕显示")
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text("显示字幕", color = Color.White, fontSize = 14.sp)
            Switch(
                checked = subVisible,
                onCheckedChange = { subVisible = it; mpv.setSubVisibility(it) }
            )
        }

        SectionLabel("字幕轨")
        if (subTracks.isEmpty()) {
            DescText("无内置字幕轨，可点击右上角图标加载外挂字幕")
        } else {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                subTracks.forEach { (id, title) ->
                    FilterChip(
                        selected = currentSid == id,
                        onClick = { currentSid = id; mpv.setSubTrack(id) },
                        label = { Text(title, maxLines = 1) }
                    )
                }
            }
        }

        SectionLabel("字幕延迟")
        LabeledSlider(
            label = "延迟（秒）",
            value = subDelay.toFloat(),
            range = -10f..10f,
            valueText = "${"%.1f".format(subDelay)}s",
            onValueChange = { subDelay = it.toDouble(); mpv.setSubDelay(subDelay) },
            onReset = { subDelay = 0.0; mpv.setSubDelay(0.0) }
        )

        SectionLabel("字幕缩放")
        LabeledSlider(
            label = "缩放",
            value = subScale.toFloat(),
            range = 0.5f..3.0f,
            valueText = "${"%.1f".format(subScale)}x",
            onValueChange = { subScale = it.toDouble(); mpv.setSubScale(subScale) },
            onReset = { subScale = 1.0; mpv.setSubScale(1.0) }
        )

        SectionLabel("字幕位置（距底部 %）")
        LabeledSlider(
            label = "位置",
            value = subPos.toFloat(),
            range = 0f..100f,
            valueText = "$subPos%",
            onValueChange = { subPos = it.toInt(); mpv.setSubPos(subPos) },
            onReset = { subPos = 0; mpv.setSubPos(0) }
        )

        Spacer(modifier = Modifier.height(32.dp))
    }
}

// -----------------------------------------------------------------
// 播放设置面板
// -----------------------------------------------------------------

/**
 * 播放设置面板：与 PC 端 controllers/playback_controller.py 对齐。
 *
 * 功能：
 * - 循环模式（单文件/列表/无）
 * - AB 循环（设置 A/B 点，清除）
 * - 逐帧（前进/后退）
 * - 速度调节（0.25~4.0）
 */
@Composable
fun PlaybackPanel(viewModel: AppViewModel) {
    val mpv = viewModel.mpv
    val fileLoaded by mpv.fileLoaded.collectAsState()
    val speed by mpv.speed.collectAsState()
    val chapterCount by mpv.chapterCount.collectAsState()
    val currentChapter by mpv.currentChapter.collectAsState()

    var loopFile by remember { mutableStateOf("no") }
    var loopPlaylist by remember { mutableStateOf("no") }
    var abLoopA by remember { mutableStateOf<Double?>(null) }
    var abLoopB by remember { mutableStateOf<Double?>(null) }

    PanelScaffold(
        title = "播放设置",
        subtitle = "循环 / AB / 逐帧 / 速度",
        onClose = { viewModel.togglePlaybackPanel() },
        actions = {
            TextButton(onClick = {
                loopFile = "no"; loopPlaylist = "no"
                abLoopA = null; abLoopB = null
                mpv.setLoopFile("no"); mpv.setLoopPlaylist("no"); mpv.clearAbLoop()
                mpv.setSpeed(1.0)
                viewModel.showOsd("播放设置", "已重置")
            }) { Text("重置", color = Color(0xFF888888), fontSize = 12.sp) }
        }
    ) {
        if (!fileLoaded) {
            Text("未在播放", color = Color(0xFF888888), fontSize = 12.sp)
        }

        SectionLabel("播放速度")
        LabeledSlider(
            label = "速度",
            value = speed.toFloat(),
            range = 0.25f..4.0f,
            valueText = "${"%.2f".format(speed)}x",
            onValueChange = { mpv.setSpeed(it.toDouble()) },
            onReset = { mpv.setSpeed(1.0) }
        )

        SectionLabel("循环模式")
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            listOf("no" to "不循环", "inf" to "单曲循环", "yes" to "循环一次").forEach { (mode, label) ->
                FilterChip(
                    selected = loopFile == mode,
                    onClick = { loopFile = mode; mpv.setLoopFile(mode) },
                    label = { Text(label) }
                )
            }
        }
        Spacer(modifier = Modifier.height(8.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            listOf("no" to "列表不循环", "inf" to "列表循环", "force" to "强制列表循环").forEach { (mode, label) ->
                FilterChip(
                    selected = loopPlaylist == mode,
                    onClick = { loopPlaylist = mode; mpv.setLoopPlaylist(mode) },
                    label = { Text(label) }
                )
            }
        }

        SectionLabel("A/B 循环")
        DescText("设置 A 点和 B 点后，在该区间内循环播放")
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(onClick = {
                abLoopA = mpv.timePos.value
                mpv.setAbLoopA()
                viewModel.showOsd("AB 循环", "A 点: ${"%.1f".format(abLoopA)}s")
            }) { Text("设置 A 点") }
            OutlinedButton(onClick = {
                abLoopB = mpv.timePos.value
                mpv.setAbLoopB()
                viewModel.showOsd("AB 循环", "B 点: ${"%.1f".format(abLoopB)}s")
            }) { Text("设置 B 点") }
            OutlinedButton(onClick = {
                abLoopA = null; abLoopB = null
                mpv.clearAbLoop()
                viewModel.showOsd("AB 循环", "已清除")
            }) { Text("清除") }
        }
        if (abLoopA != null || abLoopB != null) {
            Text(
                "A: ${abLoopA?.let { "%.1f".format(it) + "s" } ?: "未设置"}  " +
                    "B: ${abLoopB?.let { "%.1f".format(it) + "s" } ?: "未设置"}",
                color = Color(0xFF4A9EFF),
                fontSize = 12.sp,
                modifier = Modifier.padding(top = 4.dp)
            )
        }

        SectionLabel("逐帧")
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(onClick = { mpv.frameBackStep() }) { Text("◀ 上一帧") }
            OutlinedButton(onClick = { mpv.frameStep() }) { Text("下一帧 ▶") }
        }

        // 章节（如果有）
        if (chapterCount > 0) {
            SectionLabel("章节（${chapterCount} 个）")
            Text(
                "当前: 第 ${currentChapter + 1} 章",
                color = Color.White,
                fontSize = 13.sp
            )
            Spacer(modifier = Modifier.height(8.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = { mpv.chapterPrev() }) { Text("◀ 上一章") }
                OutlinedButton(onClick = { mpv.chapterNext() }) { Text("下一章 ▶") }
            }
        }

        Spacer(modifier = Modifier.height(32.dp))
    }
}

// -----------------------------------------------------------------
// 截图面板
// -----------------------------------------------------------------

/**
 * 截图面板：与 PC 端 controllers/screenshot_controller.py 对齐。
 *
 * 功能：
 * - 截图模式选择（仅画面/含字幕/含 OSD）
 * - 截图按钮
 * - 保存到 Pictures/IPTV_Screenshots 目录
 */
@Composable
fun ScreenshotPanel(viewModel: AppViewModel) {
    var mode by remember { mutableStateOf("video") }
    val fileLoaded by viewModel.mpv.fileLoaded.collectAsState()

    PanelScaffold(
        title = "截图",
        subtitle = "保存到 Pictures/IPTV_Screenshots",
        onClose = { viewModel.toggleScreenshotPanel() }
    ) {
        if (!fileLoaded) {
            Text("未在播放，无法截图", color = Color(0xFF888888), fontSize = 12.sp)
        }

        SectionLabel("截图模式")
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            listOf("video" to "仅画面", "subtitles" to "含字幕", "window" to "含 OSD").forEach { (m, label) ->
                FilterChip(
                    selected = mode == m,
                    onClick = { mode = m },
                    label = { Text(label) }
                )
            }
        }

        Spacer(modifier = Modifier.height(16.dp))

        // 截图按钮
        Surface(
            color = Color(0xFF4A9EFF),
            shape = RoundedCornerShape(8.dp),
            modifier = Modifier
                .fillMaxWidth()
                .height(52.dp)
                .clickable {
                    if (fileLoaded) viewModel.takeScreenshot(mode)
                    else viewModel.showOsd("未在播放")
                }
        ) {
            Row(
                modifier = Modifier.fillMaxSize(),
                horizontalArrangement = Arrangement.Center,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Icon(Icons.Default.CameraAlt, contentDescription = null, tint = Color.White)
                Spacer(modifier = Modifier.width(8.dp))
                Text("截图", color = Color.White, fontSize = 16.sp, fontWeight = FontWeight.Medium)
            }
        }

        Spacer(modifier = Modifier.height(16.dp))
        DescText("截图自动保存到设备的 Pictures/IPTV_Screenshots 目录")
    }
}

// -----------------------------------------------------------------
// 视图设置面板
// -----------------------------------------------------------------

/**
 * 视图设置面板：与 PC 端 controllers/view_controller.py 对齐。
 *
 * 功能：
 * - 视频比例（自适应/16:9/4:3/拉伸）
 * - OSD 显示
 */
@Composable
fun ViewSettingsPanel(viewModel: AppViewModel) {
    val mpv = viewModel.mpv
    var aspectMode by remember { mutableStateOf("auto") }

    PanelScaffold(
        title = "视图设置",
        subtitle = "视频比例 / OSD",
        onClose = { viewModel.toggleViewSettings() }
    ) {
        SectionLabel("视频比例")
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            listOf("auto" to "自适应", "16:9" to "16:9", "4:3" to "4:3", "stretch" to "拉伸").forEach { (mode, label) ->
                FilterChip(
                    selected = aspectMode == mode,
                    onClick = {
                        aspectMode = mode
                        when (mode) {
                            "auto" -> {
                                mpv.setPropertyBoolean("keepaspect", true)
                                mpv.setPropertyString("video-aspect-override", "0")
                            }
                            "16:9" -> {
                                mpv.setPropertyBoolean("keepaspect", true)
                                mpv.setPropertyString("video-aspect-override", "1.7778")
                            }
                            "4:3" -> {
                                mpv.setPropertyBoolean("keepaspect", true)
                                mpv.setPropertyString("video-aspect-override", "1.3333")
                            }
                            "stretch" -> {
                                mpv.setPropertyBoolean("keepaspect", false)
                            }
                        }
                        viewModel.showOsd("视频比例", label)
                    },
                    label = { Text(label) }
                )
            }
        }

        SectionLabel("OSD")
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(onClick = { mpv.showOsd("播放时间: ${"%.0f".format(mpv.timePos.value)}秒", 2000) }) {
                Text("显示时间")
            }
            OutlinedButton(onClick = {
                val filename = mpv.getPropertyString("filename") ?: mpv.getPropertyString("media-title") ?: ""
                mpv.showOsd(filename, 3000)
            }) { Text("显示文件名") }
        }

        Spacer(modifier = Modifier.height(32.dp))
    }
}

// -----------------------------------------------------------------
// 关于面板
// -----------------------------------------------------------------

/**
 * 关于面板：版本信息 + 功能说明。
 */
@Composable
fun AboutPanel(viewModel: AppViewModel) {
    PanelScaffold(
        title = "关于",
        subtitle = "IPTV Scanner Editor Pro",
        onClose = { viewModel.toggleAboutPanel() }
    ) {
        SectionLabel("版本信息")
        Surface(
            color = Color(0xFF1E1E1E),
            shape = RoundedCornerShape(8.dp),
            modifier = Modifier.fillMaxWidth()
        ) {
            Column(modifier = Modifier.padding(16.dp)) {
                InfoRow("应用名称", "IPTV Scanner Editor Pro")
                InfoRow("版本", "48.0.8.0")
                InfoRow("构建日期", "2026-07-01")
                InfoRow("播放引擎", "mpv (libmpv)")
                InfoRow("UI 框架", "Jetpack Compose")
                InfoRow("Python 引擎", "Chaquopy")
            }
        }

        SectionLabel("功能特性")
        val features = listOf(
            "频道播放：支持 HLS/RTSP/RTMP/HTTP 等协议",
            "订阅源管理：M3U 播放列表 CRUD + 自动加载",
            "EPG 节目单：XMLTV 格式，按频道/日期/搜索",
            "回看/时移：catchup-source 支持，EPG 过去节目回看",
            "视频调整：亮度/对比度/饱和度/色调/Gamma/旋转/翻转",
            "音频调整：音轨切换/延迟/10段EQ预设",
            "字幕：轨道切换/延迟/缩放/位置/外挂加载",
            "截图：仅画面/含字幕/含 OSD",
            "播放控制：循环/AB循环/逐帧/速度/章节",
            "局域网管理：TV 端遥控器扫码管理（5分钟自动停止）",
            "备份恢复：订阅源/EPG源/收藏/历史/队列/播放器设置",
            "TV 适配：DPAD 遥控器/手机触摸双模式"
        )
        features.forEach { feature ->
            Text(
                text = "• $feature",
                color = Color(0xFFCCCCCC),
                fontSize = 12.sp,
                modifier = Modifier.padding(vertical = 2.dp, horizontal = 4.dp)
            )
        }

        Spacer(modifier = Modifier.height(32.dp))
    }
}

@Composable
private fun InfoRow(label: String, value: String) {
    Row(
        modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp),
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        Text(text = label, color = Color(0xFF888888), fontSize = 13.sp)
        Text(text = value, color = Color.White, fontSize = 13.sp, fontWeight = FontWeight.Medium)
    }
}
