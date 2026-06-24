import subprocess
import sys
import logging
import os

if sys.platform == 'win32':
    try:
        import winreg
    except ImportError:
        winreg = None
else:
    winreg = None

logger = logging.getLogger(__name__)

_hdr_cache = None
_hdr_cache_time = 0
_HDR_CACHE_TTL = 30


def clear_hdr_cache():
    global _hdr_cache, _hdr_cache_time
    _hdr_cache = None
    _hdr_cache_time = 0


def is_android_hdr_enabled():
    global _hdr_cache, _hdr_cache_time
    import time
    now = time.monotonic()
    if _hdr_cache is not None and (now - _hdr_cache_time) < _HDR_CACHE_TTL:
        return _hdr_cache
    try:
        from PySide6.QtCore import QGuiApplication
        if QGuiApplication.instance():
            screen = QGuiApplication.primaryScreen()
            if screen:
                _hdr_cache = False
                _hdr_cache_time = now
                return False
    except Exception as e:
        logger.debug(f"Android HDR检测失败: {e}")
    _hdr_cache = False
    _hdr_cache_time = now
    return False


def is_macos_hdr_enabled():
    global _hdr_cache, _hdr_cache_time
    import time
    now = time.monotonic()
    if _hdr_cache is not None and (now - _hdr_cache_time) < _HDR_CACHE_TTL:
        return _hdr_cache
    try:
        result = subprocess.run(
            ['system_profiler', 'SPDisplaysDataType'],
            capture_output=True, text=True, timeout=10,
        )
        output = result.stdout
        _hdr_cache = 'HDR' in output
        _hdr_cache_time = now
        return _hdr_cache
    except Exception as e:
        logger.debug(f"macOS HDR检测失败: {e}")
        _hdr_cache = False
        _hdr_cache_time = now
        return False


def _check_windows_hdr_registry():
    try:
        base_path = r"SYSTEM\CurrentControlSet\Control\GraphicsDrivers"
        h_base = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base_path)
        i = 0
        while True:
            try:
                subkey_name = winreg.EnumKey(h_base, i)
                i += 1
                if subkey_name.lower() != 'monitordatastore':
                    continue
                h_mds = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, f"{base_path}\\{subkey_name}")
                j = 0
                while True:
                    try:
                        monitor_name = winreg.EnumKey(h_mds, j)
                        j += 1
                        h_mon = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, f"{base_path}\\{subkey_name}\\{monitor_name}")
                        try:
                            val, val_type = winreg.QueryValueEx(h_mon, 'HDREnabled')
                            winreg.CloseKey(h_mon)
                            if val_type == winreg.REG_DWORD and val == 1:
                                winreg.CloseKey(h_mds)
                                winreg.CloseKey(h_base)
                                logger.info(f"注册表HDR检测: 显示器 {monitor_name} HDREnabled=1")
                                return True
                        except OSError:
                            pass
                        winreg.CloseKey(h_mon)
                    except OSError:
                        break
                winreg.CloseKey(h_mds)
            except OSError:
                break
        winreg.CloseKey(h_base)
    except Exception as e:
        logger.debug(f"注册表HDR检测失败: {e}")
    return False


def is_windows_hdr_enabled():
    global _hdr_cache, _hdr_cache_time
    import time
    now = time.monotonic()
    if _hdr_cache is not None and (now - _hdr_cache_time) < _HDR_CACHE_TTL:
        return _hdr_cache

    result = _check_windows_hdr_registry()
    _hdr_cache = result
    _hdr_cache_time = now
    logger.info(f"Windows HDR检测(注册表): {'已启用' if result else '未启用'}")
    return result
