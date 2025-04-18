from PyQt6.QtWidgets import QFileDialog
from log_manager import LogManager
from channel_model import ChannelListModel

class ListManager:
    def __init__(self, model: ChannelListModel):
        self.logger = LogManager()
        self.model = model

    def open_list(self, parent=None):
        """打开列表文件"""
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                parent,
                "打开列表文件", 
                "",
                "M3U文件 (*.m3u *.m3u8);;文本文件 (*.txt);;所有文件 (*)"
            )
            if not file_path:
                self.logger.debug("用户取消选择文件")
                return False
                
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if not content.strip():
                self.logger.warning("文件内容为空")
                return False
                
            success = self.model.load_from_file(content)
            if success:
                self.logger.info(f"成功加载列表文件: {file_path}")
                self.logger.debug(f"加载频道数: {self.model.rowCount()}")
                return True
            else:
                self.logger.warning("文件格式可能不正确")
                return False
                
        except Exception as e:
            self.logger.error(f"加载列表文件失败: {str(e)}", exc_info=True)
            return False

    def save_list(self, parent=None):
        """保存列表文件"""
        try:
            file_path, _ = QFileDialog.getSaveFileName(
                parent,
                "保存列表文件",
                "",
                "M3U文件 (*.m3u);;文本文件 (*.txt);;所有文件 (*)"
            )
            if not file_path:
                self.logger.debug("用户取消保存文件")
                return False
                
            content = self.model.to_m3u()
            if not content.strip():
                self.logger.warning("没有内容可保存")
                return False
                
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
                
            self.logger.info(f"成功保存列表文件: {file_path}")
            self.logger.debug(f"保存频道数: {self.model.rowCount()}")
            return True
            
        except Exception as e:
            self.logger.error(f"保存列表文件失败: {str(e)}", exc_info=True)
            return False
