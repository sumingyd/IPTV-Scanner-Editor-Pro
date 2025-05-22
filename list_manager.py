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
                "M3U文件 (*.m3u *.m3u8);;文本文件 (*.txt);;Excel文件 (*.xlsx);;所有文件 (*)"
            )
            
            if not file_path:
                return False
                
            if file_path.lower().endswith('.xlsx'):
                success = self.model.from_excel(file_path)
            else:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                if not content.strip():
                    return False
                    
                success = self.model.load_from_file(content)
            if success:
                return True
            else:
                self.logger.warning("LIST-文件格式可能不正确")
                return False
                
        except PermissionError as e:
            self.logger.error(f"权限不足: {str(e)}")
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
                "M3U文件 (*.m3u);;文本文件 (*.txt);;Excel文件 (*.xlsx);;所有文件 (*)"
            )
            
            if not file_path:
                return False
                
            if file_path.lower().endswith('.txt'):
                content = self.model.to_txt()
                content = f"# IPTV频道列表\n# 共 {self.model.rowCount()} 个频道\n\n{content}"
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
            elif file_path.lower().endswith('.xlsx'):
                success = self.model.to_excel(file_path)
                if not success:
                    return False
            else:
                content = self.model.to_m3u()
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                
            return True
            
        except Exception as e:
            self.logger.error(f"保存列表文件失败: {str(e)}", exc_info=True)
            return False
