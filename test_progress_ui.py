"""测试进度条UI更新"""

import sys
from PyQt6 import QtWidgets, QtCore, QtGui
import time

class ProgressTestWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("进度条测试")
        self.setGeometry(100, 100, 400, 200)
        
        # 创建中央部件
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        
        # 创建布局
        layout = QtWidgets.QVBoxLayout(central_widget)
        
        # 创建进度条
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        layout.addWidget(self.progress_bar)
        
        # 创建测试按钮
        self.test_btn = QtWidgets.QPushButton("开始测试")
        self.test_btn.clicked.connect(self.start_test)
        layout.addWidget(self.test_btn)
        
        # 创建状态标签
        self.status_label = QtWidgets.QLabel("就绪")
        layout.addWidget(self.status_label)
        
        # 定时器
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_progress)
        self.current_value = 0
        
    def start_test(self):
        """开始测试"""
        self.current_value = 0
        self.progress_bar.setValue(0)
        self.status_label.setText("测试进行中...")
        self.test_btn.setEnabled(False)
        self.timer.start(100)  # 每100ms更新一次
        
    def update_progress(self):
        """更新进度"""
        self.current_value += 1
        self.progress_bar.setValue(self.current_value)
        
        # 强制UI更新
        QtWidgets.QApplication.processEvents()
        
        if self.current_value >= 100:
            self.timer.stop()
            self.status_label.setText("测试完成")
            self.test_btn.setEnabled(True)

def main():
    app = QtWidgets.QApplication(sys.argv)
    window = ProgressTestWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
