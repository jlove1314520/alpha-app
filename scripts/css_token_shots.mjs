// 2026-10-14 先.九十四-5i：app.css 換成 CSS 變數前後的「外觀不變」證據。
// 393×852、深色＋淺色，各分頁首屏截圖存到 research/ux_shots/css_tokens/<標籤>/（不進 repo）。
// 為了讓前後兩次截圖可比：凍結時鐘、擋掉所有非本機請求、不註冊 service worker，
// 並額外輸出每個元素的 computed style 摘要（字級／間距／圓角），比對用 scripts/css_token_diff.py。
// 用法：node scripts/css_token_shots.mjs before   （改之前）
//       node scripts/css_token_shots.mjs after    （改之後）
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "@playwright/test";
import { launchGuarded } from "./pw_guard.mjs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const tag = process.argv[2] || "before";
const url = process.argv[3] || "http://localhost:8792/index.html";
const outDir = path.join(ROOT, "research", "ux_shots", "css_tokens", tag);
fs.mkdirSync(outDir, { recursive: true });
const PAGES = ["home", "market", "picks", "trade", "journal", "settings"];
const PROPS = ["font-size", "padding", "margin", "gap", "border-radius", "line-height"];

const { browser, close } = await launchGuarded(chromium, {}, { label: "css_token_shots", hardTimeoutMs: 6 * 60 * 1000 });
try {
  for (const theme of ["dark", "light"]) {
    const ctx = await browser.newContext({ viewport: { width: 393, height: 852 }, deviceScaleFactor: 1,
      serviceWorkers: "block", colorScheme: theme, reducedMotion: "reduce" });
    await ctx.route("**/*", (r) => { const u = r.request().url(); return /^https?:\/\/(localhost|127\.0\.0\.1)[:/]/.test(u) ? r.continue() : r.abort(); });
    const page = await ctx.newPage();
    await page.clock.install({ time: new Date("2026-10-14T03:00:00Z") });
    await page.goto(url, { waitUntil: "load", timeout: 60000 });
    await page.clock.runFor(4000);
    await page.waitForTimeout(2500);
    for (const g of PAGES) {
      await page.evaluate((g) => { const b = document.querySelector(`nav#nav button[data-scr="${g}"]`); if (b) b.click(); }, g);
      await page.clock.runFor(1500);
      await page.waitForTimeout(1500);
      await page.evaluate(() => { window.scrollTo(0, 0); for (const el of [document.scrollingElement, document.getElementById("main"), document.getElementById("app")]) if (el) el.scrollTop = 0; });
      await page.waitForTimeout(200);
      await page.screenshot({ path: path.join(outDir, `${theme}-${g}.png`), animations: "disabled", caret: "hide" });
      const styles = await page.evaluate(({ g, PROPS }) => {
        const root = document.getElementById(`scr-${g}`) || document.body;
        const els = [document.querySelector("header"), document.querySelector("nav#nav"), ...root.querySelectorAll("*")].filter(Boolean);
        return els.map((el) => { const s = getComputedStyle(el); return PROPS.map((p) => s.getPropertyValue(p)).join("|"); });
      }, { g, PROPS });
      fs.writeFileSync(path.join(outDir, `${theme}-${g}.styles.json`), JSON.stringify(styles));
    }
    await ctx.close();
  }
} finally { await close(); }
console.log(`截圖完成：${outDir}`);
