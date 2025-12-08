@echo off
chcp 65001 > nul
set PYTHONUTF8=1

echo ========================================
echo IPTV-Scanner-Editor-Pro 编译助手
echo ========================================
echo.

REM 设置Python路径
set "PYTHON_PATH=C:\Program Files\Python314"
set "PYINSTALLER_SCRIPT_PATH=C:\Users\sm\AppData\Roaming\Python\Python314\Scripts"

echo 1. 检查Python环境...
if not exist "%PYTHON_PATH%\python.exe" (
    echo 错误: 未找到Python 3.14
    echo 请确保Python 3.14已安装在: %PYTHON_PATH%
    pause
    exit /b 1
)
echo    Python 3.14 已找到: %PYTHON_PATH%

echo.
echo 2. 检查pyinstaller...
if not exist "%PYINSTALLER_SCRIPT_PATH%\pyinstaller.exe" (
    echo 错误: 未找到pyinstaller
    echo 正在安装pyinstaller...
    "%PYTHON_PATH%\python.exe" -m pip install pyinstaller
    if errorlevel 1 (
        echo 安装pyinstaller失败
        pause
        exit /b 1
    )
    echo   pyinstaller 安装成功
) else (
    echo   pyinstaller 已安装: %PYINSTALLER_SCRIPT_PATH%
)

echo.
echo 3. 添加到临时PATH...
set "OLD_PATH=%PATH%"
set "PATH=%PYINSTALLER_SCRIPT_PATH%;%PATH%"
echo   PATH已更新

echo.
echo 4. 选择编译选项:
echo   1) 完整编译 (包含VLC和FFmpeg)
echo   2) 简化编译 (不包含VLC和FFmpeg)
echo   3) 退出
echo.
set /p choice="请选择 (1-3): "

if "%choice%"=="1" (
    echo.
    echo 开始完整编译...
    call "一键编译.bat"
) else if "%choice%"=="2" (
    echo.
    echo 开始简化编译...
    call "一键编译-无vlc+ffprobe.bat"
) else if "%choice%"=="3" (
    echo.
    echo 退出编译助手
    pause
    exit /b 0
) else (
    echo.
    echo 无效选择
    pause
    exit /b 1
)

echo.
echo ========================================
echo 编译完成!
echo ========================================
pause
