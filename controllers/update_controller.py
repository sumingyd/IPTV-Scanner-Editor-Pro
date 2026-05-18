"""
更新检查控制器 - 负责异步版本检查和新版本提示
从 pyqt_player.py 提取的独立模块
"""

import asyncio
from PyQt6.QtCore import QThread, pyqtSignal, QMetaObject, Qt
from core.log_manager import global_logger as logger


class UpdateCheckThread(QThread):
    """版本检查线程"""
    update_found = pyqtSignal(str, str)
    check_completed = pyqtSignal(bool, str)

    def run(self):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            from ui.dialogs.about_dialog import AboutDialog
            current_version = AboutDialog.CURRENT_VERSION

            latest_version, _, _ = loop.run_until_complete(
                asyncio.wait_for(self._get_latest_version(), timeout=15)
            )

            if latest_version and not latest_version.startswith("("):
                if self._is_newer_version(current_version, latest_version):
                    self.update_found.emit(latest_version, current_version)
                    self.check_completed.emit(True, f"发现新版本: {latest_version}")
                else:
                    self.check_completed.emit(True, "当前已是最新版本")
            else:
                self.check_completed.emit(False, f"版本检查失败: {latest_version}")

        except asyncio.TimeoutError:
            self.check_completed.emit(False, "版本检查超时")
        except Exception as e:
            self.check_completed.emit(False, f"版本检查异常: {str(e)}")
        finally:
            try:
                loop.close()
            except Exception:
                pass

    async def _get_latest_version(self):
        """从GitHub获取最新版本信息"""
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://api.github.com/repos/sumingyd/IPTV-Scanner-Editor-Pro/releases/latest",
                    headers={'User-Agent': 'IPTV-Scanner-Editor-Pro'},
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        version = data.get('tag_name', '').lstrip('v')
                        return version, None, None
                    elif response.status == 403:
                        return "(API限制)", None, None
                    else:
                        return "(获取失败)", None, None
        except asyncio.TimeoutError:
            return "(请求超时)", None, None
        except Exception:
            return "(获取失败)", None, None

    def _is_newer_version(self, current_version, latest_version):
        """比较版本号，判断最新版本是否比当前版本新"""
        try:
            current_parts = list(map(int, current_version.split('.')))
            latest_parts = list(map(int, latest_version.split('.')))

            max_length = max(len(current_parts), len(latest_parts))
            current_parts.extend([0] * (max_length - len(current_parts)))
            latest_parts.extend([0] * (max_length - len(latest_parts)))

            for i in range(max_length):
                if latest_parts[i] > current_parts[i]:
                    return True
                elif latest_parts[i] < current_parts[i]:
                    return False
            return False
        except (ValueError, AttributeError):
            return latest_version > current_version


class UpdateController:
    """更新检查控制器 - 管理版本检查和新版本提示"""

    def __init__(self, main_window):
        self.window = main_window
        self._update_checking = False
        self._update_checked = False
        self._check_thread = None

    def check_for_updates(self):
        """异步检查新版本"""
        if self._update_checking:
            return
        if self._update_checked:
            return

        self._update_checking = True
        try:
            old_thread = self._check_thread
            if old_thread and old_thread.isRunning():
                old_thread.quit()
                old_thread.wait(1000)

            self._check_thread = UpdateCheckThread()
            self._check_thread.setParent(self.window)
            self._check_thread.update_found.connect(self._on_update_found)
            self._check_thread.check_completed.connect(self._on_update_check_completed)
            self._check_thread.finished.connect(self._check_thread.deleteLater)
            self._check_thread.start()

        except Exception as e:
            logger.error(f"启动版本检查失败: {str(e)}")
        finally:
            self._update_checking = False
            self._update_checked = True

    def _on_update_found(self, latest_version, current_version):
        """发现新版本时的处理"""
        try:
            from ui.styles import AppStyles
            language_manager = self.window.language_manager

            original_title = self.window.windowTitle() or ""
            new_version_text = language_manager.tr("new_version_available", "New Version Available") or "New Version Available"
            if new_version_text not in original_title:
                new_title = f"{original_title} - {new_version_text} {latest_version}"
                self.window.setWindowTitle(new_title)

            status_message = f"{language_manager.tr('new_version_found', 'New version found')} {latest_version} ({language_manager.tr('current_version', 'Current Version')} {current_version})"
            self.window.status_bar.showMessage(status_message, 10000)

            self.window.status_bar.setStyleSheet(AppStyles.statusbar_error_style())

            QMetaObject.invokeMethod(self.window, "_reset_statusbar_style", Qt.ConnectionType.QueuedConnection)

            logger.info(f"发现新版本: {latest_version} (当前版本: {current_version})")

        except Exception as e:
            logger.error(f"更新界面提示失败: {str(e)}")

    def _on_update_check_completed(self, success, message):
        if success:
            logger.info(f"版本检查完成: {message}")
        else:
            logger.warning(f"版本检查失败: {message}")
