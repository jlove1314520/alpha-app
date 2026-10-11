// 2026-10-11 先.六十六-2：手機視窗（390×844）版面結構實測。
// 用法：先在 alpha-app 目錄跑 python -m http.server 8792，再 node scripts/layout_check.mjs [網址]
// 檢查：body 直接子元素只能是 #new-version-banner、#app、script；nav 底部固定（top > 700）；
// 六個分頁逐一切換，該頁 .screen 高度 > 0 且位於 <main id="main"> 內。任一失敗 exit 1。
import { chromium } from "@playwright/test";

const url = process.argv[2] || "http://localhost:8792/index.html";
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
await page.goto(url, { waitUntil: "networkidle", timeout: 30000 });
await page.waitForTimeout(1500);

let ok = true;
const out = (pass, msg) => { if (!pass) ok = false; console.log(`${pass ? "PASS" : "FAIL"} - ${msg}`); };

const kids = await page.evaluate(() => [...document.body.children].map(e =>
  e.tagName === "SCRIPT" ? "script" : (e.id ? `#${e.id}` : e.tagName.toLowerCase())));
const bad = kids.filter(k => !["#new-version-banner", "#app", "script"].includes(k));
out(bad.length === 0, `body 直接子元素：${[...new Set(kids)].join("、")}${bad.length ? `（不允許：${bad.join("、")}）` : ""}`);

const nav = await page.evaluate(() => {
  const n = document.querySelector("nav#nav");
  const r = n.getBoundingClientRect();
  return { top: Math.round(r.top), height: Math.round(r.height), inApp: !!n.closest("#app") };
});
out(nav.top > 700 && nav.inApp, `nav top=${nav.top}px、高 ${nav.height}px、在 #app 內=${nav.inApp}`);

for (const scr of ["home", "market", "picks", "trade", "journal", "settings"]) {
  await page.click(`nav#nav button[data-scr="${scr}"]`);
  await page.waitForTimeout(600);
  const r = await page.evaluate((s) => {
    const el = document.getElementById(`scr-${s}`);
    const navTop = document.querySelector("nav#nav").getBoundingClientRect().top;
    return { h: Math.round(el.getBoundingClientRect().height), inMain: !!el.closest("main#main"),
             active: el.classList.contains("active"), navTop: Math.round(navTop) };
  }, scr);
  out(r.h > 0 && r.inMain && r.active && r.navTop > 700,
    `#scr-${scr}：高 ${r.h}px、在 main 內=${r.inMain}、active=${r.active}、nav top=${r.navTop}px`);
}
await browser.close();
console.log(ok ? "=== 版面結構全部通過 ===" : "=== 版面結構有 FAIL ===");
process.exit(ok ? 0 : 1);
