// 2026-10-11 先.七十二-C8：390×844 逐頁首屏檢查（＋截圖存 research/ux_shots/，不進 repo）。
// 首屏＝捲到最上方時、底部導覽列以上看得到的範圍。規則：首屏內 .card 不得超過 3 張；首屏內說明文字（.note）不得超過 2 行。
// 匯出 checkFirstScreens(page, {shotsDir}) 給冒煙用；直接執行會截圖並列出結果。
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
export const PAGES = [
  { name: "home", go: "home" }, { name: "market", go: "market" }, { name: "picks", go: "picks" },
  { name: "trade", go: "trade" }, { name: "journal", go: "journal" }, { name: "settings", go: "settings" },
  { name: "stock", stock: "2330" },
];
export const MAX_CARDS = 3, MAX_NOTE_LINES = 2;

async function measure(page, scr) {
  return page.evaluate(({ scr, MAX_NOTE_LINES }) => {
    const nav = document.querySelector("nav#nav");
    const limit = nav ? nav.getBoundingClientRect().top : innerHeight;
    const root = document.getElementById(scr);
    const vis = (el) => { const st = getComputedStyle(el); if (st.display === "none" || st.visibility === "hidden") return false;
      for (let p = el; p && p !== document.body; p = p.parentElement) { const s = getComputedStyle(p); if (s.display === "none") return false;
        if (p.tagName === "DETAILS" && !p.open && p !== el && !el.closest("summary")) return false; }
      const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
    const inFirst = (el) => { const r = el.getBoundingClientRect(); return r.top < limit - 4 && r.bottom > 0; };
    const cards = [...root.querySelectorAll(".card")].filter(c => !c.parentElement.closest(".card") && vis(c) && inFirst(c))
      .map(c => ((c.querySelector("h3") || {}).textContent || c.id || "(無標題)").replace(/\s+/g, " ").trim().slice(0, 14));
    const longNotes = [];
    for (const n of root.querySelectorAll(".note")) {
      if (!vis(n) || !inFirst(n)) continue;
      const st = getComputedStyle(n);
      let lh = parseFloat(st.lineHeight); if (!lh) lh = parseFloat(st.fontSize) * 1.45;
      const h = n.getBoundingClientRect().height - parseFloat(st.paddingTop || 0) - parseFloat(st.paddingBottom || 0);
      const lines = Math.round(h / lh);
      if (lines > MAX_NOTE_LINES) longNotes.push(`${lines} 行：${n.innerText.replace(/\s+/g, " ").slice(0, 30)}`);
    }
    return { cards, longNotes, limit: Math.round(limit) };
  }, { scr, MAX_NOTE_LINES });
}

export async function checkFirstScreens(page, { shotsDir = null, settle = 1500 } = {}) {
  const out = {};
  for (const pg of PAGES) {
    if (pg.stock) { await page.evaluate((c) => openStock(c), pg.stock); }
    else { await page.evaluate((g) => { const b = document.querySelector(`nav#nav button[data-scr="${g}"]`); if (b) b.click(); }, pg.go); }
    await page.waitForTimeout(settle);
    // App 的捲動容器是 <main>（不是 window）；兩者都捲回最上，量到的才是真正的首屏
    await page.evaluate(() => { window.scrollTo(0, 0); for (const el of [document.scrollingElement, document.getElementById("main"), document.getElementById("app")]) if (el) el.scrollTop = 0; });
    await page.waitForTimeout(200);
    const r = await measure(page, pg.stock ? "scr-stock" : `scr-${pg.go}`);
    if (shotsDir) { fs.mkdirSync(shotsDir, { recursive: true }); await page.screenshot({ path: path.join(shotsDir, `${pg.name}.png`) }); r.shot = path.join(shotsDir, `${pg.name}.png`); }
    out[pg.name] = r;
  }
  return out;
}

if (process.argv[1] && process.argv[1].endsWith("ux_screens.mjs")) {
  const { chromium } = await import("@playwright/test");
  const { launchGuarded } = await import("./pw_guard.mjs");
  const url = process.argv[2] || "http://localhost:8792/index.html";
  const { browser, close } = await launchGuarded(chromium, {}, { label: "ux_screens", hardTimeoutMs: 5 * 60 * 1000 });
  let res;
  try {
    const page = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 });
    await page.goto(url, { waitUntil: "networkidle", timeout: 60000 });
    await page.waitForTimeout(2000);
    res = await checkFirstScreens(page, { shotsDir: path.join(ROOT, "research", "ux_shots") });
  } finally { await close(); }
  let bad = 0;
  for (const [k, r] of Object.entries(res)) {
    const ok = r.cards.length <= MAX_CARDS && !r.longNotes.length;
    if (!ok) bad++;
    console.log(`${ok ? "PASS" : "FAIL"} ${k}：首屏 ${r.cards.length} 張卡（${r.cards.join("／")}）${r.longNotes.length ? "；超過 2 行：" + r.longNotes.join("｜") : ""}`);
  }
  console.log(bad ? `=== ${bad} 頁不符 ===` : "=== 首屏全部符合 ===");
  process.exit(bad ? 1 : 0);
}
