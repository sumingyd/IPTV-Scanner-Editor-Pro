import re
from typing import List, Tuple, Generator
from log_manager import LogManager

class URLRangeParser:
    """处理带范围的URL地址解析"""
    
    def __init__(self):
        self.logger = LogManager()
        # 增强版正则，支持复杂路径中的范围表达式
        self.range_pattern = re.compile(r'\[(\d+)-(\d+)\]')
        self.multi_range_pattern = re.compile(r'(?:\[(\d+)-(\d+)\])+')
        
    def parse_url(self, url: str, batch_size: int = 10000) -> Generator[List[str], None, None]:
        """解析带范围的URL，分批生成URL列表"""
        if not self.has_range(url):
            yield url
            return
            
        self.logger.info(f"开始解析范围URL: {url}")
        self.logger.debug(f"原始URL: {url}")
        
        # 先替换所有范围表达式为占位符，保留原始位置信息
        placeholders = []
        temp_url = url
        for i, match in enumerate(self.range_pattern.finditer(url)):
            start, end = match.span()
            placeholders.append({
                'start': start,
                'end': end,
                'match': match.group()
            })
            temp_url = temp_url[:start] + f"__RANGE_{i}__" + temp_url[end:]
            
        self.logger.debug(f"替换占位符后URL: {temp_url}")
        self.logger.debug(f"找到的范围表达式: {placeholders}")
        
        # 获取所有范围表达式及其可能值
        ranges_info = []
        for match in self.range_pattern.finditer(url):
            start = int(match.group(1))
            end = int(match.group(2))
            full_match = f"{match.group(1)}-{match.group(2)}"
            zero_pad = len(match.group(1))  # 前导零长度
            ranges_info.append({
                'expr': f'[{full_match}]',
                'start': start,
                'end': end,
                'zero_pad': zero_pad,
                'start_pos': match.start(),
                'end_pos': match.end()
            })
        
        if not ranges_info:
            yield url
            return
            
        # 分割URL
        url_parts = []
        last_pos = 0
        for r in ranges_info:
            url_parts.append(url[last_pos:r['start_pos']])
            last_pos = r['end_pos']
        url_parts.append(url[last_pos:])
        
        # 生成URL批次
        batch = []
        for values in self._generate_range_values(ranges_info):
            url = self._build_url_from_parts(url_parts, ranges_info, values)
            batch.append(url)
            
            if len(batch) >= batch_size:
                yield batch
                batch = []
                
        if batch:
            yield batch
            
    def _generate_range_values(self, ranges_info):
        """生成范围值的迭代器"""
        from itertools import product
        
        ranges = []
        for r in ranges_info:
            values = range(r['start'], r['end'] + 1)
            ranges.append([str(num).zfill(r['zero_pad']) for num in values])
            
        return product(*ranges)
        
    def _build_url_from_parts(self, url_parts, ranges_info, values):
        """从URL部分和值构建完整URL"""
        url = ""
        for i in range(len(ranges_info)):
            url += url_parts[i] + values[i]
        url += url_parts[-1]
        self.logger.debug(f"构建的URL: {url}")
        return url
        
    def test_parse_url(self, url: str):
        """测试URL解析"""
        print(f"\n测试URL: {url}")
        for i, batch in enumerate(self.parse_url(url, batch_size=5)):
            print(f"批次 {i+1}:")
            for url in batch:
                print(url)
            if i >= 2:  # 只显示前3个批次
                print("...")
                break
        
    def has_range(self, url: str) -> bool:
        """检查URL是否包含范围表达式"""
        return bool(self.multi_range_pattern.search(url))
        
    def _find_all_ranges(self, url: str) -> List[Tuple[int, int, str]]:
        """查找URL中所有的范围表达式，返回(start, end, full_match)列表"""
        ranges = []
        for match in self.range_pattern.finditer(url):
            start = int(match.group(1))
            end = int(match.group(2))
            full_match = f"{match.group(1)}-{match.group(2)}"
            
            ranges.append((start, end, full_match))
        return ranges
