const CACHE_NAME = "pwa-cache-v1";
const urlsToCache = ["/web/page", "/web/tags", "/web/batch", "/web/group", "/web/other",
    "/web/static/styles.css", "/web/static/doujinshi.js", "/web/static/ehtag.js",
    "/web/static/icons/favicon.ico", "/web/static/icons/icon-192x192.png", "/web/static/icons/icon-512x512.png"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(urlsToCache);
    })
  );
});

self.addEventListener("fetch", (event) => {
  event.respondWith(
    caches.match(event.request).then((response) => {
      return response || fetch(event.request);
    })
  );
});
