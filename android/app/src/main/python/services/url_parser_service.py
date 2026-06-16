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
            if start > end:
                start, end = end, start
            zero_pad = len(parts[0])
            results.append((start, end, zero_pad))
        else:
            val = int(segment)
            zero_pad = len(segment)
            results.append((val, val, zero_pad))
        return results

    def _parse_bracket_content(self, content: str) -> Tuple[List[Tuple[int, int, int]], int]:
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

    def _count_range_size(self, parsed_segments) -> int:
        total = 0
        seen_ranges = set()
        for start, end, _ in parsed_segments:
            if (start, end) in seen_ranges:
                continue
            seen_ranges.add((start, end))
            total += (end - start + 1)
        return total

    def _iter_range_values(self, parsed_segments, pad_width: int) -> Generator[str, None, None]:
        seen = set()
        for start, end, _ in parsed_segments:
            for num in range(start, end + 1):
                if num not in seen:
                    seen.add(num)
                    yield str(num).zfill(pad_width)

    def _create_range_iterator(self, parsed_segments, pad_width: int):
        class RangeIterator:
            def __init__(self, segments, pad):
                self.segments = segments
                self.pad = pad
                self.seg_idx = 0
                self.current = None
                self.end = None
                self.needs_dedup = len(segments) > 1
                self.seen = set() if self.needs_dedup else None
                self._advance_segment()

            def _advance_segment(self):
                while self.seg_idx < len(self.segments):
                    start, end, _ = self.segments[self.seg_idx]
                    self.current = start
                    self.end = end
                    self.seg_idx += 1
                    if not self.needs_dedup or self.current not in self.seen:
                        return
                self.current = None

            def __iter__(self):
                return self

            def __next__(self):
                while self.current is not None:
                    val = self.current
                    if not self.needs_dedup or val not in self.seen:
                        if self.needs_dedup:
                            self.seen.add(val)
                        result = str(val).zfill(self.pad)
                        self.current += 1
                        if self.current > self.end:
                            self._advance_segment()
                        return result
                    self.current += 1
                    if self.current > self.end:
                        self._advance_segment()
                raise StopIteration

            def reset(self):
                self.seg_idx = 0
                self.current = None
                self.end = None
                if self.needs_dedup:
                    self.seen = set()
                self._advance_segment()

        return RangeIterator(parsed_segments, pad_width)

    def _find_valid_ranges(self, url):
        ipv6_spans = [m.span() for m in self.ipv6_pattern.finditer(url)]
        valid_ranges = []
        for match in self.range_pattern.finditer(url):
            match_start, match_end = match.span()
            if not any(ipv6_start <= match_start and match_end <= ipv6_end
                       for ipv6_start, ipv6_end in ipv6_spans):
                valid_ranges.append(match)
        return valid_ranges

    def has_range(self, url: str) -> bool:
        return len(self._find_valid_ranges(url)) > 0

    def estimate_url_count(self, url: str) -> int:
        valid_matches = self._find_valid_ranges(url)
        if not valid_matches:
            return 1
        total = 1
        for match in valid_matches:
            content = match.group(1)
            parsed_segments, _ = self._parse_bracket_content(content)
            count = self._count_range_size(parsed_segments)
            total *= count
        return total

    def parse_url(
        self, url: str, batch_size: int = 10000
    ) -> Generator[List[str], None, None]:
        valid_matches = self._find_valid_ranges(url)
        if not valid_matches:
            yield [url]
            return

        self.logger.info(f"开始解析范围URL: {url}")

        ranges_info = []
        total_urls = 1
        for match in valid_matches:
            content = match.group(1)
            parsed_segments, min_pad = self._parse_bracket_content(content)
            range_size = self._count_range_size(parsed_segments)
            total_urls *= range_size

            ranges_info.append({
                'expr': match.group(),
                'segments': parsed_segments,
                'pad_width': min_pad,
                'start_pos': match.start(),
                'end_pos': match.end()
            })

        if not ranges_info:
            yield [url]
            return

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
        for values in self._generate_range_values_lazy(ranges_info):
            expanded = self._build_url_from_parts(url_parts, range_count, values)
            batch.append(expanded)
            if len(batch) >= batch_size:
                yield batch
                batch = []

        if batch:
            yield batch

    def _generate_range_values_lazy(self, ranges_info):
        if not ranges_info:
            yield ()
            return

        iterators = []
        current_values = []
        for r in ranges_info:
            it = self._create_range_iterator(r['segments'], r['pad_width'])
            first = next(it, None)
            if first is None:
                return
            iterators.append(it)
            current_values.append(first)

        yield tuple(current_values)

        while iterators:
            idx = len(iterators) - 1
            while idx >= 0:
                nxt = next(iterators[idx], None)
                if nxt is not None:
                    current_values[idx] = nxt
                    break
                iterators[idx].reset()
                first = next(iterators[idx], None)
                if first is None:
                    return
                current_values[idx] = first
                idx -= 1

            if idx < 0:
                return

            yield tuple(current_values)

    def _build_url_from_parts(self, url_parts, range_count, values):
        url = ""
        for i in range(range_count):
            url += url_parts[i] + values[i]
        url += url_parts[-1]
        return url

    def _find_all_ranges(self, url: str) -> List[Tuple[int, int, str]]:
        ranges = []
        for match in self.range_pattern.finditer(url):
            content = match.group(1)
            parsed_segments, _ = self._parse_bracket_content(content)
            for start, end, _ in parsed_segments:
                full_match = f"{start}-{end}" if start != end else str(start)
                ranges.append((start, end, full_match))
        return ranges
