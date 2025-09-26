@echo off
chcp 65001 > nul
set PYTHONUTF8=1

REM 自动检测Python路径
for /f "tokens=2 delims==" %%I in ('python -c "import sys; print(sys.prefix)"') do set PYTHON_PATH=%%I
if "%PYTHON_PATH%"=="" (
    echo 错误: 未找到Python环境
    pause
    exit /b 1
)

echo 使用Python路径: %PYTHON_PATH%

pyinstaller --onefile --windowed --icon=logo.ico ^
--add-data "icons/*:icons" ^
--add-data "ffmpeg/*:ffmpeg" ^
--add-data "vlc/*:vlc" ^
--add-data "vlc/plugins/*:vlc/plugins" ^
--add-data "ffmpeg/bin/*:ffmpeg/bin" ^
--add-data "ffmpeg/presets/*:ffmpeg/presets" ^
--add-data "locales/zh.json:locales" ^
--add-data "locales/en.json:locales" ^
--paths "%PYTHON_PATH%\Lib\site-packages" ^
--paths "." ^
--hidden-import python-vlc ^
--hidden-import ffmpeg ^
--runtime-hook=pyi_rth_vlc.py ^
--name "IPTV" ^
--noconfirm --clean main.py
pause
