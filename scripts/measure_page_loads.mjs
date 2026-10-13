// 先.八十一-9（2026-10-13）：量測「個股頁」與「選股頁」額外下載量（全新瀏覽器環境、無快取、無 SW、393×852）。
// 做法：先開首頁等穩定（不算），之後開個股頁（並逐一點四個子分頁）或切到選股頁，只計算這之後發出的請求。
// 位元組算法同 measure_first_load.mjs：同網域檔案以本機檔案 gzip 後大小計（GitHub Pages 會 gzip），跨網域用瀏覽器回報值。
// 用法：node scripts/measure_page_loads.mjs [--url http://localhost:8792] [--code 2330]
import fs from "node:fs";
import path from "node:path";
import zlib from "node:zlib";

const TEXT_EXT = /\.(html|js|mjs|css|json|txt|svg|webmanifest)$/i;

async function sizeRows(reqs, origin) {
  const rows = [];
  for (const r of reqs) {
    const u = new URL(r.url());
    let bytes = null, how = "";
    if (u.origin === origin) {
      let p = decodeURIComponent(u.pathname).replace(/^\//, "");
      if (!p || p.endsWith("/")) p += "index.html";
      const fp = path.resolve(p);
      if (fs.existsSync(fp) && fs.statSync(fp).isFile()) {
        const buf = fs.readFileSync(fp);
        bytes = TEXT_EXT.test(fp) ? zlib.gzipSync(buf, { level: 6 }).length : buf.length;
        how = TEXT_EXT.test(fp) ? "gzip" : "raw";
      } else { bytes = 0; how = "404"; }
    } else {
      try {
        const s = await Promise.race([r.sizes(), new Promise((_, rej) => setTimeout(() => rej(new Error("timeout")), 2000))]);
        bytes = (s.responseBodySize || 0) + (s.responseHeadersSize || 0); how = "browser";
      } catch (e) { bytes = null; how = "unknown"; }
    }
    rows.push({ url: r.url().replace(/\?.*$/, ""), bytes, how });
  }
  return rows.sort((a, b) => (b.bytes || 0) - (a.bytes || 0));
}

export async function measurePage(browser, baseUrl, which, { code = "2330", settleMs = 6000 } = {}) {
  const ctx = await browser.newContext({ viewport: { width: 393, height: 852 }, serviceWorkers: "block" });
  const page = await ctx.newPage();
  const origin = new URL(baseUrl).origin;
  try {
    await page.goto(`${baseUrl}/index.html`, { waitUntil: "load", timeout: 30000 });
    await page.waitForTimeout(settleMs);
    const reqs = [];
    page.on("requestfinished", (r) => reqs.push(r));
    page.on("requestfailed", (r) => reqs.push(r));
    if (which === "stock") {
      await page.evaluate((c) => { Promise.resolve(openStock(c)).catch(() => {}); }, code);
      await page.waitForTimeout(4000);
      const subs = await page.evaluate(() => [...document.querySelectorAll("#stock-tabs button[data-sub]")].map(b => b.dataset.sub));
      for (const s of subs) {
        await page.evaluate((s) => { const b = document.querySelector(`#stock-tabs button[data-sub="${s}"]`); if (b) b.click(); }, s);
        await page.waitForTimeout(1500);
      }
    } else {
      await page.evaluate(() => { const b = document.querySelector('nav#nav button[data-scr="picks"]'); if (b) b.click(); });
      await page.waitForTimeout(6000);
    }
    const rows = await sizeRows(reqs, origin);
    return { total: rows.reduce((s, x) => s + (x.bytes || 0), 0), rows };
  } finally { await ctx.close(); }
}

if (process.argv[1] && process.argv[1].endsWith("measure_page_loads.mjs")) {
  const { chromium } = await import("@playwright/test");
  const a = process.argv.slice(2);
  const url = a.includes("--url") ? a[a.indexOf("--url") + 1] : "http://localhost:8792";
  const code = a.includes("--code") ? a[a.indexOf("--code") + 1] : "2330";
  const browser = await chromium.launch();
  try {
    for (const w of ["stock", "picks"]) {
      const r = await measurePage(browser, url, w, { code });
      console.log(`## ${w === "stock" ? "個股頁 " + code + "（含四個子分頁）" : "選股頁"}：${(r.total / 1024).toFixed(1)} KB（${r.rows.length} 個請求）`);
      for (const x of r.rows.slice(0, 12)) console.log(`  ${String(x.bytes).padStart(8)}  ${x.how.padEnd(7)} ${x.url}`);
    }
  } finally { await browser.close(); }
}
