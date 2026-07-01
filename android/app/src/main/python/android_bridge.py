import importlib
import logging
import os
import sys
import time

_t0 = time.time()

def _log(msg, level='I'):
    """统一日志输出：Chaquopy 会把 print() 重定向到 logcat 的 python 标签"""
    elapsed = time.time() - _t0
    print(f'[{level}][{elapsed:6.2f}s] {msg}', flush=True)


def _setup_android_paths():
    """设置 Android 数据目录路径（IPTV_DATA_DIR 环境变量）。

    关键：必须使用 jnius 的 autoclass 访问 Chaquopy 的 Java API，
    而非 importlib.import_module('chaquopy.python')（该 Python 模块在
    Chaquopy 运行时不存在，会抛 ModuleNotFoundError）。

    如果 IPTV_DATA_DIR 未正确设置，ConfigManager 会走 fallback 路径，
    将 config.ini 写到 Chaquopy AssetFinder 解压目录（路径含基于 APK
    内容的 hash），覆盖安装新版本后该目录被废弃，导致订阅源/EPG源/设置丢失。
    """
    if not getattr(sys, 'platform', '') == 'android':
        return
    try:
        from jnius import autoclass
        Python = autoclass('com.chaquo.python.Python')
        app = Python.getPlatform().getApplication()
        files_dir = app.getFilesDir().getAbsolutePath()
        os.environ['IPTV_DATA_DIR'] = files_dir
        if files_dir not in sys.path:
            sys.path.insert(0, files_dir)
        _log(f'_setup_android_paths: IPTV_DATA_DIR={files_dir}')
    except Exception as e:
        _log(f'_setup_android_paths failed: {e}', 'E')


def _setup_android_logging():
    """设置 Android 日志：优先用 AndroidLog，失败则用 print() fallback"""
    try:
        from jnius import autoclass
        AndroidLog = autoclass('android.util.Log')
        class AndroidLogHandler(logging.Handler):
            def emit(self, record):
                msg = self.format(record)
                level = record.levelno
                tag = record.name[:23]
                if level >= logging.ERROR:
                    AndroidLog.e(tag, msg)
                elif level >= logging.WARNING:
                    AndroidLog.w(tag, msg)
                elif level >= logging.INFO:
                    AndroidLog.i(tag, msg)
                elif level >= logging.DEBUG:
                    AndroidLog.d(tag, msg)
                else:
                    AndroidLog.v(tag, msg)
        root = logging.getLogger()
        if not any(isinstance(h, AndroidLogHandler) for h in root.handlers):
            root.addHandler(AndroidLogHandler())
        _log('Android logging via jnius OK')
        return True
    except Exception as e:
        _log(f'jnius logging unavailable, using print fallback: {e}', 'W')

    # Fallback: 用 print() 输出日志（Chaquopy 会重定向到 logcat 的 python 标签）
    class PrintLogHandler(logging.Handler):
        def emit(self, record):
            msg = self.format(record)
            level = record.levelname[0]
            print(f'[{level}] {record.name}: {msg}', flush=True)
    root = logging.getLogger()
    if not any(isinstance(h, PrintLogHandler) for h in root.handlers):
        root.addHandler(PrintLogHandler())
    _log('Android logging via print fallback OK')
    return False


def _find_mobile_dir():
    try:
        import server
        server_dir = os.path.dirname(os.path.abspath(server.__file__))
        mobile_dir = os.path.join(server_dir, 'mobile')
        if os.path.isdir(mobile_dir):
            return mobile_dir
    except Exception:
        pass
    this_dir = os.path.dirname(os.path.abspath(__file__))
    for candidate in [
        os.path.join(this_dir, 'server', 'mobile'),
        os.path.join(this_dir, 'mobile'),
    ]:
        if os.path.isdir(candidate):
            return candidate
    return None


_server_started = False


def start_server(host='0.0.0.0', port=8080):
    global _server_started
    if _server_started:
        return
    _server_started = True

    _log('start_server begin')
    _setup_android_paths()
    _log('paths setup done')

    _setup_android_logging()
    _log('logging setup done')

    logger = logging.getLogger('android_bridge')
    logger.info('Starting IPTV server on Android...')
    _log('importing modules...')

    import asyncio
    from server.context import ServerContext
    from server.routes import create_app
    from server.app import get_server
    from aiohttp import web
    _log('modules imported')

    data_dir = os.environ.get('IPTV_DATA_DIR', os.path.expanduser('~'))
    config_dir = os.path.join(data_dir, 'IPTV_Scanner_Editor_Pro')
    os.makedirs(config_dir, exist_ok=True)
    os.chdir(config_dir)
    _log(f'config_dir={config_dir}')

    _log('initializing ServerContext...')
    ServerContext.get_instance(main_window=None)
    _log('ServerContext initialized')

    _log('creating app...')
    app = create_app()
    _log('app created')

    mobile_dir = _find_mobile_dir()
    if mobile_dir:
        _register_mobile_routes(app, mobile_dir)
        logger.info(f'Mobile UI served from: {mobile_dir}')
        _log(f'mobile UI registered from: {mobile_dir}')
    else:
        logger.warning('Mobile UI directory not found, /mobile/ will not be available')
        _log('Mobile UI directory not found!', 'W')

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    _log('event loop created')

    async def _run():
        _log('runner.setup()...')
        runner = web.AppRunner(app)
        await runner.setup()
        _log('runner.setup() done')
        _log('site.start()...')
        site = web.TCPSite(runner, host, port)
        await site.start()
        _log(f'IPTV server running at http://{host}:{port}')
        logger.info(f'IPTV server running at http://{host}:{port}')
        # 标记 IPTVServer 为运行中，使首页状态显示正确
        svr = get_server()
        if svr:
            svr._running = True
            svr._start_time = time.time()
        try:
            while True:
                await asyncio.sleep(3600)
        except asyncio.CancelledError:
            pass
        finally:
            await runner.cleanup()

    try:
        loop.run_until_complete(_run())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        _log(f'server crashed: {e}', 'E')
        logger.error(f'server crashed: {e}', exc_info=True)
        raise
    finally:
        loop.close()


