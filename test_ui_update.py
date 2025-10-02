#!/usr/bin/env python3
"""
测试UI更新功能 - 验证单个频道添加和重新获取频道信息时UI是否实时更新
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

def test_single_channel_add():
    """测试单个频道添加时UI是否更新"""
    print("测试单个频道添加...")
    
    # 创建测试主窗口
    main_window = TestMainWindow()
    
    # 添加单个测试频道
    test_channel = {
        'url': 'http://example.com/test1.m3u8',
        'name': '测试频道1',
        'raw_name': '测试频道1',
        'valid': True,
        'latency': 100,
        'resolution': '1920x1080',
        'status': '有效',
        'group': '测试分组',
        'logo_url': 'http://example.com/logo1.png'
    }
    
    print(f"添加测试频道: {test_channel['name']}")
    main_window.model.add_channel(test_channel)
    
    # 检查频道是否添加成功
    channel_count = main_window.model.rowCount()
    print(f"频道数量: {channel_count}")
    
    if channel_count == 0:
        print("❌ 频道添加失败")
        return False
    
    # 强制刷新UI
    print("强制刷新UI...")
    main_window.model.update_view()
    
    # 检查视图是否更新
    if hasattr(main_window.channel_list, 'viewport_called') and main_window.channel_list.viewport_called:
        print("✅ 单个频道添加时UI更新成功")
        return True
    else:
        print("❌ 单个频道添加时UI更新失败")
        return False

def test_refresh_channel_info():
    """测试重新获取频道信息时UI是否更新"""
    print("\n测试重新获取频道信息...")
    
    # 创建测试主窗口
    main_window = TestMainWindow()
    
    # 添加一个测试频道
    test_channel = {
        'url': 'http://example.com/test2.m3u8',
        'name': '测试频道2',
        'raw_name': '测试频道2',
        'valid': True,
        'latency': 100,
        'resolution': '1920x1080',
        'status': '有效',
        'group': '测试分组',
        'logo_url': 'http://example.com/logo2.png'
    }
    
    print(f"添加测试频道: {test_channel['name']}")
    main_window.model.add_channel(test_channel)
    
    # 模拟重新获取频道信息
    print("模拟重新获取频道信息...")
    
    # 创建新的频道信息（模拟重新获取后的结果）
    new_channel_info = {
        'url': 'http://example.com/test2.m3u8',
        'name': '更新后的测试频道2',
        'raw_name': '更新后的测试频道2',
        'valid': True,
        'latency': 50,
        'resolution': '1280x720',
        'status': '有效',
        'group': '更新后的分组',
        'logo_url': 'http://example.com/new_logo2.png'
    }
    
    # 直接调用模型更新方法
    success = main_window.model.update_channel(0, new_channel_info)
    
    if success:
        print("✅ 频道信息更新成功")
        
        # 检查更新后的频道信息
        updated_channel = main_window.model.get_channel(0)
        print(f"更新后的频道信息: {updated_channel['name']}")
        
        # 强制刷新UI
        print("强制刷新UI...")
        main_window.model.update_view()
        
        # 检查视图是否更新
        if hasattr(main_window.channel_list, 'viewport_called') and main_window.channel_list.viewport_called:
            print("✅ 重新获取频道信息时UI更新成功")
            return True
        else:
            print("❌ 重新获取频道信息时UI更新失败")
            return False
    else:
        print("❌ 频道信息更新失败")
        return False

def test_batch_channel_add():
    """测试批量频道添加时UI是否更新"""
    print("\n测试批量频道添加...")
    
    # 创建测试主窗口
    main_window = TestMainWindow()
    
    # 添加多个测试频道
    channels = []
    for i in range(3):
        channel = {
            'url': f'http://example.com/batch{i}.m3u8',
            'name': f'批量频道{i}',
            'raw_name': f'批量频道{i}',
            'valid': True,
            'latency': 100 + i,
            'resolution': '1920x1080',
            'status': '有效',
            'group': '批量分组',
            'logo_url': f'http://example.com/logo_batch{i}.png'
        }
        channels.append(channel)
    
    print(f"批量添加 {len(channels)} 个频道")
    main_window.model.add_channel({'batch': True, 'channels': channels})
    
    # 检查频道是否添加成功
    channel_count = main_window.model.rowCount()
    print(f"频道数量: {channel_count}")
    
    if channel_count != len(channels):
        print("❌ 批量频道添加失败")
        return False
    
    # 强制刷新UI
    print("强制刷新UI...")
    main_window.model.update_view()
    
    # 检查视图是否更新
    if hasattr(main_window.channel_list, 'viewport_called') and main_window.channel_list.viewport_called:
        print("✅ 批量频道添加时UI更新成功")
        return True
    else:
        print("❌ 批量频道添加时UI更新失败")
        return False

def main():
    """主测试函数"""
    print("开始测试UI更新功能...")
    
    # 创建QApplication实例（PyQt6需要）
    app = QtWidgets.QApplication(sys.argv)
    
    # 测试单个频道添加
    test1_success = test_single_channel_add()
    
    # 测试重新获取频道信息
    test2_success = test_refresh_channel_info()
    
    # 测试批量频道添加
    test3_success = test_batch_channel_add()
    
    # 总结测试结果
    print("\n" + "="*50)
    print("测试结果总结:")
    print(f"单个频道添加UI更新: {'✅ 通过' if test1_success else '❌ 失败'}")
    print(f"重新获取频道信息UI更新: {'✅ 通过' if test2_success else '❌ 失败'}")
    print(f"批量频道添加UI更新: {'✅ 通过' if test3_success else '❌ 失败'}")
    
    if test1_success and test2_success and test3_success:
        print("\n🎉 所有UI更新测试通过！")
    else:
        print("\n⚠️ 部分UI更新测试失败")
    
    # 清理QApplication
    app.quit()

if __name__ == "__main__":
    main()
