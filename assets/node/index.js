/**
 * IPTV Node.js 服务容器
 * 
 * 核心能力：
 * 1. migu API 代理 - 咪咕直播源接口
 * 2. M3U 播放列表服务 - 聚合多源频道列表
 * 3. EPG 电子节目单 - XMLTV 格式
 * 4. 流代理 - 跨域转发直播流
 * 5. 频道管理 RESTful API
 * 
 * 设计原则：
 * - server + player 合体：既是 API server，也能直接提供播放数据
 * - 多端多平台复用：同一套代码服务 Win/Mac/Linux/Android/iOS
 * - UI 也可部分复用：前端页面可被任何 WebView 加载
 */

const express = require('express');
const cors = require('cors');
const axios = require('axios');
const path = require('path');
const fs = require('fs');
const { URL } = require('url');

const app = express();
const PORT = parseInt(process.env.PORT || '2699', 10);
const HOST = process.env.HOST || '0.0.0.0';

app.use(cors());
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

// ==================== 配置 ====================

const CONFIG = {

  sources: [],
  channels: [],
  epgData: null,
  startTime: Date.now(),
};

// 加载频道数据（从 data/ 目录或上游源）
function loadChannelsData() {
  const dataFile = path.join(__dirname, 'data', 'channels.json');
  if (fs.existsSync(dataFile)) {
    try {
      CONFIG.channels = JSON.parse(fs.readFileSync(dataFile, 'utf-8'));
      console.log(`[IPTV] 已加载 ${CONFIG.channels.length} 个频道`);
    } catch (e) {
      console.error('[IPTV] 加载频道数据失败:', e.message);
    }
  }
}

// 加载订阅源配置
function loadSourcesConfig() {
  const sourcesFile = path.join(__dirname, 'data', 'sources.json');
  if (fs.existsSync(sourcesFile)) {
    try {
      CONFIG.sources = JSON.parse(fs.readFileSync(sourcesFile, 'utf-8'));
    } catch (e) {
      console.error('[IPTV] 加载源配置失败:', e.message);
    }
  }
}

loadChannelsData();
loadSourcesConfig();

// ==================== 工具函数 ====================

function jsonSuccess(data = null, extra = {}) {
  const result = { success: true, ...extra };
  if (data !== null) result.data = data;
  return result;
}

function jsonError(message, code = 400) {
  return { success: false, error: message, code };
}

// 从上游 M3U URL 获取并解析频道列表
async function fetchM3UFromUrl(url) {
  try {
    const resp = await axios.get(url, {
      timeout: 15000,
      headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' },
      responseType: 'text',
    });
    return parseM3U(resp.data);
  } catch (e) {
    console.error(`[IPTV] 获取 M3U 失败: ${url}`, e.message);
    return [];
  }
}

// 解析 M3U 文本为频道数组
function parseM3U(text) {
  const channels = [];
  const lines = text.split('\n');
  let current = null;
  for (const line of lines) {
    const trimmed = line.trim();
    if (trimmed.startsWith('#EXTINF:')) {
      current = { name: '', group: '', logo: '', tvgId: '', tvgChno: '', url: '', valid: null };
      const infoMatch = trimmed.match(/#EXTINF:-1\s+(.*),(.*)$/);
      if (infoMatch) {
        current.name = infoMatch[2].trim();
        const attrs = infoMatch[1];
        const groupMatch = attrs.match(/group-title="([^"]*)"/);
        if (groupMatch) current.group = groupMatch[1];
        const logoMatch = attrs.match(/tvg-logo="([^"]*)"/);
        if (logoMatch) current.logo = logoMatch[1];
        const idMatch = attrs.match(/tvg-id="([^"]*)"/);
        if (idMatch) current.tvgId = idMatch[1];
        const chnoMatch = attrs.match(/tvg-chno="([^"]*)"/);
        if (chnoMatch) current.tvgChno = chnoMatch[1];
      }
    } else if (current && trimmed && !trimmed.startsWith('#')) {
      current.url = trimmed;
      channels.push(current);
      current = null;
    }
  }
  return channels;
}

// 将频道数组序列化为 M3U 文本
function channelsToM3U(channels) {
  const lines = ['#EXTM3U'];
  for (const ch of channels) {
    const attrs = [];
    if (ch.tvgId) attrs.push(`tvg-id="${ch.tvgId}"`);
    if (ch.tvgChno) attrs.push(`tvg-chno="${ch.tvgChno}"`);
    if (ch.logo) attrs.push(`tvg-logo="${ch.logo}"`);
    attrs.push(`group-title="${ch.group || ''}"`);
    lines.push(`#EXTINF:-1 ${attrs.join(' ')},${ch.name || ''}`);
    lines.push(ch.url);
  }
  return lines.join('\n') + '\n';
}