def stop_server():
    pass


_MIME_TYPES = {
    '.html': 'text/html',
    '.css': 'text/css',
    '.js': 'application/javascript',
    '.json': 'application/json',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.svg': 'image/svg+xml',
    '.ico': 'image/x-icon',
    '.woff': 'font/woff',
    '.woff2': 'font/woff2',
    '.ttf': 'font/ttf',
    '.webmanifest': 'application/manifest+json',
}


def _register_mobile_routes(app, base_dir):
    async def _handle_mobile(request):
        from aiohttp import web
        rel_path = request.match_info.get('path', 'index.html')
        if not rel_path or rel_path.endswith('/'):
            rel_path += 'index.html'
        file_path = os.path.join(base_dir, rel_path)
        if not os.path.isfile(file_path):
            return web.Response(text='404: Not Found', status=404)
        ext = os.path.splitext(rel_path)[1].lower()
        content_type = _MIME_TYPES.get(ext, 'application/octet-stream')
        with open(file_path, 'rb') as f:
            content = f.read()
        return web.Response(body=content, content_type=content_type, headers={'Cache-Control':'no-cache, no-store, must-revalidate','Pragma':'no-cache','Expires':'0'})

    app.router.add_get('/mobile/', _handle_mobile)
    app.router.add_get('/mobile/{path:.*}', _handle_mobile)

    # 注册管理后台路由（局域网 Web 管理页面）
    # 注意：routes.py 中的 _register_admin_routes 在 Android 上可能找不到目录
    # 因为 Chaquopy 打包后 server.__file__ 可能指向非标准路径
    # 这里用 _find_mobile_dir 找到的 server_dir 来定位 admin 目录
    server_dir = os.path.dirname(base_dir)
    admin_dir = os.path.join(server_dir, 'admin')
    if os.path.isdir(admin_dir):
        async def _handle_admin(request):
            from aiohttp import web
            rel_path = request.match_info.get('path', 'index.html')
            if not rel_path or rel_path.endswith('/'):
                rel_path += 'index.html'
            file_path = os.path.join(admin_dir, rel_path)
            if not os.path.isfile(file_path):
                return web.Response(text='404: Not Found', status=404)
            ext = os.path.splitext(rel_path)[1].lower()
            content_type = _MIME_TYPES.get(ext, 'application/octet-stream')
            with open(file_path, 'rb') as f:
                content = f.read()
            return web.Response(body=content, content_type=content_type,
                              headers={'Cache-Control':'no-cache, no-store, must-revalidate',
                                       'Pragma':'no-cache','Expires':'0'})

        # create_app() 内部已调用 _register_admin_routes 注册了 /admin/ 路由
        # 这里重复注册会抛 ValueError，用 try/except 忽略
        try:
            app.router.add_get('/admin/', _handle_admin)
            app.router.add_get('/admin/{path:.*}', _handle_admin)
            _log(f'admin UI registered from: {admin_dir}')
        except ValueError:
            _log('admin routes already registered by create_app(), skipping')


# ===================================================================
# 阶段 1：Chaquopy 直调入口（替代 HTTP endpoint）
# 设计原则：
#  - 与现有 start_server 并存，不破坏 WebView 流程
#  - Compose 端通过 Python.getInstance().getModule("android_bridge")
#       .callAttr("method_name", *args).toString() 调用
#  - 返回值统一为 JSON 字符串（Chaquopy 不能直接传 dict/list）
#  - 耗时操作（reload_sources / start_scan / reload_epg / refresh_mappings /
#    search_subtitles / download_subtitle）立即返回，内部启动 daemon 线程
#  - 调用者应在 Kotlin Dispatchers.IO 中调用，避免阻塞 UI 线程
# ===================================================================

import json as _json
import threading as _threading

_ctx_lock = _threading.Lock()
_inited = False


def _ok(data):
    """序列化成功响应。data 可以是 dict/list/str/int/bool/None"""
    return _json.dumps(data, ensure_ascii=False, default=str)


def _err(message, **extra):
    """序列化错误响应。message 是错误描述，extra 附加字段"""
    payload = {'error': str(message)}
    payload.update(extra)
    return _json.dumps(payload, ensure_ascii=False)


def init_context():
    """初始化 Python 环境 + ServerContext 单例，立即返回（不阻塞）。

    返回 'OK' 表示成功，'FAILED: ...' 表示错误。
    Compose 端应在 Dispatchers.IO 调用，调用后用 get_status_json() 轮询加载进度。
    """
    global _inited
    with _ctx_lock:
        if _inited:
            return 'OK'
        try:
            _setup_android_paths()
            _setup_android_logging()
            _log('init_context: paths and logging setup done')

            # 切换工作目录到 config_dir（与 start_server() 保持一致）
            # 确保相对路径文件（如 cache/epg_cache.json）写入正确位置
            data_dir = os.environ.get('IPTV_DATA_DIR', '')
            if data_dir:
                config_dir = os.path.join(data_dir, 'IPTV_Scanner_Editor_Pro')
                os.makedirs(config_dir, exist_ok=True)
                os.chdir(config_dir)
                _log(f'init_context: chdir to {config_dir}')

            from server.context import ServerContext
            ServerContext.get_instance(main_window=None)
            _log('init_context: ServerContext initialized (standalone mode)')
            _inited = True
            return 'OK'
        except Exception as e:
            _log(f'init_context failed: {e}', 'E')
            import traceback
            traceback.print_exc()
            return f'FAILED: {e}'


