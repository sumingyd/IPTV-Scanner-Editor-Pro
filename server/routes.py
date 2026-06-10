import asyncio
import json
import logging
import time
from aiohttp import web, web_response

from server.app import get_channel_model, get_config, get_main_window, get_server

logger = logging.getLogger('server.routes')


def create_app() -> web.Application:
    app = web.Application(middlewares=[error_middleware, cors_middleware])
    app.router.add_get('/api/status', handle_status)
    app.router.add_get('/api/m3u', handle_m3u)
    app.router.add_get('/api/m3u/{group}', handle_m3u)
    app.router.add_get('/api/channels', handle_channels_list)
    app.router.add_get('/api/channels/{id}', handle_channel_get)
    app.router.add_put('/api/channels/{id}', handle_channel_update)
    app.router.add_delete('/api/channels/{id}', handle_channel_delete)
    app.router.add_post('/api/channels', handle_channel_add)
    app.router.add_get('/api/sources', handle_sources_list)
    app.router.add_post('/api/sources', handle_sources_add)
    app.router.add_delete('/api/sources/{id}', handle_sources_delete)
    app.router.add_post('/api/scan/start', handle_scan_start)
    app.router.add_post('/api/scan/stop', handle_scan_stop)
    app.router.add_get('/api/scan/status', handle_scan_status)
    app.router.add_get('/api/epg', handle_epg)
    app.router.add_get('/stream/{id}', handle_stream_proxy)
    return app


@web.middleware
async def cors_middleware(request, handler):
    if request.method == 'OPTIONS':
        resp = web.Response(status=204)
    else:
        resp = await handler(request)
    resp.headers['Access-Control-Allow-Origin'] = '*'
    resp.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    resp.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    return resp


@web.middleware
async def error_middleware(request, handler):
    try:
        return await handler(request)
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"API错误: {e}")
        return web.json_response({'error': str(e)}, status=500)


def _json_success(data=None, **kwargs):
    result = {'success': True}
    if data is not None:
        result['data'] = data
    result.update(kwargs)
    return web.json_response(result)


def _json_error(message, status=400):
    return web.json_response({'success': False, 'error': message}, status=status)


async def handle_status(request):
    server = get_server()
    model = get_channel_model()
    total = model.rowCount() if model else 0
    valid = 0
    if model:
        for i in range(total):
            ch = model.get_channel(i)
            if ch and ch.get('valid') is True:
                valid += 1
    config = get_config()
    port = 8080
    if config:
        try:
            settings = config.load_server_settings()
            port = settings.get('port', 8080)
        except Exception:
            pass
    return _json_success(
        server='running' if server.is_running() else 'stopped',
        host=server.host if server else '0.0.0.0',
        port=server.port if server else port,
        uptime=server.get_uptime() if server else 0,
        channels={'total': total, 'valid': valid, 'invalid': total - valid}
    )


async def handle_m3u(request):
    model = get_channel_model()
    if not model:
        return _json_error('频道模型未初始化', 503)
    group_filter = request.match_info.get('group', None)
    valid_only = request.rel_url.query.get('valid', '0') == '1'
    search = request.rel_url.query.get('search', '').strip().lower()
    lines = ['#EXTM3U']
    total = model.rowCount()
    for i in range(total):
        ch = model.get_channel(i)
        if not ch:
            continue
        if valid_only and ch.get('valid') is not True:
            continue
        group = ch.get('group', '')
        if group_filter and group != group_filter:
            continue
        name = ch.get('name', '')
        if search and search not in name.lower() and search not in group.lower():
            continue
        url = ch.get('url', '')
        if not url:
            continue
        tvg_id = ch.get('tvg_id', '')
        tvg_chno = ch.get('tvg_chno', '')
        logo = ch.get('logo', '')
        attrs = []
        if tvg_id:
            attrs.append(f'tvg-id="{tvg_id}"')
        if tvg_chno:
            attrs.append(f'tvg-chno="{tvg_chno}"')
        if logo:
            attrs.append(f'tvg-logo="{logo}"')
        attrs.append(f'group-title="{group}"')
        attr_str = ' '.join(attrs)
        lines.append(f'#EXTINF:-1 {attr_str},{name}')
        lines.append(url)
    content = '\n'.join(lines) + '\n'
    return web.Response(
        text=content,
        content_type='audio/mpegurl',
        charset='utf-8',
        headers={'Content-Disposition': 'attachment; filename="iptv.m3u"'}
    )


