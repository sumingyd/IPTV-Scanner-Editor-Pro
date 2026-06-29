import asyncio
import json
import logging
import os
import time
from aiohttp import web, web_response

from server.app import get_channel_model, get_config, get_main_window, get_server, get_context

logger = logging.getLogger('server.routes')

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


def _register_admin_routes(app):
    """注册管理后台静态文件路由"""
    admin_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'admin')
    if not os.path.isdir(admin_dir):
        logger.warning(f'Admin directory not found: {admin_dir}')
        return

    async def _handle_admin(request):
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
                          headers={'Cache-Control': 'no-cache, no-store, must-revalidate',
                                   'Pragma': 'no-cache', 'Expires': '0'})

    try:
        app.router.add_get('/admin/', _handle_admin)
        app.router.add_get('/admin/{path:.*}', _handle_admin)
        logger.info(f'Admin UI registered from: {admin_dir}')
    except ValueError:
        # Android 端可能已由 android_bridge.py 注册，忽略重复注册错误
        logger.debug('Admin routes already registered, skipping')


def _get_all_channels():
    ctx = get_context()
    if ctx:
        return ctx.get_all_channels()
    return []


_I18N = {
    'zh': {
        'title': 'IPTV扫描编辑器专业版',
        'subtitle': '直播Server & RESTful API',
        'status': '服务器状态',
        'running': '运行中',
        'stopped': '已停止',
        'uptime': '运行时间',
        'base_url': '访问地址',
        'playlist': '播放列表',
        'channels': '频道管理',
        'sources': '订阅源',
        'scan': '扫描',
        'epg': '节目单',
        'stream_proxy': '流代理',
        'footer': 'IPTV扫描编辑器专业版 · 内置HTTP Server · 基于 aiohttp',
        'm3u_desc': 'M3U播放列表 (参数: valid=1, search=, group=)',
        'm3u_group_desc': '按分组获取M3U播放列表',
        'ch_list_desc': '频道列表 (参数: valid=1/0, group=, search=, page=, size=)',
        'ch_get_desc': '按索引获取频道',
        'ch_add_desc': '添加频道 (body: {url, name, group})',
        'ch_update_desc': '更新频道',
        'ch_delete_desc': '删除频道',
        'src_list_desc': '获取订阅源列表',
        'src_add_desc': '添加订阅源 (body: {url, name})',
        'src_delete_desc': '删除订阅源',
        'scan_start_desc': '开始扫描 (body: {url})',
        'scan_stop_desc': '停止扫描',
        'scan_status_desc': '扫描状态和统计',
        'epg_desc': 'EPG节目单数据 (参数: id=, search=)',
        'stream_desc': '按索引代理频道流',
        'quick_m3u': 'M3U播放列表',
        'quick_channels': '频道列表',
        'quick_status': '运行状态',
        'quick_epg': '节目单',
        'no_data': '暂无频道数据',
    },
    'en': {
        'title': 'IPTV Scanner Editor Pro',
        'subtitle': 'Live Streaming Server & RESTful API',
        'status': 'Server Status',
        'running': 'Running',
        'stopped': 'Stopped',
        'uptime': 'Uptime',
        'base_url': 'Base URL',
        'playlist': 'Playlist',
        'channels': 'Channels',
        'sources': 'Sources',
        'scan': 'Scan',
        'epg': 'EPG',
        'stream_proxy': 'Stream Proxy',
        'footer': 'IPTV Scanner Editor Pro · Built-in HTTP Server · Powered by aiohttp',
        'm3u_desc': 'M3U playlist (params: valid=1, search=, group=)',
        'm3u_group_desc': 'M3U playlist by group',
        'ch_list_desc': 'Channel list (params: valid=1/0, group=, search=, page=, size=)',
        'ch_get_desc': 'Get channel by index',
        'ch_add_desc': 'Add channel (body: {url, name, group})',
        'ch_update_desc': 'Update channel',
        'ch_delete_desc': 'Delete channel',
        'src_list_desc': 'List subscription sources',
        'src_add_desc': 'Add source (body: {url, name})',
        'src_delete_desc': 'Delete source',
        'scan_start_desc': 'Start scan (body: {url})',
        'scan_stop_desc': 'Stop scan',
        'scan_status_desc': 'Scan status & stats',
        'epg_desc': 'EPG data (params: id=, search=)',
        'stream_desc': 'Proxy stream for channel by index',
        'quick_m3u': 'M3U Playlist',
        'quick_channels': 'Channels',
        'quick_status': 'Status',
        'quick_epg': 'EPG',
        'no_data': 'No channel data',
    }
}


def _get_lang(request):
    lang = request.rel_url.query.get('lang', '').strip().lower()
    if lang in ('zh', 'cn', 'zh-cn', 'zh_cn'):
        return 'zh'
    accept = request.headers.get('Accept-Language', '')
    if 'zh' in accept.lower():
        return 'zh'
    return 'en'


def _t(lang, key, default=''):
    return _I18N.get(lang, {}).get(key, _I18N.get('en', {}).get(key, default))