// 聚合所有频道（本地 + 订阅源）
async function getAllChannels(options = {}) {
  let channels = [...CONFIG.channels];
  // 从订阅源获取
  for (const source of CONFIG.sources) {
    if (!source.enabled) continue;
    try {
      const fetched = await fetchM3UFromUrl(source.url);
      channels = channels.concat(fetched);
    } catch (e) {
      console.error(`[IPTV] 订阅源获取失败: ${source.url}`, e.message);
    }
  }
  // 去重
  const seen = new Set();
  channels = channels.filter(ch => {
    if (!ch.url || seen.has(ch.url)) return false;
    seen.add(ch.url);
    return true;
  });
  // 过滤
  if (options.validOnly) channels = channels.filter(ch => ch.valid === true);
  if (options.group) channels = channels.filter(ch => ch.group === options.group);
  if (options.search) {
    const s = options.search.toLowerCase();
    channels = channels.filter(ch =>
      (ch.name || '').toLowerCase().includes(s) || (ch.group || '').toLowerCase().includes(s)
    );
  }
  return channels;
}

// ==================== API 路由 ====================

// --- 首页 / API 文档 ---
app.get('/', (req, res) => {
  const lang = (req.query.lang || req.headers['accept-language'] || 'en').startsWith('zh') ? 'zh' : 'en';
  const i18n = {
    zh: { title: 'IPTV Node.js 服务容器', subtitle: 'migu API · M3U · EPG · 流代理 · 多端复用' },
    en: { title: 'IPTV Node.js Service Container', subtitle: 'migu API · M3U · EPG · Stream Proxy · Multi-platform' },
  };
  const t = i18n[lang];
  res.send(`<!DOCTYPE html>
<html lang="${lang}">
<head><meta charset="UTF-8"><title>${t.title}</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#1a1a2e;color:#E0E0E0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;min-height:100vh}
.c{max-width:800px;margin:0 auto;padding:40px 24px}
h1{font-size:24px;text-align:center;margin-bottom:8px}
p.sub{text-align:center;color:#9E9E9E;margin-bottom:32px}
.api{background:rgba(255,255,255,0.05);border-radius:8px;padding:16px;margin-bottom:16px}
.api h3{margin-bottom:8px;font-size:14px}
.api pre{font-family:monospace;font-size:12px;color:#BDBDBD;white-space:pre-wrap}
.get{color:#4CAF50}.post{color:#FF9800}.del{color:#F44336}
.footer{text-align:center;margin-top:32px;color:#616161;font-size:11px}
</style></head>
<body><div class="c">
<h1>${t.title}</h1>
<p class="sub">${t.subtitle}</p>
<div class="api"><h3>M3U 播放列表</h3><pre><span class="get">GET</span> /m3u              - 完整 M3U 列表 (params: valid=1, search=, group=)
<span class="get">GET</span> /m3u/{group}      - 按分组获取</pre></div>

<div class="api"><h3>频道管理</h3><pre><span class="get">GET</span>    /api/channels       - 频道列表 (params: valid=1/0, group=, search=, page=, size=)
<span class="get">GET</span>    /api/channels/{id}  - 单个频道
<span class="post">POST</span>   /api/channels       - 添加频道
<span class="post">PUT</span>    /api/channels/{id}  - 更新频道
<span class="del">DELETE</span> /api/channels/{id}  - 删除频道</pre></div>
<div class="api"><h3>EPG 节目单</h3><pre><span class="get">GET</span> /epg              - EPG 数据 (params: id=, search=)
<span class="get">GET</span> /playback.xml     - XMLTV 格式 EPG</pre></div>
<div class="api"><h3>流代理</h3><pre><span class="get">GET</span> /stream/{id}      - 代理频道流</pre></div>
<div class="api"><h3>服务状态</h3><pre><span class="get">GET</span> /api/status       - 服务器状态</pre></div>
<div class="footer">IPTV Node.js Service Container · Express · Multi-platform</div>
</div></body></html>`);
});

