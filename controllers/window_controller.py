"""
窗口框架管理器 - 负责自定义标题栏、窗口拖动、缩放等
从 pyqt_player.py 提取的独立模块
"""

import os
from PySide6.QtWidgets import QWidget, QLabel, QPushButton, QHBoxLayout, QMainWindow, QLineEdit, QComboBox
from PySide6.QtCore import Qt, QPoint, QSize
from PySide6.QtGui import QPixmap, QIcon
from ui.styles import AppStyles
from controllers.main_window_protocol import MainWindowProtocol


class WindowController:

    @staticmethod
    def _title_btn_style():
        colors = AppStyles._get_colors()
        return f"QPushButton {{ min-width: 40px; max-width: 40px; height: 28px; color: {colors['window_text']}; }}"

    def __init__(self, main_window: MainWindowProtocol):
        self.window: MainWindowProtocol = main_window
        self._dragging = False
        self._drag_offset = None
        self._stay_on_top_active = False
        
        # 标题栏组件引用（创建后赋值）
        self._title_bar = None
        self._title_icon_label = None
        self._title_label = None
        self._minimize_btn = None
        self._maximize_btn = None
        self._close_btn = None
        self._stay_on_top_btn = None

    def create_custom_title_bar(self, window_title: str = "IPTV Player Pro"):
        """创建自定义标题栏（与主题颜色一致）"""
        
        # 标题栏容器
        self._title_bar = QWidget()
        self._title_bar.setFixedHeight(32)
        self._title_bar.setObjectName("titleBar")
        self._title_bar.setStyleSheet(AppStyles.title_bar_style())

        # 标题栏布局
        title_layout = QHBoxLayout(self._title_bar)
        title_layout.setContentsMargins(12, 0, 8, 0)
        title_layout.setSpacing(0)

        # 窗口图标（左侧）
        self._title_icon_label = QLabel()
        self._title_icon_label.setFixedSize(16, 16)
        from utils.general_utils import get_icon_path
        from PySide6.QtGui import QIcon
        ico_path = get_icon_path()
        if os.path.exists(ico_path):
            pixmap = QIcon(ico_path).pixmap(16, 16)
            self._title_icon_label.setPixmap(pixmap)
            self._title_icon_label.setStyleSheet("background: transparent;")
        else:
            tv_icon_path = AppStyles.get_icon('tv', AppStyles._get_colors().get('accent', '#0078d4'), 16)
            if tv_icon_path:
                self._title_icon_label.setPixmap(QIcon(tv_icon_path).pixmap(16, 16))
            self._title_icon_label.setStyleSheet("background: transparent;")

        # 窗口标题
        self._title_label = QLabel(window_title)
        self._title_label.setStyleSheet(AppStyles.title_label_style())

        # 弹性空间
        title_layout.addWidget(self._title_icon_label)
        title_layout.addWidget(self._title_label, 1)

        # 窗口控制按钮
        btn_style = self._title_btn_style()
        title_icon_color = AppStyles._get_colors().get('window_text', '#ffffff')
        title_icon_size = QSize(14, 14)

        # 置顶按钮
        self._stay_on_top_btn = QPushButton()
        self._stay_on_top_btn.setIcon(QIcon(AppStyles.get_icon('pin', title_icon_color, 14)))
        self._stay_on_top_btn.setIconSize(title_icon_size)
        self._stay_on_top_btn.setObjectName("stayOnTopBtn")
        tooltip_text = self.window.language_manager.tr('tooltip_stay_on_top', 'Stay on Top') if hasattr(self.window, 'language_manager') else 'Stay on Top'
        self._stay_on_top_btn.setToolTip(tooltip_text)
        self._stay_on_top_btn.clicked.connect(self.toggle_stay_on_top)
        self._stay_on_top_btn.setStyleSheet(btn_style)
        title_layout.addWidget(self._stay_on_top_btn)

        # 最小化按钮
        self._minimize_btn = QPushButton()
        self._minimize_btn.setIcon(QIcon(AppStyles.get_icon('minimize', title_icon_color, 14)))
        self._minimize_btn.setIconSize(title_icon_size)
        self._minimize_btn.setObjectName("minimizeBtn")
        self._minimize_btn.setToolTip(self.window.language_manager.tr('tooltip_minimize', '最小化') if hasattr(self.window, 'language_manager') else '最小化')
        self._minimize_btn.clicked.connect(self.window.showMinimized)
        self._minimize_btn.setStyleSheet(btn_style)
        title_layout.addWidget(self._minimize_btn)

        # 最大化/还原按钮
        self._maximize_btn = QPushButton()
        self._maximize_btn.setIcon(QIcon(AppStyles.get_icon('fullscreen', title_icon_color, 14)))
        self._maximize_btn.setIconSize(title_icon_size)
        self._maximize_btn.setObjectName("maximizeBtn")
        self._maximize_btn.setToolTip(self.window.language_manager.tr('tooltip_maximize', '最大化') if hasattr(self.window, 'language_manager') else '最大化')
        self._maximize_btn.clicked.connect(self.toggle_maximize)
        self._maximize_btn.setStyleSheet(btn_style)
        title_layout.addWidget(self._maximize_btn)

        # 关闭按钮
        self._close_btn = QPushButton()
        self._close_btn.setIcon(QIcon(AppStyles.get_icon('close', title_icon_color, 14)))
        self._close_btn.setIconSize(title_icon_size)
        self._close_btn.setObjectName("closeButton")
        self._close_btn.setToolTip(self.window.language_manager.tr('tooltip_close', '关闭') if hasattr(self.window, 'language_manager') else '关闭')
        self._close_btn.clicked.connect(self.window.close)
        self._close_btn.setStyleSheet(btn_style)
        title_layout.addWidget(self._close_btn)

        return self._title_bar

    def toggle_maximize(self):
        """切换最大化/还原状态"""
        color = AppStyles._get_colors().get('window_text', '#ffffff')
        tr = self.window.language_manager.tr if hasattr(self.window, 'language_manager') else lambda k, v: v
        if self.window.isMaximized():
            self.window.showNormal()
            icon_path = AppStyles.get_icon('fullscreen', color, 14)
            if icon_path:
                self._maximize_btn.setIcon(QIcon(icon_path))
            self._maximize_btn.setToolTip(tr('tooltip_maximize', '最大化'))
        else:
            self.window.showMaximized()
            icon_path = AppStyles.get_icon('restore', color, 14)
            if icon_path:
                self._maximize_btn.setIcon(QIcon(icon_path))
            self._maximize_btn.setToolTip(tr('tooltip_restore', '还原'))

    def toggle_stay_on_top(self):
        """切换置顶状态"""
        self._stay_on_top_active = not self._stay_on_top_active
        flags = self.window.windowFlags()
        color = AppStyles._get_colors().get('window_text', '#ffffff')
        self.window.hide()
        if self._stay_on_top_active:
            self.window.setWindowFlags(flags | Qt.WindowType.WindowStaysOnTopHint)
            icon_path = AppStyles.get_icon('pin_active', color, 14)
            if icon_path:
                self._stay_on_top_btn.setIcon(QIcon(icon_path))
            accent = AppStyles._get_colors().get('accent', '#0078d4')
            r, g, b = int(accent[1:3], 16), int(accent[3:5], 16), int(accent[5:7], 16)
            self._stay_on_top_btn.setStyleSheet(
                self._title_btn_style().replace("}", "") +
                f" background-color: rgba({r}, {g}, {b}, 0.25); }}"
            )
        else:
            self.window.setWindowFlags(flags & ~Qt.WindowType.WindowStaysOnTopHint)
            icon_path = AppStyles.get_icon('pin', color, 14)
            if icon_path:
                self._stay_on_top_btn.setIcon(QIcon(icon_path))
            self._stay_on_top_btn.setStyleSheet(self._title_btn_style())
        self.window.show()
        self._sync_floating_panels_on_top()

    def _sync_floating_panels_on_top(self):
        """同步所有浮动面板的置顶状态（包括当前不可见的，确保重新显示时继承正确状态）"""
        for panel_attr in ['epg_panel', 'playlist_panel', 'floating_panel']:
            panel = getattr(self.window, panel_attr, None)
            if panel is None:
                continue
            flags = panel.windowFlags()
            if self._stay_on_top_active:
                flags |= Qt.WindowType.WindowStaysOnTopHint
            else:
                flags &= ~Qt.WindowType.WindowStaysOnTopHint
            panel.setWindowFlags(flags)
            # 只对当前可见的面板调用 show()，不可见面板仅更新 flags
            if panel.isVisible():
                panel.show()

    def handle_mouse_press_event(self, event) -> bool:
        """
        处理鼠标按下事件 - 用于窗口拖动
        Returns: bool - 是否已处理该事件
        """
        if event.button() == Qt.MouseButton.LeftButton:
            # 检查是否点击在标题栏区域（实现窗口拖动）
            if self._title_bar:
                title_bar_geo = self._title_bar.geometry()
                # 转换为全局坐标
                title_global_pos = self._title_bar.mapToGlobal(QPoint(0, 0))
                mouse_global_pos = event.globalPosition().toPoint()

                if (title_global_pos.x() <= mouse_global_pos.x() <= title_global_pos.x() + title_bar_geo.width() and
                    title_global_pos.y() <= mouse_global_pos.y() <= title_global_pos.y() + title_bar_geo.height()):

                    # 排除按钮区域
                    child = self.window.childAt(event.position().toPoint())
                    if child and isinstance(child, (QPushButton, QLineEdit, QComboBox)):
                        pass
                    else:
                        self._dragging = True
                        self._drag_offset = (event.globalPosition().toPoint() - self.window.frameGeometry().topLeft())
                        if self.window.isMaximized():
                            geo = self.window.geometry()
                            self.window.showNormal()
                            ratio = event.position().toPoint().x() / max(1, geo.width())
                            new_x = event.globalPosition().toPoint().x() - int(self.window.width() * ratio)
                            new_y = event.globalPosition().toPoint().y() - self._drag_offset.y()
                            self.window.move(new_x, new_y)
                            self._drag_offset = event.globalPosition().toPoint() - self.window.pos()
                        event.accept()
                        return True

        return False

    def handle_mouse_move_event(self, event) -> bool:
        """
        处理鼠标移动事件 - 实现窗口拖动
        Returns: bool - 是否已处理该事件
        """
        if self._dragging and self._drag_offset is not None:
            if event.buttons() & Qt.MouseButton.LeftButton:
                new_pos = event.globalPosition().toPoint() - self._drag_offset
                self.window.move(new_pos)
                event.accept()
                return True

        return False

    def handle_mouse_release_event(self, event):
        """处理鼠标释放事件 - 结束拖动"""
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            self._drag_offset = None
            
            # 触发悬浮窗提升
            if hasattr(self.window, '_raise_floating_panels'):
                self.window._raise_floating_panels()

    def handle_mouse_double_click_event(self, event) -> bool:
        """
        处理鼠标双击事件 - 标题栏双击最大化/还原
        Returns: bool - 是否已处理该事件
        """
        if self._title_bar:
            title_bar_geo = self._title_bar.geometry()
            title_global_pos = self._title_bar.mapToGlobal(QPoint(0, 0))
            mouse_global_pos = event.globalPosition().toPoint()

            if (title_global_pos.x() <= mouse_global_pos.x() <= title_global_pos.x() + title_bar_geo.width() and
                title_global_pos.y() <= mouse_global_pos.y() <= title_global_pos.y() + title_bar_geo.height()):
                self.toggle_maximize()
                event.accept()
                return True

        return False

    @property
    def is_dragging(self) -> bool:
        return self._dragging

    @property
    def is_stay_on_top(self) -> bool:
        return self._stay_on_top_active
