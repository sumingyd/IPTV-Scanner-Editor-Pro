"""简单的进度条测试程序"""

import sys
from PyQt6 import QtWidgets, QtCore
from progress_manager_new import SimpleProgressManager

class TestWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("进度条测试")
        self.setGeometry(100, 100, 400, 200)
        
        # 创建中央部件
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        
        # 创建布局
        layout = QtWidgets.QVBoxLayout()
        central_widget.setLayout(layout)
        
        # 创建进度条
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p%")
        layout.addWidget(self.progress_bar)
        
        # 创建按钮
        self.start_btn = QtWidgets.QPushButton("开始测试")
        self.start_btn.clicked.connect(self.start_test)
        layout.addWidget(self.start_btn)
        
        # 创建进度条管理器
        self.progress_manager = SimpleProgressManager(self.progress_bar)
        
        # 创建模拟的扫描器
        self.mock_scanner = MockScanner()
        
        # 连接信号
        self.progress_manager.connect_scanner(self.mock_scanner)
        
    def start_test(self):
        """开始测试"""
        self.start_btn.setEnabled(False)
        self.mock_scanner.start_mock_scan()
        
class MockScanner(QtCore.QObject):
    """模拟扫描器"""
    
    progress_updated = QtCore.pyqtSignal(int, int)
    scan_completed = QtCore.pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_progress)
        self.current = 0
        self.total = 100
        
    def start_mock_scan(self):
        """开始模拟扫描"""
        self.current = 0
        self.timer.start(100)  # 每100ms更新一次
        
    def update_progress(self):
        """更新进度"""
        self.current += 1
        self.progress_updated.emit(self.current, self.total)
        
        if self.current >= self.total:
            self.timer.stop()
            self.scan_completed.emit()

def main():
    app = QtWidgets.QApplication(sys.argv)
    window = TestWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
