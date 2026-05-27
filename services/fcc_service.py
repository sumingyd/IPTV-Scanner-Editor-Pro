"""
FCC (Fast Channel Change) 快速换台服务

IPTV 组播场景中，FCC 代理用于加速频道切换：
- 客户端换台时通过 UDP 向 FCC 代理发送 leave/join 通知
- FCC 代理在服务端侧完成 IGMP leave/join，快速转发新频道流
- 客户端无需等待 IGMP 加入延迟

URL 格式示例：
  rtp://239.1.1.1:5002?fcc=150.138.8.132:8027
  udp://239.2.1.5:5000?fcc=10.0.0.1:9000

FCC 通知协议（UDP 文本）：
  LEAVE <multicast_ip> <multicast_port>\n
  JOIN <multicast_ip> <multicast_port>\n
"""

import socket
import threading
from urllib.parse import urlparse, parse_qs
from typing import Optional, Tuple

from core.log_manager import global_logger as logger


def parse_fcc_from_url(url: str) -> Optional[Tuple[str, int]]:
    """从频道 URL 中解析 FCC 代理地址

    Args:
        url: 频道URL，如 rtp://239.1.1.1:5002?fcc=150.138.8.132:8027

    Returns:
        (fcc_ip, fcc_port) 元组，若无 fcc 参数则返回 None
    """
    if not url or '?fcc=' not in url.lower():
        return None
    try:
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        fcc_val = qs.get('fcc', [None])
        if not fcc_val or not fcc_val[0]:
            return None
        fcc_addr = fcc_val[0]
        if ':' in fcc_addr:
            ip, port_str = fcc_addr.rsplit(':', 1)
            port = int(port_str)
        else:
            ip = fcc_addr
            port = 8027
        return (ip, port)
    except Exception as e:
        logger.debug(f"解析FCC参数失败: {e}, url={url}")
        return None


def parse_multicast_from_url(url: str) -> Optional[Tuple[str, int]]:
    """从 URL 中提取组播地址和端口

    Args:
        url: 如 rtp://239.1.1.1:5002?fcc=...

    Returns:
        (multicast_ip, multicast_port) 元组，若非组播地址则返回 None
    """
    if not url:
        return None
    try:
        parsed = urlparse(url)
        host = parsed.hostname
        port = parsed.port
        if not host or not port:
            return None
        if not _is_multicast_ip(host):
            return None
        return (host, port)
    except Exception:
        return None


def _is_multicast_ip(ip: str) -> bool:
    """判断是否为组播IP地址（224.0.0.0 ~ 239.255.255.255）"""
    try:
        parts = ip.split('.')
        if len(parts) != 4:
            return False
        first = int(parts[0])
        return 224 <= first <= 239
    except Exception:
        return False


def send_fcc_notification(
    fcc_ip: str,
    fcc_port: int,
    leave_addr: Optional[Tuple[str, int]] = None,
    join_addr: Optional[Tuple[str, int]] = None,
    timeout: float = 1.0,
) -> bool:
    """向 FCC 代理发送换台通知（UDP）

    Args:
        fcc_ip: FCC 代理IP
        fcc_port: FCC 代理端口
        leave_addr: 要离开的组播地址 (ip, port)，可为 None
        join_addr: 要加入的组播地址 (ip, port)，可为 None
        timeout: UDP 超时秒数

    Returns:
        是否发送成功
    """
    messages = []
    if leave_addr:
        messages.append(f"LEAVE {leave_addr[0]} {leave_addr[1]}")
    if join_addr:
        messages.append(f"JOIN {join_addr[0]} {join_addr[1]}")

    if not messages:
        return True

    payload = '\n'.join(messages) + '\n'
    return _send_udp(fcc_ip, fcc_port, payload.encode('utf-8'), timeout)


def _send_udp(ip: str, port: int, data: bytes, timeout: float = 1.0) -> bool:
    """发送 UDP 数据包"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)
        sock.sendto(data, (ip, port))
        sock.close()
        logger.debug(f"FCC通知已发送: {ip}:{port}, 数据: {data!r}")
        return True
    except Exception as e:
        logger.debug(f"FCC通知发送失败: {e}")
        return False


class FCCService:
    """FCC 快速换台服务管理器

    跟踪当前播放频道的组播地址，换台时自动向 FCC 代理发送 leave/join。
    """

    def __init__(self):
        self._current_multicast: Optional[Tuple[str, int]] = None
        self._current_fcc: Optional[Tuple[str, int]] = None

    def on_channel_change(self, new_url: str) -> None:
        """频道切换时调用——同步发送FCC join通知，异步发送leave通知

        Args:
            new_url: 新频道的URL
        """
        fcc_addr = parse_fcc_from_url(new_url)
        new_multicast = parse_multicast_from_url(new_url)

        if not fcc_addr:
            self._current_multicast = new_multicast
            self._current_fcc = None
            return

        leave_addr = self._current_multicast
        join_addr = new_multicast

        self._current_multicast = new_multicast
        self._current_fcc = fcc_addr

        if leave_addr == join_addr:
            return

        if leave_addr:
            threading.Thread(
                target=self._notify_fcc,
                args=(fcc_addr, leave_addr, None),
                daemon=True,
            ).start()

        if join_addr:
            try:
                send_fcc_notification(fcc_addr[0], fcc_addr[1], None, join_addr, timeout=0.5)
                import time
                time.sleep(0.05)
            except Exception as e:
                logger.debug(f"FCC join同步发送失败: {e}")

    def on_stop(self) -> None:
        """停止播放时调用——发送 leave 通知"""
        if self._current_fcc and self._current_multicast:
            fcc = self._current_fcc
            leave = self._current_multicast
            threading.Thread(
                target=send_fcc_notification,
                args=(fcc[0], fcc[1], leave, None),
                daemon=True,
            ).start()
        self._current_multicast = None
        self._current_fcc = None

    @staticmethod
    def _notify_fcc(fcc_addr, leave_addr, join_addr):
        try:
            send_fcc_notification(fcc_addr[0], fcc_addr[1], leave_addr, join_addr)
        except Exception as e:
            logger.debug(f"FCC通知线程异常: {e}")

    def reset(self) -> None:
        """重置状态"""
        self._current_multicast = None
        self._current_fcc = None
