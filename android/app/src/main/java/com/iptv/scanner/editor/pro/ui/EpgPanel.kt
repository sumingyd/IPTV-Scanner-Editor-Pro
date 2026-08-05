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
import androidx.compose.foundation.layout.systemBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.itemsIndexed
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
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalConfiguration
import android.content.res.Configuration
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.iptv.scanner.editor.pro.data.IptvEpgProgram
import com.iptv.scanner.editor.pro.player.CatchupHelper
import com.iptv.scanner.editor.pro.ui.theme.tvFocusBorder
import com.iptv.scanner.editor.pro.ui.theme.tvTextField
import kotlinx.coroutines.delay
import java.text.SimpleDateFormat
import java.util.Calendar
import java.util.Date
import java.util.Locale

/**
 * EPG 节目单面板：与 PC 端 panelEPG 对齐。
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
fun EpgPanel(viewModel: AppViewModel, compact: Boolean = false) {
    val currentChannel by viewModel.currentChannel.collectAsState()
    val playbackState by viewModel.playbackState.collectAsState()
    val epgTrimmed by viewModel.currentEpg.collectAsState()
    val epg = remember(epgTrimmed, viewModel.epgCacheVersion.value) {
        viewModel.getFullEpgForCurrent()
    }
    val loading by viewModel.epgLoading.collectAsState()
    val currentIdx by viewModel.currentIdx.collectAsState()

    // 自动检测横屏模式：横屏时使用更窄的侧边栏布局
    val configuration = LocalConfiguration.current
    val isLandscape = configuration.orientation == Configuration.ORIENTATION_LANDSCAPE
    val effectiveCompact = compact || isLandscape


    // EPG 日期切换（±7 天，0=今天）
    var epgDateOffset by remember { mutableStateOf(0) }

    // TV 焦点管理：面板打开时请求焦点到关闭按钮，确保 DPAD 可操作。
    val closeFocusRequester = remember { FocusRequester() }
    LaunchedEffect(Unit) {
        kotlinx.coroutines.delay(50)
        kotlin.runCatching { closeFocusRequester.requestFocus() }
    }

    val surfaceModifier = if (effectiveCompact) {
        // compact/横屏模式：侧边栏布局，宽度 35%，最大 420dp
        Modifier
            .fillMaxHeight()
            .fillMaxWidth(0.35f)
            .widthIn(max = 420.dp)
    } else {
        Modifier
            .fillMaxHeight()
            .fillMaxWidth(0.92f)
            .widthIn(max = 380.dp)
    }

    Surface(
        color = MaterialTheme.colorScheme.surface,
        modifier = surfaceModifier
    ) {
        Column(modifier = Modifier.fillMaxSize().then(if (effectiveCompact) Modifier else Modifier.systemBarsPadding())) {
            // 标题栏已移除（活动区域内显示不需要标题）

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
                        tint = if (epgDateOffset > -7) MaterialTheme.colorScheme.onSurface else MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
                Text(
                    text = formatEpgDateLabel(epgDateOffset),
                    color = if (epgDateOffset == 0) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurface,
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
                        tint = if (epgDateOffset < 7) MaterialTheme.colorScheme.onSurface else MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }

            // 搜索框已移除

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
                            CircularProgressIndicator(color = MaterialTheme.colorScheme.primary)
                            Spacer(modifier = Modifier.height(8.dp))
                            Text("加载节目单...", color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 13.sp)
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
                        EpgList(
                            programs = dateFiltered,
                            searchActive = false,
                            hasReminder = { program -> viewModel.isReminderSet(program) },
                            supportsCatchup = currentChannel?.let { CatchupHelper.isCatchupEnabled(it) } ?: false,
                            catchupProgram = playbackState.catchupProgram?.program,
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
    supportsCatchup: Boolean,
    catchupProgram: IptvEpgProgram? = null,
    onProgramClick: (IptvEpgProgram) -> Unit
) {
    val listState = rememberLazyListState()

    // 每秒刷新 `now`，确保当前节目高亮随时间推移自动更新
    var now by remember { mutableStateOf(System.currentTimeMillis()) }
    LaunchedEffect(Unit) {
        while (true) {
            delay(1_000L)
            now = System.currentTimeMillis()
        }
    }

    // 找高亮节目索引：回看模式下高亮选定的节目，否则高亮当前时间的节目
    val currentProgramIdx = remember(programs, now, catchupProgram) {
        if (catchupProgram != null) {
            // 回看/时移模式：高亮用户选定的节目
            programs.indexOfFirst { p -> p.start == catchupProgram.start && p.title == catchupProgram.title }
        } else {
            // 直播模式：高亮当前时间正在播放的节目
            programs.indexOfFirst { p ->
                val startMs = parseTimeToMs(p.start, p.startTs)
                val endMs = parseTimeToMs(p.end.ifEmpty { p.stop }, p.stopTs)
                startMs > 0 && endMs > startMs && now >= startMs && now < endMs
            }
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
        itemsIndexed(items = programs, key = { _, p -> p.start + p.title }) { idx, program ->
            val isCurrent = idx == currentProgramIdx
            val isPast = isProgramPast(program, now)
            EpgItem(
                program = program,
                isCurrent = isCurrent,
                isPast = isPast,
                hasReminder = hasReminder(program),
                supportsCatchup = supportsCatchup,
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
    supportsCatchup: Boolean,
    onClick: () -> Unit
) {
    val bgColor = if (isCurrent) MaterialTheme.colorScheme.primary.copy(alpha = 0.15f) else Color.Transparent
    val leftBorderColor = if (isCurrent) MaterialTheme.colorScheme.primary else Color.Transparent
    val itemAlpha = if (isPast && !isCurrent) 0.5f else 1f

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .alpha(itemAlpha)
            .background(bgColor)
            .tvFocusBorder()
            .clickable(onClick = onClick)
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
                    color = if (isCurrent) MaterialTheme.colorScheme.onSurface else MaterialTheme.colorScheme.onSurfaceVariant,
                    fontSize = 11.sp
                )
                if (isCurrent) {
                    Spacer(modifier = Modifier.width(6.dp))
                    LiveBadge()
                }
                // 回看/时移标识（仅当频道真正支持回看时显示）
                if (supportsCatchup && (isPast || isCurrent)) {
                    Spacer(modifier = Modifier.width(6.dp))
                    CatchupBadge(isCurrent = isCurrent)
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
                color = if (isCurrent) MaterialTheme.colorScheme.onSurface else MaterialTheme.colorScheme.onSurfaceVariant,
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
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
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
            color = MaterialTheme.colorScheme.onSurface,
            fontSize = 9.sp,
            fontWeight = FontWeight.Bold,
            modifier = Modifier.padding(horizontal = 5.dp, vertical = 1.dp)
        )
    }
}

/**
 * 回看/时移徽章（与移动端 channelSupportsCatchup 对齐，仅支持回看的频道显示）。
 * isCurrent=true → "可时移"（蓝色），isCurrent=false → "可回放"（紫色）
 */
