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
const CACHE = 'alpha-v2026-10-16.0155'; // 2026-08-28起改用時間戳格式，由.git/hooks/pre-commit在每次commit時自動改寫
// 2026-10-11 常備.開發-20：index.html 的 CSS／JS 拆成 app.css／app.js，一併列為外殼，離線仍可開啟。
// index.html 以 app.css?v=…／app.js?v=… 引用；isShellRequest 只比對路徑（不含查詢字串），
// 離線回退用 ignoreSearch 讓安裝時預快取的無查詢字串版本也對得上。
// 2026-10-11 常備.開發-20 丙案：分頁程式拆到 app-<頁>.js（點到該頁才載入），一併列為外殼預快取，離線仍可切換各頁。
const SHELL_URLS = ['./', './index.html', './app.css', './app.js', './app-shared.js', './app-market.js', './app-picks.js', './app-stock.js', './app-trade.js', './app-journal.js', './app-settings.js', './manifest.webmanifest', './icon192.png', './icon512.png', './icon512-maskable.png'];

// 2026-10-11 先.六十九-1：外殼改「快取優先、背景更新」。
// - 外殼（SHELL_URLS）一律先回這一版快取，開 App 不必等網路；版本＝CACHE 常數。
// - 新版：瀏覽器每次開 App 會在背景比對 sw.js（頁面也會呼叫 reg.update()），內容不同就在背景安裝新的 SW，
//   把新版外殼整批抓進新的 CACHE（cache:'reload' 繞過 HTTP 快取，避免新 SW 裝到舊檔），裝好後「等待」，
//   不自動接手——頁面看到 waiting 就顯示既有的「有新版」提示條，使用者點了才 postMessage SKIP_WAITING → 重載。
//   使用者完全關閉 App 再開，瀏覽器也會自動換上等待中的新版。整批換版，不會新 index 配舊 app.js。
// - 資料檔：2026-10-13 總司令【先.八十一】8 裁示④改為「先顯示上次資料、背景更新」（stale-while-revalidate）：
//   同網域 data/*.json 有上次存的就先回（回應加 x-alpha-from-cache 與 x-alpha-cached-at 標頭，頁面據此標「上次資料」），
//   同時背景抓新版存起來；新版內容不同就 postMessage {type:'DATA_UPDATED', path} 通知頁面重畫。
//   沒存過→照常打網路並存起來。cache:'no-store'／'reload' 的請求（檢查、測試）照舊直通網路。
//   排除：price_history.json（55MB，App 不讀）。scores*.json、FinMind 等其他請求照舊不攔截。
const DATA_CACHE = 'alpha-data-v1';  // 與外殼版本無關：換版不清掉資料，讓第二次開永遠有東西先顯示
const DATA_EXCLUDE = /\/data\/price_history(\.json$|\/)/;  // 先.八十二-1：拆檔資料夾也不進快取
self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE).then(c =>
      // 逐一快取，單一檔案失敗不會讓整個安裝失敗
      Promise.all(SHELL_URLS.map(u => c.add(new Request(u, { cache: 'reload' })).catch(() => null)))
    )
  );
});
self.addEventListener('message', e => {
  if (e.data && e.data.type === 'SKIP_WAITING') self.skipWaiting();
});
self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE && k !== DATA_CACHE).map(k => caches.delete(k))))  // 資料快取跨版本保留
      .then(() => self.clients.claim())
  );
});

