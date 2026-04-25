"""
窗口框架管理器 - 负责自定义标题栏、窗口拖动、缩放等
从 pyqt_player.py 提取的独立模块
"""

import os
from PyQt6.QtWidgets import QWidget, QLabel, QPushButton, QHBoxLayout, QMainWindow
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QPixmap
from ui.styles import AppStyles


class WindowController:
    """窗口框架控制器 - 管理标题栏、拖动、缩放等功能"""

    def __init__(self, main_window: QMainWindow):
        self.window = main_window
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
        from PyQt6.QtGui import QIcon
        ico_path = get_icon_path()
        if os.path.exists(ico_path):
            # 用 QIcon.pixmap() 而非 QPixmap().scaled()：
            # ICO 文件内嵌多尺寸位图，QIcon 会自动选取最接近的分辨率，避免放大/缩小导致模糊
            pixmap = QIcon(ico_path).pixmap(16, 16)
            self._title_icon_label.setPixmap(pixmap)
        else:
            self._title_icon_label.setText("📺")
            colors = AppStyles._get_colors()
            self._title_icon_label.setStyleSheet(f"color: {colors.get('accent', '#0078d4')}; font-size: 14px; background: transparent;")
        self._title_icon_label.setStyleSheet("background: transparent;")

        # 窗口标题
        self._title_label = QLabel(window_title)
        self._title_label.setStyleSheet(AppStyles.title_label_style())

        # 弹性空间
        title_layout.addWidget(self._title_icon_label)
        title_layout.addWidget(self._title_label, 1)

        # 窗口控制按钮
        btn_style = f"QPushButton {{ min-width: 40px; max-width: 40px; height: 28px; }}"

        # 置顶按钮
        self._stay_on_top_btn = QPushButton("📌")
        self._stay_on_top_btn.setObjectName("stayOnTopBtn")
        tooltip_text = self.window.language_manager.tr('tooltip_stay_on_top', 'Stay on Top') if hasattr(self.window, 'language_manager') else 'Stay on Top'
        self._stay_on_top_btn.setToolTip(tooltip_text)
        self._stay_on_top_btn.clicked.connect(self.toggle_stay_on_top)
        self._stay_on_top_btn.setStyleSheet(btn_style)
        title_layout.addWidget(self._stay_on_top_btn)

        # 最小化按钮
        self._minimize_btn = QPushButton("─")
        self._minimize_btn.setObjectName("minimizeBtn")
        self._minimize_btn.setToolTip("最小化")
        self._minimize_btn.clicked.connect(self.window.showMinimized)
        self._minimize_btn.setStyleSheet(btn_style)
        title_layout.addWidget(self._minimize_btn)

        # 最大化/还原按钮
        self._maximize_btn = QPushButton("□")
        self._maximize_btn.setObjectName("maximizeBtn")
        self._maximize_btn.setToolTip("最大化")
        self._maximize_btn.clicked.connect(self.toggle_maximize)
        self._maximize_btn.setStyleSheet(btn_style)
        title_layout.addWidget(self._maximize_btn)

        # 关闭按钮
        self._close_btn = QPushButton("✕")
        self._close_btn.setObjectName("closeButton")
        self._close_btn.setToolTip("关闭")
        self._close_btn.clicked.connect(self.window.close)
        self._close_btn.setStyleSheet(btn_style)
        title_layout.addWidget(self._close_btn)

        return self._title_bar

    def toggle_maximize(self):
        """切换最大化/还原状态"""
        if self.window.isMaximized():
            self.window.showNormal()
            self._maximize_btn.setText("□")
            self._maximize_btn.setToolTip("最大化")
        else:
            self.window.showMaximized()
            self._maximize_btn.setText("❐")
            self._maximize_btn.setToolTip("还原")

    def toggle_stay_on_top(self):
        """切换置顶状态"""
        self._stay_on_top_active = not self._stay_on_top_active
        flags = self.window.windowFlags()
        if self._stay_on_top_active:
            self.window.setWindowFlags(flags | Qt.WindowType.WindowStaysOnTopHint)
            self._stay_on_top_btn.setText("📍")
            self._stay_on_top_btn.setStyleSheet(
                f"QPushButton {{ min-width: 40px; max-width: 40px; height: 28px; "
                f"background-color: {AppStyles._get_colors().get('accent', '#0078d4')}; }}"
            )
        else:
            self.window.setWindowFlags(flags & ~Qt.WindowType.WindowStaysOnTopHint)
            btn_style = f"QPushButton {{ min-width: 40px; max-width: 40px; height: 28px; }}"
            self._stay_on_top_btn.setText("📌")
            self._stay_on_top_btn.setStyleSheet(btn_style)
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
                    if child and isinstance(child, (QPushButton,)):
                        pass
                    else:
                        self._dragging = True
                        self._drag_offset = (event.globalPosition().toPoint() - self.window.frameGeometry().topLeft())
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
