"""
字幕在线下载服务 - 通过 OpenSubtitles XML-RPC 接口下载字幕

使用标准库 xmlrpc.client 实现，无需 API Key 即可匿名访问。
增加超时控制、重试机制和详细错误反馈。
"""
import os
import socket
import threading
import xmlrpc.client
from core.log_manager import global_logger as logger

# OpenSubtitles 公共 XML-RPC 端点（实测 2026 年仍可用）
OS_SERVER_URL = "https://api.opensubtitles.org/xml-rpc"
OS_USER_AGENT = "IPTVScannerEditorPro/1.0"

# 网络超时（秒）—— OpenSubtitles 服务器在欧洲，国内访问可能较慢
DEFAULT_TIMEOUT = 30
# 登录/搜索最大重试次数
MAX_RETRIES = 2


class _TimeoutTransport(xmlrpc.client.Transport):
    """带超时控制的 XML-RPC Transport"""

    def __init__(self, timeout=DEFAULT_TIMEOUT):
        super().__init__()
        self._timeout = timeout

    def make_connection(self, host):
        conn = super().make_connection(host)
        conn.timeout = self._timeout
        return conn


class SubtitleDownloadService:
    """字幕下载服务（OpenSubtitles）"""

    def __init__(self):
        self._proxy = None
        self._token = None
        self._lock = threading.Lock()
        # 最近一次错误信息（供 UI 显示具体原因，而非笼统的"没有找到字幕"）
        self.last_error = ''

    # ---------- 内部连接 ----------
    def _get_proxy(self):
        if self._proxy is None:
            self._proxy = xmlrpc.client.ServerProxy(
                OS_SERVER_URL,
                transport=_TimeoutTransport(DEFAULT_TIMEOUT),
                allow_none=True,
            )
        return self._proxy

    def _login_anonymous(self) -> str:
        """匿名登录，返回 token；失败返回空串并设置 last_error"""
        if self._token:
            return self._token
        last_exc = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                proxy = self._get_proxy()
                result = proxy.LogIn("", "", "en", OS_USER_AGENT)
                status = result.get('status', '')
                if status.startswith('200'):
                    self._token = result.get('token', '')
                    if self._token:
                        return self._token
                # 401 通常是 UA 未注册或被限流
                self.last_error = f'OpenSubtitles 登录被拒绝 (status={status})。可能是 User-Agent 被限流，请稍后重试。'
                logger.warning(self.last_error)
                return ''
            except (socket.timeout, TimeoutError) as e:
                last_exc = e
                self.last_error = f'连接 OpenSubtitles 超时（{DEFAULT_TIMEOUT}s）。可能是网络问题或被防火墙拦截。'
                logger.warning(f'登录超时 (尝试 {attempt+1}/{MAX_RETRIES+1}): {e}')
                # 超时后重置代理，避免连接复用问题
                self._proxy = None
            except Exception as e:
                last_exc = e
                self.last_error = f'连接 OpenSubtitles 失败: {type(e).__name__}: {e}'
                logger.warning(f'登录异常 (尝试 {attempt+1}/{MAX_RETRIES+1}): {e}')
                self._proxy = None
        if last_exc:
            logger.warning(f'登录最终失败: {last_exc}')
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
            self.last_error = f'OpenSubtitles 用户登录异常: {e}'
            logger.warning(self.last_error)
        return ''

    # ---------- 搜索 ----------
    def search(self, query: str = "", imdb_id: str = "", language: str = "eng",
               file_path: str = "") -> list:
        """搜索字幕

        Args:
            query: 文件名/关键词（如片名）
            imdb_id: IMDb ID（如 tt1234567）
            language: 语言代码（eng, chi, jpn 等，多语言用逗号分隔；
                      'all' 或空表示不限语言）
            file_path: 视频文件路径（用于 hash 搜索）

        Returns:
            字幕信息列表，每项含 file_name/download_link/movie_name/language/rating 等。
            失败返回空列表，并设置 self.last_error。
        """
        self.last_error = ''
        with self._lock:
            token = self._login_anonymous()
            if not token:
                return []
            try:
                proxy = self._get_proxy()
                # 构造查询条件
                query_dict = {}
                # 'all' 不是合法的 sublanguageid，留空让 OpenSubtitles 返回所有语言
                if language and language != 'all':
                    query_dict['sublanguageid'] = language
                if query:
                    query_dict['query'] = query
                if imdb_id:
                    query_dict['imdbid'] = imdb_id
                # 文件 hash 搜索（可选，比关键词更精准）
                if file_path and os.path.exists(file_path):
                    h, size = self._compute_file_hash(file_path)
                    if h and size:
                        query_dict['moviehash'] = h
                        query_dict['moviebytesize'] = size

                # SearchSubtitles 要求至少 query 或 moviehash 之一
                # 仅传 sublanguageid 不会返回结果，提前提示用户
                if 'query' not in query_dict and 'moviehash' not in query_dict and 'imdbid' not in query_dict:
                    self.last_error = '请输入片名，或打开本地视频文件以使用哈希精准匹配'
                    return []

                result = proxy.SearchSubtitles(token, [query_dict])
                if not isinstance(result, dict):
                    self.last_error = 'OpenSubtitles 返回了非预期的数据格式'
                    return []
                if not result.get('status', '').startswith('200'):
                    status = result.get('status', 'unknown')
                    self.last_error = f'OpenSubtitles 搜索失败 (status={status})'
                    logger.warning(self.last_error)
                    return []
                data = result.get('data', False)
                if not data or data is True:
                    # 真正的"没找到"，不是错误
                    self.last_error = ''
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
            except (socket.timeout, TimeoutError) as e:
                self.last_error = f'搜索请求超时（{DEFAULT_TIMEOUT}s）。请检查网络连接后重试。'
                logger.warning(self.last_error + f' ({e})')
                self._proxy = None
                self._token = None
                return []
            except Exception as e:
                self.last_error = f'搜索异常: {type(e).__name__}: {e}'
                logger.warning(self.last_error)
                # 重置代理，下次重新连接
                self._proxy = None
                self._token = None
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
            with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT) as resp, open(tmp_path, 'wb') as f:
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
            self.last_error = f'下载字幕失败: {type(e).__name__}: {e}'
            logger.warning(self.last_error)
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
