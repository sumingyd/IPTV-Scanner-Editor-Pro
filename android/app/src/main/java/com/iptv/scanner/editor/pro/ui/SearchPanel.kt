package com.iptv.scanner.editor.pro.ui

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
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Tv
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilterChip
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
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.iptv.scanner.editor.pro.ui.theme.tvFocusBorder
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * 全局搜索面板：与 PC 端 UnifiedSearchDialog + Web 端 search 面板对齐。
 *
 * 搜索范围：
 * - 频道：name / group / url（与 PC 端一致）
 * - 节目：title / desc（遍历 epgCache，上限 200 条）
 *
 * 结果点击：
 * - 频道：切台并播放
 * - 节目：切台，过去节目触发 catchup（与 PC 端 _on_epg_search_program_selected 对齐）
 *
 * 防抖 250ms（与 PC 端一致）。
 */
@Composable
fun SearchPanel(viewModel: AppViewModel) {
    val results by viewModel.searchResults.collectAsState()
    val loading by viewModel.searchLoading.collectAsState()
    val scope by viewModel.searchScope.collectAsState()

    var query by remember { mutableStateOf("") }

    // 输入防抖：query 变化时触发 ViewModel.performSearch（内部已有 250ms 防抖）
    LaunchedEffect(query) {
        viewModel.performSearch(query)
    }

    Surface(color = Color(0xF0121212), modifier = Modifier.fillMaxSize()) {
        Column(modifier = Modifier.fillMaxSize().padding(12.dp)) {
            // -----------------------------------------------------------------
            // 标题栏
            // -----------------------------------------------------------------
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = "全局搜索",
                    style = MaterialTheme.typography.headlineSmall,
                    color = Color.White
                )
                IconButton(
                    onClick = { viewModel.toggleSearchPanel() },
                    modifier = Modifier.tvFocusBorder()
                ) {
                    Icon(Icons.Default.Close, contentDescription = "关闭", tint = Color.White)
                }
            }

            Spacer(modifier = Modifier.height(8.dp))

            // -----------------------------------------------------------------
            // 搜索框
            // -----------------------------------------------------------------
            OutlinedTextField(
                value = query,
                onValueChange = { query = it },
                placeholder = {
                    Text(
                        "搜索频道名 / 分组 / URL / 节目标题...",
                        color = Color(0xFF888888),
                        fontSize = 13.sp
                    )
                },
                leadingIcon = {
                    Icon(Icons.Default.Search, contentDescription = null, tint = Color(0xFF888888))
                },
                trailingIcon = {
                    if (query.isNotEmpty()) {
                        IconButton(onClick = { query = "" }, modifier = Modifier.tvFocusBorder()) {
                            Icon(Icons.Default.Close, contentDescription = "清空", tint = Color(0xFF888888))
                        }
                    }
                },
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(8.dp),
                singleLine = true
            )

            Spacer(modifier = Modifier.height(8.dp))

            // -----------------------------------------------------------------
            // 范围筛选 + 状态
            // -----------------------------------------------------------------
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    FilterChip(
                        selected = scope == AppViewModel.SearchScope.ALL,
                        onClick = { viewModel.setSearchScope(AppViewModel.SearchScope.ALL) },
                        label = { Text("全部", fontSize = 11.sp) }
                    )
                    FilterChip(
                        selected = scope == AppViewModel.SearchScope.CHANNELS,
                        onClick = { viewModel.setSearchScope(AppViewModel.SearchScope.CHANNELS) },
                        label = { Text("频道", fontSize = 11.sp) }
                    )
                    FilterChip(
                        selected = scope == AppViewModel.SearchScope.PROGRAMS,
                        onClick = { viewModel.setSearchScope(AppViewModel.SearchScope.PROGRAMS) },
                        label = { Text("节目", fontSize = 11.sp) }
                    )
                }
                Row(verticalAlignment = Alignment.CenterVertically) {
                    if (loading) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(14.dp),
                            strokeWidth = 2.dp,
                            color = Color(0xFF4A9EFF)
                        )
                        Spacer(modifier = Modifier.width(6.dp))
                    }
                    Text(
                        text = "${results.size} 条结果",
                        color = Color(0xFF888888),
                        fontSize = 11.sp
                    )
                }
            }

            Spacer(modifier = Modifier.height(8.dp))

            // -----------------------------------------------------------------
            // 结果列表
            // -----------------------------------------------------------------
            when {
                query.isBlank() -> {
                    Box(
                        modifier = Modifier.fillMaxSize(),
                        contentAlignment = Alignment.Center
                    ) {
                        Text(
                            text = "输入关键词搜索频道和节目",
                            color = Color(0xFF888888),
                            fontSize = 13.sp
                        )
                    }
                }
                !loading && results.isEmpty() -> {
                    Box(
                        modifier = Modifier.fillMaxSize(),
                        contentAlignment = Alignment.Center
                    ) {
                        Text(
                            text = "无搜索结果",
                            color = Color(0xFF888888),
                            fontSize = 13.sp
                        )
                    }
                }
                else -> {
                    LazyColumn(modifier = Modifier.fillMaxSize()) {
                        items(items = results, key = { resultKey(it) }) { result ->
                            SearchResultRow(result) { viewModel.onSearchResultClick(result) }
                        }
                    }
                }
            }
        }
    }
}

