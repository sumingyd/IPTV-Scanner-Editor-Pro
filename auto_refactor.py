# 自动化重构脚本 - 批量替换所有模块的方法
import re

def read_file():
    with open('pyqt_player.py', 'r', encoding='utf-8') as f:
        return f.readlines()

def write_file(lines):
    with open('pyqt_player.py', 'w', encoding='utf-8') as f:
        f.writelines(lines)

def find_method_range(lines, method_name):
    """找到方法的起始和结束行（返回0-based索引）"""
    start = None
    end = None
    
    for i, line in enumerate(lines):
        # 查找方法定义
        if re.match(rf'^\s*def {method_name}\s*\(', line):
            start = i
        # 如果已找到开始，查找下一个同级方法或类定义
        if start is not None and i > start:
            if re.match(r'^\s*def \w+\s*\(', line) or re.match(r'^class \w+', line):
                end = i - 1  # 前一行是当前方法的最后一行
                break
    
    return start, end

def replace_method(lines, method_name, new_implementation):
    """替换整个方法实现"""
    start, end = find_method_range(lines, method_name)
    
    if start is None:
        print(f"⚠️ 未找到方法: {method_name}")
        return lines
    
    print(f"📝 替换方法: {method_name} (行 {start+1}-{end+1}, 共{end-start+1}行)")
    
    # 构建新的方法
    new_lines = [f'    def {method_name}:\n']
    new_lines.append(f'        """{new_implementation["doc"]}"""\n')
    new_lines.append(f'        {new_implementation["code"]}\n')
    new_lines.append('\n')
    
    # 替换
    new_file = lines[:start] + new_lines + lines[end+1:]
    
    return new_file

# 读取文件
lines = read_file()
original_count = len(lines)
print(f"📊 原始文件: {original_count} 行")

# ========== 替换EPG相关方法 ==========
print("\n🔧 替换EPG模块方法...")

lines = replace_method(lines, 'populate_epg_list', {
    "doc": "填充EPG列表（委托给EPGController）",
    "code": "self.epg_ctrl.populate_epg_list()"
})

lines = replace_method(lines, 'on_epg_item_clicked', {
    "doc": "处理EPG列表项点击事件（委托给EPGController）",
    "code": "self.epg_ctrl.on_epg_item_clicked(item)"
})

lines = replace_method(lines, 'toggle_epg', {
    "doc": "切换EPG面板显示/隐藏（委托给EPGController）",
    "code": "self.epg_ctrl.toggle_epg(checked)"
})

lines = replace_method(lines, 'update_epg_date_display', {
    "doc": "更新EPG日期显示（委托给EPGController）",
    "code": "self.epg_ctrl.update_epg_date_display()"
})

# ========== 替换频道列表方法 ==========
print("\n🔧 替换频道列表模块方法...")

lines = replace_method(lines, 'populate_channel_list_ui', {
    "doc": "填充频道列表UI（委托给ChannelController）",
    "code": "self.channel_ctrl.populate_channel_list()"
})

lines = replace_method(lines, 'on_group_changed', {
    "doc": "处理分组切换事件（委托给ChannelController）",
    "code": "self.channel_ctrl.on_group_changed(group_name)"
})

lines = replace_method(lines, '_on_channel_selected', {
    "doc": "处理频道选择事件（委托给ChannelController）",
    "code": "self.channel_ctrl.select_channel(item)"
})

# ========== 替换设置/文件操作方法 ==========
print("\n🔧 替换设置/文件操作模块方法...")

lines = replace_method(lines, 'open_playlist', {
    "doc": "打开播放列表（委托给SettingsFileOperations）",
    "code": "self.settings_ops.open_playlist()"
})

lines = replace_method(lines, 'save_as', {
    "doc": "另存为（委托给SettingsFileOperations）",
    "code": "self.settings_ops.save_as()"
})

lines = replace_method(lines, 'player_settings', {
    "doc": "显示播放器设置对话框（委托给SettingsFileOperations）",
    "code": "self.settings_ops.player_settings()"
})

lines = replace_method(lines, 'reload_subscription', {
    "doc": "重新加载订阅源（委托给SettingsFileOperations）",
    "code": "self.settings_ops.reload_subscription()"
})

lines = replace_method(lines, 'set_language', {
    "doc": "切换语言（委托给SettingsFileOperations）",
    "code": "self.settings_ops.set_language(language)"
})

lines = replace_method(lines, 'set_theme', {
    "doc": "切换主题（委托给SettingsFileOperations）",
    "code": "self.settings_ops.set_theme(theme)"
})

lines = replace_method(lines, 'show_about', {
    "doc": "显示关于对话框（委托给SettingsFileOperations）",
    "code": "self.settings_ops.show_about()"
})

lines = replace_method(lines, 'show_usage_instructions', {
    "doc": "显示使用说明（委托给SettingsFileOperations）",
    "code": "self.settings_ops.show_usage_instructions()"
})

lines = replace_method(lines, 'save_window_layout', {
    "doc": "保存窗口布局（委托给SettingsFileOperations）",
    "code": "self.settings_ops.save_window_layout()"
})

# ========== 替换事件处理方法 ==========
print("\n🔧 替换事件处理模块方法...")

lines = replace_method(lines, 'keyPressEvent', {
    "doc": "处理键盘按键事件（委托给EventHandler）",
    "code": "if not self.event_handler.keyPressEvent(event):\n            super().keyPressEvent(event)"
})

lines = replace_method(lines, 'eventFilter', {
    "doc": "事件过滤器（委托给EventHandler）",
    "code": "return self.event_handler.eventFilter(obj, event)"
})

lines = replace_method(lines, 'showEvent', {
    "doc": "窗口显示事件（委托给EventHandler）",
    "code": "self.event_handler.showEvent(event)"
})

lines = replace_method(lines, 'changeEvent', {
    "doc": "窗口状态变化事件（委托给EventHandler）",
    "code": "self.event_handler.changeEvent(event)"
})

lines = replace_method(lines, 'moveEvent', {
    "doc": "窗口移动事件（委托给EventHandler）",
    "code": "self.event_handler.moveEvent(event)"
})

lines = replace_method(lines, 'resizeEvent', {
    "doc": "窗口大小变化事件（委托给EventHandler）",
    "code": "self.event_handler.resizeEvent(event)"
})

lines = replace_method(lines, 'closeEvent', {
    "doc": "窗口关闭事件（委托给EventHandler）",
    "code": "self.event_handler.closeEvent(event)"
})

# 写回文件
write_file(lines)

new_count = len(lines)
reduced = original_count - new_count

print(f"\n{'='*60}")
print(f"✅ 重构完成！")
print(f"   原始行数: {original_count}")
print(f"   当前行数: {new_count}")
print(f"   减少行数: {reduced} ({reduced/original_count*100:.1f}%)")
print(f"   瘦身比例: {new_count/original_count*100:.1f}%")
print(f"{'='*60}")
