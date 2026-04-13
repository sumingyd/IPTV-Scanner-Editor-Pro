#!/usr/bin/env python3
"""
IPTV Scanner Editor Pro 打包脚本
使用 PyInstaller 将项目打包为单个 EXE 文件
"""

import os
import sys
import shutil
from pathlib import Path

# 确保使用正确的 Python 环境
print(f"当前 Python 版本: {sys.version}")
print(f"当前工作目录: {os.getcwd()}")

# 项目根目录
PROJECT_ROOT = Path(__file__).parent
print(f"项目根目录: {PROJECT_ROOT}")

# 检查 PyInstaller 是否安装
try:
    import PyInstaller
    print(f"PyInstaller 版本: {PyInstaller.__version__}")
except ImportError:
    print("错误: PyInstaller 未安装，请运行: pip install pyinstaller")
    sys.exit(1)

# 定义打包命令
PYINSTALLER_CMD = [
    sys.executable,
    "-m", "PyInstaller",
    "--onefile",  # 生成单个 EXE 文件
    "--windowed",  # 无控制台窗口
    "--name", "IPTV Scanner Editor Pro",  # 应用名称
    "--icon", str(PROJECT_ROOT / "resources" / "logo.ico"),
    "--add-data", f"{PROJECT_ROOT / 'mpv'};mpv",
    "--add-data", f"{PROJECT_ROOT / 'resources'};resources",
    "--hidden-import", "PyQt6.QtNetwork",  # 隐藏导入
    "--hidden-import", "PyQt6.QtWidgets",  # 隐藏导入
    "--hidden-import", "PyQt6.QtCore",  # 隐藏导入
    "--hidden-import", "PyQt6.QtGui",  # 隐藏导入
    "--hidden-import", "numpy",  # 隐藏导入
    "--hidden-import", "requests",  # 隐藏导入
    "--hidden-import", "aiohttp",  # 隐藏导入
    "--hidden-import", "asyncio",  # 隐藏导入
    "--hidden-import", "json",  # 隐藏导入
    "--hidden-import", "os",  # 隐藏导入
    "--hidden-import", "sys",  # 隐藏导入
    "--hidden-import", "time",  # 隐藏导入
    "--hidden-import", "threading",  # 隐藏导入
    "--hidden-import", "subprocess",  # 隐藏导入
    "--hidden-import", "urllib",  # 隐藏导入
    "--hidden-import", "socket",  # 隐藏导入
    "--hidden-import", "datetime",  # 隐藏导入
    "--hidden-import", "re",  # 隐藏导入
    "--hidden-import", "glob",  # 隐藏导入
    "--hidden-import", "pathlib",  # 隐藏导入
    "--hidden-import", "shutil",  # 隐藏导入
    "--hidden-import", "typing",  # 隐藏导入
    "--hidden-import", "collections",  # 隐藏导入
    "--hidden-import", "queue",  # 隐藏导入
    "--hidden-import", "traceback",  # 隐藏导入
    "--hidden-import", "inspect",  # 隐藏导入
    "--hidden-import", "gc",  # 隐藏导入
    "--hidden-import", "platform",  # 隐藏导入
    "--hidden-import", "math",  # 隐藏导入
    "--hidden-import", "random",  # 隐藏导入
    "--hidden-import", "hashlib",  # 隐藏导入
    "--hidden-import", "base64",  # 隐藏导入
    "--hidden-import", "io",  # 隐藏导入
    "--hidden-import", "zipfile",  # 隐藏导入
    "--hidden-import", "tarfile",  # 隐藏导入
    "--hidden-import", "tempfile",  # 隐藏导入
    "--hidden-import", "select",  # 隐藏导入
    "--hidden-import", "struct",  # 隐藏导入
    "--hidden-import", "array",  # 隐藏导入
    "--hidden-import", "bisect",  # 隐藏导入
    "--hidden-import", "functools",  # 隐藏导入
    "--hidden-import", "itertools",  # 隐藏导入
    "--hidden-import", "operator",  # 隐藏导入
    "--hidden-import", "heapq",  # 隐藏导入
    "--hidden-import", "threading",  # 隐藏导入
    "--hidden-import", "queue",  # 隐藏导入
    "--hidden-import", "concurrent.futures",  # 隐藏导入
    "--hidden-import", "multiprocessing",  # 隐藏导入
    "--hidden-import", "logging",  # 隐藏导入
    "--hidden-import", "configparser",  # 隐藏导入
    "--hidden-import", "xml.etree.ElementTree",  # 隐藏导入
    "--hidden-import", "html.parser",  # 隐藏导入
    "--hidden-import", "http.client",  # 隐藏导入
    "--hidden-import", "ssl",  # 隐藏导入
    "--hidden-import", "tkinter",  # 隐藏导入（用于文件对话框）
    "--hidden-import", "tkinter.filedialog",  # 隐藏导入
    "--hidden-import", "tkinter.messagebox",  # 隐藏导入
    str(PROJECT_ROOT / "pyqt_player.py"),  # 主入口文件
]

# 清理之前的构建结果
def clean_build():
    """清理之前的构建结果"""
    print("清理之前的构建结果...")
    
    # 移除 build 目录
    build_dir = PROJECT_ROOT / "build"
    if build_dir.exists():
        print(f"移除构建目录: {build_dir}")
        shutil.rmtree(build_dir)
    
    # 移除 dist 目录
    dist_dir = PROJECT_ROOT / "dist"
    if dist_dir.exists():
        print(f"移除发布目录: {dist_dir}")
        shutil.rmtree(dist_dir)
    
    # 移除 spec 文件
    spec_file = PROJECT_ROOT / "pyqt_player.spec"
    if spec_file.exists():
        print(f"移除 spec 文件: {spec_file}")
        spec_file.unlink()
    
    print("清理完成")

# 运行打包命令
def run_build():
    """运行打包命令"""
    print("开始打包...")
    print(f"执行命令: {' '.join(PYINSTALLER_CMD)}")
    
    try:
        import subprocess
        result = subprocess.run(PYINSTALLER_CMD, cwd=PROJECT_ROOT, capture_output=True, text=True)
        
        print(f"返回码: {result.returncode}")
        
        if result.stdout:
            print("标准输出:")
            print(result.stdout)
        
        if result.stderr:
            print("标准错误:")
            print(result.stderr)
        
        if result.returncode == 0:
            print("打包成功!")
            # 复制配置文件到 dist 目录
            dist_dir = PROJECT_ROOT / "dist"
            if dist_dir.exists():
                config_file = PROJECT_ROOT / "config.ini"
                if config_file.exists():
                    dest_config = dist_dir / "config.ini"
                    print(f"复制配置文件到: {dest_config}")
                    shutil.copy2(config_file, dest_config)
                else:
                    print("警告: config.ini 文件不存在")
            else:
                print("警告: dist 目录不存在")
            
            print("打包完成! 可执行文件位于: dist/IPTV Scanner Editor Pro.exe")
        else:
            print("打包失败!")
            sys.exit(1)
            
    except Exception as e:
        print(f"打包过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    print("=== IPTV Scanner Editor Pro 打包脚本 ===")
    
    # 清理之前的构建
    clean_build()
    
    # 运行打包
    run_build()
    
    print("=== 打包脚本执行完成 ===")
