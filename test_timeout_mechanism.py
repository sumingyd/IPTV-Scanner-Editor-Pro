#!/usr/bin/env python3
"""
测试5秒超时机制
"""

import sys
import os
import time
import threading
sys.path.append(os.path.dirname(__file__))

from scanner_controller import ScannerController
from channel_model import ChannelListModel

def test_timeout_mechanism():
    """测试5秒超时机制"""
    print("测试5秒超时机制...")
    
    # 创建模型和扫描控制器
    model = ChannelListModel()
    scanner = ScannerController(model)
    
    # 模拟添加频道到批量缓存
    test_channels = []
    for i in range(10):
        channel_info = {
            'url': f'http://example.com/channel{i}.m3u8',
            'name': f'测试频道{i}',
            'raw_name': f'测试频道{i}',
            'valid': True,
            'latency': 100,
            'resolution': '1920x1080',
            'status': '有效',
            'group': '测试分组'
        }
        test_channels.append(channel_info)
    
    print(f"添加 {len(test_channels)} 个测试频道到批量缓存")
    
    # 手动添加频道到批量缓存
    with scanner.counter_lock:
        scanner._batch_channels.extend(test_channels)
        scanner._last_channel_time = time.time()
    
    print(f"批量缓存中的频道数量: {len(scanner._batch_channels)}")
    print(f"最后频道添加时间: {scanner._last_channel_time}")
    
    # 等待6秒，应该触发超时机制
    print("等待6秒，应该触发5秒超时机制...")
    time.sleep(6)
    
    # 手动调用批量刷新
    scanner._flush_batch_channels()
    
    print(f"批量刷新后缓存中的频道数量: {len(scanner._batch_channels)}")
    
    # 检查模型是否收到了频道
    model_channel_count = model.rowCount()
    print(f"模型中的频道数量: {model_channel_count}")
    
    if model_channel_count > 0:
        print("✅ 5秒超时机制测试成功！频道已添加到模型")
        return True
    else:
        print("❌ 5秒超时机制测试失败！频道未添加到模型")
        return False

def test_batch_size_mechanism():
    """测试批量大小机制"""
    print("\n测试批量大小机制...")
    
    # 创建模型和扫描控制器
    model = ChannelListModel()
    scanner = ScannerController(model)
    
    # 添加刚好50个频道（批量大小）
    test_channels = []
    for i in range(50):
        channel_info = {
            'url': f'http://example.com/channel{i}.m3u8',
            'name': f'测试频道{i}',
            'raw_name': f'测试频道{i}',
            'valid': True,
            'latency': 100,
            'resolution': '1920x1080',
            'status': '有效',
            'group': '测试分组'
        }
        test_channels.append(channel_info)
    
    print(f"添加 {len(test_channels)} 个测试频道到批量缓存（刚好达到批量大小）")
    
    # 手动添加频道到批量缓存
    with scanner.counter_lock:
        scanner._batch_channels.extend(test_channels)
        scanner._last_channel_time = time.time()
    
    print(f"批量缓存中的频道数量: {len(scanner._batch_channels)}")
    
    # 手动调用批量刷新
    scanner._flush_batch_channels()
    
    print(f"批量刷新后缓存中的频道数量: {len(scanner._batch_channels)}")
    
    # 检查模型是否收到了频道
    model_channel_count = model.rowCount()
    print(f"模型中的频道数量: {model_channel_count}")
    
    if model_channel_count == 50:
        print("✅ 批量大小机制测试成功！所有频道已添加到模型")
        return True
    else:
        print(f"❌ 批量大小机制测试失败！期望50个频道，实际{model_channel_count}个")
        return False

def main():
    """主测试函数"""
    print("开始测试5秒超时机制...")
    
    # 测试5秒超时机制
    timeout_test_passed = test_timeout_mechanism()
    
    # 测试批量大小机制
    batch_test_passed = test_batch_size_mechanism()
    
    if timeout_test_passed and batch_test_passed:
        print("\n🎉 所有测试通过！5秒超时机制正常工作")
    else:
        print("\n⚠️ 部分测试失败，请检查实现")

if __name__ == "__main__":
    main()
