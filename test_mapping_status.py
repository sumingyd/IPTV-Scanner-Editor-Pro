#!/usr/bin/env python3
"""
测试映射状态标签的翻译功能
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from PyQt6 import QtWidgets, QtCore
from language_manager import LanguageManager

def test_mapping_status():
    """测试映射状态标签的翻译功能"""
    app = QtWidgets.QApplication(sys.argv)
    
    # 创建语言管理器
    language_manager = LanguageManager()
    language_manager.load_available_languages()
    
    print("=== 测试映射状态标签翻译功能 ===")
    print(f"可用语言: {list(language_manager.available_languages.keys())}")
    
    # 测试映射状态标签的翻译
    print("\n1. 测试映射状态标签翻译")
    
    # 测试英文
    if language_manager.set_language('en'):
        mapping_loaded = language_manager.tr('mapping_loaded', 'Remote mapping loaded')
        mapping_failed = language_manager.tr('mapping_failed', 'Remote mapping load failed')
        print(f"英文映射已加载: {mapping_loaded}")
        print(f"英文映射加载失败: {mapping_failed}")
    else:
        print("✗ 切换到英文失败")
    
    # 测试中文
    if language_manager.set_language('zh'):
        mapping_loaded = language_manager.tr('mapping_loaded', 'Remote mapping loaded')
        mapping_failed = language_manager.tr('mapping_failed', 'Remote mapping load failed')
        print(f"中文映射已加载: {mapping_loaded}")
        print(f"中文映射加载失败: {mapping_failed}")
    else:
        print("✗ 切换到中文失败")
    
    print("\n=== 映射状态标签翻译测试完成 ===")
    sys.exit(0)

if __name__ == "__main__":
    test_mapping_status()
