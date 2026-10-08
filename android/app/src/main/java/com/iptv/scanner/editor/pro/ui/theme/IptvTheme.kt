package com.iptv.scanner.editor.pro.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Box
import androidx.compose.ui.draw.clip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.ReadOnlyComposable
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.blur
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.luminance
import androidx.compose.ui.unit.dp
import com.iptv.scanner.editor.pro.ui.AptvAccent
import com.iptv.scanner.editor.pro.ui.LocalAptvStyle

/**
 * IPTV 应用主题。支持深色/浅色/跟随系统三种模式。
 *
 * 统一主色调为蓝色（Blue），绿色仅用于语义性的「成功/有效」状态。
 *
 * - primary → 蓝色 #4A9EFF（深色）/ #1A73E8（浅色）
 * - surface → 深色 #16213E / 浅色 #F5F5F5
 * - success → 绿色 #4CAF50（仅语义状态，非主色调）
 * - error #F44336 → 错误色
 * - warning #FF9800 → 警告色
 */

// 主色板（深色）
private val DarkPrimary = Color(0xFF1A1A2E)
private val DarkPrimaryDark = Color(0xFF0F0F1E)
private val DarkSurface = Color(0xFF121220)       // 与 background 接近，避免页面间色差
private val DarkSurfaceVariant = Color(0xFF1A1A2E)  // 略亮，用于卡片/列表项背景
private val DarkBackground = Color(0xFF0A0A14)

// 主色板（浅色）
private val LightPrimary = Color(0xFF3F51B5)
private val LightPrimaryDark = Color(0xFF303F9F)
private val LightSurface = Color(0xFFF5F5F5)
private val LightSurfaceVariant = Color(0xFFEEEEEE)
private val LightBackground = Color(0xFFFAFAFA)

// 主强调色 — 统一蓝色，区分深/浅色模式
private val AccentDark = Color(0xFF4A9EFF)     // 深色模式主色
private val AccentLight = Color(0xFF1A73E8)    // 浅色模式主色
private val AccentDimDark = Color(0xFF1565C0)  // 深色模式 primaryContainer
private val AccentDimLight = Color(0xFF1565C0) // 浅色模式 primaryContainer
private val OnAccent = Color(0xFFFFFFFF)

// 语义色 — 绿色仅用于「成功/有效」状态
private val SuccessColor = Color(0xFF4CAF50)

// 文字色（深色）
private val DarkTextPrimary = Color(0xFFE0E0E0)
private val DarkTextSecondary = Color(0xFF9E9E9E)

// 文字色（浅色）
private val LightTextPrimary = Color(0xFF212121)
private val LightTextSecondary = Color(0xFF757575)

// 状态色
private val ErrorColor = Color(0xFFF44336)
private val WarningColor = Color(0xFFFF9800)
private val InfoColor = Color(0xFF4A9EFF)

// 播放器专用色 — accent 统一使用 colorScheme.primary
val PlayerScrim = Color(0xAA000000)          // 控制层半透明背景
val PlayerScrimSolid = Color(0xF0000000)      // 控制层不透明背景
val PlayerBadgeLive = Color(0xFFE53935)       // 直播 LIVE 徽章
val PlayerBadgeCatchup = Color(0xFFFF9800)    // 回看徽章
val SuccessGreen = Color(0xFF4CAF50)          // 语义色：成功/有效

private val IptvDarkColorScheme = darkColorScheme(
    primary = AccentDark,
    onPrimary = OnAccent,
    primaryContainer = AccentDimDark,
    onPrimaryContainer = OnAccent,
    secondary = InfoColor,
    onSecondary = OnAccent,
    secondaryContainer = DarkSurfaceVariant,
    onSecondaryContainer = DarkTextPrimary,
    tertiary = WarningColor,
    onTertiary = OnAccent,
    background = DarkBackground,
    onBackground = DarkTextPrimary,
    surface = DarkSurface,
    onSurface = DarkTextPrimary,
    surfaceVariant = DarkSurfaceVariant,
    onSurfaceVariant = DarkTextSecondary,
    error = ErrorColor,
    onError = OnAccent,
    outline = DarkTextSecondary,
)

