// 先.一四八-3（收件匣 037／038 P2）：首頁 393 寬截圖（改版前後對照用）。用法：node scripts/home_shot.mjs <輸出 png> [網址] [light|dark|system]
import { chromium } from "@playwright/test";
const [out, base = "http://localhost:8792", theme = ""] = process.argv.slice(2);
const b = await chromium.launch();
const ctx = await b.newContext({ viewport: { width: 393, height: 852 }, deviceScaleFactor: 2, serviceWorkers: "block", colorScheme: "dark" });
const p = await ctx.newPage();
if (theme) await p.addInitScript((t) => { try { localStorage.setItem("alpha_theme", t); } catch (e) {} }, theme);
await p.goto(`${base}/index.html`, { waitUntil: "load" });
await p.waitForTimeout(7000);
const h = await p.evaluate(() => Math.min(9000, document.getElementById("scr-home").scrollHeight + 200));
await p.setViewportSize({ width: 393, height: h }); await p.waitForTimeout(1500);
await p.screenshot({ path: out });
await b.close();
console.log(out, h);
