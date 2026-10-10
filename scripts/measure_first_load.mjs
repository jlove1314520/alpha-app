// 常備.開發-20（2026-10-11）：量測「首頁首次載入傳輸量」（全新瀏覽器環境、無快取、無 SW）。
// 同網域檔案：用本機檔案內容模擬 GitHub Pages 的 gzip 傳輸量（Pages 對文字檔一律 gzip；圖片原樣）。
// 跨網域資源：用瀏覽器回報的 encoded 傳輸量（request.sizes()），逾時拿不到就記為未知並列出。
// 用法：node scripts/measure_first_load.mjs [--url http://localhost:8792] [--wait 8000]
// 也被 smoke_test.mjs 匯入（measureFirstLoad）。
import { chromium } from "@playwright/test";
import fs from "node:fs";
import zlib from "node:zlib";
import path from "node:path";

const TEXT_EXT = /\.(html|js|css|json|webmanifest|txt|svg|csv|jsonl)$/i;

export async function measureFirstLoad(browser, baseUrl, waitMs = 8000) {
  const ctx = await browser.newContext({ viewport: { width: 393, height: 852 }, serviceWorkers: "block" });
  const page = await ctx.newPage();
  const reqs = [];
  page.on("requestfinished", (r) => reqs.push(r));
  page.on("requestfailed", (r) => reqs.push(r));
  const origin = new URL(baseUrl).origin;
  await page.goto(`${baseUrl}/index.html`, { waitUntil: "load", timeout: 30000 });
  await page.waitForTimeout(waitMs);
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
  await ctx.close();
  const total = rows.reduce((s, x) => s + (x.bytes || 0), 0);
  return { total, rows: rows.sort((a, b) => (b.bytes || 0) - (a.bytes || 0)), unknown: rows.filter(x => x.bytes == null).length };
}

if (process.argv[1] && process.argv[1].endsWith("measure_first_load.mjs")) {
  const a = process.argv.slice(2);
  const url = a.includes("--url") ? a[a.indexOf("--url") + 1] : "http://localhost:8792";
  const wait = a.includes("--wait") ? +a[a.indexOf("--wait") + 1] : 8000;
  const browser = await chromium.launch({ headless: true });
  const r = await measureFirstLoad(browser, url, wait);
  await browser.close();
  for (const x of r.rows) console.log(`${String(x.bytes ?? "?").padStart(9)}  ${x.how.padEnd(7)} ${x.url}`);
  console.log(`合計 ${(r.total / 1024).toFixed(1)} KB（${r.rows.length} 個請求，未知大小 ${r.unknown} 個）`);
}
