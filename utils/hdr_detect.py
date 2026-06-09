import subprocess
import logging
import os

logger = logging.getLogger(__name__)

_hdr_cache = None


def is_windows_hdr_enabled():
    global _hdr_cache
    if _hdr_cache is not None:
        return _hdr_cache

    try:
        script = os.path.join(os.path.dirname(__file__), '_hdr_check.ps1')
        with open(script, 'w', encoding='utf-8') as f:
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
        try:
            os.remove(script)
        except OSError:
            pass
        kind = result.stdout.strip()
        logger.info(f"Windows AdvancedColorKind: {kind}")
        _hdr_cache = kind in ('Hdr', 'Wcg')
        return _hdr_cache
    except Exception as e:
        logger.debug(f"HDR检测失败: {e}")

    _hdr_cache = False
    return False
