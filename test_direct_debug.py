#!/usr/bin/env python3
"""
直接调试脚本 - 在实际应用中添加调试信息
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

from PyQt6 import QtWidgets, QtCore, QtGui
from channel_model import ChannelListModel
import time

class DebugChannelListModel(ChannelListModel):
    """调试频道列表模型 - 添加调试信息"""
    def update_channel(self, index, channel_info):
        print(f"🔍 [模型] 开始更新频道 {index}: {channel_info.get('name', '未知')}")
        result = super().update_channel(index, channel_info)
        print(f"🔍 [模型] 更新频道 {index} 结果: {result}")
        return result
        
    def data(self, index, role=QtCore.Qt.ItemDataRole.DisplayRole):
        result = super().data(index, role)
        if role == QtCore.Qt.ItemDataRole.DisplayRole and index.column() == 1:  # 名称列
            print(f"🔍 [模型] 获取数据: 行 {index.row()}, 列 {index.column()}, 角色 {role}, 值: {result}")
        return result

def test_direct_update():
    """直接测试更新功能"""
    print("开始直接测试更新功能...")
    
    # 创建QApplication实例
    app = QtWidgets.QApplication(sys.argv)
    
    # 创建调试模型
    model = DebugChannelListModel()
    
    # 添加测试频道
    test_channel = {
        'url': 'http://example.com/test.m3u8',
        'name': '原始频道名',
        'raw_name': '原始频道名',
        'valid': True,
        'latency': 100,
        'resolution': '1920x1080',
        'status': '有效',
        'group': '测试分组',
        'logo_url': 'http://example.com/logo.png'
    }
    
    print(f"添加测试频道: {test_channel['name']}")
    model.add_channel(test_channel)
    
    # 检查初始状态
    print(f"初始频道数量: {model.rowCount()}")
    initial_channel = model.get_channel(0)
    print(f"初始频道信息: {initial_channel['name']}")
    
    # 模拟更新频道信息
    new_channel_info = {
        'url': 'http://example.com/test.m3u8',
        'name': '更新后的频道名',
        'raw_name': '更新后的频道名',
        'valid': True,
        'latency': 50,
        'resolution': '1280x720',
        'status': '有效',
        'group': '更新后的分组',
        'logo_url': 'http://example.com/new_logo.png'
    }
    
    print(f"\n开始更新频道信息...")
    success = model.update_channel(0, new_channel_info)
    
    if success:
        print("✅ 频道信息更新成功")
        
        # 检查更新后的频道信息
        updated_channel = model.get_channel(0)
        print(f"更新后的频道信息: {updated_channel['name']}")
        
        # 强制发送数据变化信号
        print("发送数据变化信号...")
        top_left = model.index(0, 0)
        bottom_right = model.index(0, model.columnCount() - 1)
        model.dataChanged.emit(top_left, bottom_right, [QtCore.Qt.ItemDataRole.DisplayRole])
        
        # 检查数据是否真的更新了
        print("检查数据是否更新...")
        for col in range(model.columnCount()):
            data = model.data(model.index(0, col))
            print(f"列 {col}: {data}")
        
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

def main():
    """主测试函数"""
    print("开始直接调试...")
    
    # 测试直接更新功能
    success = test_direct_update()
    
    if success:
        print("\n🎉 直接调试通过！模型更新功能正常工作")
        print("\n如果实际应用中还是不更新，问题可能在于：")
        print("1. 实际应用中模型和视图没有正确连接")
        print("2. 实际应用中有其他代码干扰了UI更新")
        print("3. 实际应用中右键菜单功能没有正确触发更新")
    else:
        print("\n⚠️ 直接调试失败")
    
    # 清理QApplication
    QtWidgets.QApplication.quit()

if __name__ == "__main__":
    main()
