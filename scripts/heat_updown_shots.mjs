// 先.一〇九-36 驗收腳本：類股熱力圖與圖例在兩種漲跌慣例下的顏色。
// 用法：node scripts/heat_updown_shots.mjs（預設打 http://localhost:8792；伺服器用 python scripts/ensure_smoke_server.py）。
// 截圖存 repo 根目錄 heat_updown_TW.png／heat_updown_INTL.png（一次性驗收證據，不進版控），
// 並印出漲／跌圖例色塊與「漲幅最大、跌幅最大」兩塊磚的實際背景色，確認圖例與磚塊一致。
import { chromium } from "@playwright/test";

const BASE_URL = process.env.ALPHA_APP_URL || "http://localhost:8792";

async function shot(browser, scheme) {
  const page = await browser.newPage({ viewport: { width: 393, height: 852 } });
  const errs = [];
  page.on("pageerror", (e) => errs.push(String(e)));
  await page.addInitScript((k) => localStorage.setItem("alpha_color_scheme", k), scheme);
  await page.goto(`${BASE_URL}/index.html`, { waitUntil: "networkidle", timeout: 20000 });
  await page.waitForTimeout(800);
  await page.evaluate(() => window.go("market"));
  await page.waitForTimeout(2500);
  const grid = page.locator("#heat-grid");
  await grid.scrollIntoViewIfNeeded();
  await page.waitForTimeout(400);
  const info = await page.evaluate(() => {
    const bg = (el) => (el ? getComputedStyle(el).backgroundColor : null);
    const tiles = [...document.querySelectorAll("#heat-grid > *")].map((t) => {
      const m = (t.innerText || "").match(/([+-]?\d+(?:\.\d+)?)%/);
      return { pct: m ? parseFloat(m[1]) : null, bg: getComputedStyle(t).backgroundColor };
    }).filter((t) => t.pct != null).sort((a, b) => b.pct - a.pct);
    return {
      updown: document.documentElement.getAttribute("data-updown"),
      legendUp: bg(document.getElementById("heat-lg-up")),
      legendDown: bg(document.getElementById("heat-lg-down")),
      topTile: tiles[0] || null,
      bottomTile: tiles[tiles.length - 1] || null,
      nTiles: tiles.length,
    };
  });
  await page.screenshot({ path: `heat_updown_${scheme}.png` });
  console.log(scheme, JSON.stringify(info), "pageerror:", errs.length);
  await page.close();
}

const browser = await chromium.launch({ headless: true });
try {
  await shot(browser, "TW");
  await shot(browser, "INTL");
} finally {
  await browser.close();
}
