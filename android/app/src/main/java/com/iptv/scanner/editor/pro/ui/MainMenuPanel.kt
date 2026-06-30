package com.iptv.scanner.editor.pro.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
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
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ExitToApp
import androidx.compose.material.icons.filled.CalendarMonth
import androidx.compose.material.icons.filled.ClosedCaption
import androidx.compose.material.icons.filled.Equalizer
import androidx.compose.material.icons.filled.Favorite
import androidx.compose.material.icons.filled.FileOpen
import androidx.compose.material.icons.filled.GraphicEq
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.Link
import androidx.compose.material.icons.filled.ListAlt
import androidx.compose.material.icons.filled.Movie
import androidx.compose.material.icons.filled.PlayCircle
import androidx.compose.material.icons.filled.Public
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.ScreenshotMonitor
import androidx.compose.material.icons.filled.SyncAlt
import androidx.compose.material.icons.filled.Tune
import androidx.compose.material.icons.filled.VideoSettings
import androidx.compose.material.icons.filled.ViewInAr
import androidx.compose.material.icons.filled.Web
import androidx.compose.material3.Icon
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/**
 * 主菜单面板：与 PC 端 mobile/index.html 主菜单（panelMenu）对齐。
 *
 * 2 个分组：
 * - 文件（6 项）：打开播放列表 / 打开网络流 / 打开本地视频 / 订阅源管理 / EPG 订阅源 / 频道映射
 * - 播放（15 项）：频道 / 节目单 EPG / 字幕 / 视频 / 音频 / 播放 / 截图 / A/V 同步 / 网络增强 /
 *   工具 / 视图 / 设置 / 关于 / 收藏 / 退出
 *
 * 当前阶段只实现入口结构和已实现功能（频道列表 / EPG / 收藏 / 退出），
 * 其余入口点击时显示 OSD 提示"功能开发中"，后续逐步补齐子面板。
 *
 * 与内存规则对齐：
 * - File operations (local files, URLs, video, subscription management) are accessed via '文件' group in main menu
 */
@Composable
fun MainMenuPanel(viewModel: AppViewModel) {
    val currentChannel by viewModel.currentChannel.collectAsState()
    val currentIdx by viewModel.currentIdx.collectAsState()
    val favorites by viewModel.favorites.collectAsState()

    val isFavorite = currentIdx >= 0 && favorites.contains(currentIdx)

    val sections = remember(currentIdx, isFavorite) {
        buildMenuSections(
            onOpenPlaylist = { viewModel.showOsd("打开播放列表", "功能开发中") },
            onOpenUrl = { viewModel.showOsd("打开网络流", "功能开发中") },
            onOpenLocalVideo = { viewModel.showOsd("打开本地视频", "功能开发中") },
            onSources = {
                viewModel.setSourceTab(AppViewModel.SourceTab.PLAYLIST)
                viewModel.toggleMenuPanel()
                viewModel.toggleSourceManager()
            },
            onEpgSources = {
                viewModel.setSourceTab(AppViewModel.SourceTab.EPG)
                viewModel.toggleMenuPanel()
                viewModel.toggleSourceManager()
            },
            onMapping = { viewModel.showOsd("频道映射", "功能开发中") },
            onChannels = {
                viewModel.toggleMenuPanel()
                viewModel.showChannelsPanel()
            },
            onEpg = {
                viewModel.toggleMenuPanel()
                viewModel.showEpgPanel()
            },
            onSubtitle = { viewModel.showOsd("字幕", "功能开发中") },
            onVideo = { viewModel.showOsd("视频", "功能开发中") },
            onAudio = { viewModel.showOsd("音频", "功能开发中") },
            onPlayback = { viewModel.showOsd("播放", "功能开发中") },
            onScreenshot = { viewModel.showOsd("截图", "功能开发中") },
            onAvsync = { viewModel.showOsd("A/V 同步监控", "功能开发中") },
            onNetwork = { viewModel.showOsd("网络增强", "功能开发中") },
            onTools = { viewModel.showOsd("工具", "功能开发中") },
            onView = { viewModel.showOsd("视图", "功能开发中") },
            onSettings = {
                viewModel.toggleMenuPanel()
                viewModel.togglePlayerSettings()
            },
            onAbout = { viewModel.showOsd("关于", "功能开发中") },
            onToggleFavorite = {
                viewModel.toggleFavorite()
            },
            onQuit = {
                viewModel.showOsd("退出", "请使用系统返回键退出")
            },
            hasCurrentChannel = currentChannel != null,
            isFavorite = isFavorite
        )
    }

    Surface(
        color = Color(0xF0161616),
        modifier = Modifier.fillMaxSize()
    ) {
        Column(modifier = Modifier.fillMaxSize()) {
            // 标题栏
            PanelHeader(
                title = "主菜单",
                subtitle = "功能入口",
                onClose = { viewModel.toggleMenuPanel() }
            )

            // 菜单分组列表
            LazyColumn(
                modifier = Modifier.fillMaxSize(),
                contentPadding = androidx.compose.foundation.layout.PaddingValues(vertical = 4.dp)
            ) {
                sections.forEach { section ->
                    item(key = "section_header_${section.title}") {
                        SectionHeader(section.title)
                    }
                    items(
                        items = section.entries,
                        key = { entry -> section.title + "_" + entry.title }
                    ) { entry ->
                        MenuEntryItem(
                            entry = entry,
                            onClick = entry.onClick
                        )
                    }
                    item(key = "section_divider_${section.title}") {
                        Spacer(modifier = Modifier.height(4.dp))
                    }
                }
            }
        }
    }
}

