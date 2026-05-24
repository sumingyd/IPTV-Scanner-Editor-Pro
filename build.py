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
    "--onefile",
    "--windowed",
    "--name", "IPTV Scanner Editor Pro",
    "--icon", str(PROJECT_ROOT / "resources" / "logo.ico"),
    "--add-data", f"{PROJECT_ROOT / 'mpv'};mpv",
    "--add-data", f"{PROJECT_ROOT / 'resources'};resources",
    "--hidden-import", "PyQt6.QtNetwork",
    "--hidden-import", "PyQt6.QtWidgets",
    "--hidden-import", "PyQt6.QtCore",
    "--hidden-import", "PyQt6.QtGui",
    "--hidden-import", "numpy",
    "--hidden-import", "requests",
    "--hidden-import", "aiohttp",
    "--hidden-import", "asyncio",
    "--hidden-import", "controllers",
    "--hidden-import", "controllers.catchup_controller",
    "--hidden-import", "controllers.channel_controller",
    "--hidden-import", "controllers.epg_controller",
    "--hidden-import", "controllers.event_handler",
    "--hidden-import", "controllers.main_window_protocol",
    "--hidden-import", "controllers.media_controller",
    "--hidden-import", "controllers.multi_screen_controller",
    "--hidden-import", "controllers.pip_controller",
    "--hidden-import", "controllers.playback_controller",
    "--hidden-import", "controllers.progress_controller",
    "--hidden-import", "controllers.settings_file_ops",
    "--hidden-import", "controllers.subscription_controller",
    "--hidden-import", "controllers.subscription_ui_controller",
    "--hidden-import", "controllers.ui_controller",
    "--hidden-import", "controllers.update_controller",
    "--hidden-import", "controllers.window_controller",
    "--hidden-import", "core",
    "--hidden-import", "core.application_state",
    "--hidden-import", "core.config_manager",
    "--hidden-import", "core.language_manager",
    "--hidden-import", "core.log_manager",
    "--hidden-import", "core.panel_visibility",
    "--hidden-import", "core.play_state",
    "--hidden-import", "core.subscription_manager",
    "--hidden-import", "core.version",
    "--hidden-import", "models",
    "--hidden-import", "models.channel_mappings",
    "--hidden-import", "models.channel_model",
    "--hidden-import", "services",
    "--hidden-import", "services.channel_classifier",
    "--hidden-import", "services.channel_cleaner",
    "--hidden-import", "services.epg_matcher",
    "--hidden-import", "services.logo_cache_service",
    "--hidden-import", "services.logo_matcher",
    "--hidden-import", "services.m3u_parser",
    "--hidden-import", "services.mpv_bindings",
    "--hidden-import", "services.mpv_common",
    "--hidden-import", "services.mpv_player_service",
    "--hidden-import", "services.mpv_validator_service",
    "--hidden-import", "services.network_preheat_service",
    "--hidden-import", "services.scanner_service",
    "--hidden-import", "services.thumbnail_service",
    "--hidden-import", "services.url_parser_service",
    "--hidden-import", "ui",
    "--hidden-import", "ui.dialogs",
    "--hidden-import", "ui.dialogs.about_dialog",
    "--hidden-import", "ui.dialogs.file_association_dialog",
    "--hidden-import", "ui.dialogs.mapping_manager_dialog",
    "--hidden-import", "ui.dialogs.scan_channel_dialog",
    "--hidden-import", "ui.floating_dialog",
    "--hidden-import", "ui.multi_screen_widget",
    "--hidden-import", "ui.styles",
    "--hidden-import", "ui.theme_manager",
    "--hidden-import", "utils",
    "--hidden-import", "utils.config_notifier",
    "--hidden-import", "utils.error_handler",
    "--hidden-import", "utils.general_utils",
    "--hidden-import", "utils.logging_helper",
    "--hidden-import", "utils.memory_manager",
    "--hidden-import", "utils.progress_manager",
    "--hidden-import", "utils.resource_cleaner",
    "--hidden-import", "utils.scan_state_manager",
    "--hidden-import", "utils.singleton",
    "--hidden-import", "utils.thread_safety",
    str(PROJECT_ROOT / "pyqt_player.py"),
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
