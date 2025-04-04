@echo off
chcp 65001 > nul
set PYTHONUTF8=1
pyinstaller --onefile --windowed --icon=logo.ico --add-data "icons/*;icons" --add-data "ffmpeg/*;ffmpeg" --add-data "vlc/*;vlc" --hidden-import python-vlc --hidden-import ffmpeg --name "IPTV扫描编辑工具" --noconfirm --clean main.py
pause
