#!/usr/bin/env python3
"""
IPTV Scanner Editor Pro 打包脚本
使用 PyInstaller 将项目打包为可执行文件
支持 Windows (.exe) 和 macOS (.app)
"""

import os
import sys
import shutil
import plistlib
import subprocess
import urllib.request
from pathlib import Path


def _download(url, dest):
    print(f"下载: {url}")
    print(f"保存到: {dest}")
    urllib.request.urlretrieve(url, dest)
    print(f"下载完成: {dest}")


def _run(cmd, **kwargs):
    print(f"执行: {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    return subprocess.run(cmd, **kwargs)

print(f"当前 Python 版本: {sys.version}")
print(f"当前工作目录: {os.getcwd()}")
print(f"当前平台: {sys.platform}")

PROJECT_ROOT = Path(__file__).parent
print(f"项目根目录: {PROJECT_ROOT}")

try:
    import PyInstaller
    print(f"PyInstaller 版本: {PyInstaller.__version__}")
except ImportError:
    print("错误: PyInstaller 未安装，请运行: pip install pyinstaller")
    sys.exit(1)

IS_WINDOWS = sys.platform == 'win32'
IS_MACOS = sys.platform == 'darwin'
IS_LINUX = sys.platform.startswith('linux') and not getattr(sys, 'platform', '') == 'android'
IS_ANDROID = getattr(sys, 'platform', '') == 'android' or 'ANDROID_ARGUMENT' in os.environ

APP_NAME = "IPTV Scanner Editor Pro"
BUNDLE_ID = "com.iptv-scanner-editor-pro.app"

if IS_WINDOWS:
    DATA_SEP = ';'
    ICON_PATH = str(PROJECT_ROOT / "resources" / "logo.ico")
elif IS_MACOS:
    DATA_SEP = ':'
    ICON_PATH = str(PROJECT_ROOT / "resources" / "logo.icns") if (PROJECT_ROOT / "resources" / "logo.icns").exists() else None
elif IS_ANDROID:
    DATA_SEP = ':'
    ICON_PATH = None
elif IS_LINUX:
    DATA_SEP = ':'
    ICON_PATH = str(PROJECT_ROOT / "resources" / "logo.png") if (PROJECT_ROOT / "resources" / "logo.png").exists() else None
else:
    DATA_SEP = ':'
    ICON_PATH = None

HIDDEN_IMPORTS = [
    "PySide6.QtNetwork",
    "PySide6.QtWidgets",
    "PySide6.QtCore",
    "PySide6.QtGui",
    "numpy",
    "requests",
    "aiohttp",
    "asyncio",
    "utils.platform_utils",
    "controllers",
    "controllers.catchup_controller",
    "controllers.channel_controller",
    "controllers.epg_controller",
    "controllers.epg_reminder_controller",
    "controllers.event_handler",
    "controllers.favorites_controller",
    "controllers.main_window_protocol",
    "controllers.media_controller",
    "controllers.multi_screen_controller",
    "controllers.pip_controller",
    "controllers.playback_controller",
    "controllers.progress_controller",
    "controllers.settings_file_ops",
    "controllers.subscription_controller",
    "controllers.subscription_ui_controller",
    "controllers.ui_controller",
    "controllers.update_controller",
    "controllers.window_controller",
    "mixins",
    "mixins.server_mixin",
    "mixins.tray_mixin",
    "mixins.update_mixin",
    "mixins.thumbnail_mixin",
    "mixins.file_ops_mixin",
    "mixins.panel_mixin",
    "mixins.progress_mixin",
    "mixins.playback_mixin",
    "mixins.epg_mixin",
    "mixins.channel_mixin",
    "mixins.settings_mixin",
    "mixins.window_mixin",
    "mixins.control_panel_mixin",
    "mixins.playlist_panel_mixin",
    "mixins.event_mixin",
    "core",
    "core.application_state",
    "core.config_manager",
    "core.language_manager",
    "core.log_manager",
    "core.panel_visibility",
    "core.play_state",
    "core.subscription_manager",
    "core.version",
    "models",
    "models.channel_mappings",
    "models.channel_model",
    "services",
    "services.batch_edit_service",
    "services.channel_classifier",
    "services.channel_cleaner",
    "services.channel_rating_service",
    "services.channel_quick_jump_service",
    "services.channel_dedup_service",
    "services.stream_quality_scorer",
    "services.epg_matcher",
    "services.epg_reminder_service",
    "services.epg_search_service",
    "services.favorites_service",
    "services.fcc_service",
    "services.logo_cache_service",
    "services.logo_matcher",
    "services.m3u_parser",
    "services.mpv_bindings",
    "services.mpv_common",
    "services.mpv_player_service",
    "services.ffprobe_validator_service",
    "services.mpv_validator_service",
    "services.network_preheat_service",
    "services.scanner_service",
    "services.thumbnail_service",
    "services.url_parser_service",
    "server",
    "server.app",
    "server.routes",
    "ui",
    "ui.dialogs",
    "ui.dialogs.about_dialog",
    "ui.dialogs.epg_timeline_dialog",
    "ui.dialogs.file_association_dialog",
    "ui.dialogs.mapping_manager_dialog",
    "ui.dialogs.scan_channel_dialog",
    "ui.dialogs.subscription_settings_dialog",
    "ui.dialogs.reminder_popup",
    "ui.dialogs.reminder_manager_dialog",
    "ui.dialogs.unified_search_dialog",
    "ui.dialogs.video_open_dialog",
    "ui.dialogs.global_search_dialog",
    "ui.dialogs.epg_search_dialog",
    "ui.epg_timeline_widget",
    "ui.floating_dialog",
    "ui.multi_screen_widget",
    "ui.virtual_channel_list",
    "ui.menu_proxy_style",
    "ui.cache_progress_slider",
    "ui.channel_transition_overlay",
    "ui.styles",
    "ui.theme_manager",
    "utils",
    "utils.config_notifier",
    "utils.error_handler",
    "utils.general_utils",
    "utils.hdr_detect",
    "utils.logging_helper",
    "utils.memory_manager",
    "utils.progress_manager",
    "utils.resource_cleaner",
    "utils.scan_state_manager",
    "utils.singleton",
    "utils.thread_safety",
]


def prepare_macos_dependencies():
    mpv_dir = PROJECT_ROOT / "mpv"
    mpv_dir.mkdir(exist_ok=True)
    dylib_dest = mpv_dir / "libmpv.2.dylib"

    if not dylib_dest.exists():
        for src in [
            Path("/usr/local/lib/libmpv.2.dylib"),
            Path("/opt/homebrew/lib/libmpv.2.dylib"),
        ]:
            if src.exists():
                shutil.copy2(src, dylib_dest)
                print(f"libmpv.2.dylib 已从 {src} 复制到 {dylib_dest}")
                break
        else:
            print("错误: 未找到 libmpv.2.dylib，请先安装: brew install mpv")
            print("  或手动放置到: mpv/libmpv.2.dylib")
            sys.exit(1)
    else:
        print(f"libmpv.2.dylib 已就绪: {dylib_dest}")

    ffmpeg_dir = PROJECT_ROOT / "ffmpeg"
    ffmpeg_dir.mkdir(exist_ok=True)
    ffprobe_dest = ffmpeg_dir / "ffprobe"

    if not ffprobe_dest.exists():
        ffprobe_found = False
        for src in [
            Path("/opt/homebrew/bin/ffprobe"),
            Path("/usr/local/bin/ffprobe"),
        ]:
            if src.exists():
                shutil.copy2(src, ffprobe_dest)
                os.chmod(ffprobe_dest, 0o755)
                print(f"ffprobe 已从 {src} 复制到 {ffprobe_dest}")
                ffprobe_found = True
                break

        if not ffprobe_found:
            result = _run(["which", "ffprobe"], capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip():
                src = Path(result.stdout.strip())
                shutil.copy2(src, ffprobe_dest)
                os.chmod(ffprobe_dest, 0o755)
                print(f"ffprobe 已从 {src} 复制到 {ffprobe_dest}")
                ffprobe_found = True

        if not ffprobe_found:
            import platform
            mac_arch = platform.machine()
            if mac_arch == 'arm64':
                ffprobe_url = "https://www.osxexperts.net/ffprobe81arm.zip"
            else:
                ffprobe_url = "https://www.osxexperts.net/ffprobe80intel.zip"

            zip_path = PROJECT_ROOT / "_ffprobe_download.zip"
            try:
                _download(ffprobe_url, str(zip_path))
                extract_dir = PROJECT_ROOT / "_ffprobe_extract"
                extract_dir.mkdir(exist_ok=True)
                _run(["unzip", "-o", str(zip_path), "-d", str(extract_dir)], check=True)
                extracted = list(extract_dir.rglob("ffprobe"))
                if extracted:
                    shutil.copy2(extracted[0], ffprobe_dest)
                    os.chmod(ffprobe_dest, 0o755)
                    print(f"ffprobe 已下载并放置到: {ffprobe_dest}")
                else:
                    print("错误: 下载的 zip 中未找到 ffprobe")
                    sys.exit(1)
            finally:
                for p in [zip_path, PROJECT_ROOT / "_ffprobe_extract"]:
                    if p.exists():
                        if p.is_dir():
                            shutil.rmtree(p)
                        else:
                            p.unlink()
    else:
        print(f"ffprobe 已就绪: {ffprobe_dest}")


def prepare_windows_dependencies():
    mpv_dir = PROJECT_ROOT / "mpv"
    if not (mpv_dir / "libmpv-2.dll").exists():
        print("错误: 未找到 mpv/libmpv-2.dll，请手动放置到 mpv/ 目录")
        sys.exit(1)
    print(f"libmpv-2.dll 已就绪: {mpv_dir / 'libmpv-2.dll'}")

    ffmpeg_dir = PROJECT_ROOT / "ffmpeg"
    if not (ffmpeg_dir / "ffprobe.exe").exists():
        print("错误: 未找到 ffmpeg/ffprobe.exe，请手动放置到 ffmpeg/ 目录")
        sys.exit(1)
    print(f"ffprobe.exe 已就绪: {ffmpeg_dir / 'ffprobe.exe'}")


def build_macos():
    prepare_macos_dependencies()
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--windowed",
        "--name", APP_NAME,
        "--osx-bundle-identifier", BUNDLE_ID,
    ]
    if ICON_PATH and os.path.exists(ICON_PATH):
        cmd.extend(["--icon", ICON_PATH])
    cmd.extend([
        "--add-data", f"{PROJECT_ROOT / 'mpv'}{DATA_SEP}mpv",
        "--add-data", f"{PROJECT_ROOT / 'ffmpeg'}{DATA_SEP}ffmpeg",
        "--add-data", f"{PROJECT_ROOT / 'resources'}{DATA_SEP}resources",
    ])
    for imp in HIDDEN_IMPORTS:
        cmd.extend(["--hidden-import", imp])
    cmd.append(str(PROJECT_ROOT / "pyqt_player.py"))
    return cmd


def build_windows():
    prepare_windows_dependencies()
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--windowed",
        "--name", APP_NAME,
    ]
    if ICON_PATH and os.path.exists(ICON_PATH):
        cmd.extend(["--icon", ICON_PATH])
    cmd.extend([
        "--add-data", f"{PROJECT_ROOT / 'mpv'}{DATA_SEP}mpv",
        "--add-data", f"{PROJECT_ROOT / 'ffmpeg'}{DATA_SEP}ffmpeg",
        "--add-data", f"{PROJECT_ROOT / 'resources'}{DATA_SEP}resources",
    ])
    for imp in HIDDEN_IMPORTS:
        cmd.extend(["--hidden-import", imp])
    cmd.append(str(PROJECT_ROOT / "pyqt_player.py"))
    return cmd


