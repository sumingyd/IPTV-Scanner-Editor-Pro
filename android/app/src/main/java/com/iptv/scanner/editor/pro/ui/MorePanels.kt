package com.iptv.scanner.editor.pro.ui

import android.content.Intent
import android.net.Uri
import android.os.Build
import android.util.Log
import com.iptv.scanner.editor.pro.data.BookmarkItem
import com.iptv.scanner.editor.pro.data.ReminderItem
import com.iptv.scanner.editor.pro.data.ResumeItem
import com.iptv.scanner.editor.pro.data.ScanResult
import com.iptv.scanner.editor.pro.data.SubtitleItem
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Canvas
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
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Analytics
import androidx.compose.material.icons.filled.CalendarMonth
import androidx.compose.material.icons.filled.CameraAlt
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.History
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.Radar
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Subtitles
import androidx.compose.material.icons.filled.SyncAlt
import androidx.compose.material.icons.filled.Bookmark
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Divider
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
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
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.foundation.focusGroup
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.iptv.scanner.editor.pro.data.MappingEntry
import com.iptv.scanner.editor.pro.ui.theme.tvFocusBorder
import org.json.JSONArray
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

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
    scrollable: Boolean = true,
    content: @Composable () -> Unit
) {
    // 面板打开时主动抢焦点，避免焦点回落到下层统一面板的菜单项导致无法操作子面板。
    // focusGroup() 让 DPAD 导航限制在面板内部，不外溢到下层。
    val closeFocusRequester = remember { FocusRequester() }
    LaunchedEffect(Unit) {
        runCatching { closeFocusRequester.requestFocus() }
    }
    Surface(
        color = Color(0xF0121212),
        modifier = Modifier.fillMaxSize()
    ) {
        Column(
            modifier = Modifier.fillMaxSize().focusGroup().padding(16.dp)
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
                    IconButton(
                        onClick = onClose,
                        modifier = Modifier.tvFocusBorder().focusRequester(closeFocusRequester)
                    ) {
                        Icon(Icons.Default.Close, contentDescription = "关闭", tint = Color.White)
                    }
                }
            }
            Spacer(modifier = Modifier.height(16.dp))
            // 内容区域：scrollable=true 时用 verticalScroll（适用于普通 Column 内容），
            // scrollable=false 时不加 verticalScroll（适用于内含 LazyColumn 的面板，避免无限高度约束崩溃）
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .then(if (scrollable) Modifier.verticalScroll(rememberScrollState()) else Modifier)
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
                TextButton(onClick = onReset, modifier = Modifier.padding(start = 0.dp).tvFocusBorder()) {
                    Text("重置", fontSize = 12.sp, color = Color(0xFF888888))
                }
            }
        }
        Slider(
            value = value,
            onValueChange = onValueChange,
            valueRange = range,
            modifier = Modifier.fillMaxWidth().tvFocusBorder(),
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
            TextButton(
                onClick = {
                    viewModel.playUrl(url.trim())
                    url = ""
                },
                modifier = Modifier.tvFocusBorder()
            ) { Text("播放") }
        },
        dismissButton = {
            TextButton(
                onClick = { viewModel.toggleOpenUrlDialog() },
                modifier = Modifier.tvFocusBorder()
            ) { Text("取消") }
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
    // 3D 立体模式（回填当前值）
    var stereoMode by remember { mutableStateOf(mpv.getVideoStereoMode() ?: "mono") }
    // 360° 视角控制
    var projection by remember { mutableStateOf("equirect") }
    var yaw by remember { mutableStateOf(0.0) }
    var pitch by remember { mutableStateOf(0.0) }
    var roll by remember { mutableStateOf(0.0) }

    PanelScaffold(
        title = "视频设置",
        subtitle = "图像调整 / 旋转 / 翻转 / 3D 360",
        onClose = { viewModel.toggleVideoSettings() },
        actions = {
            TextButton(
                onClick = {
                    // 一键重置所有图像参数 + 3D/360
                    brightness = 0; contrast = 0; saturation = 0; hue = 0; gamma = 0
                    rotate = 0; flipMode = "none"
                    stereoMode = "mono"; yaw = 0.0; pitch = 0.0; roll = 0.0
                    mpv.setBrightness(0); mpv.setContrast(0); mpv.setSaturation(0)
                    mpv.setHue(0); mpv.setGamma(0); mpv.setVideoRotate(0); mpv.setVideoFlip("")
                    mpv.setVideoStereoMode("mono"); mpv.clear360Filter()
                    viewModel.showOsd("视频设置", "已重置")
                },
                modifier = Modifier.tvFocusBorder()
            ) { Text("全部重置", color = Color(0xFF888888), fontSize = 12.sp) }
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
                    label = { Text("${deg}°") },
                    modifier = Modifier.tvFocusBorder()
                )
            }
        }

        SectionLabel("翻转")
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            listOf("none" to "无", "horizontal" to "水平", "vertical" to "垂直", "both" to "both").forEach { (mode, label) ->
                FilterChip(
                    selected = flipMode == mode,
                    onClick = { flipMode = mode; mpv.setVideoFlip(mode) },
                    label = { Text(label) },
                    modifier = Modifier.tvFocusBorder()
                )
            }
        }

        // -----------------------------------------------------------------
        // 3D 立体模式（与 PC 端 _STEREO_MODES / Web 端 stereoMode 对齐）
        // 实时切换：点击即生效
        // -----------------------------------------------------------------
        SectionLabel("3D 立体模式")
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            listOf(
                "mono" to "2D", "sbs" to "左右(左)", "sbs2" to "左右(右)",
                "ab" to "上下(上)", "ab2" to "上下(下)"
            ).forEach { (mode, label) ->
                FilterChip(
                    selected = stereoMode == mode,
                    onClick = { stereoMode = mode; mpv.setVideoStereoMode(mode) },
                    label = { Text(label) },
                    modifier = Modifier.tvFocusBorder()
                )
            }
        }

        // -----------------------------------------------------------------
        // 360° 视角控制（与 PC 端 set_360_view / Web 端 apply360 对齐）
        // 调整滑块后点击"应用"才生效，避免拖动时频繁添加/移除滤镜
        // 注意：panorama 滤镜需 ffmpeg 编译时启用，部分设备可能不可用
        // -----------------------------------------------------------------
        SectionLabel("360° 视角")
        DescText("调整后点击「应用」生效。需 ffmpeg panorama 滤镜支持，部分设备不可用")

        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("投影：", color = Color.White, fontSize = 13.sp)
            listOf("flat" to "平面", "equirect" to "等距柱状", "cubemap" to "立方体贴图").forEach { (p, label) ->
                FilterChip(
                    selected = projection == p,
                    onClick = { projection = p },
                    label = { Text(label) },
                    modifier = Modifier.tvFocusBorder()
                )
            }
        }

        LabeledSlider(
            label = "Yaw 偏航", value = yaw.toFloat(), range = -180f..180f,
            valueText = "${yaw.toInt()}°",
            onValueChange = { yaw = it.toDouble() },
            onReset = { yaw = 0.0 }
        )
        LabeledSlider(
            label = "Pitch 俯仰", value = pitch.toFloat(), range = -90f..90f,
            valueText = "${pitch.toInt()}°",
            onValueChange = { pitch = it.toDouble() },
            onReset = { pitch = 0.0 }
        )
        LabeledSlider(
            label = "Roll 滚转", value = roll.toFloat(), range = -180f..180f,
            valueText = "${roll.toInt()}°",
            onValueChange = { roll = it.toDouble() },
            onReset = { roll = 0.0 }
        )

        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(
                onClick = {
                    mpv.set360View(yaw, pitch, roll, projection)
                    viewModel.showOsd("360° 视角", "已应用")
                },
                modifier = Modifier.tvFocusBorder()
            ) { Text("应用 360°") }
            OutlinedButton(
                onClick = {
                    mpv.clear360Filter()
                    yaw = 0.0; pitch = 0.0; roll = 0.0
                    viewModel.showOsd("360° 视角", "已清除")
                },
                modifier = Modifier.tvFocusBorder()
            ) { Text("清除 360°") }
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

    // 音调（变调不变速，0.5~2.0，1.0=正常）
    var audioPitch by remember { mutableStateOf(mpv.getPropertyDouble("audio-pitch-correction") ?: 1.0) }

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
        subtitle = "音轨 / 延迟 / EQ / 音调",
        onClose = { viewModel.toggleAudioSettings() },
        actions = {
            TextButton(
                onClick = {
                    audioDelay = 0.0; mpv.setAudioDelay(0.0)
                    eqPreset = "normal"; mpv.resetAudioEq()
                    audioPitch = 1.0; mpv.setAudioPitch(1.0)
                    viewModel.showOsd("音频设置", "已重置")
                },
                modifier = Modifier.tvFocusBorder()
            ) { Text("重置", color = Color(0xFF888888), fontSize = 12.sp) }
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
                        label = { Text(title, maxLines = 1) },
                        modifier = Modifier.tvFocusBorder()
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
                    label = { Text(label) },
                    modifier = Modifier.tvFocusBorder()
                )
            }
        }

        SectionLabel("音调（变调不变速）")
        LabeledSlider(
            label = "音调",
            value = audioPitch.toFloat(),
            range = 0.5f..2.0f,
            valueText = "${"%.2f".format(audioPitch)}x",
            onValueChange = { audioPitch = it.toDouble(); mpv.setAudioPitch(audioPitch) },
            onReset = { audioPitch = 1.0; mpv.setAudioPitch(1.0) }
        )

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
    // 字幕样式（与 PC 端 SubtitleStyleDialog 对齐）
    var subFontSize by remember { mutableStateOf((mpv.getPropertyInt("sub-font-size") ?: 55)) }
    var subColor by remember { mutableStateOf(mpv.getPropertyString("sub-color") ?: "#FFFFFFFF") }
    var subBorderColor by remember { mutableStateOf(mpv.getPropertyString("sub-border-color") ?: "#FF000000") }
    var subBorderSize by remember { mutableStateOf((mpv.getPropertyDouble("sub-border-size") ?: 2.5)) }
    var subShadowOffset by remember { mutableStateOf((mpv.getPropertyDouble("sub-shadow-offset") ?: 0.0)) }
    var subBold by remember { mutableStateOf((mpv.getPropertyInt("sub-bold") ?: 1) == 1) }
    var subItalic by remember { mutableStateOf((mpv.getPropertyInt("sub-italic") ?: 0) == 1) }

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
        subtitle = "轨道 / 延迟 / 缩放 / 位置 / 样式 / 加载",
        onClose = { viewModel.toggleSubtitleSettings() },
        actions = {
            // 在线搜索字幕按钮
            IconButton(onClick = {
                viewModel.toggleSubtitleSettings()
                viewModel.toggleSubtitleSearchPanel()
            }, modifier = Modifier.tvFocusBorder()) {
                Icon(Icons.Default.Search, contentDescription = "在线搜索字幕", tint = Color.White)
            }
            // 加载外挂字幕按钮
            IconButton(onClick = {
                subLauncher.launch(arrayOf(
                    "application/x-subrip", "text/plain", "application/octet-stream",
                    "application/x-srt", "application/x-ass", "application/x-ssa"
                ))
            }, modifier = Modifier.tvFocusBorder()) {
                Icon(Icons.Default.Subtitles, contentDescription = "加载字幕", tint = Color.White)
            }
            TextButton(
                onClick = {
                    subDelay = 0.0; mpv.setSubDelay(0.0)
                    subScale = 1.0; mpv.setSubScale(1.0)
                    subPos = 0; mpv.setSubPos(0)
                    // 重置字幕样式为默认值
                    subFontSize = 55; mpv.setPropertyString("sub-font-size", "55")
                    subColor = "#FFFFFFFF"; mpv.setPropertyString("sub-color", "#FFFFFFFF")
                    subBorderColor = "#FF000000"; mpv.setPropertyString("sub-border-color", "#FF000000")
                    subBorderSize = 2.5; mpv.setPropertyString("sub-border-size", "2.5")
                    subShadowOffset = 0.0; mpv.setPropertyString("sub-shadow-offset", "0")
                    subBold = true; mpv.setPropertyString("sub-bold", "1")
                    subItalic = false; mpv.setPropertyString("sub-italic", "0")
                    viewModel.showOsd("字幕设置", "已重置")
                },
                modifier = Modifier.tvFocusBorder()
            ) { Text("重置", color = Color(0xFF888888), fontSize = 12.sp) }
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
                onCheckedChange = { subVisible = it; mpv.setSubVisibility(it) },
                modifier = Modifier.tvFocusBorder()
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
                        label = { Text(title, maxLines = 1) },
                        modifier = Modifier.tvFocusBorder()
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

        // -----------------------------------------------------------------
        // 字幕样式（与 PC 端 SubtitleStyleDialog 对齐）
        // -----------------------------------------------------------------
        SectionLabel("字幕样式")
        DescText("颜色/字体/边框/阴影高级设置")

        // 快速预设
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            listOf(
                "默认" to mapOf(
                    "font-size" to "55", "color" to "#FFFFFFFF",
                    "border-color" to "#FF000000", "border-size" to "2.5",
                    "bold" to "1", "italic" to "0", "shadow-offset" to "0"
                ),
                "黄字黑边" to mapOf(
                    "font-size" to "55", "color" to "#FFFFFF00",
                    "border-color" to "#FF000000", "border-size" to "2.5",
                    "bold" to "1", "italic" to "0", "shadow-offset" to "0"
                ),
                "白字大号" to mapOf(
                    "font-size" to "72", "color" to "#FFFFFFFF",
                    "border-color" to "#FF000000", "border-size" to "3",
                    "bold" to "1", "italic" to "0", "shadow-offset" to "0"
                ),
                "无边框带阴影" to mapOf(
                    "font-size" to "55", "color" to "#FFFFFFFF",
                    "border-color" to "#FF000000", "border-size" to "0",
                    "bold" to "1", "italic" to "0", "shadow-offset" to "2"
                )
            ).forEach { (name, style) ->
                OutlinedButton(
                    onClick = {
                        subFontSize = style["font-size"]?.toIntOrNull() ?: 55
                        subColor = style["color"] ?: "#FFFFFFFF"
                        subBorderColor = style["border-color"] ?: "#FF000000"
                        subBorderSize = style["border-size"]?.toDoubleOrNull() ?: 2.5
                        subShadowOffset = style["shadow-offset"]?.toDoubleOrNull() ?: 0.0
                        subBold = style["bold"] == "1"
                        subItalic = style["italic"] == "1"
                        style.forEach { (k, v) -> mpv.setPropertyString("sub-$k", v) }
                        viewModel.showOsd("字幕样式", name)
                    },
                    modifier = Modifier.tvFocusBorder()
                ) { Text(name, fontSize = 11.sp) }
            }
        }

        Spacer(modifier = Modifier.height(8.dp))

        // 字体大小
        LabeledSlider(
            label = "字体大小",
            value = subFontSize.toFloat(),
            range = 10f..100f,
            valueText = subFontSize.toString(),
            onValueChange = { subFontSize = it.toInt(); mpv.setPropertyString("sub-font-size", subFontSize.toString()) },
            onReset = { subFontSize = 55; mpv.setPropertyString("sub-font-size", "55") }
        )

        // 边框粗细
        LabeledSlider(
            label = "边框粗细",
            value = subBorderSize.toFloat(),
            range = 0f..10f,
            valueText = "${"%.1f".format(subBorderSize)}",
            onValueChange = { subBorderSize = it.toDouble(); mpv.setPropertyString("sub-border-size", "%.1f".format(subBorderSize)) },
            onReset = { subBorderSize = 2.5; mpv.setPropertyString("sub-border-size", "2.5") }
        )

        // 阴影偏移
        LabeledSlider(
            label = "阴影偏移",
            value = subShadowOffset.toFloat(),
            range = 0f..10f,
            valueText = "${"%.1f".format(subShadowOffset)}",
            onValueChange = { subShadowOffset = it.toDouble(); mpv.setPropertyString("sub-shadow-offset", "%.1f".format(subShadowOffset)) },
            onReset = { subShadowOffset = 0.0; mpv.setPropertyString("sub-shadow-offset", "0") }
        )

        // 字幕颜色选择（预设色块）
        Text("字幕颜色", color = Color.White, fontSize = 13.sp, modifier = Modifier.padding(top = 8.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.padding(vertical = 4.dp)) {
            listOf(
                "#FFFFFFFF" to Color.White, "#FFFFFF00" to Color.Yellow,
                "#FFFF0000" to Color.Red, "#FF00FF00" to Color.Green,
                "#FF00FFFF" to Color.Cyan, "#FF000000" to Color.Black
            ).forEach { (hex, color) ->
                Surface(
                    color = color,
                    shape = RoundedCornerShape(4.dp),
                    modifier = Modifier
                        .size(28.dp)
                        .clickable {
                            subColor = hex
                            mpv.setPropertyString("sub-color", hex)
                        }
                        .tvFocusBorder()
                ) {
                    if (subColor.equals(hex, ignoreCase = true)) {
                        Box(
                            modifier = Modifier.fillMaxSize(),
                            contentAlignment = Alignment.Center
                        ) {
                            Text("✓", color = if (color == Color.Black) Color.White else Color.Black, fontSize = 14.sp)
                        }
                    }
                }
            }
        }

        // 边框颜色选择（预设色块）
        Text("边框颜色", color = Color.White, fontSize = 13.sp, modifier = Modifier.padding(top = 8.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.padding(vertical = 4.dp)) {
            listOf(
                "#FF000000" to Color.Black, "#FFFFFFFF" to Color.White,
                "#FFFF0000" to Color.Red, "#FF0000FF" to Color.Blue,
                "#FF00FF00" to Color.Green, "#00000000" to Color.Transparent
            ).forEach { (hex, color) ->
                Surface(
                    color = color,
                    shape = RoundedCornerShape(4.dp),
                    modifier = Modifier
                        .size(28.dp)
                        .clickable {
                            subBorderColor = hex
                            mpv.setPropertyString("sub-border-color", hex)
                        }
                        .tvFocusBorder()
                ) {
                    if (subBorderColor.equals(hex, ignoreCase = true)) {
                        Box(
                            modifier = Modifier.fillMaxSize(),
                            contentAlignment = Alignment.Center
                        ) {
                            Text("✓", color = if (color == Color.Black) Color.White else Color.Black, fontSize = 14.sp)
                        }
                    }
                }
            }
        }

        // 加粗 / 斜体开关
        Row(
            modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
            horizontalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("加粗", color = Color.White, fontSize = 13.sp)
                Spacer(modifier = Modifier.width(8.dp))
                Switch(
                    checked = subBold,
                    onCheckedChange = { subBold = it; mpv.setPropertyString("sub-bold", if (it) "1" else "0") },
                    modifier = Modifier.tvFocusBorder()
                )
            }
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("斜体", color = Color.White, fontSize = 13.sp)
                Spacer(modifier = Modifier.width(8.dp))
                Switch(
                    checked = subItalic,
                    onCheckedChange = { subItalic = it; mpv.setPropertyString("sub-italic", if (it) "1" else "0") },
                    modifier = Modifier.tvFocusBorder()
                )
            }
        }

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
    val shuffleMode by viewModel.shuffleMode.collectAsState()

    var loopFile by remember { mutableStateOf("no") }
    var loopPlaylist by remember { mutableStateOf("no") }
    var abLoopA by remember { mutableStateOf<Double?>(null) }
    var abLoopB by remember { mutableStateOf<Double?>(null) }

    PanelScaffold(
        title = "播放设置",
        subtitle = "循环 / 随机 / AB / 逐帧 / 速度",
        onClose = { viewModel.togglePlaybackPanel() },
        actions = {
            TextButton(
                onClick = {
                    loopFile = "no"; loopPlaylist = "no"
                    abLoopA = null; abLoopB = null
                    mpv.setLoopFile("no"); mpv.setLoopPlaylist("no"); mpv.clearAbLoop()
                    mpv.setSpeed(1.0)
                    if (shuffleMode) viewModel.toggleShuffleMode()
                    viewModel.showOsd("播放设置", "已重置")
                },
                modifier = Modifier.tvFocusBorder()
            ) { Text("重置", color = Color(0xFF888888), fontSize = 12.sp) }
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
                    label = { Text(label) },
                    modifier = Modifier.tvFocusBorder()
                )
            }
        }
        Spacer(modifier = Modifier.height(8.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            listOf("no" to "列表不循环", "inf" to "列表循环", "force" to "强制列表循环").forEach { (mode, label) ->
                FilterChip(
                    selected = loopPlaylist == mode,
                    onClick = { loopPlaylist = mode; mpv.setLoopPlaylist(mode) },
                    label = { Text(label) },
                    modifier = Modifier.tvFocusBorder()
                )
            }
        }

        SectionLabel("随机播放")
        DescText("开启后，切换下一频道时在当前可见频道范围内随机选择（避免短期重复）。上一频道可回退到上一个随机频道。")
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Switch(
                checked = shuffleMode,
                onCheckedChange = { viewModel.toggleShuffleMode() },
                modifier = Modifier.tvFocusBorder()
            )
            Text(
                text = if (shuffleMode) "随机播放：开" else "随机播放：关",
                color = if (shuffleMode) Color(0xFF4A9EFF) else Color(0xFF888888),
                fontSize = 13.sp
            )
        }

        SectionLabel("A/B 循环")
        DescText("设置 A 点和 B 点后，在该区间内循环播放")
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(
                onClick = {
                    abLoopA = mpv.timePos.value
                    mpv.setAbLoopA()
                    viewModel.showOsd("AB 循环", "A 点: ${"%.1f".format(abLoopA)}s")
                },
                modifier = Modifier.tvFocusBorder()
            ) { Text("设置 A 点") }
            OutlinedButton(
                onClick = {
                    abLoopB = mpv.timePos.value
                    mpv.setAbLoopB()
                    viewModel.showOsd("AB 循环", "B 点: ${"%.1f".format(abLoopB)}s")
                },
                modifier = Modifier.tvFocusBorder()
            ) { Text("设置 B 点") }
            OutlinedButton(
                onClick = {
                    abLoopA = null; abLoopB = null
                    mpv.clearAbLoop()
                    viewModel.showOsd("AB 循环", "已清除")
                },
                modifier = Modifier.tvFocusBorder()
            ) { Text("清除") }
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
            OutlinedButton(
                onClick = { mpv.frameBackStep() },
                modifier = Modifier.tvFocusBorder()
            ) { Text("◀ 上一帧") }
            OutlinedButton(
                onClick = { mpv.frameStep() },
                modifier = Modifier.tvFocusBorder()
            ) { Text("下一帧 ▶") }
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
                OutlinedButton(
                    onClick = { mpv.chapterPrev() },
                    modifier = Modifier.tvFocusBorder()
                ) { Text("◀ 上一章") }
                OutlinedButton(
                    onClick = { mpv.chapterNext() },
                    modifier = Modifier.tvFocusBorder()
                ) { Text("下一章 ▶") }
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

    // 连拍截图状态
    val burstActive by viewModel.burstActive.collectAsState()
    val burstCount by viewModel.burstCount.collectAsState()
    val burstTotal by viewModel.burstTotal.collectAsState()
    var burstInterval by remember { mutableStateOf(2.0) }
    var burstTotalInput by remember { mutableStateOf(10) }

    PanelScaffold(
        title = "截图",
        subtitle = "单张 / 连拍 / 保存到 Pictures/IPTV_Screenshots",
        onClose = {
            // 关闭面板时停止连拍
            if (burstActive) viewModel.stopBurstScreenshot()
            viewModel.toggleScreenshotPanel()
        }
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
                    label = { Text(label) },
                    modifier = Modifier.tvFocusBorder()
                )
            }
        }

        Spacer(modifier = Modifier.height(16.dp))

        // 单张截图按钮
        Surface(
            color = Color(0xFF4A9AFF),
            shape = RoundedCornerShape(8.dp),
            modifier = Modifier
                .fillMaxWidth()
                .height(52.dp)
                .clickable {
                    if (fileLoaded) viewModel.takeScreenshot(mode)
                    else viewModel.showOsd("未在播放")
                }
                .tvFocusBorder()
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

        Spacer(modifier = Modifier.height(20.dp))

        // -----------------------------------------------------------------
        // 连拍截图（与 PC 端 BurstScreenshotDialog 对齐）
        // -----------------------------------------------------------------
        SectionLabel("连拍截图")
        DescText("按设定间隔自动截图，适合捕捉精彩瞬间")

        LabeledSlider(
            label = "间隔（秒）",
            value = burstInterval.toFloat(),
            range = 0.5f..60f,
            valueText = "${"%.1f".format(burstInterval)}s",
            onValueChange = { burstInterval = it.toDouble() },
            onReset = { burstInterval = 2.0 }
        )

        LabeledSlider(
            label = "总数（张）",
            value = burstTotalInput.toFloat(),
            range = 1f..999f,
            valueText = burstTotalInput.toString(),
            onValueChange = { burstTotalInput = it.toInt() },
            onReset = { burstTotalInput = 10 }
        )

        // 连拍进度
        if (burstActive) {
            Spacer(modifier = Modifier.height(8.dp))
            LinearProgressIndicator(
                progress = { if (burstTotal > 0) burstCount.toFloat() / burstTotal else 0f },
                modifier = Modifier.fillMaxWidth(),
                color = Color(0xFF4A9AFF),
                trackColor = Color(0xFF333333)
            )
            Spacer(modifier = Modifier.height(4.dp))
            Text(
                text = "进度：$burstCount / $burstTotal",
                color = Color(0xFF4A9AFF),
                fontSize = 12.sp
            )
        }

        Spacer(modifier = Modifier.height(8.dp))

        // 开始/停止连拍按钮
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            if (!burstActive) {
                OutlinedButton(
                    onClick = {
                        if (fileLoaded) viewModel.startBurstScreenshot(burstInterval, burstTotalInput, mode)
                        else viewModel.showOsd("未在播放")
                    },
                    modifier = Modifier.tvFocusBorder()
                ) { Text("开始连拍") }
            } else {
                OutlinedButton(
                    onClick = { viewModel.stopBurstScreenshot() },
                    modifier = Modifier.tvFocusBorder()
                ) { Text("停止连拍") }
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
                    label = { Text(label) },
                    modifier = Modifier.tvFocusBorder()
                )
            }
        }

        SectionLabel("OSD")
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(
                onClick = { mpv.showOsd("播放时间: ${"%.0f".format(mpv.timePos.value)}秒", 2000) },
                modifier = Modifier.tvFocusBorder()
            ) {
                Text("显示时间")
            }
            OutlinedButton(
                onClick = {
                    val filename = mpv.getPropertyString("filename") ?: mpv.getPropertyString("media-title") ?: ""
                    mpv.showOsd(filename, 3000)
                },
                modifier = Modifier.tvFocusBorder()
            ) { Text("显示文件名") }
        }

        Spacer(modifier = Modifier.height(32.dp))
    }
}

