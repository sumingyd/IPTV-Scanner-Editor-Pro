@echo off
chcp 65001 > nul
set PYTHONUTF8=1

REM 添加pyinstaller到PATH（用户安装位置）
set "PYINSTALLER_PATH=C:\Users\sm\AppData\Roaming\Python\Python314\Scripts"
set "PATH=%PYINSTALLER_PATH%;%PATH%"

REM 自动检测Python路径
python -c "import sys; print(sys.prefix)" >nul 2>&1
if errorlevel 1 (
    echo 错误: 未找到Python环境或Python不可用
    pause
    exit /b 1
)

for /f "tokens=*" %%I in ('python -c "import sys; print(sys.prefix)"') do set PYTHON_PATH=%%I

echo 使用Python路径: %PYTHON_PATH%
echo pyinstaller路径: %PYINSTALLER_PATH%

pyinstaller --onefile --windowed --icon=logo.ico ^
--add-data "locales/zh.json:locales" ^
--add-data "locales/en.json:locales" ^
--add-data "logo.ico:." ^
--add-data "logo.png:." ^
--paths "%PYTHON_PATH%\Lib\site-packages" ^
--paths "." ^
--hidden-import python-vlc ^
--hidden-import ffmpeg ^
--runtime-hook=pyi_rth_vlc.py ^
--name "IPTV-novlc-noffprobe" ^
--noconfirm --clean main.py
pause
