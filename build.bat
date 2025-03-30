@echo off
pyinstaller --onefile --windowed --icon=logo.ico --add-data "icons/*;icons" --version-file=version_info.txt --name "IPTV扫描编辑工具" --noconfirm --clean main.py
pause