// -----------------------------------------------------------------
// 关于面板
// -----------------------------------------------------------------

/**
 * 关于面板：版本信息 + 检查更新 + 功能说明。
 */
@Composable
fun AboutPanel(viewModel: AppViewModel) {
    val currentVersion = remember { viewModel.getCurrentVersion() }
    val updateState by viewModel.updateState.collectAsState()

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
                InfoRow("版本", currentVersion)
                InfoRow("播放引擎", "mpv (libmpv)")
                InfoRow("UI 框架", "Jetpack Compose")
                InfoRow("Python 引擎", "Chaquopy")
            }
        }

        SectionLabel("版本检查")
        Row(
            modifier = Modifier.fillMaxWidth().padding(vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            OutlinedButton(
                onClick = { viewModel.checkForUpdates(auto = false) },
                enabled = updateState !is AppViewModel.UpdateState.Checking,
                modifier = Modifier.tvFocusBorder()
            ) {
                if (updateState is AppViewModel.UpdateState.Checking) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(16.dp),
                        strokeWidth = 2.dp,
                        color = MaterialTheme.colorScheme.primary
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text("检查中...")
                } else {
                    Text("检查更新")
                }
            }
            when (updateState) {
                is AppViewModel.UpdateState.Checking -> {}
                is AppViewModel.UpdateState.UpToDate -> {
                    Text("当前已是最新版本", color = Color(0xFF4CAF50), fontSize = 13.sp)
                }
                is AppViewModel.UpdateState.UpdateAvailable -> {
                    val info = updateState as AppViewModel.UpdateState.UpdateAvailable
                    Text(
                        "发现新版本 v${info.latestVersion}（当前 v$currentVersion）",
                        color = Color(0xFFFF9800),
                        fontSize = 13.sp,
                        fontWeight = FontWeight.Medium
                    )
                }
                is AppViewModel.UpdateState.Error -> {
                    val err = updateState as AppViewModel.UpdateState.Error
                    Text("检查失败: ${err.message}", color = Color(0xFFEF5350), fontSize = 13.sp)
                }
                else -> {}
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

/**
 * 更新提示对话框：发现新版本时弹出，提供应用内直接下载安装功能。
 *
 * 与 PC 端 UpdateController 的更新提示对齐。
 * 改进：TV 端跳转浏览器不便，改为通过 DownloadManager 直接下载 APK 并调起系统安装器。
 *
 * UI 状态：
 * - Idle / UpdateAvailable：显示「立即更新」按钮
 * - Downloading(progress)：显示进度条 + 「取消」按钮（禁用关闭）
 * - Completed：显示「立即安装」按钮（自动调起安装，按钮作为备用入口）
 * - Error：显示错误信息 + 「重试」按钮
 */
@Composable
fun UpdateDialog(viewModel: AppViewModel) {
    val open by viewModel.updateDialogOpen.collectAsState()
    if (!open) return

    val updateState by viewModel.updateState.collectAsState()
    val currentVersion = remember { viewModel.getCurrentVersion() }
    val apkState by viewModel.apkDownloadState.collectAsState()

    val info = updateState as? AppViewModel.UpdateState.UpdateAvailable
    if (info == null) {
        viewModel.dismissUpdateDialog()
        return
    }

    val isDownloading = apkState is AppViewModel.ApkDownloadState.Downloading
    val progress = (apkState as? AppViewModel.ApkDownloadState.Downloading)?.progress ?: 0

    AlertDialog(
        onDismissRequest = {
            // 下载中不允许点外部关闭（防止误触中断下载）
            if (!isDownloading) viewModel.dismissUpdateDialog()
        },
        title = { Text("发现新版本", fontWeight = FontWeight.Bold) },
        text = {
            Column {
                Text(
                    "新版本 v${info.latestVersion} 已发布",
                    color = Color(0xFFFF9800),
                    fontSize = 15.sp,
                    fontWeight = FontWeight.Medium
                )
                Spacer(modifier = Modifier.height(8.dp))
                Text(
                    "当前版本：v$currentVersion",
                    color = Color(0xFF888888),
                    fontSize = 13.sp
                )
                Spacer(modifier = Modifier.height(12.dp))

                when (val s = apkState) {
                    is AppViewModel.ApkDownloadState.Idle -> {
                        Text(
                            "点击「立即更新」开始下载并安装最新版 APK。",
                            color = Color(0xFFCCCCCC),
                            fontSize = 13.sp
                        )
                    }
                    is AppViewModel.ApkDownloadState.Downloading -> {
                        Text(
                            "正在下载更新包… ${s.progress}%",
                            color = Color(0xFF4A9EFF),
                            fontSize = 13.sp,
                            fontWeight = FontWeight.Medium
                        )
                        Spacer(modifier = Modifier.height(8.dp))
                        LinearProgressIndicator(
                            progress = { s.progress / 100f },
                            modifier = Modifier.fillMaxWidth(),
                            color = Color(0xFF4A9EFF),
                            trackColor = Color(0xFF333333)
                        )
                        Spacer(modifier = Modifier.height(4.dp))
                        Text(
                            "下载过程中请保持网络畅通，完成后将自动弹出安装界面。",
                            color = Color(0xFF888888),
                            fontSize = 11.sp
                        )
                    }
                    is AppViewModel.ApkDownloadState.Completed -> {
                        Text(
                            "下载完成，正在启动安装程序…",
                            color = Color(0xFF4CAF50),
                            fontSize = 13.sp,
                            fontWeight = FontWeight.Medium
                        )
                        Spacer(modifier = Modifier.height(4.dp))
                        Text(
                            "若安装界面未自动弹出，请点击「立即安装」重试。",
                            color = Color(0xFF888888),
                            fontSize = 11.sp
                        )
                    }
                    is AppViewModel.ApkDownloadState.Error -> {
                        Text(
                            "下载失败：${s.message}",
                            color = Color(0xFFE57373),
                            fontSize = 13.sp
                        )
                        Spacer(modifier = Modifier.height(4.dp))
                        Text(
                            "请检查网络后重试，或点击「浏览器下载」跳转 GitHub。",
                            color = Color(0xFF888888),
                            fontSize = 11.sp
                        )
                    }
                }
            }
        },
        confirmButton = {
            when (apkState) {
                is AppViewModel.ApkDownloadState.Idle -> {
                    TextButton(
                        onClick = { viewModel.downloadAndInstallApk(info.downloadUrl) },
                        modifier = Modifier.tvFocusBorder()
                    ) { Text("立即更新") }
                }
                is AppViewModel.ApkDownloadState.Downloading -> {
                    // 下载中只显示取消按钮
                    TextButton(
                        onClick = { viewModel.cancelApkDownload() },
                        modifier = Modifier.tvFocusBorder()
                    ) { Text("取消下载", color = Color(0xFFE57373)) }
                }
                is AppViewModel.ApkDownloadState.Completed -> {
                    TextButton(
                        onClick = { viewModel.installDownloadedApk() },
                        modifier = Modifier.tvFocusBorder()
                    ) { Text("立即安装") }
                }
                is AppViewModel.ApkDownloadState.Error -> {
                    TextButton(
                        onClick = { viewModel.downloadAndInstallApk(info.downloadUrl) },
                        modifier = Modifier.tvFocusBorder()
                    ) { Text("重试") }
                }
            }
        },
        dismissButton = {
            when {
                isDownloading -> {
                    // 下载中不显示 dismissButton（避免误触关闭对话框）
                }
                apkState is AppViewModel.ApkDownloadState.Completed -> {
                    TextButton(
                        onClick = { viewModel.dismissUpdateDialog() },
                        modifier = Modifier.tvFocusBorder()
                    ) { Text("关闭") }
                }
                else -> {
                    val context = androidx.compose.ui.platform.LocalContext.current
                    TextButton(
                        onClick = {
                            // 备用方案：跳转浏览器（用于下载失败或特殊场景）
                            val intent = Intent(Intent.ACTION_VIEW, Uri.parse(info.downloadUrl))
                            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                            try {
                                context.startActivity(intent)
                                viewModel.dismissUpdateDialog()
                            } catch (e: Exception) {
                                Log.e("UpdateDialog", "open browser failed", e)
                            }
                        },
                        modifier = Modifier.tvFocusBorder()
                    ) { Text(if (apkState is AppViewModel.ApkDownloadState.Error) "浏览器下载" else "稍后提醒") }
                }
            }
        }
    )
}

/**
 * 退出确认对话框：按 BACK 键退出时提示选择退出方式。
 * - 进入画中画：继续在小窗口中观看
 * - 立即退出：直接退出应用
 * - 取消：继续使用
 */
@Composable
fun ExitConfirmDialog(viewModel: AppViewModel) {
    val open by viewModel.exitConfirmOpen.collectAsState()
    if (!open) return

    val context = androidx.compose.ui.platform.LocalContext.current
    val activity = context as? android.app.Activity

    AlertDialog(
        onDismissRequest = { viewModel.dismissExitConfirm() },
        title = { Text("退出应用", fontWeight = FontWeight.Bold) },
        text = {
            Text(
                "您正在退出应用，请选择退出方式：",
                color = Color(0xFFCCCCCC),
                fontSize = 14.sp
            )
        },
        confirmButton = {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                // 进入 PiP
                if (activity != null &&
                    Build.VERSION.SDK_INT >= Build.VERSION_CODES.O &&
                    activity.packageManager.hasSystemFeature("android.software.picture_in_picture")
                ) {
                    TextButton(
                        onClick = {
                            viewModel.dismissExitConfirm()
                            try {
                                val builder = android.app.PictureInPictureParams.Builder()
                                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                                    builder.setAutoEnterEnabled(true)
                                    builder.setSeamlessResizeEnabled(true)
                                }
                                activity.enterPictureInPictureMode(builder.build())
                            } catch (e: Exception) {
                                Log.e("ExitConfirmDialog", "PiP failed", e)
                            }
                        },
                        modifier = Modifier.tvFocusBorder()
                    ) { Text("画中画") }
                }
                // 立即退出
                TextButton(
                    onClick = {
                        viewModel.dismissExitConfirm()
                        // 先停止播放，避免 Activity finish 后 mpv 在后台继续播放
                        viewModel.stopPlay()
                        activity?.finishAffinity()
                    },
                    modifier = Modifier.tvFocusBorder()
                ) { Text("立即退出", color = Color(0xFFEF5350)) }
            }
        },
        dismissButton = {
            TextButton(
                onClick = { viewModel.dismissExitConfirm() },
                modifier = Modifier.tvFocusBorder()
            ) { Text("取消") }
        }
    )
}

