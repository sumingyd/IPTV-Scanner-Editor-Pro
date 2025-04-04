@echo off
chcp 65001 > nul
pyinstaller --onefile --windowed --icon=logo.ico --add-data "icons/*;icons" --add-data "ffmpeg/*;ffmpeg" --add-data "vlc/*;vlc" --name "IPTV_Scanner_Editor" --noconfirm --clean main.py
pause
