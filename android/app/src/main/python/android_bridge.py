import logging
import os
import sys


def _setup_android_paths():
    if not getattr(sys, 'platform', '') == 'android':
        return
    try:
        from chaquopy.python import Python
        app = Python.getPlatform().getApplication()
        files_dir = app.getFilesDir().getAbsolutePath()
        os.environ.setdefault('IPTV_DATA_DIR', files_dir)
        sys.path.insert(0, files_dir)
    except Exception:
        pass


def _setup_android_logging():
    try:
        from android.util import Log
        class AndroidLogHandler(logging.Handler):
            def emit(self, record):
                msg = self.format(record)
                level = record.levelno
                if level >= logging.ERROR:
                    Log.e(record.name, msg)
                elif level >= logging.WARNING:
                    Log.w(record.name, msg)
                elif level >= logging.INFO:
                    Log.i(record.name, msg)
                elif level >= logging.DEBUG:
                    Log.d(record.name, msg)
                else:
                    Log.v(record.name, msg)
        root = logging.getLogger()
        if not any(isinstance(h, AndroidLogHandler) for h in root.handlers):
            root.addHandler(AndroidLogHandler())
    except Exception:
        pass


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

    _setup_android_paths()
    _setup_android_logging()

    logger = logging.getLogger('android_bridge')
    logger.info('Starting IPTV server on Android...')

    import asyncio
    from server.context import ServerContext
    from server.routes import create_app
    from aiohttp import web

    data_dir = os.environ.get('IPTV_DATA_DIR', os.path.expanduser('~'))
    config_dir = os.path.join(data_dir, 'IPTV_Scanner_Editor_Pro')
    os.makedirs(config_dir, exist_ok=True)

    os.chdir(config_dir)

    ServerContext.get_instance(main_window=None)

    app = create_app()
    mobile_dir = _find_mobile_dir()
    if mobile_dir:
        _register_mobile_routes(app, mobile_dir)
        logger.info(f'Mobile UI served from: {mobile_dir}')
    else:
        logger.warning('Mobile UI directory not found, /mobile/ will not be available')

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def _run():
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, host, port)
        await site.start()
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
