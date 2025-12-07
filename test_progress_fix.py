import sys
import time
from PyQt6 import QtWidgets, QtCore
from scanner_controller import ScannerController
from channel_model import ChannelListModel

class TestWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("进度条测试")
        self.resize(800, 600)
        
        # 创建模型和扫描器
        self.model = ChannelListModel()
        self.scanner = ScannerController(self.model, self)
        
        # 创建进度条
        self.progress_indicator = QtWidgets.QProgressBar()
        self.progress_indicator.setRange(0, 100)
        self.progress_indicator.setValue(0)
        self.progress_indicator.setTextVisible(True)
        
        # 创建测试按钮
        self.test_btn = QtWidgets.QPushButton("测试进度条")
        self.test_btn.clicked.connect(self.test_progress)
        
        # 创建布局
        central_widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.progress_indicator)
        layout.addWidget(self.test_btn)
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)
        
        # 连接进度条信号
        self._connect_progress_signals()
        
    def _connect_progress_signals(self):
        """连接进度条更新信号"""
        print("开始连接进度条更新信号")
        
        def update_progress_bars(cur, total):
            print(f"进度条更新信号收到: {cur}/{total}")
            if total > 0:
                progress_value = int(cur / total * 100)
                print(f"设置进度条值: {progress_value}%")
                self.progress_indicator.setValue(progress_value)
            else:
                print(f"total为0，不更新进度条")
                
        # 连接信号
        self.scanner.progress_updated.connect(update_progress_bars)
        print("进度条更新信号已连接")
        
    def test_progress(self):
        """测试进度条更新"""
        print("开始测试进度条")
        
        # 模拟进度更新
        for i in range(1, 11):
            current = i * 10
            total = 100
            print(f"发射进度信号: {current}/{total}")
            self.scanner.progress_updated.emit(current, total)
            QtWidgets.QApplication.processEvents()
            time.sleep(0.5)

def main():
    app = QtWidgets.QApplication(sys.argv)
    window = TestWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
