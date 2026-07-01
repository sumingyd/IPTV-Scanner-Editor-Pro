package com.iptv.scanner.editor.pro.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.drawIntoCanvas
import androidx.compose.ui.graphics.nativeCanvas
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalDensity
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
 * EPG 时间线视图：多频道 × 24h 横向网格。
 *
 * 与 PC 端 EpgTimelineDialog + Web 端 renderEpgTimeline 对齐：
 * - 左侧频道名列表（固定宽度，与主网格同步垂直滚动）
 * - 顶部时间刻度（固定高度，与主网格同步水平滚动）
 * - 主网格 Canvas 自绘（节目块 + 网格线 + 当前时间竖线）
 * - 节目块点击：过去→回看，当前/未来→提醒（与 EpgPanel handleProgramClick 一致）
 * - 日期切换（±7 天）
 * - 频道范围筛选（全部/收藏/当前分组，最多 30 频道）
 */
@Composable
fun EpgTimelinePanel(viewModel: AppViewModel) {
    val rows by viewModel.epgTimelineRows.collectAsState()
    val loading by viewModel.epgTimelineLoading.collectAsState()
    val range by viewModel.epgTimelineRange.collectAsState()
    val dateOffset by viewModel.epgTimelineDateOffset.collectAsState()
    val status by viewModel.epgTimelineStatus.collectAsState()
    val currentIdx by viewModel.currentIdx.collectAsState()
    val density = LocalDensity.current

    // 选中日期（基于今天 + offset）
    val selectedDate = remember(dateOffset) {
        val cal = Calendar.getInstance().apply { add(Calendar.DAY_OF_MONTH, dateOffset) }
        SimpleDateFormat("yyyy-MM-dd E", Locale.CHINA).format(Date(cal.timeInMillis))
    }

    // 滚动状态（频道名列 + 主网格共享垂直滚动；时间刻度 + 主网格共享水平滚动）
    val horizontalScroll = rememberScrollState()
    val verticalScroll = rememberScrollState()

    // 自动滚动到当前时间（首次加载或日期变化时，仅今天滚动）
    LaunchedEffect(rows, dateOffset) {
        if (rows.isNotEmpty() && dateOffset == 0) {
            val now = System.currentTimeMillis()
            val cal = Calendar.getInstance().apply {
                set(Calendar.HOUR_OF_DAY, 0)
                set(Calendar.MINUTE, 0)
                set(Calendar.SECOND, 0)
                set(Calendar.MILLISECOND, 0)
            }
            val dayStartMs = cal.timeInMillis
            if (now in dayStartMs until (dayStartMs + 24 * 3600 * 1000L)) {
                val hoursFromStart = (now - dayStartMs) / 3600000.0
                val hourWidthPx = with(density) { HOUR_WIDTH_DP.toPx() }
                val targetPx = (hoursFromStart * hourWidthPx).toInt() - 200
                horizontalScroll.scrollTo(targetPx.coerceAtLeast(0))
            }
        }
    }

    Surface(color = Color(0xF0121212), modifier = Modifier.fillMaxSize()) {
        Column(modifier = Modifier.fillMaxSize().padding(12.dp)) {
            // -----------------------------------------------------------------
            // 标题栏 + 工具栏
            // -----------------------------------------------------------------
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = "EPG 时间线",
                        style = MaterialTheme.typography.headlineSmall,
                        color = Color.White
                    )
                    Text(
                        text = "$selectedDate  |  $status",
                        color = Color(0xFF888888),
                        fontSize = 12.sp
                    )
                }
                Row(verticalAlignment = Alignment.CenterVertically) {
                    // 日期切换
                    IconButton(
                        onClick = { viewModel.setEpgTimelineDateOffset(dateOffset - 1) },
                        modifier = Modifier.tvFocusBorder()
                    ) {
                        Text("◀", color = Color.White, fontSize = 14.sp)
                    }
                    Text(
                        text = when (dateOffset) {
                            0 -> "今天"
                            -1 -> "昨天"
                            1 -> "明天"
                            else -> "${dateOffset}天"
                        },
                        color = Color.White,
                        fontSize = 12.sp,
                        modifier = Modifier.padding(horizontal = 6.dp)
                    )
                    IconButton(
                        onClick = { viewModel.setEpgTimelineDateOffset(dateOffset + 1) },
                        modifier = Modifier.tvFocusBorder()
                    ) {
                        Text("▶", color = Color.White, fontSize = 14.sp)
                    }
                    Spacer(modifier = Modifier.width(8.dp))
                    // 刷新
                    IconButton(
                        onClick = { viewModel.loadEpgTimeline() },
                        modifier = Modifier.tvFocusBorder()
                    ) {
                        Icon(Icons.Default.Refresh, contentDescription = "刷新", tint = Color.White)
                    }
                    // 关闭
                    IconButton(
                        onClick = { viewModel.toggleEpgTimelinePanel() },
                        modifier = Modifier.tvFocusBorder()
                    ) {
                        Icon(Icons.Default.Close, contentDescription = "关闭", tint = Color.White)
                    }
                }
            }

            Spacer(modifier = Modifier.height(8.dp))

            // 频道范围 FilterChip
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                FilterChip(
                    selected = range == AppViewModel.EpgTimelineRange.ALL,
                    onClick = { viewModel.setEpgTimelineRange(AppViewModel.EpgTimelineRange.ALL) },
                    label = { Text("全部频道", fontSize = 11.sp) },
                    modifier = Modifier.tvFocusBorder()
                )
                FilterChip(
                    selected = range == AppViewModel.EpgTimelineRange.FAVORITES,
                    onClick = { viewModel.setEpgTimelineRange(AppViewModel.EpgTimelineRange.FAVORITES) },
                    label = { Text("仅收藏", fontSize = 11.sp) },
                    modifier = Modifier.tvFocusBorder()
                )
                FilterChip(
                    selected = range == AppViewModel.EpgTimelineRange.CURRENT_GROUP,
                    onClick = { viewModel.setEpgTimelineRange(AppViewModel.EpgTimelineRange.CURRENT_GROUP) },
                    label = { Text("当前分组", fontSize = 11.sp) },
                    modifier = Modifier.tvFocusBorder()
                )
            }

            Spacer(modifier = Modifier.height(8.dp))

            // -----------------------------------------------------------------
            // 主体：时间线网格
            // -----------------------------------------------------------------
            when {
                loading && rows.isEmpty() -> {
                    Box(
                        modifier = Modifier.fillMaxSize(),
                        contentAlignment = Alignment.Center
                    ) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            CircularProgressIndicator(color = Color(0xFF4A9EFF))
                            Spacer(modifier = Modifier.height(8.dp))
                            Text("加载 EPG 数据...", color = Color(0xFF888888), fontSize = 13.sp)
                        }
                    }
                }
                rows.isEmpty() -> {
                    Box(
                        modifier = Modifier.fillMaxSize(),
                        contentAlignment = Alignment.Center
                    ) {
                        Text(
                            text = status.ifEmpty { "暂无 EPG 数据\n请在主菜单 > 文件 > EPG 订阅源 添加" },
                            color = Color(0xFF888888),
                            fontSize = 13.sp,
                            lineHeight = 20.sp
                        )
                    }
                }
                else -> {
                    TimelineGrid(
                        rows = rows,
                        currentIdx = currentIdx,
                        dateOffset = dateOffset,
                        horizontalScroll = horizontalScroll,
                        verticalScroll = verticalScroll,
                        onProgramClick = { program ->
                            handleTimelineProgramClick(program, viewModel)
                        }
                    )
                }
            }
        }
    }
}

