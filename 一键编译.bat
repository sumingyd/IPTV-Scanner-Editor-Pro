@echo off
chcp 65001 > nul
set PYTHONUTF8=1
pyinstaller --onefile --windowed --icon=logo.ico ^
--add-data "icons/*;icons" ^
--add-data "ffmpeg/*;ffmpeg" ^
--add-data "vlc/*;vlc" ^
--add-data "vlc/plugins/*;vlc/plugins" ^
--add-data "ffmpeg/bin/*;ffmpeg/bin" ^
--add-data "ffmpeg/presets/*;ffmpeg/presets" ^
--paths "C:\Users\sm\AppData\Local\Programs\Python\Python312\Lib\site-packages" ^
--hidden-import python-vlc ^
--hidden-import ffmpeg ^
--runtime-hook=pyi_rth_vlc.py ^
--name "IPTV" ^
--noconfirm --clean main.py
pause
