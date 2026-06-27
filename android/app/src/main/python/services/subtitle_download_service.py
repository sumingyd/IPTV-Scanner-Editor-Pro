"""
字幕在线下载服务 - 通过 OpenSubtitles XML-RPC 接口下载字幕

为了避免依赖第三方库，使用标准库 xmlrpc.client 实现。
无需 API Key 即可使用匿名访问（部分功能受限），用户也可配置自己的账号。
"""
import os
import threading
import xmlrpc.client
from core.log_manager import global_logger as logger

# OpenSubtitles 公共 XML-RPC 端点
OS_SERVER_URL = "https://api.opensubtitles.org/xml-rpc"
OS_USER_AGENT = "IPTVScannerEditorPro/1.0"


class SubtitleDownloadService:
    """字幕下载服务（OpenSubtitles）"""

    def __init__(self):
        self._proxy = None
        self._token = None
        self._lock = threading.Lock()

    # ---------- 内部连接 ----------
    def _get_proxy(self):
        if self._proxy is None:
            self._proxy = xmlrpc.client.ServerProxy(OS_SERVER_URL)
        return self._proxy

    def _login_anonymous(self) -> str:
        """匿名登录，返回 token；失败返回空串"""
        if self._token:
            return self._token
        try:
            proxy = self._get_proxy()
            result = proxy.LogIn("", "", "en", OS_USER_AGENT)
            if result.get('status', '').startswith('200'):
                self._token = result.get('token', '')
                return self._token
            logger.warning(f"OpenSubtitles 登录失败: {result.get('status')}")
        except Exception as e:
            logger.warning(f"OpenSubtitles 登录异常: {e}")
        return ''

    def login(self, username: str = "", password: str = "") -> str:
        """用户登录（可空，匿名访问）"""
        try:
            proxy = self._get_proxy()
            result = proxy.LogIn(username or "", password or "", "en", OS_USER_AGENT)
            if result.get('status', '').startswith('200'):
                self._token = result.get('token', '')
                return self._token
        except Exception as e:
            logger.warning(f"OpenSubtitles 用户登录异常: {e}")
        return ''

    # ---------- 搜索 ----------
    def search(self, query: str = "", imdb_id: str = "", language: str = "eng",
               file_path: str = "") -> list:
        """搜索字幕
        query: 文件名/关键词
        imdb_id: IMDb ID（如 tt1234567）
        language: 语言代码（eng, chi, jpn 等，多语言用逗号分隔）
        file_path: 视频文件路径（用于 hash 搜索）
        返回: [{...}] 列表，每项含 IDSubtitleFile/SubFileName/SubDownloadLink/MovieName/LanguageName/Score
        """
        with self._lock:
            token = self._login_anonymous()
            if not token:
                return []
            try:
                proxy = self._get_proxy()
                # 构造查询条件
                query_dict = {'sublanguageid': language}
                if query:
                    query_dict['query'] = query
                if imdb_id:
                    query_dict['imdbid'] = imdb_id
                # 文件 hash 搜索（可选）
                if file_path and os.path.exists(file_path):
                    h, size = self._compute_file_hash(file_path)
                    if h and size:
                        query_dict['moviehash'] = h
                        query_dict['moviebytesize'] = size
                result = proxy.SearchSubtitles(token, [query_dict])
                if not isinstance(result, dict):
                    return []
                if not result.get('status', '').startswith('200'):
                    logger.warning(f"OpenSubtitles 搜索失败: {result.get('status')}")
                    return []
                data = result.get('data', False)
                if not data or data is True:
                    return []
                # data 为 list of dict
                items = []
                for d in data:
                    items.append({
                        'id': d.get('IDSubtitleFile', ''),
                        'file_name': d.get('SubFileName', ''),
                        'download_link': d.get('SubDownloadLink', ''),
                        'zip_link': d.get('ZipDownloadLink', ''),
                        'movie_name': d.get('MovieName', ''),
                        'language': d.get('LanguageName', ''),
                        'language_id': d.get('SubLanguageID', ''),
                        'score': float(d.get('Score', 0) or 0),
                        'format': d.get('SubFormat', 'srt'),
                        'encoding': d.get('SubEncoding', 'UTF-8'),
                        'rating': float(d.get('SubRating', 0) or 0),
                        'bad': d.get('SubBad', '0') == '1',
                        'download_count': int(d.get('SubDownloadCnt', 0) or 0),
                        'add_date': d.get('SubAddDate', ''),
                    })
                # 按评分降序
                items.sort(key=lambda x: (x['score'], x['rating']), reverse=True)
                return items
            except Exception as e:
                logger.warning(f"OpenSubtitles 搜索异常: {e}")
                return []

    # ---------- 下载 ----------
    def download(self, download_link: str, dest_dir: str, file_name: str = "") -> str:
        """下载字幕文件（解压 gzip）到 dest_dir，返回最终路径"""
        try:
            import urllib.request
            os.makedirs(dest_dir, exist_ok=True)
            fname = file_name or os.path.basename(download_link)
            # download_link 通常是 .gz 包裹的 srt 文件
            tmp_path = os.path.join(dest_dir, fname + ".gz")
            req = urllib.request.Request(download_link, headers={'User-Agent': OS_USER_AGENT})
            with urllib.request.urlopen(req, timeout=15) as resp, open(tmp_path, 'wb') as f:
                f.write(resp.read())
            # 解压
            final_name = fname if not fname.endswith('.gz') else fname[:-3]
            final_path = os.path.join(dest_dir, final_name)
            try:
                import gzip
                with gzip.open(tmp_path, 'rb') as gz, open(final_path, 'wb') as out:
                    out.write(gz.read())
                os.remove(tmp_path)
            except Exception:
                # 若不是 gzip，直接重命名
                os.rename(tmp_path, final_path)
            return final_path
        except Exception as e:
            logger.warning(f"下载字幕失败: {e}")
            return ''

    # ---------- 文件 hash（OpenSubtitles 算法） ----------
    @staticmethod
    def _compute_file_hash(file_path: str):
        """OpenSubtitles 文件 hash 算法，返回 (hash_str, size_bytes)"""
        try:
            size = os.path.getsize(file_path)
            if size < 131072:  # 文件太小，hash 算法要求至少 128KB
                return '', 0
            hash_val = size
            with open(file_path, 'rb') as f:
                # 前 64KB
                for i in range(0, 65536, 8):
                    buf = f.read(8)
                    if len(buf) < 8:
                        break
                    (val,) = _unpack_qword(buf)
                    hash_val = (hash_val + val) & 0xFFFFFFFFFFFFFFFFFFFF  # 64-bit
                # 后 64KB
                f.seek(max(0, size - 65536))
                for i in range(0, 65536, 8):
                    buf = f.read(8)
                    if len(buf) < 8:
                        break
                    (val,) = _unpack_qword(buf)
                    hash_val = (hash_val + val) & 0xFFFFFFFFFFFFFFFFFFFF
            return f"{hash_val:016x}", size
        except Exception as e:
            logger.debug(f"计算文件 hash 失败: {e}")
            return '', 0


def _unpack_qword(buf: bytes):
    import struct
    return struct.unpack('<Q', buf)
