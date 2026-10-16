// 先.一〇三-13b 驗收：逐頁打開，掃「畫面上看得到的文字」（innerText，不含原始碼註解）裡的工程術語。
// 用法：先在 alpha-app 目錄開 python -m http.server 8792，再 node scripts/jargon_scan_13b.mjs
import { chromium } from "@playwright/test";
const base = process.env.BASE_URL || "http://127.0.0.1:8792";
const TERMS = [/Tailscale/i, /Funnel/i, /Access Client/i, /#\d{2,3}(?!\d)/, /holdout/i, /\bDSR\b/, /天條[一二三]/, /先\.[一二三四五六七八九十〇]+/,
  /常備\.開發/, /lightweight-charts/i, /上櫃解析待修/, /非逐筆\s*tick/i, /\b(?:SERVICES|MANUFACTURING|RETAIL|WHOLESALE|FINANCE|MINING|CONSTRUCTION)[A-Z\-, ]*/, /\b[A-Z][A-Z\-&, ]{14,}\b/];
const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 393, height: 852 }, serviceWorkers: "block" });
const page = await ctx.newPage();
await page.goto(`${base}/index.html`, { waitUntil: "networkidle", timeout: 30000 });
await page.waitForTimeout(2500);
const hits = {};
async function scan(label) {
  const txt = await page.evaluate(() => {
    const s = document.querySelector(".screen.active"); if (!s) return "";
    // 收起的 <details> 也算（點開就看得到），但 <script>/<style> 不算
    return [...s.querySelectorAll("*")].filter(e => !["SCRIPT","STYLE"].includes(e.tagName) && (e.checkVisibility ? e.checkVisibility() || e.closest("details:not([open])") && e.closest("details").checkVisibility() : true)).map(e => [...e.childNodes].filter(n => n.nodeType === 3).map(n => n.textContent).join(" ")).join("\n")
      + "\n" + [...s.querySelectorAll("[title]")].map(e => e.getAttribute("title")).join("\n");
  });
  for (const line of txt.split("\n")) for (const t of TERMS) { const m = line.match(t); if (m) { (hits[label] ||= new Set()).add(`${m[0]} ⟵ ${line.trim().slice(0, 140)}`); } }
}
for (const scr of ["home", "market", "chips-market", "picks", "trade", "journal", "settings"]) {
  await page.evaluate((s) => go(s), scr); await page.waitForTimeout(2500); await scan(scr);
}
for (const code of ["2330", "3324", "6488", "AAPL", "NVDA"]) {
  await page.evaluate((c) => openStock(c), code); await page.waitForTimeout(2500);
  for (const sub of ["ov", "chip", "fin", "events", "research"]) {
    const b = await page.$(`#stock-tabs button[data-sub="${sub}"]`); if (b) { await b.click().catch(() => {}); await page.waitForTimeout(1200); }
    await scan(`stock:${code}:${sub}`);
  }
}
await page.evaluate(() => go("picks")); await page.waitForTimeout(3000);
const reportCodes = await page.evaluate(() => { const c = (currentPicksCache() || {}).stocks || []; return [...new Set(["3324", "2330", ...c.slice(0, 3).map((r) => r.code)])]; });
for (const code of reportCodes) {
  const ok = await page.evaluate((c) => { showReport(c); return true; }, code).catch(() => false);
  await page.waitForTimeout(3000); if (ok) await scan(`report:${code}`);
}
await browser.close();
for (const [k, v] of Object.entries(hits)) { console.log(`== ${k}`); for (const x of v) console.log("  " + x); }
console.log(Object.keys(hits).length ? `共 ${Object.keys(hits).length} 頁有術語` : "沒有掃到術語");
