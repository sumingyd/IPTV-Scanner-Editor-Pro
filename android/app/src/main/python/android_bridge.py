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
    if not getattr(sys, 'platform', '') == 'android':
        return
    try:
        Python = importlib.import_module('chaquopy.python').Python
        app = Python.getPlatform().getApplication()
        files_dir = app.getFilesDir().getAbsolutePath()
        os.environ.setdefault('IPTV_DATA_DIR', files_dir)
        sys.path.insert(0, files_dir)
    except Exception as e:
        _log(f'_setup_android_paths failed: {e}', 'W')


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


def start_server(host='127.0.0.1', port=8080):
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
    admin_dir = os.path.join(os.path.dirname(base_dir), 'admin')
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
            return web.Response(body=content, content_type=content_type, headers={'Cache-Control':'no-cache, no-store, must-revalidate','Pragma':'no-cache','Expires':'0'})

        app.router.add_get('/admin/', _handle_admin)
        app.router.add_get('/admin/{path:.*}', _handle_admin)