// --- 服务状态 ---
app.get('/api/status', (req, res) => {
  res.json(jsonSuccess(null, {
    server: 'running',
    host: HOST,
    port: PORT,
    uptime: Math.floor((Date.now() - CONFIG.startTime) / 1000),
    channels: CONFIG.channels.length,
    sources: CONFIG.sources.length,
    platform: process.platform,
    arch: process.arch,
    nodeVersion: process.version,
  }));
});

// --- M3U 播放列表 ---
app.get('/m3u', async (req, res) => {
  try {
    const channels = await getAllChannels({
      validOnly: req.query.valid === '1',
      group: req.query.group,
      search: req.query.search,
    });
    if (!channels.length) return res.status(503).json(jsonError('暂无频道数据'));
    res.type('audio/mpegurl');
    res.set('Content-Disposition', 'attachment; filename="iptv.m3u"');
    res.send(channelsToM3U(channels));
  } catch (e) {
    res.status(500).json(jsonError(e.message));
  }
});

app.get('/m3u/:group', async (req, res) => {
  try {
    const channels = await getAllChannels({
      validOnly: req.query.valid === '1',
      group: req.params.group,
      search: req.query.search,
    });
    if (!channels.length) return res.status(503).json(jsonError('该分组无频道'));
    res.type('audio/mpegurl');
    res.send(channelsToM3U(channels));
  } catch (e) {
    res.status(500).json(jsonError(e.message));
  }
});

// --- migu API（由外部插件提供，本容器不内置） ---
// 如需 migu 支持，请在 data/plugins/ 目录放置 migu 插件

// --- 频道管理 API ---
app.get('/api/channels', async (req, res) => {
  try {
    let channels = await getAllChannels();
    const valid = req.query.valid;
    const group = req.query.group;
    const search = req.query.search;
    const page = Math.max(1, parseInt(req.query.page || '1', 10));
    const size = Math.min(500, Math.max(1, parseInt(req.query.size || '100', 10)));

    if (valid === '1') channels = channels.filter(ch => ch.valid === true);
    if (valid === '0') channels = channels.filter(ch => ch.valid === false);
    if (group) channels = channels.filter(ch => ch.group === group);
    if (search) {
      const s = search.toLowerCase();
      channels = channels.filter(ch =>
        (ch.name || '').toLowerCase().includes(s) || (ch.group || '').toLowerCase().includes(s)
      );
    }

    const total = channels.length;
    const start = (page - 1) * size;
    const items = channels.slice(start, start + size).map((ch, i) => ({ ...ch, _index: start + i }));
    const groups = [...new Set(channels.map(ch => ch.group).filter(Boolean))].sort();

    res.json(jsonSuccess(null, { channels: items, total, page, page_size: size, groups }));
  } catch (e) {
    res.status(500).json(jsonError(e.message));
  }
});

app.get('/api/channels/:id', async (req, res) => {
  try {
    const channels = await getAllChannels();
    const idx = parseInt(req.params.id, 10);
    if (isNaN(idx) || idx < 0 || idx >= channels.length) {
      return res.status(404).json(jsonError('频道不存在'));
    }
    res.json(jsonSuccess(null, { channel: { ...channels[idx], _index: idx } }));
  } catch (e) {
    res.status(500).json(jsonError(e.message));
  }
});

app.post('/api/channels', (req, res) => {
  try {
    const ch = req.body;
    if (!ch.url) return res.status(400).json(jsonError('URL 不能为空'));
    ch.name = ch.name || ch.url.split('/').pop();
    ch.group = ch.group || '未分类';
    ch.valid = ch.valid !== undefined ? ch.valid : null;
    CONFIG.channels.push(ch);
    saveChannelsData();
    res.json(jsonSuccess());
  } catch (e) {
    res.status(500).json(jsonError(e.message));
  }
});

app.put('/api/channels/:id', (req, res) => {
  try {
    const idx = parseInt(req.params.id, 10);
    if (isNaN(idx) || idx < 0 || idx >= CONFIG.channels.length) {
      return res.status(404).json(jsonError('频道不存在'));
    }
    Object.assign(CONFIG.channels[idx], req.body);
    saveChannelsData();
    res.json(jsonSuccess());
  } catch (e) {
    res.status(500).json(jsonError(e.message));
  }
});

app.delete('/api/channels/:id', (req, res) => {
  try {
    const idx = parseInt(req.params.id, 10);
    if (isNaN(idx) || idx < 0 || idx >= CONFIG.channels.length) {
      return res.status(404).json(jsonError('频道不存在'));
    }
    CONFIG.channels.splice(idx, 1);
    saveChannelsData();
    res.json(jsonSuccess());
  } catch (e) {
    res.status(500).json(jsonError(e.message));
  }
});

