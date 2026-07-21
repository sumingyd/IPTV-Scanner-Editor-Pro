package com.iptv.scanner.editor.pro.ui

import android.content.res.Configuration
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
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
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ExitToApp
import androidx.compose.material.icons.automirrored.filled.ListAlt
import androidx.compose.material.icons.filled.CalendarMonth
import androidx.compose.material.icons.filled.ClosedCaption
import androidx.compose.material.icons.filled.ContentCut
import androidx.compose.material.icons.filled.DarkMode
import androidx.compose.material.icons.filled.Equalizer
import androidx.compose.material.icons.filled.Favorite
import androidx.compose.material.icons.filled.FileDownload
import androidx.compose.material.icons.filled.FileOpen
import androidx.compose.material.icons.filled.GraphicEq
import androidx.compose.material.icons.filled.History
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.LightMode
import androidx.compose.material.icons.filled.Link
import androidx.compose.material.icons.filled.Movie
import androidx.compose.material.icons.filled.MusicNote
import androidx.compose.material.icons.filled.PictureInPicture
import androidx.compose.material.icons.filled.PlayCircle
import androidx.compose.material.icons.filled.Public
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.ScreenshotMonitor
import androidx.compose.material.icons.filled.SyncAlt
import androidx.compose.material.icons.filled.Tune
import androidx.compose.material.icons.filled.VideoSettings
import androidx.compose.material.icons.filled.ViewInAr
import androidx.compose.material.icons.filled.Web
import androidx.compose.material.icons.filled.BrightnessAuto
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
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
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.iptv.scanner.editor.pro.ui.theme.tvFocusBorder

/**
 * 主菜单面板：与 PC 端主菜单（panelMenu）对齐。
 *
 * 3 个分组：
 * - 快捷（2 项）：频道列表 / 节目单 EPG
 * - 文件（6 项）：打开播放列表 / 打开网络流 / 打开本地视频 / 订阅源管理 / EPG 订阅源 / 频道映射
 * - 播放（13 项）：字幕 / 视频 / 音频 / 播放 / 截图 / A/V 同步 / 网络增强 /
 *   工具 / 视图 / 设置 / 关于 / 收藏 / 退出
 *
 * 布局自适应：
 * - 竖屏：单列列表（图标 + 标题 + 副标题）
 * - 横屏：多列网格（4 列，仅图标 + 标题，更紧凑高效）
 */
