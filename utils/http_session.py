import threading

try:
    import requests
    from requests.adapters import HTTPAdapter
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False
    requests = None
    HTTPAdapter = None

_session = None
_lock = threading.Lock()


def get_session():
    global _session
    if not _HAS_REQUESTS:
        return None
    if _session is None:
        with _lock:
            if _session is None:
                _session = requests.Session()
                adapter = HTTPAdapter(pool_connections=10, pool_maxsize=20, max_retries=0)
                _session.mount('http://', adapter)
                _session.mount('https://', adapter)
    return _session


def get(url, **kwargs):
    session = get_session()
    if session is None:
        raise ImportError('requests is not available')
    # 统一用标量超时：此环境实测 requests 会把 (connect, read) 元组按相反顺序解释，
    # 传 (10, 30) 实际读超时只有 10s，弱网下载订阅源必然超时。
    # 标量 t 保证读超时完整为调用方指定值（订阅源加载传 30s）。
    if 'timeout' not in kwargs:
        kwargs['timeout'] = 30.0
    elif isinstance(kwargs['timeout'], (int, float)):
        kwargs['timeout'] = float(kwargs['timeout'])
    return session.get(url, **kwargs)


def head(url, **kwargs):
    session = get_session()
    if session is None:
        raise ImportError('requests is not available')
    if 'timeout' not in kwargs:
        kwargs['timeout'] = 30.0
    elif isinstance(kwargs['timeout'], (int, float)):
        kwargs['timeout'] = float(kwargs['timeout'])
    return session.head(url, **kwargs)


def post(url, **kwargs):
    session = get_session()
    if session is None:
        raise ImportError('requests is not available')
    if 'timeout' not in kwargs:
        kwargs['timeout'] = 30.0
    elif isinstance(kwargs['timeout'], (int, float)):
        kwargs['timeout'] = float(kwargs['timeout'])
    return session.post(url, **kwargs)


def close():
    global _session
    if _session is not None:
        with _lock:
            if _session is not None:
                _session.close()
                _session = None