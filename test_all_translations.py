#!/usr/bin/env python3
"""
测试所有翻译功能，包括新添加的按钮和统计标签
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from PyQt6 import QtWidgets, QtCore
from language_manager import LanguageManager

def test_all_translations():
    """测试所有翻译功能"""
    app = QtWidgets.QApplication(sys.argv)
    
    # 创建语言管理器
    language_manager = LanguageManager()
    language_manager.load_available_languages()
    
    print("=== 测试所有翻译功能 ===")
    print(f"可用语言: {list(language_manager.available_languages.keys())}")
    
    # 测试所有翻译键
    test_keys = [
        'stop_scan', 'full_scan', 'pause', 'play', 
        'total_channels', 'valid', 'invalid', 'time_elapsed'
    ]
    
    print("\n1. 测试英文翻译")
    if language_manager.set_language('en'):
        for key in test_keys:
            translation = language_manager.tr(key, key.capitalize().replace('_', ' '))
            print(f"  {key}: {translation}")
    else:
        print("✗ 切换到英文失败")
    
    print("\n2. 测试中文翻译")
    if language_manager.set_language('zh'):
        for key in test_keys:
            translation = language_manager.tr(key, key.capitalize().replace('_', ' '))
            print(f"  {key}: {translation}")
    else:
        print("✗ 切换到中文失败")
    
    print("\n3. 测试统计信息格式")
    # 模拟统计信息
    stats = {
        'total': 100,
        'valid': 75,
        'invalid': 25,
        'elapsed': 3600  # 1小时
    }
    
    # 测试英文统计格式
    if language_manager.set_language('en'):
        total_text = language_manager.tr('total_channels', 'Total Channels')
        valid_text = language_manager.tr('valid', 'Valid')
        invalid_text = language_manager.tr('invalid', 'Invalid')
        time_text = language_manager.tr('time_elapsed', 'Time Elapsed')
        elapsed = "01:00:00"
        
        stats_text = f"{total_text}: {stats['total']} | {valid_text}: {stats['valid']} | {invalid_text}: {stats['invalid']} | {time_text}: {elapsed}"
        print(f"英文统计格式: {stats_text}")
    
    # 测试中文统计格式
    if language_manager.set_language('zh'):
        total_text = language_manager.tr('total_channels', 'Total Channels')
        valid_text = language_manager.tr('valid', 'Valid')
        invalid_text = language_manager.tr('invalid', 'Invalid')
        time_text = language_manager.tr('time_elapsed', 'Time Elapsed')
        elapsed = "01:00:00"
        
        stats_text = f"{total_text}: {stats['total']} | {valid_text}: {stats['valid']} | {invalid_text}: {stats['invalid']} | {time_text}: {elapsed}"
        print(f"中文统计格式: {stats_text}")
    
    print("\n=== 所有翻译测试完成 ===")
    sys.exit(0)

if __name__ == "__main__":
    test_all_translations()
