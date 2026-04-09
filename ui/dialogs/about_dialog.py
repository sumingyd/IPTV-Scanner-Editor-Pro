from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtCore import Qt
import asyncio
import platform
import sys
import aiohttp
from core.log_manager import global_logger as logger


class AboutDialog(QtWidgets.QDialog):
    # 版本配置
    CURRENT_VERSION = "42.0.0.0"  # 当前版本号(手动修改这里)
    DEFAULT_VERSION = None  # 将从GitHub获取最新版本
    BUILD_DATE = "2026-03-28"  # 更新为当前日期

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_version = self.CURRENT_VERSION
        # 关于窗口使用硬编码中文，不进行语言切换
        # 窗口拖动相关变量
        self.dragging = False
        self.offset = None
        # 从主题获取透明度设置
        from ..styles import AppStyles
        colors = AppStyles._get_colors()
        self.opacity = colors.get('window_opacity', 220)
        self._init_ui()

    def _init_ui(self):
        """初始化UI组件"""
        # 设置窗口属性
        self.setWindowTitle("关于 IPTV Scanner Editor Pro")
        self.setMinimumWidth(600)
        self.setMinimumHeight(600)
        # 设置为工具窗口，无边框，并设置背景透明
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(QtCore.Qt.WindowType.Tool | QtCore.Qt.WindowType.FramelessWindowHint | QtCore.Qt.WindowType.WindowStaysOnTopHint)
        # 确保窗口可以接收鼠标事件
        self.setMouseTracking(True)
        # 确保窗口保持活动状态
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)

        # 主布局
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)

        # 标题部分
        title_layout = QtWidgets.QVBoxLayout()
        title_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 应用图标
        logo_label = QtWidgets.QLabel()
        logo_label.setText("📺")
        logo_label.setStyleSheet("font-size: 64px; margin-bottom: 10px; background-color: transparent;")
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_layout.addWidget(logo_label)

        # 应用名称
        app_name_label = QtWidgets.QLabel("IPTV Scanner Editor Pro")
        app_name_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #6a9eff; margin-bottom: 5px; background-color: transparent;")
        app_name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_layout.addWidget(app_name_label)

        # 应用描述
        app_desc_label = QtWidgets.QLabel("IPTV 专业扫描编辑工具")
        app_desc_label.setStyleSheet("font-size: 14px; color: #aaaaaa; margin-bottom: 20px; background-color: transparent;")
        app_desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_layout.addWidget(app_desc_label)

        main_layout.addLayout(title_layout)

        # 信息卡片
        info_card = QtWidgets.QWidget()
        info_card.setObjectName("infoCard")

        info_layout = QtWidgets.QVBoxLayout(info_card)
        info_layout.setSpacing(12)

        # 版本信息
        version_group = QtWidgets.QGroupBox()
        version_layout = QtWidgets.QGridLayout(version_group)
        version_layout.setSpacing(10)

        current_version_label = QtWidgets.QLabel("当前版本：")
        current_version_label.setStyleSheet("font-weight: bold; color: white; background-color: transparent;")
        current_version_value = QtWidgets.QLabel(self.current_version)
        current_version_value.setStyleSheet("color: #6a9eff; background-color: transparent;")

        latest_version_label = QtWidgets.QLabel("最新版本：")
        latest_version_label.setStyleSheet("font-weight: bold; color: white; background-color: transparent;")
        self.latest_version_value = QtWidgets.QLabel("检测中...")
        self.latest_version_value.setStyleSheet("color: #6a9eff; background-color: transparent;")

        build_date_label = QtWidgets.QLabel("编译日期：")
        build_date_label.setStyleSheet("font-weight: bold; color: white; background-color: transparent;")
        build_date_value = QtWidgets.QLabel(self.BUILD_DATE)
        build_date_value.setStyleSheet("color: white; background-color: transparent;")

        qt_version_label = QtWidgets.QLabel("QT版本：")
        qt_version_label.setStyleSheet("font-weight: bold; color: white; background-color: transparent;")
        qt_version_value = QtWidgets.QLabel(QtCore.qVersion())
        qt_version_value.setStyleSheet("color: white; background-color: transparent;")

        version_layout.addWidget(current_version_label, 0, 0)
        version_layout.addWidget(current_version_value, 0, 1)
        version_layout.addWidget(latest_version_label, 1, 0)
        version_layout.addWidget(self.latest_version_value, 1, 1)
        version_layout.addWidget(build_date_label, 2, 0)
        version_layout.addWidget(build_date_value, 2, 1)
        version_layout.addWidget(qt_version_label, 3, 0)
        version_layout.addWidget(qt_version_value, 3, 1)

        info_layout.addWidget(version_group)

        # 系统信息
        system_info_label = QtWidgets.QLabel("系统信息：")
        system_info_label.setStyleSheet("font-weight: bold; color: white; margin-top: 10px; background-color: transparent;")
        info_layout.addWidget(system_info_label)

        system_info_value = QtWidgets.QLabel(f"Python {sys.version.split()[0]}, {platform.system()} {platform.release()}")
        system_info_value.setStyleSheet("color: white; background-color: transparent;")
        info_layout.addWidget(system_info_value)

        main_layout.addWidget(info_card)



        # 底部信息
        bottom_layout = QtWidgets.QVBoxLayout()
        bottom_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bottom_layout.setSpacing(10)

        copyright_label = QtWidgets.QLabel("© 2025 IPTV Scanner Editor Pro 版权所有")
        copyright_label.setStyleSheet("color: #aaaaaa; font-size: 12px; background-color: transparent;")
        copyright_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bottom_layout.addWidget(copyright_label)

        github_link = QtWidgets.QLabel()
        github_link.setText('<a href="https://github.com/sumingyd/IPTV-Scanner-Editor-Pro" style="color: #6a9eff; text-decoration: none;">GitHub 仓库</a>')
        github_link.setOpenExternalLinks(True)
        github_link.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bottom_layout.addWidget(github_link)

        main_layout.addLayout(bottom_layout)

        # 按钮
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        close_btn = QtWidgets.QPushButton("关闭")
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(close_btn)

        main_layout.addLayout(button_layout)

        # 导入样式
        from ui.styles import AppStyles

        # 使用自定义样式
        self.setStyleSheet(AppStyles.about_dialog_style())

        # 启动版本检查
        QtCore.QTimer.singleShot(100, self._check_version_async)

    def _check_version_async(self):
        """异步检查版本"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            latest_version, publish_date = loop.run_until_complete(
                asyncio.wait_for(self._get_latest_version(), timeout=5)
            )
            if latest_version and latest_version not in ("请求超时", "获取失败"):
                self.latest_version_value.setText(latest_version)
            else:
                self.latest_version_value.setText(latest_version)
        except asyncio.TimeoutError:
            self.latest_version_value.setText("(请求超时)")
        except Exception:
            self.latest_version_value.setText("(获取失败)")
        finally:
            loop.close()

    async def _get_latest_version(self):
        """从GitHub获取最新版本信息"""
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
                        return "(API限制)", ""
                    else:
                        return "(获取失败)", ""
        except asyncio.TimeoutError:
            return "(请求超时)", ""
        except Exception as e:
            logger.error(f"获取最新版本失败: {str(e)}")
            return "(获取失败)", ""

    def mousePressEvent(self, event):
        """鼠标按下事件，开始拖动"""
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            # 检查事件是否发生在标签链接上
            widget = self.childAt(event.position().toPoint())
            if isinstance(widget, QtWidgets.QLabel) and widget.openExternalLinks():
                # 如果是链接标签，不启动拖动
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
        
        # 从主题中获取颜色
        colors = AppStyles._get_colors()
        
        # 创建圆角矩形路径
        path = QPainterPath()
        rect = QRectF(self.rect().adjusted(1, 1, -1, -1))
        path.addRoundedRect(rect, 12, 12)
        
        # 绘制半透明背景（只在圆角内）
        bg_color = colors.get('window', '#333333')
        if bg_color.startswith('#'):
            r = int(bg_color[1:3], 16)
            g = int(bg_color[3:5], 16)
            b = int(bg_color[5:7], 16)
        else:
            r, g, b = 30, 30, 30
        painter.fillPath(path, QColor(r, g, b, self.opacity))
        
        # 绘制边框
        border_color = colors.get('mid', '#999999')
        if border_color.startswith('#'):
            r = int(border_color[1:3], 16)
            g = int(border_color[3:5], 16)
            b = int(border_color[5:7], 16)
        else:
            r, g, b = 120, 120, 120
        painter.setPen(QColor(r, g, b, 200))
        painter.drawPath(path)
        
        # 调用父类的 paintEvent 来绘制子控件
        super().paintEvent(event)