@Composable
private fun CatchupBadge(isCurrent: Boolean) {
    val bgColor = if (isCurrent) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.tertiary
    val text = if (isCurrent) "可时移" else "可回放"
    Surface(
        color = bgColor.copy(alpha = 0.15f),
        shape = RoundedCornerShape(3.dp),
        modifier = Modifier.clip(RoundedCornerShape(3.dp))
    ) {
        Text(
            text = text,
            color = bgColor,
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
            color = MaterialTheme.colorScheme.onSurfaceVariant,
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
 * - past 程序（已结束且非当前）且频道支持回看 → startCatchup
 * - 其他情况 → toggleReminder（设置/取消提醒）
 */
private fun handleProgramClick(program: IptvEpgProgram, viewModel: AppViewModel) {
    val now = System.currentTimeMillis()
    val isPast = isProgramPast(program, now)
    val isCurrent = isProgramCurrent(program, now)

    if (isPast && !isCurrent) {
        // 过去节目 → 检查频道是否支持回看
        val channel = viewModel.currentChannel.value
        if (channel != null && CatchupHelper.isCatchupEnabled(channel)) {
            viewModel.startCatchup(program)
        } else {
            // 不支持回看 → 回退到提醒
            viewModel.toggleReminder(program, channel)
        }
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

private val DATE_FORMATS by lazy {
    listOf(
        "yyyy-MM-dd'T'HH:mm:ssXXX",
        "yyyy-MM-dd'T'HH:mm:ss'Z'",
        "yyyy-MM-dd'T'HH:mm:ss",
        "yyyy-MM-dd HH:mm:ss",
        "yyyy-MM-dd HH:mm"
    ).map { java.text.SimpleDateFormat(it, Locale.US) }
}

private fun parseTimeToMs(iso: String, ts: Long): Long {
    if (ts > 0) return ts * 1000L
    if (iso.isEmpty()) return 0
    for (fmt in DATE_FORMATS) {
        try {
            return fmt.parse(iso)?.time ?: continue
        } catch (_: Exception) {
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
