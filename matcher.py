import asyncio
from difflib import SequenceMatcher
from PyQt6.QtCore import QObject, pyqtSignal, Qt
from PyQt6.QtGui import QColor
from async_utils import AsyncWorker
from typing import Dict, List, Optional

class ChannelMatcher(QObject):
    match_progress = pyqtSignal(int)  # 进度百分比
    match_status = pyqtSignal(str)    # 状态文本
    match_finished = pyqtSignal()     # 完成信号
    error_occurred = pyqtSignal(str)  # 错误信号

    def __init__(self, epg_manager=None, parent=None):
        super().__init__(parent)
        self.worker: Optional[AsyncWorker] = None
        self.epg_manager = epg_manager
        self.old_playlist: Dict[str, Dict] = {}

    def load_old_playlist(self, playlist: Dict[str, Dict]):
        """加载旧播放列表"""
        self.old_playlist = playlist

    async def auto_match(self, channels: List[Dict]) -> List[Dict]:
        """执行自动匹配(旧列表+EPG)"""
        if not channels:
            raise ValueError("频道列表为空")

        total = len(channels)
        matched_count = 0
        
        for row in range(total):
            chan = channels[row]
            
            # 1. 匹配旧列表
            if chan['url'] in self.old_playlist:
                old_chan = self.old_playlist[chan['url']]
                chan['old_name'] = chan['name']  # 保留原始名称
                chan['name'] = old_chan['name']  # 更新为新名称
                matched_count += 1
            
            # 2. 匹配EPG (如果有epg_manager)
            if self.epg_manager:
                epg_names = self.epg_manager.match_channel_name(chan.get('name', ''))
                if epg_names:
                    chan['epg_name'] = chan['name']  # 保留原始名称
                    chan['name'] = epg_names[0]      # 更新为EPG名称
                    matched_count += 1
            
            # 更新进度
            progress = int((row + 1) / total * 100)
            self.match_progress.emit(progress)
            self.match_status.emit(f"匹配中: {row+1}/{total} ({progress}%)")
            await asyncio.sleep(0)  # 释放事件循环
        
        # 统计结果
        old_matched = sum(1 for chan in channels if 'old_name' in chan)
        epg_matched = sum(1 for chan in channels if 'epg_name' in chan)
        conflict_count = sum(1 for chan in channels 
                           if 'old_name' in chan and 'epg_name' in chan 
                           and chan['old_name'] != chan['epg_name'])
        
        stats = (f"✔ 匹配完成\n"
                f"• 共匹配 {matched_count}/{total} 个频道\n"
                f"• 旧列表匹配: {old_matched}\n"
                f"• EPG匹配: {epg_matched}\n"
                f"• 冲突: {conflict_count}")
        
        self.match_status.emit(stats)
        self.match_finished.emit()
        return channels

    def get_match_color(self, channel: Dict) -> Optional[QColor]:
        """获取匹配结果对应的背景色"""
        if 'old_name' in channel:
            return QColor(255, 255, 200)  # 浅黄：旧列表匹配
        elif 'epg_name' in channel:
            is_conflict = ('old_name' in channel and 
                         channel['epg_name'] != channel['old_name'])
            return QColor(255, 200, 200) if is_conflict else QColor(200, 255, 200)
        return None

    def _do_matching(self, source_list, target_list, progress_callback):
        """保留原有的通用匹配算法"""
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
                    source_ch['url'].lower(),
                    target_ch['url'].lower()
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
