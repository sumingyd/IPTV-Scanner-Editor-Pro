from typing import Dict, Any, List
from datetime import datetime
from core.log_manager import global_logger as logger


class EpgSearchService:
    def __init__(self):
        pass

    def search_programs(self, epg_parser, keyword: str,
                        channels: List[Dict[str, Any]] = None,
                        date=None) -> List[Dict[str, Any]]:
        if not keyword or not keyword.strip():
            return []
        keyword = keyword.strip().lower()
        results = []
        if not epg_parser:
            return results
        if not channels:
            channels = []

        seen = set()
        for ch in channels:
            ch_name = ch.get('name', '')
            tvg_id = ch.get('tvg_id', '')
            all_tags = ch.get('_all_tags', {})
            tvg_name = all_tags.get('tvg-name', '')
            comma_name = ''
            raw_extinf = ch.get('_raw_extinf', '')
            if raw_extinf and ',' in raw_extinf:
                comma_name = raw_extinf.split(',', 1)[-1].strip()
                if comma_name.startswith('"') and comma_name.endswith('"'):
                    comma_name = comma_name[1:-1]

            try:
                programs = epg_parser.get_channel_epg(
                    ch_name, tvg_id, tvg_name=tvg_name, comma_name=comma_name
                ) or []
            except Exception:
                continue

            for prog in programs:
                title = (prog.get('title', '') or '').lower()
                desc = (prog.get('desc', '') or '').lower()
                if keyword in title or keyword in desc:
                    key = f"{ch_name}_{prog.get('title', '')}_{prog.get('start', '')}"
                    if key not in seen:
                        seen.add(key)
                        results.append({
                            'channel_name': ch_name,
                            'title': prog.get('title', ''),
                            'desc': prog.get('desc', ''),
                            'start': prog.get('start', ''),
                            'end': prog.get('end', ''),
                        })

        results.sort(key=lambda r: r.get('start', ''))
        return results