async def handle_channels_list(request):
    model = get_channel_model()
    if not model:
        return _json_error('频道模型未初始化', 503)
    valid_only = request.rel_url.query.get('valid', '').strip()
    group = request.rel_url.query.get('group', '').strip()
    search = request.rel_url.query.get('search', '').strip().lower()
    page = max(1, int(request.rel_url.query.get('page', '1')))
    page_size = min(500, max(1, int(request.rel_url.query.get('size', '100'))))
    channels = []
    total = model.rowCount()
    for i in range(total):
        ch = model.get_channel(i)
        if not ch:
            continue
        if valid_only == '1' and ch.get('valid') is not True:
            continue
        if valid_only == '0' and ch.get('valid') is False:
            continue
        if group and ch.get('group', '') != group:
            continue
        if search and search not in ch.get('name', '').lower() and search not in ch.get('group', '').lower():
            continue
        channels.append({**ch, '_index': i})
    total_filtered = len(channels)
    start = (page - 1) * page_size
    end = start + page_size
    page_items = channels[start:end]
    groups = sorted(set(ch.get('group', '') for ch in [model.get_channel(i) for i in range(total)] if ch))
    return _json_success(
        channels=page_items,
        total=total_filtered,
        page=page,
        page_size=page_size,
        groups=groups
    )


async def handle_channel_get(request):
    model = get_channel_model()
    if not model:
        return _json_error('频道模型未初始化', 503)
    try:
        idx = int(request.match_info['id'])
    except ValueError:
        return _json_error('无效的频道ID')
    if not (0 <= idx < model.rowCount()):
        return _json_error('频道不存在', 404)
    ch = model.get_channel(idx)
    return _json_success(channel={**ch, '_index': idx} if ch else None)


async def handle_channel_update(request):
    model = get_channel_model()
    if not model:
        return _json_error('频道模型未初始化', 503)
    try:
        idx = int(request.match_info['id'])
    except ValueError:
        return _json_error('无效的频道ID')
    if not (0 <= idx < model.rowCount()):
        return _json_error('频道不存在', 404)
    data = await request.json()
    model.update_channel(idx, data)
    return _json_success()


async def handle_channel_delete(request):
    model = get_channel_model()
    if not model:
        return _json_error('频道模型未初始化', 503)
    try:
        idx = int(request.match_info['id'])
    except ValueError:
        return _json_error('无效的频道ID')
    if not (0 <= idx < model.rowCount()):
        return _json_error('频道不存在', 404)
    model.remove_channel(idx)
    return _json_success()


async def handle_channel_add(request):
    model = get_channel_model()
    if not model:
        return _json_error('频道模型未初始化', 503)
    data = await request.json()
    if not data.get('url'):
        return _json_error('URL不能为空')
    data.setdefault('name', data['url'].split('/')[-1])
    data.setdefault('group', '未分类')
    data.setdefault('valid', None)
    data.setdefault('status', '')
    model.add_channel(data)
    return _json_success()


async def handle_sources_list(request):
    config = get_config()
    if not config:
        return _json_error('配置未初始化', 503)
    try:
        sources = config.load_playlist_sources()
    except Exception:
        sources = []
    return _json_success(sources=sources)


async def handle_sources_add(request):
    config = get_config()
    if not config:
        return _json_error('配置未初始化', 503)
    data = await request.json()
    url = data.get('url', '').strip()
    name = data.get('name', '').strip()
    if not url:
        return _json_error('URL不能为空')
    try:
        sources = config.load_playlist_sources()
    except Exception:
        sources = []
    sources.append({'url': url, 'name': name or url, 'enabled': True, 'last_update': None})
    config.save_playlist_sources(sources)
    return _json_success()


async def handle_sources_delete(request):
    config = get_config()
    if not config:
        return _json_error('配置未初始化', 503)
    try:
        idx = int(request.match_info['id'])
    except ValueError:
        return _json_error('无效的源ID')
    try:
        sources = config.load_playlist_sources()
    except Exception:
        sources = []
    if not (0 <= idx < len(sources)):
        return _json_error('源不存在', 404)
    sources.pop(idx)
    config.save_playlist_sources(sources)
    return _json_success()


