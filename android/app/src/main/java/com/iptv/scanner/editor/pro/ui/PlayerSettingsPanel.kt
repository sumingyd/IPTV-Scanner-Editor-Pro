package com.iptv.scanner.editor.pro.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
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
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.iptv.scanner.editor.pro.data.UserPrefs
import com.iptv.scanner.editor.pro.player.PlayerType
import com.iptv.scanner.editor.pro.ui.theme.tvFocusBorder

/**
 * 播放器设置面板（全屏覆盖）。
 *
 * 三层设置：
 * 1. 播放器内核：MPV / ExoPlayer / VLC / IJK（切换后 View 重建，恢复播放进度）
 * 2. 视频输出（vo）：仅 MPV 模式下显示，gpu / mediacodec_embed
 * 3. 硬件解码（hwdec）：仅 MPV 模式下显示，必须与 vo 匹配
 *
 * 兜底方案：当黑屏检测不可靠时（如 estimated-vfps 仍有值但渲染黑屏），
 * 用户可手动切换 vo（gpu / mediacodec_embed），立即生效并持久化。
 *
 * - vo：video output，gpu（EGL 渲染）或 mediacodec_embed（MediaCodec 直接渲染）
 * - hwdec：硬件解码，auto-copy / mediacodec / no（必须与 vo 匹配）
 * - 重置：恢复默认值（MPV + vo=gpu + hwdec=auto-copy）
 */
