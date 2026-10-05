// 先.十四-一：紅色橫幅截圖證據。攔截 data/STATUS.json 注入 claude_auth 狀態，
// 不改真實 STATUS.json（那支由排程寫，手改會被下一輪覆蓋，也會污染稽核紀錄）。
// 用法：先開 `python -m http.server 8792`，再 `node scripts/shot_claude_auth_banner.mjs`
import { chromium } from "@playwright/test";
import { readFileSync, mkdirSync } from "node:fs";

const BASE = "http://localhost:8792";
const OUT = "research/data/shots";
mkdirSync(OUT, { recursive: true });
const real = JSON.parse(readFileSync("data/STATUS.json", "utf8"));

const CASES = [
  ["auth_expired", { overall_status: "AUTH_EXPIRED", detail: "marathon:AUTH_EXPIRED（OAuth session expired and could not be refreshed）" }],
  ["quota", { overall_status: "QUOTA_EXCEEDED", detail: "devqueue:QUOTA_EXCEEDED（usage limit）" }],
  ["stalled_3h", { overall_status: "STALLED_3H", detail: "marathon:STALLED_3H(39.2h)；devqueue:STALLED_3H(39.1h)" }],
  ["ok", { overall_status: "OK", detail: "三支launcher皆正常" }],
];

const browser = await chromium.launch({ headless: true });
let bad = 0;
for (const [name, ca] of CASES) {
  const page = await browser.newPage({ viewport: { width: 393, height: 852 }, ignoreHTTPSErrors: true });
  const doc = JSON.parse(JSON.stringify(real));
  doc.local_schedule_heartbeat = { ...(doc.local_schedule_heartbeat || {}), claude_auth: ca };
  await page.route("**/data/STATUS.json*", (r) =>
    r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(doc) }));
  await page.goto(BASE + "/index.html", { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(3500);
  const el = page.locator("#claude-auth-banner");
  const visible = await el.isVisible();
  const text = (await el.textContent()) || "";
  const expectVisible = ca.overall_status !== "OK";
  const ok = visible === expectVisible && (!expectVisible || text.length > 10);
  if (!ok) bad++;
  console.log(`${ok ? "PASS" : "FAIL"} ${name}: visible=${visible} (expect ${expectVisible}) text="${text.slice(0, 60)}"`);
  await page.screenshot({ path: `${OUT}/claude_auth_${name}.png`, fullPage: false });
  await page.close();
}
await browser.close();
console.log(bad ? `失敗 ${bad} 項` : `全部通過，截圖在 ${OUT}/`);
process.exit(bad ? 1 : 0);
