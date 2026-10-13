#!/usr/bin/env python3
"""
提取 mpv-android 的 native 库到 jniLibs 目录。
与 CI 工作流 .github/workflows/build.yml 的步骤一致。

libmpv 来源（2026-10 起，安卓端切换到 AVS 支持版）：
  1. 官方 mpv-android APK（基座）：提供 libplayer.so（mpv-android 的 JNI 层，
     MPVLib.kt 需同时加载 libmpv 与 libplayer）与 libc++_shared.so
     （davs2 为 C++ 编译，dlopen 时必需，见 mpv-android-avs README 已知坑）
  2. sggc/mpv-android-avs（覆盖）：带 CAVS/AVS2/AVS3-P2/AV3A 解码支持的
     libmpv.so / libavcodec.so / libdavs2.so / libuavs3d.so /
     libavs3a_decoder.so 等一套 .so，覆盖 arm64-v8a / armeabi-v7a。
     该仓库只发布这两个 ABI，x86/x86_64（仅模拟器用）沿用官方库
  3. assets/model.bin：AV3A(Audio Vivid) 解码器运行时模型。
     libavs3a_decoder 内部会 fopen("model.bin")，找不到会初始化失败；
     由 IptvApplication 启动时从 APK assets 拷贝到 filesDir 供其读取

CI 下载 URL:
  https://github.com/mpv-android/mpv-android/releases/download/2026-04-25/app-default-{arch}-release.apk
  https://github.com/sggc/mpv-android-avs/releases/download/libmpv-cavs-dynamic-v003/libmpv-cavs-android-dynamic.tar.gz
"""
import os
import sys
import tarfile
import zipfile
import urllib.request
import shutil

ANDROID_DIR = os.path.dirname(os.path.abspath(__file__))
OFFICIAL_BASE_URL = "https://github.com/mpv-android/mpv-android/releases/download/2026-04-25"
# AVS 支持版 libmpv 发布仓库，升级时 bump 标签即可
AVS_RELEASE_TAG = "libmpv-cavs-dynamic-v003"
AVS_BASE_URL = "https://github.com/sggc/mpv-android-avs/releases/download"
AVS_ASSET = "libmpv-cavs-android-dynamic.tar.gz"

# 官方 APK 覆盖全部 4 种架构（x86 系仅供模拟器）
ARCHS = ["arm64-v8a", "armeabi-v7a", "x86_64", "x86"]
# AVS 版库只发布 ARM 双架构
AVS_ARCHS = ["arm64-v8a", "armeabi-v7a"]

JNILIBS_DIR = os.path.join(ANDROID_DIR, "app", "src", "main", "jniLibs")
ASSETS_DIR = os.path.join(ANDROID_DIR, "app", "src", "main", "assets")

# 本地已有的 APK 文件名映射
LOCAL_APK_MAP = {
    "arm64-v8a": "mpv-arm64.apk",
    "x86_64": "mpv-x86_64.apk",
}


def download_file(url, dest):
    """下载文件到指定路径（已存在则复用缓存）"""
    if os.path.exists(dest):
        print(f"  使用已下载缓存: {os.path.basename(dest)}")
        return dest
    print(f"  下载: {url}")
    try:
        urllib.request.urlretrieve(url, dest)
        size_mb = os.path.getsize(dest) / (1024 * 1024)
        print(f"  下载完成: {size_mb:.1f} MB")
        return dest
    except Exception as e:
        print(f"  下载失败: {e}")
        return None


def download_apk(arch):
    """下载指定架构的官方 mpv-android APK"""
    apk_name = f"mpv-{arch}.apk"
    apk_path = os.path.join(ANDROID_DIR, apk_name)
    local_name = LOCAL_APK_MAP.get(arch)

    # 如果本地已有重命名的 APK，直接使用
    if local_name and os.path.exists(os.path.join(ANDROID_DIR, local_name)):
        print(f"[{arch}] 使用本地已有 APK: {local_name}")
        return os.path.join(ANDROID_DIR, local_name)

    print(f"[{arch}] 官方 mpv-android 基座库")
    return download_file(f"{OFFICIAL_BASE_URL}/app-default-{arch}-release.apk", apk_path)


