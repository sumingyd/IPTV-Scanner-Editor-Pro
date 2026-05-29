import gzip
import os
import re
from typing import Any, Dict, List, Optional, Tuple, Union
from urllib.parse import urlparse, urljoin

from core.log_manager import global_logger as logger


def detect_and_decode_text(raw_bytes: Union[bytes, None]) -> str:
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


def is_gzip(data: bytes) -> bool:
    return len(data) >= 2 and data[0] == 0x1F and data[1] == 0x8B


def load_m3u_file(filepath: str) -> str:
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"文件不存在: {filepath}")
    with open(filepath, 'rb') as f:
        raw = f.read()
    if is_gzip(raw):
        try:
            raw = gzip.decompress(raw)
        except Exception as e:
            logger.debug(f"gzip解压raw数据失败: {e}")
    return detect_and_decode_text(raw)


def load_m3u_from_url_data(data: bytes) -> str:
    if is_gzip(data):
        try:
            data = gzip.decompress(data)
        except Exception as e:
            logger.debug(f"gzip解压data失败: {e}")
    return detect_and_decode_text(data)


def parse_attributes(attr_string: str) -> Dict[str, str]:
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


def guess_protocol(url: str) -> str:
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


def guess_quality_from_name(name: str) -> Tuple[str, str]:
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


def normalize_url(url: str) -> str:
    if not url:
        return url
    url = url.strip()
    if '$' in url:
        url = url.split('$')[0]
    url = url.rstrip(',')
    return url


def resolve_url(url: str, base_url: Optional[str] = None) -> str:
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


def extract_tvg_url_from_header(line: str) -> Optional[str]:
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


def extract_header_attributes(line: str) -> Dict[str, str]:
    if not line or not line.startswith('#EXTM3U'):
        return {}
    attrs = parse_attributes(line[7:])
    result = {}
    epg_keys = ['x-tvg-url', 'tvg-url', 'url-tvg', 'epg-url', 'url-epg']
    for k in epg_keys:
        if k in attrs and attrs[k]:
            result['epg_url'] = attrs[k]
            break
    catchup_keys = ['catchup', 'catchup-correction', 'catchup-source',
                    'catchup-days', 'catchup-type']
    for k in catchup_keys:
        if k in attrs and attrs[k]:
            result[k] = attrs[k]
    return result


def is_valid_channel_url(url: str) -> bool:
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
    if '://' not in u:
        return False
    try:
        parsed = urlparse(u)
        host = parsed.hostname
        if not host:
            return False
        if host in ('0', '1', '2', '3', '4', '5', '6', '7', '8', '9'):
            return False
        octets = host.split('.')
        if len(octets) == 4:
            try:
                if all(0 <= int(o) <= 255 for o in octets):
                    if int(octets[0]) == 0:
                        return False
            except ValueError:
                pass
        return True
    except Exception:
        return True


_TAG_MAPPING = {
    "group-title": "group",
    "tvg-id": "tvg_id",
    "tvg-name": "name",
    "tvg-logo": "logo",
    "tvg-chno": "tvg_chno",
    "tvg-shift": "tvg_shift",
    "catchup": "catchup",
    "catchup-days": "catchup_days",
    "catchup-source": "catchup_source",
    "catchup-correction": "catchup_correction",
    "catchup-type": "catchup",
    "resolution": "resolution",
    "tvg-language": "tvg_language",
    "audio-track": "audio_track",
    "aspect-ratio": "aspect_ratio",
    "parent-code": "parent_code",
}

_HEADER_CATCHUP_MAP = {
    'catchup': 'catchup',
    'catchup-correction': 'catchup_correction',
    'catchup-source': 'catchup_source',
    'catchup-days': 'catchup_days',
    'catchup-type': 'catchup',
}


def _extract_fcc_to_channel(url: str, channel: Dict[str, Any]):
    """从频道URL中提取FCC代理地址并保存到频道字典"""
    try:
        from urllib.parse import urlparse, parse_qs
        if '?fcc=' in url.lower():
            parsed = urlparse(url)
            qs = parse_qs(parsed.query)
            fcc_val = qs.get('fcc', [None])
            if fcc_val and fcc_val[0]:
                channel['fcc'] = fcc_val[0]
    except Exception:
        pass


def _make_empty_channel(group: str = '未分类', groups: Optional[List[str]] = None, extinf: str = '') -> Dict[str, Any]:
    return {
        'name': '未命名',
        'url': '',
        'logo': '',
        'group': group,
        '_groups': groups or [group],
        'tvg_id': '',
        'tvg_chno': '',
        'tvg_shift': '',
        'catchup': '',
        'catchup_days': '',
        'catchup_source': '',
        'catchup_correction': '',
        'fcc': '',
        'resolution': '',
        'valid': None,
        'status': '待检测',
        '_raw_extinf': extinf,
        '_all_tags': {},
    }


