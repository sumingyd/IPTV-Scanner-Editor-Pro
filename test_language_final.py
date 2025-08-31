#!/usr/bin/env python3
"""
测试语言切换功能的完整修复
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
