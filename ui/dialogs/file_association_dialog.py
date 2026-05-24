from PyQt6 import QtWidgets
from PyQt6.QtCore import Qt
from ..floating_dialog import FloatingDialog


SUPPORTED_FORMATS = {
    'playlist': {
        'label_zh': '播放列表',
        'label_en': 'Playlist',
        'extensions': ['.m3u', '.m3u8'],
    },
    'text': {
        'label_zh': '文本列表',
        'label_en': 'Text List',
        'extensions': ['.txt'],
    },
    'video': {
        'label_zh': '视频文件',
        'label_en': 'Video Files',
        'extensions': ['.mp4', '.mkv', '.avi', '.mov', '.flv', '.wmv', '.ts', '.webm'],
    },
}


class FileAssociationDialog(FloatingDialog):
    def __init__(self, parent=None):
        super().__init__(parent, stay_on_top=False)
        self.language_manager = getattr(parent, 'language_manager', None)
        if not self.language_manager:
            from core.language_manager import LanguageManager
            self.language_manager = LanguageManager()
            self.language_manager.load_available_languages()
            self.language_manager.set_language('zh')

        from ..styles import AppStyles
        self.setStyleSheet(AppStyles.dialog_style())

        self._checkboxes = {}
        self._init_ui()
        self._load_current_state()

        from ..theme_manager import get_theme_manager
        get_theme_manager().register_window(self)

    def _tr(self, key, fallback):
        v = self.language_manager.tr(key, fallback)
        return v if v else fallback

    def _init_ui(self):
        tr = self._tr
        self.setWindowTitle(tr("file_association", "File Association"))
        self.setMinimumSize(400, 360)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title = QtWidgets.QLabel(tr("file_assoc_title", "选择要关联的文件格式"))
        from ui.styles import AppStyles
        title_colors = AppStyles._get_colors()
        title.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {title_colors['window_text']};")
        layout.addWidget(title)

        hint = QtWidgets.QLabel(tr("file_assoc_hint", '注册后，右键文件即可在"打开方式"中选择本程序'))
        from ui.styles import AppStyles
        hint_colors = AppStyles._get_colors()
        hint.setStyleSheet(f"font-size: 11px; color: {hint_colors['player_panel_hint']};")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        from ui.styles import AppStyles
        checkbox_style = AppStyles.common_check_box_style()

        for group_key, group_info in SUPPORTED_FORMATS.items():
            lang = self.language_manager.current_language if self.language_manager else 'zh'
            group_label = group_info['label_zh'] if lang == 'zh' else group_info['label_en']

            group_box = QtWidgets.QGroupBox(group_label)
            group_box.setStyleSheet(AppStyles.common_group_box_style())

            cols = 4
            grid = QtWidgets.QGridLayout(group_box)
            grid.setSpacing(8)
            grid.setColumnStretch(cols, 1)

            row, col = 0, 0
            for ext in group_info['extensions']:
                cb = QtWidgets.QCheckBox(ext)
                cb.setProperty('extension', ext)
                if checkbox_style:
                    cb.setStyleSheet(checkbox_style)
                self._checkboxes[ext] = cb
                grid.addWidget(cb, row, col)
                col += 1
                if col >= cols:
                    col = 0
                    row += 1

            select_all = QtWidgets.QCheckBox(tr("select_all", "全选"))
            select_all.setStyleSheet("font-size: 11px;")
            select_all.stateChanged.connect(lambda state, gk=group_key: self._toggle_group(gk, state))
            grid.addWidget(select_all, row, col)
            self._checkboxes[f'_select_all_{group_key}'] = select_all

            layout.addWidget(group_box)

        layout.addStretch()

        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addStretch()

        ok_btn = QtWidgets.QPushButton(tr("ok", "确定"))
        ok_btn.setFixedSize(90, 32)
        ok_btn.clicked.connect(self._on_ok)
        btn_layout.addWidget(ok_btn)

        cancel_btn = QtWidgets.QPushButton(tr("cancel", "取消"))
        cancel_btn.setFixedSize(90, 32)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

    def _toggle_group(self, group_key, state):
        group_info = SUPPORTED_FORMATS[group_key]
        checked = state == Qt.CheckState.Checked.value
        for ext in group_info['extensions']:
            if ext in self._checkboxes:
                self._checkboxes[ext].setChecked(checked)

    def _load_current_state(self):
        from utils.general_utils import is_extension_registered
        for ext in self._checkboxes:
            if ext.startswith('_'):
                continue
            registered = is_extension_registered(ext)
            self._checkboxes[ext].setChecked(registered)

    def _on_ok(self):
        from utils.general_utils import register_extension, unregister_extension
        for ext, cb in self._checkboxes.items():
            if ext.startswith('_'):
                continue
            if cb.isChecked():
                register_extension(ext)
            else:
                unregister_extension(ext)
        self.accept()

    def reapply_styles(self):
        from ..styles import AppStyles
        colors = AppStyles._get_colors()
        for child in self.findChildren(QtWidgets.QLabel):
            existing = child.styleSheet()
            if 'font-weight: bold' in existing:
                child.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {colors['window_text']};")
            elif 'player_panel_hint' in existing or 'font-size: 11px' in existing:
                child.setStyleSheet(f"font-size: 11px; color: {colors['player_panel_hint']};")
        for child in self.findChildren(QtWidgets.QGroupBox):
            child.setStyleSheet(AppStyles.common_group_box_style())
        for child in self.findChildren(QtWidgets.QPushButton):
            child.setStyleSheet(AppStyles.common_button_style())
        for child in self.findChildren(QtWidgets.QCheckBox):
            child.setStyleSheet(AppStyles.common_check_box_style())
