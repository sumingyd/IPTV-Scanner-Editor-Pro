import re
from typing import List, Tuple, Optional


class ChannelCleaner:

    def __init__(self):
        self.rules = {
            'remove_hd': True,
            'remove_brackets': True,
            'remove_channel_suffix': True,
            'normalize_cctv': True,
            'remove_spaces': True,
        }

    def clean(self, name: str, rules: Optional[dict] = None) -> str:
        if not name:
            return name

        active = rules or self.rules
        cleaned = name

        if active.get('normalize_cctv', True):
            cleaned = self._clean_cctv(cleaned)

        if active.get('remove_brackets', True):
            cleaned = self._clean_brackets(cleaned)

        if active.get('remove_hd', True):
            cleaned = self._clean_hd(cleaned)

        if active.get('remove_channel_suffix', True):
            cleaned = str(re.sub(r'频道$', '', cleaned))

        if active.get('remove_spaces', True):
            cleaned = str(re.sub(r'[\s\-_]+', '', cleaned)).strip()

        return cleaned

    def _clean_cctv(self, name: str) -> str:
        m = re.match(r'^CCTV[\s\-_]*(\d+)(.*)', name, re.IGNORECASE)
        if m:
            num = m.group(1)
            rest = str(re.sub(r'[\s\-_]+', '', m.group(2))).strip()
            if num == '5' and rest.startswith('+'):
                return 'CCTV5+'
            elif num == '4' and '欧洲' in rest:
                return 'CCTV4欧洲'
            elif num == '4' and '美洲' in rest:
                return 'CCTV4美洲'
            elif re.match(r'^4K$', rest, re.IGNORECASE):
                return 'CCTV4K'
            else:
                return 'CCTV' + num
        return name

    def _clean_brackets(self, name: str) -> str:
        def replace_bracket(match):
            inner = match.group(1)
            if re.search(r'4K', inner, re.IGNORECASE):
                return '4K'
            return ''

        return str(re.sub(r'[（(]\s*([^）)]*?)\s*[）)]', replace_bracket, name))

    def _clean_hd(self, name: str) -> str:
        cleaned = str(re.sub(r'\s*(HD|hd|Hd|UHD|uhd|FHD|fhd|SD|sd)\s*$', '', name))
        cleaned = str(re.sub(r'\s*(高清|超高清|标清)\s*$', '', cleaned))
        cleaned = str(re.sub(r'清$', '', cleaned))
        return cleaned

    def preview(self, channels: list, rules: Optional[dict] = None, indices: Optional[list] = None) -> List[dict]:
        results = []
        target_indices = indices if indices is not None else list(range(len(channels)))
        for i in target_indices:
            idx = int(i)
            if idx >= len(channels):
                continue
            ch = channels[idx]
            name = str(ch.get('name', ''))
            cleaned = self.clean(name, rules)
            if cleaned != name and cleaned:
                results.append({
                    'index': idx,
                    'name': name,
                    'cleaned': cleaned,
                })
        return results

    def get_rule_descriptions(self) -> List[Tuple[str, str]]:
        return [
            ('remove_hd', '去除"高清/HD/超高清"后缀'),
            ('remove_brackets', '去除括号内容(保留4K)'),
            ('remove_channel_suffix', '去除"频道"后缀'),
            ('normalize_cctv', 'CCTV名称规范化'),
            ('remove_spaces', '去除多余空格/连字符'),
        ]
