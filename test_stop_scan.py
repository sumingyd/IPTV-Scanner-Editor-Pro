#!/usr/bin/env python3
"""
测试停止扫描按钮的翻译功能
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from PyQt6 import QtWidgets, QtCore
from language_manager import LanguageManager

def test_stop_scan():
    """测试停止扫描按钮的翻译功能"""
    app = QtWidgets.QApplication(sys.argv)
    
    # 创建语言管理器
    language_manager = LanguageManager()
    language_manager.load_available_languages()
    
    print("=== 测试停止扫描按钮翻译功能 ===")
    print(f"可用语言: {list(language_manager.available_languages.keys())}")
    
    # 测试停止扫描按钮的翻译
    print("\n1. 测试停止扫描按钮翻译")
    
    # 测试英文
    if language_manager.set_language('en'):
        stop_scan = language_manager.tr('stop_scan', 'Stop Scan')
        print(f"英文停止扫描: {stop_scan}")
    else:
        print("✗ 切换到英文失败")
    
    # 测试中文
    if language_manager.set_language('zh'):
        stop_scan = language_manager.tr('stop_scan', 'Stop Scan')
        print(f"中文停止扫描: {stop_scan}")
    else:
        print("✗ 切换到中文失败")
    
    print("\n=== 停止扫描按钮翻译测试完成 ===")
    sys.exit(0)

if __name__ == "__main__":
    test_stop_scan()
