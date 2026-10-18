// 先.一一二 驗收截圖：393×852 深／淺色——新導覽列（今日頁）、研究室三塊（上／下兩張）、交易→日誌、右上設定、首頁研究室入口、更新橫幅。
// 存 research/ux_shots_112/（.gitignore，不進公開 repo），量測寫 metrics.json。
// 限制：桌面瀏覽器沒有 iPhone 狀態列，env(safe-area-inset-top)＝0；橫幅這張只驗樣式有加 safe-area，實際不壓狀態列要在手機上看。
// 用法：先在 alpha-app 目錄開 python -m http.server 8792，再 node scripts/ux_shots_112.mjs
import { chromium } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const base = process.env.BASE_URL || "http://127.0.0.1:8792";
const out = path.join("research", "ux_shots_112");
fs.mkdirSync(out, { recursive: true });
const metrics = {};
const browser = await chromium.launch();
for (const scheme of ["dark", "light"]) {
  const ctx = await browser.newContext({ viewport: { width: 393, height: 852 }, colorScheme: scheme, serviceWorkers: "block" });
  const page = await ctx.newPage();
  const pe = [];
  page.on("pageerror", (e) => pe.push(String(e)));
  await page.goto(`${base}/index.html`, { waitUntil: "networkidle", timeout: 30000 });
  await page.waitForTimeout(2500);
  const shot = (n) => page.screenshot({ path: path.join(out, `${n}_${scheme}.png`) });
  const m = {};
  // 今日（新導覽列＋右上齒輪）
  await shot("home_nav");
  m.nav = await page.evaluate(() => [...document.querySelectorAll("#nav button[data-scr]")].map((b) => b.textContent.trim()));
  // 首頁研究室入口（捲到今日事件下面）
  await page.waitForFunction(() => { const e = document.getElementById("home-lab-line"); return e && !e.hidden; }, null, { timeout: 15000 }).catch(() => {});
  await page.evaluate(() => { const e = document.getElementById("home-lab-line"); if (e) e.scrollIntoView({ block: "center" }); });
  await page.waitForTimeout(500);
  await shot("home_lab_entry");
  m.homeLab = await page.evaluate(() => (document.getElementById("home-lab-line") || {}).textContent || "");
  // 研究室
  await page.click('#nav button[data-scr="lab"]');
  await page.waitForFunction(() => document.querySelectorAll("#lab-deep-list .lab-deep").length > 0 && document.querySelectorAll("#scr-lab #radar-list .press").length > 0, null, { timeout: 20000 }).catch(() => {});
  await page.waitForTimeout(1500);
  await page.evaluate(() => { const mm = document.getElementById("main"); if (mm) mm.scrollTop = 0; });
  await shot("lab_top");
  await page.evaluate(() => { const e = document.getElementById("picks-radar-card"); if (e) e.scrollIntoView({ block: "start" }); });
  await page.waitForTimeout(500);
  await shot("lab_radar");
  await page.evaluate(() => { const e = document.getElementById("lab-heat-card"); if (e) e.scrollIntoView({ block: "start" }); });
  await page.waitForTimeout(500);
  await shot("lab_heat");
  m.lab = await page.evaluate(() => ({ deep: document.querySelectorAll("#lab-deep-list .lab-deep").length, radar: document.querySelectorAll("#scr-lab #radar-list .press").length,
    heat: document.querySelectorAll("#industry-heat-rows tr, #industry-heat-rows .row, #industry-heat-rows .f").length }));
  // 交易 → 日誌
  await page.click('#nav button[data-scr="trade"]');
  await page.waitForTimeout(1500);
  await page.click('#trade-tabs button[data-sub="journal"]');
  await page.waitForTimeout(1500);
  await page.evaluate(() => { const mm = document.getElementById("main"); if (mm) mm.scrollTop = 0; });
  await shot("trade_journal");
  m.journal = await page.evaluate(() => ({ active: document.getElementById("scr-journal").classList.contains("active"), navOn: (document.querySelector("#nav button.on") || {}).textContent?.trim() }));
  // 右上設定
  await page.click("#hdr-settings");
  await page.waitForTimeout(1500);
  await shot("settings_gear");
  m.settings = await page.evaluate(() => document.getElementById("scr-settings").classList.contains("active"));
  // 更新橫幅
  await page.evaluate(() => { go("home"); const b = document.getElementById("new-version-banner"); if (b) { b.textContent = "有新版，點此更新"; b.style.display = "block"; } });
  await page.waitForTimeout(600);
  await shot("update_banner");
  m.banner = await page.evaluate(() => { const b = document.getElementById("new-version-banner"); return { style: b.getAttribute("style").match(/padding-top:[^;]+/)?.[0], top: Math.round(b.getBoundingClientRect().top), h: Math.round(b.getBoundingClientRect().height) }; });
  m.pageerrors = pe.slice(0, 3);
  metrics[scheme] = m;
  await ctx.close();
}
await browser.close();
fs.writeFileSync(path.join(out, "metrics.json"), JSON.stringify(metrics, null, 2));
console.log(JSON.stringify(metrics, null, 1));
