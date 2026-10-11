// 2026-10-11 先.六十九-1：外殼「快取優先、背景更新、點提示條才換版」的端到端驗證（取代冒煙 #9 舊的 network-first 驗證）。
// 做法：把外殼檔複製到暫存目錄，用本檔內建的小型靜態伺服器提供（資料檔一律 404，與本測試無關），然後：
//   ①第一次開啟 → SW 安裝、接管，外殼進快取
//   ②在「舊版快取」塞一份竄改過的 index.html（模擬手機殘留的舊安裝）
//   ③改暫存目錄的 sw.js 版本號（模擬發布新版）→ reg.update() → 新 SW 在背景裝好並「等待」
//   ④頁面必須顯示「有新版」提示條；點下去（applyNewVersion）→ 新 SW 接手並自動重載
//   ⑤重載後：由新版 SW 接管、舊版快取被刪除、畫面不是竄改內容、APP_VERSION 正常
import fs from "node:fs";
import http from "node:http";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const TYPES = { ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
  ".json": "application/json", ".webmanifest": "application/manifest+json", ".png": "image/png" };

function serve(dir) {
  return new Promise((resolve) => {
    const srv = http.createServer((req, res) => {
      const p = decodeURIComponent(new URL(req.url, "http://x").pathname);
      const f = path.join(dir, p === "/" ? "index.html" : p);
      if (!f.startsWith(dir) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) { res.writeHead(404); res.end(); return; }
      res.writeHead(200, { "Content-Type": TYPES[path.extname(f)] || "application/octet-stream", "Cache-Control": "no-cache" });
      fs.createReadStream(f).pipe(res);
    });
    srv.listen(0, "127.0.0.1", () => resolve(srv));
  });
}

export async function checkSwUpdateFlow(browser) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "alpha-sw-"));
  const files = fs.readdirSync(ROOT).filter(f => /^(index\.html|sw\.js|app(-[a-z]+)?\.js|app\.css|manifest\.webmanifest|icon.*\.png)$/.test(f));
  for (const f of files) fs.copyFileSync(path.join(ROOT, f), path.join(dir, f));
  const srv = await serve(dir);
  const base = `http://127.0.0.1:${srv.address().port}`;
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const out = { steps: [] };
  try {
    const page = await ctx.newPage();
    await page.goto(base + "/index.html", { waitUntil: "load" });
    const oldCache = await page.evaluate(async () => {
      await navigator.serviceWorker.ready;
      for (let i = 0; i < 100 && !navigator.serviceWorker.controller; i++) await new Promise(r => setTimeout(r, 100));
      return (await caches.keys()).find(k => k.startsWith("alpha-v")) || null;
    });
    out.oldCache = oldCache;
    if (!oldCache) throw new Error("第一次開啟後沒有 alpha-v 快取（SW 沒裝好）");
    // ② 舊版快取塞竄改內容
    await page.evaluate(async (name) => {
      const c = await caches.open(name);
      await c.put(new Request(location.origin + "/index.html"), new Response("<html><body>STALE_FAKE_CONTENT_MARKER</body></html>", { headers: { "Content-Type": "text/html" } }));
    }, oldCache);
    // ③ 發布新版：改暫存目錄的 sw.js 版本號
    const newCache = "alpha-v9999-12-31.2359";
    const swp = path.join(dir, "sw.js");
    fs.writeFileSync(swp, fs.readFileSync(swp, "utf8").replace(/const CACHE = 'alpha-v[^']*'/, `const CACHE = '${newCache}'`));
    const st = await page.evaluate(async () => {
      const reg = await navigator.serviceWorker.getRegistration();
      await reg.update();
      for (let i = 0; i < 150 && !reg.waiting; i++) await new Promise(r => setTimeout(r, 100));
      await new Promise(r => setTimeout(r, 200));
      return { waiting: !!reg.waiting, banner: getComputedStyle(document.getElementById("new-version-banner")).display };
    });
    out.waiting = st.waiting; out.banner = st.banner;
    // ④ 點提示條 → 新 SW 接手 → 自動重載
    await Promise.all([page.waitForEvent("load", { timeout: 20000 }), page.evaluate(() => applyNewVersion())]);
    await page.waitForFunction(() => typeof window.__ALPHA_BOOT_MS === "number", null, { timeout: 20000 });
    // ⑤ 驗證
    const after = await page.evaluate(async () => ({
      keys: await caches.keys(), body: document.body.innerHTML.includes("STALE_FAKE_CONTENT_MARKER"),
      ver: typeof APP_VERSION !== "undefined" ? APP_VERSION : null, controlled: !!navigator.serviceWorker.controller,
      swUrl: navigator.serviceWorker.controller && navigator.serviceWorker.controller.scriptURL,
    }));
    Object.assign(out, after, { newCache });
    out.ok = st.waiting && st.banner === "block" && after.controlled && after.keys.includes(newCache) && !after.keys.includes(oldCache) && !after.body && !!after.ver;
    return out;
  } finally {
    await ctx.close();
    srv.close();
    fs.rmSync(dir, { recursive: true, force: true });
  }
}
