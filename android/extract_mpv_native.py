#!/usr/bin/env python3
"""
提取 mpv-android 的 native 库到 jniLibs 目录。
与 CI 工作流 .github/workflows/build.yml 的步骤一致。

CI 下载 URL:
  https://github.com/mpv-android/mpv-android/releases/download/2026-04-25/app-default-{arch}-release.apk

本地仓库已有 mpv-arm64.apk 和 mpv-x86_64.apk（可能来自之前下载），
但缺少 armeabi-v7a 和 x86 架构的 APK。

此脚本下载所有 4 种架构的 APK 并提取 .so 文件到 app/src/main/jniLibs/。
"""
import os
import sys
import zipfile
import urllib.request
import shutil

ANDROID_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_URL = "https://github.com/mpv-android/mpv-android/releases/download/2026-04-25"
ARCHS = ["arm64-v8a", "armeabi-v7a", "x86_64", "x86"]
JNILIBS_DIR = os.path.join(ANDROID_DIR, "app", "src", "main", "jniLibs")

# 本地已有的 APK 文件名映射
LOCAL_APK_MAP = {
    "arm64-v8a": "mpv-arm64.apk",
    "x86_64": "mpv-x86_64.apk",
}


def download_apk(arch):
    """下载指定架构的 mpv-android APK"""
    apk_name = f"mpv-{arch}.apk"
    apk_path = os.path.join(ANDROID_DIR, apk_name)
    local_name = LOCAL_APK_MAP.get(arch)

    # 如果本地已有重命名的 APK，直接使用
    if local_name and os.path.exists(os.path.join(ANDROID_DIR, local_name)):
        print(f"[{arch}] 使用本地已有 APK: {local_name}")
        return os.path.join(ANDROID_DIR, local_name)

    # 如果之前下载过 mpv-{arch}.apk，直接使用
    if os.path.exists(apk_path):
        print(f"[{arch}] 使用已下载 APK: {apk_name}")
        return apk_path

    # 下载
    url = f"{BASE_URL}/app-default-{arch}-release.apk"
    print(f"[{arch}] 下载: {url}")
    try:
        urllib.request.urlretrieve(url, apk_path)
        size_mb = os.path.getsize(apk_path) / (1024 * 1024)
        print(f"[{arch}] 下载完成: {size_mb:.1f} MB")
        return apk_path
    except Exception as e:
        print(f"[{arch}] 下载失败: {e}")
        return None


def extract_so(apk_path, arch):
    """从 APK 中提取 .so 文件到 jniLibs/{arch}/"""
    if not apk_path or not os.path.exists(apk_path):
        print(f"[{arch}] APK 不存在，跳过")
        return False

    target_dir = os.path.join(JNILIBS_DIR, arch)
    os.makedirs(target_dir, exist_ok=True)

    try:
        with zipfile.ZipFile(apk_path, 'r') as z:
            # APK 中的 .so 路径: lib/{arch}/*.so
            prefix = f"lib/{arch}/"
            so_files = [n for n in z.namelist() if n.startswith(prefix) and n.endswith('.so')]
            if not so_files:
                print(f"[{arch}] APK 中未找到 {prefix}*.so")
                return False

            for name in so_files:
                # 提取到 jniLibs/{arch}/{filename}
                filename = os.path.basename(name)
                target_path = os.path.join(target_dir, filename)
                with z.open(name) as src, open(target_path, 'wb') as dst:
                    shutil.copyfileobj(src, dst)
                size_kb = os.path.getsize(target_path) / 1024
                print(f"[{arch}] 提取: {filename} ({size_kb:.0f} KB)")

            return True
    except Exception as e:
        print(f"[{arch}] 提取失败: {e}")
        return False


def main():
    print("=" * 60)
    print("提取 mpv-android native 库到 jniLibs")
    print(f"jniLibs 目录: {JNILIBS_DIR}")
    print("=" * 60)

    success_count = 0
    for arch in ARCHS:
        print()
        apk_path = download_apk(arch)
        if extract_so(apk_path, arch):
            success_count += 1

    print()
    print("=" * 60)
    print(f"完成: {success_count}/{len(ARCHS)} 架构成功提取")

    # 列出最终结果
    if os.path.exists(JNILIBS_DIR):
        print("\njniLibs 目录内容:")
        for arch in ARCHS:
            arch_dir = os.path.join(JNILIBS_DIR, arch)
            if os.path.isdir(arch_dir):
                files = [f for f in os.listdir(arch_dir) if f.endswith('.so')]
                print(f"  {arch}/: {', '.join(sorted(files))}")
            else:
                print(f"  {arch}/: (缺失)")
    print("=" * 60)

    return 0 if success_count == len(ARCHS) else 1


if __name__ == "__main__":
    sys.exit(main())
