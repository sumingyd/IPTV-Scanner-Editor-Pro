import re
from typing import List, Tuple
from log_manager import LogManager

class URLRangeParser:
    """处理带范围的URL地址解析"""
    
    def __init__(self):
        self.logger = LogManager()
        # 完整匹配带前导零的范围表达式
        self.range_pattern = re.compile(r'\[(\d+)-(\d+)\]')
        
    def parse_url(self, url: str) -> List[str]:
        """解析带范围的URL，返回所有可能的URL列表"""
        if not self.has_range(url):
            return [url]
            
        self.logger.info(f"开始解析范围URL: {url}")
        
        # 获取所有范围表达式及其可能值
        ranges_info = []
        for match in self.range_pattern.finditer(url):
            start = int(match.group(1))
            end = int(match.group(2))
            full_match = f"{match.group(1)}-{match.group(2)}"
            zero_pad = len(match.group(1))  # 前导零长度
            values = [str(num).zfill(zero_pad) for num in range(start, end + 1)]
            ranges_info.append({
                'expr': f'[{full_match}]',
                'values': values,
                'start_pos': match.start(),
                'end_pos': match.end()
            })
        
        if not ranges_info:
            return [url]
            
        # 递归生成所有组合
        def generate_combinations(url_parts, current_ranges, index=0, current_url=""):
            if index == len(current_ranges):
                return [current_url + url_parts[index]]
                
            results = []
            for value in current_ranges[index]['values']:
                new_part = url_parts[index] + value
                results.extend(generate_combinations(
                    url_parts, current_ranges, index + 1, current_url + new_part))
            return results
            
        # 分割URL
        url_parts = []
        last_pos = 0
        for r in ranges_info:
            url_parts.append(url[last_pos:r['start_pos']])
            last_pos = r['end_pos']
        url_parts.append(url[last_pos:])
        
        # 生成所有URL组合
        urls = generate_combinations(url_parts, ranges_info)
        
        self.logger.info(f"生成 {len(urls)} 个URL")
        for i, url in enumerate(urls, 1):
            self.logger.debug(f"URL {i}/{len(urls)}: {url}")
        return urls
        
    def has_range(self, url: str) -> bool:
        """检查URL是否包含范围表达式"""
        return '[' in url and ']' in url and '-' in url
        
    def _find_all_ranges(self, url: str) -> List[Tuple[int, int, str]]:
        """查找URL中所有的范围表达式，返回(start, end, full_match)列表"""
        ranges = []
        for match in self.range_pattern.finditer(url):
            start = int(match.group(1))
            end = int(match.group(2))
            full_match = f"{match.group(1)}-{match.group(2)}"
            
            ranges.append((start, end, full_match))
        return ranges