def _get_ctx():
    """获取已初始化的 ServerContext 实例。未初始化时返回 None。"""
    if not _inited:
        return None
    try:
        from server.context import ServerContext
        return ServerContext.get_instance(main_window=None)
    except Exception as e:
        _log(f'_get_ctx failed: {e}', 'W')
        return None


# -------------------------------------------------------------------
# 状态与频道查询
# -------------------------------------------------------------------

def get_status_json():
    """返回 standalone 状态 JSON：channels_total / source_loading / source_message"""
    if not _inited:
        return _ok({'inited': False, 'channels_total': 0,
                    'source_loading': False, 'source_message': 'not inited'})
    try:
        ctx = _get_ctx()
        if ctx is None:
            return _err('no context')
        status = ctx.get_source_load_status() or {}
        channels = ctx.get_all_channels() or []
        return _ok({
            'inited': True,
            'channels_total': len(channels),
            'source_loading': bool(status.get('loading', False)),
            'source_message': str(status.get('message', '')),
        })
    except Exception as e:
        return _err(str(e))


def get_channels_json(page=1, size=100, group='', search='', valid_filter=''):
    """频道分页列表。返回 {total, page, size, channels}"""
    try:
        ctx = _get_ctx()
        if ctx is None:
            return _err('not inited')
        all_channels = ctx.get_all_channels() or []
        # 过滤
        filtered = all_channels
        if group:
            filtered = [c for c in filtered if c.get('group', '') == group]
        if search:
            s = search.lower()
            filtered = [c for c in filtered if s in (c.get('name', '') + c.get('url', '')).lower()]
        if valid_filter == 'valid':
            filtered = [c for c in filtered if c.get('valid') is True]
        elif valid_filter == 'invalid':
            filtered = [c for c in filtered if c.get('valid') is False]
        total = len(filtered)
        # 分页
        page = max(1, int(page))
        size = max(1, min(int(size), 5000))
        start = (page - 1) * size
        end = start + size
        page_channels = filtered[start:end]
        # 去掉内部下划线字段（_raw_extinf / _all_tags 等不需要传到 Kotlin）
        clean = []
        for c in page_channels:
            clean.append({k: v for k, v in c.items() if not k.startswith('_')})
        return _ok({
            'total': total,
            'page': page,
            'size': size,
            'channels': clean,
        })
    except Exception as e:
        return _err(str(e))


def get_channel_json(idx):
    """返回单个频道 JSON。idx 是频道索引（基于 get_all_channels 全量列表）"""
    try:
        ctx = _get_ctx()
        if ctx is None:
            return _err('not inited')
        channels = ctx.get_all_channels() or []
        idx = int(idx)
        if idx < 0 or idx >= len(channels):
            return _err('idx out of range')
        c = channels[idx]
        return _ok({k: v for k, v in c.items() if not k.startswith('_')})
    except Exception as e:
        return _err(str(e))


def get_groups_json():
    """返回所有频道分组列表（按 M3U 顺序去重）。[{name, count}]"""
    try:
        ctx = _get_ctx()
        if ctx is None:
            return _err('not inited')
        channels = ctx.get_all_channels() or []
        from collections import OrderedDict
        groups = OrderedDict()
        for c in channels:
            g = c.get('group', '未分类') or '未分类'
            groups[g] = groups.get(g, 0) + 1
        return _ok([{'name': k, 'count': v} for k, v in groups.items()])
    except Exception as e:
        return _err(str(e))


# -------------------------------------------------------------------
# 频道 CRUD（standalone 模式直接操作 _channels）
# -------------------------------------------------------------------

def add_channel(url, name, group=''):
    """添加频道到列表末尾。返回 {idx} 或 {error}"""
    try:
        ctx = _get_ctx()
        if ctx is None:
            return _err('not inited')
        new_ch = {
            'name': str(name), 'url': str(url), 'group': str(group or '未分类'),
            'logo': '', 'tvg_id': '', 'tvg_name': '', 'tvg_chno': '',
            'tvg_shift': '', 'catchup': '', 'catchup_days': '',
            'catchup_source': '', 'catchup_correction': '', 'fcc': '',
            'resolution': '', 'valid': None, 'status': '待检测',
            'id': len(ctx._channels) + 1,
        }
        ctx._channels.append(new_ch)
        return _ok({'idx': len(ctx._channels) - 1})
    except Exception as e:
        return _err(str(e))


def update_channel(idx, json_data):
    """更新频道字段。json_data 是 JSON 字符串，键为字段名。返回 {ok} 或 {error}"""
    try:
        ctx = _get_ctx()
        if ctx is None:
            return _err('not inited')
        idx = int(idx)
        if idx < 0 or idx >= len(ctx._channels):
            return _err('idx out of range')
        data = _json.loads(json_data) if isinstance(json_data, str) else json_data
        ctx._channels[idx].update(data)
        return _ok({'ok': True})
    except Exception as e:
        return _err(str(e))


def delete_channel(idx):
    """删除指定索引的频道。返回 {ok} 或 {error}"""
    try:
        ctx = _get_ctx()
        if ctx is None:
            return _err('not inited')
        idx = int(idx)
        if idx < 0 or idx >= len(ctx._channels):
            return _err('idx out of range')
        ctx._channels.pop(idx)
        return _ok({'ok': True})
    except Exception as e:
        return _err(str(e))


