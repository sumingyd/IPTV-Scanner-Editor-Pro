import socket
import threading
import time
from urllib.parse import urlparse
from PyQt6.QtCore import QObject, pyqtSignal


class DnsPrefetcher(QObject):
    dns_resolved = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cache = {}
        self._lock = threading.Lock()

    def prefetch(self, url):
        if not url:
            return
        try:
            parsed = urlparse(url)
            host = parsed.hostname
            if not host:
                return
            with self._lock:
                if host in self._cache:
                    return
            t = threading.Thread(target=self._resolve, args=(host,), daemon=True)
            t.start()
        except Exception:
            pass

    def prefetch_many(self, urls):
        for url in urls:
            self.prefetch(url)

    def _resolve(self, host):
        try:
            infos = socket.getaddrinfo(host, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
            if infos:
                ip = infos[0][4][0]
                with self._lock:
                    self._cache[host] = ip
                try:
                    self.dns_resolved.emit(host, ip)
                except RuntimeError:
                    pass
        except Exception:
            with self._lock:
                self._cache[host] = None

    def get_cached_ip(self, host):
        with self._lock:
            return self._cache.get(host)

    def clear(self):
        with self._lock:
            self._cache.clear()


class ConnectionPreheater(QObject):
    connection_ready = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cache = set()
        self._lock = threading.Lock()

    def preheat(self, url):
        if not url:
            return
        try:
            parsed = urlparse(url)
            host = parsed.hostname
            port = parsed.port
            if not host:
                return
            scheme = parsed.scheme.lower()
            if not port:
                if scheme == 'https':
                    port = 443
                elif scheme == 'http':
                    port = 80
                elif scheme == 'rtsp':
                    port = 554
                else:
                    return
            cache_key = f"{host}:{port}"
            with self._lock:
                if cache_key in self._cache:
                    return
            t = threading.Thread(target=self._connect, args=(host, port, cache_key), daemon=True)
            t.start()
        except Exception:
            pass

    def preheat_many(self, urls):
        for url in urls:
            self.preheat(url)

    def _connect(self, host, port, cache_key):
        try:
            sock = socket.create_connection((host, port), timeout=3)
            sock.close()
            with self._lock:
                self._cache.add(cache_key)
            try:
                self.connection_ready.emit(cache_key)
            except RuntimeError:
                pass
        except Exception:
            pass

    def clear(self):
        with self._lock:
            self._cache.clear()