// -----------------------------------------------------------------
// 菜单数据模型
// -----------------------------------------------------------------

private data class MenuEntry(
    val icon: ImageVector,
    val title: String,
    val subtitle: String,
    val onClick: () -> Unit,
    val highlight: Boolean = false
)

private data class MenuSection(
    val title: String,
    val entries: List<MenuEntry>
)

private fun buildMenuSections(
    onOpenPlaylist: () -> Unit,
    onOpenUrl: () -> Unit,
    onOpenLocalVideo: () -> Unit,
    onSources: () -> Unit,
    onEpgSources: () -> Unit,
    onMapping: () -> Unit,
    onChannels: () -> Unit,
    onEpg: () -> Unit,
    onSubtitle: () -> Unit,
    onVideo: () -> Unit,
    onAudio: () -> Unit,
    onPlayback: () -> Unit,
    onScreenshot: () -> Unit,
    onAvsync: () -> Unit,
    onNetwork: () -> Unit,
    onTools: () -> Unit,
    onView: () -> Unit,
    onSettings: () -> Unit,
    onAbout: () -> Unit,
    onToggleFavorite: () -> Unit,
    onQuit: () -> Unit,
    hasCurrentChannel: Boolean,
    isFavorite: Boolean
): List<MenuSection> {
    val fileSection = MenuSection(
        title = "文件",
        entries = listOf(
            MenuEntry(Icons.Default.FileOpen, "打开播放列表", "选择设备上的 M3U/M3U8 文件", onOpenPlaylist),
            MenuEntry(Icons.Default.Link, "打开网络流", "输入 M3U/M3U8 订阅源 URL", onOpenUrl),
            MenuEntry(Icons.Default.Movie, "打开本地视频", "直接播放设备上的视频文件", onOpenLocalVideo),
            MenuEntry(Icons.Default.Web, "订阅源管理", "添加、编辑、删除 M3U 订阅源", onSources),
            MenuEntry(Icons.Default.CalendarMonth, "EPG 订阅源", "管理节目单订阅地址（XMLTV）", onEpgSources),
            MenuEntry(Icons.Default.SyncAlt, "频道映射", "远程映射 + 用户映射管理", onMapping)
        )
    )

    val playbackSection = MenuSection(
        title = "播放",
        entries = listOf(
            MenuEntry(Icons.Default.ListAlt, "频道", "订阅 / 本地 / 收藏 / 历史 / 队列", onChannels, highlight = true),
            MenuEntry(Icons.Default.CalendarMonth, "节目单 EPG", "当前频道节目与提醒", onEpg, highlight = true),
            MenuEntry(Icons.Default.ClosedCaption, "字幕", "轨 / 样式 / 延迟 / 位置 / 加载", onSubtitle),
            MenuEntry(Icons.Default.VideoSettings, "视频", "图像调整 / 旋转 / 比例 / 3D 360 / HDR", onVideo),
            MenuEntry(Icons.Default.Equalizer, "音频", "轨 / 延迟 / 设备 / 声道 / 音调 / EQ", onAudio),
            MenuEntry(Icons.Default.PlayCircle, "播放", "队列 / 循环 / AB / 续播 / 书签 / 章节逐帧", onPlayback),
            MenuEntry(Icons.Default.ScreenshotMonitor, "截图", "单张 / 连拍 / 缩略图", onScreenshot),
            MenuEntry(Icons.Default.GraphicEq, "A/V 同步监控", "实时波形 / 音视频差值", onAvsync),
            MenuEntry(Icons.Default.Public, "网络增强", "Referer / Proxy / Headers", onNetwork),
            MenuEntry(Icons.Default.Tune, "工具", "搜索 / EPG时间线 / 提醒 / 映射 / 扫描 / 流质量", onTools),
            MenuEntry(Icons.Default.ViewInAr, "视图", "全屏 / 比例 / OSD", onView),
            MenuEntry(Icons.Default.Settings, "设置", "硬件解码 / 缓存 / 网络 / 关于", onSettings),
            MenuEntry(Icons.Default.Info, "关于", "版本信息 / 检查更新", onAbout),
            MenuEntry(
                Icons.Default.Favorite,
                if (isFavorite) "取消收藏" else "收藏",
                if (hasCurrentChannel) "当前频道" else "未选择频道",
                onToggleFavorite,
                highlight = hasCurrentChannel
            ),
            MenuEntry(Icons.AutoMirrored.Filled.ExitToApp, "退出", "关闭应用", onQuit)
        )
    )

    return listOf(fileSection, playbackSection)
}