def import_channels(content, name=''):
    """解析 M3U 内容并追加到频道列表。返回 {imported} 或 {error}"""
    try:
        ctx = _get_ctx()
        if ctx is None:
            return _err('not inited')
        from services.m3u_parser import parse_m3u_content
        channels, _ = parse_m3u_content(content)
        if channels:
            # 给新频道 id
            base_id = len(ctx._channels)
            for i, c in enumerate(channels):
                c['id'] = base_id + i + 1
            ctx._channels.extend(channels)
        return _ok({'imported': len(channels)})
    except Exception as e:
        return _err(str(e))


def get_m3u_text(group='', valid_only=False, search=''):
    """生成 M3U 播放列表文本（用于导出/分享）"""
    try:
        ctx = _get_ctx()
        if ctx is None:
            return _err('not inited')
        channels = ctx.get_all_channels() or []
        if group:
            channels = [c for c in channels if c.get('group', '') == group]
        if valid_only:
            channels = [c for c in channels if c.get('valid') is True]
        if search:
            s = search.lower()
            channels = [c for c in channels if s in c.get('name', '').lower()]
        lines = ['#EXTM3U']
        for c in channels:
            attrs = []
            if c.get('tvg_id'):
                attrs.append(f'tvg-id="{c["tvg_id"]}"')
            if c.get('tvg_name'):
                attrs.append(f'tvg-name="{c["tvg_name"]}"')
            if c.get('tvg_logo') or c.get('logo'):
                attrs.append(f'tvg-logo="{c.get("tvg_logo") or c.get("logo", "")}"')
            if c.get('group'):
                attrs.append(f'group-title="{c["group"]}"')
            attr_str = ' '.join(attrs)
            lines.append(f'#EXTINF:-1 {attr_str},{c.get("name", "")}')
            lines.append(c.get('url', ''))
        return _ok({'text': '\n'.join(lines), 'count': len(channels)})
    except Exception as e:
        return _err(str(e))


# -------------------------------------------------------------------
# 订阅源管理
# -------------------------------------------------------------------

def get_sources_json():
    """返回订阅源列表 JSON"""
    try:
        ctx = _get_ctx()
        if ctx is None:
            return _err('not inited')
        config = ctx.get_config()
        if config is None:
            return _err('no config')
        sources = config.load_playlist_sources() or []
        return _ok(sources)
    except Exception as e:
        return _err(str(e))


def export_config():
    """导出所有可备份的配置为 JSON 字符串。

    包含：playlist_sources + epg_sources。
    用于备份/恢复功能：导出后写入外部存储，卸载重装后可恢复。

    返回 {config: {version, playlist_sources, epg_sources}}
    """
    try:
        ctx = _get_ctx()
        if ctx is None:
            return _err('not inited')
        config = ctx.get_config()
        if config is None:
            return _err('no config')
        playlist_sources = config.load_playlist_sources() or []
        epg_sources = config.load_epg_sources() or []
        data = {
            'version': 1,
            'playlist_sources': playlist_sources,
            'epg_sources': epg_sources,
        }
        return _ok(data)
    except Exception as e:
        return _err(str(e))


def import_config(json_data):
    """从 JSON 恢复配置。

    恢复：playlist_sources + epg_sources，并触发 reload。
    用于备份/恢复功能：从外部存储读取 JSON 后恢复配置。

    Args:
        json_data: JSON 字符串或 dict，包含 playlist_sources 和/或 epg_sources
    """
    try:
        ctx = _get_ctx()
        if ctx is None:
            return _err('not inited')
        config = ctx.get_config()
        if config is None:
            return _err('no config')
        data = _json.loads(json_data) if isinstance(json_data, str) else json_data

        # 恢复 playlist_sources
        if 'playlist_sources' in data and isinstance(data['playlist_sources'], list):
            config.save_playlist_sources(data['playlist_sources'])

        # 恢复 epg_sources
        if 'epg_sources' in data and isinstance(data['epg_sources'], list):
            config.save_epg_sources(data['epg_sources'])

        # 触发 reload 以加载频道和 EPG
        try:
            ctx.reload_sources()
            _log('import_config: reload_sources triggered')
        except Exception as e:
            _log(f'import_config: reload_sources failed: {e}', 'W')
        try:
            ctx.reload_epg()
            _log('import_config: reload_epg triggered')
        except Exception as e:
            _log(f'import_config: reload_epg failed: {e}', 'W')

        return _ok({'ok': True})
    except Exception as e:
        return _err(str(e))


def add_source(url, name=''):
    """添加订阅源。返回 {ok}"""
    try:
        ctx = _get_ctx()
        if ctx is None:
            return _err('not inited')
        config = ctx.get_config()
        if config is None:
            return _err('no config')
        sources = config.load_playlist_sources() or []
        sources.append({
            'url': str(url),
            'name': str(name or f'Source {len(sources) + 1}'),
            'enabled': True,
            'last_update': None,
        })
        config.save_playlist_sources(sources)
        return _ok({'ok': True, 'count': len(sources)})
    except Exception as e:
        return _err(str(e))


def delete_source(idx):
    """删除订阅源。返回 {ok}"""
    try:
        ctx = _get_ctx()
        if ctx is None:
            return _err('not inited')
        config = ctx.get_config()
        if config is None:
            return _err('no config')
        sources = config.load_playlist_sources() or []
        idx = int(idx)
        if idx < 0 or idx >= len(sources):
            return _err('idx out of range')
        sources.pop(idx)
        config.save_playlist_sources(sources)
        return _ok({'ok': True, 'count': len(sources)})
    except Exception as e:
        return _err(str(e))


