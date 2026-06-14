from core.log_manager import global_logger as logger


class ServerMixin:
    """从 IPTVPlayer 提取的 Server 管理职责"""

    def _auto_start_server(self):
        try:
            from server.app import set_main_window, start_server, get_server
            set_main_window(self)
            settings = self.config.load_server_settings()
            if settings.get('auto_start', True):
                port = settings.get('port', 8080)
                host = settings.get('host', '0.0.0.0')
                start_server(host=host, port=port)
                server = get_server()
                if server.is_running():
                    tr = self.language_manager.tr
                    self.status_bar_show_message(
                        tr('server_started', 'Server已启动') + f' http://localhost:{port}'
                    )
                    logger.info(f"Server后端自动启动: http://{host}:{port}")
        except Exception as e:
            logger.error(f"自动启动Server失败: {e}")

    def _toggle_server(self):
        try:
            from server.app import get_server, start_server, stop_server, set_main_window
            set_main_window(self)
            server = get_server()
            tr = self.language_manager.tr
            if server.is_running():
                stop_server()
                self.status_bar_show_message(tr('server_stopped', 'Server已停止'))
                self._server_action.setText(tr('server_start', '启动Server'))
            else:
                settings = self.config.load_server_settings()
                port = settings.get('port', 8080)
                host = settings.get('host', '0.0.0.0')
                start_server(host=host, port=port)
                self.status_bar_show_message(
                    tr('server_started', 'Server已启动') + f' http://localhost:{port}'
                )
                self._server_action.setText(tr('server_stop', '停止Server'))
        except Exception as e:
            logger.error(f"切换Server失败: {e}")

    def _open_server_api(self):
        try:
            from server.app import get_server
            server = get_server()
            port = server.port if server and server.is_running() else 8080
            import webbrowser
            webbrowser.open(f'http://localhost:{port}/')
        except Exception as e:
            logger.error(f"打开Server API失败: {e}")

    def _show_server_settings(self):
        from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                                        QSpinBox, QCheckBox, QPushButton, QComboBox)
        from ui.styles import AppStyles
        tr = self.language_manager.tr
        dialog = QDialog(self)
        dialog.setWindowTitle(tr('server_settings', 'Server设置'))
        dialog.setMinimumWidth(400)
        layout = QVBoxLayout(dialog)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 20, 24, 20)

        settings = self.config.load_server_settings()

        from server.app import get_server
        server = get_server()
        is_running = server.is_running()
        port = server.port if is_running else settings.get('port', 8080)

        status_label = QLabel()
        if is_running:
            status_label.setText(f"● {tr('server_running', 'Server运行中')}  http://localhost:{port}")
            status_label.setStyleSheet("color: #4CAF50; font-weight: bold; font-size: 13px;")
        else:
            status_label.setText(f"○ {tr('server_not_running', 'Server未运行')}")
            status_label.setStyleSheet("color: #FF9800; font-weight: bold; font-size: 13px;")
        layout.addWidget(status_label)

        layout.addSpacing(4)

        auto_start_cb = QCheckBox(tr('server_auto_start', '启动时自动运行Server'))
        auto_start_cb.setChecked(settings.get('auto_start', True))
        layout.addWidget(auto_start_cb)

        port_layout = QHBoxLayout()
        port_label = QLabel(tr('server_port', '端口:'))
        port_label.setFixedWidth(70)
        port_layout.addWidget(port_label)
        port_spin = QSpinBox()
        port_spin.setRange(1024, 65535)
        port_spin.setValue(port)
        port_layout.addWidget(port_spin, 1)
        layout.addLayout(port_layout)

        host_layout = QHBoxLayout()
        host_label = QLabel(tr('server_host', '监听地址:'))
        host_label.setFixedWidth(70)
        host_layout.addWidget(host_label)
        host_combo = QComboBox()
        host_combo.addItem('0.0.0.0 (所有接口)', '0.0.0.0')
        host_combo.addItem('127.0.0.1 (仅本机)', '127.0.0.1')
        host_idx = host_combo.findData(settings.get('host', '0.0.0.0'))
        if host_idx >= 0:
            host_combo.setCurrentIndex(host_idx)
        host_layout.addWidget(host_combo, 1)
        layout.addLayout(host_layout)

        layout.addSpacing(8)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        save_btn = QPushButton(tr('save', '保存'))
        cancel_btn = QPushButton(tr('cancel', '取消'))
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        def on_save():
            self.config.save_server_settings(
                enabled=True,
                port=port_spin.value(),
                host=host_combo.currentData(),
                auto_start=auto_start_cb.isChecked()
            )
            dialog.accept()

        save_btn.clicked.connect(on_save)
        cancel_btn.clicked.connect(dialog.reject)
        save_btn.setStyleSheet(AppStyles.common_button_style())
        cancel_btn.setStyleSheet(AppStyles.common_button_style())

        dialog.setStyleSheet(AppStyles.popup_dialog_style())
        dialog.exec()