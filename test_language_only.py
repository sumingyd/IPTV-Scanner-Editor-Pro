#!/usr/bin/env python3
"""
测试语言切换功能的简单脚本
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from PyQt6 import QtWidgets, QtCore
from language_manager import LanguageManager

def test_language_switch():
    """测试语言切换功能"""
    app = QtWidgets.QApplication(sys.argv)
    
    # 创建语言管理器
    language_manager = LanguageManager()
    language_manager.load_available_languages()
    
    print("=== 测试语言切换功能 ===")
    print(f"可用语言: {list(language_manager.available_languages.keys())}")
    
    # 测试切换到英文
    print("\n1. 测试切换到英文")
    if language_manager.set_language('en'):
        print("✓ 成功切换到英文")
        print(f"翻译测试 - app_title: {language_manager.tr('app_title')}")
        print(f"翻译测试 - video_playback: {language_manager.tr('video_playback')}")
        print(f"翻译测试 - timeout_description: {language_manager.tr('timeout_description')}")
        print(f"翻译测试 - thread_count_description: {language_manager.tr('thread_count_description')}")
    else:
        print("✗ 切换到英文失败")
    
    # 测试切换回中文
    print("\n2. 测试切换回中文")
    if language_manager.set_language('zh'):
        print("✓ 成功切换到中文")
        print(f"翻译测试 - app_title: {language_manager.tr('app_title')}")
        print(f"翻译测试 - video_playback: {language_manager.tr('video_playback')}")
        print(f"翻译测试 - timeout_description: {language_manager.tr('timeout_description')}")
        print(f"翻译测试 - thread_count_description: {language_manager.tr('thread_count_description')}")
    else:
        print("✗ 切换到中文失败")
    
    print("\n=== 语言切换测试完成 ===")
    sys.exit(0)

if __name__ == "__main__":
    test_language_switch()
