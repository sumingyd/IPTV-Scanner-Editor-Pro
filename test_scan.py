#!/usr/bin/env python3
"""
测试扫描功能修复
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

from scanner_controller import ScannerController
from channel_model import ChannelListModel
from validator import StreamValidator

def test_ffmpeg_path():
    """测试ffmpeg路径查找"""
    print("测试ffmpeg路径查找...")
    validator = StreamValidator()
    ffmpeg_path = validator._get_ffmpeg_path()
    ffprobe_path = validator._get_ffprobe_path()
    
    print(f"ffmpeg路径: {ffmpeg_path}")
    print(f"ffprobe路径: {ffprobe_path}")
    print(f"ffmpeg文件存在: {os.path.exists(ffmpeg_path)}")
    print(f"ffprobe文件存在: {os.path.exists(ffprobe_path)}")
    
    return os.path.exists(ffmpeg_path) and os.path.exists(ffprobe_path)

def test_single_url_validation():
    """测试单个URL验证"""
    print("\n测试单个URL验证...")
    validator = StreamValidator()
    
    # 测试一个简单的URL
    test_url = "http://example.com/test.m3u8"  # 这个URL应该会失败，但可以测试流程
    result = validator.validate_stream(test_url, timeout=5)
    
    print(f"URL: {test_url}")
    print(f"有效: {result['valid']}")
    print(f"延迟: {result['latency']}")
    print(f"错误: {result['error']}")
    print(f"重试次数: {result['retries']}")
    print(f"频道名: {result['service_name']}")
    
    return result

def test_scanner_controller_init():
    """测试扫描控制器初始化"""
    print("\n测试扫描控制器初始化...")
    try:
        model = ChannelListModel()
        scanner = ScannerController(model)
        print("扫描控制器初始化成功")
        return True
    except Exception as e:
        print(f"扫描控制器初始化失败: {e}")
        return False

def main():
    """主测试函数"""
    print("开始测试扫描功能修复...")
    
    # 测试ffmpeg路径
    if not test_ffmpeg_path():
        print("ffmpeg路径测试失败")
        return
    
    # 测试扫描控制器初始化
    if not test_scanner_controller_init():
        print("扫描控制器初始化测试失败")
        return
    
    # 测试单个URL验证
    test_single_url_validation()
    
    print("\n测试完成！")

if __name__ == "__main__":
    main()
