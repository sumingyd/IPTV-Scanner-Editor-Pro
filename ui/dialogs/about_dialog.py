from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtCore import Qt
import asyncio
import platform
import sys
import aiohttp
from core.log_manager import global_logger as logger


class AboutDialog(QtWidgets.QDialog):
    CURRENT_VERSION = "43.0.0.0"
    DEFAULT_VERSION = None
    BUILD_DATE = "2026-04-10"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_version = self.CURRENT_VERSION
        self.dragging = False
        self.offset = None
        from ..styles import AppStyles
        colors = AppStyles._get_colors()
        self.opacity = colors.get('window_opacity', 220)
        self.language_manager = getattr(parent, 'language_manager', None)
        if not self.language_manager:
            from core.language_manager import LanguageManager
            self.language_manager = LanguageManager()
            self.language_manager.load_available_languages()
            self.language_manager.set_language('zh')
        self._init_ui()

    def _init_ui(self):
        """初始化UI组件"""
        tr = self.language_manager.tr
        self.setWindowTitle(tr("about_dialog_title", "About IPTV Scanner Editor Pro"))
        self.setMinimumWidth(520)
        self.setMinimumHeight(480)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(QtCore.Qt.WindowType.Tool | QtCore.Qt.WindowType.FramelessWindowHint | QtCore.Qt.WindowType.WindowStaysOnTopHint)
        self.setMouseTracking(True)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 16)
        main_layout.setSpacing(12)

        title_layout = QtWidgets.QVBoxLayout()
        title_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_layout.setSpacing(4)

        logo_label = QtWidgets.QLabel()
        logo_label.setText("📺")
        logo_label.setStyleSheet("font-size: 48px; background-color: transparent;")
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_layout.addWidget(logo_label)

        app_name_label = QtWidgets.QLabel("IPTV Scanner Editor Pro")
        app_name_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #6a9eff; background-color: transparent;")
        app_name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_layout.addWidget(app_name_label)

        self.app_desc_label = QtWidgets.QLabel(tr("app_description", "IPTV Professional Scanner & Editor"))
        self.app_desc_label.setStyleSheet("font-size: 12px; color: #aaaaaa; background-color: transparent;")
        self.app_desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_layout.addWidget(self.app_desc_label)

        main_layout.addLayout(title_layout)

        info_card = QtWidgets.QWidget()
        info_card.setObjectName("infoCard")
        info_layout = QtWidgets.QVBoxLayout(info_card)
        info_layout.setSpacing(6)
        info_layout.setContentsMargins(8, 8, 8, 8)

        version_group = QtWidgets.QGroupBox()
        version_layout = QtWidgets.QGridLayout(version_group)
        version_layout.setSpacing(6)
        version_layout.setContentsMargins(4, 4, 4, 4)

        label_style = "font-weight: bold; color: white; background-color: transparent; font-size: 12px;"
        value_style = "color: #6a9eff; background-color: transparent; font-size: 12px;"
        value_style_white = "color: white; background-color: transparent; font-size: 12px;"

        current_version_label = QtWidgets.QLabel(f"{tr('current_version', 'Current Version')}：")
        current_version_label.setStyleSheet(label_style)
        current_version_value = QtWidgets.QLabel(self.current_version)
        current_version_value.setStyleSheet(value_style)

        latest_version_label = QtWidgets.QLabel(f"{tr('latest_version', 'Latest Version')}：")
        latest_version_label.setStyleSheet(label_style)
        self.latest_version_value = QtWidgets.QLabel(tr("checking_update", "Checking..."))
        self.latest_version_value.setStyleSheet(value_style)

        build_date_label = QtWidgets.QLabel(f"{tr('build_date', 'Build Date')}：")
        build_date_label.setStyleSheet(label_style)
        build_date_value = QtWidgets.QLabel(self.BUILD_DATE)
        build_date_value.setStyleSheet(value_style_white)

        qt_version_label = QtWidgets.QLabel(f"{tr('qt_version', 'QT Version')}：")
        qt_version_label.setStyleSheet(label_style)
        qt_version_value = QtWidgets.QLabel(QtCore.qVersion())
        qt_version_value.setStyleSheet(value_style_white)

        version_layout.addWidget(current_version_label, 0, 0)
        version_layout.addWidget(current_version_value, 0, 1)
        version_layout.addWidget(latest_version_label, 1, 0)
        version_layout.addWidget(self.latest_version_value, 1, 1)
        version_layout.addWidget(build_date_label, 2, 0)
        version_layout.addWidget(build_date_value, 2, 1)
        version_layout.addWidget(qt_version_label, 3, 0)
        version_layout.addWidget(qt_version_value, 3, 1)

        info_layout.addWidget(version_group)

        self.system_info_label = QtWidgets.QLabel(f"{tr('system_info', 'System Info')}：")
        self.system_info_label.setStyleSheet("font-weight: bold; color: white; margin-top: 4px; background-color: transparent; font-size: 12px;")
        info_layout.addWidget(self.system_info_label)

        system_info_value = QtWidgets.QLabel(f"Python {sys.version.split()[0]}, {platform.system()} {platform.release()}")
        system_info_value.setStyleSheet("color: white; background-color: transparent; font-size: 12px;")
        info_layout.addWidget(system_info_value)

        main_layout.addWidget(info_card)

        bottom_layout = QtWidgets.QVBoxLayout()
        bottom_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bottom_layout.setSpacing(6)

        self.copyright_label = QtWidgets.QLabel(tr("copyright_text", "© 2025 IPTV Scanner Editor Pro"))
        self.copyright_label.setStyleSheet("color: #aaaaaa; font-size: 11px; background-color: transparent;")
        self.copyright_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bottom_layout.addWidget(self.copyright_label)

        github_link = QtWidgets.QLabel()
        github_link.setText(f'<a href="https://github.com/sumingyd/IPTV-Scanner-Editor-Pro" style="color: #6a9eff; text-decoration: none;">{tr("github_repo", "GitHub Repository")}</a>')
        github_link.setOpenExternalLinks(True)
        github_link.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bottom_layout.addWidget(github_link)

        main_layout.addLayout(bottom_layout)

        button_layout = QtWidgets.QHBoxLayout()
        button_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        close_btn = QtWidgets.QPushButton(tr("close_button", "Close"))
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(close_btn)

        main_layout.addLayout(button_layout)

        from ui.styles import AppStyles
        self.setStyleSheet(AppStyles.about_dialog_style())

        QtCore.QTimer.singleShot(100, self._check_version_async)

    def _check_version_async(self):
        """异步检查版本"""
        tr = self.language_manager.tr
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            latest_version, publish_date = loop.run_until_complete(
                asyncio.wait_for(self._get_latest_version(), timeout=5)
            )
            if latest_version and latest_version not in (tr("request_timeout_text", "(Request Timeout)"), tr("fetch_failed_text", "(Fetch Failed)")):
                self.latest_version_value.setText(latest_version)
            else:
                self.latest_version_value.setText(latest_version)
        except asyncio.TimeoutError:
            self.latest_version_value.setText(tr("request_timeout_text", "(Request Timeout)"))
        except Exception:
            self.latest_version_value.setText(tr("fetch_failed_text", "(Fetch Failed)"))
        finally:
            loop.close()

    async def _get_latest_version(self):
        """从GitHub获取最新版本信息"""
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
        """鼠标按下事件，开始拖动"""
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            widget = self.childAt(event.position().toPoint())
            if isinstance(widget, QtWidgets.QLabel) and widget.openExternalLinks():
                return
            self.dragging = True
            self.offset = event.position().toPoint()

    def mouseMoveEvent(self, event):
        """鼠标移动事件，执行拖动"""
        if self.dragging:
            new_position = event.globalPosition().toPoint() - self.offset
            self.move(new_position)

    def mouseReleaseEvent(self, event):
        """鼠标释放事件，结束拖动"""
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.dragging = False

    def paintEvent(self, event):
        """自定义绘制半透明背景和边框"""
        from PyQt6.QtGui import QPainter, QPainterPath
        from PyQt6.QtCore import QRectF
        from PyQt6.QtGui import QColor
        from ui.styles import AppStyles
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        colors = AppStyles._get_colors()
        
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
