"""文件队列控制器 - 管理播放队列模式（循环/随机）+ AB循环 + 逐帧"""
import random
from typing import Optional

from PySide6.QtCore import QObject, QTimer, Signal

from core.log_manager import global_logger as logger


class FileQueueController(QObject):
    """文件队列与播放控制控制器
    队列模式：
      'none'    - 不循环，文件结束后停止
      'single'  - 单文件循环（mpv loop-file='inf'）
      'all'     - 列表循环（顺序播放下一文件）
      'shuffle' - 随机播放
    """

    # 队列模式变更信号
    queue_mode_changed = Signal(str)

    QUEUE_MODES = ('none', 'single', 'all', 'shuffle')

    def __init__(self, main_window):
        super().__init__()
        self.window = main_window
        self._queue_mode = 'none'
        self._shuffle_history = []  # 记录随机播放历史，避免短期重复
        self._shuffle_history_max = 50

        pc = main_window.player_controller
        if pc and hasattr(pc, 'local_file_ended'):
            pc.local_file_ended.connect(self._on_local_file_ended)

    @property
    def queue_mode(self) -> str:
        return self._queue_mode

    def set_queue_mode(self, mode: str):
        """设置队列模式"""
        if mode not in self.QUEUE_MODES:
            return
        old = self._queue_mode
        self._queue_mode = mode
        logger.info(f"队列模式: {old} -> {mode}")

        # 同步 mpv loop-file 属性
        pc = self.window.player_controller
        if pc and hasattr(pc, 'set_loop_file'):
            if mode == 'single':
                pc.set_loop_file('inf')
            else:
                pc.set_loop_file('no')

        # 持久化
        try:
            cfg = self.window.config.load_playback_settings()
            cfg['queue_mode'] = mode
            self.window.config.save_playback_settings(cfg)
        except Exception as e:
            logger.debug(f"持久化队列模式失败: {e}")

        self.queue_mode_changed.emit(mode)

    def cycle_queue_mode(self) -> str:
        """循环切换队列模式：none -> single -> all -> shuffle -> none"""
        idx = self.QUEUE_MODES.index(self._queue_mode)
        new_mode = self.QUEUE_MODES[(idx + 1) % len(self.QUEUE_MODES)]
        self.set_queue_mode(new_mode)
        return new_mode

    def is_shuffle(self) -> bool:
        return self._queue_mode == 'shuffle'

    def toggle_shuffle(self) -> bool:
        """切换随机播放开关"""
        new_mode = 'shuffle' if self._queue_mode != 'shuffle' else 'none'
        self.set_queue_mode(new_mode)
        return self.is_shuffle()

    def load_from_config(self):
        """启动时从配置加载队列模式"""
        try:
            cfg = self.window.config.load_playback_settings()
            mode = cfg.get('queue_mode', 'none')
            if mode in self.QUEUE_MODES:
                self._queue_mode = mode
                # 同步 mpv loop-file
                pc = self.window.player_controller
                if pc and hasattr(pc, 'set_loop_file'):
                    if mode == 'single':
                        pc.set_loop_file('inf')
                    else:
                        pc.set_loop_file('no')
                logger.info(f"从配置加载队列模式: {mode}")
        except Exception as e:
            logger.debug(f"加载队列模式失败: {e}")

    # ---------- 文件结束自动续播 ----------
    def _on_local_file_ended(self, ended_url: str):
        """本地文件播放结束时的回调"""
        if self._queue_mode == 'none':
            return
        if self._queue_mode == 'single':
            # 单文件循环由 mpv loop-file 处理，不应到这里
            return

        # 延迟一点避免与 END_FILE 处理冲突
        QTimer.singleShot(300, lambda: self._play_next_file(ended_url))

    def _play_next_file(self, ended_url: str):
        """播放下一个文件"""
        channels = self._get_local_channels()
        if not channels:
            return

        current_idx = self._find_current_index(channels, ended_url)
        if current_idx < 0:
            return

        if self._queue_mode == 'all':
            next_idx = (current_idx + 1) % len(channels)
        elif self._queue_mode == 'shuffle':
            next_idx = self._pick_random_index(len(channels), current_idx)
        else:
            return

        if next_idx == current_idx and len(channels) == 1:
            # 只有一个文件，重新播放
            channel = channels[current_idx]
            self._replay_channel(channel)
            return

        channel = channels[next_idx]
        # 更新 UI 选中项
        self._select_channel_in_list(next_idx)
        # 播放
        QTimer.singleShot(100, lambda: self.window.play_channel(channel))

    def _replay_channel(self, channel: dict):
        """重新播放同一频道"""
        try:
            QTimer.singleShot(100, lambda: self.window.play_channel(channel))
        except Exception as e:
            logger.debug(f"重新播放失败: {e}")

    def _get_local_channels(self) -> list:
        """获取本地频道列表（即文件队列）"""
        channels = getattr(self.window, '_local_channels', None)
        if channels and isinstance(channels, list):
            return channels
        return []

    def _find_current_index(self, channels: list, url: str) -> int:
        """根据 URL 找到当前频道的索引"""
        if not url:
            # 回退到 current_channel
            cur = getattr(self.window, 'current_channel', None)
            if cur and isinstance(cur, dict):
                url = cur.get('url', '')
        if not url:
            return -1
        for i, ch in enumerate(channels):
            if isinstance(ch, dict) and ch.get('url') == url:
                return i
        return -1

    def _pick_random_index(self, total: int, current_idx: int) -> int:
        """随机选择一个索引，避免短期重复"""
        if total <= 1:
            return 0
        # 清理过长的历史
        if len(self._shuffle_history) > self._shuffle_history_max:
            self._shuffle_history = self._shuffle_history[-self._shuffle_history_max // 2:]
        # 尝试找到一个不在近期历史中的索引
        candidates = [i for i in range(total) if i != current_idx and i not in self._shuffle_history]
        if not candidates:
            candidates = [i for i in range(total) if i != current_idx]
        if not candidates:
            return current_idx
        idx = random.choice(candidates)
        self._shuffle_history.append(idx)
        return idx

    def _select_channel_in_list(self, idx: int):
        """在 local_channel_list UI 中选中指定索引的项"""
        try:
            cl = getattr(self.window, 'local_channel_list', None)
            if cl and 0 <= idx < cl.count():
                item = cl.item(idx)
                if item:
                    cl.setCurrentItem(item)
        except Exception as e:
            logger.debug(f"选中列表项失败: {e}")

    # ---------- 上一文件 / 下一文件 ----------
    def play_next(self):
        """播放下一个文件"""
        channels = self._get_local_channels()
        if not channels:
            return
        cur = getattr(self.window, 'current_channel', None)
        cur_url = cur.get('url', '') if cur and isinstance(cur, dict) else ''
        idx = self._find_current_index(channels, cur_url)
        if idx < 0:
            idx = 0
        else:
            idx = (idx + 1) % len(channels)
        self._select_channel_in_list(idx)
        channel = channels[idx]
        QTimer.singleShot(100, lambda: self.window.play_channel(channel))

    def play_previous(self):
        """播放上一个文件"""
        channels = self._get_local_channels()
        if not channels:
            return
        cur = getattr(self.window, 'current_channel', None)
        cur_url = cur.get('url', '') if cur and isinstance(cur, dict) else ''
        idx = self._find_current_index(channels, cur_url)
        if idx < 0:
            idx = 0
        else:
            idx = (idx - 1) % len(channels)
        self._select_channel_in_list(idx)
        channel = channels[idx]
        QTimer.singleShot(100, lambda: self.window.play_channel(channel))

    # ---------- AB 循环 ----------
    def ab_loop_set_a(self) -> Optional[float]:
        """设置 A 点"""
        pc = self.window.player_controller
        if not pc or not pc.is_playing or not hasattr(pc, 'ab_loop_set_a'):
            return None
        pos = pc.ab_loop_set_a()
        tr = self.window.language_manager.tr
        if hasattr(self.window, '_show_osd_feedback'):
            self.window._show_osd_feedback(f"{tr('ab_loop_a', 'A-B Loop A')}: {pos:.2f}s")
        return pos

    def ab_loop_set_b(self) -> Optional[float]:
        """设置 B 点"""
        pc = self.window.player_controller
        if not pc or not pc.is_playing or not hasattr(pc, 'ab_loop_set_b'):
            return None
        pos = pc.ab_loop_set_b()
        tr = self.window.language_manager.tr
        if hasattr(self.window, '_show_osd_feedback'):
            self.window._show_osd_feedback(f"{tr('ab_loop_b', 'A-B Loop B')}: {pos:.2f}s")
        return pos

    def ab_loop_clear(self):
        """清除 AB 循环"""
        pc = self.window.player_controller
        if not pc or not hasattr(pc, 'ab_loop_clear'):
            return
        pc.ab_loop_clear()
        tr = self.window.language_manager.tr
        if hasattr(self.window, '_show_osd_feedback'):
            self.window._show_osd_feedback(tr('ab_loop_cleared', 'A-B Loop cleared'))

    def get_ab_loop_status(self) -> dict:
        pc = self.window.player_controller
        if not pc or not hasattr(pc, 'ab_loop_get_status'):
            return {'a': None, 'b': None, 'active': False}
        return pc.ab_loop_get_status()

    # ---------- 逐帧播放 ----------
    def frame_step(self):
        """前进一帧"""
        pc = self.window.player_controller
        if not pc or not pc.is_playing or not hasattr(pc, 'frame_step'):
            return
        pc.frame_step()

    def frame_back_step(self):
        """后退一帧"""
        pc = self.window.player_controller
        if not pc or not pc.is_playing or not hasattr(pc, 'frame_back_step'):
            return
        pc.frame_back_step()
