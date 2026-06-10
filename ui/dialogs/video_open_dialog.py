import os
import sys
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QComboBox, QSizePolicy, QStyle, QLineEdit,
    QInputDialog, QMenu,
)
from PySide6.QtCore import Qt, QDir, QSize
from PySide6.QtGui import QIcon
from PySide6.QtGui import QAction


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

        self._drive_btn = None
        self._drives_cache = None
        if sys.platform == 'win32':
            self._drive_btn = QPushButton(self._tr("drive", "盘符"))
            self._drive_btn.setFixedWidth(70)
            self._drive_btn.setMenu(self._build_drive_menu())
            nav.addWidget(self._drive_btn)

        self._path_edit = QLineEdit(self._current_dir)
        self._path_edit.returnPressed.connect(self._on_path_entered)
        nav.addWidget(self._path_edit, 1)

        go_btn = QPushButton(self._tr("go", "转到"))
        go_btn.setFixedWidth(50)
        go_btn.clicked.connect(self._on_path_entered)
        nav.addWidget(go_btn)

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

    def _get_volume_label(self, root_path):
        try:
            import ctypes
            import threading
            result = [None]
            def _query():
                try:
                    kernel32 = ctypes.windll.kernel32
                    vol_name_buf = ctypes.create_unicode_buffer(256)
                    fs_name_buf = ctypes.create_unicode_buffer(256)
                    serial = ctypes.c_uint32(0)
                    max_comp = ctypes.c_uint32(0)
                    fs_flags = ctypes.c_uint32(0)
                    ret = kernel32.GetVolumeInformationW(
                        root_path, vol_name_buf, ctypes.sizeof(vol_name_buf) // 2,
                        ctypes.byref(serial), ctypes.byref(max_comp),
                        ctypes.byref(fs_flags), fs_name_buf, ctypes.sizeof(fs_name_buf) // 2
                    )
                    if ret:
                        result[0] = vol_name_buf.value
                except Exception:
                    pass
            t = threading.Thread(target=_query, daemon=True)
            t.start()
            t.join(timeout=0.3)
            return result[0] or ''
        except Exception:
            return ''

    def _get_win_drives(self):
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            size = kernel32.GetLogicalDriveStringsW(0, None)
            if size <= 0:
                return []
            buf = ctypes.create_unicode_buffer(size + 1)
            kernel32.GetLogicalDriveStringsW(size + 1, buf)
            drives = []
            offset = 0
            while offset < size:
                s = ctypes.wstring_at(ctypes.addressof(buf) + offset * 2)
                if not s:
                    break
                drives.append(s)
                offset += len(s) + 1
            return drives
        except Exception:
            return []

    def _get_drives_cached(self):
        if self._drives_cache is not None:
            return self._drives_cache
        drives = self._get_win_drives()
        if not drives:
            for d in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
                root = f'{d}:\\'
                if os.path.isdir(root):
                    drives.append(root)
        result = []
        for root_path in drives:
            root_path = root_path.rstrip('\\') + '\\'
            display = root_path
            try:
                vol_label = self._get_volume_label(root_path)
                if vol_label:
                    display = f"{root_path} ({vol_label})"
            except Exception:
                pass
            result.append((root_path, display))
        self._drives_cache = result
        return result

    def _build_drive_menu(self):
        menu = QMenu(self)
        from ui.styles import AppStyles
        c = AppStyles._get_colors()
        r = AppStyles._get_style_border_radius()
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {c.get('player_panel', '#1e1e1e')};
                color: {c.get('window_text', '#ffffff')};
                border: 1px solid {c.get('mid', '#555')};
                border-radius: {r}px;
                padding: 4px 0;
            }}
            QMenu::item {{
                padding: 6px 24px;
                color: {c.get('window_text', '#ffffff')};
            }}
            QMenu::item:selected {{
                background-color: {c.get('highlight', '#264f78')};
                color: {c.get('highlighted_text', '#ffffff')};
            }}
            QMenu::separator {{
                height: 1px;
                background-color: {c.get('mid', '#555')};
                margin: 4px 8px;
            }}
        """)
        current_drive = os.path.splitdrive(self._current_dir)[0]
        for root_path, display in self._get_drives_cached():
            action = QAction(display, self)
            action.setData(root_path)
            action.triggered.connect(self._on_drive_action)
            if root_path.rstrip('\\') == current_drive:
                f = action.font()
                f.setBold(True)
                action.setFont(f)
            menu.addAction(action)

        menu.addSeparator()
        net_action = QAction(self._tr("network_path", "网络路径 (\\\\server\\share)"), self)
        net_action.triggered.connect(self._on_network_path)
        menu.addAction(net_action)
        return menu

    def _on_drive_action(self):
        action = self.sender()
        if not action:
            return
        root = action.data()
        if root and os.path.isdir(root):
            self._current_dir = root
            self._refresh_list()

    def _on_network_path(self):
        net_path, ok = QInputDialog.getText(
            self,
            self._tr("network_path", "网络路径"),
            self._tr("enter_network_path", "输入网络路径 (\\\\server\\share):")
        )
        if ok and net_path.strip():
            net_path = net_path.strip()
            if os.path.isdir(net_path):
                self._current_dir = net_path
                self._refresh_list()

    def _refresh_list(self):
        self._list.clear()
        self._path_edit.setText(self._current_dir)


        try:
            entries = sorted(os.listdir(self._current_dir))
        except PermissionError:
            return
        except OSError:
            return

        dirs = []
        files = []
        for name in entries:
            full = os.path.join(self._current_dir, name)
            try:
                is_dir = os.path.isdir(full)
            except OSError:
                continue
            if is_dir:
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

    def _show_drives_root(self):
        self._list.clear()
        self._path_edit.setText('')

        if sys.platform == 'win32':
            for root_path, display in self._get_drives_cached():
                item = QListWidgetItem(self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon), display)
                item.setData(Qt.ItemDataRole.UserRole, ('drive', root_path))
                self._list.addItem(item)

            net_item = QListWidgetItem(
                self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon),
                self._tr("network_path", "网络路径 (\\\\server\\share)")
            )
            net_item.setData(Qt.ItemDataRole.UserRole, ('network', ''))
            self._list.addItem(net_item)

    def _go_up(self):
        parent = os.path.dirname(self._current_dir)
        if parent and parent != self._current_dir:
            self._current_dir = parent
            self._refresh_list()
        elif sys.platform == 'win32':
            self._current_dir = ''
            self._show_drives_root()

    def _on_path_entered(self):
        path = self._path_edit.text().strip()
        if not path:
            if sys.platform == 'win32':
                self._current_dir = ''
                self._show_drives_root()
            return
        path = os.path.normpath(path)
        if os.path.isdir(path):
            self._current_dir = path
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
        if kind == 'drive':
            if os.path.isdir(path):
                self._current_dir = path
                self._refresh_list()
        elif kind == 'network':
            self._on_network_path()
        elif kind == 'dir':
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
        if kind == 'drive':
            if os.path.isdir(path):
                self._current_dir = path
                self._refresh_list()
            return
        if kind == 'network':
            self._on_network_path()
            return
        if kind == 'dir':
            self._current_dir = path
            self._refresh_list()
            return
        self._selected_path = path
        self.accept()

    def get_selected_path(self):
        return self._selected_path