def update_source(idx, json_data):
    """更新订阅源字段（如 enabled / name / url）。"""
    try:
        ctx = _get_ctx()
        if ctx is None:
            return _err('not inited')
        config = ctx.get_config()
        if config is None:
            return _err('no config')
        sources = config.load_playlist_sources() or []
        idx = int(idx)
        if idx < 0 or idx >= len(sources):
            return _err('idx out of range')
        data = _json.loads(json_data) if isinstance(json_data, str) else json_data
        sources[idx].update(data)
        config.save_playlist_sources(sources)
        return _ok({'ok': True})
    except Exception as e:
        return _err(str(e))


def reload_sources(url=''):
    """触发订阅源重载（异步，立即返回 True/False）。url 空则加载所有已配置源。"""
    try:
        ctx = _get_ctx()
        if ctx is None:
            return _err('not inited')
        result = ctx.reload_sources(url)
        return _ok({'started': bool(result)})
    except Exception as e:
        return _err(str(e))


def get_source_status_json():
    """返回订阅源加载状态 JSON"""
    try:
        ctx = _get_ctx()
        if ctx is None:
            return _err('not inited')
        status = ctx.get_source_load_status() or {}
        return _ok(status)
    except Exception as e:
        return _err(str(e))


# -------------------------------------------------------------------
# EPG 订阅源管理
# -------------------------------------------------------------------

def get_epg_sources_json():
    """返回 EPG 订阅源列表 JSON"""
    try:
        ctx = _get_ctx()
        if ctx is None:
            return _err('not inited')
        config = ctx.get_config()
        if config is None:
            return _err('no config')
        sources = config.load_epg_sources() or []
        return _ok(sources)
    except Exception as e:
        return _err(str(e))


def add_epg_source(url, name=''):
    """添加 EPG 订阅源并触发重载。返回 {ok}"""
    try:
        ctx = _get_ctx()
        if ctx is None:
            return _err('not inited')
        config = ctx.get_config()
        if config is None:
            return _err('no config')
        sources = config.load_epg_sources() or []
        sources.append({
            'url': str(url),
            'name': str(name or f'EPG Source {len(sources) + 1}'),
            'last_update': None,
        })
        config.save_epg_sources(sources)
        # 异步重载 EPG（不阻塞）
        try:
            ctx.reload_epg()
        except Exception as e:
            _log(f'add_epg_source: reload_epg failed: {e}', 'W')
        return _ok({'ok': True, 'count': len(sources)})
    except Exception as e:
        return _err(str(e))


def delete_epg_source(idx):
    """删除 EPG 订阅源。返回 {ok}"""
    try:
        ctx = _get_ctx()
        if ctx is None:
            return _err('not inited')
        config = ctx.get_config()
        if config is None:
            return _err('no config')
        sources = config.load_epg_sources() or []
        idx = int(idx)
        if idx < 0 or idx >= len(sources):
            return _err('idx out of range')
        sources.pop(idx)
        config.save_epg_sources(sources)
        return _ok({'ok': True, 'count': len(sources)})
    except Exception as e:
        return _err(str(e))


def reload_epg():
    """异步重新加载 EPG 数据。返回 {started}"""
    try:
        ctx = _get_ctx()
        if ctx is None:
            return _err('not inited')
        result = ctx.reload_epg()
        return _ok({'started': bool(result)})
    except Exception as e:
        return _err(str(e))


def get_epg_status_json():
    """返回 EPG 加载状态 JSON（has_epg_data / channel_count / program_count）"""
    try:
        ctx = _get_ctx()
        if ctx is None:
            return _err('not inited')
        sm = ctx.get_epg_parser()
        if sm is None:
            return _ok({'has_epg_data': False, 'channel_count': 0, 'program_count': 0})
        return _ok({
            'has_epg_data': bool(sm.has_epg_data()),
            'channel_count': int(sm.get_epg_channel_count()),
            'program_count': int(sm.get_epg_program_count()),
        })
    except Exception as e:
        return _err(str(e))


# -------------------------------------------------------------------
# EPG 节目单
# -------------------------------------------------------------------

def get_epg_json(channel_name='', tvg_id='', tvg_name='', comma_name=''):
    """获取指定频道的节目单 JSON。
    匹配优先级：tvg_name > tvg_id > comma_name > channel_name > EpgMatcher 模糊匹配。
    返回 {programmes: [{title, desc, start, end}]} 或 {error}
    """
    try:
        ctx = _get_ctx()
        if ctx is None:
            return _err('not inited')
        sm = ctx.get_epg_parser()
        if sm is None:
            return _ok({'programmes': [], 'matched': False})
        programmes = sm.get_channel_epg(
            channel_name=channel_name,
            tvg_id=tvg_id or None,
            tvg_name=tvg_name or None,
            comma_name=comma_name or None,
        )
        return _ok({
            'programmes': programmes or [],
            'matched': bool(programmes),
        })
    except Exception as e:
        return _err(str(e))


def get_epg_channels_json():
    """返回所有有 EPG 数据的频道 ID 列表（用于搜索界面）。"""
    try:
        ctx = _get_ctx()
        if ctx is None:
            return _err('not inited')
        sm = ctx.get_epg_parser()
        if sm is None:
            return _ok({'channels': []})
        data = sm.get_epg_data_copy() or {}
        return _ok({'channels': list(data.keys())})
    except Exception as e:
        return _err(str(e))


# -------------------------------------------------------------------
# 扫描（URL 范围扫描）
# -------------------------------------------------------------------