async def handle_scan_start(request):
    mw = get_main_window()
    if not mw:
        return _json_error('主窗口未初始化', 503)
    scan_dialog = getattr(mw, '_scan_dialog', None)
    if not scan_dialog:
        return _json_error('扫描窗口未打开，请先打开扫描整理窗口', 400)
    if hasattr(scan_dialog, 'scanner') and scan_dialog.scanner and scan_dialog.scanner.is_scanning():
        return _json_error('扫描已在进行中', 409)
    data = {}
    try:
        data = await request.json()
    except Exception:
        pass
    url = data.get('url', '').strip()
    if not url:
        return _json_error('需要提供扫描URL')
    from PySide6.QtCore import QMetaObject, Qt
    from utils.thread_safety import invoke_on_thread
    def _trigger():
        try:
            scan_dialog.ip_range_input.setEditText(url)
            if hasattr(scan_dialog, '_on_scan_clicked'):
                scan_dialog._on_scan_clicked()
        except Exception as e:
            logger.error(f"触发扫描失败: {e}")
    invoke_on_thread(mw, _trigger)
    return _json_success(message='扫描已触发')


async def handle_scan_stop(request):
    mw = get_main_window()
    if not mw:
        return _json_error('主窗口未初始化', 503)
    scan_dialog = getattr(mw, '_scan_dialog', None)
    if not scan_dialog:
        return _json_error('扫描窗口未打开', 400)
    from utils.thread_safety import invoke_on_thread
    def _trigger():
        try:
            if hasattr(scan_dialog, '_on_scan_clicked'):
                scan_dialog._on_scan_clicked()
        except Exception as e:
            logger.error(f"停止扫描失败: {e}")
    invoke_on_thread(mw, _trigger)
    return _json_success(message='停止扫描已触发')


async def handle_scan_status(request):
    mw = get_main_window()
    if not mw:
        return _json_error('主窗口未初始化', 503)
    scan_dialog = getattr(mw, '_scan_dialog', None)
    scanner = getattr(scan_dialog, 'scanner', None) if scan_dialog else None
    if not scanner:
        return _json_success(scanning=False, validating=False, stats={})
    stats = dict(scanner.stats) if hasattr(scanner, 'stats') else {}
    return _json_success(
        scanning=scanner.is_scanning() if hasattr(scanner, 'is_scanning') else False,
        validating=getattr(scanner, 'is_validating', False),
        stats=stats
    )


async def handle_epg(request):
    mw = get_main_window()
    if not mw:
        return _json_error('主窗口未初始化', 503)
    epg_parser = getattr(mw, 'epg_parser', None)
    if not epg_parser:
        return _json_error('EPG解析器未初始化', 503)
    search = request.rel_url.query.get('search', '').strip().lower()
    channel_id = request.rel_url.query.get('id', '').strip()
    try:
        if hasattr(epg_parser, 'get_programmes_for_channel'):
            if channel_id:
                programmes = epg_parser.get_programmes_for_channel(channel_id)
                return _json_success(programmes=programmes)
        if hasattr(epg_parser, 'get_all_channels'):
            channels = epg_parser.get_all_channels()
            if search:
                channels = [ch for ch in channels if search in ch.get('name', '').lower() or search in ch.get('id', '').lower()]
            return _json_success(channels=channels)
    except Exception as e:
        logger.error(f"获取EPG失败: {e}")
    return _json_success(channels=[])


async def handle_stream_proxy(request):
    model = get_channel_model()
    if not model:
        return _json_error('频道模型未初始化', 503)
    try:
        idx = int(request.match_info['id'])
    except ValueError:
        return _json_error('无效的频道ID')
    if not (0 <= idx < model.rowCount()):
        return _json_error('频道不存在', 404)
    ch = model.get_channel(idx)
    if not ch or not ch.get('url'):
        return _json_error('频道URL为空', 404)
    stream_url = ch['url']
    import aiohttp
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(stream_url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                content_type = resp.headers.get('Content-Type', 'video/mp2t')
                response = web_response.StreamResponse(
                    status=resp.status,
                    headers={'Content-Type': content_type, 'Access-Control-Allow-Origin': '*'}
                )
                await response.prepare(request)
                async for chunk in resp.content.iter_chunked(8192):
                    await response.write(chunk)
                await response.write_eof()
                return response
    except asyncio.CancelledError:
        raise
    except Exception as e:
        logger.error(f"流代理失败: {stream_url} - {e}")
        return _json_error(f'流代理失败: {e}', 502)