// =================================================================
// 频道映射面板
// =================================================================

/**
 * 频道映射面板：远程映射 + 用户映射管理。
 * 与 PC 端 mapping_manager_dialog.py 对齐：
 * - 列表展示映射条目（标准名 ← 原始名 + 分组/Logo/tvg-id 等）
 * - 搜索过滤（标准名 / 原始名 / 分组）
 * - 添加用户映射 / 删除 / 刷新远程缓存
 *
 * 约束（项目记忆）：不得显示"远程URL：未配置"
 */
@Composable
fun MappingPanel(viewModel: AppViewModel) {
    val mappingList by viewModel.mappingList.collectAsState()
    val mappingLoading by viewModel.mappingLoading.collectAsState()
    val statusText by viewModel.mappingStatusText.collectAsState()
    var searchQuery by remember { mutableStateOf("") }
    var showAddDialog by remember { mutableStateOf(false) }

    PanelScaffold(
        title = "频道映射",
        subtitle = "远程映射 + 用户映射管理",
        onClose = { viewModel.toggleMappingPanel() },
        actions = {
            OutlinedButton(
                onClick = { viewModel.refreshMappings() },
                enabled = !mappingLoading,
                modifier = Modifier.tvFocusBorder()
            ) {
                Text("刷新远程", color = Color.White, fontSize = 12.sp)
            }
            Spacer(modifier = Modifier.width(8.dp))
            OutlinedButton(
                onClick = { showAddDialog = true },
                modifier = Modifier.tvFocusBorder()
            ) {
                Text("添加", color = Color.White, fontSize = 12.sp)
            }
        }
    ) {
        Text(text = statusText, color = Color(0xFF888888), fontSize = 12.sp)

        OutlinedTextField(
            value = searchQuery,
            onValueChange = { searchQuery = it },
            label = { Text("搜索（标准名 / 原始名 / 分组）") },
            modifier = Modifier.fillMaxWidth().padding(vertical = 8.dp),
            singleLine = true
        )

        if (mappingLoading) {
            Box(
                modifier = Modifier.fillMaxWidth().padding(32.dp),
                contentAlignment = Alignment.Center
            ) {
                CircularProgressIndicator(color = Color(0xFF4A9EFF))
            }
        } else {
            val filtered = if (searchQuery.isBlank()) {
                mappingList
            } else {
                mappingList.filter { entry ->
                    entry.standardName.contains(searchQuery, ignoreCase = true) ||
                    entry.rawName.contains(searchQuery, ignoreCase = true) ||
                    (entry.groupName?.contains(searchQuery, ignoreCase = true) ?: false)
                }
            }
            DescText("共 ${filtered.size} 条${if (searchQuery.isNotBlank()) "（已过滤）" else ""}")
            LazyColumn(
                modifier = Modifier.fillMaxWidth().heightIn(max = 500.dp)
            ) {
                items(filtered) { entry ->
                    MappingEntryRow(
                        entry = entry,
                        onDelete = { viewModel.deleteMapping(entry.standardName, entry.rawName) }
                    )
                }
            }
        }
    }

    if (showAddDialog) {
        AddMappingDialog(
            onDismiss = { showAddDialog = false },
            onAdd = { raw, std, logo, group ->
                viewModel.addMapping(raw, std, logo, group)
                showAddDialog = false
            }
        )
    }
}

