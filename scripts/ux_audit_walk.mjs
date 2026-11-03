// 先.一四八-2（收件匣 037 P1）：以人為本全頁實測——393 寬逐頁、逐子分頁截全頁圖，並抓每張卡片標題與畫面上出現的日期，
// 跟最近交易日比對（只列出，不判定），輸出 JSON 給人工逐張看。用法：node scripts/ux_audit_walk.mjs <輸出資料夾> [網址] [tag]
import { chromium } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const outDir = process.argv[2] || "research/data/screenshots/ux_audit_20261104";
const base = process.argv[3] || "http://localhost:8792";
const tag = process.argv[4] || "before";
fs.mkdirSync(outDir, { recursive: true });
const b = await chromium.launch();
const ctx = await b.newContext({ viewport: { width: 393, height: 852 }, deviceScaleFactor: 2, serviceWorkers: "block" });
const p = await ctx.newPage();
const errs = []; p.on("pageerror", (e) => errs.push(String(e.message || e)));
await p.goto(`${base}/index.html`, { waitUntil: "load" });
await p.waitForTimeout(5000);
const stops = [
  ["home", null], ["market", null], ["picks", null], ["lab", null],
  ["trade", "bots"], ["trade", "strategy"], ["trade", "monitor"], ["trade", "picks"], ["trade", "journal"], ["settings", null],
];
const report = { tag, at: new Date().toISOString(), ltd: await p.evaluate(() => lastTradingDay("tw")), pages: [], errors: errs };
for (const [scr, sub] of stops) {
  await p.evaluate((s) => go(s), scr);
  if (sub) { await p.waitForTimeout(1500); await p.evaluate((s) => { const x = document.querySelector(`#trade-tabs button[data-sub="${s}"]`); if (x) x.click(); }, sub); }
  await p.waitForTimeout(6000);
  // 全頁：把視窗拉高到內容高度再截
  const h = await p.evaluate((s) => Math.min(12000, Math.max(852, (document.getElementById("scr-" + s) || document.body).scrollHeight + 160)), scr);
  await p.setViewportSize({ width: 393, height: h });
  await p.waitForTimeout(800);
  const name = `${tag}_${scr}${sub ? "_" + sub : ""}.png`;
  await p.screenshot({ path: path.join(outDir, name), fullPage: false });
  const cards = await p.evaluate((s) => {
    const root = document.getElementById("scr-" + s); if (!root) return [];
    return [...root.querySelectorAll(".card")].filter((c) => c.offsetParent !== null).map((c) => {
      const t = (c.querySelector("h3")?.innerText || "").split("\n")[0].trim();
      const txt = c.innerText.replace(/\s+/g, " ");
      const dates = [...new Set((txt.match(/(?<![\d/])(1[0-2]|0?[1-9])\/([0-3]?\d)(?![\d/])/g) || []))];
      return { title: t, dates, len: txt.length, sample: txt.slice(0, 160) };
    });
  }, scr);
  report.pages.push({ scr, sub, shot: name, height: h, cards });
  await p.setViewportSize({ width: 393, height: 852 });
}
fs.writeFileSync(path.join(outDir, `${tag}_report.json`), JSON.stringify(report, null, 1));
await b.close();
console.log(JSON.stringify({ shots: report.pages.map((x) => x.shot), errors: errs.length, ltd: report.ltd }));
