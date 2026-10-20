package com.iptv.scanner.editor.pro.ui.theme

import android.os.Build
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.compositionLocalOf
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import dev.chrisbanes.haze.HazeState
import dev.chrisbanes.haze.HazeTint
import dev.chrisbanes.haze.hazeEffect
import dev.chrisbanes.haze.hazeSource

/**
 * iOS「液态玻璃」风格材质（iOS 26 Liquid Glass 的 Compose 近似实现）。
 *
 * 平台限制说明：
 * - 视频由 MPVView（SurfaceView）渲染，属于独立合成层，任何 RenderEffect
 *   （含 Haze）都无法对它取景模糊——这是安卓平台的硬限制（iOS 由系统合成器
 *   实现，不存在此问题）。因此玻璃面板直接叠在视频上时，模糊源为黑色，
 *   视觉表现为「烟熏玻璃 + 高光描边」；叠在 Compose 内容（渐变/海报/面板）
 *   上时为真实的背景模糊。
 * - Dialog 是独立窗口，无法共享 HazeState，自动降级为静态光泽玻璃
 *   （渐变 + 高光描边），仍有明显的 iOS 质感。
 *
 * 材质分层（自下而上）：
 * 1. backdrop blur（Haze hazeEffect，blur 22dp + 白色提亮 tint）或静态降级渐变
 * 2. 光泽渐变：顶部高光 → 中部近乎透明 → 底部微暗，模拟玻璃透镜反光
 * 3. 1.2dp 渐变高光描边：顶部亮 → 底部暗，模拟玻璃边缘折射
 * 4. content
 */

/** 背景层 HazeState：由播放器/主页根布局 provide，玻璃面板读取后对背景取景模糊 */
val LocalHazeState = compositionLocalOf<HazeState?> { null }

/** 判断当前设备是否支持实时 backdrop blur（API 31+ RenderEffect） */
internal fun isLiquidBlurSupported(): Boolean = Build.VERSION.SDK_INT >= Build.VERSION_CODES.S

/** 播放器/主页根布局使用：把整个子树标记为玻璃模糊的采样源 */
internal fun Modifier.liquidGlassSource(hazeState: HazeState): Modifier =
    this.then(Modifier.hazeSource(hazeState))

/**
 * iOS 风格液态玻璃容器。
 *
 * @param enabled 液态玻璃总开关；false 时渲染为实底面板（原样式）
 * @param fallbackColor 关闭/降级时的实底色（保持各调用点原有观感）
 * @param cornerRadius 圆角半径
 */
@Composable
fun LiquidGlassSurface(
    enabled: Boolean,
    modifier: Modifier = Modifier,
    cornerRadius: Dp = 10.dp,
    fallbackColor: Color = Color(0xF0222222),
    content: @Composable BoxScope.() -> Unit
) {
    val shape = RoundedCornerShape(cornerRadius)
    val hazeState = LocalHazeState.current
    val useBlur = enabled && isLiquidBlurSupported() && hazeState != null
    val radiusPx = with(LocalDensity.current) { cornerRadius.toPx() }

    Box(modifier = modifier.clip(shape)) {
        if (enabled) {
            if (useBlur) {
                // 层 1：实时 backdrop blur（Haze）——对 hazeSource 标记的背景取景模糊
                Box(
                    modifier = Modifier
                        .matchParentSize()
                        .hazeEffect(state = hazeState!!) {
                            blurRadius = 22.dp
                            noiseFactor = 0.04f
                            // 白色低透明度提亮：深色视频上呈「亮玻璃」，浅色背景上保持通透
                            tints = listOf(HazeTint(Color(0x14FFFFFF)))
                            // Haze 在不支持的平台上的兜底色
                            fallbackTint = HazeTint(Color(0x66202030))
                        }
                )
            } else {
                // 降级：静态光泽渐变（Dialog 独立窗口 / API < 31）
                Box(
                    modifier = Modifier
                        .matchParentSize()
                        .background(staticGlassBrush)
                )
            }
            // 层 2：光泽渐变（两种模式下都叠加，增强透镜感）
            Box(
                modifier = Modifier
                    .matchParentSize()
                    .background(glossBrush)
            )
            // 层 3：渐变高光描边（顶部亮 → 底部暗，模拟玻璃边缘折射）
            Box(
                modifier = Modifier
                    .matchParentSize()
                    .drawBehind {
                        drawRoundRect(
                            brush = Brush.verticalGradient(
                                listOf(
                                    Color.White.copy(alpha = 0.45f),
                                    Color.White.copy(alpha = 0.10f)
                                )
                            ),
                            cornerRadius = CornerRadius(radiusPx, radiusPx),
                            style = Stroke(width = 1.2.dp.toPx())
                        )
                    }
            )
        } else {
            Box(modifier = Modifier.matchParentSize().background(fallbackColor, shape))
        }
        content()
    }
}

/** 静态光泽玻璃背景（无 blur 场景的降级底色） */
private val staticGlassBrush = Brush.verticalGradient(
    listOf(
        Color(0x59FFFFFF),   // 顶部白 35%
        Color(0x26222830),   // 上部浅灰
        Color(0xB31A1E26),   // 下部深灰
        Color(0xCC101318)    // 底部更暗
    )
)

/** 玻璃光泽渐变：顶部高光 → 中部通透 → 底部微暗 */
private val glossBrush = Brush.verticalGradient(
    0f to Color.White.copy(alpha = 0.16f),
    0.30f to Color.White.copy(alpha = 0.05f),
    0.62f to Color.Transparent,
    1f to Color.Black.copy(alpha = 0.10f)
)

/** 记忆化 HazeState（根布局用） */
@Composable
fun rememberLiquidHazeState(): HazeState = remember { HazeState() }
