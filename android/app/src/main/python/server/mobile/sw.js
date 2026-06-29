/* IPTV Scanner Editor Pro - Service Worker
 * 策略：network-first（优先从网络获取最新版本，失败时回退到缓存）
 * 避免 stale-while-revalidate 导致的 HTML 修改不生效问题 */
const CACHE_NAME = 'iptv-pwa-v2';
const ASSETS = [
  '/mobile/',
  '/mobile/manifest.json',
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  /* API 和流代理请求不经过 Service Worker */
  if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/stream/')) {
    return;
  }
  /* network-first 策略：优先从网络获取最新版本
   * 网络失败时回退到缓存，确保离线可用 */
  event.respondWith(
    fetch(event.request).then(response => {
      if (response && response.status === 200) {
        const clone = response.clone();
        caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
      }
      return response;
    }).catch(() => {
      return caches.match(event.request).then(cached => {
        return cached || new Response('离线模式', { status: 503 });
      });
    })
  );
});
