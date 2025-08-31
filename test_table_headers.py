#!/usr/bin/env python3
"""
测试表头翻译功能
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from PyQt6 import QtWidgets, QtCore
from language_manager import LanguageManager
from channel_model import ChannelListModel

def test_table_headers():
    """测试表头翻译功能"""
    app = QtWidgets.QApplication(sys.argv)
    
    # 创建语言管理器
    language_manager = LanguageManager()
    language_manager.load_available_languages()
    
    # 创建频道模型
    model = ChannelListModel()
    
    print("=== 测试表头翻译功能 ===")
    print(f"可用语言: {list(language_manager.available_languages.keys())}")
    
    # 测试表头翻译
    print("\n1. 测试表头翻译")
    
    # 测试英文
    if language_manager.set_language('en'):
        model.set_language_manager(language_manager)
        print("英文表头:")
        for i in range(model.columnCount()):
            header = model.headerData(i, QtCore.Qt.Orientation.Horizontal)
            print(f"  列 {i}: {header}")
    else:
        print("✗ 切换到英文失败")
    
    # 测试中文
    if language_manager.set_language('zh'):
        model.set_language_manager(language_manager)
        print("\n中文表头:")
        for i in range(model.columnCount()):
            header = model.headerData(i, QtCore.Qt.Orientation.Horizontal)
            print(f"  列 {i}: {header}")
    else:
        print("✗ 切换到中文失败")
    
    print("\n=== 表头翻译测试完成 ===")
    sys.exit(0)

if __name__ == "__main__":
    test_table_headers()
