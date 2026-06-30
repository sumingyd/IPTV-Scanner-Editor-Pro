package com.iptv.scanner.editor.pro.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Color.Companion.Black

/**
 * IPTV 应用主题。对齐 res/values/colors.xml 的暗色主题。
 *
 * 设计选择：始终使用暗色主题（视频播放应用的标准做法，避免亮色刺眼）。
 * 即使系统是亮色模式，应用也用暗色（沉浸式播放体验）。
 *
 * 颜色对应（colors.xml → Compose）：
 * - primary #1a1a2e → 深紫蓝（背景）
 * - surface #16213e → 表面色
 * - accent #4CAF50 → 主强调色（成功/激活）
 * - text_primary #E0E0E0 → 主文字色
 * - text_secondary #9E9E9E → 次要文字色
 * - error #F44336 → 错误色
 * - warning #FF9800 → 警告色
 */

// 主色板
private val Primary = Color(0xFF1A1A2E)
private val PrimaryDark = Color(0xFF0F0F1E)
private val Surface = Color(0xFF16213E)
private val SurfaceVariant = Color(0xFF1F2D4D)
private val Background = Color(0xFF0A0A14)

// 强调色
private val Accent = Color(0xFF4CAF50)        // 绿色（激活/成功）
private val AccentDim = Color(0xFF2E7D32)    // 暗绿
private val OnAccent = Color(0xFFFFFFFF)

// 文字色
private val TextPrimary = Color(0xFFE0E0E0)
private val TextSecondary = Color(0xFF9E9E9E)
private val OnSurface = TextPrimary
private val OnBackground = TextPrimary

// 状态色
private val ErrorColor = Color(0xFFF44336)
private val WarningColor = Color(0xFFFF9800)
private val InfoColor = Color(0xFF4A9EFF)

// 播放器专用色
val PlayerScrim = Color(0xAA000000)          // 控制层半透明背景
val PlayerScrimSolid = Color(0xF0000000)      // 控制层不透明背景
val PlayerAccent = Color(0xFF4A9EFF)          // 进度条/激活按钮色
val PlayerBadgeLive = Color(0xFFE53935)       // 直播 LIVE 徽章
val PlayerBadgeCatchup = Color(0xFFFF9800)    // 回看徽章

private val IptvColorScheme = darkColorScheme(
    primary = Accent,
    onPrimary = OnAccent,
    primaryContainer = AccentDim,
    onPrimaryContainer = OnAccent,
    secondary = InfoColor,
    onSecondary = OnAccent,
    secondaryContainer = SurfaceVariant,
    onSecondaryContainer = TextPrimary,
    tertiary = WarningColor,
    onTertiary = OnAccent,
    background = Background,
    onBackground = OnBackground,
    surface = Surface,
    onSurface = OnSurface,
    surfaceVariant = SurfaceVariant,
    onSurfaceVariant = TextSecondary,
    error = ErrorColor,
    onError = OnAccent,
    outline = TextSecondary,
)

/**
 * 应用主题入口。无论系统暗色模式如何，始终用暗色（视频播放沉浸感）。
 */
@Composable
fun IptvTheme(
    content: @Composable () -> Unit
) {
    MaterialTheme(
        colorScheme = IptvColorScheme,
        content = content
    )
}