def create_app() -> web.Application:
    app = web.Application(middlewares=[error_middleware, cors_middleware])
    app.router.add_get('/', handle_index)
    app.router.add_get('/api/status', handle_status)
    app.router.add_get('/api/m3u', handle_m3u)
    app.router.add_get('/api/m3u/{group}', handle_m3u)
    app.router.add_get('/api/channels', handle_channels_list)
    app.router.add_get('/api/channels/{id}', handle_channel_get)
    app.router.add_put('/api/channels/{id}', handle_channel_update)
    app.router.add_delete('/api/channels/{id}', handle_channel_delete)
    app.router.add_post('/api/channels', handle_channel_add)
    app.router.add_post('/api/channels/import', handle_channels_import)
    app.router.add_get('/api/sources', handle_sources_list)
    app.router.add_post('/api/sources', handle_sources_add)
    app.router.add_delete('/api/sources/{id}', handle_sources_delete)
    app.router.add_post('/api/sources/reload', handle_sources_reload)
    app.router.add_get('/api/sources/status', handle_sources_status)
    app.router.add_get('/api/epg/sources', handle_epg_sources_list)
    app.router.add_post('/api/epg/sources', handle_epg_sources_add)
    app.router.add_delete('/api/epg/sources/{id}', handle_epg_sources_delete)
    app.router.add_post('/api/scan/start', handle_scan_start)
    app.router.add_post('/api/scan/stop', handle_scan_stop)
    app.router.add_get('/api/scan/status', handle_scan_status)
    app.router.add_post('/api/scan/range', handle_scan_range)
    app.router.add_get('/api/scan/results', handle_scan_results)
    app.router.add_get('/api/mappings', handle_mappings_list)
    app.router.add_post('/api/mappings', handle_mappings_add)
    app.router.add_delete('/api/mappings/{id}', handle_mappings_delete)
    app.router.add_post('/api/mappings/refresh', handle_mappings_refresh)
    app.router.add_get('/api/epg', handle_epg)
    app.router.add_get('/stream/{id}', handle_stream_proxy)
    # 播放器远程控制
    app.router.add_get('/api/player/chapters', handle_player_chapters)
    app.router.add_post('/api/player/hdr', handle_player_hdr)
    app.router.add_post('/api/player/screenshot', handle_player_screenshot)
    # 字幕在线下载
    app.router.add_get('/api/subtitle/search', handle_subtitle_search)
    app.router.add_post('/api/subtitle/download', handle_subtitle_download)
    # 文件分享与缓存清理
    app.router.add_post('/api/share/file', handle_share_file)
    app.router.add_post('/api/cache/clear', handle_cache_clear)
    # 管理后台静态文件（局域网 Web 管理页面）
    _register_admin_routes(app)
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


async def handle_index(request):
    server = get_server()
    base_url = f"http://{request.host}"
    lang = _get_lang(request)
    html = _render_index_page(base_url, server, lang)
    return web.Response(text=html, content_type='text/html', charset='utf-8')


