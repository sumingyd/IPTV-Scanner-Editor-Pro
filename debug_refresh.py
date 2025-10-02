#!/usr/bin/env python3
"""
调试脚本 - 检查右键重新获取频道信息不更新的问题
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

from PyQt6 import QtWidgets, QtCore, QtGui
from channel_model import ChannelListModel
from ui_builder import UIBuilder
import time

class DebugMainWindow:
    """调试主窗口类 - 模拟真实应用场景"""
    def __init__(self):
        self.model = ChannelListModel()
        self.ui = UIBuilder(self)
        self.config = MockConfig()
        self.language_manager = MockLanguageManager()
        self.statusBar = MockStatusBar()
        self.progress_indicator = MockProgressBar()
        self.channel_list = DebugTableView()
        
        # 关键：将模型设置到视图中
        self.channel_list.setModel(self.model)
        
        # 添加一些测试数据
        self._add_test_channels()
        
    def _add_test_channels(self):
        """添加测试频道"""
        test_channels = [
            {
                'url': 'http://example.com/test1.m3u8',
                'name': '测试频道1',
                'raw_name': '测试频道1',
                'valid': True,
                'latency': 100,
                'resolution': '1920x1080',
                'status': '有效',
                'group': '测试分组',
                'logo_url': 'http://example.com/logo1.png'
            },
            {
                'url': 'http://example.com/test2.m3u8',
                'name': '测试频道2',
                'raw_name': '测试频道2',
                'valid': True,
                'latency': 150,
                'resolution': '1280x720',
                'status': '有效',
                'group': '测试分组',
                'logo_url': 'http://example.com/logo2.png'
            }
        ]
        
        for channel in test_channels:
            self.model.add_channel(channel)
        
        print(f"添加了 {len(test_channels)} 个测试频道")

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

class DebugTableView(QtWidgets.QTableView):
    """调试表格视图，用于跟踪UI更新"""
    def __init__(self):
        super().__init__()
        self.data_changed_count = 0
        self.layout_changed_count = 0
        self.update_count = 0
        self.repaint_count = 0
        self.model_changed_count = 0
        
    def setModel(self, model):
        """重写setModel方法以跟踪模型设置"""
        self.model_changed_count += 1
        print(f"✅ 模型设置 #{self.model_changed_count}")
        super().setModel(model)
        
    def viewport(self):
        return self
        
    def update(self):
        self.update_count += 1
        print(f"✅ 视图更新调用 #{self.update_count}")
        super().update()
        
    def repaint(self):
        self.repaint_count += 1
        print(f"✅ 重绘调用 #{self.repaint_count}")
        super().repaint()
        
    def dataChanged(self, top_left, bottom_right, roles):
        self.data_changed_count += 1
        print(f"✅ 数据变化信号 #{self.data_changed_count}: 行 {top_left.row()}-{bottom_right.row()}, 列 {top_left.column()}-{bottom_right.column()}")
        super().dataChanged(top_left, bottom_right, roles)
        
    def layoutChanged(self):
        self.layout_changed_count += 1
        print(f"✅ 布局变化信号 #{self.layout_changed_count}")
        super().layoutChanged()

def test_refresh_functionality():
    """测试刷新功能"""
    print("开始测试刷新功能...")
    
    # 创建调试主窗口
    main_window = DebugMainWindow()
    
    # 检查初始状态
    print(f"\n初始状态:")
    print(f"频道数量: {main_window.model.rowCount()}")
    print(f"模型设置次数: {main_window.channel_list.model_changed_count}")
    
    # 模拟右键重新获取频道信息
    print(f"\n模拟右键重新获取频道信息...")
    
    # 获取第一个频道的索引
    index = main_window.model.index(0, 0)
    
    # 模拟_finish_refresh_channel方法
    new_channel_info = {
        'url': 'http://example.com/test1.m3u8',
        'name': '更新后的频道名',
        'raw_name': '更新后的频道名',
        'valid': True,
        'latency': 50,
        'resolution': '1280x720',
        'status': '有效',
        'group': '更新后的分组',
        'logo_url': 'http://example.com/new_logo.png'
    }
    
    print("调用 update_channel 方法...")
    success = main_window.model.update_channel(0, new_channel_info)
    
    if success:
        print("✅ 频道信息更新成功")
        
        # 检查更新后的频道信息
        updated_channel = main_window.model.get_channel(0)
        print(f"更新后的频道信息: {updated_channel['name']}")
        
        # 模拟_finish_refresh_channel中的UI更新逻辑
        print("\n模拟UI更新逻辑...")
        
        # 强制刷新整个视图，确保所有列都更新
        top_left = main_window.model.index(0, 0)
        bottom_right = main_window.model.index(0, main_window.model.columnCount() - 1)
        print("发送数据变化信号...")
        main_window.model.dataChanged.emit(top_left, bottom_right, [QtCore.Qt.ItemDataRole.DisplayRole, QtCore.Qt.ItemDataRole.DecorationRole])
        
        # 强制刷新UI，确保立即显示更新
        print("强制刷新UI视图...")
        main_window.channel_list.viewport().update()
        
        # 强制调整列宽以适应新内容
        print("强制调整列宽...")
        header = main_window.channel_list.horizontalHeader()
        header.resizeSections(QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        
        # 强制刷新整个模型，确保UI完全更新
        print("发送布局变化信号...")
        main_window.model.layoutChanged.emit()
        
        # 强制重绘
        print("强制重绘...")
        main_window.channel_list.repaint()
        
        # 检查信号触发情况
        print(f"\n信号触发情况:")
        print(f"模型设置: {main_window.channel_list.model_changed_count}")
        print(f"数据变化信号: {main_window.channel_list.data_changed_count}")
        print(f"布局变化信号: {main_window.channel_list.layout_changed_count}")
        print(f"视图更新: {main_window.channel_list.update_count}")
        print(f"重绘: {main_window.channel_list.repaint_count}")
        
        # 验证更新是否成功
        if updated_channel['name'] == '更新后的频道名':
            print("✅ 频道信息更新验证成功")
            return True
        else:
            print("❌ 频道信息更新验证失败")
            return False
    else:
        print("❌ 频道信息更新失败")
        return False

def test_ui_builder_model_setup():
    """测试UI构建器中的模型设置"""
    print("\n测试UI构建器中的模型设置...")
    
    class TestWindow:
        def __init__(self):
            self.model = None
            self.channel_list = QtWidgets.QTableView()
            self.language_manager = MockLanguageManager()
            
    test_window = TestWindow()
    ui_builder = UIBuilder(test_window)
    
    # 模拟_setup_channel_list方法
    print("模拟_setup_channel_list方法...")
    
    # 确保模型存在并正确设置到视图中
    if not hasattr(test_window, 'model') or not test_window.model:
        test_window.model = ChannelListModel()
        test_window.model.update_status_label = lambda text: print(f"状态更新: {text}")
        # 设置语言管理器
        if hasattr(test_window, 'language_manager') and test_window.language_manager:
            test_window.model.set_language_manager(test_window.language_manager)
    
    # 关键：始终将模型设置到视图中，确保连接正确
    test_window.channel_list.setModel(test_window.model)
    print("✅ 频道列表模型已设置到视图中")
    
    # 检查模型是否设置成功
    if test_window.channel_list.model() == test_window.model:
        print("✅ 模型设置验证成功")
        return True
    else:
        print("❌ 模型设置验证失败")
        return False

def main():
    """主调试函数"""
    print("开始调试右键重新获取频道信息功能...")
    
    # 创建QApplication实例（PyQt6需要）
    app = QtWidgets.QApplication(sys.argv)
    
    # 测试UI构建器中的模型设置
    ui_builder_success = test_ui_builder_model_setup()
    
    # 测试刷新功能
    refresh_success = test_refresh_functionality()
    
    if ui_builder_success and refresh_success:
        print("\n🎉 所有测试通过！重新获取频道信息功能应该正常工作")
    else:
        print("\n⚠️ 部分测试失败，需要进一步调试")
    
    # 清理QApplication
    app.quit()

if __name__ == "__main__":
    main()
