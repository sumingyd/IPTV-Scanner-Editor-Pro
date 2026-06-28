"""网络流媒体增强对话框 - Referer + HTTP 代理 + HTTP Headers"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QPushButton,
    QLineEdit, QPlainTextEdit, QGroupBox, QWidget, QSizePolicy,
)

from ui.floating_dialog import FloatingDialog
from ui.styles import AppStyles
from core.log_manager import global_logger as logger


# 代理格式提示
PROXY_FORMAT_HINT = (
    "Supported formats:\n"
    "  http://host:port\n"
    "  https://host:port\n"
    "  socks5://host:port\n"
    "  socks5h://host:port (DNS via proxy)\n"
    "Leave empty to disable proxy."
)


class NetworkEnhanceDialog(FloatingDialog):
    """网络流媒体增强对话框
    - HTTP Referer：用于绕过防盗链
    - HTTP/HTTPS 代理：用于访问受限内容
    - HTTP Headers：自定义 HTTP 头（每行一个，格式 Key: Value）
    保存按钮持久化到 config 并实时应用到 mpv
    """

    def __init__(self, main_window, parent=None):
        super().__init__(parent, frameless=False, stay_on_top=False)
        self.window = main_window
        tr = main_window.language_manager.tr
        self.setWindowTitle(tr('network_enhance_title', 'Network Stream Enhance'))
        self.setMinimumSize(560, 540)
        self._loading = False
        self._setup_ui()
        self._apply_theme()
        try:
            from ui.theme_manager import get_theme_manager
            get_theme_manager().register_window(self)
        except Exception:
            pass
        self._reload_from_config()

    def _apply_theme(self):
        c = AppStyles._get_colors()
        r = AppStyles._get_style_border_radius()
        text_color = c.get('window_text', '#ffffff')
        self.setStyleSheet(AppStyles.popup_dialog_style() + f"""
            QLabel {{ color: {text_color}; }}
            QGroupBox {{
                color: {text_color};
                border: 1px solid {c.get('mid', '#555')};
                border-radius: {r}px;
                margin-top: 12px; padding: 8px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin; left: 10px; padding: 0 4px;
            }}
            QLineEdit, QPlainTextEdit {{
                background: {c.get('base', '#1a1a1a')};
                color: {text_color};
                border: 1px solid {c.get('mid', '#555')};
                border-radius: {r}px;
                padding: 4px;
            }}
        """)

    def _setup_ui(self):
        tr = self.window.language_manager.tr
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # ===== Referer 组 =====
        referer_group = QGroupBox(tr('network_enhance_group_referer', 'HTTP Referer'))
        rform = QFormLayout(referer_group)
        rform.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.referer_edit = QLineEdit()
        self.referer_edit.setPlaceholderText('https://example.com/')
        rform.addRow(tr('network_enhance_referer', 'Referer'), self.referer_edit)
        referer_hint = QLabel(tr('network_enhance_referer_hint',
            'Used to bypass hotlink protection. Leave empty to disable.'))
        referer_hint.setWordWrap(True)
        rform.addRow('', referer_hint)
        layout.addWidget(referer_group)

        # ===== 代理组 =====
        proxy_group = QGroupBox(tr('network_enhance_group_proxy', 'HTTP/HTTPS Proxy'))
        pform = QFormLayout(proxy_group)
        pform.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.proxy_edit = QLineEdit()
        self.proxy_edit.setPlaceholderText('http://127.0.0.1:8080')
        pform.addRow(tr('network_enhance_proxy', 'Proxy URL'), self.proxy_edit)
        proxy_hint = QLabel(tr('network_enhance_proxy_hint', PROXY_FORMAT_HINT))
        proxy_hint.setWordWrap(True)
        pform.addRow('', proxy_hint)
        layout.addWidget(proxy_group)

        # ===== HTTP Headers 组 =====
        headers_group = QGroupBox(tr('network_enhance_group_headers', 'HTTP Headers'))
        hform = QVBoxLayout(headers_group)
        self.headers_edit = QPlainTextEdit()
        self.headers_edit.setPlaceholderText('Key: Value\nKey2: Value2')
        self.headers_edit.setFixedHeight(120)
        hform.addWidget(self.headers_edit)
        headers_hint = QLabel(tr('network_enhance_headers_hint',
            'One header per line, format: Key: Value'))
        headers_hint.setWordWrap(True)
        hform.addWidget(headers_hint)
        layout.addWidget(headers_group)

        # ===== 操作按钮 =====
        btn_row = QHBoxLayout()
        self.clear_btn = QPushButton(tr('network_enhance_clear', 'Clear All'))
        self.clear_btn.clicked.connect(self._clear_all)
        btn_row.addWidget(self.clear_btn)

        btn_row.addStretch()

        self.apply_btn = QPushButton(tr('network_enhance_apply', 'Apply'))
        self.apply_btn.clicked.connect(self._apply_now)
        btn_row.addWidget(self.apply_btn)

        self.save_btn = QPushButton(tr('audio_eq_save', 'Save'))
        self.save_btn.clicked.connect(self._save)
        btn_row.addWidget(self.save_btn)

        self.close_btn = QPushButton(tr('playback_queue_close', 'Close'))
        self.close_btn.clicked.connect(self.close)
        btn_row.addWidget(self.close_btn)
        layout.addLayout(btn_row)

    def _reload_from_config(self):
        """从 config 加载当前设置"""
        self._loading = True
        try:
            cfg = self.window.config.load_playback_settings()
            self.referer_edit.setText(cfg.get('http_referer', '') or '')
            self.proxy_edit.setText(cfg.get('http_proxy', '') or '')
            self.headers_edit.setPlainText(cfg.get('http_headers', '') or '')
        except Exception as e:
            logger.debug(f"加载网络增强设置失败: {e}")
        finally:
            self._loading = False

    def _collect_settings(self) -> dict:
        return {
            'http_referer': self.referer_edit.text().strip(),
            'http_proxy': self.proxy_edit.text().strip(),
            'http_headers': self.headers_edit.toPlainText().strip(),
        }

    def _apply_to_mpv(self):
        """实时应用到 mpv"""
        pc = self.window.player_controller
        if not pc:
            return
        try:
            settings = self._collect_settings()
            if hasattr(pc, 'set_http_referer'):
                pc.set_http_referer(settings['http_referer'])
            if hasattr(pc, 'set_http_proxy'):
                pc.set_http_proxy(settings['http_proxy'])
            # HTTP Headers 通过 playback_settings 应用
            if hasattr(pc, '_playback_settings'):
                pc._playback_settings['http_headers'] = settings['http_headers']
                pc._playback_settings['http_referer'] = settings['http_referer']
                pc._playback_settings['http_proxy'] = settings['http_proxy']
        except Exception as e:
            logger.debug(f"应用网络增强设置到 mpv 失败: {e}")

    def _apply_now(self):
        """应用（不保存到 config）"""
        self._apply_to_mpv()
        tr = self.window.language_manager.tr
        if hasattr(self.window, '_show_osd_feedback'):
            self.window._show_osd_feedback(tr('network_enhance_applied', 'Network settings applied'))

    def _save(self):
        """保存到 config 并应用"""
        try:
            settings = self._collect_settings()
            # 合并现有 settings 后保存
            cfg = self.window.config.load_playback_settings()
            cfg.update(settings)
            self.window.config.save_playback_settings(cfg)
            self._apply_to_mpv()
            tr = self.window.language_manager.tr
            if hasattr(self.window, '_show_osd_feedback'):
                self.window._show_osd_feedback(tr('network_enhance_saved', 'Network settings saved'))
        except Exception as e:
            logger.error(f"保存网络增强设置失败: {e}")

    def _clear_all(self):
        """清除所有设置"""
        self.referer_edit.clear()
        self.proxy_edit.clear()
        self.headers_edit.clear()

    def closeEvent(self, event):
        try:
            from ui.theme_manager import get_theme_manager
            get_theme_manager().unregister_window(self)
        except Exception:
            pass
        super().closeEvent(event)
