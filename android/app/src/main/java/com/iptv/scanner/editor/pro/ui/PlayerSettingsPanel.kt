package com.iptv.scanner.editor.pro.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
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

/**
 * 播放器设置面板（全屏覆盖）。
 *
 * 兜底方案：当黑屏检测不可靠时（如 estimated-vfps 仍有值但渲染黑屏），
 * 用户可手动切换 vo（gpu / mediacodec_embed），立即生效并持久化。
 *
 * - vo：video output，gpu（EGL 渲染）或 mediacodec_embed（MediaCodec 直接渲染）
 * - hwdec：硬件解码，auto-copy / mediacodec / no（必须与 vo 匹配）
 * - 重置：恢复默认值（vo=gpu, hwdec=auto-copy）
 */
@Composable
fun PlayerSettingsPanel(viewModel: AppViewModel) {
    val currentVo by viewModel.currentVo.collectAsState()
    val currentHwdec by viewModel.currentHwdec.collectAsState()

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
                Text(
                    text = "播放器设置",
                    style = MaterialTheme.typography.headlineSmall,
                    color = Color.White
                )
                Row(verticalAlignment = Alignment.CenterVertically) {
                    // 重置按钮
                    IconButton(onClick = { viewModel.resetPlayerSettings() }) {
                        Icon(Icons.Default.Refresh, contentDescription = "重置", tint = Color.White)
                    }
                    // 关闭按钮
                    IconButton(onClick = { viewModel.togglePlayerSettings() }) {
                        Icon(Icons.Default.Close, contentDescription = "关闭", tint = Color.White)
                    }
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

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
                    label = { Text("GPU（EGL 渲染）") }
                )
                FilterChip(
                    selected = currentVo == "mediacodec_embed",
                    onClick = { viewModel.setPlayerVo("mediacodec_embed") },
                    label = { Text("MediaCodec") }
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
                            label = { Text("auto-copy（推荐）") }
                        )
                        FilterChip(
                            selected = currentHwdec == "no",
                            onClick = { viewModel.setPlayerHwdec("no") },
                            label = { Text("no（软解）") }
                        )
                    }
                    "mediacodec_embed" -> {
                        // vo=mediacodec_embed 时：固定 mediacodec
                        FilterChip(
                            selected = currentHwdec == "mediacodec",
                            onClick = { viewModel.setPlayerHwdec("mediacodec") },
                            label = { Text("mediacodec（固定）") }
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
            // 黑屏 fallback 状态
            // -----------------------------------------------------------------
            val fallbackConfirmed = remember(currentVo) {
                // 从 UserPrefs 读取（避免引入 collectAsState）
                com.iptv.scanner.editor.pro.data.UserPrefs.getInstance().isVoFallbackConfirmed()
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
                    Text(
                        text = "1. 首次安装默认 vo=gpu，如果黑屏有声音请切换到 mediacodec_embed\n" +
                            "2. 切换 vo 后会自动重新加载当前频道\n" +
                            "3. 如果切换后仍黑屏，请重启 APP（vo 在启动时初始化）\n" +
                            "4. 点击右上角重置按钮可恢复默认值",
                        color = Color(0xFFB0BEC5),
                        fontSize = 12.sp,
                        lineHeight = 18.sp
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