@Composable
fun PlayerSettingsPanel(viewModel: AppViewModel) {
    val playerType by viewModel.playerType.collectAsState()
    val playerCapabilities by viewModel.playerCapabilities.collectAsState()
    val currentVo by viewModel.currentVo.collectAsState()
    val currentHwdec by viewModel.currentHwdec.collectAsState()
    val hdrMode by viewModel.hdrMode.collectAsState()
    val hardwareDecode by viewModel.hardwareDecode.collectAsState()
    val isMpvMode = playerType == PlayerType.MPV

    Surface(
        color = Color(0xF0121212),
        modifier = Modifier.fillMaxSize()
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(16.dp)
                .verticalScroll(rememberScrollState())
        ) {
            // 标题栏
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = "播放器设置",
                    style = MaterialTheme.typography.headlineSmall,
                    color = Color.White
                )
                Row(verticalAlignment = Alignment.CenterVertically) {
                    // 重置按钮
                    IconButton(onClick = { viewModel.resetPlayerSettings() }, modifier = Modifier.tvFocusBorder()) {
                        Icon(Icons.Default.Refresh, contentDescription = "重置", tint = Color.White)
                    }
                    // 关闭按钮
                    IconButton(onClick = { viewModel.togglePlayerSettings() }, modifier = Modifier.tvFocusBorder()) {
                        Icon(Icons.Default.Close, contentDescription = "关闭", tint = Color.White)
                    }
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            // -----------------------------------------------------------------
            // 1. 播放器内核选择（MPV / ExoPlayer / VLC / IJK）
            // -----------------------------------------------------------------
            SectionTitle("播放器内核")
            Spacer(modifier = Modifier.height(4.dp))
            SectionDesc("切换播放器会重建视频组件并恢复播放进度")

            Spacer(modifier = Modifier.height(8.dp))

            // 4 个播放器 chip（两行布局，避免窄屏溢出）
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                FilterChip(
                    selected = playerType == PlayerType.MPV,
                    onClick = { viewModel.switchPlayer(PlayerType.MPV) },
                    label = { Text("MPV") },
                    modifier = Modifier.tvFocusBorder()
                )
                FilterChip(
                    selected = playerType == PlayerType.EXO,
                    onClick = { viewModel.switchPlayer(PlayerType.EXO) },
                    label = { Text("ExoPlayer") },
                    modifier = Modifier.tvFocusBorder()
                )
            }
            Spacer(modifier = Modifier.height(6.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                FilterChip(
                    selected = playerType == PlayerType.VLC,
                    onClick = { viewModel.switchPlayer(PlayerType.VLC) },
                    label = { Text("VLC") },
                    modifier = Modifier.tvFocusBorder()
                )
                FilterChip(
                    selected = playerType == PlayerType.IJK,
                    onClick = { viewModel.switchPlayer(PlayerType.IJK) },
                    label = { Text("IJKPlayer") },
                    modifier = Modifier.tvFocusBorder()
                )
            }

            Spacer(modifier = Modifier.height(6.dp))

            // 当前播放器说明
            Text(
                text = playerType.description,
                color = Color(0xFFB0BEC5),
                fontSize = 12.sp,
                modifier = Modifier.padding(horizontal = 4.dp)
            )

            // 能力徽章：显示当前播放器支持的高级功能
            Spacer(modifier = Modifier.height(8.dp))
            PlayerCapabilityBadges(playerCapabilities)

            // -----------------------------------------------------------------
            // 2. 解码模式选择（非 MPV 内核：ExoPlayer/VLC/IJK）
            // -----------------------------------------------------------------
            // MPV 内核有更详细的 vo/hwdec 切换（下方），其他内核用统一的硬解/软解开关
            if (!isMpvMode && playerCapabilities.supportsHardwareDecodeSwitch) {
                Spacer(modifier = Modifier.height(20.dp))

                SectionTitle("解码模式")
                Spacer(modifier = Modifier.height(4.dp))
                SectionDesc("切换硬件解码（MediaCodec）与软件解码。软解兼容性好但耗电")

                Spacer(modifier = Modifier.height(8.dp))

                val isHardDecode = hardwareDecode
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    FilterChip(
                        selected = isHardDecode,
                        onClick = { viewModel.setHardwareDecode(true) },
                        label = { Text("硬件解码") },
                        modifier = Modifier.tvFocusBorder()
                    )
                    FilterChip(
                        selected = !isHardDecode,
                        onClick = { viewModel.setHardwareDecode(false) },
                        label = { Text("软件解码") },
                        modifier = Modifier.tvFocusBorder()
                    )
                }

                Spacer(modifier = Modifier.height(6.dp))

                // 解码模式说明
                val decodeDesc = when (playerType) {
                    PlayerType.EXO -> if (isHardDecode) {
                        "MediaCodec 硬件解码（默认）。软解需 FFmpeg 扩展，未安装时自动回退硬解"
                    } else {
                        "优先软件解码（FFmpeg 扩展）。未安装扩展时自动回退到 MediaCodec 硬解"
                    }
                    PlayerType.VLC -> if (isHardDecode) {
                        "MediaCodec NDK 硬件解码（默认）。兼容性好，性能佳"
                    } else {
                        "软件解码。兼容性最好但耗电，适合硬解不兼容的流"
                    }
                    PlayerType.IJK -> if (isHardDecode) {
                        "MediaCodec 硬件解码（默认）。基于 FFmpeg + MediaCodec"
                    } else {
                        "纯 FFmpeg 软件解码。兼容性最好但 CPU 占用高"
                    }
                    else -> ""
                }
                Text(
                    text = decodeDesc,
                    color = Color(0xFFB0BEC5),
                    fontSize = 12.sp,
                    modifier = Modifier.padding(horizontal = 4.dp)
                )
            }

            // -----------------------------------------------------------------
            // 3. VO / HWDEC 设置（仅 MPV 模式下显示）
            // -----------------------------------------------------------------
            // 原因：vo/hwdec 是 mpv 专属概念，其他播放器（Exo/VLC/IJK）用上方的解码模式开关
            if (isMpvMode) {
                Spacer(modifier = Modifier.height(20.dp))

                // -----------------------------------------------------------------
                // 视频输出（vo）选择
                // -----------------------------------------------------------------
                SectionTitle("视频输出（VO）")
                Spacer(modifier = Modifier.height(4.dp))
                SectionDesc("决定画面如何渲染到屏幕。黑屏有声音时切换到 mediacodec_embed")

                Spacer(modifier = Modifier.height(8.dp))

                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    FilterChip(
                        selected = currentVo == "gpu",
                        onClick = { viewModel.setPlayerVo("gpu") },
                        label = { Text("GPU（EGL 渲染）") },
                        modifier = Modifier.tvFocusBorder()
                    )
                    FilterChip(
                        selected = currentVo == "mediacodec_embed",
                        onClick = { viewModel.setPlayerVo("mediacodec_embed") },
                        label = { Text("MediaCodec") },
                        modifier = Modifier.tvFocusBorder()
                    )
                }

                Spacer(modifier = Modifier.height(6.dp))

                // 当前 vo 说明
                val voDesc = when (currentVo) {
                    "gpu" -> "GPU 渲染：基于 EGL，支持 HDR/OSD/shader，兼容大多数 GPU。" +
                        "部分 GPU（如 Mali-G76）可能黑屏"
                    "mediacodec_embed" -> "MediaCodec 直接渲染到 Surface，绕过 EGL。" +
                        "GPU EGL 兼容性问题时的 fallback，不支持 OSD/HDR"
                    else -> "未知 vo: $currentVo"
                }
                Text(
                    text = voDesc,
                    color = Color(0xFFB0BEC5),
                    fontSize = 12.sp,
                    modifier = Modifier.padding(horizontal = 4.dp)
                )

                Spacer(modifier = Modifier.height(20.dp))

                // -----------------------------------------------------------------
                // 硬件解码（hwdec）选择
                // -----------------------------------------------------------------
                SectionTitle("硬件解码（HWDEC）")
                Spacer(modifier = Modifier.height(4.dp))
                SectionDesc("决定视频解码方式。必须与 vo 匹配")

                Spacer(modifier = Modifier.height(8.dp))

                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    when (currentVo) {
                        "gpu" -> {
                            // vo=gpu 时：auto-copy（推荐）或 no（软解）
                            FilterChip(
                                selected = currentHwdec == "auto-copy",
                                onClick = { viewModel.setPlayerHwdec("auto-copy") },
                                label = { Text("auto-copy（推荐）") },
                                modifier = Modifier.tvFocusBorder()
                            )
                            FilterChip(
                                selected = currentHwdec == "no",
                                onClick = { viewModel.setPlayerHwdec("no") },
                                label = { Text("no（软解）") },
                                modifier = Modifier.tvFocusBorder()
                            )
                        }
                        "mediacodec_embed" -> {
                            // vo=mediacodec_embed 时：固定 mediacodec
                            FilterChip(
                                selected = currentHwdec == "mediacodec",
                                onClick = { viewModel.setPlayerHwdec("mediacodec") },
                                label = { Text("mediacodec（固定）") },
                                modifier = Modifier.tvFocusBorder()
                            )
                        }
                    }
                }

                Spacer(modifier = Modifier.height(6.dp))

                // 当前 hwdec 说明
                val hwdecDesc = when (currentHwdec) {
                    "auto-copy" -> "自动选择硬件解码器，解码后拷贝到 CPU 内存再上传 GPU。" +
                        "兼容性好，与 vo=gpu 配合"
                    "mediacodec" -> "MediaCodec 硬件解码，直接渲染到 Surface。" +
                        "必须与 vo=mediacodec_embed 配合"
                    "no" -> "纯软件解码。兼容性最好但耗电，CPU 解码可能慢"
                    else -> "未知 hwdec: $currentHwdec"
                }
                Text(
                    text = hwdecDesc,
                    color = Color(0xFFB0BEC5),
                    fontSize = 12.sp,
                    modifier = Modifier.padding(horizontal = 4.dp)
                )

                Spacer(modifier = Modifier.height(20.dp))

                // -----------------------------------------------------------------
                // HDR 输出模式（与 PC 端 hdr_output_mode 对齐）
                // -----------------------------------------------------------------
                SectionTitle("HDR 输出模式")
                Spacer(modifier = Modifier.height(4.dp))
                SectionDesc("HDR 视频的色彩处理方式。仅对 HDR 视频生效，非 HDR 视频不受影响")

                Spacer(modifier = Modifier.height(8.dp))

                // 4 个 HDR 模式 chip（两行布局，避免窄屏溢出）
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    FilterChip(
                        selected = hdrMode == AppViewModel.HdrMode.DISABLE,
                        onClick = { viewModel.setHdrMode(AppViewModel.HdrMode.DISABLE) },
                        label = { Text("禁用") },
                        modifier = Modifier.tvFocusBorder()
                    )
                    FilterChip(
                        selected = hdrMode == AppViewModel.HdrMode.AUTO,
                        onClick = { viewModel.setHdrMode(AppViewModel.HdrMode.AUTO) },
                        label = { Text("自动") },
                        modifier = Modifier.tvFocusBorder()
                    )
                }
                Spacer(modifier = Modifier.height(6.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    FilterChip(
                        selected = hdrMode == AppViewModel.HdrMode.TONEMAP,
                        onClick = { viewModel.setHdrMode(AppViewModel.HdrMode.TONEMAP) },
                        label = { Text("色调映射") },
                        modifier = Modifier.tvFocusBorder()
                    )
                    FilterChip(
                        selected = hdrMode == AppViewModel.HdrMode.PASSTHROUGH,
                        onClick = { viewModel.setHdrMode(AppViewModel.HdrMode.PASSTHROUGH) },
                        label = { Text("直通") },
                        modifier = Modifier.tvFocusBorder()
                    )
                }

                Spacer(modifier = Modifier.height(6.dp))

                // 当前 HDR 模式说明
                val hdrDesc = when (hdrMode) {
                    AppViewModel.HdrMode.DISABLE -> "禁用 HDR：强制 SDR 输出。" +
                        "所有视频按 bt.709/bt.1886 渲染，HDR 视频可能高光过曝"
                    AppViewModel.HdrMode.AUTO -> "自动模式：Android 端固定走色调映射" +
                        "（系统 HDR 检测复杂，与 PC 端未启用 HDR 一致）"
                    AppViewModel.HdrMode.TONEMAP -> "HDR→SDR 色调映射：HDR 视频映射到 bt.709/bt.1886。" +
                        "信任 HDR10+ 动态元数据，自动选择算法（HDR10+→st2094-40, HDR10/HLG→bt.2390）"
                    AppViewModel.HdrMode.PASSTHROUGH -> "HDR 直通：HDR 视频按 bt.2020/pq 输出。" +
                        "需要显示器支持 HDR，否则画面可能过暗或色彩异常"
                }
                Text(
                    text = hdrDesc,
                    color = Color(0xFFB0BEC5),
                    fontSize = 12.sp,
                    modifier = Modifier.padding(horizontal = 4.dp)
                )

                Spacer(modifier = Modifier.height(20.dp))

                // -----------------------------------------------------------------
                // 黑屏 fallback 状态
                // -----------------------------------------------------------------
                val fallbackConfirmed = remember(currentVo) {
                    UserPrefs.getInstance().isVoFallbackConfirmed()
                }
                if (fallbackConfirmed) {
                    Surface(
                        color = Color(0xFF1B5E20),
                        shape = RoundedCornerShape(8.dp),
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Row(
                            modifier = Modifier.padding(12.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Column(modifier = Modifier.weight(1f)) {
                                Text(
                                    text = "黑屏 fallback 已确认",
                                    color = Color.White,
                                    fontSize = 13.sp,
                                    fontWeight = FontWeight.Medium
                                )
                                Text(
                                    text = "该设备曾触发过黑屏检测，下次启动直接用 mediacodec_embed",
                                    color = Color(0xFFA5D6A7),
                                    fontSize = 11.sp
                                )
                            }
                        }
                    }
                }
            }

            Spacer(modifier = Modifier.height(20.dp))

            // -----------------------------------------------------------------
            // 提示
            // -----------------------------------------------------------------
            Surface(
                color = Color(0xFF263238),
                shape = RoundedCornerShape(8.dp),
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(modifier = Modifier.padding(12.dp)) {
                    Text(
                        text = "使用说明",
                        color = Color(0xFF90CAF9),
                        fontSize = 13.sp,
                        fontWeight = FontWeight.Medium
                    )
                    Spacer(modifier = Modifier.height(4.dp))
                    val tips = if (isMpvMode) {
                        "1. MPV 功能最完整（EQ/AB循环/逐帧/截图/HDR）\n" +
                            "2. 黑屏有声音时切换 vo 到 mediacodec_embed\n" +
                            "3. 切换 vo 后会自动重新加载当前频道\n" +
                            "4. 切换播放器内核会重建视频组件并恢复进度\n" +
                            "5. 点击右上角重置按钮可恢复默认值"
                    } else {
                        "1. ${playerType.displayName}：${playerType.description}\n" +
                            "2. 切换回 MPV 可使用全部高级功能\n" +
                            "3. 切换播放器内核会重建视频组件并恢复进度\n" +
                            "4. 点击右上角重置按钮可恢复默认值（MPV）"
                    }
                    Text(
                        text = tips,
                        color = Color(0xFFB0BEC5),
                        fontSize = 12.sp,
                        lineHeight = 18.sp
                    )
                }
            }
        }
    }
}

