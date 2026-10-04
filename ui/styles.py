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


# 各 mixin 模块内部的方法体通过模块全局名引用聚合类（拆分前 AppStyles 与
# 方法同文件同名）。聚合类定义完成后回注到各子模块命名空间，供调用时解析。
import sys as _sys
for _module_name in (
    'ui.styles_base', 'ui.styles_icons', 'ui.styles_decorations',
    'ui.styles_player', 'ui.styles_window', 'ui.styles_common',
    'ui.styles_dialog',
):
    _sys.modules[_module_name].AppStyles = AppStyles


__all__ = [
    'AppStyles', 'color_to_qcolor', 'color_to_hex',
    'rgba_to_blended_hex', '_SVG_TMPDIR',
]
