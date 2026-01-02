from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtCore import Qt
import asyncio
import platform
import sys
import aiohttp
from core.log_manager import global_logger as logger


class AboutDialog(QtWidgets.QDialog):
    # 版本配置
    CURRENT_VERSION = "33.0.0.0"  # 当前版本号(手动修改这里)
    DEFAULT_VERSION = None  # 将从GitHub获取最新版本
    BUILD_DATE = "2026-01-01"  # 更新为当前日期

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_version = self.CURRENT_VERSION
        # 关于窗口使用硬编码中文，不进行语言切换
        self._init_ui()

    # 样式常量
    LIGHT_THEME = {
        'bg': "#ffffff",
        'text': "#333333",
        'card': "#f8f9fa",
        'border': "#e0e0e0",
        'code_bg': "#f0f0f0",
        'code_text': "#333333"
    }

    DARK_THEME = {
        'bg': "#2d2d2d",
        'text': "#eeeeee",
        'card': "#3a3a3a",
        'border': "#444444",
        'code_bg': "#454545",
        'code_text': "#ffffff"
    }

    ACCENT_COLOR = "#3498db"  # 主色调

    def _init_ui(self):
        """初始化UI组件"""
        theme = self.DARK_THEME if self.palette().window().color().lightness() < 128 else self.LIGHT_THEME

        text_browser = QtWidgets.QTextBrowser()
        text_browser.setObjectName("aboutTextBrowser")
        text_browser.setHtml(self._get_about_html(theme))
        text_browser.setOpenExternalLinks(True)
        text_browser.setOpenLinks(False)
        text_browser.anchorClicked.connect(self._on_link_activated)

        close_btn = QtWidgets.QPushButton("关闭")
        close_btn.clicked.connect(self.close)

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(text_browser)
        layout.addWidget(close_btn, 0, Qt.AlignmentFlag.AlignCenter)

        self.setLayout(layout)
        self.setMinimumWidth(500)
        self.setMinimumHeight(580)

        # 导入样式
        from ui.styles import AppStyles

        # 使用统一的对话框样式和按钮样式
        self.setStyleSheet(AppStyles.dialog_style() + AppStyles.button_style() + f"""
            QDialog {{
                background-color: {theme['bg']};
                color: {theme['text']};
            }}
        """)
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.WindowType.WindowStaysOnTopHint)

        # 设置窗口标题
        self.setWindowTitle("关于 IPTV Scanner Editor Pro")

    def _get_about_html(self, theme):
        """生成关于对话框的HTML内容"""
        return f'''
        <div style="font-family: 'Microsoft YaHei', sans-serif; color: {theme['text']};">
            <h1 style="color: {self.ACCENT_COLOR}; text-align: center; margin-bottom: 15px; font-size: 18px;">
                IPTV Scanner Editor Pro / IPTV 专业扫描编辑工具
            </h1>

            <div style="background-color: {theme['card']}; padding: 15px; border-radius: 8px;
                 margin-bottom: 15px; border: 1px solid {theme['border']};">
                <p style="line-height: 1.6; margin: 5px 0;">
                    <b>当前版本：</b> {self.current_version}
                </p>
                <p style="line-height: 1.6; margin: 5px 0;">
                    <b>最新版本：</b> <span id="latestVersion"></span>
                </p>
                <p style="line-height: 1.6; margin: 5px 0;">
                    <b>编译日期：</b> {self.BUILD_DATE}
                </p>
                <p style="line-height: 1.6; margin: 5px 0;">
                    <b>QT版本：</b> {QtCore.qVersion()}
                </p>
            </div>

            <h3 style="color: {self.ACCENT_COLOR}; border-bottom: 1px solid {theme['border']};
                padding-bottom: 5px; font-size: 15px; margin-top: 0;">
                主要功能说明
            </h3>
            <ul style="margin-left: 20px; line-height: 1.6; padding-left: 5px;">
                <li><b>智能频道扫描</b>：
                    <ul style="margin-left: 15px; line-height: 1.5; list-style-type: circle;">
                        <li>设定范围地址进行扫描(如239.1.1.[1-255]:5002)，列出范围内有效频道</li>
                        <li>支持单播、组播、流链接，支持包含多个范围的地址</li>
                        <li>支持自定义扫描超时时间和线程数</li>
                        <li><i>在扫描设置中输入地址格式，点击"完整扫描"开始</i></li>
                    </ul>
                </li>
                <li><b>高级流验证</b>：
                    <ul style="margin-left: 15px; line-height: 1.5; list-style-type: circle;">
                        <li>打开一个下载的播放列表，批量检测频道有效性</li>
                        <li>支持多线程并发检测，提高验证效率</li>
                        <li>自动识别无效频道并标记状态</li>
                        <li><i>打开播放列表后点击"检测有效性"按钮</i></li>
                    </ul>
                </li>
                <li><b>智能频道管理</b>：
                    <ul style="margin-left: 15px; line-height: 1.5; list-style-type: circle;">
                        <li>支持拖拽调整频道顺序</li>
                        <li>支持右键删除选定频道、复制频道名及URL</li>
                        <li>频道会尝试获取频道名并通过映射文件匹配频道名、LOGO、分组</li>
                        <li>频道名的映射文件在仓库，可以直接去仓库提交修改</li>
                        <li>频道的logo可以直接在仓库提交上传到logo文件夹</li>
                        <li>支持频道分组管理和批量操作</li>
                        <li><i>右键频道列表或拖拽调整顺序</i></li>
                    </ul>
                </li>
                <li><b>集成视频播放</b>：
                    <ul style="margin-left: 15px; line-height: 1.5; list-style-type: circle;">
                        <li>双击频道列表可直接播放当前频道</li>
                        <li>支持VLC播放器集成，提供流畅的播放体验</li>
                        <li>自动检测播放器状态和连接质量</li>
                        <li><i>双击频道列表中的任意频道</i></li>
                    </ul>
                </li>
                <li><b>高级配置管理</b>：
                    <ul style="margin-left: 15px; line-height: 1.5; list-style-type: circle;">
                        <li>配置文件(config.ini)自动保存在程序目录</li>
                        <li>日志文件(app.log)自动轮转，最大5MB保留3个</li>
                        <li>支持自定义界面样式和主题设置</li>
                        <li>所有样式定义统一管理，确保界面一致性</li>
                        <li><i>所有设置自动保存，无需手动操作</i></li>
                    </ul>
                </li>
                <li><b>专业工具集成</b>：
                    <ul style="margin-left: 15px; line-height: 1.5; list-style-type: circle;">
                        <li>URL解析器，支持复杂地址格式</li>
                        <li>频道映射管理器，可视化编辑映射规则</li>
                        <li>排序配置工具，支持多级排序和自定义优先级</li>
                        <li>错误处理系统，智能恢复和错误报告</li>
                        <li>性能优化，支持大规模频道列表处理</li>
                        <li>多语言支持，界面文本可切换</li>
                        <li><i>通过工具栏访问各专业工具</i></li>
                    </ul>
                </li>
                <li><b>频道映射管理器</b>：
                    <ul style="margin-left: 15px; line-height: 1.5; list-style-type: circle;">
                        <li>用户映射管理：添加、编辑、删除频道映射规则</li>
                        <li>频道指纹查看：分析频道识别特征和映射历史</li>
                        <li>映射建议：基于历史数据智能推荐映射规则</li>
                        <li>支持导入/导出映射配置，便于备份和分享</li>
                        <li><i>通过"工具"菜单打开"频道映射管理器"</i></li>
                    </ul>
                </li>
                <li><b>排序配置功能</b>：
                    <ul style="margin-left: 15px; line-height: 1.5; list-style-type: circle;">
                        <li>支持三级排序优先级设置（主、次、第三优先级）</li>
                        <li>多种排序字段：分组、名称、分辨率、延迟、状态</li>
                        <li>灵活的排序方式：字母顺序、拼音、质量高低等</li>
                        <li>分组优先级自定义排序，支持拖拽调整顺序</li>
                        <li><i>通过"工具"菜单打开"排序配置"</i></li>
                    </ul>
                </li>
                <li><b>界面与样式</b>：
                    <ul style="margin-left: 15px; line-height: 1.5; list-style-type: circle;">
                        <li>统一的样式管理系统，所有界面元素风格一致</li>
                        <li>现代化的UI设计，支持深色/浅色主题</li>
                        <li>响应式布局，适应不同屏幕尺寸</li>
                        <li>按钮、标签页、对话框等组件样式统一</li>
                        <li><i>所有样式定义在styles.py文件中集中管理</i></li>
                    </ul>
                </li>
            </ul>

            <div style="margin-top: 20px; text-align: center; font-size: 0.9em; color: {theme['text']}; opacity: 0.8;">
                <p>© 2025 IPTV Scanner Editor Pro 版权所有</p>
                <p>
                    <a href="https://github.com/sumingyd/IPTV-Scanner-Editor-Pro"
                       style="color: {self.ACCENT_COLOR}; text-decoration: none;">GitHub 仓库</a>
                </p>
                <p style="font-size: 0.8em; margin-top: 10px;">
                    系统信息: Python {sys.version.split()[0]}, {platform.system()} {platform.release()}
                </p>
            </div>
        </div>
        '''

    def show(self):
        """显示对话框并异步更新最新版本号"""
        text_browser = self.findChild(QtWidgets.QTextBrowser, "aboutTextBrowser")
        if not text_browser:
            return

        # 先显示对话框
        super().show()
        QtWidgets.QApplication.processEvents()

        # 延迟100ms确保对话框完全显示后再设置文本
        def set_initial_text():
            # 直接使用原始HTML内容替换，避免toHtml()可能的问题
            original_html = self._get_about_html(
                self.DARK_THEME if self.palette().window().color().lightness() < 128 else self.LIGHT_THEME
                )
            initial_html = original_html.replace(
                '<span id="latestVersion"></span>',
                '<span id="latestVersion">检测中...</span>'
            )
            text_browser.setHtml(initial_html)

            # 再延迟100ms开始版本检查
            QtCore.QTimer.singleShot(100, lambda: self._check_version_async(text_browser))

        QtCore.QTimer.singleShot(100, set_initial_text)

    def _check_version_async(self, text_browser):
        """异步检查版本"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            latest_version, publish_date = loop.run_until_complete(
                asyncio.wait_for(self._get_latest_version(), timeout=5)
            )
            if latest_version and latest_version not in ("请求超时", "获取失败"):
                self._update_version_text(text_browser, version=latest_version)
            else:
                self._show_version_error(latest_version)
        except asyncio.TimeoutError:
            self._show_version_error("(请求超时)")
        except Exception:
            self._show_version_error("(获取失败)")
        finally:
            loop.close()

    def _update_version_text(self, text_browser, version=None, date=None, error_msg=None):
        """更新版本号文本"""
        if text_browser:
            # 确定要设置的内容
            content = version if version is not None else error_msg

            if content is not None:
                # 方法1: 直接重建整个HTML
                theme = self.DARK_THEME if self.palette().window().color().lightness() < 128 else self.LIGHT_THEME
                full_html = self._get_about_html(theme).replace(
                    '<span id="latestVersion"></span>',
                    f'<span id="latestVersion">{content}</span>'
                )
                text_browser.setHtml(full_html)

                # 强制刷新界面
                text_browser.repaint()
                QtWidgets.QApplication.processEvents()

                # 使用QTimer延迟执行确保更新
                QtCore.QTimer.singleShot(100, lambda: (
                    text_browser.setHtml(full_html),
                    text_browser.repaint(),
                    QtWidgets.QApplication.processEvents()
                ))

    def _show_version_error(self, error_msg):
        """显示版本获取错误信息"""
        text_browser = self.findChild(QtWidgets.QTextBrowser, "aboutTextBrowser")
        self._update_version_text(text_browser, error_msg=error_msg)

    def _on_link_activated(self, link):
        """处理链接点击事件"""
        link_str = link.toString()

        if link_str.startswith("http"):
            QtGui.QDesktopServices.openUrl(QtCore.QUrl(link))

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
