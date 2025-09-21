from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtCore import Qt
import asyncio
import datetime
import platform
import sys

import aiohttp

from log_manager import LogManager
logger = LogManager()

class AboutDialog(QtWidgets.QDialog):
    # 版本配置
    CURRENT_VERSION = "23.0.0.0"  # 当前版本号(手动修改这里)
    DEFAULT_VERSION = None  # 将从GitHub获取最新版本
    BUILD_DATE = "2025-09-22"  # 更新为当前日期
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_version = self.CURRENT_VERSION
        self.setWindowTitle("关于 IPTV Scanner Editor Pro")
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
        
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {theme['bg']};
                color: {theme['text']};
            }}
            QPushButton {{
                background-color: {self.ACCENT_COLOR};
                color: white;
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
                min-width: 80px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #2980b9;
            }}
        """)
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.WindowType.WindowStaysOnTopHint)

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
                <li><b>频道扫描</b>：
                    <ul style="margin-left: 15px; line-height: 1.5; list-style-type: circle;">
                        <li>设定范围地址进行扫描(如239.1.1.[1-255]:5002)，列出范围内有效频道</li>
                        <li>支持单播、组播、流链接，支持包含多个范围的地址</li>
                        <li>支持自定义扫描超时时间和线程数</li>
                    </ul>
                </li>
                <li><b>有效性检测</b>：
                    <ul style="margin-left: 15px; line-height: 1.5; list-style-type: circle;">
                        <li>打开一个下载的播放列表，批量检测频道有效性</li>
                    </ul>
                </li>
                <li><b>频道管理</b>：
                    <ul style="margin-left: 15px; line-height: 1.5; list-style-type: circle;">
                        <li>支持拖拽调整频道顺序</li>
                        <li>支持右键删除选定频道、复制频道名及URL</li>
                        <li>频道会尝试获取频道名并通过映射文件匹配频道名、LOGO、分组</li>
                        <li>频道名的映射文件在仓库，可以直接去仓库提交修改</li>
                        <li>频道的logo可以直接在仓库提交上传到logo文件夹</li>
                    </ul>
                </li>
                <li><b>视频播放</b>：
                    <ul style="margin-left: 15px; line-height: 1.5; list-style-type: circle;">
                        <li>双击频道列表可直接播放当前频道</li>
                    </ul>
                </li>
                <li><b>配置管理</b>：
                    <ul style="margin-left: 15px; line-height: 1.5; list-style-type: circle;">
                        <li>配置文件(config.ini)自动保存在程序目录</li>
                        <li>日志文件(app.log)自动轮转，最大5MB保留3个</li>
                    </ul>
                </li>
            </ul>
            
            <div style="margin-top: 20px; text-align: center; font-size: 0.9em; color: {theme['text']}; opacity: 0.8;">
                <p>© 2025 IPTV Scanner Editor Pro 版权所有</p>
                <p>
                    <a href="https://github.com/sumingyd/IPTV-Scanner-Editor-Pro" 
                       style="color: {self.ACCENT_COLOR}; text-decoration: none;">GitHub 仓库</a> 
                    | <a href="javascript:void(0)" style="color: {self.ACCENT_COLOR}; text-decoration: none;" 
                       onclick="window.pywebview.api.handle_update_click()">在线更新</a>
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
            original_html = self._get_about_html(self.DARK_THEME if self.palette().window().color().lightness() < 128 else self.LIGHT_THEME)
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
            latest_version, publish_date, _ = loop.run_until_complete(
                asyncio.wait_for(self._get_latest_version(), timeout=5)
            )
            if latest_version and latest_version not in ("请求超时", "获取失败"):
                self._update_version_text(text_browser, version=latest_version)
            else:
                self._show_version_error(latest_version)
        except asyncio.TimeoutError:
            self._show_version_error("(请求超时)")
        except Exception as e:
            self._show_version_error("(获取失败)")
        finally:
            loop.close()

    def _update_version_text(self, text_browser, version=None, date=None, error_msg=None):
        """更新版本号文本"""
        if text_browser:
            # 获取当前HTML
            current_html = text_browser.toHtml()
            
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
        if link == "javascript:void(0)":
            try:
                # 确保有事件循环
                loop = asyncio.get_event_loop()
                if loop.is_closed():
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                
                # 显示点击反馈
                QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WaitCursor)
                QtWidgets.QApplication.processEvents()
                
                # 启动更新任务
                task = loop.create_task(self._perform_online_update())
                loop.run_until_complete(task)
                
            except Exception as e:
                logger.error(f"关于对话框-更新按钮点击处理失败: {str(e)}", exc_info=True)
                QtWidgets.QMessageBox.critical(
                    self,
                    "更新错误",
                    f"无法启动更新流程: {str(e)}"
                )
            finally:
                QtWidgets.QApplication.restoreOverrideCursor()
                QtWidgets.QApplication.processEvents()
                
        elif link.toString().startswith("http"):
            QtGui.QDesktopServices.openUrl(QtCore.QUrl(link))

    async def _perform_online_update(self):
        """执行在线更新"""
        max_retries = 3
        retry_delay = 1  # 秒
        
        progress = QtWidgets.QProgressDialog("正在检查更新...", "取消", 0, 0, self)
        progress.setWindowTitle("在线更新")
        progress.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        progress.setCancelButton(None)
        progress.setMinimumDuration(0)
        progress.show()
        QtWidgets.QApplication.processEvents()

        for attempt in range(max_retries):
            try:
                # 1. 获取最新版本信息
                progress.setLabelText(f"正在获取版本信息(第{attempt+1}次尝试)...")
                version, date, download_url = await self._get_latest_version()
                
                if not download_url:
                    raise Exception("未找到下载链接")
                    
                # 2. 下载更新包
                progress.setLabelText(f"正在下载更新(第{attempt+1}次尝试)...")
                progress.setRange(0, 0)  # 不确定进度模式
                
                # 设置下载超时和重试
                timeout = aiohttp.ClientTimeout(total=30)
                connector = aiohttp.TCPConnector(force_close=True)
                
                async with aiohttp.ClientSession(
                    timeout=timeout,
                    connector=connector,
                    headers={'User-Agent': 'IPTV-Scanner-Editor-Pro'}
                ) as session:
                    try:
                        async with session.get(download_url) as response:
                            if response.status != 200:
                                raise Exception(f"下载失败: HTTP {response.status}")
                                
                            # 获取文件大小用于进度显示
                            file_size = int(response.headers.get('Content-Length', 0))
                            progress.setRange(0, file_size)
                            progress.setValue(0)
                            
                            # 3. 保存更新文件(包含版本号)
                            update_file = f"IPTV-Scanner-Editor-Pro-{version}.exe"
                            with open(update_file, "wb") as f:
                                downloaded = 0
                                async for chunk in response.content.iter_chunked(8192):
                                    f.write(chunk)
                                    downloaded += len(chunk)
                                    progress.setValue(downloaded)
                                    QtWidgets.QApplication.processEvents()
                                    
                        # 4. 提示用户重启应用完成更新
                        progress.setLabelText("更新下载完成，请重启应用")
                        QtWidgets.QMessageBox.information(
                            self, 
                            "更新完成",
                            f"已下载版本 {version} 的更新包，请重启应用完成更新"
                        )
                        return  # 成功完成，退出循环
                        
                    except aiohttp.ClientError as e:
                        logger.error(f"关于对话框-下载失败(第{attempt+1}次): {str(e)}")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(retry_delay * (attempt + 1))
                            continue
                        raise
                        
            except Exception as e:
                logger.error(f"关于对话框-在线更新失败(第{attempt+1}次): {str(e)}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (attempt + 1))
                    continue
                    
                QtWidgets.QMessageBox.critical(
                    self,
                    "更新失败",
                    f"在线更新失败: {str(e)}\n\n请检查网络连接或稍后再试。"
                )
                break
                
        progress.close()
            
    async def _check_update(self):
        """手动检查更新"""
        progress = QtWidgets.QProgressDialog("正在检查更新...", "取消", 0, 0, self)
        progress.setWindowTitle("检查更新")
        progress.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        progress.setCancelButton(None)
        progress.setMinimumDuration(0)
        progress.show()
        QtWidgets.QApplication.processEvents()
        
        try:
            await asyncio.sleep(0.5)
            latest_version, publish_date = await self._get_latest_version()
            text_label = self.findChild(QtWidgets.QLabel, "aboutTextLabel")
            self._update_version_text(text_label, version=latest_version, date=publish_date)
        except Exception as e:
            logger.error(f"手动检查更新失败: {str(e)}")
            self._show_version_error("(检查失败)")
        finally:
            progress.close()

    async def _get_latest_version(self):
        """从GitHub获取最新版本信息"""
        max_retries = 3
        retry_delay = 1  # 秒
        
        for attempt in range(max_retries):
            try:
                url = "https://api.github.com/repos/sumingyd/IPTV-Scanner-Editor-Pro/releases/latest"
                
                # 设置超时和代理
                timeout = aiohttp.ClientTimeout(total=15)
                connector = aiohttp.TCPConnector(force_close=True)
                
                # 添加User-Agent和Accept头
                headers = {
                    'User-Agent': 'IPTV-Scanner-Editor-Pro',
                    'Accept': 'application/vnd.github.v3+json'
                }
                
                async with aiohttp.ClientSession(
                    timeout=timeout,
                    connector=connector,
                    headers=headers
                ) as session:
                    try:
                        async with session.get(url) as response:
                            if response.status == 200:
                                data = await response.json()
                                version = data.get('tag_name', '').lstrip('v')
                                publish_date = data.get('published_at', '').split('T')[0]
                                download_url = data.get('assets', [{}])[0].get('browser_download_url', '')
                                if version and publish_date:
                                    self.DEFAULT_VERSION = version
                                    return (version, publish_date, download_url)
                            elif response.status == 403:
                                # GitHub API限制
                                reset_time = response.headers.get('X-RateLimit-Reset')
                                if reset_time:
                                    reset_time = datetime.datetime.fromtimestamp(int(reset_time))
                                    return (f"API限制(重置时间: {reset_time})", 
                                            datetime.date.today().strftime("%Y-%m-%d"), "")
                                return ("API请求受限", datetime.date.today().strftime("%Y-%m-%d"), "")
                            raise Exception(f"HTTP状态码: {response.status}")
                    except aiohttp.ClientError as e:
                        logger.error(f"网络请求错误: {str(e)}")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(retry_delay * (attempt + 1))
                            continue
                        raise
            except asyncio.TimeoutError:
                logger.error("获取最新版本超时")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (attempt + 1))
                    continue
                return ("请求超时", datetime.date.today().strftime("%Y-%m-%d"), "")
            except Exception as e:
                logger.error(f"关于对话框-获取版本失败: {str(e)}", exc_info=True)
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (attempt + 1))
                    continue
                return ("获取失败", datetime.date.today().strftime("%Y-%m-%d"), "")
        
        return ("网络错误", datetime.date.today().strftime("%Y-%m-%d"), "")
