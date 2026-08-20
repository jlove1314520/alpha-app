/* Alpha app prototype service worker */
const CACHE = 'alpha-v1.0.1';
const ASSETS = ['./', './index.html', './manifest.webmanifest', './icon192.png', './icon512.png'];

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE).then(c =>
      // 逐一快取，單一檔案失敗不會讓整個安裝失敗
      Promise.all(ASSETS.map(u => c.add(u).catch(() => null)))
    ).then(() => self.skipWaiting())
  );
});
self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});
self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  if (url.pathname.endsWith('/sw.js')) return;   // 不攔截 sw.js 本身
  e.respondWith(
    fetch(e.request).then(r => {
      const copy = r.clone();
      caches.open(CACHE).then(c => c.put(e.request, copy)).catch(()=>{});
      return r;
    }).catch(() => caches.match(e.request).then(m => m || caches.match('./index.html')))
  );
});