// 判斷是不是「App 外殼」的固定介面檔案（不含資料）：同網域、且路徑（相對 SW scope）對得上上面
// 那份短清單。scores.json 雖然也是同網域，但它是「評分資料」不是外殼，特別排除。
function isShellRequest(request) {
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return false; // 跨網域（含 api.finmindtrade.com）一律不算外殼
  if (url.pathname.endsWith('/scores.json')) return false; // 評分資料，不是外殼
  const scope = new URL(self.registration.scope).pathname;
  const rel = url.pathname.startsWith(scope) ? url.pathname.slice(scope.length) : url.pathname.replace(/^\//, '');
  return SHELL_URLS.includes(rel === '' ? './' : './' + rel);
}

self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  if (url.pathname.endsWith('/sw.js')) return; // 不攔截 sw.js 本身
  if (e.request.method !== 'GET') return;

  if (url.origin === self.location.origin && /\/data\/[^?]*\.json$/.test(url.pathname) && !DATA_EXCLUDE.test(url.pathname)) {
    if (e.request.cache === 'no-store' || e.request.cache === 'reload') return;  // 要最新的：直通網路
    e.respondWith(dataSWR(e));
    return;
  }

  if (!isShellRequest(e.request)) {
    // 行情/評分/任何非外殼資料：完全不呼叫 respondWith()，等同不攔截，瀏覽器
    // 直接照平常方式打網路——network-only，不快取、失敗不回退舊資料。
    return;
  }

  // App 外殼：快取優先（本版 CACHE）。快取沒有（安裝時單檔失敗）才打網路並補進快取；
  // 網路也失敗時，頁面導覽退回 index.html，app.js／app.css 回網路錯誤（拿到 HTML 會解析失敗）。
  e.respondWith(
    caches.open(CACHE).then(c => c.match(e.request, { ignoreSearch: true }).then(hit => hit ||
      fetch(e.request).then(r => {
        if (r.ok) c.put(e.request, r.clone()).catch(() => {});
        return r;
      }).catch(() => (e.request.mode === 'navigate'
        ? c.match('./index.html', { ignoreSearch: true }).then(m => m || Response.error())
        : Response.error()))))
  );
});

// 資料檔 stale-while-revalidate（先.八十一-8）。快取鍵＝路徑（去掉 ?t= 這類破快取參數）。
async function dataSWR(e) {
  const url = new URL(e.request.url);
  const key = new Request(url.origin + url.pathname);
  const c = await caches.open(DATA_CACHE);
  const hit = await c.match(key);
  const net = fetch(e.request).then(async r => {
    if (r.ok) {
      const body = await r.clone().arrayBuffer();
      const h = new Headers(r.headers);
      h.set('x-alpha-cached-at', new Date().toISOString());
      const changed = !hit || (await hit.clone().arrayBuffer().then(b => b.byteLength !== body.byteLength || new Uint8Array(b).some((v, i) => v !== new Uint8Array(body)[i])).catch(() => true));
      await c.put(key, new Response(body, { status: r.status, statusText: r.statusText, headers: h })).catch(() => {});
      if (hit && changed) {
        const list = await self.clients.matchAll({ type: 'window' });
        list.forEach(cl => cl.postMessage({ type: 'DATA_UPDATED', path: url.pathname }));
      }
    }
    return r;
  });
  if (hit) {
    e.waitUntil(net.catch(() => {}));
    const h = new Headers(hit.headers);
    h.set('x-alpha-from-cache', '1');
    return new Response(await hit.blob(), { status: hit.status, statusText: hit.statusText, headers: h });
  }
  return net;
}

// 先.三十一-一：Web Push（VAPID）。本機 alpha_live_server／auto_rebalance_bb90.py 送來的
// 否決窗、拒單、漏跑、批次完成通知。iOS 規定每則 push 都必須顯示通知，不可靜默。
self.addEventListener('push', e => {
  let d = {};
  try { d = e.data ? e.data.json() : {}; } catch (err) { d = { body: e.data ? e.data.text() : '' }; }
  const title = d.title || 'Alpha';
  e.waitUntil(self.registration.showNotification(title, {
    body: d.body || '', tag: d.tag || 'alpha', renotify: true,
    icon: './icon192.png', badge: './icon192.png', data: { url: d.url || './' }
  }));
});
self.addEventListener('notificationclick', e => {
  e.notification.close();
  const target = new URL((e.notification.data && e.notification.data.url) || './', self.registration.scope).href;
  e.waitUntil(self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(list => {
    for (const c of list) { if ('focus' in c) return c.focus(); }
    return self.clients.openWindow(target);
  }));
});
