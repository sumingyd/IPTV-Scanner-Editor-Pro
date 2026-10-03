"""macOS NSVisualEffectView 毛玻璃辅助工具。

在 macOS 上通过 PyObjC 调用 NSVisualEffectView 实现原生毛玻璃模糊效果。
非 macOS 平台或 PyObjC 不可用时，apply() 返回 False，调用方回退到 WA_TranslucentBackground。
"""
import sys


def _is_macos():
    return sys.platform == 'darwin'


class MacBlurHelper:
    """macOS 原生毛玻璃模糊辅助类。

    使用方法::

        if MacBlurHelper.apply(window):
            # 成功附着 NSVisualEffectView
        else:
            # 回退到 WA_TranslucentBackground
    """

    _initialized = False
    _objc_available = False

    @classmethod
    def _ensure_init(cls):
        if cls._initialized:
            return
        cls._initialized = True
        if not _is_macos():
            return
        try:
            import objc
            from Cocoa import NSVisualEffectView, NSView, NSWindow
            cls._objc_available = True
        except ImportError:
            cls._objc_available = False

    @classmethod
    def apply(cls, window, material="menu"):
        """将 NSVisualEffectView 附着到 Qt 窗口的 NSView 句柄。

        Args:
            window: QWidget 或 QMainWindow 实例
            material: 毛玻璃材质，可选 "menu"、"sidebar"、"popover"、"titlebar"、"fullscreen"

        Returns:
            bool: True 表示成功附着，False 表示不可用或失败
        """
        cls._ensure_init()
        if not cls._objc_available:
            return False
        try:
            from Cocoa import (
                NSVisualEffectView, NSView, NSWindow,
                NSVisualEffectMaterialMenu,
                NSVisualEffectMaterialSidebar,
                NSVisualEffectMaterialPopover,
                NSVisualEffectMaterialTitlebar,
                NSVisualEffectMaterialFullScreenUI,
                NSVisualEffectBlendingModeBehindWindow,
            )
            from PySide6.QtGui import QWindow

            material_map = {
                "menu": NSVisualEffectMaterialMenu,
                "sidebar": NSVisualEffectMaterialSidebar,
                "popover": NSVisualEffectMaterialPopover,
                "titlebar": NSVisualEffectMaterialTitlebar,
                "fullscreen": NSVisualEffectMaterialFullScreenUI,
            }

            win_handle = window.windowHandle()
            if win_handle is None:
                window.createWinId()
                win_handle = window.windowHandle()
            if win_handle is None:
                return False

            ns_view = win_handle.nativeInterface("AppKit.NSView")
            if ns_view is None:
                import objc
                ns_window_ptr = int(win_handle.winId())
                ns_window = objc.objc_object(ns_window_ptr)
                ns_view = ns_window.contentView()
                if ns_view is None:
                    return False

            effect_view = NSVisualEffectView.alloc().initWithFrame_(ns_view.frame())
            effect_view.setMaterial_(material_map.get(material, NSVisualEffectMaterialMenu))
            effect_view.setBlendingMode_(NSVisualEffectBlendingModeBehindWindow)
            effect_view.setState_(1)
            effect_view.setAutoresizingMask_(18)

            ns_view.addSubview_positioned_relativeTo_(
                effect_view, 0, None
            )

            if not hasattr(window, '_mac_blur_views'):
                window._mac_blur_views = []
            window._mac_blur_views.append(effect_view)

            return True
        except Exception:
            return False

    @classmethod
    def remove(cls, window):
        """移除 NSVisualEffectView 附着。

        Args:
            window: QWidget 或 QMainWindow 实例
        """
        if not _is_macos():
            return
        try:
            views = getattr(window, '_mac_blur_views', [])
            for view in views:
                try:
                    view.removeFromSuperview()
                except Exception:
                    pass
            window._mac_blur_views = []
        except Exception:
            pass

    @classmethod
    def is_available(cls):
        """检查 macOS 毛玻璃是否可用。"""
        cls._ensure_init()
        return cls._objc_available