def prepare_linux_dependencies():
    mpv_dir = PROJECT_ROOT / "mpv"
    mpv_dir.mkdir(exist_ok=True)
    has_mpv = any((mpv_dir / name).exists() for name in ['libmpv.so.2', 'libmpv.so.1', 'libmpv.so'])
    if not has_mpv:
        print("提示: 未找到打包的libmpv，运行时将使用系统安装的libmpv")
        print("  如需打包，请手动放置到 mpv/ 目录，或执行: sudo apt install libmpv-dev")
    else:
        print(f"libmpv.so 已就绪: {mpv_dir}")

    ffmpeg_dir = PROJECT_ROOT / "ffmpeg"
    ffmpeg_dir.mkdir(exist_ok=True)
    if not (ffmpeg_dir / "ffprobe").exists():
        print("错误: 未找到 ffmpeg/ffprobe，请手动放置到 ffmpeg/ 目录")
        print("  或执行: sudo apt install ffmpeg")
        sys.exit(1)
    print(f"ffprobe 已就绪: {ffmpeg_dir / 'ffprobe'}")


def build_linux():
    prepare_linux_dependencies()
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--windowed",
        "--name", APP_NAME,
    ]
    if ICON_PATH and os.path.exists(ICON_PATH):
        cmd.extend(["--icon", ICON_PATH])
    cmd.extend([
        "--add-data", f"{PROJECT_ROOT / 'mpv'}{DATA_SEP}mpv",
        "--add-data", f"{PROJECT_ROOT / 'ffmpeg'}{DATA_SEP}ffmpeg",
        "--add-data", f"{PROJECT_ROOT / 'resources'}{DATA_SEP}resources",
    ])
    for imp in HIDDEN_IMPORTS:
        cmd.extend(["--hidden-import", imp])
    cmd.append(str(PROJECT_ROOT / "pyqt_player.py"))
    return cmd