// --- EPG ---
app.get('/epg', (req, res) => {
  if (!CONFIG.epgData) return res.json(jsonSuccess(null, { channels: [] }));
  const channelId = req.query.id;
  const search = (req.query.search || '').toLowerCase();
  if (channelId) {
    const programmes = (CONFIG.epgData.programmes || []).filter(p => p.channel === channelId);
    return res.json(jsonSuccess(null, { programmes }));
  }
  let channels = CONFIG.epgData.channels || [];
  if (search) {
    channels = channels.filter(ch =>
      (ch.name || '').toLowerCase().includes(search) || (ch.id || '').toLowerCase().includes(search)
    );
  }
  res.json(jsonSuccess(null, { channels }));
});

// XMLTV 格式 EPG
app.get('/playback.xml', (req, res) => {
  const xmlFile = path.join(__dirname, 'data', 'epg.xml');
  if (fs.existsSync(xmlFile)) {
    res.type('application/xml');
    res.sendFile(xmlFile);
  } else {
    res.type('application/xml');
    res.send('<?xml version="1.0" encoding="UTF-8"?>\n<tv></tv>');
  }
});

// --- 流代理 ---
app.get('/stream/:id', async (req, res) => {
  try {
    const channels = await getAllChannels();
    const idx = parseInt(req.params.id, 10);
    if (isNaN(idx) || idx < 0 || idx >= channels.length) {
      return res.status(404).json(jsonError('频道不存在'));
    }
    const streamUrl = channels[idx].url;
    if (!streamUrl) return res.status(404).json(jsonError('频道 URL 为空'));

    const upstream = await axios.get(streamUrl, {
      timeout: 30000,
      responseType: 'stream',
      headers: { 'User-Agent': 'Mozilla/5.0' },
    });
    res.set('Content-Type', upstream.headers['content-type'] || 'video/mp2t');
    res.set('Access-Control-Allow-Origin', '*');
    upstream.data.pipe(res);
  } catch (e) {
    res.status(502).json(jsonError(`流代理失败: ${e.message}`));
  }
});

// --- 订阅源管理 ---
app.get('/api/sources', (req, res) => {
  res.json(jsonSuccess(null, { sources: CONFIG.sources }));
});

app.post('/api/sources', (req, res) => {
  const { url, name } = req.body;
  if (!url) return res.status(400).json(jsonError('URL 不能为空'));
  CONFIG.sources.push({ url, name: name || url, enabled: true });
  saveSourcesConfig();
  res.json(jsonSuccess());
});

app.delete('/api/sources/:id', (req, res) => {
  const idx = parseInt(req.params.id, 10);
  if (isNaN(idx) || idx < 0 || idx >= CONFIG.sources.length) {
    return res.status(404).json(jsonError('源不存在'));
  }
  CONFIG.sources.splice(idx, 1);
  saveSourcesConfig();
  res.json(jsonSuccess());
});

// ==================== 数据持久化 ====================

function saveChannelsData() {
  const dataDir = path.join(__dirname, 'data');
  if (!fs.existsSync(dataDir)) fs.mkdirSync(dataDir, { recursive: true });
  fs.writeFileSync(path.join(dataDir, 'channels.json'), JSON.stringify(CONFIG.channels, null, 2));
}

function saveSourcesConfig() {
  const dataDir = path.join(__dirname, 'data');
  if (!fs.existsSync(dataDir)) fs.mkdirSync(dataDir, { recursive: true });
  fs.writeFileSync(path.join(dataDir, 'sources.json'), JSON.stringify(CONFIG.sources, null, 2));
}

// ==================== 启动 ====================

const server = app.listen(PORT, HOST, () => {
  console.log(`[IPTV] Node.js 服务容器已启动: http://${HOST}:${PORT}`);
  console.log(`[IPTV] 平台: ${process.platform} ${process.arch} | Node: ${process.version}`);
  console.log(`[IPTV] 频道数: ${CONFIG.channels.length} | 订阅源: ${CONFIG.sources.length}`);
});

server.on('error', (e) => {
  console.error(`[IPTV] 服务启动失败:`, e.message);
  process.exit(1);
});

process.on('SIGTERM', () => server.close());
process.on('SIGINT', () => server.close());