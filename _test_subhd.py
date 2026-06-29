"""调试 SubtitleCat .srt 链接解析"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import importlib
import services.subtitle_download_service as sds
importlib.reload(sds)
from services.subtitle_download_service import SubtitleDownloadService, SUBCAT_BASE_URL

svc = SubtitleDownloadService()

# 测试 1: Inception (id=1)
print("=" * 70)
print("调试: Inception (id=1) 详情页 .srt 链接")
print("=" * 70)
detail_url = f"{SUBCAT_BASE_URL}/subs/1/Inception.html"
html = svc._fetch_html_subtitlecat(detail_url)
print(f"详情页 HTML 长度: {len(html)}")

# 找所有 .srt 链接
import re
srt_links = re.findall(r'href="(/subs/[^"]+\.srt)"', html)
print(f"找到 {len(srt_links)} 个 .srt 链接")
for link in srt_links[:5]:
    print(f"  {link}")

# 测试 _parse_subtitlecat_srt_link
parsed_link = svc._parse_subtitlecat_srt_link(html, 'all')
print(f"\n_parse_subtitlecat_srt_link 返回: {parsed_link}")

# 测试 2: Inception.2010.1080p.BrRip.x264.YIFY (id=28)
print("\n" + "=" * 70)
print("调试: Inception.2010.1080p.BrRip.x264.YIFY (id=28) 详情页")
print("=" * 70)
detail_url2 = f"{SUBCAT_BASE_URL}/subs/28/Inception.2010.1080p.BrRip.x264.YIFY.html"
html2 = svc._fetch_html_subtitlecat(detail_url2)
print(f"详情页 HTML 长度: {len(html2)}")

srt_links2 = re.findall(r'href="(/subs/[^"]+\.srt)"', html2)
print(f"找到 {len(srt_links2)} 个 .srt 链接")
for link in srt_links2[:5]:
    print(f"  {link}")

# 找中文链接
zh_links = [l for l in srt_links2 if 'zh' in l.lower()]
print(f"\n中文 .srt 链接:")
for link in zh_links:
    print(f"  {SUBCAT_BASE_URL}{link}")

# 测试下载中文 .srt
if zh_links:
    test_url = SUBCAT_BASE_URL + zh_links[0]
    print(f"\n测试下载: {test_url}")
    import urllib.request
    req = urllib.request.Request(test_url, headers={'User-Agent': SUBCAT_BASE_URL})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            content = resp.read()
        print(f"下载成功，大小: {len(content)} bytes")
        print(f"内容预览: {content[:200]}")
    except Exception as e:
        print(f"下载失败: {e}")