def prepare_android_dependencies():
    mpv_dir = PROJECT_ROOT / "mpv"
    mpv_dir.mkdir(exist_ok=True)
    has_mpv = any((mpv_dir / name).exists() for name in ['libmpv.so', 'libmpv.so.2', 'libmpv.so.1'])
    if not has_mpv:
        print("提示: 未找到打包的libmpv.so，运行时将使用系统安装的libmpv")
    else:
        print(f"libmpv.so 已就绪: {mpv_dir}")

    ffmpeg_dir = PROJECT_ROOT / "ffmpeg"
    ffmpeg_dir.mkdir(exist_ok=True)
    if not (ffmpeg_dir / "ffprobe").exists():
        print("提示: 未找到 ffmpeg/ffprobe，部分功能可能受限")
    else:
        print(f"ffprobe 已就绪: {ffmpeg_dir / 'ffprobe'}")


def build_android():
    prepare_android_dependencies()
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--windowed",
        "--name", APP_NAME,
    ]
    cmd.extend([
        "--add-data", f"{PROJECT_ROOT / 'mpv'}{DATA_SEP}mpv",
        "--add-data", f"{PROJECT_ROOT / 'ffmpeg'}{DATA_SEP}ffmpeg",
        "--add-data", f"{PROJECT_ROOT / 'resources'}{DATA_SEP}resources",
    ])
    for imp in HIDDEN_IMPORTS:
        cmd.extend(["--hidden-import", imp])
    cmd.append(str(PROJECT_ROOT / "pyqt_player.py"))
    return cmd


