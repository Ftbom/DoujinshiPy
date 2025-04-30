const CACHE_NAME = "pwa-cache-v2";
const urlsToCache = [
  "/web/static/styles.css",
  "/web/static/doujinshi.js",
  "/web/static/ehtag.js",
  "/web/static/loading.gif",
  "/web/static/icons/favicon.ico",
  "/web/static/icons/icon-192x192.png",
  "/web/static/icons/icon-512x512.png",
  "/web/offline"
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(urlsToCache).catch(console.error))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then(cacheNames =>
      Promise.all(
        cacheNames.map(name => name !== CACHE_NAME && caches.delete(name))
      )
    ).then(() => self.clients.claim())
  );
});

const authPaths = [
  '/web/page',
  '/web/tags',
  '/web/batch',
  '/web/group',
  '/web/other',
  '/web/read'
];

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  
  if (authPaths.some(path => url.pathname.startsWith(path))) {
    // 认证请求：网络优先，失败时显示离线页面
    event.respondWith(
      fetch(event.request).catch(() => caches.match("/web/offline"))
    );
  } else if (urlsToCache.some(path => url.pathname.includes(path))) {
    // 静态资源：缓存优先，网络更新
    event.respondWith(
      caches.match(event.request).then(cached => {
        const networkFetch = fetch(event.request).then(resp => {
          const clone = resp.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
          return resp;
        });
        return cached || networkFetch;
      })
    );
  } else {
    // 其他请求：网络优先
    event.respondWith(fetch(event.request));
  }
});