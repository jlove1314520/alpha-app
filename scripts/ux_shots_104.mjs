// 先.一〇四 驗收截圖：393×852 深／淺色，今日／市場／個股2330／選股／交易，存 research/ux_shots_104/<tag>/。
// 同時量「今日頁第一塊內容 y 座標」與「非今日頁橫幅總高」，結果寫 research/ux_shots_104/<tag>/metrics.json。
// 用法：先在 alpha-app 目錄開 python -m http.server 8792，再 node scripts/ux_shots_104.mjs before|after
import { chromium } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const tag = process.argv[2] || "after";
const base = process.env.BASE_URL || "http://127.0.0.1:8792";
const out = path.join("research", "ux_shots_104", tag);
fs.mkdirSync(out, { recursive: true });

const pages = [
  { name: "home", act: (p) => p.evaluate(() => go("home")) },
  { name: "market", act: (p) => p.evaluate(() => go("market")) },
  { name: "stock2330", act: (p) => p.evaluate(() => openStock("2330")) },
  { name: "picks", act: (p) => p.evaluate(() => go("picks")) },
  { name: "trade", act: (p) => p.evaluate(() => go("trade")) },
];

const metrics = {};
const browser = await chromium.launch();
for (const scheme of ["dark", "light"]) {
  const ctx = await browser.newContext({ viewport: { width: 393, height: 852 }, colorScheme: scheme, serviceWorkers: "block" });
  const page = await ctx.newPage();
  await page.goto(`${base}/index.html`, { waitUntil: "networkidle", timeout: 30000 });
  await page.waitForTimeout(1500);
  for (const pg of pages) {
    try {
      await pg.act(page);
      await page.waitForTimeout(1800);
      await page.evaluate(() => { const m = document.getElementById("main"); if (m) m.scrollTop = 0; window.scrollTo(0, 0); });
      await page.screenshot({ path: path.join(out, `${pg.name}_${scheme}.png`) });
      metrics[`${pg.name}_${scheme}`] = await page.evaluate(() => {
        const vis = (el) => { if (!el || el.hidden) return false; const r = el.getBoundingClientRect(); const cs = getComputedStyle(el); return r.height > 0 && cs.display !== "none" && cs.visibility !== "hidden"; };
        // 先.一〇四 驗收量法：橫幅＝總管一行＋原本四條橫幅＋錯誤紀錄（只算看得到的）
        const ids = ["alert-hub", "auto-banner", "diag-banner", "claude-auth-banner", "paper-tracking-banner", "error-log"];
        const banners = ids.map((id) => document.getElementById(id)).filter(vis);
        const bannerH = banners.reduce((s, el) => s + el.getBoundingClientRect().height, 0);
        const scr = document.querySelector(".screen.active");
        const firstCard = scr ? [...scr.querySelectorAll(".card")].find(vis) : null;
        const main = document.getElementById("main");
        return { screen: scr && scr.id, banner_ids: banners.map((b) => b.id), banner_total_h: Math.round(bannerH),
                 first_card_y: firstCard ? Math.round(firstCard.getBoundingClientRect().top) : null,
                 first_card: firstCard ? ((firstCard.querySelector("h3") || {}).textContent || firstCard.id || "").trim().slice(0, 12) : null,
                 main_overflow_x: main ? main.scrollWidth > main.clientWidth + 1 : null };
      });
    } catch (e) {
      metrics[`${pg.name}_${scheme}`] = { error: String(e).slice(0, 200) };
    }
  }
  await ctx.close();
}
await browser.close();
fs.writeFileSync(path.join(out, "metrics.json"), JSON.stringify(metrics, null, 2));
console.log(JSON.stringify(metrics, null, 1));
