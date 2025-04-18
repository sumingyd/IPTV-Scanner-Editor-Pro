from PyQt6.QtWidgets import QFileDialog
from log_manager import LogManager
from channel_model import ChannelListModel

class ListManager:
    def __init__(self, model: ChannelListModel):
        self.logger = LogManager()
        self.model = model

    def open_list(self, parent=None):
        """打开列表文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            parent,
            "打开列表文件", 
            "",
            "M3U文件 (*.m3u *.m3u8);;文本文件 (*.txt);;所有文件 (*)"
        )
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                self.model.load_from_file(content)
                self.logger.info(f"成功加载列表文件: {file_path}")
                return True
            except Exception as e:
                self.logger.error(f"加载列表文件失败: {e}")
                return False
        return False

    def save_list(self, parent=None):
        """保存列表文件"""
        file_path, _ = QFileDialog.getSaveFileName(
            parent,
            "保存列表文件",
            "",
            "M3U文件 (*.m3u);;文本文件 (*.txt);;所有文件 (*)"
        )
        if file_path:
            try:
                content = self.model.to_m3u()
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                self.logger.info(f"成功保存列表文件: {file_path}")
                return True
            except Exception as e:
                self.logger.error(f"保存列表文件失败: {e}")
                return False
        return False
