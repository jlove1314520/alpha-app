/* Alpha app prototype service worker */

/* 2026-08-25 修正：資料卡在 8/21 不更新，根因是這個檔案——舊版對「所有」成功的
   fetch 回應都快取，包括 FinMind 行情 API、App 自己的 scores.json 評分結果，
   一旦網路暫時不順（手機切換 Wi-Fi/行動網路很常見），就會拿舊快取頂替，卻不會
   顯示任何提示，使用者只會看到舊資料、以為是最新的。
   新規則：只有「App 外殼」（index.html/manifest/icon 這幾個介面檔案）才快取；
   任何行情/評分資料（FinMind、scores.json）一律不攔截、不快取、失敗就是失敗
   ——完全不呼叫 respondWith()，讓瀏覽器照平常方式直接打網路，成功拿新資料、
   失敗就是網路錯誤，由 App 的 fetch 呼叫端（index.html 的 fm()）自己顯示
   「連線失敗，請重試」，不會被這裡默默塞舊資料進去。 */
const CACHE = 'alpha-v2026-08-28.0329'; // 2026-08-28起改用時間戳格式，由.git/hooks/pre-commit在每次commit時自動改寫
const SHELL_URLS = ['./', './index.html', './manifest.webmanifest', './icon192.png', './icon512.png', './icon512-maskable.png'];

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE).then(c =>
      // 逐一快取，單一檔案失敗不會讓整個安裝失敗
      Promise.all(SHELL_URLS.map(u => c.add(u).catch(() => null)))
    ).then(() => self.skipWaiting())
  );
});
self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

// 判斷是不是「App 外殼」的固定介面檔案（不含資料）：同網域、且路徑對得上上面
// 那份短清單。scores.json 雖然也是同網域，但它是「評分資料」不是外殼，特別排除。
function isShellRequest(request) {
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return false; // 跨網域（含 api.finmindtrade.com）一律不算外殼
  if (url.pathname.endsWith('/scores.json')) return false; // 評分資料，不是外殼
  const path = url.pathname === '/' ? './' : ('.' + url.pathname);
  return SHELL_URLS.includes(path);
}

self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  if (url.pathname.endsWith('/sw.js')) return; // 不攔截 sw.js 本身

  if (!isShellRequest(e.request)) {
    // 行情/評分/任何非外殼資料：完全不呼叫 respondWith()，等同不攔截，瀏覽器
    // 直接照平常方式打網路——network-only，不快取、失敗不回退舊資料。
    return;
  }

  // App 外殼：network-first，成功就更新快取；失敗才退回快取版本（這裡退回的是
  // 「介面本身」，不是行情資料，網路不通時能開啟舊版介面總比完全打不開好）。
  e.respondWith(
    fetch(e.request).then(r => {
      const copy = r.clone();
      caches.open(CACHE).then(c => c.put(e.request, copy)).catch(() => {});
      return r;
    }).catch(() => caches.match(e.request).then(m => m || caches.match('./index.html')))
  );
});