def extract_apk_so(apk_path, arch):
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


def extract_avs_libs():
    """下载 AVS 支持版 libmpv 并覆盖 ARM 双架构的解码库，同时提取 model.bin"""
    tar_path = os.path.join(ANDROID_DIR, AVS_ASSET)
    downloaded = download_file(f"{AVS_BASE_URL}/{AVS_RELEASE_TAG}/{AVS_ASSET}", tar_path)
    if not downloaded:
        return False

    try:
        with tarfile.open(tar_path, 'r:gz') as t:
            members = t.getmembers()

            # 1) 覆盖 jniLibs/{arch}/*.so（libmpv/ffmpeg/davs2/uavs3d/avs3a_decoder 等）
            for arch in AVS_ARCHS:
                target_dir = os.path.join(JNILIBS_DIR, arch)
                os.makedirs(target_dir, exist_ok=True)
                prefix = f"jniLibs/{arch}/"
                count = 0
                for m in members:
                    if m.isfile() and m.name.startswith(prefix) and m.name.endswith('.so'):
                        filename = os.path.basename(m.name)
                        target_path = os.path.join(target_dir, filename)
                        with t.extractfile(m) as src, open(target_path, 'wb') as dst:
                            shutil.copyfileobj(src, dst)
                        size_kb = os.path.getsize(target_path) / 1024
                        print(f"[{arch}] AVS 覆盖: {filename} ({size_kb:.0f} KB)")
                        count += 1
                if count == 0:
                    print(f"[{arch}] AVS 包中未找到 {prefix}*.so")
                    return False

            # 2) 提取 assets/model.bin（AV3A 解码器运行时模型）
            os.makedirs(ASSETS_DIR, exist_ok=True)
            for m in members:
                if m.isfile() and m.name == "assets/model.bin":
                    target_path = os.path.join(ASSETS_DIR, "model.bin")
                    with t.extractfile(m) as src, open(target_path, 'wb') as dst:
                        shutil.copyfileobj(src, dst)
                    size_kb = os.path.getsize(target_path) / 1024
                    print(f"[assets] 提取: model.bin ({size_kb:.0f} KB)")
                    break
            else:
                print("[assets] AVS 包中未找到 model.bin")
                return False

        return True
    except Exception as e:
        print(f"AVS 库提取失败: {e}")
        return False


def main():
    print("=" * 60)
    print("提取 mpv-android native 库到 jniLibs（官方基座 + AVS 支持版覆盖）")
    print(f"jniLibs 目录: {JNILIBS_DIR}")
    print(f"AVS 来源: sggc/mpv-android-avs @ {AVS_RELEASE_TAG}")
    print("=" * 60)

    success_count = 0
    for arch in ARCHS:
        print()
        apk_path = download_apk(arch)
        if extract_apk_so(apk_path, arch):
            success_count += 1

    print()
    print("-" * 60)
    print("覆盖 AVS 支持版解码库（CAVS/AVS2/AVS3/AV3A）")
    avs_ok = extract_avs_libs()

    print()
    print("=" * 60)
    print(f"完成: 官方基座 {success_count}/{len(ARCHS)} 架构, "
          f"AVS 覆盖 {'成功' if avs_ok else '失败'}")

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
    if os.path.exists(os.path.join(ASSETS_DIR, "model.bin")):
        print("\nassets/model.bin: 已就位")
    else:
        print("\nassets/model.bin: 缺失（AV3A 音频将无法解码）")
    print("=" * 60)

    return 0 if (success_count == len(ARCHS) and avs_ok) else 1


if __name__ == "__main__":
    sys.exit(main())
