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


# ---------------------------------------------------------------------------
# 持久化 UDP socket —— 避免每次通知都创建/关闭 socket 的开销
# ---------------------------------------------------------------------------
_udp_sock_lock = threading.Lock()
_udp_sock: Optional[socket.socket] = None


def _get_udp_socket() -> socket.socket:
    """获取（必要时创建）持久化 UDP socket。

    使用非阻塞模式（setblocking(False)），sendto 永不阻塞，
    实现 fire-and-forget 语义——UDP 本身不保证送达，无需等待。
    """
    global _udp_sock
    if _udp_sock is not None:
        return _udp_sock
    with _udp_sock_lock:
        if _udp_sock is None:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setblocking(False)  # 非阻塞：sendto 立即返回
            _udp_sock = sock
            logger.debug("FCC持久化UDP socket已创建")
    return _udp_sock


def _close_udp_socket():
    """关闭持久化 UDP socket（应用退出时调用）"""
    global _udp_sock
    with _udp_sock_lock:
        if _udp_sock is not None:
            try:
                _udp_sock.close()
            except Exception as e:
                logger.debug(f"_close_udp_socket: {e}")
            _udp_sock = None


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
        fcc_val = qs.get('fcc', qs.get('FCC', [None]))
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

    使用持久化非阻塞 socket，LEAVE+JOIN 合并为单个 UDP 包发送，
    减少 socket 操作次数和网络往返延迟。

    Args:
        fcc_ip: FCC 代理IP
        fcc_port: FCC 代理端口
        leave_addr: 要离开的组播地址 (ip, port)，可为 None
        join_addr: 要加入的组播地址 (ip, port)，可为 None
        timeout: 已弃用（非阻塞模式无需超时），保留以保持向后兼容

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
    return _send_udp(fcc_ip, fcc_port, payload.encode('utf-8'))


def _send_udp(ip: str, port: int, data: bytes, timeout: float = 0.0) -> bool:
    """发送 UDP 数据包（使用持久化非阻塞 socket）

    非阻塞模式下的 sendto 行为：
    - 正常情况：数据拷贝到内核发送缓冲区后立即返回
    - 缓冲区满：抛出 BlockingIOError，静默忽略（UDP 不保证送达）
    """
    try:
        sock = _get_udp_socket()
        sock.sendto(data, (ip, port))
        logger.debug(f"FCC通知已发送: {ip}:{port}, 数据: {data!r}")
        return True
    except BlockingIOError:
        # 内核发送缓冲区满，UDP 本就不保证送达，静默忽略
        logger.debug(f"FCC通知发送缓冲区满，已丢弃: {ip}:{port}")
        return False
    except Exception as e:
        logger.debug(f"FCC通知发送失败: {e}")
        return False


class FCCService:
    """FCC 快速换台服务管理器

    跟踪当前播放频道的组播地址，换台时自动向 FCC 代理发送 leave/join。

    优化点：
    - LEAVE+JOIN 合并为单个 UDP 包，一次 socket 操作完成换台通知
    - 使用持久化非阻塞 socket，消除每次创建/关闭 socket 的开销
    - 无需额外线程：单包发送足够快（微秒级），不会阻塞 UI 线程
    """

    def __init__(self):
        self._current_multicast: Optional[Tuple[str, int]] = None
        self._current_fcc: Optional[Tuple[str, int]] = None

    def on_channel_change(self, new_url: str) -> None:
        """频道切换时调用——合并 LEAVE+JOIN 为单个 UDP 包同步发送

        优化说明：
        - 旧实现：JOIN 同步发送 + LEAVE 异步线程发送（2 次 socket 操作 + 1 次线程创建）
        - 新实现：LEAVE+JOIN 合并为 1 个 UDP 包同步发送（1 次 socket 操作，0 次线程创建）
        - rtp2httpd 收到 LEAVE+JOIN 后可立即释放旧流资源并转发新流

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

        # 合并 LEAVE+JOIN 为单个 UDP 包，一次发送完成
        # 非阻塞 socket + sendto 耗时 < 0.1ms，无需异步线程
        if join_addr or leave_addr:
            try:
                send_fcc_notification(
                    fcc_addr[0], fcc_addr[1],
                    leave_addr=leave_addr,
                    join_addr=join_addr,
                )
            except Exception as e:
                logger.debug(f"FCC通知发送失败: {e}")

    def on_stop(self) -> None:
        """停止播放时调用——发送 leave 通知"""
        if self._current_fcc and self._current_multicast:
            fcc = self._current_fcc
            leave = self._current_multicast
            try:
                send_fcc_notification(fcc[0], fcc[1], leave_addr=leave)
            except Exception as e:
                logger.debug(f"FCC leave通知失败: {e}")
        self._current_multicast = None
        self._current_fcc = None

    def reset(self) -> None:
        """重置状态"""
        self._current_multicast = None
        self._current_fcc = None
