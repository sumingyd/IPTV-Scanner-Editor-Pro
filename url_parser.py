import re
from typing import List, Tuple
from log_manager import LogManager

class URLRangeParser:
    """处理带范围的URL地址解析"""
    
    def __init__(self):
        self.logger = LogManager()
        self.range_pattern = re.compile(r'\[(\d+)-(\d+)\]')
        self.zero_padding_pattern = re.compile(r'\[0*(\d+)-0*(\d+)\]')
        
    def parse_url(self, url: str) -> List[str]:
        """解析带范围的URL，返回所有可能的URL列表"""
        if not self.has_range(url):
            return [url]
            
        self.logger.info(f"开始解析范围URL: {url}")
        ranges = self._find_all_ranges(url)
        if not ranges:
            return [url]
            
        # 生成所有可能的组合
        urls = [url]
        for start, end, full_match in ranges:
            new_urls = []
            for num in range(start, end + 1):
                for u in urls:
                    # 保持原始补零格式
                    if full_match.startswith('0'):
                        num_str = str(num).zfill(len(full_match.split('-')[0]))
                    else:
                        num_str = str(num)
                    new_urls.append(u.replace(f'[{full_match}]', num_str))
            urls = new_urls
            
        self.logger.info(f"生成 {len(urls)} 个URL")
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
            
            # 检查是否有前导零
            zero_match = self.zero_padding_pattern.search(match.group(0))
            if zero_match:
                full_match = f"{zero_match.group(1)}-{zero_match.group(2)}"
                
            ranges.append((start, end, full_match))
        return ranges