@Composable
private fun MappingEntryRow(
    entry: MappingEntry,
    onDelete: () -> Unit
) {
    Surface(
        color = Color(0xFF1E1E1E),
        shape = RoundedCornerShape(8.dp),
        modifier = Modifier.fillMaxWidth().padding(vertical = 3.dp)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(10.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = entry.standardName,
                    color = Color.White,
                    fontSize = 13.sp,
                    fontWeight = FontWeight.Medium,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
                Text(
                    text = "← ${entry.rawName}",
                    color = Color(0xFF888888),
                    fontSize = 11.sp,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
                val extras = listOfNotNull(
                    entry.groupName?.takeIf { it.isNotBlank() }?.let { "分组: $it" },
                    entry.tvgId?.takeIf { it.isNotBlank() }?.let { "tvg-id: $it" }
                ).joinToString("  |  ")
                if (extras.isNotEmpty()) {
                    Text(text = extras, color = Color(0xFF666666), fontSize = 10.sp, maxLines = 1)
                }
            }
            IconButton(onClick = onDelete, modifier = Modifier.size(32.dp).tvFocusBorder()) {
                Icon(Icons.Default.Close, contentDescription = "删除", tint = Color(0xFFE57373), modifier = Modifier.size(16.dp))
            }
        }
    }
}

@Composable
private fun AddMappingDialog(
    onDismiss: () -> Unit,
    onAdd: (rawName: String, standardName: String, logoUrl: String, groupName: String) -> Unit
) {
    var rawName by remember { mutableStateOf("") }
    var standardName by remember { mutableStateOf("") }
    var logoUrl by remember { mutableStateOf("") }
    var groupName by remember { mutableStateOf("") }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("添加用户映射") },
        text = {
            Column {
                OutlinedTextField(
                    value = rawName, onValueChange = { rawName = it },
                    label = { Text("原始频道名") },
                    modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp),
                    singleLine = true
                )
                OutlinedTextField(
                    value = standardName, onValueChange = { standardName = it },
                    label = { Text("标准频道名") },
                    modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp),
                    singleLine = true
                )
                OutlinedTextField(
                    value = logoUrl, onValueChange = { logoUrl = it },
                    label = { Text("Logo URL（可选）") },
                    modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp),
                    singleLine = true
                )
                OutlinedTextField(
                    value = groupName, onValueChange = { groupName = it },
                    label = { Text("分组名（可选）") },
                    modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp),
                    singleLine = true
                )
            }
        },
        confirmButton = {
            TextButton(
                onClick = { onAdd(rawName, standardName, logoUrl, groupName) },
                enabled = rawName.isNotBlank() && standardName.isNotBlank(),
                modifier = Modifier.tvFocusBorder()
            ) { Text("添加") }
        },
        dismissButton = {
            TextButton(
                onClick = onDismiss,
                modifier = Modifier.tvFocusBorder()
            ) { Text("取消") }
        }
    )
}