def start_scan(base_url, timeout=10, threads=4):
    """启动 URL 范围扫描（异步）。base_url 支持 [1-255] 范围表达式。
    命名变量同步：[1-255:n] 定义变量 n，{n} 引用（两处 n 同步变化）。
    返回 {started} 或 {error}
    """
    try:
        ctx = _get_ctx()
        if ctx is None:
            return _err('not inited')
        scanner = ctx.get_standalone_scanner()
        if scanner is None:
            return _err('no scanner')
        result = scanner.start_range_scan(
            base_url=str(base_url),
            timeout=int(timeout),
            threads=int(threads),
        )
        return _ok({'started': bool(result)})
    except Exception as e:
        return _err(str(e))


def stop_scan():
    """请求停止扫描（异步）。返回 {ok}"""
    try:
        ctx = _get_ctx()
        if ctx is None:
            return _err('not inited')
        scanner = ctx.get_standalone_scanner()
        if scanner is None:
            return _err('no scanner')
        scanner.stop_scan()
        return _ok({'ok': True})
    except Exception as e:
        return _err(str(e))


def get_scan_status_json():
    """返回扫描状态 JSON：running / total / valid / invalid / scanned / message / mode"""
    try:
        ctx = _get_ctx()
        if ctx is None:
            return _err('not inited')
        scanner = ctx.get_standalone_scanner()
        if scanner is None:
            return _err('no scanner')
        status = scanner.get_status() or {}
        return _ok(status)
    except Exception as e:
        return _err(str(e))


def get_scan_results_json():
    """返回 URL 范围扫描结果列表 JSON。"""
    try:
        ctx = _get_ctx()
        if ctx is None:
            return _err('not inited')
        scanner = ctx.get_standalone_scanner()
        if scanner is None:
            return _err('no scanner')
        results = scanner.get_results() or []
        return _ok(results)
    except Exception as e:
        return _err(str(e))


# -------------------------------------------------------------------
# 频道映射
# -------------------------------------------------------------------

def get_mappings_json():
    """返回所有频道映射条目 JSON。"""
    try:
        ctx = _get_ctx()
        if ctx is None:
            return _err('not inited')
        from models.channel_mappings import mapping_manager
        entries = mapping_manager.get_mapping_entries() or []
        return _ok(entries)
    except Exception as e:
        return _err(str(e))


def add_mapping(raw_name, standard_name, logo_url='', group_name=''):
    """添加用户映射。返回 {ok}"""
    try:
        ctx = _get_ctx()
        if ctx is None:
            return _err('not inited')
        from models.channel_mappings import mapping_manager
        mapping_manager.add_user_mapping(
            raw_name=str(raw_name),
            standard_name=str(standard_name),
            logo_url=str(logo_url) or None,
            group_name=str(group_name) or None,
        )
        return _ok({'ok': True})
    except Exception as e:
        return _err(str(e))


def delete_mapping(standard_name, raw_name=''):
    """删除映射。
    - 只传 standard_name：删除该 standard_name 下所有 raw_name
    - 同时传 standard_name 和 raw_name：删除单条
    """
    try:
        ctx = _get_ctx()
        if ctx is None:
            return _err('not inited')
        from models.channel_mappings import mapping_manager
        if raw_name:
            mapping_manager.remove_user_mapping_entry(
                standard_name=str(standard_name),
                raw_name=str(raw_name),
            )
        else:
            mapping_manager.remove_user_mapping(standard_name=str(standard_name))
        return _ok({'ok': True})
    except Exception as e:
        return _err(str(e))


def refresh_mappings():
    """刷新远程映射缓存（同步阻塞，Kotlin 端必须在 IO 调用）。返回 {ok}"""
    try:
        ctx = _get_ctx()
        if ctx is None:
            return _err('not inited')
        from models.channel_mappings import mapping_manager
        mapping_manager.refresh_cache()
        return _ok({'ok': True})
    except Exception as e:
        return _err(str(e))


# -------------------------------------------------------------------
# 字幕
# -------------------------------------------------------------------

def search_subtitles(query='', imdb_id='', language='all', file_path=''):
    """字幕搜索。返回 {subtitles: [...], last_error: str}"""
    try:
        ctx = _get_ctx()
        if ctx is None:
            return _err('not inited')
        from services.subtitle_download_service import SubtitleDownloadService
        svc = SubtitleDownloadService()
        results = svc.search(
            query=str(query),
            imdb_id=str(imdb_id),
            language=str(language or 'all'),
            file_path=str(file_path),
        )
        return _ok({
            'subtitles': results or [],
            'last_error': getattr(svc, 'last_error', '') or '',
        })
    except Exception as e:
        return _err(str(e))


def download_subtitle(download_link, dest_dir, file_name='', language=''):
    """下载字幕到指定目录。返回 {path} 或 {error}"""
    try:
        ctx = _get_ctx()
        if ctx is None:
            return _err('not inited')
        from services.subtitle_download_service import SubtitleDownloadService
        svc = SubtitleDownloadService()
        result_path = svc.download(
            download_link=str(download_link),
            dest_dir=str(dest_dir),
            file_name=str(file_name),
            language=str(language),
        )
        if result_path:
            return _ok({'path': result_path})
        return _err(getattr(svc, 'last_error', '下载失败') or '下载失败')
    except Exception as e:
        return _err(str(e))


# -------------------------------------------------------------------
# 缓存清理
# -------------------------------------------------------------------

