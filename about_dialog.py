from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtCore import Qt
import aiohttp
import styles
import asyncio
import datetime
import logging
import platform
import sys

from logger_utils import setup_logger
logger = setup_logger(__name__)

class AboutDialog(QtWidgets.QDialog):
    DEFAULT_VERSION = "2.0.0.0"
    BUILD_DATE = "2025-04-10"  # 固定的构建日期
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("关于")
        self._init_ui()

    def _init_ui(self):
        """初始化UI组件"""
        # 检测系统主题
        is_dark = self.palette().window().color().lightness() < 128
        
        # 动态颜色设置
        bg_color = "#2d2d2d" if is_dark else "#ffffff"
        text_color = "#eeeeee" if is_dark else "#333333"
        accent_color = "#3498db"  # 主色调保持不变
        card_bg = "#3a3a3a" if is_dark else "#f8f9fa"
        border_color = "#444444" if is_dark else "#e0e0e0"
        code_bg = "#454545" if is_dark else "#f0f0f0"
        code_text = "#ffffff" if is_dark else "#333333"

        about_text = f'''
        <div style="font-family: 'Microsoft YaHei', sans-serif; color: {text_color};">
            <h1 style="color: {accent_color}; text-align: center; margin-bottom: 15px; font-size: 18px;">
                IPTV Scanner Editor Pro / IPTV 专业扫描编辑工具
            </h1>
            
            <div style="background-color: {card_bg}; padding: 15px; border-radius: 8px; 
                 margin-bottom: 15px; border: 1px solid {border_color};">
                <p style="line-height: 1.6; margin: 5px 0;">
                    <b>当前版本：</b> 5.0.0.0
                </p>
                <p style="line-height: 1.6; margin: 5px 0;">
                    <b>最新版本：</b> {self.DEFAULT_VERSION}
                </p>
                <p style="line-height: 1.6; margin: 5px 0;">
                    <b>编译日期：</b> {self.BUILD_DATE}
                </p>
                <p style="line-height: 1.6; margin: 5px 0;">
                    <b>QT版本：</b> {QtCore.qVersion()}
                </p>
            </div>
            
            <h3 style="color: {accent_color}; border-bottom: 1px solid {border_color}; 
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
            
            <h3 style="color: {accent_color}; border-bottom: 1px solid {border_color}; 
                padding-bottom: 5px; font-size: 15px; margin-top: 15px;">
                快捷键
            </h3>
            <ul style="margin-left: 20px; line-height: 1.6; padding-left: 5px;">
                <li><code style="background-color: {code_bg}; color: {code_text}; 
                    padding: 2px 5px; border-radius: 3px;">Ctrl+O</code> - 打开播放列表</li>
                <li><code style="background-color: {code_bg}; color: {code_text};
                    padding: 2px 5px; border-radius: 3px;">Ctrl+S</code> - 保存播放列表</li>
                <li><code style="background-color: {code_bg}; color: {code_text};
                    padding: 2px 5px; border-radius: 3px;">空格键</code> - 暂停/继续播放</li>
            </ul>
            
            <div style="margin-top: 20px; text-align: center; font-size: 0.9em; color: {text_color}; opacity: 0.8;">
                <p>© 2025 IPTV Scanner Editor Pro 版权所有</p>
                <p>DeepSeek 提供技术支持</p>
                <p>
                    <a href="https://github.com/sumingyd/IPTV-Scanner-Editor-Pro" 
                       style="color: {accent_color}; text-decoration: none;">GitHub 仓库</a> 
                    | <span>作者QQ: 331874545</span>
                    | <a href="#" style="color: {accent_color}; text-decoration: none;" id="checkUpdate">检查更新</a>
                </p>
                <p style="font-size: 0.8em; margin-top: 10px;">
                    系统信息: Python {sys.version.split()[0]}, {platform.system()} {platform.release()}
                </p>
            </div>
        </div>
        '''

        # 创建内容
        text_label = QtWidgets.QLabel()
        text_label.setObjectName("aboutTextLabel")  # 设置唯一标识
        text_label.setTextFormat(Qt.TextFormat.RichText)
        text_label.setText(about_text)
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
                background-color: {bg_color};
                color: {text_color};
            }}
            QPushButton {{
                background-color: {accent_color};
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

    async def show(self):
        """显示对话框并异步更新最新版本号和编译日期"""
        super().show()  # 先显示对话框
        
        try:
            latest_version, publish_date = await asyncio.wait_for(self._get_latest_version(), timeout=5)
            # 使用正则表达式更新版本号和编译日期
            text_label = self.findChild(QtWidgets.QLabel, "aboutTextLabel")
            if text_label:
                current_text = text_label.text()
                import re
                # 更新最新版本号
                updated_text = re.sub(
                    r'(最新版本：</b>\s*)([^<]+)', 
                    f'\\g<1>{latest_version}', 
                    current_text
                )
                # 更新编译日期
                updated_text = re.sub(
                    r'(编译日期：</b>\s*)([^<]+)',
                    f'\\g<1>{publish_date}',
                    updated_text
                )
                text_label.setText(updated_text)
        except asyncio.TimeoutError:
            logger.error("获取最新版本超时")
            self._show_version_error("(请求超时)")
        except Exception as e:
            logger.error(f"获取最新版本失败: {str(e)}", exc_info=True)
            self._show_version_error("(获取失败)")

    def _show_version_error(self, error_msg):
        """显示版本获取错误信息"""
        text_label = self.findChild(QtWidgets.QLabel, "aboutTextLabel")
        if text_label:
            current_text = text_label.text()
            import re
            # 更新版本号并添加错误信息
            updated_text = re.sub(
                r'(最新版本：</b>\s*)([^<]+)', 
                f'\\g<1>{self.DEFAULT_VERSION} {error_msg}', 
                current_text
            )
            # 更新编译日期为当前日期
            updated_text = re.sub(
                r'(编译日期：</b>\s*)([^<]+)',
                f'\\g<1>{datetime.date.today().strftime("%Y-%m-%d")}',
                updated_text
            )
            text_label.setText(updated_text)

    def _on_link_activated(self, link):
        """处理链接点击事件"""
        if link == "#checkUpdate":
            asyncio.create_task(self._check_update())
            
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
            if text_label:
                current_text = text_label.text()
                import re
                # 更新最新版本号
                updated_text = re.sub(
                    r'(最新版本：</b>\s*)([^<]+)', 
                    f'\\g<1>{latest_version}', 
                    current_text
                )
                # 更新编译日期
                updated_text = re.sub(
                    r'(编译日期：</b>\s*)([^<]+)',
                    f'\\g<1>{publish_date}',
                    updated_text
                )
                text_label.setText(updated_text)
        except Exception as e:
            logger.error(f"手动检查更新失败: {str(e)}", exc_info=True)
            self._show_version_error("(检查失败)")
        finally:
            progress.close()

    async def _get_release_info(self) -> dict:
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
                        body = data.get('body', '暂无更新日志')
                        
                        if version and publish_date:
                            publish_date = publish_date.split('T')[0]
                            logger.info(f"成功获取版本信息: {version}, 发布时间: {publish_date}")
                            return {
                                'version': version,
                                'date': publish_date,
                                'changelog': body,
                                'assets': data.get('assets', [])
                            }
                    error_msg = f"获取版本信息失败，HTTP状态码: {response.status}"
                    logger.error(error_msg)
                    raise Exception(error_msg)
        except Exception as e:
            logger.error(f"获取版本信息失败: {str(e)}", exc_info=True)
            return {
                'version': self.DEFAULT_VERSION,
                'date': datetime.date.today().strftime("%Y-%m-%d"),
                'changelog': '获取更新日志失败',
                'assets': []
            }

    async def _check_for_updates(self):
        """检查并处理自动更新"""
        release_info = await self._get_release_info()
        current_version = self.DEFAULT_VERSION
        
        if release_info['version'] > current_version:
            # 显示更新对话框
            msg = QtWidgets.QMessageBox(self)
            msg.setWindowTitle("发现新版本")
            msg.setText(f"发现新版本 {release_info['version']} (当前版本 {current_version})")
            msg.setInformativeText("是否立即下载更新?")
            msg.setDetailedText(f"更新日志:\n{release_info['changelog']}")
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
                    # 查找exe安装包
                    exe_asset = next((a for a in release_info['assets'] 
                                    if a['name'].endswith('.exe')), None)
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
