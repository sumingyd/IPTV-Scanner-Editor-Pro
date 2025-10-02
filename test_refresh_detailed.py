#!/usr/bin/env python3
"""
详细测试重新获取频道信息功能 - 模拟实际应用场景
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

from PyQt6 import QtWidgets, QtCore
from channel_model import ChannelListModel
from ui_builder import UIBuilder
import time

class TestMainWindow:
    """测试主窗口类"""
    def __init__(self):
        self.model = ChannelListModel()
        self.ui = UIBuilder(self)
        self.config = MockConfig()
        self.language_manager = MockLanguageManager()
        self.statusBar = MockStatusBar()
        self.progress_indicator = MockProgressBar()
        self.channel_list = MockTableView()
        # 关键：将模型设置到视图中
        self.channel_list.setModel(self.model)
        
    def _update_validate_status(self, text):
        print(f"状态更新: {text}")

class MockConfig:
    """模拟配置类"""
    def load_window_layout(self):
        return 800, 600, [400, 400, 300, 300, 500, 200]
    
    def save_window_layout(self, width, height, dividers):
        pass

class MockLanguageManager:
    """模拟语言管理器"""
    def tr(self, key, default):
        return default

class MockStatusBar:
    """模拟状态栏"""
    def showMessage(self, message, timeout=0):
        print(f"状态栏: {message}")

class MockProgressBar:
    """模拟进度条"""
    def __init__(self):
        self.visible = False
        self.value = 0
        
    def show(self):
        self.visible = True
        print("进度条显示")
        
    def hide(self):
        self.visible = False
        print("进度条隐藏")
        
    def setValue(self, value):
        self.value = value
        print(f"进度条值: {value}%")

class MockTableView:
    """模拟表格视图"""
    def __init__(self):
        self.viewport_called = False
        self.resize_called = False
        self.repaint_called = False
        self.data_changed_called = False
        self.layout_changed_called = False
        
    def viewport(self):
        return self
        
    def update(self):
        self.viewport_called = True
        print("✅ 视图更新调用成功")
        
    def repaint(self):
        self.repaint_called = True
        print("✅ 重绘调用成功")
        
    def horizontalHeader(self):
        return self
        
    def resizeSections(self, mode):
        self.resize_called = True
        print("✅ 列宽调整调用成功")
        
    def setModel(self, model):
        self.model = model
        # 监听模型信号
        model.dataChanged.connect(self._on_data_changed)
        model.layoutChanged.connect(self._on_layout_changed)
        
    def _on_data_changed(self, top_left, bottom_right, roles):
        self.data_changed_called = True
        print(f"✅ 数据变化信号: 行 {top_left.row()}-{bottom_right.row()}, 列 {top_left.column()}-{bottom_right.column()}")
        
    def _on_layout_changed(self):
        self.layout_changed_called = True
        print("✅ 布局变化信号")

def test_refresh_channel_detailed():
    """详细测试重新获取频道信息功能"""
    print("详细测试重新获取频道信息功能...")
    
    # 创建测试主窗口
    main_window = TestMainWindow()
    
    # 添加一个测试频道
    test_channel = {
        'url': 'http://example.com/test.m3u8',
        'name': '测试频道',
        'raw_name': '测试频道',
        'valid': True,
        'latency': 100,
        'resolution': '1920x1080',
        'status': '有效',
        'group': '测试分组',
        'logo_url': 'http://example.com/logo.png'
    }
    
    print(f"添加测试频道: {test_channel['name']}")
    main_window.model.add_channel(test_channel)
    
    # 检查频道是否添加成功
    channel_count = main_window.model.rowCount()
    print(f"频道数量: {channel_count}")
    
    if channel_count == 0:
        print("❌ 频道添加失败")
        return False
    
    # 检查原始频道信息
    original_channel = main_window.model.get_channel(0)
    print(f"原始频道信息: {original_channel}")
    
    # 模拟重新获取频道信息
    print("\n模拟重新获取频道信息...")
    
    # 创建新的频道信息（模拟重新获取后的结果）
    new_channel_info = {
        'url': 'http://example.com/test.m3u8',
        'name': '更新后的测试频道',
        'raw_name': '更新后的测试频道',
        'valid': True,
        'latency': 50,
        'resolution': '1280x720',
        'status': '有效',
        'group': '更新后的分组',
        'logo_url': 'http://example.com/new_logo.png'
    }
    
    # 直接调用模型更新方法
    print("调用 update_channel 方法...")
    success = main_window.model.update_channel(0, new_channel_info)
    
    if success:
        print("✅ 频道信息更新成功")
        
        # 检查更新后的频道信息
        updated_channel = main_window.model.get_channel(0)
        print(f"更新后的频道信息: {updated_channel}")
        
        # 检查信号是否触发
        print(f"\n信号触发情况:")
        print(f"数据变化信号: {main_window.channel_list.data_changed_called}")
        print(f"布局变化信号: {main_window.channel_list.layout_changed_called}")
        print(f"视图更新: {main_window.channel_list.viewport_called}")
        print(f"重绘: {main_window.channel_list.repaint_called}")
        print(f"列宽调整: {main_window.channel_list.resize_called}")
        
        # 验证更新是否成功
        if updated_channel['name'] == '更新后的测试频道':
            print("✅ 频道信息更新验证成功")
            return True
        else:
            print("❌ 频道信息更新验证失败")
            return False
    else:
        print("❌ 频道信息更新失败")
        return False

def main():
    """主测试函数"""
    print("开始详细测试重新获取频道信息功能...")
    
    # 创建QApplication实例（PyQt6需要）
    app = QtWidgets.QApplication(sys.argv)
    
    # 测试重新获取频道信息功能
    success = test_refresh_channel_detailed()
    
    if success:
        print("\n🎉 详细测试通过！重新获取频道信息功能正常工作")
    else:
        print("\n⚠️ 详细测试失败")
    
    # 清理QApplication
    app.quit()

if __name__ == "__main__":
    main()