def _parse_extinf_line(extinf_content: str, current_group: Union[str, List[str]], genre_group_active: bool) -> Tuple[Optional[Dict[str, Any]], Union[str, List[str]], bool]:
    genre_match = re.search(r',\s*#genre#\s*', extinf_content)
    if genre_match:
        before_genre = extinf_content[:genre_match.start()].strip()
        group_name = before_genre
        comma_pos = before_genre.rfind(',')
        if comma_pos >= 0:
            group_name = before_genre[comma_pos + 1:].strip()
        group_name = group_name.strip('=').strip()
        if group_name:
            current_group = group_name
        return None, current_group, True

    last_comma = extinf_content.rfind(",")
    if last_comma > 0:
        attrs_part = extinf_content[:last_comma].strip()
        name = extinf_content[last_comma + 1:].strip()
    else:
        attrs_part = ''
        name = extinf_content.strip()

    if name.startswith('"') and name.endswith('"'):
        name = name[1:-1]

    channel = _make_empty_channel(
        group=current_group if genre_group_active else '未分类',
        extinf=extinf_content,
    )

    attr_pattern = r'([\w-]+)=["\']([^"\']*)["\']'
    matches = re.findall(attr_pattern, attrs_part)

    all_tags = {}
    groups = []

    for key, value in matches:
        all_tags[key] = value
        field_name = _TAG_MAPPING.get(key, key.replace('-', '_'))
        if key == 'group-title' and value:
            groups = [g.strip() for g in value.split(';') if g.strip()]
            genre_group_active = False
        if key != 'tvg-name':
            channel[field_name] = value

    final_comma_name = ''
    if extinf_content and ',' in extinf_content:
        final_comma_name = extinf_content.split(',', 1)[-1].strip()
        if final_comma_name.startswith('"') and final_comma_name.endswith('"'):
            final_comma_name = final_comma_name[1:-1]
    if final_comma_name:
        channel['name'] = final_comma_name
    else:
        tvg_name = all_tags.get('tvg-name', '')
        if tvg_name:
            channel['name'] = tvg_name
        elif name:
            channel['name'] = name

    if groups:
        channel['_groups'] = groups
        channel['group'] = groups[0]
    elif isinstance(current_group, list):
        channel['_groups'] = current_group
        channel['group'] = current_group[0] if current_group else '未分类'
    else:
        channel['_groups'] = [current_group] if current_group else ['未分类']
        channel['group'] = current_group if current_group else '未分类'

    channel['_all_tags'] = all_tags
    return channel, current_group, genre_group_active


def _inherit_header_attrs(channel: Dict[str, Any], header_attrs: Dict[str, str]) -> None:
    if not channel or not header_attrs:
        return
    for k, v in header_attrs.items():
        if k == 'epg_url':
            continue
        field = _HEADER_CATCHUP_MAP.get(k, k.replace('-', '_'))
        if field and not channel.get(field):
            channel[field] = v
            if '_all_tags' in channel:
                channel['_all_tags'][k] = v


def parse_m3u_content(content: str) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    channels: List[Dict[str, Any]] = []
    if not content:
        return channels, {}
    lines = content.splitlines()
    current_channel: Optional[Dict[str, Any]] = None
    current_group: Union[str, List[str]] = '未分类'
    genre_group_active = False
    header_attrs = {}

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if line.startswith('#EXTM3U'):
            header_attrs = extract_header_attributes(line)
            continue

        if line.startswith('#EXTGRP:'):
            current_group = line[8:].strip()
            if current_group.startswith('"') and current_group.endswith('"'):
                current_group = current_group[1:-1]
            continue

        if line.startswith('#EXTINF:'):
            extinf_content = line[8:].strip()
            current_channel, current_group, genre_group_active = _parse_extinf_line(
                extinf_content, current_group, genre_group_active
            )
            if current_channel:
                _inherit_header_attrs(current_channel, header_attrs)
            continue

        if line.startswith('#EXTVLCOPT:video-resolution=') and current_channel:
            resolution = line.split('=', 1)[1].strip()
            current_channel['resolution'] = resolution
            continue

        if line.startswith('#'):
            continue

        if current_channel:
            url = line.strip()
            if is_valid_channel_url(url):
                current_channel['url'] = url
                _extract_fcc_to_channel(url, current_channel)
                channels.append(current_channel)
            current_channel = None
        else:
            url = line.strip()
            if is_valid_channel_url(url):
                try:
                    from models.channel_mappings import extract_channel_name_from_url
                    ch_name = extract_channel_name_from_url(url)
                except Exception:
                    ch_name = ''
                groups_list = [g.strip() for g in current_group.split(';') if g.strip()] if isinstance(current_group, str) else (current_group if isinstance(current_group, list) else ['未分类'])
                primary_group = groups_list[0] if groups_list else '未分类'
                ch = _make_empty_channel(group=primary_group, groups=groups_list)
                ch['name'] = ch_name if ch_name else '未命名'
                ch['url'] = url
                _inherit_header_attrs(ch, header_attrs)
                channels.append(ch)

    for i, ch in enumerate(channels):
        ch['id'] = i + 1

    return channels, header_attrs