// =================================================================
// A/V 同步监控面板
// =================================================================

/**
 * A/V 同步监控面板：实时显示 avdiff / audio-pts / video-pts / audio-delay，
 * 波形图可视化历史趋势，音频延迟调整，字幕自动同步。
 * 与 PC 端 av_sync_dialog.py 对齐。
 *
 * 仅 MPV 播放器支持（其他播放器属性返回 null，显示 N/A）。
 */
@Composable
fun AvSyncPanel(viewModel: AppViewModel) {
    val avDiff by viewModel.avDiff.collectAsState()
    val audioPts by viewModel.audioPts.collectAsState()
    val videoPts by viewModel.videoPts.collectAsState()
    val audioDelay by viewModel.currentAudioDelay.collectAsState()
    val history by viewModel.avDiffHistory.collectAsState()
    val subSyncEnabled by viewModel.subSyncEnabled.collectAsState()
    val capabilities by viewModel.playerCapabilities.collectAsState()

    PanelScaffold(
        title = "A/V 同步监控",
        subtitle = "实时波形 / 音视频差值",
        onClose = { viewModel.toggleAvSyncPanel() }
    ) {
        SectionLabel("实时数值")
        InfoRow("avdiff", "%.4f s".format(avDiff))
        InfoRow("audio-pts", "%.3f s".format(audioPts))
        InfoRow("video-pts", "%.3f s".format(videoPts))
        InfoRow("audio-delay", "%.3f s".format(audioDelay))

        // avdiff 状态指示
        val diffAbs = kotlin.math.abs(avDiff)
        val diffColor = when {
            diffAbs < 0.04 -> Color(0xFF4CAF50)  // 绿色：正常
            diffAbs < 0.2 -> Color(0xFFFFC107)   // 黄色：轻微偏差
            else -> Color(0xFFF44336)            // 红色：严重偏差
        }
        Row(
            modifier = Modifier.fillMaxWidth().padding(top = 4.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text("同步状态", color = Color(0xFF888888), fontSize = 13.sp)
            Text(
                text = when {
                    diffAbs < 0.04 -> "良好"
                    diffAbs < 0.2 -> "轻微偏差"
                    else -> "严重偏差"
                },
                color = diffColor,
                fontSize = 13.sp,
                fontWeight = FontWeight.Medium
            )
        }

        SectionLabel("历史趋势波形")
        DescText("绿<0.04s  黄<0.2s  红≥0.2s（最近 200 采样点）")
        AvSyncWaveform(history = history, modifier = Modifier.fillMaxWidth().height(120.dp))

        if (capabilities.supportsAudioDelay) {
            SectionLabel("音频延迟调整")
            LabeledSlider(
                label = "音频延迟",
                value = audioDelay.toFloat(),
                range = -10f..10f,
                valueText = "%.3fs".format(audioDelay),
                onValueChange = { viewModel.adjustAudioDelay(it.toDouble() - audioDelay) },
                onReset = { viewModel.resetAudioDelay() }
            )
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                OutlinedButton(onClick = { viewModel.adjustAudioDelay(-0.1) }, modifier = Modifier.weight(1f).tvFocusBorder()) {
                    Text("-0.1s", color = Color.White)
                }
                OutlinedButton(onClick = { viewModel.adjustAudioDelay(0.1) }, modifier = Modifier.weight(1f).tvFocusBorder()) {
                    Text("+0.1s", color = Color.White)
                }
                OutlinedButton(onClick = { viewModel.resetAudioDelay() }, modifier = Modifier.weight(1f).tvFocusBorder()) {
                    Text("重置", color = Color.White)
                }
            }
        } else {
            SectionLabel("音频延迟调整")
            DescText("当前播放器不支持音频延迟调整（仅 MPV 支持）")
        }

        SectionLabel("字幕自动同步")
        DescText("基于 avdiff 比例控制算法：每 500ms 采样，超阈值(0.05s)时按 gain(0.30) 调整 sub_delay")
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text("启用自动同步", color = Color.White, fontSize = 13.sp)
            Switch(
                checked = subSyncEnabled,
                onCheckedChange = { viewModel.toggleSubSync() },
                modifier = Modifier.tvFocusBorder()
            )
        }
    }
}

/**
 * A/V 同步波形图：自绘 Canvas，中线为 avdiff=0，
 * 颜色随偏差变化（绿/黄/红），自适应范围。
 * 与 PC 端 AVSyncWaveWidget.paintEvent 对齐。
 */
@Composable
private fun AvSyncWaveform(
    history: List<Float>,
    modifier: Modifier = Modifier
) {
    Surface(
        color = Color(0xFF1A1A1A),
        shape = RoundedCornerShape(8.dp),
        modifier = modifier
    ) {
        Canvas(modifier = Modifier.fillMaxSize().padding(4.dp)) {
            val w = size.width
            val h = size.height
            val midY = h / 2f
            // 中线
            drawLine(
                color = Color(0xFF444444),
                start = Offset(0f, midY),
                end = Offset(w, midY),
                strokeWidth = 1f
            )
            if (history.size < 2) return@Canvas
            // 自适应范围：取历史数据最大绝对值的 1.5 倍，最小 0.1
            val maxAbs = history.maxOfOrNull { kotlin.math.abs(it) } ?: 0.1f
            val range = (maxAbs * 1.5f).coerceAtLeast(0.1f)
            val stepX = w / (history.size - 1).coerceAtLeast(1)
            // 绘制波形
            val path = Path()
            history.forEachIndexed { i, value ->
                val x = i * stepX
                val y = midY - (value / range).coerceIn(-1f, 1f) * (h / 2f)
                if (i == 0) path.moveTo(x, y) else path.lineTo(x, y)
            }
            drawPath(
                path = path,
                color = Color(0xFF4A9EFF),
                style = androidx.compose.ui.graphics.drawscope.Stroke(width = 2f)
            )
            // 最新的点
            val lastVal = history.last()
            val lastColor = when {
                kotlin.math.abs(lastVal) < 0.04f -> Color(0xFF4CAF50)
                kotlin.math.abs(lastVal) < 0.2f -> Color(0xFFFFC107)
                else -> Color(0xFFF44336)
            }
            drawCircle(
                color = lastColor,
                radius = 4f,
                center = Offset((history.size - 1) * stepX, midY - (lastVal / range).coerceIn(-1f, 1f) * (h / 2f))
            )
        }
    }
}

// =================================================================
// 网络增强面板
// =================================================================

/**
 * 网络增强面板：HTTP Referer / Proxy / Headers 设置。
 * 与 PC 端 network_enhance_dialog.py 对齐。
 *
 * 仅 MPV 播放器支持（通过 setPropertyString 下发到 mpv）。
 * 注意：设置在下次 loadfile 时生效，当前播放不会立即应用。
 */
@Composable
fun NetworkPanel(viewModel: AppViewModel) {
    val (initReferer, initProxy, initHeaders) = remember { viewModel.loadNetworkSettings() }
    var referer by remember { mutableStateOf(initReferer) }
    var proxy by remember { mutableStateOf(initProxy) }
    var headers by remember { mutableStateOf(initHeaders) }

    PanelScaffold(
        title = "网络增强",
        subtitle = "Referer / Proxy / Headers（仅 MPV 支持）",
        onClose = { viewModel.toggleNetworkPanel() }
    ) {
        SectionLabel("HTTP Referer")
        DescText("用于绕过防盗链（mpv referrer 属性）")
        OutlinedTextField(
            value = referer, onValueChange = { referer = it },
            label = { Text("如 https://example.com/") },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true
        )

        SectionLabel("HTTP/HTTPS 代理")
        DescText("支持 http:// / https:// / socks5:// / socks5h://（mpv http-proxy 属性）")
        OutlinedTextField(
            value = proxy, onValueChange = { proxy = it },
            label = { Text("如 socks5://127.0.0.1:1080") },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true
        )

        SectionLabel("HTTP Headers")
        DescText("每行一个，格式 Key: Value（mpv http-header-fields 属性）")
        OutlinedTextField(
            value = headers, onValueChange = { headers = it },
            label = { Text("User-Agent: Mozilla/5.0\nAuthorization: Bearer xxx") },
            modifier = Modifier.fillMaxWidth().heightIn(min = 80.dp),
            maxLines = 5
        )

        Spacer(modifier = Modifier.height(16.dp))
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            OutlinedButton(
                onClick = {
                    referer = ""; proxy = ""; headers = ""
                    viewModel.clearNetworkSettings()
                },
                modifier = Modifier.weight(1f).tvFocusBorder()
            ) { Text("清除", color = Color.White) }

            OutlinedButton(
                onClick = { viewModel.applyNetworkSettings(referer, proxy, headers) },
                modifier = Modifier.weight(1f).tvFocusBorder()
            ) { Text("应用", color = Color.White) }

            OutlinedButton(
                onClick = { viewModel.saveNetworkSettings(referer, proxy, headers) },
                modifier = Modifier.weight(1f).tvFocusBorder()
            ) { Text("保存", color = Color(0xFF4A9EFF)) }
        }

        Spacer(modifier = Modifier.height(8.dp))
        DescText("注意：设置在下次加载流时生效，当前播放不会立即应用。")
    }
}

// =================================================================
// 工具面板
// =================================================================

/**
 * 工具面板：工具入口列表，与 PC 端"工具"菜单组对齐。
 * 点击各工具项跳转到对应面板或显示 OSD 提示。
 */
@Composable
fun ToolsPanel(viewModel: AppViewModel) {
    PanelScaffold(
        title = "工具",
        subtitle = "搜索 / EPG时间线 / 提醒 / 续播 / 书签 / 映射 / 扫描 / 流质量",
        onClose = { viewModel.toggleToolsPanel() },
        scrollable = false
    ) {
        val tools = listOf(
            ToolEntry("搜索", "全局搜索频道和节目", Icons.Default.Search) {
                viewModel.toggleToolsPanel()
                viewModel.toggleSearchPanel()
            },
            ToolEntry("EPG 时间线", "节目时间线视图", Icons.Default.CalendarMonth) {
                viewModel.toggleToolsPanel()
                viewModel.toggleEpgTimelinePanel()
            },
            ToolEntry("提醒管理", "节目提醒列表", Icons.Default.Notifications) {
                viewModel.toggleToolsPanel()
                viewModel.toggleReminderPanel()
            },
            ToolEntry("续播位置", "本地视频/点播断点续播", Icons.Default.History) {
                viewModel.toggleToolsPanel()
                viewModel.toggleResumePanel()
            },
            ToolEntry("书签管理", "播放位置书签（增删查/跳转）", Icons.Default.Bookmark) {
                viewModel.toggleToolsPanel()
                viewModel.toggleBookmarkPanel()
            },
            ToolEntry("频道映射", "远程映射 + 用户映射管理", Icons.Default.SyncAlt) {
                viewModel.toggleToolsPanel()
                viewModel.toggleMappingPanel()
            },
            ToolEntry("扫描整理", "URL 范围扫描（StandaloneScanner）", Icons.Default.Radar) {
                viewModel.toggleToolsPanel()
                viewModel.toggleScanPanel()
            },
            ToolEntry("流质量检测", "码率 / 分辨率 / 编解码器", Icons.Default.Analytics) {
                viewModel.toggleToolsPanel()
                viewModel.toggleStreamQualityPanel()
            }
        )
        LazyColumn(modifier = Modifier.fillMaxWidth()) {
            items(tools) { tool ->
                ToolEntryRow(tool)
                HorizontalDivider(color = Color(0xFF2A2A2A))
            }
        }
    }
}

