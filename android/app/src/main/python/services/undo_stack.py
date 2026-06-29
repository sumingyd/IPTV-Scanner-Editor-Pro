"""撤销/重做栈 - Command 模式实现

设计：
- Command 基类定义 execute/undo/redo/description 接口
- UndoStack 管理命令历史，支持 undo/redo/clear
- 提供 AddChannel/RemoveChannel/UpdateChannel/MoveChannel 等常用命令子类
- 通过 PySide6 信号通知 UI 更新菜单状态

使用方式：
    stack = UndoStack()
    cmd = AddChannelCommand(model, channel_info)
    stack.push(cmd)  # 执行并压栈
    stack.undo()     # 撤销
    stack.redo()     # 重做
"""
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QObject, Signal

from core.log_manager import global_logger as logger


class Command:
    """命令基类"""
    def __init__(self, description: str = ''):
        self._description = description

    def execute(self) -> bool:
        """执行命令，返回是否成功"""
        return True

    def undo(self) -> bool:
        """撤销命令，返回是否成功"""
        return True

    def redo(self) -> bool:
        """重做命令（默认调用 execute）"""
        return self.execute()

    @property
    def description(self) -> str:
        return self._description or self.__class__.__name__


# 最大栈深度（避免无限增长）
_MAX_STACK_SIZE = 200


class UndoStack(QObject):
    """撤销/重做栈"""
    can_undo_changed = Signal(bool)
    can_redo_changed = Signal(bool)
    undo_text_changed = Signal(str)
    redo_text_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._undo_stack: List[Command] = []
        self._redo_stack: List[Command] = []

    def push(self, cmd: Command) -> bool:
        """执行命令并压入撤销栈，清空重做栈"""
        try:
            ok = cmd.execute()
            if not ok:
                return False
        except Exception as e:
            logger.error(f"执行命令失败: {e}")
            return False
        self._undo_stack.append(cmd)
        # 限制栈深度
        if len(self._undo_stack) > _MAX_STACK_SIZE:
            self._undo_stack.pop(0)
        self._redo_stack.clear()
        self._emit_signals()
        return True

    def undo(self) -> bool:
        if not self._undo_stack:
            return False
        cmd = self._undo_stack.pop()
        try:
            ok = cmd.undo()
        except Exception as e:
            logger.error(f"撤销命令失败: {e}")
            # 撤销失败时把命令放回栈
            self._undo_stack.append(cmd)
            return False
        if ok:
            self._redo_stack.append(cmd)
        else:
            # 撤销失败，把命令放回栈
            self._undo_stack.append(cmd)
        self._emit_signals()
        return ok

    def redo(self) -> bool:
        if not self._redo_stack:
            return False
        cmd = self._redo_stack.pop()
        try:
            ok = cmd.redo()
        except Exception as e:
            logger.error(f"重做命令失败: {e}")
            self._redo_stack.append(cmd)
            return False
        if ok:
            self._undo_stack.append(cmd)
        else:
            self._redo_stack.append(cmd)
        self._emit_signals()
        return ok

    def can_undo(self) -> bool:
        return bool(self._undo_stack)

    def can_redo(self) -> bool:
        return bool(self._redo_stack)

    def undo_text(self) -> str:
        return self._undo_stack[-1].description if self._undo_stack else ''

    def redo_text(self) -> str:
        return self._redo_stack[-1].description if self._redo_stack else ''

    def clear(self):
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._emit_signals()

    def _emit_signals(self):
        self.can_undo_changed.emit(self.can_undo())
        self.can_redo_changed.emit(self.can_redo())
        self.undo_text_changed.emit(self.undo_text())
        self.redo_text_changed.emit(self.redo_text())


# ===================== 频道相关命令 =====================

