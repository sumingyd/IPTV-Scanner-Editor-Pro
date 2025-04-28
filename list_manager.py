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
                return False
                
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if not content.strip():
                self.logger.warning("文件内容为空")
                return False
                
            success = self.model.load_from_file(content)
            if success:
                return True
            else:
                self.logger.warning("文件格式可能不正确")
                return False
                
        except PermissionError as e:
            self.logger.error(f"权限不足: {str(e)}")
            return False
        except Exception as e:
            self.logger.error(f"加载列表文件失败: {str(e)}", exc_info=True)
            return False

    def load_old_list(self, file_path):
        """加载旧列表文件到内存"""
        try:
            if not file_path:
                return None
                
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if not content.strip():
                self.logger.warning("文件内容为空")
                return None
                
            channels = self.model.parse_file_content(content)
            if channels:
                return channels
            else:
                self.logger.warning("文件格式可能不正确")
                return None
                
        except PermissionError as e:
            self.logger.error(f"权限不足: {str(e)}")
            return None
        except Exception as e:
            self.logger.error(f"加载旧列表失败: {str(e)}", exc_info=True)
            return None

    def load_m3u(self, file_path):
        """加载M3U格式的旧列表文件"""
        return self.load_old_list(file_path)

    def match_channels(self, old_channels, current_model, progress_callback=None):
        """匹配新旧频道列表"""
        try:
            matched_count = 0
            
            for i, old_ch in enumerate(old_channels):
                for j in range(current_model.rowCount()):
                    current_ch = current_model.get_channel(j)
                    # 规范化URL后比较
                    old_url = old_ch.get('url', '').strip().lower()
                    current_url = current_ch.get('url', '').strip().lower()
                    if old_url and current_url and old_url == current_url:
                        matched_count += 1
                        # 更新当前频道信息
                        current_ch.update({
                            'name': old_ch.get('name', current_ch.get('name')),
                            'group': old_ch.get('group', current_ch.get('group')),
                            'tvg_id': old_ch.get('tvg_id', current_ch.get('tvg_id', '')),
                            'logo': old_ch.get('logo', current_ch.get('logo', '')),
                            'language': old_ch.get('language', current_ch.get('language', '')),
                            'country': old_ch.get('country', current_ch.get('country', ''))
                        })
                        # 通知模型更新
                        index = current_model.index(j, 0)
                        current_model.dataChanged.emit(index, index)
                
                # 更新进度
                if progress_callback:
                    progress_callback(i + 1, len(old_channels))
            
            return matched_count
            
        except Exception as e:
            self.logger.error(f"匹配频道失败: {str(e)}", exc_info=True)
            return 0

    def count_matched_channels(self, old_channels, current_model):
        """统计已匹配的频道数量"""
        try:
            matched_count = 0
            for old_ch in old_channels:
                for j in range(current_model.rowCount()):
                    current_ch = current_model.get_channel(j)
                    old_url = old_ch.get('url', '').strip().lower()
                    current_url = current_ch.get('url', '').strip().lower()
                    if old_url and current_url and old_url == current_url:
                        matched_count += 1
                        break
            return matched_count
        except Exception as e:
            return 0

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
                return False
                
            if file_path.lower().endswith('.txt'):
                content = self.model.to_txt()
                content = f"# IPTV频道列表\n# 共 {self.model.rowCount()} 个频道\n\n{content}"
            else:
                content = self.model.to_m3u()
            
            if not content.strip():
                self.logger.warning("没有内容可保存")
                return False
                
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
                
            return True
            
        except Exception as e:
            self.logger.error(f"保存列表文件失败: {str(e)}", exc_info=True)
            return False