def _render_index_page(base_url, server, lang='en'):
    is_running = server.is_running() if server else False
    uptime = server.get_uptime() if server else 0
    uptime_str = f"{uptime // 3600}h {uptime % 3600 // 60}m {uptime % 60}s" if uptime > 0 else "-"
    status_color = "#4CAF50" if is_running else "#FF9800"
    status_text = _t(lang, 'running') if is_running else _t(lang, 'stopped')

    api_groups = [
        {
            "title": _t(lang, 'playlist'),
            "icon": "&#9654;",
            "apis": [
                {"method": "GET", "path": "/api/m3u", "desc": _t(lang, 'm3u_desc'), "type": "link"},
                {"method": "GET", "path": "/api/m3u/{group}", "desc": _t(lang, 'm3u_group_desc'), "type": "link"},
            ]
        },
        {
            "title": _t(lang, 'channels'),
            "icon": "&#128250;",
            "apis": [
                {"method": "GET", "path": "/api/channels", "desc": _t(lang, 'ch_list_desc'), "type": "json"},
                {"method": "GET", "path": "/api/channels/{id}", "desc": _t(lang, 'ch_get_desc'), "type": "json"},
                {"method": "POST", "path": "/api/channels", "desc": _t(lang, 'ch_add_desc'), "type": "json"},
                {"method": "PUT", "path": "/api/channels/{id}", "desc": _t(lang, 'ch_update_desc'), "type": "json"},
                {"method": "DELETE", "path": "/api/channels/{id}", "desc": _t(lang, 'ch_delete_desc'), "type": "json"},
            ]
        },
        {
            "title": _t(lang, 'sources'),
            "icon": "&#128229;",
            "apis": [
                {"method": "GET", "path": "/api/sources", "desc": _t(lang, 'src_list_desc'), "type": "json"},
                {"method": "POST", "path": "/api/sources", "desc": _t(lang, 'src_add_desc'), "type": "json"},
                {"method": "DELETE", "path": "/api/sources/{id}", "desc": _t(lang, 'src_delete_desc'), "type": "json"},
            ]
        },
        {
            "title": _t(lang, 'scan'),
            "icon": "&#128269;",
            "apis": [
                {"method": "POST", "path": "/api/scan/start", "desc": _t(lang, 'scan_start_desc'), "type": "json"},
                {"method": "POST", "path": "/api/scan/stop", "desc": _t(lang, 'scan_stop_desc'), "type": "json"},
                {"method": "GET", "path": "/api/scan/status", "desc": _t(lang, 'scan_status_desc'), "type": "json"},
            ]
        },
        {
            "title": _t(lang, 'epg'),
            "icon": "&#128197;",
            "apis": [
                {"method": "GET", "path": "/api/epg", "desc": _t(lang, 'epg_desc'), "type": "json"},
            ]
        },
        {
            "title": _t(lang, 'stream_proxy'),
            "icon": "&#127909;",
            "apis": [
                {"method": "GET", "path": "/stream/{id}", "desc": _t(lang, 'stream_desc'), "type": "stream"},
            ]
        },
    ]

    method_colors = {"GET": "#4CAF50", "POST": "#FF9800", "PUT": "#2196F3", "DELETE": "#F44336"}

    api_sections = ""
    for group in api_groups:
        rows = ""
        for api in group["apis"]:
            mc = method_colors.get(api["method"], "#999")
            type_badge = ""
            if api["type"] == "link":
                type_badge = f'<a href="{base_url}{api["path"]}" target="_blank" style="color:#4CAF50;font-size:11px;text-decoration:none;">&#128279; Open</a>'
            elif api["type"] == "stream":
                type_badge = '<span style="color:#9C27B0;font-size:11px;">STREAM</span>'
            else:
                type_badge = '<span style="color:#607D8B;font-size:11px;">JSON</span>'
            rows += f"""
            <tr>
                <td style="padding:8px 12px;"><span style="background:{mc};color:#fff;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600;">{api["method"]}</span></td>
                <td style="padding:8px 12px;font-family:monospace;font-size:13px;color:#E0E0E0;">{api["path"]}</td>
                <td style="padding:8px 12px;font-size:12px;color:#BDBDBD;">{api["desc"]}</td>
                <td style="padding:8px 12px;">{type_badge}</td>
            </tr>"""
        api_sections += f"""
        <div style="margin-bottom:24px;">
            <h3 style="color:#E0E0E0;margin:0 0 8px 0;font-size:15px;">{group["icon"]} {group["title"]}</h3>
            <table style="width:100%;border-collapse:collapse;background:rgba(255,255,255,0.03);border-radius:8px;overflow:hidden;">
                {rows}
            </table>
        </div>"""

    lang_toggle = 'en' if lang == 'zh' else 'zh'
    lang_label = 'English' if lang == 'zh' else '中文'

    return f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{_t(lang, 'title')} - API</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ background:#1a1a2e; color:#E0E0E0; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif; min-height:100vh; }}
