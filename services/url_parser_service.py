import re
from typing import List, Tuple, Generator
from core.log_manager import global_logger


class URLRangeParser:

    def __init__(self):
        self.logger = global_logger
        self.range_pattern = re.compile(r'\[(\d+(?:-\d+)?(?:,\d+(?:-\d+)?)*)\]')
        self.ipv6_pattern = re.compile(r'\[[a-fA-F0-9]*(?::[a-fA-F0-9]*){2,}(?:%[a-zA-Z0-9_]+)?\]')

    def _parse_segment(self, segment: str) -> List[Tuple[int, int, int]]:
        results = []
        if '-' in segment:
            parts = segment.split('-')
            start = int(parts[0])
            end = int(parts[1])
            zero_pad = len(parts[0])
            results.append((start, end, zero_pad))
        else:
            val = int(segment)
            zero_pad = len(segment)
            results.append((val, val, zero_pad))
        return results

    def _parse_bracket_content(self, content: str) -> List[Tuple[int, int, int]]:
        all_values = []
        first_pad = None
        for segment in content.split(','):
            segment = segment.strip()
            if not segment:
                continue
            parsed = self._parse_segment(segment)
            all_values.extend(parsed)
            if first_pad is None:
                first_pad = parsed[0][2]
        return all_values, first_pad or 1

    def _expand_to_values(self, parsed_segments, pad_width: int) -> List[str]:
        values = []
        seen = set()
        for start, end, _ in parsed_segments:
            for num in range(start, end + 1):
                if num not in seen:
                    seen.add(num)
                    values.append(str(num).zfill(pad_width))
        return values

    def has_range(self, url: str) -> bool:
        range_matches = list(self.range_pattern.finditer(url))
        valid_ranges = []
        for match in range_matches:
            match_start, match_end = match.span()
            is_inside_ipv6 = False
            for ipv6_match in self.ipv6_pattern.finditer(url):
                ipv6_start, ipv6_end = ipv6_match.span()
                if ipv6_start <= match_start and match_end <= ipv6_end:
                    is_inside_ipv6 = True
                    break
            if not is_inside_ipv6:
                valid_ranges.append(match)
        return len(valid_ranges) > 0

    def parse_url(
        self, url: str, batch_size: int = 10000
    ) -> Generator[List[str], None, None]:
        if not self.has_range(url):
            yield [url]
            return

        self.logger.info(f"开始解析范围URL: {url}")

        ranges_info = []
        for match in self.range_pattern.finditer(url):
            match_start, match_end = match.span()
            is_inside_ipv6 = False
            for ipv6_match in self.ipv6_pattern.finditer(url):
                ipv6_start, ipv6_end = ipv6_match.span()
                if ipv6_start <= match_start and match_end <= ipv6_end:
                    is_inside_ipv6 = True
                    break
            if is_inside_ipv6:
                continue

            content = match.group(1)
            parsed_segments, min_pad = self._parse_bracket_content(content)
            expanded_values = self._expand_to_values(parsed_segments, min_pad)

            if not expanded_values:
                continue

            ranges_info.append({
                'expr': match.group(),
                'values': expanded_values,
                'start_pos': match.start(),
                'end_pos': match.end()
            })

        if not ranges_info:
            yield [url]
            return

        total_urls = 1
        for r in ranges_info:
            total_urls *= len(r['values'])

        range_count = len(ranges_info)
        self.logger.info(
            f"URL解析: 找到 {range_count} 个范围表达式，"
            f"将生成 {total_urls} 个URL"
        )

        url_parts = []
        last_pos = 0
        for r in ranges_info:
            url_parts.append(url[last_pos:r['start_pos']])
            last_pos = r['end_pos']
        url_parts.append(url[last_pos:])

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
        def lazy_product(ranges):
            if not ranges:
                yield ()
                return
            first_values = ranges[0]['values']
            for rest in lazy_product(ranges[1:]):
                for val in first_values:
                    yield (val,) + rest
        return lazy_product(ranges_info)

    def _build_url_from_parts(self, url_parts, ranges_info, values):
        url = ""
        for i in range(len(ranges_info)):
            url += url_parts[i] + values[i]
        url += url_parts[-1]
        return url

    def test_parse_url(self, url: str):
        print(f"\n测试URL: {url}")
        for i, batch in enumerate(self.parse_url(url, batch_size=5)):
            print(f"批次 {i+1}:")
            for url in batch:
                print(url)
            if i >= 2:
                print("...")
                break

    def _find_all_ranges(self, url: str) -> List[Tuple[int, int, str]]:
        ranges = []
        for match in self.range_pattern.finditer(url):
            content = match.group(1)
            parsed_segments, _ = self._parse_bracket_content(content)
            for start, end, _ in parsed_segments:
                full_match = f"{start}-{end}" if start != end else str(start)
                ranges.append((start, end, full_match))
        return ranges
