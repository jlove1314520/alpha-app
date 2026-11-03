// 先.一四八-1（收件匣 037 P0）重現：「10/15 舊 SW＋舊資料快取的使用者今天打開」。
// 用法：node scripts/repro_stale_sw.mjs <chromium|webkit> <控制檔 root.txt> <舊版目錄> <新版目錄> [埠 8795]
// 需要先開 switch_server.py（同一個網址、依控制檔切換要送哪個目錄的檔案），因為 SW 綁網域，換版必須同一個 origin。
import { chromium, webkit } from "@playwright/test";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const [bt = "chromium", ctl, oldDir, newDir, port = "8795"] = process.argv.slice(2);
const base = `http://127.0.0.1:${port}`;
const B = bt === "webkit" ? webkit : chromium;
const ud = fs.mkdtempSync(path.join(os.tmpdir(), "alpha-sw-repro-"));
const out = { browser: bt, steps: [] };

async function snap(page, label) {
  const s = await page.evaluate(async () => {
    const txt = (id) => (document.getElementById(id) || {}).textContent || "";
    const keys = await caches.keys().catch(() => []);
    const reg = await navigator.serviceWorker.getRegistration().catch(() => null);
    return {
      appjs: [...document.scripts].map((x) => x.src).find((x) => /app\.js/.test(x)) || "",
      controller: !!navigator.serviceWorker.controller, waiting: !!(reg && reg.waiting), caches: keys,
      mktTw: txt("mkt-tw").replace(/\s+/g, " ").trim(), stale: txt("data-stale-line"),
      staleAlert: txt("data-stale-alert"),
      home: (document.getElementById("scr-home") || {}).innerText?.slice(0, 400).replace(/\s+/g, " ") || "",
    };
  });
  out.steps.push({ label, ...s });
  await page.screenshot({ path: path.join(os.tmpdir(), `repro_${bt}_${out.steps.length}.png`) }).catch(() => {});
}

const ctx = await B.launchPersistentContext(ud, { viewport: { width: 393, height: 852 } });
try {
  fs.writeFileSync(ctl, oldDir);
  let p = await ctx.newPage();
  await p.goto(`${base}/index.html`, { waitUntil: "load" });
  await p.waitForFunction(() => navigator.serviceWorker && navigator.serviceWorker.controller, null, { timeout: 15000 }).catch(() => {});
  if (!(await p.evaluate(() => !!navigator.serviceWorker.controller))) { await p.reload({ waitUntil: "load" }); }
  await p.waitForTimeout(8000);
  await snap(p, "舊版第一次開（10/15 外殼＋10/15 資料存進快取）");
  await p.close();

  fs.writeFileSync(ctl, newDir);   // 伺服器換成今天的外殼＋今天的資料
  p = await ctx.newPage();
  await p.goto(`${base}/index.html`, { waitUntil: "load" });
  await p.waitForTimeout(4000);
  await snap(p, "今天第一次開：4 秒後");
  await p.waitForTimeout(12000);
  await snap(p, "今天第一次開：16 秒後");
  await p.close();
  p = await ctx.newPage();
  await p.goto(`${base}/index.html`, { waitUntil: "load" });
  await p.waitForTimeout(8000);
  await snap(p, "關掉再開第二次：8 秒後");
} catch (e) { out.error = String(e && e.stack || e); }
finally { await ctx.close(); }
console.log(JSON.stringify(out, null, 1));
