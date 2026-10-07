package com.iptv.scanner.editor.pro.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.focusable
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
import androidx.compose.foundation.layout.systemBarsPadding
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
import androidx.compose.ui.graphics.toArgb
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import kotlinx.coroutines.delay
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.drawIntoCanvas
import androidx.compose.ui.graphics.nativeCanvas
import androidx.compose.ui.input.key.Key
import androidx.compose.ui.input.key.KeyEventType
import androidx.compose.ui.input.key.key
import androidx.compose.ui.input.key.onPreviewKeyEvent
import androidx.compose.ui.input.key.type
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.iptv.scanner.editor.pro.data.IptvEpgProgram
import com.iptv.scanner.editor.pro.ui.theme.tvFocusBorder
import kotlinx.coroutines.launch
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
    if (LocalAptvStyle.current) {
        EpgTimelinePanelAptv(viewModel)
        return
    }
    val rows by viewModel.epgTimelineRows.collectAsState()
    val loading by viewModel.epgTimelineLoading.collectAsState()
    val range by viewModel.epgTimelineRange.collectAsState()
    val dateOffset by viewModel.epgTimelineDateOffset.collectAsState()
    val status by viewModel.epgTimelineStatus.collectAsState()
    val currentIdx by viewModel.currentIdx.collectAsState()
    val density = LocalDensity.current

    // TV 焦点管理：面板打开时请求焦点到关闭按钮，确保 DPAD 可操作。
    val closeFocusRequester = remember { FocusRequester() }
    LaunchedEffect(Unit) {
        kotlinx.coroutines.delay(50)
        kotlin.runCatching { closeFocusRequester.requestFocus() }
    }

    // 选中日期（基于今天 + offset）
    val selectedDate = remember(dateOffset) {
        val cal = Calendar.getInstance().apply { add(Calendar.DAY_OF_MONTH, dateOffset) }
        SimpleDateFormat("yyyy-MM-dd E", Locale.CHINA).format(Date(cal.timeInMillis))
    }

    // 滚动状态（频道名列 + 主网格共享垂直滚动；时间刻度 + 主网格共享水平滚动）
    val horizontalScroll = rememberScrollState()
    val verticalScroll = rememberScrollState()

    var now by remember { mutableStateOf(System.currentTimeMillis()) }
    LaunchedEffect(Unit) {
        while (true) {
            delay(60_000L)
            now = System.currentTimeMillis()
        }
    }

    // 自动滚动到当前时间（首次加载或日期变化时，仅今天滚动）
    LaunchedEffect(rows, dateOffset) {
        if (rows.isNotEmpty() && dateOffset == 0) {
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

    Surface(color = Color.Transparent, modifier = Modifier.fillMaxSize()) {
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
color = MaterialTheme.colorScheme.onSurface,
maxLines = 1
)
Text(
text = "$selectedDate  |  $status",
color = MaterialTheme.colorScheme.onSurfaceVariant,
fontSize = 12.sp,
maxLines = 1
)
                }
                Row(verticalAlignment = Alignment.CenterVertically) {
                    // 日期切换
                    IconButton(
                        onClick = { viewModel.setEpgTimelineDateOffset(dateOffset - 1) },
                        modifier = Modifier.tvFocusBorder()
                    ) {
                        Text("◀", color = MaterialTheme.colorScheme.onSurface, fontSize = 14.sp)
                    }
                    Text(
                        text = when (dateOffset) {
                            0 -> "今天"
                            -1 -> "昨天"
                            1 -> "明天"
                            else -> "${dateOffset}天"
                        },
                        color = MaterialTheme.colorScheme.onSurface,
                        fontSize = 12.sp,
                        modifier = Modifier.padding(horizontal = 6.dp)
                    )
                    IconButton(
                        onClick = { viewModel.setEpgTimelineDateOffset(dateOffset + 1) },
                        modifier = Modifier.tvFocusBorder()
                    ) {
                        Text("▶", color = MaterialTheme.colorScheme.onSurface, fontSize = 14.sp)
                    }
                    Spacer(modifier = Modifier.width(8.dp))
                    // 刷新
                    IconButton(
                        onClick = { viewModel.loadEpgTimeline() },
                        modifier = Modifier.tvFocusBorder()
                    ) {
                        Icon(Icons.Default.Refresh, contentDescription = "刷新", tint = MaterialTheme.colorScheme.onSurface)
                    }
                    // 关闭
                    IconButton(
                        onClick = { viewModel.toggleEpgTimelinePanel() },
                        modifier = Modifier
                            .tvFocusBorder()
                            .focusRequester(closeFocusRequester)
                    ) {
                        Icon(Icons.Default.Close, contentDescription = "关闭", tint = MaterialTheme.colorScheme.onSurface)
                    }
                }
            }

            Spacer(modifier = Modifier.height(8.dp))

            // 频道范围 FilterChip
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                FilterChip(
                    selected = range == EpgTimelineRange.ALL,
                    onClick = { viewModel.setEpgTimelineRange(EpgTimelineRange.ALL) },
                    label = { Text("全部频道", fontSize = 11.sp) },
                    modifier = Modifier.tvFocusBorder()
                )
                FilterChip(
                    selected = range == EpgTimelineRange.FAVORITES,
                    onClick = { viewModel.setEpgTimelineRange(EpgTimelineRange.FAVORITES) },
                    label = { Text("仅收藏", fontSize = 11.sp) },
                    modifier = Modifier.tvFocusBorder()
                )
                FilterChip(
                    selected = range == EpgTimelineRange.CURRENT_GROUP,
                    onClick = { viewModel.setEpgTimelineRange(EpgTimelineRange.CURRENT_GROUP) },
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
                            CircularProgressIndicator(color = MaterialTheme.colorScheme.primary)
                            Spacer(modifier = Modifier.height(8.dp))
                            Text("加载 EPG 数据...", color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 13.sp)
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
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
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
// APTV（iOS 风格）版本
// -----------------------------------------------------------------

/**
 * APTV（iOS 风格）EPG 时间线面板：单列布局，圆角分组卡片 + iOS 选择行。
 * 仅在竖屏 APTV 模式下使用，横屏/TV 仍走 [EpgTimelinePanel] 原有布局。
 */
@Composable
private fun EpgTimelinePanelAptv(viewModel: AppViewModel) {
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

    var now by remember { mutableStateOf(System.currentTimeMillis()) }
    LaunchedEffect(Unit) {
        while (true) {
            delay(60_000L)
            now = System.currentTimeMillis()
        }
    }

    // 自动滚动到当前时间（首次加载或日期变化时，仅今天滚动）
    LaunchedEffect(rows, dateOffset) {
        if (rows.isNotEmpty() && dateOffset == 0) {
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

    Surface(color = MaterialTheme.colorScheme.surface.copy(alpha = 0.92f), modifier = Modifier.fillMaxSize()) {
        Column(modifier = Modifier.fillMaxSize().systemBarsPadding()) {
            // 标题栏 + 工具栏（日期切换 / 刷新 / 关闭）
            AptvPanelHeader(
                title = "EPG 时间线",
                subtitle = "$selectedDate  |  $status",
                onClose = { viewModel.toggleEpgTimelinePanel() },
                actions = {
                    // 日期切换
                    IconButton(
                        onClick = { viewModel.setEpgTimelineDateOffset(dateOffset - 1) }
                    ) {
                        Text("◀", color = MaterialTheme.colorScheme.onSurface, fontSize = 14.sp)
                    }
                    Text(
                        text = when (dateOffset) {
                            0 -> "今天"
                            -1 -> "昨天"
                            1 -> "明天"
                            else -> "${dateOffset}天"
                        },
                        color = MaterialTheme.colorScheme.onSurface,
                        fontSize = 12.sp,
                        modifier = Modifier.padding(horizontal = 6.dp)
                    )
                    IconButton(
                        onClick = { viewModel.setEpgTimelineDateOffset(dateOffset + 1) }
                    ) {
                        Text("▶", color = MaterialTheme.colorScheme.onSurface, fontSize = 14.sp)
                    }
                    Spacer(modifier = Modifier.width(8.dp))
                    // 刷新
                    IconButton(onClick = { viewModel.loadEpgTimeline() }) {
                        Icon(Icons.Default.Refresh, contentDescription = "刷新", tint = MaterialTheme.colorScheme.onSurface)
                    }
                }
            )

            // 频道范围选择（FilterChip → SelectionGroup）
            SettingsGroup("频道范围") {
                SelectionGroup(
                    title = "频道范围",
                    options = listOf(
                        "ALL" to "全部频道",
                        "FAVORITES" to "仅收藏",
                        "CURRENT_GROUP" to "当前分组"
                    ),
                    selectedKey = range.name,
                    onSelect = { key ->
                        val r = when (key) {
                            "FAVORITES" -> EpgTimelineRange.FAVORITES
                            "CURRENT_GROUP" -> EpgTimelineRange.CURRENT_GROUP
                            else -> EpgTimelineRange.ALL
                        }
                        viewModel.setEpgTimelineRange(r)
                    }
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
                            CircularProgressIndicator(color = MaterialTheme.colorScheme.primary)
                            Spacer(modifier = Modifier.height(8.dp))
                            Text("加载 EPG 数据...", color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 13.sp)
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
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
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
 * - 主网格 Canvas（双向滚动 + 点击检测 + TV 方向键导航）
 *
 * TV 焦点导航：
 * - 网格 Box 可聚焦，方向键移动选中节目（selectedRow + selectedProgramIdx）
 * - DPAD_CENTER/ENTER 触发 onProgramClick
 * - 触摸模式仍可用 detectTapGestures 点击
 */
@Composable
private fun TimelineGrid(
    rows: List<EpgTimelineRow>,
    currentIdx: Int,
    dateOffset: Int,
    horizontalScroll: androidx.compose.foundation.ScrollState,
    verticalScroll: androidx.compose.foundation.ScrollState,
    onProgramClick: (IptvEpgProgram) -> Unit
) {
    val density = LocalDensity.current
    val hourWidthPx = with(density) { HOUR_WIDTH_DP.toPx() }
    val rowHeightPx = with(density) { ROW_HEIGHT_DP.toPx() }
    val scope = rememberCoroutineScope()

    // TV 焦点状态：选中的行索引和该行内的节目索引
    var selectedRow by remember { mutableStateOf(-1) }
    var selectedProgramIdx by remember { mutableStateOf(-1) }
    val gridFocusRequester = remember { FocusRequester() }

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

    // 主题颜色捕获（添加为 remember key，主题切换时重新创建 Paint）
    val onSurfaceColor = MaterialTheme.colorScheme.onSurface
    val onSurfaceVariantColor = MaterialTheme.colorScheme.onSurfaceVariant
    val outlineColor = MaterialTheme.colorScheme.outline
    val secondaryColor = MaterialTheme.colorScheme.secondary
    val surfaceVariantArgb = MaterialTheme.colorScheme.surfaceVariant.toArgb()
    val errorColor = MaterialTheme.colorScheme.error
    val tertiaryColor = MaterialTheme.colorScheme.tertiary
    val primaryColor = MaterialTheme.colorScheme.primary
    val surfaceArgb = MaterialTheme.colorScheme.surface.toArgb()
    val onSurfaceVariantArgb = onSurfaceVariantColor.toArgb()
    val outlineArgb = outlineColor.toArgb()

    // 文本画笔（避免在 Canvas 内重复创建）
    val timeTextPaint = remember(density, onSurfaceVariantArgb) {
        android.graphics.Paint().apply {
            color = onSurfaceVariantArgb
            textSize = with(density) { 11.sp.toPx() }
            isAntiAlias = true
        }
    }
    val programTextPaint = remember(density, onSurfaceColor) {
        android.graphics.Paint().apply {
            color = onSurfaceColor.toArgb()
            textSize = with(density) { 10.sp.toPx() }
            isAntiAlias = true
        }
    }
    val programTextPaintCurrent = remember(density, onSurfaceColor) {
        android.graphics.Paint().apply {
            color = onSurfaceColor.toArgb()
            textSize = with(density) { 10.sp.toPx() }
            isFakeBoldText = true
            isAntiAlias = true
        }
    }
    val nowLabelPaint = remember(density) {
        android.graphics.Paint().apply {
            color = errorColor.toArgb()
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
                    .background(Color(surfaceVariantArgb))
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
                    drawRect(Color(surfaceVariantArgb))
                    // 每 2 小时一刻度
                    drawIntoCanvas { canvas ->
                        for (h in 0..24 step 2) {
                            val x = h * hourWidthPx
                            // 刻度线
                            drawLine(
                            color = Color(outlineArgb),
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
                                    if (isCurrent) MaterialTheme.colorScheme.primary.copy(alpha = 0.15f)
                                    else Color(surfaceVariantArgb)
                                )
                                .padding(horizontal = 8.dp),
                            contentAlignment = Alignment.CenterStart
                        ) {
                            Text(
                                text = row.channelName,
                                color = if (isCurrent) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant,
                                fontSize = 11.sp,
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis,
                                fontWeight = if (isCurrent) FontWeight.Medium else FontWeight.Normal
                            )
                        }
                    }
                }
            }

            // 主网格 Canvas（双向滚动 + 点击检测 + TV 方向键导航）
            Box(
                modifier = Modifier
                    .weight(1f)
                    .horizontalScroll(horizontalScroll)
                    .verticalScroll(verticalScroll)
                    .focusRequester(gridFocusRequester)
                    .focusable()
                    .onPreviewKeyEvent { e ->
                        if (e.type != KeyEventType.KeyDown) return@onPreviewKeyEvent false
                        when (e.key) {
                            Key.DirectionUp -> {
                                if (selectedRow > 0) {
                                    selectedRow--
                                    // 选中行的节目数可能不同，clamp selectedProgramIdx
                                    val progs = rows.getOrNull(selectedRow)?.programs ?: emptyList()
                                    if (selectedProgramIdx >= progs.size) selectedProgramIdx = (progs.size - 1).coerceAtLeast(0)
                                    // 滚动到选中行
                                    val target = selectedRow * rowHeightPx.toInt()
                                    scope.launch { kotlin.runCatching { verticalScroll.animateScrollTo(target) } }
                                    true
                                } else false
                            }
                            Key.DirectionDown -> {
                                if (selectedRow < rows.size - 1) {
                                    selectedRow++
                                    val progs = rows.getOrNull(selectedRow)?.programs ?: emptyList()
                                    if (selectedProgramIdx >= progs.size) selectedProgramIdx = (progs.size - 1).coerceAtLeast(0)
                                    val target = selectedRow * rowHeightPx.toInt()
                                    scope.launch { kotlin.runCatching { verticalScroll.animateScrollTo(target) } }
                                    true
                                } else false
                            }
                            Key.DirectionLeft -> {
                                val progs = rows.getOrNull(selectedRow)?.programs ?: emptyList()
                                if (selectedProgramIdx > 0) {
                                    selectedProgramIdx--
                                    // 滚动到选中节目
                                    val prog = progs.getOrNull(selectedProgramIdx)
                                    if (prog != null) {
                                        val startMs = parseTimelineTimeMs(prog.start, prog.startTs)
                                        val x = ((startMs - dayStartMs).coerceAtLeast(0) / 3600000.0).toFloat() * hourWidthPx
                                        val target = (x - 100).toInt().coerceAtLeast(0)
                                        scope.launch { kotlin.runCatching { horizontalScroll.animateScrollTo(target) } }
                                    }
                                    true
                                } else false
                            }
                            Key.DirectionRight -> {
                                val progs = rows.getOrNull(selectedRow)?.programs ?: emptyList()
                                if (selectedProgramIdx < progs.size - 1) {
                                    selectedProgramIdx++
                                    val prog = progs.getOrNull(selectedProgramIdx)
                                    if (prog != null) {
                                        val startMs = parseTimelineTimeMs(prog.start, prog.startTs)
                                        val x = ((startMs - dayStartMs).coerceAtLeast(0) / 3600000.0).toFloat() * hourWidthPx
                                        val target = (x - 100).toInt().coerceAtLeast(0)
                                        scope.launch { kotlin.runCatching { horizontalScroll.animateScrollTo(target) } }
                                    }
                                    true
                                } else false
                            }
                            Key.DirectionCenter, Key.Enter -> {
                                val prog = rows.getOrNull(selectedRow)?.programs?.getOrNull(selectedProgramIdx)
                                if (prog != null) {
                                    onProgramClick(prog)
                                    true
                                } else false
                            }
                            else -> false
                        }
                    }
            ) {
                Canvas(
                    modifier = Modifier
                        .size(
                            width = with(density) { gridWidthPx.toDp() },
                            height = with(density) { gridHeightPx.toDp() }
                        )
                        .pointerInput(rows, dateOffset) {
                            detectTapGestures { offset ->
                                // 触摸点击时也更新选中状态
                                val rowIdx = (offset.y / rowHeightPx).toInt()
                                if (rowIdx in rows.indices) {
                                    selectedRow = rowIdx
                                    val row = rows[rowIdx]
                                    val tapMs = dayStartMs + (offset.x / hourWidthPx * 3600000L).toLong()
                                    val progIdx = row.programs.indexOfFirst { p ->
                                        val s = parseTimelineTimeMs(p.start, p.startTs)
                                        val e = parseTimelineTimeMs(p.end.ifEmpty { p.stop }, p.stopTs)
                                        s > 0 && e > s && tapMs >= s && tapMs < e
                                    }
                                    if (progIdx >= 0) selectedProgramIdx = progIdx
                                }
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
                    drawRect(Color(surfaceArgb))

                    // 水平网格线（行分隔）
                    for (i in 0..rows.size) {
                        val y = i * rowHeightPx
                        drawLine(
                            color = Color(surfaceVariantArgb),
                            start = Offset(0f, y),
                            end = Offset(gridWidthPx, y),
                            strokeWidth = 1f
                        )
                    }

                    // 垂直网格线（小时分隔，每 2 小时加粗）
                    for (h in 0..24) {
                        val x = h * hourWidthPx
                        val color = if (h % 2 == 0) Color(outlineArgb) else Color(surfaceVariantArgb)
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
                            row.programs.forEachIndexed { progIdx, program ->
                                val startMs = parseTimelineTimeMs(program.start, program.startTs)
                                val endMs = parseTimelineTimeMs(
                                    program.end.ifEmpty { program.stop }, program.stopTs
                                )
                                if (startMs <= 0 || endMs <= startMs) return@forEachIndexed

                                val x1 = ((startMs - dayStartMs).coerceAtLeast(0) / 3600000.0).toFloat() * hourWidthPx
                                val x2 = ((endMs - dayStartMs).coerceAtMost(24 * 3600000L) / 3600000.0).toFloat() * hourWidthPx
                                val blockWidth = (x2 - x1).coerceAtLeast(1f)
                                val isCurrent = now in startMs until endMs
                                val isPast = now >= endMs
                                val isSelected = rowIdx == selectedRow && progIdx == selectedProgramIdx

                                // 节目块背景
                                val bgColor = when {
                                    isSelected -> tertiaryColor  // 选中：主题 tertiary
                                    isCurrent -> primaryColor     // 当前：主题 primary
                                    isPast -> Color(surfaceVariantArgb)  // 过去：随主题变
                                    else -> secondaryColor.copy(alpha = 0.3f)  // 普通：浅蓝
                                }
                                drawRoundRect(
                                    color = bgColor,
                                    topLeft = Offset(x1 + 1f, y + 2f),
                                    size = Size(blockWidth - 2f, rowHeightPx - 4f),
                                    cornerRadius = CornerRadius(3f, 3f)
                                )

                                // 选中边框（随主题自适应）
                                if (isSelected) {
                                    drawRoundRect(
                                        color = onSurfaceColor,
                                        topLeft = Offset(x1 + 1f, y + 2f),
                                        size = Size(blockWidth - 2f, rowHeightPx - 4f),
                                        cornerRadius = CornerRadius(3f, 3f),
                                        style = androidx.compose.ui.graphics.drawscope.Stroke(
                                            width = 2f
                                        )
                                    )
                                }

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
                            color = errorColor,
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
    rows: List<EpgTimelineRow>,
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