// -----------------------------------------------------------------
// 时间线网格
// -----------------------------------------------------------------

/** 网格常量（与 PC 端 HOUR_WIDTH=120 对齐，手机端窄一些） */
private val HOUR_WIDTH_DP = 60.dp
private val ROW_HEIGHT_DP = 36.dp
private val CHANNEL_NAME_WIDTH_DP = 100.dp
private val TIME_HEADER_HEIGHT_DP = 28.dp

/**
 * 时间线网格布局：
 * - 左上角空白（频道名列与时间刻度交叉处）
 * - 顶部时间刻度（水平滚动）
 * - 左侧频道名列（垂直滚动）
 * - 主网格 Canvas（双向滚动 + 点击检测）
 */
@Composable
private fun TimelineGrid(
    rows: List<AppViewModel.EpgTimelineRow>,
    currentIdx: Int,
    dateOffset: Int,
    horizontalScroll: androidx.compose.foundation.ScrollState,
    verticalScroll: androidx.compose.foundation.ScrollState,
    onProgramClick: (IptvEpgProgram) -> Unit
) {
    val density = LocalDensity.current
    val hourWidthPx = with(density) { HOUR_WIDTH_DP.toPx() }
    val rowHeightPx = with(density) { ROW_HEIGHT_DP.toPx() }

    // 选中日期的 0:00 时间戳（毫秒）
    val dayStartMs = remember(dateOffset) {
        val cal = Calendar.getInstance().apply {
            add(Calendar.DAY_OF_MONTH, dateOffset)
            set(Calendar.HOUR_OF_DAY, 0)
            set(Calendar.MINUTE, 0)
            set(Calendar.SECOND, 0)
            set(Calendar.MILLISECOND, 0)
        }
        cal.timeInMillis
    }
    val now = System.currentTimeMillis()

    // 网格总尺寸
    val gridWidthPx = hourWidthPx * 24
    val gridHeightPx = rowHeightPx * rows.size

    // 文本画笔（避免在 Canvas 内重复创建）
    val timeTextPaint = remember(density) {
        android.graphics.Paint().apply {
            color = android.graphics.Color.parseColor("#888888")
            textSize = with(density) { 11.sp.toPx() }
            isAntiAlias = true
        }
    }
    val programTextPaint = remember(density) {
        android.graphics.Paint().apply {
            color = android.graphics.Color.WHITE
            textSize = with(density) { 10.sp.toPx() }
            isAntiAlias = true
        }
    }
    val programTextPaintCurrent = remember(density) {
        android.graphics.Paint().apply {
            color = android.graphics.Color.WHITE
            textSize = with(density) { 10.sp.toPx() }
            isFakeBoldText = true
            isAntiAlias = true
        }
    }
    val nowLabelPaint = remember(density) {
        android.graphics.Paint().apply {
            color = android.graphics.Color.parseColor("#F44336")
            textSize = with(density) { 10.sp.toPx() }
            isFakeBoldText = true
            isAntiAlias = true
        }
    }

    Column(modifier = Modifier.fillMaxSize()) {
        // -----------------------------------------------------------------
        // 顶部：时间刻度行（左上角空白 + 时间刻度水平滚动）
        // -----------------------------------------------------------------
        Row(modifier = Modifier.fillMaxWidth()) {
            // 左上角空白
            Box(
                modifier = Modifier
                    .width(CHANNEL_NAME_WIDTH_DP)
                    .height(TIME_HEADER_HEIGHT_DP)
                    .background(Color(0xFF1A1A1A))
            )
            // 时间刻度（水平滚动同步）
            Box(
                modifier = Modifier
                    .weight(1f)
                    .height(TIME_HEADER_HEIGHT_DP)
                    .horizontalScroll(horizontalScroll)
            ) {
                Canvas(
                    modifier = Modifier.size(
                        width = with(density) { gridWidthPx.toDp() },
                        height = TIME_HEADER_HEIGHT_DP
                    )
                ) {
                    // 背景
                    drawRect(Color(0xFF1A1A1A))
                    // 每 2 小时一刻度
                    drawIntoCanvas { canvas ->
                        for (h in 0..24 step 2) {
                            val x = h * hourWidthPx
                            // 刻度线
                            drawLine(
                                color = Color(0xFF333333),
                                start = Offset(x, size.height - 4),
                                end = Offset(x, size.height),
                                strokeWidth = 1f
                            )
                            // 文本 HH:00
                            canvas.nativeCanvas.drawText(
                                String.format(Locale.US, "%02d:00", h % 24),
                                x + 4,
                                size.height / 2 + timeTextPaint.textSize / 3,
                                timeTextPaint
                            )
                        }
                    }
                }
            }
        }

        // -----------------------------------------------------------------
        // 主体：频道名列 + 网格（同步垂直滚动）
        // -----------------------------------------------------------------
        Row(modifier = Modifier.weight(1f)) {
            // 左侧频道名列（垂直滚动同步）
            Box(
                modifier = Modifier
                    .width(CHANNEL_NAME_WIDTH_DP)
                    .verticalScroll(verticalScroll)
            ) {
                Column {
                    rows.forEach { row ->
                        val isCurrent = row.channelIdx == currentIdx
                        Box(
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(ROW_HEIGHT_DP)
                                .background(
                                    if (isCurrent) Color(0xFF4A9EFF).copy(alpha = 0.15f)
                                    else Color(0xFF1A1A1A)
                                )
                                .padding(horizontal = 8.dp),
                            contentAlignment = Alignment.CenterStart
                        ) {
                            Text(
                                text = row.channelName,
                                color = if (isCurrent) Color(0xFF4A9EFF) else Color(0xFFCCCCCC),
                                fontSize = 11.sp,
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis,
                                fontWeight = if (isCurrent) FontWeight.Medium else FontWeight.Normal
                            )
                        }
                    }
                }
            }

            // 主网格 Canvas（双向滚动 + 点击检测）
            Box(
                modifier = Modifier
                    .weight(1f)
                    .horizontalScroll(horizontalScroll)
                    .verticalScroll(verticalScroll)
            ) {
                Canvas(
                    modifier = Modifier
                        .size(
                            width = with(density) { gridWidthPx.toDp() },
                            height = with(density) { gridHeightPx.toDp() }
                        )
                        .pointerInput(rows, dateOffset) {
                            detectTapGestures { offset ->
                                handleGridTap(
                                    offset = offset,
                                    rows = rows,
                                    dayStartMs = dayStartMs,
                                    hourWidthPx = hourWidthPx,
                                    rowHeightPx = rowHeightPx,
                                    onProgramClick = onProgramClick
                                )
                            }
                        }
                ) {
                    // 背景
                    drawRect(Color(0xFF0F0F0F))

                    // 水平网格线（行分隔）
                    for (i in 0..rows.size) {
                        val y = i * rowHeightPx
                        drawLine(
                            color = Color(0xFF222222),
                            start = Offset(0f, y),
                            end = Offset(gridWidthPx, y),
                            strokeWidth = 1f
                        )
                    }

                    // 垂直网格线（小时分隔，每 2 小时加粗）
                    for (h in 0..24) {
                        val x = h * hourWidthPx
                        val color = if (h % 2 == 0) Color(0xFF333333) else Color(0xFF222222)
                        drawLine(
                            color = color,
                            start = Offset(x, 0f),
                            end = Offset(x, gridHeightPx),
                            strokeWidth = if (h % 2 == 0) 1f else 0.8f
                        )
                    }

                    // 节目块
                    drawIntoCanvas { canvas ->
                        rows.forEachIndexed { rowIdx, row ->
                            val y = rowIdx * rowHeightPx
                            row.programs.forEach { program ->
                                val startMs = parseTimelineTimeMs(program.start, program.startTs)
                                val endMs = parseTimelineTimeMs(
                                    program.end.ifEmpty { program.stop }, program.stopTs
                                )
                                if (startMs <= 0 || endMs <= startMs) return@forEach

                                val x1 = ((startMs - dayStartMs).coerceAtLeast(0) / 3600000.0).toFloat() * hourWidthPx
                                val x2 = ((endMs - dayStartMs).coerceAtMost(24 * 3600000L) / 3600000.0).toFloat() * hourWidthPx
                                val blockWidth = (x2 - x1).coerceAtLeast(1f)
                                val isCurrent = now in startMs until endMs
                                val isPast = now >= endMs

                                // 节目块背景
                                val bgColor = when {
                                    isCurrent -> Color(0xFF4A9EFF)
                                    isPast -> Color(0xFF2A2A2A)
                                    else -> Color(0xFF2A4A8A)
                                }
                                drawRoundRect(
                                    color = bgColor,
                                    topLeft = Offset(x1 + 1f, y + 2f),
                                    size = Size(blockWidth - 2f, rowHeightPx - 4f),
                                    cornerRadius = CornerRadius(3f, 3f)
                                )

                                // 节目标题（宽度 > 40px 才绘制）
                                if (blockWidth > 40f) {
                                    val textPaint = if (isCurrent) programTextPaintCurrent else programTextPaint
                                    val title = ellipsizeText(program.title, textPaint, blockWidth - 8f)
                                    canvas.nativeCanvas.drawText(
                                        title,
                                        x1 + 4f,
                                        y + rowHeightPx / 2 + textPaint.textSize / 3,
                                        textPaint
                                    )
                                }
                            }
                        }
                    }

                    // 当前时间竖线（仅今天显示）
                    val dayEndMs = dayStartMs + 24 * 3600000L
                    if (now in dayStartMs until dayEndMs) {
                        val nowX = ((now - dayStartMs) / 3600000.0).toFloat() * hourWidthPx
                        drawLine(
                            color = Color(0xFFF44336),
                            start = Offset(nowX, 0f),
                            end = Offset(nowX, gridHeightPx),
                            strokeWidth = 2f
                        )
                        // 当前时间标签
                        drawIntoCanvas { canvas ->
                            val timeLabel = SimpleDateFormat("HH:mm", Locale.US).format(Date(now))
                            canvas.nativeCanvas.drawText(timeLabel, nowX + 4f, 12f, nowLabelPaint)
                        }
                    }
                }
            }
        }
    }
}

