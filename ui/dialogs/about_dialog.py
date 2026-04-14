import os

from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame
import asyncio
import platform
import sys
import aiohttp
from core.log_manager import global_logger as logger
from ..floating_dialog import FloatingDialog


class AboutDialog(FloatingDialog):
    CURRENT_VERSION = "44.0.0.4"
    DEFAULT_VERSION = None
    BUILD_DATE = "2026-04-15"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_version = self.CURRENT_VERSION
        self.language_manager = getattr(parent, 'language_manager', None)
        if not self.language_manager:
            from core.language_manager import LanguageManager
            self.language_manager = LanguageManager()
            self.language_manager.load_available_languages()
            self.language_manager.set_language('zh')
        from ..styles import AppStyles
        self._colors = AppStyles._get_colors()
        self._init_ui()
    
    def _init_ui(self):
        """初始化 UI"""
        tr = self.language_manager.tr
        c = self._colors
        self.setWindowTitle(tr("about_dialog_title", "About IPTV Scanner Editor Pro"))
        self.setFixedSize(480, 420)

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(28, 24, 28, 20)
        main_layout.setSpacing(0)

        # 图标居中显示
        logo_label = QtWidgets.QLabel()
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        from PyQt6.QtGui import QPixmap, QIcon
        from utils.general_utils import get_icon_path
        ico_path = get_icon_path()
        if os.path.exists(ico_path):
            # 使用 QIcon 读取 ICO 文件，然后获取最大尺寸的 pixmap
            icon = QIcon(ico_path)
            # 获取所有可用尺寸
            available_sizes = icon.availableSizes()
            if available_sizes:
                # 找到最大的尺寸
                max_size = max(available_sizes, key=lambda s: s.width() * s.height())
                pixmap = icon.pixmap(max_size)
            else:
                pixmap = icon.pixmap(256, 256)  # 默认使用 256x256
            
            if not pixmap.isNull():
                # 缩放到 128x128，保持宽高比，使用平滑变换
                scaled = pixmap.scaled(128, 128, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                logo_label.setPixmap(scaled)
        else:
            logo_label.setText("📺")
            logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_label.setStyleSheet("background-color: transparent;")
        main_layout.addWidget(logo_label)

        main_layout.addSpacing(16)

        card = QtWidgets.QWidget()
        card.setStyleSheet(f"""
            QWidget#infoCard {{
                background-color: {c['alternate_base']};
                border-radius: 8px;
                padding: 4px;
            }}
        """)
        card.setObjectName("infoCard")
        card_layout = QtWidgets.QVBoxLayout(card)
        card_layout.setContentsMargins(16, 12, 16, 12)
        card_layout.setSpacing(8)

        lbl_style = f"font-size: 12px; color: {c['window_text']}; background-color: transparent;"
        val_style = f"font-size: 12px; color: {c['accent']}; background-color: transparent;"

        rows = [
            (f"{tr('current_version', 'Current Version')}", self.current_version, True),
            (f"{tr('latest_version', 'Latest Version')}", None, True),
            (f"{tr('build_date', 'Build Date')}", self.BUILD_DATE, False),
            (f"{tr('qt_version', 'QT Version')}", QtCore.qVersion(), False),
        ]

        self.latest_version_value = None
        for label_text, value_text, is_accent in rows:
            row = QtWidgets.QHBoxLayout()
            row.setSpacing(8)
            lbl = QtWidgets.QLabel(label_text)
            lbl.setStyleSheet(lbl_style)
            lbl.setFixedWidth(100)
            val = QtWidgets.QLabel(value_text if value_text else tr("checking_update", "Checking..."))
            val.setStyleSheet(val_style if is_accent else lbl_style)
            if value_text is None:
                self.latest_version_value = val
            row.addWidget(lbl)
            row.addWidget(val)
            row.addStretch()
            card_layout.addLayout(row)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background-color: {c['mid']}; max-height: 1px; margin: 4px 0;")
        card_layout.addWidget(sep)

        sys_row = QtWidgets.QHBoxLayout()
        sys_row.setSpacing(8)
        sys_lbl = QtWidgets.QLabel(f"{tr('system_info', 'System Info')}")
        sys_lbl.setStyleSheet(lbl_style)
        sys_lbl.setFixedWidth(100)
        sys_val = QtWidgets.QLabel(f"Python {sys.version.split()[0]}, {platform.system()} {platform.release()}")
        sys_val.setStyleSheet(lbl_style)
        sys_row.addWidget(sys_lbl)
        sys_row.addWidget(sys_val)
        sys_row.addStretch()
        card_layout.addLayout(sys_row)

        main_layout.addWidget(card)

        main_layout.addSpacing(16)

        bottom_layout = QtWidgets.QHBoxLayout()
        bottom_layout.setSpacing(12)

        self.copyright_label = QtWidgets.QLabel(tr("copyright_text", "© 2025-2026 IPTV Scanner Editor Pro"))
        self.copyright_label.setStyleSheet(f"font-size: 10px; color: {c['player_panel_secondary']}; background-color: transparent;")

        github_link = QtWidgets.QLabel()
        github_link.setText(f'<a href="https://github.com/sumingyd/IPTV-Scanner-Editor-Pro" style="color: {c["accent"]}; text-decoration: none; font-size: 10px;">{tr("github_repo", "GitHub Repository")}</a>')
        github_link.setOpenExternalLinks(True)

        close_btn = QtWidgets.QPushButton(tr("close_button", "Close"))
        close_btn.setFixedSize(72, 28)
        from ui.styles import AppStyles
        close_btn.setStyleSheet(AppStyles.button_style())
        close_btn.clicked.connect(self.close)

        bottom_layout.addWidget(self.copyright_label)
        bottom_layout.addWidget(github_link)
        bottom_layout.addStretch()
        bottom_layout.addWidget(close_btn)

        main_layout.addLayout(bottom_layout)

        self.setStyleSheet(AppStyles.dialog_style())
        # 使用线程异步检查版本，不阻塞 UI
        import threading
        thread = threading.Thread(target=self._check_version_thread, daemon=True)
        thread.start()
    
    def _check_version_thread(self):
        """在线程中检查版本（不阻塞 UI）"""
        tr = self.language_manager.tr
        from core.log_manager import global_logger as logger
        logger.info("开始检查版本...")
        try:
            # 在线程中运行异步代码
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                logger.debug("开始获取最新版本...")
                latest_version, publish_date = loop.run_until_complete(
                    asyncio.wait_for(self._get_latest_version(), timeout=5)
                )
                logger.debug(f"获取到最新版本：{latest_version}")
                # 保存结果到实例变量
                self._latest_version_result = latest_version
                # 在主线程中更新 UI
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(0, self._update_version_ui)
            finally:
                loop.close()
        except asyncio.TimeoutError:
            logger.error("版本检查超时")
            self._latest_version_result = tr("request_timeout_text", "(Request Timeout)")
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(0, self._update_version_ui)
        except Exception as e:
            logger.error(f"版本检查失败：{e}")
            self._latest_version_result = tr("fetch_failed_text", "(Fetch Failed)")
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(0, self._update_version_ui)
    
    def _update_version_ui(self):
        """在主线程中更新版本显示"""
        from core.log_manager import global_logger as logger
        logger.debug(f"更新 UI 版本号：{self._latest_version_result}")
        if hasattr(self, 'latest_version_value'):
            self.latest_version_value.setText(self._latest_version_result)

    async def _get_latest_version(self):
        tr = self.language_manager.tr
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://api.github.com/repos/sumingyd/IPTV-Scanner-Editor-Pro/releases/latest",
                    headers={'User-Agent': 'IPTV-Scanner-Editor-Pro'}
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        version = data.get('tag_name', '').lstrip('v')
                        publish_date = data.get('published_at', '')
                        return version, publish_date
                    elif response.status == 403:
                        return tr("api_limit_text", "(API Limit)"), ""
                    else:
                        return tr("fetch_failed_text", "(Fetch Failed)"), ""
        except asyncio.TimeoutError:
            return tr("request_timeout_text", "(Request Timeout)"), ""
        except Exception as e:
            logger.error(f"获取最新版本失败: {str(e)}")
            return tr("fetch_failed_text", "(Fetch Failed)"), ""

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            widget = self.childAt(event.position().toPoint())
            if isinstance(widget, QtWidgets.QLabel) and widget.openExternalLinks():
                return
            self.dragging = True
            self.offset = event.position().toPoint()

    def mouseMoveEvent(self, event):
        if self.dragging:
            new_position = event.globalPosition().toPoint() - self.offset
            self.move(new_position)

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.dragging = False

    def paintEvent(self, event):
        from PyQt6.QtGui import QPainter, QPainterPath
        from PyQt6.QtCore import QRectF
        from PyQt6.QtGui import QColor
        from ui.styles import AppStyles

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        colors = AppStyles._get_colors()
        neo = AppStyles.is_neumorphic()

        path = QPainterPath()
        rect = QRectF(self.rect().adjusted(1, 1, -1, -1))
        path.addRoundedRect(rect, 12, 12)

        bg_color = colors.get('window', '#333333')
        if bg_color.startswith('#'):
            r = int(bg_color[1:3], 16)
            g = int(bg_color[3:5], 16)
            b = int(bg_color[5:7], 16)
        else:
            r, g, b = 30, 30, 30
        painter.fillPath(path, QColor(r, g, b, self.opacity))

        if not neo:
            border_color = colors.get('mid', '#999999')
            if border_color.startswith('#'):
                r = int(border_color[1:3], 16)
                g = int(border_color[3:5], 16)
                b = int(border_color[5:7], 16)
            else:
                r, g, b = 120, 120, 120
            painter.setPen(QColor(r, g, b, 200))
            painter.drawPath(path)

        super().paintEvent(event)
