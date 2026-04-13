import os
import hashlib
import time
import json
import threading
from PyQt6.QtCore import QObject, pyqtSignal, QUrl, QTimer, Qt, QBuffer, QIODevice, QThread
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from PyQt6.QtGui import QPixmap, QImage
from utils.thread_safety import ThreadSafeQObject


class LogoCacheService(ThreadSafeQObject):
    logo_loaded = pyqtSignal(str, QPixmap)

    CACHE_DIR_NAME = 'logo_cache'
    META_FILE = 'meta.json'
    DEFAULT_TTL = 7 * 24 * 3600
    MAX_CACHE_SIZE = 500

    @staticmethod
    def scale_logo_pixmap(pixmap, size=60):
        if pixmap.isNull():
            return pixmap

        from PyQt6.QtWidgets import QApplication
        screen = QApplication.primaryScreen()
        if screen:
            device_pixel_ratio = screen.devicePixelRatio()
        else:
            device_pixel_ratio = 1.0

        target_size = int(size * device_pixel_ratio)
        scaled = pixmap.scaled(target_size, target_size,
                               Qt.AspectRatioMode.KeepAspectRatio,
                               Qt.TransformationMode.SmoothTransformation)
        scaled.setDevicePixelRatio(device_pixel_ratio)

        return scaled

    @staticmethod
    def scale_logo_pixmap_to_fit(pixmap, width, height):
        if pixmap.isNull():
            return pixmap

        from PyQt6.QtWidgets import QApplication
        screen = QApplication.primaryScreen()
        if screen:
            device_pixel_ratio = screen.devicePixelRatio()
        else:
            device_pixel_ratio = 1.0

        target_w = int(width * device_pixel_ratio)
        target_h = int(height * device_pixel_ratio)
        scaled = pixmap.scaled(target_w, target_h,
                               Qt.AspectRatioMode.KeepAspectRatio,
                               Qt.TransformationMode.SmoothTransformation)
        scaled.setDevicePixelRatio(device_pixel_ratio)

        return scaled

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cache_dir = os.path.join(os.getcwd(), self.CACHE_DIR_NAME)
        os.makedirs(self._cache_dir, exist_ok=True)
        self._meta_path = os.path.join(self._cache_dir, self.META_FILE)
        self._meta = self._load_meta()
        self._memory_cache = {}
        self._negative_cache = {}
        self._lock = threading.Lock()
        self._network_manager = QNetworkAccessManager(self)
        self._pending_replies = {}
        self._warmup_queue = []
        self._warmup_timer = QTimer(self)
        self._warmup_timer.setInterval(100)
        self._warmup_timer.timeout.connect(self._process_warmup_queue)

    def _load_meta(self):
        try:
            if os.path.exists(self._meta_path):
                with open(self._meta_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def _save_meta(self):
        try:
            with open(self._meta_path, 'w', encoding='utf-8') as f:
                json.dump(self._meta, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _url_to_key(self, url):
        return hashlib.sha1(url.encode('utf-8')).hexdigest()

    def _disk_path(self, key):
        return os.path.join(self._cache_dir, key)

    def get(self, url):
        if not url:
            return None
        with self._lock:
            if url in self._negative_cache:
                neg_time = self._negative_cache[url]
                if time.time() - neg_time < 3600:
                    return None
                del self._negative_cache[url]
            if url in self._memory_cache:
                return self._memory_cache[url]

        key = self._url_to_key(url)
        disk_path = self._disk_path(key)

        if os.path.exists(disk_path):
            meta_entry = self._meta.get(key, {})
            cached_at = meta_entry.get('time', 0)
            if time.time() - cached_at > self.DEFAULT_TTL:
                try:
                    os.remove(disk_path)
                    self._meta.pop(key, None)
                except Exception:
                    pass
                return None

            pixmap = QPixmap()
            if pixmap.load(disk_path):
                with self._lock:
                    self._memory_cache[url] = pixmap
                return pixmap
        return None

    def put(self, url, pixmap):
        if not url or pixmap.isNull():
            return
        with self._lock:
            self._memory_cache[url] = pixmap
        key = self._url_to_key(url)
        disk_path = self._disk_path(key)
        try:
            pixmap.save(disk_path, 'PNG')
            self._meta[key] = {
                'url': url,
                'time': time.time(),
            }
            self._save_meta()
        except Exception:
            pass

    def mark_negative(self, url):
        with self._lock:
            self._negative_cache[url] = time.time()

    def fetch_async(self, url):
        if not url:
            return
        if not self._ensure_main_thread(self.fetch_async, url):
            return
        with self._lock:
            if url in self._memory_cache:
                self.logo_loaded.emit(url, self._memory_cache[url])
                return
            if url in self._negative_cache:
                if time.time() - self._negative_cache[url] < 3600:
                    return
                del self._negative_cache[url]

        cached = self.get(url)
        if cached:
            self.logo_loaded.emit(url, cached)
            return

        if url in self._pending_replies:
            return

        try:
            request = QNetworkRequest(QUrl(url))
            request.setHeader(QNetworkRequest.KnownHeaders.UserAgentHeader,
                              'Mozilla/5.0 (Windows NT 10.0; Win64; x64)')
            reply = self._network_manager.get(request)
            self._pending_replies[url] = reply
            reply.finished.connect(lambda: self._on_download_finished(url, reply))
        except Exception:
            self.mark_negative(url)

    def _on_download_finished(self, url, reply):
        self._pending_replies.pop(url, None)
        try:
            if reply.error() != QNetworkReply.NetworkError.NoError:
                self.mark_negative(url)
                reply.deleteLater()
                return

            content_type = reply.header(QNetworkRequest.KnownHeaders.ContentTypeHeader)
            if content_type and isinstance(content_type, str):
                ct = content_type.lower()
                if 'text/' in ct or 'html' in ct or 'json' in ct:
                    self.mark_negative(url)
                    reply.deleteLater()
                    return

            data = reply.readAll()
            if not data or len(data) < 100:
                self.mark_negative(url)
                reply.deleteLater()
                return

            pixmap = QPixmap()
            if pixmap.loadFromData(data.data()):
                self.put(url, pixmap)
                self.logo_loaded.emit(url, pixmap)
            else:
                self.mark_negative(url)
        except Exception:
            self.mark_negative(url)
        finally:
            reply.deleteLater()

    def warmup(self, urls):
        if not urls:
            return
        if not self._ensure_main_thread(self.warmup, urls):
            return
        self._warmup_queue.extend(urls)
        if not self._warmup_timer.isActive():
            self._warmup_timer.start()

    def _process_warmup_queue(self):
        if not self._warmup_queue:
            self._warmup_timer.stop()
            return
        batch = 5
        for _ in range(batch):
            if not self._warmup_queue:
                break
            url = self._warmup_queue.pop(0)
            if url and url not in self._memory_cache and url not in self._negative_cache:
                cached = self.get(url)
                if not cached:
                    self.fetch_async(url)

    def clear(self):
        with self._lock:
            self._memory_cache.clear()
            self._negative_cache.clear()
        try:
            for f in os.listdir(self._cache_dir):
                fp = os.path.join(self._cache_dir, f)
                if os.path.isfile(fp):
                    os.remove(fp)
            self._meta.clear()
            self._save_meta()
        except Exception:
            pass

    def evict_expired(self):
        now = time.time()
        expired_keys = []
        for key, meta in list(self._meta.items()):
            if now - meta.get('time', 0) > self.DEFAULT_TTL:
                expired_keys.append(key)
        for key in expired_keys:
            disk_path = self._disk_path(key)
            try:
                if os.path.exists(disk_path):
                    os.remove(disk_path)
            except Exception:
                pass
            self._meta.pop(key, None)
        if expired_keys:
            self._save_meta()
