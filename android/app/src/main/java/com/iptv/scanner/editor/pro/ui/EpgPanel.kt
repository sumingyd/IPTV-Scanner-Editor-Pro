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
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowLeft
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Notifications
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
import com.iptv.scanner.editor.pro.ui.theme.tvFocusBorder
import java.text.SimpleDateFormat
import java.util.Calendar
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
    // EPG 日期切换（±7 天，0=今天）
    var epgDateOffset by remember { mutableStateOf(0) }

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
            // 日期切换栏（±7 天）
            // -----------------------------------------------------------------
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 12.dp, vertical = 4.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                IconButton(
                    onClick = { if (epgDateOffset > -7) epgDateOffset-- },
                    modifier = Modifier.tvFocusBorder()
                ) {
                    Icon(
                        Icons.AutoMirrored.Filled.KeyboardArrowLeft,
                        contentDescription = "前一天",
                        tint = if (epgDateOffset > -7) Color.White else Color(0xFF555555)
                    )
                }
                Text(
                    text = formatEpgDateLabel(epgDateOffset),
                    color = if (epgDateOffset == 0) Color(0xFF4A9EFF) else Color.White,
                    fontSize = 13.sp,
                    fontWeight = FontWeight.Medium
                )
                IconButton(
                    onClick = { if (epgDateOffset < 7) epgDateOffset++ },
                    modifier = Modifier.tvFocusBorder()
                ) {
                    Icon(
                        Icons.AutoMirrored.Filled.KeyboardArrowRight,
                        contentDescription = "后一天",
                        tint = if (epgDateOffset < 7) Color.White else Color(0xFF555555)
                    )
                }
            }

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
                    // 按日期过滤节目（±7 天范围）
                    val cal = Calendar.getInstance().apply {
                        add(Calendar.DAY_OF_MONTH, epgDateOffset)
                        set(Calendar.HOUR_OF_DAY, 0)
                        set(Calendar.MINUTE, 0)
                        set(Calendar.SECOND, 0)
                        set(Calendar.MILLISECOND, 0)
                    }
                    val dayStartMs = cal.timeInMillis
                    cal.add(Calendar.DAY_OF_MONTH, 1)
                    val dayEndMs = cal.timeInMillis

                    val dateFiltered = epg.filter { p ->
                        val startMs = parseTimeToMs(p.start, p.startTs)
                        val endMs = parseTimeToMs(p.end.ifEmpty { p.stop }, p.stopTs)
                        startMs > 0 && endMs > startMs && startMs < dayEndMs && endMs > dayStartMs
                    }

                    if (dateFiltered.isEmpty()) {
                        EmptyState("该日期无节目数据")
                    } else {
                        val filtered = if (searchQuery.isEmpty()) dateFiltered else {
                            dateFiltered.filter {
                                it.title.contains(searchQuery, ignoreCase = true) ||
                                        it.desc.contains(searchQuery, ignoreCase = true)
                            }
                        }
                        EpgList(
                            programs = filtered,
                            searchActive = searchQuery.isNotEmpty(),
                            hasReminder = { program -> viewModel.isReminderSet(program) },
                            onProgramClick = { program ->
                                handleProgramClick(program, viewModel)
                            }
                        )
                    }
                }
            }
        }
    }
}

/**
 * 格式化 EPG 日期标签。
 * offset=0 → "今天"，offset=-1 → "昨天"，offset=1 → "明天"，其他 → "MM-dd 周X"
 */
private fun formatEpgDateLabel(offset: Int): String {
    if (offset == 0) return "今天"
    if (offset == -1) return "昨天"
    if (offset == 1) return "明天"
    val cal = Calendar.getInstance().apply { add(Calendar.DAY_OF_MONTH, offset) }
    val dateFmt = SimpleDateFormat("MM-dd", Locale.getDefault())
    val weekFmt = SimpleDateFormat("E", Locale.CHINESE)
    return "${dateFmt.format(cal.time)} ${weekFmt.format(cal.time)}"
}

/**
 * 节目列表（带自动滚动）。
 */
@Composable
private fun EpgList(
    programs: List<IptvEpgProgram>,
    searchActive: Boolean,
    hasReminder: (IptvEpgProgram) -> Boolean,
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
                hasReminder = hasReminder(program),
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
    hasReminder: Boolean,
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
            .clickable(onClick = onClick)
            .tvFocusBorder()
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
            // 时间行 + LIVE badge + 提醒铃铛
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
                if (hasReminder) {
                    Spacer(modifier = Modifier.width(6.dp))
                    ReminderBadge()
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
 * 提醒徽章（铃铛图标）。
 */
@Composable
private fun ReminderBadge() {
    Surface(
        color = Color(0xFFFFC107).copy(alpha = 0.2f),
        shape = RoundedCornerShape(3.dp),
        modifier = Modifier.clip(RoundedCornerShape(3.dp))
    ) {
        Icon(
            imageVector = Icons.Default.Notifications,
            contentDescription = "已设提醒",
            tint = Color(0xFFFFC107),
            modifier = Modifier
                .padding(horizontal = 3.dp, vertical = 1.dp)
                .size(10.dp)
        )
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
 * - current/future 程序 → toggleReminder（设置/取消提醒）
 */
private fun handleProgramClick(program: IptvEpgProgram, viewModel: AppViewModel) {
    val now = System.currentTimeMillis()
    val isPast = isProgramPast(program, now)
    val isCurrent = isProgramCurrent(program, now)

    if (isPast && !isCurrent) {
        // 过去节目 → 触发回看
        viewModel.startCatchup(program)
    } else {
        // 当前/未来节目 → 切换提醒
        viewModel.toggleReminder(program, viewModel.currentChannel.value)
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
