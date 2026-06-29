"""测试多源字幕搜索（OpenSubtitles + SubHD）"""
import sys
sys.path.insert(0, '.')

from services.subtitle_download_service import SubtitleDownloadService

svc = SubtitleDownloadService()

print('=' * 70)
print('测试 1: 搜索中文片名 "流浪地球"')
print('=' * 70)
items = svc.search(query='流浪地球', language='chi')
print(f'返回 {len(items)} 条结果')
print(f'last_error: {svc.last_error}')
for i, it in enumerate(items[:10]):  # 只显示前 10 条
    print(f'\n--- [{i+1}] {it.get("source", "")} ---')
    print(f'  file_name: {it.get("file_name", "")}')
    print(f'  language: {it.get("language", "")}')
    print(f'  format: {it.get("format", "")}')
    print(f'  movie_name: {it.get("movie_name", "")}')
    print(f'  download_link: {it.get("download_link", "")}')
    print(f'  auto_download: {it.get("auto_download", False)}')
    if it.get('source') == 'SubHD':
        print(f'  detail_url: {it.get("detail_url", "")}')
        print(f'  type: {it.get("type", "")}')
        print(f'  size: {it.get("size", "")}')
        print(f'  download_count: {it.get("download_count", 0)}')
        print(f'  add_date: {it.get("add_date", "")}')
        print(f'  uploader: {it.get("uploader", "")}')

print()
print('=' * 70)
print('测试 2: 搜索英文片名 "Inception"')
print('=' * 70)
items2 = svc.search(query='Inception', language='eng')
print(f'返回 {len(items2)} 条结果')
print(f'last_error: {svc.last_error}')
for i, it in enumerate(items2[:5]):
    print(f'[{i+1}] {it.get("source", "")} | {it.get("file_name", "")[:60]} | {it.get("language", "")}')

print()
print('=' * 70)
print('测试 3: 搜索文件名 "The.Wandering.Earth.2019.1080p.BluRay.x264"')
print('=' * 70)
items3 = svc.search(query='The.Wandering.Earth.2019.1080p.BluRay.x264', language='chi')
print(f'返回 {len(items3)} 条结果')
print(f'last_error: {svc.last_error}')
for i, it in enumerate(items3[:5]):
    print(f'[{i+1}] {it.get("source", "")} | {it.get("file_name", "")[:60]} | {it.get("language", "")}')
