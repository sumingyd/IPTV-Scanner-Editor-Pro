"""应用样式管理 - AppStyles 聚合门面

方法实现分布在 styles_base/styles_icons/styles_decorations/
styles_player/styles_window/styles_common/styles_dialog 子模块。
对外 API 完全兼容：from ui.styles import AppStyles, color_to_qcolor, ...
"""
from ui.styles_base import (
    StylesBase, color_to_qcolor, color_to_hex, rgba_to_blended_hex,
    _SVG_TMPDIR,
)
from ui.styles_icons import StylesIcons
from ui.styles_decorations import StylesDecorations
from ui.styles_player import StylesPlayer
from ui.styles_window import StylesWindow
from ui.styles_common import StylesCommon
from ui.styles_dialog import StylesDialog


class AppStyles(
    StylesIcons, StylesDecorations, StylesPlayer,
    StylesWindow, StylesCommon, StylesDialog,
):
    """应用样式管理类 - 支持颜色模式×视觉风格双维度主题。

    聚合门面：核心方法来自 StylesBase，各域方法来自对应 mixin。
    """
    pass


__all__ = [
    'AppStyles', 'color_to_qcolor', 'color_to_hex',
    'rgba_to_blended_hex', '_SVG_TMPDIR',
]