private data class ToolEntry(
    val title: String,
    val desc: String,
    val icon: androidx.compose.ui.graphics.vector.ImageVector,
    val onClick: () -> Unit
)

@Composable
private fun ToolEntryRow(tool: ToolEntry) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable { tool.onClick() }
            .tvFocusBorder()
            .padding(vertical = 12.dp, horizontal = 4.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Icon(
            imageVector = tool.icon,
            contentDescription = tool.title,
            tint = Color(0xFF4A9EFF),
            modifier = Modifier.size(28.dp)
        )
        Spacer(modifier = Modifier.width(12.dp))
        Column(modifier = Modifier.weight(1f)) {
            Text(text = tool.title, color = Color.White, fontSize = 14.sp, fontWeight = FontWeight.Medium)
            Text(text = tool.desc, color = Color(0xFF888888), fontSize = 12.sp)
        }
    }
}

// -----------------------------------------------------------------
// 字幕在线搜索面板
// 与 PC 端 subtitle_download_service.py 对齐：SubHD / SubtitleCat / OpenSubtitles 三源
// -----------------------------------------------------------------

@Composable
fun SubtitleSearchPanel(viewModel: AppViewModel) {
    val searching by viewModel.subtitleSearching.collectAsState()
    val results by viewModel.subtitleSearchResults.collectAsState()
    val error by viewModel.subtitleSearchError.collectAsState()
    val downloading by viewModel.subtitleDownloading.collectAsState()

    var query by remember { mutableStateOf("") }
    var selectedLang by remember { mutableStateOf("all") }

    val languages = listOf(
        "all" to "全部",
        "chi" to "中文",
        "eng" to "英语",
        "jpn" to "日语",
        "kor" to "韩语"
    )

    PanelScaffold(
        title = "字幕搜索",
        subtitle = "SubHD / SubtitleCat / OpenSubtitles",
        onClose = { viewModel.toggleSubtitleSearchPanel() },
        scrollable = false
    ) {
        // 搜索框
        OutlinedTextField(
            value = query,
            onValueChange = { query = it },
            placeholder = { Text("输入片名或关键词...", color = Color(0xFF888888), fontSize = 13.sp) },
            trailingIcon = {
                if (query.isNotEmpty()) {
                    IconButton(
                        onClick = { query = "" },
                        modifier = Modifier.tvFocusBorder()
                    ) {
                        Icon(Icons.Default.Close, contentDescription = "清空", tint = Color(0xFF888888))
                    }
                }
            },
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 12.dp, vertical = 6.dp),
            shape = RoundedCornerShape(8.dp),
            singleLine = true
        )

        // 语言选择
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 12.dp, vertical = 4.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            languages.forEach { (code, label) ->
                FilterChip(
                    selected = selectedLang == code,
                    onClick = { selectedLang = code },
                    label = { Text(label, fontSize = 12.sp) },
                    colors = androidx.compose.material3.FilterChipDefaults.filterChipColors(
                        selectedContainerColor = Color(0xFF4A9EFF),
                        selectedLabelColor = Color.White
                    ),
                    modifier = Modifier.tvFocusBorder()
                )
            }
        }

        // 搜索按钮
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 12.dp, vertical = 4.dp),
            contentAlignment = Alignment.Center
        ) {
            if (searching) {
                CircularProgressIndicator(
                    color = Color(0xFF4A9EFF),
                    modifier = Modifier.size(24.dp)
                )
            } else {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(8.dp))
                        .background(Color(0xFF4A9EFF))
                        .clickable { viewModel.searchSubtitles(query, selectedLang) }
                        .tvFocusBorder()
                        .padding(vertical = 10.dp),
                    horizontalArrangement = Arrangement.Center,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Icon(Icons.Default.Search, contentDescription = null, tint = Color.White, modifier = Modifier.size(18.dp))
                    Spacer(modifier = Modifier.width(6.dp))
                    Text("搜索", color = Color.White, fontSize = 14.sp, fontWeight = FontWeight.Medium)
                }
            }
        }

        // 错误提示
        if (error.isNotEmpty() && results.isEmpty() && !searching) {
            Text(
                text = error,
                color = Color(0xFFE57373),
                fontSize = 12.sp,
                modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp)
            )
        }

        // 搜索结果
        if (results.isNotEmpty()) {
            LazyColumn(
                modifier = Modifier.fillMaxWidth(),
                contentPadding = androidx.compose.foundation.layout.PaddingValues(vertical = 4.dp)
            ) {
                items(items = results, key = { it.source + "_" + it.id + "_" + it.fileName }) { item ->
                    SubtitleResultRow(
                        item = item,
                        downloading = downloading,
                        onDownload = { viewModel.downloadAndLoadSubtitle(item) },
                        onOpenInBrowser = { url ->
                            val intent = Intent(Intent.ACTION_VIEW, Uri.parse(url))
                            intent.flags = Intent.FLAG_ACTIVITY_NEW_TASK
                            try {
                                viewModel.getApplication<android.app.Application>().startActivity(intent)
                            } catch (e: Exception) {
                                viewModel.showOsd("字幕搜索", "无法打开浏览器")
                            }
                        }
                    )
                    HorizontalDivider(color = Color(0xFF2A2A2A))
                }
            }
        } else if (!searching && query.isNotEmpty() && error.isEmpty()) {
            Box(
                modifier = Modifier.fillMaxSize(),
                contentAlignment = Alignment.Center
            ) {
                Text("点击搜索按钮开始查找", color = Color(0xFF888888), fontSize = 13.sp)
            }
        }
    }
}

@Composable
private fun SubtitleResultRow(
    item: SubtitleItem,
    downloading: Boolean,
    onDownload: () -> Unit,
    onOpenInBrowser: (String) -> Unit
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 12.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Column(modifier = Modifier.weight(1f)) {
            // 第一行：文件名
            Text(
                text = item.fileName.ifBlank { item.title },
                color = Color.White,
                fontSize = 13.sp,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis
            )
            // 第二行：来源 + 语言 + 评分
            Row(
                modifier = Modifier.padding(top = 2.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                SourceBadge(item.source)
                if (item.language.isNotEmpty()) {
                    Text(item.language, color = Color(0xFF888888), fontSize = 11.sp)
                }
                if (item.score > 0) {
                    Text("★ ${item.score}", color = Color(0xFFAAAAAA), fontSize = 11.sp)
                }
            }
        }

        Spacer(modifier = Modifier.width(8.dp))

        // 操作按钮
        if (downloading) {
            CircularProgressIndicator(
                color = Color(0xFF4A9EFF),
                modifier = Modifier.size(20.dp)
            )
        } else if (item.autoDownload) {
            // 可自动下载（OpenSubtitles / SubtitleCat）
            TextButton(
                onClick = onDownload,
                modifier = Modifier.tvFocusBorder()
            ) {
                Text("下载", color = Color(0xFF4A9EFF), fontSize = 12.sp)
            }
        } else {
            // 需浏览器打开（SubHD）
            TextButton(
                onClick = { onOpenInBrowser(item.detailUrl.ifBlank { item.downloadLink }) },
                modifier = Modifier.tvFocusBorder()
            ) {
                Text("浏览器", color = Color(0xFFFF9800), fontSize = 12.sp)
            }
        }
    }
}

@Composable
private fun SourceBadge(source: String) {
    val color = when (source) {
        "OpenSubtitles" -> Color(0xFF4CAF50)
        "SubHD" -> Color(0xFF2196F3)
        "SubtitleCat" -> Color(0xFFFF9800)
        else -> Color(0xFF888888)
    }
    Surface(
        color = color.copy(alpha = 0.2f),
        shape = RoundedCornerShape(3.dp)
    ) {
        Text(
            text = source,
            color = color,
            fontSize = 10.sp,
            modifier = Modifier.padding(horizontal = 4.dp, vertical = 1.dp)
        )
    }
}

// -----------------------------------------------------------------
// URL 范围扫描面板
// -----------------------------------------------------------------

/**
 * URL 范围扫描面板：与 PC 端扫描功能对齐，后端为 StandaloneScanner。
 *
 * 功能：
 * - 输入基础 URL（支持 [1-255] 范围表达式）
 * - 调整超时和线程数
 * - 实时显示扫描进度（已扫描/有效/无效）
 * - 显示扫描结果列表
 *
 * 扫描完成后，有效频道会自动追加到频道列表（分组"扫描结果"），由后端 StandaloneScanner 处理。
 */