class AddChannelCommand(Command):
    """添加频道命令"""

    def __init__(self, model, channel_info: Dict[str, Any], description: str = ''):
        super().__init__(description or f"添加频道: {channel_info.get('name', '')}")
        self._model = model
        self._channel = dict(channel_info)
        self._row = -1

    def execute(self) -> bool:
        try:
            before_count = len(self._model.channels)
            self._model.add_channel(self._channel, is_from_file=False)
            after_count = len(self._model.channels)
            if after_count > before_count:
                # 新增成功，记录新增位置
                self._row = after_count - 1
                return True
            # 已存在相同URL，未新增
            return False
        except Exception as e:
            logger.error(f"AddChannelCommand execute 失败: {e}")
            return False

    def undo(self) -> bool:
        try:
            if self._row < 0 or self._row >= len(self._model.channels):
                return False
            return self._model.remove_channel(self._row)
        except Exception as e:
            logger.error(f"AddChannelCommand undo 失败: {e}")
            return False


class RemoveChannelCommand(Command):
    """删除频道命令"""

    def __init__(self, model, row: int, description: str = ''):
        self._model = model
        self._row = row
        self._channel: Optional[Dict[str, Any]] = None
        name = ''
        try:
            if 0 <= row < len(model.channels):
                name = model.channels[row].get('name', '')
        except Exception:
            pass
        super().__init__(description or f"删除频道: {name}")

    def execute(self) -> bool:
        try:
            if not (0 <= self._row < len(self._model.channels)):
                return False
            self._channel = dict(self._model.channels[self._row])
            return self._model.remove_channel(self._row)
        except Exception as e:
            logger.error(f"RemoveChannelCommand execute 失败: {e}")
            return False

    def undo(self) -> bool:
        try:
            if not self._channel:
                return False
            before_count = len(self._model.channels)
            self._model.add_channel(self._channel, is_from_file=False)
            after_count = len(self._model.channels)
            if after_count > before_count:
                # 重新插入到原位置（如果可能）
                new_row = after_count - 1
                if new_row != self._row and 0 <= self._row <= after_count - 1:
                    try:
                        # 移动到原位置
                        ch = self._model.channels.pop(new_row)
                        self._model.beginResetRows()
                        self._model.channels.insert(self._row, ch)
                        self._model.endResetRows()
                    except Exception:
                        pass
                return True
            return False
        except Exception as e:
            logger.error(f"RemoveChannelCommand undo 失败: {e}")
            return False


class UpdateChannelCommand(Command):
    """更新频道命令"""

    def __init__(self, model, index: int, new_channel: Dict[str, Any], description: str = ''):
        self._model = model
        self._index = index
        self._new_channel = dict(new_channel)
        self._old_channel: Optional[Dict[str, Any]] = None
        name = new_channel.get('name', '')
        super().__init__(description or f"更新频道: {name}")

    def execute(self) -> bool:
        try:
            if not (0 <= self._index < len(self._model.channels)):
                return False
            # 保存旧值（深拷贝）
            self._old_channel = dict(self._model.channels[self._index])
            return self._model.update_channel(self._index, self._new_channel)
        except Exception as e:
            logger.error(f"UpdateChannelCommand execute 失败: {e}")
            return False

    def undo(self) -> bool:
        try:
            if not self._old_channel:
                return False
            return self._model.update_channel(self._index, self._old_channel)
        except Exception as e:
            logger.error(f"UpdateChannelCommand undo 失败: {e}")
            return False


class BatchCommand(Command):
    """批量命令组合（原子操作）"""

    def __init__(self, commands: List[Command], description: str = ''):
        super().__init__(description or f"批量操作 ({len(commands)} 项)")
        self._commands = list(commands)

    def execute(self) -> bool:
        executed = []
        for cmd in self._commands:
            try:
                if cmd.execute():
                    executed.append(cmd)
                else:
                    # 失败则回滚已执行的
                    for done in reversed(executed):
                        try:
                            done.undo()
                        except Exception:
                            pass
                    return False
            except Exception as e:
                logger.error(f"BatchCommand execute 失败: {e}")
                for done in reversed(executed):
                    try:
                        done.undo()
                    except Exception:
                        pass
                return False
        return True

    def undo(self) -> bool:
        # 按相反顺序撤销
        for cmd in reversed(self._commands):
            try:
                cmd.undo()
            except Exception as e:
                logger.error(f"BatchCommand undo 失败: {e}")
                return False
        return True

    def redo(self) -> bool:
        for cmd in self._commands:
            try:
                cmd.redo()
            except Exception as e:
                logger.error(f"BatchCommand redo 失败: {e}")
                return False
        return True
