#!/usr/bin/env python3
"""
测试工具栏按钮的翻译功能
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from PyQt6 import QtWidgets, QtCore
from language_manager import LanguageManager

def test_toolbar_buttons():
    """测试工具栏按钮的翻译功能"""
    app = QtWidgets.QApplication(sys.argv)
    
    # 创建语言管理器
    language_manager = LanguageManager()
    language_manager.load_available_languages()
    
    print("=== 测试工具栏按钮翻译功能 ===")
    print(f"可用语言: {list(language_manager.available_languages.keys())}")
    
    # 测试工具栏按钮的翻译
    print("\n1. 测试工具栏按钮翻译")
    
    # 测试英文
    if language_manager.set_language('en'):
        open_list = language_manager.tr('open_list', 'Open List')
        save_list = language_manager.tr('save_list', 'Save List')
        language = language_manager.tr('language', 'Language')
        about = language_manager.tr('about', 'About')
        print(f"英文打开列表: {open_list}")
        print(f"英文保存列表: {save_list}")
        print(f"英文语言: {language}")
        print(f"英文关于: {about}")
    else:
        print("✗ 切换到英文失败")
    
    # 测试中文
    if language_manager.set_language('zh'):
        open_list = language_manager.tr('open_list', 'Open List')
        save_list = language_manager.tr('save_list', 'Save List')
        language = language_manager.tr('language', 'Language')
        about = language_manager.tr('about', 'About')
        print(f"中文打开列表: {open_list}")
        print(f"中文保存列表: {save_list}")
        print(f"中文语言: {language}")
        print(f"中文关于: {about}")
    else:
        print("✗ 切换到中文失败")
    
    print("\n=== 工具栏按钮翻译测试完成 ===")
    sys.exit(0)

if __name__ == "__main__":
    test_toolbar_buttons()
