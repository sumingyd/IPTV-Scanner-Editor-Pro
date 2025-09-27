#!/usr/bin/env python3
"""
测试频道映射新功能
"""

import sys
import os
import json
import time
from channel_mappings import mapping_manager, ChannelMappingManager

def test_mapping_manager():
    """测试映射管理器功能"""
    print("=" * 50)
    print("测试频道映射管理器")
    print("=" * 50)
    
    # 测试1: 基本功能
    print("\n1. 测试基本映射功能")
    test_name = "CCTV1"
    result = mapping_manager.get_channel_info(test_name)
    print(f"频道 '{test_name}' 的映射结果: {result}")
    
    # 测试2: 添加用户映射
    print("\n2. 测试用户自定义映射")
    mapping_manager.add_user_mapping("测试频道1", "测试标准频道", "http://example.com/logo.png", "测试分组")
    result = mapping_manager.get_channel_info("测试频道1")
    print(f"用户映射测试结果: {result}")
    
    # 测试3: 频道指纹功能
    print("\n3. 测试频道指纹功能")
    test_url = "http://example.com/stream.m3u8"
    channel_info = {
        'service_name': '测试频道',
        'resolution': '1920x1080',
        'codec': 'h264',
        'bitrate': '2000kbps'
    }
    fingerprint = mapping_manager.create_channel_fingerprint(test_url, channel_info)
    print(f"频道指纹: {fingerprint}")
    
    # 测试4: 智能学习功能
    print("\n4. 测试智能学习功能")
    mapping_manager.learn_from_scan_result(test_url, "测试频道", channel_info, "测试标准频道")
    print("学习记录已保存")
    
    # 测试5: 获取映射建议
    print("\n5. 测试映射建议功能")
    suggestions = mapping_manager.get_mapping_suggestions("测试频道")
    print(f"映射建议: {suggestions}")
    
    # 测试6: 缓存功能
    print("\n6. 测试缓存功能")
    mapping_manager.refresh_cache()
    print("缓存已刷新")
    
    # 测试7: 查看当前映射状态
    print("\n7. 当前映射状态")
    print(f"用户映射数量: {len(mapping_manager.user_mappings)}")
    print(f"频道指纹数量: {len(mapping_manager.channel_fingerprints)}")
    print(f"组合映射数量: {len(mapping_manager.combined_mappings)}")
    
    # 测试8: 保存和加载功能
    print("\n8. 测试保存和加载功能")
    # 保存用户映射
    mapping_manager._save_user_mappings()
    print("用户映射已保存")
    
    # 保存频道指纹
    mapping_manager._save_channel_fingerprints()
    print("频道指纹已保存")
    
    # 测试9: 删除用户映射
    print("\n9. 测试删除用户映射")
    mapping_manager.remove_user_mapping("测试标准频道")
    print("用户映射已删除")
    
    print("\n" + "=" * 50)
    print("测试完成!")
    print("=" * 50)

def test_file_operations():
    """测试文件操作功能"""
    print("\n" + "=" * 50)
    print("测试文件操作功能")
    print("=" * 50)
    
    # 检查缓存文件是否存在
    cache_files = [
        "channel_mappings_cache.json",
        "user_channel_mappings.json", 
        "channel_fingerprints.json"
    ]
    
    for file in cache_files:
        if os.path.exists(file):
            print(f"✓ {file} 存在")
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                print(f"  - 文件大小: {len(data)} 条记录")
            except Exception as e:
                print(f"  - 读取错误: {e}")
        else:
            print(f"✗ {file} 不存在")
    
    print("\n" + "=" * 50)
    print("文件操作测试完成!")
    print("=" * 50)

def test_error_handling():
    """测试错误处理功能"""
    print("\n" + "=" * 50)
    print("测试错误处理功能")
    print("=" * 50)
    
    # 测试异常情况处理
    test_cases = [
        ("", "空频道名"),
        ("   ", "空白频道名"),
        (None, "None频道名"),
        ("非常长的频道名称" * 10, "超长频道名")
    ]
    
    for test_name, description in test_cases:
        try:
            result = mapping_manager.get_channel_info(test_name)
            print(f"✓ {description}: 处理成功")
            print(f"  结果: {result}")
        except Exception as e:
            print(f"✗ {description}: 处理失败 - {e}")
    
    print("\n" + "=" * 50)
    print("错误处理测试完成!")
    print("=" * 50)

def main():
    """主测试函数"""
    print("IPTV扫描器频道映射功能测试")
    print("=" * 60)
    
    try:
        # 测试映射管理器功能
        test_mapping_manager()
        
        # 测试文件操作功能
        test_file_operations()
        
        # 测试错误处理功能
        test_error_handling()
        
        print("\n" + "=" * 60)
        print("所有测试完成!")
        print("=" * 60)
        
        # 显示使用说明
        print("\n使用说明:")
        print("1. 运行程序后，点击工具栏的'🗺️ 映射管理'按钮打开映射管理器")
        print("2. 在映射管理器中可以:")
        print("   - 查看和管理用户自定义映射")
        print("   - 查看频道指纹数据")
        print("   - 获取映射建议")
        print("   - 导入/导出映射规则")
        print("3. 扫描时会自动使用新的智能映射功能")
        print("4. 映射规则会自动缓存到本地，提高下次扫描速度")
        
    except Exception as e:
        print(f"测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
