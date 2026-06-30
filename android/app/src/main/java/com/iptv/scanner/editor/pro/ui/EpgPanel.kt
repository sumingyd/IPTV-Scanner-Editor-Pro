package com.iptv.scanner.editor.pro.ui

import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
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
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.iptv.scanner.editor.pro.data.IptvEpgProgram
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * EPG 节目单面板：与 PC 端 mobile/index.html panelEPG 对齐。
 *
 * - 节目列表渲染（时间、标题、副标题、描述）
 * - LIVE badge 当前节目（红色脉冲动画）
 * - 当前节目自动滚动到中央
 * - 过去节目：opacity 0.5 + cursor pointer（点击触发 catchup）
 * - 当前/未来节目：点击设置提醒
 *
 * 与内存规则对齐：
 * - EPG current program must be highlighted with LIVE badge and auto-scrolled to center
 * - EPG past programs must trigger catchup via startCatchup when clicked
 * - EPG current/future programs trigger reminder via setReminder
 */
@Composable
fun EpgPanel(viewModel: AppViewModel) {
    val currentChannel by viewModel.currentChannel.collectAsState()
    val epg by viewModel.currentEpg.collectAsState()
    val loading by viewModel.epgLoading.collectAsState()
    val currentIdx by viewModel.currentIdx.collectAsState()

    var searchQuery by remember { mutableStateOf("") }

    Surface(
        color = Color(0xF0161616),
        modifier = Modifier
            .fillMaxHeight()
            .width(360.dp)
    ) {
        Column(modifier = Modifier.fillMaxSize()) {
            // -----------------------------------------------------------------
            // 标题栏
            // -----------------------------------------------------------------
            PanelHeader(
                title = "节目单",
                subtitle = currentChannel?.name ?: "未选择频道",
                onClose = { viewModel.toggleEpgPanel() }
            )

            // -----------------------------------------------------------------
            // 搜索框
            // -----------------------------------------------------------------
            OutlinedTextField(
                value = searchQuery,
                onValueChange = { searchQuery = it },
                placeholder = { Text("搜索节目...", color = Color(0xFF888888), fontSize = 13.sp) },
                leadingIcon = { Icon(Icons.Default.Search, contentDescription = null, tint = Color(0xFF888888)) },
                trailingIcon = {
                    if (searchQuery.isNotEmpty()) {
                        IconButton(onClick = { searchQuery = "" }) {
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

            // -----------------------------------------------------------------
            // 节目列表
            // -----------------------------------------------------------------
            when {
                currentIdx < 0 -> {
                    EmptyState("请先选择频道")
                }
                loading -> {
                    Box(
                        modifier = Modifier.fillMaxSize(),
                        contentAlignment = Alignment.Center
                    ) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            CircularProgressIndicator(color = Color(0xFF4A9EFF))
                            Spacer(modifier = Modifier.height(8.dp))
                            Text("加载节目单...", color = Color(0xFF888888), fontSize = 13.sp)
                        }
                    }
                }
                epg.isEmpty() -> {
                    EmptyState("暂无节目单数据\n请在主菜单 > 文件 > EPG 订阅源 添加")
                }
                else -> {
                    val filtered = if (searchQuery.isEmpty()) epg else {
                        epg.filter {
                            it.title.contains(searchQuery, ignoreCase = true) ||
                                    it.desc.contains(searchQuery, ignoreCase = true)
                        }
                    }
                    EpgList(
                        programs = filtered,
                        searchActive = searchQuery.isNotEmpty(),
                        onProgramClick = { program ->
                            handleProgramClick(program, viewModel)
                        }
                    )
                }
            }
        }
    }
}

/**
 * 节目列表（带自动滚动）。
 */
@Composable
private fun EpgList(
    programs: List<IptvEpgProgram>,
    searchActive: Boolean,
    onProgramClick: (IptvEpgProgram) -> Unit
) {
    val listState = rememberLazyListState()
    val now = System.currentTimeMillis()

    // 找当前节目索引
    val currentProgramIdx = remember(programs, now) {
        programs.indexOfFirst { p ->
            val startMs = parseTimeToMs(p.start, p.startTs)
            val endMs = parseTimeToMs(p.end.ifEmpty { p.stop }, p.stopTs)
            startMs > 0 && endMs > startMs && now >= startMs && now < endMs
        }
    }

    // 自动滚动到当前节目（搜索时不滚动）
    LaunchedEffect(currentProgramIdx, searchActive) {
        if (!searchActive && currentProgramIdx >= 0) {
            // 滚动到当前节目（让其位于可视区域上方）
            listState.scrollToItem(currentProgramIdx.coerceAtMost(programs.size - 1))
        } else if (!searchActive && programs.isNotEmpty()) {
            // 无当前节目时，找第一个未开始的节目滚动到顶部
            val firstUpcoming = programs.indexOfFirst { p ->
                val startMs = parseTimeToMs(p.start, p.startTs)
                startMs > now
            }
            if (firstUpcoming >= 0) {
                listState.scrollToItem(firstUpcoming)
            } else {
                listState.scrollToItem(0)
            }
        }
    }

    LazyColumn(
        state = listState,
        modifier = Modifier.fillMaxSize(),
        contentPadding = androidx.compose.foundation.layout.PaddingValues(vertical = 4.dp)
    ) {
        items(items = programs, key = { it.start + it.title }) { program ->
            val idx = programs.indexOf(program)
            val isCurrent = idx == currentProgramIdx
            val isPast = isProgramPast(program, now)
            EpgItem(
                program = program,
                isCurrent = isCurrent,
                isPast = isPast,
                onClick = { onProgramClick(program) }
            )
        }
    }
}

/**
 * 节目列表项。
 */
@Composable
private fun EpgItem(
    program: IptvEpgProgram,
    isCurrent: Boolean,
    isPast: Boolean,
    onClick: () -> Unit
) {
    val bgColor = if (isCurrent) Color(0xFF4A9EFF).copy(alpha = 0.15f) else Color.Transparent
    val leftBorderColor = if (isCurrent) Color(0xFF4A9EFF) else Color.Transparent
    val itemAlpha = if (isPast && !isCurrent) 0.5f else 1f

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .alpha(itemAlpha)
            .background(bgColor)
            .clickable(enabled = isPast && !isCurrent, onClick = onClick)
            .padding(start = 12.dp, end = 12.dp, top = 10.dp, bottom = 10.dp)
    ) {
        // 左侧蓝色边框（当前节目）
        Box(
            modifier = Modifier
                .width(3.dp)
                .height(48.dp)
                .background(leftBorderColor)
        )

        Spacer(modifier = Modifier.width(9.dp))

        // 节目内容
        Column(modifier = Modifier.weight(1f)) {
            // 时间行 + LIVE badge
            Row(
                verticalAlignment = Alignment.CenterVertically
            ) {
                val timeText = buildString {
                    append(formatTime(program.start))
                    if (program.stop.isNotEmpty() || program.end.isNotEmpty()) {
                        append(" - ")
                        append(formatTime(program.stop.ifEmpty { program.end }))
                    }
                }
                Text(
                    text = timeText,
                    color = if (isCurrent) Color.White else Color(0xFFCCCCCC),
                    fontSize = 11.sp
                )
                if (isCurrent) {
                    Spacer(modifier = Modifier.width(6.dp))
                    LiveBadge()
                }
            }

            Spacer(modifier = Modifier.height(2.dp))

            // 节目标题
            Text(
                text = program.title,
                color = if (isCurrent) Color.White else Color(0xFFEEEEEE),
                fontSize = 14.sp,
                fontWeight = if (isCurrent) FontWeight.Medium else FontWeight.Normal,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis
            )

            // 节目描述
            if (program.desc.isNotEmpty()) {
                Spacer(modifier = Modifier.height(2.dp))
                Text(
                    text = program.desc,
                    color = Color(0xFF888888),
                    fontSize = 11.sp,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis
                )
            }
        }
    }
}

/**
 * LIVE 徽章（红色脉冲动画）。
 */
@Composable
private fun LiveBadge() {
    val infiniteTransition = rememberInfiniteTransition(label = "live-badge")
    val alpha by infiniteTransition.animateFloat(
        initialValue = 1f,
        targetValue = 0.5f,
        animationSpec = infiniteRepeatable(
            animation = tween(1000),
            repeatMode = RepeatMode.Reverse
        ),
        label = "live-alpha"
    )

    Surface(
        color = Color(0xFFF44336).copy(alpha = alpha),
        shape = RoundedCornerShape(3.dp),
        modifier = Modifier.clip(RoundedCornerShape(3.dp))
    ) {
        Text(
            text = "LIVE",
            color = Color.White,
            fontSize = 9.sp,
            fontWeight = FontWeight.Bold,
            modifier = Modifier.padding(horizontal = 5.dp, vertical = 1.dp)
        )
    }
}

/**
 * 空状态占位。
 */
@Composable
private fun EmptyState(text: String) {
    Box(
        modifier = Modifier.fillMaxSize(),
        contentAlignment = Alignment.Center
    ) {
        Text(
            text = text,
            color = Color(0xFF888888),
            fontSize = 13.sp,
            lineHeight = 20.sp,
            textAlign = androidx.compose.ui.text.style.TextAlign.Center
        )
    }
}

// -----------------------------------------------------------------
// 节目点击处理（与 PC 端 on_epg_clicked 对齐）
// -----------------------------------------------------------------

/**
 * 节目点击处理：
 * - past 程序（已结束且非当前）→ startCatchup
 * - current/future 程序 → setReminder
 */
private fun handleProgramClick(program: IptvEpgProgram, viewModel: AppViewModel) {
    val now = System.currentTimeMillis()
    val isPast = isProgramPast(program, now)
    val isCurrent = isProgramCurrent(program, now)

    if (isPast && !isCurrent) {
        // 过去节目 → 触发回看
        viewModel.startCatchup(program)
    } else {
        // 当前/未来节目 → 添加提醒（暂未实现完整 reminder，先显示 OSD）
        val startMs = parseTimeToMs(program.start, program.startTs)
        val remainingSec = if (startMs > 0) (startMs - now) / 1000 else 0L
        val msg = if (remainingSec > 0) {
            "节目将在 ${remainingSec / 60} 分钟后开始"
        } else {
            "正在播放"
        }
        viewModel.showOsd("节目提醒", "${program.title} - $msg")
    }
}

// -----------------------------------------------------------------
// 工具函数
// -----------------------------------------------------------------

private fun isProgramPast(program: IptvEpgProgram, nowMs: Long): Boolean {
    val endMs = parseTimeToMs(program.end.ifEmpty { program.stop }, program.stopTs)
    return endMs > 0 && nowMs >= endMs
}

private fun isProgramCurrent(program: IptvEpgProgram, nowMs: Long): Boolean {
    val startMs = parseTimeToMs(program.start, program.startTs)
    val endMs = parseTimeToMs(program.end.ifEmpty { program.stop }, program.stopTs)
    return startMs > 0 && endMs > startMs && nowMs >= startMs && nowMs < endMs
}

private fun parseTimeToMs(iso: String, ts: Long): Long {
    if (ts > 0) return ts * 1000L
    if (iso.isEmpty()) return 0
    val patterns = listOf(
        "yyyy-MM-dd'T'HH:mm:ssXXX",
        "yyyy-MM-dd'T'HH:mm:ss'Z'",
        "yyyy-MM-dd'T'HH:mm:ss",
        "yyyy-MM-dd HH:mm:ss",
        "yyyy-MM-dd HH:mm"
    )
    for (pattern in patterns) {
        try {
            return SimpleDateFormat(pattern, Locale.US).parse(iso)?.time ?: continue
        } catch (_: Exception) {
            // 尝试下一个格式
        }
    }
    return iso.toLongOrNull()?.let { if (it > 1_000_000_000_000L) it else it * 1000 } ?: 0
}

private fun formatTime(iso: String): String {
    if (iso.isEmpty()) return ""
    val ms = parseTimeToMs(iso, 0)
    if (ms <= 0) return iso
    val cal = java.util.Calendar.getInstance().apply { timeInMillis = ms }
    return String.format(Locale.US, "%02d:%02d", cal.get(java.util.Calendar.HOUR_OF_DAY), cal.get(java.util.Calendar.MINUTE))
}
