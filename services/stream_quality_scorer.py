from typing import Dict, Any, Optional
from core.log_manager import global_logger as logger


class StreamQualityScorer:
    MAX_LATENCY_MS = 5000
    MIN_BITRATE_KBPS = 500
    RESOLUTION_SCORES = {
        '4k': 100, '2160p': 100,
        '2k': 85, '1440p': 85,
        '1080p': 75, 'fhd': 75,
        '720p': 55, 'hd': 55,
        '576p': 40, 'sd': 40,
        '480p': 25,
        '360p': 15,
        '240p': 5,
    }

    @staticmethod
    def score(latency_ms: Optional[float] = None,
              bitrate_kbps: Optional[float] = None,
              resolution: Optional[str] = None,
              is_valid: Optional[bool] = None) -> Dict[str, Any]:
        if is_valid is False:
            return {'total': 0, 'grade': 'F', 'details': {'valid': False}}

        latency_score = 0.0
        if latency_ms is not None:
            if latency_ms <= 100:
                latency_score = 30
            elif latency_ms <= 500:
                latency_score = 25
            elif latency_ms <= 1000:
                latency_score = 20
            elif latency_ms <= 2000:
                latency_score = 15
            elif latency_ms <= StreamQualityScorer.MAX_LATENCY_MS:
                latency_score = 10
            else:
                latency_score = 5

        bitrate_score = 0.0
        if bitrate_kbps is not None:
            if bitrate_kbps >= 8000:
                bitrate_score = 35
            elif bitrate_kbps >= 4000:
                bitrate_score = 30
            elif bitrate_kbps >= 2000:
                bitrate_score = 25
            elif bitrate_kbps >= 1000:
                bitrate_score = 20
            elif bitrate_kbps >= StreamQualityScorer.MIN_BITRATE_KBPS:
                bitrate_score = 15
            else:
                bitrate_score = 5

        res_score = 0.0
        if resolution:
            res_lower = resolution.lower().replace(' ', '')
            for key, score in StreamQualityScorer.RESOLUTION_SCORES.items():
                if key in res_lower:
                    res_score = score * 0.35
                    break
            if res_score == 0:
                try:
                    h = int(res_lower.split('x')[-1]) if 'x' in res_lower else 0
                    if h >= 2160:
                        res_score = 35
                    elif h >= 1440:
                        res_score = 30
                    elif h >= 1080:
                        res_score = 26
                    elif h >= 720:
                        res_score = 19
                    elif h >= 480:
                        res_score = 14
                    else:
                        res_score = 5
                except (ValueError, IndexError):
                    res_score = 17.5

        total = latency_score + bitrate_score + res_score
        if total >= 85:
            grade = 'A'
        elif total >= 70:
            grade = 'B'
        elif total >= 55:
            grade = 'C'
        elif total >= 35:
            grade = 'D'
        else:
            grade = 'F'

        return {
            'total': round(total, 1),
            'grade': grade,
            'details': {
                'latency_score': round(latency_score, 1),
                'bitrate_score': round(bitrate_score, 1),
                'resolution_score': round(res_score, 1),
                'valid': True,
            }
        }

    @staticmethod
    def score_from_channel(channel: Dict[str, Any]) -> Dict[str, Any]:
        latency = None
        latency_raw = channel.get('latency', '')
        if latency_raw:
            try:
                latency = float(str(latency_raw).replace('ms', '').strip())
            except (ValueError, TypeError):
                pass

        bitrate = None
        br_raw = channel.get('bitrate', '') or channel.get('video_bitrate', '')
        if br_raw:
            try:
                bitrate = float(str(br_raw).replace('kbps', '').replace('Mbps', '').strip())
                if 'Mbps' in str(br_raw):
                    bitrate *= 1000
            except (ValueError, TypeError):
                pass

        resolution = channel.get('resolution', '')
        is_valid = channel.get('valid', None)

        return StreamQualityScorer.score(latency, bitrate, resolution, is_valid)