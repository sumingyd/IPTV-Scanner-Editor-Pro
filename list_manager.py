from PyQt6.QtWidgets import QFileDialog
from log_manager import LogManager
from channel_model import ChannelListModel

class ListManager:
    def __init__(self, model: ChannelListModel):
        self.logger = LogManager()
        self.model = model

    def open_list(self, parent=None):
        """打开列表文件
        返回: (成功状态, 错误信息)
        """
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                parent,
                "打开列表文件", 
                "",
                "M3U文件 (*.m3u *.m3u8);;文本文件 (*.txt);;Excel文件 (*.xlsx);;所有文件 (*)"
            )
            
            if not file_path:
                return False, "用户取消选择"
                
            if file_path.lower().endswith('.xlsx'):
                success = self.model.from_excel(file_path)
            else:
                # 先尝试以二进制模式读取，检查是否是Excel文件
                with open(file_path, 'rb') as f:
                    header = f.read(4)
                    f.seek(0)
                    if header == b'PK\x03\x04':  # Excel文件头
                        content = f.read()
                        success = self.model.from_excel(file_path)
                    else:
                        # 不是Excel文件，则以文本模式读取
                        content = f.read().decode('utf-8')
                        if not content.strip():
                            return False, "文件内容为空"
                        success = self.model.load_from_file(content)
            
            if success:
                self.logger.info(f"成功加载列表文件: {file_path}")
                return True, ""
            else:
                error_msg = f"文件格式可能不正确: {file_path}"
                self.logger.warning(error_msg)
                return False, error_msg
                
        except PermissionError as e:
            error_msg = f"权限不足无法读取文件 {file_path}: {str(e)}"
            self.logger.error(error_msg)
            return False, error_msg
        except FileNotFoundError as e:
            error_msg = f"文件不存在: {file_path}"
            self.logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            import os
            file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
            error_msg = (
                f"加载列表文件失败: {file_path}\n"
                f"文件大小: {file_size}字节\n"
                f"错误详情: {str(e)}\n"
                f"异常类型: {type(e).__name__}"
            )
            self.logger.error(error_msg, exc_info=True)
            return False, error_msg

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
