import sys, os
msg_map = {'fix-previous-channel-save-and-type-check': '修复: 回切功能双重BUG - 先保存旧频道再赋新值 修正UserRole类型判断', 'fix-mpv-get-property-string-memleak-and-wakeup-callback-gc': '修复: mpv_get_property_string内存泄漏和wakeup回调GC回收', 'fix-restart-event-timer-on-play-after-stop': '修复: stop后play不重启event_timer导致MPV事件不再处理', 'fix-lazy-init-theme-manager-after-QApplication': '修复: ThemeManager延迟初始化避免QApplication前创建QObject', 'fix-osd-visible-init-show-message-typo-userrole-compare-space-shortcut-gc': '修复: _osd_visible未初始化 show_message拼写 UserRole类型比较 空格快捷键GC', 'fix-beginResetModel-nested-beginInsertRows-in-load-from-file': '修复: load_from_file中beginResetModel嵌套beginInsertRows', 'fix-panel-visibility-thread-safety-and-config-zero-value-bug': '修复: PanelVisibility线程安全加锁和配置值0被误判为空'}
commit = os.environ.get('GIT_COMMIT', '')
msg = sys.stdin.read().strip()
for old, new in msg_map.items():
    if msg == old:
        print(new)
        sys.exit(0)
print(msg)
