package com.iptv.scanner.editor.pro.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
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
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.runtime.collectAsState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.Divider
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.iptv.scanner.editor.pro.data.IptvChannel
import com.iptv.scanner.editor.pro.ui.AppViewModel.ChannelTab
import com.iptv.scanner.editor.pro.ui.theme.tvFocusBorder

/**
 * 频道列表面板：5 个 tab + 搜索 + 分组过滤 + LazyColumn。
 *
 * 与 PC 端 mobile/index.html panelChannels 对齐：
 * - 5 个 tab：订阅/本地/收藏/历史/队列
 * - 搜索框：输入即过滤（name/group 包含关键字）
 * - 分组过滤器（仅 SUB/LOCAL tab 显示）
 * - 列表项：圆点 + 名称 + 分组 meta + 当前播放高亮
 * - 点击列表项 → playChannel(idx)
 *
 * PHONE 模式：右侧抽屉（60% 宽，最大 380dp）
 * TV 模式：右侧抽屉（360dp 宽，DPAD 焦点导航）
 */
@Composable
fun ChannelsPanel(viewModel: AppViewModel) {
    val tab by viewModel.channelsTab.collectAsState()
    val searchQuery by viewModel.searchQuery.collectAsState()
    val selectedGroup by viewModel.selectedGroup.collectAsState()
    val groups by viewModel.groups.collectAsState()
    val currentIdx by viewModel.currentIdx.collectAsState()
    val channels by viewModel.channels.collectAsState()
    val favorites by viewModel.favorites.collectAsState()
    val history by viewModel.history.collectAsState()
    val queue by viewModel.queue.collectAsState()

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
                title = "频道列表",
                subtitle = "${channels.size} 个频道",
                onClose = { viewModel.toggleChannelsPanel() }
            )

            // -----------------------------------------------------------------
            // 5 个 Tab
            // -----------------------------------------------------------------
            ChannelTabsRow(
                currentTab = tab,
                onTabSelected = { viewModel.setChannelsTab(it) }
            )

            // -----------------------------------------------------------------
            // 搜索框
            // -----------------------------------------------------------------
            OutlinedTextField(
                value = searchQuery,
                onValueChange = { viewModel.setSearchQuery(it) },
                placeholder = { Text("搜索频道...", color = Color(0xFF888888), fontSize = 13.sp) },
                leadingIcon = { Icon(Icons.Default.Search, contentDescription = null, tint = Color(0xFF888888)) },
                trailingIcon = {
                    if (searchQuery.isNotEmpty()) {
                        IconButton(onClick = { viewModel.setSearchQuery("") }, modifier = Modifier.tvFocusBorder()) {
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
            // 分组过滤器（仅 SUB/LOCAL tab 显示）
            // -----------------------------------------------------------------
            if (tab == ChannelTab.SUB || tab == ChannelTab.LOCAL) {
                GroupFilterRow(
                    groups = groups,
                    selectedGroup = selectedGroup,
                    onGroupSelected = { viewModel.setSelectedGroup(it) }
                )
            }

            Divider(color = Color(0xFF2A2A2A))

            // -----------------------------------------------------------------
            // 频道列表（LazyColumn）
            // -----------------------------------------------------------------
            val filteredChannels = remember(tab, searchQuery, selectedGroup, channels, favorites, history, queue) {
                viewModel.getFilteredChannels()
            }

            if (filteredChannels.isEmpty()) {
                Box(
                    modifier = Modifier.fillMaxSize(),
                    contentAlignment = Alignment.Center
                ) {
                    Text(
                        text = when (tab) {
                            ChannelTab.SUB -> "暂无频道\n请在主菜单 > 文件 > 订阅源管理 添加"
                            ChannelTab.LOCAL -> "暂无本地频道"
                            ChannelTab.FAV -> "暂无收藏\n点击频道右侧星标添加"
                            ChannelTab.HIST -> "暂无历史\n播放后会自动记录"
                            ChannelTab.QUEUE -> "暂无队列\n长按频道可加入队列"
                        },
                        color = Color(0xFF888888),
                        fontSize = 13.sp,
                        lineHeight = 20.sp,
                        textAlign = androidx.compose.ui.text.style.TextAlign.Center
                    )
                }
            } else {
                LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = androidx.compose.foundation.layout.PaddingValues(vertical = 4.dp)
                ) {
                    items(
                        items = filteredChannels,
                        key = { (channel, idx) -> idx }
                    ) { (channel, idx) ->
                        ChannelListItem(
                            channel = channel,
                            isPlaying = idx == currentIdx,
                            isFavorite = favorites.contains(idx),
                            showGroupMeta = tab == ChannelTab.SUB || tab == ChannelTab.LOCAL,
                            onClick = { viewModel.playChannel(idx) }
                        )
                    }
                }
            }
        }
    }
}

/**
 * 面板标题栏（统一组件）。
 */