// -----------------------------------------------------------------
// 点击处理
// -----------------------------------------------------------------

/**
 * 网格点击命中检测：根据点击坐标计算频道行和时间段，查找命中的节目。
 */
private fun handleGridTap(
    offset: Offset,
    rows: List<AppViewModel.EpgTimelineRow>,
    dayStartMs: Long,
    hourWidthPx: Float,
    rowHeightPx: Float,
    onProgramClick: (IptvEpgProgram) -> Unit
) {
    val rowIdx = (offset.y / rowHeightPx).toInt()
    if (rowIdx < 0 || rowIdx >= rows.size) return

    val row = rows[rowIdx]
    // 点击位置对应的时间戳（毫秒）
    val tapMs = dayStartMs + (offset.x / hourWidthPx * 3600000L).toLong()

    // 查找包含该时间点的节目
    val hit = row.programs.firstOrNull { p ->
        val startMs = parseTimelineTimeMs(p.start, p.startTs)
        val endMs = parseTimelineTimeMs(p.end.ifEmpty { p.stop }, p.stopTs)
        startMs > 0 && endMs > startMs && tapMs >= startMs && tapMs < endMs
    }
    if (hit != null) {
        onProgramClick(hit)
    }
}

/**
 * 节目点击处理（与 EpgPanel.kt handleProgramClick 对齐）：
 * - past 程序 → startCatchup
 * - current/future 程序 → toggleReminder
 */