/** 生成结果项的唯一 key */
private fun resultKey(result: AppViewModel.SearchResult): String = when (result) {
    is AppViewModel.SearchResult.ChannelResult -> "ch_${result.idx}"
    is AppViewModel.SearchResult.ProgramResult ->
        "pg_${result.channelIdx}_${result.program.start}_${result.program.title}"
}

/**
 * 搜索结果行：
 * - 频道：[TV图标] 频道名  [分组]
 * - 节目：[HH:MM] 节目标题  (频道名)
 */
@Composable
private fun SearchResultRow(
    result: AppViewModel.SearchResult,
    onClick: () -> Unit
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .tvFocusBorder()
            .padding(vertical = 10.dp, horizontal = 4.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        when (result) {
            is AppViewModel.SearchResult.ChannelResult -> {
                // 频道图标
                Icon(
                    imageVector = Icons.Default.Tv,
                    contentDescription = null,
                    tint = Color(0xFF4A9EFF),
                    modifier = Modifier.size(16.dp)
                )
                Spacer(modifier = Modifier.width(10.dp))
                // 频道名
                Text(
                    text = result.channel.name,
                    color = Color.White,
                    fontSize = 14.sp,
                    modifier = Modifier.weight(1f),
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
                // 分组
                if (result.channel.group.isNotEmpty()) {
                    Spacer(modifier = Modifier.width(8.dp))
                    Surface(
                        color = Color(0xFF2A4A8A).copy(alpha = 0.4f),
                        shape = RoundedCornerShape(4.dp),
                        modifier = Modifier.clip(RoundedCornerShape(4.dp))
                    ) {
                        Text(
                            text = result.channel.group,
                            color = Color(0xFF88AAFF),
                            fontSize = 10.sp,
                            modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp),
                            maxLines = 1
                        )
                    }
                }
            }
            is AppViewModel.SearchResult.ProgramResult -> {
                // 时间
                val timeText = remember(result.program.start) {
                    formatProgramTime(result.program.start)
                }
                Text(
                    text = timeText,
                    color = Color(0xFF4A9EFF),
                    fontSize = 12.sp,
                    modifier = Modifier.width(50.dp)
                )
                Spacer(modifier = Modifier.width(10.dp))
                // 节目标题
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = result.program.title,
                        color = Color.White,
                        fontSize = 13.sp,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                    Text(
                        text = result.channelName,
                        color = Color(0xFF888888),
                        fontSize = 11.sp,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                }
            }
        }
    }
}

/** 格式化节目时间（HH:MM） */
private fun formatProgramTime(iso: String): String {
    if (iso.isEmpty()) return "--:--"
    val patterns = listOf(
        "yyyy-MM-dd'T'HH:mm:ssXXX",
        "yyyy-MM-dd'T'HH:mm:ss'Z'",
        "yyyy-MM-dd'T'HH:mm:ss",
        "yyyy-MM-dd HH:mm:ss",
        "yyyy-MM-dd HH:mm"
    )
    for (pattern in patterns) {
        try {
            val date = SimpleDateFormat(pattern, Locale.US).parse(iso) ?: continue
            val cal = java.util.Calendar.getInstance().apply { time = date }
            return String.format(Locale.US, "%02d:%02d", cal.get(java.util.Calendar.HOUR_OF_DAY), cal.get(java.util.Calendar.MINUTE))
        } catch (_: Exception) {
        }
    }
    return iso.take(5)
}