@Composable
fun ScanPanel(viewModel: AppViewModel) {
    val scanStatus by viewModel.scanStatus.collectAsState()
    val scanResults by viewModel.scanResults.collectAsState()
    val scanLoading by viewModel.scanLoading.collectAsState()
    val scanError by viewModel.scanError.collectAsState()

    var baseUrl by remember { mutableStateOf("http://192.168.1.[1-255]:8080") }
    var timeout by remember { mutableStateOf(10) }
    var threads by remember { mutableStateOf(4) }

    val running = scanStatus?.running == true

    PanelScaffold(
        title = "URL 范围扫描",
        subtitle = "扫描 IP 范围内的 IPTV 服务（支持 [1-255] 表达式）",
        onClose = { viewModel.toggleScanPanel() }
    ) {
        // 参数表单
        SectionLabel("扫描参数")
        OutlinedTextField(
            value = baseUrl,
            onValueChange = { baseUrl = it },
            label = { Text("基础 URL") },
            placeholder = { Text("http://192.168.1.[1-255]:8080") },
            singleLine = true,
            enabled = !running,
            modifier = Modifier.fillMaxWidth()
        )
        DescText("支持 [1-255] 范围表达式，扫描该范围内所有 IP 的指定端口")

        Row(
            modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp),
            horizontalArrangement = Arrangement.spacedBy(12.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text("超时: ${timeout}s", color = Color.White, fontSize = 13.sp)
                Slider(
                    value = timeout.toFloat(),
                    onValueChange = { timeout = it.toInt().coerceIn(3, 30) },
                    valueRange = 3f..30f,
                    enabled = !running,
                    modifier = Modifier.fillMaxWidth().tvFocusBorder(),
                    colors = SliderDefaults.colors(
                        thumbColor = Color(0xFF4A9EFF),
                        activeTrackColor = Color(0xFF4A9EFF),
                        inactiveTrackColor = Color(0xFF444444)
                    )
                )
            }
            Column(modifier = Modifier.weight(1f)) {
                Text("线程: ${threads}", color = Color.White, fontSize = 13.sp)
                Slider(
                    value = threads.toFloat(),
                    onValueChange = { threads = it.toInt().coerceIn(1, 16) },
                    valueRange = 1f..16f,
                    enabled = !running,
                    modifier = Modifier.fillMaxWidth().tvFocusBorder(),
                    colors = SliderDefaults.colors(
                        thumbColor = Color(0xFF4A9EFF),
                        activeTrackColor = Color(0xFF4A9EFF),
                        inactiveTrackColor = Color(0xFF444444)
                    )
                )
            }
        }

        // 控制按钮
        Row(
            modifier = Modifier.fillMaxWidth().padding(vertical = 8.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            if (running) {
                OutlinedButton(
                    onClick = { viewModel.stopScan() },
                    modifier = Modifier.tvFocusBorder()
                ) {
                    Icon(Icons.Default.Close, contentDescription = null, tint = Color(0xFFFF5252))
                    Spacer(modifier = Modifier.width(4.dp))
                    Text("停止扫描", color = Color(0xFFFF5252))
                }
            } else {
                OutlinedButton(
                    onClick = { viewModel.startScan(baseUrl.trim(), timeout, threads) },
                    enabled = !scanLoading,
                    modifier = Modifier.tvFocusBorder()
                ) {
                    if (scanLoading) {
                        CircularProgressIndicator(
                            color = Color(0xFF4A9EFF),
                            modifier = Modifier.size(16.dp)
                        )
                    } else {
                        Icon(Icons.Default.Radar, contentDescription = null, tint = Color(0xFF4A9EFF))
                        Spacer(modifier = Modifier.width(4.dp))
                        Text("开始扫描", color = Color(0xFF4A9EFF))
                    }
                }
            }
        }

        // 错误提示
        if (scanError.isNotEmpty()) {
            Text(
                text = scanError,
                color = Color(0xFFFF5252),
                fontSize = 12.sp,
                modifier = Modifier.padding(vertical = 4.dp)
            )
        }

        // 进度
        scanStatus?.let { status ->
            SectionLabel("进度")
            val progress = if (status.total > 0) {
                status.scanned.toFloat() / status.total
            } else 0f
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Text("已扫描: ${status.scanned}/${status.total}", color = Color.White, fontSize = 13.sp)
                Text("有效: ${status.valid}", color = Color(0xFF4CAF50), fontSize = 13.sp)
                Text("无效: ${status.invalid}", color = Color(0xFFFF5252), fontSize = 13.sp)
            }
            LinearProgressIndicator(
                progress = { progress },
                modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp),
                color = Color(0xFF4A9EFF),
                trackColor = Color(0xFF333333)
            )
            if (status.message.isNotEmpty()) {
                Text(status.message, color = Color(0xFF888888), fontSize = 11.sp)
            }
        }

        // 结果列表
        if (scanResults.isNotEmpty()) {
            SectionLabel("扫描结果（${scanResults.size} 条，有效 ${scanResults.count { it.valid }}）")
            LazyColumn(
                modifier = Modifier.fillMaxWidth().heightIn(max = 400.dp)
            ) {
                items(scanResults) { result ->
                    ScanResultRow(result)
                    HorizontalDivider(color = Color(0xFF2A2A2A))
                }
            }
        }
    }
}

@Composable
private fun ScanResultRow(result: ScanResult) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 12.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = result.name.ifBlank { result.url },
                color = Color.White,
                fontSize = 13.sp,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis
            )
            Row(
                modifier = Modifier.padding(top = 2.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Surface(
                    color = if (result.valid) Color(0xFF4CAF50).copy(alpha = 0.2f)
                            else Color(0xFFFF5252).copy(alpha = 0.2f),
                    shape = RoundedCornerShape(3.dp)
                ) {
                    Text(
                        text = if (result.valid) "有效" else "无效",
                        color = if (result.valid) Color(0xFF4CAF50) else Color(0xFFFF5252),
                        fontSize = 10.sp,
                        modifier = Modifier.padding(horizontal = 4.dp, vertical = 1.dp)
                    )
                }
                if (result.latency > 0) {
                    Text("${result.latency}ms", color = Color(0xFF888888), fontSize = 11.sp)
                }
                if (result.group.isNotEmpty()) {
                    Text(result.group, color = Color(0xFF888888), fontSize = 11.sp)
                }
            }
            Text(
                text = result.url,
                color = Color(0xFF888888),
                fontSize = 11.sp,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
                modifier = Modifier.padding(top = 2.dp)
            )
        }
    }
}

// -----------------------------------------------------------------
// 节目提醒管理面板（与 PC 端 ui/dialogs/reminder_manager_dialog.py 对齐）
// -----------------------------------------------------------------

/**
 * 提醒管理面板：列出所有已设置的节目提醒，支持删除/清空。
 *
 * - 顶部显示总数和清空按钮
 * - 列表项显示频道名 / 节目标题 / 开始时间 / 倒计时
 * - 即将开始（<5 分钟）的提醒高亮显示
 * - 空列表显示占位提示
 */
@Composable
fun ReminderPanel(viewModel: AppViewModel) {
    val reminders by viewModel.reminders.collectAsState()
    val now = System.currentTimeMillis()
    val timeFmt = remember { SimpleDateFormat("MM-dd HH:mm", Locale.getDefault()) }

    PanelScaffold(
        title = "节目提醒",
        subtitle = "已设置 ${reminders.size} 条提醒",
        onClose = { viewModel.toggleReminderPanel() },
        actions = {
            if (reminders.isNotEmpty()) {
                OutlinedButton(
                    onClick = { viewModel.clearReminders() },
                    modifier = Modifier.tvFocusBorder()
                ) {
                    Icon(Icons.Default.Close, contentDescription = null, tint = Color(0xFFFF5252))
                    Spacer(modifier = Modifier.width(4.dp))
                    Text("清空", color = Color(0xFFFF5252))
                }
            }
        }
    ) {
        if (reminders.isEmpty()) {
            Box(
                modifier = Modifier.fillMaxWidth().padding(top = 60.dp),
                contentAlignment = Alignment.Center
            ) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Icon(
                        Icons.Default.Notifications,
                        contentDescription = null,
                        tint = Color(0xFF555555),
                        modifier = Modifier.size(48.dp)
                    )
                    Spacer(modifier = Modifier.height(8.dp))
                    Text("暂无节目提醒", color = Color(0xFF666666), fontSize = 13.sp)
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        "在节目单中点击当前或未来节目可设置提醒",
                        color = Color(0xFF555555),
                        fontSize = 11.sp
                    )
                }
            }
            return@PanelScaffold
        }

        // 按开始时间升序排序
        val sorted = remember(reminders) { reminders.sortedBy { it.startTs } }

        SectionLabel("提醒列表")
        LazyColumn(
            modifier = Modifier.fillMaxWidth().heightIn(max = 500.dp)
        ) {
            items(sorted, key = { it.id }) { item ->
                ReminderRow(
                    item = item,
                    now = now,
                    timeFmt = timeFmt,
                    onDelete = { viewModel.removeReminder(item.id) }
                )
                HorizontalDivider(color = Color(0xFF2A2A2A))
            }
        }
    }
}

@Composable
private fun ReminderRow(
    item: ReminderItem,
    now: Long,
    timeFmt: SimpleDateFormat,
    onDelete: () -> Unit
) {
    val remainingMs = item.startTs - now
    val isUpcoming = remainingMs in 0..5 * 60 * 1000L  // 5 分钟内即将开始
    val isPast = remainingMs < 0  // 已开始（但未结束）

    val titleColor = when {
        isUpcoming -> Color(0xFFFFC107)  // 黄色高亮
        isPast -> Color(0xFF888888)
        else -> Color.White
    }

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 12.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Column(modifier = Modifier.weight(1f)) {
            // 节目标题
            Text(
                text = item.programTitle.ifBlank { "（未命名节目）" },
                color = titleColor,
                fontSize = 14.sp,
                fontWeight = if (isUpcoming) FontWeight.Medium else FontWeight.Normal,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis
            )
            // 频道名
            if (item.channelName.isNotEmpty()) {
                Text(
                    text = item.channelName,
                    color = Color(0xFFAAAAAA),
                    fontSize = 12.sp,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.padding(top = 2.dp)
                )
            }
            // 时间 + 倒计时
            Row(
                modifier = Modifier.padding(top = 3.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = timeFmt.format(Date(item.startTs)),
                    color = Color(0xFF888888),
                    fontSize = 11.sp
                )
                val remainingText = when {
                    remainingMs > 0 -> {
                        val min = remainingMs / 60_000
                        if (min > 0) "${min}分钟后" else "即将开始"
                    }
                    remainingMs > -60 * 60 * 1000L -> "已开始"  // 1 小时内
                    else -> "已过期"
                }
                val remainingColor = when {
                    isUpcoming -> Color(0xFFFFC107)
                    isPast -> Color(0xFF888888)
                    else -> Color(0xFF4A9EFF)
                }
                Text(remainingText, color = remainingColor, fontSize = 11.sp)
            }
        }
        IconButton(onClick = onDelete, modifier = Modifier.size(32.dp).tvFocusBorder()) {
            Icon(
                Icons.Default.Close,
                contentDescription = "删除",
                tint = Color(0xFFE57373),
                modifier = Modifier.size(16.dp)
            )
        }
    }
}

// -----------------------------------------------------------------
// 续播位置管理面板（与 PC 端 ui/dialogs/resume_position_dialog.py 对齐）
// -----------------------------------------------------------------

/**
 * 续播位置面板：列出所有已保存的播放断点，支持恢复/删除/清空。
 *
 * - 顶部显示总数和清空按钮
 * - 列表项显示名称 + 位置/时长 + 更新时间
 * - 点击"恢复"调用 playResume 切换并 seek
 * - 空列表显示占位提示
 */
@Composable
fun ResumePanel(viewModel: AppViewModel) {
    val resumeList by viewModel.resumeList.collectAsState()
    val timeFmt = remember { SimpleDateFormat("MM-dd HH:mm", Locale.getDefault()) }

    PanelScaffold(
        title = "续播位置",
        subtitle = "已保存 ${resumeList.size} 条断点",
        onClose = { viewModel.toggleResumePanel() },
        actions = {
            if (resumeList.isNotEmpty()) {
                OutlinedButton(
                    onClick = { viewModel.clearResumeList() },
                    modifier = Modifier.tvFocusBorder()
                ) {
                    Icon(Icons.Default.Close, contentDescription = null, tint = Color(0xFFFF5252))
                    Spacer(modifier = Modifier.width(4.dp))
                    Text("清空", color = Color(0xFFFF5252))
                }
            }
        }
    ) {
        if (resumeList.isEmpty()) {
            Box(
                modifier = Modifier.fillMaxWidth().padding(top = 60.dp),
                contentAlignment = Alignment.Center
            ) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Icon(
                        Icons.Default.History,
                        contentDescription = null,
                        tint = Color(0xFF555555),
                        modifier = Modifier.size(48.dp)
                    )
                    Spacer(modifier = Modifier.height(8.dp))
                    Text("暂无续播记录", color = Color(0xFF666666), fontSize = 13.sp)
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        "播放本地视频或点播流时自动保存断点",
                        color = Color(0xFF555555),
                        fontSize = 11.sp
                    )
                }
            }
            return@PanelScaffold
        }

        // 按更新时间降序排序（最近观看在前）
        val sorted = remember(resumeList) { resumeList.sortedByDescending { it.updatedAt } }

        SectionLabel("断点列表")
        LazyColumn(
            modifier = Modifier.fillMaxWidth().heightIn(max = 500.dp)
        ) {
            items(sorted, key = { it.id }) { item ->
                ResumeRow(
                    item = item,
                    timeFmt = timeFmt,
                    onPlay = { viewModel.playResume(item) },
                    onDelete = { viewModel.removeResume(item.url) }
                )
                HorizontalDivider(color = Color(0xFF2A2A2A))
            }
        }
    }
}