def post_process_macos_app():
    app_path = PROJECT_ROOT / "dist" / f"{APP_NAME}.app"
    if not app_path.exists():
        print(f"警告: .app 未找到: {app_path}")
        return

    info_plist_path = app_path / "Contents" / "Info.plist"
    if info_plist_path.exists():
        with open(info_plist_path, 'rb') as f:
            plist = plistlib.load(f)
    else:
        plist = {}

    plist.update({
        'CFBundleName': APP_NAME,
        'CFBundleDisplayName': APP_NAME,
        'CFBundleIdentifier': BUNDLE_ID,
        'CFBundleVersion': '47.1.0',
        'CFBundleShortVersionString': '47.1.0',
        'CFBundlePackageType': 'APPL',
        'CFBundleInfoDictionaryVersion': '6.0',
        'LSMinimumSystemVersion': '10.15',
        'NSHighResolutionCapable': True,
        'NSSupportsAutomaticGraphicsSwitching': True,
        'CFBundleDocumentTypes': [
            {
                'CFBundleTypeName': 'M3U Playlist',
                'CFBundleTypeRole': 'Viewer',
                'LSItemContentTypes': ['public.m3u-playlist'],
                'CFBundleTypeExtensions': ['m3u', 'm3u8'],
            },
        ],
        'UTImportedTypeDeclarations': [
            {
                'UTTypeIdentifier': 'public.m3u-playlist',
                'UTTypeConformsTo': ['public.text'],
                'UTTypeDescription': 'M3U Playlist',
                'UTTypeTagSpecification': {
                    'public.filename-extension': ['m3u', 'm3u8'],
                },
            },
        ],
    })

    with open(info_plist_path, 'wb') as f:
        plistlib.dump(plist, f)

    print(f"Info.plist 已更新: {info_plist_path}")

    print(f"macOS .app 打包完成: {app_path}")


