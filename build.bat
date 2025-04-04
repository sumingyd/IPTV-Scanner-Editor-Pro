@echo off
pyinstaller --onefile --windowed --icon=logo.ico --add-data "icons/*;icons" --add-data "ffmpeg/*;ffmpeg" --add-data "vlc/*;vlc" --name "IPTV扫描编辑工具" --noconfirm --clean main.py
pause
