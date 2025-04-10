# ================= 标准库导入 =================
from copy import deepcopy
import os
import asyncio
import datetime
import sys
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
import aiohttp

# ================= 第三方库导入 =================
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt, QModelIndex, pyqtSlot
from PyQt6.QtGui import QAction, QIcon, QKeySequence, QCloseEvent
from PyQt6.QtWidgets import QFileDialog, QMessageBox
import qasync

# ================= 本地模块导入 =================
from async_utils import AsyncWorker
from channel_model import ChannelListModel
from epg_manager import EPGManager
from player import VLCPlayer
from playlist_io import PlaylistConverter, PlaylistHandler, PlaylistParser
from scanner import StreamScanner
from logger_utils import setup_logger
from config_manager import ConfigHandler
from styles import AppStyles
import utils
from validator import StreamValidator
from ui_builder import UIBuilder
from signals import SignalConnector
from matcher import ChannelMatcher
from about_dialog import AboutDialog

logger = setup_logger('Main') # 主程序日志器

# 主窗口
class MainWindow(QtWidgets.QMainWindow):
    # 初始化
    def __init__(self):
        super().__init__()
        self.validation_results = {}  # 保存验证结果 {url: True/False}
        self.first_time_hide = True  # 首次点击隐藏按钮提示
        self.is_hiding_invalid = False  # 跟踪当前是否处于隐藏无效项状态
        self.config = ConfigHandler()
        self.scanner = StreamScanner()
        self.validator = StreamValidator()  # 新增验证器实例
        self.epg_manager = EPGManager(self.config)
        self.player = VLCPlayer()
        self.playlist_handler = PlaylistHandler()
        self.converter = PlaylistConverter(self.epg_manager)
        self.playlist_source = None  # 播放列表来源：None/file/scan
        # +++ 新增智能匹配相关变量 +++
        self.old_playlist = None  # 存储旧列表数据 {url: channel_info}
        self.match_worker = None  # 异步任务对象
        self._is_closing = False  # 关闭标志
        
        # 连接信号
        self.scanner.ffprobe_missing.connect(self.show_ffprobe_warning)
            
        # 异步任务跟踪
        self.scan_worker: Optional[AsyncWorker] = None
        self.play_worker: Optional[AsyncWorker] = None

        self._init_ui()
        self._connect_signals()
        self.load_config()

        # 添加防抖定时器
        self.debounce_timer = QtCore.QTimer()
        self.debounce_timer.setSingleShot(True)  # 单次触发
        self.debounce_timer.timeout.connect(lambda: self.epg_manager.update_epg_completer(self.name_edit.text()))

        # 连接信号与槽
        self.player.state_changed.connect(self._handle_player_state)
        self.name_edit.installEventFilter(self)

    # 显示ffprobe缺失警
    def show_ffprobe_warning(self):
        """显示ffprobe缺失警告"""
        QMessageBox.warning(
            self,
            "功能受限",
            "未检测到ffprobe，部分功能将受限：\n"
            "1. 无法检测视频分辨率/编码格式\n"
            "2. 仅能验证基本连接性\n\n"
            "请安装FFmpeg以获得完整功能\n"
            "下载地址: https://ffmpeg.org"
        )

    # 异步显示警告对话框
    async def _async_show_warning(self, title: str, message: str) -> None:
        """异步显示警告对话框"""
        await utils.async_show_warning(self, title, message)

    # 事件过滤器处理焦点事件（最终版）
    def eventFilter(self, source, event: QtCore.QEvent) -> bool:
        """事件过滤器处理焦点事件（最终版）"""
        if (source is self.name_edit and 
            event.type() == QtCore.QEvent.Type.FocusIn):
            self.epg_manager.update_epg_completer(self.name_edit.text())
        return super().eventFilter(source, event)

    # 初始化用户界面
    def _init_ui(self) -> None:
        """初始化用户界面"""
        self.ui_builder = UIBuilder(self)
        self.ui_builder.build_ui()

    # 初始化所有分隔条控件
    def _init_splitters(self):
        """初始化所有分隔条控件"""
        # 主水平分割器（左右布局）
        self.main_splitter = QtWidgets.QSplitter(Qt.Orientation.Horizontal)
        self.main_splitter.setChildrenCollapsible(False)  # 防止完全折叠

        # 左侧垂直分割器（扫描面板 + 频道列表）
        self.left_splitter = QtWidgets.QSplitter(Qt.Orientation.Vertical)
        self.left_splitter.setChildrenCollapsible(False)
        self._setup_scan_panel(self.left_splitter)
        self._setup_channel_list(self.left_splitter)

        # 右侧垂直分割器（播放器 + 底部编辑区）
        self.right_splitter = QtWidgets.QSplitter(Qt.Orientation.Vertical)
        self.right_splitter.setChildrenCollapsible(False)
        self._setup_player_panel(self.right_splitter)
        
        # 底部水平分割器（编辑面板 + 匹配面板）
        bottom_container = QtWidgets.QWidget()
        bottom_container.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding
        )
        bottom_layout = QtWidgets.QHBoxLayout(bottom_container)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        
        self.h_splitter = QtWidgets.QSplitter(Qt.Orientation.Horizontal)
        self.h_splitter.setChildrenCollapsible(False)
        self._setup_edit_panel(self.h_splitter)
        self._setup_match_panel(self.h_splitter)
        bottom_layout.addWidget(self.h_splitter)
        self.right_splitter.addWidget(bottom_container)

        # 统一设置分隔条样式
        style_map = {
            QtCore.Qt.Orientation.Vertical: AppStyles.splitter_handle_style("horizontal"),  # 垂直分隔条的把手是水平的
            QtCore.Qt.Orientation.Horizontal: AppStyles.splitter_handle_style("vertical")   # 水平分隔条的把手是垂直的
        }

        for splitter in [self.left_splitter, self.right_splitter, 
                        self.main_splitter, self.h_splitter]:
            # 设置最小尺寸防止拖拽过度
            splitter.setMinimumSize(100, 100)
            
            # 根据方向应用样式
            splitter.setStyleSheet(style_map[splitter.orientation()])
            
            # 设置拖动把手的热区大小（可选，推荐8-10px）
            splitter.setHandleWidth(8)

        # 组装主界面
        self.main_splitter.addWidget(self.left_splitter)
        self.main_splitter.addWidget(self.right_splitter)

        # 设置默认尺寸（如果load_config没有恢复保存的状态，会使用这些值）
        self.main_splitter.setSizes([300, 700])   # 左右比例 3:7
        self.left_splitter.setSizes([200, 400])   # 上下比例 1:2
        self.right_splitter.setSizes([400, 200])  # 播放器较大，编辑区较小
        self.h_splitter.setSizes([300, 300])      # 左右均分

    # 配置扫描面板
    def _setup_scan_panel(self, parent: QtWidgets.QSplitter) -> None:
        """配置扫描面板"""
        self.ui_builder.build_scan_panel(parent)

    # 配置频道列表
    def _setup_channel_list(self, parent: QtWidgets.QSplitter) -> None:  
        """配置频道列表"""
        self.ui_builder.build_channel_list(parent)

    # 配置播放器面板 (已迁移到ui_builder.py)
    def _setup_player_panel(self, parent: QtWidgets.QSplitter) -> None:  
        """配置播放器面板"""
        self.ui_builder._setup_player_panel(parent)

    # 配置编辑面板 (已迁移到ui_builder.py)
    def _setup_edit_panel(self, parent: QtWidgets.QSplitter) -> None:  
        """配置编辑面板"""
        self.ui_builder._setup_edit_panel(parent)

    # 初始化菜单栏 (已迁移到ui_builder.py)
    def _setup_menubar(self) -> None:  
        """初始化菜单栏"""
        pass

    # 初始化工具栏 (已迁移到ui_builder.py)
    def _setup_toolbar(self) -> None:  
        """初始化工具栏"""
        pass

    # 从GitHub获取最新版本号
    async def _get_latest_version(self) -> str:
        """从GitHub获取最新版本号"""
        return await utils.get_latest_version()

    # 带进度显示的EPG加载
    async def _load_epg_with_progress(self):
        """带进度显示的EPG加载"""
        await self.epg_manager.load_epg_with_progress(self)

    # 显示关于对话框
    async def _show_about_dialog(self):
        """显示关于对话框"""
        dialog = AboutDialog(self)
        await dialog.show()

    # 配置智能匹配功能区
    def _setup_match_panel(self, parent_layout):
        """添加智能匹配功能区（右侧新增区域）"""
        self.matcher = ChannelMatcher(self)
        self.matcher.setup_match_panel(parent_layout)

    # 连接信号与槽
    def _connect_signals(self) -> None:
        """连接信号与槽"""
        self.signals = SignalConnector(self)
        self.signals.connect_signals()

    # 统一处理播放状态更新
    def _handle_player_state(self, msg: str):  
        """统一处理播放状态更新"""
        self.statusBar().showMessage(msg)
        # 根据播放状态更新按钮文字
        if "播放中" in msg:
            self.pause_btn.setText("暂停")
        elif "暂停" in msg:
            self.pause_btn.setText("继续")
        else:  # 不在播放状态
            self.pause_btn.setText("播放")

    # 扫描控制切换
    @pyqtSlot()
    async def toggle_scan(self) -> None:
        """切换扫描状态"""
        await self.scanner.toggle_scan_ui(self)

    # 停止扫描任务
    @pyqtSlot()
    def stop_scan(self) -> None: 
        """停止扫描任务"""
        self.scanner.stop_scan_ui(self)

    # 执行异步扫描
    async def _async_scan(self, ip_range: str) -> None:  
        """执行异步扫描"""
        await self.scanner.async_scan_ui(self, ip_range)

    # 更新扫描进度
    @pyqtSlot(int, str)
    def update_progress(self, percent: int, msg: str) -> None: 
        """更新扫描进度"""
        self.scan_progress.setValue(percent)
        # 直接显示scanner.py传递的详细状态信息
        self.statusBar().showMessage(msg)
        # 标记当前处于扫描状态
        self._last_scan_status = msg

    #处理单个频道发现
    @pyqtSlot(dict)
    def handle_channel_found(self, channel: Dict) -> None: 
        """处理单个频道发现"""
        # 检查是否已存在相同URL的频道
        if not any(c['url'] == channel['url'] for c in self.model.channels):
            # 在主线程中执行UI更新
            QtCore.QMetaObject.invokeMethod(self, "_add_channel", 
                QtCore.Qt.ConnectionType.QueuedConnection,
                QtCore.Q_ARG(dict, channel))

    #实际添加频道的槽函数
    @pyqtSlot(dict)
    def _add_channel(self, channel: Dict) -> None: 
        """实际添加频道的槽函数"""
        self.model.beginInsertRows(QtCore.QModelIndex(),
                                 len(self.model.channels),
                                 len(self.model.channels))
        self.model.channels.append(channel)
        self.model.endInsertRows()
        # 强制刷新UI
        QtWidgets.QApplication.processEvents()

    # 处理扫描任务完成
    def _handle_scan_task(self, task: asyncio.Task) -> None:
        """处理扫描任务完成"""
        try:
            if task.done():
                if task.cancelled():
                    self.handle_cancel("scan")
                elif task.exception():
                    self.handle_error(task.exception(), "scan")
                else:
                    result = task.result()
                    self.handle_scan_results(result)
            else:
                logger.warning("Received incomplete scan task")
        except Exception as e:
            self.handle_error(e, "scan")

    # 处理最终扫描结果
    @pyqtSlot(dict)
    def handle_scan_results(self, result: Dict) -> None: 
        """处理最终扫描结果"""
        if result is None:
            self.show_error("扫描失败: 未返回有效结果")
            self.scan_btn.setText("完整扫描")
            self.scan_btn.setStyleSheet(AppStyles.button_style())
            self.statusBar().showMessage("扫描失败: 未返回有效结果")
            logger.error("扫描失败: 扫描器返回None结果")
            return
            
        channels = result['channels']
        total = result['total']
        invalid = result['invalid']
        elapsed = result['elapsed']
        # 更新统计信息显示
        self.detailed_stats_label.setText(f"总数: {total} | 有效: {len(channels)} | 无效: {invalid} | 耗时: {elapsed:.1f}s")
        self.statusBar().showMessage("扫描完成")
        
        # 恢复扫描按钮状态
        self.scan_btn.setText("完整扫描")
        self.scan_btn.setStyleSheet(AppStyles.button_style())
        
        # 自动选择第一个频道但不自动播放
        if channels:
            first_index = self.model.index(0, 0)
            self.channel_list.setCurrentIndex(first_index)
            # 手动触发状态更新
            self._handle_player_state("准备播放")

    # 处理频道选择事件
    @pyqtSlot()
    def on_channel_selected(self) -> None: 
        """处理频道选择事件"""
        index = self.channel_list.currentIndex()
        if not index.isValid():
            return

        chan = self.model.channels[index.row()]
        self.name_edit.setText(chan.get('name', '未命名频道'))
        self.group_combo.setCurrentText(chan.get('group', '未分类'))

        # 更新EPG匹配状态
        epg_status = self.epg_manager.get_channel_status(chan.get('name', ''))
        self.epg_match_label.setText(epg_status['message'])
        self.epg_match_label.setStyleSheet(f"color: {epg_status['color']}; font-weight: bold;")

        if url := chan.get('url'):
            asyncio.create_task(self.safe_play(url))

    # 安全播放包装器
    async def safe_play(self, url: str) -> None:
        """安全播放包装器"""
        await self.player.safe_play(url, self)
    # 安全停止包装器
    async def safe_stop(self) -> None:
        """安全停止包装器"""
        try:
            if hasattr(self, 'player') and self.player:
                await self.player.stop()
        except Exception as e:
            self.show_error(f"停止失败: {str(e)}")

    # 统一调用播放器的停止方法
    @qasync.asyncSlot()
    async def stop_play(self): 
        """统一调用播放器的停止方法"""
        await self.safe_stop()

    # 隐藏无效频道
    async def hide_invalid_channels(self):
        """切换隐藏/显示无效频道状态"""
        # 检查是否有正在进行的验证任务
        if hasattr(self, 'validator') and self.validator.is_running():
            msg_box = QMessageBox(self)
            msg_box.setIcon(QMessageBox.Icon.Warning)
            msg_box.setWindowTitle("提示")
            msg_box.setText("有效性检测正在进行中，请等待完成")
            msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg_box.exec()
            return
            
        if not hasattr(self, 'validation_results') or not self.validation_results:
            msg_box = QMessageBox(self)
            msg_box.setIcon(QMessageBox.Icon.Warning)
            msg_box.setWindowTitle("提示")
            msg_box.setText("请先点击[检测有效性]")
            msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg_box.exec()
            return

        if not hasattr(self, 'original_channels'):
            self.original_channels = deepcopy(self.model.channels)

        if self.is_hiding_invalid:
            # 恢复显示所有频道
            self.model.channels = self.original_channels
            self.model.layoutChanged.emit()
            self.channel_list.setCornerWidget(None)
            self.filter_status_label.setText("已恢复全部频道")
            self.btn_hide_invalid.setText("隐藏无效项")
            self.is_hiding_invalid = False
        else:
            # 隐藏无效频道
            # 首次点击提示
            if self.first_time_hide:
                await self._async_show_warning(
                    "提示",
                    "将隐藏所有检测为无效的频道\n"
                    "再次点击按钮可恢复显示"
                )
                self.first_time_hide = False

            # 过滤无效频道
            valid_channels = [
                chan for chan in self.model.channels 
                if self.validation_results.get(chan['url'], False)
            ]
            
            # 更新模型
            self.model.channels = valid_channels
            self.model.layoutChanged.emit()
            
            # 显示隐藏数量提示
            hidden_count = len(self.validation_results) - len(valid_channels)
            if hidden_count > 0:
                corner_label = QtWidgets.QLabel(f"已隐藏{hidden_count}项")
                corner_label.setStyleSheet("color: gray; font-size: 10px;")
                self.channel_list.setCornerWidget(corner_label)
            else:
                self.channel_list.setCornerWidget(None)
            self.filter_status_label.setText(f"显示中: {len(valid_channels)}项")
            self.btn_hide_invalid.setText("取消隐藏")
            self.is_hiding_invalid = True

    # 显示右键菜单
    def show_context_menu(self, pos):
        """显示右键菜单"""
        menu = QtWidgets.QMenu()
        
        # 根据当前状态显示不同的菜单项
        if self.is_hiding_invalid:
            menu.addAction(
                QIcon(":/icons/restore.svg"),  # 可替换为你的图标
                "恢复显示全部",
                lambda: asyncio.create_task(self.hide_invalid_channels())
            )
        menu.addAction("复制选中URL", self.copy_selected_url)
        menu.exec(self.channel_list.mapToGlobal(pos))

    # 恢复显示所有频道
    def restore_all_channels(self):
        """恢复显示所有频道（从原始数据重建模型）"""
        if hasattr(self, 'original_channels'):  # 需要先在hide时备份原始数据
            self.model.channels = self.original_channels
        self.model.layoutChanged.emit()
        self.channel_list.setCornerText("")
        self.filter_status_label.setText("已恢复全部频道")

    # 复制选中URL到剪贴板
    def copy_selected_url(self):
        """复制选中URL到剪贴板"""
        index = self.channel_list.currentIndex()
        if index.isValid():
            url = self.model.channels[index.row()].get('url', '')
            QtWidgets.QApplication.clipboard().setText(url)
            self.statusBar().showMessage("已复制URL", 2000)

    # 保存频道编辑
    @pyqtSlot()
    def save_channel_edit(self) -> None:
        """保存频道编辑"""
        index = self.channel_list.currentIndex()
        if not index.isValid():
            self.show_error("请先选择要编辑的频道")
            return

        new_name = self.name_edit.text().strip()
        new_group = self.group_combo.currentText()

        if not new_name:
            self.show_error("频道名称不能为空")
            return

        # 立即更新模型数据
        self.model.channels[index.row()].update({
            'name': new_name,
            'group': new_group
        })
        self.model.dataChanged.emit(index, index)
        
        # 自动保存配置
        self._save_config_sync()
        
        # 处理焦点和选择逻辑
        row_count = self.model.rowCount()
        if row_count > 1:
            # 多个频道时跳转到下一个
            next_row = index.row() + 1
            if next_row < row_count:
                next_index = self.model.index(next_row, 0)
                self.channel_list.setCurrentIndex(next_index)
            else:
                # 如果是最后一个频道，回到第一个
                next_index = self.model.index(0, 0)
                self.channel_list.setCurrentIndex(next_index)
            
            # 触发选中事件并确保编辑框获得焦点
            self.on_channel_selected()
        else:
            # 单个频道时保持当前选中状态
            self.channel_list.setCurrentIndex(index)
        
        # 自动选中编辑框中的文本
        self.name_edit.selectAll()
        # 确保焦点在编辑框
        self.name_edit.setFocus()
        # 强制立即处理事件队列
        QtWidgets.QApplication.processEvents()


    # 输入框文本变化处理
    def on_text_changed(self, text: str) -> None: 
        """输入框文本变化处理"""
        # 启动防抖定时器（后续输入防抖）
        self.debounce_timer.start(300)
        # 通过epg_manager更新自动补全
        self.epg_manager.update_epg_completer(text)

    # 打开播放列表文件
    @pyqtSlot()
    def open_playlist(self) -> None: 
        """打开播放列表文件"""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "打开播放列表",
            "",
            "播放列表文件 (*.m3u *.m3u8 *.txt)"
        )
        if not path:
            return

        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()

            if path.endswith('.txt'):
                channels = PlaylistParser.parse_txt(content)
            else:
                channels = PlaylistParser.parse_m3u(content)

            # 清空现有列表，而不是追加
            self.model.channels = channels
            self.model.layoutChanged.emit()
            self.statusBar().showMessage(f"已加载列表：{Path(path).name}")
            self.playlist_source = 'file'  # 设置播放列表来源为文件
        except Exception as e:
            self.show_error(f"打开文件失败: {str(e)}")
    
    # 保存播放列表文件
    @pyqtSlot()
    def save_playlist(self) -> None: 
        """保存播放列表文件"""
        path, _ = QFileDialog.getSaveFileName(
            self,
            "保存播放列表",
            "",
            "M3U播放列表 (*.m3u *.m3u8);;文本文件 (*.txt)"
        )
        if not path:
            return

        try:
            success = self.playlist_handler.save_playlist(self.model.channels, path)
            if success:
                self.statusBar().showMessage(f"列表已保存至：{path}")
            else:
                self.show_error("保存失败，请检查文件路径")
        except Exception as e:
            self.show_error(f"保存文件失败: {str(e)}")

    def showEvent(self, event):
        """窗口显示事件"""
        super().showEvent(event)

    # 处理关闭事件
    @pyqtSlot()
    def closeEvent(self, event: QCloseEvent):
        """处理窗口关闭事件"""
        try:
            # 1. 设置关闭标志
            self._is_closing = True
            
            # 2. 停止并清理验证器资源
            if hasattr(self, 'validator'):
                self.validator.cleanup()
            
            # 3. 同步保存当前配置
            self._save_config_sync()
            
            # 4. 检查是否需要保存播放列表
            if self.playlist_source == 'file' and self.model.channels:
                reply = QMessageBox.question(
                    self,
                    '保存修改',
                    '是否保存对播放列表的修改？',
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel
                )
                
                if reply == QMessageBox.StandardButton.Yes:
                    self.save_playlist()
                elif reply == QMessageBox.StandardButton.Cancel:
                    event.ignore()
                    return None  # 明确返回None
            
            # 5. 执行父类关闭事件
            super().closeEvent(event)
            
            # 7. 接受关闭事件
            event.accept()
            return None  # 明确返回None
            
        except Exception as e:
            logger.error(f"关闭异常: {str(e)}", exc_info=True)
            event.ignore()

    # 切换有效性检测状态
    async def toggle_validation(self):
        """切换有效性检测状态"""
        if self.validator.is_running():
            await self.validator.stop_validation()
            self.btn_validate.setText("检测有效性")
            self.btn_validate.setChecked(False)
            return

        urls = [chan['url'] for chan in self.model.channels if 'url' in chan]
        if not urls:
            self.show_error("没有可检测的频道")
            return
            
        self.btn_validate.setText("停止检测")
        self.btn_validate.setStyleSheet(AppStyles.button_style(active=True))
        self.btn_validate.setChecked(True)
        self.filter_status_label.setText("有效性检测中...")
        
        try:
            # 从UI获取并发数设置并传递给验证器
            max_workers = self.thread_count_input.value()
            result = await self.validator.validate_playlist(urls, max_workers)
            
            # 处理验证结果
            self.validation_results = {chan['url']: chan['valid'] for chan in result['valid'] + result['invalid']}
            self.filter_status_label.setText(f"检测完成 - 有效: {len(result['valid'])}/{len(urls)}")
            
        except Exception as e:
            self.show_error(f"有效性检测失败: {str(e)}")
            self.btn_validate.setText("检测有效性")
            self.btn_validate.setStyleSheet(AppStyles.button_style())
            self.btn_validate.setChecked(False)

    # 加载用户配置
    def load_config(self) -> None:
        """加载用户配置"""
        try:
            # 窗口布局
            if geometry := self.config.config.get('UserPrefs', 'window_geometry', fallback=''):
                self.restoreGeometry(QtCore.QByteArray.fromHex(geometry.encode()))

            # 恢复分隔条状态
            if 'Splitters' in self.config.config:
                try:
                    if left_sizes := self.config.config['Splitters'].get('left_splitter', ''):
                        self.left_splitter.setSizes(
                            [int(size) for size in left_sizes.split(',') if size]
                        )
                    
                    if right_sizes := self.config.config['Splitters'].get('right_splitter', ''):
                        self.right_splitter.setSizes(
                            [int(size) for size in right_sizes.split(',') if size]
                        )
                    
                    if main_sizes := self.config.config['Splitters'].get('main_splitter', ''):
                        self.main_splitter.setSizes(
                            [int(size) for size in main_sizes.split(',') if size]
                        )
                    
                    if h_sizes := self.config.config['Splitters'].get('h_splitter', ''):
                        self.h_splitter.setSizes(
                            [int(size) for size in h_sizes.split(',') if size]
                        )
                except Exception as e:
                    logger.warning(f"恢复分隔条状态失败: {e}")

            # 扫描历史
            scan_address = self.config.config.get('Scanner', 'scan_address', fallback='')
            timeout = self.config.config.getint('Scanner', 'timeout', fallback=10)
            thread_count = self.config.config.getint('Scanner', 'thread_count', fallback=10)
            user_agent = self.config.config.get('Scanner', 'user_agent', fallback='')
            referer = self.config.config.get('Scanner', 'referer', fallback='')
            
            logger.info(f"加载Scanner配置: address={scan_address}, timeout={timeout}, threads={thread_count}, user_agent={user_agent}, referer={referer}")
            
            self.ip_range_input.setText(scan_address)
            self.timeout_input.setValue(timeout)
            self.thread_count_input.setValue(thread_count)
            self.user_agent_input.setText(user_agent)
            self.referer_input.setText(referer)

            # 播放器设置
            hardware_accel = self.config.config.get('Player', 'hardware_accel', fallback='d3d11va')
            self.player.hw_accel = hardware_accel

        except Exception as e:
            logger.error(f"配置加载失败: {str(e)}")

    # 清理资源
    def _cleanup_resources(self) -> None:
        """清理资源"""
        asyncio.run(AsyncWorker.cancel_all())
        if hasattr(self, 'player'):
            self.player.force_stop()  # 使用force_stop确保同步释放资源

    # 同步保存配置
    def _save_config_sync(self) -> None:
        """同步保存配置"""
        try:
            # 保存窗口几何信息
            self.config.config['UserPrefs']['window_geometry'] = self.saveGeometry().toHex().data().decode()
            
            # 保存分隔条状态
            self.config.config['Splitters']['left_splitter'] = ','.join(map(str, self.left_splitter.sizes()))
            self.config.config['Splitters']['right_splitter'] = ','.join(map(str, self.right_splitter.sizes()))
            self.config.config['Splitters']['main_splitter'] = ','.join(map(str, self.main_splitter.sizes()))
            self.config.config['Splitters']['h_splitter'] = ','.join(map(str, self.h_splitter.sizes()))

            # 保存扫描配置
            self.config.config['Scanner']['scan_address'] = self.ip_range_input.text()
            self.config.config['Scanner']['timeout'] = str(self.timeout_input.value())
            self.config.config['Scanner']['thread_count'] = str(self.thread_count_input.value())
            self.config.config['Scanner']['user_agent'] = self.user_agent_input.text()
            self.config.config['Scanner']['referer'] = self.referer_input.text()
            
            # 保存播放器配置
            self.config.config['Player']['hardware_accel'] = self.player.hw_accel
            self.config.config['Player']['volume'] = str(self.volume_slider.value())
            
            # 保存EPG配置
            
            self.config.save_prefs()
            logger.debug("配置已保存")
        except Exception as e:
            logger.error(f"保存配置失败: {str(e)}", exc_info=True)

    # 显示错误对话框
    @pyqtSlot(str)
    def show_error(self, msg: str) -> None:
        """显示错误对话框"""
        QMessageBox.critical(self, "操作错误", msg)

    # 更新状态栏
    @pyqtSlot(str)
    def update_status(self, msg: str) -> None:
        """更新状态栏"""
        self.statusBar().showMessage(msg)

    # 统一处理成功结果
    @pyqtSlot(str)
    def handle_success(self, msg: str, action: str = "") -> None:
        """统一处理成功操作（支持多类型）"""
        status_map = {
            "scan": f"扫描完成 - {msg}",
            "play": "播放成功",
            "match": "智能匹配完成"
        }
        
        # 获取状态信息
        final_msg = status_map.get(action, "操作成功")
        
        # 更新状态栏
        self.statusBar().showMessage(final_msg)
        
        # 播放成功后额外操作
        if action == "play":
            self.pause_btn.setText("暂停")
            self._handle_player_state("播放中")
        
        # 扫描成功后自动保存配置（可选）
        if action == "scan":
            self._save_config_sync()

    # 统一处理错误"
    @pyqtSlot(Exception)
    def handle_error(self, error: Exception, action: str = "") -> None:
        """增强版错误处理（带错误类型识别）"""
        error_details = {
            TimeoutError: {
                "scan": "扫描超时，请检查网络或增加超时时间",
                "play": "播放超时，流媒体服务器无响应"
            },
            ConnectionError: {
                "scan": "无法连接到目标服务器",
                "play": "播放连接失败"
            },
            json.JSONDecodeError: {
                "epg": "EPG数据格式错误"
            }
        }
        
        # 获取基础错误信息
        default_msg = f"{action}错误: {str(error)}" if action else f"错误: {str(error)}"
        
        # 尝试获取详细错误提示
        error_type = type(error)
        detail = error_details.get(error_type, {}).get(action, default_msg)
        
        # 显示错误
        self.show_error(detail)
        
        # 特殊错误处理
        if error_type == TimeoutError and action == "scan":
            self.scan_btn.setText("重试扫描")

    # 统一处理取消
    @pyqtSlot(str)
    def handle_cancel(self, action: str = "") -> None:
        """统一处理取消操作"""
        status_map = {
            "scan": "扫描已取消",
            "play": "播放已取消",
            "validate": "验证已取消"
        }
        message = status_map.get(action, "操作已取消")
        self.statusBar().showMessage(message)
        # 恢复相关按钮状态
        if action == "scan":
            self.scan_btn.setText("完整扫描")
            self.scan_btn.setStyleSheet(AppStyles.button_style())

    # 设置音量
    def set_volume(self, volume: int) -> None:
        """设置音量"""
        self.player.set_volume(volume)

    # +++ 新增方法：加载旧列表 +++
    @pyqtSlot()
    def load_old_playlist(self):
        """加载旧播放列表文件"""
        path, _ = QFileDialog.getOpenFileName(
            self, "选择旧列表", "", "播放列表 (*.m3u *.m3u8 *.txt)"
        )
        if not path:
            return
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if path.endswith('.txt'):
                channels = PlaylistParser.parse_txt(content)
            else:
                channels = PlaylistParser.parse_m3u(content)
            
            # 转换为 {url: channel} 字典
            self.old_playlist = {chan['url']: chan for chan in channels}
            self.btn_match.setEnabled(True)
            self.match_status.setText(f"✔ 已加载旧列表({len(self.old_playlist)}个频道) - 点击'执行自动匹配'开始匹配")
            self.match_status.setStyleSheet("color: #4CAF50; font-weight: bold;")
        except Exception as e:
            self.show_error(f"加载旧列表失败: {str(e)}")

    # +++ 新增方法：执行自动匹配 +++
    async def run_auto_match(self):
        """执行自动匹配任务"""
        if not hasattr(self, 'old_playlist') or not self.old_playlist:
            self.match_status.setText("请先加载旧列表")
            return

        try:
            # 创建异步任务
            self.match_worker = AsyncWorker(self._async_auto_match())
            
            # 连接信号
            self.match_worker.error.connect(lambda error: self.handle_error(error, "match"))
            self.match_worker.finished.connect(lambda: self.handle_success("匹配完成", "match"))
            
            # 启动任务
            await self.match_worker.run()
            
        except asyncio.CancelledError:
            self.match_status.setText("匹配已取消")
        except Exception as e:
            logger.error(f"匹配任务异常: {str(e)}")
            self.match_status.setText("匹配启动失败")

    # 实际执行匹配的异步方法
    async def _async_auto_match(self):
        """实际执行匹配的异步方法"""
        total = len(self.model.channels)
        self.match_progress.setMaximum(total)
        
        for row in range(total):
            chan = self.model.channels[row]
            
            # 1. 匹配旧列表
            if chan['url'] in self.old_playlist:
                old_chan = self.old_playlist[chan['url']]
                self._apply_match(row, old_chan, 'old')
            
            # 2. 匹配EPG
            if hasattr(self, 'epg_manager'):
                epg_names = self.epg_manager.match_channel_name(chan.get('name', ''))
                if epg_names:
                    self.model.channels[row]['name'] = epg_names[0]
                    self._apply_match(row, {'name': epg_names[0]}, 'epg')
            
            # 更新进度
            self.match_progress.setValue(row + 1)
            self.match_status.setText(f"匹配中: {row+1}/{total} ({(row+1)/total*100:.1f}%)")
            await asyncio.sleep(0.01)  # 释放事件循环
        
        # 统计结果
        matched_count = sum(1 for chan in self.model.channels if 'old_name' in chan or 'epg_name' in chan)
        old_matched = sum(1 for chan in self.model.channels if 'old_name' in chan)
        epg_matched = sum(1 for chan in self.model.channels if 'epg_name' in chan)
        conflict_count = sum(1 for chan in self.model.channels 
                            if 'old_name' in chan and 'epg_name' in chan 
                            and chan['old_name'] != chan['epg_name'])
        
        stats = (f"✔ 匹配完成\n"
                f"• 共匹配 {matched_count}/{total} 个频道\n"
                f"• 旧列表匹配: {old_matched}\n"
                f"• EPG匹配: {epg_matched}\n"
                f"• 冲突: {conflict_count}")
        
        self.match_status.setText(stats)
        self.match_status.setStyleSheet("color: #2196F3; font-weight: bold;")
        
        if self.cb_auto_save.isChecked():
            self.save_playlist()

    # +++ 新增方法：应用匹配结果 +++
    def _apply_match(self, row, data, source):
        """更新指定行的数据和颜色"""
        index = self.model.index(row, 0)
        chan = self.model.channels[row]
        
        # 确定颜色
        if source == 'old':
            color = QtGui.QColor(255, 255, 200)  # 浅黄：旧列表匹配
            # 保留原始名称
            self.model.channels[row]['old_name'] = chan['name']
            # 更新名称
            self.model.channels[row]['name'] = data['name']
        else:
            is_conflict = ('old_name' in chan and data['name'] != chan['old_name'])
            color = QtGui.QColor(255, 200, 200) if is_conflict else QtGui.QColor(200, 255, 200)
            # 更新名称
            self.model.channels[row]['name'] = data['name']
        
        # 更新UI
        self.model.setData(index, data['name'], Qt.ItemDataRole.DisplayRole)
        self.model.setData(index, color, Qt.ItemDataRole.BackgroundRole)
        self.model.dataChanged.emit(index, index)

# 程序入口
if __name__ == "__main__":
    # 禁用QT屏幕相关的警告
    os.environ["QT_LOGGING_RULES"] = "qt.qpa.*=false"
    app = QtWidgets.QApplication(sys.argv)
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    main_window = MainWindow()
    main_window.show()

    with loop:
        sys.exit(loop.run_forever())