def clear_cache(cache_type='all'):
    """清空指定类型缓存。
    cache_type: 'all' / 'logo' / 'epg' / 'thumbnails' / 'subtitle'
    返回 {ok, deleted_count}
    """
    try:
        ctx = _get_ctx()
        if ctx is None:
            return _err('not inited')
        import os
        import shutil
        data_dir = os.environ.get('IPTV_DATA_DIR', os.path.expanduser('~'))
        app_dir = os.path.join(data_dir, 'IPTV_Scanner_Editor_Pro')
        deleted = 0

        cache_dirs = {
            'logo': ['logo_cache', 'logos'],
            'epg': ['epg_cache'],
            'thumbnails': ['thumbnails', 'thumb_cache'],
            'subtitle': ['subtitles', 'subtitle_cache'],
        }
        if cache_type == 'all':
            target_dirs = []
            for dirs in cache_dirs.values():
                target_dirs.extend(dirs)
        else:
            target_dirs = cache_dirs.get(cache_type, [])

        for d in target_dirs:
            full = os.path.join(app_dir, d)
            if os.path.isdir(full):
                try:
                    shutil.rmtree(full)
                    deleted += 1
                except Exception:
                    pass
        return _ok({'ok': True, 'deleted_count': deleted})
    except Exception as e:
        return _err(str(e))


# -------------------------------------------------------------------
# 阶段 0 spike 兼容入口（保持 ComposeSpikeActivity 不破坏）
# 真正的入口已改名为 init_context / get_status_json / get_channels_json
# -------------------------------------------------------------------

def spike_init():
    """spike 兼容包装，转调 init_context()"""
    return init_context()


def spike_get_status_json():
    """spike 兼容包装，转调 get_status_json()"""
    return get_status_json()


def spike_get_channels_json(limit=10):
    """spike 兼容包装，转调 get_channels_json(1, limit)"""
    return get_channels_json(1, int(limit))


# -----------------------------------------------------------------
# 局域网管理服务器（TV 端遥控器输入不便，手机浏览器扫码管理）
# -----------------------------------------------------------------

_admin_server_thread = None
_admin_server_url = ''
_admin_server_port = 0
_admin_server_running = False
_admin_server_error = ''
_admin_loop = None
# 保存 _run() 协程的 task 引用，用于优雅取消（task.cancel() 触发 CancelledError，
# 让 _run() 的 finally 块执行 runner.cleanup() 释放 socket；
# 而 loop.stop() 会跳过 finally 导致 socket 泄漏 → 下次 bind 失败）
_admin_server_task = None


def start_admin_server(port=8080):
    """在后台线程启动 HTTP 管理服务器，返回局域网 URL。

    复用 create_app() + _register_mobile_routes()，暴露 /api/ 和 /mobile/ 路由。
    其他设备通过浏览器访问 http://<设备IP>:<port>/mobile/ 即可管理。
    """
    global _admin_server_thread, _admin_server_url, _admin_server_port
    global _admin_server_running, _admin_loop, _admin_server_error, _admin_server_task

    if _admin_server_running:
        return _ok({'url': _admin_server_url, 'port': _admin_server_port, 'already_running': True})

    # 如果旧 server 线程还在运行（_admin_server_running=False 但线程活着），
    # 说明上一次启动的 import 还在进行中（Chaquopy 首次 import 慢）。
    # 不要停止它，直接返回"正在启动中"，让 Kotlin 端继续轮询。
    # 这样避免用户重复点击导致重启 import（浪费之前的进度）。
    if _admin_server_thread is not None and _admin_server_thread.is_alive():
        _log('Admin server thread still running (importing), returning starting status')
        return _ok({'url': _admin_server_url, 'port': _admin_server_port, 'running': False})

    # 如果旧线程已结束但有错误（_admin_server_error 非空），需要先清理
    # （旧线程已死，不需要 cancel/join，直接重置状态）
    if _admin_server_thread is not None and not _admin_server_thread.is_alive():
        _log(f'Previous admin server thread ended with error: {_admin_server_error}')
        _admin_server_running = False
        _admin_loop = None
        _admin_server_task = None
        _admin_server_error = ''

    # 重置错误状态
    _admin_server_error = ''

    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        local_ip = s.getsockname()[0]
        s.close()
        _admin_server_url = f'http://{local_ip}:{port}'
        _admin_server_port = port
    except Exception as e:
        return _err(f'获取局域网 IP 失败: {e}')

    def _run_server():
        global _admin_server_running, _admin_loop, _admin_server_error, _admin_server_task
        try:
            import asyncio
            import time
            from server.routes import create_app
            from server.app import get_server
            from aiohttp import web

            app = create_app()
            mobile_dir = _find_mobile_dir()
            if mobile_dir:
                _register_mobile_routes(app, mobile_dir)
                _log(f'Admin server mobile routes from: {mobile_dir}')
            else:
                _log('Admin server: mobile dir not found', 'W')

            # 注册虚拟遥控器路由
            async def _handle_remote(request):
                cmd = request.match_info.get('cmd', '')
                if not cmd:
                    return web.json_response({'success': False, 'error': 'missing cmd'})
                push_remote_command(cmd)
                return web.json_response({'success': True, 'cmd': cmd})

            app.router.add_post('/api/remote/{cmd}', _handle_remote)
            _log('Admin server remote control routes registered')

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            _admin_loop = loop

            async def _run():
                global _admin_server_running, _admin_server_url, _admin_server_port
                runner = web.AppRunner(app)
                await runner.setup()
                # 端口自动选择：从 port 开始尝试，被占用则递增，最多尝试 10 个端口
                # 不会强行停止占用端口的其他服务，而是自动寻找可用端口
                actual_port = port
                site = None
                for attempt in range(10):
                    try_port = port + attempt
                    try:
                        site = web.TCPSite(runner, '0.0.0.0', try_port)
                        await site.start()
                        actual_port = try_port
                        break
                    except OSError as e:
                        if 'address already in use' in str(e).lower():
                            _log(f'Port {try_port} in use, trying {try_port + 1}...')
                            continue
                        raise
                if site is None:
                    raise OSError(f'No available port in range {port}-{port + 9}')
                # 更新实际使用的端口和 URL（端口可能因冲突而递增）
                if actual_port != _admin_server_port:
                    _admin_server_port = actual_port
                    # 从现有 URL 提取 host，重新构造
                    import re as _re
                    _admin_server_url = _re.sub(r':\d+$', f':{actual_port}', _admin_server_url)
                _admin_server_running = True
                # 同步标记 IPTVServer 为运行中，使 /api/status 返回 running（管理页面状态显示正确）
                svr = get_server()
                svr._running = True
                svr._start_time = time.time()
                _log(f'Admin server running at {_admin_server_url} (port={actual_port})')
                try:
                    while True:
                        await asyncio.sleep(3600)
                except asyncio.CancelledError:
                    _log('Admin server task cancelled, cleaning up...')
                    pass
                finally:
                    # 关键：runner.cleanup() 释放 server socket，避免端口泄漏
                    await runner.cleanup()
                    _log('Admin server runner.cleanup() done')
                    _admin_server_running = False
                    # 同步标记 IPTVServer 为已停止
                    svr = get_server()
                    svr._running = False

            # 用 task 模式：保存 task 引用，外部用 task.cancel() 优雅取消
            # task.cancel() 触发 CancelledError → _run() 的 except 捕获 → finally 执行 runner.cleanup()
            # （对比：loop.stop() 会让 run_until_complete 抛 RuntimeError，跳过 finally，socket 泄漏）
            _admin_server_task = loop.create_task(_run())
            loop.run_until_complete(_admin_server_task)
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            # 包含 traceback 在错误信息中，方便 Kotlin 端排查（OSD 会显示，logcat 也会捕获）
            _admin_server_error = f'{e}\n{tb}'
            _log(f'Admin server failed: {e}\n{tb}', 'E')
            _admin_server_running = False
        finally:
            _admin_server_task = None

    _admin_server_thread = _threading.Thread(target=_run_server, daemon=True)
    _admin_server_thread.start()

    # 立即返回，不等待 server 启动完成。
    # 原因：Chaquopy 的 callAttr 在 Python 函数执行期间会持有 GIL，
    # 导致 _run_server 子线程的 import 被阻塞，主线程的等待循环检测不到 _admin_server_running=True。
    # Kotlin 端通过 get_admin_url() 轮询 running 状态来检测后台启动是否完成。
    # 短暂等待 1 秒，让 _run_server 线程有机会启动并报告早期错误（如端口被占用）。
    import time as _time
    _time.sleep(1)
    if _admin_server_error:
        return _err(f'服务器启动失败: {_admin_server_error}')
    # 返回 running=False 表示"正在后台启动中"，Kotlin 端会启动轮询
    return _ok({'url': _admin_server_url, 'port': _admin_server_port, 'running': _admin_server_running})


