"""
事件处理器 - 负责键盘快捷键、事件过滤、窗口事件等
从 pyqt_player.py 提取的独立模块
"""

from typing import Optional
from PyQt6.QtCore import Qt, QEvent, QTimer
from PyQt6.QtGui import QKeyEvent


class EventHandler:
    """事件处理器 - 统一管理所有事件处理逻辑"""

    def __init__(self, main_window):
        self.window = main_window
        self._shortcuts = {}  # 快捷键映射表

    def keyPressEvent(self, event: QKeyEvent) -> bool:
        """
        处理键盘按键事件
        Returns: bool - 是否已处理该事件
        """
        key = event.key()
        modifiers = event.modifiers()
        
        # 常用快捷键
        if modifiers == Qt.KeyboardModifier.NoModifier:
            if key == Qt.Key.Key_Space:
                # 空格键: 播放/暂停
                if hasattr(self.window, 'playback_ctrl'):
                    self.window.playback_ctrl.toggle_play()
                return True
                
            elif key == Qt.Key.Key_Escape:
                # ESC: 退出全屏/停止播放
                if hasattr(self.window, 'isFullScreen') and self.window.isFullScreen():
                    self.window.toggle_fullscreen()
                else:
                    if hasattr(self.window, 'playback_ctrl'):
                        self.window.playback_ctrl.stop_playback()
                return True
                
            elif key == Qt.Key.Key_F:
                # F键: 切换全屏
                if hasattr(self.window, 'toggle_fullscreen'):
                    self.window.toggle_fullscreen()
                return True
                
            elif key == Qt.Key.Key_M:
                # M键: 静音
                if hasattr(self.window, 'playback_ctrl'):
                    self.window.playback_ctrl.toggle_mute()
                return True
        
        elif modifiers & Qt.KeyboardModifier.ControlModifier:
            if key == Qt.Key.Key_O:
                # Ctrl+O: 打开文件
                if hasattr(self.window, 'settings_ops'):
                    self.window.settings_ops.open_playlist()
                return True
                
            elif key == Qt.Key.Key_S:
                # Ctrl+S: 保存
                if hasattr(self.window, 'settings_ops'):
                    self.window.settings_ops.save_as()
                return True
                
            elif key == Qt.Key.Key_Q:
                # Ctrl+Q: 退出
                self.window.close()
                return True
        
        elif modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier):
            if key == Qt.Key.Key_Left:
                # Ctrl+Shift+Left: 上一个频道
                self._switch_channel(-1)
                return True
            elif key == Qt.Key.Key_Right:
                # Ctrl+Shift+Right: 下一个频道
                self._switch_channel(1)
                return True

        return False

    def _switch_channel(self, direction: int):
        """切换频道（-1=上一个，1=下一个）"""
        if not hasattr(self.window, 'channel_list'):
            return
            
        current_row = self.window.channel_list.currentRow()
        total_rows = self.window.channel_list.count()
        
        if total_rows == 0:
            return
            
        new_row = (current_row + direction) % total_rows
        self.window.channel_list.setCurrentRow(new_row)
        
        # 触发选择事件
        item = self.window.channel_list.currentItem()
        if item and hasattr(self.window, 'channel_ctrl'):
            self.window.channel_ctrl.select_channel(item)

    def eventFilter(self, obj, event: QEvent) -> bool:
        """事件过滤器 - 处理特殊事件"""
        event_type = event.type()
        
        # 鼠标移动事件（用于OSD显示）
        if event_type == QEvent.Type.MouseMove:
            if hasattr(self.window, '_on_mouse_activity'):
                self.window._on_mouse_activity()
                
        # 焦点事件
        elif event_type == QEvent.Type.FocusIn:
            pass
            
        return False  # 不消费事件，继续传递

    def showEvent(self, event):
        """窗口首次显示时，多阶段渐进式修正悬浮窗位置"""
        from core.log_manager import global_logger as logger
        logger.debug("窗口显示事件 - 显示并定位悬浮窗")

        if hasattr(self.window, 'showEvent'):
            orig_show = type(self.window).__bases__[0].showEvent
            orig_show(self.window, event)

        # 首次显示时，确保所有悬浮窗可见并正确定位
        if not getattr(self.window, '_initial_position_fixed', False):
            self.window._initial_position_fixed = True

            # 确保所有悬浮窗都显示
            for panel_name in ['epg_panel', 'playlist_panel', 'floating_panel']:
                panel = getattr(self.window, panel_name, None)
                if panel and not panel.isVisible():
                    try:
                        panel.show()
                        logger.debug(f"显示悬浮窗: {panel_name}")
                    except Exception as e:
                        logger.error(f"显示{panel_name}失败: {e}")

            # 多阶段修正位置
            from PyQt6.QtCore import QTimer
            for delay in (50, 150, 300):
                QTimer.singleShot(delay, self.window.update_floating_position)

    def changeEvent(self, event):
        """窗口状态变化事件"""
        if hasattr(self.window, 'changeEvent'):
            try:
                orig_change = type(self.window).__bases__[0].changeEvent
                orig_change(self.window, event)
            except:
                pass

        if event.type() == QEvent.Type.ActivationChange and self.window.isActiveWindow():
            if hasattr(self.window, 'raise_floating_panels'):
                self.window.raise_floating_panels()

    def moveEvent(self, event):
        """窗口移动事件"""
        if hasattr(self.window, 'moveEvent'):
            try:
                orig_move = type(self.window).__bases__[0].moveEvent
                orig_move(self.window, event)
            except:
                pass

        if hasattr(self.window, 'update_floating_position'):
            self.window.update_floating_position()

    def resizeEvent(self, event):
        """窗口大小变化事件"""
        if hasattr(self.window, 'resizeEvent'):
            try:
                orig_resize = type(self.window).__bases__[0].resizeEvent
                orig_resize(self.window, event)
            except:
                pass

        if hasattr(self.window, 'update_floating_position'):
            self.window.update_floating_position()

    def closeEvent(self, event):
        """窗口关闭事件"""
        from core.log_manager import global_logger as logger
        logger.debug("关闭事件 - 清理所有资源")

        # 1. 保存窗口布局
        if hasattr(self.window, 'settings_ops'):
            try:
                self.window.settings_ops.save_window_layout()
            except Exception as e:
                logger.error(f"保存窗口布局失败: {e}")

        # 2. 彻底终止MPV播放器（关键修复！）
        if hasattr(self.window, 'player_controller') and self.window.player_controller:
            try:
                logger.debug("正在终止MPV播放器...")
                if hasattr(self.window.player_controller, 'terminate'):
                    self.window.player_controller.terminate()
                else:
                    self.window.player_controller.stop()
                logger.info("MPV播放器已终止")
            except Exception as e:
                logger.error(f"终止MPV播放器失败: {e}")

        # 3. 关闭扫描窗口
        scan_dialog = getattr(self.window, '_scan_dialog', None) or getattr(self.window, 'scan_window', None)
        if scan_dialog:
            try:
                scan_dialog.close()
                scan_dialog.deleteLater()
            except Exception:
                pass
            self.window._scan_dialog = None
            self.window.scan_window = None

        # 4. 关闭所有悬浮窗
        for panel_name in ['floating_panel', 'epg_panel', 'playlist_panel']:
            panel = getattr(self.window, panel_name, None)
            if panel:
                try:
                    logger.debug(f"关闭悬浮窗: {panel_name}")
                    panel.close()
                    panel.deleteLater()
                except Exception as e:
                    logger.error(f"关闭{panel_name}失败: {e}")
                setattr(self.window, panel_name, None)

        # 5. 停止所有定时器
        timer_attrs = ['update_timer', 'resize_timer', '_source_timeout_timer',
                       '_auto_hide_timer', '_epg_update_timer']
        for attr in timer_attrs:
            timer = getattr(self.window, attr, None)
            if timer:
                try:
                    timer.stop()
                except Exception:
                    pass

        # 6. 强制退出应用（使用sys.exit确保进程完全终止）
        event.accept()

        import sys
        from PyQt6.QtWidgets import QApplication
        try:
            QApplication.instance().quit()
        except Exception:
            pass

        import time
        time.sleep(0.2)  # 给Qt一点时间清理

        sys.exit(0)

    def register_shortcut(self, key_sequence: str, callback):
        """注册自定义快捷键"""
        self._shortcuts[key_sequence] = callback

    def unregister_shortcut(self, key_sequence: str):
        """注销快捷键"""
        if key_sequence in self._shortcuts:
            del self._shortcuts[key_sequence]
