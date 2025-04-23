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
    CURRENT_VERSION = "6.0.0.0"  # 当前版本号(手动修改这里)
    DEFAULT_VERSION = None  # 将从GitHub获取最新版本
    BUILD_DATE = "2025-04-22"  # 更新为当前日期
    
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

        text_label = QtWidgets.QLabel()
        text_label.setObjectName("aboutTextLabel")
        text_label.setTextFormat(Qt.TextFormat.RichText)
        text_label.setText(self._get_about_html(theme))
        text_label.setWordWrap(True)
        text_label.setOpenExternalLinks(True)

        close_btn = QtWidgets.QPushButton("关闭")
        close_btn.clicked.connect(self.close)

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(text_label)
        layout.addWidget(close_btn, 0, Qt.AlignmentFlag.AlignCenter)
        
        self.setLayout(layout)
        self.setMinimumWidth(500)
        self.setMinimumHeight(580)
        text_label.linkActivated.connect(self._on_link_activated)
        
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
                IPTV Scanner Editor Pro New / IPTV 专业扫描编辑工具(新版)
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
                <li><b>EPG管理</b>：
                    <ul style="margin-left: 15px; line-height: 1.5; list-style-type: circle;">
                        <li>支持从多个源下载EPG数据，自动处理编码问题</li>
                        <li>智能合并处理重复节目信息，保留不重复的节目名称</li>
                        <li>提供节目查询和模糊匹配功能，支持频道名称模糊搜索</li>
                        <li>加载后可在频道编辑中匹配频道名，用于编辑频道名</li>
                        <li>按住Shift点击刷新可强制更新EPG数据(忽略本地缓存)</li>
                        <li>支持EPG数据本地缓存(epg.xml)</li>
                        <li>自动处理XML格式错误和编码问题，确保数据可用性</li>
                    </ul>
                </li>
                <li><b>频道扫描</b>：
                    <ul style="margin-left: 15px; line-height: 1.5; list-style-type: circle;">
                        <li>多线程扫描URL范围(如239.1.1.[1-255]:5002)</li>
                        <li>自动检测频道有效性，返回延迟和分辨率信息</li>
                        <li>实时显示扫描进度和统计信息</li>
                        <li>支持自定义扫描超时时间和线程数</li>
                        <li>扫描过程中可随时暂停/停止</li>
                        <li>自动过滤无效频道，只保留有效结果</li>
                    </ul>
                </li>
                <li><b>频道管理</b>：
                    <ul style="margin-left: 15px; line-height: 1.5; list-style-type: circle;">
                        <li>支持频道分组管理，自定义分组名称</li>
                        <li>批量检测频道有效性(延迟、分辨率)</li>
                        <li>支持拖拽调整频道顺序</li>
                    </ul>
                </li>
                <li><b>频道编辑</b>：
                    <ul style="margin-left: 15px; line-height: 1.5; list-style-type: circle;">
                        <li>修改频道基本信息(名称、分组)</li>
                        <li>支持批量导入/导出频道数据(M3U/TXT格式)</li>
                        <li>快捷键支持(Enter保存修改并编辑下一个频道)</li>
                    </ul>
                </li>
                <li><b>播放控制</b>：
                    <ul style="margin-left: 15px; line-height: 1.5; list-style-type: circle;">
                        <li>基于VLC的高性能播放引擎，支持硬件加速</li>
                        <li>音量控制(0-100)和静音功能</li>
                        <li>暂停/继续播放控制</li>
                    </ul>
                </li>
                <li><b>配置管理</b>：
                    <ul style="margin-left: 15px; line-height: 1.5; list-style-type: circle;">
                        <li>自动保存窗口布局、大小和分割位置</li>
                        <li>网络设置保存(超时、线程数、User-Agent等)</li>
                        <li>EPG配置保存(源地址、合并选项等)</li>
                        <li>配置文件(config.ini)自动保存在程序目录</li>
                        <li>日志文件(app.log)自动轮转，最大5MB保留3个</li>
                    </ul>
                </li>
                <li><b>操作方式</b>：
                    <ul style="margin-left: 15px; line-height: 1.5; list-style-type: circle;">
                        <li>Shift+点击刷新: 强制更新EPG数据</li>
                        <li>双击频道: 立即播放</li>
                        <li>Enter键: 确认编辑并进行下一个频道的编辑</li>
                        <li>Esc键: 取消操作/关闭窗口</li>
                        <li>拖拽: 调整频道顺序/分组</li>
                    </ul>
                </li>
            </ul>
            
            <div style="margin-top: 20px; text-align: center; font-size: 0.9em; color: {theme['text']}; opacity: 0.8;">
                <p>© 2025 IPTV Scanner Editor Pro New 版权所有</p>
                <p>
                    <a href="https://github.com/sumingyd/IPTV-Scanner-Editor-Pro" 
                       style="color: {self.ACCENT_COLOR}; text-decoration: none;">GitHub 仓库</a> 
                    | <a href="javascript:void(0)" style="color: {self.ACCENT_COLOR}; text-decoration: none;" id="checkUpdate">在线更新</a>
                </p>
                <p style="font-size: 0.8em; margin-top: 10px;">
                    系统信息: Python {sys.version.split()[0]}, {platform.system()} {platform.release()}
                </p>
            </div>
        </div>
        '''

    def show(self):
        """显示对话框并异步更新最新版本号"""
        logger.info("显示关于对话框，开始版本检测流程")
        super().show()
        text_label = self.findChild(QtWidgets.QLabel, "aboutTextLabel")
        if not text_label:
            logger.error("未找到关于文本标签")
            return
            
        logger.debug("设置初始版本文本为'检测中...'")
        self._update_version_text(text_label, version="检测中...")
        
        # 使用QTimer延迟执行版本检查，避免阻塞UI
        logger.info("启动版本检测定时器，100ms后执行")
        QtCore.QTimer.singleShot(100, lambda: (
            logger.debug("定时器触发，开始版本检测"),
            self._check_version_async(text_label)
        ))
        
    def _check_version_async(self, text_label):
        """异步检查版本"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            latest_version, publish_date, _ = loop.run_until_complete(
                asyncio.wait_for(self._get_latest_version(), timeout=5)
            )
            if latest_version and latest_version not in ("请求超时", "获取失败"):
                self._update_version_text(text_label, version=latest_version, date=publish_date)
            else:
                self._show_version_error(latest_version)
        except asyncio.TimeoutError:
            logger.error("获取最新版本超时")
            self._show_version_error("(请求超时)")
        except Exception as e:
            logger.error(f"获取最新版本失败: {str(e)}")
            self._show_version_error("(获取失败)")
        finally:
            loop.close()

    def _update_version_text(self, text_label, version=None, date=None, error_msg=None):
        """更新版本号文本"""
        if text_label:
            current_text = text_label.text()
            import re
            if version is not None:
                current_text = re.sub(
                    r'(最新版本：</b>\s*)([^<]+)', 
                    f'\\g<1>{version}', 
                    current_text
                )
            if error_msg is not None:
                current_text = re.sub(
                    r'(最新版本：</b>\s*)([^<]+)', 
                    f'\\g<1>{error_msg}', 
                    current_text
                )
            text_label.setText(current_text)

    def _show_version_error(self, error_msg):
        """显示版本获取错误信息"""
        text_label = self.findChild(QtWidgets.QLabel, "aboutTextLabel")
        self._update_version_text(text_label, error_msg=error_msg)

    def _on_link_activated(self, link):
        """处理链接点击事件"""
        if link == "javascript:void(0)":
            logger.info("在线更新按钮被点击")
            loop = asyncio.get_event_loop()
            task = loop.create_task(self._perform_online_update())
            QtWidgets.QApplication.processEvents()
            loop.run_until_complete(task)
        elif link.startswith("http"):
            QtGui.QDesktopServices.openUrl(QtCore.QUrl(link))

    async def _perform_online_update(self):
        """执行在线更新"""
        progress = QtWidgets.QProgressDialog("正在检查更新...", "取消", 0, 0, self)
        progress.setWindowTitle("在线更新")
        progress.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        progress.setCancelButton(None)
        progress.setMinimumDuration(0)
        progress.show()
        QtWidgets.QApplication.processEvents()

        try:
            # 1. 获取最新版本信息
            progress.setLabelText("正在获取版本信息...")
            version, date, download_url = await self._get_latest_version()
            
            if not download_url:
                raise Exception("未找到下载链接")
                
            # 2. 下载更新包
            progress.setLabelText("正在下载更新...")
            async with aiohttp.ClientSession() as session:
                async with session.get(download_url) as response:
                    if response.status != 200:
                        raise Exception(f"下载失败: HTTP {response.status}")
                        
                    # 3. 保存更新文件
                    update_file = "update.zip"
                    with open(update_file, "wb") as f:
                        while True:
                            chunk = await response.content.read(1024)
                            if not chunk:
                                break
                            f.write(chunk)
                            
            # 4. 提示用户重启应用完成更新
            progress.setLabelText("更新下载完成，请重启应用")
            QtWidgets.QMessageBox.information(
                self, 
                "更新完成",
                f"已下载版本 {version} 的更新包，请重启应用完成更新"
            )
            
        except Exception as e:
            logger.error(f"在线更新失败: {str(e)}")
            QtWidgets.QMessageBox.critical(
                self,
                "更新失败",
                f"在线更新失败: {str(e)}"
            )
        finally:
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
        try:
            url = "https://api.github.com/repos/sumingyd/IPTV-Scanner-Editor-Pro/releases/latest"
            logger.info(f"从GitHub获取最新版本: {url}")
            
            # 设置更长的超时时间
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    logger.info(f"GitHub API响应状态: {response.status}")
                    if response.status == 200:
                        data = await response.json()
                        logger.debug(f"GitHub API响应数据: {data}")
                        version = data.get('tag_name', '').lstrip('v')
                        publish_date = data.get('published_at', '').split('T')[0]
                        download_url = data.get('assets', [{}])[0].get('browser_download_url', '')
                        if version and publish_date:
                            logger.info(f"获取到最新版本: {version}, 发布时间: {publish_date}")
                            self.DEFAULT_VERSION = version
                            return (version, publish_date, download_url)
                    raise Exception(f"HTTP状态码: {response.status}")
        except asyncio.TimeoutError:
            logger.error("获取最新版本超时")
            return ("请求超时", datetime.date.today().strftime("%Y-%m-%d"), "")
        except Exception as e:
            logger.error(f"获取版本失败: {str(e)}", exc_info=True)
            return ("获取失败", datetime.date.today().strftime("%Y-%m-%d"), "")