@Composable
private fun ResumeRow(
    item: ResumeItem,
    timeFmt: SimpleDateFormat,
    onPlay: () -> Unit,
    onDelete: () -> Unit
) {
    // 格式化时长 mm:ss 或 hh:mm:ss
    fun fmt(sec: Long): String {
        if (sec <= 0) return "00:00"
        val h = sec / 3600
        val m = (sec % 3600) / 60
        val s = sec % 60
        return if (h > 0) "%02d:%02d:%02d".format(h, m, s) else "%02d:%02d".format(m, s)
    }

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 12.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Column(modifier = Modifier.weight(1f)) {
            // 名称
            Text(
                text = item.name.ifBlank { item.url },
                color = Color.White,
                fontSize = 14.sp,
                fontWeight = FontWeight.Medium,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis
            )
            // 位置 / 时长
            Row(
                modifier = Modifier.padding(top = 3.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                val progress = if (item.duration > 0) {
                    (item.position.toFloat() / item.duration.toFloat()).coerceIn(0f, 1f)
                } else 0f
                Text(
                    text = "${fmt(item.position)} / ${fmt(item.duration)}",
                    color = Color(0xFF4A9EFF),
                    fontSize = 11.sp
                )
                if (progress > 0) {
                    Text(
                        text = "${(progress * 100).toInt()}%",
                        color = Color(0xFF888888),
                        fontSize = 11.sp
                    )
                }
            }
            // 更新时间 + URL
            Row(
                modifier = Modifier.padding(top = 2.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = timeFmt.format(Date(item.updatedAt)),
                    color = Color(0xFF888888),
                    fontSize = 11.sp
                )
                if (item.channelIdx >= 0) {
                    Surface(
                        color = Color(0xFF4A9EFF).copy(alpha = 0.15f),
                        shape = RoundedCornerShape(3.dp)
                    ) {
                        Text(
                            text = "频道",
                            color = Color(0xFF4A9EFF),
                            fontSize = 10.sp,
                            modifier = Modifier.padding(horizontal = 4.dp, vertical = 1.dp)
                        )
                    }
                } else {
                    Surface(
                        color = Color(0xFF4CAF50).copy(alpha = 0.15f),
                        shape = RoundedCornerShape(3.dp)
                    ) {
                        Text(
                            text = "本地",
                            color = Color(0xFF4CAF50),
                            fontSize = 10.sp,
                            modifier = Modifier.padding(horizontal = 4.dp, vertical = 1.dp)
                        )
                    }
                }
            }
        }
        // 恢复按钮
        OutlinedButton(
            onClick = onPlay,
            modifier = Modifier.tvFocusBorder()
        ) {
            Text("恢复", color = Color(0xFF4A9EFF), fontSize = 12.sp)
        }
        Spacer(modifier = Modifier.width(4.dp))
        IconButton(onClick = onDelete, modifier = Modifier.size(32.dp).tvFocusBorder()) {
            Icon(
                Icons.Default.Close,
                contentDescription = "删除",
                tint = Color(0xFFE57373),
                modifier = Modifier.size(16.dp)
            )
        }
    }
}

// -----------------------------------------------------------------
// 书签管理面板（与 PC 端 ui/dialogs/bookmark_dialog.py 对齐）
// -----------------------------------------------------------------

/**
 * 书签面板：添加/跳转/删除/清空书签。
 *
 * - 顶部：添加书签按钮 + 视图切换（当前文件/所有文件）
 * - 列表：书签项显示名称 + 位置时间 + 创建时间 + 跳转/删除按钮
 * - 底部：清除当前/清除全部
 * - 空列表显示占位提示
 */
@Composable
fun BookmarkPanel(viewModel: AppViewModel) {
    val showCurrent by viewModel.bookmarkShowCurrent.collectAsState()
    val currentBookmarks by viewModel.currentBookmarks.collectAsState()
    val allBookmarks by viewModel.allBookmarks.collectAsState()
    val timeFmt = remember { SimpleDateFormat("MM-dd HH:mm", Locale.getDefault()) }

    val displayList = if (showCurrent) currentBookmarks else allBookmarks

    PanelScaffold(
        title = "书签",
        subtitle = "已保存 ${displayList.size} 条书签",
        onClose = { viewModel.toggleBookmarkPanel() },
        actions = {
            if (displayList.isNotEmpty()) {
                OutlinedButton(
                    onClick = {
                        if (showCurrent) viewModel.clearCurrentBookmarks()
                        else viewModel.clearAllBookmarks()
                    },
                    modifier = Modifier.tvFocusBorder()
                ) {
                    Icon(Icons.Default.Close, contentDescription = null, tint = Color(0xFFFF5252))
                    Spacer(modifier = Modifier.width(4.dp))
                    Text(
                        if (showCurrent) "清除当前" else "清空全部",
                        color = Color(0xFFFF5252)
                    )
                }
            }
        }
    ) {
        // 添加书签按钮
        OutlinedButton(
            onClick = { viewModel.addBookmark() },
            modifier = Modifier.fillMaxWidth().tvFocusBorder()
        ) {
            Icon(Icons.Default.Bookmark, contentDescription = null, tint = Color(0xFF4A9EFF))
            Spacer(modifier = Modifier.width(6.dp))
            Text("在当前位置添加书签", color = Color(0xFF4A9EFF))
        }

        Spacer(modifier = Modifier.height(12.dp))

        // 视图切换
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            FilterChip(
                selected = showCurrent,
                onClick = { viewModel.setBookmarkShowCurrent(true) },
                label = { Text("当前文件 (${currentBookmarks.size})") },
                colors = androidx.compose.material3.FilterChipDefaults.filterChipColors(
                    selectedContainerColor = Color(0xFF4A9EFF).copy(alpha = 0.2f),
                    selectedLabelColor = Color(0xFF4A9EFF)
                ),
                modifier = Modifier.tvFocusBorder()
            )
            FilterChip(
                selected = !showCurrent,
                onClick = { viewModel.setBookmarkShowCurrent(false) },
                label = { Text("所有文件 (${allBookmarks.size})") },
                colors = androidx.compose.material3.FilterChipDefaults.filterChipColors(
                    selectedContainerColor = Color(0xFF4A9EFF).copy(alpha = 0.2f),
                    selectedLabelColor = Color(0xFF4A9EFF)
                ),
                modifier = Modifier.tvFocusBorder()
            )
        }

        Spacer(modifier = Modifier.height(12.dp))

        if (displayList.isEmpty()) {
            Box(
                modifier = Modifier.fillMaxWidth().padding(top = 40.dp),
                contentAlignment = Alignment.Center
            ) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Icon(
                        Icons.Default.Bookmark,
                        contentDescription = null,
                        tint = Color(0xFF555555),
                        modifier = Modifier.size(48.dp)
                    )
                    Spacer(modifier = Modifier.height(8.dp))
                    Text(
                        if (showCurrent) "当前文件暂无书签" else "暂无任何书签",
                        color = Color(0xFF666666),
                        fontSize = 13.sp
                    )
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        "点击上方按钮在当前位置添加书签",
                        color = Color(0xFF555555),
                        fontSize = 11.sp
                    )
                }
            }
            return@PanelScaffold
        }

        SectionLabel("书签列表")
        LazyColumn(
            modifier = Modifier.fillMaxWidth().heightIn(max = 500.dp)
        ) {
            items(displayList, key = { it.id }) { item ->
                BookmarkRow(
                    item = item,
                    timeFmt = timeFmt,
                    onGoto = { viewModel.gotoBookmark(item) },
                    onDelete = { viewModel.deleteBookmark(item) }
                )
                HorizontalDivider(color = Color(0xFF2A2A2A))
            }
        }
    }
}

@Composable
private fun BookmarkRow(
    item: BookmarkItem,
    timeFmt: SimpleDateFormat,
    onGoto: () -> Unit,
    onDelete: () -> Unit
) {
    // 格式化秒为 mm:ss 或 hh:mm:ss
    fun fmt(sec: Long): String {
        if (sec <= 0) return "00:00"
        val h = sec / 3600
        val m = (sec % 3600) / 60
        val s = sec % 60
        return if (h > 0) "%02d:%02d:%02d".format(h, m, s) else "%02d:%02d".format(m, s)
    }

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 12.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Column(modifier = Modifier.weight(1f)) {
            // 名称
            Text(
                text = item.name.ifBlank { "书签 @${fmt(item.position)}" },
                color = Color.White,
                fontSize = 14.sp,
                fontWeight = FontWeight.Medium,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis
            )
            // 位置时间
            Row(
                modifier = Modifier.padding(top = 3.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Surface(
                    color = Color(0xFF4A9EFF).copy(alpha = 0.15f),
                    shape = RoundedCornerShape(3.dp)
                ) {
                    Text(
                        text = fmt(item.position),
                        color = Color(0xFF4A9EFF),
                        fontSize = 11.sp,
                        modifier = Modifier.padding(horizontal = 4.dp, vertical = 1.dp)
                    )
                }
                Text(
                    text = timeFmt.format(Date(item.createdAt)),
                    color = Color(0xFF888888),
                    fontSize = 11.sp
                )
            }
            // URL（所有文件视图下显示）
            if (item.url.isNotEmpty()) {
                Text(
                    text = item.url,
                    color = Color(0xFF666666),
                    fontSize = 10.sp,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.padding(top = 2.dp)
                )
            }
        }
        // 跳转按钮
        OutlinedButton(
            onClick = onGoto,
            modifier = Modifier.tvFocusBorder()
        ) {
            Text("跳转", color = Color(0xFF4A9EFF), fontSize = 12.sp)
        }
        Spacer(modifier = Modifier.width(4.dp))
        IconButton(onClick = onDelete, modifier = Modifier.size(32.dp).tvFocusBorder()) {
            Icon(
                Icons.Default.Close,
                contentDescription = "删除",
                tint = Color(0xFFE57373),
                modifier = Modifier.size(16.dp)
            )
        }
    }
}
