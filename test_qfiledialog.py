import sys
import os

# 在导入PyQt6之前重定向标准输出
import sys
import os

# 保存原始的文件描述符
import ctypes

# 使用Windows API重定向标准输出
def suppress_output():
    """重定向标准输出和标准错误到空设备"""
    # 获取空设备的文件描述符
    NULL_DEVICE = os.open(os.devnull, os.O_WRONLY)
    
    # 保存原始的标准输出和标准错误
    original_stdout = os.dup(1)
    original_stderr = os.dup(2)
    
    # 重定向标准输出和标准错误到空设备
    os.dup2(NULL_DEVICE, 1)
    os.dup2(NULL_DEVICE, 2)
    
    return original_stdout, original_stderr, NULL_DEVICE

def restore_output(original_stdout, original_stderr, null_device):
    """恢复标准输出和标准错误"""
    # 恢复原始的标准输出和标准错误
    os.dup2(original_stdout, 1)
    os.dup2(original_stderr, 2)
    
    # 关闭文件描述符
    os.close(original_stdout)
    os.close(original_stderr)
    os.close(null_device)

# 重定向输出
original_stdout, original_stderr, null_device = suppress_output()

from PyQt6.QtWidgets import QApplication, QFileDialog

if __name__ == "__main__":
    try:
        app = QApplication(sys.argv)
        file_path, _ = QFileDialog.getOpenFileName(
            None,
            "打开文件",
            "",
            "所有文件 (*.*)"
        )
    finally:
        # 恢复输出
        restore_output(original_stdout, original_stderr, null_device)
        sys.exit(app.exec())