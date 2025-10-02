#!/usr/bin/env python3
"""
测试完整应用流程 - 模拟实际应用中的右键重新获取频道信息
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

from PyQt6 import QtWidgets, QtCore, QtGui
from channel_model import ChannelListModel
from ui_builder import UIBuilder
import time

class FullAppMainWindow(QtWidgets.QMainWindow):
    """完整应用主窗口类 - 模拟真实应用场景"""
    def __init__(self):
        super().__init__()
        
        # 模拟main.py中的初始化流程
        self.config = MockConfig()
        self.language_manager = MockLanguageManager()
        
        # 构建UI（模拟main.py中的UI构建）
        self.ui = UIBuilder(self)
        self.ui.build_ui()
        
        # 模拟main.py中的模型初始化（关键：使用UI构建器中已经创建的模型）
        self.model = self.ui.main_window.model
        
        # 设置模型的父对象为主窗口，确保可以访问UI层的方法
        self.model.setParent(self)
        
        # 初始化控制器（模拟main.py中的控制器初始化）
        self.scanner = MockScannerController(self.model, self)
        self.player_controller = MockPlayerController()
        
        # 连接信号槽（模拟main.py中的信号连接）
        self._connect_signals()
        
        # 添加一些测试数据
        self._add_test_channels()
        
    def _add_test_channels(self):
        """添加测试频道"""
        test_channels = [
            {
                'url': 'http://example.com/test1.m3u8',
                'name': '原始频道1',
                'raw_name': '原始频道1',
                'valid': True,
                'latency': 100,
                'resolution': '1920x1080',
                'status': '有效',
                'group': '测试分组',
                'logo_url': 'http://example.com/logo1.png'
            },
            {
                'url': 'http://example.com/test2.m3u8',
                'name': '原始频道2',
                'raw_name': '原始频道2',
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
        
    def _connect_signals(self):
        """连接信号槽（模拟main.py中的信号连接）"""
        # 连接频道列表选择信号
        self.ui.main_window.channel_list.selectionModel().selectionChanged.connect(
            self._on_channel_selected
        )
        
    def _on_channel_selected(self):
        """处理频道选择事件"""
        selected = self.ui.main_window.channel_list.selectedIndexes()
        if not selected:
            return
            
        # 获取选中的频道
        row = selected[0].row()
        self.current_channel_index = row
        print(f"选中频道: 行 {row}")
        
    def _update_validate_status(self, text):
        """更新有效性检测状态标签"""
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

class MockScannerController:
    """模拟扫描控制器"""
    def __init__(self, model, main_window):
        self.model = model
        self.main_window = main_window

class MockPlayerController:
    """模拟播放控制器"""
    pass

def test_full_app_refresh():
    """测试完整应用中的刷新功能"""
    print("开始测试完整应用中的刷新功能...")
    
    # 创建完整应用主窗口
    main_window = FullAppMainWindow()
    
    # 检查初始状态
    print(f"\n初始状态:")
    print(f"频道数量: {main_window.model.rowCount()}")
    print(f"模型对象: {main_window.model}")
    print(f"视图模型: {main_window.ui.main_window.channel_list.model()}")
    
    # 检查模型和视图是否连接正确
    if main_window.ui.main_window.channel_list.model() == main_window.model:
        print("✅ 模型和视图连接正确")
    else:
        print("❌ 模型和视图连接错误")
        return False
    
    # 模拟右键重新获取频道信息
    print(f"\n模拟右键重新获取频道信息...")
    
    # 选择第一个频道
    selection_model = main_window.ui.main_window.channel_list.selectionModel()
    index = main_window.model.index(0, 0)
    selection_model.select(index, QtCore.QItemSelectionModel.SelectionFlag.Select | QtCore.QItemSelectionModel.SelectionFlag.Rows)
    
    # 等待选择生效
    QtWidgets.QApplication.processEvents()
    time.sleep(0.1)
    
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
        main_window.ui.main_window.channel_list.viewport().update()
        
        # 强制调整列宽以适应新内容
        print("强制调整列宽...")
        header = main_window.ui.main_window.channel_list.horizontalHeader()
        header.resizeSections(QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        
        # 强制刷新整个模型，确保UI完全更新
        print("发送布局变化信号...")
        main_window.model.layoutChanged.emit()
        
        # 强制重绘
        print("强制重绘...")
        main_window.ui.main_window.channel_list.repaint()
        
        # 处理事件队列，确保UI更新
        print("处理事件队列...")
        QtWidgets.QApplication.processEvents()
        
        # 验证更新是否成功
        if updated_channel['name'] == '更新后的频道名':
            print("✅ 频道信息更新验证成功")
            
            # 检查UI是否显示更新
            print(f"\n最终检查:")
            print(f"模型中的频道名: {updated_channel['name']}")
            print(f"视图模型连接: {main_window.ui.main_window.channel_list.model() == main_window.model}")
            
            return True
        else:
            print("❌ 频道信息更新验证失败")
            return False
    else:
        print("❌ 频道信息更新失败")
        return False

def main():
    """主测试函数"""
    print("开始测试完整应用流程...")
    
    # 创建QApplication实例（PyQt6需要）
    app = QtWidgets.QApplication(sys.argv)
    
    # 测试完整应用中的刷新功能
    success = test_full_app_refresh()
    
    if success:
        print("\n🎉 完整应用测试通过！重新获取频道信息功能应该正常工作")
        print("\n如果实际应用中还是不更新，请检查：")
        print("1. 实际应用中是否有其他代码干扰了模型设置")
        print("2. 实际应用中是否有其他定时器或线程干扰了UI更新")
        print("3. 实际应用中是否有其他事件处理干扰了右键菜单功能")
    else:
        print("\n⚠️ 完整应用测试失败")
    
    # 清理QApplication
    app.quit()

if __name__ == "__main__":
    main()
