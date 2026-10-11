// 2026-10-11 先.六十九-1 驗收：模擬 4G（下行 1.6Mbps、上行 750kbps、RTT 150ms），第二次開啟首頁到「可互動」的時間。
// 「可互動」＝核心 app.js 執行完畢（導覽與各面板載入函式都已註冊，點分頁會有反應），app.js 結尾寫入
// window.__ALPHA_BOOT_MS＝performance.now()（從導覽開始起算）。資料檔仍走網路，不算在可互動時間內。
// 同時統計第二次開啟後 10 秒內同一個 data/*.json 路徑被實際打到網路幾次（驗 60 秒記憶體快取）。
// 用法：先在 alpha-app 目錄跑 python -m http.server 8792，再 node scripts/measure_second_open.mjs [--url 網址]
import { chromium } from "@playwright/test";
import { launchGuarded } from "./pw_guard.mjs";

const FOUR_G = { offline: false, latency: 150, downloadThroughput: (1.6 * 1024 * 1024) / 8, uploadThroughput: (750 * 1024) / 8 };

async function throttle(ctx, page) {
  const cdp = await ctx.newCDPSession(page);
  await cdp.send("Network.enable");
  await cdp.send("Network.emulateNetworkConditions", FOUR_G);
  return cdp;
}

export async function measureSecondOpen(browser, baseUrl, { settleMs = 10000 } = {}) {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
  try {
    // 第一次開啟：讓 SW 安裝並把外殼放進快取
    const p1 = await ctx.newPage();
    await throttle(ctx, p1);
    await p1.goto(`${baseUrl}/index.html`, { waitUntil: "load", timeout: 60000 });
    await p1.evaluate(async () => {
      await navigator.serviceWorker.ready;
      for (let i = 0; i < 100 && !navigator.serviceWorker.controller; i++) await new Promise(r => setTimeout(r, 100));
    });
    const firstBoot = await p1.evaluate(() => window.__ALPHA_BOOT_MS || null);
    const cached = await p1.evaluate(async () => { const ks = await caches.keys(); let n = 0; for (const k of ks) n += (await (await caches.open(k)).keys()).length; return n; });
    await p1.waitForTimeout(1500);
    await p1.close();

    // 第二次開啟：計時＋記錄網路請求
    const p2 = await ctx.newPage();
    await throttle(ctx, p2);
    const net = [];
    p2.on("request", r => net.push(r));
    await p2.goto(`${baseUrl}/index.html`, { waitUntil: "domcontentloaded", timeout: 60000 });
    await p2.waitForFunction(() => typeof window.__ALPHA_BOOT_MS === "number", null, { timeout: 30000 });
    const t = await p2.evaluate(() => {
      const nav = performance.getEntriesByType("navigation")[0] || {};
      return { boot: window.__ALPHA_BOOT_MS, dcl: nav.domContentLoadedEventEnd || null, controlled: !!navigator.serviceWorker.controller };
    });
    await p2.waitForTimeout(settleMs);
    // 實際打到網路的 data/*.json（SW 不攔截資料；記憶體快取命中的根本不會發出請求）
    const counts = {};
    for (const r of net) {
      const u = new URL(r.url());
      if (u.origin === new URL(baseUrl).origin && /\/data\/.+\.json$/.test(u.pathname)) counts[u.pathname] = (counts[u.pathname] || 0) + 1;
    }
    const dups = Object.entries(counts).filter(([, n]) => n > 1);
    await p2.close();
    return { firstBootMs: firstBoot && Math.round(firstBoot), shellCached: cached, secondBootMs: Math.round(t.boot), secondDclMs: t.dcl && Math.round(t.dcl),
             controlled: t.controlled, dataRequests: Object.values(counts).reduce((a, b) => a + b, 0), dups };
  } finally {
    await ctx.close();
  }
}

if (process.argv[1] && process.argv[1].endsWith("measure_second_open.mjs")) {
  const a = process.argv.slice(2);
  const url = a.includes("--url") ? a[a.indexOf("--url") + 1] : "http://localhost:8792";
  const { browser, close } = await launchGuarded(chromium, { headless: true }, { label: "measure_second_open", hardTimeoutMs: 5 * 60 * 1000 });
  let r;
  try { r = await measureSecondOpen(browser, url); } finally { await close(); }
  console.log(`4G 模擬（1.6Mbps／RTT 150ms）：第一次可互動 ${r.firstBootMs}ms；第二次可互動 ${r.secondBootMs}ms（DOMContentLoaded ${r.secondDclMs}ms）；` +
    `SW 接管=${r.controlled}、外殼快取 ${r.shellCached} 檔`);
  console.log(`第二次開啟 10 秒內 data/*.json 網路請求 ${r.dataRequests} 次；重複：${r.dups.length ? r.dups.map(([p, n]) => p + "×" + n).join("、") : "無"}`);
  const ok = r.secondBootMs < 1500 && r.controlled && !r.dups.length;
  console.log(ok ? "=== 通過（<1.5 秒、無重複抓取）===" : "=== 未通過 ===");
  process.exit(ok ? 0 : 1);
}
