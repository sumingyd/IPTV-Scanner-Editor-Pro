package com.iptv.scanner.editor.pro.ui.theme

import androidx.compose.foundation.border
import androidx.compose.foundation.focusable
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.composed
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.unit.dp

/**
 * TV 端焦点高亮边框 Modifier。
 *
 * 与 PC 端 `.tv-focused` / `.focused` CSS 样式对齐：
 * - 获取焦点时显示 3dp 蓝色（PlayerAccent）圆角边框
 * - 未获取焦点时无边框
 *
 * 仅添加焦点检测和条件边框，不添加 focusable（因为 `Modifier.clickable` 已内置 focusable）。
 * 适用于已有 `clickable` 的组件，链式调用 `.tvFocusBorder()` 即可。
 *
 * 示例：
 * ```
 * Row(
 *     modifier = Modifier
 *         .fillMaxWidth()
 *         .clickable { onClick() }
 *         .tvFocusBorder()
 * )
 * ```
 *
 * @param cornerRadius 边框圆角（dp），默认 8
 */
fun Modifier.tvFocusBorder(cornerRadius: Int = 8): Modifier = composed {
    var isFocused by remember { mutableStateOf(false) }
    this
        .onFocusChanged { isFocused = it.isFocused }
        .then(
            if (isFocused) {
                Modifier.border(
                    width = 3.dp,
                    color = PlayerAccent,
                    shape = RoundedCornerShape(cornerRadius.dp)
                )
            } else {
                Modifier
            }
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
                Modifier.border(
                    width = 3.dp,
                    color = PlayerAccent,
                    shape = RoundedCornerShape(cornerRadius.dp)
                )
            } else {
                Modifier
            }
        )
}
