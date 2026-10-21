package com.iptv.scanner.editor.pro.ui.theme

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.focusable
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.composed
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.FocusDirection
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.key.Key
import androidx.compose.ui.input.key.KeyEventType
import androidx.compose.ui.input.key.key
import androidx.compose.ui.input.key.onPreviewKeyEvent
import androidx.compose.ui.input.key.type
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.unit.dp

/**
 * TV 端焦点高亮边框 Modifier。
 *
 * 焦点反馈增强（柔和边框 + 半透明背景）：
 * - 获取焦点时显示 2dp 白色圆角边框 + 半透明白色背景
 * - 未获取焦点时无边框无背景
 *
 * 仅添加焦点检测和条件边框，不添加 focusable（因为 `Modifier.clickable` 已内置 focusable）。
 * 适用于已有 `clickable` 的组件，链式调用 `.tvFocusBorder()` 即可。
 *
 * @param cornerRadius 边框圆角（dp），默认 8
 */
fun Modifier.tvFocusBorder(cornerRadius: Int = 8): Modifier = composed {
    var isFocused by remember { mutableStateOf(false) }
    this
        .onFocusChanged { isFocused = it.isFocused }
        .then(
            if (isFocused) {
                Modifier
                    .clip(RoundedCornerShape(cornerRadius.dp))
                    .background(Color(0x22FFFFFF))
                    .border(
                        width = 2.dp,
                        color = Color.White,
                        shape = RoundedCornerShape(cornerRadius.dp)
                    )
            } else {
                Modifier
            }
        )
}

/**
 * 竖屏同款「白亮玻璃凸起块」选中效果（iOS 分段控件选中态）：
 * 白 20% 底 + 白 45% 描边 + 顶部高光垂直渐变。
 * 横屏 TV 面板（统一面板/主菜单/底栏）的选中态统一使用，替代旧的纯色/描边选中。
 */
fun Modifier.tvGlassSelected(cornerRadius: Int = 10): Modifier = composed {
    val shape = RoundedCornerShape(cornerRadius.dp)
    this
        .background(Color.White.copy(alpha = 0.20f), shape)
        .border(1.dp, Color.White.copy(alpha = 0.45f), shape)
        .background(
            androidx.compose.ui.graphics.Brush.verticalGradient(
                0f to Color.White.copy(alpha = 0.22f),
                1f to Color.Transparent
            ),
            shape
        )
}

/**
 * TV 端可聚焦 + 焦点高亮 Modifier。
 *
 * 同时添加 `focusable()` + 焦点高亮边框。
 * 适用于没有 `clickable` 但需要 D-pad 焦点导航的组件（如纯展示性 Surface）。
 *
 * @param cornerRadius 边框圆角（dp），默认 8
 */
fun Modifier.tvFocusable(cornerRadius: Int = 8): Modifier = composed {
    var isFocused by remember { mutableStateOf(false) }
    this
        .onFocusChanged { isFocused = it.isFocused }
        .focusable()
        .then(
            if (isFocused) {
                Modifier
                    .clip(RoundedCornerShape(cornerRadius.dp))
                    .background(Color(0x22FFFFFF))
                    .border(
                        width = 2.dp,
                        color = Color.White,
                        shape = RoundedCornerShape(cornerRadius.dp)
                    )
            } else {
                Modifier
            }
        )
}

/**
 * TV 端 TextField 焦点导航 Modifier。
 *
 * 解决 OutlinedTextField / BasicTextField 获得焦点后 D-pad 上下键被
 * 文本光标移动消费、导致焦点无法移出输入框的问题（"焦点陷阱"）。
 *
 * 行为：
 * - DPAD_UP：移动焦点到上一个可聚焦元素，成功则消费事件
 * - DPAD_DOWN：移动焦点到下一个可聚焦元素，成功则消费事件
 * - DPAD_LEFT/RIGHT：不拦截，保留文本光标左右移动功能
 * - 其他按键（含软键盘输入）：不拦截
 *
 * 如果 moveFocus 返回 false（方向上没有更多可聚焦元素），
 * 也消费事件以防 TextField 内部将 DPAD_UP/DOWN 误解为光标移动。
 *
 * 用法：
 * ```
 * OutlinedTextField(
 *     value = text,
 *     onValueChange = { text = it },
 *     modifier = Modifier.fillMaxWidth().tvTextField(),
 *     ...
 * )
 * ```
 */
fun Modifier.tvTextField(): Modifier = composed {
    val focusManager = LocalFocusManager.current
    this.onPreviewKeyEvent { event ->
        if (event.type == KeyEventType.KeyDown) {
            when (event.key) {
                Key.DirectionUp -> {
                    focusManager.moveFocus(FocusDirection.Up)
                    true
                }
                Key.DirectionDown -> {
                    focusManager.moveFocus(FocusDirection.Down)
                    true
                }
                else -> false
            }
        } else {
            false
        }
    }
}
