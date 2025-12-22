import re
from typing import List, Tuple, Generator
from core.log_manager import LogManager, global_logger

class URLRangeParser:
    """处理带范围的URL地址解析"""
    
    def __init__(self):
        self.logger = global_logger
        # 增强版正则，支持复杂路径中的范围表达式，排除IPv6地址
        # 匹配格式: [数字-数字]，但不匹配IPv6地址中的方括号
        self.range_pattern = re.compile(r'\[(\d+)-(\d+)\]')
        self.multi_range_pattern = re.compile(r'(?:\[(\d+)-(\d+)\])+')
        # IPv6地址正则，用于识别和排除IPv6地址
        self.ipv6_pattern = re.compile(r'\[[a-fA-F0-9:]+(?:%[a-zA-Z0-9_]+)?\]')
        
    def has_range(self, url: str) -> bool:
        """检查URL是否包含范围表达式，排除IPv6地址"""
        # 先找到所有IPv6地址
        ipv6_addresses = self.ipv6_pattern.findall(url)
        
        # 找到所有范围表达式
        range_matches = list(self.range_pattern.finditer(url))
        
        # 过滤掉在IPv6地址内部的范围表达式
        valid_ranges = []
        for match in range_matches:
            match_start, match_end = match.span()
            is_inside_ipv6 = False
            
            for ipv6_match in self.ipv6_pattern.finditer(url):
                ipv6_start, ipv6_end = ipv6_match.span()
                # 如果范围表达式完全在IPv6地址内部，则排除
                if ipv6_start <= match_start and match_end <= ipv6_end:
                    is_inside_ipv6 = True
                    break
            
            if not is_inside_ipv6:
                valid_ranges.append(match)
        
        return len(valid_ranges) > 0
        
    def parse_url(self, url: str, batch_size: int = 10000) -> Generator[List[str], None, None]:
        """解析带范围的URL，分批生成URL列表"""
        if not self.has_range(url):
            yield url
            return
            
        self.logger.info(f"开始解析范围URL: {url}")
        
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
            
        # 计算生成的URL总数
        total_urls = 1
        for r in ranges_info:
            total_urls *= (r['end'] - r['start'] + 1)
        
        # 显示解析结果
        range_count = len(ranges_info)
        self.logger.info(f"URL解析: 找到 {range_count} 个范围表达式，将生成 {total_urls} 个URL")
            
        # 分割URL
        url_parts = []
        last_pos = 0
        for r in ranges_info:
            url_parts.append(url[last_pos:r['start_pos']])
            last_pos = r['end_pos']
        url_parts.append(url[last_pos:])
        
        # 生成URL批次
        batch = []
        generated_count = 0
        for values in self._generate_range_values(ranges_info):
            url = self._build_url_from_parts(url_parts, ranges_info, values)
            batch.append(url)
            generated_count += 1
            
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
        
    def _find_all_ranges(self, url: str) -> List[Tuple[int, int, str]]:
        """查找URL中所有的范围表达式，返回(start, end, full_match)列表"""
        ranges = []
        for match in self.range_pattern.finditer(url):
            start = int(match.group(1))
            end = int(match.group(2))
            full_match = f"{match.group(1)}-{match.group(2)}"
            
            ranges.append((start, end, full_match))
        return ranges
