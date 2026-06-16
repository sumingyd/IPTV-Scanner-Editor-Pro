import asyncio
import json
import logging
import threading
import time
from typing import Optional

from aiohttp import web

logger = logging.getLogger('server')

_main_window_ref = None


def set_main_window(main_window):
    global _main_window_ref
    _main_window_ref = main_window
    from server.context import ServerContext
    ServerContext.get_instance(main_window)


def get_main_window():
    return _main_window_ref


def get_context():
    from server.context import ServerContext
    return ServerContext.get_instance(_main_window_ref)


def get_channel_model():
    ctx = get_context()
    return ctx.get_channel_model() if ctx else None


def get_config():
    ctx = get_context()
    return ctx.get_config() if ctx else None


def get_language_manager():
    mw = get_main_window()
    if mw and hasattr(mw, 'language_manager'):
        return mw.language_manager
    return None


class IPTVServer:
    def __init__(self, host='0.0.0.0', port=8080):
        self.host = host
        self.port = port
        self.app: Optional[web.Application] = None
        self.runner: Optional[web.AppRunner] = None
        self.site: Optional[web.TCPSite] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._start_time = 0.0

    def start(self):
        if self._running:
            logger.warning("Server已在运行中")
            return
        self._thread = threading.Thread(target=self._run_loop, name="IPTVServer", daemon=True)
        self._thread.start()
        self._running = True
        self._start_time = time.time()
        logger.info(f"IPTV Server 启动于 http://{self.host}:{self.port}")

    def stop(self):
        if not self._running:
            return
        self._running = False
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self._async_stop(), self._loop)
        if self._thread:
            self._thread.join(timeout=5)
        self._thread = None
        logger.info("IPTV Server 已停止")

    def is_running(self):
        return self._running

    def get_uptime(self):
        if self._start_time > 0:
            return int(time.time() - self._start_time)
        return 0

    def _run_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._async_start())
            self._loop.run_forever()
        except Exception as e:
            logger.error(f"Server运行异常: {e}")
        finally:
            try:
                self._loop.close()
            except Exception:
                pass

    async def _async_start(self):
        from server.routes import create_app
        self.app = create_app()
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, self.host, self.port)
        await self.site.start()

    async def _async_stop(self):
        try:
            if self.site:
                await self.site.stop()
            if self.runner:
                await self.runner.cleanup()
        except Exception as e:
            logger.error(f"Server停止异常: {e}")


_server_instance: Optional[IPTVServer] = None


def get_server() -> IPTVServer:
    global _server_instance
    if _server_instance is None:
        _server_instance = IPTVServer()
    return _server_instance


def start_server(host='0.0.0.0', port=8080):
    global _server_instance
    if _server_instance and _server_instance.is_running():
        return _server_instance
    _server_instance = IPTVServer(host=host, port=port)
    _server_instance.start()
    return _server_instance


def stop_server():
    global _server_instance
    if _server_instance:
        _server_instance.stop()