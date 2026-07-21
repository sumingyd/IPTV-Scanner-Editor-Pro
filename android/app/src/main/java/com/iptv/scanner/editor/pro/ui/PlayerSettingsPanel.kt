package com.iptv.scanner.editor.pro.ui

import android.content.res.Configuration
import androidx.compose.foundation.focusable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.systemBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.foundation.focusGroup
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.iptv.scanner.editor.pro.data.UserPrefs
import com.iptv.scanner.editor.pro.player.PlayerType
import com.iptv.scanner.editor.pro.ui.theme.tvFocusBorder

/**
 * 播放器设置面板（全屏覆盖）。
 *
 * 仅 MPV 内核设置（与 PC 端统一）：
 * 1. 视频输出（vo）：gpu / gpu-next / mediacodec_embed
 * 2. 硬件解码（hwdec）：必须与 vo 匹配
 * 3. 反交错、HDR 模式、RTSP 传输协议、日志等级
 *
 * 兜底方案：当黑屏检测不可靠时（如 estimated-vfps 仍有值但渲染黑屏），
 * 用户可手动切换 vo（gpu / gpu-next / mediacodec_embed），立即生效并持久化。
 *
 * - vo：video output，gpu / gpu-next（EGL 渲染）或 mediacodec_embed（MediaCodec 直接渲染）
 * - hwdec：硬件解码，auto-copy / mediacodec / no（必须与 vo 匹配）
 * - 重置：恢复默认值（vo=gpu + hwdec=auto-copy）
 */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun PlayerSettingsPanel(viewModel: AppViewModel) {
    val currentVo by viewModel.currentVo.collectAsState()
    val currentHwdec by viewModel.currentHwdec.collectAsState()
    val currentRtspTransport by viewModel.currentRtspTransport.collectAsState()
    val currentDeinterlace by viewModel.currentDeinterlace.collectAsState()
    val logLevel by viewModel.logLevel.collectAsState()
    val hdrMode by viewModel.hdrMode.collectAsState()
    val hardwareDecode by viewModel.hardwareDecode.collectAsState()

    // 面板打开时主动抢焦点，避免焦点回落到下层统一面板的菜单项
    val closeFocusRequester = remember { FocusRequester() }
    LaunchedEffect(Unit) {
        runCatching { closeFocusRequester.requestFocus() }
    }

    BoxWithConstraints(
        modifier = Modifier.fillMaxSize()
    ) {
        val useDualColumn = maxWidth > 500.dp

        Surface(
            color = MaterialTheme.colorScheme.surface.copy(alpha = 0.92f),
            modifier = Modifier.fillMaxSize()
        ) {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .focusGroup()
                    .systemBarsPadding()
                    .padding(16.dp)
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        text = "播放器设置",
                        style = MaterialTheme.typography.headlineSmall,
                        color = MaterialTheme.colorScheme.onSurface
                    )
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        IconButton(onClick = { viewModel.resetPlayerSettings() }, modifier = Modifier.tvFocusBorder()) {
                            Icon(Icons.Default.Refresh, contentDescription = "重置", tint = MaterialTheme.colorScheme.onSurface)
                        }
                        IconButton(onClick = { viewModel.togglePlayerSettings() }, modifier = Modifier.tvFocusBorder().focusRequester(closeFocusRequester)) {
                            Icon(Icons.Default.Close, contentDescription = "关闭", tint = MaterialTheme.colorScheme.onSurface)
                        }
                    }
                }

                Spacer(modifier = Modifier.height(12.dp))

                if (useDualColumn) {
                    Row(
                        modifier = Modifier.fillMaxSize().verticalScroll(rememberScrollState()),
                        horizontalArrangement = Arrangement.spacedBy(16.dp)
                    ) {
                        Column(modifier = Modifier.weight(1f)) {
                            PlayerSettingsLeftColumn(viewModel)
                        }
                        Column(modifier = Modifier.weight(1f)) {
                            PlayerSettingsRightColumn(viewModel)
                        }
                    }
                } else {
                    Column(
                        modifier = Modifier.fillMaxSize().verticalScroll(rememberScrollState())
                    ) {
                        PlayerSettingsLeftColumn(viewModel)
                        PlayerSettingsRightColumn(viewModel)
                    }
                }
            }
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun PlayerSettingsLeftColumn(viewModel: AppViewModel) {
    val currentPlayerType by viewModel.playerType.collectAsState()
    val currentVo by viewModel.currentVo.collectAsState()
    val currentHwdec by viewModel.currentHwdec.collectAsState()
    val hardwareDecode by viewModel.hardwareDecode.collectAsState()
    val timeoutSwitch by viewModel.timeoutSwitchSource.collectAsState()
    val reconnectIdx by viewModel.reconnectIndex.collectAsState()
    val screenLocked by viewModel.screenLock.collectAsState()
    val bootStart by viewModel.bootStart.collectAsState()
    val autoResume by viewModel.autoResume.collectAsState()

    SectionTitle("播放器内核")
    Spacer(modifier = Modifier.height(4.dp))
    SectionDesc("切换播放器内核。MPV 功能最完整，ExoPlayer 兼容性好，系统解码为 fallback")
    Spacer(modifier = Modifier.height(8.dp))
    FlowRow(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
        verticalArrangement = Arrangement.spacedBy(4.dp)
    ) {
        FilterChip(
            selected = currentPlayerType == PlayerType.MPV,
            onClick = { viewModel.switchPlayerType(PlayerType.MPV) },
            label = { Text("MPV（推荐）") },
            modifier = Modifier.tvFocusBorder(),
            border = androidx.compose.foundation.BorderStroke(1.dp, MaterialTheme.colorScheme.primary.copy(alpha = 0.50f))
        )
        FilterChip(
            selected = currentPlayerType == PlayerType.EXO,
            onClick = { viewModel.switchPlayerType(PlayerType.EXO) },
            label = { Text("ExoPlayer") },
            modifier = Modifier.tvFocusBorder(),
            border = androidx.compose.foundation.BorderStroke(1.dp, MaterialTheme.colorScheme.primary.copy(alpha = 0.50f))
        )
        FilterChip(
            selected = currentPlayerType == PlayerType.SYSTEM,
            onClick = { viewModel.switchPlayerType(PlayerType.SYSTEM) },
            label = { Text("系统解码") },
            modifier = Modifier.tvFocusBorder(),
            border = androidx.compose.foundation.BorderStroke(1.dp, MaterialTheme.colorScheme.primary.copy(alpha = 0.50f))
        )
    }
    Spacer(modifier = Modifier.height(6.dp))
    Text(
        text = currentPlayerType.description,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        fontSize = 12.sp,
        modifier = Modifier.padding(horizontal = 4.dp)
    )
    Spacer(modifier = Modifier.height(20.dp))

    SectionTitle("播放增强")
    Spacer(modifier = Modifier.height(8.dp))
    FlowRow(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
        verticalArrangement = Arrangement.spacedBy(4.dp)
    ) {
        FilterChip(
            selected = false,
            onClick = { viewModel.setTimeoutSwitchSource((timeoutSwitch + 1) % 6) },
            label = { Text("超时换源: ${listOf("5s","8s","12s","15s","20s","30s")[timeoutSwitch]}") },
            modifier = Modifier.tvFocusBorder()
        )
        FilterChip(
            selected = false,
            onClick = { viewModel.setReconnectIndex((reconnectIdx + 1) % 6) },
            label = { Text("断线重连: ${listOf("关闭","3s","5s","10s","15s","20s")[reconnectIdx]}") },
            modifier = Modifier.tvFocusBorder()
        )
    }
    Spacer(modifier = Modifier.height(8.dp))
    Surface(
        color = MaterialTheme.colorScheme.surface,
        shape = RoundedCornerShape(8.dp),
        modifier = Modifier.fillMaxWidth()
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth().tvFocusBorder().focusable().padding(vertical = 4.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(text = "画面锁定（换源不黑屏）", color = MaterialTheme.colorScheme.primary, fontSize = 13.sp, fontWeight = FontWeight.Medium)
                    Text(text = "切换频道时保持上一帧画面，避免黑屏闪烁", color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 11.sp)
                }
                Switch(checked = screenLocked, onCheckedChange = { viewModel.setScreenLock(it) })
            }
            Spacer(modifier = Modifier.height(8.dp))
            Row(
                modifier = Modifier.fillMaxWidth().tvFocusBorder().focusable().padding(vertical = 4.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(text = "开机自启动", color = MaterialTheme.colorScheme.primary, fontSize = 13.sp, fontWeight = FontWeight.Medium)
                    Text(text = "设备开机后自动启动应用", color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 11.sp)
                }
                Switch(checked = bootStart, onCheckedChange = { viewModel.setBootStart(it) })
            }
            Spacer(modifier = Modifier.height(8.dp))
            Row(
                modifier = Modifier.fillMaxWidth().tvFocusBorder().focusable().padding(vertical = 4.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(text = "启动自动续播", color = MaterialTheme.colorScheme.primary, fontSize = 13.sp, fontWeight = FontWeight.Medium)
                    Text(text = "打开应用时自动播放上次频道", color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 11.sp)
                }
                Switch(checked = autoResume, onCheckedChange = { viewModel.setAutoResume(it) })
            }
        }
    }
    Spacer(modifier = Modifier.height(20.dp))

    if (currentPlayerType == PlayerType.MPV) {
        SectionTitle("视频输出（VO）")
        Spacer(modifier = Modifier.height(4.dp))
        SectionDesc("决定画面如何渲染到屏幕。黑屏有声音时切换到 mediacodec_embed")
        Spacer(modifier = Modifier.height(8.dp))
        FlowRow(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalArrangement = Arrangement.spacedBy(4.dp)
        ) {
            FilterChip(selected = currentVo == "gpu", onClick = { viewModel.setPlayerVo("gpu") }, label = { Text("GPU（EGL）") }, modifier = Modifier.tvFocusBorder())
            FilterChip(selected = currentVo == "gpu-next", onClick = { viewModel.setPlayerVo("gpu-next") }, label = { Text("GPU-Next（EGL）") }, modifier = Modifier.tvFocusBorder())
            FilterChip(selected = currentVo == "mediacodec_embed", onClick = { viewModel.setPlayerVo("mediacodec_embed") }, label = { Text("MediaCodec") }, modifier = Modifier.tvFocusBorder())
        }
        Spacer(modifier = Modifier.height(6.dp))
        val voDesc = when (currentVo) {
            "gpu" -> "GPU 渲染：经典 EGL 后端，支持 HDR/OSD/shader，兼容大多数 GPU。部分 GPU（如 Mali-G76）可能黑屏"
            "gpu-next" -> "GPU-Next 渲染：新一代 EGL 后端（render API），渲染路径与 GPU 不同。支持 HDR/OSD/shader，GPU 黑屏时可尝试此选项"
            "mediacodec_embed" -> "MediaCodec 直接渲染到 Surface，绕过 EGL。GPU EGL 兼容性问题时的 fallback，不支持 OSD/HDR"
            else -> "未知 vo: $currentVo"
        }
        Text(text = voDesc, color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 12.sp, modifier = Modifier.padding(horizontal = 4.dp))
        Spacer(modifier = Modifier.height(20.dp))

        SectionTitle("硬件解码（HWDEC）")
        Spacer(modifier = Modifier.height(4.dp))
        SectionDesc("决定视频解码方式。必须与 vo 匹配")
        Spacer(modifier = Modifier.height(8.dp))
        FlowRow(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalArrangement = Arrangement.spacedBy(4.dp)
        ) {
            when (currentVo) {
                "gpu", "gpu-next" -> {
                    FilterChip(selected = currentHwdec == "auto-copy", onClick = { viewModel.setPlayerHwdec("auto-copy") }, label = { Text("auto-copy（推荐）") }, modifier = Modifier.tvFocusBorder())
                    FilterChip(selected = currentHwdec == "auto", onClick = { viewModel.setPlayerHwdec("auto") }, label = { Text("auto（4K HDR）") }, modifier = Modifier.tvFocusBorder())
                    FilterChip(selected = currentHwdec == "no", onClick = { viewModel.setPlayerHwdec("no") }, label = { Text("no（软解）") }, modifier = Modifier.tvFocusBorder())
                }
                "mediacodec_embed" -> {
                    FilterChip(selected = currentHwdec == "mediacodec", onClick = { viewModel.setPlayerHwdec("mediacodec") }, label = { Text("mediacodec（固定）") }, modifier = Modifier.tvFocusBorder())
                }
            }
        }
        Spacer(modifier = Modifier.height(6.dp))
        val hwdecDesc = when (currentHwdec) {
            "auto-copy" -> "自动选择硬件解码器，解码后拷贝到 CPU 内存再上传 GPU。兼容性好，支持视频滤镜（翻转/裁剪/360°）。4K HDR 可能卡顿"
            "auto" -> "自动选择最佳硬解，优先直接输出（零拷贝）。4K HDR 流畅，但视频翻转/裁剪/360° 滤镜可能不可用"
            "mediacodec" -> "MediaCodec 硬件解码，直接渲染到 Surface。必须与 vo=mediacodec_embed 配合"
            "no" -> "纯软件解码。兼容性最好但耗电，CPU 解码可能慢"
            else -> "未知 hwdec: $currentHwdec"
        }
        Text(text = hwdecDesc, color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 12.sp, modifier = Modifier.padding(horizontal = 4.dp))
        Spacer(modifier = Modifier.height(20.dp))
    }

    if (currentPlayerType == PlayerType.EXO || currentPlayerType == PlayerType.SYSTEM) {
        SectionTitle("解码模式")
        Spacer(modifier = Modifier.height(4.dp))
        SectionDesc("硬解使用 GPU MediaCodec 加速，软解使用 FFmpeg 扩展解码器。软解兼容性更好但更耗电")
        Spacer(modifier = Modifier.height(8.dp))
        FlowRow(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalArrangement = Arrangement.spacedBy(4.dp)
        ) {
            FilterChip(selected = hardwareDecode, onClick = { viewModel.setHardwareDecode(true) }, label = { Text("硬件解码（推荐）") }, modifier = Modifier.tvFocusBorder())
            FilterChip(selected = !hardwareDecode, onClick = { viewModel.setHardwareDecode(false) }, label = { Text("软件解码") }, modifier = Modifier.tvFocusBorder())
        }
        Spacer(modifier = Modifier.height(6.dp))
        Text(
            text = if (hardwareDecode) "硬件解码：使用 Android MediaCodec 硬件加速解码。功耗低、速度快，但部分 4K/HDR 流可能不兼容。遇到花屏/卡顿时可尝试软解" else "软件解码：使用 FFmpeg 扩展解码器（软解）。兼容性最好，支持更多编码格式，但 CPU 负载高、可能发热。适合硬解不兼容的 4K/HDR 流",
            color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 12.sp, modifier = Modifier.padding(horizontal = 4.dp)
        )
        Spacer(modifier = Modifier.height(20.dp))
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun PlayerSettingsRightColumn(viewModel: AppViewModel) {
    val currentDeinterlace by viewModel.currentDeinterlace.collectAsState()
    val hdrMode by viewModel.hdrMode.collectAsState()
    val currentRtspTransport by viewModel.currentRtspTransport.collectAsState()
    val logLevel by viewModel.logLevel.collectAsState()
    val currentVo by viewModel.currentVo.collectAsState()
    val epgTz by viewModel.epgTimezoneOffset.collectAsState()
    val epgCache by viewModel.epgCacheSchedule.collectAsState()
    val groupMd by viewModel.groupMode.collectAsState()
    val perChannelEnabled by viewModel.perChannelSettingsEnabled.collectAsState()

    SectionTitle("EPG 设置")
    Spacer(modifier = Modifier.height(8.dp))
    FlowRow(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
        verticalArrangement = Arrangement.spacedBy(4.dp)
    ) {
        FilterChip(
            selected = false,
            onClick = { viewModel.setEpgTimezoneOffset((epgTz + 1) % 26) },
            label = { Text("时区: ${if (epgTz == 0) "默认" else "UTC${if (epgTz > 13) "-" else "+"}${if (epgTz > 13) (26 - epgTz) else epgTz}"}") },
            modifier = Modifier.tvFocusBorder()
        )
        FilterChip(
            selected = false,
            onClick = { viewModel.setEpgCacheSchedule((epgCache + 1) % 12) },
            label = { Text("缓存: ${listOf("关闭","1h","2h","3h","4h","6h","8h","12h","24h","48h","72h","7d")[epgCache]}") },
            modifier = Modifier.tvFocusBorder()
        )
        FilterChip(
            selected = false,
            onClick = { viewModel.setGroupMode((groupMd + 1) % 4) },
            label = { Text("分组: ${listOf("默认","二级分组","紧凑","展开")[groupMd]}") },
            modifier = Modifier.tvFocusBorder()
        )
    }
    Spacer(modifier = Modifier.height(20.dp))

    SectionTitle("反交错（Deinterlace）")
    Spacer(modifier = Modifier.height(4.dp))
    SectionDesc("消除隔行扫描视频（如 1080i TV 流）的横线梳齿。自动模式由 mpv 检测隔行内容")
    Spacer(modifier = Modifier.height(8.dp))
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        FilterChip(selected = currentDeinterlace == "no", onClick = { viewModel.setDeinterlace("no") }, label = { Text("关闭") }, modifier = Modifier.tvFocusBorder())
        FilterChip(selected = currentDeinterlace == "auto", onClick = { viewModel.setDeinterlace("auto") }, label = { Text("自动") }, modifier = Modifier.tvFocusBorder())
    }
    Spacer(modifier = Modifier.height(6.dp))
    val deinterlaceDesc = when (currentDeinterlace) {
        "no" -> "关闭反交错：逐行视频不受影响，隔行视频可能出现梳齿。适合所有逐行视频源（大部分网络流均为逐行）"
        "auto" -> "自动反交错：mpv 自动检测隔行内容并应用 yadif 滤镜。逐行视频不受影响，隔行视频（1080i TV）消除梳齿。与 hwdec=auto（直接输出）模式可能不兼容，需用 auto-copy 或 no"
        else -> "未知设置: $currentDeinterlace"
    }
    Text(text = deinterlaceDesc, color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 12.sp, modifier = Modifier.padding(horizontal = 4.dp))
    Spacer(modifier = Modifier.height(20.dp))

    SectionTitle("HDR 输出模式")
    Spacer(modifier = Modifier.height(4.dp))
    SectionDesc("HDR 视频的色彩处理方式。仅对 HDR 视频生效，非 HDR 视频不受影响")
    Spacer(modifier = Modifier.height(8.dp))
    FlowRow(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
        verticalArrangement = Arrangement.spacedBy(4.dp)
    ) {
        FilterChip(selected = hdrMode == AppViewModel.HdrMode.DISABLE, onClick = { viewModel.setHdrMode(AppViewModel.HdrMode.DISABLE) }, label = { Text("禁用") }, modifier = Modifier.tvFocusBorder())
        FilterChip(selected = hdrMode == AppViewModel.HdrMode.AUTO, onClick = { viewModel.setHdrMode(AppViewModel.HdrMode.AUTO) }, label = { Text("自动") }, modifier = Modifier.tvFocusBorder())
        FilterChip(selected = hdrMode == AppViewModel.HdrMode.TONEMAP, onClick = { viewModel.setHdrMode(AppViewModel.HdrMode.TONEMAP) }, label = { Text("色调映射") }, modifier = Modifier.tvFocusBorder())
        FilterChip(selected = hdrMode == AppViewModel.HdrMode.PASSTHROUGH, onClick = { viewModel.setHdrMode(AppViewModel.HdrMode.PASSTHROUGH) }, label = { Text("直通") }, modifier = Modifier.tvFocusBorder())
    }
    Spacer(modifier = Modifier.height(6.dp))
    val hdrDesc = when (hdrMode) {
        AppViewModel.HdrMode.DISABLE -> "禁用 HDR：强制 SDR 输出。所有视频按 bt.709/bt.1886 渲染，HDR 视频可能高光过曝"
        AppViewModel.HdrMode.AUTO -> "自动模式：检测设备 HDR 能力，支持则交给系统自动切换 HDR 显示（直通），不支持则色调映射到 SDR"
        AppViewModel.HdrMode.TONEMAP -> "HDR→SDR 色调映射：HDR 视频映射到 bt.709/bt.1886。信任 HDR10+ 动态元数据，自动选择算法（HDR10+→st2094-40, HDR10/HLG→bt.2390）"
        AppViewModel.HdrMode.PASSTHROUGH -> "HDR 直通：HDR 视频按 bt.2020/pq 输出。需要显示器支持 HDR，否则画面可能过暗或色彩异常"
    }
    Text(text = hdrDesc, color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 12.sp, modifier = Modifier.padding(horizontal = 4.dp))
    Spacer(modifier = Modifier.height(20.dp))

    SectionTitle("RTSP 传输协议")
    Spacer(modifier = Modifier.height(4.dp))
    SectionDesc("RTSP 流的传输方式。TCP 更稳定（防火墙穿透），UDP 延迟更低但可能丢包")
    Spacer(modifier = Modifier.height(8.dp))
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        FilterChip(selected = currentRtspTransport == "tcp", onClick = { viewModel.setRtspTransport("tcp") }, label = { Text("TCP（推荐）") }, modifier = Modifier.tvFocusBorder())
        FilterChip(selected = currentRtspTransport == "udp", onClick = { viewModel.setRtspTransport("udp") }, label = { Text("UDP（低延迟）") }, modifier = Modifier.tvFocusBorder())
    }
    Spacer(modifier = Modifier.height(6.dp))
    val rtspDesc = when (currentRtspTransport) {
        "tcp" -> "TCP 传输：RTSP over TCP，数据通过 TCP 通道传输。更稳定，防火墙穿透好，适合网络不稳定的环境。延迟略高"
        "udp" -> "UDP 传输：RTSP over UDP，数据通过 UDP 通道传输。延迟更低，但网络不稳定时可能丢包导致花屏。需要良好的网络环境"
        else -> "未知传输协议: $currentRtspTransport"
    }
    Text(text = rtspDesc, color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 12.sp, modifier = Modifier.padding(horizontal = 4.dp))
    Spacer(modifier = Modifier.height(20.dp))

    SectionTitle("日志等级")
    Spacer(modifier = Modifier.height(4.dp))
    SectionDesc("控制日志输出等级（app.log + logcat）。立即生效，无需重启")
    Spacer(modifier = Modifier.height(8.dp))
    FlowRow(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
        verticalArrangement = Arrangement.spacedBy(4.dp)
    ) {
        FilterChip(selected = logLevel == "error", onClick = { viewModel.setLogLevel("error") }, label = { Text("错误") }, modifier = Modifier.tvFocusBorder())
        FilterChip(selected = logLevel == "warn", onClick = { viewModel.setLogLevel("warn") }, label = { Text("警告") }, modifier = Modifier.tvFocusBorder())
        FilterChip(selected = logLevel == "info", onClick = { viewModel.setLogLevel("info") }, label = { Text("信息") }, modifier = Modifier.tvFocusBorder())
        FilterChip(selected = logLevel == "debug", onClick = { viewModel.setLogLevel("debug") }, label = { Text("调试") }, modifier = Modifier.tvFocusBorder())
    }
    Spacer(modifier = Modifier.height(6.dp))
    val logLevelDesc = when (logLevel) {
        "error" -> "仅输出错误信息。适合正式使用，日志量最小"
        "warn" -> "输出警告和错误。适合日常使用"
        "info" -> "输出信息、警告和错误（默认）。适合一般调试"
        "debug" -> "输出全部日志（含 trace）。适合深度调试，日志量很大"
        else -> "未知等级: $logLevel"
    }
    Text(text = logLevelDesc, color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 12.sp, modifier = Modifier.padding(horizontal = 4.dp))
    Spacer(modifier = Modifier.height(20.dp))

    val fallbackConfirmed = remember(currentVo) { UserPrefs.getInstance().isVoFallbackConfirmed() }
    if (fallbackConfirmed) {
        Surface(
            color = MaterialTheme.colorScheme.primaryContainer,
            shape = RoundedCornerShape(8.dp),
            modifier = Modifier.fillMaxWidth()
        ) {
            Row(modifier = Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(text = "黑屏 fallback 已确认", color = MaterialTheme.colorScheme.onSurface, fontSize = 13.sp, fontWeight = FontWeight.Medium)
                    Text(text = "该设备曾触发过黑屏检测，下次启动直接用 mediacodec_embed", color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 11.sp)
                }
            }
        }
    }
    Spacer(modifier = Modifier.height(20.dp))

    Surface(
        color = MaterialTheme.colorScheme.surface,
        shape = RoundedCornerShape(8.dp),
        modifier = Modifier.fillMaxWidth()
    ) {
        Row(
            modifier = Modifier.fillMaxWidth().tvFocusBorder().focusable().padding(12.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(text = "频道记忆", color = MaterialTheme.colorScheme.primary, fontSize = 13.sp, fontWeight = FontWeight.Medium)
                Spacer(modifier = Modifier.height(2.dp))
                Text(
                    text = "开启后，每个频道会自动记忆各自的输出/解码/HDR 设置。切换频道时自动应用，无需手动保存。在主菜单「清除频道专属设置」可重置当前频道。",
                    color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 11.sp, lineHeight = 15.sp
                )
            }
            Spacer(modifier = Modifier.width(8.dp))
            Switch(checked = perChannelEnabled, onCheckedChange = { viewModel.setPerChannelSettingsEnabled(it) })
        }
    }
    Spacer(modifier = Modifier.height(20.dp))

    Surface(
        color = MaterialTheme.colorScheme.surfaceVariant,
        shape = RoundedCornerShape(8.dp),
        modifier = Modifier.fillMaxWidth()
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            Text(text = "使用说明", color = MaterialTheme.colorScheme.primary, fontSize = 13.sp, fontWeight = FontWeight.Medium)
            Spacer(modifier = Modifier.height(4.dp))
            Text(
                text = "1. MPV 功能最完整（EQ/AB循环/逐帧/截图/HDR）\n2. 黑屏有声音时切换 vo 到 mediacodec_embed\n3. 切换 vo 后会自动重新加载当前频道\n4. 点击右上角重置按钮可恢复默认值",
                color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 12.sp, lineHeight = 18.sp
            )
        }
    }
}

@Composable
private fun SectionTitle(text: String) {
    Text(
        text = text,
        color = MaterialTheme.colorScheme.primary,
        fontSize = 14.sp,
        fontWeight = FontWeight.SemiBold
    )
}

@Composable
private fun SectionDesc(text: String) {
    Text(
        text = text,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        fontSize = 12.sp
    )
}
