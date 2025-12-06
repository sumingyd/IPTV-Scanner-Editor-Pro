#!/usr/bin/env python3
"""
测试启动动画的脚本
"""

import sys
import time
from PyQt6 import QtWidgets, QtCore, QtGui
import random

class TestLoadingScreen(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.current_step = 0
        self.steps = [
            "正在初始化应用程序...",
