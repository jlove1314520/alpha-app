// 先.一四八-1：新版外殼已在手機上之後，再出新版時要「自動接手＋自動重載一次」，不用使用者動手。
import { chromium, webkit } from "@playwright/test";
import fs from "node:fs"; import os from "node:os"; import path from "node:path";
const [bt, ctl, dir, port = "8795"] = process.argv.slice(2);
const B = bt === "webkit" ? webkit : chromium, base = `http://127.0.0.1:${port}`;
const ctx = await B.launchPersistentContext(fs.mkdtempSync(path.join(os.tmpdir(), "alpha-ar-")), { viewport: { width: 393, height: 852 } });
const out = {};
try {
  fs.writeFileSync(ctl, dir);
  const p = await ctx.newPage();
  await p.goto(`${base}/index.html`, { waitUntil: "load" });
  await p.waitForFunction(() => navigator.serviceWorker.controller, null, { timeout: 15000 }).catch(() => {});
  if (!(await p.evaluate(() => !!navigator.serviceWorker.controller))) await p.reload({ waitUntil: "load" });
  await p.waitForTimeout(3000);
  await p.evaluate(() => { window.__marker = "same-page"; });
  out.before = await p.evaluate(async () => (await caches.keys()).filter((k) => k.startsWith("alpha-v")));
  fs.writeFileSync(ctl, dir + "|bump");             // 伺服器出新版（sw.js 內容不同）
  await p.evaluate(() => navigator.serviceWorker.getRegistration().then((r) => r && r.update()));  // 等同 App 定時檢查
  await p.waitForFunction(() => window.__marker !== "same-page", null, { timeout: 20000 }).catch(() => {});
  await p.waitForLoadState("load");
  out.reloaded = await p.evaluate(() => window.__marker !== "same-page");
  out.after = await p.evaluate(async () => (await caches.keys()).filter((k) => k.startsWith("alpha-v")));
  out.waiting = await p.evaluate(async () => !!(await navigator.serviceWorker.getRegistration()).waiting);
} catch (e) { out.error = String(e); } finally { await ctx.close(); fs.writeFileSync(ctl, dir); }
console.log(JSON.stringify(out));