private val IptvLightColorScheme = lightColorScheme(
    primary = AccentLight,
    onPrimary = OnAccent,
    primaryContainer = AccentDimLight,
    onPrimaryContainer = OnAccent,
    secondary = InfoColor,
    onSecondary = OnAccent,
    secondaryContainer = LightSurfaceVariant,
    onSecondaryContainer = LightTextPrimary,
    tertiary = WarningColor,
    onTertiary = OnAccent,
    background = LightBackground,
    onBackground = LightTextPrimary,
    surface = LightSurface,
    onSurface = LightTextPrimary,
    surfaceVariant = LightSurfaceVariant,
    onSurfaceVariant = LightTextSecondary,
    error = ErrorColor,
    onError = OnAccent,
    outline = LightTextSecondary,
)

/**
 * 应用主题入口。
 * @param themeMode "dark"=深色, "light"=浅色, "system"=跟随系统
 */
@Composable
fun IptvTheme(
    themeMode: String = "dark",
    content: @Composable () -> Unit
) {
    val useDark = when (themeMode) {
        "light" -> false
        "system" -> isSystemInDarkTheme()
        else -> true  // "dark" 或默认
    }
    MaterialTheme(
        colorScheme = if (useDark) IptvDarkColorScheme else IptvLightColorScheme,
        content = content
    )
}

/**
 * 判断当前是否为深色主题。
 * 通过 surface 颜色的亮度判断（luminance < 0.5 = 深色）。
 */
@Composable
@ReadOnlyComposable
fun isDarkTheme(): Boolean {
    return MaterialTheme.colorScheme.surface.luminance() < 0.5f
}

/**
 * 播放器控制层覆盖颜色 — 随主题自适应。
 *
 * 视频控制层叠在视频上方，需要遮罩保证对比度：
 * - 深色主题：深色半透明遮罩 + 白色图标/文字
 * - 浅色主题：浅色半透明遮罩 + 深色图标/文字
 * 强调色（进度条、激活态）在两种主题下统一使用蓝色。
 */
data class PlayerOverlayColors(
    val scrim: Color,           // 控制层半透明背景
    val topBarBg: Color,        // 顶部信息条背景
    val infoBarBg: Color,       // 竖屏信息栏背景
    val iconTint: Color,        // 图标默认颜色
    val iconTintActive: Color,  // 激活态图标颜色（如静音/锁定）
    val textPrimary: Color,     // 主文字色
    val textSecondary: Color,   // 次要文字色
    val accent: Color,          // 强调色（进度条/激活按钮）
    val trackInactive: Color,   // 进度条未激活轨道色
    val badgeBg: Color,         // 徽章背景色
    val badgeText: Color,       // 徽章文字色
    val divider: Color,         // 分隔线/边框色
)

/**
 * 获取当前主题下的播放器控制层颜色。
 */
@Composable
@ReadOnlyComposable
fun rememberPlayerOverlayColors(): PlayerOverlayColors {
    val dark = isDarkTheme()
    if (LocalAptvStyle.current) {
        return PlayerOverlayColors(
            scrim = Color(0x66000000),
            topBarBg = MaterialTheme.colorScheme.surface,
            infoBarBg = MaterialTheme.colorScheme.surfaceVariant,
            iconTint = MaterialTheme.colorScheme.onSurface,
            iconTintActive = AptvAccent,
            textPrimary = MaterialTheme.colorScheme.onSurface,
            textSecondary = MaterialTheme.colorScheme.onSurfaceVariant,
            accent = AptvAccent,
            trackInactive = MaterialTheme.colorScheme.surfaceVariant,
            badgeBg = AptvAccent.copy(alpha = 0.12f),
            badgeText = AptvAccent,
            divider = MaterialTheme.colorScheme.outline,
        )
    }
    return if (dark) {
        PlayerOverlayColors(
            scrim = Color(0x66000000),
            topBarBg = Color(0xF0303548),      // TAB/控制栏：更亮的深蓝灰
            infoBarBg = Color(0xD0181C28),      // 活动区域：更深，与 TAB 形成对比      // 与信息栏同色
            iconTint = Color.White,
            iconTintActive = Color(0xFFFFA500),
            textPrimary = Color.White,
            textSecondary = Color(0xFFAAAAAA),
            accent = AccentDark,  // 与 colorScheme.primary 一致
            trackInactive = Color(0xFF3A3A5C),
            badgeBg = AccentDark.copy(alpha = 0.15f),
            badgeText = Color(0xFF8AB4F8),
            divider = Color(0xFF2A2A4E),
        )
    } else {
        PlayerOverlayColors(
            scrim = Color(0x66FFFFFF),
            topBarBg = Color(0xC8F0F2F5),       // TAB：略灰白，不要太亮
            infoBarBg = Color(0xD0E8EAED),       // 活动区域：恢复之前的浅灰白
            iconTint = Color(0xFF212121),
            iconTintActive = Color(0xFFE65100),
            textPrimary = Color(0xFF212121),
            textSecondary = Color(0xFF666666),
            accent = AccentLight,  // 与 colorScheme.primary 一致
            trackInactive = Color(0xFFCCCCCC),
            badgeBg = AccentLight.copy(alpha = 0.12f),
            badgeText = Color(0xFF616161),
            divider = Color(0xFFBDBDBD),         // 更深的分隔线，浅色模式下可见
        )
    }
}