private fun handleTimelineProgramClick(program: IptvEpgProgram, viewModel: AppViewModel) {
    val now = System.currentTimeMillis()
    val endMs = parseTimelineTimeMs(program.end.ifEmpty { program.stop }, program.stopTs)
    val startMs = parseTimelineTimeMs(program.start, program.startTs)
    val isPast = endMs > 0 && now >= endMs
    val isCurrent = startMs > 0 && endMs > startMs && now >= startMs && now < endMs

    if (isPast && !isCurrent) {
        viewModel.startCatchup(program)
    } else {
        viewModel.toggleReminder(program, viewModel.currentChannel.value)
    }
}

// -----------------------------------------------------------------
// 工具函数
// -----------------------------------------------------------------

/** 时间解析（与 EpgPanel.kt parseTimeToMs 对齐） */
private fun parseTimelineTimeMs(iso: String, ts: Long): Long {
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
        }
    }
    return iso.toLongOrNull()?.let { if (it > 1_000_000_000_000L) it else it * 1000 } ?: 0
}

/** 文本截断（避免节目标题超出节目块宽度） */
private fun ellipsizeText(text: String, paint: android.graphics.Paint, maxWidth: Float): String {
    if (paint.measureText(text) <= maxWidth) return text
    val ellipsis = "..."
    val ellipsisWidth = paint.measureText(ellipsis)
    var end = text.length
    while (end > 0 && paint.measureText(text, 0, end) + ellipsisWidth > maxWidth) {
        end--
    }
    return if (end > 0) text.substring(0, end) + ellipsis else ""
}
