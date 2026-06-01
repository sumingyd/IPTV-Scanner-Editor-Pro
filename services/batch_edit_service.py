import re
from typing import Dict, Any, List, Optional
from core.log_manager import global_logger as logger


class BatchEditService:
    def batch_set_group(self, channels: List[Dict[str, Any]],
                        indices: List[int], group: str) -> int:
        count = 0
        for idx in indices:
            if 0 <= idx < len(channels):
                channels[idx]['group'] = group
                channels[idx]['_groups'] = [group]
                count += 1
        return count

    def batch_add_name_prefix(self, channels: List[Dict[str, Any]],
                              indices: List[int], prefix: str) -> int:
        count = 0
        for idx in indices:
            if 0 <= idx < len(channels):
                old_name = channels[idx].get('name', '')
                if not old_name.startswith(prefix):
                    channels[idx]['name'] = prefix + old_name
                    count += 1
        return count

    def batch_remove_name_prefix(self, channels: List[Dict[str, Any]],
                                 indices: List[int], prefix: str) -> int:
        count = 0
        for idx in indices:
            if 0 <= idx < len(channels):
                old_name = channels[idx].get('name', '')
                if old_name.startswith(prefix):
                    channels[idx]['name'] = old_name[len(prefix):]
                    count += 1
        return count

    def batch_name_replace(self, channels: List[Dict[str, Any]],
                           indices: List[int], old_text: str, new_text: str,
                           use_regex: bool = False) -> int:
        count = 0
        for idx in indices:
            if 0 <= idx < len(channels):
                old_name = channels[idx].get('name', '')
                if use_regex:
                    try:
                        new_name = re.sub(old_text, new_text, old_name)
                    except re.error:
                        continue
                else:
                    new_name = old_name.replace(old_text, new_text)
                if new_name != old_name:
                    channels[idx]['name'] = new_name
                    count += 1
        return count

    def batch_url_replace(self, channels: List[Dict[str, Any]],
                          indices: List[int], old_text: str, new_text: str) -> int:
        count = 0
        for idx in indices:
            if 0 <= idx < len(channels):
                old_url = channels[idx].get('url', '')
                new_url = old_url.replace(old_text, new_text)
                if new_url != old_url:
                    channels[idx]['url'] = new_url
                    count += 1
        return count

    def batch_set_logo(self, channels: List[Dict[str, Any]],
                       indices: List[int], logo_url: str) -> int:
        count = 0
        for idx in indices:
            if 0 <= idx < len(channels):
                channels[idx]['logo'] = logo_url
                count += 1
        return count

    def batch_set_tvg_id(self, channels: List[Dict[str, Any]],
                         indices: List[int], tvg_id: str) -> int:
        count = 0
        for idx in indices:
            if 0 <= idx < len(channels):
                channels[idx]['tvg_id'] = tvg_id
                count += 1
        return count

    def batch_remove(self, channels: List[Dict[str, Any]],
                     indices: List[int]) -> List[Dict[str, Any]]:
        remove_set = set(indices)
        result = [ch for i, ch in enumerate(channels) if i not in remove_set]
        return result

    def batch_move_to_group(self, channels: List[Dict[str, Any]],
                            indices: List[int], target_group: str) -> int:
        return self.batch_set_group(channels, indices, target_group)