// -----------------------------------------------------------------
// 共享 UI 组件：玻璃态卡片、圆点进度条滑块、选中边框
// -----------------------------------------------------------------

/**
 * 玻璃态卡片：半透明背景 + 圆角 + 边框 + Android 12+ 模糊
 * 用于替换所有硬编码的颜色块（如设置项背景、关于面板等）
 */
@Composable
fun GlassCard(
    modifier: Modifier = Modifier,
    cornerRadius: androidx.compose.ui.unit.Dp = 12.dp,
    content: @Composable () -> Unit
) {
    val oc = rememberPlayerOverlayColors()
    val isAndroid12Plus = android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.S
    val shape = androidx.compose.foundation.shape.RoundedCornerShape(cornerRadius)
    Box(modifier = modifier) {
        if (isAndroid12Plus) {
            Box(
                modifier = Modifier
                    .then(Modifier.matchParentSize())
                    .blur(15.dp)
                    .background(oc.topBarBg.copy(alpha = 0.40f), shape)
            )
        }
        Surface(
            color = if (isAndroid12Plus) oc.topBarBg.copy(alpha = 0.25f) else oc.topBarBg.copy(alpha = 0.85f),
            shape = shape,
            border = androidx.compose.foundation.BorderStroke(1.dp, oc.accent.copy(alpha = if (isAndroid12Plus) 0.30f else 0.15f)),
            modifier = Modifier.matchParentSize()
        ) {
            content()
        }
    }
}

@Composable
fun GlassPanel(
    liquidGlass: Boolean,
    modifier: Modifier = Modifier,
    cornerRadius: androidx.compose.ui.unit.Dp = 10.dp,
    content: @Composable () -> Unit
) {
    val isAndroid12Plus = android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.S
    val useGlass = liquidGlass && isAndroid12Plus
    val shape = androidx.compose.foundation.shape.RoundedCornerShape(cornerRadius)
    Box(modifier = modifier.then(Modifier.clip(shape))) {
        if (useGlass) {
            Box(
                modifier = Modifier
                    .matchParentSize()
                    .blur(15.dp)
                    .background(Color(0x88222222))
            )
        }
        Surface(
            color = if (useGlass) Color(0xE6222222) else Color(0xF0222222),
            shape = shape
        ) {
            content()
        }
    }
}

/**
 * 选中状态边框：给已选择项加玻璃态边框效果
 */
@Composable
fun Modifier.selectedBorder(isSelected: Boolean): Modifier {
    if (!isSelected) return this
    val oc = rememberPlayerOverlayColors()
    return this.then(
        Modifier.border(
            width = 1.dp,
            color = oc.accent.copy(alpha = 0.50f),
            shape = androidx.compose.foundation.shape.RoundedCornerShape(8.dp)
        )
    )
}

/**
 * 圆点进度条样式的 Slider
 */
@Composable
fun GlassSlider(
    value: Float,
    onValueChange: (Float) -> Unit,
    modifier: Modifier = Modifier,
    valueRange: ClosedFloatingPointRange<Float> = 0f..1f,
    enabled: Boolean = true
) {
    val oc = rememberPlayerOverlayColors()
    androidx.compose.material3.Slider(
        value = value,
        onValueChange = onValueChange,
        modifier = modifier,
        valueRange = valueRange,
        enabled = enabled,
        colors = androidx.compose.material3.SliderDefaults.colors(
            thumbColor = oc.accent,
            activeTrackColor = oc.accent,
            inactiveTrackColor = oc.trackInactive,
            disabledThumbColor = oc.accent.copy(alpha = 0.5f),
            disabledActiveTrackColor = oc.accent.copy(alpha = 0.5f),
            disabledInactiveTrackColor = oc.trackInactive
        )
    )
}
