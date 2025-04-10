from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtCore import Qt
import aiohttp
import styles
import asyncio
import datetime
import logging

logger = logging.getLogger(__name__)

class AboutDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("关于")
        self._init_ui()

    async def show(self):
        """显示自动适应系统深浅色主题的关于对话框"""
        # 异步获取最新版本号
        try:
            latest_version = await asyncio.wait_for(self._get_latest_version(), timeout=5)
        except asyncio.TimeoutError:
            latest_version = "2.0.0.0"
            logger.warning("获取最新版本超时，使用默认版本号")
        
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
                    <b>最新版本：</b> {latest_version} 
                </p>
                <p style="line-height: 1.6; margin: 5px 0;">
                    <b>编译日期：</b> {datetime.date.today().strftime("%Y-%m-%d")}
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
                <p>   DeepSeek 贡献代码  </p>
                <p>
                    <a href="https://github.com/sumingyd/IPTV-Scanner-Editor-Pro" 
                       style="color: {accent_color}; text-decoration: none;">GitHub 仓库</a> 
                    | <span>作者QQ: 331874545</span>
                </p>
            </div>
        </div>
        '''

        # 创建内容
        text_label = QtWidgets.QLabel()
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
        self.setMinimumWidth(480)
        self.setMinimumHeight(550)
        
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
        super().show()

    async def _get_latest_version(self) -> str:
        """从GitHub获取最新版本号"""
        try:
            # GitHub API获取最新发布版本
            url = "https://api.github.com/repos/sumingyd/IPTV-Scanner-Editor-Pro/releases/latest"
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        version = data.get('tag_name', '').lstrip('v')
                        if version:  # 确保获取到的版本号不为空
                            return version
                    # 如果请求失败或版本号为空，则抛出异常
                    raise Exception(f"从GitHub获取最新版本失败，HTTP状态码: {response.status}")
        except Exception as e:
            logger.error(f"获取最新版本失败: {str(e)}")
            # 返回默认版本号
            return "2.0.0.0"
