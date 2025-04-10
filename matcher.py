from difflib import SequenceMatcher
from PyQt6.QtCore import QObject, pyqtSignal
from async_utils import AsyncWorker
from channel_model import ChannelListModel

class ChannelMatcher(QObject):
    match_progress = pyqtSignal(int)
    match_finished = pyqtSignal(list)
    error_occurred = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.worker = None

    def match_channels(self, source_list, target_list):
        """智能匹配两个频道列表"""
        try:
            if not source_list or not target_list:
                raise ValueError("源列表或目标列表为空")

            # 创建匹配工作线程
            self.worker = AsyncWorker(self._do_matching, source_list, target_list)
            self.worker.progress_updated.connect(self.match_progress)
            self.worker.finished.connect(self._on_matching_finished)
            self.worker.error_occurred.connect(self.error_occurred)
            self.worker.start()
            
        except Exception as e:
            self.error_occurred.emit(f"匹配错误: {str(e)}")

    def _do_matching(self, source_list, target_list, progress_callback):
        """执行实际的匹配算法"""
        matched_pairs = []
        total = len(source_list)
        
        for i, source_ch in enumerate(source_list):
            best_match = None
            best_score = 0
            
            for target_ch in target_list:
                # 计算相似度分数
                name_score = SequenceMatcher(
                    None, 
                source_ch['name'].lower(), 
                target_ch['name'].lower()
                ).ratio()
                
                url_score = SequenceMatcher(
                    None,
                    source_ch.url.lower(),
                    target_ch.url.lower()
                ).ratio()
                
                # 综合评分
                total_score = (name_score * 0.7) + (url_score * 0.3)
                
                if total_score > best_score:
                    best_score = total_score
                    best_match = target_ch
            
            if best_match and best_score > 0.6:  # 相似度阈值
                matched_pairs.append((source_ch, best_match, best_score))
            
            progress_callback(int((i + 1) / total * 100))
        
        return matched_pairs

    def _on_matching_finished(self, result):
        """匹配完成处理"""
        self.match_finished.emit(result)
        self.worker = None
