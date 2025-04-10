from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtCore import Qt
import asyncio
import datetime
import platform
import sys

import aiohttp

from logger_utils import setup_logger
logger = setup_logger(__name__)

class AboutDialog(QtWidgets.QDialog):
    DEFAULT_VERSION = None  # 将从GitHub获取最新版本
    BUILD_DATE = "2025-04-10"  # 固定的构建日期
    
    def __init__(self, parent=None, current_version="4.0.0.0"):
        super().__init__(parent)
        self.current_version = current_version  # 手动设置的当前版本
        self.setWindowTitle("关于")
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
        # 检测系统主题
        theme = self.DARK_THEME if self.palette().window().color().lightness() < 128 else self.LIGHT_THEME

        # 创建内容
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
        
        # 设置检查更新按钮点击事件
        text_label.linkActivated.connect(self._on_link_activated)
        
        # 设置自适应样式
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
                功能特性
            </h3>
            <ul style="margin-left: 20px; line-height: 1.6; padding-left: 5px;">
                <li>支持 HTTP/UDP/RTP/RTSP 协议检测</li>
                <li>EPG 信息保存与加载</li>
                <li>多线程高效扫描引擎</li>
                <li>支持 M3U/M3U8/TXT 播放列表格式</li>
                <li>实时流媒体可用性检测</li>
            </ul>
            
            <h3 style="color: {self.ACCENT_COLOR}; border-bottom: 1px solid {theme['border']}; 
                padding-bottom: 5px; font-size: 15px; margin-top: 15px;">
                快捷键
            </h3>
            <ul style="margin-left: 20px; line-height: 1.6; padding-left: 5px;">
                <li><code style="background-color: {theme['code_bg']}; color: {theme['code_text']}; 
                    padding: 2px 5px; border-radius: 3px;">Ctrl+O</code> - 打开播放列表</li>
                <li><code style="background-color: {theme['code_bg']}; color: {theme['code_text']};
                    padding: 2px 5px; border-radius: 3px;">Ctrl+S</code> - 保存播放列表</li>
                <li><code style="background-color: {theme['code_bg']}; color: {theme['code_text']};
                    padding: 2px 5px; border-radius: 3px;">空格键</code> - 暂停/继续播放</li>
            </ul>
            
            <div style="margin-top: 20px; text-align: center; font-size: 0.9em; color: {theme['text']}; opacity: 0.8;">
                <p>© 2025 IPTV Scanner Editor Pro 版权所有</p>
                <p>DeepSeek 提供技术支持</p>
                <p>
                    <a href="https://github.com/sumingyd/IPTV-Scanner-Editor-Pro" 
                       style="color: {self.ACCENT_COLOR}; text-decoration: none;">GitHub 仓库</a> 
                    | <span>作者QQ: 331874545</span>
                    | <a href="javascript:void(0)" style="color: {self.ACCENT_COLOR}; text-decoration: none;" id="checkUpdate">检查更新</a>
                </p>
                <p style="font-size: 0.8em; margin-top: 10px;">
                    系统信息: Python {sys.version.split()[0]}, {platform.system()} {platform.release()}
                </p>
            </div>
        </div>
        '''

    async def show(self):
        """显示对话框并异步更新最新版本号和编译日期"""
        super().show()  # 先显示对话框
        text_label = self.findChild(QtWidgets.QLabel, "aboutTextLabel")
        
        try:
            latest_version, publish_date = await asyncio.wait_for(self._get_latest_version(), timeout=5)
            self._update_version_text(text_label, version=latest_version, date=publish_date)
        except asyncio.TimeoutError:
            logger.error("获取最新版本超时")
            self._show_version_error("(请求超时)")
        except Exception as e:
            logger.error(f"获取最新版本失败: {str(e)}", exc_info=True)
            self._show_version_error("(获取失败)")

    def _update_version_text(self, text_label, version=None, date=None, error_msg=None):
        """更新版本号文本的公共方法"""
        if text_label:
            current_text = text_label.text()
            import re
            if version is not None:
                current_text = re.sub(
                    r'(最新版本：</b>\s*)([^<]+)', 
                    f'\\g<1>{version}', 
                    current_text
                )
            if date is not None:
                current_text = re.sub(
                    r'(编译日期：</b>\s*)([^<]+)',
                    f'\\g<1>{date}',
                    current_text
                )
            if error_msg is not None:
                current_text = re.sub(
                    r'(最新版本：</b>\s*)([^<]+)', 
                    f'\\g<1>{error_msg}', 
                    current_text
                )
                current_text = re.sub(
                    r'(编译日期：</b>\s*)([^<]+)',
                    f'\\g<1>{datetime.date.today().strftime("%Y-%m-%d")}',
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
            logger.info("检查更新按钮被点击")
            # 确保在主线程中创建异步任务
            loop = asyncio.get_event_loop()
            task = loop.create_task(self._check_update())
            # 强制处理Qt事件队列
            QtWidgets.QApplication.processEvents()
            logger.info(f"已创建检查更新任务: {task}")
            # 确保任务完成
            loop.run_until_complete(task)
        elif link.startswith("http"):
            QtGui.QDesktopServices.openUrl(QtCore.QUrl(link))
            
    async def _check_update(self):
        """手动检查更新"""
        # 创建加载对话框
        progress = QtWidgets.QProgressDialog("正在检查更新...", "取消", 0, 0, self)
        progress.setWindowTitle("检查更新")
        progress.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        progress.setCancelButton(None)  # 禁用取消按钮
        progress.setMinimumDuration(0)  # 立即显示
        progress.show()
        
        # 强制处理事件队列，确保对话框显示
        QtWidgets.QApplication.processEvents()
        
        try:
            # 添加人工延迟让用户能看到加载动画
            await asyncio.sleep(0.5)
            latest_version, publish_date = await self._get_latest_version()
            text_label = self.findChild(QtWidgets.QLabel, "aboutTextLabel")
            self._update_version_text(text_label, version=latest_version, date=publish_date)
        except Exception as e:
            logger.error(f"手动检查更新失败: {str(e)}", exc_info=True)
            self._show_version_error("(检查失败)")
        finally:
            progress.close()

    async def _get_latest_version(self):
        """从GitHub获取最新版本信息"""
        try:
            url = "https://api.github.com/repos/sumingyd/IPTV-Scanner-Editor-Pro/releases/latest"
            logger.info(f"开始从GitHub获取最新版本信息: {url}")
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        version = data.get('tag_name', '').lstrip('v')
                        publish_date = data.get('published_at', '')
                        
                        if version and publish_date:
                            publish_date = publish_date.split('T')[0]
                            logger.info(f"成功获取版本信息: {version}, 发布时间: {publish_date}")
                            self.DEFAULT_VERSION = version  # 更新DEFAULT_VERSION
                            return (version, publish_date)
                    error_msg = f"获取版本信息失败，HTTP状态码: {response.status}"
                    logger.error(error_msg)
                    raise Exception(error_msg)
        except Exception as e:
            logger.error(f"获取版本信息失败: {str(e)}", exc_info=True)
            return ("获取失败", datetime.date.today().strftime("%Y-%m-%d"))

    async def _check_for_updates(self):
        """检查并处理自动更新"""
        version, date = await self._get_latest_version()
        current_version = self.current_version
        
        # 将版本号转换为数字元组进行比较 (如 "2.0.0.0" -> (2, 0, 0, 0))
        def version_tuple(v):
            return tuple(map(int, v.split('.')))
            
        if version_tuple(version) > version_tuple(current_version):
            # 显示更新对话框
            msg = QtWidgets.QMessageBox(self)
            msg.setWindowTitle("发现新版本")
            msg.setText(f"发现新版本 {version} (当前版本 {current_version})")
            msg.setInformativeText("是否立即下载更新?")
            msg.setDetailedText(f"发布日期: {date}")
            msg.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Yes | 
                                 QtWidgets.QMessageBox.StandardButton.No)
            msg.setDefaultButton(QtWidgets.QMessageBox.StandardButton.Yes)
            
            if msg.exec() == QtWidgets.QMessageBox.StandardButton.Yes:
                # 下载更新
                progress = QtWidgets.QProgressDialog("正在下载更新...", "取消", 0, 0, self)
                progress.setWindowTitle("下载更新")
                progress.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
                progress.setCancelButton(None)
                progress.setMinimumDuration(0)
                progress.show()
                QtWidgets.QApplication.processEvents()
                
                try:
                    # 获取最新版本信息
                    latest_version, publish_date = await self._get_latest_version()
                    # 查找exe安装包
                    exe_asset = None
                    try:
                        url = "https://api.github.com/repos/sumingyd/IPTV-Scanner-Editor-Pro/releases/latest"
                        async with aiohttp.ClientSession() as session:
                            async with session.get(url) as response:
                                if response.status == 200:
                                    data = await response.json()
                                    exe_asset = next((a for a in data['assets'] 
                                                    if a['name'].endswith('.exe')), None)
                    except Exception as e:
                        logger.error(f"获取安装包信息失败: {str(e)}")
                        exe_asset = None
                    if exe_asset:
                        download_url = exe_asset['browser_download_url']
                        async with aiohttp.ClientSession() as session:
                            async with session.get(download_url) as resp:
                                if resp.status == 200:
                                    # 保存到临时文件
                                    import tempfile
                                    with tempfile.NamedTemporaryFile(
                                        suffix='.exe', delete=False) as tmp:
                                        tmp.write(await resp.read())
                                        tmp_path = tmp.name
                                        
                                    # 提示用户安装
                                    msg = QtWidgets.QMessageBox(self)
                                    msg.setWindowTitle("下载完成")
                                    msg.setText("更新已下载完成，是否立即安装?")
                                    msg.setStandardButtons(
                                        QtWidgets.QMessageBox.StandardButton.Yes | 
                                        QtWidgets.QMessageBox.StandardButton.No)
                                    msg.setDefaultButton(QtWidgets.QMessageBox.StandardButton.Yes)
                                    
                                    if msg.exec() == QtWidgets.QMessageBox.StandardButton.Yes:
                                        # 替换当前运行的exe文件
                                        import os
                                        import shutil
                                        current_exe = sys.executable
                                        backup_path = current_exe + ".bak"
                                        
                                        try:
                                            # 创建备份
                                            if os.path.exists(backup_path):
                                                os.remove(backup_path)
                                            shutil.copy2(current_exe, backup_path)
                                            
                                            # 替换文件
                                            shutil.copy2(tmp_path, current_exe)
                                            
                                            # 设置文件权限
                                            os.chmod(current_exe, os.stat(current_exe).st_mode)
                                            
                                            # 提示重启
                                            QtWidgets.QMessageBox.information(
                                                self, 
                                                "更新成功", 
                                                "更新已完成，请重新启动程序"
                                            )
                                            QtWidgets.QApplication.quit()
                                        except Exception as e:
                                            logger.error(f"更新失败: {str(e)}", exc_info=True)
                                            # 恢复备份
                                            if os.path.exists(backup_path):
                                                shutil.copy2(backup_path, current_exe)
                                            QtWidgets.QMessageBox.critical(
                                                self, 
                                                "更新失败", 
                                                f"更新过程中出错: {str(e)}\n已恢复原版本"
                                            )
                    else:
                        QtWidgets.QMessageBox.warning(
                            self, "更新失败", "未找到可用的安装包")
                except Exception as e:
                    logger.error(f"下载更新失败: {str(e)}", exc_info=True)
                    QtWidgets.QMessageBox.critical(
                        self, "更新失败", f"下载更新失败: {str(e)}")
                finally:
                    progress.close()