def clean_build():
    print("清理之前的构建结果...")
    build_dir = PROJECT_ROOT / "build"
    if build_dir.exists():
        print(f"移除构建目录: {build_dir}")
        shutil.rmtree(build_dir)
    dist_dir = PROJECT_ROOT / "dist"
    if dist_dir.exists():
        print(f"移除发布目录: {dist_dir}")
        shutil.rmtree(dist_dir)
    spec_file = PROJECT_ROOT / "pyqt_player.spec"
    if spec_file.exists():
        print(f"移除 spec 文件: {spec_file}")
        spec_file.unlink()
    print("清理完成")


def run_build():
    if IS_MACOS:
        cmd = build_macos()
    elif IS_ANDROID:
        cmd = build_android()
    elif IS_LINUX:
        cmd = build_linux()
    else:
        cmd = build_windows()

    print("开始打包...")
    print(f"执行命令: {' '.join(cmd)}")

    try:
        import subprocess
        result = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True)

        print(f"返回码: {result.returncode}")

        if result.stdout:
            print("标准输出:")
            print(result.stdout)

        if result.stderr:
            print("标准错误:")
            print(result.stderr)

        if result.returncode != 0:
            print("打包失败!")
            sys.exit(1)

        print("打包成功!")

        dist_dir = PROJECT_ROOT / "dist"
        if dist_dir.exists():
            config_file = PROJECT_ROOT / "config.ini"
            if config_file.exists():
                if IS_MACOS:
                    app_resources = dist_dir / f"{APP_NAME}.app" / "Contents" / "Resources"
                    app_resources.mkdir(parents=True, exist_ok=True)
                    dest_config = app_resources / "config.ini"
                else:
                    dest_config = dist_dir / "config.ini"
                print(f"复制配置文件到: {dest_config}")
                shutil.copy2(config_file, dest_config)
            else:
                print("警告: config.ini 文件不存在")

        if IS_MACOS:
            post_process_macos_app()
            print(f"打包完成! .app 位于: dist/{APP_NAME}.app")
        elif IS_ANDROID:
            print(f"打包完成! 可执行文件位于: dist/{APP_NAME}")
        elif IS_LINUX:
            print(f"打包完成! 可执行文件位于: dist/{APP_NAME}")
        else:
            print(f"打包完成! 可执行文件位于: dist/{APP_NAME}.exe")

    except Exception as e:
        print(f"打包过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    print("=== IPTV Scanner Editor Pro 打包脚本 ===")
    clean_build()
    run_build()
    print("=== 打包脚本执行完成 ===")