def stop_admin_server():
    """停止 HTTP 管理服务器。"""
    global _admin_server_running, _admin_loop, _admin_server_error, _admin_server_thread, _admin_server_task
    was_running = _admin_server_running
    _admin_server_running = False
    _admin_server_error = ''
    # 用 task.cancel() 代替 loop.stop()：
    # - loop.stop() 让 run_until_complete 抛 RuntimeError，跳过 _run() 的 finally 块 → runner.cleanup() 不执行 → socket 泄漏
    # - task.cancel() 触发 CancelledError → _run() 的 except 捕获 → finally 执行 runner.cleanup() → socket 正确释放
    if _admin_server_task is not None and _admin_loop is not None:
        try:
            _admin_loop.call_soon_threadsafe(_admin_server_task.cancel)
        except Exception:
            pass
    # 等待 server 线程结束，确保 socket 释放（避免下次启动时 address already in use）
    if _admin_server_thread is not None and _admin_server_thread.is_alive():
        _admin_server_thread.join(timeout=5)
    _admin_loop = None
    _admin_server_task = None
    _log('Admin server stopped')
    return _ok({'ok': True, 'was_running': was_running})


def get_admin_url():
    """返回管理服务器 URL 和运行状态。

    注意：只在有错误时包含 error 字段，避免 Kotlin 端 callPyTyped 误判空字符串为错误。
    """
    result = {
        'url': _admin_server_url,
        'running': _admin_server_running,
        'port': _admin_server_port,
    }
    if _admin_server_error:
        result['error'] = _admin_server_error
    return _ok(result)


# -------------------------------------------------------------------
# 虚拟遥控器：从 admin 页面发送遥控命令到 Android 端
#
# 机制：
# 1. admin 页面发送 HTTP POST /api/remote/{cmd}
# 2. Python 端将命令放入 _remote_command_queue
# 3. Kotlin 端每 100ms 轮询 poll_remote_command()，获取命令后执行
#
# 支持的命令：
# up/down/left/right/ok/back/menu/play/pause/play_pause/stop
# mute/vol_up/vol_down/seek_forward/seek_backward/osd
# prev_channel/next_channel
# -------------------------------------------------------------------

import queue as _queue
_remote_command_queue = _queue.Queue()


def push_remote_command(cmd):
    """将遥控命令放入队列（供 HTTP 路由调用）"""
    try:
        _remote_command_queue.put_nowait(cmd)
        return _ok({'cmd': cmd})
    except Exception as e:
        return _err(f'push command failed: {e}')


def poll_remote_command():
    """轮询遥控命令（供 Kotlin 端调用）。返回命令字符串或 None。"""
    try:
        cmd = _remote_command_queue.get_nowait()
        return _ok({'cmd': cmd})
    except _queue.Empty:
        return _ok({'cmd': None})