.container {{ max-width:960px; margin:0 auto; padding:40px 24px; }}
.header {{ text-align:center; margin-bottom:40px; }}
.header h1 {{ font-size:28px; font-weight:700; color:#fff; margin-bottom:8px; }}
.header p {{ font-size:14px; color:#9E9E9E; }}
.lang-toggle {{ position:absolute; top:16px; right:24px; background:rgba(255,255,255,0.08); border:1px solid rgba(255,255,255,0.12); border-radius:6px; padding:6px 14px; color:#BDBDBD; font-size:12px; text-decoration:none; transition:all 0.2s; }}
.lang-toggle:hover {{ background:rgba(255,255,255,0.15); color:#fff; }}
.status-card {{ display:flex; align-items:center; justify-content:center; gap:16px; background:rgba(255,255,255,0.05); border:1px solid rgba(255,255,255,0.08); border-radius:12px; padding:20px; margin-bottom:32px; }}
.status-dot {{ width:12px; height:12px; border-radius:50%; background:{status_color}; box-shadow:0 0 8px {status_color}; }}
.status-info {{ text-align:left; }}
.status-info .label {{ font-size:12px; color:#9E9E9E; text-transform:uppercase; letter-spacing:1px; }}
.status-info .value {{ font-size:16px; font-weight:600; color:#fff; }}
.quick-links {{ display:flex; gap:12px; justify-content:center; flex-wrap:wrap; margin-bottom:32px; }}
.quick-link {{ background:rgba(255,255,255,0.06); border:1px solid rgba(255,255,255,0.1); border-radius:8px; padding:12px 20px; text-decoration:none; color:#E0E0E0; font-size:13px; transition:all 0.2s; }}
.quick-link:hover {{ background:rgba(255,255,255,0.12); border-color:rgba(255,255,255,0.2); color:#fff; }}
.quick-link .path {{ font-family:monospace; color:#4CAF50; font-size:12px; }}
.footer {{ text-align:center; margin-top:40px; padding-top:20px; border-top:1px solid rgba(255,255,255,0.06); color:#616161; font-size:12px; }}
</style>
</head>
<body>
<a class="lang-toggle" href="?lang={lang_toggle}">{lang_label}</a>
<div class="container">
    <div class="header">
        <h1>{_t(lang, 'title')}</h1>
        <p>{_t(lang, 'subtitle')}</p>
    </div>
    <div class="status-card">
        <div class="status-dot"></div>
        <div class="status-info">
            <div class="label">{_t(lang, 'status')}</div>
            <div class="value">{status_text} &middot; {_t(lang, 'uptime')}: {uptime_str}</div>
        </div>
        <div class="status-info" style="margin-left:32px;">
            <div class="label">{_t(lang, 'base_url')}</div>
            <div class="value" style="font-family:monospace;font-size:14px;">{base_url}</div>
        </div>
    </div>
    <div class="quick-links">
        <a class="quick-link" href="{base_url}/api/m3u" target="_blank">&#9654; {_t(lang, 'quick_m3u')} <span class="path">/api/m3u</span></a>
        <a class="quick-link" href="{base_url}/api/channels" target="_blank">&#128250; {_t(lang, 'quick_channels')} <span class="path">/api/channels</span></a>
        <a class="quick-link" href="{base_url}/api/status" target="_blank">&#8505; {_t(lang, 'quick_status')} <span class="path">/api/status</span></a>
        <a class="quick-link" href="{base_url}/api/epg" target="_blank">&#128197; {_t(lang, 'quick_epg')} <span class="path">/api/epg</span></a>
    </div>
    {api_sections}
    <div class="footer">
        {_t(lang, 'footer')}
    </div>
</div>
</body>
</html>"""


async def handle_status(request):
    server = get_server()
    channels = _get_all_channels()
    total = len(channels)
    valid = sum(1 for ch in channels if ch.get('valid') is True)
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
    channels = _get_all_channels()
    if not channels:
        return _json_error('暂无频道数据', 503)
    group_filter = request.match_info.get('group', None)
    valid_only = request.rel_url.query.get('valid', '0') == '1'
    search = request.rel_url.query.get('search', '').strip().lower()
    lines = ['#EXTM3U']
    for ch in channels:
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
    all_channels = _get_all_channels()
    if not all_channels:
        return _json_error('暂无频道数据', 503)
    valid_only = request.rel_url.query.get('valid', '').strip()
    group = request.rel_url.query.get('group', '').strip()
    search = request.rel_url.query.get('search', '').strip().lower()
    page = max(1, int(request.rel_url.query.get('page', '1')))
    page_size = min(500, max(1, int(request.rel_url.query.get('size', '100'))))
    channels = []
    for i, ch in enumerate(all_channels):
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
    # 分组按 M3U 文件中的首次出现顺序（保持原序，去重），与 PC 端 _update_groups_for 逻辑一致
    groups = list(dict.fromkeys(ch.get('group', '') for ch in all_channels if ch.get('group')))
    return _json_success(
        channels=page_items,
        total=total_filtered,
        page=page,
        page_size=page_size,
        groups=groups
    )


async def handle_channel_get(request):
    all_channels = _get_all_channels()
    if not all_channels:
        return _json_error('暂无频道数据', 503)
    try:
        idx = int(request.match_info['id'])
    except ValueError:
        return _json_error('无效的频道ID')
    if not (0 <= idx < len(all_channels)):
        return _json_error('频道不存在', 404)
    ch = all_channels[idx]
    return _json_success(channel={**ch, '_index': idx} if ch else None)


async def handle_channel_update(request):
    model = get_channel_model()
    all_channels = _get_all_channels()
    if not all_channels:
        return _json_error('暂无频道数据', 503)
    try:
        idx = int(request.match_info['id'])
    except ValueError:
        return _json_error('无效的频道ID')
    data = await request.json()
    if model and 0 <= idx < model.rowCount():
        model.update_channel(idx, data)
    else:
        mw = get_main_window()
        if mw:
            for ch_list in (getattr(mw, '_sub_channels', []), getattr(mw, '_local_channels', [])):
                if 0 <= idx < len(ch_list):
                    ch_list[idx].update(data)
                    break
    return _json_success()


async def handle_channel_delete(request):
    model = get_channel_model()
    all_channels = _get_all_channels()
    if not all_channels:
        return _json_error('暂无频道数据', 503)
    try:
        idx = int(request.match_info['id'])
    except ValueError:
        return _json_error('无效的频道ID')
    if model and 0 <= idx < model.rowCount():
        model.remove_channel(idx)
    return _json_success()


async def handle_channel_add(request):
    data = await request.json()
    if not data.get('url'):
        return _json_error('URL不能为空')
    data.setdefault('name', data['url'].split('/')[-1])
    data.setdefault('group', '未分类')
    data.setdefault('valid', None)
    data.setdefault('status', '')
    model = get_channel_model()
    if model:
        model.add_channel(data)
    return _json_success()


async def handle_channels_import(request):
    try:
        data = await request.json()
    except Exception:
        return _json_error('无效的请求数据', 400)
    content = data.get('content', '')
    name = data.get('name', 'imported')
    if not content:
        return _json_error('内容为空', 400)
    try:
        from services.m3u_parser import parse_m3u_content
        channels, _ = parse_m3u_content(content)
        ctx = get_context()
        if ctx and hasattr(ctx, '_channels'):
            ctx._channels.extend(channels)
            existing_groups = set(ctx._channels and [c.get('group', '') for c in ctx._channels] or [])
            all_groups = list(dict.fromkeys([c.get('group', '未分组') for c in ctx._channels]))
            ctx._channels_list = all_groups if hasattr(ctx, '_channels_list') else None
        return _json_success(imported=len(channels))
    except Exception as e:
        return _json_error(f'解析失败: {e}', 500)


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


async def handle_epg_sources_list(request):
    """列出 EPG 订阅源"""
    config = get_config()
    if not config or not hasattr(config, 'load_epg_sources'):
        return _json_success(sources=[])
    try:
        sources = config.load_epg_sources()
    except Exception as e:
        logger.warning(f"加载EPG源失败: {e}")
        sources = []
    return _json_success(sources=sources)


async def handle_epg_sources_add(request):
    """添加 EPG 订阅源"""
    config = get_config()
    if not config:
        return _json_error('配置未初始化', 503)
    if not hasattr(config, 'save_epg_sources'):
        return _json_error('当前环境不支持 EPG 订阅源管理', 503)
    data = await request.json()
    url = data.get('url', '').strip()
    name = data.get('name', '').strip()
    if not url:
        return _json_error('URL不能为空')
    try:
        sources = config.load_epg_sources() if hasattr(config, 'load_epg_sources') else []
    except Exception:
        sources = []
    # 去重
    if any(s.get('url') == url for s in sources):
        return _json_error('该 EPG 源已存在', 409)
    sources.append({'url': url, 'name': name or url, 'last_update': None})
    config.save_epg_sources(sources)
    # 触发后台重新加载 EPG 数据
    ctx = get_context()
    if ctx and hasattr(ctx, 'reload_epg'):
        ctx.reload_epg()
    return _json_success()


async def handle_epg_sources_delete(request):
    """删除 EPG 订阅源"""
    config = get_config()
    if not config:
        return _json_error('配置未初始化', 503)
    if not hasattr(config, 'save_epg_sources'):
        return _json_error('当前环境不支持 EPG 订阅源管理', 503)
    try:
        idx = int(request.match_info['id'])
    except ValueError:
        return _json_error('无效的源ID')
    try:
        sources = config.load_epg_sources() if hasattr(config, 'load_epg_sources') else []
    except Exception:
        sources = []
    if not (0 <= idx < len(sources)):
        return _json_error('源不存在', 404)
    sources.pop(idx)
    config.save_epg_sources(sources)
    return _json_success()


async def handle_sources_reload(request):
    """重新加载订阅源（独立于扫描整理功能）"""
    ctx = get_context()
    if not ctx:
        return _json_error('上下文未初始化', 503)
    data = {}
    try:
        data = await request.json()
    except Exception:
        pass
    url = (data.get('url') or '').strip()
    if ctx.is_standalone():
        if not ctx.reload_sources(url):
            return _json_error('订阅源正在加载中', 409)
        return _json_success(message='订阅源加载已开始')
    # 桌面模式：调用主窗口的加载逻辑
    mw = ctx.get_main_window()
    if mw and hasattr(mw, 'reload_subscription'):
        import threading
        threading.Thread(target=mw.reload_subscription, args=(url,), daemon=True).start()
        return _json_success(message='订阅源加载已开始')
    return _json_error('不支持此操作', 503)


async def handle_sources_status(request):
    """获取订阅源加载状态"""
    ctx = get_context()
    if not ctx:
        return _json_success(loading=False, message='未初始化')
    if ctx.is_standalone():
        status = ctx.get_source_load_status()
        return _json_success(**status)
    return _json_success(loading=False, message='桌面模式')


async def handle_scan_start(request):
    ctx = get_context()
    if not ctx:
        return _json_error('上下文未初始化', 503)

    # 独立模式（Android/无 GUI）：使用 URL 范围扫描
    if ctx.is_standalone():
        scanner = ctx.get_standalone_scanner()
        if not scanner:
            return _json_error('扫描器未初始化', 503)
        data = {}
        try:
            data = await request.json()
        except Exception:
            pass
        url = data.get('url', '').strip()
        if not url:
            return _json_error('请提供扫描URL', 400)
        if scanner.is_scanning():
            return _json_error('扫描已在进行中', 409)
        timeout = int(data.get('timeout', 10))
        threads = int(data.get('threads', 4))
        if scanner.start_range_scan(url, timeout, threads):
            return _json_success(message='URL 范围扫描已开始')
        return _json_error('启动扫描失败', 500)

    # 桌面模式：依赖 _scan_dialog
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
    ctx = get_context()
    if not ctx:
        return _json_error('上下文未初始化', 503)

    # 独立模式：停止 StandaloneScanner
    if ctx.is_standalone():
        scanner = ctx.get_standalone_scanner()
        if scanner:
            scanner.stop_scan()
            return _json_success(message='停止扫描已触发')
        return _json_error('扫描器未初始化', 503)

    # 桌面模式
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
    ctx = get_context()
    if not ctx:
        return _json_success(scanning=False, validating=False, stats={})

    # 独立模式：返回 StandaloneScanner 状态
    if ctx.is_standalone():
        scanner = ctx.get_standalone_scanner()
        if not scanner:
            return _json_success(scanning=False, validating=False, stats={})
        status = scanner.get_status()
        return _json_success(
            scanning=status.get('running', False),
            validating=False,
            running=status.get('running', False),
            total=status.get('total', 0),
            valid=status.get('valid', 0),
            invalid=status.get('invalid', 0),
            scanned=status.get('scanned', 0),
            message=status.get('message', ''),
            stats={
                'total': status.get('total', 0),
                'valid': status.get('valid', 0),
                'invalid': status.get('invalid', 0),
                'scanned': status.get('scanned', 0),
            }
        )

    # 桌面模式
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


async def handle_scan_range(request):
    """URL 范围扫描（PC 端"扫描整理"功能）

    body: {url, timeout?, threads?}
    url 支持 [1-255] / [1,5,10] / [1-10,20-30] 等方括号范围表达式
    """
    ctx = get_context()
    if not ctx:
        return _json_error('上下文未初始化', 503)
    if not ctx.is_standalone():
        return _json_error('当前环境不支持 URL 范围扫描（仅独立模式可用）', 503)
    scanner = ctx.get_standalone_scanner()
    if not scanner:
        return _json_error('扫描器未初始化', 503)
    data = {}
    try:
        data = await request.json()
    except Exception:
        pass
    base_url = (data.get('url') or '').strip()
    if not base_url:
        return _json_error('URL 不能为空')
    if scanner.is_scanning():
        return _json_error('扫描已在进行中', 409)
    timeout = int(data.get('timeout', 10) or 10)
    threads = int(data.get('threads', 4) or 4)
    timeout = max(1, min(timeout, 60))
    threads = max(1, min(threads, 64))
    if scanner.start_range_scan(base_url, timeout, threads):
        return _json_success(message='URL 范围扫描已开始')
    return _json_error('启动扫描失败', 500)


async def handle_scan_results(request):
    """获取 URL 范围扫描结果列表"""
    ctx = get_context()
    if not ctx:
        return _json_success(results=[])
    if not ctx.is_standalone():
        return _json_success(results=[])
    scanner = ctx.get_standalone_scanner()
    if not scanner:
        return _json_success(results=[])
    return _json_success(results=scanner.get_results())


def _get_mapping_manager():
    """获取频道映射管理器（全局单例，不依赖 PySide6）"""
    try:
        from models.channel_mappings import mapping_manager
        return mapping_manager
    except Exception as e:
        logger.warning(f"映射管理器不可用: {e}")
        return None


async def handle_mappings_list(request):
    """列出所有映射条目"""
    mm = _get_mapping_manager()
    if not mm:
        return _json_error('映射管理器不可用', 503)
    try:
        entries = mm.get_mapping_entries()
        remote_url = ''
        config = get_config()
        if config:
            try:
                remote_url = config.get_setting('channel_mappings', 'remote_url', '')
            except Exception:
                pass
        return _json_success(entries=entries, remote_url=remote_url)
    except Exception as e:
        return _json_error(f'获取映射失败: {e}', 500)


async def handle_mappings_add(request):
    """添加用户映射 body: {raw_name, standard_name, logo_url?, group_name?}"""
    mm = _get_mapping_manager()
    if not mm:
        return _json_error('映射管理器不可用', 503)
    data = {}
    try:
        data = await request.json()
    except Exception:
        pass
    raw_name = (data.get('raw_name') or '').strip()
    standard_name = (data.get('standard_name') or '').strip()
    if not raw_name or not standard_name:
        return _json_error('原始名称和标准名称不能为空')
    logo_url = (data.get('logo_url') or '').strip()
    group_name = (data.get('group_name') or '').strip()
    try:
        mm.add_user_mapping(raw_name, standard_name, logo_url, group_name)
        return _json_success(message='映射已添加')
    except Exception as e:
        return _json_error(f'添加映射失败: {e}', 500)


async def handle_mappings_delete(request):
    """删除映射 {id} 格式: standard_name 或 standard_name||raw_name"""
    mm = _get_mapping_manager()
    if not mm:
        return _json_error('映射管理器不可用', 503)
    key = request.match_info['id']
    try:
        if '||' in key:
            standard_name, raw_name = key.split('||', 1)
            mm.remove_user_mapping_entry(standard_name, raw_name)
        else:
            mm.remove_user_mapping(key)
        return _json_success(message='映射已删除')
    except Exception as e:
        return _json_error(f'删除映射失败: {e}', 500)


async def handle_mappings_refresh(request):
    """刷新远程映射缓存"""
    mm = _get_mapping_manager()
    if not mm:
        return _json_error('映射管理器不可用', 503)
    try:
        # 在后台线程中刷新，避免阻塞
        import threading
        def _do_refresh():
            try:
                mm.refresh_cache()
            except Exception as e:
                logger.error(f"刷新远程映射失败: {e}")
        threading.Thread(target=_do_refresh, daemon=True).start()
        return _json_success(message='正在刷新远程映射...')
    except Exception as e:
        return _json_error(f'刷新失败: {e}', 500)


async def handle_epg(request):
    ctx = get_context()
    epg_parser = ctx.get_epg_parser() if ctx else None
    if not epg_parser:
        return _json_error('EPG解析器未初始化', 503)
    search = request.rel_url.query.get('search', '').strip().lower()
    channel_id = request.rel_url.query.get('id', '').strip()
    try:
        # SubscriptionManager 接口（standalone 模式）
        if hasattr(epg_parser, 'get_channel_epg'):
            if channel_id:
                programmes = epg_parser.get_channel_epg(channel_id) or []
                # 给每个节目添加 Unix 时间戳字段（前端用此判断当前节目）
                for p in programmes:
                    if 'start_ts' not in p:
                        try:
                            from datetime import datetime
                            start_str = p.get('start', '')
                            stop_str = p.get('stop', p.get('end', ''))
                            if start_str:
                                p['start_ts'] = int(datetime.fromisoformat(start_str).timestamp())
                            if stop_str:
                                p['stop_ts'] = int(datetime.fromisoformat(stop_str).timestamp())
                        except Exception:
                            pass
                return _json_success(programmes=programmes)
            if hasattr(epg_parser, 'get_epg_data_copy'):
                data = epg_parser.get_epg_data_copy() or {}
                channels = [{'id': k, 'name': k, 'programmes': len(v)} for k, v in data.items()]
                if search:
                    channels = [ch for ch in channels if search in ch.get('name', '').lower() or search in ch.get('id', '').lower()]
                return _json_success(channels=channels)
        # 桌面端 EPG parser 接口
        if hasattr(epg_parser, 'get_programmes_for_channel'):
            if channel_id:
                programmes = epg_parser.get_programmes_for_channel(channel_id)
                for p in programmes:
                    if 'start_ts' not in p:
                        try:
                            from datetime import datetime
                            start_str = p.get('start', '')
                            stop_str = p.get('stop', p.get('end', ''))
                            if start_str:
                                p['start_ts'] = int(datetime.fromisoformat(start_str).timestamp())
                            if stop_str:
                                p['stop_ts'] = int(datetime.fromisoformat(stop_str).timestamp())
                        except Exception:
                            pass
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
    all_channels = _get_all_channels()
    if not all_channels:
        return _json_error('暂无频道数据', 503)
    try:
        idx = int(request.match_info['id'])
    except ValueError:
        return _json_error('无效的频道ID')
    if not (0 <= idx < len(all_channels)):
        return _json_error('频道不存在', 404)
    ch = all_channels[idx]
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


# ===================== 播放器远程控制 =====================

def _get_player():
    """获取主窗口的 player_controller"""
    mw = get_main_window()
    if mw and hasattr(mw, 'player_controller'):
        return mw.player_controller
    return None


def _get_cache_dir(sub: str) -> str:
    """获取缓存子目录绝对路径，不存在则创建"""
    base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'cache', sub)
    os.makedirs(base, exist_ok=True)
    return base


async def handle_player_chapters(request):
    """读取当前播放文件的章节列表"""
    pc = _get_player()
    if not pc:
        return _json_error('播放器未初始化', 503)
    try:
        chapters = pc.get_chapter_list()
        return _json_success(data=chapters)
    except Exception as e:
        logger.error(f"获取章节列表失败: {e}")
        return _json_error(f'获取章节失败: {e}', 500)


async def handle_player_hdr(request):
    """切换 HDR 输出模式（需要重新初始化 mpv）"""
    try:
        body = await request.json()
    except Exception:
        body = {}
    mode = (body or {}).get('mode', '').strip().lower()
    valid_modes = {'disable', 'tonemap', 'passthrough', 'scrgb', 'auto'}
    if mode not in valid_modes:
        return _json_error(f'无效的 HDR 模式: {mode}，支持: {", ".join(sorted(valid_modes))}')
    pc = _get_player()
    if not pc:
        return _json_error('播放器未初始化', 503)
    try:
        # reinit_for_hdr_change 是阻塞操作（涉及 mpv 重新初始化）
        # 放到线程池执行，避免阻塞 event loop
        await asyncio.to_thread(pc.reinit_for_hdr_change, mode)
        return _json_success(mode=mode)
    except Exception as e:
        logger.error(f"切换 HDR 模式失败: {e}")
        return _json_error(f'切换 HDR 失败: {e}', 500)


async def handle_player_screenshot(request):
    """截图保存到缓存目录，返回路径"""
    try:
        body = await request.json()
    except Exception:
        body = {}
    mode = (body or {}).get('mode', 'video').strip().lower()
    # mpv screenshot-to-file 支持: video / subtitles / window / each-frame
    if mode not in ('video', 'subtitles', 'window', 'each-frame'):
        mode = 'video'
    pc = _get_player()
    if not pc or not pc.is_playing:
        return _json_error('当前无播放内容', 400)
    try:
        import time as _t
        cache_dir = _get_cache_dir('screenshots')
        fname = f"shot_{int(_t.time())}.png"
        fpath = os.path.join(cache_dir, fname)
        # 在线程池执行截图（send_command 是带锁的同步调用）
        ret = await asyncio.to_thread(pc.send_command, ['screenshot-to-file', fpath, mode])
        if ret != 0 and not os.path.exists(fpath):
            return _json_error('截图失败（mpv 返回错误）', 500)
        return _json_success(path=fpath)
    except Exception as e:
        logger.error(f"截图失败: {e}")
        return _json_error(f'截图失败: {e}', 500)


# ===================== 字幕在线下载 =====================

_subtitle_service_lock = asyncio.Lock()


async def handle_subtitle_search(request):
    """通过 OpenSubtitles 搜索字幕

    Query 参数：
      q: 关键词（片名，可中英文）
      lang: 语言代码（eng/chi/all），默认 all
      imdb: IMDb ID（可选）
      file_path: 视频文件路径（可选，用于哈希精准匹配）
    """
    q = request.rel_url.query.get('q', '').strip()
    lang = request.rel_url.query.get('lang', 'all').strip().lower() or 'all'
    imdb = request.rel_url.query.get('imdb', '').strip()
    file_path = request.rel_url.query.get('file_path', '').strip()
    # URL 解码处理（前端可能传 file:// 路径）
    if file_path:
        from urllib.parse import unquote
        file_path = unquote(file_path)
    if not q and not file_path and not imdb:
        return _json_error('请提供搜索关键词或文件路径')
    try:
        from services.subtitle_download_service import SubtitleDownloadService
        # 复用单例（保持登录 token）
        svc = getattr(handle_subtitle_search, '_svc', None)
        if svc is None:
            svc = SubtitleDownloadService()
            handle_subtitle_search._svc = svc
        # OpenSubtitles 调用是阻塞的，放到线程池
        async with _subtitle_service_lock:
            items = await asyncio.to_thread(svc.search, q, imdb, lang, file_path)
        if not items:
            err = getattr(svc, 'last_error', '') or '未找到字幕'
            return _json_success(data=[], message=err)
        # 转成前端期望的格式
        data = [{
            'filename': it.get('file_name', ''),
            'lang': it.get('language', ''),
            'size': it.get('size', 0),
            'url': it.get('download_link', ''),
            'rating': it.get('rating', 0),
            'movie_name': it.get('movie_name', ''),
        } for it in items]
        return _json_success(data=data)
    except Exception as e:
        logger.error(f"字幕搜索失败: {e}")
        return _json_error(f'字幕搜索失败: {e}', 500)


async def handle_subtitle_download(request):
    """下载字幕文件到缓存目录，返回本地路径"""
    try:
        body = await request.json()
    except Exception:
        body = {}
    url = (body or {}).get('url', '').strip()
    name = (body or {}).get('name', '').strip()
    if not url:
        return _json_error('URL 不能为空')
    try:
        from services.subtitle_download_service import SubtitleDownloadService
        svc = getattr(handle_subtitle_search, '_svc', None) or SubtitleDownloadService()
        handle_subtitle_search._svc = svc
        cache_dir = _get_cache_dir('subtitles')
        # 下载是阻塞的，放到线程池
        path = await asyncio.to_thread(svc.download, url, cache_dir, name)
        if not path:
            err = getattr(svc, 'last_error', '') or '下载失败'
            return _json_error(err)
        return _json_success(path=path)
    except Exception as e:
        logger.error(f"字幕下载失败: {e}")
        return _json_error(f'字幕下载失败: {e}', 500)


# ===================== 文件分享与缓存清理 =====================

async def handle_share_file(request):
    """分享文件

    PC 端：使用系统默认程序打开文件所在目录
    Android：通过 share intent 分享（由原生层处理，这里仅返回成功）
    """
    try:
        body = await request.json()
    except Exception:
        body = {}
    path = (body or {}).get('path', '').strip()
    if not path or not os.path.exists(path):
        return _json_error('文件不存在', 404)
    try:
        import sys
        if sys.platform == 'win32':
            # Windows: 在资源管理器中选中文件
            import subprocess
            subprocess.Popen(['explorer', '/select,', path])
        elif sys.platform == 'darwin':
            import subprocess
            subprocess.Popen(['open', '-R', path])
        else:
            # Linux/Android: 打开所在目录
            import subprocess
            subprocess.Popen(['xdg-open', os.path.dirname(path)])
        return _json_success()
    except Exception as e:
        logger.error(f"分享文件失败: {e}")
        return _json_error(f'分享失败: {e}', 500)


async def handle_cache_clear(request):
    """清空缓存目录

    Body: {type: 'thumbnails'/'screenshots'/'subtitles'/'all'}
    """
    try:
        body = await request.json()
    except Exception:
        body = {}
    cache_type = (body or {}).get('type', 'all').strip().lower()
    valid_types = {'thumbnails', 'screenshots', 'subtitles', 'all'}
    if cache_type not in valid_types:
        return _json_error(f'无效的缓存类型: {cache_type}')
    try:
        cache_root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'cache')
        targets = [cache_type] if cache_type != 'all' else ['thumbnails', 'screenshots', 'subtitles']
        cleared = []
        for sub in targets:
            sub_dir = os.path.join(cache_root, sub)
            if not os.path.isdir(sub_dir):
                continue
            # 删除目录下所有文件（保留目录本身）
            for fname in os.listdir(sub_dir):
                fpath = os.path.join(sub_dir, fname)
                try:
                    if os.path.isfile(fpath):
                        os.remove(fpath)
                    elif os.path.isdir(fpath):
                        import shutil
                        shutil.rmtree(fpath, ignore_errors=True)
                except Exception as e:
                    logger.warning(f"删除 {fpath} 失败: {e}")
            cleared.append(sub)
        return _json_success(cleared=cleared)
    except Exception as e:
        logger.error(f"清空缓存失败: {e}")
        return _json_error(f'清空缓存失败: {e}', 500)