@Composable
fun PanelHeader(
    title: String,
    subtitle: String = "",
    onClose: () -> Unit
) {
    Surface(
        color = Color(0xFF1F1F1F),
        modifier = Modifier.fillMaxWidth()
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 12.dp, vertical = 10.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = title,
                    style = MaterialTheme.typography.titleMedium,
                    color = Color.White,
                    fontWeight = FontWeight.SemiBold
                )
                if (subtitle.isNotEmpty()) {
                    Text(
                        text = subtitle,
                        style = MaterialTheme.typography.bodySmall,
                        color = Color(0xFF888888)
                    )
                }
            }
            IconButton(onClick = onClose, modifier = Modifier.tvFocusBorder()) {
                Icon(Icons.Default.Close, contentDescription = "关闭", tint = Color.White)
            }
        }
    }
}

/**
 * 5 个 Tab 行（订阅/本地/收藏/历史/队列）。
 */
@Composable
private fun ChannelTabsRow(
    currentTab: ChannelTab,
    onTabSelected: (ChannelTab) -> Unit
) {
    val tabs = listOf(
        ChannelTab.SUB to "订阅",
        ChannelTab.LOCAL to "本地",
        ChannelTab.FAV to "收藏",
        ChannelTab.HIST to "历史",
        ChannelTab.QUEUE to "队列"
    )
    Surface(
        color = Color(0xFF1A1A1A),
        modifier = Modifier.fillMaxWidth()
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 8.dp, vertical = 4.dp),
            horizontalArrangement = Arrangement.spacedBy(4.dp)
        ) {
            tabs.forEach { (tab, label) ->
                val isSelected = currentTab == tab
                FilterChip(
                    selected = isSelected,
                    onClick = { onTabSelected(tab) },
                    label = { Text(label, fontSize = 12.sp) },
                    modifier = Modifier.weight(1f),
                    colors = androidx.compose.material3.FilterChipDefaults.filterChipColors(
                        selectedContainerColor = Color(0xFF4A9EFF),
                        selectedLabelColor = Color.White,
                        containerColor = Color.Transparent,
                        labelColor = Color(0xFFCCCCCC)
                    )
                )
            }
        }
    }
}

/**
 * 分组过滤器行（横向滚动的 chip 列表）。
 */
@Composable
private fun GroupFilterRow(
    groups: List<String>,
    selectedGroup: String,
    onGroupSelected: (String) -> Unit
) {
    if (groups.isEmpty()) return

    Surface(
        color = Color(0xFF161616),
        modifier = Modifier.fillMaxWidth()
    ) {
        androidx.compose.foundation.lazy.LazyRow(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 8.dp, vertical = 4.dp),
            horizontalArrangement = Arrangement.spacedBy(6.dp),
            contentPadding = androidx.compose.foundation.layout.PaddingValues(horizontal = 4.dp)
        ) {
            item {
                FilterChip(
                    selected = selectedGroup.isEmpty(),
                    onClick = { onGroupSelected("") },
                    label = { Text("全部", fontSize = 11.sp) },
                    colors = groupChipColors(selectedGroup.isEmpty())
                )
            }
            items(groups) { group ->
                FilterChip(
                    selected = selectedGroup == group,
                    onClick = { onGroupSelected(group) },
                    label = { Text(group, fontSize = 11.sp, maxLines = 1) },
                    colors = groupChipColors(selectedGroup == group)
                )
            }
        }
    }
}

@Composable
private fun groupChipColors(selected: Boolean) = androidx.compose.material3.FilterChipDefaults.filterChipColors(
    selectedContainerColor = Color(0xFF4A9EFF),
    selectedLabelColor = Color.White,
    containerColor = Color(0xFF2A2A2A),
    labelColor = Color(0xFFCCCCCC)
)

/**
 * 频道列表项。
 */
@Composable
private fun ChannelListItem(
    channel: IptvChannel,
    isPlaying: Boolean,
    isFavorite: Boolean,
    showGroupMeta: Boolean,
    onClick: () -> Unit
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .tvFocusBorder()
            .clickable { onClick() }
            .padding(horizontal = 12.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        // 圆点（playing 时高亮蓝色，否则灰色）
        Box(
            modifier = Modifier
                .size(8.dp)
                .clip(CircleShape)
                .background(if (isPlaying) Color(0xFF4A9EFF) else Color(0xFF444444))
        )

        Spacer(modifier = Modifier.width(10.dp))

        // 频道名 + 分组 meta
        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = channel.name,
                color = if (isPlaying) Color(0xFF6A9EFF) else Color.White,
                fontSize = 14.sp,
                fontWeight = if (isPlaying) FontWeight.Medium else FontWeight.Normal,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis
            )
            if (showGroupMeta && channel.group.isNotEmpty()) {
                Text(
                    text = channel.group,
                    color = Color(0xFF888888),
                    fontSize = 11.sp,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
            }
        }

        // 收藏标记
        if (isFavorite) {
            Spacer(modifier = Modifier.width(8.dp))
            Text("★", color = Color(0xFFFFC107), fontSize = 12.sp)
        }
    }
}

// 导入缺失的 Composable（androidx.compose.foundation.lazy.LazyRow）
