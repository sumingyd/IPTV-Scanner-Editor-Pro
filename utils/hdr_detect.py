import subprocess
import logging
import os
import tempfile

logger = logging.getLogger(__name__)

_hdr_cache = None
_hdr_cache_time = 0
_HDR_CACHE_TTL = 30


def clear_hdr_cache():
    global _hdr_cache, _hdr_cache_time
    _hdr_cache = None
    _hdr_cache_time = 0


def is_windows_hdr_enabled():
    global _hdr_cache, _hdr_cache_time
    import time
    now = time.monotonic()
    if _hdr_cache is not None and (now - _hdr_cache_time) < _HDR_CACHE_TTL:
        return _hdr_cache

    script = None
    try:
        fd, script = tempfile.mkstemp(suffix='.ps1', prefix='hdr_check_')
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(
                '[void][Windows.Graphics.Display.DisplayInformation,Windows.Graphics.Display,ContentType=WindowsRuntime]\n'
                '$di = [Windows.Graphics.Display.DisplayInformation]::GetForCurrentView()\n'
                '$aci = $di.GetAdvancedColorInfo()\n'
                'Write-Output $aci.CurrentAdvancedColorKind\n'
            )
        result = subprocess.run(
            ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', script],
            capture_output=True, text=True, timeout=15
        )
        kind = result.stdout.strip()
        logger.info(f"Windows AdvancedColorKind: {kind}")
        _hdr_cache = kind in ('Hdr', 'Wcg')
        _hdr_cache_time = now
        return _hdr_cache
    except Exception as e:
        logger.debug(f"HDR检测失败: {e}")
        _hdr_cache = False
        _hdr_cache_time = now
        return False
    finally:
        if script:
            try:
                os.remove(script)
            except OSError:
                pass
