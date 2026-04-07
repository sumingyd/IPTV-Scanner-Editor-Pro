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
        self.opacity = 220
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
        info_card.setStyleSheet("""
            #infoCard {
                background-color: rgba(50, 50, 50, 200);
                border-radius: 10px;
                border: 1px solid rgba(100, 100, 100, 200);
                padding: 20px;
            }
        """)

        info_layout = QtWidgets.QVBoxLayout(info_card)
        info_layout.setSpacing(12)

        # 版本信息
        version_group = QtWidgets.QGroupBox()
        version_group.setStyleSheet("""
            QGroupBox {
                background-color: transparent;
                border: none;
                margin-top: 0;
            }
        """)
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

        # 功能特性
        features_title = QtWidgets.QLabel("主要功能特性")
        features_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #6a9eff; margin-top: 10px; background-color: transparent;")
        main_layout.addWidget(features_title)

        features_widget = QtWidgets.QWidget()
        features_widget.setStyleSheet("background-color: transparent;")
        features_layout = QtWidgets.QVBoxLayout(features_widget)
        features_layout.setSpacing(8)

        features = [
            "智能频道扫描：支持范围地址扫描，自动检测有效频道",
            "高级流验证：多线程并发检测频道有效性",
            "智能频道管理：支持拖拽排序、批量操作和频道映射",
            "集成视频播放：双击频道直接播放，支持VLC集成",
            "高级配置管理：自动保存配置，支持自定义样式",
            "专业工具集成：URL解析器、频道映射管理器、排序配置工具",
            "多语言支持：界面文本可切换",
            "现代化UI：统一的样式管理，支持深色/浅色主题"
        ]

        for feature in features:
            feature_label = QtWidgets.QLabel(f"• {feature}")
            feature_label.setStyleSheet("color: white; padding-left: 10px; background-color: transparent;")
            features_layout.addWidget(feature_label)

        main_layout.addWidget(features_widget)

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
        github_link.setStyleSheet("background-color: transparent;")
        bottom_layout.addWidget(github_link)

        main_layout.addLayout(bottom_layout)

        # 按钮
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        close_btn = QtWidgets.QPushButton("关闭")
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(50, 50, 50, 200);
                color: white;
                border: 1px solid rgba(100, 100, 100, 200);
                border-radius: 4px;
                padding: 8px 24px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: rgba(60, 60, 60, 220);
            }
            QPushButton:pressed {
                background-color: rgba(40, 40, 40, 220);
            }
        """)
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(close_btn)

        main_layout.addLayout(button_layout)

        # 导入样式
        from ui.styles import AppStyles

        # 使用自定义样式，确保所有元素都使用透明背景
        self.setStyleSheet("""
            QDialog {
                background-color: transparent;
            }
            QLabel {
                background-color: transparent;
            }
            QWidget {
                background-color: transparent;
            }
            QGroupBox {
                background-color: transparent;
                border: none;
            }
        """)

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
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 创建圆角矩形路径
        path = QPainterPath()
        rect = QRectF(self.rect().adjusted(1, 1, -1, -1))
        path.addRoundedRect(rect, 12, 12)
        
        # 绘制半透明背景（只在圆角内）
        painter.fillPath(path, QColor(30, 30, 30, self.opacity))
        
        # 绘制边框
        painter.setPen(QColor(120, 120, 120, 200))
        painter.drawPath(path)
        
        # 调用父类的 paintEvent 来绘制子控件
        super().paintEvent(event)