// -----------------------------------------------------------------
// 菜单组件
// -----------------------------------------------------------------

@Composable
private fun SectionHeader(title: String) {
    Surface(
        color = Color(0xFF1A1A1A),
        modifier = Modifier.fillMaxWidth()
    ) {
        Text(
            text = title,
            color = Color(0xFF4A9EFF),
            fontSize = 12.sp,
            fontWeight = FontWeight.SemiBold,
            modifier = Modifier.padding(horizontal = 16.dp, vertical = 6.dp)
        )
    }
}

@Composable
private fun MenuEntryItem(
    entry: MenuEntry,
    onClick: () -> Unit
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .padding(horizontal = 16.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        // 图标圆形背景
        Box(
            modifier = Modifier
                .size(36.dp)
                .clip(CircleShape)
                .background(
                    if (entry.highlight) Color(0xFF4A9EFF).copy(alpha = 0.2f)
                    else Color(0xFF2A2A2A)
                ),
            contentAlignment = Alignment.Center
        ) {
            Icon(
                imageVector = entry.icon,
                contentDescription = null,
                tint = if (entry.highlight) Color(0xFF4A9EFF) else Color(0xFFCCCCCC),
                modifier = Modifier.size(20.dp)
            )
        }

        Spacer(modifier = Modifier.width(12.dp))

        // 标题 + 副标题
        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = entry.title,
                color = Color.White,
                fontSize = 14.sp,
                fontWeight = if (entry.highlight) FontWeight.Medium else FontWeight.Normal,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis
            )
            if (entry.subtitle.isNotEmpty()) {
                Text(
                    text = entry.subtitle,
                    color = Color(0xFF888888),
                    fontSize = 11.sp,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
            }
        }
    }
}