@Composable
fun MainMenuPanel(viewModel: AppViewModel) {
    val currentChannel by viewModel.currentChannel.collectAsState()
    val currentIdx by viewModel.currentIdx.collectAsState()
    val favorites by viewModel.favorites.collectAsState()

    val isFavorite = currentIdx >= 0 && favorites.contains(currentIdx)

    // SAF 文件选择器
    val playlistLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.OpenDocument()
    ) { uri: Uri? ->
        if (uri != null) viewModel.importPlaylist(uri)
    }

    val videoLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.OpenDocument()
    ) { uri: Uri? ->
        if (uri != null) viewModel.playLocalVideo(uri.toString())
    }

    val sections = remember(currentIdx, isFavorite) {
        buildMenuSections(
            onOpenPlaylist = {
                if (!viewModel.isSafAvailable()) {
                    viewModel.toggleMenuPanel()
                    viewModel.showFileBrowser()
                } else {
                    playlistLauncher.launch(arrayOf(
                        "application/x-mpegurl", "application/vnd.apple.mpegurl",
                        "audio/x-mpegurl", "video/x-mpegurl",
                        "text/plain", "application/octet-stream"
                    ))
                }
            },
            onOpenUrl = {
                viewModel.toggleMenuPanel()
                viewModel.toggleOpenUrlDialog()
            },
            onOpenLocalVideo = {
                if (!viewModel.isSafAvailable()) {
                    viewModel.toggleMenuPanel()
                    viewModel.showMediaFileBrowser()
                } else {
                    videoLauncher.launch(arrayOf("video/*", "audio/*", "application/x-matroska", "application/octet-stream"))
                }
            },
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
            onMapping = {
                viewModel.toggleMenuPanel()
                viewModel.toggleMappingPanel()
            },
            onChannels = {
                viewModel.toggleMenuPanel()
                viewModel.showChannelsPanel()
            },
            onEpg = {
                viewModel.toggleMenuPanel()
                viewModel.showEpgPanel()
            },
            onSubtitle = {
                viewModel.toggleMenuPanel()
                viewModel.toggleSubtitleSettings()
            },
            onVideo = {
                viewModel.toggleMenuPanel()
                viewModel.toggleVideoSettings()
            },
            onAudio = {
                viewModel.toggleMenuPanel()
                viewModel.toggleAudioSettings()
            },
            onPlayback = {
                viewModel.toggleMenuPanel()
                viewModel.togglePlaybackPanel()
            },
            onScreenshot = {
                viewModel.toggleMenuPanel()
                viewModel.toggleScreenshotPanel()
            },
            onAvsync = {
                viewModel.toggleMenuPanel()
                viewModel.toggleAvSyncPanel()
            },
            onNetwork = {
                viewModel.toggleMenuPanel()
                viewModel.toggleNetworkPanel()
            },
            onTools = {
                viewModel.toggleMenuPanel()
                viewModel.toggleToolsPanel()
            },
            onView = {
                viewModel.toggleMenuPanel()
                viewModel.toggleViewSettings()
            },
            onSettings = {
                viewModel.toggleMenuPanel()
                viewModel.togglePlayerSettings()
            },
            onAbout = {
                viewModel.toggleMenuPanel()
                viewModel.toggleAboutPanel()
            },
            onToggleFavorite = {
                viewModel.toggleFavorite()
            },
            onQuit = {
                viewModel.showOsd("退出", "请使用系统返回键退出")
            },
            onPip = {
                viewModel.toggleMenuPanel()
                viewModel.enterPip()
            },
            onThemeDark = {
                viewModel.setThemeMode("dark")
            },
            onThemeLight = {
                viewModel.setThemeMode("light")
            },
            onThemeSystem = {
                viewModel.setThemeMode("system")
            },
            onClipExport = {
                viewModel.toggleMenuPanel()
                viewModel.toggleClipExportPanel()
            },
            onAudioVisualizer = {
                viewModel.toggleMenuPanel()
                viewModel.toggleAudioVisualizer()
            },
            onLyrics = {
                viewModel.toggleMenuPanel()
                viewModel.toggleLyricsPanel()
            },
            onSaveAs = {
                viewModel.toggleMenuPanel()
                viewModel.saveAsM3u()
            },
            onRecent = {
                viewModel.toggleMenuPanel()
                viewModel.toggleRecentPanel()
            },
            onRefresh = {
                viewModel.toggleMenuPanel()
                viewModel.refreshUi()
            },
            hasCurrentChannel = currentChannel != null,
            isFavorite = isFavorite
        )
    }

    BoxWithConstraints(modifier = Modifier.fillMaxSize()) {
        val useDualColumn = maxWidth > 500.dp

        Surface(
            color = MaterialTheme.colorScheme.surface,
            modifier = Modifier.fillMaxSize()
        ) {
            Column(modifier = Modifier.fillMaxSize().systemBarsPadding()) {
                // 标题栏
                PanelHeader(
                    title = "主菜单",
                    subtitle = "功能入口",
                    onClose = { viewModel.toggleMenuPanel() }
                )

                if (useDualColumn) {
                    // ---- 横屏：多列网格布局 ----
                    LandscapeMenuGrid(sections = sections)
                } else {
                // ---- 竖屏：单列列表布局 ----
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
    }
}

// -----------------------------------------------------------------
// 横屏网格布局
// -----------------------------------------------------------------

/**
 * 横屏主菜单网格：每个分区分组显示，每行 4 列。
 * 每个菜单项为紧凑卡片（图标 + 标题），无副标题。
 */
@Composable
private fun LandscapeMenuGrid(sections: List<MenuSection>) {
    val columnCount = 4

    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = androidx.compose.foundation.layout.PaddingValues(horizontal = 12.dp, vertical = 4.dp)
    ) {
        sections.forEach { section ->
            item(key = "grid_header_${section.title}") {
                SectionHeader(section.title)
            }
            // 将条目按 columnCount 分行
            section.entries.chunked(columnCount).forEachIndexed { rowIdx, rowEntries ->
                item(key = "grid_row_${section.title}_$rowIdx") {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(vertical = 3.dp),
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        rowEntries.forEach { entry ->
                            MenuGridItem(
                                entry = entry,
                                onClick = entry.onClick,
                                modifier = Modifier.weight(1f)
                            )
                        }
                        // 用空占位填满剩余列（保持等宽）
                        repeat(columnCount - rowEntries.size) {
                            Spacer(modifier = Modifier.weight(1f))
                        }
                    }
                }
            }
            item(key = "grid_divider_${section.title}") {
                Spacer(modifier = Modifier.height(6.dp))
            }
        }
    }
}

