import os
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QComboBox, QSizePolicy, QStyle,
)
from PyQt6.QtCore import Qt, QDir, QSize
from PyQt6.QtGui import QIcon


_VIDEO_EXTS = ('.mp4', '.mkv', '.avi', '.mov', '.flv', '.wmv', '.ts', '.m2ts', '.webm')


class VideoOpenDialog(QDialog):
    def __init__(self, parent=None, language_manager=None):
        super().__init__(parent)
        self._selected_path = None
        self._lm = language_manager
        self._current_dir = QDir.homePath()
        self._show_video_only = True

        self.setWindowTitle(self._tr("open_video", "打开视频"))
        self.setMinimumSize(640, 480)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        from ui.styles import AppStyles
        self.setStyleSheet(AppStyles.popup_dialog_style())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        nav = QHBoxLayout()
        nav.setSpacing(4)

        self._up_btn = QPushButton(self._tr("parent_folder", "上级目录"))
        self._up_btn.setFixedWidth(90)
        self._up_btn.clicked.connect(self._go_up)
        nav.addWidget(self._up_btn)

        self._path_label = QLabel()
        self._path_label.setObjectName("pathLabel")
        nav.addWidget(self._path_label, 1)

        self._filter_combo = QComboBox()
        self._filter_combo.addItem(self._tr("video_files_only", "仅视频文件"))
        self._filter_combo.addItem(self._tr("all_files", "所有文件"))
        self._filter_combo.setFixedWidth(120)
        self._filter_combo.currentIndexChanged.connect(self._on_filter_changed)
        nav.addWidget(self._filter_combo)

        layout.addLayout(nav)

        self._list = QListWidget()
        self._list.setObjectName("videoFileList")
        self._list.setIconSize(QSize(20, 20))
        self._list.itemDoubleClicked.connect(self._on_double_click)
        self._list.itemClicked.connect(self._on_single_click)
        layout.addWidget(self._list, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self._select_btn = QPushButton(self._tr("select_confirm", "选定"))
        self._select_btn.setFixedWidth(100)
        self._select_btn.setDefault(True)
        self._select_btn.clicked.connect(self._on_select)
        btn_row.addWidget(self._select_btn)

        cancel_btn = QPushButton(self._tr("cancel", "取消"))
        cancel_btn.setFixedWidth(80)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        layout.addLayout(btn_row)

        self._refresh_list()

    def _tr(self, key, default=''):
        if self._lm:
            return self._lm.tr(key, default)
        return default

    def _refresh_list(self):
        self._list.clear()
        self._path_label.setText(self._current_dir)

        try:
            entries = sorted(os.listdir(self._current_dir))
        except PermissionError:
            return

        dirs = []
        files = []
        for name in entries:
            full = os.path.join(self._current_dir, name)
            if os.path.isdir(full):
                dirs.append(name)
            elif os.path.isfile(full):
                if self._show_video_only:
                    if name.lower().endswith(_VIDEO_EXTS):
                        files.append(name)
                else:
                    files.append(name)

        for d in sorted(dirs, key=str.lower):
            item = QListWidgetItem(self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon), d)
            item.setData(Qt.ItemDataRole.UserRole, ('dir', os.path.join(self._current_dir, d)))
            self._list.addItem(item)

        for f in sorted(files, key=str.lower):
            item = QListWidgetItem(self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon), f)
            item.setData(Qt.ItemDataRole.UserRole, ('file', os.path.join(self._current_dir, f)))
            self._list.addItem(item)

    def _go_up(self):
        parent = os.path.dirname(self._current_dir)
        if parent and parent != self._current_dir:
            self._current_dir = parent
            self._refresh_list()

    def _on_filter_changed(self, index):
        self._show_video_only = (index == 0)
        self._refresh_list()

    def _on_single_click(self, item):
        pass

    def _on_double_click(self, item):
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return
        kind, path = data
        if kind == 'dir':
            self._current_dir = path
            self._refresh_list()
        else:
            self._selected_path = path
            self.accept()

    def _on_select(self):
        item = self._list.currentItem()
        if not item:
            self._selected_path = self._current_dir
            self.accept()
            return
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data:
            self._selected_path = self._current_dir
            self.accept()
            return
        kind, path = data
        self._selected_path = path
        self.accept()

    def get_selected_path(self):
        return self._selected_path