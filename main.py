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
from signals import AppSignals

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
        logger.info("主窗口初始化开始")
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
        self.matcher = ChannelMatcher(self.epg_manager, self)  # 初始化匹配器
        self.playlist_source = None  # 播放列表来源：None/file/scan
        # +++ 新增智能匹配相关变量 +++
        self.old_playlist = None  # 存储旧列表数据 {url: channel_info}
        self.match_worker = None  # 异步任务对象
        self._is_closing = False  # 关闭标志
        
        # 初始化应用信号
        self.signals = AppSignals(self)  # 传入self作为parent
        
        # 连接信号
        self.scanner.ffprobe_missing.connect(self.show_ffprobe_warning)
            
        # 异步任务跟踪
        self.scan_worker: Optional[AsyncWorker] = None
        self.play_worker: Optional[AsyncWorker] = None

        self._init_ui()
        self._connect_signals()

        # 添加防抖定时器
        self.debounce_timer = QtCore.QTimer()
        self.debounce_timer.setSingleShot(True)  # 单次触发
        self.debounce_timer.timeout.connect(lambda: self.epg_manager.update_epg_completer(self.name_edit.text()))

        # 连接信号与槽
        self.signals.player_state_changed.connect(self._handle_player_state)
        self.name_edit.installEventFilter(self)

    # 显示ffprobe缺失警
    def show_ffprobe_warning(self):
        """显示ffprobe缺失警告"""
        logger.warning("检测到ffprobe缺失，部分功能将受限")
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
        logger.info(f"显示警告对话框 - {title}: {message}")
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

    # 连接信号与槽
    def _connect_signals(self) -> None:
        """连接信号与槽"""
        # 连接扫描器信号
        self.scanner.progress_updated.connect(
            lambda p, msg: (
                self.ui_builder.ui_manager.update_progress(self.scan_progress, p),
                self.ui_builder.ui_manager.update_status(msg)
            )
        )
        self.scanner.scan_finished.connect(self.handle_scan_results)
        self.scanner.channel_found.connect(self.handle_channel_found)
        self.scanner.error_occurred.connect(self.show_error)
        self.scanner.scan_stopped.connect(self._on_scan_stopped)
        self.scanner.scan_started.connect(
            lambda ip: (
                self.ui_builder.ui_manager.update_button_state(self.scan_btn, "停止扫描", True),
                self.ui_builder.ui_manager.update_status(f"开始扫描: {ip}")
            )
        )
        self.scanner.stats_updated.connect(
            lambda stats: self.ui_builder.ui_manager.update_status(stats)
        )

    # 统一处理播放状态更新
    def _handle_player_state(self, msg: str):  
        """统一处理播放状态更新"""
        self.ui_builder.ui_manager.update_player_state_ui(msg)

    # 扫描控制切换
    @pyqtSlot()
    async def toggle_scan(self) -> None:
        """切换扫描状态"""
        ip_range = self.ip_range_input.text()
        timeout = self.timeout_input.value()
        thread_count = self.thread_count_input.value()
        
        # 强制处理事件队列确保UI更新
        QtWidgets.QApplication.processEvents()
        # 立即执行扫描任务，传递超时和线程数参数
        task = await self.scanner.toggle_scan(
            ip_range,
            timeout=timeout,
            thread_count=thread_count
        )
        # 确保任务立即启动
        if task:
            await asyncio.sleep(0)  # 让出控制权确保任务启动


    # 更新扫描进度
    @pyqtSlot(int, str)
    def update_progress(self, percent: int, msg: str) -> None: 
        """更新扫描进度"""
        self.ui_builder.ui_manager.update_progress(percent)
        self.ui_builder.ui_manager.update_status(msg)
        # 标记当前处于扫描状态
        self._last_scan_status = msg

    #处理单个频道发现
    @pyqtSlot(dict)
    def handle_channel_found(self, channel: Dict) -> None: 
        """处理单个频道发现"""
        # 检查是否已存在相同URL的频道
        if not any(c['url'] == channel['url'] for c in self.model.channels):
            # 通过UIManager添加频道
            self.ui_builder.ui_manager.add_channel(channel)

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
            self.ui_builder.ui_manager.update_button_state("scan_btn", "完整扫描", False)
            self.ui_builder.ui_manager.update_status("扫描失败: 未返回有效结果")
            logger.error("扫描失败: 扫描器返回None结果")
            return
            
        # 通过UIManager更新UI
        self.ui_builder.ui_manager.update_scan_results_ui(result)
        
        # 标记播放列表来源为扫描
        self.playlist_source = 'scan'

    @pyqtSlot()
    def _on_scan_stopped(self) -> None:
        """处理扫描停止信号"""
        self.ui_builder.ui_manager.update_button_state(self.scan_btn, "完整扫描", False)
        self.ui_builder.ui_manager.update_status("扫描已停止")
        logger.info("扫描已停止")

    # 处理频道选择事件
    @pyqtSlot()
    def on_channel_selected(self) -> None: 
        """处理频道选择事件"""
        index = self.channel_list.currentIndex()
        if not index.isValid():
            return

        chan = self.model.channels[index.row()]
        self.ui_builder.ui_manager.update_channel_selection_ui(chan)

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
        self.ui_builder.ui_manager.update_text_input_ui(text)

    # 打开播放列表文件
    @pyqtSlot()
    def open_playlist(self) -> None: 
        """打开播放列表文件"""
        logger.info("开始打开播放列表文件")
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
            logger.info(f"成功加载播放列表: {Path(path).name}, 共{len(channels)}个频道")
            self.playlist_source = 'file'  # 设置播放列表来源为文件
        except Exception as e:
            logger.error(f"打开播放列表失败: {str(e)}", exc_info=True)
            self.show_error(f"打开文件失败: {str(e)}")
    
    # 保存播放列表文件
    @pyqtSlot()
    def save_playlist(self) -> None: 
        """保存播放列表文件"""
        logger.info("开始保存播放列表")
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
                logger.info(f"播放列表已保存至: {path}, 共{len(self.model.channels)}个频道")
            else:
                self.show_error("保存失败，请检查文件路径")
        except Exception as e:
            logger.error(f"保存播放列表失败: {str(e)}", exc_info=True)
            self.show_error(f"保存文件失败: {str(e)}")

    def showEvent(self, event):
        """窗口显示事件"""
        super().showEvent(event)
        # 窗口显示后加载配置
        self.load_config()

    # 处理关闭事件
    @qasync.asyncClose
    async def closeEvent(self, event: QCloseEvent):
        """处理窗口关闭事件"""
        logger.info("开始处理窗口关闭事件")
        self._is_closing = True
        
        try:
            # 1. 停止所有扫描任务
            if hasattr(self, 'scanner') and self.scanner.is_scanning():
                await self.scanner.stop_scan(force=True)
            
            # 2. 清理验证器资源
            if hasattr(self, 'validator'):
                self.validator.cleanup()
            
            # 3. 检查是否需要保存播放列表
            if hasattr(self, 'playlist_source') and self.playlist_source == 'file' and hasattr(self, 'model') and self.model.channels:
                reply = QMessageBox.question(
                    self,
                    '保存修改',
                    '是否保存对播放列表的修改？',
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel
                )
                
                if reply == QMessageBox.StandardButton.Cancel:
                    event.ignore()
                    return
                elif reply == QMessageBox.StandardButton.Yes:
                    self.save_playlist()
            
            # 4. 同步保存配置
            if hasattr(self, '_save_config_sync'):
                self._save_config_sync()
            
            # 5. 清理播放器资源
            if hasattr(self, 'player'):
                self.player.force_stop()
            
            # 6. 最后调用父类关闭事件
            super().closeEvent(event)
            event.accept()
            logger.info("窗口关闭完成")
            
        except Exception as e:
            logger.error(f"关闭异常: {str(e)}", exc_info=True)
            event.ignore()

    # 切换有效性检测状态
    async def toggle_validation(self):
        """切换有效性检测状态"""
        logger.info("开始切换有效性检测状态")
        if self.validator.is_running():
            await self.validator.stop_validation()
            self.ui_builder.ui_manager.update_validation_ui(False)
            return

        urls = [chan['url'] for chan in self.model.channels if 'url' in chan]
        if not urls:
            logger.warning("尝试检测有效性但无可用频道")
            self.show_error("没有可检测的频道")
            return
            
        self.ui_builder.ui_manager.update_validation_ui(True)
        
        try:
            # 从UI获取并发数设置并传递给验证器
            max_workers = self.thread_count_input.value()
            result = await self.validator.validate_playlist(urls, max_workers)
            
            # 处理验证结果
            self.validation_results = {chan['url']: chan['valid'] for chan in result['valid'] + result['invalid']}
            self.ui_builder.ui_manager.update_validation_ui(False, len(result['valid']), len(urls))
            
        except Exception as e:
            logger.error(f"有效性检测失败: {str(e)}", exc_info=True)
            self.show_error(f"有效性检测失败: {str(e)}")
            self.btn_validate.setText("检测有效性")
            self.btn_validate.setStyleSheet(AppStyles.button_style())
            self.btn_validate.setChecked(False)

    # 加载用户配置
    def load_config(self) -> None:
        """加载用户配置"""
        logger.debug("开始加载用户配置")
        logger.info("开始加载应用配置...")
        try:
            # 窗口布局
            window_prefs = self.config.get_window_prefs()
            if geometry := window_prefs['geometry']:
                self.restoreGeometry(QtCore.QByteArray.fromHex(geometry.encode()))
                logger.debug("恢复窗口几何布局")

            # 恢复分隔条状态
            try:
                splitters = window_prefs['splitters']
                if left_sizes := splitters['left']:
                    self.left_splitter.setSizes(
                        [int(size) for size in left_sizes.split(',') if size]
                    )
                    logger.debug(f"恢复左侧分隔条状态: {left_sizes}")
                
                if right_sizes := splitters['right']:
                    self.right_splitter.setSizes(
                        [int(size) for size in right_sizes.split(',') if size]
                    )
                    logger.debug(f"恢复右侧分隔条状态: {right_sizes}")
                
                if main_sizes := splitters['main']:
                    self.main_splitter.setSizes(
                        [int(size) for size in main_sizes.split(',') if size]
                    )
                    logger.debug(f"恢复主分隔条状态: {main_sizes}")
                
                if h_sizes := splitters['h']:
                    self.h_splitter.setSizes(
                        [int(size) for size in h_sizes.split(',') if size]
                    )
                    logger.debug(f"恢复水平分隔条状态: {h_sizes}")
            except Exception as e:
                logger.warning(f"恢复分隔条状态失败: {e}")

            # 扫描配置
            scanner_prefs = self.config.get_scanner_prefs()
            logger.info(f"加载Scanner配置: {scanner_prefs}")
            
            self.ip_range_input.setText(scanner_prefs['address'])
            self.timeout_input.setValue(scanner_prefs['timeout'])
            self.thread_count_input.setValue(scanner_prefs['thread_count'])
            self.user_agent_input.setText(scanner_prefs['user_agent'])
            self.referer_input.setText(scanner_prefs['referer'])
            logger.debug("扫描配置已应用到UI")

            # 播放器设置
            player_prefs = self.config.get_player_prefs()
            self.player.hw_accel = player_prefs['hardware_accel']
            self.volume_slider.setValue(player_prefs['volume'])
            logger.debug(f"播放器设置已加载: 硬件加速={player_prefs['hardware_accel']}, 音量={player_prefs['volume']}")

            logger.info("应用配置加载完成")
            logger.debug(f"窗口布局: {window_prefs}")
            logger.debug(f"扫描配置: {scanner_prefs}")
            logger.debug(f"播放器配置: {player_prefs}")
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
        logger.debug("开始同步保存配置")
        try:
            prefs = {
                'window': {
                    'geometry': self.saveGeometry().toHex().data().decode(),
                    'splitters': {
                        'left': self.left_splitter.sizes(),
                        'right': self.right_splitter.sizes(),
                        'main': self.main_splitter.sizes(),
                        'h': self.h_splitter.sizes()
                    }
                },
                'scanner': {
                    'address': self.ip_range_input.text(),
                    'timeout': self.timeout_input.value(),
                    'thread_count': self.thread_count_input.value(),
                    'user_agent': self.user_agent_input.text(),
                    'referer': self.referer_input.text()
                },
                'player': {
                    'hardware_accel': self.player.hw_accel,
                    'volume': self.volume_slider.value()
                }
            }
            
            self.config.save_prefs(prefs)
            logger.debug("配置已保存")
        except Exception as e:
            logger.error(f"保存配置失败: {str(e)}", exc_info=True)

    # 显示错误对话框
    @pyqtSlot(str)
    def show_error(self, msg: str) -> None:
        """显示错误对话框"""
        logger.error(f"显示错误对话框: {msg}")
        self.ui_builder.ui_manager.show_error_message("操作错误", msg)

    # 更新状态栏
    @pyqtSlot(str)
    def update_status(self, msg: str) -> None:
        """更新状态栏"""
        self.ui_builder.ui_manager.update_status(msg)

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
        
        # 通过UIManager更新状态栏
        self.ui_builder.ui_manager.update_status(final_msg)
        
        # 播放成功后额外操作
        if action == "play":
            self.ui_builder.ui_manager.update_button_state("pause_btn", "暂停", True)
            self._handle_player_state("播放中")
        
        # 扫描成功后自动保存配置（可选）
        if action == "scan":
            self._save_config_sync()

    # 统一处理错误"
    @pyqtSlot(Exception)
    def handle_error(self, error: Exception, action: str = "") -> None:
        """增强版错误处理（带错误类型识别）"""
        logger.error(f"处理{action}错误: {str(error)}", exc_info=True)
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

    # +++ 加载旧列表 +++
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
            
            # 转换为 {url: channel} 字典并传递给matcher
            self.matcher.load_old_playlist({chan['url']: chan for chan in channels})
            self.btn_match.setEnabled(True)
            self.match_status.setText(f"✔ 已加载旧列表({len(channels)}个频道) - 点击'执行自动匹配'开始匹配")
            self.match_status.setStyleSheet("color: #4CAF50; font-weight: bold;")
        except Exception as e:
            self.show_error(f"加载旧列表失败: {str(e)}")

    # +++ 执行自动匹配 +++
    async def run_auto_match(self):
        """执行自动匹配任务(中转层)
        
        设计说明：
        1. 负责连接matcher信号与UI组件
        2. 处理匹配结果的UI更新
        3. 统一错误处理和状态管理
        4. 不包含具体匹配逻辑(在matcher.py中实现)
        """
        try:
            # 连接matcher信号到UI组件
            self.matcher.match_progress.connect(self.match_progress.setValue)
            self.matcher.match_status.connect(self.match_status.setText)
            self.matcher.match_finished.connect(
                lambda: self.handle_success("匹配完成", "match"))
            self.matcher.error_occurred.connect(
                lambda msg: self.show_error(f"匹配错误: {msg}"))
            
            # 执行匹配(具体实现在matcher.py)
            await self.matcher.auto_match(self.model.channels)
            
            # 更新UI颜色
            for row in range(len(self.model.channels)):
                index = self.model.index(row, 0)
                color = self.matcher.get_match_color(self.model.channels[row])
                if color:
                    self.model.setData(index, color, Qt.ItemDataRole.BackgroundRole)
            
            # 自动保存(如果勾选)
            if self.cb_auto_save.isChecked():
                self.save_playlist()
                
        except Exception as e:
            logger.error(f"匹配任务异常: {str(e)}")
            self.match_status.setText("匹配启动失败")

# 程序入口
if __name__ == "__main__":
    # 禁用QT屏幕相关的警告
    os.environ["QT_LOGGING_RULES"] = "qt.qpa.*=false"
    app = QtWidgets.QApplication(sys.argv)
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    # 清空日志文件
    log_file = Path('iptv_manager.log')
    if log_file.exists():
        with open(log_file, 'w', encoding='utf-8') as f:
            f.truncate()

    main_window = MainWindow()
    main_window.show()

    with loop:
        sys.exit(loop.run_forever())