/**
 * 网格菜单项（横屏紧凑模式）：图标 + 标题
 */
@Composable
private fun MenuGridItem(
    entry: MenuEntry,
    onClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    Surface(
        color = if (entry.highlight) MaterialTheme.colorScheme.primary.copy(alpha = 0.12f) else MaterialTheme.colorScheme.surfaceVariant,
        shape = RoundedCornerShape(8.dp),
        modifier = modifier
            .height(72.dp)
            .clip(RoundedCornerShape(8.dp))
            .clickable(onClick = onClick)
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(vertical = 8.dp, horizontal = 4.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center
        ) {
            // 图标
            Box(
                modifier = Modifier
                    .size(28.dp)
                    .clip(CircleShape)
                    .background(
                        if (entry.highlight) MaterialTheme.colorScheme.primary.copy(alpha = 0.2f)
                        else MaterialTheme.colorScheme.surfaceVariant
                    ),
                contentAlignment = Alignment.Center
            ) {
                Icon(
                    imageVector = entry.icon,
                    contentDescription = null,
                    tint = if (entry.highlight) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.size(16.dp)
                )
            }
            Spacer(modifier = Modifier.height(4.dp))
            // 标题
            Text(
                text = entry.title,
                color = if (entry.highlight) MaterialTheme.colorScheme.secondary else MaterialTheme.colorScheme.onSurface,
                fontSize = 11.sp,
                fontWeight = if (entry.highlight) FontWeight.Medium else FontWeight.Normal,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
                textAlign = TextAlign.Center
            )
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
    onPip: () -> Unit,
    onThemeDark: () -> Unit,
    onThemeLight: () -> Unit,
    onThemeSystem: () -> Unit,
    onClipExport: () -> Unit,
    onAudioVisualizer: () -> Unit,
    onLyrics: () -> Unit,
    onSaveAs: () -> Unit,
    onRecent: () -> Unit,
    onRefresh: () -> Unit,
    hasCurrentChannel: Boolean,
    isFavorite: Boolean
): List<MenuSection> {
    val quickSection = MenuSection(
        title = "快捷",
        entries = listOf(
            MenuEntry(Icons.AutoMirrored.Filled.ListAlt, "频道列表", "订阅 / 本地 / 收藏 / 历史", onChannels, highlight = true),
            MenuEntry(Icons.Default.CalendarMonth, "节目单 EPG", "当前频道节目 / 日期切换 / 提醒", onEpg, highlight = true)
        )
    )

    val fileSection = MenuSection(
        title = "文件",
        entries = listOf(
            MenuEntry(Icons.Default.FileOpen, "打开播放列表", "选择设备上的 M3U/M3U8 文件", onOpenPlaylist),
            MenuEntry(Icons.Default.Link, "打开网络流", "输入 M3U/M3U8 订阅源 URL", onOpenUrl),
            MenuEntry(Icons.Default.Movie, "打开本地文件", "播放设备上的视频/音频文件", onOpenLocalVideo),
            MenuEntry(Icons.Default.History, "最近打开", "最近打开的播放列表/网络流/视频", onRecent),
            MenuEntry(Icons.Default.Web, "订阅源管理", "添加、编辑、删除 M3U 订阅源", onSources),
            MenuEntry(Icons.Default.CalendarMonth, "EPG 订阅源", "管理节目单订阅地址（XMLTV）", onEpgSources),
            MenuEntry(Icons.Default.SyncAlt, "频道映射", "远程映射 + 用户映射管理", onMapping),
            MenuEntry(Icons.Default.FileDownload, "另存为 M3U", "导出当前频道列表到下载目录", onSaveAs),
            MenuEntry(Icons.Default.Refresh, "刷新", "重新加载频道和 EPG", onRefresh)
        )
    )

    val playbackSection = MenuSection(
        title = "播放",
        entries = listOf(
            MenuEntry(Icons.Default.ClosedCaption, "字幕", "轨 / 显示 / 延迟 / 缩放 / 位置 / 样式 / 加载", onSubtitle),
            MenuEntry(Icons.Default.VideoSettings, "视频", "图像调整 / 旋转 / 翻转 / 3D 360", onVideo),
            MenuEntry(Icons.Default.Equalizer, "音频", "音轨 / 延迟 / EQ / 音调", onAudio),
            MenuEntry(Icons.Default.PlayCircle, "播放", "速度 / 循环 / 随机 / AB / 逐帧 / 章节", onPlayback),
            MenuEntry(Icons.Default.ScreenshotMonitor, "截图", "单张 / 连拍 / 含字幕 / 含 OSD", onScreenshot),
            MenuEntry(Icons.Default.GraphicEq, "A/V 同步监控", "实时数值 / 波形 / 延迟调整", onAvsync),
            MenuEntry(Icons.Default.Public, "网络增强", "Referer / Proxy / Headers", onNetwork),
            MenuEntry(Icons.Default.Tune, "工具", "搜索 / EPG时间线 / 提醒 / 续播 / 书签 / 映射 / 扫描 / 流质量", onTools),
            MenuEntry(Icons.Default.PictureInPicture, "画中画", "进入 PiP 小窗口播放", onPip),
            MenuEntry(Icons.Default.ContentCut, "切片导出", "裁剪视频片段 / GIF / MP3", onClipExport),
            MenuEntry(Icons.Default.GraphicEq, "音频可视化", "实时频谱波形", onAudioVisualizer),
            MenuEntry(Icons.Default.MusicNote, "歌词", "加载 LRC / 同步高亮", onLyrics),
            MenuEntry(Icons.Default.ViewInAr, "视图", "视频比例 / OSD", onView),
            MenuEntry(Icons.Default.Settings, "设置", "播放器内核 / VO / HWDEC / HDR", onSettings),
            MenuEntry(Icons.Default.Info, "关于", "版本信息 / 功能特性", onAbout),
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

    val themeSection = MenuSection(
        title = "主题",
        entries = listOf(
            MenuEntry(Icons.Default.DarkMode, "深色模式", "沉浸式播放体验", onThemeDark, highlight = true),
            MenuEntry(Icons.Default.LightMode, "浅色模式", "明亮界面", onThemeLight),
            MenuEntry(Icons.Default.BrightnessAuto, "跟随系统", "随系统暗色/亮色切换", onThemeSystem)
        )
    )

    return listOf(quickSection, fileSection, playbackSection, themeSection)
}

// -----------------------------------------------------------------
// 菜单组件
// -----------------------------------------------------------------

@Composable
private fun SectionHeader(title: String) {
    Surface(
        color = MaterialTheme.colorScheme.surfaceVariant,
        modifier = Modifier.fillMaxWidth()
    ) {
        Text(
            text = title,
            color = MaterialTheme.colorScheme.primary,
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
            .tvFocusBorder()
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
                    if (entry.highlight) MaterialTheme.colorScheme.primary.copy(alpha = 0.2f)
                    else MaterialTheme.colorScheme.surfaceVariant
                ),
            contentAlignment = Alignment.Center
        ) {
            Icon(
                imageVector = entry.icon,
                contentDescription = null,
                tint = if (entry.highlight) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.size(20.dp)
            )
        }

        Spacer(modifier = Modifier.width(12.dp))

        // 标题 + 副标题
        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = entry.title,
                color = MaterialTheme.colorScheme.onSurface,
                fontSize = 14.sp,
                fontWeight = if (entry.highlight) FontWeight.Medium else FontWeight.Normal,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis
            )
            if (entry.subtitle.isNotEmpty()) {
                Text(
                    text = entry.subtitle,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    fontSize = 11.sp,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
            }
        }
    }
}
