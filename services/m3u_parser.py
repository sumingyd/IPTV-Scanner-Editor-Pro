import gzip
import os
import re
from urllib.parse import urlparse, urljoin


def detect_and_decode_text(raw_bytes):
    if not raw_bytes:
        return ''
    for enc in ('utf-8-sig', 'utf-8'):
        try:
            return raw_bytes.decode(enc)
        except (UnicodeDecodeError, ValueError):
            continue
    for enc in ('gb18030', 'gbk', 'gb2312'):
        try:
            return raw_bytes.decode(enc)
        except (UnicodeDecodeError, ValueError):
            continue
    for enc in ('big5', 'shift_jis', 'euc-kr', 'euc-jp'):
        try:
            return raw_bytes.decode(enc)
        except (UnicodeDecodeError, ValueError):
            continue
    try:
        import locale
        return raw_bytes.decode(locale.getpreferredencoding(), errors='replace')
    except Exception:
        return raw_bytes.decode('utf-8', errors='replace')


def is_gzip(data):
    return len(data) >= 2 and data[0] == 0x1F and data[1] == 0x8B


def load_m3u_file(filepath):
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"文件不存在: {filepath}")
    with open(filepath, 'rb') as f:
        raw = f.read()
    if is_gzip(raw):
        try:
            raw = gzip.decompress(raw)
        except Exception:
            pass
    return detect_and_decode_text(raw)


def load_m3u_from_url_data(data):
    if is_gzip(data):
        try:
            data = gzip.decompress(data)
        except Exception:
            pass
    return detect_and_decode_text(data)


def parse_attributes(attr_string):
    result = {}
    if not attr_string:
        return result
    i = 0
    n = len(attr_string)
    while i < n:
        while i < n and attr_string[i] in ' \t':
            i += 1
        if i >= n:
            break
        key_start = i
        while i < n and attr_string[i] not in '= \t':
            i += 1
        key = attr_string[key_start:i].strip()
        if not key:
            i += 1
            continue
        while i < n and attr_string[i] in ' \t':
            i += 1
        if i >= n or attr_string[i] != '=':
            result[key] = ''
            continue
        i += 1
        while i < n and attr_string[i] in ' \t':
            i += 1
        if i >= n:
            result[key] = ''
            break
        if attr_string[i] == '"':
            i += 1
            val_start = i
            while i < n and attr_string[i] != '"':
                i += 1
            result[key] = attr_string[val_start:i]
            if i < n:
                i += 1
        else:
            val_start = i
            while i < n and attr_string[i] not in ' \t':
                i += 1
            result[key] = attr_string[val_start:i]
    return result


def guess_protocol(url):
    if not url:
        return 'unknown'
    u = url.lower()
    if '.m3u8' in u or u.startswith('hls+'):
        return 'hls'
    if '.mpd' in u or u.startswith('dash+'):
        return 'dash'
    if u.startswith('rtsp://'):
        return 'rtsp'
    if u.startswith('rtp://') or u.startswith('udp://'):
        return 'rtp'
    if u.startswith('srt://'):
        return 'srt'
    if u.startswith('http://') or u.startswith('https://'):
        return 'http'
    if u.startswith('file://') or '://' not in url:
        return 'file'
    return 'unknown'


def guess_quality_from_name(name):
    if not name:
        return 'SD', 'H.264'
    n = name.upper()
    resolution = 'SD'
    codec = ''
    if '4K' in n or 'UHD' in n or '2160' in n:
        resolution = '4K'
    elif '1080' in n or 'FHD' in n or 'FULL' in n:
        resolution = 'FHD'
    elif '720' in n or 'HD' in n:
        resolution = 'HD'
    if 'HEVC' in n or 'H265' in n or 'H.265' in n:
        codec = 'H.265'
    elif 'H264' in n or 'H.264' in n or 'AVC' in n:
        codec = 'H.264'
    elif 'AV1' in n:
        codec = 'AV1'
    return resolution, codec


def normalize_url(url):
    if not url:
        return url
    url = url.strip()
    if '$' in url:
        url = url.split('$')[0]
    url = url.rstrip(',')
    return url


def resolve_url(url, base_url=None):
    url = normalize_url(url)
    if not url:
        return url
    if '://' in url or url.startswith('/'):
        if base_url and url.startswith('/'):
            parsed = urlparse(base_url)
            return f"{parsed.scheme}://{parsed.netloc}{url}"
        return url
    if base_url:
        return urljoin(base_url, url)
    return url


def extract_tvg_url_from_header(line):
    if not line or not line.startswith('#EXTM3U'):
        return None
    m = re.search(r'x-tvg-url="([^"]+)"', line, re.IGNORECASE)
    if m:
        return m.group(1)
    m = re.search(r"x-tvg-url='([^']+)'", line, re.IGNORECASE)
    if m:
        return m.group(1)
    m = re.search(r'x-tvg-url=(\S+)', line, re.IGNORECASE)
    if m:
        return m.group(1).rstrip('"').rstrip("'")
    return None


def is_valid_channel_url(url):
    if not url or not url.strip():
        return False
    u = url.strip()
    if u.startswith('#'):
        return False
    if u in ('http://0/0.m3u8', 'http://0', 'rtmp://0'):
        return False
    if u.startswith('http://0/') or u.startswith('http://0:'):
        return False
    if u.startswith('rtp://0.') or u.startswith('udp://0.'):
        return False
    return True
