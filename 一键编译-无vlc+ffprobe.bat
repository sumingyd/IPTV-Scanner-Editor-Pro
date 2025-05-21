@echo off
chcp 65001 > nul
set PYTHONUTF8=1
pyinstaller --onefile --windowed --icon=logo.ico ^
--add-data "local_channel_mappings.txt;." ^
--paths "C:\Users\sm\AppData\Local\Programs\Python\Python312\Lib\site-packages" ^
--hidden-import python-vlc ^
--hidden-import ffmpeg ^
--runtime-hook=pyi_rth_vlc.py ^
--name "IPTV-novlc-noffprobe" ^
--noconfirm --clean main.py
pause
