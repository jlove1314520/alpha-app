// 先.一〇五 驗收截圖：393×852 深／淺色——今日、個股 2330（擋掉 cdn.jsdelivr.net）、籌碼總覽、月營收（1513，13 個月）。
// 存 research/ux_shots_105/（.gitignore，不進公開 repo），並把量測寫 metrics.json。
// 用法：先在 alpha-app 目錄開 python -m http.server 8792，再 node scripts/ux_shots_105.mjs
import { chromium } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const base = process.env.BASE_URL || "http://127.0.0.1:8792";
const out = path.join("research", "ux_shots_105");
fs.mkdirSync(out, { recursive: true });
const metrics = {};
const browser = await chromium.launch();
for (const scheme of ["dark", "light"]) {
  const ctx = await browser.newContext({ viewport: { width: 393, height: 852 }, colorScheme: scheme, serviceWorkers: "block" });
  await ctx.route(/cdn\.jsdelivr\.net/, (r) => r.abort());
  const page = await ctx.newPage();
  const pe = [];
  page.on("pageerror", (e) => pe.push(String(e)));
  await page.goto(`${base}/index.html`, { waitUntil: "networkidle", timeout: 30000 });
  await page.waitForTimeout(2000);
  const m = {};
  // 今日
  await page.screenshot({ path: path.join(out, `home_${scheme}.png`) });
  m.home = await page.evaluate(() => {
    const scr = document.getElementById("scr-home");
    const card = [...scr.querySelectorAll(".card")].find((c) => !c.hidden && c.getBoundingClientRect().height > 0);
    const mev = document.getElementById("home-my-events-card");
    return { first_card_y: card ? Math.round(card.getBoundingClientRect().top) : null,
             my_events_title: mev ? (mev.querySelector("h3") || {}).textContent : null };
  });
  // 個股 2330（擋 CDN）
  const t0 = Date.now();
  await page.evaluate(() => openStock("2330"));
  const fell = await page.waitForFunction(() => /K 線圖暫時載不到/.test((document.getElementById("trend-chart") || {}).textContent || ""), null, { timeout: 10000 }).then(() => true).catch(() => false);
  m.stock2330 = { fallback_within_10s: fell, secs: +((Date.now() - t0) / 1000).toFixed(1) };
  await page.evaluate(() => { const mm = document.getElementById("main"); if (mm) mm.scrollTop = 0; });
  await page.screenshot({ path: path.join(out, `stock2330_cdnblocked_${scheme}.png`) });
  // 籌碼總覽
  await page.evaluate(() => go("chips-market"));
  await page.waitForTimeout(2500);
  await page.screenshot({ path: path.join(out, `chips_${scheme}.png`), fullPage: false });
  m.chips = await page.evaluate(() => {
    const el = document.getElementById("inst-bars"), v = el && el.querySelector(".db-val");
    const mw = document.getElementById("margin-calib-warn");
    return { inst_label_corner: !!(el && el.classList.contains("val-corner")), inst_label: v ? v.textContent : null,
             margin_warn_lines: mw ? Math.round(mw.getBoundingClientRect().height / parseFloat(getComputedStyle(mw).lineHeight || "16")) : 0,
             margin_ck_val_line: !!document.getElementById("margin-ck-val") };
  });
  // 月營收（1513）
  await page.evaluate(() => openStock("1513"));
  await page.waitForTimeout(2500);
  await page.click('#stock-tabs button[data-sub="fin"]');
  await page.waitForTimeout(2500);
  const card = await page.$("#sub-rev .card");
  if (card) await card.screenshot({ path: path.join(out, `revenue1513_${scheme}.png`) });
  m.revenue = await page.evaluate(() => {
    const ys = [...document.querySelectorAll("#rev-chart-amt .rc-yoy,#rev-chart-amt .rc-ymax")];
    let o = 0;
    for (let i = 0; i < ys.length; i++) for (let j = i + 1; j < ys.length; j++) {
      const a = ys[i].getBoundingClientRect(), b = ys[j].getBoundingClientRect();
      if (a.left < b.right - 0.5 && b.left < a.right - 0.5 && a.top < b.bottom - 0.5 && b.top < a.bottom - 0.5) o++;
    }
    return { bars: document.querySelectorAll("#rev-chart-amt .rc-bar").length, yoy_labels: document.querySelectorAll("#rev-chart-amt .rc-yoy").length,
             yoy_block_hidden: !!document.getElementById("rev-chart-yoy").hidden, label_overlaps: o };
  });
  m.pageerrors = pe.slice(0, 3);
  metrics[scheme] = m;
  await ctx.close();
}
await browser.close();
fs.writeFileSync(path.join(out, "metrics.json"), JSON.stringify(metrics, null, 2));
console.log(JSON.stringify(metrics, null, 1));