/**
 * 播放器能力徽章：可视化展示当前播放器支持的高级功能。
 *
 * 用绿色/灰色徽章区分支持/不支持的功能，让用户直观了解能力差异。
 */
@Composable
private fun PlayerCapabilityBadges(caps: com.iptv.scanner.editor.pro.player.PlayerCapabilities) {
    val badges = listOf(
        "EQ" to caps.supportsVideoEq,
        "AB循环" to caps.supportsAbLoop,
        "逐帧" to caps.supportsFrameStep,
        "章节" to caps.supportsChapters,
        "截图" to caps.supportsScreenshot,
        "OSD" to caps.supportsOsd,
        "字幕延迟" to caps.supportsSubDelay,
        "外挂字幕" to caps.supportsAddSubtitleFile,
        "音轨切换" to caps.supportsTrackList,
        "变速" to caps.supportsSpeedControl
    )
    // 每行 5 个徽章
    val rows = badges.chunked(5)
    rows.forEach { row ->
        Row(
            horizontalArrangement = Arrangement.spacedBy(6.dp),
            modifier = Modifier.padding(vertical = 2.dp)
        ) {
            row.forEach { (label, supported) ->
                Surface(
                    color = if (supported) Color(0xFF1B5E20) else Color(0xFF424242),
                    shape = RoundedCornerShape(4.dp)
                ) {
                    Text(
                        text = label,
                        color = if (supported) Color(0xFFA5D6A7) else Color(0xFF757575),
                        fontSize = 10.sp,
                        modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp)
                    )
                }
            }
        }
    }
}

@Composable
private fun SectionTitle(text: String) {
    Text(
        text = text,
        color = Color(0xFF4A9EFF),
        fontSize = 14.sp,
        fontWeight = FontWeight.SemiBold
    )
}

@Composable
private fun SectionDesc(text: String) {
    Text(
        text = text,
        color = Color(0xFF888888),
        fontSize = 12.sp
    )
}
